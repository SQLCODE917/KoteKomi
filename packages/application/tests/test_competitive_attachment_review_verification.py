from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentRangeRelation,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    PredicateArgumentHypothesis,
    PropositionFragmentReason,
    build_attachment_syntax_observation,
    classify_attachment_range_relation,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
    parse_unordered_attachment_labels,
)


@pytest.mark.parametrize(
    ("candidate", "gold", "expected"),
    (
        ((2, 5), ((1, 6),), AttachmentRangeRelation.CANDIDATE_WITHIN_GOLD),
        ((1, 6), ((2, 5),), AttachmentRangeRelation.GOLD_WITHIN_CANDIDATE),
        ((1, 4), ((3, 6),), AttachmentRangeRelation.PARTIAL_OVERLAP),
        ((0, 2), ((4, 6),), AttachmentRangeRelation.DISJOINT),
    ),
)
def test_range_relation_uses_meaningful_source_characters(
    candidate: tuple[int, int],
    gold: tuple[tuple[int, int], ...],
    expected: AttachmentRangeRelation,
) -> None:
    source = "abcdefgh"

    assert (
        classify_attachment_range_relation(
            source_text=source,
            candidate_start=candidate[0],
            candidate_end=candidate[1],
            gold_ranges=gold,
        )
        is expected
    )


def test_syntax_observation_preserves_exact_direct_argument_path() -> None:
    source = "Anthropic criticized Stargate."
    candidate, event, evidence = _syntax_case(source)
    event_start = source.index("criticized")

    observation = build_attachment_syntax_observation(
        phase="development",
        source_text=source,
        candidate=candidate,
        event=event,
        event_head_start=event_start,
        event_head_end=event_start + len("criticized"),
        event_head_text="criticized",
        linguistic_evidence=evidence,
    )

    assert observation.hypothesis is PredicateArgumentHypothesis.DIRECT_ARGUMENT
    assert observation.gap_code is None
    assert observation.structurally_supported is True
    assert tuple(item.text for item in observation.path_tokens) == (
        "criticized",
        "Anthropic",
    )
    assert tuple(item.dependency_relation for item in observation.path_steps) == ("nsubj",)


def test_syntax_observation_rejects_unknown_candidate_token() -> None:
    source = "Anthropic criticized Stargate."
    candidate, event, evidence = _syntax_case(source)
    damaged = candidate.model_copy(update={"linguistic_token_ids": ("t99",)})
    event_start = source.index("criticized")

    with pytest.raises(ValueError, match="unknown linguistic tokens"):
        build_attachment_syntax_observation(
            phase="development",
            source_text=source,
            candidate=damaged,
            event=event,
            event_head_start=event_start,
            event_head_end=event_start + len("criticized"),
            event_head_text="criticized",
            linguistic_evidence=evidence,
        )


def test_unordered_counterfactual_preserves_emission_order_and_canonicalizes_set() -> None:
    emitted, canonical = parse_unordered_attachment_labels(
        b"E2,E1",
        allowed_event_labels=("E1", "E2", "E3"),
    )

    assert emitted == ("E2", "E1")
    assert canonical == ("E1", "E2")


@pytest.mark.parametrize("raw", (b"E1,E1", b"E1,E9", b"NONE,E1", b"E1, E2"))
def test_unordered_counterfactual_rejects_invalid_label_sets(raw: bytes) -> None:
    with pytest.raises(ValueError):
        parse_unordered_attachment_labels(
            raw,
            allowed_event_labels=("E1", "E2", "E3"),
        )


def _syntax_case(
    source: str,
) -> tuple[
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    EventEntityLinguisticEvidence,
]:
    source_segment_id = "seg_review_verification_fixture"
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    candidate_text = "Anthropic"
    candidate_start = source.index(candidate_text)
    candidate_end = candidate_start + len(candidate_text)
    reasons = (PropositionFragmentReason.ENTITY_OCCURRENCE,)
    parent_ids = ("pfc_" + "1" * 24,)
    token_ids = ("t1",)
    record_ids = ("fixture_record",)
    candidate = CompetitiveAttachmentCandidate(
        id=competitive_attachment_candidate_id(
            source_segment_id=source_segment_id,
            source_text_sha256=source_digest,
            start=candidate_start,
            end=candidate_end,
            text=candidate_text,
            reasons=reasons,
            parent_candidate_ids=parent_ids,
            linguistic_token_ids=token_ids,
            source_record_ids=record_ids,
        ),
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=candidate_start,
        end=candidate_end,
        text=candidate_text,
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
    event_text = "criticized"
    event_start = source.index(event_text)
    event_end = event_start + len(event_text)
    event_id = "sge_" + "2" * 24
    trigger_id = "etd_" + "3" * 24
    event = CompetitiveAttachmentEventOption(
        id=competitive_attachment_event_option_id(
            source_grounded_event_id=event_id,
            event_trigger_id=trigger_id,
            source_segment_id=source_segment_id,
            source_text_sha256=source_digest,
            start=event_start,
            end=event_end,
            text=event_text,
        ),
        label="E1",
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=event_start,
        end=event_end,
        text=event_text,
    )
    evidence = EventEntityLinguisticEvidence(
        trace_id="xst_" + "4" * 24,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        producer_id="stanza:fixture",
        model_id="stanza-en",
        model_version="fixture",
        resource_identity="5" * 64,
        tokens=(
            EventEntityLinguisticToken(
                token_id="t1",
                sentence_id="s1",
                text="Anthropic",
                start=0,
                end=9,
                lemma="anthropic",
                part_of_speech="PROPN",
                dependency_relation="nsubj",
                head_token_id="t2",
            ),
            EventEntityLinguisticToken(
                token_id="t2",
                sentence_id="s1",
                text="criticized",
                start=10,
                end=20,
                lemma="criticize",
                part_of_speech="VERB",
                dependency_relation="root",
                head_token_id=None,
            ),
            EventEntityLinguisticToken(
                token_id="t3",
                sentence_id="s1",
                text="Stargate",
                start=21,
                end=29,
                lemma="stargate",
                part_of_speech="PROPN",
                dependency_relation="obj",
                head_token_id="t2",
            ),
            EventEntityLinguisticToken(
                token_id="t4",
                sentence_id="s1",
                text=".",
                start=29,
                end=30,
                lemma=".",
                part_of_speech="PUNCT",
                dependency_relation="punct",
                head_token_id="t2",
            ),
        ),
    )
    return candidate, event, evidence
