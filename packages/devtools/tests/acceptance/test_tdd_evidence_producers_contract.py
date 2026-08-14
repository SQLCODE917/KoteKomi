import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_run_check_indexes_its_canonical_record(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "run-check",
            "unit",
            "--output",
            str(tmp_path / "copy.json"),
            "--log",
            str(tmp_path / "check.log"),
            "--task-id",
            "task",
            "--run",
            "task-run-001",
            "--state-root",
            str(state_root),
            "--",
            sys.executable,
            "-c",
            "pass",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    record = state_root / "experiments/task/runs/task-run-001/checks/run-checks"
    canonical = next(record.glob("*.json"))
    payload = json.loads(canonical.read_text())
    assert payload["check_id"] == "unit"
    assert payload["outcome"] == "passed"
