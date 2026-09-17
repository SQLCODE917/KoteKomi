from __future__ import annotations

import json
from typing import Any, cast

import pytest
from kotekomi_application import (
    CoreferenceAntecedentInput,
    CoreferenceExecution,
    CoreferenceInput,
    CoreferenceSpanProposal,
    SemanticReferenceCandidateLabelBinding,
    SemanticReferenceCandidateValidationExecution,
    SemanticReferenceCandidateValidationInput,
    SemanticReferenceChallengeExecution,
    SemanticReferenceChallengeInput,
    SemanticReferenceModelTask,
    SemanticReferenceStatus,
    resolve_semantic_reference,
)
from kotekomi_application.semantic_reference_challenge_model_output import (
    SemanticReferenceChallengeSelection,
)
from kotekomi_application.semantic_reference_validation_model_output import (
    SemanticReferenceCandidateValidation,
    SemanticReferenceCandidateVerdict,
)
from kotekomi_domain import ModelRunStatus


class _Tokenizer:
    tokenizer_id = "fixture-tokenizer"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


class _Proposer:
    def __init__(self, clusters: tuple[tuple[tuple[int, int], ...], ...]) -> None:
        self._clusters = clusters

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        payload = {"clusters": self._clusters}
        return CoreferenceExecution(
            model_id="fixture-coref",
            model_revision="1",
            resource_identity="fixture-resource",
            clusters=tuple(
                tuple(CoreferenceSpanProposal(*span) for span in cluster)
                for cluster in self._clusters
            ),
            elapsed_milliseconds=2,
            raw_output=json.dumps(payload).encode(),
        )


class _Challenger:
    def __init__(self, result: str = "first", validation: str = "supported") -> None:
        self.result = result
        self.validation = validation
        self.requests: list[SemanticReferenceChallengeInput] = []
        self.validation_requests: list[SemanticReferenceCandidateValidationInput] = []

    def validate(
        self, request: SemanticReferenceCandidateValidationInput
    ) -> SemanticReferenceCandidateValidationExecution:
        self.validation_requests.append(request)
        parsed = (
            SemanticReferenceCandidateValidation(
                SemanticReferenceCandidateVerdict(self.validation),
                "The source context supports this bounded verdict.",
            )
            if self.validation in {"supported", "unsupported", "unclear"}
            else None
        )
        status = (
            ModelRunStatus.RUNTIME_FAILED
            if self.validation == "failed"
            else ModelRunStatus.INVALID_OUTPUT
            if self.validation == "invalid"
            else ModelRunStatus.SUCCEEDED
        )
        return SemanticReferenceCandidateValidationExecution(
            validation=parsed,
            candidate_id=request.antecedent_candidate.id,
            extraction_task_id="ext_reference_validation",
            model_run_id="mrn_reference_validation",
            model_status=status,
            producer_id="qwen2.5-fixture",
            model_visible_task=b"exact bounded candidate validation task",
            raw_output_sha256="b" * 64 if parsed is not None else None,
        )

    def challenge(
        self, request: SemanticReferenceChallengeInput
    ) -> SemanticReferenceChallengeExecution:
        self.requests.append(request)
        bindings = tuple(
            SemanticReferenceCandidateLabelBinding(f"a{ordinal}", candidate.id)
            for ordinal, candidate in enumerate(request.antecedent_candidates, start=1)
        )
        if self.result == "reversed_bindings":
            bindings = tuple(
                SemanticReferenceCandidateLabelBinding(f"a{ordinal}", candidate.id)
                for ordinal, candidate in enumerate(
                    reversed(request.antecedent_candidates),
                    start=1,
                )
            )
        if self.result == "ambiguous":
            selection = SemanticReferenceChallengeSelection(None, True, "Two candidates remain.")
        elif self.result == "unresolved":
            selection = SemanticReferenceChallengeSelection(
                None, False, "No candidate is supported."
            )
        elif self.result == "unknown":
            selection = SemanticReferenceChallengeSelection(
                "a9", False, "An unknown candidate was returned."
            )
        else:
            ordinal = 1 if self.result == "second" else 0
            selection = SemanticReferenceChallengeSelection(
                bindings[ordinal].label,
                False,
                "The source context identifies this candidate.",
            )
        return SemanticReferenceChallengeExecution(
            selection=selection,
            candidate_label_bindings=bindings,
            extraction_task_id="ext_reference_challenge",
            model_run_id="mrn_reference_challenge",
            model_status=ModelRunStatus.SUCCEEDED,
            producer_id="qwen2.5-fixture",
            model_visible_task=b"exact bounded reference task",
            raw_output_sha256="a" * 64,
            mode=request.mode,
        )


def test_him_resolves_only_after_binary_validation_supports_the_specialist_candidate() -> None:
    text = "Amodei compared Trump to a feudal warlord and criticized him."
    target_start = text.index("him")
    trump_start = text.index("Trump")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target_start,
            target_start + 3,
            (CoreferenceAntecedentInput("candidate_trump", trump_start, trump_start + 5),),
        ),
        _Proposer((((trump_start, trump_start + 5), (target_start, target_start + 3)),)),
        _Tokenizer(),
        _Challenger(),
    )

    assert result.decision.status is SemanticReferenceStatus.RESOLVED
    assert len(result.decision.antecedent_span_ids) == 1
    assert result.trace.input["source_text"] == text
    candidate_id = result.observation.antecedent_candidates[0].id
    assert result.trace.input["model_attempts"] == [
        {
            "task": "specialist_validation",
            "model_visible_task": "exact bounded candidate validation task",
            "candidate_ids": [candidate_id],
            "candidate_label_bindings": [],
        }
    ]
    output_attempt = _model_attempts(result.trace.output)[0]
    assert output_attempt["model_result"] == {
        "verdict": "supported",
        "reason": "The source context supports this bounded verdict.",
    }
    assert output_attempt["mapped_candidate_id"] == candidate_id
    assert [item.task for item in result.decision.model_executions] == [
        SemanticReferenceModelTask.SPECIALIST_VALIDATION
    ]
    assert result.trace.output["decision"] == result.decision.model_dump(mode="json")


def test_multiple_preceding_antecedents_remain_ambiguous() -> None:
    text = "Trump met Amodei before officials criticized him."
    target = text.index("him")
    trump = text.index("Trump")
    amodei = text.index("Amodei")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + 3,
            (
                CoreferenceAntecedentInput("candidate_trump", trump, trump + 5),
                CoreferenceAntecedentInput("candidate_amodei", amodei, amodei + 6),
            ),
        ),
        _Proposer((((trump, trump + 5), (amodei, amodei + 6), (target, target + 3)),)),
        _Tokenizer(),
        _Challenger("ambiguous"),
    )

    assert result.decision.status is SemanticReferenceStatus.AMBIGUOUS
    assert len(result.decision.antecedent_span_ids) == 2


def test_repeated_cluster_mentions_of_one_candidate_identity_select_the_nearest() -> None:
    text = "Trump spoke before Trump criticized him."
    first = text.index("Trump")
    second = text.index("Trump", first + 1)
    target = text.index("him")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + 3,
            (
                CoreferenceAntecedentInput("candidate_trump_1", first, first + 5),
                CoreferenceAntecedentInput("candidate_trump_2", second, second + 5),
            ),
        ),
        _Proposer((((first, first + 5), (second, second + 5), (target, target + 3)),)),
        _Tokenizer(),
        _Challenger(),
    )

    assert result.decision.status is SemanticReferenceStatus.RESOLVED
    selected = result.observation.antecedent_candidates[1].span
    assert result.decision.antecedent_span_ids == (selected.id,)


def test_model_boundary_overreach_reconciles_to_the_best_source_candidate() -> None:
    text = "The NIST itself, which hosts the AISI, revised its policy."
    nist_start = text.index("The NIST itself")
    nist_end = nist_start + len("The NIST itself")
    aisi_start = text.index("the AISI")
    target = text.index("its", aisi_start + len("the AISI"))

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + 3,
            (
                CoreferenceAntecedentInput("candidate_nist", nist_start, nist_end),
                CoreferenceAntecedentInput(
                    "candidate_aisi", aisi_start, aisi_start + len("the AISI")
                ),
            ),
        ),
        _Proposer((((0, text.index(", revised")), (target, target + 3)),)),
        _Tokenizer(),
        _Challenger(),
    )

    assert result.decision.status is SemanticReferenceStatus.RESOLVED
    selected = result.observation.antecedent_candidates[0].span
    assert selected.text == "The NIST itself"
    assert result.decision.antecedent_span_ids == (selected.id,)


def test_altered_or_out_of_range_coreference_span_fails_validation() -> None:
    text = "Trump criticized him."
    target = text.index("him")

    with pytest.raises(ValueError, match="out-of-range"):
        resolve_semantic_reference(
            CoreferenceInput("seg_fixture", text, target, target + 3),
            _Proposer((((0, 5), (target, len(text) + 1)),)),
            _Tokenizer(),
            _Challenger(),
        )


def test_bounded_input_fails_before_calling_the_model() -> None:
    text = "Trump criticized him."
    target = text.index("him")

    with pytest.raises(ValueError, match="token limit"):
        resolve_semantic_reference(
            CoreferenceInput(
                "seg_fixture",
                text,
                target,
                target + 3,
                max_input_tokens=1,
            ),
            _Proposer(()),
            _Tokenizer(),
            _Challenger(),
        )


def test_specialist_candidates_do_not_override_a_different_semantic_choice() -> None:
    text = "Trump met Amodei before officials criticized him."
    target = text.index("him")
    trump = text.index("Trump")
    amodei = text.index("Amodei")
    challenger = _Challenger("first")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + 3,
            (
                CoreferenceAntecedentInput("candidate_trump", trump, trump + 5),
                CoreferenceAntecedentInput("candidate_amodei", amodei, amodei + 6),
            ),
        ),
        _Proposer((((trump, trump + 5), (amodei, amodei + 6), (target, target + 3)),)),
        _Tokenizer(),
        challenger,
    )

    expected = result.observation.antecedent_candidates[1].span.id
    assert result.decision.antecedent_span_ids == (expected,)
    assert _model_attempts(result.trace.input)[0]["model_visible_task"] == (
        "exact bounded reference task"
    )


def test_rejected_specialist_allows_one_different_contrastive_antecedent() -> None:
    text = "Anthropic met Amodei before the company changed course."
    anthropic = text.index("Anthropic")
    amodei = text.index("Amodei")
    target = text.index("the company")
    challenger = _Challenger("second", validation="unsupported")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("the company"),
            (
                CoreferenceAntecedentInput(
                    "candidate_anthropic", anthropic, anthropic + len("Anthropic")
                ),
                CoreferenceAntecedentInput("candidate_amodei", amodei, amodei + len("Amodei")),
            ),
        ),
        _Proposer((((amodei, amodei + len("Amodei")), (target, target + 11)),)),
        _Tokenizer(),
        challenger,
    )

    assert [item.antecedent_candidate.span.text for item in challenger.validation_requests] == [
        "Amodei"
    ]
    assert [item.span.text for item in challenger.requests[0].antecedent_candidates] == [
        "Amodei",
        "Anthropic",
    ]
    anthropic_candidate = next(
        item for item in result.observation.antecedent_candidates if item.span.text == "Anthropic"
    )
    assert result.decision.status.value == "resolved"
    assert result.decision.reason.value == "specialist_rejected_contrastive_selection"
    assert result.decision.antecedent_span_ids == (anthropic_candidate.span.id,)
    assert [item.task.value for item in result.decision.model_executions] == [
        "specialist_validation",
        "contrastive_selection",
    ]
    contrastive_input = _model_attempts(result.trace.input)[1]
    assert contrastive_input["candidate_label_bindings"] == [
        {
            "label": "a1",
            "candidate_id": result.observation.antecedent_candidates[1].id,
        },
        {"label": "a2", "candidate_id": anthropic_candidate.id},
    ]
    output_attempts = _model_attempts(result.trace.output)
    assert output_attempts[0]["model_result"] == {
        "verdict": "unsupported",
        "reason": "The source context supports this bounded verdict.",
    }
    assert output_attempts[0]["mapped_candidate_id"] is None
    assert output_attempts[1]["mapped_candidate_id"] == anthropic_candidate.id
    assert result.trace.output["decision"] == result.decision.model_dump(mode="json")
    assert [item["task"] for item in _model_attempts(result.trace.input)] == [
        "specialist_validation",
        "contrastive_selection",
    ]


def test_unclear_specialist_keeps_a_different_contrastive_choice_ambiguous() -> None:
    text = "Anthropic met Amodei before the company changed course."
    anthropic = text.index("Anthropic")
    amodei = text.index("Amodei")
    target = text.index("the company")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("the company"),
            (
                CoreferenceAntecedentInput(
                    "candidate_anthropic", anthropic, anthropic + len("Anthropic")
                ),
                CoreferenceAntecedentInput("candidate_amodei", amodei, amodei + len("Amodei")),
            ),
        ),
        _Proposer((((amodei, amodei + len("Amodei")), (target, target + 11)),)),
        _Tokenizer(),
        _Challenger("second", validation="unclear"),
    )

    spans = {item.span.text: item.span.id for item in result.observation.antecedent_candidates}
    assert result.decision.status.value == "ambiguous"
    assert result.decision.reason.value == "specialist_challenge_disagreement"
    assert result.decision.antecedent_span_ids == (spans["Anthropic"], spans["Amodei"])


@pytest.mark.parametrize("validation", ("unsupported", "unclear"))
def test_specialist_and_contrastive_agreement_resolves_after_binary_rejection(
    validation: str,
) -> None:
    text = "Defense conflicted with Anthropic over the use of its products."
    defense = text.index("Defense")
    anthropic = text.index("Anthropic")
    target = text.index("its")
    challenger = _Challenger("first", validation=validation)

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("its"),
            (
                CoreferenceAntecedentInput("candidate_defense", defense, defense + len("Defense")),
                CoreferenceAntecedentInput(
                    "candidate_anthropic", anthropic, anthropic + len("Anthropic")
                ),
            ),
        ),
        _Proposer((((anthropic, anthropic + len("Anthropic")), (target, target + 3)),)),
        _Tokenizer(),
        challenger,
    )

    assert [item.span.text for item in challenger.requests[0].antecedent_candidates] == [
        "Anthropic",
        "Defense",
    ]
    assert result.decision.status is SemanticReferenceStatus.RESOLVED
    assert result.decision.reason.value == "specialist_contrastive_confirmation"
    assert result.decision.antecedent_span_ids == (
        result.observation.antecedent_candidates[1].span.id,
    )
    assert [item.task.value for item in result.decision.model_executions] == [
        "specialist_validation",
        "contrastive_selection",
    ]


def test_sole_specialist_candidate_receives_binary_validation_not_catalog_selection() -> None:
    names = ("Bloomberg", "Claude", "Minab", "Anthropic", "Amodei", "United States")
    text = " ".join((*names, "reported that if it had, safeguards applied."))
    target = text.index("it", text.index("if it had"))
    candidates = tuple(
        CoreferenceAntecedentInput(
            f"candidate_{ordinal}",
            text.index(name),
            text.index(name) + len(name),
        )
        for ordinal, name in enumerate(names)
    )
    claude = candidates[1]
    challenger = _Challenger()

    result = resolve_semantic_reference(
        CoreferenceInput("seg_fixture", text, target, target + 2, candidates),
        _Proposer((((claude.start, claude.end), (target, target + 2)),)),
        _Tokenizer(),
        challenger,
    )

    assert [item.antecedent_candidate.span.text for item in challenger.validation_requests] == [
        "Claude"
    ]
    assert challenger.requests == []
    assert result.decision.status is SemanticReferenceStatus.RESOLVED
    assert _model_attempts(result.trace.input)[0]["candidate_ids"] == [
        result.observation.specialist_proposed_antecedent_candidate_ids[0]
    ]


def test_one_candidate_cannot_be_recorded_as_ambiguous() -> None:
    text = "Anthropic changed its policy."
    anthropic = text.index("Anthropic")
    target = text.index("its")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("its"),
            (
                CoreferenceAntecedentInput(
                    "candidate_anthropic", anthropic, anthropic + len("Anthropic")
                ),
            ),
        ),
        _Proposer(()),
        _Tokenizer(),
        _Challenger("ambiguous"),
    )

    assert result.decision.status is SemanticReferenceStatus.UNRESOLVED
    assert result.decision.reason.value == "challenge_invalid"
    assert result.decision.antecedent_span_ids == ()


def test_specialist_abstention_still_challenges_nearest_source_valid_candidates() -> None:
    text = "Anthropic met Dario Amodei before the company changed course."
    anthropic = text.index("Anthropic")
    amodei = text.index("Dario Amodei")
    target = text.index("the company")
    challenger = _Challenger("second")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("the company"),
            (
                CoreferenceAntecedentInput(
                    "candidate_anthropic",
                    anthropic,
                    anthropic + len("Anthropic"),
                ),
                CoreferenceAntecedentInput(
                    "candidate_amodei",
                    amodei,
                    amodei + len("Dario Amodei"),
                ),
            ),
        ),
        _Proposer(()),
        _Tokenizer(),
        challenger,
    )

    assert len(challenger.requests) == 1
    assert [item.span.text for item in challenger.requests[0].antecedent_candidates] == [
        "Dario Amodei",
        "Anthropic",
    ]
    assert result.observation.specialist_proposed_antecedent_candidate_ids == ()
    assert result.decision.status is SemanticReferenceStatus.RESOLVED
    selected = next(
        item.span.id
        for item in result.observation.antecedent_candidates
        if item.span.text == "Anthropic"
    )
    assert result.decision.antecedent_span_ids == (selected,)
    assert (
        result.trace.input["challenge_candidate_source"]
        == "monotonic_specialist_deterministic_union"
    )


def test_specialist_candidate_set_is_bounded_to_eight_nearest_source_mentions() -> None:
    names = tuple(f"Entity{ordinal}" for ordinal in range(10))
    text = " ".join((*names, "changed its policy"))
    target = text.index("its")
    candidates = tuple(
        CoreferenceAntecedentInput(
            f"candidate_{ordinal}",
            text.index(name),
            text.index(name) + len(name),
        )
        for ordinal, name in enumerate(names)
    )
    cluster = tuple((item.start, item.end) for item in candidates) + ((target, target + 3),)
    challenger = _Challenger()

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + 3,
            candidates,
        ),
        _Proposer((cluster,)),
        _Tokenizer(),
        challenger,
    )

    assert len(result.observation.specialist_proposed_antecedent_candidate_ids) == 10
    assert [item.span.text for item in challenger.requests[0].antecedent_candidates] == [
        "Entity9",
        "Entity8",
        "Entity7",
        "Entity6",
        "Entity5",
        "Entity4",
        "Entity3",
        "Entity2",
    ]


def test_out_of_catalog_challenge_result_cannot_resolve_reference() -> None:
    text = "Trump criticized him."
    target = text.index("him")
    trump = text.index("Trump")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + 3,
            (CoreferenceAntecedentInput("candidate_trump", trump, trump + 5),),
        ),
        _Proposer(()),
        _Tokenizer(),
        _Challenger("unknown"),
    )

    assert result.decision.status is SemanticReferenceStatus.UNRESOLVED
    assert result.decision.reason.value == "challenge_invalid"
    assert result.decision.antecedent_span_ids == ()
    output_attempt = _model_attempts(result.trace.output)[0]
    assert output_attempt["model_result"] == {
        "antecedent_candidate_label": "a9",
        "ambiguous": False,
        "reason": "An unknown candidate was returned.",
    }
    assert output_attempt["mapped_candidate_id"] is None
    assert result.trace.status.value == "rejected"
    assert result.trace.diagnostics == ("semantic_reference_challenge_invalid",)


@pytest.mark.parametrize("validation", ("failed", "invalid"))
def test_failed_or_malformed_specialist_validation_cannot_invoke_fallback(
    validation: str,
) -> None:
    text = "Anthropic met Amodei before the company changed course."
    anthropic = text.index("Anthropic")
    amodei = text.index("Amodei")
    target = text.index("the company")
    challenger = _Challenger(validation=validation)

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("the company"),
            (
                CoreferenceAntecedentInput(
                    "candidate_anthropic", anthropic, anthropic + len("Anthropic")
                ),
                CoreferenceAntecedentInput("candidate_amodei", amodei, amodei + len("Amodei")),
            ),
        ),
        _Proposer((((amodei, amodei + len("Amodei")), (target, target + 11)),)),
        _Tokenizer(),
        challenger,
    )

    assert len(challenger.validation_requests) == 1
    assert challenger.requests == []
    assert result.decision.status is SemanticReferenceStatus.UNRESOLVED
    assert result.decision.reason.value == f"specialist_validation_{validation}"
    assert len(result.decision.model_executions) == 1


def test_candidate_validation_rejects_source_text_that_does_not_match_the_target() -> None:
    text = "Claude was used, but if it had, safeguards applied."
    claude = text.index("Claude")
    target = text.index("it had")
    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + 2,
            (CoreferenceAntecedentInput("candidate_claude", claude, claude + 6),),
        ),
        _Proposer((((claude, claude + 6), (target, target + 2)),)),
        _Tokenizer(),
        _Challenger(),
    )

    with pytest.raises(ValueError, match="exact target source text"):
        SemanticReferenceCandidateValidationInput(
            source_segment_id="seg_fixture",
            source_text=text[:target] + "xx" + text[target + 2 :],
            target_span=result.observation.target_span,
            antecedent_candidate=result.observation.antecedent_candidates[0],
        )


def test_challenge_rejects_candidates_from_another_source_segment() -> None:
    text = "Anthropic met Amodei before the company changed course."
    anthropic = text.index("Anthropic")
    target = text.index("the company")
    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("the company"),
            (
                CoreferenceAntecedentInput(
                    "candidate_anthropic", anthropic, anthropic + len("Anthropic")
                ),
            ),
        ),
        _Proposer(()),
        _Tokenizer(),
        _Challenger(),
    )

    with pytest.raises(ValueError, match="exact target source text"):
        SemanticReferenceChallengeInput(
            source_segment_id="seg_other",
            source_text=text,
            target_span=result.observation.target_span,
            antecedent_candidates=result.observation.antecedent_candidates,
        )


def test_reordered_candidate_label_binding_cannot_resolve_reference() -> None:
    text = "Trump met Amodei before officials criticized him."
    target = text.index("him")
    trump = text.index("Trump")
    amodei = text.index("Amodei")

    result = resolve_semantic_reference(
        CoreferenceInput(
            "seg_fixture",
            text,
            target,
            target + len("him"),
            (
                CoreferenceAntecedentInput("candidate_trump", trump, trump + len("Trump")),
                CoreferenceAntecedentInput("candidate_amodei", amodei, amodei + len("Amodei")),
            ),
        ),
        _Proposer(()),
        _Tokenizer(),
        _Challenger("reversed_bindings"),
    )

    assert result.decision.status is SemanticReferenceStatus.UNRESOLVED
    assert result.decision.reason.value == "challenge_invalid"
    assert result.decision.antecedent_span_ids == ()
    assert result.trace.status.value == "rejected"
    assert result.trace.diagnostics == ("semantic_reference_challenge_invalid",)


def _model_attempts(payload: object) -> list[dict[str, Any]]:
    return cast(dict[str, list[dict[str, Any]]], payload)["model_attempts"]
