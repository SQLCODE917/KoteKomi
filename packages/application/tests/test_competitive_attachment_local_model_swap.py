from __future__ import annotations

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentLocalModelArtifact,
    AttachmentLocalModelOutputCalibration,
    AttachmentLocalModelPrimaryRejection,
    AttachmentLocalModelReadiness,
    AttachmentLocalModelSwapCase,
    AttachmentLocalModelSwapOutcome,
    AttachmentLocalModelSwapTransition,
    AttachmentLocalModelVariant,
    AttachmentNestedTransferCase,
    AttachmentNestedTransferDecision,
    AttachmentNestedTransferEvaluation,
    AttachmentNestedTransferObservation,
    attachment_local_model_swap_transition,
    classify_attachment_local_model_swap_outcome,
)


def test_output_calibration_requires_one_exact_answer() -> None:
    calibration = AttachmentLocalModelOutputCalibration(
        input_sha256="a" * 64,
        status="completed",
        output_texts=("N",),
        output_token_count=1,
        reasoning_token_count=0,
    )

    assert calibration.output_texts == ("N",)
    with pytest.raises(ValueError, match="one exact answer"):
        AttachmentLocalModelOutputCalibration(
            input_sha256="a" * 64,
            status="completed",
            output_texts=("N", "Y"),
            output_token_count=1,
            reasoning_token_count=0,
        )


def test_local_model_artifact_pins_quantization_and_fallback_reason() -> None:
    primary = _artifact(AttachmentLocalModelVariant.Q6_K)

    assert primary.quantization == "Q6_K"

    with pytest.raises(ValueError, match="requires the Primary Variant failure reason"):
        _artifact(AttachmentLocalModelVariant.Q5_K_M)

    fallback = _artifact(
        AttachmentLocalModelVariant.Q5_K_M,
        fallback_reason="Q6_K exceeded the declared memory headroom.",
    )

    assert fallback.quantization == "Q5_K_M"


def test_local_model_readiness_rejects_over_limit_or_guardrail_failure() -> None:
    valid = {
        "status": "ready_for_load",
        "variant": AttachmentLocalModelVariant.Q6_K,
        "download_status": 0,
        "estimate_status": 0,
        "estimated_total_memory_gib": 17.5,
        "resource_guardrail_allows_load": True,
        "run_root": "/tmp/readiness",
        "model_key": "lmstudio-community/qwen3-14b-gguf@q6_k",
        "load_key": "lmstudio-community/qwen3-14b-gguf@q6_k",
        "download_log": "/tmp/readiness/download.log",
        "inventory": "/tmp/readiness/model-inventory.json",
        "estimate_log": "/tmp/readiness/memory-estimate.log",
    }

    assert AttachmentLocalModelReadiness.model_validate(valid).estimated_total_memory_gib == 17.5
    with pytest.raises(ValueError, match="less than or equal to 18"):
        AttachmentLocalModelReadiness.model_validate({**valid, "estimated_total_memory_gib": 18.1})
    with pytest.raises(ValueError, match="Input should be True"):
        AttachmentLocalModelReadiness.model_validate(
            {**valid, "resource_guardrail_allows_load": False}
        )

    rejection = AttachmentLocalModelPrimaryRejection.model_validate(
        {
            **valid,
            "status": "q6_rejected",
            "estimated_total_memory_gib": 11.29,
            "resource_guardrail_allows_load": False,
        }
    )
    assert rejection.estimated_total_memory_gib == 11.29


def test_local_model_swap_transition_distinguishes_correction_and_regression() -> None:
    baseline_wrong = _evaluation(1, expected="Y", answer="N")
    baseline_right = _evaluation(2, expected="N", answer="N")
    challenger_right = _evaluation(1, expected="Y", answer="Y")
    challenger_wrong = _evaluation(2, expected="N", answer="Y")

    assert (
        attachment_local_model_swap_transition(baseline_wrong, challenger_right)
        is AttachmentLocalModelSwapTransition.CORRECTED
    )
    assert (
        attachment_local_model_swap_transition(baseline_right, challenger_wrong)
        is AttachmentLocalModelSwapTransition.REGRESSED
    )


@pytest.mark.parametrize(
    ("challenger_correct", "swap_equal_errors", "unresolved", "expected"),
    (
        (18, False, False, AttachmentLocalModelSwapOutcome.SUPPORTED),
        (17, False, False, AttachmentLocalModelSwapOutcome.MIXED),
        (16, True, False, AttachmentLocalModelSwapOutcome.MIXED),
        (16, False, False, AttachmentLocalModelSwapOutcome.FALSIFIED),
        (18, False, True, AttachmentLocalModelSwapOutcome.INCONCLUSIVE),
    ),
)
def test_local_model_swap_outcome_uses_declared_quality_gates(
    challenger_correct: int,
    swap_equal_errors: bool,
    unresolved: bool,
    expected: AttachmentLocalModelSwapOutcome,
) -> None:
    baseline_answers = _baseline_answers()
    challenger_answers = list(baseline_answers)
    gold = _gold_answers()
    baseline_wrong = [
        index for index, answer in enumerate(baseline_answers) if answer != gold[index]
    ]
    for index in baseline_wrong[: max(0, challenger_correct - 16)]:
        challenger_answers[index] = gold[index]
    if swap_equal_errors:
        challenger_answers[baseline_wrong[0]] = gold[baseline_wrong[0]]
        challenger_answers[3] = "N" if gold[3] == "Y" else "Y"
    cases: list[AttachmentLocalModelSwapCase] = []
    for index, (expected_answer, baseline_answer, challenger_answer) in enumerate(
        zip(gold, baseline_answers, challenger_answers, strict=True),
        start=1,
    ):
        baseline = _evaluation(index, expected=expected_answer, answer=baseline_answer)
        challenger = _evaluation(
            index,
            expected=expected_answer,
            answer=challenger_answer,
            complete=not (unresolved and index == 20),
        )
        cases.append(
            AttachmentLocalModelSwapCase(
                case_id=baseline.case.id,
                historical_baseline=baseline,
                comparator_baseline=baseline,
                challenger=challenger,
                context_transition=attachment_local_model_swap_transition(baseline, baseline),
                model_transition=attachment_local_model_swap_transition(baseline, challenger),
            )
        )

    assert classify_attachment_local_model_swap_outcome(tuple(cases)) is expected


def _artifact(
    variant: AttachmentLocalModelVariant,
    *,
    fallback_reason: str | None = None,
) -> AttachmentLocalModelArtifact:
    quantization = {
        AttachmentLocalModelVariant.Q6_K: "Q6_K",
        AttachmentLocalModelVariant.Q5_K_M: "Q5_K_M",
    }[variant]
    return AttachmentLocalModelArtifact(
        variant=variant,
        model_key=f"lmstudio-community/qwen3-14b-gguf/{quantization}",
        display_name="Qwen3 14B",
        architecture="qwen3",
        quantization=quantization,
        bits_per_weight=6.5 if variant is AttachmentLocalModelVariant.Q6_K else 5.5,
        size_bytes=12_100_000_000,
        params_string="14B",
        format="gguf",
        loaded_instance_id="qwen3-14b-nonthinking",
        context_length=16_384,
        max_context_length=32768,
        estimated_total_memory_gib=13.5,
        resource_guardrail_allows_load=True,
        readiness_evidence_sha256="c" * 64,
        fallback_reason=fallback_reason,
        metadata_sha256="a" * 64,
    )


def _gold_answers() -> list[str]:
    return ["Y"] * 12 + ["N"] * 8


def _baseline_answers() -> list[str]:
    answers = _gold_answers()
    for index in (0, 1, 2, 12):
        answers[index] = "N" if answers[index] == "Y" else "Y"
    return answers


def _evaluation(
    ordinal: int,
    *,
    expected: str,
    answer: str,
    complete: bool = True,
) -> AttachmentNestedTransferEvaluation:
    case_id = f"ntc_{ordinal:024x}"
    case = AttachmentNestedTransferCase.model_construct(
        id=case_id, selector_id=f"NET-{ordinal:03d}"
    )
    expected_decision = AttachmentNestedTransferDecision.model_construct(
        case_id=case_id,
        answer=expected,
        rationale="Reviewed semantic answer.",
    )
    answer_value = AttachmentEdgeFilterAnswerValue(answer) if complete else None
    status = (
        AttachmentEdgeFilterDecisionStatus.COMPLETE
        if complete
        else AttachmentEdgeFilterDecisionStatus.UNCLEAR
    )
    decision = AttachmentEdgeFilterDecision.model_construct(answer=answer_value, status=status)
    observation = AttachmentNestedTransferObservation.model_construct(
        case_id=case_id,
        decision=decision,
        elapsed_milliseconds=1,
        model_identity_digest="b" * 64,
    )
    return AttachmentNestedTransferEvaluation.model_construct(
        case=case,
        expected=expected_decision,
        observation=observation,
        complete=complete,
        correct=complete and answer == expected,
    )
