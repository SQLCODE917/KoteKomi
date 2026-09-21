"""Typed evidence for CEA-1.12 runtime-calibrated finite termination."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_domain import ModelRunStatus
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
from kotekomi_application.staged_model_extraction import ModelOutputTokenProbability

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentCalibratedTerminationOutcome(StrEnum):
    """Terminal CEA-1.12 Mechanism Proof result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentCalibratedTerminationPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.12 evidence package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentProductionSuitabilityCondition(StrEnum):
    """One condition outside the CEA-1.12 Mechanism Proof."""

    RUNTIME_BUILD_IDENTITY = "runtime_build_identity"
    SERVER_SAMPLING_DEFAULTS = "server_sampling_defaults"
    TRUNCATION_OBSERVABILITY = "truncation_observability"
    FULL_POOL_SEMANTIC_QUALITY = "full_pool_semantic_quality"


class AttachmentCalibratedTerminationPreflight(BaseModel):
    """Sealed tasks, distributions, and settings for CEA-1.12."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibrated_termination_preflight_v1"] = (
        "attachment_calibrated_termination_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    bare_prompt: AttachmentEvidenceReference
    tasks: tuple[AttachmentResidualOwnershipTask, ...]
    archived_bare_argmax_by_task: dict[
        Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")],
        AttachmentEdgeFilterAnswerValue,
    ]
    archived_position_zero_sha256_by_task: dict[
        Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")],
        Annotated[str, Field(pattern=_SHA256)],
    ]
    expected_model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    configured_max_output_tokens: Annotated[int, Field(ge=2)]
    requested_output_limit: Literal[2] = 2
    expected_observed_output_count: Literal[1] = 1
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
            raise ValueError("Calibrated Termination inputs must be ordered and distinct.")
        task_ids = tuple(item.id for item in self.tasks)
        if len(task_ids) != 10 or task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Calibrated Termination preflight requires ten ordered tasks.")
        if tuple(self.archived_bare_argmax_by_task) != task_ids:
            raise ValueError("Calibrated Termination archived Argmax inventory drifted.")
        if tuple(self.archived_position_zero_sha256_by_task) != task_ids:
            raise ValueError("Calibrated Termination distribution inventory drifted.")
        if self.result_fingerprint != attachment_calibrated_termination_fingerprint(self):
            raise ValueError("Calibrated Termination preflight fingerprint drifted.")
        return self


class AttachmentCalibratedTerminationObservation(BaseModel):
    """One CEA-1.12 result for one exact task and repetition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibrated_termination_observation_v1"] = (
        "attachment_calibrated_termination_observation_v1"
    )
    repetition: Literal[1, 2]
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    archived_bare_argmax: AttachmentEdgeFilterAnswerValue
    archived_position_zero_sha256: Annotated[str, Field(pattern=_SHA256)]
    decision: AttachmentEdgeFilterDecision
    finite_label_evidence: AttachmentFiniteLabelEvidence | None
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    model_run_status: ModelRunStatus
    model_error_code: str | None
    model_error_message: str | None
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: str | None
    output_token_count: Annotated[int, Field(ge=0)] | None
    probability_positions: tuple[Annotated[int, Field(ge=0)], ...]
    position_zero_sha256: Annotated[str, Field(pattern=_SHA256)] | None
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    exact_raw_finite_answer: bool
    output_count_witnesses_agree: bool
    observed_answer_matches_live_argmax: bool
    live_distribution_matches_archived: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision.edge_id != self.edge_id:
            raise ValueError("Calibrated Termination decision references a foreign Edge.")
        if tuple(sorted(set(self.probability_positions))) != self.probability_positions:
            raise ValueError("Calibrated Termination probability positions must be distinct.")
        has_position_zero = 0 in self.probability_positions
        if has_position_zero != (self.position_zero_sha256 is not None):
            raise ValueError("Calibrated Termination position-zero evidence drifted.")
        if self.finite_label_evidence is not None and not has_position_zero:
            raise ValueError("Calibrated Termination finite evidence lacks position zero.")
        if (self.model_error_code is None) != (self.model_error_message is None):
            raise ValueError("Calibrated Termination model error evidence is incomplete.")
        succeeded = self.model_run_status is ModelRunStatus.SUCCEEDED
        if succeeded == (self.model_error_code is not None):
            raise ValueError("Calibrated Termination model failure evidence drifted.")
        exact_raw = attachment_exact_raw_finite_answer(self.raw_output_text)
        if self.exact_raw_finite_answer != exact_raw:
            raise ValueError("Calibrated Termination exact raw-answer result drifted.")
        witnesses_agree = attachment_output_count_witnesses_agree(
            output_token_count=self.output_token_count,
            probability_positions=self.probability_positions,
        )
        if self.output_count_witnesses_agree != witnesses_agree:
            raise ValueError("Calibrated Termination output-count witnesses drifted.")
        parsed = (
            self.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and self.decision.answer is not None
        )
        observed_matches = (
            parsed
            and self.finite_label_evidence is not None
            and self.decision.answer is self.finite_label_evidence.finite_label_argmax
        )
        if self.observed_answer_matches_live_argmax != observed_matches:
            raise ValueError("Calibrated Termination Answer-to-Argmax result drifted.")
        distribution_matches = self.position_zero_sha256 == self.archived_position_zero_sha256
        if self.live_distribution_matches_archived != distribution_matches:
            raise ValueError("Calibrated Termination archived distribution result drifted.")
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Calibrated Termination raw output text is missing.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Calibrated Termination raw output digest drifted.")
        return self


class AttachmentCalibratedTerminationCase(BaseModel):
    """Two calibrated observations for one exact task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibrated_termination_case_v1"] = (
        "attachment_calibrated_termination_case_v1"
    )
    task: AttachmentResidualOwnershipTask
    archived_bare_argmax: AttachmentEdgeFilterAnswerValue
    archived_position_zero_sha256: Annotated[str, Field(pattern=_SHA256)]
    observations: tuple[AttachmentCalibratedTerminationObservation, ...]
    repetition_answer_agrees: bool
    repetition_distribution_agrees: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        repetitions = tuple(item.repetition for item in self.observations)
        if repetitions != (1, 2):
            raise ValueError("Calibrated Termination case requires repetitions one and two.")
        if any(
            item.task_id != self.task.id
            or item.edge_id != self.task.edge_filter_task.edge.id
            or item.archived_bare_argmax is not self.archived_bare_argmax
            or item.archived_position_zero_sha256 != self.archived_position_zero_sha256
            for item in self.observations
        ):
            raise ValueError("Calibrated Termination observation drifted from its case.")
        answers = tuple(item.decision.answer for item in self.observations)
        answer_agrees = all(item.exact_raw_finite_answer for item in self.observations) and (
            answers[0] is answers[1]
        )
        if self.repetition_answer_agrees != answer_agrees:
            raise ValueError("Calibrated Termination repetition answer result drifted.")
        digests = tuple(item.position_zero_sha256 for item in self.observations)
        distribution_agrees = digests[0] is not None and digests[0] == digests[1]
        if self.repetition_distribution_agrees != distribution_agrees:
            raise ValueError("Calibrated Termination repetition distribution result drifted.")
        return self


class AttachmentCalibratedTerminationReport(BaseModel):
    """Terminal CEA-1.12 Mechanism Proof report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibrated_termination_report_v1"] = (
        "attachment_calibrated_termination_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentCalibratedTerminationCase, ...]
    successful_execution_count: Annotated[int, Field(ge=0, le=20)]
    probability_evidence_count: Annotated[int, Field(ge=0, le=20)]
    one_position_zero_count: Annotated[int, Field(ge=0, le=20)]
    one_output_token_count: Annotated[int, Field(ge=0, le=20)]
    output_count_witness_agreement_count: Annotated[int, Field(ge=0, le=20)]
    exact_raw_finite_answer_count: Annotated[int, Field(ge=0, le=20)]
    observed_answer_argmax_match_count: Annotated[int, Field(ge=0, le=20)]
    archived_distribution_match_count: Annotated[int, Field(ge=0, le=20)]
    repetition_answer_agreement_count: Annotated[int, Field(ge=0, le=10)]
    repetition_distribution_agreement_count: Annotated[int, Field(ge=0, le=10)]
    mechanism_proof: bool
    production_suitability: Literal["unmet"] = "unmet"
    unmet_suitability_conditions: tuple[AttachmentProductionSuitabilityCondition, ...]
    outcome: AttachmentCalibratedTerminationOutcome
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
            raise ValueError("Calibrated Termination report requires ten ordered cases.")
        observations = tuple(item for case in self.cases for item in case.observations)
        expected = (
            sum(item.model_run_status is ModelRunStatus.SUCCEEDED for item in observations),
            sum(item.finite_label_evidence is not None for item in observations),
            sum(item.probability_positions == (0,) for item in observations),
            sum(item.output_token_count == 1 for item in observations),
            sum(item.output_count_witnesses_agree for item in observations),
            sum(item.exact_raw_finite_answer for item in observations),
            sum(item.observed_answer_matches_live_argmax for item in observations),
            sum(item.live_distribution_matches_archived for item in observations),
            sum(item.repetition_answer_agrees for item in self.cases),
            sum(item.repetition_distribution_agrees for item in self.cases),
        )
        recorded = (
            self.successful_execution_count,
            self.probability_evidence_count,
            self.one_position_zero_count,
            self.one_output_token_count,
            self.output_count_witness_agreement_count,
            self.exact_raw_finite_answer_count,
            self.observed_answer_argmax_match_count,
            self.archived_distribution_match_count,
            self.repetition_answer_agreement_count,
            self.repetition_distribution_agreement_count,
        )
        if recorded != expected:
            raise ValueError("Calibrated Termination report counts drifted.")
        expected_mechanism = attachment_calibrated_termination_mechanism_proof(
            successful_execution_count=self.successful_execution_count,
            probability_evidence_count=self.probability_evidence_count,
            one_position_zero_count=self.one_position_zero_count,
            one_output_token_count=self.one_output_token_count,
            output_count_witness_agreement_count=self.output_count_witness_agreement_count,
            exact_raw_finite_answer_count=self.exact_raw_finite_answer_count,
            observed_answer_argmax_match_count=self.observed_answer_argmax_match_count,
            archived_distribution_match_count=self.archived_distribution_match_count,
            repetition_answer_agreement_count=self.repetition_answer_agreement_count,
            repetition_distribution_agreement_count=(self.repetition_distribution_agreement_count),
        )
        if self.mechanism_proof != expected_mechanism:
            raise ValueError("Calibrated Termination Mechanism Proof drifted.")
        expected_outcome = attachment_calibrated_termination_outcome(
            successful_execution_count=self.successful_execution_count,
            probability_evidence_count=self.probability_evidence_count,
            exact_raw_finite_answer_count=self.exact_raw_finite_answer_count,
            mechanism_proof=self.mechanism_proof,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Calibrated Termination outcome drifted.")
        expected_conditions = tuple(AttachmentProductionSuitabilityCondition)
        if self.unmet_suitability_conditions != expected_conditions:
            raise ValueError("Calibrated Termination suitability conditions drifted.")
        if self.result_fingerprint != attachment_calibrated_termination_fingerprint(self):
            raise ValueError("Calibrated Termination report fingerprint drifted.")
        return self


class AttachmentCalibratedTerminationStatus(BaseModel):
    """Machine-readable state for one CEA-1.12 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_calibrated_termination_status_v1"] = (
        "attachment_calibrated_termination_status_v1"
    )
    status: AttachmentCalibratedTerminationPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentCalibratedTerminationOutcome | None
    mechanism_proof: bool | None
    production_suitability: Literal["unmet"]
    model_execution_count: Annotated[int, Field(ge=0, le=20)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentCalibratedTerminationPackageStatus.COMPLETE
        terminal = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
            self.mechanism_proof,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete Calibrated Termination status requires terminal paths.")
        if complete != (self.model_execution_count == 20):
            raise ValueError("Calibrated Termination execution count drifted.")
        return self


def attachment_calibrated_termination_mechanism_proof(
    *,
    successful_execution_count: int,
    probability_evidence_count: int,
    one_position_zero_count: int,
    one_output_token_count: int,
    output_count_witness_agreement_count: int,
    exact_raw_finite_answer_count: int,
    observed_answer_argmax_match_count: int,
    archived_distribution_match_count: int,
    repetition_answer_agreement_count: int,
    repetition_distribution_agreement_count: int,
) -> bool:
    """Return whether every declared CEA-1.12 mechanism gate passed."""
    return (
        successful_execution_count,
        probability_evidence_count,
        one_position_zero_count,
        one_output_token_count,
        output_count_witness_agreement_count,
        exact_raw_finite_answer_count,
        observed_answer_argmax_match_count,
        archived_distribution_match_count,
        repetition_answer_agreement_count,
        repetition_distribution_agreement_count,
    ) == (20, 20, 20, 20, 20, 20, 20, 20, 10, 10)


def attachment_calibrated_termination_outcome(
    *,
    successful_execution_count: int,
    probability_evidence_count: int,
    exact_raw_finite_answer_count: int,
    mechanism_proof: bool,
) -> AttachmentCalibratedTerminationOutcome:
    """Classify the bounded CEA-1.12 mechanism result."""
    if successful_execution_count != 20 or probability_evidence_count != 20:
        return AttachmentCalibratedTerminationOutcome.INCONCLUSIVE
    if mechanism_proof:
        return AttachmentCalibratedTerminationOutcome.SUPPORTED
    if exact_raw_finite_answer_count:
        return AttachmentCalibratedTerminationOutcome.MIXED
    return AttachmentCalibratedTerminationOutcome.FALSIFIED


def attachment_exact_raw_finite_answer(value: str | None) -> bool:
    """Return whether raw output is exactly one finite answer character."""
    return value in {item.value for item in AttachmentEdgeFilterAnswerValue}


def attachment_output_count_witnesses_agree(
    *,
    output_token_count: int | None,
    probability_positions: tuple[int, ...],
) -> bool:
    """Return whether both runtime witnesses identify one position-zero token."""
    return output_token_count == 1 and probability_positions == (0,)


def attachment_position_zero_sha256(value: ModelOutputTokenProbability) -> str:
    """Return one canonical digest for exact position-zero probability evidence."""
    payload = {
        "alternatives": [
            {
                "log_probability": item.log_probability,
                "token": item.token,
                "token_bytes": list(item.token_bytes),
            }
            for item in value.alternatives
        ],
        "log_probability": value.log_probability,
        "position": value.position,
        "token": value.token,
        "token_bytes": list(value.token_bytes),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def attachment_calibrated_termination_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.12 DTO draft."""
    encoded = json.dumps(
        value.model_dump(mode="json", exclude={"result_fingerprint"}),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
