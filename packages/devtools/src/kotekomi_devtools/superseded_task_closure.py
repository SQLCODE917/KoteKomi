"""Close a task whose patch reached main through a completed successor."""

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


class SupersededTaskClosureError(ValueError):
    """Raised when a superseded task cannot become terminal evidence."""


@dataclass(frozen=True)
class SupersededTaskClosureResult:
    """One superseded task closure result."""

    exit_code: int
    payload: Json


def close_superseded_task(
    *,
    task_id: str,
    run_id: str,
    successor_task_id: str,
    successor_run_id: str,
    handoff_commit: str,
    state_root_path: Path | None,
    output: Path | None = None,
    markdown: Path | None = None,
) -> SupersededTaskClosureResult:
    """Publish supersession evidence and remove one retained feature branch."""
    root = state_root(state_root_path)
    try:
        original_specification = _original_specification(root, task_id, run_id)
        successor = _successor(root, successor_task_id, successor_run_id)
        handoff = _commit(handoff_commit)
        branch = f"feature/{task_id}"
        local_tip = _local_branch(branch)
        remote_tip = _remote_branch(branch)
        if local_tip != handoff:
            raise SupersededTaskClosureError("handoff commit must equal local feature tip")
        if not _is_ancestor(remote_tip, successor["target_commit"]):
            raise SupersededTaskClosureError(
                "remote feature tip is not reachable from successor target"
            )
        if not _is_ancestor(handoff, local_tip):
            raise SupersededTaskClosureError(
                "handoff commit is not reachable from local feature branch"
            )
        delivery_head = _delivery_head(handoff)
        patch_id = _range_patch_id(original_specification, delivery_head)
        successor_patch_id = _range_patch_id(
            successor["specification_revision"], successor["candidate_commit"]
        )
        if patch_id != successor_patch_id:
            raise SupersededTaskClosureError("handoff patch does not match successor candidate")
        message = _message(
            task_id,
            run_id,
            successor_task_id,
            successor_run_id,
            successor["result_tag"],
            successor["target_commit"],
            handoff,
            patch_id,
            original_specification,
            delivery_head,
            successor["specification_revision"],
            successor_patch_id,
        )
        result_tag = f"kotekomi/tasks/{task_id}/result"
        handoff_tag = f"kotekomi/tasks/{task_id}/superseded-handoff"
        _publish_matching_tag(result_tag, successor["target_commit"], message)
        _publish_matching_tag(handoff_tag, handoff, message)
        result: Json = {
            "schema_version": 1,
            "outcome": "superseded",
            "tag": result_tag,
            "target_commit": successor["target_commit"],
            "tag_message_sha256": _digest_text(message),
            "supersession_reason": "scope_discovery",
            "successor_task_id": successor_task_id,
            "successor_run_id": successor_run_id,
            "successor_result_tag": successor["result_tag"],
            "successor_target_commit": successor["target_commit"],
            "handoff_commit": handoff,
            "handoff_patch_id": patch_id,
            "delivery_base_commit": original_specification,
            "delivery_head_commit": delivery_head,
            "delivery_patch_id": patch_id,
            "successor_delivery_base_commit": successor["specification_revision"],
            "successor_delivery_patch_id": successor_patch_id,
            "diagnostics": [],
        }
        write_canonical_record(
            root,
            task_id,
            run_id,
            phase="complete",
            evidence_type="task_result",
            subject_id="result",
            payload=result,
            producer_command="close-superseded-task",
        )
        cleanup, failed = _cleanup(branch, local_tip)
        write_canonical_record(
            root,
            task_id,
            run_id,
            phase="main_ci",
            evidence_type="cleanup",
            subject_id="cleanup",
            payload=cleanup,
            producer_command="close-superseded-task",
        )
        payload: Json = {
            "schema_version": 1,
            "status": "superseded" if not failed else "incomplete_cleanup",
            "task_id": task_id,
            "implementation_run_id": run_id,
            "result_tag": result_tag,
            "handoff_tag": handoff_tag,
            "successor_task_id": successor_task_id,
            "successor_run_id": successor_run_id,
            "successor_target_commit": successor["target_commit"],
            "handoff_commit": handoff,
            "cleanup": cleanup,
            "diagnostics": [],
        }
        _write_copies(payload, output, markdown)
        return SupersededTaskClosureResult(0 if not failed else 2, payload)
    except (EvidenceError, OSError, SupersededTaskClosureError) as error:
        return SupersededTaskClosureResult(
            2,
            {
                "schema_version": 1,
                "status": "blocked",
                "diagnostics": [
                    {"code": "superseded_closure.prerequisite", "location": "/", "rule": str(error)}
                ],
            },
        )


def _original_specification(root: Path, task_id: str, run_id: str) -> str:
    entries = _entries(root, task_id, run_id)
    kinds = {str(entry["evidence_type"]) for entry in entries}
    required = {"tdd_binding", "task_manifest", "task_manifest_validation"}
    if not required.issubset(kinds):
        raise SupersededTaskClosureError("original task specification evidence is incomplete")
    specification = _payload(root, entries, "specification_revision").get(
        "specification_revision"
    )
    if not isinstance(specification, str):
        raise SupersededTaskClosureError("original specification revision is invalid")
    return _commit(specification)


def _successor(root: Path, task_id: str, run_id: str) -> Json:
    entries = _entries(root, task_id, run_id)
    result = _payload(root, entries, "task_result")
    cleanup = _payload(root, entries, "cleanup")
    candidate = _payload(root, entries, "candidate_commit")
    specification = _payload(root, entries, "specification_revision")
    if result.get("outcome") != "completed" or cleanup.get("branch_cleanup_complete") is not True:
        raise SupersededTaskClosureError("successor task is not completed with cleanup")
    target = result.get("target_commit")
    tag = result.get("tag")
    candidate_commit = candidate.get("commit_sha")
    specification_revision = specification.get("specification_revision")
    if not all(
        isinstance(value, str) for value in (target, tag, candidate_commit, specification_revision)
    ):
        raise SupersededTaskClosureError("successor task result is invalid")
    if _remote_tag_target(cast(str, tag)) != target:
        raise SupersededTaskClosureError("published successor result tag does not match evidence")
    target_commit = _commit(cast(str, target))
    if not _is_ancestor(target_commit, _commit("origin/main")):
        raise SupersededTaskClosureError("successor target is not reachable from origin main")
    candidate_revision = _commit(cast(str, candidate_commit))
    if not _is_ancestor(candidate_revision, target_commit):
        raise SupersededTaskClosureError(
            "successor candidate is not reachable from successor target"
        )
    return {
        "result_tag": tag,
        "target_commit": target_commit,
        "candidate_commit": candidate_revision,
        "specification_revision": _commit(cast(str, specification_revision)),
    }


def _entries(root: Path, task_id: str, run_id: str) -> list[Json]:
    try:
        return validated_entries(root, task_id, run_id)
    except EvidenceError as error:
        raise SupersededTaskClosureError("run evidence is invalid") from error


def _payload(root: Path, entries: list[Json], evidence_type: str) -> Json:
    entry = next((item for item in entries if item["evidence_type"] == evidence_type), None)
    if entry is None or entry.get("path_scope") != "state":
        raise SupersededTaskClosureError(f"required evidence is missing: {evidence_type}")
    try:
        payload = json.loads((root / str(entry["path"])).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SupersededTaskClosureError(
            f"required evidence is unreadable: {evidence_type}"
        ) from error
    if not isinstance(payload, dict):
        raise SupersededTaskClosureError(f"required evidence is invalid: {evidence_type}")
    return cast(Json, payload)


def _message(
    task_id: str,
    run_id: str,
    successor_task_id: str,
    successor_run_id: str,
    successor_result_tag: str,
    successor_target_commit: str,
    handoff_commit: str,
    handoff_patch_id: str,
    delivery_base_commit: str,
    delivery_head_commit: str,
    successor_delivery_base_commit: str,
    successor_delivery_patch_id: str,
) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "task_id": task_id,
            "implementation_run_id": run_id,
            "outcome": "superseded",
            "supersession_reason": "scope_discovery",
            "successor_task_id": successor_task_id,
            "successor_run_id": successor_run_id,
            "successor_result_tag": successor_result_tag,
            "successor_target_commit": successor_target_commit,
            "handoff_commit": handoff_commit,
            "handoff_patch_id": handoff_patch_id,
            "delivery_base_commit": delivery_base_commit,
            "delivery_head_commit": delivery_head_commit,
            "delivery_patch_id": handoff_patch_id,
            "successor_delivery_base_commit": successor_delivery_base_commit,
            "successor_delivery_patch_id": successor_delivery_patch_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _publish_matching_tag(tag: str, target: str, message: str) -> None:
    remote_target = _remote_tag_target(tag)
    if remote_target is None:
        _require_success(
            _git("tag", "-a", tag, target, "-m", message.rstrip("\n")),
            "tag creation failed",
        )
        _require_success(_git("push", "origin", f"refs/tags/{tag}"), "tag push failed")
        if _remote_tag_target(tag) != target:
            raise SupersededTaskClosureError("published tag target is invalid")
        return
    if remote_target != target or _tag_message(tag) != message:
        raise SupersededTaskClosureError("published tag conflicts with superseded closure")


def _cleanup(branch: str, expected_local_tip: str) -> tuple[Json, bool]:
    local = _local_branch_optional(branch)
    failed = False
    if local is not None:
        deleted = _git("update-ref", "-d", f"refs/heads/{branch}", expected_local_tip)
        failed = deleted.returncode != 0
    if not failed and _remote_branch_optional(branch) is not None:
        failed = _git("push", "origin", "--delete", branch).returncode != 0
    remaining: list[str] = []
    if _local_branch_optional(branch) is not None:
        remaining.append(f"refs/heads/{branch}")
    if _remote_branch_optional(branch) is not None:
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


def _commit(revision: str) -> str:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    value = result.stdout.strip()
    if result.returncode or _SHA1.fullmatch(value) is None:
        raise SupersededTaskClosureError(f"Git revision is unavailable: {revision}")
    return value


def _local_branch(branch: str) -> str:
    value = _local_branch_optional(branch)
    if value is None:
        raise SupersededTaskClosureError("local feature branch is unavailable")
    return value


def _local_branch_optional(branch: str) -> str | None:
    result = _git("show-ref", "--verify", "--hash", f"refs/heads/{branch}")
    value = result.stdout.strip()
    return value if result.returncode == 0 and _SHA1.fullmatch(value) else None


def _remote_branch(branch: str) -> str:
    value = _remote_branch_optional(branch)
    if value is None:
        raise SupersededTaskClosureError("remote feature branch is unavailable")
    return value


def _remote_branch_optional(branch: str) -> str | None:
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
    return peeled if peeled and _SHA1.fullmatch(peeled) else None


def _tag_message(tag: str) -> str:
    result = _git("for-each-ref", f"refs/tags/{tag}", "--format=%(contents)")
    if result.returncode or not result.stdout:
        raise SupersededTaskClosureError("published tag message is unavailable locally")
    return result.stdout


def _delivery_head(feature_tip: str) -> str:
    current = feature_tip
    while True:
        parents = _parents(current)
        if len(parents) == 1 and _is_receipt_only_commit(current):
            current = parents[0]
            continue
        if len(parents) == 2 and _is_receipt_only_commit(parents[1]):
            current = parents[0]
            continue
        return current


def _parents(commit: str) -> tuple[str, ...]:
    result = _git("show", "-s", "--format=%P", commit)
    values = tuple(result.stdout.split())
    if result.returncode or not all(_SHA1.fullmatch(value) for value in values):
        raise SupersededTaskClosureError("commit parents are unavailable")
    return values


def _is_receipt_only_commit(commit: str) -> bool:
    parents = _parents(commit)
    changed = _git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    paths = changed.stdout.splitlines()
    if changed.returncode or len(parents) != 1 or len(paths) != 1:
        return False
    path = paths[0]
    parts = path.split("/")
    if len(parts) != 7 or parts[:3] != [".agent", "receipts", "verification"]:
        return False
    task_id, candidate, profile, filename = parts[3:]
    ordinal = filename.removeprefix("attempt-").removesuffix(".json")
    if (
        profile not in {"portable-local", "authoritative-linux"}
        or not filename.startswith("attempt-")
        or not filename.endswith(".json")
        or len(ordinal) != 4
        or not ordinal.isdigit()
        or int(ordinal) < 1
    ):
        return False
    receipt = _git("show", f"{commit}:{path}")
    if receipt.returncode:
        return False
    try:
        decoded = json.loads(receipt.stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(decoded, dict):
        return False
    payload = cast(Json, decoded)
    return candidate == parents[0] and (
        payload.get("receipt_kind"),
        payload.get("task_id"),
        payload.get("candidate_revision"),
        payload.get("profile"),
        payload.get("attempt"),
    ) == ("candidate_verification", task_id, parents[0], profile, int(ordinal))


def _range_patch_id(base: str, head: str) -> str:
    receipt_paths = _receipt_paths_in_range(base, head)
    show = _git(
        "diff",
        "--binary",
        "--no-ext-diff",
        base,
        head,
        "--",
        ".",
        *(f":(exclude){path}" for path in receipt_paths),
    )
    if show.returncode:
        raise SupersededTaskClosureError("commit patch is unavailable")
    try:
        result = subprocess.run(
            ["git", "patch-id", "--stable"],
            input=show.stdout,
            text=True,
            capture_output=True,
            check=False,
            env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError as error:
        raise SupersededTaskClosureError("Git executable is unavailable") from error
    fields = result.stdout.split()
    if result.returncode or len(fields) != 2 or _SHA1.fullmatch(fields[0]) is None:
        raise SupersededTaskClosureError("commit patch ID is unavailable")
    return fields[0]


def _receipt_paths_in_range(base: str, head: str) -> tuple[str, ...]:
    commits = _git("rev-list", "--reverse", f"{base}..{head}")
    if commits.returncode:
        raise SupersededTaskClosureError("delivery range is unavailable")
    paths: list[str] = []
    for commit in commits.stdout.splitlines():
        if _is_receipt_only_commit(commit):
            changed = _git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
            paths.extend(changed.stdout.splitlines())
    return tuple(sorted(set(paths)))


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    return _git("merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        raise SupersededTaskClosureError("Git executable is unavailable") from error


def _require_success(result: subprocess.CompletedProcess[str], message: str) -> None:
    if result.returncode:
        raise SupersededTaskClosureError(message)


def _write_copies(payload: Json, output: Path | None, markdown: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(
            "# Superseded Task Closure\n\n```json\n"
            + json.dumps(payload, indent=2)
            + "\n```\n"
        )
