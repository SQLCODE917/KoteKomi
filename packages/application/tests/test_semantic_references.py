from __future__ import annotations

import json

import pytest
from kotekomi_application import (
    CoreferenceAntecedentInput,
    CoreferenceExecution,
    CoreferenceInput,
    CoreferenceSpanProposal,
    SemanticReferenceStatus,
    resolve_semantic_reference,
)


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


def test_him_resolves_to_the_one_visible_preceding_antecedent() -> None:
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
        )
