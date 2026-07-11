"""Local file Source ingest use case."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from kotekomi_domain import (
    Document,
    DocumentVersionKind,
    ProvenanceActivity,
    RawBlob,
    Source,
    SourceCapture,
    SourceType,
)

from kotekomi_application.ports import ArchiveObject, ArchiveStore, StagedArchiveObject

SUPPORTED_TEXT_SUFFIXES = frozenset({".md", ".txt"})
HASH_ID_LENGTH = 24
MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


class SourceFileLedger(Protocol):
    def get_source(self, record_id: str) -> Source | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...
    def save_source(self, record: Source) -> None: ...
    def save_raw_blob(self, record: RawBlob) -> None: ...
    def save_source_capture(self, record: SourceCapture) -> None: ...
    def save_document(self, record: Document) -> None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...


@dataclass(frozen=True)
class SourceFileIngestInput:
    local_file_path: str
    filename: str
    raw_bytes: bytes
    ingested_at: datetime


@dataclass(frozen=True)
class SourceFileIngestResult:
    source_id: str
    document_id: str
    provenance_activity_id: str
    raw_path: str
    extracted_text_path: str
    created: bool


def add_source_from_file(
    ingest_input: SourceFileIngestInput,
    archive_store: ArchiveStore,
    ledger_repository: SourceFileLedger,
) -> SourceFileIngestResult:
    suffix = Path(ingest_input.filename).suffix.lower()
    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_TEXT_SUFFIXES))
        raise ValueError(
            f"Unsupported Source file suffix {suffix!r}; supported suffixes: {supported}"
        )

    content_sha256 = hashlib.sha256(ingest_input.raw_bytes).hexdigest()
    short_hash = content_sha256[:HASH_ID_LENGTH]
    source_id = f"src_{short_hash}"
    document_id = f"doc_{short_hash}"
    provenance_activity_id = f"prv_{short_hash}"
    raw_blob_id = f"blb_{short_hash}"
    source_capture_id = f"cap_{short_hash}"

    existing_source = ledger_repository.get_source(source_id)
    existing_document = ledger_repository.get_document(document_id)
    existing_provenance = ledger_repository.get_provenance_activity(provenance_activity_id)
    if existing_source and existing_document and existing_provenance:
        return SourceFileIngestResult(
            source_id=source_id,
            document_id=document_id,
            provenance_activity_id=provenance_activity_id,
            raw_path=existing_document.raw_path,
            extracted_text_path=existing_document.extracted_text_path or "",
            created=False,
        )

    extracted_text = ingest_input.raw_bytes.decode("utf-8")
    source_type = infer_source_type(extracted_text)
    source_title = extract_source_title(ingest_input.filename, extracted_text)
    published_at = parse_dateline_date(extracted_text)
    source = Source(
        id=source_id,
        source_type=source_type,
        title=source_title,
        uri=ingest_input.local_file_path,
        published_at=published_at,
        created_at=ingest_input.ingested_at,
        updated_at=ingest_input.ingested_at,
    )

    staged_objects: list[StagedArchiveObject] = []
    promoted_objects: list[ArchiveObject] = []
    try:
        staged_raw = archive_store.stage_raw_source(source_id, ingest_input.raw_bytes)
        staged_objects.append(staged_raw)
        staged_text = archive_store.stage_document_text(document_id, extracted_text)
        staged_objects.append(staged_text)
        document = Document(
            id=document_id,
            source_id=source_id,
            raw_path=staged_raw.final_object.relative_path,
            extracted_text_path=staged_text.final_object.relative_path,
            content_sha256=content_sha256,
            created_from_capture_id=source_capture_id,
            publication_time=published_at,
            version_kind=DocumentVersionKind.ORIGINAL,
            created_at=ingest_input.ingested_at,
            updated_at=ingest_input.ingested_at,
        )
        raw_object = archive_store.promote_staged_object(staged_raw)
        promoted_objects.append(raw_object)
        text_object = archive_store.promote_staged_object(staged_text)
        promoted_objects.append(text_object)
        provenance_activity = ProvenanceActivity(
            id=provenance_activity_id,
            activity_type="source_file_ingest",
            agent="kotekomi",
            input_ids=(ingest_input.local_file_path,),
            output_ids=(source_id, raw_blob_id, source_capture_id, document_id),
            occurred_at=ingest_input.ingested_at,
        )

        raw_blob = RawBlob(
            id=raw_blob_id,
            hash_algorithm="sha256",
            digest=content_sha256,
            byte_length=len(ingest_input.raw_bytes),
            media_type="text/markdown" if suffix == ".md" else "text/plain",
            storage_locator=raw_object.relative_path,
            created_at=ingest_input.ingested_at,
        )
        source_capture = SourceCapture(
            id=source_capture_id,
            source_id=source_id,
            blob_id=raw_blob_id,
            idempotency_key=content_sha256,
            retrieval_method="local_file",
            requested_uri=ingest_input.local_file_path,
            canonical_uri=ingest_input.local_file_path,
            captured_at=ingest_input.ingested_at,
            transaction_time=ingest_input.ingested_at,
        )
        ledger_repository.save_source(source)
        ledger_repository.save_raw_blob(raw_blob)
        ledger_repository.save_source_capture(source_capture)
        ledger_repository.save_document(document)
        ledger_repository.save_provenance_activity(provenance_activity)
    except Exception:
        _cleanup_archive_objects(archive_store, promoted_objects, staged_objects)
        raise

    return SourceFileIngestResult(
        source_id=source_id,
        document_id=document_id,
        provenance_activity_id=provenance_activity_id,
        raw_path=raw_object.relative_path,
        extracted_text_path=text_object.relative_path,
        created=True,
    )


def cleanup_created_source_archive_objects(
    *,
    archive_store: ArchiveStore,
    raw_path: str,
    extracted_text_path: str,
) -> None:
    archive_store.delete_object(raw_path)
    archive_store.delete_object(extracted_text_path)


def _cleanup_archive_objects(
    archive_store: ArchiveStore,
    promoted_objects: list[ArchiveObject],
    staged_objects: list[StagedArchiveObject],
) -> None:
    for archive_object in reversed(promoted_objects):
        archive_store.delete_object(archive_object.relative_path)
    for staged_object in reversed(staged_objects):
        archive_store.delete_object(staged_object.staged_relative_path)


def extract_source_title(filename: str, extracted_text: str) -> str:
    for line in extracted_text.splitlines():
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            if title:
                return title
    return Path(filename).stem


def infer_source_type(extracted_text: str) -> SourceType:
    for line in extracted_text.splitlines():
        if line.strip().lower() == "source type: synthetic news fixture":
            return SourceType.ARTICLE
    return SourceType.MANUAL_FILE


def parse_dateline_date(extracted_text: str) -> datetime | None:
    for line in extracted_text.splitlines():
        if not line.startswith("Dateline: "):
            continue
        _, _, dateline = line.partition(": ")
        _, separator, date_text = dateline.partition(", ")
        if not separator:
            raise ValueError("Dateline must include a location followed by a comma.")
        parts = date_text.split()
        if len(parts) != 3:
            raise ValueError("Dateline date must use 'Month D, YYYY' format.")
        month_name, day_text, year_text = parts
        month = MONTHS.get(month_name)
        if month is None:
            raise ValueError(f"Dateline month is not recognized: {month_name}")
        try:
            day = int(day_text.rstrip(","))
            year = int(year_text)
        except ValueError as exc:
            raise ValueError("Dateline day and year must be numeric.") from exc
        return datetime(year, month, day, tzinfo=UTC)
    return None
