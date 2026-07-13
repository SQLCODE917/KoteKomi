"""Frozen analysis-plan coverage and restart-safe reconciliation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

from kotekomi_domain import (
    AnalysisPlanArtifact,
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    DocumentRepresentationBundle,
    ExtractionTask,
    ModelRun,
    ModelRunStatus,
    ProposedChange,
    ProvenanceActivity,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    AnalysisPlan,
    AnalysisUnit,
    ContextManifestStatus,
    ContextPlanningLedger,
    load_analysis_unit,
    load_context_manifest,
    validate_analysis_unit_identity,
)

HASH_ID_LENGTH = 24


class AnalysisCoverageState(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class AnalysisUnitCoverageStatus(StrEnum):
    PROCESSED_WITH_PROPOSALS = "processed_with_proposals"
    PROCESSED_NO_PROPOSALS = "processed_no_proposals"
    ABSTAINED = "abstained"
    CONTEXT_BUDGET_BLOCKED = "context_budget_blocked"
    MODEL_FAILED = "model_failed"
    SPLIT_RESOLVED = "split_resolved"
    UNREPORTED = "unreported"


class AnalysisCoverageLedger(ContextPlanningLedger, Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def save_analysis_plan_artifact(self, record: AnalysisPlanArtifact) -> None: ...
    def get_analysis_plan_artifact(self, record_id: str) -> AnalysisPlanArtifact | None: ...
    def list_context_manifest_artifacts_for_representation(
        self, representation_id: str
    ) -> tuple[ContextManifestArtifact, ...]: ...
    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None: ...
    def list_extraction_tasks(self) -> tuple[ExtractionTask, ...]: ...
    def list_model_runs(self) -> tuple[ModelRun, ...]: ...
    def list_provenance_activities(self) -> tuple[ProvenanceActivity, ...]: ...
    def list_proposed_changes(self) -> tuple[ProposedChange, ...]: ...


@dataclass(frozen=True)
class FrozenAnalysisPlan:
    id: str
    representation_id: str
    policy_id: str
    plan_digest: str
    units: tuple[AnalysisUnit, ...]


@dataclass(frozen=True)
class AnalysisUnitCoverage:
    analysis_unit_id: str
    status: AnalysisUnitCoverageStatus
    context_manifest_id: str | None
    model_run_id: str | None
    proposal_ids: tuple[str, ...]
    reason: str | None
    child_analysis_unit_ids: tuple[str, ...] = ()
    model_run_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentCoverageReport:
    frozen_plan_id: str
    representation_id: str
    state: AnalysisCoverageState
    total_pages: int
    represented_page_numbers: tuple[int, ...]
    unit_coverages: tuple[AnalysisUnitCoverage, ...]
    orphan_model_run_ids: tuple[str, ...]
    unreported_manifest_ids: tuple[str, ...]
    report_digest: str

    @property
    def complete(self) -> bool:
        return self.state is AnalysisCoverageState.COMPLETE


def freeze_analysis_plan(
    plan: AnalysisPlan,
    ledger_repository: AnalysisCoverageLedger,
) -> FrozenAnalysisPlan:
    """Persist the exact deterministic unit scope before model work begins."""
    if not plan.units:
        raise ValueError("AnalysisPlan requires at least one AnalysisUnit.")
    if any(unit.representation_id != plan.representation_id for unit in plan.units):
        raise ValueError("AnalysisPlan units must belong to its representation.")
    for unit in plan.units:
        validate_analysis_unit_identity(unit)
    if len({unit.id for unit in plan.units}) != len(plan.units):
        raise ValueError("AnalysisPlan AnalysisUnit IDs must be unique.")
    payload = _plan_payload(plan)
    digest = _digest(payload)
    frozen = FrozenAnalysisPlan(
        id=f"anp_{digest[:HASH_ID_LENGTH]}",
        representation_id=plan.representation_id,
        policy_id=plan.policy_id,
        plan_digest=digest,
        units=plan.units,
    )
    ledger_repository.save_analysis_plan_artifact(
        AnalysisPlanArtifact(
            id=frozen.id,
            representation_id=frozen.representation_id,
            plan_digest=frozen.plan_digest,
            payload=cast(dict[str, JsonValue], payload),
        )
    )
    return frozen


def load_frozen_analysis_plan(
    plan_id: str,
    ledger_repository: AnalysisCoverageLedger,
) -> FrozenAnalysisPlan:
    artifact = ledger_repository.get_analysis_plan_artifact(plan_id)
    if artifact is None:
        raise ValueError(f"Frozen AnalysisPlan is not persisted: {plan_id}")
    payload = artifact.payload
    try:
        representation_id = _required_string(payload, "representation_id")
        policy_id = _required_string(payload, "policy_id")
        units_payload = payload["units"]
        if not isinstance(units_payload, list):
            raise ValueError
        units = tuple(_analysis_unit(item) for item in units_payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Frozen AnalysisPlan payload is malformed.") from exc
    plan = AnalysisPlan(representation_id, policy_id, units)
    expected_payload = _plan_payload(plan)
    digest = _digest(expected_payload)
    if (
        artifact.id != f"anp_{digest[:HASH_ID_LENGTH]}"
        or artifact.representation_id != representation_id
        or artifact.plan_digest != digest
        or payload != expected_payload
    ):
        raise ValueError("Frozen AnalysisPlan artifact is corrupted.")
    return FrozenAnalysisPlan(artifact.id, representation_id, policy_id, digest, units)


def build_document_coverage_report(
    frozen_plan_id: str,
    ledger_repository: AnalysisCoverageLedger,
) -> DocumentCoverageReport:
    """Reconcile all planned context and model work after any restart."""
    frozen = load_frozen_analysis_plan(frozen_plan_id, ledger_repository)
    bundle = ledger_repository.get_document_representation_bundle(frozen.representation_id)
    if bundle is None:
        raise ValueError("Frozen AnalysisPlan representation is missing.")
    manifests = ledger_repository.list_context_manifest_artifacts_for_representation(
        frozen.representation_id
    )
    manifests_by_unit: dict[str, tuple[ContextManifestArtifact, ...]] = {}
    for artifact in manifests:
        manifest = load_context_manifest(artifact.id, ledger_repository)
        manifests_by_unit[manifest.analysis_unit_id] = (
            *manifests_by_unit.get(manifest.analysis_unit_id, ()),
            artifact,
        )
    tasks_by_manifest: dict[str, tuple[ExtractionTask, ...]] = {}
    for task in ledger_repository.list_extraction_tasks():
        tasks_by_manifest[task.context_manifest_id] = (
            *tasks_by_manifest.get(task.context_manifest_id, ()),
            task,
        )
    runs_by_task: dict[str, tuple[ModelRun, ...]] = {}
    for run in ledger_repository.list_model_runs():
        runs_by_task[run.extraction_task_id] = (*runs_by_task.get(run.extraction_task_id, ()), run)
    proposals_by_run = _proposals_by_run(ledger_repository)
    coverage_by_unit: dict[str, AnalysisUnitCoverage] = {}

    def reconcile(unit_id: str, visiting: frozenset[str] = frozenset()) -> AnalysisUnitCoverage:
        if unit_id in coverage_by_unit:
            return coverage_by_unit[unit_id]
        if unit_id in visiting:
            raise ValueError("AnalysisUnit split graph contains a cycle.")
        unit = next((candidate for candidate in frozen.units if candidate.id == unit_id), None)
        if unit is None:
            unit = load_analysis_unit(unit_id, ledger_repository)
        unit_manifests = manifests_by_unit.get(unit.id, ())
        if len(unit_manifests) != 1:
            coverage = AnalysisUnitCoverage(
                unit.id, AnalysisUnitCoverageStatus.UNREPORTED, None, None, (), "missing_manifest"
            )
        else:
            manifest = load_context_manifest(unit_manifests[0].id, ledger_repository)
            if manifest.status is ContextManifestStatus.CONTEXT_BUDGET_BLOCKED:
                coverage = AnalysisUnitCoverage(
                    unit.id,
                    AnalysisUnitCoverageStatus.CONTEXT_BUDGET_BLOCKED,
                    manifest.id,
                    None,
                    (),
                    manifest.blocked_reason,
                )
            elif manifest.status is ContextManifestStatus.SPLIT:
                children = tuple(
                    reconcile(child_id, visiting | {unit.id})
                    for child_id in manifest.child_analysis_unit_ids
                )
                resolved = all(
                    child.status
                    in {
                        AnalysisUnitCoverageStatus.PROCESSED_WITH_PROPOSALS,
                        AnalysisUnitCoverageStatus.PROCESSED_NO_PROPOSALS,
                        AnalysisUnitCoverageStatus.ABSTAINED,
                        AnalysisUnitCoverageStatus.SPLIT_RESOLVED,
                    }
                    for child in children
                )
                coverage = AnalysisUnitCoverage(
                    unit.id,
                    AnalysisUnitCoverageStatus.SPLIT_RESOLVED
                    if resolved
                    else AnalysisUnitCoverageStatus.UNREPORTED,
                    manifest.id,
                    None,
                    (),
                    None if resolved else "unresolved_split_child",
                    manifest.child_analysis_unit_ids,
                )
            else:
                coverage = _ready_coverage(
                    unit.id,
                    manifest.id,
                    tasks_by_manifest,
                    runs_by_task,
                    proposals_by_run,
                )
        coverage_by_unit[unit.id] = coverage
        return coverage

    planned_coverages = tuple(reconcile(unit.id) for unit in frozen.units)
    all_coverages = tuple(
        sorted(coverage_by_unit.values(), key=lambda coverage: coverage.analysis_unit_id)
    )
    known_unit_ids = set(coverage_by_unit)
    unreported_manifest_ids = tuple(
        sorted(
            artifact.id
            for unit_id, artifacts in manifests_by_unit.items()
            if unit_id not in known_unit_ids
            for artifact in artifacts
        )
    )
    known_task_ids = {
        task.id
        for coverage in all_coverages
        if coverage.context_manifest_id is not None
        for task in tasks_by_manifest.get(coverage.context_manifest_id, ())
    }
    orphan_model_run_ids = tuple(
        sorted(
            run.id
            for run in ledger_repository.list_model_runs()
            if run.extraction_task_id not in known_task_ids
        )
    )
    represented_pages = _represented_pages(bundle, frozen.units)
    total_pages = len({region.page_number for region in bundle.source_regions})
    required_success = {
        AnalysisUnitCoverageStatus.PROCESSED_WITH_PROPOSALS,
        AnalysisUnitCoverageStatus.PROCESSED_NO_PROPOSALS,
        AnalysisUnitCoverageStatus.ABSTAINED,
        AnalysisUnitCoverageStatus.SPLIT_RESOLVED,
    }
    state = (
        AnalysisCoverageState.COMPLETE
        if all(coverage.status in required_success for coverage in planned_coverages)
        and len(represented_pages) == total_pages
        and not orphan_model_run_ids
        and not unreported_manifest_ids
        else AnalysisCoverageState.INCOMPLETE
    )
    report_payload = {
        "frozen_plan_id": frozen.id,
        "representation_id": frozen.representation_id,
        "state": state.value,
        "total_pages": total_pages,
        "represented_page_numbers": represented_pages,
        "unit_coverages": [_coverage_payload(coverage) for coverage in all_coverages],
        "orphan_model_run_ids": orphan_model_run_ids,
        "unreported_manifest_ids": unreported_manifest_ids,
    }
    return DocumentCoverageReport(
        frozen.id,
        frozen.representation_id,
        state,
        total_pages,
        represented_pages,
        all_coverages,
        orphan_model_run_ids,
        unreported_manifest_ids,
        _digest(report_payload),
    )


def _ready_coverage(
    unit_id: str,
    manifest_id: str,
    tasks_by_manifest: Mapping[str, tuple[ExtractionTask, ...]],
    runs_by_task: Mapping[str, tuple[ModelRun, ...]],
    proposals_by_run: Mapping[str, tuple[str, ...]],
) -> AnalysisUnitCoverage:
    tasks = tasks_by_manifest.get(manifest_id, ())
    if not tasks:
        return AnalysisUnitCoverage(
            unit_id,
            AnalysisUnitCoverageStatus.UNREPORTED,
            manifest_id,
            None,
            (),
            "unprocessed_ready_manifest",
        )
    runs = tuple(run for task in tasks for run in runs_by_task.get(task.id, ()))
    if not runs:
        return AnalysisUnitCoverage(
            unit_id,
            AnalysisUnitCoverageStatus.UNREPORTED,
            manifest_id,
            None,
            (),
            "model_task_has_no_run",
        )
    selected = max(runs, key=lambda run: (run.completed_at, run.id))
    model_run_ids = tuple(sorted(run.id for run in runs))
    proposal_ids = tuple(
        sorted({proposal_id for run in runs for proposal_id in proposals_by_run.get(run.id, ())})
    )
    if selected.status is ModelRunStatus.SUCCEEDED:
        status = (
            AnalysisUnitCoverageStatus.PROCESSED_WITH_PROPOSALS
            if proposal_ids
            else AnalysisUnitCoverageStatus.PROCESSED_NO_PROPOSALS
        )
        return AnalysisUnitCoverage(
            unit_id,
            status,
            manifest_id,
            selected.id,
            proposal_ids,
            None,
            model_run_ids=model_run_ids,
        )
    if selected.status is ModelRunStatus.ABSTAINED:
        return AnalysisUnitCoverage(
            unit_id,
            AnalysisUnitCoverageStatus.ABSTAINED,
            manifest_id,
            selected.id,
            proposal_ids,
            None,
            model_run_ids=model_run_ids,
        )
    return AnalysisUnitCoverage(
        unit_id,
        AnalysisUnitCoverageStatus.MODEL_FAILED,
        manifest_id,
        selected.id,
        proposal_ids,
        selected.status.value,
        model_run_ids=model_run_ids,
    )


def _proposals_by_run(ledger_repository: AnalysisCoverageLedger) -> dict[str, tuple[str, ...]]:
    run_ids_by_activity = {
        activity.id: tuple(
            record_id for record_id in activity.input_ids if record_id.startswith("mrn_")
        )
        for activity in ledger_repository.list_provenance_activities()
    }
    result: dict[str, tuple[str, ...]] = {}
    for proposal in ledger_repository.list_proposed_changes():
        for run_id in run_ids_by_activity.get(proposal.provenance_activity_id or "", ()):
            result[run_id] = (*result.get(run_id, ()), proposal.id)
    return {run_id: tuple(sorted(ids)) for run_id, ids in result.items()}


def _represented_pages(
    bundle: DocumentRepresentationBundle, units: tuple[AnalysisUnit, ...]
) -> tuple[int, ...]:
    regions = {region.id: region for region in bundle.source_regions}
    nodes = {node.id: node for node in bundle.nodes}
    return tuple(
        sorted(
            {
                regions[region_id].page_number
                for unit in units
                for node_id in unit.focus_node_ids
                for region_id in nodes[node_id].source_region_ids
                if region_id in regions
            }
        )
    )


def _plan_payload(plan: AnalysisPlan) -> dict[str, object]:
    return {
        "representation_id": plan.representation_id,
        "policy_id": plan.policy_id,
        "units": [_unit_payload(unit) for unit in plan.units],
    }


def _unit_payload(unit: AnalysisUnit) -> dict[str, object]:
    return {
        "id": unit.id,
        "representation_id": unit.representation_id,
        "task_type": unit.task_type,
        "focus_node_ids": list(unit.focus_node_ids),
        "dependency_node_ids": list(unit.dependency_node_ids),
        "planner_policy_id": unit.planner_policy_id,
        "fingerprint": unit.fingerprint,
    }


def _analysis_unit(value: object) -> AnalysisUnit:
    if not isinstance(value, dict):
        raise ValueError
    payload = cast(dict[str, JsonValue], value)
    unit = AnalysisUnit(
        id=_required_string(payload, "id"),
        representation_id=_required_string(payload, "representation_id"),
        task_type=_required_string(payload, "task_type"),
        focus_node_ids=_string_tuple(payload, "focus_node_ids"),
        dependency_node_ids=_string_tuple(payload, "dependency_node_ids"),
        planner_policy_id=_required_string(payload, "planner_policy_id"),
        fingerprint=_required_string(payload, "fingerprint"),
    )
    validate_analysis_unit_identity(unit)
    return unit


def _required_string(payload: Mapping[str, JsonValue], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value:
        raise ValueError
    return value


def _string_tuple(payload: Mapping[str, JsonValue], key: str) -> tuple[str, ...]:
    value = payload[key]
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError
    return tuple(cast(str, item) for item in value)


def _coverage_payload(coverage: AnalysisUnitCoverage) -> dict[str, object]:
    return {
        "analysis_unit_id": coverage.analysis_unit_id,
        "status": coverage.status.value,
        "context_manifest_id": coverage.context_manifest_id,
        "model_run_id": coverage.model_run_id,
        "model_run_ids": coverage.model_run_ids,
        "proposal_ids": coverage.proposal_ids,
        "reason": coverage.reason,
        "child_analysis_unit_ids": coverage.child_analysis_unit_ids,
    }


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
