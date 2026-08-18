from __future__ import annotations

import json
import subprocess
from pathlib import Path

from kotekomi_devtools.evidence_catalog import write_canonical_record

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK = "task"
RUN = "task-run-001"


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _run(repo: Path, state: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "reconcile-merged-feature-branch",
            *arguments,
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


def _repository(tmp_path: Path) -> tuple[Path, str, str, str]:
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
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "checkout", "-b", f"feature/{TASK}")
    (repo / "candidate.txt").write_text("candidate\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "candidate")
    candidate = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", f"feature/{TASK}")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", f"feature/{TASK}", "-m", "merge candidate")
    promotion = _git(repo, "rev-parse", "HEAD")
    (repo / "main.txt").write_text("main\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main followup")
    final_main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "origin", "main")
    return repo, base, candidate, promotion + ":" + final_main


def _seed(state: Path, base: str, candidate: str) -> Path:
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="spec",
        evidence_type="task_manifest_validation",
        subject_id="manifest",
        payload={
            "status": "valid",
            "task_id": TASK,
            "tdd_path": "docs/task.md",
            "tdd_sha256": "a" * 64,
            "diagnostics": [],
        },
        producer_command="test",
    )
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="spec",
        evidence_type="specification_revision",
        subject_id="specification",
        payload={"specification_revision": base, "manifest_sha256": "b" * 64},
        producer_command="test",
    )
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="candidate",
        evidence_type="feature_branch",
        subject_id="feature-branch",
        payload={"branch": f"feature/{TASK}", "specification_revision": base},
        producer_command="test",
    )
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="candidate",
        evidence_type="candidate_commit",
        subject_id="candidate",
        payload={"commit_sha": candidate, "parent_sha": base},
        producer_command="test",
    )
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="candidate_ci",
        evidence_type="candidate_ci",
        subject_id="candidate",
        payload={"conclusion": "failure", "head_sha": candidate},
        producer_command="test",
    )
    ci = state / "final-main-ci.json"
    return ci


def test_reconciliation_records_final_main_and_deletes_the_feature_branch(tmp_path: Path) -> None:
    repo, base, candidate, commits = _repository(tmp_path)
    promotion, final_main = commits.split(":")
    state = tmp_path / "state"
    ci = _seed(state, base, candidate)
    ci.write_text(
        json.dumps({"schema_version": 1, "conclusion": "success", "head_sha": final_main})
    )
    candidate_ci = state / "experiments" / TASK / "runs" / RUN / "ci" / "candidate.json"
    before = candidate_ci.read_bytes()

    result = _run(
        repo,
        state,
        "--promotion",
        promotion,
        "--final-main",
        final_main,
        "--ci-result",
        str(ci),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "complete"
    assert candidate_ci.read_bytes() == before
    assert _git(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}") == ""
    assert subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/feature/{TASK}"], cwd=repo
    ).returncode == 1
    assert final_main in _git(
        repo, "ls-remote", "--tags", "origin", f"refs/tags/kotekomi/tasks/{TASK}/result*"
    )
    main_ci = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "ci" / "main.json").read_text()
    )
    assert main_ci["head_sha"] == final_main
    assert main_ci["validated_promotion_commit"] == promotion

    retry = _run(
        repo,
        state,
        "--promotion",
        promotion,
        "--final-main",
        final_main,
        "--ci-result",
        str(ci),
    )
    assert retry.returncode == 0, retry.stderr


def test_reconciliation_blocks_before_writing_main_evidence_for_wrong_candidate(
    tmp_path: Path,
) -> None:
    repo, base, candidate, commits = _repository(tmp_path)
    promotion, final_main = commits.split(":")
    state = tmp_path / "state"
    ci = _seed(state, base, candidate)
    ci.write_text(
        json.dumps({"schema_version": 1, "conclusion": "success", "head_sha": final_main})
    )
    candidate_record = (
        state / "experiments" / TASK / "runs" / RUN / "git" / "candidate-commit.json"
    )
    candidate_record.write_text(json.dumps({"commit_sha": base, "parent_sha": base}))

    result = _run(
        repo,
        state,
        "--promotion",
        promotion,
        "--final-main",
        final_main,
        "--ci-result",
        str(ci),
    )

    assert result.returncode == 2
    assert not (
        state / "experiments" / TASK / "runs" / RUN / "git" / "main-promotion.json"
    ).exists()
    assert _git(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}")
