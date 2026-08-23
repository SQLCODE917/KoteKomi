import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from kotekomi_devtools import tdd_metrics


def _event(outcome: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "phase": "verification",
        "evidence_type": "run_check",
        "subject_id": "typecheck",
        "evidence_outcome": outcome,
    }


def test_repair_history_counts_each_failed_event_before_success() -> None:
    assert tdd_metrics.repair_history([_event("failed"), _event("failed"), _event("passed")]) == (
        True,
        2,
    )


def test_repair_history_does_not_count_an_unrepaired_failure() -> None:
    assert tdd_metrics.repair_history([_event("failed")]) == (True, 0)


def test_repair_history_marks_schema_v1_events_unavailable() -> None:
    assert tdd_metrics.repair_history([{"evidence_type": "run_check", "status": "ready"}]) == (
        False,
        0,
    )


def test_metrics_requires_main_promotion_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = "task"
    run = "task-run-001"
    state = tmp_path / "state"
    snapshot = state / "experiments" / task / "spec" / "tdd-snapshot.md"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("# TDD\n")
    tdd_sha256 = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (snapshot.parent / "tdd-binding.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "task_id": task,
                "primary_tdd_path": "docs/tdd.md",
                "tdd_paths": ["docs/tdd.md"],
                "tdd_snapshot_path": str(snapshot),
                "tdd_sha256": tdd_sha256,
            }
        )
    )
    runs = state / "experiments" / task / "runs"
    runs.mkdir(parents=True)
    (runs / "index.json").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "implementation_run_id": run,
                        "ordinal": 1,
                        "status": "active",
                    }
                ]
            }
        )
    )

    def promotion_only_entries(_root: Path, _task: str, _run: str) -> list[dict[str, Any]]:
        return [
            {
                "evidence_type": "main_promotion",
                "path_scope": "state",
                "path": "unused.json",
            }
        ]

    monkeypatch.setattr(tdd_metrics, "validated_entries", promotion_only_entries)

    code, collection = tdd_metrics.tdd_metrics("docs/tdd.md", state_root_path=state, run_id=run)

    result = collection["metrics"][0]
    assert code == 0
    assert result["status"] == "partial"
    assert result["present_evidence_count"] == 1
    assert result["missing_evidence_count"] == 13
    assert result["required_evidence_count"] == 14
    assert "main_promotion" not in {item["rule"] for item in result["diagnostics"]}


def test_metrics_accepts_task_result_instead_of_receipt_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = "task"
    run = "task-run-001"
    state = tmp_path / "state"
    required = {
        "tdd_binding",
        "task_manifest",
        "task_manifest_validation",
        "candidate_lifecycle",
        "candidate_commit",
        "verification_plan",
        "verify_checks",
        "candidate_ci",
        "main_promotion",
        "main_lifecycle",
        "main_ci",
        "cleanup",
        "task_result",
    }
    entries: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {
        "verification_plan": {"planned_checks": []},
        "verify_checks": {
            "executed_check_count": 0,
            "verified_check_count": 0,
            "failed_check_count": 0,
        },
        "candidate_lifecycle": {"ready": True, "diagnostics": []},
        "main_lifecycle": {"ready": True, "diagnostics": []},
        "candidate_ci": {"conclusion": "failure"},
        "main_ci": {"conclusion": "success"},
        "cleanup": {"branch_cleanup_complete": True},
        "task_result": {"outcome": "completed"},
    }
    for evidence_type in required:
        path = state / f"{evidence_type}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payloads.get(evidence_type, {})))
        entries.append({"evidence_type": evidence_type, "path_scope": "state", "path": path.name})
    snapshot = state / "experiments" / task / "spec" / "tdd-snapshot.md"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("# TDD\n")
    tdd_sha256 = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (snapshot.parent / "tdd-binding.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "task_id": task,
                "primary_tdd_path": "docs/tdd.md",
                "tdd_paths": ["docs/tdd.md"],
                "tdd_snapshot_path": str(snapshot),
                "tdd_sha256": tdd_sha256,
            }
        )
    )
    runs = state / "experiments" / task / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "index.json").write_text(
        json.dumps({"runs": [{"implementation_run_id": run, "ordinal": 1, "status": "active"}]})
    )

    def entries_for(_root: Path, _task: str, _run: str) -> list[dict[str, Any]]:
        return entries

    monkeypatch.setattr(tdd_metrics, "validated_entries", entries_for)
    _, collection = tdd_metrics.tdd_metrics("docs/tdd.md", state_root_path=state, run_id=run)
    result = collection["metrics"][0]

    assert result["status"] == "complete"
    assert result["missing_evidence_count"] == 0


def test_metrics_report_scope_discovery_supersession_without_missing_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = "task"
    run = "task-run-001"
    state = tmp_path / "state"
    required = {
        "tdd_binding",
        "task_manifest",
        "task_manifest_validation",
        "task_result",
        "cleanup",
    }
    entries: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {
        "task_result": {
            "outcome": "superseded",
            "supersession_reason": "scope_discovery",
            "successor_task_id": "successor",
            "successor_run_id": "successor-run-001",
        },
        "cleanup": {"branch_cleanup_complete": True},
    }
    for evidence_type in required:
        path = state / f"{evidence_type}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payloads.get(evidence_type, {})))
        entries.append({"evidence_type": evidence_type, "path_scope": "state", "path": path.name})
    snapshot = state / "experiments" / task / "spec" / "tdd-snapshot.md"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("# TDD\n")
    tdd_sha256 = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (snapshot.parent / "tdd-binding.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "task_id": task,
                "primary_tdd_path": "docs/tdd.md",
                "tdd_paths": ["docs/tdd.md"],
                "tdd_snapshot_path": str(snapshot),
                "tdd_sha256": tdd_sha256,
            }
        )
    )
    runs = state / "experiments" / task / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "index.json").write_text(
        json.dumps({"runs": [{"implementation_run_id": run, "ordinal": 1, "status": "active"}]})
    )

    def entries_for(_root: Path, _task: str, _run: str) -> list[dict[str, Any]]:
        return entries

    monkeypatch.setattr(tdd_metrics, "validated_entries", entries_for)

    _, collection = tdd_metrics.tdd_metrics("docs/tdd.md", state_root_path=state, run_id=run)

    result = collection["metrics"][0]
    assert result["status"] == "superseded"
    assert result["scope_discovery_supersession_count"] == 1
    assert result["missing_evidence_count"] == 0
