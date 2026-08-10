"""Deterministic task ledger reads, status decisions, and updates."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

type JsonObject = dict[str, object]
type TaskStatus = Literal[
    "planned", "in_progress", "candidate_verified", "main_verified", "complete"
]

_STATUSES = frozenset({"planned", "in_progress", "candidate_verified", "main_verified", "complete"})
_TRANSITIONS = {
    "planned": frozenset({"planned", "in_progress"}),
    "in_progress": frozenset({"in_progress", "candidate_verified"}),
    "candidate_verified": frozenset({"candidate_verified", "main_verified"}),
    "main_verified": frozenset({"main_verified", "complete"}),
    "complete": frozenset({"complete"}),
}


class TaskLedgerError(ValueError):
    """Raised when deterministic task-ledger input is invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_json(self) -> JsonObject:
        return {
            "status": "invalid",
            "diagnostics": [{"code": self.code, "location": "ledger", "message": self.message}],
        }


@dataclass(frozen=True)
class TaskLedgerUpdate:
    """The result of a successful, in-memory task ledger transition."""

    task_id: str
    status: TaskStatus
    ledger: JsonObject

    def as_json(self) -> dict[str, str]:
        return {"task_id": self.task_id, "status": self.status}


def current_task(ledger_file: Path) -> JsonObject:
    """Return the uniquely declared current task."""
    ledger = load_task_ledger(ledger_file)
    task_id = cast(str, ledger["current_task"])
    return _task_by_id(ledger, task_id)


def next_task(ledger_file: Path) -> JsonObject:
    """Return the first planned non-current task, preserving ledger array order."""
    ledger = load_task_ledger(ledger_file)
    current = cast(str, ledger["current_task"])
    for task in _tasks(ledger):
        if task["task_id"] != current and task["status"] == "planned":
            return task
    raise TaskLedgerError("h9.task.next_missing", "no planned task follows the current task")


def task_status(ledger_file: Path, task_id: str) -> JsonObject:
    """Return task state together with its next deterministic action."""
    task = _task_by_id(load_task_ledger(ledger_file), task_id)
    result = copy.deepcopy(task)
    result["next_required_action"] = _next_required_action(task)
    return result


def update_task_ledger(
    ledger_file: Path, task_id: str, *, status: str, evidence: Path, output: Path
) -> TaskLedgerUpdate:
    """Validate a transition before atomically writing a stable ledger output."""
    ledger = load_task_ledger(ledger_file)
    task = _task_by_id(ledger, task_id)
    if status not in _STATUSES:
        raise TaskLedgerError("h9.task.status_invalid", "status is not supported")
    target = cast(TaskStatus, status)
    previous = cast(str, task["status"])
    if target not in _TRANSITIONS[previous]:
        raise TaskLedgerError("h9.task.transition_invalid", "status transition is not allowed")
    evidence_reference = _evidence_reference(evidence)
    if target == "complete" and task["goal_coverage"] != "ready":
        raise TaskLedgerError(
            "h9.task.goals_unmet", "goal coverage must be ready before completion"
        )

    updated = copy.deepcopy(ledger)
    updated_task = _task_by_id(updated, task_id)
    updated_task["status"] = target
    updated_evidence = cast(JsonObject, updated_task["evidence"])
    updated_evidence["completion"] = evidence_reference
    _write_json(output, updated)
    return TaskLedgerUpdate(task_id, target, updated)


def load_task_ledger(path: Path) -> JsonObject:
    """Load and strictly validate a Task Ledger V1 document."""
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TaskLedgerError("h9.task.ledger_missing", "ledger file does not exist") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TaskLedgerError("h9.task.ledger_invalid", "ledger file is not valid JSON") from error
    if not isinstance(parsed, dict):
        raise TaskLedgerError("h9.task.ledger_invalid", "ledger must contain an object")
    ledger = cast(JsonObject, parsed)
    if ledger.get("schema_version") != 1 or isinstance(ledger.get("schema_version"), bool):
        raise TaskLedgerError("h9.task.ledger_invalid", "schema_version must equal 1")
    current = ledger.get("current_task")
    if not isinstance(current, str) or not current:
        raise TaskLedgerError("h9.task.ledger_invalid", "current_task must be a non-empty string")
    if not isinstance(ledger.get("tasks"), list):
        raise TaskLedgerError("h9.task.ledger_invalid", "tasks must be a list")
    identifiers: set[str] = set()
    for index, value in enumerate(cast(list[object], ledger["tasks"])):
        if not isinstance(value, dict):
            raise TaskLedgerError("h9.task.ledger_invalid", f"tasks[{index}] must be an object")
        _validate_task(cast(JsonObject, value), index, identifiers)
    if current not in identifiers:
        raise TaskLedgerError("h9.task.current_missing", "current_task does not identify a task")
    return ledger


def _validate_task(task: JsonObject, index: int, identifiers: set[str]) -> None:
    task_id, title, status, coverage, evidence = (
        task.get("task_id"),
        task.get("title"),
        task.get("status"),
        task.get("goal_coverage"),
        task.get("evidence"),
    )
    if not isinstance(task_id, str) or not task_id or not isinstance(title, str) or not title:
        raise TaskLedgerError(
            "h9.task.ledger_invalid", f"tasks[{index}] requires task_id and title"
        )
    if task_id in identifiers:
        raise TaskLedgerError("h9.task.ledger_invalid", f"duplicate task_id: {task_id}")
    identifiers.add(task_id)
    if status not in _STATUSES:
        raise TaskLedgerError("h9.task.ledger_invalid", f"tasks[{index}] has an invalid status")
    if coverage not in {"not_started", "not_ready", "ready"}:
        raise TaskLedgerError("h9.task.ledger_invalid", f"tasks[{index}] has invalid goal_coverage")
    if not isinstance(evidence, dict):
        raise TaskLedgerError(
            "h9.task.ledger_invalid", f"tasks[{index}] evidence must be an object"
        )


def _tasks(ledger: JsonObject) -> list[JsonObject]:
    return [cast(JsonObject, task) for task in cast(list[object], ledger["tasks"])]


def _task_by_id(ledger: JsonObject, task_id: str) -> JsonObject:
    for task in _tasks(ledger):
        if task["task_id"] == task_id:
            return task
    raise TaskLedgerError("h9.task.not_found", f"task does not exist: {task_id}")


def _next_required_action(task: JsonObject) -> str:
    status = cast(str, task["status"])
    if status == "complete":
        return "none"
    if status == "main_verified":
        return "complete" if task["goal_coverage"] == "ready" else "resolve_goal_coverage"
    return {
        "planned": "start",
        "in_progress": "verify_candidate",
        "candidate_verified": "verify_main",
    }[status]


def _evidence_reference(path: Path) -> JsonObject:
    if not path.is_file():
        raise TaskLedgerError(
            "h9.task.evidence_missing", "evidence path does not exist or is not a file"
        )
    try:
        sha256 = _sha256_file(path)
    except OSError as error:
        raise TaskLedgerError(
            "h9.task.evidence_unreadable", "evidence path cannot be read"
        ) from error
    return {"path": str(path), "sha256": sha256}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
