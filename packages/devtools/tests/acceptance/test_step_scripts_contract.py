from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast


def _state_file(tmp_path: Path, **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "branch": "harness/h12-step-script-safety-candidate-01",
        "head": "candidate-head",
        "origin_main": "main-base",
        "remote_refs": {},
        "worktree_status": "",
    }
    payload.update(overrides)
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "kotekomi-agent", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _json(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _rules(payload: dict[str, Any]) -> set[str]:
    diagnostics_value = payload.get("diagnostics", [])
    assert isinstance(diagnostics_value, list)
    diagnostics = cast(list[object], diagnostics_value)
    rules: set[str] = set()
    for item in diagnostics:
        if isinstance(item, dict):
            diagnostic = cast(dict[str, Any], item)
            rule = diagnostic.get("rule")
            if isinstance(rule, str):
                rules.add(rule)
    return rules


def test_step_preflight_reports_clean_state(tmp_path: Path) -> None:
    state = _state_file(tmp_path)

    result = _run_cli(
        "step-preflight",
        "--task-id",
        "harness-12-step-script-safety",
        "--base",
        "spec-base",
        "--branch",
        "harness/h12-step-script-safety-candidate-01",
        "--expected-origin-main",
        "main-base",
        "--state-file",
        str(state),
    )

    assert result.returncode == 0, result.stderr
    payload = _json(result.stdout)
    assert payload["status"] == "ready"
    assert payload["branch"] == "harness/h12-step-script-safety-candidate-01"
    assert payload["head"] == "candidate-head"
    assert payload["origin_main"] == "main-base"
    assert payload["worktree_status"] == ""


def test_step_preflight_refuses_dirty_main(tmp_path: Path) -> None:
    state = _state_file(
        tmp_path,
        branch="main",
        worktree_status=" M packages/devtools/src/kotekomi_devtools/cli.py",
    )

    result = _run_cli(
        "step-preflight",
        "--task-id",
        "harness-12-step-script-safety",
        "--base",
        "main-base",
        "--branch",
        "main",
        "--state-file",
        str(state),
    )

    assert result.returncode == 1
    payload = _json(result.stdout)
    assert payload["status"] == "invalid"
    assert "dirty_main_refused" in _rules(payload)


def test_step_preflight_simulates_known_candidate_recovery(
    tmp_path: Path,
) -> None:
    state = _state_file(
        tmp_path,
        head="failed-attempt",
        worktree_status=" M packages/devtools/src/kotekomi_devtools/cli.py",
    )

    result = _run_cli(
        "step-preflight",
        "--task-id",
        "harness-12-step-script-safety",
        "--base",
        "spec-base",
        "--branch",
        "harness/h12-step-script-safety-candidate-01",
        "--recover-candidate",
        "--state-file",
        str(state),
    )

    assert result.returncode == 0, result.stderr
    payload = _json(result.stdout)
    assert payload["status"] == "ready"
    assert payload["recovered"] is True
    assert payload["head"] == "spec-base"
    assert payload["worktree_status"] == ""


def test_record_step_failure_writes_machine_readable_record(
    tmp_path: Path,
) -> None:
    state = _state_file(
        tmp_path,
        head="failed-head",
        worktree_status=" M generated-script.sh",
    )
    output = tmp_path / "failure.json"

    result = _run_cli(
        "record-step-failure",
        "--task-id",
        "harness-12-step-script-safety",
        "--step",
        "step185",
        "--reason",
        "synthetic failure",
        "--state-file",
        str(state),
        "--output",
        str(output),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    record = cast(dict[str, Any], payload)
    assert record["schema_version"] == 1
    assert record["status"] == "failed"
    assert record["task_id"] == "harness-12-step-script-safety"
    assert record["step"] == "step185"
    assert record["reason"] == "synthetic failure"
    assert record["head"] == "failed-head"
    assert record["worktree_status"] == " M generated-script.sh"
