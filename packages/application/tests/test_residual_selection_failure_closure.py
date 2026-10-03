"""Focused data-in/data-out tests for R15 residual selection-failure closure."""

from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    ConstituentSelectionTask,
    CorrectiveSelectionTask,
    ResidualClosureHalt,
    ResidualClosureReport,
    ResidualClosureRoute,
    ResidualClosureRouting,
    SelectionFailureSlot,
    build_corrective_selection_task,
    build_residual_closure_report,
    closure_route_for_slot,
    corrective_instruction_for,
    residual_closure_report_fingerprint,
    route_residual_selection_failure,
    route_residual_selection_failure_set,
    validate_closure_set_alignment,
)
from pydantic import ValidationError


def _task(event_id: str, labels: tuple[str, ...]) -> ConstituentSelectionTask:
    source_text = "Anthropic supplied compute to Stargate."
    rendered = (
        "Return a comma-separated subset of the Candidate labels, or NONE.\n"
        "Event: supplied\n"
        "Passage:\n"
        f"{source_text}\n"
        "Candidates:\n" + "\n".join(f"{label}: sample" for label in labels)
    )
    return ConstituentSelectionTask(
        event_id=event_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        source_text=source_text,
        constituent_labels=labels,
        rendered_input=rendered,
        rendered_input_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
    )


def _labels(count: int) -> tuple[str, ...]:
    return tuple(f"C{ordinal}" for ordinal in range(1, count + 1))


def test_closure_route_for_slot_maps_the_two_unrecovered_slots() -> None:
    assert (
        closure_route_for_slot(SelectionFailureSlot.REJECTION_NO_VALID_LABEL)
        is ResidualClosureRoute.LABEL_ONLY_RESELECTION
    )
    assert (
        closure_route_for_slot(SelectionFailureSlot.ABSTAINED)
        is ResidualClosureRoute.BEST_CHOICE_RESELECTION
    )


def test_rejection_no_valid_label_routes_label_only_reselection() -> None:
    routing = route_residual_selection_failure(
        raw_answer="Sacks, Amodei's decision",
        task=_task("AHE-022", _labels(3)),
    )
    assert routing.slot is SelectionFailureSlot.REJECTION_NO_VALID_LABEL
    assert routing.closure_route is ResidualClosureRoute.LABEL_ONLY_RESELECTION


def test_abstained_routes_best_choice_reselection() -> None:
    routing = route_residual_selection_failure(raw_answer="NONE", task=_task("AHE-051", _labels(3)))
    assert routing.slot is SelectionFailureSlot.ABSTAINED
    assert routing.closure_route is ResidualClosureRoute.BEST_CHOICE_RESELECTION


def test_recoverable_slot_raises_typed_halt() -> None:
    with pytest.raises(ResidualClosureHalt):
        route_residual_selection_failure(raw_answer="C1, E2", task=_task("AHE-004", _labels(3)))


def test_selected_slot_raises_typed_halt() -> None:
    with pytest.raises(ResidualClosureHalt):
        route_residual_selection_failure(raw_answer="C1", task=_task("AHE-004", _labels(3)))


def test_empty_rejection_raises_typed_halt() -> None:
    with pytest.raises(ResidualClosureHalt):
        route_residual_selection_failure(raw_answer="", task=_task("AHE-004", _labels(3)))


def test_corrective_instruction_replaces_only_the_first_line() -> None:
    task = _task("AHE-022", _labels(2))
    corrective = build_corrective_selection_task(
        task=task, route=ResidualClosureRoute.LABEL_ONLY_RESELECTION
    )
    _, _, body = task.rendered_input.partition("\n")
    assert corrective.corrected_prompt == f"{corrective.corrected_instruction}\n{body}"
    assert corrective.corrected_prompt.endswith(body)


def test_corrected_prompt_digest_matches_text() -> None:
    corrective = build_corrective_selection_task(
        task=_task("AHE-022", _labels(2)),
        route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
    )
    assert (
        corrective.corrected_prompt_sha256
        == hashlib.sha256(corrective.corrected_prompt.encode()).hexdigest()
    )


def test_corrective_task_keeps_original_rendered_input_digest() -> None:
    task = _task("AHE-022", _labels(2))
    corrective = build_corrective_selection_task(
        task=task, route=ResidualClosureRoute.LABEL_ONLY_RESELECTION
    )
    assert corrective.original_rendered_input_sha256 == task.rendered_input_sha256


def test_label_only_instruction_demands_labels_and_forbids_text() -> None:
    instruction = corrective_instruction_for(ResidualClosureRoute.LABEL_ONLY_RESELECTION)
    assert "Candidate labels" in instruction
    assert "Do not write candidate text" in instruction


def test_best_choice_instruction_demands_one_label_or_none() -> None:
    instruction = corrective_instruction_for(ResidualClosureRoute.BEST_CHOICE_RESELECTION)
    assert "exactly one Candidate label" in instruction
    assert "NONE" in instruction


def test_corrective_task_differs_by_route() -> None:
    task = _task("AHE-022", _labels(2))
    label_only = build_corrective_selection_task(
        task=task, route=ResidualClosureRoute.LABEL_ONLY_RESELECTION
    )
    best_choice = build_corrective_selection_task(
        task=task, route=ResidualClosureRoute.BEST_CHOICE_RESELECTION
    )
    assert label_only.corrected_prompt != best_choice.corrected_prompt
    assert label_only.corrected_prompt_sha256 != best_choice.corrected_prompt_sha256


def _both_routings() -> tuple[ResidualClosureRouting, ...]:
    tasks = {
        "AHE-022": _task("AHE-022", _labels(3)),
        "AHE-051": _task("AHE-051", _labels(3)),
    }
    return route_residual_selection_failure_set(
        raw_answers={"AHE-022": "Sacks, prose", "AHE-051": "NONE"},
        tasks_by_event=tasks,
    )


def test_closure_set_is_ordered_and_equals_residual_set() -> None:
    routings = _both_routings()
    assert tuple(item.event_id for item in routings) == ("AHE-022", "AHE-051")
    assert tuple(item.closure_route for item in routings) == (
        ResidualClosureRoute.LABEL_ONLY_RESELECTION,
        ResidualClosureRoute.BEST_CHOICE_RESELECTION,
    )
    assert (
        validate_closure_set_alignment(routings=routings, residual_event_ids=("AHE-022", "AHE-051"))
        == routings
    )


def test_closure_set_alignment_rejects_drift() -> None:
    routings = route_residual_selection_failure_set(
        raw_answers={"AHE-051": "NONE"},
        tasks_by_event={"AHE-051": _task("AHE-051", _labels(3))},
    )
    with pytest.raises(ValueError):
        validate_closure_set_alignment(routings=routings, residual_event_ids=("AHE-022", "AHE-051"))


def test_closure_set_requires_exact_coverage() -> None:
    with pytest.raises(ValueError):
        route_residual_selection_failure_set(
            raw_answers={"AHE-051": "NONE"},
            tasks_by_event={
                "AHE-051": _task("AHE-051", _labels(3)),
                "AHE-022": _task("AHE-022", _labels(3)),
            },
        )


def test_report_records_zero_writes_and_seals_fingerprint() -> None:
    report = build_residual_closure_report(items=_both_routings())
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == residual_closure_report_fingerprint(report)


def test_report_fingerprint_changes_when_items_change() -> None:
    report_both = build_residual_closure_report(items=_both_routings())
    only = route_residual_selection_failure_set(
        raw_answers={"AHE-051": "NONE"},
        tasks_by_event={"AHE-051": _task("AHE-051", _labels(3))},
    )
    report_one = build_residual_closure_report(items=only)
    assert report_both.result_fingerprint != report_one.result_fingerprint


def test_report_items_must_be_distinct_and_ordered() -> None:
    routing = route_residual_selection_failure(raw_answer="NONE", task=_task("AHE-051", _labels(3)))
    with pytest.raises(ValidationError):
        ResidualClosureReport(
            items=(routing, routing),
            canonical_write_count=0,
            proposed_change_count=0,
            model_execution_count=0,
            result_fingerprint="0" * 64,
        )


def test_corrective_task_rejects_a_mismatched_digest() -> None:
    with pytest.raises(ValidationError):
        CorrectiveSelectionTask(
            event_id="AHE-022",
            closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
            corrected_instruction=corrective_instruction_for(
                ResidualClosureRoute.LABEL_ONLY_RESELECTION
            ),
            corrected_prompt="wrong prompt",
            corrected_prompt_sha256="0" * 64,
            original_rendered_input_sha256="1" * 64,
        )
