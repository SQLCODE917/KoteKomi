from __future__ import annotations

import hashlib
import re

import pytest
from kotekomi_application import (
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventTriggerDraft,
    PropositionFragmentDisposition,
    PropositionFragmentReason,
    PropositionFragmentRoute,
    PropositionScopeStatus,
    SourceGroundedEventDraft,
    build_proposition_fragment_candidates,
    build_proposition_fragment_decision,
    build_source_grounded_event_draft,
    build_source_grounded_proposition_scope,
    proposition_fragment_model_task_input,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id


def test_proposition_candidates_preserve_attribution_and_event_content() -> None:
    source, trigger, event, linguistic = _attributed_fixture()

    candidates = build_proposition_fragment_candidates(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )

    by_text = {item.text: item for item in candidates}
    assert PropositionFragmentReason.EVENT_EXPRESSION in by_text["running"].reasons
    assert PropositionFragmentReason.GOVERNING_CONTEXT in by_text["Sacks"].reasons
    assert PropositionFragmentReason.GOVERNING_CONTEXT in by_text["stated"].reasons
    assert PropositionFragmentReason.PREDICATE_DEPENDENT in by_text["Anthropic"].reasons
    assert PropositionFragmentReason.PREDICATE_DEPENDENT in by_text["a strategy"].reasons


def test_scope_builder_keeps_exact_fragments_and_no_normalized_claim() -> None:
    source, trigger, event, linguistic = _attributed_fixture()
    candidates = build_proposition_fragment_candidates(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )
    decisions = tuple(
        build_proposition_fragment_decision(
            candidate=candidate,
            route=(
                PropositionFragmentRoute.DETERMINISTIC_REQUIRED
                if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
                else PropositionFragmentRoute.MODEL_JUDGMENT
            ),
            disposition=PropositionFragmentDisposition.INCLUDED,
            reason_code=(
                "event_expression_required"
                if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
                else "model_included"
            ),
            extraction_task_id=None
            if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
            else "ext_scope_fixture",
            model_run_id=None
            if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
            else "mrn_scope_fixture",
            trace_id=None
            if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
            else "xst_" + "9" * 24,
        )
        for candidate in candidates
    )

    scope = build_source_grounded_proposition_scope(
        source_text=source,
        event=event,
        trigger=trigger,
        candidates=candidates,
        decisions=decisions,
    )

    assert scope.status is PropositionScopeStatus.COMPLETE
    assert all(source[item.start : item.end] == item.text for item in scope.fragments)
    assert "Sacks" in {item.text for item in scope.fragments}
    assert "stated" in {item.text for item in scope.fragments}
    assert "running" in {item.text for item in scope.fragments}
    assert not hasattr(scope, "normalized_text")


def test_scope_builder_preserves_an_unresolved_candidate() -> None:
    source, trigger, event, linguistic = _attributed_fixture()
    candidates = build_proposition_fragment_candidates(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )
    uncertain = next(item for item in candidates if item.text == "Sacks")
    decisions = tuple(
        build_proposition_fragment_decision(
            candidate=candidate,
            route=(
                PropositionFragmentRoute.DETERMINISTIC_REQUIRED
                if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
                else PropositionFragmentRoute.MODEL_JUDGMENT
            ),
            disposition=(
                PropositionFragmentDisposition.UNRESOLVED
                if candidate.id == uncertain.id
                else (
                    PropositionFragmentDisposition.INCLUDED
                    if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
                    else PropositionFragmentDisposition.EXCLUDED
                )
            ),
            reason_code=(
                "event_expression_required"
                if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
                else ("model_uncertain" if candidate.id == uncertain.id else "model_excluded")
            ),
            extraction_task_id=None
            if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
            else "ext_scope_fixture",
            model_run_id=None
            if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
            else "mrn_scope_fixture",
            trace_id=None
            if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons
            else "xst_" + "9" * 24,
        )
        for candidate in candidates
    )

    scope = build_source_grounded_proposition_scope(
        source_text=source,
        event=event,
        trigger=trigger,
        candidates=candidates,
        decisions=decisions,
    )

    assert scope.status is PropositionScopeStatus.PARTIAL
    assert scope.unresolved_candidate_ids == (uncertain.id,)


def test_proposition_candidate_builder_rejects_changed_linguistic_text() -> None:
    source, trigger, event, linguistic = _attributed_fixture()
    changed = linguistic.model_copy(
        update={
            "tokens": (
                linguistic.tokens[0].model_copy(update={"text": "Stack"}),
                *linguistic.tokens[1:],
            )
        }
    )

    with pytest.raises(ValueError, match="does not replay"):
        build_proposition_fragment_candidates(
            source_text=source,
            trigger=trigger,
            event=event,
            linguistic_evidence=changed,
            entity_candidates=(),
        )


def test_model_task_marks_exact_occurrences_without_ids_or_offsets() -> None:
    source, trigger, event, linguistic = _attributed_fixture()
    candidates = build_proposition_fragment_candidates(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )
    candidate = next(item for item in candidates if item.text == "Sacks")

    rendered = proposition_fragment_model_task_input(
        source_text=source,
        trigger=trigger,
        candidate=candidate,
    ).decode()

    assert (
        "<source><candidate>Sacks</candidate> stated that Anthropic was "
        "<event>running</event> a strategy.</source>"
    ) in rendered
    assert candidate.id not in rendered
    assert trigger.id not in rendered
    assert str(candidate.start) not in rendered


def _attributed_fixture() -> tuple[
    str,
    EventTriggerDraft,
    SourceGroundedEventDraft,
    EventEntityLinguisticEvidence,
]:
    source = "Sacks stated that Anthropic was running a strategy."
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    expression_start = source.index("running")
    expression_end = expression_start + len("running")
    trace_id = "xst_" + "1" * 24
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id="seg_scope_fixture",
            source_text_sha256=source_digest,
            start=expression_start,
            end=expression_end,
            text="running",
            head_start=expression_start,
            head_end=expression_end,
            head_text="running",
            event_type_label="unmapped",
            extraction_task_id="ext_trigger_fixture",
            model_run_id="mrn_trigger_fixture",
            trace_id=trace_id,
        ),
        source_segment_id="seg_scope_fixture",
        source_text_sha256=source_digest,
        start=expression_start,
        end=expression_end,
        text="running",
        head_start=expression_start,
        head_end=expression_end,
        head_text="running",
        event_type_label="unmapped",
        extraction_task_id="ext_trigger_fixture",
        model_run_id="mrn_trigger_fixture",
        trace_id=trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "1" * 24,
        trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        expression_text=trigger.text,
        head_text=trigger.head_text,
        head_evidence_target_id="etg_" + "1" * 24,
        expression_evidence_target_id="etg_" + "2" * 24,
        support_evidence_target_id="etg_" + "3" * 24,
    )
    raw = tuple(
        (match.start(), match.end(), match.group()) for match in re.finditer(r"\w+|[^\w\s]", source)
    )
    heads = {
        "Sacks": ("t2", "nsubj"),
        "stated": (None, "root"),
        "that": ("t6", "mark"),
        "Anthropic": ("t6", "nsubj"),
        "was": ("t6", "aux"),
        "running": ("t2", "ccomp"),
        "a": ("t8", "det"),
        "strategy": ("t6", "obj"),
        ".": ("t2", "punct"),
    }
    tokens = tuple(
        EventEntityLinguisticToken(
            token_id=f"t{ordinal}",
            sentence_id="s1",
            text=text,
            start=start,
            end=end,
            lemma=text.casefold(),
            part_of_speech="PUNCT" if text == "." else "X",
            dependency_relation=heads[text][1],
            head_token_id=heads[text][0],
        )
        for ordinal, (start, end, text) in enumerate(raw, start=1)
    )
    linguistic = EventEntityLinguisticEvidence(
        trace_id="xst_" + "2" * 24,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        producer_id="stanza_pipeline_v1",
        model_id="stanza_english_ewt",
        model_version="fixture",
        resource_identity="4" * 64,
        tokens=tokens,
    )
    return source, trigger, event, linguistic
