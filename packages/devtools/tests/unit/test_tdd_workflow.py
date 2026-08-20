from __future__ import annotations

import json
from pathlib import Path

from kotekomi_devtools.tdd_workflow import create_or_reload_run


def test_new_run_can_follow_a_bootstrap_aborted_run(tmp_path: Path) -> None:
    task = "task"
    run = "task-run-001"
    record = tmp_path / "experiments" / task / "runs" / run / "run.json"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"status": "bootstrap_aborted"}))
    index = tmp_path / "experiments" / task / "runs" / "index.json"
    index.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": task,
                "runs": [
                    {
                        "implementation_run_id": run,
                        "ordinal": 1,
                        "run_record_path": record.relative_to(tmp_path).as_posix(),
                        "status": "bootstrap_aborted",
                    }
                ],
                "latest_run_id": run,
                "next_ordinal": 2,
                "diagnostics": [],
            }
        )
    )

    created = create_or_reload_run(tmp_path, task, new_run=True, abandon=None)

    assert created["implementation_run_id"] == "task-run-002"
    assert created["status"] == "active"
