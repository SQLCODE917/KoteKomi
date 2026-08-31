from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest
from kotekomi_application import (
    MentionBoundaryDecisionStatus,
    MentionBoundaryRelation,
    MentionProposalObservation,
    canonical_boundary_reconciliation_json,
    fuse_mention_proposals,
    mention_boundary_relation,
    reconcile_organization_mention_boundaries,
)


@pytest.mark.parametrize(
    ("first", "second", "relation", "inverse"),
    [
        ((1, 4), (1, 4), MentionBoundaryRelation.EQUAL, MentionBoundaryRelation.EQUAL),
        ((1, 8), (2, 4), MentionBoundaryRelation.CONTAINS, MentionBoundaryRelation.CONTAINED_BY),
        ((2, 4), (1, 8), MentionBoundaryRelation.CONTAINED_BY, MentionBoundaryRelation.CONTAINS),
        ((1, 5), (3, 8), MentionBoundaryRelation.CROSSING, MentionBoundaryRelation.CROSSING),
        ((1, 3), (3, 8), MentionBoundaryRelation.ADJACENT, MentionBoundaryRelation.ADJACENT),
        ((1, 3), (4, 8), MentionBoundaryRelation.DISJOINT, MentionBoundaryRelation.DISJOINT),
    ],
)
def test_half_open_interval_relations_are_total_and_have_documented_inverses(
    first: tuple[int, int],
    second: tuple[int, int],
    relation: MentionBoundaryRelation,
    inverse: MentionBoundaryRelation,
) -> None:
    assert mention_boundary_relation(*first, *second) == relation
    assert mention_boundary_relation(*second, *first) == inverse


def test_invalid_interval_fails() -> None:
    with pytest.raises(ValueError, match="half-open"):
        mention_boundary_relation(2, 2, 3, 4)


def test_equal_proposals_merge_provenance_before_uncontested_reconciliation() -> None:
    source = "Anthropic replied."
    observations = (
        _observation("qwen", source, "Anthropic", score=0.1, run="run_qwen"),
        _observation("gliner", source, "Anthropic", score=0.9, run="run_gliner"),
    )
    candidates = fuse_mention_proposals(source, "seg_1", observations)

    result = reconcile_organization_mention_boundaries(
        source_text=source,
        source_segment_id="seg_1",
        candidates=candidates,
    )

    assert len(candidates) == 1
    assert [item.proposer_id for item in candidates[0].observations] == ["gliner", "qwen"]
    assert result.decisions[0].status == MentionBoundaryDecisionStatus.UNCONTESTED
    assert result.reconciled_candidates[0].proposer_ids == ("gliner", "qwen")


def test_exact_parenthetical_alias_selects_complete_expression_and_preserves_alias() -> None:
    source = "The National Institute of Standards and Technology (NIST) published it."
    observations = tuple(
        _observation("test", source, text)
        for text in (
            "National Institute of Standards and Technology (NIST)",
            "National Institute of Standards and Technology",
            "NIST",
        )
    )
    candidates = fuse_mention_proposals(source, "seg_parenthetical", observations)

    result = reconcile_organization_mention_boundaries(
        source_text=source,
        source_segment_id="seg_parenthetical",
        candidates=tuple(reversed(candidates)),
    )

    decision = result.decisions[0]
    assert decision.status == MentionBoundaryDecisionStatus.RESOLVED
    assert decision.rule_id == "exact_parenthetical_alias_v1"
    assert [item.text for item in result.reconciled_candidates] == [
        "National Institute of Standards and Technology (NIST)"
    ]
    alias_ids = {candidate.id for candidate in candidates if candidate.text == "NIST"}
    assert set(decision.alias_evidence_candidate_ids) == alias_ids
    assert set(decision.preserved_candidate_ids) == {candidate.id for candidate in candidates}


@pytest.mark.parametrize("suffix", ["'s", "’s"])
def test_terminal_possessive_selects_only_nonpossessive_boundary(suffix: str) -> None:
    source = f"Anthropic{suffix} policy changed."
    candidates = fuse_mention_proposals(
        source,
        "seg_possessive",
        (
            _observation("qwen", source, "Anthropic"),
            _observation("gliner", source, f"Anthropic{suffix}"),
        ),
    )

    result = reconcile_organization_mention_boundaries(
        source_text=source,
        source_segment_id="seg_possessive",
        candidates=candidates,
    )

    assert result.decisions[0].rule_id == "terminal_possessive_suffix_v1"
    assert [item.text for item in result.reconciled_candidates] == ["Anthropic"]


def test_parenthetical_rule_does_not_repair_an_unrecognized_nested_boundary() -> None:
    source = "National Institute of Standards and Technology (NIST) published it."
    candidates = fuse_mention_proposals(
        source,
        "seg_parenthetical_ambiguous",
        (
            _observation(
                "qwen",
                source,
                "National Institute of Standards and Technology (NIST)",
            ),
            _observation("gliner", source, "Institute of Standards"),
        ),
    )

    result = reconcile_organization_mention_boundaries(
        source_text=source,
        source_segment_id="seg_parenthetical_ambiguous",
        candidates=candidates,
    )

    assert result.decisions[0].status == MentionBoundaryDecisionStatus.AMBIGUOUS
    assert result.reconciled_candidates == ()


def test_adjacent_and_disjoint_candidates_remain_separate_and_uncontested() -> None:
    source = "ABCDEF met GHI."
    candidates = fuse_mention_proposals(
        source,
        "seg_separate",
        (
            _observation("qwen", source, "ABC"),
            _observation("gliner", source, "DEF"),
            _observation("qwen", source, "GHI"),
        ),
    )

    result = reconcile_organization_mention_boundaries(
        source_text=source,
        source_segment_id="seg_separate",
        candidates=candidates,
    )

    assert [item.relation for item in result.relations] == [
        MentionBoundaryRelation.ADJACENT,
        MentionBoundaryRelation.DISJOINT,
        MentionBoundaryRelation.DISJOINT,
    ]
    assert all(
        decision.status == MentionBoundaryDecisionStatus.UNCONTESTED
        for decision in result.decisions
    )
    assert [item.text for item in result.reconciled_candidates] == ["ABC", "DEF", "GHI"]


def test_nested_and_crossing_conflicts_remain_ambiguous_without_candidate_loss() -> None:
    source = "Alpha Beta Gamma"
    candidates = fuse_mention_proposals(
        source,
        "seg_ambiguous",
        (
            _observation("one", source, "Alpha Beta"),
            _observation("two", source, "Beta Gamma"),
            _observation("three", source, "Beta"),
        ),
    )

    result = reconcile_organization_mention_boundaries(
        source_text=source,
        source_segment_id="seg_ambiguous",
        candidates=candidates,
    )

    decision = result.decisions[0]
    assert decision.status == MentionBoundaryDecisionStatus.AMBIGUOUS
    assert decision.selected_candidate_ids == ()
    assert set(decision.preserved_candidate_ids) == {candidate.id for candidate in candidates}
    assert result.reconciled_candidates == ()


def test_decisions_ignore_order_scores_and_model_run_identity() -> None:
    source = "Anthropic's policy."
    first_candidates = fuse_mention_proposals(
        source,
        "seg_stable",
        (
            _observation("qwen", source, "Anthropic", score=0.1, run="one"),
            _observation("gliner", source, "Anthropic's", score=0.9, run="two"),
        ),
    )
    changed = tuple(
        replace(
            candidate,
            observations=tuple(
                replace(
                    observation,
                    proposer_id=f"changed-{observation.proposer_id}",
                    score=0.5,
                    model_run_id="changed",
                )
                for observation in reversed(candidate.observations)
            ),
        )
        for candidate in reversed(first_candidates)
    )

    first = reconcile_organization_mention_boundaries(
        source_text=source, source_segment_id="seg_stable", candidates=first_candidates
    )
    second = reconcile_organization_mention_boundaries(
        source_text=source, source_segment_id="seg_stable", candidates=changed
    )

    assert first.decisions == second.decisions
    assert [item.text for item in first.reconciled_candidates] == [
        item.text for item in second.reconciled_candidates
    ]
    assert canonical_boundary_reconciliation_json(first) == canonical_boundary_reconciliation_json(
        reconcile_organization_mention_boundaries(
            source_text=source,
            source_segment_id="seg_stable",
            candidates=tuple(reversed(first_candidates)),
        )
    )


def test_source_drift_duplicate_ids_and_unfused_equal_spans_fail() -> None:
    source = "Anthropic replied."
    candidate = fuse_mention_proposals(
        source,
        "seg_invalid",
        (_observation("qwen", source, "Anthropic"),),
    )[0]
    drifted = replace(candidate, source_text_digest=hashlib.sha256(b"other").hexdigest())
    with pytest.raises(ValueError, match="digest drifted"):
        reconcile_organization_mention_boundaries(
            source_text=source, source_segment_id="seg_invalid", candidates=(drifted,)
        )
    with pytest.raises(ValueError, match="repeats a candidate identity"):
        reconcile_organization_mention_boundaries(
            source_text=source, source_segment_id="seg_invalid", candidates=(candidate, candidate)
        )
    duplicate_span = replace(candidate, id="mnc_duplicate")
    with pytest.raises(ValueError, match="must be fused"):
        reconcile_organization_mention_boundaries(
            source_text=source,
            source_segment_id="seg_invalid",
            candidates=(candidate, duplicate_span),
        )


def _observation(
    proposer: str,
    source: str,
    text: str,
    *,
    score: float | None = None,
    run: str | None = None,
) -> MentionProposalObservation:
    start = source.index(text)
    return MentionProposalObservation(proposer, text, start, start + len(text), score, run)
