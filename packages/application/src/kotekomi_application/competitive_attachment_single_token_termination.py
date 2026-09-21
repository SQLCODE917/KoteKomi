"""Typed evidence for the CEA-1.11 single-token termination experiment."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
)
from kotekomi_application.competitive_attachment_finite_answer_format import (
    AttachmentFiniteLabelEvidence,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentSingleTokenOutcome(StrEnum):
    """Terminal causal result for CEA-1.11."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentSingleTokenPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.11 package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentSingleTokenPreflight(BaseModel):
    """Sealed tasks, prompt, and settings for CEA-1.11."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_single_token_preflight_v1"] = (
        "attachment_single_token_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    bare_prompt: AttachmentEvidenceReference
    tasks: tuple[AttachmentResidualOwnershipTask, ...]
    archived_bare_argmax_by_task: dict[
        Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")],
        AttachmentEdgeFilterAnswerValue,
    ]
    configured_max_output_tokens: Annotated[int, Field(ge=1)]
    effective_max_output_tokens: Literal[1] = 1
    seed: Literal[17] = 17
    temperature: Annotated[float, Field(ge=0.0, le=0.0)] = 0.0
    top_logprobs: Literal[10] = 10
    repetition_count: Literal[2] = 2
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        labels = tuple(item.label for item in self.inputs)
        if labels != tuple(sorted(set(labels))):
            raise ValueError("Single-Token inputs must be ordered and distinct.")
        task_ids = tuple(item.id for item in self.tasks)
        if len(task_ids) != 10 or task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Single-Token preflight requires ten ordered tasks.")
        if tuple(self.archived_bare_argmax_by_task) != task_ids:
            raise ValueError("Single-Token archived argmax inventory drifted.")
        if self.result_fingerprint != attachment_single_token_fingerprint(self):
            raise ValueError("Single-Token preflight fingerprint drifted.")
        return self


class AttachmentSingleTokenObservation(BaseModel):
    """One one-token result for one exact task and repetition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_single_token_observation_v1"] = (
        "attachment_single_token_observation_v1"
    )
    repetition: Literal[1, 2]
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    archived_bare_argmax: AttachmentEdgeFilterAnswerValue
    decision: AttachmentEdgeFilterDecision
    finite_label_evidence: AttachmentFiniteLabelEvidence | None
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)] | None
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: str | None
    output_token_count: Annotated[int, Field(ge=0)] | None
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    strict_valid_output: bool
    output_is_one_token: bool
    observed_answer_matches_live_argmax: bool
    live_argmax_matches_archived: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision.edge_id != self.edge_id:
            raise ValueError("Single-Token decision references a foreign Edge.")
        valid = (
            self.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and self.decision.answer is not None
        )
        if self.strict_valid_output != valid:
            raise ValueError("Single-Token strict validity drifted.")
        if (self.model_identity_digest is None) != (self.output_token_count is None):
            raise ValueError("Single-Token receipt identity state drifted.")
        if self.finite_label_evidence is not None and self.model_identity_digest is None:
            raise ValueError("Single-Token probability evidence lacks model identity.")
        one_token = self.output_token_count == 1
        if self.output_is_one_token != one_token:
            raise ValueError("Single-Token output count drifted.")
        observed_matches = (
            valid
            and self.finite_label_evidence is not None
            and self.decision.answer is self.finite_label_evidence.finite_label_argmax
        )
        if self.observed_answer_matches_live_argmax != observed_matches:
            raise ValueError("Single-Token Observed Answer-to-Argmax result drifted.")
        live_matches = (
            self.finite_label_evidence is not None
            and self.finite_label_evidence.finite_label_argmax is self.archived_bare_argmax
        )
        if self.live_argmax_matches_archived != live_matches:
            raise ValueError("Single-Token archived Argmax result drifted.")
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Single-Token raw output text is missing.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Single-Token raw output digest drifted.")
        return self


class AttachmentSingleTokenCase(BaseModel):
    """Two repeated one-token observations for one exact task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_single_token_case_v1"] = "attachment_single_token_case_v1"
    task: AttachmentResidualOwnershipTask
    archived_bare_argmax: AttachmentEdgeFilterAnswerValue
    observations: tuple[AttachmentSingleTokenObservation, ...]
    repetition_answer_agrees: bool
    repetition_argmax_agrees: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        repetitions = tuple(item.repetition for item in self.observations)
        if repetitions != (1, 2):
            raise ValueError("Single-Token case requires ordered repetitions one and two.")
        if any(
            item.task_id != self.task.id
            or item.edge_id != self.task.edge_filter_task.edge.id
            or item.archived_bare_argmax is not self.archived_bare_argmax
            for item in self.observations
        ):
            raise ValueError("Single-Token observation drifted from its case.")
        answers = tuple(item.decision.answer for item in self.observations)
        answer_agrees = all(item.strict_valid_output for item in self.observations) and (
            answers[0] is answers[1]
        )
        if self.repetition_answer_agrees != answer_agrees:
            raise ValueError("Single-Token repetition answer agreement drifted.")
        evidence = tuple(item.finite_label_evidence for item in self.observations)
        argmax_agrees = all(item is not None for item in evidence) and (
            evidence[0].finite_label_argmax is evidence[1].finite_label_argmax
            if evidence[0] is not None and evidence[1] is not None
            else False
        )
        if self.repetition_argmax_agrees != argmax_agrees:
            raise ValueError("Single-Token repetition Argmax agreement drifted.")
        return self


class AttachmentSingleTokenReport(BaseModel):
    """Terminal CEA-1.11 report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_single_token_report_v1"] = (
        "attachment_single_token_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentSingleTokenCase, ...]
    probability_evidence_count: Annotated[int, Field(ge=0, le=20)]
    one_token_output_count: Annotated[int, Field(ge=0, le=20)]
    strict_valid_output_count: Annotated[int, Field(ge=0, le=20)]
    observed_answer_argmax_match_count: Annotated[int, Field(ge=0, le=20)]
    archived_argmax_match_count: Annotated[int, Field(ge=0, le=20)]
    repetition_answer_agreement_count: Annotated[int, Field(ge=0, le=10)]
    repetition_argmax_agreement_count: Annotated[int, Field(ge=0, le=10)]
    outcome: AttachmentSingleTokenOutcome
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
            raise ValueError("Single-Token report requires ten ordered cases.")
        observations = tuple(item for case in self.cases for item in case.observations)
        expected = (
            sum(item.finite_label_evidence is not None for item in observations),
            sum(item.output_is_one_token for item in observations),
            sum(item.strict_valid_output for item in observations),
            sum(item.observed_answer_matches_live_argmax for item in observations),
            sum(item.live_argmax_matches_archived for item in observations),
            sum(item.repetition_answer_agrees for item in self.cases),
            sum(item.repetition_argmax_agrees for item in self.cases),
        )
        recorded = (
            self.probability_evidence_count,
            self.one_token_output_count,
            self.strict_valid_output_count,
            self.observed_answer_argmax_match_count,
            self.archived_argmax_match_count,
            self.repetition_answer_agreement_count,
            self.repetition_argmax_agreement_count,
        )
        if recorded != expected:
            raise ValueError("Single-Token report counts drifted.")
        expected_outcome = attachment_single_token_outcome(
            probability_evidence_count=self.probability_evidence_count,
            one_token_output_count=self.one_token_output_count,
            strict_valid_output_count=self.strict_valid_output_count,
            observed_answer_argmax_match_count=self.observed_answer_argmax_match_count,
            archived_argmax_match_count=self.archived_argmax_match_count,
            repetition_answer_agreement_count=self.repetition_answer_agreement_count,
            repetition_argmax_agreement_count=self.repetition_argmax_agreement_count,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Single-Token outcome drifted from its evidence.")
        if self.result_fingerprint != attachment_single_token_fingerprint(self):
            raise ValueError("Single-Token report fingerprint drifted.")
        return self


class AttachmentSingleTokenStatus(BaseModel):
    """Machine-readable state for one CEA-1.11 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_single_token_status_v1"] = (
        "attachment_single_token_status_v1"
    )
    status: AttachmentSingleTokenPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentSingleTokenOutcome | None
    model_execution_count: Annotated[int, Field(ge=0, le=20)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentSingleTokenPackageStatus.COMPLETE
        terminal = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete Single-Token status requires terminal paths.")
        if complete != (self.model_execution_count == 20):
            raise ValueError("Single-Token status execution count drifted.")
        return self


def attachment_single_token_outcome(
    *,
    probability_evidence_count: int,
    one_token_output_count: int,
    strict_valid_output_count: int,
    observed_answer_argmax_match_count: int,
    archived_argmax_match_count: int,
    repetition_answer_agreement_count: int,
    repetition_argmax_agreement_count: int,
) -> AttachmentSingleTokenOutcome:
    """Classify the declared CEA-1.11 gates."""
    if probability_evidence_count != 20:
        return AttachmentSingleTokenOutcome.INCONCLUSIVE
    if (
        one_token_output_count == 20
        and strict_valid_output_count == 20
        and observed_answer_argmax_match_count == 20
        and archived_argmax_match_count == 20
        and repetition_answer_agreement_count == 10
        and repetition_argmax_agreement_count == 10
    ):
        return AttachmentSingleTokenOutcome.SUPPORTED
    if strict_valid_output_count > 6:
        return AttachmentSingleTokenOutcome.MIXED
    return AttachmentSingleTokenOutcome.FALSIFIED


def attachment_single_token_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.11 DTO draft."""
    encoded = json.dumps(
        value.model_dump(mode="json", exclude={"result_fingerprint"}),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
