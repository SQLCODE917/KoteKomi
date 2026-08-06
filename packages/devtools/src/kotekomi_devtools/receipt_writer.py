"""Deterministic writer for agent task lifecycle receipts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class ReceiptWriterError(ValueError):
    """Raised when receipt inputs do not meet the writer contract."""


@dataclass(frozen=True)
class ReceiptWriteResult:
    """The path and digest of a receipt written by ``write_receipt``."""

    receipt_path: str
    receipt_sha256: str

    def as_json(self) -> dict[str, str]:
        """Serialize the public command result."""
        return {
            "receipt_path": self.receipt_path,
            "receipt_sha256": self.receipt_sha256,
        }


def write_receipt(
    *,
    task_id: str,
    record_kind: str,
    result: str,
    output: Path,
    input_records: Sequence[str] = (),
    artifacts: Sequence[str] = (),
    fields: Sequence[str] = (),
    force: bool = False,
) -> ReceiptWriteResult:
    """Validate receipt inputs and write one canonical JSON receipt."""
    if output.exists() and not force:
        raise ReceiptWriterError(f"receipt output already exists: {output}")

    receipt_input_records = _parse_file_entries("input record", input_records)
    receipt_artifacts = _parse_file_entries("artifact", artifacts)
    receipt_fields = _parse_fields(fields)
    receipt = {
        "schema_version": 1,
        "task_id": task_id,
        "record_kind": record_kind,
        "result": result,
        "created_at": datetime.now(UTC).isoformat(),
        "git": _git_state(),
        "input_records": receipt_input_records,
        "artifacts": receipt_artifacts,
        "fields": receipt_fields,
    }
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    return ReceiptWriteResult(str(output), _sha256_bytes(serialized.encode("utf-8")))


def _parse_file_entries(kind: str, entries: Sequence[str]) -> dict[str, dict[str, str]]:
    parsed: dict[str, dict[str, str]] = {}
    for entry in entries:
        name, supplied_path = _split_entry(kind, entry)
        if name in parsed:
            raise ReceiptWriterError(f"duplicate {kind} name: {name}")
        path = Path(supplied_path)
        if not path.is_file():
            raise ReceiptWriterError(
                f"{kind} path does not exist or is not a file: {supplied_path}"
            )
        parsed[name] = {"path": supplied_path, "sha256": _sha256_file(path)}
    return parsed


def _parse_fields(entries: Sequence[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for entry in entries:
        key, value = _split_entry("field", entry)
        if key in parsed:
            raise ReceiptWriterError(f"duplicate field key: {key}")
        parsed[key] = value
    return parsed


def _split_entry(kind: str, entry: str) -> tuple[str, str]:
    name, separator, value = entry.partition("=")
    if not separator or not name or (kind != "field" and not value):
        raise ReceiptWriterError(f"invalid {kind} entry: {entry}")
    return name, value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_state() -> dict[str, object]:
    inside_worktree = _git("rev-parse", "--is-inside-work-tree")
    if inside_worktree is None or inside_worktree.returncode != 0:
        return {
            "worktree_detected": False,
            "branch": None,
            "head": None,
            "parents": [],
            "worktree_clean": None,
        }
    if inside_worktree.stdout.strip() != "true":
        return {
            "worktree_detected": False,
            "branch": None,
            "head": None,
            "parents": [],
            "worktree_clean": None,
        }

    branch = _git("symbolic-ref", "--short", "-q", "HEAD")
    head = _git("rev-parse", "HEAD")
    parents = _git("show", "-s", "--format=%P", "HEAD")
    status = _git("status", "--porcelain")
    return {
        "worktree_detected": True,
        "branch": (
            branch.stdout.strip() if branch is not None and branch.returncode == 0 else "HEAD"
        ),
        "head": head.stdout.strip() if head is not None and head.returncode == 0 else "",
        "parents": (
            parents.stdout.split() if parents is not None and parents.returncode == 0 else []
        ),
        "worktree_clean": status is not None and status.returncode == 0 and not status.stdout,
    }


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
