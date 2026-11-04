"""Offline R18 report rebuilding from durable, independently checked evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from kotekomi_application import (
    DiscriminationExecutionBinding,
    DiscriminationObservationItem,
    ExperimentalObservation,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelTaskRequest,
    ModelTaskResponse,
    TerminalOutcome,
    discrimination_report_fingerprint,
    discrimination_signals_from_parsed,
    frozen_semantic_selection_contract,
    generation_parameters_digest,
    model_identity_snapshot_digest,
    parse_corrective_reselection_answer,
)

ROOT = Path(__file__).resolve().parents[3]

# The current runner regression verifies reviewed inputs, reviewed decision texts,
# and the negative evidence checks. It adopts the live implementation binding, so a
# behavior-preserving move needs no manual rebind. The frozen historical contract and
# run are reproduced only in `scripts/run_r18_historical_reproduction.sh`.
CURRENT_CONTRACT_DIR = ROOT / "data/r18-current-regression"


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_semantic_instruction_discrimination")


def test_current_regression_reviewed_inputs_and_decisions_are_stable() -> None:
    """ISC-04: current regressions bind reviewed content, not implementation source.

    A behavior-preserving move or import change must not alter these digests, so a
    routine shared-module edit never requires a manual rebind. Changing a reviewed
    input or decision text requires a reviewed edit of the expectations file.
    """
    from kotekomi_application.semantic_selection_contract import content_digest

    contract = frozen_semantic_selection_contract(directory=CURRENT_CONTRACT_DIR)
    raw = json.loads((CURRENT_CONTRACT_DIR / "reference_policy_records.json").read_text())[
        "records"
    ]
    expectations = json.loads((CURRENT_CONTRACT_DIR / "reviewed_expectations.json").read_text())

    assert content_digest(raw) == expectations["policy_records_sha256"]
    assert (
        content_digest(
            {
                "eligibility_rule": contract.eligibility_rule,
                "complete_selected_set_rules": contract.complete_selected_set_rules,
                "none_rule": contract.none_rule,
                "canonical_boundary_rules": contract.canonical_boundary_rules,
                "signal_definitions": [
                    (definition.name.value, definition.values, definition.not_applicable_when)
                    for definition in contract.signal_definitions
                ],
            }
        )
        == expectations["thresholds_sha256"]
    )


def test_execute_archives_binding_and_rebuilds_without_more_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner()
    identity = ModelIdentitySnapshot(
        name="qwen2.5-14b-instruct",
        weights_digest=None,
        runtime="lm_studio",
        tokenizer_id="fixture-tokenizer",
    )

    class FakeRuntime:
        configured_identity = identity
        requests: list[ModelTaskRequest]

        def __init__(self) -> None:
            self.requests = []
            self.closed = False

        def check_readiness(self) -> SimpleNamespace:
            return SimpleNamespace(ready=True)

        def inspect_model_input(
            self, request: ModelInputInspectionRequest
        ) -> ModelInputMeasurement:
            return ModelInputMeasurement(
                model_identity_digest=model_identity_snapshot_digest(identity),
                runtime_identity=identity.runtime,
                model_instance_id=identity.name,
                tokenizer_id=identity.tokenizer_id,
                prompt_template_identity="fixture-template",
                logical_input_digest=request.logical_input_digest,
                formatted_input_digest=request.logical_input_digest,
                formatted_input_token_count=100,
                loaded_context_limit=65_536,
            )

        def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
            self.requests.append(task)
            return ModelTaskResponse(
                b"C1",
                ModelExecutionReceipt(
                    model_identity_digest=model_identity_snapshot_digest(identity),
                    generation_parameters_digest=generation_parameters_digest(
                        task.execution_spec.generation_parameters
                    ),
                    rendered_input_digest=task.rendered_input_digest,
                    input_token_count=100,
                    output_token_count=1,
                ),
                None,
            )

        def close(self) -> None:
            self.closed = True

    runtime = FakeRuntime()

    def fake_runtime(_config: object) -> FakeRuntime:
        return runtime

    monkeypatch.setattr(runner, "build_model_task_runtime", fake_runtime)
    monkeypatch.setattr(runner, "DATA_DIR", CURRENT_CONTRACT_DIR)
    args = argparse.Namespace(config=runner.DEFAULT_CONFIG, run_root=tmp_path)
    assert runner._prepare(args) == 0
    assert runner._execute(args) == 0
    assert runtime.closed
    assert len(runtime.requests) == 22
    binding = DiscriminationExecutionBinding.model_validate_json(
        (tmp_path / "execution.json").read_bytes()
    )
    assert binding.model_identity == identity
    sealed = (tmp_path / "report.json").read_bytes()
    assert runner._report(args) == 0
    assert (tmp_path / "report.json").read_bytes() == sealed
    assert len(runtime.requests) == 22


@pytest.fixture
def archived_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Path]:
    runner = _runner()

    def reject_runtime(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Rebuilding evidence must not construct a model runtime.")

    monkeypatch.setattr(runner, "build_model_task_runtime", reject_runtime)
    monkeypatch.setattr(runner, "DATA_DIR", CURRENT_CONTRACT_DIR)
    runner._prepare(argparse.Namespace(config=runner.DEFAULT_CONFIG, run_root=tmp_path))
    state = runner._load_prepared_state(tmp_path)
    binding = DiscriminationExecutionBinding(
        model_identity=ModelIdentitySnapshot(
            name=state.model,
            weights_digest=None,
            runtime=state.adapter,
            tokenizer_id="fixture-tokenizer",
        ),
        generation_parameters=runner._generation_parameters(state.max_output_tokens),
    )
    runner._write_json(tmp_path / "execution.json", binding.model_dump(mode="json"))
    (tmp_path / "responses").mkdir()
    (tmp_path / "items").mkdir()
    records = {record.event_id: record for record in state.records}
    for prompt in state.prompts:
        record = records[prompt.event_id]
        raw = (",".join(record.expected_selected_set) or "NONE").encode()
        parsed = parse_corrective_reselection_answer(raw.decode(), record.task, prompt.route)
        identity_digest = model_identity_snapshot_digest(binding.model_identity)
        generation_digest = generation_parameters_digest(binding.generation_parameters)
        observation = ExperimentalObservation(
            observation_id=runner._deterministic_id("obs", prompt.pair_id, prompt.prompt_sha256),
            event_id=prompt.event_id,
            route=prompt.route,
            variant=prompt.variant,
            review_status="unreviewed_experimental",
            model_identity_digest=identity_digest,
            generation_parameters_digest=generation_digest,
            rendered_input_digest=prompt.prompt_sha256,
            raw_response_sha256=hashlib.sha256(raw).hexdigest(),
            receipt={
                "model_identity_digest": identity_digest,
                "generation_parameters_digest": generation_digest,
                "rendered_input_digest": prompt.prompt_sha256,
                "input_token_count": 100,
                "output_token_count": 3,
                "output_token_probabilities": [],
            },
            parsed_answer=parsed,
        )
        item = DiscriminationObservationItem(
            pair_id=prompt.pair_id,
            event_id=prompt.event_id,
            route=prompt.route,
            variant=prompt.variant,
            outcome=TerminalOutcome.ANSWERED,
            model_invoked=True,
            observation=observation,
            signals=discrimination_signals_from_parsed(policy_record=record, parsed=parsed),
        )
        runner._write_json(
            tmp_path / "items" / f"{prompt.pair_id}.json", item.model_dump(mode="json")
        )
        (tmp_path / "responses" / f"{prompt.pair_id}.bin").write_bytes(raw)
    return runner, tmp_path


def test_report_rebuilds_all_twenty_two_archived_pairs_without_runtime(
    archived_run: tuple[Any, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, root = archived_run

    def reject_config(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Offline rebuilding must use the archived configuration.")

    monkeypatch.setattr(runner, "_config", reject_config)
    assert runner._report(argparse.Namespace(run_root=root)) == 0
    original = (root / "report.json").read_bytes()
    assert runner._report(argparse.Namespace(run_root=root)) == 0
    assert (root / "report.json").read_bytes() == original
    report = runner._read_json(root / "report.json")
    assert report["item_count"] == 22
    assert report["comparison_complete"] is True


def test_report_rejects_matching_raw_digest_with_stale_parse(
    archived_run: tuple[Any, Path],
) -> None:
    runner, root = archived_run
    path = root / "items/AHE-022::format_only.json"
    item = runner._read_json(path)
    (root / "responses/AHE-022::format_only.bin").write_bytes(b"NONE")
    item["observation"]["raw_response_sha256"] = hashlib.sha256(b"NONE").hexdigest()
    runner._write_json(path, item)
    with pytest.raises(ValueError, match="stored parse differs from the archived response"):
        runner._report(argparse.Namespace(run_root=root))
    assert not (root / "report.json").exists()


@pytest.mark.parametrize("command", ["_report", "_show"])
def test_report_commands_reject_rehashed_impossible_counts(
    archived_run: tuple[Any, Path], command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    runner, root = archived_run
    runner._report(argparse.Namespace(run_root=root))
    path = root / "report.json"
    payload = runner._read_json(path)
    payload["signal_comparisons"][0]["format_value_counts"] = {"invalid": 999}
    payload["result_fingerprint"] = discrimination_report_fingerprint(payload)
    runner._write_json(path, payload)
    altered = path.read_bytes()
    capsys.readouterr()
    with pytest.raises(ValueError, match="comparisons differ from the report items"):
        getattr(runner, command)(argparse.Namespace(run_root=root))
    assert capsys.readouterr().out == ""
    assert path.read_bytes() == altered


def test_report_rejects_stale_signals_without_rewriting_sealed_report(
    archived_run: tuple[Any, Path],
) -> None:
    runner, root = archived_run
    runner._report(argparse.Namespace(run_root=root))
    sealed = (root / "report.json").read_bytes()
    path = root / "items/AHE-022::format_only.json"
    item = runner._read_json(path)
    item["signals"][1]["value"] = "unmet"
    runner._write_json(path, item)
    with pytest.raises(ValueError, match="stored signals differ from the recomputed results"):
        runner._report(argparse.Namespace(run_root=root))
    assert (root / "report.json").read_bytes() == sealed


def test_report_rejects_empty_receipt(archived_run: tuple[Any, Path]) -> None:
    runner, root = archived_run
    path = root / "items/AHE-022::format_only.json"
    item = runner._read_json(path)
    item["observation"]["receipt"] = {}
    runner._write_json(path, item)
    with pytest.raises(ValueError, match="receipt payload has an invalid shape"):
        runner._load_evidence(root)


def test_report_rejects_prepared_prompt_drift_even_with_recomputed_digest(
    archived_run: tuple[Any, Path],
) -> None:
    runner, root = archived_run
    path = root / "prompts.json"
    prompts = runner._read_json_list(path)
    prompts[0]["prompt"] += "\nAdditional instruction."
    prompts[0]["prompt_sha256"] = hashlib.sha256(prompts[0]["prompt"].encode()).hexdigest()
    runner._write_json(path, prompts)
    with pytest.raises(ValueError, match="prepared prompts drifted from the frozen render"):
        runner._load_evidence(root)


@pytest.mark.parametrize("field", ["generation_parameters_digest", "model_identity_digest"])
def test_report_rejects_self_consistent_receipt_and_observation_drift(
    archived_run: tuple[Any, Path],
    field: str,
) -> None:
    runner, root = archived_run
    path = root / "items/AHE-022::format_only.json"
    item = runner._read_json(path)
    item["observation"][field] = "0" * 64
    item["observation"]["receipt"][field] = "0" * 64
    runner._write_json(path, item)
    with pytest.raises(ValueError, match="differs? from the run binding"):
        runner._load_evidence(root)


def test_report_rejects_execution_settings_that_drift_from_preparation(
    archived_run: tuple[Any, Path],
) -> None:
    runner, root = archived_run
    path = root / "execution.json"
    binding = runner._read_json(path)
    binding["generation_parameters"][1]["value"] = 18
    runner._write_json(path, binding)
    with pytest.raises(
        ValueError, match="execution settings differ from its prepared model binding"
    ):
        runner._load_evidence(root)


def test_report_rejects_missing_answered_response(archived_run: tuple[Any, Path]) -> None:
    runner, root = archived_run
    (root / "responses/AHE-022::format_only.bin").unlink()
    with pytest.raises(ValueError, match="requires archived response evidence"):
        runner._load_evidence(root)


@pytest.mark.parametrize("outcome", ["blocked", "failed"])
def test_report_preserves_terminal_pairs_without_responses(
    archived_run: tuple[Any, Path],
    outcome: str,
) -> None:
    runner, root = archived_run
    path = root / "items/AHE-022::format_only.json"
    item = runner._read_json(path)
    item.update(outcome=outcome, observation=None, signals=None, error="fixture terminal outcome")
    item["model_invoked"] = outcome == "failed"
    runner._write_json(path, item)
    (root / "responses/AHE-022::format_only.bin").unlink()
    assert runner._report(argparse.Namespace(run_root=root)) == 0
    report = runner._read_json(root / "report.json")
    assert report["item_count"] == 22
    assert report["comparison_complete"] is False


def test_behavior_preserving_move_needs_no_contract_rebind(tmp_path: Path) -> None:
    """ISC-04-A: a stale recorded digest must not block current regressions.

    A behavior-preserving move or import change alters implementation source, so a
    recorded development digest goes stale. The current regression must still load
    the reviewed content and prepare its run without a manual rebind.
    """
    runner = _runner()
    monkeypatch = pytest.MonkeyPatch()
    original_loader = runner.frozen_semantic_selection_contract

    def stale_loader(*, directory: Path) -> Any:
        contract = original_loader(directory=directory)
        binding = contract.binding.model_copy(
            update={"scoring_rules_sha256": "0" * 64, "renderer_sha256": "1" * 64}
        )
        return contract.model_copy(update={"binding": binding})

    monkeypatch.setattr(runner, "frozen_semantic_selection_contract", stale_loader)
    monkeypatch.setattr(runner, "DATA_DIR", CURRENT_CONTRACT_DIR)
    try:
        args = argparse.Namespace(config=runner.DEFAULT_CONFIG, run_root=tmp_path / "run")
        assert runner._prepare(args) == 0
        assert (tmp_path / "run" / "preparation.json").exists()
    finally:
        monkeypatch.undo()


def test_altered_reviewed_decision_text_is_rejected(tmp_path: Path) -> None:
    """A changed reviewed decision text must fail against its approved hash."""
    runner = _runner()
    monkeypatch = pytest.MonkeyPatch()
    original_loader = runner.frozen_semantic_selection_contract

    def altered_loader(*, directory: Path) -> Any:
        contract = original_loader(directory=directory)
        return contract.model_copy(
            update={
                "eligibility_rule": contract.eligibility_rule
                + " Select every candidate regardless of eligibility."
            }
        )

    monkeypatch.setattr(runner, "frozen_semantic_selection_contract", altered_loader)
    monkeypatch.setattr(runner, "DATA_DIR", CURRENT_CONTRACT_DIR)
    try:
        args = argparse.Namespace(config=runner.DEFAULT_CONFIG, run_root=tmp_path / "run")
        with pytest.raises(ValueError, match="thresholds"):
            runner._prepare(args)
    finally:
        monkeypatch.undo()
