from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import IngestionRunStatus
from kotekomi_pipelines.cli import main

FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
SOURCE_URL = "https://example.test/articles/anthropic-review"
PDF_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "tests"
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)


def _config(tmp_path: Path) -> Path:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        f'''
ledger_path = "{(tmp_path / "state" / "kotekomi.db").as_posix()}"
archive_path = "{(tmp_path / "state" / "archive").as_posix()}"

[processing.build_identity]
package_version = "test"
source_revision = "test"
artifact_digest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
representation_policy_version = "1"
'''.lstrip(),
        encoding="utf-8",
    )
    return config_path


def test_user_ingest_auto_initializes_storage_and_records_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)

    assert (
        main(["--config", str(config_path), "ingest", str(FIXTURE_PATH), "--url", SOURCE_URL])
        == 0
    )
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith("anthropic_model_release_review.md\t[CAPTURED]\t")
    assert "src_" not in captured.out
    assert (
        main(["--config", str(config_path), "ingestions", "list"])
        == 0
    )
    history = capsys.readouterr()
    assert history.err == ""
    assert history.out == captured.out
    assert history.out.count("\t") == 2


def test_user_ingest_retry_creates_two_runs_and_reuses_capture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)
    command = ["--config", str(config_path), "ingest", str(FIXTURE_PATH), "--url", SOURCE_URL]

    assert main(command) == 0
    capsys.readouterr()
    assert main(command) == 0
    capsys.readouterr()
    ledger_path = tmp_path / "state" / "kotekomi.db"
    with sqlite_ledger_transaction(ledger_path) as repository:
        runs = repository.list_ingestion_runs()
        sources = repository.list_sources()
        documents = repository.list_documents()

    assert len(runs) == 2
    assert all(run.status is IngestionRunStatus.CAPTURED for run in runs)
    assert runs[0].source_id == runs[1].source_id
    assert runs[0].document_id == runs[1].document_id
    assert len(sources) == 1
    assert len(documents) == 1


def test_user_ingest_accepts_project_pdf_and_text_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)
    text_path = tmp_path / "deposited.txt"
    text_path.write_text("A deposited text fixture.\n", encoding="utf-8")

    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingest",
                str(PDF_FIXTURE_PATH),
                "--url",
                "https://example.test/articles/community-health-plan",
            ]
        )
        == 0
    )
    assert "[CAPTURED]" in capsys.readouterr().out
    assert (
        main(
            [
                "--config",
                str(config_path),
                "ingest",
                str(text_path),
                "--url",
                "https://example.test/articles/deposited-text",
            ]
        )
        == 0
    )
    assert "[CAPTURED]" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("path", "url", "message"),
    [
        ("missing.md", SOURCE_URL, "not found"),
        ("unsupported.docx", SOURCE_URL, "not supported"),
        (str(FIXTURE_PATH), "http://example.test/not-https", "absolute HTTPS URL"),
    ],
)
def test_user_ingest_persists_expected_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    path: str,
    url: str,
    message: str,
) -> None:
    config_path = _config(tmp_path)

    assert main(["--config", str(config_path), "ingest", path, "--url", url]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert message in output.err
    assert "src_" not in output.err
    with sqlite_ledger_transaction(tmp_path / "state" / "kotekomi.db") as repository:
        runs = repository.list_ingestion_runs()
    assert len(runs) == 1
    assert runs[0].status is IngestionRunStatus.ERROR


def test_user_ingest_syntax_failure_creates_no_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = _config(tmp_path)

    with pytest.raises(SystemExit) as error:
        main(["--config", str(config_path), "ingest", str(FIXTURE_PATH)])

    assert error.value.code == 2
    assert not (tmp_path / "state" / "kotekomi.db").exists()
    assert "--url" in capsys.readouterr().err


def test_user_ingest_records_unexpected_capture_failure_without_a_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _config(tmp_path)

    def raise_capture_failure(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("internal source text must not be displayed")

    monkeypatch.setattr(
        "kotekomi_pipelines.cli.commit_authoritative_capture", raise_capture_failure
    )

    assert (
        main(["--config", str(config_path), "ingest", str(FIXTURE_PATH), "--url", SOURCE_URL])
        == 1
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert "could not be captured" in output.err
    assert "internal source text" not in output.err
    with sqlite_ledger_transaction(tmp_path / "state" / "kotekomi.db") as repository:
        runs = repository.list_ingestion_runs()
    assert runs[0].status is IngestionRunStatus.ERROR
