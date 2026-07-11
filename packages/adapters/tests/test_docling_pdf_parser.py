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

    with pytest.raises(RuntimeError, match="Docling conversion failed"):
        DoclingPdfParser(DoclingPdfParserConfig()).parse(
            PdfParseInput(document, raw_pdf, "pdf_policy_v1", "ptf_fixture", NOW)
        )


def test_docling_bundle_identity_derives_from_processing_task() -> None:
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
        "ptf_base",
        NOW,
    )
    base = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input,
        logical_text="fixture",
        parser_version="1",
        config=DoclingPdfParserConfig(),
    )
    changed_version = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input,
        logical_text="fixture",
        parser_version="2",
        config=DoclingPdfParserConfig(),
    )
    changed_config = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input,
        logical_text="fixture",
        parser_version="1",
        config=DoclingPdfParserConfig(enable_ocr=True),
    )
    changed_task = docling_pdf_parser.build_docling_blocked_bundle(
        parse_input=parse_input.__class__(
            parse_input.document,
            parse_input.raw_bytes,
            parse_input.policy_id,
            "ptf_changed",
            parse_input.parsed_at,
        ),
        logical_text="fixture",
        parser_version="1",
        config=DoclingPdfParserConfig(),
    )

    ids = {
        base.representation.id,
        changed_version.representation.id,
        changed_config.representation.id,
        changed_task.representation.id,
    }
    assert len(ids) == 2
    assert base.text_views[0].id.startswith(f"tvw_{base.representation.id.removeprefix('rep_')}")
