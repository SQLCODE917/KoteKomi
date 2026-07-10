from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
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


def graph_project_args(ledger_path: Path) -> list[str]:
    return [
        "graph",
        "project",
        "--ledger-path",
        str(ledger_path),
    ]


def ledger_counts(ledger_path: Path) -> dict[str, int]:
    with sqlite_ledger_transaction(ledger_path) as repository:
        return {
            "actors": len(repository.list_actors()),
            "organizations": len(repository.list_organizations()),
            "places": len(repository.list_places()),
            "events": len(repository.list_events()),
            "sources": len(repository.list_sources()),
            "documents": len(repository.list_documents()),
            "evidence_spans": len(repository.list_evidence_spans()),
            "assertions": len(repository.list_assertions()),
            "relationships": len(repository.list_relationships()),
            "outcomes": len(repository.list_outcomes()),
            "argument_edges": len(repository.list_argument_edges()),
            "provenance_activities": len(repository.list_provenance_activities()),
            "proposed_changes": len(repository.list_proposed_changes()),
            "briefings": len(repository.list_briefings()),
        }


def test_graph_project_reports_projection_without_writing_ledger(
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
        proposed_changes = repository.list_proposed_changes()
    approve_proposed_changes_in_review_order(
        ledger_path=ledger_path,
        proposed_changes=proposed_changes,
        main=main,
        review_approve_args=review_approve_args,
        clear_output=capsys.readouterr,
    )
    counts_before = ledger_counts(ledger_path)

    exit_code = main(graph_project_args(ledger_path))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Graph nodes: 18" in output
    assert "Graph edges: 34" in output
    assert ledger_counts(ledger_path) == counts_before
