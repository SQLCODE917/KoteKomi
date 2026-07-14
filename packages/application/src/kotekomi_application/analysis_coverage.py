"""Run-scoped analysis coverage and restart-safe reconciliation.

An ``AnalysisPlanArtifact`` names deterministic work.  It is not an execution
identity.  ``AnalysisRun`` freezes one invocation's planned scope, while
``AnalysisItemAttempt`` appends references to existing execution records.
Coverage therefore never discovers membership by scanning the representation or
the corpus.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, cast

from kotekomi_domain import (
    AnalysisItemAttempt,
    AnalysisPlanArtifact,
    AnalysisRun,
    AnalysisRunState,
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    DocumentRepresentationBundle,
    ExtractionTask,
    ModelRun,
    ModelRunStatus,
    PdfPreflightReport,
    PlannedAnalysisItem,
    ProcessingAttempt,
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
PRIMARY_EXECUTION_ROLE = "primary"
LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID = "latest_completed_valid_attempt_v1"


class AnalysisCoverageState(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class CoverageTerminalStatus(StrEnum):
    PROCESSED_WITH_PROPOSALS = "processed_with_proposals"
    PROCESSED_NO_PROPOSALS = "processed_no_proposals"
    ABSTAINED = "abstained"
    CONTEXT_BUDGET_BLOCKED = "context_budget_blocked"
    MODEL_FAILED = "model_failed"
    SPLIT_RESOLVED = "split_resolved"
    UNREPORTED = "unreported"


class CoveragePolicyDecision(StrEnum):
    SELECTION_NOT_APPLICABLE = "selection_not_applicable"
    NO_COMPLETED_VALID_ATTEMPT = "no_completed_valid_attempt"
    SELECTED_LATEST_COMPLETED_VALID_ATTEMPT = "selected_latest_completed_valid_attempt"


class CoverageIntegrityFailureReason(StrEnum):
    MISSING_MANIFEST = "missing_manifest"
    MULTIPLE_MANIFESTS = "multiple_manifests"
    UNEXPECTED_MANIFEST = "unexpected_manifest"
    MISSING_SELECTED_RUN = "missing_selected_run"
    RUN_TASK_MISMATCH = "run_task_mismatch"
    PROPOSAL_RUN_MISMATCH = "proposal_run_mismatch"
    SPLIT_CYCLE = "split_cycle"


class AnalysisCoverageLedger(ContextPlanningLedger, Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def find_latest_complete_pdf_preflight_report_for_task(
        self, task_fingerprint_id: str
    ) -> PdfPreflightReport | None: ...
    def save_analysis_plan_artifact(self, record: AnalysisPlanArtifact) -> None: ...
    def get_analysis_plan_artifact(self, record_id: str) -> AnalysisPlanArtifact | None: ...
    def commit_analysis_run_scope(
        self,
        *,
        analysis_run: AnalysisRun,
        planned_items: tuple[PlannedAnalysisItem, ...],
    ) -> None: ...
    def get_analysis_run(self, record_id: str) -> AnalysisRun | None: ...
    def list_planned_items_for_analysis_run(
        self, analysis_run_id: str
    ) -> tuple[PlannedAnalysisItem, ...]: ...
    def list_analysis_item_attempts_for_items(
        self, item_ids: tuple[str, ...]
    ) -> tuple[AnalysisItemAttempt, ...]: ...
    def save_analysis_item_attempt(self, record: AnalysisItemAttempt) -> None: ...
    def list_context_manifests_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ContextManifestArtifact, ...]: ...
    def list_extraction_tasks_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ExtractionTask, ...]: ...
    def list_extraction_tasks_for_manifest_ids(
        self, manifest_ids: tuple[str, ...]
    ) -> tuple[ExtractionTask, ...]: ...
    def list_model_runs_by_ids(self, record_ids: tuple[str, ...]) -> tuple[ModelRun, ...]: ...
    def list_processing_attempts_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ProcessingAttempt, ...]: ...
    def list_proposed_changes_for_model_run(
        self, model_run_id: str
    ) -> tuple[ProposedChange, ...]: ...
    def list_provenance_activities_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ProvenanceActivity, ...]: ...
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
    expected_manifest_id: str | None
    required: bool = True
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisRunInput:
    document_id: str
    frozen_plan_id: str
    coverage_policy_id: str
    started_at: datetime
    items: tuple[AnalysisRunItemInput, ...]


@dataclass(frozen=True)
class SelectedCoverageOutcome:
    selected_attempt: AnalysisItemAttempt | None
    all_model_run_ids: tuple[str, ...]
    policy_decision: CoveragePolicyDecision


class CoveragePolicy(Protocol):
    @property
    def policy_id(self) -> str: ...

    def select_current_attempt(
        self,
        planned_item: PlannedAnalysisItem,
        attempts: tuple[AnalysisItemAttempt, ...],
    ) -> SelectedCoverageOutcome: ...


@dataclass(frozen=True)
class LatestCompletedValidAttemptCoveragePolicy:
    """Select the last immutable ModelRun linked by a valid item attempt."""

    model_runs_by_id: dict[str, ModelRun]

    @property
    def policy_id(self) -> str:
        return LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID

    def select_current_attempt(
        self,
        planned_item: PlannedAnalysisItem,
        attempts: tuple[AnalysisItemAttempt, ...],
    ) -> SelectedCoverageOutcome:
        candidates = tuple(
            (attempt, self.model_runs_by_id[attempt.model_run_id])
            for attempt in attempts
            if attempt.execution_role == PRIMARY_EXECUTION_ROLE
            and attempt.model_run_id is not None
            and attempt.model_run_id in self.model_runs_by_id
            and self.model_runs_by_id[attempt.model_run_id].task_fingerprint
            == planned_item.input_fingerprint
        )
        all_model_run_ids = tuple(sorted({run.id for _, run in candidates}))
        if not candidates:
            return SelectedCoverageOutcome(
                selected_attempt=None,
                all_model_run_ids=(),
                policy_decision=CoveragePolicyDecision.NO_COMPLETED_VALID_ATTEMPT,
            )
        selected_attempt, _ = max(
            candidates,
            key=lambda candidate: (
                candidate[1].completed_at,
                candidate[1].id,
                candidate[0].id,
            ),
        )
        return SelectedCoverageOutcome(
            selected_attempt=selected_attempt,
            all_model_run_ids=all_model_run_ids,
            policy_decision=CoveragePolicyDecision.SELECTED_LATEST_COMPLETED_VALID_ATTEMPT,
        )


@dataclass(frozen=True)
class CoverageRecord:
    planned_item_id: str
    analysis_unit_id: str
    terminal_status: CoverageTerminalStatus
    context_manifest_id: str | None
    extraction_task_id: str | None
    selected_model_run_id: str | None
    selected_proposal_ids: tuple[str, ...]
    all_model_run_ids: tuple[str, ...]
    policy_decision: CoveragePolicyDecision
    blocking_reason: str | None
    abstention_reason: str | None
    child_analysis_unit_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoverageReport:
    analysis_run_id: str
    frozen_plan_id: str
    representation_id: str
    coverage_policy_id: str
    state: AnalysisCoverageState
    total_pages: int
    represented_page_numbers: tuple[int, ...]
    coverage_records: tuple[CoverageRecord, ...]
    integrity_failure_reasons: tuple[CoverageIntegrityFailureReason, ...]
    orphan_model_run_ids: tuple[str, ...]
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
) -> AnalysisRun:
    """Freeze one authoritative run and its complete planned-item scope."""
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
    if run_input.coverage_policy_id != LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID:
        raise ValueError("AnalysisRun coverage policy identity is unknown.")

    manifest_ids = tuple(
        sorted({item.expected_manifest_id for item in run_input.items if item.expected_manifest_id})
    )
    manifests = {
        artifact.id: artifact
        for artifact in ledger_repository.list_context_manifests_by_ids(manifest_ids)
    }
    split_child_ids: set[str] = set()
    for item in run_input.items:
        unit = load_analysis_unit(item.analysis_unit_id, ledger_repository)
        if unit.representation_id != frozen.representation_id:
            raise ValueError("AnalysisRun item is outside the frozen representation.")
        if item.expected_manifest_id is None:
            continue
        artifact = manifests.get(item.expected_manifest_id)
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
    if input_ids - frozen_ids - split_child_ids:
        raise ValueError("AnalysisRun includes an unplanned non-split AnalysisUnit.")

    run_id = f"arn_{uuid.uuid4().hex}"
    sorted_inputs = tuple(sorted(run_input.items, key=lambda item: item.analysis_unit_id))
    item_by_unit = {
        source.analysis_unit_id: PlannedAnalysisItem(
            id=_scoped_id("pai", run_id=run_id, analysis_unit_id=source.analysis_unit_id),
            analysis_run_id=run_id,
            analysis_unit_id=source.analysis_unit_id,
            task_type=source.task_type,
            required=source.required,
            dependencies=(),
            expected_manifest_id=source.expected_manifest_id,
            input_fingerprint=source.input_fingerprint,
        )
        for source in sorted_inputs
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
    run = AnalysisRun(
        id=run_id,
        document_id=run_input.document_id,
        representation_id=frozen.representation_id,
        frozen_analysis_plan_id=frozen.id,
        coverage_policy_id=run_input.coverage_policy_id,
        state=AnalysisRunState.RUNNING,
        started_at=run_input.started_at,
        completed_at=None,
    )
    ledger_repository.commit_analysis_run_scope(
        analysis_run=run,
        planned_items=planned_items,
    )
    return run


def record_analysis_item_attempt(
    *,
    analysis_run_id: str,
    analysis_unit_id: str,
    model_run_id: str,
    ledger_repository: AnalysisCoverageLedger,
) -> AnalysisItemAttempt:
    """Append a run-specific execution membership link after model work."""
    items = ledger_repository.list_planned_items_for_analysis_run(analysis_run_id)
    item = next(
        (candidate for candidate in items if candidate.analysis_unit_id == analysis_unit_id), None
    )
    if item is None:
        raise ValueError("AnalysisUnit is not in the AnalysisRun scope.")
    model_runs = ledger_repository.list_model_runs_by_ids((model_run_id,))
    if len(model_runs) != 1 or model_runs[0].task_fingerprint != item.input_fingerprint:
        raise ValueError("ModelRun does not match the planned item input fingerprint.")
    tasks = ledger_repository.list_extraction_tasks_by_ids((model_runs[0].extraction_task_id,))
    if len(tasks) != 1 or tasks[0].task_type != item.task_type:
        raise ValueError("ModelRun does not match the planned item task type.")
    if item.expected_manifest_id is not None and (
        tasks[0].context_manifest_id != item.expected_manifest_id
    ):
        raise ValueError("ModelRun does not match the planned item expected manifest.")
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
) -> CoverageReport:
    """Reconcile one immutable run scope without corpus-wide discovery."""
    run = ledger_repository.get_analysis_run(analysis_run_id)
    if run is None:
        raise ValueError(f"AnalysisRun is not persisted: {analysis_run_id}")
    frozen = load_frozen_analysis_plan(run.frozen_analysis_plan_id, ledger_repository)
    if frozen.representation_id != run.representation_id:
        raise ValueError("AnalysisRun frozen plan binding is corrupted.")
    bundle = ledger_repository.get_document_representation_bundle(run.representation_id)
    if bundle is None or bundle.representation.document_id != run.document_id:
        raise ValueError("AnalysisRun representation binding is corrupted.")
    items = ledger_repository.list_planned_items_for_analysis_run(run.id)
    if not items:
        raise ValueError("AnalysisRun has no persisted planned items.")
    if len({item.id for item in items}) != len(items) or any(
        item.analysis_run_id != run.id for item in items
    ):
        raise ValueError("AnalysisRun planned-item scope is corrupted.")
    item_ids = tuple(item.id for item in items)
    attempts_by_item = _attempts_by_item(
        ledger_repository.list_analysis_item_attempts_for_items(item_ids)
    )
    manifest_ids = tuple(
        sorted({item.expected_manifest_id for item in items if item.expected_manifest_id})
    )
    manifest_records = ledger_repository.list_context_manifests_by_ids(manifest_ids)
    requested_manifest_ids = set(manifest_ids)
    manifest_counts = Counter(artifact.id for artifact in manifest_records)
    manifests = {artifact.id: artifact for artifact in manifest_records}
    tasks_by_fingerprint: dict[str, tuple[ExtractionTask, ...]] = {}
    for task in ledger_repository.list_extraction_tasks_for_manifest_ids(manifest_ids):
        tasks_by_fingerprint[task.task_fingerprint] = (
            *tasks_by_fingerprint.get(task.task_fingerprint, ()),
            task,
        )
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
    model_runs = {record.id: record for record in ledger_repository.list_model_runs_by_ids(run_ids)}
    coverage_policy: CoveragePolicy = LatestCompletedValidAttemptCoveragePolicy(model_runs)
    if coverage_policy.policy_id != run.coverage_policy_id:
        raise ValueError("AnalysisRun coverage policy implementation is unavailable.")
    coverages: dict[str, CoverageRecord] = {}
    integrity_failures: set[CoverageIntegrityFailureReason] = set()
    orphan_model_run_ids: set[str] = set()
    if any(artifact.id not in requested_manifest_ids for artifact in manifest_records):
        integrity_failures.add(CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST)
    duplicate_manifest_ids = {
        manifest_id for manifest_id, count in manifest_counts.items() if count > 1
    }
    manifests_by_unit: dict[str, set[str]] = {}
    for item in items:
        if item.expected_manifest_id is not None:
            manifests_by_unit.setdefault(item.analysis_unit_id, set()).add(
                item.expected_manifest_id
            )
    multiple_manifest_item_ids = {
        item.id
        for item in items
        if (
            item.expected_manifest_id in duplicate_manifest_ids
            or len(manifests_by_unit.get(item.analysis_unit_id, set())) > 1
        )
    }

    def reconcile(
        item: PlannedAnalysisItem, visiting: frozenset[str] = frozenset()
    ) -> CoverageRecord:
        if item.id in coverages:
            return coverages[item.id]
        if item.id in visiting:
            integrity_failures.add(CoverageIntegrityFailureReason.SPLIT_CYCLE)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                item.expected_manifest_id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.SPLIT_CYCLE.value,
            )
        if item.id in multiple_manifest_item_ids:
            integrity_failures.add(CoverageIntegrityFailureReason.MULTIPLE_MANIFESTS)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                item.expected_manifest_id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.MULTIPLE_MANIFESTS.value,
            )
        if item.expected_manifest_id is None:
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                None,
                None,
                None,
                (),
                "missing_manifest",
            )
        artifact = manifests.get(item.expected_manifest_id)
        if artifact is None:
            integrity_failures.add(CoverageIntegrityFailureReason.MISSING_MANIFEST)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                item.expected_manifest_id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.MISSING_MANIFEST.value,
            )
        try:
            manifest = load_context_manifest(
                artifact.id,
                ledger_repository,
                verified_bundle=bundle,
            )
        except ValueError:
            integrity_failures.add(CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST.value,
            )
        if manifest.analysis_unit_id != item.analysis_unit_id:
            integrity_failures.add(CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST.value,
            )
        if manifest.representation_id != run.representation_id:
            integrity_failures.add(CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST.value,
            )
        if manifest.manifest_digest != artifact.manifest_digest:
            integrity_failures.add(CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                artifact.id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST.value,
            )
        if manifest.status is ContextManifestStatus.CONTEXT_BUDGET_BLOCKED:
            return _store(
                item,
                CoverageTerminalStatus.CONTEXT_BUDGET_BLOCKED,
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
                    CoverageTerminalStatus.UNREPORTED,
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
            if any(
                child.blocking_reason == CoverageIntegrityFailureReason.SPLIT_CYCLE.value
                for child in children
            ):
                integrity_failures.add(CoverageIntegrityFailureReason.SPLIT_CYCLE)
                return _store(
                    item,
                    CoverageTerminalStatus.UNREPORTED,
                    manifest.id,
                    None,
                    None,
                    (),
                    CoverageIntegrityFailureReason.SPLIT_CYCLE.value,
                    manifest.child_analysis_unit_ids,
                )
            resolved = all(child.terminal_status in _TERMINAL_SUCCESS for child in children)
            return _store(
                item,
                CoverageTerminalStatus.SPLIT_RESOLVED
                if resolved
                else CoverageTerminalStatus.UNREPORTED,
                manifest.id,
                None,
                None,
                (),
                None if resolved else "unresolved_split_child",
                manifest.child_analysis_unit_ids,
            )
        matching_tasks = tasks_by_fingerprint.get(item.input_fingerprint, ())
        if len(matching_tasks) == 0:
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                manifest.id,
                None,
                None,
                (),
                "missing_extraction_task",
            )
        if len(matching_tasks) != 1:
            integrity_failures.add(CoverageIntegrityFailureReason.RUN_TASK_MISMATCH)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                manifest.id,
                None,
                None,
                (),
                CoverageIntegrityFailureReason.RUN_TASK_MISMATCH.value,
            )
        task = matching_tasks[0]
        if (
            task.context_manifest_id != manifest.id
            or task.context_manifest_digest != manifest.manifest_digest
        ):
            integrity_failures.add(CoverageIntegrityFailureReason.RUN_TASK_MISMATCH)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                manifest.id,
                task.id,
                None,
                (),
                CoverageIntegrityFailureReason.RUN_TASK_MISMATCH.value,
            )
        if task.task_type != item.task_type or task.task_fingerprint != item.input_fingerprint:
            integrity_failures.add(CoverageIntegrityFailureReason.RUN_TASK_MISMATCH)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                manifest.id,
                task.id,
                None,
                (),
                CoverageIntegrityFailureReason.RUN_TASK_MISMATCH.value,
            )
        attempts = tuple(
            attempt
            for attempt in attempts_by_item.get(item.id, ())
            if (
                attempt.execution_role == PRIMARY_EXECUTION_ROLE
                and attempt.model_run_id is not None
            )
        )
        valid_attempts: list[AnalysisItemAttempt] = []
        missing_selected_run = False
        run_task_mismatch = False
        for attempt in attempts:
            assert attempt.model_run_id is not None
            linked = model_runs.get(attempt.model_run_id)
            if linked is None:
                missing_selected_run = True
                orphan_model_run_ids.add(attempt.model_run_id)
            elif (
                linked.extraction_task_id != task.id
                or linked.task_fingerprint != item.input_fingerprint
            ):
                run_task_mismatch = True
                orphan_model_run_ids.add(attempt.model_run_id)
            else:
                valid_attempts.append(attempt)
        if missing_selected_run:
            integrity_failures.add(CoverageIntegrityFailureReason.MISSING_SELECTED_RUN)
        if run_task_mismatch:
            integrity_failures.add(CoverageIntegrityFailureReason.RUN_TASK_MISMATCH)
        selected_outcome = coverage_policy.select_current_attempt(item, tuple(valid_attempts))
        if selected_outcome.selected_attempt is None:
            blocking_reason = (
                CoverageIntegrityFailureReason.MISSING_SELECTED_RUN.value
                if missing_selected_run
                else CoverageIntegrityFailureReason.RUN_TASK_MISMATCH.value
                if run_task_mismatch
                else "model_task_has_no_run"
            )
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                manifest.id,
                task.id,
                None,
                (),
                blocking_reason,
                policy_decision=selected_outcome.policy_decision,
            )
        selected_model_run_id = selected_outcome.selected_attempt.model_run_id
        assert selected_model_run_id is not None
        selected = model_runs[selected_model_run_id]
        selected_proposals = ledger_repository.list_proposed_changes_for_model_run(selected.id)
        selected_proposal_ids = tuple(proposal.id for proposal in selected_proposals)
        provenance_ids = tuple(
            sorted(
                {
                    proposal.provenance_activity_id
                    for proposal in selected_proposals
                    if proposal.provenance_activity_id is not None
                }
            )
        )
        provenance_by_id = {
            activity.id: activity
            for activity in ledger_repository.list_provenance_activities_by_ids(provenance_ids)
        }
        proposal_run_mismatch = (
            (bool(selected_proposals) and selected.status is not ModelRunStatus.SUCCEEDED)
            or len(set(selected_proposal_ids)) != len(selected_proposal_ids)
            or any(
                proposal.provenance_activity_id is None
                or proposal.provenance_activity_id not in provenance_by_id
                or selected.id not in provenance_by_id[proposal.provenance_activity_id].input_ids
                for proposal in selected_proposals
            )
        )
        if proposal_run_mismatch:
            integrity_failures.add(CoverageIntegrityFailureReason.PROPOSAL_RUN_MISMATCH)
            return _store(
                item,
                CoverageTerminalStatus.UNREPORTED,
                manifest.id,
                task.id,
                selected.id,
                (),
                CoverageIntegrityFailureReason.PROPOSAL_RUN_MISMATCH.value,
                all_model_run_ids=selected_outcome.all_model_run_ids,
                policy_decision=selected_outcome.policy_decision,
            )
        if selected.status is ModelRunStatus.SUCCEEDED:
            return _store(
                item,
                CoverageTerminalStatus.PROCESSED_WITH_PROPOSALS
                if selected_proposal_ids
                else CoverageTerminalStatus.PROCESSED_NO_PROPOSALS,
                manifest.id,
                task.id,
                selected.id,
                selected_proposal_ids,
                None,
                all_model_run_ids=selected_outcome.all_model_run_ids,
                policy_decision=selected_outcome.policy_decision,
            )
        if selected.status is ModelRunStatus.ABSTAINED:
            return _store(
                item,
                CoverageTerminalStatus.ABSTAINED,
                manifest.id,
                task.id,
                selected.id,
                (),
                None,
                all_model_run_ids=selected_outcome.all_model_run_ids,
                policy_decision=selected_outcome.policy_decision,
                abstention_reason=selected.abstention_reason,
            )
        return _store(
            item,
            CoverageTerminalStatus.MODEL_FAILED,
            manifest.id,
            task.id,
            selected.id,
            (),
            selected.status.value,
            all_model_run_ids=selected_outcome.all_model_run_ids,
            policy_decision=selected_outcome.policy_decision,
        )

    def _store(
        item: PlannedAnalysisItem,
        terminal_status: CoverageTerminalStatus,
        manifest_id: str | None,
        task_id: str | None,
        selected_model_run_id: str | None,
        selected_proposal_ids: tuple[str, ...],
        blocking_reason: str | None,
        child_ids: tuple[str, ...] = (),
        *,
        all_model_run_ids: tuple[str, ...] = (),
        policy_decision: CoveragePolicyDecision = CoveragePolicyDecision.SELECTION_NOT_APPLICABLE,
        abstention_reason: str | None = None,
    ) -> CoverageRecord:
        coverage = CoverageRecord(
            planned_item_id=item.id,
            analysis_unit_id=item.analysis_unit_id,
            terminal_status=terminal_status,
            context_manifest_id=manifest_id,
            extraction_task_id=task_id,
            selected_model_run_id=selected_model_run_id,
            selected_proposal_ids=selected_proposal_ids,
            all_model_run_ids=all_model_run_ids,
            policy_decision=policy_decision,
            blocking_reason=blocking_reason,
            abstention_reason=abstention_reason,
            child_analysis_unit_ids=child_ids,
        )
        coverages[item.id] = coverage
        return coverage

    for item in sorted(items, key=lambda candidate: candidate.id):
        reconcile(item)
    all_coverages = tuple(sorted(coverages.values(), key=lambda coverage: coverage.planned_item_id))
    represented_pages = _represented_pages(bundle, items, ledger_repository)
    preflight_report = ledger_repository.find_latest_complete_pdf_preflight_report_for_task(
        bundle.representation.processing_task_fingerprint_id
    )
    if preflight_report is not None:
        if preflight_report.page_count is None:
            raise ValueError("Complete PDF preflight report requires a page count.")
        total_pages = preflight_report.page_count
    else:
        quality_page_count = bundle.quality_report.metric_values.get("page_count")
        if quality_page_count is None:
            total_pages = len({region.page_number for region in bundle.source_regions})
        elif not isinstance(quality_page_count, int) or isinstance(quality_page_count, bool):
            raise ValueError("Coverage requires an authoritative integer page denominator.")
        else:
            total_pages = quality_page_count
    state = (
        AnalysisCoverageState.FAILED
        if integrity_failures
        else AnalysisCoverageState.COMPLETE
        if all(coverage.terminal_status in _TERMINAL_SUCCESS for coverage in all_coverages)
        and len(represented_pages) == total_pages
        and not orphan_model_run_ids
        else AnalysisCoverageState.INCOMPLETE
    )
    report_payload = {
        "analysis_run_id": run.id,
        "frozen_plan_id": run.frozen_analysis_plan_id,
        "representation_id": run.representation_id,
        "state": state.value,
        "total_pages": total_pages,
        "represented_page_numbers": represented_pages,
        "coverage_policy_id": coverage_policy.policy_id,
        "coverage_records": [_coverage_payload(coverage) for coverage in all_coverages],
        "integrity_failure_reasons": sorted(reason.value for reason in integrity_failures),
        "orphan_model_run_ids": sorted(orphan_model_run_ids),
    }
    return CoverageReport(
        analysis_run_id=run.id,
        frozen_plan_id=run.frozen_analysis_plan_id,
        representation_id=run.representation_id,
        coverage_policy_id=coverage_policy.policy_id,
        state=state,
        total_pages=total_pages,
        represented_page_numbers=represented_pages,
        coverage_records=all_coverages,
        integrity_failure_reasons=tuple(
            sorted(integrity_failures, key=lambda reason: reason.value)
        ),
        orphan_model_run_ids=tuple(sorted(orphan_model_run_ids)),
        report_digest=_digest(report_payload),
    )


_TERMINAL_SUCCESS = frozenset(
    {
        CoverageTerminalStatus.PROCESSED_WITH_PROPOSALS,
        CoverageTerminalStatus.PROCESSED_NO_PROPOSALS,
        CoverageTerminalStatus.ABSTAINED,
        CoverageTerminalStatus.CONTEXT_BUDGET_BLOCKED,
        CoverageTerminalStatus.SPLIT_RESOLVED,
    }
)


def _attempts_by_item(
    records: tuple[AnalysisItemAttempt, ...],
) -> dict[str, tuple[AnalysisItemAttempt, ...]]:
    grouped: dict[str, tuple[AnalysisItemAttempt, ...]] = {}
    for record in records:
        grouped[record.planned_item_id] = (*grouped.get(record.planned_item_id, ()), record)
    return grouped


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


def _coverage_payload(coverage: CoverageRecord) -> dict[str, object]:
    return {
        "planned_item_id": coverage.planned_item_id,
        "analysis_unit_id": coverage.analysis_unit_id,
        "terminal_status": coverage.terminal_status.value,
        "context_manifest_id": coverage.context_manifest_id,
        "extraction_task_id": coverage.extraction_task_id,
        "selected_model_run_id": coverage.selected_model_run_id,
        "selected_proposal_ids": list(coverage.selected_proposal_ids),
        "all_model_run_ids": list(coverage.all_model_run_ids),
        "policy_decision": coverage.policy_decision.value,
        "blocking_reason": coverage.blocking_reason,
        "abstention_reason": coverage.abstention_reason,
        "child_analysis_unit_ids": list(coverage.child_analysis_unit_ids),
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
