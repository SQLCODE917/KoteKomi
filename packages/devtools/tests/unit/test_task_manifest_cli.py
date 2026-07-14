from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_ROOT = REPOSITORY_ROOT / "packages/devtools/tests/fixtures/task_manifests"


def test_cli_emits_compact_output_for_a_manifest_with_non_ascii_text(tmp_path: Path) -> None:
    manifest = (FIXTURE_ROOT / "valid.toml").read_text().replace(
        'title = "Example task"',
        'title = "Résumé"',
    )
    manifest_path = tmp_path / "non-ascii.toml"
    manifest_path.write_text(manifest, encoding="utf-8")

    executable = shutil.which("kotekomi-agent")
    assert executable is not None
    completed = subprocess.run(
        (executable, "validate-task", str(manifest_path)),
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "\\u" not in completed.stdout
    assert list(json.loads(completed.stdout)) == [
        "status",
        "schema_version",
        "task_id",
        "manifest_sha256",
        "diagnostics",
    ]
