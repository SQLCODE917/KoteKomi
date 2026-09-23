"""Deterministic model-free composition of the Event attribution wiring unit.

D4 of the Event Attribution Production Wiring package. The composer runs the three
already-shipped construction units in one call over one governed Event:

- D3 ``split_trigger_scope`` splits the Event trigger into its reporting carrier and
  governed complement.
- D1 ``construct_attributed_statement`` turns the governed ``EventSemanticDraft`` plus its
  resolved attribution target into an ``attributed_statement`` ``ProposedAssertion``.
- D2 ``produce_support_edge`` is pinned the moment the attributed statement is constructed,
  so its ``ProduceSupportEdgeInput`` recipe is ready for the caller to review and bind.

The composer never invokes a model and never writes canonical state. A held split blocks the
attributed-statement construction instead of silently merging the reporting carrier and the
governed complement into one proposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self

from kotekomi_domain.models import (
    ActorId,
    AssertionId,
    EntityId,
    EventId,
    EvidenceTargetId,
    JsonValue,
    OrganizationId,
    PlaceId,
    SourceId,
)
from pydantic import BaseModel, ConfigDict, model_validator

from kotekomi_application.attributed_statement_construction import (
    AttributedStatementOutcome,
    AttributedStatementStatus,
    AttributionTargetResolver,
    construct_attributed_statement,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticEvidence
from kotekomi_application.hybrid_event_semantics import (
    EventArgumentTargetDraft,
    EventSemanticDraft,
    SourceGroundedEventDraft,
)
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft
from kotekomi_application.support_edge_production import ProduceSupportEdgeInput
from kotekomi_application.trigger_scope_split import (
    TriggerScopeSplit,
    TriggerScopeStatus,
    split_trigger_scope,
)

_ContentEntityId = EntityId | ActorId | OrganizationId | EventId | PlaceId


class EventAttributionWiringStatus(StrEnum):
    """Terminal state of one deterministic attribution wiring composition."""

    CONSTRUCTED = "constructed"
    HELD = "held"
    NO_ASSERTION = "no_assertion"
    FAILED = "failed"


@dataclass(frozen=True)
class EventAttributionWiringInput:
    """One fully pinned governed Event plus its D2 supports-edge ingredients.

    ``object_entity_id`` and ``object_value`` are mutually exclusive: exactly one must be
    supplied. The D2 ingredients (``evidence_assertion_id``, ``rationale``, ``confidence``,
    ``support_decision_id``, ``support_judgment_id``, ``nli_observation_id``, ``occurred_at``)
    are required only when the composer reaches a constructed attributed statement; a held
    split or a non-targeted Event never reads them.
    """

    source_text: str
    event: SourceGroundedEventDraft
    trigger: EventTriggerDraft
    linguistic_evidence: EventEntityLinguisticEvidence
    semantic_draft: EventSemanticDraft
    attribution_target: EventArgumentTargetDraft | None
    subject_entity_id: _ContentEntityId
    object_entity_id: _ContentEntityId | None
    object_value: JsonValue | None
    source_id: SourceId
    support_evidence_target_id: EvidenceTargetId
    assertion_id: AssertionId
    evidence_assertion_id: str | None = None
    rationale: str | None = None
    confidence: float | None = None
    support_decision_id: str | None = None
    support_judgment_id: str | None = None
    nli_observation_id: str | None = None
    occurred_at: datetime | None = None

    def __post_init__(self) -> None:
        if (self.object_entity_id is None) == (self.object_value is None):
            raise ValueError(
                "Event attribution wiring requires exactly one of object_entity_id or object_value."
            )


class EventAttributionWiringResult(BaseModel):
    """One bounded result of a deterministic attribution wiring composition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: EventAttributionWiringStatus
    trigger_scope_split: TriggerScopeSplit
    attributed_statement: AttributedStatementOutcome | None = None
    support_edge_input: ProduceSupportEdgeInput | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        statement = self.attributed_statement
        edge = self.support_edge_input
        if self.status is EventAttributionWiringStatus.CONSTRUCTED:
            if self.trigger_scope_split.status is not TriggerScopeStatus.COMPLETE:
                raise ValueError("A constructed wiring result requires a complete split.")
            if statement is None or edge is None:
                raise ValueError(
                    "A constructed wiring result requires a statement and a pinned D2 input."
                )
            if statement.status is not AttributedStatementStatus.CONSTRUCTED:
                raise ValueError(
                    "A constructed wiring result requires a constructed attributed statement."
                )
            proposed = statement.proposed_assertion
            assert proposed is not None
            if edge.to_assertion_id != proposed.id:
                raise ValueError("The pinned D2 input must name the constructed assertion.")
        elif self.status is EventAttributionWiringStatus.HELD:
            if self.trigger_scope_split.status is not TriggerScopeStatus.HELD:
                raise ValueError("A held wiring result requires a held split.")
            if statement is not None or edge is not None:
                raise ValueError("A held wiring result cannot carry a statement or D2 input.")
        else:
            if self.trigger_scope_split.status is not TriggerScopeStatus.COMPLETE:
                raise ValueError("A non-held statement outcome requires a complete split.")
            if statement is None or edge is not None:
                raise ValueError(
                    "A no-assertion or failed wiring result requires exactly one statement outcome."
                )
            if self.status is EventAttributionWiringStatus.NO_ASSERTION:
                if statement.status is not AttributedStatementStatus.NO_ASSERTION:
                    raise ValueError(
                        "A no-assertion wiring result requires a no-assertion statement."
                    )
            elif statement.status is not AttributedStatementStatus.FAILED:
                raise ValueError("A failed wiring result requires a failed statement.")
        return self


def wire_event_attribution(
    *,
    wiring_input: EventAttributionWiringInput,
    resolver: AttributionTargetResolver,
) -> EventAttributionWiringResult:
    """Compose the D3 split, D1 construction, and D2 recipe for one governed Event.

    A held split returns before any statement is constructed, so the reporting carrier and the
    governed complement are never merged. A constructed attributed statement always carries a
    fully pinned ``ProduceSupportEdgeInput`` ready for the caller to review and bind.
    """
    split = split_trigger_scope(
        source_text=wiring_input.source_text,
        trigger=wiring_input.trigger,
        event=wiring_input.event,
        linguistic_evidence=wiring_input.linguistic_evidence,
    )
    if split.status is TriggerScopeStatus.HELD:
        return EventAttributionWiringResult(
            status=EventAttributionWiringStatus.HELD,
            trigger_scope_split=split,
        )

    attributed = construct_attributed_statement(
        draft=wiring_input.semantic_draft,
        attribution_target=wiring_input.attribution_target,
        resolver=resolver,
        subject_entity_id=wiring_input.subject_entity_id,
        object_entity_id=wiring_input.object_entity_id,
        object_value=wiring_input.object_value,
        source_id=wiring_input.source_id,
        support_evidence_target_id=wiring_input.support_evidence_target_id,
        assertion_id=wiring_input.assertion_id,
    )
    if attributed.status is AttributedStatementStatus.NO_ASSERTION:
        return EventAttributionWiringResult(
            status=EventAttributionWiringStatus.NO_ASSERTION,
            trigger_scope_split=split,
            attributed_statement=attributed,
        )
    if attributed.status is AttributedStatementStatus.FAILED:
        return EventAttributionWiringResult(
            status=EventAttributionWiringStatus.FAILED,
            trigger_scope_split=split,
            attributed_statement=attributed,
        )

    if (
        wiring_input.evidence_assertion_id is None
        or wiring_input.rationale is None
        or wiring_input.confidence is None
        or wiring_input.support_decision_id is None
        or wiring_input.support_judgment_id is None
        or wiring_input.nli_observation_id is None
        or wiring_input.occurred_at is None
    ):
        raise ValueError(
            "A constructed wiring result requires a fully pinned supports-edge recipe."
        )

    assert attributed.proposed_assertion is not None
    support_edge_input = ProduceSupportEdgeInput(
        from_assertion_id=wiring_input.evidence_assertion_id,
        to_assertion_id=attributed.proposed_assertion.id,
        rationale=wiring_input.rationale,
        confidence=wiring_input.confidence,
        evidence_target_ids=(wiring_input.support_evidence_target_id,),
        support_decision_id=wiring_input.support_decision_id,
        support_judgment_id=wiring_input.support_judgment_id,
        nli_observation_id=wiring_input.nli_observation_id,
        occurred_at=wiring_input.occurred_at,
    )
    return EventAttributionWiringResult(
        status=EventAttributionWiringStatus.CONSTRUCTED,
        trigger_scope_split=split,
        attributed_statement=attributed,
        support_edge_input=support_edge_input,
    )