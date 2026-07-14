"""Reviewer-facing PDF evidence overlay contracts over authoritative artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from kotekomi_domain import (
    Document,
    DocumentRepresentationBundle,
    EvidenceTarget,
    PdfPageAccountingBundle,
    ProcessingTaskFingerprint,
    RawBlob,
    SourceCoordinateSystem,
)

from kotekomi_application.evidence_targets import (
    EvidenceTargetReferenceLedger,
    validate_evidence_target_record,
)


@dataclass(frozen=True)
class PdfEvidenceRectangle:
    source_region_id: str
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class PdfEvidenceOverlaySpec:
    evidence_target_id: str
    representation_id: str
    archived_pdf_object_id: str
    archived_pdf_digest: str
    page_number: int
    page_width: float
    page_height: float
    crop_left: float
    crop_top: float
    crop_right: float
    crop_bottom: float
    rotation: int
    coordinate_system: SourceCoordinateSystem
    rectangles: tuple[PdfEvidenceRectangle, ...]
    exact_quote: str
    structural_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class PdfPixelRectangle:
    source_region_id: str
    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class RenderedPdfEvidenceOverlay:
    spec: PdfEvidenceOverlaySpec
    renderer_id: str
    image_width: int
    image_height: int
    pixel_rectangles: tuple[PdfPixelRectangle, ...]
    png_bytes: bytes
    png_digest: str


class PdfEvidenceOverlayLedger(EvidenceTargetReferenceLedger, Protocol):
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_processing_task_fingerprint(
        self, record_id: str
    ) -> ProcessingTaskFingerprint | None: ...
    def get_raw_blob(self, record_id: str) -> RawBlob | None: ...
    def find_latest_complete_pdf_preflight_report_for_task(
        self, task_fingerprint_id: str
    ) -> object | None: ...
    def get_pdf_page_accounting_bundle(
        self, preflight_report_id: str
    ) -> PdfPageAccountingBundle | None: ...


class PdfEvidenceOverlayArchive(Protocol):
    def read_raw_source(self, source_id: str) -> bytes: ...


class PdfEvidenceOverlayRenderer(Protocol):
    def render(
        self, spec: PdfEvidenceOverlaySpec, archived_pdf_bytes: bytes
    ) -> RenderedPdfEvidenceOverlay: ...


def get_pdf_evidence_overlay_spec(
    evidence_target_id: str,
    ledger_repository: PdfEvidenceOverlayLedger,
) -> PdfEvidenceOverlaySpec:
    """Resolve an EvidenceTarget to archived bytes and canonical page geometry."""

    target = ledger_repository.get_evidence_target(evidence_target_id)
    if target is None:
        raise ValueError(f"EvidenceTarget not found: {evidence_target_id}")
    validate_evidence_target_record(target, ledger_repository)
    bundle = ledger_repository.get_document_representation_bundle(target.representation_id)
    assert bundle is not None
    selected_regions = tuple(
        region for region in bundle.source_regions if region.id in target.pdf_region_ids
    )
    if not selected_regions:
        raise ValueError("PDF evidence overlay requires at least one PDF source region.")
    page_numbers = {region.page_number for region in selected_regions}
    coordinate_systems = {region.coordinate_system for region in selected_regions}
    if len(page_numbers) != 1 or len(coordinate_systems) != 1:
        raise ValueError("One PDF evidence overlay must target one canonical page system.")
    coordinate_system = next(iter(coordinate_systems))
    if coordinate_system is not SourceCoordinateSystem.PDF_POINTS_TOP_LEFT_V1:
        raise ValueError("PDF evidence overlay requires canonical top-left coordinates.")
    task = ledger_repository.get_processing_task_fingerprint(
        bundle.representation.processing_task_fingerprint_id
    )
    if task is None:
        raise ValueError("PDF evidence overlay references a missing processing task.")
    raw_blob = ledger_repository.get_raw_blob(task.input_blob_id)
    if raw_blob is None:
        raise ValueError("PDF evidence overlay references a missing archived RawBlob.")
    report = ledger_repository.find_latest_complete_pdf_preflight_report_for_task(task.id)
    if report is None:
        raise ValueError("PDF evidence overlay requires complete page accounting.")
    report_id = getattr(report, "id", None)
    if not isinstance(report_id, str):
        raise ValueError("PDF evidence overlay received invalid page accounting metadata.")
    accounting = ledger_repository.get_pdf_page_accounting_bundle(report_id)
    if accounting is None:
        raise ValueError("PDF evidence overlay page accounting is incomplete.")
    page_number = next(iter(page_numbers))
    page = next(
        (item for item in accounting.page_inventory if item.page_index == page_number), None
    )
    if page is None:
        raise ValueError("PDF evidence overlay page is outside the authoritative inventory.")
    if any(
        region.page_width != page.media_width or region.page_height != page.media_height
        for region in selected_regions
    ):
        raise ValueError("PDF evidence region geometry disagrees with page accounting.")
    return PdfEvidenceOverlaySpec(
        evidence_target_id=target.id,
        representation_id=target.representation_id,
        archived_pdf_object_id=raw_blob.id,
        archived_pdf_digest=raw_blob.digest,
        page_number=page_number,
        page_width=page.media_width,
        page_height=page.media_height,
        crop_left=page.crop_left,
        crop_top=page.crop_top,
        crop_right=page.crop_right,
        crop_bottom=page.crop_bottom,
        rotation=page.rotation,
        coordinate_system=coordinate_system,
        rectangles=tuple(
            PdfEvidenceRectangle(
                region.id,
                region.left,
                region.top,
                region.right,
                region.bottom,
            )
            for region in selected_regions
        ),
        exact_quote=target.exact_text,
        structural_node_ids=target.node_ids,
    )


def render_pdf_evidence_overlay(
    evidence_target_id: str,
    ledger_repository: PdfEvidenceOverlayLedger,
    archive: PdfEvidenceOverlayArchive,
    renderer: PdfEvidenceOverlayRenderer,
) -> RenderedPdfEvidenceOverlay:
    """Render a reviewer overlay without invoking the PDF parser."""

    spec = get_pdf_evidence_overlay_spec(evidence_target_id, ledger_repository)
    pdf_bytes = archive.read_raw_source(spec.archived_pdf_object_id)
    if hashlib.sha256(pdf_bytes).hexdigest() != spec.archived_pdf_digest:
        raise ValueError("Archived PDF bytes do not match the authoritative RawBlob digest.")
    rendered = renderer.render(spec, pdf_bytes)
    if rendered.spec != spec:
        raise ValueError("PDF evidence renderer returned an overlay for a different spec.")
    if hashlib.sha256(rendered.png_bytes).hexdigest() != rendered.png_digest:
        raise ValueError("PDF evidence renderer returned an invalid PNG digest.")
    return rendered
