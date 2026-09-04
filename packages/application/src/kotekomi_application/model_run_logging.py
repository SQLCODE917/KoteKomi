"""Read-only, safe-to-display diagnostics for durable model invocation attempts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from kotekomi_domain import ModelRun
from kotekomi_domain.models import JsonValue


class ModelRunLogLedger(Protocol):
    def list_model_runs(self) -> tuple[ModelRun, ...]: ...


@dataclass(frozen=True)
class ListModelRunLogsInput:
    limit: int = 100

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit <= 0:
            raise ValueError("Model run log limit must be a positive integer.")


@dataclass(frozen=True)
class ModelRunLogEntry:
    model_run_id: str
    extraction_task_id: str
    runtime_identity: str
    status: str
    started_at: str
    completed_at: str
    requested_max_output_tokens: int | None
    input_token_count: int | None
    output_token_count: int | None
    elapsed_milliseconds: int
    deadline_milliseconds: int
    first_response_event_milliseconds: int | None
    error_code: str | None


@dataclass(frozen=True)
class ListModelRunLogsResult:
    entries: tuple[ModelRunLogEntry, ...]


def list_model_run_logs(
    input: ListModelRunLogsInput,
    ledger_repository: ModelRunLogLedger,
) -> ListModelRunLogsResult:
    ordered_runs = sorted(
        ledger_repository.list_model_runs(),
        key=lambda run: (run.started_at, run.id),
        reverse=True,
    )
    return ListModelRunLogsResult(
        entries=tuple(model_run_log_entry(run) for run in ordered_runs[: input.limit])
    )


def model_run_logs_to_json(result: ListModelRunLogsResult) -> dict[str, JsonValue]:
    return {
        "model_runs": [
            {
                "model_run_id": entry.model_run_id,
                "extraction_task_id": entry.extraction_task_id,
                "runtime_identity": entry.runtime_identity,
                "status": entry.status,
                "started_at": entry.started_at,
                "completed_at": entry.completed_at,
                "requested_max_output_tokens": entry.requested_max_output_tokens,
                "input_token_count": entry.input_token_count,
                "output_token_count": entry.output_token_count,
                "elapsed_milliseconds": entry.elapsed_milliseconds,
                "deadline_milliseconds": entry.deadline_milliseconds,
                "first_response_event_milliseconds": entry.first_response_event_milliseconds,
                "error_code": entry.error_code,
            }
            for entry in result.entries
        ]
    }


def model_run_log_entry(run: ModelRun) -> ModelRunLogEntry:
    diagnostics = run.execution_diagnostics
    receipt = run.execution_receipt
    requested_max_output_tokens = run.generation_parameters.get("max_output_tokens")
    return ModelRunLogEntry(
        model_run_id=run.id,
        extraction_task_id=run.extraction_task_id,
        runtime_identity=run.runtime_identity,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat(),
        requested_max_output_tokens=_optional_int(requested_max_output_tokens),
        input_token_count=(
            _optional_int(receipt.get("input_token_count")) if receipt is not None else None
        ),
        output_token_count=(
            _optional_int(receipt.get("output_token_count")) if receipt is not None else None
        ),
        elapsed_milliseconds=_required_int(diagnostics, "elapsed_milliseconds"),
        deadline_milliseconds=_required_int(diagnostics, "deadline_milliseconds"),
        first_response_event_milliseconds=_optional_int(
            diagnostics["first_response_event_milliseconds"]
        ),
        error_code=run.error_code,
    )


def _required_int(values: dict[str, JsonValue], key: str) -> int:
    value = values[key]
    if type(value) is not int:
        raise ValueError(f"ModelRun {key} must be an integer.")
    return value


def _optional_int(value: JsonValue | None) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise ValueError("ModelRun displayable token fields must be integers when present.")
    return value
