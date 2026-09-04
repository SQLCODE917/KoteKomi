"""Read-only, run-scoped observability for user ingestion."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Protocol, cast

from kotekomi_domain import (
    AnalysisItemAttempt,
    AnalysisPlanArtifact,
    AnalysisRun,
    IngestionChangeSet,
    IngestionRun,
    ModelRun,
    PlannedAnalysisItem,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.analysis_coverage import (
    AnalysisCoverageLedger,
    load_frozen_analysis_plan,
)
from kotekomi_application.document_entity_reconciliation import (
    build_document_entity_reconciliation_preview,
    build_reconciled_document_proposal_plan,
    canonical_document_entity_reconciliation_preview_bytes,
    canonical_reconciled_document_proposal_plan_bytes,
    load_document_entity_reconciliation_preview,
    load_reconciled_document_proposal_plan,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageTrace,
    extraction_stage_trace_to_json,
)
from kotekomi_application.hybrid_document_orchestration import (
    HYBRID_DOCUMENT_POLICY_ID,
    HybridDocumentArchive,
    HybridDocumentCoverageReport,
    HybridDocumentLedger,
    HybridStageDisposition,
    hybrid_paragraph_receipt_from_bytes,
    load_hybrid_document_coverage_report,
    read_hybrid_stage_output,
)
from kotekomi_application.hybrid_proposed_changes import HybridProposalPlan
from kotekomi_application.model_run_logging import (
    ModelRunLogEntry,
    model_run_log_entry,
)


class IngestionObservabilityLedger(Protocol):
    def get_ingestion_run(self, record_id: str) -> IngestionRun | None: ...
    def list_ingestion_runs(self) -> tuple[IngestionRun, ...]: ...
    def get_analysis_run(self, record_id: str) -> AnalysisRun | None: ...
    def get_analysis_plan_artifact(self, record_id: str) -> AnalysisPlanArtifact | None: ...
    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None: ...
    def list_planned_items_for_analysis_run(
        self, analysis_run_id: str
    ) -> tuple[PlannedAnalysisItem, ...]: ...
    def list_analysis_item_attempts_for_items(
        self, item_ids: tuple[str, ...]
    ) -> tuple[AnalysisItemAttempt, ...]: ...
    def list_model_runs_by_ids(self, record_ids: tuple[str, ...]) -> tuple[ModelRun, ...]: ...


class IngestionObservabilityArchive(HybridDocumentArchive, Protocol):
    def find_hybrid_document_coverage_report_by_sha256(
        self, expected_sha256: str
    ) -> str | None: ...

    def read_model_run_output(self, model_run_id: str) -> bytes: ...

    def ingestion_evidence_path(self, record_type: str, record_id: str) -> str: ...


@dataclass(frozen=True)
class ListIngestionHistoryInput:
    limit: int = 100

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit <= 0:
            raise ValueError("Ingestion history limit must be a positive integer.")


@dataclass(frozen=True)
class IngestionHistoryEntry:
    ingestion_run_id: str
    display_filename: str
    requested_source_url: str
    status: str
    started_at: str
    completed_at: str | None
    failure_code: str | None


@dataclass(frozen=True)
class ListIngestionHistoryResult:
    entries: tuple[IngestionHistoryEntry, ...]


@dataclass(frozen=True)
class InspectIngestionInput:
    ingestion_run_id: str

    def __post_init__(self) -> None:
        if not self.ingestion_run_id.strip():
            raise ValueError("IngestionRun ID cannot be empty.")


@dataclass(frozen=True)
class IngestionEvidenceEntry:
    authority: str
    record_type: str
    record_id: str
    sha256: str | None = None
    archive_path: str | None = None


@dataclass(frozen=True)
class IngestionSummary:
    ingestion_run_id: str
    display_filename: str
    requested_path: str
    requested_source_url: str
    normalized_source_url: str | None
    status: str
    started_at: str
    completed_at: str | None
    elapsed_milliseconds: int | None
    source_id: str | None
    document_id: str | None
    representation_id: str | None
    provenance_activity_id: str | None
    analysis_run_id: str | None
    ingestion_change_set_id: str | None
    failure_stage: str | None
    failure_code: str | None
    safe_failure_message: str | None
    analysis_state: str | None
    required_paragraph_count: int | None
    complete_paragraph_count: int | None
    gap_paragraph_count: int | None
    model_run_count: int
    trace_count: int
    evidence_count: int
    stage_status_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class InspectIngestionResult:
    summary: IngestionSummary
    evidence: tuple[IngestionEvidenceEntry, ...]
    model_runs: tuple[ModelRunLogEntry, ...]
    traces: tuple[ExtractionStageTrace, ...]


def list_ingestion_history(
    input: ListIngestionHistoryInput,
    ledger: IngestionObservabilityLedger,
) -> ListIngestionHistoryResult:
    runs = ledger.list_ingestion_runs()[: input.limit]
    return ListIngestionHistoryResult(
        tuple(
            IngestionHistoryEntry(
                ingestion_run_id=run.id,
                display_filename=run.display_filename,
                requested_source_url=run.requested_source_url,
                status=run.status.value,
                started_at=run.started_at.isoformat(),
                completed_at=run.completed_at.isoformat() if run.completed_at else None,
                failure_code=run.failure_code.value if run.failure_code else None,
            )
            for run in runs
        )
    )


def inspect_ingestion(
    input: InspectIngestionInput,
    ledger: IngestionObservabilityLedger,
    archive: IngestionObservabilityArchive,
) -> InspectIngestionResult:
    run = ledger.get_ingestion_run(input.ingestion_run_id)
    if run is None:
        raise ValueError(f"IngestionRun not found: {input.ingestion_run_id}")
    evidence = [_ledger_evidence("IngestionRun", run.id)]
    analysis: AnalysisRun | None = None
    report: HybridDocumentCoverageReport | None = None
    traces: tuple[ExtractionStageTrace, ...] = ()
    model_runs: tuple[ModelRun, ...] = ()
    model_run_ids: tuple[str, ...] = ()
    if run.analysis_run_id is not None:
        analysis = _require_analysis(run, ledger)
        frozen_plan = load_frozen_analysis_plan(
            analysis.frozen_analysis_plan_id,
            cast(AnalysisCoverageLedger, ledger),
        )
        if frozen_plan.representation_id != analysis.representation_id:
            raise ValueError("Ingestion AnalysisRun references an invalid analysis Plan.")
        items = ledger.list_planned_items_for_analysis_run(analysis.id)
        if any(item.analysis_run_id != analysis.id for item in items):
            raise ValueError("Ingestion analysis scope contains a foreign planned item.")
        attempts = ledger.list_analysis_item_attempts_for_items(tuple(item.id for item in items))
        item_ids = {item.id for item in items}
        if any(attempt.planned_item_id not in item_ids for attempt in attempts):
            raise ValueError("Ingestion analysis scope contains a foreign attempt.")
        model_run_ids = tuple(
            sorted(
                {attempt.model_run_id for attempt in attempts if attempt.model_run_id is not None}
            )
        )
        model_runs = ledger.list_model_runs_by_ids(model_run_ids)
        if {item.id for item in model_runs} != set(model_run_ids):
            raise ValueError("Ingestion analysis references a missing ModelRun.")
        evidence.extend(
            (
                _ledger_evidence("AnalysisRun", analysis.id),
                _ledger_evidence("AnalysisPlanArtifact", frozen_plan.id),
                *(_ledger_evidence("PlannedAnalysisItem", item.id) for item in items),
                *(_ledger_evidence("AnalysisItemAttempt", item.id) for item in attempts),
                *(_ledger_evidence("ModelRun", item.id) for item in model_runs),
            )
        )
        change_set = _require_change_set(run, analysis, ledger)
        evidence.append(_ledger_evidence("IngestionChangeSet", change_set.id))
        if analysis.coverage_policy_id == HYBRID_DOCUMENT_POLICY_ID:
            report, archive_evidence, traces, archived_model_run_ids = _load_hybrid_evidence(
                change_set=change_set,
                ledger=ledger,
                archive=archive,
            )
            if set(archived_model_run_ids) != set(model_run_ids):
                raise ValueError(
                    "Hybrid stage ModelRuns do not match the ingestion analysis links."
                )
            evidence.extend(archive_evidence)
    elif run.ingestion_change_set_id is not None:
        raise ValueError("IngestionRun has a change set without an AnalysisRun.")

    for model_run in model_runs:
        if model_run.raw_output_artifact_id is None:
            continue
        raw = archive.read_model_run_output(model_run.raw_output_artifact_id)
        actual = hashlib.sha256(raw).hexdigest()
        if model_run.output_digest != actual:
            raise ValueError("ModelRun output does not match its recorded digest.")
        evidence.append(
            IngestionEvidenceEntry(
                authority="derived",
                record_type="ModelRunOutput",
                record_id=model_run.raw_output_artifact_id,
                sha256=actual,
                archive_path=archive.ingestion_evidence_path(
                    "ModelRunOutput", model_run.raw_output_artifact_id
                ),
            )
        )

    ordered_evidence = tuple(
        sorted(_distinct_evidence(evidence), key=lambda item: (item.record_type, item.record_id))
    )
    ordered_traces = tuple(
        sorted(traces, key=lambda item: (item.source_segment_id, item.ordinal, item.id))
    )
    log_entries = tuple(
        model_run_log_entry(item)
        for item in sorted(model_runs, key=lambda item: (item.started_at, item.id), reverse=True)
    )
    stage_counts = Counter(trace.status.value for trace in ordered_traces)
    elapsed = (
        int((run.completed_at - run.started_at).total_seconds() * 1000)
        if run.completed_at is not None
        else None
    )
    summary = IngestionSummary(
        ingestion_run_id=run.id,
        display_filename=run.display_filename,
        requested_path=run.requested_path,
        requested_source_url=run.requested_source_url,
        normalized_source_url=run.normalized_source_url,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        elapsed_milliseconds=elapsed,
        source_id=run.source_id,
        document_id=run.document_id,
        representation_id=run.representation_id,
        provenance_activity_id=run.provenance_activity_id,
        analysis_run_id=run.analysis_run_id,
        ingestion_change_set_id=run.ingestion_change_set_id,
        failure_stage=run.failure_stage.value if run.failure_stage else None,
        failure_code=run.failure_code.value if run.failure_code else None,
        safe_failure_message=run.safe_failure_message,
        analysis_state=analysis.state.value if analysis else None,
        required_paragraph_count=report.required_paragraph_count if report else None,
        complete_paragraph_count=report.complete_paragraph_count if report else None,
        gap_paragraph_count=report.gap_paragraph_count if report else None,
        model_run_count=len(model_runs),
        trace_count=len(ordered_traces),
        evidence_count=len(ordered_evidence),
        stage_status_counts=tuple(sorted(stage_counts.items())),
    )
    return InspectIngestionResult(summary, ordered_evidence, log_entries, ordered_traces)


def ingestion_history_to_json(result: ListIngestionHistoryResult) -> dict[str, JsonValue]:
    return {
        "ingestions": [
            {
                "ingestion_run_id": item.ingestion_run_id,
                "display_filename": item.display_filename,
                "requested_source_url": item.requested_source_url,
                "status": item.status,
                "started_at": item.started_at,
                "completed_at": item.completed_at,
                "failure_code": item.failure_code,
            }
            for item in result.entries
        ]
    }


def ingestion_summary_to_json(summary: IngestionSummary) -> dict[str, JsonValue]:
    return {
        "ingestion_run_id": summary.ingestion_run_id,
        "display_filename": summary.display_filename,
        "requested_path": summary.requested_path,
        "requested_source_url": summary.requested_source_url,
        "normalized_source_url": summary.normalized_source_url,
        "status": summary.status,
        "started_at": summary.started_at,
        "completed_at": summary.completed_at,
        "elapsed_milliseconds": summary.elapsed_milliseconds,
        "source_id": summary.source_id,
        "document_id": summary.document_id,
        "representation_id": summary.representation_id,
        "provenance_activity_id": summary.provenance_activity_id,
        "analysis_run_id": summary.analysis_run_id,
        "ingestion_change_set_id": summary.ingestion_change_set_id,
        "failure_stage": summary.failure_stage,
        "failure_code": summary.failure_code,
        "safe_failure_message": summary.safe_failure_message,
        "analysis_state": summary.analysis_state,
        "required_paragraph_count": summary.required_paragraph_count,
        "complete_paragraph_count": summary.complete_paragraph_count,
        "gap_paragraph_count": summary.gap_paragraph_count,
        "model_run_count": summary.model_run_count,
        "trace_count": summary.trace_count,
        "evidence_count": summary.evidence_count,
        "stage_status_counts": dict(summary.stage_status_counts),
    }


def ingestion_evidence_to_json(entry: IngestionEvidenceEntry) -> dict[str, JsonValue]:
    return {
        "authority": entry.authority,
        "record_type": entry.record_type,
        "record_id": entry.record_id,
        "sha256": entry.sha256,
        "archive_path": entry.archive_path,
    }


def ingestion_trace_to_json(trace: ExtractionStageTrace) -> dict[str, JsonValue]:
    return extraction_stage_trace_to_json(trace)


def _require_analysis(run: IngestionRun, ledger: IngestionObservabilityLedger) -> AnalysisRun:
    assert run.analysis_run_id is not None
    analysis = ledger.get_analysis_run(run.analysis_run_id)
    if (
        analysis is None
        or analysis.document_id != run.document_id
        or analysis.representation_id != run.representation_id
    ):
        raise ValueError("IngestionRun references an invalid AnalysisRun.")
    return analysis


def _require_change_set(
    run: IngestionRun,
    analysis: AnalysisRun,
    ledger: IngestionObservabilityLedger,
) -> IngestionChangeSet:
    if run.ingestion_change_set_id is None:
        raise ValueError("Analyzed IngestionRun requires an IngestionChangeSet.")
    change_set = ledger.get_ingestion_change_set(run.ingestion_change_set_id)
    if (
        change_set is None
        or change_set.ingestion_run_id != run.id
        or change_set.analysis_run_id != analysis.id
        or change_set.representation_id != analysis.representation_id
    ):
        raise ValueError("IngestionRun references an invalid IngestionChangeSet.")
    payload: dict[str, JsonValue] = {
        "ingestion_run_id": change_set.ingestion_run_id,
        "analysis_run_id": change_set.analysis_run_id,
        "representation_id": change_set.representation_id,
        "coverage_report_digest": change_set.coverage_report_digest,
        "proposed_change_ids": list(change_set.proposed_change_ids),
        "analysis_origin": change_set.analysis_origin.value,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if change_set.change_set_digest != digest or change_set.id != f"ics_{digest[:24]}":
        raise ValueError("IngestionChangeSet digest is invalid.")
    return change_set


def _load_hybrid_evidence(
    *,
    change_set: IngestionChangeSet,
    ledger: IngestionObservabilityLedger,
    archive: IngestionObservabilityArchive,
) -> tuple[
    HybridDocumentCoverageReport,
    tuple[IngestionEvidenceEntry, ...],
    tuple[ExtractionStageTrace, ...],
    tuple[str, ...],
]:
    report_id = archive.find_hybrid_document_coverage_report_by_sha256(
        change_set.coverage_report_digest
    )
    if report_id is None:
        raise ValueError("Ingestion coverage report is missing from the Archive.")
    report = load_hybrid_document_coverage_report(
        report_id, cast(HybridDocumentLedger, ledger), archive
    )
    if report.representation_id != change_set.representation_id:
        raise ValueError("Ingestion coverage report uses the wrong representation.")
    report_bytes = archive.read_hybrid_document_coverage_report(report.id)
    evidence = [
        IngestionEvidenceEntry(
            "derived",
            "HybridDocumentCoverageReport",
            report.id,
            hashlib.sha256(report_bytes).hexdigest(),
            archive.ingestion_evidence_path("HybridDocumentCoverageReport", report.id),
        )
    ]
    manifest_bytes = archive.read_hybrid_pipeline_policy_manifest(report.policy_manifest_id)
    if hashlib.sha256(manifest_bytes).hexdigest() != report.policy_manifest_sha256:
        raise ValueError("Hybrid coverage policy evidence does not match its digest.")
    evidence.append(
        IngestionEvidenceEntry(
            "derived",
            "HybridPipelinePolicyManifest",
            report.policy_manifest_id,
            report.policy_manifest_sha256,
            archive.ingestion_evidence_path(
                "HybridPipelinePolicyManifest", report.policy_manifest_id
            ),
        )
    )
    traces: list[ExtractionStageTrace] = []
    model_run_ids: set[str] = set()
    proposal_plans: list[HybridProposalPlan] = []
    for record in report.records:
        receipt_bytes = archive.read_hybrid_paragraph_receipt(record.receipt_id)
        if hashlib.sha256(receipt_bytes).hexdigest() != record.receipt_sha256:
            raise ValueError("Hybrid Paragraph Receipt does not match its digest.")
        receipt = hybrid_paragraph_receipt_from_bytes(receipt_bytes)
        evidence.append(
            IngestionEvidenceEntry(
                "derived",
                "HybridParagraphReceipt",
                receipt.id,
                record.receipt_sha256,
                archive.ingestion_evidence_path("HybridParagraphReceipt", receipt.id),
            )
        )
        for stage in receipt.stages:
            if stage.disposition is HybridStageDisposition.NOT_RUN:
                continue
            assert stage.output_id is not None and stage.output_sha256 is not None
            raw, output = read_hybrid_stage_output(stage.stage_id, stage.output_id, archive)
            if hashlib.sha256(raw).hexdigest() != stage.output_sha256:
                raise ValueError("Hybrid stage output does not match its digest.")
            evidence.append(
                IngestionEvidenceEntry(
                    "derived",
                    stage.stage_id.value,
                    stage.output_id,
                    stage.output_sha256,
                    archive.ingestion_evidence_path(stage.stage_id.value, stage.output_id),
                )
            )
            raw_output_traces = getattr(output, "traces", ())
            if not isinstance(raw_output_traces, tuple):
                raise ValueError("Hybrid stage output traces are invalid.")
            candidate_traces = cast(tuple[object, ...], raw_output_traces)
            if not all(isinstance(item, ExtractionStageTrace) for item in candidate_traces):
                raise ValueError("Hybrid stage output traces are invalid.")
            output_traces = tuple(cast(ExtractionStageTrace, item) for item in candidate_traces)
            traces.extend(output_traces)
            if isinstance(output, HybridProposalPlan):
                proposal_plans.append(output)
            raw_model_run_ids = getattr(output, "model_run_ids", ())
            if not isinstance(raw_model_run_ids, tuple):
                raise ValueError("Hybrid stage output ModelRun IDs are invalid.")
            candidate_model_run_ids = cast(tuple[object, ...], raw_model_run_ids)
            if not all(isinstance(item, str) for item in candidate_model_run_ids):
                raise ValueError("Hybrid stage output ModelRun IDs are invalid.")
            model_run_ids.update(cast(tuple[str, ...], candidate_model_run_ids))
    reconciliation = build_document_entity_reconciliation_preview(
        tuple(proposal_plans),
        cast(HybridDocumentLedger, ledger),
        representation_id=report.representation_id,
    )
    try:
        archive.read_document_entity_reconciliation_preview(reconciliation.id)
    except FileNotFoundError:
        if change_set.proposed_change_ids != report.proposed_change_ids:
            raise ValueError("Ingestion HP-9 reconciliation evidence is missing.") from None
    else:
        reconciliation = load_document_entity_reconciliation_preview(
            reconciliation.id,
            ledger=cast(HybridDocumentLedger, ledger),
            archive=archive,
        )
        reconciliation_bytes = canonical_document_entity_reconciliation_preview_bytes(
            reconciliation
        )
        evidence.append(
            IngestionEvidenceEntry(
                "derived",
                "DocumentEntityReconciliationPreview",
                reconciliation.id,
                hashlib.sha256(reconciliation_bytes).hexdigest(),
                archive.ingestion_evidence_path(
                    "DocumentEntityReconciliationPreview", reconciliation.id
                ),
            )
        )
        document_plan = build_reconciled_document_proposal_plan(
            reconciliation,
            tuple(proposal_plans),
            cast(HybridDocumentLedger, ledger),
        )
        document_plan = load_reconciled_document_proposal_plan(
            document_plan.id,
            ledger=cast(HybridDocumentLedger, ledger),
            archive=archive,
        )
        document_plan_bytes = canonical_reconciled_document_proposal_plan_bytes(document_plan)
        if change_set.proposed_change_ids != tuple(
            item.id for item in document_plan.proposed_changes
        ):
            raise ValueError("IngestionChangeSet does not match its HP-9 Document Plan.")
        evidence.append(
            IngestionEvidenceEntry(
                "derived",
                "ReconciledDocumentProposalPlan",
                document_plan.id,
                hashlib.sha256(document_plan_bytes).hexdigest(),
                archive.ingestion_evidence_path("ReconciledDocumentProposalPlan", document_plan.id),
            )
        )
        traces.extend(reconciliation.traces)
    trace_by_id: dict[str, ExtractionStageTrace] = {}
    for trace in traces:
        existing = trace_by_id.setdefault(trace.id, trace)
        if existing != trace:
            raise ValueError("ExtractionStageTrace identity conflict.")
    return (
        report,
        tuple(evidence),
        tuple(trace_by_id.values()),
        tuple(sorted(model_run_ids)),
    )


def _ledger_evidence(record_type: str, record_id: str) -> IngestionEvidenceEntry:
    return IngestionEvidenceEntry("canonical", record_type, record_id)


def _distinct_evidence(
    evidence: list[IngestionEvidenceEntry],
) -> tuple[IngestionEvidenceEntry, ...]:
    by_key: dict[tuple[str, str], IngestionEvidenceEntry] = {}
    for item in evidence:
        key = (item.record_type, item.record_id)
        existing = by_key.setdefault(key, item)
        if existing != item:
            raise ValueError("Ingestion evidence identity conflict.")
    return tuple(by_key.values())
