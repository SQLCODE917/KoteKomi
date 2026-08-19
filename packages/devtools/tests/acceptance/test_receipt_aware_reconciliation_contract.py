from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from kotekomi_devtools.evidence_catalog import write_canonical_record

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK = "receipt-task"
RUN = "receipt-task-run-001"
type Json = dict[str, Any]


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


def _repository(tmp_path: Path) -> tuple[Path, str, str, str, str]:
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
    (repo / "receipt.txt").write_text("receipt\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "portable receipt")
    receipt = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", f"feature/{TASK}")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", f"feature/{TASK}", "-m", "merge receipt")
    promotion = _git(repo, "rev-parse", "HEAD")
    (repo / "main.txt").write_text("main\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main followup")
    final_main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "origin", "main")
    return repo, base, candidate, receipt, promotion + ":" + final_main


def _seed(state: Path, base: str, candidate: str, receipt: str, receipt_spec: str) -> Path:
    records: tuple[tuple[str, str, str, Json], ...] = (
        (
            "spec",
            "task_manifest_validation",
            "manifest",
            {
                "status": "valid",
                "task_id": TASK,
                "tdd_path": "docs/task.md",
                "tdd_sha256": "a" * 64,
                "diagnostics": [],
            },
        ),
        (
            "spec",
            "specification_revision",
            "specification",
            {"specification_revision": base, "manifest_sha256": "b" * 64},
        ),
        (
            "candidate",
            "feature_branch",
            "feature-branch",
            {"branch": f"feature/{TASK}", "specification_revision": base},
        ),
        (
            "candidate",
            "candidate_commit",
            "candidate",
            {"commit_sha": candidate, "parent_sha": base},
        ),
        (
            "verification",
            "candidate_verification_receipt",
            "portable-local",
            {
                "schema_version": 1,
                "outcome": "passed",
                "profile": "portable-local",
                "receipt_path": ".agent/receipts/test.json",
                "receipt_sha256": "c" * 64,
                "receipt_commit": receipt,
                "base_revision": base,
                "specification_revision": receipt_spec,
                "candidate_revision": candidate,
            },
        ),
    )
    for phase, evidence_type, subject_id, payload in records:
        write_canonical_record(
            state,
            TASK,
            RUN,
            phase=phase,
            evidence_type=evidence_type,
            subject_id=subject_id,
            payload=payload,
            producer_command="test",
        )
    return state / "final-main-ci.json"


def test_reconciliation_accepts_a_bound_portable_receipt_merge_parent(tmp_path: Path) -> None:
    repo, base, candidate, receipt, commits = _repository(tmp_path)
    promotion, final_main = commits.split(":")
    state = tmp_path / "state"
    ci = _seed(state, base, candidate, receipt, base)
    ci.write_text(
        json.dumps({"schema_version": 1, "conclusion": "success", "head_sha": final_main})
    )

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
    promotion_record = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "git" / "main-promotion.json").read_text()
    )
    assert promotion_record["verified_parent_commit"] == receipt
    assert _git(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}") == ""


def test_reconciliation_rejects_a_portable_receipt_with_the_wrong_specification(
    tmp_path: Path,
) -> None:
    repo, base, candidate, receipt, commits = _repository(tmp_path)
    promotion, final_main = commits.split(":")
    state = tmp_path / "state"
    ci = _seed(state, base, candidate, receipt, candidate)
    ci.write_text(
        json.dumps({"schema_version": 1, "conclusion": "success", "head_sha": final_main})
    )

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
    promotion_record = state / "experiments" / TASK / "runs" / RUN / "git" / "main-promotion.json"
    assert not promotion_record.exists()


def test_reconciliation_requires_the_remote_feature_tip_to_equal_the_receipt(
    tmp_path: Path,
) -> None:
    repo, base, candidate, receipt, commits = _repository(tmp_path)
    promotion, final_main = commits.split(":")
    state = tmp_path / "state"
    ci = _seed(state, base, candidate, receipt, base)
    ci.write_text(
        json.dumps({"schema_version": 1, "conclusion": "success", "head_sha": final_main})
    )
    _git(repo, "push", "--force", "origin", f"{candidate}:refs/heads/feature/{TASK}")

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
    assert "remote feature tip must equal verified merge parent" in result.stderr
    promotion_record = state / "experiments" / TASK / "runs" / RUN / "git" / "main-promotion.json"
    assert not promotion_record.exists()
