"""Gold contracts and pure evaluation for Event-entity connection experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self

from kotekomi_application import (
    EventEntityCandidateSelection,
    EventEntityConnectionCandidate,
    EventEntityConnectionDisposition,
    EventEntityConnectionPreview,
    EventEntityKind,
    SourceGroundedEventDraft,
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


class ConnectionGoldEntity(BaseModel):
    """One reviewed Actor or Organization involved in one source-grounded Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_id: Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")]
    entity_kind: EventEntityKind
    canonical_name: Annotated[str, Field(min_length=1)]
    accepted_entity_names: tuple[Annotated[str, Field(min_length=1)], ...]
    accepted_source_texts: tuple[Annotated[str, Field(min_length=1)], ...]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_entity(self) -> Self:
        for label, values in (
            ("accepted entity names", self.accepted_entity_names),
            ("accepted source texts", self.accepted_source_texts),
        ):
            if not values or len(set(values)) != len(values):
                raise ValueError(f"Connection Gold {label} must be nonempty and distinct.")
        if self.canonical_name not in self.accepted_entity_names:
            raise ValueError("Connection Gold canonical name must be an accepted name.")
        return self


class ConnectionGoldExcludedExpression(BaseModel):
    """One exact expression that must not become an Actor or Organization candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    exclusion_id: Annotated[str, Field(pattern=r"^EGX-[0-9]{3}$")]
    source_text: Annotated[str, Field(min_length=1)]
    contextual_kind: Literal["event"]
    rationale: Annotated[str, Field(min_length=1)]


class ConnectionGoldEvent(BaseModel):
    """Complete reviewed entity inventory for one source-grounded Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    phase: EvaluationPhase
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    event_meaning: Annotated[str, Field(min_length=1)]
    expected_entities: tuple[ConnectionGoldEntity, ...]
    excluded_actor_organization_expressions: tuple[ConnectionGoldExcludedExpression, ...] = ()
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
        excluded_texts = tuple(
            item.source_text for item in self.excluded_actor_organization_expressions
        )
        if len(set(excluded_texts)) != len(excluded_texts):
            raise ValueError("Connection Gold repeats an excluded source expression.")
        positive_texts = {
            source_text
            for entity in self.expected_entities
            for source_text in entity.accepted_source_texts
        }
        if positive_texts & set(excluded_texts):
            raise ValueError("One Gold expression cannot be both positive and excluded.")
        return self


class ConnectionGoldCatalog(BaseModel):
    """Human-reviewed 20/20 Event-entity oracle."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_event_entity_connection_gold_v1"] = (
        "hsq_event_entity_connection_gold_v1"
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
    event: SourceGroundedEventDraft
    candidate_selection: EventEntityCandidateSelection

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.event.source_text_sha256:
            raise ValueError("Prepared connection input SourceSegment digest does not match.")
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
        return self


class EventEntityCaseEvaluation(BaseModel):
    """Exact expected-versus-observed result for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    expected_entity_ids: tuple[str, ...]
    excluded_expression_ids: tuple[str, ...]
    candidate_available_entity_ids: tuple[str, ...]
    candidate_missing_entity_ids: tuple[str, ...]
    matched_entity_ids: tuple[str, ...]
    missing_entity_ids: tuple[str, ...]
    false_negative_entity_ids: tuple[str, ...]
    extra_draft_ids: tuple[str, ...]
    unresolved_candidate_ids: tuple[str, ...]
    candidate_gap_ids: tuple[str, ...]
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
            ("candidate gap IDs", self.candidate_gap_ids),
            ("violated exclusion IDs", self.violated_exclusion_ids),
            ("semantic result", self.semantic_result),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"Connection evaluation {label} must be ordered and distinct.")
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
        expected_pass = (
            not (
                self.missing_entity_ids
                or self.extra_draft_ids
                or self.unresolved_candidate_ids
                or self.candidate_gap_ids
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
    candidate_gap_ids: tuple[str, ...]
    violated_exclusion_ids: tuple[str, ...]
    candidate_count: Annotated[int, Field(ge=0)]
    candidate_inventory: tuple[str, ...]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("expected entity IDs", self.expected_entity_ids),
            ("excluded expression IDs", self.excluded_expression_ids),
            ("available entity IDs", self.available_entity_ids),
            ("missing entity IDs", self.missing_entity_ids),
            ("candidate gap IDs", self.candidate_gap_ids),
            ("violated exclusion IDs", self.violated_exclusion_ids),
            ("candidate inventory", self.candidate_inventory),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"Connection preflight {label} must be ordered and distinct.")
        if set(self.expected_entity_ids) != set(self.available_entity_ids) | set(
            self.missing_entity_ids
        ):
            raise ValueError("Connection preflight does not partition expected entities.")
        expected_pass = not (
            self.missing_entity_ids or self.candidate_gap_ids or self.violated_exclusion_ids
        )
        if self.passed != expected_pass:
            raise ValueError("Connection preflight pass state does not match its evidence.")
        return self


class EventEntityCandidatePreflightReport(BaseModel):
    """Complete pre-model upstream suitability report for one 20-Event phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_event_entity_candidate_preflight_v1"] = (
        "hsq_event_entity_candidate_preflight_v1"
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
    candidate_count: Annotated[int, Field(ge=0)]
    candidate_gap_count: Annotated[int, Field(ge=0)]
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
            "candidate_count": sum(item.candidate_count for item in self.events),
            "candidate_gap_count": sum(len(item.candidate_gap_ids) for item in self.events),
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

    schema_version: Literal["hsq_event_entity_connection_report_v1"] = (
        "hsq_event_entity_connection_report_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    phase: EvaluationPhase
    repetition: Annotated[int, Field(ge=1)]
    event_count: Literal[20]
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
    candidate_gap_count: Annotated[int, Field(ge=0)]
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
            "candidate_gap_count": sum(len(item.candidate_gap_ids) for item in self.events),
            "violated_exclusion_count": sum(
                len(item.violated_exclusion_ids) for item in self.events
            ),
            "model_execution_count": sum(item.model_execution_count for item in self.events),
        }
        for field_name, expected in totals.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"Connection report {field_name} drifted from its Events.")
        if self.result_fingerprint != _result_fingerprint(self.events):
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
    trigger_source_by_event = {
        event.event_id: segment.source_text
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
        source_text = trigger_source_by_event[item.event_id]
        if any(
            accepted_source_text not in source_text
            for entity in item.expected_entities
            for accepted_source_text in entity.accepted_source_texts
        ):
            raise ValueError(
                "Connection Gold accepted source expression is absent from its SourceSegment."
            )
        if any(
            exclusion.source_text not in source_text
            for exclusion in item.excluded_actor_organization_expressions
        ):
            raise ValueError("Connection Gold exclusion is absent from its SourceSegment.")
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
            if draft.entity_kind is expected.entity_kind
            and draft.entity_name in expected.accepted_entity_names
            and _draft_has_accepted_source(preview, draft.candidate_id, expected)
        )
        if len(matches) == 1:
            matched.append(expected.entity_id)
            unmatched.discard(matches[0].id)
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
        span.end <= len(prepared.source_text)
        and prepared.source_text[span.start : span.end] == span.text
        for candidate in preview.candidates
        for span in candidate.source_spans
    )
    semantic_result = tuple(
        sorted(f"{item.entity_kind.value}:{item.entity_name}" for item in preview.drafts)
    )
    return EventEntityCaseEvaluation(
        event_id=gold.event_id,
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
        candidate_gap_ids=tuple(sorted(item.id for item in preview.candidate_gaps)),
        violated_exclusion_ids=violated_exclusions,
        candidate_count=len(preview.candidates),
        model_execution_count=len(preview.model_run_ids),
        exact_source_mapping=exact_source,
        semantic_result=semantic_result,
        passed=not (
            missing or unmatched or unresolved or preview.candidate_gaps or violated_exclusions
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
    return EventEntityPhaseReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        phase=phase,
        repetition=repetition,
        event_count=20,
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
        candidate_gap_count=sum(len(item.candidate_gap_ids) for item in ordered),
        violated_exclusion_count=sum(len(item.violated_exclusion_ids) for item in ordered),
        model_execution_count=sum(item.model_execution_count for item in ordered),
        model_elapsed_milliseconds=model_elapsed_milliseconds,
        result_fingerprint=_result_fingerprint(ordered),
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
        candidate_count=sum(item.candidate_count for item in events),
        candidate_gap_count=sum(len(item.candidate_gap_ids) for item in events),
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
    available: list[str] = []
    missing: list[str] = []
    for expected in gold.expected_entities:
        matched = any(
            candidate.entity_kind == expected.entity_kind
            and candidate.entity_name in expected.accepted_entity_names
            and _candidate_has_accepted_source(candidate, expected)
            for candidate in candidates
        )
        (available if matched else missing).append(expected.entity_id)
    inventory = tuple(
        sorted(
            f"{item.id}:{item.entity_kind.value}:{item.entity_name}:"
            + "|".join(span.text for span in item.source_spans)
            for item in candidates
        )
    )
    gaps = tuple(sorted(item.id for item in prepared.candidate_selection.gaps))
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
        candidate_gap_ids=gaps,
        violated_exclusion_ids=violated_exclusions,
        candidate_count=len(candidates),
        candidate_inventory=inventory,
        passed=not missing and not gaps and not violated_exclusions,
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
        f"Typed candidate gaps: `{report.candidate_gap_count}`",
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
                    "available" if entity_id in evaluation.available_entity_ids else "missing"
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
        lines.extend(("", "Typed candidate gaps:", ""))
        if evaluation.candidate_gap_ids:
            lines.extend(f"- `{item}`" for item in evaluation.candidate_gap_ids)
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
            "Accepted source expressions must exist byte-for-byte in the Event's exact "
            "SourceSegment."
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
                    "Accepted source expressions: "
                    + ", ".join(
                        json.dumps(item, ensure_ascii=False)
                        for item in entity.accepted_source_texts
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
                    "Exact excluded source expression: "
                    + json.dumps(exclusion.source_text, ensure_ascii=False),
                    "",
                    f"Rationale: {exclusion.rationale}",
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
    observed = {item.text for item in candidate.source_spans} | {
        item.text for item in candidate.resolved_antecedent_spans
    }
    return bool(observed & set(expected.accepted_source_texts))


def _candidate_has_excluded_source(
    candidate: EventEntityConnectionCandidate,
    exclusion: ConnectionGoldExcludedExpression,
) -> bool:
    observed = {item.text for item in candidate.source_spans} | {
        item.text for item in candidate.resolved_antecedent_spans
    }
    return exclusion.source_text in observed


def _result_fingerprint(events: tuple[EventEntityCaseEvaluation, ...]) -> str:
    payload = [
        {"event_id": item.event_id, "semantic_result": item.semantic_result} for item in events
    ]
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


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
