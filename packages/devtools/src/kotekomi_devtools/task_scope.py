from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from kotekomi_devtools.task_manifest import Diagnostic, validate_task_manifest

type JsonObject = dict[str, object]
type AuditMode = Literal["revision", "worktree"]


@dataclass(frozen=True)
class ScopeDiagnostic:
    code: str
    location: str
    rule: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "rule": self.rule}


@dataclass(frozen=True)
class ChangedPath:
    path: str
    allowed: bool
    protected: bool

    def as_json(self) -> dict[str, str | bool]:
        return {"path": self.path, "allowed": self.allowed, "protected": self.protected}


@dataclass(frozen=True)
class ProtectedArtifact:
    path: str
    kind: str
    exists: bool
    changed: bool
    expected_sha256: str
    actual_sha256: str | None
    manifest_index: int

    def as_json(self) -> dict[str, str | bool | None]:
        return {
            "path": self.path,
            "kind": self.kind,
            "exists": self.exists,
            "changed": self.changed,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
        }


@dataclass(frozen=True)
class TaskScopeResult:
    schema_version: int | None
    task_id: str | None
    mode: AuditMode
    base_revision: str | None
    head_revision: str | None
    changed_paths: tuple[ChangedPath, ...]
    protected_artifacts: tuple[ProtectedArtifact, ...]
    diagnostics: tuple[ScopeDiagnostic | Diagnostic, ...]

    @property
    def status(
        self,
    ) -> Literal["clean", "scope_violation", "protected_artifact_violation", "invalid"]:
        codes = {diagnostic.code for diagnostic in self.diagnostics}
        if any(code.startswith("task_manifest.") for code in codes):
            return "invalid"
        if any(code.startswith("task_scope.protected_artifact_") for code in codes):
            return "protected_artifact_violation"
        if codes:
            return "scope_violation"
        return "clean"

    @property
    def exit_code(self) -> int:
        return {"clean": 0, "scope_violation": 1, "protected_artifact_violation": 1, "invalid": 2}[
            self.status
        ]

    def as_json(self) -> JsonObject:
        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "mode": self.mode,
            "base_revision": self.base_revision,
            "head_revision": self.head_revision,
            "changed_paths": [path.as_json() for path in self.changed_paths],
            "protected_artifacts": [artifact.as_json() for artifact in self.protected_artifacts],
            "diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics],
        }


def audit_task_scope(
    manifest_path: Path,
    *,
    base_revision: str,
    head_revision: str | None,
    worktree: bool,
) -> TaskScopeResult:
    mode: AuditMode = "worktree" if worktree else "revision"
    validation = validate_task_manifest(manifest_path)
    if not validation.valid:
        return TaskScopeResult(
            validation.schema_version,
            validation.task_id,
            mode,
            None,
            None,
            (),
            (),
            validation.diagnostics,
        )

    manifest = _load_manifest(manifest_path)
    base = _resolve_commit(base_revision)
    head = "WORKTREE" if worktree else _resolve_commit(cast(str, head_revision))
    paths = _changed_paths(base, head if not worktree else None, worktree)
    changed_paths = _changed_path_entries(paths, manifest)
    protected_artifacts = _protected_artifacts(paths, manifest, head, worktree)
    diagnostics = _diagnostics(changed_paths, protected_artifacts)
    return TaskScopeResult(
        validation.schema_version,
        validation.task_id,
        mode,
        base,
        head,
        changed_paths,
        protected_artifacts,
        diagnostics,
    )


def _load_manifest(path: Path) -> JsonObject:
    return cast(JsonObject, tomllib.loads(path.read_text(encoding="utf-8")))


def _resolve_commit(revision: str) -> str:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    if result.returncode != 0:
        raise RuntimeError(f"unable to resolve commit: {revision}")
    return result.stdout.decode("ascii").strip()


def _changed_paths(
    base_revision: str, head_revision: str | None, worktree: bool
) -> tuple[str, ...]:
    if worktree:
        paths = _worktree_changed_paths(base_revision)
        paths.update(_untracked_paths())
        return tuple(sorted(paths))

    return _revision_changed_paths(base_revision, cast(str, head_revision))


def _revision_changed_paths(base_revision: str, head_revision: str) -> tuple[str, ...]:
    commits = _git("rev-list", "--reverse", f"{base_revision}..{head_revision}")
    if commits.returncode != 0:
        raise RuntimeError("unable to inspect Git revision range")
    paths: set[str] = set()
    for commit in commits.stdout.decode("ascii").splitlines():
        changed = _git(
            "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "-z", commit
        )
        if changed.returncode != 0:
            raise RuntimeError("unable to inspect Git commit paths")
        commit_paths = _null_delimited_paths(changed.stdout)
        if _is_verification_receipt_commit(commit, commit_paths):
            continue
        paths.update(commit_paths)
    return tuple(sorted(paths))


def _is_verification_receipt_commit(commit: str, paths: tuple[str, ...]) -> bool:
    parents = _git("show", "-s", "--format=%P", commit)
    if parents.returncode != 0:
        raise RuntimeError("unable to inspect Git commit parents")
    parent_ids = parents.stdout.decode("ascii").split()
    if len(parent_ids) != 1 or len(paths) != 1:
        return False
    path = paths[0]
    parts = path.split("/")
    if len(parts) != 7 or parts[:3] != [".agent", "receipts", "verification"]:
        return False
    task_id, candidate, profile, filename = parts[3:]
    if profile not in {"portable-local", "authoritative-linux"}:
        return False
    if not filename.startswith("attempt-") or not filename.endswith(".json"):
        return False
    ordinal = filename.removeprefix("attempt-").removesuffix(".json")
    if len(ordinal) != 4 or not ordinal.isdigit() or int(ordinal) < 1:
        return False
    receipt = _revision_file(commit, path)
    if receipt is None:
        return False
    try:
        decoded: object = json.loads(receipt)
    except json.JSONDecodeError:
        return False
    if not isinstance(decoded, dict):
        return False
    payload = cast(JsonObject, decoded)
    return (
        payload.get("receipt_kind"),
        payload.get("task_id"),
        payload.get("candidate_revision"),
        payload.get("profile"),
        payload.get("attempt"),
    ) == (
        "candidate_verification",
        task_id,
        parent_ids[0],
        profile,
        int(ordinal),
    ) and candidate == parent_ids[0]


def _worktree_changed_paths(base_revision: str) -> set[str]:
    return _staged_index_paths(base_revision) | _modified_index_paths()


def _staged_index_paths(base_revision: str) -> set[str]:
    result = _git("ls-tree", "-r", "-z", base_revision)
    if result.returncode != 0:
        raise RuntimeError("unable to inspect Git tree")
    base_entries = _tree_entries(result.stdout)
    index_entries = dict(_index_entries(_index_output()))
    return {
        path
        for path in base_entries.keys() | index_entries.keys()
        if base_entries.get(path) != index_entries.get(path)
    }


def _modified_index_paths() -> set[str]:
    object_format = _object_format()
    return {
        path
        for path, (mode, object_id) in _index_entries(_index_output())
        if _worktree_path_changed(mode, object_id, path, object_format)
    }


def _index_output() -> bytes:
    result = _git("ls-files", "--stage", "-z")
    if result.returncode != 0:
        raise RuntimeError("unable to inspect Git index")
    return result.stdout


def _index_entries(output: bytes) -> tuple[tuple[str, tuple[str, str]], ...]:
    entries: list[tuple[str, tuple[str, str]]] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", maxsplit=1)
        mode, object_id, stage = metadata.decode("ascii").split(" ")
        if stage == "0":
            entries.append((path.decode("utf-8"), (mode, object_id)))
    return tuple(entries)


def _tree_entries(output: bytes) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", maxsplit=1)
        mode, kind, object_id = metadata.decode("ascii").split(" ")
        if kind == "blob":
            entries[path.decode("utf-8")] = (mode, object_id)
    return entries


def _object_format() -> str:
    result = _git("rev-parse", "--show-object-format")
    if result.returncode != 0:
        raise RuntimeError("unable to identify Git object format")
    return result.stdout.decode("ascii").strip()


def _worktree_path_changed(mode: str, object_id: str, path: str, object_format: str) -> bool:
    file_path = Path(path)
    try:
        file_mode = file_path.lstat().st_mode
    except OSError:
        return True
    if mode == "120000":
        if not stat.S_ISLNK(file_mode):
            return True
        data = os.fsencode(os.readlink(file_path))
        actual_mode = "120000"
    else:
        if not stat.S_ISREG(file_mode):
            return True
        data = file_path.read_bytes()
        actual_mode = "100755" if file_mode & stat.S_IXUSR else "100644"
    return actual_mode != mode or _blob_digest(data, object_format) != object_id


def _blob_digest(content: bytes, object_format: str) -> str:
    digest = hashlib.new(object_format)
    digest.update(f"blob {len(content)}\0".encode("ascii"))
    digest.update(content)
    return digest.hexdigest()


def _untracked_paths() -> tuple[str, ...]:
    result = _git("ls-files", "--others", "--exclude-standard", "-z")
    if result.returncode != 0:
        raise RuntimeError("unable to inspect untracked files")
    return _null_delimited_paths(result.stdout)


def _null_delimited_paths(output: bytes) -> tuple[str, ...]:
    return tuple(path.decode("utf-8") for path in output.split(b"\0") if path)


def _changed_path_entries(paths: tuple[str, ...], manifest: JsonObject) -> tuple[ChangedPath, ...]:
    allowed_paths = cast(list[str], manifest["allowed_paths"])
    protected_paths = {
        cast(str, artifact["path"])
        for artifact in cast(list[JsonObject], manifest["protected_artifacts"])
    }
    return tuple(
        ChangedPath(
            path,
            any(_allows(allowed_path, path) for allowed_path in allowed_paths),
            path in protected_paths,
        )
        for path in paths
    )


def _allows(allowed_path: str, changed_path: str) -> bool:
    return allowed_path == changed_path or (
        allowed_path.endswith("/") and changed_path.startswith(allowed_path)
    )


def _protected_artifacts(
    changed_paths: tuple[str, ...], manifest: JsonObject, head_revision: str, worktree: bool
) -> tuple[ProtectedArtifact, ...]:
    changed = set(changed_paths)
    artifacts = cast(list[JsonObject], manifest["protected_artifacts"])
    return tuple(
        _protected_artifact(artifact, index, changed, head_revision, worktree)
        for index, artifact in sorted(
            enumerate(artifacts), key=lambda item: cast(str, item[1]["path"])
        )
    )


def _protected_artifact(
    artifact: JsonObject,
    manifest_index: int,
    changed_paths: set[str],
    head_revision: str,
    worktree: bool,
) -> ProtectedArtifact:
    path = cast(str, artifact["path"])
    content = _worktree_file(path) if worktree else _revision_file(head_revision, path)
    actual_sha256 = hashlib.sha256(content).hexdigest() if content is not None else None
    return ProtectedArtifact(
        path,
        cast(str, artifact["kind"]),
        content is not None,
        path in changed_paths,
        cast(str, artifact["sha256"]),
        actual_sha256,
        manifest_index,
    )


def _revision_file(revision: str, path: str) -> bytes | None:
    result = _git("show", f"{revision}:{path}")
    return result.stdout if result.returncode == 0 else None


def _worktree_file(path: str) -> bytes | None:
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def _diagnostics(
    changed_paths: tuple[ChangedPath, ...], protected_artifacts: tuple[ProtectedArtifact, ...]
) -> tuple[ScopeDiagnostic, ...]:
    diagnostics: list[ScopeDiagnostic] = []
    for index, path in enumerate(changed_paths):
        if not path.allowed:
            diagnostics.append(
                ScopeDiagnostic(
                    "task_scope.scope_violation", f"/changed_paths/{index}/path", "allowed_path"
                )
            )
    for artifact in protected_artifacts:
        location = f"/protected_artifacts/{artifact.manifest_index}"
        if not artifact.exists:
            diagnostics.append(
                ScopeDiagnostic(
                    "task_scope.protected_artifact_missing",
                    f"{location}/path",
                    "protected_artifact_exists",
                )
            )
        if artifact.changed:
            diagnostics.append(
                ScopeDiagnostic(
                    "task_scope.protected_artifact_changed",
                    f"{location}/path",
                    "protected_artifact_unchanged",
                )
            )
        if (
            artifact.actual_sha256 is not None
            and artifact.actual_sha256 != artifact.expected_sha256
        ):
            diagnostics.append(
                ScopeDiagnostic(
                    "task_scope.protected_artifact_digest_mismatch",
                    f"{location}/actual_sha256",
                    "protected_artifact_digest",
                )
            )
    return tuple(sorted(diagnostics, key=lambda item: (item.location, item.code, item.rule)))


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", *arguments],
            capture_output=True,
            check=False,
            env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError as error:
        raise RuntimeError("unable to run git") from error
