"""Trigger-containment candidate split and Gold correction for the R2 deliverable.

This Pipeline composes the model-free Application Layer splitter against the
frozen Proposition Gold fragments and the frozen trigger Gold.  It builds the
187-candidate universe from exact fragment ranges, materializes each Event
trigger to authoritative source characters, and produces one corrected
Attachment Gold plus one Markdown review.  It never executes a model and never
changes canonical state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from kotekomi_application import (
    AttachmentSourceRange,
    CorrectedAttachmentGold,
    CorrectedCandidateLabel,
    TriggerContainmentCorrectionReport,
    TriggerContainmentResize,
    build_corrected_attachment_gold,
    build_trigger_containment_resize,
    exact_fragment_membership,
    foreign_trigger_ranges,
    resize_candidate_range,
)
from kotekomi_application.context_planning import derive_source_copy_view
from kotekomi_application.source_occurrences import source_occurrences

from kotekomi_pipelines.event_trigger_stage_local import TriggerGoldCatalog
from kotekomi_pipelines.source_grounded_proposition_stage_local import PropositionGoldCatalog

CORRECTED_CATALOG_ID = "hsq-source-grounded-proposition-gold-v1-corrected"


@dataclass(frozen=True)
class CandidateUniverseEntry:
    """One distinct fragment range plus its derived Gold Attachment Set."""

    candidate_id: str
    phase: Literal["development", "validation"]
    source_text_sha256: str
    source_range: AttachmentSourceRange
    gold_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class EventTriggerRange:
    """One Event trigger materialized to authoritative source characters."""

    source_text_sha256: str
    source_range: AttachmentSourceRange
    event_id: str


def trigger_containment_candidate_id(source_text_sha256: str, start: int, end: int) -> str:
    """Return one deterministic candidate ID for an exact fragment range."""
    value = f"{source_text_sha256}:{start}:{end}".encode()
    return "cac_" + hashlib.sha256(value).hexdigest()[:24]


def source_by_digest(catalog: PropositionGoldCatalog) -> dict[str, str]:
    """Return one authoritative source text per frozen digest."""
    result: dict[str, str] = {}
    for event in catalog.events:
        if event.source_text_sha256 in result:
            if result[event.source_text_sha256] != event.source_text:
                raise ValueError("Proposition Gold repeats a digest with different text.")
        else:
            result[event.source_text_sha256] = event.source_text
    return result


def build_candidate_universe(
    catalog: PropositionGoldCatalog,
) -> tuple[CandidateUniverseEntry, ...]:
    """Derive the 187-candidate universe from exact fragment ranges only."""
    grouped: dict[tuple[str, int, int], list[tuple[str, Literal["development", "validation"]]]] = {}
    for event in catalog.events:
        for fragment in event.fragments:
            key = (event.source_text_sha256, fragment.start, fragment.end)
            grouped.setdefault(key, []).append((event.event_id, event.phase))
    entries: list[CandidateUniverseEntry] = []
    for (sha, start, end), pairs in sorted(grouped.items()):
        phases: set[Literal["development", "validation"]] = {phase for _, phase in pairs}
        if len(phases) != 1:
            raise ValueError("One fragment range spans multiple phases.")
        gold_event_ids = tuple(sorted({event_id for event_id, _ in pairs}))
        source_text = next(
            event.source_text for event in catalog.events if event.source_text_sha256 == sha
        )
        entries.append(
            CandidateUniverseEntry(
                candidate_id=trigger_containment_candidate_id(sha, start, end),
                phase=next(iter(phases)),
                source_text_sha256=sha,
                source_range=AttachmentSourceRange(
                    start=start, end=end, text=source_text[start:end]
                ),
                gold_event_ids=gold_event_ids,
            )
        )
    return tuple(sorted(entries, key=lambda item: item.candidate_id))


def materialize_event_triggers(
    trigger_gold: TriggerGoldCatalog,
) -> tuple[EventTriggerRange, ...]:
    """Materialize every Event trigger to authoritative source characters."""
    result: list[EventTriggerRange] = []
    for segment in trigger_gold.segments:
        source_copy = derive_source_copy_view(segment.source_text)
        occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
        for event in segment.events:
            for expression in event.accepted_expression_ranges:
                raw_start, raw_end = source_copy.authoritative_range(
                    occurrences[expression.start_occurrence_id].start,
                    occurrences[expression.end_occurrence_id].end,
                )
                result.append(
                    EventTriggerRange(
                        source_text_sha256=segment.source_text_sha256,
                        source_range=AttachmentSourceRange(
                            start=raw_start,
                            end=raw_end,
                            text=segment.source_text[raw_start:raw_end],
                        ),
                        event_id=event.event_id,
                    )
                )
    return tuple(result)


def correct_attachment_gold(
    *,
    catalog: PropositionGoldCatalog,
    trigger_gold: TriggerGoldCatalog,
    source_catalog_sha256: str,
) -> CorrectedAttachmentGold:
    """Split every trigger-containment candidate and re-label by exact membership."""
    sources = source_by_digest(catalog)
    event_fragments: dict[str, dict[str, tuple[tuple[int, int], ...]]] = {}
    for event in catalog.events:
        event_fragments.setdefault(event.source_text_sha256, {})[event.event_id] = tuple(
            (item.start, item.end) for item in event.fragments
        )
    universe = build_candidate_universe(catalog)
    if len(universe) != 187:
        raise ValueError("R2 candidate universe drifted from the 187 fragment ranges.")
    triggers = materialize_event_triggers(trigger_gold)
    by_source: dict[str, list[tuple[AttachmentSourceRange, str]]] = {}
    for trigger in triggers:
        by_source.setdefault(trigger.source_text_sha256, []).append(
            (trigger.source_range, trigger.event_id)
        )

    labels: list[CorrectedCandidateLabel] = []
    resizes: list[TriggerContainmentResize] = []
    for entry in universe:
        source_text = sources[entry.source_text_sha256]
        foreign = foreign_trigger_ranges(
            candidate_range=entry.source_range,
            triggers=tuple(by_source.get(entry.source_text_sha256, ())),
            gold_event_ids=entry.gold_event_ids,
        )
        if not foreign:
            labels.append(
                CorrectedCandidateLabel(
                    candidate_id=entry.candidate_id,
                    phase=entry.phase,
                    source_range=entry.source_range,
                    gold_event_ids=entry.gold_event_ids,
                )
            )
            continue
        resized = resize_candidate_range(
            candidate_range=entry.source_range,
            foreign_ranges=foreign,
            source_text=source_text,
        )
        label_after = exact_fragment_membership(resized, event_fragments[entry.source_text_sha256])
        resizes.append(
            build_trigger_containment_resize(
                candidate_id=entry.candidate_id,
                phase=entry.phase,
                candidate_range=entry.source_range,
                foreign_ranges=foreign,
                resized_range=resized,
                label_before=entry.gold_event_ids,
                label_after=label_after,
            )
        )
        labels.append(
            CorrectedCandidateLabel(
                candidate_id=entry.candidate_id,
                phase=entry.phase,
                source_range=resized,
                gold_event_ids=label_after,
            )
        )
    return build_corrected_attachment_gold(
        catalog_id=CORRECTED_CATALOG_ID,
        source_catalog_sha256=source_catalog_sha256,
        corrected_labels=tuple(labels),
        resizes=tuple(resizes),
    )


def corrected_gold_file_bytes(
    *,
    catalog: PropositionGoldCatalog,
    corrected: CorrectedAttachmentGold,
) -> bytes:
    """Serialize the corrected Gold file preserving every Event unchanged."""
    payload: dict[str, Any] = {
        "schema_version": corrected.schema_version,
        "catalog_id": corrected.catalog_id,
        "source_catalog_sha256": corrected.source_catalog_sha256,
        "events": [event.model_dump(mode="json") for event in catalog.events],
        "corrected_labels": [item.model_dump(mode="json") for item in corrected.corrected_labels],
        "resizes": [item.model_dump(mode="json") for item in corrected.resizes],
    }
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )


def render_trigger_containment_correction_review(
    *,
    corrected: CorrectedAttachmentGold,
    report: TriggerContainmentCorrectionReport,
) -> str:
    """Render one Markdown review of the corrected Gold and error-class re-score."""
    development, validation = report.partitions
    lines = [
        "# R2 Trigger-Containment Candidate Split and Gold Correction",
        "",
        f"Corrected Gold file: `docs/{corrected.catalog_id}.json`",
        f"Corrected Gold SHA-256: `{report.corrected_gold_sha256}`",
        "",
        f"Changed candidates: `{report.changed_candidate_count}`",
        "Model executions: `0`",
        "Canonical writes: `0`",
        "",
        "## Error-class re-score",
        "",
        "### development",
        "",
        f"- `none` `{development.before_error_census.none_count}` -> "
        f"`{development.after_error_census.none_count}`",
        f"- `mixed` `{development.before_error_census.mixed_count}` -> "
        f"`{development.after_error_census.mixed_count}`",
        f"- `temporal` `{development.before_error_census.temporal_count}` -> "
        f"`{development.after_error_census.temporal_count}`",
        "",
        "### validation",
        "",
        f"- `none` `{validation.before_error_census.none_count}` -> "
        f"`{validation.after_error_census.none_count}`",
        f"- `mixed` `{validation.before_error_census.mixed_count}` -> "
        f"`{validation.after_error_census.mixed_count}`",
        f"- `temporal` `{validation.before_error_census.temporal_count}` -> "
        f"`{validation.after_error_census.temporal_count}`",
        "",
        "## Off-universe candidates (carried, not re-scored)",
        "",
        f"- development: `{len(development.off_universe_candidate_ids)}`",
        f"- validation: `{len(validation.off_universe_candidate_ids)}`",
        "",
        "## Changed candidates",
        "",
    ]
    changed = (*development.changed_candidate_ids, *validation.changed_candidate_ids)
    if changed:
        for candidate_id in changed:
            lines.append(f"- `{candidate_id}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Resized candidates",
            "",
        ]
    )
    if corrected.resizes:
        for resize in corrected.resizes:
            label_before = "none" if not resize.label_before else ",".join(resize.label_before)
            label_after = "none" if not resize.label_after else ",".join(resize.label_after)
            lines.append(
                f"- `{resize.candidate_id}` `{resize.candidate_range.text}` -> "
                f"`{resize.resized_range.text}`; "
                f"label `{label_before}` -> `{label_after}`"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)
