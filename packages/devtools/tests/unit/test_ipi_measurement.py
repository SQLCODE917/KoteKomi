"""IPI measurement validation and route decisions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from kotekomi_devtools.ipi_measurement import (
    MeasurementError,
    compare,
    load_condition_result,
    measure,
)


def _row(reference_id: str, outcome: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "reference_id": reference_id,
        "outcome": outcome,
        "first_blocking_stage": "none" if outcome == "usable" else "composition",
        "active_seconds": 60,
        "waiting_seconds": 0,
        "corrections": 0,
        "hold_reason": None,
        "failing_criterion": None,
        "event_id": "sge_example",
        "assertion_id": "ast_example" if outcome == "usable" else None,
        "proposal_id": "pcg_example" if outcome == "usable" else None,
        "notes": "",
    }
    if outcome == "hold":
        row["hold_reason"] = "unsupported_time_place"
    if outcome == "incorrect":
        row["failing_criterion"] = "essential_complements"
    if outcome == "not_attempted":
        row["active_seconds"] = 0
    row.update(overrides)
    return row


def _document(
    *,
    condition: str = "baseline",
    rows: list[dict[str, object]],
    waiting_time_accepted: bool = False,
) -> dict[str, object]:
    return {
        "partition": "reserved",
        "condition": condition,
        "revision": "7dc9a44",
        "operator": "operator",
        "root": "/tmp/root",
        "waiting_time_accepted": waiting_time_accepted,
        "statements": rows,
    }


def _write(tmp_path: Path, payload: dict[str, object], name: str = "result.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _result(condition: str, rows: list[dict[str, object]]) -> object:
    return load_condition_result(
        _write(Path(tempfile.mkdtemp()), _document(condition=condition, rows=rows), "r.json")
    )


def test_measure_counts_usable_rows_and_keeps_failed_effort(tmp_path: Path) -> None:
    payload = _document(
        rows=[
            _row("R-1", "usable", active_seconds=100),
            _row("R-2", "hold", active_seconds=80),
            _row("R-3", "timeout", active_seconds=300),
            _row("R-4", "not_attempted"),
        ]
    )
    measures = measure(load_condition_result(_write(tmp_path, payload)))
    assert measures.reference_count == 4
    assert measures.usable_count == 1
    assert measures.active_seconds == 480
    assert measures.review_cost_seconds == pytest.approx(480.0)


def test_usable_row_requires_its_proposal_and_assertion(tmp_path: Path) -> None:
    payload = _document(rows=[_row("R-1", "usable", proposal_id=None)])
    with pytest.raises(MeasurementError, match="ProposedChange"):
        load_condition_result(_write(tmp_path, payload))


def test_attempted_row_requires_measured_active_time(tmp_path: Path) -> None:
    payload = _document(rows=[_row("R-1", "hold", active_seconds=0)])
    with pytest.raises(MeasurementError, match="active seconds"):
        load_condition_result(_write(tmp_path, payload))


def test_unknown_stage_is_rejected(tmp_path: Path) -> None:
    payload = _document(rows=[_row("R-1", "hold", first_blocking_stage="somewhere")])
    with pytest.raises(MeasurementError, match="first_blocking_stage"):
        load_condition_result(_write(tmp_path, payload))


def test_duplicate_reference_ids_are_rejected(tmp_path: Path) -> None:
    payload = _document(rows=[_row("R-1", "hold"), _row("R-1", "hold")])
    with pytest.raises(MeasurementError, match="unique"):
        load_condition_result(_write(tmp_path, payload))


def test_capability_route_passes_when_two_more_statements_become_usable() -> None:
    baseline = _result(
        "baseline",
        [_row("R-1", "hold", active_seconds=100), _row("R-2", "hold", active_seconds=100)],
    )
    final = _result(
        "final",
        [_row("R-1", "usable", active_seconds=100), _row("R-2", "usable", active_seconds=100)],
    )
    decision = compare(baseline, final)
    assert decision.capability_route is True
    assert decision.passed is True


def test_effort_route_passes_when_cost_falls_by_a_quarter() -> None:
    baseline = _result(
        "baseline",
        [
            _row("R-1", "usable", active_seconds=120),
            _row("R-2", "usable", active_seconds=120),
            _row("R-3", "usable", active_seconds=120),
        ],
    )
    final = _result(
        "final",
        [
            _row("R-1", "usable", active_seconds=80),
            _row("R-2", "usable", active_seconds=80),
            _row("R-3", "usable", active_seconds=80),
        ],
    )
    decision = compare(baseline, final)
    assert decision.effort_route is True
    assert decision.passed is True


def test_lost_usable_statement_fails_the_comparison() -> None:
    baseline = _result("baseline", [_row("R-1", "usable"), _row("R-2", "hold")])
    final = _result(
        "final",
        [_row("R-1", "hold"), _row("R-2", "usable"), _row("R-3", "usable")],
    )
    decision = compare(baseline, final)
    assert decision.regressions == ("R-1",)
    assert decision.passed is False


def test_waiting_time_increase_needs_operator_acceptance(tmp_path: Path) -> None:
    baseline = _result("baseline", [_row("R-1", "usable", waiting_seconds=100)])
    final_rows = [_row("R-1", "usable", waiting_seconds=200)]
    unaccepted = load_condition_result(
        _write(tmp_path, _document(condition="final", rows=final_rows), "final.json")
    )
    assert compare(baseline, unaccepted).waiting_time_passed is False
    accepted = load_condition_result(
        _write(
            tmp_path,
            _document(condition="final", rows=final_rows, waiting_time_accepted=True),
            "final-accepted.json",
        )
    )
    assert compare(baseline, accepted).waiting_time_passed is True
