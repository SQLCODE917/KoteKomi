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
        raw_blobs = repository.list_raw_blobs()
        source_captures = repository.list_source_captures()
        document_representations = repository.list_document_representations()
        text_views = repository.list_text_views()
        document_nodes = repository.list_document_nodes()
        parse_quality_reports = repository.list_parse_quality_reports()
        provenance_activities = repository.list_provenance_activities()

    assert len(sources) == 1
    assert len(documents) == 1
    assert len(raw_blobs) == 1
    assert len(source_captures) == 1
    assert len(document_representations) == 1
    assert len(text_views) == 1
    assert len(document_nodes) == 1
    assert len(parse_quality_reports) == 1
    assert len(provenance_activities) == 1
    source = sources[0]
    document = documents[0]
    provenance_activity = provenance_activities[0]
    assert source.title == FIXTURE_TITLE
    assert document.raw_path.startswith("sources/raw/blb_")
    assert document.extracted_text_path is not None
    assert document.extracted_text_path.startswith("documents/extracted/doc_")
    assert (archive_path / document.raw_path).is_file()
    assert (archive_path / document.extracted_text_path).is_file()
    assert provenance_activity.activity_type == "source_file_ingest"
    assert provenance_activity.output_ids == (
        source.id,
        raw_blobs[0].id,
        source_captures[0].id,
        document.id,
        document_representations[0].id,
        f"tvw_{document_representations[0].id.removeprefix('rep_')}_logical",
        f"nod_{document_representations[0].id.removeprefix('rep_')}_document",
        f"pqr_{document_representations[0].id.removeprefix('rep_')}_quality_v1",
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        bundle = repository.get_document_representation_bundle(document_representations[0].id)
    assert bundle is not None
    assert bundle.nodes[0].text == text_views[0].text


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
        assert len(repository.list_document_representations()) == 1
        assert len(repository.list_text_views()) == 1
        assert len(repository.list_document_nodes()) == 1
        assert len(repository.list_parse_quality_reports()) == 1
        assert len(repository.list_provenance_activities()) == 1
