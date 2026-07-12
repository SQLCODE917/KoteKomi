import hashlib
import sys
from datetime import UTC, datetime

import pytest
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import PdfParseInput
from kotekomi_domain import Document

NOW = datetime(2026, 7, 11, tzinfo=UTC)


def test_adapter_package_does_not_eagerly_import_docling() -> None:
    import kotekomi_adapters

    assert kotekomi_adapters.LocalArchiveStore is not None
    assert kotekomi_adapters.DoclingPdfParser is DoclingPdfParser
    assert "docling.document_converter" not in sys.modules


def test_docling_parser_raises_when_docling_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kotekomi_adapters import docling_pdf_parser

    def fail_to_load() -> tuple[object, object, object, object, object]:
        raise RuntimeError("simulated Docling startup failure")

    raw_pdf = b"%PDF-1.7\nfixture"
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

    raw_pdf = b"%PDF-1.7\nfixture"
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
