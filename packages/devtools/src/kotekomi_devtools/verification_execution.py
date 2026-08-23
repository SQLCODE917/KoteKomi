"""Deterministic verification execution records for planned checks."""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

type JsonObject = dict[str, Any]


class VerificationExecutionError(ValueError):
    """Raised when verification execution inputs are invalid."""


@dataclass(frozen=True)
class ExecutionDiagnostic:
    """One deterministic verification execution diagnostic."""

    code: str
    location: str
    rule: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "rule": self.rule}


@dataclass(frozen=True)
class CheckRunRecord:
    """One recorded check execution."""

    check_id: str
    argv: tuple[str, ...]
    exit_code: int
    status: str
    log_path: str
    log_sha256: str
    started_at: str
    ended_at: str
    duration_seconds: float

    @property
    def command(self) -> str:
        return shlex.join(self.argv)

    def as_json(self) -> JsonObject:
        return {
            "argv": list(self.argv),
            "check_id": self.check_id,
            "command": self.command,
            "duration_seconds": self.duration_seconds,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "log_path": self.log_path,
            "log_sha256": self.log_sha256,
            "schema_version": 1,
            "started_at": self.started_at,
            "status": self.status,
        }


@dataclass(frozen=True)
class PlannedCheck:
    """One check required by a verification plan."""

    id: str
    command: str


@dataclass(frozen=True)
class RunRecordSummary:
    """A loaded check run record summary."""

    path: str
    check_id: str
    command: str
    status: str
    exit_code: int

    def as_json(self) -> JsonObject:
        return {
            "check_id": self.check_id,
            "command": self.command,
            "exit_code": self.exit_code,
            "path": self.path,
            "status": self.status,
        }


@dataclass(frozen=True)
class VerificationExecutionReport:
    """The deterministic comparison between a plan and run records."""

    plan_path: str
    planned_checks: tuple[PlannedCheck, ...]
    records: tuple[RunRecordSummary, ...]
    diagnostics: tuple[ExecutionDiagnostic, ...]

    @property
    def ready(self) -> bool:
        return not self.diagnostics

    @property
    def exit_code(self) -> int:
        return 0 if self.ready else 1

    def as_json(self) -> JsonObject:
        return {
            "completed_check_ids": sorted(
                record.check_id
                for record in self.records
                if record.status == "passed" and record.exit_code == 0
            ),
            "diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics],
            "plan_path": self.plan_path,
            "planned_check_ids": [check.id for check in self.planned_checks],
            "records": [record.as_json() for record in self.records],
            "schema_version": 1,
            "status": "ready" if self.ready else "not_ready",
        }

    def markdown(self) -> str:
        lines = [
            "# Verification Execution",
            "",
            f"Status: {'ready' if self.ready else 'not_ready'}",
            f"Plan: `{self.plan_path}`",
            "",
            "## Planned checks",
            "",
        ]
        if self.planned_checks:
            for check in self.planned_checks:
                lines.append(f"- `{check.id}`: `{check.command}`")
        else:
            lines.append("- None.")

        lines.extend(["", "## Run records", ""])
        if self.records:
            for record in self.records:
                lines.extend(
                    [
                        f"- `{record.check_id}`",
                        f"  - Status: `{record.status}`",
                        f"  - Exit code: `{record.exit_code}`",
                        f"  - Command: `{record.command}`",
                        f"  - Record: `{record.path}`",
                    ]
                )
        else:
            lines.append("- None.")

        lines.extend(["", "## Diagnostics", ""])
        if self.diagnostics:
            for diagnostic in self.diagnostics:
                lines.append(f"- `{diagnostic.code}` at `{diagnostic.location}`: {diagnostic.rule}")
        else:
            lines.append("- None.")
        return "\n".join(lines) + "\n"


def run_check(
    check_id: str,
    *,
    output: Path,
    log: Path,
    argv: Sequence[str],
) -> CheckRunRecord:
    """Run one command argv, write a combined log, and write a stable JSON record."""
    command_argv = tuple(argv)
    if not check_id:
        raise VerificationExecutionError("run-check requires CHECK_ID")
    if not command_argv:
        raise VerificationExecutionError("run-check requires a command argv after --")

    started_at = _utc_timestamp()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command_argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log_bytes = completed.stdout
        exit_code = completed.returncode
    except OSError as error:
        log_bytes = f"ERROR: {error}\n".encode()
        exit_code = 127

    ended_at = _utc_timestamp()
    duration_seconds = round(time.monotonic() - started, 6)
    _write_bytes(log, log_bytes)
    record = CheckRunRecord(
        check_id=check_id,
        argv=command_argv,
        exit_code=exit_code,
        status="passed" if exit_code == 0 else "failed",
        log_path=str(log),
        log_sha256=hashlib.sha256(log_bytes).hexdigest(),
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
    )
    _write_json(output, record.as_json())
    return record


def verify_check_records(
    plan_path: Path,
    *,
    run_records: Sequence[Path],
    output: Path,
    markdown: Path,
) -> VerificationExecutionReport:
    """Verify that all planned checks have matching successful run records."""
    diagnostics: list[ExecutionDiagnostic] = []
    plan_payload = _load_json(
        plan_path, "/plan", "verification_execution.plan_invalid", diagnostics
    )
    planned = _planned_checks(plan_payload, diagnostics) if plan_payload is not None else ()
    records = _run_records(run_records, diagnostics)

    planned_by_id = {check.id: check for check in planned}
    records_by_id: dict[str, list[RunRecordSummary]] = {}
    for record in records:
        records_by_id.setdefault(record.check_id, []).append(record)

    for check in planned:
        matches = records_by_id.get(check.id, [])
        if not matches:
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.check_missing",
                    f"/checks/{check.id}",
                    "planned_check_requires_successful_run_record",
                )
            )
            continue
        if len(matches) > 1:
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.check_duplicate",
                    f"/run_records/{check.id}",
                    "planned_check_must_have_exactly_one_run_record",
                )
            )
            continue

        record = matches[0]
        if record.status != "passed" or record.exit_code != 0:
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.check_failed",
                    f"/run_records/{record.check_id}",
                    "planned_check_run_record_must_pass",
                )
            )
        if record.command != check.command:
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.command_mismatch",
                    f"/run_records/{record.check_id}/command",
                    "run_record_command_must_match_plan_command",
                )
            )

    for record in records:
        if record.check_id not in planned_by_id:
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.extra_record",
                    f"/run_records/{record.check_id}",
                    "extra_run_record_does_not_satisfy_a_planned_check",
                )
            )

    report = VerificationExecutionReport(
        plan_path=str(plan_path),
        planned_checks=planned,
        records=records,
        diagnostics=tuple(diagnostics),
    )
    _write_json(output, report.as_json())
    _write_text(markdown, report.markdown())
    return report


def _planned_checks(
    payload: Mapping[str, Any],
    diagnostics: list[ExecutionDiagnostic],
) -> tuple[PlannedCheck, ...]:
    raw_checks = payload.get("checks")
    if not isinstance(raw_checks, list):
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.plan_invalid",
                "/plan/checks",
                "verification_plan_requires_checks_array",
            )
        )
        return ()

    planned: list[PlannedCheck] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(cast(list[object], raw_checks)):
        location = f"/plan/checks/{index}"
        if not isinstance(raw_item, Mapping):
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.plan_invalid",
                    location,
                    "verification_plan_check_must_be_object",
                )
            )
            continue
        check = cast(Mapping[str, Any], raw_item)
        check_id = check.get("id")
        command = check.get("command")
        if not isinstance(check_id, str) or not isinstance(command, str):
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.plan_invalid",
                    location,
                    "verification_plan_check_requires_id_and_command",
                )
            )
            continue
        if check_id in seen:
            diagnostics.append(
                ExecutionDiagnostic(
                    "verification_execution.plan_invalid",
                    location,
                    "verification_plan_check_ids_must_be_unique",
                )
            )
            continue
        seen.add(check_id)
        planned.append(PlannedCheck(check_id, command))
    return tuple(planned)


def _run_records(
    paths: Sequence[Path],
    diagnostics: list[ExecutionDiagnostic],
) -> tuple[RunRecordSummary, ...]:
    records: list[RunRecordSummary] = []
    for index, path in enumerate(paths):
        payload = _load_json(
            path,
            f"/run_records/{index}",
            "verification_execution.record_invalid",
            diagnostics,
        )
        if payload is None:
            continue
        record = _run_record(path, payload, index, diagnostics)
        if record is not None:
            records.append(record)
    return tuple(records)


def _run_record(
    path: Path,
    payload: Mapping[str, Any],
    index: int,
    diagnostics: list[ExecutionDiagnostic],
) -> RunRecordSummary | None:
    check_id = payload.get("check_id")
    command = payload.get("command")
    status = payload.get("status")
    exit_code = payload.get("exit_code")
    log_path = payload.get("log_path")
    log_sha256 = payload.get("log_sha256")
    raw_argv = payload.get("argv")

    if isinstance(raw_argv, list):
        argv_items = cast(list[object], raw_argv)
    else:
        argv_items = None

    argv_strings: list[str] = []
    if argv_items is not None:
        for raw_item in argv_items:
            if isinstance(raw_item, str):
                argv_strings.append(raw_item)

    if (
        not isinstance(check_id, str)
        or not isinstance(command, str)
        or not isinstance(status, str)
        or not isinstance(exit_code, int)
        or argv_items is None
        or len(argv_strings) != len(argv_items)
    ):
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.record_invalid",
                f"/run_records/{index}",
                "run_record_requires_check_id_argv_command_status_and_exit_code",
            )
        )
        return None

    if command != shlex.join(argv_strings):
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.record_invalid",
                f"/run_records/{index}/command",
                "run_record_command_must_match_argv",
            )
        )
        return None

    if not isinstance(log_path, str) or not isinstance(log_sha256, str):
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.run_record_invalid",
                f"/run_records/{index}",
                "run_record_requires_log_path_and_log_sha256",
            )
        )
        return None
    if not _run_record_log_is_valid(path, log_path, log_sha256, index, diagnostics):
        return None
    return RunRecordSummary(
        path=str(path),
        check_id=check_id,
        command=command,
        status=status,
        exit_code=exit_code,
    )


def _run_record_log_is_valid(
    record_path: Path,
    log_path: str,
    log_sha256: str,
    index: int,
    diagnostics: list[ExecutionDiagnostic],
) -> bool:
    if len(log_sha256) != 64:
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.log_digest_invalid",
                f"/run_records/{index}/log_sha256",
                "run_record_log_sha256_must_be_64_hex_characters",
            )
        )
        return False
    try:
        int(log_sha256, 16)
    except ValueError:
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.log_digest_invalid",
                f"/run_records/{index}/log_sha256",
                "run_record_log_sha256_must_be_64_hex_characters",
            )
        )
        return False

    resolved_log = Path(log_path)
    if not resolved_log.is_absolute():
        resolved_log = record_path.parent / resolved_log

    try:
        log_bytes = resolved_log.read_bytes()
    except OSError:
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.log_missing",
                f"/run_records/{index}/log_path",
                "run_record_log_path_must_exist",
            )
        )
        return False

    actual_sha256 = hashlib.sha256(log_bytes).hexdigest()
    if actual_sha256 != log_sha256:
        diagnostics.append(
            ExecutionDiagnostic(
                "verification_execution.log_digest_mismatch",
                f"/run_records/{index}/log_sha256",
                "run_record_log_sha256_must_match_log_bytes",
            )
        )
        return False

    return True


def _load_json(
    path: Path,
    location: str,
    code: str,
    diagnostics: list[ExecutionDiagnostic],
) -> JsonObject | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        diagnostics.append(ExecutionDiagnostic(code, location, "json_file_must_be_readable"))
        return None
    if not isinstance(loaded, dict):
        diagnostics.append(ExecutionDiagnostic(code, location, "json_file_must_be_an_object"))
        return None
    return cast(JsonObject, loaded)


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: JsonObject) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
