"""Ingestion composition stage (R20 increments 3-4).

The stage wires the live Adapter to the Application Layer composition use case.
It routes typed reference diagnostics into the use case, so an unresolved or
awaiting-acceptance reference becomes an Event-specific hold. An explicit
recomposition runs the same path again after approval.
"""

from __future__ import annotations

from kotekomi_application import (
    AssertionConstructionInputs,
    EventCompositionRecord,
    ReferenceDiagnostic,
    ReferenceDiagnosticReason,
    ReferenceResolution,
    compose_event_from_resolution,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
)

from kotekomi_pipelines.live_identity_reference_provider import (
    LiveIdentityReferenceLedger,
    LiveIdentityReferenceProvider,
)


def compose_ingested_event(
    *,
    repository: LiveIdentityReferenceLedger,
    event_id: str,
    source_text: str,
    source_text_sha256: str,
    inventory: ConstituentCandidateInventory,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
    assertion_inputs: AssertionConstructionInputs,
    representation_id: str,
    text_view_id: str,
    pending_identity_ids: tuple[str, ...] = (),
) -> EventCompositionRecord:
    """Compose one ingested Event, turning reference diagnostics into holds.

    The live Adapter supplies accepted references and mention diagnostics. When
    the Adapter has no accepted reference but one identity occurrence awaits
    review, the stage adds an ``awaiting_acceptance`` diagnostic so the held
    record names the reference that review will provide.
    """
    provider = LiveIdentityReferenceProvider(
        repository,
        representation_id=representation_id,
        text_view_id=text_view_id,
    )
    resolution = provider.resolve_references_with_diagnostics(
        event_id, source_text, source_text_sha256
    )
    if not resolution.diagnostics and not resolution.references.entities and pending_identity_ids:
        resolution = ReferenceResolution(
            references=resolution.references,
            diagnostics=tuple(
                ReferenceDiagnostic(
                    occurrence_id=f"pending:{identity_id}",
                    identity_id=identity_id,
                    reason=ReferenceDiagnosticReason.AWAITING_ACCEPTANCE,
                    detail="Identity occurrence awaits review.",
                )
                for identity_id in pending_identity_ids
            ),
        )
    return compose_event_from_resolution(
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        inventory=inventory,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
        resolution=resolution,
        assertion_inputs=assertion_inputs,
    )
