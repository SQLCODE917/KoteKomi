"""Model proposal validation helpers."""

from __future__ import annotations

import json
from typing import cast

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Relationship,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.ports import ModelProposal


def validate_model_proposal(proposal: ModelProposal) -> ModelProposal:
    record_json = _validated_record_json(proposal.record_type, proposal.record)
    _validate_evidence(proposal.evidence)
    return ModelProposal(
        record_type=proposal.record_type,
        stable_label=proposal.stable_label,
        record=record_json,
        evidence=proposal.evidence,
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
