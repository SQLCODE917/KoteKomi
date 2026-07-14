"""Domain Core models and validation rules."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]

EntityId = Annotated[str, Field(pattern=r"^ent_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ActorId = Annotated[str, Field(pattern=r"^act_[A-Za-z0-9][A-Za-z0-9_-]*$")]
OrganizationId = Annotated[str, Field(pattern=r"^org_[A-Za-z0-9][A-Za-z0-9_-]*$")]
EventId = Annotated[str, Field(pattern=r"^evt_[A-Za-z0-9][A-Za-z0-9_-]*$")]
PlaceId = Annotated[str, Field(pattern=r"^plc_[A-Za-z0-9][A-Za-z0-9_-]*$")]
SourceId = Annotated[str, Field(pattern=r"^src_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentId = Annotated[str, Field(pattern=r"^doc_[A-Za-z0-9][A-Za-z0-9_-]*$")]
EvidenceTargetId = Annotated[str, Field(pattern=r"^etg_[A-Za-z0-9][A-Za-z0-9_-]*$")]
EvidenceValidationAttemptId = Annotated[str, Field(pattern=r"^eva_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ProcessingTaskFingerprintId = Annotated[str, Field(pattern=r"^ptf_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ProcessingAttemptId = Annotated[str, Field(pattern=r"^pat_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ProcessingAttemptOutcomeId = Annotated[str, Field(pattern=r"^pao_[A-Za-z0-9][A-Za-z0-9_-]*$")]
AssertionEvidenceLinkId = Annotated[str, Field(pattern=r"^ael_[A-Za-z0-9][A-Za-z0-9_-]*$")]
EvidenceReanchoringRelationId = Annotated[str, Field(pattern=r"^erl_[A-Za-z0-9][A-Za-z0-9_-]*$")]
AssertionId = Annotated[str, Field(pattern=r"^ast_[A-Za-z0-9][A-Za-z0-9_-]*$")]
RelationshipId = Annotated[str, Field(pattern=r"^rel_[A-Za-z0-9][A-Za-z0-9_-]*$")]
OutcomeId = Annotated[str, Field(pattern=r"^out_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ArgumentEdgeId = Annotated[str, Field(pattern=r"^arg_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ProvenanceActivityId = Annotated[str, Field(pattern=r"^prv_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ProposedChangeId = Annotated[str, Field(pattern=r"^pcg_[A-Za-z0-9][A-Za-z0-9_-]*$")]
BriefingId = Annotated[str, Field(pattern=r"^brf_[A-Za-z0-9][A-Za-z0-9_-]*$")]
RawBlobId = Annotated[str, Field(pattern=r"^blb_[A-Za-z0-9][A-Za-z0-9_-]*$")]
SourceCaptureId = Annotated[str, Field(pattern=r"^cap_[A-Za-z0-9][A-Za-z0-9_-]*$")]
CaptureDocumentResolutionId = Annotated[str, Field(pattern=r"^cdr_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentRevisionRelationId = Annotated[str, Field(pattern=r"^drv_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentRepresentationId = Annotated[str, Field(pattern=r"^rep_[A-Za-z0-9][A-Za-z0-9_-]*$")]
TextViewId = Annotated[str, Field(pattern=r"^tvw_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentNodeId = Annotated[str, Field(pattern=r"^nod_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentEdgeId = Annotated[str, Field(pattern=r"^deg_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ParseQualityReportId = Annotated[str, Field(pattern=r"^pqr_[A-Za-z0-9][A-Za-z0-9_-]*$")]
SourceRegionId = Annotated[str, Field(pattern=r"^srg_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ContextManifestId = Annotated[str, Field(pattern=r"^ctx_[A-Za-z0-9][A-Za-z0-9_-]*$")]
AnalysisUnitId = Annotated[str, Field(pattern=r"^anu_[A-Za-z0-9][A-Za-z0-9_-]*$")]
AnalysisPlanId = Annotated[str, Field(pattern=r"^anp_[A-Za-z0-9][A-Za-z0-9_-]*$")]
AnalysisRunId = Annotated[str, Field(pattern=r"^arn_[A-Za-z0-9][A-Za-z0-9_-]*$")]
PlannedAnalysisItemId = Annotated[str, Field(pattern=r"^pai_[A-Za-z0-9][A-Za-z0-9_-]*$")]
AnalysisItemAttemptId = Annotated[str, Field(pattern=r"^aia_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ExtractionTaskId = Annotated[str, Field(pattern=r"^ext_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ModelRunId = Annotated[str, Field(pattern=r"^mrn_[A-Za-z0-9][A-Za-z0-9_-]*$")]
PdfPreflightReportId = Annotated[str, Field(pattern=r"^pfr_[A-Za-z0-9][A-Za-z0-9_-]*$")]
PdfPageInventoryId = Annotated[str, Field(pattern=r"^ppi_[A-Za-z0-9][A-Za-z0-9_-]*$")]
PdfPageExtractionStatusId = Annotated[str, Field(pattern=r"^pes_[A-Za-z0-9][A-Za-z0-9_-]*$")]
PdfTransformationArtifactId = Annotated[str, Field(pattern=r"^pta_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentTableId = Annotated[str, Field(pattern=r"^tbl_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentTableFragmentId = Annotated[str, Field(pattern=r"^tfr_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentTableRowId = Annotated[str, Field(pattern=r"^trw_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentTableCellId = Annotated[str, Field(pattern=r"^tcl_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentTableAnnotationId = Annotated[str, Field(pattern=r"^tan_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentReferenceId = Annotated[str, Field(pattern=r"^drf_[A-Za-z0-9][A-Za-z0-9_-]*$")]


def utc_now() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    """Base model for immutable Domain Core records."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class EntityKind(StrEnum):
    ACTOR = "actor"
    ORGANIZATION = "organization"
    EVENT = "event"
    PLACE = "place"


class SourceType(StrEnum):
    ARTICLE = "article"
    TRANSCRIPT = "transcript"
    PDF = "pdf"
    BLOG_POST = "blog_post"
    SOCIAL_POST = "social_post"
    FILING = "filing"
    PRESS_RELEASE = "press_release"
    MANUAL_FILE = "manual_file"


class DocumentVersionKind(StrEnum):
    ORIGINAL = "original"
    UPDATE = "update"
    CORRECTION = "correction"
    WITHDRAWAL = "withdrawal"
    UNKNOWN = "unknown"


class DocumentRevisionType(StrEnum):
    UPDATES = "updates"
    CORRECTS = "corrects"
    SUPERSEDES = "supersedes"
    WITHDRAWS = "withdraws"


class TextViewKind(StrEnum):
    LOGICAL = "logical"
    DISPLAY = "display"
    VERBATIM = "verbatim"
    PROVIDER_BODY = "provider_body"


class RepresentationAnalyzability(StrEnum):
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class DocumentEdgeProvenanceKind(StrEnum):
    DETERMINISTIC = "deterministic"
    PARSER = "parser"
    PROPOSED = "proposed"
    REVIEWED = "reviewed"


class SourceCoordinateSystem(StrEnum):
    PDF_POINTS_TOP_LEFT_V1 = "pdf_points_top_left_v1"
    PDF_POINTS_BOTTOM_LEFT_RAW_V1 = "pdf_points_bottom_left_raw_v1"


class PdfExtractionPath(StrEnum):
    EMBEDDED = "embedded"
    OCR = "ocr"
    MIXED = "mixed"
    INACCESSIBLE = "inaccessible"


class PdfPageQualityStatus(StrEnum):
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class PdfPageInventoryDisposition(StrEnum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


class PdfTransformationType(StrEnum):
    REPAIR = "repair"
    RENDER = "render"
    OCR = "ocr"


class TableAnnotationKind(StrEnum):
    CAPTION = "caption"
    UNIT = "unit"
    NOTE = "note"


class DocumentReferenceKind(StrEnum):
    FOOTNOTE = "footnote"
    CROSS_REFERENCE = "cross_reference"


class EvidenceValidationAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProcessingAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class ModelRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    ABSTAINED = "abstained"
    INVALID_OUTPUT = "invalid_output"
    RUNTIME_FAILED = "runtime_failed"
    OUTPUT_ARCHIVE_FAILED = "output_archive_failed"
    PUBLISH_FAILED = "publish_failed"
    CANCELLED = "cancelled"


class ProcessingArtifactKind(StrEnum):
    DOCUMENT_REPRESENTATION = "document_representation"
    TEXT_VIEW = "text_view"
    DOCUMENT_NODE = "document_node"
    DOCUMENT_EDGE = "document_edge"
    SOURCE_REGION = "source_region"
    QUALITY_REPORT = "quality_report"
    PROVENANCE_ACTIVITY = "provenance_activity"
    PDF_PREFLIGHT_REPORT = "pdf_preflight_report"
    PDF_PAGE_INVENTORY = "pdf_page_inventory"
    PDF_PAGE_EXTRACTION_STATUS = "pdf_page_extraction_status"
    PDF_TRANSFORMATION_ARTIFACT = "pdf_transformation_artifact"
    PDF_TRANSFORMATION_BLOB = "pdf_transformation_blob"


class OutputDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"


class ProcessingStage(StrEnum):
    BUILD_IDENTITY = "build_identity"
    ATTEMPT_START = "attempt_start"
    PARSER = "parser"
    ARCHIVE = "archive"
    REPRESENTATION_VALIDATION = "representation_validation"
    PERSISTENCE = "persistence"
    RECONCILIATION = "reconciliation"


class AssertionEvidenceRole(StrEnum):
    DIRECT_SUPPORT = "direct_support"
    ATTRIBUTION = "attribution"
    DEFINITION = "definition"
    SCOPE = "scope"
    TEMPORAL_ANCHOR = "temporal_anchor"
    IDENTITY_RESOLUTION = "identity_resolution"
    CONTRADICTION = "contradiction"
    BACKGROUND = "background"


class EvidencePolarity(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXTUALIZES = "contextualizes"


class EvidenceNecessity(StrEnum):
    REQUIRED = "required"
    SUPPLEMENTARY = "supplementary"


class AssertionType(StrEnum):
    REPORTED_OBSERVATION = "reported_observation"
    SOURCE_CLAIM = "source_claim"
    DIRECT_QUOTE = "direct_quote"
    ANALYTIC_INFERENCE = "analytic_inference"
    CORROBORATION = "corroboration"
    CONTRADICTION = "contradiction"
    OUTCOME_OBSERVATION = "outcome_observation"
    STATUS_UPDATE = "status_update"


class AssertionStatus(StrEnum):
    PROPOSED = "proposed"
    REPORTED = "reported"
    CORROBORATED = "corroborated"
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class EpistemicScope(StrEnum):
    SOURCE_REPORT = "source_report"
    ATTRIBUTED_STATEMENT = "attributed_statement"
    WORLD_STATE = "world_state"
    CAUSAL_EXPLANATION = "causal_explanation"
    ANALYTIC_INFERENCE = "analytic_inference"


class SourceAuthority(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class AttributionBasis(StrEnum):
    DIRECT_DOCUMENT = "direct_document"
    QUOTED_STATEMENT = "quoted_statement"
    REPORTED_BY_SOURCE = "reported_by_source"
    ANONYMOUS_SOURCE = "anonymous_source"
    UNCLEAR = "unclear"
    NOT_APPLICABLE = "not_applicable"


class ArgumentEdgeRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    WEAKENS = "weakens"
    CONTEXTUALIZES = "contextualizes"
    INFERS = "infers"
    CORROBORATES = "corroborates"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


def is_accepted_status(status: AssertionStatus) -> bool:
    return status is not AssertionStatus.PROPOSED


class Entity(DomainModel):
    id: EntityId
    entity_kind: EntityKind
    canonical_name: NonEmptyStr
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Actor(DomainModel):
    id: ActorId
    name: NonEmptyStr
    role_names: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    organization_ids: tuple[OrganizationId, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Organization(DomainModel):
    id: OrganizationId
    name: NonEmptyStr
    organization_type: NonEmptyStr | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Place(DomainModel):
    id: PlaceId
    name: NonEmptyStr
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Event(DomainModel):
    id: EventId
    name: NonEmptyStr
    start_at: datetime | None = None
    end_at: datetime | None = None
    place_id: PlaceId | None = None
    participant_actor_ids: tuple[ActorId, ...] = Field(default_factory=tuple)
    participant_organization_ids: tuple[OrganizationId, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Source(DomainModel):
    id: SourceId
    source_type: SourceType
    identity_policy_id: NonEmptyStr
    canonical_identity_key: NonEmptyStr
    provider_namespace: NonEmptyStr | None = None
    provider_item_id: NonEmptyStr | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RawBlob(DomainModel):
    id: RawBlobId
    hash_algorithm: NonEmptyStr
    digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    byte_length: Annotated[int, Field(ge=0)]
    media_type: NonEmptyStr
    storage_locator: NonEmptyStr
    created_at: datetime = Field(default_factory=utc_now)


class SourceCapture(DomainModel):
    id: SourceCaptureId
    source_id: SourceId
    blob_id: RawBlobId
    idempotency_key: NonEmptyStr
    retrieval_method: NonEmptyStr
    requested_uri: NonEmptyStr | None = None
    canonical_uri: NonEmptyStr | None = None
    request_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    response_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    provider_item_id: NonEmptyStr | None = None
    provider_version: NonEmptyStr | None = None
    rights_profile_id: NonEmptyStr | None = None
    embargo_until: datetime | None = None
    captured_at: datetime = Field(default_factory=utc_now)
    transaction_time: datetime = Field(default_factory=utc_now)


class CaptureDocumentResolution(DomainModel):
    id: CaptureDocumentResolutionId
    capture_id: SourceCaptureId
    document_id: DocumentId
    resolution_policy: NonEmptyStr
    resolution_basis: NonEmptyStr
    created_at: datetime = Field(default_factory=utc_now)


class Document(DomainModel):
    id: DocumentId
    source_id: SourceId
    content_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    provider_version: NonEmptyStr | None = None
    publication_time: datetime | None = None
    provider_update_time: datetime | None = None
    version_kind: DocumentVersionKind = DocumentVersionKind.UNKNOWN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DocumentRevisionRelation(DomainModel):
    id: DocumentRevisionRelationId
    earlier_document_id: DocumentId
    later_document_id: DocumentId
    relation_type: DocumentRevisionType
    basis: NonEmptyStr
    recorded_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_documents(self) -> Self:
        if self.earlier_document_id == self.later_document_id:
            raise ValueError("Document revision relation cannot reference one Document twice.")
        return self


class DocumentRepresentation(DomainModel):
    id: DocumentRepresentationId
    document_id: DocumentId
    parser_name: NonEmptyStr
    parser_version: NonEmptyStr
    parser_config_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    processing_task_fingerprint_id: ProcessingTaskFingerprintId
    input_blob_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    canonical_output_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    created_at: datetime = Field(default_factory=utc_now)


class TextView(DomainModel):
    id: TextViewId
    representation_id: DocumentRepresentationId
    kind: TextViewKind
    content_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    text: str
    normalization_policy: NonEmptyStr

    @model_validator(mode="after")
    def validate_content_digest(self) -> Self:
        actual_digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if self.content_digest != actual_digest:
            raise ValueError("Text view content_digest must match its UTF-8 text.")
        return self


class PdfPreflightReport(DomainModel):
    """Immutable authoritative denominator for one PDF processing task."""

    id: PdfPreflightReportId
    document_id: DocumentId
    raw_blob_id: RawBlobId
    processing_task_fingerprint_id: ProcessingTaskFingerprintId
    processing_attempt_id: ProcessingAttemptId
    pdf_version: NonEmptyStr
    page_inventory_disposition: PdfPageInventoryDisposition
    page_count: Annotated[int, Field(ge=0)] | None
    encrypted: bool
    permissions: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    page_inventory_ids: tuple[PdfPageInventoryId, ...]
    page_extraction_status_ids: tuple[PdfPageExtractionStatusId, ...]
    transformation_artifact_ids: tuple[PdfTransformationArtifactId, ...] = Field(
        default_factory=tuple
    )
    global_issues: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    preflight_tool: NonEmptyStr
    tool_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_page_denominator(self) -> Self:
        if self.page_inventory_disposition is PdfPageInventoryDisposition.UNAVAILABLE:
            if self.page_count is not None:
                raise ValueError("Unavailable PDF page inventory cannot claim a page count.")
            if self.page_inventory_ids or self.page_extraction_status_ids:
                raise ValueError("Unavailable PDF page inventory cannot enumerate page records.")
            if not self.global_issues:
                raise ValueError("Unavailable PDF page inventory requires an explicit issue.")
            return self
        if self.page_count is None:
            raise ValueError("Complete PDF page inventory requires a known page count.")
        if len(self.page_inventory_ids) != self.page_count:
            raise ValueError("PdfPreflightReport must enumerate every page inventory record.")
        if len(self.page_extraction_status_ids) != self.page_count:
            raise ValueError("PdfPreflightReport must enumerate one status for every page.")
        if len(set(self.page_inventory_ids)) != len(self.page_inventory_ids):
            raise ValueError("PdfPreflightReport page inventory IDs must be unique.")
        if len(set(self.page_extraction_status_ids)) != len(self.page_extraction_status_ids):
            raise ValueError("PdfPreflightReport page status IDs must be unique.")
        if len(set(self.transformation_artifact_ids)) != len(self.transformation_artifact_ids):
            raise ValueError("PdfPreflightReport transformation artifact IDs must be unique.")
        return self


class PdfPageInventory(DomainModel):
    id: PdfPageInventoryId
    preflight_report_id: PdfPreflightReportId
    page_index: Annotated[int, Field(ge=1)]
    media_width: Annotated[float, Field(gt=0)]
    media_height: Annotated[float, Field(gt=0)]
    crop_left: Annotated[float, Field(ge=0)]
    crop_top: Annotated[float, Field(ge=0)]
    crop_right: Annotated[float, Field(gt=0)]
    crop_bottom: Annotated[float, Field(gt=0)]
    rotation: Annotated[int, Field(ge=0, le=270, multiple_of=90)]
    embedded_text_character_count: Annotated[int, Field(ge=0)]
    image_coverage: Confidence
    suspicious_glyph_rate: Confidence
    glyph_issue_count: Annotated[int, Field(ge=0)]
    warnings: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        if (
            self.crop_right <= self.crop_left
            or self.crop_bottom <= self.crop_top
            or self.crop_right > self.media_width
            or self.crop_bottom > self.media_height
        ):
            raise ValueError("PdfPageInventory CropBox must lie within its MediaBox.")
        return self


class PdfPageExtractionStatus(DomainModel):
    id: PdfPageExtractionStatusId
    preflight_report_id: PdfPreflightReportId
    page_inventory_id: PdfPageInventoryId
    page_index: Annotated[int, Field(ge=1)]
    extraction_path: PdfExtractionPath
    status: PdfPageQualityStatus
    extracted_character_count: Annotated[int, Field(ge=0)]
    rotation_applied: Annotated[int, Field(ge=0, le=270, multiple_of=90)]
    warnings: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    policy_id: NonEmptyStr
    policy_version: NonEmptyStr
    policy_reasons: tuple[NonEmptyStr, ...]
    ocr_confidence: Confidence | None = None
    transformation_artifact_ids: tuple[PdfTransformationArtifactId, ...] = Field(
        default_factory=tuple
    )

    @model_validator(mode="after")
    def validate_terminal_status(self) -> Self:
        if not self.policy_reasons:
            raise ValueError("PdfPageExtractionStatus requires an explicit policy reason.")
        if self.extraction_path is PdfExtractionPath.INACCESSIBLE:
            if self.status is not PdfPageQualityStatus.BLOCKED:
                raise ValueError("An inaccessible PDF page must be blocked.")
            if self.extracted_character_count != 0:
                raise ValueError("An inaccessible PDF page cannot claim extracted output.")
        if self.extraction_path in {PdfExtractionPath.OCR, PdfExtractionPath.MIXED}:
            if not self.transformation_artifact_ids:
                raise ValueError("An OCR-derived PDF page requires a transformation artifact.")
            if self.ocr_confidence is None:
                raise ValueError("An OCR-derived PDF page requires OCR confidence.")
        if self.extraction_path is PdfExtractionPath.EMBEDDED and (
            self.transformation_artifact_ids
        ):
            raise ValueError("An embedded-only PDF page cannot claim a transformation artifact.")
        if self.extraction_path not in {PdfExtractionPath.OCR, PdfExtractionPath.MIXED} and (
            self.ocr_confidence is not None
        ):
            raise ValueError("A non-OCR PDF page cannot claim OCR confidence.")
        return self


class PdfTransformationArtifact(DomainModel):
    id: PdfTransformationArtifactId
    preflight_report_id: PdfPreflightReportId
    input_blob_id: RawBlobId
    output_blob_id: RawBlobId
    activity_type: PdfTransformationType
    tool_name: NonEmptyStr
    tool_version: NonEmptyStr
    model_name: NonEmptyStr
    model_version: NonEmptyStr
    model_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    configuration_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    page_scope: tuple[Annotated[int, Field(ge=1)], ...]
    language_set: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def validate_page_scope(self) -> Self:
        if self.output_blob_id == self.input_blob_id:
            raise ValueError("A PDF transformation output must differ from its source blob.")
        if len(set(self.page_scope)) != len(self.page_scope):
            raise ValueError("PdfTransformationArtifact requires a unique page scope.")
        if self.activity_type is not PdfTransformationType.REPAIR and not self.page_scope:
            raise ValueError("A page-derived PDF transformation requires a nonempty page scope.")
        if tuple(sorted(self.page_scope)) != self.page_scope:
            raise ValueError("PdfTransformationArtifact page scope must be sorted.")
        if self.activity_type is PdfTransformationType.OCR:
            if len(self.page_scope) != 1:
                raise ValueError("An OCR transformation must account for exactly one PDF page.")
            if not self.language_set:
                raise ValueError("An OCR transformation requires its language set.")
            if self.confidence is None:
                raise ValueError("An OCR transformation requires page confidence.")
        elif self.language_set or self.confidence is not None:
            raise ValueError("A non-OCR transformation cannot claim OCR language or confidence.")
        return self


class PdfPageAccountingBundle(DomainModel):
    """Complete authoritative PDF page accounting, validated as one commit unit."""

    preflight_report: PdfPreflightReport
    page_inventory: tuple[PdfPageInventory, ...]
    page_extraction_statuses: tuple[PdfPageExtractionStatus, ...]
    transformation_artifacts: tuple[PdfTransformationArtifact, ...] = Field(default_factory=tuple)
    transformation_blobs: tuple[RawBlob, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_accounting(self) -> Self:
        report = self.preflight_report
        _require_unique_ids(self.page_inventory, "PdfPageInventory")
        _require_unique_ids(self.page_extraction_statuses, "PdfPageExtractionStatus")
        _require_unique_ids(self.transformation_artifacts, "PdfTransformationArtifact")
        _require_unique_ids(self.transformation_blobs, "PDF transformation RawBlob")
        if tuple(page.id for page in self.page_inventory) != report.page_inventory_ids:
            raise ValueError("PDF page inventory does not match the preflight denominator.")
        if (
            tuple(status.id for status in self.page_extraction_statuses)
            != report.page_extraction_status_ids
        ):
            raise ValueError("PDF page statuses do not match the preflight denominator.")
        if (
            tuple(artifact.id for artifact in self.transformation_artifacts)
            != report.transformation_artifact_ids
        ):
            raise ValueError("PDF transformations do not match the preflight report.")
        expected_page_indices = (
            tuple(range(1, report.page_count + 1)) if report.page_count is not None else ()
        )
        if tuple(page.page_index for page in self.page_inventory) != expected_page_indices:
            raise ValueError("PDF page inventory must be ordered and contiguous from page 1.")
        if (
            tuple(status.page_index for status in self.page_extraction_statuses)
            != expected_page_indices
        ):
            raise ValueError("PDF page statuses must be ordered and contiguous from page 1.")
        inventories_by_id = {page.id: page for page in self.page_inventory}
        transformations_by_id = {
            artifact.id: artifact for artifact in self.transformation_artifacts
        }
        transformation_blobs_by_id = {blob.id: blob for blob in self.transformation_blobs}
        if tuple(artifact.output_blob_id for artifact in self.transformation_artifacts) != tuple(
            blob.id for blob in self.transformation_blobs
        ):
            raise ValueError("PDF transformation blobs must match artifact outputs in order.")
        for page in self.page_inventory:
            if page.preflight_report_id != report.id:
                raise ValueError("PdfPageInventory must belong to its preflight report.")
        for status in self.page_extraction_statuses:
            inventory = inventories_by_id.get(status.page_inventory_id)
            if status.preflight_report_id != report.id or inventory is None:
                raise ValueError("PdfPageExtractionStatus must belong to its page inventory.")
            if inventory.page_index != status.page_index:
                raise ValueError("PDF page status and inventory page index must agree.")
            if inventory.rotation != status.rotation_applied:
                raise ValueError("PDF page status and inventory rotation must agree.")
            for artifact_id in status.transformation_artifact_ids:
                artifact = transformations_by_id.get(artifact_id)
                if artifact is None or status.page_index not in artifact.page_scope:
                    raise ValueError("PDF page status references an unrelated transformation.")
            if status.extraction_path in {
                PdfExtractionPath.OCR,
                PdfExtractionPath.MIXED,
            }:
                ocr_artifacts = tuple(
                    transformations_by_id[artifact_id]
                    for artifact_id in status.transformation_artifact_ids
                    if transformations_by_id[artifact_id].activity_type is PdfTransformationType.OCR
                )
                if len(ocr_artifacts) != 1:
                    raise ValueError(
                        "An OCR-derived PDF page must reference exactly one OCR transformation."
                    )
                if status.ocr_confidence != ocr_artifacts[0].confidence:
                    raise ValueError("PDF page OCR confidence must match its OCR transformation.")
        available_inputs = {report.raw_blob_id}
        for artifact in self.transformation_artifacts:
            if artifact.preflight_report_id != report.id:
                raise ValueError("PdfTransformationArtifact must belong to its preflight report.")
            if artifact.input_blob_id not in available_inputs:
                raise ValueError("PDF transformation input must be archived before its output.")
            if artifact.output_blob_id not in transformation_blobs_by_id:
                raise ValueError("PDF transformation output must be an archived RawBlob.")
            if report.page_count is None and artifact.page_scope:
                raise ValueError(
                    "Unavailable PDF page inventory cannot scope page transformations."
                )
            if report.page_count is not None and any(
                page > report.page_count for page in artifact.page_scope
            ):
                raise ValueError("PDF transformation page scope exceeds the page denominator.")
            available_inputs.add(artifact.output_blob_id)
        return self


class SourceRegion(DomainModel):
    id: SourceRegionId
    representation_id: DocumentRepresentationId
    coordinate_system: SourceCoordinateSystem
    page_number: Annotated[int, Field(ge=1)]
    page_width: Annotated[float, Field(gt=0)]
    page_height: Annotated[float, Field(gt=0)]
    left: Annotated[float, Field(ge=0)]
    top: Annotated[float, Field(ge=0)]
    right: Annotated[float, Field(ge=0)]
    bottom: Annotated[float, Field(ge=0)]
    rotation_applied: Annotated[int, Field(ge=0, le=270, multiple_of=90)]

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("Source region must have positive width and height.")
        if self.right > self.page_width or self.bottom > self.page_height:
            raise ValueError("Source region must lie within its page bounds.")
        return self


class DocumentNode(DomainModel):
    id: DocumentNodeId
    representation_id: DocumentRepresentationId
    parent_node_id: DocumentNodeId | None = None
    node_type: NonEmptyStr
    order_index: Annotated[int, Field(ge=0)]
    structural_path: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    section_path: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    text_view_id: TextViewId
    start_char: Annotated[int, Field(ge=0)]
    end_char: Annotated[int, Field(ge=0)]
    source_region_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    source_page_numbers: tuple[Annotated[int, Field(ge=1)], ...] = Field(default_factory=tuple)
    source_text_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    parser_confidence: Confidence | None = None
    extraction_path: PdfExtractionPath | None = None

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_char < self.start_char:
            raise ValueError("Document node end_char must not precede start_char.")
        if self.end_char == self.start_char and self.node_type != "document":
            raise ValueError("Only an empty document root may have an empty text range.")
        return self


class DocumentEdge(DomainModel):
    id: DocumentEdgeId
    representation_id: DocumentRepresentationId
    from_node_id: DocumentNodeId
    to_node_id: DocumentNodeId
    edge_type: NonEmptyStr
    provenance_kind: DocumentEdgeProvenanceKind
    provenance_id: NonEmptyStr


class DocumentTable(DomainModel):
    """One logical table, potentially assembled from multiple page fragments."""

    id: DocumentTableId
    representation_id: DocumentRepresentationId
    fragment_ids: tuple[DocumentTableFragmentId, ...]
    row_ids: tuple[DocumentTableRowId, ...]
    cell_ids: tuple[DocumentTableCellId, ...]
    annotation_ids: tuple[DocumentTableAnnotationId, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_membership(self) -> Self:
        for label, values in (
            ("fragment", self.fragment_ids),
            ("row", self.row_ids),
            ("cell", self.cell_ids),
            ("annotation", self.annotation_ids),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"DocumentTable {label} IDs must be unique.")
        if not self.fragment_ids or not self.row_ids or not self.cell_ids:
            raise ValueError("DocumentTable requires fragments, rows, and cells.")
        return self


class DocumentTableFragment(DomainModel):
    id: DocumentTableFragmentId
    representation_id: DocumentRepresentationId
    table_id: DocumentTableId
    fragment_index: Annotated[int, Field(ge=0)]
    page_numbers: tuple[Annotated[int, Field(ge=1)], ...]
    source_region_ids: tuple[SourceRegionId, ...]
    continued_from_fragment_id: DocumentTableFragmentId | None = None
    repeated_header_cell_ids: tuple[DocumentTableCellId, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_fragment(self) -> Self:
        if not self.page_numbers or tuple(sorted(set(self.page_numbers))) != self.page_numbers:
            raise ValueError("DocumentTableFragment requires sorted unique pages.")
        if not self.source_region_ids or len(set(self.source_region_ids)) != len(
            self.source_region_ids
        ):
            raise ValueError("DocumentTableFragment requires unique source regions.")
        if len(set(self.repeated_header_cell_ids)) != len(self.repeated_header_cell_ids):
            raise ValueError("Repeated table-header cell IDs must be unique.")
        if self.continued_from_fragment_id == self.id:
            raise ValueError("DocumentTableFragment cannot continue from itself.")
        return self


class DocumentTableRow(DomainModel):
    id: DocumentTableRowId
    representation_id: DocumentRepresentationId
    table_id: DocumentTableId
    fragment_id: DocumentTableFragmentId
    row_index: Annotated[int, Field(ge=0)]
    fragment_row_index: Annotated[int, Field(ge=0)]
    cell_ids: tuple[DocumentTableCellId, ...]

    @model_validator(mode="after")
    def validate_cells(self) -> Self:
        if not self.cell_ids or len(set(self.cell_ids)) != len(self.cell_ids):
            raise ValueError("DocumentTableRow requires unique cells.")
        return self


class DocumentTableCell(DomainModel):
    id: DocumentTableCellId
    representation_id: DocumentRepresentationId
    table_id: DocumentTableId
    fragment_id: DocumentTableFragmentId
    row_id: DocumentTableRowId
    node_id: DocumentNodeId | None = None
    row_index: Annotated[int, Field(ge=0)]
    column_index: Annotated[int, Field(ge=0)]
    row_span: Annotated[int, Field(ge=1)]
    column_span: Annotated[int, Field(ge=1)]
    is_row_header: bool = False
    is_column_header: bool = False
    row_header_cell_ids: tuple[DocumentTableCellId, ...] = Field(default_factory=tuple)
    column_header_cell_ids: tuple[DocumentTableCellId, ...] = Field(default_factory=tuple)
    source_region_ids: tuple[SourceRegionId, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_cell(self) -> Self:
        if self.id in self.row_header_cell_ids or self.id in self.column_header_cell_ids:
            raise ValueError("DocumentTableCell cannot be its own header ancestor.")
        if len(set(self.row_header_cell_ids)) != len(self.row_header_cell_ids) or len(
            set(self.column_header_cell_ids)
        ) != len(self.column_header_cell_ids):
            raise ValueError("DocumentTableCell header ancestry must be unique.")
        if len(set(self.source_region_ids)) != len(self.source_region_ids):
            raise ValueError("DocumentTableCell source regions must be unique.")
        if self.node_id is None and self.source_region_ids:
            raise ValueError("A table cell without text cannot claim text source regions.")
        return self


class DocumentTableAnnotation(DomainModel):
    id: DocumentTableAnnotationId
    representation_id: DocumentRepresentationId
    table_id: DocumentTableId
    fragment_id: DocumentTableFragmentId | None = None
    kind: TableAnnotationKind
    node_id: DocumentNodeId
    source_region_ids: tuple[SourceRegionId, ...]

    @model_validator(mode="after")
    def validate_regions(self) -> Self:
        if not self.source_region_ids or len(set(self.source_region_ids)) != len(
            self.source_region_ids
        ):
            raise ValueError("DocumentTableAnnotation requires unique source regions.")
        return self


class DocumentReference(DomainModel):
    id: DocumentReferenceId
    representation_id: DocumentRepresentationId
    kind: DocumentReferenceKind
    marker_node_id: DocumentNodeId
    target_node_id: DocumentNodeId
    marker_start_char: Annotated[int, Field(ge=0)]
    marker_end_char: Annotated[int, Field(gt=0)]
    marker_text: NonEmptyStr

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.marker_node_id == self.target_node_id:
            raise ValueError("DocumentReference marker and target must differ.")
        if self.marker_end_char <= self.marker_start_char:
            raise ValueError("DocumentReference marker range must be positive.")
        return self


class ParseQualityReport(DomainModel):
    id: ParseQualityReportId
    representation_id: DocumentRepresentationId
    metric_values: dict[str, JsonValue] = Field(default_factory=dict)
    issues: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    analyzability: RepresentationAnalyzability


class DocumentRepresentationBundle(DomainModel):
    """A complete parser output that can be validated without the parser runtime."""

    representation: DocumentRepresentation
    text_views: tuple[TextView, ...]
    nodes: tuple[DocumentNode, ...]
    edges: tuple[DocumentEdge, ...] = Field(default_factory=tuple)
    source_regions: tuple[SourceRegion, ...] = Field(default_factory=tuple)
    tables: tuple[DocumentTable, ...] = Field(default_factory=tuple)
    table_fragments: tuple[DocumentTableFragment, ...] = Field(default_factory=tuple)
    table_rows: tuple[DocumentTableRow, ...] = Field(default_factory=tuple)
    table_cells: tuple[DocumentTableCell, ...] = Field(default_factory=tuple)
    table_annotations: tuple[DocumentTableAnnotation, ...] = Field(default_factory=tuple)
    references: tuple[DocumentReference, ...] = Field(default_factory=tuple)
    quality_report: ParseQualityReport

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        representation_id = self.representation.id
        text_views = {view.id: view for view in self.text_views}
        nodes = {node.id: node for node in self.nodes}
        source_regions = {region.id: region for region in self.source_regions}
        _require_unique_ids(self.text_views, "TextView")
        _require_unique_ids(self.nodes, "DocumentNode")
        _require_unique_ids(self.edges, "DocumentEdge")
        _require_unique_ids(self.source_regions, "SourceRegion")
        _require_unique_ids(self.tables, "DocumentTable")
        _require_unique_ids(self.table_fragments, "DocumentTableFragment")
        _require_unique_ids(self.table_rows, "DocumentTableRow")
        _require_unique_ids(self.table_cells, "DocumentTableCell")
        _require_unique_ids(self.table_annotations, "DocumentTableAnnotation")
        _require_unique_ids(self.references, "DocumentReference")
        if not text_views:
            raise ValueError("Document representation must contain at least one TextView.")
        if len({view.kind for view in self.text_views}) != len(self.text_views):
            raise ValueError("Document representation TextView kinds must be unique.")
        logical_views = tuple(view for view in self.text_views if view.kind is TextViewKind.LOGICAL)
        if len(logical_views) != 1:
            raise ValueError("Document representation must contain exactly one logical TextView.")
        if self.quality_report.representation_id != representation_id:
            raise ValueError("Parse quality report must belong to the representation.")
        for view in self.text_views:
            if view.representation_id != representation_id:
                raise ValueError("TextView must belong to the representation.")
        for region in self.source_regions:
            if region.representation_id != representation_id:
                raise ValueError("SourceRegion must belong to the representation.")
        for node in self.nodes:
            if node.representation_id != representation_id:
                raise ValueError("DocumentNode must belong to the representation.")
            text_view = text_views.get(node.text_view_id)
            if text_view is None:
                raise ValueError("DocumentNode must reference a TextView in its representation.")
            if node.end_char > len(text_view.text):
                raise ValueError("DocumentNode range must lie within its TextView.")
            if node.parent_node_id is not None and node.parent_node_id not in nodes:
                raise ValueError("DocumentNode parent must exist in its representation.")
            if any(region_id not in source_regions for region_id in node.source_region_ids):
                raise ValueError("DocumentNode must reference SourceRegions in its representation.")
            referenced_regions = tuple(
                source_regions[region_id] for region_id in node.source_region_ids
            )
            expected_page_numbers = tuple(
                sorted({region.page_number for region in referenced_regions})
            )
            if node.source_page_numbers != expected_page_numbers:
                raise ValueError("DocumentNode source_page_numbers must match its SourceRegions.")
            expected_text_digest = hashlib.sha256(
                text_view.text[node.start_char : node.end_char].encode("utf-8")
            ).hexdigest()
            if referenced_regions and node.source_text_digest != expected_text_digest:
                raise ValueError("DocumentNode text range must agree with its SourceRegions.")
            if not referenced_regions and node.source_text_digest is not None:
                raise ValueError(
                    "DocumentNode without SourceRegions must not declare a source_text_digest."
                )
            if node.node_type == "furniture" and text_view.kind is TextViewKind.LOGICAL:
                raise ValueError("Furniture DocumentNodes must not enter the logical TextView.")
            region_geometries = {
                (
                    region.page_number,
                    region.left,
                    region.top,
                    region.right,
                    region.bottom,
                )
                for region in referenced_regions
            }
            if len(region_geometries) != len(referenced_regions):
                raise ValueError(
                    "DocumentNode must not reference duplicate contradictory SourceRegions."
                )
        _validate_document_node_tree(tuple(nodes.values()))
        for edge in self.edges:
            if edge.representation_id != representation_id:
                raise ValueError("DocumentEdge must belong to the representation.")
            if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
                raise ValueError("DocumentEdge endpoints must exist in its representation.")
            if edge.from_node_id == edge.to_node_id:
                raise ValueError("DocumentEdge must not be a self-edge.")
        _validate_reading_order_edges(self.edges)
        _validate_document_table_structure(
            representation_id=representation_id,
            text_views=text_views,
            nodes=nodes,
            source_regions=source_regions,
            tables=self.tables,
            fragments=self.table_fragments,
            rows=self.table_rows,
            cells=self.table_cells,
            annotations=self.table_annotations,
            references=self.references,
        )
        actual_digest = canonical_representation_digest(
            self.representation,
            text_views=self.text_views,
            nodes=self.nodes,
            edges=self.edges,
            source_regions=self.source_regions,
            quality_report=self.quality_report,
            tables=self.tables,
            table_fragments=self.table_fragments,
            table_rows=self.table_rows,
            table_cells=self.table_cells,
            table_annotations=self.table_annotations,
            references=self.references,
        )
        if self.representation.canonical_output_digest != actual_digest:
            raise ValueError(
                "Document representation canonical_output_digest does not match output."
            )
        return self


def _require_unique_ids(
    records: tuple[
        TextView
        | DocumentNode
        | DocumentEdge
        | SourceRegion
        | PdfPageInventory
        | PdfPageExtractionStatus
        | PdfTransformationArtifact
        | RawBlob
        | DocumentTable
        | DocumentTableFragment
        | DocumentTableRow
        | DocumentTableCell
        | DocumentTableAnnotation
        | DocumentReference,
        ...,
    ],
    record_name: str,
) -> None:
    if len({record.id for record in records}) != len(records):
        raise ValueError(f"{record_name} IDs must be unique within a representation.")


def _validate_document_node_tree(nodes: tuple[DocumentNode, ...]) -> None:
    nodes_by_id = {node.id: node for node in nodes}
    roots = [node for node in nodes if node.parent_node_id is None]
    if len(roots) != 1:
        raise ValueError("Document representation must contain exactly one root DocumentNode.")
    if roots[0].node_type != "document":
        raise ValueError("Document representation root DocumentNode must have type 'document'.")
    sibling_orders: set[tuple[str | None, int]] = set()
    for node in nodes:
        sibling_order = (node.parent_node_id, node.order_index)
        if sibling_order in sibling_orders:
            raise ValueError("DocumentNode sibling order_index values must be unique.")
        sibling_orders.add(sibling_order)
        ancestor_ids: set[str] = {node.id}
        parent_id = node.parent_node_id
        while parent_id is not None:
            if parent_id in ancestor_ids:
                raise ValueError("DocumentNode parentage must not contain a cycle.")
            ancestor_ids.add(parent_id)
            parent = nodes_by_id.get(parent_id)
            if parent is None:
                raise ValueError("DocumentNode parent_node_id must reference a node in its bundle.")
            parent_id = parent.parent_node_id


def _validate_reading_order_edges(edges: tuple[DocumentEdge, ...]) -> None:
    reading_order_edges = tuple(edge for edge in edges if edge.edge_type == "reading_order")
    successors: dict[str, tuple[str, ...]] = {}
    for edge in reading_order_edges:
        successors[edge.from_node_id] = (
            *successors.get(edge.from_node_id, ()),
            edge.to_node_id,
        )
    state: dict[str, int] = {}
    for start_node_id in successors:
        if state.get(start_node_id) == 2:
            continue
        stack: list[tuple[str, bool]] = [(start_node_id, False)]
        while stack:
            node_id, expanded = stack.pop()
            if expanded:
                state[node_id] = 2
                continue
            node_state = state.get(node_id, 0)
            if node_state == 1:
                raise ValueError("DocumentEdge reading order must not contain a cycle.")
            if node_state == 2:
                continue
            state[node_id] = 1
            stack.append((node_id, True))
            for successor in reversed(successors.get(node_id, ())):
                if state.get(successor) == 1:
                    raise ValueError("DocumentEdge reading order must not contain a cycle.")
                if state.get(successor, 0) == 0:
                    stack.append((successor, False))


def _validate_document_table_structure(
    *,
    representation_id: str,
    text_views: dict[str, TextView],
    nodes: dict[str, DocumentNode],
    source_regions: dict[str, SourceRegion],
    tables: tuple[DocumentTable, ...],
    fragments: tuple[DocumentTableFragment, ...],
    rows: tuple[DocumentTableRow, ...],
    cells: tuple[DocumentTableCell, ...],
    annotations: tuple[DocumentTableAnnotation, ...],
    references: tuple[DocumentReference, ...],
) -> None:
    tables_by_id = {table.id: table for table in tables}
    fragments_by_id = {fragment.id: fragment for fragment in fragments}
    rows_by_id = {row.id: row for row in rows}
    cells_by_id = {cell.id: cell for cell in cells}
    annotations_by_id = {annotation.id: annotation for annotation in annotations}
    for table in tables:
        if table.representation_id != representation_id:
            raise ValueError("DocumentTable must belong to its representation.")
        table_fragments = tuple(fragments_by_id.get(record_id) for record_id in table.fragment_ids)
        table_rows = tuple(rows_by_id.get(record_id) for record_id in table.row_ids)
        table_cells = tuple(cells_by_id.get(record_id) for record_id in table.cell_ids)
        table_annotations = tuple(
            annotations_by_id.get(record_id) for record_id in table.annotation_ids
        )
        if any(record is None for record in table_fragments):
            raise ValueError("DocumentTable references a missing fragment.")
        if any(record is None for record in table_rows):
            raise ValueError("DocumentTable references a missing row.")
        if any(record is None for record in table_cells):
            raise ValueError("DocumentTable references a missing cell.")
        if any(record is None for record in table_annotations):
            raise ValueError("DocumentTable references a missing annotation.")
        prior_fragment_id: str | None = None
        for index, fragment in enumerate(table_fragments):
            assert fragment is not None
            if (
                fragment.representation_id != representation_id
                or fragment.table_id != table.id
                or fragment.fragment_index != index
                or fragment.continued_from_fragment_id != prior_fragment_id
            ):
                raise ValueError("DocumentTable fragment continuation chain is invalid.")
            if any(region_id not in source_regions for region_id in fragment.source_region_ids):
                raise ValueError("DocumentTableFragment references a missing SourceRegion.")
            prior_fragment_id = fragment.id
        for row in table_rows:
            assert row is not None
            if (
                row.representation_id != representation_id
                or row.table_id != table.id
                or row.fragment_id not in table.fragment_ids
            ):
                raise ValueError("DocumentTableRow belongs to an unrelated table fragment.")
            if (
                tuple(cell.id for cell in table_cells if cell is not None and cell.row_id == row.id)
                != row.cell_ids
            ):
                raise ValueError("DocumentTableRow cell membership is not canonical.")
        occupied: set[tuple[int, int]] = set()
        for cell in table_cells:
            assert cell is not None
            if (
                cell.representation_id != representation_id
                or cell.table_id != table.id
                or cell.fragment_id not in table.fragment_ids
                or cell.row_id not in table.row_ids
            ):
                raise ValueError("DocumentTableCell belongs to an unrelated table row.")
            for coordinate in (
                (row, column)
                for row in range(cell.row_index, cell.row_index + cell.row_span)
                for column in range(cell.column_index, cell.column_index + cell.column_span)
            ):
                if coordinate in occupied:
                    raise ValueError("DocumentTableCell spans overlap.")
                occupied.add(coordinate)
            if cell.node_id is not None:
                node = nodes.get(cell.node_id)
                if node is None or node.node_type not in {
                    "table_cell",
                    "table_row_header",
                    "table_column_header",
                    "table_corner_header",
                }:
                    raise ValueError("DocumentTableCell requires a canonical table-cell node.")
                if cell.source_region_ids != node.source_region_ids:
                    raise ValueError("DocumentTableCell regions must match its text node.")
            for header_id in cell.row_header_cell_ids:
                header = cells_by_id.get(header_id)
                if header is None or header.table_id != table.id or not header.is_row_header:
                    raise ValueError("DocumentTableCell row-header ancestry is invalid.")
            for header_id in cell.column_header_cell_ids:
                header = cells_by_id.get(header_id)
                if header is None or header.table_id != table.id or not header.is_column_header:
                    raise ValueError("DocumentTableCell column-header ancestry is invalid.")
        for fragment in table_fragments:
            assert fragment is not None
            for header_id in fragment.repeated_header_cell_ids:
                header = cells_by_id.get(header_id)
                if header is None or not (header.is_row_header or header.is_column_header):
                    raise ValueError("DocumentTableFragment repeated header is invalid.")
        for annotation in table_annotations:
            assert annotation is not None
            node = nodes.get(annotation.node_id)
            if (
                annotation.representation_id != representation_id
                or annotation.table_id != table.id
                or (
                    annotation.fragment_id is not None
                    and annotation.fragment_id not in table.fragment_ids
                )
                or node is None
                or annotation.source_region_ids != node.source_region_ids
            ):
                raise ValueError("DocumentTableAnnotation is not grounded in its table.")
    if set(fragment.table_id for fragment in fragments) - set(tables_by_id):
        raise ValueError("Orphan DocumentTableFragment is forbidden.")
    if set(row.table_id for row in rows) - set(tables_by_id):
        raise ValueError("Orphan DocumentTableRow is forbidden.")
    if set(cell.table_id for cell in cells) - set(tables_by_id):
        raise ValueError("Orphan DocumentTableCell is forbidden.")
    if set(annotation.table_id for annotation in annotations) - set(tables_by_id):
        raise ValueError("Orphan DocumentTableAnnotation is forbidden.")
    for reference in references:
        marker = nodes.get(reference.marker_node_id)
        target = nodes.get(reference.target_node_id)
        if reference.representation_id != representation_id or marker is None or target is None:
            raise ValueError("DocumentReference endpoints must belong to its representation.")
        if marker.text_view_id not in text_views:
            raise ValueError("DocumentReference marker TextView is missing.")
        if (
            reference.marker_start_char < marker.start_char
            or reference.marker_end_char > marker.end_char
        ):
            raise ValueError("DocumentReference marker range lies outside its marker node.")
        marker_view = text_views[marker.text_view_id]
        if (
            marker_view.text[reference.marker_start_char : reference.marker_end_char]
            != reference.marker_text
        ):
            raise ValueError("DocumentReference marker text does not match its TextView.")
        if reference.kind is DocumentReferenceKind.FOOTNOTE and target.node_type not in {
            "footnote",
            "table_note",
        }:
            raise ValueError("Footnote DocumentReference requires a footnote target.")


def canonical_representation_digest(
    representation: DocumentRepresentation,
    *,
    text_views: tuple[TextView, ...],
    nodes: tuple[DocumentNode, ...],
    edges: tuple[DocumentEdge, ...],
    source_regions: tuple[SourceRegion, ...],
    quality_report: ParseQualityReport,
    tables: tuple[DocumentTable, ...] = (),
    table_fragments: tuple[DocumentTableFragment, ...] = (),
    table_rows: tuple[DocumentTableRow, ...] = (),
    table_cells: tuple[DocumentTableCell, ...] = (),
    table_annotations: tuple[DocumentTableAnnotation, ...] = (),
    references: tuple[DocumentReference, ...] = (),
) -> str:
    """Return the SHA-256 digest of a stable representation serialization."""

    representation_payload = _canonical_record_payload(representation)
    representation_payload.pop("canonical_output_digest")
    representation_payload.pop("created_at")
    payload = {
        "representation": representation_payload,
        "text_views": [
            _canonical_record_payload(view) for view in sorted(text_views, key=lambda view: view.id)
        ],
        "nodes": [
            _canonical_record_payload(node) for node in sorted(nodes, key=lambda node: node.id)
        ],
        "edges": [
            _canonical_record_payload(edge) for edge in sorted(edges, key=lambda edge: edge.id)
        ],
        "source_regions": [
            _canonical_record_payload(region)
            for region in sorted(source_regions, key=lambda region: region.id)
        ],
        "tables": [
            _canonical_record_payload(table) for table in sorted(tables, key=lambda x: x.id)
        ],
        "table_fragments": [
            _canonical_record_payload(fragment)
            for fragment in sorted(table_fragments, key=lambda x: x.id)
        ],
        "table_rows": [
            _canonical_record_payload(row) for row in sorted(table_rows, key=lambda x: x.id)
        ],
        "table_cells": [
            _canonical_record_payload(cell) for cell in sorted(table_cells, key=lambda x: x.id)
        ],
        "table_annotations": [
            _canonical_record_payload(annotation)
            for annotation in sorted(table_annotations, key=lambda x: x.id)
        ],
        "references": [
            _canonical_record_payload(reference)
            for reference in sorted(references, key=lambda x: x.id)
        ],
        "quality_report": _canonical_record_payload(quality_report),
    }
    canonical_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _canonical_record_payload(record: DomainModel) -> dict[str, object]:
    """Map one flat authority record without Pydantic's recursive serializer."""

    return {field_name: getattr(record, field_name) for field_name in type(record).model_fields}


class TableEvidenceSelector(DomainModel):
    table_id: DocumentTableId
    cell_id: DocumentTableCellId
    row_header_cell_ids: tuple[DocumentTableCellId, ...]
    column_header_cell_ids: tuple[DocumentTableCellId, ...]

    @model_validator(mode="after")
    def validate_header_ancestry(self) -> Self:
        if not self.row_header_cell_ids or not self.column_header_cell_ids:
            raise ValueError("TableEvidenceSelector requires row and column header ancestry.")
        if len(set(self.row_header_cell_ids)) != len(self.row_header_cell_ids) or len(
            set(self.column_header_cell_ids)
        ) != len(self.column_header_cell_ids):
            raise ValueError("TableEvidenceSelector header ancestry must be unique.")
        return self


class EvidenceTarget(DomainModel):
    id: EvidenceTargetId
    source_id: SourceId
    document_id: DocumentId
    representation_id: DocumentRepresentationId
    text_view_id: TextViewId
    text_view_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    start_char: Annotated[int, Field(ge=0)]
    end_char: Annotated[int, Field(gt=0)]
    exact_text: NonEmptyStr
    normalization_policy: NonEmptyStr
    prefix_text: str = ""
    suffix_text: str = ""
    node_ids: tuple[DocumentNodeId, ...] = Field(default_factory=tuple)
    pdf_region_ids: tuple[SourceRegionId, ...] = Field(default_factory=tuple)
    dom_selector: dict[str, JsonValue] | None = None
    table_selector: TableEvidenceSelector | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_target_shape(self) -> Self:
        if self.end_char <= self.start_char:
            raise ValueError("EvidenceTarget end_char must follow start_char.")
        if not (
            self.node_ids
            or self.pdf_region_ids
            or self.dom_selector is not None
            or self.table_selector is not None
        ):
            raise ValueError("EvidenceTarget requires a structural or occurrence selector.")
        return self


class EvidenceValidationAttempt(DomainModel):
    id: EvidenceValidationAttemptId
    evidence_target_id: EvidenceTargetId
    target_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    validator_version: NonEmptyStr
    status: EvidenceValidationAttemptStatus
    error_message: str | None = None
    attempted_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        if (
            self.status is EvidenceValidationAttemptStatus.SUCCEEDED
            and self.error_message is not None
        ):
            raise ValueError("Successful EvidenceValidationAttempt cannot have an error_message.")
        if self.status is EvidenceValidationAttemptStatus.FAILED and not self.error_message:
            raise ValueError("Failed EvidenceValidationAttempt requires an error_message.")
        return self


class ProcessingTaskFingerprint(DomainModel):
    id: ProcessingTaskFingerprintId
    task_kind: NonEmptyStr
    input_document_id: DocumentId
    input_blob_id: RawBlobId
    input_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    processor_name: NonEmptyStr
    processor_version: NonEmptyStr
    processor_config_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    build_identity: BuildIdentitySnapshot
    build_identity_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    policy_id: NonEmptyStr
    output_contract_version: NonEmptyStr
    fingerprint_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ProcessingAttempt(DomainModel):
    id: ProcessingAttemptId
    task_fingerprint_id: ProcessingTaskFingerprintId
    started_at: datetime
    invocation_id: NonEmptyStr
    initiator: NonEmptyStr | None = None


class BuildIdentitySnapshot(DomainModel):
    package_version: NonEmptyStr
    source_revision: NonEmptyStr
    artifact_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    representation_policy_version: NonEmptyStr


class ProcessingArtifactRef(DomainModel):
    kind: ProcessingArtifactKind
    artifact_id: NonEmptyStr
    role: NonEmptyStr
    digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None


class ProcessingBlocker(DomainModel):
    code: NonEmptyStr
    stage: ProcessingStage
    safe_message: NonEmptyStr


class ProcessingFailure(DomainModel):
    code: NonEmptyStr
    failure_type: NonEmptyStr
    stage: ProcessingStage
    safe_message: NonEmptyStr
    retryable: bool
    diagnostic_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None


class ProcessingAttemptOutcome(DomainModel):
    id: ProcessingAttemptOutcomeId
    attempt_id: ProcessingAttemptId
    status: ProcessingAttemptStatus
    finished_at: datetime
    output_artifacts: tuple[ProcessingArtifactRef, ...] = Field(default_factory=tuple)
    output_disposition: OutputDisposition | None = None
    blocking_reasons: tuple[ProcessingBlocker, ...] = Field(default_factory=tuple)
    failure: ProcessingFailure | None = None
    cancellation_reason: NonEmptyStr | None = None
    interruption_basis: NonEmptyStr | None = None
    provenance_activity_id: ProvenanceActivityId | None = None

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        if self.status is ProcessingAttemptStatus.SUCCEEDED:
            if not self.output_artifacts or self.output_disposition is None:
                raise ValueError(
                    "Successful ProcessingAttemptOutcome requires outputs and disposition."
                )
            if (
                self.blocking_reasons
                or self.failure is not None
                or self.cancellation_reason is not None
                or self.interruption_basis is not None
            ):
                raise ValueError(
                    "Successful ProcessingAttemptOutcome cannot include terminal errors."
                )
        elif self.status is ProcessingAttemptStatus.BLOCKED:
            if not self.blocking_reasons:
                raise ValueError("Blocked ProcessingAttemptOutcome requires blockers.")
            if (
                self.output_disposition is not None
                or self.failure is not None
                or self.cancellation_reason is not None
                or self.interruption_basis is not None
            ):
                raise ValueError(
                    "Blocked ProcessingAttemptOutcome cannot include another terminal state."
                )
        elif self.status is ProcessingAttemptStatus.FAILED:
            if self.failure is None:
                raise ValueError("Failed ProcessingAttemptOutcome requires failure details.")
            if (
                self.output_disposition is not None
                or self.blocking_reasons
                or self.cancellation_reason is not None
                or self.interruption_basis is not None
            ):
                raise ValueError(
                    "Failed ProcessingAttemptOutcome cannot include another terminal state."
                )
        elif self.status is ProcessingAttemptStatus.CANCELLED:
            if self.cancellation_reason is None:
                raise ValueError("Cancelled ProcessingAttemptOutcome requires cancellation reason.")
            if (
                self.output_artifacts
                or self.output_disposition is not None
                or self.blocking_reasons
                or self.failure is not None
                or self.interruption_basis is not None
            ):
                raise ValueError(
                    "Cancelled ProcessingAttemptOutcome cannot include another terminal state."
                )
        elif self.status is ProcessingAttemptStatus.INTERRUPTED:
            if self.interruption_basis is None:
                raise ValueError(
                    "Interrupted ProcessingAttemptOutcome requires reconciliation basis."
                )
            if (
                self.output_artifacts
                or self.output_disposition is not None
                or self.blocking_reasons
                or self.failure is not None
                or self.cancellation_reason is not None
            ):
                raise ValueError(
                    "Interrupted ProcessingAttemptOutcome cannot include another terminal state."
                )
        return self


class AssertionEvidenceLink(DomainModel):
    id: AssertionEvidenceLinkId
    assertion_id: AssertionId
    evidence_target_id: EvidenceTargetId
    validation_attempt_id: EvidenceValidationAttemptId
    role: AssertionEvidenceRole
    polarity: EvidencePolarity
    necessity: EvidenceNecessity
    provenance_id: ProvenanceActivityId
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceReanchoringRelation(DomainModel):
    id: EvidenceReanchoringRelationId
    earlier_evidence_target_id: EvidenceTargetId
    later_evidence_target_id: EvidenceTargetId
    provenance_id: ProvenanceActivityId
    basis: NonEmptyStr
    recorded_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_evidence_targets(self) -> Self:
        if self.earlier_evidence_target_id == self.later_evidence_target_id:
            raise ValueError(
                "Evidence reanchoring relation cannot reference one EvidenceTarget twice."
            )
        return self


def canonical_evidence_target_digest(evidence_target: EvidenceTarget) -> str:
    """Return the SHA-256 digest of immutable, replayable evidence selectors."""

    payload = evidence_target.model_dump(mode="json")
    for field_name in ("created_at",):
        payload.pop(field_name)
    canonical_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class Assertion(DomainModel):
    id: AssertionId
    assertion_type: AssertionType
    epistemic_scope: EpistemicScope
    subject_entity_id: EntityId | ActorId | OrganizationId | EventId | PlaceId
    predicate: NonEmptyStr
    object_entity_id: EntityId | ActorId | OrganizationId | EventId | PlaceId | None = None
    object_value: JsonValue = None
    status: AssertionStatus
    source_authority: SourceAuthority
    attribution_basis: AttributionBasis
    attributed_to_id: ActorId | OrganizationId | None = None
    source_report_confidence: Confidence | None = None
    extraction_confidence: Confidence | None = None
    world_truth_confidence: Confidence | None = None
    causal_confidence: Confidence | None = None
    qualifiers: dict[str, JsonValue] = Field(default_factory=dict)
    current_assessment: str = ""
    source_ids: tuple[SourceId, ...] = Field(default_factory=tuple)
    evidence_target_ids: tuple[EvidenceTargetId, ...] = Field(default_factory=tuple)
    authority_source_ids: tuple[SourceId, ...] = Field(default_factory=tuple)
    authority_evidence_target_ids: tuple[EvidenceTargetId, ...] = Field(default_factory=tuple)
    provenance_activity_ids: tuple[ProvenanceActivityId, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_assertion_rules(self) -> Self:
        has_object_entity = self.object_entity_id is not None
        has_object_value = self.object_value is not None
        if has_object_entity == has_object_value:
            raise ValueError("Assertion must have exactly one object entity or object value.")

        if is_accepted_status(self.status) and not self.provenance_activity_ids:
            raise ValueError("Accepted Assertion must reference a ProvenanceActivity.")

        if is_accepted_status(self.status) and self.source_ids and not self.evidence_target_ids:
            raise ValueError("Accepted Source-backed Assertion must reference an EvidenceTarget.")

        if (
            self.assertion_type is AssertionType.ANALYTIC_INFERENCE
            and self.epistemic_scope is not EpistemicScope.ANALYTIC_INFERENCE
        ):
            raise ValueError("Analytic inference must use epistemic_scope analytic_inference.")

        if (
            self.epistemic_scope is EpistemicScope.ANALYTIC_INFERENCE
            and self.assertion_type is not AssertionType.ANALYTIC_INFERENCE
        ):
            raise ValueError("epistemic_scope analytic_inference must use analytic_inference.")

        if self.source_ids and self.source_authority is SourceAuthority.NOT_APPLICABLE:
            raise ValueError("Source-backed Assertion must declare source_authority.")

        if not self.source_ids and self.source_authority is not SourceAuthority.NOT_APPLICABLE:
            raise ValueError(
                "Non-source-backed Assertion must use source_authority not_applicable."
            )

        if (
            self.epistemic_scope is EpistemicScope.ATTRIBUTED_STATEMENT
            and self.attributed_to_id is None
        ):
            raise ValueError("Attributed statement Assertion must include attributed_to_id.")

        if self.source_authority is SourceAuthority.PRIMARY and (
            not self.authority_source_ids or not self.authority_evidence_target_ids
        ):
            raise ValueError("Primary source_authority must reference authority evidence.")

        if not set(self.authority_source_ids).issubset(self.source_ids):
            raise ValueError("authority_source_ids must be a subset of source_ids.")

        if not set(self.authority_evidence_target_ids).issubset(self.evidence_target_ids):
            raise ValueError(
                "authority_evidence_target_ids must be a subset of evidence_target_ids."
            )

        if (
            self.epistemic_scope is EpistemicScope.ANALYTIC_INFERENCE
            and not self.source_ids
            and self.attribution_basis is not AttributionBasis.NOT_APPLICABLE
        ):
            raise ValueError(
                "Non-source-backed analytic inference must use attribution_basis not_applicable."
            )

        if self.qualifiers.get("causal") is True and self.causal_confidence is None:
            raise ValueError("Causal analytic inference must include causal_confidence.")

        if self.qualifiers.get("causal") is True and (
            self.assertion_type is not AssertionType.ANALYTIC_INFERENCE
        ):
            raise ValueError("Causal inference must use assertion_type analytic_inference.")

        return self


class Relationship(DomainModel):
    id: RelationshipId
    subject_id: EntityId | ActorId | OrganizationId | EventId | PlaceId
    predicate: NonEmptyStr
    object_id: EntityId | ActorId | OrganizationId | EventId | PlaceId
    assertion_ids: tuple[AssertionId, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Outcome(DomainModel):
    id: OutcomeId
    description: NonEmptyStr
    actor_ids: tuple[ActorId, ...] = Field(default_factory=tuple)
    organization_ids: tuple[OrganizationId, ...] = Field(default_factory=tuple)
    event_ids: tuple[EventId, ...] = Field(default_factory=tuple)
    assertion_ids: tuple[AssertionId, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ArgumentEdge(DomainModel):
    id: ArgumentEdgeId
    from_assertion_id: AssertionId
    to_assertion_id: AssertionId
    relation: ArgumentEdgeRelation
    rationale: NonEmptyStr
    evidence_target_ids: tuple[EvidenceTargetId, ...] = Field(default_factory=tuple)
    confidence: Confidence
    created_at: datetime = Field(default_factory=utc_now)


class ProvenanceActivity(DomainModel):
    id: ProvenanceActivityId
    activity_type: NonEmptyStr
    agent: NonEmptyStr
    input_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    output_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    occurred_at: datetime = Field(default_factory=utc_now)


class ExtractionTask(DomainModel):
    """The immutable, fully pinned semantic task presented to one model run."""

    id: ExtractionTaskId
    task_type: NonEmptyStr
    context_manifest_id: NonEmptyStr
    context_manifest_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    context_manifest_payload: dict[str, JsonValue]
    input_candidate_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    prompt_id: NonEmptyStr
    schema_id: NonEmptyStr
    model_profile_id: NonEmptyStr
    execution_spec_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    task_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    created_at: datetime | None = None


class ContextManifestArtifact(DomainModel):
    """The immutable authoritative record of one finalized context manifest."""

    id: ContextManifestId
    analysis_unit_id: NonEmptyStr
    representation_id: DocumentRepresentationId
    manifest_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    payload: dict[str, JsonValue]
    created_at: datetime | None = None


class AnalysisUnitArtifact(DomainModel):
    """The immutable authoritative record of one planned analysis unit."""

    id: AnalysisUnitId
    representation_id: DocumentRepresentationId
    unit_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    payload: dict[str, JsonValue]
    created_at: datetime | None = None


class AnalysisPlanArtifact(DomainModel):
    """The immutable frozen scope of one document analysis run."""

    id: AnalysisPlanId
    representation_id: DocumentRepresentationId
    plan_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    payload: dict[str, JsonValue]
    created_at: datetime | None = None


class AnalysisRunState(StrEnum):
    RUNNING = "running"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisRun(DomainModel):
    id: AnalysisRunId
    document_id: DocumentId
    representation_id: DocumentRepresentationId
    frozen_analysis_plan_id: AnalysisPlanId
    coverage_policy_id: NonEmptyStr
    state: AnalysisRunState
    started_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        if self.state is AnalysisRunState.RUNNING and self.completed_at is not None:
            raise ValueError("A running AnalysisRun cannot have completed_at.")
        if self.state is not AnalysisRunState.RUNNING and self.completed_at is None:
            raise ValueError("A terminal AnalysisRun requires completed_at.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("AnalysisRun cannot complete before it starts.")
        return self


class PlannedAnalysisItem(DomainModel):
    id: PlannedAnalysisItemId
    analysis_run_id: AnalysisRunId
    analysis_unit_id: AnalysisUnitId
    task_type: NonEmptyStr
    required: bool
    dependencies: tuple[PlannedAnalysisItemId, ...] = Field(default_factory=tuple)
    expected_manifest_id: ContextManifestId | None = None
    input_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class AnalysisItemAttempt(DomainModel):
    id: AnalysisItemAttemptId
    planned_item_id: PlannedAnalysisItemId
    execution_role: NonEmptyStr
    processing_attempt_id: ProcessingAttemptId | None = None
    model_run_id: ModelRunId | None = None

    @model_validator(mode="after")
    def validate_execution_reference(self) -> Self:
        if (self.processing_attempt_id is None) == (self.model_run_id is None):
            raise ValueError("AnalysisItemAttempt must reference exactly one execution record.")
        return self


class ModelRun(DomainModel):
    """An immutable invocation attempt, including terminal failures and abstentions."""

    id: ModelRunId
    extraction_task_id: ExtractionTaskId
    task_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    model_identity: dict[str, JsonValue]
    runtime_identity: NonEmptyStr
    tokenizer_id: NonEmptyStr
    prompt_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    schema_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    execution_spec_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    generation_parameters: dict[str, JsonValue]
    raw_output_artifact_id: NonEmptyStr | None = None
    output_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    status: ModelRunStatus
    abstention_reason: NonEmptyStr | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime
    execution_receipt: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_output_state(self) -> Self:
        has_artifact = self.raw_output_artifact_id is not None
        has_digest = self.output_digest is not None
        if has_artifact != has_digest:
            raise ValueError("ModelRun raw output artifact and digest must be recorded together.")
        if self.status in {ModelRunStatus.SUCCEEDED, ModelRunStatus.ABSTAINED} and not has_artifact:
            raise ValueError("Successful or abstained ModelRun requires archived raw output.")
        if self.status is ModelRunStatus.ABSTAINED and self.abstention_reason is None:
            raise ValueError("Abstained ModelRun requires an abstention reason.")
        if self.status is not ModelRunStatus.ABSTAINED and self.abstention_reason is not None:
            raise ValueError("Only an abstained ModelRun may have an abstention reason.")
        response_statuses = {
            ModelRunStatus.SUCCEEDED,
            ModelRunStatus.ABSTAINED,
            ModelRunStatus.INVALID_OUTPUT,
            ModelRunStatus.OUTPUT_ARCHIVE_FAILED,
            ModelRunStatus.PUBLISH_FAILED,
        }
        if self.status in response_statuses and self.execution_receipt is None:
            raise ValueError("ModelRun with a runtime response requires its execution receipt.")
        if self.execution_receipt is not None:
            expected_keys = {
                "model_identity_digest",
                "generation_parameters_digest",
                "rendered_input_digest",
                "input_token_count",
                "output_token_count",
            }
            if set(self.execution_receipt) != expected_keys:
                raise ValueError("ModelRun execution receipt has an invalid shape.")
            for key in (
                "model_identity_digest",
                "generation_parameters_digest",
                "rendered_input_digest",
            ):
                value = self.execution_receipt[key]
                if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
                    raise ValueError("ModelRun execution receipt has an invalid digest.")
            input_token_count = self.execution_receipt["input_token_count"]
            output_token_count = self.execution_receipt["output_token_count"]
            if (
                not isinstance(input_token_count, int)
                or isinstance(input_token_count, bool)
                or input_token_count < 0
            ):
                raise ValueError("ModelRun execution receipt input token count is invalid.")
            if output_token_count is not None and (
                not isinstance(output_token_count, int)
                or isinstance(output_token_count, bool)
                or output_token_count < 0
            ):
                raise ValueError("ModelRun execution receipt output token count is invalid.")
        if self.completed_at < self.started_at:
            raise ValueError("ModelRun completed_at must not precede started_at.")
        return self


class ProposedChange(DomainModel):
    id: ProposedChangeId
    review_status: ReviewStatus = ReviewStatus.PENDING
    proposed_json: dict[str, JsonValue]
    original_proposed_json: dict[str, JsonValue] | None = None
    accepted_json: dict[str, JsonValue] | None = None
    source_id: SourceId | None = None
    document_id: DocumentId | None = None
    model_name: NonEmptyStr | None = None
    prompt_id: NonEmptyStr | None = None
    provenance_activity_id: ProvenanceActivityId | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_review_rules(self) -> Self:
        if self.review_status is ReviewStatus.EDITED and self.original_proposed_json is None:
            raise ValueError("Edited ProposedChange must store original proposed JSON.")
        if self.review_status is ReviewStatus.EDITED and self.accepted_json is None:
            raise ValueError("Edited ProposedChange must store accepted JSON.")
        return self


class Briefing(DomainModel):
    id: BriefingId
    title: NonEmptyStr
    previous_briefing_id: BriefingId | None = None
    entity_ids: tuple[EntityId, ...] = Field(default_factory=tuple)
    actor_ids: tuple[ActorId, ...] = Field(default_factory=tuple)
    organization_ids: tuple[OrganizationId, ...] = Field(default_factory=tuple)
    place_ids: tuple[PlaceId, ...] = Field(default_factory=tuple)
    event_ids: tuple[EventId, ...] = Field(default_factory=tuple)
    document_ids: tuple[DocumentId, ...] = Field(default_factory=tuple)
    assertion_ids: tuple[AssertionId, ...] = Field(default_factory=tuple)
    relationship_ids: tuple[RelationshipId, ...] = Field(default_factory=tuple)
    argument_edge_ids: tuple[ArgumentEdgeId, ...] = Field(default_factory=tuple)
    outcome_ids: tuple[OutcomeId, ...] = Field(default_factory=tuple)
    source_ids: tuple[SourceId, ...] = Field(default_factory=tuple)
    evidence_target_ids: tuple[EvidenceTargetId, ...] = Field(default_factory=tuple)
    analytic_inference_assertion_ids: tuple[AssertionId, ...] = Field(default_factory=tuple)
    provenance_activity_id: ProvenanceActivityId
    markdown_path: NonEmptyStr | None = None
    generated_at: datetime = Field(default_factory=utc_now)
