from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    ArchiveObject,
    AssertionProposalInput,
    ModelProposal,
    deterministic_proposed_change_id,
    propose_assertions_for_document,
)
from kotekomi_domain import Document, ProposedChange, ProvenanceActivity, ReviewStatus

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
HASH = "a" * 64


class FakeArchiveStore:
    def __init__(self, document_texts: dict[str, str]) -> None:
        self.document_texts = document_texts

    def initialize(self) -> None:
        return None

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        raise NotImplementedError

    def read_raw_source(self, source_id: str) -> bytes:
        raise NotImplementedError

    def write_document_text(self, document_id: str, text: str) -> ArchiveObject:
        raise NotImplementedError

    def read_document_text(self, document_id: str) -> str:
        return self.document_texts[document_id]


class FakeLedgerRepository:
    def __init__(self, documents: dict[str, Document] | None = None) -> None:
        self.documents = documents or {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}
        self.proposed_changes: dict[str, ProposedChange] = {}

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposed_changes[record.id] = record


class FakeModelRuntime:
    model_name = "fixture-extraction-runtime"
    prompt_id = "propose_assertions"

    def __init__(self, proposals: tuple[ModelProposal, ...]) -> None:
        self.proposals = proposals
        self.calls: list[tuple[str, str, str]] = []

    def propose_assertions(
        self,
        *,
        document_id: str,
        source_id: str,
        document_text: str,
    ) -> tuple[ModelProposal, ...]:
        self.calls.append((document_id, source_id, document_text))
        return self.proposals


def test_propose_assertions_for_document_creates_pending_proposed_changes() -> None:
    document = Document(
        id="doc_article_a",
        source_id="src_article_a",
        raw_path="sources/raw/src_article_a.bin",
        extracted_text_path="documents/extracted/doc_article_a.txt",
        content_sha256=HASH,
    )
    ledger = FakeLedgerRepository(documents={document.id: document})
    archive = FakeArchiveStore({document.id: "document text"})
    model_runtime = FakeModelRuntime(
        (
            ModelProposal(
                record_type="Assertion",
                stable_label="release_was_delayed",
                record={"id": "ast_release_was_delayed"},
                evidence={
                    "selector_type": "exact_text",
                    "exact_text": "document text",
                    "source_id": document.source_id,
                    "document_id": document.id,
                },
            ),
            ModelProposal(
                record_type="EvidenceSpan",
                stable_label="delay_evidence",
                record={"id": "evs_delay_evidence"},
                evidence={
                    "selector_type": "exact_text",
                    "exact_text": "document text",
                    "source_id": document.source_id,
                    "document_id": document.id,
                },
            ),
        )
    )

    result = propose_assertions_for_document(
        AssertionProposalInput(document_id=document.id, proposed_at=NOW),
        archive,
        ledger,
        model_runtime,
    )

    assert model_runtime.calls == [(document.id, document.source_id, "document text")]
    assert result.document_id == document.id
    assert result.source_id == document.source_id
    assert len(result.proposed_change_ids) == 2
    assert len(ledger.provenance_activities) == 1
    provenance_activity = ledger.provenance_activities[result.provenance_activity_id]
    assert provenance_activity.activity_type == "model_assertion_proposal"
    assert provenance_activity.agent == "fixture-extraction-runtime"
    assert provenance_activity.input_ids == (document.id,)
    assert provenance_activity.output_ids == result.proposed_change_ids

    expected_id = deterministic_proposed_change_id(
        document_id=document.id,
        record_type="Assertion",
        stable_label="release_was_delayed",
    )
    proposed_change = ledger.proposed_changes[expected_id]
    assert proposed_change.review_status is ReviewStatus.PENDING
    assert proposed_change.source_id == document.source_id
    assert proposed_change.document_id == document.id
    assert proposed_change.model_name == "fixture-extraction-runtime"
    assert proposed_change.prompt_id == "propose_assertions"
    assert proposed_change.provenance_activity_id == provenance_activity.id
    assert proposed_change.proposed_json["record_type"] == "Assertion"
    assert proposed_change.proposed_json["stable_label"] == "release_was_delayed"
    assert proposed_change.proposed_json["record"] == {"id": "ast_release_was_delayed"}


def test_propose_assertions_for_document_rejects_missing_document() -> None:
    ledger = FakeLedgerRepository()
    archive = FakeArchiveStore({})
    model_runtime = FakeModelRuntime(())

    with pytest.raises(ValueError, match="Document not found: doc_missing"):
        propose_assertions_for_document(
            AssertionProposalInput(document_id="doc_missing", proposed_at=NOW),
            archive,
            ledger,
            model_runtime,
        )

    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}
    assert model_runtime.calls == []


def test_propose_assertions_for_document_rejects_mismatched_evidence_reference() -> None:
    document = Document(
        id="doc_article_a",
        source_id="src_article_a",
        raw_path="sources/raw/src_article_a.bin",
        extracted_text_path="documents/extracted/doc_article_a.txt",
        content_sha256=HASH,
    )
    ledger = FakeLedgerRepository(documents={document.id: document})
    archive = FakeArchiveStore({document.id: "document text"})
    model_runtime = FakeModelRuntime(
        (
            ModelProposal(
                record_type="Assertion",
                stable_label="release_was_delayed",
                record={"id": "ast_release_was_delayed"},
                evidence={
                    "selector_type": "exact_text",
                    "exact_text": "document text",
                    "source_id": "src_other",
                    "document_id": document.id,
                },
            ),
        )
    )

    with pytest.raises(ValueError, match="evidence source_id does not match"):
        propose_assertions_for_document(
            AssertionProposalInput(document_id=document.id, proposed_at=NOW),
            archive,
            ledger,
            model_runtime,
        )

    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}
