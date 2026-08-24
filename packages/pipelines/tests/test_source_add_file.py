import json
import sqlite3
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
SOURCE_URL = "https://example.test/articles/anthropic-review"
PDF_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "tests"
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)
PDF_SOURCE_URL = "https://example.test/articles/community-health-plan"


def ledger_init_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "ledger",
        "init",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def processing_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        """
[processing]
representation_policy_version = "deposited-source-v1"
""".lstrip()
    )
    return config_path


def test_source_add_file_ingests_fixture_into_ledger_and_archive(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    config_path = processing_config(tmp_path)
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()

    exit_code = main(
        [
            "--config",
            str(config_path),
            "source",
            "add-file",
            str(FIXTURE_PATH),
            "--source-url",
            SOURCE_URL,
            "--ledger-path",
            str(ledger_path),
            "--archive-path",
            str(archive_path),
            "--format",
            "json",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    result = json.loads(output)
    assert result["status"] == "created"
    assert result["source_id"].startswith("src_")
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
    with sqlite3.connect(ledger_path) as connection:
        task_count = connection.execute(
            "SELECT COUNT(*) FROM processing_task_fingerprints"
        ).fetchone()[0]
        attempt_rows = connection.execute(
            "SELECT id FROM processing_attempts ORDER BY started_at, id"
        ).fetchall()
        outcome_rows = connection.execute(
            "SELECT attempt_id, status FROM processing_attempt_outcomes"
        ).fetchall()

    assert len(sources) == 1
    assert len(documents) == 1
    assert len(raw_blobs) == 1
    assert len(source_captures) == 1
    assert len(document_representations) == 1
    assert len(text_views) == 1
    assert len(document_nodes) == 1
    assert len(parse_quality_reports) == 1
    assert len(provenance_activities) == 2
    assert task_count == 1
    assert len(attempt_rows) == 1
    assert outcome_rows == [(attempt_rows[0][0], "succeeded")]
    source = sources[0]
    document = documents[0]
    capture_provenance = next(
        activity
        for activity in provenance_activities
        if activity.activity_type == "deposited_source_capture"
    )
    representation_provenance = next(
        activity
        for activity in provenance_activities
        if activity.activity_type == "source_file_representation"
    )
    assert source.canonical_identity_key == SOURCE_URL
    assert raw_blobs[0].storage_locator.startswith("sources/raw/blb_")
    assert (archive_path / raw_blobs[0].storage_locator).is_file()
    assert capture_provenance.input_ids == (SOURCE_URL, str(FIXTURE_PATH))
    assert capture_provenance.output_ids == (
        source.id,
        raw_blobs[0].id,
        source_captures[0].id,
        document.id,
    )
    assert representation_provenance.input_ids == (
        document.id,
        document_representations[0].processing_task_fingerprint_id,
    )
    assert representation_provenance.output_ids == (
        document_representations[0].id,
        f"tvw_{document_representations[0].id.removeprefix('rep_')}_logical",
        f"nod_{document_representations[0].id.removeprefix('rep_')}_document",
        f"pqr_{document_representations[0].id.removeprefix('rep_')}_quality_v1",
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        bundle = repository.get_document_representation_bundle(document_representations[0].id)
    assert bundle is not None
    assert (bundle.nodes[0].start_char, bundle.nodes[0].end_char) == (0, len(text_views[0].text))


def test_source_add_file_ingests_project_pdf_fixture(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    config_path = processing_config(tmp_path)
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()

    exit_code = main(
        [
            "--config",
            str(config_path),
            "source",
            "add-file",
            str(PDF_FIXTURE_PATH),
            "--source-url",
            PDF_SOURCE_URL,
            "--ledger-path",
            str(ledger_path),
            "--archive-path",
            str(archive_path),
            "--format",
            "json",
        ]
    )

    result = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert result["status"] == "created"
    assert result["representation_id"].startswith("rep_")
    assert result["blocking_reasons"] == []
    with sqlite_ledger_transaction(ledger_path) as repository:
        source = repository.list_sources()[0]
        raw_blob = repository.list_raw_blobs()[0]
        representations = repository.list_document_representations()
    assert source.canonical_identity_key == PDF_SOURCE_URL
    assert (archive_path / raw_blob.storage_locator).read_bytes() == PDF_FIXTURE_PATH.read_bytes()
    assert len(representations) == 1

    assert (
        main(
            [
                "retrieval",
                "build-document",
                "--channel",
                "exact-lexical",
                "--representation-id",
                result["representation_id"],
                "--ledger-path",
                str(ledger_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    build = json.loads(capsys.readouterr().out)
    assert build["status"] == "complete"
    assert build["unit_count"] > 0
    assert (
        main(
            [
                "retrieval",
                "query",
                "--channel",
                "exact-lexical",
                "--representation-id",
                result["representation_id"],
                "--query",
                "community health assessment",
                "--maximum-hits",
                "1",
                "--context-profile",
                "retrieval-validation-v1",
                "--ledger-path",
                str(ledger_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    query = json.loads(capsys.readouterr().out)
    assert query["status"] == "complete"
    assert query["hits"][0]["selection_reason"] == "exact_before_lexical"
    assert "community health assessment" in query["context_manifest_rendered_input"]

    assert (
        main(
            [
                "--config",
                str(config_path),
                "source",
                "add-file",
                str(PDF_FIXTURE_PATH),
                "--source-url",
                PDF_SOURCE_URL,
                "--ledger-path",
                str(ledger_path),
                "--archive-path",
                str(archive_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "reused"


def test_source_add_file_rejects_missing_or_invalid_source_url(
    tmp_path: Path,
) -> None:
    config_path = processing_config(tmp_path)

    with pytest.raises(SystemExit):
        main(["--config", str(config_path), "source", "add-file", str(FIXTURE_PATH)])
    with pytest.raises(ValueError, match="absolute HTTPS URL"):
        main(
            [
                "--config",
                str(config_path),
                "source",
                "add-file",
                str(FIXTURE_PATH),
                "--source-url",
                "http://example.test/article",
            ]
        )


def test_source_add_file_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    config_path = processing_config(tmp_path)
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    args = [
        "--config",
        str(config_path),
        "source",
        "add-file",
        str(FIXTURE_PATH),
        "--source-url",
        SOURCE_URL,
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]

    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0

    output = capsys.readouterr().out
    assert "Source reused: src_" in output
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_sources()) == 1
        assert len(repository.list_documents()) == 1
        assert len(repository.list_document_representations()) == 1
        assert len(repository.list_text_views()) == 1
        assert len(repository.list_document_nodes()) == 1
        assert len(repository.list_parse_quality_reports()) == 1
        assert len(repository.list_provenance_activities()) == 2
    with sqlite3.connect(ledger_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM processing_task_fingerprints").fetchone()[0]
            == 1
        )
        attempts = connection.execute("SELECT id FROM processing_attempts").fetchall()
        outcomes = connection.execute(
            "SELECT attempt_id, status FROM processing_attempt_outcomes"
        ).fetchall()
    assert len(attempts) == 2
    assert {row[0] for row in outcomes} == {row[0] for row in attempts}
    assert {row[1] for row in outcomes} == {"succeeded"}
