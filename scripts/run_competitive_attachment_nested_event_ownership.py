#!/usr/bin/env python3
"""Run the CEA-1.22 Nested Event Ownership diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from base64 import b64encode
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
    AttachmentBlindReviewReport,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentNestedEventObservation,
    AttachmentNestedEventPreflight,
    AttachmentStructuralSafetyReport,
    CompetitiveAttachmentMatrix,
    ExecutionSetting,
    ExtractionStageTrace,
    attachment_nested_event_ownership_model_task_input,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_nested_event_ownership import (
    attachment_nested_event_case_by_task_id,
    build_attachment_nested_event_preflight,
    build_attachment_nested_event_report,
    render_attachment_nested_event_handoff,
    render_attachment_nested_event_preflight,
    render_attachment_nested_event_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

ROOT = Path(__file__).resolve().parents[1]
TDD = ROOT / "docs/2026-09-21-competitive-attachment-nested-event-ownership.md"
PROMPT = ROOT / "prompts/competitive_attachment_nested_event_ownership_v1.md"
OUTPUT_TOKEN_LIMIT = 2


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--blind-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.22 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    config = _config(args.config)
    blind_root = args.blind_root.resolve()
    blind = _validated_blind_package(blind_root)
    structural = _validated_structural_report(blind)
    structural_inputs = {item.label: item for item in structural.inputs}
    development_matrices = _load_matrices(
        _required_reference(structural_inputs, "development_matrices")
    )
    validation_matrices = _load_matrices(
        _required_reference(structural_inputs, "validation_matrices")
    )
    development_run = _required_reference(structural_inputs, "development_run")
    validation_run = _required_reference(structural_inputs, "validation_run")
    development_root = Path(development_run.path).resolve().parent
    validation_root = Path(validation_run.path).resolve().parent
    cea14.validate_competitive_attachment_phase_evidence(
        development_root, expected_phase="development"
    )
    cea14.validate_competitive_attachment_phase_evidence(
        validation_root, expected_phase="validation"
    )
    prompt = _reference("prompt", PROMPT)
    inputs = tuple(
        sorted(
            (
                _reference("blind_claude_review", blind_root / "claude-opus-review.md"),
                _reference("blind_report", blind_root / "report.json"),
                _reference("blind_review", blind_root / "comparison-review.md"),
                _reference("blind_status", blind_root / "status.json"),
                _reference("development_matrices", development_matrices[0]),
                _reference("development_run", Path(development_run.path)),
                _reference("structural_report", Path(_blind_input(blind, "cea119_report").path)),
                _reference("tdd", TDD),
                _reference("validation_matrices", validation_matrices[0]),
                _reference("validation_run", Path(validation_run.path)),
            ),
            key=lambda item: item.label,
        )
    )
    matrices = (*development_matrices[1], *validation_matrices[1])
    preflight = build_attachment_nested_event_preflight(
        inputs=inputs,
        prompt=prompt,
        blind_report=blind,
        matrices=matrices,
    )
    preflight_path = root / "preflight.json"
    preflight_review_path = root / "preflight-review.md"
    _write_json(preflight_path, preflight.model_dump(mode="json"))
    preflight_review_path.write_text(
        render_attachment_nested_event_preflight(preflight), encoding="utf-8"
    )
    generation = _generation(config)
    metadata = {
        "schema_version": "attachment_nested_event_run_v1",
        "status": "prepared",
        "config_path": str(args.config.resolve()),
        "blind_root": str(blind_root),
        "development_run_root": str(development_root),
        "validation_run_root": str(validation_root),
        "runtime_contract": cea14.attachment_edge_filter_runtime_contract(config),
        "prompt_path": str(PROMPT),
        "prompt_sha256": prompt.sha256,
        "prompt_id": ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
        "task_renderer_id": ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
        "generation_parameters": _generation_payload(generation),
        "effective_max_output_tokens": OUTPUT_TOKEN_LIMIT,
        "preflight_fingerprint": preflight.result_fingerprint,
        "preflight_sha256": _sha_file(preflight_path),
        "preflight_review_sha256": _sha_file(preflight_review_path),
        "production_integration": "not_activated",
    }
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        {
            "schema_version": "attachment_nested_event_status_v1",
            "status": "prepared",
            "run_root": str(root),
            "preflight": str(preflight_path),
            "preflight_review": str(preflight_review_path),
        },
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(root),
                "preflight": str(preflight_path),
                "preflight_review": str(preflight_review_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    if metadata.get("status") not in {"prepared", "complete"}:
        raise ValueError("CEA-1.22 run metadata is not prepared.")
    config = _config(args.config)
    if cea14.attachment_edge_filter_runtime_contract(config) != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.22 runtime contract drifted.")
    preflight_path = root / "preflight.json"
    preflight_review_path = root / "preflight-review.md"
    preflight = AttachmentNestedEventPreflight.model_validate_json(preflight_path.read_bytes())
    if (
        preflight.result_fingerprint != metadata.get("preflight_fingerprint")
        or _sha_file(preflight_path) != metadata.get("preflight_sha256")
        or _sha_file(preflight_review_path) != metadata.get("preflight_review_sha256")
    ):
        raise ValueError("CEA-1.22 preflight evidence drifted.")
    for reference in (*preflight.inputs, preflight.prompt):
        _validate_reference(reference)
    generation = _generation(config)
    if _generation_payload(generation) != metadata.get("generation_parameters"):
        raise ValueError("CEA-1.22 generation parameters drifted.")
    cases_by_task = attachment_nested_event_case_by_task_id(preflight.cases)
    for phase in ("development", "validation"):
        phase_tasks = tuple(item.task for item in preflight.cases if item.phase == phase)
        for repetition in (1, 2):
            cea14.execute_attachment_edge_filter_tasks(
                root=root,
                config=config,
                tasks=phase_tasks,
                output_directory=root / f"{phase}-r{repetition}",
                phase=phase,
                metadata=metadata,
                generation_parameters=generation,
                prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
                task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
                effective_max_output_tokens=OUTPUT_TOKEN_LIMIT,
            )
    observations = tuple(
        _load_observation(
            root=root,
            path=root / f"{case.phase}-r{repetition}" / f"{case.task.task_id}.json",
            config=config,
            case_id=case.id,
            task=case.task,
            repetition=repetition,
            prompt_sha256=preflight.prompt.sha256,
        )
        for case in preflight.cases
        for repetition in (1, 2)
    )
    if {item.case_id for item in observations} != {item.id for item in preflight.cases} or {
        item.decision.task_id for item in observations
    } != set(cases_by_task):
        raise ValueError("CEA-1.22 observation inventory drifted.")
    identities = {
        item.model_identity_digest
        for item in observations
        if item.model_identity_digest is not None
    }
    if len(identities) > 1:
        raise ValueError("CEA-1.22 repetitions used different model identities.")
    execution_references = tuple(
        sorted(
            (item.execution_record for item in observations),
            key=lambda item: item.label,
        )
    )
    report = build_attachment_nested_event_report(
        inputs=(
            _reference("preflight", preflight_path),
            _reference("preflight_review", preflight_review_path),
            *execution_references,
        ),
        preflight=preflight,
        observations=observations,
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    prompt_text = PROMPT.read_text(encoding="utf-8")
    review_path.write_text(
        render_attachment_nested_event_review(report, prompt_text=prompt_text),
        encoding="utf-8",
    )
    package = tuple(
        sorted(
            (
                *preflight.inputs,
                preflight.prompt,
                *report.inputs,
                _reference(
                    "application_contract",
                    ROOT / "packages/application/src/kotekomi_application/"
                    "competitive_attachment_nested_event_ownership.py",
                ),
                _reference(
                    "pipeline_policy",
                    ROOT / "packages/pipelines/src/kotekomi_pipelines/"
                    "competitive_attachment_nested_event_ownership.py",
                ),
                _reference("report", report_path),
                _reference("review", review_path),
                _reference("runner", Path(__file__)),
            ),
            key=lambda item: item.label,
        )
    )
    handoff_path.write_text(
        render_attachment_nested_event_handoff(
            report,
            prompt_text=prompt_text,
            package_files=package,
            source_repository_url="https://github.com/SQLCODE917/KoteKomi",
            source_revision=_git_revision(),
        ),
        encoding="utf-8",
    )
    metadata.update(
        {
            "status": "complete",
            "report_fingerprint": report.result_fingerprint,
            "report_sha256": _sha_file(report_path),
            "review_sha256": _sha_file(review_path),
            "handoff_sha256": _sha_file(handoff_path),
        }
    )
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        {
            "schema_version": "attachment_nested_event_status_v1",
            "status": "complete",
            "outcome": report.outcome.value,
            "run_root": str(root),
            "report": str(report_path),
            "review": str(review_path),
            "handoff": str(handoff_path),
            "claude_review": str(root / "claude-opus-review.md"),
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "outcome": report.outcome.value,
                "run_root": str(root),
                "report": str(report_path),
                "review": str(review_path),
                "handoff": str(handoff_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _load_observation(
    *,
    root: Path,
    path: Path,
    config: PipelineConfig,
    case_id: str,
    task: AttachmentEdgeFilterTask,
    repetition: Literal[1, 2],
    prompt_sha256: str,
) -> AttachmentNestedEventObservation:
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    decision, value = cea14.validate_attachment_edge_filter_execution_record(
        path,
        task,
        archive=archive,
        expected_prompt_sha256=prompt_sha256,
        expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
        expected_prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
        expected_task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical(value["trace"]))
    model_run = ModelRun.model_validate_json(_canonical(value["model_run"]))
    exact_input = trace.input.get("exact_model_input")
    visible_task = trace.input.get("model_visible_task")
    if not isinstance(exact_input, str) or not isinstance(visible_task, str):
        raise ValueError("CEA-1.22 execution lacks exact model input evidence.")
    expected_task = attachment_nested_event_ownership_model_task_input(task).decode()
    if visible_task != expected_task:
        raise ValueError("CEA-1.22 execution task rendering drifted.")
    raw_output = (
        archive.read_model_run_output(model_run.id) if model_run.output_digest is not None else None
    )
    admission = model_run.input_admission
    identity = (
        admission.model_identity_digest
        if admission is not None and admission.status.value == "ready"
        else None
    )
    return AttachmentNestedEventObservation(
        case_id=case_id,
        repetition=repetition,
        decision=decision,
        execution_record=_reference(f"execution_{repetition}_{case_id}", path),
        exact_model_input=exact_input,
        raw_output_base64=(b64encode(raw_output).decode() if raw_output is not None else None),
        model_identity_digest=identity,
        elapsed_milliseconds=_elapsed_milliseconds(model_run),
        runtime_invoked=model_run.runtime_invoked,
    )


def _validated_blind_package(root: Path) -> AttachmentBlindReviewReport:
    status = _read_json(root / "status.json")
    if (
        status.get("schema_version") != "attachment_blind_review_status_v1"
        or status.get("status") != "complete"
        or status.get("outcome") != "mixed"
    ):
        raise ValueError("CEA-1.22 requires the completed mixed CEA-1.21 package.")
    paths = {
        "report_sha256": root / "report.json",
        "review_sha256": root / "comparison-review.md",
        "handoff_sha256": root / "second-opinion-handoff.md",
    }
    for key, path in paths.items():
        if status.get(key) != _sha_file(path):
            raise ValueError(f"CEA-1.22 CEA-1.21 evidence drifted: {key}.")
    if not (root / "claude-opus-review.md").is_file():
        raise ValueError("CEA-1.22 requires the completed CEA-1.21 second opinion.")
    report = AttachmentBlindReviewReport.model_validate_json((root / "report.json").read_bytes())
    if status.get("result_fingerprint") != report.result_fingerprint:
        raise ValueError("CEA-1.22 CEA-1.21 result fingerprint drifted.")
    for reference in report.inputs:
        _validate_reference(reference)
    return report


def _validated_structural_report(
    blind: AttachmentBlindReviewReport,
) -> AttachmentStructuralSafetyReport:
    reference = _blind_input(blind, "cea119_report")
    _validate_reference(reference)
    report = AttachmentStructuralSafetyReport.model_validate_json(Path(reference.path).read_bytes())
    for item in report.inputs:
        _validate_reference(item)
    return report


def _blind_input(report: AttachmentBlindReviewReport, label: str) -> AttachmentEvidenceReference:
    values = tuple(item for item in report.inputs if item.label == label)
    if len(values) != 1:
        raise ValueError(f"CEA-1.22 requires one CEA-1.21 input: {label}.")
    return values[0]


def _required_reference(
    values: dict[str, AttachmentEvidenceReference], label: str
) -> AttachmentEvidenceReference:
    reference = values.get(label)
    if reference is None:
        raise ValueError(f"CEA-1.22 requires structural input: {label}.")
    _validate_reference(reference)
    return reference


def _load_matrices(
    reference: AttachmentEvidenceReference,
) -> tuple[Path, tuple[CompetitiveAttachmentMatrix, ...]]:
    path = Path(reference.path).resolve()
    value = json.loads(path.read_text())
    if not isinstance(value, list):
        raise ValueError("CEA-1.22 matrices evidence must be a JSON array.")
    matrices = tuple(
        CompetitiveAttachmentMatrix.model_validate_json(_canonical(item))
        for item in cast(list[object], value)
    )
    if not matrices:
        raise ValueError("CEA-1.22 matrices evidence cannot be empty.")
    return path, matrices


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting(key="frequency_penalty", value=0.0),
        ExecutionSetting(key="max_output_tokens", value=config.model_execution.max_output_tokens),
        ExecutionSetting(key="seed", value=17),
        ExecutionSetting(key="temperature", value=0),
        ExecutionSetting(key="top_logprobs", value=10),
    )


def _generation_payload(
    values: tuple[ExecutionSetting, ...],
) -> dict[str, object]:
    return {item.key: item.value for item in values}


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if type(value) is not int or value < 0:
        raise ValueError("CEA-1.22 execution lacks elapsed milliseconds.")
    return value


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.22 evidence file is missing: {resolved}.")
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_sha_file(resolved),
    )


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    resolved = path if path.is_absolute() else ROOT / path
    if not resolved.is_file() or _sha_file(resolved) != reference.sha256:
        raise ValueError(f"CEA-1.22 referenced evidence drifted: {reference.label}.")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"CEA-1.22 expected a JSON object: {path}.")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
