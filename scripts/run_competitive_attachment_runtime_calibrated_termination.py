#!/usr/bin/env python3
"""Run the CEA-1.12 runtime-calibrated finite termination experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    AttachmentAnswerFormatPreflight,
    AttachmentAnswerFormatReport,
    AttachmentCalibratedTerminationObservation,
    AttachmentCalibratedTerminationPackageStatus,
    AttachmentCalibratedTerminationPreflight,
    AttachmentCalibratedTerminationReport,
    AttachmentCalibratedTerminationStatus,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentSingleTokenPreflight,
    AttachmentSingleTokenReport,
    ExecutionSetting,
    ExtractionStageTrace,
    attachment_edge_filter_generation_parameters,
    attachment_exact_raw_finite_answer,
    attachment_output_count_witnesses_agree,
    attachment_position_zero_sha256,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_finite_answer_format import (
    finite_label_evidence,
)
from kotekomi_pipelines.competitive_attachment_runtime_calibrated_termination import (
    build_calibrated_termination_preflight,
    build_calibrated_termination_report,
    render_calibrated_termination_handoff,
    render_calibrated_termination_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = (
    REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-runtime-calibrated-termination.md"
)
BARE_PROMPT_PATH = (
    REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_format_bare_v1.md"
)
BARE_PROMPT_ID = "competitive_attachment_residual_ownership_format_bare_v1"
REQUESTED_OUTPUT_LIMIT = 2
TOP_LOGPROBS = 10


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--single-token-root", type=Path, required=True)
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
        raise ValueError("CEA-1.12 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    single_root = args.single_token_root.resolve()
    config = _config(args.config)
    single_metadata, single_preflight, single_report = _load_single_token_package(single_root)
    answer_root = Path(_required_str(single_metadata, "answer_format_root"))
    answer_metadata, answer_preflight, answer_report = _load_answer_format_package(answer_root)
    _validate_runtime(config, answer_metadata)
    prompt = _file_reference("bare_prompt", BARE_PROMPT_PATH)
    if prompt.sha256 != answer_preflight.bare_prompt.sha256:
        raise ValueError("CEA-1.12 Bare Prompt differs from CEA-1.10.")
    if tuple(item.id for item in single_preflight.tasks) != tuple(
        item.id for item in answer_preflight.tasks
    ):
        raise ValueError("CEA-1.12 predecessor task inventories differ.")
    _validate_probe_evidence(single_root)
    archived = _archived_evidence(answer_report)
    archived_argmax = {task_id: value[0] for task_id, value in archived.items()}
    archived_distributions = {task_id: value[1] for task_id, value in archived.items()}
    model_identities = {value[2] for value in archived.values()}
    if len(model_identities) != 1:
        raise ValueError("CEA-1.12 archived Bare model identity is not singular.")
    expected_identity = next(iter(model_identities))
    if {
        item.model_identity_digest for case in single_report.cases for item in case.observations
    } != {expected_identity}:
        raise ValueError("CEA-1.12 CEA-1.11 admission identity differs from CEA-1.10.")
    inputs = tuple(
        sorted(
            (
                _file_reference("answer_format_preflight", answer_root / "preflight.json"),
                _file_reference("answer_format_report", answer_root / "report.json"),
                _file_reference("answer_format_run", answer_root / "run.json"),
                _file_reference("answer_format_status", answer_root / "status.json"),
                _file_reference(
                    "single_token_claude_review", single_root / "claude-opus-review.md"
                ),
                _file_reference("single_token_handoff", single_root / "second-opinion-handoff.md"),
                _file_reference("single_token_preflight", single_root / "preflight.json"),
                _file_reference("single_token_report", single_root / "report.json"),
                _file_reference("single_token_review", single_root / "comparison-review.md"),
                _file_reference("single_token_run", single_root / "run.json"),
                _file_reference("single_token_status", single_root / "status.json"),
                _file_reference(
                    "probe_limit_1_request",
                    single_root / "one-token-response-probe-request.json",
                ),
                _file_reference(
                    "probe_limit_1_response",
                    single_root / "one-token-response-probe-response.sse",
                ),
                *(
                    _file_reference(
                        f"probe_limit_{limit}_summary",
                        single_root / f"output-limit-{limit}-summary.json",
                    )
                    for limit in (2, 3, 4)
                ),
                _file_reference(
                    "probe_limit_2_position_zero",
                    single_root / "probe-limit-2-position-0.json",
                ),
                _file_reference(
                    "archived_limit_8_position_zero",
                    single_root / "archived-limit-8-position-0.json",
                ),
                _file_reference("tdd", TDD_PATH),
                *(
                    _file_reference(
                        f"answer_format_bare_{case.task.id}",
                        Path(case.bare.execution_record.path),
                    )
                    for case in answer_report.cases
                ),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_calibrated_termination_preflight(
        inputs=inputs,
        bare_prompt=prompt,
        tasks=answer_preflight.tasks,
        archived_bare_argmax_by_task=archived_argmax,
        archived_position_zero_sha256_by_task=archived_distributions,
        expected_model_identity_digest=expected_identity,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
    )
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    metadata = {
        "schema_version": "attachment_calibrated_termination_run_v1",
        "status": "prepared",
        "config_path": str(args.config.resolve()),
        "single_token_root": str(single_root),
        "answer_format_root": str(answer_root),
        "development_run_root": answer_metadata["development_run_root"],
        "runtime_contract": answer_metadata["runtime_contract"],
        "runtime_contract_sha256": answer_metadata["runtime_contract_sha256"],
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
        "requested_output_limit": REQUESTED_OUTPUT_LIMIT,
        "top_logprobs": TOP_LOGPROBS,
        "production_suitability": "unmet",
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
    status = _status(root, AttachmentCalibratedTerminationPackageStatus.PREPARED)
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
        raise ValueError("CEA-1.12 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentCalibratedTerminationPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.12 preflight fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.12 preflight file digest drifted.")
    for reference in (*preflight.inputs, preflight.bare_prompt):
        _validate_reference(reference)
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    if _generation_payload(configured_generation) != metadata.get(
        "configured_generation_parameters"
    ):
        raise ValueError("CEA-1.12 configured generation settings drifted.")
    if _generation_payload(effective_generation) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.12 effective generation settings drifted.")
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
                effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
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
    _validate_model_identity(preflight, observations)
    report_inputs = (
        _file_reference("preflight", root / "preflight.json"),
        _file_reference("repetition_1_executions", root / "repetition-1"),
        _file_reference("repetition_2_executions", root / "repetition-2"),
    )
    report = build_calibrated_termination_report(
        inputs=report_inputs,
        preflight=preflight,
        observations=observations,
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "comparison-review.md").write_text(
        render_calibrated_termination_review(report),
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
        render_calibrated_termination_handoff(
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
    status = _status(
        root,
        AttachmentCalibratedTerminationPackageStatus.COMPLETE,
        report=report,
    )
    _write_json(root / "status.json", status.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "handoff": status.handoff_path,
                "mechanism_proof": report.mechanism_proof,
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
    preflight: AttachmentCalibratedTerminationPreflight,
    repetition: int,
    configured_generation: tuple[ExecutionSetting, ...],
    archived_model_input_by_task: dict[str, str],
) -> tuple[AttachmentCalibratedTerminationObservation, ...]:
    if repetition not in (1, 2):
        raise ValueError("CEA-1.12 repetition must be one or two.")
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=REQUESTED_OUTPUT_LIMIT,
    )
    effective_payload = _generation_payload(effective_generation)
    effective_digest = generation_parameters_digest(effective_generation)
    result: list[AttachmentCalibratedTerminationObservation] = []
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
            raise ValueError("CEA-1.12 execution generation settings drifted.")
        exact_input = trace.input.get("exact_model_input")
        raw_output = trace.output.get("raw_output_text")
        if not isinstance(exact_input, str) or not exact_input:
            raise ValueError("CEA-1.12 execution lacks exact model input.")
        if exact_input != archived_model_input_by_task[residual_task.id]:
            raise ValueError("CEA-1.12 exact model input differs from CEA-1.10 Bare input.")
        if raw_output is not None and not isinstance(raw_output, str):
            raise ValueError("CEA-1.12 raw output text has invalid shape.")
        forbidden = (
            task.edge.id,
            task.candidate.id,
            task.edge.source_grounded_event_id,
            "expected_answer",
        )
        if any(item in exact_input for item in forbidden):
            raise ValueError("CEA-1.12 model input exposes hidden evaluation data.")
        identity = _admitted_model_identity_digest(model_run)
        evidence = None
        output_count = None
        positions: tuple[int, ...] = ()
        distribution_digest = None
        if model_run.execution_receipt is not None:
            receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
            if receipt.generation_parameters_digest != effective_digest:
                raise ValueError("CEA-1.12 receipt generation settings drifted.")
            if receipt.model_identity_digest != identity:
                raise ValueError("CEA-1.12 receipt model identity differs from admission.")
            output_count = receipt.output_token_count
            positions = tuple(item.position for item in receipt.output_token_probabilities)
            position_zero = next(
                (item for item in receipt.output_token_probabilities if item.position == 0),
                None,
            )
            if position_zero is not None:
                distribution_digest = attachment_position_zero_sha256(position_zero)
            try:
                evidence = finite_label_evidence(receipt)
            except ValueError:
                evidence = None
        archived_argmax = preflight.archived_bare_argmax_by_task[residual_task.id]
        archived_distribution = preflight.archived_position_zero_sha256_by_task[residual_task.id]
        parsed = (
            decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and decision.answer is not None
        )
        exact_raw = attachment_exact_raw_finite_answer(raw_output)
        result.append(
            AttachmentCalibratedTerminationObservation(
                repetition=cast(Any, repetition),
                task_id=residual_task.id,
                edge_id=task.edge.id,
                archived_bare_argmax=archived_argmax,
                archived_position_zero_sha256=archived_distribution,
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
                output_token_count=output_count,
                probability_positions=positions,
                position_zero_sha256=distribution_digest,
                elapsed_milliseconds=_elapsed_milliseconds(model_run),
                exact_raw_finite_answer=exact_raw,
                output_count_witnesses_agree=attachment_output_count_witnesses_agree(
                    output_token_count=output_count,
                    probability_positions=positions,
                ),
                observed_answer_matches_live_argmax=(
                    parsed
                    and evidence is not None
                    and decision.answer is evidence.finite_label_argmax
                ),
                live_distribution_matches_archived=(distribution_digest == archived_distribution),
            )
        )
    return tuple(result)


def _load_single_token_package(
    root: Path,
) -> tuple[dict[str, Any], AttachmentSingleTokenPreflight, AttachmentSingleTokenReport]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.12 requires a complete CEA-1.11 package.")
    _validate_package_digests(root, metadata, "CEA-1.11")
    claude_review = root / "claude-opus-review.md"
    if not claude_review.is_file() or not claude_review.read_bytes():
        raise ValueError("CEA-1.12 requires the completed CEA-1.11 Claude review.")
    preflight = AttachmentSingleTokenPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentSingleTokenReport.model_validate_json((root / "report.json").read_bytes())
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.12 CEA-1.11 preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.12 CEA-1.11 report fingerprint changed.")
    if report.outcome.value != "inconclusive":
        raise ValueError("CEA-1.12 requires the inconclusive CEA-1.11 outcome.")
    if any(
        (
            report.probability_evidence_count,
            report.one_token_output_count,
            report.strict_valid_output_count,
        )
    ):
        raise ValueError("CEA-1.12 requires the CEA-1.11 empty-output result.")
    return metadata, preflight, report


def _load_answer_format_package(
    root: Path,
) -> tuple[dict[str, Any], AttachmentAnswerFormatPreflight, AttachmentAnswerFormatReport]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.12 requires a complete CEA-1.10 package.")
    _validate_package_digests(root, metadata, "CEA-1.10")
    preflight = AttachmentAnswerFormatPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentAnswerFormatReport.model_validate_json((root / "report.json").read_bytes())
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.12 CEA-1.10 preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.12 CEA-1.10 report fingerprint changed.")
    return metadata, preflight, report


def _validate_package_digests(root: Path, metadata: dict[str, Any], label: str) -> None:
    checks = {
        "preflight_file_sha256": root / "preflight.json",
        "report_file_sha256": root / "report.json",
        "review_file_sha256": root / "comparison-review.md",
        "handoff_file_sha256": root / "second-opinion-handoff.md",
    }
    for field, path in checks.items():
        if not path.is_file() or metadata.get(field) != _file_sha(path):
            raise ValueError(f"CEA-1.12 {label} package digest changed: {field}.")


def _validate_probe_evidence(root: Path) -> None:
    request = _read_json(root / "one-token-response-probe-request.json")
    if request.get("max_output_tokens") != 1:
        raise ValueError("CEA-1.12 limit-one probe request drifted.")
    terminal = _terminal_sse_response(root / "one-token-response-probe-response.sse")
    if terminal.get("output") != [] or _usage_output_tokens(terminal) != 0:
        raise ValueError("CEA-1.12 limit-one probe result drifted.")
    expected = {2: 1, 3: 2, 4: 3}
    for limit, output_count in expected.items():
        summary = _read_json(root / f"output-limit-{limit}-summary.json")
        if summary.get("max_output_tokens") != limit:
            raise ValueError(f"CEA-1.12 limit-{limit} probe request drifted.")
        if _usage_output_tokens(summary) != output_count:
            raise ValueError(f"CEA-1.12 limit-{limit} probe output count drifted.")
        if not _response_output_text(summary):
            raise ValueError(f"CEA-1.12 limit-{limit} probe lacks output text.")
    archived = _read_json(root / "archived-limit-8-position-0.json")
    probed = _read_json(root / "probe-limit-2-position-0.json")
    if archived != probed:
        raise ValueError("CEA-1.12 probe distribution differs from archived CEA-1.10.")


def _terminal_sse_response(path: Path) -> dict[str, Any]:
    terminal: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("data: "):
            continue
        value = cast(object, json.loads(line.removeprefix("data: ")))
        if not isinstance(value, dict):
            continue
        values = cast(dict[str, object], value)
        if values.get("type") == "response.completed":
            response = values.get("response")
            if isinstance(response, dict):
                terminal = cast(dict[str, Any], response)
    if terminal is None:
        raise ValueError("CEA-1.12 limit-one probe lacks a terminal response.")
    return terminal


def _usage_output_tokens(value: dict[str, Any]) -> int | None:
    usage = cast(object, value.get("usage"))
    if not isinstance(usage, dict):
        return None
    output_tokens = cast(dict[str, object], usage).get("output_tokens")
    return output_tokens if type(output_tokens) is int else None


def _response_output_text(value: dict[str, Any]) -> str | None:
    output = cast(object, value.get("output"))
    if not isinstance(output, list):
        return None
    values: list[str] = []
    for item in cast(list[object], output):
        if not isinstance(item, dict):
            continue
        content = cast(dict[str, object], item).get("content")
        if not isinstance(content, list):
            continue
        for part in cast(list[object], content):
            if not isinstance(part, dict):
                continue
            text = cast(dict[str, object], part).get("text")
            if isinstance(text, str):
                values.append(text)
    return values[0] if len(values) == 1 else None


def _archived_evidence(
    report: AttachmentAnswerFormatReport,
) -> dict[str, tuple[AttachmentEdgeFilterAnswerValue, str, str]]:
    result: dict[str, tuple[AttachmentEdgeFilterAnswerValue, str, str]] = {}
    for case in report.cases:
        evidence = case.bare.finite_label_evidence
        if evidence is None or case.bare.model_identity_digest is None:
            raise ValueError("CEA-1.12 archived Bare evidence is incomplete.")
        value = _read_json(Path(case.bare.execution_record.path))
        model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
        if model_run.execution_receipt is None:
            raise ValueError("CEA-1.12 archived Bare execution lacks a receipt.")
        receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
        first = next(
            (item for item in receipt.output_token_probabilities if item.position == 0),
            None,
        )
        if first is None:
            raise ValueError("CEA-1.12 archived Bare execution lacks position zero.")
        result[case.task.id] = (
            evidence.finite_label_argmax,
            attachment_position_zero_sha256(first),
            case.bare.model_identity_digest,
        )
    return result


def _archived_model_inputs(
    metadata: dict[str, Any],
    preflight: AttachmentCalibratedTerminationPreflight,
) -> dict[str, str]:
    root = Path(_required_str(metadata, "answer_format_root"))
    report = AttachmentAnswerFormatReport.model_validate_json((root / "report.json").read_bytes())
    values = {case.task.id: case.bare.exact_model_input for case in report.cases}
    if set(values) != {item.id for item in preflight.tasks}:
        raise ValueError("CEA-1.12 archived model input inventory drifted.")
    return values


def _validate_model_identity(
    preflight: AttachmentCalibratedTerminationPreflight,
    observations: tuple[AttachmentCalibratedTerminationObservation, ...],
) -> None:
    observed = {item.model_identity_digest for item in observations}
    if observed != {preflight.expected_model_identity_digest}:
        raise ValueError("CEA-1.12 model identity differs from archived Bare execution.")


def _admitted_model_identity_digest(model_run: ModelRun) -> str:
    admission = model_run.input_admission
    if admission is None or admission.status.value != "ready":
        raise ValueError("CEA-1.12 ModelRun lacks ready input admission evidence.")
    return admission.model_identity_digest


def _status(
    root: Path,
    status: AttachmentCalibratedTerminationPackageStatus,
    *,
    report: AttachmentCalibratedTerminationReport | None = None,
) -> AttachmentCalibratedTerminationStatus:
    complete = status is AttachmentCalibratedTerminationPackageStatus.COMPLETE
    return AttachmentCalibratedTerminationStatus(
        status=status,
        run_root=str(root),
        preflight_path=str(root / "preflight.json"),
        report_path=str(root / "report.json") if complete else None,
        review_path=str(root / "comparison-review.md") if complete else None,
        handoff_path=str(root / "second-opinion-handoff.md") if complete else None,
        claude_review_path=str(root / "claude-opus-review.md") if complete else None,
        outcome=report.outcome if report is not None else None,
        mechanism_proof=report.mechanism_proof if report is not None else None,
        production_suitability="unmet",
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
        raise ValueError("CEA-1.12 generation settings are not canonically ordered.")
    return settings


def _generation_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    expected = cea14.attachment_edge_filter_runtime_contract(config)
    if expected != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.12 configured runtime differs from sealed evidence.")


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
        raise ValueError(f"CEA-1.12 evidence digest drifted: {reference.label}.")


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
        raise ValueError("CEA-1.12 ModelRun lacks elapsed milliseconds.")
    return value


def _required_str(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"CEA-1.12 metadata lacks {key}.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
