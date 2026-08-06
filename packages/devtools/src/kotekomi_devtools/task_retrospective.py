"""Deterministic metrics and Markdown summaries for task lifecycle records."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

type JsonObject = dict[str, object]

_REQUIRED_RECORD_FIELDS = ("schema_version", "record_kind", "task_id", "result", "created_at")


class TaskRetrospectiveError(ValueError):
    """Raised when retrospective input is incomplete and strict mode is selected."""


@dataclass(frozen=True)
class _Record:
    path: Path
    relative_path: str
    value: JsonObject
    created_at: datetime | None


@dataclass(frozen=True)
class TaskRetrospectiveResult:
    task_id: str | None
    output: str
    markdown: str

    def as_json(self) -> dict[str, str | None]:
        return {"task_id": self.task_id, "output": self.output, "markdown": self.markdown}


def write_task_retrospective(
    records_dir: Path,
    *,
    output: Path,
    markdown: Path,
    task_id: str | None = None,
    allow_incomplete: bool = False,
) -> TaskRetrospectiveResult:
    """Read local records, validate their local references, and write both outputs."""
    records, diagnostics = _read_records(records_dir)
    selected = tuple(
        record for record in records if task_id is None or record.value["task_id"] == task_id
    )
    if not selected:
        _diagnostic(
            diagnostics,
            "retrospective.no_matching_records",
            "records",
            "no records matched the requested task",
        )
    inferred_task_id = _infer_task_id(selected, task_id, diagnostics)
    _verify_references(selected, diagnostics)
    if diagnostics and not allow_incomplete:
        raise TaskRetrospectiveError(
            "; ".join(f"{item['code']}: {item['message']}" for item in diagnostics)
        )
    payload = _metrics(selected, inferred_task_id, diagnostics)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown.write_text(_markdown(payload), encoding="utf-8")
    return TaskRetrospectiveResult(inferred_task_id, str(output), str(markdown))


def _diagnostic(diagnostics: list[dict[str, str]], code: str, location: str, message: str) -> None:
    diagnostics.append({"code": code, "location": location, "message": message})


def _read_records(records_dir: Path) -> tuple[tuple[_Record, ...], list[dict[str, str]]]:
    diagnostics: list[dict[str, str]] = []
    if not records_dir.is_dir():
        _diagnostic(
            diagnostics,
            "retrospective.missing_records_directory",
            "records",
            f"records directory does not exist: {records_dir}",
        )
        return (), diagnostics
    records: list[_Record] = []
    for path in sorted(records_dir.rglob("*.json")):
        relative_path = path.relative_to(records_dir).as_posix()
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            message = error.msg if isinstance(error, json.JSONDecodeError) else str(error)
            _diagnostic(
                diagnostics,
                "retrospective.malformed_json",
                relative_path,
                f"unable to parse JSON: {message}",
            )
            continue
        if not isinstance(parsed, dict) or not any(
            field in parsed for field in _REQUIRED_RECORD_FIELDS
        ):
            continue
        value = cast(JsonObject, parsed)
        invalid = False
        for field in _REQUIRED_RECORD_FIELDS:
            valid = (
                isinstance(value.get(field), int) and not isinstance(value.get(field), bool)
                if field == "schema_version"
                else isinstance(value.get(field), str)
            )
            if not valid:
                _diagnostic(
                    diagnostics,
                    "retrospective.invalid_record",
                    f"{relative_path}:{field}",
                    f"{field} must be {'an integer' if field == 'schema_version' else 'a string'}",
                )
                invalid = True
        if invalid:
            continue
        created_at = _parse_created_at(cast(str, value["created_at"]), relative_path, diagnostics)
        records.append(_Record(path, relative_path, value, created_at))
    return tuple(records), diagnostics


def _parse_created_at(
    value: str, relative_path: str, diagnostics: list[dict[str, str]]
) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00" if value.endswith("Z") else value)
    except ValueError:
        _diagnostic(
            diagnostics,
            "retrospective.invalid_created_at",
            f"{relative_path}:created_at",
            "created_at must be an ISO 8601 timestamp",
        )
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _infer_task_id(
    records: tuple[_Record, ...], requested_task_id: str | None, diagnostics: list[dict[str, str]]
) -> str | None:
    if requested_task_id is not None:
        return requested_task_id
    task_ids = sorted({cast(str, record.value["task_id"]) for record in records})
    if len(task_ids) == 1:
        return task_ids[0]
    if task_ids:
        _diagnostic(
            diagnostics,
            "retrospective.ambiguous_task_id",
            "records",
            "multiple task_ids remain; use --task-id to select one",
        )
    return None


def _verify_references(records: tuple[_Record, ...], diagnostics: list[dict[str, str]]) -> None:
    for record in records:
        for field in ("input_records", "artifacts"):
            entries = record.value.get(field)
            location = f"{record.relative_path}:{field}"
            if entries is None:
                continue
            if not isinstance(entries, dict):
                _diagnostic(
                    diagnostics,
                    "retrospective.invalid_reference_map",
                    location,
                    f"{field} must be a map",
                )
                continue
            references = cast(dict[object, object], entries)
            for name, entry in sorted(references.items(), key=lambda item: str(item[0])):
                _verify_reference(entry, f"{location}.{name}", diagnostics)


def _verify_reference(entry: object, location: str, diagnostics: list[dict[str, str]]) -> None:
    if not isinstance(entry, dict):
        _diagnostic(
            diagnostics, "retrospective.invalid_reference", location, "reference must be a map"
        )
        return
    reference = cast(JsonObject, entry)
    path_value, sha256 = reference.get("path"), reference.get("sha256")
    if not isinstance(path_value, str) or not isinstance(sha256, str):
        _diagnostic(
            diagnostics,
            "retrospective.invalid_reference",
            location,
            "reference must contain string path and sha256 values",
        )
        return
    if len(sha256) != 64 or any(character not in "0123456789abcdefABCDEF" for character in sha256):
        _diagnostic(
            diagnostics,
            "retrospective.invalid_sha256",
            location,
            "sha256 must be 64 hexadecimal characters",
        )
        return
    path = Path(path_value)
    if not path.exists():
        return
    if not path.is_file():
        _diagnostic(
            diagnostics,
            "retrospective.invalid_reference",
            location,
            "local reference path is not a file",
        )
        return
    try:
        actual = _sha256_file(path)
    except OSError as error:
        _diagnostic(
            diagnostics,
            "retrospective.unreadable_reference",
            location,
            f"unable to read local reference: {error}",
        )
    else:
        if actual.lower() != sha256.lower():
            _diagnostic(
                diagnostics,
                "retrospective.sha256_mismatch",
                location,
                "local reference sha256 does not match",
            )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _metrics(
    records: tuple[_Record, ...], task_id: str | None, diagnostics: list[dict[str, str]]
) -> JsonObject:
    kinds = Counter(cast(str, record.value["record_kind"]) for record in records)
    results = Counter(cast(str, record.value["result"]) for record in records)
    timestamps = sorted(
        (record.created_at, cast(str, record.value["created_at"]))
        for record in records
        if record.created_at is not None
    )
    first, last = (timestamps[0][1], timestamps[-1][1]) if timestamps else (None, None)
    duration: int | float | None = None
    if timestamps:
        seconds = (timestamps[-1][0] - timestamps[0][0]).total_seconds()
        duration = int(seconds) if seconds.is_integer() else seconds
    scope_statuses, budget_statuses, production_diff_lines, changed_paths = _audit_metrics(records)
    ci_records = tuple(record for record in records if _is_ci_record(record))
    return {
        "task_id": task_id,
        "diagnostics": diagnostics,
        "records": {
            "total": len(records),
            "by_kind": dict(sorted(kinds.items())),
            "by_result": dict(sorted(results.items())),
        },
        "timeline": {
            "first_created_at": first,
            "last_created_at": last,
            "duration_seconds": duration,
        },
        "events": {
            "candidate_attempts": sum(
                record.value["record_kind"] in {"candidate-start", "candidate-attempt"}
                for record in records
            ),
            "oracle_failures": sum(
                record.value["record_kind"] == "oracle-failure"
                or record.value["result"] == "oracle_failure_recorded"
                for record in records
            ),
            "oracle_repairs": sum(
                record.value["record_kind"] == "oracle-repair"
                or record.value["result"] == "oracle_repaired"
                for record in records
            ),
            "cleanup_complete": any(_cleanup_complete(record) for record in records),
        },
        "ci": {
            "total": len(ci_records),
            "success": sum(_ci_success(record) for record in ci_records),
        },
        "audits": {
            "scope_statuses": dict(sorted(scope_statuses.items())),
            "budget_statuses": dict(sorted(budget_statuses.items())),
            "production_diff_lines": production_diff_lines,
        },
        "checks": {"passed": sum(_passed_checks(record) for record in records)},
        "changed_paths": sorted(changed_paths),
    }


def _audit_metrics(
    records: tuple[_Record, ...],
) -> tuple[Counter[str], Counter[str], int | None, set[str]]:
    scope_statuses: Counter[str] = Counter()
    budget_statuses: Counter[str] = Counter()
    production_diff_lines: int | None = None
    changed_paths: set[str] = set()
    for record in records:
        _add_changed_paths(changed_paths, record.value.get("changed_paths"))
        audits = record.value.get("audits")
        if not isinstance(audits, dict):
            continue
        audit = cast(JsonObject, audits)
        scope, budget = audit.get("scope"), audit.get("budget")
        if isinstance(scope, dict):
            scope_map = cast(JsonObject, scope)
            _count_status(scope_statuses, scope_map.get("status"))
            _add_changed_paths(changed_paths, scope_map.get("changed_paths"))
        if isinstance(budget, dict):
            budget_map = cast(JsonObject, budget)
            _count_status(budget_statuses, budget_map.get("status"))
            totals = budget_map.get("totals")
            lines = (
                cast(JsonObject, totals).get("production_diff_lines")
                if isinstance(totals, dict)
                else None
            )
            if isinstance(lines, int) and not isinstance(lines, bool):
                production_diff_lines = lines
    return scope_statuses, budget_statuses, production_diff_lines, changed_paths


def _add_changed_paths(paths: set[str], value: object) -> None:
    if isinstance(value, list):
        for item in cast(list[object], value):
            path = (
                item
                if isinstance(item, str)
                else cast(JsonObject, item).get("path")
                if isinstance(item, dict)
                else None
            )
            if isinstance(path, str):
                paths.add(path)


def _count_status(statuses: Counter[str], value: object) -> None:
    if isinstance(value, str):
        statuses[value] += 1


def _is_ci_record(record: _Record) -> bool:
    return (
        isinstance(record.value.get("github_actions"), dict)
        or cast(str, record.value["record_kind"]).endswith("-ci")
        or cast(str, record.value["result"]).endswith("_ci_verified")
    )


def _ci_success(record: _Record) -> bool:
    github_actions = record.value.get("github_actions")
    return (
        isinstance(github_actions, dict)
        and cast(JsonObject, github_actions).get("conclusion") == "success"
    )


def _cleanup_complete(record: _Record) -> bool:
    return (
        record.value["record_kind"] == "cleanup" and record.value["result"] == "cleanup_complete"
    ) or (
        isinstance(record.value.get("final_state"), dict)
        and cast(JsonObject, record.value["final_state"]).get("worktree_clean") is True
    )


def _passed_checks(record: _Record) -> int:
    return sum(
        value == "passed"
        for field in ("local_checks", "retained_checks")
        if isinstance(checks := record.value.get(field), dict)
        for value in cast(dict[object, object], checks).values()
    )


def _markdown(payload: JsonObject) -> str:
    records, events, ci, timeline = (
        cast(JsonObject, payload[key]) for key in ("records", "events", "ci", "timeline")
    )
    diagnostics = cast(list[JsonObject], payload["diagnostics"])
    task_id = cast(str | None, payload["task_id"]) or "unknown"
    start, end, duration = (
        timeline["first_created_at"] or "unknown",
        timeline["last_created_at"] or "unknown",
        timeline["duration_seconds"],
    )
    lines = [
        f"# Retrospective: {task_id}",
        "",
        f"Records: {records['total']}",
        f"Timeline: {start} to {end} ({duration if duration is not None else 'unknown'} seconds)",
        f"Candidate attempts: {events['candidate_attempts']}",
        f"Oracle failures: {events['oracle_failures']}",
        f"Oracle repairs: {events['oracle_repairs']}",
        f"Cleanup complete: {events['cleanup_complete']}",
        f"CI success: {ci['success']}/{ci['total']}",
        f"Diagnostics: {len(diagnostics)}",
    ]
    if diagnostics:
        lines.extend(
            [
                "",
                "## Diagnostics",
                "",
                *(
                    f"- {item['code']}: {item['message']} ({item['location']})"
                    for item in diagnostics
                ),
            ]
        )
    return "\n".join(lines) + "\n"
