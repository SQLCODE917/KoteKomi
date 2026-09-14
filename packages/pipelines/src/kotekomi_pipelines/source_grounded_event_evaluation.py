"""Pure Gold evaluation for the source-grounded Event boundary."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal, Self

from kotekomi_application import (
    SourceGroundedEventDraft,
    build_source_grounded_event,
    derive_source_copy_view,
    validate_source_grounded_event,
)
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_domain import EvidenceTarget
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.evaluation_contracts import EvaluationPhase
from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    TriggerGoldEvent,
    TriggerGoldSegment,
)

_SHA256 = r"^[a-f0-9]{64}$"


class SourceGroundedEventGoldItem(BaseModel):
    """One human review outcome over a Trigger Gold Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    phase: EvaluationPhase
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    expected_review_outcome: Literal["approved", "rejected"]
    rationale: Annotated[str, Field(min_length=1)]


class SourceGroundedEventGoldCatalog(BaseModel):
    """Reviewed source-grounded Event outcomes pinned to Trigger Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_source_grounded_event_gold_v1"] = (
        "hsq_source_grounded_event_gold_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    review_status: Literal["proposed", "approved"]
    trigger_gold_path: Annotated[str, Field(min_length=1)]
    trigger_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    items: tuple[SourceGroundedEventGoldItem, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        event_ids = tuple(item.event_id for item in self.items)
        if tuple(sorted(set(event_ids))) != event_ids:
            raise ValueError("Source-Grounded Event Gold IDs must be ordered and distinct.")
        return self


class NormalizedSourceExpression(BaseModel):
    """One exact expression in authoritative SourceSegment coordinates."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Normalized source expression range does not match its text.")
        return self


class NormalizedExpectedEvent(BaseModel):
    """Human-reviewed Event expectation resolved from occurrence IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    diagnostic_meaning: Annotated[str, Field(min_length=1)]
    head: NormalizedSourceExpression
    accepted_expressions: tuple[NormalizedSourceExpression, ...]


class NormalizedActualEvent(BaseModel):
    """Runtime source-grounded Event expressed in the same coordinates as Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_grounded_event_id: Annotated[str, Field(min_length=1)]
    event_subject_id: Annotated[str, Field(min_length=1)]
    trigger_id: Annotated[str, Field(min_length=1)]
    head: NormalizedSourceExpression
    expression: NormalizedSourceExpression
    head_evidence_target_id: Annotated[str, Field(min_length=1)]
    expression_evidence_target_id: Annotated[str, Field(min_length=1)]
    support_evidence_target_id: Annotated[str, Field(min_length=1)]


class NormalizedEventComparison(BaseModel):
    """Readable, one-to-one expected-versus-actual Event evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["exact", "missing", "extra", "incorrectly_grounded"]
    expected: NormalizedExpectedEvent | None
    actual: NormalizedActualEvent | None

    @model_validator(mode="after")
    def validate_sides(self) -> Self:
        if self.status == "missing" and (self.expected is None or self.actual is not None):
            raise ValueError("A missing Event requires only an expected side.")
        if self.status == "extra" and (self.expected is not None or self.actual is None):
            raise ValueError("An extra Event requires only an actual side.")
        if self.status in {"exact", "incorrectly_grounded"} and (
            self.expected is None or self.actual is None
        ):
            raise ValueError("A compared Event requires expected and actual sides.")
        return self


class SourceGroundedEventSegmentEvaluation(BaseModel):
    """Exact grounding comparison for one authoritative SourceSegment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: EvaluationPhase
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_segment_observation_count: Annotated[int, Field(ge=0)]
    expected_event_count: Annotated[int, Field(ge=0)]
    observed_event_count: Annotated[int, Field(ge=0)]
    grounded_event_ids: tuple[str, ...]
    missing_event_ids: tuple[str, ...]
    extra_source_grounded_event_ids: tuple[str, ...]
    incorrectly_grounded_event_ids: tuple[str, ...]
    approved_review_event_ids: tuple[str, ...]
    rejected_review_event_ids: tuple[str, ...]
    comparisons: tuple[NormalizedEventComparison, ...]
    passed: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        for label, values in (
            ("grounded Event IDs", self.grounded_event_ids),
            ("missing Event IDs", self.missing_event_ids),
            ("extra source-grounded Event IDs", self.extra_source_grounded_event_ids),
            ("incorrectly grounded Event IDs", self.incorrectly_grounded_event_ids),
            ("approved review Event IDs", self.approved_review_event_ids),
            ("rejected review Event IDs", self.rejected_review_event_ids),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{label} must be ordered and distinct.")
        expected_ids = (
            set(self.grounded_event_ids)
            | set(self.missing_event_ids)
            | set(self.incorrectly_grounded_event_ids)
        )
        if self.expected_event_count != len(expected_ids):
            raise ValueError("Source-grounded expected count does not match its Event IDs.")
        if self.observed_event_count != (
            len(self.grounded_event_ids)
            + len(self.incorrectly_grounded_event_ids)
            + len(self.extra_source_grounded_event_ids)
        ):
            raise ValueError("Source-grounded observed count does not match its Event IDs.")
        comparison_statuses = tuple(item.status for item in self.comparisons)
        if comparison_statuses.count("exact") != len(self.grounded_event_ids):
            raise ValueError("Exact Event comparisons do not match grounded Event IDs.")
        if comparison_statuses.count("missing") != len(self.missing_event_ids):
            raise ValueError("Missing Event comparisons do not match missing Event IDs.")
        if comparison_statuses.count("extra") != len(self.extra_source_grounded_event_ids):
            raise ValueError("Extra Event comparisons do not match extra Event IDs.")
        if comparison_statuses.count("incorrectly_grounded") != len(
            self.incorrectly_grounded_event_ids
        ):
            raise ValueError("Incorrect Event comparisons do not match incorrect Event IDs.")
        if self.passed != (
            self.source_segment_observation_count == 1
            and not self.missing_event_ids
            and not self.extra_source_grounded_event_ids
            and not self.incorrectly_grounded_event_ids
        ):
            raise ValueError("Source-grounded pass state does not match its evidence.")
        return self


class SourceGroundedEventPhaseEvaluation(BaseModel):
    """Aggregate source-grounding evidence for one locked Gold partition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: EvaluationPhase
    segment_count: Annotated[int, Field(ge=0)]
    expected_event_count: Annotated[int, Field(ge=0)]
    observed_event_count: Annotated[int, Field(ge=0)]
    grounded_event_count: Annotated[int, Field(ge=0)]
    missing_event_count: Annotated[int, Field(ge=0)]
    extra_event_count: Annotated[int, Field(ge=0)]
    incorrectly_grounded_event_count: Annotated[int, Field(ge=0)]
    approved_review_event_count: Annotated[int, Field(ge=0)]
    rejected_review_event_count: Annotated[int, Field(ge=0)]
    passed: bool


class SourceGroundedEventEvaluationReport(BaseModel):
    """Complete read-only evaluation over the approved source-grounded Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_source_grounded_event_report_v1"] = (
        "hsq_source_grounded_event_report_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    trigger_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    coverage_report_id: Annotated[str, Field(pattern=r"^hdc_[a-f0-9]{24}$")]
    coverage_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    segment_count: Annotated[int, Field(ge=0)]
    expected_event_count: Annotated[int, Field(ge=0)]
    observed_event_count: Annotated[int, Field(ge=0)]
    grounded_event_count: Annotated[int, Field(ge=0)]
    missing_event_count: Annotated[int, Field(ge=0)]
    extra_event_count: Annotated[int, Field(ge=0)]
    incorrectly_grounded_event_count: Annotated[int, Field(ge=0)]
    approved_review_event_count: Annotated[int, Field(ge=0)]
    rejected_review_event_count: Annotated[int, Field(ge=0)]
    phase_evaluations: tuple[SourceGroundedEventPhaseEvaluation, ...]
    segments: tuple[SourceGroundedEventSegmentEvaluation, ...]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    passed: bool

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        ordered_segments = tuple(
            sorted(self.segments, key=lambda item: (item.phase, item.source_text_sha256))
        )
        if self.segments != ordered_segments:
            raise ValueError("Source-grounded segment evaluations must be ordered.")
        expected_phases: tuple[EvaluationPhase, ...] = ("development", "validation")
        if tuple(item.phase for item in self.phase_evaluations) != expected_phases:
            raise ValueError("Source-grounded report requires both ordered Gold phases.")
        phase_by_name = {item.phase: item for item in self.phase_evaluations}
        for phase in expected_phases:
            phase_segments = tuple(item for item in self.segments if item.phase == phase)
            if not phase_segments:
                raise ValueError("Source-grounded report is missing one Gold phase.")
            expected = _phase_evaluation(phase, phase_segments)
            if phase_by_name[phase] != expected:
                raise ValueError("Source-grounded phase summary does not match its segments.")
        totals = _evaluation_totals(self.segments)
        for field_name, expected in totals.items():
            if getattr(self, field_name) != expected:
                raise ValueError(
                    f"Source-grounded report {field_name} does not match its segments."
                )
        if self.passed != all(item.passed for item in self.segments):
            raise ValueError("Source-grounded report pass state does not match its segments.")
        return self


def load_source_grounded_event_gold(
    path: Path,
    *,
    repository_root: Path,
    require_approved: bool = True,
) -> tuple[SourceGroundedEventGoldCatalog, TriggerGoldCatalog]:
    """Load Source-Grounded Event Gold and validate its complete parent binding."""
    catalog = SourceGroundedEventGoldCatalog.model_validate_json(path.read_bytes())
    if require_approved and catalog.review_status != "approved":
        raise ValueError("Source-Grounded Event Gold requires human approval.")
    parent_path = (repository_root / catalog.trigger_gold_path).resolve()
    root = repository_root.resolve()
    if not parent_path.is_relative_to(root):
        raise ValueError("Source-Grounded Event Gold parent path leaves the repository.")
    parent_bytes = parent_path.read_bytes()
    if hashlib.sha256(parent_bytes).hexdigest() != catalog.trigger_gold_sha256:
        raise ValueError("Source-Grounded Event Gold parent digest drifted.")
    parent = TriggerGoldCatalog.model_validate_json(parent_bytes)
    parent_items = {
        event.event_id: (segment.phase, segment.source_text_sha256)
        for segment in parent.segments
        for event in segment.events
    }
    observed_items = {
        item.event_id: (item.phase, item.source_text_sha256) for item in catalog.items
    }
    if observed_items != parent_items:
        raise ValueError("Source-Grounded Event Gold does not cover Trigger Gold exactly.")
    return catalog, parent


def build_source_grounded_event_evaluation_report(
    *,
    catalog: SourceGroundedEventGoldCatalog,
    trigger_gold: TriggerGoldCatalog,
    catalog_sha256: str,
    coverage_report_id: str,
    coverage_report_sha256: str,
    representation_id: str,
    segments: tuple[SourceGroundedEventSegmentEvaluation, ...],
) -> SourceGroundedEventEvaluationReport:
    """Aggregate exact source-grounding evidence without changing canonical state."""
    ordered = tuple(sorted(segments, key=lambda item: (item.phase, item.source_text_sha256)))
    expected_segments = {
        (item.phase, item.source_text_sha256): item for item in trigger_gold.segments
    }
    observed_segments = {(item.phase, item.source_text_sha256): item for item in ordered}
    if len(observed_segments) != len(ordered) or set(observed_segments) != set(expected_segments):
        raise ValueError("Source-grounded report does not cover Trigger Gold exactly.")
    review_by_id = {item.event_id: item for item in catalog.items}
    for key, gold_segment in expected_segments.items():
        evaluation = observed_segments[key]
        expected_ids = {item.event_id for item in gold_segment.events}
        approved = {
            item_id
            for item_id in expected_ids
            if review_by_id[item_id].expected_review_outcome == "approved"
        }
        if (
            evaluation.expected_event_count != len(expected_ids)
            or set(evaluation.grounded_event_ids)
            | set(evaluation.missing_event_ids)
            | set(evaluation.incorrectly_grounded_event_ids)
            != expected_ids
            or set(evaluation.approved_review_event_ids) != approved
            or set(evaluation.rejected_review_event_ids) != expected_ids - approved
        ):
            raise ValueError("Source-grounded segment result drifted from reviewed Gold.")
    totals = _evaluation_totals(ordered)
    return SourceGroundedEventEvaluationReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        trigger_gold_sha256=catalog.trigger_gold_sha256,
        coverage_report_id=coverage_report_id,
        coverage_report_sha256=coverage_report_sha256,
        representation_id=representation_id,
        segment_count=totals["segment_count"],
        expected_event_count=totals["expected_event_count"],
        observed_event_count=totals["observed_event_count"],
        grounded_event_count=totals["grounded_event_count"],
        missing_event_count=totals["missing_event_count"],
        extra_event_count=totals["extra_event_count"],
        incorrectly_grounded_event_count=totals["incorrectly_grounded_event_count"],
        approved_review_event_count=totals["approved_review_event_count"],
        rejected_review_event_count=totals["rejected_review_event_count"],
        phase_evaluations=tuple(
            _phase_evaluation(phase, tuple(item for item in ordered if item.phase == phase))
            for phase in ("development", "validation")
        ),
        segments=ordered,
        passed=all(item.passed for item in ordered),
    )


def evaluate_source_grounded_event_corpus(
    *,
    catalog: SourceGroundedEventGoldCatalog,
    trigger_gold: TriggerGoldCatalog,
    catalog_sha256: str,
    coverage_report_id: str,
    coverage_report_sha256: str,
    representation_id: str,
    source_segment_observation_counts: Mapping[str, int],
    triggers_by_source_text_sha256: Mapping[str, tuple[EventTriggerDraft, ...]],
    source_events_by_source_text_sha256: Mapping[str, tuple[SourceGroundedEventDraft, ...]],
    evidence_by_id: Mapping[str, EvidenceTarget],
) -> SourceGroundedEventEvaluationReport:
    """Evaluate every locked Gold segment from reloaded production evidence."""
    review_items = {item.event_id: item for item in catalog.items}
    segments = tuple(
        evaluate_source_grounded_event_segment(
            gold_segment=segment,
            review_items=review_items,
            triggers=triggers_by_source_text_sha256.get(segment.source_text_sha256, ()),
            source_events=source_events_by_source_text_sha256.get(segment.source_text_sha256, ()),
            evidence_by_id=evidence_by_id,
            source_segment_observation_count=source_segment_observation_counts.get(
                segment.source_text_sha256, 0
            ),
        )
        for segment in trigger_gold.segments
    )
    return build_source_grounded_event_evaluation_report(
        catalog=catalog,
        trigger_gold=trigger_gold,
        catalog_sha256=catalog_sha256,
        coverage_report_id=coverage_report_id,
        coverage_report_sha256=coverage_report_sha256,
        representation_id=representation_id,
        segments=segments,
    )


def evaluate_source_grounded_event_segment(
    *,
    gold_segment: TriggerGoldSegment,
    review_items: Mapping[str, SourceGroundedEventGoldItem],
    triggers: tuple[EventTriggerDraft, ...],
    source_events: tuple[SourceGroundedEventDraft, ...],
    evidence_by_id: Mapping[str, EvidenceTarget],
    source_segment_observation_count: int = 1,
) -> SourceGroundedEventSegmentEvaluation:
    """Compare one deterministic grounding result with reviewed Trigger Gold."""
    trigger_ids = tuple(item.id for item in triggers)
    if len(set(trigger_ids)) != len(trigger_ids):
        raise ValueError("Source-grounded evaluation received duplicate trigger IDs.")
    source_event_ids = tuple(item.id for item in source_events)
    if len(set(source_event_ids)) != len(source_event_ids):
        raise ValueError("Source-grounded evaluation received duplicate Event IDs.")

    expected_by_trigger_id: dict[str, TriggerGoldEvent] = {}
    for trigger in triggers:
        matches = tuple(
            event
            for event in gold_segment.events
            if _trigger_matches_gold(gold_segment, event, trigger)
        )
        if len(matches) == 1:
            expected_by_trigger_id[trigger.id] = matches[0]

    source_events_by_gold: dict[str, list[tuple[EventTriggerDraft, SourceGroundedEventDraft]]] = {}
    trigger_by_id = {item.id: item for item in triggers}
    extra: set[str] = set()
    for source_event in source_events:
        trigger = trigger_by_id.get(source_event.trigger_id)
        expected = expected_by_trigger_id.get(source_event.trigger_id)
        if trigger is None or expected is None:
            extra.add(source_event.id)
            continue
        source_events_by_gold.setdefault(expected.event_id, []).append((trigger, source_event))

    gold_by_id = {item.event_id: item for item in gold_segment.events}
    grounded: set[str] = set()
    incorrect: set[str] = set()
    retained_by_gold: dict[str, tuple[EventTriggerDraft, SourceGroundedEventDraft]] = {}
    for event_id, candidates in source_events_by_gold.items():
        ordered = sorted(candidates, key=lambda item: item[1].id)
        exact = tuple(
            item
            for item in ordered
            if _grounding_is_exact(gold_segment, item[0], item[1], evidence_by_id)
        )
        if exact:
            grounded.add(event_id)
            retained = exact[0]
        else:
            incorrect.add(event_id)
            retained = ordered[0]
        retained_by_gold[event_id] = retained
        retained_id = retained[1].id
        extra.update(item.id for _, item in ordered if item.id != retained_id)

    expected_ids = {item.event_id for item in gold_segment.events}
    missing = expected_ids - grounded - incorrect
    approved = {
        item_id
        for item_id in expected_ids
        if review_items[item_id].expected_review_outcome == "approved"
    }
    rejected = expected_ids - approved
    source_event_by_id = {item.id: item for item in source_events}
    comparisons: list[NormalizedEventComparison] = []
    for event_id in sorted(expected_ids):
        expected = _normalized_expected_event(gold_segment, gold_by_id[event_id])
        retained = retained_by_gold.get(event_id)
        if retained is None:
            comparisons.append(
                NormalizedEventComparison(status="missing", expected=expected, actual=None)
            )
            continue
        status: Literal["exact", "incorrectly_grounded"] = (
            "exact" if event_id in grounded else "incorrectly_grounded"
        )
        comparisons.append(
            NormalizedEventComparison(
                status=status,
                expected=expected,
                actual=_normalized_actual_event(gold_segment, retained[0], retained[1]),
            )
        )
    for source_event_id in sorted(extra):
        source_event = source_event_by_id[source_event_id]
        trigger = trigger_by_id.get(source_event.trigger_id)
        if trigger is None:
            raise ValueError("An extra source-grounded Event references an unknown trigger.")
        comparisons.append(
            NormalizedEventComparison(
                status="extra",
                expected=None,
                actual=_normalized_actual_event(gold_segment, trigger, source_event),
            )
        )
    return SourceGroundedEventSegmentEvaluation(
        phase=gold_segment.phase,
        source_text_sha256=gold_segment.source_text_sha256,
        source_segment_observation_count=source_segment_observation_count,
        expected_event_count=len(expected_ids),
        observed_event_count=len(source_events),
        grounded_event_ids=tuple(sorted(grounded)),
        missing_event_ids=tuple(sorted(missing)),
        extra_source_grounded_event_ids=tuple(sorted(extra)),
        incorrectly_grounded_event_ids=tuple(sorted(incorrect)),
        approved_review_event_ids=tuple(sorted(approved)),
        rejected_review_event_ids=tuple(sorted(rejected)),
        comparisons=tuple(comparisons),
        passed=(
            source_segment_observation_count == 1 and not missing and not extra and not incorrect
        ),
    )


def _normalized_expected_event(
    segment: TriggerGoldSegment,
    event: TriggerGoldEvent,
) -> NormalizedExpectedEvent:
    source_copy = derive_source_copy_view(segment.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    head_occurrence = occurrences[event.head_occurrence_id]
    head_start, head_end = source_copy.authoritative_range(
        head_occurrence.start,
        head_occurrence.end,
    )
    expressions = tuple(
        _normalized_expression(
            segment.source_text,
            *source_copy.authoritative_range(
                occurrences[item.start_occurrence_id].start,
                occurrences[item.end_occurrence_id].end,
            ),
        )
        for item in event.accepted_expression_ranges
    )
    return NormalizedExpectedEvent(
        event_id=event.event_id,
        diagnostic_meaning=event.meaning,
        head=_normalized_expression(segment.source_text, head_start, head_end),
        accepted_expressions=expressions,
    )


def _normalized_actual_event(
    segment: TriggerGoldSegment,
    trigger: EventTriggerDraft,
    source_event: SourceGroundedEventDraft,
) -> NormalizedActualEvent:
    mention = source_event.mention
    return NormalizedActualEvent(
        source_grounded_event_id=source_event.id,
        event_subject_id=source_event.event_subject_id,
        trigger_id=trigger.id,
        head=_normalized_expression(segment.source_text, trigger.head_start, trigger.head_end),
        expression=_normalized_expression(segment.source_text, trigger.start, trigger.end),
        head_evidence_target_id=mention.head_evidence_target_id,
        expression_evidence_target_id=mention.expression_evidence_target_id,
        support_evidence_target_id=mention.support_evidence_target_id,
    )


def _normalized_expression(source_text: str, start: int, end: int) -> NormalizedSourceExpression:
    return NormalizedSourceExpression(start=start, end=end, text=source_text[start:end])


def _trigger_matches_gold(
    segment: TriggerGoldSegment,
    expected: TriggerGoldEvent,
    trigger: EventTriggerDraft,
) -> bool:
    if trigger.source_text_sha256 != segment.source_text_sha256:
        return False
    source_copy = derive_source_copy_view(segment.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    head = occurrences[expected.head_occurrence_id]
    head_range = source_copy.authoritative_range(head.start, head.end)
    expression_ranges = {
        source_copy.authoritative_range(
            occurrences[item.start_occurrence_id].start,
            occurrences[item.end_occurrence_id].end,
        )
        for item in expected.accepted_expression_ranges
    }
    return (trigger.head_start, trigger.head_end) == head_range and (
        trigger.start,
        trigger.end,
    ) in expression_ranges


def _grounding_is_exact(
    segment: TriggerGoldSegment,
    trigger: EventTriggerDraft,
    source_event: SourceGroundedEventDraft,
    evidence_by_id: Mapping[str, EvidenceTarget],
) -> bool:
    if (
        source_event.trigger_id != trigger.id
        or source_event.source_segment_id != trigger.source_segment_id
        or source_event.source_text_sha256 != segment.source_text_sha256
        or source_event.expression_text != trigger.text
        or source_event.head_text != trigger.head_text
    ):
        return False
    mention = source_event.mention
    target_ids = (
        mention.head_evidence_target_id,
        mention.expression_evidence_target_id,
        mention.support_evidence_target_id,
    )
    if any(item not in evidence_by_id for item in target_ids):
        return False
    head, expression, support = (evidence_by_id[item] for item in target_ids)
    if (
        (
            head.start_char - support.start_char,
            head.end_char - support.start_char,
            head.exact_text,
        )
        != (trigger.head_start, trigger.head_end, trigger.head_text)
        or (
            expression.start_char - support.start_char,
            expression.end_char - support.start_char,
            expression.exact_text,
        )
        != (trigger.start, trigger.end, trigger.text)
        or support.exact_text != segment.source_text
    ):
        return False
    try:
        validate_source_grounded_event(
            build_source_grounded_event(source_event),
            evidence_by_id,
        )
    except ValueError:
        return False
    return True


def _evaluation_totals(
    segments: tuple[SourceGroundedEventSegmentEvaluation, ...],
) -> dict[str, int]:
    return {
        "segment_count": len(segments),
        "expected_event_count": sum(item.expected_event_count for item in segments),
        "observed_event_count": sum(item.observed_event_count for item in segments),
        "grounded_event_count": sum(len(item.grounded_event_ids) for item in segments),
        "missing_event_count": sum(len(item.missing_event_ids) for item in segments),
        "extra_event_count": sum(len(item.extra_source_grounded_event_ids) for item in segments),
        "incorrectly_grounded_event_count": sum(
            len(item.incorrectly_grounded_event_ids) for item in segments
        ),
        "approved_review_event_count": sum(
            len(item.approved_review_event_ids) for item in segments
        ),
        "rejected_review_event_count": sum(
            len(item.rejected_review_event_ids) for item in segments
        ),
    }


def _phase_evaluation(
    phase: EvaluationPhase,
    segments: tuple[SourceGroundedEventSegmentEvaluation, ...],
) -> SourceGroundedEventPhaseEvaluation:
    return SourceGroundedEventPhaseEvaluation(
        phase=phase,
        passed=all(item.passed for item in segments),
        **_evaluation_totals(segments),
    )
