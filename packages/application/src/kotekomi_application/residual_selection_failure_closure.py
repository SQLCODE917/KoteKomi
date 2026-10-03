"""Residual selection-failure closure for the R15 deliverable.

R15 decides one closure route for each unrecovered selection-failure slot
(``rejection_no_valid_label`` and ``abstained``) and prepares one corrective
re-selection task per residual Event without invoking a model.

The closed closure routes are ``label_only_reselection`` and
``best_choice_reselection``.  ``rejection_no_valid_label`` maps to
``label_only_reselection`` because the model broke the label format;
``abstained`` maps to ``best_choice_reselection`` because the model answered
``NONE``.

Each corrective re-selection task keeps the frozen Event, Passage, and
Candidates body unchanged and swaps only the original selection instruction for
one closed corrective instruction.  The report seals one ordered residual set
with zero canonical writes, zero ProposedChanges, and zero model executions.

Nothing here invokes a model, writes canonical state, or reads a held-out
partition.  The corrective re-selection itself runs in the next deliverable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentSelectionTask,
)
from kotekomi_application.selection_failure_slot_routing import (
    SelectionFailureSlot,
    classify_selection_failure,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]


class ResidualClosureRoute(StrEnum):
    """One closed closure route per unrecovered selection failure."""

    LABEL_ONLY_RESELECTION = "label_only_reselection"
    BEST_CHOICE_RESELECTION = "best_choice_reselection"


_CORRECTIVE_INSTRUCTIONS: dict[ResidualClosureRoute, str] = {
    ResidualClosureRoute.LABEL_ONLY_RESELECTION: (
        "Return ONLY a comma-separated list of Candidate labels, for example C1 or C3. "
        "Do not write candidate text. Do not explain."
    ),
    ResidualClosureRoute.BEST_CHOICE_RESELECTION: (
        "Return exactly one Candidate label for the single best candidate. Answer NONE "
        "only when no candidate fits. Do not add other text."
    ),
}


class ResidualClosureHalt(ValueError):
    """Typed halt raised when a slot is not an unrecovered selection failure."""

    def __init__(self, slot: SelectionFailureSlot) -> None:
        self.slot = slot
        super().__init__(f"Residual selection-failure closure halted on slot: {slot.value}")


def closure_route_for_slot(slot: SelectionFailureSlot) -> ResidualClosureRoute:
    """Map one unrecovered selection-failure slot to one closure route."""
    if slot is SelectionFailureSlot.REJECTION_NO_VALID_LABEL:
        return ResidualClosureRoute.LABEL_ONLY_RESELECTION
    if slot is SelectionFailureSlot.ABSTAINED:
        return ResidualClosureRoute.BEST_CHOICE_RESELECTION
    raise ResidualClosureHalt(slot)


def corrective_instruction_for(route: ResidualClosureRoute) -> str:
    """Return the closed corrective instruction for one closure route."""
    return _CORRECTIVE_INSTRUCTIONS[route]


def _corrected_prompt(*, task: ConstituentSelectionTask, route: ResidualClosureRoute) -> str:
    """Swap the original selection instruction for the corrective instruction."""
    _, separator, body = task.rendered_input.partition("\n")
    if not separator:
        raise ValueError("Corrective re-selection requires a newline-delimited task body.")
    return f"{corrective_instruction_for(route)}\n{body}"


class CorrectiveSelectionTask(BaseModel):
    """One corrected re-selection prompt plus provenance digests."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    closure_route: ResidualClosureRoute
    corrected_instruction: Annotated[str, Field(min_length=1)]
    corrected_prompt: Annotated[str, Field(min_length=1)]
    corrected_prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    original_rendered_input_sha256: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            hashlib.sha256(self.corrected_prompt.encode()).hexdigest()
            != self.corrected_prompt_sha256
        ):
            raise ValueError("Corrective task corrected-prompt digest does not match.")
        if not self.corrected_prompt.startswith(self.corrected_instruction):
            raise ValueError("Corrective prompt must begin with the corrective instruction.")
        if self.corrected_instruction != corrective_instruction_for(self.closure_route):
            raise ValueError("Corrective instruction disagrees with the closure route.")
        return self


def build_corrective_selection_task(
    *,
    task: ConstituentSelectionTask,
    route: ResidualClosureRoute,
) -> CorrectiveSelectionTask:
    """Build one corrective re-selection task from one frozen selection task."""
    instruction = corrective_instruction_for(route)
    corrected = _corrected_prompt(task=task, route=route)
    return CorrectiveSelectionTask(
        event_id=task.event_id,
        closure_route=route,
        corrected_instruction=instruction,
        corrected_prompt=corrected,
        corrected_prompt_sha256=hashlib.sha256(corrected.encode()).hexdigest(),
        original_rendered_input_sha256=task.rendered_input_sha256,
    )


class ResidualClosureRouting(BaseModel):
    """One Event's closure route, corrective task, and frozen answer digest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    slot: SelectionFailureSlot
    raw_answer_sha256: Annotated[str, Field(pattern=_SHA256)]
    closure_route: ResidualClosureRoute
    corrective_task: CorrectiveSelectionTask

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.corrective_task.event_id != self.event_id:
            raise ValueError("Corrective task references a different Event.")
        if self.corrective_task.closure_route is not self.closure_route:
            raise ValueError("Corrective task route disagrees with the routing route.")
        return self


def route_residual_selection_failure(
    *,
    raw_answer: str,
    task: ConstituentSelectionTask,
) -> ResidualClosureRouting:
    """Decide one closure route and prepare one corrective task per residual Event."""
    diagnosis = classify_selection_failure(raw_answer=raw_answer, task=task)
    route = closure_route_for_slot(diagnosis.slot)
    return ResidualClosureRouting(
        event_id=task.event_id,
        slot=diagnosis.slot,
        raw_answer_sha256=hashlib.sha256(raw_answer.encode()).hexdigest(),
        closure_route=route,
        corrective_task=build_corrective_selection_task(task=task, route=route),
    )


def route_residual_selection_failure_set(
    *,
    raw_answers: Mapping[str, str],
    tasks_by_event: Mapping[str, ConstituentSelectionTask],
) -> tuple[ResidualClosureRouting, ...]:
    """Return one ordered closure routing per covered residual Event."""
    events = tuple(sorted(raw_answers))
    if set(events) != set(tasks_by_event):
        raise ValueError("Residual closure routing requires one task per answered Event.")
    for event_id in events:
        if tasks_by_event[event_id].event_id != event_id:
            raise ValueError("Residual closure routing contains an Event ID mismatch.")
    return tuple(
        route_residual_selection_failure(
            raw_answer=raw_answers[event_id],
            task=tasks_by_event[event_id],
        )
        for event_id in events
    )


def validate_closure_set_alignment(
    *,
    routings: tuple[ResidualClosureRouting, ...],
    residual_event_ids: tuple[str, ...],
) -> tuple[ResidualClosureRouting, ...]:
    """Reject a closure set that drifts from the residual-review set."""
    ids = tuple(item.event_id for item in routings)
    if ids != tuple(sorted(set(ids))):
        raise ValueError("Residual closure set must be ordered and distinct.")
    if ids != tuple(sorted(residual_event_ids)):
        raise ValueError("Residual closure set drifted from the residual-review set.")
    return routings


class ResidualClosureReport(BaseModel):
    """Sealed R15 report: the ordered closure set and zero-write safety."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    items: tuple[ResidualClosureRouting, ...]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.event_id for item in self.items)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("R15 report items must be ordered and distinct.")
        if (
            self.canonical_write_count != 0
            or self.proposed_change_count != 0
            or self.model_execution_count != 0
        ):
            raise ValueError("R15 report must record zero writes, proposals, and model executions.")
        return self


def residual_closure_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one R15 report draft."""
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


def build_residual_closure_report(
    *,
    items: tuple[ResidualClosureRouting, ...],
) -> ResidualClosureReport:
    """Assemble and seal the R15 report with zero writes, proposals, and model executions."""
    draft = ResidualClosureReport.model_construct(
        items=items,
        canonical_write_count=0,
        proposed_change_count=0,
        model_execution_count=0,
        result_fingerprint="0" * 64,
    )
    return ResidualClosureReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=residual_closure_report_fingerprint(draft),
    )
