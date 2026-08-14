import json
import subprocess
from pathlib import Path
from typing import Any

from kotekomi_devtools.tdd_workflow import workflow_status

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


def test_workflow_blocks_ci_and_merge_evidence_for_the_wrong_commit(tmp_path: Path) -> None:
    root = tmp_path / "state"
    records: dict[str, dict[str, Any]] = {
        "candidate_commit": {"commit_sha": "candidate", "parent_sha": "base"},
        "verification_plan": {"planned_checks": []},
        "verify_checks": {"status": "ready"},
        "candidate_ci": {"conclusion": "success", "head_sha": "different"},
    }
    entries = [
        {"evidence_type": "tdd_binding", "path": "binding.json"},
        {"evidence_type": "task_manifest", "path": "manifest.toml"},
        {"evidence_type": "task_manifest_validation", "path": "manifest-validation.json"},
        {"evidence_type": "candidate_lifecycle", "path": "candidate-lifecycle.json"},
    ]
    for evidence_type, payload in records.items():
        path = root / f"{evidence_type}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
        entries.append({"evidence_type": evidence_type, "path": path.name})

    phase, action, missing, diagnostics = workflow_status(root, entries, True)

    assert (phase, action, missing) == ("candidate_ci", "blocked", [])
    assert diagnostics[0]["code"] == "workflow.candidate_ci_commit_mismatch"
