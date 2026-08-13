from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast


def _write_receipt(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_status(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "kotekomi-agent", "receipt-chain-status", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_receipt_chain_status_cli_reports_complete_chain(tmp_path: Path) -> None:
    receipt = tmp_path / "spec-commit.json"
    digest = _write_receipt(receipt, {"result": "spec_ready"})
    output = tmp_path / "status.json"
    markdown = tmp_path / "status.md"

    result = _run_status(
        "--task-id", "h15-fixture", "--phase", "spec",
        "--receipt", f"spec-commit={receipt}", "--expect", f"spec-commit={digest}",
        "--required", "spec-commit", "--output", str(output), "--markdown", str(markdown),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["task_id"] == "h15-fixture"
    assert payload["phase"] == "spec"
    assert payload["status"] == "ready"
    assert payload["diagnostics"] == []
    assert "spec-commit" in markdown.read_text(encoding="utf-8")


def test_receipt_chain_status_cli_fails_closed_for_missing_default(tmp_path: Path) -> None:
    output = tmp_path / "missing.json"

    result = _run_status(
        "--task-id", "h15-fixture", "--phase", "spec",
        "--state-root", str(tmp_path / "state"), "--required", "spec-ci",
        "--output", str(output),
    )

    assert result.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert payload["missing_required_records"] == ["spec-ci"]
    diagnostics_value = payload["diagnostics"]
    assert isinstance(diagnostics_value, list)
    diagnostics = cast(list[dict[str, object]], diagnostics_value)
    assert diagnostics[0]["code"] == "receipt_chain_status.missing_receipt"


def test_receipt_chain_status_cli_fails_closed_for_digest_mismatch(tmp_path: Path) -> None:
    receipt = tmp_path / "candidate-ci.json"
    _write_receipt(receipt, {"result": "candidate_ci_success"})
    output = tmp_path / "mismatch.json"

    result = _run_status(
        "--task-id", "h15-fixture", "--phase", "candidate",
        "--receipt", f"candidate-ci={receipt}", "--expect", f"candidate-ci={'0' * 64}",
        "--required", "candidate-ci", "--output", str(output),
    )

    assert result.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    diagnostics_value = payload["diagnostics"]
    assert isinstance(diagnostics_value, list)
    diagnostics = cast(list[dict[str, object]], diagnostics_value)
    assert diagnostics[0]["code"] == "receipt_chain_status.digest_mismatch"
