"""JSON Schema generation for Domain Core models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from kotekomi_domain.models import (
    Actor,
    ArgumentEdge,
    Assertion,
    Briefing,
    Document,
    Entity,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    Source,
)

type DomainModelType = type[BaseModel]

DOMAIN_SCHEMA_MODELS: dict[str, DomainModelType] = {
    "actor.schema.json": Actor,
    "argument_edge.schema.json": ArgumentEdge,
    "assertion.schema.json": Assertion,
    "briefing.schema.json": Briefing,
    "document.schema.json": Document,
    "entity.schema.json": Entity,
    "event.schema.json": Event,
    "evidence_span.schema.json": EvidenceSpan,
    "organization.schema.json": Organization,
    "outcome.schema.json": Outcome,
    "place.schema.json": Place,
    "provenance_activity.schema.json": ProvenanceActivity,
    "proposed_change.schema.json": ProposedChange,
    "relationship.schema.json": Relationship,
    "source.schema.json": Source,
}


def schema_for(model: DomainModelType) -> dict[str, object]:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema


def write_schemas(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in DOMAIN_SCHEMA_MODELS.items():
        path = output_dir / filename
        path.write_text(json.dumps(schema_for(model), indent=2, sort_keys=True) + "\n")
