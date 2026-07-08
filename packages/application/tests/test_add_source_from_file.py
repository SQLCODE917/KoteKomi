import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_application import (
    ArchiveObject,
    SourceFileIngestInput,
    add_source_from_file,
)
from kotekomi_domain import Document, ProvenanceActivity, Source, SourceType

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "tests"
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
FIXTURE_TITLE = "Anthropic delayed model rollout after U.S. review raised cyber-safety concerns"


class FakeArchiveStore:
    def __init__(self) -> None:
        self.raw_writes: dict[str, bytes] = {}
        self.text_writes: dict[str, str] = {}

    def initialize(self) -> None:
        return None

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        if source_id in self.raw_writes:
            raise FileExistsError(source_id)
        self.raw_writes[source_id] = content
        return ArchiveObject(
            relative_path=f"sources/raw/{source_id}.bin",
            size_bytes=len(content),
        )

    def read_raw_source(self, source_id: str) -> bytes:
        return self.raw_writes[source_id]

    def write_document_text(self, document_id: str, text: str) -> ArchiveObject:
        if document_id in self.text_writes:
            raise FileExistsError(document_id)
        self.text_writes[document_id] = text
        return ArchiveObject(
            relative_path=f"documents/extracted/{document_id}.txt",
            size_bytes=len(text.encode("utf-8")),
        )

    def read_document_text(self, document_id: str) -> str:
        return self.text_writes[document_id]


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.documents: dict[str, Document] = {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}

    def get_source(self, record_id: str) -> Source | None:
        return self.sources.get(record_id)

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self.provenance_activities.get(record_id)

    def save_source(self, record: Source) -> None:
        self.sources[record.id] = record

    def save_document(self, record: Document) -> None:
        self.documents[record.id] = record

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record


def test_add_source_from_file_creates_source_document_and_provenance() -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()

    result = add_source_from_file(
        SourceFileIngestInput(
            local_file_path=str(FIXTURE_PATH),
            filename=FIXTURE_PATH.name,
            raw_bytes=raw_bytes,
            ingested_at=NOW,
        ),
        archive,
        ledger,
    )

    source = ledger.sources[result.source_id]
    document = ledger.documents[result.document_id]
    provenance = ledger.provenance_activities[result.provenance_activity_id]
    assert result.created is True
    assert source.title == FIXTURE_TITLE
    assert source.source_type is SourceType.ARTICLE
    assert source.published_at == datetime(2026, 7, 2, tzinfo=UTC)
    assert document.raw_path == f"sources/raw/{result.source_id}.bin"
    assert document.extracted_text_path == f"documents/extracted/{result.document_id}.txt"
    assert document.content_sha256 == hashlib.sha256(raw_bytes).hexdigest()
    assert provenance.activity_type == "source_file_ingest"
    assert provenance.agent == "kotekomi"
    assert provenance.input_ids == (str(FIXTURE_PATH),)
    assert provenance.output_ids == (result.source_id, result.document_id)


def test_add_source_from_file_is_idempotent_after_records_exist() -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()
    ingest_input = SourceFileIngestInput(
        local_file_path=str(FIXTURE_PATH),
        filename=FIXTURE_PATH.name,
        raw_bytes=raw_bytes,
        ingested_at=NOW,
    )

    first = add_source_from_file(ingest_input, archive, ledger)
    second = add_source_from_file(ingest_input, archive, ledger)

    assert first.created is True
    assert second.created is False
    assert first.source_id == second.source_id
    assert first.document_id == second.document_id
    assert len(archive.raw_writes) == 1
    assert len(archive.text_writes) == 1
    assert len(ledger.sources) == 1
    assert len(ledger.documents) == 1
    assert len(ledger.provenance_activities) == 1


def test_add_source_from_file_rejects_unsupported_suffix() -> None:
    with pytest.raises(ValueError, match="Unsupported Source file suffix"):
        add_source_from_file(
            SourceFileIngestInput(
                local_file_path="fixture.pdf",
                filename="fixture.pdf",
                raw_bytes=b"%PDF",
                ingested_at=NOW,
            ),
            FakeArchiveStore(),
            FakeLedgerRepository(),
        )


def test_add_source_from_file_defaults_text_file_metadata() -> None:
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()

    result = add_source_from_file(
        SourceFileIngestInput(
            local_file_path="notes.txt",
            filename="notes.txt",
            raw_bytes=b"plain text note",
            ingested_at=NOW,
        ),
        archive,
        ledger,
    )

    source = ledger.sources[result.source_id]
    assert source.title == "notes"
    assert source.source_type is SourceType.MANUAL_FILE
    assert source.published_at is None
