from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import ProposedChange, ReviewStatus
from kotekomi_pipelines.cli import main

from packages.pipelines.tests.review_helpers import approve_proposed_changes_in_review_order

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
        "--model-runtime",
        "fixture",
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
        initial_proposed_changes = repository.list_proposed_changes()
    approve_proposed_changes_in_review_order(
        ledger_path=ledger_path,
        proposed_changes=initial_proposed_changes,
        main=main,
        review_approve_args=review_approve_args,
        clear_output=capsys.readouterr,
    )

    exit_code = main(graph_mine_args(ledger_path))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Candidates: 1" in output
    assert "ProposedChanges: 5" in output
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

    assert len(mined_changes) == 5
    assert len(mining_activities) == 1
    assert sorted(record_type(change) for change in mined_changes) == [
        "ArgumentEdge",
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
        assert len(repository.list_proposed_changes()) == 21

    approve_proposed_changes_in_review_order(
        ledger_path=ledger_path,
        proposed_changes=mined_changes,
        main=main,
        review_approve_args=review_approve_args,
        clear_output=capsys.readouterr,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_assertions()) == 4
        assert len(repository.list_relationships()) == 2
        assert len(repository.list_argument_edges()) == 3
        assert all(
            proposed_change.review_status is ReviewStatus.APPROVED
            for proposed_change in repository.list_proposed_changes()
        )

    assert main(graph_mine_args(ledger_path)) == 0
    accepted_rerun_output = capsys.readouterr().out
    assert "Candidates: 0" in accepted_rerun_output
    assert "ProposedChanges: 0" in accepted_rerun_output
    assert "ProvenanceActivity: none" in accepted_rerun_output


def record_type(proposed_change: ProposedChange) -> str:
    value = proposed_change.proposed_json["record_type"]
    assert isinstance(value, str)
    return value


def stable_label(proposed_change: ProposedChange) -> str:
    value = proposed_change.proposed_json["stable_label"]
    assert isinstance(value, str)
    return value
