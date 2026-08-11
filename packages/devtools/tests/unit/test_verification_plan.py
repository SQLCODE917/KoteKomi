from __future__ import annotations

import json
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
    ]
    assert [check.source for check in plan.checks] == [
        "manifest",
        "quality",
        "quality",
        "retained",
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
