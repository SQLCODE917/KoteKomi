"""Versioned quality-policy routing for PDF analysis admission."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    DocumentRepresentationBundle,
    RepresentationAnalyzability,
    canonical_representation_digest,
)

PDF_ANALYSIS_ADMISSION_POLICY_ID = "pdf_analysis_admission_v1"


class PdfAnalysisAdmissionDecision(StrEnum):
    ADMITTED = "admitted"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED = "blocked"


class PdfAnalysisCoverageStatus(StrEnum):
    ADMITTED = "admitted"
    PARSE_QUALITY_REQUIRES_REVIEW = "parse_quality_requires_review"
    PARSE_QUALITY_BLOCKED = "parse_quality_blocked"


@dataclass(frozen=True)
class PdfAnalysisAdmissionOutcome:
    representation_id: str
    quality_report_id: str
    analyzability: RepresentationAnalyzability
    policy_id: str
    decision: PdfAnalysisAdmissionDecision
    coverage_status: PdfAnalysisCoverageStatus


class PdfAnalysisAdmissionLedger(Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


@dataclass(frozen=True)
class PdfAnalysisAdmissionPolicy:
    """Initial policy: degraded representations require explicit review."""

    policy_id: str = PDF_ANALYSIS_ADMISSION_POLICY_ID

    def decide(
        self, analyzability: RepresentationAnalyzability
    ) -> tuple[PdfAnalysisAdmissionDecision, PdfAnalysisCoverageStatus]:
        if analyzability is RepresentationAnalyzability.ACCEPTABLE:
            return (
                PdfAnalysisAdmissionDecision.ADMITTED,
                PdfAnalysisCoverageStatus.ADMITTED,
            )
        if analyzability is RepresentationAnalyzability.DEGRADED:
            return (
                PdfAnalysisAdmissionDecision.REQUIRES_REVIEW,
                PdfAnalysisCoverageStatus.PARSE_QUALITY_REQUIRES_REVIEW,
            )
        return (
            PdfAnalysisAdmissionDecision.BLOCKED,
            PdfAnalysisCoverageStatus.PARSE_QUALITY_BLOCKED,
        )


def evaluate_pdf_analysis_admission(
    representation_id: str,
    ledger_repository: PdfAnalysisAdmissionLedger,
    policy: PdfAnalysisAdmissionPolicy | None = None,
) -> PdfAnalysisAdmissionOutcome:
    """Evaluate a persisted representation under a pinned admission policy."""

    bundle = ledger_repository.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError(f"Missing PDF DocumentRepresentation: {representation_id}")
    actual_digest = canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
        tables=bundle.tables,
        table_fragments=bundle.table_fragments,
        table_rows=bundle.table_rows,
        table_cells=bundle.table_cells,
        table_annotations=bundle.table_annotations,
        references=bundle.references,
        source_selectors=bundle.source_selectors,
    )
    if actual_digest != bundle.representation.canonical_output_digest:
        raise ValueError("PDF analysis admission found a corrupted representation digest.")
    selected_policy = policy or PdfAnalysisAdmissionPolicy()
    decision, coverage_status = selected_policy.decide(
        bundle.quality_report.analyzability
    )
    return PdfAnalysisAdmissionOutcome(
        representation_id=representation_id,
        quality_report_id=bundle.quality_report.id,
        analyzability=bundle.quality_report.analyzability,
        policy_id=selected_policy.policy_id,
        decision=decision,
        coverage_status=coverage_status,
    )
