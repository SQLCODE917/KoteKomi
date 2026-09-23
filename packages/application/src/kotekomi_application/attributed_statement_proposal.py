"""Reviewed attributed-statement proposal submission use case.

The D4 ``wire_event_attribution`` composer produces an ``attributed_statement``
``ProposedAssertion`` but writes nothing. This module is the first canonical-write step on
that proposal: it validates every deterministic reference and submits the assertion as a
``ProposedChange`` accompanied by one ``ProvenanceActivity``.

The submitter is deterministic and idempotent. A repeated identical submission returns the
existing ``ProposedChange`` unchanged. A rejected submission is reported as a typed failure
instead of being silently resurrected.

The submitter never converts a proposal into accepted state: review and acceptance remain
separate ``proposed_change_review`` use cases.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    Document,
    EpistemicScope,
    EvidenceNecessity,
    EvidencePolarity,
    ProposedAssertion,
    ProposedChange,
    ProvenanceActivity,
    ReviewStatus,
    Source,
)

from kotekomi_application.evidence_targets import (
    EvidenceTargetReplayLedger,
    verify_evidence_target,
)

HASH_ID_LENGTH = 24
ATTRIBUTED_STATEMENT_ACTIVITY_TYPE = "attributed_statement_proposed"


class AttributedStatementProposalFailure(StrEnum):
    """Typed reason one attributed-statement proposal could not be submitted."""

    ALREADY_REJECTED = "attributed_statement_already_rejected"
    WRONG_EPISTEMIC_SCOPE = "attributed_statement_wrong_epistemic_scope"


class AttributedStatementProposalLedger(EvidenceTargetReplayLedger, Protocol):
    """The narrow Ledger surface the attributed-statement submitter needs."""

    def get_source(self, record_id: str) -> Source | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def save_proposed_change(self, record: ProposedChange) -> None: ...


@dataclass(frozen=True)
class SubmitAttributedStatementProposalInput:
    """One fully pinned attributed-statement proposal submission request.

    ``support_evidence_target_id`` and ``support_validation_attempt_id`` name the already
    accepted EvidenceTarget and its successful EvidenceValidationAttempt that back the
    attributed statement. Neither is created here.
    """

    proposed_assertion: ProposedAssertion
    support_evidence_target_id: str
    support_validation_attempt_id: str
    proposer: str
    document_id: str
    submitted_at: datetime
    model_name: str | None = None
    prompt_id: str | None = None


@dataclass(frozen=True)
class SubmitAttributedStatementProposalResult:
    status: str
    proposed_change_id: str | None
    assertion_id: str | None
    provenance_activity_id: str | None
    failure: AttributedStatementProposalFailure | None = None


def submit_attributed_statement_proposal(
    proposal: SubmitAttributedStatementProposalInput,
    ledger_repository: AttributedStatementProposalLedger,
) -> SubmitAttributedStatementProposalResult:
    """Submit one ``attributed_statement`` ProposedChange or return a typed non-record.

    Reference validation happens before any write. A missing Source, mismatched Document,
    unavailable EvidenceTarget, unavailable EvidenceValidationAttempt, or non-replayable
    evidence fails fast with ``ValueError``.
    """
    if not proposal.proposer.strip():
        raise ValueError("Attributed-statement proposal requires a proposer.")

    assertion = proposal.proposed_assertion
    if assertion.epistemic_scope is not EpistemicScope.ATTRIBUTED_STATEMENT:
        return _failed(
            assertion.id,
            None,
            AttributedStatementProposalFailure.WRONG_EPISTEMIC_SCOPE,
        )

    proposed_change_id = _deterministic_id("pcg", "attributed_statement", assertion.id)
    provenance_activity_id = _deterministic_id(
        "prv", "attributed_statement_proposed", proposed_change_id
    )

    existing = ledger_repository.get_proposed_change(proposed_change_id)
    if existing is not None:
        if existing.review_status is ReviewStatus.REJECTED:
            return _failed(
                assertion.id,
                proposed_change_id,
                AttributedStatementProposalFailure.ALREADY_REJECTED,
            )
        recorded = existing.review_status is ReviewStatus.APPROVED
        return SubmitAttributedStatementProposalResult(
            status=("recorded" if recorded else "pending"),
            proposed_change_id=existing.id,
            assertion_id=assertion.id,
            provenance_activity_id=existing.provenance_activity_id,
        )

    if not assertion.source_ids:
        raise ValueError("Attributed-statement proposal requires a Source.")
    if len(set(assertion.source_ids)) != len(assertion.source_ids):
        raise ValueError("Attributed-statement Sources must be unique.")
    if proposal.support_evidence_target_id not in assertion.evidence_target_ids:
        raise ValueError("Attributed-statement support EvidenceTarget is not on the assertion.")

    source = ledger_repository.get_source(assertion.source_ids[0])
    if source is None:
        raise ValueError(
            f"Attributed-statement proposal references missing Source: {assertion.source_ids[0]}"
        )
    document = ledger_repository.get_document(proposal.document_id)
    if document is None or document.source_id != source.id:
        raise ValueError("Attributed-statement proposal Document does not belong to its Source.")

    evidence = ledger_repository.get_evidence_target(proposal.support_evidence_target_id)
    if evidence is None:
        raise ValueError(
            "Attributed-statement proposal references missing EvidenceTarget: "
            f"{proposal.support_evidence_target_id}"
        )
    if evidence.id not in assertion.evidence_target_ids:
        raise ValueError("Attributed-statement support EvidenceTarget is not on the assertion.")
    if evidence.source_id not in assertion.source_ids:
        raise ValueError("Attributed-statement support EvidenceTarget belongs to another Source.")

    validation_attempt = ledger_repository.get_evidence_validation_attempt(
        proposal.support_validation_attempt_id
    )
    if validation_attempt is None:
        raise ValueError(
            "Attributed-statement proposal references missing EvidenceValidationAttempt: "
            f"{proposal.support_validation_attempt_id}"
        )
    if validation_attempt.evidence_target_id != evidence.id:
        raise ValueError(
            "Attributed-statement validation attempt belongs to another EvidenceTarget."
        )
    if not verify_evidence_target(evidence, validation_attempt, ledger_repository).valid:
        raise ValueError("Attributed-statement proposal requires replayable successful evidence.")

    activity = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=ATTRIBUTED_STATEMENT_ACTIVITY_TYPE,
        agent=proposal.proposer,
        input_ids=(source.id, document.id, evidence.id, validation_attempt.id),
        output_ids=(proposed_change_id,),
        occurred_at=proposal.submitted_at,
    )
    proposed_change = ProposedChange(
        id=proposed_change_id,
        review_status=ReviewStatus.PENDING,
        proposed_json={
            "record_type": "Assertion",
            "stable_label": assertion.id,
            "record": assertion.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
            "evidence_links": [
                {
                    "evidence_target_id": evidence.id,
                    "validation_attempt_id": validation_attempt.id,
                    "role": "direct_support",
                    "polarity": EvidencePolarity.SUPPORTS.value,
                    "necessity": EvidenceNecessity.REQUIRED.value,
                }
            ],
        },
        source_id=source.id,
        document_id=document.id,
        model_name=proposal.model_name,
        prompt_id=proposal.prompt_id,
        provenance_activity_id=activity.id,
        created_at=proposal.submitted_at,
        updated_at=proposal.submitted_at,
    )
    ledger_repository.save_provenance_activity(activity)
    ledger_repository.save_proposed_change(proposed_change)
    return SubmitAttributedStatementProposalResult(
        status="pending",
        proposed_change_id=proposed_change.id,
        assertion_id=assertion.id,
        provenance_activity_id=activity.id,
    )


def _failed(
    assertion_id: str,
    proposed_change_id: str | None,
    failure: AttributedStatementProposalFailure,
) -> SubmitAttributedStatementProposalResult:
    return SubmitAttributedStatementProposalResult(
        status="failed",
        proposed_change_id=proposed_change_id,
        assertion_id=assertion_id,
        provenance_activity_id=None,
        failure=failure,
    )


def _deterministic_id(prefix: str, *parts: str) -> str:
    value = "\x1f".join(parts)
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"