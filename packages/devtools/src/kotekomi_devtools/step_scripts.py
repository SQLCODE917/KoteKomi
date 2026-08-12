from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


class StepScriptError(Exception):
    pass


@dataclass(frozen=True)
class StepState:
    branch: str
    head: str
    origin_main: str
    remote_refs: dict[str, str]
    worktree_status: str


def step_preflight_payload(
    *,
    task_id: str,
    base: str,
    branch: str,
    expected_origin_main: str | None = None,
    origin_main_ref: str = "origin/main",
    remote_branches: list[str] | None = None,
    state_file: Path | None = None,
    cwd: Path = Path("."),
    recover_candidate: bool = False,
    allow_dirty_main: bool = False,
) -> dict[str, Any]:
    state = _load_step_state(
        state_file=state_file,
        cwd=cwd,
        origin_main_ref=origin_main_ref,
        remote_branches=remote_branches or [],
    )
    diagnostics: list[dict[str, str]] = []
    recovered = False

    if recover_candidate:
        if state.branch == "main":
            diagnostics.append(
                _step_diagnostic(
                    "dirty_main_refused",
                    "/branch",
                    "recover_candidate_refuses_main",
                )
            )
        if state.branch != branch:
            diagnostics.append(
                _step_diagnostic(
                    "branch_mismatch",
                    "/branch",
                    "expected_candidate_branch",
                )
            )
        if expected_origin_main is not None and (
            state.origin_main != expected_origin_main
        ):
            diagnostics.append(
                _step_diagnostic(
                    "origin_main_mismatch",
                    "/origin_main",
                    "expected_origin_main",
                )
            )
        if not diagnostics:
            if state_file is None:
                subprocess.run(
                    ["git", "reset", "--hard", base],
                    cwd=cwd,
                    check=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "clean", "-fd"],
                    cwd=cwd,
                    check=True,
                    text=True,
                )
                state = _load_step_state(
                    state_file=None,
                    cwd=cwd,
                    origin_main_ref=origin_main_ref,
                    remote_branches=remote_branches or [],
                )
            else:
                state = StepState(
                    branch=state.branch,
                    head=base,
                    origin_main=state.origin_main,
                    remote_refs=state.remote_refs,
                    worktree_status="",
                )
            recovered = True
    else:
        if state.branch != branch:
            diagnostics.append(
                _step_diagnostic("branch_mismatch", "/branch", "expected_branch")
            )
        if expected_origin_main is not None and (
            state.origin_main != expected_origin_main
        ):
            diagnostics.append(
                _step_diagnostic(
                    "origin_main_mismatch",
                    "/origin_main",
                    "expected_origin_main",
                )
            )
        if state.worktree_status:
            if state.branch == "main" and not allow_dirty_main:
                diagnostics.append(
                    _step_diagnostic(
                        "dirty_main_refused",
                        "/worktree_status",
                        "dirty_main_refused",
                    )
                )
            else:
                diagnostics.append(
                    _step_diagnostic(
                        "worktree_dirty",
                        "/worktree_status",
                        "worktree_must_be_clean",
                    )
                )

    return {
        "base": base,
        "branch": state.branch,
        "diagnostics": diagnostics,
        "expected_branch": branch,
        "head": state.head,
        "origin_main": state.origin_main,
        "recovered": recovered,
        "remote_refs": state.remote_refs,
        "schema_version": 1,
        "status": "ready" if not diagnostics else "invalid",
        "task_id": task_id,
        "worktree_status": state.worktree_status,
    }


def step_failure_payload(
    *,
    task_id: str,
    step: str,
    reason: str,
    state_file: Path | None = None,
    cwd: Path = Path("."),
    origin_main_ref: str = "origin/main",
    log: Path | None = None,
) -> dict[str, Any]:
    state = _load_step_state(
        state_file=state_file,
        cwd=cwd,
        origin_main_ref=origin_main_ref,
        remote_branches=[],
    )
    payload: dict[str, Any] = {
        "branch": state.branch,
        "head": state.head,
        "origin_main": state.origin_main,
        "reason": reason,
        "schema_version": 1,
        "status": "failed",
        "step": step,
        "task_id": task_id,
        "worktree_status": state.worktree_status,
    }
    if log is not None:
        payload["log_path"] = str(log)
        if log.exists():
            payload["log_sha256"] = _file_sha256(log)
        else:
            payload["log_missing"] = True
    return payload


def record_step_failure(
    *,
    task_id: str,
    step: str,
    reason: str,
    output: Path,
    log: Path | None = None,
    state_file: Path | None = None,
    cwd: Path = Path("."),
    origin_main_ref: str = "origin/main",
    force: bool = False,
) -> dict[str, str]:
    payload = step_failure_payload(
        task_id=task_id,
        step=step,
        reason=reason,
        state_file=state_file,
        cwd=cwd,
        origin_main_ref=origin_main_ref,
        log=log,
    )
    write_step_json(payload, output, force=force)
    return {
        "record_path": str(output),
        "record_sha256": _file_sha256(output),
    }


def write_step_json(
    payload: dict[str, Any],
    output: Path | None,
    *,
    force: bool,
) -> None:
    if output is None:
        return
    if output.exists() and not force:
        raise StepScriptError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _load_step_state(
    *,
    state_file: Path | None,
    cwd: Path,
    origin_main_ref: str,
    remote_branches: list[str],
) -> StepState:
    if state_file is not None:
        loaded = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise StepScriptError("step state file must contain a JSON object")
        payload = cast(dict[str, Any], loaded)
        remote_refs_value = payload.get("remote_refs", {})
        if not isinstance(remote_refs_value, dict):
            raise StepScriptError("step state remote_refs must be an object")
        remote_refs_payload = cast(dict[Any, Any], remote_refs_value)
        return StepState(
            branch=_required_string(payload, "branch"),
            head=_required_string(payload, "head"),
            origin_main=_required_string(payload, "origin_main"),
            remote_refs={
                str(key): str(value)
                for key, value in remote_refs_payload.items()
            },
            worktree_status=_required_string(payload, "worktree_status"),
        )

    return StepState(
        branch=_git(cwd, "branch", "--show-current"),
        head=_git(cwd, "rev-parse", "HEAD"),
        origin_main=_git(cwd, "rev-parse", origin_main_ref),
        remote_refs={
            branch: _remote_ref(cwd, branch) for branch in remote_branches
        },
        worktree_status=_git(cwd, "status", "--porcelain"),
    )


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise StepScriptError(f"step state requires string {key}")
    return value


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _remote_ref(cwd: Path, branch: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/remotes/origin/{branch}",
        ],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _step_diagnostic(code: str, location: str, rule: str) -> dict[str, str]:
    return {"code": code, "location": location, "rule": rule}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
