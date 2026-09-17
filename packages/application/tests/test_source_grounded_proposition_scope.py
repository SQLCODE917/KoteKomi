from __future__ import annotations

import hashlib
import re

import pytest
from kotekomi_application import (
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventTriggerDraft,
    PropositionFragmentCandidate,
    PropositionFragmentDisposition,
    PropositionFragmentReason,
    PropositionFragmentRoute,
    PropositionFragmentTaskInputStatus,
    PropositionScopeStatus,
    SourceGroundedEventDraft,
    build_proposition_fragment_candidates,
    build_proposition_fragment_decision,
    build_source_grounded_event_draft,
    build_source_grounded_proposition_scope,
    marker_free_proposition_fragment_model_task_input,
    proposition_fragment_candidate_id,
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


@pytest.mark.parametrize(
    ("source", "trigger_ordinal", "specs", "expected", "overbroad"),
    (
        (
            "Amodei published a blog post rebuffing claims.",
            2,
            (
                ("Amodei", 2, "nsubj", "PROPN"),
                ("published", None, "root", "VERB"),
                ("a", 5, "det", "DET"),
                ("blog", 5, "compound", "NOUN"),
                ("post", 2, "obj", "NOUN"),
                ("rebuffing", 5, "acl", "VERB"),
                ("claims", 6, "obj", "NOUN"),
                (".", 2, "punct", "PUNCT"),
            ),
            "a blog post",
            "a blog post rebuffing claims",
        ),
        (
            'Amodei described the bill, then tied to the Act, as "too blunt".',
            2,
            (
                ("Amodei", 2, "nsubj", "PROPN"),
                ("described", None, "root", "VERB"),
                ("the", 4, "det", "DET"),
                ("bill", 2, "obj", "NOUN"),
                (",", 7, "punct", "PUNCT"),
                ("then", 7, "advmod", "ADV"),
                ("tied", 4, "acl", "VERB"),
                ("to", 10, "case", "ADP"),
                ("the", 10, "det", "DET"),
                ("Act", 7, "obl", "PROPN"),
                (",", 15, "punct", "PUNCT"),
                ("as", 15, "case", "ADP"),
                ('"', 15, "punct", "PUNCT"),
                ("too", 15, "advmod", "ADV"),
                ("blunt", 7, "obl", "ADJ"),
                ('"', 15, "punct", "PUNCT"),
                (".", 2, "punct", "PUNCT"),
            ),
            'as "too blunt"',
            'the bill, then tied to the Act, as "too blunt"',
        ),
        (
            "Anthropic announced that it would allow customers to use Claude Gov. [11][12]",
            2,
            (
                ("Anthropic", 2, "nsubj", "PROPN"),
                ("announced", None, "root", "VERB"),
                ("that", 6, "mark", "SCONJ"),
                ("it", 6, "nsubj", "PRON"),
                ("would", 6, "aux", "AUX"),
                ("allow", 2, "ccomp", "VERB"),
                ("customers", 6, "iobj", "NOUN"),
                ("to", 9, "mark", "PART"),
                ("use", 6, "xcomp", "VERB"),
                ("Claude", 9, "obj", "PROPN"),
                ("Gov.", 10, "flat", "PROPN"),
                ("[", 13, "punct", "PUNCT"),
                ("11", 10, "appos", "NUM"),
                ("]", 13, "punct", "PUNCT"),
                ("[", 16, "punct", "PUNCT"),
                ("12", 13, "nmod", "NUM"),
                ("]", 16, "punct", "PUNCT"),
            ),
            "that it would allow customers to use Claude Gov.",
            "that it would allow customers to use Claude Gov. [11][12]",
        ),
    ),
)
def test_proposition_candidates_add_clause_local_constituents(
    source: str,
    trigger_ordinal: int,
    specs: tuple[tuple[str, int | None, str, str], ...],
    expected: str,
    overbroad: str,
) -> None:
    trigger, event, linguistic = _fixture_from_specs(source, trigger_ordinal, specs)

    candidates = build_proposition_fragment_candidates(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )

    by_text = {item.text: item for item in candidates}
    assert overbroad in by_text
    assert PropositionFragmentReason.CLAUSE_LOCAL_CONSTITUENT in by_text[expected].reasons


def test_proposition_candidates_do_not_partially_overlap_event_expression() -> None:
    source = "Actor made a decision to attend Forum and report."
    trigger, event, linguistic = _fixture_from_specs(
        source,
        4,
        (
            ("Actor", 2, "nsubj", "PROPN"),
            ("made", None, "root", "VERB"),
            ("a", 4, "det", "DET"),
            ("decision", 2, "obj", "NOUN"),
            ("to", 6, "mark", "PART"),
            ("attend", 4, "acl", "VERB"),
            ("Forum", 6, "obj", "PROPN"),
            ("and", 9, "cc", "CCONJ"),
            ("report", 6, "conj", "NOUN"),
            (".", 2, "punct", "PUNCT"),
        ),
        trigger_expression_ordinals=(4, 7),
    )

    candidates = build_proposition_fragment_candidates(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )

    expression = tuple(
        item for item in candidates if PropositionFragmentReason.EVENT_EXPRESSION in item.reasons
    )
    model_candidates = tuple(item for item in candidates if item not in expression)
    assert len(expression) == 1
    assert expression[0].text == "decision to attend Forum"
    assert all(item.end <= trigger.start or item.start >= trigger.end for item in model_candidates)
    assert "to attend Forum and report" not in {item.text for item in candidates}


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


def test_marker_free_model_task_preserves_source_and_uses_plain_field_labels() -> None:
    source, trigger, event, linguistic = _attributed_fixture()
    candidates = build_proposition_fragment_candidates(
        source_text=source,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )
    candidate = next(item for item in candidates if item.text == "Sacks")

    task = marker_free_proposition_fragment_model_task_input(
        source_text=source,
        trigger=trigger,
        candidate=candidate,
    )

    assert task.status is PropositionFragmentTaskInputStatus.READY
    assert task.event_occurrence_count == 1
    assert task.candidate_occurrence_count == 1
    assert task.reason_code is None
    assert task.rendered_input == (
        "Passage:\n"
        "Sacks stated that Anthropic was running a strategy.\n\n"
        "Event:\nrunning\n\n"
        "Candidate:\nSacks\n"
    )
    assert "<source>" not in task.rendered_input
    assert "<event>" not in task.rendered_input
    assert "<candidate>" not in task.rendered_input
    assert candidate.id not in task.rendered_input
    assert trigger.id not in task.rendered_input


def test_marker_free_model_task_blocks_repeated_candidate_literal() -> None:
    source = "Sacks stated that Sacks was running a strategy."
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    trigger_start = source.index("running")
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id="seg_repeated_candidate",
            source_text_sha256=source_digest,
            start=trigger_start,
            end=trigger_start + len("running"),
            text="running",
            head_start=trigger_start,
            head_end=trigger_start + len("running"),
            head_text="running",
            event_type_label="unmapped",
            extraction_task_id="ext_repeated_candidate",
            model_run_id="mrn_repeated_candidate",
            trace_id="xst_" + "2" * 24,
        ),
        source_segment_id="seg_repeated_candidate",
        source_text_sha256=source_digest,
        start=trigger_start,
        end=trigger_start + len("running"),
        text="running",
        head_start=trigger_start,
        head_end=trigger_start + len("running"),
        head_text="running",
        event_type_label="unmapped",
        extraction_task_id="ext_repeated_candidate",
        model_run_id="mrn_repeated_candidate",
        trace_id="xst_" + "2" * 24,
    )
    reasons = (PropositionFragmentReason.GOVERNING_CONTEXT,)
    candidate_id = proposition_fragment_candidate_id(
        source_grounded_event_id="sge_" + "3" * 24,
        event_trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        start=0,
        end=len("Sacks"),
        text="Sacks",
        reasons=reasons,
        linguistic_token_ids=("t1",),
        source_record_ids=("trace_fixture",),
    )
    candidate = PropositionFragmentCandidate(
        id=candidate_id,
        source_grounded_event_id="sge_" + "3" * 24,
        event_trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        start=0,
        end=len("Sacks"),
        text="Sacks",
        reasons=reasons,
        linguistic_token_ids=("t1",),
        source_record_ids=("trace_fixture",),
    )

    task = marker_free_proposition_fragment_model_task_input(
        source_text=source,
        trigger=trigger,
        candidate=candidate,
    )

    assert task.status is PropositionFragmentTaskInputStatus.OCCURRENCE_AMBIGUOUS
    assert task.event_occurrence_count == 1
    assert task.candidate_occurrence_count == 2
    assert task.rendered_input is None
    assert task.rendered_input_sha256 is None
    assert task.reason_code == "candidate_occurrence_ambiguous"


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


def _fixture_from_specs(
    source: str,
    trigger_ordinal: int,
    specs: tuple[tuple[str, int | None, str, str], ...],
    *,
    trigger_expression_ordinals: tuple[int, int] | None = None,
) -> tuple[EventTriggerDraft, SourceGroundedEventDraft, EventEntityLinguisticEvidence]:
    positions: list[tuple[int, int]] = []
    cursor = 0
    for text, _head, _relation, _part_of_speech in specs:
        start = source.index(text, cursor)
        end = start + len(text)
        positions.append((start, end))
        cursor = end
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    head_start, head_end = positions[trigger_ordinal - 1]
    expression_start_ordinal, expression_end_ordinal = trigger_expression_ordinals or (
        trigger_ordinal,
        trigger_ordinal,
    )
    trigger_start = positions[expression_start_ordinal - 1][0]
    trigger_end = positions[expression_end_ordinal - 1][1]
    trigger_text = source[trigger_start:trigger_end]
    head_text = specs[trigger_ordinal - 1][0]
    trace_id = "xst_" + "5" * 24
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id="seg_clause_local_fixture",
            source_text_sha256=source_digest,
            start=trigger_start,
            end=trigger_end,
            text=trigger_text,
            head_start=head_start,
            head_end=head_end,
            head_text=head_text,
            event_type_label="unmapped",
            extraction_task_id="ext_clause_local_fixture",
            model_run_id="mrn_clause_local_fixture",
            trace_id=trace_id,
        ),
        source_segment_id="seg_clause_local_fixture",
        source_text_sha256=source_digest,
        start=trigger_start,
        end=trigger_end,
        text=trigger_text,
        head_start=head_start,
        head_end=head_end,
        head_text=head_text,
        event_type_label="unmapped",
        extraction_task_id="ext_clause_local_fixture",
        model_run_id="mrn_clause_local_fixture",
        trace_id=trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "5" * 24,
        trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        expression_text=trigger.text,
        head_text=trigger.head_text,
        head_evidence_target_id="etg_" + "5" * 24,
        expression_evidence_target_id="etg_" + "6" * 24,
        support_evidence_target_id="etg_" + "7" * 24,
    )
    tokens = tuple(
        EventEntityLinguisticToken(
            token_id=f"t{ordinal}",
            sentence_id="s1",
            text=text,
            start=positions[ordinal - 1][0],
            end=positions[ordinal - 1][1],
            lemma=text.casefold(),
            part_of_speech=part_of_speech,
            dependency_relation=relation,
            head_token_id=None if head is None else f"t{head}",
        )
        for ordinal, (text, head, relation, part_of_speech) in enumerate(specs, start=1)
    )
    linguistic = EventEntityLinguisticEvidence(
        trace_id="xst_" + "6" * 24,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        producer_id="stanza_pipeline_v1",
        model_id="stanza_english_ewt",
        model_version="fixture",
        resource_identity="6" * 64,
        tokens=tokens,
    )
    return trigger, event, linguistic
