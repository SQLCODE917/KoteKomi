"""Authoritative structured-news capture, revision, rights, and representation use cases."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    DocumentEdge,
    DocumentEdgeProvenanceKind,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentRevisionType,
    DocumentSourceSelector,
    DocumentSourceSelectorKind,
    DocumentVersionKind,
    NewsDeliveryEnvelopeArtifact,
    NewsFormatPrecedence,
    NewsRepresentationMetadata,
    NewsRevisionClassification,
    NewsRightsFacts,
    NewsRightsProfile,
    NewsUsePurpose,
    OutputDisposition,
    ParseQualityReport,
    ProcessingArtifactKind,
    ProcessingArtifactRef,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingBlocker,
    ProcessingFailure,
    ProcessingStage,
    ProvenanceActivity,
    ProviderIdentity,
    ProviderNewsItem,
    RawBlob,
    RepresentationAnalyzability,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    AnalysisPlan,
    AnalysisUnitPlanningInput,
    ContextPlanningLedger,
    plan_analysis_units,
)
from kotekomi_application.ports import ArchiveStore
from kotekomi_application.processing import (
    BuildIdentity,
    ProcessingAttemptIdFactory,
    ProcessingClock,
    ProcessingLedger,
    begin_processing_task,
    processing_attempt_outcome,
    processing_task_fingerprint,
)
from kotekomi_application.representation_identity import (
    BundleCommitDisposition,
    BundleCommitOutcome,
    DocumentRepresentationBundleLedger,
    deterministic_representation_id,
)
from kotekomi_application.source_capture import (
    CaptureLedger,
    CaptureRequest,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    capture_identity,
    capture_source,
)

HASH_ID_LENGTH = 24
NEWS_RIGHTS_POLICY_ID = "explicit_news_rights_v1"
NEWS_CURRENT_REVISION_POLICY_ID = "explicit_revision_chain_v1"


class NewsIngestStatus(StrEnum):
    CREATED = "created"
    REUSED = "reused"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class NewsDeliveryEnvelope:
    payload: bytes
    media_type: str
    envelope_bytes: bytes
    envelope_media_type: str
    retrieval_method: str
    requested_uri: str | None
    canonical_uri: str | None
    response_status: int | None
    safe_metadata: dict[str, JsonValue]

    def __post_init__(self) -> None:
        forbidden = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
        if _safe_metadata_contains_secret(self.safe_metadata, forbidden):
            raise ValueError("News delivery envelope metadata must not contain secrets.")
        if not self.payload or not self.envelope_bytes:
            raise ValueError("News ingestion requires payload and canonical envelope bytes.")
        if self.response_status is not None and not 100 <= self.response_status <= 599:
            raise ValueError("News delivery response status is outside the HTTP range.")


@dataclass(frozen=True)
class NewsIdentification:
    identity: ProviderIdentity
    version_created_at: datetime
    first_published_at: datetime | None
    updated_at: datetime | None
    headlines: tuple[str, ...]
    rights: NewsRightsFacts
    format_precedence: NewsFormatPrecedence


@dataclass(frozen=True)
class NewsRevisionDecision:
    generic_kind: DocumentVersionKind
    provider_kind: str
    previous_provider_version: str | None
    classification_basis: tuple[str, ...]


@dataclass(frozen=True)
class NewsProcessorIdentity:
    adapter_name: str
    adapter_version: str
    adapter_config_digest: str
    output_contract_version: str


class NewsProviderAdapter(Protocol):
    @property
    def processor_identity(self) -> NewsProcessorIdentity: ...

    def identify(self, delivery: NewsDeliveryEnvelope) -> NewsIdentification: ...
    def parse(self, delivery: NewsDeliveryEnvelope) -> ProviderNewsItem: ...
    def classify_revision(
        self,
        identification: NewsIdentification,
        prior_revisions: tuple[NewsRevisionClassification, ...],
    ) -> NewsRevisionDecision: ...


class StructuredNewsLedger(
    CaptureLedger,
    DocumentRepresentationBundleLedger,
    ProcessingLedger,
    Protocol,
):
    def save_raw_blob(self, record: RawBlob) -> None: ...
    def save_news_rights_profile(self, record: NewsRightsProfile) -> None: ...
    def get_news_rights_profile(self, record_id: str) -> NewsRightsProfile | None: ...
    def save_news_delivery_envelope_artifact(
        self, record: NewsDeliveryEnvelopeArtifact
    ) -> None: ...
    def save_news_revision_classification(self, record: NewsRevisionClassification) -> None: ...
    def find_news_revision(
        self, provider_namespace: str, provider_item_id: str, provider_version: str
    ) -> NewsRevisionClassification | None: ...
    def list_news_revisions_for_source(
        self, source_id: str
    ) -> tuple[NewsRevisionClassification, ...]: ...
    def save_news_representation_metadata(self, record: NewsRepresentationMetadata) -> None: ...
    def get_news_representation_metadata(
        self, representation_id: str
    ) -> NewsRepresentationMetadata | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def commit_news_representation_processing(
        self,
        *,
        expected_task_fingerprint_id: str,
        bundle: DocumentRepresentationBundle,
        metadata: NewsRepresentationMetadata,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitOutcome: ...


class NewsContextPlanningLedger(StructuredNewsLedger, ContextPlanningLedger, Protocol):
    pass


@dataclass(frozen=True)
class NewsIngestInput:
    delivery: NewsDeliveryEnvelope
    captured_at: datetime
    transaction_time: datetime
    idempotency_key: str
    build_identity: BuildIdentity
    policy_id: str = NEWS_RIGHTS_POLICY_ID


@dataclass(frozen=True)
class NewsIngestOutcome:
    status: NewsIngestStatus
    source_id: str | None = None
    document_id: str | None = None
    representation_id: str | None = None
    processing_attempt_id: str | None = None
    rights_profile_id: str | None = None
    revision_classification_id: str | None = None
    blocking_code: str | None = None
    failure_code: str | None = None


@dataclass(frozen=True)
class NewsUseAuthorization:
    allowed: bool
    policy_id: str
    purpose: NewsUsePurpose
    reason: str


@dataclass(frozen=True)
class NewsAnalysisPlanningInput:
    representation_id: str
    policy_id: str
    task_type: str
    as_of: datetime
    max_focus_nodes_per_unit: int = 1


@dataclass(frozen=True)
class NewsAnalysisPlanningOutcome:
    authorization: NewsUseAuthorization
    plan: AnalysisPlan | None


class ExplicitNewsRightsPolicy:
    policy_id = NEWS_RIGHTS_POLICY_ID

    def build_profile(
        self,
        facts: NewsRightsFacts,
        *,
        provider_namespace: str,
        evaluated_at: datetime,
    ) -> NewsRightsProfile:
        if not facts.archive_permitted:
            raise PermissionError("news_archive_not_permitted")
        if (
            facts.entitlement_expires_at is not None
            and facts.entitlement_expires_at <= evaluated_at
        ):
            raise PermissionError("news_entitlement_expired")
        purposes = set(NewsUsePurpose)
        normalized_signals = {
            signal.casefold().rsplit(":", 1)[-1] for signal in facts.provider_signals
        }
        if not normalized_signals.intersection({"public-fixture", "redistributable"}):
            purposes.discard(NewsUsePurpose.PUBLIC_FIXTURE)
        if facts.embargo_until is not None and facts.embargo_until > evaluated_at:
            purposes.intersection_update(
                {NewsUsePurpose.ARCHIVE, NewsUsePurpose.DIAGNOSTIC, NewsUsePurpose.REVIEW}
            )
        if "restricted" in normalized_signals or "withheld" in normalized_signals:
            purposes.intersection_update(
                {NewsUsePurpose.ARCHIVE, NewsUsePurpose.DIAGNOSTIC, NewsUsePurpose.REVIEW}
            )
        if "no-model" in normalized_signals:
            purposes.discard(NewsUsePurpose.MODEL_CONTEXT)
        signal_restrictions = {
            "no-body": NewsUsePurpose.BODY_TEXT,
            "no-log": NewsUsePurpose.LOG,
            "no-export": NewsUsePurpose.EXPORT,
            "no-index": NewsUsePurpose.SEARCH_INDEX,
            "no-embed": NewsUsePurpose.EMBEDDING,
            "no-review": NewsUsePurpose.REVIEW,
            "no-briefing": NewsUsePurpose.BRIEFING,
            "no-graph": NewsUsePurpose.GRAPH_PUBLICATION,
        }
        for signal, purpose in signal_restrictions.items():
            if signal in normalized_signals:
                purposes.discard(purpose)
        facts_payload = facts.model_dump(mode="json")
        facts_digest = _digest(facts_payload)
        profile_digest = _digest(
            {
                "facts_digest": facts_digest,
                "policy_id": self.policy_id,
                "provider_namespace": provider_namespace,
                "allowed_purposes": sorted(purpose.value for purpose in purposes),
            }
        )
        return NewsRightsProfile(
            id=f"nrp_{profile_digest[:HASH_ID_LENGTH]}",
            policy_id=self.policy_id,
            facts_digest=facts_digest,
            provider_namespace=provider_namespace,
            usage_terms=facts.usage_terms,
            distribution_scopes=facts.distribution_scopes,
            provider_signals=facts.provider_signals,
            embargo_until=facts.embargo_until,
            entitlement_expires_at=facts.entitlement_expires_at,
            archive_permitted=facts.archive_permitted,
            allowed_purposes=tuple(sorted(purposes, key=lambda purpose: purpose.value)),
            created_at=evaluated_at,
        )

    def authorize(
        self,
        profile: NewsRightsProfile,
        purpose: NewsUsePurpose,
        *,
        as_of: datetime,
    ) -> NewsUseAuthorization:
        if profile.policy_id != self.policy_id:
            return NewsUseAuthorization(False, self.policy_id, purpose, "rights_policy_mismatch")
        if profile.entitlement_expires_at is not None and profile.entitlement_expires_at <= as_of:
            return NewsUseAuthorization(False, self.policy_id, purpose, "entitlement_expired")
        if (
            profile.embargo_until is not None
            and profile.embargo_until > as_of
            and purpose
            not in {
                NewsUsePurpose.ARCHIVE,
                NewsUsePurpose.DIAGNOSTIC,
                NewsUsePurpose.REVIEW,
            }
        ):
            return NewsUseAuthorization(False, self.policy_id, purpose, "embargo_active")
        if purpose not in profile.allowed_purposes:
            return NewsUseAuthorization(False, self.policy_id, purpose, "purpose_not_permitted")
        return NewsUseAuthorization(True, self.policy_id, purpose, "permitted")


def ingest_structured_news(
    ingest_input: NewsIngestInput,
    ledger: StructuredNewsLedger,
    archive: ArchiveStore,
    adapter: NewsProviderAdapter,
    attempt_id_factory: ProcessingAttemptIdFactory,
    clock: ProcessingClock,
    rights_policy: ExplicitNewsRightsPolicy | None = None,
) -> NewsIngestOutcome:
    ingest_input.build_identity.snapshot()
    transport_outcome = _delivery_failure(ingest_input.delivery.response_status)
    if transport_outcome is not None:
        return transport_outcome
    try:
        identification = adapter.identify(ingest_input.delivery)
    except ValueError:
        return NewsIngestOutcome(
            NewsIngestStatus.FAILED,
            failure_code="provider_payload_invalid",
        )
    policy = rights_policy or ExplicitNewsRightsPolicy()
    try:
        rights_profile = policy.build_profile(
            identification.rights,
            provider_namespace=identification.identity.provider_namespace,
            evaluated_at=ingest_input.transaction_time,
        )
    except PermissionError as exc:
        return NewsIngestOutcome(
            NewsIngestStatus.BLOCKED,
            blocking_code=str(exc),
        )

    provisional_request = _capture_request(
        ingest_input=ingest_input,
        identification=identification,
        rights_profile=rights_profile,
        revision_decision=NewsRevisionDecision(
            DocumentVersionKind.ORIGINAL, "original", None, ("provider_identity",)
        ),
    )
    identity_policy = StableSourceIdentityPolicy()
    provisional_identity = capture_identity(provisional_request, identity_policy)
    prior_revisions = ledger.list_news_revisions_for_source(provisional_identity.source_id)
    existing_revision = ledger.find_news_revision(
        identification.identity.provider_namespace,
        identification.identity.provider_item_id,
        identification.identity.provider_version,
    )
    if existing_revision is None:
        try:
            revision_decision = adapter.classify_revision(identification, prior_revisions)
            previous = _previous_revision(revision_decision, prior_revisions)
        except ValueError:
            return NewsIngestOutcome(
                NewsIngestStatus.FAILED,
                failure_code="provider_revision_invalid",
            )
    else:
        existing_profile = ledger.get_news_rights_profile(existing_revision.rights_profile_id)
        if existing_profile is None:
            raise ValueError("Existing news revision is missing its rights profile.")
        if (
            existing_profile.facts_digest != rights_profile.facts_digest
            or existing_profile.allowed_purposes != rights_profile.allowed_purposes
        ):
            return NewsIngestOutcome(
                NewsIngestStatus.FAILED,
                failure_code="provider_identity_rights_conflict",
            )
        rights_profile = existing_profile
        previous = next(
            (
                revision
                for revision in prior_revisions
                if revision.document_id == existing_revision.previous_document_id
            ),
            None,
        )
        revision_decision = NewsRevisionDecision(
            existing_revision.generic_kind,
            existing_revision.provider_kind,
            previous.provider_version if previous is not None else None,
            existing_revision.classification_basis,
        )
    request = _capture_request(
        ingest_input=ingest_input,
        identification=identification,
        rights_profile=rights_profile,
        revision_decision=revision_decision,
        previous=previous,
    )
    identity = capture_identity(request, identity_policy)
    if (
        existing_revision is not None
        and existing_revision.content_digest != identity.content_digest
    ):
        return NewsIngestOutcome(
            NewsIngestStatus.FAILED,
            failure_code="provider_identity_version_conflict",
        )

    payload_archive = archive.put_if_absent_or_identical(
        identity.raw_blob_id,
        ingest_input.delivery.payload,
        identity.content_digest,
    )
    envelope_digest = hashlib.sha256(ingest_input.delivery.envelope_bytes).hexdigest()
    envelope_blob_id = f"blb_{envelope_digest}"
    envelope_archive = archive.put_if_absent_or_identical(
        envelope_blob_id,
        ingest_input.delivery.envelope_bytes,
        envelope_digest,
    )
    request = replace(request, storage_locator=payload_archive.object.relative_path)
    ledger.save_news_rights_profile(rights_profile)
    capture = capture_source(request, ledger, identity_policy)
    envelope_blob = RawBlob(
        id=envelope_blob_id,
        hash_algorithm="sha256",
        digest=envelope_digest,
        byte_length=len(ingest_input.delivery.envelope_bytes),
        media_type=ingest_input.delivery.envelope_media_type,
        storage_locator=envelope_archive.object.relative_path,
        created_at=capture.source_capture.transaction_time,
    )
    existing_envelope_blob = ledger.get_raw_blob(envelope_blob_id)
    if existing_envelope_blob is None:
        ledger.save_raw_blob(envelope_blob)
    elif existing_envelope_blob != envelope_blob:
        raise ValueError("Archived news delivery envelope conflicts with its digest.")
    envelope_artifact_digest = _digest(
        {"capture_id": capture.source_capture.id, "digest": envelope_digest}
    )
    envelope_artifact = NewsDeliveryEnvelopeArtifact(
        id=f"nde_{envelope_artifact_digest[:HASH_ID_LENGTH]}",
        capture_id=capture.source_capture.id,
        blob_id=envelope_blob.id,
        envelope_digest=envelope_digest,
        retrieval_method=ingest_input.delivery.retrieval_method,
        requested_uri=ingest_input.delivery.requested_uri,
        canonical_uri=ingest_input.delivery.canonical_uri,
        response_status=ingest_input.delivery.response_status,
        safe_metadata=ingest_input.delivery.safe_metadata,
        created_at=capture.source_capture.transaction_time,
    )
    ledger.save_news_delivery_envelope_artifact(envelope_artifact)
    classification = existing_revision or _classification(
        capture.document.id,
        capture.source.id,
        identity.content_digest,
        identification,
        rights_profile,
        revision_decision,
        previous,
        ingest_input.transaction_time,
    )
    ledger.save_news_revision_classification(classification)

    processor = adapter.processor_identity
    task = processing_task_fingerprint(
        task_kind="structured_news_document_representation",
        document_id=capture.document.id,
        blob_id=capture.raw_blob.id,
        input_digest=capture.raw_blob.digest,
        processor_name=processor.adapter_name,
        processor_version=processor.adapter_version,
        processor_config_digest=processor.adapter_config_digest,
        build_identity=ingest_input.build_identity,
        policy_id=ingest_input.policy_id,
        output_contract_version=processor.output_contract_version,
    )
    attempt = begin_processing_task(
        task=task,
        ledger=ledger,
        attempt_id_factory=attempt_id_factory,
        clock=clock,
        invocation_id=f"structured_news:{capture.document.id}:{ingest_input.idempotency_key}",
        interruption_basis="structured-news retry found an unclosed attempt",
    )
    try:
        item = adapter.parse(ingest_input.delivery)
    except Exception as exc:
        _record_news_failure(
            ledger,
            attempt,
            clock,
            code="structured_news_parser_failure",
            stage=ProcessingStage.PARSER,
            error=exc,
            retryable=False,
        )
        return _failed_ingest_outcome(
            capture.source.id,
            capture.document.id,
            attempt.id,
            rights_profile.id,
            classification.id,
            "structured_news_parser_failure",
        )
    try:
        _validate_identification(item, identification)
        bundle, metadata = _news_representation(
            item=item,
            classification=classification,
            rights_profile=rights_profile,
            task_id=task.id,
            document_id=capture.document.id,
            input_digest=capture.raw_blob.digest,
            processor=processor,
            created_at=classification.recorded_at,
        )
    except Exception as exc:
        _record_news_failure(
            ledger,
            attempt,
            clock,
            code="structured_news_representation_validation_failure",
            stage=ProcessingStage.REPRESENTATION_VALIDATION,
            error=exc,
            retryable=False,
        )
        return _failed_ingest_outcome(
            capture.source.id,
            capture.document.id,
            attempt.id,
            rights_profile.id,
            classification.id,
            "structured_news_representation_validation_failure",
        )
    blocked = classification.generic_kind is DocumentVersionKind.WITHDRAWAL
    artifacts = (
        ProcessingArtifactRef(
            kind=ProcessingArtifactKind.DOCUMENT_REPRESENTATION,
            artifact_id=bundle.representation.id,
            role="canonical_document_representation",
        ),
        ProcessingArtifactRef(
            kind=ProcessingArtifactKind.NEWS_REPRESENTATION_METADATA,
            artifact_id=metadata.id,
            role="provider_news_metadata",
        ),
    )
    created_outcome = processing_attempt_outcome(
        attempt=attempt,
        status=(ProcessingAttemptStatus.BLOCKED if blocked else ProcessingAttemptStatus.SUCCEEDED),
        finished_at=clock.now(),
        output_artifacts=artifacts,
        output_disposition=None if blocked else OutputDisposition.CREATED,
        blocking_reasons=(
            (
                ProcessingBlocker(
                    code="provider_withdrawal",
                    stage=ProcessingStage.REPRESENTATION_VALIDATION,
                    safe_message="Provider withdrew this item from current publication.",
                ),
            )
            if blocked
            else ()
        ),
        provenance_activity_id=_provenance_id(task.id),
    )
    reused_outcome = created_outcome.model_copy(
        update={
            "output_disposition": None if blocked else OutputDisposition.REUSED,
        }
    )
    try:
        commit = ledger.commit_news_representation_processing(
            expected_task_fingerprint_id=task.id,
            bundle=bundle,
            metadata=metadata,
            created_provenance_activity=_provenance(
                task.id,
                capture.document.id,
                bundle,
                metadata,
                classification.recorded_at,
            ),
            created_outcome=created_outcome,
            reused_outcome=reused_outcome,
        )
    except Exception as exc:
        _record_news_failure(
            ledger,
            attempt,
            clock,
            code="structured_news_persistence_failure",
            stage=ProcessingStage.PERSISTENCE,
            error=exc,
            retryable=True,
        )
        return _failed_ingest_outcome(
            capture.source.id,
            capture.document.id,
            attempt.id,
            rights_profile.id,
            classification.id,
            "structured_news_persistence_failure",
        )
    return NewsIngestOutcome(
        status=(
            NewsIngestStatus.BLOCKED
            if blocked
            else (
                NewsIngestStatus.CREATED
                if commit.disposition is BundleCommitDisposition.CREATED
                else NewsIngestStatus.REUSED
            )
        ),
        source_id=capture.source.id,
        document_id=capture.document.id,
        representation_id=bundle.representation.id,
        processing_attempt_id=attempt.id,
        rights_profile_id=rights_profile.id,
        revision_classification_id=classification.id,
        blocking_code="provider_withdrawal" if blocked else None,
    )


def authorize_news_use(
    profile: NewsRightsProfile,
    purpose: NewsUsePurpose,
    *,
    as_of: datetime,
    policy: ExplicitNewsRightsPolicy | None = None,
) -> NewsUseAuthorization:
    return (policy or ExplicitNewsRightsPolicy()).authorize(profile, purpose, as_of=as_of)


def authorize_news_representation_use(
    representation_id: str,
    purpose: NewsUsePurpose,
    *,
    as_of: datetime,
    ledger: StructuredNewsLedger,
    policy: ExplicitNewsRightsPolicy | None = None,
) -> NewsUseAuthorization:
    metadata = ledger.get_news_representation_metadata(representation_id)
    if metadata is None:
        raise ValueError("DocumentRepresentation has no authoritative news metadata.")
    profile = ledger.get_news_rights_profile(metadata.rights_profile_id)
    if profile is None:
        raise ValueError("News representation references a missing rights profile.")
    return authorize_news_use(profile, purpose, as_of=as_of, policy=policy)


def plan_news_analysis_units(
    planning_input: NewsAnalysisPlanningInput,
    ledger: NewsContextPlanningLedger,
    policy: ExplicitNewsRightsPolicy | None = None,
) -> NewsAnalysisPlanningOutcome:
    authorization = authorize_news_representation_use(
        planning_input.representation_id,
        NewsUsePurpose.MODEL_CONTEXT,
        as_of=planning_input.as_of,
        ledger=ledger,
        policy=policy,
    )
    if not authorization.allowed:
        return NewsAnalysisPlanningOutcome(authorization, None)
    plan = plan_analysis_units(
        AnalysisUnitPlanningInput(
            representation_id=planning_input.representation_id,
            policy_id=planning_input.policy_id,
            task_type=planning_input.task_type,
            max_focus_nodes_per_unit=planning_input.max_focus_nodes_per_unit,
        ),
        ledger,
    )
    return NewsAnalysisPlanningOutcome(authorization, plan)


def select_current_news_revision(
    revisions: tuple[NewsRevisionClassification, ...],
) -> NewsRevisionClassification | None:
    if not revisions:
        return None
    by_document = {revision.document_id: revision for revision in revisions}
    if len(by_document) != len(revisions):
        raise ValueError("News revision chain contains duplicate Document identities.")
    identity_keys = {
        (revision.source_id, revision.provider_namespace, revision.provider_item_id)
        for revision in revisions
    }
    if len(identity_keys) != 1:
        raise ValueError("News revision chain mixes provider item identities.")
    originals = tuple(
        revision for revision in revisions if revision.generic_kind is DocumentVersionKind.ORIGINAL
    )
    if len(originals) != 1:
        raise ValueError("News revision chain requires exactly one original.")
    for revision in revisions:
        if (
            revision.generic_kind is not DocumentVersionKind.ORIGINAL
            and revision.previous_document_id not in by_document
        ):
            raise ValueError("News revision chain references a missing predecessor.")
    predecessor_ids = {
        revision.previous_document_id
        for revision in revisions
        if revision.previous_document_id is not None
    }
    tips = tuple(revision for revision in revisions if revision.document_id not in predecessor_ids)
    if len(tips) != 1:
        raise ValueError("News revision chain has an ambiguous current tip.")
    tip = tips[0]
    visited: set[str] = set()
    cursor: NewsRevisionClassification | None = tip
    while cursor is not None:
        if cursor.document_id in visited:
            raise ValueError("News revision chain contains a cycle.")
        visited.add(cursor.document_id)
        cursor = (
            by_document[cursor.previous_document_id]
            if cursor.previous_document_id is not None
            else None
        )
    if len(visited) != len(revisions) or originals[0].document_id not in visited:
        raise ValueError("News revision chain is disconnected or branched.")
    return None if tip.generic_kind is DocumentVersionKind.WITHDRAWAL else tip


def _capture_request(
    *,
    ingest_input: NewsIngestInput,
    identification: NewsIdentification,
    rights_profile: NewsRightsProfile,
    revision_decision: NewsRevisionDecision,
    previous: NewsRevisionClassification | None = None,
) -> CaptureRequest:
    identity = identification.identity
    relation_type = {
        DocumentVersionKind.UPDATE: DocumentRevisionType.UPDATES,
        DocumentVersionKind.CORRECTION: DocumentRevisionType.CORRECTS,
        DocumentVersionKind.CLARIFICATION: DocumentRevisionType.CLARIFIES,
        DocumentVersionKind.WITHDRAWAL: DocumentRevisionType.WITHDRAWS,
    }.get(revision_decision.generic_kind)
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.ARTICLE,
            title=identification.headlines[0]
            if identification.headlines
            else identity.provider_item_id,
            stable_key=f"{identity.provider_namespace}:{identity.provider_item_id}",
            uri=identity.canonical_uri,
        ),
        payload=ingest_input.delivery.payload,
        media_type=ingest_input.delivery.media_type,
        storage_locator="pending",
        idempotency_key=ingest_input.idempotency_key,
        retrieval_method=ingest_input.delivery.retrieval_method,
        requested_uri=ingest_input.delivery.requested_uri,
        canonical_uri=identity.canonical_uri or ingest_input.delivery.canonical_uri,
        provider_item_id=identity.provider_item_id,
        provider_version=identity.provider_version,
        version_kind=revision_decision.generic_kind,
        publication_time=identification.first_published_at,
        provider_update_time=identification.updated_at or identification.version_created_at,
        captured_at=ingest_input.captured_at,
        transaction_time=ingest_input.transaction_time,
        rights_profile_id=rights_profile.id,
        embargo_until=identification.rights.embargo_until,
        request_metadata={},
        response_metadata=ingest_input.delivery.safe_metadata,
        revision_of_document_id=previous.document_id if previous is not None else None,
        revision_type=relation_type,
        provider_namespace=identity.provider_namespace,
    )


def _previous_revision(
    decision: NewsRevisionDecision,
    priors: tuple[NewsRevisionClassification, ...],
) -> NewsRevisionClassification | None:
    if decision.generic_kind is DocumentVersionKind.ORIGINAL:
        if priors:
            raise ValueError("Original provider item already has revision history.")
        return None
    if decision.previous_provider_version is None:
        raise ValueError("Non-original news revision requires a provider predecessor version.")
    matches = tuple(
        revision
        for revision in priors
        if revision.provider_version == decision.previous_provider_version
    )
    if len(matches) != 1:
        raise ValueError("News revision predecessor is missing or ambiguous.")
    return matches[0]


def _classification(
    document_id: str,
    source_id: str,
    content_digest: str,
    identification: NewsIdentification,
    rights_profile: NewsRightsProfile,
    decision: NewsRevisionDecision,
    previous: NewsRevisionClassification | None,
    recorded_at: datetime,
) -> NewsRevisionClassification:
    identity = identification.identity
    digest = _digest(
        {
            "source_id": source_id,
            "document_id": document_id,
            "provider_version": identity.provider_version,
            "generic_kind": decision.generic_kind.value,
            "provider_kind": decision.provider_kind,
        }
    )
    return NewsRevisionClassification(
        id=f"nrc_{digest[:HASH_ID_LENGTH]}",
        document_id=document_id,
        source_id=source_id,
        provider_namespace=identity.provider_namespace,
        provider_item_id=identity.provider_item_id,
        provider_version=identity.provider_version,
        provider_status=identity.provider_status,
        normalized_version_key=identity.normalized_version_key,
        generic_kind=decision.generic_kind,
        previous_document_id=previous.document_id if previous is not None else None,
        provider_kind=decision.provider_kind,
        classification_basis=decision.classification_basis,
        content_digest=content_digest,
        rights_profile_id=rights_profile.id,
        recorded_at=recorded_at,
    )


def _news_representation(
    *,
    item: ProviderNewsItem,
    classification: NewsRevisionClassification,
    rights_profile: NewsRightsProfile,
    task_id: str,
    document_id: str,
    input_digest: str,
    processor: NewsProcessorIdentity,
    created_at: datetime,
) -> tuple[DocumentRepresentationBundle, NewsRepresentationMetadata]:
    representation_id = deterministic_representation_id(task_id)
    key = representation_id.removeprefix("rep_")
    text_parts = tuple(element.text for element in item.body_elements if element.text)
    text = "\n\n".join(text_parts)
    view = TextView(
        id=f"tvw_{key}_logical",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="provider_element_join_v1",
    )
    root = DocumentNode(
        id=f"nod_{key}_document",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        structural_path=("document",),
        text_view_id=view.id,
        start_char=0,
        end_char=len(text),
    )
    nodes: list[DocumentNode] = [root]
    selectors: list[DocumentSourceSelector] = []
    cursor = 0
    text_elements = tuple(element for element in item.body_elements if element.text)
    for index, element in enumerate(text_elements, start=1):
        start = cursor
        end = start + len(element.text)
        node_id = f"nod_{key}_{index:04d}"
        nodes.append(
            DocumentNode(
                id=node_id,
                representation_id=representation_id,
                parent_node_id=root.id,
                node_type=element.kind.value,
                order_index=index,
                structural_path=element.hierarchy_path or (element.kind.value, str(index)),
                text_view_id=view.id,
                start_char=start,
                end_char=end,
            )
        )
        selector_kind = (
            DocumentSourceSelectorKind.DOM_PATH
            if item.format_precedence
            in {
                NewsFormatPrecedence.NEWSARTICLE_JSON_LD,
                NewsFormatPrecedence.SEMANTIC_HTML,
                NewsFormatPrecedence.MAIN_TEXT_FALLBACK,
            }
            else DocumentSourceSelectorKind.XML_PATH
        )
        selectors.append(
            DocumentSourceSelector(
                id=f"dss_{key}_{index:04d}",
                representation_id=representation_id,
                node_id=node_id,
                kind=selector_kind,
                path=element.source_path,
                element_digest=hashlib.sha256(element.text.encode()).hexdigest(),
            )
        )
        cursor = end + (2 if index < len(text_elements) else 0)
    edges = tuple(
        DocumentEdge(
            id=f"deg_{key}_contains_{index:04d}",
            representation_id=representation_id,
            from_node_id=root.id,
            to_node_id=node.id,
            edge_type="contains",
            provenance_kind=DocumentEdgeProvenanceKind.PARSER,
            provenance_id=f"{processor.adapter_name}:{processor.adapter_version}",
        )
        for index, node in enumerate(nodes[1:], start=1)
    )
    analyzability = (
        RepresentationAnalyzability.BLOCKED
        if classification.generic_kind is DocumentVersionKind.WITHDRAWAL or not text
        else (
            RepresentationAnalyzability.DEGRADED
            if item.format_precedence is NewsFormatPrecedence.MAIN_TEXT_FALLBACK
            else RepresentationAnalyzability.ACCEPTABLE
        )
    )
    quality = ParseQualityReport(
        id=f"pqr_{key}_quality_v1",
        representation_id=representation_id,
        metric_values={
            "body_element_count": len(item.body_elements),
            "format_precedence": item.format_precedence.value,
        },
        issues=("provider_withdrawal",)
        if classification.generic_kind is DocumentVersionKind.WITHDRAWAL
        else (),
        analyzability=analyzability,
    )
    representation = DocumentRepresentation(
        id=representation_id,
        document_id=document_id,
        parser_name=processor.adapter_name,
        parser_version=processor.adapter_version,
        parser_config_digest=processor.adapter_config_digest,
        processing_task_fingerprint_id=task_id,
        input_blob_digest=input_digest,
        canonical_output_digest="0" * 64,
        created_at=created_at,
    )
    digest = canonical_representation_digest(
        representation,
        text_views=(view,),
        nodes=tuple(nodes),
        edges=edges,
        source_regions=(),
        quality_report=quality,
        source_selectors=tuple(selectors),
    )
    bundle = DocumentRepresentationBundle(
        representation=representation.model_copy(update={"canonical_output_digest": digest}),
        text_views=(view,),
        nodes=tuple(nodes),
        edges=edges,
        source_selectors=tuple(selectors),
        quality_report=quality,
    )
    metadata = NewsRepresentationMetadata(
        id=f"nrm_{key}",
        representation_id=representation_id,
        document_id=document_id,
        revision_classification_id=classification.id,
        rights_profile_id=rights_profile.id,
        adapter_name=processor.adapter_name,
        adapter_version=processor.adapter_version,
        format_precedence=item.format_precedence,
        provider_status=item.identity.provider_status,
        version_created_at=item.version_created_at,
        first_published_at=item.first_published_at,
        updated_at=item.updated_at,
        language=item.language,
        headlines=item.headlines,
        bylines=item.bylines,
        dateline=item.dateline,
        subjects=item.subjects,
        locations=item.locations,
        media_references=item.media_references,
        raw_metadata=item.raw_metadata,
    )
    return bundle, metadata


def _validate_identification(item: ProviderNewsItem, identification: NewsIdentification) -> None:
    if item.identity != identification.identity:
        raise ValueError("Parsed provider identity disagrees with preflight identification.")
    if item.version_created_at != identification.version_created_at:
        raise ValueError("Parsed provider version timestamp disagrees with identification.")
    if item.rights != identification.rights:
        raise ValueError("Parsed provider rights disagree with identification.")
    if item.format_precedence is not identification.format_precedence:
        raise ValueError("Parsed format precedence disagrees with identification.")


def _delivery_failure(status: int | None) -> NewsIngestOutcome | None:
    if status in {401, 403}:
        return NewsIngestOutcome(NewsIngestStatus.BLOCKED, blocking_code="provider_entitlement")
    if status == 429:
        return NewsIngestOutcome(NewsIngestStatus.BLOCKED, blocking_code="provider_rate_limit")
    if status is not None and status >= 500:
        return NewsIngestOutcome(NewsIngestStatus.FAILED, failure_code="provider_server_error")
    return None


def _record_news_failure(
    ledger: StructuredNewsLedger,
    attempt: ProcessingAttempt,
    clock: ProcessingClock,
    *,
    code: str,
    stage: ProcessingStage,
    error: Exception,
    retryable: bool,
) -> None:
    ledger.record_failed_processing_attempt_outcome(
        processing_attempt_outcome(
            attempt=attempt,
            status=ProcessingAttemptStatus.FAILED,
            finished_at=clock.now(),
            failure=ProcessingFailure(
                code=code,
                failure_type=type(error).__name__,
                stage=stage,
                safe_message="Structured-news processing failed.",
                retryable=retryable,
            ),
        )
    )


def _failed_ingest_outcome(
    source_id: str,
    document_id: str,
    attempt_id: str,
    rights_profile_id: str,
    revision_classification_id: str,
    failure_code: str,
) -> NewsIngestOutcome:
    return NewsIngestOutcome(
        NewsIngestStatus.FAILED,
        source_id=source_id,
        document_id=document_id,
        processing_attempt_id=attempt_id,
        rights_profile_id=rights_profile_id,
        revision_classification_id=revision_classification_id,
        failure_code=failure_code,
    )


def _provenance_id(task_id: str) -> str:
    digest = _digest({"task_id": task_id, "activity": "structured_news_representation"})
    return f"prv_{digest[:HASH_ID_LENGTH]}"


def _provenance(
    task_id: str,
    document_id: str,
    bundle: DocumentRepresentationBundle,
    metadata: NewsRepresentationMetadata,
    created_at: datetime,
) -> ProvenanceActivity:
    return ProvenanceActivity(
        id=_provenance_id(task_id),
        activity_type="structured_news_representation",
        agent="kotekomi_application.structured_news",
        input_ids=(document_id, task_id),
        output_ids=(bundle.representation.id, metadata.id),
        occurred_at=created_at,
    )


def _digest(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _safe_metadata_contains_secret(value: JsonValue, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            key.casefold() in forbidden or _safe_metadata_contains_secret(item, forbidden)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_safe_metadata_contains_secret(item, forbidden) for item in value)
    return False
