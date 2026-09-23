"""Deterministic model-free event-attribution wiring composition contract tests.

Covers the D4 acceptance criteria AC-WIR-CMP-01..06.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    EventAttributionWiringInput,
    EventAttributionWiringResult,
    EventAttributionWiringStatus,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventTriggerDraft,
    SourceGroundedEventDraft,
    build_source_grounded_event_draft,
    wire_event_attribution,
)
from kotekomi_application.hybrid_event_semantics import (
    EventArgumentTargetDraft,
    EventAttributionKind,
    EventSemanticDraft,
    build_event_argument_target_draft,
    build_event_semantic_draft,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id
from kotekomi_domain import SemanticArgumentTargetKind

_Token = tuple[str, str, str, str, str | None, str]
_Tokens = tuple[_Token, ...]

_SUPPORT = "etg_" + "e" * 24
_EVIDENCE_ASSERTION = "ast_evidence_01"
_RATIONALE = "The source quotes Sacks verbatim."
_CONFIDENCE = 0.94
_SUPPORT_DECISION = "pdc_support_01"
_SUPPORT_JUDGMENT = "ssj_support_01"
_NLI_OBSERVATION = "nob_support_01"
_OCCURRED_AT = datetime(2026, 9, 22, 0, 0, tzinfo=UTC)

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


class _Resolver:
    def __init__(self, result: str | None) -> None:
        self.result = result
        self.calls = 0

    def resolve_attribution_target(self, target: EventArgumentTargetDraft) -> str | None:
        self.calls += 1
        return self.result


def test_targeted_event_composes_carrier_complement_statement_and_edge() -> None:
    result = _wire(_FRONTED_SOURCE, _FRONTED_TOKENS, "chastised", "chastised")

    assert result.status is EventAttributionWiringStatus.CONSTRUCTED
    split = result.trigger_scope_split
    assert split.reporting_carrier is not None
    assert split.reporting_carrier.text == "According to Semafor"
    assert split.governed_complement is not None
    assert split.governed_complement.text == "Trump officials chastised Anthropic's hiring"

    assert result.attributed_statement is not None
    statement = result.attributed_statement.proposed_assertion
    assert statement is not None
    assert statement.attributed_to_id == "act_sacks"

    assert result.support_edge_input is not None
    edge = result.support_edge_input
    assert edge.from_assertion_id == _EVIDENCE_ASSERTION
    assert edge.to_assertion_id == statement.id
    assert edge.rationale == _RATIONALE
    assert edge.confidence == _CONFIDENCE
    assert edge.evidence_target_ids == (_SUPPORT,)
    assert edge.support_decision_id == _SUPPORT_DECISION
    assert edge.support_judgment_id == _SUPPORT_JUDGMENT
    assert edge.nli_observation_id == _NLI_OBSERVATION


def test_governed_complement_without_reporting_clause_produces_held() -> None:
    result = _wire(_HELD_SOURCE, _HELD_TOKENS, "chastised", "chastised")

    assert result.status is EventAttributionWiringStatus.HELD
    assert result.attributed_statement is None
    assert result.support_edge_input is None


def test_source_narrator_produces_no_assertion() -> None:
    result = _wire(
        _FRONTED_SOURCE,
        _FRONTED_TOKENS,
        "chastised",
        "chastised",
        kind=EventAttributionKind.SOURCE_NARRATOR,
    )

    assert result.status is EventAttributionWiringStatus.NO_ASSERTION
    assert result.attributed_statement is not None
    assert result.support_edge_input is None


def test_unresolved_produces_failed() -> None:
    result = _wire(
        _FRONTED_SOURCE,
        _FRONTED_TOKENS,
        "chastised",
        "chastised",
        kind=EventAttributionKind.UNRESOLVED,
    )

    assert result.status is EventAttributionWiringStatus.FAILED
    assert result.attributed_statement is not None
    assert result.support_edge_input is None


def test_constructed_requires_pinned_edge_ingredients() -> None:
    trigger, event, evidence = _inputs(_FRONTED_SOURCE, _FRONTED_TOKENS, "chastised", "chastised")
    target = _target(kind=SemanticArgumentTargetKind.MENTION_CANDIDATE, reference_id="mnc_sacks")
    draft = _semantic_draft(trigger, event, EventAttributionKind.MENTION_CANDIDATE, target.id)

    with pytest.raises(ValueError, match="fully pinned"):
        wire_event_attribution(
            wiring_input=EventAttributionWiringInput(
                source_text=_FRONTED_SOURCE,
                event=event,
                trigger=trigger,
                linguistic_evidence=evidence,
                semantic_draft=draft,
                attribution_target=target,
                subject_entity_id="act_trump_officials",
                object_entity_id=None,
                object_value="Anthropic's hiring",
                source_id="src_article_a",
                support_evidence_target_id=_SUPPORT,
                assertion_id="ast_wiring_01",
            ),
            resolver=_Resolver("act_sacks"),
        )


def _wire(
    source: str,
    tokens: _Tokens,
    expression: str,
    head: str,
    *,
    kind: EventAttributionKind = EventAttributionKind.MENTION_CANDIDATE,
) -> EventAttributionWiringResult:
    trigger, event, evidence = _inputs(source, tokens, expression, head)
    target = (
        _target(kind=SemanticArgumentTargetKind.MENTION_CANDIDATE, reference_id="mnc_sacks")
        if kind is EventAttributionKind.MENTION_CANDIDATE
        else None
    )
    attribution_target_id = target.id if target is not None else None
    draft = _semantic_draft(trigger, event, kind, attribution_target_id)
    return wire_event_attribution(
        wiring_input=EventAttributionWiringInput(
            source_text=source,
            event=event,
            trigger=trigger,
            linguistic_evidence=evidence,
            semantic_draft=draft,
            attribution_target=target,
            subject_entity_id="act_trump_officials",
            object_entity_id=None,
            object_value="Anthropic's hiring",
            source_id="src_article_a",
            support_evidence_target_id=_SUPPORT,
            assertion_id="ast_wiring_01",
            evidence_assertion_id=_EVIDENCE_ASSERTION,
            rationale=_RATIONALE,
            confidence=_CONFIDENCE,
            support_decision_id=_SUPPORT_DECISION,
            support_judgment_id=_SUPPORT_JUDGMENT,
            nli_observation_id=_NLI_OBSERVATION,
            occurred_at=_OCCURRED_AT,
        ),
        resolver=_Resolver("act_sacks"),
    )


def _semantic_draft(
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    kind: EventAttributionKind,
    attribution_target_id: str | None,
) -> EventSemanticDraft:
    return build_event_semantic_draft(
        event_subject_id=event.event_subject_id,
        trigger_id=trigger.id,
        trigger_text="chastised",
        frame_id="statement",
        proposed_event_label="chastised",
        argument_assignment_ids=(),
        qualifier_ids=(),
        polarity="affirmed",
        modality="actual",
        attribution_kind=kind,
        attribution_target_id=attribution_target_id,
        support_evidence_target_id=_SUPPORT,
        frame_selection_task_id="ext_fixture",
        frame_selection_model_run_id="mrn_fixture",
        frame_selection_trace_id="xst_" + "d" * 24,
    )


def _target(
    *, kind: SemanticArgumentTargetKind, reference_id: str | None
) -> EventArgumentTargetDraft:
    return build_event_argument_target_draft(
        kind=kind,
        reference_id=reference_id,
        source_segment_id="seg_trigger_scope_fixture",
        text="Semafor",
        start=10,
        end=17,
        evidence_target_id="etg_" + "f" * 24,
        evidence_validation_attempt_id="eva_" + "f" * 24,
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
        support_evidence_target_id=_SUPPORT,
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


def _tokens(source: str, values: _Tokens) -> tuple[EventEntityLinguisticToken, ...]:
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