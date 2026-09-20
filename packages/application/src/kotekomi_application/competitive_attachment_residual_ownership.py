"""Typed evidence for the CEA-1.7 Residual Ownership diagnostic."""

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
    AttachmentEdgeFilterTask,
    attachment_edge_filter_model_task_input,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSourceRange,
)

_SHA256 = r"^[a-f0-9]{64}$"
ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID = "attachment_residual_remainder_task_v1"


class AttachmentResidualOwnershipOutcome(StrEnum):
    """Development result for one Residual Ownership task contract."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class AttachmentResidualOwnershipPackageStatus(StrEnum):
    """Lifecycle stage for one CEA-1.7 experiment package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentResidualOwnershipTask(BaseModel):
    """One Gold-free Residual Edge selected from exact source ranges."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_ownership_task_v1"] = (
        "attachment_residual_ownership_task_v1"
    )
    id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    phase: Literal["development", "validation"]
    edge_filter_task: AttachmentEdgeFilterTask
    remainder_ranges: tuple[AttachmentSourceRange, ...]
    task_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.edge_filter_task.edge.phase != self.phase:
            raise ValueError("Residual Ownership task contains a foreign phase Edge.")
        expected_ranges = attachment_candidate_remainder_ranges(self.edge_filter_task)
        if self.remainder_ranges != expected_ranges:
            raise ValueError("Residual Ownership Candidate Remainder drifted.")
        if attachment_contained_foreign_event_ids(self.edge_filter_task):
            raise ValueError("Residual Ownership task contains a Foreign Event.")
        expected_fingerprint = attachment_residual_ownership_task_fingerprint(
            self.edge_filter_task,
            expected_ranges,
        )
        if self.task_fingerprint != expected_fingerprint:
            raise ValueError("Residual Ownership task fingerprint drifted.")
        if self.id != _identifier("aro", expected_fingerprint):
            raise ValueError("Residual Ownership task ID drifted.")
        return self


class AttachmentResidualOwnershipObservation(BaseModel):
    """One Qwen result scored against one occurrence-level Gold answer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_ownership_observation_v1"] = (
        "attachment_residual_ownership_observation_v1"
    )
    repetition: Literal[1, 2]
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    edge_id: Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]
    expected_answer: Literal["Y", "N"]
    decision: AttachmentEdgeFilterDecision
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: str | None
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision.edge_id != self.edge_id:
            raise ValueError("Residual Ownership decision references a foreign Edge.")
        actual = (
            self.decision.answer.value
            if self.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            and self.decision.answer is not None
            else None
        )
        if self.passed != (actual == self.expected_answer):
            raise ValueError("Residual Ownership observation result drifted.")
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Residual Ownership raw output text is missing.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Residual Ownership raw output digest drifted.")
        return self


class AttachmentResidualOwnershipCaseEvaluation(BaseModel):
    """Two repetitions for one occurrence-specific Residual Edge."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_ownership_case_evaluation_v1"] = (
        "attachment_residual_ownership_case_evaluation_v1"
    )
    task: AttachmentResidualOwnershipTask
    expected_answer: Literal["Y", "N"]
    observations: tuple[AttachmentResidualOwnershipObservation, ...]
    stable_semantic_result: bool
    passed_both_repetitions: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.repetition for item in self.observations) != (1, 2):
            raise ValueError("Residual Ownership case requires repetitions one and two.")
        if any(
            item.task_id != self.task.id
            or item.edge_id != self.task.edge_filter_task.edge.id
            or item.expected_answer != self.expected_answer
            for item in self.observations
        ):
            raise ValueError("Residual Ownership case observation drifted from its task.")
        semantic_results = tuple(
            (item.decision.status, item.decision.answer) for item in self.observations
        )
        if self.stable_semantic_result != (semantic_results[0] == semantic_results[1]):
            raise ValueError("Residual Ownership stability result drifted.")
        if self.passed_both_repetitions != all(item.passed for item in self.observations):
            raise ValueError("Residual Ownership case pass result drifted.")
        return self


class AttachmentResidualOwnershipReport(BaseModel):
    """Terminal development report for the CEA-1.7 diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_ownership_report_v1"] = (
        "attachment_residual_ownership_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentResidualOwnershipCaseEvaluation, ...]
    task_count: Literal[10]
    observation_count: Literal[20]
    expected_positive_count: Literal[7]
    expected_negative_count: Literal[3]
    correct_observation_count: Annotated[int, Field(ge=0, le=20)]
    positive_retention_count: Annotated[int, Field(ge=0, le=14)]
    negative_rejection_count: Annotated[int, Field(ge=0, le=6)]
    stable_case_count: Annotated[int, Field(ge=0, le=10)]
    unresolved_observation_count: Annotated[int, Field(ge=0, le=20)]
    model_execution_count: Literal[20]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    outcome: AttachmentResidualOwnershipOutcome
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) != self.task_count:
            raise ValueError("Residual Ownership report task inventory drifted.")
        task_ids = tuple(item.task.id for item in self.cases)
        if task_ids != tuple(sorted(task_ids)) or len(set(task_ids)) != len(task_ids):
            raise ValueError("Residual Ownership cases must be ordered and distinct.")
        if sum(item.expected_answer == "Y" for item in self.cases) != 7:
            raise ValueError("Residual Ownership positive inventory drifted.")
        if sum(item.expected_answer == "N" for item in self.cases) != 3:
            raise ValueError("Residual Ownership negative inventory drifted.")
        observations = tuple(item for case in self.cases for item in case.observations)
        actual_counts = (
            len(observations),
            sum(item.passed for item in observations),
            sum(
                item.expected_answer == "Y"
                and item.decision.answer is AttachmentEdgeFilterAnswerValue.YES
                and item.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
                for item in observations
            ),
            sum(
                item.expected_answer == "N"
                and item.decision.answer is AttachmentEdgeFilterAnswerValue.NO
                and item.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
                for item in observations
            ),
            sum(item.stable_semantic_result for item in self.cases),
            sum(
                item.decision.status is not AttachmentEdgeFilterDecisionStatus.COMPLETE
                for item in observations
            ),
        )
        recorded_counts = (
            self.observation_count,
            self.correct_observation_count,
            self.positive_retention_count,
            self.negative_rejection_count,
            self.stable_case_count,
            self.unresolved_observation_count,
        )
        if recorded_counts != actual_counts:
            raise ValueError("Residual Ownership report metrics drifted.")
        positive_loss = any(
            item.expected_answer == "Y" and not item.passed for item in observations
        )
        supported = (
            self.correct_observation_count == 20
            and self.stable_case_count == 10
            and self.unresolved_observation_count == 0
        )
        expected_outcome = (
            AttachmentResidualOwnershipOutcome.SUPPORTED
            if supported
            else AttachmentResidualOwnershipOutcome.FALSIFIED
            if positive_loss
            else AttachmentResidualOwnershipOutcome.MIXED
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Residual Ownership outcome drifted from its observations.")
        if self.result_fingerprint != attachment_residual_ownership_fingerprint(self):
            raise ValueError("Residual Ownership report fingerprint drifted.")
        return self


class AttachmentResidualOwnershipPreflight(BaseModel):
    """Gold-free CEA-1.7 selection and input inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_ownership_preflight_v1"] = (
        "attachment_residual_ownership_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    development_mixed_edge_ids: tuple[str, ...]
    development_tasks: tuple[AttachmentResidualOwnershipTask, ...]
    validation_mixed_edge_ids: tuple[str, ...]
    validation_tasks: tuple[AttachmentResidualOwnershipTask, ...]
    gold_entered_selection: Literal[False] = False
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        inventories = (
            (self.development_mixed_edge_ids, 12),
            (self.validation_mixed_edge_ids, 2),
        )
        for values, expected_count in inventories:
            if len(values) != expected_count or values != tuple(sorted(set(values))):
                raise ValueError("Residual Ownership mixed Edge inventory drifted.")
        tasks = (
            (self.development_tasks, "development", 10),
            (self.validation_tasks, "validation", 7),
        )
        for values, phase, expected_count in tasks:
            if len(values) != expected_count:
                raise ValueError("Residual Ownership task inventory drifted.")
            if any(item.phase != phase for item in values):
                raise ValueError("Residual Ownership preflight contains a foreign phase task.")
            identifiers = tuple(item.id for item in values)
            if identifiers != tuple(sorted(set(identifiers))):
                raise ValueError("Residual Ownership tasks must be ordered and distinct.")
        if self.result_fingerprint != attachment_residual_ownership_fingerprint(self):
            raise ValueError("Residual Ownership preflight fingerprint drifted.")
        return self


class AttachmentResidualOwnershipStatus(BaseModel):
    """Machine-readable state for one CEA-1.7 experiment package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_residual_ownership_status_v1"] = (
        "attachment_residual_ownership_status_v1"
    )
    status: AttachmentResidualOwnershipPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentResidualOwnershipOutcome | None
    model_execution_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentResidualOwnershipPackageStatus.COMPLETE
        terminal_values = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
        )
        if complete != all(item is not None for item in terminal_values):
            raise ValueError("Complete Residual Ownership status requires terminal paths.")
        if complete != (self.model_execution_count == 20):
            raise ValueError("Residual Ownership execution count drifted from status.")
        return self


def build_attachment_residual_ownership_task(
    task: AttachmentEdgeFilterTask,
) -> AttachmentResidualOwnershipTask:
    """Build one Gold-free task for a Containment Edge without a Foreign Event."""
    remainder = attachment_candidate_remainder_ranges(task)
    fingerprint = attachment_residual_ownership_task_fingerprint(task, remainder)
    return AttachmentResidualOwnershipTask(
        id=_identifier("aro", fingerprint),
        phase=task.edge.phase,
        edge_filter_task=task,
        remainder_ranges=remainder,
        task_fingerprint=fingerprint,
    )


def attachment_candidate_remainder_ranges(
    task: AttachmentEdgeFilterTask,
) -> tuple[AttachmentSourceRange, ...]:
    """Return exact Candidate characters outside the Target Event."""
    candidate = task.edge.candidate_range
    event = task.edge.event_range
    if not _properly_contains(candidate, event):
        raise ValueError("Residual Ownership requires proper Target Event containment.")
    ranges: list[AttachmentSourceRange] = []
    for start, end in ((candidate.start, event.start), (event.end, candidate.end)):
        if start == end:
            continue
        ranges.append(
            AttachmentSourceRange(
                start=start,
                end=end,
                text=task.source_text[start:end],
            )
        )
    return tuple(ranges)


def attachment_residual_remainder_model_task_input(
    task: AttachmentEdgeFilterTask,
) -> bytes:
    """Render exact Candidate Remainder parts without identifiers or offsets."""
    ranges = attachment_candidate_remainder_ranges(task)
    lines = [
        attachment_edge_filter_model_task_input(task).decode("utf-8").rstrip(),
        "",
        "Candidate Remainder parts:",
    ]
    lines.extend(
        f"R{index}: <remainder>{item.text}</remainder>"
        for index, item in enumerate(ranges, start=1)
    )
    return ("\n".join(lines) + "\n").encode()


def attachment_contained_foreign_event_ids(
    task: AttachmentEdgeFilterTask,
) -> tuple[str, ...]:
    """Return Other Event IDs fully contained by the Candidate."""
    candidate = task.edge.candidate_range
    return tuple(
        option.source_grounded_event_id
        for option in task.event_options
        if option.source_grounded_event_id != task.edge.source_grounded_event_id
        and candidate.start <= option.start
        and candidate.end >= option.end
    )


def attachment_residual_ownership_task_fingerprint(
    task: AttachmentEdgeFilterTask,
    remainder_ranges: tuple[AttachmentSourceRange, ...],
) -> str:
    """Bind one Residual Ownership task to exact source input."""
    return _sha(
        {
            "edge_filter_task": task.model_dump(mode="json"),
            "remainder_ranges": [item.model_dump(mode="json") for item in remainder_ranges],
        }
    )


def attachment_residual_ownership_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.7 report draft."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def _properly_contains(candidate: AttachmentSourceRange, event: AttachmentSourceRange) -> bool:
    return (
        candidate.start <= event.start
        and candidate.end >= event.end
        and (candidate.start, candidate.end) != (event.start, event.end)
    )


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
