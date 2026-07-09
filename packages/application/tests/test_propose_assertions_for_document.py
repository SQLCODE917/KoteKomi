from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    ArchiveObject,
    AssertionProposalInput,
    ModelProposal,
    StagedArchiveObject,
    deterministic_proposed_change_id,
    propose_assertions_for_document,
)
from kotekomi_domain import Document, ProposedChange, ProvenanceActivity, ReviewStatus
from kotekomi_domain.models import JsonValue

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

    def read_briefing_markdown(self, briefing_id: str) -> str:
        raise NotImplementedError

    def read_briefing_citations_json(self, briefing_id: str) -> str:
        raise NotImplementedError

    def stage_raw_source(self, source_id: str, content: bytes) -> StagedArchiveObject:
        raise NotImplementedError

    def stage_document_text(self, document_id: str, text: str) -> StagedArchiveObject:
        raise NotImplementedError

    def stage_briefing_markdown(
        self,
        briefing_id: str,
        markdown: str,
    ) -> StagedArchiveObject:
        raise NotImplementedError

    def stage_briefing_citations_json(
        self,
        briefing_id: str,
        citations_json: str,
    ) -> StagedArchiveObject:
        raise NotImplementedError

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        raise NotImplementedError

    def delete_object(self, relative_path: str) -> None:
        raise NotImplementedError


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
    document = document_fixture()
    ledger = FakeLedgerRepository(documents={document.id: document})
    archive = FakeArchiveStore({document.id: "document text"})
    model_runtime = FakeModelRuntime(
        (
            ModelProposal(
                record_type="Assertion",
                stable_label="release_was_delayed",
                record=assertion_record(document),
                evidence=evidence_record(document),
            ),
            ModelProposal(
                record_type="EvidenceSpan",
                stable_label="delay_evidence",
                record=evidence_span_record(document),
                evidence=evidence_record(document),
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
    proposed_record = proposed_change.proposed_json["record"]
    assert isinstance(proposed_record, dict)
    assert proposed_record["id"] == "ast_release_was_delayed"
    assert proposed_record["assertion_type"] == "source_claim"
    assert proposed_record["epistemic_scope"] == "source_report"
    assert proposed_record["source_authority"] == "secondary"
    assert proposed_record["attribution_basis"] == "reported_by_source"
    assert proposed_record["status"] == "proposed"


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
    document = document_fixture()
    ledger = FakeLedgerRepository(documents={document.id: document})
    archive = FakeArchiveStore({document.id: "document text"})
    model_runtime = FakeModelRuntime(
        (
            ModelProposal(
                record_type="Assertion",
                stable_label="release_was_delayed",
                record=assertion_record(document),
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


def test_propose_assertions_for_document_rejects_invalid_model_record() -> None:
    document = document_fixture()
    ledger = FakeLedgerRepository(documents={document.id: document})
    archive = FakeArchiveStore({document.id: "document text"})
    model_runtime = FakeModelRuntime(
        (
            ModelProposal(
                record_type="Assertion",
                stable_label="release_was_delayed",
                record={"id": "ast_release_was_delayed"},
                evidence=evidence_record(document),
            ),
        )
    )

    with pytest.raises(ValueError):
        propose_assertions_for_document(
            AssertionProposalInput(document_id=document.id, proposed_at=NOW),
            archive,
            ledger,
            model_runtime,
        )

    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}


def test_propose_assertions_for_document_rejects_assertion_missing_epistemic_scope() -> None:
    document = document_fixture()
    invalid_record = assertion_record(document)
    invalid_record.pop("epistemic_scope")
    ledger = FakeLedgerRepository(documents={document.id: document})
    archive = FakeArchiveStore({document.id: "document text"})
    model_runtime = FakeModelRuntime(
        (
            ModelProposal(
                record_type="Assertion",
                stable_label="release_was_delayed",
                record=invalid_record,
                evidence=evidence_record(document),
            ),
        )
    )

    with pytest.raises(ValueError, match="epistemic_scope"):
        propose_assertions_for_document(
            AssertionProposalInput(document_id=document.id, proposed_at=NOW),
            archive,
            ledger,
            model_runtime,
        )

    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}


def document_fixture() -> Document:
    return Document(
        id="doc_article_a",
        source_id="src_article_a",
        raw_path="sources/raw/src_article_a.bin",
        extracted_text_path="documents/extracted/doc_article_a.txt",
        content_sha256=HASH,
    )


def assertion_record(document: Document) -> dict[str, JsonValue]:
    return {
        "id": "ast_release_was_delayed",
        "assertion_type": "source_claim",
        "epistemic_scope": "source_report",
        "subject_entity_id": "org_anthropic",
        "predicate": "postponed_rollout",
        "object_value": {"model": "Claude Fable 5"},
        "status": "proposed",
        "source_authority": "secondary",
        "attribution_basis": "reported_by_source",
        "source_ids": [document.source_id],
        "evidence_span_ids": ["evs_delay_evidence"],
        "provenance_activity_ids": [],
    }


def evidence_span_record(document: Document) -> dict[str, JsonValue]:
    return {
        "id": "evs_delay_evidence",
        "source_id": document.source_id,
        "document_id": document.id,
        "selector_type": "exact_text",
        "exact_text": "document text",
    }


def evidence_record(document: Document) -> dict[str, JsonValue]:
    return {
        "selector_type": "exact_text",
        "exact_text": "document text",
        "source_id": document.source_id,
        "document_id": document.id,
    }
