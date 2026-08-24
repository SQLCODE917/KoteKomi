from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_application import (
    CompleteIngestionRunCapturedInput,
    CompleteIngestionRunErrorInput,
    IngestionRunTransitionConflict,
    StartIngestionRunInput,
    complete_ingestion_run_as_captured,
    complete_ingestion_run_as_error,
    list_ingestion_runs,
    start_ingestion_run,
)
from kotekomi_domain import (
    IngestionFailureCode,
    IngestionFailureStage,
    IngestionRun,
    IngestionRunStatus,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class FakeIdFactory:
    def __init__(self) -> None:
        self.count = 0

    def new_ingestion_run_id(self) -> str:
        self.count += 1
        return f"igr_{self.count}"


class FakeRepository:
    def __init__(self) -> None:
        self.records: dict[str, IngestionRun] = {}

    def create_ingestion_run(self, record: IngestionRun) -> None:
        self.records[record.id] = record

    def get_ingestion_run(self, record_id: str) -> IngestionRun | None:
        return self.records.get(record_id)

    def complete_ingestion_run_if_running(self, record: IngestionRun) -> bool:
        current = self.records.get(record.id)
        if current is None or current.status is not IngestionRunStatus.RUNNING:
            return False
        self.records[record.id] = record
        return True

    def list_ingestion_runs(self) -> tuple[IngestionRun, ...]:
        return tuple(
            sorted(self.records.values(), key=lambda run: (run.started_at, run.id), reverse=True)
        )


def _start(repository: FakeRepository, ids: FakeIdFactory, clock: FakeClock) -> IngestionRun:
    return start_ingestion_run(
        StartIngestionRunInput(
            requested_path="raw/example.pdf",
            display_filename="example.pdf",
            requested_source_url="https://example.test/source",
        ),
        repository,
        ids,
        clock,
    )


def _captured_input(run: IngestionRun) -> CompleteIngestionRunCapturedInput:
    return CompleteIngestionRunCapturedInput(
        ingestion_run_id=run.id,
        normalized_source_url="https://example.test/source",
        source_id="src_fixture",
        document_id="doc_fixture",
        representation_id="rep_fixture",
        provenance_activity_id="prv_fixture",
    )


def test_start_and_capture_persist_one_complete_run() -> None:
    repository = FakeRepository()
    ids = FakeIdFactory()
    clock = FakeClock()

    started = _start(repository, ids, clock)
    completed = complete_ingestion_run_as_captured(_captured_input(started), repository, clock)

    assert started.status is IngestionRunStatus.RUNNING
    assert completed.status is IngestionRunStatus.CAPTURED
    assert completed.representation_id == "rep_fixture"


def test_error_completion_preserves_safe_typed_failure() -> None:
    repository = FakeRepository()
    ids = FakeIdFactory()
    clock = FakeClock()
    started = _start(repository, ids, clock)

    completed = complete_ingestion_run_as_error(
        CompleteIngestionRunErrorInput(
            ingestion_run_id=started.id,
            failure_stage=IngestionFailureStage.SOURCE_VALIDATION,
            failure_code=IngestionFailureCode.FILE_NOT_FOUND,
            safe_failure_message="The requested deposited file was not found.",
        ),
        repository,
        clock,
    )

    assert completed.status is IngestionRunStatus.ERROR
    assert completed.failure_code is IngestionFailureCode.FILE_NOT_FOUND


def test_conflicting_terminal_completion_fails_and_retries_have_new_ids() -> None:
    repository = FakeRepository()
    ids = FakeIdFactory()
    clock = FakeClock()
    first = _start(repository, ids, clock)
    second = _start(repository, ids, clock)
    complete_ingestion_run_as_captured(_captured_input(first), repository, clock)

    with pytest.raises(IngestionRunTransitionConflict, match="ingestion_run_transition_conflict"):
        complete_ingestion_run_as_error(
            CompleteIngestionRunErrorInput(
                ingestion_run_id=first.id,
                failure_stage=IngestionFailureStage.SOURCE_CAPTURE,
                failure_code=IngestionFailureCode.SOURCE_CAPTURE_FAILED,
                safe_failure_message="The deposited source could not be captured.",
            ),
            repository,
            clock,
        )

    assert first.id != second.id
    assert tuple(run.id for run in list_ingestion_runs(repository)) == (second.id, first.id)
