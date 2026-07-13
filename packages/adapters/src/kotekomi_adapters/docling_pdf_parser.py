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
from typing import TYPE_CHECKING, Any, cast

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
    DocumentEdge,
    DocumentEdgeProvenanceKind,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
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
    enable_ocr: bool = False
    enable_table_structure: bool = False


@dataclass(frozen=True)
class _PageGeometry:
    page_number: int
    width: float
    height: float


@dataclass(frozen=True)
class _LayoutRegion:
    page_number: int
    page_width: float
    page_height: float
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class _LayoutItem:
    text: str
    node_type: str
    regions: tuple[_LayoutRegion, ...]


class PdfSourcePreflightError(RuntimeError):
    """The source bytes cannot yield a trustworthy PDF page inventory."""


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
            "pdfimages_version": _pdfimages_version(),
            "pdfinfo_version": _pdfinfo_version(),
            "pdftotext_version": _pdftotext_version(),
        }
        config_digest = hashlib.sha256(
            json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return PdfProcessorIdentity("docling", parser_version, config_digest, "2")

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
            page_geometry = _page_geometry_from_document(conversion.document)
            layout_items = _layout_items_from_document(conversion.document, page_geometry)
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
    return PdfParseResult(
        preflight=preflight,
        representation_bundle=(
            DocumentRepresentationBundle.model_validate_json(json.dumps(bundle_payload))
            if bundle_payload is not None
            else None
        ),
        blocking_reasons=tuple(blocking_reasons),
    )


def _docling_version() -> str:
    try:
        return version("docling")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Docling package version is unavailable for authoritative processing."
        ) from exc


def _page_geometry_from_document(document: DoclingDocument) -> tuple[_PageGeometry, ...]:
    pages = tuple(
        _PageGeometry(
            page_number=int(page_number),
            width=float(page.size.width),
            height=float(page.size.height),
        )
        for page_number, page in sorted(document.pages.items())
    )
    if not pages:
        raise ValueError("Docling conversion produced no PDF pages.")
    return pages


def _layout_items_from_document(
    document: DoclingDocument,
    page_geometry: tuple[_PageGeometry, ...],
) -> tuple[_LayoutItem, ...]:
    geometry_by_page = {page.page_number: page for page in page_geometry}
    layout_items: list[_LayoutItem] = []
    for item, _depth in document.iterate_items():
        layout_item = _layout_item_from_docling_item(item, geometry_by_page)
        if layout_item is not None:
            layout_items.append(layout_item)
    for item in cast(Any, document.texts):
        content_layer = getattr(getattr(item, "content_layer", None), "value", None)
        if content_layer != "furniture":
            continue
        layout_item = _layout_item_from_docling_item(item, geometry_by_page, node_type="furniture")
        if layout_item is not None:
            layout_items.append(layout_item)
    if not layout_items:
        raise ValueError("Docling conversion produced no body text items.")
    return tuple(layout_items)


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
    return _LayoutItem(
        text=text,
        node_type=node_type or ("heading" if label == "section_header" else "paragraph"),
        regions=regions,
    )


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
    top = page.height - float(bounding_box.t)
    bottom = page.height - float(bounding_box.b)
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError("Docling text provenance has invalid PDF bounds.")
    if right > page.width or bottom > page.height:
        raise ValueError("Docling text provenance exceeds its PDF page bounds.")
    return _LayoutRegion(page_number, page.width, page.height, left, top, right, bottom)


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
        media_left, media_bottom, media_right, media_top = media_box
        crop_left, crop_bottom, crop_right, crop_top = crop_box
        width = media_right - media_left
        height = media_top - media_bottom
        rotation = int(rotation_match.group(1)) % 360
        geometries.append(_PageGeometry(page_index, width, height))
        page_preflights.append(
            PdfPagePreflight(
                page_index=page_index,
                width=width,
                height=height,
                rotation=rotation,
                embedded_text_character_count=0,
                crop_left=crop_left - media_left,
                crop_top=media_top - crop_top,
                crop_right=crop_right - media_left,
                crop_bottom=media_top - crop_bottom,
            )
        )
    image_coverage = _image_coverage_by_page(raw_bytes, tuple(geometries))
    text_metrics = _embedded_text_metrics_by_page(raw_bytes, page_count)
    pages = tuple(
        replace(
            page,
            embedded_text_character_count=text_metrics[page.page_index][0],
            image_coverage=image_coverage[page.page_index],
            suspicious_glyph_rate=text_metrics[page.page_index][1],
            glyph_issue_count=text_metrics[page.page_index][2],
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
    configuration = {
        "enable_ocr": config.enable_ocr,
        "enable_table_structure": config.enable_table_structure,
        "policy_id": parse_input.policy_id,
        "pdfimages_version": _pdfimages_version(),
        "pdfinfo_version": _pdfinfo_version(),
        "pdftotext_version": _pdftotext_version(),
    }
    config_digest = hashlib.sha256(
        json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    representation_id = deterministic_representation_id(parse_input.processing_task_fingerprint_id)
    representation_key = representation_id.removeprefix("rep_")
    text_view_id = f"tvw_{representation_key}_logical"
    root_node_id = f"nod_{representation_key}_document"
    quality_id = f"pqr_{representation_key}_quality_v1"
    logical_text, nodes, source_regions = _canonical_layout_records(
        representation_id=representation_id,
        representation_key=representation_key,
        text_view_id=text_view_id,
        layout_items=layout_items,
    )
    text_digest = hashlib.sha256(logical_text.encode("utf-8")).hexdigest()
    text_view = TextView(
        id=text_view_id,
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=text_digest,
        text=logical_text,
        normalization_policy="docling_layout_text_v1",
    )
    root = DocumentNode(
        id=root_node_id,
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        structural_path=("document",),
        text_view_id=text_view_id,
        start_char=0,
        end_char=len(logical_text),
    )
    nodes = (root, *nodes)
    edges = tuple(
        DocumentEdge(
            id=f"deg_{representation_key}_document_to_{node.order_index:04d}",
            representation_id=representation_id,
            from_node_id=root.id,
            to_node_id=node.id,
            edge_type="contains",
            provenance_kind=DocumentEdgeProvenanceKind.PARSER,
            provenance_id="docling_layout_v1",
        )
        for node in nodes[1:]
    )
    quality_report = _quality_report(
        quality_id=quality_id,
        representation_id=representation_id,
        page_geometry=page_geometry,
        nodes=nodes,
        source_regions=source_regions,
        logical_text=logical_text,
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
                nodes=nodes,
                edges=edges,
                source_regions=source_regions,
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=nodes,
        edges=edges,
        source_regions=source_regions,
        quality_report=quality_report,
    )


def _canonical_layout_records(
    *,
    representation_id: str,
    representation_key: str,
    text_view_id: str,
    layout_items: tuple[_LayoutItem, ...],
) -> tuple[str, tuple[DocumentNode, ...], tuple[SourceRegion, ...]]:
    text_parts: list[str] = []
    nodes: list[DocumentNode] = []
    source_regions: list[SourceRegion] = []
    current_section_path: tuple[str, ...] = ()
    cursor = 0
    for order_index, item in enumerate(layout_items, start=1):
        if text_parts:
            text_parts.append("\n")
            cursor += 1
        start_char = cursor
        text_parts.append(item.text)
        cursor += len(item.text)
        end_char = cursor
        if item.node_type == "heading":
            current_section_path = (item.text,)
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
                    rotation_applied=0,
                )
            )
        nodes.append(
            DocumentNode(
                id=f"nod_{representation_key}_{order_index:04d}",
                representation_id=representation_id,
                parent_node_id=f"nod_{representation_key}_document",
                node_type=item.node_type,
                order_index=order_index,
                structural_path=("document", item.node_type, f"{order_index:04d}"),
                section_path=current_section_path,
                text_view_id=text_view_id,
                start_char=start_char,
                end_char=end_char,
                source_region_ids=tuple(region_ids),
                source_page_numbers=tuple(sorted({region.page_number for region in item.regions})),
                source_text_digest=hashlib.sha256(item.text.encode("utf-8")).hexdigest(),
            )
        )
    return "".join(text_parts), tuple(nodes), tuple(source_regions)


def _quality_report(
    *,
    quality_id: str,
    representation_id: str,
    page_geometry: tuple[_PageGeometry, ...],
    nodes: tuple[DocumentNode, ...],
    source_regions: tuple[SourceRegion, ...],
    logical_text: str,
) -> ParseQualityReport:
    expected_pages = {page.page_number for page in page_geometry}
    covered_pages = {region.page_number for region in source_regions}
    content_nodes = nodes[1:]
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
            "reading_order_node_count": len(content_nodes),
            "heading_node_count": sum(node.node_type == "heading" for node in content_nodes),
            "paragraph_node_count": sum(node.node_type == "paragraph" for node in content_nodes),
            "furniture_node_count": sum(node.node_type == "furniture" for node in content_nodes),
            "source_region_count": len(source_regions),
        },
        issues=tuple(issues),
        analyzability=(
            RepresentationAnalyzability.ACCEPTABLE
            if not issues
            else RepresentationAnalyzability.BLOCKED
        ),
    )
