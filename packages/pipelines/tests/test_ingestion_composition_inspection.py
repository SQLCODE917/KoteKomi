"""Current saved Composition outcomes for Events in one retained IngestionRun.

The retained IRA run supplies a real mixed state: one composed Event, many typed
holds, paragraphs without Events, and paragraph locations for every Event. The
tests copy that run before changing anything, and they never call an analyzer or
rerun composition.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TypedDict, cast

import pytest
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import EventCompositionRecord, EventCompositionStatus
from kotekomi_pipelines import cli
from kotekomi_pipelines.ingestion_composition_inspection import (
    InspectCompositionOutcomesInput,
    InspectCompositionOutcomesResult,
    _resolve_outcome,
    inspect_composition_outcomes,
    realized_event_evidence,
)

RETAINED = (
    Path(__file__).resolve().parents[3] / "data" / "ira-acceptance-20261105-141506-176099" / "state"
)
RUN = "igr_c4b8a09978114e49bb63e8c7df73a005"
COMPOSED_EVENT = "sge_6691bbb38ce7e592ea5ab155"
COMPOSED_PARAGRAPH = 14
HELD_EVENT = "sge_b7ed76a97b0b968caa0b52bd"
HELD_PARAGRAPH = 1
MALFORMED_EVENT = "sge_d0093ff082341fd88823576a"
MALFORMED_PARAGRAPH = 2
MISMATCHED_EVENT = "sge_5d71f09fceb81fadbab208e9"
MISMATCHED_PARAGRAPH = 3
NO_EVENT_PARAGRAPH = 18
EXPECTED_EVENTS = 167
EXPECTED_COMPOSED = 1
EXPECTED_HELD = 166

requires_retained = pytest.mark.skipif(
    not (RETAINED / "kotekomi.db").is_file(),
    reason="the retained IRA IngestionRun is not present in this checkout",
)


def _isolated_state(tmp_path: Path) -> Path:
    root = tmp_path / "state"
    shutil.copytree(RETAINED, root)
    return root


def _config(tmp_path: Path, root: Path) -> Path:
    path = tmp_path / "kotekomi.toml"
    path.write_text(
        f'ledger_path = "{(root / "kotekomi.db").as_posix()}"\n'
        f'archive_path = "{(root / "archive").as_posix()}"\n'
        'runtime_profile = "fixture"\n'
        "[processing]\n"
        'representation_policy_version = "deposited-source-v1"\n',
        encoding="utf-8",
    )
    return path


def _inspect(root: Path) -> InspectCompositionOutcomesResult:
    return inspect_composition_outcomes(
        InspectCompositionOutcomesInput(
            ledger_path=root / "kotekomi.db",
            archive_path=root / "archive",
            ingestion_run_id=RUN,
        )
    )


def _run_cli(config: Path, output_format: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(
            [
                "--config",
                str(config),
                "ingestions",
                "composition",
                RUN,
                "--format",
                output_format,
            ]
        )
    return code, out.getvalue(), err.getvalue()


def _row_locations(paragraphs: tuple[int, ...]) -> str:
    return (
        f"paragraph {paragraphs[0]}"
        if len(paragraphs) == 1
        else "paragraphs " + ",".join(str(item) for item in paragraphs)
    )


def _text_rows(text: str) -> list[tuple[str, str, str]]:
    lines = text.splitlines()
    start = lines.index("Events:") + 1
    rows: list[tuple[str, str, str]] = []
    for line in lines[start:]:
        status, locations, event_id = line.split("\t")[:3]
        rows.append((status, locations, event_id))
    return rows


class _JsonRow(TypedDict):
    event_id: str
    status: str
    paragraphs: list[int]
    hold_reason: str | None
    diagnostic: str | None


class _JsonPayload(TypedDict):
    ingestion_run_id: str
    total_events: int
    counts: dict[str, int]
    events: list[_JsonRow]


def _json_rows(payload: _JsonPayload) -> list[tuple[str, str, str]]:
    return [
        (event["status"], _row_locations(tuple(event["paragraphs"])), event["event_id"])
        for event in payload["events"]
    ]


@requires_retained
def test_current_mixed_outcomes_are_reported(tmp_path: Path) -> None:
    """One retained run shows composed, held, missing, and no-Event evidence."""
    root = _isolated_state(tmp_path)
    (root / "composition-outcomes" / f"{HELD_EVENT}.json").unlink()

    result = _inspect(root)

    assert result.ingestion_run_id == RUN
    assert result.total_events == EXPECTED_EVENTS
    assert result.counts == {
        "composed": EXPECTED_COMPOSED,
        "held": EXPECTED_HELD - 1,
        "missing": 1,
        "invalid": 0,
    }
    by_id = {row.event_id: row for row in result.rows}
    assert by_id[COMPOSED_EVENT].status == "composed"
    assert by_id[COMPOSED_EVENT].paragraphs == (COMPOSED_PARAGRAPH,)
    assert by_id[HELD_EVENT].status == "missing"
    assert by_id[HELD_EVENT].paragraphs == (HELD_PARAGRAPH,)
    held = next(row for row in result.rows if row.status == "held")
    assert held.hold_reason == "assertion_inputs_unavailable"
    assert all(NO_EVENT_PARAGRAPH not in row.paragraphs for row in result.rows)
    assert result.rows == tuple(sorted(result.rows, key=lambda row: (row.paragraphs, row.event_id)))


@requires_retained
def test_text_and_json_report_the_same_rows(tmp_path: Path) -> None:
    """Text and JSON share counts, rows, and stable order."""
    root = _isolated_state(tmp_path)
    (root / "composition-outcomes" / f"{HELD_EVENT}.json").unlink()
    config = _config(tmp_path, root)

    code, text, err = _run_cli(config, "text")
    assert (code, err) == (0, "")
    text_lines = text.splitlines()
    assert text_lines[:3] == [
        f"IngestionRun: {RUN}",
        "Current saved Composition outcomes:",
        f"Realized Events: {EXPECTED_EVENTS}",
    ]
    assert "Composed: 1" in text_lines
    assert f"Held: {EXPECTED_HELD - 1}" in text_lines
    assert "Missing: 1" in text_lines
    assert "Invalid: 0" in text_lines
    assert "the US" not in text
    assert "the 2026 Iran war" not in text

    code, payload_text, err = _run_cli(config, "json")
    assert (code, err) == (0, "")
    payload = cast(_JsonPayload, json.loads(payload_text))
    assert payload["ingestion_run_id"] == RUN
    assert payload["total_events"] == EXPECTED_EVENTS
    assert payload["counts"] == {
        "composed": EXPECTED_COMPOSED,
        "held": EXPECTED_HELD - 1,
        "missing": 1,
        "invalid": 0,
    }
    assert _text_rows(text) == _json_rows(payload)
    assert len(payload["events"]) == EXPECTED_EVENTS


@requires_retained
def test_invalid_evidence_is_actionable_and_not_repaired(tmp_path: Path) -> None:
    """Malformed and mismatched files are invalid; unrelated files are ignored."""
    root = _isolated_state(tmp_path)
    outcomes = root / "composition-outcomes"
    (outcomes / f"{HELD_EVENT}.json").unlink()
    malformed = outcomes / f"{MALFORMED_EVENT}.json"
    malformed.write_text("{not a composition record", encoding="utf-8")
    store = CompositionOutcomeStore(outcomes)
    record = store.load(MISMATCHED_EVENT)
    mismatched = outcomes / f"{MISMATCHED_EVENT}.json"
    store.save(
        EventCompositionRecord(
            event_id=record.event_id,
            source_text_sha256="0" * 64,
            status=record.status,
            hold_reason=record.hold_reason,
        )
    )
    unrelated = outcomes / "unrelated.json"
    unrelated.write_text("{not a composition record", encoding="utf-8")
    malformed_before = malformed.read_bytes()
    mismatched_before = mismatched.read_bytes()
    unrelated_before = unrelated.read_bytes()
    config = _config(tmp_path, root)

    code, text, err = _run_cli(config, "text")

    assert (code, err) == (1, "")
    assert "Composed: 1" in text
    assert f"Held: {EXPECTED_HELD - 3}" in text
    assert "Missing: 1" in text
    assert "Invalid: 2" in text
    assert (
        f"invalid\tparagraph {MALFORMED_PARAGRAPH}\t{MALFORMED_EVENT}\t"
        "diagnostic: outcome is malformed"
    ) in text
    assert (
        f"invalid\tparagraph {MISMATCHED_PARAGRAPH}\t{MISMATCHED_EVENT}\t"
        "diagnostic: source text digest differs from the paragraph"
    ) in text
    assert f"missing\tparagraph {HELD_PARAGRAPH}\t{HELD_EVENT}" in text
    assert "unrelated" not in text
    assert "the US" not in text
    assert "the 2026 Iran war" not in text

    code, payload_text, err = _run_cli(config, "json")
    assert (code, err) == (1, "")
    payload = cast(_JsonPayload, json.loads(payload_text))
    assert payload["counts"] == {
        "composed": 1,
        "held": EXPECTED_HELD - 3,
        "missing": 1,
        "invalid": 2,
    }
    assert _text_rows(text) == _json_rows(payload)

    assert malformed.read_bytes() == malformed_before
    assert mismatched.read_bytes() == mismatched_before
    assert unrelated.read_bytes() == unrelated_before
    assert not (outcomes / f"{HELD_EVENT}.json").exists()


@requires_retained
def test_newer_saved_outcome_is_reported_as_current(tmp_path: Path) -> None:
    """A later saved outcome replaces the earlier result without historical claims."""
    root = _isolated_state(tmp_path)
    store = CompositionOutcomeStore(root / "composition-outcomes")

    before = _inspect(root)
    assert {row.event_id: row.status for row in before.rows}[COMPOSED_EVENT] == "composed"

    current = store.load(COMPOSED_EVENT)
    store.save(
        EventCompositionRecord(
            event_id=current.event_id,
            source_text_sha256=current.source_text_sha256,
            status=EventCompositionStatus.HELD,
            hold_reason="selection_gap",
        )
    )
    after = _inspect(root)

    row = {item.event_id: item for item in after.rows}[COMPOSED_EVENT]
    assert row.status == "held"
    assert row.hold_reason == "selection_gap"
    assert after.counts == {
        "composed": 0,
        "held": EXPECTED_HELD + 1,
        "missing": 0,
        "invalid": 0,
    }


def test_realized_events_count_once_per_paragraph_evidence() -> None:
    """Repeated occurrences do not inflate the denominator or merge conflicts."""
    evidence = realized_event_evidence(
        (
            (1, "a" * 64, ("sge_repeat",)),
            (1, "a" * 64, ("sge_repeat",)),
            (2, "b" * 64, ("sge_repeat",)),
        )
    )

    assert evidence == {"sge_repeat": ((1, "a" * 64), (2, "b" * 64))}


def test_unreadable_outcome_is_invalid() -> None:
    """An unreadable matching file is invalid, not a saved or missing outcome."""

    def load(_event_id: str) -> EventCompositionRecord:
        raise OSError("fixture read failure")

    row = _resolve_outcome(
        event_id="sge_unreadable",
        evidence=((1, "a" * 64),),
        load=load,
    )

    assert row.status == "invalid"
    assert row.diagnostic == "outcome is unreadable"


def test_conflicting_paragraph_evidence_is_invalid_not_deduplicated() -> None:
    """A conflicting Event location is actionable and never silently chosen."""

    def load(_event_id: str) -> EventCompositionRecord:
        raise AssertionError("conflicting evidence must not read one saved outcome")

    row = _resolve_outcome(
        event_id="sge_conflict",
        evidence=((1, "a" * 64), (2, "b" * 64)),
        load=load,
    )

    assert row.status == "invalid"
    assert row.paragraphs == (1, 2)
    assert row.diagnostic == "conflicting paragraph evidence"


def test_zero_events_does_not_claim_completed_composition() -> None:
    """Zero realized Events is reported as zero, not as completion."""
    result = InspectCompositionOutcomesResult(
        ingestion_run_id="igr_empty",
        total_events=0,
        counts={"composed": 0, "held": 0, "missing": 0, "invalid": 0},
        rows=(),
    )

    text = cli._composition_inspection_text(result)

    assert "Realized Events: 0" in text
    assert "Events: none" in text
    assert "complete" not in text.lower()
