from __future__ import annotations

import math
from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentArchivedFiniteLabelObservation,
    AttachmentCandidateRemainderArm,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEvidenceReference,
    ExecutionSetting,
    ModelExecutionReceipt,
    ModelOutputTokenProbability,
    ModelTokenAlternative,
    attachment_edge_filter_generation_parameters,
)
from kotekomi_pipelines.competitive_attachment_finite_answer_format import (
    answer_format_outcome,
    build_finite_label_recovery_report,
    finite_label_evidence,
    validate_answer_format_prompt_pair,
)

ROOT = Path(__file__).resolve().parents[3]


def test_foreign_emitted_token_preserves_diagnostic_finite_label_evidence() -> None:
    receipt = _receipt(
        emitted_token="Answer",
        emitted_log_probability=-0.21875,
        alternatives=(
            ModelTokenAlternative("Answer", -0.21875, tuple(b"Answer")),
            ModelTokenAlternative("Y", -1.8125, (89,)),
            ModelTokenAlternative("U", -4.0625, (85,)),
            ModelTokenAlternative("N", -5.21875, (78,)),
        ),
    )

    evidence = finite_label_evidence(receipt)

    assert evidence.emitted_token == "Answer"
    assert evidence.finite_label_argmax is AttachmentEdgeFilterAnswerValue.YES
    assert math.isclose(evidence.attachment_score, 1.9764189099786782, abs_tol=1e-12)
    assert evidence.answer_label_observed is True
    assert evidence.conservative_answer_log_probability == -0.21875


def test_missing_answer_alternative_uses_a_conservative_upper_bound() -> None:
    receipt = _receipt(
        emitted_token="Y",
        emitted_log_probability=-0.1,
        alternatives=(
            ModelTokenAlternative("Y", -0.1, (89,)),
            ModelTokenAlternative("N", -2.0, (78,)),
            ModelTokenAlternative("U", -3.0, (85,)),
            ModelTokenAlternative("Other", -7.0, tuple(b"Other")),
        ),
    )

    evidence = finite_label_evidence(receipt)

    assert evidence.answer_label_observed is False
    assert evidence.answer_label_log_probability is None
    assert evidence.conservative_answer_log_probability == -7.0


def test_format_prompts_differ_only_in_two_demonstration_answers() -> None:
    labeled = (
        ROOT / "prompts/competitive_attachment_residual_ownership_format_labeled_v1.md"
    ).read_text()
    bare = (
        ROOT / "prompts/competitive_attachment_residual_ownership_format_bare_v1.md"
    ).read_text()

    validate_answer_format_prompt_pair(labeled, bare)

    with pytest.raises(ValueError, match="two answer lines"):
        validate_answer_format_prompt_pair(labeled, bare.replace("Target Event", "Chosen Event"))


def test_recovery_preserves_two_invalid_outputs_and_all_finite_scores() -> None:
    observations = tuple(_archived_observation(index, invalid=index >= 18) for index in range(20))

    report = build_finite_label_recovery_report(
        inputs=(AttachmentEvidenceReference(label="input", path="/input", sha256="a" * 64),),
        observations=observations,
    )

    assert report.finite_label_evidence_count == 20
    assert report.sealed_score_comparison_count == 18
    assert report.sealed_score_match_count == 18
    assert report.invalid_observed_answer_count == 2


@pytest.mark.parametrize(
    ("values", "expected"),
    (
        (
            {
                "probability_evidence_count": 20,
                "answer_pressure_comparison_count": 10,
                "labeled_valid_output_count": 8,
                "bare_valid_output_count": 10,
                "labeled_answer_first_token_count": 2,
                "bare_answer_first_token_count": 0,
                "finite_label_argmax_agreement_count": 9,
                "median_answer_pressure_delta_upper_bound": -5.0,
            },
            "supported",
        ),
        (
            {
                "probability_evidence_count": 20,
                "answer_pressure_comparison_count": 10,
                "labeled_valid_output_count": 8,
                "bare_valid_output_count": 9,
                "labeled_answer_first_token_count": 2,
                "bare_answer_first_token_count": 0,
                "finite_label_argmax_agreement_count": 8,
                "median_answer_pressure_delta_upper_bound": -4.0,
            },
            "mixed",
        ),
        (
            {
                "probability_evidence_count": 20,
                "answer_pressure_comparison_count": 10,
                "labeled_valid_output_count": 10,
                "bare_valid_output_count": 10,
                "labeled_answer_first_token_count": 0,
                "bare_answer_first_token_count": 0,
                "finite_label_argmax_agreement_count": 10,
                "median_answer_pressure_delta_upper_bound": 0.0,
            },
            "falsified",
        ),
        (
            {
                "probability_evidence_count": 19,
                "answer_pressure_comparison_count": 10,
                "labeled_valid_output_count": 8,
                "bare_valid_output_count": 10,
                "labeled_answer_first_token_count": 2,
                "bare_answer_first_token_count": 0,
                "finite_label_argmax_agreement_count": 9,
                "median_answer_pressure_delta_upper_bound": -6.0,
            },
            "inconclusive",
        ),
        (
            {
                "probability_evidence_count": 20,
                "answer_pressure_comparison_count": 9,
                "labeled_valid_output_count": 8,
                "bare_valid_output_count": 10,
                "labeled_answer_first_token_count": 2,
                "bare_answer_first_token_count": 0,
                "finite_label_argmax_agreement_count": 9,
                "median_answer_pressure_delta_upper_bound": None,
            },
            "inconclusive",
        ),
    ),
)
def test_format_outcome_uses_predeclared_gates(
    values: dict[str, int | float | None],
    expected: str,
) -> None:
    result = answer_format_outcome(**values)  # type: ignore[arg-type]

    assert result.value == expected


def test_edge_filter_can_raise_only_the_experimental_output_limit() -> None:
    settings = (
        ExecutionSetting("max_output_tokens", 512),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", 10),
    )

    effective = attachment_edge_filter_generation_parameters(
        settings,
        effective_max_output_tokens=8,
    )

    assert {item.key: item.value for item in effective}["max_output_tokens"] == 8


def _receipt(
    *,
    emitted_token: str,
    emitted_log_probability: float,
    alternatives: tuple[ModelTokenAlternative, ...],
) -> ModelExecutionReceipt:
    return ModelExecutionReceipt(
        model_identity_digest="1" * 64,
        generation_parameters_digest="2" * 64,
        rendered_input_digest="3" * 64,
        input_token_count=10,
        output_token_count=1,
        output_token_probabilities=(
            ModelOutputTokenProbability(
                position=0,
                token=emitted_token,
                log_probability=emitted_log_probability,
                token_bytes=tuple(emitted_token.encode()),
                alternatives=alternatives,
            ),
        ),
    )


def _archived_observation(
    index: int,
    *,
    invalid: bool,
) -> AttachmentArchivedFiniteLabelObservation:
    alternatives = (
        (
            ModelTokenAlternative("Answer", -0.1, tuple(b"Answer")),
            ModelTokenAlternative("Y", -0.2, (89,)),
            ModelTokenAlternative("N", -2.0, (78,)),
            ModelTokenAlternative("U", -3.0, (85,)),
        )
        if invalid
        else (
            ModelTokenAlternative("Y", -0.1, (89,)),
            ModelTokenAlternative("N", -2.0, (78,)),
            ModelTokenAlternative("U", -3.0, (85,)),
        )
    )
    evidence = finite_label_evidence(
        _receipt(
            emitted_token="Answer" if invalid else "Y",
            emitted_log_probability=-0.1,
            alternatives=alternatives,
        )
    )
    return AttachmentArchivedFiniteLabelObservation(
        arm=(
            AttachmentCandidateRemainderArm.BASELINE
            if index % 2 == 0
            else AttachmentCandidateRemainderArm.REMAINDER
        ),
        task_id=f"aro_{index // 2:024x}",
        execution_record=AttachmentEvidenceReference(
            label=f"execution_{index:02d}",
            path=f"/execution/{index}",
            sha256=f"{index + 1:064x}",
        ),
        observed_answer=None if invalid else AttachmentEdgeFilterAnswerValue.YES,
        raw_output_text="Answer:" if invalid else "Y",
        finite_label_evidence=evidence,
        sealed_attachment_score=None if invalid else evidence.attachment_score,
        sealed_score_matches=None if invalid else True,
    )
