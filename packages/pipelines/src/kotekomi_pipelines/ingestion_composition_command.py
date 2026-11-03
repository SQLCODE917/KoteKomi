"""Explicit recomposition command for one ingested Event (R20).

Approval does not recompose automatically. This command is the discoverable,
explicit second step: it re-runs the composition stage for one Event and returns
the persisted-shape composition record. The thin runner
``scripts/recompose_ingested_event.py`` wraps it.
"""

from __future__ import annotations

from typing import Annotated

from kotekomi_application import (
    AssertionConstructionInputs,
    ConstituentCandidateInventory,
    EventCompositionRecord,
    EventEntityLinguisticToken,
)
from kotekomi_domain import AssertionType, AttributionBasis, SourceAuthority
from pydantic import BaseModel, ConfigDict, Field

from kotekomi_pipelines.ingestion_composition_stage import compose_ingested_event
from kotekomi_pipelines.live_identity_reference_provider import (
    LiveIdentityReferenceLedger,
)

_EventId = Annotated[
    str, Field(pattern=r"^(?:(?:TGE|AHE)-[0-9]{3}|sge_[A-Za-z0-9][A-Za-z0-9_-]*)$")
]
_SHA256 = r"^[a-f0-9]{64}$"


class RecompositionRequest(BaseModel):
    """All inputs the explicit recomposition command needs for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    inventory: ConstituentCandidateInventory
    trigger_head_start: Annotated[int, Field(ge=0)]
    trigger_head_end: Annotated[int, Field(gt=0)]
    tokens: tuple[EventEntityLinguisticToken, ...]
    representation_id: Annotated[str, Field(min_length=1)]
    text_view_id: Annotated[str, Field(min_length=1)]
    node_start_char: Annotated[int, Field(ge=0)] = 0
    pending_identity_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    predicate_by_label: dict[str, str]
    identity_by_entity: dict[str, str]
    assertion_type: AssertionType
    source_authority: SourceAuthority
    attribution_basis: AttributionBasis
    source_id: Annotated[str, Field(min_length=1)]
    evidence_target_id: Annotated[str, Field(min_length=1)]


def run_recomposition(
    request: RecompositionRequest,
    repository: LiveIdentityReferenceLedger,
) -> EventCompositionRecord:
    """Run the explicit recomposition command for one ingested Event."""
    return compose_ingested_event(
        repository=repository,
        event_id=request.event_id,
        source_text=request.source_text,
        source_text_sha256=request.source_text_sha256,
        inventory=request.inventory,
        trigger_head_start=request.trigger_head_start,
        trigger_head_end=request.trigger_head_end,
        tokens=request.tokens,
        assertion_inputs=AssertionConstructionInputs(
            predicate_by_label=request.predicate_by_label,
            identity_by_entity=request.identity_by_entity,
            assertion_type=request.assertion_type,
            source_authority=request.source_authority,
            attribution_basis=request.attribution_basis,
            source_id=request.source_id,
            evidence_target_id=request.evidence_target_id,
        ),
        representation_id=request.representation_id,
        text_view_id=request.text_view_id,
        node_start_char=request.node_start_char,
        pending_identity_ids=request.pending_identity_ids,
    )
