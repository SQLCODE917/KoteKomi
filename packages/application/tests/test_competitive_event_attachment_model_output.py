from __future__ import annotations

import pytest
from kotekomi_application import (
    CompetitiveAttachmentAnswerKind,
    parse_competitive_attachment_answer,
)


@pytest.mark.parametrize(
    ("payload", "kind", "labels"),
    (
        (b"NONE", CompetitiveAttachmentAnswerKind.NONE, ()),
        (b"  UNCLEAR\n", CompetitiveAttachmentAnswerKind.UNCLEAR, ()),
        (b"E1", CompetitiveAttachmentAnswerKind.ATTACHED, ("E1",)),
        (b"E1,E3", CompetitiveAttachmentAnswerKind.ATTACHED, ("E1", "E3")),
    ),
)
def test_parser_accepts_only_finite_ordered_answers(
    payload: bytes,
    kind: CompetitiveAttachmentAnswerKind,
    labels: tuple[str, ...],
) -> None:
    answer = parse_competitive_attachment_answer(
        payload,
        allowed_event_labels=("E1", "E2", "E3"),
    )

    assert answer.kind is kind
    assert answer.event_labels == labels


@pytest.mark.parametrize(
    "payload",
    (b"E3,E1", b"E1,E1", b"E4", b"NONE,E1", b"E1 because it fits", b""),
)
def test_parser_rejects_reordered_duplicate_unknown_mixed_or_explanatory_output(
    payload: bytes,
) -> None:
    with pytest.raises(ValueError):
        parse_competitive_attachment_answer(
            payload,
            allowed_event_labels=("E1", "E2", "E3"),
        )
