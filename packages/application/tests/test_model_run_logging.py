from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_application import (
    ListModelRunLogsInput,
    list_model_run_logs,
    model_run_logs_to_json,
)
from kotekomi_domain import ModelRun, ModelRunStatus

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


class FakeModelRunLogLedger:
    def __init__(self, runs: tuple[ModelRun, ...]) -> None:
        self.runs = runs

    def list_model_runs(self) -> tuple[ModelRun, ...]:
        return self.runs


def test_list_model_run_logs_orders_newest_first_and_excludes_model_content() -> None:
    older = _model_run("mrn_older", NOW)
    newer = _model_run("mrn_newer", NOW + timedelta(minutes=1))

    result = list_model_run_logs(
        ListModelRunLogsInput(limit=1),
        FakeModelRunLogLedger((older, newer)),
    )

    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.model_run_id == newer.id
    assert entry.elapsed_milliseconds == 1250
    assert entry.deadline_milliseconds == 300000
    assert entry.first_response_event_milliseconds == 250
    assert entry.input_token_count == 44
    assert entry.output_token_count == 12
    assert entry.requested_max_output_tokens == 8192
    assert model_run_logs_to_json(result) == {
        "model_runs": [
            {
                "model_run_id": "mrn_newer",
                "extraction_task_id": "ext_fixture",
                "runtime_identity": "lm_studio",
                "status": "succeeded",
                "started_at": (NOW + timedelta(minutes=1)).isoformat(),
                "completed_at": (NOW + timedelta(minutes=1, seconds=2)).isoformat(),
                "requested_max_output_tokens": 8192,
                "input_token_count": 44,
                "output_token_count": 12,
                "elapsed_milliseconds": 1250,
                "deadline_milliseconds": 300000,
                "first_response_event_milliseconds": 250,
                "error_code": None,
            }
        ]
    }


def test_list_model_run_logs_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        ListModelRunLogsInput(limit=0)


def _model_run(record_id: str, started_at: datetime) -> ModelRun:
    digest = "a" * 64
    return ModelRun(
        id=record_id,
        extraction_task_id="ext_fixture",
        task_fingerprint=digest,
        model_identity={"name": "fixture-model"},
        runtime_identity="lm_studio",
        tokenizer_id="fixture_tokenizer_v1",
        prompt_digest=digest,
        schema_digest=digest,
        execution_spec_digest=digest,
        generation_parameters={"max_output_tokens": 8192},
        raw_output_artifact_id=record_id,
        output_digest=digest,
        status=ModelRunStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=2),
        execution_diagnostics={
            "elapsed_milliseconds": 1250,
            "deadline_milliseconds": 300000,
            "first_response_event_milliseconds": 250,
        },
        execution_receipt={
            "model_identity_digest": digest,
            "generation_parameters_digest": digest,
            "rendered_input_digest": digest,
            "input_token_count": 44,
            "output_token_count": 12,
        },
    )
