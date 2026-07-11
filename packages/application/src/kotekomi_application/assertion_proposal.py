"""Assertion proposal use case."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from kotekomi_domain import Document, ProposedChange, ProvenanceActivity, ReviewStatus
from kotekomi_domain.models import JsonValue

from kotekomi_application.model_proposal_validation import validate_model_proposal
from kotekomi_application.model_runtime import ModelOutputValidationError
from kotekomi_application.ports import ArchiveStore, ModelProposal, ModelRuntime

HASH_ID_LENGTH = 24
MODEL_ASSERTION_PROPOSAL_ACTIVITY = "model_assertion_proposal"


class AssertionProposalLedger(Protocol):
    def get_document(self, record_id: str) -> Document | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def save_proposed_change(self, record: ProposedChange) -> None: ...


@dataclass(frozen=True)
class AssertionProposalInput:
    document_id: str
    proposed_at: datetime


@dataclass(frozen=True)
class AssertionProposalResult:
    document_id: str
    source_id: str
    provenance_activity_id: str
    proposed_change_ids: tuple[str, ...]


def propose_assertions_for_document(
    proposal_input: AssertionProposalInput,
    archive_store: ArchiveStore,
    ledger_repository: AssertionProposalLedger,
    model_runtime: ModelRuntime,
) -> AssertionProposalResult:
    document = ledger_repository.get_document(proposal_input.document_id)
    if document is None:
        raise ValueError(f"Document not found: {proposal_input.document_id}")

    document_text = archive_store.read_document_text(document.id)
    proposals = model_runtime.propose_assertions(
        document_id=document.id,
        source_id=document.source_id,
        document_text=document_text,
    )
    provenance_activity_id = deterministic_provenance_activity_id(
        document_id=document.id,
        model_name=model_runtime.model_name,
        prompt_id=model_runtime.prompt_id,
    )
    try:
        proposals = tuple(validate_model_proposal(proposal) for proposal in proposals)
    except ValueError as exc:
        raise ModelOutputValidationError(f"Invalid ModelRuntime proposal: {exc}") from exc
    for proposal in proposals:
        _validate_proposal_references(proposal, document, document_text)
    proposed_changes = tuple(
        _build_proposed_change(
            proposal=proposal,
            document=document,
            model_name=model_runtime.model_name,
            prompt_id=model_runtime.prompt_id,
            provenance_activity_id=provenance_activity_id,
            proposed_at=proposal_input.proposed_at,
        )
        for proposal in proposals
    )
    proposed_change_ids = tuple(record.id for record in proposed_changes)
    if len(set(proposed_change_ids)) != len(proposed_change_ids):
        raise ValueError("ModelRuntime returned duplicate ProposedChange identifiers.")

    provenance_activity = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=MODEL_ASSERTION_PROPOSAL_ACTIVITY,
        agent=model_runtime.model_name,
        input_ids=(document.id,),
        output_ids=proposed_change_ids,
        occurred_at=proposal_input.proposed_at,
    )

    ledger_repository.save_provenance_activity(provenance_activity)
    for proposed_change in proposed_changes:
        ledger_repository.save_proposed_change(proposed_change)

    return AssertionProposalResult(
        document_id=document.id,
        source_id=document.source_id,
        provenance_activity_id=provenance_activity_id,
        proposed_change_ids=proposed_change_ids,
    )


def deterministic_proposed_change_id(
    *,
    document_id: str,
    record_type: str,
    stable_label: str,
) -> str:
    digest = hashlib.sha256(f"{document_id}:{record_type}:{stable_label}".encode()).hexdigest()
    return f"pcg_{digest[:HASH_ID_LENGTH]}"


def deterministic_provenance_activity_id(
    *,
    document_id: str,
    model_name: str,
    prompt_id: str,
) -> str:
    digest = hashlib.sha256(
        (f"{document_id}:{MODEL_ASSERTION_PROPOSAL_ACTIVITY}:{model_name}:{prompt_id}").encode()
    ).hexdigest()
    return f"prv_{digest[:HASH_ID_LENGTH]}"


def _build_proposed_change(
    *,
    proposal: ModelProposal,
    document: Document,
    model_name: str,
    prompt_id: str,
    provenance_activity_id: str,
    proposed_at: datetime,
) -> ProposedChange:
    proposed_json: dict[str, JsonValue] = {
        "record_type": proposal.record_type,
        "stable_label": proposal.stable_label,
        "record": proposal.record,
        "evidence": proposal.evidence,
    }
    if proposal.record_type == "Assertion":
        proposed_json["evidence_links"] = cast(JsonValue, list(proposal.evidence_links))
    return ProposedChange(
        id=deterministic_proposed_change_id(
            document_id=document.id,
            record_type=proposal.record_type,
            stable_label=proposal.stable_label,
        ),
        review_status=ReviewStatus.PENDING,
        proposed_json=proposed_json,
        source_id=document.source_id,
        document_id=document.id,
        model_name=model_name,
        prompt_id=prompt_id,
        provenance_activity_id=provenance_activity_id,
        created_at=proposed_at,
        updated_at=proposed_at,
    )


def _validate_proposal_references(
    proposal: ModelProposal,
    document: Document,
    document_text: str,
) -> None:
    evidence_source_id = proposal.evidence.get("source_id")
    evidence_document_id = proposal.evidence.get("document_id")
    if evidence_source_id != document.source_id:
        raise ModelOutputValidationError(
            "ModelRuntime proposal evidence source_id does not match the Document source_id."
        )
    if evidence_document_id != document.id:
        raise ModelOutputValidationError(
            "ModelRuntime proposal evidence document_id does not match the Document id."
        )
    exact_text = proposal.evidence.get("exact_text")
    if not isinstance(exact_text, str) or exact_text not in document_text:
        raise ModelOutputValidationError(
            "ModelRuntime proposal evidence exact_text does not occur in the Document."
        )
