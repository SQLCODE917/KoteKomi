"""Application-owned closure of one automatic-ingestion proposal set."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    IngestionChangeSet,
    IngestionChangeSetOrigin,
    IngestionRun,
)

from kotekomi_application.analysis_coverage import (
    AnalysisCoverageLedger,
    AnalysisCoverageState,
    CoverageReport,
    build_coverage_report,
)

HASH_ID_LENGTH = 24


class IngestionChangeSetLedger(AnalysisCoverageLedger, Protocol):
    def get_ingestion_run(self, record_id: str) -> IngestionRun | None: ...
    def list_ingestion_runs(self) -> tuple[IngestionRun, ...]: ...
    def save_ingestion_change_set(self, record: IngestionChangeSet) -> None: ...
    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None: ...


@dataclass(frozen=True)
class CloseIngestionChangeSetInput:
    ingestion_run_id: str
    analysis_run_id: str
    analysis_origin: IngestionChangeSetOrigin
    closed_at: datetime


@dataclass(frozen=True)
class CloseIngestionChangeSetResult:
    change_set: IngestionChangeSet
    coverage_report: CoverageReport


@dataclass(frozen=True)
class ReusableAnalysisSelection:
    """A fully equivalent, completed analysis that needs no new model work."""

    analysis_run_id: str
    coverage_report: CoverageReport


def find_reusable_completed_analysis(
    *,
    representation_id: str,
    frozen_analysis_plan_id: str,
    expected_item_fingerprints: tuple[tuple[str, str], ...],
    ledger_repository: IngestionChangeSetLedger,
) -> ReusableAnalysisSelection | None:
    """Select only an exact prior task plan with successful complete coverage."""
    expected = tuple(sorted(expected_item_fingerprints))
    if len({unit_id for unit_id, _ in expected}) != len(expected):
        raise ValueError("Reusable analysis requires distinct AnalysisUnit IDs.")
    for prior_run in ledger_repository.list_ingestion_runs():
        if (
            prior_run.representation_id != representation_id
            or prior_run.analysis_run_id is None
            or prior_run.ingestion_change_set_id is None
        ):
            continue
        change_set = ledger_repository.get_ingestion_change_set(prior_run.ingestion_change_set_id)
        analysis_run = ledger_repository.get_analysis_run(prior_run.analysis_run_id)
        if (
            change_set is None
            or analysis_run is None
            or change_set.analysis_run_id != analysis_run.id
            or analysis_run.frozen_analysis_plan_id != frozen_analysis_plan_id
        ):
            continue
        actual = tuple(
            sorted(
                (item.analysis_unit_id, item.input_fingerprint)
                for item in ledger_repository.list_planned_items_for_analysis_run(analysis_run.id)
            )
        )
        if actual != expected:
            continue
        report = build_coverage_report(analysis_run.id, ledger_repository)
        if report.state is AnalysisCoverageState.COMPLETE and not any(
            record.terminal_status.value == "context_budget_blocked"
            for record in report.coverage_records
        ):
            return ReusableAnalysisSelection(analysis_run.id, report)
    return None


def close_ingestion_change_set(
    input: CloseIngestionChangeSetInput,
    ledger_repository: IngestionChangeSetLedger,
) -> CloseIngestionChangeSetResult:
    """Close a full, unblocked analysis scope into one immutable pending set."""
    ingestion_run = ledger_repository.get_ingestion_run(input.ingestion_run_id)
    if ingestion_run is None:
        raise ValueError("IngestionChangeSet references a missing IngestionRun.")
    analysis_run = ledger_repository.get_analysis_run(input.analysis_run_id)
    if analysis_run is None:
        raise ValueError("IngestionChangeSet references a missing AnalysisRun.")
    if (
        ingestion_run.representation_id is not None
        and analysis_run.representation_id != ingestion_run.representation_id
    ):
        raise ValueError(
            "IngestionChangeSet AnalysisRun does not match IngestionRun representation."
        )
    report = build_coverage_report(analysis_run.id, ledger_repository)
    if report.state is not AnalysisCoverageState.COMPLETE:
        raise ValueError("IngestionChangeSet requires complete analysis coverage.")
    if any(
        record.terminal_status.value == "context_budget_blocked"
        for record in report.coverage_records
    ):
        raise ValueError("IngestionChangeSet requires unblocked analysis coverage.")
    proposal_ids = tuple(
        sorted(
            {
                proposal_id
                for record in report.coverage_records
                for proposal_id in record.selected_proposal_ids
            }
        )
    )
    payload = {
        "ingestion_run_id": ingestion_run.id,
        "analysis_run_id": analysis_run.id,
        "representation_id": analysis_run.representation_id,
        "coverage_report_digest": report.report_digest,
        "proposed_change_ids": proposal_ids,
        "analysis_origin": input.analysis_origin.value,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    change_set = IngestionChangeSet(
        id=f"ics_{digest[:HASH_ID_LENGTH]}",
        ingestion_run_id=ingestion_run.id,
        analysis_run_id=analysis_run.id,
        representation_id=analysis_run.representation_id,
        coverage_report_digest=report.report_digest,
        proposed_change_ids=proposal_ids,
        analysis_origin=input.analysis_origin,
        closed_at=input.closed_at,
        change_set_digest=digest,
    )
    existing = ledger_repository.get_ingestion_change_set(change_set.id)
    if existing is not None:
        if existing.model_dump(exclude={"closed_at"}) != change_set.model_dump(
            exclude={"closed_at"}
        ):
            raise ValueError("IngestionChangeSet identity conflict.")
        return CloseIngestionChangeSetResult(existing, report)
    ledger_repository.save_ingestion_change_set(change_set)
    return CloseIngestionChangeSetResult(change_set, report)
