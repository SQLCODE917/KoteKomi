import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from kotekomi_adapters import (
    DoclingPdfParser,
    DoclingPdfParserConfig,
    LocalArchiveStore,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    BuildIdentity,
    CaptureRequest,
    PdfIngestInput,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    Uuid4ProcessingAttemptIdFactory,
    capture_identity,
    capture_source,
    ingest_pdf,
)
from kotekomi_domain import (
    DocumentNode,
    DocumentVersionKind,
    PdfPageQualityStatus,
    SourceType,
    TextViewKind,
)

from .pdf_page_accounting_assertions import assert_equivalent_pdf_page_accounting

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pdf"
PDF_PATH = FIXTURE_ROOT / "layout" / "adversarial_columns_hierarchy_v1.pdf"
GOLD_PATH = FIXTURE_ROOT / "gold" / "adversarial_columns_hierarchy_v1.json"
RAW_PDF = PDF_PATH.read_bytes()
RAW_DIGEST = "b28397d8a1951927300a18c6350ec17cc2d7a7784ff2ee525a4d41d80ab13dd8"
NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
POLICY_ID = "pdf_layout_authority_v1"
BUILD_IDENTITY = BuildIdentity("pdf-layout-proof", "pdf-layout-proof", "a" * 64, "1")


def _capture_request() -> CaptureRequest:
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title="KoteKomi adversarial PDF layout fixture",
            stable_key="kotekomi-adversarial-layout-v1",
            uri="file:///fixtures/adversarial_columns_hierarchy_v1.pdf",
        ),
        payload=RAW_PDF,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{RAW_DIGEST}.bin",
        idempotency_key="kotekomi-adversarial-layout-v1",
        retrieval_method="fixture",
        requested_uri="file:///fixtures/adversarial_columns_hierarchy_v1.pdf",
        canonical_uri="file:///fixtures/adversarial_columns_hierarchy_v1.pdf",
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


def _ingest_input(document_id: str, raw_blob_id: str) -> PdfIngestInput:
    return PdfIngestInput(
        document_id=document_id,
        raw_bytes=RAW_PDF,
        policy_id=POLICY_ID,
        ingested_at=NOW,
        raw_blob_id=raw_blob_id,
        build_identity=BUILD_IDENTITY,
    )


def _node_text(node: DocumentNode, views_by_id: dict[str, str]) -> str:
    return views_by_id[node.text_view_id][node.start_char : node.end_char]


def test_public_pdf_layout_is_rotation_safe_ordered_hierarchical_and_restart_stable(
    tmp_path: Path,
) -> None:
    assert hashlib.sha256(RAW_PDF).hexdigest() == RAW_DIGEST
    gold = cast(dict[str, object], json.loads(GOLD_PATH.read_text(encoding="utf-8")))
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    identity = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(identity.raw_blob_id, RAW_PDF, RAW_DIGEST)
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)

    parser = DoclingPdfParser(DoclingPdfParserConfig())
    with sqlite_ledger_transaction(ledger_path) as repository:
        first = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert first.representation_id is not None
        first_bundle = repository.get_document_representation_bundle(first.representation_id)
        first_accounting = repository.get_pdf_page_accounting_bundle(first.preflight_report_id)

    with sqlite_ledger_transaction(ledger_path) as repository:
        second = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert second.representation_id is not None
        second_bundle = repository.get_document_representation_bundle(second.representation_id)
        second_accounting = repository.get_pdf_page_accounting_bundle(second.preflight_report_id)

    assert archive.read_raw_source(capture.raw_blob.id) == RAW_PDF
    assert first.representation_id == second.representation_id
    assert first_bundle is not None
    assert second_bundle == first_bundle
    assert first_accounting is not None
    assert second_accounting is not None
    assert first.preflight_report_id != second.preflight_report_id
    assert_equivalent_pdf_page_accounting(first_accounting, second_accounting)
    assert [page.rotation for page in first_accounting.page_inventory] == [0, 0, 90]
    assert all(
        status.status is PdfPageQualityStatus.ACCEPTABLE
        for status in first_accounting.page_extraction_statuses
    )

    views = {view.kind: view for view in first_bundle.text_views}
    assert set(views) == {TextViewKind.LOGICAL, TextViewKind.DISPLAY}
    logical_lines = views[TextViewKind.LOGICAL].text.splitlines()
    display_lines = views[TextViewKind.DISPLAY].text.splitlines()
    assert logical_lines == gold["logical_analysis_lines"]
    for furniture in cast(list[str], gold["forbidden_logical_lines"]):
        assert furniture not in logical_lines
    for furniture in cast(list[str], gold["furniture_lines"]):
        assert furniture in display_lines

    views_by_id = {view.id: view.text for view in first_bundle.text_views}
    content_nodes = tuple(
        sorted(
            (node for node in first_bundle.nodes if node.parent_node_id is not None),
            key=lambda node: node.order_index,
        )
    )
    nodes_by_text = {_node_text(node, views_by_id): node for node in content_nodes}
    assert [
        _node_text(node, views_by_id) for node in content_nodes if node.node_type == "furniture"
    ] == gold["furniture_lines"]
    assert sum(node.node_type == "list_item" for node in content_nodes) == 5
    for parent_text, child_text in cast(list[list[str]], gold["hierarchy"]):
        assert nodes_by_text[child_text].parent_node_id == nodes_by_text[parent_text].id

    logical_nodes = tuple(node for node in content_nodes if node.node_type != "furniture")
    reading_edges = tuple(edge for edge in first_bundle.edges if edge.edge_type == "reading_order")
    assert tuple(edge.from_node_id for edge in reading_edges) == tuple(
        node.id for node in logical_nodes[:-1]
    )
    assert tuple(edge.to_node_id for edge in reading_edges) == tuple(
        node.id for node in logical_nodes[1:]
    )

    rotated_node = nodes_by_text["ROTATED BODY remains inside canonical coordinates."]
    rotated_region = next(
        region
        for region in first_bundle.source_regions
        if region.id in rotated_node.source_region_ids
    )
    assert rotated_region.page_number == 3
    assert rotated_region.rotation_applied == 90
    assert (rotated_region.page_width, rotated_region.page_height) == (612.0, 792.0)
    assert (
        round(rotated_region.left, 3),
        round(rotated_region.top, 3),
        round(rotated_region.right, 3),
        round(rotated_region.bottom, 3),
    ) == (54.0, 142.102, 327.251, 152.277)
