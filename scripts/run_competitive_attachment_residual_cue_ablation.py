#!/usr/bin/env python3
"""Run the CEA-1.8 demonstration cue ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Literal

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentResidualCueAblationPackageStatus,
    AttachmentResidualCueAblationPreflight,
    AttachmentResidualCueAblationReport,
    AttachmentResidualCueAblationStatus,
    AttachmentResidualOwnershipObservation,
    AttachmentResidualOwnershipPreflight,
    AttachmentResidualOwnershipReport,
    ExecutionSetting,
    ExtractionStageTrace,
    ModelExecutionReceipt,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_edge_filter_calibration import (
    attachment_answer_probability,
)
from kotekomi_pipelines.competitive_attachment_residual_cue_ablation import (
    build_residual_cue_ablation_preflight,
    build_residual_cue_ablation_report,
    render_residual_cue_ablation_handoff,
    render_residual_cue_ablation_review,
)
from kotekomi_pipelines.competitive_attachment_residual_ownership import (
    build_attachment_residual_ownership_report,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-demonstration-cue-ablation.md"
BASELINE_PROMPT_PATH = REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_v1.md"
CUE_PROMPT_PATH = REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_v2.md"
CUE_PROMPT_ID = "competitive_attachment_residual_ownership_v2"
TOP_LOGPROBS = 10


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--baseline-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)

    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.8 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    baseline_root = args.baseline_root.resolve()
    config = _config(args.config)
    baseline_run = _read_json(baseline_root / "run.json")
    baseline_status = _read_json(baseline_root / "status.json")
    if baseline_run.get("status") != "complete" or baseline_status.get("status") != "complete":
        raise ValueError("CEA-1.8 requires a complete CEA-1.7 baseline.")
    _validate_runtime(config, baseline_run)
    baseline_preflight = AttachmentResidualOwnershipPreflight.model_validate_json(
        (baseline_root / "preflight.json").read_bytes()
    )
    baseline_report = AttachmentResidualOwnershipReport.model_validate_json(
        (baseline_root / "report.json").read_bytes()
    )
    baseline_prompt = _file_reference("baseline_prompt", BASELINE_PROMPT_PATH)
    if baseline_report.prompt.sha256 != baseline_prompt.sha256:
        raise ValueError("CEA-1.8 repository Baseline Prompt differs from CEA-1.7.")
    cue_prompt = _file_reference("cue_prompt", CUE_PROMPT_PATH)
    inputs = tuple(
        sorted(
            (
                _file_reference("baseline_preflight", baseline_root / "preflight.json"),
                _file_reference("baseline_report", baseline_root / "report.json"),
                _file_reference("baseline_run", baseline_root / "run.json"),
                _file_reference("baseline_status", baseline_root / "status.json"),
                _file_reference("tdd", TDD_PATH),
                *(
                    AttachmentEvidenceReference(
                        label=f"predecessor_{item.label}",
                        path=item.path,
                        sha256=item.sha256,
                    )
                    for item in baseline_preflight.inputs
                ),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_residual_cue_ablation_preflight(
        inputs=inputs,
        baseline_prompt=baseline_prompt,
        cue_prompt=cue_prompt,
        baseline_prompt_text=BASELINE_PROMPT_PATH.read_text(encoding="utf-8"),
        cue_prompt_text=CUE_PROMPT_PATH.read_text(encoding="utf-8"),
        baseline_report=baseline_report,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(configured_generation)
    metadata = dict(baseline_run)
    for key in (
        "diagnostic_review_sha256",
        "generation_parameters",
        "generation_parameters_sha256",
        "handoff_sha256",
        "report_sha256",
        "top_logprobs",
    ):
        metadata.pop(key, None)
    metadata.update(
        {
            "schema_version": "attachment_residual_cue_ablation_run_v1",
            "status": "prepared",
            "config_path": str(args.config.resolve()),
            "baseline_root": str(baseline_root),
            "prompt_path": str(CUE_PROMPT_PATH),
            "prompt_sha256": cue_prompt.sha256,
            "prompt_id": CUE_PROMPT_ID,
            "tdd_path": str(TDD_PATH),
            "preflight_sha256": preflight.result_fingerprint,
            "configured_generation_parameters": _generation_payload(configured_generation),
            "configured_generation_parameters_sha256": generation_parameters_digest(
                configured_generation
            ),
            "effective_generation_parameters": _generation_payload(effective_generation),
            "effective_generation_parameters_sha256": generation_parameters_digest(
                effective_generation
            ),
            "top_logprobs": TOP_LOGPROBS,
            "production_integration": "not_activated",
        }
    )
    _write_json(root / "run.json", metadata)
    _write_json(root / "preflight.json", preflight.model_dump(mode="json"))
    _write_json(
        root / "tasks-development.json",
        [item.model_dump(mode="json") for item in preflight.tasks],
    )
    status = _status(root, AttachmentResidualCueAblationPackageStatus.PREPARED)
    _write_json(root / "status.json", status.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "preflight": str(root / "preflight.json"),
                "run_root": str(root),
                "status": status.status.value,
            },
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    if metadata.get("status") not in {"prepared", "complete"}:
        raise ValueError("CEA-1.8 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentResidualCueAblationPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_sha256"):
        raise ValueError("CEA-1.8 preflight digest drifted.")
    for reference in (*preflight.inputs, preflight.baseline_prompt, preflight.cue_prompt):
        _validate_reference(reference)
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(configured_generation)
    if _generation_payload(configured_generation) != metadata.get(
        "configured_generation_parameters"
    ):
        raise ValueError("CEA-1.8 configured generation settings drifted.")
    if _generation_payload(effective_generation) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.8 effective generation settings drifted.")
    underlying_tasks = tuple(item.edge_filter_task for item in preflight.tasks)
    for repetition in (1, 2):
        cea14.execute_attachment_edge_filter_tasks(
            root=root,
            config=config,
            tasks=underlying_tasks,
            output_directory=root / f"cue/repetition-{repetition}",
            phase="development",
            metadata=metadata,
            generation_parameters=configured_generation,
            prompt_id=CUE_PROMPT_ID,
        )
    baseline_root = Path(_required_str(metadata, "baseline_root"))
    baseline_report = AttachmentResidualOwnershipReport.model_validate_json(
        (baseline_root / "report.json").read_bytes()
    )
    expected_by_task: dict[str, Literal["Y", "N"]] = {
        item.task.id: item.expected_answer for item in baseline_report.cases
    }
    observations, probabilities = _load_observations(
        root=root,
        config=config,
        preflight=preflight,
        expected_by_task=expected_by_task,
        configured_generation=configured_generation,
    )
    cue_report = build_attachment_residual_ownership_report(
        inputs=preflight.inputs,
        prompt=preflight.cue_prompt,
        tasks=preflight.tasks,
        expected_answers=expected_by_task,
        observations=observations,
    )
    _write_json(root / "ablation-report.json", cue_report.model_dump(mode="json"))
    comparison_inputs = (
        _file_reference("ablation_report", root / "ablation-report.json"),
        _file_reference("baseline_report", baseline_root / "report.json"),
        _file_reference("preflight", root / "preflight.json"),
    )
    report = build_residual_cue_ablation_report(
        inputs=comparison_inputs,
        baseline_prompt=preflight.baseline_prompt,
        cue_prompt=preflight.cue_prompt,
        baseline_report=baseline_report,
        cue_report=cue_report,
        probabilities=probabilities,
    )
    _write_json(root / "comparison-report.json", report.model_dump(mode="json"))
    (root / "comparison-review.md").write_text(
        render_residual_cue_ablation_review(report, cue_report),
        encoding="utf-8",
    )
    (root / "second-opinion-handoff.md").write_text(
        render_residual_cue_ablation_handoff(
            report,
            cue_report,
            baseline_prompt_text=BASELINE_PROMPT_PATH.read_text(encoding="utf-8"),
            cue_prompt_text=CUE_PROMPT_PATH.read_text(encoding="utf-8"),
            source_repository_url="https://github.com/SQLCODE917/KoteKomi",
            source_revision=_source_revision(),
        ),
        encoding="utf-8",
    )
    metadata["status"] = "complete"
    metadata["ablation_report_sha256"] = _file_sha(root / "ablation-report.json")
    metadata["comparison_report_sha256"] = _file_sha(root / "comparison-report.json")
    metadata["comparison_review_sha256"] = _file_sha(root / "comparison-review.md")
    metadata["handoff_sha256"] = _file_sha(root / "second-opinion-handoff.md")
    _write_json(root / "run.json", metadata)
    status = _status(
        root,
        AttachmentResidualCueAblationPackageStatus.COMPLETE,
        report=report,
    )
    _write_json(root / "status.json", status.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "handoff": status.handoff_path,
                "outcome": report.outcome.value,
                "report": status.comparison_report_path,
                "review": status.review_path,
                "run_root": str(root),
                "second_opinion_review": status.claude_review_path,
                "status": status.status.value,
            },
            sort_keys=True,
        )
    )
    return 0


def _load_observations(
    *,
    root: Path,
    config: PipelineConfig,
    preflight: AttachmentResidualCueAblationPreflight,
    expected_by_task: dict[str, Literal["Y", "N"]],
    configured_generation: tuple[ExecutionSetting, ...],
) -> tuple[
    tuple[AttachmentResidualOwnershipObservation, ...],
    dict[tuple[str, int], AttachmentAnswerProbability | None],
]:
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    observations: list[AttachmentResidualOwnershipObservation] = []
    probabilities: dict[tuple[str, int], AttachmentAnswerProbability | None] = {}
    effective_generation = attachment_edge_filter_generation_parameters(configured_generation)
    effective_payload = _generation_payload(effective_generation)
    effective_digest = generation_parameters_digest(effective_generation)
    for residual_task in preflight.tasks:
        task = residual_task.edge_filter_task
        for repetition in (1, 2):
            path = root / f"cue/repetition-{repetition}/{task.task_id}.json"
            decision, value = cea14.validate_attachment_edge_filter_execution_record(
                path,
                task,
                archive=archive,
                expected_prompt_sha256=preflight.cue_prompt.sha256,
                expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
                expected_prompt_id=CUE_PROMPT_ID,
            )
            trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
            model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
            if model_run.generation_parameters != effective_payload:
                raise ValueError("CEA-1.8 ModelRun generation settings drifted.")
            exact_input = trace.input.get("exact_model_input")
            raw_output = trace.output.get("raw_output_text")
            if not isinstance(exact_input, str) or not exact_input:
                raise ValueError("CEA-1.8 execution lacks exact model input.")
            if raw_output is not None and not isinstance(raw_output, str):
                raise ValueError("CEA-1.8 raw output text has invalid shape.")
            forbidden = (
                task.edge.id,
                task.candidate.id,
                task.edge.source_grounded_event_id,
                "expected_answer",
            )
            if any(item in exact_input for item in forbidden):
                raise ValueError("CEA-1.8 model input exposes hidden evaluation data.")
            probability: AttachmentAnswerProbability | None = None
            if model_run.execution_receipt is not None:
                receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
                if receipt.generation_parameters_digest != effective_digest:
                    raise ValueError("CEA-1.8 receipt generation settings drifted.")
                probability = _answer_probability(decision.answer, receipt)
            probabilities[(residual_task.id, repetition)] = probability
            expected = expected_by_task[residual_task.id]
            actual = (
                decision.answer.value
                if decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
                and decision.answer is not None
                else None
            )
            observations.append(
                AttachmentResidualOwnershipObservation(
                    repetition=repetition,
                    task_id=residual_task.id,
                    edge_id=task.edge.id,
                    expected_answer=expected,
                    decision=decision,
                    execution_record=_file_reference(
                        f"{residual_task.id}_repetition_{repetition}",
                        path,
                    ),
                    exact_model_input=exact_input,
                    raw_output_text=raw_output,
                    elapsed_milliseconds=_elapsed_milliseconds(model_run),
                    passed=actual == expected,
                )
            )
    return tuple(observations), probabilities


def _answer_probability(
    answer: AttachmentEdgeFilterAnswerValue | None,
    receipt: ModelExecutionReceipt,
) -> AttachmentAnswerProbability | None:
    if answer is None or not receipt.output_token_probabilities:
        return None
    try:
        return attachment_answer_probability(receipt, emitted_answer=answer)
    except ValueError:
        return None


def _status(
    root: Path,
    status: AttachmentResidualCueAblationPackageStatus,
    *,
    report: AttachmentResidualCueAblationReport | None = None,
) -> AttachmentResidualCueAblationStatus:
    complete = status is AttachmentResidualCueAblationPackageStatus.COMPLETE
    return AttachmentResidualCueAblationStatus(
        status=status,
        run_root=str(root),
        preflight_path=str(root / "preflight.json"),
        ablation_report_path=str(root / "ablation-report.json") if complete else None,
        comparison_report_path=str(root / "comparison-report.json") if complete else None,
        review_path=str(root / "comparison-review.md") if complete else None,
        handoff_path=str(root / "second-opinion-handoff.md") if complete else None,
        claude_review_path=str(root / "claude-opus-review.md") if complete else None,
        outcome=report.outcome if report is not None else None,
        model_execution_count=report.model_execution_count if report is not None else 0,
    )


def _configured_generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    settings = (
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", TOP_LOGPROBS),
    )
    if tuple(sorted(settings, key=lambda item: item.key)) != settings:
        raise ValueError("CEA-1.8 generation settings are not canonically ordered.")
    return settings


def _generation_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    expected = cea14.attachment_edge_filter_runtime_contract(config)
    if expected != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.8 configured runtime differs from sealed evidence.")


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _file_reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    return AttachmentEvidenceReference(label=label, path=str(resolved), sha256=_file_sha(resolved))


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    if _file_sha(Path(reference.path)) != reference.sha256:
        raise ValueError(f"CEA-1.8 evidence digest drifted: {reference.label}.")


def _source_revision() -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if type(value) is not int or value < 0:
        raise ValueError("CEA-1.8 ModelRun lacks elapsed milliseconds.")
    return value


def _required_str(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"CEA-1.8 metadata lacks {key}.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
