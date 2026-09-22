#!/usr/bin/env python3
"""Run CEA-1.17 Residual Ownership transfer calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID,
    ATTACHMENT_OWNERSHIP_REMAINDER_RENDERER_ID,
    ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    AttachmentEvidenceReference,
    AttachmentPartwiseObservation,
    AttachmentPartwiseReport,
    AttachmentRemainderEnumerationObservation,
    AttachmentRemainderEnumerationReport,
    AttachmentResidualOwnershipPreflight,
    AttachmentResidualOwnershipTask,
    AttachmentResidualTransferGoldCase,
    AttachmentResidualTransferObservation,
    AttachmentResidualTransferPreflight,
    ExecutionSetting,
    ExtractionStageTrace,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_domain.models import JsonValue
from kotekomi_pipelines.competitive_attachment_finite_answer_format import finite_label_evidence
from kotekomi_pipelines.competitive_attachment_residual_transfer import (
    build_residual_transfer_phase,
    build_residual_transfer_preflight,
    build_residual_transfer_report,
    render_residual_transfer_handoff,
    render_residual_transfer_review,
    select_residual_transfer_threshold,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

ROOT = Path(__file__).resolve().parents[1]
TDD = ROOT / "docs/2026-09-21-competitive-attachment-residual-transfer-calibration.md"
GOLD = ROOT / "docs/cea117-residual-ownership-transfer-gold-v1.json"
PROMPT = ROOT / "prompts/competitive_attachment_residual_ownership_format_bare_v1.md"
PROMPT_ID = "competitive_attachment_residual_ownership_format_bare_v1"
FILTERED_TASK_IDS = {"aro_7d658622da90db3299ebee76", "aro_e05ad7d4c4c93ca6ceac7a6d"}


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    for name in (
        "config",
        "residual-root",
        "partwise-root",
        "enumeration-root",
        "cardinality-root",
        "run-root",
    ):
        prepare.add_argument(f"--{name}", type=Path, required=True)
    run = commands.add_parser("run-validation")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run-validation": _run_validation}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.17 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    config = _config(args.config)
    residual_root = args.residual_root.resolve()
    partwise_root = args.partwise_root.resolve()
    enumeration_root = args.enumeration_root.resolve()
    cardinality_root = args.cardinality_root.resolve()
    residual = AttachmentResidualOwnershipPreflight.model_validate_json(
        (residual_root / "preflight.json").read_bytes()
    )
    partwise = AttachmentPartwiseReport.model_validate_json(
        (partwise_root / "report.json").read_bytes()
    )
    enumeration = AttachmentRemainderEnumerationReport.model_validate_json(
        (enumeration_root / "report.json").read_bytes()
    )
    cardinality = _read_json(cardinality_root / "report.json")
    if cardinality.get("outcome") != "falsified":
        raise ValueError("CEA-1.17 requires the completed falsified CEA-1.16 result.")
    if not (cardinality_root / "claude-opus-review.md").is_file():
        raise ValueError("CEA-1.17 requires the CEA-1.16 independent review.")
    gold = _load_gold()
    prompt = _reference("prompt", PROMPT)
    source_metadata = _read_json(enumeration_root / "run.json")
    _validate_runtime(config, source_metadata)
    validation_root, validation_lineage = _validation_evidence_lineage(residual_root)
    cea14.validate_competitive_attachment_phase_evidence(
        validation_root, expected_phase="validation"
    )
    development = _development_observations(
        tasks=residual.development_tasks,
        gold=gold,
        partwise=partwise,
        enumeration=enumeration,
        partwise_root=partwise_root,
        enumeration_root=enumeration_root,
        config=config,
        prompt_sha256=prompt.sha256,
    )
    threshold = select_residual_transfer_threshold(development)
    phase = build_residual_transfer_phase(
        phase="development",
        tasks=residual.development_tasks,
        gold=gold,
        observations=development,
        threshold=threshold,
    )
    if phase.auroc != (0.9375, 0.9375) or any(
        abs(item - 0.9861111111111112) > 1e-12 for item in phase.average_precision
    ):
        raise ValueError("CEA-1.17 sealed development ranking drifted.")
    if tuple(item.accuracy for item in phase.threshold_metrics) != (0.9, 0.9):
        raise ValueError("CEA-1.17 development threshold no longer yields nine of ten.")
    identities = {item.model_identity_digest for item in development}
    if len(identities) != 1:
        raise ValueError("CEA-1.17 development evidence used multiple model identities.")
    inputs = tuple(
        sorted(
            (
                _reference("cardinality_claude_review", cardinality_root / "claude-opus-review.md"),
                _reference("cardinality_report", cardinality_root / "report.json"),
                _reference("gold", GOLD),
                _reference("partwise_report", partwise_root / "report.json"),
                _reference("enumeration_report", enumeration_root / "report.json"),
                _reference("residual_preflight", residual_root / "preflight.json"),
                _reference("tdd", TDD),
                *validation_lineage,
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_residual_transfer_preflight(
        inputs=inputs,
        prompt=prompt,
        gold=gold,
        development=phase,
        validation_tasks=residual.validation_tasks,
        expected_model_identity_digest=next(iter(identities)),
    )
    _write_json(root / "preflight.json", preflight.model_dump(mode="json"))
    metadata = dict(source_metadata)
    metadata.update(
        {
            "schema_version": "attachment_residual_transfer_run_v1",
            "status": "prepared",
            "config_path": str(args.config.resolve()),
            "prompt_path": str(PROMPT),
            "prompt_sha256": prompt.sha256,
            "prompt_id": PROMPT_ID,
            "validation_run_root": str(validation_root),
            "preflight_fingerprint": preflight.result_fingerprint,
            "preflight_file_sha256": _sha_file(root / "preflight.json"),
            "production_integration": "not_activated",
        }
    )
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        {
            "schema_version": "attachment_residual_transfer_status_v1",
            "status": "prepared",
            "run_root": str(root),
            "preflight": str(root / "preflight.json"),
        },
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(root),
                "preflight": str(root / "preflight.json"),
                "threshold": threshold,
            },
            sort_keys=True,
        )
    )
    return 0


def _run_validation(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentResidualTransferPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint") or _sha_file(
        root / "preflight.json"
    ) != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.17 preflight drifted.")
    for item in (*preflight.inputs, preflight.prompt):
        if _sha_file(Path(item.path)) != item.sha256:
            raise ValueError(f"CEA-1.17 input drifted: {item.label}.")
    generation = _configured_generation(config)
    for repetition in (1, 2):
        cea14.execute_attachment_edge_filter_tasks(
            root=root,
            config=config,
            tasks=tuple(item.edge_filter_task for item in preflight.validation_tasks),
            output_directory=root / f"validation-r{repetition}",
            phase="validation",
            metadata=metadata,
            generation_parameters=generation,
            prompt_id=PROMPT_ID,
            task_renderer_id=ATTACHMENT_OWNERSHIP_REMAINDER_RENDERER_ID,
            effective_max_output_tokens=2,
        )
    gold = tuple(item for item in preflight.gold if item.phase == "validation")
    gold_by_id = {item.task_id: item for item in gold}
    observations = tuple(
        _load_observation(
            path=root / f"validation-r{repetition}" / f"{task.edge_filter_task.task_id}.json",
            archive_root=root / "archive",
            task=task,
            gold=gold_by_id[task.id],
            repetition=repetition,
            config=config,
            prompt_sha256=preflight.prompt.sha256,
            expected_renderer=ATTACHMENT_OWNERSHIP_REMAINDER_RENDERER_ID,
            generation=generation,
            reference_label=f"validation_{repetition}_{task.id}",
        )
        for task in preflight.validation_tasks
        for repetition in (1, 2)
    )
    if {item.model_identity_digest for item in observations} != {
        preflight.expected_model_identity_digest
    }:
        raise ValueError("CEA-1.17 validation model identity drifted.")
    validation = build_residual_transfer_phase(
        phase="validation",
        tasks=preflight.validation_tasks,
        gold=preflight.gold,
        observations=observations,
        threshold=preflight.selected_threshold,
    )
    report_inputs = tuple(
        _reference(f"execution_{index:02d}", Path(item.execution_record.path))
        for index, item in enumerate(observations, 1)
    )
    report = build_residual_transfer_report(
        preflight=preflight, inputs=report_inputs, validation=validation
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_residual_transfer_review(report), encoding="utf-8")
    package = (
        *preflight.inputs,
        preflight.prompt,
        _reference("preflight", root / "preflight.json"),
        _reference("report", report_path),
        _reference("review", review_path),
        *report_inputs,
    )
    handoff_path.write_text(
        render_residual_transfer_handoff(
            report,
            prompt_text=PROMPT.read_text(),
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
            "report_file_sha256": _sha_file(report_path),
            "review_file_sha256": _sha_file(review_path),
            "handoff_file_sha256": _sha_file(handoff_path),
        }
    )
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        {
            "schema_version": "attachment_residual_transfer_status_v1",
            "status": "complete",
            "outcome": report.outcome.value,
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
                "claude_review": str(root / "claude-opus-review.md"),
            },
            sort_keys=True,
        )
    )
    return 0


def _development_observations(
    *,
    tasks: tuple[AttachmentResidualOwnershipTask, ...],
    gold: tuple[AttachmentResidualTransferGoldCase, ...],
    partwise: AttachmentPartwiseReport,
    enumeration: AttachmentRemainderEnumerationReport,
    partwise_root: Path,
    enumeration_root: Path,
    config: PipelineConfig,
    prompt_sha256: str,
) -> tuple[AttachmentResidualTransferObservation, ...]:
    gold_by_id = {item.task_id: item for item in gold if item.phase == "development"}
    partwise_by_id = {item.task.id: item for item in partwise.cases}
    enumeration_by_id = {item.view.authoritative_task.id: item for item in enumeration.cases}
    generation = _configured_generation(config)
    result: list[AttachmentResidualTransferObservation] = []
    for task in tasks:
        if task.id in FILTERED_TASK_IDS:
            filtered_values: tuple[AttachmentRemainderEnumerationObservation, ...] = (
                enumeration_by_id[task.id].observations
            )
            items = tuple((item.repetition, item.execution_record.path) for item in filtered_values)
            renderer = ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID
            archive_root = enumeration_root / "archive"
        else:
            whole_values: tuple[AttachmentPartwiseObservation, ...] = partwise_by_id[
                task.id
            ].whole_observations
            items = tuple((item.repetition, item.execution_record.path) for item in whole_values)
            renderer = ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID
            archive_root = partwise_root / "archive"
        for repetition, execution_path in items:
            result.append(
                _load_observation(
                    path=Path(execution_path),
                    archive_root=archive_root,
                    task=task,
                    gold=gold_by_id[task.id],
                    repetition=cast(Literal[1, 2], repetition),
                    config=config,
                    prompt_sha256=prompt_sha256,
                    expected_renderer=renderer,
                    generation=generation,
                    reference_label=f"development_{repetition}_{task.id}",
                )
            )
    return tuple(result)


def _load_observation(
    *,
    path: Path,
    archive_root: Path,
    task: AttachmentResidualOwnershipTask,
    gold: AttachmentResidualTransferGoldCase,
    repetition: Literal[1, 2],
    config: PipelineConfig,
    prompt_sha256: str,
    expected_renderer: str,
    generation: tuple[ExecutionSetting, ...],
    reference_label: str,
) -> AttachmentResidualTransferObservation:
    archive = LocalArchiveStore(archive_root)
    archive.initialize()
    decision, value = cea14.validate_attachment_edge_filter_execution_record(
        path,
        task.edge_filter_task,
        archive=archive,
        expected_prompt_sha256=prompt_sha256,
        expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
        expected_prompt_id=PROMPT_ID,
        expected_task_renderer_id=expected_renderer,
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical(value["trace"]))
    model_run = ModelRun.model_validate_json(_canonical(value["model_run"]))
    exact_input = trace.input.get("exact_model_input")
    raw_output = trace.output.get("raw_output_text")
    if not isinstance(exact_input, str) or not isinstance(raw_output, str):
        raise ValueError("CEA-1.17 execution lacks exact data-in/data-out.")
    if any(term in exact_input.casefold() for term in ("expected_answer", "gold", "baseline")):
        raise ValueError("CEA-1.17 model input exposes evaluation evidence.")
    if model_run.execution_receipt is None:
        raise ValueError("CEA-1.17 execution lacks a ModelExecutionReceipt.")
    receipt = model_execution_receipt_from_payload(
        cast(Mapping[str, JsonValue], model_run.execution_receipt)
    )
    evidence = finite_label_evidence(receipt)
    identity = _model_identity_digest(model_run)
    strict = (
        raw_output in {"Y", "N", "U"}
        and decision.answer is not None
        and decision.answer.value == raw_output
        and receipt.output_token_count == 1
        and evidence.finite_label_argmax is decision.answer
    )
    return AttachmentResidualTransferObservation(
        phase=task.phase,
        repetition=repetition,
        task_id=task.id,
        expected_answer=gold.expected_answer,
        decision=decision,
        evidence=evidence,
        execution_record=_reference(reference_label, path),
        exact_model_input=exact_input,
        raw_output_text=raw_output,
        model_identity_digest=identity,
        elapsed_milliseconds=_elapsed_milliseconds(model_run),
        strict_finite_answer=strict,
    )


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _configured_generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting(key="frequency_penalty", value=0.0),
        ExecutionSetting(key="max_output_tokens", value=config.model_execution.max_output_tokens),
        ExecutionSetting(key="seed", value=17),
        ExecutionSetting(key="temperature", value=0),
        ExecutionSetting(key="top_logprobs", value=10),
    )


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    if cea14.attachment_edge_filter_runtime_contract(config) != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.17 runtime contract drifted.")


def _validation_evidence_lineage(
    residual_root: Path,
) -> tuple[Path, tuple[AttachmentEvidenceReference, ...]]:
    residual_run_path = residual_root / "run.json"
    residual_metadata = _read_json(residual_run_path)
    if (
        residual_metadata.get("schema_version") != "attachment_residual_ownership_run_v1"
        or residual_metadata.get("status") != "complete"
    ):
        raise ValueError("CEA-1.17 requires completed CEA-1.7 run metadata.")
    calibration_root = _metadata_root(residual_metadata, "calibration_root")
    calibration_run_path = calibration_root / "run.json"
    calibration_metadata = _read_json(calibration_run_path)
    if (
        calibration_metadata.get("schema_version") != "attachment_calibration_run_v1"
        or calibration_metadata.get("status") != "diagnostic_complete"
    ):
        raise ValueError("CEA-1.17 requires completed CEA-1.5 calibration metadata.")
    residual_validation_root = _metadata_root(residual_metadata, "validation_run_root")
    calibration_validation_root = _metadata_root(calibration_metadata, "validation_run_root")
    if residual_validation_root != calibration_validation_root:
        raise ValueError("CEA-1.17 upstream validation evidence roots disagree.")
    validation_root = residual_validation_root
    lineage = (
        _reference("residual_run", residual_run_path),
        _reference("calibration_run", calibration_run_path),
        _reference("validation_run", validation_root / "run.json"),
        _reference("validation_canonical_state", validation_root / "canonical-state.json"),
        _reference("validation_inputs", validation_root / "inputs.jsonl"),
    )
    return validation_root, lineage


def _metadata_root(metadata: dict[str, Any], key: str) -> Path:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"CEA-1.17 metadata requires string {key}.")
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def _model_identity_digest(model_run: ModelRun) -> str:
    admission = model_run.input_admission
    if admission is None or admission.status.value != "ready":
        raise ValueError("CEA-1.17 execution lacks admitted model identity.")
    return admission.model_identity_digest


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if type(value) is not int or value < 0:
        raise ValueError("CEA-1.17 execution lacks elapsed milliseconds.")
    return value


def _load_gold() -> tuple[AttachmentResidualTransferGoldCase, ...]:
    value = _read_json(GOLD)
    if value.get("schema_version") != "attachment_residual_transfer_gold_v1":
        raise ValueError("CEA-1.17 Gold schema is unknown.")
    cases = tuple(
        AttachmentResidualTransferGoldCase.model_validate(item)
        for item in cast(list[object], value["cases"])
    )
    if len(cases) != 17 or len({item.task_id for item in cases}) != 17:
        raise ValueError("CEA-1.17 Gold inventory drifted.")
    return cases


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    return AttachmentEvidenceReference(
        label=label, path=str(path.resolve()), sha256=_sha_file(path)
    )


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    )


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
