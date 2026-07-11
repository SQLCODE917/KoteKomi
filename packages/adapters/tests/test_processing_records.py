import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import (
    BuildIdentity,
    processing_attempt_outcome,
    processing_task_fingerprint,
    reconcile_interrupted_processing_attempts,
    start_processing_attempt,
)
from kotekomi_domain import (
    ProcessingAttempt,
    ProcessingAttemptStatus,
    ProcessingFailure,
    ProcessingStage,
    RawBlob,
)

from .domain_fixtures import sample_domain_records

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


class SequenceAttemptIdFactory:
    def __init__(self) -> None:
        self._next = 1

    def new_attempt_id(self) -> str:
        value = f"pat_{self._next:024d}"
        self._next += 1
        return value


def _task():
    return processing_task_fingerprint(
        task_kind="test_processing",
        document_id="doc_article_a",
        blob_id="blb_processing_fixture",
        input_digest="a" * 64,
        processor_name="fixture",
        processor_version="1",
        processor_config_digest="b" * 64,
        build_identity=BuildIdentity("fixture", "fixture", "c" * 64, "1"),
        policy_id="fixture_policy",
        output_contract_version="1",
    )


def _initialize_task_inputs(ledger_path: Path) -> None:
    source, document = sample_domain_records()[5:7]
    raw_blob = RawBlob(
        id="blb_processing_fixture",
        hash_algorithm="sha256",
        digest="a" * 64,
        byte_length=1,
        media_type="application/octet-stream",
        storage_locator="sources/raw/blb_processing_fixture.bin",
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_source(source)
        repository.save_document(document)
        repository.save_raw_blob(raw_blob)


def test_attempt_start_survives_an_interrupted_output_transaction(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    _initialize_task_inputs(ledger_path)
    task = _task()
    attempt: ProcessingAttempt | None = None

    with pytest.raises(RuntimeError, match="simulated processor death"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            attempt = start_processing_attempt(
                task=task,
                ledger=repository,
                attempt_id_factory=SequenceAttemptIdFactory(),
                started_at=NOW,
                invocation_id="test:interrupted",
            )
            raise RuntimeError("simulated processor death")

    assert attempt is not None

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.get_processing_task_fingerprint(task.id) == task
        assert repository.get_processing_attempt(attempt.id) == attempt
        assert repository.get_processing_attempt_outcome(attempt.id) is None

    with sqlite_ledger_transaction(ledger_path) as repository:
        reconciled = reconcile_interrupted_processing_attempts(
            task_fingerprint_id=task.id,
            ledger=repository,
            reconciled_at=NOW,
            interruption_basis="process restart observed an unclosed attempt",
        )
        assert (
            reconcile_interrupted_processing_attempts(
                task_fingerprint_id=task.id,
                ledger=repository,
                reconciled_at=NOW,
                interruption_basis="process restart observed an unclosed attempt",
            )
            == ()
        )

    assert len(reconciled) == 1
    assert reconciled[0].status is ProcessingAttemptStatus.INTERRUPTED


def test_failed_outcome_is_durable_after_output_rollback(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    _initialize_task_inputs(ledger_path)
    task = _task()
    attempt: ProcessingAttempt | None = None

    with pytest.raises(RuntimeError, match="processor failed"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            attempt = start_processing_attempt(
                task=task,
                ledger=repository,
                attempt_id_factory=SequenceAttemptIdFactory(),
                started_at=NOW,
                invocation_id="test:failure",
            )
            repository.record_failed_processing_attempt_outcome(
                processing_attempt_outcome(
                    attempt=attempt,
                    status=ProcessingAttemptStatus.FAILED,
                    finished_at=NOW,
                    failure=ProcessingFailure(
                        code="fixture_failure",
                        failure_type="RuntimeError",
                        stage=ProcessingStage.PARSER,
                        safe_message="Fixture processor failed.",
                        retryable=False,
                    ),
                )
            )
            raise RuntimeError("processor failed")

    assert attempt is not None

    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = repository.get_processing_attempt_outcome(attempt.id)
    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.FAILED


def test_attempt_lookup_uses_indexed_keyset_pagination(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    _initialize_task_inputs(ledger_path)
    task = _task()
    attempts = tuple(
        ProcessingAttempt(
            id=f"pat_{index:024d}",
            task_fingerprint_id=task.id,
            started_at=NOW,
            invocation_id=f"test:{index}",
        )
        for index in range(1, 4)
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.ensure_processing_task_fingerprint(task)
        for attempt in attempts:
            repository.append_processing_attempt(attempt)
        repository.append_processing_attempt_outcome(
            processing_attempt_outcome(
                attempt=attempts[0],
                status=ProcessingAttemptStatus.INTERRUPTED,
                finished_at=NOW,
                interruption_basis="fixture reconciliation",
            )
        )
        assert repository.list_processing_attempts(task.id, limit=2) == attempts[:2]
        assert (
            repository.list_processing_attempts(task.id, after=attempts[1].id, limit=2)
            == attempts[2:]
        )

    with sqlite3.connect(ledger_path) as connection:
        query_plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT payload_json FROM processing_attempts
            WHERE task_fingerprint_id = ?
            ORDER BY started_at, id LIMIT ?
            """,
            (task.id, 2),
        ).fetchall()
    assert any("processing_attempts_by_fingerprint" in row[-1] for row in query_plan)

    with sqlite3.connect(ledger_path) as connection:
        with pytest.raises(
            sqlite3.DatabaseError, match="processing_task_fingerprints are immutable"
        ):
            connection.execute(
                "UPDATE processing_task_fingerprints SET payload_json = '{}' WHERE id = ?",
                (task.id,),
            )
        with pytest.raises(sqlite3.DatabaseError, match="processing_attempts are immutable"):
            connection.execute("DELETE FROM processing_attempts WHERE id = ?", (attempts[0].id,))
        with pytest.raises(
            sqlite3.DatabaseError, match="processing_attempt_outcomes are immutable"
        ):
            connection.execute(
                "DELETE FROM processing_attempt_outcomes WHERE attempt_id = ?", (attempts[0].id,)
            )
