from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    EventEntityConnectionCandidate,
    EventEntityKind,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventEntityMentionInput,
    EventEntitySourceSpan,
    EventTriggerDraft,
    PredicateArgumentGapCode,
    PredicateArgumentHypothesis,
    PredicateArgumentPathDirection,
    SourceGroundedEventDraft,
    build_event_entity_connection_candidates,
    build_predicate_argument_observation,
    build_source_grounded_event_draft,
    predicate_argument_is_structurally_supported,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id


def test_direct_argument_preserves_exact_dependency_path() -> None:
    source = "Anthropic criticized Stargate."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="criticized",
        head="criticized",
        entity_text="Anthropic",
        tokens=(
            ("Anthropic", "anthropic", "PROPN", "nsubj", "t2", "s1"),
            ("criticized", "criticize", "VERB", "root", None, "s1"),
            ("Stargate", "stargate", "PROPN", "obj", "t2", "s1"),
            (".", ".", "PUNCT", "punct", "t2", "s1"),
        ),
    )

    observation = build_predicate_argument_observation(
        source_text=source,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.DIRECT_ARGUMENT
    assert observation.gap_code is None
    assert observation.predicate_anchor is not None
    assert observation.predicate_anchor.text == "criticized"
    assert observation.entity_anchor is not None
    assert observation.entity_anchor.text == "Anthropic"
    assert tuple(item.text for item in observation.path_tokens) == (
        "criticized",
        "Anthropic",
    )
    assert observation.path_steps[0].direction is PredicateArgumentPathDirection.TOWARD_DEPENDENT
    assert observation.path_steps[0].dependency_relation == "nsubj"
    assert predicate_argument_is_structurally_supported(observation.hypothesis) is True


def test_coordination_extends_one_core_argument_without_losing_occurrence() -> None:
    source = "Palantir and AWS offered services."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="offered",
        head="offered",
        entity_text="AWS",
        tokens=(
            ("Palantir", "palantir", "PROPN", "nsubj", "t4", "s1"),
            ("and", "and", "CCONJ", "cc", "t3", "s1"),
            ("AWS", "aws", "PROPN", "conj", "t1", "s1"),
            ("offered", "offer", "VERB", "root", None, "s1"),
            ("services", "service", "NOUN", "obj", "t4", "s1"),
            (".", ".", "PUNCT", "punct", "t4", "s1"),
        ),
    )

    observation = build_predicate_argument_observation(
        source_text=source,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.COORDINATED_ARGUMENT
    assert tuple(item.dependency_relation for item in observation.path_steps) == (
        "nsubj",
        "conj",
    )


def test_relative_clause_uses_the_exact_antecedent_path() -> None:
    source = "firms which reached agreements."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="reached",
        head="reached",
        entity_text="firms",
        tokens=(
            ("firms", "firm", "NOUN", "root", None, "s1"),
            ("which", "which", "PRON", "nsubj", "t3", "s1"),
            ("reached", "reach", "VERB", "acl:relcl", "t1", "s1"),
            ("agreements", "agreement", "NOUN", "obj", "t3", "s1"),
            (".", ".", "PUNCT", "punct", "t1", "s1"),
        ),
    )

    observation = build_predicate_argument_observation(
        source_text=source,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.RELATIVE_CLAUSE_ARGUMENT
    assert tuple(item.dependency_relation for item in observation.path_steps) == ("acl:relcl",)


def test_controlled_predicate_inherits_the_governing_subject() -> None:
    source = "Anthropic planned to acquire Beta."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="acquire",
        head="acquire",
        entity_text="Anthropic",
        tokens=(
            ("Anthropic", "anthropic", "PROPN", "nsubj", "t2", "s1"),
            ("planned", "plan", "VERB", "root", None, "s1"),
            ("to", "to", "PART", "mark", "t4", "s1"),
            ("acquire", "acquire", "VERB", "xcomp", "t2", "s1"),
            ("Beta", "beta", "PROPN", "obj", "t4", "s1"),
            (".", ".", "PUNCT", "punct", "t2", "s1"),
        ),
    )

    observation = build_predicate_argument_observation(
        source_text=source,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.INHERITED_ARGUMENT
    assert tuple(item.dependency_relation for item in observation.path_steps) == (
        "xcomp",
        "nsubj",
    )


def test_nominal_qualification_preserves_the_named_program() -> None:
    source = "Companies offered services with FedRAMP authorization."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="offered",
        head="offered",
        entity_text="FedRAMP",
        tokens=(
            ("Companies", "company", "NOUN", "nsubj", "t2", "s1"),
            ("offered", "offer", "VERB", "root", None, "s1"),
            ("services", "service", "NOUN", "obj", "t2", "s1"),
            ("with", "with", "ADP", "case", "t6", "s1"),
            ("FedRAMP", "fedramp", "PROPN", "compound", "t6", "s1"),
            ("authorization", "authorization", "NOUN", "obl", "t2", "s1"),
            (".", ".", "PUNCT", "punct", "t2", "s1"),
        ),
    )

    observation = build_predicate_argument_observation(
        source_text=source,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.QUALIFIED_ARGUMENT
    assert tuple(item.text for item in observation.path_tokens) == (
        "offered",
        "authorization",
        "FedRAMP",
    )


def test_different_sentence_is_structural_evidence_without_a_path() -> None:
    source = "Anthropic criticized Stargate. Google responded."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="criticized",
        head="criticized",
        entity_text="Google",
        tokens=(
            ("Anthropic", "anthropic", "PROPN", "nsubj", "t2", "s1"),
            ("criticized", "criticize", "VERB", "root", None, "s1"),
            ("Stargate", "stargate", "PROPN", "obj", "t2", "s1"),
            (".", ".", "PUNCT", "punct", "t2", "s1"),
            ("Google", "google", "PROPN", "nsubj", "t6", "s2"),
            ("responded", "respond", "VERB", "root", None, "s2"),
            (".", ".", "PUNCT", "punct", "t6", "s2"),
        ),
    )

    observation = build_predicate_argument_observation(
        source_text=source,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.DIFFERENT_SENTENCE
    assert observation.path_tokens == ()
    assert observation.path_steps == ()
    assert predicate_argument_is_structurally_supported(observation.hypothesis) is False


def test_multiple_entity_heads_produce_an_explicit_diagnostic_gap() -> None:
    source = "Alpha Beta criticized Stargate."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="criticized",
        head="criticized",
        entity_text="Alpha Beta",
        tokens=(
            ("Alpha", "alpha", "PROPN", "nsubj", "t3", "s1"),
            ("Beta", "beta", "PROPN", "nsubj", "t3", "s1"),
            ("criticized", "criticize", "VERB", "root", None, "s1"),
            ("Stargate", "stargate", "PROPN", "obj", "t3", "s1"),
            (".", ".", "PUNCT", "punct", "t3", "s1"),
        ),
    )

    observation = build_predicate_argument_observation(
        source_text=source,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.DIAGNOSTIC_GAP
    assert observation.gap_code is PredicateArgumentGapCode.ENTITY_ANCHOR_AMBIGUOUS
    assert observation.entity_anchor is None


def test_changed_authoritative_characters_fail_before_analysis() -> None:
    source = "Anthropic criticized Stargate."
    trigger, event, candidate, evidence = _case(
        source=source,
        expression="criticized",
        head="criticized",
        entity_text="Anthropic",
        tokens=(
            ("Anthropic", "anthropic", "PROPN", "nsubj", "t2", "s1"),
            ("criticized", "criticize", "VERB", "root", None, "s1"),
            ("Stargate", "stargate", "PROPN", "obj", "t2", "s1"),
            (".", ".", "PUNCT", "punct", "t2", "s1"),
        ),
    )

    with pytest.raises(ValueError, match="source digest"):
        build_predicate_argument_observation(
            source_text=source + " changed",
            trigger=trigger,
            event=event,
            candidate=candidate,
            linguistic_evidence=evidence,
        )


def _case(
    *,
    source: str,
    expression: str,
    head: str,
    entity_text: str,
    tokens: tuple[tuple[str, str, str, str, str | None, str], ...],
) -> tuple[
    EventTriggerDraft,
    SourceGroundedEventDraft,
    EventEntityConnectionCandidate,
    EventEntityLinguisticEvidence,
]:
    source_segment_id = "seg_predicate_fixture"
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    trigger_start = source.index(expression)
    head_start = trigger_start + expression.index(head)
    trigger_end = trigger_start + len(expression)
    head_end = head_start + len(head)
    trace_id = "xst_" + "1" * 24
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id=source_segment_id,
            source_text_sha256=source_digest,
            start=trigger_start,
            end=trigger_end,
            text=expression,
            head_start=head_start,
            head_end=head_end,
            head_text=head,
            event_type_label="source_grounded",
            extraction_task_id="ext_predicate_fixture",
            model_run_id="mrn_predicate_fixture",
            trace_id=trace_id,
        ),
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=trigger_start,
        end=trigger_end,
        text=expression,
        head_start=head_start,
        head_end=head_end,
        head_text=head,
        event_type_label="source_grounded",
        extraction_task_id="ext_predicate_fixture",
        model_run_id="mrn_predicate_fixture",
        trace_id=trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "2" * 24,
        trigger_id=trigger.id,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        expression_text=expression,
        head_text=head,
        head_evidence_target_id="etg_" + "3" * 24,
        expression_evidence_target_id="etg_" + "4" * 24,
        support_evidence_target_id="etg_" + "5" * 24,
    )
    entity_start = source.index(entity_text)
    mention_id = "mnc_" + "6" * 24
    span_values = (
        source_segment_id,
        source_digest,
        str(entity_start),
        str(entity_start + len(entity_text)),
        entity_text,
        mention_id,
        "",
    )
    source_span = EventEntitySourceSpan(
        id="ees_" + hashlib.sha256(chr(31).join(span_values).encode()).hexdigest()[:24],
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=entity_start,
        end=entity_start + len(entity_text),
        text=entity_text,
        mention_candidate_id=mention_id,
    )
    candidate = build_event_entity_connection_candidates(
        event,
        (
            EventEntityMentionInput(
                entity_identity="organization:" + entity_text.casefold().replace(" ", "-"),
                entity_kind=EventEntityKind.ORGANIZATION,
                entity_name=entity_text,
                denotation_decision_id="edd_" + "7" * 24,
                source_span=source_span,
            ),
        ),
        source_text=source,
    )[0]
    evidence = EventEntityLinguisticEvidence(
        trace_id="xst_" + "8" * 24,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        producer_id="stanza:fixture",
        model_id="stanza-en",
        model_version="fixture",
        resource_identity="9" * 64,
        tokens=_tokens(source, tokens),
    )
    return trigger, event, candidate, evidence


def _tokens(
    source: str,
    values: tuple[tuple[str, str, str, str, str | None, str], ...],
) -> tuple[EventEntityLinguisticToken, ...]:
    cursor = 0
    result: list[EventEntityLinguisticToken] = []
    for ordinal, (text, lemma, pos, relation, head_id, sentence_id) in enumerate(values, start=1):
        start = source.index(text, cursor)
        end = start + len(text)
        cursor = end
        result.append(
            EventEntityLinguisticToken(
                token_id=f"t{ordinal}",
                sentence_id=sentence_id,
                text=text,
                start=start,
                end=end,
                lemma=lemma,
                part_of_speech=pos,
                dependency_relation=relation,
                head_token_id=head_id,
            )
        )
    return tuple(result)
