import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore, SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import (
    CaptureRequest,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    capture_identity,
    capture_source,
)
from kotekomi_domain import (
    DocumentRevisionRelation,
    DocumentRevisionType,
    DocumentVersionKind,
    SourceType,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)


def request(payload: bytes, key: str, **changes: object) -> CaptureRequest:
    values: dict[str, object] = {
        "identity_hint": SourceIdentityHint(SourceType.ARTICLE, "Article", "provider:item-1"),
        "payload": payload,
        "media_type": "text/plain",
        "storage_locator": f"sources/raw/blb_{hashlib.sha256(payload).hexdigest()}.bin",
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
        "embargo_until": NOW + timedelta(days=1),
        "request_metadata": {"request_id": key},
        "response_metadata": {"etag": key},
    }
    values.update(changes)
    return CaptureRequest(**values)  # type: ignore[arg-type]


def capture(
    ledger_path: Path,
    archive: LocalArchiveStore,
    capture_request: CaptureRequest,
):
    identity = capture_identity(capture_request, StableSourceIdentityPolicy())
    raw_path = archive.archive_root / capture_request.storage_locator
    if not raw_path.exists():
        archive.write_raw_source(identity.raw_blob_id, capture_request.payload)
    with sqlite_ledger_transaction(ledger_path) as repository:
        return capture_source(capture_request, repository, StableSourceIdentityPolicy())


def test_sqlite_capture_sequence_preserves_versions_and_retries(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()

    original = capture(ledger_path, archive, request(b"original", "v1"))
    retry = capture(ledger_path, archive, request(b"original", "v1"))
    update = capture(
        ledger_path,
        archive,
        request(
            b"updated",
            "v2",
            version_kind=DocumentVersionKind.UPDATE,
            revision_of_document_id=original.document.id,
            revision_type=DocumentRevisionType.UPDATES,
        ),
    )
    correction = capture(
        ledger_path,
        archive,
        request(
            b"corrected",
            "v3",
            version_kind=DocumentVersionKind.CORRECTION,
            revision_of_document_id=update.document.id,
            revision_type=DocumentRevisionType.CORRECTS,
        ),
    )
    withdrawal = capture(
        ledger_path,
        archive,
        request(
            b"withdrawn",
            "v4",
            version_kind=DocumentVersionKind.WITHDRAWAL,
            revision_of_document_id=correction.document.id,
            revision_type=DocumentRevisionType.WITHDRAWS,
        ),
    )

    assert retry.created is False
    assert retry.source_capture == original.source_capture
    assert retry.document == original.document
    assert original.raw_blob.id == f"blb_{original.raw_blob.digest}"
    assert archive.read_raw_source(original.raw_blob.id) == b"original"
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_sources()) == 1
        assert len(repository.list_raw_blobs()) == 4
        assert len(repository.list_source_captures()) == 4
        assert len(repository.list_capture_document_resolutions()) == 4
        assert (
            repository.get_capture_document_resolution(original.document_resolution.id)
            == original.document_resolution
        )
        assert len(repository.list_documents()) == 4
        assert repository.get_document(original.document.id) == original.document
        assert {
            relation.relation_type for relation in repository.list_document_revision_relations()
        } == {
            DocumentRevisionType.CORRECTS,
            DocumentRevisionType.UPDATES,
            DocumentRevisionType.WITHDRAWS,
        }
    assert withdrawal.source.id == original.source.id
    assert correction.source_capture.provider_item_id == "item-1"
    assert correction.source_capture.provider_version == "v3"
    assert correction.source_capture.captured_at == NOW
    assert correction.source_capture.transaction_time == NOW
    assert correction.source_capture.rights_profile_id == "rights-1"
    assert correction.source_capture.embargo_until == NOW + timedelta(days=1)
    assert correction.source_capture.response_metadata == {"etag": "v3"}
    assert correction.document.publication_time == NOW
    assert correction.document.provider_update_time == NOW


def test_sqlite_capture_conflict_rolls_back_without_partial_records(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    policy = StableSourceIdentityPolicy()
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture_source(request(b"original", "v1"), repository, policy)

    with pytest.raises(ValueError, match="idempotency conflict"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            capture_source(request(b"different", "v1"), repository, policy)

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_sources()) == 1
        assert len(repository.list_raw_blobs()) == 1
        assert len(repository.list_source_captures()) == 1
        assert len(repository.list_documents()) == 1


def test_sqlite_capture_rejects_a_revision_cycle_before_insert(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    policy = StableSourceIdentityPolicy()
    with sqlite_ledger_transaction(ledger_path) as repository:
        original = capture_source(request(b"original", "v1"), repository, policy)
    cycle_request = request(
        b"updated",
        "v2",
        version_kind=DocumentVersionKind.UPDATE,
        revision_of_document_id=original.document.id,
        revision_type=DocumentRevisionType.UPDATES,
    )
    future = capture_identity(cycle_request, policy)
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_document_revision_relation(
            DocumentRevisionRelation(
                id="drv_negative_fixture",
                earlier_document_id=future.document_id,
                later_document_id=original.document.id,
                relation_type=DocumentRevisionType.SUPERSEDES,
                basis="negative_fixture",
                recorded_at=NOW,
            )
        )

    with pytest.raises(ValueError, match="would create a cycle"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            capture_source(cycle_request, repository, policy)

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_raw_blobs()) == 1
        assert len(repository.list_source_captures()) == 1
        assert len(repository.list_documents()) == 1
