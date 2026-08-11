from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASK_ID = "harness-09-followup-retrospective-verification-plan"
NO_CACHE = "no:cacheprovider"
DEVTOOLS_SRC = Path("packages/devtools/src/kotekomi_devtools")


def _run_cli(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(PROJECT_ROOT), "kotekomi-agent", *args],
        cwd=cwd or PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _require_verification_plan() -> None:
    result = _run_cli(["verification-plan", "--help"])
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "verification-plan" not in combined:
        pytest.skip("verification-plan command is not implemented yet")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _pytest_argv(path: str) -> str:
    return f'["uv", "run", "pytest", "-p", "{NO_CACHE}", "{path}"]'


def _acceptance_block(id_: str, path: str) -> list[str]:
    return [
        "[[acceptance]]",
        f'id = "{id_}"',
        f"argv = {_pytest_argv(path)}",
        "timeout_seconds = 60",
        'profile = "portable-local"',
        "",
    ]


def _manifest_text(task_id: str, tdd_sha: str, contract_sha: str) -> str:
    lines = [
        "schema_version = 1",
        f'task_id = "{task_id}"',
        'title = "H9 Followup Verification Plan"',
        'status = "ready_for_terra_high"',
        'series_id = "terra-high-harness-v1"',
        'task_class = "repository-tooling"',
        'model_profile = "terra-high-v1"',
        'baseline_revision = "BASE_PLACEHOLDER"',
        'tdd_path = "docs/agent-harness/h9-followup/README.md"',
        f'tdd_sha256 = "{tdd_sha}"',
        'goal = "Plan required local verification checks deterministically."',
        "depends_on = [",
        '  "harness-01-task-manifest-contract",',
        '  "harness-02-task-preflight",',
        '  "harness-03-task-budget-audit",',
        '  "harness-04-task-scope-audit",',
        "]",
        "allowed_paths = [",
        '  "packages/devtools/src/kotekomi_devtools/cli.py",',
        '  "packages/devtools/src/kotekomi_devtools/verification_plan.py",',
        '  "packages/devtools/AGENTS.md",',
        '  "packages/devtools/tests/unit/test_verification_plan.py",',
        "]",
        "reference_paths = [",
        '  "docs/agent-harness/h9-followup/README.md",',
        '  "docs/agent-harness/h9-followup/verification-plan-tdd.md",',
        '  "docs/agent-harness/h9-followup/operational-guidance.md",',
        '  "docs/agent-harness/h9-followup/retrospective.md",',
        '  "docs/agent-harness/h9-followup/h10-readiness.md",',
        "]",
        "stop_conditions = [",
        '  "task manifest schema changed",',
        '  "verification-plan TDD changed",',
        '  "protected verification-plan acceptance test changed",',
        "]",
        "",
        "[readiness]",
        'authority = "The H9 follow-up docs define deterministic verification planning."',
        'contract_family = "agent-harness"',
        'dominant_outcome = "verification-plan writes deterministic reports."',
        'failure_policy = "Uncovered paths exit nonzero with deterministic diagnostics."',
        'legacy_disposition = "Existing H1-H9 commands remain available."',
        'negative_proof = "The command must not run tests, mutate git, or invoke Terra."',
        'public_entry_point = "kotekomi-agent verification-plan"',
        'scope_policy = "Only planner, CLI, AGENTS guidance, and unit tests may change."',
        'side_effect_boundary = "Only requested report outputs may be written."',
        "unresolved_decisions = []",
        "",
        "[budget]",
        "maximum_production_files = 3",
        "maximum_test_files = 1",
        "maximum_production_diff_lines = 450",
        "",
        "[[protected_artifacts]]",
        'kind = "acceptance-test"',
        'path = "packages/devtools/tests/acceptance/test_verification_plan_contract.py"',
        f'sha256 = "{contract_sha}"',
        "",
    ]
    lines.extend(
        _acceptance_block(
            "h9-followup-verification-plan-contract",
            "packages/devtools/tests/acceptance/test_verification_plan_contract.py",
        )
    )
    lines.extend(
        _acceptance_block(
            "h9-goal-accountability-contract-retained",
            "packages/devtools/tests/acceptance/test_goal_accountability_contract.py",
        )
    )
    lines.extend(
        _acceptance_block(
            "h9-task-ledger-contract-retained",
            "packages/devtools/tests/acceptance/test_task_ledger_contract.py",
        )
    )
    lines.extend(
        _acceptance_block(
            "h8-task-retrospective-contract-retained",
            "packages/devtools/tests/acceptance/test_task_retrospective_contract.py",
        )
    )
    lines.extend(
        _acceptance_block(
            "h7-receipt-writer-contract-retained",
            "packages/devtools/tests/acceptance/test_receipt_writer_contract.py",
        )
    )
    lines.extend(
        [
            "[[acceptance]]",
            'id = "repository-static-checks"',
            'argv = ["uv", "run", "ruff", "check"]',
            "timeout_seconds = 60",
            'profile = "portable-local"',
            "",
            "[[acceptance]]",
            'id = "repository-type-checks"',
            'argv = ["uv", "run", "pyright"]',
            "timeout_seconds = 60",
            'profile = "portable-local"',
            "",
        ]
    )
    return "\n".join(lines)


def _manifest(repo: Path) -> Path:
    tdd = repo / "docs" / "agent-harness" / "h9-followup" / "README.md"
    _write(tdd, "# Follow-up TDD\n")
    protected_contract = (
        repo
        / "packages"
        / "devtools"
        / "tests"
        / "acceptance"
        / "test_verification_plan_contract.py"
    )
    _write(protected_contract, "# protected contract\n")
    manifest = repo / ".agent" / "tasks" / "followup.toml"
    _write(manifest, _manifest_text(TASK_ID, _sha(tdd), _sha(protected_contract)))
    return manifest


def _repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Verification Plan Test")
    _git(repo, "config", "user.email", "verification-plan@example.invalid")
    manifest = _manifest(repo)
    _write(repo / DEVTOOLS_SRC / "cli.py", "print('old')\n")
    _write(repo / DEVTOOLS_SRC / "verification_plan.py", "OLD = True\n")
    _write(repo / "packages" / "devtools" / "AGENTS.md", "# Agents\n")
    _write(
        repo / "packages" / "devtools" / "tests" / "unit" / "test_verification_plan.py",
        "# tests\n",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    base = _git(repo, "rev-parse", "HEAD")
    text = manifest.read_text(encoding="utf-8").replace("BASE_PLACEHOLDER", base)
    manifest.write_text(text, encoding="utf-8")
    _git(repo, "add", str(manifest.relative_to(repo)))
    _git(repo, "commit", "-m", "freeze manifest")
    base = _git(repo, "rev-parse", "HEAD")
    return repo, manifest, base


def _run_plan(
    repo: Path,
    manifest: Path,
    base: str,
    head: str,
    output: Path,
    markdown: Path,
) -> subprocess.CompletedProcess[str]:
    return _run_cli(
        [
            "verification-plan",
            str(manifest.relative_to(repo)),
            "--base",
            base,
            "--head",
            head,
            "--output",
            str(output),
            "--markdown",
            str(markdown),
        ],
        cwd=repo,
    )


def test_verification_plan_help_lists_core_options() -> None:
    _require_verification_plan()

    result = _run_cli(["verification-plan", "--help"])

    assert result.returncode == 0
    assert "MANIFEST" in result.stdout
    assert "--base" in result.stdout
    assert "--head" in result.stdout
    assert "--output" in result.stdout
    assert "--markdown" in result.stdout


def test_verification_plan_expands_cli_touched_path_checks(tmp_path: Path) -> None:
    _require_verification_plan()
    repo, manifest, base = _repo(tmp_path)
    _write(repo / DEVTOOLS_SRC / "cli.py", "print('new')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "change cli")
    head = _git(repo, "rev-parse", "HEAD")
    output = tmp_path / "plan.json"
    markdown = tmp_path / "plan.md"

    first = _run_plan(repo, manifest, base, head, output, markdown)

    assert first.returncode == 0, first.stderr
    payload = _json(output)
    assert payload["status"] == "ready"
    assert payload["task_id"] == TASK_ID
    assert payload["changed_paths"] == ["packages/devtools/src/kotekomi_devtools/cli.py"]
    assert payload["diagnostics"] == []
    check_ids = [item["id"] for item in cast(list[dict[str, Any]], payload["checks"])]
    assert check_ids == sorted(check_ids)
    assert "task-manifest-contract" in check_ids
    assert "task-preflight-contract" in check_ids
    assert "h9-followup-verification-plan-contract" in check_ids
    assert "h9-goal-accountability-contract-retained" in check_ids
    assert "h9-task-ledger-contract-retained" in check_ids
    assert "h8-task-retrospective-contract-retained" in check_ids
    assert "h7-receipt-writer-contract-retained" in check_ids
    assert "repository-static-checks" in check_ids
    assert "repository-type-checks" in check_ids
    markdown_text = markdown.read_text(encoding="utf-8")
    title = f"# Verification Plan: {TASK_ID}"
    assert title in markdown_text
    assert "cli.py touched" in markdown_text

    second_output = tmp_path / "second-plan.json"
    second_markdown = tmp_path / "second-plan.md"
    second = _run_plan(repo, manifest, base, head, second_output, second_markdown)

    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == second_output.read_bytes()
    assert markdown.read_bytes() == second_markdown.read_bytes()


def test_verification_plan_allows_manifest_scoped_non_cli_path(tmp_path: Path) -> None:
    _require_verification_plan()
    repo, manifest, base = _repo(tmp_path)
    _write(repo / DEVTOOLS_SRC / "verification_plan.py", "NEW = True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "change planner")
    head = _git(repo, "rev-parse", "HEAD")
    output = tmp_path / "plan.json"
    markdown = tmp_path / "plan.md"

    result = _run_plan(repo, manifest, base, head, output, markdown)

    assert result.returncode == 0, result.stderr
    payload = _json(output)
    assert payload["status"] == "ready"
    assert payload["diagnostics"] == []
    check_ids = [item["id"] for item in cast(list[dict[str, Any]], payload["checks"])]
    assert "h9-followup-verification-plan-contract" in check_ids
    assert "repository-static-checks" in check_ids
    assert "repository-type-checks" in check_ids
    assert "task-manifest-contract" not in check_ids
    assert "task-preflight-contract" not in check_ids


def test_verification_plan_fails_closed_for_uncovered_path(tmp_path: Path) -> None:
    _require_verification_plan()
    repo, manifest, base = _repo(tmp_path)
    _write(repo / "unplanned.txt", "surprise\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "uncovered")
    head = _git(repo, "rev-parse", "HEAD")
    output = tmp_path / "plan.json"
    markdown = tmp_path / "plan.md"

    result = _run_plan(repo, manifest, base, head, output, markdown)

    assert result.returncode == 1
    payload = _json(output)
    assert payload["status"] == "not_ready"
    diagnostics = cast(list[dict[str, str]], payload["diagnostics"])
    assert diagnostics == [
        {
            "code": "verification_plan.uncovered_changed_path",
            "location": "/changed_paths/0",
            "rule": "changed_paths_require_manifest_or_shared_rule",
        }
    ]
    assert "unplanned.txt" in markdown.read_text(encoding="utf-8")
