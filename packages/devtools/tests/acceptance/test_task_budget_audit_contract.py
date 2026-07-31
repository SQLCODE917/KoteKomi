from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_MANIFEST = REPO_ROOT / ".agent" / "tasks" / "harness-03-task-budget-audit.toml"
SCHEMA_SOURCE = REPO_ROOT / ".agent" / "schemas" / "task-manifest-v1.schema.json"
CLI_NAME = "kotekomi-agent"
MANIFEST_RELATIVE = ".agent/tasks/example-task.toml"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "KoteKomi Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "KoteKomi Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


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
        _write(self.manifest_path, _render_manifest(self))

    def amend_manifest(self, patch: ManifestPatch) -> None:
        self.manifest_patch = patch
        self.write_manifest()
        _git(self.root, "add", MANIFEST_RELATIVE)
        _git(self.root, "commit", "--amend", "--no-edit")
        self.base_commit = _git_output(self.root, "rev-parse", "HEAD")

    def commit(self, message: str) -> str:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-m", message)
        return _git_output(self.root, "rev-parse", "HEAD")

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
    completed = _run(REPO_ROOT, CLI_NAME, "budget-audit", "--help")
    assert completed.returncode == 0
    assert "usage: kotekomi-agent budget-audit" in completed.stdout


def test_revision_diff_within_budget_is_exact(tmp_path: Path) -> None:
    fixture = _create_ready_repo(tmp_path)
    _write(
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
    _write(
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
    _write(
        fixture.root / "packages/devtools/src/kotekomi_devtools/a.py",
        "a\n",
    )
    _write(
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
    _write(
        fixture.root / "packages/devtools/tests/unit/test_a.py",
        "def test_a():\n    assert True\n",
    )
    _write(
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
    _write(fixture.root / "docs/notes.md", "outside\n")
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
    _write(fixture.root / "docs/notes.md", "outside\n")
    _write(fixture.root / "packages/devtools/src/kotekomi_devtools/a.py", _lines(2))
    _write(fixture.root / "packages/devtools/src/kotekomi_devtools/b.py", "b\n")
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
    _write(tracked, "old\n")
    fixture.base_commit = fixture.commit("add tracked file")
    _write(tracked, "old\nnew\n")

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
    _write(
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
    _write(fixture.root / "scratch.txt", "outside\n")
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
    _write(target, _lines(4))
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
    _write(
        fixture.root / "packages/devtools/tests/unit/test_z.py",
        "def test_z():\n    assert True\n",
    )
    _write(fixture.root / "packages/devtools/src/kotekomi_devtools/a.py", "a\n")
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
    _git(root, "init", "-b", "main")
    _write(root / ".agent/schemas/task-manifest-v1.schema.json", SCHEMA_SOURCE.read_text())
    _write(root / "AGENTS.md", "Test instructions.\n")
    _write(root / "docs/example-tdd.md", "Example TDD.\n")
    _write(root / "packages/devtools/tests/acceptance/protected.py", "PROTECTED = True\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "baseline")
    base = _git_output(root, "rev-parse", "HEAD")
    fixture = Fixture(root, base, patch)
    fixture.write_manifest()
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "specification")
    fixture.base_commit = _git_output(root, "rev-parse", "HEAD")
    return fixture


def _run_budget(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return _run(cwd, CLI_NAME, "budget-audit", *argv)


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=GIT_ENV,
    )


def _git(cwd: Path, *argv: str) -> None:
    completed = _run(cwd, "git", *argv)
    if completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(argv)} failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def _git_output(cwd: Path, *argv: str) -> str:
    completed = _run(cwd, "git", *argv)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def _resolve(cwd: Path, revision: str) -> str:
    return _git_output(cwd, "rev-parse", revision)


def _repo_state(root: Path) -> tuple[str, str, str]:
    return (
        _git_output(root, "branch", "--show-current"),
        _git_output(root, "status", "--short"),
        _sha256_file(root / ".git/index"),
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


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


def _render_manifest(fixture: Fixture) -> str:
    template = tomllib.loads(SOURCE_MANIFEST.read_text())
    protected_path = "packages/devtools/tests/acceptance/protected.py"
    protected_sha = _sha256_file(fixture.root / protected_path)

    template["task_id"] = "example-budget-task"
    template["title"] = "Example Budget Task"
    template["baseline_revision"] = fixture.base_commit
    template["tdd_path"] = "docs/example-tdd.md"
    template["tdd_sha256"] = _sha256_file(fixture.root / "docs/example-tdd.md")
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

    return _toml_document(template)


def _toml_document(data: dict[str, Any]) -> str:
    lines: list[str] = []

    for key, value in data.items():
        if isinstance(value, dict):
            continue

        if isinstance(value, list) and value and isinstance(value[0], dict):
            continue

        lines.append(f"{key} = {_toml_value(value)}")

    for key, value in data.items():
        if isinstance(value, dict):
            table = cast("dict[str, Any]", value)
            lines.append("")
            lines.append(f"[{key}]")

            for child_key, child_value in table.items():
                lines.append(f"{child_key} = {_toml_value(child_value)}")

            continue

        if isinstance(value, list) and value and isinstance(value[0], dict):
            tables = cast("list[dict[str, Any]]", value)

            for item in tables:
                lines.append("")
                lines.append(f"[[{key}]]")

                for child_key, child_value in item.items():
                    lines.append(f"{child_key} = {_toml_value(child_value)}")

    return "\n".join(lines) + "\n"

def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, list):
        items = cast("list[Any]", value)
        return "[" + ", ".join(_toml_value(item) for item in items) + "]"

    raise TypeError(f"Unsupported TOML value: {value!r}")

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
