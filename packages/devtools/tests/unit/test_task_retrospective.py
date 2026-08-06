from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_devtools.task_retrospective import (
    TaskRetrospectiveError,
    write_task_retrospective,
)


def test_retrospective_uses_one_task_and_combines_supported_metrics(tmp_path: Path) -> None:
    records = tmp_path / "records"
    support = records / "support.json"
    _write_json(support, {"support": True})
    _write_json(
        records / "start.json",
        _record("candidate-start", "candidate_started", "2026-08-06T10:00:00Z"),
    )
    _write_json(
        records / "audit.json",
        _record(
            "candidate-audit",
            "passed",
            "2026-08-06T11:00:00+01:00",
            input_records={"support": {"path": str(support), "sha256": _sha256(support)}},
            changed_paths=[{"path": "z.py"}],
            audits={
                "scope": {"status": "clean", "changed_paths": ["a.py"]},
                "budget": {"status": "within_budget", "totals": {"production_diff_lines": 12}},
            },
            local_checks={"local": "passed"},
            retained_checks={"retained": "passed"},
        ),
    )
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"

    result = write_task_retrospective(records, output=output, markdown=markdown)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.task_id == "task"
    assert payload["records"]["total"] == 2
    assert payload["timeline"]["duration_seconds"] == 0
    assert payload["audits"] == {
        "scope_statuses": {"clean": 1},
        "budget_statuses": {"within_budget": 1},
        "production_diff_lines": 12,
    }
    assert payload["checks"]["passed"] == 2
    assert payload["changed_paths"] == ["a.py", "z.py"]
    assert markdown.read_text(encoding="utf-8").endswith("\n")


def test_retrospective_rejects_bad_local_digest_unless_incomplete(tmp_path: Path) -> None:
    records = tmp_path / "records"
    support = records / "support.txt"
    support.parent.mkdir()
    support.write_text("before\n", encoding="utf-8")
    _write_json(
        records / "record.json",
        _record(
            "candidate-start",
            "candidate_started",
            "2026-08-06T10:00:00Z",
            artifacts={"support": {"path": str(support), "sha256": _sha256(support)}},
        ),
    )
    support.write_text("after\n", encoding="utf-8")
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"

    with pytest.raises(TaskRetrospectiveError, match="sha256"):
        write_task_retrospective(records, output=output, markdown=markdown)

    write_task_retrospective(records, output=output, markdown=markdown, allow_incomplete=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["diagnostics"][0]["code"] == "retrospective.sha256_mismatch"


def test_retrospective_allows_missing_records_directory_only_when_requested(tmp_path: Path) -> None:
    output = tmp_path / "output.json"
    markdown = tmp_path / "output.md"

    with pytest.raises(TaskRetrospectiveError, match="records directory"):
        write_task_retrospective(tmp_path / "missing", output=output, markdown=markdown)

    write_task_retrospective(
        tmp_path / "missing",
        output=output,
        markdown=markdown,
        task_id="task",
        allow_incomplete=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["task_id"] == "task"
    assert {item["code"] for item in payload["diagnostics"]} == {
        "retrospective.missing_records_directory",
        "retrospective.no_matching_records",
    }


def _record(
    record_kind: str,
    result: str,
    created_at: str,
    **extra: object,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_kind": record_kind,
        "task_id": "task",
        "result": result,
        "created_at": created_at,
        **extra,
    }


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
