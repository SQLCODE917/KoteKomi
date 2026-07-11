"""PDF ingestion use case over a tool-neutral, structure-preserving parser Port."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    Document,
    DocumentRepresentationBundle,
    ProvenanceActivity,
)

from kotekomi_application.representation_identity import DocumentRepresentationBundleLedger

HASH_ID_LENGTH = 24
PDF_INGEST_ACTIVITY = "pdf_document_ingest"


@dataclass(frozen=True)
class PdfPagePreflight:
    page_index: int
    width: float
    height: float
    rotation: int
    embedded_text_character_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfPreflight:
    parser_name: str
    parser_version: str
    encrypted: bool
    page_count: int
    pages: tuple[PdfPagePreflight, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfParseInput:
    document: Document
    raw_bytes: bytes
    policy_id: str
    parsed_at: datetime


@dataclass(frozen=True)
class PdfParseResult:
    preflight: PdfPreflight
    representation_bundle: DocumentRepresentationBundle | None
    blocking_reasons: tuple[str, ...] = ()


class PdfDocumentParser(Protocol):
    def parse(self, parse_input: PdfParseInput) -> PdfParseResult: ...


class PdfIngestLedger(DocumentRepresentationBundleLedger, Protocol):
    def get_document(self, record_id: str) -> Document | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...


@dataclass(frozen=True)
class PdfIngestInput:
    document_id: str
    raw_bytes: bytes
    policy_id: str
    ingested_at: datetime


@dataclass(frozen=True)
class PdfIngestOutcome:
    document_id: str
    preflight: PdfPreflight
    representation_id: str | None
    provenance_activity_id: str | None
    blocking_reasons: tuple[str, ...]


def ingest_pdf(
    ingest_input: PdfIngestInput,
    ledger_repository: PdfIngestLedger,
    parser: PdfDocumentParser,
) -> PdfIngestOutcome:
    document = ledger_repository.get_document(ingest_input.document_id)
    if document is None:
        raise ValueError(f"Document not found: {ingest_input.document_id}")
    actual_digest = hashlib.sha256(ingest_input.raw_bytes).hexdigest()
    if actual_digest != document.content_sha256:
        raise ValueError("PDF bytes do not match the immutable Document content_sha256.")
    parse_result = parser.parse(
        PdfParseInput(
            document=document,
            raw_bytes=ingest_input.raw_bytes,
            policy_id=ingest_input.policy_id,
            parsed_at=ingest_input.ingested_at,
        )
    )
    bundle = parse_result.representation_bundle
    if bundle is None:
        return PdfIngestOutcome(
            document_id=document.id,
            preflight=parse_result.preflight,
            representation_id=None,
            provenance_activity_id=None,
            blocking_reasons=parse_result.blocking_reasons,
        )
    if bundle.representation.document_id != document.id:
        raise ValueError("PDF parser returned a representation for a different Document.")
    provenance_activity_id = _provenance_id(
        document.id, bundle.representation.id, ingest_input.policy_id
    )
    provenance = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=PDF_INGEST_ACTIVITY,
        agent=parse_result.preflight.parser_name,
        input_ids=(document.id, ingest_input.policy_id),
        output_ids=(
            bundle.representation.id,
            *(view.id for view in bundle.text_views),
            *(node.id for node in bundle.nodes),
            *(region.id for region in bundle.source_regions),
            *(edge.id for edge in bundle.edges),
            bundle.quality_report.id,
        ),
        occurred_at=ingest_input.ingested_at,
    )
    ledger_repository.commit_document_representation_bundle(bundle)
    ledger_repository.save_provenance_activity(provenance)
    return PdfIngestOutcome(
        document_id=document.id,
        preflight=parse_result.preflight,
        representation_id=bundle.representation.id,
        provenance_activity_id=provenance_activity_id,
        blocking_reasons=parse_result.blocking_reasons,
    )


def _provenance_id(document_id: str, representation_id: str, policy_id: str) -> str:
    value = f"{document_id}:{representation_id}:{policy_id}:{PDF_INGEST_ACTIVITY}"
    return f"prv_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"
