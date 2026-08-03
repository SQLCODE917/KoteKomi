"""Read-only Git diff budget auditing for Task Manifests."""

from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from kotekomi_devtools.task_manifest import Diagnostic, validate_task_manifest

type JsonObject = dict[str, object]
type PathCategory = Literal["production", "test", "other"]


@dataclass(frozen=True)
class BudgetDiagnostic:
    """One stable Task Budget Audit diagnostic."""

    code: str
    location: str
    rule: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "rule": self.rule}


@dataclass(frozen=True)
class PathStat:
    """The classified line counts for one changed path."""

    path: str
    category: PathCategory
    added: int
    deleted: int

    def as_json(self) -> dict[str, str | int]:
        return {
            "path": self.path,
            "category": self.category,
            "added": self.added,
            "deleted": self.deleted,
            "diff_lines": self.added + self.deleted,
        }


@dataclass(frozen=True)
class TaskBudgetResult:
    """The public result of auditing one Task Manifest candidate."""

    schema_version: int | None
    task_id: str | None
    mode: Literal["revision", "worktree"]
    base_revision: str | None
    head_revision: str | None
    budget: dict[str, int] | None
    totals: dict[str, int] | None
    path_stats: tuple[PathStat, ...]
    diagnostics: tuple[BudgetDiagnostic | Diagnostic, ...]

    @property
    def status(self) -> Literal["within_budget", "over_budget", "invalid"]:
        if any(diagnostic.code.startswith("task_manifest.") for diagnostic in self.diagnostics):
            return "invalid"
        return "over_budget" if self.diagnostics else "within_budget"

    @property
    def exit_code(self) -> int:
        return {"within_budget": 0, "over_budget": 1, "invalid": 2}[self.status]

    def as_json(self) -> JsonObject:
        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "mode": self.mode,
            "base_revision": self.base_revision,
            "head_revision": self.head_revision,
            "budget": self.budget,
            "totals": self.totals,
            "path_stats": [path_stat.as_json() for path_stat in self.path_stats],
            "diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics],
        }


def audit_task_budget(
    manifest_path: Path,
    *,
    base_revision: str,
    head_revision: str | None,
    worktree: bool,
) -> TaskBudgetResult:
    """Validate a Task Manifest and audit its candidate diff without writing Git state."""
    mode: Literal["revision", "worktree"] = "worktree" if worktree else "revision"
    validation = validate_task_manifest(manifest_path)
    if not validation.valid:
        return TaskBudgetResult(
            validation.schema_version,
            validation.task_id,
            mode,
            None,
            None,
            None,
            None,
            (),
            validation.diagnostics,
        )

    manifest = _load_manifest(manifest_path)
    budget = _budget(manifest)
    base = _resolve_commit(base_revision)
    head = "WORKTREE" if worktree else _resolve_commit(cast(str, head_revision))
    stats = _path_stats(base, head_revision if not worktree else None, worktree)
    totals = _totals(stats)
    diagnostics = _diagnostics(stats, manifest, budget, totals)
    return TaskBudgetResult(
        validation.schema_version,
        validation.task_id,
        mode,
        base,
        head,
        budget,
        totals,
        stats,
        diagnostics,
    )


def _load_manifest(path: Path) -> JsonObject:
    return cast(JsonObject, tomllib.loads(path.read_text(encoding="utf-8")))


def _budget(manifest: JsonObject) -> dict[str, int]:
    value = cast(dict[str, object], manifest["budget"])
    return {
        "maximum_production_files": cast(int, value["maximum_production_files"]),
        "maximum_test_files": cast(int, value["maximum_test_files"]),
        "maximum_production_diff_lines": cast(int, value["maximum_production_diff_lines"]),
    }


def _resolve_commit(revision: str) -> str:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    if result.returncode != 0:
        raise RuntimeError(f"unable to resolve commit: {revision}")
    return result.stdout.decode("ascii").strip()


def _path_stats(
    base_revision: str,
    head_revision: str | None,
    worktree: bool,
) -> tuple[PathStat, ...]:
    arguments = ["diff", "--numstat", "--no-renames", "-z", base_revision]
    if not worktree:
        arguments.append(cast(str, head_revision))
    tracked = _git(*arguments)
    if tracked.returncode != 0:
        raise RuntimeError("unable to inspect Git diff")

    stats = _parse_numstat(tracked.stdout)
    if worktree:
        for path in _untracked_paths():
            stats[path] = ( _untracked_lines(path), 0)
    return tuple(
        PathStat(path, _classify(path), added, deleted)
        for path, (added, deleted) in sorted(stats.items())
    )


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", *arguments], capture_output=True, check=False
        )
    except OSError as error:
        raise RuntimeError("unable to run git") from error


def _parse_numstat(output: bytes) -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        added, deleted, path = record.split(b"\t", maxsplit=2)
        stats[path.decode("utf-8")] = (_numstat_count(added), _numstat_count(deleted))
    return stats


def _numstat_count(value: bytes) -> int:
    return int(value) if value != b"-" else 0


def _untracked_paths() -> tuple[str, ...]:
    result = _git("ls-files", "--others", "--exclude-standard", "-z")
    if result.returncode != 0:
        raise RuntimeError("unable to inspect untracked files")
    return tuple(path.decode("utf-8") for path in result.stdout.split(b"\0") if path)


def _untracked_lines(path: str) -> int:
    file_path = Path(path)
    data = os.fsencode(os.readlink(file_path)) if file_path.is_symlink() else file_path.read_bytes()
    return data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))


def _classify(path: str) -> PathCategory:
    if path.startswith("packages/devtools/src/"):
        return "production"
    if path.startswith("packages/devtools/tests/"):
        return "test"
    return "other"


def _totals(stats: tuple[PathStat, ...]) -> dict[str, int]:
    return {
        "production_files": sum(stat.category == "production" for stat in stats),
        "test_files": sum(stat.category == "test" for stat in stats),
        "production_diff_lines": sum(
            stat.added + stat.deleted for stat in stats if stat.category == "production"
        ),
    }


def _diagnostics(
    stats: tuple[PathStat, ...],
    manifest: JsonObject,
    budget: dict[str, int],
    totals: dict[str, int],
) -> tuple[BudgetDiagnostic, ...]:
    diagnostics: list[BudgetDiagnostic] = []
    for name in (
        "maximum_production_files",
        "maximum_test_files",
        "maximum_production_diff_lines",
    ):
        rule = name.removeprefix("maximum_")
        if totals[rule] > budget[name]:
            diagnostics.append(
                BudgetDiagnostic("task_budget.budget_violation", f"/budget/{name}", rule)
            )

    allowed_paths = cast(list[str], manifest["allowed_paths"])
    for index, stat in enumerate(stats):
        if not any(_allows(allowed_path, stat.path) for allowed_path in allowed_paths):
            diagnostics.append(
                BudgetDiagnostic(
                    "task_budget.scope_violation", f"/path_stats/{index}/path", "allowed_path"
                )
            )
    return tuple(sorted(diagnostics, key=lambda item: (item.location, item.code, item.rule)))


def _allows(allowed_path: str, changed_path: str) -> bool:
    return allowed_path == changed_path or (
        allowed_path.endswith("/") and changed_path.startswith(allowed_path)
    )
