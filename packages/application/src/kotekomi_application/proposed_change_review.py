"""ProposedChange review use cases."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from kotekomi_domain import (
    Actor,
    Assertion,
    AssertionStatus,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    ReviewStatus,
)
from kotekomi_domain.models import JsonValue

HASH_ID_LENGTH = 24
APPROVED_ACTIVITY_TYPE = "proposed_change_approved"
REJECTED_ACTIVITY_TYPE = "proposed_change_rejected"
type AcceptedReviewRecord = (
    Actor | Organization | Event | EvidenceSpan | Assertion | Relationship | Outcome
)


class ProposedChangeReviewLedger(Protocol):
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def save_proposed_change(self, record: ProposedChange) -> None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...

    def get_actor(self, record_id: str) -> Actor | None: ...
    def save_actor(self, record: Actor) -> None: ...

    def get_organization(self, record_id: str) -> Organization | None: ...
    def save_organization(self, record: Organization) -> None: ...

    def get_event(self, record_id: str) -> Event | None: ...
    def save_event(self, record: Event) -> None: ...

    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None: ...
    def save_evidence_span(self, record: EvidenceSpan) -> None: ...

    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def save_assertion(self, record: Assertion) -> None: ...

    def get_relationship(self, record_id: str) -> Relationship | None: ...
    def save_relationship(self, record: Relationship) -> None: ...

    def get_outcome(self, record_id: str) -> Outcome | None: ...
    def save_outcome(self, record: Outcome) -> None: ...


@dataclass(frozen=True)
class ReviewProposedChangeInput:
    proposed_change_id: str
    reviewer: str
    reviewed_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class ReviewProposedChangeResult:
    proposed_change_id: str
    review_status: ReviewStatus
    provenance_activity_id: str
    accepted_record_id: str | None = None
    accepted_record_type: str | None = None


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

    ledger_repository.save_provenance_activity(provenance_activity)
    _save_accepted_record(accepted_record, ledger_repository)
    ledger_repository.save_proposed_change(reviewed_change)

    return ReviewProposedChangeResult(
        proposed_change_id=proposed_change.id,
        review_status=ReviewStatus.APPROVED,
        provenance_activity_id=provenance_activity.id,
        accepted_record_id=accepted_record_id,
        accepted_record_type=record_type,
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
    raise ValueError(f"Unsupported ProposedChange record_type: {record_type}")


def _accepted_assertion(
    record_json: dict[str, JsonValue],
    provenance_activity_id: str,
) -> Assertion:
    assertion_json = dict(record_json)
    if assertion_json.get("status") == AssertionStatus.PROPOSED.value:
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
    else:
        ledger_repository.save_outcome(accepted_record)


def _reviewed_proposed_change(
    *,
    proposed_change: ProposedChange,
    review_status: ReviewStatus,
    reviewed_at: datetime,
    accepted_record: AcceptedReviewRecord | None,
) -> ProposedChange:
    accepted_json: dict[str, JsonValue] | None = None
    if accepted_record is not None:
        accepted_json = cast(dict[str, JsonValue], accepted_record.model_dump(mode="json"))
    return ProposedChange(
        id=proposed_change.id,
        review_status=review_status,
        proposed_json=proposed_change.proposed_json,
        original_proposed_json=proposed_change.original_proposed_json,
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
