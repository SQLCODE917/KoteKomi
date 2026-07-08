from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import ReviewStatus
from kotekomi_pipelines.cli import main

SOURCE_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
MODEL_OUTPUT_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "model_outputs"
    / "anthropic_model_release_review_proposals.json"
)


def ledger_init_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "ledger",
        "init",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def source_add_file_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "source",
        "add-file",
        str(SOURCE_FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def propose_assertions_args(
    ledger_path: Path,
    archive_path: Path,
    document_id: str,
) -> list[str]:
    return [
        "source",
        "propose-assertions",
        "--document-id",
        document_id,
        "--model-output-fixture",
        str(MODEL_OUTPUT_FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def test_source_propose_assertions_creates_pending_proposed_changes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    assert main(source_add_file_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = repository.list_documents()[0]

    exit_code = main(propose_assertions_args(ledger_path, archive_path, document.id))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"Document: {document.id}" in output
    assert "ProposedChanges: 10" in output
    with sqlite_ledger_transaction(ledger_path) as repository:
        proposed_changes = repository.list_proposed_changes()
        proposal_activities = tuple(
            activity
            for activity in repository.list_provenance_activities()
            if activity.activity_type == "model_assertion_proposal"
        )
        assert repository.list_actors() == ()
        assert repository.list_organizations() == ()
        assert repository.list_events() == ()
        assert repository.list_evidence_spans() == ()
        assert repository.list_assertions() == ()
        assert repository.list_relationships() == ()
        assert repository.list_outcomes() == ()

    assert len(proposed_changes) == 10
    assert len(proposal_activities) == 1
    proposal_activity = proposal_activities[0]
    assert proposal_activity.agent == "fixture-extraction-runtime"
    assert proposal_activity.input_ids == (document.id,)
    assert set(proposal_activity.output_ids) == {
        proposed_change.id for proposed_change in proposed_changes
    }
    assert {proposed_change.review_status for proposed_change in proposed_changes} == {
        ReviewStatus.PENDING
    }
    assert {proposed_change.source_id for proposed_change in proposed_changes} == {
        document.source_id
    }
    assert {proposed_change.document_id for proposed_change in proposed_changes} == {document.id}
    assert {proposed_change.model_name for proposed_change in proposed_changes} == {
        "fixture-extraction-runtime"
    }
    assert {proposed_change.prompt_id for proposed_change in proposed_changes} == {
        "propose_assertions"
    }
    record_types: set[str] = set()
    for proposed_change in proposed_changes:
        record_type = proposed_change.proposed_json["record_type"]
        assert isinstance(record_type, str)
        record_types.add(record_type)
    assert record_types.issuperset(
        {
            "Actor",
            "Organization",
            "Event",
            "Assertion",
            "Outcome",
            "Relationship",
            "EvidenceSpan",
        }
    )


def test_source_propose_assertions_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    assert main(source_add_file_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = repository.list_documents()[0]
    args = propose_assertions_args(ledger_path, archive_path, document.id)

    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0

    with sqlite_ledger_transaction(ledger_path) as repository:
        proposal_activities = tuple(
            activity
            for activity in repository.list_provenance_activities()
            if activity.activity_type == "model_assertion_proposal"
        )
        assert len(repository.list_proposed_changes()) == 10
        assert len(proposal_activities) == 1
