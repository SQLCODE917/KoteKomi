from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK_ID = "harness-09-task-ledger-accountability"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(PROJECT_ROOT), "kotekomi-agent", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _require_goal_check() -> None:
    result = _run_cli(["goal-check", "--help"])
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "goal-check" not in combined:
        pytest.skip("goal-check command is not implemented yet")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt(records: Path, name: str, *, result: str = "verified") -> dict[str, Any]:
    path = records / name
    _write_json(
        path,
        {
            "schema_version": 1,
            "task_id": TASK_ID,
            "record_kind": name.removesuffix(".json"),
            "result": result,
            "created_at": "2026-08-10T13:00:00+00:00",
        },
    )
    return {"path": name, "sha256": _sha256(path)}


def _goals_file(
    root: Path,
    records: Path,
    *,
    missing_in_scope_evidence: bool = False,
    missing_deferred_reason: bool = False,
    missing_deferred_future_task: bool = False,
    missing_out_of_scope_reason: bool = False,
) -> Path:
    evidence = [] if missing_in_scope_evidence else [_receipt(records, "main-ci.json")]
    deferred: dict[str, Any] = {
        "id": "H9-G7",
        "statement": "Implement scaffold-task.",
        "disposition": "deferred",
    }
    if not missing_deferred_reason:
        deferred["reason"] = "Separate task with its own manifest and acceptance oracle."
    if not missing_deferred_future_task:
        deferred["future_task"] = "harness-10-task-scaffold-task"

    out_of_scope: dict[str, Any] = {
        "id": "H9-GX",
        "statement": "Rewrite unrelated product code.",
        "disposition": "out_of_scope",
    }
    if not missing_out_of_scope_reason:
        out_of_scope["reason"] = "Outside the implementation-agent harness bounded context."

    path = root / "goals.json"
    _write_json(
        path,
        {
            "schema_version": 1,
            "task_id": TASK_ID,
            "goals": [
                {
                    "id": "H9-G1",
                    "statement": "Turn prose goals into tracked obligations.",
                    "disposition": "in_scope",
                    "evidence": evidence,
                },
                deferred,
                out_of_scope,
            ],
        },
    )
    return path


def test_goal_check_help_lists_core_options() -> None:
    _require_goal_check()

    result = _run_cli(["goal-check", "--help"])

    assert result.returncode == 0
    assert "GOALS_FILE" in result.stdout
    assert "--records-dir" in result.stdout
    assert "--output" in result.stdout
    assert "--markdown" in result.stdout


def test_goal_check_writes_deterministic_json_and_markdown(tmp_path: Path) -> None:
    _require_goal_check()
    records = tmp_path / "records"
    goals = _goals_file(tmp_path, records)
    output = tmp_path / "out" / "goal-report.json"
    markdown = tmp_path / "out" / "goal-report.md"

    first = _run_cli(
        [
            "goal-check",
            str(goals),
            "--records-dir",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ]
    )

    assert first.returncode == 0, first.stderr
    assert output.read_text(encoding="utf-8").endswith("\n")
    assert markdown.read_text(encoding="utf-8").endswith("\n")

    payload = _load_json(output)
    assert payload["status"] == "ready"
    assert payload["task_id"] == TASK_ID
    assert payload["diagnostics"] == []
    assert payload["counts"] == {
        "deferred": 1,
        "in_scope": 1,
        "met": 1,
        "out_of_scope": 1,
        "total": 3,
        "unmet": 0,
    }

    markdown_text = markdown.read_text(encoding="utf-8")
    assert "# Goal Report: harness-09-task-ledger-accountability" in markdown_text
    assert "Goal coverage: ready" in markdown_text
    assert "H9-G1" in markdown_text

    second_output = tmp_path / "out" / "goal-report-second.json"
    second_markdown = tmp_path / "out" / "goal-report-second.md"
    second = _run_cli(
        [
            "goal-check",
            str(goals),
            "--records-dir",
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


def test_goal_check_fails_for_missing_in_scope_evidence(tmp_path: Path) -> None:
    _require_goal_check()
    records = tmp_path / "records"
    goals = _goals_file(tmp_path, records, missing_in_scope_evidence=True)
    output = tmp_path / "goal-report.json"
    markdown = tmp_path / "goal-report.md"

    result = _run_cli(
        [
            "goal-check",
            str(goals),
            "--records-dir",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ]
    )

    assert result.returncode == 1
    payload = _load_json(output)
    assert payload["status"] == "not_ready"
    diagnostics = cast(list[dict[str, str]], payload["diagnostics"])
    assert any(item["code"] == "h9.goal.evidence_missing" for item in diagnostics)


def test_goal_check_fails_for_deferred_goal_without_future_task(tmp_path: Path) -> None:
    _require_goal_check()
    records = tmp_path / "records"
    goals = _goals_file(tmp_path, records, missing_deferred_future_task=True)
    output = tmp_path / "goal-report.json"
    markdown = tmp_path / "goal-report.md"

    result = _run_cli(
        [
            "goal-check",
            str(goals),
            "--records-dir",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ]
    )

    assert result.returncode == 1
    diagnostics = cast(list[dict[str, str]], _load_json(output)["diagnostics"])
    assert any(item["code"] == "h9.goal.future_task_missing" for item in diagnostics)


def test_goal_check_fails_for_out_of_scope_goal_without_reason(tmp_path: Path) -> None:
    _require_goal_check()
    records = tmp_path / "records"
    goals = _goals_file(tmp_path, records, missing_out_of_scope_reason=True)
    output = tmp_path / "goal-report.json"
    markdown = tmp_path / "goal-report.md"

    result = _run_cli(
        [
            "goal-check",
            str(goals),
            "--records-dir",
            str(records),
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ]
    )

    assert result.returncode == 1
    diagnostics = cast(list[dict[str, str]], _load_json(output)["diagnostics"])
    assert any(item["code"] == "h9.goal.out_of_scope_reason_missing" for item in diagnostics)
