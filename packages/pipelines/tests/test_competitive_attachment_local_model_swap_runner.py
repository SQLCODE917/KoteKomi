from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from kotekomi_domain import ModelRun, ModelRunStatus

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_local_model_swap")


def test_model_swap_uses_model_specific_transport_allowances() -> None:
    runner = _runner()

    assert runner.COMPARATOR_EFFECTIVE_MAX_OUTPUT_TOKENS == 2
    assert runner.CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS == 16


def test_runtime_failure_reports_the_preserved_model_error() -> None:
    runner = _runner()
    model_run = ModelRun.model_construct(
        status=ModelRunStatus.RUNTIME_FAILED,
        error_code="ModelRuntimeResponseError",
        error_message="LM Studio response must contain exactly one output_text value.",
    )

    with pytest.raises(
        ValueError,
        match=(
            "runtime_failed: ModelRuntimeResponseError: "
            "LM Studio response must contain exactly one output_text value"
        ),
    ):
        runner._require_successful_model_run(
            model_run,
            task_id="aet_fixture",
            expected_effective_max_output_tokens=16,
        )


def test_successful_run_requires_the_declared_transport_allowance() -> None:
    runner = _runner()
    model_run = ModelRun.model_construct(
        status=ModelRunStatus.SUCCEEDED,
        generation_parameters={"max_output_tokens": 2},
    )

    with pytest.raises(ValueError, match="wrong effective output-token limit"):
        runner._require_successful_model_run(
            model_run,
            task_id="aet_fixture",
            expected_effective_max_output_tokens=16,
        )


def test_output_calibration_binds_exact_input_and_completed_sse(tmp_path: Path) -> None:
    runner = _runner()
    exact_input = b"semantic task\n/no_think\n"
    input_sha256 = hashlib.sha256(exact_input).hexdigest()
    completed = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "N"}],
            }
        ],
        "usage": {
            "output_tokens": 1,
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }
    result = {
        "schema_version": "qwen3_exact_output_probe_v1",
        "input_sha256": input_sha256,
        "status": "completed",
        "output_texts": ["N"],
        "output_token_count": 1,
        "reasoning_token_count": 0,
    }
    request = {
        "model": "qwen3-fixture",
        "input": exact_input.decode(),
        "stream": True,
        "frequency_penalty": 0.0,
        "max_output_tokens": 16,
        "seed": 17,
        "temperature": 0,
        "include": ["message.output_text.logprobs"],
        "top_logprobs": 10,
    }
    status = {
        "schema_version": "qwen3_exact_output_probe_status_v1",
        "status": "complete",
        "probe_status": 0,
        "run_root": str(tmp_path),
        "result": str(tmp_path / "result.json"),
    }
    (tmp_path / "exact-input.txt").write_bytes(exact_input)
    (tmp_path / "request.json").write_text(json.dumps(request), encoding="utf-8")
    (tmp_path / "completed.json").write_text(json.dumps(completed), encoding="utf-8")
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps(status), encoding="utf-8")
    (tmp_path / "response.sse").write_text(
        "data: " + json.dumps({"type": "response.completed", "response": completed}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "model-load.log").write_text("loaded\n", encoding="utf-8")

    calibration, result_reference, references = runner._validated_output_calibration(
        tmp_path,
        expected_input_sha256s=frozenset({"f" * 64, input_sha256}),
        expected_model_id="qwen3-fixture",
    )

    assert calibration.output_texts == ("N",)
    assert result_reference.label == "output_calibration_result"
    assert len(references) == 7

    with pytest.raises(ValueError, match="different model input"):
        runner._validated_output_calibration(
            tmp_path,
            expected_input_sha256s=frozenset({"f" * 64}),
            expected_model_id="qwen3-fixture",
        )
