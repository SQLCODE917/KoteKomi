"""Reviewed construction decisions for one ingested Event.

The pipeline builds an Event review packet from stored ingestion records. The
operator supplies the meaning-bearing decisions. This module validates those
decisions, accepts the identity occurrence through the existing use case, and
persists one approved construction review bound to the Event's source revision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    EventConstructionReview,
    EvidenceTarget,
    IdentityOccurrenceKind,
    ProvenanceActivity,
    ReviewStatus,
    SourceAuthority,
)

from kotekomi_application.assertion_construction import AssertionConstructionInputs
from kotekomi_application.evidence_targets import validate_evidence_target_record
from kotekomi_application.identity_occurrence_acceptance import (
    GroundingCandidate,
    IdentityOccurrenceAcceptanceLedger,
    IdentityOccurrenceProposalInput,
    accept_identity_occurrence,
    propose_identity_occurrence,
)

_REVIEW_RECORD_TYPE = "EventConstructionReview"


class EventConstructionReviewError(ValueError):
    """A reviewed decision cannot apply to the selected Event."""


class EventConstructionReviewConflict(EventConstructionReviewError):
    """An approved review for this Event records a different decision."""


@dataclass(frozen=True)
class ReviewCandidateIdentity:
    """One review-selectable identity candidate with its exact occurrence."""

    start: int
    end: int
    exact_text: str
    identity_name: str
    subject_role: bool = False


@dataclass(frozen=True)
class EventReviewPacket:
    """One Event's review packet assembled from stored ingestion records."""

    ingestion_run_id: str
    event_id: str
    paragraph_node_id: str
    representation_id: str
    text_view_id: str
    text_view_digest: str
    source_text_sha256: str
    source_id: str
    document_id: str
    node_start_char: int
    source_text: str
    trigger_start: int
    trigger_end: int
    relation_label: str
    subject_start: int | None
    subject_end: int | None
    subject_text: str | None
    object_start: int | None
    object_end: int | None
    object_text: str | None
    statement_start: int
    statement_end: int
    candidates: tuple[ReviewCandidateIdentity, ...]
    accepted_identity_ids: tuple[str, ...]
    required_decisions: tuple[str, ...]
    hold_reason: str | None
    existing_review_id: str | None
    evidence_target_id: str | None


def packet_source_digest(packet: EventReviewPacket) -> str:
    """Return the digest of the exact source text the packet displays."""
    return hashlib.sha256(packet.source_text.encode()).hexdigest()


def _check_span(packet: EventReviewPacket, start: int, end: int, text: str) -> None:
    if not (0 <= start < end <= len(packet.source_text)):
        raise EventConstructionReviewError("A displayed span lies outside the source text.")
    if packet.source_text[start:end] != text:
        raise EventConstructionReviewError("A displayed span does not match the source text.")


def validate_packet_bindings(packet: EventReviewPacket) -> None:
    """Reject a packet whose displayed content does not match its bindings."""
    if packet_source_digest(packet) != packet.source_text_sha256:
        raise EventConstructionReviewError("The packet source text digest does not match.")
    _check_span(
        packet,
        packet.trigger_start,
        packet.trigger_end,
        packet.source_text[packet.trigger_start : packet.trigger_end],
    )
    if packet.subject_start is not None and packet.subject_end is not None:
        if packet.subject_text is None:
            raise EventConstructionReviewError("A subject span requires its subject text.")
        _check_span(packet, packet.subject_start, packet.subject_end, packet.subject_text)
    if packet.object_start is not None and packet.object_end is not None:
        if packet.object_text is None:
            raise EventConstructionReviewError("An object span requires its object text.")
        _check_span(packet, packet.object_start, packet.object_end, packet.object_text)
    for candidate in packet.candidates:
        _check_span(packet, candidate.start, candidate.end, candidate.exact_text)


@dataclass(frozen=True)
class EventConstructionDecisionInput:
    """The operator's reviewed decisions for one Event."""

    candidate_start: int
    candidate_end: int
    exact_text: str
    identity_kind: IdentityOccurrenceKind
    identity_decision: Literal["new_identity", "existing_identity"]
    identity_name: str | None
    existing_identity_id: str | None
    predicate: str
    assertion_type: AssertionType
    source_authority: SourceAuthority
    attribution_basis: AttributionBasis
    reviewer: str


def decision_sha256(packet: EventReviewPacket, decision: EventConstructionDecisionInput) -> str:
    payload = json.dumps(
        {
            "event_id": packet.event_id,
            "ingestion_run_id": packet.ingestion_run_id,
            "paragraph_node_id": packet.paragraph_node_id,
            "source_text_sha256": packet.source_text_sha256,
            "candidate_start": decision.candidate_start,
            "candidate_end": decision.candidate_end,
            "exact_text": decision.exact_text,
            "identity_kind": decision.identity_kind.value,
            "identity_decision": decision.identity_decision,
            "identity_name": decision.identity_name,
            "existing_identity_id": decision.existing_identity_id,
            "predicate": decision.predicate,
            "assertion_type": decision.assertion_type.value,
            "source_authority": decision.source_authority.value,
            "attribution_basis": decision.attribution_basis.value,
        },
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class EventConstructionReviewLedger(IdentityOccurrenceAcceptanceLedger, Protocol):
    """The Ledger capabilities the reviewed-decision use case requires."""

    def save_event_construction_review(self, record: EventConstructionReview) -> None: ...

    def get_event_construction_review_for_event(
        self, event_id: str
    ) -> EventConstructionReview | None: ...


def record_event_construction_decision(
    packet: EventReviewPacket,
    decision: EventConstructionDecisionInput,
    repository: EventConstructionReviewLedger,
    *,
    now: datetime,
) -> EventConstructionReview:
    """Validate reviewed decisions and commit the accepted prerequisites.

    The use case accepts the identity occurrence through the existing use case and
    persists one approved construction review bound to the Event's source revision.
    A repeated identical decision returns the stored review and writes nothing.
    """
    validate_packet_bindings(packet)
    if not decision.predicate.strip() or not decision.reviewer.strip():
        raise EventConstructionReviewError("A decision requires one predicate and one reviewer.")
    candidate = next(
        (
            item
            for item in packet.candidates
            if item.start == decision.candidate_start and item.end == decision.candidate_end
        ),
        None,
    )
    if candidate is None or candidate.exact_text != decision.exact_text:
        raise EventConstructionReviewError(
            "The decision does not select one review candidate from this packet."
        )
    digest = decision_sha256(packet, decision)
    existing = repository.get_event_construction_review_for_event(packet.event_id)
    if existing is not None:
        if existing.decision_sha256 == digest:
            return existing
        raise EventConstructionReviewConflict(
            "An approved review for this Event records a different decision."
        )

    proposal_input = IdentityOccurrenceProposalInput(
        identity_kind=decision.identity_kind,
        decision=decision.identity_decision,
        existing_identity_id=decision.existing_identity_id,
        identity_name=decision.identity_name,
        source_id=packet.source_id,
        document_id=packet.document_id,
        representation_id=packet.representation_id,
        text_view_id=packet.text_view_id,
        text_view_digest=packet.text_view_digest,
        start_char=packet.node_start_char + candidate.start,
        end_char=packet.node_start_char + candidate.end,
        exact_text=candidate.exact_text,
        node_id=packet.paragraph_node_id,
    )
    grounding = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name=candidate.identity_name,
    )
    proposal_id = "pcg_" + digest[:24]
    proposal = propose_identity_occurrence(
        grounding, proposal_input, proposal_id=proposal_id, now=now
    )
    repository.save_proposed_change(proposal)
    occurrence = accept_identity_occurrence(proposal, repository, agent=decision.reviewer, now=now)
    statement_start = packet.node_start_char + packet.statement_start
    statement_end = packet.node_start_char + packet.statement_end
    statement_text = packet.source_text[packet.statement_start : packet.statement_end]
    statement_digest = hashlib.sha256(
        f"{packet.source_id}:{packet.document_id}:{packet.text_view_id}:"
        f"{statement_start}:{statement_end}:{statement_text}".encode()
    ).hexdigest()
    statement_target = EvidenceTarget(
        id="etg_" + statement_digest[:24],
        source_id=packet.source_id,
        document_id=packet.document_id,
        representation_id=packet.representation_id,
        text_view_id=packet.text_view_id,
        text_view_digest=packet.text_view_digest,
        start_char=statement_start,
        end_char=statement_end,
        exact_text=statement_text,
        normalization_policy="utf8_identity_v1",
        node_ids=(packet.paragraph_node_id,),
    )
    validate_evidence_target_record(statement_target, repository)
    repository.save_evidence_target(statement_target)

    review_id = "ecr_" + digest[:24]
    provenance_id = (
        "prv_"
        + hashlib.sha256(f"record_event_construction_review:{review_id}".encode()).hexdigest()[:24]
    )
    review = EventConstructionReview(
        id=review_id,
        event_id=packet.event_id,
        ingestion_run_id=packet.ingestion_run_id,
        paragraph_node_id=packet.paragraph_node_id,
        representation_id=packet.representation_id,
        text_view_id=packet.text_view_id,
        source_text_sha256=packet.source_text_sha256,
        source_id=packet.source_id,
        document_id=packet.document_id,
        evidence_target_id=occurrence.evidence_target_id,
        statement_evidence_target_id=statement_target.id,
        identity_occurrence_id=occurrence.id,
        subject_identity_id=occurrence.identity_id,
        subject_identity_kind=occurrence.identity_kind,
        predicate=decision.predicate,
        assertion_type=decision.assertion_type,
        source_authority=decision.source_authority,
        attribution_basis=decision.attribution_basis,
        reviewer=decision.reviewer,
        review_status=ReviewStatus.APPROVED,
        decision_sha256=digest,
        provenance_activity_id=provenance_id,
        created_at=now,
        updated_at=now,
    )
    repository.save_provenance_activity(
        ProvenanceActivity(
            id=provenance_id,
            activity_type="record_event_construction_review",
            agent=decision.reviewer,
            output_ids=(review_id, occurrence.id, occurrence.evidence_target_id),
            occurred_at=now,
        )
    )
    repository.save_event_construction_review(review)
    return review


def assertion_inputs_from_review(
    review: EventConstructionReview, *, relation_label: str, constructed_at: datetime
) -> AssertionConstructionInputs:
    """Build the retained Assertion construction inputs from a review."""
    return AssertionConstructionInputs(
        predicate_by_label={relation_label: review.predicate},
        identity_by_entity={review.subject_identity_id: review.subject_identity_id},
        assertion_type=review.assertion_type,
        source_authority=review.source_authority,
        attribution_basis=review.attribution_basis,
        source_id=review.source_id,
        evidence_target_id=review.statement_evidence_target_id,
        constructed_at=constructed_at,
    )
