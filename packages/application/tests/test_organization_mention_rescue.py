from __future__ import annotations

from kotekomi_application import (
    MentionProposalObservation,
    fuse_monotonic_organization_candidates,
)


def _observation(
    proposer: str, text: str, start: int, *, score: float | None = None
) -> MentionProposalObservation:
    return MentionProposalObservation(proposer, text, start, start + len(text), score)


def test_monotonic_fusion_retains_baseline_and_adds_rescue_spans() -> None:
    source = "Anthropic partnered with Palantir."

    result = fuse_monotonic_organization_candidates(
        source_text=source,
        source_segment_id="segment-1",
        baseline_observations=(_observation("qwen", "Anthropic", 0),),
        rescue_observations=(
            _observation("gliner", "Anthropic", 0, score=0.9),
            _observation("gliner", "Palantir", 25, score=0.8),
        ),
    )

    actual = [
        (item.text, item.baseline, item.rescue, item.proposer_ids)
        for item in result.mention_candidates
    ]
    assert actual == [
        ("Anthropic", True, False, ("gliner", "qwen")),
        ("Palantir", False, True, ("gliner",)),
    ]
    assert result.mention_candidates[0].source_text_digest
    assert len(result.candidate_pairs) == 1
    assert result.candidate_pairs[0].requires_new_judgment is True


def test_monotonic_fusion_groups_explicit_parenthetical_aliases() -> None:
    source = "National Institute of Standards and Technology (NIST) worked with Anthropic and NIST."

    result = fuse_monotonic_organization_candidates(
        source_text=source,
        source_segment_id="segment-1",
        baseline_observations=(
            _observation("qwen", "Anthropic", 66),
            _observation("qwen", "NIST", 80),
        ),
        rescue_observations=(
            _observation(
                "gliner",
                "National Institute of Standards and Technology (NIST)",
                0,
                score=0.9,
            ),
        ),
    )

    nist = next(
        item for item in result.candidate_groups if item.preferred_text.startswith("National")
    )
    assert len(nist.mention_candidate_ids) == 2
    assert nist.baseline is True
    assert nist.rescue is True
    assert len(result.candidate_pairs) == 1
    assert result.candidate_pairs[0].requires_new_judgment is False


def test_monotonic_fusion_keeps_unequal_overlaps_visible() -> None:
    source = "U.S. Department of Commerce announced it."

    result = fuse_monotonic_organization_candidates(
        source_text=source,
        source_segment_id="segment-1",
        baseline_observations=(_observation("qwen", "U.S. Department of Commerce", 0),),
        rescue_observations=(_observation("gliner", "Department of Commerce", 5, score=0.8),),
    )

    assert len(result.mention_candidates) == 2
    assert len(result.candidate_groups) == 2
    assert result.candidate_pairs == ()
    assert len(result.pair_exclusions) == 1
    assert result.pair_exclusions[0].reason == "overlapping_source_spans"
