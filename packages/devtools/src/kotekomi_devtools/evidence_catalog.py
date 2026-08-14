"""Deterministic run-scoped evidence records, index, and event log."""

from __future__ import annotations

import hashlib
import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

type Json = dict[str, Any]
PHASES = (
    "intake",
    "spec",
    "candidate",
    "verification",
    "candidate_ci",
    "main",
    "main_ci",
    "complete",
)
_TRUSTED_FIELDS: dict[str, tuple[str, ...]] = {
    "task_manifest": ("task_id", "tdd_path", "tdd_sha256"),
    "tdd_binding": ("task_id", "primary_tdd_path", "tdd_paths", "tdd_sha256"),
    "task_manifest_validation": ("status", "task_id", "tdd_path", "tdd_sha256", "diagnostics"),
    "candidate_lifecycle": ("ready", "diagnostics"),
    "candidate_commit": ("commit_sha", "parent_sha"),
    "verification_plan": ("status", "planned_checks"),
    "run_check": ("check_id", "outcome", "diagnostics"),
    "verify_checks": (
        "status",
        "planned_check_count",
        "executed_check_count",
        "verified_check_count",
        "failed_check_count",
    ),
    "candidate_ci": ("conclusion", "head_sha"),
    "main_merge": ("merge_commit", "parent_commit", "verified_parent_commit"),
    "main_lifecycle": ("ready", "diagnostics"),
    "main_ci": ("conclusion", "head_sha"),
    "cleanup": ("branch_cleanup_complete", "remaining_branches"),
    "receipt_chain_status": (
        "status",
        "receipt_total_count",
        "receipt_present_count",
        "receipt_missing_count",
        "digest_mismatch_count",
        "expected_receipts",
        "missing_receipts",
        "digest_mismatches",
        "diagnostics",
    ),
    "metrics_record": (
        "task_id",
        "implementation_run_id",
        "status",
        "planned_check_count",
        "verified_check_count",
        "failed_check_count",
        "repair_count",
        "diagnostics",
    ),
    "scorecard_record": (
        "task_id",
        "implementation_run_id",
        "status",
        "score_dimensions",
        "overall_score",
        "diagnostics",
    ),
}


class EvidenceError(ValueError):
    pass


def state_root(value: Path | None) -> Path:
    return (value or Path("~/.local/state/kotekomi")).expanduser().resolve()


def run_root(root: Path, task_id: str, run_id: str) -> Path:
    return root / "experiments" / task_id / "runs" / run_id


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_bytes(value))


def _load(path: Path) -> Json:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"invalid evidence JSON: {path}") from error
    if not isinstance(value, dict):
        raise EvidenceError(f"invalid evidence JSON: {path}")
    return cast(Json, value)


def _load_evidence_payload(path: Path, evidence_type: str) -> Json:
    if evidence_type == "task_manifest":
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise EvidenceError(f"invalid task manifest: {path}") from error
        return payload
    return _load(path)


def canonical_relative(
    evidence_type: str, task_id: str, run_id: str, subject_id: str = ""
) -> tuple[str, str]:
    run = f"experiments/{task_id}/runs/{run_id}"
    fixed = {
        "task_manifest_validation": f"{run}/spec/task-manifest-validation.json",
        "candidate_lifecycle": f"{run}/lifecycle/candidate.json",
        "candidate_commit": f"{run}/git/candidate-commit.json",
        "verification_plan": f"{run}/verification/verification-plan.json",
        "verify_checks": f"{run}/checks/verify-checks.json",
        "candidate_ci": f"{run}/ci/candidate.json",
        "main_merge": f"{run}/git/main-merge.json",
        "main_lifecycle": f"{run}/lifecycle/main.json",
        "main_ci": f"{run}/ci/main.json",
        "cleanup": f"{run}/cleanup/branch-cleanup.json",
        "receipt_chain_status": f"{run}/receipts/receipt-chain-status.json",
        "metrics_record": f"{run}/metrics/tdd-metrics.json",
        "scorecard_record": f"{run}/scorecard/tdd-scorecard.json",
        "tdd_binding": f"experiments/{task_id}/spec/tdd-binding.json",
    }
    if evidence_type == "task_manifest":
        return "repo", f".agent/tasks/{task_id}.toml"
    if evidence_type == "run_check":
        return (
            "state",
            f"{run}/checks/run-checks/{hashlib.sha256(subject_id.encode()).hexdigest()[:16]}.json",
        )
    if evidence_type not in fixed:
        raise EvidenceError(f"unknown evidence type: {evidence_type}")
    return "state", fixed[evidence_type]


def write_canonical_record(
    root: Path,
    task_id: str,
    run_id: str,
    *,
    phase: str,
    evidence_type: str,
    subject_id: str,
    payload: Json,
    producer_command: str,
) -> Path:
    """Write one run-scoped record then make it discoverable in the evidence index."""
    scope, relative_path = canonical_relative(evidence_type, task_id, run_id, subject_id)
    if scope != "state":
        raise EvidenceError(f"{evidence_type} is external evidence")
    path = root / relative_path
    _write(path, payload)
    index_record(
        root,
        task_id,
        run_id,
        phase=phase,
        evidence_type=evidence_type,
        subject_id=subject_id,
        path_scope=scope,
        relative_path=relative_path,
        producer_command=producer_command,
    )
    return path


def _index_path(root: Path, task: str, run: str) -> Path:
    return run_root(root, task, run) / "evidence" / "index.json"


def _events_path(root: Path, task: str, run: str) -> Path:
    return run_root(root, task, run) / "evidence" / "events.jsonl"


def read_index(root: Path, task: str, run: str) -> Json:
    path = _index_path(root, task, run)
    if not path.exists():
        return {
            "schema_version": 1,
            "task_id": task,
            "implementation_run_id": run,
            "entries": [],
            "diagnostics": [],
        }
    value = _load(path)
    if value.get("task_id") != task or value.get("implementation_run_id") != run:
        raise EvidenceError("evidence index identity mismatch")
    return value


def rebuild_index(root: Path, task: str, run: str) -> Json:
    """Recreate a missing index from the canonical records that already exist."""
    known_records = (
        ("intake", "tdd_binding", "binding"),
        ("spec", "task_manifest", "manifest"),
        ("spec", "task_manifest_validation", "manifest"),
        ("candidate", "candidate_lifecycle", "candidate"),
        ("candidate", "candidate_commit", "candidate"),
        ("verification", "verification_plan", "plan"),
        ("verification", "verify_checks", "verify-checks"),
        ("candidate_ci", "candidate_ci", "candidate"),
        ("main", "main_merge", "main"),
        ("main", "main_lifecycle", "main"),
        ("main_ci", "main_ci", "main"),
        ("main_ci", "cleanup", "cleanup"),
        ("complete", "receipt_chain_status", "receipt-chain"),
        ("complete", "metrics_record", run),
        ("complete", "scorecard_record", run),
    )
    index_path = _index_path(root, task, run)
    if index_path.exists():
        return read_index(root, task, run)
    for phase, evidence_type, subject_id in known_records:
        scope, relative_path = canonical_relative(evidence_type, task, run, subject_id)
        base = Path.cwd() if scope == "repo" else root
        if (base / relative_path).is_file():
            index_record(
                root,
                task,
                run,
                phase=phase,
                evidence_type=evidence_type,
                subject_id=subject_id,
                path_scope=scope,
                relative_path=relative_path,
                producer_command="evidence-index-rebuild",
            )
    checks_root = run_root(root, task, run) / "checks" / "run-checks"
    for path in sorted(checks_root.glob("*.json")) if checks_root.is_dir() else []:
        payload = _load(path)
        check_id = payload.get("check_id")
        if not isinstance(check_id, str):
            raise EvidenceError(f"run-check record missing check_id: {path}")
        scope, relative_path = canonical_relative("run_check", task, run, check_id)
        if relative_path != path.relative_to(root).as_posix():
            raise EvidenceError(f"run-check canonical path mismatch: {path}")
        index_record(
            root,
            task,
            run,
            phase="verification",
            evidence_type="run_check",
            subject_id=check_id,
            path_scope=scope,
            relative_path=relative_path,
            producer_command="evidence-index-rebuild",
        )
    return read_index(root, task, run)


def index_record(
    root: Path,
    task: str,
    run: str,
    *,
    phase: str,
    evidence_type: str,
    subject_id: str,
    path_scope: str,
    relative_path: str,
    producer_command: str,
    diagnostics: list[Json] | None = None,
) -> None:
    if (
        path_scope not in {"repo", "state"}
        or Path(relative_path).is_absolute()
        or ".." in Path(relative_path).parts
    ):
        raise EvidenceError("invalid evidence path")
    base = Path.cwd() if path_scope == "repo" else root
    target = base / relative_path
    if not target.is_file():
        raise EvidenceError(f"evidence file is missing: {target}")
    index = read_index(root, task, run)
    entry = {
        "phase": phase,
        "evidence_type": evidence_type,
        "subject_id": subject_id,
        "path_scope": path_scope,
        "path": relative_path,
        "sha256": digest(target),
        "producer_command": producer_command,
        "diagnostics": diagnostics or [],
    }
    key = (phase, evidence_type, subject_id)
    entries = [
        item
        for item in index["entries"]
        if (item["phase"], item["evidence_type"], item["subject_id"]) != key
    ]
    entries.append(entry)
    entries.sort(
        key=lambda item: (
            PHASES.index(item["phase"]),
            item["evidence_type"],
            item["subject_id"],
            item["path"],
        )
    )
    index["entries"] = entries
    _write(_index_path(root, task, run), index)
    event = {
        "schema_version": 1,
        "task_id": task,
        "implementation_run_id": run,
        "event_type": "evidence_indexed",
        "phase": phase,
        "evidence_type": evidence_type,
        "subject_id": subject_id,
        "status": "ready",
        "sha256": entry["sha256"],
        "created_at": datetime.now(UTC).isoformat(),
    }
    event_path = _events_path(root, task, run)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def validated_entries(root: Path, task: str, run: str) -> list[Json]:
    entries = read_index(root, task, run)["entries"]
    for entry in entries:
        base = Path.cwd() if entry["path_scope"] == "repo" else root
        path = base / entry["path"]
        if not path.is_file() or digest(path) != entry["sha256"]:
            raise EvidenceError(f"evidence digest mismatch: {entry['path']}")
        payload = _load_evidence_payload(path, entry["evidence_type"])
        trusted_fields = _TRUSTED_FIELDS.get(entry["evidence_type"])
        if trusted_fields is None:
            raise EvidenceError(f"unknown evidence type: {entry['evidence_type']}")
        missing = [field for field in trusted_fields if field not in payload]
        if missing:
            raise EvidenceError(
                f"evidence fields missing for {entry['evidence_type']}: {', '.join(missing)}"
            )
    return entries
