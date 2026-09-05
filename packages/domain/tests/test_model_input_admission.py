from datetime import UTC, datetime

import pytest
from kotekomi_domain import (
    ModelInputAdmission,
    ModelInputAdmissionStatus,
    ModelRun,
    ModelRunStatus,
)
from pydantic import ValidationError

NOW = datetime(2026, 9, 4, tzinfo=UTC)
DIGEST = "a" * 64


def _admission(
    *,
    formatted_input_token_count: int = 500,
    configured_context_limit: int = 512,
    loaded_context_limit: int = 2_048,
    status: ModelInputAdmissionStatus = ModelInputAdmissionStatus.READY,
) -> ModelInputAdmission:
    required_capacity = formatted_input_token_count + 8 + 4
    return ModelInputAdmission(
        id="mia_fixture",
        extraction_task_id="ext_fixture",
        model_profile_id="fixture-profile",
        model_identity_digest=DIGEST,
        runtime_identity="fixture-runtime",
        model_instance_id="fixture-model",
        tokenizer_id="fixture-tokenizer",
        prompt_template_identity="fixture-template",
        logical_input_digest=DIGEST,
        formatted_input_digest=DIGEST,
        configured_context_limit=configured_context_limit,
        loaded_context_limit=loaded_context_limit,
        effective_context_limit=min(configured_context_limit, loaded_context_limit),
        formatted_input_token_count=formatted_input_token_count,
        reserved_output_tokens=8,
        safety_margin_tokens=4,
        required_capacity=required_capacity,
        status=status,
        blocked_reason=(
            "complete_request_exceeds_context_budget"
            if status is ModelInputAdmissionStatus.CONTEXT_BUDGET_BLOCKED
            else None
        ),
    )


def _model_run(admission: ModelInputAdmission) -> ModelRun:
    return ModelRun(
        id="mrn_fixture",
        extraction_task_id="ext_fixture",
        task_fingerprint=DIGEST,
        model_identity={
            "name": "fixture-model",
            "weights_digest": None,
            "runtime": "fixture-runtime",
            "tokenizer_id": "fixture-tokenizer",
            "determinism_settings": [],
        },
        runtime_identity="fixture-runtime",
        tokenizer_id="fixture-tokenizer",
        prompt_digest=DIGEST,
        schema_digest=DIGEST,
        execution_spec_digest=DIGEST,
        generation_parameters={},
        input_admission=admission,
        runtime_invoked=False,
        status=ModelRunStatus.INPUT_BLOCKED,
        started_at=NOW,
        completed_at=NOW,
        execution_diagnostics={
            "elapsed_milliseconds": 0,
            "deadline_milliseconds": 300_000,
            "first_response_event_milliseconds": None,
        },
    )


def test_model_input_admission_recomputes_effective_and_required_capacity() -> None:
    admission = _admission()

    assert admission.effective_context_limit == 512
    assert admission.required_capacity == 512

    with pytest.raises(ValidationError, match="effective limit"):
        ModelInputAdmission.model_validate(
            {
                **admission.model_dump(),
                "effective_context_limit": 2_048,
            }
        )
    with pytest.raises(ValidationError, match="required capacity"):
        ModelInputAdmission.model_validate(
            {
                **admission.model_dump(),
                "required_capacity": 511,
            }
        )


def test_model_input_admission_status_must_match_capacity() -> None:
    with pytest.raises(ValidationError, match="must fit"):
        _admission(
            formatted_input_token_count=501,
            status=ModelInputAdmissionStatus.READY,
        )
    with pytest.raises(ValidationError, match="must exceed"):
        _admission(status=ModelInputAdmissionStatus.CONTEXT_BUDGET_BLOCKED)

    blocked = _admission(
        formatted_input_token_count=501,
        status=ModelInputAdmissionStatus.CONTEXT_BUDGET_BLOCKED,
    )
    assert blocked.required_capacity == 513


def test_input_blocked_model_run_is_an_attempt_without_model_response() -> None:
    blocked = _admission(
        formatted_input_token_count=501,
        status=ModelInputAdmissionStatus.CONTEXT_BUDGET_BLOCKED,
    )
    run = _model_run(blocked)

    assert run.runtime_invoked is False
    assert run.execution_receipt is None
    assert run.raw_output_artifact_id is None

    with pytest.raises(ValidationError, match="cannot invoke"):
        ModelRun.model_validate({**run.model_dump(), "runtime_invoked": True})
    with pytest.raises(ValidationError, match="cannot contain model response"):
        ModelRun.model_validate(
            {
                **run.model_dump(),
                "execution_receipt": {
                    "model_identity_digest": DIGEST,
                    "generation_parameters_digest": DIGEST,
                    "rendered_input_digest": DIGEST,
                    "input_token_count": 501,
                    "output_token_count": None,
                },
            }
        )


def test_model_run_keeps_runtime_usage_distinct_from_admitted_formatted_count() -> None:
    admission = _admission(formatted_input_token_count=36)

    run = ModelRun(
        id="mrn_fixture",
        extraction_task_id="ext_fixture",
        task_fingerprint=DIGEST,
        model_identity={"name": "fixture-model"},
        runtime_identity="fixture-runtime",
        tokenizer_id="fixture-tokenizer",
        prompt_digest=DIGEST,
        schema_digest=DIGEST,
        execution_spec_digest=DIGEST,
        generation_parameters={},
        input_admission=admission,
        runtime_invoked=True,
        raw_output_artifact_id="artifact_fixture",
        output_digest=DIGEST,
        status=ModelRunStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
        execution_diagnostics={
            "elapsed_milliseconds": 1,
            "deadline_milliseconds": 300_000,
            "first_response_event_milliseconds": None,
        },
        execution_receipt={
            "model_identity_digest": DIGEST,
            "generation_parameters_digest": DIGEST,
            "rendered_input_digest": admission.logical_input_digest,
            "input_token_count": 11,
            "output_token_count": 1,
        },
    )

    assert run.input_admission is not None
    assert run.input_admission.formatted_input_token_count == 36
    assert run.execution_receipt is not None
    assert run.execution_receipt["input_token_count"] == 11
