"""Reserved passage custody for the IPI package.

The reviewer authors the reserved manifest outside the implementing agent's
context. This module validates that manifest against the package rules and the
inspected-material record, then seals it under a custody root. Diagnostics name
passage identifiers and digests only; they never echo reserved text.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

PASSAGE_COUNT = 6
STATEMENT_KINDS = ("straightforward", "qualified")


class CustodyError(ValueError):
    """The reserved manifest breaks a custody rule."""


@dataclass(frozen=True)
class ReservedStatement:
    """One reserved reference statement and the context the reviewer allows to omit."""

    reference_id: str
    kind: str
    required_content: str
    admissible_omissions: str
    in_scope_rationale: str


@dataclass(frozen=True)
class ReservedPassage:
    """One sealed reserved passage."""

    passage_id: str
    source_path: str
    source_sha256: str
    page: int
    text_sha256: str
    statements: tuple[ReservedStatement, ...]


@dataclass(frozen=True)
class ReservedManifest:
    """The reviewer-owned reserved partition."""

    revision: str
    reviewer: str
    sealed_on: str
    passages: tuple[ReservedPassage, ...]


def reserved_template(*, source_path: str, source_sha256: str, reviewer: str) -> dict[str, Any]:
    """Return the empty reserved manifest the reviewer fills in."""
    return {
        "record": "ipi-reserved-manifest-v1",
        "revision": "7dc9a44",
        "reviewer": reviewer,
        "sealed_on": "YYYY-MM-DD",
        "passages": [
            {
                "passage_id": f"RES-{index:02d}",
                "source_path": source_path,
                "source_sha256": source_sha256,
                "page": 0,
                "text": "",
                "text_sha256": "",
                "context_before": "",
                "context_after": "",
                "statements": [
                    {
                        "reference_id": f"R-RES-{index:02d}",
                        "kind": "straightforward",
                        "statement": "",
                        "required_content": "",
                        "admissible_omissions": "",
                        "in_scope_rationale": "",
                    }
                ],
            }
            for index in range(1, PASSAGE_COUNT + 1)
        ],
    }


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CustodyError("Each manifest record must be a JSON object.")
    return cast("dict[str, Any]", value)


def _text(mapping: object, key: str, where: str) -> str:
    value = _mapping(mapping).get(key)
    if not isinstance(value, str) or not value.strip():
        raise CustodyError(f"{where}: {key} must be non-empty text.")
    return value


def _inspected(payload: object) -> dict[str, Any]:
    record = _mapping(payload)
    if not isinstance(record.get("sources"), list):
        raise CustodyError("The inspected-material record needs one sources list.")
    return record


def _inspected_for(source_path: str, inspected: dict[str, Any]) -> dict[str, Any]:
    for source in cast("list[object]", inspected["sources"]):
        record = _mapping(source)
        if record.get("path") == source_path:
            return record
    raise CustodyError(f"Source {source_path} is absent from the inspected-material record.")


def validate_manifest(payload: object, inspected: object) -> ReservedManifest:
    """Validate the reserved manifest against the package custody rules."""
    document = _mapping(payload)
    if document.get("record") != "ipi-reserved-manifest-v1":
        raise CustodyError("The reserved manifest has the wrong record name.")
    revision = _text(document, "revision", "manifest")
    reviewer = _text(document, "reviewer", "manifest")
    sealed_on = _text(document, "sealed_on", "manifest")
    rows = document.get("passages")
    if not isinstance(rows, list) or len(cast("list[object]", rows)) != PASSAGE_COUNT:
        raise CustodyError(f"The reserved partition requires exactly {PASSAGE_COUNT} passages.")
    inspected_record = _inspected(inspected)
    passages: list[ReservedPassage] = []
    kinds: list[str] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    seen_references: set[str] = set()
    for row in cast("list[object]", rows):
        passage = _mapping(row)
        passage_id = _text(passage, "passage_id", "passage")
        if passage_id in seen_ids:
            raise CustodyError(f"Passage {passage_id} is duplicated.")
        seen_ids.add(passage_id)
        source_path = _text(passage, "source_path", passage_id)
        source_sha256 = _text(passage, "source_sha256", passage_id)
        source = _inspected_for(source_path, inspected_record)
        if source.get("sha256") != source_sha256:
            raise CustodyError(f"{passage_id}: source digest does not match the inspected record.")
        if source.get("excluded_from_reserved") is True:
            raise CustodyError(f"{passage_id}: the source is excluded from the reserved partition.")
        page = passage.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise CustodyError(f"{passage_id}: page must be a positive integer.")
        text = _text(passage, "text", passage_id)
        digest = _text(passage, "text_sha256", passage_id)
        if text_digest(text) != digest:
            raise CustodyError(f"{passage_id}: passage digest does not match its text.")
        if digest in seen_texts:
            raise CustodyError(f"Passage {passage_id} repeats another passage.")
        seen_texts.add(digest)
        inspected_digests = source.get("inspected_paragraph_sha256")
        if isinstance(inspected_digests, list) and digest in inspected_digests:
            raise CustodyError(f"{passage_id}: the passage is in the inspected-material record.")
        statements = passage.get("statements")
        if not isinstance(statements, list) or not statements:
            raise CustodyError(f"{passage_id}: every passage carries one reference statement.")
        parsed: list[ReservedStatement] = []
        for statement_row in cast("list[object]", statements):
            statement = _mapping(statement_row)
            reference_id = _text(statement, "reference_id", passage_id)
            if reference_id in seen_references:
                raise CustodyError(f"Reference {reference_id} is duplicated.")
            seen_references.add(reference_id)
            kind = _text(statement, "kind", reference_id)
            if kind not in STATEMENT_KINDS:
                raise CustodyError(f"{reference_id}: kind must be one of {STATEMENT_KINDS}.")
            kinds.append(kind)
            parsed.append(
                ReservedStatement(
                    reference_id=reference_id,
                    kind=kind,
                    required_content=_text(statement, "required_content", reference_id),
                    admissible_omissions=_text(statement, "admissible_omissions", reference_id),
                    in_scope_rationale=_text(statement, "in_scope_rationale", reference_id),
                )
            )
        passages.append(
            ReservedPassage(
                passage_id=passage_id,
                source_path=source_path,
                source_sha256=source_sha256,
                page=page,
                text_sha256=digest,
                statements=tuple(parsed),
            )
        )
    if kinds.count("straightforward") < 2:
        raise CustodyError("The reserved partition needs two straightforward statements.")
    if kinds.count("qualified") < 2:
        raise CustodyError("The reserved partition needs two qualified statements.")
    return ReservedManifest(
        revision=revision,
        reviewer=reviewer,
        sealed_on=sealed_on,
        passages=tuple(passages),
    )


def text_digest(text: str) -> str:
    """Return the digest of one passage text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_digest(value: Any) -> str:
    """Return the digest of one canonical JSON value."""
    payload = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def manifest_summary(manifest: ReservedManifest) -> dict[str, Any]:
    """Return the reviewable summary: counts and digests, never passage text."""
    kinds = [statement.kind for passage in manifest.passages for statement in passage.statements]
    return {
        "passage_count": len(manifest.passages),
        "statement_count": len(kinds),
        "straightforward_statement_count": kinds.count("straightforward"),
        "qualified_statement_count": kinds.count("qualified"),
        "source_count": len({passage.source_sha256 for passage in manifest.passages}),
        "passage_digests": [passage.text_sha256 for passage in manifest.passages],
        "reference_ids": [
            statement.reference_id
            for passage in manifest.passages
            for statement in passage.statements
        ],
    }


def fill_text_digests(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with each passage's text digest computed from its text."""
    filled: dict[str, Any] = cast("dict[str, Any]", json.loads(json.dumps(payload)))
    passages = filled.get("passages")
    if isinstance(passages, list):
        for row in cast("list[object]", passages):
            passage = _mapping(row)
            text = passage.get("text")
            if isinstance(text, str):
                passage["text_sha256"] = text_digest(text)
    return filled


def seal(custody_root: Path, payload: dict[str, Any], inspected: Any) -> tuple[Path, str]:
    """Validate the reserved manifest and write it under the custody root."""
    validate_manifest(payload, inspected)
    custody_root.mkdir(parents=True, exist_ok=True)
    path = custody_root / "reserved-manifest.json"
    if path.exists():
        raise CustodyError("A sealed reserved manifest already exists; the partition is fixed.")
    canonical = json.dumps(payload, allow_nan=False, indent=1, sort_keys=True) + "\n"
    path.write_text(canonical, encoding="utf-8")
    return path, canonical_digest(payload)


def load_manifest(path: Path) -> dict[str, Any]:
    """Load one reserved manifest document."""
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise CustodyError(f"Cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise CustodyError(f"{path} is not valid JSON: {error}") from error
    return _mapping(payload)
