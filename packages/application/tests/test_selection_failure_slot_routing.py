"""Focused data-in/data-out tests for R11 selection-failure slot routing."""

from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
    SelectionFailureDiagnosis,
    SelectionFailureSlot,
    build_selection_failure_report,
    classify_selection_failure,
    classify_selection_failure_set,
    parse_constituent_selection_answer,
    selection_failure_recoverable,
    selection_failure_report_fingerprint,
    selection_failure_slot_status,
    validate_diagnosis_set_alignment,
    validate_diagnosis_status,
)
from pydantic import ValidationError


def _task(event_id: str, labels: tuple[str, ...]) -> ConstituentSelectionTask:
    source_text = "candidate source text"
    rendered = "Event: test\nCandidates:\n" + "\n".join(f"{label}: sample" for label in labels)
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


def _diagnosis(raw_answer: str, event_id: str = "AHE-004") -> SelectionFailureDiagnosis:
    return classify_selection_failure(raw_answer=raw_answer, task=_task(event_id, _labels(3)))


def _status(raw_answer: str, event_id: str = "AHE-004") -> ConstituentSelectionStatus:
    return parse_constituent_selection_answer(
        raw_answer=raw_answer, task=_task(event_id, _labels(3))
    ).status


def test_all_valid_tokens_map_to_selected() -> None:
    diagnosis = _diagnosis("C1, C3")
    assert diagnosis.slot is SelectionFailureSlot.SELECTED
    assert diagnosis.recoverable is False


def test_none_raw_answer_maps_to_abstained() -> None:
    diagnosis = _diagnosis("NONE")
    assert diagnosis.slot is SelectionFailureSlot.ABSTAINED
    assert diagnosis.recoverable is False


def test_empty_raw_answer_maps_to_rejection_empty() -> None:
    diagnosis = _diagnosis("")
    assert diagnosis.slot is SelectionFailureSlot.REJECTION_EMPTY
    assert diagnosis.recoverable is False


def test_whitespace_only_raw_answer_maps_to_rejection_empty() -> None:
    diagnosis = _diagnosis(" ,  ")
    assert diagnosis.slot is SelectionFailureSlot.REJECTION_EMPTY


def test_zero_valid_label_maps_to_rejection_no_valid_label() -> None:
    diagnosis = _diagnosis("Sacks, Amodei's decision")
    assert diagnosis.slot is SelectionFailureSlot.REJECTION_NO_VALID_LABEL
    assert diagnosis.recoverable is False


def test_mixed_valid_and_invalid_maps_to_rejection_label_mismatch() -> None:
    diagnosis = _diagnosis("C1, E2")
    assert diagnosis.slot is SelectionFailureSlot.REJECTION_LABEL_MISMATCH
    assert diagnosis.recoverable is True


def test_recoverable_true_only_for_label_mismatch() -> None:
    assert selection_failure_recoverable(SelectionFailureSlot.REJECTION_LABEL_MISMATCH) is True
    for slot in (
        SelectionFailureSlot.SELECTED,
        SelectionFailureSlot.ABSTAINED,
        SelectionFailureSlot.REJECTION_EMPTY,
        SelectionFailureSlot.REJECTION_NO_VALID_LABEL,
    ):
        assert selection_failure_recoverable(slot) is False


def test_diagnosis_rejects_mismatched_recoverable_marker() -> None:
    with pytest.raises(ValidationError):
        SelectionFailureDiagnosis(
            event_id="AHE-004",
            raw_answer_sha256="a" * 64,
            slot=SelectionFailureSlot.REJECTION_LABEL_MISMATCH,
            recoverable=False,
        )


def test_slot_status_mapping() -> None:
    assert (
        selection_failure_slot_status(SelectionFailureSlot.SELECTED)
        is ConstituentSelectionStatus.SELECTED
    )
    assert (
        selection_failure_slot_status(SelectionFailureSlot.ABSTAINED)
        is ConstituentSelectionStatus.NONE
    )
    assert (
        selection_failure_slot_status(SelectionFailureSlot.REJECTION_EMPTY)
        is ConstituentSelectionStatus.REJECTED
    )
    assert (
        selection_failure_slot_status(SelectionFailureSlot.REJECTION_NO_VALID_LABEL)
        is ConstituentSelectionStatus.REJECTED
    )
    assert (
        selection_failure_slot_status(SelectionFailureSlot.REJECTION_LABEL_MISMATCH)
        is ConstituentSelectionStatus.REJECTED
    )


def test_diagnosis_slot_agrees_with_frozen_status() -> None:
    for raw_answer in ("C1", "C1, C3", "NONE", "", "Sacks, Amodei's decision", "C1, E2"):
        diagnosis = _diagnosis(raw_answer)
        status = _status(raw_answer)
        assert selection_failure_slot_status(diagnosis.slot) is status
        assert validate_diagnosis_status(diagnosis=diagnosis, status=status) == diagnosis


def test_validate_diagnosis_status_rejects_disagreement() -> None:
    diagnosis = _diagnosis("NONE")
    with pytest.raises(ValueError):
        validate_diagnosis_status(diagnosis=diagnosis, status=ConstituentSelectionStatus.REJECTED)


def test_diagnosis_set_is_ordered_and_equals_residual_review_set() -> None:
    raw_answers = {"AHE-051": "NONE", "AHE-004": "C1, E2", "AHE-022": "Sacks, prose"}
    tasks = {event_id: _task(event_id, _labels(3)) for event_id in raw_answers}
    diagnoses = classify_selection_failure_set(raw_answers=raw_answers, tasks_by_event=tasks)
    assert tuple(item.event_id for item in diagnoses) == ("AHE-004", "AHE-022", "AHE-051")
    assert tuple(item.slot for item in diagnoses) == (
        SelectionFailureSlot.REJECTION_LABEL_MISMATCH,
        SelectionFailureSlot.REJECTION_NO_VALID_LABEL,
        SelectionFailureSlot.ABSTAINED,
    )
    assert (
        validate_diagnosis_set_alignment(
            diagnoses=diagnoses,
            residual_event_ids=("AHE-004", "AHE-022", "AHE-051"),
        )
        == diagnoses
    )


def test_validate_diagnosis_set_alignment_rejects_drift() -> None:
    diagnoses = classify_selection_failure_set(
        raw_answers={"AHE-004": "C1, E2"},
        tasks_by_event={"AHE-004": _task("AHE-004", _labels(3))},
    )
    with pytest.raises(ValueError):
        validate_diagnosis_set_alignment(
            diagnoses=diagnoses, residual_event_ids=("AHE-004", "AHE-022")
        )


def test_classify_set_requires_exact_coverage() -> None:
    with pytest.raises(ValueError):
        classify_selection_failure_set(
            raw_answers={"AHE-004": "NONE"},
            tasks_by_event={
                "AHE-004": _task("AHE-004", _labels(3)),
                "AHE-022": _task("AHE-022", _labels(3)),
            },
        )


def test_report_records_zero_writes_and_seals_fingerprint() -> None:
    tasks = {
        "AHE-004": _task("AHE-004", _labels(3)),
        "AHE-022": _task("AHE-022", _labels(3)),
        "AHE-051": _task("AHE-051", _labels(3)),
    }
    diagnoses = classify_selection_failure_set(
        raw_answers={"AHE-004": "C1, E2", "AHE-022": "Sacks, prose", "AHE-051": "NONE"},
        tasks_by_event=tasks,
    )
    report = build_selection_failure_report(diagnoses=diagnoses)
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == selection_failure_report_fingerprint(report)


def test_report_fingerprint_changes_when_one_diagnosis_changes() -> None:
    report_a = build_selection_failure_report(
        diagnoses=classify_selection_failure_set(
            raw_answers={"AHE-004": "C1, E2"},
            tasks_by_event={"AHE-004": _task("AHE-004", _labels(3))},
        )
    )
    report_b = build_selection_failure_report(
        diagnoses=classify_selection_failure_set(
            raw_answers={"AHE-004": "NONE"},
            tasks_by_event={"AHE-004": _task("AHE-004", _labels(3))},
        )
    )
    assert report_a.result_fingerprint != report_b.result_fingerprint
