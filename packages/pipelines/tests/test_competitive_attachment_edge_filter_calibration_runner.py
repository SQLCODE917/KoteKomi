from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterDecisionStatus,
    ExecutionSetting,
    ExtractionStageStatus,
    build_extraction_stage_trace,
    generation_parameters_digest,
)
from kotekomi_domain import (
    ModelInputAdmission,
    ModelInputAdmissionStatus,
    ModelRun,
    ModelRunStatus,
)

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "a" * 64


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_edge_filter_calibration")


def test_model_failed_execution_is_preserved_before_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner()
    root = tmp_path / "run"
    directory = root / "diagnostic" / "v8" / "repetition-1"
    task_id = "aet_" + "1" * 24
    execution = directory / f"{task_id}.json"
    execution.parent.mkdir(parents=True)
    execution.write_text("first failure", encoding="utf-8")
    task = SimpleNamespace(task_id=task_id)
    decision = SimpleNamespace(status=AttachmentEdgeFilterDecisionStatus.MODEL_FAILED)

    def fake_validate(*_args: object, **_kwargs: object) -> tuple[Any, dict[str, Any]]:
        return decision, {}

    monkeypatch.setattr(
        runner.cea14,
        "validate_attachment_edge_filter_execution_record",
        fake_validate,
    )

    runner.quarantine_model_failed_executions(
        root=root,
        directory=directory,
        tasks=cast(Any, (task,)),
        expected_prompt_sha256="1" * 64,
        expected_runtime_contract={},
    )

    first = (
        root / "failed-attempts" / "diagnostic" / "v8" / "repetition-1" / task_id / "attempt-1.json"
    )
    assert first.read_text(encoding="utf-8") == "first failure"
    assert not execution.exists()

    execution.write_text("second failure", encoding="utf-8")
    runner.quarantine_model_failed_executions(
        root=root,
        directory=directory,
        tasks=cast(Any, (task,)),
        expected_prompt_sha256="1" * 64,
        expected_runtime_contract={},
    )

    second = first.with_name("attempt-2.json")
    assert second.read_text(encoding="utf-8") == "second failure"
    assert first.read_text(encoding="utf-8") == "first failure"


def test_complete_execution_is_reused_without_quarantine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner()
    root = tmp_path / "run"
    directory = root / "diagnostic" / "v8" / "repetition-1"
    task_id = "aet_" + "2" * 24
    execution = directory / f"{task_id}.json"
    execution.parent.mkdir(parents=True)
    execution.write_text("complete", encoding="utf-8")
    task = SimpleNamespace(task_id=task_id)
    decision = SimpleNamespace(status=AttachmentEdgeFilterDecisionStatus.COMPLETE)

    def fake_validate(*_args: object, **_kwargs: object) -> tuple[Any, dict[str, Any]]:
        return decision, {}

    monkeypatch.setattr(
        runner.cea14,
        "validate_attachment_edge_filter_execution_record",
        fake_validate,
    )

    runner.quarantine_model_failed_executions(
        root=root,
        directory=directory,
        tasks=cast(Any, (task,)),
        expected_prompt_sha256="1" * 64,
        expected_runtime_contract={},
    )

    assert execution.read_text(encoding="utf-8") == "complete"
    assert not (root / "failed-attempts").exists()


def test_json_native_model_run_uses_the_strict_json_boundary() -> None:
    runner = _runner()
    now = datetime(2026, 9, 20, tzinfo=UTC)
    admission = ModelInputAdmission(
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
        configured_context_limit=512,
        loaded_context_limit=512,
        effective_context_limit=512,
        formatted_input_token_count=100,
        reserved_output_tokens=8,
        safety_margin_tokens=4,
        required_capacity=112,
        status=ModelInputAdmissionStatus.READY,
    )
    model_run = ModelRun(
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
        started_at=now,
        completed_at=now,
        execution_diagnostics={
            "elapsed_milliseconds": 1,
            "deadline_milliseconds": 300_000,
            "first_response_event_milliseconds": None,
        },
        execution_receipt={
            "model_identity_digest": DIGEST,
            "generation_parameters_digest": DIGEST,
            "rendered_input_digest": DIGEST,
            "input_token_count": 100,
            "output_token_count": 1,
            "output_token_probabilities": [],
        },
    )

    parsed = runner.model_run_from_execution_record(
        {"model_run": model_run.model_dump(mode="json")}
    )

    assert parsed == model_run


def test_json_native_stage_trace_uses_the_strict_json_boundary() -> None:
    runner = _runner()
    trace = build_extraction_stage_trace(
        trace_run_id="fixture-run",
        ordinal=1,
        stage_id="competitive_attachment_edge_filter",
        stage_version="fixture-v1",
        producer_id="fixture-model",
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        input_record_ids=("input_fixture",),
        execution_record_ids=("ext_fixture", "mrn_fixture"),
        configuration={"prompt_sha256": DIGEST},
        input_payload={"edge_id": "edge_fixture"},
        output_payload={"answer": "Y"},
        status=ExtractionStageStatus.COMPLETED,
    )

    parsed = runner.extraction_stage_trace_from_execution_record(
        {"trace": trace.model_dump(mode="json")}
    )

    assert parsed == trace


def test_execution_evidence_uses_the_bounded_task_generation_contract() -> None:
    runner = _runner()
    now = datetime(2026, 9, 20, tzinfo=UTC)
    configured = (
        ExecutionSetting("max_output_tokens", 2_048),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", 10),
    )
    effective = (
        ExecutionSetting("max_output_tokens", 3),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", 10),
    )
    model_run = ModelRun(
        id="mrn_fixture",
        extraction_task_id="ext_fixture",
        task_fingerprint=DIGEST,
        model_identity={"name": "fixture-model"},
        runtime_identity="fixture-runtime",
        tokenizer_id="fixture-tokenizer",
        prompt_digest=DIGEST,
        schema_digest=DIGEST,
        execution_spec_digest=DIGEST,
        generation_parameters={item.key: item.value for item in effective},
        input_admission=None,
        runtime_invoked=True,
        raw_output_artifact_id="artifact_fixture",
        output_digest=DIGEST,
        status=ModelRunStatus.SUCCEEDED,
        started_at=now,
        completed_at=now,
        execution_diagnostics={
            "elapsed_milliseconds": 1,
            "deadline_milliseconds": 300_000,
            "first_response_event_milliseconds": None,
        },
        execution_receipt={
            "model_identity_digest": DIGEST,
            "generation_parameters_digest": generation_parameters_digest(effective),
            "rendered_input_digest": DIGEST,
            "input_token_count": 100,
            "output_token_count": 1,
            "output_token_probabilities": [],
        },
    )

    receipt = runner.validate_execution_generation_evidence(model_run, configured)

    assert receipt.generation_parameters_digest == generation_parameters_digest(effective)


def test_execution_evidence_rejects_the_unbounded_configured_ceiling() -> None:
    runner = _runner()
    now = datetime(2026, 9, 20, tzinfo=UTC)
    configured = (
        ExecutionSetting("max_output_tokens", 2_048),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", 10),
    )
    model_run = ModelRun(
        id="mrn_fixture",
        extraction_task_id="ext_fixture",
        task_fingerprint=DIGEST,
        model_identity={"name": "fixture-model"},
        runtime_identity="fixture-runtime",
        tokenizer_id="fixture-tokenizer",
        prompt_digest=DIGEST,
        schema_digest=DIGEST,
        execution_spec_digest=DIGEST,
        generation_parameters={item.key: item.value for item in configured},
        input_admission=None,
        runtime_invoked=True,
        raw_output_artifact_id="artifact_fixture",
        output_digest=DIGEST,
        status=ModelRunStatus.SUCCEEDED,
        started_at=now,
        completed_at=now,
        execution_diagnostics={
            "elapsed_milliseconds": 1,
            "deadline_milliseconds": 300_000,
            "first_response_event_milliseconds": None,
        },
        execution_receipt={
            "model_identity_digest": DIGEST,
            "generation_parameters_digest": generation_parameters_digest(configured),
            "rendered_input_digest": DIGEST,
            "input_token_count": 100,
            "output_token_count": 1,
            "output_token_probabilities": [],
        },
    )

    with pytest.raises(ValueError, match="execution generation settings drifted"):
        runner.validate_execution_generation_evidence(model_run, configured)
