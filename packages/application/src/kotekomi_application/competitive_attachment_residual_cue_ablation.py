"""Typed evidence for the CEA-1.8 demonstration cue ablation."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
)
from kotekomi_application.competitive_attachment_edge_filter_calibration import (
    AttachmentAnswerProbability,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSourceRange,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentResidualCueAblationOutcome(StrEnum):
    """Terminal causal result for the CEA-1.8 prompt ablation."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentResidualCueAblationPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.8 evidence package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentResidualGoldAdjudication(BaseModel):
    """One operator-approved correction to inherited Attachment Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_gold_adjudication_v1"] = (
        "attachment_residual_gold_adjudication_v1"
    )
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    candidate_range: AttachmentSourceRange
    target_event_range: AttachmentSourceRange
    inherited_answer: Literal["N"]
    corrected_answer: Literal["Y"]
    rationale: Literal["exact_attachment_range_does_not_answer_residual_ownership"]
    review_authority: Literal["operator_approved"] = "operator_approved"

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        candidate = self.candidate_range
        event = self.target_event_range
        if not (candidate.start <= event.start and event.end <= candidate.end):
            raise ValueError("Residual Gold adjudication requires Event containment.")
        return self


class AttachmentResidualCueAblationPreflight(BaseModel):
    """Sealed inputs and truthful runtime settings for CEA-1.8."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_cue_ablation_preflight_v2"] = (
        "attachment_residual_cue_ablation_preflight_v2"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    baseline_prompt: AttachmentEvidenceReference
    cue_prompt: AttachmentEvidenceReference
    tasks: tuple[AttachmentResidualOwnershipTask, ...]
    gold_adjudications: tuple[AttachmentResidualGoldAdjudication, ...]
    baseline_report_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    prompt_diff_valid: Literal[True] = True
    baseline_constant_no: Literal[True] = True
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
            raise ValueError("Cue ablation inputs must be ordered and distinct.")
        task_ids = tuple(item.id for item in self.tasks)
        if len(task_ids) != 10 or task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Cue ablation requires ten ordered distinct tasks.")
        if len(self.gold_adjudications) != 1:
            raise ValueError("Cue ablation requires one Residual Gold adjudication.")
        task_by_id = {item.id: item for item in self.tasks}
        for adjudication in self.gold_adjudications:
            task = task_by_id.get(adjudication.task_id)
            if task is None:
                raise ValueError("Residual Gold adjudication references a foreign task.")
            edge = task.edge_filter_task.edge
            if (
                edge.id != adjudication.edge_id
                or edge.candidate_range != adjudication.candidate_range
                or edge.event_range != adjudication.target_event_range
            ):
                raise ValueError("Residual Gold adjudication differs from exact task evidence.")
        if self.baseline_prompt.sha256 == self.cue_prompt.sha256:
            raise ValueError("Cue ablation prompts must differ.")
        if self.result_fingerprint != attachment_residual_cue_ablation_fingerprint(self):
            raise ValueError("Cue ablation preflight fingerprint drifted.")
        return self


class AttachmentResidualCueAblationCase(BaseModel):
    """One task's baseline answers, cue answers, and probability evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_cue_ablation_case_v2"] = (
        "attachment_residual_cue_ablation_case_v2"
    )
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    inherited_expected_answer: Literal["Y", "N"]
    expected_answer: Literal["Y", "N"]
    baseline_answers: tuple[
        AttachmentEdgeFilterAnswerValue,
        AttachmentEdgeFilterAnswerValue,
    ]
    cue_answers: tuple[
        AttachmentEdgeFilterAnswerValue | None,
        AttachmentEdgeFilterAnswerValue | None,
    ]
    cue_probabilities: tuple[
        AttachmentAnswerProbability | None,
        AttachmentAnswerProbability | None,
    ]
    stable_cue_result: bool
    positive_yes_observation_count: Annotated[int, Field(ge=0, le=2)]
    positive_recovery: bool
    negative_regression: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.baseline_answers != (
            AttachmentEdgeFilterAnswerValue.NO,
            AttachmentEdgeFilterAnswerValue.NO,
        ):
            raise ValueError("Cue ablation baseline must contain two N answers.")
        for answer, probability in zip(
            self.cue_answers,
            self.cue_probabilities,
            strict=True,
        ):
            if (answer is None) != (probability is None):
                raise ValueError("Cue answer and Probability Evidence completeness differ.")
            if probability is not None and probability.emitted_answer is not answer:
                raise ValueError("Cue answer differs from its Probability Evidence.")
        stable = self.cue_answers[0] is not None and self.cue_answers[0] is self.cue_answers[1]
        positive_yes_count = (
            sum(item is AttachmentEdgeFilterAnswerValue.YES for item in self.cue_answers)
            if self.expected_answer == "Y"
            else 0
        )
        recovered = self.expected_answer == "Y" and self.cue_answers == (
            AttachmentEdgeFilterAnswerValue.YES,
            AttachmentEdgeFilterAnswerValue.YES,
        )
        regressed = self.expected_answer == "N" and any(
            item is not AttachmentEdgeFilterAnswerValue.NO for item in self.cue_answers
        )
        if self.stable_cue_result != stable:
            raise ValueError("Cue ablation stability result drifted.")
        if self.positive_yes_observation_count != positive_yes_count:
            raise ValueError("Cue ablation positive answer count drifted.")
        if self.positive_recovery != recovered:
            raise ValueError("Cue ablation positive recovery drifted.")
        if self.negative_regression != regressed:
            raise ValueError("Cue ablation negative regression drifted.")
        return self


class AttachmentResidualCueAblationReport(BaseModel):
    """Occurrence-level comparison of CEA-1.7 with the cue ablation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_cue_ablation_report_v2"] = (
        "attachment_residual_cue_ablation_report_v2"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    baseline_prompt: AttachmentEvidenceReference
    cue_prompt: AttachmentEvidenceReference
    gold_adjudications: tuple[AttachmentResidualGoldAdjudication, ...]
    cases: tuple[AttachmentResidualCueAblationCase, ...]
    baseline_no_count: Literal[20] = 20
    cue_yes_count: Annotated[int, Field(ge=0, le=20)]
    cue_no_count: Annotated[int, Field(ge=0, le=20)]
    cue_unclear_count: Annotated[int, Field(ge=0, le=20)]
    unresolved_count: Annotated[int, Field(ge=0, le=20)]
    probability_evidence_count: Annotated[int, Field(ge=0, le=20)]
    stable_case_count: Annotated[int, Field(ge=0, le=10)]
    positive_yes_observation_count: Annotated[int, Field(ge=0, le=20)]
    positive_recovery_case_count: Annotated[int, Field(ge=0, le=10)]
    negative_regression_case_count: Annotated[int, Field(ge=0, le=10)]
    outcome: AttachmentResidualCueAblationOutcome
    model_execution_count: Literal[20] = 20
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        task_ids = tuple(item.task_id for item in self.cases)
        if len(task_ids) != 10 or task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Cue ablation cases must be ordered and distinct.")
        if len(self.gold_adjudications) != 1:
            raise ValueError("Cue ablation report requires one Residual Gold adjudication.")
        adjudication_by_task = {item.task_id: item for item in self.gold_adjudications}
        if len(adjudication_by_task) != len(self.gold_adjudications):
            raise ValueError("Residual Gold adjudications must reference distinct tasks.")
        case_by_task = {item.task_id: item for item in self.cases}
        for task_id, case in case_by_task.items():
            adjudication = adjudication_by_task.get(task_id)
            if adjudication is None:
                if case.inherited_expected_answer != case.expected_answer:
                    raise ValueError("Unadjudicated Residual Gold answer changed.")
            elif (
                case.edge_id != adjudication.edge_id
                or case.inherited_expected_answer != adjudication.inherited_answer
                or case.expected_answer != adjudication.corrected_answer
            ):
                raise ValueError("Residual Gold adjudication was not applied exactly.")
        if set(adjudication_by_task) - set(case_by_task):
            raise ValueError("Residual Gold adjudication references a missing case.")
        if sum(item.expected_answer == "Y" for item in self.cases) != 8:
            raise ValueError("Corrected cue ablation positive inventory drifted.")
        if sum(item.expected_answer == "N" for item in self.cases) != 2:
            raise ValueError("Corrected cue ablation negative inventory drifted.")
        answers = tuple(answer for case in self.cases for answer in case.cue_answers)
        counts = (
            sum(item is AttachmentEdgeFilterAnswerValue.YES for item in answers),
            sum(item is AttachmentEdgeFilterAnswerValue.NO for item in answers),
            sum(item is AttachmentEdgeFilterAnswerValue.UNCLEAR for item in answers),
            sum(item is None for item in answers),
            sum(item is not None for case in self.cases for item in case.cue_probabilities),
            sum(item.stable_cue_result for item in self.cases),
            sum(item.positive_yes_observation_count for item in self.cases),
            sum(item.positive_recovery for item in self.cases),
            sum(item.negative_regression for item in self.cases),
        )
        recorded = (
            self.cue_yes_count,
            self.cue_no_count,
            self.cue_unclear_count,
            self.unresolved_count,
            self.probability_evidence_count,
            self.stable_case_count,
            self.positive_yes_observation_count,
            self.positive_recovery_case_count,
            self.negative_regression_case_count,
        )
        if recorded != counts:
            raise ValueError("Cue ablation report metrics drifted.")
        complete = self.unresolved_count == 0 and self.probability_evidence_count == 20
        if not complete:
            expected = AttachmentResidualCueAblationOutcome.INCONCLUSIVE
        elif self.positive_yes_observation_count == 0:
            expected = AttachmentResidualCueAblationOutcome.FALSIFIED
        elif (
            self.positive_recovery_case_count > 0
            and self.negative_regression_case_count == 0
            and self.stable_case_count == 10
        ):
            expected = AttachmentResidualCueAblationOutcome.SUPPORTED
        else:
            expected = AttachmentResidualCueAblationOutcome.MIXED
        if self.outcome is not expected:
            raise ValueError("Cue ablation outcome drifted from its observations.")
        if self.result_fingerprint != attachment_residual_cue_ablation_fingerprint(self):
            raise ValueError("Cue ablation report fingerprint drifted.")
        return self


class AttachmentResidualCueAblationStatus(BaseModel):
    """Machine-readable state for one CEA-1.8 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_cue_ablation_status_v1"] = (
        "attachment_residual_cue_ablation_status_v1"
    )
    status: AttachmentResidualCueAblationPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    ablation_report_path: str | None
    comparison_report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentResidualCueAblationOutcome | None
    model_execution_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentResidualCueAblationPackageStatus.COMPLETE
        terminal = (
            self.ablation_report_path,
            self.comparison_report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete cue ablation status requires terminal paths.")
        if complete != (self.model_execution_count == 20):
            raise ValueError("Cue ablation execution count drifted from status.")
        return self


def attachment_residual_cue_ablation_fingerprint(value: BaseModel) -> str:
    """Return one canonical CEA-1.8 evidence fingerprint."""
    payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
