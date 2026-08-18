"""Read-only lifecycle readiness checks for Task Manifests."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from kotekomi_devtools.task_budget import TaskBudgetResult, audit_task_budget
from kotekomi_devtools.task_manifest import validate_task_manifest
from kotekomi_devtools.task_scope import ProtectedArtifact, TaskScopeResult, audit_task_scope

type JsonObject = dict[str, object]
type JsonDiagnostic = dict[str, str]
type LifecycleStatus = Literal["ready", "not_ready", "invalid"]

_PHASE_CHECKS: dict[str, tuple[str, ...]] = {
    "spec": ("validate-task", "preflight-task"),
    "candidate": ("validate-task", "scope-audit", "budget-audit", "protected-artifacts"),
    "verified": ("candidate-commit-record", "candidate-ci-record"),
    "main": ("promotion-topology", "main-ci-record"),
}
_CANDIDATE_RECORDS = ("candidate-commit.json", "candidate-ci.json")


@dataclass(frozen=True)
class LifecycleResult:
    """The public result of checking a Task Manifest lifecycle phase."""

    status: LifecycleStatus
    task_id: str | None
    phase: str
    diagnostics: tuple[JsonDiagnostic, ...]
    required_checks: tuple[str, ...]
    observed_records: tuple[JsonObject, ...] = ()

    @property
    def exit_code(self) -> int:
        return 0 if self.status == "ready" else 1

    def as_json(self) -> JsonObject:
        return {
            "status": self.status,
            "schema_version": 1,
            "task_id": self.task_id,
            "phase": self.phase,
            "diagnostics": list(self.diagnostics),
            "required_checks": list(self.required_checks),
            "observed_records": list(self.observed_records),
        }


def check_task_lifecycle(
    manifest_path: Path,
    *,
    phase: str,
    base_revision: str | None = None,
    head_revision: str | None = None,
    worktree: bool = False,
    records_dir: Path | None = None,
    main_base_revision: str | None = None,
    verified_revision: str | None = None,
) -> LifecycleResult:
    """Check one lifecycle phase without modifying repository or remote state."""
    required_checks = _PHASE_CHECKS.get(phase, ())
    if not required_checks:
        return _result(
            "invalid", None, phase, (_diagnostic("unknown_phase", "/phase", "known_phase"),)
        )

    validation = validate_task_manifest(manifest_path)
    if not validation.valid:
        return _result(
            "invalid",
            validation.task_id,
            phase,
            tuple(diagnostic.as_json() for diagnostic in validation.diagnostics),
            required_checks,
        )

    manifest = _load_manifest(manifest_path)
    if phase == "spec":
        return _check_spec(validation.task_id, manifest, phase, required_checks)
    if phase == "candidate":
        return _check_candidate(
            validation.task_id,
            manifest_path,
            manifest,
            phase,
            required_checks,
            base_revision,
            head_revision,
            worktree,
        )
    if phase == "verified":
        return _check_verified(validation.task_id, phase, required_checks, records_dir)
    return _check_main(
        validation.task_id,
        phase,
        required_checks,
        main_base_revision,
        verified_revision,
        head_revision,
    )


def _check_spec(
    task_id: str | None,
    manifest: JsonObject,
    phase: str,
    checks: tuple[str, ...],
) -> LifecycleResult:
    base = _resolve_commit(cast(str, manifest["baseline_revision"]))
    head = _resolve_commit("HEAD")
    if base is None:
        return _result(
            "invalid",
            task_id,
            phase,
            (
                _diagnostic(
                    "execution_base_not_found", "/baseline_revision", "execution_base_commit_exists"
                ),
            ),
            checks,
        )
    if head is None:
        return _result(
            "invalid",
            task_id,
            phase,
            (_diagnostic("head_not_found", "/head", "head_commit_exists"),),
            checks,
        )
    if head != base:
        return _result(
            "not_ready",
            task_id,
            phase,
            (_diagnostic("head_not_execution_base", "/head", "preflight_requires_execution_base"),),
            checks,
        )
    return _result("ready", task_id, phase, (), checks)


def _check_candidate(
    task_id: str | None,
    manifest_path: Path,
    manifest: JsonObject,
    phase: str,
    checks: tuple[str, ...],
    base: str | None,
    head: str | None,
    worktree: bool,
) -> LifecycleResult:
    if base is None or (head is None and not worktree):
        return _result(
            "invalid",
            task_id,
            phase,
            (
                _diagnostic(
                    "missing_revision_range",
                    "/base",
                    "candidate_requires_base_and_head_or_worktree",
                ),
            ),
            checks,
        )
    if head is not None and worktree:
        return _result(
            "invalid",
            task_id,
            phase,
            (
                _diagnostic(
                    "ambiguous_revision_range", "/head", "candidate_requires_exactly_one_target"
                ),
            ),
            checks,
        )

    revisions = (("/base", base),) if worktree else (("/base", base), ("/head", head))
    unresolved = tuple(
        _diagnostic("revision_not_found", location, "commit_exists")
        for location, revision in revisions
        if revision is None or _resolve_commit(revision) is None
    )
    if unresolved:
        return _result("invalid", task_id, phase, unresolved, checks)

    try:
        scope = audit_task_scope(
            manifest_path, base_revision=base, head_revision=head, worktree=worktree
        )
        budget = audit_task_budget(
            manifest_path, base_revision=base, head_revision=head, worktree=worktree
        )
    except RuntimeError:
        return _result(
            "invalid",
            task_id,
            phase,
            (
                _diagnostic(
                    "revision_range_unavailable", "/base", "candidate_revision_range_available"
                ),
            ),
            checks,
        )

    diagnostics = _candidate_diagnostics(manifest_path, manifest, scope, budget)
    return _result("ready" if not diagnostics else "not_ready", task_id, phase, diagnostics, checks)


def _candidate_diagnostics(
    manifest_path: Path,
    manifest: JsonObject,
    scope: TaskScopeResult,
    budget: TaskBudgetResult,
) -> tuple[JsonDiagnostic, ...]:
    """Classify a range while excluding frozen specification artifacts.

    A range can start before the specification commit. A protected file at its
    frozen digest is specification history, not a candidate modification.
    """
    frozen_paths = _frozen_paths(manifest_path, manifest, scope)
    diagnostics: list[JsonDiagnostic] = []
    for diagnostic in scope.diagnostics:
        if _ignored_scope_diagnostic(diagnostic.code, diagnostic.location, scope, frozen_paths):
            continue
        diagnostics.append(diagnostic.as_json())
    diagnostics.extend(
        diagnostic.as_json()
        for diagnostic in budget.diagnostics
        if diagnostic.code == "task_budget.budget_violation"
    )
    return tuple(sorted(diagnostics, key=_diagnostic_key))


def _frozen_paths(manifest_path: Path, manifest: JsonObject, scope: TaskScopeResult) -> set[str]:
    paths = {
        artifact.path
        for artifact in scope.protected_artifacts
        if artifact.actual_sha256 == artifact.expected_sha256
    }
    paths.add(cast(str, manifest["tdd_path"]))
    try:
        paths.add(manifest_path.resolve().relative_to(Path.cwd().resolve()).as_posix())
    except ValueError:
        pass
    return paths


def _ignored_scope_diagnostic(
    code: str, location: str, scope: TaskScopeResult, frozen_paths: set[str]
) -> bool:
    if code == "task_scope.scope_violation":
        index = _location_index(location, "/changed_paths/")
        return index is not None and scope.changed_paths[index].path in frozen_paths
    if code == "task_scope.protected_artifact_changed":
        artifact = _artifact_at_manifest_index(
            scope, _location_index(location, "/protected_artifacts/")
        )
        return artifact is not None and artifact.actual_sha256 == artifact.expected_sha256
    if code == "task_scope.protected_artifact_digest_mismatch":
        artifact = _artifact_at_manifest_index(
            scope, _location_index(location, "/protected_artifacts/")
        )
        return artifact is not None and not artifact.changed
    return False


def _location_index(location: str, prefix: str) -> int | None:
    if not location.startswith(prefix):
        return None
    value = location.removeprefix(prefix).split("/", maxsplit=1)[0]
    return int(value) if value.isdigit() else None


def _artifact_at_manifest_index(
    scope: TaskScopeResult, index: int | None
) -> ProtectedArtifact | None:
    return next(
        (artifact for artifact in scope.protected_artifacts if artifact.manifest_index == index),
        None,
    )


def _check_verified(
    task_id: str | None,
    phase: str,
    checks: tuple[str, ...],
    records_dir: Path | None,
) -> LifecycleResult:
    if records_dir is None:
        return _result(
            "invalid",
            task_id,
            phase,
            (_diagnostic("records_dir_missing", "/records_dir", "verified_requires_records_dir"),),
            checks,
        )

    diagnostics: list[JsonDiagnostic] = []
    records: list[JsonObject] = []
    for name in _CANDIDATE_RECORDS:
        path = records_dir / name
        if not path.is_file():
            diagnostics.append(
                _diagnostic(
                    "record_missing", f"/records/{name}", "verified_requires_candidate_records"
                )
            )
        else:
            records.append({"name": name, "path": str(path)})
            if not _is_json_object(path):
                diagnostics.append(
                    _diagnostic(
                        "record_invalid", f"/records/{name}", "verified_requires_candidate_records"
                    )
                )

    status: LifecycleStatus = "ready" if not diagnostics else "not_ready"
    if any(item["code"] == "task_lifecycle.record_invalid" for item in diagnostics):
        status = "invalid"
    return _result(status, task_id, phase, tuple(diagnostics), checks, tuple(records))


def _is_json_object(path: Path) -> bool:
    try:
        return isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False


def _check_main(
    task_id: str | None,
    phase: str,
    checks: tuple[str, ...],
    main_base: str | None,
    verified: str | None,
    head: str | None,
) -> LifecycleResult:
    revisions = (("/main_base", main_base), ("/verified", verified), ("/head", head))
    missing_main_revisions = (
        (main_base, "/main-base", "missing_main_base", "main_requires_main_base"),
        (verified, "/verified", "missing_verified", "main_requires_verified"),
        (head, "/head", "missing_head", "main_requires_head"),
    )
    diagnostics = [
        _diagnostic(code, location, rule)
        for value, location, code, rule in missing_main_revisions
        if value is None
    ]
    if diagnostics:
        return _result(
            "invalid",
            task_id,
            phase,
            tuple(diagnostics),
            checks,
        )
    resolved = tuple(
        (location, _resolve_commit(cast(str, revision))) for location, revision in revisions
    )
    unresolved = tuple(
        _diagnostic("revision_not_found", location, "commit_exists")
        for location, revision in resolved
        if revision is None
    )
    if unresolved:
        return _result("invalid", task_id, phase, unresolved, checks)

    main_base, verified, head = (cast(str, revision) for _, revision in resolved)
    parents = _parents(head)
    if len(parents) == 1:
        if head == verified and parents == (main_base,):
            return _result("ready", task_id, phase, (), checks)
        return _result(
            "not_ready",
            task_id,
            phase,
            (
                _diagnostic(
                    "direct_promotion_mismatch", "/head", "main_requires_expected_direct_promotion"
                ),
            ),
            checks,
        )
    if len(parents) == 2:
        if parents == (main_base, verified):
            return _result("ready", task_id, phase, (), checks)
        return _result(
            "not_ready",
            task_id,
            phase,
            (
                _diagnostic(
                    "merge_parent_mismatch", "/head", "main_requires_expected_merge_parents"
                ),
            ),
            checks,
        )
    return _result(
        "not_ready",
        task_id,
        phase,
        (
            _diagnostic(
                "unsupported_promotion_topology",
                "/head",
                "main_requires_direct_or_merge_promotion",
            ),
        ),
        checks,
    )


def _load_manifest(path: Path) -> JsonObject:
    return cast(JsonObject, tomllib.loads(path.read_text(encoding="utf-8")))


def _resolve_commit(revision: str) -> str | None:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _parents(revision: str) -> tuple[str, ...]:
    result = _git("show", "-s", "--format=%P", revision)
    return () if result is None or result.returncode != 0 else tuple(result.stdout.split())


def _git(*arguments: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError:
        return None


def _diagnostic(code: str, location: str, rule: str) -> JsonDiagnostic:
    return {"code": f"task_lifecycle.{code}", "location": location, "rule": rule}


def _diagnostic_key(diagnostic: JsonDiagnostic) -> tuple[str, str, str]:
    return diagnostic["location"], diagnostic["code"], diagnostic["rule"]


def _result(
    status: LifecycleStatus,
    task_id: str | None,
    phase: str,
    diagnostics: tuple[JsonDiagnostic, ...],
    required_checks: tuple[str, ...] = (),
    observed_records: tuple[JsonObject, ...] = (),
) -> LifecycleResult:
    return LifecycleResult(status, task_id, phase, diagnostics, required_checks, observed_records)
