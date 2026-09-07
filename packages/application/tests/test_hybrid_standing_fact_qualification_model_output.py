from __future__ import annotations

import pytest
from kotekomi_application import (
    parse_standing_fact_qualification_output,
    standing_fact_qualification_schema_bytes,
)
from kotekomi_domain import StandingFactQualificationOutcome


def test_standing_fact_qualification_parses_the_literal_contract() -> None:
    output = parse_standing_fact_qualification_output(
        b"outcome: supported_standing_fact\n"
        b"reason: The exact source states the complete standing relation.\n"
    )

    assert output.outcome is StandingFactQualificationOutcome.SUPPORTED_STANDING_FACT
    assert output.reason == "The exact source states the complete standing relation."
    assert b"event_not_standing" in standing_fact_qualification_schema_bytes()


@pytest.mark.parametrize(
    "payload",
    (
        b"outcome: supported_standing_fact\n",
        b"reason: absent outcome\noutcome: supported_standing_fact\n",
        b"outcome: invented\nreason: no\n",
        b"outcome: supported_standing_fact\nreason: \n",
        b"outcome: supported_standing_fact \nreason: whitespace\n",
    ),
)
def test_standing_fact_qualification_rejects_nonliteral_outputs(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_standing_fact_qualification_output(payload)
