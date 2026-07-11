from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    CaptureRequest,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    capture_source,
)
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

NOW = datetime(2026, 7, 11, tzinfo=UTC)


class FakeCaptureLedger:
    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.blobs: dict[str, RawBlob] = {}
        self.captures: dict[str, SourceCapture] = {}
        self.documents: dict[str, Document] = {}
        self.relations: dict[str, DocumentRevisionRelation] = {}

    def get_source(self, record_id: str) -> Source | None:
        return self.sources.get(record_id)

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_source_capture(self, record_id: str) -> SourceCapture | None:
        return self.captures.get(record_id)

    def list_document_revision_relations(self) -> tuple[DocumentRevisionRelation, ...]:
        return tuple(self.relations.values())

    def save_source(self, record: Source) -> None:
        self.sources[record.id] = record

    def save_raw_blob(self, record: RawBlob) -> None:
        self.blobs[record.id] = record

    def save_source_capture(self, record: SourceCapture) -> None:
        self.captures[record.id] = record

    def save_document(self, record: Document) -> None:
        self.documents[record.id] = record

    def save_document_revision_relation(self, record: DocumentRevisionRelation) -> None:
        self.relations[record.id] = record


def request(payload: bytes, key: str, **changes: object) -> CaptureRequest:
    values: dict[str, object] = {
        "identity_hint": SourceIdentityHint(SourceType.ARTICLE, "Article", "publisher:item-1"),
        "payload": payload,
        "media_type": "text/plain",
        "storage_locator": f"raw/{key}",
        "idempotency_key": key,
        "retrieval_method": "fixture",
        "requested_uri": "https://example.test/item-1",
        "canonical_uri": "https://example.test/item-1",
        "provider_item_id": "item-1",
        "provider_version": key,
        "version_kind": DocumentVersionKind.ORIGINAL,
        "publication_time": NOW,
        "provider_update_time": NOW,
        "captured_at": NOW,
        "transaction_time": NOW,
        "rights_profile_id": "rights-1",
        "embargo_until": None,
        "request_metadata": {},
        "response_metadata": {},
    }
    values.update(changes)
    return CaptureRequest(**values)  # type: ignore[arg-type]


def test_capture_preserves_source_identity_and_versions() -> None:
    ledger = FakeCaptureLedger()
    policy = StableSourceIdentityPolicy()
    original = capture_source(request(b"original", "v1"), ledger, policy)
    retry = capture_source(request(b"original", "v1"), ledger, policy)
    update = capture_source(
        request(
            b"updated",
            "v2",
            version_kind=DocumentVersionKind.UPDATE,
            revision_of_document_id=original.document.id,
            revision_type=DocumentRevisionType.UPDATES,
        ),
        ledger,
        policy,
    )
    correction = capture_source(
        request(
            b"corrected",
            "v3",
            version_kind=DocumentVersionKind.CORRECTION,
            revision_of_document_id=update.document.id,
            revision_type=DocumentRevisionType.CORRECTS,
        ),
        ledger,
        policy,
    )
    withdrawal = capture_source(
        request(
            b"withdrawn",
            "v4",
            version_kind=DocumentVersionKind.WITHDRAWAL,
            revision_of_document_id=correction.document.id,
            revision_type=DocumentRevisionType.WITHDRAWS,
        ),
        ledger,
        policy,
    )
    assert retry.created is False
    assert len(ledger.sources) == 1 and len(ledger.documents) == 4 and len(ledger.captures) == 4
    assert len(ledger.relations) == 3
    assert withdrawal.source.id == original.source.id


def test_capture_rejects_conflicting_retry() -> None:
    ledger = FakeCaptureLedger()
    policy = StableSourceIdentityPolicy()
    capture_source(request(b"original", "v1"), ledger, policy)
    with pytest.raises(ValueError, match="idempotency conflict"):
        capture_source(request(b"different", "v1"), ledger, policy)
