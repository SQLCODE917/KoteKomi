# Reuse established disposable-repository fixtures through the public CLI.
# pyright: reportPrivateUsage=false
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .test_specification_commit_selection_contract import BRANCH, _cli, _git, _repo


def _start(tmp_path: Path, *, production: bool = False) -> tuple[Path, Path, str, str, Path, str]:
    repo, task, spec, manifest = _repo(tmp_path)
    if production:
        manifest.write_text(
            manifest.read_text().replace(
                "implementation.txt", "packages/devtools/src/kotekomi_devtools/a.py"
            )
        )
        spec = _commit(repo)
    state = tmp_path / "state"
    first = _cli(repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", spec)
    assert first.returncode == 0, first.stdout + first.stderr
    return repo, state, task, spec, manifest, json.loads(first.stdout)["implementation_run_id"]


def _amend(repo: Path, state: Path, revision: str) -> tuple[int, dict[str, Any]]:
    result = _cli(
        repo,
        state,
        "implement-tdd",
        "docs/leaf.md",
        "--specification-commit",
        revision,
        "--amend-reason",
        "The same task needs another implementation path",
    )
    return result.returncode, json.loads(result.stdout)


def _commit(repo: Path) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "amend implementation boundary")
    revision = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "origin", BRANCH)
    return revision


def test_amendment_preserves_run_and_evidence_and_invalidates_current_checks(
    tmp_path: Path,
) -> None:
    repo, state, task, spec, manifest, run = _start(tmp_path)
    active = state / "experiments" / task / "runs" / run
    old_log = active / "checks" / "previous.log"
    old_log.parent.mkdir()
    old_log.write_text("old check evidence")
    manifest.write_text(
        manifest.read_text().replace('"implementation.txt"]', '"implementation.txt", "helper.txt"]')
    )
    revision = _commit(repo)
    code, result = _amend(repo, state, revision)
    assert code == 0, result
    assert result["implementation_run_id"] == run
    assert result["implementation_phase"] == "candidate"
    archive = state / "experiments" / task / "amendments" / run / revision
    assert (archive / "run/checks/previous.log").read_text() == "old check evidence"
    assert not old_log.exists()
    assert spec in (archive / "amendment.json").read_text()
    assert (
        json.loads((active / "git/specification-revision.json").read_text())[
            "specification_revision"
        ]
        == revision
    )
    assert json.loads((active / "evidence/index.json").read_text())["entries"]
    # Idempotent replay after a new candidate must not erase its evidence.
    (repo / "helper.txt").write_text("new implementation")
    _commit(repo)
    old_log.parent.mkdir()
    old_log.write_text("fresh check evidence")
    code, repeated = _amend(repo, state, revision)
    assert code == 0, repeated
    assert repeated["implementation_run_id"] == run
    assert old_log.read_text() == "fresh check evidence"
    assert len(json.loads((active.parent / "index.json").read_text())["runs"]) == 1


@pytest.mark.parametrize("change", ["acceptance", "baseline", "tdd", "dirty", "terminal"])
def test_amendment_rejects_changed_authority_or_unavailable_checkout(
    tmp_path: Path, change: str
) -> None:
    repo, state, task, spec, manifest, run = _start(tmp_path)
    active = state / "experiments" / task / "runs" / run
    pin = (active / "git/specification-revision.json").read_bytes()
    original = manifest.read_text()
    if change == "acceptance":
        manifest.write_text(original.replace('argv = ["true"]', 'argv = ["false"]'))
    elif change == "baseline":
        manifest.write_text(
            original.replace(original.split('baseline_revision = "')[1].split('"')[0], spec)
        )
    elif change == "tdd":
        (repo / "docs/leaf.md").write_text("# Leaf\nChanged behavior\n")
    else:
        manifest.write_text(
            original.replace("maximum_production_files = 1", "maximum_production_files = 2")
        )
    revision = _commit(repo)
    if change == "dirty":
        (repo / "dirty.txt").write_text("uncommitted")
    if change == "terminal":
        ended = _cli(repo, state, "implement-tdd", "docs/leaf.md", "--abandon-run", run)
        assert ended.returncode == 0
    code, result = _amend(repo, state, revision)
    assert code == 1, result
    assert result["status"] == "blocked"
    assert (active / "git/specification-revision.json").read_bytes() == pin
    assert not (state / "experiments" / task / "amendment-pending.json").exists()


def test_pending_amendment_blocks_ordinary_status_and_resumes_same_operation(
    tmp_path: Path,
) -> None:
    repo, state, task, _, manifest, run = _start(tmp_path)
    manifest.write_text(
        manifest.read_text().replace("maximum_production_files = 1", "maximum_production_files = 2")
    )
    revision = _commit(repo)
    code, result = _amend(repo, state, revision)
    assert code == 0, result
    experiment = state / "experiments" / task
    archive = experiment / "amendments" / run / revision
    request = json.loads((archive / "amendment.json").read_text())
    del request["previous_specification_revision"]
    # Simulate a crash after invalidating evidence but before replacing the specification pin.
    pending = experiment / "amendment-pending.json"
    pending.write_text(json.dumps(request))
    (experiment / "runs" / run / "git/specification-revision.json").unlink()
    blocked = _cli(repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", revision)
    assert blocked.returncode == 1
    assert "amendment pending" in blocked.stdout
    code, resumed = _amend(repo, state, revision)
    assert code == 0, resumed
    assert resumed["implementation_run_id"] == run
    assert not pending.exists()


def test_budget_size_is_advisory_but_scope_still_blocks_lifecycle(tmp_path: Path) -> None:
    repo, state, task, spec, manifest, run = _start(tmp_path, production=True)
    source = repo / "packages/devtools/src/kotekomi_devtools/a.py"
    source.parent.mkdir(parents=True)
    source.write_text("implementation\n" * 20)
    candidate = _commit(repo)
    budget = _cli(repo, state, "budget-audit", str(manifest), "--base", spec, "--head", candidate)
    assert budget.returncode == 0, budget.stdout
    assert json.loads(budget.stdout)["status"] == "over_budget"
    result = _cli(
        repo,
        state,
        "lifecycle-check",
        str(manifest),
        "--phase",
        "candidate",
        "--base",
        spec,
        "--head",
        candidate,
        "--task-id",
        task,
        "--run",
        run,
    )
    assert result.returncode == 0, result.stdout
    (repo / "outside.txt").write_text("scope violation")
    outside = _commit(repo)
    result = _cli(
        repo,
        state,
        "lifecycle-check",
        str(manifest),
        "--phase",
        "candidate",
        "--base",
        spec,
        "--head",
        outside,
        "--task-id",
        task,
        "--run",
        run,
    )
    assert result.returncode == 1, result.stdout
    assert "scope" in result.stdout


def test_amendment_rejects_changed_protected_file_bytes(tmp_path: Path) -> None:
    import hashlib

    repo, _, _, manifest = _repo(tmp_path)
    protected = repo / "oracle.txt"
    protected.write_text("frozen oracle")
    manifest.write_text(
        manifest.read_text()
        + '\n[[protected_artifacts]]\nkind = "fixture"\npath = "oracle.txt"\n'
        + f'sha256 = "{hashlib.sha256(protected.read_bytes()).hexdigest()}"\n'
    )
    spec = _commit(repo)
    state = tmp_path / "state"
    first = _cli(repo, state, "implement-tdd", "docs/leaf.md", "--specification-commit", spec)
    assert first.returncode == 0, first.stdout
    protected.write_text("weakened oracle")
    manifest.write_text(
        manifest.read_text().replace("maximum_production_files = 1", "maximum_production_files = 2")
    )
    revision = _commit(repo)
    code, result = _amend(repo, state, revision)
    assert code == 1, result
    assert "protected content" in result["diagnostics"][0]["rule"]
