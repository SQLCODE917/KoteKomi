from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]


def _run_cli(args: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(REPO_ROOT), "kotekomi-agent", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _json_result(args: list[str], cwd: Path = REPO_ROOT) -> tuple[int, dict[str, Any]]:
    result = _run_cli(args, cwd=cwd)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - assertion aid
        raise AssertionError(
            f"stdout was not JSON\nstdout={result.stdout}\nstderr={result.stderr}"
        ) from exc

    assert isinstance(payload, dict)
    return result.returncode, cast(dict[str, Any], payload)


def _require_write_receipt() -> None:
    result = _run_cli(["--help"])
    if "write-receipt" not in result.stdout:
        pytest.skip("write-receipt is not implemented yet")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _load_receipt(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _write_minimal(output: Path, *, force: bool = False) -> tuple[int, dict[str, Any]]:
    args = [
        "write-receipt",
        "--task-id",
        "harness-07-task-receipt-writer",
        "--record-kind",
        "candidate-commit",
        "--result",
        "candidate_committed",
        "--output",
        str(output),
    ]
    if force:
        args.append("--force")
    return _json_result(args)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Receipt Writer Test")
    _git(repo, "config", "user.email", "receipt-writer@example.invalid")

    _write_text(repo / "tracked.txt", "clean\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")

    return repo


def test_write_receipt_help_lists_core_options() -> None:
    _require_write_receipt()

    result = _run_cli(["write-receipt", "--help"])

    assert result.returncode == 0
    assert "--task-id" in result.stdout
    assert "--record-kind" in result.stdout
    assert "--result" in result.stdout
    assert "--output" in result.stdout
    assert "--input-record" in result.stdout
    assert "--artifact" in result.stdout
    assert "--field" in result.stdout
    assert "--force" in result.stdout


def test_write_receipt_writes_canonical_minimal_receipt(tmp_path: Path) -> None:
    _require_write_receipt()

    output = tmp_path / "receipts" / "candidate-commit.json"

    code, result = _write_minimal(output)

    assert code == 0
    assert Path(cast(str, result["receipt_path"])).resolve() == output.resolve()
    assert result["receipt_sha256"] == _sha256(output)

    raw = output.read_text(encoding="utf-8")
    receipt = _load_receipt(output)

    assert raw == json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    assert receipt["schema_version"] == 1
    assert receipt["task_id"] == "harness-07-task-receipt-writer"
    assert receipt["record_kind"] == "candidate-commit"
    assert receipt["result"] == "candidate_committed"
    assert isinstance(receipt["created_at"], str)
    assert receipt["input_records"] == {}
    assert receipt["artifacts"] == {}
    assert receipt["fields"] == {}

    git_state = cast(dict[str, Any], receipt["git"])
    assert isinstance(git_state["branch"], str)
    assert isinstance(git_state["head"], str)
    assert isinstance(git_state["parents"], list)
    assert isinstance(git_state["worktree_clean"], bool)


def test_write_receipt_refuses_overwrite_without_force(tmp_path: Path) -> None:
    _require_write_receipt()

    output = tmp_path / "receipt.json"
    first_code, first_result = _write_minimal(output)

    assert first_code == 0
    before = output.read_bytes()

    second = _run_cli(
        [
            "write-receipt",
            "--task-id",
            "harness-07-task-receipt-writer",
            "--record-kind",
            "candidate-commit",
            "--result",
            "candidate_committed",
            "--output",
            str(output),
        ]
    )

    assert second.returncode != 0
    assert output.read_bytes() == before
    assert first_result["receipt_sha256"] == _sha256(output)


def test_write_receipt_force_allows_overwrite(tmp_path: Path) -> None:
    _require_write_receipt()

    output = tmp_path / "receipt.json"
    first_code, first_result = _write_minimal(output)

    assert first_code == 0

    second_code, second_result = _json_result(
        [
            "write-receipt",
            "--task-id",
            "harness-07-task-receipt-writer",
            "--record-kind",
            "candidate-ci",
            "--result",
            "candidate_ci_verified",
            "--output",
            str(output),
            "--field",
            "run_id=123",
            "--force",
        ]
    )

    assert second_code == 0
    assert second_result["receipt_sha256"] == _sha256(output)
    assert second_result["receipt_sha256"] != first_result["receipt_sha256"]

    receipt = _load_receipt(output)
    assert receipt["record_kind"] == "candidate-ci"
    assert receipt["result"] == "candidate_ci_verified"
    assert receipt["fields"] == {"run_id": "123"}


def test_write_receipt_records_input_records_and_artifacts(tmp_path: Path) -> None:
    _require_write_receipt()

    input_record = tmp_path / "candidate-ci.json"
    artifact = tmp_path / "manifest.toml"
    output = tmp_path / "receipt.json"

    _write_text(input_record, '{"result":"candidate_ci_verified"}\n')
    _write_text(artifact, 'task_id = "harness-07-task-receipt-writer"\n')

    code, result = _json_result(
        [
            "write-receipt",
            "--task-id",
            "harness-07-task-receipt-writer",
            "--record-kind",
            "candidate-verified",
            "--result",
            "candidate_verified",
            "--output",
            str(output),
            "--input-record",
            f"candidate-ci={input_record}",
            "--artifact",
            f"manifest={artifact}",
            "--field",
            "verified_commit=abc123",
        ]
    )

    assert code == 0
    assert result["receipt_sha256"] == _sha256(output)

    receipt = _load_receipt(output)
    assert receipt["input_records"] == {
        "candidate-ci": {"path": str(input_record), "sha256": _sha256(input_record)}
    }
    assert receipt["artifacts"] == {
        "manifest": {"path": str(artifact), "sha256": _sha256(artifact)}
    }
    assert receipt["fields"] == {"verified_commit": "abc123"}


def test_write_receipt_rejects_missing_input_record_and_artifact(tmp_path: Path) -> None:
    _require_write_receipt()

    output = tmp_path / "receipt.json"

    missing_input = _run_cli(
        [
            "write-receipt",
            "--task-id",
            "harness-07-task-receipt-writer",
            "--record-kind",
            "candidate-verified",
            "--result",
            "candidate_verified",
            "--output",
            str(output),
            "--input-record",
            f"missing={tmp_path / 'missing.json'}",
        ]
    )

    assert missing_input.returncode != 0
    assert not output.exists()

    missing_artifact = _run_cli(
        [
            "write-receipt",
            "--task-id",
            "harness-07-task-receipt-writer",
            "--record-kind",
            "candidate-verified",
            "--result",
            "candidate_verified",
            "--output",
            str(output),
            "--artifact",
            f"missing={tmp_path / 'missing.toml'}",
        ]
    )

    assert missing_artifact.returncode != 0
    assert not output.exists()


def test_write_receipt_reports_dirty_worktree_without_cleaning_it(tmp_path: Path) -> None:
    _require_write_receipt()

    repo = _init_git_repo(tmp_path)
    output = tmp_path / "dirty-receipt.json"

    _write_text(repo / "tracked.txt", "dirty\n")

    code, _ = _json_result(
        [
            "write-receipt",
            "--task-id",
            "harness-07-task-receipt-writer",
            "--record-kind",
            "candidate-audit",
            "--result",
            "candidate_audit_passed",
            "--output",
            str(output),
        ],
        cwd=repo,
    )

    assert code == 0
    receipt = _load_receipt(output)
    git_state = cast(dict[str, Any], receipt["git"])

    assert git_state["branch"] == "main"
    assert git_state["worktree_clean"] is False
    assert _git(repo, "status", "--short") == "M tracked.txt"
