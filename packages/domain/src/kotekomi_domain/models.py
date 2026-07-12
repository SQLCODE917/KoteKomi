"""Domain Core models and validation rules."""

from __future__ import annotations

import hashlib
import json
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
ExtractionTaskId = Annotated[str, Field(pattern=r"^ext_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ModelRunId = Annotated[str, Field(pattern=r"^mrn_[A-Za-z0-9][A-Za-z0-9_-]*$")]


def utc_now() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    """Base model for immutable Domain Core records."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


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
    CANCELLED = "cancelled"


class ProcessingArtifactKind(StrEnum):
    DOCUMENT_REPRESENTATION = "document_representation"
    TEXT_VIEW = "text_view"
    DOCUMENT_NODE = "document_node"
    DOCUMENT_EDGE = "document_edge"
    SOURCE_REGION = "source_region"
    QUALITY_REPORT = "quality_report"
    PROVENANCE_ACTIVITY = "provenance_activity"


class OutputDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"


class ProcessingStage(StrEnum):
    BUILD_IDENTITY = "build_identity"
    ATTEMPT_START = "attempt_start"
    PARSER = "parser"
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


class SourceRegion(DomainModel):
    id: SourceRegionId
    representation_id: DocumentRepresentationId
    coordinate_system: NonEmptyStr
    page_number: Annotated[int, Field(ge=1)]
    page_width: Annotated[float, Field(gt=0)]
    page_height: Annotated[float, Field(gt=0)]
    left: Annotated[float, Field(ge=0)]
    top: Annotated[float, Field(ge=0)]
    right: Annotated[float, Field(ge=0)]
    bottom: Annotated[float, Field(ge=0)]

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
    parser_confidence: Confidence | None = None

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
        if not text_views:
            raise ValueError("Document representation must contain at least one TextView.")
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
        _validate_document_node_tree(tuple(nodes.values()))
        for edge in self.edges:
            if edge.representation_id != representation_id:
                raise ValueError("DocumentEdge must belong to the representation.")
            if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
                raise ValueError("DocumentEdge endpoints must exist in its representation.")
        actual_digest = canonical_representation_digest(
            self.representation,
            text_views=self.text_views,
            nodes=self.nodes,
            edges=self.edges,
            source_regions=self.source_regions,
            quality_report=self.quality_report,
        )
        if self.representation.canonical_output_digest != actual_digest:
            raise ValueError(
                "Document representation canonical_output_digest does not match output."
            )
        return self


def _require_unique_ids(
    records: tuple[TextView | DocumentNode | DocumentEdge | SourceRegion, ...],
    record_name: str,
) -> None:
    if len({record.id for record in records}) != len(records):
        raise ValueError(f"{record_name} IDs must be unique within a representation.")


def _validate_document_node_tree(nodes: tuple[DocumentNode, ...]) -> None:
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
            parent = next(candidate for candidate in nodes if candidate.id == parent_id)
            parent_id = parent.parent_node_id


def canonical_representation_digest(
    representation: DocumentRepresentation,
    *,
    text_views: tuple[TextView, ...],
    nodes: tuple[DocumentNode, ...],
    edges: tuple[DocumentEdge, ...],
    source_regions: tuple[SourceRegion, ...],
    quality_report: ParseQualityReport,
) -> str:
    """Return the SHA-256 digest of a stable representation serialization."""

    representation_payload = representation.model_dump(mode="json")
    representation_payload.pop("canonical_output_digest")
    representation_payload.pop("created_at")
    payload = {
        "representation": representation_payload,
        "text_views": [
            view.model_dump(mode="json") for view in sorted(text_views, key=lambda view: view.id)
        ],
        "nodes": [node.model_dump(mode="json") for node in sorted(nodes, key=lambda node: node.id)],
        "edges": [edge.model_dump(mode="json") for edge in sorted(edges, key=lambda edge: edge.id)],
        "source_regions": [
            region.model_dump(mode="json")
            for region in sorted(source_regions, key=lambda region: region.id)
        ],
        "quality_report": quality_report.model_dump(mode="json"),
    }
    canonical_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


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
    table_selector: dict[str, JsonValue] | None = None
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
    task_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    created_at: datetime = Field(default_factory=utc_now)


class ContextManifestArtifact(DomainModel):
    """The immutable authoritative record of one finalized context manifest."""

    id: ContextManifestId
    analysis_unit_id: NonEmptyStr
    representation_id: DocumentRepresentationId
    manifest_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    payload: dict[str, JsonValue]
    created_at: datetime | None = None


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
    generation_parameters: dict[str, JsonValue]
    raw_output_artifact_id: NonEmptyStr | None = None
    output_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    status: ModelRunStatus
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def validate_output_state(self) -> Self:
        has_artifact = self.raw_output_artifact_id is not None
        has_digest = self.output_digest is not None
        if has_artifact != has_digest:
            raise ValueError("ModelRun raw output artifact and digest must be recorded together.")
        if self.status in {ModelRunStatus.SUCCEEDED, ModelRunStatus.ABSTAINED} and not has_artifact:
            raise ValueError("Successful or abstained ModelRun requires archived raw output.")
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
