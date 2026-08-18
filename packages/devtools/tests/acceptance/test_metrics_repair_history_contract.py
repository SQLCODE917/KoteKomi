import hashlib
import json
from pathlib import Path

from kotekomi_devtools.evidence_catalog import write_canonical_record
from kotekomi_devtools.tdd_metrics import tdd_metrics
from kotekomi_devtools.tdd_scorecards import score_metrics


def _binding_and_run(state: Path) -> tuple[str, str]:
    task = "metrics-repair"
    run = "metrics-repair-run-001"
    snapshot = state / "experiments" / task / "spec" / "tdd-snapshot.md"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("# Metrics repair\n")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (snapshot.parent / "tdd-binding.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "task_id": task,
                "primary_tdd_path": "docs/metrics.md",
                "tdd_paths": ["docs/metrics.md"],
                "tdd_snapshot_path": str(snapshot),
                "tdd_sha256": digest,
            }
        )
    )
    runs = state / "experiments" / task / "runs"
    runs.mkdir(parents=True)
    (runs / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": task,
                "runs": [{"implementation_run_id": run, "ordinal": 1, "status": "active"}],
            }
        )
    )
    return task, run


def test_metrics_count_a_failed_check_replaced_by_a_passed_check(tmp_path: Path) -> None:
    state = tmp_path / "state"
    task, run = _binding_and_run(state)
    for status in ("failed", "passed"):
        write_canonical_record(
            state,
            task,
            run,
            phase="verification",
            evidence_type="run_check",
            subject_id="typecheck",
            payload={
                "check_id": "typecheck",
                "outcome": status,
                "diagnostics": [],
                "status": status,
            },
            producer_command="run-check",
        )

    _, collection = tdd_metrics("docs/metrics.md", state_root_path=state, run_id=run)

    metric = collection["metrics"][0]
    assert metric["repair_history_available"] is True
    assert metric["repair_count"] == 1


def test_legacy_history_omits_repair_score_dimensions(tmp_path: Path) -> None:
    state = tmp_path / "state"
    task, run = _binding_and_run(state)
    events = state / "experiments" / task / "runs" / run / "evidence" / "events.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text(json.dumps({"evidence_type": "run_check", "status": "ready"}) + "\n")

    _, collection = tdd_metrics("docs/metrics.md", state_root_path=state, run_id=run)
    metric = collection["metrics"][0]
    card = score_metrics(metric)

    assert metric["repair_history_available"] is False
    assert "metrics.repair_history_unavailable" in {item["code"] for item in metric["diagnostics"]}
    assert card["omitted_score_dimensions"] == ["first_pass_effectiveness", "repair_efficiency"]
    assert card["scored_weight_total"] == 0.75
