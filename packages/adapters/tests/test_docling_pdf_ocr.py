import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
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
    PdfParseInput,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    Uuid4ProcessingAttemptIdFactory,
    capture_identity,
    capture_source,
    ingest_pdf,
)
from kotekomi_domain import (
    Document,
    DocumentVersionKind,
    PdfExtractionPath,
    PdfPageQualityStatus,
    PdfTransformationType,
    SourceType,
    TextViewKind,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pdf"
MIXED_PATH = FIXTURE_ROOT / "mixed" / "mixed_born_digital_scan_v1.pdf"
GOLD_PATH = FIXTURE_ROOT / "gold" / "mixed_born_digital_scan_v1.json"
OCR_REFERENCE_PATH = FIXTURE_ROOT / "ocr" / "ocrmypdf-linn.txt"
RAW_PDF = MIXED_PATH.read_bytes()
RAW_DIGEST = "236492169fa4dcdd0ca95e59f1ceaba26ad948f74cea3d74556c34bdd1d8a2e9"
NOW = datetime(2026, 7, 13, 13, 0, tzinfo=UTC)
BUILD_IDENTITY = BuildIdentity("pdf-ocr-proof", "pdf-ocr-proof", "c" * 64, "1")


def _capture_request() -> CaptureRequest:
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title="KoteKomi mixed embedded and scanned fixture",
            stable_key="kotekomi-mixed-pdf-v1",
            uri="file:///fixtures/mixed_born_digital_scan_v1.pdf",
        ),
        payload=RAW_PDF,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{RAW_DIGEST}.bin",
        idempotency_key="kotekomi-mixed-pdf-v1",
        retrieval_method="fixture",
        requested_uri="file:///fixtures/mixed_born_digital_scan_v1.pdf",
        canonical_uri="file:///fixtures/mixed_born_digital_scan_v1.pdf",
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


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def test_generated_mixed_pdf_selectively_ocrs_one_page_and_replays_after_restart(
    tmp_path: Path,
) -> None:
    assert hashlib.sha256(RAW_PDF).hexdigest() == RAW_DIGEST
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    ledger_path = tmp_path / "ledger.db"
    archive_path = tmp_path / "archive"
    archive = LocalArchiveStore(archive_path)
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    identity = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(identity.raw_blob_id, RAW_PDF, RAW_DIGEST)
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)

    ingest_input = PdfIngestInput(
        document_id=capture.document.id,
        raw_bytes=RAW_PDF,
        policy_id="selective_mixed_pdf_v1",
        ingested_at=NOW,
        raw_blob_id=capture.raw_blob.id,
        build_identity=BUILD_IDENTITY,
    )
    parser = DoclingPdfParser(DoclingPdfParserConfig())
    with sqlite_ledger_transaction(ledger_path) as repository:
        first = ingest_pdf(
            ingest_input,
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
            transformation_archive=archive,
        )
        assert first.representation_id is not None
        first_bundle = repository.get_document_representation_bundle(first.representation_id)
        first_accounting = repository.get_pdf_page_accounting_bundle(first.preflight_report_id)

    reopened_archive = LocalArchiveStore(archive_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        second = ingest_pdf(
            ingest_input,
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
            transformation_archive=reopened_archive,
        )
        assert second.representation_id == first.representation_id
        assert second.representation_id is not None
        second_bundle = repository.get_document_representation_bundle(second.representation_id)
        second_accounting = repository.get_pdf_page_accounting_bundle(second.preflight_report_id)

    assert first_bundle is not None
    assert second_bundle == first_bundle
    assert first_accounting is not None
    assert second_accounting == first_accounting
    assert reopened_archive.read_raw_source(capture.raw_blob.id) == RAW_PDF

    statuses = first_accounting.page_extraction_statuses
    assert tuple(status.extraction_path for status in statuses) == (
        PdfExtractionPath.EMBEDDED,
        PdfExtractionPath.OCR,
        PdfExtractionPath.EMBEDDED,
    )
    assert all(status.status is PdfPageQualityStatus.ACCEPTABLE for status in statuses)
    assert all(status.policy_version == gold["selection_policy_version"] for status in statuses)
    assert statuses[0].transformation_artifact_ids == ()
    assert statuses[2].transformation_artifact_ids == ()
    assert statuses[1].ocr_confidence is not None and statuses[1].ocr_confidence > 0.95

    artifacts = first_accounting.transformation_artifacts
    assert tuple(artifact.activity_type.value for artifact in artifacts) == tuple(
        gold["ocr_execution"]["archived_artifact_types"]
    )
    assert all(artifact.page_scope == (2,) for artifact in artifacts)
    assert artifacts[1].input_blob_id == artifacts[0].output_blob_id
    assert artifacts[1].tool_name == gold["ocr_execution"]["engine"]
    assert artifacts[1].tool_version == gold["ocr_execution"]["engine_version"]
    assert artifacts[1].model_name.split("+") == gold["ocr_execution"]["model_names"]
    assert artifacts[1].model_digest != artifacts[1].configuration_digest
    assert artifacts[1].language_set == tuple(gold["ocr_execution"]["language_set"])
    assert statuses[1].transformation_artifact_ids == tuple(artifact.id for artifact in artifacts)

    render_blob, sidecar_blob = first_accounting.transformation_blobs
    render_bytes = reopened_archive.read_pdf_transformation_blob(render_blob.id)
    sidecar_bytes = reopened_archive.read_pdf_transformation_blob(sidecar_blob.id)
    assert render_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    sidecar = json.loads(sidecar_bytes)
    assert sidecar["page"] == 2
    assert sidecar["input_digest"] == render_blob.digest
    assert sidecar["engine"]["model_digest"] == artifacts[1].model_digest

    logical_view = next(
        view for view in first_bundle.text_views if view.kind is TextViewKind.LOGICAL
    )
    for expected in gold["page_processing"][0]["exact_text"]:
        assert expected in logical_view.text
    for expected in gold["page_processing"][2]["exact_text"]:
        assert expected in logical_view.text
    nodes_by_page = {
        page: tuple(
            node
            for node in first_bundle.nodes
            if node.parent_node_id is not None and node.source_page_numbers == (page,)
        )
        for page in (1, 2, 3)
    }
    assert all(node.extraction_path is PdfExtractionPath.EMBEDDED for node in nodes_by_page[1])
    assert all(node.extraction_path is PdfExtractionPath.OCR for node in nodes_by_page[2])
    assert all(node.parser_confidence is not None for node in nodes_by_page[2])
    assert all(node.extraction_path is PdfExtractionPath.EMBEDDED for node in nodes_by_page[3])
    page_two_text = "\n".join(
        logical_view.text[node.start_char : node.end_char]
        for node in sorted(nodes_by_page[2], key=lambda node: node.order_index)
    )
    expected_words = _word_set(OCR_REFERENCE_PATH.read_text(encoding="utf-8"))
    assert len(expected_words & _word_set(page_two_text)) / len(expected_words) > 0.9


@pytest.mark.parametrize(
    "relative_path",
    (
        "font-mapping/ocrmypdf-truetype-font-nomapping.pdf",
        "font-mapping/ocrmypdf-vector-text.pdf",
    ),
)
def test_malformed_font_and_vector_text_pages_use_the_same_ocr_fallback(
    relative_path: str,
) -> None:
    raw_pdf = (FIXTURE_ROOT / relative_path).read_bytes()
    document = Document(
        id="doc_font_fallback",
        source_id="src_font_fallback",
        content_sha256=hashlib.sha256(raw_pdf).hexdigest(),
    )
    result = DoclingPdfParser(DoclingPdfParserConfig()).parse(
        PdfParseInput(
            document=document,
            raw_bytes=raw_pdf,
            policy_id="malformed_font_fallback_v1",
            processing_task_fingerprint_id="ptf_font_fallback",
            parsed_at=NOW,
        )
    )

    assert result.representation_bundle is not None
    assert tuple(payload.activity_type for payload in result.transformation_payloads) == (
        PdfTransformationType.RENDER,
        PdfTransformationType.OCR,
    )
    content_nodes = tuple(
        node for node in result.representation_bundle.nodes if node.parent_node_id is not None
    )
    assert content_nodes
    assert all(node.extraction_path is PdfExtractionPath.OCR for node in content_nodes)
    assert all(node.parser_confidence is not None for node in content_nodes)


def test_unrecoverable_type3_font_fallback_is_explicitly_blocked() -> None:
    raw_pdf = (FIXTURE_ROOT / "font-mapping" / "ocrmypdf-type3-font-nomapping.pdf").read_bytes()
    result = DoclingPdfParser(DoclingPdfParserConfig()).parse(
        PdfParseInput(
            document=Document(
                id="doc_type3_fallback",
                source_id="src_type3_fallback",
                content_sha256=hashlib.sha256(raw_pdf).hexdigest(),
            ),
            raw_bytes=raw_pdf,
            policy_id="malformed_font_fallback_v1",
            processing_task_fingerprint_id="ptf_type3_fallback",
            parsed_at=NOW,
        )
    )

    assert result.representation_bundle is None
    assert result.blocking_reasons == ("Selective OCR produced no usable text for page 1.",)
    assert tuple(payload.activity_type for payload in result.transformation_payloads) == (
        PdfTransformationType.RENDER,
    )
