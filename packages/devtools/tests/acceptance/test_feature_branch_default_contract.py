from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from kotekomi_devtools.tdd_binding import derive_task_id

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def _cli(repo: Path, state: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            *args,
            "--state-root",
            str(state),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_manifest(repo: Path, *, version: int, baseline: str) -> tuple[str, Path]:
    tdd = repo / "docs" / "leaf.md"
    tdd.parent.mkdir(parents=True, exist_ok=True)
    tdd.write_text("# Leaf\n")
    tdd_sha256 = hashlib.sha256(tdd.read_bytes()).hexdigest()
    task_id = derive_task_id("Leaf", tdd_sha256)
    manifest = repo / ".agent" / "tasks" / f"{task_id}.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "\n".join(
            [
                f"schema_version = {version}",
                f'task_id = "{task_id}"',
                'title = "Leaf"',
                'status = "ready_for_terra_high"',
                'series_id = "feature-branch"',
                'task_class = "repository-tooling"',
                'model_profile = "terra-high-v1"',
                f'baseline_revision = "{baseline}"',
                'tdd_path = "docs/leaf.md"',
                f'tdd_sha256 = "{tdd_sha256}"',
                'goal = "Create the feature branch."',
                "depends_on = []",
                'allowed_paths = ["packages/devtools"]',
                "reference_paths = []",
                'stop_conditions = ["none"]',
                "",
                "[readiness]",
                'authority = "Leaf TDD"',
                'contract_family = "feature-branch"',
                'dominant_outcome = "Feature branch"',
                'failure_policy = "Block invalid Git state."',
                'legacy_disposition = "V1 is historical."',
                'negative_proof = "No direct main run."',
                'public_entry_point = "implement-tdd"',
                'scope_policy = "Feature branch creation."',
                'side_effect_boundary = "Git refs and state evidence."',
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
                f'sha256 = "{tdd_sha256}"',
                "",
                "[[acceptance]]",
                'id = "leaf"',
                'argv = ["uv", "run", "pytest"]',
                "timeout_seconds = 120",
                'profile = "portable-local"',
                "",
            ]
        )
    )
    return task_id, manifest


def _repo(tmp_path: Path, *, version: int) -> tuple[Path, str, str, Path]:
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
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    task_id, manifest = _write_manifest(repo, version=version, baseline=base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "specification")
    specification = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", "main")
    return repo, task_id, specification, manifest


def test_v2_run_creates_and_pushes_a_feature_branch(tmp_path: Path) -> None:
    repo, task_id, specification, _ = _repo(tmp_path, version=2)
    state = tmp_path / "state"

    result = _cli(repo, state, "implement-tdd", "docs/leaf.md")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready"
    assert payload["feature_branch"] == f"feature/{task_id}"
    assert _git(repo, "rev-parse", f"feature/{task_id}") == specification
    assert _git(repo, "rev-parse", f"origin/feature/{task_id}") == specification
    root = state / "experiments" / task_id / "runs" / payload["implementation_run_id"]
    assert (
        json.loads((root / "git" / "specification-revision.json").read_text())[
            "specification_revision"
        ]
        == specification
    )
    assert (
        json.loads((root / "git" / "feature-branch.json").read_text())["remote_revision"]
        == specification
    )


def test_candidate_must_equal_the_remote_feature_tip(tmp_path: Path) -> None:
    repo, task_id, _, _ = _repo(tmp_path, version=2)
    state = tmp_path / "state"
    run = json.loads(_cli(repo, state, "implement-tdd", "docs/leaf.md").stdout)[
        "implementation_run_id"
    ]
    _git(repo, "checkout", f"feature/{task_id}")
    (repo / "candidate.txt").write_text("candidate\n")
    _git(repo, "add", "candidate.txt")
    _git(repo, "commit", "-m", "candidate")
    candidate = _git(repo, "rev-parse", "HEAD")

    blocked = _cli(
        repo,
        state,
        "record-candidate-commit",
        "--commit",
        candidate,
        "--task-id",
        task_id,
        "--run",
        run,
    )

    assert blocked.returncode == 2
    _git(repo, "push", "origin", f"feature/{task_id}")
    accepted = _cli(
        repo,
        state,
        "record-candidate-commit",
        "--commit",
        candidate,
        "--task-id",
        task_id,
        "--run",
        run,
    )
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["commit_sha"] == candidate


def test_v1_manifest_is_historical_and_creates_no_feature_branch(tmp_path: Path) -> None:
    repo, task_id, _, _ = _repo(tmp_path, version=1)

    result = _cli(repo, tmp_path / "state", "implement-tdd", "docs/leaf.md")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "historical"
    assert _git(repo, "branch", "--list", f"feature/{task_id}") == ""
