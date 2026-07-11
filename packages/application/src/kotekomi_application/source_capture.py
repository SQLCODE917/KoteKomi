"""Stable Source identity and immutable Document-version capture use case."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    Document,
    DocumentRevisionRelation,
    DocumentRevisionType,
    DocumentVersionKind,
    RawBlob,
    Source,
    SourceCapture,
    SourceType,
)
from kotekomi_domain.models import JsonValue

HASH_ID_LENGTH = 24


@dataclass(frozen=True)
class SourceIdentityHint:
    source_type: SourceType
    title: str
    stable_key: str
    uri: str | None = None


class SourceIdentityPolicy(Protocol):
    @property
    def policy_id(self) -> str: ...

    def canonical_key(self, hint: SourceIdentityHint) -> str: ...


@dataclass(frozen=True)
class CaptureRequest:
    identity_hint: SourceIdentityHint
    payload: bytes
    media_type: str
    storage_locator: str
    idempotency_key: str
    retrieval_method: str
    requested_uri: str | None
    canonical_uri: str | None
    provider_item_id: str | None
    provider_version: str | None
    version_kind: DocumentVersionKind
    publication_time: datetime | None
    provider_update_time: datetime | None
    captured_at: datetime
    transaction_time: datetime
    rights_profile_id: str | None
    embargo_until: datetime | None
    request_metadata: dict[str, JsonValue]
    response_metadata: dict[str, JsonValue]
    extracted_text_locator: str | None = None
    revision_of_document_id: str | None = None
    revision_type: DocumentRevisionType | None = None


@dataclass(frozen=True)
class CaptureOutcome:
    source: Source
    raw_blob: RawBlob
    source_capture: SourceCapture
    document: Document
    revision_relation: DocumentRevisionRelation | None
    created: bool


@dataclass(frozen=True)
class CaptureIdentity:
    """Deterministic identities allocated by a capture request."""

    source_id: str
    raw_blob_id: str
    source_capture_id: str
    document_id: str
    content_digest: str


class CaptureLedger(Protocol):
    def get_source(self, record_id: str) -> Source | None: ...
    def get_raw_blob(self, record_id: str) -> RawBlob | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_source_capture(self, record_id: str) -> SourceCapture | None: ...
    def list_documents(self) -> tuple[Document, ...]: ...
    def list_document_revision_relations(self) -> tuple[DocumentRevisionRelation, ...]: ...
    def save_source(self, record: Source) -> None: ...
    def save_raw_blob(self, record: RawBlob) -> None: ...
    def save_source_capture(self, record: SourceCapture) -> None: ...
    def save_document(self, record: Document) -> None: ...
    def save_document_revision_relation(self, record: DocumentRevisionRelation) -> None: ...


class StableSourceIdentityPolicy:
    policy_id = "stable_source_identity_v1"

    def canonical_key(self, hint: SourceIdentityHint) -> str:
        return hint.stable_key.strip()


def capture_source(
    request: CaptureRequest,
    ledger_repository: CaptureLedger,
    identity_policy: SourceIdentityPolicy,
) -> CaptureOutcome:
    identity = capture_identity(request, identity_policy)
    existing_capture = ledger_repository.get_source_capture(identity.source_capture_id)
    if existing_capture is not None:
        source = ledger_repository.get_source(identity.source_id)
        raw_blob = ledger_repository.get_raw_blob(identity.raw_blob_id)
        existing_document = ledger_repository.get_document(identity.document_id)
        if (
            source is None
            or raw_blob is None
            or existing_document is None
            or not _is_idempotent_retry(
                request=request,
                source=source,
                raw_blob=raw_blob,
                capture=existing_capture,
                document=existing_document,
                relation=_requested_relation(request, identity),
                ledger_repository=ledger_repository,
            )
        ):
            raise ValueError("Capture idempotency conflict.")
        return CaptureOutcome(
            source,
            raw_blob,
            existing_capture,
            existing_document,
            _find_requested_relation(request, identity, ledger_repository),
            False,
        )
    _validate_revision_request(request, identity)
    _validate_provider_version_conflict(request, identity, ledger_repository)

    existing_document = ledger_repository.get_document(identity.document_id)
    if request.revision_of_document_id is not None:
        earlier = ledger_repository.get_document(request.revision_of_document_id)
        if earlier is None or earlier.source_id != identity.source_id:
            raise ValueError(
                "Document revision must reference an existing Document for the same Source."
            )
        if existing_document is not None:
            raise ValueError("Document revision requires changed content.")
        if _would_create_revision_cycle(ledger_repository, earlier.id, identity.document_id):
            raise ValueError("Document revision relation would create a cycle.")

    source = ledger_repository.get_source(identity.source_id)
    source_is_new = source is None
    if source is None:
        source = Source(
            id=identity.source_id,
            source_type=request.identity_hint.source_type,
            title=request.identity_hint.title,
            uri=request.identity_hint.uri,
            published_at=request.publication_time,
            created_at=request.transaction_time,
            updated_at=request.transaction_time,
        )
    raw_blob = ledger_repository.get_raw_blob(identity.raw_blob_id)
    raw_blob_is_new = raw_blob is None
    if raw_blob is None:
        raw_blob = RawBlob(
            id=identity.raw_blob_id,
            hash_algorithm="sha256",
            digest=identity.content_digest,
            byte_length=len(request.payload),
            media_type=request.media_type,
            storage_locator=request.storage_locator,
            created_at=request.transaction_time,
        )
    capture = SourceCapture(
        id=identity.source_capture_id,
        source_id=identity.source_id,
        blob_id=identity.raw_blob_id,
        idempotency_key=request.idempotency_key,
        retrieval_method=request.retrieval_method,
        requested_uri=request.requested_uri,
        canonical_uri=request.canonical_uri,
        request_metadata=request.request_metadata,
        response_metadata=request.response_metadata,
        provider_item_id=request.provider_item_id,
        provider_version=request.provider_version,
        rights_profile_id=request.rights_profile_id,
        embargo_until=request.embargo_until,
        captured_at=request.captured_at,
        transaction_time=request.transaction_time,
    )
    document_is_new = existing_document is None
    document = existing_document or Document(
        id=identity.document_id,
        source_id=identity.source_id,
        raw_path=request.storage_locator,
        extracted_text_path=request.extracted_text_locator,
        content_sha256=identity.content_digest,
        created_from_capture_id=identity.source_capture_id,
        provider_version=request.provider_version,
        publication_time=request.publication_time,
        provider_update_time=request.provider_update_time,
        version_kind=request.version_kind,
        created_at=request.transaction_time,
        updated_at=request.transaction_time,
    )
    relation = _requested_relation(request, identity)

    if source_is_new:
        ledger_repository.save_source(source)
    if raw_blob_is_new:
        ledger_repository.save_raw_blob(raw_blob)
    ledger_repository.save_source_capture(capture)
    if document_is_new:
        ledger_repository.save_document(document)
    if relation is not None:
        # The caller supplies one transaction for the complete capture use case.
        # Rechecking immediately before the insert closes the relation-check/write gap.
        if _would_create_revision_cycle(
            ledger_repository, relation.earlier_document_id, relation.later_document_id
        ):
            raise ValueError("Document revision relation would create a cycle.")
        ledger_repository.save_document_revision_relation(relation)
    return CaptureOutcome(source, raw_blob, capture, document, relation, True)


def capture_identity(
    request: CaptureRequest,
    identity_policy: SourceIdentityPolicy,
) -> CaptureIdentity:
    """Return capture IDs without mutating the Ledger or Archive."""

    canonical_key = identity_policy.canonical_key(request.identity_hint)
    if not canonical_key:
        raise ValueError("Source identity policy returned an empty canonical key.")
    source_id = _id("src", identity_policy.policy_id, canonical_key)
    content_digest = hashlib.sha256(request.payload).hexdigest()
    return CaptureIdentity(
        source_id=source_id,
        raw_blob_id=f"blb_{content_digest}",
        source_capture_id=_id("cap", source_id, request.idempotency_key),
        document_id=_id("doc", source_id, request.provider_version or "", content_digest),
        content_digest=content_digest,
    )


def _validate_revision_request(request: CaptureRequest, identity: CaptureIdentity) -> None:
    if (request.revision_of_document_id is None) != (request.revision_type is None):
        raise ValueError("Document revision requires both a prior Document and a revision type.")
    if request.revision_of_document_id == identity.document_id:
        raise ValueError("Document revision cannot relate a Document to itself.")


def _validate_provider_version_conflict(
    request: CaptureRequest,
    identity: CaptureIdentity,
    ledger_repository: CaptureLedger,
) -> None:
    if request.provider_item_id is None or request.provider_version is None:
        return
    for document in ledger_repository.list_documents():
        if (
            document.source_id == identity.source_id
            and document.provider_version == request.provider_version
            and document.content_sha256 != identity.content_digest
        ):
            raise ValueError("Provider item/version conflicts with previously captured bytes.")


def _requested_relation(
    request: CaptureRequest, identity: CaptureIdentity
) -> DocumentRevisionRelation | None:
    if request.revision_of_document_id is None or request.revision_type is None:
        return None
    return DocumentRevisionRelation(
        id=_id("drv", request.revision_of_document_id, identity.document_id, request.revision_type),
        earlier_document_id=request.revision_of_document_id,
        later_document_id=identity.document_id,
        relation_type=request.revision_type,
        basis="capture_request",
        recorded_at=request.transaction_time,
    )


def _find_requested_relation(
    request: CaptureRequest,
    identity: CaptureIdentity,
    ledger_repository: CaptureLedger,
) -> DocumentRevisionRelation | None:
    relation = _requested_relation(request, identity)
    if relation is None:
        return None
    return next(
        (
            existing
            for existing in ledger_repository.list_document_revision_relations()
            if existing.id == relation.id
        ),
        None,
    )


def _is_idempotent_retry(
    *,
    request: CaptureRequest,
    source: Source,
    raw_blob: RawBlob,
    capture: SourceCapture,
    document: Document,
    relation: DocumentRevisionRelation | None,
    ledger_repository: CaptureLedger,
) -> bool:
    expected_relation = _find_requested_relation_from_relation(relation, ledger_repository)
    return (
        source.source_type == request.identity_hint.source_type
        and source.title == request.identity_hint.title
        and source.uri == request.identity_hint.uri
        and source.published_at == request.publication_time
        and raw_blob.hash_algorithm == "sha256"
        and raw_blob.digest == hashlib.sha256(request.payload).hexdigest()
        and raw_blob.byte_length == len(request.payload)
        and raw_blob.media_type == request.media_type
        and raw_blob.storage_locator == request.storage_locator
        and capture.idempotency_key == request.idempotency_key
        and capture.retrieval_method == request.retrieval_method
        and capture.requested_uri == request.requested_uri
        and capture.canonical_uri == request.canonical_uri
        and capture.request_metadata == request.request_metadata
        and capture.response_metadata == request.response_metadata
        and capture.provider_item_id == request.provider_item_id
        and capture.provider_version == request.provider_version
        and capture.rights_profile_id == request.rights_profile_id
        and capture.embargo_until == request.embargo_until
        and document.source_id == source.id
        and document.content_sha256 == raw_blob.digest
        and document.provider_version == request.provider_version
        and document.publication_time == request.publication_time
        and document.provider_update_time == request.provider_update_time
        and document.version_kind == request.version_kind
        and document.extracted_text_path == request.extracted_text_locator
        and _same_revision_relation(expected_relation, relation)
    )


def _find_requested_relation_from_relation(
    relation: DocumentRevisionRelation | None,
    ledger_repository: CaptureLedger,
) -> DocumentRevisionRelation | None:
    if relation is None:
        return None
    return next(
        (
            existing
            for existing in ledger_repository.list_document_revision_relations()
            if existing.id == relation.id
        ),
        None,
    )


def _same_revision_relation(
    existing: DocumentRevisionRelation | None,
    requested: DocumentRevisionRelation | None,
) -> bool:
    if existing is None or requested is None:
        return existing is requested
    return (
        existing.id == requested.id
        and existing.earlier_document_id == requested.earlier_document_id
        and existing.later_document_id == requested.later_document_id
        and existing.relation_type == requested.relation_type
        and existing.basis == requested.basis
    )


def _would_create_revision_cycle(ledger: CaptureLedger, earlier_id: str, later_id: str) -> bool:
    frontier = [later_id]
    visited: set[str] = set()
    while frontier:
        current = frontier.pop()
        if current == earlier_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        frontier.extend(
            relation.later_document_id
            for relation in ledger.list_document_revision_relations()
            if relation.earlier_document_id == current
        )
    return False


def _digest(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()


def _id(prefix: str, *parts: object) -> str:
    return f"{prefix}_{_digest(*(str(part) for part in parts))[:HASH_ID_LENGTH]}"
