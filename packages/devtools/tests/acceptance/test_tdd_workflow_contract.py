import json
import subprocess
from pathlib import Path
from typing import Any

from kotekomi_devtools.tdd_workflow import suggested_commands, workflow_status

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
        "specification_revision": {"specification_revision": "specification"},
        "candidate_commit": {"commit_sha": "candidate", "parent_sha": "base"},
        "verification_plan": {"planned_checks": []},
        "verify_checks": {"status": "ready"},
        "candidate_verification_receipt": {
            "outcome": "passed",
            "receipt_commit": "receipt",
            "specification_revision": "specification",
            "candidate_revision": "candidate",
        },
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


def test_workflow_selects_and_validates_main_promotion_evidence(tmp_path: Path) -> None:
    def status_for(
        directory: str, records: dict[str, dict[str, Any]]
    ) -> tuple[str, str, list[str], list[dict[str, Any]]]:
        root = tmp_path / directory
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
        return workflow_status(root, entries, True)

    base: dict[str, dict[str, Any]] = {
        "specification_revision": {"specification_revision": "specification"},
        "candidate_commit": {"commit_sha": "candidate", "parent_sha": "base"},
        "verification_plan": {"planned_checks": []},
        "verify_checks": {"status": "ready"},
        "candidate_verification_receipt": {
            "outcome": "passed",
            "receipt_commit": "receipt",
            "specification_revision": "specification",
            "candidate_revision": "candidate",
        },
        "candidate_ci": {"conclusion": "success", "head_sha": "receipt"},
    }
    assert status_for("missing", base)[:3] == (
        "main",
        "produce_main_promotion_evidence",
        ["main_promotion"],
    )

    direct = base | {
        "main_promotion": {
            "promotion_kind": "direct",
            "promotion_commit": "different",
            "parent_commit": "base",
            "verified_parent_commit": None,
        }
    }
    assert status_for("direct", direct)[1] == "blocked"
    assert (
        status_for("direct", direct)[3][0]["code"] == "workflow.main_promotion_candidate_mismatch"
    )

    merge = base | {
        "main_promotion": {
            "promotion_kind": "merge",
            "promotion_commit": "merge",
            "parent_commit": "base",
            "verified_parent_commit": "different",
        }
    }
    assert status_for("merge", merge)[1] == "blocked"

    main_ci = base | {
        "main_promotion": {
            "promotion_kind": "direct",
            "promotion_commit": "receipt",
            "parent_commit": "base",
            "verified_parent_commit": None,
        },
        "main_lifecycle": {"ready": True},
        "main_ci": {"conclusion": "success", "head_sha": "different"},
    }
    assert status_for("main-ci", main_ci)[1] == "blocked"
    assert status_for("main-ci", main_ci)[3][0]["code"] == "workflow.main_ci_commit_mismatch"


def test_workflow_blocks_non_ready_main_lifecycle(tmp_path: Path) -> None:
    root = tmp_path / "state"
    records: dict[str, dict[str, Any]] = {
        "specification_revision": {"specification_revision": "specification"},
        "candidate_commit": {"commit_sha": "candidate", "parent_sha": "base"},
        "verification_plan": {"planned_checks": []},
        "verify_checks": {"status": "ready"},
        "candidate_verification_receipt": {
            "outcome": "passed",
            "receipt_commit": "receipt",
            "specification_revision": "specification",
            "candidate_revision": "candidate",
        },
        "candidate_ci": {"conclusion": "success", "head_sha": "receipt"},
        "main_promotion": {
            "promotion_kind": "direct",
            "promotion_commit": "receipt",
            "parent_commit": "base",
            "verified_parent_commit": None,
        },
        "main_lifecycle": {"ready": False},
        "main_ci": {"conclusion": "success", "head_sha": "candidate"},
        "cleanup": {"branch_cleanup_complete": True},
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

    assert (phase, action, missing) == ("main", "blocked", [])
    assert diagnostics[0]["code"] == "workflow.main_lifecycle_not_ready"


def test_workflow_requires_and_derives_a_portable_candidate_receipt_command(tmp_path: Path) -> None:
    manifest = tmp_path / "task.toml"
    manifest.write_text('baseline_revision = "base"\n', encoding="utf-8")
    root = tmp_path / "state"
    records: dict[str, dict[str, Any]] = {
        "specification_revision": {"specification_revision": "specification"},
        "candidate_commit": {"commit_sha": "candidate", "parent_sha": "base"},
        "verification_plan": {"planned_checks": []},
        "verify_checks": {"status": "ready"},
    }
    entries: list[dict[str, Any]] = [
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

    assert workflow_status(root, entries, True)[:3] == (
        "verification",
        "verify_candidate",
        ["candidate_verification_receipt"],
    )
    command = suggested_commands(
        "verify_candidate", "task", "task-run-001", str(manifest), root, entries
    )[0]

    assert command == {
        "command": "verify-candidate",
        "arguments": [
            "--manifest",
            str(manifest),
            "--base",
            "base",
            "--specification",
            "specification",
            "--candidate",
            "candidate",
            "--profile",
            "portable-local",
            "--task-id",
            "task",
            "--run",
            "task-run-001",
            "--state-root",
            str(root),
        ],
    }
