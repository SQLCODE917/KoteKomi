from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from kotekomi_devtools.step_scripts import (
    step_failure_payload,
    step_preflight_payload,
)


def _state(tmp_path: Path, **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "branch": "candidate",
        "head": "head",
        "origin_main": "main",
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


def test_step_preflight_clean_state_is_ready(tmp_path: Path) -> None:
    payload = step_preflight_payload(
        task_id="task",
        base="base",
        branch="candidate",
        state_file=_state(tmp_path),
    )

    assert payload["status"] == "ready"
    assert payload["branch"] == "candidate"
    assert payload["worktree_status"] == ""


def test_step_preflight_dirty_main_refuses_by_default(tmp_path: Path) -> None:
    payload = step_preflight_payload(
        task_id="task",
        base="base",
        branch="main",
        state_file=_state(
            tmp_path,
            branch="main",
            worktree_status=" M file",
        ),
    )

    assert payload["status"] == "invalid"
    assert "dirty_main_refused" in _rules(payload)


def test_step_preflight_recovery_resets_injected_candidate_state(
    tmp_path: Path,
) -> None:
    payload = step_preflight_payload(
        task_id="task",
        base="base",
        branch="candidate",
        recover_candidate=True,
        state_file=_state(
            tmp_path,
            head="dirty-head",
            worktree_status=" M file",
        ),
    )

    assert payload["status"] == "ready"
    assert payload["recovered"] is True
    assert payload["head"] == "base"
    assert payload["worktree_status"] == ""


def test_step_failure_payload_records_failure_state(tmp_path: Path) -> None:
    payload = step_failure_payload(
        task_id="task",
        step="step185",
        reason="failed patch",
        state_file=_state(
            tmp_path,
            branch="candidate",
            head="failed-head",
            worktree_status=" M file",
        ),
    )

    assert payload["schema_version"] == 1
    assert payload["status"] == "failed"
    assert payload["branch"] == "candidate"
    assert payload["head"] == "failed-head"
    assert payload["reason"] == "failed patch"
    assert payload["worktree_status"] == " M file"
