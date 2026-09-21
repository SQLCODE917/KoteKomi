#!/usr/bin/env python3
"""Run the CEA-1.10 finite answer format experiment."""

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
    AttachmentAnswerFormatArm,
    AttachmentAnswerFormatObservation,
    AttachmentAnswerFormatPackageStatus,
    AttachmentAnswerFormatPreflight,
    AttachmentAnswerFormatReport,
    AttachmentAnswerFormatStatus,
    AttachmentArchivedFiniteLabelObservation,
    AttachmentCandidateRemainderArm,
    AttachmentCandidateRemainderPreflight,
    AttachmentCandidateRemainderReport,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentFiniteLabelRecoveryReport,
    ExecutionSetting,
    ExtractionStageTrace,
    attachment_edge_filter_generation_parameters,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.competitive_attachment_finite_answer_format import (
    build_answer_format_preflight,
    build_answer_format_report,
    build_finite_label_recovery_report,
    finite_label_evidence,
    render_answer_format_handoff,
    render_answer_format_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-20-competitive-attachment-finite-answer-format.md"
LABELED_PROMPT_PATH = (
    REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_format_labeled_v1.md"
)
BARE_PROMPT_PATH = (
    REPOSITORY_ROOT / "prompts/competitive_attachment_residual_ownership_format_bare_v1.md"
)
LABELED_PROMPT_ID = "competitive_attachment_residual_ownership_format_labeled_v1"
BARE_PROMPT_ID = "competitive_attachment_residual_ownership_format_bare_v1"
EFFECTIVE_MAX_OUTPUT_TOKENS = 8
TOP_LOGPROBS = 10
DISPUTED_GOLD_TASK_IDS = (
    "aro_663cb1f408cade57e5d2ebb9",
    "aro_7d658622da90db3299ebee76",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--candidate-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)

    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.10 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    candidate_root = args.candidate_root.resolve()
    config = _config(args.config)
    candidate_metadata, candidate_preflight, candidate_report = _load_candidate_package(
        candidate_root
    )
    _validate_runtime(config, candidate_metadata)
    labeled_prompt = _file_reference("labeled_prompt", LABELED_PROMPT_PATH)
    bare_prompt = _file_reference("bare_prompt", BARE_PROMPT_PATH)
    predecessor_files = _candidate_package_references(candidate_root, candidate_report)
    inputs = tuple(
        sorted(
            (
                *predecessor_files,
                _file_reference(
                    "candidate_claude_review", candidate_root / "claude-opus-review.md"
                ),
                _file_reference("tdd", TDD_PATH),
            ),
            key=lambda item: item.label,
        )
    )
    preflight = build_answer_format_preflight(
        inputs=inputs,
        labeled_prompt=labeled_prompt,
        bare_prompt=bare_prompt,
        labeled_prompt_text=LABELED_PROMPT_PATH.read_text(encoding="utf-8"),
        bare_prompt_text=BARE_PROMPT_PATH.read_text(encoding="utf-8"),
        tasks=candidate_preflight.tasks,
        configured_max_output_tokens=config.model_execution.max_output_tokens,
        disputed_gold_task_ids=DISPUTED_GOLD_TASK_IDS,
    )
    recovery = _recover_candidate_probabilities(candidate_report)
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    metadata = dict(candidate_metadata)
    for key in tuple(metadata):
        if key.endswith("_sha256") and key not in {
            "runtime_contract_sha256",
            "development_tasks_sha256",
            "validation_tasks_sha256",
        }:
            metadata.pop(key)
    metadata.update(
        {
            "schema_version": "attachment_answer_format_run_v1",
            "status": "prepared",
            "config_path": str(args.config.resolve()),
            "candidate_root": str(candidate_root),
            "labeled_prompt_path": str(LABELED_PROMPT_PATH),
            "labeled_prompt_sha256": labeled_prompt.sha256,
            "labeled_prompt_id": LABELED_PROMPT_ID,
            "bare_prompt_path": str(BARE_PROMPT_PATH),
            "bare_prompt_sha256": bare_prompt.sha256,
            "bare_prompt_id": BARE_PROMPT_ID,
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
    )
    _write_json(root / "preflight.json", preflight.model_dump(mode="json"))
    _write_json(root / "recovery-report.json", recovery.model_dump(mode="json"))
    metadata.update(
        {
            "preflight_fingerprint": preflight.result_fingerprint,
            "preflight_file_sha256": _file_sha(root / "preflight.json"),
            "recovery_fingerprint": recovery.result_fingerprint,
            "recovery_file_sha256": _file_sha(root / "recovery-report.json"),
        }
    )
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "tasks-development.json",
        [item.model_dump(mode="json") for item in preflight.tasks],
    )
    status = _status(root, AttachmentAnswerFormatPackageStatus.PREPARED)
    _write_json(root / "status.json", status.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "preflight": str(root / "preflight.json"),
                "recovery": str(root / "recovery-report.json"),
                "run_root": str(root),
                "status": status.status.value,
            },
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    if metadata.get("status") not in {"prepared", "complete"}:
        raise ValueError("CEA-1.10 run metadata is not prepared.")
    config = _config(args.config)
    _validate_runtime(config, metadata)
    preflight = AttachmentAnswerFormatPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    recovery = AttachmentFiniteLabelRecoveryReport.model_validate_json(
        (root / "recovery-report.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.10 preflight fingerprint drifted.")
    if recovery.result_fingerprint != metadata.get("recovery_fingerprint"):
        raise ValueError("CEA-1.10 recovery fingerprint drifted.")
    if _file_sha(root / "preflight.json") != metadata.get("preflight_file_sha256"):
        raise ValueError("CEA-1.10 preflight file digest drifted.")
    if _file_sha(root / "recovery-report.json") != metadata.get("recovery_file_sha256"):
        raise ValueError("CEA-1.10 recovery file digest drifted.")
    for reference in (*preflight.inputs, preflight.labeled_prompt, preflight.bare_prompt):
        _validate_reference(reference)
    configured_generation = _configured_generation(config)
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    if _generation_payload(configured_generation) != metadata.get(
        "configured_generation_parameters"
    ):
        raise ValueError("CEA-1.10 configured generation settings drifted.")
    if _generation_payload(effective_generation) != metadata.get("effective_generation_parameters"):
        raise ValueError("CEA-1.10 effective generation settings drifted.")
    tasks = tuple(item.edge_filter_task for item in preflight.tasks)
    labeled_metadata = dict(metadata)
    labeled_metadata.update(
        {
            "prompt_path": str(LABELED_PROMPT_PATH),
            "prompt_sha256": preflight.labeled_prompt.sha256,
        }
    )
    cea14.execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=tasks,
        output_directory=root / "labeled",
        phase="development",
        metadata=labeled_metadata,
        generation_parameters=configured_generation,
        prompt_id=LABELED_PROMPT_ID,
        task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    bare_metadata = dict(metadata)
    bare_metadata.update(
        {
            "prompt_path": str(BARE_PROMPT_PATH),
            "prompt_sha256": preflight.bare_prompt.sha256,
        }
    )
    cea14.execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=tasks,
        output_directory=root / "bare",
        phase="development",
        metadata=bare_metadata,
        generation_parameters=configured_generation,
        prompt_id=BARE_PROMPT_ID,
        task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    labeled = _load_observations(
        root=root,
        directory=root / "labeled",
        config=config,
        preflight=preflight,
        arm=AttachmentAnswerFormatArm.LABELED,
        prompt_sha256=preflight.labeled_prompt.sha256,
        prompt_id=LABELED_PROMPT_ID,
        configured_generation=configured_generation,
    )
    bare = _load_observations(
        root=root,
        directory=root / "bare",
        config=config,
        preflight=preflight,
        arm=AttachmentAnswerFormatArm.BARE,
        prompt_sha256=preflight.bare_prompt.sha256,
        prompt_id=BARE_PROMPT_ID,
        configured_generation=configured_generation,
    )
    _validate_model_identity(labeled, bare)
    report_inputs = (
        _file_reference("bare_executions", root / "bare"),
        _file_reference("labeled_executions", root / "labeled"),
        _file_reference("preflight", root / "preflight.json"),
        _file_reference("recovery", root / "recovery-report.json"),
    )
    report = build_answer_format_report(
        inputs=report_inputs,
        preflight=preflight,
        labeled_observations=labeled,
        bare_observations=bare,
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "comparison-review.md").write_text(
        render_answer_format_review(report),
        encoding="utf-8",
    )
    package_files = tuple(
        sorted(
            (
                *preflight.inputs,
                preflight.labeled_prompt,
                preflight.bare_prompt,
                _file_reference("comparison_report", root / "report.json"),
                _file_reference("comparison_review", root / "comparison-review.md"),
                _file_reference("preflight", root / "preflight.json"),
                _file_reference("recovery", root / "recovery-report.json"),
                *(
                    _file_reference(f"labeled_{path.stem}", path)
                    for path in sorted((root / "labeled").glob("aet_*.json"))
                ),
                *(
                    _file_reference(f"bare_{path.stem}", path)
                    for path in sorted((root / "bare").glob("aet_*.json"))
                ),
            ),
            key=lambda item: item.label,
        )
    )
    (root / "second-opinion-handoff.md").write_text(
        render_answer_format_handoff(
            report,
            recovery=recovery,
            labeled_prompt_text=LABELED_PROMPT_PATH.read_text(encoding="utf-8"),
            bare_prompt_text=BARE_PROMPT_PATH.read_text(encoding="utf-8"),
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
    status = _status(root, AttachmentAnswerFormatPackageStatus.COMPLETE, report=report)
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


def _recover_candidate_probabilities(
    report: AttachmentCandidateRemainderReport,
) -> AttachmentFiniteLabelRecoveryReport:
    observations: list[AttachmentArchivedFiniteLabelObservation] = []
    references: list[AttachmentEvidenceReference] = []
    for case in report.cases:
        for arm_name, observation in (
            (AttachmentCandidateRemainderArm.BASELINE, case.baseline),
            (AttachmentCandidateRemainderArm.REMAINDER, case.remainder),
        ):
            reference = observation.execution_record
            _validate_reference(reference)
            value = _read_json(Path(reference.path))
            model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
            if model_run.execution_receipt is None:
                raise ValueError("CEA-1.10 recovery requires every CEA-1.9 execution receipt.")
            receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
            evidence = finite_label_evidence(receipt)
            sealed_score = (
                observation.probability.attachment_score
                if observation.probability is not None
                else None
            )
            observations.append(
                AttachmentArchivedFiniteLabelObservation(
                    arm=arm_name,
                    task_id=case.task.id,
                    execution_record=reference,
                    observed_answer=observation.decision.answer,
                    raw_output_text=observation.raw_output_text or "",
                    finite_label_evidence=evidence,
                    sealed_attachment_score=sealed_score,
                    sealed_score_matches=(
                        None
                        if sealed_score is None
                        else abs(sealed_score - evidence.attachment_score) <= 1e-12
                    ),
                )
            )
            references.append(reference)
    return build_finite_label_recovery_report(
        inputs=tuple(sorted(references, key=lambda item: item.label)),
        observations=tuple(observations),
    )


def _load_observations(
    *,
    root: Path,
    directory: Path,
    config: PipelineConfig,
    preflight: AttachmentAnswerFormatPreflight,
    arm: AttachmentAnswerFormatArm,
    prompt_sha256: str,
    prompt_id: str,
    configured_generation: tuple[ExecutionSetting, ...],
) -> tuple[AttachmentAnswerFormatObservation, ...]:
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    effective_generation = attachment_edge_filter_generation_parameters(
        configured_generation,
        effective_max_output_tokens=EFFECTIVE_MAX_OUTPUT_TOKENS,
    )
    effective_payload = _generation_payload(effective_generation)
    effective_digest = generation_parameters_digest(effective_generation)
    result: list[AttachmentAnswerFormatObservation] = []
    for residual_task in preflight.tasks:
        task = residual_task.edge_filter_task
        path = directory / f"{task.task_id}.json"
        decision, value = cea14.validate_attachment_edge_filter_execution_record(
            path,
            task,
            archive=archive,
            expected_prompt_sha256=prompt_sha256,
            expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
            expected_prompt_id=prompt_id,
            expected_task_renderer_id=ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
        )
        trace = ExtractionStageTrace.model_validate_json(_canonical_json(value["trace"]))
        model_run = ModelRun.model_validate_json(_canonical_json(value["model_run"]))
        if model_run.generation_parameters != effective_payload:
            raise ValueError("CEA-1.10 execution generation settings drifted.")
        exact_input = trace.input.get("exact_model_input")
        raw_output = trace.output.get("raw_output_text")
        if not isinstance(exact_input, str) or not exact_input:
            raise ValueError("CEA-1.10 execution lacks exact model input.")
        if raw_output is not None and not isinstance(raw_output, str):
            raise ValueError("CEA-1.10 raw output text has invalid shape.")
        forbidden = (
            task.edge.id,
            task.candidate.id,
            task.edge.source_grounded_event_id,
            "expected_answer",
        )
        if any(item in exact_input for item in forbidden):
            raise ValueError("CEA-1.10 model input exposes hidden evaluation data.")
        evidence = None
        identity = None
        output_token_count = None
        if model_run.execution_receipt is not None:
            receipt = model_execution_receipt_from_payload(model_run.execution_receipt)
            if receipt.generation_parameters_digest != effective_digest:
                raise ValueError("CEA-1.10 receipt generation settings drifted.")
            output_token_count = receipt.output_token_count
            try:
                evidence = finite_label_evidence(receipt)
            except ValueError:
                evidence = None
            if evidence is not None:
                identity = receipt.model_identity_digest
        result.append(
            AttachmentAnswerFormatObservation(
                arm=arm,
                task_id=residual_task.id,
                edge_id=task.edge.id,
                decision=decision,
                finite_label_evidence=evidence,
                model_identity_digest=identity,
                execution_record=_file_reference(f"{arm.value}_{residual_task.id}", path),
                exact_model_input=exact_input,
                raw_output_text=raw_output,
                output_token_count=output_token_count,
                elapsed_milliseconds=_elapsed_milliseconds(model_run),
                strict_valid_output=(
                    decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
                    and decision.answer is not None
                ),
            )
        )
    return tuple(result)


def _load_candidate_package(
    root: Path,
) -> tuple[
    dict[str, Any], AttachmentCandidateRemainderPreflight, AttachmentCandidateRemainderReport
]:
    metadata = _read_json(root / "run.json")
    status = _read_json(root / "status.json")
    if metadata.get("status") != "complete" or status.get("status") != "complete":
        raise ValueError("CEA-1.10 requires a complete CEA-1.9 package.")
    checks = {
        "preflight_file_sha256": root / "preflight.json",
        "report_file_sha256": root / "report.json",
        "review_file_sha256": root / "comparison-review.md",
        "handoff_file_sha256": root / "second-opinion-handoff.md",
    }
    for field, path in checks.items():
        expected = metadata.get(field)
        if not path.is_file() or expected != _file_sha(path):
            raise ValueError(f"CEA-1.10 CEA-1.9 evidence digest changed: {field}.")
    review_path = root / "claude-opus-review.md"
    if not review_path.is_file() or not review_path.read_bytes():
        raise ValueError("CEA-1.10 requires the completed CEA-1.9 second opinion.")
    preflight = AttachmentCandidateRemainderPreflight.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    report = AttachmentCandidateRemainderReport.model_validate_json(
        (root / "report.json").read_bytes()
    )
    if preflight.result_fingerprint != metadata.get("preflight_fingerprint"):
        raise ValueError("CEA-1.10 CEA-1.9 preflight fingerprint changed.")
    if report.result_fingerprint != metadata.get("report_fingerprint"):
        raise ValueError("CEA-1.10 CEA-1.9 report fingerprint changed.")
    if report.outcome.value != "inconclusive":
        raise ValueError("CEA-1.10 requires the inconclusive CEA-1.9 outcome.")
    return metadata, preflight, report


def _candidate_package_references(
    root: Path,
    report: AttachmentCandidateRemainderReport,
) -> tuple[AttachmentEvidenceReference, ...]:
    execution_references = tuple(
        item.execution_record for case in report.cases for item in (case.baseline, case.remainder)
    )
    return tuple(
        sorted(
            (
                _file_reference("candidate_handoff", root / "second-opinion-handoff.md"),
                _file_reference("candidate_preflight", root / "preflight.json"),
                _file_reference("candidate_report", root / "report.json"),
                _file_reference("candidate_review", root / "comparison-review.md"),
                _file_reference("candidate_run", root / "run.json"),
                _file_reference("candidate_status", root / "status.json"),
                *execution_references,
            ),
            key=lambda item: item.label,
        )
    )


def _validate_model_identity(
    labeled: tuple[AttachmentAnswerFormatObservation, ...],
    bare: tuple[AttachmentAnswerFormatObservation, ...],
) -> None:
    identities = {
        item.model_identity_digest
        for item in (*labeled, *bare)
        if item.model_identity_digest is not None
    }
    if len(identities) > 1:
        raise ValueError("CEA-1.10 arms used different model identities.")


def _status(
    root: Path,
    status: AttachmentAnswerFormatPackageStatus,
    *,
    report: AttachmentAnswerFormatReport | None = None,
) -> AttachmentAnswerFormatStatus:
    complete = status is AttachmentAnswerFormatPackageStatus.COMPLETE
    return AttachmentAnswerFormatStatus(
        status=status,
        run_root=str(root),
        preflight_path=str(root / "preflight.json"),
        recovery_path=str(root / "recovery-report.json"),
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
        raise ValueError("CEA-1.10 generation settings are not canonically ordered.")
    return settings


def _generation_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in settings}


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    expected = cea14.attachment_edge_filter_runtime_contract(config)
    if expected != metadata.get("runtime_contract"):
        raise ValueError("CEA-1.10 configured runtime differs from sealed evidence.")


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
        raise ValueError(f"CEA-1.10 evidence digest drifted: {reference.label}.")


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
        raise ValueError("CEA-1.10 ModelRun lacks elapsed milliseconds.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
