"""Source mapping and shared source-attached rendering regressions."""

from __future__ import annotations

from dataclasses import replace

import pytest
from kotekomi_adapters.extraction_view.render import (
    annotated_rows,
    profile_annotations,
    render_annotated_paragraph,
    render_live_block,
    source_lines,
)
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V2,
    SourceSegment,
    build_hybrid_reference_preview,
    hybrid_extraction_preview_sha256,
    hybrid_source_segment_id,
    paragraph_source_segments,
)
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
    build_profile,
    build_segments,
    normalize_segment_span,
    normalize_text_view_span,
)
from kotekomi_pipelines.replay_reader.transport import main

# Reuse coherent validated boundary fixtures; visibility is intentionally test-only.
from packages.application.tests.test_hybrid_document_references import (
    _bundle,  # pyright: ignore[reportPrivateUsage]
    _parent_preview,  # pyright: ignore[reportPrivateUsage]
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


def test_build_segments_propagates_offsets_and_ids() -> None:
    text = "First sentence ends here. Second sentence follows."
    sources = paragraph_source_segments(text, PARAGRAPH_SEGMENT_V2)
    segments = build_segments(text, "rep_1", "node_1")
    assert [s.start for s in segments] == [s.start_char for s in sources]
    assert [s.end for s in segments] == [s.end_char for s in sources]
    assert [s.text for s in segments] == [s.exact_text for s in sources]
    for segment, source in zip(segments, sources, strict=True):
        assert segment.segment_id == hybrid_source_segment_id("rep_1", "node_1", source)


def test_normalize_segment_span_to_global() -> None:
    segment = SourceSegment(label="s2", start_char=12, end_char=27, exact_text="second sentence")
    assert normalize_segment_span(segment=segment, start=1, end=7) == Span(13, 19, "econd ")


def test_normalize_text_view_span_to_global() -> None:
    assert normalize_text_view_span(
        start_char=44, end_char=47, text="foo", node_start_char=40
    ) == Span(4, 7, "foo")


def test_normalize_text_view_span_rejects_out_of_node() -> None:
    with pytest.raises(ValueError, match="reference span falls outside its paragraph node"):
        normalize_text_view_span(start_char=39, end_char=42, text="x", node_start_char=40)


def test_plain_render_is_source_attached_and_deterministic() -> None:
    profile = example_profile()
    block = render_annotated_paragraph(profile)
    assert block == render_annotated_paragraph(profile)
    assert "\033" not in block
    lines = block.splitlines()
    assert lines[2] == profile.text
    assert lines[3].startswith("└─ Mention · organization")
    assert lines[4].startswith("└─ Reference")
    assert lines[5].startswith("└─ Grounding")
    assert "          └─ Proposal · Organization, Event" in lines
    assert 'Organization: "Widget Co"' in block
    assert "awaiting review" in block


def test_overlapping_layers_are_independent() -> None:
    profile = example_profile()
    rows = annotated_rows(profile, profile.present_stages, 100)
    keys = [row.annotation_key for row in rows if row.annotation_key is not None]
    assert len(keys) == len(set(keys)) == 7
    assert keys[:3] == ["hp1_mentions:0", "hp2_references:0", "hp3_grounding:0"]
    block = render_live_block(profile, {"hp1_mentions"})
    assert "Mention · organization" in block
    assert "Grounding" not in block
    assert "Proposal" not in block


def test_repeated_expression_proposals_use_recorded_offsets() -> None:
    profile = example_profile()
    text = "acquired then acquired"
    proposals = tuple(
        replace(
            profile.proposal_plan[0],
            event_id=f"event_{start}",
            trigger_span=Span(start, start + 8, "acquired"),
        )
        for start in (0, 14)
    )
    profile = replace(
        profile,
        text=text,
        mentions=(),
        references=(),
        groundings=(),
        triggers=(),
        events=(),
        standing_facts=(),
        proposal_plan=proposals,
        present_stages=frozenset({"hp7_proposal_plan"}),
    )
    items = profile_annotations(profile)
    assert [item.span.start for item in items] == [0, 14]
    rows = annotated_rows(profile, profile.present_stages, 80)
    assert rows[1].text.plain.startswith("└─ Proposal")
    assert rows[2].text.plain.startswith("              └─ Proposal")


@pytest.mark.parametrize("width", [2, 8, 20, 80])
def test_source_wrap_preserves_newlines_tabs_and_unicode_coordinates(width: int) -> None:
    text = "界e\u0301\tOrganization\n\nsecond 👩\u200d💻 line"
    lines = source_lines(text, width)
    assert any(line.start == line.end for line in lines)
    assert all("\n" not in line.text and "\t" not in line.text for line in lines)
    assert all(line.columns[-1] <= width for line in lines)
    for line in lines:
        assert len(line.columns) == len(line.display_offsets) == line.end - line.start + 1
        assert line.display_offsets[-1] == len(line.text)
    covered = {index for line in lines for index in range(line.start, line.end)}
    assert covered == {index for index, char in enumerate(text) if char != "\n"}
    assert lines[0].columns[:2] == (0, 2)
    if width >= 3:
        assert lines[0].columns[:3] == (0, 2, 2)


@pytest.mark.parametrize(
    "paragraphs,focus,expected_targets",
    [
        (("National Institute of Standards and Technology (NIST) acted. NIST replied.",), 0, 1),
        (("National Institute of Standards and Technology (NIST) acted.", "NIST replied."), 1, 1),
        (
            (
                "National Institute of Standards and Technology (NIST) acted.",
                "Northern Institute of Science and Technology (NIST) acted.",
                "NIST replied.",
            ),
            2,
            2,
        ),
    ],
)
def test_valid_alias_targets_retain_source_identity(
    paragraphs: tuple[str, ...], focus: int, expected_targets: int
) -> None:
    bundle = _bundle(paragraphs)
    parent = _parent_preview(bundle, paragraph_index=focus, candidate_texts=("NIST",))
    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )
    node = next(item for item in bundle.nodes if item.id == parent.paragraph_node_id)
    profile = build_profile(
        text=paragraphs[focus],
        representation_id=bundle.representation.id,
        paragraph_node_id=node.id,
        node_start_char=node.start_char,
        stage_outputs={"hp2_references": preview},
        bundle=bundle,
    )
    reference = profile.references[0]
    assert profile.representation_id == bundle.representation.id
    assert profile.paragraph_node_id == node.id
    assert profile.node_start_char == node.start_char
    assert profile.text_view_id == node.text_view_id
    assert len(reference.targets) == expected_targets
    assert reference.status == ("ambiguous" if expected_targets == 2 else "resolved")
    for target in reference.targets:
        assert target.text_view_id == bundle.text_views[0].id
        assert bundle.text_views[0].text[target.start_char : target.end_char] == target.text
        assert (target.local_span is not None) == (focus == 0)
    assert "Reference · explicit_alias" in render_annotated_paragraph(profile)


def test_negative_alias_with_missing_target_fails_explicitly() -> None:
    bundle = _bundle(("National Institute of Standards and Technology (NIST) acted.",))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("NIST",))
    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
    )
    # Deliberately malformed deterministic fixture: a dangling target must fail.
    invalid = preview.model_copy(update={"alias_declarations": ()})
    node = next(item for item in bundle.nodes if item.id == parent.paragraph_node_id)
    with pytest.raises(ValueError, match="^reference target is missing\\.$"):
        build_profile(
            text=bundle.text_views[0].text[node.start_char : node.end_char],
            representation_id=bundle.representation.id,
            paragraph_node_id=node.id,
            node_start_char=node.start_char,
            stage_outputs={"hp2_references": invalid},
            bundle=bundle,
        )


def test_negative_annotation_source_text_mismatch_fails_explicitly() -> None:
    profile = example_profile()
    profile = replace(
        profile, mentions=(replace(profile.mentions[0], span=Span(0, 9, "WRONGTEXT")),)
    )
    with pytest.raises(ValueError, match="^annotation span text does not match the paragraph\\.$"):
        profile_annotations(profile)


def test_cli_help_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_semantic_antecedent_keeps_its_exact_local_span() -> None:
    from packages.application.tests.test_hybrid_document_references import (
        _Challenger,  # pyright: ignore[reportPrivateUsage]
        _CoreferenceProposer,  # pyright: ignore[reportPrivateUsage]
        _Tokenizer,  # pyright: ignore[reportPrivateUsage]
    )

    text = "Trump spoke before Amodei criticized him."
    bundle = _bundle((text,))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Trump", "him"))
    target = text.index("him")
    preview = build_hybrid_reference_preview(
        parent_preview=parent,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        bundle=bundle,
        coreference_proposer=_CoreferenceProposer((((0, 5), (target, target + 3)),)),
        coreference_tokenizer=_Tokenizer(),
        semantic_reference_challenger=_Challenger(),
    )
    node = next(item for item in bundle.nodes if item.id == parent.paragraph_node_id)
    profile = build_profile(
        text=text,
        representation_id=bundle.representation.id,
        paragraph_node_id=node.id,
        node_start_char=node.start_char,
        stage_outputs={"hp2_references": preview},
        bundle=bundle,
    )
    reference = profile.references[0]
    assert reference.source_span == Span(target, target + 3, "him")
    assert reference.targets[0].local_span == Span(0, 5, "Trump")
    assert profile_annotations(profile)[0].related_spans == (Span(0, 5, "Trump"),)


def test_real_source_grounded_proposal_plan_binds_to_recorded_trigger() -> None:
    from kotekomi_application import build_hybrid_proposal_plan

    from packages.application.tests.test_hybrid_event_semantics_preview import (
        _run_semantics,  # pyright: ignore[reportPrivateUsage]
        _run_to_triggers,  # pyright: ignore[reportPrivateUsage]
        _Runtime,  # pyright: ignore[reportPrivateUsage]
    )

    text = "Events\n1789 Capital abandoned an investment in Anthropic."
    mentions = (("1789 Capital", "organization"), ("Anthropic", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | investment_abandonment\n",
        semantic_output=(
            b"frame: investment_abandonment\npolarity: affirmed\nmodality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: investment_abandonment.disinvestor | c1\n"
            b"argument: investment_abandonment.abandoned_asset | o4-o7\n"
            b"argument: investment_abandonment.investee | c2\n"
            b"reason: The source explicitly states the abandoned investment.\n"
        ),
    )
    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)
    plan = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)
    node = next(item for item in ledger.bundle.nodes if item.id == plan.paragraph_node_id)
    paragraph = ledger.bundle.text_views[0].text[node.start_char : node.end_char]
    profile = build_profile(
        text=paragraph,
        representation_id=ledger.bundle.representation.id,
        paragraph_node_id=node.id,
        node_start_char=node.start_char,
        stage_outputs={
            "hp4_event_triggers": hp4.preview,
            "hp6_event_semantics": hp6.preview,
            "hp7_proposal_plan": plan,
        },
        bundle=ledger.bundle,
    )
    assert profile.proposal_plan
    proposal = profile.proposal_plan[0]
    assert proposal.trigger_span == profile.triggers[0].span
    assert {item.record_type for item in proposal.proposed_changes} == {"Event", "Organization"}
    assert {item.name for item in proposal.proposed_changes} >= {"1789 Capital", "Anthropic"}
    assert any(item.stage == "hp7_proposal_plan" for item in profile_annotations(profile))


def test_partial_grapheme_annotation_paints_glyph_without_changing_source_coordinates() -> None:
    profile = example_profile()
    profile = replace(
        profile,
        text="e\u0301",
        mentions=(MentionAnnotation(Span(0, 1, "e"), ("symbol",), True, 1),),
        references=(),
        groundings=(),
        triggers=(),
        events=(),
        proposal_plan=(),
        standing_facts=(),
        present_stages=frozenset({"hp1_mentions"}),
    )
    rows = annotated_rows(profile, profile.present_stages, 20, "hp1_mentions:0")
    assert rows[0].text.plain == "e\u0301"
    assert any(
        span.style == "bold reverse" and span.start == 0 and span.end == 2
        for span in rows[0].text.spans
    )
    assert profile_annotations(profile)[0].span == Span(0, 1, "e")


def test_negative_stage_with_missing_output_is_rejected() -> None:
    with pytest.raises(
        ValueError, match="^hp1_mentions output is not a HybridExtractionPreview\\.$"
    ):
        build_profile(
            text="Acme acted.",
            representation_id="rep_1",
            paragraph_node_id="node_1",
            node_start_char=0,
            stage_outputs={"hp1_mentions": None},
        )


def test_negative_stage_from_another_representation_is_rejected() -> None:
    bundle = _bundle(("Acme acted.",))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Acme",))
    invalid = parent.model_copy(update={"representation_id": "another_representation"})
    with pytest.raises(ValueError, match="^stage output belongs to another representation\\.$"):
        build_profile(
            text="Acme acted.",
            representation_id=bundle.representation.id,
            paragraph_node_id=parent.paragraph_node_id,
            node_start_char=0,
            stage_outputs={"hp1_mentions": invalid},
            bundle=bundle,
        )
