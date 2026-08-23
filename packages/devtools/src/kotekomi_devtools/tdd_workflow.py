"""TDD implementation status and deterministic run state."""

from __future__ import annotations

import hashlib
import json
import subprocess
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
    write_canonical_record,
)
from kotekomi_devtools.lifecycle_evidence import LifecycleEvidenceError, create_feature_branch
from kotekomi_devtools.task_manifest import validate_task_manifest
from kotekomi_devtools.tdd_binding import bind_tdd

type Json = dict[str, Any]
PHASE_REQUIREMENTS = {
    "spec": {"tdd_binding", "task_manifest", "task_manifest_validation"},
    "candidate": {"candidate_lifecycle", "candidate_commit"},
    "verification": {"verification_plan", "verify_checks", "candidate_verification_receipt"},
    "candidate_ci": {"candidate_ci"},
    "main": {"main_promotion", "main_lifecycle"},
    "main_ci": {"main_ci", "cleanup"},
    "complete": {"task_result", "cleanup"},
}
_TERMINAL_RUN_STATUSES = {"complete", "abandoned", "superseded"}


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
    live = [row for row in rows if row["status"] not in _TERMINAL_RUN_STATUSES]
    pool = live or rows
    return max(pool, key=lambda row: row["ordinal"], default=None)


def _create_or_reload(root: Path, task: str, *, new_run: bool, abandon: str | None) -> Json:
    index_path, index = _runs(root, task)
    rows = index["runs"]
    if abandon:
        matched = next((row for row in rows if row["implementation_run_id"] == abandon), None)
        if matched is None or matched["status"] in {"complete", "superseded"}:
            raise ValueError("run cannot be abandoned")
        if matched["status"] != "abandoned":
            matched["status"] = "abandoned"
            matched["updated_at"] = datetime.now(UTC).isoformat()
            record_path = root / matched["run_record_path"]
            record = _read(record_path)
            record["status"] = "abandoned"
            record["terminal_reason"] = "operator_abandoned"
            record["updated_at"] = matched["updated_at"]
            _write(record_path, record)
        index["latest_run_id"] = (_latest(index) or {}).get("implementation_run_id")
        _write(index_path, index)
        return matched
    latest = _latest(index)
    if latest and latest["status"] in {"active", "blocked"}:
        if new_run:
            raise ValueError("cannot create a new run while a non-terminal run exists")
        selected = latest
    else:
        if latest and latest["status"] == "superseded":
            if new_run:
                raise ValueError("superseded task cannot create or resume a run")
            selected = latest
        elif latest and latest["status"] in {"complete", "abandoned"} and not new_run:
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


def _terminal_result(
    *,
    binding_result: Any,
    binding: Json,
    task: str,
    run: Json,
    root: Path,
) -> Json:
    """Return a terminal run without creating or indexing further evidence."""
    run_id = str(run["implementation_run_id"])
    status = str(run["status"])
    return {
        "schema_version": 1,
        "status": status,
        "task_id": task,
        "implementation_run_id": run_id,
        "requested_tdd_path": binding_result.requested_tdd_path,
        "primary_tdd_path": binding["primary_tdd_path"],
        "tdd_paths": binding["tdd_paths"],
        "tdd_sha256": binding["tdd_sha256"],
        "implementation_phase": status,
        "next_action": None,
        "required_evidence": [],
        "missing_evidence": [],
        "producer_arguments": {
            "task_id": task,
            "implementation_run_id": run_id,
            "run_root": str(run_root(root, task, run_id)),
            "evidence_index_path": str(
                root / "experiments" / task / "runs" / run_id / "evidence" / "index.json"
            ),
        },
        "suggested_commands": [],
        "diagnostics": [],
    }


def workflow_status(
    root: Path, entries: list[Json], manifest_exists: bool
) -> tuple[str, str, list[str], list[Json]]:
    kinds = {item["evidence_type"] for item in entries}
    if not manifest_exists or not PHASE_REQUIREMENTS["spec"].issubset(kinds):
        return "spec", "create_task_manifest", sorted(PHASE_REQUIREMENTS["spec"] - kinds), []
    if {"task_result", "cleanup"}.issubset(kinds):
        task_result = _payload(root, entries, "task_result")
        cleanup = _payload(root, entries, "cleanup")
        if (
            cleanup.get("branch_cleanup_complete") is True
            and task_result.get("outcome") == "completed"
        ):
            return "complete", "complete", [], []
        if (
            cleanup.get("branch_cleanup_complete") is True
            and task_result.get("outcome") == "superseded"
        ):
            return "complete", "superseded", [], []
    if "candidate_lifecycle" not in kinds:
        return "candidate", "produce_candidate_lifecycle_evidence", ["candidate_lifecycle"], []
    if "candidate_commit" not in kinds:
        return "candidate", "produce_candidate_commit_evidence", ["candidate_commit"], []
    required_verification = {"verification_plan", "verify_checks"}
    if not required_verification.issubset(kinds):
        return (
            "verification",
            "produce_verification_evidence",
            sorted(required_verification - kinds),
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
    receipt_entry = next(
        (
            item
            for item in entries
            if item["evidence_type"] == "candidate_verification_receipt"
            and item.get("subject_id", "portable-local") == "portable-local"
        ),
        None,
    )
    if receipt_entry is None:
        return "verification", "verify_candidate", ["candidate_verification_receipt"], []
    receipt = _read(root / receipt_entry["path"])
    if receipt.get("outcome") != "passed":
        return (
            "verification",
            "blocked",
            [],
            [_diagnostic("candidate_receipt_not_passed", "portable_local_receipt_is_passed")],
        )
    specification = _payload(root, entries, "specification_revision")
    candidate = _payload(root, entries, "candidate_commit")
    if receipt.get("specification_revision") != specification.get(
        "specification_revision"
    ) or receipt.get("candidate_revision") != candidate.get("commit_sha"):
        return (
            "verification",
            "blocked",
            [],
            [_diagnostic("candidate_receipt_mismatch", "receipt_revisions_match_run_evidence")],
        )
    if "candidate_ci" not in kinds:
        return "candidate_ci", "produce_candidate_ci_evidence", ["candidate_ci"], []
    candidate_ci = _payload(root, entries, "candidate_ci")
    blocked = _ci_diagnostic("candidate", candidate_ci, receipt["receipt_commit"], "receipt_commit")
    if blocked:
        return "candidate_ci", "blocked", [], [blocked]
    if "main_promotion" not in kinds:
        return "main", "promote_feature_branch", ["main_promotion"], []
    promotion = _payload(root, entries, "main_promotion")
    if "feature_branch" in kinds and promotion["promotion_kind"] == "direct":
        return (
            "main",
            "blocked",
            [],
            [_diagnostic("direct_main_promotion", "feature_branch_runs_require_merge_promotion")],
        )
    if (
        promotion["promotion_kind"] == "merge"
        and promotion["verified_parent_commit"] != receipt["receipt_commit"]
    ):
        return (
            "main",
            "blocked",
            [],
            [
                _diagnostic(
                    "main_promotion_candidate_mismatch",
                    "verified_parent_commit_matches_candidate_commit",
                )
            ],
        )
    if (
        promotion["promotion_kind"] == "direct"
        and promotion["promotion_commit"] != receipt["receipt_commit"]
    ):
        return (
            "main",
            "blocked",
            [],
            [
                _diagnostic(
                    "main_promotion_candidate_mismatch", "promotion_commit_matches_candidate_commit"
                )
            ],
        )
    if "main_lifecycle" not in kinds:
        return "main", "produce_main_lifecycle_evidence", ["main_lifecycle"], []
    main_lifecycle = _payload(root, entries, "main_lifecycle")
    if main_lifecycle.get("ready") is not True:
        return (
            "main",
            "blocked",
            [],
            [_diagnostic("main_lifecycle_not_ready", "main_lifecycle_is_ready")],
        )
    if "main_ci" not in kinds:
        return "main_ci", "produce_main_ci_evidence", ["main_ci"], []
    main_ci = _payload(root, entries, "main_ci")
    blocked = _ci_diagnostic("main", main_ci, promotion["promotion_commit"], "promotion_commit")
    if blocked:
        return "main_ci", "blocked", [], [blocked]
    if "task_result" not in kinds:
        return "main_ci", "complete_feature_branch", ["task_result", "cleanup"], []
    if "cleanup" not in kinds:
        return "main_ci", "complete_feature_branch", ["cleanup"], []
    cleanup = _payload(root, entries, "cleanup")
    if cleanup["branch_cleanup_complete"] is not True:
        return (
            "main_ci",
            "blocked",
            [],
            [_diagnostic("cleanup_incomplete", "branch_cleanup_complete")],
        )
    return "complete", "produce_complete_evidence", ["task_result"], []


def _payload(root: Path, entries: list[Json], evidence_type: str) -> Json:
    entry = next(item for item in entries if item["evidence_type"] == evidence_type)
    return _read(root / entry["path"])


def _ci_diagnostic(name: str, ci: Json, expected_sha: object, expected_field: str) -> Json | None:
    if ci["conclusion"] != "success":
        return _diagnostic(f"{name}_ci_not_success", "conclusion_is_success")
    if ci["head_sha"] != expected_sha and ci.get("validated_promotion_commit") != expected_sha:
        return _diagnostic(f"{name}_ci_commit_mismatch", f"head_sha_matches_{expected_field}")
    return None


def _diagnostic(code: str, rule: str) -> Json:
    return {"code": f"workflow.{code}", "location": "/evidence", "rule": rule}


def suggested_commands(
    action: str,
    task_id: str,
    run_id: str,
    manifest_path: str,
    root: Path,
    entries: list[Json],
) -> list[Json]:
    if action in {"blocked", "complete", "superseded"}:
        return []
    command = {
        "create_task_manifest": "create-task-manifest",
        "produce_candidate_lifecycle_evidence": "lifecycle-check",
        "produce_candidate_commit_evidence": "record-candidate-commit",
        "produce_verification_evidence": "verification-plan",
        "verify_candidate": "verify-candidate",
        "produce_candidate_ci_evidence": "record-candidate-ci",
        "promote_feature_branch": "promote-feature-branch",
        "produce_main_lifecycle_evidence": "lifecycle-check",
        "produce_main_ci_evidence": "record-main-ci",
        "complete_feature_branch": "complete-feature-branch",
        "produce_complete_evidence": "receipt-chain-status",
    }.get(action, "evidence-index")
    arguments = ["--task-id", task_id, "--run", run_id]
    if action == "create_task_manifest":
        arguments.extend(["--manifest-path", manifest_path])
    if action == "produce_complete_evidence":
        arguments.extend(["--phase", "complete"])
    if action == "verify_candidate":
        manifest = tomllib.loads(Path(manifest_path).read_text(encoding="utf-8"))
        specification = _payload(root, entries, "specification_revision")
        candidate = _payload(root, entries, "candidate_commit")
        arguments = [
            "--manifest",
            manifest_path,
            "--base",
            str(manifest["baseline_revision"]),
            "--specification",
            str(specification["specification_revision"]),
            "--candidate",
            str(candidate["commit_sha"]),
            "--profile",
            "portable-local",
            *arguments,
            "--state-root",
            str(root),
        ]
    if action in {"promote_feature_branch", "complete_feature_branch"}:
        arguments.extend(["--state-root", str(root)])
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
    feature_branch: str | None = None
    try:
        run = _create_or_reload(root, task, new_run=new_run, abandon=abandon_run)
    except ValueError as error:
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "task_id": task,
            "diagnostics": [{"code": "workflow.run", "location": "/run", "rule": str(error)}],
        }
    if abandon_run is not None or run["status"] in _TERMINAL_RUN_STATUSES:
        result = _terminal_result(
            binding_result=binding_result,
            binding=binding,
            task=task,
            run=run,
            root=root,
        )
        if output:
            _write(output, result)
        if markdown:
            markdown.parent.mkdir(parents=True, exist_ok=True)
            markdown.write_text(f"# Implement TDD\n\nPhase: `{result['implementation_phase']}`\n")
        return 0, result
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
        if manifest_identity.get("schema_version") == 1:
            return 0, {
                "schema_version": 1,
                "status": "historical",
                "task_id": task,
                "implementation_run_id": run_id,
                "requested_tdd_path": binding_result.requested_tdd_path,
                "primary_tdd_path": binding["primary_tdd_path"],
                "tdd_paths": binding["tdd_paths"],
                "tdd_sha256": binding["tdd_sha256"],
                "manifest_path": str(manifest.relative_to(Path.cwd())),
                "manifest_validation_status": validation_status,
                "implementation_phase": "historical",
                "next_action": None,
                "missing_evidence": [],
                "producer_arguments": {},
                "suggested_commands": [],
                "diagnostics": [],
            }
        if manifest_identity.get("schema_version") == 2:
            try:
                specification = _record_specification(root, task, run_id, manifest)
                existing = next(
                    (
                        item
                        for item in validated_entries(root, task, run_id)
                        if item["evidence_type"] == "feature_branch"
                    ),
                    None,
                )
                if existing is not None:
                    branch = _read(root / existing["path"])
                    if (
                        branch.get("branch") != f"feature/{task}"
                        or branch.get("specification_revision") != specification
                    ):
                        raise EvidenceError(
                            "feature branch evidence conflicts with specification revision"
                        )
                    feature_branch = str(branch["branch"])
                else:
                    branch_result = create_feature_branch(
                        task_id=task,
                        run_id=run_id,
                        specification_revision=specification,
                        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        state_root_path=root,
                    )
                    feature_branch = cast(str, branch_result.payload["branch"])
            except (EvidenceError, LifecycleEvidenceError) as error:
                return 1, {
                    "schema_version": 1,
                    "status": "blocked",
                    "task_id": task,
                    "implementation_run_id": run_id,
                    "diagnostics": [
                        {
                            "code": "workflow.feature_branch_invalid",
                            "location": "/feature_branch",
                            "rule": str(error),
                        }
                    ],
                }
    try:
        rebuild_index(root, task, run_id)
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
    if action == "complete":
        mark_run_complete(root, task, run_id)
    if action == "superseded":
        mark_run_superseded(root, task, run_id)
    result: Json = {
        "schema_version": 1,
        "status": (
            "blocked"
            if action == "blocked"
            else "complete"
            if action == "complete"
            else "superseded"
            if action == "superseded"
            else "ready"
        ),
        "task_id": task,
        "implementation_run_id": run_id,
        "requested_tdd_path": binding_result.requested_tdd_path,
        "primary_tdd_path": binding["primary_tdd_path"],
        "tdd_paths": binding["tdd_paths"],
        "tdd_sha256": binding["tdd_sha256"],
        "manifest_path": str(manifest.relative_to(Path.cwd())),
        "manifest_validation_status": validation_status,
        "implementation_phase": phase,
        "next_action": None if action in {"blocked", "complete", "superseded"} else action,
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
        "suggested_commands": suggested_commands(
            action,
            task,
            run_id,
            str(manifest.relative_to(Path.cwd())),
            root,
            entries,
        ),
        "diagnostics": diagnostics,
    }
    if feature_branch is not None:
        result["feature_branch"] = feature_branch
    if output:
        _write(output, result)
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(f"# Implement TDD\n\nPhase: `{phase}`\n\nNext action: `{action}`\n")
    return 0, result


def mark_run_complete(root: Path, task: str, run_id: str) -> None:
    """Persist the terminal complete state after evidence proves task closure."""
    index_path, index = _runs(root, task)
    row = next(
        (item for item in index["runs"] if item["implementation_run_id"] == run_id),
        None,
    )
    if row is None or row["status"] == "abandoned":
        raise EvidenceError("complete workflow requires an active or blocked run")
    if row["status"] != "complete":
        now = datetime.now(UTC).isoformat()
        row["status"] = "complete"
        row["updated_at"] = now
        record_path = root / row["run_record_path"]
        record = _read(record_path)
        record["status"] = "complete"
        record["terminal_reason"] = None
        record["updated_at"] = now
        _write(record_path, record)
    index["latest_run_id"] = (_latest(index) or {}).get("implementation_run_id")
    _write(index_path, index)


def mark_run_superseded(root: Path, task: str, run_id: str) -> None:
    """Persist terminal supersession after a completed successor proves delivery."""
    index_path, index = _runs(root, task)
    row = next(
        (item for item in index["runs"] if item["implementation_run_id"] == run_id),
        None,
    )
    if row is None or row["status"] == "complete":
        raise EvidenceError("superseded workflow requires an active or blocked run")
    if row["status"] == "abandoned" and not _has_complete_supersession_evidence(root, task, run_id):
        raise EvidenceError("superseded workflow requires canonical evidence")
    if row["status"] != "superseded":
        now = datetime.now(UTC).isoformat()
        prior_status = row["status"]
        row["status"] = "superseded"
        row["updated_at"] = now
        record_path = root / row["run_record_path"]
        record = _read(record_path)
        if prior_status == "abandoned":
            record["prior_status"] = "abandoned"
            record["prior_terminal_reason"] = record.get("terminal_reason")
        record["status"] = "superseded"
        record["terminal_reason"] = "superseded_by_successor"
        record["updated_at"] = now
        _write(record_path, record)
    index["latest_run_id"] = (_latest(index) or {}).get("implementation_run_id")
    _write(index_path, index)


def _has_complete_supersession_evidence(root: Path, task: str, run_id: str) -> bool:
    try:
        entries = validated_entries(root, task, run_id)
    except EvidenceError:
        return False
    payloads: dict[str, Json] = {}
    for evidence_type in ("task_result", "cleanup"):
        entry = next((item for item in entries if item["evidence_type"] == evidence_type), None)
        if entry is None or entry["path_scope"] != "state":
            return False
        try:
            payloads[evidence_type] = _read(root / str(entry["path"]))
        except (OSError, ValueError, json.JSONDecodeError):
            return False
    return (
        payloads["task_result"].get("outcome") == "superseded"
        and payloads["cleanup"].get("branch_cleanup_complete") is True
    )


def _record_specification(root: Path, task: str, run_id: str, manifest: Path) -> str:
    """Persist the clean current-main specification once for a V2 run."""
    path = root / canonical_relative("specification_revision", task, run_id, "specification")[1]
    manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if path.is_file():
        payload = _read(path)
        if payload.get("manifest_sha256") != manifest_sha256:
            raise EvidenceError("specification manifest conflict")
        revision = payload.get("specification_revision")
        if isinstance(revision, str):
            return revision
        raise EvidenceError("specification revision is invalid")
    branch = _git("branch", "--show-current")
    head = _git("rev-parse", "HEAD")
    origin_main = _git("rev-parse", "origin/main")
    status = _git("status", "--porcelain")
    manifest_blob = _git("show", f"HEAD:{manifest.relative_to(Path.cwd()).as_posix()}")
    if (
        branch.returncode != 0
        or branch.stdout.strip() != "main"
        or head.returncode != 0
        or origin_main.returncode != 0
        or head.stdout.strip() != origin_main.stdout.strip()
        or status.returncode != 0
        or status.stdout
        or manifest_blob.returncode != 0
        or manifest_blob.stdout.encode() != manifest.read_bytes()
    ):
        raise EvidenceError("specification requires clean current main with committed manifest")
    revision = head.stdout.strip()
    write_canonical_record(
        root,
        task,
        run_id,
        phase="spec",
        evidence_type="specification_revision",
        subject_id="specification",
        payload={
            "schema_version": 1,
            "specification_revision": revision,
            "manifest_sha256": manifest_sha256,
            "diagnostics": [],
        },
        producer_command="implement-tdd",
    )
    return revision


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], text=True, capture_output=True, check=False)
