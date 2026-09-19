#!/usr/bin/env python3
"""Prepare, diagnose, run, and evaluate CEA-1."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    COMPETITIVE_ATTACHMENT_POLICY_ID,
    COMPETITIVE_ATTACHMENT_SCHEMA_ID,
    COMPETITIVE_ATTACHMENT_TASK_RENDERER_ID,
    PARAGRAPH_SEGMENT_V3,
    PROPOSITION_SCOPE_POLICY_ID,
    AttachmentEvidenceReference,
    AttachmentReviewVerificationManifest,
    AttachmentReviewVerificationReport,
    AttachmentReviewVerificationStatus,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentCommand,
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentEventOrder,
    CompetitiveAttachmentFailureAudit,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentPhaseReport,
    CompetitiveDiscriminationApproval,
    CompetitiveDiscriminationCatalog,
    CompetitiveDiscriminationComparison,
    CompetitiveDiscriminationConditionReport,
    CompetitiveDiscriminationPromptArm,
    CompetitiveDiscriminationPromptReference,
    ContextModelProfile,
    ExecutionSetting,
    ExtractionStageTrace,
    SourceSegmentAnalysisUnitInput,
    Uuid4ModelRunIdFactory,
    build_competitive_attachment_matrix,
    build_event_entity_connection_candidates,
    build_proposition_fragment_candidates,
    competitive_attachment_answer_schema_bytes,
    competitive_attachment_matrix_id,
    competitive_attachment_result_sha256,
    create_analysis_unit_from_source_segment,
    run_competitive_event_attachment,
)
from kotekomi_application.competitive_event_attachment_preview import (
    CompetitiveAttachmentArchive,
    CompetitiveAttachmentLedger,
)
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentRepresentationBundle,
    ExtractionTask,
    ModelRun,
    Source,
)
from kotekomi_pipelines.competitive_attachment_discrimination import (
    build_competitive_attachment_failure_audit,
    build_competitive_discrimination_catalog,
    build_competitive_discrimination_condition_report,
    compare_competitive_discrimination_reports,
)
from kotekomi_pipelines.competitive_attachment_review_verification import (
    attachment_review_verification_summary,
    build_attachment_review_verification_report,
    canonical_attachment_review_json,
    render_attachment_review_verification,
    render_attachment_second_opinion_summary,
)
from kotekomi_pipelines.competitive_event_attachment_stage_local import (
    CompetitiveAttachmentBaselineDecision,
    CompetitiveAttachmentDiagnosticApproval,
    CompetitiveAttachmentPreflightReport,
    build_competitive_attachment_oracle,
    build_competitive_attachment_phase_report,
    compare_competitive_attachment_reports,
    load_prompt_v3_baseline,
    validate_competitive_attachment_diagnostic_approval,
)
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
    load_connection_gold_catalog,
)
from kotekomi_pipelines.event_entity_experiment_inputs import (
    load_event_entity_experiment_inputs,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldFragmentRequirement,
    load_proposition_gold_catalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
DEFAULT_PROMPT = REPOSITORY_ROOT / "prompts/competitive_event_attachment_v1.md"
BASELINE_PROMPT = REPOSITORY_ROOT / "prompts/source_grounded_proposition_fragment_membership_v3.md"
DISCRIMINATION_PROMPTS = {
    CompetitiveDiscriminationPromptArm.CONTROL: DEFAULT_PROMPT,
    CompetitiveDiscriminationPromptArm.SCOPE: REPOSITORY_ROOT
    / "prompts/competitive_event_attachment_scope_v2.md",
    CompetitiveDiscriminationPromptArm.EXAMPLES: REPOSITORY_ROOT
    / "prompts/competitive_event_attachment_examples_v2.md",
    CompetitiveDiscriminationPromptArm.COMBINED: REPOSITORY_ROOT
    / "prompts/competitive_event_attachment_combined_v2.md",
}


class _ExperimentLedger:
    """Ephemeral repository that makes accepted-state writes impossible."""

    def __init__(
        self,
        source: Source,
        document: Document,
        bundle: DocumentRepresentationBundle,
    ) -> None:
        self.source = source
        self.document = document
        self.bundle = bundle
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.context_manifests: dict[str, ContextManifestArtifact] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.accepted_ledger_change_count = 0

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.context_manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.context_manifests.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.context_manifests[manifest.id] = manifest
        self.analysis_units.update({item.id: item for item in child_analysis_units})

    def save_extraction_task(self, record: ExtractionTask) -> None:
        self.extraction_tasks[record.id] = record

    def save_model_run(self, record: ModelRun) -> None:
        self.model_runs[record.id] = record

    def commit_successful_model_run_and_candidate_batch(
        self, *, model_run: ModelRun, batch: object
    ) -> None:
        del model_run, batch
        self.accepted_ledger_change_count += 1
        raise AssertionError("CEA-1 cannot write accepted Ledger state.")


@dataclass(frozen=True)
class _CanonicalState:
    source: Source
    document: Document
    bundle: DocumentRepresentationBundle


@dataclass(frozen=True)
class _Cea1Evidence:
    root: Path
    report_path: Path
    report_bytes: bytes
    report: CompetitiveAttachmentPhaseReport
    inputs: tuple[EventEntityExperimentInput, ...]
    input_matrices: tuple[CompetitiveAttachmentMatrix, ...]
    terminal_matrices: tuple[CompetitiveAttachmentMatrix, ...]
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]
    baseline: dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]]
    gold_bindings: dict[str, str]
    source_text_by_digest: dict[str, str]


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--coverage-report-id", required=True)
    prepare.add_argument("--phase", choices=("development", "validation"), required=True)
    prepare.add_argument("--repetition", type=int, required=True)
    prepare.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    prepare.add_argument("--baseline-run-root", type=Path, required=True)
    prepare.add_argument("--development-report", type=Path, action="append", default=[])
    prepare.add_argument("--run-root", type=Path, required=True)

    diagnose = commands.add_parser("diagnose")
    diagnose.add_argument("--config", type=Path, required=True)
    diagnose.add_argument("--run-root", type=Path, required=True)
    diagnose.add_argument("--approve-reviewer")

    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    run.add_argument("--diagnostic-approval", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    finalize.add_argument("--run-root", type=Path, required=True)

    compare = commands.add_parser("compare")
    compare.add_argument("--development-report", type=Path, action="append", required=True)
    compare.add_argument("--validation-report", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)

    discrimination_prepare = commands.add_parser("prepare-discrimination")
    discrimination_prepare.add_argument("--development-run-root", type=Path, required=True)
    discrimination_prepare.add_argument("--validation-run-root", type=Path, required=True)
    discrimination_prepare.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    discrimination_prepare.add_argument("--run-root", type=Path, required=True)

    discrimination_approve = commands.add_parser("approve-discrimination")
    discrimination_approve.add_argument("--run-root", type=Path, required=True)
    discrimination_approve.add_argument("--reviewer", required=True)

    discrimination_run = commands.add_parser("run-discrimination")
    discrimination_run.add_argument("--config", type=Path, required=True)
    discrimination_run.add_argument("--run-root", type=Path, required=True)
    discrimination_run.add_argument("--approval", type=Path, required=True)

    verify_review = commands.add_parser("verify-review-findings")
    verify_review.add_argument("--development-run-root", type=Path, required=True)
    verify_review.add_argument("--validation-run-root", type=Path, required=True)
    verify_review.add_argument("--discrimination-run-root", type=Path, required=True)
    verify_review.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    verify_review.add_argument("--output-root", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "diagnose":
        return _diagnose(args)
    if args.command == "run":
        return _run(args)
    if args.command == "finalize":
        return _finalize(args)
    if args.command == "compare":
        return _compare(args)
    if args.command == "prepare-discrimination":
        return _prepare_discrimination(args)
    if args.command == "approve-discrimination":
        return _approve_discrimination(args)
    if args.command == "run-discrimination":
        return _run_discrimination(args)
    return _verify_review_findings(args)


def _prepare(args: argparse.Namespace) -> int:
    _validate_repetition(args.phase, args.repetition)
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    gold_path = args.gold.resolve()
    catalog = load_proposition_gold_catalog(gold_path, repository_root=REPOSITORY_ROOT)
    if catalog.review_status.value != "approved":
        raise ValueError("CEA-1 requires approved Proposition Gold.")
    connection_path = (REPOSITORY_ROOT / catalog.connection_gold_path).resolve()
    connection, _, trigger = load_connection_gold_catalog(
        connection_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
    )
    selected_connection = tuple(item for item in connection.events if item.phase == args.phase)
    config = _config(args.config)
    execution_contract = _execution_contract(config)
    canonical = load_event_entity_experiment_inputs(
        config=config,
        coverage_report_id=args.coverage_report_id,
        selected_gold=selected_connection,
        trigger_gold=trigger,
    )
    _write_json(
        root / "canonical-state.json",
        {
            "source": canonical.source.model_dump(mode="json"),
            "document": canonical.document.model_dump(mode="json"),
            "bundle": canonical.bundle.model_dump(mode="json"),
        },
    )
    _write_jsonl(root / "inputs.jsonl", [item.model_dump(mode="json") for item in canonical.inputs])
    matrices, bindings = _build_matrices(canonical.inputs)
    _write_json(root / "matrices.json", [item.model_dump(mode="json") for item in matrices])
    _write_json(root / "gold-bindings.json", bindings)
    oracle, preflight = build_competitive_attachment_oracle(
        catalog=catalog,
        phase=args.phase,
        matrices=matrices,
        source_grounded_event_by_gold_id=bindings,
    )
    _write_json(
        root / "oracle.json",
        {
            matrix_id: [item.model_dump(mode="json") for item in decisions]
            for matrix_id, decisions in sorted(oracle.items())
        },
    )
    _write_json(root / "preflight.json", preflight.model_dump(mode="json"))
    (root / "preflight-review.md").write_text(
        _render_preflight_review(preflight, matrices), encoding="utf-8"
    )
    baseline_root = args.baseline_run_root.resolve()
    baseline = load_prompt_v3_baseline(
        run_root=baseline_root,
        phase=args.phase,
        matrices=matrices,
        gold_event_to_source_grounded_event=bindings,
        expected_gold_sha256=_sha(gold_path.read_bytes()),
        expected_prompt_sha256=_sha(BASELINE_PROMPT.read_bytes()),
        expected_runtime=_runtime_contract(config),
    )
    _write_json(
        root / "baseline.json",
        {
            matrix_id: [item.model_dump(mode="json") for item in decisions]
            for matrix_id, decisions in sorted(baseline.items())
        },
    )
    diagnostic = _diagnostic_catalog(catalog, matrices, oracle, bindings, args.phase)
    _write_json(root / "diagnostic-catalog.json", diagnostic)
    expected_source_segments = 6 if args.phase == "development" else 13
    if preflight.event_count != 20 or preflight.source_segment_count != expected_source_segments:
        raise ValueError("CEA-1 prepared input does not match the approved forty-Event split.")
    development_contract_sha256s: tuple[str, ...] = ()
    if args.phase == "validation":
        development_reports = tuple(path.resolve() for path in args.development_report)
        if len(development_reports) != 3:
            raise ValueError("Validation prepare requires three finalized development reports.")
        reports = tuple(_load_phase_report(path) for path in development_reports)
        if (
            any(item.phase != "development" for item in reports)
            or len({item.result_fingerprint for item in reports}) != 1
        ):
            raise ValueError("Validation requires stable finalized development evidence.")
        development_metadata = tuple(_load_metadata(path.parent) for path in development_reports)
        for path, item in zip(development_reports, development_metadata, strict=True):
            _validate_static_contract(path.parent, item)
            manifest = _read_json(path.parent / "manifest.json")
            if manifest.get("report_sha256") != _sha(path.read_bytes()):
                raise ValueError("Validation development receipt chain is invalid.")
        if (
            {item["status"] for item in development_metadata} != {"finalized"}
            or {item["phase"] for item in development_metadata} != {"development"}
            or {item["repetition"] for item in development_metadata} != {1, 2, 3}
            or any(
                item.get("execution_contract") != execution_contract
                for item in development_metadata
            )
        ):
            raise ValueError("Validation requires one frozen development execution contract.")
        development_contract_sha256s = tuple(
            _sha(path.read_bytes()) for path in development_reports
        )
    metadata = {
        "schema_version": "competitive_attachment_experiment_run_v1",
        "status": "prepared",
        "phase": args.phase,
        "repetition": args.repetition,
        "coverage_report_id": canonical.coverage.id,
        "coverage_report_sha256": _sha(canonical.coverage_payload),
        "gold_path": _relative_or_absolute(gold_path),
        "gold_sha256": _sha(gold_path.read_bytes()),
        "prompt_path": _relative_or_absolute(DEFAULT_PROMPT),
        "prompt_sha256": _sha(DEFAULT_PROMPT.read_bytes()),
        "schema_id": COMPETITIVE_ATTACHMENT_SCHEMA_ID,
        "schema_sha256": _schema_set_sha256(matrices),
        "policy_id": COMPETITIVE_ATTACHMENT_POLICY_ID,
        "execution_contract": execution_contract,
        "execution_contract_sha256": _sha(_canonical_json(execution_contract)),
        "runtime": _runtime_contract(config),
        "baseline_run_root": str(baseline_root),
        "baseline_run_sha256": _sha((baseline_root / "run.json").read_bytes()),
        "development_contract_sha256s": list(development_contract_sha256s),
        "canonical_state_sha256": _sha((root / "canonical-state.json").read_bytes()),
        "inputs_sha256": _sha((root / "inputs.jsonl").read_bytes()),
        "matrices_sha256": _sha((root / "matrices.json").read_bytes()),
        "bindings_sha256": _sha((root / "gold-bindings.json").read_bytes()),
        "oracle_sha256": _sha((root / "oracle.json").read_bytes()),
        "baseline_sha256": _sha((root / "baseline.json").read_bytes()),
        "preflight_sha256": _sha((root / "preflight.json").read_bytes()),
        "diagnostic_catalog_sha256": _sha((root / "diagnostic-catalog.json").read_bytes()),
        "matrix_count": len(matrices),
        "candidate_count": sum(len(item.candidates) for item in matrices),
    }
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "candidate_count": metadata["candidate_count"],
                "matrix_count": len(matrices),
                "phase": args.phase,
                "preflight": str(root / "preflight.json"),
                "preflight_review": str(root / "preflight-review.md"),
                "run_root": str(root),
                "status": "prepared" if preflight.passed else "candidate_gap",
            },
            sort_keys=True,
        )
    )
    return 0 if preflight.passed else 2


def _diagnose(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root)
    if metadata["phase"] != "development" or metadata["repetition"] != 1:
        raise ValueError("CEA-1 diagnostic runs only on development repetition 1.")
    _validate_static_contract(root, metadata)
    if args.approve_reviewer is not None:
        if not args.approve_reviewer.strip():
            raise ValueError("Diagnostic approval requires a reviewer name.")
        result_path = root / "diagnostic-result.json"
        review_path = root / "diagnostic-review.md"
        if not result_path.is_file() or not review_path.is_file():
            raise ValueError("Execute the CEA-1 diagnostic before approving it.")
        result = _read_json(result_path)
        if result.get("status") != "review_required" or not result.get("approval_ready"):
            raise ValueError("CEA-1 diagnostic evidence is not approval-ready.")
        approval = CompetitiveAttachmentDiagnosticApproval(
            reviewer=args.approve_reviewer.strip(),
            diagnostic_result_sha256=_sha(result_path.read_bytes()),
            diagnostic_review_sha256=_sha(review_path.read_bytes()),
            prompt_sha256=cast(str, metadata["prompt_sha256"]),
            execution_contract_sha256=cast(str, metadata["execution_contract_sha256"]),
        )
        approval_payload = approval.model_dump(mode="json")
        _write_json(root / "diagnostic-approval.json", approval_payload)
        print(
            json.dumps(
                {
                    "approval": str(root / "diagnostic-approval.json"),
                    **approval_payload,
                },
                sort_keys=True,
            )
        )
        return 0
    config = _config(args.config)
    _validate_runtime(config, metadata)
    matrices = _load_matrices(root / "matrices.json")
    catalog = cast(list[dict[str, Any]], _read_json(root / "diagnostic-catalog.json")["cases"])
    candidate_ids = {str(item["candidate_id"]) for item in catalog}
    subset = tuple(
        _matrix_subset(item, candidate_ids)
        for item in matrices
        if any(candidate.id in candidate_ids for candidate in item.candidates)
    )
    records = _execute_matrices(root, config, subset, output_directory="diagnostic-matrices")
    finite = all(
        decision.status
        in {
            CompetitiveAttachmentDecisionStatus.COMPLETE,
            CompetitiveAttachmentDecisionStatus.UNCLEAR,
        }
        for matrix, _ in records
        for decision in matrix.decisions
    )
    case_results = _diagnostic_case_results(catalog, records, root)
    multi_event_retained = all(
        item["exact"] for item in case_results if item["category"] == "multi_event"
    )
    approval_ready = finite and multi_event_retained
    result = {
        "schema_version": "competitive_attachment_diagnostic_result_v1",
        "case_count": len(catalog),
        "cases": case_results,
        "approval_ready": approval_ready,
        "finite_outputs_valid": finite,
        "multi_event_retained": multi_event_retained,
        "status": "review_required",
        "result_sha256s": [digest for _, digest in records],
    }
    _write_json(root / "diagnostic-result.json", result)
    (root / "diagnostic-review.md").write_text(
        _render_diagnostic_review(catalog, records, root), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                **result,
                "review": str(root / "diagnostic-review.md"),
                "result": str(root / "diagnostic-result.json"),
            },
            sort_keys=True,
        )
    )
    return 0 if approval_ready else 1


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root)
    if metadata["status"] not in {"prepared", "run_complete"}:
        raise ValueError("CEA-1 run is not prepared.")
    _validate_static_contract(root, metadata)
    _validate_diagnostic_approval(args.diagnostic_approval.resolve(), metadata)
    config = _config(args.config)
    _validate_runtime(config, metadata)
    matrices = _load_matrices(root / "matrices.json")
    _execute_matrices(root, config, matrices, output_directory="matrices")
    metadata["status"] = "run_complete"
    metadata["diagnostic_approval_sha256"] = _sha(args.diagnostic_approval.read_bytes())
    _write_json(root / "run.json", metadata)
    return 0


def _finalize(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root)
    if metadata["status"] not in {"run_complete", "finalized"}:
        raise ValueError("CEA-1 experiment has not completed model execution.")
    _validate_static_contract(root, metadata)
    gold_path = args.gold.resolve()
    if metadata["gold_path"] != _relative_or_absolute(gold_path):
        raise ValueError("CEA-1 Gold path changed after preparation.")
    catalog = load_proposition_gold_catalog(gold_path, repository_root=REPOSITORY_ROOT)
    matrices = _load_terminal_matrices(root / "matrices", _load_matrices(root / "matrices.json"))
    oracle = _load_oracle(root / "oracle.json")
    baseline = _load_baseline(root / "baseline.json")
    bindings = {
        str(key): str(value) for key, value in _read_json(root / "gold-bindings.json").items()
    }
    entity_occurrences = _entity_occurrences(
        catalog, cast(Literal["development", "validation"], metadata["phase"])
    )
    model_runs = tuple(
        ModelRun.model_validate_json(_canonical_json(item))
        for path in sorted((root / "matrices").glob("*.json"))
        for item in cast(list[object], _read_json(path)["model_runs"])
    )
    report = build_competitive_attachment_phase_report(
        catalog=catalog,
        catalog_sha256=_sha(gold_path.read_bytes()),
        phase=cast(Literal["development", "validation"], metadata["phase"]),
        repetition=_required_int(metadata["repetition"], "repetition"),
        matrices=matrices,
        gold_by_matrix=oracle,
        baseline_by_matrix=baseline,
        source_grounded_event_by_gold_id=bindings,
        entity_occurrences_by_gold_event=entity_occurrences,
        model_execution_count=len(model_runs),
        input_token_count=sum(
            _receipt_count(item, "input_token_count")
            for item in model_runs
            if item.execution_receipt is not None
        ),
        output_token_count=sum(
            _receipt_count(item, "output_token_count")
            for item in model_runs
            if item.execution_receipt is not None
        ),
        elapsed_milliseconds=sum(
            _required_int(item.execution_diagnostics["elapsed_milliseconds"], "elapsed")
            for item in model_runs
        ),
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "review.md").write_text(
        _render_phase_review(report, matrices, oracle, baseline), encoding="utf-8"
    )
    manifest = {
        "schema_version": "competitive_attachment_manifest_v1",
        "phase": report.phase,
        "repetition": report.repetition,
        "report_sha256": _sha((root / "report.json").read_bytes()),
        "review_sha256": _sha((root / "review.md").read_bytes()),
        "result_fingerprint": report.result_fingerprint,
        "model_execution_count": report.model_execution_count,
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
    }
    _write_json(root / "manifest.json", manifest)
    if report.phase == "validation":
        (root / "FINALIZED").write_text(_sha(_canonical_json(manifest)), encoding="utf-8")
    metadata["status"] = "finalized"
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "metrics": report.metrics.model_dump(mode="json"),
                "report": str(root / "report.json"),
                "review": str(root / "review.md"),
            },
            sort_keys=True,
        )
    )
    return 0


def _compare(args: argparse.Namespace) -> int:
    development_paths = tuple(path.resolve() for path in args.development_report)
    development = tuple(_load_phase_report(path) for path in development_paths)
    validation_path = args.validation_report.resolve()
    validation = _load_phase_report(validation_path)
    result = compare_competitive_attachment_reports(
        development,
        validation,
        development_report_sha256s=tuple(_sha(path.read_bytes()) for path in development_paths),
        validation_report_sha256=_sha(validation_path.read_bytes()),
    )
    _write_json(args.output.resolve(), result.model_dump(mode="json"))
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    return 0


def _prepare_discrimination(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.1 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    development = _load_cea1_evidence(args.development_run_root.resolve())
    validation = _load_cea1_evidence(args.validation_run_root.resolve())
    if development.report.phase != "development" or development.report.repetition != 1:
        raise ValueError("CEA-1.1 requires CEA-1 development repetition one.")
    if validation.report.phase != "validation" or validation.report.repetition != 1:
        raise ValueError("CEA-1.1 requires the frozen CEA-1 validation repetition.")
    gold_path = args.gold.resolve()
    gold = load_proposition_gold_catalog(gold_path, repository_root=REPOSITORY_ROOT)
    audit = build_competitive_attachment_failure_audit(
        report_bytes=validation.report_bytes,
        report=validation.report,
        matrices=validation.terminal_matrices,
        oracle=validation.oracle,
        baseline=validation.baseline,
        catalog=gold,
        gold_bindings=validation.gold_bindings,
        source_text_by_digest=validation.source_text_by_digest,
    )
    expected_counts = (65, 17, 25, 13, 5, 5)
    observed_counts = (
        audit.error_count,
        audit.complete_omission_count,
        audit.under_attachment_count,
        audit.false_positive_none_count,
        audit.over_attachment_count,
        audit.wrong_set_substitution_count,
    )
    if observed_counts != expected_counts:
        raise ValueError(f"CEA-1.1 failure audit did not reproduce CEA-1: {observed_counts!r}.")
    catalog = build_competitive_discrimination_catalog(
        report_bytes=development.report_bytes,
        report=development.report,
        matrices=development.terminal_matrices,
        oracle=development.oracle,
        source_text_by_digest=development.source_text_by_digest,
    )
    _validate_prompt_factors()
    prompt_references = tuple(
        CompetitiveDiscriminationPromptReference(
            arm=arm,
            prompt_id=f"competitive_event_attachment_cea11_{arm.value}_v1",
            prompt_sha256=_sha(path.read_bytes()),
        )
        for arm, path in DISCRIMINATION_PROMPTS.items()
    )
    _write_json(root / "failure-audit.json", audit.model_dump(mode="json"))
    (root / "failure-audit-review.md").write_text(
        _render_failure_audit_review(audit), encoding="utf-8"
    )
    _write_json(root / "catalog.json", catalog.model_dump(mode="json"))
    (root / "catalog-review.md").write_text(
        _render_discrimination_catalog_review(
            catalog,
            development.terminal_matrices,
            development.oracle,
            development.source_text_by_digest,
        ),
        encoding="utf-8",
    )
    _write_json(
        root / "prompt-manifest.json",
        {
            "schema_version": "competitive_discrimination_prompt_manifest_v1",
            "prompts": [item.model_dump(mode="json") for item in prompt_references],
        },
    )
    (root / "prompt-review.md").write_text(
        _render_prompt_review(prompt_references), encoding="utf-8"
    )
    metadata = {
        "schema_version": "competitive_discrimination_run_v1",
        "status": "prepared",
        "development_root": str(development.root),
        "development_report_sha256": _sha(development.report_bytes),
        "validation_root": str(validation.root),
        "validation_report_sha256": _sha(validation.report_bytes),
        "gold_path": _relative_or_absolute(gold_path),
        "gold_sha256": _sha(gold_path.read_bytes()),
        "failure_audit_sha256": _sha((root / "failure-audit.json").read_bytes()),
        "failure_audit_review_sha256": _sha((root / "failure-audit-review.md").read_bytes()),
        "catalog_sha256": _sha((root / "catalog.json").read_bytes()),
        "catalog_review_sha256": _sha((root / "catalog-review.md").read_bytes()),
        "prompt_manifest_sha256": _sha((root / "prompt-manifest.json").read_bytes()),
        "prompt_review_sha256": _sha((root / "prompt-review.md").read_bytes()),
    }
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "audit": str(root / "failure-audit.json"),
                "audit_review": str(root / "failure-audit-review.md"),
                "catalog": str(root / "catalog.json"),
                "catalog_review": str(root / "catalog-review.md"),
                "prompt_review": str(root / "prompt-review.md"),
                "status": "prepared",
            },
            sort_keys=True,
        )
    )
    return 0


def _approve_discrimination(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_discrimination_metadata(root)
    _validate_discrimination_prepared(root, metadata)
    manifest = _read_json(root / "prompt-manifest.json")
    prompts = tuple(
        CompetitiveDiscriminationPromptReference.model_validate_json(_canonical_json(item))
        for item in cast(list[object], manifest.get("prompts"))
    )
    approval = CompetitiveDiscriminationApproval(
        reviewer=args.reviewer,
        failure_audit_sha256=cast(str, metadata["failure_audit_sha256"]),
        catalog_sha256=cast(str, metadata["catalog_sha256"]),
        prompts=prompts,
    )
    _write_json(root / "approval.json", approval.model_dump(mode="json"))
    metadata["status"] = "approved"
    metadata["approval_sha256"] = _sha((root / "approval.json").read_bytes())
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "approval": str(root / "approval.json"),
                "reviewer": approval.reviewer,
                "status": "approved",
            },
            sort_keys=True,
        )
    )
    return 0


def _run_discrimination(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_discrimination_metadata(root)
    _validate_discrimination_prepared(root, metadata)
    approval_path = args.approval.resolve()
    approval = CompetitiveDiscriminationApproval.model_validate_json(approval_path.read_bytes())
    if metadata.get("approval_sha256") != _sha(approval_path.read_bytes()):
        raise ValueError("CEA-1.1 approval does not match its prepared run.")
    if (
        approval.failure_audit_sha256 != metadata["failure_audit_sha256"]
        or approval.catalog_sha256 != metadata["catalog_sha256"]
    ):
        raise ValueError("CEA-1.1 approval evidence changed after review.")
    config = _config(args.config)
    development = _load_cea1_evidence(Path(cast(str, metadata["development_root"])))
    if _sha(development.report_bytes) != metadata["development_report_sha256"]:
        raise ValueError("CEA-1.1 development evidence changed after preparation.")
    gold_path = (REPOSITORY_ROOT / cast(str, metadata["gold_path"])).resolve()
    if not gold_path.is_file():
        gold_path = Path(cast(str, metadata["gold_path"])).resolve()
    if _sha(gold_path.read_bytes()) != metadata["gold_sha256"]:
        raise ValueError("CEA-1.1 Gold changed after preparation.")
    gold = load_proposition_gold_catalog(gold_path, repository_root=REPOSITORY_ROOT)
    catalog = CompetitiveDiscriminationCatalog.model_validate_json(
        (root / "catalog.json").read_bytes()
    )
    selected_by_matrix: dict[str, set[str]] = {}
    for item in catalog.cases:
        selected_by_matrix.setdefault(item.matrix_id, set()).add(item.candidate_id)
    selected_matrices = tuple(
        _matrix_subset(matrix, selected_by_matrix[matrix.id])
        for matrix in development.input_matrices
        if matrix.id in selected_by_matrix
    )
    selected_candidate_ids = {
        candidate.id for matrix in selected_matrices for candidate in matrix.candidates
    }
    if selected_candidate_ids != {item.candidate_id for item in catalog.cases}:
        raise ValueError("CEA-1.1 selected Candidate inventory changed after approval.")
    for reference in approval.prompts:
        if _sha(DISCRIMINATION_PROMPTS[reference.arm].read_bytes()) != reference.prompt_sha256:
            raise ValueError(f"CEA-1.1 prompt changed after approval: {reference.arm.value}.")
    runtime_contract = _runtime_contract(config)
    existing_runtime_contract = metadata.get("runtime")
    if existing_runtime_contract is not None and existing_runtime_contract != runtime_contract:
        raise ValueError("CEA-1.1 runtime configuration changed after execution began.")
    if existing_runtime_contract is None:
        metadata["runtime"] = runtime_contract
        metadata["generation_parameters"] = [
            {"key": item.key, "value": item.value} for item in _generation(config)
        ]
        metadata["status"] = "running"
        _write_json(root / "run.json", metadata)
    conditions = tuple(
        (arm, order, repetition)
        for repetition in (1, 2)
        for arm in CompetitiveDiscriminationPromptArm
        if repetition == 1 or arm is CompetitiveDiscriminationPromptArm.COMBINED
        for order in (
            CompetitiveAttachmentEventOrder.SOURCE,
            CompetitiveAttachmentEventOrder.REVERSED,
        )
    )
    reports: list[CompetitiveDiscriminationConditionReport] = []
    report_sha256s: dict[tuple[CompetitiveDiscriminationPromptArm, str, int], str] = {}
    for arm, order, repetition in conditions:
        prompt_path = DISCRIMINATION_PROMPTS[arm]
        prompt = prompt_path.read_bytes()
        reference = next(item for item in approval.prompts if item.arm is arm)
        if _sha(prompt) != reference.prompt_sha256:
            raise ValueError(f"CEA-1.1 prompt changed after approval: {arm.value}.")
        directory = f"conditions/{arm.value}-{order.value}-r{repetition}"
        terminal = _execute_matrices(
            root,
            config,
            selected_matrices,
            output_directory=directory,
            evidence_root=development.root,
            prompt_bytes=prompt,
            prompt_id=reference.prompt_id,
            event_order=order,
        )
        terminal_matrices = tuple(item[0] for item in terminal)
        model_runs = _condition_model_runs(root / directory)
        report = build_competitive_discrimination_condition_report(
            arm=arm,
            event_order=order.value,
            repetition=repetition,
            prompt_bytes=prompt,
            catalog=catalog,
            matrices=terminal_matrices,
            oracle=development.oracle,
            gold_catalog=gold,
            gold_bindings=development.gold_bindings,
            model_runs=model_runs,
        )
        report_path = root / directory / "report.json"
        _write_json(report_path, report.model_dump(mode="json"))
        (root / directory / "review.md").write_text(
            _render_condition_review(report), encoding="utf-8"
        )
        reports.append(report)
        report_sha256s[(arm, order.value, repetition)] = _sha(report_path.read_bytes())
    comparison = compare_competitive_discrimination_reports(
        failure_audit_sha256=cast(str, metadata["failure_audit_sha256"]),
        catalog_sha256=cast(str, metadata["catalog_sha256"]),
        reports=tuple(reports),
        report_sha256s=report_sha256s,
    )
    _write_json(root / "comparison.json", comparison.model_dump(mode="json"))
    (root / "comparison-review.md").write_text(
        _render_discrimination_comparison(comparison, tuple(reports)), encoding="utf-8"
    )
    metadata["status"] = "complete"
    metadata["comparison_sha256"] = _sha((root / "comparison.json").read_bytes())
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "comparison": str(root / "comparison.json"),
                "outcome": comparison.outcome,
                "review": str(root / "comparison-review.md"),
                "status": "complete",
            },
            sort_keys=True,
        )
    )
    return 0


def _verify_review_findings(args: argparse.Namespace) -> int:
    root = args.output_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.2 requires an absent or empty output root.")
    root.mkdir(parents=True, exist_ok=True)

    development = _validated_cea1_evidence(
        args.development_run_root.resolve(),
        expected_phase="development",
    )
    validation = _validated_cea1_evidence(
        args.validation_run_root.resolve(),
        expected_phase="validation",
    )
    discrimination_root = args.discrimination_run_root.resolve()
    (
        failure_audit,
        discrimination_catalog,
        condition_matrices,
    ) = _validated_discrimination_evidence(
        discrimination_root,
        development=development,
        validation=validation,
    )
    gold_path = args.gold.resolve()
    gold_catalog = load_proposition_gold_catalog(
        gold_path,
        repository_root=REPOSITORY_ROOT,
    )
    if gold_catalog.review_status.value != "approved":
        raise ValueError("CEA-1.2 requires approved Proposition Gold.")
    entity_occurrences_by_event = {
        evidence.gold_bindings[gold_event_id]: occurrences
        for phase, evidence in (
            ("development", development),
            ("validation", validation),
        )
        for gold_event_id, occurrences in _entity_occurrences(
            gold_catalog,
            cast(Literal["development", "validation"], phase),
        ).items()
    }

    second_opinion_path = REPOSITORY_ROOT / "2nd-opinion-3.md"
    tdd_path = (
        REPOSITORY_ROOT / "docs/2026-09-18-competitive-event-attachment-review-verification.md"
    )
    input_references = tuple(
        sorted(
            (
                _evidence_reference(
                    "cea1_development_bindings", development.root / "gold-bindings.json"
                ),
                _evidence_reference("cea1_development_inputs", development.root / "inputs.jsonl"),
                _evidence_reference(
                    "cea1_development_manifest", development.root / "manifest.json"
                ),
                _evidence_reference(
                    "cea1_development_matrices", development.root / "matrices.json"
                ),
                _evidence_reference("cea1_development_oracle", development.root / "oracle.json"),
                _evidence_reference("cea1_development_report", development.report_path),
                _directory_evidence_reference("cea1_development_run_root", development.root),
                _evidence_reference(
                    "cea1_validation_bindings", validation.root / "gold-bindings.json"
                ),
                _evidence_reference("cea1_validation_inputs", validation.root / "inputs.jsonl"),
                _evidence_reference("cea1_validation_manifest", validation.root / "manifest.json"),
                _evidence_reference("cea1_validation_matrices", validation.root / "matrices.json"),
                _evidence_reference("cea1_validation_oracle", validation.root / "oracle.json"),
                _evidence_reference("cea1_validation_report", validation.report_path),
                _directory_evidence_reference("cea1_validation_run_root", validation.root),
                _evidence_reference(
                    "discrimination_approval", discrimination_root / "approval.json"
                ),
                _evidence_reference("discrimination_catalog", discrimination_root / "catalog.json"),
                _evidence_reference(
                    "discrimination_comparison", discrimination_root / "comparison.json"
                ),
                _directory_evidence_reference(
                    "discrimination_conditions",
                    discrimination_root / "conditions",
                ),
                _evidence_reference(
                    "discrimination_failure_audit", discrimination_root / "failure-audit.json"
                ),
                _evidence_reference("discrimination_run", discrimination_root / "run.json"),
                _directory_evidence_reference("discrimination_run_root", discrimination_root),
                _evidence_reference("gold_catalog", gold_path),
                _evidence_reference(
                    "prompt_combined",
                    DISCRIMINATION_PROMPTS[CompetitiveDiscriminationPromptArm.COMBINED],
                ),
                _evidence_reference(
                    "prompt_control",
                    DISCRIMINATION_PROMPTS[CompetitiveDiscriminationPromptArm.CONTROL],
                ),
                _evidence_reference(
                    "prompt_examples",
                    DISCRIMINATION_PROMPTS[CompetitiveDiscriminationPromptArm.EXAMPLES],
                ),
                _evidence_reference(
                    "prompt_scope", DISCRIMINATION_PROMPTS[CompetitiveDiscriminationPromptArm.SCOPE]
                ),
                _evidence_reference(
                    "review_policy_application",
                    REPOSITORY_ROOT
                    / "packages"
                    / "application"
                    / "src"
                    / "kotekomi_application"
                    / "competitive_attachment_review_verification.py",
                ),
                _evidence_reference(
                    "review_policy_predicate_arguments",
                    REPOSITORY_ROOT
                    / "packages"
                    / "application"
                    / "src"
                    / "kotekomi_application"
                    / "event_entity_predicate_arguments.py",
                ),
                _evidence_reference(
                    "review_policy_pipeline",
                    REPOSITORY_ROOT
                    / "packages"
                    / "pipelines"
                    / "src"
                    / "kotekomi_pipelines"
                    / "competitive_attachment_review_verification.py",
                ),
                _evidence_reference(
                    "review_policy_runner",
                    Path(__file__).resolve(),
                ),
                _evidence_reference("second_opinion", second_opinion_path),
            ),
            key=lambda item: item.label,
        )
    )
    report = build_attachment_review_verification_report(
        input_references=input_references,
        development_report=development.report,
        development_matrices=development.input_matrices,
        development_oracle=development.oracle,
        development_inputs=development.inputs,
        development_bindings=development.gold_bindings,
        validation_report=validation.report,
        validation_matrices=validation.input_matrices,
        validation_oracle=validation.oracle,
        validation_inputs=validation.inputs,
        validation_bindings=validation.gold_bindings,
        entity_occurrences_by_event=entity_occurrences_by_event,
        gold_catalog=gold_catalog,
        failure_audit=failure_audit,
        discrimination_catalog=discrimination_catalog,
        condition_matrices=condition_matrices,
        prompt_bytes_by_arm={
            arm.value: path.read_bytes() for arm, path in DISCRIMINATION_PROMPTS.items()
        },
    )
    source_text_by_digest = {
        item.event.source_text_sha256: item.source_text
        for item in (*development.inputs, *validation.inputs)
    }
    report_path = root / "report.json"
    review_path = root / "review.md"
    summary_path = root / "summary.json"
    handoff_path = root / "second-opinion-summary.md"
    status_path = root / "status.json"
    manifest_path = root / "manifest.json"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(
        render_attachment_review_verification(
            report,
            source_text_by_digest=source_text_by_digest,
        ),
        encoding="utf-8",
    )
    _write_json(summary_path, attachment_review_verification_summary(report))
    handoff_path.write_text(
        render_attachment_second_opinion_summary(report),
        encoding="utf-8",
    )
    status = AttachmentReviewVerificationStatus(
        result_fingerprint=report.result_fingerprint,
        report_path=report_path.name,
        review_path=review_path.name,
        summary_path=summary_path.name,
        second_opinion_summary_path=handoff_path.name,
    )
    _write_json(status_path, status.model_dump(mode="json"))
    outputs = tuple(
        sorted(
            (
                _output_evidence_reference("report", report_path),
                _output_evidence_reference("review", review_path),
                _output_evidence_reference("second_opinion_summary", handoff_path),
                _output_evidence_reference("status", status_path),
                _output_evidence_reference("summary", summary_path),
            ),
            key=lambda item: item.label,
        )
    )
    manifest = AttachmentReviewVerificationManifest(
        tdd=_evidence_reference("tdd", tdd_path),
        inputs=input_references,
        outputs=outputs,
        result_fingerprint=report.result_fingerprint,
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))

    AttachmentReviewVerificationReport.model_validate_json(report_path.read_bytes())
    AttachmentReviewVerificationStatus.model_validate_json(status_path.read_bytes())
    AttachmentReviewVerificationManifest.model_validate_json(manifest_path.read_bytes())
    if (
        report_path.read_bytes()
        != canonical_attachment_review_json(report.model_dump(mode="json")) + b"\n"
    ):
        raise ValueError("CEA-1.2 report serialization is not canonical.")
    print(
        json.dumps(
            {
                "handoff": str(handoff_path),
                "manifest": str(manifest_path),
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


def _validated_cea1_evidence(
    root: Path,
    *,
    expected_phase: Literal["development", "validation"],
) -> _Cea1Evidence:
    metadata = _load_metadata(root)
    if (
        metadata.get("status") != "finalized"
        or metadata.get("phase") != expected_phase
        or metadata.get("repetition") != 1
    ):
        raise ValueError(f"CEA-1.2 requires finalized {expected_phase} repetition one.")
    _validate_static_contract(root, metadata)
    evidence = _load_cea1_evidence(root)
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    expected_manifest = {
        "schema_version": "competitive_attachment_manifest_v1",
        "phase": expected_phase,
        "repetition": 1,
        "report_sha256": _sha(evidence.report_bytes),
        "review_sha256": _sha((root / "review.md").read_bytes()),
        "result_fingerprint": evidence.report.result_fingerprint,
        "model_execution_count": evidence.report.model_execution_count,
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
    }
    if manifest != expected_manifest:
        raise ValueError(f"CEA-1.2 {expected_phase} manifest receipt chain is invalid.")
    if expected_phase == "validation":
        finalized = root / "FINALIZED"
        expected_receipt = _sha(_canonical_json(manifest))
        if not finalized.is_file() or finalized.read_text(encoding="utf-8") != expected_receipt:
            raise ValueError("CEA-1.2 validation finalization receipt is invalid.")
    return evidence


def _validated_discrimination_evidence(
    root: Path,
    *,
    development: _Cea1Evidence,
    validation: _Cea1Evidence,
) -> tuple[
    CompetitiveAttachmentFailureAudit,
    CompetitiveDiscriminationCatalog,
    tuple[tuple[str, tuple[CompetitiveAttachmentMatrix, ...]], ...],
]:
    metadata = _load_discrimination_metadata(root)
    _validate_discrimination_prepared(root, metadata)
    if metadata.get("status") != "complete":
        raise ValueError("CEA-1.2 requires a completed CEA-1.1 run.")
    for field, path in (
        ("approval_sha256", root / "approval.json"),
        ("comparison_sha256", root / "comparison.json"),
    ):
        if metadata.get(field) != _sha(path.read_bytes()):
            raise ValueError(f"CEA-1.2 CEA-1.1 digest changed: {field}.")
    if metadata.get("development_report_sha256") != _sha(development.report_bytes) or metadata.get(
        "validation_report_sha256"
    ) != _sha(validation.report_bytes):
        raise ValueError("CEA-1.2 CEA-1.1 phase evidence no longer matches CEA-1.")
    approval = CompetitiveDiscriminationApproval.model_validate_json(
        (root / "approval.json").read_bytes()
    )
    failure_audit = CompetitiveAttachmentFailureAudit.model_validate_json(
        (root / "failure-audit.json").read_bytes()
    )
    catalog = CompetitiveDiscriminationCatalog.model_validate_json(
        (root / "catalog.json").read_bytes()
    )
    comparison = CompetitiveDiscriminationComparison.model_validate_json(
        (root / "comparison.json").read_bytes()
    )
    if (
        approval.failure_audit_sha256 != _sha((root / "failure-audit.json").read_bytes())
        or approval.catalog_sha256 != _sha((root / "catalog.json").read_bytes())
        or comparison.failure_audit_sha256 != approval.failure_audit_sha256
        or comparison.catalog_sha256 != approval.catalog_sha256
    ):
        raise ValueError("CEA-1.2 CEA-1.1 approval and comparison chain is invalid.")

    expected_conditions = {
        f"{arm.value}-{order.value}-r{repetition}"
        for repetition in (1, 2)
        for arm in CompetitiveDiscriminationPromptArm
        if repetition == 1 or arm is CompetitiveDiscriminationPromptArm.COMBINED
        for order in (
            CompetitiveAttachmentEventOrder.SOURCE,
            CompetitiveAttachmentEventOrder.REVERSED,
        )
    }
    condition_root = root / "conditions"
    observed_conditions = {item.name for item in condition_root.iterdir() if item.is_dir()}
    if observed_conditions != expected_conditions:
        raise ValueError("CEA-1.2 CEA-1.1 condition inventory changed.")
    comparison_by_arm = {item.arm: item for item in comparison.arms}
    expected_candidate_ids = {item.candidate_id for item in catalog.cases}
    condition_matrices: list[tuple[str, tuple[CompetitiveAttachmentMatrix, ...]]] = []
    for condition in sorted(expected_conditions):
        directory = condition_root / condition
        report = CompetitiveDiscriminationConditionReport.model_validate_json(
            (directory / "report.json").read_bytes()
        )
        expected_name = f"{report.arm.value}-{report.event_order}-r{report.repetition}"
        if condition != expected_name:
            raise ValueError(f"CEA-1.2 condition metadata drifted: {condition}.")
        if report.repetition == 1:
            arm = comparison_by_arm[report.arm]
            expected_digest = (
                arm.source_report_sha256
                if report.event_order == "source"
                else arm.reversed_report_sha256
            )
            if _sha((directory / "report.json").read_bytes()) != expected_digest:
                raise ValueError(f"CEA-1.2 comparison report digest drifted: {condition}.")
        terminal_matrices: list[CompetitiveAttachmentMatrix] = []
        for path in sorted(directory.glob("cam_*.json")):
            record = _read_json(path)
            input_matrix = CompetitiveAttachmentMatrix.model_validate_json(
                _canonical_json(record.get("input_matrix"))
            )
            terminal, _ = _validate_execution(
                path,
                input_matrix,
                expected_prompt_sha256=report.prompt_sha256,
                expected_event_order=CompetitiveAttachmentEventOrder(report.event_order),
            )
            terminal_matrices.append(terminal)
        condition_candidate_ids = {
            candidate.id for matrix in terminal_matrices for candidate in matrix.candidates
        }
        if condition_candidate_ids != expected_candidate_ids:
            raise ValueError(f"CEA-1.2 condition Candidate inventory drifted: {condition}.")
        if {item.candidate_id for item in report.cases} != expected_candidate_ids:
            raise ValueError(f"CEA-1.2 condition report inventory drifted: {condition}.")
        condition_matrices.append((condition, tuple(terminal_matrices)))
    return failure_audit, catalog, tuple(condition_matrices)


def _evidence_reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.2 evidence file is missing: {resolved}.")
    return AttachmentEvidenceReference(
        label=label,
        path=_relative_or_absolute(resolved),
        sha256=_sha(resolved.read_bytes()),
    )


def _directory_evidence_reference(
    label: str,
    path: Path,
) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    files = tuple(sorted(item for item in resolved.rglob("*") if item.is_file()))
    if not files:
        raise ValueError(f"CEA-1.2 evidence directory is empty: {resolved}.")
    inventory = tuple(
        {
            "path": str(item.relative_to(resolved)),
            "sha256": _sha(item.read_bytes()),
        }
        for item in files
    )
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_sha(_canonical_json(inventory)),
    )


def _output_evidence_reference(label: str, path: Path) -> AttachmentEvidenceReference:
    if not path.is_file():
        raise ValueError(f"CEA-1.2 output file is missing: {path}.")
    return AttachmentEvidenceReference(
        label=label,
        path=path.name,
        sha256=_sha(path.read_bytes()),
    )


def _build_matrices(
    inputs: tuple[EventEntityExperimentInput, ...],
) -> tuple[tuple[CompetitiveAttachmentMatrix, ...], dict[str, str]]:
    groups: dict[str, list[EventEntityExperimentInput]] = {}
    bindings: dict[str, str] = {}
    for item in inputs:
        groups.setdefault(item.event.source_text_sha256, []).append(item)
        bindings[item.gold_event_id] = item.event.id
    matrices: list[CompetitiveAttachmentMatrix] = []
    for digest, group in sorted(groups.items()):
        source_texts = {item.source_text for item in group}
        if len(source_texts) != 1 or _sha(next(iter(source_texts)).encode()) != digest:
            raise ValueError("CEA-1 grouped inputs do not share exact source text.")
        candidates_by_event = {
            item.event.id: build_proposition_fragment_candidates(
                source_text=item.source_text,
                trigger=item.trigger,
                event=item.event,
                linguistic_evidence=item.linguistic_evidence,
                entity_candidates=build_event_entity_connection_candidates(
                    item.event,
                    item.candidate_selection.mentions,
                    source_text=item.source_text,
                ),
            )
            for item in group
        }
        matrices.append(
            build_competitive_attachment_matrix(
                source_text=group[0].source_text,
                event_inputs=tuple((item.event, item.trigger) for item in group),
                candidates_by_event=candidates_by_event,
            )
        )
    return tuple(sorted(matrices, key=lambda item: item.source_text_sha256)), bindings


def _execute_matrices(
    root: Path,
    config: PipelineConfig,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    *,
    output_directory: str,
    evidence_root: Path | None = None,
    prompt_bytes: bytes | None = None,
    prompt_id: str = "competitive_event_attachment_v1",
    event_order: CompetitiveAttachmentEventOrder = CompetitiveAttachmentEventOrder.SOURCE,
) -> tuple[tuple[CompetitiveAttachmentMatrix, str], ...]:
    input_root = evidence_root or root
    state = _load_canonical_state(input_root / "canonical-state.json")
    inputs = _load_inputs(input_root / "inputs.jsonl")
    representative_by_digest = {item.event.source_text_sha256: item for item in inputs}
    output_dir = root / output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    prompt = prompt_bytes if prompt_bytes is not None else DEFAULT_PROMPT.read_bytes()
    results: list[tuple[CompetitiveAttachmentMatrix, str]] = []
    try:
        for ordinal, matrix in enumerate(matrices, start=1):
            output = output_dir / f"{matrix.id}.json"
            if output.exists():
                terminal, digest = _validate_execution(
                    output,
                    matrix,
                    expected_prompt_sha256=_sha(prompt),
                    expected_prompt_id=prompt_id,
                    expected_event_order=event_order,
                    expected_runtime_contract=_runtime_contract(config),
                )
                results.append((terminal, digest))
                print(f"Competitive matrix {ordinal}/{len(matrices)}: reused")
                continue
            prepared = representative_by_digest[matrix.source_text_sha256]
            ledger = _ExperimentLedger(state.source, state.document, state.bundle)
            unit = create_analysis_unit_from_source_segment(
                SourceSegmentAnalysisUnitInput(
                    representation_id=prepared.representation_id,
                    paragraph_node_id=prepared.paragraph_node_id,
                    source_segment_label=prepared.source_segment_label,
                    policy_id=COMPETITIVE_ATTACHMENT_POLICY_ID,
                    task_type="competitive_event_attachment_experiment",
                    source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
                ),
                ledger,
            )
            result = run_competitive_event_attachment(
                CompetitiveAttachmentCommand(
                    source_id=prepared.source_id,
                    document_id=prepared.document_id,
                    representation_id=prepared.representation_id,
                    source_text=prepared.source_text,
                    matrix=matrix,
                    analysis_unit=unit,
                    model_profile=_profile(config),
                    generation_parameters=_generation(config),
                    prompt_bytes=prompt,
                    prompt_id=prompt_id,
                    event_order=event_order,
                ),
                ledger=cast(CompetitiveAttachmentLedger, ledger),
                archive=cast(CompetitiveAttachmentArchive, archive),
                model_runtime=runtime,
                model_run_id_factory=Uuid4ModelRunIdFactory(),
                tokenizer=runtime,
            )
            if ledger.accepted_ledger_change_count:
                raise AssertionError("CEA-1 changed accepted Ledger state.")
            _write_json(
                output,
                {
                    "schema_version": "competitive_attachment_execution_v1",
                    "input_matrix": matrix.model_dump(mode="json"),
                    "terminal_matrix": result.matrix.model_dump(mode="json"),
                    "traces": [item.model_dump(mode="json") for item in result.traces],
                    "diagnostics": list(result.diagnostics),
                    "result_sha256": result.sha256,
                    "model_runs": [
                        item.model_dump(mode="json")
                        for item in sorted(ledger.model_runs.values(), key=lambda value: value.id)
                    ],
                    "accepted_ledger_change_count": ledger.accepted_ledger_change_count,
                    "event_order": event_order.value,
                    "prompt_id": prompt_id,
                    "prompt_sha256": _sha(prompt),
                    "runtime_contract": _runtime_contract(config),
                },
            )
            results.append((result.matrix, result.sha256))
            print(
                f"Competitive matrix {ordinal}/{len(matrices)}: complete "
                f"({len(result.model_run_ids)} model executions)"
            )
    finally:
        close = getattr(runtime, "close", None)
        if callable(close):
            close()
    return tuple(results)


def _validate_execution(
    path: Path,
    expected_matrix: CompetitiveAttachmentMatrix,
    *,
    expected_prompt_sha256: str | None = None,
    expected_prompt_id: str | None = None,
    expected_event_order: CompetitiveAttachmentEventOrder | None = None,
    expected_runtime_contract: dict[str, object] | None = None,
) -> tuple[CompetitiveAttachmentMatrix, str]:
    record = _read_json(path)
    if record.get("schema_version") != "competitive_attachment_execution_v1":
        raise ValueError(f"Reusable CEA-1 execution schema is unknown: {path}")
    observed_input = CompetitiveAttachmentMatrix.model_validate_json(
        _canonical_json(record.get("input_matrix"))
    )
    if observed_input != expected_matrix:
        raise ValueError(f"Reusable CEA-1 input matrix drifted: {path}")
    terminal = CompetitiveAttachmentMatrix.model_validate_json(
        _canonical_json(record.get("terminal_matrix"))
    )
    traces = tuple(
        ExtractionStageTrace.model_validate_json(_canonical_json(item))
        for item in cast(list[object], record.get("traces"))
    )
    diagnostics = tuple(cast(list[str], record.get("diagnostics")))
    digest = competitive_attachment_result_sha256(terminal, traces, diagnostics)
    if record.get("result_sha256") != digest:
        raise ValueError(f"Reusable CEA-1 execution digest is invalid: {path}")
    if record.get("accepted_ledger_change_count") != 0:
        raise ValueError(f"Reusable CEA-1 execution changed accepted state: {path}")
    if expected_prompt_sha256 is not None and record.get("prompt_sha256") != expected_prompt_sha256:
        raise ValueError(f"Reusable CEA execution prompt changed: {path}")
    if expected_prompt_id is not None and record.get("prompt_id") != expected_prompt_id:
        raise ValueError(f"Reusable CEA execution prompt identity changed: {path}")
    if expected_event_order is not None and record.get("event_order") != expected_event_order.value:
        raise ValueError(f"Reusable CEA execution Event order changed: {path}")
    if (
        expected_runtime_contract is not None
        and record.get("runtime_contract") != expected_runtime_contract
    ):
        raise ValueError(f"Reusable CEA execution runtime changed: {path}")
    tuple(
        ModelRun.model_validate_json(_canonical_json(item))
        for item in cast(list[object], record.get("model_runs"))
    )
    return terminal, digest


def _diagnostic_catalog(
    catalog: PropositionGoldCatalog,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: dict[str, tuple[Any, ...]],
    bindings: dict[str, str],
    phase: str,
) -> dict[str, object]:
    if phase != "development":
        return {"schema_version": "competitive_attachment_diagnostic_catalog_v1", "cases": []}
    gold_by_sge = {bindings[item.event_id]: item for item in catalog.events if item.phase == phase}
    categories: dict[
        str, list[tuple[CompetitiveAttachmentMatrix, CompetitiveAttachmentCandidate]]
    ] = {
        "one_of_five_events": [],
        "coordinated_shared_subject": [],
        "shared_temporal_expression": [],
        "attribution_source": [],
        "clausal_complement": [],
        "none": [],
        "multi_event": [],
    }
    for matrix in matrices:
        gold_by_candidate = {item.candidate_id: item for item in oracle[matrix.id]}
        for candidate in matrix.candidates:
            decision = gold_by_candidate[candidate.id]
            gold_ids = decision.source_grounded_event_ids
            requirements = {
                requirement
                for event_id in gold_ids
                for fragment in gold_by_sge[event_id].fragments
                if _overlaps(candidate.start, candidate.end, fragment.start, fragment.end)
                for requirement in fragment.requirements
            }
            eligible = {
                "one_of_five_events": len(matrix.event_options) == 5 and len(gold_ids) == 1,
                "coordinated_shared_subject": (
                    len(gold_ids) > 1 and PropositionFragmentRequirementProxy.entity(candidate)
                ),
                "shared_temporal_expression": (
                    len(gold_ids) > 1
                    and PropositionGoldFragmentRequirement.TEMPORAL in requirements
                ),
                "attribution_source": PropositionGoldFragmentRequirement.ATTRIBUTION
                in requirements,
                "clausal_complement": PropositionFragmentRequirementProxy.clausal(candidate),
                "none": not gold_ids,
                "multi_event": len(gold_ids) > 1,
            }
            for category, matches in eligible.items():
                if matches:
                    categories[category].append((matrix, candidate))
    if any(not value for value in categories.values()):
        missing = sorted(key for key, value in categories.items() if not value)
        raise ValueError(f"CEA-1 diagnostic catalog lacks required cases: {missing}")
    selected_by_category: dict[
        str, tuple[CompetitiveAttachmentMatrix, CompetitiveAttachmentCandidate]
    ] = {}
    used: set[str] = set()
    for category, candidates in categories.items():
        available = tuple(item for item in candidates if item[1].id not in used)
        if not available:
            raise ValueError(f"CEA-1 diagnostic cannot isolate category: {category}")
        selected = max(
            available,
            key=lambda item: _diagnostic_candidate_rank(category, item[1]),
        )
        selected_by_category[category] = selected
        used.add(selected[1].id)
    cases: list[dict[str, object]] = []
    for category, selected in selected_by_category.items():
        matrix, candidate = selected
        gold = next(item for item in oracle[matrix.id] if item.candidate_id == candidate.id)
        cases.append(
            {
                "case_id": f"CEA-DIA-{len(cases) + 1:02d}",
                "category": category,
                "matrix_id": matrix.id,
                "candidate_id": candidate.id,
                "candidate_text": candidate.text,
                "gold_event_ids": list(gold.source_grounded_event_ids),
            }
        )
    return {"schema_version": "competitive_attachment_diagnostic_catalog_v1", "cases": cases}


def _diagnostic_candidate_rank(
    category: str, candidate: CompetitiveAttachmentCandidate
) -> tuple[int, int, int]:
    reasons = {item.value for item in candidate.reasons}
    entity = int("entity_occurrence" in reasons)
    governing = int("governing_context" in reasons)
    event_expression = int("event_expression" in reasons)
    normalized = candidate.text.strip().lower()
    starts_with_connector = int(
        normalized in {"and", "but", "of", "or", "to", "with"}
        or normalized.startswith(("and ", "but ", "of ", "or ", "to ", "with "))
    )
    if category in {"coordinated_shared_subject", "multi_event"}:
        return entity, -starts_with_connector, len(candidate.text)
    if category == "one_of_five_events":
        return event_expression, -starts_with_connector, len(candidate.text)
    if category == "shared_temporal_expression":
        return -starts_with_connector, -len(candidate.text), entity
    if category == "attribution_source":
        return entity + governing, -len(candidate.text), -starts_with_connector
    if category == "clausal_complement":
        clause_marker = int(normalized.startswith(("that ", "which ", "who ", "to ")))
        return clause_marker, -starts_with_connector, len(candidate.text)
    if category == "none":
        return -starts_with_connector, -len(candidate.text), entity
    return -starts_with_connector, len(candidate.text), entity


class PropositionFragmentRequirementProxy:
    """Small local predicates that avoid leaking Gold into model-visible data."""

    @staticmethod
    def entity(candidate: Any) -> bool:
        return any(reason.value == "entity_occurrence" for reason in candidate.reasons)

    @staticmethod
    def clausal(candidate: Any) -> bool:
        return any(reason.value == "clause_local_constituent" for reason in candidate.reasons)


def _diagnostic_case_results(
    catalog: list[dict[str, Any]],
    records: tuple[tuple[CompetitiveAttachmentMatrix, str], ...],
    root: Path,
) -> list[dict[str, object]]:
    matrix_by_candidate = {
        candidate.id: matrix for matrix, _ in records for candidate in matrix.candidates
    }
    result: list[dict[str, object]] = []
    for case in catalog:
        candidate_id = str(case["candidate_id"])
        matrix = matrix_by_candidate[candidate_id]
        decision = next(item for item in matrix.decisions if item.candidate_id == candidate_id)
        expected_ids = tuple(cast(list[str], case["gold_event_ids"]))
        actual_ids = tuple(item.source_grounded_event_id for item in decision.edges)
        execution = _read_json(root / "diagnostic-matrices" / f"{matrix.id}.json")
        model_run = next(
            ModelRun.model_validate_json(_canonical_json(item))
            for item in cast(list[object], execution["model_runs"])
            if cast(dict[str, Any], item)["id"] == decision.model_run_id
        )
        result.append(
            {
                "actual_event_ids": list(actual_ids),
                "candidate_id": candidate_id,
                "category": str(case["category"]),
                "elapsed_milliseconds": _required_int(
                    model_run.execution_diagnostics["elapsed_milliseconds"], "elapsed"
                ),
                "exact": (
                    decision.status is CompetitiveAttachmentDecisionStatus.COMPLETE
                    and actual_ids == expected_ids
                ),
                "expected_event_ids": list(expected_ids),
                "model_run_id": decision.model_run_id,
                "status": decision.status.value,
            }
        )
    return result


def _matrix_subset(
    matrix: CompetitiveAttachmentMatrix, candidate_ids: set[str]
) -> CompetitiveAttachmentMatrix:
    candidates = tuple(item for item in matrix.candidates if item.id in candidate_ids)
    matrix_id = competitive_attachment_matrix_id(
        source_segment_id=matrix.source_segment_id,
        source_text_sha256=matrix.source_text_sha256,
        candidate_ids=tuple(item.id for item in candidates),
        event_option_ids=tuple(item.id for item in matrix.event_options),
        decision_ids=(),
    )
    return CompetitiveAttachmentMatrix(
        id=matrix_id,
        source_segment_id=matrix.source_segment_id,
        source_text_sha256=matrix.source_text_sha256,
        candidates=candidates,
        event_options=matrix.event_options,
    )


def _render_preflight_review(
    report: CompetitiveAttachmentPreflightReport,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
) -> str:
    lines = [
        f"# CEA-1 {report.phase} Preflight",
        "",
        f"Passed: `{str(report.passed).lower()}`",
        "",
        f"Events: `{report.event_count}`",
        "",
        f"SourceSegments: `{report.source_segment_count}`",
        "",
        f"Exact candidates: `{report.candidate_count}`",
        "",
        f"Shared Gold candidates: `{report.shared_gold_candidate_count}`",
        "",
        f"NONE candidates: `{report.empty_gold_candidate_count}`",
        "",
    ]
    for matrix in matrices:
        lines.extend(
            (
                f"## {matrix.source_segment_id}",
                "",
                f"Competing Events: `{len(matrix.event_options)}`",
                "",
                f"Candidate occurrences: `{len(matrix.candidates)}`",
                "",
            )
        )
    for event in report.events:
        lines.append(
            f"- {event.gold_event_id}: missing `{', '.join(event.missing_fragment_ids) or 'none'}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_diagnostic_review(
    catalog: list[dict[str, Any]],
    records: tuple[tuple[CompetitiveAttachmentMatrix, str], ...],
    root: Path,
) -> str:
    result_by_candidate = {
        str(item["candidate_id"]): item for item in _diagnostic_case_results(catalog, records, root)
    }
    matrix_by_original_candidate = {
        candidate.id: matrix for matrix, _ in records for candidate in matrix.candidates
    }
    lines = [
        "# CEA-1 Competitive Attachment Diagnostic Review",
        "",
        "Review each exact Candidate, all Event options, raw answer, and mapped edges.",
        "",
    ]
    for case in catalog:
        matrix = matrix_by_original_candidate[str(case["candidate_id"])]
        candidate = next(item for item in matrix.candidates if item.id == case["candidate_id"])
        decision = next(item for item in matrix.decisions if item.candidate_id == candidate.id)
        expected_event_ids = set(cast(list[str], case["gold_event_ids"]))
        actual_event_ids = {item.source_grounded_event_id for item in decision.edges}
        expected_labels = tuple(
            option.label
            for option in matrix.event_options
            if option.source_grounded_event_id in expected_event_ids
        )
        mapped_labels = tuple(
            option.label
            for option in matrix.event_options
            if option.source_grounded_event_id in actual_event_ids
        )
        case_result = result_by_candidate[candidate.id]
        record = _read_json(root / "diagnostic-matrices" / f"{matrix.id}.json")
        trace = next(
            ExtractionStageTrace.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["traces"])
            if cast(dict[str, Any], item)["input"]["candidate_id"] == candidate.id
        )
        lines.extend(
            (
                f"## {case['case_id']} — {case['category']}",
                "",
                "Exact model input:",
                "",
                "~~~~text",
                str(trace.input["exact_model_input"]),
                "~~~~",
                "",
                f"Expected task-local labels: `{','.join(expected_labels) or 'NONE'}`",
                "",
                f"Raw Qwen output: `{trace.output['raw_output_text']}`",
                "",
                f"Mapped task-local labels: `{','.join(mapped_labels) or 'NONE'}`",
                "",
                f"Decision status: `{decision.status.value}`",
                "",
                f"Exact Attachment Set: `{str(case_result['exact']).lower()}`",
                "",
                f"Elapsed milliseconds: `{case_result['elapsed_milliseconds']}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_phase_review(
    report: Any,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: dict[str, tuple[Any, ...]],
    baseline: dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]],
) -> str:
    lines = [
        f"# CEA-1 {report.phase} Repetition {report.repetition}",
        "",
        "Every section below is occurrence-specific.",
        "",
    ]
    for matrix in matrices:
        gold = {item.candidate_id: item for item in oracle[matrix.id]}
        prior = {item.candidate_id: item for item in baseline[matrix.id]}
        lines.extend((f"## {matrix.source_segment_id}", ""))
        for candidate, decision in zip(matrix.candidates, matrix.decisions, strict=True):
            lines.extend(
                (
                    f"### `{candidate.text}` [{candidate.start}, {candidate.end})",
                    "",
                    "Gold: `"
                    + (",".join(gold[candidate.id].source_grounded_event_ids) or "NONE")
                    + "`",
                    "",
                    "Prompt-v3 baseline: `"
                    + (",".join(prior[candidate.id].attached_event_ids) or "NONE")
                    + "`",
                    "",
                    "Competitive: `"
                    + (",".join(item.source_grounded_event_id for item in decision.edges) or "NONE")
                    + "`",
                    "",
                    f"Status: `{decision.status.value}`",
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def _entity_occurrences(
    catalog: PropositionGoldCatalog,
    phase: Literal["development", "validation"],
) -> dict[str, tuple[tuple[int, int], ...]]:
    connection_path = (REPOSITORY_ROOT / catalog.connection_gold_path).resolve()
    connection, _, _ = load_connection_gold_catalog(
        connection_path, repository_root=REPOSITORY_ROOT, require_approved=True
    )
    return {
        item.event_id: tuple(
            sorted(
                {
                    (occurrence.start, occurrence.end)
                    for entity in item.expected_entities
                    for occurrence in entity.accepted_source_occurrences
                }
            )
        )
        for item in connection.events
        if item.phase == phase
    }


def _validate_static_contract(root: Path, metadata: dict[str, Any]) -> None:
    checks = (
        ("gold_sha256", _stored_path(metadata["gold_path"]).read_bytes()),
        ("prompt_sha256", DEFAULT_PROMPT.read_bytes()),
        ("canonical_state_sha256", (root / "canonical-state.json").read_bytes()),
        ("inputs_sha256", (root / "inputs.jsonl").read_bytes()),
        ("matrices_sha256", (root / "matrices.json").read_bytes()),
        ("bindings_sha256", (root / "gold-bindings.json").read_bytes()),
        ("oracle_sha256", (root / "oracle.json").read_bytes()),
        ("baseline_sha256", (root / "baseline.json").read_bytes()),
        ("preflight_sha256", (root / "preflight.json").read_bytes()),
        ("diagnostic_catalog_sha256", (root / "diagnostic-catalog.json").read_bytes()),
    )
    for field, payload in checks:
        if metadata[field] != _sha(payload):
            raise ValueError(f"CEA-1 static contract changed: {field}")
    execution_contract_value = metadata.get("execution_contract")
    runtime_contract_value = metadata.get("runtime")
    if not isinstance(execution_contract_value, dict) or not isinstance(
        runtime_contract_value, dict
    ):
        raise ValueError("CEA-1 execution contract is not a JSON object.")
    execution_contract = cast(dict[str, object], execution_contract_value)
    runtime_contract = cast(dict[str, object], runtime_contract_value)
    expected_generation: list[dict[str, object]] = [
        {
            "key": "max_output_tokens",
            "value": runtime_contract.get("max_output_tokens"),
        },
        {"key": "seed", "value": 17},
        {"key": "temperature", "value": 0},
    ]
    if (
        metadata.get("execution_contract_sha256") != _sha(_canonical_json(execution_contract))
        or execution_contract.get("answer_schema_id") != COMPETITIVE_ATTACHMENT_SCHEMA_ID
        or execution_contract.get("candidate_policy_id") != PROPOSITION_SCOPE_POLICY_ID
        or execution_contract.get("policy_id") != COMPETITIVE_ATTACHMENT_POLICY_ID
        or execution_contract.get("prompt_sha256") != metadata["prompt_sha256"]
        or execution_contract.get("runtime") != metadata["runtime"]
        or execution_contract.get("generation_parameters") != expected_generation
        or execution_contract.get("task_renderer_id") != COMPETITIVE_ATTACHMENT_TASK_RENDERER_ID
    ):
        raise ValueError("CEA-1 execution contract changed after preparation.")
    matrices = _load_matrices(root / "matrices.json")
    if metadata["schema_sha256"] != _schema_set_sha256(matrices):
        raise ValueError("CEA-1 finite output schemas changed after preparation.")
    preflight = CompetitiveAttachmentPreflightReport.model_validate_json(
        (root / "preflight.json").read_bytes()
    )
    if not preflight.passed:
        raise ValueError("CEA-1 execution requires passing candidate preflight.")


def _validate_diagnostic_approval(path: Path, metadata: dict[str, Any]) -> None:
    approval = validate_competitive_attachment_diagnostic_approval(
        _read_json(path),
        expected_prompt_sha256=cast(str, metadata["prompt_sha256"]),
        expected_execution_contract_sha256=cast(str, metadata["execution_contract_sha256"]),
    )
    for field, filename in (
        ("diagnostic_result_sha256", "diagnostic-result.json"),
        ("diagnostic_review_sha256", "diagnostic-review.md"),
    ):
        evidence_path = path.parent / filename
        if not evidence_path.is_file() or getattr(approval, field) != _sha(
            evidence_path.read_bytes()
        ):
            raise ValueError("CEA-1 diagnostic approval receipt chain is invalid.")


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    if metadata["runtime"] != _runtime_contract(config):
        raise ValueError("CEA-1 runtime configuration changed after preparation.")
    if metadata.get("execution_contract") != _execution_contract(config):
        raise ValueError("CEA-1 execution contract changed after preparation.")


def _load_cea1_evidence(root: Path) -> _Cea1Evidence:
    resolved = root.resolve()
    input_matrices = _load_matrices(resolved / "matrices.json")
    terminal_matrices = _load_terminal_matrices(resolved / "matrices", input_matrices)
    report_path = resolved / "report.json"
    report_bytes = report_path.read_bytes()
    inputs = _load_inputs(resolved / "inputs.jsonl")
    source_text_by_digest = {item.event.source_text_sha256: item.source_text for item in inputs}
    if set(source_text_by_digest) != {item.source_text_sha256 for item in input_matrices}:
        raise ValueError("CEA-1 source text inventory does not match its matrices.")
    bindings_value = _read_json(resolved / "gold-bindings.json")
    return _Cea1Evidence(
        root=resolved,
        report_path=report_path,
        report_bytes=report_bytes,
        report=_load_phase_report(report_path),
        inputs=inputs,
        input_matrices=input_matrices,
        terminal_matrices=terminal_matrices,
        oracle=_load_oracle(resolved / "oracle.json"),
        baseline=_load_baseline(resolved / "baseline.json"),
        gold_bindings={str(key): str(value) for key, value in bindings_value.items()},
        source_text_by_digest=source_text_by_digest,
    )


def _load_discrimination_metadata(root: Path) -> dict[str, Any]:
    value = _read_json(root / "run.json")
    if value.get("schema_version") != "competitive_discrimination_run_v1":
        raise ValueError("CEA-1.1 run metadata schema is unknown.")
    return value


def _validate_discrimination_prepared(root: Path, metadata: dict[str, Any]) -> None:
    for field, filename in (
        ("failure_audit_sha256", "failure-audit.json"),
        ("failure_audit_review_sha256", "failure-audit-review.md"),
        ("catalog_sha256", "catalog.json"),
        ("catalog_review_sha256", "catalog-review.md"),
        ("prompt_manifest_sha256", "prompt-manifest.json"),
        ("prompt_review_sha256", "prompt-review.md"),
    ):
        path = root / filename
        if not path.is_file() or metadata.get(field) != _sha(path.read_bytes()):
            raise ValueError(f"CEA-1.1 prepared evidence changed: {filename}.")
    audit = CompetitiveAttachmentFailureAudit.model_validate_json(
        (root / "failure-audit.json").read_bytes()
    )
    if (
        audit.error_count,
        audit.complete_omission_count,
        audit.under_attachment_count,
        audit.false_positive_none_count,
        audit.over_attachment_count,
        audit.wrong_set_substitution_count,
    ) != (65, 17, 25, 13, 5, 5):
        raise ValueError("CEA-1.1 prepared audit no longer reproduces CEA-1.")
    CompetitiveDiscriminationCatalog.model_validate_json((root / "catalog.json").read_bytes())
    _validate_prompt_factors()


def _validate_prompt_factors() -> None:
    sections = {
        arm: _prompt_sections(path.read_text(encoding="utf-8"))
        for arm, path in DISCRIMINATION_PROMPTS.items()
    }
    control_instruction, control_examples, control_output = sections[
        CompetitiveDiscriminationPromptArm.CONTROL
    ]
    scope_instruction, scope_examples, scope_output = sections[
        CompetitiveDiscriminationPromptArm.SCOPE
    ]
    examples_instruction, examples_examples, examples_output = sections[
        CompetitiveDiscriminationPromptArm.EXAMPLES
    ]
    combined_instruction, combined_examples, combined_output = sections[
        CompetitiveDiscriminationPromptArm.COMBINED
    ]
    if not (
        scope_examples == control_examples
        and examples_instruction == control_instruction
        and combined_instruction == scope_instruction
        and combined_examples == examples_examples
        and control_output == scope_output == examples_output == combined_output
    ):
        raise ValueError("CEA-1.1 Prompt Arms change an undeclared factor.")
    required_answers = ("Answer: `E2`", "Answer: `E1,E3`", "Answer: `E2,E4`")
    if any(value not in examples_examples for value in required_answers):
        raise ValueError("CEA-1.1 examples lack a required non-prefix answer.")


def _prompt_sections(value: str) -> tuple[str, str, str]:
    example_start = value.index("Example 1:")
    output_start = value.index("Return `NONE`")
    return value[:example_start], value[example_start:output_start], value[output_start:]


def _condition_model_runs(directory: Path) -> tuple[ModelRun, ...]:
    return tuple(
        ModelRun.model_validate_json(_canonical_json(item))
        for path in sorted(directory.glob("cam_*.json"))
        for item in cast(list[object], _read_json(path).get("model_runs"))
    )


def _render_failure_audit_review(audit: CompetitiveAttachmentFailureAudit) -> str:
    lines = [
        "# CEA-1.1 Failure Audit Review",
        "",
        f"Nonexact candidates: `{audit.error_count}`",
        "",
        f"Complete omissions: `{audit.complete_omission_count}`",
        "",
        f"Partial under-attachments: `{audit.under_attachment_count}`",
        "",
        f"Gold-NONE false positives: `{audit.false_positive_none_count}`",
        "",
        f"Over-attachments: `{audit.over_attachment_count}`",
        "",
        f"Wrong-set substitutions: `{audit.wrong_set_substitution_count}`",
        "",
        "Allowed mechanism labels: `scope_wording`, `position_bias`, "
        "`shared_fragment`, `repeated_occurrence`, `none_overselection`, "
        "`genuine_ambiguity`, `gold_or_candidate_issue`, `other`.",
        "",
    ]
    for ordinal, case in enumerate(audit.cases, start=1):
        lines.extend(
            (
                f"## CEA11-ERR-{ordinal:03d} — {case.candidate_text}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {case.source_text}",
                "",
                f"Candidate: `{case.candidate_text}` at "
                f"`[{case.candidate_start}, {case.candidate_end})`",
                "",
                "Event options:",
                "",
            )
        )
        lines.extend(
            f"- `{item.label}` `{item.text}` -> `{item.source_grounded_event_id}`"
            for item in case.event_options
        )
        lines.extend(
            (
                "",
                f"Gold: `{', '.join(case.gold_event_ids) or 'NONE'}`",
                "",
                f"Baseline: `{', '.join(case.baseline_event_ids) or 'NONE'}`",
                "",
                f"Actual: `{', '.join(case.competitive_event_ids) or 'NONE'}`",
                "",
                f"Failure Shape: `{case.failure_shape.value}`",
                "",
                f"Missing: `{', '.join(case.missing_event_ids) or 'none'}`",
                "",
                f"Extra: `{', '.join(case.extra_event_ids) or 'none'}`",
                "",
                f"Candidate reasons: `{', '.join(item.value for item in case.candidate_reasons)}`",
                "",
                f"Gold requirements: `{', '.join(case.gold_requirement_labels) or 'none'}`",
                "",
                f"Shared Gold: `{str(case.shared_gold).lower()}`",
                "",
                f"Repeated exact text count: `{case.repeated_text_count}`",
                "",
                f"Gold prefix: `{str(case.gold_is_prefix).lower()}`",
                "",
                f"Prediction prefix: `{str(case.prediction_is_prefix).lower()}`",
                "",
                "Exact model input:",
                "",
                "~~~~text",
                case.model_input.rstrip(),
                "~~~~",
                "",
                f"Raw output base64: `{case.raw_output_base64 or 'none'}`",
                "",
                "Mechanism labels: `pending`",
                "",
                "Review rationale: `pending`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_discrimination_catalog_review(
    catalog: CompetitiveDiscriminationCatalog,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: dict[str, tuple[Any, ...]],
    source_text_by_digest: dict[str, str],
) -> str:
    matrix_by_id = {item.id: item for item in matrices}
    gold_by_candidate = {item.candidate_id: item for values in oracle.values() for item in values}
    lines = ["# CEA-1.1 Development Catalog Review", ""]
    for case in catalog.cases:
        matrix = matrix_by_id[case.matrix_id]
        candidate = next(item for item in matrix.candidates if item.id == case.candidate_id)
        gold = gold_by_candidate[candidate.id]
        lines.extend(
            (
                f"## CEA11-DIA-{case.ordinal:02d} — {candidate.text}",
                "",
                f"> {source_text_by_digest[matrix.source_text_sha256]}",
                "",
                f"Candidate: `{candidate.text}` at `[{candidate.start}, {candidate.end})`",
                "",
                f"Categories: `{', '.join(item.value for item in case.categories)}`",
                "",
                f"Gold: `{', '.join(gold.source_grounded_event_ids) or 'NONE'}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_prompt_review(
    references: tuple[CompetitiveDiscriminationPromptReference, ...],
) -> str:
    lines = ["# CEA-1.1 Prompt Review", ""]
    for reference in references:
        prompt = DISCRIMINATION_PROMPTS[reference.arm].read_text(encoding="utf-8")
        lines.extend(
            (
                f"## {reference.arm.value}",
                "",
                f"Prompt ID: `{reference.prompt_id}`",
                "",
                f"SHA-256: `{reference.prompt_sha256}`",
                "",
                "~~~~text",
                prompt.rstrip(),
                "~~~~",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_condition_review(report: CompetitiveDiscriminationConditionReport) -> str:
    value = report
    lines = [
        f"# CEA-1.1 {value.arm.value} / {value.event_order} / repetition {value.repetition}",
        "",
        f"Exact Attachment Set accuracy: `{value.metrics.exact_set_accuracy:.6f}`",
        "",
        f"Mean Jaccard Similarity: `{value.metrics.mean_jaccard_similarity:.6f}`",
        "",
        f"Hamming Loss: `{value.metrics.hamming_loss:.6f}`",
        "",
        f"Sibling-Event Leakage: `{value.metrics.sibling_event_leakage_count}`",
        "",
    ]
    for case in value.cases:
        lines.extend(
            (
                f"## {case.candidate_id}",
                "",
                f"Gold: `{', '.join(case.gold_event_ids) or 'NONE'}`",
                "",
                f"Actual: `{', '.join(case.predicted_event_ids) or 'NONE'}`",
                "",
                f"Exact: `{str(case.exact).lower()}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_discrimination_comparison(
    comparison: CompetitiveDiscriminationComparison,
    reports: tuple[CompetitiveDiscriminationConditionReport, ...],
) -> str:
    value = comparison
    lines = [
        "# CEA-1.1 Comparison",
        "",
        f"Outcome: `{value.outcome.value}`",
        "",
        f"Combined repeat stable: `{str(value.combined_repeat_stable).lower()}`",
        "",
        "Exact accuracy improved in both orders: "
        f"`{str(value.exact_accuracy_improved_both_orders).lower()}`",
        "",
        f"Jaccard improved in both orders: `{str(value.jaccard_improved_both_orders).lower()}`",
        "",
        f"Hamming reduced in both orders: `{str(value.hamming_reduced_both_orders).lower()}`",
        "",
        f"Order sensitivity reduced: `{str(value.order_sensitivity_reduced).lower()}`",
        "",
        "## Conditions",
        "",
    ]
    lines.extend(
        f"- `{item.arm.value}/{item.event_order}/r{item.repetition}`: "
        f"exact `{item.metrics.exact_set_accuracy:.6f}`, "
        f"Jaccard `{item.metrics.mean_jaccard_similarity:.6f}`, "
        f"Hamming `{item.metrics.hamming_loss:.6f}`"
        for item in reports
    )
    return "\n".join(lines).rstrip() + "\n"


def _schema_set_sha256(matrices: tuple[CompetitiveAttachmentMatrix, ...]) -> str:
    schemas = {
        competitive_attachment_answer_schema_bytes(
            tuple(item.label for item in matrix.event_options)
        )
        for matrix in matrices
    }
    return _sha(b"\n".join(sorted(schemas)))


def _load_terminal_matrices(
    directory: Path, expected: tuple[CompetitiveAttachmentMatrix, ...]
) -> tuple[CompetitiveAttachmentMatrix, ...]:
    observed = tuple(
        _validate_execution(directory / f"{item.id}.json", item)[0] for item in expected
    )
    if len(tuple(directory.glob("*.json"))) != len(expected):
        raise ValueError("CEA-1 execution directory contains unexpected matrices.")
    return observed


def _load_matrices(path: Path) -> tuple[CompetitiveAttachmentMatrix, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("CEA-1 matrices must be a JSON array.")
    return tuple(
        CompetitiveAttachmentMatrix.model_validate_json(_canonical_json(item))
        for item in cast(list[object], value)
    )


def _load_oracle(
    path: Path,
) -> dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]:
    value = _read_json(path)
    return {
        matrix_id: tuple(
            CompetitiveAttachmentGoldDecision.model_validate_json(_canonical_json(item))
            for item in items
        )
        for matrix_id, items in cast(dict[str, list[object]], value).items()
    }


def _load_baseline(path: Path) -> dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]]:
    value = _read_json(path)
    return {
        matrix_id: tuple(
            CompetitiveAttachmentBaselineDecision.model_validate_json(_canonical_json(item))
            for item in items
        )
        for matrix_id, items in cast(dict[str, list[object]], value).items()
    }


def _load_phase_report(path: Path):  # type: ignore[no-untyped-def]
    from kotekomi_application import CompetitiveAttachmentPhaseReport

    return CompetitiveAttachmentPhaseReport.model_validate_json(path.read_bytes())


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _load_canonical_state(path: Path) -> _CanonicalState:
    value = _read_json(path)
    return _CanonicalState(
        Source.model_validate_json(_canonical_json(value["source"])),
        Document.model_validate_json(_canonical_json(value["document"])),
        DocumentRepresentationBundle.model_validate_json(_canonical_json(value["bundle"])),
    )


def _load_metadata(root: Path) -> dict[str, Any]:
    value = _read_json(root / "run.json")
    if value.get("schema_version") != "competitive_attachment_experiment_run_v1":
        raise ValueError("CEA-1 run metadata schema is unknown.")
    return value


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _profile(config: PipelineConfig) -> ContextModelProfile:
    return ContextModelProfile(
        config.model_execution.profile_name or "lm-studio",
        config.model_execution.context_tokens,
        config.model_execution.max_output_tokens,
        256,
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


def _execution_contract(config: PipelineConfig) -> dict[str, object]:
    """Freeze every tunable contract that may affect CEA-1 model decisions."""
    return {
        "answer_schema_id": COMPETITIVE_ATTACHMENT_SCHEMA_ID,
        "candidate_policy_id": PROPOSITION_SCOPE_POLICY_ID,
        "generation_parameters": [
            {"key": item.key, "value": item.value} for item in _generation(config)
        ],
        "policy_id": COMPETITIVE_ATTACHMENT_POLICY_ID,
        "prompt_sha256": _sha(DEFAULT_PROMPT.read_bytes()),
        "runtime": _runtime_contract(config),
        "task_renderer_id": COMPETITIVE_ATTACHMENT_TASK_RENDERER_ID,
    }


def _validate_repetition(phase: str, repetition: int) -> None:
    if phase == "development" and repetition not in {1, 2, 3}:
        raise ValueError("CEA-1 development repetitions are one through three.")
    if phase == "validation" and repetition != 1:
        raise ValueError("CEA-1 validation runs exactly once.")


def _overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


def _required_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")
    return value


def _receipt_count(model_run: ModelRun, field: str) -> int:
    if model_run.execution_receipt is None:
        return 0
    value = model_run.execution_receipt.get(field)
    if value is None and field == "output_token_count":
        return 0
    return _required_int(value, f"ModelRun receipt {field}")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json(value) + b"\n")


def _write_jsonl(path: Path, values: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(_canonical_json(item) + b"\n" for item in values))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, Any], value)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(REPOSITORY_ROOT))
    except ValueError:
        return str(path)


def _stored_path(value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("CEA-1 stored path must be a string.")
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
