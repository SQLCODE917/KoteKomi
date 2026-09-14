from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    ContextualKind,
    DiscourseRole,
    EntityInvolvementAnswerValue,
    EventEntityCandidateGapReason,
    EventEntityConnectionDisposition,
    EventEntityKind,
    EventEntityMentionInput,
    EventEntitySourceSpan,
    MentionBoundaryStatus,
    ReferenceStatus,
    Referentiality,
    SourceGroundedEventDraft,
    build_entity_involvement_judgment,
    build_event_entity_connection_candidates,
    build_source_grounded_event_draft,
    decide_event_entity_connection,
    entity_involvement_answer_schema_bytes,
    event_entity_model_task_input,
    parse_entity_involvement_answer,
    select_event_entity_mentions,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceDecision,
    ReferenceSpan,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    MentionBoundaryDecision,
    MentionCandidate,
    MentionInterpretation,
)


def test_entity_involvement_output_is_one_finite_answer() -> None:
    assert parse_entity_involvement_answer(b"Y").value is EntityInvolvementAnswerValue.YES
    assert parse_entity_involvement_answer(b"N").value is EntityInvolvementAnswerValue.NO
    assert parse_entity_involvement_answer(b"U").value is EntityInvolvementAnswerValue.UNCERTAIN
    assert (
        entity_involvement_answer_schema_bytes() == b"Return exactly one character: Y, N, or U.\n"
    )

    for invalid in (b"yes", b"Y\nN", b" Y", b"", b"\xff"):
        with pytest.raises(ValueError):
            parse_entity_involvement_answer(invalid)


def test_candidate_builder_deduplicates_one_entity_and_preserves_source_evidence() -> None:
    source = "Anthropic said Anthropic would participate."
    event = _event(source, expression="would participate")
    first_start = source.index("Anthropic")
    second_start = source.index("Anthropic", first_start + 1)
    mentions = (
        _mention(source, first_start, "mnc_" + "1" * 24, "etg_" + "4" * 24),
        _mention(source, second_start, "mnc_" + "2" * 24, "etg_" + "5" * 24),
    )

    candidates = build_event_entity_connection_candidates(
        event,
        mentions,
        source_text=source,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.entity_name == "Anthropic"
    assert tuple(item.mention_candidate_id for item in candidate.source_spans) == (
        "mnc_" + "1" * 24,
        "mnc_" + "2" * 24,
    )
    assert candidate.source_spans[0].start == first_start


def test_candidate_builder_rejects_cross_segment_entity_evidence() -> None:
    source = "Anthropic participated."
    event = _event(source, expression="participated")
    mention = _mention(source, 0, "mnc_" + "1" * 24, "etg_" + "4" * 24)
    changed_span = mention.source_span.model_copy(update={"source_segment_id": "seg_other"})
    mention = mention.model_copy(update={"source_span": changed_span})

    with pytest.raises(ValueError, match="share the Event SourceSegment"):
        build_event_entity_connection_candidates(event, (mention,), source_text=source)


def test_model_task_contains_one_plain_language_pair_and_no_internal_ids() -> None:
    source = "Hegseth publicly rebuked Dario Amodei's approach."
    event = _event(source, expression="rebuked")
    start = source.index("Dario Amodei")
    candidate = build_event_entity_connection_candidates(
        event,
        (
            EventEntityMentionInput(
                entity_identity="actor:dario-amodei",
                entity_kind=EventEntityKind.ACTOR,
                entity_name="Dario Amodei",
                source_span=_source_span(
                    source,
                    start,
                    "Dario Amodei",
                    "mnc_" + "1" * 24,
                ),
            ),
        ),
        source_text=source,
    )[0]

    task = event_entity_model_task_input(source, candidate).decode()

    assert source in task
    assert '"rebuked"' in task
    assert '"Dario Amodei"' in task
    assert "mnc_" not in task
    assert "sge_" not in task
    assert "etg_" not in task
    assert "start" not in task


@pytest.mark.parametrize(
    ("answer", "disposition", "has_draft"),
    (
        (
            EntityInvolvementAnswerValue.YES,
            EventEntityConnectionDisposition.CONNECTED,
            True,
        ),
        (
            EntityInvolvementAnswerValue.NO,
            EventEntityConnectionDisposition.NOT_CONNECTED,
            False,
        ),
        (
            EntityInvolvementAnswerValue.UNCERTAIN,
            EventEntityConnectionDisposition.UNRESOLVED,
            False,
        ),
    ),
)
def test_only_yes_creates_connection_draft(
    answer: EntityInvolvementAnswerValue,
    disposition: EventEntityConnectionDisposition,
    has_draft: bool,
) -> None:
    source = "Anthropic participated."
    event = _event(source, expression="participated")
    candidate = build_event_entity_connection_candidates(
        event,
        (_mention(source, 0, "mnc_" + "1" * 24, "etg_" + "4" * 24),),
        source_text=source,
    )[0]
    judgment = build_entity_involvement_judgment(
        candidate_id=candidate.id,
        answer=answer,
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        trace_id="xst_" + "8" * 24,
    )

    decision, draft = decide_event_entity_connection(candidate, judgment)

    assert decision.disposition is disposition
    assert (draft is not None) is has_draft
    if draft is not None:
        assert draft.entity_name == "Anthropic"
        assert draft.entity_source_span_ids == (candidate.source_spans[0].id,)
        assert draft.event_mention_id == event.mention.id
        assert draft.model_run_id == "mrn_fixture"


def test_failed_model_judgment_is_typed_unresolved() -> None:
    source = "Anthropic participated."
    event = _event(source, expression="participated")
    candidate = build_event_entity_connection_candidates(
        event,
        (_mention(source, 0, "mnc_" + "1" * 24, "etg_" + "4" * 24),),
        source_text=source,
    )[0]

    decision, draft = decide_event_entity_connection(candidate, None)

    assert decision.disposition is EventEntityConnectionDisposition.UNRESOLVED
    assert decision.reason_code == "model_judgment_failed"
    assert draft is None


def test_selector_maps_person_and_government_mentions_without_semantic_repair() -> None:
    source = "Hegseth said the United States acted."
    event = _event(source, expression="acted")
    hegseth = _upstream_candidate(source, "Hegseth", "1")
    united_states = _upstream_candidate(source, "United States", "2")
    mention_preview = _mention_preview(
        (hegseth, united_states),
        (
            _interpretation(hegseth, ContextualKind.PERSON, "3"),
            _interpretation(united_states, ContextualKind.GOVERNMENT, "4"),
        ),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "5" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ACTOR, "Hegseth"),
        (EventEntityKind.ORGANIZATION, "United States"),
    ]
    assert selection.gaps == ()


def test_selector_preserves_resolved_antecedent_and_types_boundary_ambiguity() -> None:
    source = "Dario Amodei spoke after he arrived."
    event = _event(source, expression="arrived")
    actor = _upstream_candidate(source, "Dario Amodei", "1")
    pronoun = _upstream_candidate(source, "he", "2")
    ambiguous = _upstream_candidate(source, "Amodei", "3")
    selected_decisions = tuple(
        _boundary_decision(item, selected=True, suffix=str(index))
        for index, item in enumerate((actor, pronoun), start=1)
    )
    ambiguous_decision = _boundary_decision(ambiguous, selected=False, suffix="3")
    mention_preview = _mention_preview(
        (actor, ambiguous, pronoun),
        (
            _interpretation(actor, ContextualKind.PERSON, "4"),
            _interpretation(ambiguous, ContextualKind.PERSON, "5"),
            _interpretation(
                pronoun,
                ContextualKind.PERSON,
                "6",
                referentiality=Referentiality.ANAPHORIC,
            ),
        ),
        boundary_decisions=(*selected_decisions, ambiguous_decision),
    )
    antecedent_text = "Dario Amodei"
    antecedent_digest = hashlib.sha256(antecedent_text.encode()).hexdigest()
    antecedent_parts = (
        "rep_fixture",
        "nod_fixture",
        "tvw_fixture",
        "0",
        str(len(antecedent_text)),
        antecedent_digest,
    )
    antecedent = ReferenceSpan(
        id="rsp_" + hashlib.sha256(chr(31).join(antecedent_parts).encode()).hexdigest()[:24],
        representation_id="rep_fixture",
        node_id="nod_fixture",
        text_view_id="tvw_fixture",
        start_char=0,
        end_char=len(antecedent_text),
        text=antecedent_text,
        text_sha256=antecedent_digest,
    )
    reference = ReferenceDecision.model_construct(
        id="rfd_" + "8" * 24,
        candidate_id=pronoun.id,
        status=ReferenceStatus.RESOLVED,
        antecedent_span_ids=(antecedent.id,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "9" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(reference,),
        semantic_antecedent_spans=(antecedent,),
        alias_declarations=(),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
    )

    resolved = next(item for item in selection.mentions if item.source_span.text == "he")
    assert resolved.entity_name == "Dario Amodei"
    assert resolved.resolved_antecedent_span == antecedent
    assert resolved.source_span.reference_decision_id == reference.id
    assert len(selection.gaps) == 1
    assert selection.gaps[0].mention_text == "Amodei"
    assert selection.gaps[0].reason is EventEntityCandidateGapReason.BOUNDARY_AMBIGUOUS


def _event(source: str, *, expression: str) -> SourceGroundedEventDraft:
    return build_source_grounded_event_draft(
        event_subject_id="esd_" + "1" * 24,
        trigger_id="etd_" + "2" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        expression_text=expression,
        head_text=expression.split()[-1],
        head_evidence_target_id="etg_" + "1" * 24,
        expression_evidence_target_id="etg_" + "2" * 24,
        support_evidence_target_id="etg_" + "3" * 24,
    )


def _mention(
    source: str,
    start: int,
    candidate_id: str,
    _evidence_target_id: str,
) -> EventEntityMentionInput:
    text = "Anthropic"
    return EventEntityMentionInput(
        entity_identity="organization:anthropic",
        entity_kind=EventEntityKind.ORGANIZATION,
        entity_name=text,
        source_span=_source_span(source, start, text, candidate_id),
    )


def _source_span(
    source: str,
    start: int,
    text: str,
    candidate_id: str,
) -> EventEntitySourceSpan:
    digest = hashlib.sha256(source.encode()).hexdigest()
    values = (
        "seg_fixture",
        digest,
        str(start),
        str(start + len(text)),
        text,
        candidate_id,
        "",
    )
    span_id = "ees_" + hashlib.sha256(chr(31).join(values).encode()).hexdigest()[:24]
    return EventEntitySourceSpan(
        id=span_id,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=start,
        end=start + len(text),
        text=text,
        mention_candidate_id=candidate_id,
    )


def _upstream_candidate(source: str, text: str, suffix: str) -> MentionCandidate:
    start = source.index(text)
    digest = hashlib.sha256(source.encode()).hexdigest()
    candidate_id = (
        "mnc_"
        + hashlib.sha256(
            chr(31).join(("seg_fixture", digest, str(start), str(start + len(text)), text)).encode()
        ).hexdigest()[:24]
    )
    return MentionCandidate(
        id=candidate_id,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=start,
        end=start + len(text),
        text=text,
        observation_ids=("mob_" + suffix * 24,),
        type_hints=(ContextualKind.PERSON,),
    )


def _boundary_decision(
    candidate: MentionCandidate,
    *,
    selected: bool,
    suffix: str,
) -> MentionBoundaryDecision:
    return MentionBoundaryDecision.model_construct(
        id="mbd_" + suffix * 24,
        source_segment_id=candidate.source_segment_id,
        status=(MentionBoundaryStatus.RESOLVED if selected else MentionBoundaryStatus.AMBIGUOUS),
        candidate_ids=(candidate.id,),
        selected_candidate_ids=(candidate.id,) if selected else (),
    )


def _interpretation(
    candidate: MentionCandidate,
    kind: ContextualKind,
    suffix: str,
    *,
    referentiality: Referentiality = Referentiality.SPECIFIC_ENTITY,
) -> MentionInterpretation:
    return MentionInterpretation.model_construct(
        id="mit_" + suffix * 24,
        candidate_id=candidate.id,
        referentiality=referentiality,
        contextual_kind=kind,
        discourse_role=DiscourseRole.ACTOR,
        support_segment_id=candidate.source_segment_id,
    )


def _mention_preview(
    candidates: tuple[MentionCandidate, ...],
    interpretations: tuple[MentionInterpretation, ...],
    *,
    boundary_decisions: tuple[MentionBoundaryDecision, ...] | None = None,
) -> HybridExtractionPreview:
    decisions = boundary_decisions or tuple(
        _boundary_decision(item, selected=True, suffix=str(index))
        for index, item in enumerate(candidates, start=1)
    )
    return HybridExtractionPreview.model_construct(
        id="hxp_" + "a" * 24,
        candidates=candidates,
        boundary_decisions=decisions,
        boundary_adjudications=(),
        interpretations=interpretations,
    )
