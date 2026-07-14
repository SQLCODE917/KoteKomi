"""Integrated public-path sign-off for the authoritative PDF gold matrix."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pytest
from kotekomi_adapters import (
    LocalArchiveStore,
    PdfiumEvidenceOverlayRenderer,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import (
    LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
    AnalysisCoverageState,
    AnalysisRunInput,
    AnalysisRunItemInput,
    AnalysisUnitPlanningInput,
    BoundedExtractionInput,
    BoundedExtractionOutcome,
    BuildIdentity,
    CaptureRequest,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ExecutionSetting,
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelTaskRequest,
    ModelTaskResponse,
    PdfAnalysisAdmissionDecision,
    PdfAnalysisAdmissionOutcome,
    PdfAnalysisCoverageStatus,
    PdfIngestInput,
    PdfParseInput,
    PdfParseResult,
    PdfProcessorIdentity,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    StagedClaimTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    Uuid4ProcessingAttemptIdFactory,
    build_context_manifest,
    build_coverage_report,
    capture_identity,
    capture_source,
    evaluate_pdf_analysis_admission,
    freeze_analysis_plan,
    generation_parameters_digest,
    ingest_pdf,
    model_identity_snapshot_digest,
    plan_analysis_units,
    record_analysis_item_attempt,
    render_pdf_evidence_overlay,
    run_bounded_extraction,
    staged_claim_output_schema_bytes,
    start_analysis_run,
    submit_grounded_candidate_batch,
    verify_evidence_target,
)
from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentationBundle,
    DocumentVersionKind,
    ModelRunStatus,
    PdfPageInventoryDisposition,
    PdfPageQualityStatus,
    ProcessingArtifactKind,
    ProcessingAttemptStatus,
    ProcessingStage,
    RepresentationAnalyzability,
    SourceType,
    TableEvidenceSelector,
    TextViewKind,
)
from PIL import Image

from .test_pdf_production_path import FixturePdfParser

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pdf"
MANIFEST = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
MATRIX_PATH = FIXTURE_ROOT / "gold" / "integrated_gold_matrix_v1.json"
MATRIX = json.loads(MATRIX_PATH.read_text())
ROWS = tuple(MATRIX["rows"])
RENDER_OVERLAY_ROWS = {
    "born_digital_press_release",
    "image_only_scan",
    "adversarial_layout",
    "complex_table",
}
NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
BUILD_IDENTITY = BuildIdentity("pdf-gold-matrix", "pdf-gold-matrix", "8" * 64, "1")
PROMPT_BYTES = b"Return a bounded grounded claim or explicitly abstain."
ABSTENTION_OUTPUT = json.dumps(
    {
        "kind": "abstain",
        "schema_id": "staged_claim_output_v1",
        "reason": "gold matrix fixture produced no fixture-owned semantic claim",
    },
    separators=(",", ":"),
).encode()


@dataclass(frozen=True)
class _CapturedPdf:
    document_id: str
    raw_blob_id: str
    source_id: str


class _FixedClock:
    def now(self) -> datetime:
        return NOW + timedelta(days=1)


class _ExactTokenizer:
    tokenizer_id = "pdf_gold_matrix_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


def _model_identity() -> ModelIdentitySnapshot:
    return ModelIdentitySnapshot(
        "pdf_gold_matrix_fixture_model",
        "9" * 64,
        "fixture-runtime-v1",
        _ExactTokenizer.tokenizer_id,
        (ExecutionSetting("seed", 7), ExecutionSetting("temperature", 0)),
    )


def _execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=_model_identity(),
        generation_parameters=(
            ExecutionSetting("seed", 7),
            ExecutionSetting("temperature", 0),
        ),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=manifest.schema_id,
        schema_digest=manifest.schema_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="staged_claim_output_v1",
    )


class _AbstainingRuntime:
    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return _model_identity()

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        return ModelTaskResponse(
            ABSTENTION_OUTPUT,
            ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(
                    task.execution_spec.model_identity
                ),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=task.rendered_input_digest,
                input_token_count=len(task.rendered_input.decode().split()),
                output_token_count=len(ABSTENTION_OUTPUT.decode().split()),
            ),
        )


class _InvalidCoordinateParser:
    def __init__(self) -> None:
        self._delegate = FixturePdfParser()
        self.results: list[PdfParseResult] = []

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        return self._delegate.processing_identity(policy_id)

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        if self.results:
            return self.results[0]
        result = self._delegate.parse(parse_input)
        bundle = result.representation_bundle
        assert bundle is not None and bundle.source_regions
        first = bundle.source_regions[0].model_copy(update={"left": -1.0})
        invalid = PdfParseResult(
            preflight=result.preflight,
            representation_bundle=bundle.model_copy(
                update={"source_regions": (first, *bundle.source_regions[1:])}
            ),
            transformation_payloads=result.transformation_payloads,
            blocking_reasons=result.blocking_reasons,
        )
        self.results.append(invalid)
        return invalid


def _fixture(row: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    entry = next(item for item in MANIFEST["fixtures"] if item["fixture_id"] == row["fixture_id"])
    raw = (FIXTURE_ROOT / entry["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry["local_sha256"]
    return entry, raw


def _capture(
    ledger_path: Path,
    archive: LocalArchiveStore,
    row_id: str,
    raw_pdf: bytes,
) -> _CapturedPdf:
    digest = hashlib.sha256(raw_pdf).hexdigest()
    request = CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title=f"Integrated PDF gold row {row_id}",
            stable_key=f"pdf-gold-{row_id}",
            uri=f"fixture://pdf-gold/{row_id}.pdf",
        ),
        payload=raw_pdf,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{digest}.bin",
        idempotency_key=f"pdf-gold-{row_id}-v1",
        retrieval_method="fixture",
        requested_uri=f"fixture://pdf-gold/{row_id}.pdf",
        canonical_uri=f"fixture://pdf-gold/{row_id}.pdf",
        provider_item_id=None,
        provider_version=None,
        version_kind=DocumentVersionKind.ORIGINAL,
        publication_time=None,
        provider_update_time=None,
        captured_at=NOW,
        transaction_time=NOW,
        rights_profile_id=None,
        embargo_until=None,
        request_metadata={},
        response_metadata={},
    )
    policy = StableSourceIdentityPolicy()
    identity = capture_identity(request, policy)
    archive.put_if_absent_or_identical(identity.raw_blob_id, raw_pdf, digest)
    with sqlite_ledger_transaction(ledger_path) as repository:
        result = capture_source(request, repository, policy)
    return _CapturedPdf(result.document.id, result.raw_blob.id, result.source.id)


def _ingest_input(captured: _CapturedPdf, raw_pdf: bytes, row_id: str) -> PdfIngestInput:
    return PdfIngestInput(
        document_id=captured.document_id,
        raw_bytes=raw_pdf,
        policy_id=f"pdf_gold_matrix_{row_id}_v1",
        ingested_at=NOW,
        raw_blob_id=captured.raw_blob_id,
        build_identity=BUILD_IDENTITY,
    )


def _parser(row: dict[str, Any]) -> DoclingPdfParser:
    return DoclingPdfParser(
        DoclingPdfParserConfig(enable_table_structure=row.get("parser_mode") == "table_structure")
    )


def _only_task_id(ledger_path: Path) -> str:
    with sqlite3.connect(ledger_path) as connection:
        rows = connection.execute("SELECT id FROM processing_task_fingerprints").fetchall()
    assert len(rows) == 1
    return str(rows[0][0])


def _assert_page_accounting(row: dict[str, Any], accounting: Any) -> None:
    report = accounting.preflight_report
    assert report.page_count == row["expected_page_count"]
    assert len(accounting.page_inventory) == report.page_count
    assert len(accounting.page_extraction_statuses) == report.page_count
    assert [status.page_index for status in accounting.page_extraction_statuses] == list(
        range(1, report.page_count + 1)
    )
    actual_paths = [status.extraction_path.value for status in accounting.page_extraction_statuses]
    assert actual_paths == row["expected_page_paths"], [
        (
            status.page_index,
            status.extraction_path.value,
            status.status.value,
            status.policy_reasons,
        )
        for status in accounting.page_extraction_statuses
    ]
    assert sorted(
        {item.activity_type.value for item in accounting.transformation_artifacts}
    ) == sorted(row["expected_transformations"])


def _first_evidence_node(
    bundle: DocumentRepresentationBundle, *, rotated: bool = False
) -> tuple[DocumentNode, str]:
    views = {view.id: view for view in bundle.text_views}
    regions = {region.id: region for region in bundle.source_regions}
    node = next(
        item
        for item in bundle.nodes
        if item.node_type == "paragraph"
        and item.source_region_ids
        and item.end_char > item.start_char
        and (
            not rotated
            or any(regions[region_id].rotation_applied != 0 for region_id in item.source_region_ids)
        )
    )
    return node, views[node.text_view_id].text[node.start_char : node.end_char]


def _table_evidence_candidate(
    bundle: DocumentRepresentationBundle,
) -> tuple[DocumentNode, str, tuple[str, ...], tuple[str, ...], TableEvidenceSelector]:
    cells = {cell.id: cell for cell in bundle.table_cells}
    nodes = {node.id: node for node in bundle.nodes}
    cell = next(
        item
        for item in bundle.table_cells
        if item.node_id is not None
        and item.row_header_cell_ids
        and item.column_header_cell_ids
    )
    header_cells = tuple(
        cells[cell_id]
        for cell_id in (*cell.row_header_cell_ids, *cell.column_header_cell_ids)
    )
    assert cell.node_id is not None
    assert all(header.node_id is not None for header in header_cells)
    node_ids = (cell.node_id, *(header.node_id for header in header_cells if header.node_id))
    selected_nodes = tuple(nodes[node_id] for node_id in node_ids)
    node = selected_nodes[0]
    view = next(view for view in bundle.text_views if view.id == node.text_view_id)
    text = view.text[node.start_char : node.end_char]
    region_ids = tuple(
        dict.fromkeys(
            region_id
            for selected_node in selected_nodes
            for region_id in selected_node.source_region_ids
        )
    )
    return (
        node,
        text,
        node_ids,
        region_ids,
        TableEvidenceSelector(
            table_id=cell.table_id,
            cell_id=cell.id,
            row_header_cell_ids=cell.row_header_cell_ids,
            column_header_cell_ids=cell.column_header_cell_ids,
        ),
    )


def _submit_overlay(
    *,
    row_id: str,
    captured: _CapturedPdf,
    bundle: DocumentRepresentationBundle,
    repository: Any,
) -> tuple[str, str]:
    table_selector = None
    if row_id == "complex_table":
        node, text, node_ids, region_ids, table_selector = _table_evidence_candidate(bundle)
    else:
        node, text = _first_evidence_node(
            bundle, rotated=row_id == "adversarial_layout"
        )
        node_ids = (node.id,)
        region_ids = node.source_region_ids
    outcome = submit_grounded_candidate_batch(
        GroundedCandidateBatchInput(
            task_fingerprint=hashlib.sha256(f"overlay:{row_id}".encode()).hexdigest(),
            source_id=captured.source_id,
            document_id=captured.document_id,
            representation_id=bundle.representation.id,
            model_name="deterministic-pdf-gold-overlay",
            prompt_id="pdf-gold-overlay-v1",
            validator_version="pdf-gold-overlay-validator-v1",
            submitted_at=NOW,
            organizations=(GroundedOrganizationCandidate("subject", "Fixture Subject"),),
            evidence=(
                GroundedEvidenceCandidate(
                    local_id="evidence",
                    text_view_id=node.text_view_id,
                    start_char=node.start_char,
                    end_char=node.end_char,
                    exact_text=text,
                    node_ids=node_ids,
                    pdf_region_ids=region_ids,
                    table_selector=table_selector,
                ),
            ),
            assertions=(
                GroundedAssertionCandidate(
                    local_id="claim",
                    subject_organization_local_id="subject",
                    evidence_local_id="evidence",
                    predicate="appears_in_pdf_gold_fixture",
                    object_value=row_id,
                ),
            ),
        ),
        repository,
    )
    return (
        outcome.evidence_target_ids_by_local_id["evidence"],
        outcome.validation_attempt_ids_by_evidence_local_id["evidence"],
    )


def _complete_analysis(
    *,
    row_id: str,
    captured: _CapturedPdf,
    bundle: DocumentRepresentationBundle,
    repository: Any,
    archive: LocalArchiveStore,
) -> tuple[str, dict[str, ContextManifest]]:
    plan = plan_analysis_units(
        AnalysisUnitPlanningInput(
            bundle.representation.id,
            f"pdf_gold_plan_{row_id}_v1",
            "claim_extraction",
            max_focus_nodes_per_unit=64,
        ),
        repository,
    )
    frozen = freeze_analysis_plan(plan, repository)
    manifests: dict[str, ContextManifest] = {}
    runs: dict[str, BoundedExtractionOutcome] = {}
    for index, unit in enumerate(plan.units):
        manifest = build_context_manifest(
            ContextManifestInput(
                analysis_unit=unit,
                model_profile=ContextModelProfile("pdf_gold_matrix_fixture_model", 65_536, 64, 16),
                prompt_id="pdf_gold_claim_extraction_v1",
                prompt_bytes=PROMPT_BYTES,
                schema_id="staged_claim_output_v1",
                schema_bytes=staged_claim_output_schema_bytes(),
                renderer_version="pdf_gold_renderer_v1",
            ),
            repository,
            _ExactTokenizer(),
        ).manifest
        assert manifest.status is ContextManifestStatus.READY
        manifests[unit.id] = manifest
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=captured.source_id,
                document_id=captured.document_id,
                representation_id=bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=PROMPT_BYTES,
                execution_spec=_execution_spec(manifest),
                validator_version="pdf-gold-output-validator-v1",
                started_at=NOW + timedelta(seconds=index),
                completed_at=NOW + timedelta(seconds=index + 1),
            ),
            repository,
            archive,
            _AbstainingRuntime(),
            Uuid4ModelRunIdFactory(),
            _ExactTokenizer(),
            StagedClaimTaskSchemaRegistry(),
        )
        assert outcome.model_run.status is ModelRunStatus.ABSTAINED
        runs[unit.id] = outcome
    analysis_run = start_analysis_run(
        AnalysisRunInput(
            document_id=captured.document_id,
            frozen_plan_id=frozen.id,
            coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
            started_at=NOW,
            items=tuple(
                AnalysisRunItemInput(
                    analysis_unit_id=unit.id,
                    task_type=unit.task_type,
                    input_fingerprint=runs[unit.id].extraction_task.task_fingerprint,
                    expected_manifest_id=manifests[unit.id].id,
                )
                for unit in plan.units
            ),
        ),
        repository,
    )
    for unit in plan.units:
        record_analysis_item_attempt(
            analysis_run_id=analysis_run.id,
            analysis_unit_id=unit.id,
            model_run_id=runs[unit.id].model_run.id,
            ledger_repository=repository,
        )
    report = build_coverage_report(analysis_run.id, repository)
    assert report.state is AnalysisCoverageState.COMPLETE, (
        report.represented_page_numbers,
        tuple(
            (
                item.analysis_unit_id,
                item.terminal_status.value,
                item.blocking_reason,
                item.abstention_reason,
            )
            for item in report.coverage_records
        ),
    )
    assert report.total_pages == bundle.quality_report.metric_values["page_count"]
    assert report.represented_page_numbers == tuple(range(1, report.total_pages + 1))
    assert report.orphan_model_run_ids == ()
    assert report.integrity_failure_reasons == ()
    return analysis_run.id, manifests


def _assert_specialized_gold(
    row: dict[str, Any],
    bundle: DocumentRepresentationBundle,
    manifests: dict[str, ContextManifest],
) -> None:
    if "expected_tables" in row:
        assert len(bundle.tables) == row["expected_tables"]
        assert len(bundle.table_fragments) == row["expected_table_fragments"]
    if "expected_footnote_references" in row:
        footnotes = [item for item in bundle.references if item.kind == "footnote"]
        assert len(footnotes) == row["expected_footnote_references"]
        nodes_by_id = {node.id: node for node in bundle.nodes}
        assert (
            nodes_by_id[footnotes[0].marker_node_id].source_page_numbers[0]
            < nodes_by_id[footnotes[0].target_node_id].source_page_numbers[0]
        )
        views = {view.id: view for view in bundle.text_views}
        focus = next(
            node
            for node in bundle.nodes
            if "CR guides the response described several pages after its definition"
            in views[node.text_view_id].text[node.start_char : node.end_char]
        )
        manifest = next(
            item
            for item in manifests.values()
            if isinstance(item.analysis_unit_payload["focus_node_ids"], list)
            and focus.id in item.analysis_unit_payload["focus_node_ids"]
        )
        selected_node_ids = {
            node_id
            for candidate in manifest.selected_candidates
            for node_id in candidate.source_node_ids
        }
        definition = next(
            node
            for node in bundle.nodes
            if "Community resilience (CR) means"
            in views[node.text_view_id].text[node.start_char : node.end_char]
        )
        assert definition.id in selected_node_ids
    if row["row_id"] == "adversarial_layout":
        gold = json.loads(
            (FIXTURE_ROOT / "gold" / "adversarial_columns_hierarchy_v1.json").read_text()
        )
        logical = next(view for view in bundle.text_views if view.kind is TextViewKind.LOGICAL)
        positions = [logical.text.index(text) for text in gold["logical_analysis_lines"]]
        assert positions == sorted(positions)
        assert all(text not in logical.text for text in gold["forbidden_logical_lines"])


@pytest.mark.parametrize("row", ROWS, ids=lambda row: cast(dict[str, Any], row)["row_id"])
def test_integrated_pdf_gold_matrix(row: dict[str, Any], tmp_path: Path) -> None:
    _, raw_pdf = _fixture(row)
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    captured = _capture(ledger_path, archive, row["row_id"], raw_pdf)
    ingest_input = _ingest_input(captured, raw_pdf, row["row_id"])
    bundle: DocumentRepresentationBundle | None = None
    analysis_run_id: str | None = None
    evidence_id: str | None = None
    validation_id: str | None = None
    admission: PdfAnalysisAdmissionOutcome | None = None

    if row.get("parser_mode") == "invalid_coordinates":
        parser = _InvalidCoordinateParser()
        with pytest.raises(ValueError):
            with sqlite_ledger_transaction(ledger_path) as repository:
                ingest_pdf(
                    ingest_input,
                    repository,
                    parser,
                    Uuid4ProcessingAttemptIdFactory(),
                    _FixedClock(),
                    archive,
                )
        assert parser.results[0].preflight.page_count == row["expected_page_count"]
        task_id = _only_task_id(ledger_path)
        with sqlite_ledger_transaction(ledger_path) as repository:
            (attempt,) = repository.list_processing_attempts(task_id)
            outcome = repository.get_processing_attempt_outcome(attempt.id)
            assert outcome is not None
            assert outcome.status is ProcessingAttemptStatus.FAILED
            assert outcome.failure is not None
            assert outcome.failure.code == row["expected_failure_code"]
            assert outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION
            assert repository.list_document_representations() == ()
            (report_ref,) = tuple(
                artifact
                for artifact in outcome.output_artifacts
                if artifact.kind is ProcessingArtifactKind.PDF_PREFLIGHT_REPORT
            )
            first_failed_accounting = repository.get_pdf_page_accounting_bundle(
                report_ref.artifact_id
            )
            assert first_failed_accounting is not None
            assert (
                first_failed_accounting.preflight_report.page_inventory_disposition
                is PdfPageInventoryDisposition.COMPLETE
            )
            assert first_failed_accounting.preflight_report.page_count == 1
            (failed_status,) = first_failed_accounting.page_extraction_statuses
            assert failed_status.extraction_path.value == row["expected_page_paths"][0]
            assert failed_status.status is PdfPageQualityStatus.BLOCKED
            assert failed_status.policy_reasons == ("representation_validation_failed",)
            assert row["expected_representation_disposition"] == "not_committed"
        with pytest.raises(ValueError):
            with sqlite_ledger_transaction(ledger_path) as repository:
                ingest_pdf(
                    ingest_input,
                    repository,
                    parser,
                    Uuid4ProcessingAttemptIdFactory(),
                    _FixedClock(),
                    archive,
                )
        with sqlite_ledger_transaction(ledger_path) as repository:
            attempts = repository.list_processing_attempts(task_id)
            assert len(attempts) == 2
            outcomes = tuple(
                repository.get_processing_attempt_outcome(item.id) for item in attempts
            )
            assert all(
                item is not None
                and item.status is ProcessingAttemptStatus.FAILED
                and item.failure is not None
                and item.failure.code == row["expected_failure_code"]
                and item.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION
                for item in outcomes
            )
            assert repository.list_document_representations() == ()
            report_refs = tuple(
                artifact
                for item in outcomes
                if item is not None
                for artifact in item.output_artifacts
                if artifact.kind is ProcessingArtifactKind.PDF_PREFLIGHT_REPORT
            )
            assert len(report_refs) == 2
            report_ids = {report_ref.artifact_id for report_ref in report_refs}
            assert first_failed_accounting.preflight_report.id in report_ids
            assert len(report_ids) == 2
            assert (
                repository.get_pdf_page_accounting_bundle(
                    first_failed_accounting.preflight_report.id
                )
                == first_failed_accounting
            )
            (second_report_id,) = report_ids - {first_failed_accounting.preflight_report.id}
            second_failed_accounting = repository.get_pdf_page_accounting_bundle(
                second_report_id
            )
            assert second_failed_accounting is not None
            assert (
                second_failed_accounting.page_extraction_statuses[0].extraction_path.value
                == row["expected_page_paths"][0]
            )
            assert second_failed_accounting.page_extraction_statuses[0].policy_reasons == (
                "representation_validation_failed",
            )
        assert archive.read_raw_source(captured.raw_blob_id) == raw_pdf
        return

    with sqlite_ledger_transaction(ledger_path) as repository:
        first = ingest_pdf(
            ingest_input,
            repository,
            _parser(row),
            Uuid4ProcessingAttemptIdFactory(),
            _FixedClock(),
            archive,
        )
        accounting = repository.get_pdf_page_accounting_bundle(first.preflight_report_id)
        assert accounting is not None
        _assert_page_accounting(row, accounting)
        if first.representation_id is None:
            assert row["expected_quality"] == "blocked"
            assert row["expected_blocking_reason"] in first.blocking_reasons
            assert repository.list_document_representations() == ()
            report_identity = accounting.preflight_report.id
        else:
            bundle = repository.get_document_representation_bundle(first.representation_id)
            assert bundle is not None
            assert {view.kind for view in bundle.text_views} == {
                TextViewKind.LOGICAL,
                TextViewKind.DISPLAY,
            }
            admission = evaluate_pdf_analysis_admission(first.representation_id, repository)
            if row["expected_quality"] == "degraded":
                assert admission.coverage_status.value == row["expected_coverage"]
                assert (
                    bundle.quality_report.analyzability
                    is RepresentationAnalyzability.DEGRADED
                )
                assert (
                    admission.decision
                    is PdfAnalysisAdmissionDecision.REQUIRES_REVIEW
                )
                assert (
                    admission.coverage_status
                    is PdfAnalysisCoverageStatus.PARSE_QUALITY_REQUIRES_REVIEW
                )
                report_identity = admission
            else:
                assert row["expected_quality"] == "acceptable"
                assert (
                    bundle.quality_report.analyzability
                    is RepresentationAnalyzability.ACCEPTABLE
                )
                assert admission.decision is PdfAnalysisAdmissionDecision.ADMITTED
                analysis_run_id, manifests = _complete_analysis(
                    row_id=row["row_id"],
                    captured=captured,
                    bundle=bundle,
                    repository=repository,
                    archive=archive,
                )
                report = build_coverage_report(analysis_run_id, repository)
                report_identity = report.report_digest
                _assert_specialized_gold(row, bundle, manifests)
                evidence_id, validation_id = _submit_overlay(
                    row_id=row["row_id"],
                    captured=captured,
                    bundle=bundle,
                    repository=repository,
                )
                evidence = repository.get_evidence_target(evidence_id)
                validation = repository.get_evidence_validation_attempt(validation_id)
                assert evidence is not None and validation is not None
                assert verify_evidence_target(evidence, validation, repository).valid

    reopened_archive = LocalArchiveStore(tmp_path / "archive")
    with sqlite_ledger_transaction(ledger_path) as repository:
        replayed = repository.get_pdf_page_accounting_bundle(first.preflight_report_id)
        assert replayed == accounting
        if first.representation_id is None:
            assert replayed is not None
            assert replayed.preflight_report.id == report_identity
        else:
            assert bundle is not None
            replayed_bundle = repository.get_document_representation_bundle(first.representation_id)
            assert replayed_bundle == bundle
            if row["expected_quality"] == "degraded":
                assert admission is not None
                assert (
                    evaluate_pdf_analysis_admission(first.representation_id, repository)
                    == report_identity
                )
            else:
                assert analysis_run_id is not None
                assert evidence_id is not None
                assert validation_id is not None
                assert (
                    build_coverage_report(analysis_run_id, repository).report_digest
                    == report_identity
                )
                replayed_evidence = repository.get_evidence_target(evidence_id)
                replayed_validation = repository.get_evidence_validation_attempt(validation_id)
                assert replayed_evidence is not None and replayed_validation is not None
                assert verify_evidence_target(
                    replayed_evidence, replayed_validation, repository
                ).valid
                if row["row_id"] not in RENDER_OVERLAY_ROWS:
                    rendered = None
                else:
                    original_parse = DoclingPdfParser.parse

                    def parser_must_not_run(*_args: object, **_kwargs: object) -> object:
                        raise AssertionError("Reviewer rendering must not invoke Docling.")

                    DoclingPdfParser.parse = parser_must_not_run  # type: ignore[method-assign]
                    try:
                        rendered = render_pdf_evidence_overlay(
                            evidence_id,
                            repository,
                            reopened_archive,
                            PdfiumEvidenceOverlayRenderer(),
                        )
                    finally:
                        DoclingPdfParser.parse = original_parse  # type: ignore[method-assign]
                if rendered is not None:
                    assert rendered.spec.exact_quote == replayed_evidence.exact_text
                    assert rendered.spec.structural_node_ids == replayed_evidence.node_ids
                    assert rendered.pixel_rectangles
                    image = Image.open(BytesIO(rendered.png_bytes)).convert("RGB")
                    assert image.size == (rendered.image_width, rendered.image_height)
                    for rectangle in rendered.pixel_rectangles:
                        assert image.getpixel((rectangle.left, rectangle.top)) == (255, 0, 0)
                    if row["row_id"] == "adversarial_layout":
                        assert rendered.spec.rotation in {90, 180, 270}
                    if row["row_id"] == "complex_table":
                        assert replayed_evidence.table_selector is not None
        rerun = ingest_pdf(
            ingest_input,
            repository,
            _parser(row),
            Uuid4ProcessingAttemptIdFactory(),
            _FixedClock(),
            reopened_archive,
        )
        assert rerun.representation_id == first.representation_id
        assert rerun.preflight_report_id != first.preflight_report_id
        rerun_accounting = repository.get_pdf_page_accounting_bundle(rerun.preflight_report_id)
        assert rerun_accounting is not None
        _assert_page_accounting(row, rerun_accounting)
        assert repository.get_pdf_page_accounting_bundle(first.preflight_report_id) == accounting
        if first.representation_id is not None:
            if row["expected_quality"] == "degraded":
                assert (
                    evaluate_pdf_analysis_admission(first.representation_id, repository)
                    == report_identity
                )
            else:
                assert analysis_run_id is not None
                assert (
                    build_coverage_report(analysis_run_id, repository).report_digest
                    == report_identity
                )

    assert reopened_archive.read_raw_source(captured.raw_blob_id) == raw_pdf
    task_id = _only_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        assert len(attempts) == 2
        outcomes = tuple(repository.get_processing_attempt_outcome(item.id) for item in attempts)
        assert all(item is not None for item in outcomes)
        expected = (
            ProcessingAttemptStatus.BLOCKED
            if first.representation_id is None
            else ProcessingAttemptStatus.SUCCEEDED
        )
        assert all(item is not None and item.status is expected for item in outcomes)


def test_integrated_gold_matrix_is_an_exact_fixture_class_partition() -> None:
    required = MATRIX["required_fixture_classes"]
    observed = [fixture_class for row in ROWS for fixture_class in row["classes"]]
    assert len(required) == len(set(required))
    assert len(observed) == len(set(observed))
    assert set(observed) == set(required)
    assert all(
        row["expected_coverage"]
        in {
            "complete",
            "parse_quality_requires_review",
            "blocked_before_analysis",
            "failed_before_analysis",
        }
        for row in ROWS
    )
    assert {row["expected_quality"] for row in ROWS} == {
        "acceptable",
        "degraded",
        "blocked",
        "failed",
    }
    assert RENDER_OVERLAY_ROWS <= {row["row_id"] for row in ROWS}
    assert all(row["evidence_overlay"] for row in ROWS if row["row_id"] in RENDER_OVERLAY_ROWS)
    expected_coverage_by_quality = {
        "acceptable": "complete",
        "degraded": "parse_quality_requires_review",
        "blocked": "blocked_before_analysis",
        "failed": "failed_before_analysis",
    }
    assert all(
        row["expected_coverage"] == expected_coverage_by_quality[row["expected_quality"]]
        for row in ROWS
    )
    assert all(row["evidence_overlay"] == (row["expected_quality"] == "acceptable") for row in ROWS)
