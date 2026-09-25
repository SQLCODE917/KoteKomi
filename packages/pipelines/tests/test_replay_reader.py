"""Deterministic unit coverage for the sacrificial replay reader.

These tests exercise the two pure seams that do not require persisted pipeline
state: span normalization back into paragraph-global offsets, and the
deterministic annotated-paragraph renderer. The CLI transport is only smoke
tested for argument parsing; a live replay against a real state root is left to
manual verification with ``kotekomi-replay --state-root ...``.
"""

from __future__ import annotations

import pytest
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    SourceSegment,
    hybrid_source_segment_id,
    paragraph_source_segments,
)
from kotekomi_pipelines.replay_reader.model import (
    EventAnnotation,
    GroundingAnnotation,
    MentionAnnotation,
    ParagraphAnnotationProfile,
    ProposalPlanAnnotation,
    ProposedChangeAnnotation,
    ReferenceAnnotation,
    Span,
    StandingFactAnnotation,
    TriggerAnnotation,
    build_segments,
    normalize_segment_span,
    normalize_text_view_span,
)
from kotekomi_pipelines.replay_reader.render import (
    render_annotated_paragraph,
    render_live_block,
)
from kotekomi_pipelines.replay_reader.transport import main


def test_build_segments_propagates_offsets_and_ids() -> None:
    text = "First sentence ends here. Second sentence follows."
    sources = paragraph_source_segments(text, PARAGRAPH_SEGMENT_V3)
    assert sources, "test text must segment into at least one SourceSegment"
    segments = build_segments(text, "rep_1", "node_1")
    assert [s.start for s in segments] == [s.start_char for s in sources]
    assert [s.end for s in segments] == [s.end_char for s in sources]
    assert [s.text for s in segments] == [s.exact_text for s in sources]
    for segment, source in zip(segments, sources, strict=True):
        assert segment.segment_id == hybrid_source_segment_id("rep_1", "node_1", source)


def test_normalize_segment_span_to_global() -> None:
    segment = SourceSegment(label="s2", start_char=12, end_char=30, exact_text="second sentence")
    span = normalize_segment_span(segment=segment, start=1, end=7)
    assert span == Span(start=13, end=19, text="econd ")


def test_normalize_text_view_span_to_global() -> None:
    span = normalize_text_view_span(start_char=44, end_char=47, text="foo", node_start_char=40)
    assert span == Span(start=4, end=7, text="foo")


def test_normalize_text_view_span_rejects_out_of_node() -> None:
    with pytest.raises(ValueError):
        normalize_text_view_span(start_char=39, end_char=42, text="x", node_start_char=40)


def test_render_annotated_paragraph_is_deterministic() -> None:
    text = "Acme Corp acquired Widget Co."
    profile = ParagraphAnnotationProfile(
        text=text,
        segments=(),
        mentions=(
            MentionAnnotation(
                span=Span(0, 9, "Acme Corp"),
                type_hints=("ORG", "PRODUCT"),
                selected=True,
                producers=3,
            ),
        ),
        references=(
            ReferenceAnnotation(
                source_span=Span(0, 9, "Acme Corp"),
                target_spans=(Span(20, 29, "Widget Co"),),
                kind="explicit_alias",
                status="resolved",
                reason="unique_explicit_alias",
            ),
        ),
        groundings=(
            GroundingAnnotation(
                span=Span(0, 9, "Acme Corp"),
                top_id="Q42",
                top_label="Acme Corporation",
                score=0.998,
            ),
        ),
        triggers=(
            TriggerAnnotation(
                trigger_id="etd_1",
                span=Span(10, 18, "acquired"),
                head_span=Span(10, 18, "acquired"),
                label="BUSINESS_ACQUISITION",
            ),
        ),
        events=(
            EventAnnotation(
                trigger_span=Span(10, 18, "acquired"),
                trigger_label="BUSINESS_ACQUISITION",
                head_text="Acme Corp",
                expression_text="acquired",
            ),
        ),
        standing_facts=(
            StandingFactAnnotation(
                subject_span=Span(0, 9, "Acme Corp"),
                relation_span=Span(10, 18, "acquired"),
                object_span=Span(20, 29, "Widget Co"),
                subject_label="Acme Corp",
                relation_label="acquired",
                object_selector="c1",
                disposition="proposed",
            ),
        ),
        present_stages=frozenset(
            {
                "hp1_mentions",
                "hp2_references",
                "hp3_grounding",
                "hp4_event_triggers",
                "hp6_event_semantics",
                "hp10_standing_facts",
            }
        ),
    )
    assert render_annotated_paragraph(profile) == (
        "stages: hp1_mentions hp2_references hp3_grounding hp4_event_triggers "
        "hp6_event_semantics hp10_standing_facts\n"
        "\n"
        "Acme Corp acquired Widget Co.\n"
        "\n"
        "Mentions (hp1_mentions):\n"
        '  - "Acme Corp" (0:9) type=ORG,PRODUCT producers=3 [selected]\n'
        "References (hp2_references):\n"
        '  - "Acme Corp" (0:9) -> "Widget Co" (20:29) explicit_alias/resolved/'
        "unique_explicit_alias\n"
        "Grounding (hp3_grounding):\n"
        '  - "Acme Corp" (0:9) -> Q42 Acme Corporation score=0.998\n'
        "Event triggers (hp4_event_triggers):\n"
        '  - "acquired" (10:18) event_type=BUSINESS_ACQUISITION head="acquired" (10:18)\n'
        "Events (hp6_event_semantics):\n"
        '  - head="Acme Corp" expression="acquired" trigger="acquired" '
        "(10:18) (BUSINESS_ACQUISITION)\n"
        "Standing facts (hp10_standing_facts):\n"
        '  - "Acme Corp" (0:9) --acquired-> "Widget Co" (20:29) [proposed]'
    )


def test_cli_help_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_render_proposal_plan_section() -> None:
    profile = ParagraphAnnotationProfile(
        text="Acme Corp acquired Widget Co.",
        segments=(),
        mentions=(),
        references=(),
        groundings=(),
        triggers=(),
        events=(),
        standing_facts=(),
        present_stages=frozenset({"hp7_proposal_plan"}),
        proposal_plan=(
            ProposalPlanAnnotation(
                event_id="sge_1",
                event_text="Acme Corp acquired Widget Co.",
                proposed_changes=(
                    ProposedChangeAnnotation(
                        change_id="pcg_1",
                        record_type="Organization",
                        record_id="org_1",
                        name="Widget Co",
                    ),
                    ProposedChangeAnnotation(
                        change_id="pcg_2",
                        record_type="Event",
                        record_id="evt_1",
                        name="Acme Corp acquired Widget Co.",
                    ),
                ),
            ),
        ),
    )
    assert render_annotated_paragraph(profile) == (
        "stages: hp7_proposal_plan\n"
        "\n"
        "Acme Corp acquired Widget Co.\n"
        "\n"
        "Proposal plan (hp7_proposal_plan):\n"
        '  - event "Acme Corp acquired Widget Co." (sge_1)\n'
        '      * Organization "Widget Co" (org_1)\n'
        '      * Event "Acme Corp acquired Widget Co." (evt_1)'
    )


def test_render_live_block_omits_pending_stages() -> None:
    profile = ParagraphAnnotationProfile(
        text="Acme Corp acquired Widget Co.",
        segments=(),
        mentions=(
            MentionAnnotation(
                span=Span(0, 9, "Acme Corp"),
                type_hints=("ORG",),
                selected=True,
                producers=1,
            ),
        ),
        references=(),
        groundings=(),
        triggers=(),
        events=(),
        standing_facts=(),
        present_stages=frozenset({"hp1_mentions", "hp7_proposal_plan"}),
        proposal_plan=(
            ProposalPlanAnnotation(event_id="evt_1", event_text="acquired", proposed_changes=()),
        ),
    )
    assert render_live_block(profile, completed_stages={"hp1_mentions"}) == (
        "stages: hp1_mentions\n"
        "\n"
        "Acme Corp acquired Widget Co.\n"
        "\n"
        "Mentions (hp1_mentions):\n"
        '  - "Acme Corp" (0:9) type=ORG producers=1 [selected]'
    )
