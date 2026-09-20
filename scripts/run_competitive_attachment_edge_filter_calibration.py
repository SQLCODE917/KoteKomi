#!/usr/bin/env python3
"""Calibrate and aggregate-evaluate the CEA-1.5 Attachment Edge Filter."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_adapters.lm_studio_model_runtime import LM_STUDIO_MAX_TOP_LOGPROBS
from kotekomi_application import (
    AttachmentCalibrationDevelopmentFreeze,
    AttachmentCalibrationManifest,
    AttachmentCalibrationObservation,
    AttachmentCalibrationPhaseResult,
    AttachmentCalibrationPromptArm,
    AttachmentCalibrationPromptResult,
    AttachmentCalibrationReport,
    AttachmentCalibrationStatus,
    AttachmentCalibrationThresholdEvaluation,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterDiagnosticCatalog,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentExpectedExactProfile,
    ExecutionSetting,
    ExtractionStageTrace,
    ModelExecutionReceipt,
    attachment_calibration_fingerprint,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_edge_filter_calibration import (
    attachment_answer_probability,
    attachment_calibration_outcome,
    build_calibrated_phase_result,
    build_calibration_prompt_result,
    build_expected_exact_profile,
    select_development_calibration,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-19-competitive-attachment-edge-filter-calibration.md"
TOP_LOGPROBS = LM_STUDIO_MAX_TOP_LOGPROBS


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    prepare.add_argument("--v8-root", type=Path, required=True)
    prepare.add_argument("--v9-root", type=Path, required=True)

    for name in ("diagnose", "run-development", "run-validation"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--run-root", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    return {
        "prepare": _prepare,
        "diagnose": _diagnose,
        "run-development": _run_development,
        "run-validation": _run_validation,
        "finalize": _finalize,
    }[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.5 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    config = _config(args.config)
    source_roots = {
        AttachmentCalibrationPromptArm.V8: args.v8_root.resolve(),
        AttachmentCalibrationPromptArm.V9: args.v9_root.resolve(),
    }
    source_metadata = {
        arm: _load_source_metadata(source_root) for arm, source_root in source_roots.items()
    }
    v8_metadata = source_metadata[AttachmentCalibrationPromptArm.V8]
    v9_metadata = source_metadata[AttachmentCalibrationPromptArm.V9]
    if _source_runtime_contract(v8_metadata) != _source_runtime_contract(v9_metadata):
        raise ValueError("CEA-1.5 prompt arms used different runtime contracts.")
    if _runtime_contract(config) != _source_runtime_contract(v9_metadata):
        raise ValueError("CEA-1.5 configured runtime differs from CEA-1.4.")
    for name in (
        "pool-development.json",
        "pool-validation.json",
        "tasks-development.json",
        "tasks-validation.json",
        "diagnostic-catalog.json",
    ):
        first = source_roots[AttachmentCalibrationPromptArm.V8] / name
        second = source_roots[AttachmentCalibrationPromptArm.V9] / name
        if first.read_bytes() != second.read_bytes():
            raise ValueError(f"CEA-1.5 prompt-arm prepared evidence differs: {name}.")
        shutil.copyfile(second, root / name)
    prompt_references: dict[str, dict[str, str]] = {}
    for arm, source_root in source_roots.items():
        expected_sha = _required_str(source_metadata[arm], "prompt_sha256")
        prompt = _recover_prompt(source_root, expected_sha)
        prompt_path = root / "prompts" / f"{arm.value}.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_bytes(prompt)
        prompt_references[arm.value] = {
            "path": str(prompt_path),
            "sha256": expected_sha,
            "source_root": str(source_root),
        }
    metadata = dict(v9_metadata)
    metadata.pop("prompt_path", None)
    metadata.pop("prompt_sha256", None)
    probability_generation = _probability_generation(config)
    metadata.update(
        {
            "schema_version": "attachment_calibration_run_v1",
            "status": "prepared",
            "config_path": str(args.config.resolve()),
            "prompt_arms": prompt_references,
            "top_logprobs": TOP_LOGPROBS,
            "generation_parameters": _generation_payload(probability_generation),
            "generation_parameters_sha256": generation_parameters_digest(probability_generation),
            "source_v8_root": str(source_roots[AttachmentCalibrationPromptArm.V8]),
            "source_v9_root": str(source_roots[AttachmentCalibrationPromptArm.V9]),
        }
    )
    development = cea14.reload_prepared_attachment_edge_filter_phase(root, metadata, "development")
    validation = cea14.reload_prepared_attachment_edge_filter_phase(root, metadata, "validation")
    development_profile = build_expected_exact_profile(
        phase="development",
        edges=development.edges,
        gold_sets=development.gold_sets,
        baseline_exact_set_accuracy=development.cea13_primary_metrics.exact_set_accuracy,
    )
    validation_profile = build_expected_exact_profile(
        phase="validation",
        edges=validation.edges,
        gold_sets=validation.gold_sets,
        baseline_exact_set_accuracy=validation.cea13_primary_metrics.exact_set_accuracy,
    )
    _write_json(
        root / "expected-exact-development.json",
        development_profile.model_dump(mode="json"),
    )
    _write_json(
        root / "expected-exact-validation.json",
        validation_profile.model_dump(mode="json"),
    )
    metadata["expected_exact_development_sha256"] = _file_sha(
        root / "expected-exact-development.json"
    )
    metadata["expected_exact_validation_sha256"] = _file_sha(
        root / "expected-exact-validation.json"
    )
    metadata["runtime_contract_sha256"] = _sha(_canonical_json(_runtime_contract(config)))
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "preflight.json",
        {
            "schema_version": "attachment_calibration_preflight_v1",
            "development_candidate_count": len(development.gold_sets),
            "development_edge_count": len(development.edges),
            "validation_candidate_count": len(validation.gold_sets),
            "validation_edge_count": len(validation.edges),
            "diagnostic_task_count": len(
                AttachmentEdgeFilterDiagnosticCatalog.model_validate_json(
                    (root / "diagnostic-catalog.json").read_bytes()
                ).tasks
            ),
            "prompt_arms": prompt_references,
            "generation_parameters_sha256": metadata["generation_parameters_sha256"],
            "gold_entered_model_task": False,
            "production_integration": "not_activated",
            "passed": True,
        },
    )
    print(
        json.dumps(
            {
                "preflight": str(root / "preflight.json"),
                "run_root": str(root),
                "status": "prepared",
            },
            sort_keys=True,
        )
    )
    return 0


def _diagnose(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root, {"prepared", "diagnostic_complete"})
    config = _config(args.config)
    _validate_runtime(config, metadata)
    catalog = AttachmentEdgeFilterDiagnosticCatalog.model_validate_json(
        (root / "diagnostic-catalog.json").read_bytes()
    )
    prepared = cea14.reload_prepared_attachment_edge_filter_phase(root, metadata, "development")
    development_profile = _load_profile(root / "expected-exact-development.json")
    validation_profile = _load_profile(root / "expected-exact-validation.json")
    prompt_results: list[AttachmentCalibrationPromptResult] = []
    for arm in AttachmentCalibrationPromptArm:
        arm_metadata = _arm_metadata(metadata, arm)
        observations: list[AttachmentCalibrationObservation] = []
        for repetition in (1, 2):
            output = root / "diagnostic" / arm.value / f"repetition-{repetition}"
            quarantine_model_failed_executions(
                root=root,
                directory=output,
                tasks=catalog.tasks,
                expected_prompt_sha256=_prompt_sha(metadata, arm),
                expected_runtime_contract=_runtime_contract(config),
            )
            cea14.execute_attachment_edge_filter_tasks(
                root=root,
                config=config,
                tasks=catalog.tasks,
                output_directory=output,
                phase="development",
                metadata=arm_metadata,
                generation_parameters=_probability_generation(config),
            )
            observations.extend(
                _load_observations(
                    root=root,
                    directory=output,
                    tasks=catalog.tasks,
                    prompt_arm=arm,
                    repetition=repetition,
                    metadata=arm_metadata,
                    config=config,
                    gold_sets=prepared.gold_sets,
                    diagnostic_catalog=catalog,
                )
            )
            metadata[f"diagnostic_{arm.value}_repetition_{repetition}_sha256"] = _directory_sha(
                output
            )
        result = build_calibration_prompt_result(
            prompt_arm=arm,
            prompt_sha256=_prompt_sha(metadata, arm),
            observations=tuple(observations),
            development_profile=development_profile,
            validation_profile=validation_profile,
        )
        _write_json(
            root / "diagnostic" / arm.value / "report.json",
            result.model_dump(mode="json"),
        )
        prompt_results.append(result)
    selected = _select_prompt(tuple(prompt_results))
    review_path = root / "diagnostic-review.md"
    review_path.write_text(
        _render_diagnostic_review(catalog, tuple(prompt_results)), encoding="utf-8"
    )
    summary = {
        "schema_version": "attachment_calibration_diagnostic_summary_v1",
        "status": "complete",
        "prompt_results": [
            {
                "prompt_arm": item.prompt_arm.value,
                "outcome": item.outcome.value,
                "auroc": item.repetition_auroc,
                "average_precision": item.repetition_average_precision,
                "selected_threshold": (
                    item.selected_threshold.threshold
                    if item.selected_threshold is not None
                    else None
                ),
                "result_fingerprint": item.result_fingerprint,
            }
            for item in prompt_results
        ],
        "selected_prompt_arm": selected.prompt_arm.value if selected is not None else None,
        "selected_threshold": (
            selected.selected_threshold.threshold
            if selected is not None and selected.selected_threshold is not None
            else None
        ),
        "development_replay_authorized": selected is not None,
        "review": str(review_path),
        "production_integration": "not_activated",
    }
    _write_json(root / "diagnostic-summary.json", summary)
    metadata["status"] = "diagnostic_complete"
    metadata["diagnostic_summary_sha256"] = _file_sha(root / "diagnostic-summary.json")
    _write_json(root / "run.json", metadata)
    print(json.dumps(summary, sort_keys=True))
    return 0 if selected is not None else 1


def _run_development(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root, {"diagnostic_complete", "development_frozen"})
    config = _config(args.config)
    _validate_runtime(config, metadata)
    selected_prompt = _selected_prompt(root)
    arm = selected_prompt.prompt_arm
    prepared = cea14.reload_prepared_attachment_edge_filter_phase(root, metadata, "development")
    output = root / "development" / "executions"
    diagnostic_source = root / "diagnostic" / arm.value / "repetition-1"
    arm_metadata = _arm_metadata(metadata, arm)
    quarantine_model_failed_executions(
        root=root,
        directory=output,
        tasks=prepared.tasks,
        expected_prompt_sha256=_prompt_sha(metadata, arm),
        expected_runtime_contract=_runtime_contract(config),
    )
    diagnostic_ids = {
        item.task_id
        for item in AttachmentEdgeFilterDiagnosticCatalog.model_validate_json(
            (root / "diagnostic-catalog.json").read_bytes()
        ).tasks
    }
    for task in prepared.tasks:
        if task.task_id not in diagnostic_ids:
            continue
        source = diagnostic_source / f"{task.task_id}.json"
        target = output / f"{task.task_id}.json"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    cea14.execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=prepared.tasks,
        output_directory=output,
        phase="development",
        metadata=arm_metadata,
        generation_parameters=_probability_generation(config),
    )
    observations = _load_observations(
        root=root,
        directory=output,
        tasks=prepared.tasks,
        prompt_arm=arm,
        repetition=1,
        metadata=arm_metadata,
        config=config,
        gold_sets=prepared.gold_sets,
    )
    report = select_development_calibration(
        prompt_arm=arm,
        prompt_sha256=_prompt_sha(metadata, arm),
        observations=observations,
        edges=prepared.edges,
        matrices=prepared.evidence.matrices,
        gold_sets=prepared.gold_sets,
        comparisons=prepared.comparisons,
        gold_by_event_id=prepared.gold_by_event_id,
        source_text_by_digest=prepared.source_text_by_digest,
        entity_occurrences_by_event=prepared.entity_occurrences_by_event,
        protected_baseline=prepared.cea13_primary_metrics,
    )
    report_path = root / "development" / "report.json"
    _write_json(report_path, report.model_dump(mode="json"))
    (root / "development" / "review.md").write_text(
        _render_phase_review(report, prepared), encoding="utf-8"
    )
    freeze_draft = AttachmentCalibrationDevelopmentFreeze.model_construct(
        prompt_arm=arm,
        prompt_sha256=_prompt_sha(metadata, arm),
        runtime_contract_sha256=cast(str, metadata["runtime_contract_sha256"]),
        generation_parameters_sha256=cast(str, metadata["generation_parameters_sha256"]),
        threshold=report.threshold,
        selected_arm=report.selected_arm,
        development_report_sha256=_file_sha(report_path),
        result_fingerprint="0" * 64,
    )
    freeze = AttachmentCalibrationDevelopmentFreeze(
        **freeze_draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_calibration_fingerprint(freeze_draft),
    )
    _write_json(root / "development-freeze.json", freeze.model_dump(mode="json"))
    metadata["status"] = "development_frozen"
    metadata["development_execution_sha256"] = _directory_sha(output)
    metadata["development_report_sha256"] = _file_sha(report_path)
    metadata["development_freeze_sha256"] = _file_sha(root / "development-freeze.json")
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "development_report": str(report_path),
                "freeze": str(root / "development-freeze.json"),
                "prompt_arm": arm.value,
                "selected_arm": report.selected_arm.value,
                "threshold": report.threshold,
                "status": "frozen",
            },
            sort_keys=True,
        )
    )
    return 0


def _run_validation(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root, {"development_frozen", "validation_complete"})
    config = _config(args.config)
    _validate_runtime(config, metadata)
    freeze = _validated_development_freeze(root, metadata)
    prepared = cea14.reload_prepared_attachment_edge_filter_phase(root, metadata, "validation")
    output = root / "validation" / "executions"
    arm_metadata = _arm_metadata(metadata, freeze.prompt_arm)
    quarantine_model_failed_executions(
        root=root,
        directory=output,
        tasks=prepared.tasks,
        expected_prompt_sha256=_prompt_sha(metadata, freeze.prompt_arm),
        expected_runtime_contract=_runtime_contract(config),
    )
    cea14.execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=prepared.tasks,
        output_directory=output,
        phase="validation",
        metadata=arm_metadata,
        generation_parameters=_probability_generation(config),
    )
    observations = _load_observations(
        root=root,
        directory=output,
        tasks=prepared.tasks,
        prompt_arm=freeze.prompt_arm,
        repetition=1,
        metadata=arm_metadata,
        config=config,
        gold_sets=prepared.gold_sets,
    )
    report = build_calibrated_phase_result(
        phase="validation",
        prompt_arm=freeze.prompt_arm,
        prompt_sha256=freeze.prompt_sha256,
        threshold=freeze.threshold,
        observations=observations,
        edges=prepared.edges,
        matrices=prepared.evidence.matrices,
        gold_sets=prepared.gold_sets,
        comparisons=prepared.comparisons,
        gold_by_event_id=prepared.gold_by_event_id,
        source_text_by_digest=prepared.source_text_by_digest,
        entity_occurrences_by_event=prepared.entity_occurrences_by_event,
        baseline_metrics=prepared.cea13_primary_metrics,
        frozen_selected_arm=freeze.selected_arm,
    )
    report_path = root / "validation" / "report.json"
    _write_json(report_path, report.model_dump(mode="json"))
    (root / "validation" / "review.md").write_text(
        _render_phase_review(report, prepared), encoding="utf-8"
    )
    metadata["status"] = "validation_complete"
    metadata["validation_execution_sha256"] = _directory_sha(output)
    metadata["validation_report_sha256"] = _file_sha(report_path)
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "report": str(report_path),
                "selected_arm": report.selected_arm.value,
                "status": "complete",
            },
            sort_keys=True,
        )
    )
    return 0


def _finalize(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root, {"validation_complete", "complete"})
    diagnostic = tuple(
        AttachmentCalibrationPromptResult.model_validate_json(
            (root / "diagnostic" / arm.value / "report.json").read_bytes()
        )
        for arm in AttachmentCalibrationPromptArm
    )
    development = AttachmentCalibrationPhaseResult.model_validate_json(
        (root / "development" / "report.json").read_bytes()
    )
    validation = AttachmentCalibrationPhaseResult.model_validate_json(
        (root / "validation" / "report.json").read_bytes()
    )
    freeze = _validated_development_freeze(root, metadata)
    if (
        development.prompt_arm is not freeze.prompt_arm
        or development.prompt_sha256 != freeze.prompt_sha256
        or development.threshold != freeze.threshold
        or development.selected_arm is not freeze.selected_arm
    ):
        raise ValueError("CEA-1.5 development report drifted from its freeze.")
    outcome = attachment_calibration_outcome(development, validation)
    inputs = tuple(
        sorted(
            (
                _file_reference("diagnostic_catalog", root / "diagnostic-catalog.json", root),
                _file_reference("development_freeze", root / "development-freeze.json", root),
                _file_reference(
                    "development_profile", root / "expected-exact-development.json", root
                ),
                _file_reference("gold_catalog", _metadata_path(metadata, "gold_path")),
                _file_reference("pool_development", root / "pool-development.json", root),
                _file_reference("pool_validation", root / "pool-validation.json", root),
                _file_reference(
                    "prompt_v8", _prompt_path(metadata, AttachmentCalibrationPromptArm.V8), root
                ),
                _file_reference(
                    "prompt_v9", _prompt_path(metadata, AttachmentCalibrationPromptArm.V9), root
                ),
                _file_reference("tasks_development", root / "tasks-development.json", root),
                _file_reference("tasks_validation", root / "tasks-validation.json", root),
                _file_reference(
                    "validation_profile", root / "expected-exact-validation.json", root
                ),
            ),
            key=lambda item: item.label,
        )
    )
    draft = AttachmentCalibrationReport.model_construct(
        inputs=inputs,
        diagnostic=diagnostic,
        development=development,
        validation=validation,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    report = AttachmentCalibrationReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_calibration_fingerprint(draft),
    )
    report_path = root / "report.json"
    review_path = root / "review.md"
    summary_path = root / "summary.json"
    handoff_path = root / "second-opinion-handoff.md"
    status_path = root / "status.json"
    manifest_path = root / "manifest.json"
    _write_json(report_path, report.model_dump(mode="json"))
    summary = _summary(report)
    _write_json(summary_path, summary)
    review_path.write_text(_render_final_review(report), encoding="utf-8")
    handoff_path.write_text(_render_handoff(report), encoding="utf-8")
    status = AttachmentCalibrationStatus(
        outcome=outcome,
        result_fingerprint=report.result_fingerprint,
        report_path=report_path.name,
        review_path=review_path.name,
        summary_path=summary_path.name,
        handoff_path=handoff_path.name,
    )
    _write_json(status_path, status.model_dump(mode="json"))
    outputs = tuple(
        sorted(
            (
                _file_reference("handoff", handoff_path, root),
                _directory_reference("model_output_archive", root / "archive", root),
                _file_reference(
                    "diagnostic_report_v8", root / "diagnostic" / "v8" / "report.json", root
                ),
                _file_reference(
                    "diagnostic_report_v9", root / "diagnostic" / "v9" / "report.json", root
                ),
                _file_reference("diagnostic_review", root / "diagnostic-review.md", root),
                _file_reference("diagnostic_summary", root / "diagnostic-summary.json", root),
                _file_reference("development_report", root / "development" / "report.json", root),
                _file_reference("development_review", root / "development" / "review.md", root),
                _file_reference("preflight", root / "preflight.json", root),
                _file_reference("report", report_path, root),
                _file_reference("review", review_path, root),
                _file_reference("status", status_path, root),
                _file_reference("summary", summary_path, root),
                _file_reference("validation_report", root / "validation" / "report.json", root),
                _file_reference("validation_review", root / "validation" / "review.md", root),
                _directory_reference(
                    "development_executions", root / "development" / "executions", root
                ),
                _directory_reference(
                    "validation_executions", root / "validation" / "executions", root
                ),
                *(
                    (_directory_reference("failed_attempts", root / "failed-attempts", root),)
                    if (root / "failed-attempts").is_dir()
                    else ()
                ),
                *(
                    _directory_reference(
                        f"diagnostic_{arm.value}_repetition_{repetition}",
                        root / "diagnostic" / arm.value / f"repetition-{repetition}",
                        root,
                    )
                    for arm in AttachmentCalibrationPromptArm
                    for repetition in (1, 2)
                ),
            ),
            key=lambda item: item.label,
        )
    )
    manifest = AttachmentCalibrationManifest(
        tdd=_file_reference("tdd", TDD_PATH),
        inputs=inputs,
        outputs=outputs,
        result_fingerprint=report.result_fingerprint,
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    metadata["status"] = "complete"
    metadata["result_fingerprint"] = report.result_fingerprint
    metadata["manifest_sha256"] = _file_sha(manifest_path)
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "handoff": str(handoff_path),
                "manifest": str(manifest_path),
                "outcome": outcome.value,
                "report": str(report_path),
                "review": str(review_path),
                "status": "complete",
                "status_file": str(status_path),
                "summary": str(summary_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _load_observations(
    *,
    root: Path,
    directory: Path,
    tasks: tuple[AttachmentEdgeFilterTask, ...],
    prompt_arm: AttachmentCalibrationPromptArm,
    repetition: int,
    metadata: dict[str, Any],
    config: PipelineConfig,
    gold_sets: dict[str, tuple[str, ...]],
    diagnostic_catalog: AttachmentEdgeFilterDiagnosticCatalog | None = None,
) -> tuple[AttachmentCalibrationObservation, ...]:
    archive = LocalArchiveStore(root / "archive")
    configured_generation = _probability_generation(config)
    result: list[AttachmentCalibrationObservation] = []
    for task in tasks:
        path = directory / f"{task.task_id}.json"
        decision, value = cea14.validate_attachment_edge_filter_execution_record(
            path,
            task,
            archive=archive,
            expected_prompt_sha256=_prompt_sha(metadata, prompt_arm),
            expected_runtime_contract=_runtime_contract(config),
        )
        if (
            decision.status
            not in {
                AttachmentEdgeFilterDecisionStatus.COMPLETE,
                AttachmentEdgeFilterDecisionStatus.UNCLEAR,
            }
            or decision.answer is None
        ):
            raise ValueError("CEA-1.5 calibration requires complete Y/N/U execution evidence.")
        model_run = model_run_from_execution_record(value)
        receipt = validate_execution_generation_evidence(model_run, configured_generation)
        trace = extraction_stage_trace_from_execution_record(value)
        exact_input_sha = trace.input.get("exact_model_input_sha256")
        exact_model_input = trace.input.get("exact_model_input")
        raw_output_text = trace.output.get("raw_output_text")
        if (
            not isinstance(exact_input_sha, str)
            or not isinstance(exact_model_input, str)
            or not exact_model_input
            or _sha(exact_model_input.encode()) != exact_input_sha
        ):
            raise ValueError("CEA-1.5 execution trace lacks exact input evidence.")
        if (
            not isinstance(raw_output_text, str)
            or not raw_output_text
            or _sha(raw_output_text.encode()) != decision.raw_output_sha256
        ):
            raise ValueError("CEA-1.5 execution trace lacks exact output evidence.")
        elapsed_milliseconds = model_run.execution_diagnostics.get("elapsed_milliseconds")
        if type(elapsed_milliseconds) is not int:
            raise ValueError("CEA-1.5 execution lacks elapsed-time evidence.")
        expected: Literal["Y", "N"] = (
            "Y" if task.edge.source_grounded_event_id in gold_sets[task.edge.candidate_id] else "N"
        )
        coverage: set[str] = (
            set(diagnostic_catalog.coverage_by_task_id[task.task_id])
            if diagnostic_catalog is not None
            else set()
        )
        result.append(
            AttachmentCalibrationObservation(
                prompt_arm=prompt_arm,
                repetition=repetition,
                task_id=task.task_id,
                edge_id=task.edge.id,
                expected_answer=expected,
                protected_positive=(
                    expected == "Y"
                    and (
                        bool({"shared_entity", "attribution"} & coverage)
                        or "entity_occurrence" in task.candidate.reasons
                    )
                ),
                hard_negative=expected == "N" and "gold_none" in coverage,
                extraction_task_id=cast(str, decision.extraction_task_id),
                model_run_id=cast(str, decision.model_run_id),
                trace_id=cast(str, decision.trace_id),
                execution_receipt_sha256=_sha(_canonical_json(model_run.execution_receipt)),
                prompt_sha256=_prompt_sha(metadata, prompt_arm),
                exact_model_input_sha256=exact_input_sha,
                exact_model_input=exact_model_input,
                raw_output_sha256=cast(str, decision.raw_output_sha256),
                raw_output_text=raw_output_text,
                elapsed_milliseconds=elapsed_milliseconds,
                input_token_count=receipt.input_token_count,
                output_token_count=receipt.output_token_count,
                probability=attachment_answer_probability(receipt, emitted_answer=decision.answer),
            )
        )
    return tuple(result)


def model_run_from_execution_record(value: dict[str, Any]) -> ModelRun:
    """Parse one JSON-native execution payload through the strict Domain boundary."""
    return ModelRun.model_validate_json(_canonical_json(value.get("model_run")))


def extraction_stage_trace_from_execution_record(
    value: dict[str, Any],
) -> ExtractionStageTrace:
    """Parse one JSON-native trace payload through the strict Application boundary."""
    return ExtractionStageTrace.model_validate_json(_canonical_json(value.get("trace")))


def validate_execution_generation_evidence(
    model_run: ModelRun,
    configured_generation: tuple[ExecutionSetting, ...],
) -> ModelExecutionReceipt:
    """Validate evidence against the bounded task settings actually sent to the runtime."""
    effective_generation = attachment_edge_filter_generation_parameters(configured_generation)
    if model_run.generation_parameters != _generation_payload(effective_generation):
        raise ValueError("CEA-1.5 execution generation settings drifted.")
    if model_run.execution_receipt is None:
        raise ValueError("CEA-1.5 execution lacks its receipt.")
    receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
    if receipt.generation_parameters_digest != generation_parameters_digest(effective_generation):
        raise ValueError("CEA-1.5 receipt generation digest drifted.")
    return receipt


def quarantine_model_failed_executions(
    *,
    root: Path,
    directory: Path,
    tasks: tuple[AttachmentEdgeFilterTask, ...],
    expected_prompt_sha256: str,
    expected_runtime_contract: dict[str, object],
) -> None:
    """Preserve explicit runtime failures before an operator-requested retry."""
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    for task in tasks:
        path = directory / f"{task.task_id}.json"
        if not path.is_file():
            continue
        decision, _ = cea14.validate_attachment_edge_filter_execution_record(
            path,
            task,
            archive=archive,
            expected_prompt_sha256=expected_prompt_sha256,
            expected_runtime_contract=expected_runtime_contract,
        )
        if decision.status is not AttachmentEdgeFilterDecisionStatus.MODEL_FAILED:
            continue
        relative_directory = directory.resolve().relative_to(root.resolve())
        destination_directory = root / "failed-attempts" / relative_directory / task.task_id
        destination_directory.mkdir(parents=True, exist_ok=True)
        attempt = 1
        destination = destination_directory / f"attempt-{attempt}.json"
        while destination.exists():
            attempt += 1
            destination = destination_directory / f"attempt-{attempt}.json"
        path.replace(destination)
        print(f"Edge Filter task {task.task_id}: quarantined model_failed attempt {attempt}")


def _recover_prompt(root: Path, expected_sha256: str) -> bytes:
    execution = next(
        iter(sorted((root / "diagnostic" / "repetition-1").glob("aet_*.json"))),
        None,
    )
    if execution is None:
        raise ValueError("CEA-1.5 cannot recover a prompt without sealed execution evidence.")
    value = _read_json(execution)
    extraction_task_value = value.get("extraction_task")
    if not isinstance(extraction_task_value, dict):
        raise ValueError("CEA-1.5 sealed execution lacks its ExtractionTask.")
    extraction_task = cast(dict[str, object], extraction_task_value)
    manifest_value = extraction_task.get("context_manifest_payload")
    if not isinstance(manifest_value, dict):
        raise ValueError("CEA-1.5 sealed execution lacks its ContextManifest payload.")
    manifest = cast(dict[str, object], manifest_value)
    encoded = manifest.get("rendered_input_base64")
    if not isinstance(encoded, str):
        raise ValueError("CEA-1.5 sealed ContextManifest lacks rendered input.")
    rendered = base64.b64decode(encoded, validate=True)
    matches = tuple(
        rendered[:end]
        for end in range(1, len(rendered) + 1)
        if _sha(rendered[:end]) == expected_sha256
    )
    if len(matches) != 1:
        raise ValueError("CEA-1.5 could not recover one exact prompt prefix.")
    return matches[0]


def _select_prompt(
    results: tuple[AttachmentCalibrationPromptResult, ...],
) -> AttachmentCalibrationPromptResult | None:
    eligible = tuple(item for item in results if item.selected_threshold is not None)
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda item: (
            sum(
                metric.accuracy for metric in _required_selected_threshold(item).repetition_metrics
            ),
            sum(item.repetition_auroc),
            sum(item.repetition_average_precision),
            -tuple(AttachmentCalibrationPromptArm).index(item.prompt_arm),
        ),
    )


def _required_selected_threshold(
    result: AttachmentCalibrationPromptResult,
) -> AttachmentCalibrationThresholdEvaluation:
    if result.selected_threshold is None:
        raise ValueError("CEA-1.5 selected Prompt Arm lacks a threshold.")
    return result.selected_threshold


def _selected_prompt(root: Path) -> AttachmentCalibrationPromptResult:
    summary = _read_json(root / "diagnostic-summary.json")
    value = summary.get("selected_prompt_arm")
    if not isinstance(value, str):
        raise ValueError("CEA-1.5 diagnostic did not authorize development replay.")
    arm = AttachmentCalibrationPromptArm(value)
    return AttachmentCalibrationPromptResult.model_validate_json(
        (root / "diagnostic" / arm.value / "report.json").read_bytes()
    )


def _probability_generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    base = _generation(config)
    settings = (*base, ExecutionSetting("top_logprobs", TOP_LOGPROBS))
    if tuple(sorted(settings, key=lambda item: item.key)) != settings:
        raise ValueError("CEA-1.5 probability settings are not canonically ordered.")
    return settings


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )


def _runtime_contract(config: PipelineConfig) -> dict[str, object]:
    value = config.model_execution
    return {
        "adapter": value.adapter,
        "context_tokens": value.context_tokens,
        "endpoint": value.endpoint,
        "max_output_tokens": value.max_output_tokens,
        "model": value.model,
        "profile_name": value.profile_name,
        "timeout_seconds": value.timeout_seconds,
    }


def _generation_payload(
    settings: tuple[ExecutionSetting, ...],
) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _source_runtime_contract(metadata: dict[str, Any]) -> dict[str, object]:
    value = metadata.get("runtime_contract")
    if not isinstance(value, dict):
        raise ValueError("CEA-1.5 source metadata lacks a runtime contract.")
    return cast(dict[str, object], value)


def _metadata_path(metadata: dict[str, Any], key: str) -> Path:
    value = _required_str(metadata, key)
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _required_str(value: dict[str, Any], key: str) -> str:
    observed = value.get(key)
    if not isinstance(observed, str) or not observed:
        raise ValueError(f"CEA-1.5 metadata requires string {key}.")
    return observed


def _arm_metadata(metadata: dict[str, Any], arm: AttachmentCalibrationPromptArm) -> dict[str, Any]:
    result = dict(metadata)
    result["prompt_path"] = str(_prompt_path(metadata, arm))
    result["prompt_sha256"] = _prompt_sha(metadata, arm)
    return result


def _prompt_reference(
    metadata: dict[str, Any], arm: AttachmentCalibrationPromptArm
) -> dict[str, str]:
    arms = metadata.get("prompt_arms")
    if not isinstance(arms, dict):
        raise ValueError("CEA-1.5 metadata lacks prompt arms.")
    value = cast(dict[str, object], arms).get(arm.value)
    if not isinstance(value, dict):
        raise ValueError(f"CEA-1.5 metadata lacks prompt arm {arm.value}.")
    typed = cast(dict[str, object], value)
    if set(typed) != {"path", "sha256", "source_root"} or any(
        not isinstance(item, str) or not item for item in typed.values()
    ):
        raise ValueError("CEA-1.5 prompt reference shape is invalid.")
    return cast(dict[str, str], typed)


def _prompt_path(metadata: dict[str, Any], arm: AttachmentCalibrationPromptArm) -> Path:
    return Path(_prompt_reference(metadata, arm)["path"])


def _prompt_sha(metadata: dict[str, Any], arm: AttachmentCalibrationPromptArm) -> str:
    return _prompt_reference(metadata, arm)["sha256"]


def _load_metadata(root: Path, allowed_status: set[str]) -> dict[str, Any]:
    metadata = _read_json(root / "run.json")
    if metadata.get("schema_version") != "attachment_calibration_run_v1":
        raise ValueError("CEA-1.5 run metadata schema is unknown.")
    if metadata.get("status") not in allowed_status:
        raise ValueError(f"CEA-1.5 run status is not allowed: {metadata.get('status')}.")
    for arm in AttachmentCalibrationPromptArm:
        path = _prompt_path(metadata, arm)
        if _file_sha(path) != _prompt_sha(metadata, arm):
            raise ValueError(f"CEA-1.5 prompt arm {arm.value} drifted.")
    checks = {
        "development_pool_sha256": root / "pool-development.json",
        "development_tasks_sha256": root / "tasks-development.json",
        "diagnostic_catalog_sha256": root / "diagnostic-catalog.json",
        "expected_exact_development_sha256": root / "expected-exact-development.json",
        "expected_exact_validation_sha256": root / "expected-exact-validation.json",
        "validation_pool_sha256": root / "pool-validation.json",
        "validation_tasks_sha256": root / "tasks-validation.json",
    }
    for key, path in checks.items():
        if metadata.get(key) != _file_sha(path):
            raise ValueError(f"CEA-1.5 prepared evidence drifted: {key}.")
    execution_checks = {
        **{
            f"diagnostic_{arm.value}_repetition_{repetition}_sha256": root
            / "diagnostic"
            / arm.value
            / f"repetition-{repetition}"
            for arm in AttachmentCalibrationPromptArm
            for repetition in (1, 2)
        },
        "development_execution_sha256": root / "development" / "executions",
        "validation_execution_sha256": root / "validation" / "executions",
    }
    for key, path in execution_checks.items():
        expected = metadata.get(key)
        if expected is not None and expected != _directory_sha(path):
            raise ValueError(f"CEA-1.5 execution evidence drifted: {key}.")
    return metadata


def _load_source_metadata(root: Path) -> dict[str, Any]:
    metadata = _read_json(root / "run.json")
    if metadata.get("schema_version") != "attachment_edge_filter_experiment_run_v1":
        raise ValueError("CEA-1.5 source run metadata schema is unknown.")
    checks = {
        "development_pool_sha256": root / "pool-development.json",
        "development_tasks_sha256": root / "tasks-development.json",
        "diagnostic_catalog_sha256": root / "diagnostic-catalog.json",
        "validation_pool_sha256": root / "pool-validation.json",
        "validation_tasks_sha256": root / "tasks-validation.json",
    }
    for key, path in checks.items():
        if metadata.get(key) != _file_sha(path):
            raise ValueError(f"CEA-1.5 source evidence drifted: {key}.")
    gold_path = _metadata_path(metadata, "gold_path")
    if metadata.get("gold_sha256") != _file_sha(gold_path):
        raise ValueError("CEA-1.5 source Gold changed after CEA-1.4 prepare.")
    return metadata


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    observed = _runtime_contract(config)
    if observed != metadata.get("runtime_contract") or _sha(
        _canonical_json(observed)
    ) != metadata.get("runtime_contract_sha256"):
        raise ValueError("CEA-1.5 configured runtime differs from its frozen contract.")
    generation = _probability_generation(config)
    if _generation_payload(generation) != metadata.get(
        "generation_parameters"
    ) or generation_parameters_digest(generation) != metadata.get("generation_parameters_sha256"):
        raise ValueError("CEA-1.5 generation settings differ from their frozen contract.")


def _validated_development_freeze(
    root: Path,
    metadata: dict[str, Any],
) -> AttachmentCalibrationDevelopmentFreeze:
    path = root / "development-freeze.json"
    if metadata.get("development_freeze_sha256") != _file_sha(path):
        raise ValueError("CEA-1.5 development freeze changed after selection.")
    freeze = AttachmentCalibrationDevelopmentFreeze.model_validate_json(path.read_bytes())
    if (
        freeze.prompt_sha256 != _prompt_sha(metadata, freeze.prompt_arm)
        or freeze.runtime_contract_sha256 != metadata.get("runtime_contract_sha256")
        or freeze.generation_parameters_sha256 != metadata.get("generation_parameters_sha256")
        or freeze.development_report_sha256 != metadata.get("development_report_sha256")
    ):
        raise ValueError("CEA-1.5 development freeze references changed evidence.")
    return freeze


def _load_profile(path: Path) -> AttachmentExpectedExactProfile:
    return AttachmentExpectedExactProfile.model_validate_json(path.read_bytes())


def _render_diagnostic_review(
    catalog: AttachmentEdgeFilterDiagnosticCatalog,
    results: tuple[AttachmentCalibrationPromptResult, ...],
) -> str:
    tasks = {item.task_id: item for item in catalog.tasks}
    lines = ["# CEA-1.5 Calibration Diagnostic Review", ""]
    for result in results:
        lines.extend(
            (
                f"## Prompt {result.prompt_arm.value}",
                "",
                f"Outcome: `{result.outcome.value}`",
                f"AUROC: `{result.repetition_auroc}`",
                f"Average precision: `{result.repetition_average_precision}`",
                "",
            )
        )
        for observation in result.observations:
            task = tasks[observation.task_id]
            lines.extend(
                (
                    f"### {observation.task_id} — repetition {observation.repetition}",
                    "",
                    "Exact SourceSegment:",
                    "",
                    f"> {task.source_text}",
                    "",
                    f"Exact Candidate: `{task.candidate.text}`",
                    f"Target Event: `{task.edge.event_range.text}`",
                    "",
                    "Exact model input:",
                    "",
                    f"```text\n{observation.exact_model_input}\n```",
                    "",
                    f"Expected: `{observation.expected_answer}`",
                    f"Raw output: `{observation.raw_output_text}`",
                    f"Parsed answer: `{observation.probability.emitted_answer.value}`",
                    f"Execution receipt: `{observation.execution_receipt_sha256}`",
                    f"Score: `{observation.probability.attachment_score}`",
                    "Probabilities: "
                    f"`Y={observation.probability.yes_log_probability}`, "
                    f"`N={observation.probability.no_log_probability}`, "
                    f"`U={observation.probability.unclear_log_probability}`",
                    f"Elapsed milliseconds: `{observation.elapsed_milliseconds}`",
                    "",
                )
            )
    return "\n".join(lines)


def _render_phase_review(report: AttachmentCalibrationPhaseResult, prepared: Any) -> str:
    selected = next(item for item in report.arms if item.arm is report.selected_arm)
    return "\n".join(
        (
            f"# CEA-1.5 {report.phase.title()} Calibration Review",
            "",
            f"Prompt arm: `{report.prompt_arm.value}`",
            f"Threshold: `{report.threshold}`",
            f"Selected Pool Arm: `{report.selected_arm.value}`",
            f"Exact Attachment Set accuracy: `{selected.metrics.exact_set_accuracy}`",
            f"CEA-1.3 exact-set baseline: `{report.baseline_metrics.exact_set_accuracy}`",
            f"Edge precision: `{selected.metrics.edge_precision}`",
            f"CEA-1.3 edge-precision baseline: `{report.baseline_metrics.edge_precision}`",
            f"Edge recall: `{selected.metrics.edge_recall}`",
            f"Sibling-Event Leakage: `{selected.metrics.sibling_event_leakage_count}`",
            "CEA-1.3 Sibling-Event Leakage: "
            f"`{report.baseline_metrics.sibling_event_leakage_count}`",
            f"Entity recall: `{selected.metrics.entity_recall}`",
            f"Qualification recall: `{selected.metrics.qualification_recall}`",
            f"Maximum-Pool edges: `{len(prepared.edges)}`",
            "Production integration: `not_activated`",
            "",
        )
    )


def _summary(report: AttachmentCalibrationReport) -> dict[str, object]:
    return {
        "schema_version": "attachment_calibration_summary_v1",
        "status": "complete",
        "outcome": report.outcome.value,
        "prompt_arm": report.development.prompt_arm.value,
        "threshold": report.development.threshold,
        "selected_arm": report.development.selected_arm.value,
        "development": _phase_metrics(report.development),
        "validation": _phase_metrics(report.validation),
        "production_integration": "not_activated",
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
        "result_fingerprint": report.result_fingerprint,
    }


def _phase_metrics(report: AttachmentCalibrationPhaseResult) -> dict[str, object]:
    result = next(item for item in report.arms if item.arm is report.selected_arm)
    return {
        "baseline": report.baseline_metrics.model_dump(mode="json"),
        "calibrated": result.metrics.model_dump(mode="json"),
    }


def _render_final_review(report: AttachmentCalibrationReport) -> str:
    summary = _summary(report)
    return "\n".join(
        (
            "# CEA-1.5 Calibration Result",
            "",
            f"Outcome: `{report.outcome.value}`",
            f"Prompt arm: `{report.development.prompt_arm.value}`",
            f"Threshold: `{report.development.threshold}`",
            f"Selected Pool Arm: `{report.development.selected_arm.value}`",
            "",
            "Development:",
            "",
            f"```json\n{json.dumps(summary['development'], indent=2, sort_keys=True)}\n```",
            "",
            "Validation:",
            "",
            f"```json\n{json.dumps(summary['validation'], indent=2, sort_keys=True)}\n```",
            "",
            "Production integration remains `not_activated`.",
            "",
        )
    )


def _render_handoff(report: AttachmentCalibrationReport) -> str:
    development = next(
        item for item in report.development.arms if item.arm is report.development.selected_arm
    )
    validation = next(
        item for item in report.validation.arms if item.arm is report.validation.selected_arm
    )
    lines = [
        "# CEA-1.5 Second-Opinion Handoff",
        "",
        "## Question",
        "",
        "Do first-token Y/N/U probabilities make the generic Attachment Edge Filter calibratable?",
        "",
        "## Frozen decision",
        "",
        f"Outcome: `{report.outcome.value}`",
        f"Prompt arm: `{report.development.prompt_arm.value}`",
        f"Threshold: `{report.development.threshold}`",
        f"Pool arm: `{report.development.selected_arm.value}`",
        "Validation interpretation: `diagnostic_only`",
        "Production integration: `not_activated`",
        "",
        "## Diagnostic ranking",
        "",
    ]
    for item in report.diagnostic:
        lines.extend(
            (
                f"Prompt `{item.prompt_arm.value}` outcome: `{item.outcome.value}`",
                f"Prompt `{item.prompt_arm.value}` AUROC: `{item.repetition_auroc}`",
                "Prompt "
                f"`{item.prompt_arm.value}` average precision: "
                f"`{item.repetition_average_precision}`",
                "",
            )
        )
    lines.extend(
        (
            "## Aggregate result",
            "",
            _handoff_metric_line(
                "Development exact-set accuracy",
                report.development.baseline_metrics.exact_set_accuracy,
                development.metrics.exact_set_accuracy,
            ),
            _handoff_metric_line(
                "Development edge precision",
                report.development.baseline_metrics.edge_precision,
                development.metrics.edge_precision,
            ),
            _handoff_metric_line(
                "Development sibling leakage",
                report.development.baseline_metrics.sibling_event_leakage_count,
                development.metrics.sibling_event_leakage_count,
            ),
            _handoff_metric_line(
                "Validation exact-set accuracy",
                report.validation.baseline_metrics.exact_set_accuracy,
                validation.metrics.exact_set_accuracy,
            ),
            _handoff_metric_line(
                "Validation edge precision",
                report.validation.baseline_metrics.edge_precision,
                validation.metrics.edge_precision,
            ),
            _handoff_metric_line(
                "Validation sibling leakage",
                report.validation.baseline_metrics.sibling_event_leakage_count,
                validation.metrics.sibling_event_leakage_count,
            ),
            "",
            "## Evidence map",
            "",
            "`diagnostic-review.md` contains exact model input, raw output, and Y/N/U scores.",
            "`development/review.md` contains the selected development result.",
            "`validation/review.md` contains the frozen validation result.",
            "`report.json` contains the complete typed terminal evidence.",
            "`manifest.json` binds the inputs, executions, Archive, and rendered evidence.",
            "",
            "## Interpretation limits",
            "",
            "The break-even estimate assumes homogeneous independent edge errors.",
            "Development Gold selected the threshold and Pool Arm.",
            "Validation reuses prior source material and is not independent transfer evidence.",
            "No ProposedChange or accepted Ledger state was written.",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
            "",
        )
    )
    return "\n".join(lines)


def _handoff_metric_line(label: str, baseline: float | int, calibrated: float | int) -> str:
    return f"{label}: CEA-1.3 `{baseline}`; calibrated `{calibrated}`"


def _file_reference(
    label: str, path: Path, relative_to: Path | None = None
) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    stored = str(resolved.relative_to(relative_to)) if relative_to is not None else str(resolved)
    return AttachmentEvidenceReference(label=label, path=stored, sha256=_file_sha(resolved))


def _directory_reference(
    label: str,
    path: Path,
    relative_to: Path | None = None,
) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"CEA-1.5 evidence directory is missing: {resolved}.")
    stored = (
        str(resolved.relative_to(relative_to.resolve()))
        if relative_to is not None
        else str(resolved)
    )
    return AttachmentEvidenceReference(
        label=label,
        path=stored,
        sha256=_directory_sha(resolved),
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json(value) + b"\n")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _directory_sha(path: Path) -> str:
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    if not files:
        raise ValueError(f"CEA-1.5 evidence directory is empty: {path}.")
    inventory = tuple(
        {
            "path": str(item.relative_to(path)),
            "sha256": _file_sha(item),
        }
        for item in files
    )
    return _sha(_canonical_json(inventory))


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
