"""Typed evidence for the CEA-1.13 Part-Wise Residual Ownership experiment."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_domain import ModelRunStatus
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterTask,
    attachment_edge_filter_model_task_input,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
    attachment_candidate_remainder_ranges,
    build_attachment_residual_ownership_task,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSourceRange,
)

_SHA256 = r"^[a-f0-9]{64}$"
ATTACHMENT_REMAINDER_PART_RENDERER_ID = "attachment_remainder_part_task_v1"


class AttachmentRemainderPartKind(StrEnum):
    """Deterministic character class for one exact Remainder Part."""

    SUBSTANTIVE = "substantive"
    STRUCTURAL = "structural"


class AttachmentPartwiseArm(StrEnum):
    """One CEA-1.13 semantic task shape."""

    WHOLE = "whole"
    PART = "part"


class AttachmentPartwiseOutcome(StrEnum):
    """Terminal result for the CEA-1.13 hypothesis."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentPartwisePackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.13 evidence package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentRemainderPartTask(BaseModel):
    """One exact Candidate Remainder part bound to its Target Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_part_task_v1"] = (
        "attachment_remainder_part_task_v1"
    )
    id: Annotated[str, Field(pattern=r"^arp_[a-f0-9]{24}$")]
    residual_task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_filter_task: AttachmentEdgeFilterTask
    part_number: Annotated[int, Field(ge=1, le=2)]
    source_range: AttachmentSourceRange
    kind: AttachmentRemainderPartKind
    task_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_residual = build_attachment_residual_ownership_task(self.edge_filter_task)
        if self.residual_task_id != expected_residual.id:
            raise ValueError("Remainder Part references a foreign Residual Ownership task.")
        ranges = attachment_candidate_remainder_ranges(self.edge_filter_task)
        if self.part_number > len(ranges):
            raise ValueError("Remainder Part number is outside the Candidate Remainder.")
        if self.source_range != ranges[self.part_number - 1]:
            raise ValueError("Remainder Part range drifted from authoritative characters.")
        expected_kind = attachment_remainder_part_kind(self.source_range.text)
        if self.kind is not expected_kind:
            raise ValueError("Remainder Part character class drifted.")
        expected_fingerprint = attachment_remainder_part_task_fingerprint(
            residual_task_id=self.residual_task_id,
            edge_filter_task=self.edge_filter_task,
            part_number=self.part_number,
            source_range=self.source_range,
        )
        if self.task_fingerprint != expected_fingerprint:
            raise ValueError("Remainder Part task fingerprint drifted.")
        if self.id != _identifier("arp", expected_fingerprint):
            raise ValueError("Remainder Part task ID drifted.")
        return self


class AttachmentPartwiseObservation(BaseModel):
    """One exact whole-Candidate or Remainder Part model observation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_partwise_observation_v1"] = (
        "attachment_partwise_observation_v1"
    )
    arm: AttachmentPartwiseArm
    repetition: Literal[1, 2]
    residual_task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    part_task_id: Annotated[str, Field(pattern=r"^arp_[a-f0-9]{24}$")] | None
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    decision: AttachmentEdgeFilterDecision
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: str | None
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    model_run_status: ModelRunStatus
    output_token_count: Annotated[int, Field(ge=0)] | None
    probability_positions: tuple[Annotated[int, Field(ge=0)], ...]
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    strict_finite_answer: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (self.arm is AttachmentPartwiseArm.PART) != (self.part_task_id is not None):
            raise ValueError("Part-wise observation arm and Part task reference disagree.")
        if self.decision.edge_id != self.edge_id:
            raise ValueError("Part-wise observation references a foreign Edge.")
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Part-wise observation lacks archived raw output text.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Part-wise raw output digest drifted.")
        expected_strict = (
            self.raw_output_text in {item.value for item in AttachmentEdgeFilterAnswerValue}
            and self.decision.answer is not None
            and self.decision.answer.value == self.raw_output_text
            and self.output_token_count == 1
            and self.probability_positions == (0,)
        )
        if self.strict_finite_answer != expected_strict:
            raise ValueError("Part-wise strict finite-answer result drifted.")
        return self


class AttachmentPartwiseCaseEvaluation(BaseModel):
    """Whole and Part Arm results for one occurrence-specific Candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_partwise_case_evaluation_v1"] = (
        "attachment_partwise_case_evaluation_v1"
    )
    task: AttachmentResidualOwnershipTask
    part_tasks: tuple[AttachmentRemainderPartTask, ...]
    expected_answer: Literal["Y", "N"]
    archived_whole_answer: Literal["Y", "N", "U"]
    whole_observations: tuple[AttachmentPartwiseObservation, ...]
    part_observations: tuple[AttachmentPartwiseObservation, ...]
    whole_answers: tuple[Literal["Y", "N", "U"] | None, ...]
    part_aggregate_answers: tuple[Literal["Y", "N", "U"] | None, ...]
    whole_stable: bool
    part_stable: bool
    whole_passed: bool
    part_passed: bool
    recovered: bool
    regressed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_parts = build_attachment_remainder_part_tasks(self.task)
        if self.part_tasks != expected_parts:
            raise ValueError("Part-wise case Part task inventory drifted.")
        if tuple(item.repetition for item in self.whole_observations) != (1, 2):
            raise ValueError("Part-wise case requires two Whole Arm observations.")
        if any(
            item.arm is not AttachmentPartwiseArm.WHOLE
            or item.residual_task_id != self.task.id
            or item.decision.task_id != self.task.edge_filter_task.task_id
            for item in self.whole_observations
        ):
            raise ValueError("Part-wise case contains a foreign Whole Arm observation.")
        substantive = tuple(
            item for item in self.part_tasks if item.kind is AttachmentRemainderPartKind.SUBSTANTIVE
        )
        expected_part_keys = tuple(
            (repetition, item.id) for repetition in (1, 2) for item in substantive
        )
        observed_part_keys = tuple(
            (item.repetition, item.part_task_id) for item in self.part_observations
        )
        if observed_part_keys != expected_part_keys or any(
            item.arm is not AttachmentPartwiseArm.PART
            or item.residual_task_id != self.task.id
            or item.decision.task_id != self.task.edge_filter_task.task_id
            for item in self.part_observations
        ):
            raise ValueError("Part-wise case Part Arm observation inventory drifted.")
        expected_whole = tuple(_observation_answer(item) for item in self.whole_observations)
        expected_aggregate = tuple(
            aggregate_attachment_remainder_part_answers(
                self.part_tasks,
                tuple(item for item in self.part_observations if item.repetition == repetition),
            )
            for repetition in (1, 2)
        )
        if self.whole_answers != expected_whole:
            raise ValueError("Part-wise case Whole Arm answers drifted.")
        if self.part_aggregate_answers != expected_aggregate:
            raise ValueError("Part-wise case Part Aggregate answers drifted.")
        whole_stable = expected_whole[0] == expected_whole[1]
        part_stable = expected_aggregate[0] == expected_aggregate[1]
        whole_passed = all(item == self.expected_answer for item in expected_whole)
        part_passed = all(item == self.expected_answer for item in expected_aggregate)
        recorded = (
            self.whole_stable,
            self.part_stable,
            self.whole_passed,
            self.part_passed,
            self.recovered,
            self.regressed,
        )
        expected = (
            whole_stable,
            part_stable,
            whole_passed,
            part_passed,
            not whole_passed and part_passed,
            whole_passed and not part_passed,
        )
        if recorded != expected:
            raise ValueError("Part-wise case evaluation flags drifted.")
        return self


class AttachmentPartwisePreflight(BaseModel):
    """Digest-bound CEA-1.13 input inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_partwise_preflight_v1"] = "attachment_partwise_preflight_v1"
    inputs: tuple[AttachmentEvidenceReference, ...]
    whole_prompt: AttachmentEvidenceReference
    part_prompt: AttachmentEvidenceReference
    tasks: tuple[AttachmentResidualOwnershipTask, ...]
    part_tasks: tuple[AttachmentRemainderPartTask, ...]
    expected_answer_by_task: dict[str, Literal["Y", "N"]]
    archived_whole_answer_by_task: dict[str, Literal["Y", "N", "U"]]
    configured_max_output_tokens: Annotated[int, Field(ge=2)]
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.tasks) != 10:
            raise ValueError("Part-wise preflight requires ten Residual Ownership tasks.")
        task_ids = tuple(item.id for item in self.tasks)
        if task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Part-wise preflight tasks must be ordered and distinct.")
        expected_parts = tuple(
            part for task in self.tasks for part in build_attachment_remainder_part_tasks(task)
        )
        if self.part_tasks != expected_parts or len(self.part_tasks) != 18:
            raise ValueError("Part-wise preflight requires eighteen exact Remainder Parts.")
        if (
            sum(item.kind is AttachmentRemainderPartKind.STRUCTURAL for item in self.part_tasks)
            != 1
        ):
            raise ValueError("Part-wise preflight Structural Part inventory drifted.")
        if set(self.expected_answer_by_task) != set(task_ids):
            raise ValueError("Part-wise preflight Gold inventory drifted.")
        if sum(value == "Y" for value in self.expected_answer_by_task.values()) != 8:
            raise ValueError("Part-wise preflight requires eight Gold-positive cases.")
        if sum(value == "N" for value in self.expected_answer_by_task.values()) != 2:
            raise ValueError("Part-wise preflight requires two Gold-negative cases.")
        if set(self.archived_whole_answer_by_task) != set(task_ids):
            raise ValueError("Part-wise archived Whole Arm inventory drifted.")
        if self.result_fingerprint != attachment_partwise_fingerprint(self):
            raise ValueError("Part-wise preflight fingerprint drifted.")
        return self


class AttachmentPartwiseReport(BaseModel):
    """Terminal Candidate-level comparison for CEA-1.13."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_partwise_report_v1"] = "attachment_partwise_report_v1"
    inputs: tuple[AttachmentEvidenceReference, ...]
    whole_prompt: AttachmentEvidenceReference
    part_prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentPartwiseCaseEvaluation, ...]
    task_count: Literal[10] = 10
    part_task_count: Literal[18] = 18
    substantive_part_count: Literal[17] = 17
    structural_part_count: Literal[1] = 1
    model_execution_count: Literal[54] = 54
    whole_correct_count: Annotated[int, Field(ge=0, le=10)]
    part_correct_count: Annotated[int, Field(ge=0, le=10)]
    whole_positive_correct_count: Annotated[int, Field(ge=0, le=8)]
    part_positive_correct_count: Annotated[int, Field(ge=0, le=8)]
    whole_negative_correct_count: Annotated[int, Field(ge=0, le=2)]
    part_negative_correct_count: Annotated[int, Field(ge=0, le=2)]
    recovered_case_count: Annotated[int, Field(ge=0, le=10)]
    regressed_case_count: Annotated[int, Field(ge=0, le=10)]
    stable_whole_case_count: Annotated[int, Field(ge=0, le=10)]
    stable_part_case_count: Annotated[int, Field(ge=0, le=10)]
    strict_finite_output_count: Annotated[int, Field(ge=0, le=54)]
    archived_whole_agreement_count: Annotated[int, Field(ge=0, le=20)]
    unresolved_output_count: Annotated[int, Field(ge=0, le=54)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    outcome: AttachmentPartwiseOutcome
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) != 10:
            raise ValueError("Part-wise report requires ten cases.")
        task_ids = tuple(item.task.id for item in self.cases)
        if task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Part-wise report cases must be ordered and distinct.")
        observations = tuple(
            observation
            for case in self.cases
            for observation in (*case.whole_observations, *case.part_observations)
        )
        actual = (
            sum(item.whole_passed for item in self.cases),
            sum(item.part_passed for item in self.cases),
            sum(item.expected_answer == "Y" and item.whole_passed for item in self.cases),
            sum(item.expected_answer == "Y" and item.part_passed for item in self.cases),
            sum(item.expected_answer == "N" and item.whole_passed for item in self.cases),
            sum(item.expected_answer == "N" and item.part_passed for item in self.cases),
            sum(item.recovered for item in self.cases),
            sum(item.regressed for item in self.cases),
            sum(item.whole_stable for item in self.cases),
            sum(item.part_stable for item in self.cases),
            sum(item.strict_finite_answer for item in observations),
            sum(
                answer == case.archived_whole_answer
                for case in self.cases
                for answer in case.whole_answers
            ),
            sum(_observation_answer(item) is None for item in observations),
        )
        recorded = (
            self.whole_correct_count,
            self.part_correct_count,
            self.whole_positive_correct_count,
            self.part_positive_correct_count,
            self.whole_negative_correct_count,
            self.part_negative_correct_count,
            self.recovered_case_count,
            self.regressed_case_count,
            self.stable_whole_case_count,
            self.stable_part_case_count,
            self.strict_finite_output_count,
            self.archived_whole_agreement_count,
            self.unresolved_output_count,
        )
        if recorded != actual:
            raise ValueError("Part-wise report metrics drifted.")
        expected_outcome = attachment_partwise_outcome(
            strict_finite_output_count=self.strict_finite_output_count,
            unresolved_output_count=self.unresolved_output_count,
            stable_whole_case_count=self.stable_whole_case_count,
            stable_part_case_count=self.stable_part_case_count,
            whole_correct_count=self.whole_correct_count,
            part_correct_count=self.part_correct_count,
            recovered_case_count=self.recovered_case_count,
            regressed_case_count=self.regressed_case_count,
            part_negative_correct_count=self.part_negative_correct_count,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Part-wise report outcome drifted from its evidence.")
        if self.result_fingerprint != attachment_partwise_fingerprint(self):
            raise ValueError("Part-wise report fingerprint drifted.")
        return self


class AttachmentPartwiseStatus(BaseModel):
    """Machine-readable state for one CEA-1.13 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_partwise_status_v1"] = "attachment_partwise_status_v1"
    status: AttachmentPartwisePackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentPartwiseOutcome | None
    model_execution_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentPartwisePackageStatus.COMPLETE
        terminal = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete Part-wise status requires terminal paths.")
        if complete != (self.model_execution_count == 54):
            raise ValueError("Part-wise execution count drifted from status.")
        return self


def build_attachment_remainder_part_tasks(
    task: AttachmentResidualOwnershipTask,
) -> tuple[AttachmentRemainderPartTask, ...]:
    """Build exact Remainder Part tasks in source order."""
    result: list[AttachmentRemainderPartTask] = []
    for number, source_range in enumerate(task.remainder_ranges, start=1):
        fingerprint = attachment_remainder_part_task_fingerprint(
            residual_task_id=task.id,
            edge_filter_task=task.edge_filter_task,
            part_number=number,
            source_range=source_range,
        )
        result.append(
            AttachmentRemainderPartTask(
                id=_identifier("arp", fingerprint),
                residual_task_id=task.id,
                edge_filter_task=task.edge_filter_task,
                part_number=number,
                source_range=source_range,
                kind=attachment_remainder_part_kind(source_range.text),
                task_fingerprint=fingerprint,
            )
        )
    return tuple(result)


def attachment_remainder_part_kind(text: str) -> AttachmentRemainderPartKind:
    """Classify one exact range from Unicode character categories."""
    substantive = any(unicodedata.category(character)[0] in {"L", "N"} for character in text)
    return (
        AttachmentRemainderPartKind.SUBSTANTIVE
        if substantive
        else AttachmentRemainderPartKind.STRUCTURAL
    )


def attachment_remainder_part_model_task_input(
    task: AttachmentEdgeFilterTask,
    part_number: int,
) -> bytes:
    """Render one exact Remainder Part without canonical identifiers or offsets."""
    ranges = attachment_candidate_remainder_ranges(task)
    if type(part_number) is not int or not 1 <= part_number <= len(ranges):
        raise ValueError("Remainder Part renderer requires one valid part number.")
    source_range = ranges[part_number - 1]
    return (
        attachment_edge_filter_model_task_input(task).decode("utf-8").rstrip()
        + "\n\nRemainder Part:\n"
        + f"<remainder>{source_range.text}</remainder>\n"
    ).encode()


def aggregate_attachment_remainder_part_answers(
    part_tasks: tuple[AttachmentRemainderPartTask, ...],
    observations: tuple[AttachmentPartwiseObservation, ...],
) -> Literal["Y", "N", "U"] | None:
    """Aggregate exact Part answers without semantic inference."""
    substantive = tuple(
        item for item in part_tasks if item.kind is AttachmentRemainderPartKind.SUBSTANTIVE
    )
    by_id = {item.part_task_id: _observation_answer(item) for item in observations}
    if set(by_id) != {item.id for item in substantive} or len(by_id) != len(observations):
        raise ValueError("Part Aggregate observation inventory is incomplete or foreign.")
    answers = tuple(by_id[item.id] for item in substantive)
    if any(item is None for item in answers):
        return None
    if "N" in answers:
        return "N"
    if "U" in answers:
        return "U"
    return "Y"


def attachment_partwise_outcome(
    *,
    strict_finite_output_count: int,
    unresolved_output_count: int,
    stable_whole_case_count: int,
    stable_part_case_count: int,
    whole_correct_count: int,
    part_correct_count: int,
    recovered_case_count: int,
    regressed_case_count: int,
    part_negative_correct_count: int,
) -> AttachmentPartwiseOutcome:
    """Classify the CEA-1.13 result from its declared safety gates."""
    complete = strict_finite_output_count == 54 and unresolved_output_count == 0
    supported = (
        complete
        and stable_whole_case_count == 10
        and stable_part_case_count == 10
        and part_correct_count > whole_correct_count
        and recovered_case_count > 0
        and regressed_case_count == 0
        and part_negative_correct_count == 2
    )
    if not complete:
        return AttachmentPartwiseOutcome.INCONCLUSIVE
    if supported:
        return AttachmentPartwiseOutcome.SUPPORTED
    if recovered_case_count:
        return AttachmentPartwiseOutcome.MIXED
    return AttachmentPartwiseOutcome.FALSIFIED


def attachment_remainder_part_task_fingerprint(
    *,
    residual_task_id: str,
    edge_filter_task: AttachmentEdgeFilterTask,
    part_number: int,
    source_range: AttachmentSourceRange,
) -> str:
    """Bind one Part task to authoritative source and its Target Event."""
    return _sha(
        {
            "residual_task_id": residual_task_id,
            "edge_filter_task": edge_filter_task.model_dump(mode="json"),
            "part_number": part_number,
            "source_range": source_range.model_dump(mode="json"),
        }
    )


def attachment_partwise_fingerprint(value: BaseModel) -> str:
    """Return one canonical CEA-1.13 DTO fingerprint."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def _observation_answer(
    observation: AttachmentPartwiseObservation,
) -> Literal["Y", "N", "U"] | None:
    if not observation.strict_finite_answer or observation.decision.answer is None:
        return None
    return observation.decision.answer.value


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
