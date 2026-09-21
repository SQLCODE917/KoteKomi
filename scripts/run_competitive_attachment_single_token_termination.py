#!/usr/bin/env python3
"""Run the CEA-1.11 single-token termination experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    AttachmentAnswerFormatPreflight,
    AttachmentAnswerFormatReport,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentFiniteLabelEvidence,
    AttachmentSingleTokenObservation,
    AttachmentSingleTokenPackageStatus,
    AttachmentSingleTokenPreflight,
    AttachmentSingleTokenReport,
    AttachmentSingleTokenStatus,
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
from kotekomi_pipelines.competitive_attachment_single_token_termination import (
    build_single_token_preflight,
    build_single_token_report,
    render_single_token_handoff,
    render_single_token_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-single-token-termination.md"
BARE_PROMPT_PATH = (
    REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_format_bare_v1.md"
)
BARE_PROMPT_ID = "competitive_attachment_residual_ownership_format_bare_v1"
EFFECTIVE_MAX_OUTPUT_TOKENS = 1
TOP_LOGPROBS = 10


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--answer-format-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)

    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--config", type=Path, required=True)
    finalize.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run, "finalize": _finalize}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.11 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    predecessor_root = args.answer_format_root.resolve()
    config = _config(args.config)
    predecessor_metadata, predecessor_preflight, predecessor_report = _load_predecessor(
        predecessor_root
    )
    _validate_runtime(config, predecessor_metadata)
    prompt = _file_reference("bare_prompt", BARE_PROMPT_PATH)
    if prompt.sha256 != predecessor_preflight.bare_prompt.sha256:
        raise ValueError("CEA-1.11 Bare Prompt differs from CEA-1.10.")
    archived_argmax = {
        case.task.id: _required_argmax(case.bare.finite_label_evidence, case.task.id)
        for case in predecessor_report.cases
    }
    inputs = tuple(
        sorted(
            (
                _file_reference(
                    "predecessor_claude_review", predecessor_root / "claude-opus-review.md"
                ),
                _file_reference(
                    "predecessor_handoff", predecessor_root / "second-opinion-handoff.md"
                ),
                _file_reference("predecessor_preflight", predecessor_root / "preflight.json"),
                _file_reference("predecessor_recovery", predecessor_root / "recovery-report.json"),
                _file_reference("predecessor_report", predecessor_root / "report.json"),
                _file_reference("predecessor_review", predecessor_root / "comparison-review.md"),
                _file_reference("predecessor_run", predecessor_root / "run.json"),
                _file_reference("predecessor_status", predecessor_root / "status.json"),
                _file_reference("tdd", TDD_PATH),
                *(
                    _file_reference(
                        f"predecessor_bare_{case.task.id}", Path(case.bare.execution_record.path)
                    )
                    for case in predecessor_report.cases
                ),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_single_token_preflight(
        inputs=inputs,
        bare_prompt=prompt,
        tasks=predecessor_preflight.tasks,
        archived_bare_argmax_by_task=archived_argmax,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    metadata = {
        "schema_version": "attachment_single_token_run_v1",
        "status": "prepared",
        "config_path": str(args.config.resolve()),
        "answer_format_root": str(predecessor_root),
        "development_run_root": predecessor_metadata["development_run_root"],
        "runtime_contract": predecessor_metadata["runtime_contract"],
        "runtime_contract_sha256": predecessor_metadata["runtime_contract_sha256"],
        "prompt_path": str(BARE_PROMPT_PATH),
        "prompt_sha256": prompt.sha256,
        "prompt_id": BARE_PROMPT_ID,
        "task_renderer_id": ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
        "tdd_path": str(TDD_PATH),
        "configured_generation_parameters": _generation_payload(configured_generation),
        "configured_generation_parameters_sha256": generation_parameters_digest(
            configured_generation
        ),
        "effective_generation_parameters": _generation_payload(effective_generation),
        "effective_generation_parameters_sha256": generation_parameters_digest(
            effective_generation
        ),
        "effective_max_output_tokens": EFFECTIVE_MAX_OUTPUT_TOKENS,
        "top_logprobs": TOP_LOGPROBS,
        "production_integration": "not_activated",
    }
    _write_json(root / "preflight.json", preflight.model_dump(mode="json"))
    _write_json(
        root / "tasks-development.json",
        [item.model_dump(mode="json") for item in preflight.tasks],
    )
    metadata.update(
        {
            "preflight_fingerprint": preflight.result_fingerprint,
            "preflight_file_sha256": _file_sha(root / "preflight.json"),
        }
    )
    _write_json(root / "run.json", metadata)
    status = _status(root, AttachmentSingleTokenPackageStatus.PREPARED)
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
    return _run_or_finalize(args, execute=True)


def _finalize(args: argparse.Namespace) -> int:
    return _run_or_finalize(args, execute=False)


def _run_or_finalize(args: argparse.Namespace, *, execute: bool) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    if metadata.get("status") not in {"prepared", "complete"}:
        raise ValueError("CEA-1.11 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentSingleTokenPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.11 preflight fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.11 preflight file digest drifted.")
    for reference in (*preflight.inputs, preflight.bare_prompt):
        _validate_reference(reference)
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    if _generation_payload(configured_generation) != metadata.get(
        "configured_generation_parameters"
    ):
        raise ValueError("CEA-1.11 configured generation settings drifted.")
    if _generation_payload(effective_generation) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.11 effective generation settings drifted.")
    if execute:
        tasks = tuple(item.edge_filter_task for item in preflight.tasks)
        for repetition in (1, 2):
            cea14.execute_attachment_edge_filter_tasks(
                root=root,
                config=config,
                tasks=tasks,
                output_directory=root / f"repetition-{repetition}",
                phase="development",
                metadata=metadata,
                generation_parameters=configured_generation,
                prompt_id=BARE_PROMPT_ID,
                task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
                effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
            )
    archived_input = _archived_model_inputs(metadata, preflight)
    observations = tuple(
        item
        for repetition in (1, 2)
        for item in _load_observations(
            root=root,
            directory=root / f"repetition-{repetition}",
            config=config,
            preflight=preflight,
            repetition=repetition,
            configured_generation=configured_generation,
            archived_model_input_by_task=archived_input,
        )
    )
    _validate_model_identity(metadata, observations)
    report_inputs = (
        _file_reference("preflight", root / "preflight.json"),
        _file_reference("repetition_1_executions", root / "repetition-1"),
        _file_reference("repetition_2_executions", root / "repetition-2"),
    )
    report = build_single_token_report(
        inputs=report_inputs,
        preflight=preflight,
        observations=observations,
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "comparison-review.md").write_text(
        render_single_token_review(report),
        encoding="utf-8",
    )
    package_files = tuple(
        sorted(
            (
                *preflight.inputs,
                preflight.bare_prompt,
                _file_reference("comparison_report", root / "report.json"),
                _file_reference("comparison_review", root / "comparison-review.md"),
                _file_reference("preflight", root / "preflight.json"),
                *(
                    _file_reference(f"repetition_1_{path.stem}", path)
                    for path in sorted((root / "repetition-1").glob("aet_*.json"))
                ),
                *(
                    _file_reference(f"repetition_2_{path.stem}", path)
                    for path in sorted((root / "repetition-2").glob("aet_*.json"))
                ),
            ),
            key=lambda item: item.label,
        )
    )
    (root / "second-opinion-handoff.md").write_text(
        render_single_token_handoff(
            report,
            prompt_text=BARE_PROMPT_PATH.read_text(encoding="utf-8"),
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
    status = _status(root, AttachmentSingleTokenPackageStatus.COMPLETE, report=report)
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
    preflight: AttachmentSingleTokenPreflight,
    repetition: int,
    configured_generation: tuple[ExecutionSetting, ...],
    archived_model_input_by_task: dict[str, str],
) -> tuple[AttachmentSingleTokenObservation, ...]:
    if repetition not in (1, 2):
        raise ValueError("CEA-1.11 repetition must be one or two.")
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    effective_payload = _generation_payload(effective_generation)
    effective_digest = generation_parameters_digest(effective_generation)
    result: list[AttachmentSingleTokenObservation] = []
    for residual_task in preflight.tasks:
        task = residual_task.edge_filter_task
        path = directory / f"{task.task_id}.json"
        decision, value = cea14.validate_attachment_edge_filter_execution_record(
            path,
            task,
            archive=archive,
            expected_prompt_sha256=preflight.bare_prompt.sha256,
            expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
            expected_prompt_id=BARE_PROMPT_ID,
            expected_task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
        )
        trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
        model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
        if model_run.generation_parameters != effective_payload:
            raise ValueError("CEA-1.11 execution generation settings drifted.")
        exact_input = trace.input.get("exact_model_input")
        raw_output = trace.output.get("raw_output_text")
        if not isinstance(exact_input, str) or not exact_input:
            raise ValueError("CEA-1.11 execution lacks exact model input.")
        if exact_input != archived_model_input_by_task[residual_task.id]:
            raise ValueError("CEA-1.11 exact model input differs from CEA-1.10 Bare input.")
        if raw_output is not None and not isinstance(raw_output, str):
            raise ValueError("CEA-1.11 raw output text has invalid shape.")
        forbidden = (
            task.edge.id,
            task.candidate.id,
            task.edge.source_grounded_event_id,
            "expected_answer",
        )
        if any(item in exact_input for item in forbidden):
            raise ValueError("CEA-1.11 model input exposes hidden evaluation data.")
        evidence = None
        identity = _admitted_model_identity_digest(model_run)
        output_token_count = None
        if model_run.execution_receipt is not None:
            receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
            if receipt.generation_parameters_digest != effective_digest:
                raise ValueError("CEA-1.11 receipt generation settings drifted.")
            if receipt.model_identity_digest != identity:
                raise ValueError("CEA-1.11 receipt model identity differs from admission.")
            output_token_count = receipt.output_token_count
            try:
                evidence = finite_label_evidence(receipt)
            except ValueError:
                evidence = None
        archived = preflight.archived_bare_argmax_by_task[residual_task.id]
        strict_valid = (
            decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and decision.answer is not None
        )
        observed_matches = (
            strict_valid
            and evidence is not None
            and decision.answer is evidence.finite_label_argmax
        )
        archived_matches = evidence is not None and evidence.finite_label_argmax is archived
        result.append(
            AttachmentSingleTokenObservation(
                repetition=repetition,
                task_id=residual_task.id,
                edge_id=task.edge.id,
                archived_bare_argmax=archived,
                decision=decision,
                finite_label_evidence=evidence,
                model_identity_digest=identity,
                model_run_status=model_run.status,
                model_error_code=model_run.error_code,
                model_error_message=model_run.error_message,
                execution_record=_file_reference(
                    f"repetition_{repetition}_{residual_task.id}", path
                ),
                exact_model_input=exact_input,
                raw_output_text=raw_output,
                output_token_count=output_token_count,
                elapsed_milliseconds=_elapsed_milliseconds(model_run),
                strict_valid_output=strict_valid,
                output_is_one_token=output_token_count == 1,
                observed_answer_matches_live_argmax=observed_matches,
                live_argmax_matches_archived=archived_matches,
            )
        )
    return tuple(result)


def _load_predecessor(
    root: Path,
) -> tuple[dict[str, Any], AttachmentAnswerFormatPreflight, AttachmentAnswerFormatReport]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.11 requires a complete CEA-1.10 package.")
    checks = {
        "preflight_file_sha256": root / "preflight.json",
        "report_file_sha256": root / "report.json",
        "review_file_sha256": root / "comparison-review.md",
        "handoff_file_sha256": root / "second-opinion-handoff.md",
    }
    for field, path in checks.items():
        if not path.is_file() or metadata.get(field) != _file_sha(path):
            raise ValueError(f"CEA-1.11 predecessor digest changed: {field}.")
    claude_review = root / "claude-opus-review.md"
    if not claude_review.is_file() or not claude_review.read_bytes():
        raise ValueError("CEA-1.11 requires the completed CEA-1.10 Claude review.")
    preflight = AttachmentAnswerFormatPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentAnswerFormatReport.model_validate_json((root / "report.json").read_bytes())
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.11 predecessor preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.11 predecessor report fingerprint changed.")
    if report.outcome.value != "falsified":
        raise ValueError("CEA-1.11 requires the falsified CEA-1.10 outcome.")
    if report.bare_answer_first_token_count != 0:
        raise ValueError("CEA-1.11 requires zero Bare first-token Answer outputs.")
    if any(
        case.bare.finite_label_evidence is None
        or case.bare.finite_label_evidence.emitted_token.strip() not in {"Y", "N", "U"}
        for case in report.cases
    ):
        raise ValueError("CEA-1.11 requires ten finite Bare first-token answers.")
    return metadata, preflight, report


def _archived_model_inputs(
    metadata: dict[str, Any],
    preflight: AttachmentSingleTokenPreflight,
) -> dict[str, str]:
    root = Path(_required_str(metadata, "answer_format_root"))
    report = AttachmentAnswerFormatReport.model_validate_json((root / "report.json").read_bytes())
    values = {case.task.id: case.bare.exact_model_input for case in report.cases}
    if set(values) != {item.id for item in preflight.tasks}:
        raise ValueError("CEA-1.11 archived model input inventory drifted.")
    return values


def _validate_model_identity(
    metadata: dict[str, Any],
    observations: tuple[AttachmentSingleTokenObservation, ...],
) -> None:
    live = {item.model_identity_digest for item in observations}
    if len(live) > 1:
        raise ValueError("CEA-1.11 repetitions used different model identities.")
    predecessor_root = Path(_required_str(metadata, "answer_format_root"))
    predecessor = AttachmentAnswerFormatReport.model_validate_json(
        (predecessor_root / "report.json").read_bytes()
    )
    archived = {
        case.bare.model_identity_digest
        for case in predecessor.cases
        if case.bare.model_identity_digest is not None
    }
    if live != archived:
        raise ValueError("CEA-1.11 model identity differs from CEA-1.10 Bare execution.")


def _admitted_model_identity_digest(model_run: ModelRun) -> str:
    admission = model_run.input_admission
    if admission is None or admission.status.value != "ready":
        raise ValueError("CEA-1.11 ModelRun lacks ready input admission evidence.")
    return admission.model_identity_digest


def _required_argmax(
    evidence: AttachmentFiniteLabelEvidence | None,
    task_id: str,
) -> AttachmentEdgeFilterAnswerValue:
    if evidence is None:
        raise ValueError(f"CEA-1.11 predecessor lacks Finite Label Evidence: {task_id}.")
    return evidence.finite_label_argmax


def _status(
    root: Path,
    status: AttachmentSingleTokenPackageStatus,
    *,
    report: AttachmentSingleTokenReport | None = None,
) -> AttachmentSingleTokenStatus:
    complete = status is AttachmentSingleTokenPackageStatus.COMPLETE
    return AttachmentSingleTokenStatus(
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
        raise ValueError("CEA-1.11 generation settings are not canonically ordered.")
    return settings


def _generation_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    expected = cea14.attachment_edge_filter_runtime_contract(config)
    if expected != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.11 configured runtime differs from sealed evidence.")


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
    observed = _file_reference(reference.label, Path(reference.path))
    if observed.sha256 != reference.sha256:
        raise ValueError(f"CEA-1.11 evidence digest drifted: {reference.label}.")


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
        raise ValueError("CEA-1.11 ModelRun lacks elapsed milliseconds.")
    return value


def _required_str(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"CEA-1.11 metadata lacks {key}.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
