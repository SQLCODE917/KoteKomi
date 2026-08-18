from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest

from . import _oracle_fixtures as oracle

REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST = REPO_ROOT / ".agent/tasks/harness-06-task-lifecycle-state-machine.toml"

ALLOWED_CANDIDATE_PATHS = (
    "packages/devtools/src/kotekomi_devtools/cli.py",
    "packages/devtools/src/kotekomi_devtools/task_lifecycle.py",
    "packages/devtools/tests/unit/test_task_lifecycle.py",
)


def _run_cli(args: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(REPO_ROOT), "kotekomi-agent", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _json_result(args: list[str], cwd: Path = REPO_ROOT) -> tuple[int, dict[str, Any]]:
    result = _run_cli(args, cwd=cwd)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"stdout was not JSON.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ) from exc

    return result.returncode, payload


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    return result.stdout.strip()


def _require_lifecycle_check() -> None:
    result = _run_cli(["--help"])
    if "lifecycle-check" not in result.stdout:
        pytest.skip("lifecycle-check is not implemented yet")


def _assert_common_payload(payload: dict[str, Any], phase: str) -> None:
    assert payload["schema_version"] == 1
    assert payload["task_id"] == "harness-06-task-lifecycle-state-machine"
    assert payload["phase"] == phase
    assert payload["status"] in {"ready", "not_ready", "invalid"}
    assert isinstance(payload["diagnostics"], list)
    assert isinstance(payload["required_checks"], list)
    assert isinstance(payload["observed_records"], list)


def _diagnostic_codes(payload: dict[str, Any]) -> set[str]:
    return {item["code"] for item in payload["diagnostics"]}


def _protected_paths() -> tuple[str, ...]:
    manifest_raw: object = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = cast(dict[str, object], manifest_raw)
    paths: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            value_dict = cast(dict[object, object], value)
            protected = value_dict.get("protected_artifacts")
            if isinstance(protected, list):
                protected_items = cast(list[object], protected)
                for raw_item in protected_items:
                    if isinstance(raw_item, dict):
                        item = cast(dict[object, object], raw_item)
                        path_value = item.get("path")
                        if isinstance(path_value, str):
                            paths.append(path_value)
            for child in value_dict.values():
                visit(child)
        elif isinstance(value, list):
            children = cast(list[object], value)
            for child in children:
                visit(child)

    visit(manifest)

    assert paths, "manifest did not expose protected_artifacts"
    return tuple(dict.fromkeys(paths))


def _copy_protected_artifacts(repo: Path) -> None:
    for relative in _protected_paths():
        source = REPO_ROOT / relative
        target = repo / relative

        if not source.is_file():
            raise AssertionError(f"protected artifact missing in source repo: {relative}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def _init_lifecycle_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "lifecycle-repo"
    repo.mkdir(parents=True)

    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.email", "h6@example.invalid")
    _git(repo, "config", "user.name", "H6 Test")

    _copy_protected_artifacts(repo)

    for relative in ALLOWED_CANDIDATE_PATHS:
        oracle.write_fixture_text(repo / relative, f"base fixture for {relative}\n")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")

    return repo


def _make_candidate_commit(repo: Path) -> tuple[str, str]:
    base = _git(repo, "rev-parse", "HEAD")

    for relative in ALLOWED_CANDIDATE_PATHS:
        oracle.write_fixture_text(
            repo / relative,
            f"base fixture for {relative}\ncandidate fixture for {relative}\n",
        )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "candidate")
    head = _git(repo, "rev-parse", "HEAD")

    return base, head


def _make_merge_commit(repo: Path) -> tuple[str, str, str]:
    main_base = _git(repo, "rev-parse", "HEAD")

    _git(repo, "switch", "-c", "verified")
    oracle.write_fixture_text(repo / "verified.txt", "verified\n")
    _git(repo, "add", "verified.txt")
    _git(repo, "commit", "-m", "verified")
    verified = _git(repo, "rev-parse", "HEAD")

    _git(repo, "switch", "main")
    _git(repo, "merge", "--no-ff", "verified", "-m", "merge verified")
    merge = _git(repo, "rev-parse", "HEAD")

    return main_base, verified, merge


def _make_direct_commit(repo: Path) -> tuple[str, str]:
    main_base = _git(repo, "rev-parse", "HEAD")
    oracle.write_fixture_text(repo / "direct.txt", "direct\n")
    _git(repo, "add", "direct.txt")
    _git(repo, "commit", "-m", "direct")
    return main_base, _git(repo, "rev-parse", "HEAD")


def _make_octopus_commit(repo: Path) -> tuple[str, str, str]:
    main_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-c", "first")
    oracle.write_fixture_text(repo / "first.txt", "first\n")
    _git(repo, "add", "first.txt")
    _git(repo, "commit", "-m", "first")
    verified = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "main")
    _git(repo, "switch", "-c", "second", main_base)
    oracle.write_fixture_text(repo / "second.txt", "second\n")
    _git(repo, "add", "second.txt")
    _git(repo, "commit", "-m", "second")
    _git(repo, "switch", "main")
    _git(repo, "merge", "--no-ff", "first", "second", "-m", "octopus")
    return main_base, verified, _git(repo, "rev-parse", "HEAD")


def test_lifecycle_check_help_lists_phase_values() -> None:
    _require_lifecycle_check()

    result = _run_cli(["lifecycle-check", "--help"])

    assert result.returncode == 0
    assert "--phase" in result.stdout
    assert "spec" in result.stdout
    assert "candidate" in result.stdout
    assert "verified" in result.stdout
    assert "main" in result.stdout


def test_spec_phase_reports_head_not_execution_base_after_head_moves() -> None:
    _require_lifecycle_check()

    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "spec",
        ]
    )

    _assert_common_payload(payload, "spec")
    assert code != 0
    assert payload["status"] in {"not_ready", "invalid"}

    if payload["status"] == "not_ready":
        assert "validate-task" in payload["required_checks"]
        assert "preflight-task" in payload["required_checks"]
        assert "task_lifecycle.head_not_execution_base" in _diagnostic_codes(payload)
    else:
        assert payload["diagnostics"]


def test_candidate_phase_requires_revision_range() -> None:
    _require_lifecycle_check()

    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "candidate",
        ]
    )

    _assert_common_payload(payload, "candidate")
    assert code != 0
    assert payload["status"] == "invalid"
    assert "task_lifecycle.missing_revision_range" in _diagnostic_codes(payload)


def test_candidate_phase_accepts_clean_revision_range(tmp_path: Path) -> None:
    _require_lifecycle_check()

    repo = _init_lifecycle_repo(tmp_path)
    base, head = _make_candidate_commit(repo)

    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "candidate",
            "--base",
            base,
            "--head",
            head,
        ],
        cwd=repo,
    )

    _assert_common_payload(payload, "candidate")
    assert code == 0
    assert payload["status"] == "ready"
    assert "scope-audit" in payload["required_checks"]
    assert "budget-audit" in payload["required_checks"]
    assert "protected-artifacts" in payload["required_checks"]


def test_verified_phase_reports_missing_candidate_records(tmp_path: Path) -> None:
    _require_lifecycle_check()

    records_dir = tmp_path / "records"
    records_dir.mkdir()

    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "verified",
            "--records-dir",
            str(records_dir),
        ]
    )

    _assert_common_payload(payload, "verified")
    assert code != 0
    assert payload["status"] == "not_ready"
    assert "candidate-commit-record" in payload["required_checks"]
    assert "candidate-ci-record" in payload["required_checks"]
    assert "task_lifecycle.record_missing" in _diagnostic_codes(payload)


def test_verified_phase_accepts_present_candidate_records(tmp_path: Path) -> None:
    _require_lifecycle_check()

    records_dir = tmp_path / "records"
    oracle.write_fixture_text(
        records_dir / "candidate-commit.json",
        json.dumps({"schema_version": 1, "record_kind": "candidate-commit"}) + "\n",
    )
    oracle.write_fixture_text(
        records_dir / "candidate-ci.json",
        json.dumps({"schema_version": 1, "record_kind": "candidate-ci"}) + "\n",
    )

    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "verified",
            "--records-dir",
            str(records_dir),
        ]
    )

    _assert_common_payload(payload, "verified")
    assert code == 0
    assert payload["status"] == "ready"
    assert {item["name"] for item in payload["observed_records"]} == {
        "candidate-commit.json",
        "candidate-ci.json",
    }


def test_main_phase_verifies_direct_and_merge_topology(tmp_path: Path) -> None:
    _require_lifecycle_check()

    repo = _init_lifecycle_repo(tmp_path)
    main_base, verified, merge = _make_merge_commit(repo)

    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "main",
            "--main-base",
            main_base,
            "--verified",
            verified,
            "--head",
            merge,
        ],
        cwd=repo,
    )

    _assert_common_payload(payload, "main")
    assert code == 0
    assert payload["status"] == "ready"
    assert "promotion-topology" in payload["required_checks"]
    assert "main-ci-record" in payload["required_checks"]

    direct_repo = _init_lifecycle_repo(tmp_path / "direct")
    main_base, direct = _make_direct_commit(direct_repo)
    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "main",
            "--main-base",
            main_base,
            "--verified",
            direct,
            "--head",
            direct,
        ],
        cwd=direct_repo,
    )
    _assert_common_payload(payload, "main")
    assert code == 0
    assert payload["status"] == "ready"


def test_main_phase_rejects_invalid_promotion_topology(tmp_path: Path) -> None:
    _require_lifecycle_check()

    direct_repo = _init_lifecycle_repo(tmp_path / "direct")
    main_base, direct = _make_direct_commit(direct_repo)
    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "main",
            "--main-base",
            main_base,
            "--verified",
            main_base,
            "--head",
            direct,
        ],
        cwd=direct_repo,
    )
    assert code == 1
    assert "task_lifecycle.direct_promotion_mismatch" in _diagnostic_codes(payload)
    assert "main_requires_expected_direct_promotion" in _h11_diagnostic_rules(payload)

    merge_repo = _init_lifecycle_repo(tmp_path / "merge")
    main_base, verified, merge = _make_merge_commit(merge_repo)
    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "main",
            "--main-base",
            main_base,
            "--verified",
            main_base,
            "--head",
            merge,
        ],
        cwd=merge_repo,
    )
    assert code == 1
    assert "task_lifecycle.merge_parent_mismatch" in _diagnostic_codes(payload)
    assert "main_requires_expected_merge_parents" in _h11_diagnostic_rules(payload)

    root_repo = _init_lifecycle_repo(tmp_path / "root")
    root = _git(root_repo, "rev-parse", "HEAD")
    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "main",
            "--main-base",
            root,
            "--verified",
            root,
            "--head",
            root,
        ],
        cwd=root_repo,
    )
    assert code == 1
    assert "task_lifecycle.unsupported_promotion_topology" in _diagnostic_codes(payload)
    assert "main_requires_direct_or_merge_promotion" in _h11_diagnostic_rules(payload)

    octopus_repo = _init_lifecycle_repo(tmp_path / "octopus")
    main_base, verified, octopus = _make_octopus_commit(octopus_repo)
    code, payload = _json_result(
        [
            "lifecycle-check",
            str(MANIFEST),
            "--phase",
            "main",
            "--main-base",
            main_base,
            "--verified",
            verified,
            "--head",
            octopus,
        ],
        cwd=octopus_repo,
    )
    assert code == 1
    assert "task_lifecycle.unsupported_promotion_topology" in _diagnostic_codes(payload)


def _h11_diagnostic_rules(payload: dict[str, Any]) -> set[str]:
    diagnostics = cast(list[object], payload.get("diagnostics", []))
    rules: set[str] = set()
    for item in diagnostics:
        assert isinstance(item, dict)
        diagnostic = cast(dict[str, object], item)
        rule = diagnostic.get("rule")
        if isinstance(rule, str):
            rules.add(rule)
    return rules


def test_main_phase_reports_specific_missing_revision_arguments() -> None:
    _require_lifecycle_check()

    cases: list[tuple[list[str], set[str]]] = [
        (
            [],
            {
                "main_requires_main_base",
                "main_requires_verified",
                "main_requires_head",
            },
        ),
        (
            ["--main-base", "HEAD", "--head", "HEAD"],
            {"main_requires_verified"},
        ),
        (
            ["--verified", "HEAD", "--head", "HEAD"],
            {"main_requires_main_base"},
        ),
        (
            ["--main-base", "HEAD", "--verified", "HEAD"],
            {"main_requires_head"},
        ),
    ]

    for extra_args, expected_rules in cases:
        code, payload = _json_result(
            [
                "lifecycle-check",
                str(MANIFEST),
                "--phase",
                "main",
                *extra_args,
            ]
        )
        assert code == 1
        _assert_common_payload(payload, "main")
        assert expected_rules <= _h11_diagnostic_rules(payload)


def test_agents_guidance_requires_candidate_lifecycle_before_dogfood_and_ci() -> None:
    agents_text = (Path(__file__).resolve().parents[2] / "AGENTS.md").read_text(encoding="utf-8")
    normalized = " ".join(agents_text.lower().split())

    assert "candidate lifecycle" in normalized
    assert "before dogfood verification execution" in normalized
    assert "before candidate ci" in normalized
