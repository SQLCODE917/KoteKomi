"""Reviewed cross-source lineage proposal use cases."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import Document, ProposedChange, ProvenanceActivity, ReviewStatus
from kotekomi_domain.models import JsonValue


class SourceLineageProposalFailure(StrEnum):
    DOCUMENT_MISSING = "document_missing"
    SAME_DOCUMENT = "same_document"
    SAME_SOURCE = "same_source"
    CONTENT_DIGEST_MISMATCH = "content_digest_mismatch"
    ALREADY_REJECTED = "relation_already_rejected"


@dataclass(frozen=True)
class ProposeVerbatimRepublicationInput:
    document_ids: tuple[str, str]
    proposer: str
    rationale: str
    proposed_at: datetime


@dataclass(frozen=True)
class ProposeVerbatimRepublicationResult:
    status: str
    proposed_change_id: str | None
    source_lineage_relation_id: str | None
    failure: SourceLineageProposalFailure | None = None


class SourceLineageProposalLedger(Protocol):
    def get_document(self, record_id: str) -> Document | None: ...
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def save_proposed_change(self, record: ProposedChange) -> None: ...


def propose_verbatim_republication(
    proposal: ProposeVerbatimRepublicationInput,
    ledger_repository: SourceLineageProposalLedger,
) -> ProposeVerbatimRepublicationResult:
    first_id, second_id = proposal.document_ids
    if first_id == second_id:
        return _failed(SourceLineageProposalFailure.SAME_DOCUMENT)
    if not proposal.proposer.strip() or not proposal.rationale.strip():
        raise ValueError("Source lineage proposal requires proposer and rationale.")
    document_ids = tuple(sorted((first_id, second_id)))
    first = ledger_repository.get_document(document_ids[0])
    second = ledger_repository.get_document(document_ids[1])
    if first is None or second is None:
        return _failed(SourceLineageProposalFailure.DOCUMENT_MISSING)
    if first.source_id == second.source_id:
        return _failed(SourceLineageProposalFailure.SAME_SOURCE)
    if first.content_sha256 != second.content_sha256:
        return _failed(SourceLineageProposalFailure.CONTENT_DIGEST_MISMATCH)

    relation_id = _deterministic_id(
        "slr", "verbatim_republication", document_ids, first.content_sha256
    )
    proposed_change_id = _deterministic_id("pcg", "source_lineage", relation_id)
    existing = ledger_repository.get_proposed_change(proposed_change_id)
    if existing is not None:
        if existing.review_status is ReviewStatus.REJECTED:
            return ProposeVerbatimRepublicationResult(
                status="failed",
                proposed_change_id=existing.id,
                source_lineage_relation_id=relation_id,
                failure=SourceLineageProposalFailure.ALREADY_REJECTED,
            )
        return ProposeVerbatimRepublicationResult(
            status=("recorded" if existing.review_status is ReviewStatus.APPROVED else "pending"),
            proposed_change_id=existing.id,
            source_lineage_relation_id=relation_id,
        )

    activity_id = _deterministic_id("prv", "source_lineage_proposed", proposed_change_id)
    activity = ProvenanceActivity(
        id=activity_id,
        activity_type="source_lineage_relation_proposed",
        agent=proposal.proposer,
        input_ids=document_ids,
        output_ids=(proposed_change_id,),
        occurred_at=proposal.proposed_at,
    )
    record: dict[str, JsonValue] = {
        "id": relation_id,
        "document_ids": list(document_ids),
        "relation_type": "verbatim_republication",
        "shared_content_sha256": first.content_sha256,
        "rationale": proposal.rationale,
    }
    proposed_change = ProposedChange(
        id=proposed_change_id,
        review_status=ReviewStatus.PENDING,
        proposed_json={
            "record_type": "SourceLineageRelation",
            "stable_label": relation_id,
            "record": record,
        },
        source_id=first.source_id,
        document_id=first.id,
        provenance_activity_id=activity.id,
        created_at=proposal.proposed_at,
        updated_at=proposal.proposed_at,
    )
    ledger_repository.save_provenance_activity(activity)
    ledger_repository.save_proposed_change(proposed_change)
    return ProposeVerbatimRepublicationResult(
        status="pending",
        proposed_change_id=proposed_change.id,
        source_lineage_relation_id=relation_id,
    )


def _failed(failure: SourceLineageProposalFailure) -> ProposeVerbatimRepublicationResult:
    return ProposeVerbatimRepublicationResult(
        status="failed", proposed_change_id=None, source_lineage_relation_id=None, failure=failure
    )


def _deterministic_id(prefix: str, *values: object) -> str:
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}_{hashlib.sha256(encoded.encode()).hexdigest()[:24]}"
