"""Typed evidence for the CEA-1.9 explicit Candidate Remainder experiment."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from statistics import median
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
)
from kotekomi_application.competitive_attachment_edge_filter_calibration import (
    AttachmentAnswerProbability,
)
from kotekomi_application.competitive_attachment_residual_cue_ablation import (
    AttachmentResidualGoldAdjudication,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentCandidateRemainderArm(StrEnum):
    """One task contract in the paired CEA-1.9 experiment."""

    BASELINE = "baseline"
    REMAINDER = "remainder"


class AttachmentCandidateRemainderOutcome(StrEnum):
    """Terminal causal result for the paired Candidate Remainder experiment."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentCandidateRemainderPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.9 evidence package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentCandidateRemainderPreflight(BaseModel):
    """Sealed tasks, prompts, and runtime settings for CEA-1.9."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_remainder_preflight_v1"] = (
        "attachment_candidate_remainder_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    baseline_prompt: AttachmentEvidenceReference
    remainder_prompt: AttachmentEvidenceReference
    tasks: tuple[AttachmentResidualOwnershipTask, ...]
    gold_adjudications: tuple[AttachmentResidualGoldAdjudication, ...]
    configured_max_output_tokens: Annotated[int, Field(ge=3)]
    effective_max_output_tokens: Literal[3] = 3
    seed: Literal[17] = 17
    temperature: Annotated[float, Field(ge=0.0, le=0.0)] = 0.0
    top_logprobs: Literal[10] = 10
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        labels = tuple(item.label for item in self.inputs)
        if labels != tuple(sorted(set(labels))):
            raise ValueError("Candidate Remainder inputs must be ordered and distinct.")
        identifiers = tuple(item.id for item in self.tasks)
        if len(identifiers) != 10 or identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("Candidate Remainder preflight requires ten ordered tasks.")
        if self.baseline_prompt.sha256 == self.remainder_prompt.sha256:
            raise ValueError("Candidate Remainder prompts must differ.")
        if len(self.gold_adjudications) != 1:
            raise ValueError("Candidate Remainder preflight requires one Gold adjudication.")
        task_by_id = {item.id: item for item in self.tasks}
        for adjudication in self.gold_adjudications:
            task = task_by_id.get(adjudication.task_id)
            if task is None or task.edge_filter_task.edge.id != adjudication.edge_id:
                raise ValueError("Candidate Remainder Gold adjudication references foreign input.")
            if (
                task.edge_filter_task.edge.candidate_range != adjudication.candidate_range
                or task.edge_filter_task.edge.event_range != adjudication.target_event_range
            ):
                raise ValueError("Candidate Remainder Gold adjudication range drifted.")
        if self.result_fingerprint != attachment_candidate_remainder_fingerprint(self):
            raise ValueError("Candidate Remainder preflight fingerprint drifted.")
        return self


class AttachmentCandidateRemainderObservation(BaseModel):
    """One arm result for one occurrence-specific Residual Ownership task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_remainder_observation_v1"] = (
        "attachment_candidate_remainder_observation_v1"
    )
    arm: AttachmentCandidateRemainderArm
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    expected_answer: Literal["Y", "N"]
    decision: AttachmentEdgeFilterDecision
    probability: AttachmentAnswerProbability | None
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)] | None
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: str | None
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision.edge_id != self.edge_id:
            raise ValueError("Candidate Remainder decision references a foreign Edge.")
        actual = (
            self.decision.answer.value
            if self.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and self.decision.answer is not None
            else None
        )
        if self.passed != (actual == self.expected_answer):
            raise ValueError("Candidate Remainder observation result drifted.")
        if self.probability is not None and self.probability.emitted_answer is not (
            self.decision.answer
        ):
            raise ValueError("Candidate Remainder probability answer drifted.")
        if (self.probability is None) != (self.model_identity_digest is None):
            raise ValueError("Candidate Remainder probability identity evidence drifted.")
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Candidate Remainder raw output text is missing.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Candidate Remainder raw output digest drifted.")
        return self


class AttachmentCandidateRemainderCase(BaseModel):
    """Paired Baseline and Remainder observations for one exact task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_remainder_case_v1"] = (
        "attachment_candidate_remainder_case_v1"
    )
    task: AttachmentResidualOwnershipTask
    inherited_expected_answer: Literal["Y", "N"]
    expected_answer: Literal["Y", "N"]
    baseline: AttachmentCandidateRemainderObservation
    remainder: AttachmentCandidateRemainderObservation
    baseline_attachment_score: float | None
    remainder_attachment_score: float | None
    score_delta: float | None
    positive_recovery: bool
    negative_regression: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            self.baseline.arm is not AttachmentCandidateRemainderArm.BASELINE
            or self.remainder.arm is not AttachmentCandidateRemainderArm.REMAINDER
        ):
            raise ValueError("Candidate Remainder case arm order drifted.")
        if any(
            item.task_id != self.task.id
            or item.edge_id != self.task.edge_filter_task.edge.id
            or item.expected_answer != self.expected_answer
            for item in (self.baseline, self.remainder)
        ):
            raise ValueError("Candidate Remainder observation drifted from its case.")
        baseline_score = (
            self.baseline.probability.attachment_score
            if self.baseline.probability is not None
            else None
        )
        remainder_score = (
            self.remainder.probability.attachment_score
            if self.remainder.probability is not None
            else None
        )
        delta = (
            remainder_score - baseline_score
            if baseline_score is not None and remainder_score is not None
            else None
        )
        if not _optional_close(self.baseline_attachment_score, baseline_score):
            raise ValueError("Candidate Remainder Baseline score drifted.")
        if not _optional_close(self.remainder_attachment_score, remainder_score):
            raise ValueError("Candidate Remainder intervention score drifted.")
        if not _optional_close(self.score_delta, delta):
            raise ValueError("Candidate Remainder Score Delta drifted.")
        baseline_answer = _answer(self.baseline)
        remainder_answer = _answer(self.remainder)
        recovery = (
            self.expected_answer == "Y"
            and baseline_answer is AttachmentEdgeFilterAnswerValue.NO
            and remainder_answer is AttachmentEdgeFilterAnswerValue.YES
        )
        regression = (
            self.expected_answer == "N"
            and baseline_answer is AttachmentEdgeFilterAnswerValue.NO
            and remainder_answer is not AttachmentEdgeFilterAnswerValue.NO
        )
        if self.positive_recovery != recovery:
            raise ValueError("Candidate Remainder Positive Recovery drifted.")
        if self.negative_regression != regression:
            raise ValueError("Candidate Remainder Negative Regression drifted.")
        return self


class AttachmentCandidateRemainderReport(BaseModel):
    """Paired development result for CEA-1.9."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_remainder_report_v1"] = (
        "attachment_candidate_remainder_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    baseline_prompt: AttachmentEvidenceReference
    remainder_prompt: AttachmentEvidenceReference
    gold_adjudications: tuple[AttachmentResidualGoldAdjudication, ...]
    cases: tuple[AttachmentCandidateRemainderCase, ...]
    baseline_correct_count: Annotated[int, Field(ge=0, le=10)]
    remainder_correct_count: Annotated[int, Field(ge=0, le=10)]
    baseline_positive_correct_count: Annotated[int, Field(ge=0, le=8)]
    remainder_positive_correct_count: Annotated[int, Field(ge=0, le=8)]
    baseline_negative_correct_count: Annotated[int, Field(ge=0, le=2)]
    remainder_negative_correct_count: Annotated[int, Field(ge=0, le=2)]
    positive_recovery_count: Annotated[int, Field(ge=0, le=8)]
    negative_regression_count: Annotated[int, Field(ge=0, le=2)]
    probability_evidence_count: Annotated[int, Field(ge=0, le=20)]
    positive_median_score_delta: float | None
    negative_max_score_delta: float | None
    outcome: AttachmentCandidateRemainderOutcome
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
            raise ValueError("Candidate Remainder report requires ten ordered cases.")
        if len(self.gold_adjudications) != 1:
            raise ValueError("Candidate Remainder report requires one Gold adjudication.")
        adjudication = self.gold_adjudications[0]
        case_by_task = {item.task.id: item for item in self.cases}
        adjudicated_case = case_by_task.get(adjudication.task_id)
        if (
            adjudicated_case is None
            or adjudicated_case.task.edge_filter_task.edge.id != adjudication.edge_id
            or adjudicated_case.inherited_expected_answer != adjudication.inherited_answer
            or adjudicated_case.expected_answer != adjudication.corrected_answer
        ):
            raise ValueError("Candidate Remainder Gold adjudication was not applied exactly.")
        if any(
            item.task.id != adjudication.task_id
            and item.inherited_expected_answer != item.expected_answer
            for item in self.cases
        ):
            raise ValueError("Candidate Remainder unadjudicated Gold answer changed.")
        if sum(item.expected_answer == "Y" for item in self.cases) != 8:
            raise ValueError("Candidate Remainder positive inventory drifted.")
        if sum(item.expected_answer == "N" for item in self.cases) != 2:
            raise ValueError("Candidate Remainder negative inventory drifted.")
        recorded = (
            self.baseline_correct_count,
            self.remainder_correct_count,
            self.baseline_positive_correct_count,
            self.remainder_positive_correct_count,
            self.baseline_negative_correct_count,
            self.remainder_negative_correct_count,
            self.positive_recovery_count,
            self.negative_regression_count,
            self.probability_evidence_count,
        )
        expected = _report_counts(self.cases)
        if recorded != expected:
            raise ValueError("Candidate Remainder report metrics drifted.")
        positive_deltas = tuple(
            item.score_delta
            for item in self.cases
            if item.expected_answer == "Y" and item.score_delta is not None
        )
        negative_deltas = tuple(
            item.score_delta
            for item in self.cases
            if item.expected_answer == "N" and item.score_delta is not None
        )
        expected_positive_median = median(positive_deltas) if len(positive_deltas) == 8 else None
        expected_negative_max = max(negative_deltas) if len(negative_deltas) == 2 else None
        if not _optional_close(self.positive_median_score_delta, expected_positive_median):
            raise ValueError("Candidate Remainder positive median drifted.")
        if not _optional_close(self.negative_max_score_delta, expected_negative_max):
            raise ValueError("Candidate Remainder negative maximum drifted.")
        complete = self.probability_evidence_count == 20 and all(
            _answer(item.baseline) is not None and _answer(item.remainder) is not None
            for item in self.cases
        )
        selective = (
            expected_positive_median is not None
            and expected_negative_max is not None
            and expected_positive_median > expected_negative_max
        )
        if not complete:
            expected_outcome = AttachmentCandidateRemainderOutcome.INCONCLUSIVE
        elif self.positive_recovery_count == 0:
            expected_outcome = AttachmentCandidateRemainderOutcome.FALSIFIED
        elif (
            self.remainder_correct_count > self.baseline_correct_count
            and self.negative_regression_count == 0
            and selective
        ):
            expected_outcome = AttachmentCandidateRemainderOutcome.SUPPORTED
        else:
            expected_outcome = AttachmentCandidateRemainderOutcome.MIXED
        if self.outcome is not expected_outcome:
            raise ValueError("Candidate Remainder outcome drifted from its evidence.")
        if self.result_fingerprint != attachment_candidate_remainder_fingerprint(self):
            raise ValueError("Candidate Remainder report fingerprint drifted.")
        return self


class AttachmentCandidateRemainderStatus(BaseModel):
    """Machine-readable state for one CEA-1.9 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_remainder_status_v1"] = (
        "attachment_candidate_remainder_status_v1"
    )
    status: AttachmentCandidateRemainderPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentCandidateRemainderOutcome | None
    model_execution_count: Annotated[int, Field(ge=0, le=20)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentCandidateRemainderPackageStatus.COMPLETE
        terminal = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete Candidate Remainder status requires terminal paths.")
        if complete != (self.model_execution_count == 20):
            raise ValueError("Candidate Remainder status execution count drifted.")
        return self


def attachment_candidate_remainder_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.9 DTO draft."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def _report_counts(
    cases: tuple[AttachmentCandidateRemainderCase, ...],
) -> tuple[int, int, int, int, int, int, int, int, int]:
    return (
        sum(item.baseline.passed for item in cases),
        sum(item.remainder.passed for item in cases),
        sum(item.expected_answer == "Y" and item.baseline.passed for item in cases),
        sum(item.expected_answer == "Y" and item.remainder.passed for item in cases),
        sum(item.expected_answer == "N" and item.baseline.passed for item in cases),
        sum(item.expected_answer == "N" and item.remainder.passed for item in cases),
        sum(item.positive_recovery for item in cases),
        sum(item.negative_regression for item in cases),
        sum(
            observation.probability is not None
            for item in cases
            for observation in (item.baseline, item.remainder)
        ),
    )


def _answer(
    observation: AttachmentCandidateRemainderObservation,
) -> AttachmentEdgeFilterAnswerValue | None:
    if observation.decision.status is not AttachmentEdgeFilterDecisionStatus.COMPLETE:
        return None
    return observation.decision.answer


def _optional_close(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(left, right, abs_tol=1e-12)


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
