from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from kotekomi_devtools.evidence_catalog import write_canonical_record

from packages.devtools.tests.acceptance._oracle_fixtures import (
    git,
    git_output,
    init_git_repo,
    render_manifest,
    sha256_file,
    write_fixture_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK = "feature-promotion-example"
RUN = f"{TASK}-run-001"


def _run(
    repo: Path, state: Path, command: str, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            command,
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


def _manifest(repo: Path, base: str) -> dict[str, Any]:
    tdd = repo / "docs/example.md"
    return {
        "schema_version": 2,
        "task_id": TASK,
        "title": "Feature promotion fixture",
        "status": "ready_for_terra_high",
        "series_id": "tdd-harness",
        "task_class": "repository-tooling",
        "model_profile": "terra-high-v1",
        "baseline_revision": base,
        "tdd_path": "docs/example.md",
        "tdd_sha256": sha256_file(tdd),
        "goal": "Promote one verified feature branch.",
        "depends_on": [],
        "allowed_paths": ["candidate.txt"],
        "reference_paths": [],
        "stop_conditions": ["The command force-pushes main."],
        "readiness": {
            "authority": "Fixture TDD.",
            "contract_family": "tdd-harness",
            "dominant_outcome": "One promoted branch.",
            "failure_policy": "Invalid evidence blocks promotion.",
            "legacy_disposition": "None.",
            "negative_proof": "No force push.",
            "public_entry_point": "kotekomi-agent promote-feature-branch",
            "scope_policy": "One feature branch.",
            "side_effect_boundary": "Non-force merge and result tag.",
            "unresolved_decisions": [],
        },
        "budget": {
            "maximum_production_files": 1,
            "maximum_test_files": 1,
            "maximum_production_diff_lines": 100,
        },
        "protected_artifacts": [
            {"kind": "leaf-tdd", "path": "docs/example.md", "sha256": sha256_file(tdd)}
        ],
        "acceptance": [
            {
                "id": "fixture-contract",
                "argv": ["uv", "run", "pytest", "fixture-contract"],
                "timeout_seconds": 30,
                "profile": "portable-local",
            }
        ],
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, str, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    schema_dir = repo / ".agent/schemas"
    schema_dir.mkdir(parents=True)
    for name in ("task-manifest-v1.schema.json", "task-manifest-v2.schema.json"):
        shutil.copyfile(PROJECT_ROOT / ".agent/schemas" / name, schema_dir / name)
    write_fixture_text(repo / "docs/example.md", "# Example\n")
    base = _commit(repo, "base")
    write_fixture_text(repo / f".agent/tasks/{TASK}.toml", render_manifest(_manifest(repo, base)))
    specification = _commit(repo, "specification")
    git(repo, "push", "-u", "origin", "main")
    git(repo, "switch", "-c", f"feature/{TASK}")
    write_fixture_text(repo / "candidate.txt", "candidate\n")
    candidate = _commit(repo, "candidate")
    receipt_path = ".agent/receipts/portable-local.json"
    write_fixture_text(repo / receipt_path, '{"schema_version":1}\n')
    receipt = _commit(repo, "receipt")
    git(repo, "push", "-u", "origin", f"feature/{TASK}")
    git(repo, "switch", "main")
    state = tmp_path / "state"
    _seed(state, base, specification, candidate, receipt, receipt_path)
    return repo, state, specification, candidate, receipt


def _commit(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git_output(repo, "rev-parse", "HEAD")


def _seed(
    state: Path, base: str, specification: str, candidate: str, receipt: str, receipt_path: str
) -> None:
    records = (
        (
            "spec",
            "specification_revision",
            "specification",
            {"specification_revision": specification, "manifest_sha256": "a" * 64},
        ),
        (
            "candidate",
            "feature_branch",
            "feature-branch",
            {"branch": f"feature/{TASK}", "specification_revision": specification},
        ),
        (
            "candidate",
            "candidate_commit",
            "candidate",
            {"commit_sha": candidate, "parent_sha": specification},
        ),
        (
            "verification",
            "candidate_verification_receipt",
            "portable-local",
            {
                "schema_version": 1,
                "outcome": "passed",
                "profile": "portable-local",
                "receipt_path": receipt_path,
                "receipt_sha256": "b" * 64,
                "receipt_commit": receipt,
                "base_revision": base,
                "specification_revision": specification,
                "candidate_revision": candidate,
            },
        ),
        (
            "candidate_ci",
            "candidate_ci",
            "candidate",
            {"conclusion": "success", "head_sha": receipt},
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
            payload={"schema_version": 1, **payload, "diagnostics": []},
            producer_command="test",
        )


def _remote(repo: Path, ref: str) -> str:
    return git_output(repo, "ls-remote", "origin", ref).split()[0]


def _record_main_ci(repo: Path, state: Path, promotion: str) -> None:
    result = state / "main-ci.json"
    result.write_text(
        json.dumps({"schema_version": 1, "conclusion": "success", "head_sha": promotion})
    )
    recorded = _run(repo, state, "record-main-ci", "--ci-result", str(result))
    assert recorded.returncode == 0, recorded.stderr


def test_promotion_creates_verified_merge_and_completion_tags_then_cleans_branch(
    tmp_path: Path,
) -> None:
    repo, state, specification, _, receipt = _fixture(tmp_path)

    promoted = _run(repo, state, "promote-feature-branch")

    assert promoted.returncode == 0, promoted.stderr
    promotion = json.loads(promoted.stdout)["promotion_commit"]
    assert _remote(repo, "refs/heads/main") == promotion
    assert git_output(repo, "show", "-s", "--format=%P", promotion).split() == [
        specification,
        receipt,
    ]
    _record_main_ci(repo, state, promotion)

    completed = _run(repo, state, "complete-feature-branch")

    assert completed.returncode == 0, completed.stderr
    tag = f"kotekomi/tasks/{TASK}/result"
    assert _remote(repo, f"refs/tags/{tag}^{{}}") == promotion
    assert git_output(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}") == ""
    record = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "results/task-result.json").read_text()
    )
    assert record["target_commit"] == promotion
    assert (
        record["tag_message_sha256"]
        == hashlib.sha256(
            git_output(repo, "for-each-ref", f"refs/tags/{tag}", "--format=%(contents)").encode()
        ).hexdigest()
    )


def test_completion_retains_remote_branch_when_local_cleanup_is_not_possible(
    tmp_path: Path,
) -> None:
    repo, state, _, _, _ = _fixture(tmp_path)
    promoted = _run(repo, state, "promote-feature-branch")
    promotion = json.loads(promoted.stdout)["promotion_commit"]
    _record_main_ci(repo, state, promotion)
    git(repo, "switch", f"feature/{TASK}")
    write_fixture_text(repo / "uncommitted.txt", "retain local branch\n")

    completed = _run(repo, state, "complete-feature-branch")

    assert completed.returncode == 2
    assert _remote(repo, f"refs/heads/feature/{TASK}")
    cleanup = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "cleanup/branch-cleanup.json").read_text()
    )
    assert cleanup["branch_cleanup_complete"] is False


def test_abandonment_cleans_an_orphan_branch_without_replacing_supersession(
    tmp_path: Path,
) -> None:
    repo, state, specification, _, _ = _fixture(tmp_path)
    branch = f"feature/{TASK}"
    git(repo, "branch", "-D", branch)
    git(repo, "push", "origin", "--delete", branch)
    git(repo, "branch", branch, specification)
    git(repo, "push", "-u", "origin", branch)
    run_path = state / "experiments" / TASK / "runs" / RUN / "run.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps({"status": "abandoned", "terminal_reason": "operator_abandoned"})
    )
    historical_run = f"{TASK}-run-000"
    historical_path = state / "experiments" / TASK / "runs" / historical_run / "run.json"
    historical_path.parent.mkdir(parents=True)
    historical_path.write_text(json.dumps({"status": "superseded"}))
    (historical_path.parent.parent / "index.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "implementation_run_id": historical_run,
                        "ordinal": 0,
                        "run_record_path": historical_path.relative_to(state).as_posix(),
                        "status": "superseded",
                    },
                    {
                        "implementation_run_id": RUN,
                        "ordinal": 1,
                        "run_record_path": run_path.relative_to(state).as_posix(),
                        "status": "abandoned",
                    },
                ]
            }
        )
    )
    tag = f"kotekomi/tasks/{TASK}/result"
    message = json.dumps(
        {"schema_version": 1, "outcome": "superseded", "task_id": TASK}, sort_keys=True
    )
    git(repo, "tag", "-a", tag, specification, "-m", message)
    git(repo, "push", "origin", f"refs/tags/{tag}")
    contents = git_output(repo, "for-each-ref", tag, "--format=%(contents)")
    write_canonical_record(
        state,
        TASK,
        historical_run,
        phase="complete",
        evidence_type="task_result",
        subject_id="result",
        payload={
            "schema_version": 1,
            "outcome": "superseded",
            "tag": tag,
            "target_commit": specification,
            "tag_message_sha256": hashlib.sha256(contents.encode()).hexdigest(),
            "supersession_reason": "scope_discovery",
            "successor_task_id": "successor",
            "successor_run_id": "successor-run-001",
            "successor_result_tag": "kotekomi/tasks/successor/result",
            "successor_target_commit": specification,
            "handoff_commit": specification,
            "handoff_patch_id": "a" * 40,
            "delivery_base_commit": "b" * 40,
            "delivery_head_commit": specification,
            "delivery_patch_id": "a" * 40,
            "successor_delivery_base_commit": "b" * 40,
            "successor_delivery_patch_id": "a" * 40,
            "delivery_relation": "exact",
            "historic_delivery_diff_sha256": "c" * 64,
            "diagnostics": [],
        },
        producer_command="test",
    )

    abandoned = _run(repo, state, "abandon-feature-branch")

    assert abandoned.returncode == 0, abandoned.stderr
    assert git_output(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}") == ""
    assert not (state / "experiments" / TASK / "runs" / RUN / "results/task-result.json").exists()
    cleanup = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "cleanup/branch-cleanup.json").read_text()
    )
    assert cleanup["terminal_result_preserved"] is True


def test_abandonment_cleans_a_tagged_unmerged_feature_branch(tmp_path: Path) -> None:
    repo, state, _, _, receipt = _fixture(tmp_path)
    run_path = state / "experiments" / TASK / "runs" / RUN / "run.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps({"status": "abandoned", "terminal_reason": "operator_abandoned"})
    )
    (run_path.parent.parent / "index.json").write_text(
        json.dumps({"runs": [{"implementation_run_id": RUN}]})
    )

    abandoned = _run(repo, state, "abandon-feature-branch")

    assert abandoned.returncode == 0, abandoned.stderr
    tag = f"kotekomi/tasks/{TASK}/result"
    assert _remote(repo, f"refs/tags/{tag}^{{}}") == receipt
    assert (
        subprocess.run(
            ["git", "show-ref", "--verify", f"refs/heads/feature/{TASK}"],
            cwd=repo,
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )
    assert git_output(repo, "ls-remote", "origin", f"refs/heads/feature/{TASK}") == ""


def test_abandonment_retains_a_local_ref_that_differs_from_the_remote_tip(tmp_path: Path) -> None:
    repo, state, _, candidate, receipt = _fixture(tmp_path)
    run_path = state / "experiments" / TASK / "runs" / RUN / "run.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps({"status": "abandoned", "terminal_reason": "operator_abandoned"})
    )
    (run_path.parent.parent / "index.json").write_text(
        json.dumps({"runs": [{"implementation_run_id": RUN}]})
    )
    git(repo, "branch", "-f", f"feature/{TASK}", candidate)

    abandoned = _run(repo, state, "abandon-feature-branch")

    assert abandoned.returncode == 2
    assert git_output(repo, "rev-parse", f"feature/{TASK}") == candidate
    assert _remote(repo, f"refs/heads/feature/{TASK}") == receipt
    cleanup = json.loads(
        (state / "experiments" / TASK / "runs" / RUN / "cleanup/branch-cleanup.json").read_text()
    )
    assert cleanup["branch_cleanup_complete"] is False
    assert cleanup["remaining_branches"] == [f"feature/{TASK}", f"origin/feature/{TASK}"]
