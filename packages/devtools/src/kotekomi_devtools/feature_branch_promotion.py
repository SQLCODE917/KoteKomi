"""Mutating feature-branch promotion and terminal-result producers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_devtools.evidence_catalog import (
    EvidenceError,
    state_root,
    validated_entries,
    write_canonical_record,
)
from kotekomi_devtools.task_lifecycle import check_task_lifecycle

type Json = dict[str, Any]


class FeatureBranchPromotionError(ValueError):
    """A feature-branch transition could not be made canonical."""


@dataclass(frozen=True)
class FeatureBranchResult:
    exit_code: int
    payload: Json


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
    )


def _commit(revision: str, *, cwd: Path | None = None) -> str:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}", cwd=cwd)
    value = result.stdout.strip()
    if result.returncode or len(value) != 40:
        raise FeatureBranchPromotionError(f"commit is unavailable: {revision}")
    return value


def _parents(commit: str, *, cwd: Path | None = None) -> tuple[str, ...]:
    result = _git("show", "-s", "--format=%P", commit, cwd=cwd)
    if result.returncode:
        raise FeatureBranchPromotionError("commit parents are unavailable")
    return tuple(result.stdout.split())


def _payload(root: Path, task: str, run: str, kind: str, subject: str | None = None) -> Json:
    try:
        entries = validated_entries(root, task, run)
    except EvidenceError as error:
        raise FeatureBranchPromotionError("run evidence is invalid") from error
    entry = next(
        (
            item
            for item in entries
            if item["evidence_type"] == kind and (subject is None or item["subject_id"] == subject)
        ),
        None,
    )
    if entry is None or entry["path_scope"] != "state":
        raise FeatureBranchPromotionError(f"required evidence is missing: {kind}")
    try:
        value = json.loads((root / entry["path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FeatureBranchPromotionError(f"required evidence is invalid: {kind}") from error
    if not isinstance(value, dict):
        raise FeatureBranchPromotionError(f"required evidence is invalid: {kind}")
    return cast(Json, value)


def _remote(branch: str) -> str:
    result = _git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}")
    fields = result.stdout.split()
    if result.returncode or not fields:
        raise FeatureBranchPromotionError(f"remote branch is unavailable: {branch}")
    return fields[0]


def _result(code: int, **payload: Any) -> FeatureBranchResult:
    return FeatureBranchResult(code, {"schema_version": 1, **payload})


def promote_feature_branch(
    *, task_id: str, run_id: str, state_root_path: Path | None
) -> FeatureBranchResult:
    root = state_root(state_root_path)
    try:
        feature = _payload(root, task_id, run_id, "feature_branch")
        candidate = _payload(root, task_id, run_id, "candidate_commit")
        receipt = _payload(
            root, task_id, run_id, "candidate_verification_receipt", "portable-local"
        )
        ci = _payload(root, task_id, run_id, "candidate_ci")
        branch, receipt_commit = str(feature["branch"]), str(receipt["receipt_commit"])
        if (
            receipt.get("outcome") != "passed"
            or ci.get("conclusion") != "success"
            or ci.get("head_sha") != receipt_commit
        ):
            raise FeatureBranchPromotionError(
                "receipt and candidate CI must pass for the receipt commit"
            )
        fetched = _git("fetch", "origin", "main", branch)
        if fetched.returncode:
            raise FeatureBranchPromotionError("required remote revisions cannot be fetched")
        main_base, remote_receipt = _remote("main"), _remote(branch)
        if remote_receipt != receipt_commit or receipt.get("candidate_revision") != candidate.get(
            "commit_sha"
        ):
            raise FeatureBranchPromotionError(
                "receipt evidence does not match the remote feature tip"
            )
        if _parents(remote_receipt) != (str(candidate["commit_sha"]),):
            raise FeatureBranchPromotionError(
                "receipt commit must have only the recorded candidate parent"
            )
        changed = _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", remote_receipt
        ).stdout.splitlines()
        if changed != [receipt["receipt_path"]]:
            raise FeatureBranchPromotionError("receipt commit must change only its receipt path")
    except FeatureBranchPromotionError as error:
        return _result(
            2,
            status="blocked",
            diagnostics=[{"code": "promotion.prerequisite", "rule": str(error)}],
        )

    with tempfile.TemporaryDirectory(prefix="kotekomi-promotion-") as temporary:
        worktree = Path(temporary) / "merge"
        added = _git("worktree", "add", "--detach", str(worktree), main_base)
        if added.returncode:
            return _result(
                2,
                status="blocked",
                diagnostics=[{"code": "promotion.worktree", "rule": "detached_worktree_created"}],
            )
        try:
            merged = _git("merge", "--no-ff", "--no-edit", remote_receipt, cwd=worktree)
            if merged.returncode:
                _git("merge", "--abort", cwd=worktree)
                return _result(
                    1,
                    status="conflict",
                    diagnostics=[
                        {"code": "promotion.merge_conflict", "rule": "origin_main_unchanged"}
                    ],
                )
            promotion = _commit("HEAD", cwd=worktree)
            if _parents(promotion, cwd=worktree) != (main_base, remote_receipt):
                return _result(
                    2,
                    status="blocked",
                    diagnostics=[{"code": "promotion.topology", "rule": "ordered_merge_parents"}],
                )
            pushed = _git("push", "origin", f"{promotion}:refs/heads/main", cwd=worktree)
        finally:
            _git("worktree", "remove", str(worktree))
    if pushed.returncode or _remote("main") != promotion:
        return _result(
            2,
            status="blocked",
            diagnostics=[{"code": "promotion.remote_race", "rule": "non_force_main_push"}],
        )
    write_canonical_record(
        root,
        task_id,
        run_id,
        phase="main",
        evidence_type="main_promotion",
        subject_id="main",
        payload={
            "schema_version": 1,
            "promotion_kind": "merge",
            "promotion_commit": promotion,
            "parent_commit": main_base,
            "verified_parent_commit": remote_receipt,
            "diagnostics": [],
        },
        producer_command="promote-feature-branch",
    )
    lifecycle = check_task_lifecycle(
        Path(f".agent/tasks/{task_id}.toml"),
        phase="main",
        main_base_revision=main_base,
        verified_revision=remote_receipt,
        head_revision=promotion,
    ).as_json()
    write_canonical_record(
        root,
        task_id,
        run_id,
        phase="main",
        evidence_type="main_lifecycle",
        subject_id="main",
        payload={
            "schema_version": 1,
            "ready": lifecycle["status"] == "ready",
            "diagnostics": lifecycle["diagnostics"],
        },
        producer_command="promote-feature-branch",
    )
    return _result(
        0,
        status="promoted",
        promotion_commit=promotion,
        main_base=main_base,
        receipt_commit=remote_receipt,
        diagnostics=[],
    )


def _message(payload: Json) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _tag_matches(tag: str, target: str, message: str) -> bool:
    if _git("cat-file", "-e", f"refs/tags/{tag}^{{tag}}").returncode:
        return False
    exists = _git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    if exists.returncode:
        return False
    contents = _git("for-each-ref", f"refs/tags/{tag}", "--format=%(contents)").stdout.rstrip("\n")
    return exists.stdout.strip() == target and contents == message


def _remote_tag_target(tag: str) -> str | None:
    result = _git("ls-remote", "--tags", "origin", f"refs/tags/{tag}*")
    if result.returncode:
        return None
    refs = [line.split() for line in result.stdout.splitlines()]
    peeled = next(
        (fields[0] for fields in refs if len(fields) == 2 and fields[1] == f"refs/tags/{tag}^{{}}"),
        None,
    )
    direct = next(
        (fields[0] for fields in refs if len(fields) == 2 and fields[1] == f"refs/tags/{tag}"),
        None,
    )
    return peeled or direct


def _publish_tag(tag: str, target: str, message: str) -> bool:
    remote_target = _remote_tag_target(tag)
    local_exists = _git("rev-parse", "--verify", f"refs/tags/{tag}").returncode == 0
    if remote_target is not None:
        if (
            not local_exists
            and _git("fetch", "origin", f"refs/tags/{tag}:refs/tags/{tag}").returncode
        ):
            return False
        return _tag_matches(tag, target, message)
    if not local_exists and _git("tag", "-a", tag, target, "-m", message).returncode:
        return False
    if not _tag_matches(tag, target, message):
        return False
    pushed = _git("push", "origin", f"refs/tags/{tag}")
    return pushed.returncode == 0 and _remote_tag_target(tag) == target


def _cleanup(root: Path, task: str, run: str, branch: str, target: str, command: str) -> bool:
    local_deleted = True
    current_branch = _git("branch", "--show-current").stdout.strip()
    if current_branch == "main":
        if _git("status", "--porcelain").stdout:
            local_deleted = False
        elif _git("merge", "--ff-only", target).returncode:
            local_deleted = False
    for block in _git("worktree", "list", "--porcelain").stdout.strip().split("\n\n"):
        lines = block.splitlines()
        path = next(
            (line.removeprefix("worktree ") for line in lines if line.startswith("worktree ")), None
        )
        head = next(
            (
                line.removeprefix("branch refs/heads/")
                for line in lines
                if line.startswith("branch refs/heads/")
            ),
            None,
        )
        if path and head == branch:
            if _git("status", "--porcelain", cwd=Path(path)).stdout:
                local_deleted = False
                break
            if _git("switch", "--detach", target, cwd=Path(path)).returncode:
                local_deleted = False
                break
    local_branch_exists = (
        _git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    )
    if local_deleted and local_branch_exists:
        local_deleted = _git("branch", "-d", branch).returncode == 0
    remote_exists = (
        _git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}").returncode == 0
    )
    if local_deleted and remote_exists:
        _git("push", "origin", "--delete", branch)
    remaining: list[str] = []
    if _git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        remaining.append(branch)
    if _git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}").returncode == 0:
        remaining.append(f"origin/{branch}")
    write_canonical_record(
        root,
        task,
        run,
        phase="main_ci",
        evidence_type="cleanup",
        subject_id="cleanup",
        payload={
            "schema_version": 1,
            "branch_cleanup_complete": not remaining,
            "remaining_branches": remaining,
            "diagnostics": [],
        },
        producer_command=command,
    )
    return not remaining


def _complete(
    *, task_id: str, run_id: str, state_root_path: Path | None, abandoned: bool
) -> FeatureBranchResult:
    root = state_root(state_root_path)
    try:
        feature = _payload(root, task_id, run_id, "feature_branch")
        branch = str(feature["branch"])
        if abandoned:
            record = json.loads(
                (root / "experiments" / task_id / "runs" / run_id / "run.json").read_text()
            )
            if record.get("status") != "abandoned":
                raise FeatureBranchPromotionError("abandonment requires an abandoned run record")
            target = _remote(branch)
            tag_body: Json = {
                "schema_version": 1,
                "task_id": task_id,
                "implementation_run_id": run_id,
                "outcome": "abandoned",
                "feature_tip": target,
                "terminal_reason": "operator_abandoned",
            }
        else:
            promotion, ci, receipt = (
                _payload(root, task_id, run_id, "main_promotion"),
                _payload(root, task_id, run_id, "main_ci"),
                _payload(root, task_id, run_id, "candidate_verification_receipt", "portable-local"),
            )
            target = str(promotion["promotion_commit"])
            if (
                promotion.get("promotion_kind") != "merge"
                or ci.get("conclusion") != "success"
                or ci.get("head_sha") != target
            ):
                raise FeatureBranchPromotionError(
                    "completion requires successful main CI for merge promotion"
                )
            ci_sha256 = ci.get("ci_result_sha256")
            if not isinstance(ci_sha256, str) or len(ci_sha256) != 64:
                raise FeatureBranchPromotionError("main CI evidence has no result digest")
            tag_body = {
                "schema_version": 1,
                "task_id": task_id,
                "implementation_run_id": run_id,
                "outcome": "completed",
                "promotion_commit": target,
                "receipt_commit": receipt["receipt_commit"],
                "main_ci_sha256": ci_sha256,
            }
    except (FeatureBranchPromotionError, OSError, json.JSONDecodeError) as error:
        return _result(
            2,
            status="blocked",
            diagnostics=[{"code": "completion.prerequisite", "rule": str(error)}],
        )
    tag, message = f"kotekomi/tasks/{task_id}/result", _message(tag_body)
    if not _publish_tag(tag, target, message):
        return _result(
            2,
            status="blocked",
            diagnostics=[
                {"code": "completion.tag_conflict", "rule": "matching_published_result_tag"}
            ],
        )
    write_canonical_record(
        root,
        task_id,
        run_id,
        phase="complete",
        evidence_type="task_result",
        subject_id="result",
        payload={
            "schema_version": 1,
            "outcome": tag_body["outcome"],
            "tag": tag,
            "target_commit": target,
            "tag_message_sha256": hashlib.sha256(message.encode()).hexdigest(),
            "diagnostics": [],
        },
        producer_command="abandon-feature-branch" if abandoned else "complete-feature-branch",
    )
    cleaned = _cleanup(
        root,
        task_id,
        run_id,
        branch,
        target,
        "abandon-feature-branch" if abandoned else "complete-feature-branch",
    )
    return _result(
        0 if cleaned else 2,
        status="complete" if cleaned else "incomplete_cleanup",
        tag=tag,
        target_commit=target,
        diagnostics=[],
    )


def complete_feature_branch(**kwargs: Any) -> FeatureBranchResult:
    return _complete(abandoned=False, **kwargs)


def abandon_feature_branch(**kwargs: Any) -> FeatureBranchResult:
    return _complete(abandoned=True, **kwargs)
