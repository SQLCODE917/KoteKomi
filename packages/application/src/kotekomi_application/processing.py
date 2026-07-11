"""Authoritative processing identity and append-only execution lifecycle."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    BuildIdentitySnapshot,
    OutputDisposition,
    ProcessingArtifactRef,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingBlocker,
    ProcessingFailure,
    ProcessingTaskFingerprint,
)


class ProcessingTaskDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"


@dataclass(frozen=True)
class BuildIdentity:
    package_version: str
    source_revision: str
    artifact_digest: str
    representation_policy_version: str

    def snapshot(self) -> BuildIdentitySnapshot:
        return BuildIdentitySnapshot(**asdict(self))


class ProcessingAttemptIdFactory(Protocol):
    def new_attempt_id(self) -> str: ...


class Uuid4ProcessingAttemptIdFactory:
    def new_attempt_id(self) -> str:
        return f"pat_{uuid.uuid4().hex}"


class ProcessingLedger(Protocol):
    def ensure_processing_task_fingerprint(
        self, record: ProcessingTaskFingerprint
    ) -> ProcessingTaskDisposition: ...
    def append_processing_attempt(self, record: ProcessingAttempt) -> None: ...
    def append_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None: ...
    def commit_processing_attempt_start(self) -> None: ...
    def record_failed_processing_attempt_outcome(
        self, record: ProcessingAttemptOutcome
    ) -> None: ...
    def get_processing_attempt_outcome(
        self, attempt_id: str
    ) -> ProcessingAttemptOutcome | None: ...
    def list_processing_attempts(
        self, fingerprint_id: str, *, after: str | None = None, limit: int = 100
    ) -> tuple[ProcessingAttempt, ...]: ...


def processing_task_fingerprint(
    *,
    task_kind: str,
    document_id: str,
    blob_id: str,
    input_digest: str,
    processor_name: str,
    processor_version: str,
    processor_config_digest: str,
    build_identity: BuildIdentity,
    policy_id: str,
    output_contract_version: str,
) -> ProcessingTaskFingerprint:
    snapshot = build_identity.snapshot()
    build_identity_digest = _digest(snapshot.model_dump(mode="json"))
    body = {
        "task_kind": task_kind,
        "input_document_id": document_id,
        "input_blob_id": blob_id,
        "input_digest": input_digest,
        "processor_name": processor_name,
        "processor_version": processor_version,
        "processor_config_digest": processor_config_digest,
        "policy_id": policy_id,
        "output_contract_version": output_contract_version,
    }
    fingerprint_digest = _digest({**body, "build_identity_digest": build_identity_digest})
    return ProcessingTaskFingerprint(
        id=f"ptf_{fingerprint_digest[:24]}",
        build_identity=snapshot,
        build_identity_digest=build_identity_digest,
        fingerprint_digest=fingerprint_digest,
        **body,
    )


def start_processing_attempt(
    *,
    task: ProcessingTaskFingerprint,
    ledger: ProcessingLedger,
    attempt_id_factory: ProcessingAttemptIdFactory,
    started_at: datetime,
    invocation_id: str,
    initiator: str | None = None,
) -> ProcessingAttempt:
    ledger.ensure_processing_task_fingerprint(task)
    attempt = ProcessingAttempt(
        id=attempt_id_factory.new_attempt_id(),
        task_fingerprint_id=task.id,
        started_at=started_at,
        invocation_id=invocation_id,
        initiator=initiator,
    )
    ledger.append_processing_attempt(attempt)
    # This is intentionally a narrow commit boundary.  The start must survive
    # a crash or parser failure that occurs before the output transaction.
    ledger.commit_processing_attempt_start()
    return attempt


def processing_attempt_outcome(
    *,
    attempt: ProcessingAttempt,
    status: ProcessingAttemptStatus,
    finished_at: datetime,
    output_artifacts: tuple[ProcessingArtifactRef, ...] = (),
    output_disposition: OutputDisposition | None = None,
    blocking_reasons: tuple[ProcessingBlocker, ...] = (),
    failure: ProcessingFailure | None = None,
    cancellation_reason: str | None = None,
    interruption_basis: str | None = None,
    provenance_activity_id: str | None = None,
) -> ProcessingAttemptOutcome:
    return ProcessingAttemptOutcome(
        id=f"pao_{attempt.id.removeprefix('pat_')}",
        attempt_id=attempt.id,
        status=status,
        finished_at=finished_at,
        output_artifacts=output_artifacts,
        output_disposition=output_disposition,
        blocking_reasons=blocking_reasons,
        failure=failure,
        cancellation_reason=cancellation_reason,
        interruption_basis=interruption_basis,
        provenance_activity_id=provenance_activity_id,
    )


def reconcile_interrupted_processing_attempts(
    *,
    task_fingerprint_id: str,
    ledger: ProcessingLedger,
    reconciled_at: datetime,
    interruption_basis: str,
    limit: int = 100,
) -> tuple[ProcessingAttemptOutcome, ...]:
    """Append interruption outcomes for starts left open by an unclean stop."""
    reconciled: list[ProcessingAttemptOutcome] = []
    for attempt in ledger.list_processing_attempts(task_fingerprint_id, limit=limit):
        if ledger.get_processing_attempt_outcome(attempt.id) is not None:
            continue
        outcome = processing_attempt_outcome(
            attempt=attempt,
            status=ProcessingAttemptStatus.INTERRUPTED,
            finished_at=reconciled_at,
            interruption_basis=interruption_basis,
        )
        ledger.append_processing_attempt_outcome(outcome)
        reconciled.append(outcome)
    return tuple(reconciled)


def _digest(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
