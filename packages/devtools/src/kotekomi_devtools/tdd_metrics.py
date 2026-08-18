"""Metrics derived from validated run evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kotekomi_devtools.evidence_catalog import (
    EvidenceError,
    index_record,
    state_root,
    validated_entries,
)
from kotekomi_devtools.tdd_binding import list_tdd_bindings, lookup_tdd_binding

type Json = dict[str, Any]
_REPAIR_OUTCOMES: dict[str, tuple[set[str], set[str]]] = {
    "candidate_lifecycle": ({"ready"}, {"not_ready", "blocked"}),
    "run_check": ({"passed"}, {"failed", "blocked"}),
    "verify_checks": ({"passed"}, {"failed", "blocked"}),
    "candidate_ci": ({"success"}, {"failure", "cancelled", "skipped", "blocked"}),
    "main_lifecycle": ({"ready"}, {"not_ready", "blocked"}),
    "main_ci": ({"success"}, {"failure", "cancelled", "skipped", "blocked"}),
}


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _read(path: Path) -> Json:
    return json.loads(path.read_text())


def _runs(root: Path, task: str) -> list[Json]:
    index = _read(root / "experiments" / task / "runs" / "index.json")
    return sorted(index["runs"], key=lambda row: row["ordinal"])


def repair_history(events: list[Json]) -> tuple[bool, int]:
    """Return repair-history availability and repaired failures from immutable events."""
    pending_failures: dict[tuple[str, str, str], int] = {}
    repairs = 0
    for event in events:
        evidence_type = event.get("evidence_type")
        if evidence_type not in _REPAIR_OUTCOMES:
            continue
        outcome = event.get("evidence_outcome")
        successful, unsuccessful = _REPAIR_OUTCOMES[evidence_type]
        if event.get("schema_version") != 2 or not isinstance(outcome, str):
            return False, 0
        if outcome not in successful | unsuccessful:
            return False, 0
        key = (
            str(event.get("phase", "")),
            evidence_type,
            str(event.get("subject_id", "")),
        )
        if outcome in unsuccessful:
            pending_failures[key] = pending_failures.get(key, 0) + 1
        else:
            repairs += pending_failures.pop(key, 0)
    return True, repairs


def _metric(root: Path, binding: Json, run: Json) -> Json:
    task, run_id = str(binding["task_id"]), str(run["implementation_run_id"])
    try:
        entries = validated_entries(root, task, run_id)
    except EvidenceError as error:
        return {
            "schema_version": 1,
            "task_id": task,
            "implementation_run_id": run_id,
            "status": "blocked",
            "diagnostics": [{"code": "metrics.evidence", "location": "/", "rule": str(error)}],
        }
    by_type = {entry["evidence_type"]: entry for entry in entries}
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
        "receipt_chain_status",
    }
    if "task_result" in by_type:
        required.remove("receipt_chain_status")
        required.add("task_result")
    missing = required - set(by_type)

    def record(kind: str) -> Json:
        entry = by_type.get(kind)
        return _read(root / entry["path"]) if entry and entry["path_scope"] == "state" else {}

    receipt = record("receipt_chain_status")
    plan = record("verification_plan")
    checks = record("verify_checks")
    candidate = record("candidate_lifecycle")
    main = record("main_lifecycle")
    cleanup = record("cleanup")
    cci = record("candidate_ci")
    mci = record("main_ci")
    event_path = root / "experiments" / task / "runs" / run_id / "evidence" / "events.jsonl"
    events = (
        [json.loads(line) for line in event_path.read_text().splitlines()]
        if event_path.exists()
        else []
    )
    repair_history_available, repairs = repair_history(events)
    lifecycle_diagnostics = candidate.get("diagnostics", []) + main.get("diagnostics", [])
    result: Json = {
        "schema_version": 1,
        "task_id": task,
        "primary_tdd_path": binding["primary_tdd_path"],
        "tdd_paths": binding["tdd_paths"],
        "tdd_sha256": binding["tdd_sha256"],
        "implementation_run_id": run_id,
        "status": "complete" if not missing else "partial",
        "receipt_total_count": receipt.get("receipt_total_count", 0),
        "receipt_present_count": receipt.get("receipt_present_count", 0),
        "receipt_missing_count": receipt.get("receipt_missing_count", 0),
        "digest_mismatch_count": receipt.get("digest_mismatch_count", 0),
        "candidate_lifecycle_ready": candidate.get("ready", False),
        "main_lifecycle_ready": main.get("ready", False),
        "planned_check_count": len(plan.get("planned_checks", [])),
        "executed_check_count": checks.get("executed_check_count", 0),
        "verified_check_count": checks.get("verified_check_count", 0),
        "failed_check_count": checks.get("failed_check_count", 0),
        "candidate_ci_conclusion": cci.get("conclusion", "missing"),
        "main_ci_conclusion": mci.get("conclusion", "missing"),
        "repair_history_available": repair_history_available,
        "repair_count": repairs,
        "budget_violation_count": sum(
            1
            for item in lifecycle_diagnostics
            if str(item.get("code", "")).startswith("task_budget.")
        ),
        "protected_artifact_violation_count": sum(
            1
            for item in lifecycle_diagnostics
            if str(item.get("code", "")).startswith("protected_artifact.")
        ),
        "branch_cleanup_complete": cleanup.get("branch_cleanup_complete", False),
        "required_evidence_count": len(required),
        "present_evidence_count": len(required - missing),
        "missing_evidence_count": len(missing),
        "diagnostics": [
            {"code": "metrics.missing_evidence", "location": "/evidence", "rule": item}
            for item in sorted(missing)
        ]
        + (
            []
            if repair_history_available
            else [
                {
                    "code": "metrics.repair_history_unavailable",
                    "location": "/evidence/events.jsonl",
                    "rule": "repair_relevant_events_require_schema_version_2_outcomes",
                }
            ]
        ),
    }
    rel = f"experiments/{task}/runs/{run_id}/metrics/tdd-metrics.json"
    _write(root / rel, result)
    index_record(
        root,
        task,
        run_id,
        phase="complete",
        evidence_type="metrics_record",
        subject_id=run_id,
        path_scope="state",
        relative_path=rel,
        producer_command="tdd-metrics",
    )
    return result


def tdd_metrics(
    tdd_path: str | None,
    *,
    state_root_path: Path | None = None,
    run_id: str | None = None,
    latest: bool = False,
    output: Path | None = None,
    markdown: Path | None = None,
) -> tuple[int, Json]:
    root = state_root(state_root_path)
    if run_id and latest or (run_id or latest) and not tdd_path:
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "diagnostics": [
                {
                    "code": "metrics.selector",
                    "location": "/",
                    "rule": "run_selector_requires_tdd_path",
                }
            ],
        }
    bindings = (
        [lookup_tdd_binding(root, tdd_path=str(tdd_path))] if tdd_path else list_tdd_bindings(root)
    )
    metrics: list[Json] = []
    for binding in bindings:
        if binding is None:
            continue
        rows = _runs(root, str(binding["task_id"]))
        selected = (
            [row for row in rows if row["implementation_run_id"] == run_id]
            if run_id
            else [max(rows, key=lambda row: row["ordinal"])]
            if latest and rows
            else rows
        )
        metrics += [_metric(root, binding, row) for row in selected]
    collection: Json = {
        "schema_version": 1,
        "status": "complete"
        if metrics and all(item.get("status") == "complete" for item in metrics)
        else "partial",
        "metrics_collection_path": "",
        "metrics_record_paths": {
            str(item["implementation_run_id"]): (
                f"experiments/{item['task_id']}/runs/"
                f"{item['implementation_run_id']}/metrics/tdd-metrics.json"
            )
            for item in metrics
        },
        "metrics": metrics,
        "diagnostics": [],
    }
    path = root / (
        f"experiments/{bindings[0]['task_id']}/metrics/tdd-metrics.collection.json"
        if tdd_path and bindings and bindings[0]
        else "tdds/reports/metrics/all-known.metrics.json"
    )
    collection["metrics_collection_path"] = str(path)
    _write(path, collection)
    if output:
        _write(output, collection)
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text("# TDD metrics\n")
    return (0 if metrics else 1), collection
