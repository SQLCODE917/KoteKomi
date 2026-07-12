"""JSON Schema generation for Domain Core models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from kotekomi_domain.models import (
    Actor,
    AnalysisUnitArtifact,
    ArgumentEdge,
    Assertion,
    AssertionEvidenceLink,
    Briefing,
    BuildIdentitySnapshot,
    ContextManifestArtifact,
    Document,
    DocumentEdge,
    DocumentNode,
    DocumentRepresentation,
    DocumentRevisionRelation,
    Entity,
    Event,
    EvidenceReanchoringRelation,
    EvidenceTarget,
    EvidenceValidationAttempt,
    ExtractionTask,
    ModelRun,
    Organization,
    Outcome,
    ParseQualityReport,
    Place,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingTaskFingerprint,
    ProposedChange,
    ProvenanceActivity,
    RawBlob,
    Relationship,
    Source,
    SourceCapture,
    SourceRegion,
    TextView,
)

type DomainModelType = type[BaseModel]

DOMAIN_SCHEMA_MODELS: dict[str, DomainModelType] = {
    "actor.schema.json": Actor,
    "analysis_unit_artifact.schema.json": AnalysisUnitArtifact,
    "argument_edge.schema.json": ArgumentEdge,
    "assertion.schema.json": Assertion,
    "assertion_evidence_link.schema.json": AssertionEvidenceLink,
    "briefing.schema.json": Briefing,
    "build_identity_snapshot.schema.json": BuildIdentitySnapshot,
    "context_manifest_artifact.schema.json": ContextManifestArtifact,
    "document.schema.json": Document,
    "document_edge.schema.json": DocumentEdge,
    "document_node.schema.json": DocumentNode,
    "document_representation.schema.json": DocumentRepresentation,
    "document_revision_relation.schema.json": DocumentRevisionRelation,
    "evidence_reanchoring_relation.schema.json": EvidenceReanchoringRelation,
    "entity.schema.json": Entity,
    "event.schema.json": Event,
    "extraction_task.schema.json": ExtractionTask,
    "evidence_target.schema.json": EvidenceTarget,
    "evidence_validation_attempt.schema.json": EvidenceValidationAttempt,
    "organization.schema.json": Organization,
    "outcome.schema.json": Outcome,
    "model_run.schema.json": ModelRun,
    "place.schema.json": Place,
    "processing_attempt.schema.json": ProcessingAttempt,
    "processing_attempt_outcome.schema.json": ProcessingAttemptOutcome,
    "processing_task_fingerprint.schema.json": ProcessingTaskFingerprint,
    "parse_quality_report.schema.json": ParseQualityReport,
    "provenance_activity.schema.json": ProvenanceActivity,
    "raw_blob.schema.json": RawBlob,
    "proposed_change.schema.json": ProposedChange,
    "relationship.schema.json": Relationship,
    "source.schema.json": Source,
    "source_capture.schema.json": SourceCapture,
    "source_region.schema.json": SourceRegion,
    "text_view.schema.json": TextView,
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
