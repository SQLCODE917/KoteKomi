"""Abort an unchanged feature branch before it gains a candidate commit."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_devtools.evidence_catalog import (
    EvidenceError,
    state_root,
    validated_entries,
    write_canonical_record,
)
from kotekomi_devtools.tdd_workflow import mark_run_bootstrap_aborted

type Json = dict[str, Any]
_SHA1 = re.compile(r"[0-9a-f]{40}")


class BootstrapRunAbortError(ValueError):
    """Raised when a run cannot use the bootstrap abort path."""


@dataclass(frozen=True)
class BootstrapRunAbortResult:
    """One bootstrap abort result and its canonical record."""

    exit_code: int
    payload: Json

    def as_json(self) -> Json:
        return self.payload


def abort_bootstrap_run(
    *, task_id: str, run_id: str, state_root_path: Path | None
) -> BootstrapRunAbortResult:
    """Remove an unchanged local and remote feature branch without a result tag."""
    root = state_root(state_root_path)
    entries = _entries(root, task_id, run_id)
    branch = _branch(entries, root, task_id)
    status = _run_status(root, task_id, run_id)
    if status == "bootstrap_aborted":
        _require_no_candidate_evidence(entries)
        return _repeat_complete(root, entries, task_id, run_id, branch)
    if status not in {"active", "blocked"}:
        raise BootstrapRunAbortError("bootstrap abort requires an active or blocked run")
    _require_bootstrap_entries(entries)
    _require_no_candidate_evidence(entries)
    specification = _specification(entries, root)
    if (
        _local_branch_target(branch) != specification
        or _remote_branch_target(branch) != specification
    ):
        raise BootstrapRunAbortError("feature branch tips must equal the specification revision")

    local_delete = _git("branch", "-d", branch)
    diagnostics: list[Json] = []
    if local_delete.returncode != 0:
        diagnostics.append(_diagnostic("local_delete_failed", "git_branch_delete"))
        return _incomplete(root, task_id, run_id, branch, diagnostics)

    remote_delete = _git("push", "origin", "--delete", branch)
    if remote_delete.returncode != 0:
        diagnostics.append(_diagnostic("remote_delete_failed", "git_push_delete"))
    remaining = _remaining_branches(branch)
    if remaining:
        if not diagnostics:
            diagnostics.append(_diagnostic("branch_remaining", "feature_refs_absent"))
        return _write_result(root, task_id, run_id, False, remaining, diagnostics)
    return _write_result(root, task_id, run_id, True, [], diagnostics)


def _entries(root: Path, task_id: str, run_id: str) -> list[Json]:
    try:
        return validated_entries(root, task_id, run_id)
    except EvidenceError as error:
        raise BootstrapRunAbortError("run evidence is invalid") from error


def _require_bootstrap_entries(entries: list[Json]) -> None:
    kinds = {str(entry["evidence_type"]) for entry in entries}
    required = {"specification_revision", "feature_branch"}
    missing = sorted(required - kinds)
    if missing:
        raise BootstrapRunAbortError(f"bootstrap evidence is missing: {', '.join(missing)}")


def _require_no_candidate_evidence(entries: list[Json]) -> None:
    forbidden = {
        "candidate_commit",
        "candidate_verification_receipt",
        "candidate_ci",
        "main_promotion",
        "main_lifecycle",
        "main_ci",
        "task_result",
        "cleanup",
    }
    present = sorted(forbidden & {str(entry["evidence_type"]) for entry in entries})
    if present:
        raise BootstrapRunAbortError(
            f"bootstrap abort forbids evidence: {', '.join(present)}"
        )


def _branch(entries: list[Json], root: Path, task_id: str) -> str:
    _require_bootstrap_entries(entries)
    payload = _payload(root, entries, "feature_branch")
    branch = payload.get("branch")
    expected = f"feature/{task_id}"
    if branch != expected:
        raise BootstrapRunAbortError("feature branch evidence does not match task")
    return expected


def _specification(entries: list[Json], root: Path) -> str:
    specification = _payload(root, entries, "specification_revision").get(
        "specification_revision"
    )
    feature_specification = _payload(root, entries, "feature_branch").get(
        "specification_revision"
    )
    if (
        not isinstance(specification, str)
        or _SHA1.fullmatch(specification) is None
        or feature_specification != specification
    ):
        raise BootstrapRunAbortError("bootstrap evidence has invalid specification revision")
    return specification


def _payload(root: Path, entries: list[Json], evidence_type: str) -> Json:
    entry = next(item for item in entries if item["evidence_type"] == evidence_type)
    if entry.get("path_scope") != "state":
        raise BootstrapRunAbortError(f"{evidence_type} must use state evidence")
    try:
        payload = json.loads((root / str(entry["path"])).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BootstrapRunAbortError(f"{evidence_type} is unreadable") from error
    if not isinstance(payload, dict):
        raise BootstrapRunAbortError(f"{evidence_type} is invalid")
    return cast(Json, payload)


def _run_status(root: Path, task_id: str, run_id: str) -> str:
    path = root / "experiments" / task_id / "runs" / run_id / "run.json"
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BootstrapRunAbortError("run record is unreadable") from error
    if not isinstance(value, dict):
        raise BootstrapRunAbortError("run record has invalid status")
    record = cast(Json, value)
    status = record.get("status")
    if not isinstance(status, str):
        raise BootstrapRunAbortError("run record has invalid status")
    return status


def _repeat_complete(
    root: Path, entries: list[Json], task_id: str, run_id: str, branch: str
) -> BootstrapRunAbortResult:
    entry = next((item for item in entries if item["evidence_type"] == "bootstrap_abort"), None)
    if entry is None:
        raise BootstrapRunAbortError("bootstrap-aborted run requires bootstrap abort evidence")
    record = _payload(root, entries, "bootstrap_abort")
    if (
        record.get("status") != "complete"
        or record.get("branch_cleanup_complete") is not True
        or record.get("remaining_branches") != []
        or _remaining_branches(branch)
    ):
        raise BootstrapRunAbortError("bootstrap abort evidence conflicts with feature refs")
    return BootstrapRunAbortResult(0, _response(task_id, run_id, record))


def _incomplete(
    root: Path, task_id: str, run_id: str, branch: str, diagnostics: list[Json]
) -> BootstrapRunAbortResult:
    return _write_result(
        root, task_id, run_id, False, _remaining_branches(branch), diagnostics
    )


def _write_result(
    root: Path,
    task_id: str,
    run_id: str,
    complete: bool,
    remaining: list[str],
    diagnostics: list[Json],
) -> BootstrapRunAbortResult:
    record: Json = {
        "schema_version": 1,
        "status": "complete" if complete else "incomplete",
        "branch_cleanup_complete": complete,
        "remaining_branches": remaining,
        "diagnostics": diagnostics,
    }
    write_canonical_record(
        root,
        task_id,
        run_id,
        phase="candidate",
        evidence_type="bootstrap_abort",
        subject_id="bootstrap",
        payload=record,
        producer_command="abort-bootstrap-run",
    )
    if complete:
        mark_run_bootstrap_aborted(root, task_id, run_id)
    return BootstrapRunAbortResult(0 if complete else 2, _response(task_id, run_id, record))


def _response(task_id: str, run_id: str, record: Json) -> Json:
    return {
        "schema_version": 1,
        "status": record["status"],
        "task_id": task_id,
        "implementation_run_id": run_id,
        "bootstrap_abort": record,
    }


def _remaining_branches(branch: str) -> list[str]:
    remaining: list[str] = []
    if _local_branch_target(branch) is not None:
        remaining.append(f"refs/heads/{branch}")
    if _remote_branch_target(branch) is not None:
        remaining.append(f"refs/remotes/origin/{branch}")
    return remaining


def _local_branch_target(branch: str) -> str | None:
    result = _git("rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    target = result.stdout.strip()
    return target if result.returncode == 0 and _SHA1.fullmatch(target) else None


def _remote_branch_target(branch: str) -> str | None:
    result = _git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}")
    fields = result.stdout.split()
    return fields[0] if result.returncode == 0 and fields and _SHA1.fullmatch(fields[0]) else None


def _diagnostic(code: str, rule: str) -> Json:
    return {"code": f"bootstrap_abort.{code}", "location": "/branch", "rule": rule}


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], text=True, capture_output=True, check=False)
