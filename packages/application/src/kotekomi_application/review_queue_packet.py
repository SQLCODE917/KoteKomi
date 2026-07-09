"""Review Queue and Review Packet read-model use cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, cast

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    Document,
    Entity,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProposedChange,
    Relationship,
    ReviewStatus,
    Source,
)
from kotekomi_domain.models import JsonValue

REVIEW_RECORD_TYPE_ORDER = {
    "Organization": 0,
    "Actor": 1,
    "Event": 2,
    "EvidenceSpan": 3,
    "Assertion": 4,
    "Relationship": 5,
    "Outcome": 6,
    "ArgumentEdge": 7,
}


type ReviewPacketRecord = (
    Actor | Organization | Event | EvidenceSpan | Assertion | Relationship | Outcome | ArgumentEdge
)


class ReviewReferenceResolution(StrEnum):
    ACCEPTED = "accepted"
    PENDING = "pending"
    MISSING = "missing"


class ReviewQueuePacketLedger(Protocol):
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def list_proposed_changes(self) -> tuple[ProposedChange, ...]: ...
    def get_source(self, record_id: str) -> Source | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_entity(self, record_id: str) -> Entity | None: ...
    def get_actor(self, record_id: str) -> Actor | None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...
    def get_event(self, record_id: str) -> Event | None: ...
    def get_place(self, record_id: str) -> Place | None: ...
    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None: ...
    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def get_relationship(self, record_id: str) -> Relationship | None: ...
    def get_outcome(self, record_id: str) -> Outcome | None: ...
    def get_argument_edge(self, record_id: str) -> ArgumentEdge | None: ...


@dataclass(frozen=True)
class ReviewQueueInput:
    review_status: ReviewStatus = ReviewStatus.PENDING
    record_type: str | None = None
    source_id: str | None = None
    document_id: str | None = None


@dataclass(frozen=True)
class ReviewQueueItem:
    proposed_change_id: str
    review_status: ReviewStatus
    record_type: str
    stable_label: str
    source_id: str | None
    document_id: str | None
    model_name: str | None
    prompt_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class ReviewQueueResult:
    items: tuple[ReviewQueueItem, ...]


@dataclass(frozen=True)
class ReviewPacketInput:
    proposed_change_id: str


@dataclass(frozen=True)
class ReviewEvidenceContext:
    source_id: str
    source_title: str | None
    document_id: str
    selector_type: str
    exact_text: str
    prefix_text: str
    suffix_text: str
    location: dict[str, JsonValue]


@dataclass(frozen=True)
class ReviewReferenceContext:
    referenced_id: str
    referenced_type: str
    resolution_status: ReviewReferenceResolution


@dataclass(frozen=True)
class ReviewAssertionContext:
    epistemic_scope: str
    source_authority: str
    attribution_basis: str
    source_report_confidence: float | None
    extraction_confidence: float | None
    world_truth_confidence: float | None
    causal_confidence: float | None


@dataclass(frozen=True)
class ReviewPacketMetadata:
    source_id: str | None
    document_id: str | None
    model_name: str | None
    prompt_id: str | None
    provenance_activity_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ReviewPacket:
    proposed_change_id: str
    review_status: ReviewStatus
    record_type: str
    stable_label: str
    proposed_record_json: dict[str, JsonValue]
    metadata: ReviewPacketMetadata
    evidence_contexts: tuple[ReviewEvidenceContext, ...]
    reference_contexts: tuple[ReviewReferenceContext, ...]
    assertion_context: ReviewAssertionContext | None


@dataclass(frozen=True)
class ReviewEditableRecordExportInput:
    proposed_change_id: str


@dataclass(frozen=True)
class ReviewEditableRecordExport:
    proposed_change_id: str
    record_type: str
    stable_label: str
    record_json: dict[str, JsonValue]


@dataclass(frozen=True)
class ReviewReadinessInput:
    record_type: str | None = None
    source_id: str | None = None
    document_id: str | None = None


@dataclass(frozen=True)
class ReviewReadinessBlocker:
    proposed_change_id: str
    record_type: str
    stable_label: str
    referenced_type: str
    referenced_id: str
    resolution_status: ReviewReferenceResolution


@dataclass(frozen=True)
class ReviewReadinessStatus:
    review_required: bool
    pending_count: int
    pending_record_type_counts: dict[str, int]
    pending_reference_count: int
    missing_reference_count: int
    can_project_graph: bool
    can_generate_briefing: bool
    next_recommended_command: str
    blockers: tuple[ReviewReadinessBlocker, ...]


def list_review_queue(
    review_input: ReviewQueueInput,
    ledger_repository: ReviewQueuePacketLedger,
) -> ReviewQueueResult:
    items = tuple(
        _queue_item(proposed_change)
        for proposed_change in ledger_repository.list_proposed_changes()
        if proposed_change.review_status is review_input.review_status
        and _matches_optional_filter(
            _proposal_record_type(proposed_change),
            review_input.record_type,
        )
        and _matches_optional_filter(proposed_change.source_id, review_input.source_id)
        and _matches_optional_filter(proposed_change.document_id, review_input.document_id)
    )
    return ReviewQueueResult(items=tuple(sorted(items, key=_queue_sort_key)))


def get_review_packet(
    review_input: ReviewPacketInput,
    ledger_repository: ReviewQueuePacketLedger,
) -> ReviewPacket:
    proposed_change = _get_proposed_change(review_input.proposed_change_id, ledger_repository)
    record_type = _proposal_record_type(proposed_change)
    stable_label = _proposal_stable_label(proposed_change)
    record_json = _proposal_record_json(proposed_change)
    record = _proposed_record_from_json(record_type=record_type, record_json=record_json)
    return ReviewPacket(
        proposed_change_id=proposed_change.id,
        review_status=proposed_change.review_status,
        record_type=record_type,
        stable_label=stable_label,
        proposed_record_json=record_json,
        metadata=ReviewPacketMetadata(
            source_id=proposed_change.source_id,
            document_id=proposed_change.document_id,
            model_name=proposed_change.model_name,
            prompt_id=proposed_change.prompt_id,
            provenance_activity_id=proposed_change.provenance_activity_id,
            created_at=proposed_change.created_at,
            updated_at=proposed_change.updated_at,
        ),
        evidence_contexts=_evidence_contexts(proposed_change, record, ledger_repository),
        reference_contexts=_reference_contexts(record, ledger_repository),
        assertion_context=_assertion_context(record),
    )


def export_review_editable_record(
    review_input: ReviewEditableRecordExportInput,
    ledger_repository: ReviewQueuePacketLedger,
) -> ReviewEditableRecordExport:
    proposed_change = _get_proposed_change(review_input.proposed_change_id, ledger_repository)
    record_type = _proposal_record_type(proposed_change)
    stable_label = _proposal_stable_label(proposed_change)
    record_json = _proposal_record_json(proposed_change)
    _proposed_record_from_json(record_type=record_type, record_json=record_json)
    return ReviewEditableRecordExport(
        proposed_change_id=proposed_change.id,
        record_type=record_type,
        stable_label=stable_label,
        record_json=record_json,
    )


def get_review_readiness(
    review_input: ReviewReadinessInput,
    ledger_repository: ReviewQueuePacketLedger,
) -> ReviewReadinessStatus:
    queue = list_review_queue(
        ReviewQueueInput(
            review_status=ReviewStatus.PENDING,
            record_type=review_input.record_type,
            source_id=review_input.source_id,
            document_id=review_input.document_id,
        ),
        ledger_repository,
    )
    pending_record_type_counts: dict[str, int] = {}
    blockers: list[ReviewReadinessBlocker] = []
    for item in queue.items:
        pending_record_type_counts[item.record_type] = (
            pending_record_type_counts.get(item.record_type, 0) + 1
        )
        packet = get_review_packet(
            ReviewPacketInput(proposed_change_id=item.proposed_change_id),
            ledger_repository,
        )
        blockers.extend(_readiness_blockers(packet))
    pending_count = len(queue.items)
    review_required = pending_count > 0
    return ReviewReadinessStatus(
        review_required=review_required,
        pending_count=pending_count,
        pending_record_type_counts=dict(sorted(pending_record_type_counts.items())),
        pending_reference_count=sum(
            1
            for blocker in blockers
            if blocker.resolution_status is ReviewReferenceResolution.PENDING
        ),
        missing_reference_count=sum(
            1
            for blocker in blockers
            if blocker.resolution_status is ReviewReferenceResolution.MISSING
        ),
        can_project_graph=not review_required,
        can_generate_briefing=not review_required,
        next_recommended_command="kotekomi review list"
        if review_required
        else "kotekomi graph project",
        blockers=tuple(blockers),
    )


def review_queue_result_to_json(result: ReviewQueueResult) -> dict[str, JsonValue]:
    return {
        "items": [
            {
                "proposed_change_id": item.proposed_change_id,
                "review_status": item.review_status.value,
                "record_type": item.record_type,
                "stable_label": item.stable_label,
                "source_id": item.source_id,
                "document_id": item.document_id,
                "model_name": item.model_name,
                "prompt_id": item.prompt_id,
                "created_at": item.created_at.isoformat(),
            }
            for item in result.items
        ]
    }


def review_packet_to_json(packet: ReviewPacket) -> dict[str, JsonValue]:
    return {
        "proposed_change_id": packet.proposed_change_id,
        "review_status": packet.review_status.value,
        "record_type": packet.record_type,
        "stable_label": packet.stable_label,
        "proposed_record_json": packet.proposed_record_json,
        "metadata": {
            "source_id": packet.metadata.source_id,
            "document_id": packet.metadata.document_id,
            "model_name": packet.metadata.model_name,
            "prompt_id": packet.metadata.prompt_id,
            "provenance_activity_id": packet.metadata.provenance_activity_id,
            "created_at": packet.metadata.created_at.isoformat(),
            "updated_at": packet.metadata.updated_at.isoformat(),
        },
        "evidence_contexts": [
            {
                "source_id": context.source_id,
                "source_title": context.source_title,
                "document_id": context.document_id,
                "selector_type": context.selector_type,
                "exact_text": context.exact_text,
                "prefix_text": context.prefix_text,
                "suffix_text": context.suffix_text,
                "location": context.location,
            }
            for context in packet.evidence_contexts
        ],
        "reference_contexts": [
            {
                "referenced_id": context.referenced_id,
                "referenced_type": context.referenced_type,
                "resolution_status": context.resolution_status.value,
            }
            for context in packet.reference_contexts
        ],
        "assertion_context": _assertion_context_to_json(packet.assertion_context),
    }


def review_readiness_to_json(status: ReviewReadinessStatus) -> dict[str, JsonValue]:
    pending_record_type_counts: dict[str, JsonValue] = {
        record_type: count for record_type, count in status.pending_record_type_counts.items()
    }
    return {
        "review_required": status.review_required,
        "pending_count": status.pending_count,
        "pending_record_type_counts": pending_record_type_counts,
        "pending_reference_count": status.pending_reference_count,
        "missing_reference_count": status.missing_reference_count,
        "can_project_graph": status.can_project_graph,
        "can_generate_briefing": status.can_generate_briefing,
        "next_recommended_command": status.next_recommended_command,
        "blockers": [
            {
                "proposed_change_id": blocker.proposed_change_id,
                "record_type": blocker.record_type,
                "stable_label": blocker.stable_label,
                "referenced_type": blocker.referenced_type,
                "referenced_id": blocker.referenced_id,
                "resolution_status": blocker.resolution_status.value,
            }
            for blocker in status.blockers
        ],
    }


def _readiness_blockers(packet: ReviewPacket) -> tuple[ReviewReadinessBlocker, ...]:
    return tuple(
        ReviewReadinessBlocker(
            proposed_change_id=packet.proposed_change_id,
            record_type=packet.record_type,
            stable_label=packet.stable_label,
            referenced_type=reference.referenced_type,
            referenced_id=reference.referenced_id,
            resolution_status=reference.resolution_status,
        )
        for reference in packet.reference_contexts
        if reference.resolution_status
        in {ReviewReferenceResolution.PENDING, ReviewReferenceResolution.MISSING}
    )


def _assertion_context_to_json(
    context: ReviewAssertionContext | None,
) -> dict[str, JsonValue] | None:
    if context is None:
        return None
    return {
        "epistemic_scope": context.epistemic_scope,
        "source_authority": context.source_authority,
        "attribution_basis": context.attribution_basis,
        "source_report_confidence": context.source_report_confidence,
        "extraction_confidence": context.extraction_confidence,
        "world_truth_confidence": context.world_truth_confidence,
        "causal_confidence": context.causal_confidence,
    }


def _matches_optional_filter(value: str | None, expected: str | None) -> bool:
    return expected is None or value == expected


def _queue_item(proposed_change: ProposedChange) -> ReviewQueueItem:
    return ReviewQueueItem(
        proposed_change_id=proposed_change.id,
        review_status=proposed_change.review_status,
        record_type=_proposal_record_type(proposed_change),
        stable_label=_proposal_stable_label(proposed_change),
        source_id=proposed_change.source_id,
        document_id=proposed_change.document_id,
        model_name=proposed_change.model_name,
        prompt_id=proposed_change.prompt_id,
        created_at=proposed_change.created_at,
    )


def _queue_sort_key(item: ReviewQueueItem) -> tuple[int, str, str]:
    return (REVIEW_RECORD_TYPE_ORDER[item.record_type], item.stable_label, item.proposed_change_id)


def _get_proposed_change(
    proposed_change_id: str,
    ledger_repository: ReviewQueuePacketLedger,
) -> ProposedChange:
    proposed_change = ledger_repository.get_proposed_change(proposed_change_id)
    if proposed_change is None:
        raise ValueError(f"ProposedChange not found: {proposed_change_id}")
    return proposed_change


def _proposal_record_type(proposed_change: ProposedChange) -> str:
    record_type = proposed_change.proposed_json.get("record_type")
    if not isinstance(record_type, str) or not record_type.strip():
        raise ValueError(f"ProposedChange missing record_type: {proposed_change.id}")
    if record_type not in REVIEW_RECORD_TYPE_ORDER:
        raise ValueError(f"Unsupported ProposedChange record_type: {record_type}")
    return record_type


def _proposal_stable_label(proposed_change: ProposedChange) -> str:
    stable_label = proposed_change.proposed_json.get("stable_label")
    if not isinstance(stable_label, str) or not stable_label.strip():
        raise ValueError(f"ProposedChange missing stable_label: {proposed_change.id}")
    return stable_label


def _proposal_record_json(proposed_change: ProposedChange) -> dict[str, JsonValue]:
    record = proposed_change.proposed_json.get("record")
    if not isinstance(record, dict):
        raise ValueError(f"ProposedChange missing record object: {proposed_change.id}")
    return cast(dict[str, JsonValue], record)


def _proposed_record_from_json(
    *,
    record_type: str,
    record_json: dict[str, JsonValue],
) -> ReviewPacketRecord:
    if record_type == "Actor":
        return Actor.model_validate_json(json.dumps(record_json))
    if record_type == "Organization":
        return Organization.model_validate_json(json.dumps(record_json))
    if record_type == "Event":
        return Event.model_validate_json(json.dumps(record_json))
    if record_type == "EvidenceSpan":
        return EvidenceSpan.model_validate_json(json.dumps(record_json))
    if record_type == "Assertion":
        return Assertion.model_validate_json(json.dumps(record_json))
    if record_type == "Relationship":
        return Relationship.model_validate_json(json.dumps(record_json))
    if record_type == "Outcome":
        return Outcome.model_validate_json(json.dumps(record_json))
    if record_type == "ArgumentEdge":
        return ArgumentEdge.model_validate_json(json.dumps(record_json))
    raise ValueError(f"Unsupported ProposedChange record_type: {record_type}")


def _evidence_contexts(
    proposed_change: ProposedChange,
    record: ReviewPacketRecord,
    ledger_repository: ReviewQueuePacketLedger,
) -> tuple[ReviewEvidenceContext, ...]:
    contexts: list[ReviewEvidenceContext] = []
    evidence = proposed_change.proposed_json.get("evidence")
    if isinstance(evidence, dict):
        contexts.append(
            _evidence_context_from_json(cast(dict[str, JsonValue], evidence), ledger_repository)
        )
    if isinstance(record, EvidenceSpan):
        contexts.append(
            _evidence_context_from_span(
                record,
                ledger_repository,
            )
        )
    if isinstance(record, Assertion):
        for evidence_span_id in record.evidence_span_ids:
            evidence_span = _find_evidence_span(evidence_span_id, ledger_repository)
            if evidence_span is not None:
                contexts.append(_evidence_context_from_span(evidence_span, ledger_repository))
    return _deduplicate_evidence_contexts(contexts)


def _evidence_context_from_json(
    evidence_json: dict[str, JsonValue],
    ledger_repository: ReviewQueuePacketLedger,
) -> ReviewEvidenceContext:
    source_id = _required_string(evidence_json, "source_id", "evidence")
    document_id = _required_string(evidence_json, "document_id", "evidence")
    selector_type = _required_string(evidence_json, "selector_type", "evidence")
    exact_text = _required_string(evidence_json, "exact_text", "evidence")
    prefix_text = _optional_string(evidence_json.get("prefix_text"))
    suffix_text = _optional_string(evidence_json.get("suffix_text"))
    location = _optional_json_object(evidence_json.get("location"))
    source = ledger_repository.get_source(source_id)
    return ReviewEvidenceContext(
        source_id=source_id,
        source_title=source.title if source is not None else None,
        document_id=document_id,
        selector_type=selector_type,
        exact_text=exact_text,
        prefix_text=prefix_text,
        suffix_text=suffix_text,
        location=location,
    )


def _evidence_context_from_span(
    evidence_span: EvidenceSpan,
    ledger_repository: ReviewQueuePacketLedger,
) -> ReviewEvidenceContext:
    source = ledger_repository.get_source(evidence_span.source_id)
    return ReviewEvidenceContext(
        source_id=evidence_span.source_id,
        source_title=source.title if source is not None else None,
        document_id=evidence_span.document_id,
        selector_type=evidence_span.selector_type.value,
        exact_text=evidence_span.exact_text,
        prefix_text=evidence_span.prefix_text,
        suffix_text=evidence_span.suffix_text,
        location=evidence_span.location,
    )


def _deduplicate_evidence_contexts(
    contexts: list[ReviewEvidenceContext],
) -> tuple[ReviewEvidenceContext, ...]:
    seen: set[tuple[str, str, str]] = set()
    deduplicated: list[ReviewEvidenceContext] = []
    for context in contexts:
        key = (context.source_id, context.document_id, context.exact_text)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(context)
    return tuple(deduplicated)


def _find_evidence_span(
    evidence_span_id: str,
    ledger_repository: ReviewQueuePacketLedger,
) -> EvidenceSpan | None:
    accepted = ledger_repository.get_evidence_span(evidence_span_id)
    if accepted is not None:
        return accepted
    for proposed_change in ledger_repository.list_proposed_changes():
        if proposed_change.review_status is not ReviewStatus.PENDING:
            continue
        if _pending_record_id(proposed_change) != evidence_span_id:
            continue
        if _proposal_record_type(proposed_change) != "EvidenceSpan":
            return None
        return EvidenceSpan.model_validate_json(json.dumps(_proposal_record_json(proposed_change)))
    return None


def _reference_contexts(
    record: ReviewPacketRecord,
    ledger_repository: ReviewQueuePacketLedger,
) -> tuple[ReviewReferenceContext, ...]:
    references = _record_references(record)
    return tuple(
        ReviewReferenceContext(
            referenced_id=referenced_id,
            referenced_type=referenced_type,
            resolution_status=_resolve_reference(referenced_type, referenced_id, ledger_repository),
        )
        for referenced_type, referenced_id in references
    )


def _record_references(record: ReviewPacketRecord) -> tuple[tuple[str, str], ...]:
    references: list[tuple[str, str]] = []
    if isinstance(record, Actor):
        references.extend(("Organization", record_id) for record_id in record.organization_ids)
    elif isinstance(record, Organization):
        return ()
    elif isinstance(record, Event):
        if record.place_id is not None:
            references.append(("Place", record.place_id))
        references.extend(("Actor", record_id) for record_id in record.participant_actor_ids)
        references.extend(
            ("Organization", record_id) for record_id in record.participant_organization_ids
        )
    elif isinstance(record, EvidenceSpan):
        references.append(("Source", record.source_id))
        references.append(("Document", record.document_id))
        if record.assertion_id is not None:
            references.append(("Assertion", record.assertion_id))
    elif isinstance(record, Assertion):
        references.append(
            (_entity_reference_type(record.subject_entity_id), record.subject_entity_id)
        )
        if record.object_entity_id is not None:
            references.append(
                (_entity_reference_type(record.object_entity_id), record.object_entity_id)
            )
        references.extend(("Source", record_id) for record_id in record.source_ids)
        references.extend(("EvidenceSpan", record_id) for record_id in record.evidence_span_ids)
        references.extend(("Source", record_id) for record_id in record.authority_source_ids)
        references.extend(
            ("EvidenceSpan", record_id) for record_id in record.authority_evidence_span_ids
        )
    elif isinstance(record, Relationship):
        references.append((_entity_reference_type(record.subject_id), record.subject_id))
        references.append((_entity_reference_type(record.object_id), record.object_id))
        references.extend(("Assertion", record_id) for record_id in record.assertion_ids)
    elif isinstance(record, Outcome):
        references.extend(("Actor", record_id) for record_id in record.actor_ids)
        references.extend(("Organization", record_id) for record_id in record.organization_ids)
        references.extend(("Event", record_id) for record_id in record.event_ids)
        references.extend(("Assertion", record_id) for record_id in record.assertion_ids)
    elif type(record) is ArgumentEdge:
        references.append(("Assertion", record.from_assertion_id))
        references.append(("Assertion", record.to_assertion_id))
        references.extend(("EvidenceSpan", record_id) for record_id in record.evidence_span_ids)
    else:
        raise TypeError(f"Unsupported review packet record type: {type(record).__name__}")
    return _deduplicate_references(references)


def _deduplicate_references(references: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    deduplicated: list[tuple[str, str]] = []
    for reference in references:
        if reference in seen:
            continue
        seen.add(reference)
        deduplicated.append(reference)
    return tuple(deduplicated)


def _entity_reference_type(record_id: str) -> str:
    if record_id.startswith("ent_"):
        return "Entity"
    if record_id.startswith("act_"):
        return "Actor"
    if record_id.startswith("org_"):
        return "Organization"
    if record_id.startswith("evt_"):
        return "Event"
    if record_id.startswith("plc_"):
        return "Place"
    raise ValueError(f"Unsupported entity reference ID: {record_id}")


def _resolve_reference(
    referenced_type: str,
    referenced_id: str,
    ledger_repository: ReviewQueuePacketLedger,
) -> ReviewReferenceResolution:
    if _accepted_reference_exists(referenced_type, referenced_id, ledger_repository):
        return ReviewReferenceResolution.ACCEPTED
    if _pending_reference_exists(referenced_type, referenced_id, ledger_repository):
        return ReviewReferenceResolution.PENDING
    return ReviewReferenceResolution.MISSING


def _accepted_reference_exists(
    referenced_type: str,
    referenced_id: str,
    ledger_repository: ReviewQueuePacketLedger,
) -> bool:
    if referenced_type == "Actor":
        return ledger_repository.get_actor(referenced_id) is not None
    if referenced_type == "Organization":
        return ledger_repository.get_organization(referenced_id) is not None
    if referenced_type == "Event":
        return ledger_repository.get_event(referenced_id) is not None
    if referenced_type == "EvidenceSpan":
        return ledger_repository.get_evidence_span(referenced_id) is not None
    if referenced_type == "Assertion":
        return ledger_repository.get_assertion(referenced_id) is not None
    if referenced_type == "Relationship":
        return ledger_repository.get_relationship(referenced_id) is not None
    if referenced_type == "Outcome":
        return ledger_repository.get_outcome(referenced_id) is not None
    if referenced_type == "ArgumentEdge":
        return ledger_repository.get_argument_edge(referenced_id) is not None
    if referenced_type == "Source":
        return ledger_repository.get_source(referenced_id) is not None
    if referenced_type == "Document":
        return ledger_repository.get_document(referenced_id) is not None
    if referenced_type == "Place":
        return ledger_repository.get_place(referenced_id) is not None
    if referenced_type == "Entity":
        return ledger_repository.get_entity(referenced_id) is not None
    raise ValueError(f"Unsupported reference type: {referenced_type}")


def _pending_reference_exists(
    referenced_type: str,
    referenced_id: str,
    ledger_repository: ReviewQueuePacketLedger,
) -> bool:
    for proposed_change in ledger_repository.list_proposed_changes():
        if proposed_change.review_status is not ReviewStatus.PENDING:
            continue
        if _proposal_record_type(proposed_change) != referenced_type:
            continue
        if _pending_record_id(proposed_change) == referenced_id:
            return True
    return False


def _pending_record_id(proposed_change: ProposedChange) -> str | None:
    record = _proposal_record_json(proposed_change)
    record_id = record.get("id")
    if record_id is None:
        return None
    if not isinstance(record_id, str) or not record_id.strip():
        raise ValueError(f"ProposedChange record has invalid id: {proposed_change.id}")
    return record_id


def _assertion_context(record: ReviewPacketRecord) -> ReviewAssertionContext | None:
    if not isinstance(record, Assertion):
        return None
    return ReviewAssertionContext(
        epistemic_scope=record.epistemic_scope.value,
        source_authority=record.source_authority.value,
        attribution_basis=record.attribution_basis.value,
        source_report_confidence=record.source_report_confidence,
        extraction_confidence=record.extraction_confidence,
        world_truth_confidence=record.world_truth_confidence,
        causal_confidence=record.causal_confidence,
    )


def _required_string(
    values: dict[str, JsonValue],
    key: str,
    context: str,
) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} missing {key}.")
    return value


def _optional_string(value: JsonValue | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Evidence context contains a non-string optional text field.")
    return value


def _optional_json_object(value: JsonValue | None) -> dict[str, JsonValue]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Evidence context location must be an object.")
    return cast(dict[str, JsonValue], value)
