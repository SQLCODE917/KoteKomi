from __future__ import annotations

import hashlib
import math
from typing import Literal

import pytest
from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentCalibrationArmResult,
    AttachmentCalibrationDiagnosticOutcome,
    AttachmentCalibrationObservation,
    AttachmentCalibrationOutcome,
    AttachmentCalibrationPhaseResult,
    AttachmentCalibrationPromptArm,
    AttachmentEdgeFilterAnswerValue,
    AttachmentExpectedExactCandidate,
    AttachmentExpectedExactProfile,
    AttachmentMetricSnapshot,
    AttachmentPoolArm,
    ModelExecutionReceipt,
    ModelOutputTokenProbability,
    ModelTokenAlternative,
)
from kotekomi_pipelines.competitive_attachment_edge_filter_calibration import (
    attachment_answer_probability,
    attachment_calibration_outcome,
    build_calibration_prompt_result,
    expected_exact_set_accuracy,
)


def test_runtime_alternatives_become_one_auditable_attachment_score() -> None:
    receipt = ModelExecutionReceipt(
        model_identity_digest="1" * 64,
        generation_parameters_digest="2" * 64,
        rendered_input_digest="3" * 64,
        input_token_count=10,
        output_token_count=1,
        output_token_probabilities=(
            ModelOutputTokenProbability(
                position=0,
                token="Y",
                log_probability=-0.1,
                token_bytes=(89,),
                alternatives=(
                    ModelTokenAlternative("Y", -0.1, (89,)),
                    ModelTokenAlternative("N", -2.0, (78,)),
                    ModelTokenAlternative("U", -3.0, (85,)),
                ),
            ),
        ),
    )

    result = attachment_answer_probability(
        receipt,
        emitted_answer=AttachmentEdgeFilterAnswerValue.YES,
    )

    assert math.isclose(
        sum(
            math.exp(value)
            for value in (
                result.yes_log_probability,
                result.no_log_probability,
                result.unclear_log_probability,
            )
        ),
        1.0,
        abs_tol=1e-12,
    )
    assert result.yes_log_probability < -0.1
    assert result.attachment_score > 1.0


def test_rounded_winner_and_same_answer_variants_are_conditionally_normalized() -> None:
    receipt = ModelExecutionReceipt(
        model_identity_digest="1" * 64,
        generation_parameters_digest="2" * 64,
        rendered_input_digest="3" * 64,
        input_token_count=10,
        output_token_count=1,
        output_token_probabilities=(
            ModelOutputTokenProbability(
                position=0,
                token="Y",
                log_probability=0.0,
                token_bytes=(89,),
                alternatives=(
                    ModelTokenAlternative("Y", 0.0, (89,)),
                    ModelTokenAlternative("U", -14.0, (85,)),
                    ModelTokenAlternative("N", -15.0, (78,)),
                    ModelTokenAlternative("\tY", -18.0, (9, 89)),
                ),
            ),
        ),
    )

    result = attachment_answer_probability(
        receipt,
        emitted_answer=AttachmentEdgeFilterAnswerValue.YES,
    )

    assert result.yes_log_probability <= 0
    assert result.no_log_probability <= 0
    assert result.unclear_log_probability <= 0
    assert math.isclose(
        sum(
            math.exp(value)
            for value in (
                result.yes_log_probability,
                result.no_log_probability,
                result.unclear_log_probability,
            )
        ),
        1.0,
        abs_tol=1e-12,
    )
    assert result.attachment_score > 10


def test_stable_safe_scores_clear_the_break_even_gate() -> None:
    observations = tuple(
        _observation(
            index=index,
            repetition=repetition,
            expected="Y" if index < 8 else "N",
            score=1.0 if index < 8 else -1.0,
            protected=index == 0,
            hard_negative=index == 8,
            prompt_arm=AttachmentCalibrationPromptArm.V8,
        )
        for repetition in (1, 2)
        for index in range(16)
    )
    development = _profile("development", baseline=0.5)
    validation = _profile("validation", baseline=0.5)

    result = build_calibration_prompt_result(
        prompt_arm=AttachmentCalibrationPromptArm.V8,
        prompt_sha256="4" * 64,
        observations=observations,
        development_profile=development,
        validation_profile=validation,
    )

    assert result.outcome is AttachmentCalibrationDiagnosticOutcome.CALIBRATABLE
    assert result.selected_threshold is not None
    assert result.selected_threshold.clears_break_even is True
    assert result.repetition_auroc == (1.0, 1.0)


def test_protected_positive_below_hard_negative_blocks_replay() -> None:
    observations = tuple(
        _observation(
            index=index,
            repetition=repetition,
            expected="Y" if index < 8 else "N",
            score=(-2.0 if index == 0 else 1.0 if index < 8 else 2.0 if index == 8 else -1.0),
            protected=index == 0,
            hard_negative=index == 8,
            prompt_arm=AttachmentCalibrationPromptArm.V9,
        )
        for repetition in (1, 2)
        for index in range(16)
    )

    result = build_calibration_prompt_result(
        prompt_arm=AttachmentCalibrationPromptArm.V9,
        prompt_sha256="5" * 64,
        observations=observations,
        development_profile=_profile("development", baseline=0.5),
        validation_profile=_profile("validation", baseline=0.5),
    )

    assert result.outcome is AttachmentCalibrationDiagnosticOutcome.NOT_SEPARABLE
    assert result.selected_threshold is None


def test_changed_cross_class_ordering_is_ranking_unstable() -> None:
    observations = tuple(
        _observation(
            index=index,
            repetition=repetition,
            expected="Y" if index < 8 else "N",
            score=(
                -2.0
                if repetition == 2 and index == 0
                else 2.0
                if repetition == 2 and index == 8
                else 1.0
                if index < 8
                else -1.0
            ),
            protected=index == 0,
            hard_negative=index == 8,
            prompt_arm=AttachmentCalibrationPromptArm.V9,
        )
        for repetition in (1, 2)
        for index in range(16)
    )

    result = build_calibration_prompt_result(
        prompt_arm=AttachmentCalibrationPromptArm.V9,
        prompt_sha256="5" * 64,
        observations=observations,
        development_profile=_profile("development", baseline=0.5),
        validation_profile=_profile("validation", baseline=0.5),
    )

    assert result.score_ranking_stable is False
    assert result.outcome is AttachmentCalibrationDiagnosticOutcome.RANKING_UNSTABLE
    assert result.selected_threshold is None


def test_safe_scores_below_break_even_are_inconclusive() -> None:
    observations = tuple(
        _observation(
            index=index,
            repetition=repetition,
            expected="Y" if index < 8 else "N",
            score=(2.0 if index == 0 else -1.0 if index < 8 else -2.0 if index == 8 else 1.0),
            protected=index == 0,
            hard_negative=index == 8,
            prompt_arm=AttachmentCalibrationPromptArm.V9,
        )
        for repetition in (1, 2)
        for index in range(16)
    )

    result = build_calibration_prompt_result(
        prompt_arm=AttachmentCalibrationPromptArm.V9,
        prompt_sha256="5" * 64,
        observations=observations,
        development_profile=_profile("development", baseline=0.99),
        validation_profile=_profile("validation", baseline=0.99),
    )

    assert result.outcome is AttachmentCalibrationDiagnosticOutcome.INCONCLUSIVE
    assert result.selected_threshold is None


def test_expected_exact_model_keeps_pool_gaps_at_zero_probability() -> None:
    profile = AttachmentExpectedExactProfile(
        phase="development",
        baseline_exact_set_accuracy=0.5,
        candidates=(
            AttachmentExpectedExactCandidate(
                candidate_id="cac_" + "1" * 24,
                true_edge_count=1,
                false_edge_count=1,
                missing_gold_edge_count=0,
            ),
            AttachmentExpectedExactCandidate(
                candidate_id="cac_" + "2" * 24,
                true_edge_count=0,
                false_edge_count=0,
                missing_gold_edge_count=1,
            ),
        ),
    )

    result = expected_exact_set_accuracy(profile, sensitivity=0.8, specificity=0.9)
    assert math.isclose(result, 0.36, abs_tol=1e-12)


def test_terminal_outcome_requires_frozen_improvement_in_both_phases() -> None:
    development = _phase(
        phase="development",
        baseline=_metrics(exact=0.6, precision=0.7, leakage=10),
        calibrated=_metrics(exact=0.7, precision=0.8, leakage=8),
    )
    validation = _phase(
        phase="validation",
        baseline=_metrics(exact=0.5, precision=0.6, leakage=12),
        calibrated=_metrics(exact=0.65, precision=0.75, leakage=9),
    )

    assert (
        attachment_calibration_outcome(development, validation)
        is AttachmentCalibrationOutcome.SUPPORTED
    )


def test_terminal_outcome_is_mixed_when_validation_does_not_improve() -> None:
    development = _phase(
        phase="development",
        baseline=_metrics(exact=0.6, precision=0.7, leakage=10),
        calibrated=_metrics(exact=0.7, precision=0.8, leakage=8),
    )
    validation = _phase(
        phase="validation",
        baseline=_metrics(exact=0.6, precision=0.7, leakage=10),
        calibrated=_metrics(exact=0.6, precision=0.65, leakage=10),
    )

    assert (
        attachment_calibration_outcome(development, validation)
        is AttachmentCalibrationOutcome.MIXED
    )


def test_terminal_outcome_rejects_validation_threshold_drift() -> None:
    baseline = _metrics(exact=0.6, precision=0.7, leakage=10)
    development = _phase(phase="development", baseline=baseline, calibrated=baseline)
    validation = _phase(
        phase="validation",
        baseline=baseline,
        calibrated=baseline,
        threshold=0.5,
    )

    with pytest.raises(ValueError, match="frozen contract"):
        attachment_calibration_outcome(development, validation)


def _observation(
    *,
    index: int,
    repetition: int,
    expected: Literal["Y", "N"],
    score: float,
    protected: bool,
    hard_negative: bool,
    prompt_arm: AttachmentCalibrationPromptArm,
) -> AttachmentCalibrationObservation:
    exact_model_input = "exact model input"
    raw_output_text = expected
    no = -4.0
    unclear = -5.0
    denominator = _logsumexp((no, unclear))
    yes = score + denominator
    return AttachmentCalibrationObservation(
        prompt_arm=prompt_arm,
        repetition=repetition,
        task_id=f"aet_{index + 1:024x}",
        edge_id=f"ape_{index + 1:024x}",
        expected_answer=expected,
        protected_positive=protected,
        hard_negative=hard_negative,
        extraction_task_id=f"ext_{index}",
        model_run_id=f"mrn_{index}",
        trace_id=f"xst_{index}",
        execution_receipt_sha256="7" * 64,
        prompt_sha256=("4" if prompt_arm is AttachmentCalibrationPromptArm.V8 else "5") * 64,
        exact_model_input_sha256=hashlib.sha256(exact_model_input.encode()).hexdigest(),
        exact_model_input=exact_model_input,
        raw_output_sha256=hashlib.sha256(raw_output_text.encode()).hexdigest(),
        raw_output_text=raw_output_text,
        elapsed_milliseconds=10,
        input_token_count=100,
        output_token_count=1,
        probability=AttachmentAnswerProbability(
            token_position=0,
            emitted_answer=(
                AttachmentEdgeFilterAnswerValue.YES
                if expected == "Y"
                else AttachmentEdgeFilterAnswerValue.NO
            ),
            yes_log_probability=yes,
            no_log_probability=no,
            unclear_log_probability=unclear,
            attachment_score=score,
        ),
    )


def _profile(
    phase: Literal["development", "validation"],
    *,
    baseline: float,
) -> AttachmentExpectedExactProfile:
    return AttachmentExpectedExactProfile(
        phase=phase,
        baseline_exact_set_accuracy=baseline,
        candidates=tuple(
            AttachmentExpectedExactCandidate(
                candidate_id=f"cac_{index + 1:024x}",
                true_edge_count=1,
                false_edge_count=1,
                missing_gold_edge_count=0,
            )
            for index in range(16)
        ),
    )


def _phase(
    *,
    phase: Literal["development", "validation"],
    baseline: AttachmentMetricSnapshot,
    calibrated: AttachmentMetricSnapshot,
    threshold: float = 0.25,
) -> AttachmentCalibrationPhaseResult:
    selected_arm = AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT
    arms = tuple(
        AttachmentCalibrationArmResult(
            arm=arm,
            edge_count=10,
            retained_edge_count=5,
            metrics=calibrated,
        )
        for arm in AttachmentPoolArm
    )
    return AttachmentCalibrationPhaseResult.model_construct(
        phase=phase,
        prompt_arm=AttachmentCalibrationPromptArm.V8,
        prompt_sha256="4" * 64,
        threshold=threshold,
        decisions=(),
        arms=arms,
        baseline_name="cea13_primary",
        baseline_metrics=baseline,
        selected_arm=selected_arm,
        result_fingerprint="0" * 64,
    )


def _metrics(*, exact: float, precision: float, leakage: int) -> AttachmentMetricSnapshot:
    return AttachmentMetricSnapshot(
        candidate_count=10,
        event_count=2,
        exact_set_count=int(exact * 10),
        exact_set_accuracy=exact,
        true_positive_edge_count=8,
        false_positive_edge_count=2,
        false_negative_edge_count=2,
        edge_precision=precision,
        edge_recall=0.8,
        edge_f1=0.8,
        sibling_event_leakage_count=leakage,
        shared_gold_edge_count=2,
        shared_matched_edge_count=2,
        shared_fragment_recall=1.0,
        none_case_count=1,
        none_correct_count=1,
        none_accuracy=1.0,
        exact_event_count=1,
        character_precision=0.8,
        character_recall=0.8,
        character_f1=0.8,
        entity_gold_edge_count=2,
        entity_matched_edge_count=2,
        entity_recall=1.0,
        qualification_gold_edge_count=2,
        qualification_matched_edge_count=2,
        qualification_recall=1.0,
        anchor_gap_count=0,
    )


def _logsumexp(values: tuple[float, ...]) -> float:
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))
