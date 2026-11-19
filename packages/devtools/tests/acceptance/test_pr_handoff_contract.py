from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

from kotekomi_devtools.tdd_binding import derive_task_id

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BRANCH = "spec/handoff"
TEMPLATE = PROJECT_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def _preflight(repo: Path, description: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "handoff-preflight",
            str(description),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    remote = repo.parent / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / ".agent" / "schemas").mkdir(parents=True)
    for schema in ("task-manifest-v1.schema.json", "task-manifest-v2.schema.json"):
        shutil.copy2(PROJECT_ROOT / ".agent" / "schemas" / schema, repo / ".agent" / "schemas")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "checkout", "-b", BRANCH)
    return repo, base


def _manifest_text(
    *, task_id: str, baseline: str, tdd_path: str, tdd_sha256: str, version: int
) -> str:
    return "\n".join(
        [
            f"schema_version = {version}",
            f'task_id = "{task_id}"',
            'title = "Leaf"',
            'status = "ready_for_terra_high"',
            'series_id = "same-branch-delivery-handoff"',
            'task_class = "repository-tooling"',
            'model_profile = "terra-high-v1"',
            f'baseline_revision = "{baseline}"',
            f'tdd_path = "{tdd_path}"',
            f'tdd_sha256 = "{tdd_sha256}"',
            'goal = "Exercise the PR handoff preflight."',
            "depends_on = []",
            f'allowed_paths = ["{tdd_path}", "implementation.txt"]',
            "reference_paths = []",
            'stop_conditions = ["none"]',
            "",
            "[readiness]",
            'authority = "Leaf TDD"',
            'contract_family = "same-branch-delivery-handoff"',
            'dominant_outcome = "One current handoff."',
            'failure_policy = "Fail closed."',
            'legacy_disposition = "Preserve existing entry points."',
            'negative_proof = "Fixtures reject ambiguous pins."',
            'public_entry_point = "handoff-preflight"',
            'scope_policy = "One read-only preflight."',
            'side_effect_boundary = "No writes."',
            "unresolved_decisions = []",
            "",
            "[budget]",
            "maximum_production_files = 1",
            "maximum_test_files = 1",
            "maximum_production_diff_lines = 1",
            "",
            "[[protected_artifacts]]",
            'kind = "leaf-tdd"',
            f'path = "{tdd_path}"',
            f'sha256 = "{tdd_sha256}"',
            "",
            "[[acceptance]]",
            'id = "leaf"',
            'argv = ["true"]',
            "timeout_seconds = 120",
            'profile = "portable-local"',
            "",
        ]
    )


def _specification(
    repo: Path,
    baseline: str,
    *,
    tdd_path: str = "docs/leaf.md",
    tdd_text: str = "# Leaf\n",
    title: str = "Leaf",
    version: int = 2,
    tdd_sha256: str | None = None,
) -> tuple[str, str]:
    tdd = repo / tdd_path
    tdd.parent.mkdir(parents=True, exist_ok=True)
    tdd.write_text(tdd_text)
    digest = tdd_sha256 or hashlib.sha256(tdd.read_bytes()).hexdigest()
    task_id = derive_task_id(title, digest)
    manifest = repo / ".agent" / "tasks" / f"{task_id}.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        _manifest_text(
            task_id=task_id,
            baseline=baseline,
            tdd_path=tdd_path,
            tdd_sha256=digest,
            version=version,
        )
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"specification {tdd_path}")
    _git(repo, "push", "origin", BRANCH)
    return _git(repo, "rev-parse", "HEAD"), task_id


def _description(
    tmp_path: Path,
    name: str,
    *,
    spec_commit: str = "",
    status: str = "ready",
    tdd: str = "docs/leaf.md",
    prerequisite: str = "none",
    extra: str = "",
) -> Path:
    path = tmp_path / name
    path.write_text(
        "## Current Handoff\n\n"
        f"- Status: {status}\n"
        f"- Spec commit: {spec_commit}\n"
        f"- TDD: {tdd}\n"
        f"- Prerequisite: {prerequisite}\n"
        f"{extra}"
    )
    return path


def _template_description(tmp_path: Path, *, spec_commit: str, tdd: str = "docs/leaf.md") -> Path:
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.replace("<full 40-character lowercase SHA>", spec_commit)
    text = text.replace("<repository-relative leaf TDD path>", tdd)
    path = tmp_path / "template-pr.md"
    path.write_text(text)
    return path


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result.stdout))


def _codes(payload: dict[str, object]) -> list[str]:
    diagnostics = cast(list[object], payload["diagnostics"])
    return [str(cast(dict[str, object], item)["code"]) for item in diagnostics]


def test_ready_handoff_returns_one_start_command_and_survives_later_pushes(
    tmp_path: Path,
) -> None:
    repo, base = _repo(tmp_path)
    specification, task_id = _specification(repo, base)
    description = _template_description(tmp_path, spec_commit=specification)
    before = _git(repo, "status", "--porcelain")

    first = _preflight(repo, description)

    assert first.returncode == 0, first.stderr
    payload = _payload(first)
    assert payload["status"] == "ready"
    assert payload["spec_commit"] == specification
    assert payload["tdd_path"] == "docs/leaf.md"
    assert payload["manifest_path"] == f".agent/tasks/{task_id}.toml"
    assert payload["task_id"] == task_id
    assert payload["start_command"] == [
        "kotekomi-agent",
        "implement-tdd",
        "docs/leaf.md",
        "--specification-commit",
        specification,
    ]
    assert payload["diagnostics"] == []
    assert _git(repo, "status", "--porcelain") == before

    for name in ("implementation.txt", "repair.txt"):
        (repo / name).write_text(f"{name}\n")
        _git(repo, "add", name)
        _git(repo, "commit", "-m", name)
        _git(repo, "push", "origin", BRANCH)

        result = _preflight(repo, description)

        assert result.returncode == 0, result.stderr
        assert _payload(result) == payload


def test_replacement_handoff_selects_only_the_new_pin_and_duplicate_blocks(
    tmp_path: Path,
) -> None:
    repo, base = _repo(tmp_path)
    first_spec, first_task = _specification(repo, base)
    second_spec, second_task = _specification(
        repo, base, tdd_path="docs/leaf-v2.md", tdd_text="# Leaf v2\n", title="Leaf v2"
    )
    old_description = _description(tmp_path, "old.md", spec_commit=first_spec)
    new_description = _description(
        tmp_path, "new.md", spec_commit=second_spec, tdd="docs/leaf-v2.md"
    )

    old = _preflight(repo, old_description)
    new = _preflight(repo, new_description)

    assert old.returncode == 0, old.stderr
    assert new.returncode == 0, new.stderr
    assert _payload(old)["start_command"] == [
        "kotekomi-agent",
        "implement-tdd",
        "docs/leaf.md",
        "--specification-commit",
        first_spec,
    ]
    assert _payload(old)["task_id"] == first_task
    assert _payload(new)["start_command"] == [
        "kotekomi-agent",
        "implement-tdd",
        "docs/leaf-v2.md",
        "--specification-commit",
        second_spec,
    ]
    assert _payload(new)["task_id"] == second_task
    assert _git(repo, "show", f"{first_spec}:docs/leaf.md") == "# Leaf"
    assert _git(repo, "show", f"{first_spec}:.agent/tasks/{first_task}.toml") != ""
    assert not (repo / ".agent" / "receipts").exists()

    duplicated = _description(
        tmp_path,
        "duplicated.md",
        spec_commit=second_spec,
        tdd="docs/leaf-v2.md",
        extra=(
            "\n## Current Handoff\n\n"
            f"- Status: ready\n- Spec commit: {first_spec}\n"
            "- TDD: docs/leaf.md\n- Prerequisite: none\n"
        ),
    )
    blocked = _preflight(repo, duplicated)

    assert blocked.returncode == 1
    assert _payload(blocked)["status"] == "blocked"
    assert _codes(_payload(blocked)) == ["handoff.section_duplicate"]
    assert "start_command" not in _payload(blocked)
    assert not (repo / ".agent" / "receipts").exists()


def test_malformed_handoffs_stop_pickup(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    specification, _ = _specification(repo, base)
    missing = tmp_path / "missing.md"
    missing.write_text("## Scope\n\nNo handoff here.\n")
    cases = [
        (missing, "handoff.section_missing"),
        (
            _description(tmp_path, "blocked.md", spec_commit=specification, status="blocked"),
            "handoff.status_blocked",
        ),
        (
            _description(tmp_path, "draft.md", spec_commit=specification, status="draft"),
            "handoff.status_invalid",
        ),
        (
            _description(tmp_path, "short.md", spec_commit=specification[:12]),
            "handoff.spec_commit_invalid",
        ),
        (
            _description(tmp_path, "absolute.md", spec_commit=specification, tdd="/docs/leaf.md"),
            "handoff.tdd_path_invalid",
        ),
        (
            _description(
                tmp_path, "prerequisite.md", spec_commit=specification, prerequisite="Handoff-00"
            ),
            "handoff.prerequisite_pending",
        ),
    ]

    for description, code in cases:
        result = _preflight(repo, description)

        assert result.returncode == 1
        payload = _payload(result)
        assert payload["status"] == "blocked"
        assert _codes(payload) == [code]
        assert "start_command" not in payload

    unreadable = _preflight(repo, tmp_path / "absent.md")

    assert unreadable.returncode == 1
    assert _codes(_payload(unreadable)) == ["handoff.description_unreadable"]


def test_invalid_or_unreachable_pins_stop_pickup(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    _specification(repo, base)

    unresolved = _preflight(repo, _description(tmp_path, "unresolved.md", spec_commit="0" * 40))

    assert unresolved.returncode == 1
    assert _codes(_payload(unresolved)) == ["handoff.spec_commit_unresolved"]

    _git(repo, "checkout", "-b", "other", "main")
    (repo / "other.txt").write_text("other\n")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-m", "other")
    other = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", BRANCH)

    unreachable = _preflight(repo, _description(tmp_path, "unreachable.md", spec_commit=other))

    assert unreachable.returncode == 1
    assert _codes(_payload(unreachable)) == ["handoff.spec_commit_unreachable"]


def test_tdd_and_manifest_mismatch_or_drift_stops_pickup(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    specification, task_id = _specification(repo, base)

    missing_tdd = _preflight(
        repo,
        _description(tmp_path, "missing-tdd.md", spec_commit=specification, tdd="docs/absent.md"),
    )

    assert missing_tdd.returncode == 1
    assert _codes(_payload(missing_tdd)) == ["handoff.tdd_missing_at_pin"]

    (repo / "docs" / "leaf.md").write_text("# Drifted\n")
    tdd_drift = _preflight(repo, _description(tmp_path, "drift.md", spec_commit=specification))

    assert tdd_drift.returncode == 1
    assert _codes(_payload(tdd_drift)) == ["handoff.tdd_checkout_drift"]
    _git(repo, "checkout", "--", "docs/leaf.md")

    manifest = repo / ".agent" / "tasks" / f"{task_id}.toml"
    manifest.write_text(manifest.read_text() + "\n")
    manifest_drift = _preflight(
        repo, _description(tmp_path, "manifest-drift.md", spec_commit=specification)
    )

    assert manifest_drift.returncode == 1
    assert _codes(_payload(manifest_drift)) == ["handoff.manifest_checkout_drift"]
    _git(repo, "checkout", "--", f".agent/tasks/{task_id}.toml")


def test_manifest_must_be_v2_and_bind_the_pinned_tdd(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    specification, _ = _specification(repo, base, tdd_sha256="0" * 64)
    mismatched = _preflight(repo, _description(tmp_path, "mismatch.md", spec_commit=specification))

    assert mismatched.returncode == 1
    assert _codes(_payload(mismatched)) == ["handoff.manifest_invalid"]

    repo_v1, base_v1 = _repo(tmp_path / "v1")
    specification_v1, _ = _specification(repo_v1, base_v1, version=1)
    v1 = _preflight(repo_v1, _description(tmp_path, "v1.md", spec_commit=specification_v1))

    assert v1.returncode == 1
    assert _codes(_payload(v1)) == ["handoff.manifest_invalid"]


def test_duplicate_manifests_for_one_tdd_stop_pickup(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    _specification(repo, base)
    digest = hashlib.sha256((repo / "docs" / "leaf.md").read_bytes()).hexdigest()
    other_task = derive_task_id("Other", digest)
    (repo / ".agent" / "tasks" / f"{other_task}.toml").write_text(
        _manifest_text(
            task_id=other_task,
            baseline=base,
            tdd_path="docs/leaf.md",
            tdd_sha256=digest,
            version=2,
        )
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "duplicate manifest")
    _git(repo, "push", "origin", BRANCH)
    specification = _git(repo, "rev-parse", "HEAD")

    ambiguous = _preflight(repo, _description(tmp_path, "ambiguous.md", spec_commit=specification))

    assert ambiguous.returncode == 1
    assert _codes(_payload(ambiguous)) == ["handoff.manifest_ambiguous"]


def test_start_command_starts_the_same_task(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    specification, task_id = _specification(repo, base)
    description = _template_description(tmp_path, spec_commit=specification)

    ready = _preflight(repo, description)

    assert ready.returncode == 0, ready.stderr
    payload = _payload(ready)
    start_command = cast(list[str], payload["start_command"])
    started = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            *start_command,
            "--state-root",
            str(tmp_path / "state"),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    assert started.returncode == 0, started.stderr
    started_payload = _payload(started)
    assert started_payload["status"] == "ready"
    assert started_payload["task_id"] == payload["task_id"] == task_id
    assert started_payload["manifest_path"] == payload["manifest_path"]


def test_preflight_rejects_a_manifest_id_not_derived_from_the_tdd(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    specification, manifest_task_id = _specification(repo, base, title="Other")
    description = _template_description(tmp_path, spec_commit=specification)

    blocked = _preflight(repo, description)

    assert blocked.returncode == 1
    payload = _payload(blocked)
    assert _codes(payload) == ["handoff.manifest_invalid"]
    diagnostic = cast(list[dict[str, str]], payload["diagnostics"])[0]
    assert diagnostic["rule"] == "task_id_matches_tdd_binding"
    assert "start_command" not in payload
    assert (repo / ".agent" / "tasks" / f"{manifest_task_id}.toml").is_file()
