from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

from kotekomi_devtools.verification_execution import verify_check_records


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    stable_payload = dict(payload)
    if {
        "argv",
        "check_id",
        "command",
        "exit_code",
        "log_path",
        "log_sha256",
        "status",
    }.issubset(stable_payload):
        log_path = path.with_suffix(".log")
        log_path.write_text("ok\n", encoding="utf-8")
        stable_payload["log_path"] = str(log_path)
        stable_payload["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
    path.write_text(
        json.dumps(stable_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _plan(path: Path, check_id: str, argv: list[str]) -> None:
    _write_json(
        path,
        {
            "status": "ready",
            "schema_version": 1,
            "task_id": "unit",
            "base_revision": "base",
            "head_revision": "head",
            "changed_paths": [],
            "checks": [
                {
                    "id": check_id,
                    "command": shlex.join(argv),
                    "reason": "unit fixture",
                    "source": "manifest",
                }
            ],
            "diagnostics": [],
        },
    )


def _record(
    path: Path,
    check_id: str,
    argv: list[str],
    *,
    status: str = "passed",
    exit_code: int = 0,
) -> None:
    _write_json(
        path,
        {
            "schema_version": 1,
            "check_id": check_id,
            "argv": argv,
            "command": shlex.join(argv),
            "status": status,
            "exit_code": exit_code,
            "log_path": "check.log",
            "log_sha256": "0" * 64,
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:00:01Z",
            "duration_seconds": 1.0,
        },
    )


def _codes(output: Path) -> set[str]:
    payload = json.loads(output.read_text(encoding="utf-8"))
    return {item["code"] for item in payload["diagnostics"]}


def test_verify_check_records_ready_for_matching_record(tmp_path: Path) -> None:
    argv = ["uv", "run", "python", "--version"]
    plan = tmp_path / "plan.json"
    record = tmp_path / "record.json"
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"
    _plan(plan, "planned", argv)
    _record(record, "planned", argv)

    report = verify_check_records(plan, run_records=[record], output=output, markdown=markdown)

    assert report.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["diagnostics"] == []


def test_verify_check_records_reports_missing_check(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"
    _plan(plan, "planned", ["uv", "run", "python", "--version"])

    report = verify_check_records(plan, run_records=[], output=output, markdown=markdown)

    assert report.exit_code == 1
    assert _codes(output) == {"verification_execution.check_missing"}


def test_verify_check_records_reports_command_mismatch(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    record = tmp_path / "record.json"
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"
    _plan(plan, "planned", ["uv", "run", "python", "--version"])
    _record(record, "planned", ["uv", "run", "python", "-V"])

    report = verify_check_records(plan, run_records=[record], output=output, markdown=markdown)

    assert report.exit_code == 1
    assert _codes(output) == {"verification_execution.command_mismatch"}


def _log_integrity_record(path: Path, check_id: str, argv: list[str]) -> None:
    log_path = path.with_suffix(".log")
    log_path.write_text("ok\n", encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "argv": argv,
                "check_id": check_id,
                "command": shlex.join(argv),
                "duration_seconds": 0.001,
                "ended_at": "2026-01-01T00:00:01Z",
                "exit_code": 0,
                "log_path": str(log_path),
                "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
                "schema_version": 1,
                "started_at": "2026-01-01T00:00:00Z",
                "status": "passed",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_verify_check_records_reports_missing_log(tmp_path: Path) -> None:
    argv = ["uv", "run", "python", "-c", "print('ok')"]
    plan = tmp_path / "plan.json"
    record = tmp_path / "record.json"
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"
    _plan(plan, "sample-missing-log", argv)
    _log_integrity_record(record, "sample-missing-log", argv)
    payload = json.loads(record.read_text(encoding="utf-8"))
    payload["log_path"] = str(tmp_path / "missing.log")
    record.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = verify_check_records(plan, run_records=[record], output=output, markdown=markdown)

    assert report.exit_code == 1
    assert "verification_execution.log_missing" in _codes(output)


def test_verify_check_records_reports_log_digest_mismatch(tmp_path: Path) -> None:
    argv = ["uv", "run", "python", "-c", "print('ok')"]
    plan = tmp_path / "plan.json"
    record = tmp_path / "record.json"
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"
    _plan(plan, "sample-bad-log-digest", argv)
    _log_integrity_record(record, "sample-bad-log-digest", argv)
    payload = json.loads(record.read_text(encoding="utf-8"))
    payload["log_sha256"] = "0" * 64
    record.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = verify_check_records(plan, run_records=[record], output=output, markdown=markdown)

    assert report.exit_code == 1
    assert "verification_execution.log_digest_mismatch" in _codes(output)
