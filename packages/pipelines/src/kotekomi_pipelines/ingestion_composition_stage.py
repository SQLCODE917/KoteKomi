"""Ingestion composition stage (R20 increments 3-4).

The stage wires the live Adapter to the Application Layer composition use case.
It routes typed reference diagnostics into the use case, so an unresolved or
awaiting-acceptance reference becomes an Event-specific hold. An explicit
recomposition runs the same path again after approval.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from kotekomi_application import (
    AssertionConstructionInputs,
    EventCompositionRecord,
    EventCompositionStatus,
    EventCompositionStore,
    ReferenceDiagnostic,
    ReferenceDiagnosticReason,
    ReferenceResolution,
    compose_event_from_resolution,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    build_constituent_candidate_inventory,
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
    node_start_char: int = 0,
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
        node_start_char=node_start_char,
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


def compose_paragraph_events(
    *,
    repository: LiveIdentityReferenceLedger,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    events: tuple[tuple[str, int, int], ...],
    assertion_inputs_by_event: Mapping[str, AssertionConstructionInputs],
    representation_id: str,
    text_view_id: str,
    store: EventCompositionStore,
    node_start_char: int = 0,
    pending_identity_ids_by_event: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[EventCompositionRecord, ...]:
    """Compose every Event in one ingested paragraph and persist each outcome.

    A missing dependency inventory or missing reviewed assertion inputs produces
    an explicit held record. No Event is skipped.
    """
    source_text_sha256 = hashlib.sha256(source_text.encode()).hexdigest()
    pending = pending_identity_ids_by_event or {}
    records: list[EventCompositionRecord] = []
    for event_id, trigger_start, trigger_end in events:
        record = _compose_one_paragraph_event(
            repository=repository,
            event_id=event_id,
            source_text=source_text,
            source_text_sha256=source_text_sha256,
            tokens=tokens,
            trigger_start=trigger_start,
            trigger_end=trigger_end,
            assertion_inputs=assertion_inputs_by_event.get(event_id),
            representation_id=representation_id,
            text_view_id=text_view_id,
            node_start_char=node_start_char,
            pending_identity_ids=pending.get(event_id, ()),
        )
        store.save(record)
        records.append(record)
    return tuple(records)


def _compose_one_paragraph_event(
    *,
    repository: LiveIdentityReferenceLedger,
    event_id: str,
    source_text: str,
    source_text_sha256: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    trigger_start: int,
    trigger_end: int,
    assertion_inputs: AssertionConstructionInputs | None,
    representation_id: str,
    text_view_id: str,
    node_start_char: int,
    pending_identity_ids: tuple[str, ...],
) -> EventCompositionRecord:
    if not tokens:
        return _paragraph_hold(event_id, source_text_sha256, "inventory_unavailable")
    try:
        inventory = build_constituent_candidate_inventory(
            source_text=source_text,
            event_id=event_id,
            tokens=tokens,
            event_expression_start=trigger_start,
            event_expression_end=trigger_end,
        )
    except ValueError:
        return _paragraph_hold(event_id, source_text_sha256, "inventory_unavailable")
    if assertion_inputs is None:
        return _paragraph_hold(event_id, source_text_sha256, "assertion_inputs_unavailable")
    return compose_ingested_event(
        repository=repository,
        event_id=event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        inventory=inventory,
        trigger_head_start=trigger_start,
        trigger_head_end=trigger_end,
        tokens=tokens,
        assertion_inputs=assertion_inputs,
        representation_id=representation_id,
        text_view_id=text_view_id,
        node_start_char=node_start_char,
        pending_identity_ids=pending_identity_ids,
    )


def _paragraph_hold(
    event_id: str, source_text_sha256: str, hold_reason: str
) -> EventCompositionRecord:
    return EventCompositionRecord(
        event_id=event_id,
        source_text_sha256=source_text_sha256,
        status=EventCompositionStatus.HELD,
        hold_reason=hold_reason,
    )
