#!/usr/bin/env python3
"""Run the CEA-1.13 Part-Wise Residual Ownership experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_REMAINDER_PART_RENDERER_ID,
    ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    AttachmentCalibratedTerminationPreflight,
    AttachmentCalibratedTerminationReport,
    AttachmentEvidenceReference,
    AttachmentPartwiseArm,
    AttachmentPartwiseObservation,
    AttachmentPartwisePackageStatus,
    AttachmentPartwisePreflight,
    AttachmentPartwiseReport,
    AttachmentPartwiseStatus,
    AttachmentRemainderPartKind,
    AttachmentRemainderPartTask,
    AttachmentResidualCueAblationReport,
    ExecutionSetting,
    ExtractionStageTrace,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_partwise_residual_ownership import (
    build_partwise_preflight,
    build_partwise_report,
    render_partwise_handoff,
    render_partwise_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-partwise-residual-ownership.md"
WHOLE_PROMPT_PATH = (
    REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_format_bare_v1.md"
)
PART_PROMPT_PATH = REPOSITORY_ROOT / "prompts/competitive_attachment_remainder_part_v1.md"
WHOLE_PROMPT_ID = "competitive_attachment_residual_ownership_format_bare_v1"
PART_PROMPT_ID = "competitive_attachment_remainder_part_v1"
REQUESTED_OUTPUT_LIMIT = 2
TOP_LOGPROBS = 10


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--calibrated-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.13 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    calibrated_root = args.calibrated_root.resolve()
    config = _config(args.config)
    calibrated_metadata, calibrated_preflight, calibrated_report = _load_calibrated_package(
        calibrated_root
    )
    _validate_runtime(config, calibrated_metadata)
    answer_root = Path(_required_str(calibrated_metadata, "answer_format_root"))
    answer_metadata = _read_json(answer_root / "run.json")
    cue_root = Path(_required_str(answer_metadata, "cue_root"))
    cue_report_path = cue_root / "comparison-report.json"
    cue_report = AttachmentResidualCueAblationReport.model_validate_json(
        cue_report_path.read_bytes()
    )
    expected = {item.task_id: item.expected_answer for item in cue_report.cases}
    whole_prompt = _file_reference("whole_prompt", WHOLE_PROMPT_PATH)
    part_prompt = _file_reference("part_prompt", PART_PROMPT_PATH)
    inputs = tuple(
        sorted(
            (
                _file_reference(
                    "calibrated_handoff", calibrated_root / "second-opinion-handoff.md"
                ),
                _file_reference("calibrated_preflight", calibrated_root / "preflight.json"),
                _file_reference("calibrated_report", calibrated_root / "report.json"),
                _file_reference("calibrated_review", calibrated_root / "comparison-review.md"),
                _file_reference("calibrated_run", calibrated_root / "run.json"),
                _file_reference("calibrated_status", calibrated_root / "status.json"),
                _file_reference(
                    "calibrated_claude_review", calibrated_root / "claude-opus-review.md"
                ),
                _file_reference("corrected_gold_report", cue_report_path),
                _file_reference("tdd", TDD_PATH),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_partwise_preflight(
        inputs=inputs,
        whole_prompt=whole_prompt,
        part_prompt=part_prompt,
        calibrated_preflight=calibrated_preflight,
        calibrated_report=calibrated_report,
        expected_answer_by_task=cast(dict[str, Literal["Y", "N"]], expected),
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    metadata = {
        "schema_version": "attachment_partwise_run_v1",
        "status": "prepared",
        "config_path": str(args.config.resolve()),
        "calibrated_root": str(calibrated_root),
        "cue_root": str(cue_root),
        "development_run_root": _required_str(calibrated_metadata, "development_run_root"),
        "runtime_contract": calibrated_metadata["runtime_contract"],
        "runtime_contract_sha256": _sha_json(calibrated_metadata["runtime_contract"]),
        "whole_prompt_path": str(WHOLE_PROMPT_PATH),
        "whole_prompt_sha256": whole_prompt.sha256,
        "whole_prompt_id": WHOLE_PROMPT_ID,
        "part_prompt_path": str(PART_PROMPT_PATH),
        "part_prompt_sha256": part_prompt.sha256,
        "part_prompt_id": PART_PROMPT_ID,
        "tdd_path": str(TDD_PATH),
        "configured_generation_parameters": _generation_payload(configured_generation),
        "configured_generation_parameters_sha256": generation_parameters_digest(
            configured_generation
        ),
        "effective_generation_parameters": _generation_payload(effective_generation),
        "effective_generation_parameters_sha256": generation_parameters_digest(
            effective_generation
        ),
        "effective_max_output_tokens": REQUESTED_OUTPUT_LIMIT,
        "top_logprobs": TOP_LOGPROBS,
        "production_integration": "not_activated",
    }
    preflight_path = root / "preflight.json"
    _write_json(preflight_path, preflight.model_dump(mode="json"))
    metadata["preflight_fingerprint"] = preflight.result_fingerprint
    metadata["preflight_file_sha256"] = _file_sha(preflight_path)
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "tasks-parts.json",
        [item.model_dump(mode="json") for item in preflight.part_tasks],
    )
    status = _status(root, AttachmentPartwisePackageStatus.PREPARED)
    _write_json(root / "status.json", status.model_dump(mode="json"))
    print(
        json.dumps(
            {"preflight": str(preflight_path), "run_root": str(root), "status": "prepared"},
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    if metadata.get("status") not in {"prepared", "complete"}:
        raise ValueError("CEA-1.13 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentPartwisePreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.13 preflight fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.13 preflight file digest drifted.")
    for reference in (*preflight.inputs, preflight.whole_prompt, preflight.part_prompt):
        _validate_reference(reference)
    generation = _configured_generation(config)
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if _generation_payload(generation) != metadata.get("configured_generation_parameters"):
        raise ValueError("CEA-1.13 configured generation settings drifted.")
    if _generation_payload(effective) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.13 effective generation settings drifted.")
    edge_tasks = tuple(item.edge_filter_task for item in preflight.tasks)
    whole_metadata = dict(metadata)
    whole_metadata.update(
        {
            "prompt_path": str(WHOLE_PROMPT_PATH),
            "prompt_sha256": preflight.whole_prompt.sha256,
        }
    )
    part_metadata = dict(metadata)
    part_metadata.update(
        {
            "prompt_path": str(PART_PROMPT_PATH),
            "prompt_sha256": preflight.part_prompt.sha256,
        }
    )
    for repetition in (1, 2):
        cea14.execute_attachment_edge_filter_tasks(
            root=root,
            config=config,
            tasks=edge_tasks,
            output_directory=root / f"whole-r{repetition}",
            phase="development",
            metadata=whole_metadata,
            generation_parameters=generation,
            prompt_id=WHOLE_PROMPT_ID,
            task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
            effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
        )
        for part_number in (1, 2):
            selected = tuple(
                item.edge_filter_task
                for item in preflight.part_tasks
                if item.kind is AttachmentRemainderPartKind.SUBSTANTIVE
                and item.part_number == part_number
            )
            cea14.execute_attachment_edge_filter_tasks(
                root=root,
                config=config,
                tasks=selected,
                output_directory=root / f"part-r{repetition}" / f"part-{part_number}",
                phase="development",
                metadata=part_metadata,
                generation_parameters=generation,
                prompt_id=PART_PROMPT_ID,
                task_renderer_id=ATTACHMENT_REMAINDER_PART_RENDERER_ID,
                remainder_part_number=part_number,
                effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
            )
    whole_observations = tuple(
        _load_observation(
            root=root,
            path=root / f"whole-r{repetition}" / f"{task.edge_filter_task.task_id}.json",
            config=config,
            residual_task_id=task.id,
            part_task=None,
            repetition=repetition,
            expected_prompt_sha256=preflight.whole_prompt.sha256,
            expected_prompt_id=WHOLE_PROMPT_ID,
            expected_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
            generation=generation,
        )
        for task in preflight.tasks
        for repetition in (1, 2)
    )
    part_observations = tuple(
        _load_observation(
            root=root,
            path=(
                root
                / f"part-r{repetition}"
                / f"part-{part.part_number}"
                / f"{part.edge_filter_task.task_id}.json"
            ),
            config=config,
            residual_task_id=part.residual_task_id,
            part_task=part,
            repetition=repetition,
            expected_prompt_sha256=preflight.part_prompt.sha256,
            expected_prompt_id=PART_PROMPT_ID,
            expected_renderer_id=ATTACHMENT_REMAINDER_PART_RENDERER_ID,
            generation=generation,
        )
        for part in preflight.part_tasks
        if part.kind is AttachmentRemainderPartKind.SUBSTANTIVE
        for repetition in (1, 2)
    )
    identities = {item.model_identity_digest for item in (*whole_observations, *part_observations)}
    if len(identities) != 1:
        raise ValueError("CEA-1.13 executions used more than one model identity.")
    execution_paths = tuple(
        Path(item.execution_record.path) for item in (*whole_observations, *part_observations)
    )
    report_inputs = tuple(
        sorted(
            (
                _file_reference("preflight", root / "preflight.json"),
                *(
                    _file_reference(f"execution_{index:02d}", path)
                    for index, path in enumerate(execution_paths, start=1)
                ),
            ),
            key=lambda item: item.label,
        )
    )
    report = build_partwise_report(
        preflight=preflight,
        inputs=report_inputs,
        whole_observations=whole_observations,
        part_observations=part_observations,
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_partwise_review(report), encoding="utf-8")
    package_files = tuple(
        sorted(
            (
                _file_reference("report", report_path),
                _file_reference("review", review_path),
                *preflight.inputs,
                preflight.whole_prompt,
                preflight.part_prompt,
                *report_inputs,
            ),
            key=lambda item: item.label,
        )
    )
    handoff_path.write_text(
        render_partwise_handoff(
            report,
            whole_prompt_text=WHOLE_PROMPT_PATH.read_text(encoding="utf-8"),
            part_prompt_text=PART_PROMPT_PATH.read_text(encoding="utf-8"),
            package_files=package_files,
            source_repository_url="https://github.com/SQLCODE917/KoteKomi",
            source_revision=_git_revision(),
        ),
        encoding="utf-8",
    )
    metadata.update(
        {
            "status": "complete",
            "report_fingerprint": report.result_fingerprint,
            "report_file_sha256": _file_sha(report_path),
            "review_file_sha256": _file_sha(review_path),
            "handoff_file_sha256": _file_sha(handoff_path),
            "proposed_change_count": 0,
            "accepted_ledger_change_count": 0,
        }
    )
    _write_json(root / "run.json", metadata)
    status = _status(root, AttachmentPartwisePackageStatus.COMPLETE, report=report)
    _write_json(root / "status.json", status.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "handoff": str(handoff_path),
                "outcome": report.outcome.value,
                "report": str(report_path),
                "review": str(review_path),
                "run_root": str(root),
                "second_opinion_review": str(root / "claude-opus-review.md"),
                "status": "complete",
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
    residual_task_id: str,
    part_task: AttachmentRemainderPartTask | None,
    repetition: int,
    expected_prompt_sha256: str,
    expected_prompt_id: str,
    expected_renderer_id: str,
    generation: tuple[ExecutionSetting, ...],
) -> AttachmentPartwiseObservation:
    task = (
        part_task.edge_filter_task
        if part_task is not None
        else _task_by_residual_id(
            root,
            residual_task_id,
        )
    )
    decision, value = cea14.validate_attachment_edge_filter_execution_record(
        path,
        task,
        archive=_initialized_archive(root / "archive"),
        expected_prompt_sha256=expected_prompt_sha256,
        expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
        expected_prompt_id=expected_prompt_id,
        expected_task_renderer_id=expected_renderer_id,
        expected_remainder_part_number=(part_task.part_number if part_task is not None else None),
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
    model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if model_run.generation_parameters != _generation_payload(effective):
        raise ValueError(f"CEA-1.13 execution generation settings drifted: {path}.")
    exact_input = trace.input.get("exact_model_input")
    raw_output = trace.output.get("raw_output_text")
    if not isinstance(exact_input, str) or not exact_input:
        raise ValueError(f"CEA-1.13 execution lacks exact model input: {path}.")
    if raw_output is not None and not isinstance(raw_output, str):
        raise ValueError(f"CEA-1.13 raw output text has invalid shape: {path}.")
    if "expected_answer" in exact_input:
        raise ValueError("CEA-1.13 model input exposes Gold.")
    receipt = (
        model_execution_receipt_from_payload(model_run.execution_receipt)
        if model_run.execution_receipt is not None
        else None
    )
    output_count = receipt.output_token_count if receipt is not None else None
    positions = (
        tuple(item.position for item in receipt.output_token_probabilities)
        if receipt is not None
        else ()
    )
    identity = _admitted_model_identity_digest(model_run)
    if receipt is not None and receipt.model_identity_digest != identity:
        raise ValueError("CEA-1.13 receipt and admission model identities differ.")
    strict = (
        raw_output in {"Y", "N", "U"}
        and decision.answer is not None
        and decision.answer.value == raw_output
        and output_count == 1
        and positions == (0,)
    )
    return AttachmentPartwiseObservation(
        arm=(AttachmentPartwiseArm.PART if part_task is not None else AttachmentPartwiseArm.WHOLE),
        repetition=cast(Any, repetition),
        residual_task_id=residual_task_id,
        part_task_id=part_task.id if part_task is not None else None,
        edge_id=task.edge.id,
        decision=decision,
        execution_record=_file_reference(
            _observation_label(
                repetition=repetition,
                residual_task_id=residual_task_id,
                part_task=part_task,
            ),
            path,
        ),
        exact_model_input=exact_input,
        raw_output_text=raw_output,
        model_identity_digest=identity,
        model_run_status=model_run.status,
        output_token_count=output_count,
        probability_positions=positions,
        elapsed_milliseconds=_elapsed_milliseconds(model_run),
        strict_finite_answer=strict,
    )


def _task_by_residual_id(root: Path, residual_task_id: str):
    preflight = AttachmentPartwisePreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    return next(item.edge_filter_task for item in preflight.tasks if item.id == residual_task_id)


def _observation_label(
    *,
    repetition: int,
    residual_task_id: str,
    part_task: AttachmentRemainderPartTask | None,
) -> str:
    identifier = part_task.id if part_task is not None else residual_task_id
    arm = "part" if part_task is not None else "whole"
    return f"{arm}_{repetition}_{identifier}"


def _load_calibrated_package(
    root: Path,
) -> tuple[
    dict[str, Any], AttachmentCalibratedTerminationPreflight, AttachmentCalibratedTerminationReport
]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.13 requires a complete CEA-1.12 package.")
    _validate_package_digests(root, metadata)
    claude_review = root / "claude-opus-review.md"
    if not claude_review.is_file() or not claude_review.read_bytes():
        raise ValueError("CEA-1.13 requires the completed CEA-1.12 Claude review.")
    preflight = AttachmentCalibratedTerminationPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentCalibratedTerminationReport.model_validate_json(
        (root / "report.json").read_bytes()
    )
    source_revision = _source_revision_from_handoff(root / "second-opinion-handoff.md")
    for reference in (*preflight.inputs, preflight.bare_prompt):
        _validate_sealed_reference(reference, source_revision=source_revision)
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.12 preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.12 report fingerprint changed.")
    return metadata, preflight, report


def _source_revision_from_handoff(path: Path) -> str:
    matches = re.findall(r"^Source revision: `([a-f0-9]{40})`$", path.read_text(), re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("CEA-1.12 handoff requires one full source revision.")
    return matches[0]


def _validate_sealed_reference(
    reference: AttachmentEvidenceReference,
    *,
    source_revision: str,
) -> None:
    path = Path(reference.path)
    if path.is_file() and _file_sha(path) == reference.sha256:
        return
    try:
        repository_path = path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError as error:
        raise ValueError(f"CEA-1.12 sealed input drifted: {reference.label}.") from error
    result = subprocess.run(
        ["git", "show", f"{source_revision}:{repository_path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    if hashlib.sha256(result.stdout).hexdigest() != reference.sha256:
        raise ValueError(f"CEA-1.12 historical source input drifted: {reference.label}.")


def _status(
    root: Path,
    status: AttachmentPartwisePackageStatus,
    *,
    report: AttachmentPartwiseReport | None = None,
) -> AttachmentPartwiseStatus:
    complete = status is AttachmentPartwisePackageStatus.COMPLETE
    return AttachmentPartwiseStatus(
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
        ExecutionSetting("frequency_penalty", 0.0),
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", TOP_LOGPROBS),
    )
    if tuple(sorted(settings, key=lambda item: item.key)) != settings:
        raise ValueError("CEA-1.13 generation settings are not canonically ordered.")
    return settings


def _generation_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    expected = cea14.attachment_edge_filter_runtime_contract(config)
    if expected != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.13 configured runtime differs from sealed evidence.")


def _validate_package_digests(root: Path, metadata: dict[str, Any]) -> None:
    for key, filename in (
        ("preflight_file_sha256", "preflight.json"),
        ("report_file_sha256", "report.json"),
        ("review_file_sha256", "comparison-review.md"),
        ("handoff_file_sha256", "second-opinion-handoff.md"),
    ):
        if metadata.get(key) != _file_sha(root / filename):
            raise ValueError(f"CEA-1.12 package digest drifted: {filename}.")


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or _file_sha(path) != reference.sha256:
        raise ValueError(f"CEA-1.13 direct input drifted: {reference.label}.")


def _admitted_model_identity_digest(model_run: ModelRun) -> str:
    admission = model_run.input_admission
    if admission is None or admission.status.value != "ready":
        raise ValueError("CEA-1.13 ModelRun lacks an admitted model identity.")
    return admission.model_identity_digest


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if type(value) is not int or value < 0:
        raise ValueError("CEA-1.13 ModelRun lacks valid elapsed milliseconds.")
    return value


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _initialized_archive(path: Path) -> LocalArchiveStore:
    archive = LocalArchiveStore(path)
    archive.initialize()
    return archive


def _file_reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.13 evidence file is missing: {resolved}.")
    return AttachmentEvidenceReference(label=label, path=str(resolved), sha256=_file_sha(resolved))


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json(value) + b"\n")


def _required_str(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"CEA-1.13 metadata requires {key}.")
    return item


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
