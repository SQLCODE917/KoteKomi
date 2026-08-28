from __future__ import annotations

import pytest
from kotekomi_application.organization_mention_qualification import (
    AliasDecisionStatus,
    MentionProposalObservation,
    QualificationStatus,
    combine_validated_organization_mentions,
    derive_qualified_organization_pairs,
    fuse_mention_proposals,
    resolve_document_organization_identities,
    resolve_organization_qualification,
)


def _observation(
    proposer: str,
    text: str,
    start: int,
    end: int,
    score: float | None = None,
) -> MentionProposalObservation:
    return MentionProposalObservation(proposer, text, start, end, score)


def _validated(
    source: str,
    segment: str,
    candidate_text: str,
    returned_text: str,
    representation: str = "rep_test",
):
    start = source.index(candidate_text)
    candidates = fuse_mention_proposals(
        source,
        segment,
        (_observation("qwen", candidate_text, start, start + len(candidate_text)),),
    )
    result = resolve_organization_qualification(
        representation_id=representation,
        source_text=source,
        candidate=candidates[0],
        returned_text=returned_text,
        rejected=False,
        model_run_id="mrn_test",
    )
    assert result.mention is not None
    return result.mention


def test_fusion_combines_equal_spans_and_preserves_unequal_overlaps() -> None:
    source = "National Institute of Standards and Technology (NIST)"
    candidates = fuse_mention_proposals(
        source,
        "segment-1",
        (
            _observation("qwen", source, 0, len(source)),
            _observation("gliner", source, 0, len(source), 0.91),
            _observation("gliner", "Standards and Technology", 22, 46, 0.61),
        ),
    )

    assert len(candidates) == 2
    assert [item.proposer_id for item in candidates[0].observations] == ["gliner", "qwen"]
    assert candidates[1].text == "Standards and Technology"


def test_fusion_rejects_source_character_mismatch() -> None:
    with pytest.raises(ValueError, match="source characters"):
        fuse_mention_proposals(
            "Anthropic",
            "segment-1",
            (_observation("gliner", "Anthrop1c", 0, 9, 0.5),),
        )


def test_qualification_resolves_partial_candidate_to_complete_literal_expression() -> None:
    source = "The National Institute of Standards and Technology (NIST) published guidance."
    mention = _validated(
        source,
        "segment-1",
        "Institute of Standards and Technology",
        "National Institute of Standards and Technology (NIST)",
    )

    assert source[mention.start : mention.end] == mention.text
    assert mention.text == "National Institute of Standards and Technology (NIST)"


def test_qualification_rejects_expression_that_does_not_bind_candidate() -> None:
    source = "Anthropic consulted the National Institute of Standards and Technology."
    candidate = fuse_mention_proposals(
        source,
        "segment-1",
        (_observation("gliner", "Anthropic", 0, 9, 0.7),),
    )[0]

    result = resolve_organization_qualification(
        representation_id="rep_test",
        source_text=source,
        candidate=candidate,
        returned_text="National Institute of Standards and Technology",
        rejected=False,
        model_run_id="mrn_test",
    )

    assert result.status is QualificationStatus.INVALID
    assert result.diagnostics == ("organization_expression_not_candidate_bound",)
    assert result.mention is None


def test_rejected_candidate_never_creates_a_validated_mention() -> None:
    candidate = fuse_mention_proposals(
        "United States",
        "segment-1",
        (_observation("gliner", "United States", 0, 13, 0.8),),
    )[0]

    result = resolve_organization_qualification(
        representation_id="rep_test",
        source_text="United States",
        candidate=candidate,
        returned_text=None,
        rejected=True,
        model_run_id="mrn_test",
    )

    assert result.status is QualificationStatus.REJECTED
    assert result.mention is None


def test_equal_final_spans_combine_proposer_and_model_provenance() -> None:
    source = "National Institute of Standards and Technology (NIST)"
    candidates = fuse_mention_proposals(
        source,
        "segment-1",
        (
            _observation("qwen", source, 0, len(source)),
            _observation("gliner", "Standards and Technology", 22, 46, 0.7),
        ),
    )
    mentions = tuple(
        result.mention
        for index, candidate in enumerate(candidates, start=1)
        if (
            result := resolve_organization_qualification(
                representation_id="rep_test",
                source_text=source,
                candidate=candidate,
                returned_text=source,
                rejected=False,
                model_run_id=f"mrn_{index}",
            )
        ).mention
        is not None
    )

    combined = combine_validated_organization_mentions(mentions)

    assert len(combined) == 1
    assert combined[0].proposer_ids == ("gliner", "qwen")
    assert combined[0].qualification_model_run_ids == ("mrn_1", "mrn_2")


def test_document_alias_resolution_groups_nist_with_its_expanded_name() -> None:
    declaration = "U.S. National Institute of Standards and Technology (NIST)"
    first = _validated(declaration, "segment-1", declaration, declaration)
    second = _validated("NIST published guidance.", "segment-2", "NIST", "NIST")

    result = resolve_document_organization_identities("rep_test", (first, second))

    assert len(result.identities) == 1
    assert result.identities[0].preferred_name == (
        "U.S. National Institute of Standards and Technology"
    )
    assert result.identities[0].alias_names == ("NIST",)
    assert result.alias_decisions[0].status is AliasDecisionStatus.RESOLVED


def test_conflicting_alias_declarations_remain_separate_and_auditable() -> None:
    first_text = "National Institute of Standards and Technology (NIST)"
    second_text = "Network Institute for Systems Testing (NIST)"
    first = _validated(first_text, "segment-1", first_text, first_text)
    second = _validated(second_text, "segment-2", second_text, second_text)
    alias = _validated("NIST issued guidance.", "segment-3", "NIST", "NIST")

    result = resolve_document_organization_identities("rep_test", (first, second, alias))

    assert len(result.identities) == 3
    assert {item.status for item in result.alias_decisions} == {AliasDecisionStatus.AMBIGUOUS}


def test_pair_generation_uses_only_validated_distinct_identities() -> None:
    declaration = "National Institute of Standards and Technology (NIST)"
    source = f"{declaration} worked with Anthropic and NIST."
    declaration_mention = _validated(source, "segment-1", declaration, declaration)
    anthropic_start = source.index("Anthropic")
    anthropic_candidate = fuse_mention_proposals(
        source,
        "segment-1",
        (_observation("qwen", "Anthropic", anthropic_start, anthropic_start + 9),),
    )[0]
    anthropic_result = resolve_organization_qualification(
        representation_id="rep_test",
        source_text=source,
        candidate=anthropic_candidate,
        returned_text="Anthropic",
        rejected=False,
        model_run_id="mrn_anthropic",
    )
    assert anthropic_result.mention is not None
    nist_start = source.rindex("NIST")
    nist_candidate = fuse_mention_proposals(
        source,
        "segment-1",
        (_observation("gliner", "NIST", nist_start, nist_start + 4, 0.8),),
    )[0]
    nist_result = resolve_organization_qualification(
        representation_id="rep_test",
        source_text=source,
        candidate=nist_candidate,
        returned_text="NIST",
        rejected=False,
        model_run_id="mrn_nist",
    )
    assert nist_result.mention is not None
    mentions = (declaration_mention, anthropic_result.mention, nist_result.mention)
    identities = resolve_document_organization_identities("rep_test", mentions).identities

    pairs = derive_qualified_organization_pairs("segment-1", mentions, identities)

    assert len(pairs) == 1
    assert {pairs[0].first_organization_text, pairs[0].second_organization_text} == {
        declaration,
        "Anthropic",
    }
