"""Read current saved Composition outcomes for one retained IngestionRun.

The selected run's archived paragraphs define the denominator. Outcomes are read
one Event at a time; a later recomposition can replace one. The report therefore
describes current saved outcomes, not historical completion of that attempt.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import EventCompositionRecord, EventCompositionStatus
from kotekomi_application.ingestion_inspection import build_profile
from pydantic import ValidationError

from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs

type EventEvidence = tuple[int, str]
type CompositionStatus = Literal["composed", "held", "missing", "invalid"]
_STATUSES: tuple[CompositionStatus, ...] = ("composed", "held", "missing", "invalid")


@dataclass(frozen=True)
class InspectCompositionOutcomesInput:
    ledger_path: Path
    archive_path: Path
    ingestion_run_id: str


@dataclass(frozen=True)
class CompositionOutcomeRow:
    event_id: str
    status: CompositionStatus
    paragraphs: tuple[int, ...]
    hold_reason: str | None = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class InspectCompositionOutcomesResult:
    ingestion_run_id: str
    total_events: int
    counts: dict[str, int]
    rows: tuple[CompositionOutcomeRow, ...]


def realized_event_evidence(
    paragraphs: Iterable[tuple[int, str, Iterable[str]]],
) -> dict[str, tuple[EventEvidence, ...]]:
    """Group unique Event IDs; repeated identical evidence counts once."""
    grouped: dict[str, list[EventEvidence]] = {}
    for paragraph, source_text_sha256, event_ids in paragraphs:
        for event_id in event_ids:
            evidence = (paragraph, source_text_sha256)
            if evidence not in grouped.setdefault(event_id, []):
                grouped[event_id].append(evidence)
    return {event_id: tuple(items) for event_id, items in grouped.items()}


def inspect_composition_outcomes(
    input: InspectCompositionOutcomesInput,
) -> InspectCompositionOutcomesResult:
    """Report current saved outcomes for the selected run's realized Events."""
    paragraphs = load_paragraph_inputs(
        input.ledger_path, input.archive_path, ingestion_run_id=input.ingestion_run_id
    )
    evidence_by_event = realized_event_evidence(
        (
            paragraph.ordinal + 1,
            hashlib.sha256(paragraph.text.encode()).hexdigest(),
            tuple(
                event.event_id
                for event in build_profile(
                    text=paragraph.text,
                    representation_id=paragraph.representation_id,
                    paragraph_node_id=paragraph.paragraph_node_id,
                    node_start_char=paragraph.node_start_char,
                    stage_outputs=paragraph.stage_outputs,
                    bundle=paragraph.bundle,
                ).events
            ),
        )
        for paragraph in paragraphs
    )
    store = CompositionOutcomeStore(input.ledger_path.parent / "composition-outcomes")
    rows = tuple(
        sorted(
            (
                _resolve_outcome(event_id=event_id, evidence=evidence, load=store.load)
                for event_id, evidence in evidence_by_event.items()
            ),
            key=lambda row: (row.paragraphs, row.event_id),
        )
    )
    return InspectCompositionOutcomesResult(
        ingestion_run_id=input.ingestion_run_id,
        total_events=len(rows),
        counts={status: sum(1 for row in rows if row.status == status) for status in _STATUSES},
        rows=rows,
    )


def _resolve_outcome(
    *,
    event_id: str,
    evidence: tuple[EventEvidence, ...],
    load: Callable[[str], EventCompositionRecord],
) -> CompositionOutcomeRow:
    """Resolve one Event from exactly one retained evidence set."""
    paragraphs = tuple(sorted({paragraph for paragraph, _digest in evidence}))
    if len(evidence) != 1:
        return _invalid(event_id, paragraphs, "conflicting paragraph evidence")
    try:
        record = load(event_id)
    except FileNotFoundError:
        return CompositionOutcomeRow(event_id, "missing", paragraphs)
    except OSError:
        return _invalid(event_id, paragraphs, "outcome is unreadable")
    except ValidationError:
        return _invalid(event_id, paragraphs, "outcome is malformed")
    if record.event_id != event_id:
        return _invalid(event_id, paragraphs, "Event ID differs from its file name")
    if record.source_text_sha256 != evidence[0][1]:
        return _invalid(event_id, paragraphs, "source text digest differs from the paragraph")
    if record.status is EventCompositionStatus.HELD:
        assert record.hold_reason is not None
        return CompositionOutcomeRow(event_id, "held", paragraphs, record.hold_reason)
    if record.status is EventCompositionStatus.COMPOSED:
        return CompositionOutcomeRow(event_id, "composed", paragraphs)
    return _invalid(event_id, paragraphs, "unsupported outcome status")


def _invalid(event_id: str, paragraphs: tuple[int, ...], diagnostic: str) -> CompositionOutcomeRow:
    return CompositionOutcomeRow(event_id, "invalid", paragraphs, None, diagnostic)


def composition_inspection_to_json(
    result: InspectCompositionOutcomesResult,
) -> dict[str, object]:
    """Serialize the same counts and rows the text report prints."""
    payload = asdict(result)
    payload["schema_version"] = 1
    payload["events"] = payload.pop("rows")
    return payload
