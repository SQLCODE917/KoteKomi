from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK_ID = "harness-07-task-receipt-writer"


def _run_cli(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(PROJECT_ROOT), "kotekomi-agent", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _require_task_retrospective() -> None:
    result = _run_cli(["task-retrospective", "--help"])
    if result.returncode != 0:
        pytest.skip("task-retrospective command is not implemented yet")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_records(root: Path) -> tuple[Path, Path]:
    records = root / "records"
    support = records / "support" / "input.json"
    _write_json(support, {"ok": True})

    _write_json(
        records / "specification-freeze.json",
        {
            "schema_version": 1,
            "record_kind": "specification-freeze",
            "task_id": TASK_ID,
            "result": "specification_frozen",
            "created_at": "2026-08-06T12:20:00+00:00",
            "input_records": {"support": {"path": str(support), "sha256": _sha256(support)}},
        },
    )
    _write_json(
        records / "candidate" / "candidate-start.json",
        {
            "schema_version": 1,
            "record_kind": "candidate-start",
            "task_id": TASK_ID,
            "result": "candidate_started",
            "created_at": "2026-08-06T12:30:00+00:00",
        },
    )
    _write_json(
        records / "candidate" / "codex-result.json",
        {
            "schema_version": 1,
            "record_kind": "codex-result",
            "task_id": TASK_ID,
            "result": "codex_completed",
            "created_at": "2026-08-06T12:35:00+00:00",
            "codex": {"duration_seconds": 282, "exit_code": 0},
        },
    )
    _write_json(
        records / "candidate" / "oracle-failure.json",
        {
            "schema_version": 1,
            "record_kind": "oracle-failure",
            "task_id": TASK_ID,
            "result": "oracle_failure_recorded",
            "created_at": "2026-08-06T12:40:00+00:00",
        },
    )
    _write_json(
        records / "oracle-repair.json",
        {
            "schema_version": 1,
            "record_kind": "oracle-repair",
            "task_id": TASK_ID,
            "result": "oracle_repaired",
            "created_at": "2026-08-06T12:44:00+00:00",
        },
    )
    _write_json(
        records / "candidate" / "candidate-audit.json",
        {
            "schema_version": 1,
            "record_kind": "candidate-audit",
            "task_id": TASK_ID,
            "result": "candidate_audit_passed",
            "created_at": "2026-08-06T12:55:00+00:00",
            "audits": {
                "scope": {
                    "status": "clean",
                    "changed_paths": [
                        {"path": "packages/devtools/src/kotekomi_devtools/cli.py"},
                        {"path": "packages/devtools/src/kotekomi_devtools/receipt_writer.py"},
                    ],
                },
                "budget": {
                    "status": "within_budget",
                    "totals": {
                        "production_files": 2,
                        "test_files": 1,
                        "production_diff_lines": 188,
                    },
                },
            },
            "local_checks": {
                "h7_acceptance": "passed",
                "h6_acceptance": "passed",
                "devtools_unit": "passed",
                "ruff": "passed",
                "pyright": "passed",
            },
        },
    )
    _write_json(
        records / "candidate" / "candidate-commit.json",
        {
            "schema_version": 1,
            "record_kind": "candidate-commit",
            "task_id": TASK_ID,
            "result": "candidate_committed",
            "created_at": "2026-08-06T12:56:00+00:00",
            "changed_paths": [
                "packages/devtools/src/kotekomi_devtools/cli.py",
                "packages/devtools/src/kotekomi_devtools/receipt_writer.py",
                "packages/devtools/tests/unit/test_receipt_writer.py",
            ],
        },
    )
    _write_json(
        records / "candidate" / "candidate-ci.json",
        {
            "schema_version": 1,
            "record_kind": "candidate-ci",
            "task_id": TASK_ID,
            "result": "candidate_ci_verified",
            "created_at": "2026-08-06T13:04:00+00:00",
            "github_actions": {"status": "completed", "conclusion": "success"},
        },
    )
    _write_json(
        records / "main-ci.json",
        {
            "schema_version": 1,
            "record_kind": "main-ci",
            "task_id": TASK_ID,
            "result": "main_ci_verified",
            "created_at": "2026-08-06T13:19:00+00:00",
            "github_actions": {"status": "completed", "conclusion": "success"},
        },
    )
    _write_json(
        records / "cleanup.json",
        {
            "schema_version": 1,
            "record_kind": "cleanup",
            "task_id": TASK_ID,
            "result": "cleanup_complete",
            "created_at": "2026-08-06T13:25:00+00:00",
            "final_state": {"worktree_clean": True},
        },
    )

    return records, support


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_task_retrospective_help_lists_core_options() -> None:
    _require_task_retrospective()

    result = _run_cli(["task-retrospective", "--help"])

    assert result.returncode == 0
    assert "RECORDS_DIR" in result.stdout
    assert "--output" in result.stdout
    assert "--markdown" in result.stdout
    assert "--task-id" in result.stdout
    assert "--allow-incomplete" in result.stdout


def test_task_retrospective_writes_deterministic_json_and_markdown(tmp_path: Path) -> None:
    _require_task_retrospective()
    records, _ = _fixture_records(tmp_path)
    output = tmp_path / "out" / "retrospective.json"
    markdown = tmp_path / "out" / "retrospective.md"

    result = _run_cli(
        [
            "task-retrospective",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8").endswith("\n")
    assert markdown.read_text(encoding="utf-8").endswith("\n")

    payload = _load_json(output)
    assert payload["task_id"] == TASK_ID
    assert payload["diagnostics"] == []
    assert payload["records"]["total"] == 10
    assert payload["records"]["by_kind"]["oracle-failure"] == 1
    assert payload["records"]["by_result"]["candidate_ci_verified"] == 1
    assert payload["timeline"]["duration_seconds"] == 3900
    assert payload["events"]["candidate_attempts"] == 1
    assert payload["events"]["oracle_failures"] == 1
    assert payload["events"]["oracle_repairs"] == 1
    assert payload["events"]["cleanup_complete"] is True
    assert payload["ci"]["total"] == 2
    assert payload["ci"]["success"] == 2
    assert payload["audits"]["production_diff_lines"] == 188
    assert payload["checks"]["passed"] >= 5
    assert "packages/devtools/src/kotekomi_devtools/receipt_writer.py" in payload["changed_paths"]

    markdown_text = markdown.read_text(encoding="utf-8")
    assert "# Retrospective: harness-07-task-receipt-writer" in markdown_text
    assert "Oracle repairs: 1" in markdown_text
    assert "CI success: 2/2" in markdown_text

    second_output = tmp_path / "out" / "retrospective-second.json"
    second_markdown = tmp_path / "out" / "retrospective-second.md"
    second = _run_cli(
        [
            "task-retrospective",
            str(records),
            "--output",
            str(second_output),
            "--markdown",
            str(second_markdown),
        ]
    )
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == second_output.read_bytes()
    assert markdown.read_bytes() == second_markdown.read_bytes()


def test_task_retrospective_fails_closed_on_broken_sha_chain(tmp_path: Path) -> None:
    _require_task_retrospective()
    records, support = _fixture_records(tmp_path)
    support.write_text('{"ok": false}\n', encoding="utf-8")
    output = tmp_path / "retrospective.json"
    markdown = tmp_path / "retrospective.md"

    result = _run_cli(
        [
            "task-retrospective",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ]
    )

    assert result.returncode != 0
    assert not output.exists()
    assert not markdown.exists()
    assert "sha" in result.stderr.lower() or "diagnostic" in result.stderr.lower()


def test_task_retrospective_allow_incomplete_reports_diagnostics(tmp_path: Path) -> None:
    _require_task_retrospective()
    records, support = _fixture_records(tmp_path)
    support.write_text('{"ok": false}\n', encoding="utf-8")
    output = tmp_path / "retrospective.json"
    markdown = tmp_path / "retrospective.md"

    result = _run_cli(
        [
            "task-retrospective",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
            "--allow-incomplete",
        ]
    )

    assert result.returncode == 0, result.stderr
    payload = _load_json(output)
    assert payload["diagnostics"]
    assert any("sha" in json.dumps(diagnostic).lower() for diagnostic in payload["diagnostics"])


def test_task_retrospective_task_id_filters_mixed_records(tmp_path: Path) -> None:
    _require_task_retrospective()
    records, _ = _fixture_records(tmp_path)
    _write_json(
        records / "other-task.json",
        {
            "schema_version": 1,
            "record_kind": "cleanup",
            "task_id": "other-task",
            "result": "cleanup_complete",
            "created_at": "2026-08-06T13:30:00+00:00",
        },
    )
    output = tmp_path / "retrospective.json"
    markdown = tmp_path / "retrospective.md"

    result = _run_cli(
        [
            "task-retrospective",
            str(records),
            "--task-id",
            TASK_ID,
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ]
    )

    assert result.returncode == 0, result.stderr
    payload = _load_json(output)
    assert payload["task_id"] == TASK_ID
    assert payload["records"]["total"] == 10
    assert payload["events"]["cleanup_complete"] is True


def test_task_retrospective_does_not_mutate_git(tmp_path: Path) -> None:
    _require_task_retrospective()
    records, _ = _fixture_records(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo, check=True, capture_output=True)

    output = tmp_path / "retrospective.json"
    markdown = tmp_path / "retrospective.md"
    result = _run_cli(
        [
            "task-retrospective",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ],
        cwd=repo,
    )

    assert result.returncode == 0, result.stderr
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    assert status.stdout == ""
