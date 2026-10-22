"""Semantic instruction discrimination experiment for the R18 deliverable.

R18 asks one bounded question: does naming the eligibility rule and the
complete-selected-set rules improve the three instruction-sensitive signals
(``answer_grammar``, ``semantic_selection``, and ``abstention_correctness``) over
the format-only instruction?

R18 freezes the source text, the Candidate pools, the routes, the model, and the
runtime configuration and varies only the instruction prefix.  It renders two
prompts per frozen R17 reference policy record -- one format-only and one semantic
-- whose prompt body is byte-identical.  Each pair is admitted through the
existing tokenizer contract, executed at most once, and archived as an unreviewed
experimental observation.  The five independent signals are never merged; boundary
coverage and composition readiness evaluate the frozen reference record, never the
observed answer.  The predeclared verdict is per signal and keeps every malformed,
blocked, and failed pair in the denominator.

Nothing here writes canonical Ledger state or a ProposedChange.  The sealed report
records zero canonical writes and zero ProposedChanges.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain import ModelInputAdmissionStatus
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.corrective_reselection_execution import (
    parse_corrective_reselection_answer,
)
from kotekomi_application.model_runtime import ModelRuntimeError
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
)
from kotekomi_application.residual_selection_failure_closure import (
    CorrectiveSelectionTask,
    ResidualClosureRoute,
    corrective_instruction_for,
)
from kotekomi_application.semantic_selection_contract import (
    ReferencePolicyRecord,
    SemanticSelectionContract,
    SemanticSelectionSignalName,
    SemanticSelectionSignalResult,
    check_boundary_coverage,
    compute_composition_readiness,
)
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
    model_identity_snapshot_digest,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]

#: The two residual Events R18 reports individually in the diagnostic group.
DIAGNOSTIC_EVENT_IDS: tuple[str, ...] = ("AHE-022", "AHE-051")

#: The unreviewed marker every experimental observation carries.
EXPERIMENTAL_REVIEW_STATUS: Literal["unreviewed_experimental"] = "unreviewed_experimental"


class InstructionVariant(StrEnum):
    """One pinned instruction prefix the model reads."""

    FORMAT_ONLY = "format_only"
    SEMANTIC = "semantic"


class TerminalOutcome(StrEnum):
    """One terminal outcome for one (instruction variant, reference record) pair."""

    ANSWERED = "answered"
    BLOCKED = "blocked"
    FAILED = "failed"


class DiscriminationVerdict(StrEnum):
    """One predeclared, per-signal comparison result across the two variants."""

    IMPROVEMENT = "improvement"
    REGRESSION = "regression"
    MIXED = "mixed"
    INCONCLUSIVE = "inconclusive"


class DiscriminationGroup(StrEnum):
    """One report group: the two diagnostic records or the nine constructed ones."""

    DIAGNOSTIC = "diagnostic"
    CONSTRUCTED = "constructed"


_INSTRUCTION_SENSITIVE_SIGNALS: tuple[SemanticSelectionSignalName, ...] = (
    SemanticSelectionSignalName.ANSWER_GRAMMAR,
    SemanticSelectionSignalName.SEMANTIC_SELECTION,
    SemanticSelectionSignalName.ABSTENTION_CORRECTNESS,
)


def corrective_task_body(*, record: ReferencePolicyRecord, frozen_input: bytes) -> str:
    """Extract the shared body from the digest-bound archived corrective task.

    R17's rendered task includes semantic instructions and is not the format-only
    control. Use the frozen input's existing CorrectiveSelectionTask instead.
    """
    if hashlib.sha256(frozen_input).hexdigest() != record.input_binding.input_file.sha256:
        raise ValueError("Discrimination frozen input digest drifted.")
    document = json.loads(frozen_input)
    if not isinstance(document, dict):
        raise ValueError("Discrimination frozen input must be a JSON object.")
    task = CorrectiveSelectionTask.model_validate_json(json.dumps(document["corrective_task"]))
    if task.event_id != record.event_id:
        raise ValueError("Discrimination corrective task references a different Event.")
    if task.closure_route is not record.input_binding.frozen_route:
        raise ValueError("Discrimination corrective task route differs from its frozen route.")
    prefix = task.corrected_instruction + "\n"
    if not task.corrected_prompt.startswith(prefix):
        raise ValueError("Discrimination corrective task requires a newline-delimited body.")
    body = task.corrected_prompt[len(prefix) :]
    if not body:
        raise ValueError("Discrimination corrective task body must not be empty.")
    return body


def format_only_instruction(route: ResidualClosureRoute) -> str:
    """Return the frozen R15 corrective instruction for one route, byte for byte."""
    return corrective_instruction_for(route)


def semantic_instruction(
    *, route: ResidualClosureRoute, contract: SemanticSelectionContract
) -> str:
    """Return the format-only instruction followed by the eligibility and complete-set rules."""
    lines = [corrective_instruction_for(route), f"Eligibility: {contract.eligibility_rule}"]
    lines.extend(contract.complete_selected_set_rules)
    return "\n".join(lines)


def discrimination_pair_id(*, event_id: str, variant: InstructionVariant) -> str:
    """Return the deterministic pair identifier for one (variant, record) pair."""
    return f"{event_id}::{variant.value}"


class DiscriminationPreparedPrompt(BaseModel):
    """One prepared prompt binding a pair to its rendered item and shared body."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    pair_id: Annotated[str, Field(min_length=1)]
    event_id: _EventId
    route: ResidualClosureRoute
    variant: InstructionVariant
    prompt: Annotated[str, Field(min_length=1)]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    body_sha256: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_prompt(self) -> Self:
        if hashlib.sha256(self.prompt.encode()).hexdigest() != self.prompt_sha256:
            raise ValueError("Prepared prompt digest does not match its content.")
        if self.pair_id != discrimination_pair_id(event_id=self.event_id, variant=self.variant):
            raise ValueError("Prepared prompt pair ID differs from its Event and variant.")
        return self


def render_discrimination_prompt(
    *,
    record: ReferencePolicyRecord,
    contract: SemanticSelectionContract,
    variant: InstructionVariant,
    frozen_input: bytes,
) -> str:
    """Render one prompt whose body is the frozen corrective task body."""
    body = corrective_task_body(record=record, frozen_input=frozen_input)
    route = record.input_binding.frozen_route
    if variant is InstructionVariant.FORMAT_ONLY:
        instruction = format_only_instruction(route)
    elif variant is InstructionVariant.SEMANTIC:
        instruction = semantic_instruction(route=route, contract=contract)
    else:
        raise ValueError(f"Unsupported instruction variant: {variant}")
    return f"{instruction}\n{body}"


def render_discrimination_prompts(
    *, record: ReferencePolicyRecord, contract: SemanticSelectionContract, frozen_input: bytes
) -> tuple[DiscriminationPreparedPrompt, DiscriminationPreparedPrompt]:
    """Render the two prompts for one record with one byte-identical body."""
    body = corrective_task_body(record=record, frozen_input=frozen_input)
    body_sha256 = hashlib.sha256(body.encode()).hexdigest()
    route = record.input_binding.frozen_route
    prepared: list[DiscriminationPreparedPrompt] = []
    for variant in (InstructionVariant.FORMAT_ONLY, InstructionVariant.SEMANTIC):
        prompt = render_discrimination_prompt(
            record=record, contract=contract, variant=variant, frozen_input=frozen_input
        )
        prepared.append(
            DiscriminationPreparedPrompt(
                pair_id=discrimination_pair_id(event_id=record.event_id, variant=variant),
                event_id=record.event_id,
                route=route,
                variant=variant,
                prompt=prompt,
                prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                body_sha256=body_sha256,
            )
        )
    return prepared[0], prepared[1]


class ExperimentalObservation(BaseModel):
    """One unreviewed experimental response bound to its task, receipt, and archive."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    observation_id: Annotated[str, Field(min_length=1)]
    event_id: _EventId
    route: ResidualClosureRoute
    variant: InstructionVariant
    review_status: Literal["unreviewed_experimental"]
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    generation_parameters_digest: Annotated[str, Field(pattern=_SHA256)]
    rendered_input_digest: Annotated[str, Field(pattern=_SHA256)]
    raw_response_sha256: Annotated[str, Field(pattern=_SHA256)]
    receipt: dict[str, JsonValue]
    parsed_answer: ConstituentSelectionAnswer


class DiscriminationExecutionBinding(BaseModel):
    """Run-wide model identity and generation settings recorded before execution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model_identity: ModelIdentitySnapshot
    generation_parameters: tuple[ExecutionSetting, ...]

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        keys = tuple(setting.key for setting in self.generation_parameters)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("Discrimination generation settings must be ordered and distinct.")
        generation_parameters_digest(self.generation_parameters)
        return self


class DiscriminationObservationItem(BaseModel):
    """One terminal (instruction variant, reference record) pair in the report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    pair_id: Annotated[str, Field(min_length=1)]
    event_id: _EventId
    route: ResidualClosureRoute
    variant: InstructionVariant
    outcome: TerminalOutcome
    model_invoked: bool
    observation: ExperimentalObservation | None = None
    signals: tuple[SemanticSelectionSignalResult, ...] | None = None
    error: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_terminal(self) -> Self:
        if self.outcome is TerminalOutcome.ANSWERED:
            if self.observation is None:
                raise ValueError("An answered pair requires an experimental observation.")
            if self.signals is None:
                raise ValueError("An answered pair requires its five signal results.")
            if not self.model_invoked:
                raise ValueError("An answered pair must have invoked the model.")
            if self.error is not None:
                raise ValueError("An answered pair cannot carry an error.")
        else:
            if self.observation is not None:
                raise ValueError("A non-answered pair cannot carry an observation.")
            if self.signals is not None:
                raise ValueError("A non-answered pair cannot carry signal results.")
            if self.error is None:
                raise ValueError("A blocked or failed pair requires an error.")
            if self.outcome is TerminalOutcome.BLOCKED and self.model_invoked:
                raise ValueError("A blocked pair never invokes the model.")
        if self.observation is not None:
            if self.observation.variant is not self.variant:
                raise ValueError("Observation variant differs from its pair.")
            if self.observation.event_id != self.event_id:
                raise ValueError("Observation Event differs from its pair.")
            if self.observation.route is not self.route:
                raise ValueError("Observation route differs from its pair.")
        if self.signals is not None:
            names = tuple(signal.name for signal in self.signals)
            if names != tuple(SemanticSelectionSignalName):
                raise ValueError("An experiment item must cover the five signals in order.")
        return self


def discrimination_signals_from_parsed(
    *,
    policy_record: ReferencePolicyRecord,
    parsed: ConstituentSelectionAnswer,
) -> tuple[SemanticSelectionSignalResult, ...]:
    """Apply the exact R17 five-signal rules to one parsed experimental answer."""
    if parsed.event_id != policy_record.event_id:
        raise ValueError("Discrimination parsed answer Event differs from its policy record.")
    grammar = "invalid" if parsed.status is ConstituentSelectionStatus.REJECTED else "valid"
    if parsed.status is ConstituentSelectionStatus.REJECTED:
        semantic = "not_applicable"
        abstention = "not_applicable"
    else:
        selected = tuple(f"C{i}" for i in parsed.selected_label_indexes)
        semantic = "met" if selected == policy_record.expected_selected_set else "unmet"
        abstention = (
            "not_applicable"
            if parsed.status is not ConstituentSelectionStatus.NONE
            else ("justified" if policy_record.none_policy.justified else "unjustified")
        )
    coverage = check_boundary_coverage(policy_record=policy_record)
    readiness = compute_composition_readiness(policy_record=policy_record)
    return (
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.ANSWER_GRAMMAR,
            value=grammar,
            explanation="Strict R16 route grammar applied once to the raw response.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.SEMANTIC_SELECTION,
            value=semantic,
            explanation="Observed label set compared with the reviewed expected selected set.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.BOUNDARY_COVERAGE,
            value=coverage,
            explanation="Expected source ranges compared with the frozen Candidate pool.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.ABSTENTION_CORRECTNESS,
            value=abstention,
            explanation="Observed NONE judged against the reviewed expected eligible set.",
        ),
        SemanticSelectionSignalResult(
            name=SemanticSelectionSignalName.COMPOSITION_READINESS,
            value=readiness,
            explanation="Readiness evaluates the reference selected set, not the observed answer.",
        ),
    )


def evaluate_discrimination_observation(
    *,
    policy_record: ReferencePolicyRecord,
    route: ResidualClosureRoute,
    raw_response: str,
) -> tuple[SemanticSelectionSignalResult, ...]:
    """Parse one raw response once and apply the exact R17 five-signal rules."""
    if route is not policy_record.input_binding.frozen_route:
        raise ValueError("Discrimination evaluation route differs from its frozen route.")
    parsed = parse_corrective_reselection_answer(raw_response, policy_record.task, route)
    return discrimination_signals_from_parsed(policy_record=policy_record, parsed=parsed)


def rebuild_discrimination_item(
    *,
    prepared: DiscriminationPreparedPrompt,
    policy_record: ReferencePolicyRecord,
    item: DiscriminationObservationItem,
    raw_response: bytes | None,
    execution_binding: DiscriminationExecutionBinding,
) -> DiscriminationObservationItem:
    """Verify archived evidence and rebuild an item's parse and five signal results."""
    expected_pair = discrimination_pair_id(event_id=prepared.event_id, variant=prepared.variant)
    if prepared.pair_id != expected_pair or item.pair_id != expected_pair:
        raise ValueError("Discrimination evidence pair differs from its prepared prompt.")
    if item.event_id != prepared.event_id or policy_record.event_id != prepared.event_id:
        raise ValueError("Discrimination evidence Event differs from its prepared prompt.")
    if (
        item.route is not prepared.route
        or prepared.route is not policy_record.input_binding.frozen_route
    ):
        raise ValueError("Discrimination evidence route differs from its frozen route.")
    if item.variant is not prepared.variant:
        raise ValueError("Discrimination evidence variant differs from its prepared prompt.")
    if item.outcome is not TerminalOutcome.ANSWERED:
        if raw_response is not None:
            raise ValueError("A non-answered discrimination item cannot carry a raw response.")
        return item
    observation = item.observation
    if observation is None or raw_response is None:
        raise ValueError("An answered discrimination item requires archived response evidence.")
    if hashlib.sha256(raw_response).hexdigest() != observation.raw_response_sha256:
        raise ValueError("Discrimination archived response digest drifted.")
    receipt = model_execution_receipt_from_payload(observation.receipt)
    identity_digest = model_identity_snapshot_digest(execution_binding.model_identity)
    parameters_digest = generation_parameters_digest(execution_binding.generation_parameters)
    if (
        receipt.model_identity_digest != identity_digest
        or observation.model_identity_digest != identity_digest
    ):
        raise ValueError("Discrimination receipt identity differs from the run binding.")
    if (
        receipt.generation_parameters_digest != parameters_digest
        or observation.generation_parameters_digest != parameters_digest
    ):
        raise ValueError(
            "Discrimination receipt generation parameters differ from the run binding."
        )
    if (
        receipt.rendered_input_digest != prepared.prompt_sha256
        or observation.rendered_input_digest != prepared.prompt_sha256
    ):
        raise ValueError("Discrimination receipt input differs from the prepared prompt.")
    parsed = parse_corrective_reselection_answer(
        raw_response.decode("utf-8", errors="replace"), policy_record.task, prepared.route
    )
    if observation.parsed_answer != parsed:
        raise ValueError("Discrimination stored parse differs from the archived response.")
    signals = discrimination_signals_from_parsed(policy_record=policy_record, parsed=parsed)
    if item.signals != signals:
        raise ValueError("Discrimination stored signals differ from the recomputed results.")
    return DiscriminationObservationItem(
        pair_id=expected_pair,
        event_id=prepared.event_id,
        route=prepared.route,
        variant=prepared.variant,
        outcome=TerminalOutcome.ANSWERED,
        model_invoked=True,
        observation=ExperimentalObservation(
            **observation.model_dump(exclude={"parsed_answer"}), parsed_answer=parsed
        ),
        signals=signals,
    )


def _discrimination_receipt_payload(receipt: ModelExecutionReceipt) -> dict[str, JsonValue]:
    """Serialize one execution receipt exactly as R16 archives it."""
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


@dataclass(frozen=True)
class DiscriminationExecutionRequest:
    """Frozen inputs for one experimental (instruction variant, reference record) pair."""

    observation_id: str
    event_id: str
    route: ResidualClosureRoute
    variant: InstructionVariant
    prompt: str
    prompt_sha256: str
    prepared_prompt: DiscriminationPreparedPrompt
    task: ConstituentSelectionTask
    policy_record: ReferencePolicyRecord
    model_profile_id: str
    model_identity: ModelIdentitySnapshot
    generation_parameters: tuple[ExecutionSetting, ...]
    model_run_id: str
    extraction_task_id: str
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


def run_discrimination_attempt(
    request: DiscriminationExecutionRequest,
    *,
    runtime: ModelTaskRuntime,
    store_response: Callable[[bytes], str],
) -> DiscriminationObservationItem:
    """Admit, execute, parse, and evaluate one experimental pair at most once.

    The function validates the Event, frozen route, policy task, and prepared prompt
    together before admission or any model call, admits
    the prompt through the existing tokenizer contract, records a blocked admission
    as a terminal ``blocked`` pair with no execution, invokes the model at most once,
    archives the raw response and validated receipt, parses the archived response
    once through the route grammar, and records runtime failures as terminal
    ``failed`` pairs.  Answered pairs carry an unreviewed experimental observation
    and the five independent signal results.
    """
    if hashlib.sha256(request.prompt.encode()).hexdigest() != request.prompt_sha256:
        raise ValueError("Discrimination prompt digest drifted before execution.")
    prepared = DiscriminationPreparedPrompt.model_validate_json(
        request.prepared_prompt.model_dump_json()
    )
    policy = request.policy_record
    if request.event_id != policy.event_id or prepared.event_id != policy.event_id:
        raise ValueError("Discrimination execution Event differs from its policy record.")
    if request.task.event_id != policy.event_id or policy.task.event_id != policy.event_id:
        raise ValueError("Discrimination execution task Event differs from its policy record.")
    if request.task != policy.task:
        raise ValueError("Discrimination execution task differs from its policy task.")
    frozen_route = policy.input_binding.frozen_route
    if request.route is not frozen_route or prepared.route is not frozen_route:
        raise ValueError("Discrimination execution route differs from its frozen route.")
    if request.variant is not prepared.variant:
        raise ValueError("Discrimination execution variant differs from its prepared prompt.")
    if request.prompt != prepared.prompt or request.prompt_sha256 != prepared.prompt_sha256:
        raise ValueError("Discrimination execution prompt differs from its prepared prompt.")

    rendered_input = request.prompt.encode("utf-8")
    model_identity_digest = model_identity_snapshot_digest(request.model_identity)
    parameters_digest = generation_parameters_digest(request.generation_parameters)

    def _terminal(
        outcome: TerminalOutcome,
        *,
        model_invoked: bool,
        error: str | None = None,
        observation: ExperimentalObservation | None = None,
        signals: tuple[SemanticSelectionSignalResult, ...] | None = None,
    ) -> DiscriminationObservationItem:
        return DiscriminationObservationItem(
            pair_id=discrimination_pair_id(event_id=request.event_id, variant=request.variant),
            event_id=request.event_id,
            route=request.route,
            variant=request.variant,
            outcome=outcome,
            model_invoked=model_invoked,
            observation=observation,
            signals=signals,
            error=error,
        )

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
        return _terminal(TerminalOutcome.FAILED, model_invoked=False, error=str(error))

    if admission.status is not ModelInputAdmissionStatus.READY:
        error = admission.blocked_reason or "complete_request_exceeds_context_budget"
        return _terminal(TerminalOutcome.BLOCKED, model_invoked=False, error=error)

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
        rendered_input_digest=request.prompt_sha256,
        output_contract_version=request.output_contract_version,
    )
    model_task = ModelTaskRequest(
        extraction_task_id=request.extraction_task_id,
        task_fingerprint=request.prompt_sha256,
        task_type="semantic_instruction_discrimination",
        context_manifest_id=request.context_manifest_id,
        context_manifest_digest=request.context_manifest_digest,
        rendered_input=rendered_input,
        rendered_input_digest=request.prompt_sha256,
        execution_spec=spec,
        input_admission=admission,
    )

    try:
        response = runtime.run_model_task(model_task)
    except ModelRuntimeError as error:
        return _terminal(TerminalOutcome.FAILED, model_invoked=True, error=str(error))

    raw_response_sha256 = store_response(response.raw_output)
    receipt = response.execution_receipt
    if receipt.model_identity_digest != model_identity_digest:
        raise ValueError("Discrimination receipt identity does not match its execution spec.")
    if receipt.generation_parameters_digest != parameters_digest:
        raise ValueError("Discrimination receipt generation parameters do not match its spec.")
    if receipt.rendered_input_digest != request.prompt_sha256:
        raise ValueError("Discrimination receipt input does not match the prepared prompt.")
    receipt_payload = _discrimination_receipt_payload(receipt)
    model_execution_receipt_from_payload(receipt_payload)

    try:
        raw_answer = response.raw_output.decode("utf-8")
    except UnicodeDecodeError:
        raw_answer = response.raw_output.decode("utf-8", errors="replace")

    parsed = parse_corrective_reselection_answer(raw_answer, request.task, request.route)
    signals = discrimination_signals_from_parsed(policy_record=request.policy_record, parsed=parsed)
    observation = ExperimentalObservation(
        observation_id=request.observation_id,
        event_id=request.event_id,
        route=request.route,
        variant=request.variant,
        review_status=EXPERIMENTAL_REVIEW_STATUS,
        model_identity_digest=model_identity_digest,
        generation_parameters_digest=parameters_digest,
        rendered_input_digest=request.prompt_sha256,
        raw_response_sha256=raw_response_sha256,
        receipt=receipt_payload,
        parsed_answer=parsed,
    )
    return _terminal(
        TerminalOutcome.ANSWERED,
        model_invoked=True,
        observation=observation,
        signals=signals,
    )


def _comparison_direction(
    signal: SemanticSelectionSignalName, format_value: str, semantic_value: str
) -> str:
    """Return ``better``, ``worse``, ``same``, or ``undecidable`` for one record pair."""
    if signal is SemanticSelectionSignalName.ANSWER_GRAMMAR:
        if format_value in {"valid", "invalid"} and semantic_value in {"valid", "invalid"}:
            if format_value == "invalid" and semantic_value == "valid":
                return "better"
            if format_value == "valid" and semantic_value == "invalid":
                return "worse"
            return "same"
        return "undecidable"
    if signal is SemanticSelectionSignalName.SEMANTIC_SELECTION:
        if "not_applicable" in {format_value, semantic_value}:
            return "undecidable"
        if format_value == "unmet" and semantic_value == "met":
            return "better"
        if format_value == "met" and semantic_value == "unmet":
            return "worse"
        return "same"
    if signal is SemanticSelectionSignalName.ABSTENTION_CORRECTNESS:
        if "not_applicable" in {format_value, semantic_value}:
            return "undecidable"
        if format_value == "unjustified" and semantic_value == "justified":
            return "better"
        if format_value == "justified" and semantic_value == "unjustified":
            return "worse"
        return "same"
    raise ValueError(f"Instruction-invariant signal cannot be compared: {signal}")


def _verdict(
    *, better: int, worse: int, undecidable: int, incomplete: int
) -> DiscriminationVerdict:
    """Apply the predeclared per-signal verdict rules to one group's tallies."""
    if incomplete:
        return DiscriminationVerdict.INCONCLUSIVE
    if undecidable:
        return DiscriminationVerdict.INCONCLUSIVE
    if better and not worse:
        return DiscriminationVerdict.IMPROVEMENT
    if worse and not better:
        return DiscriminationVerdict.REGRESSION
    if better and worse:
        return DiscriminationVerdict.MIXED
    return DiscriminationVerdict.INCONCLUSIVE


def _signal_value(
    item: DiscriminationObservationItem, signal: SemanticSelectionSignalName
) -> str | None:
    """Return one answered pair's signal value, or ``None`` for a terminal pair."""
    if item.outcome is not TerminalOutcome.ANSWERED or item.signals is None:
        return None
    for result in item.signals:
        if result.name is signal:
            return result.value
    return None


class DiscriminationSignalComparison(BaseModel):
    """One predeclared, per-signal, per-group comparison across the two variants."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    signal: SemanticSelectionSignalName
    group: DiscriminationGroup
    verdict: DiscriminationVerdict
    denominator: Annotated[int, Field(ge=1)]
    format_value_counts: dict[str, int]
    semantic_value_counts: dict[str, int]
    better_pair_count: Annotated[int, Field(ge=0)]
    worse_pair_count: Annotated[int, Field(ge=0)]
    undecidable_pair_count: Annotated[int, Field(ge=0)]
    incomplete_pair_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_signal_and_verdict(self) -> Self:
        if self.signal not in _INSTRUCTION_SENSITIVE_SIGNALS:
            raise ValueError("Only instruction-sensitive signals carry a comparison.")
        expected = _verdict(
            better=self.better_pair_count,
            worse=self.worse_pair_count,
            undecidable=self.undecidable_pair_count,
            incomplete=self.incomplete_pair_count,
        )
        if self.verdict is not expected:
            raise ValueError("Discrimination verdict drifted from its tallies.")
        return self


def compute_discrimination_signal_comparison(
    *,
    signal: SemanticSelectionSignalName,
    group: DiscriminationGroup,
    group_event_ids: tuple[str, ...],
    items_by_pair: dict[tuple[str, InstructionVariant], DiscriminationObservationItem],
) -> DiscriminationSignalComparison:
    """Tally one signal across two variants for one group and apply the verdict."""
    denominator = 2 * len(group_event_ids)
    format_value_counts: dict[str, int] = {}
    semantic_value_counts: dict[str, int] = {}
    better = worse = undecidable = 0
    incomplete = 0
    for event_id in group_event_ids:
        format_item = items_by_pair[(event_id, InstructionVariant.FORMAT_ONLY)]
        semantic_item = items_by_pair[(event_id, InstructionVariant.SEMANTIC)]
        if format_item.outcome is not TerminalOutcome.ANSWERED:
            incomplete += 1
        if semantic_item.outcome is not TerminalOutcome.ANSWERED:
            incomplete += 1
        format_value = _signal_value(format_item, signal)
        semantic_value = _signal_value(semantic_item, signal)
        if format_value is not None:
            format_value_counts[format_value] = format_value_counts.get(format_value, 0) + 1
        if semantic_value is not None:
            semantic_value_counts[semantic_value] = semantic_value_counts.get(semantic_value, 0) + 1
        if format_value is None or semantic_value is None:
            continue
        direction = _comparison_direction(signal, format_value, semantic_value)
        if direction == "better":
            better += 1
        elif direction == "worse":
            worse += 1
        elif direction == "undecidable":
            undecidable += 1
    return DiscriminationSignalComparison(
        signal=signal,
        group=group,
        verdict=_verdict(
            better=better, worse=worse, undecidable=undecidable, incomplete=incomplete
        ),
        denominator=denominator,
        format_value_counts=format_value_counts,
        semantic_value_counts=semantic_value_counts,
        better_pair_count=better,
        worse_pair_count=worse,
        undecidable_pair_count=undecidable,
        incomplete_pair_count=incomplete,
    )


def compute_discrimination_comparisons(
    *,
    items: tuple[DiscriminationObservationItem, ...],
    diagnostic_event_ids: tuple[str, ...],
    constructed_event_ids: tuple[str, ...],
) -> tuple[DiscriminationSignalComparison, ...]:
    """Compute the six comparisons: three sensitive signals by two report groups."""
    items_by_pair = {(item.event_id, item.variant): item for item in items}
    comparisons: list[DiscriminationSignalComparison] = []
    for signal in _INSTRUCTION_SENSITIVE_SIGNALS:
        for group, event_ids in (
            (DiscriminationGroup.DIAGNOSTIC, diagnostic_event_ids),
            (DiscriminationGroup.CONSTRUCTED, constructed_event_ids),
        ):
            comparisons.append(
                compute_discrimination_signal_comparison(
                    signal=signal,
                    group=group,
                    group_event_ids=event_ids,
                    items_by_pair=items_by_pair,
                )
            )
    return tuple(comparisons)


class DiscriminationReport(BaseModel):
    """One sealed, zero-write semantic instruction discrimination report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    contract_version: Annotated[int, Field(ge=1)]
    record_count: Annotated[int, Field(ge=0)]
    item_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    comparison_complete: bool
    diagnostic_event_ids: tuple[_EventId, ...]
    constructed_event_ids: tuple[_EventId, ...]
    items: tuple[DiscriminationObservationItem, ...]
    signal_comparisons: tuple[DiscriminationSignalComparison, ...]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.item_count != len(self.items):
            raise ValueError("Report item count drifted from its items.")
        if self.record_count * 2 != self.item_count:
            raise ValueError("A report carries exactly two items per record.")
        if self.canonical_write_count != 0 or self.proposed_change_count != 0:
            raise ValueError("A discrimination report records zero writes and zero proposals.")
        pair_ids = tuple(item.pair_id for item in self.items)
        if pair_ids != tuple(sorted(set(pair_ids))):
            raise ValueError("Report items must be ordered and distinct by pair ID.")
        if self.model_execution_count != sum(1 for item in self.items if item.model_invoked):
            raise ValueError("Report model execution count drifted from its items.")
        if self.model_execution_count > self.item_count:
            raise ValueError("Report model executions exceed the one-per-pair budget.")
        if self.diagnostic_event_ids != tuple(sorted(set(self.diagnostic_event_ids))):
            raise ValueError("Diagnostic event IDs must be ordered and distinct.")
        if self.constructed_event_ids != tuple(sorted(set(self.constructed_event_ids))):
            raise ValueError("Constructed event IDs must be ordered and distinct.")
        if set(self.diagnostic_event_ids) & set(self.constructed_event_ids):
            raise ValueError("Diagnostic and constructed groups must be disjoint.")
        expected_event_ids = tuple(
            sorted(set(self.diagnostic_event_ids) | set(self.constructed_event_ids))
        )
        observed_event_ids = tuple(sorted({item.event_id for item in self.items}))
        if observed_event_ids != expected_event_ids:
            raise ValueError("Report items drifted from the declared groups.")
        for event_id in expected_event_ids:
            pair_variants = tuple(item.variant for item in self.items if item.event_id == event_id)
            if pair_variants != (
                InstructionVariant.FORMAT_ONLY,
                InstructionVariant.SEMANTIC,
            ):
                raise ValueError(
                    "A record must carry exactly one format-only and one semantic pair."
                )
        if self.comparison_complete != all(
            item.outcome is TerminalOutcome.ANSWERED for item in self.items
        ):
            raise ValueError("Comparison completeness drifted from the item outcomes.")
        expected_comparisons = tuple(
            (signal, group)
            for signal in _INSTRUCTION_SENSITIVE_SIGNALS
            for group in (DiscriminationGroup.DIAGNOSTIC, DiscriminationGroup.CONSTRUCTED)
        )
        observed_comparisons = tuple(
            (comparison.signal, comparison.group) for comparison in self.signal_comparisons
        )
        if observed_comparisons != expected_comparisons:
            raise ValueError("Signal comparisons must cover the sensitive signals in group order.")
        recomputed = compute_discrimination_comparisons(
            items=self.items,
            diagnostic_event_ids=self.diagnostic_event_ids,
            constructed_event_ids=self.constructed_event_ids,
        )
        if self.signal_comparisons != recomputed:
            raise ValueError("Discrimination comparisons differ from the report items.")
        return self


def discrimination_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one report, excluding its own fingerprint."""
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


def build_discrimination_report(
    *,
    contract: SemanticSelectionContract,
    records: tuple[ReferencePolicyRecord, ...],
    items: tuple[DiscriminationObservationItem, ...],
) -> DiscriminationReport:
    """Assemble and seal the report with zero canonical writes and zero proposals."""
    ordered_items = tuple(sorted(items, key=lambda item: item.pair_id))
    diagnostic = tuple(
        sorted(record.event_id for record in records if record.event_id in DIAGNOSTIC_EVENT_IDS)
    )
    constructed = tuple(
        sorted(record.event_id for record in records if record.event_id not in DIAGNOSTIC_EVENT_IDS)
    )
    model_execution_count = sum(1 for item in ordered_items if item.model_invoked)
    complete = all(item.outcome is TerminalOutcome.ANSWERED for item in ordered_items)
    comparisons = compute_discrimination_comparisons(
        items=ordered_items,
        diagnostic_event_ids=diagnostic,
        constructed_event_ids=constructed,
    )
    draft = DiscriminationReport.model_construct(
        contract_version=contract.version,
        record_count=len(records),
        item_count=len(ordered_items),
        model_execution_count=model_execution_count,
        canonical_write_count=0,
        proposed_change_count=0,
        comparison_complete=complete,
        diagnostic_event_ids=diagnostic,
        constructed_event_ids=constructed,
        items=ordered_items,
        signal_comparisons=comparisons,
        result_fingerprint="0" * 64,
    )
    return DiscriminationReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=discrimination_report_fingerprint(draft),
    )


_REPORT_FIELDS = {
    "contract_version",
    "record_count",
    "item_count",
    "model_execution_count",
    "canonical_write_count",
    "proposed_change_count",
    "comparison_complete",
    "diagnostic_event_ids",
    "constructed_event_ids",
    "items",
    "signal_comparisons",
    "result_fingerprint",
}


def rebuild_discrimination_report(payload: dict[str, object]) -> DiscriminationReport:
    """Rebuild one sealed report from its validated persisted payload."""
    if set(payload) != _REPORT_FIELDS:
        raise ValueError("Discrimination report payload has an invalid shape.")
    items_value = payload["items"]
    if not isinstance(items_value, list):
        raise ValueError("Discrimination report items must be a list.")
    items = tuple(
        DiscriminationObservationItem.model_validate(item, strict=False)
        for item in cast(list[object], items_value)
    )
    comparisons_value = payload["signal_comparisons"]
    if not isinstance(comparisons_value, list):
        raise ValueError("Discrimination report comparisons must be a list.")
    comparisons = tuple(
        DiscriminationSignalComparison.model_validate(item, strict=False)
        for item in cast(list[object], comparisons_value)
    )
    report = DiscriminationReport(
        contract_version=cast(int, payload["contract_version"]),
        record_count=cast(int, payload["record_count"]),
        item_count=cast(int, payload["item_count"]),
        model_execution_count=cast(int, payload["model_execution_count"]),
        canonical_write_count=cast(int, payload["canonical_write_count"]),
        proposed_change_count=cast(int, payload["proposed_change_count"]),
        comparison_complete=cast(bool, payload["comparison_complete"]),
        diagnostic_event_ids=tuple(
            cast(str, item) for item in cast(list[object], payload["diagnostic_event_ids"])
        ),
        constructed_event_ids=tuple(
            cast(str, item) for item in cast(list[object], payload["constructed_event_ids"])
        ),
        items=items,
        signal_comparisons=comparisons,
        result_fingerprint=cast(str, payload["result_fingerprint"]),
    )
    if report.result_fingerprint != discrimination_report_fingerprint(report):
        raise ValueError("Discrimination report fingerprint does not match its contents.")
    return report
