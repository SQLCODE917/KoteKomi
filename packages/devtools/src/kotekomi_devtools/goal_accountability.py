"""Deterministic goal coverage validation and report rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

type JsonObject = dict[str, object]


class GoalAccountabilityError(ValueError):
    """Raised when a goals ledger is not valid deterministic input."""


@dataclass(frozen=True)
class GoalDiagnostic:
    """One stable goal coverage diagnostic."""

    code: str
    location: str
    message: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


@dataclass(frozen=True)
class GoalReport:
    """The deterministic result of accounting for every declared goal."""

    task_id: str
    goals: tuple[JsonObject, ...]
    met_goal_ids: frozenset[str]
    diagnostics: tuple[GoalDiagnostic, ...]

    @property
    def ready(self) -> bool:
        return not self.diagnostics

    def as_json(self) -> JsonObject:
        in_scope = [goal for goal in self.goals if goal["disposition"] == "in_scope"]
        met = sum(cast(str, goal["id"]) in self.met_goal_ids for goal in in_scope)
        return {
            "status": "ready" if self.ready else "not_ready",
            "task_id": self.task_id,
            "counts": {
                "total": len(self.goals),
                "in_scope": len(in_scope),
                "deferred": sum(goal["disposition"] == "deferred" for goal in self.goals),
                "out_of_scope": sum(goal["disposition"] == "out_of_scope" for goal in self.goals),
                "met": met,
                "unmet": len(in_scope) - met,
            },
            "goals": list(self.goals),
            "diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics],
        }

    def markdown(self) -> str:
        lines = [
            f"# Goal Report: {self.task_id}",
            "",
            f"Goal coverage: {'ready' if self.ready else 'not_ready'}",
            "",
            "## Goals",
            "",
        ]
        for goal in self.goals:
            disposition = cast(str, goal["disposition"])
            state = (
                "met"
                if cast(str, goal["id"]) in self.met_goal_ids
                else disposition
                if disposition != "in_scope"
                else "unmet"
            )
            lines.append(f"- {goal['id']} ({goal['disposition']}): {state} — {goal['statement']}")
        if self.diagnostics:
            lines.extend(["", "## Diagnostics", ""])
            lines.extend(
                f"- {diagnostic.code} ({diagnostic.location}): {diagnostic.message}"
                for diagnostic in self.diagnostics
            )
        return "\n".join(lines) + "\n"


def check_goals(goals_file: Path, records_dir: Path) -> GoalReport:
    """Validate all goal dispositions and evidence references without writing state."""
    payload = _load_goals(goals_file)
    task_id = cast(str, payload["task_id"])
    goals = tuple(cast(JsonObject, goal) for goal in cast(list[object], payload["goals"]))
    diagnostics: list[GoalDiagnostic] = []
    met_goal_ids: set[str] = set()
    for index, goal in enumerate(goals):
        if _check_goal(goal, index, records_dir, diagnostics):
            met_goal_ids.add(cast(str, goal["id"]))
    return GoalReport(task_id, goals, frozenset(met_goal_ids), tuple(diagnostics))


def write_goal_report(
    goals_file: Path, records_dir: Path, *, output: Path, markdown: Path
) -> GoalReport:
    """Check goals and write byte-stable JSON and Markdown reports."""
    report = check_goals(goals_file, records_dir)
    _write_text(output, json.dumps(report.as_json(), indent=2, sort_keys=True) + "\n")
    _write_text(markdown, report.markdown())
    return report


def _load_goals(path: Path) -> JsonObject:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GoalAccountabilityError("h9.goal.input_missing: goals file does not exist") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GoalAccountabilityError(
            "h9.goal.input_invalid: goals file is not valid JSON"
        ) from error
    if not isinstance(parsed, dict):
        raise GoalAccountabilityError("h9.goal.input_invalid: goals file must contain an object")
    payload = cast(JsonObject, parsed)
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        raise GoalAccountabilityError("h9.goal.input_invalid: schema_version must equal 1")
    if not _nonempty_string(payload.get("task_id")):
        raise GoalAccountabilityError("h9.goal.input_invalid: task_id must be a non-empty string")
    goals = payload.get("goals")
    if not isinstance(goals, list):
        raise GoalAccountabilityError("h9.goal.input_invalid: goals must be a list")
    identifiers: set[str] = set()
    for index, value in enumerate(cast(list[object], goals)):
        if not isinstance(value, dict):
            raise GoalAccountabilityError(
                f"h9.goal.input_invalid: goals[{index}] must be an object"
            )
        goal = cast(JsonObject, value)
        if not _nonempty_string(goal.get("id")) or not _nonempty_string(goal.get("statement")):
            raise GoalAccountabilityError(
                f"h9.goal.input_invalid: goals[{index}] requires id and statement"
            )
        identifier = cast(str, goal["id"])
        if identifier in identifiers:
            raise GoalAccountabilityError(f"h9.goal.input_invalid: duplicate goal id: {identifier}")
        identifiers.add(identifier)
        if goal.get("disposition") not in {"in_scope", "deferred", "out_of_scope"}:
            raise GoalAccountabilityError(
                f"h9.goal.input_invalid: goals[{index}] has an invalid disposition"
            )
    return payload


def _check_goal(
    goal: JsonObject, index: int, records_dir: Path, diagnostics: list[GoalDiagnostic]
) -> bool:
    disposition = cast(str, goal["disposition"])
    location = f"goals[{index}]"
    if disposition == "in_scope":
        evidence = goal.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            _diagnostic(
                diagnostics, "h9.goal.evidence_missing", location, "in-scope goal has no evidence"
            )
            return False
        valid = True
        for evidence_index, reference in enumerate(cast(list[object], evidence)):
            valid = _check_evidence(
                reference, f"{location}.evidence[{evidence_index}]", records_dir, diagnostics
            ) and valid
        return valid
    elif disposition == "deferred":
        if not _nonempty_string(goal.get("reason")):
            _diagnostic(
                diagnostics,
                "h9.goal.deferred_reason_missing",
                location,
                "deferred goal requires a reason",
            )
        if not _nonempty_string(goal.get("future_task")):
            _diagnostic(
                diagnostics,
                "h9.goal.future_task_missing",
                location,
                "deferred goal requires a future_task",
            )
    elif not _nonempty_string(goal.get("reason")):
        _diagnostic(
            diagnostics,
            "h9.goal.out_of_scope_reason_missing",
            location,
            "out-of-scope goal requires a reason",
        )
    return False


def _check_evidence(
    value: object, location: str, records_dir: Path, diagnostics: list[GoalDiagnostic]
) -> bool:
    if not isinstance(value, dict):
        _diagnostic(diagnostics, "h9.goal.evidence_missing", location, "evidence must be an object")
        return False
    reference = cast(JsonObject, value)
    path_value, expected = reference.get("path"), reference.get("sha256")
    if not _nonempty_string(path_value) or not _sha256(expected):
        _diagnostic(
            diagnostics, "h9.goal.evidence_missing", location, "evidence requires path and sha256"
        )
        return False
    path = Path(cast(str, path_value))
    resolved = path if path.is_absolute() else records_dir / path
    if not resolved.is_file():
        _diagnostic(
            diagnostics, "h9.goal.evidence_missing_file", location, "evidence file does not exist"
        )
        return False
    try:
        actual = _sha256_file(resolved)
    except OSError:
        _diagnostic(
            diagnostics, "h9.goal.evidence_missing_file", location, "evidence file cannot be read"
        )
        return False
    if actual.lower() != cast(str, expected).lower():
        _diagnostic(
            diagnostics,
            "h9.goal.evidence_sha256_mismatch",
            location,
            "evidence sha256 does not match",
        )
        return False
    return True


def _diagnostic(
    diagnostics: list[GoalDiagnostic], code: str, location: str, message: str
) -> None:
    diagnostics.append(GoalDiagnostic(code, location, message))


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdefABCDEF" for character in value
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
