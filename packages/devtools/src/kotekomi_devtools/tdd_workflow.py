"""TDD implementation status and deterministic run state."""

from __future__ import annotations

import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from kotekomi_devtools.evidence_catalog import (
    EvidenceError,
    canonical_relative,
    index_record,
    rebuild_index,
    run_root,
    state_root,
    validated_entries,
)
from kotekomi_devtools.task_manifest import validate_task_manifest
from kotekomi_devtools.tdd_binding import bind_tdd

type Json = dict[str, Any]
PHASE_REQUIREMENTS = {
    "spec": {"tdd_binding", "task_manifest", "task_manifest_validation"},
    "candidate": {"candidate_lifecycle", "candidate_commit"},
    "verification": {"verification_plan", "verify_checks"},
    "candidate_ci": {"candidate_ci"},
    "main": {"main_merge", "main_lifecycle"},
    "main_ci": {"main_ci", "cleanup"},
    "complete": {"receipt_chain_status"},
}


def _write(path: Path, value: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _read(path: Path) -> Json:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("invalid JSON")
    return cast(Json, value)


def _runs(root: Path, task: str) -> tuple[Path, Json]:
    path = root / "experiments" / task / "runs" / "index.json"
    if path.exists():
        return path, _read(path)
    return path, {
        "schema_version": 1,
        "task_id": task,
        "runs": [],
        "latest_run_id": None,
        "next_ordinal": 1,
        "diagnostics": [],
    }


def _latest(index: Json) -> Json | None:
    rows = index["runs"]
    live = [row for row in rows if row["status"] != "abandoned"]
    pool = live or rows
    return max(pool, key=lambda row: row["ordinal"], default=None)


def _create_or_reload(root: Path, task: str, *, new_run: bool, abandon: str | None) -> Json:
    index_path, index = _runs(root, task)
    rows = index["runs"]
    if abandon:
        matched = next((row for row in rows if row["implementation_run_id"] == abandon), None)
        if matched is None or matched["status"] in {"complete", "abandoned"}:
            raise ValueError("run cannot be abandoned")
        matched["status"] = "abandoned"
        matched["updated_at"] = datetime.now(UTC).isoformat()
        record_path = root / matched["run_record_path"]
        record = _read(record_path)
        record["status"] = "abandoned"
        record["terminal_reason"] = "operator_abandoned"
        record["updated_at"] = matched["updated_at"]
        _write(record_path, record)
    latest = _latest(index)
    if latest and latest["status"] in {"active", "blocked"}:
        if new_run:
            raise ValueError("cannot create a new run while a non-terminal run exists")
        selected = latest
    else:
        if latest and latest["status"] in {"complete", "abandoned"} and not new_run and not abandon:
            selected = latest
        else:
            ordinal = int(index["next_ordinal"])
            run_id = f"{task}-run-{ordinal:03d}"
            now = datetime.now(UTC).isoformat()
            rel = f"experiments/{task}/runs/{run_id}/run.json"
            selected = {
                "implementation_run_id": run_id,
                "ordinal": ordinal,
                "run_record_path": rel,
                "status": "active",
                "started_at": now,
                "updated_at": now,
            }
            rows.append(selected)
            index["next_ordinal"] = ordinal + 1
            _write(
                root / rel,
                {
                    "schema_version": 1,
                    "task_id": task,
                    **selected,
                    "terminal_reason": None,
                    "diagnostics": [],
                },
            )
    index["latest_run_id"] = (_latest(index) or {}).get("implementation_run_id")
    _write(index_path, index)
    return selected


def workflow_status(
    root: Path, entries: list[Json], manifest_exists: bool
) -> tuple[str, str, list[str], list[Json]]:
    kinds = {item["evidence_type"] for item in entries}
    if not manifest_exists or not PHASE_REQUIREMENTS["spec"].issubset(kinds):
        return "spec", "create_task_manifest", sorted(PHASE_REQUIREMENTS["spec"] - kinds), []
    if "candidate_lifecycle" not in kinds:
        return "candidate", "produce_candidate_lifecycle_evidence", ["candidate_lifecycle"], []
    if "candidate_commit" not in kinds:
        return "candidate", "produce_candidate_commit_evidence", ["candidate_commit"], []
    if not PHASE_REQUIREMENTS["verification"].issubset(kinds):
        return (
            "verification",
            "produce_verification_evidence",
            sorted(PHASE_REQUIREMENTS["verification"] - kinds),
            [],
        )
    plan = _payload(root, entries, "verification_plan")
    planned = plan.get("planned_checks", [])
    if not isinstance(planned, list) or not all(
        isinstance(item.get("id"), str) for item in cast(list[Json], planned)
    ):
        return "verification", "produce_verification_evidence", ["verification_plan"], []
    planned_ids = {str(item["id"]) for item in cast(list[Json], planned)}
    recorded_ids = {
        str(item["subject_id"]) for item in entries if item["evidence_type"] == "run_check"
    }
    missing_checks = sorted(f"run_check:{item}" for item in planned_ids - recorded_ids)
    if missing_checks:
        return "verification", "produce_verification_evidence", missing_checks, []
    if "candidate_ci" not in kinds:
        return "candidate_ci", "produce_candidate_ci_evidence", ["candidate_ci"], []
    candidate = _payload(root, entries, "candidate_commit")
    candidate_ci = _payload(root, entries, "candidate_ci")
    blocked = _ci_diagnostic("candidate", candidate_ci, candidate["commit_sha"], "commit_sha")
    if blocked:
        return "candidate_ci", "blocked", [], [blocked]
    if "main_merge" not in kinds:
        return "main", "produce_main_merge_evidence", ["main_merge"], []
    merge = _payload(root, entries, "main_merge")
    if merge["verified_parent_commit"] != candidate["commit_sha"]:
        return (
            "main",
            "blocked",
            [],
            [
                _diagnostic(
                    "main_merge_candidate_mismatch",
                    "verified_parent_commit_matches_candidate_commit",
                )
            ],
        )
    if "main_lifecycle" not in kinds:
        return "main", "produce_main_lifecycle_evidence", ["main_lifecycle"], []
    if "main_ci" not in kinds:
        return "main_ci", "produce_main_ci_evidence", ["main_ci"], []
    main_ci = _payload(root, entries, "main_ci")
    blocked = _ci_diagnostic("main", main_ci, merge["merge_commit"], "merge_commit")
    if blocked:
        return "main_ci", "blocked", [], [blocked]
    if "cleanup" not in kinds:
        return "main_ci", "produce_cleanup_evidence", ["cleanup"], []
    cleanup = _payload(root, entries, "cleanup")
    if cleanup["branch_cleanup_complete"] is not True:
        return (
            "main_ci",
            "blocked",
            [],
            [_diagnostic("cleanup_incomplete", "branch_cleanup_complete")],
        )
    if "receipt_chain_status" not in kinds:
        return "complete", "produce_complete_evidence", ["receipt_chain_status"], []
    return "complete", "complete", [], []


def _payload(root: Path, entries: list[Json], evidence_type: str) -> Json:
    entry = next(item for item in entries if item["evidence_type"] == evidence_type)
    return _read(root / entry["path"])


def _ci_diagnostic(name: str, ci: Json, expected_sha: object, expected_field: str) -> Json | None:
    if ci["conclusion"] != "success":
        return _diagnostic(f"{name}_ci_not_success", "conclusion_is_success")
    if ci["head_sha"] != expected_sha:
        return _diagnostic(f"{name}_ci_commit_mismatch", f"head_sha_matches_{expected_field}")
    return None


def _diagnostic(code: str, rule: str) -> Json:
    return {"code": f"workflow.{code}", "location": "/evidence", "rule": rule}


def _suggested_commands(action: str, task_id: str, run_id: str, manifest_path: str) -> list[Json]:
    if action in {"blocked", "complete"}:
        return []
    command = {
        "create_task_manifest": "create-task-manifest",
        "produce_candidate_lifecycle_evidence": "lifecycle-check",
        "produce_candidate_commit_evidence": "record-candidate-commit",
        "produce_verification_evidence": "verification-plan",
        "produce_candidate_ci_evidence": "record-candidate-ci",
        "produce_main_merge_evidence": "record-main-merge",
        "produce_main_lifecycle_evidence": "lifecycle-check",
        "produce_main_ci_evidence": "record-main-ci",
        "produce_cleanup_evidence": "record-branch-cleanup",
        "produce_complete_evidence": "receipt-chain-status",
    }.get(action, "evidence-index")
    arguments = ["--task-id", task_id, "--run", run_id]
    if action == "create_task_manifest":
        arguments.extend(["--manifest-path", manifest_path])
    return [{"command": command, "arguments": arguments}]


def implement_tdd(
    tdd_path: Path | str,
    *,
    state_root_path: Path | None = None,
    output: Path | None = None,
    markdown: Path | None = None,
    new_run: bool = False,
    abandon_run: str | None = None,
) -> tuple[int, Json]:
    root = state_root(state_root_path)
    if new_run and abandon_run:
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "diagnostics": [
                {
                    "code": "workflow.option_conflict",
                    "location": "/",
                    "rule": "new_run_and_abandon_run_mutually_exclusive",
                }
            ],
        }
    binding_result = bind_tdd(tdd_path, state_root=root)
    if binding_result.status != "ready":
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            **binding_result.as_json(),
            "implementation_phase": "intake",
            "next_action": None,
            "missing_evidence": [],
            "producer_arguments": {},
        }
    binding = binding_result.binding or {}
    task = str(binding["task_id"])
    try:
        run = _create_or_reload(root, task, new_run=new_run, abandon=abandon_run)
    except ValueError as error:
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "task_id": task,
            "diagnostics": [{"code": "workflow.run", "location": "/run", "rule": str(error)}],
        }
    run_id = str(run["implementation_run_id"])
    rebuild_index(root, task, run_id)
    scope, rel = canonical_relative("tdd_binding", task, run_id)
    index_record(
        root,
        task,
        run_id,
        phase="intake",
        evidence_type="tdd_binding",
        subject_id="binding",
        path_scope=scope,
        relative_path=rel,
        producer_command="implement-tdd",
    )
    manifest = Path.cwd() / ".agent" / "tasks" / f"{task}.toml"
    validation_status = "missing"
    if manifest.exists():
        scope, rel = canonical_relative("task_manifest", task, run_id)
        index_record(
            root,
            task,
            run_id,
            phase="spec",
            evidence_type="task_manifest",
            subject_id="manifest",
            path_scope=scope,
            relative_path=rel,
            producer_command="implement-tdd",
        )
        validation = validate_task_manifest(manifest)
        validation_status = "valid" if validation.valid else "invalid"
        try:
            manifest_identity = tomllib.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            manifest_identity = {}
        manifest_tdd_path = manifest_identity.get("tdd_path")
        manifest_tdd_sha256 = manifest_identity.get("tdd_sha256")
        validation_payload = validation.as_json() | {
            "tdd_path": manifest_tdd_path,
            "tdd_sha256": manifest_tdd_sha256,
        }
        vscope, vrel = canonical_relative("task_manifest_validation", task, run_id)
        _write(root / vrel, validation_payload)
        index_record(
            root,
            task,
            run_id,
            phase="spec",
            evidence_type="task_manifest_validation",
            subject_id="manifest",
            path_scope=vscope,
            relative_path=vrel,
            producer_command="implement-tdd",
        )
        if (
            not validation.valid
            or validation.task_id != task
            or manifest_tdd_sha256 != binding["tdd_sha256"]
            or manifest_tdd_path not in cast(list[str], binding["tdd_paths"])
        ):
            return 1, {
                "schema_version": 1,
                "status": "blocked",
                "task_id": task,
                "implementation_run_id": run_id,
                "diagnostics": [
                    {
                        "code": "workflow.manifest_invalid",
                        "location": "/manifest",
                        "rule": "binding_identity_matches_valid_manifest",
                    }
                ],
            }
    try:
        entries = validated_entries(root, task, run_id)
    except EvidenceError as error:
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "task_id": task,
            "implementation_run_id": run_id,
            "diagnostics": [
                {"code": "workflow.evidence_invalid", "location": "/evidence", "rule": str(error)}
            ],
        }
    phase, action, missing, diagnostics = workflow_status(root, entries, manifest.exists())
    result: Json = {
        "schema_version": 1,
        "status": "blocked" if action == "blocked" else "ready",
        "task_id": task,
        "implementation_run_id": run_id,
        "requested_tdd_path": binding_result.requested_tdd_path,
        "primary_tdd_path": binding["primary_tdd_path"],
        "tdd_paths": binding["tdd_paths"],
        "tdd_sha256": binding["tdd_sha256"],
        "manifest_path": str(manifest.relative_to(Path.cwd())),
        "manifest_validation_status": validation_status,
        "implementation_phase": phase,
        "next_action": None if action == "blocked" else action,
        "required_evidence": sorted(PHASE_REQUIREMENTS.get(phase, set())),
        "missing_evidence": missing,
        "producer_arguments": {
            "task_id": task,
            "implementation_run_id": run_id,
            "run_root": str(run_root(root, task, run_id)),
            "evidence_index_path": str(
                root / "experiments" / task / "runs" / run_id / "evidence" / "index.json"
            ),
        },
        "suggested_commands": _suggested_commands(
            action,
            task,
            run_id,
            str(manifest.relative_to(Path.cwd())),
        ),
        "diagnostics": diagnostics,
    }
    if output:
        _write(output, result)
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(f"# Implement TDD\n\nPhase: `{phase}`\n\nNext action: `{action}`\n")
    return 0, result
