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


def test_resume_reuses_initial_branch_evidence_after_a_candidate_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    (repo / ".agent" / "schemas").mkdir(parents=True)
    for name in ("task-manifest-v1.schema.json", "task-manifest-v2.schema.json"):
        shutil.copy2(PROJECT_ROOT / ".agent" / "schemas" / name, repo / ".agent" / "schemas")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    baseline = _git(repo, "rev-parse", "HEAD")
    tdd = repo / "docs" / "leaf.md"
    tdd.parent.mkdir()
    tdd.write_text("# Leaf\n")
    digest = hashlib.sha256(tdd.read_bytes()).hexdigest()
    task_id = derive_task_id("Leaf", digest)
    manifest = repo / ".agent" / "tasks" / f"{task_id}.toml"
    manifest.parent.mkdir()
    manifest.write_text(
        "\n".join(
            [
                "schema_version = 2",
                f'task_id = "{task_id}"',
                'title = "Leaf"',
                'status = "ready_for_terra_high"',
                'series_id = "feature-branch"',
                'task_class = "repository-tooling"',
                'model_profile = "terra-high-v1"',
                f'baseline_revision = "{baseline}"',
                'tdd_path = "docs/leaf.md"',
                f'tdd_sha256 = "{digest}"',
                'goal = "Resume the feature branch."',
                "depends_on = []",
                'allowed_paths = ["packages/devtools"]',
                "reference_paths = []",
                'stop_conditions = ["none"]',
                "",
                "[readiness]",
                'authority = "Leaf TDD"',
                'contract_family = "feature-branch"',
                'dominant_outcome = "Feature branch resume"',
                'failure_policy = "Block invalid Git state."',
                'legacy_disposition = "V1 is historical."',
                'negative_proof = "No direct main run."',
                'public_entry_point = "implement-tdd"',
                'scope_policy = "Feature branch resume."',
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
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "specification")
    specification = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", "main")
    state = tmp_path / "state"
    first = _cli(repo, state, "implement-tdd", "docs/leaf.md")
    assert first.returncode == 0, first.stderr
    run = json.loads(first.stdout)["implementation_run_id"]
    _git(repo, "switch", f"feature/{task_id}")
    (repo / "candidate.txt").write_text("candidate\n")
    _git(repo, "add", "candidate.txt")
    _git(repo, "commit", "-m", "candidate")
    _git(repo, "push", "origin", f"feature/{task_id}")

    resumed = _cli(repo, state, "implement-tdd", "docs/leaf.md")

    assert resumed.returncode == 0, resumed.stderr
    payload = json.loads(resumed.stdout)
    assert payload["implementation_run_id"] == run
    assert payload["next_action"] == "produce_candidate_lifecycle_evidence"
    branch = state / "experiments" / task_id / "runs" / run / "git" / "feature-branch.json"
    assert json.loads(branch.read_text())["remote_revision"] == specification
