"""Run-scoped analysis coverage and restart-safe reconciliation.

An ``AnalysisPlanArtifact`` names deterministic work.  It is not an execution
identity.  ``AnalysisRunArtifact`` freezes one invocation's selected manifests
and tasks, while ``AnalysisItemAttempt`` appends its own model-run history.
Coverage therefore never discovers membership by scanning the representation or
the corpus.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, cast

from kotekomi_domain import (
    AnalysisItemAttempt,
    AnalysisItemManifestSelection,
    AnalysisItemTaskSelection,
    AnalysisPlanArtifact,
    AnalysisRunArtifact,
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    DocumentRepresentationBundle,
    ExtractionTask,
    ModelRun,
    ModelRunStatus,
    PlannedAnalysisItem,
    ProcessingAttempt,
    ProposedChange,
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
PRIMARY_SELECTION_ROLE = "primary"
PRIMARY_EXECUTION_ROLE = "primary"


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
    def commit_analysis_run_scope(
        self,
        *,
        analysis_run: AnalysisRunArtifact,
        planned_items: tuple[PlannedAnalysisItem, ...],
        manifest_selections: tuple[AnalysisItemManifestSelection, ...],
        task_selections: tuple[AnalysisItemTaskSelection, ...],
    ) -> None: ...
    def get_analysis_run(self, record_id: str) -> AnalysisRunArtifact | None: ...
    def list_planned_analysis_items(
        self, analysis_run_id: str
    ) -> tuple[PlannedAnalysisItem, ...]: ...
    def list_analysis_item_manifest_selections(
        self, item_ids: tuple[str, ...]
    ) -> tuple[AnalysisItemManifestSelection, ...]: ...
    def list_analysis_item_task_selections(
        self, item_ids: tuple[str, ...]
    ) -> tuple[AnalysisItemTaskSelection, ...]: ...
    def list_analysis_item_attempts(
        self, item_ids: tuple[str, ...]
    ) -> tuple[AnalysisItemAttempt, ...]: ...
    def save_analysis_item_attempt(self, record: AnalysisItemAttempt) -> None: ...
    def get_context_manifests_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ContextManifestArtifact, ...]: ...
    def get_extraction_tasks_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ExtractionTask, ...]: ...
    def get_model_runs_by_ids(self, record_ids: tuple[str, ...]) -> tuple[ModelRun, ...]: ...
    def get_processing_attempts_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ProcessingAttempt, ...]: ...
    def list_proposed_changes_for_model_run(
        self, model_run_id: str
    ) -> tuple[ProposedChange, ...]: ...
    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None: ...


@dataclass(frozen=True)
class FrozenAnalysisPlan:
    id: str
    representation_id: str
    policy_id: str
    plan_digest: str
    units: tuple[AnalysisUnit, ...]


@dataclass(frozen=True)
class AnalysisRunItemInput:
    analysis_unit_id: str
    task_type: str
    input_fingerprint: str
    context_manifest_id: str | None
    extraction_task_id: str | None
    required: bool = True
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisRunInput:
    document_id: str
    frozen_plan_id: str
    coverage_policy_id: str
    coverage_policy_digest: str
    started_at: datetime
    items: tuple[AnalysisRunItemInput, ...]


@dataclass(frozen=True)
class AnalysisRunStart:
    analysis_run: AnalysisRunArtifact
    planned_items: tuple[PlannedAnalysisItem, ...]


@dataclass(frozen=True)
class AnalysisUnitCoverage:
    planned_item_id: str
    analysis_unit_id: str
    status: AnalysisUnitCoverageStatus
    context_manifest_id: str | None
    extraction_task_id: str | None
    model_run_id: str | None
    proposal_ids: tuple[str, ...]
    reason: str | None
    child_analysis_unit_ids: tuple[str, ...] = ()
    model_run_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentCoverageReport:
    analysis_run_id: str
    frozen_plan_id: str
    representation_id: str
    state: AnalysisCoverageState
    total_pages: int
    represented_page_numbers: tuple[int, ...]
    unit_coverages: tuple[AnalysisUnitCoverage, ...]
    orphan_model_run_ids: tuple[str, ...]
    scope_digest: str
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


def start_analysis_run(
    run_input: AnalysisRunInput,
    ledger_repository: AnalysisCoverageLedger,
) -> AnalysisRunStart:
    """Freeze an invocation's selected context/task membership atomically."""
    frozen = load_frozen_analysis_plan(run_input.frozen_plan_id, ledger_repository)
    bundle = ledger_repository.get_document_representation_bundle(frozen.representation_id)
    if bundle is None or bundle.representation.document_id != run_input.document_id:
        raise ValueError("AnalysisRun document does not own the frozen representation.")
    if not run_input.items:
        raise ValueError("AnalysisRun requires at least one planned item.")
    if len({item.analysis_unit_id for item in run_input.items}) != len(run_input.items):
        raise ValueError("AnalysisRun may select each AnalysisUnit only once.")
    frozen_ids = {unit.id for unit in frozen.units}
    input_ids = {item.analysis_unit_id for item in run_input.items}
    if not frozen_ids.issubset(input_ids):
        raise ValueError("AnalysisRun must include every frozen AnalysisPlan unit.")
    if any(
        not item.task_type or not _is_digest(item.input_fingerprint) for item in run_input.items
    ):
        raise ValueError("AnalysisRun item task types and input fingerprints are required.")
    if not run_input.coverage_policy_id or not _is_digest(run_input.coverage_policy_digest):
        raise ValueError("AnalysisRun coverage policy identity is invalid.")

    manifest_ids = tuple(
        sorted({item.context_manifest_id for item in run_input.items if item.context_manifest_id})
    )
    manifests = {
        artifact.id: artifact
        for artifact in ledger_repository.get_context_manifests_by_ids(manifest_ids)
    }
    task_ids = tuple(
        sorted({item.extraction_task_id for item in run_input.items if item.extraction_task_id})
    )
    tasks = {task.id: task for task in ledger_repository.get_extraction_tasks_by_ids(task_ids)}
    split_child_ids: set[str] = set()
    for item in run_input.items:
        unit = load_analysis_unit(item.analysis_unit_id, ledger_repository)
        if unit.representation_id != frozen.representation_id:
            raise ValueError("AnalysisRun item is outside the frozen representation.")
        if item.context_manifest_id is None:
            if item.extraction_task_id is not None:
                raise ValueError("AnalysisRun task selection requires a manifest selection.")
            continue
        artifact = manifests.get(item.context_manifest_id)
        if artifact is None:
            raise ValueError("AnalysisRun selected ContextManifest is not persisted.")
        manifest = load_context_manifest(artifact.id, ledger_repository)
        if (
            manifest.analysis_unit_id != item.analysis_unit_id
            or manifest.representation_id != frozen.representation_id
            or manifest.manifest_digest != artifact.manifest_digest
        ):
            raise ValueError("AnalysisRun selected ContextManifest binding is invalid.")
        if manifest.status is ContextManifestStatus.SPLIT:
            split_child_ids.update(manifest.child_analysis_unit_ids)
        if item.extraction_task_id is None:
            continue
        task = tasks.get(item.extraction_task_id)
        if task is None:
            raise ValueError("AnalysisRun selected ExtractionTask is not persisted.")
        if (
            task.context_manifest_id != manifest.id
            or task.context_manifest_digest != manifest.manifest_digest
            or task.task_type != item.task_type
            or task.task_fingerprint != item.input_fingerprint
        ):
            raise ValueError("AnalysisRun selected ExtractionTask binding is invalid.")
    if input_ids - frozen_ids - split_child_ids:
        raise ValueError("AnalysisRun includes an unplanned non-split AnalysisUnit.")

    run_id = f"arn_{uuid.uuid4().hex}"
    sorted_inputs = tuple(sorted(run_input.items, key=lambda item: item.analysis_unit_id))
    item_by_unit = {
        item.analysis_unit_id: PlannedAnalysisItem(
            id=_scoped_id("pai", run_id=run_id, analysis_unit_id=item.analysis_unit_id),
            analysis_run_id=run_id,
            analysis_unit_id=item.analysis_unit_id,
            task_type=item.task_type,
            required=item.required,
            ordinal=index,
            dependencies=(),
            input_fingerprint=item.input_fingerprint,
        )
        for index, item in enumerate(sorted_inputs)
    }
    planned_items = tuple(item_by_unit[item.analysis_unit_id] for item in sorted_inputs)
    _validate_dependencies(sorted_inputs, item_by_unit)
    planned_items = tuple(
        item.model_copy(
            update={
                "dependencies": tuple(
                    item_by_unit[dependency].id for dependency in source.dependencies
                )
            }
        )
        for item, source in zip(planned_items, sorted_inputs, strict=True)
    )
    item_by_unit = {item.analysis_unit_id: item for item in planned_items}
    manifest_selections = tuple(
        AnalysisItemManifestSelection(
            id=_scoped_id(
                "ams",
                item_id=item_by_unit[source.analysis_unit_id].id,
                manifest_id=source.context_manifest_id,
                role=PRIMARY_SELECTION_ROLE,
            ),
            planned_item_id=item_by_unit[source.analysis_unit_id].id,
            context_manifest_id=source.context_manifest_id,
            selection_role=PRIMARY_SELECTION_ROLE,
        )
        for source in sorted_inputs
        if source.context_manifest_id is not None
    )
    task_selections = tuple(
        AnalysisItemTaskSelection(
            id=_scoped_id(
                "ats",
                item_id=item_by_unit[source.analysis_unit_id].id,
                task_id=source.extraction_task_id,
                role=PRIMARY_SELECTION_ROLE,
            ),
            planned_item_id=item_by_unit[source.analysis_unit_id].id,
            extraction_task_id=source.extraction_task_id,
            selection_role=PRIMARY_SELECTION_ROLE,
        )
        for source in sorted_inputs
        if source.extraction_task_id is not None
    )
    scope_payload = _scope_payload(
        document_id=run_input.document_id,
        frozen=frozen,
        coverage_policy_id=run_input.coverage_policy_id,
        coverage_policy_digest=run_input.coverage_policy_digest,
        items=sorted_inputs,
    )
    run = AnalysisRunArtifact(
        id=run_id,
        document_id=run_input.document_id,
        representation_id=frozen.representation_id,
        analysis_plan_id=frozen.id,
        frozen_plan_digest=frozen.plan_digest,
        coverage_policy_id=run_input.coverage_policy_id,
        coverage_policy_digest=run_input.coverage_policy_digest,
        scope_digest=_digest(scope_payload),
        started_at=run_input.started_at,
    )
    ledger_repository.commit_analysis_run_scope(
        analysis_run=run,
        planned_items=planned_items,
        manifest_selections=manifest_selections,
        task_selections=task_selections,
    )
    return AnalysisRunStart(run, planned_items)


def record_analysis_item_attempt(
    *,
    analysis_run_id: str,
    analysis_unit_id: str,
    model_run_id: str,
    ledger_repository: AnalysisCoverageLedger,
) -> AnalysisItemAttempt:
    """Append a run-specific execution membership link after model work."""
    items = ledger_repository.list_planned_analysis_items(analysis_run_id)
    item = next(
        (candidate for candidate in items if candidate.analysis_unit_id == analysis_unit_id), None
    )
    if item is None:
        raise ValueError("AnalysisUnit is not in the AnalysisRun scope.")
    task_selections = tuple(
        selection
        for selection in ledger_repository.list_analysis_item_task_selections((item.id,))
        if selection.selection_role == PRIMARY_SELECTION_ROLE
    )
    if len(task_selections) != 1:
        raise ValueError(
            "AnalysisItem requires exactly one selected extraction task before attempts."
        )
    model_runs = ledger_repository.get_model_runs_by_ids((model_run_id,))
    if (
        len(model_runs) != 1
        or model_runs[0].extraction_task_id != task_selections[0].extraction_task_id
    ):
        raise ValueError("ModelRun does not belong to the AnalysisRun selected task.")
    attempt = AnalysisItemAttempt(
        id=_scoped_id(
            "aia",
            planned_item_id=item.id,
            model_run_id=model_run_id,
            role=PRIMARY_EXECUTION_ROLE,
        ),
        planned_item_id=item.id,
        model_run_id=model_run_id,
        execution_role=PRIMARY_EXECUTION_ROLE,
    )
    ledger_repository.save_analysis_item_attempt(attempt)
    return attempt


def build_coverage_report(
    analysis_run_id: str,
    ledger_repository: AnalysisCoverageLedger,
) -> DocumentCoverageReport:
    """Reconcile one immutable run scope without corpus-wide discovery."""
    run = ledger_repository.get_analysis_run(analysis_run_id)
    if run is None:
        raise ValueError(f"AnalysisRun is not persisted: {analysis_run_id}")
    frozen = load_frozen_analysis_plan(run.analysis_plan_id, ledger_repository)
    if (
        frozen.plan_digest != run.frozen_plan_digest
        or frozen.representation_id != run.representation_id
    ):
        raise ValueError("AnalysisRun frozen plan binding is corrupted.")
    bundle = ledger_repository.get_document_representation_bundle(run.representation_id)
    if bundle is None or bundle.representation.document_id != run.document_id:
        raise ValueError("AnalysisRun representation binding is corrupted.")
    items = ledger_repository.list_planned_analysis_items(run.id)
    if not items:
        raise ValueError("AnalysisRun has no persisted planned items.")
    if len({item.id for item in items}) != len(items) or any(
        item.analysis_run_id != run.id for item in items
    ):
        raise ValueError("AnalysisRun planned-item scope is corrupted.")
    item_ids = tuple(item.id for item in items)
    manifests_by_item = _manifest_selections_by_item(
        ledger_repository.list_analysis_item_manifest_selections(item_ids)
    )
    tasks_by_item = _task_selections_by_item(
        ledger_repository.list_analysis_item_task_selections(item_ids)
    )
    attempts_by_item = _attempts_by_item(ledger_repository.list_analysis_item_attempts(item_ids))
    manifest_ids = tuple(
        sorted(
            {
                selection.context_manifest_id
                for selections in manifests_by_item.values()
                for selection in selections
            }
        )
    )
    task_ids = tuple(
        sorted(
            {
                selection.extraction_task_id
                for selections in tasks_by_item.values()
                for selection in selections
            }
        )
    )
    manifests = {
        artifact.id: artifact
        for artifact in ledger_repository.get_context_manifests_by_ids(manifest_ids)
    }
    tasks = {task.id: task for task in ledger_repository.get_extraction_tasks_by_ids(task_ids)}
    run_ids = tuple(
        sorted(
            {
                attempt.model_run_id
                for attempts in attempts_by_item.values()
                for attempt in attempts
                if attempt.model_run_id is not None
            }
        )
    )
    model_runs = {record.id: record for record in ledger_repository.get_model_runs_by_ids(run_ids)}
    coverages: dict[str, AnalysisUnitCoverage] = {}
    failed = False
    orphan_model_run_ids: set[str] = set()

    def reconcile(
        item: PlannedAnalysisItem, visiting: frozenset[str] = frozenset()
    ) -> AnalysisUnitCoverage:
        nonlocal failed
        if item.id in coverages:
            return coverages[item.id]
        if item.id in visiting:
            raise ValueError("AnalysisRun planned-item dependency graph contains a cycle.")
        selections = _primary_manifest_selections(manifests_by_item.get(item.id, ()))
        if len(selections) == 0:
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                None,
                None,
                None,
                (),
                "missing_manifest",
            )
        if len(selections) != 1:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                None,
                None,
                None,
                (),
                "ambiguous_manifest",
            )
        selection = selections[0]
        artifact = manifests.get(selection.context_manifest_id)
        if artifact is None:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                selection.context_manifest_id,
                None,
                None,
                (),
                "selected_manifest_missing",
            )
        try:
            manifest = load_context_manifest(artifact.id, ledger_repository)
        except ValueError:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                "manifest_integrity_failure",
            )
        if manifest.analysis_unit_id != item.analysis_unit_id:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                "manifest_unit_mismatch",
            )
        if manifest.representation_id != run.representation_id:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                "manifest_representation_mismatch",
            )
        if manifest.manifest_digest != artifact.manifest_digest:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                "manifest_digest_mismatch",
            )
        if manifest.status is ContextManifestStatus.CONTEXT_BUDGET_BLOCKED:
            return _store(
                item,
                AnalysisUnitCoverageStatus.CONTEXT_BUDGET_BLOCKED,
                manifest.id,
                None,
                None,
                (),
                manifest.blocked_reason,
            )
        if manifest.status is ContextManifestStatus.SPLIT:
            child_items = {candidate.analysis_unit_id: candidate for candidate in items}
            missing_children = tuple(
                child_id
                for child_id in manifest.child_analysis_unit_ids
                if child_id not in child_items
            )
            if missing_children:
                return _store(
                    item,
                    AnalysisUnitCoverageStatus.UNREPORTED,
                    manifest.id,
                    None,
                    None,
                    (),
                    "unresolved_split_child",
                    manifest.child_analysis_unit_ids,
                )
            children = tuple(
                reconcile(child_items[child_id], visiting | {item.id})
                for child_id in manifest.child_analysis_unit_ids
            )
            resolved = all(child.status in _TERMINAL_SUCCESS for child in children)
            return _store(
                item,
                AnalysisUnitCoverageStatus.SPLIT_RESOLVED
                if resolved
                else AnalysisUnitCoverageStatus.UNREPORTED,
                manifest.id,
                None,
                None,
                (),
                None if resolved else "unresolved_split_child",
                manifest.child_analysis_unit_ids,
            )
        task_selection = _primary_task_selections(tasks_by_item.get(item.id, ()))
        if len(task_selection) == 0:
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                manifest.id,
                None,
                None,
                (),
                "missing_extraction_task",
            )
        if len(task_selection) != 1:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                manifest.id,
                None,
                None,
                (),
                "ambiguous_extraction_task",
            )
        task = tasks.get(task_selection[0].extraction_task_id)
        if task is None:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                manifest.id,
                task_selection[0].extraction_task_id,
                None,
                (),
                "selected_extraction_task_missing",
            )
        if (
            task.context_manifest_id != manifest.id
            or task.context_manifest_digest != manifest.manifest_digest
        ):
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                manifest.id,
                task.id,
                None,
                (),
                "task_manifest_mismatch",
            )
        if task.task_type != item.task_type or task.task_fingerprint != item.input_fingerprint:
            failed = True
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                manifest.id,
                task.id,
                None,
                (),
                "task_input_mismatch",
            )
        attempts = tuple(
            attempt
            for attempt in attempts_by_item.get(item.id, ())
            if (
                attempt.execution_role == PRIMARY_EXECUTION_ROLE
                and attempt.model_run_id is not None
            )
        )
        valid_runs: list[ModelRun] = []
        for attempt in attempts:
            assert attempt.model_run_id is not None
            linked = model_runs.get(attempt.model_run_id)
            if linked is None or linked.extraction_task_id != task.id:
                orphan_model_run_ids.add(attempt.model_run_id)
            else:
                valid_runs.append(linked)
        if not valid_runs:
            return _store(
                item,
                AnalysisUnitCoverageStatus.UNREPORTED,
                manifest.id,
                task.id,
                None,
                (),
                "model_task_has_no_run",
            )
        selected = max(valid_runs, key=lambda candidate: (candidate.completed_at, candidate.id))
        proposal_ids = tuple(
            proposal.id
            for proposal in ledger_repository.list_proposed_changes_for_model_run(selected.id)
        )
        all_run_ids = tuple(sorted(run.id for run in valid_runs))
        if selected.status is ModelRunStatus.SUCCEEDED:
            return _store(
                item,
                AnalysisUnitCoverageStatus.PROCESSED_WITH_PROPOSALS
                if proposal_ids
                else AnalysisUnitCoverageStatus.PROCESSED_NO_PROPOSALS,
                manifest.id,
                task.id,
                selected.id,
                proposal_ids,
                None,
                model_run_ids=all_run_ids,
            )
        if selected.status is ModelRunStatus.ABSTAINED:
            return _store(
                item,
                AnalysisUnitCoverageStatus.ABSTAINED,
                manifest.id,
                task.id,
                selected.id,
                (),
                None,
                model_run_ids=all_run_ids,
            )
        return _store(
            item,
            AnalysisUnitCoverageStatus.MODEL_FAILED,
            manifest.id,
            task.id,
            selected.id,
            (),
            selected.status.value,
            model_run_ids=all_run_ids,
        )

    def _store(
        item: PlannedAnalysisItem,
        status: AnalysisUnitCoverageStatus,
        manifest_id: str | None,
        task_id: str | None,
        model_run_id: str | None,
        proposal_ids: tuple[str, ...],
        reason: str | None,
        child_ids: tuple[str, ...] = (),
        *,
        model_run_ids: tuple[str, ...] = (),
    ) -> AnalysisUnitCoverage:
        coverage = AnalysisUnitCoverage(
            item.id,
            item.analysis_unit_id,
            status,
            manifest_id,
            task_id,
            model_run_id,
            proposal_ids,
            reason,
            child_ids,
            model_run_ids,
        )
        coverages[item.id] = coverage
        return coverage

    for item in sorted(items, key=lambda candidate: (candidate.ordinal, candidate.id)):
        reconcile(item)
    all_coverages = tuple(sorted(coverages.values(), key=lambda coverage: coverage.planned_item_id))
    represented_pages = _represented_pages(bundle, items, ledger_repository)
    total_pages = len({region.page_number for region in bundle.source_regions})
    state = (
        AnalysisCoverageState.FAILED
        if failed
        else AnalysisCoverageState.COMPLETE
        if all(coverage.status in _TERMINAL_SUCCESS for coverage in all_coverages)
        and len(represented_pages) == total_pages
        and not orphan_model_run_ids
        else AnalysisCoverageState.INCOMPLETE
    )
    report_payload = {
        "analysis_run_id": run.id,
        "frozen_plan_id": run.analysis_plan_id,
        "representation_id": run.representation_id,
        "state": state.value,
        "total_pages": total_pages,
        "represented_page_numbers": represented_pages,
        "unit_coverages": [_coverage_payload(coverage) for coverage in all_coverages],
        "orphan_model_run_ids": sorted(orphan_model_run_ids),
        "scope_digest": run.scope_digest,
    }
    return DocumentCoverageReport(
        run.id,
        run.analysis_plan_id,
        run.representation_id,
        state,
        total_pages,
        represented_pages,
        all_coverages,
        tuple(sorted(orphan_model_run_ids)),
        run.scope_digest,
        _digest(report_payload),
    )


_TERMINAL_SUCCESS = frozenset(
    {
        AnalysisUnitCoverageStatus.PROCESSED_WITH_PROPOSALS,
        AnalysisUnitCoverageStatus.PROCESSED_NO_PROPOSALS,
        AnalysisUnitCoverageStatus.ABSTAINED,
        AnalysisUnitCoverageStatus.CONTEXT_BUDGET_BLOCKED,
        AnalysisUnitCoverageStatus.SPLIT_RESOLVED,
    }
)


def _manifest_selections_by_item(
    records: tuple[AnalysisItemManifestSelection, ...],
) -> dict[str, tuple[AnalysisItemManifestSelection, ...]]:
    grouped: dict[str, tuple[AnalysisItemManifestSelection, ...]] = {}
    for record in records:
        grouped[record.planned_item_id] = (*grouped.get(record.planned_item_id, ()), record)
    return grouped


def _task_selections_by_item(
    records: tuple[AnalysisItemTaskSelection, ...],
) -> dict[str, tuple[AnalysisItemTaskSelection, ...]]:
    grouped: dict[str, tuple[AnalysisItemTaskSelection, ...]] = {}
    for record in records:
        grouped[record.planned_item_id] = (*grouped.get(record.planned_item_id, ()), record)
    return grouped


def _attempts_by_item(
    records: tuple[AnalysisItemAttempt, ...],
) -> dict[str, tuple[AnalysisItemAttempt, ...]]:
    grouped: dict[str, tuple[AnalysisItemAttempt, ...]] = {}
    for record in records:
        grouped[record.planned_item_id] = (*grouped.get(record.planned_item_id, ()), record)
    return grouped


def _primary_manifest_selections(
    records: tuple[AnalysisItemManifestSelection, ...],
) -> tuple[AnalysisItemManifestSelection, ...]:
    return tuple(record for record in records if record.selection_role == PRIMARY_SELECTION_ROLE)


def _primary_task_selections(
    records: tuple[AnalysisItemTaskSelection, ...],
) -> tuple[AnalysisItemTaskSelection, ...]:
    return tuple(record for record in records if record.selection_role == PRIMARY_SELECTION_ROLE)


def _represented_pages(
    bundle: DocumentRepresentationBundle,
    items: tuple[PlannedAnalysisItem, ...],
    ledger_repository: AnalysisCoverageLedger,
) -> tuple[int, ...]:
    regions = {region.id: region for region in bundle.source_regions}
    nodes = {node.id: node for node in bundle.nodes}
    pages: set[int] = set()
    for item in items:
        unit = load_analysis_unit(item.analysis_unit_id, ledger_repository)
        for node_id in unit.focus_node_ids:
            node = nodes.get(node_id)
            if node is None:
                raise ValueError("AnalysisRun unit focus node is missing from its representation.")
            pages.update(
                regions[region_id].page_number
                for region_id in node.source_region_ids
                if region_id in regions
            )
    return tuple(sorted(pages))


def _validate_dependencies(
    inputs: tuple[AnalysisRunItemInput, ...],
    item_by_unit: dict[str, PlannedAnalysisItem],
) -> None:
    for item in inputs:
        if any(dependency not in item_by_unit for dependency in item.dependencies):
            raise ValueError("AnalysisRun item dependency is outside the frozen scope.")
        if item.analysis_unit_id in item.dependencies:
            raise ValueError("AnalysisRun item cannot depend on itself.")


def _scope_payload(
    *,
    document_id: str,
    frozen: FrozenAnalysisPlan,
    coverage_policy_id: str,
    coverage_policy_digest: str,
    items: tuple[AnalysisRunItemInput, ...],
) -> dict[str, object]:
    return {
        "document_id": document_id,
        "representation_id": frozen.representation_id,
        "analysis_plan_id": frozen.id,
        "frozen_plan_digest": frozen.plan_digest,
        "coverage_policy_id": coverage_policy_id,
        "coverage_policy_digest": coverage_policy_digest,
        "items": [
            {
                "analysis_unit_id": item.analysis_unit_id,
                "task_type": item.task_type,
                "input_fingerprint": item.input_fingerprint,
                "context_manifest_id": item.context_manifest_id,
                "extraction_task_id": item.extraction_task_id,
                "required": item.required,
                "dependencies": list(item.dependencies),
            }
            for item in items
        ],
    }


def _coverage_payload(coverage: AnalysisUnitCoverage) -> dict[str, object]:
    return {
        "planned_item_id": coverage.planned_item_id,
        "analysis_unit_id": coverage.analysis_unit_id,
        "status": coverage.status.value,
        "context_manifest_id": coverage.context_manifest_id,
        "extraction_task_id": coverage.extraction_task_id,
        "model_run_id": coverage.model_run_id,
        "proposal_ids": list(coverage.proposal_ids),
        "reason": coverage.reason,
        "child_analysis_unit_ids": list(coverage.child_analysis_unit_ids),
        "model_run_ids": list(coverage.model_run_ids),
    }


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


def _required_string(payload: dict[str, JsonValue], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value:
        raise ValueError
    return value


def _string_tuple(payload: dict[str, JsonValue], key: str) -> tuple[str, ...]:
    value = payload[key]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError
    return cast(tuple[str, ...], tuple(value))


def _is_digest(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _scoped_id(prefix: str, **payload: object) -> str:
    return f"{prefix}_{_digest(payload)[:HASH_ID_LENGTH]}"
