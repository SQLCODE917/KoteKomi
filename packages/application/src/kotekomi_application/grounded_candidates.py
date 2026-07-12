"""Atomic submission of bounded, grounded extraction candidates."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    DocumentNode,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    Organization,
    ProposedChange,
    ProvenanceActivity,
    RepresentationAnalyzability,
    ReviewStatus,
    Source,
    SourceAuthority,
    SourceRegion,
    TextView,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)

from kotekomi_application.evidence_targets import (
    EvidenceTargetLedger,
    validate_evidence_target_record,
)

HASH_ID_LENGTH = 24
GROUNDED_CANDIDATE_BATCH_ACTIVITY = "grounded_candidate_batch_submitted"


class GroundedCandidateLedger(EvidenceTargetLedger, Protocol):
    def get_source(self, record_id: str) -> Source | None: ...
    def commit_grounded_candidate_batch(
        self,
        *,
        evidence_targets: tuple[EvidenceTarget, ...],
        validation_attempts: tuple[EvidenceValidationAttempt, ...],
        provenance_activity: ProvenanceActivity,
        proposed_changes: tuple[ProposedChange, ...],
    ) -> None: ...


class GroundedCandidateContextLedger(EvidenceTargetLedger, Protocol):
    def get_source(self, record_id: str) -> Source | None: ...


@dataclass(frozen=True)
class GroundedCandidateContextInput:
    source_id: str
    document_id: str
    representation_id: str
    node_ids: tuple[str, ...]


@dataclass(frozen=True)
class GroundedCandidateContext:
    id: str
    source_id: str
    document_id: str
    representation_id: str
    representation_digest: str
    text_views: tuple[TextView, ...]
    nodes: tuple[DocumentNode, ...]
    source_regions: tuple[SourceRegion, ...]


@dataclass(frozen=True)
class GroundedOrganizationCandidate:
    local_id: str
    name: str
    organization_type: str | None = None


@dataclass(frozen=True)
class GroundedEvidenceCandidate:
    local_id: str
    text_view_id: str
    start_char: int
    end_char: int
    exact_text: str
    node_ids: tuple[str, ...]
    pdf_region_ids: tuple[str, ...] = ()
    prefix_text: str = ""
    suffix_text: str = ""


@dataclass(frozen=True)
class GroundedAssertionCandidate:
    local_id: str
    subject_organization_local_id: str
    evidence_local_id: str
    predicate: str
    object_value: str
    source_authority: SourceAuthority = SourceAuthority.SECONDARY
    attribution_basis: AttributionBasis = AttributionBasis.REPORTED_BY_SOURCE


@dataclass(frozen=True)
class GroundedCandidateBatchInput:
    task_fingerprint: str
    source_id: str
    document_id: str
    representation_id: str
    model_name: str
    prompt_id: str
    validator_version: str
    submitted_at: datetime
    organizations: tuple[GroundedOrganizationCandidate, ...]
    evidence: tuple[GroundedEvidenceCandidate, ...]
    assertions: tuple[GroundedAssertionCandidate, ...]
    originating_model_run_id: str | None = None


@dataclass(frozen=True)
class ProposedChangeBatchOutcome:
    provenance_activity_id: str
    organization_ids_by_local_id: dict[str, str]
    evidence_target_ids_by_local_id: dict[str, str]
    validation_attempt_ids_by_evidence_local_id: dict[str, str]
    proposed_change_ids_by_local_id: dict[str, str]


@dataclass(frozen=True)
class GroundedCandidateBatchCommit:
    """Validated records awaiting one Application-owned atomic commit."""

    evidence_targets: tuple[EvidenceTarget, ...]
    validation_attempts: tuple[EvidenceValidationAttempt, ...]
    provenance_activity: ProvenanceActivity
    proposed_changes: tuple[ProposedChange, ...]
    outcome: ProposedChangeBatchOutcome


def build_grounded_candidate_context(
    context_input: GroundedCandidateContextInput,
    ledger_repository: GroundedCandidateContextLedger,
) -> GroundedCandidateContext:
    """Build a deterministic, representation-scoped context for one bounded extraction task."""
    if not context_input.node_ids:
        raise ValueError("Grounded candidate context requires at least one DocumentNode.")
    if len(set(context_input.node_ids)) != len(context_input.node_ids):
        raise ValueError("Grounded candidate context DocumentNode selectors must be unique.")
    source = ledger_repository.get_source(context_input.source_id)
    if source is None:
        raise ValueError(
            f"Grounded candidate context references missing Source: {context_input.source_id}"
        )
    document = ledger_repository.get_document(context_input.document_id)
    if document is None or document.source_id != source.id:
        raise ValueError("Grounded candidate context Document does not belong to its Source.")
    bundle = ledger_repository.get_document_representation_bundle(context_input.representation_id)
    if bundle is None or bundle.representation.document_id != document.id:
        raise ValueError(
            "Grounded candidate context references a mismatched DocumentRepresentation."
        )
    if bundle.quality_report.analyzability is not RepresentationAnalyzability.ACCEPTABLE:
        raise ValueError(
            "Grounded candidate context requires an acceptable DocumentRepresentation."
        )
    actual_digest = canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
    )
    if actual_digest != bundle.representation.canonical_output_digest:
        raise ValueError("Grounded candidate context DocumentRepresentation digest is corrupted.")
    nodes_by_id = {node.id: node for node in bundle.nodes}
    selected_nodes: list[DocumentNode] = []
    for node_id in context_input.node_ids:
        node = nodes_by_id.get(node_id)
        if node is None:
            raise ValueError(
                f"Grounded candidate context references missing DocumentNode: {node_id}"
            )
        selected_nodes.append(node)
    selected_nodes.sort(key=lambda node: node.id)
    text_view_ids = {node.text_view_id for node in selected_nodes}
    text_views = tuple(
        sorted(
            (view for view in bundle.text_views if view.id in text_view_ids),
            key=lambda view: view.id,
        )
    )
    selected_region_ids = {
        region_id for node in selected_nodes for region_id in node.source_region_ids
    }
    source_regions = tuple(
        sorted(
            (region for region in bundle.source_regions if region.id in selected_region_ids),
            key=lambda region: region.id,
        )
    )
    return GroundedCandidateContext(
        id=_deterministic_id(
            "ctx",
            source.id,
            document.id,
            bundle.representation.id,
            actual_digest,
            *(node.id for node in selected_nodes),
        ),
        source_id=source.id,
        document_id=document.id,
        representation_id=bundle.representation.id,
        representation_digest=actual_digest,
        text_views=text_views,
        nodes=tuple(selected_nodes),
        source_regions=source_regions,
    )


def prepare_grounded_candidate_batch(
    batch_input: GroundedCandidateBatchInput,
    ledger_repository: GroundedCandidateLedger,
) -> GroundedCandidateBatchCommit:
    """Validate a bounded candidate batch without publishing any downstream records."""
    _require_fingerprint(batch_input.task_fingerprint)
    _require_nonempty(batch_input.model_name, "Grounded candidate batch model_name")
    _require_nonempty(batch_input.prompt_id, "Grounded candidate batch prompt_id")
    _require_nonempty(batch_input.validator_version, "Grounded candidate batch validator_version")
    _require_unique_local_ids(
        (candidate.local_id for candidate in batch_input.organizations), "organization"
    )
    _require_unique_local_ids(
        (candidate.local_id for candidate in batch_input.evidence), "evidence"
    )
    _require_unique_local_ids(
        (candidate.local_id for candidate in batch_input.assertions), "assertion"
    )
    if not batch_input.assertions:
        raise ValueError("Grounded candidate batch requires at least one Assertion candidate.")

    source = ledger_repository.get_source(batch_input.source_id)
    if source is None:
        raise ValueError(
            f"Grounded candidate batch references missing Source: {batch_input.source_id}"
        )
    document = ledger_repository.get_document(batch_input.document_id)
    if document is None or document.source_id != source.id:
        raise ValueError("Grounded candidate batch Document does not belong to its Source.")
    bundle = ledger_repository.get_document_representation_bundle(batch_input.representation_id)
    if bundle is None or bundle.representation.document_id != document.id:
        raise ValueError("Grounded candidate batch references a mismatched DocumentRepresentation.")

    organization_ids = {
        candidate.local_id: _deterministic_id(
            "org",
            batch_input.task_fingerprint,
            "organization",
            candidate.name,
            candidate.organization_type or "",
        )
        for candidate in batch_input.organizations
    }
    evidence_by_local_id: dict[str, EvidenceTarget] = {}
    for candidate in batch_input.evidence:
        text_view = next(
            (view for view in bundle.text_views if view.id == candidate.text_view_id), None
        )
        if text_view is None:
            raise ValueError(
                f"Grounded evidence candidate {candidate.local_id} references a missing TextView."
            )
        evidence = EvidenceTarget(
            id=_deterministic_id(
                "etg",
                batch_input.task_fingerprint,
                "evidence",
                candidate.text_view_id,
                str(candidate.start_char),
                str(candidate.end_char),
                candidate.exact_text,
                candidate.prefix_text,
                candidate.suffix_text,
                *candidate.node_ids,
                *candidate.pdf_region_ids,
            ),
            source_id=source.id,
            document_id=document.id,
            representation_id=bundle.representation.id,
            text_view_id=text_view.id,
            text_view_digest=text_view.content_digest,
            start_char=candidate.start_char,
            end_char=candidate.end_char,
            exact_text=candidate.exact_text,
            normalization_policy=text_view.normalization_policy,
            prefix_text=candidate.prefix_text,
            suffix_text=candidate.suffix_text,
            node_ids=candidate.node_ids,
            pdf_region_ids=candidate.pdf_region_ids,
            created_at=batch_input.submitted_at,
        )
        validate_evidence_target_record(evidence, ledger_repository)
        evidence_by_local_id[candidate.local_id] = evidence
    if len({evidence.id for evidence in evidence_by_local_id.values()}) != len(
        evidence_by_local_id
    ):
        raise ValueError("Grounded candidate batch contains duplicate EvidenceTarget identities.")

    validation_attempts = tuple(
        EvidenceValidationAttempt(
            id=_deterministic_id(
                "eva", batch_input.task_fingerprint, "validation", evidence.id
            ),
            evidence_target_id=evidence.id,
            target_digest=canonical_evidence_target_digest(evidence),
            validator_version=batch_input.validator_version,
            status=EvidenceValidationAttemptStatus.SUCCEEDED,
            attempted_at=batch_input.submitted_at,
        )
        for evidence in evidence_by_local_id.values()
    )
    validation_id_by_evidence_id = {
        attempt.evidence_target_id: attempt.id for attempt in validation_attempts
    }

    provenance_activity = ProvenanceActivity(
        id=_deterministic_id(
            "prv", batch_input.task_fingerprint, GROUNDED_CANDIDATE_BATCH_ACTIVITY
        ),
        activity_type=GROUNDED_CANDIDATE_BATCH_ACTIVITY,
        agent=batch_input.model_name,
        input_ids=(
            source.id,
            document.id,
            bundle.representation.id,
            batch_input.task_fingerprint,
            *(
                (batch_input.originating_model_run_id,)
                if batch_input.originating_model_run_id is not None
                else ()
            ),
        ),
        output_ids=(),
        occurred_at=batch_input.submitted_at,
    )
    organization_changes = tuple(
        _organization_proposed_change(
            batch_input=batch_input,
            candidate=candidate,
            organization_id=organization_ids[candidate.local_id],
            provenance_activity_id=provenance_activity.id,
        )
        for candidate in batch_input.organizations
    )
    assertion_changes = tuple(
        _assertion_proposed_change(
            batch_input=batch_input,
            candidate=candidate,
            organization_ids=organization_ids,
            evidence_by_local_id=evidence_by_local_id,
            validation_id_by_evidence_id=validation_id_by_evidence_id,
            provenance_activity_id=provenance_activity.id,
        )
        for candidate in batch_input.assertions
    )
    proposed_changes = organization_changes + assertion_changes
    provenance_activity = provenance_activity.model_copy(
        update={
            "output_ids": (
                *(target.id for target in evidence_by_local_id.values()),
                *(attempt.id for attempt in validation_attempts),
                *(change.id for change in proposed_changes),
            )
        }
    )
    outcome = ProposedChangeBatchOutcome(
        provenance_activity_id=provenance_activity.id,
        organization_ids_by_local_id=organization_ids,
        evidence_target_ids_by_local_id={
            local_id: target.id for local_id, target in evidence_by_local_id.items()
        },
        validation_attempt_ids_by_evidence_local_id={
            local_id: validation_id_by_evidence_id[target.id]
            for local_id, target in evidence_by_local_id.items()
        },
        proposed_change_ids_by_local_id={
            **{
                candidate.local_id: change.id
                for candidate, change in zip(
                    batch_input.organizations, organization_changes, strict=True
                )
            },
            **{
                candidate.local_id: change.id
                for candidate, change in zip(batch_input.assertions, assertion_changes, strict=True)
            },
        },
    )
    return GroundedCandidateBatchCommit(
        evidence_targets=tuple(evidence_by_local_id.values()),
        validation_attempts=validation_attempts,
        provenance_activity=provenance_activity,
        proposed_changes=proposed_changes,
        outcome=outcome,
    )


def submit_grounded_candidate_batch(
    batch_input: GroundedCandidateBatchInput,
    ledger_repository: GroundedCandidateLedger,
) -> ProposedChangeBatchOutcome:
    """Validate and atomically persist a bounded batch of reviewable candidates."""
    commit = prepare_grounded_candidate_batch(batch_input, ledger_repository)
    ledger_repository.commit_grounded_candidate_batch(
        evidence_targets=commit.evidence_targets,
        validation_attempts=commit.validation_attempts,
        provenance_activity=commit.provenance_activity,
        proposed_changes=commit.proposed_changes,
    )
    return commit.outcome


def _organization_proposed_change(
    *,
    batch_input: GroundedCandidateBatchInput,
    candidate: GroundedOrganizationCandidate,
    organization_id: str,
    provenance_activity_id: str,
) -> ProposedChange:
    organization = Organization(
        id=organization_id,
        name=candidate.name,
        organization_type=candidate.organization_type,
        created_at=batch_input.submitted_at,
        updated_at=batch_input.submitted_at,
    )
    return ProposedChange(
        id=_deterministic_id("pcg", batch_input.task_fingerprint, "organization", organization_id),
        review_status=ReviewStatus.PENDING,
        proposed_json={
            "record_type": "Organization",
            "stable_label": organization_id,
            "record": organization.model_dump(mode="json"),
        },
        source_id=batch_input.source_id,
        document_id=batch_input.document_id,
        model_name=batch_input.model_name,
        prompt_id=batch_input.prompt_id,
        provenance_activity_id=provenance_activity_id,
        created_at=batch_input.submitted_at,
        updated_at=batch_input.submitted_at,
    )


def _assertion_proposed_change(
    *,
    batch_input: GroundedCandidateBatchInput,
    candidate: GroundedAssertionCandidate,
    organization_ids: dict[str, str],
    evidence_by_local_id: dict[str, EvidenceTarget],
    validation_id_by_evidence_id: dict[str, str],
    provenance_activity_id: str,
) -> ProposedChange:
    subject_organization_id = organization_ids.get(candidate.subject_organization_local_id)
    if subject_organization_id is None:
        raise ValueError(
            "Grounded Assertion candidate references an unknown task-local Organization: "
            f"{candidate.subject_organization_local_id}"
        )
    evidence = evidence_by_local_id.get(candidate.evidence_local_id)
    if evidence is None:
        raise ValueError(
            "Grounded Assertion candidate references an unknown task-local EvidenceTarget: "
            f"{candidate.evidence_local_id}"
        )
    assertion_id = _deterministic_id(
        "ast",
        batch_input.task_fingerprint,
        "assertion",
        subject_organization_id,
        candidate.predicate,
        candidate.object_value,
        evidence.id,
    )
    return ProposedChange(
        id=_deterministic_id("pcg", batch_input.task_fingerprint, "assertion", assertion_id),
        review_status=ReviewStatus.PENDING,
        proposed_json={
            "record_type": "Assertion",
            "stable_label": assertion_id,
            "record": {
                "id": assertion_id,
                "assertion_type": AssertionType.SOURCE_CLAIM.value,
                "epistemic_scope": "source_report",
                "subject_entity_id": subject_organization_id,
                "predicate": candidate.predicate,
                "object_value": candidate.object_value,
                "status": AssertionStatus.PROPOSED.value,
                "source_authority": candidate.source_authority.value,
                "attribution_basis": candidate.attribution_basis.value,
                "source_ids": [batch_input.source_id],
                "evidence_target_ids": [evidence.id],
                "provenance_activity_ids": [],
            },
            "evidence_links": [
                {
                    "evidence_target_id": evidence.id,
                    "validation_attempt_id": validation_id_by_evidence_id[evidence.id],
                    "role": "direct_support",
                    "polarity": EvidencePolarity.SUPPORTS.value,
                    "necessity": EvidenceNecessity.REQUIRED.value,
                }
            ],
        },
        source_id=batch_input.source_id,
        document_id=batch_input.document_id,
        model_name=batch_input.model_name,
        prompt_id=batch_input.prompt_id,
        provenance_activity_id=provenance_activity_id,
        created_at=batch_input.submitted_at,
        updated_at=batch_input.submitted_at,
    )


def _require_unique_local_ids(values: Iterable[str], kind: str) -> None:
    local_ids = tuple(values)
    if any(not local_id.strip() for local_id in local_ids):
        raise ValueError(f"Grounded {kind} candidate local_id must be non-empty.")
    if len(set(local_ids)) != len(local_ids):
        raise ValueError(f"Grounded candidate batch has duplicate {kind} local_id values.")


def _require_nonempty(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must be non-empty.")


def _require_fingerprint(value: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("Grounded candidate batch task_fingerprint must be a SHA-256 digest.")


def _deterministic_id(prefix: str, *parts: str) -> str:
    value = "\x1f".join(parts)
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"
