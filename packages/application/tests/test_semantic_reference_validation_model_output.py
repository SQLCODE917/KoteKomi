from __future__ import annotations

import pytest
from kotekomi_application.semantic_reference_validation_model_output import (
    SemanticReferenceCandidateVerdict,
    parse_semantic_reference_candidate_validation_output,
    semantic_reference_candidate_validation_schema_bytes,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("supported", SemanticReferenceCandidateVerdict.SUPPORTED),
        ("unsupported", SemanticReferenceCandidateVerdict.UNSUPPORTED),
        ("unclear", SemanticReferenceCandidateVerdict.UNCLEAR),
    ),
)
def test_reference_candidate_validation_parses_each_typed_verdict(
    value: str,
    expected: SemanticReferenceCandidateVerdict,
) -> None:
    result = parse_semantic_reference_candidate_validation_output(
        f"verdict: {value}\nreason: The bounded evidence supports this judgment.\n".encode()
    )

    assert result.verdict is expected
    assert result.reason == "The bounded evidence supports this judgment."


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"verdict: supported\n",
        b"reason: wrong order\nverdict: supported\n",
        b"verdict: yes\nreason: untyped result\n",
        b"verdict: supported \nreason: untrimmed\n",
        b"verdict: supported\nreason: \n",
    ),
)
def test_reference_candidate_validation_rejects_changed_literal_contract(
    payload: bytes,
) -> None:
    with pytest.raises(ValueError):
        parse_semantic_reference_candidate_validation_output(payload)


def test_reference_candidate_validation_schema_is_literal_and_bounded() -> None:
    schema = semantic_reference_candidate_validation_schema_bytes()

    assert b"supported, unsupported, or unclear" in schema
    assert b"exactly two lines" in schema
    assert b"candidate ID" not in schema
    assert b'"properties"' not in schema
