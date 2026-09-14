from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    BinarySemanticAnswerValue,
    EventHeadAnswerValue,
    EventHeadCandidate,
    EventHeadCandidateDispositionValue,
    EventRoutingAnswerValue,
    EventRoutingJudgment,
    EventSemanticRoute,
    EventTriggerDecision,
    EventVerbRoleAnswerValue,
    HybridEventTriggerPrompts,
    LinguisticAnalysis,
    LinguisticToken,
    NominalizationAnalysis,
    NominalizationCandidate,
    UniversalPartOfSpeech,
    parse_binary_semantic_answer,
    parse_event_head_answer,
    parse_event_verb_role_answer,
)
from kotekomi_application.hybrid_event_trigger_preview import (
    reconcile_event_trigger_decisions,
)
from kotekomi_application.hybrid_event_triggers import (
    event_trigger_expression_range,
    select_event_head_candidates,
)
from kotekomi_application.source_occurrences import source_occurrences
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("payload", "expected"),
    [(b"E", EventHeadAnswerValue.EVENT), (b"N", EventHeadAnswerValue.NOT_EVENT)],
)
def test_event_head_answer_accepts_only_one_literal(
    payload: bytes,
    expected: EventHeadAnswerValue,
) -> None:
    assert parse_event_head_answer(payload).value is expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"E", EventVerbRoleAnswerValue.EVENT),
        (b"S", EventVerbRoleAnswerValue.STANDING),
        (b"H", EventVerbRoleAnswerValue.HELPER),
    ],
)
def test_event_verb_role_accepts_only_one_literal(
    payload: bytes,
    expected: EventVerbRoleAnswerValue,
) -> None:
    assert parse_event_verb_role_answer(payload).value is expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [(b"Y", BinarySemanticAnswerValue.YES), (b"N", BinarySemanticAnswerValue.NO)],
)
def test_binary_semantic_answer_accepts_only_one_literal(
    payload: bytes,
    expected: BinarySemanticAnswerValue,
) -> None:
    assert parse_binary_semantic_answer(payload).value is expected


@pytest.mark.parametrize("payload", [b"", b"yes", b" E", b"N because"])
def test_bounded_event_answers_reject_non_literal_output(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_event_head_answer(payload)


def test_stanza_verbs_and_qanom_nouns_become_exact_candidates() -> None:
    source = "Anthropic rebuked the proposal."
    digest = hashlib.sha256(source.encode()).hexdigest()
    analysis = LinguisticAnalysis(
        source_text_sha256=digest,
        producer_id="stanza:fixture",
        model_id="en_ewt",
        model_version="1",
        resource_identity="a" * 64,
        tokens=(
            LinguisticToken(
                "t1",
                "s1",
                "Anthropic",
                0,
                9,
                "Anthropic",
                UniversalPartOfSpeech.PROPER_NOUN,
                "nsubj",
                "t2",
            ),
            LinguisticToken(
                "t2", "s1", "rebuked", 10, 17, "rebuke", UniversalPartOfSpeech.VERB, "root", None
            ),
            LinguisticToken(
                "t3", "s1", "the", 18, 21, "the", UniversalPartOfSpeech.DETERMINER, "det", "t4"
            ),
            LinguisticToken(
                "t4", "s1", "proposal", 22, 30, "proposal", UniversalPartOfSpeech.NOUN, "obj", "t2"
            ),
        ),
    )
    nominalization = NominalizationAnalysis(
        source_text_sha256=digest,
        producer_id="qanom:fixture",
        model_id="qanom",
        model_revision="1",
        resource_identity="b" * 64,
        threshold=0.45,
        candidates=(NominalizationCandidate("t4", "proposal", 22, 30, True, 2.0, -2.0, 0.88),),
    )

    selection = select_event_head_candidates(
        source,
        source_occurrences(source),
        analysis,
        nominalization,
    )

    assert [(item.occurrence_id, item.text) for item in selection.candidates] == [
        ("o2", "rebuked"),
        ("o4", "proposal"),
    ]
    assert [item.disposition for item in selection.dispositions] == [
        EventHeadCandidateDispositionValue.EXCLUDED,
        EventHeadCandidateDispositionValue.INCLUDED,
        EventHeadCandidateDispositionValue.EXCLUDED,
        EventHeadCandidateDispositionValue.INCLUDED,
    ]
    assert selection.candidates[1].nominalization_probability == 0.88


def test_nominal_event_expression_retains_one_marked_infinitival_clause() -> None:
    source = "decision to attend Forum over inauguration; hiring"
    tokens = (
        LinguisticToken(
            "t1", "s1", "decision", 0, 8, "decision", UniversalPartOfSpeech.NOUN, "root", None
        ),
        LinguisticToken(
            "t2", "s1", "to", 9, 11, "to", UniversalPartOfSpeech.PARTICLE, "mark", "t3"
        ),
        LinguisticToken(
            "t3", "s1", "attend", 12, 18, "attend", UniversalPartOfSpeech.VERB, "acl", "t1"
        ),
        LinguisticToken(
            "t4", "s1", "Forum", 19, 24, "Forum", UniversalPartOfSpeech.PROPER_NOUN, "obj", "t3"
        ),
        LinguisticToken(
            "t5", "s1", "over", 25, 29, "over", UniversalPartOfSpeech.ADPOSITION, "case", "t6"
        ),
        LinguisticToken(
            "t6",
            "s1",
            "inauguration",
            30,
            42,
            "inauguration",
            UniversalPartOfSpeech.NOUN,
            "obl",
            "t3",
        ),
        LinguisticToken(
            "t7", "s1", ";", 42, 43, ";", UniversalPartOfSpeech.PUNCTUATION, "punct", "t8"
        ),
        LinguisticToken(
            "t8", "s1", "hiring", 44, 50, "hire", UniversalPartOfSpeech.NOUN, "appos", "t6"
        ),
    )
    candidate = EventHeadCandidate(
        occurrence_id="o1",
        text="decision",
        start=0,
        end=8,
        linguistic_token_id="t1",
        sentence_id="s1",
        lemma="decision",
        part_of_speech=UniversalPartOfSpeech.NOUN,
        dependency_relation="root",
        dependency_head_token_id=None,
        lexical_nominalization_candidate=True,
        nominalization_probability=0.9,
    )

    start, end = event_trigger_expression_range(candidate, source, tokens)

    assert source[start:end] == "decision to attend Forum over inauguration"


def test_event_expression_does_not_expand_a_verb_head() -> None:
    source = "decided to attend"
    tokens = (
        LinguisticToken(
            "t1", "s1", "decided", 0, 7, "decide", UniversalPartOfSpeech.VERB, "root", None
        ),
        LinguisticToken(
            "t2", "s1", "to", 8, 10, "to", UniversalPartOfSpeech.PARTICLE, "mark", "t3"
        ),
        LinguisticToken(
            "t3", "s1", "attend", 11, 17, "attend", UniversalPartOfSpeech.VERB, "xcomp", "t1"
        ),
    )
    candidate = _candidate("o1", "decided", 0, UniversalPartOfSpeech.VERB)

    assert event_trigger_expression_range(candidate, source, tokens) == (0, 7)


def test_candidate_selection_rejects_specialist_source_drift() -> None:
    source = "A changed source"
    analysis = LinguisticAnalysis(
        source_text_sha256="a" * 64,
        producer_id="fixture",
        model_id="fixture",
        model_version="1",
        resource_identity="b" * 64,
        tokens=(
            LinguisticToken("t1", "s1", "A", 0, 1, "a", UniversalPartOfSpeech.NOUN, "root", None),
        ),
    )
    nominalization = NominalizationAnalysis(
        source_text_sha256="a" * 64,
        producer_id="fixture",
        model_id="fixture",
        model_revision="1",
        resource_identity="b" * 64,
        threshold=0.45,
        candidates=(),
    )

    with pytest.raises(ValueError, match="source digest"):
        select_event_head_candidates(
            source,
            source_occurrences(source),
            analysis,
            nominalization,
        )


def test_routing_judgment_rejects_an_answer_from_the_wrong_contract() -> None:
    with pytest.raises(ValidationError, match="invalid for its semantic route"):
        EventRoutingJudgment(
            occurrence_id="o1",
            route=EventSemanticRoute.VERB_ROLE,
            answer=EventRoutingAnswerValue.YES,
            extraction_task_id="ext_fixture",
            model_run_id="mrn_fixture",
        )


def test_reconciliation_retains_valid_siblings_and_marks_one_failed_candidate() -> None:
    candidates = {
        "o1": _candidate("o1", "rebuked", 0, UniversalPartOfSpeech.VERB),
        "o2": _candidate("o2", "proposal", 8, UniversalPartOfSpeech.NOUN),
    }
    decision = EventTriggerDecision(
        occurrence_id="o1",
        answer=EventHeadAnswerValue.EVENT,
        reason_code="model_event_role",
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
    )

    result = reconcile_event_trigger_decisions(
        (decision,),
        candidates=candidates,
        unclassified_occurrence_ids=("o2",),
    )

    assert result.event_decisions == (decision,)
    assert result.unclassified_occurrence_ids == ("o2",)
    assert result.dispositions[0].disposition.value == "accepted"


def test_prompt_bundle_maps_every_semantic_route_explicitly() -> None:
    prompts = HybridEventTriggerPrompts(
        verb_role=b"verb-role",
        verb_similarity=b"verb-similarity",
        noun_inventory=b"noun-inventory",
        noun_dependent_kind=b"noun-dependent-kind",
        noun_media_artifact=b"noun-media-artifact",
        noun_governor_distinct=b"noun-governor-distinct",
        noun_reaction=b"noun-reaction",
        noun_standing=b"noun-standing",
    )

    assert {prompts.for_route(route) for route in EventSemanticRoute} == {
        b"verb-role",
        b"verb-similarity",
        b"noun-inventory",
        b"noun-dependent-kind",
        b"noun-media-artifact",
        b"noun-governor-distinct",
        b"noun-reaction",
        b"noun-standing",
    }


def _candidate(
    occurrence_id: str,
    text: str,
    start: int,
    part_of_speech: UniversalPartOfSpeech,
) -> EventHeadCandidate:
    nominal = part_of_speech is UniversalPartOfSpeech.NOUN
    return EventHeadCandidate(
        occurrence_id=occurrence_id,
        text=text,
        start=start,
        end=start + len(text),
        linguistic_token_id=f"t{occurrence_id.removeprefix('o')}",
        sentence_id="s1",
        lemma=text,
        part_of_speech=part_of_speech,
        dependency_relation="root" if not nominal else "obj",
        dependency_head_token_id=None if not nominal else "t1",
        lexical_nominalization_candidate=True if nominal else None,
        nominalization_probability=0.9 if nominal else None,
    )
