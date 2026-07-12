import hashlib
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters import LocalArchiveStore, SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import (
    BuildIdentity,
    CaptureRequest,
    PdfIngestInput,
    PdfPagePreflight,
    PdfParseInput,
    PdfParseResult,
    PdfProcessorIdentity,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    Uuid4ProcessingAttemptIdFactory,
    capture_identity,
    capture_source,
    ingest_pdf,
)
from kotekomi_domain import (
    DocumentRepresentationBundle,
    DocumentVersionKind,
    RepresentationAnalyzability,
    SourceType,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)
RAW_PDF = FIXTURE_PATH.read_bytes()
RAW_PDF_DIGEST = "510e8700c0afde7206599f9d0ebd8374b1034204f02e36066aec57d8054b43b7"
NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
BUILD_IDENTITY = BuildIdentity("r1a-pdf", "r1a-pdf", "a" * 64, "1")
POLICY_ID = "r1a_born_digital_pdf_v1"


class RecordingDoclingParser:
    def __init__(self) -> None:
        self._parser = DoclingPdfParser(DoclingPdfParserConfig())
        self.results: list[PdfParseResult] = []

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        return self._parser.processing_identity(policy_id)

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        result = self._parser.parse(parse_input)
        self.results.append(result)
        return result


def _capture_request() -> CaptureRequest:
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title="2025 Community Health Improvement Plan Press Release",
            stable_key="johnson-county-2025-community-health-improvement-plan-press-release",
            uri="fixture://2025-community-health-improvement-plan-press-release.pdf",
        ),
        payload=RAW_PDF,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{RAW_PDF_DIGEST}.bin",
        idempotency_key="r1a-community-health-press-release-v1",
        retrieval_method="fixture",
        requested_uri="fixture://2025-community-health-improvement-plan-press-release.pdf",
        canonical_uri="fixture://2025-community-health-improvement-plan-press-release.pdf",
        provider_item_id=None,
        provider_version="2025-03-18",
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


def _ingest_input(document_id: str, raw_blob_id: str) -> PdfIngestInput:
    return PdfIngestInput(
        document_id=document_id,
        raw_bytes=RAW_PDF,
        policy_id=POLICY_ID,
        ingested_at=NOW,
        raw_blob_id=raw_blob_id,
        build_identity=BUILD_IDENTITY,
    )


def test_docling_r1a_ingests_the_press_release_as_an_analyzeable_representation(
    tmp_path: Path,
) -> None:
    assert hashlib.sha256(RAW_PDF).hexdigest() == RAW_PDF_DIGEST
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    capture_identity_result = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(
        capture_identity_result.raw_blob_id,
        RAW_PDF,
        RAW_PDF_DIGEST,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)

    parser = RecordingDoclingParser()
    with sqlite_ledger_transaction(ledger_path) as repository:
        first = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert first.representation_id is not None
        stored_bundle = repository.get_document_representation_bundle(first.representation_id)

    with sqlite_ledger_transaction(ledger_path) as repository:
        second = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert second.representation_id is not None
        replayed_bundle = repository.get_document_representation_bundle(second.representation_id)

    assert archive.read_raw_source(capture.raw_blob.id) == RAW_PDF
    assert first.representation_id == second.representation_id
    assert first.provenance_activity_id is not None
    assert second.provenance_activity_id is None
    assert len(parser.results) == 2
    first_result, second_result = parser.results
    assert first_result.preflight == second_result.preflight
    assert first_result.representation_bundle is not None
    assert first_result.representation_bundle == second_result.representation_bundle
    assert stored_bundle is not None
    assert replayed_bundle is not None
    _assert_persisted_bundle(first_result.representation_bundle, stored_bundle)
    _assert_persisted_bundle(first_result.representation_bundle, replayed_bundle)

    _assert_r1a_representation(first_result.representation_bundle, first_result)


def _assert_persisted_bundle(
    expected: DocumentRepresentationBundle,
    actual: DocumentRepresentationBundle,
) -> None:
    assert actual.representation == expected.representation
    assert actual.text_views == expected.text_views
    assert actual.nodes == tuple(sorted(expected.nodes, key=lambda node: node.id))
    assert actual.edges == tuple(sorted(expected.edges, key=lambda edge: edge.id))
    assert actual.source_regions == tuple(
        sorted(expected.source_regions, key=lambda region: region.id)
    )
    assert actual.quality_report == expected.quality_report


def _assert_r1a_representation(
    bundle: DocumentRepresentationBundle,
    parse_result: PdfParseResult,
) -> None:
    preflight = parse_result.preflight
    assert preflight.page_count == 1
    assert preflight.warnings == ()
    assert preflight.pages == (
        PdfPagePreflight(
            page_index=1,
            width=612.0,
            height=792.0,
            rotation=0,
            embedded_text_character_count=2312,
        ),
    )
    assert parse_result.blocking_reasons == ()

    assert bundle.quality_report.analyzability is RepresentationAnalyzability.ACCEPTABLE
    assert bundle.quality_report.issues == ()
    assert bundle.quality_report.metric_values == {
        "page_count": 1,
        "covered_page_count": 1,
        "logical_text_char_count": 2328,
        "reading_order_node_count": 17,
        "heading_node_count": 2,
        "paragraph_node_count": 15,
        "source_region_count": 17,
    }
    assert len(bundle.text_views) == 1
    text_view = bundle.text_views[0]
    assert text_view.text.startswith("For Immediate Release March 18, 2025\nContact\n")

    root, *content_nodes = bundle.nodes
    assert root.node_type == "document"
    assert (root.start_char, root.end_char) == (0, len(text_view.text))
    assert tuple(node.order_index for node in bundle.nodes) == tuple(range(len(bundle.nodes)))
    assert {node.node_type for node in content_nodes} == {"heading", "paragraph"}
    assert all(text_view.text[node.start_char : node.end_char] for node in content_nodes)
    assert all(node.source_region_ids for node in content_nodes)
    assert tuple(edge.from_node_id for edge in bundle.edges) == (root.id,) * len(content_nodes)
    assert tuple(edge.to_node_id for edge in bundle.edges) == tuple(
        node.id for node in content_nodes
    )

    preflight_pages = {page.page_index: page for page in preflight.pages}
    assert {region.page_number for region in bundle.source_regions} == set(preflight_pages)
    for region in bundle.source_regions:
        page = preflight_pages[region.page_number]
        assert region.coordinate_system == "pdf_points_top_left_v1"
        assert (region.page_width, region.page_height) == (page.width, page.height)
        assert 0 <= region.left < region.right <= page.width
        assert 0 <= region.top < region.bottom <= page.height

    selected_paragraph = next(
        node
        for node in content_nodes
        if text_view.text[node.start_char : node.end_char].startswith("IOWA CITY, Iowa")
    )
    selected_region = next(
        region
        for region in bundle.source_regions
        if region.id == selected_paragraph.source_region_ids[0]
    )
    assert selected_region.page_number == 1
    assert abs(selected_region.left - 72.024) < 0.000001
    assert abs(selected_region.top - 268.25288) < 0.000001
    assert abs(selected_region.right - 538.12912) < 0.000001
    assert abs(selected_region.bottom - 328.67496707182323) < 0.000001
