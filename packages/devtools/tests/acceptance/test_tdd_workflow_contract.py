import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_workflow_creates_run_and_requests_manifest(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "one.md").write_text("# One\n")
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "implement-tdd",
            "docs/one.md",
            "--state-root",
            str(tmp_path / "state"),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["next_action"] == "create_task_manifest"
    assert payload["suggested_commands"][0]["arguments"][:4] == [
        "--task-id",
        payload["task_id"],
        "--run",
        payload["implementation_run_id"],
    ]
    assert (
        tmp_path
        / "state"
        / "experiments"
        / payload["task_id"]
        / "runs"
        / payload["implementation_run_id"]
        / "run.json"
    ).is_file()
