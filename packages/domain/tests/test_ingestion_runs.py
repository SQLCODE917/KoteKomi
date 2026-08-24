from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_domain import (
    IngestionFailureCode,
    IngestionFailureStage,
    IngestionRun,
    IngestionRunStatus,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _run(**updates: object) -> IngestionRun:
    body: dict[str, object] = {
        "id": "igr_fixture",
        "requested_path": "raw/example.pdf",
        "display_filename": "example.pdf",
        "requested_source_url": "https://example.test/source",
        "status": IngestionRunStatus.RUNNING,
        "started_at": NOW,
    }
    body.update(updates)
    return IngestionRun.model_validate(body)


def test_ingestion_run_accepts_each_valid_cir1_state() -> None:
    running = _run()
    captured = _run(
        status=IngestionRunStatus.CAPTURED,
        normalized_source_url="https://example.test/source",
        completed_at=NOW + timedelta(seconds=1),
        source_id="src_fixture",
        document_id="doc_fixture",
        representation_id="rep_fixture",
        provenance_activity_id="prv_fixture",
    )
    error = _run(
        status=IngestionRunStatus.ERROR,
        completed_at=NOW + timedelta(seconds=1),
        source_id="src_fixture",
        document_id="doc_fixture",
        failure_stage=IngestionFailureStage.SOURCE_VALIDATION,
        failure_code=IngestionFailureCode.FILE_NOT_FOUND,
        safe_failure_message="The requested deposited file was not found.",
    )

    assert running.status is IngestionRunStatus.RUNNING
    assert captured.status is IngestionRunStatus.CAPTURED
    assert error.status is IngestionRunStatus.ERROR


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"status": IngestionRunStatus.CAPTURED, "completed_at": NOW},
            "requires canonical capture links",
        ),
        (
            {"status": IngestionRunStatus.ERROR, "completed_at": NOW},
            "requires safe typed failure details",
        ),
        (
            {"completed_at": NOW},
            "cannot contain terminal state",
        ),
        (
            {
                "status": IngestionRunStatus.ERROR,
                "completed_at": NOW - timedelta(seconds=1),
                "failure_stage": IngestionFailureStage.ARCHIVE,
                "failure_code": IngestionFailureCode.ARCHIVE_INITIALIZATION_FAILED,
                "safe_failure_message": "Unable to initialize the local Archive.",
            },
            "cannot complete before it starts",
        ),
    ],
)
def test_ingestion_run_rejects_invalid_state_shapes(
    updates: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _run(**updates)
