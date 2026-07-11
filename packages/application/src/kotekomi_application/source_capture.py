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


class CaptureLedger(Protocol):
    def get_source(self, record_id: str) -> Source | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_source_capture(self, record_id: str) -> SourceCapture | None: ...
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
    canonical_key = identity_policy.canonical_key(request.identity_hint)
    if not canonical_key:
        raise ValueError("Source identity policy returned an empty canonical key.")
    source_id = _id("src", identity_policy.policy_id, canonical_key)
    digest = hashlib.sha256(request.payload).hexdigest()
    raw_blob_id = f"blb_{digest[:HASH_ID_LENGTH]}"
    request_fingerprint = _digest(source_id, request.idempotency_key, request.requested_uri or "")
    capture_id = _id("cap", source_id, request_fingerprint)
    document_id = _id("doc", source_id, request.provider_version or "", digest)
    existing_capture = ledger_repository.get_source_capture(capture_id)
    if existing_capture is not None:
        existing_document = ledger_repository.get_document(document_id)
        if existing_capture.blob_id != raw_blob_id or existing_document is None:
            raise ValueError("Capture idempotency conflict.")
        source = ledger_repository.get_source(source_id)
        if source is None:
            raise ValueError("Capture references a missing Source.")
        return CaptureOutcome(
            source,
            RawBlob(
                id=raw_blob_id,
                hash_algorithm="sha256",
                digest=digest,
                byte_length=len(request.payload),
                media_type=request.media_type,
                storage_locator=request.storage_locator,
                created_at=request.transaction_time,
            ),
            existing_capture,
            existing_document,
            None,
            False,
        )
    if request.revision_type is None and request.revision_of_document_id is not None:
        raise ValueError("Document revision requires a revision type.")
    if request.revision_of_document_id is not None:
        earlier = ledger_repository.get_document(request.revision_of_document_id)
        if earlier is None or earlier.source_id != source_id:
            raise ValueError(
                "Document revision must reference an existing Document for the same Source."
            )
        if _would_create_revision_cycle(ledger_repository, earlier.id, document_id):
            raise ValueError("Document revision relation would create a cycle.")
    source = ledger_repository.get_source(source_id) or Source(
        id=source_id,
        source_type=request.identity_hint.source_type,
        title=request.identity_hint.title,
        uri=request.identity_hint.uri,
        published_at=request.publication_time,
        created_at=request.transaction_time,
        updated_at=request.transaction_time,
    )
    raw_blob = RawBlob(
        id=raw_blob_id,
        hash_algorithm="sha256",
        digest=digest,
        byte_length=len(request.payload),
        media_type=request.media_type,
        storage_locator=request.storage_locator,
        created_at=request.transaction_time,
    )
    capture = SourceCapture(
        id=capture_id,
        source_id=source_id,
        blob_id=raw_blob_id,
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
    document = Document(
        id=document_id,
        source_id=source_id,
        raw_path=request.storage_locator,
        content_sha256=digest,
        created_from_capture_id=capture_id,
        provider_version=request.provider_version,
        publication_time=request.publication_time,
        provider_update_time=request.provider_update_time,
        version_kind=request.version_kind,
        created_at=request.transaction_time,
        updated_at=request.transaction_time,
    )
    relation = None
    if request.revision_of_document_id is not None and request.revision_type is not None:
        relation = DocumentRevisionRelation(
            id=_id("drv", request.revision_of_document_id, document_id, request.revision_type),
            earlier_document_id=request.revision_of_document_id,
            later_document_id=document_id,
            relation_type=request.revision_type,
            basis="capture_request",
            recorded_at=request.transaction_time,
        )
    ledger_repository.save_source(source)
    ledger_repository.save_raw_blob(raw_blob)
    ledger_repository.save_source_capture(capture)
    ledger_repository.save_document(document)
    if relation is not None:
        ledger_repository.save_document_revision_relation(relation)
    return CaptureOutcome(source, raw_blob, capture, document, relation, True)


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
