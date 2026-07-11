"""Model proposal boundary DTOs and validation."""

from __future__ import annotations

import json
from typing import Annotated, Literal, cast

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionEvidenceRole,
    Event,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceSpan,
    Organization,
    Outcome,
    Relationship,
)
from kotekomi_domain.models import DocumentId, JsonValue, SourceId
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from kotekomi_application.ports import ModelProposal

StableLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$"),
]
ExactText = Annotated[str, StringConstraints(min_length=1)]


class _ModelBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModelProposalEvidence(_ModelBoundary):
    selector_type: Literal["exact_text"]
    exact_text: ExactText
    source_id: SourceId
    document_id: DocumentId


class ModelProposalEvidenceLink(_ModelBoundary):
    evidence_span_id: str
    role: AssertionEvidenceRole
    polarity: EvidencePolarity
    necessity: EvidenceNecessity


class _ActorProposal(_ModelBoundary):
    record_type: Literal["Actor"]
    stable_label: StableLabel
    record: Actor
    evidence: ModelProposalEvidence


class _OrganizationProposal(_ModelBoundary):
    record_type: Literal["Organization"]
    stable_label: StableLabel
    record: Organization
    evidence: ModelProposalEvidence


class _EventProposal(_ModelBoundary):
    record_type: Literal["Event"]
    stable_label: StableLabel
    record: Event
    evidence: ModelProposalEvidence


class _EvidenceSpanProposal(_ModelBoundary):
    record_type: Literal["EvidenceSpan"]
    stable_label: StableLabel
    record: EvidenceSpan
    evidence: ModelProposalEvidence


class _AssertionProposal(_ModelBoundary):
    record_type: Literal["Assertion"]
    stable_label: StableLabel
    record: Assertion
    evidence: ModelProposalEvidence
    evidence_links: tuple[ModelProposalEvidenceLink, ...] = ()

    @model_validator(mode="after")
    def require_evidence_links_for_source_backed_assertion(self) -> _AssertionProposal:
        if self.record.source_ids and not self.evidence_links:
            raise ValueError("Source-backed Assertion proposals require evidence_links.")
        return self


class _RelationshipProposal(_ModelBoundary):
    record_type: Literal["Relationship"]
    stable_label: StableLabel
    record: Relationship
    evidence: ModelProposalEvidence


class _OutcomeProposal(_ModelBoundary):
    record_type: Literal["Outcome"]
    stable_label: StableLabel
    record: Outcome
    evidence: ModelProposalEvidence


class _ArgumentEdgeProposal(_ModelBoundary):
    record_type: Literal["ArgumentEdge"]
    stable_label: StableLabel
    record: ArgumentEdge
    evidence: ModelProposalEvidence


type ModelProposalWire = Annotated[
    _ActorProposal
    | _OrganizationProposal
    | _EventProposal
    | _EvidenceSpanProposal
    | _AssertionProposal
    | _RelationshipProposal
    | _OutcomeProposal
    | _ArgumentEdgeProposal,
    Field(discriminator="record_type"),
]


class ModelProposalBatch(_ModelBoundary):
    proposals: tuple[ModelProposalWire, ...]


def model_proposal_batch_json_schema() -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], ModelProposalBatch.model_json_schema())


def parse_model_proposal_batch_json(payload: str) -> tuple[ModelProposal, ...]:
    try:
        batch = ModelProposalBatch.model_validate_json(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid model proposal batch: {exc}") from exc
    return tuple(_model_proposal_from_wire(proposal) for proposal in batch.proposals)


def _model_proposal_from_wire(proposal: ModelProposalWire) -> ModelProposal:
    evidence_links: tuple[dict[str, JsonValue], ...] = ()
    if isinstance(proposal, _AssertionProposal):
        evidence_links = tuple(
            cast(dict[str, JsonValue], evidence_link.model_dump(mode="json"))
            for evidence_link in proposal.evidence_links
        )
    return ModelProposal(
        record_type=proposal.record_type,
        stable_label=proposal.stable_label,
        record=cast(dict[str, JsonValue], proposal.record.model_dump(mode="json")),
        evidence=cast(dict[str, JsonValue], proposal.evidence.model_dump(mode="json")),
        evidence_links=evidence_links,
    )


def validate_model_proposal(proposal: ModelProposal) -> ModelProposal:
    record_json = _validated_record_json(proposal.record_type, proposal.record)
    _validate_evidence(proposal.evidence)
    if proposal.record_type != "Assertion" and proposal.evidence_links:
        raise ValueError("Only Assertion proposals may contain evidence_links.")
    if (
        proposal.record_type == "Assertion"
        and record_json.get("source_ids")
        and not proposal.evidence_links
    ):
        raise ValueError("Source-backed Assertion proposals require evidence_links.")
    evidence_links = tuple(
        cast(
            dict[str, JsonValue],
            ModelProposalEvidenceLink.model_validate_json(json.dumps(evidence_link)).model_dump(
                mode="json"
            ),
        )
        for evidence_link in proposal.evidence_links
    )
    return ModelProposal(
        record_type=proposal.record_type,
        stable_label=proposal.stable_label,
        record=record_json,
        evidence=proposal.evidence,
        evidence_links=evidence_links,
    )


def _validated_record_json(
    record_type: str,
    record_json: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    if record_type == "Actor":
        record = Actor.model_validate_json(json.dumps(record_json))
    elif record_type == "Organization":
        record = Organization.model_validate_json(json.dumps(record_json))
    elif record_type == "Event":
        record = Event.model_validate_json(json.dumps(record_json))
    elif record_type == "EvidenceSpan":
        record = EvidenceSpan.model_validate_json(json.dumps(record_json))
    elif record_type == "Assertion":
        record = Assertion.model_validate_json(json.dumps(record_json))
    elif record_type == "Relationship":
        record = Relationship.model_validate_json(json.dumps(record_json))
    elif record_type == "Outcome":
        record = Outcome.model_validate_json(json.dumps(record_json))
    elif record_type == "ArgumentEdge":
        record = ArgumentEdge.model_validate_json(json.dumps(record_json))
    else:
        raise ValueError(f"Unsupported ModelProposal record_type: {record_type}")
    return cast(dict[str, JsonValue], record.model_dump(mode="json"))


def _validate_evidence(evidence: dict[str, JsonValue]) -> None:
    for key in ("source_id", "document_id", "exact_text"):
        value = evidence.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"ModelProposal evidence.{key} must be a non-empty string.")
