from pathlib import Path

import pytest
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import load_config


def test_ledger_init_creates_ledger_and_archive_from_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"

    exit_code = main(
        [
            "ledger",
            "init",
            "--ledger-path",
            str(ledger_path),
            "--archive-path",
            str(archive_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert ledger_path.exists()
    assert archive_path.is_dir()
    assert "Applied migrations: 001" in output


def test_ledger_init_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive_path = tmp_path / "archive"
    args = [
        "ledger",
        "init",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]

    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0

    output = capsys.readouterr().out
    assert "Applied migrations: none" in output


def test_load_config_reads_paths_relative_to_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text('ledger_path = "state/kotekomi.db"\narchive_path = "state/archive"\n')

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.ledger_path == (tmp_path / "state" / "kotekomi.db").resolve()
    assert config.archive_path == (tmp_path / "state" / "archive").resolve()


def test_load_config_allows_flag_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text('ledger_path = "state/kotekomi.db"\narchive_path = "state/archive"\n')

    config = load_config(
        config_path=config_path,
        ledger_path_override=Path("override.db"),
        archive_path_override=Path("override_archive"),
    )

    assert config.ledger_path == Path("override.db").resolve()
    assert config.archive_path == Path("override_archive").resolve()
