"""Canonical TDD bindings and their derived local index."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlsplit

from kotekomi_devtools.receipt_writer import ReceiptWriterError, write_receipt

type JsonObject = dict[str, object]
type BindingStatus = Literal["ready", "blocked"]

_DEFAULT_STATE_ROOT = Path("~/.local/state/kotekomi/experiments")
_INDEX_NAME = "tdd-index.json"
_BINDING_NAME = "tdd-binding.json"
_SNAPSHOT_NAME = "tdd-snapshot.md"
_DIGEST_SUFFIX_LENGTH = 12
_ATX_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$")
_SETEXT_UNDERLINE = re.compile(r"^[ \t]*(?:=+|-+)[ \t]*$")
_SLUG_SEPARATOR = re.compile(r"[^a-z0-9]+")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TASK_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{12}$")
_BINDING_KEYS = frozenset(
    {
        "schema_version",
        "task_id",
        "tdd_path",
        "tdd_snapshot_path",
        "tdd_sha256",
        "tdd_title",
        "status",
        "diagnostics",
    }
)
_INDEX_KEYS = frozenset(
    {"schema_version", "by_tdd_path", "by_tdd_sha256", "by_task_id", "diagnostics"}
)


class TddBindingError(ValueError):
    """Raised when canonical TDD binding state is invalid or unreadable."""


class _StoreError(TddBindingError):
    """A store failure that can be represented in a binding result."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.rule)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class Diagnostic:
    """One stable TDD binding diagnostic."""

    code: str
    location: str
    rule: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "rule": self.rule}


@dataclass(frozen=True)
class TddBinding:
    """One canonical binding between a TDD snapshot and a task identifier."""

    task_id: str
    tdd_path: str
    tdd_snapshot_path: str
    tdd_sha256: str
    tdd_title: str
    status: Literal["ready"]
    diagnostics: tuple[Diagnostic, ...] = ()

    def as_json(self) -> JsonObject:
        return {
            "schema_version": 1,
            "task_id": self.task_id,
            "tdd_path": self.tdd_path,
            "tdd_snapshot_path": self.tdd_snapshot_path,
            "tdd_sha256": self.tdd_sha256,
            "tdd_title": self.tdd_title,
            "status": self.status,
            "diagnostics": [item.as_json() for item in self.diagnostics],
        }


@dataclass(frozen=True)
class TddIndex:
    """Derived lookup state for canonical TDD bindings."""

    by_tdd_path: dict[str, str]
    by_tdd_sha256: dict[str, tuple[str, ...]]
    by_task_id: dict[str, str]
    diagnostics: tuple[Diagnostic, ...] = ()

    def as_json(self) -> JsonObject:
        return {
            "schema_version": 1,
            "by_tdd_path": dict(sorted(self.by_tdd_path.items())),
            "by_tdd_sha256": {
                digest: list(task_ids) for digest, task_ids in sorted(self.by_tdd_sha256.items())
            },
            "by_task_id": dict(sorted(self.by_task_id.items())),
            "diagnostics": [item.as_json() for item in self.diagnostics],
        }


@dataclass(frozen=True)
class TddBindingResult:
    """Public result returned by the binding command."""

    status: BindingStatus
    task_id: str | None
    tdd_path: str | None
    tdd_snapshot_path: str | None
    tdd_sha256: str | None
    tdd_title: str | None
    canonical_binding_path: str | None
    tdd_index_path: str
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def exit_code(self) -> int:
        return 0 if self.status == "ready" else 1

    def as_json(self) -> JsonObject:
        return {
            "schema_version": 1,
            "status": self.status,
            "task_id": self.task_id,
            "tdd_path": self.tdd_path,
            "tdd_snapshot_path": self.tdd_snapshot_path,
            "tdd_sha256": self.tdd_sha256,
            "tdd_title": self.tdd_title,
            "canonical_binding_path": self.canonical_binding_path,
            "tdd_index_path": self.tdd_index_path,
            "diagnostics": [item.as_json() for item in self.diagnostics],
        }


@dataclass(frozen=True)
class _TddInput:
    path: str
    content: bytes
    digest: str
    title: str
    task_id: str


def bind_tdd(
    tdd_path: Path | str,
    *,
    output: Path,
    receipt: Path,
    cwd: Path | None = None,
    state_root: Path | None = None,
) -> TddBindingResult:
    """Create or read one canonical binding and write a verified receipt.

    ``output`` is a caller-selected materialized copy.  Canonical state always
    lives under ``<state-root>/<task-id>/spec`` so arbitrary output paths cannot
    fragment index discovery.
    """
    base = (cwd or Path.cwd()).resolve()
    root = _state_root(state_root)
    index_path = root / _INDEX_NAME
    try:
        tdd = _read_tdd_input(tdd_path, cwd=base)
    except _TddInputError as error:
        return TddBindingResult(
            "blocked",
            None,
            error.tdd_path,
            None,
            None,
            None,
            None,
            str(index_path),
            (error.diagnostic,),
        )

    canonical_path, snapshot_path = _canonical_paths(root, tdd.task_id)
    output_path = _resolve_path(output, base)
    receipt_path = _resolve_path(receipt, base)
    try:
        bindings = _load_bindings(root)
        _build_index(bindings)
    except _StoreError as error:
        return _blocked_result(tdd, snapshot_path, index_path, error.diagnostic)

    same_path = [(path, binding) for path, binding in bindings if binding.tdd_path == tdd.path]
    if len(same_path) > 1:
        return _blocked_result(
            tdd,
            snapshot_path,
            index_path,
            Diagnostic(
                "tdd_binding.duplicate_path",
                "/tdd_path",
                "one repo-relative TDD path must have one canonical binding",
            ),
        )
    if same_path and same_path[0][1].tdd_sha256 != tdd.digest:
        return _blocked_result(
            tdd,
            snapshot_path,
            index_path,
            Diagnostic(
                "tdd_binding.digest_conflict",
                "/tdd_sha256",
                "TDD path is already bound to a different snapshot digest",
            ),
            canonical_binding_path=str(same_path[0][0]),
        )

    if same_path:
        canonical_path, binding = same_path[0]
    else:
        collision = [(path, item) for path, item in bindings if item.task_id == tdd.task_id]
        if collision:
            return _blocked_result(
                tdd,
                snapshot_path,
                index_path,
                Diagnostic(
                    "tdd_binding.task_id_collision",
                    "/task_id",
                    "derived task identifier already identifies a different binding",
                ),
                canonical_binding_path=str(collision[0][0]),
            )
        binding = TddBinding(
            task_id=tdd.task_id,
            tdd_path=tdd.path,
            tdd_snapshot_path=str(snapshot_path),
            tdd_sha256=tdd.digest,
            tdd_title=tdd.title,
            status="ready",
        )

    try:
        _validate_destinations(
            output_path=output_path,
            receipt_path=receipt_path,
            canonical_path=canonical_path,
            snapshot_path=snapshot_path,
            index_path=index_path,
            binding=binding,
        )
    except _StoreError as error:
        return _blocked_result(
            tdd,
            snapshot_path,
            index_path,
            error.diagnostic,
            canonical_binding_path=str(canonical_path) if canonical_path.exists() else None,
        )

    try:
        if not same_path:
            _write_snapshot(snapshot_path, tdd.content)
            _write_json(canonical_path, binding.as_json(), overwrite=False)
            bindings.append((canonical_path, binding))
        index = _build_index(bindings)
        _write_json(index_path, index.as_json(), overwrite=True)
        _write_json(output_path, binding.as_json(), overwrite=True)
        _write_binding_receipt(
            task_id=binding.task_id,
            binding_path=canonical_path,
            snapshot_path=snapshot_path,
            digest=binding.tdd_sha256,
            receipt=receipt_path,
        )
    except (OSError, ReceiptWriterError, TddBindingError) as error:
        return _blocked_result(
            tdd,
            snapshot_path,
            index_path,
            Diagnostic("tdd_binding.write_failed", "/", str(error)),
            canonical_binding_path=str(canonical_path) if canonical_path.exists() else None,
        )

    return TddBindingResult(
        "ready",
        binding.task_id,
        binding.tdd_path,
        binding.tdd_snapshot_path,
        binding.tdd_sha256,
        binding.tdd_title,
        str(canonical_path),
        str(index_path),
    )


def read_tdd_binding(path: Path) -> TddBinding:
    """Read a canonical record and prove that its snapshot still matches it."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TddBindingError(f"canonical TDD binding is unreadable: {path}") from error
    binding = _parse_binding(value, path)
    snapshot = Path(binding.tdd_snapshot_path)
    try:
        digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    except OSError as error:
        raise TddBindingError(f"TDD snapshot is unreadable: {snapshot}") from error
    if digest != binding.tdd_sha256:
        raise TddBindingError(f"TDD snapshot digest does not match canonical binding: {path}")
    return binding


def read_tdd_index(path: Path) -> TddIndex:
    """Read and validate one derived TDD index."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TddBindingError(f"TDD index is unreadable: {path}") from error
    return _parse_index(value, path)


def rebuild_tdd_index(store_root: Path, *, index: Path | None = None) -> TddIndex:
    """Rebuild and persist the derived index from canonical binding records."""
    root = _state_root(store_root)
    index_path = _resolve_path(index, root) if index is not None else root / _INDEX_NAME
    if index_path != root / _INDEX_NAME:
        raise TddBindingError("TDD index must use the canonical state-root location")
    bindings = _load_bindings(root)
    result = _build_index(bindings)
    _write_json(index_path, result.as_json(), overwrite=True)
    return result


def lookup_tdd_bindings(
    store_root: Path,
    *,
    tdd_path: str | None = None,
    tdd_sha256: str | None = None,
    task_id: str | None = None,
) -> tuple[TddBinding, ...]:
    """Look up bindings after rebuilding missing, unreadable, or stale state."""
    supplied = [tdd_path is not None, tdd_sha256 is not None, task_id is not None]
    if sum(supplied) != 1:
        raise TddBindingError("lookup requires exactly one TDD path, digest, or task ID")

    root = _state_root(store_root)
    index_path = root / _INDEX_NAME
    bindings = _load_bindings(root)
    expected = _build_index(bindings)
    try:
        current = read_tdd_index(index_path)
    except TddBindingError:
        current = None
    if current is None or current != expected:
        _write_json(index_path, expected.as_json(), overwrite=True)
        current = expected

    if tdd_path is not None:
        selected_ids = (current.by_tdd_path.get(tdd_path),)
    elif tdd_sha256 is not None:
        selected_ids = current.by_tdd_sha256.get(tdd_sha256, ())
    else:
        selected_ids = (task_id,)
    result: list[TddBinding] = []
    for selected_id in selected_ids:
        if selected_id is None:
            continue
        binding_path = current.by_task_id.get(selected_id)
        if binding_path is None:
            raise TddBindingError(f"TDD index points at a missing canonical binding: {selected_id}")
        result.append(read_tdd_binding(Path(binding_path)))
    return tuple(result)


class _TddInputError(ValueError):
    def __init__(self, tdd_path: str | None, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.rule)
        self.tdd_path = tdd_path
        self.diagnostic = diagnostic


def _read_tdd_input(value: Path | str, *, cwd: Path) -> _TddInput:
    supplied = str(value)
    if _is_network_source(supplied):
        raise _TddInputError(
            None,
            Diagnostic("tdd_path.network_source", "/tdd_path", "local_file_only"),
        )
    candidate = Path(value)
    resolved = (candidate if candidate.is_absolute() else cwd / candidate).resolve()
    try:
        relative = resolved.relative_to(cwd)
    except ValueError as error:
        raise _TddInputError(
            None,
            Diagnostic("tdd_path.repository_relative", "/tdd_path", "repository_relative"),
        ) from error
    tdd_path = relative.as_posix()
    if resolved.suffix.lower() != ".md":
        raise _TddInputError(
            tdd_path,
            Diagnostic("tdd_path.markdown_required", "/tdd_path", "markdown_file"),
        )
    try:
        content = resolved.read_bytes()
        text = content.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise _TddInputError(
            tdd_path,
            Diagnostic("tdd_path.unreadable", "/tdd_path", "readable_utf8_local_file"),
        ) from error
    digest = hashlib.sha256(content).hexdigest()
    title = _first_heading(text) or resolved.stem
    return _TddInput(tdd_path, content, digest, title, derive_task_id(title, digest))


def derive_task_id(title_or_filename: str, tdd_sha256: str) -> str:
    """Create a stable slug plus short digest task identifier."""
    if not _SHA256.fullmatch(tdd_sha256):
        raise TddBindingError("TDD digest must be a lowercase SHA-256 hex value")
    return f"{slugify(title_or_filename)}-{tdd_sha256[:_DIGEST_SUFFIX_LENGTH]}"


def slugify(value: str) -> str:
    """Create the lowercase task identifier slug used by the Harness."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = _SLUG_SEPARATOR.sub("-", normalized.lower()).strip("-")
    return slug or "tdd"


def _first_heading(text: str) -> str | None:
    lines = text.splitlines()
    for number, line in enumerate(lines):
        match = _ATX_HEADING.match(line)
        if match and (title := match.group(1).strip()):
            return title
        if line.strip() and number + 1 < len(lines) and _SETEXT_UNDERLINE.match(lines[number + 1]):
            return line.strip()
    return None


def _is_network_source(value: str) -> bool:
    parsed = urlsplit(value)
    return bool(parsed.scheme or parsed.netloc or value.startswith("//"))


def _state_root(value: Path | None) -> Path:
    return (value or _DEFAULT_STATE_ROOT).expanduser().resolve()


def _resolve_path(value: Path, base: Path) -> Path:
    return (value if value.is_absolute() else base / value).resolve()


def _canonical_paths(root: Path, task_id: str) -> tuple[Path, Path]:
    evidence = root / task_id / "spec"
    return evidence / _BINDING_NAME, evidence / _SNAPSHOT_NAME


def _blocked_result(
    tdd: _TddInput,
    snapshot_path: Path,
    index_path: Path,
    diagnostic: Diagnostic,
    *,
    canonical_binding_path: str | None = None,
) -> TddBindingResult:
    return TddBindingResult(
        "blocked",
        tdd.task_id,
        tdd.path,
        str(snapshot_path),
        tdd.digest,
        tdd.title,
        canonical_binding_path,
        str(index_path),
        (diagnostic,),
    )


def _validate_destinations(
    *,
    output_path: Path,
    receipt_path: Path,
    canonical_path: Path,
    snapshot_path: Path,
    index_path: Path,
    binding: TddBinding,
) -> None:
    protected = {canonical_path, snapshot_path, index_path}
    if output_path == receipt_path or output_path in protected or receipt_path in protected:
        raise _StoreError(
            Diagnostic(
                "tdd_binding.destination_conflict",
                "/output",
                "output and receipt must not overwrite canonical TDD binding state",
            )
        )
    expected = _json_bytes(binding.as_json())
    if output_path.exists() and output_path.read_bytes() != expected:
        raise _StoreError(
            Diagnostic(
                "tdd_binding.output_conflict",
                "/output",
                "binding output already exists with different canonical content",
            )
        )
    if receipt_path.exists():
        _validate_receipt(receipt_path, binding, canonical_path, snapshot_path)


def _validate_receipt(
    path: Path,
    binding: TddBinding,
    canonical_path: Path,
    snapshot_path: Path,
) -> None:
    if not canonical_path.is_file() or not snapshot_path.is_file():
        raise _StoreError(
            Diagnostic(
                "tdd_binding.receipt_conflict",
                "/receipt",
                "an existing receipt cannot precede its canonical TDD binding",
            )
        )
    try:
        raw_payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _StoreError(
            Diagnostic("tdd_binding.receipt_conflict", "/receipt", "existing receipt is unreadable")
        ) from error
    if not isinstance(raw_payload, dict):
        raise _StoreError(
            Diagnostic("tdd_binding.receipt_conflict", "/receipt", "existing receipt is invalid")
        )
    payload = cast(JsonObject, raw_payload)
    fields = payload.get("fields")
    artifacts = payload.get("artifacts")
    if not isinstance(fields, dict) or not isinstance(artifacts, dict):
        raise _StoreError(
            Diagnostic(
                "tdd_binding.receipt_conflict",
                "/receipt",
                "existing receipt does not attest to this canonical TDD binding",
            )
        )
    receipt_fields = cast(JsonObject, fields)
    receipt_artifacts = cast(JsonObject, artifacts)
    expected_binding_digest = hashlib.sha256(_json_bytes(binding.as_json())).hexdigest()
    expected: bool = (
        payload.get("task_id") == binding.task_id
        and payload.get("record_kind") == "tdd-binding"
        and payload.get("result") == "tdd_binding_ready"
        and receipt_fields.get("tdd_sha256") == binding.tdd_sha256
        and receipt_fields.get("canonical_binding_path") == str(canonical_path)
        and _artifact_matches(
            receipt_artifacts.get("canonical_binding"), canonical_path, expected_binding_digest
        )
        and _artifact_matches(
            receipt_artifacts.get("tdd_snapshot"), snapshot_path, binding.tdd_sha256
        )
    )
    if not expected:
        raise _StoreError(
            Diagnostic(
                "tdd_binding.receipt_conflict",
                "/receipt",
                "existing receipt does not attest to this canonical TDD binding",
            )
        )


def _artifact_matches(value: object, path: Path, digest: str) -> bool:
    if not isinstance(value, dict):
        return False
    artifact = cast(JsonObject, value)
    return artifact.get("path") == str(path) and artifact.get("sha256") == digest


def _write_binding_receipt(
    *,
    task_id: str,
    binding_path: Path,
    snapshot_path: Path,
    digest: str,
    receipt: Path,
) -> None:
    if receipt.exists():
        return
    write_receipt(
        task_id=task_id,
        record_kind="tdd-binding",
        result="tdd_binding_ready",
        output=receipt,
        artifacts=[f"canonical_binding={binding_path}", f"tdd_snapshot={snapshot_path}"],
        fields=[f"tdd_sha256={digest}", f"canonical_binding_path={binding_path}"],
    )


def _load_bindings(store_root: Path) -> list[tuple[Path, TddBinding]]:
    bindings: list[tuple[Path, TddBinding]] = []
    if not store_root.exists():
        return bindings
    for path in sorted(store_root.glob(f"*/spec/{_BINDING_NAME}")):
        try:
            binding = read_tdd_binding(path)
            _validate_canonical_location(path.resolve(), binding, store_root)
            bindings.append((path.resolve(), binding))
        except TddBindingError as error:
            raise _StoreError(
                Diagnostic(
                    "tdd_binding.invalid_canonical_binding",
                    str(path),
                    str(error),
                )
            ) from error
    return bindings


def _validate_canonical_location(path: Path, binding: TddBinding, store_root: Path) -> None:
    expected_binding, expected_snapshot = _canonical_paths(store_root, binding.task_id)
    if path != expected_binding or Path(binding.tdd_snapshot_path) != expected_snapshot:
        raise TddBindingError(
            f"canonical TDD binding does not use its task evidence directory: {path}"
        )
    if binding.task_id != derive_task_id(binding.tdd_title, binding.tdd_sha256):
        raise TddBindingError(f"canonical TDD binding task identifier is inconsistent: {path}")


def _parse_binding(value: object, path: Path) -> TddBinding:
    if not isinstance(value, dict):
        raise TddBindingError(f"invalid canonical TDD binding: {path}")
    payload = cast(dict[str, object], value)
    if payload.keys() != _BINDING_KEYS or payload.get("schema_version") != 1:
        raise TddBindingError(f"invalid canonical TDD binding: {path}")
    task_id = payload.get("task_id")
    tdd_path = payload.get("tdd_path")
    snapshot = payload.get("tdd_snapshot_path")
    digest = payload.get("tdd_sha256")
    title = payload.get("tdd_title")
    diagnostics = payload.get("diagnostics")
    valid_strings = all(
        isinstance(item, str) for item in (task_id, tdd_path, snapshot, digest, title)
    )
    valid_path = isinstance(tdd_path, str) and _is_repo_relative(tdd_path)
    if (
        not valid_strings
        or not isinstance(task_id, str)
        or not _TASK_ID.fullmatch(task_id)
        or not valid_path
        or not isinstance(snapshot, str)
        or not Path(snapshot).is_absolute()
        or not isinstance(digest, str)
        or not _SHA256.fullmatch(digest)
        or not isinstance(title, str)
        or not title
        or payload.get("status") != "ready"
        or not isinstance(diagnostics, list)
        or diagnostics
    ):
        raise TddBindingError(f"invalid canonical TDD binding: {path}")
    return TddBinding(
        task_id,
        cast(str, tdd_path),
        snapshot,
        digest,
        title,
        "ready",
    )


def _is_repo_relative(value: str) -> bool:
    path = Path(value)
    return (
        not path.is_absolute()
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _build_index(bindings: list[tuple[Path, TddBinding]]) -> TddIndex:
    by_path: dict[str, str] = {}
    by_digest: dict[str, set[str]] = {}
    by_task: dict[str, str] = {}
    for path, binding in sorted(bindings, key=lambda item: str(item[0])):
        if binding.tdd_path in by_path:
            raise _StoreError(
                Diagnostic(
                    "tdd_index.duplicate_path",
                    "/by_tdd_path",
                    "canonical bindings contain duplicate TDD paths",
                )
            )
        if binding.task_id in by_task:
            raise _StoreError(
                Diagnostic(
                    "tdd_index.duplicate_task_id",
                    "/by_task_id",
                    "canonical bindings contain duplicate task identifiers",
                )
            )
        by_path[binding.tdd_path] = binding.task_id
        by_task[binding.task_id] = str(path)
        by_digest.setdefault(binding.tdd_sha256, set()).add(binding.task_id)
    return TddIndex(
        by_path,
        {digest: tuple(sorted(task_ids)) for digest, task_ids in by_digest.items()},
        by_task,
    )


def _parse_index(value: object, path: Path) -> TddIndex:
    if not isinstance(value, dict):
        raise TddBindingError(f"invalid TDD index: {path}")
    payload = cast(dict[str, object], value)
    if payload.keys() != _INDEX_KEYS or payload.get("schema_version") != 1:
        raise TddBindingError(f"invalid TDD index: {path}")
    by_path = payload.get("by_tdd_path")
    by_digest = payload.get("by_tdd_sha256")
    by_task = payload.get("by_task_id")
    diagnostics = payload.get("diagnostics")
    if (
        not isinstance(by_path, dict)
        or not isinstance(by_digest, dict)
        or not isinstance(by_task, dict)
    ):
        raise TddBindingError(f"invalid TDD index: {path}")
    if not isinstance(diagnostics, list) or diagnostics:
        raise TddBindingError(f"invalid TDD index: {path}")
    raw_path = cast(dict[object, object], by_path)
    raw_task = cast(dict[object, object], by_task)
    raw_digest = cast(dict[object, object], by_digest)
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in raw_path.items()):
        raise TddBindingError(f"invalid TDD index: {path}")
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in raw_task.items()):
        raise TddBindingError(f"invalid TDD index: {path}")
    parsed_digest: dict[str, tuple[str, ...]] = {}
    for key, item in raw_digest.items():
        if not isinstance(key, str) or not _SHA256.fullmatch(key) or not isinstance(item, list):
            raise TddBindingError(f"invalid TDD index: {path}")
        raw_task_ids = cast(list[object], item)
        if not all(isinstance(task_id, str) for task_id in raw_task_ids):
            raise TddBindingError(f"invalid TDD index: {path}")
        parsed_digest[key] = tuple(cast(str, task_id) for task_id in raw_task_ids)
    return TddIndex(
        {cast(str, key): cast(str, item) for key, item in raw_path.items()},
        parsed_digest,
        {cast(str, key): cast(str, item) for key, item in raw_task.items()},
    )


def _write_snapshot(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise TddBindingError(
                f"canonical TDD snapshot already exists with different bytes: {path}"
            )
        return
    _write_bytes(path, content, overwrite=False)


def _write_json(path: Path, value: JsonObject, *, overwrite: bool) -> None:
    _write_bytes(path, _json_bytes(value), overwrite=overwrite)


def _json_bytes(value: JsonObject) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_bytes(path: Path, value: bytes, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise TddBindingError(f"refusing to overwrite existing canonical state: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
