#!/usr/bin/env python3
"""Run the CEA-1.14 Candidate marker boundary ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    AttachmentCandidateMarkerArm,
    AttachmentCandidateMarkerObservation,
    AttachmentCandidateMarkerPackageStatus,
    AttachmentCandidateMarkerPreflight,
    AttachmentCandidateMarkerReport,
    AttachmentCandidateMarkerStatus,
    AttachmentCandidateMarkerView,
    AttachmentEvidenceReference,
    AttachmentPartwisePreflight,
    AttachmentPartwiseReport,
    ExecutionSetting,
    ExtractionStageTrace,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_candidate_marker_boundary import (
    build_candidate_marker_preflight,
    build_candidate_marker_report,
    render_candidate_marker_handoff,
    render_candidate_marker_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = (
    REPOSITORY_ROOT / "docs/2026-09-21-competitive-attachment-candidate-marker-boundary-ablation.md"
)
PROMPT_PATH = (
    REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_format_bare_v1.md"
)
PROMPT_ID = "competitive_attachment_residual_ownership_format_bare_v1"
REQUESTED_OUTPUT_LIMIT = 2
TOP_LOGPROBS = 10


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--partwise-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.14 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    partwise_root = args.partwise_root.resolve()
    config = _config(args.config)
    partwise_metadata, partwise_preflight, partwise_report = _load_partwise_package(partwise_root)
    _validate_runtime(config, partwise_metadata)
    prompt = _file_reference("whole_prompt", PROMPT_PATH)
    if prompt.sha256 != partwise_preflight.whole_prompt.sha256:
        raise ValueError("CEA-1.14 Whole Arm Prompt differs from CEA-1.13.")
    inputs = tuple(
        sorted(
            (
                _file_reference("partwise_claude_review", partwise_root / "claude-opus-review.md"),
                _file_reference("partwise_handoff", partwise_root / "second-opinion-handoff.md"),
                _file_reference("partwise_preflight", partwise_root / "preflight.json"),
                _file_reference("partwise_report", partwise_root / "report.json"),
                _file_reference("partwise_review", partwise_root / "comparison-review.md"),
                _file_reference("partwise_run", partwise_root / "run.json"),
                _file_reference("partwise_status", partwise_root / "status.json"),
                _file_reference("tdd", TDD_PATH),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_candidate_marker_preflight(
        inputs=inputs,
        prompt=prompt,
        predecessor=partwise_report,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    metadata = {
        "schema_version": "attachment_candidate_marker_run_v1",
        "status": "prepared",
        "config_path": str(args.config.resolve()),
        "partwise_root": str(partwise_root),
        "development_run_root": _required_str(partwise_metadata, "development_run_root"),
        "runtime_contract": partwise_metadata["runtime_contract"],
        "runtime_contract_sha256": _sha_json(partwise_metadata["runtime_contract"]),
        "prompt_path": str(PROMPT_PATH),
        "prompt_sha256": prompt.sha256,
        "prompt_id": PROMPT_ID,
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
    _write_json(
        root / "marker-views.json", [item.model_dump(mode="json") for item in preflight.views]
    )
    metadata["preflight_fingerprint"] = preflight.result_fingerprint
    metadata["preflight_file_sha256"] = _file_sha(preflight_path)
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        _status(root, AttachmentCandidateMarkerPackageStatus.PREPARED).model_dump(mode="json"),
    )
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
        raise ValueError("CEA-1.14 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentCandidateMarkerPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.14 preflight fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.14 preflight file digest drifted.")
    for reference in (*preflight.inputs, preflight.prompt):
        _validate_reference(reference)
    generation = _configured_generation(config)
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if _generation_payload(generation) != metadata.get("configured_generation_parameters"):
        raise ValueError("CEA-1.14 configured generation settings drifted.")
    if _generation_payload(effective) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.14 effective generation settings drifted.")
    for arm in AttachmentCandidateMarkerArm:
        views = tuple(item for item in preflight.views if item.arm is arm)
        tasks = tuple(item.rendered_task.edge_filter_task for item in views)
        for repetition in (1, 2):
            cea14.execute_attachment_edge_filter_tasks(
                root=root,
                config=config,
                tasks=tasks,
                output_directory=root / f"{arm.value}-r{repetition}",
                phase="development",
                metadata=metadata,
                generation_parameters=generation,
                prompt_id=PROMPT_ID,
                task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
                effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
            )
    observations = tuple(
        _load_observation(
            root=root,
            path=(
                root
                / f"{view.arm.value}-r{repetition}"
                / f"{view.rendered_task.edge_filter_task.task_id}.json"
            ),
            config=config,
            view=view,
            repetition=repetition,
            expected_prompt_sha256=preflight.prompt.sha256,
            generation=generation,
        )
        for view in preflight.views
        for repetition in (1, 2)
    )
    identities = {item.model_identity_digest for item in observations}
    if identities != {preflight.expected_model_identity_digest}:
        raise ValueError("CEA-1.14 executions used a foreign model identity.")
    execution_paths = tuple(Path(item.execution_record.path) for item in observations)
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
    report = build_candidate_marker_report(
        preflight=preflight,
        inputs=report_inputs,
        observations=observations,
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_candidate_marker_review(report), encoding="utf-8")
    package_files = tuple(
        sorted(
            (
                _file_reference("report", report_path),
                _file_reference("review", review_path),
                *preflight.inputs,
                preflight.prompt,
                *report_inputs,
            ),
            key=lambda item: item.label,
        )
    )
    handoff_path.write_text(
        render_candidate_marker_handoff(
            report,
            prompt_text=PROMPT_PATH.read_text(encoding="utf-8"),
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
    _write_json(
        root / "status.json",
        _status(
            root,
            AttachmentCandidateMarkerPackageStatus.COMPLETE,
            report=report,
        ).model_dump(mode="json"),
    )
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
    view: AttachmentCandidateMarkerView,
    repetition: int,
    expected_prompt_sha256: str,
    generation: tuple[ExecutionSetting, ...],
) -> AttachmentCandidateMarkerObservation:
    task = view.rendered_task.edge_filter_task
    decision, value = cea14.validate_attachment_edge_filter_execution_record(
        path,
        task,
        archive=_initialized_archive(root / "archive"),
        expected_prompt_sha256=expected_prompt_sha256,
        expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
        expected_prompt_id=PROMPT_ID,
        expected_task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
    model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if model_run.generation_parameters != _generation_payload(effective):
        raise ValueError(f"CEA-1.14 execution generation settings drifted: {path}.")
    exact_input = trace.input.get("exact_model_input")
    raw_output = trace.output.get("raw_output_text")
    if not isinstance(exact_input, str) or not exact_input:
        raise ValueError(f"CEA-1.14 execution lacks exact model input: {path}.")
    if raw_output is not None and not isinstance(raw_output, str):
        raise ValueError(f"CEA-1.14 raw output text has invalid shape: {path}.")
    if "expected_answer" in exact_input:
        raise ValueError("CEA-1.14 model input exposes Gold.")
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
        raise ValueError("CEA-1.14 receipt and admission model identities differ.")
    strict = (
        raw_output in {"Y", "N", "U"}
        and decision.answer is not None
        and decision.answer.value == raw_output
        and output_count == 1
        and positions == (0,)
    )
    return AttachmentCandidateMarkerObservation(
        arm=view.arm,
        repetition=cast(Any, repetition),
        view_id=view.id,
        authoritative_task_id=view.authoritative_task.id,
        rendered_task_id=view.rendered_task.id,
        decision=decision,
        execution_record=_file_reference(
            f"{view.arm.value}_{repetition}_{view.id}",
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


def _load_partwise_package(
    root: Path,
) -> tuple[dict[str, Any], AttachmentPartwisePreflight, AttachmentPartwiseReport]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.14 requires a complete CEA-1.13 package.")
    checks = {
        "preflight_file_sha256": root / "preflight.json",
        "report_file_sha256": root / "report.json",
        "review_file_sha256": root / "comparison-review.md",
        "handoff_file_sha256": root / "second-opinion-handoff.md",
    }
    for key, path in checks.items():
        if _file_sha(path) != metadata.get(key):
            raise ValueError(f"CEA-1.13 package digest drifted: {key}.")
    claude_review = root / "claude-opus-review.md"
    if not claude_review.is_file() or not claude_review.read_bytes():
        raise ValueError("CEA-1.14 requires the completed CEA-1.13 independent review.")
    preflight = AttachmentPartwisePreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentPartwiseReport.model_validate_json((root / "report.json").read_bytes())
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.13 preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.13 report fingerprint changed.")
    source_revision = _source_revision_from_handoff(root / "second-opinion-handoff.md")
    for reference in (*preflight.inputs, preflight.whole_prompt, preflight.part_prompt):
        _validate_sealed_reference(reference, source_revision=source_revision)
    return metadata, preflight, report


def _source_revision_from_handoff(path: Path) -> str:
    matches = re.findall(r"^Source revision: `([a-f0-9]{40})`$", path.read_text(), re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("CEA-1.13 handoff requires one full source revision.")
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
        raise ValueError(f"CEA-1.13 sealed input drifted: {reference.label}.") from error
    result = subprocess.run(
        ["git", "show", f"{source_revision}:{repository_path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    if hashlib.sha256(result.stdout).hexdigest() != reference.sha256:
        raise ValueError(f"CEA-1.13 historical source input drifted: {reference.label}.")


def _status(
    root: Path,
    status: AttachmentCandidateMarkerPackageStatus,
    *,
    report: AttachmentCandidateMarkerReport | None = None,
) -> AttachmentCandidateMarkerStatus:
    complete = status is AttachmentCandidateMarkerPackageStatus.COMPLETE
    return AttachmentCandidateMarkerStatus(
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
    return (
        ExecutionSetting(key="frequency_penalty", value=0.0),
        ExecutionSetting(
            key="max_output_tokens",
            value=config.model_execution.max_output_tokens,
        ),
        ExecutionSetting(key="seed", value=17),
        ExecutionSetting(key="temperature", value=0),
        ExecutionSetting(key="top_logprobs", value=TOP_LOGPROBS),
    )


def _generation_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    if cea14.attachment_edge_filter_runtime_contract(config) != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.14 runtime contract drifted.")


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or _file_sha(path) != reference.sha256:
        raise ValueError(f"CEA-1.14 input drifted: {reference.label}.")


def _admitted_model_identity_digest(model_run: ModelRun) -> str:
    admission = model_run.input_admission
    if admission is None or admission.status.value != "ready":
        raise ValueError("CEA-1.14 ModelRun lacks an admitted model identity.")
    return admission.model_identity_digest


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("CEA-1.14 ModelRun lacks elapsed milliseconds.")
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
    return AttachmentEvidenceReference(
        label=label,
        path=str(path.resolve()),
        sha256=_file_sha(path),
    )


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_canonical_json(value) + b"\n")


def _required_str(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"CEA-1.14 metadata requires {key}.")
    return result


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
