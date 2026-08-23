"""Read-only readiness checks for a validated Task Manifest."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_devtools.task_manifest import Diagnostic, validate_task_manifest

type JsonObject = dict[str, Any]
_WILDCARD_CHARACTERS = frozenset("*?[]")
_REGULAR_GIT_MODES = frozenset({"100644", "100755"})


@dataclass(frozen=True)
class PreflightDiagnostic:
    code: str
    location: str
    rule: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "rule": self.rule}


@dataclass(frozen=True)
class PreflightResult:
    schema_version: int | None
    task_id: str | None
    manifest_sha256: str | None
    manifest_file_sha256: str | None
    execution_base_revision: str | None
    diagnostics: tuple[PreflightDiagnostic | Diagnostic, ...]

    @property
    def ready(self) -> bool:
        return not self.diagnostics

    def as_json(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "not_ready",
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "manifest_sha256": self.manifest_sha256,
            "manifest_file_sha256": self.manifest_file_sha256,
            "execution_base_revision": self.execution_base_revision,
            "diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics],
        }


def preflight_task(manifest_path: str) -> PreflightResult:
    stage_one = _stage_one_diagnostics(manifest_path)
    repository_root = _repository_root()
    if repository_root is None:
        stage_one.append(_diagnostic("repository_violation", "/repository", "git_repository"))
    elif not _is_current_directory(repository_root):
        stage_one.append(_diagnostic("repository_violation", "/repository", "repository_root"))

    if stage_one:
        return PreflightResult(None, None, None, None, None, _sorted(stage_one))

    assert repository_root is not None
    path = repository_root / manifest_path
    manifest_file_sha256 = _file_digest(path)
    validation = validate_task_manifest(path)
    if not validation.valid:
        return PreflightResult(
            validation.schema_version,
            validation.task_id,
            None,
            manifest_file_sha256,
            None,
            validation.diagnostics,
        )

    parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    diagnostics, execution_base = _stage_three(repository_root, manifest_path, parsed)
    return PreflightResult(
        validation.schema_version,
        validation.task_id,
        validation.manifest_sha256,
        manifest_file_sha256,
        execution_base,
        _sorted(diagnostics),
    )


def _stage_one_diagnostics(manifest_path: str) -> list[PreflightDiagnostic]:
    diagnostics: list[PreflightDiagnostic] = []
    if not _is_repository_relative_posix_path(manifest_path):
        diagnostics.append(
            _diagnostic("manifest_path_violation", "/manifest_path", "repository_relative_posix")
        )
    if manifest_path.endswith("/"):
        diagnostics.append(_diagnostic("manifest_path_violation", "/manifest_path", "exact_file"))
    return diagnostics


def _is_repository_relative_posix_path(path: str) -> bool:
    if not path or path.startswith(("/", "~")) or "\\" in path or "//" in path:
        return False
    if _WILDCARD_CHARACTERS.intersection(path):
        return False
    return all(part not in {".", ".."} for part in path.split("/"))


def _stage_three(
    root: Path,
    manifest_path: str,
    manifest: JsonObject,
) -> tuple[list[PreflightDiagnostic], str | None]:
    diagnostics: list[PreflightDiagnostic] = []
    execution_base = _execution_base(manifest_path)
    if execution_base is not None:
        if not _committed_regular_file(execution_base, manifest_path) or not _current_regular_file(
            root, manifest_path
        ):
            diagnostics.append(
                _diagnostic("manifest_violation", "/manifest_path", "tracked_regular_file")
            )
        if _git_stdout("rev-parse", "HEAD") != execution_base:
            diagnostics.append(
                _diagnostic("manifest_violation", "/manifest_path", "head_is_execution_base")
            )

    if _worktree_is_dirty():
        diagnostics.append(_diagnostic("repository_violation", "/repository", "clean_worktree"))

    baseline = manifest["baseline_revision"]
    baseline_revision = _commit_revision(baseline)
    if baseline_revision is None:
        diagnostics.append(_diagnostic("revision_violation", "/baseline_revision", "commit_exists"))
    elif execution_base is not None and not _is_ancestor(baseline_revision, execution_base):
        diagnostics.append(
            _diagnostic("revision_violation", "/baseline_revision", "ancestor_of_execution_base")
        )

    if execution_base is not None:
        _lock_tdd(diagnostics, root, execution_base, manifest)
        _lock_protected_artifacts(diagnostics, root, execution_base, manifest)
        _check_reference_paths(diagnostics, root, execution_base, manifest)
        _check_dependency_receipts(diagnostics, execution_base, manifest)

    _check_allowed_paths(diagnostics, root, manifest_path, manifest)
    return diagnostics, execution_base


def _lock_tdd(
    diagnostics: list[PreflightDiagnostic], root: Path, revision: str, manifest: JsonObject
) -> None:
    path = manifest["tdd_path"]
    location = "/tdd_path"
    if not _committed_regular_file(revision, path) or not _current_regular_file(root, path):
        diagnostics.append(_diagnostic("tdd_violation", location, "tracked_regular_file"))
        return
    if not _matches_digest(revision, path, root / path, manifest["tdd_sha256"]):
        diagnostics.append(_diagnostic("tdd_violation", "/tdd_sha256", "digest_match"))


def _lock_protected_artifacts(
    diagnostics: list[PreflightDiagnostic], root: Path, revision: str, manifest: JsonObject
) -> None:
    for index, artifact in enumerate(manifest["protected_artifacts"]):
        path = artifact["path"]
        if not _committed_regular_file(revision, path) or not _current_regular_file(root, path):
            diagnostics.append(
                _diagnostic(
                    "protected_artifact_violation",
                    f"/protected_artifacts/{index}/path",
                    "tracked_regular_file",
                )
            )
        elif not _matches_digest(revision, path, root / path, artifact["sha256"]):
            diagnostics.append(
                _diagnostic(
                    "protected_artifact_violation",
                    f"/protected_artifacts/{index}/sha256",
                    "digest_match",
                )
            )


def _check_reference_paths(
    diagnostics: list[PreflightDiagnostic], root: Path, revision: str, manifest: JsonObject
) -> None:
    for index, reference in enumerate(manifest["reference_paths"]):
        valid = (
            _committed_nonempty_directory(revision, reference)
            and _current_directory(root, reference)
            if reference.endswith("/")
            else (
                _committed_regular_file(revision, reference)
                and _current_regular_file(root, reference)
            )
        )
        if not valid:
            diagnostics.append(
                _diagnostic(
                    "reference_violation",
                    f"/reference_paths/{index}",
                    "tracked_file_or_nonempty_directory",
                )
            )


def _check_allowed_paths(
    diagnostics: list[PreflightDiagnostic], root: Path, manifest_path: str, manifest: JsonObject
) -> None:
    protected_paths = {manifest_path, manifest["tdd_path"]}
    protected_paths.update(artifact["path"] for artifact in manifest["protected_artifacts"])
    for index, allowed_path in enumerate(manifest["allowed_paths"]):
        if allowed_path in protected_paths or (
            allowed_path.endswith("/")
            and any(path.startswith(allowed_path) for path in protected_paths)
        ):
            diagnostics.append(
                _diagnostic("scope_violation", f"/allowed_paths/{index}", "protected_overlap")
            )
        if _has_symlink_component(root, allowed_path):
            diagnostics.append(
                _diagnostic("scope_violation", f"/allowed_paths/{index}", "symlink_ancestor")
            )


def _check_dependency_receipts(
    diagnostics: list[PreflightDiagnostic], revision: str, manifest: JsonObject
) -> None:
    receipts = _committed_receipts(revision)
    for index, dependency in enumerate(manifest["depends_on"]):
        matches = [receipt for receipt in receipts if receipt.get("task_id") == dependency]
        if len(matches) > 1:
            rule = "unique_leaf_verified_receipt"
        elif len(matches) != 1 or matches[0].get("result") != "leaf_verified":
            rule = "leaf_verified_receipt"
        else:
            continue
        diagnostics.append(_diagnostic("dependency_violation", f"/depends_on/{index}", rule))


def _execution_base(manifest_path: str) -> str | None:
    result = _git("log", "-n", "1", "--format=%H", "HEAD", "--", manifest_path)
    if result is None or result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value if value else None


def _commit_revision(revision: str) -> str | None:
    return _git_stdout("rev-parse", "--verify", f"{revision}^{{commit}}")


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    result = _git("merge-base", "--is-ancestor", ancestor, descendant)
    return result is not None and result.returncode == 0


def _worktree_is_dirty() -> bool:
    result = _git("status", "--porcelain=v1", "--untracked-files=all")
    return result is not None and bool(result.stdout)


def _repository_root() -> Path | None:
    path = _git_stdout("rev-parse", "--show-toplevel")
    return Path(path) if path is not None else None


def _is_current_directory(root: Path) -> bool:
    try:
        return os.path.samefile(Path.cwd(), root)
    except OSError:
        return False


def _git_stdout(*arguments: str) -> str | None:
    result = _git(*arguments)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _git(*arguments: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(["git", *arguments], text=True, capture_output=True, check=False)
    except OSError:
        return None


def _git_bytes(*arguments: str) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(["git", *arguments], capture_output=True, check=False)
    except OSError:
        return None


def _tree_entry(revision: str, path: str) -> tuple[str, str] | None:
    result = _git("ls-tree", "-z", revision, "--", path)
    if result is None or result.returncode != 0 or not result.stdout:
        return None
    record = result.stdout.split("\0", maxsplit=1)[0]
    try:
        metadata, _ = record.split("\t", maxsplit=1)
        mode, kind, object_id = metadata.split(" ", maxsplit=2)
    except ValueError:
        return None
    return (mode, object_id) if kind == "blob" else None


def _committed_regular_file(revision: str, path: str) -> bool:
    entry = _tree_entry(revision, path)
    return entry is not None and entry[0] in _REGULAR_GIT_MODES


def _committed_nonempty_directory(revision: str, path: str) -> bool:
    result = _git("ls-tree", "-r", "-z", revision, "--", path)
    if result is None or result.returncode != 0:
        return False
    return any(
        entry[0] in _REGULAR_GIT_MODES
        for entry in _tree_entries(result.stdout)
        if entry[2].startswith(path)
    )


def _tree_entries(output: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for record in output.split("\0"):
        if not record:
            continue
        try:
            metadata, path = record.split("\t", maxsplit=1)
            mode, kind, object_id = metadata.split(" ", maxsplit=2)
        except ValueError:
            continue
        entries.append((mode, kind, path if object_id else ""))
    return entries


def _current_regular_file(root: Path, path: str) -> bool:
    if _has_symlink_component(root, path):
        return False
    try:
        return stat.S_ISREG((root / path).lstat().st_mode)
    except OSError:
        return False


def _current_directory(root: Path, path: str) -> bool:
    if _has_symlink_component(root, path):
        return False
    try:
        return stat.S_ISDIR((root / path.rstrip("/")).lstat().st_mode)
    except OSError:
        return False


def _has_symlink_component(root: Path, path: str) -> bool:
    current = root
    for part in path.rstrip("/").split("/"):
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return False
        except OSError:
            return False
        if stat.S_ISLNK(mode):
            return True
    return False


def _matches_digest(revision: str, path: str, current: Path, expected: str) -> bool:
    entry = _tree_entry(revision, path)
    if entry is None:
        return False
    committed = _git_bytes("cat-file", "blob", entry[1])
    if committed is None or committed.returncode != 0:
        return False
    current_digest = _file_digest(current)
    return hashlib.sha256(committed.stdout).hexdigest() == expected and current_digest == expected


def _file_digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _committed_receipts(revision: str) -> list[JsonObject]:
    result = _git("ls-tree", "-r", "-z", revision, "--", ".agent/receipts")
    if result is None or result.returncode != 0:
        return []
    receipts: list[JsonObject] = []
    for mode, kind, path in _tree_entries(result.stdout):
        if mode not in _REGULAR_GIT_MODES or kind != "blob" or not path.endswith(".json"):
            continue
        entry = _tree_entry(revision, path)
        if entry is None:
            continue
        content = _git_bytes("cat-file", "blob", entry[1])
        if content is None or content.returncode != 0:
            continue
        try:
            parsed: object = json.loads(content.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(parsed, dict):
            receipts.append(cast(JsonObject, parsed))
    return receipts


def _diagnostic(kind: str, location: str, rule: str) -> PreflightDiagnostic:
    return PreflightDiagnostic(f"task_preflight.{kind}", location, rule)


def _sorted(diagnostics: list[PreflightDiagnostic]) -> tuple[PreflightDiagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.location, item.code, item.rule)))
