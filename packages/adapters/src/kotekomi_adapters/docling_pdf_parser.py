"""Docling implementation of the PDF parser Port.

This adapter deliberately publishes a blocked representation until its rich Docling
layout graph is mapped into canonical nodes, tables, and source regions. It never
relabels Docling's Markdown export as evidence-safe structure.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import version
from io import BytesIO

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import DoclingDocument
from kotekomi_application.pdf_ingest import (
    PdfDocumentParser,
    PdfPagePreflight,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
)
from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

HASH_ID_LENGTH = 24


@dataclass(frozen=True)
class DoclingPdfParserConfig:
    code_revision: str = "unknown"
    enable_ocr: bool = False
    enable_table_structure: bool = True


class DoclingPdfParser(PdfDocumentParser):
    """Convert PDF bytes with pinned Docling settings and fail closed on structure."""

    def __init__(self, config: DoclingPdfParserConfig | None = None) -> None:
        self._config = config or DoclingPdfParserConfig()

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        parser_version = version("docling")
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self._config.enable_ocr
        pipeline_options.do_table_structure = self._config.enable_table_structure
        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            },
        )
        try:
            conversion = converter.convert(
                DocumentStream(
                    name=f"{parse_input.document.id}.pdf",
                    stream=BytesIO(parse_input.raw_bytes),
                )
            )
            logical_text = conversion.document.export_to_markdown()
        except Exception as exc:
            return PdfParseResult(
                preflight=PdfPreflight(
                    parser_name="docling",
                    parser_version=parser_version,
                    encrypted=False,
                    page_count=0,
                    pages=(),
                    warnings=(f"docling_error:{type(exc).__name__}",),
                ),
                representation_bundle=None,
                blocking_reasons=(f"Docling PDF conversion failed: {type(exc).__name__}",),
            )
        preflight = _preflight_from_document(conversion.document, parser_version)
        bundle = _blocked_markdown_bundle(
            parse_input=parse_input,
            logical_text=logical_text,
            parser_version=parser_version,
            config=self._config,
        )
        return PdfParseResult(
            preflight=preflight,
            representation_bundle=bundle,
            blocking_reasons=(
                "Docling layout graph mapping to canonical nodes and regions is not complete.",
            ),
        )


def _preflight_from_document(document: DoclingDocument, parser_version: str) -> PdfPreflight:
    pages = tuple(
        PdfPagePreflight(
            page_index=page_number,
            width=page.size.width,
            height=page.size.height,
            rotation=0,
            embedded_text_character_count=0,
            warnings=("embedded_text_metrics_pending",),
        )
        for page_number, page in sorted(document.pages.items())
    )
    return PdfPreflight(
        parser_name="docling",
        parser_version=parser_version,
        encrypted=False,
        page_count=len(pages),
        pages=pages,
        warnings=("embedded_text_metrics_pending",),
    )


def _blocked_markdown_bundle(
    *,
    parse_input: PdfParseInput,
    logical_text: str,
    parser_version: str,
    config: DoclingPdfParserConfig,
) -> DocumentRepresentationBundle:
    input_digest = hashlib.sha256(parse_input.raw_bytes).hexdigest()
    configuration = {
        "enable_ocr": config.enable_ocr,
        "enable_table_structure": config.enable_table_structure,
        "policy_id": parse_input.policy_id,
    }
    config_digest = hashlib.sha256(
        json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    representation_id = f"rep_{input_digest[:HASH_ID_LENGTH]}_docling"
    text_view_id = f"tvw_{input_digest[:HASH_ID_LENGTH]}_docling"
    node_id = f"nod_{input_digest[:HASH_ID_LENGTH]}_docling"
    quality_id = f"pqr_{input_digest[:HASH_ID_LENGTH]}_docling"
    text_digest = hashlib.sha256(logical_text.encode()).hexdigest()
    text_view = TextView(
        id=text_view_id,
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=text_digest,
        text=logical_text,
        normalization_policy="docling_markdown_v1",
    )
    root = DocumentNode(
        id=node_id,
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view_id,
        start_char=0,
        end_char=len(logical_text),
        text=logical_text,
    )
    quality_report = ParseQualityReport(
        id=quality_id,
        representation_id=representation_id,
        metric_values={"logical_text_char_count": len(logical_text)},
        issues=("canonical_layout_mapping_pending",),
        analyzability=RepresentationAnalyzability.BLOCKED,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=parse_input.document.id,
        parser_name="docling",
        parser_version=parser_version,
        parser_config_digest=config_digest,
        code_revision=config.code_revision,
        input_blob_digest=input_digest,
        canonical_output_digest="0" * 64,
        created_at=parse_input.parsed_at,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root,),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root,),
        quality_report=quality_report,
    )
