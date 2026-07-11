"""Domain Core models and validation rules."""

from __future__ import annotations

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
EvidenceSpanId = Annotated[str, Field(pattern=r"^evs_[A-Za-z0-9][A-Za-z0-9_-]*$")]
AssertionId = Annotated[str, Field(pattern=r"^ast_[A-Za-z0-9][A-Za-z0-9_-]*$")]
RelationshipId = Annotated[str, Field(pattern=r"^rel_[A-Za-z0-9][A-Za-z0-9_-]*$")]
OutcomeId = Annotated[str, Field(pattern=r"^out_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ArgumentEdgeId = Annotated[str, Field(pattern=r"^arg_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ProvenanceActivityId = Annotated[str, Field(pattern=r"^prv_[A-Za-z0-9][A-Za-z0-9_-]*$")]
ProposedChangeId = Annotated[str, Field(pattern=r"^pcg_[A-Za-z0-9][A-Za-z0-9_-]*$")]
BriefingId = Annotated[str, Field(pattern=r"^brf_[A-Za-z0-9][A-Za-z0-9_-]*$")]
RawBlobId = Annotated[str, Field(pattern=r"^blb_[A-Za-z0-9][A-Za-z0-9_-]*$")]
SourceCaptureId = Annotated[str, Field(pattern=r"^cap_[A-Za-z0-9][A-Za-z0-9_-]*$")]
DocumentRevisionRelationId = Annotated[
    str, Field(pattern=r"^drv_[A-Za-z0-9][A-Za-z0-9_-]*$")
]


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


class SelectorType(StrEnum):
    EXACT_TEXT = "exact_text"
    TEXT_POSITION = "text_position"
    PAGE = "page"


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
    DEPRECATED = "deprecated"


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
    title: NonEmptyStr
    uri: NonEmptyStr | None = None
    published_at: datetime | None = None
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


class Document(DomainModel):
    id: DocumentId
    source_id: SourceId
    raw_path: NonEmptyStr
    extracted_text_path: NonEmptyStr | None = None
    content_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    created_from_capture_id: SourceCaptureId | None = None
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


class EvidenceSpan(DomainModel):
    id: EvidenceSpanId
    source_id: SourceId
    document_id: DocumentId
    assertion_id: AssertionId | None = None
    selector_type: SelectorType
    exact_text: NonEmptyStr
    prefix_text: str = ""
    suffix_text: str = ""
    location: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


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
    evidence_span_ids: tuple[EvidenceSpanId, ...] = Field(default_factory=tuple)
    authority_source_ids: tuple[SourceId, ...] = Field(default_factory=tuple)
    authority_evidence_span_ids: tuple[EvidenceSpanId, ...] = Field(default_factory=tuple)
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

        if is_accepted_status(self.status) and self.source_ids and not self.evidence_span_ids:
            raise ValueError("Accepted Source-backed Assertion must reference an EvidenceSpan.")

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
            not self.authority_source_ids or not self.authority_evidence_span_ids
        ):
            raise ValueError("Primary source_authority must reference authority evidence.")

        if not set(self.authority_source_ids).issubset(self.source_ids):
            raise ValueError("authority_source_ids must be a subset of source_ids.")

        if not set(self.authority_evidence_span_ids).issubset(self.evidence_span_ids):
            raise ValueError(
                "authority_evidence_span_ids must be a subset of evidence_span_ids."
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
    evidence_span_ids: tuple[EvidenceSpanId, ...] = Field(default_factory=tuple)
    confidence: Confidence
    created_at: datetime = Field(default_factory=utc_now)


class ProvenanceActivity(DomainModel):
    id: ProvenanceActivityId
    activity_type: NonEmptyStr
    agent: NonEmptyStr
    input_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    output_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    occurred_at: datetime = Field(default_factory=utc_now)


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
    evidence_span_ids: tuple[EvidenceSpanId, ...] = Field(default_factory=tuple)
    analytic_inference_assertion_ids: tuple[AssertionId, ...] = Field(default_factory=tuple)
    provenance_activity_id: ProvenanceActivityId
    markdown_path: NonEmptyStr | None = None
    generated_at: datetime = Field(default_factory=utc_now)
