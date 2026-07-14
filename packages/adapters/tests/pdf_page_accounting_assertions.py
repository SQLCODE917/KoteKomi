"""Assertions for attempt-distinct but semantically identical PDF accounting."""

from kotekomi_domain import PdfPageAccountingBundle


def assert_equivalent_pdf_page_accounting(
    first: PdfPageAccountingBundle,
    second: PdfPageAccountingBundle,
) -> None:
    """Ignore orchestration identities while comparing authoritative page facts."""

    assert first.preflight_report.model_dump(
        exclude={
            "id",
            "processing_attempt_id",
            "page_inventory_ids",
            "page_extraction_status_ids",
            "transformation_artifact_ids",
        }
    ) == second.preflight_report.model_dump(
        exclude={
            "id",
            "processing_attempt_id",
            "page_inventory_ids",
            "page_extraction_status_ids",
            "transformation_artifact_ids",
        }
    )
    assert tuple(
        page.model_dump(exclude={"id", "preflight_report_id"}) for page in first.page_inventory
    ) == tuple(
        page.model_dump(exclude={"id", "preflight_report_id"}) for page in second.page_inventory
    )
    assert tuple(
        status.model_dump(
            exclude={
                "id",
                "preflight_report_id",
                "page_inventory_id",
                "transformation_artifact_ids",
            }
        )
        for status in first.page_extraction_statuses
    ) == tuple(
        status.model_dump(
            exclude={
                "id",
                "preflight_report_id",
                "page_inventory_id",
                "transformation_artifact_ids",
            }
        )
        for status in second.page_extraction_statuses
    )
    assert tuple(
        artifact.model_dump(exclude={"id", "preflight_report_id"})
        for artifact in first.transformation_artifacts
    ) == tuple(
        artifact.model_dump(exclude={"id", "preflight_report_id"})
        for artifact in second.transformation_artifacts
    )
    assert first.transformation_blobs == second.transformation_blobs
