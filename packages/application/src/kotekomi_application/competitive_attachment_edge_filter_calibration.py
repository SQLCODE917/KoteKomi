"""Typed CEA-1.5 probability calibration evidence and derived decisions."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentPoolArm,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentMetricSnapshot,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentCalibrationPromptArm(StrEnum):
    """One sealed CEA-1.4 prompt arm evaluated without changing its bytes."""

    V8 = "v8"
    V9 = "v9"


class AttachmentCalibrationDiagnosticOutcome(StrEnum):
    """Bounded go/no-go result before the expensive development replay."""

    CALIBRATABLE = "calibratable"
    RANKING_UNSTABLE = "ranking_unstable"
    NOT_SEPARABLE = "not_separable"
    INCONCLUSIVE = "inconclusive"


class AttachmentCalibrationOutcome(StrEnum):
    """Terminal CEA-1.5 aggregate outcome."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class AttachmentAnswerProbability(BaseModel):
    """Canonical Y/N/U probability evidence for one finite model answer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_answer_probability_v1"] = "attachment_answer_probability_v1"
    token_position: Annotated[int, Field(ge=0)]
    emitted_answer: AttachmentEdgeFilterAnswerValue
    yes_log_probability: float
    no_log_probability: float
    unclear_log_probability: float
    attachment_score: float

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        values = (
            self.yes_log_probability,
            self.no_log_probability,
            self.unclear_log_probability,
            self.attachment_score,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Attachment answer probability values must be finite.")
        if any(value > 0 for value in values[:3]):
            raise ValueError("Attachment answer log probabilities must be non-positive.")
        expected = self.yes_log_probability - _logsumexp(
            (self.no_log_probability, self.unclear_log_probability)
        )
        if not math.isclose(self.attachment_score, expected, abs_tol=1e-12):
            raise ValueError("Attachment score drifted from its Y/N/U probabilities.")
        return self


class AttachmentCalibrationObservation(BaseModel):
    """One exact Edge Filter execution plus its calibrated semantic evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibration_observation_v1"] = (
        "attachment_calibration_observation_v1"
    )
    prompt_arm: AttachmentCalibrationPromptArm
    repetition: Annotated[int, Field(ge=1)]
    task_id: Annotated[str, Field(pattern=r"^aet_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    expected_answer: Literal["Y", "N"]
    protected_positive: bool
    hard_negative: bool
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(min_length=1)]
    execution_receipt_sha256: Annotated[str, Field(pattern=_SHA256)]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    exact_model_input_sha256: Annotated[str, Field(pattern=_SHA256)]
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_sha256: Annotated[str, Field(pattern=_SHA256)]
    raw_output_text: Annotated[str, Field(min_length=1)]
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    input_token_count: Annotated[int, Field(ge=0)]
    output_token_count: Annotated[int, Field(ge=0)] | None
    probability: AttachmentAnswerProbability

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.exact_model_input.encode()).hexdigest() != (
            self.exact_model_input_sha256
        ):
            raise ValueError("Calibration observation model-input digest drifted.")
        if hashlib.sha256(self.raw_output_text.encode()).hexdigest() != self.raw_output_sha256:
            raise ValueError("Calibration observation raw-output digest drifted.")
        if self.protected_positive and self.expected_answer != "Y":
            raise ValueError("Only a Gold-positive edge can be protected.")
        if self.hard_negative and self.expected_answer != "N":
            raise ValueError("Only a Gold-negative edge can be a hard negative.")
        return self


class AttachmentBinaryMetrics(BaseModel):
    """Finite threshold metrics over occurrence-specific Pool Edges."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    true_positive_count: Annotated[int, Field(ge=0)]
    false_positive_count: Annotated[int, Field(ge=0)]
    true_negative_count: Annotated[int, Field(ge=0)]
    false_negative_count: Annotated[int, Field(ge=0)]
    sensitivity: Annotated[float, Field(ge=0, le=1)]
    specificity: Annotated[float, Field(ge=0, le=1)]
    precision: Annotated[float, Field(ge=0, le=1)]
    f1: Annotated[float, Field(ge=0, le=1)]
    accuracy: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        positive = self.true_positive_count + self.false_negative_count
        negative = self.true_negative_count + self.false_positive_count
        predicted_positive = self.true_positive_count + self.false_positive_count
        total = positive + negative
        expected = {
            "sensitivity": _ratio(self.true_positive_count, positive),
            "specificity": _ratio(self.true_negative_count, negative),
            "precision": _ratio(self.true_positive_count, predicted_positive),
            "f1": _f1(
                _ratio(self.true_positive_count, predicted_positive),
                _ratio(self.true_positive_count, positive),
            ),
            "accuracy": _ratio(self.true_positive_count + self.true_negative_count, total),
        }
        if any(
            not math.isclose(getattr(self, key), value, abs_tol=1e-12)
            for key, value in expected.items()
        ):
            raise ValueError("Attachment binary metrics drifted from their counts.")
        return self


class AttachmentExpectedExactCandidate(BaseModel):
    """One Candidate's Maximum-Pool cardinalities for feasibility modeling."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    true_edge_count: Annotated[int, Field(ge=0)]
    false_edge_count: Annotated[int, Field(ge=0)]
    missing_gold_edge_count: Annotated[int, Field(ge=0)]


class AttachmentExpectedExactProfile(BaseModel):
    """Sealed Candidate cardinalities used only as an explicit IID feasibility model."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    baseline_exact_set_accuracy: Annotated[float, Field(ge=0, le=1)]
    candidates: tuple[AttachmentExpectedExactCandidate, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.candidates:
            raise ValueError("Expected-exact profile requires Candidates.")
        identifiers = tuple(item.candidate_id for item in self.candidates)
        if tuple(sorted(identifiers)) != identifiers or len(set(identifiers)) != len(identifiers):
            raise ValueError("Expected-exact profile Candidates must be ordered and distinct.")
        return self


class AttachmentCalibrationThresholdEvaluation(BaseModel):
    """One deterministic threshold evaluated against both diagnostic repetitions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    threshold: float
    repetition_metrics: tuple[AttachmentBinaryMetrics, AttachmentBinaryMetrics]
    development_expected_exact_accuracy: tuple[float, float]
    validation_expected_exact_accuracy: tuple[float, float]
    protected_positive_retained: bool
    hard_negative_rejected: bool
    clears_break_even: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        values = (
            self.threshold,
            *self.development_expected_exact_accuracy,
            *self.validation_expected_exact_accuracy,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Attachment threshold evaluation values must be finite.")
        if any(not 0 <= value <= 1 for value in values[1:]):
            raise ValueError("Expected exact-set accuracy must be a probability.")
        return self


class AttachmentCalibrationPromptResult(BaseModel):
    """Two-repetition diagnostic result for one sealed prompt arm."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt_arm: AttachmentCalibrationPromptArm
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    observations: tuple[AttachmentCalibrationObservation, ...]
    repetition_auroc: tuple[float, float]
    repetition_average_precision: tuple[float, float]
    selected_threshold: AttachmentCalibrationThresholdEvaluation | None
    score_ranking_stable: bool
    outcome: AttachmentCalibrationDiagnosticOutcome
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.observations) != 32:
            raise ValueError("A prompt calibration result requires sixteen cases twice.")
        if {item.prompt_arm for item in self.observations} != {self.prompt_arm}:
            raise ValueError("Calibration observations contain a foreign prompt arm.")
        if {item.prompt_sha256 for item in self.observations} != {self.prompt_sha256}:
            raise ValueError("Calibration observations contain a foreign prompt digest.")
        if {item.repetition for item in self.observations} != {1, 2}:
            raise ValueError("Calibration observations require repetitions one and two.")
        for repetition in (1, 2):
            identifiers = tuple(
                item.task_id for item in self.observations if item.repetition == repetition
            )
            if len(identifiers) != 16 or len(set(identifiers)) != 16:
                raise ValueError("Each calibration repetition requires sixteen distinct task IDs.")
        if any(
            not 0 <= value <= 1
            for value in (*self.repetition_auroc, *self.repetition_average_precision)
        ):
            raise ValueError("Calibration ranking metrics must be probabilities.")
        if (self.outcome is AttachmentCalibrationDiagnosticOutcome.CALIBRATABLE) != (
            self.selected_threshold is not None
        ):
            raise ValueError("Only a calibratable prompt can select a threshold.")
        if self.result_fingerprint != _sha(
            self.model_dump(mode="json", exclude={"result_fingerprint"})
        ):
            raise ValueError("Calibration prompt result fingerprint drifted.")
        return self


class AttachmentCalibratedEdgeDecision(BaseModel):
    """Derived retention at a frozen threshold without rewriting the model answer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    model_answer: AttachmentEdgeFilterAnswerValue
    probability: AttachmentAnswerProbability
    threshold: float
    retained: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not math.isfinite(self.threshold):
            raise ValueError("Calibrated Edge threshold must be finite.")
        if self.retained != (self.probability.attachment_score >= self.threshold):
            raise ValueError("Calibrated Edge retention drifted from its threshold.")
        if self.model_answer is not self.probability.emitted_answer:
            raise ValueError("Calibrated Edge model answer drifted from probability evidence.")
        return self


class AttachmentCalibrationArmResult(BaseModel):
    """One Pool Arm measured from calibrated Edge decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    arm: AttachmentPoolArm
    edge_count: Annotated[int, Field(ge=0)]
    retained_edge_count: Annotated[int, Field(ge=0)]
    metrics: AttachmentMetricSnapshot

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.retained_edge_count > self.edge_count:
            raise ValueError("A calibrated Pool Arm cannot retain more edges than it contains.")
        return self


class AttachmentCalibrationPhaseResult(BaseModel):
    """One complete development or frozen validation calibration result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    prompt_arm: AttachmentCalibrationPromptArm
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    threshold: float
    decisions: tuple[AttachmentCalibratedEdgeDecision, ...]
    arms: tuple[AttachmentCalibrationArmResult, ...]
    baseline_name: Literal["cea13_primary"] = "cea13_primary"
    baseline_metrics: AttachmentMetricSnapshot
    selected_arm: AttachmentPoolArm
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_edges = 490 if self.phase == "development" else 257
        if len(self.decisions) != expected_edges:
            raise ValueError("Calibration phase decision inventory drifted.")
        if len({item.edge_id for item in self.decisions}) != len(self.decisions):
            raise ValueError("Calibration phase decisions must identify distinct edges.")
        if tuple(item.arm for item in self.arms) != tuple(AttachmentPoolArm):
            raise ValueError("Calibration phase requires every canonical Pool Arm.")
        if self.selected_arm not in {item.arm for item in self.arms}:
            raise ValueError("Calibration selected arm is absent.")
        if not math.isfinite(self.threshold):
            raise ValueError("Calibration phase threshold must be finite.")
        if self.result_fingerprint != _sha(
            self.model_dump(mode="json", exclude={"result_fingerprint"})
        ):
            raise ValueError("Calibration phase fingerprint drifted.")
        return self


class AttachmentCalibrationDevelopmentFreeze(BaseModel):
    """Frozen prompt, score threshold, and Pool Arm required by validation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibration_development_freeze_v1"] = (
        "attachment_calibration_development_freeze_v1"
    )
    prompt_arm: AttachmentCalibrationPromptArm
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    runtime_contract_sha256: Annotated[str, Field(pattern=_SHA256)]
    generation_parameters_sha256: Annotated[str, Field(pattern=_SHA256)]
    threshold: float
    selected_arm: AttachmentPoolArm
    development_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not math.isfinite(self.threshold):
            raise ValueError("Calibration freeze threshold must be finite.")
        if self.result_fingerprint != _sha(
            self.model_dump(mode="json", exclude={"result_fingerprint"})
        ):
            raise ValueError("Calibration development freeze fingerprint drifted.")
        return self


class AttachmentCalibrationReport(BaseModel):
    """Terminal CEA-1.5 report with diagnostic and frozen aggregate evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibration_report_v1"] = "attachment_calibration_report_v1"
    inputs: tuple[AttachmentEvidenceReference, ...]
    diagnostic: tuple[AttachmentCalibrationPromptResult, ...]
    development: AttachmentCalibrationPhaseResult
    validation: AttachmentCalibrationPhaseResult
    outcome: AttachmentCalibrationOutcome
    validation_interpretation: Literal["diagnostic_only"] = "diagnostic_only"
    production_integration: Literal["not_activated"] = "not_activated"
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.prompt_arm for item in self.diagnostic) != tuple(
            AttachmentCalibrationPromptArm
        ):
            raise ValueError("Calibration report requires both canonical prompt arms.")
        if self.development.phase != "development" or self.validation.phase != "validation":
            raise ValueError("Calibration report phase order is invalid.")
        if self.result_fingerprint != _sha(
            self.model_dump(mode="json", exclude={"result_fingerprint"})
        ):
            raise ValueError("Calibration report fingerprint drifted.")
        return self


class AttachmentCalibrationManifest(BaseModel):
    """Digest-closed evidence inventory for one terminal CEA-1.5 run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibration_manifest_v1"] = (
        "attachment_calibration_manifest_v1"
    )
    tdd: AttachmentEvidenceReference
    inputs: tuple[AttachmentEvidenceReference, ...]
    outputs: tuple[AttachmentEvidenceReference, ...]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (("inputs", self.inputs), ("outputs", self.outputs)):
            labels = tuple(item.label for item in values)
            if labels != tuple(sorted(labels)) or len(set(labels)) != len(labels):
                raise ValueError(f"Calibration manifest {label} must be ordered and distinct.")
        return self


class AttachmentCalibrationStatus(BaseModel):
    """Terminal machine-readable CEA-1.5 status."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibration_status_v1"] = "attachment_calibration_status_v1"
    status: Literal["complete"] = "complete"
    outcome: AttachmentCalibrationOutcome
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    report_path: Annotated[str, Field(min_length=1)]
    review_path: Annotated[str, Field(min_length=1)]
    summary_path: Annotated[str, Field(min_length=1)]
    handoff_path: Annotated[str, Field(min_length=1)]


def attachment_calibration_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one calibration DTO draft."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _logsumexp(values: tuple[float, ...]) -> float:
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
