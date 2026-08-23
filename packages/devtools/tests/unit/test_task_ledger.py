from __future__ import annotations

import json
from pathlib import Path

import pytest
from kotekomi_devtools.task_ledger import (
    TaskLedgerError,
    next_task,
    task_status,
    update_task_ledger,
)


def test_task_completion_gate_requires_ready_goal_coverage_without_writing(tmp_path: Path) -> None:
    evidence = tmp_path / "cleanup.json"
    evidence.write_text("cleanup\n", encoding="utf-8")
    ledger = _ledger(tmp_path, goal_coverage="not_ready")
    original = ledger.read_bytes()

    with pytest.raises(TaskLedgerError, match="goal coverage") as error:
        update_task_ledger(ledger, "task-one", status="complete", evidence=evidence, output=ledger)

    assert error.value.code == "h9.task.goals_unmet"
    assert ledger.read_bytes() == original


def test_task_ledger_preserves_order_and_writes_stable_completion_update(tmp_path: Path) -> None:
    evidence = tmp_path / "cleanup.json"
    evidence.write_text("cleanup\n", encoding="utf-8")
    ledger = _ledger(tmp_path, goal_coverage="ready")
    first, second = tmp_path / "first.json", tmp_path / "second.json"

    assert next_task(ledger)["task_id"] == "task-two"
    assert task_status(ledger, "task-one")["next_required_action"] == "complete"
    update_task_ledger(ledger, "task-one", status="complete", evidence=evidence, output=first)
    update_task_ledger(ledger, "task-one", status="complete", evidence=evidence, output=second)

    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8"))["tasks"][0]["status"] == "complete"


def test_task_transition_requires_the_expected_previous_status(tmp_path: Path) -> None:
    evidence = tmp_path / "cleanup.json"
    evidence.write_text("cleanup\n", encoding="utf-8")
    ledger = _ledger(tmp_path, goal_coverage="ready", status="planned")

    with pytest.raises(TaskLedgerError, match="transition") as error:
        update_task_ledger(
            ledger, "task-one", status="complete", evidence=evidence, output=tmp_path / "out.json"
        )

    assert error.value.code == "h9.task.transition_invalid"


def _ledger(root: Path, *, goal_coverage: str, status: str = "main_verified") -> Path:
    path = root / "ledger.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "current_task": "task-one",
                "tasks": [
                    {
                        "task_id": "task-one",
                        "title": "Task one",
                        "status": status,
                        "goal_coverage": goal_coverage,
                        "evidence": {},
                    },
                    {
                        "task_id": "task-two",
                        "title": "Task two",
                        "status": "planned",
                        "goal_coverage": "not_started",
                        "evidence": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
