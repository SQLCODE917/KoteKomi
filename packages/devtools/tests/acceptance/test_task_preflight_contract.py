from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

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
SCHEMA_SOURCE = REPO_ROOT / ".agent" / "schemas" / "task-manifest-v1.schema.json"
CLI_NAME = "kotekomi-agent"
MANIFEST_RELATIVE = ".agent/tasks/example-task.toml"
H1_TASK_ID = "harness-01-task-manifest-contract"


def _preflight_help_reports_absent() -> bool:
    executable = shutil.which(CLI_NAME)

    if executable is None:
        return False

    completed = subprocess.run(
        (executable, "preflight-task", "--help"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return (
        completed.returncode == 2
        and "invalid choice" in completed.stderr
        and "preflight-task" in completed.stderr
    )


pytestmark = pytest.mark.skipif(
    _preflight_help_reports_absent(),
    reason="H2 bootstrap: preflight-task is not implemented.",
)


@dataclass(frozen=True)
class Protected:
    path: str
    sha256: str
    kind: str = "acceptance-test"


@dataclass(frozen=True)
class ManifestSpec:
    baseline_revision: str
    task_id: str
    tdd_path: str
    tdd_sha256: str
    allowed_paths: tuple[str, ...]
    reference_paths: tuple[str, ...]
    protected_artifacts: tuple[Protected, ...]
    depends_on: tuple[str, ...]


@dataclass
class RepositoryFixture:
    root: Path
    baseline_commit: str
    specification_commit: str
    manifest: ManifestSpec

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_RELATIVE

    def write_manifest(self) -> None:
        write_fixture_text(
            self.manifest_path,
            render_manifest(_manifest_data(self.manifest)),
        )

    def amend(
        self,
        manifest: ManifestSpec | None = None,
    ) -> str:
        if manifest is not None:
            self.manifest = manifest
            self.write_manifest()

        git(self.root, "add", "-A")
        git(self.root, "commit", "--amend", "--no-edit")
        self.specification_commit = git_output(
            self.root,
            "rev-parse",
            "HEAD",
        )
        return self.specification_commit

    def run(
        self,
        argument: str = MANIFEST_RELATIVE,
        *,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return _run_preflight(cwd or self.root, argument)


def _cli() -> str:
    executable = shutil.which(CLI_NAME)

    if executable is None:
        pytest.fail(f"{CLI_NAME} is not available on PATH")

    return executable


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_manifest_sha(path: Path) -> str:
    value = tomllib.loads(path.read_text())
    content = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256_bytes(content)


def _manifest_data(spec: ManifestSpec) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": spec.task_id,
        "title": "Example preflight task",
        "status": "ready_for_terra_high",
        "series_id": "example-series",
        "task_class": "repository-tooling",
        "model_profile": "terra-high-v1",
        "baseline_revision": spec.baseline_revision,
        "tdd_path": spec.tdd_path,
        "tdd_sha256": spec.tdd_sha256,
        "goal": "Prove one disposable task is ready.",
        "depends_on": list(spec.depends_on),
        "allowed_paths": list(spec.allowed_paths),
        "reference_paths": list(spec.reference_paths),
        "stop_conditions": ["A protected contract conflicts."],
        "readiness": {
            "dominant_outcome": "A task is ready or not ready.",
            "contract_family": "task-preflight-v1",
            "public_entry_point": "kotekomi-agent preflight-task",
            "authority": "The committed manifest and protected records.",
            "scope_policy": "Read-only repository preflight.",
            "side_effect_boundary": "git-read-only",
            "failure_policy": "Not-ready diagnostics and no writes.",
            "negative_proof": "Dirty, ambiguous, and unlocked tasks fail.",
            "legacy_disposition": "No existing command is replaced.",
            "unresolved_decisions": [],
        },
        "budget": {
            "maximum_production_files": 2,
            "maximum_test_files": 2,
            "maximum_production_diff_lines": 450,
        },
        "protected_artifacts": [
            {"path": item.path, "sha256": item.sha256, "kind": item.kind}
            for item in spec.protected_artifacts
        ],
        "acceptance": [
            {
                "id": "example-contract",
                "argv": ["python", "-m", "pytest"],
                "timeout_seconds": 120,
                "profile": "portable-local",
            }
        ],
    }


def _verified_receipt(
    *,
    task_id: str = H1_TASK_ID,
    result: str = "leaf_verified",
) -> str:
    return (
        json.dumps(
            {
                "schema_version": 1,
                "task_id": task_id,
                "result": result,
            },
            sort_keys=True,
        )
        + "\n"
    )


def _commit(cwd: Path, message: str) -> str:
    git(cwd, "add", "-A")
    git(cwd, "commit", "-m", message)
    return git_output(cwd, "rev-parse", "HEAD")


def _create_ready_repo(tmp_path: Path) -> RepositoryFixture:
    root = tmp_path / "repo"
    root.mkdir()
    init_git_repo(root)

    schema_target = root / ".agent" / "schemas" / "task-manifest-v1.schema.json"
    schema_target.parent.mkdir(parents=True)
    shutil.copyfile(SCHEMA_SOURCE, schema_target)

    write_fixture_text(root / "AGENTS.md", "# Test repository\n")
    write_fixture_text(
        root / "docs" / "reference" / "guide.md",
        "# Reference\n",
    )
    write_fixture_text(root / "README.md", "# Baseline\n")
    baseline = _commit(root, "baseline")

    tdd_path = root / "docs" / "task.md"
    protected_path = root / "tests" / "acceptance.py"
    write_fixture_text(tdd_path, "# Task contract\n")
    write_fixture_text(protected_path, "EXPECTED = 'ready'\n")
    write_fixture_text(
        root / ".agent" / "receipts" / "h1.json",
        _verified_receipt(),
    )

    spec = ManifestSpec(
        baseline_revision=baseline,
        task_id="example-task",
        tdd_path="docs/task.md",
        tdd_sha256=sha256_file(tdd_path),
        allowed_paths=("src/tool.py", "tests/unit/"),
        reference_paths=(
            "AGENTS.md",
            "docs/reference/",
        ),
        protected_artifacts=(
            Protected(
                "tests/acceptance.py",
                sha256_file(protected_path),
            ),
        ),
        depends_on=(H1_TASK_ID,),
    )
    fixture = RepositoryFixture(
        root=root,
        baseline_commit=baseline,
        specification_commit="",
        manifest=spec,
    )
    fixture.write_manifest()
    fixture.specification_commit = _commit(
        root,
        "freeze specification",
    )
    return fixture


def _run_preflight(
    cwd: Path,
    argument: str,
) -> subprocess.CompletedProcess[str]:
    return run_command(cwd, (_cli(), "preflight-task", argument))


def _payload(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    assert completed.stdout.endswith("\n")
    assert completed.stdout.count("\n") == 1
    value: object = json.loads(completed.stdout)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _diagnostic(
    code: str,
    location: str,
    rule: str,
) -> dict[str, str]:
    return {
        "code": code,
        "location": location,
        "rule": rule,
    }


def _stage1_expected(
    diagnostics: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "status": "not_ready",
        "schema_version": None,
        "task_id": None,
        "manifest_sha256": None,
        "manifest_file_sha256": None,
        "execution_base_revision": None,
        "diagnostics": diagnostics,
    }


def _stage2_expected(
    fixture: RepositoryFixture,
    diagnostics: list[dict[str, str]],
    *,
    task_id: str | None,
) -> dict[str, object]:
    return {
        "status": "not_ready",
        "schema_version": 1,
        "task_id": task_id,
        "manifest_sha256": None,
        "manifest_file_sha256": sha256_file(fixture.manifest_path),
        "execution_base_revision": None,
        "diagnostics": diagnostics,
    }


def _stage3_expected(
    fixture: RepositoryFixture,
    diagnostics: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "status": ("ready" if not diagnostics else "not_ready"),
        "schema_version": 1,
        "task_id": fixture.manifest.task_id,
        "manifest_sha256": _canonical_manifest_sha(fixture.manifest_path),
        "manifest_file_sha256": sha256_file(fixture.manifest_path),
        "execution_base_revision": (fixture.specification_commit),
        "diagnostics": diagnostics,
    }


def _assert_result(
    completed: subprocess.CompletedProcess[str],
    expected: dict[str, object],
    *,
    exit_code: int,
) -> None:
    expected_stdout = (
        json.dumps(
            expected,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    assert completed.returncode == exit_code
    assert completed.stderr == ""
    assert completed.stdout == expected_stdout
    assert _payload(completed) == expected


def _branch(root: Path) -> str:
    return git_output(root, "branch", "--show-current")


def test_ready_result_is_exact_deterministic_and_read_only(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    before_status, before_index = status_then_index_baseline(fixture.root)
    before = {
        "head": git_output(fixture.root, "rev-parse", "HEAD"),
        "branch": _branch(fixture.root),
        "status": before_status,
        "index": before_index,
    }

    first = fixture.run()
    second = fixture.run()
    expected = _stage3_expected(fixture, [])

    _assert_result(first, expected, exit_code=0)
    _assert_result(second, expected, exit_code=0)
    assert first.stdout == second.stdout

    after_status, after_index = status_then_index_baseline(fixture.root)
    after = {
        "head": git_output(fixture.root, "rev-parse", "HEAD"),
        "branch": _branch(fixture.root),
        "status": after_status,
        "index": after_index,
    }
    assert after == before


@pytest.mark.parametrize(
    ("argument", "rule"),
    [
        ("/absolute/task.toml", "repository_relative_posix"),
        ("./.agent/tasks/task.toml", "repository_relative_posix"),
        ("../task.toml", "repository_relative_posix"),
        (r".agent\tasks\task.toml", "repository_relative_posix"),
        (".agent//tasks/task.toml", "repository_relative_posix"),
        ("~/task.toml", "repository_relative_posix"),
        (".agent/tasks/*.toml", "repository_relative_posix"),
        (".agent/tasks/", "exact_file"),
    ],
)
def test_manifest_argument_violations_short_circuit(
    tmp_path: Path,
    argument: str,
    rule: str,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    completed = fixture.run(argument)
    expected = _stage1_expected(
        [
            _diagnostic(
                "task_preflight.manifest_path_violation",
                "/manifest_path",
                rule,
            )
        ]
    )
    _assert_result(completed, expected, exit_code=1)


def test_multiple_stage_one_diagnostics_are_stable(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    completed = fixture.run("~/", cwd=fixture.root / "docs")
    expected = _stage1_expected(
        [
            _diagnostic(
                "task_preflight.manifest_path_violation",
                "/manifest_path",
                "exact_file",
            ),
            _diagnostic(
                "task_preflight.manifest_path_violation",
                "/manifest_path",
                "repository_relative_posix",
            ),
            _diagnostic(
                "task_preflight.repository_violation",
                "/repository",
                "repository_root",
            ),
        ]
    )
    _assert_result(completed, expected, exit_code=1)


def test_invocation_outside_git_repository(
    tmp_path: Path,
) -> None:
    root = tmp_path / "not-a-repository"
    root.mkdir()
    completed = _run_preflight(root, MANIFEST_RELATIVE)
    expected = _stage1_expected(
        [
            _diagnostic(
                "task_preflight.repository_violation",
                "/repository",
                "git_repository",
            )
        ]
    )
    _assert_result(completed, expected, exit_code=1)


def test_invocation_from_repository_subdirectory(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    subdirectory = fixture.root / "docs"
    completed = fixture.run(cwd=subdirectory)
    expected = _stage1_expected(
        [
            _diagnostic(
                "task_preflight.repository_violation",
                "/repository",
                "repository_root",
            )
        ]
    )
    _assert_result(completed, expected, exit_code=1)


@pytest.mark.parametrize(
    "dirty_kind",
    ["staged", "unstaged", "untracked"],
)
def test_dirty_worktree_is_not_ready(
    tmp_path: Path,
    dirty_kind: str,
) -> None:
    fixture = _create_ready_repo(tmp_path)

    if dirty_kind == "staged":
        write_fixture_text(fixture.root / "README.md", "# Staged\n")
        git(fixture.root, "add", "README.md")
    elif dirty_kind == "unstaged":
        write_fixture_text(fixture.root / "README.md", "# Unstaged\n")
    else:
        write_fixture_text(fixture.root / "scratch.txt", "untracked\n")

    expected = _stage3_expected(
        fixture,
        [
            _diagnostic(
                "task_preflight.repository_violation",
                "/repository",
                "clean_worktree",
            )
        ],
    )
    _assert_result(fixture.run(), expected, exit_code=1)


def test_ignored_file_does_not_make_task_dirty(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(fixture.root / ".gitignore", "ignored.txt\n")
    git(fixture.root, "add", ".gitignore")
    git(fixture.root, "commit", "--amend", "--no-edit")
    fixture.specification_commit = git_output(
        fixture.root,
        "rev-parse",
        "HEAD",
    )
    write_fixture_text(fixture.root / "ignored.txt", "ignored\n")
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, []),
        exit_code=0,
    )


def test_untracked_manifest_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    manifest_text = fixture.manifest_path.read_text()
    git(fixture.root, "rm", MANIFEST_RELATIVE)
    fixture.specification_commit = _commit(
        fixture.root,
        "delete manifest",
    )
    write_fixture_text(fixture.manifest_path, manifest_text)

    diagnostics = [
        _diagnostic(
            "task_preflight.manifest_violation",
            "/manifest_path",
            "tracked_regular_file",
        ),
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_committed_manifest_symbolic_link_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    manifest_text = fixture.manifest_path.read_text()
    target = fixture.root / ".agent" / "tasks" / "manifest-target.toml"
    write_fixture_text(target, manifest_text)
    fixture.manifest_path.unlink()
    fixture.manifest_path.symlink_to("manifest-target.toml")
    fixture.amend()

    diagnostics = [
        _diagnostic(
            "task_preflight.manifest_violation",
            "/manifest_path",
            "tracked_regular_file",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_current_manifest_symbolic_link_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    manifest_text = fixture.manifest_path.read_text()
    target = fixture.root / ".agent" / "tasks" / "current-target.toml"
    write_fixture_text(target, manifest_text)
    fixture.manifest_path.unlink()
    fixture.manifest_path.symlink_to("current-target.toml")

    diagnostics = [
        _diagnostic(
            "task_preflight.manifest_violation",
            "/manifest_path",
            "tracked_regular_file",
        ),
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_later_unrelated_head_is_not_execution_base(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(fixture.root / "later.txt", "later\n")
    _commit(fixture.root, "later unrelated commit")

    diagnostics = [
        _diagnostic(
            "task_preflight.manifest_violation",
            "/manifest_path",
            "head_is_execution_base",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_missing_baseline_commit(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    fixture.amend(
        replace(
            fixture.manifest,
            baseline_revision="f" * 40,
        )
    )
    diagnostics = [
        _diagnostic(
            "task_preflight.revision_violation",
            "/baseline_revision",
            "commit_exists",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_nonancestor_baseline_commit(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    tree = git_output(
        fixture.root,
        "rev-parse",
        f"{fixture.baseline_commit}^{{tree}}",
    )
    side = git_output(
        fixture.root,
        "commit-tree",
        tree,
        "-m",
        "nonancestor baseline",
    )
    fixture.amend(
        replace(
            fixture.manifest,
            baseline_revision=side,
        )
    )

    diagnostics = [
        _diagnostic(
            "task_preflight.revision_violation",
            "/baseline_revision",
            "ancestor_of_execution_base",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


@pytest.mark.parametrize(
    "mode",
    ["missing", "untracked", "symlink", "digest"],
)
def test_tdd_lock_failures(
    tmp_path: Path,
    mode: str,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    rule = "tracked_regular_file"
    location = "/tdd_path"

    if mode == "missing":
        fixture.amend(
            replace(
                fixture.manifest,
                tdd_path="docs/missing.md",
                tdd_sha256="a" * 64,
            )
        )
    elif mode == "untracked":
        content = "# Untracked TDD\n"
        fixture.amend(
            replace(
                fixture.manifest,
                tdd_path="docs/untracked.md",
                tdd_sha256=_sha256_bytes(content.encode("utf-8")),
            )
        )
        write_fixture_text(fixture.root / "docs" / "untracked.md", content)
        write_fixture_text(
            fixture.root / ".git" / "info" / "exclude",
            "docs/untracked.md\n",
        )
    elif mode == "symlink":
        write_fixture_text(fixture.root / "docs" / "target.md", "# Target\n")
        link = fixture.root / "docs" / "link.md"
        link.symlink_to("target.md")
        fixture.amend(
            replace(
                fixture.manifest,
                tdd_path="docs/link.md",
                tdd_sha256="b" * 64,
            )
        )
    else:
        fixture.amend(
            replace(
                fixture.manifest,
                tdd_sha256="c" * 64,
            )
        )
        rule = "digest_match"
        location = "/tdd_sha256"

    diagnostics = [
        _diagnostic(
            "task_preflight.tdd_violation",
            location,
            rule,
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_current_tdd_byte_mutation_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(fixture.root / fixture.manifest.tdd_path, "# Changed task contract\n")

    diagnostics = [
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
        _diagnostic(
            "task_preflight.tdd_violation",
            "/tdd_sha256",
            "digest_match",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_current_tdd_symbolic_link_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    tdd_path = fixture.root / fixture.manifest.tdd_path
    target = fixture.root / "docs" / "tdd-target.md"
    write_fixture_text(target, tdd_path.read_text())
    fixture.amend()
    tdd_path.unlink()
    tdd_path.symlink_to("tdd-target.md")

    diagnostics = [
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
        _diagnostic(
            "task_preflight.tdd_violation",
            "/tdd_path",
            "tracked_regular_file",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


@pytest.mark.parametrize(
    "mode",
    ["missing", "untracked", "symlink", "digest"],
)
def test_protected_artifact_lock_failures(
    tmp_path: Path,
    mode: str,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    rule = "tracked_regular_file"
    location = "/protected_artifacts/0/path"

    if mode == "missing":
        artifact = Protected(
            "tests/missing.py",
            "d" * 64,
        )
        fixture.amend(
            replace(
                fixture.manifest,
                protected_artifacts=(artifact,),
            )
        )
    elif mode == "untracked":
        content = "EXPECTED = 'untracked'\n"
        artifact = Protected(
            "tests/untracked.py",
            _sha256_bytes(content.encode("utf-8")),
        )
        fixture.amend(
            replace(
                fixture.manifest,
                protected_artifacts=(artifact,),
            )
        )
        write_fixture_text(fixture.root / "tests" / "untracked.py", content)
        write_fixture_text(
            fixture.root / ".git" / "info" / "exclude",
            "tests/untracked.py\n",
        )
    elif mode == "symlink":
        write_fixture_text(
            fixture.root / "tests" / "target.py",
            "EXPECTED = 'target'\n",
        )
        link = fixture.root / "tests" / "link.py"
        link.symlink_to("target.py")
        artifact = Protected("tests/link.py", "e" * 64)
        fixture.amend(
            replace(
                fixture.manifest,
                protected_artifacts=(artifact,),
            )
        )
    else:
        artifact = replace(
            fixture.manifest.protected_artifacts[0],
            sha256="f" * 64,
        )
        fixture.amend(
            replace(
                fixture.manifest,
                protected_artifacts=(artifact,),
            )
        )
        rule = "digest_match"
        location = "/protected_artifacts/0/sha256"

    diagnostics = [
        _diagnostic(
            "task_preflight.protected_artifact_violation",
            location,
            rule,
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_current_protected_artifact_byte_mutation_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    artifact = fixture.manifest.protected_artifacts[0]
    write_fixture_text(fixture.root / artifact.path, "EXPECTED = 'changed'\n")

    diagnostics = [
        _diagnostic(
            "task_preflight.protected_artifact_violation",
            "/protected_artifacts/0/sha256",
            "digest_match",
        ),
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_current_protected_artifact_symbolic_link_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    artifact = fixture.manifest.protected_artifacts[0]
    artifact_path = fixture.root / artifact.path
    target = fixture.root / "tests" / "acceptance-target.py"
    write_fixture_text(target, artifact_path.read_text())
    fixture.amend()
    artifact_path.unlink()
    artifact_path.symlink_to("acceptance-target.py")

    diagnostics = [
        _diagnostic(
            "task_preflight.protected_artifact_violation",
            "/protected_artifacts/0/path",
            "tracked_regular_file",
        ),
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


@pytest.mark.parametrize(
    ("reference", "create_directory"),
    [
        ("docs/missing.md", False),
        ("docs/empty/", True),
    ],
)
def test_reference_path_failures(
    tmp_path: Path,
    reference: str,
    create_directory: bool,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    fixture.amend(
        replace(
            fixture.manifest,
            reference_paths=(reference,),
        )
    )

    if create_directory:
        (fixture.root / "docs" / "empty").mkdir()

    diagnostics = [
        _diagnostic(
            "task_preflight.reference_violation",
            "/reference_paths/0",
            "tracked_file_or_nonempty_directory",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_exact_reference_committed_as_symbolic_link_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    target = fixture.root / "docs" / "reference-target.md"
    link = fixture.root / "docs" / "reference-link.md"
    write_fixture_text(target, "# Reference target\n")
    link.symlink_to("reference-target.md")
    fixture.amend(
        replace(
            fixture.manifest,
            reference_paths=("docs/reference-link.md",),
        )
    )

    diagnostics = [
        _diagnostic(
            "task_preflight.reference_violation",
            "/reference_paths/0",
            "tracked_file_or_nonempty_directory",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_directory_reference_current_symbolic_link_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    reference = fixture.root / "docs" / "reference"
    target = fixture.root / "docs" / "reference-target"
    write_fixture_text(target / "guide.md", "# Target reference\n")
    fixture.amend()
    shutil.rmtree(reference)
    reference.symlink_to("reference-target", target_is_directory=True)

    diagnostics = [
        _diagnostic(
            "task_preflight.reference_violation",
            "/reference_paths/1",
            "tracked_file_or_nonempty_directory",
        ),
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


@pytest.mark.parametrize(
    "allowed_path",
    [MANIFEST_RELATIVE, ".agent/"],
)
def test_allowed_scope_protected_overlap(
    tmp_path: Path,
    allowed_path: str,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    fixture.amend(
        replace(
            fixture.manifest,
            allowed_paths=(allowed_path,),
        )
    )
    diagnostics = [
        _diagnostic(
            "task_preflight.scope_violation",
            "/allowed_paths/0",
            "protected_overlap",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_allowed_path_symbolic_link_ancestor(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    write_fixture_text(fixture.root / "real" / ".keep", "tracked\n")
    (fixture.root / "linked").symlink_to("real")
    fixture.amend(
        replace(
            fixture.manifest,
            allowed_paths=("linked/output.py",),
        )
    )
    diagnostics = [
        _diagnostic(
            "task_preflight.scope_violation",
            "/allowed_paths/0",
            "symlink_ancestor",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


@pytest.mark.parametrize(
    "mode",
    ["missing", "malformed-unrelated", "failed", "multiple"],
)
def test_dependency_receipt_failures(
    tmp_path: Path,
    mode: str,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    receipt_root = fixture.root / ".agent" / "receipts"
    (receipt_root / "h1.json").unlink()

    rule = "leaf_verified_receipt"

    if mode == "malformed-unrelated":
        write_fixture_text(receipt_root / "broken.json", "{not json")
        write_fixture_text(
            receipt_root / "other.json",
            _verified_receipt(task_id="other-task"),
        )
    elif mode == "failed":
        write_fixture_text(
            receipt_root / "failed.json",
            _verified_receipt(result="failed"),
        )
    elif mode == "multiple":
        write_fixture_text(receipt_root / "one.json", _verified_receipt())
        write_fixture_text(receipt_root / "two.json", _verified_receipt())
        rule = "unique_leaf_verified_receipt"

    fixture.amend()
    diagnostics = [
        _diagnostic(
            "task_preflight.dependency_violation",
            "/depends_on/0",
            rule,
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_untracked_matching_dependency_receipt_does_not_count(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    receipt_root = fixture.root / ".agent" / "receipts"
    (receipt_root / "h1.json").unlink()
    fixture.amend()
    write_fixture_text(receipt_root / "untracked.json", _verified_receipt())

    diagnostics = [
        _diagnostic(
            "task_preflight.dependency_violation",
            "/depends_on/0",
            "leaf_verified_receipt",
        ),
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_current_receipt_edit_does_not_override_committed_blob(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    receipt = fixture.root / ".agent" / "receipts" / "h1.json"
    write_fixture_text(receipt, _verified_receipt(result="failed"))
    fixture.amend()
    write_fixture_text(receipt, _verified_receipt())

    diagnostics = [
        _diagnostic(
            "task_preflight.dependency_violation",
            "/depends_on/0",
            "leaf_verified_receipt",
        ),
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_current_receipt_symbolic_link_does_not_override_committed_blob(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    receipt_root = fixture.root / ".agent" / "receipts"
    receipt = receipt_root / "h1.json"
    target = receipt_root / "other.json"
    write_fixture_text(target, _verified_receipt(task_id="other-task"))
    fixture.amend()
    receipt.unlink()
    receipt.symlink_to("other.json")

    diagnostics = [
        _diagnostic(
            "task_preflight.repository_violation",
            "/repository",
            "clean_worktree",
        )
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def test_one_verified_dependency_receipt_passes(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, []),
        exit_code=0,
    )


def test_h1_failure_short_circuits_stage_three(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    fixture.amend(
        replace(
            fixture.manifest,
            task_id="Example_Task",
            allowed_paths=("/absolute",),
        )
    )
    diagnostics = [
        _diagnostic(
            "task_manifest.schema_violation",
            "/task_id",
            "pattern",
        )
    ]
    expected = _stage2_expected(
        fixture,
        diagnostics,
        task_id=None,
    )
    _assert_result(fixture.run(), expected, exit_code=1)


def test_multiple_stage_three_diagnostics_are_stable(
    tmp_path: Path,
) -> None:
    fixture = _create_ready_repo(tmp_path)
    (fixture.root / ".agent" / "receipts" / "h1.json").unlink()
    missing = Protected("tests/missing.py", "1" * 64)
    manifest = replace(
        fixture.manifest,
        baseline_revision="f" * 40,
        tdd_path="docs/missing.md",
        tdd_sha256="2" * 64,
        allowed_paths=(MANIFEST_RELATIVE,),
        reference_paths=("docs/missing-reference.md",),
        protected_artifacts=(missing,),
    )
    fixture.amend(manifest)

    diagnostics = [
        _diagnostic(
            "task_preflight.scope_violation",
            "/allowed_paths/0",
            "protected_overlap",
        ),
        _diagnostic(
            "task_preflight.revision_violation",
            "/baseline_revision",
            "commit_exists",
        ),
        _diagnostic(
            "task_preflight.dependency_violation",
            "/depends_on/0",
            "leaf_verified_receipt",
        ),
        _diagnostic(
            "task_preflight.protected_artifact_violation",
            "/protected_artifacts/0/path",
            "tracked_regular_file",
        ),
        _diagnostic(
            "task_preflight.reference_violation",
            "/reference_paths/0",
            "tracked_file_or_nonempty_directory",
        ),
        _diagnostic(
            "task_preflight.tdd_violation",
            "/tdd_path",
            "tracked_regular_file",
        ),
    ]
    _assert_result(
        fixture.run(),
        _stage3_expected(fixture, diagnostics),
        exit_code=1,
    )


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])

    return roots


def test_product_packages_import_no_devtools() -> None:
    violations = [
        str(path.relative_to(REPO_ROOT))
        for package in (
            "adapters",
            "application",
            "briefing",
            "domain",
            "pipelines",
        )
        for path in sorted((REPO_ROOT / "packages" / package / "src").rglob("*.py"))
        if "kotekomi_devtools" in _import_roots(path)
    ]
    assert violations == []
