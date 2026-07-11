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


def test_docling_parser_returns_a_typed_block_when_docling_load_fails(
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

    result = DoclingPdfParser(DoclingPdfParserConfig(code_revision="test")).parse(
        PdfParseInput(document, raw_pdf, "pdf_policy_v1", NOW)
    )

    assert result.representation_bundle is None
    assert result.preflight.warnings == ("docling_error:RuntimeError",)
    assert result.blocking_reasons == ("Docling PDF conversion failed: RuntimeError",)


def test_docling_bundle_identity_changes_with_its_parser_fingerprint() -> None:
    from kotekomi_adapters import docling_pdf_parser

    raw_pdf = b"%PDF-1.7\nfixture"
    parse_input = PdfParseInput(
        Document(
            id="doc_pdf_fixture",
            source_id="src_pdf_fixture",
            content_sha256=hashlib.sha256(raw_pdf).hexdigest(),
        ),
        raw_pdf,
        "pdf_policy_v1",
        NOW,
    )
    base = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input,
        logical_text="fixture",
        parser_version="1",
        config=DoclingPdfParserConfig(code_revision="base"),
    )
    changed_version = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input,
        logical_text="fixture",
        parser_version="2",
        config=DoclingPdfParserConfig(code_revision="base"),
    )
    changed_config = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input,
        logical_text="fixture",
        parser_version="1",
        config=DoclingPdfParserConfig(code_revision="base", enable_ocr=True),
    )
    changed_code = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input,
        logical_text="fixture",
        parser_version="1",
        config=DoclingPdfParserConfig(code_revision="changed"),
    )

    ids = {
        base.representation.id,
        changed_version.representation.id,
        changed_config.representation.id,
        changed_code.representation.id,
    }
    assert len(ids) == 4
    assert base.text_views[0].id.startswith(f"tvw_{base.representation.id.removeprefix('rep_')}")
