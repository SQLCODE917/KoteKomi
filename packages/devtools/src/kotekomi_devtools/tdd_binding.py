"""Canonical binding of local Technical Design Documents to Harness tasks."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from kotekomi_devtools.receipt_writer import write_receipt

_SHA = re.compile(r"^[0-9a-f]{64}$")
_HEADING = re.compile(r"^\s{0,3}#+\s+(.+?)\s*#*\s*$")


class TddBindingError(ValueError):
    """Raised for invalid canonical TDD binding state."""


def _json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _write(path: Path, value: object, *, overwrite: bool = True) -> None:
    if path.exists() and not overwrite:
        raise TddBindingError(f"immutable record already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json(value))


def _root(value: Path | None) -> Path:
    return (value or Path("~/.local/state/kotekomi")).expanduser().resolve()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "tdd"


def derive_task_id(title: str, digest: str) -> str:
    if not _SHA.fullmatch(digest):
        raise TddBindingError("TDD digest must be lowercase SHA-256")
    return f"{slugify(title)}-{digest[:12]}"


def _heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        found = _HEADING.match(line)
        if found and found.group(1).strip():
            return found.group(1).strip()
    return fallback


def _paths(root: Path, task_id: str) -> tuple[Path, Path, Path, Path]:
    spec = root / "experiments" / task_id / "spec"
    return (
        spec / "tdd-binding.json",
        spec / "tdd-snapshot.md",
        spec / "tdd-binding-revisions",
        spec / "receipts",
    )


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TddBindingError(f"invalid JSON record: {path}") from error
    if not isinstance(payload, dict):
        raise TddBindingError(f"invalid JSON record: {path}")
    return cast(dict[str, object], payload)


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise TddBindingError(f"binding field must be a string list: {field}")
    items = cast(list[object], value)
    strings: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise TddBindingError(f"binding field must be a string list: {field}")
        strings.append(item)
    return strings


def _integer(value: object, *, field: str) -> int:
    if not isinstance(value, int):
        raise TddBindingError(f"binding field must be an integer: {field}")
    return value


def _bindings(root: Path) -> list[tuple[Path, dict[str, object]]]:
    result: list[tuple[Path, dict[str, object]]] = []
    for path in (
        sorted((root / "experiments").glob("*/spec/tdd-binding.json"))
        if (root / "experiments").exists()
        else []
    ):
        record = _read_json(path)
        if record.get("status") != "ready" or not isinstance(record.get("task_id"), str):
            raise TddBindingError(f"invalid canonical binding: {path}")
        snapshot = Path(str(record.get("tdd_snapshot_path", "")))
        if not snapshot.is_file() or hashlib.sha256(
            snapshot.read_bytes()
        ).hexdigest() != record.get("tdd_sha256"):
            raise TddBindingError(f"binding snapshot mismatch: {path}")
        result.append((path, record))
    return result


def _index(root: Path, bindings: list[tuple[Path, dict[str, object]]]) -> dict[str, object]:
    by_path: dict[str, str] = {}
    by_digest: dict[str, str] = {}
    by_task: dict[str, str] = {}
    for path, binding in bindings:
        task_id = str(binding["task_id"])
        digest = str(binding["tdd_sha256"])
        if digest in by_digest and by_digest[digest] != task_id:
            raise TddBindingError("one TDD digest must have one task identifier")
        for alias in _string_list(binding.get("tdd_paths"), field="tdd_paths"):
            if alias in by_path and by_path[alias] != task_id:
                raise TddBindingError("one TDD path must have one task identifier")
            by_path[alias] = task_id
        by_digest[digest] = task_id
        by_task[task_id] = str(path)
    return {
        "schema_version": 1,
        "by_tdd_path": dict(sorted(by_path.items())),
        "by_tdd_sha256": dict(sorted(by_digest.items())),
        "by_task_id": dict(sorted(by_task.items())),
        "diagnostics": [],
    }


def rebuild_tdd_index(state_root: Path) -> dict[str, object]:
    root = _root(state_root)
    result = _index(root, _bindings(root))
    _write(root / "tdds" / "index.json", result)
    return result


def lookup_tdd_binding(
    state_root: Path, *, tdd_path: str | None = None, task_id: str | None = None
) -> dict[str, object] | None:
    if (tdd_path is None) == (task_id is None):
        raise TddBindingError("lookup requires exactly one TDD path or task identifier")
    root = _root(state_root)
    bindings = _bindings(root)
    expected = _index(root, bindings)
    index_path = root / "tdds" / "index.json"
    try:
        if _read_json(index_path) != expected:
            _write(index_path, expected)
    except TddBindingError:
        _write(index_path, expected)
    selected = tdd_path if tdd_path is not None else None
    for _, binding in bindings:
        if selected is not None and selected in _string_list(
            binding.get("tdd_paths"), field="tdd_paths"
        ):
            return binding
        if task_id is not None and binding.get("task_id") == task_id:
            return binding
    return None


def list_tdd_bindings(state_root: Path) -> list[dict[str, object]]:
    """Return all validated canonical bindings in deterministic task order."""
    root = _root(state_root)
    bindings = _bindings(root)
    expected = _index(root, bindings)
    _write(root / "tdds" / "index.json", expected)
    return [binding for _, binding in bindings]


@dataclass(frozen=True)
class TddBindingResult:
    status: str
    requested_tdd_path: str | None
    binding: dict[str, object] | None
    diagnostics: tuple[dict[str, str], ...] = ()

    @property
    def exit_code(self) -> int:
        return 0 if self.status == "ready" else 1

    def as_json(self) -> dict[str, object]:
        binding = self.binding or {}
        return {
            "schema_version": 1,
            "status": self.status,
            "requested_tdd_path": self.requested_tdd_path,
            "task_id": binding.get("task_id"),
            "primary_tdd_path": binding.get("primary_tdd_path"),
            "tdd_paths": binding.get("tdd_paths", []),
            "tdd_snapshot_path": binding.get("tdd_snapshot_path"),
            "tdd_sha256": binding.get("tdd_sha256"),
            "tdd_title": binding.get("tdd_title"),
            "canonical_binding_path": binding.get("canonical_binding_path"),
            "latest_binding_revision": binding.get("latest_binding_revision"),
            "latest_binding_revision_path": binding.get("latest_binding_revision_path"),
            "latest_binding_receipt_path": binding.get("latest_binding_receipt_path"),
            "diagnostics": list(self.diagnostics),
        }


def bind_tdd(
    tdd_path: Path | str,
    *,
    output: Path | None = None,
    cwd: Path | None = None,
    state_root: Path | None = None,
) -> TddBindingResult:
    base = (cwd or Path.cwd()).resolve()
    supplied = str(tdd_path)
    if urlsplit(supplied).scheme or supplied.startswith("//"):
        return TddBindingResult(
            "blocked",
            None,
            None,
            (
                {
                    "code": "tdd_path.network_source",
                    "location": "/tdd_path",
                    "rule": "local_file_only",
                },
            ),
        )
    candidate = Path(tdd_path)
    resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
    try:
        requested = resolved.relative_to(base).as_posix()
        content = resolved.read_bytes()
        text = content.decode("utf-8")
    except (ValueError, OSError, UnicodeDecodeError):
        return TddBindingResult(
            "blocked",
            None,
            None,
            (
                {
                    "code": "tdd_path.unreadable",
                    "location": "/tdd_path",
                    "rule": "readable_utf8_repository_file",
                },
            ),
        )
    if resolved.suffix.lower() != ".md":
        return TddBindingResult(
            "blocked",
            requested,
            None,
            (
                {
                    "code": "tdd_path.markdown_required",
                    "location": "/tdd_path",
                    "rule": "markdown_file",
                },
            ),
        )
    root = _root(state_root)
    digest = hashlib.sha256(content).hexdigest()
    title = _heading(text, resolved.stem)
    try:
        known = lookup_tdd_binding(root, tdd_path=requested)
        if known is not None and known.get("tdd_sha256") != digest:
            return TddBindingResult(
                "blocked",
                requested,
                known,
                (
                    {
                        "code": "tdd_binding.digest_conflict",
                        "location": "/tdd_sha256",
                        "rule": "path_digest_is_immutable",
                    },
                ),
            )
        by_digest = next(
            (item for _, item in _bindings(root) if item.get("tdd_sha256") == digest), None
        )
        binding: dict[str, object] | None = by_digest or known
        if binding is None:
            task_id = derive_task_id(title, digest)
            collision = lookup_tdd_binding(root, task_id=task_id)
            if collision is not None:
                return TddBindingResult(
                    "blocked",
                    requested,
                    collision,
                    (
                        {
                            "code": "tdd_binding.task_id_collision",
                            "location": "/task_id",
                            "rule": "unique_task_identifier",
                        },
                    ),
                )
            binding_path, snapshot, revisions, receipts = _paths(root, task_id)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(content)
            aliases = [requested]
            revision = 1
            binding = {
                "schema_version": 1,
                "task_id": task_id,
                "primary_tdd_path": requested,
                "tdd_paths": aliases,
                "tdd_snapshot_path": str(snapshot),
                "tdd_sha256": digest,
                "tdd_title": title,
                "canonical_binding_path": str(binding_path),
                "latest_binding_revision": revision,
                "latest_binding_revision_path": str(revisions / "tdd-binding-001.json"),
                "latest_binding_receipt_path": str(receipts / "tdd-binding-001.receipt.json"),
                "status": "ready",
                "diagnostics": [],
            }
        else:
            binding = dict(binding)
            existing_aliases = _string_list(binding["tdd_paths"], field="tdd_paths")
            aliases = sorted({*existing_aliases, requested})
            if aliases != existing_aliases:
                binding["tdd_paths"] = aliases
                binding["latest_binding_revision"] = (
                    _integer(binding["latest_binding_revision"], field="latest_binding_revision")
                    + 1
                )
                revision = _integer(
                    binding["latest_binding_revision"], field="latest_binding_revision"
                )
                _, _, revisions, receipts = _paths(root, str(binding["task_id"]))
                binding["latest_binding_revision_path"] = str(
                    revisions / f"tdd-binding-{revision:03d}.json"
                )
                binding["latest_binding_receipt_path"] = str(
                    receipts / f"tdd-binding-{revision:03d}.receipt.json"
                )
            else:
                revision = _integer(
                    binding["latest_binding_revision"], field="latest_binding_revision"
                )
        revision_path = Path(str(binding["latest_binding_revision_path"]))
        receipt_path = Path(str(binding["latest_binding_receipt_path"]))
        if not revision_path.exists():
            _write(revision_path, binding, overwrite=False)
            write_receipt(
                task_id=str(binding["task_id"]),
                record_kind="tdd-binding",
                result="tdd_binding_ready",
                output=receipt_path,
                artifacts=[f"binding={revision_path}"],
                fields=[f"tdd_sha256={digest}", f"binding_revision={revision}"],
            )
        _write(Path(str(binding["canonical_binding_path"])), binding)
        rebuild_tdd_index(root)
        result = TddBindingResult("ready", requested, binding)
        if output is not None:
            _write((output if output.is_absolute() else base / output).resolve(), result.as_json())
        return result
    except (OSError, TddBindingError, ValueError) as error:
        return TddBindingResult(
            "blocked",
            requested,
            None,
            ({"code": "tdd_binding.store_error", "location": "/", "rule": str(error)},),
        )
