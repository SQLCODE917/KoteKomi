"""IPI measurement validation, manifest enforcement, and route decisions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from kotekomi_devtools.ipi_measurement import (
    ApprovedManifest,
    ConditionResult,
    MeasurementError,
    compare,
    load_approved_manifest,
    load_condition_result,
    measure,
)

BUDGET = 300


def _row(reference_id: str, outcome: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "reference_id": reference_id,
        "outcome": outcome,
        "first_blocking_stage": "none" if outcome == "usable" else "composition",
        "active_seconds": 60,
        "waiting_seconds": 0,
        "corrections": 0,
        "command_retries": 0,
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
        "partition": "development",
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


def _result(condition: str, rows: list[dict[str, object]]) -> ConditionResult:
    return load_condition_result(
        _write(Path(tempfile.mkdtemp()), _document(condition=condition, rows=rows), "r.json")
    )


def _manifest(
    tmp_path: Path, reference_ids: list[str], *, status: str = "approved"
) -> ApprovedManifest:
    payload = {
        "record": "ipi-development-manifest-v1",
        "status": status,
        "reviewer": "reviewer",
        "approved_on": "2026-11-06",
        "attempt_budget_seconds": BUDGET,
        "passages": [
            {
                "passage_id": "DEV-01",
                "statements": [{"reference_id": reference_id} for reference_id in reference_ids],
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_approved_manifest(path)


def _approved(tmp_path: Path, reference_ids: list[str]) -> ApprovedManifest:
    return _manifest(tmp_path, reference_ids)


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
    assert measures.review_cost_seconds == 480.0


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


def test_manifest_must_be_approved_before_any_comparison(tmp_path: Path) -> None:
    with pytest.raises(MeasurementError, match="not approved"):
        _manifest(tmp_path, ["R-1"], status="proposed")


def test_capability_route_passes_when_two_more_statements_become_usable(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1", "R-2"])
    baseline = _result(
        "baseline",
        [_row("R-1", "hold", active_seconds=100), _row("R-2", "hold", active_seconds=100)],
    )
    final = _result(
        "final",
        [_row("R-1", "usable", active_seconds=100), _row("R-2", "usable", active_seconds=100)],
    )
    decision = compare(baseline, final, manifest)
    assert decision.capability_route is True
    assert decision.passed is True


def test_effort_route_passes_when_cost_falls_by_a_quarter(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1", "R-2", "R-3"])
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
    decision = compare(baseline, final, manifest)
    assert decision.effort_route is True
    assert decision.passed is True


def test_lost_usable_statement_fails_the_comparison(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1", "R-2", "R-3"])
    baseline = _result(
        "baseline", [_row("R-1", "usable"), _row("R-2", "hold"), _row("R-3", "hold")]
    )
    final = _result(
        "final",
        [_row("R-1", "hold"), _row("R-2", "usable"), _row("R-3", "usable")],
    )
    decision = compare(baseline, final, manifest)
    assert decision.regressions == ("R-1",)
    assert decision.passed is False


def test_different_final_reference_set_cannot_pass(tmp_path: Path) -> None:
    """The reproduced false pass: 7 baseline references against 2 substituted references."""
    manifest = _approved(tmp_path, [f"R-{index}" for index in range(1, 8)])
    baseline = _result(
        "baseline", [_row(f"R-{index}", "hold", active_seconds=BUDGET) for index in range(1, 8)]
    )
    final = _result(
        "final",
        [
            _row("R-1", "usable", active_seconds=BUDGET),
            _row("R-2", "usable", active_seconds=BUDGET),
        ],
    )
    with pytest.raises(MeasurementError, match="records 2 statements"):
        compare(baseline, final, manifest)


def test_one_substituted_reference_is_rejected(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1", "R-2"])
    baseline = _result("baseline", [_row("R-1", "hold"), _row("R-2", "hold")])
    final = _result("final", [_row("R-1", "usable"), _row("R-9", "usable")])
    with pytest.raises(MeasurementError, match="omits approved references: R-2"):
        compare(baseline, final, manifest)


def test_a_statement_over_the_attempt_budget_is_rejected(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1"])
    baseline = _result("baseline", [_row("R-1", "hold", active_seconds=BUDGET + 1)])
    final = _result("final", [_row("R-1", "usable")])
    with pytest.raises(MeasurementError, match="attempt budget"):
        compare(baseline, final, manifest)


def test_not_attempted_statement_makes_the_comparison_incomplete(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1", "R-2"])
    baseline = _result("baseline", [_row("R-1", "hold"), _row("R-2", "not_attempted")])
    final = _result("final", [_row("R-1", "usable"), _row("R-2", "usable")])
    decision = compare(baseline, final, manifest)
    assert decision.incomplete_reference_ids == ("R-2",)
    assert decision.passed is False


def test_zero_baseline_capability_route_respects_the_baseline_attempt_budget(
    tmp_path: Path,
) -> None:
    manifest = _approved(tmp_path, ["R-1", "R-2"])
    baseline = _result(
        "baseline",
        [
            _row("R-1", "hold", active_seconds=BUDGET),
            _row("R-2", "hold", active_seconds=BUDGET),
        ],
    )
    at_budget = _result(
        "final",
        [
            _row("R-1", "usable", active_seconds=BUDGET),
            _row("R-2", "usable", active_seconds=BUDGET),
        ],
    )
    decision = compare(baseline, at_budget, manifest)
    assert decision.capability_route is True
    assert decision.budget_passed is True
    underspent = _result(
        "final",
        [_row("R-1", "usable", active_seconds=100), _row("R-2", "usable", active_seconds=100)],
    )
    assert compare(baseline, underspent, manifest).budget_passed is True


def test_zero_baseline_route_rejects_an_unapproved_extra_reference(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1"])
    baseline = _result("baseline", [_row("R-1", "hold", active_seconds=BUDGET)])
    final = _result(
        "final",
        [
            _row("R-1", "usable", active_seconds=BUDGET),
            _row("R-2", "usable", active_seconds=BUDGET),
        ],
    )
    with pytest.raises(MeasurementError, match="records 2 statements"):
        compare(baseline, final, manifest)


def test_waiting_time_increase_needs_operator_acceptance(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1"])
    baseline = _result("baseline", [_row("R-1", "usable", waiting_seconds=100)])
    final_rows = [_row("R-1", "usable", waiting_seconds=200)]
    unaccepted = load_condition_result(
        _write(tmp_path, _document(condition="final", rows=final_rows), "final.json")
    )
    assert compare(baseline, unaccepted, manifest).waiting_time_passed is False
    accepted = load_condition_result(
        _write(
            tmp_path,
            _document(condition="final", rows=final_rows, waiting_time_accepted=True),
            "final-accepted.json",
        )
    )
    assert compare(baseline, accepted, manifest).waiting_time_passed is True


def test_shared_setup_waiting_is_counted_once_in_the_total(tmp_path: Path) -> None:
    """A Document ingestion is charged once per condition, never to a statement row."""
    manifest = _approved(tmp_path, ["R-1", "R-2"])
    baseline_payload = _document(
        rows=[_row("R-1", "hold", waiting_seconds=10), _row("R-2", "hold", waiting_seconds=10)]
    )
    baseline_payload["setup_waiting_seconds"] = 1800
    final_payload = _document(
        condition="final",
        rows=[_row("R-1", "usable", waiting_seconds=10), _row("R-2", "usable", waiting_seconds=10)],
    )
    final_payload["setup_waiting_seconds"] = 1800
    baseline = load_condition_result(_write(tmp_path, baseline_payload, "b.json"))
    final = load_condition_result(_write(tmp_path, final_payload, "f.json"))
    baseline_measures = measure(baseline)
    final_measures = measure(final)
    assert baseline_measures.waiting_seconds == 20
    assert baseline_measures.setup_waiting_seconds == 1800
    assert baseline_measures.total_waiting_seconds == 1820
    assert final_measures.total_waiting_seconds == 1820
    assert compare(baseline, final, manifest).waiting_time_passed is True


def test_waiting_increase_check_uses_the_setup_inclusive_total(tmp_path: Path) -> None:
    manifest = _approved(tmp_path, ["R-1"])
    baseline_payload = _document(rows=[_row("R-1", "usable", waiting_seconds=10)])
    baseline_payload["setup_waiting_seconds"] = 100
    final_payload = _document(
        condition="final", rows=[_row("R-1", "usable", waiting_seconds=10)]
    )
    final_payload["setup_waiting_seconds"] = 200
    baseline = load_condition_result(_write(tmp_path, baseline_payload, "b.json"))
    final = load_condition_result(_write(tmp_path, final_payload, "f.json"))
    assert compare(baseline, final, manifest).waiting_time_passed is False
