#!/usr/bin/env python3
"""Run the CEA-1.24 Qwen3-14B local model swap experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import run_competitive_attachment_edge_filter_experiment as cea14
import run_competitive_attachment_nested_event_transfer as cea123
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_NONTHINKING_RENDERER_ID,
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
    AttachmentEvidenceReference,
    AttachmentLocalModelOutputCalibration,
    AttachmentLocalModelPrimaryRejection,
    AttachmentLocalModelReadiness,
    AttachmentLocalModelSwapPreflight,
    AttachmentLocalModelSwapReport,
    AttachmentLocalModelVariant,
    AttachmentNestedTransferCatalog,
    AttachmentNestedTransferReport,
    AttachmentNestedTransferSubmission,
    ExecutionSetting,
    attachment_nested_event_ownership_model_task_input,
    attachment_nested_event_ownership_nonthinking_model_task_input,
)
from kotekomi_domain import ModelRun, ModelRunStatus
from kotekomi_pipelines.competitive_attachment_local_model_swap import (
    build_attachment_local_model_swap_preflight,
    build_attachment_local_model_swap_report,
    map_lm_studio_model_artifact,
    render_attachment_local_model_swap_review,
)
from kotekomi_pipelines.competitive_attachment_nested_event_transfer import (
    build_attachment_nested_transfer_report,
    render_attachment_nested_transfer_review,
    validate_attachment_nested_transfer_submission,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

ROOT = Path(__file__).resolve().parents[1]
TDD = ROOT / "docs/2026-09-22-competitive-attachment-local-model-swap.md"
PROGRAM = ROOT / "docs/2026-09-18-competitive-event-attachment-program.md"
PROMPT = ROOT / "prompts/competitive_attachment_nested_event_ownership_v1.md"
COMPARATOR_EFFECTIVE_MAX_OUTPUT_TOKENS = 2
CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS = 16


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--baseline-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    run_baseline = commands.add_parser("run-baseline")
    run_baseline.add_argument("--config", type=Path, required=True)
    run_baseline.add_argument("--run-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    run.add_argument("--model-id", required=True)
    run.add_argument(
        "--variant",
        choices=tuple(item.value for item in AttachmentLocalModelVariant),
        required=True,
    )
    run.add_argument("--readiness-status", type=Path, required=True)
    run.add_argument("--primary-readiness-status", type=Path)
    run.add_argument("--fallback-reason")
    run.add_argument("--output-calibration-root", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run-baseline": _run_baseline, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    baseline_root = args.baseline_root.resolve()
    run_root = args.run_root.resolve()
    if run_root.exists() and any(run_root.iterdir()):
        raise ValueError("CEA-1.24 run root must be absent or empty.")
    baseline, catalog, _ = _validated_baseline(baseline_root, require_second_opinion=True)
    if PROMPT.read_bytes() != Path(catalog.prompt.path).read_bytes():
        raise ValueError("CEA-1.24 Semantic Prompt differs from CEA-1.23.")
    baseline_report_path = baseline_root / "report.json"
    blind_response_path = baseline_root / "blind-review-response.json"
    inputs = tuple(
        sorted(
            (
                _reference("baseline_report", baseline_report_path),
                _reference("baseline_run", baseline_root / "run.json"),
                _reference("baseline_review", baseline_root / "comparison-review.md"),
                _reference("baseline_handoff", baseline_root / "second-opinion-handoff.md"),
                _reference("baseline_second_opinion", baseline_root / "claude-opus-review.md"),
                _reference("baseline_catalog", baseline_root / "catalog.json"),
                _reference("blind_review_response", blind_response_path),
                _reference("program", PROGRAM),
                _reference("tdd", TDD),
                catalog.prompt,
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_attachment_local_model_swap_preflight(
        inputs=inputs,
        baseline_root=str(baseline_root),
        baseline_report=_reference("baseline_report", baseline_report_path),
        blind_review_response=_reference("blind_review_response", blind_response_path),
        semantic_prompt=catalog.prompt,
    )
    run_root.mkdir(parents=True, exist_ok=True)
    preflight_path = run_root / "preflight.json"
    _write_json(preflight_path, preflight.model_dump(mode="json"))
    _write_json(
        run_root / "run.json",
        {
            "schema_version": "attachment_local_model_swap_run_v1",
            "status": "prepared",
            "baseline_root": str(baseline_root),
            "preflight_fingerprint": preflight.result_fingerprint,
            "preflight_sha256": _sha_file(preflight_path),
            "source_revision": _git_revision(),
        },
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(run_root),
                "preflight": str(preflight_path),
                "baseline_correct": baseline.correct_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _run_baseline(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    metadata = _read_json(run_root / "run.json")
    if metadata.get("status") not in {"prepared", "comparator_running", "comparator_complete"}:
        raise ValueError("CEA-1.24 Comparator Baseline metadata is not prepared.")
    preflight_path = run_root / "preflight.json"
    preflight = AttachmentLocalModelSwapPreflight.model_validate_json(preflight_path.read_bytes())
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint") or _sha_file(
        preflight_path
    ) != metadata.get("preflight_sha256"):
        raise ValueError("CEA-1.24 preflight evidence drifted.")
    for reference in preflight.inputs:
        _validate_reference(reference)
    baseline_root = Path(preflight.baseline_root)
    historical, catalog, submission = _validated_baseline(
        baseline_root,
        require_second_opinion=True,
    )
    config = load_config(
        config_path=args.config.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )
    baseline_run = _read_json(baseline_root / "run.json")
    runtime_contract = cea14.attachment_edge_filter_runtime_contract(config)
    if runtime_contract != baseline_run.get("runtime_contract"):
        raise ValueError("CEA-1.24 Comparator Baseline changed the Qwen2.5 runtime contract.")
    generation = _generation(config)
    generation_payload = {item.key: item.value for item in generation}
    if generation_payload != baseline_run.get("generation_parameters"):
        raise ValueError("CEA-1.24 Comparator Baseline changed generation settings.")
    comparator_root = run_root / "comparator-baseline"
    comparator_root.mkdir(parents=True, exist_ok=True)
    comparator_metadata: dict[str, Any] = {
        "schema_version": "attachment_local_model_swap_comparator_run_v1",
        "status": "running",
        "config_path": str(args.config.resolve()),
        "runtime_contract": runtime_contract,
        "generation_parameters": generation_payload,
        "exact_source_context": True,
        "effective_max_output_tokens": COMPARATOR_EFFECTIVE_MAX_OUTPUT_TOKENS,
    }
    _write_json(comparator_root / "run.json", comparator_metadata)
    metadata.update(
        {
            "status": "comparator_running",
            "comparator_root": str(comparator_root),
        }
    )
    _write_json(run_root / "run.json", metadata)
    cea123.execute_attachment_nested_transfer_tasks(
        root=comparator_root,
        config=config,
        catalog=catalog,
        metadata=comparator_metadata,
        generation=generation,
        prompt=PROMPT.read_bytes(),
        prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
        task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
        model_task_input=attachment_nested_event_ownership_model_task_input,
        progress_label="Qwen2.5 comparator case",
        policy_id="competitive_attachment_local_model_comparator_v1",
        task_type="competitive_attachment_local_model_comparator",
        exact_source_context=True,
        effective_max_output_tokens=COMPARATOR_EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    archive = LocalArchiveStore(comparator_root / "archive")
    archive.initialize()
    observations = tuple(
        cea123.load_attachment_nested_transfer_observation(
            path=comparator_root / "executions" / f"{case.task.task_id}.json",
            archive=archive,
            config=config,
            case=case,
            prompt_sha256=catalog.prompt.sha256,
            prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
            task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
            model_task_input=attachment_nested_event_ownership_model_task_input,
        )
        for case in catalog.cases
    )
    _validate_strict_outputs(
        comparator_root,
        catalog,
        expected_effective_max_output_tokens=COMPARATOR_EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    comparator = build_attachment_nested_transfer_report(
        inputs=tuple(
            sorted(
                (item.execution_record for item in observations),
                key=lambda item: item.label,
            )
        ),
        catalog=catalog,
        submission=submission,
        observations=observations,
    )
    _validate_exact_source_context_report(comparator)
    if comparator.model_identity_digests != historical.model_identity_digests:
        raise ValueError("CEA-1.24 Comparator Baseline changed the Qwen2.5 model identity.")
    report_path = comparator_root / "report.json"
    review_path = comparator_root / "comparison-review.md"
    _write_json(report_path, comparator.model_dump(mode="json"))
    review_path.write_text(
        render_attachment_nested_transfer_review(
            comparator,
            prompt_text=PROMPT.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    comparator_metadata.update(
        {
            "status": "complete",
            "report_sha256": _sha_file(report_path),
            "review_sha256": _sha_file(review_path),
        }
    )
    _write_json(comparator_root / "run.json", comparator_metadata)
    metadata.update(
        {
            "status": "comparator_complete",
            "comparator_report_sha256": _sha_file(report_path),
            "comparator_review_sha256": _sha_file(review_path),
        }
    )
    _write_json(run_root / "run.json", metadata)
    print(
        json.dumps(
            {
                "status": "comparator_complete",
                "run_root": str(run_root),
                "report": str(report_path),
                "review": str(review_path),
                "historical_correct": historical.correct_count,
                "comparator_correct": comparator.correct_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    metadata = _read_json(run_root / "run.json")
    if metadata.get("status") not in {"comparator_complete", "running", "complete"}:
        raise ValueError("CEA-1.24 run metadata is not prepared.")
    preflight_path = run_root / "preflight.json"
    preflight = AttachmentLocalModelSwapPreflight.model_validate_json(preflight_path.read_bytes())
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint") or _sha_file(
        preflight_path
    ) != metadata.get("preflight_sha256"):
        raise ValueError("CEA-1.24 preflight evidence drifted.")
    for reference in preflight.inputs:
        _validate_reference(reference)
    baseline_root = Path(preflight.baseline_root)
    baseline, catalog, submission = _validated_baseline(
        baseline_root,
        require_second_opinion=True,
    )
    comparator_baseline = _validated_comparator_baseline(
        run_root,
        historical_baseline=baseline,
        historical_run=_read_json(baseline_root / "run.json"),
        catalog=catalog,
        submission=submission,
    )
    expected_calibration_input_sha256s = frozenset(
        hashlib.sha256((item.observation.exact_model_input + "\n/no_think\n").encode()).hexdigest()
        for item in comparator_baseline.evaluations
    )
    calibration, calibration_reference, calibration_references = _validated_output_calibration(
        args.output_calibration_root.resolve(),
        expected_input_sha256s=expected_calibration_input_sha256s,
        expected_model_id=cast(str, args.model_id),
    )
    comparator_root = Path(cast(str, metadata["comparator_root"]))
    variant = AttachmentLocalModelVariant(args.variant)
    fallback_reason = cast(str | None, args.fallback_reason)
    readiness_path = args.readiness_status.resolve()
    readiness = AttachmentLocalModelReadiness.model_validate_json(readiness_path.read_bytes())
    if readiness.variant is not variant:
        raise ValueError("CEA-1.24 readiness evidence names another model variant.")
    primary_readiness_argument = cast(Path | None, args.primary_readiness_status)
    primary_readiness_path: Path | None = None
    primary_rejection: AttachmentLocalModelPrimaryRejection | None = None
    if variant is AttachmentLocalModelVariant.Q6_K:
        if primary_readiness_argument is not None or fallback_reason is not None:
            raise ValueError("CEA-1.24 Q6_K cannot carry fallback evidence.")
    else:
        if primary_readiness_argument is None:
            raise ValueError("CEA-1.24 Q5_K_M requires the rejected Q6_K readiness record.")
        primary_readiness_path = primary_readiness_argument.resolve()
        primary_rejection = AttachmentLocalModelPrimaryRejection.model_validate_json(
            primary_readiness_path.read_bytes()
        )
        fallback_reason = fallback_reason or _fallback_reason(primary_rejection)
    config = _challenger_config(args.config.resolve(), cast(str, args.model_id))
    if config.model_execution.adapter != "lm_studio":
        raise ValueError("CEA-1.24 requires the LM Studio Adapter.")
    model_catalog = _lm_studio_model_catalog(
        config.model_execution.endpoint,
        config.model_execution.timeout_seconds,
    )
    model_catalog_path = run_root / "lm-studio-models.json"
    _write_json(model_catalog_path, model_catalog)
    artifact = map_lm_studio_model_artifact(
        payload=model_catalog,
        configured_instance_id=config.model_execution.model,
        variant=variant,
        estimated_total_memory_gib=readiness.estimated_total_memory_gib,
        readiness_evidence_sha256=_sha_file(readiness_path),
        fallback_reason=fallback_reason,
    )
    if artifact.model_key != readiness.model_key:
        raise ValueError("CEA-1.24 loaded model differs from its readiness estimate.")
    artifact_path = run_root / "model-artifact.json"
    _write_json(artifact_path, artifact.model_dump(mode="json"))
    generation = _generation(config)
    _validate_challenger_runtime(
        config,
        generation,
        _read_json(baseline_root / "run.json"),
    )
    runtime_contract = cea14.attachment_edge_filter_runtime_contract(config)
    generation_payload = {item.key: item.value for item in generation}
    stored_contract = metadata.get("runtime_contract")
    if stored_contract is not None and stored_contract != runtime_contract:
        raise ValueError("CEA-1.24 runtime contract drifted.")
    stored_generation = metadata.get("generation_parameters")
    if stored_generation is not None and stored_generation != generation_payload:
        raise ValueError("CEA-1.24 generation settings drifted.")
    stored_effective_limit = metadata.get("effective_max_output_tokens")
    if (
        stored_effective_limit is not None
        and stored_effective_limit != CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS
    ):
        raise ValueError("CEA-1.24 effective output-token limit drifted.")
    metadata.update(
        {
            "status": "running",
            "config_path": str(args.config.resolve()),
            "model_id": config.model_execution.model,
            "variant": variant.value,
            "fallback_reason": fallback_reason,
            "readiness_status_sha256": _sha_file(readiness_path),
            "primary_readiness_status_sha256": (
                _sha_file(primary_readiness_path) if primary_readiness_path is not None else None
            ),
            "runtime_contract": runtime_contract,
            "generation_parameters": generation_payload,
            "effective_max_output_tokens": CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS,
            "model_artifact_sha256": _sha_file(artifact_path),
            "output_calibration_sha256": calibration_reference.sha256,
            "output_calibration_answer": calibration.output_texts[0],
        }
    )
    _write_json(run_root / "run.json", metadata)
    cea123.execute_attachment_nested_transfer_tasks(
        root=run_root,
        config=config,
        catalog=catalog,
        metadata=metadata,
        generation=generation,
        prompt=PROMPT.read_bytes(),
        prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
        task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_NONTHINKING_RENDERER_ID,
        model_task_input=attachment_nested_event_ownership_nonthinking_model_task_input,
        progress_label="Qwen3 swap case",
        policy_id="competitive_attachment_local_model_swap_v1",
        task_type="competitive_attachment_local_model_swap",
        exact_source_context=True,
        effective_max_output_tokens=CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    archive = LocalArchiveStore(run_root / "archive")
    archive.initialize()
    observations = tuple(
        cea123.load_attachment_nested_transfer_observation(
            path=run_root / "executions" / f"{case.task.task_id}.json",
            archive=archive,
            config=config,
            case=case,
            prompt_sha256=catalog.prompt.sha256,
            prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
            task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_NONTHINKING_RENDERER_ID,
            model_task_input=attachment_nested_event_ownership_nonthinking_model_task_input,
        )
        for case in catalog.cases
    )
    _validate_strict_outputs(
        run_root,
        catalog,
        expected_effective_max_output_tokens=CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    challenger = build_attachment_nested_transfer_report(
        inputs=tuple(
            sorted(
                (
                    _reference("model_artifact", artifact_path),
                    *tuple(item.execution_record for item in observations),
                ),
                key=lambda item: item.label,
            )
        ),
        catalog=catalog,
        submission=submission,
        observations=observations,
    )
    challenger_path = run_root / "challenger-report.json"
    _write_json(challenger_path, challenger.model_dump(mode="json"))
    _validate_challenger_input_parity(comparator_baseline, challenger)
    readiness_references = _readiness_references(
        "challenger_readiness",
        readiness_path,
        readiness,
    )
    if primary_readiness_path is not None:
        if primary_rejection is None:
            raise ValueError("CEA-1.24 lacks its Primary Variant rejection evidence.")
        readiness_references += _readiness_references(
            "primary_readiness",
            primary_readiness_path,
            primary_rejection,
        )
    report = build_attachment_local_model_swap_report(
        inputs=tuple(
            sorted(
                (
                    *preflight.inputs,
                    _reference("preflight", preflight_path),
                    _reference("comparator_baseline_report", comparator_root / "report.json"),
                    _reference(
                        "comparator_baseline_review",
                        comparator_root / "comparison-review.md",
                    ),
                    *readiness_references,
                    *calibration_references,
                    _reference("model_catalog", model_catalog_path),
                    _reference("model_artifact", artifact_path),
                    _reference("challenger_report", challenger_path),
                ),
                key=lambda item: item.label,
            )
        ),
        preflight=_reference("preflight", preflight_path),
        output_calibration=calibration_reference,
        model_artifact=artifact,
        historical_baseline=baseline,
        comparator_baseline=comparator_baseline,
        challenger=challenger,
        comparator_effective_max_output_tokens=COMPARATOR_EFFECTIVE_MAX_OUTPUT_TOKENS,
        challenger_effective_max_output_tokens=CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    report_path = run_root / "report.json"
    review_path = run_root / "comparison-review.md"
    handoff_path = run_root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_attachment_local_model_swap_review(report), encoding="utf-8")
    handoff_path.write_text(
        _render_handoff(report_path, review_path, report),
        encoding="utf-8",
    )
    metadata.update(
        {
            "status": "complete",
            "outcome": report.outcome.value,
            "report_fingerprint": report.result_fingerprint,
            "report_sha256": _sha_file(report_path),
            "review_sha256": _sha_file(review_path),
            "handoff_sha256": _sha_file(handoff_path),
        }
    )
    _write_json(run_root / "run.json", metadata)
    status_path = run_root / "status.json"
    _write_json(
        status_path,
        {
            "schema_version": "attachment_local_model_swap_status_v1",
            "status": "complete",
            "outcome": report.outcome.value,
            "run_root": str(run_root),
            "report": str(report_path),
            "review": str(review_path),
            "handoff": str(handoff_path),
            "claude_review": str(run_root / "claude-opus-review.md"),
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "outcome": report.outcome.value,
                "run_root": str(run_root),
                "report": str(report_path),
                "review": str(review_path),
                "handoff": str(handoff_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _validated_baseline(
    root: Path,
    *,
    require_second_opinion: bool,
) -> tuple[
    AttachmentNestedTransferReport,
    AttachmentNestedTransferCatalog,
    AttachmentNestedTransferSubmission,
]:
    status = _read_json(root / "status.json")
    if (
        status.get("schema_version") != "attachment_nested_transfer_status_v1"
        or status.get("status") != "complete"
        or status.get("outcome") != "mixed"
    ):
        raise ValueError("CEA-1.24 requires the completed mixed CEA-1.23 package.")
    baseline_run = _read_json(root / "run.json")
    if (
        baseline_run.get("schema_version") != "attachment_nested_transfer_run_v1"
        or baseline_run.get("status") != "complete"
        or baseline_run.get("prompt_id") != ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID
        or baseline_run.get("prompt_sha256") != hashlib.sha256(PROMPT.read_bytes()).hexdigest()
        or baseline_run.get("effective_max_output_tokens") != 2
    ):
        raise ValueError("CEA-1.23 Baseline runtime metadata drifted.")
    runtime_contract = baseline_run.get("runtime_contract")
    if not isinstance(runtime_contract, dict) or runtime_contract != {
        "adapter": "lm_studio",
        "context_tokens": 16_384,
        "endpoint": "http://127.0.0.1:1234/v1",
        "max_output_tokens": 2048,
        "model": "qwen2.5-14b-instruct",
        "profile_name": "lm-studio",
        "timeout_seconds": 300.0,
    }:
        raise ValueError("CEA-1.23 Baseline runtime contract drifted.")
    if baseline_run.get("generation_parameters") != {
        "frequency_penalty": 0.0,
        "max_output_tokens": 2048,
        "seed": 17,
        "temperature": 0,
        "top_logprobs": 10,
    }:
        raise ValueError("CEA-1.23 Baseline generation settings drifted.")
    if require_second_opinion and not (root / "claude-opus-review.md").is_file():
        raise ValueError("CEA-1.24 requires the completed CEA-1.23 second opinion.")
    report = AttachmentNestedTransferReport.model_validate_json((root / "report.json").read_bytes())
    catalog = AttachmentNestedTransferCatalog.model_validate_json(
        (root / "catalog.json").read_bytes()
    )
    submission = AttachmentNestedTransferSubmission.model_validate_json(
        (root / "blind-review-response.json").read_bytes()
    )
    validate_attachment_nested_transfer_submission(catalog, submission)
    for reference in (*catalog.inputs, catalog.prompt, *report.inputs):
        if reference.label in {"program", "tdd"}:
            continue
        _validate_reference(reference)
    if (
        report.case_count != 20
        or report.correct_count != 16
        or report.accuracy != 0.8
        or report.yes_recall != 0.75
        or report.no_recall != 0.875
        or report.proposed_change_count != 0
        or report.accepted_ledger_change_count != 0
    ):
        raise ValueError("CEA-1.23 Baseline metrics differ from the accepted result.")
    return report, catalog, submission


def _validated_comparator_baseline(
    run_root: Path,
    *,
    historical_baseline: AttachmentNestedTransferReport,
    historical_run: dict[str, Any],
    catalog: AttachmentNestedTransferCatalog,
    submission: AttachmentNestedTransferSubmission,
) -> AttachmentNestedTransferReport:
    metadata = _read_json(run_root / "run.json")
    comparator_root_value = metadata.get("comparator_root")
    if not isinstance(comparator_root_value, str) or not comparator_root_value:
        raise ValueError("CEA-1.24 lacks its Comparator Baseline root.")
    comparator_root = Path(comparator_root_value)
    report_path = comparator_root / "report.json"
    review_path = comparator_root / "comparison-review.md"
    comparator_run = _read_json(comparator_root / "run.json")
    if (
        comparator_run.get("schema_version") != "attachment_local_model_swap_comparator_run_v1"
        or comparator_run.get("status") != "complete"
        or comparator_run.get("exact_source_context") is not True
        or comparator_run.get("effective_max_output_tokens")
        != COMPARATOR_EFFECTIVE_MAX_OUTPUT_TOKENS
        or comparator_run.get("runtime_contract") != historical_run.get("runtime_contract")
        or comparator_run.get("generation_parameters")
        != historical_run.get("generation_parameters")
        or comparator_run.get("report_sha256") != _sha_file(report_path)
        or comparator_run.get("review_sha256") != _sha_file(review_path)
        or metadata.get("comparator_report_sha256") != _sha_file(report_path)
        or metadata.get("comparator_review_sha256") != _sha_file(review_path)
    ):
        raise ValueError("CEA-1.24 Comparator Baseline evidence drifted.")
    report = AttachmentNestedTransferReport.model_validate_json(report_path.read_bytes())
    validate_attachment_nested_transfer_submission(catalog, submission)
    if tuple(item.case for item in report.evaluations) != catalog.cases:
        raise ValueError("CEA-1.24 Comparator Baseline changed the source-exact cases.")
    expected = {item.case_id: item for item in submission.decisions}
    if any(item.expected != expected[item.case.id] for item in report.evaluations):
        raise ValueError("CEA-1.24 Comparator Baseline changed blind Gold.")
    if report.model_identity_digests != historical_baseline.model_identity_digests:
        raise ValueError("CEA-1.24 Comparator Baseline changed the Qwen2.5 model identity.")
    for reference in report.inputs:
        _validate_reference(reference)
    _validate_exact_source_context_report(report)
    return report


def _validate_exact_source_context_report(report: AttachmentNestedTransferReport) -> None:
    for item in report.evaluations:
        source_text = item.case.task.source_text
        exact_input = item.observation.exact_model_input
        context_copy = f"[direct_prose]\n[paragraph]\n{source_text}"
        task_copy = f"Passage:\n{source_text}"
        if exact_input.count(source_text) != 2:
            raise ValueError("CEA-1.24 Exact Source Context must contain two exact copies.")
        if exact_input.count(context_copy) != 1 or exact_input.count(task_copy) != 1:
            raise ValueError("CEA-1.24 Exact Source Context rendering drifted.")
        if "SOURCE SEGMENT:" in exact_input:
            raise ValueError("CEA-1.24 Exact Source Context was re-segmented.")


def _validate_challenger_input_parity(
    comparator: AttachmentNestedTransferReport,
    challenger: AttachmentNestedTransferReport,
) -> None:
    _validate_exact_source_context_report(challenger)
    for comparator_item, challenger_item in zip(
        comparator.evaluations,
        challenger.evaluations,
        strict=True,
    ):
        if comparator_item.case != challenger_item.case:
            raise ValueError("CEA-1.24 Challenger changed one source-exact case.")
        expected = comparator_item.observation.exact_model_input + "\n/no_think\n"
        if challenger_item.observation.exact_model_input != expected:
            raise ValueError(
                "CEA-1.24 Challenger changed more than the terminal Non-Thinking Control."
            )


def _challenger_config(path: Path, model_id: str) -> PipelineConfig:
    config = load_config(
        config_path=path,
        ledger_path_override=None,
        archive_path_override=None,
    )
    return replace(
        config,
        model_execution=replace(
            config.model_execution,
            model=model_id,
            context_tokens=16_384,
        ),
    )


def _lm_studio_model_catalog(endpoint: str, timeout_seconds: float) -> dict[str, Any]:
    parsed = urlsplit(endpoint)
    url = urlunsplit((parsed.scheme, parsed.netloc, "/api/v1/models", "", ""))
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=min(timeout_seconds, 30.0)) as response:  # noqa: S310
        payload = response.read()
        if response.status != 200:
            raise ValueError(f"LM Studio model metadata returned HTTP {response.status}.")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("LM Studio model metadata must be one JSON object.")
    return cast(dict[str, Any], value)


def _generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting(key="frequency_penalty", value=0.0),
        ExecutionSetting(key="max_output_tokens", value=config.model_execution.max_output_tokens),
        ExecutionSetting(key="seed", value=17),
        ExecutionSetting(key="temperature", value=0),
        ExecutionSetting(key="top_logprobs", value=10),
    )


def _validate_challenger_runtime(
    config: PipelineConfig,
    generation: tuple[ExecutionSetting, ...],
    baseline_run: dict[str, Any],
) -> None:
    baseline_contract = baseline_run.get("runtime_contract")
    if not isinstance(baseline_contract, dict):
        raise ValueError("CEA-1.24 lacks the Baseline runtime contract.")
    observed_contract = cea14.attachment_edge_filter_runtime_contract(config)
    expected_contract: dict[str, object] = {
        **cast(dict[str, object], baseline_contract),
        "model": config.model_execution.model,
    }
    if observed_contract != expected_contract:
        raise ValueError("CEA-1.24 Challenger changed more than the loaded model.")
    observed_generation = {item.key: item.value for item in generation}
    if observed_generation != baseline_run.get("generation_parameters"):
        raise ValueError("CEA-1.24 Challenger generation settings differ from Baseline.")


def _validate_strict_outputs(
    root: Path,
    catalog: AttachmentNestedTransferCatalog,
    *,
    expected_effective_max_output_tokens: int,
) -> None:
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    for case in catalog.cases:
        value = _read_json(root / "executions" / f"{case.task.task_id}.json")
        model_run = ModelRun.model_validate_json(_canonical(value["model_run"]))
        _require_successful_model_run(
            model_run,
            task_id=case.task.task_id,
            expected_effective_max_output_tokens=expected_effective_max_output_tokens,
        )
        receipt = model_run.execution_receipt
        if receipt is None:
            raise ValueError("CEA-1.24 execution lacks a model receipt.")
        output_token_count = receipt.get("output_token_count")
        if type(output_token_count) is not int or output_token_count != 1:
            raise ValueError("CEA-1.24 requires one output token.")
        raw = archive.read_model_run_output(model_run.id)
        if raw not in {b"Y", b"N", b"U"}:
            raise ValueError("CEA-1.24 requires one raw answer character.")


def _require_successful_model_run(
    model_run: ModelRun,
    *,
    task_id: str,
    expected_effective_max_output_tokens: int,
) -> None:
    if model_run.status is not ModelRunStatus.SUCCEEDED:
        detail = ": ".join(
            item for item in (model_run.error_code, model_run.error_message) if item is not None
        )
        suffix = f": {detail}" if detail else ""
        raise ValueError(f"CEA-1.24 execution {task_id} ended {model_run.status.value}{suffix}.")
    if (
        model_run.generation_parameters.get("max_output_tokens")
        != expected_effective_max_output_tokens
    ):
        raise ValueError("CEA-1.24 execution used the wrong effective output-token limit.")


def _fallback_reason(rejection: AttachmentLocalModelPrimaryRejection) -> str:
    if not rejection.resource_guardrail_allows_load:
        return (
            "Q6_K was rejected by LM Studio resource guardrails at "
            f"{rejection.estimated_total_memory_gib:g} GiB."
        )
    if rejection.estimated_total_memory_gib > 18.0:
        return (
            "Q6_K exceeded the declared 18 GiB memory gate at "
            f"{rejection.estimated_total_memory_gib:g} GiB."
        )
    return f"Q6_K memory estimation failed with status {rejection.estimate_status}."


def _readiness_references(
    prefix: str,
    status_path: Path,
    readiness: AttachmentLocalModelReadiness | AttachmentLocalModelPrimaryRejection,
) -> tuple[AttachmentEvidenceReference, ...]:
    return (
        _reference(f"{prefix}_status", status_path),
        _reference(f"{prefix}_download_log", Path(readiness.download_log)),
        _reference(f"{prefix}_inventory", Path(readiness.inventory)),
        _reference(f"{prefix}_estimate_log", Path(readiness.estimate_log)),
    )


def _validated_output_calibration(
    root: Path,
    *,
    expected_input_sha256s: frozenset[str],
    expected_model_id: str,
) -> tuple[
    AttachmentLocalModelOutputCalibration,
    AttachmentEvidenceReference,
    tuple[AttachmentEvidenceReference, ...],
]:
    paths = {
        "output_calibration_status": root / "status.json",
        "output_calibration_result": root / "result.json",
        "output_calibration_request": root / "request.json",
        "output_calibration_response": root / "response.sse",
        "output_calibration_completed": root / "completed.json",
        "output_calibration_input": root / "exact-input.txt",
        "output_calibration_model_load": root / "model-load.log",
    }
    if any(not path.is_file() for path in paths.values()):
        raise ValueError("CEA-1.24 output calibration evidence is incomplete.")
    status = _read_json(paths["output_calibration_status"])
    if (
        status.get("schema_version") != "qwen3_exact_output_probe_status_v1"
        or status.get("status") != "complete"
        or status.get("probe_status") != 0
        or status.get("run_root") != str(root)
        or status.get("result") != str(paths["output_calibration_result"])
    ):
        raise ValueError("CEA-1.24 output calibration status is invalid.")
    calibration = AttachmentLocalModelOutputCalibration.model_validate_json(
        paths["output_calibration_result"].read_bytes()
    )
    exact_input = paths["output_calibration_input"].read_bytes()
    if (
        calibration.input_sha256 not in expected_input_sha256s
        or hashlib.sha256(exact_input).hexdigest() != calibration.input_sha256
    ):
        raise ValueError("CEA-1.24 output calibration used a different model input.")
    request = _read_json(paths["output_calibration_request"])
    expected_request_controls = {
        "model": expected_model_id,
        "stream": True,
        "frequency_penalty": 0.0,
        "max_output_tokens": CHALLENGER_EFFECTIVE_MAX_OUTPUT_TOKENS,
        "seed": 17,
        "temperature": 0,
        "include": ["message.output_text.logprobs"],
        "top_logprobs": 10,
    }
    if any(request.get(key) != value for key, value in expected_request_controls.items()):
        raise ValueError("CEA-1.24 output calibration request controls drifted.")
    if request.get("input") != exact_input.decode("utf-8"):
        raise ValueError("CEA-1.24 output calibration request changed the exact input.")
    completed = cast(dict[str, object], _read_json(paths["output_calibration_completed"]))
    output_value = completed.get("output")
    if not isinstance(output_value, list):
        raise ValueError("CEA-1.24 output calibration response lacks output entries.")
    texts_list: list[str] = []
    for raw_item in cast(list[object], output_value):
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        content_value = item.get("content")
        if not isinstance(content_value, list):
            continue
        for raw_content in cast(list[object], content_value):
            if not isinstance(raw_content, dict):
                continue
            content = cast(dict[str, object], raw_content)
            text = content.get("text")
            if content.get("type") == "output_text" and isinstance(text, str):
                texts_list.append(text)
    texts = tuple(texts_list)
    usage_value = completed.get("usage")
    if not isinstance(usage_value, dict):
        raise ValueError("CEA-1.24 output calibration response lacks usage.")
    usage = cast(dict[str, object], usage_value)
    output_details = usage.get("output_tokens_details")
    if not isinstance(output_details, dict):
        raise ValueError("CEA-1.24 output calibration response lacks output-token details.")
    typed_output_details = cast(dict[str, object], output_details)
    if (
        completed.get("status") != calibration.status
        or texts != calibration.output_texts
        or usage.get("output_tokens") != calibration.output_token_count
        or typed_output_details.get("reasoning_tokens") != calibration.reasoning_token_count
    ):
        raise ValueError("CEA-1.24 output calibration result drifted from its response.")
    terminal_responses: list[object] = []
    for line in paths["output_calibration_response"].read_text(encoding="utf-8").splitlines():
        if not line.startswith("data: "):
            continue
        event_value: object = json.loads(line.removeprefix("data: "))
        if isinstance(event_value, dict):
            event = cast(dict[str, object], event_value)
            if event.get("type") == "response.completed":
                terminal_responses.append(event.get("response"))
    if len(terminal_responses) != 1 or terminal_responses[0] != completed:
        raise ValueError("CEA-1.24 output calibration SSE differs from its completed response.")
    references = tuple(_reference(label, path) for label, path in sorted(paths.items()))
    result_reference = next(
        item for item in references if item.label == "output_calibration_result"
    )
    return calibration, result_reference, references


def _render_handoff(
    report_path: Path,
    review_path: Path,
    report: AttachmentLocalModelSwapReport,
) -> str:
    references = tuple(
        sorted(
            (
                *report.inputs,
                _reference("report", report_path),
                _reference("review", review_path),
                _reference("runner", Path(__file__)),
                _reference(
                    "application_contract",
                    ROOT / "packages/application/src/kotekomi_application/"
                    "competitive_attachment_local_model_swap.py",
                ),
                _reference(
                    "pipeline_policy",
                    ROOT / "packages/pipelines/src/kotekomi_pipelines/"
                    "competitive_attachment_local_model_swap.py",
                ),
            ),
            key=lambda item: item.label,
        )
    )
    lines = [
        "# CEA-1.24 Independent Review Handoff",
        "",
        "Review the frozen local-model comparison against its exact evidence.",
        "",
        "The semantic prompt, twenty cases, and blind labels come unchanged from CEA-1.23.",
        "",
        "Qwen2.5 and Qwen3 receive the same Exact Source Context.",
        "",
        "The Challenger changes the loaded model and appends `/no_think` after each task.",
        "",
        "The Comparator requests two output tokens. The Challenger requests sixteen output "
        "tokens because the Qwen3 runtime produced no visible text at two.",
        "",
        "KoteKomi accepts only one exact `Y`, `N`, or `U` output token from either model.",
        "",
        f"Stored outcome: `{report.outcome.value}`",
        "",
        f"Historical Baseline correct: `{report.historical_baseline_correct_count}` / `20`",
        "",
        f"Comparator Baseline correct: `{report.comparator_baseline_correct_count}` / `20`",
        "",
        f"Challenger correct: `{report.challenger_correct_count}` / `20`",
        "",
        "Effective output-token limits, Comparator / Challenger: "
        f"`{report.comparator_effective_max_output_tokens}` / "
        f"`{report.challenger_effective_max_output_tokens}`",
        "",
        f"Context corrected / regressed: `{len(report.context_corrected_case_ids)}` / "
        f"`{len(report.context_regressed_case_ids)}`",
        "",
        f"Corrected cases: `{len(report.corrected_case_ids)}`",
        "",
        f"Regressed cases: `{len(report.regressed_case_ids)}`",
        "",
        "Verify the following questions:",
        "",
        "1. Do the source cases, expected labels, and Semantic Prompt match CEA-1.23 exactly?",
        "2. Does the Comparator correct CEA-1.23's re-segmented context without changing Qwen2.5?",
        "3. Does LM Studio metadata establish the reported Qwen3-14B quantization?",
        "4. Is `/no_think` final in every model-visible task?",
        "5. Do both transition series and the aggregate metrics recompute exactly?",
        "6. Does the evidence support the stored outcome without claiming production readiness?",
        "7. What is the strongest bounded next experiment?",
        "",
        "The inference is limited to one model family and twenty reviewed cases.",
        "",
        "## Historical CEA-1.23 failures",
    ]
    for item in report.cases:
        if item.historical_baseline.correct:
            continue
        task = item.comparator_baseline.case.task
        target = next(
            option.text for option in task.event_options if option.label == task.target_event_label
        )
        historical = item.historical_baseline.observation.decision.answer
        comparator = item.comparator_baseline.observation.decision.answer
        challenger = item.challenger.observation.decision.answer
        lines.extend(
            [
                "",
                f"### {item.comparator_baseline.case.selector_id}",
                "",
                f"> {task.source_text}",
                "",
                f"Candidate: {json.dumps(task.candidate.text, ensure_ascii=False)}",
                "",
                f"Target Event: {json.dumps(target, ensure_ascii=False)}",
                "",
                f"Expected: `{item.comparator_baseline.expected.answer}`",
                "",
                "Historical / Comparator / Challenger: "
                f"`{historical.value if historical else 'unresolved'}` / "
                f"`{comparator.value if comparator else 'unresolved'}` / "
                f"`{challenger.value if challenger else 'unresolved'}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Evidence",
        ]
    )
    for reference in references:
        lines.extend(
            [
                "",
                f"- `{reference.label}`: `{reference.path}` (`sha256:{reference.sha256}`)",
            ]
        )
    lines.extend(
        [
            "",
            "Source repository: https://github.com/SQLCODE917/KoteKomi",
            "",
            f"Source revision: `{_git_revision()}`",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.24 evidence is missing: {label}.")
    return AttachmentEvidenceReference(label=label, path=str(resolved), sha256=_sha_file(resolved))


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or _sha_file(path) != reference.sha256:
        raise ValueError(f"CEA-1.24 evidence digest drifted: {reference.label}.")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
