from __future__ import annotations

import hashlib
import re

import pytest
from kotekomi_application import (
    ContextualKind,
    DiscourseRole,
    EntityInvolvementAnswerValue,
    EntityLinkCandidate,
    EntityLinkCandidateKind,
    EntityLinkEvidence,
    EventEntityCandidateGapReason,
    EventEntityCandidateRoute,
    EventEntityConnectionCandidate,
    EventEntityConnectionDisposition,
    EventEntityDenotationRule,
    EventEntityGapDependencyRule,
    EventEntityKind,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventEntityMentionInput,
    EventEntitySourceSpan,
    ExternalEntityClass,
    HybridEntityGroundingPreview,
    LinkedEntityClassEvidence,
    MentionBoundaryStatus,
    ReferenceStatus,
    Referentiality,
    SourceGroundedEventDraft,
    build_entity_involvement_judgment,
    build_event_entity_candidate_routes,
    build_event_entity_connection_candidates,
    build_extraction_stage_trace,
    build_source_grounded_event_draft,
    consolidate_event_entity_connections,
    decide_event_entity_connection,
    entity_involvement_answer_batch_schema_bytes,
    event_entity_linguistic_evidence_from_trace,
    event_entity_model_task_input,
    parse_entity_involvement_answer_batch,
    select_event_entity_mentions,
)
from kotekomi_application.extraction_stage_trace import ExtractionStageStatus
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
    MentionObservation,
)
from kotekomi_application.semantic_references import CoreferenceObservation, CoreferenceSpan


def test_entity_involvement_output_is_one_finite_ordered_vector() -> None:
    assert parse_entity_involvement_answer_batch(b"YNU").values == (
        EntityInvolvementAnswerValue.YES,
        EntityInvolvementAnswerValue.NO,
        EntityInvolvementAnswerValue.UNCERTAIN,
    )
    assert b"one character per candidate" in entity_involvement_answer_batch_schema_bytes()

    for invalid in (b"yes", b"Y\nN", b" Y", b"", b"\xff"):
        with pytest.raises(ValueError):
            parse_entity_involvement_answer_batch(invalid)


def test_candidate_builder_preserves_each_exact_occurrence_until_event_assignment() -> None:
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

    assert len(candidates) == 2
    assert [item.entity_name for item in candidates] == ["Anthropic", "Anthropic"]
    assert [item.source_spans[0].mention_candidate_id for item in candidates] == [
        "mnc_" + "1" * 24,
        "mnc_" + "2" * 24,
    ]
    assert [item.source_spans[0].start for item in candidates] == [first_start, second_start]
    assert candidates[0].id != candidates[1].id

    first_judgment = build_entity_involvement_judgment(
        candidate_id=candidates[0].id,
        answer=EntityInvolvementAnswerValue.NO,
        extraction_task_id="ext_first",
        model_run_id="mrn_first",
        trace_id="xst_" + "a" * 24,
    )
    second_judgment = build_entity_involvement_judgment(
        candidate_id=candidates[1].id,
        answer=EntityInvolvementAnswerValue.YES,
        extraction_task_id="ext_second",
        model_run_id="mrn_second",
        trace_id="xst_" + "b" * 24,
    )
    routes = _candidate_routes(source, candidates)
    first_decision, _ = decide_event_entity_connection(candidates[0], routes[0], first_judgment)
    second_decision, _ = decide_event_entity_connection(candidates[1], routes[1], second_judgment)

    identity_connections = consolidate_event_entity_connections(
        candidates,
        (first_decision, second_decision),
    )

    assert len(identity_connections) == 1
    identity_connection = identity_connections[0]
    assert identity_connection.disposition is EventEntityConnectionDisposition.CONNECTED
    assert identity_connection.connected_candidate_ids == (candidates[1].id,)
    assert identity_connection.not_connected_candidate_ids == (candidates[0].id,)
    assert identity_connection.unresolved_candidate_ids == ()


def test_candidate_builder_rejects_cross_segment_entity_evidence() -> None:
    source = "Anthropic participated."
    event = _event(source, expression="participated")
    mention = _mention(source, 0, "mnc_" + "1" * 24, "etg_" + "4" * 24)
    changed_span = mention.source_span.model_copy(update={"source_segment_id": "seg_other"})
    mention = mention.model_copy(update={"source_span": changed_span})

    with pytest.raises(ValueError, match="share the Event SourceSegment"):
        build_event_entity_connection_candidates(event, (mention,), source_text=source)


def test_candidate_router_reserves_every_same_sentence_pair_for_qwen() -> None:
    source = "Dario Amodei criticized Stargate. Anthropic hired Amodei."
    event = _event(source, expression="criticized")

    def mention(text: str, start: int, suffix: str, identity: str) -> EventEntityMentionInput:
        return EventEntityMentionInput(
            entity_identity=identity,
            entity_kind=EventEntityKind.ACTOR,
            entity_name=text,
            denotation_decision_id="edd_" + suffix * 24,
            source_span=_source_span(source, start, text, "mnc_" + suffix * 24),
        )

    full_start = source.index("Dario Amodei")
    candidates = build_event_entity_connection_candidates(
        event,
        (
            mention("Dario Amodei", full_start, "1", "actor:dario-amodei"),
            mention("Amodei", full_start + len("Dario "), "2", "actor:amodei"),
            mention(
                "Anthropic",
                source.index("Anthropic"),
                "3",
                "organization:anthropic",
            ),
        ),
        source_text=source,
    )

    routes = _candidate_routes(source, candidates)
    route_by_name = {
        candidate.entity_name: route for candidate, route in zip(candidates, routes, strict=True)
    }

    assert route_by_name["Dario Amodei"].route.value == "model_judgment"
    assert route_by_name["Amodei"].reason.value == "semantic_judgment_required"
    assert route_by_name["Anthropic"].reason.value == "different_linguistic_sentence"


def test_linguistic_trace_mapping_preserves_pinned_specialist_identity_and_source_ranges() -> None:
    source = "Anthropic criticized Stargate."
    fixture = _candidate_routes_linguistic_evidence(source)
    trace = build_extraction_stage_trace(
        trace_run_id="event_trigger:fixture",
        ordinal=0,
        stage_id="linguistic_analysis",
        stage_version="stanza-en:fixture",
        producer_id=fixture.producer_id,
        source_segment_id=fixture.source_segment_id,
        source_text_sha256=fixture.source_text_sha256,
        configuration={
            "model_id": fixture.model_id,
            "model_version": fixture.model_version,
            "resource_identity": fixture.resource_identity,
        },
        input_payload={"source_copy_text": source},
        output_payload={
            "source_text_sha256": fixture.source_text_sha256,
            "tokens": [item.model_dump(mode="json") for item in fixture.tokens],
        },
        status=ExtractionStageStatus.COMPLETED,
    )

    mapped = event_entity_linguistic_evidence_from_trace(trace, source_text=source)

    assert mapped.trace_id == trace.id
    assert mapped.resource_identity == fixture.resource_identity
    assert tuple((item.start, item.end, item.text) for item in mapped.tokens) == tuple(
        (item.start, item.end, item.text) for item in fixture.tokens
    )
    with pytest.raises(ValueError, match="matching completed linguistic evidence"):
        event_entity_linguistic_evidence_from_trace(trace, source_text=source + " changed")


def test_model_task_contains_one_plain_language_inventory_and_no_internal_ids() -> None:
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
                denotation_decision_id="edd_" + "1" * 24,
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

    task = event_entity_model_task_input(source, (candidate,)).decode()

    assert "Ordered candidate inventory" in task
    assert "Candidate 1 source passage" in task
    assert "<event>rebuked</event>" in task
    assert "<entity>Dario Amodei</entity>" in task
    assert "mnc_" not in task
    assert "sge_" not in task
    assert "etg_" not in task
    assert "start" not in task
    assert "Resolved entity name" not in task
    assert "resolves to this entity name" not in task


def test_model_task_distinguishes_repeated_entity_occurrences() -> None:
    source = "Anthropic said Anthropic would participate."
    event = _event(source, expression="would participate")
    first_start = source.index("Anthropic")
    second_start = source.index("Anthropic", first_start + 1)
    candidates = build_event_entity_connection_candidates(
        event,
        (
            _mention(source, first_start, "mnc_" + "1" * 24, "etg_" + "4" * 24),
            _mention(source, second_start, "mnc_" + "2" * 24, "etg_" + "5" * 24),
        ),
        source_text=source,
    )

    task = event_entity_model_task_input(source, candidates).decode()

    assert "<entity>Anthropic</entity> said Anthropic" in task
    assert "Anthropic said <entity>Anthropic</entity>" in task
    assert task.count("<event>would participate</event>") == 2
    assert "Return exactly 2 answer characters" in task


def test_model_task_nests_an_entity_inside_the_exact_event_expression() -> None:
    source = "Amodei made a decision over Trump's inauguration."
    expression = "decision over Trump's inauguration"
    event = _event(source, expression=expression)
    start = source.index("Trump")
    candidate = build_event_entity_connection_candidates(
        event,
        (
            EventEntityMentionInput(
                entity_identity="actor:trump",
                entity_kind=EventEntityKind.ACTOR,
                entity_name="Trump",
                denotation_decision_id="edd_" + "1" * 24,
                source_span=_source_span(
                    source,
                    start,
                    "Trump",
                    "mnc_" + "1" * 24,
                ),
            ),
        ),
        source_text=source,
    )[0]

    task = event_entity_model_task_input(source, (candidate,)).decode()

    assert "<event>decision over <entity>Trump</entity>'s inauguration</event>" in task


def test_model_task_rejects_an_unaddressed_repeated_event_expression() -> None:
    source = "Anthropic said it had said enough."
    event = _event(source, expression="said")
    candidate = build_event_entity_connection_candidates(
        event,
        (_mention(source, 0, "mnc_" + "1" * 24, "etg_" + "4" * 24),),
        source_text=source,
    )[0]

    with pytest.raises(ValueError, match="one exact Event expression occurrence"):
        event_entity_model_task_input(source, (candidate,))


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

    route = _candidate_routes(source, (candidate,))[0]
    decision, draft = decide_event_entity_connection(candidate, route, judgment)

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

    route = _candidate_routes(source, (candidate,))[0]
    decision, draft = decide_event_entity_connection(candidate, route, None)

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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ACTOR, "Hegseth"),
        (EventEntityKind.ORGANIZATION, "United States"),
    ]
    assert selection.gaps == ()
    assert [item.rule_id for item in selection.denotation_decisions] == [
        EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND,
        EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND,
    ]


def test_selector_rejects_grounding_from_another_reference_preview() -> None:
    source = "Anthropic acted."
    event = _event(source, expression="acted")
    candidate = _upstream_candidate(source, "Anthropic", "1")
    mention_preview = _mention_preview(
        (candidate,),
        (_interpretation(candidate, ContextualKind.ORGANIZATION, "2"),),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )
    grounding_preview = HybridEntityGroundingPreview.model_construct(
        id="hgp_" + "4" * 24,
        parent_preview_id="hrp_" + "5" * 24,
        mention_preview_id=mention_preview.id,
        link_evidence=(),
    )

    with pytest.raises(ValueError, match="another upstream Preview"):
        select_event_entity_mentions(
            source_text=source,
            event=event,
            mention_preview=mention_preview,
            reference_preview=reference_preview,
            grounding_preview=grounding_preview,
        )


def test_strong_person_observation_cannot_be_overwritten_by_government_interpretation() -> None:
    source = "Trump rescinded the order."
    event = _event(source, expression="rescinded")
    trump = _upstream_candidate(source, "Trump", "1")
    observation = _observation(trump, ContextualKind.PERSON, "gliner:fixture")
    trump = trump.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (trump,),
        (_interpretation(trump, ContextualKind.GOVERNMENT, "2"),),
        observations=(observation,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ACTOR, "Trump")
    ]
    assert len(selection.denotation_decisions) == 1
    decision = selection.denotation_decisions[0]
    assert decision.rule_id is EventEntityDenotationRule.SPECIALIST_PERSON_EVIDENCE
    assert decision.source_evidence_ids == (observation.id,)
    assert decision.mention_interpretation_id == mention_preview.interpretations[0].id
    assert decision.diagnostics == ("model_contextual_kind_overridden:government",)


def test_person_specialists_do_not_override_explicit_organization_usage() -> None:
    source = "The court denied Anthropic's motion."
    event = _event(source, expression="denied")
    anthropic = _upstream_candidate(source, "Anthropic", "1")
    observation = _observation(anthropic, ContextualKind.PERSON, "gliner:fixture")
    anthropic = anthropic.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (anthropic,),
        (_interpretation(anthropic, ContextualKind.ORGANIZATION, "2"),),
        observations=(observation,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )
    link_evidence = EntityLinkEvidence.model_construct(
        id="ele_" + "4" * 24,
        candidate_id=anthropic.id,
        coarse_mention_type="PERSON",
        candidates=(),
        linked_entity_classes=None,
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(
            mention_preview,
            reference_preview,
            link_evidence=(link_evidence,),
        ),
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ORGANIZATION, "Anthropic")
    ]
    decision = selection.denotation_decisions[0]
    assert decision.rule_id is EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND
    assert decision.source_evidence_ids == (observation.id,)
    assert decision.mention_interpretation_id == mention_preview.interpretations[0].id
    assert decision.diagnostics == ()


def test_refined_org_evidence_can_rescue_a_named_initiative_as_an_organization() -> None:
    source = "Anthropic worked with Open Philanthropy."
    event = _event(source, expression="worked")
    organization = _upstream_candidate(
        source,
        "Open Philanthropy",
        "1",
        kind=ContextualKind.INITIATIVE,
    )
    observation = _observation(organization, ContextualKind.INITIATIVE, "gliner:fixture")
    organization = organization.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (organization,),
        (_interpretation(organization, ContextualKind.INITIATIVE, "2"),),
        observations=(observation,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )
    link_evidence = EntityLinkEvidence.model_construct(
        id="ele_" + "4" * 24,
        candidate_id=organization.id,
        coarse_mention_type="ORG",
        candidates=(),
        linked_entity_classes=None,
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(
            mention_preview,
            reference_preview,
            link_evidence=(link_evidence,),
        ),
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ORGANIZATION, "Open Philanthropy")
    ]
    decision = selection.denotation_decisions[0]
    assert decision.rule_id is EventEntityDenotationRule.SPECIALIST_ORGANIZATION_EVIDENCE
    assert decision.source_evidence_ids == (link_evidence.id,)
    assert decision.diagnostics == ("model_contextual_kind_overridden:initiative",)


def test_exact_external_identity_class_can_rescue_named_institutional_program() -> None:
    source = "Companies offered services with FedRAMP authorization."
    event = _event(source, expression="offered")
    program = _upstream_candidate(source, "FedRAMP", "1", kind=ContextualKind.POLICY)
    mention_preview = _mention_preview(
        (program,),
        (_interpretation(program, ContextualKind.POLICY, "2"),),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )
    link_evidence = EntityLinkEvidence.model_construct(
        id="ele_" + "4" * 24,
        candidate_id=program.id,
        coarse_mention_type=None,
        candidates=(
            EntityLinkCandidate(
                rank=1,
                kind=EntityLinkCandidateKind.KNOWLEDGE_BASE_ENTITY,
                wikidata_id="Q21070748",
                wikipedia_title="FedRAMP",
                score=0.9358,
            ),
        ),
        linked_entity_classes=LinkedEntityClassEvidence(
            wikidata_id="Q21070748",
            classes=(ExternalEntityClass(class_id="Q43229", label="organization"),),
        ),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(
            mention_preview,
            reference_preview,
            link_evidence=(link_evidence,),
        ),
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ORGANIZATION, "FedRAMP")
    ]
    decision = selection.denotation_decisions[0]
    assert decision.rule_id is EventEntityDenotationRule.EXTERNAL_ORGANIZATION_CLASS
    assert decision.source_evidence_ids == (link_evidence.id,)
    assert decision.diagnostics == (
        "external_organization_class:Q21070748:Q43229",
        "model_contextual_kind_overridden:policy",
    )


def test_external_organization_class_requires_exact_linked_title() -> None:
    source = "Companies offered services with FedRAMP authorization."
    event = _event(source, expression="offered")
    program = _upstream_candidate(source, "FedRAMP", "1", kind=ContextualKind.INITIATIVE)
    mention_preview = _mention_preview(
        (program,),
        (_interpretation(program, ContextualKind.INITIATIVE, "2"),),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )
    link_evidence = EntityLinkEvidence.model_construct(
        id="ele_" + "4" * 24,
        candidate_id=program.id,
        coarse_mention_type=None,
        candidates=(
            EntityLinkCandidate(
                rank=1,
                kind=EntityLinkCandidateKind.KNOWLEDGE_BASE_ENTITY,
                wikidata_id="Q21070748",
                wikipedia_title="Different Program",
                score=0.9358,
            ),
        ),
        linked_entity_classes=LinkedEntityClassEvidence(
            wikidata_id="Q21070748",
            classes=(ExternalEntityClass(class_id="Q43229", label="organization"),),
        ),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(
            mention_preview,
            reference_preview,
            link_evidence=(link_evidence,),
        ),
    )

    assert selection.mentions == ()
    assert selection.denotation_decisions == ()


def test_refined_org_evidence_can_rescue_a_named_publication_as_an_organization() -> None:
    source = "Amodei wrote an op-ed in The New York Times."
    event = _event(source, expression="wrote")
    publication = _upstream_candidate(
        source,
        "The New York Times",
        "1",
        kind=ContextualKind.PUBLICATION,
    )
    observation = _observation(
        publication,
        ContextualKind.PUBLICATION,
        "gliner:fixture",
    )
    publication = publication.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (publication,),
        (_interpretation(publication, ContextualKind.PUBLICATION, "2"),),
        observations=(observation,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )
    link_evidence = EntityLinkEvidence.model_construct(
        id="ele_" + "4" * 24,
        candidate_id=publication.id,
        coarse_mention_type="ORG",
        candidates=(),
        linked_entity_classes=None,
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(
            mention_preview,
            reference_preview,
            link_evidence=(link_evidence,),
        ),
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ORGANIZATION, "The New York Times")
    ]
    decision = selection.denotation_decisions[0]
    assert decision.rule_id is EventEntityDenotationRule.SPECIALIST_ORGANIZATION_EVIDENCE
    assert decision.source_evidence_ids == (link_evidence.id,)
    assert decision.diagnostics == ("model_contextual_kind_overridden:publication",)


def test_specialist_organization_label_does_not_override_contextual_event_usage() -> None:
    source = "Amodei decided to attend the World Economic Forum."
    event = _event(source, expression="decided")
    forum = _upstream_candidate(
        source,
        "World Economic Forum",
        "1",
        kind=ContextualKind.INITIATIVE,
    )
    mention_preview = _mention_preview(
        (forum,),
        (_interpretation(forum, ContextualKind.EVENT, "2"),),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
    )
    link_evidence = EntityLinkEvidence.model_construct(
        id="ele_" + "4" * 24,
        candidate_id=forum.id,
        coarse_mention_type="ORG",
        candidates=(),
        linked_entity_classes=None,
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(
            mention_preview,
            reference_preview,
            link_evidence=(link_evidence,),
        ),
    )

    assert selection.mentions == ()
    assert selection.denotation_decisions == ()
    assert selection.gaps == ()


def test_exact_gliner_person_survives_an_incomplete_overlap_judgment() -> None:
    source = "Amodei's statement included views espoused by vice president JD Vance."
    event = _event(source, expression="espoused")
    broad = _upstream_candidate(
        source,
        "Amodei's statement included views espoused by vice president JD Vance",
        "1",
        kind=ContextualKind.UNCLEAR,
    )
    vance = _upstream_candidate(source, "JD Vance", "2")
    observation = _observation(vance, ContextualKind.PERSON, "gliner:fixture")
    vance = vance.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (broad, vance),
        (_interpretation(broad, ContextualKind.PERSON, "3"),),
        boundary_decisions=(
            _boundary_decision(broad, selected=True, suffix="4"),
            _boundary_decision(vance, selected=False, suffix="5"),
        ),
        observations=(observation,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "6" * 24,
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    exact = next(item for item in selection.mentions if item.source_span.text == "JD Vance")
    assert exact.entity_kind is EventEntityKind.ACTOR
    assert exact.entity_name == "JD Vance"
    decision = next(
        item for item in selection.denotation_decisions if item.id == exact.denotation_decision_id
    )
    assert decision.rule_id is EventEntityDenotationRule.SPECIALIST_PERSON_EVIDENCE
    assert decision.source_evidence_ids == (observation.id,)


def test_exact_known_name_recurrence_supplies_a_missed_later_occurrence() -> None:
    source = "Trump acted before Trump officials met."
    event = _event(source, expression="met")
    first = _upstream_candidate(source, "Trump", "1")
    observation = _observation(first, ContextualKind.PERSON, "gliner:fixture")
    first = first.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (first,),
        (_interpretation(first, ContextualKind.PERSON, "2"),),
        observations=(observation,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
        coreference_observations=(),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    observed = [(item.entity_name, item.source_span.text) for item in selection.mentions]
    assert observed == [
        ("Trump", "Trump"),
        ("Trump", "Trump"),
        ("Trump officials", "Trump officials"),
    ]
    recurrence = next(
        item
        for item in selection.denotation_decisions
        if item.rule_id is EventEntityDenotationRule.KNOWN_NAME_RECURRENCE
    )
    assert recurrence.diagnostics == ("exact_name_recurrence",)


def test_entity_name_normalizes_pdf_whitespace_but_source_span_does_not() -> None:
    source = "Anthropic hired Biden  officials."
    event = _event(source, expression="hired")
    officials = _upstream_candidate(source, "Biden  officials", "1")
    mention_preview = _mention_preview(
        (officials,),
        (_interpretation(officials, ContextualKind.PERSON, "2"),),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    assert selection.mentions[0].entity_name == "Biden officials"
    assert selection.mentions[0].source_span.text == "Biden  officials"


def test_coreference_cluster_rescues_exact_known_name_occurrences_monotonically() -> None:
    source = "Sacks viewed Anthropic's policy before Anthropic responded."
    event = _event(source, expression="viewed")
    other_source = "Anthropic develops models."
    known = _candidate_in_segment(other_source, "Anthropic", "seg_other", "1")
    mention_preview = _mention_preview(
        (known,),
        (_interpretation(known, ContextualKind.ORGANIZATION, "2"),),
    )
    first_start = source.index("Anthropic")
    first_text = "Anthropic's"
    second_start = source.index("Anthropic", first_start + 1)
    first_span = _coreference_span(source, first_start, first_text)
    second_span = _coreference_span(source, second_start, "Anthropic")
    observation = CoreferenceObservation.model_construct(
        id="cfo_" + "3" * 24,
        source_segment_id=event.source_segment_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        clusters=((first_span, second_span),),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "4" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
        coreference_observations=(observation,),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    observed = [
        (item.entity_kind, item.entity_name, item.source_span.text) for item in selection.mentions
    ]
    assert observed == [
        (EventEntityKind.ORGANIZATION, "Anthropic", "Anthropic"),
        (EventEntityKind.ORGANIZATION, "Anthropic", "Anthropic's"),
        (EventEntityKind.ORGANIZATION, "Anthropic", "Anthropic"),
    ]
    assert all(
        item.rule_id is EventEntityDenotationRule.KNOWN_NAME_RECURRENCE
        for item in selection.denotation_decisions
    )
    possessive = next(
        item
        for item, mention in zip(
            selection.denotation_decisions,
            selection.mentions,
            strict=True,
        )
        if mention.source_span.text == "Anthropic's"
    )
    assert observation.id in possessive.source_evidence_ids


def test_coreference_rescue_does_not_promote_a_reference_marker_pronoun() -> None:
    source = "Trump changed his policy."
    event = _event(source, expression="changed")
    trump = _upstream_candidate(source, "Trump", "1")
    his = _upstream_candidate(source, "his", "2")
    trump_observation = _observation(trump, ContextualKind.PERSON, "gliner:fixture")
    his_observation = _observation(
        his,
        ContextualKind.PERSON,
        "kotekomi_reference_marker_v1",
    )
    trump = trump.model_copy(update={"observation_ids": (trump_observation.id,)})
    his = his.model_copy(update={"observation_ids": (his_observation.id,)})
    mention_preview = _mention_preview(
        (trump, his),
        (_interpretation(trump, ContextualKind.PERSON, "3"),),
        observations=(trump_observation, his_observation),
    )
    trump_span = _coreference_span(source, source.index("Trump"), "Trump")
    his_span = _coreference_span(source, source.index("his"), "his")
    observation = CoreferenceObservation.model_construct(
        id="cfo_" + "4" * 24,
        source_segment_id=event.source_segment_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        clusters=((trump_span, his_span),),
    )
    reference = ReferenceDecision.model_construct(
        id="rfd_" + "5" * 24,
        candidate_id=his.id,
        status=ReferenceStatus.AMBIGUOUS,
        antecedent_span_ids=("rsp_" + "6" * 24, "rsp_" + "7" * 24),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "8" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(reference,),
        semantic_antecedent_spans=(),
        alias_declarations=(),
        coreference_observations=(observation,),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    assert [item.entity_name for item in selection.mentions] == ["Trump"]
    assert len(selection.gaps) == 1
    assert selection.gaps[0].mention_text == "his"
    assert selection.gaps[0].reason is EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS


def test_role_qualified_plural_people_become_source_bound_actor_groups() -> None:
    source = "Trump officials met Biden  officials."
    event = _event(source, expression="met")
    trump = _upstream_candidate(source, "Trump", "1")
    biden = _upstream_candidate(source, "Biden", "2")
    trump_observation = _observation(trump, ContextualKind.PERSON, "gliner:fixture")
    biden_observation = _observation(biden, ContextualKind.PERSON, "gliner:fixture")
    trump = trump.model_copy(update={"observation_ids": (trump_observation.id,)})
    biden = biden.model_copy(update={"observation_ids": (biden_observation.id,)})
    mention_preview = _mention_preview(
        (trump, biden),
        (
            _interpretation(trump, ContextualKind.GOVERNMENT, "3"),
            _interpretation(biden, ContextualKind.PERSON, "4"),
        ),
        observations=(trump_observation, biden_observation),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "5" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(),
        semantic_antecedent_spans=(),
        alias_declarations=(),
        coreference_observations=(),
    )

    selection = select_event_entity_mentions(
        source_text=source,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    groups = tuple(
        item
        for item in selection.mentions
        if item.entity_name in {"Trump officials", "Biden officials"}
    )
    assert [(item.entity_kind, item.entity_name, item.source_span.text) for item in groups] == [
        (EventEntityKind.ACTOR, "Trump officials", "Trump officials"),
        (EventEntityKind.ACTOR, "Biden officials", "Biden  officials"),
    ]
    assert groups[0].entity_identity != next(
        item.entity_identity for item in selection.mentions if item.entity_name == "Trump"
    )
    decisions = {
        item.id: item
        for item in selection.denotation_decisions
        if item.rule_id is EventEntityDenotationRule.SOURCE_BOUND_ACTOR_GROUP
    }
    assert {item.denotation_decision_id for item in groups} == set(decisions)


def test_organization_representatives_become_a_source_bound_actor_group() -> None:
    source = "According to Reuters, Anthropic representatives opposed the designation."
    event = _event(source, expression="opposed")
    anthropic = _upstream_candidate(
        source,
        "Anthropic",
        "1",
        kind=ContextualKind.ORGANIZATION,
    )
    observation = _observation(anthropic, ContextualKind.ORGANIZATION, "gliner:fixture")
    anthropic = anthropic.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (anthropic,),
        (_interpretation(anthropic, ContextualKind.ORGANIZATION, "2"),),
        observations=(observation,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    assert [(item.entity_kind, item.entity_name) for item in selection.mentions] == [
        (EventEntityKind.ORGANIZATION, "Anthropic"),
        (EventEntityKind.ACTOR, "Anthropic representatives"),
    ]
    group = selection.mentions[1]
    assert group.source_span.text == "Anthropic representatives"
    decision = next(
        item for item in selection.denotation_decisions if item.id == group.denotation_decision_id
    )
    assert decision.rule_id is EventEntityDenotationRule.SOURCE_BOUND_ACTOR_GROUP
    assert decision.diagnostics == ("exact_named_agent_plus_plural_human_role",)


def test_source_bound_actor_group_replaces_same_range_organization_candidate() -> None:
    source = "Trump officials met."
    event = _event(source, expression="met")
    trump = _upstream_candidate(source, "Trump", "1")
    officials = _upstream_candidate(
        source,
        "Trump officials",
        "2",
        kind=ContextualKind.ORGANIZATION,
    )
    observation = _observation(trump, ContextualKind.PERSON, "gliner:fixture")
    trump = trump.model_copy(update={"observation_ids": (observation.id,)})
    mention_preview = _mention_preview(
        (trump, officials),
        (
            _interpretation(trump, ContextualKind.GOVERNMENT, "3"),
            _interpretation(officials, ContextualKind.ORGANIZATION, "4"),
        ),
        observations=(observation,),
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    full_span = tuple(
        item for item in selection.mentions if item.source_span.text == "Trump officials"
    )
    assert len(full_span) == 1
    assert full_span[0].entity_kind is EventEntityKind.ACTOR
    assert full_span[0].entity_name == "Trump officials"
    decision = next(
        item
        for item in selection.denotation_decisions
        if item.id == full_span[0].denotation_decision_id
    )
    assert decision.rule_id is EventEntityDenotationRule.SOURCE_BOUND_ACTOR_GROUP


def test_selector_preserves_resolved_antecedent_and_ignores_unrelated_boundary_ambiguity() -> None:
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    resolved = next(item for item in selection.mentions if item.source_span.text == "he")
    assert resolved.entity_name == "Dario Amodei"
    assert resolved.resolved_antecedent_span == antecedent
    assert resolved.source_span.reference_decision_id == reference.id
    assert selection.gaps == ()

    candidate = next(
        item
        for item in build_event_entity_connection_candidates(
            event,
            selection.mentions,
            source_text=source,
        )
        if item.primary_source_span_id == resolved.source_span.id
    )
    task = event_entity_model_task_input(source, (candidate,)).decode()
    assert "<entity>he</entity>" in task
    assert 'resolved entity name as a JSON string:\n"Dario Amodei"' in task


def test_boundary_ambiguity_is_a_gap_when_it_overlaps_the_event_expression() -> None:
    source = "The disputed proposal changed."
    event = _event(source, expression="disputed")
    ambiguous = _upstream_candidate(source, "disputed", "1")
    mention_preview = _mention_preview(
        (ambiguous,),
        (),
        boundary_decisions=(_boundary_decision(ambiguous, selected=False, suffix="2"),),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "3" * 24,
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    assert len(selection.gaps) == 1
    assert selection.gaps[0].reason is EventEntityCandidateGapReason.BOUNDARY_AMBIGUOUS
    assert selection.gap_dependencies[0].rule_id is EventEntityGapDependencyRule.EXPRESSION_OVERLAP


def test_resolved_reference_inherits_known_antecedent_denotation_without_interpretation() -> None:
    source = "Anthropic announced that it changed."
    event = _event(source, expression="announced")
    organization = _upstream_candidate(
        source,
        "Anthropic",
        "1",
        kind=ContextualKind.ORGANIZATION,
    )
    pronoun = _upstream_candidate(source, "it", "2")
    mention_preview = _mention_preview(
        (organization, pronoun),
        (_interpretation(organization, ContextualKind.ORGANIZATION, "3"),),
    )
    antecedent_text = "Anthropic"
    antecedent_digest = hashlib.sha256(antecedent_text.encode()).hexdigest()
    antecedent_values = (
        "rep_fixture",
        "nod_fixture",
        "tvw_fixture",
        "0",
        str(len(antecedent_text)),
        antecedent_digest,
    )
    antecedent = ReferenceSpan(
        id="rsp_" + hashlib.sha256(chr(31).join(antecedent_values).encode()).hexdigest()[:24],
        representation_id="rep_fixture",
        node_id="nod_fixture",
        text_view_id="tvw_fixture",
        start_char=0,
        end_char=len(antecedent_text),
        text=antecedent_text,
        text_sha256=antecedent_digest,
    )
    reference = ReferenceDecision.model_construct(
        id="rfd_" + "5" * 24,
        candidate_id=pronoun.id,
        status=ReferenceStatus.RESOLVED,
        antecedent_span_ids=(antecedent.id,),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "6" * 24,
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
        grounding_preview=_grounding_preview(mention_preview, reference_preview),
    )

    resolved = next(item for item in selection.mentions if item.source_span.text == "it")
    assert resolved.entity_kind is EventEntityKind.ORGANIZATION
    assert resolved.entity_name == "Anthropic"
    assert resolved.resolved_antecedent_span == antecedent
    decision = next(
        item
        for item in selection.denotation_decisions
        if item.id == resolved.denotation_decision_id
    )
    assert decision.rule_id is EventEntityDenotationRule.RESOLVED_REFERENCE
    assert reference.id in decision.source_evidence_ids
    assert antecedent.id in decision.source_evidence_ids
    assert selection.gaps == ()


def test_reference_gap_affects_only_an_immediately_adjacent_event_expression() -> None:
    source = "Amodei urged his associates to vote, describing him."
    his = _upstream_candidate(source, "his", "1")
    him = _upstream_candidate(source, "him", "2")
    mention_preview = _mention_preview((his, him), ())
    references = tuple(
        ReferenceDecision.model_construct(
            id="rfd_" + suffix * 24,
            candidate_id=candidate.id,
            status=ReferenceStatus.AMBIGUOUS,
            antecedent_span_ids=("rsp_" + "3" * 24, "rsp_" + "4" * 24),
        )
        for candidate, suffix in ((his, "5"), (him, "6"))
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "7" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=references,
        semantic_antecedent_spans=(),
        alias_declarations=(),
        coreference_observations=(),
    )

    selections = {
        expression: select_event_entity_mentions(
            source_text=source,
            event=_event(source, expression=expression),
            mention_preview=mention_preview,
            reference_preview=reference_preview,
            grounding_preview=_grounding_preview(mention_preview, reference_preview),
        )
        for expression in ("urged", "vote", "describing")
    }

    assert [(item.mention_text, item.reason) for item in selections["urged"].gaps] == [
        ("his", EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS)
    ]
    assert (
        selections["urged"].gap_dependencies[0].rule_id
        is EventEntityGapDependencyRule.ADJACENT_REFERENCE
    )
    assert selections["vote"].gaps == ()
    assert [(item.mention_text, item.reason) for item in selections["describing"].gaps] == [
        ("him", EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS)
    ]
    assert (
        selections["describing"].gap_dependencies[0].rule_id
        is EventEntityGapDependencyRule.ADJACENT_REFERENCE
    )


def test_ambiguous_possessive_blocks_only_its_dependent_event() -> None:
    source = (
        "Sacks viewed Amodei's decision over Trump's inauguration; "
        "his hiring of officials; and Anthropic would not support Trump's agenda."
    )
    pronoun = _upstream_candidate(source, "his", "1")
    mention_preview = _mention_preview((pronoun,), ())
    reference = ReferenceDecision.model_construct(
        id="rfd_" + "2" * 24,
        candidate_id=pronoun.id,
        status=ReferenceStatus.AMBIGUOUS,
        antecedent_span_ids=("rsp_" + "3" * 24, "rsp_" + "4" * 24),
    )
    reference_preview = HybridReferencePreview.model_construct(
        id="hrp_" + "5" * 24,
        parent_preview_id=mention_preview.id,
        reference_decisions=(reference,),
        semantic_antecedent_spans=(),
        alias_declarations=(),
        coreference_observations=(),
    )

    selections = {
        expression: select_event_entity_mentions(
            source_text=source,
            event=_event(source, expression=expression),
            mention_preview=mention_preview,
            reference_preview=reference_preview,
            grounding_preview=_grounding_preview(mention_preview, reference_preview),
        )
        for expression in ("viewed", "decision", "inauguration", "hiring", "support")
    }

    unrelated = ("viewed", "decision", "inauguration", "support")
    assert all(not selections[item].gaps for item in unrelated)
    hiring = selections["hiring"]
    assert len(hiring.gaps) == 1
    assert hiring.gaps[0].reason is EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS
    assert len(hiring.gap_dependencies) == 1
    assert hiring.gap_dependencies[0].rule_id is EventEntityGapDependencyRule.ADJACENT_POSSESSIVE


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
        denotation_decision_id="edd_" + candidate_id.removeprefix("mnc_"),
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


def _upstream_candidate(
    source: str,
    text: str,
    suffix: str,
    *,
    kind: ContextualKind = ContextualKind.PERSON,
) -> MentionCandidate:
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
        type_hints=(kind,),
    )


def _candidate_in_segment(
    source: str,
    text: str,
    source_segment_id: str,
    suffix: str,
) -> MentionCandidate:
    start = source.index(text)
    digest = hashlib.sha256(source.encode()).hexdigest()
    values = (source_segment_id, digest, str(start), str(start + len(text)), text)
    return MentionCandidate(
        id="mnc_" + hashlib.sha256(chr(31).join(values).encode()).hexdigest()[:24],
        source_segment_id=source_segment_id,
        source_text_sha256=digest,
        start=start,
        end=start + len(text),
        text=text,
        observation_ids=("mob_" + suffix * 24,),
        type_hints=(ContextualKind.ORGANIZATION,),
    )


def _coreference_span(source: str, start: int, text: str) -> CoreferenceSpan:
    assert source[start : start + len(text)] == text
    values = ("seg_fixture", str(start), str(start + len(text)), text)
    return CoreferenceSpan(
        id="cfs_" + hashlib.sha256("\0".join(values).encode()).hexdigest()[:24],
        source_segment_id="seg_fixture",
        start=start,
        end=start + len(text),
        text=text,
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
    observations: tuple[MentionObservation, ...] = (),
) -> HybridExtractionPreview:
    decisions = boundary_decisions or tuple(
        _boundary_decision(item, selected=True, suffix=str(index))
        for index, item in enumerate(candidates, start=1)
    )
    return HybridExtractionPreview.model_construct(
        id="hxp_" + "a" * 24,
        observations=observations,
        candidates=candidates,
        boundary_decisions=decisions,
        boundary_adjudications=(),
        interpretations=interpretations,
    )


def _grounding_preview(
    mention_preview: HybridExtractionPreview,
    reference_preview: HybridReferencePreview,
    *,
    link_evidence: tuple[EntityLinkEvidence, ...] = (),
) -> HybridEntityGroundingPreview:
    return HybridEntityGroundingPreview.model_construct(
        id="hgp_" + "f" * 24,
        parent_preview_id=reference_preview.id,
        mention_preview_id=mention_preview.id,
        link_evidence=link_evidence,
    )


def _observation(
    candidate: MentionCandidate,
    kind: ContextualKind,
    producer_id: str,
) -> MentionObservation:
    execution_record_id = "mrn_fixture"
    values = (
        candidate.source_segment_id,
        str(candidate.start),
        str(candidate.end),
        candidate.text,
        producer_id,
        execution_record_id,
        kind.value,
    )
    return MentionObservation(
        id="mob_" + hashlib.sha256(chr(31).join(values).encode()).hexdigest()[:24],
        source_segment_id=candidate.source_segment_id,
        start=candidate.start,
        end=candidate.end,
        text=candidate.text,
        type_hints=(kind,),
        producer_id=producer_id,
        execution_record_id=execution_record_id,
    )


def _candidate_routes(
    source_text: str,
    candidates: tuple[EventEntityConnectionCandidate, ...],
) -> tuple[EventEntityCandidateRoute, ...]:
    evidence = _candidate_routes_linguistic_evidence(source_text)
    return build_event_entity_candidate_routes(
        source_text=source_text,
        candidates=candidates,
        linguistic_evidence=evidence,
    )


def _candidate_routes_linguistic_evidence(
    source_text: str,
) -> EventEntityLinguisticEvidence:
    token_values = tuple(
        (match.start(), match.end(), match.group())
        for match in re.finditer(r"\w+|[^\w\s]", source_text)
    )
    sentence_ordinal = 1
    sentence_root_id: str | None = None
    tokens: list[EventEntityLinguisticToken] = []
    for ordinal, (start, end, text) in enumerate(token_values, start=1):
        token_id = f"t{ordinal}"
        if sentence_root_id is None:
            sentence_root_id = token_id
        tokens.append(
            EventEntityLinguisticToken(
                token_id=token_id,
                sentence_id=f"s{sentence_ordinal}",
                text=text,
                start=start,
                end=end,
                lemma=text.casefold(),
                part_of_speech="X",
                dependency_relation="root" if token_id == sentence_root_id else "dep",
                head_token_id=None if token_id == sentence_root_id else sentence_root_id,
            )
        )
        if text in {".", "!", "?"}:
            sentence_ordinal += 1
            sentence_root_id = None
    return EventEntityLinguisticEvidence(
        trace_id="xst_" + "9" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        producer_id="stanza:fixture",
        model_id="stanza-en",
        model_version="fixture",
        resource_identity="a" * 64,
        tokens=tuple(tokens),
    )
