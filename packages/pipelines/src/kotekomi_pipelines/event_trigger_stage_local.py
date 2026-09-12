"""Complete segment-level Gold evaluation for event trigger discovery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self, cast

from kotekomi_application import ExtractionStageTrace, HybridEventTriggerPreview
from kotekomi_application.context_planning import SourceCopyView, derive_source_copy_view
from kotekomi_application.source_occurrences import SourceOccurrence, source_occurrences
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.task_allocation_stage_local import StageLocalInput, StageLocalPhase

_SHA256 = r"^[a-f0-9]{64}$"
_OCCURRENCE_ID = r"^o[1-9][0-9]*$"


class TriggerGoldRange(BaseModel):
    """One accepted contiguous expression over deterministic SourceOccurrence IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start_occurrence_id: Annotated[str, Field(pattern=_OCCURRENCE_ID)]
    end_occurrence_id: Annotated[str, Field(pattern=_OCCURRENCE_ID)]


class TriggerGoldEvent(BaseModel):
    """One reviewed explicit Event in an authoritative SourceSegment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    meaning: Annotated[str, Field(min_length=1)]
    head_occurrence_id: Annotated[str, Field(pattern=_OCCURRENCE_ID)]
    accepted_expression_ranges: tuple[TriggerGoldRange, ...]

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if not self.accepted_expression_ranges:
            raise ValueError("Trigger Gold Event requires an accepted expression range.")
        values = tuple(
            (item.start_occurrence_id, item.end_occurrence_id)
            for item in self.accepted_expression_ranges
        )
        if len(set(values)) != len(values):
            raise ValueError("Trigger Gold Event repeats an accepted expression range.")
        return self


class TriggerGoldSegment(BaseModel):
    """Complete reviewed event inventory for one authoritative SourceSegment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: StageLocalPhase
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    event_free: bool
    events: tuple[TriggerGoldEvent, ...]

    @model_validator(mode="after")
    def validate_segment(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Trigger Gold SourceSegment digest does not match its text.")
        if self.event_free != (not self.events):
            raise ValueError("Trigger Gold event-free state does not match its Events.")
        if len({item.event_id for item in self.events}) != len(self.events):
            raise ValueError("Trigger Gold SourceSegment repeats an Event ID.")
        _validate_gold_occurrences(self)
        return self


class TriggerGoldCatalog(BaseModel):
    """Human-reviewed complete Event trigger oracle for the HSQ SourceSegments."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_event_trigger_gold_v1"] = "hsq_event_trigger_gold_v1"
    catalog_id: Annotated[str, Field(min_length=1)]
    review_status: Literal["proposed", "approved"]
    source_split_path: Annotated[str, Field(min_length=1)]
    source_split_sha256: Annotated[str, Field(pattern=_SHA256)]
    segments: tuple[TriggerGoldSegment, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        if len(self.segments) != 26:
            raise ValueError("Trigger Gold requires all twenty-six unique SourceSegments.")
        digests = tuple(item.source_text_sha256 for item in self.segments)
        if len(set(digests)) != len(digests):
            raise ValueError("Trigger Gold repeats a SourceSegment.")
        event_ids = tuple(event.event_id for segment in self.segments for event in segment.events)
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("Trigger Gold repeats an Event ID across SourceSegments.")
        return self


class TriggerStageSegmentEvaluation(BaseModel):
    """Exact expected-versus-observed trigger result for one SourceSegment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: StageLocalPhase
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    expected_event_count: Annotated[int, Field(ge=0)]
    actual_event_count: Annotated[int, Field(ge=0)]
    exact_head_matched_event_ids: tuple[str, ...]
    exact_expression_matched_event_ids: tuple[str, ...]
    matched_event_ids: tuple[str, ...]
    missing_event_ids: tuple[str, ...]
    extra_trigger_ids: tuple[str, ...]
    duplicate_trigger_ids: tuple[str, ...]
    bounded_semantic_judgment_count: Annotated[int, Field(ge=0)]
    failed_model_judgment_count: Annotated[int, Field(ge=0)]
    source_occurrence_count: Annotated[int, Field(ge=0)]
    event_head_candidate_count: Annotated[int, Field(ge=0)]
    classified_candidate_count: Annotated[int, Field(ge=0)]
    unclassified_candidate_ids: tuple[str, ...]
    gold_candidate_miss_event_ids: tuple[str, ...]
    complete_candidate_dispositions: bool
    exact_source_mapping: bool
    passed: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        for label, values in (
            ("exact-head matched Event IDs", self.exact_head_matched_event_ids),
            ("exact-expression matched Event IDs", self.exact_expression_matched_event_ids),
            ("matched Event IDs", self.matched_event_ids),
            ("missing Event IDs", self.missing_event_ids),
            ("extra trigger IDs", self.extra_trigger_ids),
            ("duplicate trigger IDs", self.duplicate_trigger_ids),
            ("Gold candidate-miss Event IDs", self.gold_candidate_miss_event_ids),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"Trigger stage {label} must be ordered and distinct.")
        expected_ids = set(self.matched_event_ids) | set(self.missing_event_ids)
        if self.expected_event_count != len(expected_ids):
            raise ValueError("Trigger stage expected count drifted from its Gold Event IDs.")
        if self.actual_event_count != (
            len(self.matched_event_ids)
            + len(self.extra_trigger_ids)
            + len(self.duplicate_trigger_ids)
        ):
            raise ValueError("Trigger stage actual count drifted from classified triggers.")
        if len(set(self.unclassified_candidate_ids)) != len(self.unclassified_candidate_ids):
            raise ValueError("Trigger stage repeats an unclassified EventHeadCandidate.")
        if self.event_head_candidate_count != (
            self.classified_candidate_count + len(self.unclassified_candidate_ids)
        ):
            raise ValueError("Trigger stage EventHeadCandidate coverage is inconsistent.")
        if self.bounded_semantic_judgment_count < self.event_head_candidate_count:
            raise ValueError("Each EventHeadCandidate requires at least one bounded judgment.")
        if not set(self.gold_candidate_miss_event_ids) <= expected_ids:
            raise ValueError("Trigger stage candidate miss references an unknown Gold Event.")
        if not (
            set(self.exact_head_matched_event_ids) <= expected_ids
            and set(self.exact_expression_matched_event_ids) <= expected_ids
        ):
            raise ValueError("Trigger stage partial matches reference an unknown Gold Event.")
        expected_pass = (
            not (
                self.missing_event_ids
                or self.extra_trigger_ids
                or self.duplicate_trigger_ids
                or self.failed_model_judgment_count
                or self.unclassified_candidate_ids
                or self.gold_candidate_miss_event_ids
            )
            and self.exact_source_mapping
            and self.complete_candidate_dispositions
        )
        if self.passed != expected_pass:
            raise ValueError("Trigger stage pass state does not match its evidence.")
        return self


class TriggerStageReport(BaseModel):
    """Complete phase result for the SourceOccurrence to event trigger boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_event_trigger_stage_report_v7"] = (
        "hsq_event_trigger_stage_report_v7"
    )
    phase: StageLocalPhase
    segment_count: Annotated[int, Field(ge=0)]
    passed_segment_count: Annotated[int, Field(ge=0)]
    expected_event_count: Annotated[int, Field(ge=0)]
    actual_event_count: Annotated[int, Field(ge=0)]
    exact_head_match_count: Annotated[int, Field(ge=0)]
    exact_expression_match_count: Annotated[int, Field(ge=0)]
    missing_event_count: Annotated[int, Field(ge=0)]
    extra_trigger_count: Annotated[int, Field(ge=0)]
    duplicate_trigger_count: Annotated[int, Field(ge=0)]
    bounded_semantic_judgment_count: Annotated[int, Field(ge=0)]
    failed_model_judgment_count: Annotated[int, Field(ge=0)]
    source_occurrence_count: Annotated[int, Field(ge=0)]
    event_head_candidate_count: Annotated[int, Field(ge=0)]
    classified_candidate_count: Annotated[int, Field(ge=0)]
    unclassified_candidate_count: Annotated[int, Field(ge=0)]
    gold_candidate_miss_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    model_elapsed_milliseconds: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    passed: bool
    segments: tuple[TriggerStageSegmentEvaluation, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        totals = {
            "segment_count": len(self.segments),
            "passed_segment_count": sum(item.passed for item in self.segments),
            "expected_event_count": sum(item.expected_event_count for item in self.segments),
            "actual_event_count": sum(item.actual_event_count for item in self.segments),
            "exact_head_match_count": sum(
                len(item.exact_head_matched_event_ids) for item in self.segments
            ),
            "exact_expression_match_count": sum(
                len(item.exact_expression_matched_event_ids) for item in self.segments
            ),
            "missing_event_count": sum(len(item.missing_event_ids) for item in self.segments),
            "extra_trigger_count": sum(len(item.extra_trigger_ids) for item in self.segments),
            "duplicate_trigger_count": sum(
                len(item.duplicate_trigger_ids) for item in self.segments
            ),
            "bounded_semantic_judgment_count": sum(
                item.bounded_semantic_judgment_count for item in self.segments
            ),
            "failed_model_judgment_count": sum(
                item.failed_model_judgment_count for item in self.segments
            ),
            "source_occurrence_count": sum(item.source_occurrence_count for item in self.segments),
            "event_head_candidate_count": sum(
                item.event_head_candidate_count for item in self.segments
            ),
            "classified_candidate_count": sum(
                item.classified_candidate_count for item in self.segments
            ),
            "unclassified_candidate_count": sum(
                len(item.unclassified_candidate_ids) for item in self.segments
            ),
            "gold_candidate_miss_count": sum(
                len(item.gold_candidate_miss_event_ids) for item in self.segments
            ),
        }
        for field_name, expected in totals.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"Trigger stage {field_name} drifted from its segments.")
        if self.model_execution_count != self.bounded_semantic_judgment_count:
            raise ValueError(
                "Trigger stage model execution count does not match its bounded judgments."
            )
        if self.passed != (self.passed_segment_count == self.segment_count):
            raise ValueError("Trigger stage report pass state drifted from its segments.")
        return self


def load_trigger_gold_catalog(
    path: Path,
    *,
    repository_root: Path,
    inputs: tuple[StageLocalInput, ...],
    require_approved: bool,
) -> TriggerGoldCatalog:
    """Validate Trigger Gold against its pinned split and authoritative SourceSegments."""
    catalog = TriggerGoldCatalog.model_validate_json(path.read_bytes())
    split_path = repository_root / catalog.source_split_path
    if hashlib.sha256(split_path.read_bytes()).hexdigest() != catalog.source_split_sha256:
        raise ValueError("Trigger Gold source split digest drifted.")
    if require_approved and catalog.review_status != "approved":
        raise ValueError("Trigger Gold requires human approval before validation.")
    expected = {item.source_text_sha256: (item.phase, item.source_text) for item in inputs}
    observed = {
        item.source_text_sha256: (item.phase, item.source_text) for item in catalog.segments
    }
    if observed != expected:
        raise ValueError("Trigger Gold does not cover the pinned SourceSegments exactly.")
    return catalog


def evaluate_trigger_segment(
    gold: TriggerGoldSegment,
    preview: HybridEventTriggerPreview,
) -> TriggerStageSegmentEvaluation:
    """Match exact EventTriggerDraft ranges to complete segment-level Gold."""
    source_copy = derive_source_copy_view(gold.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    expected = {
        item.event_id: (
            _authoritative_span(source_copy, occurrences[item.head_occurrence_id]),
            {
                _range_span(source_copy, occurrences, expression)
                for expression in item.accepted_expression_ranges
            },
        )
        for item in gold.events
    }
    source_segment_ids = {
        item.source_segment_id
        for item in preview.triggers
        if item.source_text_sha256 == gold.source_text_sha256
    }
    triggers = tuple(
        item for item in preview.triggers if item.source_text_sha256 == gold.source_text_sha256
    )
    matched: dict[str, str] = {}
    extras: list[str] = []
    duplicates: list[str] = []
    for trigger in triggers:
        candidates = tuple(
            event_id
            for event_id, (head_span, expression_spans) in expected.items()
            if (trigger.head_start, trigger.head_end) == head_span
            and (trigger.start, trigger.end) in expression_spans
        )
        if len(candidates) != 1:
            extras.append(trigger.id)
            continue
        event_id = candidates[0]
        if event_id in matched:
            duplicates.append(trigger.id)
        else:
            matched[event_id] = trigger.id
    missing = tuple(sorted(set(expected) - set(matched)))
    exact_head_matched = tuple(
        sorted(
            event_id
            for event_id, (head_span, _) in expected.items()
            if any((item.head_start, item.head_end) == head_span for item in triggers)
        )
    )
    exact_expression_matched = tuple(
        sorted(
            event_id
            for event_id, (_, expression_spans) in expected.items()
            if any((item.start, item.end) in expression_spans for item in triggers)
        )
    )
    exact_mapping = len(source_segment_ids) <= 1 and all(
        item.end <= len(gold.source_text)
        and gold.source_text[item.start : item.end] == item.text
        and gold.source_text[item.head_start : item.head_end] == item.head_text
        for item in triggers
    )
    reconciliation_traces = tuple(
        item
        for item in preview.traces
        if item.stage_id == "event_trigger_reconciliation"
        and item.source_text_sha256 == gold.source_text_sha256
    )
    candidate_traces = tuple(
        item
        for item in preview.traces
        if item.stage_id == "event_head_candidate_selection"
        and item.source_text_sha256 == gold.source_text_sha256
    )
    candidate_ids, complete_candidate_dispositions = _candidate_selection_evidence(
        candidate_traces,
        occurrences=occurrences,
    )
    judgment_traces = tuple(
        item
        for item in preview.traces
        if item.stage_id.startswith("event_")
        and item.stage_id not in {"event_head_candidate_selection", "event_trigger_reconciliation"}
        and item.source_text_sha256 == gold.source_text_sha256
        and item.execution_record_ids
    )
    gold_candidate_misses = tuple(
        sorted(
            event_id
            for event_id, event in ((item.event_id, item) for item in gold.events)
            if event.head_occurrence_id not in candidate_ids
        )
    )
    failed_model_judgments = sum(item.status.value != "completed" for item in judgment_traces)
    if len(reconciliation_traces) != 1:
        unclassified_candidate_ids = tuple(candidate_ids)
    else:
        unclassified_candidate_ids = _unclassified_occurrence_ids(
            reconciliation_traces[0],
            occurrences={item: occurrences[item] for item in candidate_ids},
        )
    classified_candidate_count = len(candidate_ids) - len(unclassified_candidate_ids)
    return TriggerStageSegmentEvaluation(
        phase=gold.phase,
        source_text_sha256=gold.source_text_sha256,
        expected_event_count=len(expected),
        actual_event_count=len(triggers),
        exact_head_matched_event_ids=exact_head_matched,
        exact_expression_matched_event_ids=exact_expression_matched,
        matched_event_ids=tuple(sorted(matched)),
        missing_event_ids=missing,
        extra_trigger_ids=tuple(sorted(extras)),
        duplicate_trigger_ids=tuple(sorted(duplicates)),
        bounded_semantic_judgment_count=len(judgment_traces),
        failed_model_judgment_count=failed_model_judgments,
        source_occurrence_count=len(occurrences),
        event_head_candidate_count=len(candidate_ids),
        classified_candidate_count=classified_candidate_count,
        unclassified_candidate_ids=unclassified_candidate_ids,
        gold_candidate_miss_event_ids=gold_candidate_misses,
        complete_candidate_dispositions=complete_candidate_dispositions,
        exact_source_mapping=exact_mapping,
        passed=not (
            missing
            or extras
            or duplicates
            or failed_model_judgments
            or unclassified_candidate_ids
            or gold_candidate_misses
        )
        and exact_mapping
        and complete_candidate_dispositions,
    )


def build_trigger_stage_report(
    *,
    phase: StageLocalPhase,
    evaluations: tuple[TriggerStageSegmentEvaluation, ...],
    model_execution_count: int,
    model_elapsed_milliseconds: int,
) -> TriggerStageReport:
    ordered = tuple(sorted(evaluations, key=lambda item: item.source_text_sha256))
    return TriggerStageReport(
        phase=phase,
        segment_count=len(ordered),
        passed_segment_count=sum(item.passed for item in ordered),
        expected_event_count=sum(item.expected_event_count for item in ordered),
        actual_event_count=sum(item.actual_event_count for item in ordered),
        exact_head_match_count=sum(len(item.exact_head_matched_event_ids) for item in ordered),
        exact_expression_match_count=sum(
            len(item.exact_expression_matched_event_ids) for item in ordered
        ),
        missing_event_count=sum(len(item.missing_event_ids) for item in ordered),
        extra_trigger_count=sum(len(item.extra_trigger_ids) for item in ordered),
        duplicate_trigger_count=sum(len(item.duplicate_trigger_ids) for item in ordered),
        bounded_semantic_judgment_count=sum(
            item.bounded_semantic_judgment_count for item in ordered
        ),
        failed_model_judgment_count=sum(item.failed_model_judgment_count for item in ordered),
        source_occurrence_count=sum(item.source_occurrence_count for item in ordered),
        event_head_candidate_count=sum(item.event_head_candidate_count for item in ordered),
        classified_candidate_count=sum(item.classified_candidate_count for item in ordered),
        unclassified_candidate_count=sum(len(item.unclassified_candidate_ids) for item in ordered),
        gold_candidate_miss_count=sum(len(item.gold_candidate_miss_event_ids) for item in ordered),
        model_execution_count=model_execution_count,
        model_elapsed_milliseconds=model_elapsed_milliseconds,
        passed=all(item.passed for item in ordered),
        segments=ordered,
    )


def render_trigger_gold_review(catalog: TriggerGoldCatalog) -> str:
    """Render exact source-owned Trigger Gold for human semantic review."""
    lines = [
        "# HSQ SourceOccurrence to Event Trigger Gold Review",
        "",
        f"Catalog: `{catalog.catalog_id}`",
        "",
        f"Current review status: `{catalog.review_status}`",
        "",
        "Approve only when each segment contains every explicit Event and no invented Event.",
        "",
        "Diagnostic meanings explain the annotation but are not scored as ontology labels.",
        "",
    ]
    for ordinal, segment in enumerate(catalog.segments, start=1):
        source_copy = derive_source_copy_view(segment.source_text)
        occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
        lines.extend(
            (
                f"## {ordinal:02d} — {segment.phase} — {segment.source_text_sha256[:12]}",
                "",
                "Exact SourceSegment:",
                "",
                "```text",
                segment.source_text,
                "```",
                "",
            )
        )
        lines.extend(("Proposed complete Event inventory:", ""))
        if segment.event_free:
            lines.extend(("- No explicit Event.", ""))
        for event in segment.events:
            head = occurrences[event.head_occurrence_id]
            head_start, head_end = source_copy.authoritative_range(head.start, head.end)
            lines.extend(
                (
                    f"### {event.event_id}",
                    "",
                    f"Diagnostic meaning: {event.meaning}",
                    "",
                    "Exact head: "
                    f"{json.dumps(head.text, ensure_ascii=False)} "
                    f"(`{head.occurrence_id}`, authoritative `[{head_start},{head_end})`)",
                    "",
                    "Accepted exact expressions:",
                    "",
                )
            )
            for expression in event.accepted_expression_ranges:
                start = occurrences[expression.start_occurrence_id]
                end = occurrences[expression.end_occurrence_id]
                authoritative_start, authoritative_end = source_copy.authoritative_range(
                    start.start,
                    end.end,
                )
                exact = segment.source_text[authoritative_start:authoritative_end]
                lines.append(
                    f"- {json.dumps(exact, ensure_ascii=False)} "
                    f"(`{start.occurrence_id}`–`{end.occurrence_id}`, "
                    f"authoritative `[{authoritative_start},{authoritative_end})`)"
                )
            lines.extend(("", f"Event review: `{catalog.review_status}`", ""))
        lines.extend((f"Segment review: `{catalog.review_status}`", ""))
    return "\n".join(lines)


def _validate_gold_occurrences(segment: TriggerGoldSegment) -> None:
    source_copy = derive_source_copy_view(segment.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    ordinals = {item: ordinal for ordinal, item in enumerate(occurrences)}
    signatures: set[tuple[str, str, str]] = set()
    for event in segment.events:
        if event.head_occurrence_id not in occurrences:
            raise ValueError("Trigger Gold head references an unknown SourceOccurrence.")
        for expression in event.accepted_expression_ranges:
            if (
                expression.start_occurrence_id not in occurrences
                or expression.end_occurrence_id not in occurrences
            ):
                raise ValueError("Trigger Gold expression references an unknown SourceOccurrence.")
            start = ordinals[expression.start_occurrence_id]
            end = ordinals[expression.end_occurrence_id]
            head = ordinals[event.head_occurrence_id]
            if start > end or not start <= head <= end:
                raise ValueError("Trigger Gold expression does not contain its head.")
            signature = (
                event.head_occurrence_id,
                expression.start_occurrence_id,
                expression.end_occurrence_id,
            )
            if signature in signatures:
                raise ValueError("Trigger Gold Events share an indistinguishable exact span.")
            signatures.add(signature)


def _authoritative_span(
    source_copy: SourceCopyView,
    occurrence: SourceOccurrence,
) -> tuple[int, int]:
    return source_copy.authoritative_range(occurrence.start, occurrence.end)


def _range_span(
    source_copy: SourceCopyView,
    occurrences: dict[str, SourceOccurrence],
    expression: TriggerGoldRange,
) -> tuple[int, int]:
    return source_copy.authoritative_range(
        occurrences[expression.start_occurrence_id].start,
        occurrences[expression.end_occurrence_id].end,
    )


def _candidate_selection_evidence(
    traces: tuple[ExtractionStageTrace, ...],
    *,
    occurrences: dict[str, SourceOccurrence],
) -> tuple[tuple[str, ...], bool]:
    if len(traces) != 1:
        return (), False
    trace = traces[0]
    raw_candidates = trace.output.get("candidates")
    raw_dispositions = trace.output.get("dispositions")
    if not isinstance(raw_candidates, list) or not isinstance(raw_dispositions, list):
        raise ValueError("Event-head candidate trace lacks typed output collections.")
    candidate_ids: list[str] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            raise ValueError("Event-head candidate trace contains an invalid candidate.")
        candidate = cast(dict[str, object], raw)
        occurrence_id = candidate.get("occurrence_id")
        if not isinstance(occurrence_id, str) or occurrence_id not in occurrences:
            raise ValueError("Event-head candidate references an unknown SourceOccurrence.")
        occurrence = occurrences[occurrence_id]
        if (
            candidate.get("text") != occurrence.text
            or candidate.get("start") != occurrence.start
            or candidate.get("end") != occurrence.end
        ):
            raise ValueError("Event-head candidate does not match exact source characters.")
        candidate_ids.append(occurrence_id)
    expected_order = {item: int(item.removeprefix("o")) for item in occurrences}
    if candidate_ids != sorted(set(candidate_ids), key=lambda item: expected_order[item]):
        raise ValueError("Event-head candidates must be ordered and distinct.")

    disposition_ids: list[str] = []
    included_ids: list[str] = []
    for raw in raw_dispositions:
        if not isinstance(raw, dict):
            raise ValueError("Candidate trace contains an invalid disposition.")
        disposition = cast(dict[str, object], raw)
        occurrence_id = disposition.get("occurrence_id")
        value = disposition.get("disposition")
        if not isinstance(occurrence_id, str) or occurrence_id not in occurrences:
            raise ValueError("Candidate disposition references an unknown SourceOccurrence.")
        if value not in {"included", "excluded", "unmapped"}:
            raise ValueError("Candidate disposition has an unsupported outcome.")
        disposition_ids.append(occurrence_id)
        if value == "included":
            included_ids.append(occurrence_id)
    complete = disposition_ids == list(occurrences) and included_ids == candidate_ids
    return tuple(candidate_ids), complete


def _unclassified_occurrence_ids(
    trace: ExtractionStageTrace,
    *,
    occurrences: dict[str, SourceOccurrence],
) -> tuple[str, ...]:
    raw = trace.output.get("unclassified_occurrence_ids")
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError("Trigger reconciliation trace lacks typed unclassified occurrences.")
    values = cast(list[str], raw)
    if len(set(values)) != len(values) or any(item not in occurrences for item in values):
        raise ValueError("Trigger reconciliation trace has invalid unclassified occurrences.")
    ordinals = {
        occurrence_id: int(occurrence_id.removeprefix("o")) for occurrence_id in occurrences
    }
    ordered = tuple(sorted(values, key=lambda item: ordinals[item]))
    if tuple(values) != ordered:
        raise ValueError("Trigger reconciliation unclassified occurrences are not in source order.")
    return ordered
