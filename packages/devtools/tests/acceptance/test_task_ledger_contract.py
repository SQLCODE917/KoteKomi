from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK_ID = "harness-09-task-ledger-accountability"
NEXT_TASK_ID = "harness-10-task-scaffold-task"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(PROJECT_ROOT), "kotekomi-agent", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _require_task_ledger() -> None:
    result = _run_cli(["task-ledger", "--help"])
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "task-ledger" not in combined:
        pytest.skip("task-ledger command is not implemented yet")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence(root: Path, name: str) -> dict[str, str]:
    path = root / "records" / name
    _write_json(
        path,
        {
            "schema_version": 1,
            "task_id": TASK_ID,
            "record_kind": name.removesuffix(".json"),
            "result": "verified",
            "created_at": "2026-08-10T13:00:00+00:00",
        },
    )
    return {"path": str(path), "sha256": _sha256(path)}


def _ledger(root: Path, *, goal_coverage: str = "ready") -> Path:
    main_ci = _evidence(root, "main-ci.json")
    cleanup = _evidence(root, "cleanup.json")
    path = root / "task-ledger.json"
    _write_json(
        path,
        {
            "schema_version": 1,
            "current_task": TASK_ID,
            "tasks": [
                {
                    "task_id": TASK_ID,
                    "title": "H9 Task Ledger Accountability",
                    "status": "main_verified",
                    "goal_coverage": goal_coverage,
                    "evidence": {
                        "cleanup": cleanup,
                        "main-ci": main_ci,
                    },
                },
                {
                    "task_id": NEXT_TASK_ID,
                    "title": "H10 Scaffold Task",
                    "status": "planned",
                    "goal_coverage": "not_started",
                    "evidence": {},
                },
            ],
        },
    )
    return path


def test_task_ledger_help_lists_core_subcommands() -> None:
    _require_task_ledger()

    result = _run_cli(["task-ledger", "--help"])

    assert result.returncode == 0
    assert "current" in result.stdout
    assert "next" in result.stdout
    assert "status" in result.stdout
    assert "update" in result.stdout


def test_task_ledger_current_and_next_are_deterministic(tmp_path: Path) -> None:
    _require_task_ledger()
    ledger = _ledger(tmp_path)

    current = _run_cli(["task-ledger", "current", str(ledger)])
    next_task = _run_cli(["task-ledger", "next", str(ledger)])

    assert current.returncode == 0, current.stderr
    assert next_task.returncode == 0, next_task.stderr
    assert _stdout_json(current)["task_id"] == TASK_ID
    assert _stdout_json(next_task)["task_id"] == NEXT_TASK_ID


def test_task_ledger_status_reports_next_required_action(tmp_path: Path) -> None:
    _require_task_ledger()
    ledger = _ledger(tmp_path)

    result = _run_cli(["task-ledger", "status", str(ledger), TASK_ID])

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)
    assert payload["task_id"] == TASK_ID
    assert payload["status"] == "main_verified"
    assert payload["goal_coverage"] == "ready"
    assert payload["next_required_action"] == "complete"


def test_task_ledger_update_rejects_completion_with_unmet_goals(tmp_path: Path) -> None:
    _require_task_ledger()
    ledger = _ledger(tmp_path, goal_coverage="not_ready")
    before = ledger.read_bytes()

    result = _run_cli(
        [
            "task-ledger",
            "update",
            str(ledger),
            TASK_ID,
            "--status",
            "complete",
            "--evidence",
            str(tmp_path / "records" / "cleanup.json"),
            "--output",
            str(ledger),
        ]
    )

    assert result.returncode == 1
    assert ledger.read_bytes() == before
    diagnostics = cast(list[dict[str, str]], _stdout_json(result)["diagnostics"])
    assert any(item["code"] == "h9.task.goals_unmet" for item in diagnostics)


def test_task_ledger_update_complete_writes_stable_ledger(tmp_path: Path) -> None:
    _require_task_ledger()
    ledger = _ledger(tmp_path)
    output = tmp_path / "updated-ledger.json"

    first = _run_cli(
        [
            "task-ledger",
            "update",
            str(ledger),
            TASK_ID,
            "--status",
            "complete",
            "--evidence",
            str(tmp_path / "records" / "cleanup.json"),
            "--output",
            str(output),
        ]
    )

    assert first.returncode == 0, first.stderr
    payload = _load_json(output)
    tasks = cast(list[dict[str, Any]], payload["tasks"])
    task = next(item for item in tasks if item["task_id"] == TASK_ID)
    assert task["status"] == "complete"
    assert _stdout_json(first)["status"] == "complete"

    second_output = tmp_path / "updated-ledger-second.json"
    second = _run_cli(
        [
            "task-ledger",
            "update",
            str(ledger),
            TASK_ID,
            "--status",
            "complete",
            "--evidence",
            str(tmp_path / "records" / "cleanup.json"),
            "--output",
            str(second_output),
        ]
    )

    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == second_output.read_bytes()
