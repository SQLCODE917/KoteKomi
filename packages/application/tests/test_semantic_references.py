from __future__ import annotations

import json

import pytest
from kotekomi_application import (
    CoreferenceAntecedentInput,
    CoreferenceExecution,
    CoreferenceInput,
    CoreferenceSpanProposal,
    SemanticReferenceChallengeExecution,
    SemanticReferenceChallengeInput,
    SemanticReferenceStatus,
    resolve_semantic_reference,
)
from kotekomi_application.semantic_reference_challenge_model_output import (
    SemanticReferenceChallengeSelection,
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
    def __init__(self, result: str = "first") -> None:
        self.result = result
        self.requests: list[SemanticReferenceChallengeInput] = []

    def challenge(
        self, request: SemanticReferenceChallengeInput
    ) -> SemanticReferenceChallengeExecution:
        self.requests.append(request)
        if self.result == "ambiguous":
            selection = SemanticReferenceChallengeSelection(None, True, "Two candidates remain.")
        elif self.result == "unresolved":
            selection = SemanticReferenceChallengeSelection(
                None, False, "No candidate is supported."
            )
        elif self.result == "unknown":
            selection = SemanticReferenceChallengeSelection(
                "cfa_000000000000000000000000", False, "An unknown candidate was returned."
            )
        else:
            ordinal = 1 if self.result == "second" else 0
            selection = SemanticReferenceChallengeSelection(
                request.antecedent_candidates[ordinal].id,
                False,
                "The source context identifies this candidate.",
            )
        return SemanticReferenceChallengeExecution(
            selection=selection,
            extraction_task_id="ext_reference_challenge",
            model_run_id="mrn_reference_challenge",
            model_status=ModelRunStatus.SUCCEEDED,
            producer_id="qwen2.5-fixture",
            model_visible_task=b"exact bounded reference task",
            raw_output_sha256="a" * 64,
        )


def test_him_resolves_only_after_the_challenger_selects_the_specialist_candidate() -> None:
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
    assert result.trace.input["model_visible_challenge_task"] == "exact bounded reference task"


def test_specialist_narrowing_cannot_remove_another_source_valid_candidate() -> None:
    text = "Anthropic met Amodei before the company changed course."
    anthropic = text.index("Anthropic")
    amodei = text.index("Amodei")
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
                    "candidate_anthropic", anthropic, anthropic + len("Anthropic")
                ),
                CoreferenceAntecedentInput("candidate_amodei", amodei, amodei + len("Amodei")),
            ),
        ),
        _Proposer((((amodei, amodei + len("Amodei")), (target, target + 11)),)),
        _Tokenizer(),
        challenger,
    )

    assert [item.span.text for item in challenger.requests[0].antecedent_candidates] == [
        "Amodei",
        "Anthropic",
    ]
    anthropic_span = next(
        item.span.id
        for item in result.observation.antecedent_candidates
        if item.span.text == "Anthropic"
    )
    amodei_span = next(
        item.span.id
        for item in result.observation.antecedent_candidates
        if item.span.text == "Amodei"
    )
    assert result.decision.status.value == "ambiguous"
    assert result.decision.reason.value == "specialist_challenge_disagreement"
    assert result.decision.antecedent_span_ids == (anthropic_span, amodei_span)


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
        _Proposer((((anthropic, anthropic + len("Anthropic")), (target, target + 3)),)),
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
        _Proposer((((trump, trump + 5), (target, target + 3)),)),
        _Tokenizer(),
        _Challenger("unknown"),
    )

    assert result.decision.status is SemanticReferenceStatus.UNRESOLVED
    assert result.decision.antecedent_span_ids == ()
