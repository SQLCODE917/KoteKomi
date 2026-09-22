"""Typed evidence for the CEA-1.22 Nested Event Ownership diagnostic."""

from __future__ import annotations

import hashlib
import json
from base64 import b64decode
from binascii import Error as BinasciiError
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
)

_SHA256 = r"^[a-f0-9]{64}$"

ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID = "competitive_attachment_nested_event_ownership_v1"
ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID = "competitive_attachment_nested_event_ownership_v1"
ATTACHMENT_NESTED_EVENT_OWNERSHIP_NONTHINKING_RENDERER_ID = (
    "competitive_attachment_nested_event_ownership_qwen3_nonthinking_v1"
)
QWEN3_NONTHINKING_CONTROL = "/no_think"


class AttachmentNestedEventOutcome(StrEnum):
    """The terminal CEA-1.22 diagnostic result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentNestedEventCase(BaseModel):
    """One Head-Aligned Candidate with at least one Contained Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^neo_[a-f0-9]{24}$")]
    blind_case_id: Annotated[str, Field(pattern=r"^ubr_[a-f0-9]{24}$")]
    phase: Literal["development", "validation"]
    task: AttachmentEdgeFilterTask
    contained_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    expected_answer: Literal["Y", "N"]
    expected_rationale: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        target = next(
            item for item in self.task.event_options if item.label == self.task.target_event_label
        )
        candidate = self.task.candidate
        expected_contained = tuple(
            item.source_grounded_event_id
            for item in self.task.event_options
            if item.source_grounded_event_id != target.source_grounded_event_id
            and candidate.start <= item.start
            and item.end <= candidate.end
        )
        if not expected_contained:
            raise ValueError("Nested Event case requires one Contained Event.")
        if self.contained_event_ids != expected_contained:
            raise ValueError("Nested Event inventory drifted from exact source containment.")
        if self.phase != self.task.edge.phase:
            raise ValueError("Nested Event case phase drifted from its task.")
        if not (candidate.start <= target.start and target.end <= candidate.end):
            raise ValueError("Nested Event target must occur inside the Candidate.")
        expected_id = attachment_nested_event_case_id(
            blind_case_id=self.blind_case_id,
            task_id=self.task.task_id,
        )
        if self.id != expected_id:
            raise ValueError("Nested Event case ID drifted.")
        return self


class AttachmentNestedEventPreflight(BaseModel):
    """The complete five-case input contract before Qwen execution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_nested_event_preflight_v1"] = (
        "attachment_nested_event_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentNestedEventCase, ...]
    case_count: Annotated[int, Field(ge=0)]
    expected_yes_count: Annotated[int, Field(ge=0)]
    expected_no_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ordered = tuple(
            sorted(
                self.cases,
                key=lambda item: (
                    item.phase,
                    item.task.edge.source_text_sha256,
                    item.task.candidate.start,
                    item.task.candidate.end,
                    item.task.edge.event_range.start,
                    item.id,
                ),
            )
        )
        if self.cases != ordered:
            raise ValueError("Nested Event cases must use canonical order.")
        if len({item.id for item in self.cases}) != len(self.cases):
            raise ValueError("Nested Event cases must be distinct.")
        observed = (self.case_count, self.expected_yes_count, self.expected_no_count)
        expected = (
            len(self.cases),
            sum(item.expected_answer == "Y" for item in self.cases),
            sum(item.expected_answer == "N" for item in self.cases),
        )
        if observed != expected:
            raise ValueError("Nested Event preflight counts drifted.")
        if self.result_fingerprint != attachment_nested_event_fingerprint(self):
            raise ValueError("Nested Event preflight fingerprint drifted.")
        return self


class AttachmentNestedEventObservation(BaseModel):
    """One exact model execution result for one diagnostic case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: Annotated[str, Field(pattern=r"^neo_[a-f0-9]{24}$")]
    repetition: Literal[1, 2]
    decision: AttachmentEdgeFilterDecision
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_base64: str | None
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)] | None
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    runtime_invoked: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.raw_output_base64 is None:
            if self.decision.raw_output_sha256 is not None:
                raise ValueError("Nested Event raw output evidence is missing.")
        else:
            try:
                raw = b64decode(self.raw_output_base64, validate=True)
            except (BinasciiError, ValueError) as error:
                raise ValueError("Nested Event raw output must be valid base64.") from error
            if hashlib.sha256(raw).hexdigest() != self.decision.raw_output_sha256:
                raise ValueError("Nested Event raw output digest drifted.")
        return self


class AttachmentNestedEventEvaluation(BaseModel):
    """Two repeated decisions evaluated against one blind label."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case: AttachmentNestedEventCase
    observations: tuple[AttachmentNestedEventObservation, ...]
    complete: bool
    stable: bool
    correct_decision_count: Annotated[int, Field(ge=0, le=2)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.repetition for item in self.observations) != (1, 2):
            raise ValueError("Nested Event evaluation requires repetitions one and two.")
        if any(item.case_id != self.case.id for item in self.observations):
            raise ValueError("Nested Event evaluation contains a foreign observation.")
        answers = tuple(item.decision.answer for item in self.observations)
        expected_complete = all(
            item.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            for item in self.observations
        )
        expected_stable = expected_complete and answers[0] is answers[1]
        expected_correct = sum(
            answer is not None and answer.value == self.case.expected_answer for answer in answers
        )
        if (self.complete, self.stable, self.correct_decision_count) != (
            expected_complete,
            expected_stable,
            expected_correct,
        ):
            raise ValueError("Nested Event evaluation result drifted.")
        return self


class AttachmentNestedEventReport(BaseModel):
    """The terminal CEA-1.22 diagnostic report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_nested_event_report_v1"] = (
        "attachment_nested_event_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    evaluations: tuple[AttachmentNestedEventEvaluation, ...]
    outcome: AttachmentNestedEventOutcome
    case_count: Annotated[int, Field(ge=0)]
    observation_count: Annotated[int, Field(ge=0)]
    complete_observation_count: Annotated[int, Field(ge=0)]
    unresolved_observation_count: Annotated[int, Field(ge=0)]
    stable_case_count: Annotated[int, Field(ge=0)]
    positive_correct_decision_count: Annotated[int, Field(ge=0)]
    negative_correct_decision_count: Annotated[int, Field(ge=0)]
    model_identity_digests: tuple[Annotated[str, Field(pattern=_SHA256)], ...]
    model_execution_count: Annotated[int, Field(ge=0)]
    model_elapsed_milliseconds: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        observations = tuple(
            observation
            for evaluation in self.evaluations
            for observation in evaluation.observations
        )
        positives = tuple(item for item in self.evaluations if item.case.expected_answer == "Y")
        negatives = tuple(item for item in self.evaluations if item.case.expected_answer == "N")
        observed = (
            self.case_count,
            self.observation_count,
            self.complete_observation_count,
            self.unresolved_observation_count,
            self.stable_case_count,
            self.positive_correct_decision_count,
            self.negative_correct_decision_count,
            self.model_identity_digests,
            self.model_execution_count,
            self.model_elapsed_milliseconds,
        )
        expected = (
            len(self.evaluations),
            len(observations),
            sum(
                item.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
                for item in observations
            ),
            sum(
                item.decision.status is not AttachmentEdgeFilterDecisionStatus.COMPLETE
                for item in observations
            ),
            sum(item.stable for item in self.evaluations),
            sum(item.correct_decision_count for item in positives),
            sum(item.correct_decision_count for item in negatives),
            tuple(
                sorted(
                    {
                        item.model_identity_digest
                        for item in observations
                        if item.model_identity_digest is not None
                    }
                )
            ),
            sum(item.runtime_invoked for item in observations),
            sum(item.elapsed_milliseconds for item in observations),
        )
        if observed != expected:
            raise ValueError("Nested Event report counts drifted.")
        expected_outcome = classify_attachment_nested_event_outcome(evaluations=self.evaluations)
        if self.outcome is not expected_outcome:
            raise ValueError("Nested Event report outcome drifted.")
        if self.result_fingerprint != attachment_nested_event_fingerprint(self):
            raise ValueError("Nested Event report fingerprint drifted.")
        return self


def attachment_nested_event_ownership_model_task_input(
    task: AttachmentEdgeFilterTask,
) -> bytes:
    """Render the bounded semantic task without canonical identifiers or offsets."""
    target = next(item for item in task.event_options if item.label == task.target_event_label)
    candidate = task.candidate
    if not (candidate.start <= target.start and target.end <= candidate.end):
        raise ValueError("Nested Event task target must occur inside the Candidate.")
    contained = tuple(
        item
        for item in task.event_options
        if item.source_grounded_event_id != target.source_grounded_event_id
        and candidate.start <= item.start
        and item.end <= candidate.end
    )
    if not contained:
        raise ValueError("Nested Event task requires one Contained Event.")
    lines = [
        "Passage:",
        task.source_text,
        "",
        "Candidate:",
        json.dumps(candidate.text, ensure_ascii=False),
        "",
        "Target Event:",
        json.dumps(target.text, ensure_ascii=False),
        "",
        "Contained Events:",
    ]
    lines.extend(
        f"C{index}: {json.dumps(item.text, ensure_ascii=False)}"
        for index, item in enumerate(contained, start=1)
    )
    return ("\n".join(lines) + "\n").encode()


def attachment_nested_event_ownership_nonthinking_model_task_input(
    task: AttachmentEdgeFilterTask,
) -> bytes:
    """Append the Qwen3 Non-Thinking Control after the complete semantic task."""
    semantic_task = attachment_nested_event_ownership_model_task_input(task)
    return semantic_task + b"\n" + QWEN3_NONTHINKING_CONTROL.encode() + b"\n"


def attachment_nested_event_case_id(*, blind_case_id: str, task_id: str) -> str:
    """Return one stable case ID."""
    digest = hashlib.sha256(f"{blind_case_id}\x1f{task_id}".encode()).hexdigest()
    return "neo_" + digest[:24]


def classify_attachment_nested_event_outcome(
    *,
    evaluations: tuple[AttachmentNestedEventEvaluation, ...],
) -> AttachmentNestedEventOutcome:
    """Classify the five-case, two-repetition diagnostic."""
    if any(not item.complete or not item.stable for item in evaluations):
        return AttachmentNestedEventOutcome.INCONCLUSIVE
    negatives = tuple(item for item in evaluations if item.case.expected_answer == "N")
    if any(item.correct_decision_count != 2 for item in negatives):
        return AttachmentNestedEventOutcome.FALSIFIED
    positive_correct = sum(
        item.correct_decision_count for item in evaluations if item.case.expected_answer == "Y"
    )
    if positive_correct == 8:
        return AttachmentNestedEventOutcome.SUPPORTED
    if positive_correct >= 6:
        return AttachmentNestedEventOutcome.MIXED
    return AttachmentNestedEventOutcome.FALSIFIED


def attachment_nested_event_fingerprint(value: BaseModel) -> str:
    """Return one canonical CEA-1.22 fingerprint."""
    payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
