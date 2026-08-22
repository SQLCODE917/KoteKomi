from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from kotekomi_devtools.evidence_catalog import index_record, write_canonical_record

from packages.devtools.tests.acceptance._oracle_fixtures import git, git_output, init_git_repo

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK = "original-task"
RUN = f"{TASK}-run-001"
SUCCESSOR = "successor-task"
SUCCESSOR_RUN = f"{SUCCESSOR}-run-001"


def _run(repo: Path, state: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "close-superseded-task",
            "--task-id",
            TASK,
            "--run",
            RUN,
            "--successor-task-id",
            SUCCESSOR,
            "--successor-run",
            SUCCESSOR_RUN,
            "--handoff-commit",
            *arguments,
            "--state-root",
            str(state),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _commit(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git_output(repo, "rev-parse", "HEAD")


def _write_spec(repo: Path) -> None:
    schema_dir = repo / ".agent/schemas"
    schema_dir.mkdir(parents=True)
    for name in ("task-manifest-v1.schema.json", "task-manifest-v2.schema.json"):
        shutil.copyfile(PROJECT_ROOT / ".agent/schemas" / name, schema_dir / name)
    task_dir = repo / ".agent/tasks"
    task_dir.mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "docs/original.md").write_text("# Original\n")
    (task_dir / f"{TASK}.toml").write_text(
        f'task_id = "{TASK}"\ntdd_path = "docs/original.md"\ntdd_sha256 = "' + "a" * 64 + '"\n'
    )


def _seed_original(state: Path, repo: Path, specification: str) -> None:
    binding = {
        "schema_version": 1,
        "task_id": TASK,
        "primary_tdd_path": "docs/original.md",
        "tdd_paths": ["docs/original.md"],
        "tdd_sha256": "a" * 64,
        "diagnostics": [],
    }
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="intake",
        evidence_type="tdd_binding",
        subject_id="binding",
        payload=binding,
        producer_command="test",
    )
    index_record(
        state,
        TASK,
        RUN,
        phase="spec",
        evidence_type="task_manifest",
        subject_id="manifest",
        path_scope="repo",
        relative_path=f".agent/tasks/{TASK}.toml",
        producer_command="test",
    )
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="spec",
        evidence_type="task_manifest_validation",
        subject_id="manifest",
        payload={
            "schema_version": 1,
            "status": "valid",
            "task_id": TASK,
            "tdd_path": "docs/original.md",
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
        payload={
            "schema_version": 1,
            "specification_revision": specification,
            "manifest_sha256": "b" * 64,
            "diagnostics": [],
        },
        producer_command="test",
    )


def _seed_successor(state: Path, candidate: str, target: str, specification: str) -> None:
    tag = f"kotekomi/tasks/{SUCCESSOR}/result"
    write_canonical_record(
        state,
        SUCCESSOR,
        SUCCESSOR_RUN,
        phase="candidate",
        evidence_type="candidate_commit",
        subject_id="candidate",
        payload={
            "schema_version": 1,
            "commit_sha": candidate,
            "parent_sha": "0" * 40,
            "diagnostics": [],
        },
        producer_command="test",
    )
    write_canonical_record(
        state,
        SUCCESSOR,
        SUCCESSOR_RUN,
        phase="spec",
        evidence_type="specification_revision",
        subject_id="specification",
        payload={
            "schema_version": 1,
            "specification_revision": specification,
            "manifest_sha256": "b" * 64,
            "diagnostics": [],
        },
        producer_command="test",
    )
    write_canonical_record(
        state,
        SUCCESSOR,
        SUCCESSOR_RUN,
        phase="complete",
        evidence_type="task_result",
        subject_id="result",
        payload={
            "schema_version": 1,
            "outcome": "completed",
            "tag": tag,
            "target_commit": target,
            "tag_message_sha256": "b" * 64,
            "diagnostics": [],
        },
        producer_command="test",
    )
    write_canonical_record(
        state,
        SUCCESSOR,
        SUCCESSOR_RUN,
        phase="main_ci",
        evidence_type="cleanup",
        subject_id="cleanup",
        payload={
            "schema_version": 1,
            "branch_cleanup_complete": True,
            "remaining_branches": [],
            "diagnostics": [],
        },
        producer_command="test",
    )


def _fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, merge_handoff: bool = False
) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    _write_spec(repo)
    _commit(repo, "specification")
    specification = git_output(repo, "rev-parse", "HEAD")
    git(repo, "push", "-u", "origin", "main")
    git(repo, "switch", "-c", f"feature/{TASK}")
    (repo / "handoff.txt").write_text("carried patch\n")
    handoff = _commit(repo, "original handoff")
    git(repo, "push", "-u", "origin", f"feature/{TASK}")
    if merge_handoff:
        git(repo, "switch", "-c", "receipt", handoff)
        receipt_path = (
            f".agent/receipts/verification/{TASK}/{handoff}/portable-local/attempt-0001.json"
        )
        (repo / receipt_path).parent.mkdir(parents=True)
        (repo / receipt_path).write_text(
            json.dumps(
                {
                    "attempt": 1,
                    "candidate_revision": handoff,
                    "profile": "portable-local",
                    "receipt_kind": "candidate_verification",
                    "task_id": TASK,
                },
                sort_keys=True,
            )
            + "\n"
        )
        _commit(repo, "receipt")
        git(repo, "switch", f"feature/{TASK}")
        git(repo, "merge", "--no-ff", "receipt", "-m", "receipt merge")
        handoff = git_output(repo, "rev-parse", "HEAD")
        git(repo, "push", "origin", f"feature/{TASK}")
    git(repo, "switch", "-c", f"feature/{SUCCESSOR}")
    git(repo, "rm", "handoff.txt")
    _commit(repo, "revert handoff")
    (repo / "handoff.txt").write_text("carried patch\n")
    candidate = _commit(repo, "successor handoff")
    (repo / "different.txt").write_text("different patch\n")
    _commit(repo, "different successor patch")
    git(repo, "switch", "main")
    git(repo, "merge", "--no-ff", f"feature/{SUCCESSOR}", "-m", "successor merge")
    target = git_output(repo, "rev-parse", "HEAD")
    tag = f"kotekomi/tasks/{SUCCESSOR}/result"
    git(repo, "tag", "-a", tag, target, "-m", "successor result")
    git(repo, "push", "origin", "main", f"refs/tags/{tag}")
    state = tmp_path / "state"
    monkeypatch.chdir(repo)
    _seed_original(state, repo, specification)
    _seed_successor(state, candidate, target, specification)
    return repo, state, handoff


def test_closure_tags_patch_equivalent_handoff_and_deletes_feature_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, state, handoff = _fixture(tmp_path, monkeypatch)

    result = _run(repo, state, handoff)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "superseded"
    assert git_output(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}") == ""
    assert f"refs/heads/feature/{TASK}" not in git_output(repo, "show-ref", "--heads")
    result_tag = f"kotekomi/tasks/{TASK}/result"
    handoff_tag = f"kotekomi/tasks/{TASK}/superseded-handoff"
    assert git_output(repo, "ls-remote", "origin", f"refs/tags/{result_tag}^{{}}")
    assert (
        git_output(repo, "ls-remote", "origin", f"refs/tags/{handoff_tag}^{{}}").split()[0]
        == handoff
    )
    record = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "results/task-result.json").read_text()
    )
    assert record["outcome"] == "superseded"
    assert record["supersession_reason"] == "scope_discovery"
    assert len(record["handoff_patch_id"]) == 40


def test_closure_blocks_when_handoff_patch_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, state, handoff = _fixture(tmp_path, monkeypatch)
    write_canonical_record(
        state,
        SUCCESSOR,
        SUCCESSOR_RUN,
        phase="candidate",
        evidence_type="candidate_commit",
        subject_id="candidate",
        payload={
            "schema_version": 1,
            "commit_sha": git_output(repo, "rev-parse", f"feature/{SUCCESSOR}"),
            "parent_sha": "0" * 40,
            "diagnostics": [],
        },
        producer_command="test",
    )

    result = _run(repo, state, handoff)

    assert result.returncode == 2
    assert "handoff patch does not match" in result.stdout
    assert git_output(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}")


def test_closure_resolves_a_receipt_merge_delivery_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, state, handoff = _fixture(tmp_path, monkeypatch, merge_handoff=True)

    result = _run(repo, state, handoff)

    assert result.returncode == 0, result.stderr
    record = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "results/task-result.json").read_text()
    )
    assert record["delivery_head_commit"] != handoff
    assert record["delivery_patch_id"] == record["successor_delivery_patch_id"]
