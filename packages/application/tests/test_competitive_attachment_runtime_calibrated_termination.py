from __future__ import annotations

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    ModelOutputTokenProbability,
    ModelTokenAlternative,
    attachment_calibrated_termination_mechanism_proof,
    attachment_calibrated_termination_outcome,
    attachment_exact_raw_finite_answer,
    attachment_output_count_witnesses_agree,
    attachment_position_zero_sha256,
    parse_attachment_edge_filter_answer,
)


@pytest.mark.parametrize(
    ("successful", "probability", "exact", "mechanism", "expected"),
    (
        (20, 20, 20, True, "supported"),
        (20, 20, 19, False, "mixed"),
        (20, 20, 0, False, "falsified"),
        (19, 19, 19, False, "inconclusive"),
    ),
)
def test_calibrated_termination_outcome_uses_declared_mechanism_boundary(
    successful: int,
    probability: int,
    exact: int,
    mechanism: bool,
    expected: str,
) -> None:
    assert (
        attachment_calibrated_termination_outcome(
            successful_execution_count=successful,
            probability_evidence_count=probability,
            exact_raw_finite_answer_count=exact,
            mechanism_proof=mechanism,
        ).value
        == expected
    )


def test_mechanism_proof_requires_every_independent_gate() -> None:
    passing = {
        "successful_execution_count": 20,
        "probability_evidence_count": 20,
        "one_position_zero_count": 20,
        "one_output_token_count": 20,
        "output_count_witness_agreement_count": 20,
        "exact_raw_finite_answer_count": 20,
        "observed_answer_argmax_match_count": 20,
        "archived_distribution_match_count": 20,
        "repetition_answer_agreement_count": 10,
        "repetition_distribution_agreement_count": 10,
    }

    assert attachment_calibrated_termination_mechanism_proof(**passing)
    assert not attachment_calibrated_termination_mechanism_proof(
        **(passing | {"exact_raw_finite_answer_count": 19})
    )


def test_exact_raw_answer_is_stricter_than_the_existing_stripping_parser() -> None:
    assert parse_attachment_edge_filter_answer(b"Y\n\n") is AttachmentEdgeFilterAnswerValue.YES
    assert attachment_exact_raw_finite_answer("Y")
    assert not attachment_exact_raw_finite_answer("Y\n\n")
    assert not attachment_exact_raw_finite_answer(None)


def test_output_count_witnesses_must_independently_identify_one_token() -> None:
    assert attachment_output_count_witnesses_agree(
        output_token_count=1,
        probability_positions=(0,),
    )
    assert not attachment_output_count_witnesses_agree(
        output_token_count=1,
        probability_positions=(0, 1),
    )
    assert not attachment_output_count_witnesses_agree(
        output_token_count=2,
        probability_positions=(0,),
    )


def test_position_zero_digest_covers_full_ordered_probability_evidence() -> None:
    alternatives = (
        ModelTokenAlternative("Y", -0.25, (89,)),
        ModelTokenAlternative("N", -1.25, (78,)),
        ModelTokenAlternative("U", -2.25, (85,)),
    )
    first = ModelOutputTokenProbability(0, "Y", -0.25, (89,), alternatives)
    changed = ModelOutputTokenProbability(
        0,
        "Y",
        -0.5,
        (89,),
        (
            ModelTokenAlternative("Y", -0.5, (89,)),
            ModelTokenAlternative("N", -1.25, (78,)),
            ModelTokenAlternative("U", -2.25, (85,)),
        ),
    )

    assert attachment_position_zero_sha256(first) == attachment_position_zero_sha256(first)
    assert attachment_position_zero_sha256(first) != attachment_position_zero_sha256(changed)
