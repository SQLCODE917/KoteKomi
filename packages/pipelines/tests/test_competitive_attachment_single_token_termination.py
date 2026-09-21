from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from kotekomi_application import (
    AttachmentSingleTokenPreflight,
    ExecutionSetting,
    attachment_edge_filter_generation_parameters,
    attachment_single_token_outcome,
)
from kotekomi_pipelines.competitive_attachment_single_token_termination import (
    build_single_token_report,
)


@pytest.mark.parametrize(
    ("values", "expected"),
    (
        (
            {
                "probability_evidence_count": 20,
                "one_token_output_count": 20,
                "strict_valid_output_count": 20,
                "observed_answer_argmax_match_count": 20,
                "archived_argmax_match_count": 20,
                "repetition_answer_agreement_count": 10,
                "repetition_argmax_agreement_count": 10,
            },
            "supported",
        ),
        (
            {
                "probability_evidence_count": 20,
                "one_token_output_count": 20,
                "strict_valid_output_count": 19,
                "observed_answer_argmax_match_count": 19,
                "archived_argmax_match_count": 20,
                "repetition_answer_agreement_count": 9,
                "repetition_argmax_agreement_count": 10,
            },
            "mixed",
        ),
        (
            {
                "probability_evidence_count": 20,
                "one_token_output_count": 6,
                "strict_valid_output_count": 6,
                "observed_answer_argmax_match_count": 6,
                "archived_argmax_match_count": 20,
                "repetition_answer_agreement_count": 3,
                "repetition_argmax_agreement_count": 10,
            },
            "falsified",
        ),
        (
            {
                "probability_evidence_count": 19,
                "one_token_output_count": 19,
                "strict_valid_output_count": 19,
                "observed_answer_argmax_match_count": 19,
                "archived_argmax_match_count": 19,
                "repetition_answer_agreement_count": 9,
                "repetition_argmax_agreement_count": 9,
            },
            "inconclusive",
        ),
    ),
)
def test_single_token_outcome_uses_predeclared_gates(
    values: dict[str, int],
    expected: str,
) -> None:
    assert attachment_single_token_outcome(**values).value == expected


def test_edge_filter_can_enforce_one_output_token() -> None:
    settings = (
        ExecutionSetting("max_output_tokens", 512),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", 10),
    )

    effective = attachment_edge_filter_generation_parameters(
        settings,
        effective_max_output_tokens=1,
    )

    assert {item.key: item.value for item in effective}["max_output_tokens"] == 1


def test_report_rejects_missing_repetition_observations() -> None:
    preflight = cast(AttachmentSingleTokenPreflight, SimpleNamespace(tasks=()))

    with pytest.raises(ValueError, match="both repetitions"):
        build_single_token_report(inputs=(), preflight=preflight, observations=())
