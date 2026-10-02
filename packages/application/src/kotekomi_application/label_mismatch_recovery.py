"""Label-mismatch recovery for the R12 deliverable.

R12 folds the one recoverable ``rejection_label_mismatch`` raw answer back into a
completed selection and re-measures it through the deterministic composer.

The recovery is token-only and deterministic: it keeps exactly the comma-separated
tokens that match one candidate label, drops every foreign token, and orders the
kept labels by task label order. It never reads free prose to remap a foreign
token, never invokes a model, and never writes canonical state.

Non-recoverable slots (``selected``, ``abstained``, ``rejection_empty``, and
``rejection_no_valid_label``) raise a typed halt and never enter recovery.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.decontextualization_composition import (
    DecontextualizationEntityRef,
    DecontextualizedProposition,
    build_decontextualized_proposition,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
)
from kotekomi_application.selection_failure_slot_routing import (
    SelectionFailureSlot,
    classify_selection_failure,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]


class LabelMismatchRecoveryHalt(ValueError):
    """Typed halt raised when a raw answer is not a recoverable label mismatch."""

    def __init__(self, slot: SelectionFailureSlot) -> None:
        self.slot = slot
        super().__init__(f"Label-mismatch recovery halted on slot: {slot.value}")


def _answer_tokens(raw_answer: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw_answer.split(",") if item.strip())


def recover_label_mismatch(
    *,
    raw_answer: str,
    task: ConstituentSelectionTask,
) -> ConstituentSelectionAnswer:
    """Rewrite one ``rejection_label_mismatch`` raw answer into a completed selection.

    The recovery confirms the slot before rewriting, keeps exactly the tokens that
    match one candidate label, drops every foreign token, and orders the kept labels
    by task label order with a one-based index per kept label.
    """
    diagnosis = classify_selection_failure(raw_answer=raw_answer, task=task)
    if diagnosis.slot is not SelectionFailureSlot.REJECTION_LABEL_MISMATCH:
        raise LabelMismatchRecoveryHalt(diagnosis.slot)

    tokens = _answer_tokens(raw_answer)
    labels = task.constituent_labels
    kept = tuple(label for label in labels if label in tokens)
    if not kept:
        raise ValueError("Label-mismatch recovery produced no valid candidate labels.")
    indexes = tuple(labels.index(label) + 1 for label in kept)
    return ConstituentSelectionAnswer(
        event_id=task.event_id,
        status=ConstituentSelectionStatus.SELECTED,
        selected_label_indexes=indexes,
    )


def remeasure_recovered_selection(
    *,
    recovered: ConstituentSelectionAnswer,
    source_text: str,
    source_text_sha256: str,
    inventory: ConstituentCandidateInventory,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
    entities: tuple[DecontextualizationEntityRef, ...],
) -> DecontextualizedProposition:
    """Run one recovered selection through the deterministic composer.

    The re-measure produces exactly one proposition or exactly one typed hold and
    never invokes a model or writes canonical state.
    """
    if recovered.status is not ConstituentSelectionStatus.SELECTED:
        raise ValueError("Re-measure requires one completed selection.")
    return build_decontextualized_proposition(
        event_id=recovered.event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        inventory=inventory,
        answer=recovered,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
        entities=entities,
    )


class LabelMismatchRecovery(BaseModel):
    """One Event's completed selection plus its re-measured result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    raw_answer_sha256: Annotated[str, Field(pattern=_SHA256)]
    completed_selection: ConstituentSelectionAnswer
    remeasured_result: DecontextualizedProposition

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.completed_selection.event_id != self.event_id:
            raise ValueError("Recovery completed selection references a different Event.")
        if self.completed_selection.status is not ConstituentSelectionStatus.SELECTED:
            raise ValueError("Recovery completed selection must book status selected.")
        if self.remeasured_result.event_id != self.event_id:
            raise ValueError("Recovery re-measured result references a different Event.")
        return self


def build_label_mismatch_recovery(
    *,
    recovered: ConstituentSelectionAnswer,
    raw_answer: str,
    remeasured: DecontextualizedProposition,
) -> LabelMismatchRecovery:
    """Assemble one recovery record binding the frozen answer, selection, and result."""
    return LabelMismatchRecovery(
        event_id=recovered.event_id,
        raw_answer_sha256=hashlib.sha256(raw_answer.encode()).hexdigest(),
        completed_selection=recovered,
        remeasured_result=remeasured,
    )


class LabelMismatchRecoveryReport(BaseModel):
    """Sealed R12 report: the ordered recovery set and zero-write safety."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    recoveries: tuple[LabelMismatchRecovery, ...]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.event_id for item in self.recoveries)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("R12 report recoveries must be ordered and distinct.")
        if (
            self.canonical_write_count != 0
            or self.proposed_change_count != 0
            or self.model_execution_count != 0
        ):
            raise ValueError("R12 report must record zero writes, proposals, and model executions.")
        return self


def label_mismatch_recovery_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one R12 report draft."""
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


def build_label_mismatch_recovery_report(
    *,
    recoveries: tuple[LabelMismatchRecovery, ...],
) -> LabelMismatchRecoveryReport:
    """Assemble and seal the R12 report with zero writes, proposals, and model executions."""
    draft = LabelMismatchRecoveryReport.model_construct(
        recoveries=recoveries,
        canonical_write_count=0,
        proposed_change_count=0,
        model_execution_count=0,
        result_fingerprint="0" * 64,
    )
    return LabelMismatchRecoveryReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=label_mismatch_recovery_report_fingerprint(draft),
    )
