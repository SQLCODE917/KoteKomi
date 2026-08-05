from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from . import _oracle_fixtures as oracle

REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST = REPO_ROOT / ".agent/tasks/harness-06-task-lifecycle-state-machine.toml"

H5_MAIN_MERGE = "37e6b8c886fdb39288f1c88bc26ede7bbf704b50"
H5_MAIN_PARENT = "63fa7cae7c4a5f03619ceeec953aee7fbf7eea53"
H5_VERIFIED = "17bb8e2b77ab2b5edaf5a540fc6ac28c855dcfed"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _json_result(args: list[str]) -> tuple[int, dict[str, Any]]:
    result = _run(args)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"stdout was not JSON.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ) from exc

    return result.returncode, payload


def _require_lifecycle_check() -> None:
    result = _run(["uv", "run", "kotekomi-agent", "--help"])
    if "lifecycle-check" not in result.stdout:
        pytest.skip("lifecycle-check is not implemented yet")


def _assert_common_payload(payload: dict[str, Any], phase: str) -> None:
    assert payload["schema_version"] == 1
    assert payload["task_id"] == "harness-06-task-lifecycle-state-machine"
    assert payload["phase"] == phase
    assert payload["status"] in {"ready", "not_ready", "invalid"}
    assert isinstance(payload["diagnostics"], list)
    assert isinstance(payload["required_checks"], list)
    assert isinstance(payload["observed_records"], list)


def _diagnostic_codes(payload: dict[str, Any]) -> set[str]:
    return {item["code"] for item in payload["diagnostics"]}


def test_lifecycle_check_help_lists_phase_values() -> None:
    _require_lifecycle_check()

    result = _run(["uv", "run", "kotekomi-agent", "lifecycle-check", "--help"])

    assert result.returncode == 0
    assert "--phase" in result.stdout
    assert "spec" in result.stdout
    assert "candidate" in result.stdout
    assert "verified" in result.stdout
    assert "main" in result.stdout


def test_spec_phase_reports_head_not_execution_base_after_head_moves() -> None:
    _require_lifecycle_check()

    code, payload = _json_result(
        [
            "uv",
            "run",
            "kotekomi-agent",
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "spec",
        ]
    )

    _assert_common_payload(payload, "spec")
    assert code != 0
    assert payload["status"] == "not_ready"
    assert "validate-task" in payload["required_checks"]
    assert "preflight-task" in payload["required_checks"]
    assert "task_lifecycle.head_not_execution_base" in _diagnostic_codes(payload)


def test_candidate_phase_requires_revision_range() -> None:
    _require_lifecycle_check()

    code, payload = _json_result(
        [
            "uv",
            "run",
            "kotekomi-agent",
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "candidate",
        ]
    )

    _assert_common_payload(payload, "candidate")
    assert code != 0
    assert payload["status"] == "invalid"
    assert "task_lifecycle.missing_revision_range" in _diagnostic_codes(payload)


def test_candidate_phase_accepts_clean_revision_range() -> None:
    _require_lifecycle_check()

    head = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    base = _run(["git", "rev-parse", "HEAD^"]).stdout.strip()

    code, payload = _json_result(
        [
            "uv",
            "run",
            "kotekomi-agent",
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "candidate",
            "--base",
            base,
            "--head",
            head,
        ]
    )

    _assert_common_payload(payload, "candidate")
    assert code == 0
    assert payload["status"] == "ready"
    assert "scope-audit" in payload["required_checks"]
    assert "budget-audit" in payload["required_checks"]
    assert "protected-artifacts" in payload["required_checks"]


def test_verified_phase_reports_missing_candidate_records(tmp_path: Path) -> None:
    _require_lifecycle_check()

    records_dir = tmp_path / "records"
    records_dir.mkdir()

    code, payload = _json_result(
        [
            "uv",
            "run",
            "kotekomi-agent",
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "verified",
            "--records-dir",
            str(records_dir),
        ]
    )

    _assert_common_payload(payload, "verified")
    assert code != 0
    assert payload["status"] == "not_ready"
    assert "candidate-commit-record" in payload["required_checks"]
    assert "candidate-ci-record" in payload["required_checks"]
    assert "task_lifecycle.record_missing" in _diagnostic_codes(payload)


def test_verified_phase_accepts_present_candidate_records(tmp_path: Path) -> None:
    _require_lifecycle_check()

    records_dir = tmp_path / "records"
    oracle.write_fixture_text(
        records_dir / "candidate-commit.json",
        json.dumps({"schema_version": 1, "record_kind": "candidate-commit"}) + "\n",
    )
    oracle.write_fixture_text(
        records_dir / "candidate-ci.json",
        json.dumps({"schema_version": 1, "record_kind": "candidate-ci"}) + "\n",
    )

    code, payload = _json_result(
        [
            "uv",
            "run",
            "kotekomi-agent",
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "verified",
            "--records-dir",
            str(records_dir),
        ]
    )

    _assert_common_payload(payload, "verified")
    assert code == 0
    assert payload["status"] == "ready"
    assert {item["name"] for item in payload["observed_records"]} == {
        "candidate-commit.json",
        "candidate-ci.json",
    }


def test_main_phase_verifies_merge_parents() -> None:
    _require_lifecycle_check()

    code, payload = _json_result(
        [
            "uv",
            "run",
            "kotekomi-agent",
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "main",
            "--main-base",
            H5_MAIN_PARENT,
            "--verified",
            H5_VERIFIED,
            "--head",
            H5_MAIN_MERGE,
        ]
    )

    _assert_common_payload(payload, "main")
    assert code == 0
    assert payload["status"] == "ready"
    assert "merge-parents" in payload["required_checks"]
    assert "main-ci-record" in payload["required_checks"]
