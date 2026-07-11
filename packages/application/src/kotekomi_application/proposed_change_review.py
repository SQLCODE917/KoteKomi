"""ProposedChange review use cases."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, cast

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionEvidenceLink,
    AssertionEvidenceRole,
    AssertionStatus,
    AssertionType,
    Document,
    Entity,
    Event,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    ReviewStatus,
    Source,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.evidence_targets import (
    EvidenceTargetLedger,
    deterministic_assertion_evidence_link_id,
    verify_evidence_target,
)
from kotekomi_application.review_queue_packet import (
    ReviewNextInput,
    ReviewPacket,
    ReviewPacketInput,
    ReviewQueueInput,
    ReviewQueueItem,
    ReviewQueuePacketLedger,
    get_review_next,
    get_review_packet,
    list_review_queue,
    review_packet_to_json,
)

HASH_ID_LENGTH = 24
APPROVED_ACTIVITY_TYPE = "proposed_change_approved"
REJECTED_ACTIVITY_TYPE = "proposed_change_rejected"
EDITED_ACTIVITY_TYPE = "proposed_change_edited"
type AcceptedReviewRecord = (
    Actor | Organization | Event | EvidenceSpan | Assertion | Relationship | Outcome | ArgumentEdge
)


class AssertionEvidenceLinkWriter(Protocol):
    def save_assertion_evidence_link(self, record: AssertionEvidenceLink) -> None: ...


class ProposedChangeReviewLedger(Protocol):
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def save_proposed_change(self, record: ProposedChange) -> None: ...
    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...

    def get_entity(self, record_id: str) -> Entity | None: ...

    def get_actor(self, record_id: str) -> Actor | None: ...
    def save_actor(self, record: Actor) -> None: ...

    def get_organization(self, record_id: str) -> Organization | None: ...
    def save_organization(self, record: Organization) -> None: ...

    def get_event(self, record_id: str) -> Event | None: ...
    def save_event(self, record: Event) -> None: ...

    def get_place(self, record_id: str) -> Place | None: ...

    def get_source(self, record_id: str) -> Source | None: ...

    def get_document(self, record_id: str) -> Document | None: ...

    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None: ...
    def save_evidence_span(self, record: EvidenceSpan) -> None: ...

    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def save_assertion(self, record: Assertion) -> None: ...

    def get_relationship(self, record_id: str) -> Relationship | None: ...
    def save_relationship(self, record: Relationship) -> None: ...

    def get_outcome(self, record_id: str) -> Outcome | None: ...
    def save_outcome(self, record: Outcome) -> None: ...

    def get_argument_edge(self, record_id: str) -> ArgumentEdge | None: ...
    def save_argument_edge(self, record: ArgumentEdge) -> None: ...


class ReviewNextDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class ReviewDrainStoppedReason(StrEnum):
    QUEUE_EMPTY = "queue_empty"
    LIMIT_REACHED = "limit_reached"
    VALIDATION_FAILED = "validation_failed"
    DRY_RUN_COMPLETE = "dry_run_complete"


class ReviewNextDecisionLedger(ProposedChangeReviewLedger, ReviewQueuePacketLedger, Protocol):
    pass


@dataclass(frozen=True)
class ReviewProposedChangeInput:
    proposed_change_id: str
    reviewer: str
    reviewed_at: datetime
    reason: str | None = None
    accepted_record_json: dict[str, JsonValue] | None = None


@dataclass(frozen=True)
class ReviewProposedChangeResult:
    proposed_change_id: str
    review_status: ReviewStatus
    provenance_activity_id: str
    accepted_record_id: str | None = None
    accepted_record_type: str | None = None
    assertion_evidence_link_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewNextDecisionInput:
    decision: ReviewNextDecision
    reviewer: str
    reviewed_at: datetime
    record_type: str | None = None
    source_id: str | None = None
    document_id: str | None = None
    reason: str | None = None
    accepted_record_json: dict[str, JsonValue] | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class ReviewNextDecisionResult:
    has_next: bool
    item: ReviewQueueItem | None
    packet: ReviewPacket | None
    decision: ReviewNextDecision
    executed: bool
    dry_run: bool
    review_result: ReviewProposedChangeResult | None = None


@dataclass(frozen=True)
class ReviewDrainInput:
    decision: ReviewNextDecision
    reviewer: str
    reviewed_at: datetime
    record_type: str | None = None
    source_id: str | None = None
    document_id: str | None = None
    reason: str | None = None
    accepted_record_json: dict[str, JsonValue] | None = None
    limit: int | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class ReviewDrainResult:
    decision: ReviewNextDecision
    attempted_count: int
    executed_count: int
    dry_run: bool
    stopped_reason: ReviewDrainStoppedReason
    item_results: tuple[ReviewNextDecisionResult, ...]
    error_message: str | None = None


def run_review_next_decision(
    review_input: ReviewNextDecisionInput,
    ledger_repository: ReviewNextDecisionLedger,
) -> ReviewNextDecisionResult:
    next_result = get_review_next(
        ReviewNextInput(
            record_type=review_input.record_type,
            source_id=review_input.source_id,
            document_id=review_input.document_id,
        ),
        ledger_repository,
    )
    if not next_result.has_next:
        return ReviewNextDecisionResult(
            has_next=False,
            item=None,
            packet=None,
            decision=review_input.decision,
            executed=False,
            dry_run=review_input.dry_run,
            review_result=None,
        )
    if next_result.item is None or next_result.packet is None:
        raise ValueError("ReviewNextResult has_next=true without item and packet.")
    _validate_review_next_decision_input(review_input)
    if review_input.dry_run:
        return ReviewNextDecisionResult(
            has_next=True,
            item=next_result.item,
            packet=next_result.packet,
            decision=review_input.decision,
            executed=False,
            dry_run=True,
            review_result=None,
        )
    result = _run_review_decision(
        review_input=review_input,
        proposed_change_id=next_result.item.proposed_change_id,
        ledger_repository=ledger_repository,
    )
    return ReviewNextDecisionResult(
        has_next=True,
        item=next_result.item,
        packet=next_result.packet,
        decision=review_input.decision,
        executed=True,
        dry_run=False,
        review_result=result,
    )


def review_next_decision_result_to_json(
    result: ReviewNextDecisionResult,
) -> dict[str, JsonValue]:
    return {
        "has_next": result.has_next,
        "item": _review_queue_item_to_json(result.item),
        "packet": review_packet_to_json(result.packet) if result.packet is not None else None,
        "decision": result.decision.value,
        "executed": result.executed,
        "dry_run": result.dry_run,
        "review_result": _review_proposed_change_result_to_json(result.review_result),
    }


def run_review_drain(
    review_input: ReviewDrainInput,
    ledger_repository: ReviewNextDecisionLedger,
) -> ReviewDrainResult:
    _validate_review_drain_input(review_input)
    if review_input.dry_run:
        return _run_review_drain_dry_run(review_input, ledger_repository)

    item_results: list[ReviewNextDecisionResult] = []
    while _can_continue_drain(review_input, item_results):
        try:
            item_result = run_review_next_decision(
                _drain_item_input(review_input, dry_run=False),
                ledger_repository,
            )
        except ValueError as error:
            return ReviewDrainResult(
                decision=review_input.decision,
                attempted_count=len(item_results) + 1,
                executed_count=_executed_count(item_results),
                dry_run=False,
                stopped_reason=ReviewDrainStoppedReason.VALIDATION_FAILED,
                item_results=tuple(item_results),
                error_message=str(error),
            )
        if not item_result.has_next:
            return ReviewDrainResult(
                decision=review_input.decision,
                attempted_count=len(item_results),
                executed_count=_executed_count(item_results),
                dry_run=False,
                stopped_reason=ReviewDrainStoppedReason.QUEUE_EMPTY,
                item_results=tuple(item_results),
            )
        item_results.append(item_result)

    return ReviewDrainResult(
        decision=review_input.decision,
        attempted_count=len(item_results),
        executed_count=_executed_count(item_results),
        dry_run=False,
        stopped_reason=ReviewDrainStoppedReason.LIMIT_REACHED,
        item_results=tuple(item_results),
    )


def review_drain_result_to_json(result: ReviewDrainResult) -> dict[str, JsonValue]:
    return {
        "decision": result.decision.value,
        "attempted_count": result.attempted_count,
        "executed_count": result.executed_count,
        "dry_run": result.dry_run,
        "stopped_reason": result.stopped_reason.value,
        "item_results": [
            review_next_decision_result_to_json(item_result) for item_result in result.item_results
        ],
        "error_message": result.error_message,
    }


def _run_review_drain_dry_run(
    review_input: ReviewDrainInput,
    ledger_repository: ReviewNextDecisionLedger,
) -> ReviewDrainResult:
    queue = list_review_queue(
        ReviewQueueInput(
            record_type=review_input.record_type,
            source_id=review_input.source_id,
            document_id=review_input.document_id,
        ),
        ledger_repository,
    )
    selected_items = queue.items
    if review_input.limit is not None:
        selected_items = selected_items[: review_input.limit]
    item_results = tuple(
        ReviewNextDecisionResult(
            has_next=True,
            item=item,
            packet=get_review_packet(
                ReviewPacketInput(proposed_change_id=item.proposed_change_id),
                ledger_repository,
            ),
            decision=review_input.decision,
            executed=False,
            dry_run=True,
            review_result=None,
        )
        for item in selected_items
    )
    if not item_results and review_input.limit == 0 and queue.items:
        stopped_reason = ReviewDrainStoppedReason.LIMIT_REACHED
    elif not item_results:
        stopped_reason = ReviewDrainStoppedReason.QUEUE_EMPTY
    elif review_input.limit is not None and len(queue.items) > review_input.limit:
        stopped_reason = ReviewDrainStoppedReason.LIMIT_REACHED
    else:
        stopped_reason = ReviewDrainStoppedReason.DRY_RUN_COMPLETE
    return ReviewDrainResult(
        decision=review_input.decision,
        attempted_count=len(item_results),
        executed_count=0,
        dry_run=True,
        stopped_reason=stopped_reason,
        item_results=item_results,
    )


def _validate_review_next_decision_input(review_input: ReviewNextDecisionInput) -> None:
    if not review_input.reviewer.strip():
        raise ValueError("Review-Next decision requires reviewer.")
    if review_input.decision is ReviewNextDecision.REJECT and not (
        review_input.reason and review_input.reason.strip()
    ):
        raise ValueError("Review-Next reject decision requires reason.")
    if (
        review_input.decision is ReviewNextDecision.EDIT
        and review_input.accepted_record_json is None
    ):
        raise ValueError("Review-Next edit decision requires accepted_record_json.")


def _validate_review_drain_input(review_input: ReviewDrainInput) -> None:
    _validate_review_next_decision_input(_drain_item_input(review_input, dry_run=False))
    if review_input.limit is not None and review_input.limit < 0:
        raise ValueError("Review Drain limit must be zero or greater.")


def _drain_item_input(
    review_input: ReviewDrainInput,
    *,
    dry_run: bool,
) -> ReviewNextDecisionInput:
    return ReviewNextDecisionInput(
        decision=review_input.decision,
        reviewer=review_input.reviewer,
        reviewed_at=review_input.reviewed_at,
        record_type=review_input.record_type,
        source_id=review_input.source_id,
        document_id=review_input.document_id,
        reason=review_input.reason,
        accepted_record_json=review_input.accepted_record_json,
        dry_run=dry_run,
    )


def _can_continue_drain(
    review_input: ReviewDrainInput,
    item_results: list[ReviewNextDecisionResult],
) -> bool:
    return review_input.limit is None or len(item_results) < review_input.limit


def _executed_count(item_results: list[ReviewNextDecisionResult]) -> int:
    return sum(1 for item_result in item_results if item_result.executed)


def _run_review_decision(
    *,
    review_input: ReviewNextDecisionInput,
    proposed_change_id: str,
    ledger_repository: ReviewNextDecisionLedger,
) -> ReviewProposedChangeResult:
    proposed_review_input = ReviewProposedChangeInput(
        proposed_change_id=proposed_change_id,
        reviewer=review_input.reviewer,
        reviewed_at=review_input.reviewed_at,
        reason=review_input.reason,
        accepted_record_json=review_input.accepted_record_json,
    )
    if review_input.decision is ReviewNextDecision.APPROVE:
        return approve_proposed_change(proposed_review_input, ledger_repository)
    if review_input.decision is ReviewNextDecision.REJECT:
        return reject_proposed_change(proposed_review_input, ledger_repository)
    if review_input.decision is ReviewNextDecision.EDIT:
        return edit_proposed_change(proposed_review_input, ledger_repository)
    raise ValueError(f"Unsupported Review-Next decision: {review_input.decision}")


def _review_queue_item_to_json(item: ReviewQueueItem | None) -> dict[str, JsonValue] | None:
    if item is None:
        return None
    return {
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


def _review_proposed_change_result_to_json(
    result: ReviewProposedChangeResult | None,
) -> dict[str, JsonValue] | None:
    if result is None:
        return None
    return {
        "proposed_change_id": result.proposed_change_id,
        "review_status": result.review_status.value,
        "provenance_activity_id": result.provenance_activity_id,
        "accepted_record_id": result.accepted_record_id,
        "accepted_record_type": result.accepted_record_type,
    }


def approve_proposed_change(
    review_input: ReviewProposedChangeInput,
    ledger_repository: ProposedChangeReviewLedger,
) -> ReviewProposedChangeResult:
    proposed_change = _get_pending_proposed_change(review_input, ledger_repository)
    record_type = _proposal_record_type(proposed_change)
    provenance_activity_id = deterministic_review_provenance_activity_id(
        proposed_change_id=proposed_change.id,
        activity_type=APPROVED_ACTIVITY_TYPE,
        reviewer=review_input.reviewer,
    )
    accepted_record = _accepted_record_from_proposed_change(
        proposed_change=proposed_change,
        provenance_activity_id=provenance_activity_id,
    )
    accepted_record_id = _record_id(accepted_record)
    provenance_activity = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=APPROVED_ACTIVITY_TYPE,
        agent=review_input.reviewer,
        input_ids=(proposed_change.id,),
        output_ids=(accepted_record_id,),
        occurred_at=review_input.reviewed_at,
    )
    reviewed_change = _reviewed_proposed_change(
        proposed_change=proposed_change,
        review_status=ReviewStatus.APPROVED,
        reviewed_at=review_input.reviewed_at,
        accepted_record=accepted_record,
    )
    _validate_accepted_record_references(
        accepted_record=accepted_record,
        pending_provenance_activity=provenance_activity,
        ledger_repository=ledger_repository,
    )
    evidence_links = _prepared_assertion_evidence_links(
        proposed_change,
        accepted_record,
        provenance_activity_id,
        review_input.reviewed_at,
        ledger_repository,
    )

    ledger_repository.save_provenance_activity(provenance_activity)
    _save_accepted_record(accepted_record, ledger_repository)
    for evidence_link in evidence_links:
        cast("AssertionEvidenceLinkWriter", ledger_repository).save_assertion_evidence_link(
            evidence_link
        )
    ledger_repository.save_proposed_change(reviewed_change)

    return ReviewProposedChangeResult(
        proposed_change_id=proposed_change.id,
        review_status=ReviewStatus.APPROVED,
        provenance_activity_id=provenance_activity.id,
        accepted_record_id=accepted_record_id,
        accepted_record_type=record_type,
        assertion_evidence_link_ids=tuple(link.id for link in evidence_links),
    )


def reject_proposed_change(
    review_input: ReviewProposedChangeInput,
    ledger_repository: ProposedChangeReviewLedger,
) -> ReviewProposedChangeResult:
    proposed_change = _get_pending_proposed_change(review_input, ledger_repository)
    provenance_activity_id = deterministic_review_provenance_activity_id(
        proposed_change_id=proposed_change.id,
        activity_type=REJECTED_ACTIVITY_TYPE,
        reviewer=review_input.reviewer,
    )
    provenance_activity = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=REJECTED_ACTIVITY_TYPE,
        agent=review_input.reviewer,
        input_ids=(proposed_change.id,),
        output_ids=(proposed_change.id,),
        occurred_at=review_input.reviewed_at,
    )
    reviewed_change = _reviewed_proposed_change(
        proposed_change=proposed_change,
        review_status=ReviewStatus.REJECTED,
        reviewed_at=review_input.reviewed_at,
        accepted_record=None,
    )

    ledger_repository.save_provenance_activity(provenance_activity)
    ledger_repository.save_proposed_change(reviewed_change)

    return ReviewProposedChangeResult(
        proposed_change_id=proposed_change.id,
        review_status=ReviewStatus.REJECTED,
        provenance_activity_id=provenance_activity.id,
    )


def edit_proposed_change(
    review_input: ReviewProposedChangeInput,
    ledger_repository: ProposedChangeReviewLedger,
) -> ReviewProposedChangeResult:
    proposed_change = _get_pending_proposed_change(review_input, ledger_repository)
    record_type = _proposal_record_type(proposed_change)
    if review_input.accepted_record_json is None:
        raise ValueError("Edited ProposedChange requires accepted_record_json.")
    provenance_activity_id = deterministic_review_provenance_activity_id(
        proposed_change_id=proposed_change.id,
        activity_type=EDITED_ACTIVITY_TYPE,
        reviewer=review_input.reviewer,
    )
    accepted_record = _accepted_record_from_json(
        record_type=record_type,
        record_json=review_input.accepted_record_json,
        provenance_activity_id=provenance_activity_id,
    )
    accepted_record_id = _record_id(accepted_record)
    provenance_activity = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=EDITED_ACTIVITY_TYPE,
        agent=review_input.reviewer,
        input_ids=(proposed_change.id,),
        output_ids=(accepted_record_id,),
        occurred_at=review_input.reviewed_at,
    )
    reviewed_change = _reviewed_proposed_change(
        proposed_change=proposed_change,
        review_status=ReviewStatus.EDITED,
        reviewed_at=review_input.reviewed_at,
        accepted_record=accepted_record,
        original_proposed_json=proposed_change.proposed_json,
    )
    _validate_accepted_record_references(
        accepted_record=accepted_record,
        pending_provenance_activity=provenance_activity,
        ledger_repository=ledger_repository,
    )

    ledger_repository.save_provenance_activity(provenance_activity)
    _save_accepted_record(accepted_record, ledger_repository)
    ledger_repository.save_proposed_change(reviewed_change)

    return ReviewProposedChangeResult(
        proposed_change_id=proposed_change.id,
        review_status=ReviewStatus.EDITED,
        provenance_activity_id=provenance_activity.id,
        accepted_record_id=accepted_record_id,
        accepted_record_type=record_type,
    )


def deterministic_review_provenance_activity_id(
    *,
    proposed_change_id: str,
    activity_type: str,
    reviewer: str,
) -> str:
    digest = hashlib.sha256(f"{proposed_change_id}:{activity_type}:{reviewer}".encode()).hexdigest()
    return f"prv_{digest[:HASH_ID_LENGTH]}"


def _get_pending_proposed_change(
    review_input: ReviewProposedChangeInput,
    ledger_repository: ProposedChangeReviewLedger,
) -> ProposedChange:
    proposed_change = ledger_repository.get_proposed_change(review_input.proposed_change_id)
    if proposed_change is None:
        raise ValueError(f"ProposedChange not found: {review_input.proposed_change_id}")
    if proposed_change.review_status is not ReviewStatus.PENDING:
        raise ValueError(f"ProposedChange is not pending: {review_input.proposed_change_id}")
    return proposed_change


def _proposal_record_type(proposed_change: ProposedChange) -> str:
    record_type = proposed_change.proposed_json.get("record_type")
    if not isinstance(record_type, str) or not record_type.strip():
        raise ValueError(f"ProposedChange missing record_type: {proposed_change.id}")
    return record_type


def _proposal_record_json(proposed_change: ProposedChange) -> dict[str, JsonValue]:
    record = proposed_change.proposed_json.get("record")
    if not isinstance(record, dict):
        raise ValueError(f"ProposedChange missing record object: {proposed_change.id}")
    return cast(dict[str, JsonValue], record)


def _accepted_record_from_proposed_change(
    *,
    proposed_change: ProposedChange,
    provenance_activity_id: str,
) -> AcceptedReviewRecord:
    record_type = _proposal_record_type(proposed_change)
    record_json = _proposal_record_json(proposed_change)
    return _accepted_record_from_json(
        record_type=record_type,
        record_json=record_json,
        provenance_activity_id=provenance_activity_id,
    )


def _accepted_record_from_json(
    *,
    record_type: str,
    record_json: dict[str, JsonValue],
    provenance_activity_id: str,
) -> AcceptedReviewRecord:
    if record_type == "Actor":
        return Actor.model_validate_json(json.dumps(record_json))
    if record_type == "Organization":
        return Organization.model_validate_json(json.dumps(record_json))
    if record_type == "Event":
        return Event.model_validate_json(json.dumps(record_json))
    if record_type == "EvidenceSpan":
        return EvidenceSpan.model_validate_json(json.dumps(record_json))
    if record_type == "Assertion":
        return _accepted_assertion(record_json, provenance_activity_id)
    if record_type == "Relationship":
        return Relationship.model_validate_json(json.dumps(record_json))
    if record_type == "Outcome":
        return Outcome.model_validate_json(json.dumps(record_json))
    if record_type == "ArgumentEdge":
        return ArgumentEdge.model_validate_json(json.dumps(record_json))
    raise ValueError(f"Unsupported ProposedChange record_type: {record_type}")


def _accepted_assertion(
    record_json: dict[str, JsonValue],
    provenance_activity_id: str,
) -> Assertion:
    assertion_json = dict(record_json)
    if assertion_json.get("status") == AssertionStatus.PROPOSED.value:
        if assertion_json.get("assertion_type") == AssertionType.ANALYTIC_INFERENCE.value:
            assertion_json["status"] = AssertionStatus.CORROBORATED.value
        else:
            assertion_json["status"] = AssertionStatus.REPORTED.value
    existing_provenance_ids = assertion_json.get("provenance_activity_ids")
    if existing_provenance_ids is None:
        provenance_ids: list[JsonValue] = []
    elif isinstance(existing_provenance_ids, list):
        provenance_ids = list(existing_provenance_ids)
    else:
        raise ValueError("Assertion proposal provenance_activity_ids must be an array.")
    if provenance_activity_id not in provenance_ids:
        provenance_ids.append(provenance_activity_id)
    assertion_json["provenance_activity_ids"] = provenance_ids
    return Assertion.model_validate_json(json.dumps(assertion_json))


def _prepared_assertion_evidence_links(
    proposed_change: ProposedChange,
    accepted_record: AcceptedReviewRecord,
    provenance_id: str,
    reviewed_at: datetime,
    ledger_repository: ProposedChangeReviewLedger,
) -> tuple[AssertionEvidenceLink, ...]:
    if not isinstance(accepted_record, Assertion):
        return ()
    specifications = proposed_change.proposed_json.get("evidence_links")
    if specifications is None:
        return ()  # Explicit legacy compatibility: not an authoritative evidence proposal.
    if not isinstance(specifications, list):
        raise ValueError("Assertion evidence_links must be an array.")
    links: list[AssertionEvidenceLink] = []
    for specification in specifications:
        if not isinstance(specification, dict):
            raise ValueError("Assertion evidence link must be an object.")
        evidence_id = specification.get("evidence_span_id")
        if not isinstance(evidence_id, str):
            raise ValueError("Assertion evidence link requires evidence_span_id.")
        evidence = ledger_repository.get_evidence_span(evidence_id)
        evidence_ledger = cast("EvidenceTargetLedger", ledger_repository)
        if evidence is None or not verify_evidence_target(evidence, evidence_ledger).valid:
            raise ValueError(
                "Assertion evidence link requires a replayable validated EvidenceSpan."
            )
        if (
            evidence.source_id not in accepted_record.source_ids
            or evidence.id not in accepted_record.evidence_span_ids
        ):
            raise ValueError("Assertion evidence link must belong to the accepted Assertion.")
        role = AssertionEvidenceRole(specification.get("role"))
        polarity = EvidencePolarity(specification.get("polarity"))
        necessity = EvidenceNecessity(specification.get("necessity"))
        links.append(
            AssertionEvidenceLink(
                id=deterministic_assertion_evidence_link_id(
                    assertion_id=accepted_record.id,
                    evidence_span_id=evidence.id,
                    role=role,
                    polarity=polarity,
                    necessity=necessity,
                ),
                assertion_id=accepted_record.id,
                evidence_span_id=evidence.id,
                role=role,
                polarity=polarity,
                necessity=necessity,
                provenance_id=provenance_id,
                created_at=reviewed_at,
            )
        )
    if accepted_record.source_ids and not any(
        link.role is AssertionEvidenceRole.DIRECT_SUPPORT
        and link.polarity is EvidencePolarity.SUPPORTS
        for link in links
    ):
        raise ValueError("Source-backed Assertion requires validated direct_support evidence.")
    return tuple(links)


def _validate_accepted_record_references(
    *,
    accepted_record: AcceptedReviewRecord,
    pending_provenance_activity: ProvenanceActivity,
    ledger_repository: ProposedChangeReviewLedger,
) -> None:
    if isinstance(accepted_record, Actor):
        for organization_id in accepted_record.organization_ids:
            _require_organization(ledger_repository, organization_id, accepted_record.id)
    elif isinstance(accepted_record, Organization):
        return
    elif isinstance(accepted_record, Event):
        if accepted_record.place_id is not None:
            _require_place(ledger_repository, accepted_record.place_id, accepted_record.id)
        for actor_id in accepted_record.participant_actor_ids:
            _require_actor(ledger_repository, actor_id, accepted_record.id)
        for organization_id in accepted_record.participant_organization_ids:
            _require_organization(ledger_repository, organization_id, accepted_record.id)
    elif isinstance(accepted_record, EvidenceSpan):
        _require_source(ledger_repository, accepted_record.source_id, accepted_record.id)
        _require_document(ledger_repository, accepted_record.document_id, accepted_record.id)
        if accepted_record.assertion_id is not None:
            _require_assertion(ledger_repository, accepted_record.assertion_id, accepted_record.id)
    elif isinstance(accepted_record, Assertion):
        _require_entity_reference(
            ledger_repository,
            accepted_record.subject_entity_id,
            accepted_record.id,
        )
        if accepted_record.object_entity_id is not None:
            _require_entity_reference(
                ledger_repository,
                accepted_record.object_entity_id,
                accepted_record.id,
            )
        for source_id in accepted_record.source_ids:
            _require_source(ledger_repository, source_id, accepted_record.id)
        for evidence_span_id in accepted_record.evidence_span_ids:
            _require_evidence_span(ledger_repository, evidence_span_id, accepted_record.id)
        for provenance_activity_id in accepted_record.provenance_activity_ids:
            _require_provenance_activity(
                ledger_repository,
                provenance_activity_id,
                accepted_record.id,
                pending_provenance_activity.id,
            )
    elif isinstance(accepted_record, Relationship):
        _require_entity_reference(ledger_repository, accepted_record.subject_id, accepted_record.id)
        _require_entity_reference(ledger_repository, accepted_record.object_id, accepted_record.id)
        for assertion_id in accepted_record.assertion_ids:
            _require_assertion(ledger_repository, assertion_id, accepted_record.id)
    elif isinstance(accepted_record, Outcome):
        for actor_id in accepted_record.actor_ids:
            _require_actor(ledger_repository, actor_id, accepted_record.id)
        for organization_id in accepted_record.organization_ids:
            _require_organization(ledger_repository, organization_id, accepted_record.id)
        for event_id in accepted_record.event_ids:
            _require_event(ledger_repository, event_id, accepted_record.id)
        for assertion_id in accepted_record.assertion_ids:
            _require_assertion(ledger_repository, assertion_id, accepted_record.id)
    elif type(accepted_record) is ArgumentEdge:
        argument_edge = accepted_record
        _require_assertion(ledger_repository, argument_edge.from_assertion_id, argument_edge.id)
        _require_assertion(ledger_repository, argument_edge.to_assertion_id, argument_edge.id)
        for evidence_span_id in argument_edge.evidence_span_ids:
            _require_evidence_span(ledger_repository, evidence_span_id, argument_edge.id)
    else:
        raise TypeError(f"Unsupported accepted record type: {type(accepted_record).__name__}")


def _require_entity_reference(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if record_id.startswith("ent_"):
        if ledger_repository.get_entity(record_id) is not None:
            return
    elif record_id.startswith("act_"):
        if ledger_repository.get_actor(record_id) is not None:
            return
    elif record_id.startswith("org_"):
        if ledger_repository.get_organization(record_id) is not None:
            return
    elif record_id.startswith("evt_"):
        if ledger_repository.get_event(record_id) is not None:
            return
    elif record_id.startswith("plc_") and ledger_repository.get_place(record_id) is not None:
        return
    raise ValueError(
        f"Accepted record {referring_record_id} references missing entity record: {record_id}"
    )


def _require_actor(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_actor(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing Actor: {record_id}"
        )


def _require_organization(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_organization(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing Organization: {record_id}"
        )


def _require_event(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_event(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing Event: {record_id}"
        )


def _require_place(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_place(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing Place: {record_id}"
        )


def _require_source(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_source(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing Source: {record_id}"
        )


def _require_document(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_document(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing Document: {record_id}"
        )


def _require_evidence_span(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_evidence_span(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing EvidenceSpan: {record_id}"
        )


def _require_assertion(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
) -> None:
    if ledger_repository.get_assertion(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing Assertion: {record_id}"
        )


def _require_provenance_activity(
    ledger_repository: ProposedChangeReviewLedger,
    record_id: str,
    referring_record_id: str,
    pending_provenance_activity_id: str,
) -> None:
    if record_id == pending_provenance_activity_id:
        return
    if ledger_repository.get_provenance_activity(record_id) is None:
        raise ValueError(
            f"Accepted record {referring_record_id} references missing ProvenanceActivity: "
            f"{record_id}"
        )


def _save_accepted_record(
    accepted_record: AcceptedReviewRecord,
    ledger_repository: ProposedChangeReviewLedger,
) -> None:
    if isinstance(accepted_record, Actor):
        ledger_repository.save_actor(accepted_record)
    elif isinstance(accepted_record, Organization):
        ledger_repository.save_organization(accepted_record)
    elif isinstance(accepted_record, Event):
        ledger_repository.save_event(accepted_record)
    elif isinstance(accepted_record, EvidenceSpan):
        ledger_repository.save_evidence_span(accepted_record)
    elif isinstance(accepted_record, Assertion):
        ledger_repository.save_assertion(accepted_record)
    elif isinstance(accepted_record, Relationship):
        ledger_repository.save_relationship(accepted_record)
    elif isinstance(accepted_record, Outcome):
        ledger_repository.save_outcome(accepted_record)
    elif type(accepted_record) is ArgumentEdge:
        argument_edge = accepted_record
        ledger_repository.save_argument_edge(argument_edge)
    else:
        raise TypeError(f"Unsupported accepted record type: {type(accepted_record).__name__}")


def _reviewed_proposed_change(
    *,
    proposed_change: ProposedChange,
    review_status: ReviewStatus,
    reviewed_at: datetime,
    accepted_record: AcceptedReviewRecord | None,
    original_proposed_json: dict[str, JsonValue] | None = None,
) -> ProposedChange:
    accepted_json: dict[str, JsonValue] | None = None
    if accepted_record is not None:
        accepted_json = cast(dict[str, JsonValue], accepted_record.model_dump(mode="json"))
    return ProposedChange(
        id=proposed_change.id,
        review_status=review_status,
        proposed_json=proposed_change.proposed_json,
        original_proposed_json=original_proposed_json
        if original_proposed_json is not None
        else proposed_change.original_proposed_json,
        accepted_json=accepted_json,
        source_id=proposed_change.source_id,
        document_id=proposed_change.document_id,
        model_name=proposed_change.model_name,
        prompt_id=proposed_change.prompt_id,
        provenance_activity_id=proposed_change.provenance_activity_id,
        created_at=proposed_change.created_at,
        updated_at=reviewed_at,
    )


def _record_id(record: AcceptedReviewRecord) -> str:
    return record.id
