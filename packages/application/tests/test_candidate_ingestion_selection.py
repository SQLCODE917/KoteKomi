"""Ingestion identity and eligibility: typed records in, selection or error out."""

from datetime import UTC, datetime

import pytest
from kotekomi_application.candidate_wiki import (
    select_candidate_ingestion,
    select_candidate_ingestions,
)
from kotekomi_domain import IngestionRun, IngestionRunStatus


def captured_run(
    run_id: str, *, day: int = 4, filename: str = "report.pdf", closed: bool = True
) -> IngestionRun:
    return IngestionRun(
        id=run_id,
        requested_path=f"/input/{filename}",
        display_filename=filename,
        requested_source_url="https://example.test/report",
        normalized_source_url="https://example.test/report",
        status=IngestionRunStatus.CAPTURED,
        started_at=datetime(2026, 9, day, tzinfo=UTC),
        completed_at=datetime(2026, 9, day, tzinfo=UTC),
        source_id="src_example",
        document_id="doc_example",
        representation_id="rep_example",
        provenance_activity_id="prv_example",
        analysis_run_id="arn_example" if closed else None,
        ingestion_change_set_id="ics_example" if closed else None,
    )


def test_explicit_selection_returns_the_named_older_ingestion() -> None:
    older = captured_run("igr_older", day=3)
    newer = captured_run("igr_newer")
    assert select_candidate_ingestion("report.pdf", older.id, (newer, older)) == older


@pytest.mark.parametrize(
    ("run", "selected_id", "error"),
    [
        (captured_run("igr_known"), "igr_missing", "Unknown ingestion run"),
        (captured_run("igr_other", filename="other.pdf"), "igr_other", "does not match filename"),
        (captured_run("igr_unclosed", closed=False), "igr_unclosed", "not eligible"),
        (
            IngestionRun(
                id="igr_running",
                requested_path="/input/report.pdf",
                display_filename="report.pdf",
                requested_source_url="https://example.test/report",
                status=IngestionRunStatus.RUNNING,
                started_at=datetime(2026, 9, 4, tzinfo=UTC),
            ),
            "igr_running",
            "not eligible",
        ),
    ],
)
def test_explicit_selection_rejects_the_wrong_identity_or_ineligible_state(
    run: IngestionRun,
    selected_id: str,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        select_candidate_ingestion("report.pdf", selected_id, (run,))


def test_filename_selection_returns_only_closed_matches_newest_first() -> None:
    older = captured_run("igr_older", day=3)
    newer = captured_run("igr_newer")
    runs = (
        older,
        captured_run("igr_other", filename="other.pdf"),
        captured_run("igr_unclosed", closed=False),
        newer,
    )
    assert select_candidate_ingestions("report.pdf", runs).matches == (newer, older)


@pytest.mark.parametrize("filename", ["", "dir/report.pdf", r"dir\report.pdf"])
def test_both_selectors_reject_non_basename_input(filename: str) -> None:
    runs = (captured_run("igr_known"),)
    with pytest.raises(ValueError, match="exact filename basename"):
        select_candidate_ingestion(filename, "igr_known", runs)
    with pytest.raises(ValueError, match="exact filename basename"):
        select_candidate_ingestions(filename, runs)


@pytest.mark.parametrize("selected_id", ["", " igr_known", "igr_known "])
def test_explicit_selection_requires_an_exact_nonempty_id(selected_id: str) -> None:
    with pytest.raises(ValueError, match="exact non-empty value"):
        select_candidate_ingestion("report.pdf", selected_id, (captured_run("igr_known"),))
