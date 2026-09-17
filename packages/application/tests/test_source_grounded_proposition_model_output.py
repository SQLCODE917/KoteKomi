from __future__ import annotations

import pytest
from kotekomi_application import (
    PropositionFragmentAnswerValue,
    parse_proposition_fragment_answer,
    proposition_fragment_answer_schema_bytes,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        (b"Y", PropositionFragmentAnswerValue.YES),
        (b"N", PropositionFragmentAnswerValue.NO),
        (b"U", PropositionFragmentAnswerValue.UNCERTAIN),
        (b"Y\n\n", PropositionFragmentAnswerValue.YES),
        (b"\nN\r\n", PropositionFragmentAnswerValue.NO),
        (b" U \t", PropositionFragmentAnswerValue.UNCERTAIN),
    ),
)
def test_parser_accepts_only_the_three_finite_answers(
    raw: bytes,
    expected: PropositionFragmentAnswerValue,
) -> None:
    assert parse_proposition_fragment_answer(raw).value is expected


@pytest.mark.parametrize(
    "raw",
    (b"", b"YES", b"Y N", b"Y\nN", b"`Y`", b"?", b"\xc2\xa0Y", b"\xff"),
)
def test_parser_rejects_every_other_shape(raw: bytes) -> None:
    with pytest.raises(ValueError):
        parse_proposition_fragment_answer(raw)


def test_schema_describes_the_exact_contract() -> None:
    assert proposition_fragment_answer_schema_bytes() == (
        b"Return exactly one answer character: Y, N, or U. "
        b"Surrounding ASCII whitespace is framing only.\n"
    )
