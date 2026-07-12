"""Docling implementation of the PDF parser Port.

This adapter deliberately publishes a blocked representation until its rich Docling
layout graph is mapped into canonical nodes, tables, and source regions. It never
relabels Docling's Markdown export as evidence-safe structure.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from typing import TYPE_CHECKING, Any

from kotekomi_application.pdf_ingest import (
    PdfDocumentParser,
    PdfPagePreflight,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
    PdfProcessorIdentity,
)

if TYPE_CHECKING:
    from docling_core.types.doc.document import DoclingDocument
from kotekomi_application.representation_identity import deterministic_representation_id
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
    enable_ocr: bool = False
    enable_table_structure: bool = True


class DoclingPdfParser(PdfDocumentParser):
    """Convert PDF bytes with pinned Docling settings and fail closed on structure."""

    def __init__(self, config: DoclingPdfParserConfig) -> None:
        self._config = config

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        parser_version = _docling_version()
        configuration = {
            "enable_ocr": self._config.enable_ocr,
            "enable_table_structure": self._config.enable_table_structure,
            "policy_id": policy_id,
        }
        config_digest = hashlib.sha256(
            json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return PdfProcessorIdentity("docling", parser_version, config_digest, "1")

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        parser_version = _docling_version()
        try:
            (
                document_stream_type,
                input_format,
                pdf_pipeline_options_type,
                document_converter_type,
                pdf_format_option_type,
            ) = _load_docling_components()
            pipeline_options = pdf_pipeline_options_type()
            pipeline_options.do_ocr = self._config.enable_ocr
            pipeline_options.do_table_structure = self._config.enable_table_structure
            converter = document_converter_type(
                allowed_formats=[input_format.PDF],
                format_options={
                    input_format.PDF: pdf_format_option_type(pipeline_options=pipeline_options),
                },
            )
            conversion = converter.convert(
                document_stream_type(
                    name=f"{parse_input.document.id}.pdf",
                    stream=BytesIO(parse_input.raw_bytes),
                ),
                raises_on_error=False,
            )
            blocking_reasons = _conversion_blocking_reasons(conversion)
            if blocking_reasons:
                return PdfParseResult(
                    preflight=_blocked_preflight(parser_version, blocking_reasons),
                    representation_bundle=None,
                    blocking_reasons=blocking_reasons,
                )
            if _conversion_failed(conversion):
                raise RuntimeError("Docling conversion returned a processor failure status.")
            logical_text = conversion.document.export_to_markdown()
        except Exception as exc:
            blocked_result = _source_blocked_result(exc, parser_version)
            if blocked_result is not None:
                return blocked_result
            raise RuntimeError(f"Docling conversion failed: {type(exc).__name__}") from exc
        preflight = _preflight_from_document(conversion.document, parser_version)
        bundle = build_docling_blocked_bundle(
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


def _load_docling_components() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    """Load Docling only for an explicit PDF parse request."""

    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    return DocumentStream, InputFormat, PdfPipelineOptions, DocumentConverter, PdfFormatOption


def _docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Docling package version is unavailable for authoritative processing."
        ) from exc


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


def _conversion_blocking_reasons(conversion: Any) -> tuple[str, ...]:
    categories = {
        str(getattr(getattr(error, "category", None), "value", ""))
        for error in getattr(conversion, "errors", ())
    }
    reasons: list[str] = []
    if "policy" in categories:
        reasons.append("PDF source is blocked by the configured extraction policy.")
    if "source_unavailable" in categories:
        reasons.append("PDF source is inaccessible to the configured parser.")
    return tuple(reasons)


def _conversion_failed(conversion: Any) -> bool:
    status = str(getattr(getattr(conversion, "status", None), "value", ""))
    return status not in {"success", "partial_success"}


def _source_blocked_result(
    error: Exception,
    parser_version: str,
) -> PdfParseResult | None:
    try:
        from docling.exceptions import DocumentLoadError, OperationNotAllowed, SecurityError
    except ImportError:
        return None
    if isinstance(error, SecurityError):
        reasons = ("PDF source is inaccessible under the configured security policy.",)
    elif isinstance(error, OperationNotAllowed):
        reasons = ("PDF source access is not permitted by the configured policy.",)
    elif isinstance(error, DocumentLoadError):
        reasons = ("PDF source cannot be loaded by the configured parser.",)
    else:
        return None
    return PdfParseResult(
        preflight=_blocked_preflight(parser_version, reasons),
        representation_bundle=None,
        blocking_reasons=reasons,
    )


def _blocked_preflight(parser_version: str, reasons: tuple[str, ...]) -> PdfPreflight:
    return PdfPreflight(
        parser_name="docling",
        parser_version=parser_version,
        encrypted=False,
        page_count=0,
        pages=(),
        warnings=("source_access_blocked", *reasons),
    )


def build_docling_blocked_bundle(
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
    representation_id = deterministic_representation_id(parse_input.processing_task_fingerprint_id)
    representation_key = representation_id.removeprefix("rep_")
    text_view_id = f"tvw_{representation_key}_logical"
    node_id = f"nod_{representation_key}_document"
    quality_id = f"pqr_{representation_key}_quality_v1"
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
        processing_task_fingerprint_id=parse_input.processing_task_fingerprint_id,
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
