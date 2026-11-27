"""Public Wiki command behavior with real storage, selection, rendering and publication."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import kotekomi_pipelines.cli as cli
import pytest

from packages.pipelines.tests.support.candidate_wiki_fixture import seed_wiki_example


def _build(config: Path, *arguments: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(Path(sys.executable).with_name("kotekomi")),
            "--config",
            str(config),
            "wiki",
            "build",
            *arguments,
            "--candidate",
        ],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _active_run(root: Path) -> str:
    manifest = root / "archive/review/wiki/manifest.json"
    return str(json.loads(manifest.read_text())["ingestion_run_id"])


def _files(directory: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    }


def _ledger_contents(root: Path) -> tuple[str, ...]:
    with sqlite3.connect(root / "kotekomi.db") as connection:
        return tuple(connection.iterdump())


def test_explicit_selection_publishes_the_selected_ingestion_and_preserves_state(
    tmp_path: Path,
) -> None:
    config = seed_wiki_example(tmp_path)
    ledger_before = _ledger_contents(tmp_path)
    active = tmp_path / "archive/review/wiki"
    builds = tmp_path / "archive/review/wiki-builds"

    older = _build(config, "report.pdf", "--ingestion-run", "igr_older")
    assert older.returncode == 0, older.stderr
    assert older.stdout.strip() == "review/wiki/"
    assert "Select ingestion" not in older.stdout + older.stderr
    assert _active_run(tmp_path) == "igr_older"
    old_build = active.resolve()
    old_files = _files(old_build)

    repeated = _build(config, "report.pdf", "--ingestion-run", "igr_older")
    assert repeated.returncode == 0, repeated.stderr
    assert active.resolve() == old_build
    assert len(tuple(builds.iterdir())) == 1
    assert _files(old_build) == old_files

    newer = _build(config, "report.pdf", "--ingestion-run", "igr_newer")
    assert newer.returncode == 0, newer.stderr
    assert _active_run(tmp_path) == "igr_newer"
    assert active.resolve() != old_build
    assert len(tuple(builds.iterdir())) == 2
    assert _files(old_build) == old_files
    current_build = active.resolve()
    published_files = _files(builds)

    for filename, run_id, error in (
        ("report.pdf", "igr_missing", "Unknown ingestion run"),
        ("report.pdf", "igr_unclosed", "not eligible"),
        ("other.pdf", "igr_older", "does not match filename"),
    ):
        rejected = _build(config, filename, "--ingestion-run", run_id)
        assert rejected.returncode == 1
        assert error in rejected.stderr
        assert active.resolve() == current_build
        assert _files(builds) == published_files
    assert _ledger_contents(tmp_path) == ledger_before


@pytest.mark.parametrize("single_ingestion", [True, False])
def test_filename_only_build_retains_single_and_interactive_selection(
    tmp_path: Path,
    single_ingestion: bool,
) -> None:
    config = seed_wiki_example(tmp_path, single_ingestion=single_ingestion)
    # The interactive list is newest first; choose its older entry.
    result = _build(config, "report.pdf", stdin="" if single_ingestion else "2\n")
    assert result.returncode == 0, result.stderr
    assert _active_run(tmp_path) == "igr_older"


def test_public_candidate_wiki_audit_command_dispatches_with_stable_record_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_audit(
        *,
        config_path: Path | None,
        build_id: str,
        record_id: str,
        output_format: str,
    ) -> int:
        received.update(
            config_path=config_path,
            build_id=build_id,
            record_id=record_id,
            output_format=output_format,
        )
        return 0

    monkeypatch.setattr(cli, "audit_candidate_wiki", fake_audit)

    result = cli.main(
        [
            "--config",
            "/tmp/kotekomi.toml",
            "wiki",
            "audit",
            "--build-id",
            "wkb_example",
            "--record-id",
            "evt_example",
            "--format",
            "json",
        ]
    )

    assert result == 0
    assert received == {
        "config_path": Path("/tmp/kotekomi.toml"),
        "build_id": "wkb_example",
        "record_id": "evt_example",
        "output_format": "json",
    }
