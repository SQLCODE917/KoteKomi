import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import PdfParseInput
from kotekomi_domain import Document

NOW = datetime(2026, 7, 11, tzinfo=UTC)
FIXTURE_PDF = (
    Path(__file__).parent / "fixtures/pdf/2025-community-health-improvement-plan-press-release.pdf"
)


def test_adapter_package_does_not_eagerly_import_docling() -> None:
    import kotekomi_adapters

    assert kotekomi_adapters.LocalArchiveStore is not None
    assert kotekomi_adapters.DoclingPdfParser is DoclingPdfParser
    assert "docling.document_converter" not in sys.modules


def test_source_preflight_establishes_the_page_denominator_before_docling() -> None:
    from kotekomi_adapters import docling_pdf_parser

    mixed_pdf = FIXTURE_PDF.parent / "mixed/mixed_born_digital_scan_v1.pdf"
    preflight = docling_pdf_parser.preflight_pdf_source(mixed_pdf.read_bytes(), "fixture")

    assert preflight.page_count == 3
    assert tuple(page.page_index for page in preflight.pages) == (1, 2, 3)
    assert tuple(page.image_coverage for page in preflight.pages) == (
        0.0,
        1.0,
        0.0011883541295306002,
    )
    assert preflight.preflight_tool == "poppler_pdf_preflight"
    assert preflight.preflight_tool_version


def test_docling_parser_raises_when_docling_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kotekomi_adapters import docling_pdf_parser

    def fail_to_load() -> tuple[object, object, object, object, object]:
        raise RuntimeError("simulated Docling startup failure")

    raw_pdf = FIXTURE_PDF.read_bytes()
    document = Document(
        id="doc_pdf_fixture",
        source_id="src_pdf_fixture",
        content_sha256=hashlib.sha256(raw_pdf).hexdigest(),
    )
    monkeypatch.setattr(docling_pdf_parser, "_load_docling_components", fail_to_load)
    monkeypatch.setenv("KOTEKOMI_DOCLING_WORKER", "1")

    with pytest.raises(RuntimeError, match="Docling conversion failed"):
        DoclingPdfParser(DoclingPdfParserConfig()).parse(
            PdfParseInput(document, raw_pdf, "pdf_policy_v1", "ptf_fixture", NOW)
        )


@pytest.mark.parametrize(
    ("exception_name", "expected_reason"),
    (
        (
            "SecurityError",
            "PDF source is inaccessible under the configured security policy.",
        ),
        (
            "OperationNotAllowed",
            "PDF source access is not permitted by the configured policy.",
        ),
        (
            "DocumentLoadError",
            "PDF source cannot be loaded by the configured parser.",
        ),
    ),
)
def test_docling_parser_returns_a_typed_blocked_result_for_source_conditions(
    monkeypatch: pytest.MonkeyPatch,
    exception_name: str,
    expected_reason: str,
) -> None:
    from docling import exceptions
    from kotekomi_adapters import docling_pdf_parser

    def raise_source_condition() -> tuple[object, object, object, object, object]:
        raise getattr(exceptions, exception_name)("fixture source condition")

    raw_pdf = FIXTURE_PDF.read_bytes()
    document = Document(
        id="doc_pdf_fixture",
        source_id="src_pdf_fixture",
        content_sha256=hashlib.sha256(raw_pdf).hexdigest(),
    )
    monkeypatch.setattr(docling_pdf_parser, "_load_docling_components", raise_source_condition)
    monkeypatch.setenv("KOTEKOMI_DOCLING_WORKER", "1")

    result = DoclingPdfParser(DoclingPdfParserConfig()).parse(
        PdfParseInput(document, raw_pdf, "pdf_policy_v1", "ptf_fixture", NOW)
    )

    assert result.representation_bundle is None
    assert result.blocking_reasons == (expected_reason,)
    assert result.preflight.warnings == ("source_access_blocked", expected_reason)
