from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_ACCEPTANCE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _ACCEPTANCE_DIR.parents[3]

if str(_ACCEPTANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_ACCEPTANCE_DIR))

_GIT_BACKED_ACCEPTANCE_FIXTURES = [
    _ACCEPTANCE_DIR / "test_task_preflight_contract.py",
    _ACCEPTANCE_DIR / "test_task_budget_audit_contract.py",
    _ACCEPTANCE_DIR / "test_task_scope_audit_contract.py",
]

_REQUIRED_API = [
    "write_fixture_text",
    "sha256_file",
    "run_command",
    "run_json_command",
    "git",
    "git_output",
    "init_git_repo",
    "status_short",
    "index_sha",
    "status_then_index_baseline",
    "assert_status_and_index_unchanged",
    "protected_artifact",
    "render_manifest",
]


def _toolkit() -> Any:
    return pytest.importorskip(
        "_oracle_fixtures",
        reason="H5 oracle fixture toolkit is not implemented yet.",
    )


def test_toolkit_exports_required_api() -> None:
    toolkit = _toolkit()

    missing = [name for name in _REQUIRED_API if not hasattr(toolkit, name)]

    assert missing == []


def test_parent_safe_write_creates_parent_and_uses_utf8(tmp_path: Path) -> None:
    toolkit = _toolkit()

    target = tmp_path / "missing" / "nested" / "fixture.txt"

    toolkit.write_fixture_text(target, "alpha\nβeta\n")

    assert target.read_text(encoding="utf-8") == "alpha\nβeta\n"
    assert toolkit.sha256_file(target) == (
        "8f526437d5fd3c789fc5f8d26b8452b4bde81bb0aa0dbbbc81fd8091d1d378d7"
    )


def test_git_repo_helpers_create_clean_deterministic_repo(tmp_path: Path) -> None:
    toolkit = _toolkit()

    repo = tmp_path / "repo"
    repo.mkdir()

    base = toolkit.init_git_repo(repo)

    assert len(base) == 40
    assert toolkit.git_output(repo, "rev-parse", "HEAD") == base
    assert toolkit.status_short(repo) == ""

    toolkit.write_fixture_text(repo / "dir" / "fixture.txt", "value\n")
    toolkit.git(repo, "add", ".")
    toolkit.git(repo, "commit", "-m", "Add fixture")

    assert toolkit.status_short(repo) == ""


def test_status_then_index_baseline_is_stable_after_tracked_change(
    tmp_path: Path,
) -> None:
    toolkit = _toolkit()

    repo = tmp_path / "repo"
    repo.mkdir()

    toolkit.init_git_repo(repo)

    tracked = repo / "tracked.txt"
    toolkit.write_fixture_text(tracked, "one\n")
    toolkit.git(repo, "add", ".")
    toolkit.git(repo, "commit", "-m", "Add tracked file")

    toolkit.write_fixture_text(tracked, "two\n")

    baseline = toolkit.status_then_index_baseline(repo)

    assert baseline == toolkit.status_then_index_baseline(repo)

    toolkit.assert_status_and_index_unchanged(repo, baseline)


def test_run_json_command_returns_exit_code_and_payload() -> None:
    toolkit = _toolkit()

    code, payload = toolkit.run_json_command(
        _REPO_ROOT,
        [
            "uv",
            "run",
            "kotekomi-agent",
            "validate-task",
            ".agent/tasks/harness-05-oracle-fixture-toolkit.toml",
        ],
        expected_exit_code=0,
    )

    assert code == 0
    assert payload["status"] == "valid"
    assert payload["task_id"] == "harness-05-oracle-fixture-toolkit"


def test_protected_artifact_helper_returns_kind_path_and_digest(
    tmp_path: Path,
) -> None:
    toolkit = _toolkit()

    artifact = tmp_path / "artifact.txt"
    toolkit.write_fixture_text(artifact, "artifact\n")

    payload = toolkit.protected_artifact(artifact, "fixture")

    assert payload == {
        "kind": "fixture",
        "path": str(artifact),
        "sha256": toolkit.sha256_file(artifact),
    }


def test_git_backed_acceptance_fixtures_use_toolkit_and_no_raw_write_text() -> None:
    _toolkit()

    failures: list[str] = []

    for path in _GIT_BACKED_ACCEPTANCE_FIXTURES:
        text = path.read_text(encoding="utf-8")

        if "_oracle_fixtures" not in text:
            failures.append(f"{path}: does not import _oracle_fixtures")

        if ".write_text(" in text:
            failures.append(f"{path}: contains direct .write_text(")

    assert failures == []
