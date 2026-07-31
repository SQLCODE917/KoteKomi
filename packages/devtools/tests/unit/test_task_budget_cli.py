from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def test_budget_audit_reports_invalid_manifest_before_git_analysis(tmp_path: Path) -> None:
    manifest = tmp_path / "invalid.toml"
    manifest.write_text("task_id = 'broken'\n", encoding="utf-8")
    executable = shutil.which("kotekomi-agent")
    assert executable is not None

    completed = subprocess.run(
        (executable, "budget-audit", str(manifest), "--base", "missing", "--worktree"),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stderr == ""
    assert list(json.loads(completed.stdout)) == [
        "status",
        "schema_version",
        "task_id",
        "mode",
        "base_revision",
        "head_revision",
        "budget",
        "totals",
        "path_stats",
        "diagnostics",
    ]
