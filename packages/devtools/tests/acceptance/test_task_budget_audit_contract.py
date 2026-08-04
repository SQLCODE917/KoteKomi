from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from packages.devtools.tests.acceptance._oracle_fixtures import (
    git,
    git_output,
    init_git_repo,
    render_manifest,
    run_command,
    sha256_file,
    status_then_index_baseline,
    write_fixture_text,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_MANIFEST = REPO_ROOT / ".agent" / "tasks" / "harness-03-task-budget-audit.toml"
SCHEMA_SOURCE = REPO_ROOT / ".agent" / "schemas" / "task-manifest-v1.schema.json"
CLI_NAME = "kotekomi-agent"
MANIFEST_RELATIVE = ".agent/tasks/example-task.toml"

def _budget_help_reports_absent() -> bool:
    executable = shutil.which(CLI_NAME)
    if executable is None:
        return False
    completed = subprocess.run(
        (executable, "budget-audit", "--help"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return (
        completed.returncode == 2
        and "invalid choice" in completed.stderr
        and "budget-audit" in completed.stderr
    )


pytestmark = pytest.mark.skipif(
    _budget_help_reports_absent(),
    reason="H3 bootstrap: budget-audit is not implemented.",
)


@dataclass(frozen=True)
class Budget:
    maximum_production_files: int = 2
    maximum_test_files: int = 2
    maximum_production_diff_lines: int = 10


@dataclass(frozen=True)
class ManifestPatch:
    allowed_paths: tuple[str, ...] = (
        "packages/devtools/src/",
        "packages/devtools/tests/unit/",
    )
    budget: Budget = Budget()


DEFAULT_MANIFEST_PATCH = ManifestPatch()
DEFAULT_BUDGET = Budget()


@dataclass
class Fixture:
    root: Path
    base_commit: str
    manifest_patch: ManifestPatch

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_RELATIVE

    def write_manifest(self) -> None:
        write_fixture_text(self.manifest_path, render_manifest(_manifest_data(self)))

    def amend_manifest(self, patch: ManifestPatch) -> None:
        self.manifest_patch = patch
        self.write_manifest()
        git(self.root, "add", MANIFEST_RELATIVE)
        git(self.root, "commit", "--amend", "--no-edit")
        self.base_commit = git_output(self.root, "rev-parse", "HEAD")

    def commit(self, message: str) -> str:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-m", message)
        return git_output(self.root, "rev-parse", "HEAD")

    def run_revision(self, head: str) -> subprocess.CompletedProcess[str]:
        return _run_budget(
            self.root,
            MANIFEST_RELATIVE,
            "--base",
            self.base_commit,
            "--head",
            head,
        )

    def run_worktree(self) -> subprocess.CompletedProcess[str]:
        return _run_budget(
            self.root,
            MANIFEST_RELATIVE,
            "--base",
            self.base_commit,
            "--worktree",
        )


def test_budget_audit_help_reports_command() -> None:
    completed = run_command(REPO_ROOT, (CLI_NAME, "budget-audit", "--help"))
    assert completed.returncode == 0
    assert "usage: kotekomi-agent budget-audit" in completed.stdout


def test_revision_diff_within_budget_is_exact(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(
        fixture.root / "packages/devtools/src/kotekomi_devtools/a.py",
        _lines(3),
    )
    head = fixture.commit("add production file")
    base = _resolve(fixture.root, fixture.base_commit)
    resolved_head = _resolve(fixture.root, head)

    _assert_result(
        fixture.run_revision(head),
        {
            "status": "within_budget",
            "schema_version": 1,
            "task_id": "example-budget-task",
            "mode": "revision",
            "base_revision": base,
            "head_revision": resolved_head,
            "budget": _budget_payload(),
            "totals": {
                "production_files": 1,
                "test_files": 0,
                "production_diff_lines": 3,
            },
            "path_stats": [
                _path_stat(
                    "packages/devtools/src/kotekomi_devtools/a.py",
                    "production",
                    3,
                    0,
                )
            ],
            "diagnostics": [],
        },
        exit_code=0,
    )


def test_no_changes_is_within_budget(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    _assert_result(
        fixture.run_revision(fixture.base_commit),
        {
            "status": "within_budget",
            "schema_version": 1,
            "task_id": "example-budget-task",
            "mode": "revision",
            "base_revision": _resolve(fixture.root, fixture.base_commit),
            "head_revision": _resolve(fixture.root, fixture.base_commit),
            "budget": _budget_payload(),
            "totals": {
                "production_files": 0,
                "test_files": 0,
                "production_diff_lines": 0,
            },
            "path_stats": [],
            "diagnostics": [],
        },
        exit_code=0,
    )


def test_revision_diff_over_production_lines(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(
        fixture.root / "packages/devtools/src/kotekomi_devtools/a.py",
        _lines(11),
    )
    head = fixture.commit("large production file")
    result = _payload(fixture.run_revision(head), exit_code=1)

    assert result["status"] == "over_budget"
    assert result["totals"]["production_diff_lines"] == 11
    assert result["diagnostics"] == [
        _diagnostic(
            "task_budget.budget_violation",
            "/budget/maximum_production_diff_lines",
            "production_diff_lines",
        )
    ]


def test_revision_diff_over_production_file_count(tmp_path: Path) -> None:
    fixture = _create_ready_repo(
        tmp_path,
        ManifestPatch(budget=Budget(maximum_production_files=1)),
    )
    write_fixture_text(
        fixture.root / "packages/devtools/src/kotekomi_devtools/a.py",
        "a\n",
    )
    write_fixture_text(
        fixture.root / "packages/devtools/src/kotekomi_devtools/b.py",
        "b\n",
    )
    head = fixture.commit("two production files")
    result = _payload(fixture.run_revision(head), exit_code=1)

    assert result["totals"]["production_files"] == 2
    assert result["diagnostics"] == [
        _diagnostic(
            "task_budget.budget_violation",
            "/budget/maximum_production_files",
            "production_files",
        )
    ]


def test_revision_diff_over_test_file_count(tmp_path: Path) -> None:
    fixture = _create_ready_repo(
        tmp_path,
        ManifestPatch(budget=Budget(maximum_test_files=1)),
    )
    write_fixture_text(
        fixture.root / "packages/devtools/tests/unit/test_a.py",
        "def test_a():\n    assert True\n",
    )
    write_fixture_text(
        fixture.root / "packages/devtools/tests/unit/test_b.py",
        "def test_b():\n    assert True\n",
    )
    head = fixture.commit("two test files")
    result = _payload(fixture.run_revision(head), exit_code=1)

    assert result["totals"]["test_files"] == 2
    assert result["diagnostics"] == [
        _diagnostic(
            "task_budget.budget_violation",
            "/budget/maximum_test_files",
            "test_files",
        )
    ]


def test_revision_diff_outside_allowed_paths(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(fixture.root / "docs/notes.md", "outside\n")
    head = fixture.commit("outside allowed paths")
    result = _payload(fixture.run_revision(head), exit_code=1)

    assert result["path_stats"] == [
        _path_stat("docs/notes.md", "other", 1, 0)
    ]
    assert result["diagnostics"] == [
        _diagnostic(
            "task_budget.scope_violation",
            "/path_stats/0/path",
            "allowed_path",
        )
    ]


def test_multiple_diagnostics_are_sorted(tmp_path: Path) -> None:
    fixture = _create_ready_repo(
        tmp_path,
        ManifestPatch(budget=Budget(maximum_production_files=1, maximum_production_diff_lines=1)),
    )
    write_fixture_text(fixture.root / "docs/notes.md", "outside\n")
    write_fixture_text(fixture.root / "packages/devtools/src/kotekomi_devtools/a.py", _lines(2))
    write_fixture_text(fixture.root / "packages/devtools/src/kotekomi_devtools/b.py", "b\n")
    head = fixture.commit("multiple violations")
    result = _payload(fixture.run_revision(head), exit_code=1)

    assert result["diagnostics"] == [
        _diagnostic(
            "task_budget.budget_violation",
            "/budget/maximum_production_diff_lines",
            "production_diff_lines",
        ),
        _diagnostic(
            "task_budget.budget_violation",
            "/budget/maximum_production_files",
            "production_files",
        ),
        _diagnostic(
            "task_budget.scope_violation",
            "/path_stats/0/path",
            "allowed_path",
        ),
    ]


def test_worktree_tracked_modification_is_read_only(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    tracked = fixture.root / "packages/devtools/src/kotekomi_devtools/existing.py"
    write_fixture_text(tracked, "old\n")
    fixture.base_commit = fixture.commit("add tracked file")
    write_fixture_text(tracked, "old\nnew\n")

    before = _repo_state(fixture.root)
    result = _payload(fixture.run_worktree(), exit_code=0)
    after = _repo_state(fixture.root)

    assert before == after
    assert result["mode"] == "worktree"
    assert result["head_revision"] == "WORKTREE"
    assert result["path_stats"] == [
        _path_stat(
            "packages/devtools/src/kotekomi_devtools/existing.py",
            "production",
            1,
            0,
        )
    ]


def test_worktree_untracked_file_is_read_only(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(
        fixture.root / "packages/devtools/src/kotekomi_devtools/untracked.py",
        _lines(2),
    )

    before = _repo_state(fixture.root)
    result = _payload(fixture.run_worktree(), exit_code=0)
    after = _repo_state(fixture.root)

    assert before == after
    assert result["path_stats"] == [
        _path_stat(
            "packages/devtools/src/kotekomi_devtools/untracked.py",
            "production",
            2,
            0,
        )
    ]


def test_worktree_untracked_file_outside_allowed_paths(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(fixture.root / "scratch.txt", "outside\n")
    result = _payload(fixture.run_worktree(), exit_code=1)

    assert result["path_stats"] == [
        _path_stat("scratch.txt", "other", 1, 0)
    ]
    assert result["diagnostics"] == [
        _diagnostic(
            "task_budget.scope_violation",
            "/path_stats/0/path",
            "allowed_path",
        )
    ]


def test_deleted_production_file_counts_deleted_lines(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    target = fixture.root / "packages/devtools/src/kotekomi_devtools/delete_me.py"
    write_fixture_text(target, _lines(4))
    fixture.base_commit = fixture.commit("add file to delete")
    target.unlink()
    head = fixture.commit("delete production file")
    result = _payload(fixture.run_revision(head), exit_code=0)

    assert result["path_stats"] == [
        _path_stat(
            "packages/devtools/src/kotekomi_devtools/delete_me.py",
            "production",
            0,
            4,
        )
    ]
    assert result["totals"]["production_diff_lines"] == 4


def test_path_stats_are_sorted_by_path(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(
        fixture.root / "packages/devtools/tests/unit/test_z.py",
        "def test_z():\n    assert True\n",
    )
    write_fixture_text(fixture.root / "packages/devtools/src/kotekomi_devtools/a.py", "a\n")
    head = fixture.commit("two sorted paths")
    result = _payload(fixture.run_revision(head), exit_code=0)

    assert [item["path"] for item in result["path_stats"]] == [
        "packages/devtools/src/kotekomi_devtools/a.py",
        "packages/devtools/tests/unit/test_z.py",
    ]


def _create_ready_repo(
    tmp_path: Path,
    patch: ManifestPatch = DEFAULT_MANIFEST_PATCH,
) -> Fixture:
    root = tmp_path / "repo"
    root.mkdir()
    init_git_repo(root)
    write_fixture_text(
        root / ".agent/schemas/task-manifest-v1.schema.json",
        SCHEMA_SOURCE.read_text(),
    )
    write_fixture_text(root / "AGENTS.md", "Test instructions.\n")
    write_fixture_text(root / "docs/example-tdd.md", "Example TDD.\n")
    write_fixture_text(
        root / "packages/devtools/tests/acceptance/protected.py",
        "PROTECTED = True\n",
    )
    git(root, "add", "-A")
    git(root, "commit", "-m", "baseline")
    base = git_output(root, "rev-parse", "HEAD")
    fixture = Fixture(root, base, patch)
    fixture.write_manifest()
    git(root, "add", "-A")
    git(root, "commit", "-m", "specification")
    fixture.base_commit = git_output(root, "rev-parse", "HEAD")
    return fixture


def _run_budget(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return run_command(cwd, (CLI_NAME, "budget-audit", *argv))


def _resolve(cwd: Path, revision: str) -> str:
    return git_output(cwd, "rev-parse", revision)


def _repo_state(root: Path) -> tuple[str, str, str]:
    status, index = status_then_index_baseline(root)
    return (
        git_output(root, "branch", "--show-current"),
        status,
        index,
    )


def _lines(count: int) -> str:
    return "".join(f"line {index}\n" for index in range(count))


def _payload(
    completed: subprocess.CompletedProcess[str],
    *,
    exit_code: int,
) -> dict[str, Any]:
    assert completed.returncode == exit_code
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def _assert_result(
    completed: subprocess.CompletedProcess[str],
    expected: dict[str, Any],
    *,
    exit_code: int,
) -> None:
    assert _payload(completed, exit_code=exit_code) == expected


def _path_stat(
    path: str,
    category: str,
    added: int,
    deleted: int,
) -> dict[str, Any]:
    return {
        "path": path,
        "category": category,
        "added": added,
        "deleted": deleted,
        "diff_lines": added + deleted,
    }


def _budget_payload(
    budget: Budget = DEFAULT_BUDGET,
) -> dict[str, int]:
    return {
        "maximum_production_files": budget.maximum_production_files,
        "maximum_test_files": budget.maximum_test_files,
        "maximum_production_diff_lines": budget.maximum_production_diff_lines,
    }


def _diagnostic(code: str, location: str, rule: str) -> dict[str, str]:
    return {"code": code, "location": location, "rule": rule}


def _manifest_data(fixture: Fixture) -> dict[str, Any]:
    template = tomllib.loads(SOURCE_MANIFEST.read_text())
    protected_path = "packages/devtools/tests/acceptance/protected.py"
    protected_sha = sha256_file(fixture.root / protected_path)

    template["task_id"] = "example-budget-task"
    template["title"] = "Example Budget Task"
    template["baseline_revision"] = fixture.base_commit
    template["tdd_path"] = "docs/example-tdd.md"
    template["tdd_sha256"] = sha256_file(fixture.root / "docs/example-tdd.md")
    template["goal"] = "Exercise budget-audit acceptance fixture."
    template["depends_on"] = []
    template["allowed_paths"] = list(fixture.manifest_patch.allowed_paths)
    template["reference_paths"] = ["AGENTS.md"]
    template["protected_artifacts"] = [
        {
            "path": protected_path,
            "sha256": protected_sha,
            "kind": "acceptance-test",
        }
    ]
    template["acceptance"] = [
        {
            "id": "fixture-noop",
            "argv": ["true"],
            "timeout_seconds": 60,
            "profile": "portable-local",
        }
    ]
    template["budget"] = {
        "maximum_production_files": fixture.manifest_patch.budget.maximum_production_files,
        "maximum_test_files": fixture.manifest_patch.budget.maximum_test_files,
        "maximum_production_diff_lines": (
            fixture.manifest_patch.budget.maximum_production_diff_lines
        ),
    }

    return template
