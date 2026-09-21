"""Typed evidence for the CEA-1.10 finite answer format experiment."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from statistics import median
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_candidate_remainder import (
    AttachmentCandidateRemainderArm,
)
from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentAnswerFormatArm(StrEnum):
    """One demonstration answer format in CEA-1.10."""

    LABELED = "labeled"
    BARE = "bare"


class AttachmentAnswerFormatOutcome(StrEnum):
    """Terminal causal result for CEA-1.10."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentAnswerFormatPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.10 package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentFiniteLabelEvidence(BaseModel):
    """First-position finite-label evidence independent of raw-output validity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_finite_label_evidence_v1"] = (
        "attachment_finite_label_evidence_v1"
    )
    token_position: Literal[0] = 0
    emitted_token: Annotated[str, Field(min_length=1)]
    emitted_log_probability: Annotated[float, Field(le=0)]
    yes_log_probability: Annotated[float, Field(le=0)]
    no_log_probability: Annotated[float, Field(le=0)]
    unclear_log_probability: Annotated[float, Field(le=0)]
    finite_label_argmax: AttachmentEdgeFilterAnswerValue
    attachment_score: float
    answer_label_observed: bool
    answer_label_log_probability: Annotated[float, Field(le=0)] | None
    lowest_alternative_log_probability: Annotated[float, Field(le=0)]
    conservative_answer_log_probability: Annotated[float, Field(le=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        values = (
            self.emitted_log_probability,
            self.yes_log_probability,
            self.no_log_probability,
            self.unclear_log_probability,
            self.attachment_score,
            self.lowest_alternative_log_probability,
            self.conservative_answer_log_probability,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Finite Label Evidence requires finite probabilities.")
        labels = {
            AttachmentEdgeFilterAnswerValue.YES: self.yes_log_probability,
            AttachmentEdgeFilterAnswerValue.NO: self.no_log_probability,
            AttachmentEdgeFilterAnswerValue.UNCLEAR: self.unclear_log_probability,
        }
        expected_argmax = max(labels, key=lambda item: (labels[item], -tuple(labels).index(item)))
        if self.finite_label_argmax is not expected_argmax:
            raise ValueError("Finite Label Argmax drifted from its probabilities.")
        expected_score = self.yes_log_probability - _logsumexp(
            (self.no_log_probability, self.unclear_log_probability)
        )
        if not math.isclose(self.attachment_score, expected_score, abs_tol=1e-12):
            raise ValueError("Finite Label Attachment Score drifted.")
        if self.answer_label_observed != (self.answer_label_log_probability is not None):
            raise ValueError("Answer Label observation state drifted.")
        expected_conservative = (
            self.answer_label_log_probability
            if self.answer_label_log_probability is not None
            else self.lowest_alternative_log_probability
        )
        if not math.isclose(
            self.conservative_answer_log_probability,
            expected_conservative,
            abs_tol=1e-12,
        ):
            raise ValueError("Conservative Answer Log Probability drifted.")
        return self


class AttachmentArchivedFiniteLabelObservation(BaseModel):
    """Recovered diagnostic evidence from one sealed CEA-1.9 execution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_archived_finite_label_observation_v1"] = (
        "attachment_archived_finite_label_observation_v1"
    )
    arm: AttachmentCandidateRemainderArm
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    execution_record: AttachmentEvidenceReference
    observed_answer: AttachmentEdgeFilterAnswerValue | None
    raw_output_text: str
    finite_label_evidence: AttachmentFiniteLabelEvidence
    sealed_attachment_score: float | None
    sealed_score_matches: bool | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (self.sealed_attachment_score is None) != (self.sealed_score_matches is None):
            raise ValueError("Archived sealed-score comparison state drifted.")
        if self.sealed_attachment_score is not None:
            matches = math.isclose(
                self.sealed_attachment_score,
                self.finite_label_evidence.attachment_score,
                abs_tol=1e-12,
            )
            if self.sealed_score_matches != matches:
                raise ValueError("Archived sealed-score comparison drifted.")
        return self


class AttachmentFiniteLabelRecoveryReport(BaseModel):
    """Model-free recovery over all sealed CEA-1.9 receipts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_finite_label_recovery_report_v1"] = (
        "attachment_finite_label_recovery_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    observations: tuple[AttachmentArchivedFiniteLabelObservation, ...]
    finite_label_evidence_count: Literal[20] = 20
    sealed_score_comparison_count: Literal[18] = 18
    sealed_score_match_count: Literal[18] = 18
    invalid_observed_answer_count: Literal[2] = 2
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        keys = tuple((item.task_id, item.arm) for item in self.observations)
        if len(keys) != 20 or keys != tuple(sorted(set(keys))):
            raise ValueError("Finite-label recovery requires twenty ordered observations.")
        comparisons = tuple(
            item for item in self.observations if item.sealed_score_matches is not None
        )
        if len(comparisons) != self.sealed_score_comparison_count:
            raise ValueError("Finite-label sealed-score comparison count drifted.")
        if sum(item.sealed_score_matches is True for item in comparisons) != (
            self.sealed_score_match_count
        ):
            raise ValueError("Finite-label sealed-score match count drifted.")
        if sum(item.observed_answer is None for item in self.observations) != (
            self.invalid_observed_answer_count
        ):
            raise ValueError("Finite-label invalid-answer count drifted.")
        if self.result_fingerprint != attachment_answer_format_fingerprint(self):
            raise ValueError("Finite-label recovery fingerprint drifted.")
        return self


class AttachmentAnswerFormatPreflight(BaseModel):
    """Sealed tasks, prompts, and settings for CEA-1.10."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_answer_format_preflight_v1"] = (
        "attachment_answer_format_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    labeled_prompt: AttachmentEvidenceReference
    bare_prompt: AttachmentEvidenceReference
    tasks: tuple[AttachmentResidualOwnershipTask, ...]
    configured_max_output_tokens: Annotated[int, Field(ge=8)]
    effective_max_output_tokens: Literal[8] = 8
    seed: Literal[17] = 17
    temperature: Annotated[float, Field(ge=0.0, le=0.0)] = 0.0
    top_logprobs: Literal[10] = 10
    disputed_gold_task_ids: tuple[Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")], ...]
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        labels = tuple(item.label for item in self.inputs)
        if labels != tuple(sorted(set(labels))):
            raise ValueError("Answer Format inputs must be ordered and distinct.")
        task_ids = tuple(item.id for item in self.tasks)
        if len(task_ids) != 10 or task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Answer Format preflight requires ten ordered tasks.")
        if self.labeled_prompt.sha256 == self.bare_prompt.sha256:
            raise ValueError("Answer Format prompts must differ.")
        if tuple(sorted(set(self.disputed_gold_task_ids))) != self.disputed_gold_task_ids:
            raise ValueError("Disputed Gold task IDs must be ordered and distinct.")
        if not set(self.disputed_gold_task_ids).issubset(task_ids):
            raise ValueError("Disputed Gold task IDs must reference prepared tasks.")
        if self.result_fingerprint != attachment_answer_format_fingerprint(self):
            raise ValueError("Answer Format preflight fingerprint drifted.")
        return self


class AttachmentAnswerFormatObservation(BaseModel):
    """One live format-arm result for one occurrence-specific task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_answer_format_observation_v1"] = (
        "attachment_answer_format_observation_v1"
    )
    arm: AttachmentAnswerFormatArm
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    decision: AttachmentEdgeFilterDecision
    finite_label_evidence: AttachmentFiniteLabelEvidence | None
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)] | None
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: str | None
    output_token_count: Annotated[int, Field(ge=0)] | None
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    strict_valid_output: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision.edge_id != self.edge_id:
            raise ValueError("Answer Format decision references a foreign Edge.")
        valid = (
            self.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and self.decision.answer is not None
        )
        if self.strict_valid_output != valid:
            raise ValueError("Answer Format strict validity drifted.")
        if (self.finite_label_evidence is None) != (self.model_identity_digest is None):
            raise ValueError("Answer Format probability identity evidence drifted.")
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Answer Format raw output text is missing.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Answer Format raw output digest drifted.")
        return self


class AttachmentAnswerFormatCase(BaseModel):
    """Paired Labeled and Bare observations for one exact task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_answer_format_case_v1"] = "attachment_answer_format_case_v1"
    task: AttachmentResidualOwnershipTask
    labeled: AttachmentAnswerFormatObservation
    bare: AttachmentAnswerFormatObservation
    finite_label_argmax_agrees: bool
    strict_validity_improved: bool
    answer_pressure_delta_upper_bound: float | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            self.labeled.arm is not AttachmentAnswerFormatArm.LABELED
            or self.bare.arm is not AttachmentAnswerFormatArm.BARE
        ):
            raise ValueError("Answer Format case arm order drifted.")
        if any(
            item.task_id != self.task.id or item.edge_id != self.task.edge_filter_task.edge.id
            for item in (self.labeled, self.bare)
        ):
            raise ValueError("Answer Format observation drifted from its task.")
        labeled_evidence = self.labeled.finite_label_evidence
        bare_evidence = self.bare.finite_label_evidence
        agrees = (
            labeled_evidence is not None
            and bare_evidence is not None
            and labeled_evidence.finite_label_argmax is bare_evidence.finite_label_argmax
        )
        if self.finite_label_argmax_agrees != agrees:
            raise ValueError("Answer Format argmax agreement drifted.")
        improved = not self.labeled.strict_valid_output and self.bare.strict_valid_output
        if self.strict_validity_improved != improved:
            raise ValueError("Answer Format strict-validity improvement drifted.")
        delta = (
            bare_evidence.conservative_answer_log_probability
            - labeled_evidence.conservative_answer_log_probability
            if labeled_evidence is not None and bare_evidence is not None
            else None
        )
        if not _optional_close(self.answer_pressure_delta_upper_bound, delta):
            raise ValueError("Answer Format pressure delta drifted.")
        return self


class AttachmentAnswerFormatReport(BaseModel):
    """Terminal CEA-1.10 format-effect report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_answer_format_report_v1"] = (
        "attachment_answer_format_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    labeled_prompt: AttachmentEvidenceReference
    bare_prompt: AttachmentEvidenceReference
    disputed_gold_task_ids: tuple[str, ...]
    cases: tuple[AttachmentAnswerFormatCase, ...]
    probability_evidence_count: Annotated[int, Field(ge=0, le=20)]
    labeled_valid_output_count: Annotated[int, Field(ge=0, le=10)]
    bare_valid_output_count: Annotated[int, Field(ge=0, le=10)]
    labeled_answer_first_token_count: Annotated[int, Field(ge=0, le=10)]
    bare_answer_first_token_count: Annotated[int, Field(ge=0, le=10)]
    finite_label_argmax_agreement_count: Annotated[int, Field(ge=0, le=10)]
    strict_validity_improvement_count: Annotated[int, Field(ge=0, le=10)]
    answer_pressure_comparison_count: Annotated[int, Field(ge=0, le=10)]
    median_answer_pressure_delta_upper_bound: float | None
    outcome: AttachmentAnswerFormatOutcome
    model_execution_count: Literal[20] = 20
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        task_ids = tuple(item.task.id for item in self.cases)
        if len(task_ids) != 10 or task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Answer Format report requires ten ordered cases.")
        evidence_count = sum(
            item.finite_label_evidence is not None
            for case in self.cases
            for item in (case.labeled, case.bare)
        )
        labeled_valid = sum(item.labeled.strict_valid_output for item in self.cases)
        bare_valid = sum(item.bare.strict_valid_output for item in self.cases)
        labeled_answer = sum(_starts_with_answer(item.labeled) for item in self.cases)
        bare_answer = sum(_starts_with_answer(item.bare) for item in self.cases)
        agreements = sum(item.finite_label_argmax_agrees for item in self.cases)
        improvements = sum(item.strict_validity_improved for item in self.cases)
        pressure_comparisons = sum(
            item.answer_pressure_delta_upper_bound is not None for item in self.cases
        )
        recorded = (
            self.probability_evidence_count,
            self.labeled_valid_output_count,
            self.bare_valid_output_count,
            self.labeled_answer_first_token_count,
            self.bare_answer_first_token_count,
            self.finite_label_argmax_agreement_count,
            self.strict_validity_improvement_count,
            self.answer_pressure_comparison_count,
        )
        expected = (
            evidence_count,
            labeled_valid,
            bare_valid,
            labeled_answer,
            bare_answer,
            agreements,
            improvements,
            pressure_comparisons,
        )
        if recorded != expected:
            raise ValueError("Answer Format report counts drifted.")
        deltas = tuple(
            item.answer_pressure_delta_upper_bound
            for item in self.cases
            if item.answer_pressure_delta_upper_bound is not None
        )
        expected_median = median(deltas) if pressure_comparisons == 10 else None
        if not _optional_close(self.median_answer_pressure_delta_upper_bound, expected_median):
            raise ValueError("Answer Format median pressure delta drifted.")
        complete = evidence_count == 20 and pressure_comparisons == 10
        if not complete:
            expected_outcome = AttachmentAnswerFormatOutcome.INCONCLUSIVE
        elif (
            bare_valid == 10
            and bare_answer == 0
            and labeled_answer >= 1
            and expected_median is not None
            and expected_median <= -5.0
            and agreements >= 9
        ):
            expected_outcome = AttachmentAnswerFormatOutcome.SUPPORTED
        elif bare_valid > labeled_valid:
            expected_outcome = AttachmentAnswerFormatOutcome.MIXED
        else:
            expected_outcome = AttachmentAnswerFormatOutcome.FALSIFIED
        if self.outcome is not expected_outcome:
            raise ValueError("Answer Format outcome drifted from its evidence.")
        if self.result_fingerprint != attachment_answer_format_fingerprint(self):
            raise ValueError("Answer Format report fingerprint drifted.")
        return self


class AttachmentAnswerFormatStatus(BaseModel):
    """Machine-readable state for one CEA-1.10 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_answer_format_status_v1"] = (
        "attachment_answer_format_status_v1"
    )
    status: AttachmentAnswerFormatPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    recovery_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentAnswerFormatOutcome | None
    model_execution_count: Annotated[int, Field(ge=0, le=20)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentAnswerFormatPackageStatus.COMPLETE
        terminal = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete Answer Format status requires terminal paths.")
        if complete != (self.model_execution_count == 20):
            raise ValueError("Answer Format status execution count drifted.")
        return self


def attachment_answer_format_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.10 DTO draft."""
    encoded = json.dumps(
        value.model_dump(mode="json", exclude={"result_fingerprint"}),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _starts_with_answer(observation: AttachmentAnswerFormatObservation) -> bool:
    evidence = observation.finite_label_evidence
    return evidence is not None and evidence.emitted_token.strip() == "Answer"


def _optional_close(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(left, right, abs_tol=1e-12)


def _logsumexp(values: tuple[float, ...]) -> float:
    maximum = max(values)
    return maximum + math.log(sum(math.exp(item - maximum) for item in values))
