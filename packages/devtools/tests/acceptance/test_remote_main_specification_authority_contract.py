from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from kotekomi_devtools.tdd_binding import derive_task_id

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _cli(repo: Path, state: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            *arguments,
            "--state-root",
            str(state),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _manifest(task_id: str, digest: str, baseline: str) -> str:
    return "\n".join(
        [
            "schema_version = 2",
            f'task_id = "{task_id}"',
            'title = "Leaf"',
            'status = "ready_for_terra_high"',
            'series_id = "remote-main"',
            'task_class = "repository-tooling"',
            'model_profile = "terra-high-v1"',
            f'baseline_revision = "{baseline}"',
            'tdd_path = "docs/leaf.md"',
            f'tdd_sha256 = "{digest}"',
            'goal = "Test remote main specification authority."',
            "depends_on = []",
            'allowed_paths = ["packages/devtools"]',
            "reference_paths = []",
            'stop_conditions = ["none"]',
            "",
            "[readiness]",
            'authority = "Leaf TDD"',
            'contract_family = "remote-main"',
            'dominant_outcome = "Remote specification"',
            'failure_policy = "Block invalid remote state."',
            'legacy_disposition = "None."',
            'negative_proof = "Caller checkout has no authority."',
            'public_entry_point = "implement-tdd"',
            'scope_policy = "Remote state only."',
            'side_effect_boundary = "Feature refs and state evidence."',
            "unresolved_decisions = []",
            "",
            "[budget]",
            "maximum_production_files = 1",
            "maximum_test_files = 1",
            "maximum_production_diff_lines = 1",
            "",
            "[[protected_artifacts]]",
            'kind = "leaf-tdd"',
            'path = "docs/leaf.md"',
            f'sha256 = "{digest}"',
            "",
            "[[acceptance]]",
            'id = "leaf"',
            'argv = ["uv", "run", "pytest"]',
            "timeout_seconds = 120",
            'profile = "portable-local"',
            "",
        ]
    )


def _repository(tmp_path: Path, *, push_manifest: bool = True) -> tuple[Path, str, str, bytes]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / ".agent" / "schemas").mkdir(parents=True)
    for schema in ("task-manifest-v1.schema.json", "task-manifest-v2.schema.json"):
        shutil.copy2(PROJECT_ROOT / ".agent" / "schemas" / schema, repo / ".agent" / "schemas")
    tdd = repo / "docs" / "leaf.md"
    tdd.parent.mkdir()
    tdd.write_text("# Leaf\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    baseline = _git(repo, "rev-parse", "HEAD")
    digest = hashlib.sha256(tdd.read_bytes()).hexdigest()
    task_id = derive_task_id("Leaf", digest)
    manifest_bytes = _manifest(task_id, digest, baseline).encode("utf-8")
    manifest = repo / ".agent" / "tasks" / f"{task_id}.toml"
    manifest.parent.mkdir()
    manifest.write_bytes(manifest_bytes)
    if push_manifest:
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "specification")
    else:
        _git(repo, "reset", "--", manifest.relative_to(repo).as_posix())
    _git(repo, "push", "-u", "origin", "main")
    return repo, task_id, _git(repo, "rev-parse", "HEAD"), manifest_bytes


def test_v2_uses_remote_main_snapshot_from_a_dirty_feature_worktree(tmp_path: Path) -> None:
    repo, task_id, specification, remote_manifest = _repository(tmp_path)
    state = tmp_path / "state"
    _git(repo, "checkout", "-b", "caller")
    (repo / "caller-note.txt").write_text("dirty\n")
    local_manifest = repo / ".agent" / "tasks" / f"{task_id}.toml"
    local_manifest.write_text("schema_version = 2\n")

    first = _cli(repo, state, "implement-tdd", "docs/leaf.md")

    assert first.returncode == 0, first.stderr
    payload = json.loads(first.stdout)
    run = payload["implementation_run_id"]
    run_root = state / "experiments" / task_id / "runs" / run
    assert (run_root / "spec" / "task-manifest.toml").read_bytes() == remote_manifest
    specification_path = run_root / "git" / "specification-revision.json"
    specification_record = json.loads(specification_path.read_text())
    assert specification_record == {
        "diagnostics": [],
        "manifest_sha256": hashlib.sha256(remote_manifest).hexdigest(),
        "schema_version": 1,
        "specification_revision": specification,
    }
    assert _git(repo, "rev-parse", f"origin/feature/{task_id}") == specification

    _git(repo, "checkout", "main")
    (repo / "later.txt").write_text("later\n")
    _git(repo, "add", "later.txt")
    _git(repo, "commit", "-m", "later main update")
    _git(repo, "push", "origin", "main")
    _git(repo, "checkout", "caller")

    reused = _cli(repo, state, "implement-tdd", "docs/leaf.md")

    assert reused.returncode == 0, reused.stderr
    assert json.loads(reused.stdout)["implementation_run_id"] == run
    assert json.loads((run_root / "git" / "specification-revision.json").read_text()) == (
        specification_record
    )
    assert _git(repo, "rev-parse", f"origin/feature/{task_id}") == specification


def test_remote_specification_failure_blocks_before_v2_manifest_evidence(tmp_path: Path) -> None:
    repo, task_id, _, _ = _repository(tmp_path, push_manifest=False)
    state = tmp_path / "state"

    result = _cli(repo, state, "implement-tdd", "docs/leaf.md")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "workflow.remote_specification_invalid"
    index_path = (
        state
        / "experiments"
        / task_id
        / "runs"
        / payload["implementation_run_id"]
        / "evidence"
        / "index.json"
    )
    index = json.loads(index_path.read_text())
    assert [entry["evidence_type"] for entry in index["entries"]] == ["tdd_binding"]
