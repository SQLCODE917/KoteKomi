from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST = REPO_ROOT / ".agent/tasks/harness-06-task-lifecycle-state-machine.toml"
ENTRYPOINT = "from kotekomi_devtools.cli import entrypoint; raise SystemExit(entrypoint())"
H5_MAIN_MERGE = "37e6b8c886fdb39288f1c88bc26ede7bbf704b50"
H5_MAIN_PARENT = "63fa7cae7c4a5f03619ceeec953aee7fbf7eea53"
H5_VERIFIED = "17bb8e2b77ab2b5edaf5a540fc6ac28c855dcfed"


def _run(*arguments: str) -> tuple[int, dict[str, Any], str]:
    environment = os.environ | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(REPO_ROOT / "packages/devtools/src"),
    }
    result = subprocess.run(
        (sys.executable, "-c", ENTRYPOINT, "lifecycle-check", str(MANIFEST), *arguments),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    return result.returncode, json.loads(result.stdout), result.stdout


def test_candidate_phase_rejects_missing_and_ambiguous_revision_ranges() -> None:
    code, missing, _ = _run("--phase", "candidate")

    assert code != 0
    assert missing["status"] == "invalid"
    assert missing["diagnostics"] == [
        {
            "code": "task_lifecycle.missing_revision_range",
            "location": "/base",
            "rule": "candidate_requires_base_and_head_or_worktree",
        }
    ]

    code, ambiguous, _ = _run(
        "--phase",
        "candidate",
        "--base",
        H5_MAIN_PARENT,
        "--head",
        H5_MAIN_MERGE,
        "--worktree",
    )

    assert code != 0
    assert ambiguous["status"] == "invalid"
    assert ambiguous["diagnostics"][0]["code"] == "task_lifecycle.ambiguous_revision_range"


def test_verified_phase_requires_json_object_records(tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir()
    (records_dir / "candidate-commit.json").write_text("{}\n", encoding="utf-8")
    (records_dir / "candidate-ci.json").write_text("[]\n", encoding="utf-8")

    code, payload, output = _run("--phase", "verified", "--records-dir", str(records_dir))

    assert code != 0
    assert payload["status"] == "invalid"
    assert payload["schema_version"] == 1
    assert payload["diagnostics"] == [
        {
            "code": "task_lifecycle.record_invalid",
            "location": "/records/candidate-ci.json",
            "rule": "verified_requires_candidate_records",
        }
    ]
    assert [record["name"] for record in payload["observed_records"]] == [
        "candidate-commit.json",
        "candidate-ci.json",
    ]
    assert output.count("\n") == 1


def test_main_phase_rejects_unexpected_merge_parents() -> None:
    code, payload, _ = _run(
        "--phase",
        "main",
        "--main-base",
        H5_MAIN_PARENT,
        "--verified",
        H5_MAIN_PARENT,
        "--head",
        H5_MAIN_MERGE,
    )

    assert code != 0
    assert payload["status"] in {"not_ready", "invalid"}
    assert payload["diagnostics"]


def _h11_rules(payload: dict[str, Any]) -> set[str]:
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
    code, all_missing, _ = _run("--phase", "main")
    assert code == 1
    assert {
        "main_requires_main_base",
        "main_requires_verified",
        "main_requires_head",
    } <= _h11_rules(all_missing)

    code, missing_verified, _ = _run(
        "--phase",
        "main",
        "--main-base",
        "HEAD",
        "--head",
        "HEAD",
    )
    assert code == 1
    assert {"main_requires_verified"} <= _h11_rules(missing_verified)
    assert "main_requires_main_base" not in _h11_rules(missing_verified)
    assert "main_requires_head" not in _h11_rules(missing_verified)

    code, missing_main_base, _ = _run(
        "--phase",
        "main",
        "--verified",
        "HEAD",
        "--head",
        "HEAD",
    )
    assert code == 1
    assert {"main_requires_main_base"} <= _h11_rules(missing_main_base)
    assert "main_requires_verified" not in _h11_rules(missing_main_base)
    assert "main_requires_head" not in _h11_rules(missing_main_base)

    code, missing_head, _ = _run(
        "--phase",
        "main",
        "--main-base",
        "HEAD",
        "--verified",
        "HEAD",
    )
    assert code == 1
    assert {"main_requires_head"} <= _h11_rules(missing_head)
    assert "main_requires_main_base" not in _h11_rules(missing_head)
    assert "main_requires_verified" not in _h11_rules(missing_head)
