"""Independent candidate verification and immutable receipt commits."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import tempfile
import tomllib
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from kotekomi_devtools.task_manifest import validate_task_manifest
from kotekomi_devtools.task_scope import audit_task_scope
from kotekomi_devtools.verification_execution import run_check
from kotekomi_devtools.verification_plan import VerificationPlanError, build_verification_plan

type JsonObject = dict[str, Any]
type Profile = Literal["portable-local", "authoritative-linux"]


@dataclass(frozen=True)
class CandidateVerificationResult:
    """The public result of one independent candidate verification attempt."""

    status: Literal["complete", "invalid"]
    task_id: str | None
    profile: str
    outcome: Literal["passed", "failed"] | None
    receipt_path: str | None
    receipt_sha256: str | None
    verification_branch: str | None
    verification_commit: str | None
    diagnostics: tuple[dict[str, str], ...]

    @property
    def exit_code(self) -> int:
        if self.status == "invalid":
            return 2
        return 0 if self.outcome == "passed" else 1

    def as_json(self) -> JsonObject:
        return {
            "status": self.status,
            "schema_version": 1,
            "task_id": self.task_id,
            "profile": self.profile,
            "outcome": self.outcome,
            "receipt_path": self.receipt_path,
            "receipt_sha256": self.receipt_sha256,
            "verification_branch": self.verification_branch,
            "verification_commit": self.verification_commit,
            "diagnostics": list(self.diagnostics),
        }


def verify_candidate(
    manifest_path: Path,
    *,
    base_revision: str,
    specification_revision: str,
    candidate_revision: str,
    profile: str,
) -> CandidateVerificationResult:
    """Verify one frozen candidate and commit one immutable receipt attempt."""
    if profile not in {"portable-local", "authoritative-linux"}:
        return _invalid(profile, "profile_invalid", "/profile", "known_verification_profile")
    if profile == "authoritative-linux" and platform.system() != "Linux":
        return _invalid(profile, "profile_platform_invalid", "/profile", "linux_required")
    if not _repository_relative(manifest_path):
        return _invalid(profile, "manifest_path_invalid", "/manifest", "repository_relative_posix")

    root = _repository_root()
    if root is None:
        return _invalid(profile, "repository_not_found", "/", "git_worktree_required")
    resolved = _revisions(root, base_revision, specification_revision, candidate_revision)
    if resolved is None:
        return _invalid(profile, "revision_not_found", "/revision", "commit_exists")
    base, specification, candidate = resolved
    if not _ancestor(root, base, specification):
        return _invalid(
            profile, "base_not_specification_ancestor", "/specification", "base_ancestor"
        )
    if specification == candidate:
        return _invalid(
            profile,
            "candidate_equals_specification",
            "/candidate",
            "candidate_after_specification",
        )
    if not _ancestor(root, specification, candidate):
        return _invalid(
            profile,
            "specification_not_candidate_ancestor",
            "/candidate",
            "specification_ancestor",
        )

    manifest_name = manifest_path.as_posix()
    specification_manifest = _blob(root, specification, manifest_name)
    candidate_manifest = _blob(root, candidate, manifest_name)
    if specification_manifest is None or candidate_manifest is None:
        return _invalid(
            profile,
            "manifest_blob_missing",
            "/manifest",
            "manifest_exists_at_specification_and_candidate",
        )
    if specification_manifest != candidate_manifest:
        return _invalid(
            profile, "manifest_changed", "/manifest", "manifest_frozen_after_specification"
        )

    with _detached_worktree(root, candidate) as candidate_root:
        if candidate_root is None:
            return _invalid(
                profile, "candidate_worktree_unavailable", "/candidate", "detached_worktree"
            )
        with _working_directory(candidate_root):
            validation = validate_task_manifest(manifest_path)
            if not validation.valid or validation.task_id is None:
                return _invalid(
                    profile,
                    "manifest_invalid",
                    "/manifest",
                    "valid_task_manifest",
                    tuple(diagnostic.as_json() for diagnostic in validation.diagnostics),
                )
            manifest = _manifest(candidate_root / manifest_path)
            if manifest is None:
                return _invalid(profile, "manifest_invalid", "/manifest", "readable_toml")
            manifest_base = manifest.get("baseline_revision")
            if manifest_base != base:
                return _invalid(
                    profile,
                    "manifest_base_mismatch",
                    "/baseline_revision",
                    "execution_base_matches",
                )
            task_id = validation.task_id
            tdd_path = manifest.get("tdd_path")
            specification_tdd = (
                _blob(root, specification, tdd_path) if isinstance(tdd_path, str) else None
            )
            candidate_tdd = _blob(root, candidate, tdd_path) if isinstance(tdd_path, str) else None
            if (
                specification_tdd is None
                or candidate_tdd is None
                or specification_tdd != candidate_tdd
                or _sha256(specification_tdd) != manifest.get("tdd_sha256")
            ):
                return _invalid(
                    profile, "tdd_changed", "/tdd_path", "tdd_frozen_after_specification"
                )

            scope = audit_task_scope(
                manifest_path,
                base_revision=specification,
                head_revision=candidate,
                worktree=False,
            )
            scope_payload = scope.as_json()
            plan_payload, check_results, execution_diagnostics = _execute_checks(
                manifest_path, specification, candidate
            )

    diagnostics = _sorted_diagnostics(
        [
            *(
                _diagnostic_from(value)
                for value in cast(list[JsonObject], scope_payload["diagnostics"])
            ),
            *execution_diagnostics,
        ]
    )
    outcome: Literal["passed", "failed"] = (
        "passed"
        if scope_payload["status"] == "clean"
        and plan_payload["status"] == "ready"
        and all(item["status"] == "passed" and item["exit_code"] == 0 for item in check_results)
        else "failed"
    )
    artifacts = _protected_artifacts(manifest, manifest_name, tdd_path, specification_manifest)
    branch = _verification_branch(task_id, candidate, cast(Profile, profile))
    branch_state = _branch_state(root, branch, task_id, candidate, cast(Profile, profile))
    if branch_state is None:
        return _invalid(
            profile, "verification_branch_invalid", "/verification_branch", "valid_receipt_chain"
        )
    parent, attempt = branch_state
    receipt_path = _receipt_path(task_id, candidate, cast(Profile, profile), attempt)
    receipt = {
        "schema_version": 1,
        "receipt_kind": "candidate_verification",
        "task_id": task_id,
        "attempt": attempt,
        "profile": profile,
        "outcome": outcome,
        "base_revision": base,
        "specification_revision": specification,
        "candidate_revision": candidate,
        "manifest": {"path": manifest_name, "sha256": _sha256(specification_manifest)},
        "protected_artifacts": artifacts,
        "scope_audit": scope_payload,
        "verification_plan": plan_payload,
        "check_results": check_results,
        "diagnostics": diagnostics,
    }
    receipt_bytes = _canonical_json(receipt)
    commit = _commit_receipt(root, parent, receipt_path, receipt_bytes)
    if commit is None:
        return _invalid(profile, "receipt_commit_failed", "/receipt", "verification_commit_created")
    old_value = _ref_value(root, branch)
    if old_value is not None and old_value != parent:
        return _invalid(
            profile, "verification_branch_changed", "/verification_branch", "expected_ref_value"
        )
    if not _update_ref(root, branch, commit, old_value):
        return _invalid(
            profile, "verification_branch_changed", "/verification_branch", "expected_ref_value"
        )
    return CandidateVerificationResult(
        "complete",
        task_id,
        profile,
        outcome,
        receipt_path,
        _sha256(receipt_bytes),
        branch,
        commit,
        tuple(diagnostics),
    )


def _execute_checks(
    manifest_path: Path, specification: str, candidate: str
) -> tuple[JsonObject, list[JsonObject], list[dict[str, str]]]:
    try:
        plan = build_verification_plan(
            manifest_path, base_revision=specification, head_revision=candidate
        )
    except VerificationPlanError:
        diagnostic = _diagnostic(
            "verification_plan_invalid", "/verification_plan", "verification_plan_builds"
        )
        return (
            {"status": "not_ready", "sha256": None, "planned_checks": []},
            [],
            [diagnostic],
        )
    planned_checks = [{"id": check.id, "argv": list(check.argv)} for check in plan.checks]
    plan_record = {
        "status": "ready" if plan.ready else "not_ready",
        "planned_checks": planned_checks,
    }
    plan_record["sha256"] = _sha256(_canonical_json(plan.as_json()))
    results: list[JsonObject] = []
    with tempfile.TemporaryDirectory(prefix="kotekomi-verify-") as directory:
        root = Path(directory)
        for check in plan.checks:
            record = run_check(
                check.id,
                output=root / f"{check.id}.json",
                log=root / f"{check.id}.log",
                argv=check.argv,
            )
            results.append(
                {
                    "check_id": record.check_id,
                    "argv": list(record.argv),
                    "status": record.status,
                    "exit_code": record.exit_code,
                    "log_sha256": record.log_sha256,
                }
            )
    diagnostics = [_diagnostic(item.code, item.location, item.rule) for item in plan.diagnostics]
    return plan_record, sorted(results, key=lambda item: str(item["check_id"])), diagnostics


def _protected_artifacts(
    manifest: JsonObject, manifest_path: str, tdd_path: object, manifest_bytes: bytes
) -> list[JsonObject]:
    artifacts: dict[str, str] = {manifest_path: _sha256(manifest_bytes)}
    if isinstance(tdd_path, str):
        artifacts[tdd_path] = str(manifest.get("tdd_sha256", ""))
    declared = manifest.get("protected_artifacts")
    if isinstance(declared, list):
        for entry in cast(list[object], declared):
            if not isinstance(entry, Mapping):
                continue
            artifact = cast(Mapping[str, object], entry)
            path = artifact.get("path")
            if isinstance(path, str):
                artifacts[path] = str(artifact.get("sha256", ""))
    return [{"path": path, "sha256": digest} for path, digest in sorted(artifacts.items())]


def _branch_state(
    root: Path, branch: str, task_id: str, candidate: str, profile: Profile
) -> tuple[str, int] | None:
    head = _ref_value(root, branch)
    if head is None:
        return candidate, 1
    if not _ancestor(root, candidate, head):
        return None
    commits = _git(root, "rev-list", "--reverse", f"{candidate}..{head}")
    if commits is None or not commits.stdout.strip():
        return None
    previous = candidate
    ordinal = 0
    for commit in commits.stdout.splitlines():
        parents = _git(root, "show", "-s", "--format=%P", commit)
        changed = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", commit)
        if parents is None or changed is None or parents.stdout.split() != [previous]:
            return None
        ordinal += 1
        expected_path = _receipt_path(task_id, candidate, profile, ordinal)
        if changed.stdout.splitlines() != [expected_path]:
            return None
        receipt_blob = _blob(root, commit, expected_path)
        if receipt_blob is None:
            return None
        try:
            decoded = json.loads(receipt_blob)
        except json.JSONDecodeError:
            return None
        if not isinstance(decoded, dict):
            return None
        receipt = cast(JsonObject, decoded)
        if (
            receipt.get("receipt_kind"),
            receipt.get("task_id"),
            receipt.get("candidate_revision"),
            receipt.get("profile"),
            receipt.get("attempt"),
        ) != ("candidate_verification", task_id, candidate, profile, ordinal):
            return None
        previous = commit
    return head, ordinal + 1


def _commit_receipt(root: Path, parent: str, receipt_path: str, receipt: bytes) -> str | None:
    with _detached_worktree(root, parent) as worktree:
        if worktree is None:
            return None
        destination = worktree / receipt_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(receipt)
        if _git(worktree, "add", "--", receipt_path) is None:
            return None
        committed = _git(worktree, "commit", "-m", "Record candidate verification receipt")
        if committed is None:
            return None
        revision = _git(worktree, "rev-parse", "HEAD")
        return revision.stdout.strip() if revision is not None else None


@contextmanager
def _detached_worktree(root: Path, revision: str) -> Generator[Path | None, None, None]:
    with tempfile.TemporaryDirectory(prefix="kotekomi-worktree-") as directory:
        path = Path(directory) / "worktree"
        added = _git(root, "worktree", "add", "--detach", str(path), revision)
        try:
            yield path if added is not None else None
        finally:
            if added is not None:
                _git(root, "worktree", "remove", "--force", str(path))


@contextmanager
def _working_directory(path: Path) -> Generator[None, None, None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _repository_root() -> Path | None:
    result = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()) if result is not None else None


def _revisions(root: Path, *revisions: str) -> tuple[str, str, str] | None:
    resolved = tuple(_resolve(root, revision) for revision in revisions)
    if any(value is None for value in resolved):
        return None
    return cast(tuple[str, str, str], resolved)


def _resolve(root: Path, revision: str) -> str | None:
    result = _git(root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    return result.stdout.strip() if result is not None else None


def _ancestor(root: Path, older: str, newer: str) -> bool:
    result = _git(root, "merge-base", "--is-ancestor", older, newer, allow_failure=True)
    return result is not None and result.returncode == 0


def _blob(root: Path, revision: str, path: str) -> bytes | None:
    result = _git_bytes(root, "show", f"{revision}:{path}", allow_failure=True)
    return result.stdout if result is not None and result.returncode == 0 else None


def _manifest(path: Path) -> JsonObject | None:
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return payload


def _verification_branch(task_id: str, candidate: str, profile: Profile) -> str:
    return f"refs/heads/kotekomi-verification/{task_id}/{candidate}/{profile}"


def _receipt_path(task_id: str, candidate: str, profile: Profile, attempt: int) -> str:
    return (
        f".agent/receipts/verification/{task_id}/{candidate}/{profile}/attempt-{attempt:04d}.json"
    )


def _ref_value(root: Path, ref: str) -> str | None:
    result = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}", allow_failure=True)
    return result.stdout.strip() if result is not None and result.returncode == 0 else None


def _update_ref(root: Path, ref: str, new: str, old: str | None) -> bool:
    if old is None:
        object_format = _git(root, "rev-parse", "--show-object-format")
        if object_format is None:
            return False
        old = "0" * (64 if object_format.stdout.strip() == "sha256" else 40)
    result = _git(root, "update-ref", ref, new, old, allow_failure=True)
    return result is not None and result.returncode == 0


def _repository_relative(path: Path) -> bool:
    value = path.as_posix()
    return (
        not path.is_absolute()
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in PurePosixPath(value).parts)
    )


def _git(
    cwd: Path,
    *arguments: str,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError:
        return None
    if result.returncode != 0 and not allow_failure:
        return None
    return result


def _git_bytes(
    cwd: Path, *arguments: str, allow_failure: bool = False
) -> subprocess.CompletedProcess[bytes] | None:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", *arguments],
            cwd=cwd,
            capture_output=True,
            text=False,
            check=False,
            env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError:
        return None
    if result.returncode != 0 and not allow_failure:
        return None
    return result


def _canonical_json(value: object) -> bytes:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{serialized}\n".encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _diagnostic(code: str, location: str, rule: str) -> dict[str, str]:
    return {"code": code, "location": location, "rule": rule}


def _diagnostic_from(value: JsonObject) -> dict[str, str]:
    return _diagnostic(str(value["code"]), str(value["location"]), str(value["rule"]))


def _sorted_diagnostics(values: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(values, key=lambda item: (item["location"], item["code"], item["rule"]))


def _invalid(
    profile: str,
    code: str,
    location: str,
    rule: str,
    diagnostics: tuple[dict[str, str], ...] = (),
) -> CandidateVerificationResult:
    return CandidateVerificationResult(
        "invalid",
        None,
        profile,
        None,
        None,
        None,
        None,
        None,
        tuple([_diagnostic(code, location, rule), *diagnostics]),
    )
