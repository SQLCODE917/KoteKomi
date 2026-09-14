from __future__ import annotations

import pytest
from kotekomi_application.hybrid_standing_fact_model_output import (
    StandingFactAbstention,
    StandingFactObjectKind,
    StandingFactProposal,
    StandingFactProposalBatch,
    parse_standing_fact_output,
)


def test_parses_entity_and_literal_standing_facts() -> None:
    parsed = parse_standing_fact_output(
        b"fact: c1 | o2-o3 | entity | c2\nfact: c1 | o4-o6 | literal | o7-o10\n"
    )

    assert parsed == StandingFactProposalBatch(
        proposals=(
            StandingFactProposal("c1", "o2-o3", StandingFactObjectKind.ENTITY, "c2"),
            StandingFactProposal(
                "c1",
                "o4-o6",
                StandingFactObjectKind.LITERAL,
                "o7-o10",
            ),
        )
    )


def test_retains_bad_line_without_erasing_valid_fact() -> None:
    parsed = parse_standing_fact_output(
        b"fact: unknown | o2-o3 | entity | c2\nfact: c1 | o2-o3 | entity | c2\n"
    )

    assert isinstance(parsed, StandingFactProposalBatch)
    assert parsed.proposals == (
        StandingFactProposal("c1", "o2-o3", StandingFactObjectKind.ENTITY, "c2"),
    )
    assert [(item.line_number, item.raw_line, item.reason) for item in parsed.rejections] == [
        (
            1,
            "fact: unknown | o2-o3 | entity | c2",
            "subject must use one local candidate label",
        )
    ]


def test_parses_explicit_abstention() -> None:
    assert parse_standing_fact_output(b"abstain: no standing fact\n") == (
        StandingFactAbstention("no standing fact")
    )


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"fact: c1 | o2 | entity | c2\n\n",
        b"abstain: none\nfact: c1 | o2 | entity | c2\n",
    ),
)
def test_rejects_invalid_container_output(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_standing_fact_output(payload)


def test_literal_object_must_select_a_supplied_occurrence_range() -> None:
    parsed = parse_standing_fact_output(b"fact: c1 | o2-o3 | literal | exact words\n")

    assert isinstance(parsed, StandingFactProposalBatch)
    assert parsed.proposals == ()
    assert parsed.rejections[0].reason == "literal object must use one source-occurrence range"
