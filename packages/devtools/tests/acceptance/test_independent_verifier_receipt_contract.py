from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

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
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
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
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env=_env(fake_bin),
    )


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
    repo, base, specification, candidate, fake_bin = _repo(tmp_path)
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
    repo, base, specification, candidate, fake_bin = _repo(tmp_path)
    manifest = repo / ".agent/tasks/independent-verifier-example.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    drifted = _commit(repo, "drift manifest")

    result = _verify(repo, fake_bin, base, specification, drifted)

    assert result.returncode == 2
    assert _payload(result)["receipt_path"] is None
