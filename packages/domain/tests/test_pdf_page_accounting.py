import pytest
from kotekomi_domain import (
    PdfExtractionPath,
    PdfPageAccountingBundle,
    PdfPageExtractionStatus,
    PdfPageInventory,
    PdfPageInventoryDisposition,
    PdfPageQualityStatus,
    PdfPreflightReport,
    PdfTransformationArtifact,
    PdfTransformationType,
    RawBlob,
)


def _page(page_index: int) -> PdfPageInventory:
    return PdfPageInventory(
        id=f"ppi_fixture_{page_index}",
        preflight_report_id="pfr_fixture",
        page_index=page_index,
        media_width=612,
        media_height=792,
        crop_left=0,
        crop_top=0,
        crop_right=612,
        crop_bottom=792,
        rotation=0,
        embedded_text_character_count=120,
        image_coverage=0.0,
        suspicious_glyph_rate=0.0,
        glyph_issue_count=0,
    )


def _status(
    page_index: int,
    *,
    extraction_path: PdfExtractionPath = PdfExtractionPath.EMBEDDED,
    status: PdfPageQualityStatus = PdfPageQualityStatus.ACCEPTABLE,
    extracted_character_count: int = 120,
    transformation_artifact_ids: tuple[str, ...] = (),
    ocr_confidence: float | None = None,
) -> PdfPageExtractionStatus:
    return PdfPageExtractionStatus(
        id=f"pes_fixture_{page_index}",
        preflight_report_id="pfr_fixture",
        page_inventory_id=f"ppi_fixture_{page_index}",
        page_index=page_index,
        extraction_path=extraction_path,
        status=status,
        extracted_character_count=extracted_character_count,
        rotation_applied=0,
        policy_id="pdf_extraction_policy_v1",
        policy_version="selective_pdf_page_policy_v1",
        policy_reasons=("usable_embedded_text",),
        transformation_artifact_ids=transformation_artifact_ids,
        ocr_confidence=ocr_confidence,
    )


def _report(page_count: int = 2) -> PdfPreflightReport:
    return PdfPreflightReport(
        id="pfr_fixture",
        document_id="doc_fixture",
        raw_blob_id="blb_fixture",
        processing_task_fingerprint_id="ptf_fixture",
        processing_attempt_id="pat_fixture",
        pdf_version="1.7",
        page_inventory_disposition=PdfPageInventoryDisposition.COMPLETE,
        page_count=page_count,
        encrypted=False,
        page_inventory_ids=tuple(f"ppi_fixture_{page}" for page in range(1, page_count + 1)),
        page_extraction_status_ids=tuple(
            f"pes_fixture_{page}" for page in range(1, page_count + 1)
        ),
        preflight_tool="fixture_preflight",
        tool_version="1",
    )


def test_pdf_page_accounting_enumerates_one_terminal_status_per_page() -> None:
    accounting = PdfPageAccountingBundle(
        preflight_report=_report(),
        page_inventory=(_page(1), _page(2)),
        page_extraction_statuses=(_status(1), _status(2)),
    )

    assert accounting.preflight_report.page_count == 2
    assert [status.page_index for status in accounting.page_extraction_statuses] == [1, 2]


def test_pdf_page_accounting_rejects_an_omitted_page_status() -> None:
    with pytest.raises(ValueError, match="statuses do not match"):
        PdfPageAccountingBundle(
            preflight_report=_report(),
            page_inventory=(_page(1), _page(2)),
            page_extraction_statuses=(_status(1),),
        )


def test_pdf_page_accounting_requires_ocr_transformation_provenance() -> None:
    with pytest.raises(ValueError, match="requires a transformation artifact"):
        _status(1, extraction_path=PdfExtractionPath.OCR)


def test_pdf_page_accounting_binds_ocr_status_to_archived_transformation() -> None:
    artifact = PdfTransformationArtifact(
        id="pta_fixture_ocr_1",
        preflight_report_id="pfr_fixture",
        input_blob_id="blb_fixture",
        output_blob_id="blb_fixture_ocr",
        activity_type=PdfTransformationType.OCR,
        tool_name="fixture_ocr",
        tool_version="1",
        model_name="fixture_ocr_model",
        model_version="1",
        model_digest="b" * 64,
        configuration_digest="a" * 64,
        page_scope=(1,),
        language_set=("eng",),
        confidence=0.95,
    )
    status = _status(
        1,
        extraction_path=PdfExtractionPath.OCR,
        transformation_artifact_ids=(artifact.id,),
        ocr_confidence=0.95,
    )
    report = _report(page_count=1).model_copy(
        update={"transformation_artifact_ids": (artifact.id,)}
    )

    accounting = PdfPageAccountingBundle(
        preflight_report=report,
        page_inventory=(_page(1),),
        page_extraction_statuses=(status,),
        transformation_artifacts=(artifact,),
        transformation_blobs=(
            RawBlob(
                id="blb_fixture_ocr",
                hash_algorithm="sha256",
                digest="c" * 64,
                byte_length=10,
                media_type="application/json",
                storage_locator="transformations/blb_fixture_ocr.bin",
            ),
        ),
    )

    assert accounting.page_extraction_statuses[0].transformation_artifact_ids == (artifact.id,)


def test_document_level_repair_can_precede_an_unavailable_page_inventory() -> None:
    artifact = PdfTransformationArtifact(
        id="pta_fixture_repair",
        preflight_report_id="pfr_fixture",
        input_blob_id="blb_fixture",
        output_blob_id="blb_fixture_repair",
        activity_type=PdfTransformationType.REPAIR,
        tool_name="fixture_repair",
        tool_version="1",
        model_name="deterministic_repair",
        model_version="1",
        model_digest="b" * 64,
        configuration_digest="a" * 64,
        page_scope=(),
    )
    report = _report(page_count=0).model_copy(
        update={
            "page_inventory_disposition": PdfPageInventoryDisposition.UNAVAILABLE,
            "page_count": None,
            "global_issues": ("page_inventory_unavailable",),
            "transformation_artifact_ids": (artifact.id,),
        }
    )

    accounting = PdfPageAccountingBundle(
        preflight_report=report,
        page_inventory=(),
        page_extraction_statuses=(),
        transformation_artifacts=(artifact,),
        transformation_blobs=(
            RawBlob(
                id="blb_fixture_repair",
                hash_algorithm="sha256",
                digest="c" * 64,
                byte_length=10,
                media_type="application/pdf",
                storage_locator="transformations/blb_fixture_repair.bin",
            ),
        ),
    )

    assert accounting.transformation_artifacts == (artifact,)


def test_unavailable_page_inventory_cannot_claim_zero_pages() -> None:
    payload = _report(page_count=0).model_dump()
    payload.update(
        {
            "page_inventory_disposition": PdfPageInventoryDisposition.UNAVAILABLE,
            "global_issues": ("page_inventory_unavailable",),
        }
    )
    with pytest.raises(ValueError, match="cannot claim a page count"):
        PdfPreflightReport.model_validate(payload)


def test_pdf_page_accounting_rejects_disagreeing_ocr_confidence() -> None:
    artifact = PdfTransformationArtifact(
        id="pta_fixture_ocr_1",
        preflight_report_id="pfr_fixture",
        input_blob_id="blb_fixture",
        output_blob_id="blb_fixture_ocr",
        activity_type=PdfTransformationType.OCR,
        tool_name="fixture_ocr",
        tool_version="1",
        model_name="fixture_ocr_model",
        model_version="1",
        model_digest="b" * 64,
        configuration_digest="a" * 64,
        page_scope=(1,),
        language_set=("eng",),
        confidence=0.95,
    )
    report = _report(page_count=1).model_copy(
        update={"transformation_artifact_ids": (artifact.id,)}
    )

    with pytest.raises(ValueError, match="confidence must match"):
        PdfPageAccountingBundle(
            preflight_report=report,
            page_inventory=(_page(1),),
            page_extraction_statuses=(
                _status(
                    1,
                    extraction_path=PdfExtractionPath.OCR,
                    transformation_artifact_ids=(artifact.id,),
                    ocr_confidence=0.75,
                ),
            ),
            transformation_artifacts=(artifact,),
            transformation_blobs=(
                RawBlob(
                    id="blb_fixture_ocr",
                    hash_algorithm="sha256",
                    digest="c" * 64,
                    byte_length=10,
                    media_type="application/json",
                    storage_locator="transformations/blb_fixture_ocr.bin",
                ),
            ),
        )


def test_inaccessible_page_cannot_claim_an_acceptable_representation() -> None:
    with pytest.raises(ValueError, match="must be blocked"):
        _status(1, extraction_path=PdfExtractionPath.INACCESSIBLE)
