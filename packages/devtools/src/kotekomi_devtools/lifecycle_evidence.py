"""Read-only Git and CI lifecycle evidence producers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_devtools.evidence_catalog import state_root, write_canonical_record

type Json = dict[str, Any]
_SHA1 = re.compile(r"[0-9a-f]{40}")
_CONCLUSIONS = {"success", "failure", "cancelled", "skipped"}


class LifecycleEvidenceError(ValueError):
    """Raised when a lifecycle fact cannot become canonical evidence."""


@dataclass(frozen=True)
class LifecycleEvidenceResult:
    """One canonical lifecycle record and its output copies."""

    payload: Json

    def as_json(self) -> Json:
        return self.payload


def record_candidate_commit(
    *,
    task_id: str,
    run_id: str,
    revision: str,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> LifecycleEvidenceResult:
    commit = _resolve_commit(revision)
    parents = _parents(commit)
    if not parents:
        raise LifecycleEvidenceError("candidate commit requires a first parent")
    payload: Json = {
        "schema_version": 1,
        "commit_sha": commit,
        "parent_sha": parents[0],
        "diagnostics": [],
    }
    return _publish(
        task_id,
        run_id,
        state_root_path,
        "candidate",
        "candidate_commit",
        "candidate",
        payload,
        "record-candidate-commit",
        output,
        markdown,
    )


def record_candidate_ci(
    *,
    task_id: str,
    run_id: str,
    ci_result: Path,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> LifecycleEvidenceResult:
    return _record_ci(
        task_id,
        run_id,
        ci_result,
        state_root_path,
        "candidate_ci",
        "candidate_ci",
        "candidate",
        "record-candidate-ci",
        output,
        markdown,
    )


def record_main_merge(
    *,
    task_id: str,
    run_id: str,
    revision: str,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> LifecycleEvidenceResult:
    merge = _resolve_commit(revision)
    parents = _parents(merge)
    if len(parents) != 2:
        raise LifecycleEvidenceError("main merge requires exactly two parents")
    payload: Json = {
        "schema_version": 1,
        "merge_commit": merge,
        "parent_commit": parents[0],
        "verified_parent_commit": parents[1],
        "diagnostics": [],
    }
    return _publish(
        task_id,
        run_id,
        state_root_path,
        "main",
        "main_merge",
        "main",
        payload,
        "record-main-merge",
        output,
        markdown,
    )


def record_main_ci(
    *,
    task_id: str,
    run_id: str,
    ci_result: Path,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> LifecycleEvidenceResult:
    return _record_ci(
        task_id,
        run_id,
        ci_result,
        state_root_path,
        "main_ci",
        "main_ci",
        "main",
        "record-main-ci",
        output,
        markdown,
    )


def record_branch_cleanup(
    *,
    task_id: str,
    run_id: str,
    branches: tuple[str, ...],
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> LifecycleEvidenceResult:
    if not branches:
        raise LifecycleEvidenceError("branch cleanup requires at least one --branch")
    if len(set(branches)) != len(branches):
        raise LifecycleEvidenceError("branch cleanup branches must be unique")
    remaining = sorted(branch for branch in branches if _branch_exists(branch))
    payload: Json = {
        "schema_version": 1,
        "branch_cleanup_complete": not remaining,
        "remaining_branches": remaining,
        "diagnostics": [],
    }
    return _publish(
        task_id,
        run_id,
        state_root_path,
        "main_ci",
        "cleanup",
        "cleanup",
        payload,
        "record-branch-cleanup",
        output,
        markdown,
    )


def _record_ci(
    task_id: str,
    run_id: str,
    ci_result: Path,
    state_root_path: Path | None,
    phase: str,
    evidence_type: str,
    subject_id: str,
    command: str,
    output: Path | None,
    markdown: Path | None,
) -> LifecycleEvidenceResult:
    source = read_ci_result(ci_result)
    head = cast(str, source["head_sha"])
    _resolve_commit(head)
    payload: Json = {
        "schema_version": 1,
        "conclusion": source["conclusion"],
        "head_sha": head,
        "ci_result_sha256": hashlib.sha256(ci_result.read_bytes()).hexdigest(),
        "diagnostics": [],
    }
    return _publish(
        task_id,
        run_id,
        state_root_path,
        phase,
        evidence_type,
        subject_id,
        payload,
        command,
        output,
        markdown,
    )


def _publish(
    task_id: str,
    run_id: str,
    state_root_path: Path | None,
    phase: str,
    evidence_type: str,
    subject_id: str,
    payload: Json,
    command: str,
    output: Path | None,
    markdown: Path | None,
) -> LifecycleEvidenceResult:
    root = state_root(state_root_path)
    write_canonical_record(
        root,
        task_id,
        run_id,
        phase=phase,
        evidence_type=evidence_type,
        subject_id=subject_id,
        payload=payload,
        producer_command=command,
    )
    _write_copies(payload, output, markdown)
    return LifecycleEvidenceResult(payload)


def read_ci_result(path: Path) -> Json:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LifecycleEvidenceError("CI result must be readable UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise LifecycleEvidenceError("CI result must be a JSON object")
    record = cast(dict[str, object], value)
    if type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        raise LifecycleEvidenceError("CI result requires schema_version 1")
    conclusion = record.get("conclusion")
    head = record.get("head_sha")
    if not isinstance(conclusion, str) or conclusion not in _CONCLUSIONS:
        raise LifecycleEvidenceError("CI result conclusion is invalid")
    if not isinstance(head, str) or _SHA1.fullmatch(head) is None:
        raise LifecycleEvidenceError("CI result head_sha must be a lowercase SHA-1")
    return cast(Json, record)


def _resolve_commit(revision: str) -> str:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    if result.returncode != 0 or _SHA1.fullmatch(result.stdout.strip()) is None:
        raise LifecycleEvidenceError(f"Git revision is not a local commit: {revision}")
    return result.stdout.strip()


def _parents(commit: str) -> tuple[str, ...]:
    result = _git("show", "-s", "--format=%P", commit)
    if result.returncode != 0:
        raise LifecycleEvidenceError(f"Git parents are unavailable: {commit}")
    return tuple(result.stdout.split())


def _branch_exists(branch: str) -> bool:
    local = _git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
    remote = _git("show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}")
    return local.returncode == 0 or remote.returncode == 0


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError as error:
        raise LifecycleEvidenceError("Git executable is unavailable") from error


def _write_copies(payload: Json, output: Path | None, markdown: Path | None) -> None:
    try:
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
            )
        if markdown:
            markdown.parent.mkdir(parents=True, exist_ok=True)
            markdown.write_text(
                "# Lifecycle Evidence\n\n```json\n"
                + json.dumps(payload, sort_keys=True, indent=2)
                + "\n```\n",
                encoding="utf-8",
            )
    except OSError as error:
        raise LifecycleEvidenceError("lifecycle evidence report copy is not writable") from error
