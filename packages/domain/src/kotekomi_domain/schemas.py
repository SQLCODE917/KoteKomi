"""JSON Schema generation for Domain Core models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from kotekomi_domain.models import (
    Actor,
    AnalysisItemAttempt,
    AnalysisPlanArtifact,
    AnalysisRun,
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
    DocumentReference,
    DocumentRepresentation,
    DocumentRevisionRelation,
    DocumentSourceSelector,
    DocumentTable,
    DocumentTableAnnotation,
    DocumentTableCell,
    DocumentTableFragment,
    DocumentTableRow,
    Entity,
    Event,
    EvidenceReanchoringRelation,
    EvidenceTarget,
    EvidenceValidationAttempt,
    ExtractionTask,
    ModelRun,
    NewsDeliveryEnvelopeArtifact,
    NewsRepresentationMetadata,
    NewsRevisionClassification,
    NewsRightsProfile,
    Organization,
    Outcome,
    ParseQualityReport,
    PdfPageExtractionStatus,
    PdfPageInventory,
    PdfPreflightReport,
    PdfTransformationArtifact,
    Place,
    PlannedAnalysisItem,
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
    "analysis_plan_artifact.schema.json": AnalysisPlanArtifact,
    "analysis_run.schema.json": AnalysisRun,
    "analysis_item_attempt.schema.json": AnalysisItemAttempt,
    "planned_analysis_item.schema.json": PlannedAnalysisItem,
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
    "document_reference.schema.json": DocumentReference,
    "document_revision_relation.schema.json": DocumentRevisionRelation,
    "document_source_selector.schema.json": DocumentSourceSelector,
    "document_table.schema.json": DocumentTable,
    "document_table_annotation.schema.json": DocumentTableAnnotation,
    "document_table_cell.schema.json": DocumentTableCell,
    "document_table_fragment.schema.json": DocumentTableFragment,
    "document_table_row.schema.json": DocumentTableRow,
    "evidence_reanchoring_relation.schema.json": EvidenceReanchoringRelation,
    "entity.schema.json": Entity,
    "event.schema.json": Event,
    "extraction_task.schema.json": ExtractionTask,
    "evidence_target.schema.json": EvidenceTarget,
    "evidence_validation_attempt.schema.json": EvidenceValidationAttempt,
    "organization.schema.json": Organization,
    "outcome.schema.json": Outcome,
    "model_run.schema.json": ModelRun,
    "news_delivery_envelope_artifact.schema.json": NewsDeliveryEnvelopeArtifact,
    "news_representation_metadata.schema.json": NewsRepresentationMetadata,
    "news_revision_classification.schema.json": NewsRevisionClassification,
    "news_rights_profile.schema.json": NewsRightsProfile,
    "place.schema.json": Place,
    "processing_attempt.schema.json": ProcessingAttempt,
    "processing_attempt_outcome.schema.json": ProcessingAttemptOutcome,
    "processing_task_fingerprint.schema.json": ProcessingTaskFingerprint,
    "parse_quality_report.schema.json": ParseQualityReport,
    "pdf_page_extraction_status.schema.json": PdfPageExtractionStatus,
    "pdf_page_inventory.schema.json": PdfPageInventory,
    "pdf_preflight_report.schema.json": PdfPreflightReport,
    "pdf_transformation_artifact.schema.json": PdfTransformationArtifact,
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
