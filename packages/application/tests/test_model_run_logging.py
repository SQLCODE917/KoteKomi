from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_application import (
    ListModelRunLogsInput,
    ListModelRunLogsResult,
    list_model_run_logs,
    model_run_log_entry,
    model_run_logs_to_json,
)
from kotekomi_domain import (
    ModelInputAdmission,
    ModelInputAdmissionStatus,
    ModelRun,
    ModelRunStatus,
)

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
    assert entry.runtime_reported_input_token_count == 44
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
                "runtime_reported_input_token_count": 44,
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


def test_input_blocked_log_explains_capacity_without_claiming_runtime_usage() -> None:
    admission = ModelInputAdmission(
        id="mia_blocked",
        extraction_task_id="ext_fixture",
        model_profile_id="fixture-profile",
        model_identity_digest="a" * 64,
        runtime_identity="lm_studio",
        model_instance_id="fixture-model",
        tokenizer_id="fixture-tokenizer",
        prompt_template_identity="fixture-template",
        logical_input_digest="b" * 64,
        formatted_input_digest="c" * 64,
        configured_context_limit=512,
        loaded_context_limit=16_384,
        effective_context_limit=512,
        formatted_input_token_count=2_039,
        reserved_output_tokens=8,
        safety_margin_tokens=4,
        required_capacity=2_051,
        status=ModelInputAdmissionStatus.CONTEXT_BUDGET_BLOCKED,
        blocked_reason="complete_request_exceeds_context_budget",
    )
    run = ModelRun(
        id="mrn_blocked",
        extraction_task_id="ext_fixture",
        task_fingerprint="a" * 64,
        model_identity={"name": "fixture-model"},
        runtime_identity="lm_studio",
        tokenizer_id="fixture-tokenizer",
        prompt_digest="a" * 64,
        schema_digest="a" * 64,
        execution_spec_digest="a" * 64,
        generation_parameters={"max_output_tokens": 8},
        input_admission=admission,
        runtime_invoked=False,
        status=ModelRunStatus.INPUT_BLOCKED,
        started_at=NOW,
        completed_at=NOW,
        execution_diagnostics={
            "elapsed_milliseconds": 1,
            "deadline_milliseconds": 300_000,
            "first_response_event_milliseconds": None,
        },
    )

    entry = model_run_log_entry(run)
    model_runs = model_run_logs_to_json(ListModelRunLogsResult((entry,)))["model_runs"]

    assert isinstance(model_runs, list)
    payload = model_runs[0]
    assert isinstance(payload, dict)
    assert payload["status"] == "input_blocked"
    assert payload["runtime_invoked"] is False
    assert payload["runtime_reported_input_token_count"] is None
    assert payload["admitted_input_token_count"] == 2_039
    assert payload["effective_context_limit"] == 512
    assert payload["required_capacity"] == 2_051
    assert payload["input_admission_reason"] == "complete_request_exceeds_context_budget"


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
