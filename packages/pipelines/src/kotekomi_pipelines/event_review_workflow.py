"""Operator workflow for one ingested Event: packet, decision, recomposition.

The workflow loads stored ingestion records, builds the review packet, records
one reviewed decision, and recomposes the Event through the retained production
path. It never infers identity, predicate, or classification.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionRecord,
    EventConstructionDecisionInput,
    EventConstructionReviewError,
    EventEntityLinguisticToken,
    EventReviewPacket,
    ReviewCandidateIdentity,
    assertion_inputs_from_review,
    build_constituent_candidate_inventory,
    ingested_grounding_candidates,
    record_event_construction_decision,
    validate_packet_bindings,
)
from kotekomi_application.ingestion_inspection import (
    EventAnnotation,
    ParagraphAnnotationProfile,
    ParagraphInput,
    build_profile,
)
from kotekomi_domain import (
    Assertion,
    EventConstructionReview,
    ProposedAssertion,
    ProposedChange,
)

from kotekomi_pipelines.ingestion_composition_stage import compose_ingested_event
from kotekomi_pipelines.ingestion_token_artifact import load_ingestion_token_artifact
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs

_REQUIRED_DECISIONS = (
    "identity",
    "predicate",
    "assertion_type",
    "source_authority",
    "attribution_basis",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _paragraph_event(
    paragraphs: Sequence[ParagraphInput], event_id: str
) -> tuple[ParagraphInput | None, ParagraphAnnotationProfile | None, EventAnnotation | None]:
    for paragraph in paragraphs:
        profile = build_profile(
            text=paragraph.text,
            representation_id=paragraph.representation_id,
            paragraph_node_id=paragraph.paragraph_node_id,
            node_start_char=paragraph.node_start_char,
            stage_outputs=paragraph.stage_outputs,
            bundle=paragraph.bundle,
        )
        event = next((item for item in profile.events if item.event_id == event_id), None)
        if event is not None:
            return paragraph, profile, event
    return None, None, None


def build_event_review_packet(
    *,
    ledger_path: Path,
    archive_path: Path,
    ingestion_run_id: str,
    event_id: str,
) -> EventReviewPacket:
    """Assemble one Event's review packet from stored ingestion records."""
    try:
        paragraphs = load_paragraph_inputs(
            ledger_path, archive_path, ingestion_run_id=ingestion_run_id
        )
    except (OSError, ValueError, sqlite3.Error) as error:
        raise EventConstructionReviewError(
            f"Ingestion run {ingestion_run_id} is not replayable: {error}"
        ) from error
    paragraph, profile, event = _paragraph_event(paragraphs, event_id)
    if paragraph is None or profile is None or event is None:
        raise EventConstructionReviewError(
            f"Event {event_id} does not belong to ingestion run {ingestion_run_id}."
        )
    bundle = paragraph.bundle
    if bundle is None:
        raise EventConstructionReviewError("The selected Event has no source bundle.")
    artifact = load_ingestion_token_artifact(
        ledger_path.parent / "token-artifacts" / f"{paragraph.paragraph_node_id}.json",
        paragraph_text=paragraph.text,
    )
    node = next(node for node in bundle.nodes if node.id == paragraph.paragraph_node_id)
    view = next(view for view in bundle.text_views if view.id == node.text_view_id)
    trigger = next(
        (
            token
            for token in artifact.tokens
            if (token.start, token.end) == (event.trigger_span.start, event.trigger_span.end)
        ),
        None,
    )
    subject = (
        next(
            (
                token
                for token in artifact.tokens
                if token.dependency_relation in {"nsubj", "nsubj:pass"}
                and token.head_token_id == trigger.token_id
            ),
            None,
        )
        if trigger is not None
        else None
    )
    obj = (
        next(
            (
                token
                for token in artifact.tokens
                if token.dependency_relation in {"obj", "iobj"}
                and token.head_token_id == trigger.token_id
            ),
            None,
        )
        if trigger is not None
        else None
    )
    subject_span = None if subject is None else (subject.start, subject.end)
    candidates = tuple(
        sorted(
            (
                ReviewCandidateIdentity(
                    start=candidate.start,
                    end=candidate.end,
                    exact_text=candidate.exact_text,
                    identity_name=candidate.candidate.identity_name or candidate.exact_text,
                    subject_role=(candidate.start, candidate.end) == subject_span,
                )
                for candidate in ingested_grounding_candidates(
                    text=paragraph.text,
                    representation_id=paragraph.representation_id,
                    paragraph_node_id=paragraph.paragraph_node_id,
                    stage_outputs=paragraph.stage_outputs,
                )
            ),
            key=lambda item: (not item.subject_role, item.start),
        )
    )
    outcome = _outcome_for(ledger_path, event_id)
    with sqlite_ledger_transaction(ledger_path) as repository:
        review = repository.get_event_construction_review_for_event(event_id)
        accepted = tuple(
            occurrence.identity_id for occurrence in repository.list_identity_occurrences()
        )
        document = repository.get_document(bundle.representation.document_id)
        if document is None:
            raise EventConstructionReviewError("The selected Event has no archived Document.")
        source_id = document.source_id
    packet = EventReviewPacket(
        ingestion_run_id=ingestion_run_id,
        event_id=event_id,
        paragraph_node_id=paragraph.paragraph_node_id,
        representation_id=paragraph.representation_id,
        text_view_id=view.id,
        text_view_digest=view.content_digest,
        source_text_sha256=_sha256(paragraph.text),
        source_id=source_id,
        document_id=bundle.representation.document_id,
        node_start_char=paragraph.node_start_char,
        source_text=paragraph.text,
        trigger_start=event.trigger_span.start,
        trigger_end=event.trigger_span.end,
        relation_label=event.trigger_label,
        subject_start=None if subject is None else subject.start,
        subject_end=None if subject is None else subject.end,
        subject_text=None if subject is None else subject.text,
        object_start=None if obj is None else obj.start,
        object_end=None if obj is None else obj.end,
        object_text=None if obj is None else obj.text,
        statement_start=_statement_start(event, subject, obj),
        statement_end=_statement_end(event, subject, obj),
        candidates=candidates,
        accepted_identity_ids=accepted,
        required_decisions=() if review is not None else _REQUIRED_DECISIONS,
        hold_reason=None if outcome is None else outcome.hold_reason,
        existing_review_id=None if review is None else review.id,
        evidence_target_id=None if review is None else review.evidence_target_id,
    )
    validate_packet_bindings(packet)
    return packet


def _statement_start(
    event: EventAnnotation,
    subject: EventEntityLinguisticToken | None,
    obj: EventEntityLinguisticToken | None,
) -> int:
    starts = [event.trigger_span.start]
    if subject is not None:
        starts.append(subject.start)
    if obj is not None:
        starts.append(obj.start)
    return min(starts)


def _statement_end(
    event: EventAnnotation,
    subject: EventEntityLinguisticToken | None,
    obj: EventEntityLinguisticToken | None,
) -> int:
    ends = [event.trigger_span.end]
    if subject is not None:
        ends.append(subject.end)
    if obj is not None:
        ends.append(obj.end)
    return max(ends)


def _outcome_for(ledger_path: Path, event_id: str) -> EventCompositionRecord | None:
    store = CompositionOutcomeStore(ledger_path.parent / "composition-outcomes")
    try:
        return store.load(event_id)
    except FileNotFoundError:
        return None


def record_review_decision(
    *,
    ledger_path: Path,
    archive_path: Path,
    ingestion_run_id: str,
    event_id: str,
    decision: EventConstructionDecisionInput,
    now: datetime,
) -> EventConstructionReview:
    """Record one reviewed decision and commit its accepted prerequisites."""
    packet = build_event_review_packet(
        ledger_path=ledger_path,
        archive_path=archive_path,
        ingestion_run_id=ingestion_run_id,
        event_id=event_id,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        return record_event_construction_decision(packet, decision, repository, now=now)


def recompose_reviewed_event(
    *,
    ledger_path: Path,
    archive_path: Path,
    ingestion_run_id: str,
    event_id: str,
    now: datetime,
) -> EventCompositionRecord:
    """Recompose one reviewed Event and expose its pending Assertion proposal."""
    packet = build_event_review_packet(
        ledger_path=ledger_path,
        archive_path=archive_path,
        ingestion_run_id=ingestion_run_id,
        event_id=event_id,
    )
    paragraphs = load_paragraph_inputs(ledger_path, archive_path, ingestion_run_id=ingestion_run_id)
    paragraph, profile, event = _paragraph_event(paragraphs, event_id)
    if paragraph is None or profile is None or event is None:
        raise EventConstructionReviewError("The selected Event is no longer in this run.")
    artifact = load_ingestion_token_artifact(
        ledger_path.parent / "token-artifacts" / f"{paragraph.paragraph_node_id}.json",
        paragraph_text=paragraph.text,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        review = repository.get_event_construction_review_for_event(event_id)
        if review is None:
            raise EventConstructionReviewError(
                "The Event has no approved construction review; record the decisions first."
            )
        if review.source_text_sha256 != artifact.source_text_sha256:
            raise EventConstructionReviewError(
                "The approved review belongs to a different source revision."
            )
        inventory = build_constituent_candidate_inventory(
            source_text=paragraph.text,
            event_id=event_id,
            tokens=artifact.tokens,
            event_expression_start=event.trigger_span.start,
            event_expression_end=event.trigger_span.end,
        )
        record = compose_ingested_event(
            repository=repository,
            event_id=event_id,
            source_text=paragraph.text,
            source_text_sha256=artifact.source_text_sha256,
            inventory=inventory,
            trigger_head_start=event.trigger_span.start,
            trigger_head_end=event.trigger_span.end,
            tokens=artifact.tokens,
            assertion_inputs=assertion_inputs_from_review(
                review, relation_label=packet.relation_label, constructed_at=now
            ),
            representation_id=paragraph.representation_id,
            text_view_id=artifact.text_view_id,
            node_start_char=paragraph.node_start_char,
        )
        if record.assertion is not None:
            _upsert_assertion_proposal(record.assertion, review, repository, now)
    # The transaction commits the canonical proposal before the derived outcome.
    CompositionOutcomeStore(ledger_path.parent / "composition-outcomes").save(record)
    return record


def _proposal_payload(assertion: Assertion, review: EventConstructionReview) -> dict[str, Any]:
    proposed = ProposedAssertion(
        id=assertion.id,
        assertion_type=assertion.assertion_type,
        epistemic_scope=assertion.epistemic_scope,
        subject_entity_id=assertion.subject_entity_id,
        subject_value=assertion.subject_value,
        relation_label=review.predicate,
        object_entity_id=assertion.object_entity_id,
        object_value=assertion.object_value,
        source_authority=assertion.source_authority,
        attribution_basis=assertion.attribution_basis,
        attributed_to_id=assertion.attributed_to_id,
        qualifiers=assertion.qualifiers,
        source_ids=assertion.source_ids,
        evidence_target_ids=assertion.evidence_target_ids,
    )
    return {
        "record_type": "Assertion",
        "stable_label": assertion.id,
        "record": proposed.model_dump(mode="json"),
    }


class AssertionProposalLedger(Protocol):
    """Proposal persistence the recomposition step requires."""

    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...

    def save_proposed_change(self, record: ProposedChange) -> None: ...


def _upsert_assertion_proposal(
    assertion: Assertion,
    review: EventConstructionReview,
    repository: AssertionProposalLedger,
    now: datetime,
) -> ProposedChange:
    payload = _proposal_payload(assertion, review)
    proposal_id = (
        "pcg_"
        + hashlib.sha256(
            f"assertion_proposal:{review.event_id}:{review.decision_sha256}:{assertion.id}".encode()
        ).hexdigest()[:24]
    )
    existing = repository.get_proposed_change(proposal_id)
    if existing is not None:
        if existing.proposed_json != payload:
            raise EventConstructionReviewError(
                "A different pending proposal already exists for this Event decision."
            )
        return existing
    proposal = ProposedChange(
        id=proposal_id,
        proposed_json=payload,
        source_id=review.source_id,
        document_id=review.document_id,
        model_name=None,
        prompt_id=None,
        created_at=now,
        updated_at=now,
    )
    repository.save_proposed_change(proposal)
    return proposal
