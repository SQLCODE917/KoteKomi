from datetime import UTC, datetime
from typing import cast

from kotekomi_application.proposed_change_review import (
    ProposedChangeReviewLedger,
    ReviewProposedChangeInput,
    approve_proposed_change,
)
from kotekomi_application.source_lineage import (
    ProposeVerbatimRepublicationInput,
    SourceLineageProposalFailure,
    propose_verbatim_republication,
)
from kotekomi_domain import Document, ProposedChange, ProvenanceActivity, SourceLineageRelation

NOW = datetime(2026, 8, 23, tzinfo=UTC)


class FakeLedger:
    def __init__(self, first: Document, second: Document) -> None:
        self.documents = {first.id: first, second.id: second}
        self.proposed_changes: dict[str, ProposedChange] = {}
        self.activities: dict[str, ProvenanceActivity] = {}
        self.relations: dict[str, SourceLineageRelation] = {}

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposed_changes[record.id] = record

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self.activities.get(record_id)

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.activities[record.id] = record

    def get_source_lineage_relation(self, record_id: str) -> SourceLineageRelation | None:
        return self.relations.get(record_id)

    def save_source_lineage_relation(self, record: SourceLineageRelation) -> None:
        self.relations[record.id] = record


def _document(document_id: str, source_id: str, digest: str = "a" * 64) -> Document:
    return Document(
        id=document_id,
        source_id=source_id,
        content_sha256=digest,
        created_at=NOW,
        updated_at=NOW,
    )


def test_verbatim_republication_is_proposed_then_reviewed() -> None:
    first = _document("doc_first", "src_first")
    second = _document("doc_second", "src_second")
    ledger = FakeLedger(first, second)

    proposed = propose_verbatim_republication(
        ProposeVerbatimRepublicationInput(
            document_ids=(second.id, first.id),
            proposer="analyst",
            rationale="Both deposited sources contain the same archived PDF bytes.",
            proposed_at=NOW,
        ),
        ledger,
    )

    assert proposed.status == "pending"
    assert proposed.proposed_change_id is not None
    review = approve_proposed_change(
        ReviewProposedChangeInput(
            proposed_change_id=proposed.proposed_change_id,
            reviewer="reviewer",
            reviewed_at=NOW,
        ),
        cast(ProposedChangeReviewLedger, ledger),
    )

    relation = ledger.relations[review.accepted_record_id or ""]
    assert relation.document_ids == (first.id, second.id)
    assert relation.shared_content_sha256 == first.content_sha256
    assert relation.review_provenance_activity_id == review.provenance_activity_id


def test_verbatim_republication_rejects_mismatched_bytes_without_a_proposal() -> None:
    ledger = FakeLedger(
        _document("doc_first", "src_first"), _document("doc_second", "src_second", "b" * 64)
    )

    result = propose_verbatim_republication(
        ProposeVerbatimRepublicationInput(
            document_ids=("doc_first", "doc_second"),
            proposer="analyst",
            rationale="Compare deposited bytes.",
            proposed_at=NOW,
        ),
        ledger,
    )

    assert result.status == "failed"
    assert result.failure is SourceLineageProposalFailure.CONTENT_DIGEST_MISMATCH
    assert ledger.proposed_changes == {}


def test_verbatim_republication_rejects_two_documents_from_one_source() -> None:
    ledger = FakeLedger(_document("doc_first", "src_one"), _document("doc_second", "src_one"))

    result = propose_verbatim_republication(
        ProposeVerbatimRepublicationInput(
            document_ids=("doc_first", "doc_second"),
            proposer="analyst",
            rationale="Compare deposited bytes.",
            proposed_at=NOW,
        ),
        ledger,
    )

    assert result.status == "failed"
    assert result.failure is SourceLineageProposalFailure.SAME_SOURCE
