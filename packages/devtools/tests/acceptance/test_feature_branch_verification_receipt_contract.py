from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

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
V1_SCHEMA = PROJECT_ROOT / ".agent/schemas/task-manifest-v1.schema.json"
V2_SCHEMA = PROJECT_ROOT / ".agent/schemas/task-manifest-v2.schema.json"
PYTHONPATH = str(PROJECT_ROOT / "packages/devtools/src")
ENTRYPOINT = "from kotekomi_devtools.cli import entrypoint; raise SystemExit(entrypoint())"
TASK = "feature-receipt-example"
RUN = f"{TASK}-run-001"
MANIFEST = f".agent/tasks/{TASK}.toml"


def _env(fake_bin: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["PYTHONPATH"] = PYTHONPATH
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _commit(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git_output(repo, "rev-parse", "HEAD")


def _fake_uv(path: Path) -> None:
    path.mkdir()
    executable = path / "uv"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)


def _manifest_data(repo: Path, baseline: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "task_id": TASK,
        "title": "Feature receipt fixture",
        "status": "ready_for_terra_high",
        "series_id": "tdd-harness",
        "task_class": "repository-tooling",
        "model_profile": "terra-high-v1",
        "baseline_revision": baseline,
        "tdd_path": "docs/example.md",
        "tdd_sha256": sha256_file(repo / "docs/example.md"),
        "goal": "Verify one feature candidate.",
        "depends_on": [],
        "allowed_paths": ["packages/devtools/src/kotekomi_devtools/cli.py"],
        "reference_paths": [],
        "stop_conditions": ["The verifier changes main."],
        "readiness": {
            "authority": "Fixture TDD.",
            "contract_family": "tdd-harness",
            "dominant_outcome": "One feature receipt.",
            "failure_policy": "Verification failure is recorded.",
            "legacy_disposition": "None.",
            "negative_proof": "No verification branch.",
            "public_entry_point": "kotekomi-agent verify-candidate",
            "scope_policy": "One candidate.",
            "side_effect_boundary": "One receipt commit.",
            "unresolved_decisions": [],
        },
        "budget": {
            "maximum_production_files": 1,
            "maximum_test_files": 1,
            "maximum_production_diff_lines": 100,
        },
        "protected_artifacts": [
            {
                "kind": "leaf-tdd",
                "path": "docs/example.md",
                "sha256": sha256_file(repo / "docs/example.md"),
            }
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


def _fixture(
    tmp_path: Path, *, protected_failure: bool = False
) -> tuple[Path, Path, str, str, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    for source, name in (
        (V1_SCHEMA, "task-manifest-v1.schema.json"),
        (V2_SCHEMA, "task-manifest-v2.schema.json"),
    ):
        destination = repo / ".agent/schemas" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    write_fixture_text(repo / "docs/example.md", "# Example\n")
    write_fixture_text(repo / "packages/devtools/src/kotekomi_devtools/cli.py", "VALUE = 1\n")
    base = _commit(repo, "base")
    write_fixture_text(repo / MANIFEST, render_manifest(_manifest_data(repo, base)))
    specification = _commit(repo, "specification")
    git(repo, "push", "origin", "main")
    git(repo, "switch", "-c", f"feature/{TASK}")
    changed = "outside scope\n" if protected_failure else "VALUE = 2\n"
    write_fixture_text(
        repo
        / ("README.md" if protected_failure else "packages/devtools/src/kotekomi_devtools/cli.py"),
        changed,
    )
    candidate = _commit(repo, "candidate")
    git(repo, "push", "origin", f"feature/{TASK}")
    state = tmp_path / "state"
    for phase, evidence_type, subject_id, payload in (
        (
            "spec",
            "specification_revision",
            "specification",
            {
                "specification_revision": specification,
                "manifest_sha256": sha256_file(repo / MANIFEST),
            },
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
    ):
        write_canonical_record(
            state,
            TASK,
            RUN,
            phase=phase,
            evidence_type=evidence_type,
            subject_id=subject_id,
            payload=payload,
            producer_command="fixture",
        )
    fake_bin = tmp_path / "bin"
    _fake_uv(fake_bin)
    return repo, state, base, specification, candidate, fake_bin


def _verify(
    repo: Path, state: Path, base: str, specification: str, candidate: str, fake_bin: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            ENTRYPOINT,
            "verify-candidate",
            "--manifest",
            MANIFEST,
            "--base",
            base,
            "--specification",
            specification,
            "--candidate",
            candidate,
            "--profile",
            "portable-local",
            "--task-id",
            TASK,
            "--run",
            RUN,
            "--state-root",
            str(state),
        ],
        cwd=repo,
        env=_env(fake_bin),
        text=True,
        capture_output=True,
        check=False,
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    value = json.loads(result.stdout)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_active_verifier_pushes_and_indexes_one_parent_feature_receipt(tmp_path: Path) -> None:
    repo, state, base, specification, candidate, fake_bin = _fixture(tmp_path)

    result = _verify(repo, state, base, specification, candidate, fake_bin)

    assert result.returncode == 0, result.stderr
    payload = _payload(result)
    receipt_commit = str(payload["receipt_commit"])
    assert "verification_branch" not in payload
    assert git_output(repo, "show", "-s", "--format=%P", receipt_commit) == candidate
    assert (
        git_output(repo, "ls-remote", "--heads", "origin", f"refs/heads/feature/{TASK}").split()[0]
        == receipt_commit
    )
    changed = git_output(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", receipt_commit)
    assert changed == str(payload["receipt_path"])
    receipt = json.loads(git_output(repo, "show", f"{receipt_commit}:{changed}"))
    assert receipt["candidate_revision"] == candidate
    evidence = (
        state
        / "experiments"
        / TASK
        / "runs"
        / RUN
        / "receipts/candidate-verification-portable-local.json"
    )
    assert json.loads(evidence.read_text())["receipt_commit"] == receipt_commit

    retry = _verify(repo, state, base, specification, candidate, fake_bin)
    assert retry.returncode == 0
    assert _payload(retry)["receipt_commit"] == receipt_commit


def test_active_verifier_records_failed_receipt_for_a_scope_failure(
    tmp_path: Path,
) -> None:
    repo, state, base, specification, candidate, fake_bin = _fixture(
        tmp_path, protected_failure=True
    )

    result = _verify(repo, state, base, specification, candidate, fake_bin)

    assert result.returncode == 1, result.stderr
    payload = _payload(result)
    receipt = json.loads(
        git_output(repo, "show", f"{payload['receipt_commit']}:{payload['receipt_path']}")
    )
    assert receipt["outcome"] == "failed"
