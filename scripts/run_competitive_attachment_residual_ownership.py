#!/usr/bin/env python3
"""Run the CEA-1.7 Residual Attachment Ownership diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
import run_competitive_attachment_measurement_authority as cea16
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentMeasurementAuditReport,
    AttachmentResidualOwnershipObservation,
    AttachmentResidualOwnershipPackageStatus,
    AttachmentResidualOwnershipPreflight,
    AttachmentResidualOwnershipReport,
    AttachmentResidualOwnershipStatus,
    ExtractionStageTrace,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_residual_ownership import (
    build_attachment_residual_ownership_preflight,
    build_attachment_residual_ownership_report,
    render_attachment_residual_ownership_handoff,
    render_attachment_residual_ownership_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-residual-ownership.md"
PROMPT_PATH = REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_v1.md"
PROMPT_ID = "competitive_attachment_residual_ownership_v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--calibration-root", type=Path, required=True)
    prepare.add_argument("--measurement-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)

    run = commands.add_parser("run-development")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    return {"prepare": _prepare, "run-development": _run_development}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.7 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    config = _config(args.config)
    calibration_root = args.calibration_root.resolve()
    measurement_root = args.measurement_root.resolve()
    metadata = cea16.validated_attachment_calibration_metadata(calibration_root)
    _validate_runtime(config, metadata)
    report = cea16.load_attachment_measurement_report(measurement_root)
    if report.outcome.value != "unsafe":
        raise ValueError("CEA-1.7 requires the unsafe CEA-1.6 R1-strict result.")
    development_tasks = _load_tasks(calibration_root / "tasks-development.json")
    validation_tasks = _load_tasks(calibration_root / "tasks-validation.json")
    inputs = (
        _file_reference("calibration_run", calibration_root / "run.json"),
        _file_reference("development_tasks", calibration_root / "tasks-development.json"),
        _file_reference("measurement_report", measurement_root / "audit-report.json"),
        _file_reference("measurement_status", measurement_root / "status.json"),
        _file_reference("tdd", TDD_PATH),
        _file_reference("validation_tasks", calibration_root / "tasks-validation.json"),
    )
    prompt = _file_reference("residual_ownership_prompt", PROMPT_PATH)
    preflight = build_attachment_residual_ownership_preflight(
        inputs=inputs,
        prompt=prompt,
        development_tasks=development_tasks,
        validation_tasks=validation_tasks,
    )
    _validate_preflight_against_measurement(preflight, report)
    run_metadata = dict(metadata)
    run_metadata.update(
        {
            "schema_version": "attachment_residual_ownership_run_v1",
            "status": "prepared",
            "config_path": str(args.config.resolve()),
            "calibration_root": str(calibration_root),
            "measurement_root": str(measurement_root),
            "prompt_path": str(PROMPT_PATH),
            "prompt_sha256": prompt.sha256,
            "prompt_id": PROMPT_ID,
            "preflight_sha256": preflight.result_fingerprint,
            "production_integration": "not_activated",
        }
    )
    _write_json(root / "run.json", run_metadata)
    _write_json(root / "preflight.json", preflight.model_dump(mode="json"))
    _write_json(
        root / "tasks-development.json",
        [item.model_dump(mode="json") for item in preflight.development_tasks],
    )
    _write_json(
        root / "tasks-validation.json",
        [item.model_dump(mode="json") for item in preflight.validation_tasks],
    )
    status = _status(root, AttachmentResidualOwnershipPackageStatus.PREPARED)
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


def _run_development(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    if metadata.get("status") not in {"prepared", "complete"}:
        raise ValueError("CEA-1.7 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentResidualOwnershipPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_sha256"):
        raise ValueError("CEA-1.7 preflight digest drifted.")
    for reference in preflight.inputs:
        _validate_reference(reference)
    _validate_reference(preflight.prompt)
    underlying_tasks = tuple(item.edge_filter_task for item in preflight.development_tasks)
    for repetition in (1, 2):
        cea14.execute_attachment_edge_filter_tasks(
            root=root,
            config=config,
            tasks=underlying_tasks,
            output_directory=root / f"development/repetition-{repetition}",
            phase="development",
            metadata=metadata,
            prompt_id=PROMPT_ID,
        )
    measurement = cea16.load_attachment_measurement_report(
        Path(cast(str, metadata["measurement_root"]))
    )
    expected_by_edge: dict[str, Literal["Y", "N"]] = {
        item.edge.id: item.expected_answer
        for item in measurement.development.decisions
        if item.edge.id in {task.edge_filter_task.edge.id for task in preflight.development_tasks}
    }
    observations = _load_observations(
        root=root,
        config=config,
        preflight=preflight,
        expected_by_edge=expected_by_edge,
    )
    expected_by_task: dict[str, Literal["Y", "N"]] = {
        task.id: expected_by_edge[task.edge_filter_task.edge.id]
        for task in preflight.development_tasks
    }
    report = build_attachment_residual_ownership_report(
        inputs=preflight.inputs,
        prompt=preflight.prompt,
        tasks=preflight.development_tasks,
        expected_answers=expected_by_task,
        observations=observations,
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "diagnostic-review.md").write_text(
        render_attachment_residual_ownership_review(report), encoding="utf-8"
    )
    (root / "second-opinion-handoff.md").write_text(
        render_attachment_residual_ownership_handoff(
            report,
            prompt_text=PROMPT_PATH.read_text(encoding="utf-8"),
            source_repository_url="https://github.com/SQLCODE917/KoteKomi",
            source_revision=_source_revision(),
        ),
        encoding="utf-8",
    )
    metadata["status"] = "complete"
    metadata["report_sha256"] = _file_sha(root / "report.json")
    metadata["diagnostic_review_sha256"] = _file_sha(root / "diagnostic-review.md")
    metadata["handoff_sha256"] = _file_sha(root / "second-opinion-handoff.md")
    _write_json(root / "run.json", metadata)
    status = _status(
        root,
        AttachmentResidualOwnershipPackageStatus.COMPLETE,
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
    config: PipelineConfig,
    preflight: AttachmentResidualOwnershipPreflight,
    expected_by_edge: dict[str, Literal["Y", "N"]],
) -> tuple[AttachmentResidualOwnershipObservation, ...]:
    if set(expected_by_edge) != {
        item.edge_filter_task.edge.id for item in preflight.development_tasks
    }:
        raise ValueError("CEA-1.7 development Gold inventory drifted.")
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    result: list[AttachmentResidualOwnershipObservation] = []
    for residual_task in preflight.development_tasks:
        task = residual_task.edge_filter_task
        for repetition in (1, 2):
            path = root / f"development/repetition-{repetition}/{task.task_id}.json"
            decision, value = cea14.validate_attachment_edge_filter_execution_record(
                path,
                task,
                archive=archive,
                expected_prompt_sha256=preflight.prompt.sha256,
                expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
                expected_prompt_id=PROMPT_ID,
            )
            trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
            model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
            exact_input = trace.input.get("exact_model_input")
            raw_output = trace.output.get("raw_output_text")
            if not isinstance(exact_input, str) or not exact_input:
                raise ValueError("CEA-1.7 execution lacks exact model input.")
            if raw_output is not None and not isinstance(raw_output, str):
                raise ValueError("CEA-1.7 raw output text has invalid shape.")
            forbidden = (
                task.edge.id,
                task.candidate.id,
                task.edge.source_grounded_event_id,
                "expected_answer",
            )
            if any(item in exact_input for item in forbidden):
                raise ValueError("CEA-1.7 model input exposes hidden evaluation data.")
            expected = expected_by_edge[task.edge.id]
            actual = decision.answer.value if decision.answer is not None else None
            result.append(
                AttachmentResidualOwnershipObservation(
                    repetition=repetition,
                    task_id=residual_task.id,
                    edge_id=task.edge.id,
                    expected_answer=expected,
                    decision=decision,
                    execution_record=_file_reference(
                        f"{residual_task.id}_repetition_{repetition}", path
                    ),
                    exact_model_input=exact_input,
                    raw_output_text=raw_output,
                    elapsed_milliseconds=_elapsed_milliseconds(model_run),
                    passed=actual == expected,
                )
            )
    return tuple(result)


def _validate_preflight_against_measurement(
    preflight: AttachmentResidualOwnershipPreflight,
    report: AttachmentMeasurementAuditReport,
) -> None:
    report_edges = {
        item.edge.id
        for phase in (report.development, report.validation)
        for item in phase.decisions
        if item.rule_answer.value == "reject"
    }
    preflight_edges = {
        *preflight.development_mixed_edge_ids,
        *(item.edge_filter_task.edge.id for item in preflight.development_tasks),
        *preflight.validation_mixed_edge_ids,
        *(item.edge_filter_task.edge.id for item in preflight.validation_tasks),
    }
    if preflight_edges != report_edges:
        raise ValueError("CEA-1.7 Containment Edge inventory differs from CEA-1.6.")


def _status(
    root: Path,
    status: AttachmentResidualOwnershipPackageStatus,
    *,
    report: AttachmentResidualOwnershipReport | None = None,
) -> AttachmentResidualOwnershipStatus:
    complete = status is AttachmentResidualOwnershipPackageStatus.COMPLETE
    return AttachmentResidualOwnershipStatus(
        status=status,
        run_root=str(root),
        preflight_path=str(root / "preflight.json"),
        report_path=str(root / "report.json") if complete else None,
        review_path=str(root / "diagnostic-review.md") if complete else None,
        handoff_path=str(root / "second-opinion-handoff.md") if complete else None,
        claude_review_path=str(root / "claude-opus-review.md") if complete else None,
        outcome=report.outcome if report is not None else None,
        model_execution_count=report.model_execution_count if report is not None else 0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
    )


def _load_tasks(path: Path) -> tuple[AttachmentEdgeFilterTask, ...]:
    value = _read_json(path)
    if not isinstance(value, list):
        raise ValueError("CEA-1.7 task evidence must be a JSON array.")
    return tuple(
        AttachmentEdgeFilterTask.model_validate_json(_canonical_json(item))
        for item in cast(list[object], value)
    )


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    if cea14.attachment_edge_filter_runtime_contract(config) != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.7 configured runtime differs from sealed CEA-1.5 evidence.")


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _file_reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_file_sha(resolved),
    )


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    if _file_sha(Path(reference.path)) != reference.sha256:
        raise ValueError(f"CEA-1.7 evidence digest drifted: {reference.label}.")


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
        raise ValueError("CEA-1.7 ModelRun lacks elapsed milliseconds.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
