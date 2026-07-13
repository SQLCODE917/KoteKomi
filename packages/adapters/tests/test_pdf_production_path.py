import hashlib
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import (
    SQLiteLedgerInitializer,
    SQLiteLedgerRepository,
    sqlite_ledger_transaction,
)
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import (
    BuildIdentity,
    BundleCommitOutcome,
    CaptureRequest,
    PdfIngestInput,
    PdfPagePreflight,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
    PdfProcessorIdentity,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    Uuid4ProcessingAttemptIdFactory,
    capture_source,
    deterministic_representation_id,
    ingest_pdf,
    processing_task_fingerprint,
)
from kotekomi_domain import (
    DocumentEdge,
    DocumentEdgeProvenanceKind,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentVersionKind,
    ParseQualityReport,
    PdfExtractionPath,
    PdfPageAccountingBundle,
    PdfPageQualityStatus,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingStage,
    ProvenanceActivity,
    RepresentationAnalyzability,
    SourceCoordinateSystem,
    SourceRegion,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
RAW_PDF = b"%PDF-1.7\nproduction-path fixture\n"
BUILD_IDENTITY = BuildIdentity("pdf-proof", "pdf-proof", "a" * 64, "1")
POLICY_ID = "pdf_proof_v1"


class FixturePdfParser:
    def __init__(
        self,
        *,
        analyzability: RepresentationAnalyzability = RepresentationAnalyzability.ACCEPTABLE,
        target_document_id: str | None = None,
    ) -> None:
        self._analyzability = analyzability
        self._target_document_id = target_document_id
        self.parse_calls = 0

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        del policy_id
        return PdfProcessorIdentity("fixture_pdf", "1", "b" * 64, "1")

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        self.parse_calls += 1
        bundle = _representation_bundle(
            parse_input,
            analyzability=self._analyzability,
            document_id=self._target_document_id or parse_input.document.id,
        )
        blocking_reasons = (
            ("fixture parser retained diagnostic text but blocked analysis",)
            if self._analyzability is RepresentationAnalyzability.BLOCKED
            else ()
        )
        return PdfParseResult(
            preflight=PdfPreflight(
                parser_name="fixture_pdf",
                parser_version="1",
                preflight_tool="fixture_preflight",
                preflight_tool_version="1",
                encrypted=False,
                page_count=1,
                pages=(
                    PdfPagePreflight(
                        page_index=1,
                        width=612,
                        height=792,
                        rotation=0,
                        embedded_text_character_count=len("PDF production-path text"),
                    ),
                ),
            ),
            representation_bundle=bundle,
            blocking_reasons=blocking_reasons,
        )


class InterruptedFixturePdfParser(FixturePdfParser):
    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        del parse_input
        self.parse_calls += 1
        raise KeyboardInterrupt("simulated PDF process interruption")


class OmittedPageBlockedFixturePdfParser(FixturePdfParser):
    def __init__(self) -> None:
        super().__init__(analyzability=RepresentationAnalyzability.BLOCKED)

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        result = super().parse(parse_input)
        first_page = result.preflight.pages[0]
        return PdfParseResult(
            preflight=PdfPreflight(
                parser_name=result.preflight.parser_name,
                parser_version=result.preflight.parser_version,
                preflight_tool=result.preflight.preflight_tool,
                preflight_tool_version=result.preflight.preflight_tool_version,
                encrypted=False,
                page_count=2,
                pages=(
                    first_page,
                    PdfPagePreflight(
                        page_index=2,
                        width=612,
                        height=792,
                        rotation=0,
                        embedded_text_character_count=0,
                        image_coverage=1.0,
                    ),
                ),
            ),
            representation_bundle=result.representation_bundle,
            blocking_reasons=("fixture parser omitted page 2 output",),
        )


class MismatchedFixturePdfParser(FixturePdfParser):
    def __init__(self, mismatch: str, returned_bundle: DocumentRepresentationBundle | None = None):
        super().__init__()
        self._mismatch = mismatch
        self._returned_bundle = returned_bundle

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        result = super().parse(parse_input)
        bundle = self._returned_bundle or result.representation_bundle
        assert bundle is not None
        representation = bundle.representation
        preflight = result.preflight
        if self._mismatch == "unchanged":
            pass
        elif self._mismatch == "representation_id":
            representation = representation.model_copy(update={"id": "rep_wrong_task"})
        elif self._mismatch == "task":
            representation = representation.model_copy(
                update={"processing_task_fingerprint_id": "ptf_wrong_task"}
            )
        elif self._mismatch == "input_digest":
            representation = representation.model_copy(update={"input_blob_digest": "f" * 64})
        elif self._mismatch == "parser_name":
            representation = representation.model_copy(update={"parser_name": "wrong_parser"})
        elif self._mismatch == "parser_version":
            representation = representation.model_copy(update={"parser_version": "wrong"})
        elif self._mismatch == "parser_config":
            representation = representation.model_copy(update={"parser_config_digest": "f" * 64})
        elif self._mismatch == "preflight_name":
            preflight = PdfPreflight(
                parser_name="wrong_parser",
                parser_version=preflight.parser_version,
                preflight_tool=preflight.preflight_tool,
                preflight_tool_version=preflight.preflight_tool_version,
                encrypted=preflight.encrypted,
                page_count=preflight.page_count,
                pages=preflight.pages,
                warnings=preflight.warnings,
            )
        elif self._mismatch == "preflight_version":
            preflight = PdfPreflight(
                parser_name=preflight.parser_name,
                parser_version="wrong",
                preflight_tool=preflight.preflight_tool,
                preflight_tool_version=preflight.preflight_tool_version,
                encrypted=preflight.encrypted,
                page_count=preflight.page_count,
                pages=preflight.pages,
                warnings=preflight.warnings,
            )
        else:
            raise AssertionError(f"Unexpected mismatch: {self._mismatch}")
        return PdfParseResult(
            preflight=preflight,
            representation_bundle=bundle.model_copy(update={"representation": representation}),
            blocking_reasons=result.blocking_reasons,
        )


class MutatingFixturePdfParser(FixturePdfParser):
    """Inject one impossible parser result without validating it in the fixture."""

    def __init__(self, mutation: str) -> None:
        super().__init__()
        self._mutation = mutation

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        result = super().parse(parse_input)
        bundle = result.representation_bundle
        assert bundle is not None
        root, paragraph = bundle.nodes
        (region,) = bundle.source_regions
        preflight = result.preflight

        if self._mutation == "negative_x0_or_y0":
            region = region.model_copy(update={"left": -1})
        elif self._mutation == "x1_before_x0":
            region = region.model_copy(update={"right": region.left})
        elif self._mutation == "y1_before_y0":
            region = region.model_copy(update={"bottom": region.top})
        elif self._mutation == "beyond_media_box":
            region = region.model_copy(update={"right": region.page_width + 1})
        elif self._mutation == "inside_media_box_outside_crop_box":
            original_page = preflight.pages[0]
            page = PdfPagePreflight(
                page_index=original_page.page_index,
                width=original_page.width,
                height=original_page.height,
                rotation=original_page.rotation,
                embedded_text_character_count=original_page.embedded_text_character_count,
                crop_left=original_page.crop_left,
                crop_top=original_page.crop_top,
                crop_right=500,
                crop_bottom=original_page.crop_bottom,
            )
            preflight = PdfPreflight(
                parser_name=preflight.parser_name,
                parser_version=preflight.parser_version,
                preflight_tool=preflight.preflight_tool,
                preflight_tool_version=preflight.preflight_tool_version,
                encrypted=preflight.encrypted,
                page_count=preflight.page_count,
                pages=(page,),
                warnings=preflight.warnings,
            )
        elif self._mutation == "non_finite_coordinate":
            region = region.model_copy(update={"left": float("nan")})
        elif self._mutation == "page_outside_inventory":
            region = region.model_copy(update={"page_number": 2})
        elif self._mutation == "wrong_representation":
            region = region.model_copy(update={"representation_id": "rep_wrong_fixture"})
        elif self._mutation == "node_region_page_disagreement":
            paragraph = paragraph.model_copy(update={"source_page_numbers": (2,)})
        elif self._mutation == "wrong_coordinate_system":
            region = region.model_copy(
                update={"coordinate_system": SourceCoordinateSystem.PDF_POINTS_BOTTOM_LEFT_RAW_V1}
            )
        elif self._mutation == "rotation_applied_twice":
            region = region.model_copy(update={"rotation_applied": 180})
        elif self._mutation == "region_text_range_disagreement":
            paragraph = paragraph.model_copy(update={"source_text_digest": "f" * 64})
        elif self._mutation == "duplicate_contradictory_regions":
            duplicate = region.model_copy(update={"id": f"{region.id}_duplicate"})
            paragraph = paragraph.model_copy(
                update={"source_region_ids": (region.id, duplicate.id)}
            )
            bundle = bundle.model_copy(update={"source_regions": (region, duplicate)})
        elif self._mutation == "reading_order_self_edge":
            self_edge = DocumentEdge(
                id=f"{bundle.edges[0].id}_self",
                representation_id=bundle.representation.id,
                from_node_id=paragraph.id,
                to_node_id=paragraph.id,
                edge_type="reading_order",
                provenance_kind=DocumentEdgeProvenanceKind.DETERMINISTIC,
                provenance_id="fixture_pdf_mutation_v1",
            )
            bundle = bundle.model_copy(update={"edges": (*bundle.edges, self_edge)})
        elif self._mutation == "reading_order_cycle":
            forward = DocumentEdge(
                id=f"{bundle.edges[0].id}_reading_forward",
                representation_id=bundle.representation.id,
                from_node_id=root.id,
                to_node_id=paragraph.id,
                edge_type="reading_order",
                provenance_kind=DocumentEdgeProvenanceKind.DETERMINISTIC,
                provenance_id="fixture_pdf_mutation_v1",
            )
            backward = forward.model_copy(
                update={
                    "id": f"{bundle.edges[0].id}_reading_backward",
                    "from_node_id": paragraph.id,
                    "to_node_id": root.id,
                }
            )
            bundle = bundle.model_copy(update={"edges": (*bundle.edges, forward, backward)})
        elif self._mutation == "parent_from_different_representation":
            paragraph = paragraph.model_copy(update={"parent_node_id": "nod_other_document"})
        else:
            raise AssertionError(f"Unexpected parser-output mutation: {self._mutation}")

        if self._mutation not in {
            "duplicate_contradictory_regions",
            "reading_order_self_edge",
            "reading_order_cycle",
        }:
            bundle = bundle.model_copy(
                update={"nodes": (root, paragraph), "source_regions": (region,)}
            )
        return PdfParseResult(
            preflight=preflight,
            representation_bundle=bundle,
            blocking_reasons=result.blocking_reasons,
        )


class PersistenceFailingRepository(SQLiteLedgerRepository):
    def commit_pdf_document_processing(
        self,
        *,
        expected_task_fingerprint_id: str,
        bundle: DocumentRepresentationBundle,
        page_accounting: PdfPageAccountingBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitOutcome:
        del (
            expected_task_fingerprint_id,
            bundle,
            page_accounting,
            created_provenance_activity,
            created_outcome,
            reused_outcome,
        )
        raise RuntimeError("simulated PDF persistence failure")


@contextmanager
def persistence_failing_transaction(
    ledger_path: Path,
) -> Generator[PersistenceFailingRepository]:
    connection = sqlite3.connect(ledger_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("BEGIN")
        yield PersistenceFailingRepository(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _capture_request(
    raw_pdf: bytes = RAW_PDF, fixture_key: str = "pdf-production-path"
) -> CaptureRequest:
    digest = hashlib.sha256(raw_pdf).hexdigest()
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title="PDF production-path fixture",
            stable_key=f"{fixture_key}-fixture",
            uri=f"file:///{fixture_key}-fixture.pdf",
        ),
        payload=raw_pdf,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{digest}.bin",
        idempotency_key=f"{fixture_key}-v1",
        retrieval_method="fixture",
        requested_uri="file:///pdf-production-path-fixture.pdf",
        canonical_uri="file:///pdf-production-path-fixture.pdf",
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


def _initialize_captured_pdf(
    ledger_path: Path,
    raw_pdf: bytes = RAW_PDF,
    fixture_key: str = "pdf-production-path",
) -> tuple[str, str]:
    SQLiteLedgerInitializer(ledger_path).initialize()
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(
            _capture_request(raw_pdf, fixture_key),
            repository,
            StableSourceIdentityPolicy(),
        )
    return capture.document.id, capture.raw_blob.id


def _ingest_input(
    document_id: str,
    raw_blob_id: str,
    build_identity: BuildIdentity = BUILD_IDENTITY,
    raw_pdf: bytes = RAW_PDF,
) -> PdfIngestInput:
    return PdfIngestInput(
        document_id=document_id,
        raw_bytes=raw_pdf,
        policy_id=POLICY_ID,
        ingested_at=NOW,
        raw_blob_id=raw_blob_id,
        build_identity=build_identity,
    )


def _only_processing_task_id(ledger_path: Path) -> str:
    with sqlite3.connect(ledger_path) as connection:
        rows = connection.execute("SELECT id FROM processing_task_fingerprints").fetchall()
    assert len(rows) == 1
    return str(rows[0][0])


def _representation_bundle(
    parse_input: PdfParseInput,
    *,
    analyzability: RepresentationAnalyzability,
    document_id: str,
) -> DocumentRepresentationBundle:
    representation_id = deterministic_representation_id(parse_input.processing_task_fingerprint_id)
    representation_key = representation_id.removeprefix("rep_")
    text = "PDF production-path text"
    text_view = TextView(
        id=f"tvw_{representation_key}_logical",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
        normalization_policy="fixture_pdf_v1",
    )
    display_view = TextView(
        id=f"tvw_{representation_key}_display",
        representation_id=representation_id,
        kind=TextViewKind.DISPLAY,
        content_digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
        normalization_policy="fixture_pdf_display_v1",
    )
    root = DocumentNode(
        id=f"nod_{representation_key}_document",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    region = SourceRegion(
        id=f"srg_{representation_key}_page_1",
        representation_id=representation_id,
        coordinate_system=SourceCoordinateSystem.PDF_POINTS_TOP_LEFT_V1,
        page_number=1,
        page_width=612,
        page_height=792,
        left=36,
        top=36,
        right=576,
        bottom=72,
        rotation_applied=0,
    )
    paragraph = DocumentNode(
        id=f"nod_{representation_key}_paragraph_1",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
        source_region_ids=(region.id,),
        source_page_numbers=(1,),
        source_text_digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        extraction_path=PdfExtractionPath.EMBEDDED,
    )
    edge = DocumentEdge(
        id=f"deg_{representation_key}_contains_1",
        representation_id=representation_id,
        from_node_id=root.id,
        to_node_id=paragraph.id,
        edge_type="contains",
        provenance_kind=DocumentEdgeProvenanceKind.DETERMINISTIC,
        provenance_id="fixture_pdf_v1",
    )
    quality_report = ParseQualityReport(
        id=f"pqr_{representation_key}_quality_v1",
        representation_id=representation_id,
        metric_values={"logical_text_char_count": len(text)},
        issues=("fixture_blocked",) if analyzability is RepresentationAnalyzability.BLOCKED else (),
        analyzability=analyzability,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document_id,
        parser_name="fixture_pdf",
        parser_version="1",
        parser_config_digest="b" * 64,
        processing_task_fingerprint_id=parse_input.processing_task_fingerprint_id,
        input_blob_digest=hashlib.sha256(parse_input.raw_bytes).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=parse_input.parsed_at,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view, display_view),
                nodes=(root, paragraph),
                edges=(edge,),
                source_regions=(region,),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view, display_view),
        nodes=(root, paragraph),
        edges=(edge,),
        source_regions=(region,),
        quality_report=quality_report,
    )


def test_pdf_production_path_creates_then_reuses_after_restart(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)
    parser = FixturePdfParser()

    with sqlite_ledger_transaction(ledger_path) as repository:
        created = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
    task_id = _only_processing_task_id(ledger_path)

    with sqlite_ledger_transaction(ledger_path) as repository:
        reused = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert created.representation_id is not None
        assert reused.representation_id == created.representation_id
        assert created.provenance_activity_id is not None
        assert reused.provenance_activity_id is None
        assert repository.get_document_representation_bundle(created.representation_id) is not None
        attempts = repository.list_processing_attempts(task_id)
        page_accounting = repository.get_pdf_page_accounting_bundle(created.preflight_report_id)
        outcomes = tuple(
            repository.get_processing_attempt_outcome(attempt.id) for attempt in attempts
        )

    assert parser.parse_calls == 2
    assert page_accounting is not None
    assert page_accounting.preflight_report.page_count == 1
    assert len(page_accounting.page_inventory) == 1
    assert len(page_accounting.page_extraction_statuses) == 1
    assert page_accounting.page_extraction_statuses[0].status.value == "acceptable"
    assert page_accounting.page_extraction_statuses[0].extraction_path.value == "embedded"
    assert len(attempts) == 2
    assert all(outcome is not None for outcome in outcomes)
    assert {
        outcome.output_disposition.value
        for outcome in outcomes
        if outcome is not None and outcome.output_disposition is not None
    } == {
        "created",
        "reused",
    }


def test_pdf_retry_reconciles_a_process_interrupted_attempt(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(KeyboardInterrupt, match="process interruption"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                InterruptedFixturePdfParser(),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        recovered = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(),
            Uuid4ProcessingAttemptIdFactory(),
        )
        attempts = repository.list_processing_attempts(task_id)
        outcomes = tuple(
            repository.get_processing_attempt_outcome(attempt.id) for attempt in attempts
        )

    assert recovered.representation_id is not None
    assert len(attempts) == 2
    assert [outcome.status for outcome in outcomes if outcome is not None] == [
        ProcessingAttemptStatus.INTERRUPTED,
        ProcessingAttemptStatus.SUCCEEDED,
    ]


def test_pdf_production_path_persists_blocked_diagnostic_bundle(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(analyzability=RepresentationAnalyzability.BLOCKED),
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert outcome.representation_id is not None
        assert outcome.provenance_activity_id is not None
        assert outcome.blocking_reasons == (
            "fixture parser retained diagnostic text but blocked analysis",
        )

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert outcome.representation_id is not None
        bundle = repository.get_document_representation_bundle(outcome.representation_id)
        assert bundle is not None
        assert bundle.quality_report.analyzability is RepresentationAnalyzability.BLOCKED
        attempts = repository.list_processing_attempts(
            bundle.representation.processing_task_fingerprint_id
        )
        attempt_outcome = repository.get_processing_attempt_outcome(attempts[0].id)

    assert attempt_outcome is not None
    assert attempt_outcome.status is ProcessingAttemptStatus.BLOCKED
    assert attempt_outcome.output_artifacts


def test_pdf_omitted_page_remains_in_authoritative_terminal_accounting_after_restart(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            OmittedPageBlockedFixturePdfParser(),
            Uuid4ProcessingAttemptIdFactory(),
        )

    with sqlite_ledger_transaction(ledger_path) as repository:
        accounting = repository.get_pdf_page_accounting_bundle(outcome.preflight_report_id)
        assert outcome.representation_id is not None
        representation = repository.get_document_representation_bundle(outcome.representation_id)

    assert accounting is not None
    assert representation is not None
    assert accounting.preflight_report.page_count == 2
    assert [page.page_index for page in accounting.page_inventory] == [1, 2]
    assert [status.page_index for status in accounting.page_extraction_statuses] == [1, 2]
    assert [status.status.value for status in accounting.page_extraction_statuses] == [
        "blocked",
        "blocked",
    ]
    assert accounting.page_extraction_statuses[1].extraction_path.value == "inaccessible"
    assert accounting.page_extraction_statuses[1].policy_reasons == ("parser_omitted_page_output",)
    assert representation.quality_report.analyzability is RepresentationAnalyzability.BLOCKED


def test_pdf_page_accounting_tables_reject_direct_update_and_delete(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(),
            Uuid4ProcessingAttemptIdFactory(),
        )
        accounting = repository.get_pdf_page_accounting_bundle(outcome.preflight_report_id)

    assert accounting is not None
    records = (
        ("pdf_preflight_reports", accounting.preflight_report.id),
        ("pdf_page_inventories", accounting.page_inventory[0].id),
        (
            "pdf_page_extraction_statuses",
            accounting.page_extraction_statuses[0].id,
        ),
    )
    with sqlite3.connect(ledger_path) as connection:
        for table, record_id in records:
            with pytest.raises(sqlite3.DatabaseError, match="immutable"):
                connection.execute(
                    f"UPDATE {table} SET payload_json = '{{}}' WHERE id = ?",
                    (record_id,),
                )
            with pytest.raises(sqlite3.DatabaseError, match="immutable"):
                connection.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))


def test_pdf_production_path_records_docling_source_access_as_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from docling import exceptions
    from kotekomi_adapters import docling_pdf_parser

    def raise_security_error() -> tuple[object, object, object, object, object]:
        raise exceptions.SecurityError("fixture source access blocked")

    def fixture_preflight(_raw_bytes: bytes, parser_version: str) -> PdfPreflight:
        return PdfPreflight(
            parser_name="docling",
            parser_version=parser_version,
            encrypted=False,
            page_count=1,
            pages=(PdfPagePreflight(1, 612, 792, 0, 20),),
            pdf_version="1.7",
            preflight_tool="fixture_preflight",
            preflight_tool_version="1",
        )

    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)
    monkeypatch.setattr(docling_pdf_parser, "_load_docling_components", raise_security_error)
    monkeypatch.setattr(docling_pdf_parser, "preflight_pdf_source", fixture_preflight)
    monkeypatch.setenv("KOTEKOMI_DOCLING_WORKER", "1")

    with sqlite_ledger_transaction(ledger_path) as repository:
        result = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
        )

    assert result.representation_id is None
    assert result.blocking_reasons == (
        "PDF source is inaccessible under the configured security policy.",
    )
    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()
        accounting = repository.get_pdf_page_accounting_bundle(result.preflight_report_id)

    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.BLOCKED
    assert outcome.failure is None
    assert accounting is not None
    assert accounting.preflight_report.page_count == 1
    assert accounting.preflight_report.pdf_version == "1.7"
    assert len(accounting.page_extraction_statuses) == 1
    assert accounting.page_extraction_statuses[0].extraction_path is PdfExtractionPath.INACCESSIBLE
    assert accounting.page_extraction_statuses[0].status is PdfPageQualityStatus.BLOCKED


@pytest.mark.parametrize(
    "fixture_path",
    (
        "fixtures/pdf/encrypted/encrypted_aes256_v1.pdf",
        "fixtures/pdf/corrupt/ocrmypdf-invalid.pdf",
    ),
)
def test_public_pdf_ingestion_blocks_when_source_preflight_cannot_establish_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixture_path: str,
) -> None:
    raw_pdf = (Path(__file__).parent / fixture_path).read_bytes()
    fixture_key = Path(fixture_path).stem
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(
        ledger_path,
        raw_pdf,
        fixture_key,
    )
    monkeypatch.setenv("KOTEKOMI_DOCLING_WORKER", "1")

    with sqlite_ledger_transaction(ledger_path) as repository:
        result = ingest_pdf(
            _ingest_input(document_id, raw_blob_id, raw_pdf=raw_pdf),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
        )

    assert result.representation_id is None
    assert result.blocking_reasons == (
        "PDF source preflight could not establish an authoritative page inventory.",
    )
    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        accounting = repository.get_pdf_page_accounting_bundle(result.preflight_report_id)

    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.BLOCKED
    assert outcome.failure is None
    assert accounting is not None
    assert accounting.preflight_report.page_count == 0
    assert accounting.page_extraction_statuses == ()


def test_pdf_production_path_records_validation_failure_without_representation(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(ValueError, match="mismatched document ID"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                FixturePdfParser(target_document_id="doc_wrong_fixture"),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()
        assert repository.list_provenance_activities() == ()

    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.FAILED
    assert outcome.failure is not None
    assert outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION


@pytest.mark.parametrize(
    "mismatch",
    (
        "representation_id",
        "task",
        "input_digest",
        "parser_name",
        "parser_version",
        "parser_config",
        "preflight_name",
        "preflight_version",
    ),
)
def test_pdf_processing_rejects_every_parser_task_binding_disagreement(
    tmp_path: Path,
    mismatch: str,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(ValueError, match="mismatched"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                MismatchedFixturePdfParser(mismatch),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        attempt_outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()
        assert repository.list_provenance_activities() == ()

    assert attempt_outcome is not None
    assert attempt_outcome.status is ProcessingAttemptStatus.FAILED
    assert attempt_outcome.failure is not None
    assert attempt_outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION


@pytest.mark.parametrize(
    "mutation",
    (
        "negative_x0_or_y0",
        "x1_before_x0",
        "y1_before_y0",
        "beyond_media_box",
        "inside_media_box_outside_crop_box",
        "non_finite_coordinate",
        "page_outside_inventory",
        "wrong_representation",
        "node_region_page_disagreement",
        "wrong_coordinate_system",
        "rotation_applied_twice",
        "region_text_range_disagreement",
        "duplicate_contradictory_regions",
        "reading_order_self_edge",
        "reading_order_cycle",
        "parent_from_different_representation",
    ),
)
def test_pdf_parser_output_mutations_fail_closed_and_retry_cleanly(
    tmp_path: Path,
    mutation: str,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(ValueError):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                MutatingFixturePdfParser(mutation),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts_after_failure = repository.list_processing_attempts(task_id)
        failed_outcome = repository.get_processing_attempt_outcome(attempts_after_failure[0].id)
        assert repository.get_document(document_id) is not None
        assert repository.get_raw_blob(raw_blob_id) is not None
        assert repository.list_document_representations() == ()
        assert repository.list_text_views() == ()
        assert repository.list_document_nodes() == ()
        assert repository.list_document_edges() == ()
        assert repository.list_source_regions() == ()
        assert repository.list_parse_quality_reports() == ()
        assert repository.list_provenance_activities() == ()
        assert repository.find_pdf_preflight_report_for_task(task_id) is None

    assert len(attempts_after_failure) == 1
    assert failed_outcome is not None
    assert failed_outcome.status is ProcessingAttemptStatus.FAILED
    assert failed_outcome.failure is not None
    assert failed_outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION

    with sqlite_ledger_transaction(ledger_path) as repository:
        retry = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(),
            Uuid4ProcessingAttemptIdFactory(),
        )

    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts_after_retry = repository.list_processing_attempts(task_id)
        outcomes_after_retry = tuple(
            repository.get_processing_attempt_outcome(attempt.id)
            for attempt in attempts_after_retry
        )
        assert retry.representation_id is not None
        assert repository.get_document_representation_bundle(retry.representation_id) is not None

    assert len(attempts_after_retry) == 2
    assert [outcome.status for outcome in outcomes_after_retry if outcome is not None] == [
        ProcessingAttemptStatus.FAILED,
        ProcessingAttemptStatus.SUCCEEDED,
    ]


def test_pdf_processing_rejects_task_a_output_for_changed_build_identity_task_b(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with sqlite_ledger_transaction(ledger_path) as repository:
        first = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(),
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert first.representation_id is not None
        first_bundle = repository.get_document_representation_bundle(first.representation_id)
        assert first.provenance_activity_id is not None
        first_provenance = repository.get_provenance_activity(first.provenance_activity_id)
        assert first_bundle is not None
        assert first_provenance is not None

    changed_build_identity = BuildIdentity(
        "pdf-proof",
        "changed-revision",
        "a" * 64,
        "1",
    )
    changed_task = processing_task_fingerprint(
        task_kind="pdf_document_representation",
        document_id=document_id,
        blob_id=raw_blob_id,
        input_digest=hashlib.sha256(RAW_PDF).hexdigest(),
        processor_name="fixture_pdf",
        processor_version="1",
        processor_config_digest="b" * 64,
        build_identity=changed_build_identity,
        policy_id=POLICY_ID,
        output_contract_version="1",
    )
    with pytest.raises(ValueError, match="mismatched representation ID"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id, changed_build_identity),
                repository,
                MismatchedFixturePdfParser("unchanged", first_bundle),
                Uuid4ProcessingAttemptIdFactory(),
            )

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert first.representation_id is not None
        assert (
            repository.get_document_representation_bundle(first.representation_id) == first_bundle
        )
        assert repository.get_provenance_activity(first.provenance_activity_id) == first_provenance
        assert len(repository.list_document_representations()) == 1
        task_ids = {
            first_bundle.representation.processing_task_fingerprint_id,
            changed_task.id,
        }
        attempts = tuple(
            attempt
            for task_id in task_ids
            for attempt in repository.list_processing_attempts(task_id)
        )
        outcomes = tuple(
            repository.get_processing_attempt_outcome(attempt.id) for attempt in attempts
        )
        assert all(
            repository.get_processing_task_fingerprint(task_id) is not None for task_id in task_ids
        )

    assert len(task_ids) == 2
    assert len(attempts) == 2
    assert {outcome.status for outcome in outcomes if outcome is not None} == {
        ProcessingAttemptStatus.SUCCEEDED,
        ProcessingAttemptStatus.FAILED,
    }
    failed_outcome = next(
        outcome
        for outcome in outcomes
        if outcome is not None and outcome.status is ProcessingAttemptStatus.FAILED
    )
    assert failed_outcome.failure is not None
    assert failed_outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION


def test_pdf_production_path_records_persistence_failure_without_representation(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(RuntimeError, match="simulated PDF persistence failure"):
        with persistence_failing_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                FixturePdfParser(),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()
        assert repository.list_provenance_activities() == ()

    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.FAILED
    assert outcome.failure is not None
    assert outcome.failure.stage is ProcessingStage.PERSISTENCE
