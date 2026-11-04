"""Source-grounded Event composition from a live reference resolution (R20).

The composition use case consumes a ``ReferenceResolution`` that carries both
accepted references and typed diagnostics. It runs the selection, the composer,
and the inspectable Assertion constructor, then returns one persisted-shape
``EventCompositionRecord``. A diagnostic that explains an unavailable reference
becomes the Event-specific hold reason instead of a generic composer hold.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol, Self

from kotekomi_domain import Assertion
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.assertion_construction import (
    AssertionConstructionInputs,
    AssertionConstructionStatus,
    construct_inspectable_assertion,
)
from kotekomi_application.decontextualization_composition import (
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DecontextualizedRole,
    build_decontextualized_proposition,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.event_entity_reference_provider import EventEntityReferences
from kotekomi_application.ingestion_inspection import CompositionAnnotation, Span
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
)
from kotekomi_application.source_grounded_selection import (
    SourceGroundedSelectionStatus,
    select_source_grounded_constituents,
)
from kotekomi_application.source_ranges import SourceRange

#: Accepts the experiment residual IDs and the live SourceGroundedEvent IDs.
_EventId = Annotated[
    str, Field(pattern=r"^(?:(?:TGE|AHE)-[0-9]{3}|sge_[A-Za-z0-9][A-Za-z0-9_-]*)$")
]
_SHA256 = r"^[a-f0-9]{64}$"


class ReferenceDiagnosticReason(StrEnum):
    """Typed reason one accepted mention leaves no reference for an Event."""

    AMBIGUOUS_MENTION = "ambiguous_mention"
    MENTION_NOT_FOUND = "mention_not_found"
    AWAITING_ACCEPTANCE = "awaiting_acceptance"
    CROSS_VIEW_UNSUPPORTED = "cross_view_unsupported"


class ReferenceDiagnostic(BaseModel):
    """One explicit explanation for an unavailable Event reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    occurrence_id: Annotated[str, Field(min_length=1)]
    identity_id: Annotated[str, Field(min_length=1)]
    reason: ReferenceDiagnosticReason
    detail: Annotated[str, Field(min_length=1)]


class ReferenceResolution(BaseModel):
    """One Event's accepted references plus every unresolved-mention diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    references: EventEntityReferences
    diagnostics: tuple[ReferenceDiagnostic, ...]


class EventCompositionStatus(StrEnum):
    """Terminal state of one ingested Event composition."""

    HELD = "held"
    COMPOSED = "composed"


class EventCompositionRecord(BaseModel):
    """One Event's persisted composition outcome and its supporting spans."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    status: EventCompositionStatus
    relation_label: Annotated[str, Field(min_length=1)] | None = None
    subject_text: Annotated[str, Field(min_length=1)] | None = None
    object_text: Annotated[str, Field(min_length=1)] | None = None
    assertion: Assertion | None = None
    supporting_subject_span: SourceRange | None = None
    supporting_object_span: SourceRange | None = None
    hold_reason: Annotated[str, Field(min_length=1)] | None = None
    unavailable_reference: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is EventCompositionStatus.COMPOSED:
            if self.assertion is None or self.hold_reason is not None:
                raise ValueError("A composed record requires an Assertion and no hold.")
        elif self.hold_reason is None:
            raise ValueError("A held record requires one hold reason.")
        return self


def compose_event_from_resolution(
    *,
    event_id: str,
    source_text: str,
    source_text_sha256: str,
    inventory: ConstituentCandidateInventory,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
    resolution: ReferenceResolution,
    assertion_inputs: AssertionConstructionInputs,
) -> EventCompositionRecord:
    """Compose one ingested Event, turning reference diagnostics into holds."""
    selection = select_source_grounded_constituents(
        event_id=event_id,
        source_text=source_text,
        inventory=inventory,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
    )
    if selection.status is SourceGroundedSelectionStatus.BOUNDARY_GAP or selection.answer is None:
        return _held(event_id, source_text_sha256, "selection_gap", None)

    proposition = build_decontextualized_proposition(
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        inventory=inventory,
        answer=selection.answer,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
        entities=resolution.references.entities,
        subject_value_authorizations=resolution.references.subject_value_authorizations,
    )

    if proposition.status is DecontextualizationStatus.PROPOSITION:
        construction = construct_inspectable_assertion(proposition, assertion_inputs)
        if construction.status is AssertionConstructionStatus.CONSTRUCTED:
            return EventCompositionRecord(
                event_id=event_id,
                source_text_sha256=source_text_sha256,
                status=EventCompositionStatus.COMPOSED,
                relation_label=proposition.relation_label,
                subject_text=_role_text(proposition.subject),
                object_text=_role_text(proposition.object),
                assertion=construction.assertion,
                supporting_subject_span=(
                    proposition.subject.exact_fragment if proposition.subject else None
                ),
                supporting_object_span=(
                    proposition.object.exact_fragment if proposition.object else None
                ),
            )
        reason = construction.block_reason.value if construction.block_reason else "assertion"
        return _held(event_id, source_text_sha256, reason, None)

    reason = (
        proposition.hold_reason.value if proposition.hold_reason is not None else "composition_held"
    )
    unavailable: str | None = None
    if (
        proposition.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE
        and resolution.diagnostics
    ):
        diagnostic = resolution.diagnostics[0]
        reason = diagnostic.reason.value
        unavailable = diagnostic.identity_id
    return _held(event_id, source_text_sha256, reason, unavailable)


def _role_text(role: DecontextualizedRole | None) -> str | None:
    return None if role is None else role.exact_fragment.text


def _held(
    event_id: str,
    source_text_sha256: str,
    hold_reason: str,
    unavailable_reference: str | None,
) -> EventCompositionRecord:
    return EventCompositionRecord(
        event_id=event_id,
        source_text_sha256=source_text_sha256,
        status=EventCompositionStatus.HELD,
        hold_reason=hold_reason,
        unavailable_reference=unavailable_reference,
    )


class EventCompositionStore(Protocol):
    """Persistence operations ingestion, recomposition, and inspection require."""

    def save(self, record: EventCompositionRecord) -> None: ...

    def load(self, event_id: str) -> EventCompositionRecord: ...

    def annotations(self, event_ids: tuple[str, ...]) -> tuple[CompositionAnnotation, ...]: ...


def composition_annotation(record: EventCompositionRecord) -> CompositionAnnotation:
    """Map one persisted composition record to the replay-view annotation."""
    if record.status is EventCompositionStatus.COMPOSED:
        summary = f"composed: {record.relation_label} {record.subject_text} -> {record.object_text}"
    else:
        summary = f"held: {record.hold_reason}"
        if record.unavailable_reference is not None:
            summary += f" (missing {record.unavailable_reference})"
    source_span = record.supporting_subject_span
    span = None
    if source_span is not None:
        span = Span(start=source_span.start, end=source_span.end, text=source_span.text)
    return CompositionAnnotation(
        event_id=record.event_id,
        status=record.status.value,
        summary=summary,
        span=span,
    )
