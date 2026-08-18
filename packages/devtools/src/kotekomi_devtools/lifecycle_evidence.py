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

from kotekomi_devtools.evidence_catalog import (
    EvidenceError,
    state_root,
    validated_entries,
    write_canonical_record,
)

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
    _require_feature_tip(task_id, run_id, state_root_path, commit)
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


def create_feature_branch(
    *,
    task_id: str,
    run_id: str,
    specification_revision: str,
    manifest_sha256: str,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> LifecycleEvidenceResult:
    """Create one task branch at a persisted specification revision without switching HEAD."""
    specification = _resolve_commit(specification_revision)
    branch = f"feature/{task_id}"
    local = _ref_commit(f"refs/heads/{branch}")
    remote = _remote_ref_commit(branch)
    if (
        local is not None
        and local != specification
        or remote is not None
        and remote != specification
    ):
        raise LifecycleEvidenceError("feature branch conflicts with specification revision")
    created_local = local is None
    if created_local:
        _require_success(_git("branch", branch, specification), "feature branch creation failed")
        local = specification
    if remote is None:
        pushed = _git("push", "origin", f"refs/heads/{branch}:refs/heads/{branch}")
        if pushed.returncode != 0:
            if created_local:
                _git("update-ref", "-d", f"refs/heads/{branch}", specification)
            raise LifecycleEvidenceError("feature branch push failed")
        remote = _remote_ref_commit(branch)
    if local != specification or remote != specification:
        raise LifecycleEvidenceError("feature branch conflicts with specification revision")
    payload: Json = {
        "schema_version": 1,
        "branch": branch,
        "specification_revision": specification,
        "local_revision": local,
        "remote_revision": remote,
        "diagnostics": [],
    }
    return _publish(
        task_id,
        run_id,
        state_root_path,
        "candidate",
        "feature_branch",
        "feature-branch",
        payload,
        "create-feature-branch",
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


def record_main_promotion(
    *,
    task_id: str,
    run_id: str,
    revision: str,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> LifecycleEvidenceResult:
    promotion = _resolve_commit(revision)
    if _resolve_commit("origin/main") != promotion:
        raise LifecycleEvidenceError("main promotion must equal origin/main")
    parents = _parents(promotion)
    if len(parents) not in {1, 2}:
        raise LifecycleEvidenceError("main promotion requires one or two parents")
    payload: Json = {
        "schema_version": 1,
        "promotion_kind": "merge" if len(parents) == 2 else "direct",
        "promotion_commit": promotion,
        "parent_commit": parents[0],
        "verified_parent_commit": parents[1] if len(parents) == 2 else None,
        "diagnostics": [],
    }
    return _publish(
        task_id,
        run_id,
        state_root_path,
        "main",
        "main_promotion",
        "main",
        payload,
        "record-main-promotion",
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
    if len(set(branches)) != len(branches):
        raise LifecycleEvidenceError("branch cleanup branches must be unique")
    root = state_root(state_root_path)
    if not branches:
        _require_direct_main_promotion(root, task_id, run_id)
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


def _require_direct_main_promotion(root: Path, task_id: str, run_id: str) -> None:
    try:
        entries = validated_entries(root, task_id, run_id)
    except EvidenceError as error:
        raise LifecycleEvidenceError("main promotion evidence is invalid") from error
    entry = next((item for item in entries if item["evidence_type"] == "main_promotion"), None)
    if entry is None or entry["path_scope"] != "state":
        raise LifecycleEvidenceError("zero-branch cleanup requires direct main promotion evidence")
    try:
        value = json.loads((root / entry["path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleEvidenceError("main promotion evidence is invalid") from error
    if not isinstance(value, dict):
        raise LifecycleEvidenceError("main promotion evidence is invalid")
    promotion = cast(Json, value)
    if promotion.get("promotion_kind") != "direct":
        raise LifecycleEvidenceError("zero-branch cleanup requires direct main promotion evidence")


def _require_feature_tip(
    task_id: str, run_id: str, state_root_path: Path | None, commit: str
) -> None:
    root = state_root(state_root_path)
    try:
        entries = validated_entries(root, task_id, run_id)
    except EvidenceError as error:
        raise LifecycleEvidenceError("feature branch evidence is invalid") from error
    entry = next((item for item in entries if item["evidence_type"] == "feature_branch"), None)
    if entry is None:
        return
    path = root / entry["path"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleEvidenceError("feature branch evidence is invalid") from error
    if not isinstance(payload, dict):
        raise LifecycleEvidenceError("feature branch evidence is invalid")
    feature_evidence = cast(Json, payload)
    branch = feature_evidence.get("branch")
    if not isinstance(branch, str):
        raise LifecycleEvidenceError("feature branch evidence is invalid")
    if _remote_ref_commit(branch) != commit:
        raise LifecycleEvidenceError("candidate commit must equal the remote feature tip")
    specification = feature_evidence.get("specification_revision")
    if (
        not isinstance(specification, str)
        or specification == commit
        or not _is_ancestor(specification, commit)
    ):
        raise LifecycleEvidenceError(
            "candidate commit must descend from the specification revision"
        )


def _ref_commit(ref: str) -> str | None:
    result = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def _remote_ref_commit(branch: str) -> str | None:
    result = _git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}")
    if result.returncode != 0:
        return None
    fields = result.stdout.split()
    return fields[0] if fields and _SHA1.fullmatch(fields[0]) else None


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    return _git("merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _require_success(result: subprocess.CompletedProcess[str], message: str) -> None:
    if result.returncode != 0:
        raise LifecycleEvidenceError(message)


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
