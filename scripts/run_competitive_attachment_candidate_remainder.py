#!/usr/bin/env python3
"""Run the CEA-1.9 explicit Candidate Remainder experiment."""

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
    ATTACHMENT_EDGE_FILTER_RENDERER_ID,
    ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    AttachmentAnswerProbability,
    AttachmentCandidateRemainderArm,
    AttachmentCandidateRemainderObservation,
    AttachmentCandidateRemainderPackageStatus,
    AttachmentCandidateRemainderPreflight,
    AttachmentCandidateRemainderReport,
    AttachmentCandidateRemainderStatus,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentResidualCueAblationPreflight,
    AttachmentResidualCueAblationReport,
    ExecutionSetting,
    ExtractionStageTrace,
    ModelExecutionReceipt,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_candidate_remainder import (
    build_candidate_remainder_preflight,
    build_candidate_remainder_report,
    render_candidate_remainder_handoff,
    render_candidate_remainder_review,
)
from kotekomi_pipelines.competitive_attachment_edge_filter_calibration import (
    attachment_answer_probability,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-candidate-remainder.md"
BASELINE_PROMPT_PATH = REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_v2.md"
REMAINDER_PROMPT_PATH = REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_v3.md"
BASELINE_PROMPT_ID = "competitive_attachment_residual_ownership_v2"
REMAINDER_PROMPT_ID = "competitive_attachment_residual_ownership_v3"
TOP_LOGPROBS = 10


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--cue-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)

    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.9 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    cue_root = args.cue_root.resolve()
    config = _config(args.config)
    cue_metadata, cue_preflight, cue_report = _load_cue_package(cue_root)
    _validate_runtime(config, cue_metadata)
    baseline_prompt = _file_reference("baseline_prompt", BASELINE_PROMPT_PATH)
    remainder_prompt = _file_reference("remainder_prompt", REMAINDER_PROMPT_PATH)
    inputs = tuple(
        sorted(
            (
                _file_reference("cue_comparison_report", cue_root / "comparison-report.json"),
                _file_reference("cue_preflight", cue_root / "preflight.json"),
                _file_reference("cue_run", cue_root / "run.json"),
                _file_reference("cue_second_opinion", cue_root / "claude-opus-review.md"),
                _file_reference("cue_status", cue_root / "status.json"),
                _file_reference("tdd", TDD_PATH),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_candidate_remainder_preflight(
        inputs=inputs,
        baseline_prompt=baseline_prompt,
        remainder_prompt=remainder_prompt,
        baseline_prompt_text=BASELINE_PROMPT_PATH.read_text(encoding="utf-8"),
        remainder_prompt_text=REMAINDER_PROMPT_PATH.read_text(encoding="utf-8"),
        cue_preflight=cue_preflight,
        cue_report=cue_report,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(configured_generation)
    metadata = dict(cue_metadata)
    for key in tuple(metadata):
        if key.endswith("_sha256") and key not in {
            "runtime_contract_sha256",
            "development_tasks_sha256",
            "validation_tasks_sha256",
        }:
            metadata.pop(key)
    metadata.update(
        {
            "schema_version": "attachment_candidate_remainder_run_v1",
            "status": "prepared",
            "config_path": str(args.config.resolve()),
            "cue_root": str(cue_root),
            "baseline_prompt_path": str(BASELINE_PROMPT_PATH),
            "baseline_prompt_sha256": baseline_prompt.sha256,
            "baseline_prompt_id": BASELINE_PROMPT_ID,
            "remainder_prompt_path": str(REMAINDER_PROMPT_PATH),
            "remainder_prompt_sha256": remainder_prompt.sha256,
            "remainder_prompt_id": REMAINDER_PROMPT_ID,
            "tdd_path": str(TDD_PATH),
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
    preflight_path = root / "preflight.json"
    _write_json(preflight_path, preflight.model_dump(mode="json"))
    metadata.update(_preflight_evidence_metadata(preflight, preflight_path))
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "tasks-development.json",
        [item.model_dump(mode="json") for item in preflight.tasks],
    )
    status = _status(root, AttachmentCandidateRemainderPackageStatus.PREPARED)
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
        raise ValueError("CEA-1.9 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentCandidateRemainderPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.9 preflight fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.9 preflight file digest drifted.")
    for reference in (*preflight.inputs, preflight.baseline_prompt, preflight.remainder_prompt):
        _validate_reference(reference)
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(configured_generation)
    if _generation_payload(configured_generation) != metadata.get(
        "configured_generation_parameters"
    ):
        raise ValueError("CEA-1.9 configured generation settings drifted.")
    if _generation_payload(effective_generation) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.9 effective generation settings drifted.")
    tasks = tuple(item.edge_filter_task for item in preflight.tasks)
    baseline_metadata = dict(metadata)
    baseline_metadata.update(
        {
            "prompt_path": str(BASELINE_PROMPT_PATH),
            "prompt_sha256": preflight.baseline_prompt.sha256,
        }
    )
    cea14.execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=tasks,
        output_directory=root / "baseline",
        phase="development",
        metadata=baseline_metadata,
        generation_parameters=configured_generation,
        prompt_id=BASELINE_PROMPT_ID,
        task_renderer_id=ATTACHMENT_EDGE_FILTER_RENDERER_ID,
    )
    remainder_metadata = dict(metadata)
    remainder_metadata.update(
        {
            "prompt_path": str(REMAINDER_PROMPT_PATH),
            "prompt_sha256": preflight.remainder_prompt.sha256,
        }
    )
    cea14.execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=tasks,
        output_directory=root / "remainder",
        phase="development",
        metadata=remainder_metadata,
        generation_parameters=configured_generation,
        prompt_id=REMAINDER_PROMPT_ID,
        task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    )
    cue_root = Path(_required_str(metadata, "cue_root"))
    _, _, cue_report = _load_cue_package(cue_root)
    expected_by_task: dict[str, Literal["Y", "N"]] = {
        item.task_id: item.expected_answer for item in cue_report.cases
    }
    baseline = _load_observations(
        root=root,
        directory=root / "baseline",
        config=config,
        preflight=preflight,
        arm=AttachmentCandidateRemainderArm.BASELINE,
        prompt_sha256=preflight.baseline_prompt.sha256,
        prompt_id=BASELINE_PROMPT_ID,
        task_renderer_id=ATTACHMENT_EDGE_FILTER_RENDERER_ID,
        expected_by_task=expected_by_task,
        configured_generation=configured_generation,
    )
    remainder = _load_observations(
        root=root,
        directory=root / "remainder",
        config=config,
        preflight=preflight,
        arm=AttachmentCandidateRemainderArm.REMAINDER,
        prompt_sha256=preflight.remainder_prompt.sha256,
        prompt_id=REMAINDER_PROMPT_ID,
        task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
        expected_by_task=expected_by_task,
        configured_generation=configured_generation,
    )
    _validate_model_identity(baseline, remainder)
    report_inputs = (
        _file_reference("baseline_executions", root / "baseline"),
        _file_reference("preflight", root / "preflight.json"),
        _file_reference("remainder_executions", root / "remainder"),
    )
    report = build_candidate_remainder_report(
        inputs=report_inputs,
        preflight=preflight,
        cue_report=cue_report,
        baseline_observations=baseline,
        remainder_observations=remainder,
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "comparison-review.md").write_text(
        render_candidate_remainder_review(report),
        encoding="utf-8",
    )
    package_files = tuple(
        sorted(
            (
                *preflight.inputs,
                preflight.baseline_prompt,
                _file_reference("comparison_report", root / "report.json"),
                _file_reference("comparison_review", root / "comparison-review.md"),
                _file_reference("preflight", root / "preflight.json"),
                preflight.remainder_prompt,
                *(
                    _file_reference(f"baseline_{path.stem}", path)
                    for path in sorted((root / "baseline").glob("aet_*.json"))
                ),
                *(
                    _file_reference(f"remainder_{path.stem}", path)
                    for path in sorted((root / "remainder").glob("aet_*.json"))
                ),
            ),
            key=lambda item: item.label,
        )
    )
    (root / "second-opinion-handoff.md").write_text(
        render_candidate_remainder_handoff(
            report,
            baseline_prompt_text=BASELINE_PROMPT_PATH.read_text(encoding="utf-8"),
            remainder_prompt_text=REMAINDER_PROMPT_PATH.read_text(encoding="utf-8"),
            package_files=package_files,
            source_repository_url="https://github.com/SQLCODE917/KoteKomi",
            source_revision=_source_revision(),
        ),
        encoding="utf-8",
    )
    metadata.update(
        {
            "status": "complete",
            "report_file_sha256": _file_sha(root / "report.json"),
            "report_fingerprint": report.result_fingerprint,
            "review_file_sha256": _file_sha(root / "comparison-review.md"),
            "handoff_file_sha256": _file_sha(root / "second-opinion-handoff.md"),
        }
    )
    _write_json(root / "run.json", metadata)
    status = _status(
        root,
        AttachmentCandidateRemainderPackageStatus.COMPLETE,
        report=report,
    )
    _write_json(root / "status.json", status.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "handoff": status.handoff_path,
                "outcome": report.outcome.value,
                "report": status.report_path,
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
    directory: Path,
    config: PipelineConfig,
    preflight: AttachmentCandidateRemainderPreflight,
    arm: AttachmentCandidateRemainderArm,
    prompt_sha256: str,
    prompt_id: str,
    task_renderer_id: str,
    expected_by_task: dict[str, Literal["Y", "N"]],
    configured_generation: tuple[ExecutionSetting, ...],
) -> tuple[AttachmentCandidateRemainderObservation, ...]:
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    effective_generation = attachment_edge_filter_generation_parameters(configured_generation)
    effective_payload = _generation_payload(effective_generation)
    effective_digest = generation_parameters_digest(effective_generation)
    result: list[AttachmentCandidateRemainderObservation] = []
    for residual_task in preflight.tasks:
        task = residual_task.edge_filter_task
        path = directory / f"{task.task_id}.json"
        decision, value = cea14.validate_attachment_edge_filter_execution_record(
            path,
            task,
            archive=archive,
            expected_prompt_sha256=prompt_sha256,
            expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
            expected_prompt_id=prompt_id,
            expected_task_renderer_id=task_renderer_id,
        )
        trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
        model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
        if model_run.generation_parameters != effective_payload:
            raise ValueError("CEA-1.9 execution generation settings drifted.")
        exact_input = trace.input.get("exact_model_input")
        raw_output = trace.output.get("raw_output_text")
        if not isinstance(exact_input, str) or not exact_input:
            raise ValueError("CEA-1.9 execution lacks exact model input.")
        if raw_output is not None and not isinstance(raw_output, str):
            raise ValueError("CEA-1.9 raw output text has invalid shape.")
        forbidden = (
            task.edge.id,
            task.candidate.id,
            task.edge.source_grounded_event_id,
            "expected_answer",
        )
        if any(item in exact_input for item in forbidden):
            raise ValueError("CEA-1.9 model input exposes hidden evaluation data.")
        probability: AttachmentAnswerProbability | None = None
        model_identity_digest: str | None = None
        if model_run.execution_receipt is not None:
            receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
            if receipt.generation_parameters_digest != effective_digest:
                raise ValueError("CEA-1.9 receipt generation settings drifted.")
            probability = _answer_probability(decision.answer, receipt)
            if probability is not None:
                model_identity_digest = receipt.model_identity_digest
        expected = expected_by_task[residual_task.id]
        actual = (
            decision.answer.value
            if decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and decision.answer is not None
            else None
        )
        result.append(
            AttachmentCandidateRemainderObservation(
                arm=arm,
                task_id=residual_task.id,
                edge_id=task.edge.id,
                expected_answer=expected,
                decision=decision,
                probability=probability,
                model_identity_digest=model_identity_digest,
                execution_record=_file_reference(f"{arm.value}_{residual_task.id}", path),
                exact_model_input=exact_input,
                raw_output_text=raw_output,
                elapsed_milliseconds=_elapsed_milliseconds(model_run),
                passed=actual == expected,
            )
        )
    return tuple(result)


def _load_cue_package(
    root: Path,
) -> tuple[
    dict[str, Any], AttachmentResidualCueAblationPreflight, AttachmentResidualCueAblationReport
]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.9 requires a complete CEA-1.8 package.")
    checks = {
        "preflight_file_sha256": root / "preflight.json",
        "ablation_report_sha256": root / "ablation-report.json",
        "comparison_report_sha256": root / "comparison-report.json",
        "comparison_review_sha256": root / "comparison-review.md",
        "handoff_sha256": root / "second-opinion-handoff.md",
    }
    for field, path in checks.items():
        expected = metadata.get(field)
        if not path.is_file() or expected != _file_sha(path):
            raise ValueError(f"CEA-1.9 CEA-1.8 evidence digest changed: {field}.")
    review_path = root / "claude-opus-review.md"
    if not review_path.is_file() or not review_path.read_bytes():
        raise ValueError("CEA-1.9 requires the completed CEA-1.8 second opinion.")
    preflight = AttachmentResidualCueAblationPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.9 CEA-1.8 preflight fingerprint changed.")
    report = AttachmentResidualCueAblationReport.model_validate_json(
        (root / "comparison-report.json").read_bytes()
    )
    if report.outcome.value != "supported":
        raise ValueError("CEA-1.9 requires the supported narrow CEA-1.8 outcome.")
    return metadata, preflight, report


def _validate_model_identity(
    baseline: tuple[AttachmentCandidateRemainderObservation, ...],
    remainder: tuple[AttachmentCandidateRemainderObservation, ...],
) -> None:
    identities = {
        item.model_identity_digest
        for item in (*baseline, *remainder)
        if item.model_identity_digest is not None
    }
    if len(identities) > 1:
        raise ValueError("CEA-1.9 arms used different model identities.")


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
    status: AttachmentCandidateRemainderPackageStatus,
    *,
    report: AttachmentCandidateRemainderReport | None = None,
) -> AttachmentCandidateRemainderStatus:
    complete = status is AttachmentCandidateRemainderPackageStatus.COMPLETE
    return AttachmentCandidateRemainderStatus(
        status=status,
        run_root=str(root),
        preflight_path=str(root / "preflight.json"),
        report_path=str(root / "report.json") if complete else None,
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
        raise ValueError("CEA-1.9 generation settings are not canonically ordered.")
    return settings


def _generation_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _preflight_evidence_metadata(
    preflight: AttachmentCandidateRemainderPreflight,
    path: Path,
) -> dict[str, str]:
    """Name the typed fingerprint and serialized-file digest independently."""
    return {
        "preflight_fingerprint": preflight.result_fingerprint,
        "preflight_file_sha256": _file_sha(path),
    }


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    expected = cea14.attachment_edge_filter_runtime_contract(config)
    if expected != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.9 configured runtime differs from sealed evidence.")


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _file_reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if resolved.is_dir():
        payload = b"".join(
            child.name.encode() + b"\0" + child.read_bytes()
            for child in sorted(resolved.glob("aet_*.json"))
        )
        digest = hashlib.sha256(payload).hexdigest()
    else:
        digest = _file_sha(resolved)
    return AttachmentEvidenceReference(label=label, path=str(resolved), sha256=digest)


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    observed = _file_reference(reference.label, path)
    if observed.sha256 != reference.sha256:
        raise ValueError(f"CEA-1.9 evidence digest drifted: {reference.label}.")


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
        raise ValueError("CEA-1.9 ModelRun lacks elapsed milliseconds.")
    return value


def _required_str(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"CEA-1.9 metadata lacks {key}.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
