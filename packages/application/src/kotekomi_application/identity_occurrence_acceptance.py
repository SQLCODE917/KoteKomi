"""Identity-occurrence proposal and acceptance (R20 first increment).

The proposal use case emits a pending ``ProposedChange`` that names one identity
decision and one exact source occurrence. The acceptance use case validates the
identity, the replayable ``EvidenceTarget``, the occurrence association, and a
``ProvenanceActivity`` together, then commits all of them or nothing.

A grounding candidate never becomes an accepted reference directly. A ``nil``,
ineligible, or ambiguous candidate produces a typed hold and no proposal.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from kotekomi_domain import (
    Actor,
    Document,
    DocumentRepresentationBundle,
    EvidenceTarget,
    IdentityOccurrence,
    IdentityOccurrenceKind,
    Organization,
    ProposedChange,
    ProvenanceActivity,
    ReviewStatus,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict

from kotekomi_application.evidence_targets import validate_evidence_target_record

_RECORD_TYPE = "IdentityOccurrence"


class IdentityOccurrenceHoldReason(StrEnum):
    """Typed reason an identity occurrence cannot be proposed."""

    CANDIDATE_NOT_ACCEPTABLE = "candidate_not_acceptable"
    INVALID_EXISTING_IDENTITY = "invalid_existing_identity"
    IDENTITY_KIND_MISMATCH = "identity_kind_mismatch"
    EVIDENCE_UNREPLAYABLE = "evidence_unreplayable"


class IdentityOccurrenceHold(ValueError):
    """One typed hold that blocks an identity-occurrence proposal or acceptance."""

    def __init__(self, reason: IdentityOccurrenceHoldReason, detail: str) -> None:
        super().__init__(f"Identity occurrence hold: {reason.value}: {detail}")
        self.reason = reason


class IdentityOccurrenceAcceptanceLedger(Protocol):
    """The Ledger capabilities the acceptance path reads and writes."""

    def get_actor(self, record_id: str) -> Actor | None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def save_actor(self, record: Actor) -> None: ...
    def save_organization(self, record: Organization) -> None: ...
    def save_evidence_target(self, record: EvidenceTarget) -> None: ...
    def save_identity_occurrence(self, record: IdentityOccurrence) -> None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def save_proposed_change(self, record: ProposedChange) -> None: ...


class GroundingCandidate(BaseModel):
    """One grounding candidate supplied by ingestion for one exact mention span."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_kind: Literal["knowledge_base_entity", "nil"]
    eligible: bool
    ambiguous: bool
    identity_name: str | None = None


class IngestedGroundingCandidate(BaseModel):
    """One review-selectable candidate with its exact paragraph occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: int
    end: int
    exact_text: str
    candidate: GroundingCandidate


def ingested_grounding_candidates(
    *,
    text: str,
    representation_id: str,
    paragraph_node_id: str,
    stage_outputs: Mapping[str, object],
) -> tuple[IngestedGroundingCandidate, ...]:
    """Derive review-selectable candidates from persisted HP-3 output.

    Only candidates HP-3 marked eligible are returned, each bound to its exact
    paragraph occurrence. A candidate is never accepted here; review decides.
    """
    from kotekomi_application.hybrid_entity_grounding import (
        EntityGroundingEligibilityStatus,
        EntityLinkCandidateKind,
        HybridEntityGroundingPreview,
    )
    from kotekomi_application.hybrid_mention_interpretation import hybrid_source_segment_id
    from kotekomi_application.ingestion_inspection import paragraph_segments

    preview = stage_outputs.get("hp3_grounding")
    if preview is None:
        return ()
    if not isinstance(preview, HybridEntityGroundingPreview):
        raise ValueError("Persisted HP-3 output has an unexpected record type.")
    eligible = {
        item.candidate_id
        for item in preview.eligibility
        if item.status is EntityGroundingEligibilityStatus.ELIGIBLE
    }
    segments = {
        hybrid_source_segment_id(representation_id, paragraph_node_id, segment): segment
        for segment in paragraph_segments(text, representation_id, paragraph_node_id)
    }
    candidates: list[IngestedGroundingCandidate] = []
    for link in preview.link_evidence:
        if link.candidate_id not in eligible:
            continue
        segment = segments.get(link.source_segment_id)
        if segment is None:
            raise ValueError("HP-3 link evidence names an unknown SourceSegment.")
        if segment.exact_text[link.start : link.end] != link.text:
            raise ValueError("HP-3 link evidence is not source-exact.")
        top = link.candidates[0] if link.candidates else None
        kind = (
            "knowledge_base_entity"
            if top is not None and top.kind is EntityLinkCandidateKind.KNOWLEDGE_BASE_ENTITY
            else "nil"
        )
        candidates.append(
            IngestedGroundingCandidate(
                start=segment.start_char + link.start,
                end=segment.start_char + link.end,
                exact_text=link.text,
                candidate=GroundingCandidate(
                    candidate_kind=kind,
                    eligible=True,
                    ambiguous=False,
                    identity_name=top.label if top is not None else None,
                ),
            )
        )
    return tuple(candidates)


@dataclass(frozen=True)
class IdentityOccurrenceProposalInput:
    """The reviewed decision that names the identity and its exact occurrence."""

    identity_kind: IdentityOccurrenceKind
    decision: Literal["new_identity", "existing_identity"]
    existing_identity_id: str | None
    identity_name: str | None
    source_id: str
    document_id: str
    representation_id: str
    text_view_id: str
    text_view_digest: str
    start_char: int
    end_char: int
    exact_text: str
    node_id: str
    normalization_policy: str = "utf8_identity_v1"


def _digest(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()


def propose_identity_occurrence(
    candidate: GroundingCandidate,
    proposal: IdentityOccurrenceProposalInput,
    *,
    proposal_id: str,
    now: datetime,
) -> ProposedChange:
    """Propose one identity occurrence as a pending ProposedChange.

    A nil, ineligible, or ambiguous candidate produces a typed hold and no
    proposal. A valid candidate produces a pending proposal only; it writes no
    accepted state.
    """
    if candidate.candidate_kind == "nil" or not candidate.eligible or candidate.ambiguous:
        raise IdentityOccurrenceHold(
            IdentityOccurrenceHoldReason.CANDIDATE_NOT_ACCEPTABLE,
            "The grounding candidate is not a specific, unambiguous identity.",
        )
    if proposal.decision == "new_identity" and not proposal.identity_name:
        raise IdentityOccurrenceHold(
            IdentityOccurrenceHoldReason.CANDIDATE_NOT_ACCEPTABLE,
            "A new identity proposal requires one identity name.",
        )
    if proposal.decision == "existing_identity" and not proposal.existing_identity_id:
        raise IdentityOccurrenceHold(
            IdentityOccurrenceHoldReason.INVALID_EXISTING_IDENTITY,
            "An existing identity proposal requires one identity ID.",
        )
    proposed_json: dict[str, JsonValue] = {
        "record_type": _RECORD_TYPE,
        "identity_kind": proposal.identity_kind.value,
        "decision": proposal.decision,
        "identity_name": proposal.identity_name,
        "existing_identity_id": proposal.existing_identity_id,
        "occurrence": {
            "source_id": proposal.source_id,
            "document_id": proposal.document_id,
            "representation_id": proposal.representation_id,
            "text_view_id": proposal.text_view_id,
            "text_view_digest": proposal.text_view_digest,
            "start_char": proposal.start_char,
            "end_char": proposal.end_char,
            "exact_text": proposal.exact_text,
            "node_id": proposal.node_id,
            "normalization_policy": proposal.normalization_policy,
        },
    }
    return ProposedChange(
        id=proposal_id,
        review_status=ReviewStatus.PENDING,
        proposed_json=proposed_json,
        source_id=proposal.source_id,
        document_id=proposal.document_id,
        created_at=now,
        updated_at=now,
    )


def accept_identity_occurrence(
    proposed_change: ProposedChange,
    repository: IdentityOccurrenceAcceptanceLedger,
    *,
    agent: str,
    now: datetime,
) -> IdentityOccurrence:
    """Accept one pending proposal atomically, or raise a typed hold.

    The acceptance validates the identity, the replayable EvidenceTarget, the
    occurrence association, and the ProvenanceActivity together. A failure raises
    and the caller's Ledger transaction rolls back every write.
    """
    if proposed_change.review_status is not ReviewStatus.PENDING:
        raise IdentityOccurrenceHold(
            IdentityOccurrenceHoldReason.CANDIDATE_NOT_ACCEPTABLE,
            "The proposal is not pending review.",
        )
    proposed = proposed_change.proposed_json
    if proposed.get("record_type") != _RECORD_TYPE:
        raise IdentityOccurrenceHold(
            IdentityOccurrenceHoldReason.CANDIDATE_NOT_ACCEPTABLE,
            "The proposal does not propose an identity occurrence.",
        )
    occurrence_json = proposed["occurrence"]
    if not isinstance(occurrence_json, dict):
        raise IdentityOccurrenceHold(
            IdentityOccurrenceHoldReason.EVIDENCE_UNREPLAYABLE,
            "The proposal occurrence payload is malformed.",
        )
    evidence_target = _build_evidence_target(occurrence_json)
    try:
        validate_evidence_target_record(evidence_target, repository)
    except ValueError as error:
        raise IdentityOccurrenceHold(
            IdentityOccurrenceHoldReason.EVIDENCE_UNREPLAYABLE, str(error)
        ) from error

    identity_id = _resolve_identity(proposed, repository, now)
    occurrence_id = "ioc_" + _digest(identity_id, evidence_target.id)[:24]
    provenance_id = "prv_" + _digest("accept_identity_occurrence", occurrence_id)[:24]
    occurrence = IdentityOccurrence(
        id=occurrence_id,
        identity_id=identity_id,
        identity_kind=IdentityOccurrenceKind(str(proposed["identity_kind"])),
        evidence_target_id=evidence_target.id,
        provenance_activity_id=provenance_id,
        created_at=now,
        updated_at=now,
    )
    provenance = ProvenanceActivity(
        id=provenance_id,
        activity_type="accept_identity_occurrence",
        agent=agent,
        output_ids=(identity_id, evidence_target.id, occurrence_id),
        occurred_at=now,
    )

    repository.save_evidence_target(evidence_target)
    repository.save_provenance_activity(provenance)
    repository.save_identity_occurrence(occurrence)
    repository.save_proposed_change(
        proposed_change.model_copy(
            update={
                "review_status": ReviewStatus.APPROVED,
                "accepted_json": occurrence.model_dump(mode="json"),
                "provenance_activity_id": provenance_id,
                "updated_at": now,
            }
        )
    )
    return occurrence


def _build_evidence_target(occurrence: Mapping[str, JsonValue]) -> EvidenceTarget:
    start_char = int(occurrence["start_char"])  # type: ignore[arg-type]
    end_char = int(occurrence["end_char"])  # type: ignore[arg-type]
    exact_text = str(occurrence["exact_text"])
    payload = json.dumps(
        {
            "source_id": occurrence["source_id"],
            "document_id": occurrence["document_id"],
            "representation_id": occurrence["representation_id"],
            "text_view_id": occurrence["text_view_id"],
            "start_char": start_char,
            "end_char": end_char,
            "exact_text": exact_text,
        },
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return EvidenceTarget(
        id="etg_" + hashlib.sha256(payload.encode()).hexdigest()[:24],
        source_id=str(occurrence["source_id"]),
        document_id=str(occurrence["document_id"]),
        representation_id=str(occurrence["representation_id"]),
        text_view_id=str(occurrence["text_view_id"]),
        text_view_digest=str(occurrence["text_view_digest"]),
        start_char=start_char,
        end_char=end_char,
        exact_text=exact_text,
        normalization_policy=str(occurrence["normalization_policy"]),
        node_ids=(str(occurrence["node_id"]),),
    )


def _resolve_identity(
    proposed: Mapping[str, JsonValue],
    repository: IdentityOccurrenceAcceptanceLedger,
    now: datetime,
) -> str:
    kind = IdentityOccurrenceKind(str(proposed["identity_kind"]))
    decision = str(proposed["decision"])
    if decision == "existing_identity":
        identity_id = str(proposed["existing_identity_id"])
        if kind is IdentityOccurrenceKind.ACTOR:
            if repository.get_actor(identity_id) is None:
                raise IdentityOccurrenceHold(
                    IdentityOccurrenceHoldReason.INVALID_EXISTING_IDENTITY,
                    f"Actor record {identity_id} does not exist.",
                )
        else:
            if repository.get_organization(identity_id) is None:
                raise IdentityOccurrenceHold(
                    IdentityOccurrenceHoldReason.INVALID_EXISTING_IDENTITY,
                    f"Organization record {identity_id} does not exist.",
                )
        return identity_id
    name = str(proposed["identity_name"])
    if kind is IdentityOccurrenceKind.ACTOR:
        identity_id = "act_" + _digest("actor", name)[:24]
        if repository.get_actor(identity_id) is None:
            repository.save_actor(Actor(id=identity_id, name=name, created_at=now, updated_at=now))
        return identity_id
    identity_id = "org_" + _digest("organization", name)[:24]
    if repository.get_organization(identity_id) is None:
        repository.save_organization(
            Organization(id=identity_id, name=name, created_at=now, updated_at=now)
        )
    return identity_id
