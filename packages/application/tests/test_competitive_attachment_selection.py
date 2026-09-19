from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentNormalizationOperation,
    AttachmentSourceRange,
    AttachmentSyntaxObservation,
    PredicateArgumentHypothesis,
    PredicateArgumentPathDirection,
    PredicateArgumentPathStep,
    PredicateArgumentToken,
    attachment_syntax_policies,
    governed_complement_scope_supports,
    normalize_attachment_comparison_range,
    syntax_policy_supports,
)


@pytest.mark.parametrize(
    ("source", "candidate", "expected", "operations"),
    (
        (
            'Prefix, as "far too blunt an instrument" suffix',
            ', as "far too blunt an instrument"',
            'as "far too blunt an instrument"',
            (AttachmentNormalizationOperation.LEADING_DELIMITER,),
        ),
        (
            "Prefix that it would allow Claude Gov. [11][12] suffix",
            "that it would allow Claude Gov. [11][12]",
            "that it would allow Claude Gov.",
            (AttachmentNormalizationOperation.TERMINAL_CITATION_MARKERS,),
        ),
        (
            "Prefix   :  exact fact suffix",
            "  :  exact fact",
            "exact fact",
            (
                AttachmentNormalizationOperation.LEADING_WHITESPACE,
                AttachmentNormalizationOperation.LEADING_DELIMITER,
            ),
        ),
        (
            "Prefix (Acme-Co's) suffix",
            "(Acme-Co's)",
            "(Acme-Co's)",
            (),
        ),
    ),
)
def test_comparison_range_applies_only_declared_boundary_normalization(
    source: str,
    candidate: str,
    expected: str,
    operations: tuple[AttachmentNormalizationOperation, ...],
) -> None:
    start = source.index(candidate)
    result = normalize_attachment_comparison_range(
        phase="development",
        source_segment_id="seg_fixture",
        source_text=source,
        candidate_id="cac_" + "1" * 24,
        authoritative_start=start,
        authoritative_end=start + len(candidate),
    )

    assert result.authoritative_range.text == candidate
    assert result.comparison_text == expected
    assert result.operations == operations
    assert source[result.comparison_start : result.comparison_end] == expected


def test_comparison_range_records_empty_citation_only_gap() -> None:
    source = "Claim [7]"
    start = source.index("[7]")

    result = normalize_attachment_comparison_range(
        phase="validation",
        source_segment_id="seg_fixture",
        source_text=source,
        candidate_id="cac_" + "2" * 24,
        authoritative_start=start,
        authoritative_end=len(source),
    )

    assert result.comparison_text == ""
    assert result.gap_code is not None


def test_policy_inventory_contains_all_bounded_and_complement_variants() -> None:
    policies = attachment_syntax_policies()

    assert len(policies) == 10
    assert tuple(item.policy_id for item in policies) == (
        "path_1",
        "path_1_plus_complement",
        "path_2",
        "path_2_plus_complement",
        "path_3",
        "path_3_plus_complement",
        "path_4",
        "path_4_plus_complement",
        "path_unbounded",
        "path_unbounded_plus_complement",
    )


def test_governed_complement_rescues_direct_subtree_beyond_path_limit() -> None:
    observation = _observation(
        directions=(
            PredicateArgumentPathDirection.TOWARD_DEPENDENT,
            PredicateArgumentPathDirection.TOWARD_DEPENDENT,
        ),
        relations=("ccomp", "obj"),
    )
    policies = {item.policy_id: item for item in attachment_syntax_policies()}

    assert governed_complement_scope_supports(observation) is True
    assert syntax_policy_supports(observation, policies["path_1"]) is False
    assert syntax_policy_supports(observation, policies["path_1_plus_complement"]) is True


def test_governed_complement_does_not_cross_back_into_sibling_subtree() -> None:
    observation = _observation(
        directions=(
            PredicateArgumentPathDirection.TOWARD_DEPENDENT,
            PredicateArgumentPathDirection.TOWARD_HEAD,
        ),
        relations=("ccomp", "conj"),
    )
    policy = next(
        item for item in attachment_syntax_policies() if item.policy_id == "path_1_plus_complement"
    )

    assert governed_complement_scope_supports(observation) is False
    assert syntax_policy_supports(observation, policy) is False


def _observation(
    *,
    directions: tuple[PredicateArgumentPathDirection, PredicateArgumentPathDirection],
    relations: tuple[str, str],
) -> AttachmentSyntaxObservation:
    source = "said acquired target"
    event = _token("t1", "said", 0, 4, "root", None)
    complement = _token("t2", "acquired", 5, 13, relations[0], "t1")
    candidate = _token("t3", "target", 14, 20, relations[1], "t2")
    return AttachmentSyntaxObservation(
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        linguistic_trace_id="xst_" + "1" * 24,
        linguistic_resource_identity="2" * 64,
        candidate_id="cac_" + "3" * 24,
        source_grounded_event_id="sge_" + "4" * 24,
        candidate_range=AttachmentSourceRange(start=14, end=20, text="target"),
        event_range=AttachmentSourceRange(start=0, end=4, text="said"),
        event_head_range=AttachmentSourceRange(start=0, end=4, text="said"),
        event_anchor=event,
        candidate_anchor=candidate,
        path_tokens=(event, complement, candidate),
        path_steps=(
            PredicateArgumentPathStep(
                from_token_id="t1",
                to_token_id="t2",
                direction=directions[0],
                dependency_relation=relations[0],
            ),
            PredicateArgumentPathStep(
                from_token_id="t2",
                to_token_id="t3",
                direction=directions[1],
                dependency_relation=relations[1],
            ),
        ),
        hypothesis=PredicateArgumentHypothesis.INHERITED_ARGUMENT,
        gap_code=None,
        own_event_expression=False,
        structurally_supported=True,
    )


def _token(
    token_id: str,
    text: str,
    start: int,
    end: int,
    relation: str,
    head: str | None,
) -> PredicateArgumentToken:
    return PredicateArgumentToken(
        token_id=token_id,
        sentence_id="s1",
        text=text,
        start=start,
        end=end,
        lemma=text,
        part_of_speech="VERB" if token_id != "t3" else "NOUN",
        dependency_relation=relation,
        head_token_id=head,
    )
