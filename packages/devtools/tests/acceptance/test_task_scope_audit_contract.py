from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SOURCE_MANIFEST = PROJECT_ROOT / ".agent/tasks/harness-04-task-scope-audit.toml"
SCHEMA_SOURCE = PROJECT_ROOT / ".agent/schemas/task-manifest-v1.schema.json"
PYTHONPATH = str(PROJECT_ROOT / "packages/devtools/src")
ENTRYPOINT = (
    "from kotekomi_devtools.cli import entrypoint; "
    "raise SystemExit(entrypoint())"
)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run(
    args: list[str],
    cwd: Path,
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-c", ENTRYPOINT, *args],
        cwd=cwd,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed: {args}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    return result


def _require_scope_audit() -> None:
    result = _run(["--help"], PROJECT_ROOT)

    if result.returncode != 0:
        pytest.skip("kotekomi-agent help is unavailable")

    if "scope-audit" not in result.stdout:
        pytest.skip("scope-audit command is not implemented yet")


def _git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _index_sha(repo: Path) -> str:
    index = repo / ".git/index"

    if not index.exists():
        return ""

    return hashlib.sha256(index.read_bytes()).hexdigest()


def _status(repo: Path) -> str:
    return _git(repo, ["status", "--short"])


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, ["add", "."])
    _git(repo, ["commit", "-m", message])
    return _git(repo, ["rev-parse", "HEAD"])


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    _require_scope_audit()

    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, ["init"])
    _git(repo, ["config", "user.email", "scope@example.test"])
    _git(repo, ["config", "user.name", "Scope Audit Test"])

    schema_target = repo / ".agent/schemas/task-manifest-v1.schema.json"
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCHEMA_SOURCE, schema_target)

    _write(
        repo / "packages/devtools/src/kotekomi_devtools/cli.py",
        "print('cli')\n",
    )
    _write(
        repo / "packages/devtools/src/kotekomi_devtools/task_scope.py",
        "VALUE = 1\n",
    )
    _write(
        repo / "packages/devtools/tests/unit/test_scope.py",
        "def test_scope() -> None:\n    assert True\n",
    )
    _write(repo / "packages/devtools/AGENTS.md", "agent rules\n")
    _write(repo / "docs/example-tdd.md", "example tdd\n")
    _write(
        repo / "packages/devtools/tests/acceptance/test_task_scope.py",
        "def test_contract() -> None:\n    assert True\n",
    )
    _write(
        repo / ".agent/receipts/bootstrap/example.json",
        json.dumps({"result": "ok"}, sort_keys=True) + "\n",
    )

    base = _commit_all(repo, "base")
    _write_manifest(repo, base)
    _commit_all(repo, "manifest")

    base_with_manifest = _git(repo, ["rev-parse", "HEAD"])
    _write_manifest(repo, base_with_manifest)
    _commit_all(repo, "manifest baseline")

    return repo, _git(repo, ["rev-parse", "HEAD"])


def _load_source_manifest() -> dict[str, Any]:
    return tomllib.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))


def _manifest_for(repo: Path, baseline: str) -> dict[str, Any]:
    manifest = _load_source_manifest()
    manifest["baseline_revision"] = baseline
    manifest["tdd_path"] = "docs/example-tdd.md"
    manifest["tdd_sha256"] = _sha256(repo / "docs/example-tdd.md")
    manifest["allowed_paths"] = [
        "packages/devtools/src/kotekomi_devtools/cli.py",
        "packages/devtools/src/kotekomi_devtools/task_scope.py",
        "packages/devtools/tests/unit/",
    ]
    manifest["reference_paths"] = [
        "packages/devtools/src/kotekomi_devtools/task_budget.py"
    ]
    manifest["protected_artifacts"] = [
        {
            "kind": "json-schema",
            "path": ".agent/schemas/task-manifest-v1.schema.json",
            "sha256": _sha256(
                repo / ".agent/schemas/task-manifest-v1.schema.json"
            ),
        },
        {
            "kind": "leaf-tdd",
            "path": "docs/example-tdd.md",
            "sha256": _sha256(repo / "docs/example-tdd.md"),
        },
        {
            "kind": "acceptance-test",
            "path": "packages/devtools/tests/acceptance/test_task_scope.py",
            "sha256": _sha256(
                repo / "packages/devtools/tests/acceptance/test_task_scope.py"
            ),
        },
        {
            "kind": "agent-instructions",
            "path": "packages/devtools/AGENTS.md",
            "sha256": _sha256(repo / "packages/devtools/AGENTS.md"),
        },
        {
            "kind": "fixture",
            "path": ".agent/receipts/bootstrap/example.json",
            "sha256": _sha256(repo / ".agent/receipts/bootstrap/example.json"),
        },
    ]
    return manifest


def _write_manifest(repo: Path, baseline: str) -> Path:
    manifest = _manifest_for(repo, baseline)
    path = repo / ".agent/tasks/example-scope-audit.toml"
    _write(path, _render_manifest(manifest))
    return path


def _render_manifest(manifest: dict[str, Any]) -> str:
    top_keys = [
        "schema_version",
        "task_id",
        "title",
        "status",
        "series_id",
        "task_class",
        "model_profile",
        "baseline_revision",
        "tdd_path",
        "tdd_sha256",
        "goal",
        "depends_on",
        "allowed_paths",
        "reference_paths",
        "stop_conditions",
    ]

    lines: list[str] = []

    for key in top_keys:
        lines.append(f"{key} = {_toml_value(manifest[key])}")

    lines.append("")

    for item in cast(list[dict[str, Any]], manifest["protected_artifacts"]):
        lines.append("[[protected_artifacts]]")
        for key in ["kind", "path", "sha256"]:
            lines.append(f"{key} = {_toml_value(item[key])}")
        lines.append("")

    for item in cast(list[dict[str, Any]], manifest["acceptance"]):
        lines.append("[[acceptance]]")
        for key in item:
            lines.append(f"{key} = {_toml_value(item[key])}")
        lines.append("")

    lines.append("[readiness]")
    for key, value in cast(dict[str, Any], manifest["readiness"]).items():
        lines.append(f"{key} = {_toml_value(value)}")

    lines.append("")
    lines.append("[budget]")
    for key, value in cast(dict[str, Any], manifest["budget"]).items():
        lines.append(f"{key} = {_toml_value(value)}")

    return "\n".join(lines) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, list):
        items = cast(list[Any], value)
        return "[" + ", ".join(_toml_value(item) for item in items) + "]"

    raise TypeError(f"Unsupported TOML value: {value!r}")


def _scope_audit(
    repo: Path,
    manifest: Path,
    *args: str,
) -> tuple[int, dict[str, Any]]:
    _require_scope_audit()

    result = _run(["scope-audit", str(manifest), *args], repo)

    if not result.stdout:
        raise AssertionError(f"No stdout. stderr:\n{result.stderr}")

    payload = json.loads(result.stdout)
    return result.returncode, cast(dict[str, Any], payload)


def _changed_paths(payload: dict[str, Any]) -> list[str]:
    changed_paths = cast(list[dict[str, Any]], payload["changed_paths"])
    return [str(item["path"]) for item in changed_paths]


def _diagnostics(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], payload["diagnostics"])



def test_scope_audit_help_reports_command() -> None:
    result = _run(["--help"], PROJECT_ROOT)

    if "scope-audit" not in result.stdout:
        pytest.skip("scope-audit command is not implemented yet")

    help_result = _run(["scope-audit", "--help"], PROJECT_ROOT)

    assert help_result.returncode == 0
    assert "scope-audit" in help_result.stdout
    assert "--base" in help_result.stdout
    assert "--head" in help_result.stdout
    assert "--worktree" in help_result.stdout


def test_revision_allowed_change_is_clean(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(
        repo / "packages/devtools/src/kotekomi_devtools/task_scope.py",
        "VALUE = 2\n",
    )
    head = _commit_all(repo, "allowed change")

    code, payload = _scope_audit(repo, manifest, "--base", base, "--head", head)

    assert code == 0
    assert payload["status"] == "clean"
    assert payload["mode"] == "revision"
    assert payload["base_revision"] == base
    assert payload["head_revision"] == head
    assert _changed_paths(payload) == [
        "packages/devtools/src/kotekomi_devtools/task_scope.py"
    ]
    assert payload["changed_paths"][0]["allowed"] is True
    assert payload["changed_paths"][0]["protected"] is False
    assert payload["diagnostics"] == []


def test_no_changes_is_clean(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    code, payload = _scope_audit(repo, manifest, "--base", base, "--head", base)

    assert code == 0
    assert payload["status"] == "clean"
    assert payload["changed_paths"] == []
    assert payload["diagnostics"] == []


def test_revision_disallowed_change_reports_scope_violation(
    tmp_path: Path,
) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(repo / "README.md", "outside scope\n")
    head = _commit_all(repo, "outside scope")

    code, payload = _scope_audit(repo, manifest, "--base", base, "--head", head)

    assert code == 1
    assert payload["status"] == "scope_violation"
    assert _changed_paths(payload) == ["README.md"]

    diagnostics = _diagnostics(payload)
    assert diagnostics == [
        {
            "code": "task_scope.scope_violation",
            "location": "/changed_paths/0/path",
            "rule": "allowed_path",
        }
    ]


def test_revision_protected_change_reports_protected_violation(
    tmp_path: Path,
) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(repo / "packages/devtools/AGENTS.md", "changed rules\n")
    head = _commit_all(repo, "protected change")

    code, payload = _scope_audit(repo, manifest, "--base", base, "--head", head)

    assert code == 1
    assert payload["status"] == "protected_artifact_violation"

    protected = [
        item
        for item in payload["protected_artifacts"]
        if item["path"] == "packages/devtools/AGENTS.md"
    ][0]

    assert protected["exists"] is True
    assert protected["changed"] is True
    assert protected["actual_sha256"] != protected["expected_sha256"]

    codes = {item["code"] for item in _diagnostics(payload)}
    assert "task_scope.protected_artifact_changed" in codes
    assert "task_scope.protected_artifact_digest_mismatch" in codes


def test_revision_protected_delete_reports_missing(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    (repo / "packages/devtools/AGENTS.md").unlink()
    head = _commit_all(repo, "delete protected")

    code, payload = _scope_audit(repo, manifest, "--base", base, "--head", head)

    assert code == 1
    assert payload["status"] == "protected_artifact_violation"

    protected = [
        item
        for item in payload["protected_artifacts"]
        if item["path"] == "packages/devtools/AGENTS.md"
    ][0]

    assert protected["exists"] is False
    assert protected["changed"] is True
    assert protected["actual_sha256"] is None

    codes = {item["code"] for item in _diagnostics(payload)}
    assert "task_scope.protected_artifact_missing" in codes
    assert "task_scope.protected_artifact_changed" in codes


def test_manifest_digest_mismatch_without_diff_reports_violation(
    tmp_path: Path,
) -> None:
    repo, base = _init_repo(tmp_path)
    manifest_path = repo / ".agent/tasks/example-scope-audit.toml"
    manifest = _manifest_for(repo, base)
    manifest["protected_artifacts"][0]["sha256"] = "0" * 64
    _write(manifest_path, _render_manifest(manifest))

    code, payload = _scope_audit(
        repo,
        manifest_path,
        "--base",
        base,
        "--head",
        base,
    )

    assert code == 1
    assert payload["status"] == "protected_artifact_violation"

    diagnostics = _diagnostics(payload)
    assert diagnostics == [
        {
            "code": "task_scope.protected_artifact_digest_mismatch",
            "location": "/protected_artifacts/0/actual_sha256",
            "rule": "protected_artifact_digest",
        }
    ]


def test_worktree_tracked_modification_is_read_only(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(
        repo / "packages/devtools/src/kotekomi_devtools/task_scope.py",
        "VALUE = 3\n",
    )

    before_index = _index_sha(repo)
    before_status = _status(repo)

    code, payload = _scope_audit(repo, manifest, "--base", base, "--worktree")

    assert code == 0
    assert payload["status"] == "clean"
    assert payload["mode"] == "worktree"
    assert payload["head_revision"] == "WORKTREE"
    assert _index_sha(repo) == before_index
    assert _status(repo) == before_status


def test_worktree_untracked_allowed_is_clean_and_read_only(
    tmp_path: Path,
) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(
        repo / "packages/devtools/tests/unit/test_new.py",
        "def test_new():\n    assert True\n",
    )

    before_index = _index_sha(repo)
    before_status = _status(repo)

    code, payload = _scope_audit(repo, manifest, "--base", base, "--worktree")

    assert code == 0
    assert payload["status"] == "clean"
    assert "packages/devtools/tests/unit/test_new.py" in _changed_paths(payload)
    assert _index_sha(repo) == before_index
    assert _status(repo) == before_status


def test_worktree_untracked_disallowed_reports_scope_violation_and_read_only(
    tmp_path: Path,
) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(repo / "notes.txt", "outside\n")

    before_index = _index_sha(repo)
    before_status = _status(repo)

    code, payload = _scope_audit(repo, manifest, "--base", base, "--worktree")

    assert code == 1
    assert payload["status"] == "scope_violation"
    assert "notes.txt" in _changed_paths(payload)
    assert _index_sha(repo) == before_index
    assert _status(repo) == before_status


def test_worktree_protected_modification_reports_violation(
    tmp_path: Path,
) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(repo / "packages/devtools/AGENTS.md", "changed in worktree\n")

    code, payload = _scope_audit(repo, manifest, "--base", base, "--worktree")

    assert code == 1
    assert payload["status"] == "protected_artifact_violation"

    codes = {item["code"] for item in _diagnostics(payload)}
    assert "task_scope.protected_artifact_changed" in codes
    assert "task_scope.protected_artifact_digest_mismatch" in codes


def test_diagnostics_are_sorted(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(repo / "z-outside.txt", "z\n")
    _write(repo / "packages/devtools/AGENTS.md", "changed\n")
    head = _commit_all(repo, "multiple violations")

    code, payload = _scope_audit(repo, manifest, "--base", base, "--head", head)

    assert code == 1

    diagnostics = _diagnostics(payload)
    keys = [
        (item["location"], item["code"], item["rule"])
        for item in diagnostics
    ]
    assert keys == sorted(keys)


def test_changed_paths_and_protected_artifacts_are_sorted(
    tmp_path: Path,
) -> None:
    repo, base = _init_repo(tmp_path)
    manifest = repo / ".agent/tasks/example-scope-audit.toml"

    _write(repo / "zeta.txt", "z\n")
    _write(repo / "alpha.txt", "a\n")
    head = _commit_all(repo, "sort paths")

    code, payload = _scope_audit(repo, manifest, "--base", base, "--head", head)

    assert code == 1
    assert _changed_paths(payload) == sorted(_changed_paths(payload))

    protected_paths = [
        item["path"]
        for item in payload["protected_artifacts"]
    ]
    assert protected_paths == sorted(protected_paths)
