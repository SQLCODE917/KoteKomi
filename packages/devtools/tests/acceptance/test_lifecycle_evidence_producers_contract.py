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
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
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
    _git(repo, "push", "-u", "origin", "main")
    return repo, candidate, _git(repo, "rev-parse", "HEAD")


def _direct_repo(tmp_path: Path, *, push: bool = True) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", "main")
    (repo / "direct.txt").write_text("direct\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "direct")
    direct = _git(repo, "rev-parse", "HEAD")
    if push:
        _git(repo, "push", "origin", "main")
    return repo, base, direct


def _octopus_repo(tmp_path: Path) -> Path:
    repo, base, _ = _direct_repo(tmp_path)
    _git(repo, "checkout", "-b", "first", base)
    (repo / "first.txt").write_text("first\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "first")
    _git(repo, "checkout", "-b", "second", base)
    (repo / "second.txt").write_text("second\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", "first", "second", "-m", "octopus")
    _git(repo, "push", "origin", "main")
    return repo


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
        ("record-main-promotion", "--commit", merge),
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


def test_main_promotion_records_direct_commit_and_report_copies(tmp_path: Path) -> None:
    repo, base, direct = _direct_repo(tmp_path)
    state = tmp_path / "state"
    output = tmp_path / "reports" / "promotion.json"
    markdown = tmp_path / "reports" / "promotion.md"

    result = _cli(
        repo,
        state,
        "record-main-promotion",
        "--commit",
        direct,
        "--output",
        str(output),
        "--markdown",
        str(markdown),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "schema_version": 1,
        "promotion_kind": "direct",
        "promotion_commit": direct,
        "parent_commit": base,
        "verified_parent_commit": None,
        "diagnostics": [],
    }
    root = state / "experiments" / TASK / "runs" / RUN
    canonical = root / "git" / "main-promotion.json"
    assert json.loads(canonical.read_text()) == payload
    assert json.loads(output.read_text()) == payload
    assert direct in markdown.read_text()
    index = json.loads((root / "evidence" / "index.json").read_text())
    assert index["entries"][-1]["evidence_type"] == "main_promotion"
    assert index["entries"][-1]["path"] == canonical.relative_to(state).as_posix()
    assert len((root / "evidence" / "events.jsonl").read_text().splitlines()) == 1


def test_main_promotion_rejects_invalid_topology_and_origin_state(tmp_path: Path) -> None:
    root_repo = tmp_path / "root-repo"
    root_repo.mkdir()
    _git(root_repo, "init", "--initial-branch", "main")
    _git(root_repo, "config", "user.name", "Test")
    _git(root_repo, "config", "user.email", "test@example.invalid")
    root_remote = tmp_path / "root-origin.git"
    _git(tmp_path, "init", "--bare", str(root_remote))
    _git(root_repo, "remote", "add", "origin", str(root_remote))
    (root_repo / "root.txt").write_text("root\n")
    _git(root_repo, "add", ".")
    _git(root_repo, "commit", "-m", "root")
    root_commit = _git(root_repo, "rev-parse", "HEAD")
    _git(root_repo, "push", "-u", "origin", "main")
    assert (
        _cli(
            root_repo, tmp_path / "root-state", "record-main-promotion", "--commit", root_commit
        ).returncode
        == 2
    )

    stale_repo, _, stale_commit = _direct_repo(tmp_path / "stale", push=False)
    assert (
        _cli(
            stale_repo, tmp_path / "stale-state", "record-main-promotion", "--commit", stale_commit
        ).returncode
        == 2
    )

    absent_repo = tmp_path / "absent-repo"
    absent_repo.mkdir()
    _git(absent_repo, "init", "--initial-branch", "main")
    _git(absent_repo, "config", "user.name", "Test")
    _git(absent_repo, "config", "user.email", "test@example.invalid")
    (absent_repo / "commit.txt").write_text("commit\n")
    _git(absent_repo, "add", ".")
    _git(absent_repo, "commit", "-m", "commit")
    absent_commit = _git(absent_repo, "rev-parse", "HEAD")
    assert (
        _cli(
            absent_repo,
            tmp_path / "absent-state",
            "record-main-promotion",
            "--commit",
            absent_commit,
        ).returncode
        == 2
    )

    octopus_repo = _octopus_repo(tmp_path / "octopus")
    octopus_commit = _git(octopus_repo, "rev-parse", "HEAD")
    assert len(_git(octopus_repo, "show", "-s", "--format=%P", octopus_commit).split()) == 3
    assert (
        _cli(
            octopus_repo,
            tmp_path / "octopus-state",
            "record-main-promotion",
            "--commit",
            octopus_commit,
        ).returncode
        == 2
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
