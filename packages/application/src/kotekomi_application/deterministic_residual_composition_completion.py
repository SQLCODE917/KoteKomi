"""Deterministic residual composition completion use case (R19).

This coordinating use case composes three model-free operations for one residual
Event:

1. the deterministic source-grounded selector, which derives one
   ``ConstituentSelectionAnswer`` from the trigger-head dependents only;
2. the ``EventEntityReferenceProvider`` Port, which resolves accepted Actor and
   Organization references and reviewed subject-value exclusions; and
3. the deterministic composer, which assembles one ``DecontextualizedProposition``.

The use case — not the composer — calls the Port and passes validated references
into the composer. A boundary-gap selection halts with a typed partial outcome
instead of a composed proposition. R19 executes no model, writes no canonical
state, and records no proposed change.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.decontextualization_composition import (
    DecontextualizationStatus,
    DecontextualizedProposition,
    build_decontextualized_proposition,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.event_entity_reference_provider import (
    EventEntityReferenceProvider,
    EventEntityReferences,
)
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
)
from kotekomi_application.source_grounded_selection import (
    SourceGroundedSelectionResult,
    SourceGroundedSelectionStatus,
    select_source_grounded_constituents,
)

_EventId = Annotated[
    str, Field(pattern=r"^(?:(?:TGE|AHE)-[0-9]{3}|sge_[A-Za-z0-9][A-Za-z0-9_-]*)$")
]
#: One R19 Assertion is an inspectable, never persisted, `proposed` record. It has no
#: wall-clock creation time, so it carries this documented logical epoch instead of
#: `utc_now` to keep the sealed report reproducible. The value is the R19 program's
#: start epoch, declared here rather than derived from content at runtime.
_R19_ASSERTION_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class DeterministicResidualCompositionStatus(StrEnum):
    """Terminal state of one deterministic residual composition completion."""

    COMPOSED = "composed"
    COMPOSITION_HELD = "composition_held"
    SELECTION_GAP = "selection_gap"


class DeterministicResidualCompositionOutcome(BaseModel):
    """One residual Event's production selection and composed proposition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    status: DeterministicResidualCompositionStatus
    selection: SourceGroundedSelectionResult
    references: EventEntityReferences
    proposition: DecontextualizedProposition | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is DeterministicResidualCompositionStatus.COMPOSED:
            if (
                self.proposition is None
                or self.proposition.status is not DecontextualizationStatus.PROPOSITION
            ):
                raise ValueError("A composed outcome requires a proposition, not a held result.")
        elif self.status is DeterministicResidualCompositionStatus.COMPOSITION_HELD:
            if (
                self.proposition is None
                or self.proposition.status is not DecontextualizationStatus.HELD
            ):
                raise ValueError(
                    "A composition-held outcome requires a held proposition with a hold reason."
                )
        elif self.proposition is not None:
            raise ValueError("A selection-gap outcome cannot carry a proposition.")
        return self


def complete_deterministic_residual_composition(
    *,
    event_id: str,
    source_text: str,
    source_text_sha256: str,
    inventory: ConstituentCandidateInventory,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
    provider: EventEntityReferenceProvider,
) -> DeterministicResidualCompositionOutcome:
    """Complete one residual Event's selection and composition through the Port.

    The selection runs first; the provider runs second so a selection gap never
    hides a missing reference, and the composer runs last with validated
    references it never looks up itself.
    """
    selection = select_source_grounded_constituents(
        event_id=event_id,
        source_text=source_text,
        inventory=inventory,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
    )
    references = provider.resolve_references(
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
    )
    if selection.status is SourceGroundedSelectionStatus.BOUNDARY_GAP:
        return DeterministicResidualCompositionOutcome(
            event_id=event_id,
            status=DeterministicResidualCompositionStatus.SELECTION_GAP,
            selection=selection,
            references=references,
            proposition=None,
        )
    answer = selection.answer
    if answer is None:
        raise ValueError("A non-gap source-grounded selection requires an answer.")
    proposition = build_decontextualized_proposition(
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        inventory=inventory,
        answer=answer,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
        entities=references.entities,
        subject_value_authorizations=references.subject_value_authorizations,
    )
    if proposition.status is DecontextualizationStatus.PROPOSITION:
        status = DeterministicResidualCompositionStatus.COMPOSED
    else:
        status = DeterministicResidualCompositionStatus.COMPOSITION_HELD
    return DeterministicResidualCompositionOutcome(
        event_id=event_id,
        status=status,
        selection=selection,
        references=references,
        proposition=proposition,
    )
