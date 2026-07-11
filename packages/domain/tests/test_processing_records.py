from datetime import UTC, datetime

import pytest
from kotekomi_domain import (
    OutputDisposition,
    ProcessingArtifactKind,
    ProcessingArtifactRef,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingBlocker,
    ProcessingFailure,
    ProcessingStage,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)


def _outcome(**updates: object) -> ProcessingAttemptOutcome:
    body: dict[str, object] = {
        "id": "pao_fixture",
        "attempt_id": "pat_fixture",
        "status": ProcessingAttemptStatus.SUCCEEDED,
        "finished_at": NOW,
        "output_disposition": OutputDisposition.CREATED,
        "output_artifacts": (
            ProcessingArtifactRef(
                kind=ProcessingArtifactKind.DOCUMENT_REPRESENTATION,
                artifact_id="rep_fixture",
                role="canonical_document_representation",
            ),
        ),
    }
    body.update(updates)
    return ProcessingAttemptOutcome.model_validate(body)


def test_processing_outcome_rejects_mixed_terminal_states() -> None:
    with pytest.raises(ValueError, match="cannot include terminal errors"):
        _outcome(
            blocking_reasons=(
                ProcessingBlocker(
                    code="blocked",
                    stage=ProcessingStage.PARSER,
                    safe_message="Blocked.",
                ),
            )
        )


def test_processing_outcome_requires_and_isolates_failure_details() -> None:
    with pytest.raises(ValueError, match="requires failure details"):
        _outcome(
            status=ProcessingAttemptStatus.FAILED,
            output_artifacts=(),
            output_disposition=None,
        )

    with pytest.raises(ValueError, match="cannot include another terminal state"):
        _outcome(
            status=ProcessingAttemptStatus.FAILED,
            failure=ProcessingFailure(
                code="failed",
                failure_type="RuntimeError",
                stage=ProcessingStage.PARSER,
                safe_message="Failed.",
                retryable=False,
            ),
        )
