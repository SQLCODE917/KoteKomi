from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_domain import (
    IngestionFailureCode,
    IngestionFailureStage,
    IngestionRun,
    IngestionRunStatus,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _run(record_id: str, *, started_at: datetime = NOW) -> IngestionRun:
    return IngestionRun(
        id=record_id,
        requested_path="raw/example.pdf",
        display_filename="example.pdf",
        requested_source_url="https://example.test/source",
        status=IngestionRunStatus.RUNNING,
        started_at=started_at,
    )


def test_sqlite_ingestion_runs_round_trip_and_order(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    result = SQLiteLedgerInitializer(ledger_path).initialize()

    assert "010" in result.applied_migrations
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.create_ingestion_run(_run("igr_a"))
        repository.create_ingestion_run(_run("igr_b"))
        repository.create_ingestion_run(_run("igr_c", started_at=NOW + timedelta(seconds=1)))
        runs = repository.list_ingestion_runs()
        accepted_records = repository.list_accepted_canonical_records()

    assert tuple(run.id for run in runs) == ("igr_c", "igr_b", "igr_a")
    assert accepted_records == ()


def test_sqlite_ingestion_run_terminal_transition_is_guarded(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    running = _run("igr_fixture")
    errored = running.model_copy(
        update={
            "status": IngestionRunStatus.ERROR,
            "completed_at": NOW + timedelta(seconds=1),
            "failure_stage": IngestionFailureStage.SOURCE_VALIDATION,
            "failure_code": IngestionFailureCode.FILE_NOT_FOUND,
            "safe_failure_message": "The requested deposited file was not found.",
        }
    )

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.create_ingestion_run(running)
        assert repository.complete_ingestion_run_if_running(errored) is True
        assert repository.complete_ingestion_run_if_running(errored) is False
        assert repository.get_ingestion_run(running.id) == errored


def test_sqlite_ingestion_run_rejects_missing_canonical_links(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    captured = _run("igr_fixture").model_copy(
        update={
            "status": IngestionRunStatus.CAPTURED,
            "completed_at": NOW + timedelta(seconds=1),
            "normalized_source_url": "https://example.test/source",
            "source_id": "src_missing",
            "document_id": "doc_missing",
            "representation_id": "rep_missing",
            "provenance_activity_id": "prv_missing",
        }
    )

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.create_ingestion_run(_run("igr_fixture"))
        with pytest.raises(ValueError, match="missing Source"):
            repository.complete_ingestion_run_if_running(captured)
