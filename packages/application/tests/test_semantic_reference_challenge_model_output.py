from __future__ import annotations

import pytest
from kotekomi_application.semantic_reference_challenge_model_output import (
    parse_semantic_reference_challenge_output,
    semantic_reference_challenge_schema_bytes,
)


def test_reference_challenge_parses_supplied_candidate_and_typed_non_resolutions() -> None:
    selected = parse_semantic_reference_challenge_output(
        b"antecedent: a1\nreason: The target refers to this supplied antecedent.\n"
    )
    ambiguous = parse_semantic_reference_challenge_output(
        b"antecedent: ambiguous\nreason: Two supplied candidates remain plausible.\n"
    )
    unresolved = parse_semantic_reference_challenge_output(
        b"antecedent: unresolved\nreason: No supplied candidate is supported.\n"
    )

    assert selected.antecedent_candidate_label == "a1"
    assert ambiguous.ambiguous is True
    assert unresolved.antecedent_candidate_label is None
    assert unresolved.ambiguous is False


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"antecedent: a1\n",
        b"reason: wrong order\nantecedent: unresolved\n",
        b"antecedent: copied antecedent text\nreason: not a supplied ID\n",
        b"antecedent: cfa_0123456789abcdef01234567\nreason: opaque ID\n",
    ),
)
def test_reference_challenge_rejects_changed_literal_contract(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_semantic_reference_challenge_output(payload)


def test_reference_challenge_schema_is_literal_and_does_not_request_source_text() -> None:
    schema = semantic_reference_challenge_schema_bytes()

    assert b"legal_outcomes" in schema
    assert b"<supplied" not in schema
    assert b"source" not in schema
    assert b'"properties"' not in schema
