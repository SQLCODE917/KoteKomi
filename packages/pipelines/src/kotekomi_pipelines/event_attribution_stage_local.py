"""Deterministic model-free Event attribution submission stage (local).

D5 and D6 of the Event Attribution Production Wiring package. This module is the local
authoring surface that turns one fully pinned, reviewed ``attributed_statement`` wiring unit
into an accepted-state submission:

- ``EventAttributionManifest`` is the strict, explicit data contract for one submission. It
  carries every ``EventAttributionWiringInput`` field plus the fields the reviewed
  attributed-statement submitter needs: ``support_validation_attempt_id``, ``proposer``,
  ``document_id``, ``submitted_at``, ``model_name``, and ``prompt_id``, and one pinned
  ``attributed_to_id`` resolution.
- ``load_event_attribution_manifest`` parses a manifest JSON file through the declared
  contract and fails fast on unknown fields, impossible shape, or invalid identities.
- ``compose_event_attribution_wiring_input`` reconstructs the application-layer
  ``EventAttributionWiringInput`` from a validated manifest.
- ``submit_event_attribution`` runs the deterministic composer and, only for a constructed
  attributed statement, submits the reviewed ``ProposedChange`` and its
  ``ProvenanceActivity`` via the already-shipped reviewed submitter.

The stage never invokes a model and never converts a proposal into accepted state. A held,
no-assertion, or failed composition writes nothing. The pinned resolver fails fast when the
pinned Actor or Organization is absent from the Ledger instead of by passing a dangling id
into the review queue.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, Self

from kotekomi_application import (
    AttributedStatementProposalFailure,
    AttributedStatementProposalLedger,
    EventArgumentTargetDraft,
    EventAttributionWiringInput,
    EventAttributionWiringStatus,
    EventEntityLinguisticEvidence,
    EventSemanticDraft,
    EventTriggerDraft,
    SourceGroundedEventDraft,
    SubmitAttributedStatementProposalInput,
    submit_attributed_statement_proposal,
    wire_event_attribution,
)
from kotekomi_domain import Actor, Organization
from kotekomi_domain.models import (
    ActorId,
    AssertionId,
    DocumentId,
    EntityId,
    EventId,
    EvidenceTargetId,
    EvidenceValidationAttemptId,
    JsonValue,
    OrganizationId,
    PlaceId,
    SourceId,
)
from pydantic import BaseModel, ConfigDict, model_validator

MANIFEST_SCHEMA_VERSION = "event_attribution_submission_v1"

_ContentEntityId = EntityId | ActorId | OrganizationId | EventId | PlaceId


class EventAttributionSubmissionLedger(AttributedStatementProposalLedger, Protocol):
    """The narrow Ledger surface the submission stage needs.

    Extends the reviewed submitter surface with the two identity reads the pinned resolver
    requires, so one pinned ``attributed_to_id`` is validated against the existing Actor or
    Organization before any write.
    """

    def get_actor(self, record_id: str) -> Actor | None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...


class EventAttributionManifest(BaseModel):
    """One strict, explicit Event attribution submission manifest.

    The manifest is the inbound data contract for the stage. Every field that
    ``EventAttributionWiringInput`` requires is present, together with the reviewed
    submitter's fields and one pinned ``attributed_to_id``. The manifest is frozen, rejects
    unknown fields, and validates its own shape before the composer is allowed to run.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["event_attribution_submission_v1"] = MANIFEST_SCHEMA_VERSION
    source_text: str
    event: SourceGroundedEventDraft
    trigger: EventTriggerDraft
    linguistic_evidence: EventEntityLinguisticEvidence
    semantic_draft: EventSemanticDraft
    attribution_target: EventArgumentTargetDraft | None
    attributed_to_id: ActorId | OrganizationId
    subject_entity_id: _ContentEntityId
    object_entity_id: _ContentEntityId | None = None
    object_value: JsonValue = None
    source_id: SourceId
    support_evidence_target_id: EvidenceTargetId
    assertion_id: AssertionId
    evidence_assertion_id: str | None = None
    rationale: str | None = None
    confidence: float | None = None
    support_decision_id: str | None = None
    support_judgment_id: str | None = None
    nli_observation_id: str | None = None
    occurred_at: datetime | None = None
    support_validation_attempt_id: EvidenceValidationAttemptId
    proposer: str
    document_id: DocumentId
    submitted_at: datetime
    model_name: str | None = None
    prompt_id: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (self.object_entity_id is None) == (self.object_value is None):
            raise ValueError(
                "Event attribution manifest requires exactly one of object_entity_id or "
                "object_value."
            )
        if not self.proposer.strip():
            raise ValueError("Event attribution manifest requires a proposer.")
        return self


@dataclass(frozen=True)
class SubmitEventAttributionResult:
    """One bounded result of the Event attribution submission stage."""

    status: str
    wiring_status: EventAttributionWiringStatus
    proposed_change_id: str | None = None
    assertion_id: str | None = None
    provenance_activity_id: str | None = None
    proposal_failure: AttributedStatementProposalFailure | None = None


def load_event_attribution_manifest(path: Path) -> EventAttributionManifest:
    """Load and strictly validate one Event attribution submission manifest file."""
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Event attribution manifest is not readable: {exc}") from exc
    try:
        json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Event attribution manifest is not valid JSON: {exc}") from exc
    return EventAttributionManifest.model_validate_json(payload)


def compose_event_attribution_wiring_input(
    manifest: EventAttributionManifest,
) -> EventAttributionWiringInput:
    """Reconstruct the application-layer wiring input from one validated manifest."""
    return EventAttributionWiringInput(
        source_text=manifest.source_text,
        event=manifest.event,
        trigger=manifest.trigger,
        linguistic_evidence=manifest.linguistic_evidence,
        semantic_draft=manifest.semantic_draft,
        attribution_target=manifest.attribution_target,
        subject_entity_id=manifest.subject_entity_id,
        object_entity_id=manifest.object_entity_id,
        object_value=manifest.object_value,
        source_id=manifest.source_id,
        support_evidence_target_id=manifest.support_evidence_target_id,
        assertion_id=manifest.assertion_id,
        evidence_assertion_id=manifest.evidence_assertion_id,
        rationale=manifest.rationale,
        confidence=manifest.confidence,
        support_decision_id=manifest.support_decision_id,
        support_judgment_id=manifest.support_judgment_id,
        nli_observation_id=manifest.nli_observation_id,
        occurred_at=manifest.occurred_at,
    )


class _PinnedAttributionResolver:
    """Resolve one attribution target to a pinned, Ledger-verified Actor or Organization.

    The resolver fails fast when the pinned id is absent from the Ledger rather than
    returning ``None``, so a dangling pinned resolution can never enter the review queue.
    """

    def __init__(
        self,
        attributed_to_id: ActorId | OrganizationId,
        ledger: EventAttributionSubmissionLedger,
    ) -> None:
        self._attributed_to_id = attributed_to_id
        self._ledger = ledger

    def resolve_attribution_target(
        self, target: EventArgumentTargetDraft
    ) -> ActorId | OrganizationId | None:
        if self._attributed_to_id.startswith("act_"):
            actor = self._ledger.get_actor(self._attributed_to_id)
            if actor is None:
                raise ValueError(
                    f"Pinned attribution Actor is missing from the Ledger: {self._attributed_to_id}"
                )
            return actor.id
        if self._attributed_to_id.startswith("org_"):
            organization = self._ledger.get_organization(self._attributed_to_id)
            if organization is None:
                raise ValueError(
                    "Pinned attribution Organization is missing from the Ledger: "
                    f"{self._attributed_to_id}"
                )
            return organization.id
        raise ValueError("Pinned attribution target must be an Actor or Organization.")


def submit_event_attribution(
    *,
    manifest: EventAttributionManifest,
    ledger: EventAttributionSubmissionLedger,
) -> SubmitEventAttributionResult:
    """Compose and submit one reviewed ``attributed_statement`` proposal.

    A held split, no-assertion, or failed composition writes nothing and reports the wiring
    status. A constructed composition submits the reviewed ``ProposedChange`` and its
    ``ProvenanceActivity`` through the deterministic, idempotent reviewed submitter.
    """
    wiring_input = compose_event_attribution_wiring_input(manifest)
    resolver = _PinnedAttributionResolver(manifest.attributed_to_id, ledger)
    wiring = wire_event_attribution(wiring_input=wiring_input, resolver=resolver)
    if wiring.status is not EventAttributionWiringStatus.CONSTRUCTED:
        return SubmitEventAttributionResult(
            status=wiring.status.value,
            wiring_status=wiring.status,
        )

    assert wiring.attributed_statement is not None
    proposed = wiring.attributed_statement.proposed_assertion
    assert proposed is not None

    proposal = SubmitAttributedStatementProposalInput(
        proposed_assertion=proposed,
        support_evidence_target_id=manifest.support_evidence_target_id,
        support_validation_attempt_id=manifest.support_validation_attempt_id,
        proposer=manifest.proposer,
        document_id=manifest.document_id,
        submitted_at=manifest.submitted_at,
        model_name=manifest.model_name,
        prompt_id=manifest.prompt_id,
    )
    submitted = submit_attributed_statement_proposal(proposal, ledger)
    return SubmitEventAttributionResult(
        status=submitted.status,
        wiring_status=wiring.status,
        proposed_change_id=submitted.proposed_change_id,
        assertion_id=submitted.assertion_id,
        provenance_activity_id=submitted.provenance_activity_id,
        proposal_failure=submitted.failure,
    )
