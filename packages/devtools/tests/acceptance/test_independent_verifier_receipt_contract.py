from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from kotekomi_devtools.evidence_catalog import validated_entries, write_canonical_record

from packages.devtools.tests.acceptance._oracle_fixtures import (
    git,
    git_output,
    init_git_repo,
    render_manifest,
    sha256_file,
    write_fixture_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_SOURCE = PROJECT_ROOT / ".agent/schemas/task-manifest-v1.schema.json"
PYTHONPATH = str(PROJECT_ROOT / "packages/devtools/src")
ENTRYPOINT = "from kotekomi_devtools.cli import entrypoint; raise SystemExit(entrypoint())"


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


def _write_fake_uv(path: Path) -> None:
    path.mkdir()
    script = path / "uv"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)


def _manifest(repo: Path, baseline: str) -> dict[str, Any]:
    tdd = repo / "docs/example-tdd.md"
    contract = repo / "packages/devtools/tests/acceptance/example_contract.py"
    return {
        "schema_version": 1,
        "task_id": "independent-verifier-example",
        "title": "Independent verifier example",
        "status": "ready_for_terra_high",
        "series_id": "tdd-harness",
        "task_class": "repository-tooling",
        "model_profile": "terra-high-v1",
        "baseline_revision": baseline,
        "tdd_path": "docs/example-tdd.md",
        "tdd_sha256": sha256_file(tdd),
        "goal": "Verify one frozen candidate.",
        "depends_on": [],
        "allowed_paths": ["packages/devtools/src/kotekomi_devtools/cli.py"],
        "reference_paths": [],
        "stop_conditions": ["The verifier changes product code."],
        "readiness": {
            "authority": "The fixture TDD defines this contract.",
            "contract_family": "tdd-harness",
            "dominant_outcome": "One candidate receipt exists.",
            "failure_policy": "The verifier records candidate failures.",
            "legacy_disposition": "None.",
            "negative_proof": "The verifier does not alter the candidate.",
            "public_entry_point": "kotekomi-agent verify-candidate",
            "scope_policy": "One candidate range.",
            "side_effect_boundary": "One verification receipt commit.",
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
                "path": "docs/example-tdd.md",
                "sha256": sha256_file(tdd),
            },
            {
                "kind": "acceptance-test",
                "path": "packages/devtools/tests/acceptance/example_contract.py",
                "sha256": sha256_file(contract),
            },
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


def _write_manifest(repo: Path, baseline: str) -> None:
    write_fixture_text(
        repo / ".agent/tasks/independent-verifier-example.toml",
        render_manifest(_manifest(repo, baseline)),
    )


def _repo(tmp_path: Path) -> tuple[Path, str, str, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    schema = repo / ".agent/schemas/task-manifest-v1.schema.json"
    schema.parent.mkdir(parents=True)
    shutil.copyfile(SCHEMA_SOURCE, schema)
    write_fixture_text(repo / "docs/example-tdd.md", "# Example TDD\n")
    write_fixture_text(
        repo / "packages/devtools/tests/acceptance/example_contract.py",
        "def test_contract() -> None:\n    assert True\n",
    )
    write_fixture_text(repo / "packages/devtools/src/kotekomi_devtools/cli.py", "VALUE = 1\n")
    base = _commit(repo, "base")
    _write_manifest(repo, base)
    specification = _commit(repo, "specification")
    write_fixture_text(repo / "packages/devtools/src/kotekomi_devtools/cli.py", "VALUE = 2\n")
    candidate = _commit(repo, "candidate")
    fake_bin = tmp_path / "bin"
    _write_fake_uv(fake_bin)
    return repo, base, specification, candidate, fake_bin


def _verify(
    repo: Path,
    fake_bin: Path,
    base: str,
    specification: str,
    candidate: str,
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    state_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    arguments = [
        sys.executable,
        "-c",
        ENTRYPOINT,
        "verify-candidate",
        "--manifest",
        ".agent/tasks/independent-verifier-example.toml",
        "--base",
        base,
        "--specification",
        specification,
        "--candidate",
        candidate,
        "--profile",
        "portable-local",
    ]
    if task_id is not None and run_id is not None and state_root is not None:
        arguments.extend(["--task-id", task_id, "--run", run_id, "--state-root", str(state_root)])
    return subprocess.run(
        arguments,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env=_env(fake_bin),
    )


def _active_run(
    repo: Path,
    tmp_path: Path,
    base: str,
    specification: str,
    candidate: str,
) -> tuple[str, str, Path, Path]:
    task_id = "independent-verifier-example"
    run_id = "independent-verifier-example-run-001"
    remote = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", f"{candidate}:refs/heads/feature/{task_id}")
    state = tmp_path / "state"
    manifest = repo / ".agent/tasks/independent-verifier-example.toml"
    records = (
        (
            "specification_revision",
            "specification",
            {"specification_revision": specification, "manifest_sha256": sha256_file(manifest)},
        ),
        (
            "feature_branch",
            "branch",
            {"branch": f"feature/{task_id}", "specification_revision": specification},
        ),
        ("candidate_commit", "candidate", {"commit_sha": candidate, "parent_sha": specification}),
    )
    for evidence_type, subject_id, payload in records:
        write_canonical_record(
            state,
            task_id,
            run_id,
            phase="candidate",
            evidence_type=evidence_type,
            subject_id=subject_id,
            payload={"schema_version": 1, **payload, "diagnostics": []},
            producer_command="test",
        )
    return task_id, run_id, state, remote


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    value = json.loads(result.stdout)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _receipt(repo: Path, payload: dict[str, Any]) -> dict[str, Any]:
    text = git_output(
        repo,
        "show",
        f"{payload['verification_commit']}:{payload['receipt_path']}",
    )
    value = json.loads(text)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_verify_candidate_commits_a_receipt_that_binds_frozen_revisions(tmp_path: Path) -> None:
    repo, base, specification, candidate, fake_bin = _repo(tmp_path)

    result = _verify(repo, fake_bin, base, specification, candidate)

    assert result.returncode == 0, result.stderr
    payload = _payload(result)
    assert payload["outcome"] == "passed"
    recorded = _receipt(repo, payload)
    assert recorded["base_revision"] == base
    assert recorded["specification_revision"] == specification
    assert recorded["candidate_revision"] == candidate
    assert (
        recorded["manifest"]["sha256"]
        == hashlib.sha256(
            (repo / ".agent/tasks/independent-verifier-example.toml").read_bytes()
        ).hexdigest()
    )
    assert recorded["outcome"] == "passed"
    assert len(recorded["check_results"]) >= 1
    verification_commit = str(payload["verification_commit"])
    changed_path = git_output(
        repo, "diff-tree", "--no-commit-id", "--name-only", "-r", verification_commit
    )
    assert changed_path == str(payload["receipt_path"])


def test_verify_candidate_records_protected_artifact_failure_and_retry(tmp_path: Path) -> None:
    repo, base, specification, _candidate, fake_bin = _repo(tmp_path)
    write_fixture_text(
        repo / "packages/devtools/tests/acceptance/example_contract.py",
        "def test_contract() -> None:\n    assert False\n",
    )
    changed_candidate = _commit(repo, "changed protected artifact")

    failed = _verify(repo, fake_bin, base, specification, changed_candidate)

    assert failed.returncode == 1, failed.stderr
    failed_payload = _payload(failed)
    assert failed_payload["outcome"] == "failed"
    assert _receipt(repo, failed_payload)["outcome"] == "failed"
    retry = _verify(repo, fake_bin, base, specification, changed_candidate)
    assert retry.returncode == 1, retry.stderr
    assert str(_payload(retry)["receipt_path"]).endswith("attempt-0002.json")


def test_verify_candidate_rejects_manifest_drift_without_a_receipt(tmp_path: Path) -> None:
    repo, base, specification, _candidate, fake_bin = _repo(tmp_path)
    manifest = repo / ".agent/tasks/independent-verifier-example.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    drifted = _commit(repo, "drift manifest")

    result = _verify(repo, fake_bin, base, specification, drifted)

    assert result.returncode == 2
    assert _payload(result)["receipt_path"] is None


def test_active_run_publishes_and_reuses_a_remote_receipt(tmp_path: Path) -> None:
    repo, base, specification, candidate, fake_bin = _repo(tmp_path)
    task_id, run_id, state, remote = _active_run(repo, tmp_path, base, specification, candidate)

    first = _verify(
        repo,
        fake_bin,
        base,
        specification,
        candidate,
        task_id=task_id,
        run_id=run_id,
        state_root=state,
    )

    assert first.returncode == 0, first.stderr
    payload = _payload(first)
    receipt_commit = str(payload["receipt_commit"])
    assert git_output(remote, "rev-parse", f"refs/heads/feature/{task_id}") == receipt_commit
    entries = validated_entries(state, task_id, run_id)
    receipts = [
        entry for entry in entries if entry["evidence_type"] == "candidate_verification_receipt"
    ]
    assert len(receipts) == 1
    indexed_receipt = json.loads((state / receipts[0]["path"]).read_text(encoding="utf-8"))
    assert indexed_receipt["candidate_revision"] == candidate
    assert indexed_receipt["receipt_commit"] == receipt_commit
    repeated = _verify(
        repo,
        fake_bin,
        base,
        specification,
        candidate,
        task_id=task_id,
        run_id=run_id,
        state_root=state,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert _payload(repeated)["receipt_commit"] == receipt_commit


def test_active_run_remote_tip_mismatch_emits_json_without_a_receipt(tmp_path: Path) -> None:
    repo, base, specification, candidate, fake_bin = _repo(tmp_path)
    task_id, run_id, state, remote = _active_run(repo, tmp_path, base, specification, candidate)
    write_fixture_text(repo / "other.txt", "other\n")
    other = _commit(repo, "other")
    git(repo, "push", "--force", "origin", f"{other}:refs/heads/feature/{task_id}")

    result = _verify(
        repo,
        fake_bin,
        base,
        specification,
        candidate,
        task_id=task_id,
        run_id=run_id,
        state_root=state,
    )

    assert result.returncode == 2
    assert _payload(result)["diagnostics"][0]["code"] == "feature_branch_changed"
    assert git_output(remote, "rev-parse", f"refs/heads/feature/{task_id}") == other
