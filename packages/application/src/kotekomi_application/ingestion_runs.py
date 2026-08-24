"""Durable user-ingestion history use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from kotekomi_domain import (
    IngestionFailureCode,
    IngestionFailureStage,
    IngestionRun,
    IngestionRunStatus,
)


class IngestionRunClock(Protocol):
    def now(self) -> datetime: ...


class IngestionRunIdFactory(Protocol):
    def new_ingestion_run_id(self) -> str: ...


class IngestionRunRepository(Protocol):
    def create_ingestion_run(self, record: IngestionRun) -> None: ...
    def get_ingestion_run(self, record_id: str) -> IngestionRun | None: ...
    def complete_ingestion_run_if_running(self, record: IngestionRun) -> bool: ...
    def list_ingestion_runs(self) -> tuple[IngestionRun, ...]: ...


class IngestionRunTransitionConflict(ValueError):
    """A durable run has a terminal result incompatible with the requested one."""


class UtcIngestionRunClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class Uuid4IngestionRunIdFactory:
    def new_ingestion_run_id(self) -> str:
        return f"igr_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class StartIngestionRunInput:
    requested_path: str
    display_filename: str
    requested_source_url: str


@dataclass(frozen=True)
class CompleteIngestionRunCapturedInput:
    ingestion_run_id: str
    normalized_source_url: str
    source_id: str
    document_id: str
    representation_id: str
    provenance_activity_id: str
    analysis_run_id: str | None = None
    ingestion_change_set_id: str | None = None


@dataclass(frozen=True)
class CompleteIngestionRunErrorInput:
    ingestion_run_id: str
    failure_stage: IngestionFailureStage
    failure_code: IngestionFailureCode
    safe_failure_message: str
    normalized_source_url: str | None = None
    source_id: str | None = None
    document_id: str | None = None
    representation_id: str | None = None
    provenance_activity_id: str | None = None


def start_ingestion_run(
    input: StartIngestionRunInput,
    repository: IngestionRunRepository,
    id_factory: IngestionRunIdFactory,
    clock: IngestionRunClock,
) -> IngestionRun:
    record = IngestionRun(
        id=id_factory.new_ingestion_run_id(),
        requested_path=input.requested_path,
        display_filename=input.display_filename,
        requested_source_url=input.requested_source_url,
        status=IngestionRunStatus.RUNNING,
        started_at=clock.now(),
    )
    repository.create_ingestion_run(record)
    return record


def complete_ingestion_run_as_captured(
    input: CompleteIngestionRunCapturedInput,
    repository: IngestionRunRepository,
    clock: IngestionRunClock,
) -> IngestionRun:
    current = _require_ingestion_run(input.ingestion_run_id, repository)
    desired = IngestionRun.model_validate(
        current.model_dump()
        | {
            "normalized_source_url": input.normalized_source_url,
            "status": IngestionRunStatus.CAPTURED,
            "completed_at": clock.now(),
            "source_id": input.source_id,
            "document_id": input.document_id,
            "representation_id": input.representation_id,
            "provenance_activity_id": input.provenance_activity_id,
            "analysis_run_id": input.analysis_run_id,
            "ingestion_change_set_id": input.ingestion_change_set_id,
            "failure_stage": None,
            "failure_code": None,
            "safe_failure_message": None,
        }
    )
    return _complete_terminal_run(current, desired, repository)


def complete_ingestion_run_as_error(
    input: CompleteIngestionRunErrorInput,
    repository: IngestionRunRepository,
    clock: IngestionRunClock,
) -> IngestionRun:
    current = _require_ingestion_run(input.ingestion_run_id, repository)
    desired = IngestionRun.model_validate(
        current.model_dump()
        | {
            "normalized_source_url": input.normalized_source_url,
            "status": IngestionRunStatus.ERROR,
            "completed_at": clock.now(),
            "source_id": input.source_id,
            "document_id": input.document_id,
            "representation_id": input.representation_id,
            "provenance_activity_id": input.provenance_activity_id,
            "failure_stage": input.failure_stage,
            "failure_code": input.failure_code,
            "safe_failure_message": input.safe_failure_message,
        }
    )
    return _complete_terminal_run(current, desired, repository)


def list_ingestion_runs(repository: IngestionRunRepository) -> tuple[IngestionRun, ...]:
    return repository.list_ingestion_runs()


def _require_ingestion_run(
    ingestion_run_id: str, repository: IngestionRunRepository
) -> IngestionRun:
    record = repository.get_ingestion_run(ingestion_run_id)
    if record is None:
        raise ValueError(f"IngestionRun not found: {ingestion_run_id}")
    return record


def _complete_terminal_run(
    current: IngestionRun,
    desired: IngestionRun,
    repository: IngestionRunRepository,
) -> IngestionRun:
    if current.status is not IngestionRunStatus.RUNNING:
        if _same_terminal_state(current, desired):
            return current
        raise IngestionRunTransitionConflict("ingestion_run_transition_conflict")
    if repository.complete_ingestion_run_if_running(desired):
        return desired
    persisted = _require_ingestion_run(desired.id, repository)
    if _same_terminal_state(persisted, desired):
        return persisted
    raise IngestionRunTransitionConflict("ingestion_run_transition_conflict")


def _same_terminal_state(left: IngestionRun, right: IngestionRun) -> bool:
    if left.status is not right.status:
        return False
    return left.model_dump(exclude={"completed_at"}) == right.model_dump(exclude={"completed_at"})
