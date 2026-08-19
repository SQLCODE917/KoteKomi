"""Close an already-merged feature branch with portable Harness evidence."""

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
from kotekomi_devtools.lifecycle_evidence import read_ci_result

type Json = dict[str, Any]
_SHA1 = re.compile(r"[0-9a-f]{40}")


class FeatureBranchReconciliationError(ValueError):
    """Raised when historic feature-branch facts cannot be reconciled."""


@dataclass(frozen=True)
class FeatureBranchReconciliationResult:
    """One completed reconciliation result."""

    payload: Json

    def as_json(self) -> Json:
        return self.payload


def reconcile_merged_feature_branch(
    *,
    task_id: str,
    run_id: str,
    promotion: str,
    final_main: str,
    ci_result: Path,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> FeatureBranchReconciliationResult:
    """Record an existing task merge, then publish its result and cleanup evidence."""
    root = state_root(state_root_path)
    entries = _entries(root, task_id, run_id)
    specification = _payload(root, entries, "specification_revision")
    branch_evidence = _payload(root, entries, "feature_branch")
    candidate = _payload(root, entries, "candidate_commit")
    manifest = _payload(root, entries, "task_manifest_validation")
    if manifest.get("status") != "valid":
        raise FeatureBranchReconciliationError("task manifest validation is not valid")
    branch = branch_evidence.get("branch")
    expected_branch = f"feature/{task_id}"
    if branch != expected_branch:
        raise FeatureBranchReconciliationError("feature branch evidence does not match task")
    main_base = specification.get("specification_revision")
    candidate_commit = candidate.get("commit_sha")
    if not isinstance(main_base, str) or not isinstance(candidate_commit, str):
        raise FeatureBranchReconciliationError("task evidence has invalid commit identity")
    merge_commit = _resolve_commit(promotion)
    final_commit = _resolve_commit(final_main)
    if _resolve_commit("origin/main") != final_commit:
        raise FeatureBranchReconciliationError("final main must equal origin/main")
    if not _is_ancestor(merge_commit, final_commit):
        raise FeatureBranchReconciliationError("promotion must be an ancestor of final main")
    parents = _parents(merge_commit)
    if len(parents) != 2:
        raise FeatureBranchReconciliationError("promotion requires exactly two parents")
    if parents[0] != main_base:
        raise FeatureBranchReconciliationError(
            "promotion first parent must equal specification revision"
        )
    verified_parent = verified_merge_parent(root, entries, candidate_commit, main_base, parents[1])
    ci = read_ci_result(ci_result)
    if ci["conclusion"] != "success" or ci["head_sha"] != final_commit:
        raise FeatureBranchReconciliationError("final main CI must succeed for final main")

    tag = f"kotekomi/tasks/{task_id}/result"
    message = reconciliation_tag_message(task_id, run_id, merge_commit, final_commit, ci_result)
    message_sha256 = hashlib.sha256(message.encode("utf-8")).hexdigest()
    existing_result = _existing_result(root, entries)
    remote_tag_target = _remote_tag_target(tag)
    if existing_result is not None:
        _require_matching_result(existing_result, tag, final_commit, message_sha256)
        if remote_tag_target != final_commit:
            raise FeatureBranchReconciliationError(
                "published result tag does not match task result"
            )
        cleanup = _existing_cleanup(root, entries)
        if cleanup is not None and cleanup.get("branch_cleanup_complete") is True:
            response = _result_payload(
                task_id, run_id, merge_commit, final_commit, existing_result, cleanup
            )
            _write_copies(response, output, markdown)
            return FeatureBranchReconciliationResult(response)
    elif remote_tag_target is not None:
        raise FeatureBranchReconciliationError("result tag conflicts with reconciliation")

    if _remote_branch_target(expected_branch) != verified_parent:
        raise FeatureBranchReconciliationError(
            "remote feature tip must equal verified merge parent"
        )

    promotion_payload: Json = {
        "schema_version": 1,
        "promotion_kind": "merge",
        "promotion_commit": merge_commit,
        "parent_commit": main_base,
        "verified_parent_commit": verified_parent,
        "diagnostics": [],
    }
    lifecycle_payload: Json = {"schema_version": 1, "ready": True, "diagnostics": []}
    main_ci_payload: Json = {
        "schema_version": 1,
        "conclusion": "success",
        "head_sha": final_commit,
        "validated_promotion_commit": merge_commit,
        "ci_result_sha256": hashlib.sha256(ci_result.read_bytes()).hexdigest(),
        "diagnostics": [],
    }
    _publish(root, task_id, run_id, "main", "main_promotion", "main", promotion_payload)
    _publish(root, task_id, run_id, "main", "main_lifecycle", "main", lifecycle_payload)
    _publish(root, task_id, run_id, "main_ci", "main_ci", "main", main_ci_payload)

    if existing_result is None:
        _publish_tag(tag, final_commit, message)
        result: Json = {
            "schema_version": 1,
            "outcome": "completed",
            "tag": tag,
            "target_commit": final_commit,
            "tag_message_sha256": message_sha256,
            "diagnostics": [],
        }
        _publish(root, task_id, run_id, "complete", "task_result", "result", result)
    else:
        result = existing_result

    cleanup, errors = _cleanup_branch(expected_branch)
    _publish(root, task_id, run_id, "main_ci", "cleanup", "cleanup", cleanup)
    response = _result_payload(task_id, run_id, merge_commit, final_commit, result, cleanup)
    _write_copies(response, output, markdown)
    if errors:
        raise FeatureBranchReconciliationError("feature branch cleanup failed")
    return FeatureBranchReconciliationResult(response)


def _entries(root: Path, task_id: str, run_id: str) -> list[Json]:
    try:
        entries = validated_entries(root, task_id, run_id)
    except EvidenceError as error:
        raise FeatureBranchReconciliationError("run evidence is invalid") from error
    required = {
        "task_manifest_validation",
        "specification_revision",
        "feature_branch",
        "candidate_commit",
    }
    kinds = {str(entry["evidence_type"]) for entry in entries}
    missing = sorted(required - kinds)
    if missing:
        raise FeatureBranchReconciliationError(
            f"reconciliation evidence is missing: {', '.join(missing)}"
        )
    return entries


def _payload(root: Path, entries: list[Json], evidence_type: str) -> Json:
    entry = next(entry for entry in entries if entry["evidence_type"] == evidence_type)
    return _entry_payload(root, entry, evidence_type)


def _entry_payload(root: Path, entry: Json, evidence_type: str) -> Json:
    if entry.get("path_scope") != "state":
        raise FeatureBranchReconciliationError(f"{evidence_type} must use state evidence")
    try:
        value = json.loads((root / str(entry["path"])).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FeatureBranchReconciliationError(f"{evidence_type} is unreadable") from error
    if not isinstance(value, dict):
        raise FeatureBranchReconciliationError(f"{evidence_type} is invalid")
    return cast(Json, value)


def verified_merge_parent(
    root: Path,
    entries: list[Json],
    candidate_commit: str,
    specification_revision: str,
    merge_second_parent: str,
) -> str:
    if merge_second_parent == candidate_commit:
        return candidate_commit
    receipt = _portable_receipt(root, entries)
    receipt_commit = receipt.get("receipt_commit")
    if not isinstance(receipt_commit, str):
        raise FeatureBranchReconciliationError("portable receipt has invalid receipt commit")
    if merge_second_parent != receipt_commit:
        raise FeatureBranchReconciliationError(
            "promotion second parent must equal candidate or portable receipt commit"
        )
    if receipt.get("outcome") != "passed":
        raise FeatureBranchReconciliationError("portable receipt outcome must be passed")
    if receipt.get("candidate_revision") != candidate_commit:
        raise FeatureBranchReconciliationError(
            "portable receipt candidate revision must equal candidate commit"
        )
    if receipt.get("specification_revision") != specification_revision:
        raise FeatureBranchReconciliationError(
            "portable receipt specification revision must equal specification evidence"
        )
    return receipt_commit


def _portable_receipt(root: Path, entries: list[Json]) -> Json:
    entry = next(
        (
            entry
            for entry in entries
            if entry["evidence_type"] == "candidate_verification_receipt"
            and entry.get("subject_id") == "portable-local"
        ),
        None,
    )
    if entry is None:
        raise FeatureBranchReconciliationError(
            "portable receipt is required for receipt merge parent"
        )
    return _entry_payload(root, entry, "candidate_verification_receipt")


def _existing_result(root: Path, entries: list[Json]) -> Json | None:
    if not any(entry["evidence_type"] == "task_result" for entry in entries):
        return None
    return _payload(root, entries, "task_result")


def _existing_cleanup(root: Path, entries: list[Json]) -> Json | None:
    if not any(entry["evidence_type"] == "cleanup" for entry in entries):
        return None
    return _payload(root, entries, "cleanup")


def _require_matching_result(result: Json, tag: str, target: str, message_sha256: str) -> None:
    if (
        result.get("outcome") != "completed"
        or result.get("tag") != tag
        or result.get("target_commit") != target
        or result.get("tag_message_sha256") != message_sha256
    ):
        raise FeatureBranchReconciliationError("task result conflicts with reconciliation")


def _publish(
    root: Path,
    task_id: str,
    run_id: str,
    phase: str,
    evidence_type: str,
    subject_id: str,
    payload: Json,
) -> None:
    write_canonical_record(
        root,
        task_id,
        run_id,
        phase=phase,
        evidence_type=evidence_type,
        subject_id=subject_id,
        payload=payload,
        producer_command="reconcile-merged-feature-branch",
    )


def reconciliation_tag_message(
    task_id: str, run_id: str, promotion: str, final_main: str, ci_result: Path
) -> str:
    payload = {
        "schema_version": 1,
        "task_id": task_id,
        "implementation_run_id": run_id,
        "outcome": "completed",
        "promotion_commit": promotion,
        "final_main_commit": final_main,
        "main_ci_sha256": hashlib.sha256(ci_result.read_bytes()).hexdigest(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def _publish_tag(tag: str, target: str, message: str) -> None:
    if _local_tag_exists(tag):
        raise FeatureBranchReconciliationError("local result tag conflicts with reconciliation")
    _require_success(
        _git("tag", "-a", tag, target, "-m", message.rstrip("\n")),
        "result tag creation failed",
    )
    pushed = _git("push", "origin", f"refs/tags/{tag}")
    if pushed.returncode != 0:
        raise FeatureBranchReconciliationError("result tag push failed")
    if _remote_tag_target(tag) != target:
        raise FeatureBranchReconciliationError("published result tag target is invalid")


def _cleanup_branch(branch: str) -> tuple[Json, bool]:
    failed = False
    if _local_branch_exists(branch):
        failed = _git("branch", "-d", branch).returncode != 0
    if not failed and _remote_branch_target(branch) is not None:
        failed = _git("push", "origin", "--delete", branch).returncode != 0
    remaining: list[str] = []
    if _local_branch_exists(branch):
        remaining.append(f"refs/heads/{branch}")
    if _remote_branch_target(branch) is not None:
        remaining.append(f"refs/remotes/origin/{branch}")
    return (
        {
            "schema_version": 1,
            "branch_cleanup_complete": not remaining,
            "remaining_branches": remaining,
            "diagnostics": [],
        },
        failed or bool(remaining),
    )


def _result_payload(
    task_id: str,
    run_id: str,
    promotion: str,
    final_main: str,
    result: Json,
    cleanup: Json,
) -> Json:
    return {
        "schema_version": 1,
        "status": "complete" if cleanup.get("branch_cleanup_complete") else "blocked",
        "task_id": task_id,
        "implementation_run_id": run_id,
        "promotion_commit": promotion,
        "final_main_commit": final_main,
        "task_result": result,
        "cleanup": cleanup,
        "diagnostics": [],
    }


def _resolve_commit(revision: str) -> str:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    commit = result.stdout.strip()
    if result.returncode != 0 or _SHA1.fullmatch(commit) is None:
        raise FeatureBranchReconciliationError(f"Git revision is not a local commit: {revision}")
    return commit


def _parents(commit: str) -> tuple[str, ...]:
    result = _git("show", "-s", "--format=%P", commit)
    if result.returncode != 0:
        raise FeatureBranchReconciliationError("promotion parents are unavailable")
    return tuple(result.stdout.split())


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    return _git("merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _remote_branch_target(branch: str) -> str | None:
    result = _git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}")
    fields = result.stdout.split()
    return fields[0] if result.returncode == 0 and fields and _SHA1.fullmatch(fields[0]) else None


def _remote_tag_target(tag: str) -> str | None:
    result = _git("ls-remote", "--tags", "origin", f"refs/tags/{tag}*")
    lines = [line.split() for line in result.stdout.splitlines()]
    exact = f"refs/tags/{tag}"
    if not any(len(fields) == 2 and fields[1] == exact for fields in lines):
        return None
    peeled = next(
        (fields[0] for fields in lines if len(fields) == 2 and fields[1] == f"{exact}^{{}}"),
        None,
    )
    return peeled if peeled is not None and _SHA1.fullmatch(peeled) else None


def _local_branch_exists(branch: str) -> bool:
    return _git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def _local_tag_exists(tag: str) -> bool:
    return _git("show-ref", "--tags", "--verify", "--quiet", f"refs/tags/{tag}").returncode == 0


def _require_success(result: subprocess.CompletedProcess[str], message: str) -> None:
    if result.returncode != 0:
        raise FeatureBranchReconciliationError(message)


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
        raise FeatureBranchReconciliationError("Git executable is unavailable") from error


def _write_copies(payload: Json, output: Path | None, markdown: Path | None) -> None:
    try:
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        if markdown:
            markdown.parent.mkdir(parents=True, exist_ok=True)
            markdown.write_text(
                "# Feature Branch Reconciliation\n\n```json\n"
                + json.dumps(payload, sort_keys=True, indent=2)
                + "\n```\n"
            )
    except OSError as error:
        raise FeatureBranchReconciliationError(
            "reconciliation report copy is not writable"
        ) from error
