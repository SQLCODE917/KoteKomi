"""Deterministic semantic identity for immutable Document representations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    DocumentRepresentationBundle,
    ProcessingAttemptOutcome,
    ProvenanceActivity,
)


class BundleCommitDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"


@dataclass(frozen=True)
class BundleCommitOutcome:
    disposition: BundleCommitDisposition
    representation_id: str


class DocumentRepresentationBundleLedger(Protocol):
    def commit_document_representation_bundle(
        self, bundle: DocumentRepresentationBundle
    ) -> BundleCommitOutcome:
        """Low-level atomic bundle primitive for adapters and repository fixtures.

        Public processing use cases must use
        ``commit_document_representation_processing`` so the bundle is bound
        to the attempt it closes.
        """
        ...

    def commit_document_representation_processing(
        self,
        *,
        expected_task_fingerprint_id: str,
        bundle: DocumentRepresentationBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitOutcome:
        """Atomically close a processing attempt for a representation bundle.

        The bundle and both terminal outcomes must bind to the expected task
        and the same singular attempt.
        A newly produced bundle records its production provenance.  A reused
        bundle records only the new attempt outcome and must not fabricate a
        second production activity for immutable output.
        """
        ...


def deterministic_representation_id(
    task_fingerprint_id: str,
    output_role: str = "canonical_document_representation",
) -> str:
    value = f"{task_fingerprint_id}:{output_role}"
    return f"rep_{hashlib.sha256(value.encode()).hexdigest()[:24]}"
