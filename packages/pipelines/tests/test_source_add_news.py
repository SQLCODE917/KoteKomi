from __future__ import annotations

import json
from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_pipelines.cli import main

FIXTURES = Path(__file__).parents[2] / "adapters" / "tests" / "fixtures" / "news"


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "kotekomi.toml"
    path.write_text(
        """
[processing.build_identity]
package_version = "test"
source_revision = "test"
artifact_digest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
representation_policy_version = "structured-news-v1"
""".lstrip()
    )
    return path


def test_source_add_news_cli_is_public_safe_and_idempotent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive_path = tmp_path / "archive"
    config_path = _config(tmp_path)
    assert (
        main(
            [
                "ledger",
                "init",
                "--ledger-path",
                str(ledger_path),
                "--archive-path",
                str(archive_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    args = [
        "--config",
        str(config_path),
        "source",
        "add-news",
        "--adapter",
        "newsml-g2",
        "--payload",
        str(FIXTURES / "newsml" / "original.xml"),
        "--envelope",
        str(FIXTURES / "envelope.json"),
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]

    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "created"
    assert "Project Atlas" not in json.dumps(first)
    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "reused"
    assert second["representation_id"] == first["representation_id"]

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_sources()) == 1
        assert len(repository.list_documents()) == 1
        assert len(repository.list_document_representations()) == 1
