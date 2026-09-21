#!/usr/bin/env python3
"""Run the CEA-1.15 Remainder enumeration isolation experiment."""

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
    ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID,
    AttachmentCandidateMarkerPreflight,
    AttachmentCandidateMarkerReport,
    AttachmentEvidenceReference,
    AttachmentRemainderEnumerationObservation,
    AttachmentRemainderEnumerationPackageStatus,
    AttachmentRemainderEnumerationPreflight,
    AttachmentRemainderEnumerationReport,
    AttachmentRemainderEnumerationStatus,
    AttachmentRemainderEnumerationView,
    ExecutionSetting,
    ExtractionStageTrace,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_remainder_enumeration_isolation import (
    build_remainder_enumeration_preflight,
    build_remainder_enumeration_report,
    render_remainder_enumeration_handoff,
    render_remainder_enumeration_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = (
    REPOSITORY_ROOT / "docs/2026-09-21-competitive-attachment-remainder-enumeration-isolation.md"
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
    prepare.add_argument("--marker-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.15 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    marker_root = args.marker_root.resolve()
    config = _config(args.config)
    marker_metadata, marker_preflight, marker_report = _load_marker_package(marker_root)
    _validate_runtime(config, marker_metadata)
    prompt = _file_reference("whole_prompt", PROMPT_PATH)
    if prompt.sha256 != marker_preflight.prompt.sha256:
        raise ValueError("CEA-1.15 prompt differs from CEA-1.14.")
    inputs = tuple(
        sorted(
            (
                _file_reference("marker_claude_review", marker_root / "claude-opus-review.md"),
                _file_reference("marker_handoff", marker_root / "second-opinion-handoff.md"),
                _file_reference("marker_preflight", marker_root / "preflight.json"),
                _file_reference("marker_report", marker_root / "report.json"),
                _file_reference("marker_review", marker_root / "comparison-review.md"),
                _file_reference("marker_run", marker_root / "run.json"),
                _file_reference("marker_status", marker_root / "status.json"),
                _file_reference("tdd", TDD_PATH),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_remainder_enumeration_preflight(
        inputs=inputs,
        prompt=prompt,
        predecessor=marker_report,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    metadata = {
        "schema_version": "attachment_remainder_enumeration_run_v1",
        "status": "prepared",
        "config_path": str(args.config.resolve()),
        "marker_root": str(marker_root),
        "development_run_root": _required_str(marker_metadata, "development_run_root"),
        "runtime_contract": marker_metadata["runtime_contract"],
        "runtime_contract_sha256": _sha_json(marker_metadata["runtime_contract"]),
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
        root / "enumeration-views.json",
        [item.model_dump(mode="json") for item in preflight.views],
    )
    metadata["preflight_fingerprint"] = preflight.result_fingerprint
    metadata["preflight_file_sha256"] = _file_sha(preflight_path)
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        _status(
            root,
            AttachmentRemainderEnumerationPackageStatus.PREPARED,
        ).model_dump(mode="json"),
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
        raise ValueError("CEA-1.15 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentRemainderEnumerationPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.15 preflight fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.15 preflight file digest drifted.")
    for reference in (*preflight.inputs, preflight.prompt):
        _validate_reference(reference)
    generation = _configured_generation(config)
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if _generation_payload(generation) != metadata.get("configured_generation_parameters"):
        raise ValueError("CEA-1.15 configured generation settings drifted.")
    if _generation_payload(effective) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.15 effective generation settings drifted.")
    tasks = tuple(item.authoritative_task.edge_filter_task for item in preflight.views)
    for repetition in (1, 2):
        cea14.execute_attachment_edge_filter_tasks(
            root=root,
            config=config,
            tasks=tasks,
            output_directory=root / f"filtered-r{repetition}",
            phase="development",
            metadata=metadata,
            generation_parameters=generation,
            prompt_id=PROMPT_ID,
            task_renderer_id=ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID,
            effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
        )
    observations = tuple(
        _load_observation(
            root=root,
            path=root
            / f"filtered-r{repetition}"
            / f"{view.authoritative_task.edge_filter_task.task_id}.json",
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
        raise ValueError("CEA-1.15 executions used a foreign model identity.")
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
    report = build_remainder_enumeration_report(
        preflight=preflight,
        inputs=report_inputs,
        observations=observations,
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_remainder_enumeration_review(report), encoding="utf-8")
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
        render_remainder_enumeration_handoff(
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
            AttachmentRemainderEnumerationPackageStatus.COMPLETE,
            report=report,
        ).model_dump(mode="json"),
    )
    print(
        json.dumps(
            {
                "handoff": str(handoff_path),
                "mechanism": report.mechanism.value,
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
    view: AttachmentRemainderEnumerationView,
    repetition: Literal[1, 2],
    expected_prompt_sha256: str,
    generation: tuple[ExecutionSetting, ...],
) -> AttachmentRemainderEnumerationObservation:
    task = view.authoritative_task.edge_filter_task
    decision, value = cea14.validate_attachment_edge_filter_execution_record(
        path,
        task,
        archive=_initialized_archive(root / "archive"),
        expected_prompt_sha256=expected_prompt_sha256,
        expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
        expected_prompt_id=PROMPT_ID,
        expected_task_renderer_id=ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID,
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
    model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if model_run.generation_parameters != _generation_payload(effective):
        raise ValueError(f"CEA-1.15 execution generation settings drifted: {path}.")
    exact_input = trace.input.get("exact_model_input")
    raw_output = trace.output.get("raw_output_text")
    if not isinstance(exact_input, str) or not exact_input:
        raise ValueError(f"CEA-1.15 execution lacks exact model input: {path}.")
    if raw_output is not None and not isinstance(raw_output, str):
        raise ValueError(f"CEA-1.15 raw output text has invalid shape: {path}.")
    if any(term in exact_input.casefold() for term in ("expected_answer", "gold", "baseline")):
        raise ValueError("CEA-1.15 model input exposes evaluation evidence.")
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
        raise ValueError("CEA-1.15 receipt and admission model identities differ.")
    strict = (
        raw_output in {"Y", "N", "U"}
        and decision.answer is not None
        and decision.answer.value == raw_output
        and output_count == 1
        and positions == (0,)
    )
    return AttachmentRemainderEnumerationObservation(
        repetition=repetition,
        view_id=view.id,
        authoritative_task_id=view.authoritative_task.id,
        decision=decision,
        execution_record=_file_reference(f"filtered_{repetition}_{view.id}", path),
        exact_model_input=exact_input,
        raw_output_text=raw_output,
        model_identity_digest=identity,
        model_run_status=model_run.status,
        output_token_count=output_count,
        probability_positions=positions,
        elapsed_milliseconds=_elapsed_milliseconds(model_run),
        strict_finite_answer=strict,
    )


def _load_marker_package(
    root: Path,
) -> tuple[dict[str, Any], AttachmentCandidateMarkerPreflight, AttachmentCandidateMarkerReport]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.15 requires a complete CEA-1.14 package.")
    checks = {
        "preflight_file_sha256": root / "preflight.json",
        "report_file_sha256": root / "report.json",
        "review_file_sha256": root / "comparison-review.md",
        "handoff_file_sha256": root / "second-opinion-handoff.md",
    }
    for key, path in checks.items():
        if _file_sha(path) != metadata.get(key):
            raise ValueError(f"CEA-1.14 package digest drifted: {key}.")
    claude_review = root / "claude-opus-review.md"
    if not claude_review.is_file() or not claude_review.read_bytes():
        raise ValueError("CEA-1.15 requires the completed CEA-1.14 independent review.")
    preflight = AttachmentCandidateMarkerPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentCandidateMarkerReport.model_validate_json(
        (root / "report.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.14 preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.14 report fingerprint changed.")
    source_revision = _source_revision_from_handoff(root / "second-opinion-handoff.md")
    for reference in (*preflight.inputs, preflight.prompt):
        _validate_sealed_reference(reference, source_revision=source_revision)
    return metadata, preflight, report


def _source_revision_from_handoff(path: Path) -> str:
    matches = re.findall(r"^Source revision: `([a-f0-9]{40})`$", path.read_text(), re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("CEA-1.14 handoff requires one full source revision.")
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
        raise ValueError(f"CEA-1.14 sealed input drifted: {reference.label}.") from error
    result = subprocess.run(
        ["git", "show", f"{source_revision}:{repository_path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    if hashlib.sha256(result.stdout).hexdigest() != reference.sha256:
        raise ValueError(f"CEA-1.14 historical source input drifted: {reference.label}.")


def _status(
    root: Path,
    status: AttachmentRemainderEnumerationPackageStatus,
    *,
    report: AttachmentRemainderEnumerationReport | None = None,
) -> AttachmentRemainderEnumerationStatus:
    complete = status is AttachmentRemainderEnumerationPackageStatus.COMPLETE
    return AttachmentRemainderEnumerationStatus(
        status=status,
        run_root=str(root),
        preflight_path=str(root / "preflight.json"),
        report_path=str(root / "report.json") if complete else None,
        review_path=str(root / "comparison-review.md") if complete else None,
        handoff_path=str(root / "second-opinion-handoff.md") if complete else None,
        claude_review_path=str(root / "claude-opus-review.md") if complete else None,
        outcome=report.outcome if report is not None else None,
        mechanism=report.mechanism if report is not None else None,
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
        raise ValueError("CEA-1.15 runtime contract drifted.")


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or _file_sha(path) != reference.sha256:
        raise ValueError(f"CEA-1.15 input drifted: {reference.label}.")


def _admitted_model_identity_digest(model_run: ModelRun) -> str:
    admission = model_run.input_admission
    if admission is None or admission.status.value != "ready":
        raise ValueError("CEA-1.15 ModelRun lacks an admitted model identity.")
    return admission.model_identity_digest


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if type(value) is not int or value < 0:
        raise ValueError("CEA-1.15 ModelRun lacks elapsed milliseconds.")
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
        raise ValueError(f"CEA-1.15 evidence file is missing: {resolved}.")
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_file_sha(resolved),
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
        raise ValueError(f"CEA-1.15 metadata requires {key}.")
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
