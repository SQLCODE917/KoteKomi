from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from kotekomi_devtools.goal_accountability import check_goals, write_goal_report


def test_goal_coverage_counts_states_and_validates_relative_evidence(tmp_path: Path) -> None:
    records = tmp_path / "records"
    evidence = records / "main-ci.json"
    _write_json(evidence, {"result": "verified"})
    goals = tmp_path / "goals.json"
    _write_json(
        goals,
        {
            "schema_version": 1,
            "task_id": "task",
            "goals": [
                {
                    "id": "G1",
                    "statement": "A goal.",
                    "disposition": "in_scope",
                    "evidence": [{"path": "main-ci.json", "sha256": _sha256(evidence)}],
                },
                {
                    "id": "G2",
                    "statement": "A deferred goal.",
                    "disposition": "deferred",
                    "reason": "Later work.",
                    "future_task": "task-two",
                },
                {
                    "id": "G3",
                    "statement": "An excluded goal.",
                    "disposition": "out_of_scope",
                    "reason": "Separate concern.",
                },
            ],
        },
    )

    report = check_goals(goals, records)

    assert report.ready
    assert report.as_json()["counts"] == {
        "total": 3,
        "in_scope": 1,
        "deferred": 1,
        "out_of_scope": 1,
        "met": 1,
        "unmet": 0,
    }


def test_goal_coverage_reports_every_unmet_goal_and_writes_stable_outputs(tmp_path: Path) -> None:
    goals = tmp_path / "goals.json"
    _write_json(
        goals,
        {
            "schema_version": 1,
            "task_id": "task",
            "goals": [
                {"id": "G1", "statement": "A goal.", "disposition": "in_scope", "evidence": []},
                {"id": "G2", "statement": "Later.", "disposition": "deferred"},
                {"id": "G3", "statement": "Excluded.", "disposition": "out_of_scope"},
            ],
        },
    )
    first_json, first_markdown = tmp_path / "one.json", tmp_path / "one.md"
    second_json, second_markdown = tmp_path / "two.json", tmp_path / "two.md"

    report = write_goal_report(
        goals, tmp_path / "records", output=first_json, markdown=first_markdown
    )
    write_goal_report(goals, tmp_path / "records", output=second_json, markdown=second_markdown)

    assert not report.ready
    diagnostics = cast(list[dict[str, str]], report.as_json()["diagnostics"])
    assert [item["code"] for item in diagnostics] == [
        "h9.goal.evidence_missing",
        "h9.goal.deferred_reason_missing",
        "h9.goal.future_task_missing",
        "h9.goal.out_of_scope_reason_missing",
    ]
    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_markdown.read_bytes() == second_markdown.read_bytes()
    assert first_markdown.read_text(encoding="utf-8").endswith("\n")


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
