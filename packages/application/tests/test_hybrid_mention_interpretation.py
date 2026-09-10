from __future__ import annotations

import hashlib
from itertools import product

import pytest
from kotekomi_application.context_planning import SourceSegment
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    BoundaryCandidateJudgmentValue,
    MentionBoundaryAdjudicationJudgment,
    MentionBoundaryCandidateStatus,
    boundary_candidate_judgment_schema_bytes,
    build_mention_boundary_adjudication,
    effective_mention_candidate_ids,
    parse_boundary_candidate_judgments,
    unresolved_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    ContextualKind,
    DiscourseRole,
    HybridPreviewStatus,
    MentionBoundaryDecision,
    MentionBoundaryStatus,
    MentionOccurrenceSelection,
    MentionOccurrenceSelectionBatch,
    Referentiality,
    build_hybrid_extraction_preview,
    canonical_hybrid_extraction_preview_bytes,
    fuse_mention_observations,
    hybrid_extraction_preview_from_bytes,
    hybrid_extraction_preview_sha256,
    map_occurrence_selections_to_observations,
    observation_from_proposal,
    parse_mention_interpretation_output,
    parse_mention_proposal_output,
    reconcile_mention_boundaries,
    resolve_mention_interpretation,
)
from kotekomi_application.mention_proposer import MentionProposal


def test_qwen_occurrence_selections_map_to_exact_source_ranges() -> None:
    segment = SourceSegment("s1", 0, 31, "Anthropic met Anthropic again.")
    parsed = parse_mention_proposal_output(b"mention: s1 | o1 | o1\nmention: s1 | o3 | o3\n")
    assert isinstance(parsed, MentionOccurrenceSelectionBatch)

    observations = map_occurrence_selections_to_observations(
        selections=parsed.selections,
        source_segments=(segment,),
        source_segment_ids={"s1": "seg_source"},
        producer_id="qwen2.5",
        execution_record_id="mrn_qwen",
    )

    assert [(item.start, item.end, item.text) for item in observations] == [
        (0, 9, "Anthropic"),
        (14, 23, "Anthropic"),
    ]
    assert all(item.type_hints == (ContextualKind.UNCLEAR,) for item in observations)


def test_malformed_proposal_line_does_not_erase_a_valid_line() -> None:
    parsed = parse_mention_proposal_output(
        b"mention: s1 | o1 | o2\nmention: s1 | s5 | s9\ncandidate: invented_internal_identifier\n"
    )

    assert isinstance(parsed, MentionOccurrenceSelectionBatch)
    assert parsed.selections == (MentionOccurrenceSelection("s1", "o1", "o2"),)
    assert [(item.line_number, item.code) for item in parsed.rejections] == [
        (2, "invalid_source_occurrence_id"),
        (3, "unknown_line"),
    ]


def test_interpretation_contract_separates_three_dimensions() -> None:
    draft = parse_mention_interpretation_output(
        b"candidate: c1\n"
        b"referentiality: specific_entity\n"
        b"contextual_kind: organization\n"
        b"discourse_role: origin\n"
        b"support: s2\n"
    )

    assert draft.referentiality is Referentiality.SPECIFIC_ENTITY
    assert draft.contextual_kind is ContextualKind.ORGANIZATION
    assert draft.discourse_role is DiscourseRole.ORIGIN


def test_boundary_judgment_parser_preserves_valid_siblings_and_rejects_bad_lines() -> None:
    parsed = parse_boundary_candidate_judgments(
        b"c1 | complete\ncandidate c2 | incomplete\nc2 | incomplete\nc3 | unclear\nc1 | unclear\n"
    )

    assert [(item.candidate_label, item.judgment) for item in parsed.judgments] == [
        ("c2", BoundaryCandidateJudgmentValue.INCOMPLETE),
        ("c3", BoundaryCandidateJudgmentValue.UNCLEAR),
    ]
    assert [(item.line_number, item.code) for item in parsed.rejections] == [
        (1, "duplicate_candidate_label"),
        (2, "invalid_candidate_label"),
        (5, "duplicate_candidate_label"),
    ]


def test_boundary_judgment_schema_requests_the_minimal_unambiguous_form() -> None:
    assert boundary_candidate_judgment_schema_bytes() == (
        b"Complete every prefix listed under required_output_prefixes.\n"
        b"Append exactly one status: complete, incomplete, or unclear.\n"
        b"Return exactly those completed lines and no other text.\n"
    )
    assert b"<supplied" not in boundary_candidate_judgment_schema_bytes()


def test_boundary_judgment_parser_rejects_superseded_and_placeholder_labels() -> None:
    parsed = parse_boundary_candidate_judgments(
        b"candidate: c1 | complete\n<supplied c2> | unclear\nc3 | incomplete\n"
    )

    assert [(item.candidate_label, item.judgment.value) for item in parsed.judgments] == [
        ("c3", "incomplete")
    ]
    assert [(item.line_number, item.code) for item in parsed.rejections] == [
        (1, "invalid_candidate_label"),
        (2, "invalid_candidate_label"),
    ]


def test_boundary_decision_status_and_selection_cannot_disagree() -> None:
    source = "Alpha Beta"
    segment_id = "seg_boundary_status"
    observation = observation_from_proposal(
        proposal=MentionProposal("s1", source, 0, len(source), ("organization",)),
        source_segment_id=segment_id,
        producer_id="fixture",
        execution_record_id="mrn_fixture",
    )
    candidate = fuse_mention_observations(
        source_segments={segment_id: source},
        observations=(observation,),
    )[0]
    decisions, _ = reconcile_mention_boundaries(
        source_segments={segment_id: source},
        observations=(observation,),
        candidates=(candidate,),
    )
    payload = decisions[0].model_dump(mode="python")
    payload["status"] = MentionBoundaryStatus.AMBIGUOUS

    with pytest.raises(ValueError, match="ambiguous.*cannot select"):
        MentionBoundaryDecision.model_validate(payload)


@pytest.mark.parametrize(
    ("source", "candidate_texts", "statuses", "expected_texts"),
    [
        (
            "Amodei wrote an op-ed.",
            ("Amodei", "Amodei wrote"),
            (MentionBoundaryCandidateStatus.COMPLETE, MentionBoundaryCandidateStatus.INCOMPLETE),
            ("Amodei",),
        ),
        (
            "The administration targeted law firms, Amodei responded.",
            ("administration targeted law firms, Amodei", "Amodei"),
            (MentionBoundaryCandidateStatus.INCOMPLETE, MentionBoundaryCandidateStatus.COMPLETE),
            ("Amodei",),
        ),
        (
            "Anthropic's technology achieved a result.",
            ("Anthropic", "Anthropic's technology achieved"),
            (MentionBoundaryCandidateStatus.COMPLETE, MentionBoundaryCandidateStatus.INCOMPLETE),
            ("Anthropic",),
        ),
        (
            "Anthropic's services remained available.",
            ("Anthropic", "Anthropic's services"),
            (MentionBoundaryCandidateStatus.COMPLETE, MentionBoundaryCandidateStatus.COMPLETE),
            ("Anthropic", "Anthropic's services"),
        ),
    ],
)
def test_semantic_boundary_adjudication_recovers_complete_nested_expressions(
    source: str,
    candidate_texts: tuple[str, ...],
    statuses: tuple[MentionBoundaryCandidateStatus, ...],
    expected_texts: tuple[str, ...],
) -> None:
    segment_id = "seg_boundary_fixture"
    observations = tuple(
        observation_from_proposal(
            proposal=MentionProposal(
                "s1",
                text,
                source.index(text),
                source.index(text) + len(text),
                ("organization",),
            ),
            source_segment_id=segment_id,
            producer_id=f"fixture_{index}",
            execution_record_id=f"mrn_{index}",
        )
        for index, text in enumerate(candidate_texts, start=1)
    )
    candidates = fuse_mention_observations(
        source_segments={segment_id: source},
        observations=observations,
    )
    decisions, selected = reconcile_mention_boundaries(
        source_segments={segment_id: source},
        observations=observations,
        candidates=candidates,
    )
    assert selected == ()
    status_by_text = dict(zip(candidate_texts, statuses, strict=True))
    adjudication = build_mention_boundary_adjudication(
        boundary_decision_id=decisions[0].id,
        source_segment_id=segment_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        judgments=tuple(
            MentionBoundaryAdjudicationJudgment(
                candidate_id=candidate.id,
                status=status_by_text[candidate.text],
            )
            for candidate in candidates
        ),
        extraction_task_id="ext_boundary",
        model_run_id="mrn_boundary",
        trace_id=f"xst_{'a' * 24}",
    )
    effective = set(effective_mention_candidate_ids(decisions, (adjudication,)))

    assert tuple(item.text for item in candidates if item.id in effective) == expected_texts
    assert unresolved_mention_candidate_ids(decisions, (adjudication,)) == ()


def test_every_valid_interpretation_label_combination_maps_to_source_identity() -> None:
    source = "Entity acted."
    segment_id = "seg_label_matrix"
    observation = observation_from_proposal(
        proposal=MentionProposal("s1", "Entity", 0, 6, ("organization",)),
        source_segment_id=segment_id,
        producer_id="fixture",
        execution_record_id="mrn_proposal",
    )
    candidate = fuse_mention_observations(
        source_segments={segment_id: source}, observations=(observation,)
    )[0]
    trace = build_extraction_stage_trace(
        trace_run_id="run_label_matrix",
        ordinal=0,
        stage_id="mention_interpretation",
        stage_version="v1",
        producer_id="qwen2.5",
        source_segment_id=segment_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        configuration={},
        input_payload={},
        output_payload={},
        status=ExtractionStageStatus.COMPLETED,
    )

    for referentiality, contextual_kind, discourse_role in product(
        Referentiality, ContextualKind, DiscourseRole
    ):
        draft = parse_mention_interpretation_output(
            (
                "candidate: c1\n"
                f"referentiality: {referentiality.value}\n"
                f"contextual_kind: {contextual_kind.value}\n"
                f"discourse_role: {discourse_role.value}\n"
                "support: s1\n"
            ).encode()
        )
        mapped = resolve_mention_interpretation(
            draft=draft,
            candidate_labels={"c1": candidate},
            source_segment_ids={"s1": segment_id},
            model_run_id="mrn_interpretation",
            trace_id=trace.id,
        )
        assert (
            mapped.referentiality,
            mapped.contextual_kind,
            mapped.discourse_role,
        ) == (referentiality, contextual_kind, discourse_role)


@pytest.mark.parametrize(
    "raw_output",
    [
        b"candidate: c1\nreferentiality: specific_entity\n",
        (
            b"candidate: c1\n"
            b"referentiality: specific_entity\n"
            b"contextual_kind: organization\n"
            b"discourse_role: origin\n"
            b"support: s1\n"
            b"explanation: extra\n"
        ),
        (
            b"candidate: c1\n"
            b"contextual_kind: organization\n"
            b"referentiality: specific_entity\n"
            b"discourse_role: origin\n"
            b"support: s1\n"
        ),
    ],
)
def test_interpretation_contract_rejects_missing_extra_or_reordered_fields(
    raw_output: bytes,
) -> None:
    with pytest.raises(ValueError):
        parse_mention_interpretation_output(raw_output)


def test_equal_observations_fuse_and_parenthetical_rule_remains_deterministic() -> None:
    source = "National Institute of Standards and Technology (NIST) acted."
    segment_id = "seg_parenthetical"
    observations = tuple(
        observation_from_proposal(
            proposal=MentionProposal(
                source_segment_label="s1",
                text=text,
                start=source.index(text),
                end=source.index(text) + len(text),
                type_hints=("organization",),
                score=score,
            ),
            source_segment_id=segment_id,
            producer_id=producer,
            execution_record_id=f"mrn_{producer}",
        )
        for producer, text, score in (
            (
                "qwen",
                "National Institute of Standards and Technology (NIST)",
                0.1,
            ),
            (
                "gliner",
                "National Institute of Standards and Technology (NIST)",
                0.9,
            ),
            ("qwen", "National Institute of Standards and Technology", 0.2),
            ("gliner", "NIST", 0.8),
        )
    )
    candidates = fuse_mention_observations(
        source_segments={segment_id: source},
        observations=observations,
    )
    decisions, selected = reconcile_mention_boundaries(
        source_segments={segment_id: source},
        observations=tuple(reversed(observations)),
        candidates=tuple(reversed(candidates)),
    )

    assert len(candidates) == 3
    assert decisions[0].status is MentionBoundaryStatus.RESOLVED
    assert decisions[0].rule_id == "exact_parenthetical_alias_v1"
    assert [item.text for item in selected] == [
        "National Institute of Standards and Technology (NIST)"
    ]


def test_unrecognized_nested_boundary_remains_ambiguous() -> None:
    source = "Alpha Beta Gamma"
    segment_id = "seg_ambiguous"
    observations = tuple(
        observation_from_proposal(
            proposal=MentionProposal(
                "s1",
                text,
                source.index(text),
                source.index(text) + len(text),
                ("organization",),
            ),
            source_segment_id=segment_id,
            producer_id=f"proposer_{index}",
            execution_record_id=f"mrn_{index}",
        )
        for index, text in enumerate(("Alpha Beta", "Beta Gamma", "Beta"), start=1)
    )
    candidates = fuse_mention_observations(
        source_segments={segment_id: source},
        observations=observations,
    )

    decisions, selected = reconcile_mention_boundaries(
        source_segments={segment_id: source},
        observations=observations,
        candidates=candidates,
    )

    assert decisions[0].status is MentionBoundaryStatus.AMBIGUOUS
    assert set(decisions[0].preserved_candidate_ids) == {item.id for item in candidates}
    assert selected == ()


def test_terminal_possessive_selects_only_the_base_source_boundary() -> None:
    source = "Anthropic's policy changed."
    segment_id = "seg_possessive"
    observations = tuple(
        observation_from_proposal(
            proposal=MentionProposal(
                "s1",
                text,
                0,
                len(text),
                ("organization",),
            ),
            source_segment_id=segment_id,
            producer_id=producer,
            execution_record_id=f"mrn_{producer}",
        )
        for producer, text in (("qwen", "Anthropic"), ("gliner", "Anthropic's"))
    )
    candidates = fuse_mention_observations(
        source_segments={segment_id: source}, observations=observations
    )

    decisions, selected = reconcile_mention_boundaries(
        source_segments={segment_id: source},
        observations=observations,
        candidates=candidates,
    )

    assert decisions[0].rule_id == "terminal_possessive_suffix_v1"
    assert [item.text for item in selected] == ["Anthropic"]


def test_preview_is_canonical_and_interpretation_maps_only_local_labels() -> None:
    source = "The European Union issued guidance."
    segment_id = "seg_eu"
    observations = map_occurrence_selections_to_observations(
        selections=(
            MentionOccurrenceSelection(
                "s1",
                "o2",
                "o3",
            ),
        ),
        source_segments=(SourceSegment("s1", 0, len(source), source),),
        source_segment_ids={"s1": segment_id},
        producer_id="qwen2.5",
        execution_record_id="mrn_proposal",
    )
    candidates = fuse_mention_observations(
        source_segments={segment_id: source},
        observations=observations,
    )
    decisions, selected = reconcile_mention_boundaries(
        source_segments={segment_id: source},
        observations=observations,
        candidates=candidates,
    )
    assert selected == candidates
    trace = build_extraction_stage_trace(
        trace_run_id="run_1",
        ordinal=0,
        stage_id="mention_interpretation",
        stage_version="v1",
        producer_id="qwen2.5",
        source_segment_id=segment_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        configuration={},
        input_payload={},
        output_payload={},
        status=ExtractionStageStatus.COMPLETED,
        execution_record_ids=("ext_1", "mrn_interpretation", "mrn_proposal"),
    )
    draft = parse_mention_interpretation_output(
        b"candidate: c1\n"
        b"referentiality: specific_entity\n"
        b"contextual_kind: organization\n"
        b"discourse_role: origin\n"
        b"support: s1\n"
    )
    interpretation = resolve_mention_interpretation(
        draft=draft,
        candidate_labels={"c1": candidates[0]},
        source_segment_ids={"s1": segment_id},
        model_run_id="mrn_interpretation",
        trace_id=trace.id,
    )
    preview = build_hybrid_extraction_preview(
        representation_id="rep_test",
        paragraph_node_id="nod_test",
        context_manifest_id="ctx_test",
        ontology_card_sha256="a" * 64,
        observations=observations,
        candidates=candidates,
        boundary_decisions=decisions,
        interpretations=(interpretation,),
        extraction_task_ids=("ext_1",),
        model_run_ids=("mrn_interpretation", "mrn_proposal"),
        traces=(trace,),
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    payload = canonical_hybrid_extraction_preview_bytes(preview)

    assert hybrid_extraction_preview_from_bytes(payload) == preview
    assert hybrid_extraction_preview_sha256(preview) == hashlib.sha256(payload).hexdigest()

    with pytest.raises(ValueError, match="unknown candidate"):
        resolve_mention_interpretation(
            draft=draft,
            candidate_labels={"c2": candidates[0]},
            source_segment_ids={"s1": segment_id},
            model_run_id="mrn_interpretation",
            trace_id=trace.id,
        )

    with pytest.raises(ValueError, match="unknown support"):
        resolve_mention_interpretation(
            draft=draft,
            candidate_labels={"c1": candidates[0]},
            source_segment_ids={"s2": segment_id},
            model_run_id="mrn_interpretation",
            trace_id=trace.id,
        )
