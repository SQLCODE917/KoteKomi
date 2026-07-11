from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    PdfDocumentParser,
    PdfIngestInput,
    PdfIngestLedger,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
    ingest_pdf,
)
from kotekomi_domain import Document

NOW = datetime(2026, 7, 11, tzinfo=UTC)
RAW_PDF = b"%PDF-1.7\nfixture"


class FakePdfParser:
    def parse(self, _parse_input: PdfParseInput) -> PdfParseResult:
        return PdfParseResult(
            preflight=PdfPreflight(
                parser_name="fake_pdf",
                parser_version="1",
                encrypted=False,
                page_count=0,
                pages=(),
            ),
            representation_bundle=None,
            blocking_reasons=("fixture parser blocked",),
        )


class FakePdfLedger:
    def __init__(self) -> None:
        import hashlib

        self.document = Document(
            id="doc_pdf_fixture",
            source_id="src_pdf_fixture",
            content_sha256=hashlib.sha256(RAW_PDF).hexdigest(),
        )

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None


def test_ingest_pdf_returns_typed_blocked_outcome_without_publishing_representation() -> None:
    outcome = ingest_pdf(
        PdfIngestInput("doc_pdf_fixture", RAW_PDF, "pdf_policy_v1", NOW),
        cast(PdfIngestLedger, FakePdfLedger()),
        cast(PdfDocumentParser, FakePdfParser()),
    )

    assert outcome.representation_id is None
    assert outcome.provenance_activity_id is None
    assert outcome.blocking_reasons == ("fixture parser blocked",)


def test_ingest_pdf_rejects_bytes_that_do_not_match_the_immutable_document() -> None:
    with pytest.raises(ValueError, match="content_sha256"):
        ingest_pdf(
            PdfIngestInput("doc_pdf_fixture", b"wrong", "pdf_policy_v1", NOW),
            cast(PdfIngestLedger, FakePdfLedger()),
            cast(PdfDocumentParser, FakePdfParser()),
        )
