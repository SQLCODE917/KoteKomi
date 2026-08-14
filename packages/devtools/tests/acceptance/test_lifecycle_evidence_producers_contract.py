from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK = "task"
RUN = "task-run-001"


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
            "--task-id",
            TASK,
            "--run",
            RUN,
            "--state-root",
            str(state),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "checkout", "-b", "candidate")
    (repo / "candidate.txt").write_text("candidate\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "candidate")
    candidate = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    (repo / "main.txt").write_text("main\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main")
    _git(repo, "merge", "--no-ff", "candidate", "-m", "merge candidate")
    return repo, candidate, _git(repo, "rev-parse", "HEAD")


def test_lifecycle_producers_write_canonical_records_and_events(tmp_path: Path) -> None:
    repo, candidate, merge = _repo(tmp_path)
    state = tmp_path / "state"
    candidate_ci = tmp_path / "candidate-ci.json"
    candidate_ci.write_text(
        json.dumps({"schema_version": 1, "conclusion": "failure", "head_sha": candidate}) + "\n"
    )
    main_ci = tmp_path / "main-ci.json"
    main_ci.write_text(
        json.dumps({"schema_version": 1, "conclusion": "success", "head_sha": merge}) + "\n"
    )

    commands = [
        ("record-candidate-commit", "--commit", candidate),
        ("record-candidate-ci", "--ci-result", str(candidate_ci)),
        ("record-main-merge", "--merge", merge),
        ("record-main-ci", "--ci-result", str(main_ci)),
        ("record-branch-cleanup", "--branch", "candidate"),
    ]
    for command in commands:
        result = _cli(repo, state, *command)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["schema_version"] == 1

    root = state / "experiments" / TASK / "runs" / RUN
    assert json.loads((root / "ci" / "candidate.json").read_text())["conclusion"] == "failure"
    assert json.loads((root / "cleanup" / "branch-cleanup.json").read_text())[
        "remaining_branches"
    ] == ["candidate"]
    assert len((root / "evidence" / "events.jsonl").read_text().splitlines()) == 5
    assert (
        hashlib.sha256(candidate_ci.read_bytes()).hexdigest()
        == json.loads((root / "ci" / "candidate.json").read_text())["ci_result_sha256"]
    )


def test_candidate_root_commit_and_duplicate_cleanup_block_before_writing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "root.txt").write_text("root\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "root")
    state = tmp_path / "state"
    root = _git(repo, "rev-parse", "HEAD")
    assert _cli(repo, state, "record-candidate-commit", "--commit", root).returncode == 2
    assert (
        _cli(repo, state, "record-branch-cleanup", "--branch", "x", "--branch", "x").returncode == 2
    )
    assert not (state / "experiments" / TASK / "runs" / RUN).exists()
