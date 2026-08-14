import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_tdd_bind_documented_command_writes_stdout_and_optional_copy(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "one.md").write_text("# One\n")
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "tdd-bind",
            "docs/one.md",
            "--state-root",
            str(tmp_path / "state"),
            "--output",
            "copy.json",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready"
    assert json.loads((tmp_path / "copy.json").read_text())["task_id"] == payload["task_id"]


def test_tdd_bind_blocks_network_source(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "kotekomi-agent",
            "tdd-bind",
            "https://example.invalid/tdd.md",
            "--state-root",
            str(tmp_path / "state"),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["status"] == "blocked"
