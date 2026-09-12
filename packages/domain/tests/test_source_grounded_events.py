import pytest
from kotekomi_domain import Event, EventMention, deterministic_event_mention_id


def _mention(
    *,
    head: str = "etg_head",
    expression: str = "etg_expression",
    support: str = "etg_support",
) -> EventMention:
    return EventMention(
        id=deterministic_event_mention_id(
            head_evidence_target_id=head,
            expression_evidence_target_id=expression,
            support_evidence_target_id=support,
        ),
        head_evidence_target_id=head,
        expression_evidence_target_id=expression,
        support_evidence_target_id=support,
    )


def test_event_mention_identity_is_deterministic_and_embedded_in_event() -> None:
    mention = _mention()

    event = Event(id="evt_source_grounded", name="publicly rebuked", mentions=(mention,))

    assert event.mentions == (mention,)
    assert mention.id == deterministic_event_mention_id(
        head_evidence_target_id="etg_head",
        expression_evidence_target_id="etg_expression",
        support_evidence_target_id="etg_support",
    )


def test_event_mention_rejects_identity_that_does_not_match_evidence() -> None:
    with pytest.raises(ValueError, match="does not match its evidence identities"):
        EventMention(
            id="evm_wrong",
            head_evidence_target_id="etg_head",
            expression_evidence_target_id="etg_expression",
            support_evidence_target_id="etg_support",
        )


def test_event_rejects_duplicate_embedded_event_mentions() -> None:
    mention = _mention()

    with pytest.raises(ValueError, match="distinct identities"):
        Event(
            id="evt_source_grounded",
            name="publicly rebuked",
            mentions=(mention, mention),
        )


def test_event_mention_can_reuse_one_target_for_a_one_word_expression() -> None:
    mention = _mention(head="etg_exact", expression="etg_exact")

    assert mention.head_evidence_target_id == mention.expression_evidence_target_id
