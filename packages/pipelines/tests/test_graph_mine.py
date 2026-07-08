from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import ProposedChange, ReviewStatus
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


def review_approve_args(ledger_path: Path, proposed_change_id: str) -> list[str]:
    return [
        "review",
        "approve",
        "--proposed-change-id",
        proposed_change_id,
        "--reviewer",
        "analyst",
        "--ledger-path",
        str(ledger_path),
    ]


def graph_mine_args(ledger_path: Path) -> list[str]:
    return [
        "graph",
        "mine",
        "--ledger-path",
        str(ledger_path),
    ]


def test_graph_mine_creates_pending_connection_proposals_and_is_idempotent(
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
    assert main(propose_assertions_args(ledger_path, archive_path, document.id)) == 0
    capsys.readouterr()
    with sqlite_ledger_transaction(ledger_path) as repository:
        initial_proposed_change_ids = tuple(
            proposed_change.id for proposed_change in repository.list_proposed_changes()
        )
    for proposed_change_id in initial_proposed_change_ids:
        assert main(review_approve_args(ledger_path, proposed_change_id)) == 0
        capsys.readouterr()

    exit_code = main(graph_mine_args(ledger_path))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Candidates: 1" in output
    assert "ProposedChanges: 4" in output
    assert "ProvenanceActivity: prv_" in output
    with sqlite_ledger_transaction(ledger_path) as repository:
        mined_changes = tuple(
            proposed_change
            for proposed_change in repository.list_proposed_changes()
            if proposed_change.review_status is ReviewStatus.PENDING
        )
        mining_activities = tuple(
            activity
            for activity in repository.list_provenance_activities()
            if activity.activity_type == "graph_connection_mining"
        )

    assert len(mined_changes) == 4
    assert len(mining_activities) == 1
    assert sorted(record_type(change) for change in mined_changes) == [
        "ArgumentEdge",
        "ArgumentEdge",
        "Assertion",
        "Relationship",
    ]
    assert {stable_label(change).split("_", maxsplit=1)[0] for change in mined_changes} == {
        "argument",
        "assertion",
        "relationship",
    }
    assert all(change.provenance_activity_id == mining_activities[0].id for change in mined_changes)

    assert main(graph_mine_args(ledger_path)) == 0
    rerun_output = capsys.readouterr().out
    assert "Candidates: 1" in rerun_output
    assert "ProposedChanges: 0" in rerun_output
    assert "ProvenanceActivity: none" in rerun_output
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_proposed_changes()) == 14


def record_type(proposed_change: ProposedChange) -> str:
    value = proposed_change.proposed_json["record_type"]
    assert isinstance(value, str)
    return value


def stable_label(proposed_change: ProposedChange) -> str:
    value = proposed_change.proposed_json["stable_label"]
    assert isinstance(value, str)
    return value
