"""Docling implementation of the PDF parser Port for born-digital PDF layout."""
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedFunction=false

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import resource
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from kotekomi_application.pdf_ingest import (
    PdfDocumentParser,
    PdfExtractionPolicy,
    PdfPagePreflight,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
    PdfProcessorIdentity,
    PdfTransformationPayload,
)

if TYPE_CHECKING:
    from docling_core.types.doc.document import DoclingDocument
from kotekomi_application.representation_identity import deterministic_representation_id
from kotekomi_domain import (
    DocumentEdge,
    DocumentEdgeProvenanceKind,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    PdfExtractionPath,
    PdfTransformationType,
    RepresentationAnalyzability,
    SourceCoordinateSystem,
    SourceRegion,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

HASH_ID_LENGTH = 24


@dataclass(frozen=True)
class DoclingPdfParserConfig:
    enable_ocr: bool = True
    enable_table_structure: bool = False
    ocr_language: str = "english"
    ocr_render_scale: int = 2
    ocr_text_score: float = 0.5


@dataclass(frozen=True)
class _PageGeometry:
    page_number: int
    width: float
    height: float
    rotation: int


@dataclass(frozen=True)
class _LayoutRegion:
    page_number: int
    page_width: float
    page_height: float
    left: float
    top: float
    right: float
    bottom: float
    rotation_applied: int


@dataclass(frozen=True)
class _LayoutItem:
    text: str
    node_type: str
    regions: tuple[_LayoutRegion, ...]
    heading_level: int | None = None
    marker: str | None = None
    extraction_path: PdfExtractionPath = PdfExtractionPath.EMBEDDED
    confidence: float | None = None


class PdfSourcePreflightError(RuntimeError):
    """The source bytes cannot yield a trustworthy PDF page inventory."""


class PdfOcrNoUsableTextError(RuntimeError):
    def __init__(
        self,
        page_number: int,
        transformation_payloads: tuple[PdfTransformationPayload, ...],
    ) -> None:
        super().__init__(f"Selective OCR produced no usable text for page {page_number}.")
        self.page_number = page_number
        self.transformation_payloads = transformation_payloads


class DoclingPdfParser(PdfDocumentParser):
    """Convert PDF bytes with pinned Docling settings and fail closed on structure."""

    def __init__(self, config: DoclingPdfParserConfig) -> None:
        self._config = config

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        parser_version = _docling_version()
        configuration = _parser_configuration(self._config, policy_id)
        config_digest = hashlib.sha256(
            json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return PdfProcessorIdentity("docling", parser_version, config_digest, "4")

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        if os.environ.get("KOTEKOMI_DOCLING_WORKER") != "1":
            return _parse_with_large_stack_worker(parse_input, self._config)
        return self._parse_in_process(parse_input)

    def _parse_in_process(self, parse_input: PdfParseInput) -> PdfParseResult:
        parser_version = _docling_version()
        try:
            source_preflight = preflight_pdf_source(parse_input.raw_bytes, parser_version)
        except PdfSourcePreflightError as exc:
            reason = str(exc)
            return PdfParseResult(
                preflight=_blocked_preflight(
                    parser_version,
                    (reason,),
                    _pdf_version(parse_input.raw_bytes),
                    _pdf_is_encrypted(parse_input.raw_bytes),
                ),
                representation_bundle=None,
                blocking_reasons=(reason,),
            )
        extraction_policy = PdfExtractionPolicy(parse_input.policy_id)
        selected_ocr_pages = tuple(
            page.page_index
            for page in source_preflight.pages
            if extraction_policy.select_extraction_path(page) is PdfExtractionPath.OCR
        )
        if selected_ocr_pages and not self._config.enable_ocr:
            reason = "Selective OCR is required but disabled for pages: " + ",".join(
                str(page) for page in selected_ocr_pages
            )
            return PdfParseResult(
                preflight=replace(
                    source_preflight,
                    warnings=(*source_preflight.warnings, "selected_ocr_disabled"),
                ),
                representation_bundle=None,
                blocking_reasons=(reason,),
            )
        try:
            page_geometry = _page_geometry_from_preflight(source_preflight)
            if len(selected_ocr_pages) == source_preflight.page_count:
                embedded_items: tuple[_LayoutItem, ...] = ()
            else:
                (
                    document_stream_type,
                    input_format,
                    pdf_pipeline_options_type,
                    document_converter_type,
                    pdf_format_option_type,
                ) = _load_docling_components()
                pipeline_options = pdf_pipeline_options_type()
                pipeline_options.do_ocr = False
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
                        preflight=replace(
                            source_preflight,
                            warnings=tuple(
                                dict.fromkeys(
                                    (
                                        *source_preflight.warnings,
                                        "source_access_blocked",
                                        *blocking_reasons,
                                    )
                                )
                            ),
                        ),
                        representation_bundle=None,
                        blocking_reasons=blocking_reasons,
                    )
                if _conversion_failed(conversion):
                    raise RuntimeError("Docling conversion returned a processor failure status.")
                docling_page_geometry = tuple(
                    page
                    for page in _page_geometry_from_document(conversion.document)
                    if page.page_number not in selected_ocr_pages
                )
                embedded_page_geometry = tuple(
                    page for page in page_geometry if page.page_number not in selected_ocr_pages
                )
                _validate_docling_page_geometry(docling_page_geometry, embedded_page_geometry)
                embedded_items = tuple(
                    item
                    for item in _layout_items_from_document(conversion.document, page_geometry)
                    if item.regions[0].page_number not in selected_ocr_pages
                )
            ocr_items, transformation_payloads = _ocr_selected_pages(
                parse_input.raw_bytes,
                page_geometry,
                selected_ocr_pages,
                self._config,
            )
            layout_items = _finalize_layout_items(
                (*embedded_items, *ocr_items),
                page_geometry,
            )
        except PdfOcrNoUsableTextError as exc:
            reason = str(exc)
            return PdfParseResult(
                preflight=replace(
                    source_preflight,
                    warnings=(*source_preflight.warnings, "selected_ocr_no_usable_text"),
                ),
                representation_bundle=None,
                transformation_payloads=exc.transformation_payloads,
                blocking_reasons=(reason,),
            )
        except Exception as exc:
            blocked_result = _source_blocked_result(
                exc,
                source_preflight,
            )
            if blocked_result is not None:
                return blocked_result
            raise RuntimeError(f"Docling conversion failed: {type(exc).__name__}") from exc
        preflight = _preflight_from_layout(
            source_preflight,
            layout_items,
        )
        bundle = build_docling_representation_bundle(
            parse_input=parse_input,
            page_geometry=page_geometry,
            layout_items=layout_items,
            parser_version=parser_version,
            config=self._config,
        )

        return PdfParseResult(
            preflight=preflight,
            representation_bundle=bundle,
            transformation_payloads=transformation_payloads,
        )


@cache
def _load_docling_components() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    """Load Docling only for an explicit PDF parse request."""

    _raise_stack_limit_for_docling_import()

    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    return DocumentStream, InputFormat, PdfPipelineOptions, DocumentConverter, PdfFormatOption


def _raise_stack_limit_for_docling_import() -> None:
    """Avoid Pydantic schema-import stack exhaustion in Docling's recursive models."""
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_STACK)
    target_limit = 64 * 1024 * 1024
    if soft_limit == resource.RLIM_INFINITY or soft_limit >= target_limit:
        return
    if hard_limit != resource.RLIM_INFINITY and hard_limit < target_limit:
        target_limit = hard_limit
    resource.setrlimit(resource.RLIMIT_STACK, (target_limit, hard_limit))


def _parse_with_large_stack_worker(
    parse_input: PdfParseInput,
    config: DoclingPdfParserConfig,
) -> PdfParseResult:
    request = {
        "document": parse_input.document.model_dump(mode="json"),
        "raw_bytes_base64": base64.b64encode(parse_input.raw_bytes).decode("ascii"),
        "policy_id": parse_input.policy_id,
        "processing_task_fingerprint_id": parse_input.processing_task_fingerprint_id,
        "parsed_at": parse_input.parsed_at.isoformat(),
        "config": {
            "enable_ocr": config.enable_ocr,
            "enable_table_structure": config.enable_table_structure,
            "ocr_language": config.ocr_language,
            "ocr_render_scale": config.ocr_render_scale,
            "ocr_text_score": config.ocr_text_score,
        },
    }
    environment = {**os.environ, "KOTEKOMI_DOCLING_WORKER": "1"}
    completed: subprocess.CompletedProcess[bytes] | None = None
    for _ in range(5):
        completed = subprocess.run(
            [sys.executable, "-m", "kotekomi_adapters.docling_pdf_worker"],
            input=json.dumps(request, separators=(",", ":")).encode(),
            capture_output=True,
            check=False,
            env=environment,
            preexec_fn=_raise_stack_limit_for_docling_import if os.name == "posix" else None,
        )
        if completed.returncode == 0:
            break
    if completed is None:
        raise RuntimeError("Docling worker did not start.")
    if completed.returncode != 0:
        error_text = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Docling worker failed: {error_text or completed.returncode}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Docling worker returned malformed JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Docling worker returned a non-object result.")
    return _pdf_parse_result_from_payload(payload)


def _pdf_parse_result_to_payload(result: PdfParseResult) -> dict[str, object]:
    return {
        "preflight": {
            "parser_name": result.preflight.parser_name,
            "parser_version": result.preflight.parser_version,
            "encrypted": result.preflight.encrypted,
            "page_count": result.preflight.page_count,
            "pages": [page.__dict__ for page in result.preflight.pages],
            "warnings": list(result.preflight.warnings),
            "pdf_version": result.preflight.pdf_version,
            "permissions": list(result.preflight.permissions),
            "preflight_tool": result.preflight.preflight_tool,
            "preflight_tool_version": result.preflight.preflight_tool_version,
        },
        "representation_bundle": (
            result.representation_bundle.model_dump(mode="json")
            if result.representation_bundle is not None
            else None
        ),
        "transformation_payloads": [
            {
                "activity_type": payload.activity_type.value,
                "input_digest": payload.input_digest,
                "output_payload_base64": base64.b64encode(payload.output_payload).decode("ascii"),
                "output_media_type": payload.output_media_type,
                "tool_name": payload.tool_name,
                "tool_version": payload.tool_version,
                "model_name": payload.model_name,
                "model_version": payload.model_version,
                "model_digest": payload.model_digest,
                "configuration_digest": payload.configuration_digest,
                "page_scope": list(payload.page_scope),
                "language_set": list(payload.language_set),
                "confidence": payload.confidence,
            }
            for payload in result.transformation_payloads
        ],
        "blocking_reasons": list(result.blocking_reasons),
    }


def _pdf_parse_result_from_payload(payload: dict[str, object]) -> PdfParseResult:
    preflight_payload = payload.get("preflight")
    if not isinstance(preflight_payload, dict):
        raise RuntimeError("Docling worker result is missing preflight.")
    pages_payload = preflight_payload.get("pages")
    if not isinstance(pages_payload, list):
        raise RuntimeError("Docling worker preflight pages are malformed.")
    try:
        pages = tuple(
            PdfPagePreflight(
                page_index=int(page["page_index"]),
                width=float(page["width"]),
                height=float(page["height"]),
                rotation=int(page["rotation"]),
                embedded_text_character_count=int(page["embedded_text_character_count"]),
                warnings=tuple(page.get("warnings", [])),
                crop_left=float(page.get("crop_left", 0.0)),
                crop_top=float(page.get("crop_top", 0.0)),
                crop_right=(
                    float(page["crop_right"]) if page.get("crop_right") is not None else None
                ),
                crop_bottom=(
                    float(page["crop_bottom"]) if page.get("crop_bottom") is not None else None
                ),
                image_coverage=float(page.get("image_coverage", 0.0)),
                suspicious_glyph_rate=float(page.get("suspicious_glyph_rate", 0.0)),
                glyph_issue_count=int(page.get("glyph_issue_count", 0)),
            )
            for page in pages_payload
            if isinstance(page, dict)
        )
        if len(pages) != len(pages_payload):
            raise ValueError("page must be an object")
        preflight = PdfPreflight(
            parser_name=str(preflight_payload["parser_name"]),
            parser_version=str(preflight_payload["parser_version"]),
            preflight_tool=str(preflight_payload["preflight_tool"]),
            preflight_tool_version=str(preflight_payload["preflight_tool_version"]),
            encrypted=bool(preflight_payload["encrypted"]),
            page_count=int(preflight_payload["page_count"]),
            pages=pages,
            warnings=tuple(preflight_payload.get("warnings", [])),
            pdf_version=str(preflight_payload.get("pdf_version", "unknown")),
            permissions=tuple(preflight_payload.get("permissions", [])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Docling worker preflight is malformed.") from exc
    bundle_payload = payload.get("representation_bundle")
    if bundle_payload is not None and not isinstance(bundle_payload, dict):
        raise RuntimeError("Docling worker representation bundle is malformed.")
    blocking_reasons = payload.get("blocking_reasons", [])
    if not isinstance(blocking_reasons, list) or not all(
        isinstance(reason, str) for reason in blocking_reasons
    ):
        raise RuntimeError("Docling worker blocking reasons are malformed.")
    transformations_payload = payload.get("transformation_payloads", [])
    if not isinstance(transformations_payload, list):
        raise RuntimeError("Docling worker transformation payloads are malformed.")
    try:
        transformations = tuple(
            PdfTransformationPayload(
                activity_type=PdfTransformationType(str(item["activity_type"])),
                input_digest=str(item["input_digest"]),
                output_payload=base64.b64decode(str(item["output_payload_base64"]), validate=True),
                output_media_type=str(item["output_media_type"]),
                tool_name=str(item["tool_name"]),
                tool_version=str(item["tool_version"]),
                model_name=str(item["model_name"]),
                model_version=str(item["model_version"]),
                model_digest=str(item["model_digest"]),
                configuration_digest=str(item["configuration_digest"]),
                page_scope=tuple(int(page) for page in item["page_scope"]),
                language_set=tuple(str(language) for language in item["language_set"]),
                confidence=(
                    float(item["confidence"]) if item.get("confidence") is not None else None
                ),
            )
            for item in transformations_payload
            if isinstance(item, dict)
        )
        if len(transformations) != len(transformations_payload):
            raise ValueError("transformation must be an object")
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Docling worker transformation payload is malformed.") from exc
    return PdfParseResult(
        preflight=preflight,
        representation_bundle=(
            DocumentRepresentationBundle.model_validate_json(json.dumps(bundle_payload))
            if bundle_payload is not None
            else None
        ),
        transformation_payloads=transformations,
        blocking_reasons=tuple(blocking_reasons),
    )


def _docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Docling package version is unavailable for authoritative processing."
        ) from exc


def _parser_configuration(
    config: DoclingPdfParserConfig,
    policy_id: str,
) -> dict[str, object]:
    ocr_identity = _rapidocr_identity() if config.enable_ocr else None
    return {
        "enable_ocr": config.enable_ocr,
        "enable_table_structure": config.enable_table_structure,
        "ocr_language": config.ocr_language,
        "ocr_render_scale": config.ocr_render_scale,
        "ocr_text_score": config.ocr_text_score,
        "ocr_identity": ocr_identity,
        "ocr_render_engine": (
            {"name": "pypdfium2", "version": version("pypdfium2")} if config.enable_ocr else None
        ),
        "page_selection_policy_version": PdfExtractionPolicy.policy_version,
        "policy_id": policy_id,
        "layout_contract_version": "canonical_pdf_layout_v2",
        "pdfimages_version": _pdfimages_version(),
        "pdffonts_version": _pdffonts_version(),
        "pdfinfo_version": _pdfinfo_version(),
        "pdftotext_version": _pdftotext_version(),
    }


def _page_geometry_from_document(document: DoclingDocument) -> tuple[_PageGeometry, ...]:
    pages = tuple(
        _PageGeometry(
            page_number=int(page_number),
            width=float(page.size.width),
            height=float(page.size.height),
            rotation=0,
        )
        for page_number, page in sorted(document.pages.items())
    )
    if not pages:
        raise ValueError("Docling conversion produced no PDF pages.")
    return pages


def _page_geometry_from_preflight(
    preflight: PdfPreflight,
) -> tuple[_PageGeometry, ...]:
    return tuple(
        _PageGeometry(page.page_index, page.width, page.height, page.rotation)
        for page in preflight.pages
    )


def _validate_docling_page_geometry(
    docling_pages: tuple[_PageGeometry, ...],
    source_pages: tuple[_PageGeometry, ...],
) -> None:
    source_by_number = {page.page_number: page for page in source_pages}
    for docling_page in docling_pages:
        source_page = source_by_number.get(docling_page.page_number)
        if source_page is None:
            raise ValueError("Docling returned a page outside the source inventory.")
        if (docling_page.width, docling_page.height) != (
            source_page.width,
            source_page.height,
        ):
            raise ValueError("Docling page geometry disagrees with canonical source geometry.")


def _layout_items_from_document(
    document: DoclingDocument,
    page_geometry: tuple[_PageGeometry, ...],
) -> tuple[_LayoutItem, ...]:
    geometry_by_page = {page.page_number: page for page in page_geometry}
    layout_items: list[_LayoutItem] = []
    seen_item_refs: set[str] = set()
    for item, _depth in document.iterate_items():
        layout_item = _layout_item_from_docling_item(item, geometry_by_page)
        if layout_item is not None:
            layout_items.append(layout_item)
            seen_item_refs.add(str(getattr(item, "self_ref", "")))
    for item in cast(Any, document.texts):
        content_layer = getattr(getattr(item, "content_layer", None), "value", None)
        item_ref = str(getattr(item, "self_ref", ""))
        if content_layer != "furniture" or item_ref in seen_item_refs:
            continue
        layout_item = _layout_item_from_docling_item(item, geometry_by_page, node_type="furniture")
        if layout_item is not None:
            layout_items.append(layout_item)
    return tuple(layout_items)


def _finalize_layout_items(
    layout_items: tuple[_LayoutItem, ...],
    page_geometry: tuple[_PageGeometry, ...],
) -> tuple[_LayoutItem, ...]:
    if not layout_items:
        raise ValueError("PDF processing produced no usable text items.")
    classified_items = _classify_repeated_furniture(layout_items)
    leveled_items = _assign_heading_levels(classified_items)
    return _order_layout_items(leveled_items, page_geometry)


def _layout_item_from_docling_item(
    item: Any,
    geometry_by_page: dict[int, _PageGeometry],
    *,
    node_type: str | None = None,
) -> _LayoutItem | None:
    text = getattr(item, "text", None)
    if text is None:
        return None
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Docling text item has no usable text.")
    provenance = tuple(cast(Any, getattr(item, "prov", ())))
    if not provenance:
        raise ValueError("Docling text item has no PDF provenance.")
    regions = tuple(
        _layout_region_from_provenance(provenance_item, geometry_by_page)
        for provenance_item in provenance
    )
    label = getattr(getattr(item, "label", None), "value", None)
    content_layer = getattr(getattr(item, "content_layer", None), "value", None)
    resolved_node_type = node_type
    if resolved_node_type is None:
        resolved_node_type = {
            "section_header": "heading",
            "title": "heading",
            "list_item": "list_item",
            "caption": "caption",
            "footnote": "footnote",
            "page_header": "furniture",
            "page_footer": "furniture",
        }.get(str(label), "paragraph")
    if content_layer == "furniture":
        resolved_node_type = "furniture"
    heading_level = getattr(item, "level", None) if resolved_node_type == "heading" else None
    marker = getattr(item, "marker", None) if resolved_node_type == "list_item" else None
    return _LayoutItem(
        text=text,
        node_type=resolved_node_type,
        regions=regions,
        heading_level=int(heading_level) if heading_level is not None else None,
        marker=str(marker) if marker else None,
    )


def _ocr_selected_pages(
    raw_bytes: bytes,
    page_geometry: tuple[_PageGeometry, ...],
    selected_pages: tuple[int, ...],
    config: DoclingPdfParserConfig,
) -> tuple[tuple[_LayoutItem, ...], tuple[PdfTransformationPayload, ...]]:
    if not selected_pages:
        return (), ()
    try:
        import pypdfium2 as pdfium  # pyright: ignore[reportMissingTypeStubs]
        from rapidocr import RapidOCR  # pyright: ignore[reportMissingTypeStubs]
    except ImportError as exc:
        raise RuntimeError("Pinned selective OCR runtime is unavailable.") from exc

    identity = _rapidocr_identity()
    ocr_configuration = {
        "engine": "rapidocr_onnxruntime",
        "language": config.ocr_language,
        "render_scale": config.ocr_render_scale,
        "text_score": config.ocr_text_score,
        "selection_policy": PdfExtractionPolicy.policy_version,
    }
    ocr_configuration_digest = _canonical_json_digest(ocr_configuration)
    render_configuration = {
        "format": "png",
        "render_scale": config.ocr_render_scale,
        "rotation_contract": "canonical_page_orientation_v1",
    }
    render_configuration_digest = _canonical_json_digest(render_configuration)
    renderer_version = version("pypdfium2")
    renderer_model_digest = _canonical_json_digest(
        {"renderer": "pdfium", "version": renderer_version}
    )
    pdf = pdfium.PdfDocument(BytesIO(raw_bytes))
    ocr = RapidOCR(params={"Global.text_score": config.ocr_text_score})
    geometry_by_page = {page.page_number: page for page in page_geometry}
    items: list[_LayoutItem] = []
    payloads: list[PdfTransformationPayload] = []
    raw_digest = hashlib.sha256(raw_bytes).hexdigest()
    for page_number in selected_pages:
        geometry = geometry_by_page[page_number]
        page = pdf[page_number - 1]
        bitmap = page.render(scale=config.ocr_render_scale)
        image = bitmap.to_pil()
        png_buffer = BytesIO()
        image.save(png_buffer, format="PNG", optimize=False, compress_level=9)
        png_bytes = png_buffer.getvalue()
        png_digest = hashlib.sha256(png_bytes).hexdigest()
        payloads.append(
            PdfTransformationPayload(
                activity_type=PdfTransformationType.RENDER,
                input_digest=raw_digest,
                output_payload=png_bytes,
                output_media_type="image/png",
                tool_name="pypdfium2",
                tool_version=renderer_version,
                model_name="pdfium_page_renderer",
                model_version=renderer_version,
                model_digest=renderer_model_digest,
                configuration_digest=render_configuration_digest,
                page_scope=(page_number,),
            )
        )
        result = cast(Any, ocr(image))
        if result is None or not result.txts:
            raise PdfOcrNoUsableTextError(page_number, tuple(payloads))
        scores = tuple(float(score) for score in result.scores)
        boxes = tuple(box.tolist() for box in result.boxes)
        if not (len(result.txts) == len(scores) == len(boxes)):
            raise RuntimeError("Selective OCR returned inconsistent text, score, and box counts.")
        sidecar_records: list[dict[str, object]] = []
        for text, score, box in zip(result.txts, scores, boxes, strict=True):
            normalized_text = str(text).strip()
            if not normalized_text:
                raise RuntimeError("Selective OCR returned an empty text record.")
            xs = tuple(float(point[0]) for point in box)
            ys = tuple(float(point[1]) for point in box)
            left = min(xs) * geometry.width / image.width
            right = max(xs) * geometry.width / image.width
            top = min(ys) * geometry.height / image.height
            bottom = max(ys) * geometry.height / image.height
            region = _LayoutRegion(
                page_number,
                geometry.width,
                geometry.height,
                left,
                top,
                right,
                bottom,
                geometry.rotation,
            )
            items.append(
                _LayoutItem(
                    text=normalized_text,
                    node_type="paragraph",
                    regions=(region,),
                    extraction_path=PdfExtractionPath.OCR,
                    confidence=score,
                )
            )
            sidecar_records.append(
                {
                    "box": [[round(float(value), 6) for value in point] for point in box],
                    "confidence": round(score, 6),
                    "text": normalized_text,
                }
            )
        page_confidence = sum(scores) / len(scores)
        sidecar = json.dumps(
            {
                "configuration": ocr_configuration,
                "engine": identity,
                "input_digest": png_digest,
                "page": page_number,
                "records": sidecar_records,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        payloads.append(
            PdfTransformationPayload(
                activity_type=PdfTransformationType.OCR,
                input_digest=png_digest,
                output_payload=sidecar,
                output_media_type="application/vnd.kotekomi.pdf-ocr+json",
                tool_name="rapidocr",
                tool_version=cast(str, identity["engine_version"]),
                model_name=cast(str, identity["model_name"]),
                model_version=cast(str, identity["model_version"]),
                model_digest=cast(str, identity["model_digest"]),
                configuration_digest=ocr_configuration_digest,
                page_scope=(page_number,),
                language_set=(config.ocr_language,),
                confidence=page_confidence,
            )
        )
    return tuple(items), tuple(payloads)


@cache
def _rapidocr_identity() -> dict[str, object]:
    import rapidocr  # pyright: ignore[reportMissingTypeStubs]

    model_root = Path(rapidocr.__file__).parent / "models"
    model_names = (
        "PP-OCRv6_det_small.onnx",
        "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "PP-OCRv6_rec_small.onnx",
    )
    model_digests = {
        name: hashlib.sha256((model_root / name).read_bytes()).hexdigest() for name in model_names
    }
    engine_version = version("rapidocr")
    return {
        "backend": "onnxruntime",
        "backend_version": version("onnxruntime"),
        "engine_version": engine_version,
        "model_digest": _canonical_json_digest(model_digests),
        "model_name": "+".join(model_names),
        "model_version": f"rapidocr-bundled-{engine_version}",
        "models": model_digests,
    }


def _canonical_json_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _classify_repeated_furniture(
    layout_items: tuple[_LayoutItem, ...],
) -> tuple[_LayoutItem, ...]:
    occurrences: dict[str, set[int]] = {}
    for item in layout_items:
        region = item.regions[0]
        near_page_edge = region.top <= region.page_height * 0.1 or (
            region.bottom >= region.page_height * 0.9
        )
        if not near_page_edge:
            continue
        key = re.sub(r"\d+", "#", " ".join(item.text.casefold().split()))
        occurrences.setdefault(key, set()).add(region.page_number)
    repeated_keys = {key for key, pages in occurrences.items() if len(pages) >= 2}
    return tuple(
        replace(item, node_type="furniture")
        if re.sub(r"\d+", "#", " ".join(item.text.casefold().split())) in repeated_keys
        else item
        for item in layout_items
    )


def _assign_heading_levels(
    layout_items: tuple[_LayoutItem, ...],
) -> tuple[_LayoutItem, ...]:
    headings = tuple(item for item in layout_items if item.node_type == "heading")
    if not headings:
        return layout_items
    declared_levels = {item.heading_level for item in headings if item.heading_level is not None}
    if len(declared_levels) > 1:
        return layout_items
    heights = sorted(
        {round(max(region.bottom - region.top for region in item.regions), 1) for item in headings},
        reverse=True,
    )
    level_by_height = {height: index + 1 for index, height in enumerate(heights)}
    return tuple(
        replace(
            item,
            heading_level=level_by_height[
                round(max(region.bottom - region.top for region in item.regions), 1)
            ],
        )
        if item.node_type == "heading"
        else item
        for item in layout_items
    )


def _order_layout_items(
    layout_items: tuple[_LayoutItem, ...],
    page_geometry: tuple[_PageGeometry, ...],
) -> tuple[_LayoutItem, ...]:
    ordered: list[_LayoutItem] = []
    for page in page_geometry:
        page_items = tuple(
            item for item in layout_items if item.regions[0].page_number == page.page_number
        )
        furniture = tuple(item for item in page_items if item.node_type == "furniture")
        top_furniture = sorted(
            (item for item in furniture if item.regions[0].top < page.height / 2),
            key=_layout_item_visual_key,
        )
        bottom_furniture = sorted(
            (item for item in furniture if item.regions[0].top >= page.height / 2),
            key=_layout_item_visual_key,
        )
        body_items = tuple(item for item in page_items if item.node_type != "furniture")
        headings = sorted(
            (item for item in body_items if item.node_type == "heading"),
            key=_layout_item_visual_key,
        )
        remaining = set(range(len(body_items)))
        body_by_index = dict(enumerate(body_items))
        body_order: list[_LayoutItem] = []
        previous_top = float("-inf")
        for heading in headings:
            heading_top = heading.regions[0].top
            segment_indices = tuple(
                index
                for index in sorted(remaining)
                if body_by_index[index].node_type != "heading"
                and previous_top <= body_by_index[index].regions[0].top < heading_top
            )
            body_order.extend(
                _order_column_segment(
                    tuple(body_by_index[index] for index in segment_indices),
                    page.width,
                )
            )
            remaining.difference_update(segment_indices)
            heading_index = next(
                index for index in sorted(remaining) if body_by_index[index] is heading
            )
            remaining.remove(heading_index)
            body_order.append(heading)
            previous_top = heading_top
        body_order.extend(
            _order_column_segment(
                tuple(body_by_index[index] for index in sorted(remaining)),
                page.width,
            )
        )
        ordered.extend((*top_furniture, *body_order, *bottom_furniture))
    return tuple(ordered)


def _order_column_segment(
    items: tuple[_LayoutItem, ...],
    page_width: float,
) -> tuple[_LayoutItem, ...]:
    if len(items) < 2:
        return items
    by_left = sorted(items, key=lambda item: item.regions[0].left)
    columns: list[list[_LayoutItem]] = []
    threshold = page_width * 0.15
    for item in by_left:
        if not columns or item.regions[0].left - columns[-1][-1].regions[0].left > threshold:
            columns.append([item])
        else:
            columns[-1].append(item)
    return tuple(item for column in columns for item in sorted(column, key=_layout_item_visual_key))


def _layout_item_visual_key(item: _LayoutItem) -> tuple[float, float, str]:
    region = item.regions[0]
    return region.top, region.left, item.text


def _layout_region_from_provenance(
    provenance: Any,
    geometry_by_page: dict[int, _PageGeometry],
) -> _LayoutRegion:
    page_number = int(provenance.page_no)
    page = geometry_by_page.get(page_number)
    if page is None:
        raise ValueError("Docling text provenance references an unknown PDF page.")
    bounding_box = provenance.bbox
    left = float(bounding_box.l)
    right = float(bounding_box.r)
    coordinate_origin = str(getattr(getattr(bounding_box, "coord_origin", None), "value", ""))
    if coordinate_origin == "BOTTOMLEFT":
        top = page.height - float(bounding_box.t)
        bottom = page.height - float(bounding_box.b)
    elif coordinate_origin == "TOPLEFT":
        top = float(bounding_box.t)
        bottom = float(bounding_box.b)
    else:
        raise ValueError("Docling provenance uses an unknown coordinate origin.")
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError("Docling text provenance has invalid PDF bounds.")
    if right > page.width or bottom > page.height:
        raise ValueError("Docling text provenance exceeds its PDF page bounds.")
    return _LayoutRegion(
        page_number,
        page.width,
        page.height,
        left,
        top,
        right,
        bottom,
        page.rotation,
    )


def _preflight_from_layout(
    source_preflight: PdfPreflight,
    layout_items: tuple[_LayoutItem, ...],
) -> PdfPreflight:
    source_pages = {page.page_index for page in source_preflight.pages}
    for item in layout_items:
        for page_number in {region.page_number for region in item.regions}:
            if page_number not in source_pages:
                raise ValueError("Docling returned content outside the source page inventory.")
    return source_preflight


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
    source_preflight: PdfPreflight,
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
        preflight=replace(
            source_preflight,
            warnings=tuple(
                dict.fromkeys((*source_preflight.warnings, "source_access_blocked", *reasons))
            ),
        ),
        representation_bundle=None,
        blocking_reasons=reasons,
    )


def _blocked_preflight(
    parser_version: str,
    reasons: tuple[str, ...],
    pdf_version: str,
    encrypted: bool,
) -> PdfPreflight:
    return PdfPreflight(
        parser_name="docling",
        parser_version=parser_version,
        encrypted=encrypted,
        page_count=0,
        pages=(),
        warnings=("source_access_blocked", *reasons),
        pdf_version=pdf_version,
        preflight_tool="poppler_pdf_preflight",
        preflight_tool_version=_pdfinfo_version(),
    )


def preflight_pdf_source(raw_bytes: bytes, parser_version: str) -> PdfPreflight:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary_pdf:
        temporary_pdf.write(raw_bytes)
        temporary_pdf.flush()
        completed = subprocess.run(
            ("pdfinfo", "-f", "1", "-l", "999999", "-box", temporary_pdf.name),
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )
    if completed.returncode != 0:
        raise PdfSourcePreflightError(
            "PDF source preflight could not establish an authoritative page inventory."
        )
    output = completed.stdout
    page_count_match = re.search(r"^Pages:\s+(\d+)\s*$", output, re.MULTILINE)
    version_match = re.search(r"^PDF version:\s+([^\s]+)\s*$", output, re.MULTILINE)
    encrypted_match = re.search(r"^Encrypted:\s+(yes|no)(?:\s+\((.*)\))?\s*$", output, re.MULTILINE)
    if page_count_match is None or version_match is None or encrypted_match is None:
        raise PdfSourcePreflightError("PDF source preflight returned incomplete document metadata.")
    page_count = int(page_count_match.group(1))
    geometries: list[_PageGeometry] = []
    page_preflights: list[PdfPagePreflight] = []
    for page_index in range(1, page_count + 1):
        media_box = _pdfinfo_page_box(output, page_index, "MediaBox")
        crop_box = _pdfinfo_page_box(output, page_index, "CropBox")
        rotation_match = re.search(
            rf"^Page\s+{page_index}\s+rot:\s+(\d+)\s*$",
            output,
            re.MULTILINE,
        )
        if rotation_match is None:
            raise PdfSourcePreflightError("PDF source preflight omitted page rotation metadata.")
        rotation = int(rotation_match.group(1)) % 360
        width, height, canonical_crop = _canonical_page_bounds(
            media_box,
            crop_box,
            rotation,
        )
        canonical_left, canonical_top, canonical_right, canonical_bottom = canonical_crop
        geometries.append(_PageGeometry(page_index, width, height, rotation))
        page_preflights.append(
            PdfPagePreflight(
                page_index=page_index,
                width=width,
                height=height,
                rotation=rotation,
                embedded_text_character_count=0,
                crop_left=canonical_left,
                crop_top=canonical_top,
                crop_right=canonical_right,
                crop_bottom=canonical_bottom,
            )
        )
    image_coverage = _image_coverage_by_page(raw_bytes, tuple(geometries))
    text_metrics = _embedded_text_metrics_by_page(raw_bytes, page_count)
    font_warnings = _font_mapping_warnings_by_page(raw_bytes, page_count)
    pages = tuple(
        replace(
            page,
            embedded_text_character_count=text_metrics[page.page_index][0],
            image_coverage=image_coverage[page.page_index],
            suspicious_glyph_rate=text_metrics[page.page_index][1],
            glyph_issue_count=text_metrics[page.page_index][2],
            warnings=(
                font_warnings[page.page_index] if text_metrics[page.page_index][0] < 64 else ()
            ),
        )
        for page in page_preflights
    )
    permission_details = encrypted_match.group(2)
    permissions = (
        tuple(part.strip() for part in permission_details.split() if part.strip())
        if permission_details
        else (("all",) if encrypted_match.group(1) == "no" else ())
    )
    return PdfPreflight(
        parser_name="docling",
        parser_version=parser_version,
        encrypted=encrypted_match.group(1) == "yes",
        page_count=page_count,
        pages=pages,
        pdf_version=version_match.group(1),
        permissions=permissions,
        preflight_tool="poppler_pdf_preflight",
        preflight_tool_version=_pdfinfo_version(),
    )


def _pdfinfo_page_box(
    output: str,
    page_index: int,
    box_name: str,
) -> tuple[float, float, float, float]:
    match = re.search(
        rf"^Page\s+{page_index}\s+{box_name}:\s+"
        r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+"
        r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*$",
        output,
        re.MULTILINE,
    )
    if match is None:
        raise PdfSourcePreflightError(f"PDF source preflight omitted page {box_name} metadata.")
    return cast(tuple[float, float, float, float], tuple(map(float, match.groups())))


def _canonical_page_bounds(
    media_box: tuple[float, float, float, float],
    crop_box: tuple[float, float, float, float],
    rotation: int,
) -> tuple[float, float, tuple[float, float, float, float]]:
    media_left, media_bottom, media_right, media_top = media_box
    raw_width = media_right - media_left
    raw_height = media_top - media_bottom
    left = crop_box[0] - media_left
    bottom = crop_box[1] - media_bottom
    right = crop_box[2] - media_left
    top = crop_box[3] - media_bottom
    if rotation == 0:
        return raw_width, raw_height, (left, raw_height - top, right, raw_height - bottom)
    if rotation == 90:
        return raw_height, raw_width, (bottom, left, top, right)
    if rotation == 180:
        return raw_width, raw_height, (raw_width - right, bottom, raw_width - left, top)
    if rotation == 270:
        return (
            raw_height,
            raw_width,
            (raw_height - top, raw_width - right, raw_height - bottom, raw_width - left),
        )
    raise PdfSourcePreflightError("PDF source preflight returned a non-cardinal rotation.")


def _embedded_text_metrics_by_page(
    raw_bytes: bytes,
    page_count: int,
) -> dict[int, tuple[int, float, int]]:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary_pdf:
        temporary_pdf.write(raw_bytes)
        temporary_pdf.flush()
        completed = subprocess.run(
            ("pdftotext", "-enc", "UTF-8", temporary_pdf.name, "-"),
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )
    if completed.returncode != 0:
        raise PdfSourcePreflightError("PDF source preflight could not measure embedded text.")
    page_texts = completed.stdout.split("\f")
    if len(page_texts) < page_count:
        raise PdfSourcePreflightError("PDF source preflight returned incomplete page text metrics.")
    metrics: dict[int, tuple[int, float, int]] = {}
    for page_index, page_text in enumerate(page_texts[:page_count], start=1):
        text = page_text.strip()
        issue_count = sum(
            character == "\ufffd"
            or (unicodedata.category(character) in {"Cc", "Co"} and not character.isspace())
            for character in text
        )
        metrics[page_index] = (
            len(text),
            issue_count / len(text) if text else 0.0,
            issue_count,
        )
    return metrics


def _font_mapping_warnings_by_page(
    raw_bytes: bytes,
    page_count: int,
) -> dict[int, tuple[str, ...]]:
    warnings: dict[int, tuple[str, ...]] = {}
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary_pdf:
        temporary_pdf.write(raw_bytes)
        temporary_pdf.flush()
        for page_index in range(1, page_count + 1):
            completed = subprocess.run(
                ("pdffonts", "-f", str(page_index), "-l", str(page_index), temporary_pdf.name),
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "LC_ALL": "C"},
            )
            if completed.returncode != 0:
                raise PdfSourcePreflightError(
                    "PDF source preflight could not inspect font Unicode mappings."
                )
            font_rows = tuple(
                line.split() for line in completed.stdout.splitlines()[2:] if line.strip()
            )
            warnings[page_index] = (
                ("font_unicode_mapping_unavailable",)
                if any(len(fields) >= 3 and fields[-3] == "no" for fields in font_rows)
                else ()
            )
    return warnings


def _pdf_version(raw_bytes: bytes) -> str:
    match = re.search(rb"%PDF-([0-9]+\.[0-9]+)", raw_bytes[:1024])
    return match.group(1).decode("ascii") if match is not None else "unknown"


def _pdf_is_encrypted(raw_bytes: bytes) -> bool:
    return re.search(rb"/Encrypt(?:\s|/|<<)", raw_bytes) is not None


@cache
def _pdfimages_version() -> str:
    completed = subprocess.run(
        ("pdfimages", "-v"),
        check=True,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    first_line = next(
        (line.strip() for line in output.splitlines() if line.strip()),
        "",
    )
    if not first_line.startswith("pdfimages version "):
        raise RuntimeError("pdfimages version is unavailable for processing identity.")
    return first_line.removeprefix("pdfimages version ")


@cache
def _pdffonts_version() -> str:
    completed = subprocess.run(
        ("pdffonts", "-v"),
        check=True,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if not first_line.startswith("pdffonts version "):
        raise RuntimeError("pdffonts version is unavailable for processing identity.")
    return first_line.removeprefix("pdffonts version ")


@cache
def _pdfinfo_version() -> str:
    completed = subprocess.run(
        ("pdfinfo", "-v"),
        check=True,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if not first_line.startswith("pdfinfo version "):
        raise RuntimeError("pdfinfo version is unavailable for processing identity.")
    return first_line.removeprefix("pdfinfo version ")


@cache
def _pdftotext_version() -> str:
    completed = subprocess.run(
        ("pdftotext", "-v"),
        check=True,
        capture_output=True,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if not first_line.startswith("pdftotext version "):
        raise RuntimeError("pdftotext version is unavailable for processing identity.")
    return first_line.removeprefix("pdftotext version ")


def _image_coverage_by_page(
    raw_bytes: bytes,
    page_geometry: tuple[_PageGeometry, ...],
) -> dict[int, float]:
    coverage = {page.page_number: 0.0 for page in page_geometry}
    page_area = {page.page_number: page.width * page.height for page in page_geometry}
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary_pdf:
        temporary_pdf.write(raw_bytes)
        temporary_pdf.flush()
        completed = subprocess.run(
            ("pdfimages", "-list", temporary_pdf.name),
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )
    if completed.returncode != 0:
        raise PdfSourcePreflightError("PDF source preflight could not measure page image coverage.")
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 14 or not fields[0].isdigit() or fields[2] != "image":
            continue
        page_number = int(fields[0])
        if page_number not in coverage:
            continue
        width_pixels = int(fields[3])
        height_pixels = int(fields[4])
        x_dpi = float(fields[12])
        y_dpi = float(fields[13])
        if x_dpi <= 0 or y_dpi <= 0:
            raise RuntimeError("pdfimages returned an invalid image resolution.")
        image_area = (width_pixels * 72 / x_dpi) * (height_pixels * 72 / y_dpi)
        coverage[page_number] = min(
            1.0,
            coverage[page_number] + image_area / page_area[page_number],
        )
    return coverage


def build_docling_representation_bundle(
    *,
    parse_input: PdfParseInput,
    page_geometry: tuple[_PageGeometry, ...],
    layout_items: tuple[_LayoutItem, ...],
    parser_version: str,
    config: DoclingPdfParserConfig,
) -> DocumentRepresentationBundle:
    input_digest = hashlib.sha256(parse_input.raw_bytes).hexdigest()
    configuration = _parser_configuration(config, parse_input.policy_id)
    config_digest = hashlib.sha256(
        json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    representation_id = deterministic_representation_id(parse_input.processing_task_fingerprint_id)
    representation_key = representation_id.removeprefix("rep_")
    logical_view_id = f"tvw_{representation_key}_logical"
    display_view_id = f"tvw_{representation_key}_display"
    root_node_id = f"nod_{representation_key}_document"
    quality_id = f"pqr_{representation_key}_quality_v1"
    logical_text, display_text, nodes, source_regions = _canonical_layout_records(
        representation_id=representation_id,
        representation_key=representation_key,
        logical_view_id=logical_view_id,
        display_view_id=display_view_id,
        layout_items=layout_items,
    )
    logical_view = TextView(
        id=logical_view_id,
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(logical_text.encode("utf-8")).hexdigest(),
        text=logical_text,
        normalization_policy="docling_analysis_text_v2",
    )
    display_view = TextView(
        id=display_view_id,
        representation_id=representation_id,
        kind=TextViewKind.DISPLAY,
        content_digest=hashlib.sha256(display_text.encode("utf-8")).hexdigest(),
        text=display_text,
        normalization_policy="docling_display_text_v2",
    )
    root = DocumentNode(
        id=root_node_id,
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        structural_path=("document",),
        text_view_id=logical_view_id,
        start_char=0,
        end_char=len(logical_text),
        extraction_path=(
            PdfExtractionPath.MIXED
            if len({item.extraction_path for item in layout_items}) > 1
            else layout_items[0].extraction_path
        ),
    )
    nodes = (root, *nodes)
    contains_edges = tuple(
        DocumentEdge(
            id=f"deg_{representation_key}_contains_{node.order_index:04d}",
            representation_id=representation_id,
            from_node_id=cast(str, node.parent_node_id),
            to_node_id=node.id,
            edge_type="contains",
            provenance_kind=DocumentEdgeProvenanceKind.PARSER,
            provenance_id="docling_layout_v2",
        )
        for node in nodes[1:]
    )
    logical_nodes = tuple(node for node in nodes[1:] if node.node_type != "furniture")
    reading_order_edges = tuple(
        DocumentEdge(
            id=f"deg_{representation_key}_reading_{index:04d}",
            representation_id=representation_id,
            from_node_id=earlier.id,
            to_node_id=later.id,
            edge_type="reading_order",
            provenance_kind=DocumentEdgeProvenanceKind.DETERMINISTIC,
            provenance_id="canonical_xy_cut_reading_order_v1",
        )
        for index, (earlier, later) in enumerate(
            zip(logical_nodes, logical_nodes[1:], strict=False),
            start=1,
        )
    )
    edges = (*contains_edges, *reading_order_edges)
    quality_report = _quality_report(
        quality_id=quality_id,
        representation_id=representation_id,
        page_geometry=page_geometry,
        nodes=nodes,
        source_regions=source_regions,
        logical_text=logical_text,
        display_text=display_text,
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
                text_views=(logical_view, display_view),
                nodes=nodes,
                edges=edges,
                source_regions=source_regions,
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(logical_view, display_view),
        nodes=nodes,
        edges=edges,
        source_regions=source_regions,
        quality_report=quality_report,
    )


def _canonical_layout_records(
    *,
    representation_id: str,
    representation_key: str,
    logical_view_id: str,
    display_view_id: str,
    layout_items: tuple[_LayoutItem, ...],
) -> tuple[str, str, tuple[DocumentNode, ...], tuple[SourceRegion, ...]]:
    display_text, display_ranges = _render_layout_text(layout_items)
    logical_items = tuple(item for item in layout_items if item.node_type != "furniture")
    logical_text, compact_logical_ranges = _render_layout_text(logical_items)
    logical_ranges: dict[int, tuple[int, int]] = {}
    logical_index = 0
    for item_index, item in enumerate(layout_items):
        if item.node_type != "furniture":
            logical_ranges[item_index] = compact_logical_ranges[logical_index]
            logical_index += 1
    nodes: list[DocumentNode] = []
    source_regions: list[SourceRegion] = []
    root_node_id = f"nod_{representation_key}_document"
    parent_paths: dict[str, tuple[str, ...]] = {root_node_id: ("document",)}
    section_stack: list[tuple[int, str, str]] = []
    list_stack: list[tuple[float, str]] = []
    current_page: int | None = None
    for item_index, item in enumerate(layout_items):
        order_index = item_index + 1
        node_id = f"nod_{representation_key}_{order_index:04d}"
        page_number = item.regions[0].page_number
        if page_number != current_page:
            section_stack.clear()
            list_stack.clear()
            current_page = page_number
        rendered_text = _rendered_layout_item_text(item)
        if item.node_type == "furniture":
            parent_id = root_node_id
            section_path: tuple[str, ...] = ()
            text_view_id = display_view_id
            start_char, end_char = display_ranges[item_index]
        elif item.node_type == "heading":
            level = item.heading_level or 1
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            parent_id = section_stack[-1][1] if section_stack else root_node_id
            section_path = (*tuple(entry[2] for entry in section_stack), item.text)
            text_view_id = logical_view_id
            start_char, end_char = logical_ranges[item_index]
            list_stack.clear()
        elif item.node_type == "list_item":
            item_left = min(region.left for region in item.regions)
            while list_stack and item_left <= list_stack[-1][0] + 1.0:
                list_stack.pop()
            parent_id = (
                list_stack[-1][1]
                if list_stack
                else (section_stack[-1][1] if section_stack else root_node_id)
            )
            section_path = tuple(entry[2] for entry in section_stack)
            text_view_id = logical_view_id
            start_char, end_char = logical_ranges[item_index]
        else:
            parent_id = section_stack[-1][1] if section_stack else root_node_id
            section_path = tuple(entry[2] for entry in section_stack)
            text_view_id = logical_view_id
            start_char, end_char = logical_ranges[item_index]
            list_stack.clear()
        region_ids: list[str] = []
        for region_index, region in enumerate(item.regions, start=1):
            region_id = f"srg_{representation_key}_{order_index:04d}_{region_index:02d}"
            region_ids.append(region_id)
            source_regions.append(
                SourceRegion(
                    id=region_id,
                    representation_id=representation_id,
                    coordinate_system=SourceCoordinateSystem.PDF_POINTS_TOP_LEFT_V1,
                    page_number=region.page_number,
                    page_width=region.page_width,
                    page_height=region.page_height,
                    left=region.left,
                    top=region.top,
                    right=region.right,
                    bottom=region.bottom,
                    rotation_applied=region.rotation_applied,
                )
            )
        structural_path = (
            *parent_paths[parent_id],
            f"{item.node_type}:{order_index:04d}",
        )
        node = DocumentNode(
            id=node_id,
            representation_id=representation_id,
            parent_node_id=parent_id,
            node_type=item.node_type,
            order_index=order_index,
            structural_path=structural_path,
            section_path=section_path,
            text_view_id=text_view_id,
            start_char=start_char,
            end_char=end_char,
            source_region_ids=tuple(region_ids),
            source_page_numbers=tuple(sorted({region.page_number for region in item.regions})),
            source_text_digest=hashlib.sha256(rendered_text.encode("utf-8")).hexdigest(),
            parser_confidence=item.confidence,
            extraction_path=item.extraction_path,
        )
        nodes.append(node)
        parent_paths[node.id] = structural_path
        if item.node_type == "heading":
            section_stack.append((item.heading_level or 1, node.id, item.text))
        elif item.node_type == "list_item":
            list_stack.append((min(region.left for region in item.regions), node.id))
    return logical_text, display_text, tuple(nodes), tuple(source_regions)


def _render_layout_text(
    layout_items: tuple[_LayoutItem, ...],
) -> tuple[str, tuple[tuple[int, int], ...]]:
    parts: list[str] = []
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for item in layout_items:
        if parts:
            parts.append("\n")
            cursor += 1
        rendered_text = _rendered_layout_item_text(item)
        start = cursor
        parts.append(rendered_text)
        cursor += len(rendered_text)
        ranges.append((start, cursor))
    return "".join(parts), tuple(ranges)


def _rendered_layout_item_text(item: _LayoutItem) -> str:
    return f"{item.marker} {item.text}" if item.marker else item.text


def _quality_report(
    *,
    quality_id: str,
    representation_id: str,
    page_geometry: tuple[_PageGeometry, ...],
    nodes: tuple[DocumentNode, ...],
    source_regions: tuple[SourceRegion, ...],
    logical_text: str,
    display_text: str,
) -> ParseQualityReport:
    expected_pages = {page.page_number for page in page_geometry}
    covered_pages = {region.page_number for region in source_regions}
    content_nodes = nodes[1:]
    logical_nodes = tuple(node for node in content_nodes if node.node_type != "furniture")
    issues: list[str] = []
    if not logical_text:
        issues.append("empty_logical_text")
    if not content_nodes:
        issues.append("missing_content_nodes")
    if any(not node.source_region_ids for node in content_nodes):
        issues.append("content_node_missing_source_region")
    if covered_pages != expected_pages:
        issues.append("missing_page_region_coverage")
    return ParseQualityReport(
        id=quality_id,
        representation_id=representation_id,
        metric_values={
            "page_count": len(page_geometry),
            "covered_page_count": len(covered_pages),
            "logical_text_char_count": len(logical_text),
            "display_text_char_count": len(display_text),
            "reading_order_node_count": len(logical_nodes),
            "heading_node_count": sum(node.node_type == "heading" for node in content_nodes),
            "paragraph_node_count": sum(node.node_type == "paragraph" for node in content_nodes),
            "list_item_node_count": sum(node.node_type == "list_item" for node in content_nodes),
            "furniture_node_count": sum(node.node_type == "furniture" for node in content_nodes),
            "embedded_node_count": sum(
                node.extraction_path is PdfExtractionPath.EMBEDDED for node in content_nodes
            ),
            "ocr_node_count": sum(
                node.extraction_path is PdfExtractionPath.OCR for node in content_nodes
            ),
            "source_region_count": len(source_regions),
        },
        issues=tuple(issues),
        analyzability=(
            RepresentationAnalyzability.ACCEPTABLE
            if not issues
            else RepresentationAnalyzability.BLOCKED
        ),
    )
