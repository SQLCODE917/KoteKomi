"""Focused Fake-Port and route tests for R16 corrective re-selection execution."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
    CorrectiveReselectionAttempt,
    CorrectiveReselectionExecutionItem,
    CorrectiveReselectionExecutionRequest,
    CorrectiveReselectionOutcome,
    CorrectiveReselectionReport,
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DecontextualizedProposition,
    EventEntityLinguisticToken,
    ExecutionAttemptStatus,
    ExecutionSetting,
    JsonValue,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelRuntimeError,
    ModelTaskRequest,
    ModelTaskResponse,
    ParserConstituent,
    ResidualClosureRoute,
    build_corrective_reselection_report,
    compose_corrective_reselection_answer,
    corrective_reselection_report_fingerprint,
    generation_parameters_digest,
    model_execution_spec_from_payload,
    model_execution_spec_payload,
    model_identity_snapshot_digest,
    parse_best_choice_reselection_answer,
    parse_corrective_reselection_answer,
    parse_label_only_reselection_answer,
    parser_constituent_id,
    rebuild_corrective_reselection_report,
    run_corrective_reselection_attempt,
)
from pydantic import ValidationError

SOURCE = "Acme fired Bob."


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _task(event_id: str, labels: tuple[str, ...]) -> ConstituentSelectionTask:
    rendered = (
        "Return a comma-separated subset of the Candidate labels, or NONE.\n"
        f"Event: {event_id}\n"
        f"Passage:\n{SOURCE}\n"
        "Candidates:\n" + "\n".join(f"{label}: sample" for label in labels)
    )
    return ConstituentSelectionTask(
        event_id=event_id,
        source_text_sha256=_digest(SOURCE),
        source_text=SOURCE,
        constituent_labels=labels,
        rendered_input=rendered,
        rendered_input_sha256=_digest(rendered),
    )


def _labels(count: int) -> tuple[str, ...]:
    return tuple(f"C{ordinal}" for ordinal in range(1, count + 1))


def _identity() -> ModelIdentitySnapshot:
    return ModelIdentitySnapshot(
        name="fixture-model",
        weights_digest="d" * 64,
        runtime="fixture-runtime",
        tokenizer_id="fixture-tokenizer",
        determinism_settings=(ExecutionSetting("temperature", 0),),
    )


_GENERATION = (ExecutionSetting("seed", 17), ExecutionSetting("temperature", 0))


def _tokens() -> tuple[EventEntityLinguisticToken, ...]:
    return (
        EventEntityLinguisticToken(
            token_id="t1",
            sentence_id="s1",
            text="Acme",
            start=0,
            end=4,
            lemma="acme",
            part_of_speech="PROPN",
            dependency_relation="nsubj",
            head_token_id="t2",
        ),
        EventEntityLinguisticToken(
            token_id="t2",
            sentence_id="s1",
            text="fired",
            start=5,
            end=10,
            lemma="fire",
            part_of_speech="VERB",
            dependency_relation="ROOT",
            head_token_id=None,
        ),
        EventEntityLinguisticToken(
            token_id="t3",
            sentence_id="s1",
            text="Bob",
            start=11,
            end=14,
            lemma="bob",
            part_of_speech="PROPN",
            dependency_relation="dobj",
            head_token_id="t2",
        ),
    )


def _subject_inventory(event_id: str) -> ConstituentCandidateInventory:
    acme = ParserConstituent(
        constituent_id=parser_constituent_id(_digest(SOURCE), 0, 4),
        event_id=event_id,
        source_text_sha256=_digest(SOURCE),
        constituent_range=AttachmentSourceRange(start=0, end=4, text="Acme"),
        token_ids=("t1",),
    )
    return ConstituentCandidateInventory(
        event_id=event_id,
        source_text_sha256=_digest(SOURCE),
        constituents=(acme,),
    )


def _selected(event_id: str, *indexes: int) -> ConstituentSelectionAnswer:
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=ConstituentSelectionStatus.SELECTED,
        selected_label_indexes=tuple(sorted(indexes)),
    )


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


def _request(
    *,
    event_id: str = "AHE-022",
    route: ResidualClosureRoute = ResidualClosureRoute.LABEL_ONLY_RESELECTION,
    corrected_prompt: str = "Return the corrected label.",
    task: ConstituentSelectionTask | None = None,
    inventory: ConstituentCandidateInventory | None = None,
    identity: ModelIdentitySnapshot | None = None,
) -> CorrectiveReselectionExecutionRequest:
    task = task or _task(event_id, _labels(3))
    return CorrectiveReselectionExecutionRequest(
        attempt_id="atc_" + "a" * 24,
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        event_id=event_id,
        closure_route=route,
        corrected_prompt=corrected_prompt,
        corrected_prompt_sha256=_digest(corrected_prompt),
        task=task,
        inventory=inventory or _subject_inventory(event_id),
        trigger_head_start=5,
        trigger_head_end=10,
        tokens=_tokens(),
        entities=(),
        model_profile_id="fixture-profile",
        model_identity=identity or _identity(),
        generation_parameters=_GENERATION,
        configured_context_limit=32_768,
        reserved_output_tokens=100,
        safety_margin_tokens=50,
        prompt_id="fixture_prompt_v1",
        prompt_digest="e" * 64,
        schema_id="fixture_schema_v1",
        schema_digest="f" * 64,
        context_manifest_id="cm_fixture",
        context_manifest_digest="c" * 64,
        output_contract_version="fixture_contract_v1",
    )


class FakeRuntime:
    def __init__(
        self,
        raw_output: bytes = b"C1",
        *,
        identity: ModelIdentitySnapshot | None = None,
        receipt: ModelExecutionReceipt | None = None,
        error: ModelRuntimeError | None = None,
        admission_error: ModelRuntimeError | None = None,
        formatted_input_token_count: int | None = None,
        loaded_context_limit: int = 65_536,
    ) -> None:
        self.identity = identity or _identity()
        self.raw_output = raw_output
        self._receipt = receipt
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
        receipt = self._receipt or ModelExecutionReceipt(
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


# --- Label-only answer grammar --------------------------------------------------


def test_label_only_accepts_multiple_distinct_labels() -> None:
    answer = parse_label_only_reselection_answer("C1, C2", _task("AHE-022", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.SELECTED
    assert answer.selected_label_indexes == (1, 2)


def test_label_only_permits_spaces_and_tabs_around_commas() -> None:
    answer = parse_label_only_reselection_answer("C1 ,\tC2", _task("AHE-022", _labels(3)))
    assert answer.selected_label_indexes == (1, 2)


def test_label_only_orders_indexes_by_frozen_candidate_list() -> None:
    answer = parse_label_only_reselection_answer("C3, C1", _task("AHE-022", _labels(3)))
    assert answer.selected_label_indexes == (1, 3)


def test_label_only_rejects_none() -> None:
    answer = parse_label_only_reselection_answer("NONE", _task("AHE-022", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_label_only_rejects_foreign_label() -> None:
    answer = parse_label_only_reselection_answer("C9", _task("AHE-022", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_label_only_rejects_duplicate_label() -> None:
    answer = parse_label_only_reselection_answer("C1, C1", _task("AHE-022", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_label_only_rejects_empty_element() -> None:
    answer = parse_label_only_reselection_answer("C1,,C2", _task("AHE-022", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_label_only_rejects_lowercase_label() -> None:
    answer = parse_label_only_reselection_answer("c1", _task("AHE-022", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_label_only_rejects_non_grammar_character() -> None:
    answer = parse_label_only_reselection_answer("C1, C2!", _task("AHE-022", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


# --- Best-choice answer grammar --------------------------------------------------


def test_best_choice_accepts_single_label() -> None:
    answer = parse_best_choice_reselection_answer("C2", _task("AHE-051", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.SELECTED
    assert answer.selected_label_indexes == (2,)


def test_best_choice_accepts_none() -> None:
    answer = parse_best_choice_reselection_answer("NONE", _task("AHE-051", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.NONE
    assert answer.selected_label_indexes == ()


def test_best_choice_rejects_multiple_labels() -> None:
    answer = parse_best_choice_reselection_answer("C1, C2", _task("AHE-051", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_best_choice_rejects_mixed_none() -> None:
    answer = parse_best_choice_reselection_answer("NONE, C1", _task("AHE-051", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_best_choice_rejects_foreign_label() -> None:
    answer = parse_best_choice_reselection_answer("C9", _task("AHE-051", _labels(3)))
    assert answer.status is ConstituentSelectionStatus.REJECTED


def test_dispatch_selects_route_grammar() -> None:
    task = _task("AHE-022", _labels(3))
    assert (
        parse_corrective_reselection_answer(
            "C1", task, ResidualClosureRoute.LABEL_ONLY_RESELECTION
        ).status
        is ConstituentSelectionStatus.SELECTED
    )
    assert (
        parse_corrective_reselection_answer(
            "NONE", task, ResidualClosureRoute.BEST_CHOICE_RESELECTION
        ).status
        is ConstituentSelectionStatus.NONE
    )


# --- Composition -----------------------------------------------------------------


def test_compose_returns_none_for_rejected_answer() -> None:
    result = compose_corrective_reselection_answer(
        answer=_rejected("AHE-022"),
        source_text=SOURCE,
        source_text_sha256=_digest(SOURCE),
        inventory=_subject_inventory("AHE-022"),
        trigger_head_start=5,
        trigger_head_end=10,
        tokens=_tokens(),
        entities=(),
    )
    assert result is None


def test_compose_returns_none_for_none_answer() -> None:
    result = compose_corrective_reselection_answer(
        answer=_none("AHE-051"),
        source_text=SOURCE,
        source_text_sha256=_digest(SOURCE),
        inventory=_subject_inventory("AHE-051"),
        trigger_head_start=5,
        trigger_head_end=10,
        tokens=_tokens(),
        entities=(),
    )
    assert result is None


def test_compose_selected_with_empty_entities_yields_subject_unavailable_hold() -> None:
    result = compose_corrective_reselection_answer(
        answer=_selected("AHE-022", 1),
        source_text=SOURCE,
        source_text_sha256=_digest(SOURCE),
        inventory=_subject_inventory("AHE-022"),
        trigger_head_start=5,
        trigger_head_end=10,
        tokens=_tokens(),
        entities=(),
    )
    assert result is not None
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE


# --- Execution item data model ---------------------------------------------------


def test_answered_item_requires_a_receipt() -> None:
    with pytest.raises(ValidationError):
        CorrectiveReselectionExecutionItem(
            event_id="AHE-022",
            closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
            attempt_id="atc_" + "a" * 24,
            outcome=CorrectiveReselectionOutcome.REJECTED,
            model_invoked=True,
            raw_response_sha256="0" * 64,
            receipt=None,
            parsed_answer=_rejected("AHE-022"),
            error=None,
        )


def test_blocked_item_rejects_a_receipt() -> None:
    with pytest.raises(ValidationError):
        CorrectiveReselectionExecutionItem(
            event_id="AHE-022",
            closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
            attempt_id="atc_" + "a" * 24,
            outcome=CorrectiveReselectionOutcome.INPUT_BLOCKED,
            model_invoked=False,
            raw_response_sha256=None,
            receipt={"model_identity_digest": "0" * 64},
            error="complete_request_exceeds_context_budget",
        )


def test_answered_item_requires_a_model_invocation() -> None:
    with pytest.raises(ValidationError):
        CorrectiveReselectionExecutionItem(
            event_id="AHE-022",
            closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
            attempt_id="atc_" + "a" * 24,
            outcome=CorrectiveReselectionOutcome.REJECTED,
            model_invoked=False,
            raw_response_sha256="3" * 64,
            receipt=_receipt_payload(),
            parsed_answer=_rejected("AHE-022"),
            error=None,
        )


def test_blocked_item_rejects_a_model_invocation() -> None:
    with pytest.raises(ValidationError):
        CorrectiveReselectionExecutionItem(
            event_id="AHE-022",
            closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
            attempt_id="atc_" + "a" * 24,
            outcome=CorrectiveReselectionOutcome.INPUT_BLOCKED,
            model_invoked=True,
            error="complete_request_exceeds_context_budget",
        )


# --- Report ----------------------------------------------------------------------


def _receipt_payload() -> dict[str, JsonValue]:
    return {
        "model_identity_digest": "a" * 64,
        "generation_parameters_digest": "b" * 64,
        "rendered_input_digest": "c" * 64,
        "input_token_count": 1,
        "output_token_count": None,
        "output_token_probabilities": [],
    }


def _rejected_item(event_id: str) -> CorrectiveReselectionExecutionItem:
    return CorrectiveReselectionExecutionItem(
        event_id=event_id,
        closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
        attempt_id="atc_" + "a" * 24,
        outcome=CorrectiveReselectionOutcome.REJECTED,
        model_invoked=True,
        raw_response_sha256="3" * 64,
        receipt=_receipt_payload(),
        parsed_answer=_rejected(event_id),
        error=None,
    )


def test_report_seals_zero_writes_and_fingerprint() -> None:
    report = build_corrective_reselection_report(
        source_report_fingerprint="1" * 64,
        closure_report_fingerprint="2" * 64,
        items=(),
    )
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == corrective_reselection_report_fingerprint(report)


def test_report_rejects_a_nonzero_write_count() -> None:
    with pytest.raises(ValueError):
        CorrectiveReselectionReport(
            source_report_fingerprint="1" * 64,
            closure_report_fingerprint="2" * 64,
            items=(),
            outcome_counts={outcome.value: 0 for outcome in CorrectiveReselectionOutcome},
            model_execution_count=0,
            canonical_write_count=1,
            proposed_change_count=0,
            result_fingerprint="0" * 64,
        )


def test_report_requires_every_outcome_count_key() -> None:
    with pytest.raises(ValueError):
        CorrectiveReselectionReport(
            source_report_fingerprint="1" * 64,
            closure_report_fingerprint="2" * 64,
            items=(),
            outcome_counts={"input_blocked": 0},
            model_execution_count=0,
            canonical_write_count=0,
            proposed_change_count=0,
            result_fingerprint="0" * 64,
        )


def test_report_items_must_be_ordered_and_distinct() -> None:
    item = _rejected_item("AHE-022")
    with pytest.raises(ValueError):
        CorrectiveReselectionReport(
            source_report_fingerprint="1" * 64,
            closure_report_fingerprint="2" * 64,
            items=(item, item),
            outcome_counts={outcome.value: 0 for outcome in CorrectiveReselectionOutcome},
            model_execution_count=0,
            canonical_write_count=0,
            proposed_change_count=0,
            result_fingerprint="0" * 64,
        )


def test_report_rebuild_roundtrips() -> None:
    report = build_corrective_reselection_report(
        source_report_fingerprint="1" * 64,
        closure_report_fingerprint="2" * 64,
        items=(_rejected_item("AHE-022"),),
    )
    rebuilt = rebuild_corrective_reselection_report(report.model_dump(mode="json"))
    assert rebuilt == report
    assert rebuilt.result_fingerprint == report.result_fingerprint


# --- Execution item impossible-result validation ---------------------------------


def _held_composition(event_id: str) -> DecontextualizedProposition:
    result = compose_corrective_reselection_answer(
        answer=_selected(event_id, 1),
        source_text=SOURCE,
        source_text_sha256=_digest(SOURCE),
        inventory=_subject_inventory(event_id),
        trigger_head_start=5,
        trigger_head_end=10,
        tokens=_tokens(),
        entities=(),
    )
    assert result is not None
    assert result.status is DecontextualizationStatus.HELD
    return result


def test_selected_proposition_rejects_a_held_composition() -> None:
    with pytest.raises(ValidationError):
        CorrectiveReselectionExecutionItem(
            event_id="AHE-022",
            closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
            attempt_id="atc_" + "a" * 24,
            outcome=CorrectiveReselectionOutcome.SELECTED_PROPOSITION,
            model_invoked=True,
            raw_response_sha256="3" * 64,
            receipt=_receipt_payload(),
            parsed_answer=_selected("AHE-022", 1),
            composition_result=_held_composition("AHE-022"),
            error=None,
        )


def test_selected_item_rejects_a_foreign_event_answer() -> None:
    with pytest.raises(ValidationError):
        CorrectiveReselectionExecutionItem(
            event_id="AHE-022",
            closure_route=ResidualClosureRoute.LABEL_ONLY_RESELECTION,
            attempt_id="atc_" + "a" * 24,
            outcome=CorrectiveReselectionOutcome.SELECTED_HOLD,
            model_invoked=True,
            raw_response_sha256="3" * 64,
            receipt=_receipt_payload(),
            parsed_answer=_selected("AHE-051", 1),
            composition_result=_held_composition("AHE-022"),
            error=None,
        )


# --- Execution spec payload round-trip -------------------------------------------


def _execution_spec() -> ModelExecutionSpec:
    return ModelExecutionSpec(
        model_profile_id="fixture-profile",
        model_identity=_identity(),
        generation_parameters=_GENERATION,
        prompt_id="fixture_prompt_v1",
        prompt_digest="e" * 64,
        schema_id="fixture_schema_v1",
        schema_digest="f" * 64,
        context_manifest_id="ctx_fixture",
        context_manifest_digest="a" * 64,
        rendered_input_digest="b" * 64,
        output_contract_version="constituent_selection_label_v1",
    )


def test_execution_spec_payload_roundtrips() -> None:
    spec = _execution_spec()
    parsed = model_execution_spec_from_payload(model_execution_spec_payload(spec))
    assert parsed == spec
    assert model_identity_snapshot_digest(parsed.model_identity) == model_identity_snapshot_digest(
        spec.model_identity
    )
    assert generation_parameters_digest(
        parsed.generation_parameters
    ) == generation_parameters_digest(spec.generation_parameters)


def test_execution_spec_from_payload_rejects_an_empty_record() -> None:
    with pytest.raises(ValueError):
        model_execution_spec_from_payload({})


def test_execution_spec_from_payload_rejects_a_foreign_identity() -> None:
    payload = model_execution_spec_payload(_execution_spec())
    payload["model_identity"] = {"name": "", "determinism_settings": {}}
    with pytest.raises(ValueError):
        model_execution_spec_from_payload(payload)


# --- Fake-Port execution ---------------------------------------------------------


def _store(stored: list[bytes]) -> Callable[[bytes], str]:
    def store(raw_output: bytes) -> str:
        stored.append(raw_output)
        return hashlib.sha256(raw_output).hexdigest()

    return store


def test_corrected_prompt_digest_guard_halts_before_runtime() -> None:
    runtime = FakeRuntime()
    persisted: list[CorrectiveReselectionAttempt] = []
    stored: list[bytes] = []
    request = replace(_request(), corrected_prompt_sha256="0" * 64)
    with pytest.raises(ValueError):
        run_corrective_reselection_attempt(
            request,
            runtime=runtime,
            persist_running_attempt=persisted.append,
            store_response=_store(stored),
        )
    assert runtime.requests == []
    assert stored == []
    assert persisted == []


def test_input_blocked_produces_blocked_item_and_zero_executions() -> None:
    runtime = FakeRuntime(loaded_context_limit=10)
    persisted: list[CorrectiveReselectionAttempt] = []
    result = run_corrective_reselection_attempt(
        _request(),
        runtime=runtime,
        persist_running_attempt=persisted.append,
        store_response=_store([]),
    )
    assert result.item.outcome is CorrectiveReselectionOutcome.INPUT_BLOCKED
    assert result.attempt.status is ExecutionAttemptStatus.INPUT_BLOCKED
    assert result.item.error == "complete_request_exceeds_context_budget"
    assert runtime.requests == []
    assert persisted == []


def test_answered_produces_selected_hold_item_with_one_execution() -> None:
    runtime = FakeRuntime(raw_output=b"C1")
    persisted: list[CorrectiveReselectionAttempt] = []
    stored: list[bytes] = []
    result = run_corrective_reselection_attempt(
        _request(event_id="AHE-022", route=ResidualClosureRoute.LABEL_ONLY_RESELECTION),
        runtime=runtime,
        persist_running_attempt=persisted.append,
        store_response=_store(stored),
    )
    assert result.item.outcome is CorrectiveReselectionOutcome.SELECTED_HOLD
    assert result.item.composition_result is not None
    assert result.item.composition_result.status is DecontextualizationStatus.HELD
    assert len(runtime.requests) == 1
    assert len(persisted) == 1
    assert persisted[0].status is ExecutionAttemptStatus.RUNNING
    assert result.attempt.status is ExecutionAttemptStatus.ANSWERED
    assert stored == [b"C1"]
    assert result.item.raw_response_sha256 == hashlib.sha256(b"C1").hexdigest()


def test_grammar_rejection_answers_without_composition() -> None:
    runtime = FakeRuntime(raw_output=b"NONE")
    persisted: list[CorrectiveReselectionAttempt] = []
    result = run_corrective_reselection_attempt(
        _request(event_id="AHE-022", route=ResidualClosureRoute.LABEL_ONLY_RESELECTION),
        runtime=runtime,
        persist_running_attempt=persisted.append,
        store_response=_store([]),
    )
    assert result.item.outcome is CorrectiveReselectionOutcome.REJECTED
    assert result.item.composition_result is None
    assert result.item.parsed_answer is not None
    assert result.item.parsed_answer.status is ConstituentSelectionStatus.REJECTED
    assert len(runtime.requests) == 1


def test_runtime_failed_produces_failed_item() -> None:
    runtime = FakeRuntime(error=ModelRuntimeError("fixture runtime failure"))
    persisted: list[CorrectiveReselectionAttempt] = []
    result = run_corrective_reselection_attempt(
        _request(),
        runtime=runtime,
        persist_running_attempt=persisted.append,
        store_response=_store([]),
    )
    assert result.item.outcome is CorrectiveReselectionOutcome.RUNTIME_FAILED
    assert result.item.error == "fixture runtime failure"
    assert result.item.parsed_answer is None
    assert result.item.composition_result is None
    assert len(runtime.requests) == 1
    assert len(persisted) == 1
    assert persisted[0].status is ExecutionAttemptStatus.RUNNING


def test_admission_runtime_error_produces_failed_item_and_zero_executions() -> None:
    runtime = FakeRuntime(admission_error=ModelRuntimeError("fixture admission failure"))
    persisted: list[CorrectiveReselectionAttempt] = []
    result = run_corrective_reselection_attempt(
        _request(),
        runtime=runtime,
        persist_running_attempt=persisted.append,
        store_response=_store([]),
    )
    assert result.item.outcome is CorrectiveReselectionOutcome.RUNTIME_FAILED
    assert result.item.error == "fixture admission failure"
    assert result.item.parsed_answer is None
    assert result.item.composition_result is None
    assert result.item.raw_response_sha256 is None
    assert result.attempt.status is ExecutionAttemptStatus.RUNTIME_FAILED
    assert result.attempt.admission is None
    assert result.attempt.execution_spec is None
    assert runtime.requests == []
    assert persisted == []


def test_admission_failure_does_not_inflate_execution_count() -> None:
    admission_failing = FakeRuntime(admission_error=ModelRuntimeError("fixture admission failure"))
    failed = run_corrective_reselection_attempt(
        _request(event_id="AHE-022", route=ResidualClosureRoute.LABEL_ONLY_RESELECTION),
        runtime=admission_failing,
        persist_running_attempt=lambda _attempt: None,
        store_response=_store([]),
    )
    assert failed.item.outcome is CorrectiveReselectionOutcome.RUNTIME_FAILED
    assert failed.item.model_invoked is False
    succeeding = FakeRuntime(raw_output=b"NONE")
    answered = run_corrective_reselection_attempt(
        _request(event_id="AHE-051", route=ResidualClosureRoute.BEST_CHOICE_RESELECTION),
        runtime=succeeding,
        persist_running_attempt=lambda _attempt: None,
        store_response=_store([]),
    )
    assert answered.item.outcome is CorrectiveReselectionOutcome.ABSTAINED
    report = build_corrective_reselection_report(
        source_report_fingerprint="1" * 64,
        closure_report_fingerprint="2" * 64,
        items=(failed.item, answered.item),
    )
    assert report.model_execution_count == 1
    assert report.outcome_counts["runtime_failed"] == 1
    assert report.outcome_counts["abstained"] == 1


def test_first_event_failure_then_second_event_execution() -> None:
    failing = FakeRuntime(error=ModelRuntimeError("first event failure"))
    first = run_corrective_reselection_attempt(
        _request(event_id="AHE-022", route=ResidualClosureRoute.LABEL_ONLY_RESELECTION),
        runtime=failing,
        persist_running_attempt=lambda _attempt: None,
        store_response=_store([]),
    )
    assert first.item.outcome is CorrectiveReselectionOutcome.RUNTIME_FAILED
    succeeding = FakeRuntime(raw_output=b"NONE")
    second = run_corrective_reselection_attempt(
        _request(event_id="AHE-051", route=ResidualClosureRoute.BEST_CHOICE_RESELECTION),
        runtime=succeeding,
        persist_running_attempt=lambda _attempt: None,
        store_response=_store([]),
    )
    assert second.item.outcome is CorrectiveReselectionOutcome.ABSTAINED
    report = build_corrective_reselection_report(
        source_report_fingerprint="1" * 64,
        closure_report_fingerprint="2" * 64,
        items=(first.item, second.item),
    )
    assert report.model_execution_count == 2
    assert report.outcome_counts["runtime_failed"] == 1
    assert report.outcome_counts["abstained"] == 1
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
