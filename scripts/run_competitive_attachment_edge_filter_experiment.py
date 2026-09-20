#!/usr/bin/env python3
"""Prepare, execute, freeze, and evaluate the CEA-1.4 Edge Filter."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_EDGE_FILTER_POLICY_ID,
    ATTACHMENT_EDGE_FILTER_PROMPT_ID,
    ATTACHMENT_EDGE_FILTER_SCHEMA_ID,
    PARAGRAPH_SEGMENT_V3,
    AttachmentComparisonRange,
    AttachmentEdgeFilterCommand,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDevelopmentFreeze,
    AttachmentEdgeFilterDiagnosticApproval,
    AttachmentEdgeFilterDiagnosticCatalog,
    AttachmentEdgeFilterManifest,
    AttachmentEdgeFilterPhaseReport,
    AttachmentEdgeFilterReport,
    AttachmentEdgeFilterStatus,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentMetricSnapshot,
    AttachmentPoolArm,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentReviewVerificationManifest,
    AttachmentReviewVerificationReport,
    AttachmentReviewVerificationStatus,
    AttachmentSelectionPolicyManifest,
    AttachmentSelectionPolicyReport,
    AttachmentSelectionPolicyStatus,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentPhaseReport,
    ContextModelProfile,
    ExecutionSetting,
    ExtractionStageTrace,
    SourceSegmentAnalysisUnitInput,
    Uuid4ModelRunIdFactory,
    attachment_edge_filter_report_fingerprint,
    attachment_edge_filter_result_sha256,
    attachment_edge_filter_schema_bytes,
    create_analysis_unit_from_source_segment,
    run_attachment_edge_filter,
)
from kotekomi_application.competitive_attachment_edge_filter_preview import (
    AttachmentEdgeFilterArchive,
    AttachmentEdgeFilterLedger,
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
from kotekomi_pipelines.competitive_attachment_edge_filter import (
    attachment_edge_filter_outcome,
    attachment_edge_filter_summary,
    build_attachment_edge_filter_diagnostic_catalog,
    build_attachment_edge_filter_phase_report,
    build_attachment_edge_filter_tasks,
    build_attachment_pool_edges,
    measure_attachment_edge_filter_predictions,
    normalized_attachment_gold_sets,
    render_attachment_edge_filter_review,
)
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
    load_connection_gold_catalog,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    load_proposition_gold_catalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-19-competitive-attachment-edge-filter.md"
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
DEFAULT_PROMPT = REPOSITORY_ROOT / "prompts/competitive_attachment_edge_filter_v1.md"


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
        raise AssertionError("CEA-1.4 cannot write accepted Ledger state.")


@dataclass(frozen=True)
class _CanonicalState:
    source: Source
    document: Document
    bundle: DocumentRepresentationBundle


@dataclass(frozen=True)
class _PhaseEvidence:
    root: Path
    report: CompetitiveAttachmentPhaseReport
    inputs: tuple[EventEntityExperimentInput, ...]
    matrices: tuple[CompetitiveAttachmentMatrix, ...]
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]
    bindings: dict[str, str]


@dataclass(frozen=True)
class PreparedAttachmentEdgeFilterPhase:
    evidence: _PhaseEvidence
    edges: tuple[AttachmentPoolEdge, ...]
    tasks: tuple[AttachmentEdgeFilterTask, ...]
    source_text_by_digest: dict[str, str]
    gold_sets: dict[str, tuple[str, ...]]
    comparisons: dict[str, AttachmentComparisonRange]
    gold_by_event_id: dict[str, PropositionGoldEvent]
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]]
    competitive_qwen_metrics: AttachmentMetricSnapshot
    cea13_primary_metrics: AttachmentMetricSnapshot
    oracle_ceiling_metrics: AttachmentMetricSnapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    _add_prepare_inputs(prepare)
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)

    diagnose = commands.add_parser("diagnose")
    diagnose.add_argument("--config", type=Path, required=True)
    diagnose.add_argument("--run-root", type=Path, required=True)

    approve = commands.add_parser("approve-diagnostic")
    approve.add_argument("--run-root", type=Path, required=True)
    approve.add_argument("--reviewer", required=True)

    development = commands.add_parser("run-development")
    development.add_argument("--config", type=Path, required=True)
    development.add_argument("--run-root", type=Path, required=True)

    freeze = commands.add_parser("freeze-development")
    freeze.add_argument("--run-root", type=Path, required=True)

    validation = commands.add_parser("run-validation")
    validation.add_argument("--config", type=Path, required=True)
    validation.add_argument("--run-root", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    actions = {
        "prepare": _prepare,
        "diagnose": _diagnose,
        "approve-diagnostic": _approve_diagnostic,
        "run-development": _run_development,
        "freeze-development": _freeze_development,
        "run-validation": _run_validation,
        "finalize": _finalize,
    }
    return actions[args.command](args)


def _add_prepare_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--development-run-root", type=Path, required=True)
    parser.add_argument("--validation-run-root", type=Path, required=True)
    parser.add_argument("--review-run-root", type=Path, required=True)
    parser.add_argument("--selection-run-root", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.4 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    config = _config(args.config)
    development = _validated_cea1_evidence(
        args.development_run_root.resolve(), expected_phase="development"
    )
    validation = _validated_cea1_evidence(
        args.validation_run_root.resolve(), expected_phase="validation"
    )
    review_root = args.review_run_root.resolve()
    selection_root = args.selection_run_root.resolve()
    review = _validated_review_evidence(review_root)
    selection = _validated_selection_evidence(selection_root)
    gold_path = args.gold.resolve()
    gold = load_proposition_gold_catalog(gold_path, repository_root=REPOSITORY_ROOT)
    if gold.review_status.value != "approved":
        raise ValueError("CEA-1.4 requires approved Proposition Gold.")
    prompt_sha = _sha(DEFAULT_PROMPT.read_bytes())
    runtime = _runtime_contract(config)
    metadata: dict[str, object] = {
        "schema_version": "attachment_edge_filter_experiment_run_v1",
        "status": "prepared",
        "development_run_root": str(development.root),
        "validation_run_root": str(validation.root),
        "review_run_root": str(review_root),
        "selection_run_root": str(selection_root),
        "gold_path": _stored_path(gold_path),
        "gold_sha256": _sha(gold_path.read_bytes()),
        "prompt_path": _stored_path(DEFAULT_PROMPT),
        "prompt_sha256": prompt_sha,
        "schema_sha256": _sha(attachment_edge_filter_schema_bytes()),
        "runtime_contract": runtime,
        "runtime_contract_sha256": _sha(_canonical_json(runtime)),
        "config_path": str(args.config.resolve()),
        "development_report_sha256": _sha((development.root / "report.json").read_bytes()),
        "validation_report_sha256": _sha((validation.root / "report.json").read_bytes()),
        "review_report_sha256": _sha((review_root / "report.json").read_bytes()),
        "selection_report_sha256": _sha((selection_root / "report.json").read_bytes()),
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
    }
    prepared: dict[str, PreparedAttachmentEdgeFilterPhase] = {}
    for phase, evidence in (("development", development), ("validation", validation)):
        prepared[phase] = _build_prepared_phase(
            cast(Literal["development", "validation"], phase),
            evidence=evidence,
            review=review,
            selection=selection,
            gold=gold,
        )
        _write_json(
            root / f"pool-{phase}.json",
            [item.model_dump(mode="json") for item in prepared[phase].edges],
        )
        _write_json(
            root / f"tasks-{phase}.json",
            [item.model_dump(mode="json") for item in prepared[phase].tasks],
        )
    diagnostic = build_attachment_edge_filter_diagnostic_catalog(
        tasks=prepared["development"].tasks,
        gold_sets=prepared["development"].gold_sets,
        source_text_by_digest=prepared["development"].source_text_by_digest,
        gold_by_event_id=prepared["development"].gold_by_event_id,
    )
    _write_json(root / "diagnostic-catalog.json", diagnostic.model_dump(mode="json"))
    metadata.update(
        {
            "development_pool_sha256": _sha((root / "pool-development.json").read_bytes()),
            "development_tasks_sha256": _sha((root / "tasks-development.json").read_bytes()),
            "validation_pool_sha256": _sha((root / "pool-validation.json").read_bytes()),
            "validation_tasks_sha256": _sha((root / "tasks-validation.json").read_bytes()),
            "diagnostic_catalog_sha256": _sha((root / "diagnostic-catalog.json").read_bytes()),
        }
    )
    _write_json(root / "run.json", metadata)
    diagnostic_segment_counts = {
        source_segment_id: sum(
            task.edge.source_segment_id == source_segment_id for task in diagnostic.tasks
        )
        for source_segment_id in sorted({task.edge.source_segment_id for task in diagnostic.tasks})
    }
    diagnostic_expected_yes_count = sum(
        task.edge.source_grounded_event_id
        in prepared["development"].gold_sets[task.edge.candidate_id]
        for task in diagnostic.tasks
    )
    diagnostic_tasks_by_candidate = {
        candidate_id: tuple(
            task for task in diagnostic.tasks if task.edge.candidate_id == candidate_id
        )
        for candidate_id in {task.edge.candidate_id for task in diagnostic.tasks}
    }
    diagnostic_mixed_candidate_pair_count = sum(
        not prepared["development"].gold_sets[candidate_id]
        and any(AttachmentProposalOrigin.QWEN in task.edge.origins for task in candidate_tasks)
        and any(task.edge.origins == (AttachmentProposalOrigin.SYNTAX,) for task in candidate_tasks)
        for candidate_id, candidate_tasks in diagnostic_tasks_by_candidate.items()
    )
    _write_json(
        root / "preflight.json",
        {
            "schema_version": "attachment_edge_filter_preflight_v1",
            "development_candidate_count": len(prepared["development"].gold_sets),
            "development_maximum_pool_edge_count": len(prepared["development"].edges),
            "development_pool_arm_edge_counts": _arm_counts(prepared["development"].edges),
            "validation_candidate_count": len(prepared["validation"].gold_sets),
            "validation_maximum_pool_edge_count": len(prepared["validation"].edges),
            "validation_pool_arm_edge_counts": _arm_counts(prepared["validation"].edges),
            "diagnostic_task_count": len(diagnostic.tasks),
            "diagnostic_source_segment_counts": diagnostic_segment_counts,
            "diagnostic_expected_yes_count": diagnostic_expected_yes_count,
            "diagnostic_expected_no_count": (len(diagnostic.tasks) - diagnostic_expected_yes_count),
            "diagnostic_mixed_candidate_pair_count": (diagnostic_mixed_candidate_pair_count),
            "diagnostic_shared_entity_edge_count": sum(
                "shared_entity" in diagnostic.coverage_by_task_id[task.task_id]
                for task in diagnostic.tasks
            ),
            "gold_entered_model_task": False,
            "passed": True,
        },
    )
    print(
        json.dumps(
            {
                "diagnostic_catalog": str(root / "diagnostic-catalog.json"),
                "preflight": str(root / "preflight.json"),
                "run_root": str(root),
                "status": "prepared",
            },
            sort_keys=True,
        )
    )
    return 0


def _diagnose(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_prepared_metadata(root)
    config = _config(args.config)
    _validate_runtime(config, metadata)
    catalog = AttachmentEdgeFilterDiagnosticCatalog.model_validate_json(
        (root / "diagnostic-catalog.json").read_bytes()
    )
    prepared = reload_prepared_attachment_edge_filter_phase(root, metadata, "development")
    expected_answer_by_task_id = {
        task.task_id: (
            "Y"
            if task.edge.source_grounded_event_id in prepared.gold_sets[task.edge.candidate_id]
            else "N"
        )
        for task in catalog.tasks
    }
    repetition_results: list[dict[str, object]] = []
    for repetition in (1, 2):
        directory = root / "diagnostic" / f"repetition-{repetition}"
        execute_attachment_edge_filter_tasks(
            root=root,
            config=config,
            tasks=catalog.tasks,
            output_directory=directory,
            phase="development",
            metadata=metadata,
        )
        decisions = _load_decisions(
            directory,
            catalog.tasks,
            archive=LocalArchiveStore(root / "archive"),
            expected_prompt_sha256=_required_str(metadata, "prompt_sha256"),
            expected_runtime_contract=_runtime_contract(config),
        )
        result: dict[str, object] = {
            "schema_version": "attachment_edge_filter_diagnostic_result_v1",
            "repetition": repetition,
            "task_count": len(catalog.tasks),
            "semantic_results": [
                _diagnostic_result_item(
                    task,
                    decision,
                    directory / f"{task.task_id}.json",
                    expected_answer=expected_answer_by_task_id[task.task_id],
                )
                for task, decision in zip(catalog.tasks, decisions, strict=True)
            ],
            "invalid_output_count": sum(
                item.status.value == "invalid_output" for item in decisions
            ),
            "blocked_count": sum(item.status.value == "input_blocked" for item in decisions),
            "failed_count": sum(item.status.value == "model_failed" for item in decisions),
        }
        result["semantic_exact_count"] = sum(
            bool(item["matches_gold"])
            for item in cast(list[dict[str, object]], result["semantic_results"])
        )
        result["result_fingerprint"] = _sha(_canonical_json(result))
        _write_json(directory / "result.json", result)
        repetition_results.append(result)
    stable = repetition_results[0]["semantic_results"] == repetition_results[1]["semantic_results"]
    review_path = root / "diagnostic-review.md"
    review_path.write_text(
        _render_diagnostic_review(
            catalog=catalog,
            repetition_results=tuple(repetition_results),
            stable=stable,
        ),
        encoding="utf-8",
    )
    clean_executions = all(
        result[field] == 0
        for result in repetition_results
        for field in ("invalid_output_count", "blocked_count", "failed_count")
    )
    raw_semantic_exact_counts = tuple(
        result["semantic_exact_count"] for result in repetition_results
    )
    if any(type(value) is not int for value in raw_semantic_exact_counts):
        raise ValueError("CEA-1.4 diagnostic semantic exact count is not an integer.")
    semantic_exact_counts = cast(tuple[int, ...], raw_semantic_exact_counts)
    semantic_exact = semantic_exact_counts == (len(catalog.tasks), len(catalog.tasks))
    approval_ready = stable and clean_executions and semantic_exact
    summary = {
        "schema_version": "attachment_edge_filter_diagnostic_summary_v2",
        "status": "complete",
        "stable_semantic_results": stable,
        "clean_executions": clean_executions,
        "semantic_exact_counts": semantic_exact_counts,
        "semantic_task_count": len(catalog.tasks),
        "semantic_exact": semantic_exact,
        "repetition_1_sha256": _sha((root / "diagnostic/repetition-1/result.json").read_bytes()),
        "repetition_2_sha256": _sha((root / "diagnostic/repetition-2/result.json").read_bytes()),
        "review": str(review_path),
        "approval_ready": approval_ready,
    }
    _write_json(root / "diagnostic-summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if approval_ready else 1


def _approve_diagnostic(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_prepared_metadata(root)
    catalog_path = root / "diagnostic-catalog.json"
    review_path = root / "diagnostic-review.md"
    first_path = root / "diagnostic/repetition-1/result.json"
    second_path = root / "diagnostic/repetition-2/result.json"
    for path in (catalog_path, review_path, first_path, second_path):
        if not path.is_file():
            raise ValueError(f"CEA-1.4 diagnostic evidence is missing: {path}.")
    first = _read_json(first_path)
    second = _read_json(second_path)
    if first.get("semantic_results") != second.get("semantic_results"):
        raise ValueError("CEA-1.4 diagnostic semantic results are not stable.")
    if any(
        result.get(field) != 0
        for result in (first, second)
        for field in ("invalid_output_count", "blocked_count", "failed_count")
    ):
        raise ValueError("CEA-1.4 diagnostic contains invalid, blocked, or failed execution.")
    if any(
        item.get("matches_gold") is not True
        for result in (first, second)
        for item in cast(list[dict[str, object]], result.get("semantic_results"))
    ):
        raise ValueError("CEA-1.4 diagnostic contains a semantic Gold mismatch.")
    approval = AttachmentEdgeFilterDiagnosticApproval(
        reviewer=args.reviewer,
        reviewed_at=datetime.now(UTC).isoformat(),
        catalog_sha256=_sha(catalog_path.read_bytes()),
        prompt_sha256=_required_str(metadata, "prompt_sha256"),
        runtime_contract_sha256=_required_str(metadata, "runtime_contract_sha256"),
        repetition_1_sha256=_sha(first_path.read_bytes()),
        repetition_2_sha256=_sha(second_path.read_bytes()),
        review_sha256=_sha(review_path.read_bytes()),
        stable_semantic_results=True,
    )
    approval_path = root / "diagnostic-approval.json"
    _write_json(approval_path, approval.model_dump(mode="json"))
    metadata["diagnostic_approval_sha256"] = _sha(approval_path.read_bytes())
    metadata["status"] = "diagnostic_approved"
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "approval": str(approval_path),
                "reviewer": args.reviewer,
                "status": "approved",
            },
            sort_keys=True,
        )
    )
    return 0


def _run_development(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_prepared_metadata(
        root, allowed_status={"diagnostic_approved", "development_run"}
    )
    config = _config(args.config)
    _validate_runtime(config, metadata)
    _validate_diagnostic_approval(root, metadata)
    tasks = _load_tasks(root / "tasks-development.json")
    output = root / "development" / "executions"
    output.mkdir(parents=True, exist_ok=True)
    catalog = AttachmentEdgeFilterDiagnosticCatalog.model_validate_json(
        (root / "diagnostic-catalog.json").read_bytes()
    )
    diagnostic_ids = {item.task_id for item in catalog.tasks}
    for task in tasks:
        if task.task_id not in diagnostic_ids:
            continue
        source = root / "diagnostic/repetition-1" / f"{task.task_id}.json"
        target = output / f"{task.task_id}.json"
        if not target.exists():
            shutil.copyfile(source, target)
    execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=tasks,
        output_directory=output,
        phase="development",
        metadata=metadata,
    )
    decisions = _load_decisions(
        output,
        tasks,
        archive=LocalArchiveStore(root / "archive"),
        expected_prompt_sha256=_required_str(metadata, "prompt_sha256"),
        expected_runtime_contract=_runtime_contract(config),
    )
    metadata["status"] = "development_run"
    metadata["development_execution_sha256"] = _directory_sha(output)
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "decision_count": len(decisions),
                "execution_directory": str(output),
                "status": "complete",
            },
            sort_keys=True,
        )
    )
    return 0


def _freeze_development(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_prepared_metadata(
        root, allowed_status={"development_run", "development_frozen"}
    )
    _validate_diagnostic_approval(root, metadata)
    prepared = reload_prepared_attachment_edge_filter_phase(root, metadata, "development")
    decisions = _load_decisions(
        root / "development/executions",
        prepared.tasks,
        archive=LocalArchiveStore(root / "archive"),
        expected_prompt_sha256=_required_str(metadata, "prompt_sha256"),
        expected_runtime_contract=_required_runtime_contract(metadata),
    )
    report = build_attachment_edge_filter_phase_report(
        phase="development",
        matrices=prepared.evidence.matrices,
        edges=prepared.edges,
        decisions=decisions,
        gold_sets=prepared.gold_sets,
        comparisons=prepared.comparisons,
        gold_by_event_id=prepared.gold_by_event_id,
        source_text_by_digest=prepared.source_text_by_digest,
        entity_occurrences_by_event=prepared.entity_occurrences_by_event,
        competitive_qwen_metrics=prepared.competitive_qwen_metrics,
        cea13_primary_metrics=prepared.cea13_primary_metrics,
        oracle_ceiling_metrics=prepared.oracle_ceiling_metrics,
    )
    report_path = root / "development/report.json"
    review_path = root / "development/review.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(
        render_attachment_edge_filter_review(
            phase=report,
            tasks_by_edge_id={item.edge.id: item for item in prepared.tasks},
        ),
        encoding="utf-8",
    )
    approval_path = root / "diagnostic-approval.json"
    freeze = AttachmentEdgeFilterDevelopmentFreeze(
        selected_arm=report.selected_arm,
        prompt_sha256=_required_str(metadata, "prompt_sha256"),
        runtime_contract_sha256=_required_str(metadata, "runtime_contract_sha256"),
        parser_sha256=_sha(
            (
                REPOSITORY_ROOT / "packages/application/src/kotekomi_application/"
                "competitive_attachment_edge_filter.py"
            ).read_bytes()
        ),
        diagnostic_approval_sha256=_sha(approval_path.read_bytes()),
        development_report_sha256=_sha(report_path.read_bytes()),
        result_fingerprint=report.result_fingerprint,
    )
    freeze_path = root / "development-freeze.json"
    _write_json(freeze_path, freeze.model_dump(mode="json"))
    metadata["status"] = "development_frozen"
    metadata["development_report_sha256"] = _sha(report_path.read_bytes())
    metadata["development_freeze_sha256"] = _sha(freeze_path.read_bytes())
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "development_report": str(report_path),
                "freeze": str(freeze_path),
                "selected_arm": report.selected_arm.value,
                "status": "frozen",
            },
            sort_keys=True,
        )
    )
    return 0


def _run_validation(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_prepared_metadata(
        root, allowed_status={"development_frozen", "validation_run"}
    )
    config = _config(args.config)
    _validate_runtime(config, metadata)
    freeze = _validated_development_freeze(root, metadata)
    prepared = reload_prepared_attachment_edge_filter_phase(root, metadata, "validation")
    output = root / "validation" / "executions"
    execute_attachment_edge_filter_tasks(
        root=root,
        config=config,
        tasks=prepared.tasks,
        output_directory=output,
        phase="validation",
        metadata=metadata,
    )
    decisions = _load_decisions(
        output,
        prepared.tasks,
        archive=LocalArchiveStore(root / "archive"),
        expected_prompt_sha256=_required_str(metadata, "prompt_sha256"),
        expected_runtime_contract=_runtime_contract(config),
    )
    report = build_attachment_edge_filter_phase_report(
        phase="validation",
        matrices=prepared.evidence.matrices,
        edges=prepared.edges,
        decisions=decisions,
        gold_sets=prepared.gold_sets,
        comparisons=prepared.comparisons,
        gold_by_event_id=prepared.gold_by_event_id,
        source_text_by_digest=prepared.source_text_by_digest,
        entity_occurrences_by_event=prepared.entity_occurrences_by_event,
        competitive_qwen_metrics=prepared.competitive_qwen_metrics,
        cea13_primary_metrics=prepared.cea13_primary_metrics,
        oracle_ceiling_metrics=prepared.oracle_ceiling_metrics,
        frozen_selected_arm=freeze.selected_arm,
    )
    report_path = root / "validation/report.json"
    review_path = root / "validation/review.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(
        render_attachment_edge_filter_review(
            phase=report,
            tasks_by_edge_id={item.edge.id: item for item in prepared.tasks},
        ),
        encoding="utf-8",
    )
    metadata["status"] = "validation_run"
    metadata["validation_execution_sha256"] = _directory_sha(output)
    metadata["validation_report_sha256"] = _sha(report_path.read_bytes())
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "decision_count": len(decisions),
                "report": str(report_path),
                "selected_arm": report.selected_arm.value,
                "status": "complete",
            },
            sort_keys=True,
        )
    )
    return 0


def _finalize(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_prepared_metadata(root, allowed_status={"validation_run", "complete"})
    freeze = _validated_development_freeze(root, metadata)
    development_path = root / "development/report.json"
    validation_path = root / "validation/report.json"
    development = AttachmentEdgeFilterPhaseReport.model_validate_json(development_path.read_bytes())
    validation = AttachmentEdgeFilterPhaseReport.model_validate_json(validation_path.read_bytes())
    if development.selected_arm is not freeze.selected_arm:
        raise ValueError("CEA-1.4 development report drifted after its freeze.")
    outcome = attachment_edge_filter_outcome(development, validation)
    inputs = tuple(
        sorted(
            (
                _file_reference(
                    "cea12_manifest",
                    Path(_required_str(metadata, "review_run_root")) / "manifest.json",
                ),
                _file_reference(
                    "cea12_report", Path(_required_str(metadata, "review_run_root")) / "report.json"
                ),
                _file_reference(
                    "cea13_manifest",
                    Path(_required_str(metadata, "selection_run_root")) / "manifest.json",
                ),
                _file_reference(
                    "cea13_report",
                    Path(_required_str(metadata, "selection_run_root")) / "report.json",
                ),
                _file_reference(
                    "development_freeze", root / "development-freeze.json", relative_to=root
                ),
                _file_reference("development_report", development_path, relative_to=root),
                _file_reference(
                    "diagnostic_approval", root / "diagnostic-approval.json", relative_to=root
                ),
                _file_reference(
                    "diagnostic_catalog", root / "diagnostic-catalog.json", relative_to=root
                ),
                _file_reference("gold_catalog", _metadata_path(metadata, "gold_path")),
                _file_reference("prompt", _metadata_path(metadata, "prompt_path")),
                _file_reference("validation_report", validation_path, relative_to=root),
            ),
            key=lambda item: item.label,
        )
    )
    draft = AttachmentEdgeFilterReport.model_construct(
        inputs=inputs,
        development=development,
        validation=validation,
        selected_arm=freeze.selected_arm,
        outcome=outcome,
        validation_interpretation="diagnostic_only",
        production_integration="not_activated",
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint="0" * 64,
    )
    report = AttachmentEdgeFilterReport(
        inputs=inputs,
        development=development,
        validation=validation,
        selected_arm=freeze.selected_arm,
        outcome=outcome,
        validation_interpretation="diagnostic_only",
        production_integration="not_activated",
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint=attachment_edge_filter_report_fingerprint(draft),
    )
    report_path = root / "report.json"
    review_path = root / "review.md"
    summary_path = root / "summary.json"
    handoff_path = root / "second-opinion-handoff.md"
    status_path = root / "status.json"
    manifest_path = root / "manifest.json"
    _write_json(report_path, report.model_dump(mode="json"))
    summary = attachment_edge_filter_summary(development, validation, outcome)
    summary["result_fingerprint"] = report.result_fingerprint
    _write_json(summary_path, summary)
    review_path.write_text(_render_final_review(report), encoding="utf-8")
    handoff_path.write_text(_render_handoff(report), encoding="utf-8")
    status = AttachmentEdgeFilterStatus(
        outcome=outcome,
        result_fingerprint=report.result_fingerprint,
        report_path=report_path.name,
        review_path=review_path.name,
        summary_path=summary_path.name,
        handoff_path=handoff_path.name,
    )
    _write_json(status_path, status.model_dump(mode="json"))
    outputs = tuple(
        sorted(
            (
                _file_reference("handoff", handoff_path, relative_to=root),
                _file_reference("report", report_path, relative_to=root),
                _file_reference("review", review_path, relative_to=root),
                _file_reference("status", status_path, relative_to=root),
                _file_reference("summary", summary_path, relative_to=root),
            ),
            key=lambda item: item.label,
        )
    )
    manifest = AttachmentEdgeFilterManifest(
        tdd=_file_reference("tdd", TDD_PATH),
        inputs=inputs,
        outputs=outputs,
        result_fingerprint=report.result_fingerprint,
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    AttachmentEdgeFilterReport.model_validate_json(report_path.read_bytes())
    AttachmentEdgeFilterStatus.model_validate_json(status_path.read_bytes())
    AttachmentEdgeFilterManifest.model_validate_json(manifest_path.read_bytes())
    metadata["status"] = "complete"
    metadata["result_fingerprint"] = report.result_fingerprint
    metadata["manifest_sha256"] = _sha(manifest_path.read_bytes())
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "handoff": str(handoff_path),
                "manifest": str(manifest_path),
                "outcome": outcome.value,
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


def _build_prepared_phase(
    phase: Literal["development", "validation"],
    *,
    evidence: _PhaseEvidence,
    review: AttachmentReviewVerificationReport,
    selection: AttachmentSelectionPolicyReport,
    gold: PropositionGoldCatalog,
) -> PreparedAttachmentEdgeFilterPhase:
    observations = (
        review.development.observations
        if phase == "development"
        else review.validation.observations
    )
    edges = build_attachment_pool_edges(
        phase=phase,
        matrices=evidence.matrices,
        qwen_report=evidence.report,
        syntax_observations=observations,
    )
    source_text_by_digest = {
        item.event.source_text_sha256: item.source_text for item in evidence.inputs
    }
    tasks = build_attachment_edge_filter_tasks(
        matrices=evidence.matrices,
        source_text_by_digest=source_text_by_digest,
        edges=edges,
    )
    original_gold = _flatten_oracle(evidence.oracle)
    changes = {
        item.candidate_id: item.normalized_gold_event_ids
        for item in selection.normalization_changes
        if item.phase == phase
    }
    gold_sets = normalized_attachment_gold_sets(
        original_gold=original_gold,
        normalization_changes=changes,
    )
    comparisons = {
        item.candidate_id: item for item in selection.comparison_ranges if item.phase == phase
    }
    gold_by_tge = {item.event_id: item for item in gold.events if item.phase == phase}
    gold_by_event_id = {evidence.bindings[event_id]: item for event_id, item in gold_by_tge.items()}
    entity_occurrences_by_tge = _entity_occurrences(gold, phase)
    entity_occurrences_by_event = {
        evidence.bindings[event_id]: occurrences
        for event_id, occurrences in entity_occurrences_by_tge.items()
    }
    selection_phase = selection.development if phase == "development" else selection.validation
    primary = next(
        item
        for item in selection_phase.policies
        if item.policy.policy_id == selection.primary_policy_id
    )
    maximum_predictions = _edge_predictions(
        gold_sets, edges, AttachmentPoolArm.PATH_UNBOUNDED_PLUS_COMPLEMENT
    )
    ceiling_predictions = {
        candidate_id: tuple(sorted(set(values) & set(gold_sets[candidate_id])))
        for candidate_id, values in maximum_predictions.items()
    }
    ceiling_metrics = measure_attachment_edge_filter_predictions(
        matrices=evidence.matrices,
        gold_sets=gold_sets,
        predicted_sets=ceiling_predictions,
        comparisons=comparisons,
        gold_by_event_id=gold_by_event_id,
        source_text_by_digest=source_text_by_digest,
        entity_occurrences_by_event=entity_occurrences_by_event,
    )
    return PreparedAttachmentEdgeFilterPhase(
        evidence=evidence,
        edges=edges,
        tasks=tasks,
        source_text_by_digest=source_text_by_digest,
        gold_sets=gold_sets,
        comparisons=comparisons,
        gold_by_event_id=gold_by_event_id,
        entity_occurrences_by_event=entity_occurrences_by_event,
        competitive_qwen_metrics=selection_phase.competitive_qwen_metrics,
        cea13_primary_metrics=primary.union_metrics,
        oracle_ceiling_metrics=ceiling_metrics,
    )


def reload_prepared_attachment_edge_filter_phase(
    root: Path,
    metadata: dict[str, Any],
    phase: Literal["development", "validation"],
) -> PreparedAttachmentEdgeFilterPhase:
    review_root = Path(_required_str(metadata, "review_run_root"))
    selection_root = Path(_required_str(metadata, "selection_run_root"))
    evidence_root = Path(_required_str(metadata, f"{phase}_run_root"))
    evidence = _validated_cea1_evidence(evidence_root, expected_phase=phase)
    review = _validated_review_evidence(review_root)
    selection = _validated_selection_evidence(selection_root)
    gold = load_proposition_gold_catalog(
        _metadata_path(metadata, "gold_path"), repository_root=REPOSITORY_ROOT
    )
    prepared = _build_prepared_phase(
        phase,
        evidence=evidence,
        review=review,
        selection=selection,
        gold=gold,
    )
    stored_edges = _load_edges(root / f"pool-{phase}.json")
    stored_tasks = _load_tasks(root / f"tasks-{phase}.json")
    if stored_edges != prepared.edges or stored_tasks != prepared.tasks:
        raise ValueError(f"CEA-1.4 prepared {phase} pool or tasks drifted.")
    return prepared


def execute_attachment_edge_filter_tasks(
    *,
    root: Path,
    config: PipelineConfig,
    tasks: tuple[AttachmentEdgeFilterTask, ...],
    output_directory: Path,
    phase: Literal["development", "validation"],
    metadata: dict[str, Any],
    generation_parameters: tuple[ExecutionSetting, ...] | None = None,
) -> None:
    evidence_root = Path(_required_str(metadata, f"{phase}_run_root"))
    state = _load_canonical_state(evidence_root / "canonical-state.json")
    inputs = _load_inputs(evidence_root / "inputs.jsonl")
    representative_by_digest = {item.event.source_text_sha256: item for item in inputs}
    output_directory.mkdir(parents=True, exist_ok=True)
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    prompt = _metadata_path(metadata, "prompt_path").read_bytes()
    for ordinal, task in enumerate(tasks, start=1):
        output = output_directory / f"{task.task_id}.json"
        if output.exists():
            validate_attachment_edge_filter_execution_record(
                output,
                task,
                archive=archive,
                expected_prompt_sha256=_required_str(metadata, "prompt_sha256"),
                expected_runtime_contract=_runtime_contract(config),
            )
            print(f"Edge Filter task {ordinal}/{len(tasks)}: reused")
            continue
        prepared = representative_by_digest[task.edge.source_text_sha256]
        ledger = _ExperimentLedger(state.source, state.document, state.bundle)
        unit = create_analysis_unit_from_source_segment(
            SourceSegmentAnalysisUnitInput(
                representation_id=prepared.representation_id,
                paragraph_node_id=prepared.paragraph_node_id,
                source_segment_label=prepared.source_segment_label,
                policy_id=ATTACHMENT_EDGE_FILTER_POLICY_ID,
                task_type="competitive_attachment_edge_filter_experiment",
                source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
            ),
            ledger,
        )
        result = run_attachment_edge_filter(
            AttachmentEdgeFilterCommand(
                source_id=prepared.source_id,
                document_id=prepared.document_id,
                representation_id=prepared.representation_id,
                task=task,
                analysis_unit=unit,
                model_profile=_profile(config),
                generation_parameters=(generation_parameters or _generation(config)),
                prompt_bytes=prompt,
                prompt_id=ATTACHMENT_EDGE_FILTER_PROMPT_ID,
            ),
            ledger=cast(AttachmentEdgeFilterLedger, ledger),
            archive=cast(AttachmentEdgeFilterArchive, archive),
            model_runtime=runtime,
            model_run_id_factory=Uuid4ModelRunIdFactory(),
            tokenizer=runtime,
        )
        if ledger.accepted_ledger_change_count:
            raise AssertionError("CEA-1.4 changed accepted Ledger state.")
        _write_json(
            output,
            {
                "schema_version": "attachment_edge_filter_execution_v1",
                "task": task.model_dump(mode="json"),
                "decision": result.decision.model_dump(mode="json"),
                "trace": result.trace.model_dump(mode="json"),
                "extraction_task": ledger.extraction_tasks[result.extraction_task_id].model_dump(
                    mode="json"
                ),
                "model_run": ledger.model_runs[result.model_run_id].model_dump(mode="json"),
                "result_sha256": result.sha256,
                "prompt_sha256": _sha(prompt),
                "runtime_contract": _runtime_contract(config),
                "accepted_ledger_change_count": 0,
            },
        )
        print(f"Edge Filter task {ordinal}/{len(tasks)}: {result.decision.status.value}")


def _load_decisions(
    directory: Path,
    tasks: tuple[AttachmentEdgeFilterTask, ...],
    *,
    archive: LocalArchiveStore,
    expected_prompt_sha256: str,
    expected_runtime_contract: dict[str, object],
) -> tuple[AttachmentEdgeFilterDecision, ...]:
    decisions = tuple(
        validate_attachment_edge_filter_execution_record(
            directory / f"{task.task_id}.json",
            task,
            archive=archive,
            expected_prompt_sha256=expected_prompt_sha256,
            expected_runtime_contract=expected_runtime_contract,
        )[0]
        for task in tasks
    )
    expected_task_ids = {task.task_id for task in tasks}
    observed_task_ids = {path.stem for path in directory.glob("aet_*.json")}
    if observed_task_ids != expected_task_ids:
        raise ValueError("CEA-1.4 execution directory task inventory is incomplete or foreign.")
    return decisions


def validate_attachment_edge_filter_execution_record(
    path: Path,
    task: AttachmentEdgeFilterTask,
    *,
    archive: LocalArchiveStore | None = None,
    expected_prompt_sha256: str | None = None,
    expected_runtime_contract: dict[str, object] | None = None,
) -> tuple[AttachmentEdgeFilterDecision, dict[str, Any]]:
    value = _read_json(path)
    if value.get("schema_version") != "attachment_edge_filter_execution_v1":
        raise ValueError(f"CEA-1.4 execution schema is invalid: {path}.")
    stored_task = AttachmentEdgeFilterTask.model_validate_json(_canonical_json(value.get("task")))
    if stored_task != task:
        raise ValueError(f"CEA-1.4 execution task drifted: {path}.")
    decision = AttachmentEdgeFilterDecision.model_validate_json(
        _canonical_json(value.get("decision"))
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical_json(value.get("trace")))
    extraction_task = ExtractionTask.model_validate_json(
        _canonical_json(value.get("extraction_task"))
    )
    model_run = ModelRun.model_validate_json(_canonical_json(value.get("model_run")))
    if decision.task_id != task.task_id or decision.edge_id != task.edge.id:
        raise ValueError(f"CEA-1.4 decision references foreign evidence: {path}.")
    if (
        decision.extraction_task_id != extraction_task.id
        or decision.model_run_id != model_run.id
        or decision.trace_id != trace.id
        or model_run.extraction_task_id != extraction_task.id
        or model_run.task_fingerprint != extraction_task.task_fingerprint
    ):
        raise ValueError(f"CEA-1.4 execution lineage is inconsistent: {path}.")
    if extraction_task.input_candidate_ids != (
        task.candidate.id,
        task.edge.source_grounded_event_id,
    ):
        raise ValueError(f"CEA-1.4 ExtractionTask references foreign input: {path}.")
    if (
        trace.source_segment_id != task.edge.source_segment_id
        or trace.source_text_sha256 != task.edge.source_text_sha256
        or trace.input.get("edge_id") != task.edge.id
        or trace.input.get("task_fingerprint") != task.task_fingerprint
        or trace.execution_record_ids != tuple(sorted((extraction_task.id, model_run.id)))
    ):
        raise ValueError(f"CEA-1.4 stage trace references foreign evidence: {path}.")
    expected_answer = decision.answer.value if decision.answer is not None else None
    if (
        trace.output.get("model_run_id") != model_run.id
        or trace.output.get("model_run_status") != model_run.status.value
        or trace.output.get("answer") != expected_answer
        or trace.output.get("diagnostic_code") != decision.diagnostic_code
    ):
        raise ValueError(f"CEA-1.4 stage trace output drifted from its decision: {path}.")
    if value.get("result_sha256") != attachment_edge_filter_result_sha256(decision, trace):
        raise ValueError(f"CEA-1.4 execution result digest drifted: {path}.")
    if model_run.output_digest != decision.raw_output_sha256:
        raise ValueError(f"CEA-1.4 ModelRun output digest drifted from its decision: {path}.")
    if model_run.output_digest is not None:
        if archive is None:
            raise ValueError(f"CEA-1.4 raw output cannot be verified without its Archive: {path}.")
        raw_output = archive.read_model_run_output(model_run.id)
        if _sha(raw_output) != model_run.output_digest:
            raise ValueError(f"CEA-1.4 archived raw output digest drifted: {path}.")
    if expected_prompt_sha256 is not None and value.get("prompt_sha256") != (
        expected_prompt_sha256
    ):
        raise ValueError(f"CEA-1.4 execution prompt drifted: {path}.")
    if expected_prompt_sha256 is not None and (
        model_run.prompt_digest != expected_prompt_sha256
        or trace.configuration.get("prompt_sha256") != expected_prompt_sha256
    ):
        raise ValueError(f"CEA-1.4 model evidence prompt digest drifted: {path}.")
    if (
        extraction_task.prompt_id != ATTACHMENT_EDGE_FILTER_PROMPT_ID
        or extraction_task.schema_id != ATTACHMENT_EDGE_FILTER_SCHEMA_ID
        or model_run.schema_digest != trace.configuration.get("schema_sha256")
    ):
        raise ValueError(f"CEA-1.4 model evidence contract drifted: {path}.")
    if expected_runtime_contract is not None and value.get("runtime_contract") != (
        expected_runtime_contract
    ):
        raise ValueError(f"CEA-1.4 execution runtime drifted: {path}.")
    if value.get("accepted_ledger_change_count") != 0:
        raise ValueError(f"CEA-1.4 execution wrote accepted state: {path}.")
    return decision, value


def _validated_cea1_evidence(
    root: Path,
    *,
    expected_phase: Literal["development", "validation"],
) -> _PhaseEvidence:
    metadata = _read_json(root / "run.json")
    if (
        metadata.get("schema_version") != "competitive_attachment_experiment_run_v1"
        or metadata.get("status") != "finalized"
        or metadata.get("phase") != expected_phase
        or metadata.get("repetition") != 1
    ):
        raise ValueError(f"CEA-1.4 requires finalized {expected_phase} CEA-1 evidence.")
    checks = {
        "canonical_state_sha256": root / "canonical-state.json",
        "inputs_sha256": root / "inputs.jsonl",
        "matrices_sha256": root / "matrices.json",
        "bindings_sha256": root / "gold-bindings.json",
        "oracle_sha256": root / "oracle.json",
    }
    for field, path in checks.items():
        if not path.is_file() or metadata.get(field) != _sha(path.read_bytes()):
            raise ValueError(f"CEA-1.4 CEA-1 evidence digest changed: {field}.")
    report_path = root / "report.json"
    report = CompetitiveAttachmentPhaseReport.model_validate_json(report_path.read_bytes())
    manifest = _read_json(root / "manifest.json")
    if (
        manifest.get("report_sha256") != _sha(report_path.read_bytes())
        or manifest.get("result_fingerprint") != report.result_fingerprint
        or manifest.get("proposed_change_count") != 0
        or manifest.get("accepted_ledger_change_count") != 0
    ):
        raise ValueError(f"CEA-1.4 {expected_phase} CEA-1 manifest is invalid.")
    inputs = _load_inputs(root / "inputs.jsonl")
    matrices = _load_matrices(root / "matrices.json")
    oracle = _load_oracle(root / "oracle.json")
    bindings = {
        str(key): str(value) for key, value in _read_json(root / "gold-bindings.json").items()
    }
    expected_candidates = 162 if expected_phase == "development" else 179
    if (
        report.phase != expected_phase
        or len(report.cases) != expected_candidates
        or sum(len(item.candidates) for item in matrices) != expected_candidates
        or len(inputs) != 20
    ):
        raise ValueError(f"CEA-1.4 {expected_phase} CEA-1 inventory drifted.")
    return _PhaseEvidence(root, report, inputs, matrices, oracle, bindings)


def _validated_review_evidence(root: Path) -> AttachmentReviewVerificationReport:
    report_path = root / "report.json"
    report = AttachmentReviewVerificationReport.model_validate_json(report_path.read_bytes())
    status = AttachmentReviewVerificationStatus.model_validate_json(
        (root / "status.json").read_bytes()
    )
    manifest = AttachmentReviewVerificationManifest.model_validate_json(
        (root / "manifest.json").read_bytes()
    )
    if not (report.result_fingerprint == status.result_fingerprint == manifest.result_fingerprint):
        raise ValueError("CEA-1.4 CEA-1.2 fingerprint chain is invalid.")
    for reference in manifest.outputs:
        _validate_reference(reference, base=root)
    return report


def _validated_selection_evidence(root: Path) -> AttachmentSelectionPolicyReport:
    report_path = root / "report.json"
    report = AttachmentSelectionPolicyReport.model_validate_json(report_path.read_bytes())
    status = AttachmentSelectionPolicyStatus.model_validate_json(
        (root / "status.json").read_bytes()
    )
    manifest = AttachmentSelectionPolicyManifest.model_validate_json(
        (root / "manifest.json").read_bytes()
    )
    if not (report.result_fingerprint == status.result_fingerprint == manifest.result_fingerprint):
        raise ValueError("CEA-1.4 CEA-1.3 fingerprint chain is invalid.")
    for reference in manifest.outputs:
        _validate_reference(reference, base=root)
    return report


def _validated_development_freeze(
    root: Path,
    metadata: dict[str, Any],
) -> AttachmentEdgeFilterDevelopmentFreeze:
    path = root / "development-freeze.json"
    freeze = AttachmentEdgeFilterDevelopmentFreeze.model_validate_json(path.read_bytes())
    if metadata.get("development_freeze_sha256") != _sha(path.read_bytes()):
        raise ValueError("CEA-1.4 development freeze digest changed.")
    if freeze.prompt_sha256 != _required_str(metadata, "prompt_sha256") or (
        freeze.runtime_contract_sha256 != _required_str(metadata, "runtime_contract_sha256")
    ):
        raise ValueError("CEA-1.4 frozen prompt or runtime drifted.")
    report_path = root / "development/report.json"
    if freeze.development_report_sha256 != _sha(report_path.read_bytes()):
        raise ValueError("CEA-1.4 frozen development report drifted.")
    return freeze


def _validate_diagnostic_approval(root: Path, metadata: dict[str, Any]) -> None:
    path = root / "diagnostic-approval.json"
    approval = AttachmentEdgeFilterDiagnosticApproval.model_validate_json(path.read_bytes())
    if metadata.get("diagnostic_approval_sha256") != _sha(path.read_bytes()):
        raise ValueError("CEA-1.4 diagnostic approval digest changed.")
    expected = (
        _sha((root / "diagnostic-catalog.json").read_bytes()),
        _required_str(metadata, "prompt_sha256"),
        _required_str(metadata, "runtime_contract_sha256"),
        _sha((root / "diagnostic/repetition-1/result.json").read_bytes()),
        _sha((root / "diagnostic/repetition-2/result.json").read_bytes()),
        _sha((root / "diagnostic-review.md").read_bytes()),
    )
    observed = (
        approval.catalog_sha256,
        approval.prompt_sha256,
        approval.runtime_contract_sha256,
        approval.repetition_1_sha256,
        approval.repetition_2_sha256,
        approval.review_sha256,
    )
    if observed != expected:
        raise ValueError("CEA-1.4 diagnostic approval no longer binds its evidence.")


def _load_prepared_metadata(
    root: Path,
    *,
    allowed_status: set[str] | None = None,
) -> dict[str, Any]:
    metadata = _read_json(root / "run.json")
    if metadata.get("schema_version") != "attachment_edge_filter_experiment_run_v1":
        raise ValueError("CEA-1.4 run metadata schema is unknown.")
    allowed = allowed_status or {
        "prepared",
        "diagnostic_approved",
        "development_run",
        "development_frozen",
        "validation_run",
        "complete",
    }
    if metadata.get("status") not in allowed:
        raise ValueError(f"CEA-1.4 run status is not allowed: {metadata.get('status')}.")
    checks = {
        "development_pool_sha256": root / "pool-development.json",
        "development_tasks_sha256": root / "tasks-development.json",
        "validation_pool_sha256": root / "pool-validation.json",
        "validation_tasks_sha256": root / "tasks-validation.json",
        "diagnostic_catalog_sha256": root / "diagnostic-catalog.json",
    }
    for field, path in checks.items():
        if metadata.get(field) != _sha(path.read_bytes()):
            raise ValueError(f"CEA-1.4 prepared evidence drifted: {field}.")
    if _required_str(metadata, "prompt_sha256") != _sha(
        _metadata_path(metadata, "prompt_path").read_bytes()
    ):
        raise ValueError("CEA-1.4 prompt changed after prepare.")
    if _required_str(metadata, "gold_sha256") != _sha(
        _metadata_path(metadata, "gold_path").read_bytes()
    ):
        raise ValueError("CEA-1.4 Gold changed after prepare.")
    return metadata


def _validate_runtime(config: PipelineConfig, metadata: dict[str, Any]) -> None:
    observed = _runtime_contract(config)
    if observed != metadata.get("runtime_contract") or _sha(_canonical_json(observed)) != (
        metadata.get("runtime_contract_sha256")
    ):
        raise ValueError("CEA-1.4 configured runtime differs from its frozen contract.")


def _diagnostic_result_item(
    task: AttachmentEdgeFilterTask,
    decision: AttachmentEdgeFilterDecision,
    execution_path: Path,
    *,
    expected_answer: str,
) -> dict[str, object]:
    value = _read_json(execution_path)
    trace = ExtractionStageTrace.model_validate_json(_canonical_json(value.get("trace")))
    exact_model_input = trace.input.get("exact_model_input")
    raw_output_text = trace.output.get("raw_output_text")
    if not isinstance(exact_model_input, str):
        raise ValueError("CEA-1.4 diagnostic trace lacks its exact model input.")
    if raw_output_text is not None and not isinstance(raw_output_text, str):
        raise ValueError("CEA-1.4 diagnostic raw output is not text or null.")
    return {
        "task_id": task.task_id,
        "edge_id": task.edge.id,
        "status": decision.status.value,
        "answer": decision.answer.value if decision.answer else None,
        "expected_answer": expected_answer,
        "matches_gold": decision.answer is not None and decision.answer.value == expected_answer,
        "retained": decision.retained,
        "unresolved": decision.unresolved,
        "exact_model_input": exact_model_input,
        "raw_output_text": raw_output_text,
    }


def _render_diagnostic_review(
    *,
    catalog: AttachmentEdgeFilterDiagnosticCatalog,
    repetition_results: tuple[dict[str, object], ...],
    stable: bool,
) -> str:
    results = tuple(
        {
            str(item["task_id"]): item
            for item in cast(list[dict[str, object]], result["semantic_results"])
        }
        for result in repetition_results
    )
    lines = [
        "# CEA-1.4 Edge Filter Diagnostic Review",
        "",
        f"Semantic results stable: `{str(stable).lower()}`",
        "",
        "Gold-exact decisions per repetition: `"
        + " / ".join(str(result["semantic_exact_count"]) for result in repetition_results)
        + f"` of `{len(catalog.tasks)}`",
        "",
        "The exact model task below contains no Gold label, canonical ID, "
        "source offset, or proposal origin.",
        "",
    ]
    for task in catalog.tasks:
        first = results[0][task.task_id]
        second = results[1][task.task_id]
        lines.extend(
            (
                f"## {task.task_id}",
                "",
                f"Coverage: `{', '.join(catalog.coverage_by_task_id[task.task_id]) or 'control'}`",
                "",
                "Exact model input:",
                "",
                "~~~~text",
                str(first["exact_model_input"]),
                "~~~~",
                "",
                f"Candidate: `{task.candidate.text}`",
                "",
                "Target Event: `"
                + next(
                    item.text
                    for item in task.event_options
                    if item.label == task.target_event_label
                )
                + "`",
                "",
                f"Expected answer: `{first['expected_answer']}`",
                "",
                "Repetition 1 raw output:",
                "",
                "~~~~text",
                str(first.get("raw_output_text")),
                "~~~~",
                "",
                f"Repetition 1 mapped answer: `{first.get('answer') or first['status']}`",
                "",
                f"Repetition 1 Gold match: `{str(first['matches_gold']).lower()}`",
                "",
                "Repetition 2 raw output:",
                "",
                "~~~~text",
                str(second.get("raw_output_text")),
                "~~~~",
                "",
                f"Repetition 2 mapped answer: `{second.get('answer') or second['status']}`",
                "",
                f"Repetition 2 Gold match: `{str(second['matches_gold']).lower()}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_final_review(report: AttachmentEdgeFilterReport) -> str:
    lines = [
        "# CEA-1.4 High-Recall Competitive Edge Filter Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Selected Pool Arm: `{report.selected_arm.value}`",
        "",
        "Validation is diagnostic rather than independent transfer evidence.",
        "",
        "Production integration: `not_activated`",
        "",
    ]
    for phase in (report.development, report.validation):
        selected = next(item for item in phase.arms if item.arm is report.selected_arm)
        baseline = phase.competitive_qwen_metrics
        candidate = selected.filtered_metrics
        lines.extend(
            (
                f"## {phase.phase.title()}",
                "",
                f"Maximum Pool Edges: `{phase.maximum_pool_edge_count}`",
                "",
                f"Qwen exact / precision / recall: `{baseline.exact_set_accuracy:.6f}` / "
                f"`{baseline.edge_precision:.6f}` / `{baseline.edge_recall:.6f}`",
                "",
                f"Filtered exact / precision / recall: `{candidate.exact_set_accuracy:.6f}` / "
                f"`{candidate.edge_precision:.6f}` / `{candidate.edge_recall:.6f}`",
                "",
                f"Qwen / filtered sibling leakage: `{baseline.sibling_event_leakage_count}` / "
                f"`{candidate.sibling_event_leakage_count}`",
                "",
                f"Unresolved / invalid / blocked / failed: `{selected.unresolved_edge_count}` / "
                f"`{phase.invalid_output_count}` / `{phase.blocked_count}` / "
                f"`{phase.failed_count}`",
                "",
            )
        )
    lines.extend((f"Result fingerprint: `{report.result_fingerprint}`", ""))
    return "\n".join(lines)


def _render_handoff(report: AttachmentEdgeFilterReport) -> str:
    lines = [
        "# CEA-1.4 Second-Opinion Handoff",
        "",
        "## Experimental question",
        "",
        "Can one bounded Qwen2.5 Y/N/U judgment per occurrence-specific "
        "Candidate-to-Event edge safely filter a high-recall Qwen-plus-syntax pool?",
        "",
        "## Result",
        "",
        f"Outcome: `{report.outcome.value}`.",
        "",
        f"Selected development arm: `{report.selected_arm.value}`.",
        "",
        "## Fixed boundaries",
        "",
        "- Gold constructed no Pool Edge and entered no model task.",
        "- Every sibling Event remained visible in every task.",
        "- Qwen returned only `Y`, `N`, or `U`.",
        "- KoteKomi created every ID, mapping, trace, metric, and package record.",
        "- No ProposedChange or accepted Ledger state was written.",
        "- Production integration remains inactive.",
        "",
        "## Phase metrics",
        "",
    ]
    for phase in (report.development, report.validation):
        selected = next(item for item in phase.arms if item.arm is report.selected_arm)
        lines.extend(
            (
                f"### {phase.phase.title()}",
                "",
                f"Candidate count: `{phase.candidate_count}`.",
                "",
                f"Maximum Pool Edge count: `{phase.maximum_pool_edge_count}`.",
                "",
                "Filtered exact-set accuracy: "
                f"`{selected.filtered_metrics.exact_set_accuracy:.6f}`.",
                "",
                "Filtered edge precision / recall / F1: "
                f"`{selected.filtered_metrics.edge_precision:.6f}` / "
                f"`{selected.filtered_metrics.edge_recall:.6f}` / "
                f"`{selected.filtered_metrics.edge_f1:.6f}`.",
                "",
                "Oracle exact-set ceiling: "
                f"`{phase.oracle_ceiling_metrics.exact_set_accuracy:.6f}`.",
                "",
            )
        )
    lines.extend(
        (
            "## Evidence navigation",
            "",
            "- `development/review.md` and `validation/review.md` contain every exact "
            "source, Candidate, Target Event, mapped decision, and trace ID.",
            "- `report.json` contains every arm metric and typed decision.",
            "- `manifest.json` binds the complete input and output digest chain.",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`.",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _flatten_oracle(
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
) -> dict[str, tuple[str, ...]]:
    return {
        decision.candidate_id: decision.source_grounded_event_ids
        for decisions in oracle.values()
        for decision in decisions
    }


def _edge_predictions(
    gold_sets: dict[str, tuple[str, ...]],
    edges: tuple[AttachmentPoolEdge, ...],
    arm: AttachmentPoolArm,
) -> dict[str, tuple[str, ...]]:
    result: dict[str, set[str]] = {candidate_id: set() for candidate_id in gold_sets}
    for edge in edges:
        if "qwen" in {item.value for item in edge.origins} or arm in edge.syntax_arms:
            result[edge.candidate_id].add(edge.source_grounded_event_id)
    return {key: tuple(sorted(value)) for key, value in result.items()}


def _arm_counts(edges: tuple[AttachmentPoolEdge, ...]) -> dict[str, int]:
    return {
        arm.value: sum(
            "qwen" in {origin.value for origin in edge.origins} or arm in edge.syntax_arms
            for edge in edges
        )
        for arm in AttachmentPoolArm
    }


def _entity_occurrences(
    catalog: PropositionGoldCatalog,
    phase: Literal["development", "validation"],
) -> dict[str, tuple[tuple[int, int], ...]]:
    connection_path = (REPOSITORY_ROOT / catalog.connection_gold_path).resolve()
    connection, _, _ = load_connection_gold_catalog(
        connection_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
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


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line
    )


def _load_matrices(path: Path) -> tuple[CompetitiveAttachmentMatrix, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("CEA-1.4 matrix evidence must be a JSON array.")
    return tuple(
        CompetitiveAttachmentMatrix.model_validate_json(_canonical_json(item))
        for item in cast(list[object], value)
    )


def _load_oracle(
    path: Path,
) -> dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]:
    value = _read_json(path)
    return {
        str(matrix_id): tuple(
            CompetitiveAttachmentGoldDecision.model_validate_json(_canonical_json(item))
            for item in cast(list[object], decisions)
        )
        for matrix_id, decisions in value.items()
    }


def _load_edges(path: Path) -> tuple[AttachmentPoolEdge, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("CEA-1.4 Pool Edge evidence must be a JSON array.")
    return tuple(
        AttachmentPoolEdge.model_validate_json(_canonical_json(item))
        for item in cast(list[object], value)
    )


def _load_tasks(path: Path) -> tuple[AttachmentEdgeFilterTask, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("CEA-1.4 task evidence must be a JSON array.")
    return tuple(
        AttachmentEdgeFilterTask.model_validate_json(_canonical_json(item))
        for item in cast(list[object], value)
    )


def _load_canonical_state(path: Path) -> _CanonicalState:
    value = _read_json(path)
    return _CanonicalState(
        Source.model_validate_json(_canonical_json(value["source"])),
        Document.model_validate_json(_canonical_json(value["document"])),
        DocumentRepresentationBundle.model_validate_json(_canonical_json(value["bundle"])),
    )


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


def _validate_reference(reference: AttachmentEvidenceReference, *, base: Path) -> None:
    path = Path(reference.path)
    if not path.is_absolute():
        repository_path = REPOSITORY_ROOT / path
        path = repository_path if repository_path.exists() else base / path
    observed = _directory_sha(path) if path.is_dir() else _sha(path.read_bytes())
    if observed != reference.sha256:
        raise ValueError(f"CEA-1.4 referenced evidence changed: {reference.label}.")


def _file_reference(
    label: str,
    path: Path,
    *,
    relative_to: Path | None = None,
) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.4 evidence file is missing: {resolved}.")
    stored = (
        str(resolved.relative_to(relative_to.resolve()))
        if relative_to is not None
        else _stored_path(resolved)
    )
    return AttachmentEvidenceReference(
        label=label,
        path=stored,
        sha256=_sha(resolved.read_bytes()),
    )


def _metadata_path(metadata: dict[str, Any], key: str) -> Path:
    value = _required_str(metadata, key)
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _required_str(value: dict[str, Any], key: str) -> str:
    observed = value.get(key)
    if not isinstance(observed, str) or not observed:
        raise ValueError(f"CEA-1.4 metadata requires string {key}.")
    return observed


def _required_runtime_contract(value: dict[str, Any]) -> dict[str, object]:
    observed = value.get("runtime_contract")
    if not isinstance(observed, dict):
        raise ValueError("CEA-1.4 metadata requires a runtime contract.")
    typed = cast(dict[str, object], observed)
    required_keys = {
        "adapter",
        "context_tokens",
        "endpoint",
        "max_output_tokens",
        "model",
        "profile_name",
        "timeout_seconds",
    }
    if set(typed) != required_keys:
        raise ValueError("CEA-1.4 runtime contract shape is invalid.")
    return typed


def _stored_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPOSITORY_ROOT))
    except ValueError:
        return str(resolved)


def _directory_sha(path: Path) -> str:
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    if not files:
        raise ValueError(f"CEA-1.4 evidence directory is empty: {path}.")
    inventory = tuple(
        {"path": str(item.relative_to(path)), "sha256": _sha(item.read_bytes())} for item in files
    )
    return _sha(_canonical_json(inventory))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json(value) + b"\n")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
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


if __name__ == "__main__":
    raise SystemExit(main())
