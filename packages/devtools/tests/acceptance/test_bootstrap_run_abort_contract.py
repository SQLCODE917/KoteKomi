from __future__ import annotations

import json
import subprocess
from pathlib import Path

from kotekomi_devtools.evidence_catalog import write_canonical_record

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK = "bootstrap-abort-task"
RUN = "bootstrap-abort-task-run-001"
BRANCH = f"feature/{TASK}"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=check
    )


def _output(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.strip()


def _cli(repo: Path, state: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "abort-bootstrap-run",
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


def _fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    specification = _output(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "branch", BRANCH, specification)
    _git(repo, "push", "origin", f"{BRANCH}:{BRANCH}")

    state = tmp_path / "state"
    run_root = state / "experiments" / TASK / "runs" / RUN
    run_root.mkdir(parents=True)
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": TASK,
                "implementation_run_id": RUN,
                "ordinal": 1,
                "status": "active",
                "terminal_reason": None,
            }
        )
    )
    index = state / "experiments" / TASK / "runs" / "index.json"
    index.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": TASK,
                "runs": [
                    {
                        "implementation_run_id": RUN,
                        "ordinal": 1,
                        "run_record_path": run_root.relative_to(state).as_posix() + "/run.json",
                        "status": "active",
                    }
                ],
                "latest_run_id": RUN,
            }
        )
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
            "manifest_sha256": "0" * 64,
            "diagnostics": [],
        },
        producer_command="fixture",
    )
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="candidate",
        evidence_type="feature_branch",
        subject_id="feature-branch",
        payload={
            "schema_version": 1,
            "branch": BRANCH,
            "specification_revision": specification,
            "diagnostics": [],
        },
        producer_command="fixture",
    )
    return repo, state, specification


def _remote_target(repo: Path) -> str | None:
    result = _git(repo, "ls-remote", "--exit-code", "origin", f"refs/heads/{BRANCH}", check=False)
    fields = result.stdout.split()
    return fields[0] if result.returncode == 0 and fields else None


def _record(state: Path) -> dict[str, object]:
    return json.loads(_record_path(state).read_text())


def _record_path(state: Path) -> Path:
    return state / "experiments" / TASK / "runs" / RUN / "lifecycle/bootstrap-abort.json"


def test_abort_deletes_an_unchanged_bootstrap_branch_without_a_result_tag(tmp_path: Path) -> None:
    repo, state, _ = _fixture(tmp_path)

    result = _cli(repo, state)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "complete"
    assert _git(repo, "rev-parse", "--verify", f"refs/heads/{BRANCH}", check=False).returncode != 0
    assert _remote_target(repo) is None
    assert _record(state)["branch_cleanup_complete"] is True
    assert _git(repo, "tag", "--list", f"kotekomi/tasks/{TASK}/result").stdout == ""
    run = json.loads((state / "experiments" / TASK / "runs" / RUN / "run.json").read_text())
    assert run["status"] == "bootstrap_aborted"


def test_candidate_evidence_blocks_abort_before_branch_deletion(tmp_path: Path) -> None:
    repo, state, specification = _fixture(tmp_path)
    write_canonical_record(
        state,
        TASK,
        RUN,
        phase="candidate",
        evidence_type="candidate_commit",
        subject_id="candidate",
        payload={"schema_version": 1, "commit_sha": specification, "parent_sha": specification},
        producer_command="fixture",
    )

    result = _cli(repo, state)

    assert result.returncode == 2
    assert _output(repo, "rev-parse", f"refs/heads/{BRANCH}") == specification
    assert _remote_target(repo) == specification
    assert not _record_path(state).exists()


def test_changed_feature_tip_blocks_abort_before_branch_deletion(tmp_path: Path) -> None:
    repo, state, specification = _fixture(tmp_path)
    _git(repo, "switch", BRANCH)
    (repo / "changed.txt").write_text("changed\n")
    _git(repo, "add", "changed.txt")
    _git(repo, "commit", "-m", "changed")

    result = _cli(repo, state)

    assert result.returncode == 2
    assert _output(repo, "rev-parse", f"refs/heads/{BRANCH}") != specification
    assert _remote_target(repo) == specification
    assert not _record_path(state).exists()


def test_local_delete_failure_retains_remote_and_records_incomplete_cleanup(tmp_path: Path) -> None:
    repo, state, specification = _fixture(tmp_path)
    _git(repo, "switch", BRANCH)

    result = _cli(repo, state)

    assert result.returncode == 2
    assert _output(repo, "rev-parse", f"refs/heads/{BRANCH}") == specification
    assert _remote_target(repo) == specification
    record = _record(state)
    assert record["status"] == "incomplete"
    assert record["branch_cleanup_complete"] is False
    assert record["remaining_branches"] == [
        f"refs/heads/{BRANCH}",
        f"refs/remotes/origin/{BRANCH}",
    ]


def test_repeated_complete_abort_requires_absent_feature_refs(tmp_path: Path) -> None:
    repo, state, _ = _fixture(tmp_path)
    assert _cli(repo, state).returncode == 0

    repeated = _cli(repo, state)

    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)["status"] == "complete"
