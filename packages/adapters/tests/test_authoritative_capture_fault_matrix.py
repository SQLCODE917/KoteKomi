import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore, SQLiteLedgerInitializer, SQLiteLedgerRepository
from kotekomi_application import (
    ArchiveObject,
    AuthoritativeCaptureRequest,
    BuildIdentity,
    StagedArchiveObject,
    Uuid4ProcessingAttemptIdFactory,
    commit_authoritative_capture,
)
from kotekomi_domain import (
    CaptureDocumentResolution,
    Document,
    DocumentNode,
    DocumentRepresentation,
    ParseQualityReport,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    RawBlob,
    Source,
    SourceCapture,
    TextView,
)

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
BUILD_IDENTITY = BuildIdentity("fault-matrix", "fault-matrix", "a" * 64, "1")
RAW_BYTES = b"# Fault matrix fixture\n\nAuthoritative capture bytes.\n"


class InjectedCrash(RuntimeError):
    pass


class FaultingArchiveStore(LocalArchiveStore):
    def __init__(self, archive_root: Path, checkpoint: str) -> None:
        super().__init__(archive_root)
        self._checkpoint = checkpoint
        self.deleted_paths: list[str] = []

    def put_if_absent_or_identical(self, object_id: str, payload: bytes, expected_digest: str):
        outcome = super().put_if_absent_or_identical(object_id, payload, expected_digest)
        self._crash("archive_raw")
        return outcome

    def stage_document_text(self, document_id: str, text: str):
        staged = super().stage_document_text(document_id, text)
        self._crash("archive_text_staged")
        return staged

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        promoted = super().promote_staged_object(staged_object)
        self._crash("archive_text_promoted")
        return promoted

    def delete_object(self, relative_path: str) -> None:
        self.deleted_paths.append(relative_path)
        super().delete_object(relative_path)

    def _crash(self, checkpoint: str) -> None:
        if self._checkpoint == checkpoint:
            self._checkpoint = ""
            raise InjectedCrash(checkpoint)


class FaultingLedgerRepository(SQLiteLedgerRepository):
    def __init__(self, connection: sqlite3.Connection, checkpoint: str) -> None:
        super().__init__(connection)
        self._checkpoint = checkpoint

    def save_source(self, record: Source) -> None:
        super().save_source(record)
        self._crash("source")

    def save_raw_blob(self, record: RawBlob) -> None:
        super().save_raw_blob(record)
        self._crash("raw_blob")

    def save_source_capture(self, record: SourceCapture) -> None:
        super().save_source_capture(record)
        self._crash("source_capture")

    def save_document(self, record: Document) -> None:
        super().save_document(record)
        self._crash("document")

    def save_capture_document_resolution(self, record: CaptureDocumentResolution) -> None:
        super().save_capture_document_resolution(record)
        self._crash("document_resolution")

    def save_document_representation(self, record: DocumentRepresentation) -> None:
        super().save_document_representation(record)
        self._crash("representation")

    def save_text_view(self, record: TextView) -> None:
        super().save_text_view(record)
        self._crash("text_view")

    def save_document_node(self, record: DocumentNode) -> None:
        super().save_document_node(record)
        self._crash("document_node")

    def save_parse_quality_report(self, record: ParseQualityReport) -> None:
        super().save_parse_quality_report(record)
        self._crash("quality_report")

    def commit_processing_attempt_start(self) -> None:
        super().commit_processing_attempt_start()
        self._crash("attempt_start")

    def append_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        super().append_processing_attempt_outcome(record)
        self._crash("attempt_outcome")

    def _crash(self, checkpoint: str) -> None:
        if self._checkpoint == checkpoint:
            self._checkpoint = ""
            raise InjectedCrash(checkpoint)


@contextmanager
def faulting_transaction(ledger_path: Path, checkpoint: str) -> Generator[FaultingLedgerRepository]:
    connection = sqlite3.connect(ledger_path)
    connection.execute("PRAGMA foreign_keys = ON")
    committed = False
    try:
        connection.execute("BEGIN")
        yield FaultingLedgerRepository(connection, checkpoint)
        if checkpoint == "before_transaction_commit":
            raise InjectedCrash(checkpoint)
        connection.commit()
        committed = True
        if checkpoint == "after_transaction_commit":
            raise InjectedCrash(checkpoint)
    except Exception:
        if not committed:
            connection.rollback()
        raise
    finally:
        connection.close()


def _request(
    build_identity: BuildIdentity = BUILD_IDENTITY,
) -> AuthoritativeCaptureRequest:
    return AuthoritativeCaptureRequest(
        local_file_path="fault-matrix.md",
        filename="fault-matrix.md",
        raw_bytes=RAW_BYTES,
        ingested_at=NOW,
        build_identity=build_identity,
    )


@pytest.mark.parametrize(
    "checkpoint",
    (
        "archive_raw",
        "archive_text_staged",
        "archive_text_promoted",
        "source",
        "raw_blob",
        "source_capture",
        "document",
        "document_resolution",
        "representation",
        "text_view",
        "document_node",
        "quality_report",
        "attempt_start",
        "attempt_outcome",
        "before_transaction_commit",
        "after_transaction_commit",
    ),
)
def test_authoritative_capture_fault_matrix_converges_after_restart(
    tmp_path: Path, checkpoint: str
) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive_path = tmp_path / "archive"
    SQLiteLedgerInitializer(ledger_path).initialize()
    archive = FaultingArchiveStore(archive_path, checkpoint)
    archive.initialize()

    with pytest.raises(InjectedCrash, match=checkpoint):
        with faulting_transaction(ledger_path, checkpoint) as repository:
            commit_authoritative_capture(
                _request(), archive, repository, Uuid4ProcessingAttemptIdFactory()
            )
    assert all(path.startswith(".staging/") for path in archive.deleted_paths)

    stable_archive = LocalArchiveStore(archive_path)
    with sqlite3.connect(ledger_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        repository = SQLiteLedgerRepository(connection)
        result = commit_authoritative_capture(
            _request(), stable_archive, repository, Uuid4ProcessingAttemptIdFactory()
        )
        connection.commit()

    assert (
        stable_archive.read_raw_source(
            result.raw_path.removeprefix("sources/raw/").removesuffix(".bin")
        )
        == RAW_BYTES
    )
    assert stable_archive.read_document_text(result.document_id) == RAW_BYTES.decode()
    with sqlite3.connect(ledger_path) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "sources",
                "raw_blobs",
                "source_captures",
                "capture_document_resolutions",
                "documents",
                "document_representations",
                "text_views",
                "document_nodes",
                "parse_quality_reports",
                "provenance_activities",
                "processing_task_fingerprints",
            )
        }
        attempt_ids = {
            attempt_id for (attempt_id,) in connection.execute("SELECT id FROM processing_attempts")
        }
        outcomes = connection.execute(
            "SELECT attempt_id, status FROM processing_attempt_outcomes"
        ).fetchall()
    assert counts == {
        "sources": 1,
        "raw_blobs": 1,
        "source_captures": 1,
        "capture_document_resolutions": 1,
        "documents": 1,
        "document_representations": 1,
        "text_views": 1,
        "document_nodes": 1,
        "parse_quality_reports": 1,
        "provenance_activities": 2,
        "processing_task_fingerprints": 1,
    }
    assert {attempt_id for attempt_id, _status in outcomes} == attempt_ids
    assert {status for _attempt_id, status in outcomes} <= {
        ProcessingAttemptStatus.SUCCEEDED.value,
        ProcessingAttemptStatus.FAILED.value,
        ProcessingAttemptStatus.INTERRUPTED.value,
    }


def test_authoritative_capture_creates_new_representation_for_changed_build_identity(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive_path = tmp_path / "archive"
    SQLiteLedgerInitializer(ledger_path).initialize()
    archive = LocalArchiveStore(archive_path)
    archive.initialize()

    with sqlite3.connect(ledger_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        repository = SQLiteLedgerRepository(connection)
        first = commit_authoritative_capture(
            _request(), archive, repository, Uuid4ProcessingAttemptIdFactory()
        )
        first_bundle = repository.get_document_representation_bundle(first.representation_id)
        first_provenance = repository.get_provenance_activity(first.provenance_activity_id)
        connection.commit()

    changed_build_identity = BuildIdentity(
        "fault-matrix",
        "changed-revision",
        "a" * 64,
        "1",
    )
    with sqlite3.connect(ledger_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        repository = SQLiteLedgerRepository(connection)
        second = commit_authoritative_capture(
            _request(changed_build_identity),
            archive,
            repository,
            Uuid4ProcessingAttemptIdFactory(),
        )
        connection.commit()

    with sqlite3.connect(ledger_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        repository = SQLiteLedgerRepository(connection)
        preserved_first_bundle = repository.get_document_representation_bundle(
            first.representation_id
        )
        preserved_first_provenance = repository.get_provenance_activity(
            first.provenance_activity_id
        )
        provenance_activity_types = tuple(
            activity.activity_type for activity in repository.list_provenance_activities()
        )
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "sources",
                "raw_blobs",
                "source_captures",
                "capture_document_resolutions",
                "documents",
                "document_representations",
                "processing_task_fingerprints",
                "processing_attempts",
                "processing_attempt_outcomes",
                "provenance_activities",
            )
        }
        outcome_statuses = connection.execute(
            "SELECT status FROM processing_attempt_outcomes ORDER BY id"
        ).fetchall()

    assert first.source_id == second.source_id
    assert first.document_id == second.document_id
    assert first.representation_id != second.representation_id
    assert first_bundle == preserved_first_bundle
    assert first_provenance == preserved_first_provenance
    assert counts == {
        "sources": 1,
        "raw_blobs": 1,
        "source_captures": 1,
        "capture_document_resolutions": 1,
        "documents": 1,
        "document_representations": 2,
        "processing_task_fingerprints": 2,
        "processing_attempts": 2,
        "processing_attempt_outcomes": 2,
        "provenance_activities": 3,
    }
    assert provenance_activity_types.count("source_file_capture") == 1
    assert provenance_activity_types.count("source_file_representation") == 2
    assert outcome_statuses == [
        (ProcessingAttemptStatus.SUCCEEDED.value,),
        (ProcessingAttemptStatus.SUCCEEDED.value,),
    ]
