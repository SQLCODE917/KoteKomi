"""Model-free trigger-containment candidate split and Gold correction for R2.

The splitter detects every Attachment Candidate that strictly contains a
foreign Event trigger, emits one source-exact resized candidate, and re-derives
that resized candidate's Gold Attachment Set by exact fragment membership.  The
correction never reads a Route Decision and never mutates the original
Proposition Gold.

The report layer re-scores the R1 Route Decisions against the corrected Gold
by recounting the ``none``, ``mixed``, and ``temporal`` error classes on both
frozen partitions and listing every candidate whose comparison changes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentSourceRange,
)
from kotekomi_application.deterministic_dependency_path_attachment_router import (
    AttachmentRouteDecision,
    AttachmentRouteErrorCensus,
    build_error_census,
    classify_error_class,
)

_SHA256 = r"^[a-f0-9]{64}$"
type _EventId = Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
type _CandidateId = Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]


class TriggerContainmentResize(BaseModel):
    """One trigger-containment candidate after its foreign triggers are removed."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    phase: Literal["development", "validation"]
    candidate_range: AttachmentSourceRange
    foreign_trigger_ranges: tuple[AttachmentSourceRange, ...]
    resized_range: AttachmentSourceRange
    label_before: tuple[_EventId, ...]
    label_after: tuple[_EventId, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.foreign_trigger_ranges:
            raise ValueError("A trigger-containment resize requires a foreign trigger.")
        foreign = self.foreign_trigger_ranges
        if foreign != tuple(sorted(foreign, key=lambda item: (item.start, item.end))) or len(
            set(foreign)
        ) != len(foreign):
            raise ValueError("Foreign trigger ranges must be ordered and distinct.")
        for item in self.foreign_trigger_ranges:
            if not (
                self.candidate_range.start < item.start and item.end < self.candidate_range.end
            ):
                raise ValueError("Foreign trigger range is not strictly contained.")
        if not (
            self.candidate_range.start <= self.resized_range.start
            and self.resized_range.end <= self.candidate_range.end
            and (self.resized_range.start, self.resized_range.end)
            != (self.candidate_range.start, self.candidate_range.end)
        ):
            raise ValueError("Resized range is not a proper fragment of the candidate.")
        if not self.resized_range.text.strip():
            raise ValueError("Resized range cannot be whitespace-only.")
        _ordered_distinct("label before", self.label_before)
        _ordered_distinct("label after", self.label_after)
        return self


class CorrectedCandidateLabel(BaseModel):
    """One candidate's corrected Gold Attachment Set in the corrected Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    phase: Literal["development", "validation"]
    source_range: AttachmentSourceRange
    gold_event_ids: tuple[_EventId, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("corrected Gold Event IDs", self.gold_event_ids)
        return self


class CorrectedAttachmentGold(BaseModel):
    """The corrected label mapping plus the corrected Gold file digest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["corrected_attachment_gold_v1"] = "corrected_attachment_gold_v1"
    catalog_id: Annotated[str, Field(min_length=1)]
    source_catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    corrected_labels: tuple[CorrectedCandidateLabel, ...]
    resizes: tuple[TriggerContainmentResize, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            tuple(sorted(self.corrected_labels, key=lambda item: item.candidate_id))
            != self.corrected_labels
        ):
            raise ValueError("Corrected labels must use canonical candidate order.")
        if len({item.candidate_id for item in self.corrected_labels}) != len(self.corrected_labels):
            raise ValueError("Corrected labels repeat one candidate ID.")
        if tuple(sorted(self.resizes, key=lambda item: item.candidate_id)) != self.resizes:
            raise ValueError("Resizes must use canonical candidate order.")
        for resize in self.resizes:
            entry = next(
                item for item in self.corrected_labels if item.candidate_id == resize.candidate_id
            )
            if entry.gold_event_ids != resize.label_after:
                raise ValueError("Corrected label drifted from its resize.")
        return self


class CorrectionPartitionReport(BaseModel):
    """One partition's unchanged R1 decisions and before/after error census."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    decisions: tuple[AttachmentRouteDecision, ...]
    before_error_census: AttachmentRouteErrorCensus
    after_error_census: AttachmentRouteErrorCensus
    changed_candidate_ids: tuple[_CandidateId, ...]
    off_universe_candidate_ids: tuple[_CandidateId, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(sorted(self.decisions, key=lambda item: item.candidate_id)) != self.decisions:
            raise ValueError("Correction partition decisions must use canonical order.")
        if any(item.partition_role.value != self.partition_role for item in self.decisions):
            raise ValueError("Correction partition contains a foreign decision.")
        _ordered_distinct("changed candidate IDs", self.changed_candidate_ids)
        _ordered_distinct("off-universe candidate IDs", self.off_universe_candidate_ids)
        return self


class TriggerContainmentCorrectionReport(BaseModel):
    """Complete R2 correction report with zero model and canonical writes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["trigger_containment_correction_report_v1"] = (
        "trigger_containment_correction_report_v1"
    )
    partitions: tuple[CorrectionPartitionReport, CorrectionPartitionReport]
    changed_candidate_count: Annotated[int, Field(ge=0)]
    corrected_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    model_execution_count: Literal[0] = 0
    canonical_write_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.partition_role for item in self.partitions) != (
            "development",
            "validation",
        ):
            raise ValueError("Correction report requires development then validation.")
        changed = sum(len(item.changed_candidate_ids) for item in self.partitions)
        if self.changed_candidate_count != changed:
            raise ValueError("Correction changed-candidate count drifted from the partitions.")
        if self.result_fingerprint != trigger_containment_correction_report_fingerprint(self):
            raise ValueError("Correction report fingerprint drifted.")
        return self


def foreign_trigger_ranges(
    *,
    candidate_range: AttachmentSourceRange,
    triggers: tuple[tuple[AttachmentSourceRange, str], ...],
    gold_event_ids: tuple[str, ...],
) -> tuple[AttachmentSourceRange, ...]:
    """Return the foreign Event trigger ranges strictly contained in a candidate."""
    result: list[AttachmentSourceRange] = []
    for trigger_range, event_id in triggers:
        if event_id in gold_event_ids:
            continue
        if candidate_range.start < trigger_range.start and trigger_range.end < candidate_range.end:
            result.append(trigger_range)
    return tuple(sorted(result, key=lambda item: (item.start, item.end)))


def resize_candidate_range(
    *,
    candidate_range: AttachmentSourceRange,
    foreign_ranges: tuple[AttachmentSourceRange, ...],
    source_text: str,
) -> AttachmentSourceRange:
    """Return the longest-leftmost non-whitespace fragment that remains."""
    removed = _merge_intervals(tuple((item.start, item.end) for item in foreign_ranges))
    remaining: list[tuple[int, int]] = []
    cursor = candidate_range.start
    for start, end in removed:
        if cursor < start:
            remaining.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < candidate_range.end:
        remaining.append((cursor, candidate_range.end))
    fragments = [
        (start, end) for start, end in remaining if start < end and source_text[start:end].strip()
    ]
    if not fragments:
        raise ValueError("Trigger-containment resize leaves no non-whitespace fragment.")
    start, end = max(fragments, key=lambda item: (item[1] - item[0], -item[0]))
    return AttachmentSourceRange(start=start, end=end, text=source_text[start:end])


def exact_fragment_membership(
    source_range: AttachmentSourceRange,
    event_fragments: Mapping[str, tuple[tuple[int, int], ...]],
) -> tuple[str, ...]:
    """Return the ordered Event IDs whose fragment list contains the exact range."""
    target = (source_range.start, source_range.end)
    return tuple(
        sorted(
            event_id for event_id, fragments in event_fragments.items() if target in set(fragments)
        )
    )


def build_trigger_containment_resize(
    *,
    candidate_id: str,
    phase: Literal["development", "validation"],
    candidate_range: AttachmentSourceRange,
    foreign_ranges: tuple[AttachmentSourceRange, ...],
    resized_range: AttachmentSourceRange,
    label_before: tuple[str, ...],
    label_after: tuple[str, ...],
) -> TriggerContainmentResize:
    """Build one validated resize record."""
    return TriggerContainmentResize(
        candidate_id=candidate_id,
        phase=phase,
        candidate_range=candidate_range,
        foreign_trigger_ranges=foreign_ranges,
        resized_range=resized_range,
        label_before=label_before,
        label_after=label_after,
    )


def build_corrected_attachment_gold(
    *,
    catalog_id: str,
    source_catalog_sha256: str,
    corrected_labels: tuple[CorrectedCandidateLabel, ...],
    resizes: tuple[TriggerContainmentResize, ...],
) -> CorrectedAttachmentGold:
    """Assemble the corrected label mapping record."""
    return CorrectedAttachmentGold(
        catalog_id=catalog_id,
        source_catalog_sha256=source_catalog_sha256,
        corrected_labels=tuple(sorted(corrected_labels, key=lambda item: item.candidate_id)),
        resizes=tuple(sorted(resizes, key=lambda item: item.candidate_id)),
    )


def build_correction_partition_report(
    *,
    partition_role: Literal["development", "validation"],
    decisions: tuple[AttachmentRouteDecision, ...],
    before_attachment: Mapping[str, tuple[str, ...]],
    before_mixed: Mapping[str, bool],
    before_temporal: Mapping[str, bool],
    after_attachment: Mapping[str, tuple[str, ...]],
    after_mixed: Mapping[str, bool],
    after_temporal: Mapping[str, bool],
    off_universe_candidate_ids: tuple[str, ...] = (),
) -> CorrectionPartitionReport:
    """Assemble one partition's unchanged decisions and before/after census."""
    ordered = tuple(sorted(decisions, key=lambda item: item.candidate_id))
    changed: list[str] = []
    for decision in ordered:
        candidate_id = decision.candidate_id
        before = classify_error_class(
            gold_is_empty=not before_attachment.get(candidate_id, ()),
            gold_mixed=bool(before_mixed.get(candidate_id, False)),
            gold_temporal=bool(before_temporal.get(candidate_id, False)),
        )
        after = classify_error_class(
            gold_is_empty=not after_attachment.get(candidate_id, ()),
            gold_mixed=bool(after_mixed.get(candidate_id, False)),
            gold_temporal=bool(after_temporal.get(candidate_id, False)),
        )
        if before is not after:
            changed.append(candidate_id)
    return CorrectionPartitionReport(
        partition_role=partition_role,
        decisions=ordered,
        before_error_census=build_error_census(
            partition_role=partition_role,
            decisions=ordered,
            gold_attachment=before_attachment,
            gold_mixed=before_mixed,
            gold_temporal=before_temporal,
        ),
        after_error_census=build_error_census(
            partition_role=partition_role,
            decisions=ordered,
            gold_attachment=after_attachment,
            gold_mixed=after_mixed,
            gold_temporal=after_temporal,
        ),
        changed_candidate_ids=tuple(changed),
        off_universe_candidate_ids=tuple(sorted(off_universe_candidate_ids)),
    )


def build_trigger_containment_correction_report(
    *,
    development: CorrectionPartitionReport,
    validation: CorrectionPartitionReport,
    corrected_gold_sha256: str,
) -> TriggerContainmentCorrectionReport:
    """Assemble the complete R2 report and seal it with a semantic fingerprint."""
    if development.partition_role != "development":
        raise ValueError("Correction report development partition role drifted.")
    if validation.partition_role != "validation":
        raise ValueError("Correction report validation partition role drifted.")
    changed_candidate_count = sum(
        len(item.changed_candidate_ids) for item in (development, validation)
    )
    draft = TriggerContainmentCorrectionReport.model_construct(
        partitions=(development, validation),
        changed_candidate_count=changed_candidate_count,
        corrected_gold_sha256=corrected_gold_sha256,
        result_fingerprint="0" * 64,
    )
    return TriggerContainmentCorrectionReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=trigger_containment_correction_report_fingerprint(draft),
    )


def trigger_containment_correction_report_fingerprint(
    value: BaseModel | dict[str, object],
) -> str:
    """Return the semantic digest of an R2 correction report."""
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    else:
        payload = {key: item for key, item in value.items() if key != "result_fingerprint"}
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def corrected_attachment_gold_bytes(value: CorrectedAttachmentGold) -> bytes:
    """Serialize the corrected Gold content byte-identically."""
    return (
        json.dumps(
            value.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )


def canonical_json(value: object) -> bytes:
    """Return canonical JSON bytes for semantic fingerprints."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError(f"{label} must be ordered and distinct.")


def _merge_intervals(values: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    merged: list[list[int]] = []
    for start, end in sorted(values):
        if not merged or merged[-1][1] < start:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return tuple((start, end) for start, end in merged)
