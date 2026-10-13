"""Execution boundary DTOs and ingestion lifecycle decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from kotekomi_domain import (
    IngestionFailureCode,
    IngestionFailureStage,
    IngestionRun,
    IngestionRunStatus,
)
from pydantic import BaseModel, ConfigDict, Field

from kotekomi_application.ingestion_inspection import ParagraphSnapshot
from kotekomi_application.ingestion_runs import (
    CompleteIngestionRunErrorInput,
    IngestionRunClock,
    IngestionRunRepository,
    complete_ingestion_run_as_error,
)


class ProcessRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class IngestionProcessRequest(ProcessRecord):
    config_path: str
    source_path: str
    source_url: str
    ledger_path: str
    ingestion_run_id: str
    paragraph_ordinal: int | None


class ParagraphEvent(ProcessRecord):
    kind: Literal["paragraph"] = "paragraph"
    snapshot: ParagraphSnapshot


class TextEvent(ProcessRecord):
    kind: Literal["text"] = "text"
    text: str
    is_error: bool


class FinishedEvent(ProcessRecord):
    kind: Literal["finished"] = "finished"
    code: int


ProcessEvent = Annotated[ParagraphEvent | TextEvent | FinishedEvent, Field(discriminator="kind")]


@dataclass(frozen=True)
class AssignedIngestionRunIdFactory:
    record_id: str

    def new_ingestion_run_id(self) -> str:
        return self.record_id


@dataclass(frozen=True)
class StoppedExecutionInput:
    ingestion_run_id: str
    interrupted: bool


@dataclass(frozen=True)
class StoppedExecutionResult:
    disposition: Literal["not_started", "already_terminal", "closed_error"]
    run: IngestionRun | None


def finalize_inspection_execution(
    input: StoppedExecutionInput, ledger: IngestionRunRepository, clock: IngestionRunClock
) -> StoppedExecutionResult:
    run = ledger.get_ingestion_run(input.ingestion_run_id)
    if run is None:
        return StoppedExecutionResult("not_started", None)
    if run.status is not IngestionRunStatus.RUNNING:
        return StoppedExecutionResult("already_terminal", run)
    result = complete_ingestion_run_as_error(
        CompleteIngestionRunErrorInput(
            ingestion_run_id=run.id,
            failure_stage=IngestionFailureStage.INTERRUPTION
            if input.interrupted
            else IngestionFailureStage.AUTOMATIC_EXTRACTION,
            failure_code=IngestionFailureCode.USER_INTERRUPTED
            if input.interrupted
            else IngestionFailureCode.AUTOMATIC_EXTRACTION_FAILED,
            safe_failure_message="Ingestion interrupted by the user."
            if input.interrupted
            else "The ingestion worker stopped unexpectedly.",
        ),
        ledger,
        clock,
    )
    return StoppedExecutionResult("closed_error", result)
