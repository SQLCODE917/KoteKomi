from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentCandidateRootEvidence,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    PropositionFragmentReason,
    attachment_candidate_root_evidence,
    attachment_candidate_root_tokens,
    attachment_syntax_is_head_aligned,
    build_attachment_syntax_observation,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)


def test_exact_candidate_root_equal_to_event_anchor_is_head_aligned() -> None:
    source = "an agreement with Institute"
    candidate, event, evidence = _case(
        source,
        event_text="agreement",
        tokens=(
            ("an", "DET", "det", "t2"),
            ("agreement", "NOUN", "root", None),
            ("with", "ADP", "case", "t4"),
            ("Institute", "PROPN", "nmod", "t2"),
        ),
    )
    event_start = source.index("agreement")

    syntax = build_attachment_syntax_observation(
        phase="validation",
        source_text=source,
        candidate=candidate,
        event=event,
        event_head_start=event_start,
        event_head_end=event_start + len("agreement"),
        event_head_text="agreement",
        linguistic_evidence=evidence,
    )
    roots = attachment_candidate_root_tokens(candidate, evidence)
    root_evidence = attachment_candidate_root_evidence(candidate, evidence)

    assert tuple((item.token_id, item.text) for item in roots) == (("t2", "agreement"),)
    assert root_evidence.roots == roots
    assert tuple(item.token_id for item in root_evidence.tokens) == candidate.linguistic_token_ids
    assert syntax.event_anchor is not None
    assert syntax.event_anchor.token_id == "t2"
    assert attachment_syntax_is_head_aligned(syntax, roots) is True


def test_multiple_candidate_roots_remain_semantic() -> None:
    source = "wrote an"
    candidate, event, evidence = _case(
        source,
        event_text="wrote",
        tokens=(
            ("wrote", "VERB", "root", None),
            ("an", "DET", "dep", None),
        ),
    )

    syntax = build_attachment_syntax_observation(
        phase="validation",
        source_text=source,
        candidate=candidate,
        event=event,
        event_head_start=0,
        event_head_end=len("wrote"),
        event_head_text="wrote",
        linguistic_evidence=evidence,
    )
    roots = attachment_candidate_root_tokens(candidate, evidence)

    assert tuple(item.token_id for item in roots) == ("t1", "t2")
    assert attachment_syntax_is_head_aligned(syntax, roots) is False


def test_candidate_root_evidence_rejects_an_incomplete_root_inventory() -> None:
    source = "wrote an"
    candidate, _event, evidence = _case(
        source,
        event_text="wrote",
        tokens=(
            ("wrote", "VERB", "root", None),
            ("an", "DET", "dep", None),
        ),
    )
    complete = attachment_candidate_root_evidence(candidate, evidence)

    with pytest.raises(ValueError, match="Candidate Roots are incomplete"):
        AttachmentCandidateRootEvidence(
            tokens=complete.tokens,
            roots=(complete.roots[0],),
        )


def test_zero_candidate_roots_remain_semantic() -> None:
    source = "event"
    candidate, event, evidence = _case(
        source,
        event_text="event",
        tokens=(("event", "NOUN", "dep", "t1"),),
    )
    syntax = build_attachment_syntax_observation(
        phase="validation",
        source_text=source,
        candidate=candidate,
        event=event,
        event_head_start=0,
        event_head_end=len(source),
        event_head_text=source,
        linguistic_evidence=evidence,
    )
    roots = attachment_candidate_root_tokens(candidate, evidence)

    assert roots == ()
    assert syntax.gap_code is not None
    assert attachment_syntax_is_head_aligned(syntax, roots) is False


def test_dependency_gap_blocks_one_root_from_the_structural_route() -> None:
    source = "event"
    candidate, event, evidence = _case(
        source,
        event_text="event",
        tokens=(("event", "NOUN", "root", None),),
    )
    syntax = build_attachment_syntax_observation(
        phase="validation",
        source_text=source,
        candidate=candidate,
        event=event,
        event_head_start=1,
        event_head_end=len(source),
        event_head_text="vent",
        linguistic_evidence=evidence,
    )
    roots = attachment_candidate_root_tokens(candidate, evidence)

    assert len(roots) == 1
    assert syntax.gap_code is not None
    assert attachment_syntax_is_head_aligned(syntax, roots) is False


def _case(
    source: str,
    *,
    event_text: str,
    tokens: tuple[tuple[str, str, str, str | None], ...],
) -> tuple[
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    EventEntityLinguisticEvidence,
]:
    source_segment_id = "seg_dependency_head_fixture"
    digest = hashlib.sha256(source.encode()).hexdigest()
    token_values: list[EventEntityLinguisticToken] = []
    cursor = 0
    for ordinal, (text, part_of_speech, relation, head) in enumerate(tokens, 1):
        start = source.index(text, cursor)
        end = start + len(text)
        cursor = end
        token_values.append(
            EventEntityLinguisticToken(
                token_id=f"t{ordinal}",
                sentence_id="s1",
                text=text,
                start=start,
                end=end,
                lemma=text.casefold(),
                part_of_speech=part_of_speech,
                dependency_relation=relation,
                head_token_id=head,
            )
        )
    reasons = (PropositionFragmentReason.CLAUSE_LOCAL_CONSTITUENT,)
    parent_ids = ("pfc_" + "1" * 24,)
    token_ids = tuple(item.token_id for item in token_values)
    record_ids = ("fixture_record",)
    candidate = CompetitiveAttachmentCandidate(
        id=competitive_attachment_candidate_id(
            source_segment_id=source_segment_id,
            source_text_sha256=digest,
            start=0,
            end=len(source),
            text=source,
            reasons=reasons,
            parent_candidate_ids=parent_ids,
            linguistic_token_ids=token_ids,
            source_record_ids=record_ids,
        ),
        source_segment_id=source_segment_id,
        source_text_sha256=digest,
        start=0,
        end=len(source),
        text=source,
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
    event_start = source.index(event_text)
    event_end = event_start + len(event_text)
    event_id = "sge_" + "2" * 24
    trigger_id = "etd_" + "3" * 24
    event = CompetitiveAttachmentEventOption(
        id=competitive_attachment_event_option_id(
            source_grounded_event_id=event_id,
            event_trigger_id=trigger_id,
            source_segment_id=source_segment_id,
            source_text_sha256=digest,
            start=event_start,
            end=event_end,
            text=event_text,
        ),
        label="E1",
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id=source_segment_id,
        source_text_sha256=digest,
        start=event_start,
        end=event_end,
        text=event_text,
    )
    evidence = EventEntityLinguisticEvidence(
        trace_id="xst_" + "4" * 24,
        source_segment_id=source_segment_id,
        source_text_sha256=digest,
        producer_id="stanza:fixture",
        model_id="stanza-en",
        model_version="fixture",
        resource_identity="5" * 64,
        tokens=tuple(token_values),
    )
    return candidate, event, evidence
