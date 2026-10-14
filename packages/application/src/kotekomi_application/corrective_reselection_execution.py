"""Corrective re-selection execution for the R16 deliverable.

R16 executes the two R15 corrective re-selection tasks once against the local
LM Studio runtime, applies the closure route's strict answer grammar, and
re-measures each selected answer through the deterministic composer.

The label-only route (``AHE-022``) accepts one or more distinct Candidate labels
separated by commas.  The best-choice route (``AHE-051``) accepts exactly one
Candidate label or the exact uppercase token ``NONE``.  Every foreign label,
duplicate label, empty element, lowercase label, mixed label with ``NONE``,
Markdown fence, explanation, internal newline, or other non-grammar character is
rejected without repair and archived unchanged.

Nothing here writes canonical Ledger state or a ProposedChange.  Every
deterministic invariant failure halts before a model call; only model-runtime
errors and blocked admissions become terminal execution items.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self, cast

from kotekomi_domain import ModelInputAdmissionStatus
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.decontextualization_composition import (
    DecontextualizationEntityRef,
    DecontextualizationStatus,
    DecontextualizedProposition,
    build_decontextualized_proposition,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.model_runtime import ModelRuntimeError
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
)
from kotekomi_application.residual_selection_failure_closure import ResidualClosureRoute
from kotekomi_application.staged_model_extraction import (
    ExecutionSetting,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelInputAdmissionRequest,
    ModelTaskRequest,
    ModelTaskRuntime,
    admit_model_input,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
    model_execution_spec_payload,
    model_identity_snapshot_digest,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]
_AttemptId = Annotated[str, Field(pattern=r"^atc_[a-f0-9]{24}$")]
_LABEL = re.compile(r"^C[1-9][0-9]*$")
_ASCII_WHITESPACE = " \t\n\r\v\f"
_ASCII_SPACE_OR_TAB = " \t"


class ExecutionAttemptStatus(StrEnum):
    """Lifecycle state of one corrective re-selection attempt."""

    PREPARED = "prepared"
    RUNNING = "running"
    ANSWERED = "answered"
    INPUT_BLOCKED = "input_blocked"
    RUNTIME_FAILED = "runtime_failed"


class CorrectiveReselectionOutcome(StrEnum):
    """Terminal outcome recorded for one Event in the sealed report."""

    SELECTED_PROPOSITION = "selected_proposition"
    SELECTED_HOLD = "selected_hold"
    REJECTED = "rejected"
    ABSTAINED = "abstained"
    INPUT_BLOCKED = "input_blocked"
    RUNTIME_FAILED = "runtime_failed"


def _rejected(event_id: str) -> ConstituentSelectionAnswer:
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=ConstituentSelectionStatus.REJECTED,
        selected_label_indexes=(),
    )


def _none(event_id: str) -> ConstituentSelectionAnswer:
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=ConstituentSelectionStatus.NONE,
        selected_label_indexes=(),
    )


def _selected(event_id: str, indexes: tuple[int, ...]) -> ConstituentSelectionAnswer:
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=ConstituentSelectionStatus.SELECTED,
        selected_label_indexes=tuple(sorted(indexes)),
    )


def parse_label_only_reselection_answer(
    raw_answer: str,
    task: ConstituentSelectionTask,
) -> ConstituentSelectionAnswer:
    """Parse one corrected label-only answer under the strict R16 grammar.

    The answer strips outer ASCII whitespace, accepts one or more distinct
    Candidate labels separated by commas, and permits ASCII spaces and tabs
    around the commas.  ``NONE``, foreign labels, duplicates, empty elements,
    and non-grammar characters reject the answer.
    """
    text = raw_answer.strip(_ASCII_WHITESPACE)
    if not text:
        return _rejected(task.event_id)
    elements = [element.strip(_ASCII_SPACE_OR_TAB) for element in text.split(",")]
    if any(element == "" for element in elements):
        return _rejected(task.event_id)
    if any(_LABEL.fullmatch(element) is None for element in elements):
        return _rejected(task.event_id)
    if len(set(elements)) != len(elements):
        return _rejected(task.event_id)
    unknown = [element for element in elements if element not in task.constituent_labels]
    if unknown:
        return _rejected(task.event_id)
    return _selected(
        task.event_id,
        tuple(task.constituent_labels.index(element) + 1 for element in elements),
    )


def parse_best_choice_reselection_answer(
    raw_answer: str,
    task: ConstituentSelectionTask,
) -> ConstituentSelectionAnswer:
    """Parse one corrected best-choice answer under the strict R16 grammar.

    The answer strips outer ASCII whitespace and accepts exactly one Candidate
    label or the exact uppercase token ``NONE``.  Everything else, including a
    mixed label with ``NONE``, rejects the answer.
    """
    text = raw_answer.strip(_ASCII_WHITESPACE)
    if text == "NONE":
        return _none(task.event_id)
    if _LABEL.fullmatch(text) is not None and text in task.constituent_labels:
        return _selected(task.event_id, (task.constituent_labels.index(text) + 1,))
    return _rejected(task.event_id)


def parse_corrective_reselection_answer(
    raw_answer: str,
    task: ConstituentSelectionTask,
    route: ResidualClosureRoute,
) -> ConstituentSelectionAnswer:
    """Dispatch one corrected answer through the route's strict grammar."""
    if route is ResidualClosureRoute.LABEL_ONLY_RESELECTION:
        return parse_label_only_reselection_answer(raw_answer, task)
    if route is ResidualClosureRoute.BEST_CHOICE_RESELECTION:
        return parse_best_choice_reselection_answer(raw_answer, task)
    raise ValueError(f"Unsupported corrective re-selection route: {route}")


def compose_corrective_reselection_answer(
    *,
    answer: ConstituentSelectionAnswer,
    source_text: str,
    source_text_sha256: str,
    inventory: ConstituentCandidateInventory,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
    entities: tuple[DecontextualizationEntityRef, ...],
) -> DecontextualizedProposition | None:
    """Compose one selected answer, or return ``None`` for a non-selected answer."""
    if answer.status is not ConstituentSelectionStatus.SELECTED:
        return None
    return build_decontextualized_proposition(
        event_id=answer.event_id,
        source_text=source_text,
        source_text_sha256=source_text_sha256,
        inventory=inventory,
        answer=answer,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
        tokens=tokens,
        entities=entities,
    )


def _receipt_payload(receipt: ModelExecutionReceipt) -> dict[str, JsonValue]:
    return {
        "model_identity_digest": receipt.model_identity_digest,
        "generation_parameters_digest": receipt.generation_parameters_digest,
        "rendered_input_digest": receipt.rendered_input_digest,
        "input_token_count": receipt.input_token_count,
        "output_token_count": receipt.output_token_count,
        "output_token_probabilities": [
            {
                "position": item.position,
                "token": item.token,
                "log_probability": item.log_probability,
                "token_bytes": list(item.token_bytes),
                "alternatives": [
                    {
                        "token": alternative.token,
                        "log_probability": alternative.log_probability,
                        "token_bytes": list(alternative.token_bytes),
                    }
                    for alternative in item.alternatives
                ],
            }
            for item in receipt.output_token_probabilities
        ],
    }


class CorrectiveReselectionAttempt(BaseModel):
    """One persisted corrective re-selection attempt before its terminal result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    attempt_id: _AttemptId
    event_id: _EventId
    closure_route: ResidualClosureRoute
    status: ExecutionAttemptStatus
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    model_profile_id: Annotated[str, Field(min_length=1)]
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    generation_parameters_digest: Annotated[str, Field(pattern=_SHA256)]
    rendered_input_digest: Annotated[str, Field(pattern=_SHA256)]
    admission: dict[str, JsonValue] | None = None
    execution_spec: dict[str, JsonValue] | None = None
    error: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.model_run_id.startswith("mrn_"):
            raise ValueError("Corrective re-selection attempt requires a ModelRun ID.")
        if not self.extraction_task_id.startswith("ext_"):
            raise ValueError("Corrective re-selection attempt requires an ExtractionTask ID.")
        if self.status is ExecutionAttemptStatus.PREPARED:
            if (
                self.admission is not None
                or self.execution_spec is not None
                or self.error is not None
            ):
                raise ValueError(
                    "A prepared attempt carries no admission, execution spec, or error."
                )
        elif self.status is ExecutionAttemptStatus.RUNNING:
            if self.error is not None:
                raise ValueError("A running attempt cannot carry an error.")
            if self.admission is None or self.execution_spec is None:
                raise ValueError("A running attempt requires admission and its execution spec.")
        elif self.status is ExecutionAttemptStatus.ANSWERED:
            if self.error is not None:
                raise ValueError("An answered attempt cannot carry an error.")
            if self.admission is None or self.execution_spec is None:
                raise ValueError("An answered attempt requires admission and its execution spec.")
        elif self.status is ExecutionAttemptStatus.INPUT_BLOCKED:
            if self.error is None:
                raise ValueError("An input-blocked attempt requires a blocked-reason error.")
            if self.admission is None:
                raise ValueError("An input-blocked attempt requires its blocked admission.")
            if self.execution_spec is not None:
                raise ValueError("An input-blocked attempt carries no execution spec.")
        elif self.status is ExecutionAttemptStatus.RUNTIME_FAILED:
            if self.error is None:
                raise ValueError("A runtime-failed attempt requires an error.")
            if (self.admission is None) != (self.execution_spec is None):
                raise ValueError(
                    "A runtime-failed attempt carries admission and its execution spec "
                    "together, or neither when admission failed before invocation."
                )
        else:
            raise ValueError(f"Unsupported corrective re-selection attempt status: {self.status}")
        return self


class CorrectiveReselectionExecutionItem(BaseModel):
    """One terminal execution item binding evidence, answer, and composition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    closure_route: ResidualClosureRoute
    attempt_id: _AttemptId
    outcome: CorrectiveReselectionOutcome
    model_invoked: bool
    raw_response_sha256: Annotated[str, Field(pattern=_SHA256)] | None = None
    receipt: dict[str, JsonValue] | None = None
    parsed_answer: ConstituentSelectionAnswer | None = None
    composition_result: DecontextualizedProposition | None = None
    error: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.outcome in {
            CorrectiveReselectionOutcome.SELECTED_PROPOSITION,
            CorrectiveReselectionOutcome.SELECTED_HOLD,
            CorrectiveReselectionOutcome.REJECTED,
            CorrectiveReselectionOutcome.ABSTAINED,
        }:
            if (
                self.raw_response_sha256 is None
                or self.receipt is None
                or self.parsed_answer is None
            ):
                raise ValueError(
                    "An answered execution item requires response, receipt, and answer."
                )
            if not self.model_invoked:
                raise ValueError("An answered execution item must record a model invocation.")
            if self.error is not None:
                raise ValueError("An answered execution item cannot carry an error.")
            model_execution_receipt_from_payload(self.receipt)
            self._validate_answered_outcome()
        elif self.outcome is CorrectiveReselectionOutcome.INPUT_BLOCKED:
            if self.error is None:
                raise ValueError("An input-blocked outcome requires an error.")
            if self.model_invoked:
                raise ValueError("An input-blocked outcome records no model invocation.")
            if self.receipt is not None:
                raise ValueError("An input-blocked outcome carries no receipt.")
            if self.parsed_answer is not None or self.composition_result is not None:
                raise ValueError("An input-blocked outcome carries no answer or composition.")
        elif self.outcome is CorrectiveReselectionOutcome.RUNTIME_FAILED:
            if self.error is None:
                raise ValueError("A runtime-failed outcome requires an error.")
            if self.parsed_answer is not None or self.composition_result is not None:
                raise ValueError("A runtime-failed outcome carries no answer or composition.")
        return self

    def _validate_answered_outcome(self) -> None:
        answer = self.parsed_answer
        assert answer is not None
        if answer.event_id != self.event_id:
            raise ValueError("An execution item's parsed answer must reference its own Event.")
        if self.outcome in {
            CorrectiveReselectionOutcome.SELECTED_PROPOSITION,
            CorrectiveReselectionOutcome.SELECTED_HOLD,
        }:
            if answer.status is not ConstituentSelectionStatus.SELECTED:
                raise ValueError("A selected outcome requires a selected answer.")
            if self.composition_result is None:
                raise ValueError("A selected outcome requires a composition result.")
            composition = self.composition_result
            if composition.event_id != self.event_id:
                raise ValueError("A composition result references a different Event.")
            if self.outcome is CorrectiveReselectionOutcome.SELECTED_PROPOSITION:
                if composition.status is not DecontextualizationStatus.PROPOSITION:
                    raise ValueError(
                        "A selected-proposition outcome requires a proposition composition."
                    )
            else:
                if composition.status is not DecontextualizationStatus.HELD:
                    raise ValueError("A selected-hold outcome requires a held composition.")
        elif self.outcome is CorrectiveReselectionOutcome.REJECTED:
            if answer.status is not ConstituentSelectionStatus.REJECTED:
                raise ValueError("A rejected outcome requires a rejected answer.")
            if self.composition_result is not None:
                raise ValueError("A rejected outcome cannot carry a composition result.")
        elif self.outcome is CorrectiveReselectionOutcome.ABSTAINED:
            if answer.status is not ConstituentSelectionStatus.NONE:
                raise ValueError("An abstained outcome requires a NONE answer.")
            if self.composition_result is not None:
                raise ValueError("An abstained outcome cannot carry a composition result.")


@dataclass(frozen=True)
class CorrectiveReselectionExecutionRequest:
    """Frozen inputs for one corrective re-selection execution attempt."""

    attempt_id: str
    extraction_task_id: str
    model_run_id: str
    event_id: str
    closure_route: ResidualClosureRoute
    corrected_prompt: str
    corrected_prompt_sha256: str
    task: ConstituentSelectionTask
    inventory: ConstituentCandidateInventory
    trigger_head_start: int
    trigger_head_end: int
    tokens: tuple[EventEntityLinguisticToken, ...]
    entities: tuple[DecontextualizationEntityRef, ...]
    model_profile_id: str
    model_identity: ModelIdentitySnapshot
    generation_parameters: tuple[ExecutionSetting, ...]
    configured_context_limit: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    prompt_id: str
    prompt_digest: str
    schema_id: str
    schema_digest: str
    context_manifest_id: str
    context_manifest_digest: str
    output_contract_version: str


@dataclass(frozen=True)
class CorrectiveReselectionExecutionOutcome:
    """One Event's terminal attempt plus its terminal execution item."""

    attempt: CorrectiveReselectionAttempt
    item: CorrectiveReselectionExecutionItem


def _outcome_for_answered(
    *, answer: ConstituentSelectionAnswer, composition: DecontextualizedProposition | None
) -> CorrectiveReselectionOutcome:
    if answer.status is ConstituentSelectionStatus.REJECTED:
        return CorrectiveReselectionOutcome.REJECTED
    if answer.status is ConstituentSelectionStatus.NONE:
        return CorrectiveReselectionOutcome.ABSTAINED
    if composition is None or composition.status is DecontextualizationStatus.HELD:
        return CorrectiveReselectionOutcome.SELECTED_HOLD
    return CorrectiveReselectionOutcome.SELECTED_PROPOSITION


def run_corrective_reselection_attempt(
    request: CorrectiveReselectionExecutionRequest,
    *,
    runtime: ModelTaskRuntime,
    persist_running_attempt: Callable[[CorrectiveReselectionAttempt], None],
    store_response: Callable[[bytes], str],
) -> CorrectiveReselectionExecutionOutcome:
    """Admit, execute, parse, and compose one corrective re-selection.

    The function verifies the corrected prompt digest before any model call,
    persists a ``running`` attempt with its admission and execution
    specification before invoking the runtime, calls ``run_model_task`` at most
    once, archives the completed response before parsing the grammar, and
    records blocked admissions and runtime errors as terminal execution items.
    """
    if (
        hashlib.sha256(request.corrected_prompt.encode()).hexdigest()
        != request.corrected_prompt_sha256
    ):
        raise ValueError("Corrective re-selection corrected prompt digest drifted.")

    task = request.task
    rendered_input = request.corrected_prompt.encode("utf-8")
    model_identity_digest = model_identity_snapshot_digest(request.model_identity)
    parameters_digest = generation_parameters_digest(request.generation_parameters)

    try:
        admission = admit_model_input(
            ModelInputAdmissionRequest(
                model_run_id=request.model_run_id,
                extraction_task_id=request.extraction_task_id,
                model_profile_id=request.model_profile_id,
                model_identity=request.model_identity,
                logical_input=rendered_input,
                configured_context_limit=request.configured_context_limit,
                reserved_output_tokens=request.reserved_output_tokens,
                safety_margin_tokens=request.safety_margin_tokens,
            ),
            runtime,
        )
    except ModelRuntimeError as error:
        failed_attempt = CorrectiveReselectionAttempt(
            attempt_id=request.attempt_id,
            event_id=request.event_id,
            closure_route=request.closure_route,
            status=ExecutionAttemptStatus.RUNTIME_FAILED,
            extraction_task_id=request.extraction_task_id,
            model_run_id=request.model_run_id,
            model_profile_id=request.model_profile_id,
            model_identity_digest=model_identity_digest,
            generation_parameters_digest=parameters_digest,
            rendered_input_digest=request.corrected_prompt_sha256,
            admission=None,
            execution_spec=None,
            error=str(error),
        )
        failed_item = CorrectiveReselectionExecutionItem(
            event_id=request.event_id,
            closure_route=request.closure_route,
            attempt_id=request.attempt_id,
            outcome=CorrectiveReselectionOutcome.RUNTIME_FAILED,
            model_invoked=False,
            error=str(error),
        )
        return CorrectiveReselectionExecutionOutcome(attempt=failed_attempt, item=failed_item)

    if admission.status is not ModelInputAdmissionStatus.READY:
        error = admission.blocked_reason or "complete_request_exceeds_context_budget"
        block_attempt = CorrectiveReselectionAttempt(
            attempt_id=request.attempt_id,
            event_id=request.event_id,
            closure_route=request.closure_route,
            status=ExecutionAttemptStatus.INPUT_BLOCKED,
            extraction_task_id=request.extraction_task_id,
            model_run_id=request.model_run_id,
            model_profile_id=request.model_profile_id,
            model_identity_digest=model_identity_digest,
            generation_parameters_digest=parameters_digest,
            rendered_input_digest=request.corrected_prompt_sha256,
            admission=admission.model_dump(mode="json"),
            execution_spec=None,
            error=error,
        )
        block_item = CorrectiveReselectionExecutionItem(
            event_id=request.event_id,
            closure_route=request.closure_route,
            attempt_id=request.attempt_id,
            outcome=CorrectiveReselectionOutcome.INPUT_BLOCKED,
            model_invoked=False,
            error=error,
        )
        return CorrectiveReselectionExecutionOutcome(attempt=block_attempt, item=block_item)

    spec = ModelExecutionSpec(
        model_profile_id=request.model_profile_id,
        model_identity=request.model_identity,
        generation_parameters=request.generation_parameters,
        prompt_id=request.prompt_id,
        prompt_digest=request.prompt_digest,
        schema_id=request.schema_id,
        schema_digest=request.schema_digest,
        context_manifest_id=request.context_manifest_id,
        context_manifest_digest=request.context_manifest_digest,
        rendered_input_digest=request.corrected_prompt_sha256,
        output_contract_version=request.output_contract_version,
    )
    running_attempt = CorrectiveReselectionAttempt(
        attempt_id=request.attempt_id,
        event_id=request.event_id,
        closure_route=request.closure_route,
        status=ExecutionAttemptStatus.RUNNING,
        extraction_task_id=request.extraction_task_id,
        model_run_id=request.model_run_id,
        model_profile_id=request.model_profile_id,
        model_identity_digest=model_identity_digest,
        generation_parameters_digest=parameters_digest,
        rendered_input_digest=request.corrected_prompt_sha256,
        admission=admission.model_dump(mode="json"),
        execution_spec=model_execution_spec_payload(spec),
        error=None,
    )
    persist_running_attempt(running_attempt)

    model_task = ModelTaskRequest(
        extraction_task_id=request.extraction_task_id,
        task_fingerprint=request.corrected_prompt_sha256,
        task_type="corrective_reselection",
        context_manifest_id=request.context_manifest_id,
        context_manifest_digest=request.context_manifest_digest,
        rendered_input=rendered_input,
        rendered_input_digest=request.corrected_prompt_sha256,
        execution_spec=spec,
        input_admission=admission,
    )

    try:
        response = runtime.run_model_task(model_task)
    except ModelRuntimeError as error:
        failed_attempt = CorrectiveReselectionAttempt(
            attempt_id=request.attempt_id,
            event_id=request.event_id,
            closure_route=request.closure_route,
            status=ExecutionAttemptStatus.RUNTIME_FAILED,
            extraction_task_id=request.extraction_task_id,
            model_run_id=request.model_run_id,
            model_profile_id=request.model_profile_id,
            model_identity_digest=model_identity_digest,
            generation_parameters_digest=parameters_digest,
            rendered_input_digest=request.corrected_prompt_sha256,
            admission=admission.model_dump(mode="json"),
            execution_spec=model_execution_spec_payload(spec),
            error=str(error),
        )
        failed_item = CorrectiveReselectionExecutionItem(
            event_id=request.event_id,
            closure_route=request.closure_route,
            attempt_id=request.attempt_id,
            outcome=CorrectiveReselectionOutcome.RUNTIME_FAILED,
            model_invoked=True,
            error=str(error),
        )
        return CorrectiveReselectionExecutionOutcome(attempt=failed_attempt, item=failed_item)

    raw_sha256 = store_response(response.raw_output)
    receipt = response.execution_receipt
    if receipt.model_identity_digest != model_identity_digest:
        raise ValueError(
            "Corrective re-selection receipt identity does not match its execution spec."
        )
    if receipt.generation_parameters_digest != parameters_digest:
        raise ValueError(
            "Corrective re-selection receipt generation parameters do not match its spec."
        )
    if receipt.rendered_input_digest != request.corrected_prompt_sha256:
        raise ValueError(
            "Corrective re-selection receipt input does not match the corrected prompt."
        )
    receipt_payload = _receipt_payload(receipt)
    model_execution_receipt_from_payload(receipt_payload)

    try:
        raw_answer = response.raw_output.decode("utf-8")
    except UnicodeDecodeError:
        answer = _rejected(request.event_id)
    else:
        answer = parse_corrective_reselection_answer(
            raw_answer=raw_answer,
            task=task,
            route=request.closure_route,
        )
    composition = compose_corrective_reselection_answer(
        answer=answer,
        source_text=task.source_text,
        source_text_sha256=task.source_text_sha256,
        inventory=request.inventory,
        trigger_head_start=request.trigger_head_start,
        trigger_head_end=request.trigger_head_end,
        tokens=request.tokens,
        entities=request.entities,
    )

    terminal_attempt = CorrectiveReselectionAttempt(
        attempt_id=request.attempt_id,
        event_id=request.event_id,
        closure_route=request.closure_route,
        status=ExecutionAttemptStatus.ANSWERED,
        extraction_task_id=request.extraction_task_id,
        model_run_id=request.model_run_id,
        model_profile_id=request.model_profile_id,
        model_identity_digest=model_identity_digest,
        generation_parameters_digest=parameters_digest,
        rendered_input_digest=request.corrected_prompt_sha256,
        admission=admission.model_dump(mode="json"),
        execution_spec=model_execution_spec_payload(spec),
        error=None,
    )
    item = CorrectiveReselectionExecutionItem(
        event_id=request.event_id,
        closure_route=request.closure_route,
        attempt_id=request.attempt_id,
        outcome=_outcome_for_answered(answer=answer, composition=composition),
        model_invoked=True,
        raw_response_sha256=raw_sha256,
        receipt=receipt_payload,
        parsed_answer=answer,
        composition_result=composition,
        error=None,
    )
    return CorrectiveReselectionExecutionOutcome(attempt=terminal_attempt, item=item)


def _outcome_counts(
    items: tuple[CorrectiveReselectionExecutionItem, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {outcome.value: 0 for outcome in CorrectiveReselectionOutcome}
    for item in items:
        counts[item.outcome.value] += 1
    return counts


def _model_execution_count(
    items: tuple[CorrectiveReselectionExecutionItem, ...],
) -> int:
    # Count ``run_model_task`` invocations, not terminal outcomes.  An admission
    # error records a ``runtime_failed`` outcome without ever invoking the model;
    # a runtime error after admission still counts as one invocation.
    return sum(1 for item in items if item.model_invoked)


def corrective_reselection_report_fingerprint(
    value: BaseModel | dict[str, object],
) -> str:
    """Return the semantic digest of one R16 report draft."""
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


class CorrectiveReselectionReport(BaseModel):
    """Sealed R16 report with ordered terminal items and zero-write safety."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_report_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    closure_report_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    items: tuple[CorrectiveReselectionExecutionItem, ...]
    outcome_counts: dict[str, Annotated[int, Field(ge=0)]]
    model_execution_count: Annotated[int, Field(ge=0)]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.event_id for item in self.items)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("R16 report items must be ordered and distinct.")
        expected_keys = {outcome.value for outcome in CorrectiveReselectionOutcome}
        if set(self.outcome_counts) != expected_keys:
            raise ValueError("R16 report outcome counts must cover every outcome exactly once.")
        if self.outcome_counts != _outcome_counts(self.items):
            raise ValueError("R16 report outcome counts drifted from its items.")
        if self.model_execution_count != _model_execution_count(self.items):
            raise ValueError("R16 report model execution count drifted from its items.")
        if self.canonical_write_count != 0 or self.proposed_change_count != 0:
            raise ValueError("R16 report must record zero canonical writes and zero proposals.")
        return self


def build_corrective_reselection_report(
    *,
    source_report_fingerprint: str,
    closure_report_fingerprint: str,
    items: tuple[CorrectiveReselectionExecutionItem, ...],
) -> CorrectiveReselectionReport:
    """Assemble and seal the R16 report from its terminal execution items."""
    draft = CorrectiveReselectionReport.model_construct(
        source_report_fingerprint=source_report_fingerprint,
        closure_report_fingerprint=closure_report_fingerprint,
        items=items,
        outcome_counts=_outcome_counts(items),
        model_execution_count=_model_execution_count(items),
        canonical_write_count=0,
        proposed_change_count=0,
        result_fingerprint="0" * 64,
    )
    return CorrectiveReselectionReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=corrective_reselection_report_fingerprint(draft),
    )


def rebuild_corrective_reselection_report(
    payload: dict[str, object],
) -> CorrectiveReselectionReport:
    """Rebuild one sealed R16 report from its validated persisted payload."""
    if set(payload) != {
        "source_report_fingerprint",
        "closure_report_fingerprint",
        "items",
        "outcome_counts",
        "model_execution_count",
        "canonical_write_count",
        "proposed_change_count",
        "result_fingerprint",
    }:
        raise ValueError("R16 report payload has an invalid shape.")
    items_value = payload["items"]
    if not isinstance(items_value, list):
        raise ValueError("R16 report items must be a list.")
    items = tuple(
        CorrectiveReselectionExecutionItem.model_validate(item, strict=False)
        for item in cast(list[object], items_value)
    )
    report = CorrectiveReselectionReport(
        source_report_fingerprint=cast(str, payload["source_report_fingerprint"]),
        closure_report_fingerprint=cast(str, payload["closure_report_fingerprint"]),
        items=items,
        outcome_counts=cast(dict[str, int], payload["outcome_counts"]),
        model_execution_count=cast(int, payload["model_execution_count"]),
        canonical_write_count=cast(int, payload["canonical_write_count"]),
        proposed_change_count=cast(int, payload["proposed_change_count"]),
        result_fingerprint=cast(str, payload["result_fingerprint"]),
    )
    if report.result_fingerprint != corrective_reselection_report_fingerprint(report):
        raise ValueError("R16 report fingerprint does not match its contents.")
    return report
