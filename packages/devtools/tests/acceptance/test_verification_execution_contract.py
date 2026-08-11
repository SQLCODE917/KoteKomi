from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _run_cli(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(PROJECT_ROOT), "kotekomi-agent", *args],
        cwd=cwd or PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _require_execution_commands() -> None:
    missing: list[str] = []
    for command in ("run-check", "verify-checks"):
        result = _run_cli([command, "--help"])
        combined = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or command not in combined:
            missing.append(command)
    if missing:
        missing_text = ", ".join(missing)
        pytest.skip(
            f"verification execution commands are not implemented yet: {missing_text}"
        )


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


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


def _plan(path: Path, checks: list[dict[str, Any]]) -> None:
    _write_json(
        path,
        {
            "status": "ready",
            "schema_version": 1,
            "task_id": "harness-10-verification-execution-accountability",
            "base_revision": "base",
            "head_revision": "head",
            "changed_paths": [],
            "checks": checks,
            "diagnostics": [],
        },
    )


def _check(
    check_id: str,
    argv: list[str],
    *,
    status: str = "passed",
    exit_code: int = 0,
) -> dict[str, Any]:
    return {
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
    }


def _run_check(
    check_id: str,
    output: Path,
    log: Path,
    argv: list[str],
) -> subprocess.CompletedProcess[str]:
    return _run_cli(
        [
            "run-check",
            check_id,
            "--output",
            str(output),
            "--log",
            str(log),
            "--",
            *argv,
        ]
    )


def _verify(
    plan: Path,
    records: list[Path],
    output: Path,
    markdown: Path,
) -> subprocess.CompletedProcess[str]:
    args = ["verify-checks", str(plan)]
    for record in records:
        args.extend(["--run-record", str(record)])
    args.extend(["--output", str(output), "--markdown", str(markdown)])
    return _run_cli(args)


def test_verification_execution_help_lists_core_options() -> None:
    _require_execution_commands()

    run_help = _run_cli(["run-check", "--help"])
    verify_help = _run_cli(["verify-checks", "--help"])

    assert run_help.returncode == 0
    assert "CHECK_ID" in run_help.stdout
    assert "--output" in run_help.stdout
    assert "--log" in run_help.stdout
    assert verify_help.returncode == 0
    assert "PLAN_JSON" in verify_help.stdout
    assert "--run-record" in verify_help.stdout
    assert "--markdown" in verify_help.stdout


def test_run_check_records_successful_command(tmp_path: Path) -> None:
    _require_execution_commands()

    output = tmp_path / "record.json"
    log = tmp_path / "record.log"
    argv = ["uv", "run", "--project", str(PROJECT_ROOT), "python", "-c", "print('ok')"]

    result = _run_check("sample-success", output, log, argv)

    assert result.returncode == 0
    assert output.exists()
    assert log.exists()
    record = _json(output)
    assert record["schema_version"] == 1
    assert record["check_id"] == "sample-success"
    assert record["argv"] == argv
    assert record["status"] == "passed"
    assert record["exit_code"] == 0
    log_sha = record["log_sha256"]
    assert isinstance(log_sha, str)
    assert len(log_sha) == 64
    assert "ok" in log.read_text(encoding="utf-8")


def test_run_check_records_failing_command_and_returns_failure(tmp_path: Path) -> None:
    _require_execution_commands()

    output = tmp_path / "record.json"
    log = tmp_path / "record.log"
    argv = [
        "uv",
        "run",
        "--project",
        str(PROJECT_ROOT),
        "python",
        "-c",
        "import sys; sys.exit(7)",
    ]

    result = _run_check("sample-failure", output, log, argv)

    assert result.returncode == 7
    assert output.exists()
    record = _json(output)
    assert record["check_id"] == "sample-failure"
    assert record["argv"] == argv
    assert record["status"] == "failed"
    assert record["exit_code"] == 7


def test_verify_checks_accepts_complete_successful_records(tmp_path: Path) -> None:
    _require_execution_commands()

    argv = ["uv", "run", "--project", str(PROJECT_ROOT), "python", "-c", "print('ok')"]
    plan = tmp_path / "plan.json"
    record = tmp_path / "record.json"
    log = tmp_path / "record.log"
    output = tmp_path / "verify.json"
    markdown = tmp_path / "verify.md"

    _plan(
        plan,
        [
            {
                "id": "sample-success",
                "command": shlex.join(argv),
                "reason": "test fixture",
                "source": "manifest",
            }
        ],
    )
    run_result = _run_check("sample-success", record, log, argv)
    assert run_result.returncode == 0

    result = _verify(plan, [record], output, markdown)

    assert result.returncode == 0
    payload = _json(output)
    assert payload["status"] == "ready"
    assert payload["diagnostics"] == []
    assert "sample-success" in markdown.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("case_name", "records", "expected_code"),
    [
        ("missing", [], "verification_execution.check_missing"),
        (
            "failed",
            [
                _check(
                    "planned",
                    ["uv", "run", "python", "--version"],
                    status="failed",
                    exit_code=1,
                )
            ],
            "verification_execution.check_failed",
        ),
        (
            "duplicate",
            [
                _check("planned", ["uv", "run", "python", "--version"]),
                _check("planned", ["uv", "run", "python", "--version"]),
            ],
            "verification_execution.check_duplicate",
        ),
        (
            "command-mismatch",
            [_check("planned", ["uv", "run", "python", "-V"])],
            "verification_execution.command_mismatch",
        ),
    ],
)
def test_verify_checks_fails_closed_for_invalid_completion(
    tmp_path: Path,
    case_name: str,
    records: list[dict[str, Any]],
    expected_code: str,
) -> None:
    _require_execution_commands()

    plan = tmp_path / f"{case_name}-plan.json"
    output = tmp_path / f"{case_name}-verify.json"
    markdown = tmp_path / f"{case_name}-verify.md"
    expected_argv = ["uv", "run", "python", "--version"]
    _plan(
        plan,
        [
            {
                "id": "planned",
                "command": shlex.join(expected_argv),
                "reason": "test fixture",
                "source": "manifest",
            }
        ],
    )

    record_paths: list[Path] = []
    for index, record_payload in enumerate(records):
        record_path = tmp_path / f"{case_name}-{index}.json"
        _write_json(record_path, record_payload)
        record_paths.append(record_path)

    result = _verify(plan, record_paths, output, markdown)

    assert result.returncode == 1
    payload = _json(output)
    assert payload["status"] == "not_ready"
    diagnostics = cast(list[dict[str, Any]], payload["diagnostics"])
    assert expected_code in {cast(str, diagnostic["code"]) for diagnostic in diagnostics}
    assert expected_code in markdown.read_text(encoding="utf-8")


def test_verify_checks_fails_closed_for_malformed_record(tmp_path: Path) -> None:
    _require_execution_commands()

    plan = tmp_path / "plan.json"
    record = tmp_path / "malformed.json"
    output = tmp_path / "verify.json"
    markdown = tmp_path / "verify.md"
    argv = ["uv", "run", "python", "--version"]
    _plan(
        plan,
        [
            {
                "id": "planned",
                "command": shlex.join(argv),
                "reason": "test fixture",
                "source": "manifest",
            }
        ],
    )
    record.write_text("{not json\n", encoding="utf-8")

    result = _verify(plan, [record], output, markdown)

    assert result.returncode == 1
    payload = _json(output)
    diagnostics = cast(list[dict[str, Any]], payload["diagnostics"])
    assert "verification_execution.record_invalid" in {
        cast(str, diagnostic["code"]) for diagnostic in diagnostics
    }


def test_verify_checks_reports_extra_records_without_satisfying_plan(tmp_path: Path) -> None:
    _require_execution_commands()

    plan = tmp_path / "plan.json"
    extra = tmp_path / "extra.json"
    output = tmp_path / "verify.json"
    markdown = tmp_path / "verify.md"
    planned_argv = ["uv", "run", "python", "--version"]
    _plan(
        plan,
        [
            {
                "id": "planned",
                "command": shlex.join(planned_argv),
                "reason": "test fixture",
                "source": "manifest",
            }
        ],
    )
    _write_json(extra, _check("extra", planned_argv))

    result = _verify(plan, [extra], output, markdown)

    assert result.returncode == 1
    payload = _json(output)
    diagnostics = cast(list[dict[str, Any]], payload["diagnostics"])
    codes = {cast(str, diagnostic["code"]) for diagnostic in diagnostics}
    assert "verification_execution.check_missing" in codes
    assert "verification_execution.extra_record" in codes
    assert "verification_execution.extra_record" in markdown.read_text(encoding="utf-8")

def test_verify_checks_rejects_missing_run_log(tmp_path: Path) -> None:
    _require_execution_commands()

    argv = ["uv", "run", "--project", str(PROJECT_ROOT), "python", "-c", "print('ok')"]
    plan = tmp_path / "plan.json"
    record = tmp_path / "record.json"
    log = tmp_path / "record.log"
    output = tmp_path / "verify.json"
    markdown = tmp_path / "verify.md"
    _plan(
        plan,
        [
            {
                "id": "sample-missing-log",
                "command": shlex.join(argv),
                "reason": "test fixture",
                "source": "manifest",
            }
        ],
    )
    run_result = _run_check("sample-missing-log", record, log, argv)
    assert run_result.returncode == 0
    payload = _json(record)
    payload["log_path"] = str(tmp_path / "missing.log")
    record.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = _verify(plan, [record], output, markdown)

    assert result.returncode == 1
    report = _json(output)
    assert report["status"] == "not_ready"
    codes = {item["code"] for item in report["diagnostics"]}
    assert "verification_execution.log_missing" in codes


def test_verify_checks_rejects_run_log_digest_mismatch(tmp_path: Path) -> None:
    _require_execution_commands()

    argv = ["uv", "run", "--project", str(PROJECT_ROOT), "python", "-c", "print('ok')"]
    plan = tmp_path / "plan.json"
    record = tmp_path / "record.json"
    log = tmp_path / "record.log"
    output = tmp_path / "verify.json"
    markdown = tmp_path / "verify.md"
    _plan(
        plan,
        [
            {
                "id": "sample-bad-log-digest",
                "command": shlex.join(argv),
                "reason": "test fixture",
                "source": "manifest",
            }
        ],
    )
    run_result = _run_check("sample-bad-log-digest", record, log, argv)
    assert run_result.returncode == 0
    payload = _json(record)
    payload["log_sha256"] = "0" * 64
    record.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = _verify(plan, [record], output, markdown)

    assert result.returncode == 1
    report = _json(output)
    assert report["status"] == "not_ready"
    codes = {item["code"] for item in report["diagnostics"]}
    assert "verification_execution.log_digest_mismatch" in codes
