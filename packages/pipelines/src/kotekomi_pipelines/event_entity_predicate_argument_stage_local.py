"""Gold evaluation for the model-free Stanza predicate-argument diagnostic."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_application import (
    EventEntityConnectionCandidate,
    EventTriggerDraft,
    PredicateArgumentHypothesis,
    PredicateArgumentObservation,
    SourceGroundedEventDraft,
    build_event_entity_connection_candidates,
    build_predicate_argument_observation,
    predicate_argument_is_structurally_supported,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.evaluation_contracts import EvaluationPhase
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldCatalog,
    ConnectionGoldEntity,
    ConnectionGoldEvent,
    EventEntityExperimentInput,
)

_SHA256 = r"^[a-f0-9]{64}$"


class PredicateArgumentComparison(StrEnum):
    """The occurrence-level comparison between one observation and Gold."""

    STRUCTURAL_MATCH = "structural_match"
    STRUCTURAL_EXTRA = "structural_extra"
    EXPECTED_SEMANTIC_REMAINDER = "expected_semantic_remainder"
    EXPECTED_DIAGNOSTIC_GAP = "expected_diagnostic_gap"
    EXPECTED_DIFFERENT_SENTENCE = "expected_different_sentence"
    IMPLICIT_NEGATIVE_RETAINED = "implicit_negative_retained"


class PredicateArgumentCandidateEvaluation(BaseModel):
    """One exact candidate occurrence compared with reviewed Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    entity_kind: Literal["actor", "organization"]
    entity_name: Annotated[str, Field(min_length=1)]
    entity_start: Annotated[int, Field(ge=0)]
    entity_end: Annotated[int, Field(gt=0)]
    entity_text: Annotated[str, Field(min_length=1)]
    expected_entity_ids: tuple[Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")], ...]
    structurally_supported: bool
    comparison: PredicateArgumentComparison
    observation: PredicateArgumentObservation

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.entity_end - self.entity_start != len(self.entity_text):
            raise ValueError("Predicate-argument evaluation range does not match its text.")
        if tuple(sorted(set(self.expected_entity_ids))) != self.expected_entity_ids:
            raise ValueError("Predicate-argument expected entity IDs must be ordered and distinct.")
        if self.structurally_supported != predicate_argument_is_structurally_supported(
            self.observation.hypothesis
        ):
            raise ValueError("Predicate-argument structural support drifted from its observation.")
        if self.expected_entity_ids and self.structurally_supported:
            expected = PredicateArgumentComparison.STRUCTURAL_MATCH
        elif not self.expected_entity_ids and self.structurally_supported:
            expected = PredicateArgumentComparison.STRUCTURAL_EXTRA
        elif self.expected_entity_ids and (
            self.observation.hypothesis is PredicateArgumentHypothesis.DIAGNOSTIC_GAP
        ):
            expected = PredicateArgumentComparison.EXPECTED_DIAGNOSTIC_GAP
        elif self.expected_entity_ids and (
            self.observation.hypothesis is PredicateArgumentHypothesis.DIFFERENT_SENTENCE
        ):
            expected = PredicateArgumentComparison.EXPECTED_DIFFERENT_SENTENCE
        elif self.expected_entity_ids:
            expected = PredicateArgumentComparison.EXPECTED_SEMANTIC_REMAINDER
        else:
            expected = PredicateArgumentComparison.IMPLICIT_NEGATIVE_RETAINED
        if self.comparison is not expected:
            raise ValueError("Predicate-argument comparison does not match its evidence.")
        return self


class PredicateArgumentEventEvaluation(BaseModel):
    """Complete diagnostic evidence for one reviewed Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    gold_event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    phase: EvaluationPhase
    source_segment_label: Annotated[str, Field(min_length=1)]
    source_text: Annotated[str, Field(min_length=1)]
    event_meaning: Annotated[str, Field(min_length=1)]
    trigger: EventTriggerDraft
    event: SourceGroundedEventDraft
    expected_entity_ids: tuple[Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")], ...]
    structurally_matched_entity_ids: tuple[Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")], ...]
    semantic_remainder_entity_ids: tuple[Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")], ...]
    missing_candidate_entity_ids: tuple[Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")], ...]
    candidates: tuple[PredicateArgumentCandidateEvaluation, ...]

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        expected = set(self.expected_entity_ids)
        structural = set(self.structurally_matched_entity_ids)
        remainder = set(self.semantic_remainder_entity_ids)
        missing = set(self.missing_candidate_entity_ids)
        if structural | remainder | missing != expected:
            raise ValueError("Predicate-argument Event result does not partition Gold entities.")
        if (structural & remainder) or (structural & missing) or (remainder & missing):
            raise ValueError("Predicate-argument Event result partitions overlap.")
        candidate_ids = tuple(item.candidate_id for item in self.candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("Predicate-argument Event repeats a candidate.")
        return self


class PredicateArgumentHypothesisMetrics(BaseModel):
    """Occurrence-level Gold metrics for one diagnostic hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    hypothesis: PredicateArgumentHypothesis
    candidate_count: Annotated[int, Field(ge=0)]
    expected_candidate_count: Annotated[int, Field(ge=0)]
    implicit_negative_count: Annotated[int, Field(ge=0)]
    structural_match_count: Annotated[int, Field(ge=0)]
    structural_extra_count: Annotated[int, Field(ge=0)]
    precision: Annotated[float, Field(ge=0.0, le=1.0)] | None
    gold_candidate_recall: Annotated[float, Field(ge=0.0, le=1.0)]

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        if self.expected_candidate_count + self.implicit_negative_count != self.candidate_count:
            raise ValueError("Predicate-argument hypothesis candidate partition drifted.")
        structurally_supported = predicate_argument_is_structurally_supported(self.hypothesis)
        if not structurally_supported and (
            self.structural_match_count or self.structural_extra_count or self.precision is not None
        ):
            raise ValueError("A non-structural hypothesis cannot report structural precision.")
        if structurally_supported:
            denominator = self.structural_match_count + self.structural_extra_count
            expected_precision = self.structural_match_count / denominator if denominator else 0.0
            if self.precision != expected_precision:
                raise ValueError("Predicate-argument hypothesis precision drifted.")
        return self


class PredicateArgumentPhaseReport(BaseModel):
    """One complete development or validation diagnostic report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["predicate_argument_phase_report_v1"] = (
        "predicate_argument_phase_report_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    phase: EvaluationPhase
    event_count: Annotated[int, Field(ge=0)]
    candidate_count: Annotated[int, Field(ge=0)]
    expected_candidate_count: Annotated[int, Field(ge=0)]
    expected_entity_count: Annotated[int, Field(ge=0)]
    structurally_matched_entity_count: Annotated[int, Field(ge=0)]
    semantic_remainder_entity_count: Annotated[int, Field(ge=0)]
    missing_candidate_entity_count: Annotated[int, Field(ge=0)]
    structural_match_count: Annotated[int, Field(ge=0)]
    structural_extra_count: Annotated[int, Field(ge=0)]
    expected_semantic_remainder_count: Annotated[int, Field(ge=0)]
    expected_diagnostic_gap_count: Annotated[int, Field(ge=0)]
    expected_different_sentence_count: Annotated[int, Field(ge=0)]
    implicit_negative_count: Annotated[int, Field(ge=0)]
    diagnostic_gap_count: Annotated[int, Field(ge=0)]
    potential_model_candidate_reduction_count: Annotated[int, Field(ge=0)]
    structural_precision: Annotated[float, Field(ge=0.0, le=1.0)]
    structural_entity_recall: Annotated[float, Field(ge=0.0, le=1.0)]
    hypothesis_metrics: tuple[PredicateArgumentHypothesisMetrics, ...]
    model_execution_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    complete: bool
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    events: tuple[PredicateArgumentEventEvaluation, ...]

    @model_validator(mode="after")
    def validate_phase(self) -> Self:
        if self.event_count != len(self.events):
            raise ValueError("Predicate-argument phase Event count drifted.")
        if self.candidate_count != sum(len(item.candidates) for item in self.events):
            raise ValueError("Predicate-argument phase candidate count drifted.")
        if tuple(item.hypothesis for item in self.hypothesis_metrics) != tuple(
            PredicateArgumentHypothesis
        ):
            raise ValueError("Predicate-argument phase hypothesis metrics are incomplete.")
        if sum(item.candidate_count for item in self.hypothesis_metrics) != self.candidate_count:
            raise ValueError("Predicate-argument phase hypothesis counts drifted.")
        if self.result_fingerprint != _phase_fingerprint(self.events):
            raise ValueError("Predicate-argument phase fingerprint drifted.")
        return self


class PredicateArgumentDiagnosticReport(BaseModel):
    """The complete 40-case model-free diagnostic result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["predicate_argument_diagnostic_v1"] = "predicate_argument_diagnostic_v1"
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    development: PredicateArgumentPhaseReport
    validation: PredicateArgumentPhaseReport
    routing_hypothesis_supported: bool
    model_execution_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    passed: bool
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.development.phase != "development" or self.validation.phase != "validation":
            raise ValueError("Predicate-argument report requires both evaluation phases.")
        expected_supported = all(
            item.structural_match_count > 0 and item.structural_extra_count == 0
            for item in (self.development, self.validation)
        )
        if self.routing_hypothesis_supported != expected_supported:
            raise ValueError("Predicate-argument routing conclusion drifted from phase evidence.")
        expected_passed = (
            self.development.complete
            and self.validation.complete
            and self.development.event_count == 20
            and self.validation.event_count == 20
        )
        if self.passed != expected_passed:
            raise ValueError("Predicate-argument diagnostic status drifted from its evidence.")
        expected_fingerprint = hashlib.sha256(
            _canonical_json(
                {
                    "development": self.development.result_fingerprint,
                    "validation": self.validation.result_fingerprint,
                    "routing_hypothesis_supported": self.routing_hypothesis_supported,
                }
            ).encode()
        ).hexdigest()
        if self.result_fingerprint != expected_fingerprint:
            raise ValueError("Predicate-argument diagnostic fingerprint drifted.")
        return self


def build_predicate_argument_diagnostic_report(
    *,
    catalog: ConnectionGoldCatalog,
    catalog_sha256: str,
    inputs: tuple[EventEntityExperimentInput, ...],
) -> PredicateArgumentDiagnosticReport:
    """Analyze and evaluate all forty approved Gold Events without a model runtime."""
    if catalog.review_status != "approved":
        raise ValueError("Predicate-argument diagnostic requires approved Gold.")
    if len(inputs) != 40 or {item.gold_event_id for item in inputs} != {
        item.event_id for item in catalog.events
    }:
        raise ValueError("Predicate-argument diagnostic requires all forty Gold Events.")
    gold_by_id = {item.event_id: item for item in catalog.events}
    events = tuple(
        evaluate_predicate_argument_event(gold_by_id[prepared.gold_event_id], prepared)
        for prepared in sorted(inputs, key=lambda item: item.gold_event_id)
    )
    development = build_predicate_argument_phase_report(
        catalog=catalog,
        catalog_sha256=catalog_sha256,
        phase="development",
        events=tuple(item for item in events if item.phase == "development"),
    )
    validation = build_predicate_argument_phase_report(
        catalog=catalog,
        catalog_sha256=catalog_sha256,
        phase="validation",
        events=tuple(item for item in events if item.phase == "validation"),
    )
    routing_supported = all(
        item.structural_match_count > 0 and item.structural_extra_count == 0
        for item in (development, validation)
    )
    fingerprint = hashlib.sha256(
        _canonical_json(
            {
                "development": development.result_fingerprint,
                "validation": validation.result_fingerprint,
                "routing_hypothesis_supported": routing_supported,
            }
        ).encode()
    ).hexdigest()
    return PredicateArgumentDiagnosticReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        development=development,
        validation=validation,
        routing_hypothesis_supported=routing_supported,
        passed=development.complete and validation.complete,
        result_fingerprint=fingerprint,
    )


def render_predicate_argument_review(report: PredicateArgumentDiagnosticReport) -> str:
    """Render exact data-in/data-out evidence for human review."""
    lines = [
        "# Stanza Predicate-Argument Diagnostic Review",
        "",
        f"Catalog: `{report.catalog_id}`",
        "",
        f"Catalog SHA-256: `{report.catalog_sha256}`",
        "",
        f"Diagnostic complete: `{str(report.passed).lower()}`",
        "",
        f"Routing hypothesis supported: `{str(report.routing_hypothesis_supported).lower()}`",
        "",
    ]
    for phase in (report.development, report.validation):
        lines.extend(
            (
                f"## {phase.phase.title()}",
                "",
                f"Events: `{phase.event_count}`",
                "",
                f"Candidates: `{phase.candidate_count}`",
                "",
                f"Structural matches: `{phase.structural_match_count}`",
                "",
                f"Structural extras: `{phase.structural_extra_count}`",
                "",
                f"Expected semantic remainders: `{phase.expected_semantic_remainder_count}`",
                "",
            )
        )
        for event in phase.events:
            lines.extend(
                (
                    f"### {event.gold_event_id}",
                    "",
                    "Exact SourceSegment:",
                    "",
                    "> " + event.source_text.replace("\n", "\n> "),
                    "",
                    f"Expected intelligence: {event.event_meaning}",
                    "",
                    "Exact Event expression: "
                    f"`{event.trigger.start}:{event.trigger.end}` — "
                    + json.dumps(event.trigger.text, ensure_ascii=False),
                    "",
                    "Exact Event head: "
                    f"`{event.trigger.head_start}:{event.trigger.head_end}` — "
                    + json.dumps(event.trigger.head_text, ensure_ascii=False),
                    "",
                )
            )
            for candidate in event.candidates:
                observation = candidate.observation
                expected = (
                    ", ".join(candidate.expected_entity_ids)
                    if candidate.expected_entity_ids
                    else "implicit negative"
                )
                path = (
                    " -> ".join(
                        f"{item.token_id}:{item.text}/{item.dependency_relation}"
                        for item in observation.path_tokens
                    )
                    if observation.path_tokens
                    else "none"
                )
                lines.extend(
                    (
                        f"#### Candidate `{candidate.candidate_id}`",
                        "",
                        "Exact candidate: "
                        f"`{candidate.entity_start}:{candidate.entity_end}` — "
                        + json.dumps(candidate.entity_text, ensure_ascii=False),
                        "",
                        f"Entity: `{candidate.entity_kind}:{candidate.entity_name}`",
                        "",
                        f"Expected result: {expected}",
                        "",
                        f"Actual hypothesis: `{observation.hypothesis.value}`",
                        "",
                        f"Actual comparison: `{candidate.comparison.value}`",
                        "",
                        f"Dependency path: {path}",
                        "",
                        "Diagnostic gap: "
                        + (
                            f"`{observation.gap_code.value}`"
                            if observation.gap_code is not None
                            else "none"
                        ),
                        "",
                    )
                )
    return "\n".join(lines)


def predicate_argument_summary(report: PredicateArgumentDiagnosticReport) -> dict[str, object]:
    """Return a bounded machine-readable summary without source text."""
    return {
        "schema_version": "predicate_argument_diagnostic_summary_v1",
        "catalog_id": report.catalog_id,
        "catalog_sha256": report.catalog_sha256,
        "passed": report.passed,
        "routing_hypothesis_supported": report.routing_hypothesis_supported,
        "model_execution_count": report.model_execution_count,
        "accepted_ledger_change_count": report.accepted_ledger_change_count,
        "result_fingerprint": report.result_fingerprint,
        "development": _phase_summary(report.development),
        "validation": _phase_summary(report.validation),
    }


def evaluate_predicate_argument_event(
    gold: ConnectionGoldEvent,
    prepared: EventEntityExperimentInput,
) -> PredicateArgumentEventEvaluation:
    if prepared.gold_event_id != gold.event_id or prepared.phase != gold.phase:
        raise ValueError("Predicate-argument input belongs to another Gold Event.")
    candidates = build_event_entity_connection_candidates(
        prepared.event,
        prepared.candidate_selection.mentions,
        source_text=prepared.source_text,
    )
    evaluations: list[PredicateArgumentCandidateEvaluation] = []
    for candidate in candidates:
        observation = build_predicate_argument_observation(
            source_text=prepared.source_text,
            trigger=prepared.trigger,
            event=prepared.event,
            candidate=candidate,
            linguistic_evidence=prepared.linguistic_evidence,
        )
        expected_ids = tuple(
            sorted(
                item.entity_id
                for item in gold.expected_entities
                if _candidate_matches_expected(candidate, item)
            )
        )
        structurally_supported = predicate_argument_is_structurally_supported(
            observation.hypothesis
        )
        comparison = _comparison(
            expected=bool(expected_ids),
            structurally_supported=structurally_supported,
            hypothesis=observation.hypothesis,
        )
        primary_span = next(
            item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
        )
        evaluations.append(
            PredicateArgumentCandidateEvaluation(
                candidate_id=candidate.id,
                entity_kind=candidate.entity_kind.value,
                entity_name=candidate.entity_name,
                entity_start=primary_span.start,
                entity_end=primary_span.end,
                entity_text=primary_span.text,
                expected_entity_ids=expected_ids,
                structurally_supported=structurally_supported,
                comparison=comparison,
                observation=observation,
            )
        )
    expected_ids = tuple(item.entity_id for item in gold.expected_entities)
    available = {entity_id for item in evaluations for entity_id in item.expected_entity_ids}
    structural = {
        entity_id
        for item in evaluations
        if item.structurally_supported
        for entity_id in item.expected_entity_ids
    }
    remainder = available - structural
    missing = set(expected_ids) - available
    return PredicateArgumentEventEvaluation(
        gold_event_id=gold.event_id,
        phase=gold.phase,
        source_segment_label=prepared.source_segment_label,
        source_text=prepared.source_text,
        event_meaning=gold.event_meaning,
        trigger=prepared.trigger,
        event=prepared.event,
        expected_entity_ids=expected_ids,
        structurally_matched_entity_ids=tuple(sorted(structural)),
        semantic_remainder_entity_ids=tuple(sorted(remainder)),
        missing_candidate_entity_ids=tuple(sorted(missing)),
        candidates=tuple(evaluations),
    )


def _candidate_matches_expected(
    candidate: EventEntityConnectionCandidate,
    expected: ConnectionGoldEntity,
) -> bool:
    primary_span = next(
        item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
    )
    accepted_ranges = {
        (item.start, item.end, item.source_text) for item in expected.accepted_source_occurrences
    }
    return (
        candidate.entity_kind is expected.entity_kind
        and candidate.entity_name in expected.accepted_entity_names
        and (primary_span.start, primary_span.end, primary_span.text) in accepted_ranges
    )


def _comparison(
    *,
    expected: bool,
    structurally_supported: bool,
    hypothesis: PredicateArgumentHypothesis,
) -> PredicateArgumentComparison:
    if expected and structurally_supported:
        return PredicateArgumentComparison.STRUCTURAL_MATCH
    if not expected and structurally_supported:
        return PredicateArgumentComparison.STRUCTURAL_EXTRA
    if expected and hypothesis is PredicateArgumentHypothesis.DIAGNOSTIC_GAP:
        return PredicateArgumentComparison.EXPECTED_DIAGNOSTIC_GAP
    if expected and hypothesis is PredicateArgumentHypothesis.DIFFERENT_SENTENCE:
        return PredicateArgumentComparison.EXPECTED_DIFFERENT_SENTENCE
    if expected:
        return PredicateArgumentComparison.EXPECTED_SEMANTIC_REMAINDER
    return PredicateArgumentComparison.IMPLICIT_NEGATIVE_RETAINED


def build_predicate_argument_phase_report(
    *,
    catalog: ConnectionGoldCatalog,
    catalog_sha256: str,
    phase: EvaluationPhase,
    events: tuple[PredicateArgumentEventEvaluation, ...],
) -> PredicateArgumentPhaseReport:
    candidates = tuple(candidate for event in events for candidate in event.candidates)
    expected_candidate_count = sum(bool(item.expected_entity_ids) for item in candidates)
    hypothesis_metrics = tuple(
        _hypothesis_metrics(
            hypothesis=hypothesis,
            candidates=tuple(
                item for item in candidates if item.observation.hypothesis is hypothesis
            ),
            total_expected_candidate_count=expected_candidate_count,
        )
        for hypothesis in PredicateArgumentHypothesis
    )
    structural_match_count = sum(
        item.comparison is PredicateArgumentComparison.STRUCTURAL_MATCH for item in candidates
    )
    structural_extra_count = sum(
        item.comparison is PredicateArgumentComparison.STRUCTURAL_EXTRA for item in candidates
    )
    precision_denominator = structural_match_count + structural_extra_count
    expected_entity_count = sum(len(item.expected_entity_ids) for item in events)
    structural_entity_count = sum(len(item.structurally_matched_entity_ids) for item in events)
    return PredicateArgumentPhaseReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        phase=phase,
        event_count=len(events),
        candidate_count=len(candidates),
        expected_candidate_count=expected_candidate_count,
        expected_entity_count=expected_entity_count,
        structurally_matched_entity_count=structural_entity_count,
        semantic_remainder_entity_count=sum(
            len(item.semantic_remainder_entity_ids) for item in events
        ),
        missing_candidate_entity_count=sum(
            len(item.missing_candidate_entity_ids) for item in events
        ),
        structural_match_count=structural_match_count,
        structural_extra_count=structural_extra_count,
        expected_semantic_remainder_count=sum(
            item.comparison is PredicateArgumentComparison.EXPECTED_SEMANTIC_REMAINDER
            for item in candidates
        ),
        expected_diagnostic_gap_count=sum(
            item.comparison is PredicateArgumentComparison.EXPECTED_DIAGNOSTIC_GAP
            for item in candidates
        ),
        expected_different_sentence_count=sum(
            item.comparison is PredicateArgumentComparison.EXPECTED_DIFFERENT_SENTENCE
            for item in candidates
        ),
        implicit_negative_count=sum(not item.expected_entity_ids for item in candidates),
        diagnostic_gap_count=sum(
            item.observation.hypothesis is PredicateArgumentHypothesis.DIAGNOSTIC_GAP
            for item in candidates
        ),
        potential_model_candidate_reduction_count=sum(
            item.structurally_supported for item in candidates
        ),
        structural_precision=(
            structural_match_count / precision_denominator if precision_denominator else 0.0
        ),
        structural_entity_recall=(
            structural_entity_count / expected_entity_count if expected_entity_count else 0.0
        ),
        hypothesis_metrics=hypothesis_metrics,
        complete=(
            len(events) == 20
            and all(not item.missing_candidate_entity_ids for item in events)
            and len(candidates) == sum(len(item.candidates) for item in events)
        ),
        result_fingerprint=_phase_fingerprint(events),
        events=events,
    )


def _phase_summary(report: PredicateArgumentPhaseReport) -> dict[str, object]:
    return {
        "event_count": report.event_count,
        "candidate_count": report.candidate_count,
        "expected_candidate_count": report.expected_candidate_count,
        "expected_entity_count": report.expected_entity_count,
        "structurally_matched_entity_count": report.structurally_matched_entity_count,
        "semantic_remainder_entity_count": report.semantic_remainder_entity_count,
        "missing_candidate_entity_count": report.missing_candidate_entity_count,
        "structural_match_count": report.structural_match_count,
        "structural_extra_count": report.structural_extra_count,
        "expected_semantic_remainder_count": report.expected_semantic_remainder_count,
        "expected_diagnostic_gap_count": report.expected_diagnostic_gap_count,
        "expected_different_sentence_count": report.expected_different_sentence_count,
        "implicit_negative_count": report.implicit_negative_count,
        "diagnostic_gap_count": report.diagnostic_gap_count,
        "potential_model_candidate_reduction_count": (
            report.potential_model_candidate_reduction_count
        ),
        "structural_precision": report.structural_precision,
        "structural_entity_recall": report.structural_entity_recall,
        "hypothesis_metrics": {
            item.hypothesis.value: {
                "candidate_count": item.candidate_count,
                "expected_candidate_count": item.expected_candidate_count,
                "implicit_negative_count": item.implicit_negative_count,
                "structural_match_count": item.structural_match_count,
                "structural_extra_count": item.structural_extra_count,
                "precision": item.precision,
                "gold_candidate_recall": item.gold_candidate_recall,
            }
            for item in report.hypothesis_metrics
        },
        "model_execution_count": report.model_execution_count,
        "accepted_ledger_change_count": report.accepted_ledger_change_count,
        "complete": report.complete,
        "result_fingerprint": report.result_fingerprint,
    }


def _hypothesis_metrics(
    *,
    hypothesis: PredicateArgumentHypothesis,
    candidates: tuple[PredicateArgumentCandidateEvaluation, ...],
    total_expected_candidate_count: int,
) -> PredicateArgumentHypothesisMetrics:
    expected_count = sum(bool(item.expected_entity_ids) for item in candidates)
    match_count = sum(
        item.comparison is PredicateArgumentComparison.STRUCTURAL_MATCH for item in candidates
    )
    extra_count = sum(
        item.comparison is PredicateArgumentComparison.STRUCTURAL_EXTRA for item in candidates
    )
    structurally_supported = predicate_argument_is_structurally_supported(hypothesis)
    precision_denominator = match_count + extra_count
    return PredicateArgumentHypothesisMetrics(
        hypothesis=hypothesis,
        candidate_count=len(candidates),
        expected_candidate_count=expected_count,
        implicit_negative_count=len(candidates) - expected_count,
        structural_match_count=match_count,
        structural_extra_count=extra_count,
        precision=(
            match_count / precision_denominator
            if structurally_supported and precision_denominator
            else 0.0
            if structurally_supported
            else None
        ),
        gold_candidate_recall=(
            expected_count / total_expected_candidate_count
            if total_expected_candidate_count
            else 0.0
        ),
    )


def _phase_fingerprint(events: tuple[PredicateArgumentEventEvaluation, ...]) -> str:
    payload = [
        {
            "gold_event_id": event.gold_event_id,
            "candidates": [
                {
                    "candidate_id": item.candidate_id,
                    "expected_entity_ids": item.expected_entity_ids,
                    "comparison": item.comparison.value,
                    "observation_id": item.observation.id,
                }
                for item in event.candidates
            ],
        }
        for event in events
    ]
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
