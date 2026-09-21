#!/usr/bin/env python3
"""Run the CEA-1.16 Remainder cardinality ablation."""

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
    ATTACHMENT_SPLIT_REMAINDER_RENDERER_ID,
    AttachmentEvidenceReference,
    AttachmentRemainderCardinalityObservation,
    AttachmentRemainderCardinalityPackageStatus,
    AttachmentRemainderCardinalityPreflight,
    AttachmentRemainderCardinalityReport,
    AttachmentRemainderCardinalityStatus,
    AttachmentRemainderEnumerationPreflight,
    AttachmentRemainderEnumerationReport,
    ExecutionSetting,
    ExtractionStageTrace,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_finite_answer_format import (
    finite_label_evidence,
)
from kotekomi_pipelines.competitive_attachment_remainder_cardinality_ablation import (
    build_remainder_cardinality_preflight,
    build_remainder_cardinality_report,
    render_remainder_cardinality_handoff,
    render_remainder_cardinality_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = (
    REPOSITORY_ROOT / "docs/2026-09-21-competitive-attachment-remainder-cardinality-ablation.md"
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
    prepare.add_argument("--enumeration-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.16 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    predecessor_root = args.enumeration_root.resolve()
    config = _config(args.config)
    predecessor_metadata, predecessor_preflight, predecessor_report = _load_predecessor_package(
        predecessor_root
    )
    _validate_runtime(config, predecessor_metadata)
    prompt = _file_reference("whole_prompt", PROMPT_PATH)
    if prompt.sha256 != predecessor_preflight.prompt.sha256:
        raise ValueError("CEA-1.16 prompt differs from CEA-1.15.")
    inputs = tuple(
        sorted(
            (
                _file_reference(
                    "enumeration_claude_review",
                    predecessor_root / "claude-opus-review.md",
                ),
                _file_reference(
                    "enumeration_handoff",
                    predecessor_root / "second-opinion-handoff.md",
                ),
                _file_reference("enumeration_preflight", predecessor_root / "preflight.json"),
                _file_reference("enumeration_report", predecessor_root / "report.json"),
                _file_reference(
                    "enumeration_review",
                    predecessor_root / "comparison-review.md",
                ),
                _file_reference("enumeration_run", predecessor_root / "run.json"),
                _file_reference("enumeration_status", predecessor_root / "status.json"),
                _file_reference("tdd", TDD_PATH),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_remainder_cardinality_preflight(
        inputs=inputs,
        prompt=prompt,
        predecessor=predecessor_report,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    metadata = {
        "schema_version": "attachment_remainder_cardinality_run_v1",
        "status": "prepared",
        "config_path": str(args.config.resolve()),
        "enumeration_root": str(predecessor_root),
        "development_run_root": _required_str(
            predecessor_metadata,
            "development_run_root",
        ),
        "runtime_contract": predecessor_metadata["runtime_contract"],
        "runtime_contract_sha256": _sha_json(predecessor_metadata["runtime_contract"]),
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
    _write_json(root / "split-view.json", preflight.view.model_dump(mode="json"))
    metadata["preflight_fingerprint"] = preflight.result_fingerprint
    metadata["preflight_file_sha256"] = _file_sha(preflight_path)
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        _status(
            root,
            AttachmentRemainderCardinalityPackageStatus.PREPARED,
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
        raise ValueError("CEA-1.16 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentRemainderCardinalityPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.16 preflight fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.16 preflight file digest drifted.")
    for reference in (*preflight.inputs, preflight.prompt):
        _validate_reference(reference)
    generation = _configured_generation(config)
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if _generation_payload(generation) != metadata.get("configured_generation_parameters"):
        raise ValueError("CEA-1.16 configured generation settings drifted.")
    if _generation_payload(effective) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.16 effective generation settings drifted.")
    task = preflight.view.predecessor_view.authoritative_task.edge_filter_task
    output_directory = root / "split"
    cea14.execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=(task,),
        output_directory=output_directory,
        phase="development",
        metadata=metadata,
        generation_parameters=generation,
        prompt_id=PROMPT_ID,
        task_renderer_id=ATTACHMENT_SPLIT_REMAINDER_RENDERER_ID,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    execution_path = output_directory / f"{task.task_id}.json"
    observation = _load_observation(
        root=root,
        path=execution_path,
        config=config,
        preflight=preflight,
        expected_prompt_sha256=preflight.prompt.sha256,
        generation=generation,
    )
    if observation.model_identity_digest != preflight.expected_model_identity_digest:
        raise ValueError("CEA-1.16 execution used a foreign model identity.")
    report_inputs = (
        _file_reference("execution", execution_path),
        _file_reference("preflight", root / "preflight.json"),
    )
    report = build_remainder_cardinality_report(
        preflight=preflight,
        inputs=report_inputs,
        observation=observation,
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_remainder_cardinality_review(report), encoding="utf-8")
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
        render_remainder_cardinality_handoff(
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
            AttachmentRemainderCardinalityPackageStatus.COMPLETE,
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
    preflight: AttachmentRemainderCardinalityPreflight,
    expected_prompt_sha256: str,
    generation: tuple[ExecutionSetting, ...],
) -> AttachmentRemainderCardinalityObservation:
    task = preflight.view.predecessor_view.authoritative_task.edge_filter_task
    decision, value = cea14.validate_attachment_edge_filter_execution_record(
        path,
        task,
        archive=_initialized_archive(root / "archive"),
        expected_prompt_sha256=expected_prompt_sha256,
        expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
        expected_prompt_id=PROMPT_ID,
        expected_task_renderer_id=ATTACHMENT_SPLIT_REMAINDER_RENDERER_ID,
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
    model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
    effective = attachment_edge_filter_generation_parameters(
        generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if model_run.generation_parameters != _generation_payload(effective):
        raise ValueError("CEA-1.16 execution generation settings drifted.")
    exact_input = trace.input.get("exact_model_input")
    raw_output = trace.output.get("raw_output_text")
    if not isinstance(exact_input, str) or not exact_input:
        raise ValueError("CEA-1.16 execution lacks exact model input.")
    if raw_output is not None and not isinstance(raw_output, str):
        raise ValueError("CEA-1.16 raw output text has invalid shape.")
    if any(term in exact_input.casefold() for term in ("expected_answer", "gold", "baseline")):
        raise ValueError("CEA-1.16 model input exposes evaluation evidence.")
    receipt = (
        model_execution_receipt_from_payload(model_run.execution_receipt)
        if model_run.execution_receipt is not None
        else None
    )
    evidence = finite_label_evidence(receipt) if receipt is not None else None
    output_count = receipt.output_token_count if receipt is not None else None
    identity = _admitted_model_identity_digest(model_run)
    if receipt is not None and receipt.model_identity_digest != identity:
        raise ValueError("CEA-1.16 receipt and admission model identities differ.")
    strict = (
        raw_output in {"Y", "N", "U"}
        and decision.answer is not None
        and decision.answer.value == raw_output
        and output_count == 1
        and evidence is not None
    )
    return AttachmentRemainderCardinalityObservation(
        view_id=preflight.view.id,
        authoritative_task_id=preflight.view.predecessor_view.authoritative_task.id,
        decision=decision,
        execution_record=_file_reference("split_execution", path),
        exact_model_input=exact_input,
        raw_output_text=raw_output,
        finite_label_evidence=evidence,
        model_identity_digest=identity,
        model_run_status=model_run.status,
        output_token_count=output_count,
        elapsed_milliseconds=_elapsed_milliseconds(model_run),
        strict_finite_answer=strict,
    )


def _load_predecessor_package(
    root: Path,
) -> tuple[
    dict[str, Any],
    AttachmentRemainderEnumerationPreflight,
    AttachmentRemainderEnumerationReport,
]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.16 requires a complete CEA-1.15 package.")
    checks = {
        "preflight_file_sha256": root / "preflight.json",
        "report_file_sha256": root / "report.json",
        "review_file_sha256": root / "comparison-review.md",
        "handoff_file_sha256": root / "second-opinion-handoff.md",
    }
    for key, path in checks.items():
        if _file_sha(path) != metadata.get(key):
            raise ValueError(f"CEA-1.15 package digest drifted: {key}.")
    claude_review = root / "claude-opus-review.md"
    if not claude_review.is_file() or not claude_review.read_bytes():
        raise ValueError("CEA-1.16 requires the completed CEA-1.15 independent review.")
    preflight = AttachmentRemainderEnumerationPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentRemainderEnumerationReport.model_validate_json(
        (root / "report.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.15 preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.15 report fingerprint changed.")
    source_revision = _source_revision_from_handoff(root / "second-opinion-handoff.md")
    for reference in (*preflight.inputs, preflight.prompt):
        _validate_sealed_reference(reference, source_revision=source_revision)
    return metadata, preflight, report


def _source_revision_from_handoff(path: Path) -> str:
    matches = re.findall(r"^Source revision: `([a-f0-9]{40})`$", path.read_text(), re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("CEA-1.15 handoff requires one full source revision.")
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
        raise ValueError(f"CEA-1.15 sealed input drifted: {reference.label}.") from error
    result = subprocess.run(
        ["git", "show", f"{source_revision}:{repository_path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    if hashlib.sha256(result.stdout).hexdigest() != reference.sha256:
        raise ValueError(f"CEA-1.15 historical source input drifted: {reference.label}.")


def _status(
    root: Path,
    status: AttachmentRemainderCardinalityPackageStatus,
    *,
    report: AttachmentRemainderCardinalityReport | None = None,
) -> AttachmentRemainderCardinalityStatus:
    complete = status is AttachmentRemainderCardinalityPackageStatus.COMPLETE
    return AttachmentRemainderCardinalityStatus(
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
        raise ValueError("CEA-1.16 runtime contract drifted.")


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or _file_sha(path) != reference.sha256:
        raise ValueError(f"CEA-1.16 input drifted: {reference.label}.")


def _admitted_model_identity_digest(model_run: ModelRun) -> str:
    admission = model_run.input_admission
    if admission is None or admission.status.value != "ready":
        raise ValueError("CEA-1.16 ModelRun lacks an admitted model identity.")
    return admission.model_identity_digest


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if type(value) is not int or value < 0:
        raise ValueError("CEA-1.16 ModelRun lacks elapsed milliseconds.")
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
        raise ValueError(f"CEA-1.16 evidence file is missing: {resolved}.")
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
        raise ValueError(f"CEA-1.16 metadata requires {key}.")
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
