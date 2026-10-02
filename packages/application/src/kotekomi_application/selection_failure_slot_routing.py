"""Selection-failure slot routing for the R11 deliverable.

R11 classifies each frozen run-005 residual selection answer into one closed
selection-failure slot, marks a label-mismatch rejection recoverable, and seals
one zero-write report.

The closed slots are ``selected``, ``abstained``, ``rejection_empty``,
``rejection_no_valid_label``, and ``rejection_label_mismatch``.  Only
``rejection_label_mismatch`` is recoverable.

Nothing here invokes a model, writes canonical state, or reads a held-out
partition.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]


class SelectionFailureSlot(StrEnum):
    """One closed selection-failure slot over a frozen raw answer."""

    SELECTED = "selected"
    ABSTAINED = "abstained"
    REJECTION_EMPTY = "rejection_empty"
    REJECTION_NO_VALID_LABEL = "rejection_no_valid_label"
    REJECTION_LABEL_MISMATCH = "rejection_label_mismatch"


_REJECTION_SLOTS = frozenset(
    {
        SelectionFailureSlot.REJECTION_EMPTY,
        SelectionFailureSlot.REJECTION_NO_VALID_LABEL,
        SelectionFailureSlot.REJECTION_LABEL_MISMATCH,
    }
)


def selection_failure_recoverable(slot: SelectionFailureSlot) -> bool:
    """Return the recoverability marker: true only for a label-mismatch rejection."""
    return slot == SelectionFailureSlot.REJECTION_LABEL_MISMATCH


def selection_failure_slot_status(slot: SelectionFailureSlot) -> ConstituentSelectionStatus:
    """Map one selection-failure slot to the Constituent Selection Answer status it books."""
    if slot is SelectionFailureSlot.SELECTED:
        return ConstituentSelectionStatus.SELECTED
    if slot is SelectionFailureSlot.ABSTAINED:
        return ConstituentSelectionStatus.NONE
    if slot in _REJECTION_SLOTS:
        return ConstituentSelectionStatus.REJECTED
    raise ValueError(f"Unsupported selection-failure slot: {slot}")


def _answer_tokens(raw_answer: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw_answer.split(",") if item.strip())


def _slot_from_tokens(
    *,
    tokens: tuple[str, ...],
    valid_labels: frozenset[str],
) -> SelectionFailureSlot:
    if tokens == ("NONE",):
        return SelectionFailureSlot.ABSTAINED
    if not tokens:
        return SelectionFailureSlot.REJECTION_EMPTY
    has_valid = any(token in valid_labels for token in tokens)
    has_invalid = any(token not in valid_labels for token in tokens)
    if has_valid and has_invalid:
        return SelectionFailureSlot.REJECTION_LABEL_MISMATCH
    if not has_valid:
        return SelectionFailureSlot.REJECTION_NO_VALID_LABEL
    return SelectionFailureSlot.SELECTED


class SelectionFailureDiagnosis(BaseModel):
    """One Event's selection-failure slot plus a recoverability marker."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    raw_answer_sha256: Annotated[str, Field(pattern=_SHA256)]
    slot: SelectionFailureSlot
    recoverable: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.recoverable is not selection_failure_recoverable(self.slot):
            raise ValueError("Diagnosis recoverable marker does not match its slot.")
        return self


def classify_selection_failure(
    *,
    raw_answer: str,
    task: ConstituentSelectionTask,
) -> SelectionFailureDiagnosis:
    """Classify one frozen raw selection answer into one closed slot."""
    slot = _slot_from_tokens(
        tokens=_answer_tokens(raw_answer),
        valid_labels=frozenset(task.constituent_labels),
    )
    return SelectionFailureDiagnosis(
        event_id=task.event_id,
        raw_answer_sha256=hashlib.sha256(raw_answer.encode()).hexdigest(),
        slot=slot,
        recoverable=selection_failure_recoverable(slot),
    )


def classify_selection_failure_set(
    *,
    raw_answers: Mapping[str, str],
    tasks_by_event: Mapping[str, ConstituentSelectionTask],
) -> tuple[SelectionFailureDiagnosis, ...]:
    """Return one ordered diagnosis per answered Event."""
    if set(raw_answers) != set(tasks_by_event):
        raise ValueError("Selection-failure census requires one task per raw answer.")
    diagnoses: list[SelectionFailureDiagnosis] = []
    for event_id in sorted(raw_answers):
        task = tasks_by_event[event_id]
        if task.event_id != event_id:
            raise ValueError("Selection-failure census contains an Event ID mismatch.")
        diagnoses.append(classify_selection_failure(raw_answer=raw_answers[event_id], task=task))
    return tuple(diagnoses)


def validate_diagnosis_status(
    *,
    diagnosis: SelectionFailureDiagnosis,
    status: ConstituentSelectionStatus,
) -> SelectionFailureDiagnosis:
    """Reject a diagnosis whose slot disagrees with the frozen answer status."""
    if selection_failure_slot_status(diagnosis.slot) is not status:
        raise ValueError(
            f"Diagnosis slot {diagnosis.slot.value} disagrees with status {status.value}."
        )
    return diagnosis


def validate_diagnosis_set_alignment(
    *,
    diagnoses: tuple[SelectionFailureDiagnosis, ...],
    residual_event_ids: tuple[str, ...],
) -> tuple[SelectionFailureDiagnosis, ...]:
    """Reject a diagnosis set that drifts from the residual-review set."""
    ids = tuple(item.event_id for item in diagnoses)
    if ids != tuple(sorted(set(ids))):
        raise ValueError("Diagnosis set must be ordered and distinct.")
    if ids != tuple(sorted(residual_event_ids)):
        raise ValueError("Diagnosis set drifted from the residual-review set.")
    return diagnoses


class SelectionFailureReport(BaseModel):
    """Sealed R11 report: diagnosis set and zero-write safety."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    diagnoses: tuple[SelectionFailureDiagnosis, ...]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.event_id for item in self.diagnoses)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("Report diagnoses must be ordered and distinct.")
        if (
            self.canonical_write_count != 0
            or self.proposed_change_count != 0
            or self.model_execution_count != 0
        ):
            raise ValueError("R11 report must record zero writes, proposals, and model executions.")
        return self


def selection_failure_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one R11 report draft."""
    if isinstance(value, BaseModel):
        payload: object = value.model_dump(mode="json", exclude={"result_fingerprint"})
    else:
        payload = {key: item for key, item in value.items() if key != "result_fingerprint"}
    return hashlib.sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def build_selection_failure_report(
    *,
    diagnoses: tuple[SelectionFailureDiagnosis, ...],
) -> SelectionFailureReport:
    """Assemble and seal the R11 report with zero writes, proposals, and model executions."""
    draft = SelectionFailureReport.model_construct(
        diagnoses=diagnoses,
        canonical_write_count=0,
        proposed_change_count=0,
        model_execution_count=0,
        result_fingerprint="0" * 64,
    )
    return SelectionFailureReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=selection_failure_report_fingerprint(draft),
    )
