"""Filesystem Adapter for one Event's persisted composition outcome.

The Application Layer owns the record and its validation. This Adapter stores one
record per Event under the replay source location, replaces each file atomically,
and raises on a malformed record instead of returning an empty result.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from kotekomi_application.ingestion_inspection import CompositionAnnotation
from kotekomi_application.source_grounded_reference_composition import (
    EventCompositionRecord,
    composition_annotation,
)


class CompositionOutcomeStore:
    """Store and load Event composition outcomes for one state root."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _path(self, event_id: str) -> Path:
        if not event_id or "/" in event_id or event_id in {".", ".."}:
            raise ValueError("Composition outcome requires one Event identifier.")
        return self._root / f"{event_id}.json"

    def save(self, record: EventCompositionRecord) -> None:
        """Replace one record atomically so a reader sees a complete file."""
        path = self._path(record.event_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = record.model_dump_json(indent=2)
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def save_at(self, path: Path, record: EventCompositionRecord) -> None:
        """Replace one explicit file atomically with one validated record."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = record.model_dump_json(indent=2)
        handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def save_many(self, records: tuple[EventCompositionRecord, ...]) -> None:
        for record in records:
            self.save(record)

    def load(self, event_id: str) -> EventCompositionRecord:
        """Load one record; a malformed record raises a validation error."""
        return EventCompositionRecord.model_validate_json(self._path(event_id).read_bytes())

    def load_all(self) -> tuple[EventCompositionRecord, ...]:
        if not self._root.is_dir():
            return ()
        return tuple(
            EventCompositionRecord.model_validate_json(path.read_bytes())
            for path in sorted(self._root.glob("*.json"))
        )

    def annotations(self, event_ids: tuple[str, ...]) -> tuple[CompositionAnnotation, ...]:
        """Return replay annotations for the Events a paragraph actually shows."""
        if not self._root.is_dir():
            return ()
        annotations: list[CompositionAnnotation] = []
        for event_id in event_ids:
            path = self._path(event_id)
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                continue
            record = EventCompositionRecord.model_validate_json(raw)
            if record.event_id != event_id:
                raise ValueError("Composition outcome filename and Event ID disagree.")
            annotations.append(
                replace(
                    composition_annotation(record),
                    outcome_path=f"{self._root.name}/{path.name}",
                    outcome_sha256=hashlib.sha256(raw).hexdigest(),
                )
            )
        return tuple(annotations)
