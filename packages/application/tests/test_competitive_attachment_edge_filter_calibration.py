from __future__ import annotations

import math

import pytest
from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentCalibratedEdgeDecision,
    AttachmentCalibrationDevelopmentFreeze,
    AttachmentCalibrationPromptArm,
    AttachmentEdgeFilterAnswerValue,
    AttachmentPoolArm,
    ModelOutputTokenProbability,
    ModelTokenAlternative,
    attachment_calibration_fingerprint,
    model_execution_receipt_from_payload,
)


def test_probability_contract_preserves_model_answer_and_calibrated_decision() -> None:
    no_or_unclear = _logsumexp((-2.0, -3.0))
    probability = AttachmentAnswerProbability(
        token_position=0,
        emitted_answer=AttachmentEdgeFilterAnswerValue.YES,
        yes_log_probability=-0.1,
        no_log_probability=-2.0,
        unclear_log_probability=-3.0,
        attachment_score=-0.1 - no_or_unclear,
    )

    decision = AttachmentCalibratedEdgeDecision(
        edge_id="ape_" + "1" * 24,
        model_answer=AttachmentEdgeFilterAnswerValue.YES,
        probability=probability,
        threshold=2.0,
        retained=False,
    )

    assert decision.model_answer is AttachmentEdgeFilterAnswerValue.YES
    assert decision.retained is False


def test_output_token_probability_rejects_missing_emitted_alternative() -> None:
    with pytest.raises(ValueError, match="emitted model token"):
        ModelOutputTokenProbability(
            position=0,
            token="Y",
            log_probability=-0.1,
            token_bytes=(89,),
            alternatives=(ModelTokenAlternative("N", -0.2, (78,)),),
        )


def test_output_token_probability_rejects_mismatched_emitted_probability() -> None:
    with pytest.raises(ValueError, match="must match its alternative"):
        ModelOutputTokenProbability(
            position=0,
            token="Y",
            log_probability=-0.1,
            token_bytes=(89,),
            alternatives=(ModelTokenAlternative("Y", -0.2, (89,)),),
        )


def test_persisted_probability_evidence_rejects_foreign_fields() -> None:
    with pytest.raises(ValueError, match="invalid shape"):
        model_execution_receipt_from_payload(
            {
                "model_identity_digest": "1" * 64,
                "generation_parameters_digest": "2" * 64,
                "rendered_input_digest": "3" * 64,
                "input_token_count": 10,
                "output_token_count": 1,
                "output_token_probabilities": [
                    {
                        "position": 0,
                        "token": "Y",
                        "log_probability": -0.1,
                        "token_bytes": [89],
                        "alternatives": [
                            {
                                "token": "Y",
                                "log_probability": -0.1,
                                "token_bytes": [89],
                            }
                        ],
                        "foreign": True,
                    }
                ],
            }
        )


def test_development_freeze_rejects_a_foreign_fingerprint() -> None:
    with pytest.raises(ValueError, match="freeze fingerprint drifted"):
        AttachmentCalibrationDevelopmentFreeze(
            prompt_arm=AttachmentCalibrationPromptArm.V8,
            prompt_sha256="1" * 64,
            runtime_contract_sha256="2" * 64,
            generation_parameters_sha256="3" * 64,
            threshold=0.25,
            selected_arm=AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT,
            development_report_sha256="4" * 64,
            result_fingerprint="5" * 64,
        )


def test_development_freeze_accepts_its_canonical_fingerprint() -> None:
    draft = AttachmentCalibrationDevelopmentFreeze.model_construct(
        prompt_arm=AttachmentCalibrationPromptArm.V8,
        prompt_sha256="1" * 64,
        runtime_contract_sha256="2" * 64,
        generation_parameters_sha256="3" * 64,
        threshold=0.25,
        selected_arm=AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT,
        development_report_sha256="4" * 64,
        result_fingerprint="0" * 64,
    )

    result = AttachmentCalibrationDevelopmentFreeze(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_calibration_fingerprint(draft),
    )

    assert result.result_fingerprint == attachment_calibration_fingerprint(draft)


def _logsumexp(values: tuple[float, ...]) -> float:
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))
