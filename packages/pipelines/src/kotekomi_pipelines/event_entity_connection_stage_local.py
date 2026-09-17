"""Gold contracts and pure evaluation for Event-entity connection experiments."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from kotekomi_application import (
    EventEntityCandidateGap,
    EventEntityCandidateGapReason,
    EventEntityCandidateRouteKind,
    EventEntityCandidateSelection,
    EventEntityConnectionCandidate,
    EventEntityConnectionDisposition,
    EventEntityConnectionPreview,
    EventEntityKind,
    EventEntityLinguisticEvidence,
    EventTriggerDraft,
    SourceGroundedEventDraft,
    build_event_entity_candidate_routes,
    build_event_entity_connection_candidates,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.evaluation_contracts import EvaluationPhase
from kotekomi_pipelines.event_trigger_stage_local import TriggerGoldCatalog
from kotekomi_pipelines.source_grounded_event_evaluation import (
    SourceGroundedEventGoldCatalog,
)

_SHA256 = r"^[a-f0-9]{64}$"

type EventEntityPreparationStatus = Literal[
    "gold_review_required",
    "upstream_blocked",
    "prepared",
]


class EventEntityGoldDisposition(StrEnum):
    """Raw Gold label for one exact Event-entity candidate occurrence."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class EventEntityOccurrenceScore(StrEnum):
    """Strict occurrence score for one exact candidate decision."""

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    TRUE_NEGATIVE = "true_negative"


class EventEntityOccurrenceEvaluation(BaseModel):
    """One exact candidate occurrence compared directly with raw Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    candidate_id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    candidate_signature: Annotated[str, Field(pattern=_SHA256)]
    entity_identity: Annotated[str, Field(min_length=1)]
    entity_kind: EventEntityKind
    entity_name: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_start: Annotated[int, Field(ge=0)]
    source_end: Annotated[int, Field(gt=0)]
    source_text: Annotated[str, Field(min_length=1)]
    expected_entity_ids: tuple[Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")], ...]
    gold_disposition: EventEntityGoldDisposition
    observed_disposition: EventEntityConnectionDisposition
    strict_score: EventEntityOccurrenceScore
    unresolved: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.source_end - self.source_start != len(self.source_text):
            raise ValueError("Occurrence evaluation range does not match its source text.")
        if tuple(sorted(set(self.expected_entity_ids))) != self.expected_entity_ids:
            raise ValueError("Occurrence evaluation Gold entity IDs must be ordered and distinct.")
        expected_gold = (
            EventEntityGoldDisposition.POSITIVE
            if self.expected_entity_ids
            else EventEntityGoldDisposition.NEGATIVE
        )
        if self.gold_disposition is not expected_gold:
            raise ValueError("Occurrence Gold disposition drifted from its matched entities.")
        expected_unresolved = (
            self.observed_disposition is EventEntityConnectionDisposition.UNRESOLVED
        )
        if self.unresolved != expected_unresolved:
            raise ValueError("Occurrence unresolved state drifted from its disposition.")
        expected_score = _strict_occurrence_score(
            self.gold_disposition,
            self.observed_disposition,
        )
        if self.strict_score is not expected_score:
            raise ValueError("Occurrence strict score drifted from Gold and observed dispositions.")
        expected_signature = event_entity_candidate_signature(
            event_id=self.event_id,
            candidate_id=self.candidate_id,
            entity_identity=self.entity_identity,
            entity_kind=self.entity_kind,
            entity_name=self.entity_name,
            source_text_sha256=self.source_text_sha256,
            source_start=self.source_start,
            source_end=self.source_end,
            source_text=self.source_text,
        )
        if self.candidate_signature != expected_signature:
            raise ValueError("Occurrence candidate signature drifted from its exact evidence.")
        return self


class EventEntityConfusionMetrics(BaseModel):
    """One self-validating occurrence-level confusion matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    true_positive_count: Annotated[int, Field(ge=0)]
    false_positive_count: Annotated[int, Field(ge=0)]
    false_negative_count: Annotated[int, Field(ge=0)]
    true_negative_count: Annotated[int, Field(ge=0)]
    precision: Annotated[float, Field(ge=0.0, le=1.0)]
    recall: Annotated[float, Field(ge=0.0, le=1.0)]
    f1: Annotated[float, Field(ge=0.0, le=1.0)]

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        expected_precision = _ratio(
            self.true_positive_count,
            self.true_positive_count + self.false_positive_count,
        )
        expected_recall = _ratio(
            self.true_positive_count,
            self.true_positive_count + self.false_negative_count,
        )
        expected_f1 = _f1(expected_precision, expected_recall)
        if (
            self.precision != expected_precision
            or self.recall != expected_recall
            or self.f1 != expected_f1
        ):
            raise ValueError("Occurrence confusion metrics drifted from their counts.")
        return self


class ConnectionGoldSourceOccurrence(BaseModel):
    """One exact source occurrence accepted as evidence for an Event-entity connection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    source_text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_occurrence(self) -> Self:
        if self.end - self.start != len(self.source_text):
            raise ValueError("Connection Gold source occurrence range does not match its text.")
        return self


class ConnectionGoldEntity(BaseModel):
    """One reviewed Actor or Organization involved in one source-grounded Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_id: Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")]
    entity_kind: EventEntityKind
    canonical_name: Annotated[str, Field(min_length=1)]
    accepted_entity_names: tuple[Annotated[str, Field(min_length=1)], ...]
    accepted_source_occurrences: tuple[ConnectionGoldSourceOccurrence, ...]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_entity(self) -> Self:
        if not self.accepted_entity_names or len(set(self.accepted_entity_names)) != len(
            self.accepted_entity_names
        ):
            raise ValueError("Connection Gold accepted entity names must be nonempty and distinct.")
        occurrence_keys = tuple(
            (item.start, item.end, item.source_text) for item in self.accepted_source_occurrences
        )
        if not occurrence_keys or tuple(sorted(set(occurrence_keys))) != occurrence_keys:
            raise ValueError(
                "Connection Gold source occurrences must be nonempty, ordered, and distinct."
            )
        if self.canonical_name not in self.accepted_entity_names:
            raise ValueError("Connection Gold canonical name must be an accepted name.")
        return self


class ConnectionGoldExcludedExpression(BaseModel):
    """One exact expression that must not become an Actor or Organization candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    exclusion_id: Annotated[str, Field(pattern=r"^EGX-[0-9]{3}$")]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    source_text: Annotated[str, Field(min_length=1)]
    contextual_kind: Literal["event"]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_expression(self) -> Self:
        if self.end - self.start != len(self.source_text):
            raise ValueError("Connection Gold exclusion range does not match its source text.")
        return self


class ConnectionGoldExpectedGap(BaseModel):
    """One reviewed upstream ambiguity that must remain visible and source-exact."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    gap_id: Annotated[str, Field(pattern=r"^EGG-[0-9]{3}$")]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    source_text: Annotated[str, Field(min_length=1)]
    reason: EventEntityCandidateGapReason
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_gap(self) -> Self:
        if self.end - self.start != len(self.source_text):
            raise ValueError("Connection Gold gap range does not match its source text.")
        return self


class ConnectionGoldEvent(BaseModel):
    """Complete reviewed entity inventory for one source-grounded Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    phase: EvaluationPhase
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    event_meaning: Annotated[str, Field(min_length=1)]
    expected_entities: tuple[ConnectionGoldEntity, ...]
    excluded_actor_organization_expressions: tuple[ConnectionGoldExcludedExpression, ...] = ()
    expected_candidate_gaps: tuple[ConnectionGoldExpectedGap, ...] = ()
    review_rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        entity_ids = tuple(item.entity_id for item in self.expected_entities)
        if tuple(sorted(set(entity_ids))) != entity_ids:
            raise ValueError("Connection Gold entity IDs must be ordered and distinct.")
        meanings = tuple((item.entity_kind, item.canonical_name) for item in self.expected_entities)
        if len(set(meanings)) != len(meanings):
            raise ValueError("Connection Gold repeats an Event-entity meaning.")
        exclusion_ids = tuple(
            item.exclusion_id for item in self.excluded_actor_organization_expressions
        )
        if tuple(sorted(set(exclusion_ids))) != exclusion_ids:
            raise ValueError("Connection Gold exclusion IDs must be ordered and distinct.")
        excluded_occurrences = tuple(
            (item.start, item.end, item.source_text)
            for item in self.excluded_actor_organization_expressions
        )
        if len(set(excluded_occurrences)) != len(excluded_occurrences):
            raise ValueError("Connection Gold repeats an excluded source occurrence.")
        gap_ids = tuple(item.gap_id for item in self.expected_candidate_gaps)
        if tuple(sorted(set(gap_ids))) != gap_ids:
            raise ValueError("Connection Gold expected gap IDs must be ordered and distinct.")
        gap_ranges = tuple(
            (item.start, item.end, item.source_text) for item in self.expected_candidate_gaps
        )
        if len(set(gap_ranges)) != len(gap_ranges):
            raise ValueError("Connection Gold repeats an expected candidate gap.")
        positive_occurrences = {
            (occurrence.start, occurrence.end, occurrence.source_text)
            for entity in self.expected_entities
            for occurrence in entity.accepted_source_occurrences
        }
        if positive_occurrences & set(excluded_occurrences):
            raise ValueError("One Gold occurrence cannot be both positive and excluded.")
        return self


class ConnectionGoldCatalog(BaseModel):
    """Human-reviewed 20/20 Event-entity oracle."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_event_entity_connection_gold_v2"] = (
        "hsq_event_entity_connection_gold_v2"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    review_status: Literal["proposed", "approved"]
    trigger_gold_path: Annotated[str, Field(min_length=1)]
    trigger_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_grounded_gold_path: Annotated[str, Field(min_length=1)]
    source_grounded_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    events: tuple[ConnectionGoldEvent, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        if len(self.events) != 40:
            raise ValueError("Connection Gold requires exactly forty Events.")
        event_ids = tuple(item.event_id for item in self.events)
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("Connection Gold repeats an Event.")
        phases: tuple[EvaluationPhase, ...] = ("development", "validation")
        if any(sum(item.phase == phase for item in self.events) != 20 for phase in phases):
            raise ValueError("Connection Gold requires twenty Events per phase.")
        entity_ids = tuple(
            entity.entity_id for event in self.events for entity in event.expected_entities
        )
        if len(set(entity_ids)) != len(entity_ids):
            raise ValueError("Connection Gold entity item IDs must be globally distinct.")
        exclusion_ids = tuple(
            exclusion.exclusion_id
            for event in self.events
            for exclusion in event.excluded_actor_organization_expressions
        )
        if len(set(exclusion_ids)) != len(exclusion_ids):
            raise ValueError("Connection Gold exclusion IDs must be globally distinct.")
        expected_gap_ids = tuple(
            gap.gap_id for event in self.events for gap in event.expected_candidate_gaps
        )
        if len(set(expected_gap_ids)) != len(expected_gap_ids):
            raise ValueError("Connection Gold expected gap IDs must be globally distinct.")
        return self


class EventEntityExperimentInput(BaseModel):
    """Immutable prepared input for one Gold Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: EvaluationPhase
    gold_event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    source_id: Annotated[str, Field(min_length=1)]
    document_id: Annotated[str, Field(min_length=1)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    source_segment_label: Annotated[str, Field(min_length=1)]
    source_text: Annotated[str, Field(min_length=1)]
    event_semantics_preview_id: Annotated[str, Field(pattern=r"^hsp_[a-f0-9]{24}$")]
    event_semantics_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    trigger: EventTriggerDraft
    event: SourceGroundedEventDraft
    candidate_selection: EventEntityCandidateSelection
    linguistic_evidence: EventEntityLinguisticEvidence

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.event.source_text_sha256:
            raise ValueError("Prepared connection input SourceSegment digest does not match.")
        if (
            self.trigger.id != self.event.trigger_id
            or self.trigger.source_segment_id != self.event.source_segment_id
            or self.trigger.source_text_sha256 != self.event.source_text_sha256
            or self.trigger.text != self.event.expression_text
            or self.trigger.head_text != self.event.head_text
            or self.trigger.end > len(self.source_text)
            or self.trigger.head_end > len(self.source_text)
            or self.source_text[self.trigger.start : self.trigger.end] != self.trigger.text
            or self.source_text[self.trigger.head_start : self.trigger.head_end]
            != self.trigger.head_text
        ):
            raise ValueError("Prepared connection trigger does not match its Event source.")
        if (
            self.linguistic_evidence.source_segment_id != self.event.source_segment_id
            or self.linguistic_evidence.source_text_sha256 != self.event.source_text_sha256
        ):
            raise ValueError("Prepared connection linguistic evidence does not match its Event.")
        if any(
            item.source_span.source_segment_id != self.event.source_segment_id
            or item.source_span.source_text_sha256 != self.event.source_text_sha256
            or item.source_span.end > len(self.source_text)
            or self.source_text[item.source_span.start : item.source_span.end]
            != item.source_span.text
            for item in self.candidate_selection.mentions
        ):
            raise ValueError("Prepared connection mention does not match its Event source.")
        if any(
            item.source_segment_id != self.event.source_segment_id
            or item.source_text_sha256 != self.event.source_text_sha256
            or item.mention_end > len(self.source_text)
            or self.source_text[item.mention_start : item.mention_end] != item.mention_text
            for item in self.candidate_selection.gaps
        ):
            raise ValueError("Prepared connection gap does not match its Event source.")
        if any(
            item.source_grounded_event_id != self.event.id
            or item.event_mention_id != self.event.mention.id
            or item.event_expression_end > len(self.source_text)
            or self.source_text[item.event_expression_start : item.event_expression_end]
            != self.event.expression_text
            for item in self.candidate_selection.gap_dependencies
        ):
            raise ValueError("Prepared connection gap dependency does not match its Event.")
        return self


class EventEntityCaseEvaluation(BaseModel):
    """Exact expected-versus-observed result for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    occurrences: tuple[EventEntityOccurrenceEvaluation, ...]
    expected_entity_ids: tuple[str, ...]
    excluded_expression_ids: tuple[str, ...]
    candidate_available_entity_ids: tuple[str, ...]
    candidate_missing_entity_ids: tuple[str, ...]
    matched_entity_ids: tuple[str, ...]
    missing_entity_ids: tuple[str, ...]
    false_negative_entity_ids: tuple[str, ...]
    extra_draft_ids: tuple[str, ...]
    unresolved_candidate_ids: tuple[str, ...]
    expected_gap_ids: tuple[str, ...]
    matched_expected_gap_ids: tuple[str, ...]
    missing_expected_gap_ids: tuple[str, ...]
    candidate_gap_ids: tuple[str, ...]
    unexpected_candidate_gap_ids: tuple[str, ...]
    violated_exclusion_ids: tuple[str, ...]
    candidate_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    exact_source_mapping: bool
    semantic_result: tuple[str, ...]
    passed: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        for label, values in (
            ("expected entity IDs", self.expected_entity_ids),
            ("excluded expression IDs", self.excluded_expression_ids),
            ("candidate available entity IDs", self.candidate_available_entity_ids),
            ("candidate missing entity IDs", self.candidate_missing_entity_ids),
            ("matched entity IDs", self.matched_entity_ids),
            ("missing entity IDs", self.missing_entity_ids),
            ("false negative entity IDs", self.false_negative_entity_ids),
            ("extra draft IDs", self.extra_draft_ids),
            ("unresolved candidate IDs", self.unresolved_candidate_ids),
            ("expected gap IDs", self.expected_gap_ids),
            ("matched expected gap IDs", self.matched_expected_gap_ids),
            ("missing expected gap IDs", self.missing_expected_gap_ids),
            ("candidate gap IDs", self.candidate_gap_ids),
            ("unexpected candidate gap IDs", self.unexpected_candidate_gap_ids),
            ("violated exclusion IDs", self.violated_exclusion_ids),
            ("semantic result", self.semantic_result),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"Connection evaluation {label} must be ordered and distinct.")
        if tuple(sorted(self.occurrences, key=lambda item: item.candidate_id)) != self.occurrences:
            raise ValueError("Connection evaluation occurrences must use candidate order.")
        if len({item.candidate_id for item in self.occurrences}) != len(self.occurrences):
            raise ValueError("Connection evaluation repeats a candidate occurrence.")
        if any(item.event_id != self.event_id for item in self.occurrences):
            raise ValueError("Connection evaluation contains an occurrence from another Event.")
        if self.candidate_count != len(self.occurrences):
            raise ValueError("Connection candidate count drifted from its occurrence rows.")
        observed_unresolved = tuple(
            item.candidate_id for item in self.occurrences if item.unresolved
        )
        if self.unresolved_candidate_ids != observed_unresolved:
            raise ValueError("Connection unresolved IDs drifted from its occurrence rows.")
        occurrence_available = {
            entity_id for item in self.occurrences for entity_id in item.expected_entity_ids
        }
        occurrence_matched = {
            entity_id
            for item in self.occurrences
            if item.strict_score is EventEntityOccurrenceScore.TRUE_POSITIVE
            for entity_id in item.expected_entity_ids
        }
        if occurrence_available != set(self.candidate_available_entity_ids):
            raise ValueError("Connection candidate availability drifted from occurrence Gold.")
        if occurrence_matched != set(self.matched_entity_ids):
            raise ValueError("Connection matched entities drifted from occurrence scores.")
        if sum(
            item.strict_score is EventEntityOccurrenceScore.FALSE_POSITIVE
            for item in self.occurrences
        ) != len(self.extra_draft_ids):
            raise ValueError("Connection extra drafts drifted from occurrence false positives.")
        if set(self.expected_entity_ids) != set(self.matched_entity_ids) | set(
            self.missing_entity_ids
        ):
            raise ValueError("Connection evaluation does not partition expected entities.")
        if set(self.expected_entity_ids) != set(self.candidate_available_entity_ids) | set(
            self.candidate_missing_entity_ids
        ):
            raise ValueError("Connection evaluation does not partition candidate availability.")
        if not set(self.false_negative_entity_ids).issubset(
            set(self.candidate_available_entity_ids) & set(self.missing_entity_ids)
        ):
            raise ValueError("Connection false negatives do not match candidate evidence.")
        if set(self.expected_gap_ids) != set(self.matched_expected_gap_ids) | set(
            self.missing_expected_gap_ids
        ):
            raise ValueError("Connection evaluation does not partition expected gaps.")
        if not set(self.unexpected_candidate_gap_ids).issubset(self.candidate_gap_ids):
            raise ValueError("Connection unexpected gaps are absent from candidate gaps.")
        expected_pass = (
            not (
                self.missing_entity_ids
                or self.extra_draft_ids
                or self.unresolved_candidate_ids
                or self.missing_expected_gap_ids
                or self.unexpected_candidate_gap_ids
                or self.violated_exclusion_ids
            )
            and self.exact_source_mapping
        )
        if self.passed != expected_pass:
            raise ValueError("Connection evaluation pass state does not match its evidence.")
        return self


class EventEntityCandidateAvailability(BaseModel):
    """Exact pre-model candidate coverage for one Gold Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    expected_entity_ids: tuple[str, ...]
    excluded_expression_ids: tuple[str, ...]
    available_entity_ids: tuple[str, ...]
    missing_entity_ids: tuple[str, ...]
    model_routable_entity_ids: tuple[str, ...]
    deterministically_rejected_entity_ids: tuple[str, ...]
    expected_gap_ids: tuple[str, ...]
    matched_expected_gap_ids: tuple[str, ...]
    missing_expected_gap_ids: tuple[str, ...]
    candidate_gap_ids: tuple[str, ...]
    unexpected_candidate_gap_ids: tuple[str, ...]
    violated_exclusion_ids: tuple[str, ...]
    candidate_count: Annotated[int, Field(ge=0)]
    model_candidate_count: Annotated[int, Field(ge=0)]
    deterministic_candidate_count: Annotated[int, Field(ge=0)]
    candidate_inventory: tuple[str, ...]
    route_inventory: tuple[str, ...]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("expected entity IDs", self.expected_entity_ids),
            ("excluded expression IDs", self.excluded_expression_ids),
            ("available entity IDs", self.available_entity_ids),
            ("missing entity IDs", self.missing_entity_ids),
            ("model-routable entity IDs", self.model_routable_entity_ids),
            (
                "deterministically rejected entity IDs",
                self.deterministically_rejected_entity_ids,
            ),
            ("expected gap IDs", self.expected_gap_ids),
            ("matched expected gap IDs", self.matched_expected_gap_ids),
            ("missing expected gap IDs", self.missing_expected_gap_ids),
            ("candidate gap IDs", self.candidate_gap_ids),
            ("unexpected candidate gap IDs", self.unexpected_candidate_gap_ids),
            ("violated exclusion IDs", self.violated_exclusion_ids),
            ("candidate inventory", self.candidate_inventory),
            ("route inventory", self.route_inventory),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"Connection preflight {label} must be ordered and distinct.")
        if set(self.expected_entity_ids) != set(self.available_entity_ids) | set(
            self.missing_entity_ids
        ):
            raise ValueError("Connection preflight does not partition expected entities.")
        if set(self.available_entity_ids) != set(self.model_routable_entity_ids) | set(
            self.deterministically_rejected_entity_ids
        ) or set(self.model_routable_entity_ids) & set(self.deterministically_rejected_entity_ids):
            raise ValueError("Connection preflight does not partition available entity routes.")
        if self.model_candidate_count + self.deterministic_candidate_count != self.candidate_count:
            raise ValueError("Connection preflight candidate-route counts do not partition input.")
        if set(self.expected_gap_ids) != set(self.matched_expected_gap_ids) | set(
            self.missing_expected_gap_ids
        ):
            raise ValueError("Connection preflight does not partition expected gaps.")
        if not set(self.unexpected_candidate_gap_ids).issubset(self.candidate_gap_ids):
            raise ValueError("Connection preflight unexpected gaps are absent from candidate gaps.")
        expected_pass = not (
            self.missing_entity_ids
            or self.deterministically_rejected_entity_ids
            or self.missing_expected_gap_ids
            or self.unexpected_candidate_gap_ids
            or self.violated_exclusion_ids
        )
        if self.passed != expected_pass:
            raise ValueError("Connection preflight pass state does not match its evidence.")
        return self


class EventEntityCandidatePreflightReport(BaseModel):
    """Complete pre-model upstream suitability report for one 20-Event phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_event_entity_candidate_preflight_v2"] = (
        "hsq_event_entity_candidate_preflight_v2"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    gold_review_status: Literal["proposed", "approved"]
    phase: EvaluationPhase
    event_count: Literal[20]
    expected_entity_count: Annotated[int, Field(ge=0)]
    excluded_expression_count: Annotated[int, Field(ge=0)]
    available_entity_count: Annotated[int, Field(ge=0)]
    missing_entity_count: Annotated[int, Field(ge=0)]
    model_routable_entity_count: Annotated[int, Field(ge=0)]
    deterministically_rejected_entity_count: Annotated[int, Field(ge=0)]
    candidate_count: Annotated[int, Field(ge=0)]
    model_candidate_count: Annotated[int, Field(ge=0)]
    deterministic_candidate_count: Annotated[int, Field(ge=0)]
    expected_candidate_gap_count: Annotated[int, Field(ge=0)]
    matched_expected_candidate_gap_count: Annotated[int, Field(ge=0)]
    missing_expected_candidate_gap_count: Annotated[int, Field(ge=0)]
    candidate_gap_count: Annotated[int, Field(ge=0)]
    unexpected_candidate_gap_count: Annotated[int, Field(ge=0)]
    violated_exclusion_count: Annotated[int, Field(ge=0)]
    passed: bool
    events: tuple[EventEntityCandidateAvailability, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if len(self.events) != self.event_count:
            raise ValueError("Connection preflight requires twenty Event results.")
        if tuple(sorted(self.events, key=lambda item: item.event_id)) != self.events:
            raise ValueError("Connection preflight Events must be ordered.")
        expected_totals = {
            "expected_entity_count": sum(len(item.expected_entity_ids) for item in self.events),
            "excluded_expression_count": sum(
                len(item.excluded_expression_ids) for item in self.events
            ),
            "available_entity_count": sum(len(item.available_entity_ids) for item in self.events),
            "missing_entity_count": sum(len(item.missing_entity_ids) for item in self.events),
            "model_routable_entity_count": sum(
                len(item.model_routable_entity_ids) for item in self.events
            ),
            "deterministically_rejected_entity_count": sum(
                len(item.deterministically_rejected_entity_ids) for item in self.events
            ),
            "candidate_count": sum(item.candidate_count for item in self.events),
            "model_candidate_count": sum(item.model_candidate_count for item in self.events),
            "deterministic_candidate_count": sum(
                item.deterministic_candidate_count for item in self.events
            ),
            "expected_candidate_gap_count": sum(len(item.expected_gap_ids) for item in self.events),
            "matched_expected_candidate_gap_count": sum(
                len(item.matched_expected_gap_ids) for item in self.events
            ),
            "missing_expected_candidate_gap_count": sum(
                len(item.missing_expected_gap_ids) for item in self.events
            ),
            "candidate_gap_count": sum(len(item.candidate_gap_ids) for item in self.events),
            "unexpected_candidate_gap_count": sum(
                len(item.unexpected_candidate_gap_ids) for item in self.events
            ),
            "violated_exclusion_count": sum(
                len(item.violated_exclusion_ids) for item in self.events
            ),
        }
        for field_name, expected in expected_totals.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"Connection preflight {field_name} drifted from its Events.")
        if self.passed != all(item.passed for item in self.events):
            raise ValueError("Connection preflight pass state drifted from its Events.")
        return self


def event_entity_preparation_status(
    *,
    gold_review_status: Literal["proposed", "approved"],
    preflight_passed: bool,
) -> EventEntityPreparationStatus:
    """Select the only valid pre-model terminal or ready state."""
    if gold_review_status != "approved":
        return "gold_review_required"
    if not preflight_passed:
        return "upstream_blocked"
    return "prepared"


class EventEntityPhaseReport(BaseModel):
    """One repetition over one frozen Gold phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_event_entity_connection_report_v2"] = (
        "hsq_event_entity_connection_report_v2"
    )
    scoring_policy_id: Literal["event_entity_occurrence_strict_v1"] = (
        "event_entity_occurrence_strict_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    phase: EvaluationPhase
    repetition: Annotated[int, Field(ge=1)]
    event_count: Literal[20]
    occurrence_count: Annotated[int, Field(ge=0)]
    candidate_inventory_sha256: Annotated[str, Field(pattern=_SHA256)]
    strict_metrics: EventEntityConfusionMetrics
    connected_sensitivity_metrics: EventEntityConfusionMetrics
    passed_event_count: Annotated[int, Field(ge=0, le=20)]
    expected_entity_count: Annotated[int, Field(ge=0)]
    excluded_expression_count: Annotated[int, Field(ge=0)]
    matched_entity_count: Annotated[int, Field(ge=0)]
    missing_entity_count: Annotated[int, Field(ge=0)]
    candidate_available_entity_count: Annotated[int, Field(ge=0)]
    candidate_missing_entity_count: Annotated[int, Field(ge=0)]
    false_negative_entity_count: Annotated[int, Field(ge=0)]
    extra_connection_count: Annotated[int, Field(ge=0)]
    unresolved_connection_count: Annotated[int, Field(ge=0)]
    expected_candidate_gap_count: Annotated[int, Field(ge=0)]
    matched_expected_candidate_gap_count: Annotated[int, Field(ge=0)]
    missing_expected_candidate_gap_count: Annotated[int, Field(ge=0)]
    candidate_gap_count: Annotated[int, Field(ge=0)]
    unexpected_candidate_gap_count: Annotated[int, Field(ge=0)]
    violated_exclusion_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    model_elapsed_milliseconds: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    passed: bool
    events: tuple[EventEntityCaseEvaluation, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if len(self.events) != 20:
            raise ValueError("Connection report requires twenty Event results.")
        if tuple(sorted(self.events, key=lambda item: item.event_id)) != self.events:
            raise ValueError("Connection report Events must be ordered.")
        occurrences = tuple(item for event in self.events for item in event.occurrences)
        if self.occurrence_count != len(occurrences):
            raise ValueError("Connection report occurrence count drifted from its Events.")
        if self.candidate_inventory_sha256 != _candidate_inventory_sha256(occurrences):
            raise ValueError("Connection report candidate inventory digest drifted.")
        if self.strict_metrics != _confusion_metrics(occurrences, unresolved_as_connected=False):
            raise ValueError("Connection report strict metrics drifted from its occurrences.")
        if self.connected_sensitivity_metrics != _confusion_metrics(
            occurrences,
            unresolved_as_connected=True,
        ):
            raise ValueError("Connection report sensitivity metrics drifted from its occurrences.")
        totals = {
            "passed_event_count": sum(item.passed for item in self.events),
            "expected_entity_count": sum(len(item.expected_entity_ids) for item in self.events),
            "excluded_expression_count": sum(
                len(item.excluded_expression_ids) for item in self.events
            ),
            "matched_entity_count": sum(len(item.matched_entity_ids) for item in self.events),
            "missing_entity_count": sum(len(item.missing_entity_ids) for item in self.events),
            "candidate_available_entity_count": sum(
                len(item.candidate_available_entity_ids) for item in self.events
            ),
            "candidate_missing_entity_count": sum(
                len(item.candidate_missing_entity_ids) for item in self.events
            ),
            "false_negative_entity_count": sum(
                len(item.false_negative_entity_ids) for item in self.events
            ),
            "extra_connection_count": sum(len(item.extra_draft_ids) for item in self.events),
            "unresolved_connection_count": sum(
                len(item.unresolved_candidate_ids) for item in self.events
            ),
            "expected_candidate_gap_count": sum(len(item.expected_gap_ids) for item in self.events),
            "matched_expected_candidate_gap_count": sum(
                len(item.matched_expected_gap_ids) for item in self.events
            ),
            "missing_expected_candidate_gap_count": sum(
                len(item.missing_expected_gap_ids) for item in self.events
            ),
            "candidate_gap_count": sum(len(item.candidate_gap_ids) for item in self.events),
            "unexpected_candidate_gap_count": sum(
                len(item.unexpected_candidate_gap_ids) for item in self.events
            ),
            "violated_exclusion_count": sum(
                len(item.violated_exclusion_ids) for item in self.events
            ),
            "model_execution_count": sum(item.model_execution_count for item in self.events),
        }
        for field_name, expected in totals.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"Connection report {field_name} drifted from its Events.")
        if self.result_fingerprint != _result_fingerprint(
            catalog_sha256=self.catalog_sha256,
            scoring_policy_id=self.scoring_policy_id,
            events=self.events,
        ):
            raise ValueError("Connection report fingerprint drifted from its semantic results.")
        if self.passed != (self.passed_event_count == self.event_count):
            raise ValueError("Connection report pass state drifted from its Events.")
        return self


def load_connection_gold_catalog(
    path: Path,
    *,
    repository_root: Path,
    require_approved: bool,
) -> tuple[
    ConnectionGoldCatalog,
    SourceGroundedEventGoldCatalog,
    TriggerGoldCatalog,
]:
    """Load Connection Gold and validate both immutable parent bindings."""
    payload = path.read_bytes()
    catalog = ConnectionGoldCatalog.model_validate_json(payload)
    if require_approved and catalog.review_status != "approved":
        raise ValueError("Connection Gold requires human approval before validation.")
    trigger_path = _bound_repository_path(repository_root, catalog.trigger_gold_path)
    grounded_path = _bound_repository_path(repository_root, catalog.source_grounded_gold_path)
    trigger_payload = trigger_path.read_bytes()
    if hashlib.sha256(trigger_payload).hexdigest() != catalog.trigger_gold_sha256:
        raise ValueError("Connection Gold Trigger Gold digest drifted.")
    trigger = TriggerGoldCatalog.model_validate_json(trigger_payload)
    grounded_payload = grounded_path.read_bytes()
    if hashlib.sha256(grounded_payload).hexdigest() != catalog.source_grounded_gold_sha256:
        raise ValueError("Connection Gold source-grounded Gold digest drifted.")
    grounded = SourceGroundedEventGoldCatalog.model_validate_json(grounded_payload)
    grounded_items = {
        item.event_id: (item.phase, item.source_text_sha256, item.expected_review_outcome)
        for item in grounded.items
    }
    trigger_contract_by_event = {
        event.event_id: (segment.source_text, event.meaning)
        for segment in trigger.segments
        for event in segment.events
    }
    for item in catalog.events:
        if grounded_items.get(item.event_id) != (
            item.phase,
            item.source_text_sha256,
            "approved",
        ):
            raise ValueError("Connection Gold selects an unapproved or changed Event.")
        source_text, event_meaning = trigger_contract_by_event[item.event_id]
        if item.event_meaning != event_meaning:
            raise ValueError("Connection Gold Event meaning drifted from Trigger Gold.")
        if any(
            occurrence.end > len(source_text)
            or source_text[occurrence.start : occurrence.end] != occurrence.source_text
            for entity in item.expected_entities
            for occurrence in entity.accepted_source_occurrences
        ):
            raise ValueError("Connection Gold source occurrence does not replay its SourceSegment.")
        if any(
            exclusion.end > len(source_text)
            or source_text[exclusion.start : exclusion.end] != exclusion.source_text
            for exclusion in item.excluded_actor_organization_expressions
        ):
            raise ValueError("Connection Gold exclusion does not replay its SourceSegment.")
        if any(
            gap.end > len(source_text) or source_text[gap.start : gap.end] != gap.source_text
            for gap in item.expected_candidate_gaps
        ):
            raise ValueError("Connection Gold expected gap does not replay its SourceSegment.")
    return catalog, grounded, trigger


def evaluate_event_entity_case(
    gold: ConnectionGoldEvent,
    prepared: EventEntityExperimentInput,
    preview: EventEntityConnectionPreview,
) -> EventEntityCaseEvaluation:
    """Match positive drafts to Gold while treating every other candidate as negative."""
    if prepared.gold_event_id != gold.event_id or prepared.phase != gold.phase:
        raise ValueError("Connection result belongs to another Gold Event.")
    if (
        preview.parent_preview_id != prepared.event_semantics_preview_id
        or preview.parent_preview_sha256 != prepared.event_semantics_preview_sha256
    ):
        raise ValueError("Connection result names changed parent Event evidence.")
    if any(
        item.source_grounded_event_id != prepared.event.id
        or item.source_segment_id != prepared.event.source_segment_id
        or item.source_text_sha256 != prepared.event.source_text_sha256
        for item in preview.candidates
    ):
        raise ValueError("Connection result belongs to another source-grounded Event.")
    return evaluate_event_entity_preview(
        gold,
        source_text=prepared.source_text,
        preview=preview,
    )


def evaluate_event_entity_preview(
    gold: ConnectionGoldEvent,
    *,
    source_text: str,
    preview: EventEntityConnectionPreview,
) -> EventEntityCaseEvaluation:
    """Score one typed Preview directly against raw Gold and authoritative text."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if source_digest != gold.source_text_sha256:
        raise ValueError("Connection measurement SourceSegment digest drifted from Gold.")
    if any(item.source_text_sha256 != source_digest for item in preview.candidates):
        raise ValueError("Connection measurement candidate belongs to another SourceSegment.")
    decision_by_candidate = {item.candidate_id: item for item in preview.decisions}
    if set(decision_by_candidate) != {item.id for item in preview.candidates}:
        raise ValueError("Connection result lacks one decision per candidate occurrence.")
    occurrence_evaluations = tuple(
        sorted(
            (
                _evaluate_candidate_occurrence(
                    event_id=gold.event_id,
                    source_text=source_text,
                    gold_entities=gold.expected_entities,
                    candidate=candidate,
                    disposition=decision_by_candidate[candidate.id].disposition,
                )
                for candidate in preview.candidates
            ),
            key=lambda item: item.candidate_id,
        )
    )
    draft_by_id = {item.id: item for item in preview.drafts}
    unmatched = set(draft_by_id)
    matched: list[str] = []
    missing: list[str] = []
    candidate_available: list[str] = []
    candidate_missing: list[str] = []
    false_negatives: list[str] = []
    for expected in gold.expected_entities:
        candidate_matches = tuple(
            candidate
            for candidate in preview.candidates
            if candidate.entity_kind is expected.entity_kind
            and candidate.entity_name in expected.accepted_entity_names
            and _candidate_has_accepted_source(candidate, expected)
        )
        if candidate_matches:
            candidate_available.append(expected.entity_id)
        else:
            candidate_missing.append(expected.entity_id)
        matches = tuple(
            draft
            for draft in preview.drafts
            if draft.id in unmatched
            and draft.entity_kind is expected.entity_kind
            and draft.entity_name in expected.accepted_entity_names
            and _draft_has_accepted_source(preview, draft.candidate_id, expected)
        )
        if matches:
            matched.append(expected.entity_id)
            unmatched.difference_update(item.id for item in matches)
        else:
            missing.append(expected.entity_id)
            if candidate_matches and not matches:
                false_negatives.append(expected.entity_id)
    unresolved = tuple(
        sorted(
            item.candidate_id
            for item in preview.decisions
            if item.disposition is EventEntityConnectionDisposition.UNRESOLVED
        )
    )
    matched_expected_gaps, missing_expected_gaps, unexpected_gaps = _match_expected_candidate_gaps(
        gold.expected_candidate_gaps,
        preview.candidate_gaps,
    )
    violated_exclusions = tuple(
        sorted(
            exclusion.exclusion_id
            for exclusion in gold.excluded_actor_organization_expressions
            if any(
                _candidate_has_excluded_source(candidate, exclusion)
                for candidate in preview.candidates
            )
        )
    )
    exact_source = all(
        span.end <= len(source_text) and source_text[span.start : span.end] == span.text
        for candidate in preview.candidates
        for span in candidate.source_spans
    )
    semantic_result = tuple(
        sorted(
            {
                f"{item.entity_kind.value}:{item.entity_name}"
                for item in preview.identity_connections
                if item.disposition is EventEntityConnectionDisposition.CONNECTED
            }
        )
    )
    return EventEntityCaseEvaluation(
        event_id=gold.event_id,
        occurrences=occurrence_evaluations,
        expected_entity_ids=tuple(sorted(item.entity_id for item in gold.expected_entities)),
        excluded_expression_ids=tuple(
            sorted(item.exclusion_id for item in gold.excluded_actor_organization_expressions)
        ),
        candidate_available_entity_ids=tuple(sorted(candidate_available)),
        candidate_missing_entity_ids=tuple(sorted(candidate_missing)),
        matched_entity_ids=tuple(sorted(matched)),
        missing_entity_ids=tuple(sorted(missing)),
        false_negative_entity_ids=tuple(sorted(false_negatives)),
        extra_draft_ids=tuple(sorted(unmatched)),
        unresolved_candidate_ids=unresolved,
        expected_gap_ids=tuple(sorted(item.gap_id for item in gold.expected_candidate_gaps)),
        matched_expected_gap_ids=matched_expected_gaps,
        missing_expected_gap_ids=missing_expected_gaps,
        candidate_gap_ids=tuple(sorted(item.id for item in preview.candidate_gaps)),
        unexpected_candidate_gap_ids=unexpected_gaps,
        violated_exclusion_ids=violated_exclusions,
        candidate_count=len(preview.candidates),
        model_execution_count=len(preview.model_run_ids),
        exact_source_mapping=exact_source,
        semantic_result=semantic_result,
        passed=not (
            missing
            or unmatched
            or unresolved
            or missing_expected_gaps
            or unexpected_gaps
            or violated_exclusions
        )
        and exact_source,
    )


def build_event_entity_phase_report(
    *,
    catalog: ConnectionGoldCatalog,
    catalog_sha256: str,
    phase: EvaluationPhase,
    repetition: int,
    evaluations: tuple[EventEntityCaseEvaluation, ...],
    model_elapsed_milliseconds: int,
) -> EventEntityPhaseReport:
    """Build one self-validating phase report from exact Event results."""
    ordered = tuple(sorted(evaluations, key=lambda item: item.event_id))
    occurrences = tuple(item for event in ordered for item in event.occurrences)
    scoring_policy_id = "event_entity_occurrence_strict_v1"
    return EventEntityPhaseReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        scoring_policy_id=scoring_policy_id,
        phase=phase,
        repetition=repetition,
        event_count=20,
        occurrence_count=len(occurrences),
        candidate_inventory_sha256=_candidate_inventory_sha256(occurrences),
        strict_metrics=_confusion_metrics(occurrences, unresolved_as_connected=False),
        connected_sensitivity_metrics=_confusion_metrics(
            occurrences,
            unresolved_as_connected=True,
        ),
        passed_event_count=sum(item.passed for item in ordered),
        expected_entity_count=sum(len(item.expected_entity_ids) for item in ordered),
        excluded_expression_count=sum(len(item.excluded_expression_ids) for item in ordered),
        matched_entity_count=sum(len(item.matched_entity_ids) for item in ordered),
        missing_entity_count=sum(len(item.missing_entity_ids) for item in ordered),
        candidate_available_entity_count=sum(
            len(item.candidate_available_entity_ids) for item in ordered
        ),
        candidate_missing_entity_count=sum(
            len(item.candidate_missing_entity_ids) for item in ordered
        ),
        false_negative_entity_count=sum(len(item.false_negative_entity_ids) for item in ordered),
        extra_connection_count=sum(len(item.extra_draft_ids) for item in ordered),
        unresolved_connection_count=sum(len(item.unresolved_candidate_ids) for item in ordered),
        expected_candidate_gap_count=sum(len(item.expected_gap_ids) for item in ordered),
        matched_expected_candidate_gap_count=sum(
            len(item.matched_expected_gap_ids) for item in ordered
        ),
        missing_expected_candidate_gap_count=sum(
            len(item.missing_expected_gap_ids) for item in ordered
        ),
        candidate_gap_count=sum(len(item.candidate_gap_ids) for item in ordered),
        unexpected_candidate_gap_count=sum(
            len(item.unexpected_candidate_gap_ids) for item in ordered
        ),
        violated_exclusion_count=sum(len(item.violated_exclusion_ids) for item in ordered),
        model_execution_count=sum(item.model_execution_count for item in ordered),
        model_elapsed_milliseconds=model_elapsed_milliseconds,
        result_fingerprint=_result_fingerprint(
            catalog_sha256=catalog_sha256,
            scoring_policy_id=scoring_policy_id,
            events=ordered,
        ),
        passed=all(item.passed for item in ordered),
        events=ordered,
    )


def build_event_entity_candidate_preflight_report(
    *,
    catalog: ConnectionGoldCatalog,
    catalog_sha256: str,
    phase: EvaluationPhase,
    inputs: tuple[EventEntityExperimentInput, ...],
) -> EventEntityCandidatePreflightReport:
    """Prove that upstream evidence can expose every Gold entity before model work."""
    gold_by_id = {item.event_id: item for item in catalog.events if item.phase == phase}
    input_by_id = {item.gold_event_id: item for item in inputs}
    if set(gold_by_id) != set(input_by_id):
        raise ValueError("Connection preflight does not cover its complete Gold phase.")
    evaluations: list[EventEntityCandidateAvailability] = []
    for event_id in sorted(gold_by_id):
        evaluations.append(
            evaluate_event_entity_candidate_availability(
                gold_by_id[event_id],
                input_by_id[event_id],
            )
        )
    events = tuple(evaluations)
    return EventEntityCandidatePreflightReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        gold_review_status=catalog.review_status,
        phase=phase,
        event_count=20,
        expected_entity_count=sum(len(item.expected_entity_ids) for item in events),
        excluded_expression_count=sum(len(item.excluded_expression_ids) for item in events),
        available_entity_count=sum(len(item.available_entity_ids) for item in events),
        missing_entity_count=sum(len(item.missing_entity_ids) for item in events),
        model_routable_entity_count=sum(len(item.model_routable_entity_ids) for item in events),
        deterministically_rejected_entity_count=sum(
            len(item.deterministically_rejected_entity_ids) for item in events
        ),
        candidate_count=sum(item.candidate_count for item in events),
        model_candidate_count=sum(item.model_candidate_count for item in events),
        deterministic_candidate_count=sum(item.deterministic_candidate_count for item in events),
        expected_candidate_gap_count=sum(len(item.expected_gap_ids) for item in events),
        matched_expected_candidate_gap_count=sum(
            len(item.matched_expected_gap_ids) for item in events
        ),
        missing_expected_candidate_gap_count=sum(
            len(item.missing_expected_gap_ids) for item in events
        ),
        candidate_gap_count=sum(len(item.candidate_gap_ids) for item in events),
        unexpected_candidate_gap_count=sum(
            len(item.unexpected_candidate_gap_ids) for item in events
        ),
        violated_exclusion_count=sum(len(item.violated_exclusion_ids) for item in events),
        passed=all(item.passed for item in events),
        events=events,
    )


def evaluate_event_entity_candidate_availability(
    gold: ConnectionGoldEvent,
    prepared: EventEntityExperimentInput,
) -> EventEntityCandidateAvailability:
    """Identify upstream recall and typing failures before model judgment."""
    if prepared.gold_event_id != gold.event_id or prepared.phase != gold.phase:
        raise ValueError("Connection preflight input belongs to another Gold Event.")
    candidates = build_event_entity_connection_candidates(
        prepared.event,
        prepared.candidate_selection.mentions,
        source_text=prepared.source_text,
    )
    routes = build_event_entity_candidate_routes(
        source_text=prepared.source_text,
        candidates=candidates,
        linguistic_evidence=prepared.linguistic_evidence,
    )
    route_by_candidate = {item.candidate_id: item for item in routes}
    available: list[str] = []
    missing: list[str] = []
    model_routable: list[str] = []
    deterministically_rejected: list[str] = []
    for expected in gold.expected_entities:
        matching_candidates = tuple(
            candidate.entity_kind == expected.entity_kind
            and candidate.entity_name in expected.accepted_entity_names
            and _candidate_has_accepted_source(candidate, expected)
            for candidate in candidates
        )
        matched_candidates = tuple(
            candidate
            for candidate, matches in zip(candidates, matching_candidates, strict=True)
            if matches
        )
        if not matched_candidates:
            missing.append(expected.entity_id)
            continue
        available.append(expected.entity_id)
        if any(
            route_by_candidate[candidate.id].route is EventEntityCandidateRouteKind.MODEL_JUDGMENT
            for candidate in matched_candidates
        ):
            model_routable.append(expected.entity_id)
        else:
            deterministically_rejected.append(expected.entity_id)
    inventory = tuple(
        sorted(
            f"{item.id}:{item.entity_kind.value}:{item.entity_name}:"
            + "|".join(span.text for span in item.source_spans)
            for item in candidates
        )
    )
    gaps = tuple(sorted(item.id for item in prepared.candidate_selection.gaps))
    route_inventory = tuple(
        sorted(
            f"{item.candidate_id}:{item.route.value}:{item.reason.value}:"
            f"{item.event_sentence_id}:{item.entity_sentence_id}"
            for item in routes
        )
    )
    matched_expected_gaps, missing_expected_gaps, unexpected_gaps = _match_expected_candidate_gaps(
        gold.expected_candidate_gaps,
        prepared.candidate_selection.gaps,
    )
    violated_exclusions = tuple(
        sorted(
            exclusion.exclusion_id
            for exclusion in gold.excluded_actor_organization_expressions
            if any(_candidate_has_excluded_source(candidate, exclusion) for candidate in candidates)
        )
    )
    return EventEntityCandidateAvailability(
        event_id=gold.event_id,
        expected_entity_ids=tuple(sorted(item.entity_id for item in gold.expected_entities)),
        excluded_expression_ids=tuple(
            sorted(item.exclusion_id for item in gold.excluded_actor_organization_expressions)
        ),
        available_entity_ids=tuple(sorted(available)),
        missing_entity_ids=tuple(sorted(missing)),
        model_routable_entity_ids=tuple(sorted(model_routable)),
        deterministically_rejected_entity_ids=tuple(sorted(deterministically_rejected)),
        expected_gap_ids=tuple(sorted(item.gap_id for item in gold.expected_candidate_gaps)),
        matched_expected_gap_ids=matched_expected_gaps,
        missing_expected_gap_ids=missing_expected_gaps,
        candidate_gap_ids=gaps,
        unexpected_candidate_gap_ids=unexpected_gaps,
        violated_exclusion_ids=violated_exclusions,
        candidate_count=len(candidates),
        model_candidate_count=sum(
            item.route is EventEntityCandidateRouteKind.MODEL_JUDGMENT for item in routes
        ),
        deterministic_candidate_count=sum(
            item.route is EventEntityCandidateRouteKind.DETERMINISTIC_NOT_CONNECTED
            for item in routes
        ),
        candidate_inventory=inventory,
        route_inventory=route_inventory,
        passed=not (
            missing
            or deterministically_rejected
            or missing_expected_gaps
            or unexpected_gaps
            or violated_exclusions
        ),
    )


def render_event_entity_candidate_preflight_review(
    report: EventEntityCandidatePreflightReport,
    catalog: ConnectionGoldCatalog,
    inputs: tuple[EventEntityExperimentInput, ...],
) -> str:
    """Render exact expected-versus-available evidence before expensive model work."""
    gold_by_id = {item.event_id: item for item in catalog.events if item.phase == report.phase}
    input_by_id = {item.gold_event_id: item for item in inputs}
    if set(gold_by_id) != {item.event_id for item in report.events} or set(input_by_id) != set(
        gold_by_id
    ):
        raise ValueError("Connection preflight review inputs do not cover its phase.")
    lines = [
        f"# Event-Entity Candidate Preflight — {report.phase}",
        "",
        f"Gold review status: `{report.gold_review_status}`",
        "",
        f"Result: `{'passed' if report.passed else 'upstream_blocked'}`",
        "",
        (
            "Expected entities available: "
            f"`{report.available_entity_count}/{report.expected_entity_count}`"
        ),
        "",
        (
            "Available entities retained for semantic judgment: "
            f"`{report.model_routable_entity_count}/{report.available_entity_count}`"
        ),
        "",
        (
            "Expected entities rejected by deterministic routing: "
            f"`{report.deterministically_rejected_entity_count}`"
        ),
        "",
        (
            "Candidate routes: "
            f"`{report.model_candidate_count}` model / "
            f"`{report.deterministic_candidate_count}` deterministic"
        ),
        "",
        (
            "Reviewed candidate gaps matched: "
            f"`{report.matched_expected_candidate_gap_count}/"
            f"{report.expected_candidate_gap_count}`"
        ),
        "",
        f"Unexpected candidate gaps: `{report.unexpected_candidate_gap_count}`",
        "",
        (
            "Contextual exclusions preserved: "
            f"`{report.excluded_expression_count - report.violated_exclusion_count}/"
            f"{report.excluded_expression_count}`"
        ),
        "",
        (
            "This report stops before Qwen. Missing entities and typed gaps belong to the "
            "upstream mention/reference boundary."
        ),
        "",
    ]
    for evaluation in report.events:
        gold = gold_by_id[evaluation.event_id]
        prepared = input_by_id[evaluation.event_id]
        expected_by_id = {item.entity_id: item for item in gold.expected_entities}
        lines.extend(
            (
                f"## {evaluation.event_id} — {'ready' if evaluation.passed else 'blocked'}",
                "",
                f"Event: {gold.event_meaning}",
                "",
                "Exact SourceSegment:",
                "",
                "> " + prepared.source_text,
                "",
                "Expected entities:",
                "",
            )
        )
        if not evaluation.expected_entity_ids:
            lines.extend(("- None.", ""))
        else:
            for entity_id in evaluation.expected_entity_ids:
                expected = expected_by_id[entity_id]
                disposition = (
                    "model-routable"
                    if entity_id in evaluation.model_routable_entity_ids
                    else (
                        "deterministically rejected"
                        if entity_id in evaluation.deterministically_rejected_entity_ids
                        else "missing"
                    )
                )
                lines.append(
                    f"- `{entity_id}` — `{expected.entity_kind.value}` — "
                    f"{expected.canonical_name} — **{disposition}**"
                )
            lines.append("")
        lines.extend(("Actual candidate inventory:", ""))
        if evaluation.candidate_inventory:
            lines.extend(f"- `{item}`" for item in evaluation.candidate_inventory)
        else:
            lines.append("- None.")
        lines.extend(("", "Exact candidate routes:", ""))
        if evaluation.route_inventory:
            lines.extend(f"- `{item}`" for item in evaluation.route_inventory)
        else:
            lines.append("- None.")
        lines.extend(("", "Typed candidate gaps:", ""))
        if evaluation.candidate_gap_ids:
            lines.extend(f"- `{item}`" for item in evaluation.candidate_gap_ids)
        else:
            lines.append("- None.")
        lines.extend(("", "Reviewed expected gaps:", ""))
        if gold.expected_candidate_gaps:
            for gap in gold.expected_candidate_gaps:
                disposition = (
                    "matched" if gap.gap_id in evaluation.matched_expected_gap_ids else "missing"
                )
                lines.append(
                    f"- `{gap.gap_id}` — `{gap.reason.value}` — "
                    f"{json.dumps(gap.source_text, ensure_ascii=False)} — **{disposition}**"
                )
        else:
            lines.append("- None.")
        lines.extend(("", "Unexpected candidate gaps:", ""))
        if evaluation.unexpected_candidate_gap_ids:
            lines.extend(f"- `{item}`" for item in evaluation.unexpected_candidate_gap_ids)
        else:
            lines.append("- None.")
        lines.extend(("", "Expected contextual exclusions:", ""))
        if gold.excluded_actor_organization_expressions:
            for exclusion in gold.excluded_actor_organization_expressions:
                disposition = (
                    "violated"
                    if exclusion.exclusion_id in evaluation.violated_exclusion_ids
                    else "preserved"
                )
                lines.append(
                    f"- `{exclusion.exclusion_id}` — "
                    f"{json.dumps(exclusion.source_text, ensure_ascii=False)} — "
                    f"`{exclusion.contextual_kind}` — **{disposition}**"
                )
        else:
            lines.append("- None.")
        lines.append("")
    return "\n".join(lines)


def render_connection_gold_review(
    catalog: ConnectionGoldCatalog,
    trigger_gold: TriggerGoldCatalog,
) -> str:
    """Render the complete proposed entity inventory for human review."""
    lines = [
        "# HSQ Event-Entity Connection Gold Review",
        "",
        f"Catalog: `{catalog.catalog_id}`",
        "",
        f"Current review status: `{catalog.review_status}`",
        "",
        "Approve only when each Event lists every involved Actor and Organization.",
        "",
        (
            "Accepted source occurrences must replay byte-for-byte at their recorded ranges in "
            "the Event's exact SourceSegment."
        ),
        "",
        "Normalized names and aliases belong in the entity-name inventory, not source evidence.",
        "",
        (
            "Entities named elsewhere in the SourceSegment but unrelated to the marked Event "
            "are negatives."
        ),
        "",
    ]
    source_by_event = {
        item.event_id: segment.source_text
        for segment in trigger_gold.segments
        for item in segment.events
    }
    for event in catalog.events:
        lines.extend(
            (
                f"## {event.event_id} — {event.phase}",
                "",
                f"Event: {event.event_meaning}",
                "",
                "Exact SourceSegment:",
                "",
                "> " + source_by_event[event.event_id],
                "",
                "Expected involved entities:",
                "",
            )
        )
        if not event.expected_entities:
            lines.extend(("- None.", ""))
        for entity in event.expected_entities:
            lines.extend(
                (
                    (
                        f"### {entity.entity_id} — {entity.entity_kind.value} — "
                        f"{entity.canonical_name}"
                    ),
                    "",
                    "Accepted exact source occurrences:",
                    "",
                    *(
                        f"- `{item.start}:{item.end}` — "
                        + json.dumps(item.source_text, ensure_ascii=False)
                        for item in entity.accepted_source_occurrences
                    ),
                    "",
                    f"Rationale: {entity.rationale}",
                    "",
                )
            )
        lines.extend(("Expected contextual exclusions:", ""))
        if not event.excluded_actor_organization_expressions:
            lines.extend(("- None.", ""))
        for exclusion in event.excluded_actor_organization_expressions:
            lines.extend(
                (
                    (
                        f"### {exclusion.exclusion_id} — not Actor/Organization — "
                        f"{exclusion.contextual_kind}"
                    ),
                    "",
                    "Exact excluded source occurrence: "
                    f"`{exclusion.start}:{exclusion.end}` — "
                    + json.dumps(exclusion.source_text, ensure_ascii=False),
                    "",
                    f"Rationale: {exclusion.rationale}",
                    "",
                )
            )
        lines.extend(("Expected typed candidate gaps:", ""))
        if not event.expected_candidate_gaps:
            lines.extend(("- None.", ""))
        for gap in event.expected_candidate_gaps:
            lines.extend(
                (
                    f"### {gap.gap_id} — {gap.reason.value}",
                    "",
                    (
                        "Exact source occurrence: "
                        f"`{gap.start}:{gap.end}` — "
                        + json.dumps(gap.source_text, ensure_ascii=False)
                    ),
                    "",
                    f"Rationale: {gap.rationale}",
                    "",
                )
            )
        lines.extend((f"Event review: `{catalog.review_status}`", ""))
    return "\n".join(lines)


def _draft_has_accepted_source(
    preview: EventEntityConnectionPreview,
    candidate_id: str,
    expected: ConnectionGoldEntity,
) -> bool:
    candidate = next(item for item in preview.candidates if item.id == candidate_id)
    return _candidate_has_accepted_source(candidate, expected)


def _candidate_has_accepted_source(
    candidate: EventEntityConnectionCandidate,
    expected: ConnectionGoldEntity,
) -> bool:
    observed = {(item.start, item.end, item.text) for item in candidate.source_spans}
    accepted = {
        (item.start, item.end, item.source_text) for item in expected.accepted_source_occurrences
    }
    return bool(observed & accepted)


def _candidate_has_excluded_source(
    candidate: EventEntityConnectionCandidate,
    exclusion: ConnectionGoldExcludedExpression,
) -> bool:
    observed = {(item.start, item.end, item.text) for item in candidate.source_spans}
    return (exclusion.start, exclusion.end, exclusion.source_text) in observed


def _match_expected_candidate_gaps(
    expected_gaps: tuple[ConnectionGoldExpectedGap, ...],
    actual_gaps: tuple[EventEntityCandidateGap, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Partition reviewed gap expectations and unexpected source-bound gaps."""
    matched_expected: list[str] = []
    used_actual: set[str] = set()
    for expected in expected_gaps:
        matches = tuple(
            actual
            for actual in actual_gaps
            if actual.mention_start == expected.start
            and actual.mention_end == expected.end
            and actual.mention_text == expected.source_text
            and actual.reason is expected.reason
        )
        if len(matches) > 1:
            raise ValueError("One expected Connection gap matches multiple actual gaps.")
        if matches:
            matched_expected.append(expected.gap_id)
            used_actual.add(matches[0].id)
    expected_ids = {item.gap_id for item in expected_gaps}
    matched_ids = set(matched_expected)
    return (
        tuple(sorted(matched_ids)),
        tuple(sorted(expected_ids - matched_ids)),
        tuple(sorted(item.id for item in actual_gaps if item.id not in used_actual)),
    )


def validate_equal_event_entity_candidate_inventories(
    reports: tuple[EventEntityPhaseReport, ...],
) -> None:
    """Reject comparisons whose arms did not judge the same exact occurrences."""
    if not reports:
        raise ValueError("Candidate inventory comparison requires at least one report.")
    phases = {item.phase for item in reports}
    if len(phases) != 1:
        raise ValueError("Candidate inventory comparison requires one evaluation phase.")
    inventories = {item.candidate_inventory_sha256 for item in reports}
    if len(inventories) != 1:
        raise ValueError("Event-entity reports contain different candidate inventories.")


def _evaluate_candidate_occurrence(
    *,
    event_id: str,
    source_text: str,
    gold_entities: tuple[ConnectionGoldEntity, ...],
    candidate: EventEntityConnectionCandidate,
    disposition: EventEntityConnectionDisposition,
) -> EventEntityOccurrenceEvaluation:
    primary = next(
        item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
    )
    if primary.end > len(source_text) or source_text[primary.start : primary.end] != primary.text:
        raise ValueError("Occurrence candidate does not replay its authoritative SourceSegment.")
    matches = tuple(
        item.entity_id
        for item in gold_entities
        if item.entity_kind is candidate.entity_kind
        and candidate.entity_name in item.accepted_entity_names
        and (primary.start, primary.end, primary.text)
        in {
            (occurrence.start, occurrence.end, occurrence.source_text)
            for occurrence in item.accepted_source_occurrences
        }
    )
    if len(matches) > 1:
        raise ValueError("One candidate occurrence matches multiple Connection Gold entities.")
    gold_disposition = (
        EventEntityGoldDisposition.POSITIVE if matches else EventEntityGoldDisposition.NEGATIVE
    )
    return EventEntityOccurrenceEvaluation(
        event_id=event_id,
        candidate_id=candidate.id,
        candidate_signature=event_entity_candidate_signature(
            event_id=event_id,
            candidate_id=candidate.id,
            entity_identity=candidate.entity_identity,
            entity_kind=candidate.entity_kind,
            entity_name=candidate.entity_name,
            source_text_sha256=candidate.source_text_sha256,
            source_start=primary.start,
            source_end=primary.end,
            source_text=primary.text,
        ),
        entity_identity=candidate.entity_identity,
        entity_kind=candidate.entity_kind,
        entity_name=candidate.entity_name,
        source_text_sha256=candidate.source_text_sha256,
        source_start=primary.start,
        source_end=primary.end,
        source_text=primary.text,
        expected_entity_ids=tuple(sorted(matches)),
        gold_disposition=gold_disposition,
        observed_disposition=disposition,
        strict_score=_strict_occurrence_score(gold_disposition, disposition),
        unresolved=disposition is EventEntityConnectionDisposition.UNRESOLVED,
    )


def event_entity_candidate_signature(
    *,
    event_id: str,
    candidate_id: str,
    entity_identity: str,
    entity_kind: EventEntityKind,
    entity_name: str,
    source_text_sha256: str,
    source_start: int,
    source_end: int,
    source_text: str,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "candidate_id": candidate_id,
                "entity_identity": entity_identity,
                "entity_kind": entity_kind.value,
                "entity_name": entity_name,
                "event_id": event_id,
                "source_end": source_end,
                "source_start": source_start,
                "source_text": source_text,
                "source_text_sha256": source_text_sha256,
            }
        ).encode()
    ).hexdigest()


def _strict_occurrence_score(
    gold_disposition: EventEntityGoldDisposition,
    observed_disposition: EventEntityConnectionDisposition,
) -> EventEntityOccurrenceScore:
    connected = observed_disposition is EventEntityConnectionDisposition.CONNECTED
    if gold_disposition is EventEntityGoldDisposition.POSITIVE:
        return (
            EventEntityOccurrenceScore.TRUE_POSITIVE
            if connected
            else EventEntityOccurrenceScore.FALSE_NEGATIVE
        )
    return (
        EventEntityOccurrenceScore.FALSE_POSITIVE
        if connected
        else EventEntityOccurrenceScore.TRUE_NEGATIVE
    )


def _confusion_metrics(
    occurrences: tuple[EventEntityOccurrenceEvaluation, ...],
    *,
    unresolved_as_connected: bool,
) -> EventEntityConfusionMetrics:
    counts = {score: 0 for score in EventEntityOccurrenceScore}
    for occurrence in occurrences:
        score = occurrence.strict_score
        if unresolved_as_connected and occurrence.unresolved:
            score = (
                EventEntityOccurrenceScore.TRUE_POSITIVE
                if occurrence.gold_disposition is EventEntityGoldDisposition.POSITIVE
                else EventEntityOccurrenceScore.FALSE_POSITIVE
            )
        counts[score] += 1
    true_positive = counts[EventEntityOccurrenceScore.TRUE_POSITIVE]
    false_positive = counts[EventEntityOccurrenceScore.FALSE_POSITIVE]
    false_negative = counts[EventEntityOccurrenceScore.FALSE_NEGATIVE]
    true_negative = counts[EventEntityOccurrenceScore.TRUE_NEGATIVE]
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return EventEntityConfusionMetrics(
        true_positive_count=true_positive,
        false_positive_count=false_positive,
        false_negative_count=false_negative,
        true_negative_count=true_negative,
        precision=precision,
        recall=recall,
        f1=_f1(precision, recall),
    )


def _candidate_inventory_sha256(
    occurrences: tuple[EventEntityOccurrenceEvaluation, ...],
) -> str:
    return hashlib.sha256(
        _canonical_json(sorted(item.candidate_signature for item in occurrences)).encode()
    ).hexdigest()


def _result_fingerprint(
    *,
    catalog_sha256: str,
    scoring_policy_id: str,
    events: tuple[EventEntityCaseEvaluation, ...],
) -> str:
    payload = {
        "catalog_sha256": catalog_sha256,
        "events": [item.model_dump(mode="json") for item in events],
        "scoring_policy_id": scoring_policy_id,
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _bound_repository_path(repository_root: Path, value: str) -> Path:
    root = repository_root.resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Connection Gold parent path leaves the repository.")
    return path


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
