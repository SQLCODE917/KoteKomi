from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_pipelines.cli import main

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
FIXTURE_TITLE = "Anthropic delayed model rollout after U.S. review raised cyber-safety concerns"


def ledger_init_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "ledger",
        "init",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def test_source_add_file_ingests_fixture_into_ledger_and_archive(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()

    exit_code = main(
        [
            "source",
            "add-file",
            str(FIXTURE_PATH),
            "--ledger-path",
            str(ledger_path),
            "--archive-path",
            str(archive_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Source created: src_" in output
    with sqlite_ledger_transaction(ledger_path) as repository:
        sources = repository.list_sources()
        documents = repository.list_documents()
        provenance_activities = repository.list_provenance_activities()

    assert len(sources) == 1
    assert len(documents) == 1
    assert len(provenance_activities) == 1
    source = sources[0]
    document = documents[0]
    provenance_activity = provenance_activities[0]
    assert source.title == FIXTURE_TITLE
    assert document.raw_path.startswith("sources/raw/src_")
    assert document.extracted_text_path is not None
    assert document.extracted_text_path.startswith("documents/extracted/doc_")
    assert (archive_path / document.raw_path).is_file()
    assert (archive_path / document.extracted_text_path).is_file()
    assert provenance_activity.activity_type == "source_file_ingest"
    assert provenance_activity.output_ids == (source.id, document.id)


def test_source_add_file_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    args = [
        "source",
        "add-file",
        str(FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]

    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0

    output = capsys.readouterr().out
    assert "Source already_exists: src_" in output
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_sources()) == 1
        assert len(repository.list_documents()) == 1
        assert len(repository.list_provenance_activities()) == 1
