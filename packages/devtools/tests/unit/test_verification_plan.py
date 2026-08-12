from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import kotekomi_devtools.verification_plan as verification_plan
import pytest
from kotekomi_devtools.verification_plan import build_verification_plan, write_verification_plan


def test_plan_combines_manifest_retained_and_quality_checks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(verification_plan, "_changed_paths", _planner_path)

    plan = build_verification_plan(manifest, base_revision="base", head_revision="head")

    assert plan.ready
    assert [check.id for check in plan.checks] == [
        "feature-contract",
        "repository-static-checks",
        "repository-type-checks",
        "retained-contract-retained",
        "verification-plan-acceptance-contract",
        "verification-plan-unit-contract",
    ]
    assert [check.source for check in plan.checks] == [
        "manifest",
        "quality",
        "quality",
        "retained",
        "touched-path",
        "touched-path",
    ]


def test_plan_adds_shared_cli_contracts_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(verification_plan, "_changed_paths", _cli_and_uncovered_paths)

    plan = build_verification_plan(manifest, base_revision="base", head_revision="head")

    assert not plan.ready
    assert plan.exit_code == 1
    assert [check.id for check in plan.checks] == [
        "cli-delimiter-regression-contract",
        "feature-contract",
        "repository-static-checks",
        "repository-type-checks",
        "retained-contract-retained",
        "task-manifest-contract",
        "task-preflight-contract",
    ]
    assert plan.diagnostics[0].as_json() == {
        "code": "verification_plan.uncovered_changed_path",
        "location": "/changed_paths/1",
        "rule": "changed_paths_require_manifest_or_shared_rule",
    }


def test_written_reports_are_byte_stable_and_end_with_newlines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(verification_plan, "_changed_paths", _planner_path)
    first_json, first_markdown = tmp_path / "first.json", tmp_path / "first.md"
    second_json, second_markdown = tmp_path / "second.json", tmp_path / "second.md"

    write_verification_plan(
        manifest,
        base_revision="base",
        head_revision="head",
        output=first_json,
        markdown=first_markdown,
    )
    write_verification_plan(
        manifest,
        base_revision="base",
        head_revision="head",
        output=second_json,
        markdown=second_markdown,
    )

    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_markdown.read_bytes() == second_markdown.read_bytes()
    assert first_json.read_text(encoding="utf-8").endswith("\n")
    assert first_markdown.read_text(encoding="utf-8").endswith("\n")
    assert list(json.loads(first_json.read_text(encoding="utf-8"))) == sorted(
        json.loads(first_json.read_text(encoding="utf-8"))
    )


def _manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "task.toml"
    manifest.write_text(
        """\
task_id = "task"
allowed_paths = ["packages/devtools/src/kotekomi_devtools/verification_plan.py"]

[[acceptance]]
id = "feature-contract"
argv = ["uv", "run", "pytest", "feature.py"]

[[acceptance]]
id = "retained-contract-retained"
argv = ["uv", "run", "pytest", "retained.py"]
""",
        encoding="utf-8",
    )
    return manifest


def _planner_path(base_revision: str, head_revision: str) -> tuple[str, ...]:
    del base_revision, head_revision
    return ("packages/devtools/src/kotekomi_devtools/verification_plan.py",)


def _cli_and_uncovered_paths(base_revision: str, head_revision: str) -> tuple[str, ...]:
    del base_revision, head_revision
    return ("packages/devtools/src/kotekomi_devtools/cli.py", "uncovered.txt")


def _h14_coverage_manifest(tmp_path: Path, allowed_paths: list[str]) -> Path:
    manifest = tmp_path / "h14-manifest.toml"
    allowed = "".join(f'  "{path}",\n' for path in allowed_paths)
    manifest.write_text(
        (
            "schema_version = 1\n"
            'task_id = "h14-fixture"\n'
            "allowed_paths = [\n"
            f"{allowed}"
            "]\n"
            "reference_paths = []\n"
            "\n"
            "[[acceptance]]\n"
            'id = "feature-contract"\n'
            'argv = ["uv", "run", "pytest", "-p", "no:cacheprovider", "feature.py"]\n'
            "timeout_seconds = 60\n"
            'profile = "portable-local"\n'
        ),
        encoding="utf-8",
    )
    return manifest


def _h14_coverage_changed_paths(
    paths: tuple[str, ...],
) -> Callable[[str, str], tuple[str, ...]]:
    def _changed_paths(base_revision: str, head_revision: str) -> tuple[str, ...]:
        del base_revision, head_revision
        return paths

    return _changed_paths


def test_h14_coverage_known_harness_paths_add_required_contracts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cases = [
        (
            "packages/devtools/src/kotekomi_devtools/step_scripts.py",
            {
                "step-scripts-acceptance-contract",
                "step-scripts-unit-contract",
            },
        ),
        (
            "packages/devtools/src/kotekomi_devtools/task_lifecycle.py",
            {
                "task-lifecycle-acceptance-contract",
                "task-lifecycle-unit-contract",
            },
        ),
        (
            "packages/devtools/src/kotekomi_devtools/verification_execution.py",
            {"verification-execution-contract"},
        ),
        (
            "packages/devtools/src/kotekomi_devtools/verification_plan.py",
            {
                "verification-plan-acceptance-contract",
                "verification-plan-unit-contract",
            },
        ),
    ]

    for index, (changed_path, expected_ids) in enumerate(cases):
        case_dir = tmp_path / f"h14-case-{index}"
        case_dir.mkdir()
        manifest = _h14_coverage_manifest(case_dir, [changed_path])
        monkeypatch.setattr(
            verification_plan,
            "_changed_paths",
            _h14_coverage_changed_paths((changed_path,)),
        )

        plan = build_verification_plan(
            manifest,
            base_revision="base",
            head_revision="head",
        )

        assert plan.ready
        check_ids = {check.id for check in plan.checks}
        assert expected_ids.issubset(check_ids)


def test_h14_coverage_unknown_path_still_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = _h14_coverage_manifest(
        tmp_path,
        ["packages/devtools/src/kotekomi_devtools/known.py"],
    )
    monkeypatch.setattr(
        verification_plan,
        "_changed_paths",
        _h14_coverage_changed_paths(
            ("packages/devtools/src/kotekomi_devtools/uncovered.py",)
        ),
    )

    plan = build_verification_plan(
        manifest,
        base_revision="base",
        head_revision="head",
    )

    assert not plan.ready
    check_ids = {check.id for check in plan.checks}
    assert "step-scripts-acceptance-contract" not in check_ids
    assert "verification-plan-unit-contract" not in check_ids
    assert plan.diagnostics
