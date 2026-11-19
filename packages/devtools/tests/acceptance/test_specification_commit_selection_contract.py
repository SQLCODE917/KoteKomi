from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from kotekomi_devtools.tdd_binding import derive_task_id

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BRANCH = "spec/feature"


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


def _write_manifest(repo: Path, *, baseline: str) -> tuple[str, Path]:
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
                "schema_version = 2",
                f'task_id = "{task_id}"',
                'title = "Leaf"',
                'status = "ready_for_terra_high"',
                'series_id = "specification-commit-selection"',
                'task_class = "repository-tooling"',
                'model_profile = "terra-high-v1"',
                f'baseline_revision = "{baseline}"',
                'tdd_path = "docs/leaf.md"',
                f'tdd_sha256 = "{tdd_sha256}"',
                'goal = "Exercise specification commit selection."',
                "depends_on = []",
                'allowed_paths = ["docs/leaf.md", ".agent/tasks"]',
                "reference_paths = []",
                'stop_conditions = ["none"]',
                "",
                "[readiness]",
                'authority = "Leaf TDD"',
                'contract_family = "specification-commit-selection"',
                'dominant_outcome = "Pinned specification commit"',
                'failure_policy = "Block invalid specification input."',
                'legacy_disposition = "The main start path remains."',
                'negative_proof = "A mismatched TDD blocks."',
                'public_entry_point = "implement-tdd"',
                'scope_policy = "Specification commit selection."',
                'side_effect_boundary = "State evidence and existing branch refs."',
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


def _repo(tmp_path: Path) -> tuple[Path, str, str, Path]:
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
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "checkout", "-b", BRANCH)
    task_id, manifest = _write_manifest(repo, baseline=base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "specification")
    specification = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", BRANCH)
    return repo, task_id, specification, manifest


def _specification_record(state: Path, task_id: str, run_id: str) -> Path:
    return state / "experiments" / task_id / "runs" / run_id / "git" / "specification-revision.json"


def test_specification_commit_selection_starts_on_existing_branch(tmp_path: Path) -> None:
    repo, task_id, specification, _ = _repo(tmp_path)
    state = tmp_path / "state"

    blocked = _cli(repo, state, "implement-tdd", "docs/leaf.md")

    assert blocked.returncode == 1
    blocked_payload = json.loads(blocked.stdout)
    assert blocked_payload["status"] == "blocked"
    assert blocked_payload["diagnostics"][0]["code"] == "workflow.specification_invalid"
    assert "specification requires clean current main" in blocked_payload["diagnostics"][0]["rule"]
    run_id = blocked_payload["implementation_run_id"]
    run_record_path = state / "experiments" / task_id / "runs" / run_id / "run.json"
    run_record = json.loads(run_record_path.read_text())
    assert run_record["status"] == "blocked"
    assert run_record["diagnostics"] == blocked_payload["diagnostics"]

    accepted = _cli(
        repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", specification
    )

    assert accepted.returncode == 0, accepted.stderr
    payload = json.loads(accepted.stdout)
    assert payload["status"] == "ready"
    assert payload["feature_branch"] == BRANCH
    assert payload["implementation_run_id"] == run_id
    specification_record = json.loads(_specification_record(state, task_id, run_id).read_text())
    assert specification_record["specification_revision"] == specification
    feature_record = json.loads(
        (
            state / "experiments" / task_id / "runs" / run_id / "git" / "feature-branch.json"
        ).read_text()
    )
    assert feature_record["branch"] == BRANCH
    assert feature_record["specification_revision"] == specification
    assert feature_record["local_revision"] == specification
    assert feature_record["remote_revision"] == specification
    run_record = json.loads(run_record_path.read_text())
    assert run_record["status"] == "active"
    assert run_record["diagnostics"] == []


def test_specification_commit_pin_survives_implementation_push(tmp_path: Path) -> None:
    repo, task_id, specification, _ = _repo(tmp_path)
    state = tmp_path / "state"

    first = _cli(
        repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", specification
    )
    assert first.returncode == 0, first.stderr
    run_id = json.loads(first.stdout)["implementation_run_id"]
    record_path = _specification_record(state, task_id, run_id)
    pinned = record_path.read_bytes()

    (repo / "implementation.txt").write_text("implementation\n")
    _git(repo, "add", "implementation.txt")
    _git(repo, "commit", "-m", "implementation")
    _git(repo, "push", "origin", BRANCH)

    second = _cli(
        repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", specification
    )

    assert second.returncode == 0, second.stderr
    second_payload = json.loads(second.stdout)
    assert second_payload["status"] == "ready"
    assert second_payload["implementation_run_id"] == run_id
    assert record_path.read_bytes() == pinned
    assert json.loads(record_path.read_text())["specification_revision"] == specification


def test_specification_commit_selection_blocks_mismatched_tdd(tmp_path: Path) -> None:
    repo, task_id, _, _ = _repo(tmp_path)
    state = tmp_path / "state"
    tdd = repo / "docs" / "leaf.md"
    original = tdd.read_bytes()
    tdd.write_text("# Leaf\n\nMismatched specification.\n")
    _git(repo, "add", "docs/leaf.md")
    _git(repo, "commit", "-m", "mismatched tdd")
    mismatched = _git(repo, "rev-parse", "HEAD")
    tdd.write_bytes(original)
    _git(repo, "add", "docs/leaf.md")
    _git(repo, "commit", "-m", "restore tdd")
    _git(repo, "push", "origin", BRANCH)

    blocked = _cli(
        repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", mismatched
    )

    assert blocked.returncode == 1
    payload = json.loads(blocked.stdout)
    assert payload["status"] == "blocked"
    assert payload["diagnostics"][0]["code"] == "workflow.specification_invalid"
    assert "specification TDD differs from the bound TDD" in payload["diagnostics"][0]["rule"]
    run_id = payload["implementation_run_id"]
    assert not _specification_record(state, task_id, run_id).exists()
    run_record_path = state / "experiments" / task_id / "runs" / run_id / "run.json"
    run_record = json.loads(run_record_path.read_text())
    assert run_record["status"] == "blocked"
    assert run_record["diagnostics"] == payload["diagnostics"]

    repeated = _cli(
        repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", mismatched
    )

    assert repeated.returncode == 1
    repeated_payload = json.loads(repeated.stdout)
    assert repeated_payload["implementation_run_id"] == run_id
    assert repeated_payload["status"] == "blocked"
    repeated_record = json.loads(run_record_path.read_text())
    assert repeated_record["status"] == "blocked"
