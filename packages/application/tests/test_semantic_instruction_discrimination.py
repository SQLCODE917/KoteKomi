"""Focused tests for the R18 semantic instruction discrimination experiment."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from kotekomi_application import (
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    CorrectiveSelectionTask,
    DiscriminationExecutionBinding,
    DiscriminationExecutionRequest,
    DiscriminationGroup,
    DiscriminationObservationItem,
    DiscriminationSignalComparison,
    DiscriminationVerdict,
    ExecutionSetting,
    ExperimentalObservation,
    InstructionVariant,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelRuntimeError,
    ModelTaskRequest,
    ModelTaskResponse,
    ObservedAnswer,
    ResidualClosureRoute,
    SemanticSelectionSignalName,
    SemanticSelectionSignalResult,
    TerminalOutcome,
    build_discrimination_report,
    compute_discrimination_comparisons,
    corrective_instruction_for,
    discrimination_pair_id,
    discrimination_report_fingerprint,
    discrimination_signals_from_parsed,
    evaluate_discrimination_observation,
    evaluate_selection,
    frozen_semantic_selection_contract,
    generation_parameters_digest,
    load_observed_answers,
    load_reference_policy_records,
    model_identity_snapshot_digest,
    rebuild_discrimination_item,
    rebuild_discrimination_report,
    render_discrimination_prompts,
    run_discrimination_attempt,
    semantic_instruction,
)
from kotekomi_domain.models import JsonValue
from pydantic import ValidationError

DATA_DIR = Path(__file__).resolve().parents[3] / "data/r17-semantic-selection-contract"

_DIAGNOSTIC = ("AHE-022", "AHE-051")
_CONSTRUCTED = ("AHE-901",)

_EVENT_GRAMMAR = SemanticSelectionSignalName.ANSWER_GRAMMAR
_EVENT_SELECTION = SemanticSelectionSignalName.SEMANTIC_SELECTION
_EVENT_COVERAGE = SemanticSelectionSignalName.BOUNDARY_COVERAGE
_EVENT_ABSTENTION = SemanticSelectionSignalName.ABSTENTION_CORRECTNESS
_EVENT_READINESS = SemanticSelectionSignalName.COMPOSITION_READINESS


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@lru_cache(maxsize=1)
def _contract():
    return frozen_semantic_selection_contract(directory=DATA_DIR)


@lru_cache(maxsize=1)
def _records():
    return load_reference_policy_records(contract=_contract(), directory=DATA_DIR)


def _record(event_id: str):
    return next(record for record in _records() if record.event_id == event_id)


def _frozen_input(event_id: str) -> bytes:
    record = _record(event_id)
    return (DATA_DIR.parents[1] / record.input_binding.input_file.path).read_bytes()


def _frozen_corrective_task(event_id: str) -> CorrectiveSelectionTask:
    """Load the digest-verified frozen R15 corrective task for one Event."""
    record = _record(event_id)
    binding = record.input_binding
    input_path = Path(__file__).resolve().parents[3] / binding.input_file.path
    assert hashlib.sha256(input_path.read_bytes()).hexdigest() == binding.input_file.sha256
    frozen = json.loads(input_path.read_text())
    corrective = CorrectiveSelectionTask.model_validate(frozen["corrective_task"], strict=False)
    assert corrective.closure_route == binding.frozen_route
    return corrective


def _frozen_corrective_body(event_id: str) -> str:
    """Return the frozen corrective task body (Event frame, Passage, Candidates)."""
    corrective = _frozen_corrective_task(event_id)
    return corrective.corrected_prompt[len(corrective.corrected_instruction) + 1 :]


def _identity() -> ModelIdentitySnapshot:
    return ModelIdentitySnapshot(
        name="fixture-model",
        weights_digest="d" * 64,
        runtime="fixture-runtime",
        tokenizer_id="fixture-tokenizer",
    )


_GENERATION = (ExecutionSetting("seed", 17), ExecutionSetting("temperature", 0))


class FakeRuntime:
    def __init__(
        self,
        raw_output: bytes = b"C1",
        *,
        identity: ModelIdentitySnapshot | None = None,
        error: ModelRuntimeError | None = None,
        admission_error: ModelRuntimeError | None = None,
        formatted_input_token_count: int | None = None,
        loaded_context_limit: int = 65_536,
    ) -> None:
        self.identity = identity or _identity()
        self.raw_output = raw_output
        self.error = error
        self.admission_error = admission_error
        self._formatted = formatted_input_token_count
        self._loaded_context_limit = loaded_context_limit
        self.requests: list[ModelTaskRequest] = []
        self.inspections: list[ModelInputInspectionRequest] = []

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return self.identity

    @property
    def task_deadline_seconds(self) -> float:
        return 300.0

    @property
    def tokenizer_id(self) -> str:
        return self.identity.tokenizer_id

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())

    def inspect_model_input(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        self.inspections.append(request)
        if self.admission_error is not None:
            raise self.admission_error
        formatted = (
            self._formatted
            if self._formatted is not None
            else self.count_tokens(request.logical_input)
        )
        return ModelInputMeasurement(
            model_identity_digest=model_identity_snapshot_digest(request.model_identity),
            runtime_identity=self.identity.runtime,
            model_instance_id=self.identity.name,
            tokenizer_id=self.tokenizer_id,
            prompt_template_identity="fixture_no_prompt_template_v1",
            logical_input_digest=request.logical_input_digest,
            formatted_input_digest=request.logical_input_digest,
            formatted_input_token_count=formatted,
            loaded_context_limit=self._loaded_context_limit,
        )

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        if self.error is not None:
            raise self.error
        receipt = ModelExecutionReceipt(
            model_identity_digest=model_identity_snapshot_digest(
                task.execution_spec.model_identity
            ),
            generation_parameters_digest=generation_parameters_digest(
                task.execution_spec.generation_parameters
            ),
            rendered_input_digest=task.rendered_input_digest,
            input_token_count=task.input_admission.formatted_input_token_count,
            output_token_count=None,
        )
        return ModelTaskResponse(self.raw_output, receipt, None)


def _signal_results(
    *,
    grammar: str = "valid",
    semantic: str = "met",
    coverage: str = "met",
    abstention: str = "not_applicable",
    readiness: str = "ready",
) -> tuple[SemanticSelectionSignalResult, ...]:
    return (
        SemanticSelectionSignalResult(name=_EVENT_GRAMMAR, value=grammar, explanation="x"),
        SemanticSelectionSignalResult(name=_EVENT_SELECTION, value=semantic, explanation="x"),
        SemanticSelectionSignalResult(name=_EVENT_COVERAGE, value=coverage, explanation="x"),
        SemanticSelectionSignalResult(name=_EVENT_ABSTENTION, value=abstention, explanation="x"),
        SemanticSelectionSignalResult(name=_EVENT_READINESS, value=readiness, explanation="x"),
    )


def _parsed(
    event_id: str, status: ConstituentSelectionStatus, indexes: tuple[int, ...] = ()
) -> ConstituentSelectionAnswer:
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=status,
        selected_label_indexes=indexes,
    )


_RECEIPT: dict[str, JsonValue] = {
    "model_identity_digest": "d" * 64,
    "generation_parameters_digest": "e" * 64,
    "rendered_input_digest": "f" * 64,
    "input_token_count": 10,
    "output_token_count": 1,
    "output_token_probabilities": [],
}


def _observation(
    event_id: str, route: ResidualClosureRoute, variant: InstructionVariant
) -> ExperimentalObservation:
    return ExperimentalObservation(
        observation_id=f"obs_{event_id}_{variant.value}",
        event_id=event_id,
        route=route,
        variant=variant,
        review_status="unreviewed_experimental",
        model_identity_digest="d" * 64,
        generation_parameters_digest="e" * 64,
        rendered_input_digest="f" * 64,
        raw_response_sha256=_digest("C1"),
        receipt=_RECEIPT,
        parsed_answer=_parsed(event_id, ConstituentSelectionStatus.SELECTED, (1,)),
    )


def _route(event_id: str) -> ResidualClosureRoute:
    if event_id == "AHE-022":
        return ResidualClosureRoute.LABEL_ONLY_RESELECTION
    return ResidualClosureRoute.BEST_CHOICE_RESELECTION


def _answered_item(
    event_id: str,
    variant: InstructionVariant,
    *,
    grammar: str = "valid",
    semantic: str = "met",
    coverage: str = "met",
    abstention: str = "not_applicable",
    readiness: str = "ready",
) -> DiscriminationObservationItem:
    return DiscriminationObservationItem(
        pair_id=discrimination_pair_id(event_id=event_id, variant=variant),
        event_id=event_id,
        route=_route(event_id),
        variant=variant,
        outcome=TerminalOutcome.ANSWERED,
        model_invoked=True,
        observation=_observation(event_id, _route(event_id), variant),
        signals=_signal_results(
            grammar=grammar,
            semantic=semantic,
            coverage=coverage,
            abstention=abstention,
            readiness=readiness,
        ),
    )


def _blocked_item(event_id: str, variant: InstructionVariant) -> DiscriminationObservationItem:
    return DiscriminationObservationItem(
        pair_id=discrimination_pair_id(event_id=event_id, variant=variant),
        event_id=event_id,
        route=_route(event_id),
        variant=variant,
        outcome=TerminalOutcome.BLOCKED,
        model_invoked=False,
        error="complete_request_exceeds_context_budget",
    )


def _request(
    event_id: str = "AHE-022", variant: InstructionVariant = InstructionVariant.FORMAT_ONLY
) -> DiscriminationExecutionRequest:
    record = _record(event_id)
    rendered = render_discrimination_prompts(
        record=record, contract=_contract(), frozen_input=_frozen_input(event_id)
    )
    prompt = rendered[0] if variant is InstructionVariant.FORMAT_ONLY else rendered[1]
    return DiscriminationExecutionRequest(
        observation_id="obs_1",
        event_id=event_id,
        route=record.input_binding.frozen_route,
        variant=variant,
        prompt=prompt.prompt,
        prompt_sha256=prompt.prompt_sha256,
        prepared_prompt=prompt,
        task=record.task,
        policy_record=record,
        model_profile_id="fixture-profile",
        model_identity=_identity(),
        generation_parameters=_GENERATION,
        model_run_id="mrn_x",
        extraction_task_id="ext_x",
        configured_context_limit=32_768,
        reserved_output_tokens=100,
        safety_margin_tokens=50,
        prompt_id="fixture_prompt_v1",
        prompt_digest="a" * 64,
        schema_id="fixture_schema_v1",
        schema_digest="b" * 64,
        context_manifest_id="cm_fixture",
        context_manifest_digest="c" * 64,
        output_contract_version="fixture_contract_v1",
    )


# --- Renderer (AC-R18-INS) -----------------------------------------------------


def test_renderer_emits_two_prompts_with_byte_identical_body() -> None:
    record = _record("AHE-022")
    format_prompt, semantic_prompt = render_discrimination_prompts(
        record=record, contract=_contract(), frozen_input=_frozen_input(record.event_id)
    )
    assert format_prompt.pair_id == "AHE-022::format_only"
    assert semantic_prompt.pair_id == "AHE-022::semantic"
    assert format_prompt.body_sha256 == semantic_prompt.body_sha256
    assert format_prompt.route is record.input_binding.frozen_route
    body = _frozen_corrective_body("AHE-022")
    assert "Eligibility" not in body
    assert format_prompt.prompt.endswith("\n" + body)
    assert semantic_prompt.prompt.endswith("\n" + body)


def test_format_prompt_equals_frozen_r15_corrective_task() -> None:
    record = _record("AHE-022")
    format_prompt, _ = render_discrimination_prompts(
        record=record, contract=_contract(), frozen_input=_frozen_input(record.event_id)
    )
    route = record.input_binding.frozen_route
    corrective = _frozen_corrective_task("AHE-022")
    body = corrective.corrected_prompt[len(corrective.corrected_instruction) + 1 :]
    assert "Eligibility" not in format_prompt.prompt
    assert format_prompt.prompt == corrective_instruction_for(route) + "\n" + body
    assert format_prompt.prompt == corrective.corrected_prompt


def test_every_format_only_prompt_equals_its_archived_corrective_prompt() -> None:
    contract = _contract()
    for record in _records():
        format_prompt, semantic_prompt = render_discrimination_prompts(
            record=record, contract=contract, frozen_input=_frozen_input(record.event_id)
        )
        corrective = _frozen_corrective_task(record.event_id)
        assert format_prompt.prompt == corrective.corrected_prompt
        assert "Eligibility" not in format_prompt.prompt
        assert format_prompt.body_sha256 == semantic_prompt.body_sha256
        body = corrective.corrected_prompt[len(corrective.corrected_instruction) + 1 :]
        assert format_prompt.prompt.endswith("\n" + body)
        assert (
            semantic_prompt.prompt
            == semantic_instruction(route=corrective.closure_route, contract=contract) + "\n" + body
        )
        assert format_prompt.body_sha256 == _digest(body)


def test_renderer_does_not_derive_body_from_r17_semantic_task() -> None:
    record = _record("AHE-022")
    semantic_task_text = "Additional semantic instruction.\n" + record.task.rendered_input
    changed_task = record.task.model_copy(
        update={
            "rendered_input": semantic_task_text,
            "rendered_input_sha256": _digest(semantic_task_text),
        }
    )
    changed_record = record.model_copy(update={"task": changed_task})
    format_prompt, _ = render_discrimination_prompts(
        record=changed_record, contract=_contract(), frozen_input=_frozen_input(record.event_id)
    )
    assert format_prompt.prompt == _frozen_corrective_task(record.event_id).corrected_prompt


def test_renderer_rejects_frozen_input_digest_drift() -> None:
    record = _record("AHE-022")
    with pytest.raises(ValueError, match="Discrimination frozen input digest drifted"):
        render_discrimination_prompts(
            record=record,
            contract=_contract(),
            frozen_input=_frozen_input(record.event_id) + b"\n",
        )


def test_renderer_rejects_frozen_corrective_task_for_another_event() -> None:
    record = _record("AHE-022")
    other_binding = _record("AHE-901").input_binding
    changed_binding = record.input_binding.model_copy(
        update={"input_file": other_binding.input_file}
    )
    changed_record = record.model_copy(update={"input_binding": changed_binding})
    with pytest.raises(ValueError, match="corrective task references a different Event"):
        render_discrimination_prompts(
            record=changed_record, contract=_contract(), frozen_input=_frozen_input("AHE-901")
        )


def test_renderer_rejects_frozen_corrective_task_route_mismatch() -> None:
    record = _record("AHE-022")
    changed_binding = record.input_binding.model_copy(
        update={"frozen_route": ResidualClosureRoute.BEST_CHOICE_RESELECTION}
    )
    changed_record = record.model_copy(update={"input_binding": changed_binding})
    with pytest.raises(ValueError, match="corrective task route differs from its frozen route"):
        render_discrimination_prompts(
            record=changed_record,
            contract=_contract(),
            frozen_input=_frozen_input(record.event_id),
        )


def test_semantic_instruction_names_only_eligibility_and_complete_set_rules() -> None:
    contract = _contract()
    label_only = ResidualClosureRoute.LABEL_ONLY_RESELECTION
    prefix = semantic_instruction(route=label_only, contract=contract)
    assert prefix.startswith(corrective_instruction_for(label_only))
    assert contract.eligibility_rule in prefix
    for rule in contract.complete_selected_set_rules:
        assert rule in prefix
    assert contract.none_rule not in prefix
    for rule in contract.canonical_boundary_rules:
        assert rule not in prefix


def test_renderer_produces_exactly_twenty_two_prompts() -> None:
    contract = _contract()
    prompts = [
        prompt
        for record in _records()
        for prompt in render_discrimination_prompts(
            record=record, contract=contract, frozen_input=_frozen_input(record.event_id)
        )
    ]
    assert len(prompts) == 22
    assert len({prompt.pair_id for prompt in prompts}) == 22


# --- Evaluator (AC-R18-EVL) ----------------------------------------------------


def test_evaluator_reproduces_r17_signal_values_for_frozen_answers() -> None:
    contract = _contract()
    records = _records()
    by_event = {record.event_id: record for record in records}
    answers = load_observed_answers(contract=contract, directory=DATA_DIR, records=records)
    assert answers
    for answer in answers:
        record = by_event[answer.event_id]
        reviewed = evaluate_selection(
            contract=contract, policy_record=record, observed_answer=answer
        )
        experimental = evaluate_discrimination_observation(
            policy_record=record, route=answer.route, raw_response=answer.raw_response
        )
        reviewed_by_name = {signal.name: signal.value for signal in reviewed}
        experimental_by_name = {signal.name: signal.value for signal in experimental}
        assert experimental_by_name == reviewed_by_name


def test_evaluator_met_for_exact_expected_selected_set() -> None:
    record = _record("AHE-022")
    signals = evaluate_discrimination_observation(
        policy_record=record,
        route=record.input_binding.frozen_route,
        raw_response="C1,C3",
    )
    by_name = {signal.name: signal.value for signal in signals}
    assert by_name[_EVENT_GRAMMAR] == "valid"
    assert by_name[_EVENT_SELECTION] == "met"


def test_evaluator_label_only_rejects_none_as_malformed() -> None:
    record = _record("AHE-022")
    signals = evaluate_discrimination_observation(
        policy_record=record, route=record.input_binding.frozen_route, raw_response="NONE"
    )
    by_name = {signal.name: signal.value for signal in signals}
    assert by_name[_EVENT_GRAMMAR] == "invalid"
    assert by_name[_EVENT_SELECTION] == "not_applicable"


def test_invariant_signals_restate_identically_across_answers() -> None:
    record = _record("AHE-051")
    route = record.input_binding.frozen_route
    selected = evaluate_discrimination_observation(
        policy_record=record, route=route, raw_response="C3"
    )
    abstained = evaluate_discrimination_observation(
        policy_record=record, route=route, raw_response="NONE"
    )
    selected_by_name = {signal.name: signal.value for signal in selected}
    abstained_by_name = {signal.name: signal.value for signal in abstained}
    assert selected_by_name[_EVENT_COVERAGE] == abstained_by_name[_EVENT_COVERAGE]
    assert selected_by_name[_EVENT_READINESS] == abstained_by_name[_EVENT_READINESS]


def test_ahe051_correct_c3_keeps_gap_and_not_ready() -> None:
    record = _record("AHE-051")
    signals = evaluate_discrimination_observation(
        policy_record=record, route=record.input_binding.frozen_route, raw_response="C3"
    )
    by_name = {signal.name: signal.value for signal in signals}
    assert by_name[_EVENT_SELECTION] == "met"
    assert by_name[_EVENT_COVERAGE] == "gap"
    assert by_name[_EVENT_READINESS] == "not_ready"


def test_ahe022_composition_readiness_is_not_ready() -> None:
    record = _record("AHE-022")
    signals = evaluate_discrimination_observation(
        policy_record=record,
        route=record.input_binding.frozen_route,
        raw_response="C1,C3",
    )
    by_name = {signal.name: signal.value for signal in signals}
    assert by_name[_EVENT_SELECTION] == "met"
    assert by_name[_EVENT_READINESS] == "not_ready"


# --- Experimental observation (AC-R18-OBS) -------------------------------------


def test_experimental_observation_carries_no_human_review_metadata() -> None:
    observation = _observation("AHE-022", _route("AHE-022"), InstructionVariant.FORMAT_ONLY)
    assert observation.review_status == "unreviewed_experimental"
    field_names = set(ExperimentalObservation.model_fields)
    for review_field in (
        "reviewer_identity",
        "review_mode",
        "review_date",
        "review_commit",
        "review_evidence",
    ):
        assert review_field not in field_names


def test_reviewed_observed_answer_still_requires_review_metadata() -> None:
    with pytest.raises(ValidationError):
        ObservedAnswer.model_validate({})


def test_blocked_item_rejects_an_observation() -> None:
    with pytest.raises(ValidationError):
        DiscriminationObservationItem(
            pair_id="AHE-022::format_only",
            event_id="AHE-022",
            route=_route("AHE-022"),
            variant=InstructionVariant.FORMAT_ONLY,
            outcome=TerminalOutcome.BLOCKED,
            model_invoked=False,
            error="complete_request_exceeds_context_budget",
            observation=_observation("AHE-022", _route("AHE-022"), InstructionVariant.FORMAT_ONLY),
        )


# --- Admission and terminals (AC-R18-BUDGET, AC-R18-OBS-02) --------------------


def _run(
    request: DiscriminationExecutionRequest, runtime: FakeRuntime
) -> DiscriminationObservationItem:
    def store_response(raw_output: bytes) -> str:
        return hashlib.sha256(raw_output).hexdigest()

    return run_discrimination_attempt(request, runtime=runtime, store_response=store_response)


def _assert_invalid_execution_request(
    request: DiscriminationExecutionRequest, message: str
) -> None:
    runtime = FakeRuntime(raw_output=b"NONE")
    stored: list[bytes] = []

    def store_response(raw: bytes) -> str:
        stored.append(raw)
        return hashlib.sha256(raw).hexdigest()

    with pytest.raises(ValueError, match=message):
        run_discrimination_attempt(request, runtime=runtime, store_response=store_response)
    assert runtime.inspections == []
    assert runtime.requests == []
    assert stored == []


def test_execution_rejects_route_override_before_admission() -> None:
    request = replace(_request(), route=ResidualClosureRoute.BEST_CHOICE_RESELECTION)
    _assert_invalid_execution_request(request, "execution route differs from its frozen route")


def test_execution_rejects_request_event_mismatch_before_admission() -> None:
    request = replace(_request(), event_id="AHE-051")
    _assert_invalid_execution_request(request, "execution Event differs from its policy record")


def test_execution_rejects_another_events_task_before_admission() -> None:
    request = replace(_request(), task=_record("AHE-051").task)
    _assert_invalid_execution_request(
        request, "execution task Event differs from its policy record"
    )


def test_execution_rejects_same_event_task_label_drift_before_admission() -> None:
    request = _request()
    changed_task = request.task.model_copy(update={"constituent_labels": ("C999",)})
    _assert_invalid_execution_request(
        replace(request, task=changed_task), "execution task differs from its policy task"
    )


def test_execution_rejects_another_events_policy_before_admission() -> None:
    request = replace(_request(), policy_record=_record("AHE-051"))
    _assert_invalid_execution_request(request, "execution Event differs from its policy record")


def test_execution_rejects_another_events_prepared_prompt_before_admission() -> None:
    request = replace(_request(), prepared_prompt=_request("AHE-051").prepared_prompt)
    _assert_invalid_execution_request(request, "execution Event differs from its policy record")


def test_execution_rejects_prepared_route_override_before_admission() -> None:
    request = _request()
    prepared = request.prepared_prompt.model_copy(
        update={"route": ResidualClosureRoute.BEST_CHOICE_RESELECTION}
    )
    _assert_invalid_execution_request(
        replace(request, prepared_prompt=prepared), "execution route differs from its frozen route"
    )


def test_execution_rejects_variant_mismatch_before_admission() -> None:
    request = replace(_request(), variant=InstructionVariant.SEMANTIC)
    _assert_invalid_execution_request(request, "execution variant differs from its prepared prompt")


def test_execution_rejects_altered_prompt_with_recomputed_digest_before_admission() -> None:
    request = _request()
    altered = request.prompt + "\nAdditional instruction."
    request = replace(request, prompt=altered, prompt_sha256=_digest(altered))
    _assert_invalid_execution_request(request, "execution prompt differs from its prepared prompt")


def test_execution_revalidates_prepared_prompt_digest_before_admission() -> None:
    request = _request()
    prepared = request.prepared_prompt.model_copy(update={"prompt_sha256": "0" * 64})
    _assert_invalid_execution_request(
        replace(request, prepared_prompt=prepared), "Prepared prompt digest does not match"
    )


def test_execution_revalidates_prepared_pair_id_before_admission() -> None:
    request = _request()
    prepared = request.prepared_prompt.model_copy(update={"pair_id": "AHE-051::format_only"})
    _assert_invalid_execution_request(
        replace(request, prepared_prompt=prepared), "Prepared prompt pair ID differs"
    )


@pytest.mark.parametrize("variant", list(InstructionVariant))
@pytest.mark.parametrize(("event_id", "raw"), [("AHE-022", b"C1,C3"), ("AHE-051", b"NONE")])
def test_execution_preserves_frozen_route_grammar_for_both_variants(
    variant: InstructionVariant, event_id: str, raw: bytes
) -> None:
    runtime = FakeRuntime(raw_output=raw)
    item = _run(_request(event_id, variant), runtime)
    assert len(runtime.inspections) == 1
    assert len(runtime.requests) == 1
    assert item.outcome is TerminalOutcome.ANSWERED
    assert item.observation is not None
    assert item.observation.parsed_answer.event_id == event_id
    expected = (
        ConstituentSelectionStatus.SELECTED
        if event_id == "AHE-022"
        else ConstituentSelectionStatus.NONE
    )
    assert item.observation.parsed_answer.status is expected


def test_experimental_evaluation_rejects_route_override() -> None:
    with pytest.raises(ValueError, match="evaluation route differs from its frozen route"):
        evaluate_discrimination_observation(
            policy_record=_record("AHE-022"),
            route=ResidualClosureRoute.BEST_CHOICE_RESELECTION,
            raw_response="NONE",
        )


def test_experimental_signals_reject_cross_event_parsed_answer() -> None:
    with pytest.raises(ValueError, match="parsed answer Event differs from its policy record"):
        discrimination_signals_from_parsed(
            policy_record=_record("AHE-022"),
            parsed=_parsed("AHE-051", ConstituentSelectionStatus.NONE),
        )


def _rebuild_item(
    item: DiscriminationObservationItem, raw_response: bytes | None
) -> DiscriminationObservationItem:
    request = _request()
    prepared = render_discrimination_prompts(
        record=request.policy_record,
        contract=_contract(),
        frozen_input=_frozen_input(request.event_id),
    )[0]
    return rebuild_discrimination_item(
        prepared=prepared,
        policy_record=request.policy_record,
        item=item,
        raw_response=raw_response,
        execution_binding=DiscriminationExecutionBinding(
            model_identity=request.model_identity,
            generation_parameters=request.generation_parameters,
        ),
    )


@pytest.mark.parametrize("raw_response", [b"C1,C3", b"NONE", b",C3,,", b"\xff"])
def test_rebuild_reproduces_answered_and_malformed_responses(raw_response: bytes) -> None:
    item = _run(_request(), FakeRuntime(raw_output=raw_response))
    assert _rebuild_item(item, raw_response) == item


def test_rebuild_rejects_stored_parse_that_disagrees_with_archived_bytes() -> None:
    item = _run(_request(), FakeRuntime(raw_output=b"C1,C3"))
    assert item.observation is not None
    observation = item.observation.model_copy(update={"raw_response_sha256": _digest("NONE")})
    stale = item.model_copy(update={"observation": observation})
    with pytest.raises(ValueError, match="stored parse differs from the archived response"):
        _rebuild_item(stale, b"NONE")


def test_rebuild_rejects_stored_signals_that_disagree_with_frozen_policy() -> None:
    item = _run(_request(), FakeRuntime(raw_output=b"C1,C3"))
    assert item.signals is not None
    signals = tuple(
        signal.model_copy(update={"value": "unmet"}) if signal.name is _EVENT_SELECTION else signal
        for signal in item.signals
    )
    stale = item.model_copy(update={"signals": signals})
    with pytest.raises(ValueError, match="stored signals differ from the recomputed results"):
        _rebuild_item(stale, b"C1,C3")


def test_rebuild_rejects_empty_receipt() -> None:
    item = _run(_request(), FakeRuntime(raw_output=b"C1,C3"))
    assert item.observation is not None
    observation = item.observation.model_copy(update={"receipt": {}})
    with pytest.raises(ValueError, match="receipt payload has an invalid shape"):
        _rebuild_item(item.model_copy(update={"observation": observation}), b"C1,C3")


@pytest.mark.parametrize("location", ["receipt", "observation"])
@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("model_identity_digest", "receipt identity differs from the run binding"),
        (
            "generation_parameters_digest",
            "receipt generation parameters differ from the run binding",
        ),
        ("rendered_input_digest", "receipt input differs from the prepared prompt"),
    ],
)
def test_rebuild_rejects_receipt_binding_drift(location: str, field: str, message: str) -> None:
    item = _run(_request(), FakeRuntime(raw_output=b"C1,C3"))
    assert item.observation is not None
    observation = item.observation
    if location == "receipt":
        receipt = dict(observation.receipt)
        receipt[field] = "0" * 64
        observation = observation.model_copy(update={"receipt": receipt})
    else:
        observation = observation.model_copy(update={field: "0" * 64})
    with pytest.raises(ValueError, match=message):
        _rebuild_item(item.model_copy(update={"observation": observation}), b"C1,C3")


def test_rebuild_rejects_archived_response_digest_drift() -> None:
    item = _run(_request(), FakeRuntime(raw_output=b"C1,C3"))
    with pytest.raises(ValueError, match="archived response digest drifted"):
        _rebuild_item(item, b"C3")


def test_rebuild_rejects_missing_answered_response() -> None:
    item = _run(_request(), FakeRuntime(raw_output=b"C1,C3"))
    with pytest.raises(ValueError, match="requires archived response evidence"):
        _rebuild_item(item, None)


def test_rebuild_preserves_blocked_item_without_response() -> None:
    item = _blocked_item("AHE-022", InstructionVariant.FORMAT_ONLY)
    assert _rebuild_item(item, None) == item
    with pytest.raises(
        ValueError, match="non-answered discrimination item cannot carry a raw response"
    ):
        _rebuild_item(item, b"C1,C3")


def test_blocked_admission_is_terminal_without_execution() -> None:
    runtime = FakeRuntime(formatted_input_token_count=40_000, loaded_context_limit=10_000)
    item = _run(_request("AHE-022"), runtime)
    assert item.outcome is TerminalOutcome.BLOCKED
    assert item.model_invoked is False
    assert runtime.requests == []


def test_runtime_failure_is_terminal_failed() -> None:
    runtime = FakeRuntime(error=ModelRuntimeError("fixture runtime failure"))
    item = _run(_request("AHE-022"), runtime)
    assert item.outcome is TerminalOutcome.FAILED
    assert item.model_invoked is True


def test_admission_error_is_terminal_failed_without_execution() -> None:
    runtime = FakeRuntime(admission_error=ModelRuntimeError("fixture admission failure"))
    item = _run(_request("AHE-022"), runtime)
    assert item.outcome is TerminalOutcome.FAILED
    assert item.model_invoked is False
    assert runtime.requests == []


def test_answered_item_records_one_execution_and_five_signals() -> None:
    runtime = FakeRuntime(raw_output=b"C1,C3")
    item = _run(_request("AHE-022"), runtime)
    assert item.outcome is TerminalOutcome.ANSWERED
    assert item.model_invoked is True
    assert len(runtime.requests) == 1
    assert item.observation is not None
    assert item.observation.review_status == "unreviewed_experimental"
    assert item.signals is not None
    assert [signal.name for signal in item.signals] == [
        _EVENT_GRAMMAR,
        _EVENT_SELECTION,
        _EVENT_COVERAGE,
        _EVENT_ABSTENTION,
        _EVENT_READINESS,
    ]


# --- Verdict (AC-R18-VER) ------------------------------------------------------


def _semantic_pairs(
    semantic_by_pair: dict[tuple[str, InstructionVariant], str],
) -> tuple[DiscriminationObservationItem, ...]:
    items: list[DiscriminationObservationItem] = []
    for event_id in _DIAGNOSTIC + _CONSTRUCTED:
        for variant in (InstructionVariant.FORMAT_ONLY, InstructionVariant.SEMANTIC):
            items.append(
                _answered_item(event_id, variant, semantic=semantic_by_pair[(event_id, variant)])
            )
    return tuple(items)


def _comparison_for(
    items: tuple[DiscriminationObservationItem, ...],
    signal: SemanticSelectionSignalName,
    group: DiscriminationGroup,
) -> DiscriminationSignalComparison:
    for comparison in compute_discrimination_comparisons(
        items=items,
        diagnostic_event_ids=_DIAGNOSTIC,
        constructed_event_ids=_CONSTRUCTED,
    ):
        if comparison.signal is signal and comparison.group is group:
            return comparison
    raise AssertionError("comparison not found")


def test_verdict_improvement_when_semantic_met_and_format_unmet() -> None:
    items = _semantic_pairs(
        {
            ("AHE-022", InstructionVariant.FORMAT_ONLY): "unmet",
            ("AHE-022", InstructionVariant.SEMANTIC): "met",
            ("AHE-051", InstructionVariant.FORMAT_ONLY): "unmet",
            ("AHE-051", InstructionVariant.SEMANTIC): "met",
            ("AHE-901", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-901", InstructionVariant.SEMANTIC): "met",
        }
    )
    comparison = _comparison_for(items, _EVENT_SELECTION, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.verdict is DiscriminationVerdict.IMPROVEMENT
    assert comparison.denominator == 4
    assert comparison.better_pair_count == 2
    assert comparison.worse_pair_count == 0


def test_verdict_regression_when_semantic_unmet_and_format_met() -> None:
    items = _semantic_pairs(
        {
            ("AHE-022", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-022", InstructionVariant.SEMANTIC): "unmet",
            ("AHE-051", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-051", InstructionVariant.SEMANTIC): "unmet",
            ("AHE-901", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-901", InstructionVariant.SEMANTIC): "met",
        }
    )
    comparison = _comparison_for(items, _EVENT_SELECTION, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.verdict is DiscriminationVerdict.REGRESSION
    assert comparison.worse_pair_count == 2
    assert comparison.better_pair_count == 0


def test_verdict_mixed_when_one_record_improves_and_one_regresses() -> None:
    items = _semantic_pairs(
        {
            ("AHE-022", InstructionVariant.FORMAT_ONLY): "unmet",
            ("AHE-022", InstructionVariant.SEMANTIC): "met",
            ("AHE-051", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-051", InstructionVariant.SEMANTIC): "unmet",
            ("AHE-901", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-901", InstructionVariant.SEMANTIC): "met",
        }
    )
    comparison = _comparison_for(items, _EVENT_SELECTION, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.verdict is DiscriminationVerdict.MIXED
    assert comparison.better_pair_count == 1
    assert comparison.worse_pair_count == 1


def test_verdict_inconclusive_when_no_difference() -> None:
    items = _semantic_pairs(
        {
            ("AHE-022", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-022", InstructionVariant.SEMANTIC): "met",
            ("AHE-051", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-051", InstructionVariant.SEMANTIC): "met",
            ("AHE-901", InstructionVariant.FORMAT_ONLY): "met",
            ("AHE-901", InstructionVariant.SEMANTIC): "met",
        }
    )
    comparison = _comparison_for(items, _EVENT_SELECTION, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.verdict is DiscriminationVerdict.INCONCLUSIVE


def test_denominator_keeps_blocked_pair_and_marks_inconclusive() -> None:
    items = (
        _blocked_item("AHE-022", InstructionVariant.FORMAT_ONLY),
        _answered_item("AHE-022", InstructionVariant.SEMANTIC, semantic="met"),
        _answered_item("AHE-051", InstructionVariant.FORMAT_ONLY, semantic="unmet"),
        _answered_item("AHE-051", InstructionVariant.SEMANTIC, semantic="met"),
        _answered_item("AHE-901", InstructionVariant.FORMAT_ONLY, semantic="met"),
        _answered_item("AHE-901", InstructionVariant.SEMANTIC, semantic="met"),
    )
    comparison = _comparison_for(items, _EVENT_SELECTION, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.denominator == 4
    assert comparison.incomplete_pair_count == 1
    assert comparison.verdict is DiscriminationVerdict.INCONCLUSIVE


def test_malformed_pair_is_undecidable_and_inconclusive() -> None:
    items = (
        _answered_item("AHE-022", InstructionVariant.FORMAT_ONLY, semantic="not_applicable"),
        _answered_item("AHE-022", InstructionVariant.SEMANTIC, semantic="met"),
        _answered_item("AHE-051", InstructionVariant.FORMAT_ONLY, semantic="unmet"),
        _answered_item("AHE-051", InstructionVariant.SEMANTIC, semantic="met"),
        _answered_item("AHE-901", InstructionVariant.FORMAT_ONLY, semantic="met"),
        _answered_item("AHE-901", InstructionVariant.SEMANTIC, semantic="met"),
    )
    comparison = _comparison_for(items, _EVENT_SELECTION, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.undecidable_pair_count == 1
    assert comparison.verdict is DiscriminationVerdict.INCONCLUSIVE


def test_answer_grammar_improvement_when_semantic_fixes_malformed() -> None:
    items = (
        _answered_item(
            "AHE-022",
            InstructionVariant.FORMAT_ONLY,
            grammar="invalid",
            semantic="not_applicable",
        ),
        _answered_item("AHE-022", InstructionVariant.SEMANTIC, grammar="valid", semantic="met"),
        _answered_item("AHE-051", InstructionVariant.FORMAT_ONLY, grammar="valid"),
        _answered_item("AHE-051", InstructionVariant.SEMANTIC, grammar="valid"),
        _answered_item("AHE-901", InstructionVariant.FORMAT_ONLY, grammar="valid"),
        _answered_item("AHE-901", InstructionVariant.SEMANTIC, grammar="valid"),
    )
    comparison = _comparison_for(items, _EVENT_GRAMMAR, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.verdict is DiscriminationVerdict.IMPROVEMENT
    assert comparison.better_pair_count == 1


def test_abstention_improvement_when_semantic_justifies() -> None:
    items = (
        _answered_item("AHE-022", InstructionVariant.FORMAT_ONLY, abstention="unjustified"),
        _answered_item("AHE-022", InstructionVariant.SEMANTIC, abstention="justified"),
        _answered_item("AHE-051", InstructionVariant.FORMAT_ONLY, abstention="unjustified"),
        _answered_item("AHE-051", InstructionVariant.SEMANTIC, abstention="justified"),
        _answered_item("AHE-901", InstructionVariant.FORMAT_ONLY, abstention="not_applicable"),
        _answered_item("AHE-901", InstructionVariant.SEMANTIC, abstention="not_applicable"),
    )
    comparison = _comparison_for(items, _EVENT_ABSTENTION, DiscriminationGroup.DIAGNOSTIC)
    assert comparison.verdict is DiscriminationVerdict.IMPROVEMENT
    assert comparison.better_pair_count == 2


def test_verdict_is_per_signal_not_merged() -> None:
    items = (
        _answered_item(
            "AHE-022", InstructionVariant.FORMAT_ONLY, semantic="unmet", grammar="valid"
        ),
        _answered_item("AHE-022", InstructionVariant.SEMANTIC, semantic="met", grammar="invalid"),
        _answered_item("AHE-051", InstructionVariant.FORMAT_ONLY, semantic="met"),
        _answered_item("AHE-051", InstructionVariant.SEMANTIC, semantic="met"),
        _answered_item("AHE-901", InstructionVariant.FORMAT_ONLY, semantic="met"),
        _answered_item("AHE-901", InstructionVariant.SEMANTIC, semantic="met"),
    )
    selection = _comparison_for(items, _EVENT_SELECTION, DiscriminationGroup.DIAGNOSTIC)
    grammar = _comparison_for(items, _EVENT_GRAMMAR, DiscriminationGroup.DIAGNOSTIC)
    assert selection.verdict is DiscriminationVerdict.IMPROVEMENT
    assert grammar.verdict is DiscriminationVerdict.REGRESSION


# --- Report (AC-R18-REP, AC-R18-BUDGET-02) -------------------------------------


def _all_answered_items() -> tuple[DiscriminationObservationItem, ...]:
    items: list[DiscriminationObservationItem] = []
    for record in _records():
        items.append(_answered_item(record.event_id, InstructionVariant.FORMAT_ONLY))
        items.append(_answered_item(record.event_id, InstructionVariant.SEMANTIC))
    return tuple(items)


def test_report_seals_twenty_two_pairs_and_zero_writes() -> None:
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    assert report.record_count == 11
    assert report.item_count == 22
    assert report.model_execution_count == 22
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.comparison_complete is True
    assert report.diagnostic_event_ids == ("AHE-022", "AHE-051")
    assert len(report.constructed_event_ids) == 9
    assert len(report.signal_comparisons) == 6


def test_report_separates_diagnostic_from_constructed() -> None:
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    assert set(report.diagnostic_event_ids) == {"AHE-022", "AHE-051"}
    diagnostic_pairs = {
        item.event_id for item in report.items if item.event_id in report.diagnostic_event_ids
    }
    assert diagnostic_pairs == {"AHE-022", "AHE-051"}
    # each diagnostic record is reported individually with two variants
    for event_id in ("AHE-022", "AHE-051"):
        variants = {item.variant for item in report.items if item.event_id == event_id}
        assert variants == {InstructionVariant.FORMAT_ONLY, InstructionVariant.SEMANTIC}


def test_report_rebuild_roundtrips() -> None:
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    rebuilt = rebuild_discrimination_report(report.model_dump(mode="json"))
    assert rebuilt == report
    assert rebuilt.result_fingerprint == report.result_fingerprint


@pytest.mark.parametrize("comparison_index", range(6))
def test_report_rebuild_rejects_impossible_counts_even_with_recomputed_fingerprint(
    comparison_index: int,
) -> None:
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    payload = report.model_dump(mode="json")
    payload["signal_comparisons"][comparison_index]["format_value_counts"] = {"invalid": 999}
    payload["result_fingerprint"] = discrimination_report_fingerprint(payload)
    with pytest.raises(ValueError, match="comparisons differ from the report items"):
        rebuild_discrimination_report(payload)


@pytest.mark.parametrize(
    "updates",
    [
        {"format_value_counts": {"valid": 1, "invalid": 1}},
        {"semantic_value_counts": {}},
        {"denominator": 999},
        {"better_pair_count": 1, "verdict": "improvement"},
        {"worse_pair_count": 1, "verdict": "regression"},
        {"better_pair_count": 1, "worse_pair_count": 1, "verdict": "mixed"},
        {"undecidable_pair_count": 999},
        {"incomplete_pair_count": 999},
    ],
)
def test_report_rebuild_rejects_stale_tallies_with_internally_consistent_verdict(
    updates: dict[str, object],
) -> None:
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    payload = report.model_dump(mode="json")
    payload["signal_comparisons"][0].update(updates)
    payload["result_fingerprint"] = discrimination_report_fingerprint(payload)
    with pytest.raises(ValueError, match="comparisons differ from the report items"):
        rebuild_discrimination_report(payload)


def test_report_rebuild_rejects_comparisons_that_ignore_changed_item_signals() -> None:
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    payload = report.model_dump(mode="json")
    payload["items"][0]["signals"][1]["value"] = "unmet"
    payload["result_fingerprint"] = discrimination_report_fingerprint(payload)
    with pytest.raises(ValueError, match="comparisons differ from the report items"):
        rebuild_discrimination_report(payload)


def test_report_rebuild_preserves_malformed_pair_tallies() -> None:
    items = list(_all_answered_items())
    first = items[0]
    items[0] = _answered_item(
        first.event_id, first.variant, grammar="invalid", semantic="not_applicable"
    )
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=tuple(items)
    )
    rebuilt = rebuild_discrimination_report(report.model_dump(mode="json"))
    assert rebuilt == report
    selection = next(
        comparison
        for comparison in rebuilt.signal_comparisons
        if comparison.signal is _EVENT_SELECTION
        and comparison.group is DiscriminationGroup.DIAGNOSTIC
    )
    assert selection.undecidable_pair_count == 1
    assert selection.verdict is DiscriminationVerdict.INCONCLUSIVE
    assert selection.denominator == 4


def test_report_marks_incomplete_when_a_pair_is_terminal() -> None:
    items = list(_all_answered_items())
    items[5] = _blocked_item(items[5].event_id, items[5].variant)
    report = build_discrimination_report(
        contract=_contract(), records=_records(), items=tuple(items)
    )
    assert report.comparison_complete is False
    assert report.model_execution_count == 21
    assert rebuild_discrimination_report(report.model_dump(mode="json")) == report


def test_report_fingerprint_changes_when_terminal_outcome_changes() -> None:
    base = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    items = list(_all_answered_items())
    items[0] = _blocked_item(items[0].event_id, items[0].variant)
    changed = build_discrimination_report(
        contract=_contract(), records=_records(), items=tuple(items)
    )
    assert changed.result_fingerprint != base.result_fingerprint


def test_report_fingerprint_changes_when_signal_result_changes() -> None:
    base = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    items = list(_all_answered_items())
    first = items[0]
    items[0] = _answered_item(first.event_id, first.variant, semantic="unmet")
    changed = build_discrimination_report(
        contract=_contract(), records=_records(), items=tuple(items)
    )
    assert changed.result_fingerprint != base.result_fingerprint


def test_report_fingerprint_changes_when_raw_response_digest_changes() -> None:
    base = build_discrimination_report(
        contract=_contract(), records=_records(), items=_all_answered_items()
    )
    items = list(_all_answered_items())
    first = items[0]
    original = first.observation
    assert original is not None
    changed_observation = ExperimentalObservation(
        observation_id=original.observation_id,
        event_id=original.event_id,
        route=original.route,
        variant=original.variant,
        review_status="unreviewed_experimental",
        model_identity_digest=original.model_identity_digest,
        generation_parameters_digest=original.generation_parameters_digest,
        rendered_input_digest=original.rendered_input_digest,
        raw_response_sha256=_digest("C999"),
        receipt=original.receipt,
        parsed_answer=original.parsed_answer,
    )
    items[0] = DiscriminationObservationItem(
        pair_id=first.pair_id,
        event_id=first.event_id,
        route=first.route,
        variant=first.variant,
        outcome=first.outcome,
        model_invoked=first.model_invoked,
        observation=changed_observation,
        signals=first.signals,
    )
    changed = build_discrimination_report(
        contract=_contract(), records=_records(), items=tuple(items)
    )
    assert changed.result_fingerprint != base.result_fingerprint
