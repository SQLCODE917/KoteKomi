"""Shared replay fixtures for tests that need one annotated paragraph."""

from __future__ import annotations

from kotekomi_application.ingestion_inspection import (
    EventAnnotation,
    GroundingAnnotation,
    InspectionRecord,
    MentionAnnotation,
    ParagraphAnnotationProfile,
    ProposalPlanAnnotation,
    ProposedChangeAnnotation,
    ReferenceAnnotation,
    ReferenceTargetAnnotation,
    Span,
    StandingFactAnnotation,
    TriggerAnnotation,
)


def example_profile() -> ParagraphAnnotationProfile:
    text = "Acme Corp acquired Widget Co."
    mention = Span(0, 9, "Acme Corp")
    trigger = Span(10, 18, "acquired")
    target = Span(19, 28, "Widget Co")
    return ParagraphAnnotationProfile(
        text=text,
        representation_id="rep_1",
        paragraph_node_id="node_1",
        node_start_char=0,
        text_view_id="view_1",
        segments=(),
        records=(
            InspectionRecord(
                "hp1_mentions:0",
                "hp1_mentions",
                "mnc_fixture",
                "MentionCandidate",
                (mention,),
                {"effective_selected": True},
            ),
            InspectionRecord(
                "hp2_references:0",
                "hp2_references",
                "ref_fixture",
                "ReferenceDecision",
                (mention,),
                {"target_node_id": "node_1"},
                ("alias_fixture",),
                ("trace_fixture",),
            ),
            InspectionRecord(
                "hp3_grounding:0",
                "hp3_grounding",
                "ele_fixture",
                "EntityLinkEvidence",
                (mention,),
                {"identity": "Q42"},
            ),
        ),
        mentions=(MentionAnnotation(mention, ("organization",), True, 3),),
        references=(
            ReferenceAnnotation(
                mention,
                (
                    ReferenceTargetAnnotation(
                        "node_1", "view_1", target.start, target.end, target.text, target
                    ),
                ),
                "explicit_alias",
                "resolved",
                "unique_explicit_alias",
            ),
        ),
        groundings=(GroundingAnnotation(mention, "Q42", "Acme Corporation", 0.998),),
        triggers=(TriggerAnnotation("trigger_1", trigger, trigger, "BUSINESS_ACQUISITION"),),
        events=(
            EventAnnotation("event_1", trigger, "BUSINESS_ACQUISITION", "acquired", "acquired"),
        ),
        standing_facts=(
            StandingFactAnnotation(
                mention, trigger, target, "Acme Corp", "acquired", "Widget Co", "proposed"
            ),
        ),
        present_stages=frozenset(
            {
                "hp1_mentions",
                "hp2_references",
                "hp3_grounding",
                "hp4_event_triggers",
                "hp6_event_semantics",
                "hp7_proposal_plan",
                "hp10_standing_facts",
            }
        ),
        proposal_plan=(
            ProposalPlanAnnotation(
                "event_1",
                "acquired",
                trigger,
                (
                    ProposedChangeAnnotation("change_1", "Organization", "org_1", "Widget Co"),
                    ProposedChangeAnnotation("change_2", "Event", "event_1", "acquired"),
                ),
            ),
        ),
    )
