"""Deterministic model-free trigger-scope split contract tests."""

from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventTriggerDraft,
    SourceGroundedEventDraft,
    TriggerScopeHoldReason,
    TriggerScopeSplit,
    TriggerScopeStatus,
    build_source_grounded_event_draft,
    split_trigger_scope,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id

_Token = tuple[str, str, str, str, str | None, str]
_Tokens = tuple[_Token, ...]

_FRONTED_SOURCE = "According to Semafor, Trump officials chastised Anthropic's hiring."
_FRONTED_TOKENS: _Tokens = (
    ("According", "accord", "VERB", "advcl", "t7", "s1"),
    ("to", "to", "ADP", "case", "t1", "s1"),
    ("Semafor", "semafor", "PROPN", "obl", "t1", "s1"),
    (",", ",", "PUNCT", "punct", "t7", "s1"),
    ("Trump", "trump", "PROPN", "compound", "t6", "s1"),
    ("officials", "official", "NOUN", "nsubj", "t7", "s1"),
    ("chastised", "chastise", "VERB", "root", None, "s1"),
    ("Anthropic", "anthropic", "PROPN", "poss", "t10", "s1"),
    ("'s", "'s", "PART", "case", "t8", "s1"),
    ("hiring", "hire", "NOUN", "obj", "t7", "s1"),
    (".", ".", "PUNCT", "punct", "t7", "s1"),
)

_COMPLEMENT_SOURCE = "Sacks stated that Anthropic ran a sophisticated regulatory strategy."
_COMPLEMENT_TOKENS: _Tokens = (
    ("Sacks", "sacks", "PROPN", "nsubj", "t2", "s1"),
    ("stated", "state", "VERB", "root", None, "s1"),
    ("that", "that", "SCONJ", "mark", "t5", "s1"),
    ("Anthropic", "anthropic", "PROPN", "nsubj", "t5", "s1"),
    ("ran", "run", "VERB", "ccomp", "t2", "s1"),
    ("a", "a", "DET", "det", "t9", "s1"),
    ("sophisticated", "sophisticated", "ADJ", "amod", "t9", "s1"),
    ("regulatory", "regulatory", "ADJ", "amod", "t9", "s1"),
    ("strategy", "strategy", "NOUN", "obj", "t5", "s1"),
    (".", ".", "PUNCT", "punct", "t2", "s1"),
)

_HELD_SOURCE = "Trump officials chastised Anthropic's hiring."
_HELD_TOKENS: _Tokens = (
    ("Trump", "trump", "PROPN", "compound", "t2", "s1"),
    ("officials", "official", "NOUN", "nsubj", "t3", "s1"),
    ("chastised", "chastise", "VERB", "root", None, "s1"),
    ("Anthropic", "anthropic", "PROPN", "poss", "t6", "s1"),
    ("'s", "'s", "PART", "case", "t4", "s1"),
    ("hiring", "hire", "NOUN", "obj", "t3", "s1"),
    (".", ".", "PUNCT", "punct", "t3", "s1"),
)


def test_fronted_attribution_splits_carrier_and_complement() -> None:
    result = _split(_FRONTED_SOURCE, _FRONTED_TOKENS, "chastised", "chastised")
    assert result.status is TriggerScopeStatus.COMPLETE
    assert result.hold_reason is None
    assert result.reporting_carrier is not None
    assert result.reporting_carrier.text == "According to Semafor"
    assert result.governed_complement is not None
    assert result.governed_complement.text == "Trump officials chastised Anthropic's hiring"


def test_reporting_verb_complement_keeps_stated_content_in_complement() -> None:
    result = _split(_COMPLEMENT_SOURCE, _COMPLEMENT_TOKENS, "ran", "ran")
    assert result.status is TriggerScopeStatus.COMPLETE
    assert result.hold_reason is None
    assert result.reporting_carrier is not None
    assert result.reporting_carrier.text == "Sacks stated"
    assert result.governed_complement is not None
    assert result.governed_complement.text == "Anthropic ran a sophisticated regulatory strategy"


def test_governed_complement_without_reporting_clause_is_held() -> None:
    result = _split(_HELD_SOURCE, _HELD_TOKENS, "chastised", "chastised")
    assert result.status is TriggerScopeStatus.HELD
    assert result.hold_reason is TriggerScopeHoldReason.REPORTING_PREDICATE_MISSING
    assert result.reporting_carrier is None
    assert result.governed_complement is None


def test_held_result_never_merges_partial_parts() -> None:
    result = _split(_HELD_SOURCE, _HELD_TOKENS, "chastised", "chastised")
    assert result.status is TriggerScopeStatus.HELD
    assert result.reporting_carrier is None
    assert result.governed_complement is None


def test_complete_split_emits_both_parts_never_one() -> None:
    result = _split(_FRONTED_SOURCE, _FRONTED_TOKENS, "chastised", "chastised")
    assert result.status is TriggerScopeStatus.COMPLETE
    assert (result.reporting_carrier is None) == (result.governed_complement is None)


def test_split_result_rebuilds_from_same_inputs() -> None:
    first = _split(_FRONTED_SOURCE, _FRONTED_TOKENS, "chastised", "chastised")
    second = _split(_FRONTED_SOURCE, _FRONTED_TOKENS, "chastised", "chastised")
    assert first == second
    assert first.id == second.id


def test_source_digest_drift_fails_fast() -> None:
    trigger, event, evidence = _inputs(_FRONTED_SOURCE, _FRONTED_TOKENS, "chastised", "chastised")
    with pytest.raises(ValueError, match="source digest"):
        split_trigger_scope(
            source_text=_FRONTED_SOURCE + " changed",
            trigger=trigger,
            event=event,
            linguistic_evidence=evidence,
        )


def _split(
    source: str,
    tokens: _Tokens,
    expression: str,
    head: str,
) -> TriggerScopeSplit:
    trigger, event, evidence = _inputs(source, tokens, expression, head)
    return split_trigger_scope(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=evidence,
    )


def _inputs(
    source: str,
    tokens: _Tokens,
    expression: str,
    head: str,
) -> tuple[EventTriggerDraft, SourceGroundedEventDraft, EventEntityLinguisticEvidence]:
    source_segment_id = "seg_trigger_scope_fixture"
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    trigger_start = source.index(expression)
    head_start = trigger_start + expression.index(head)
    trigger_end = trigger_start + len(expression)
    head_end = head_start + len(head)
    trace_id = "xst_" + "a" * 24
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
            extraction_task_id="ext_trigger_scope_fixture",
            model_run_id="mrn_trigger_scope_fixture",
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
        extraction_task_id="ext_trigger_scope_fixture",
        model_run_id="mrn_trigger_scope_fixture",
        trace_id=trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "b" * 24,
        trigger_id=trigger.id,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        expression_text=expression,
        head_text=head,
        head_evidence_target_id="etg_" + "c" * 24,
        expression_evidence_target_id="etg_" + "d" * 24,
        support_evidence_target_id="etg_" + "e" * 24,
    )
    evidence = EventEntityLinguisticEvidence(
        trace_id=trace_id,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        producer_id="stanza:fixture",
        model_id="stanza-en",
        model_version="fixture",
        resource_identity="f" * 64,
        tokens=_tokens(source, tokens),
    )
    return trigger, event, evidence


def _tokens(
    source: str,
    values: _Tokens,
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