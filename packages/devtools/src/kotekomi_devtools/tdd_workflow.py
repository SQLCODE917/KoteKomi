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
from kotekomi_devtools.task_manifest import validate_task_manifest_text
from kotekomi_devtools.tdd_binding import bind_tdd

type Json = dict[str, Any]
PHASE_REQUIREMENTS = {
    "spec": {"tdd_binding", "task_manifest", "task_manifest_validation"},
    "candidate": {"candidate_lifecycle", "candidate_commit"},
    "verification": {"verification_plan", "verify_checks", "candidate_verification_receipt"},
    "candidate_ci": {"candidate_ci"},
    "main": {"main_promotion", "main_lifecycle"},
    "main_ci": {"main_ci", "cleanup"},
    "complete": {"receipt_chain_status"},
}


def _write(path: Path, value: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


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
        return "main", "produce_main_promotion_evidence", ["main_promotion"], []
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


def suggested_commands(
    action: str,
    task_id: str,
    run_id: str,
    manifest_path: str,
    root: Path,
    entries: list[Json],
) -> list[Json]:
    if action in {"blocked", "complete"}:
        return []
    command = {
        "create_task_manifest": "create-task-manifest",
        "produce_candidate_lifecycle_evidence": "lifecycle-check",
        "produce_candidate_commit_evidence": "record-candidate-commit",
        "produce_verification_evidence": "verification-plan",
        "verify_candidate": "verify-candidate",
        "produce_candidate_ci_evidence": "record-candidate-ci",
        "produce_main_promotion_evidence": "record-main-promotion",
        "produce_main_lifecycle_evidence": "lifecycle-check",
        "produce_main_ci_evidence": "record-main-ci",
        "produce_cleanup_evidence": "record-branch-cleanup",
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
    manifest, validation_status, manifest_identity, manifest_sha256, remote_error = (
        _manifest_for_run(root, task, run_id, binding)
    )
    if remote_error is not None:
        return 2, _remote_specification_blocked(task, run_id, remote_error)
    if manifest is not None:
        if manifest_identity.get("schema_version") == 1:
            return 0, _historical_result(
                binding_result.requested_tdd_path,
                binding,
                task,
                run_id,
                manifest,
                validation_status,
            )
        try:
            specification = _record_specification(root, task, run_id, manifest_sha256)
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
                    manifest_sha256=manifest_sha256,
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
    phase, action, missing, diagnostics = workflow_status(root, entries, manifest is not None)
    result: Json = {
        "schema_version": 1,
        "status": "blocked" if action == "blocked" else "ready",
        "task_id": task,
        "implementation_run_id": run_id,
        "requested_tdd_path": binding_result.requested_tdd_path,
        "primary_tdd_path": binding["primary_tdd_path"],
        "tdd_paths": binding["tdd_paths"],
        "tdd_sha256": binding["tdd_sha256"],
        "manifest_path": str(manifest) if manifest is not None else None,
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
        "suggested_commands": suggested_commands(
            action,
            task,
            run_id,
            str(manifest) if manifest is not None else "",
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


def _record_specification(root: Path, task: str, run_id: str, manifest_sha256: str) -> str:
    """Persist the remote-main specification once for a V2 run."""
    path = root / canonical_relative("specification_revision", task, run_id, "specification")[1]
    if path.is_file():
        payload = _read(path)
        if payload.get("manifest_sha256") != manifest_sha256:
            raise EvidenceError("specification manifest conflict")
        revision = payload.get("specification_revision")
        if isinstance(revision, str):
            return revision
        raise EvidenceError("specification revision is invalid")
    revision = _specification_revision(root, task, run_id)
    if revision is None:
        raise EvidenceError("remote specification revision is missing")
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


def _manifest_for_run(
    root: Path, task: str, run_id: str, binding: Json
) -> tuple[Path | None, str, Json, str, str | None]:
    """Return the manifest immutable to this run, or one remote-specification failure."""
    entries = validated_entries(root, task, run_id)
    specification = next(
        (item for item in entries if item["evidence_type"] == "specification_revision"), None
    )
    manifest_entry = next(
        (
            item
            for item in entries
            if item["evidence_type"] == "task_manifest" and item["path_scope"] == "state"
        ),
        None,
    )
    if specification is not None or manifest_entry is not None:
        if specification is None or manifest_entry is None:
            return None, "invalid", {}, "", "persisted specification evidence is incomplete"
        manifest = root / str(manifest_entry["path"])
        raw = manifest.read_bytes()
        specification_payload = _read(root / str(specification["path"]))
        if specification_payload.get("manifest_sha256") != hashlib.sha256(raw).hexdigest():
            return None, "invalid", {}, "", "persisted manifest digest conflicts with specification"
        return _validate_and_index_manifest(
            root, task, run_id, manifest, raw, binding, path_scope="state"
        )

    local_manifest = Path.cwd() / ".agent" / "tasks" / f"{task}.toml"
    if local_manifest.is_file() and _manifest_schema_version(local_manifest) == 1:
        return _validate_and_index_manifest(
            root,
            task,
            run_id,
            local_manifest,
            local_manifest.read_bytes(),
            binding,
            path_scope="repo",
        )
    if not local_manifest.exists():
        return None, "missing", {}, "", None
    fetched = _git("fetch", "origin", "main")
    if fetched.returncode != 0:
        return None, "invalid", {}, "", "origin main fetch failed"
    revision_result = _git("rev-parse", "refs/remotes/origin/main")
    if revision_result.returncode != 0:
        return None, "invalid", {}, "", "origin main cannot be resolved"
    revision = revision_result.stdout.strip()
    blob = _git_bytes("show", f"{revision}:.agent/tasks/{task}.toml")
    if blob.returncode != 0:
        return None, "invalid", {}, "", "remote task manifest is absent"
    _, _, remote_error = _validated_manifest_identity(blob.stdout, task, binding)
    if remote_error is not None:
        return None, "invalid", {}, "", remote_error
    remote_manifest = run_root(root, task, run_id) / "spec" / "task-manifest.toml"
    _write_bytes(remote_manifest, blob.stdout)
    result = _validate_and_index_manifest(
        root, task, run_id, remote_manifest, blob.stdout, binding, path_scope="state"
    )
    if result[4] is not None:
        return result
    _write(
        root / canonical_relative("specification_revision", task, run_id, "specification")[1],
        {
            "schema_version": 1,
            "specification_revision": revision,
            "manifest_sha256": hashlib.sha256(blob.stdout).hexdigest(),
            "diagnostics": [],
        },
    )
    _, specification_path = canonical_relative(
        "specification_revision", task, run_id, "specification"
    )
    index_record(
        root,
        task,
        run_id,
        phase="spec",
        evidence_type="specification_revision",
        subject_id="specification",
        path_scope="state",
        relative_path=specification_path,
        producer_command="implement-tdd",
    )
    return result


def _validate_and_index_manifest(
    root: Path,
    task: str,
    run_id: str,
    manifest: Path,
    raw: bytes,
    binding: Json,
    *,
    path_scope: str,
) -> tuple[Path | None, str, Json, str, str | None]:
    validation_status, identity, error = _validated_manifest_identity(raw, task, binding)
    if error is not None:
        return None, validation_status, identity, "", error
    text = raw.decode("utf-8")
    validation = validate_task_manifest_text(text)
    manifest_tdd_path = identity["tdd_path"]
    manifest_tdd_sha256 = identity["tdd_sha256"]
    relative_path = (
        manifest.relative_to(root).as_posix()
        if path_scope == "state"
        else f".agent/tasks/{task}.toml"
    )
    index_record(
        root,
        task,
        run_id,
        phase="spec",
        evidence_type="task_manifest",
        subject_id="manifest",
        path_scope=path_scope,
        relative_path=relative_path,
        producer_command="implement-tdd",
    )
    validation_payload = validation.as_json() | {
        "tdd_path": manifest_tdd_path,
        "tdd_sha256": manifest_tdd_sha256,
    }
    _, validation_path = canonical_relative("task_manifest_validation", task, run_id)
    _write(root / validation_path, validation_payload)
    index_record(
        root,
        task,
        run_id,
        phase="spec",
        evidence_type="task_manifest_validation",
        subject_id="manifest",
        path_scope="state",
        relative_path=validation_path,
        producer_command="implement-tdd",
    )
    return manifest, validation_status, identity, hashlib.sha256(raw).hexdigest(), None


def _validated_manifest_identity(
    raw: bytes, task: str, binding: Json
) -> tuple[str, Json, str | None]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "invalid", {}, "remote task manifest is not UTF-8"
    validation = validate_task_manifest_text(text)
    validation_status = "valid" if validation.valid else "invalid"
    try:
        identity = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        identity = {}
    if (
        not validation.valid
        or validation.task_id != task
        or identity.get("tdd_sha256") != binding["tdd_sha256"]
        or identity.get("tdd_path") not in cast(list[str], binding["tdd_paths"])
    ):
        return validation_status, identity, "remote manifest does not match TDD binding"
    return validation_status, identity, None


def _specification_revision(root: Path, task: str, run_id: str) -> str | None:
    path = root / canonical_relative("specification_revision", task, run_id, "specification")[1]
    if not path.is_file():
        return None
    revision = _read(path).get("specification_revision")
    return revision if isinstance(revision, str) else None


def _manifest_schema_version(manifest: Path) -> int | None:
    try:
        parsed = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    version = parsed.get("schema_version")
    return version if type(version) is int else None


def _historical_result(
    requested_tdd_path: str | None,
    binding: Json,
    task: str,
    run_id: str,
    manifest: Path,
    validation_status: str,
) -> Json:
    return {
        "schema_version": 1,
        "status": "historical",
        "task_id": task,
        "implementation_run_id": run_id,
        "requested_tdd_path": requested_tdd_path,
        "primary_tdd_path": binding["primary_tdd_path"],
        "tdd_paths": binding["tdd_paths"],
        "tdd_sha256": binding["tdd_sha256"],
        "manifest_path": str(manifest),
        "manifest_validation_status": validation_status,
        "implementation_phase": "historical",
        "next_action": None,
        "missing_evidence": [],
        "producer_arguments": {},
        "suggested_commands": [],
        "diagnostics": [],
    }


def _remote_specification_blocked(task: str, run_id: str, rule: str) -> Json:
    return {
        "schema_version": 1,
        "status": "blocked",
        "task_id": task,
        "implementation_run_id": run_id,
        "diagnostics": [
            {
                "code": "workflow.remote_specification_invalid",
                "location": "/specification",
                "rule": rule,
            }
        ],
    }


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], text=True, capture_output=True, check=False)


def _git_bytes(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *arguments], capture_output=True, check=False)
