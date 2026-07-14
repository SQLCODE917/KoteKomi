"""Task Manifest V1 loading, validation, and canonical serialization."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator, ValidationError

type JsonObject = dict[str, Any]
type DiagnosticCode = Literal[
    "task_manifest.file_not_found",
    "task_manifest.file_unreadable",
    "task_manifest.toml_parse_error",
    "task_manifest.schema_violation",
    "task_manifest.semantic_violation",
    "task_manifest.path_violation",
]

_IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_WILDCARD_CHARACTERS = frozenset("*?[]")
_SCHEMA_PATH = Path(".agent/schemas/task-manifest-v1.schema.json")


@dataclass(frozen=True)
class Diagnostic:
    """One stable Task Manifest validation diagnostic."""

    code: DiagnosticCode
    location: str
    rule: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "rule": self.rule}


@dataclass(frozen=True)
class ValidationResult:
    """The public result of validating one Task Manifest."""

    schema_version: int | None
    task_id: str | None
    manifest_sha256: str | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def valid(self) -> bool:
        return not self.diagnostics

    def as_json(self) -> dict[str, object]:
        return {
            "status": "valid" if self.valid else "invalid",
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "manifest_sha256": self.manifest_sha256,
            "diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics],
        }


def validate_task_manifest(path: Path) -> ValidationResult:
    """Validate a Task Manifest without accessing its referenced records."""
    parsed = _read_toml(path)
    if isinstance(parsed, ValidationResult):
        return parsed

    identity = _parsed_identity(parsed)
    schema_diagnostics = _schema_diagnostics(parsed)
    if schema_diagnostics:
        return ValidationResult(*identity, None, _sorted(schema_diagnostics))

    semantic_diagnostics = _semantic_and_path_diagnostics(parsed)
    if semantic_diagnostics:
        return ValidationResult(*identity, None, _sorted(semantic_diagnostics))

    return ValidationResult(*identity, _canonical_digest(parsed), ())


def _read_toml(path: Path) -> JsonObject | ValidationResult:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _file_failure("task_manifest.file_not_found", "exists")
    except UnicodeDecodeError:
        return _file_failure("task_manifest.file_unreadable", "utf8")
    except OSError:
        return _file_failure("task_manifest.file_unreadable", "readable")

    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return ValidationResult(
            None,
            None,
            None,
            (Diagnostic("task_manifest.toml_parse_error", "", "toml"),),
        )
    return parsed


def _file_failure(code: DiagnosticCode, rule: str) -> ValidationResult:
    return ValidationResult(None, None, None, (Diagnostic(code, "", rule),))


def _parsed_identity(parsed: Mapping[str, object]) -> tuple[int | None, str | None]:
    schema_version = parsed.get("schema_version")
    task_id = parsed.get("task_id")
    return (
        schema_version if type(schema_version) is int and schema_version == 1 else None,
        task_id if isinstance(task_id, str) and _IDENTIFIER.fullmatch(task_id) else None,
    )


def _schema_diagnostics(parsed: JsonObject) -> list[Diagnostic]:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors: Iterable[ValidationError] = validator.iter_errors(parsed)  # type: ignore[reportUnknownMemberType]
    return [_schema_diagnostic(error) for error in errors]


def _schema_diagnostic(error: ValidationError) -> Diagnostic:
    return Diagnostic(
        "task_manifest.schema_violation",
        _json_pointer(error.absolute_path),
        cast(str, error.validator),
    )


def _semantic_and_path_diagnostics(parsed: JsonObject) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    _validate_path(diagnostics, "/tdd_path", _string_at(parsed, "tdd_path"), exact_file=True)
    _validate_path_array(diagnostics, "/allowed_paths", _string_array(parsed, "allowed_paths"))
    _validate_path_array(diagnostics, "/reference_paths", _string_array(parsed, "reference_paths"))

    protected_artifacts = _object_array(parsed, "protected_artifacts")
    protected_paths = [artifact["path"] for artifact in protected_artifacts]
    for index, protected_path in enumerate(protected_paths):
        _validate_path(
            diagnostics,
            f"/protected_artifacts/{index}/path",
            cast(str, protected_path),
            exact_file=True,
        )
    _validate_duplicates(
        diagnostics,
        "/protected_artifacts",
        protected_paths,
        "path",
        "task_manifest.path_violation",
        "unique_path",
    )

    acceptance = _object_array(parsed, "acceptance")
    _validate_duplicates(
        diagnostics,
        "/acceptance",
        [command["id"] for command in acceptance],
        "id",
        "task_manifest.semantic_violation",
        "unique_identifier",
    )
    return diagnostics


def _string_at(value: Mapping[str, object], key: str) -> str:
    return cast(str, value[key])


def _string_array(value: Mapping[str, object], key: str) -> list[object]:
    return cast(list[object], value[key])


def _object_array(value: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    return [cast(Mapping[str, object], item) for item in cast(list[object], value[key])]


def _validate_path_array(
    diagnostics: list[Diagnostic],
    base_location: str,
    paths: list[object],
) -> None:
    for index, path in enumerate(paths):
        _validate_path(diagnostics, f"{base_location}/{index}", cast(str, path), exact_file=False)
    _validate_duplicates(
        diagnostics,
        base_location,
        paths,
        None,
        "task_manifest.path_violation",
        "unique_path",
    )


def _validate_path(
    diagnostics: list[Diagnostic],
    location: str,
    path: str,
    *,
    exact_file: bool,
) -> None:
    if not _is_repository_relative_posix_path(path):
        diagnostics.append(
            Diagnostic("task_manifest.path_violation", location, "repository_relative_posix")
        )
    if exact_file and path.endswith("/"):
        diagnostics.append(Diagnostic("task_manifest.path_violation", location, "exact_file"))


def _is_repository_relative_posix_path(path: str) -> bool:
    if not path or path.startswith(("/", "~")) or "\\" in path or "//" in path:
        return False
    if _WILDCARD_CHARACTERS.intersection(path):
        return False
    return all(segment not in {".", ".."} for segment in path.split("/"))


def _validate_duplicates(
    diagnostics: list[Diagnostic],
    base_location: str,
    values: list[object],
    field: str | None,
    code: DiagnosticCode,
    rule: str,
) -> None:
    seen: set[object] = set()
    for index, value in enumerate(values):
        if value in seen:
            suffix = f"/{field}" if field is not None else ""
            diagnostics.append(Diagnostic(code, f"{base_location}/{index}{suffix}", rule))
        else:
            seen.add(value)


def _canonical_digest(parsed: JsonObject) -> str:
    canonical = json.dumps(
        parsed,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _json_pointer(path: Iterable[object]) -> str:
    return "".join(f"/{_escape_pointer_segment(segment)}" for segment in path)


def _escape_pointer_segment(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _sorted(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(
        sorted(
            diagnostics,
            key=lambda diagnostic: (
                diagnostic.location,
                diagnostic.code,
                diagnostic.rule,
            ),
        )
    )
