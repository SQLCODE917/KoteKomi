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
        b"fact: c1 | collaborated with | entity | c2\n"
        b"fact: c1 | is described as | literal | an AI safety company\n"
    )

    assert parsed == StandingFactProposalBatch(
        proposals=(
            StandingFactProposal("c1", "collaborated with", StandingFactObjectKind.ENTITY, "c2"),
            StandingFactProposal(
                "c1",
                "is described as",
                StandingFactObjectKind.LITERAL,
                "an AI safety company",
            ),
        )
    )


def test_retains_bad_line_without_erasing_valid_fact() -> None:
    parsed = parse_standing_fact_output(
        b"fact: unknown | collaborated with | entity | c2\n"
        b"fact: c1 | collaborated with | entity | c2\n"
    )

    assert isinstance(parsed, StandingFactProposalBatch)
    assert parsed.proposals == (
        StandingFactProposal("c1", "collaborated with", StandingFactObjectKind.ENTITY, "c2"),
    )
    assert [(item.line_number, item.raw_line, item.reason) for item in parsed.rejections] == [
        (
            1,
            "fact: unknown | collaborated with | entity | c2",
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
        b"fact: c1 | owns | entity | c2\n\n",
        b"abstain: none\nfact: c1 | owns | entity | c2\n",
    ),
)
def test_rejects_invalid_container_output(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_standing_fact_output(payload)
