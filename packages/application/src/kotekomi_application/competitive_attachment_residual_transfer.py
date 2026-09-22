"""Typed evidence and exact rendering for CEA-1.17 Residual Ownership transfer."""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterDecision,
    attachment_edge_filter_model_task_input,
)
from kotekomi_application.competitive_attachment_edge_filter_calibration import (
    AttachmentBinaryMetrics,
)
from kotekomi_application.competitive_attachment_finite_answer_format import (
    AttachmentFiniteLabelEvidence,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSourceRange,
)

_SHA256 = r"^[a-f0-9]{64}$"
_LEADING_THAT = re.compile(r"(?i:that)(?P<space>\s+)")

ATTACHMENT_OWNERSHIP_REMAINDER_RENDERER_ID = "attachment_ownership_remainder_task_v1"


class AttachmentResidualTransferOutcome(StrEnum):
    """Terminal CEA-1.17 transfer result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentResidualTransferGoldCase(BaseModel):
    """One explicit semantic answer for one exact Residual Ownership task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    phase: Literal["development", "validation"]
    expected_answer: Literal["Y", "N"]
    rationale: Annotated[str, Field(min_length=1)]


class AttachmentResidualTransferObservation(BaseModel):
    """One exact model execution and its finite-label evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    repetition: Literal[1, 2]
    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    expected_answer: Literal["Y", "N"]
    decision: AttachmentEdgeFilterDecision
    evidence: AttachmentFiniteLabelEvidence
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: Annotated[str, Field(min_length=1)]
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    strict_finite_answer: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_strict = (
            self.raw_output_text in {"Y", "N", "U"}
            and self.decision.answer is not None
            and self.decision.answer.value == self.raw_output_text
            and self.evidence.finite_label_argmax is self.decision.answer
        )
        if self.strict_finite_answer != expected_strict:
            raise ValueError("Residual transfer finite-answer state drifted.")
        return self


class AttachmentResidualTransferCase(BaseModel):
    """One task, its Gold, and both exact observations."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task: AttachmentResidualOwnershipTask
    gold: AttachmentResidualTransferGoldCase
    displayed_remainder_ranges: tuple[AttachmentSourceRange, ...]
    omitted_remainder_ranges: tuple[AttachmentSourceRange, ...]
    observations: tuple[AttachmentResidualTransferObservation, ...]
    literal_answers: tuple[Literal["Y", "N", "U"], ...]
    threshold_answers: tuple[Literal["Y", "N"], ...]
    stable: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        displayed, omitted = attachment_ownership_remainder_ranges(self.task)
        if (self.displayed_remainder_ranges, self.omitted_remainder_ranges) != (
            displayed,
            omitted,
        ):
            raise ValueError("Residual transfer Remainder evidence drifted.")
        if self.gold.task_id != self.task.id or self.gold.phase != self.task.phase:
            raise ValueError("Residual transfer Gold references a foreign task.")
        if tuple(item.repetition for item in self.observations) != (1, 2):
            raise ValueError("Residual transfer case requires repetitions one and two.")
        answers = tuple(
            item.decision.answer.value for item in self.observations if item.decision.answer
        )
        if self.literal_answers != answers or len(answers) != 2:
            raise ValueError("Residual transfer literal answers drifted.")
        if self.stable != (
            self.literal_answers[0] == self.literal_answers[1]
            and self.threshold_answers[0] == self.threshold_answers[1]
        ):
            raise ValueError("Residual transfer stability drifted.")
        return self


class AttachmentResidualTransferPhaseReport(BaseModel):
    """Occurrence-level literal and calibrated metrics for one phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    threshold: float
    cases: tuple[AttachmentResidualTransferCase, ...]
    literal_metrics: tuple[AttachmentBinaryMetrics, AttachmentBinaryMetrics]
    threshold_metrics: tuple[AttachmentBinaryMetrics, AttachmentBinaryMetrics]
    auroc: tuple[float, float]
    average_precision: tuple[float, float]
    strict_observation_count: Annotated[int, Field(ge=0)]
    stable_case_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_count = 10 if self.phase == "development" else 7
        if len(self.cases) != expected_count or any(
            item.task.phase != self.phase for item in self.cases
        ):
            raise ValueError("Residual transfer phase inventory drifted.")
        if not math.isfinite(self.threshold):
            raise ValueError("Residual transfer threshold must be finite.")
        observations = tuple(item for case in self.cases for item in case.observations)
        if self.strict_observation_count != sum(item.strict_finite_answer for item in observations):
            raise ValueError("Residual transfer strict-output count drifted.")
        if self.stable_case_count != sum(item.stable for item in self.cases):
            raise ValueError("Residual transfer stable-case count drifted.")
        return self


class AttachmentResidualTransferPreflight(BaseModel):
    """Frozen development calibration and validation inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    gold: tuple[AttachmentResidualTransferGoldCase, ...]
    development: AttachmentResidualTransferPhaseReport
    validation_tasks: tuple[AttachmentResidualOwnershipTask, ...]
    expected_model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    selected_threshold: float
    gold_entered_model_task: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.selected_threshold != self.development.threshold:
            raise ValueError("Residual transfer threshold drifted from development.")
        if len(self.gold) != 17 or len(self.validation_tasks) != 7:
            raise ValueError("Residual transfer preflight inventory drifted.")
        if self.result_fingerprint != attachment_residual_transfer_fingerprint(self):
            raise ValueError("Residual transfer preflight fingerprint drifted.")
        return self


class AttachmentResidualTransferReport(BaseModel):
    """Terminal CEA-1.17 transfer report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inputs: tuple[AttachmentEvidenceReference, ...]
    preflight_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    development: AttachmentResidualTransferPhaseReport
    validation: AttachmentResidualTransferPhaseReport
    outcome: AttachmentResidualTransferOutcome
    model_execution_count: Literal[14] = 14
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.development.phase != "development" or self.validation.phase != "validation":
            raise ValueError("Residual transfer report phase drifted.")
        if self.result_fingerprint != attachment_residual_transfer_fingerprint(self):
            raise ValueError("Residual transfer report fingerprint drifted.")
        return self


def attachment_ownership_remainder_ranges(
    task: AttachmentResidualOwnershipTask,
) -> tuple[tuple[AttachmentSourceRange, ...], tuple[AttachmentSourceRange, ...]]:
    """Return exact Remainders, omitting only a leading `that` from the explicit list."""
    source = task.edge_filter_task.source_text
    event = task.edge_filter_task.edge.event_range
    displayed: list[AttachmentSourceRange] = []
    omitted: list[AttachmentSourceRange] = []
    checked_prefix = False
    for value in task.remainder_ranges:
        if not checked_prefix and value.end <= event.start:
            checked_prefix = True
            match = _LEADING_THAT.match(value.text)
            if match is not None:
                split = value.start + match.end()
                omitted.append(
                    AttachmentSourceRange(
                        start=value.start, end=split, text=source[value.start : split]
                    )
                )
                if split < value.end:
                    displayed.append(
                        AttachmentSourceRange(
                            start=split, end=value.end, text=source[split : value.end]
                        )
                    )
                continue
        displayed.append(value)
    return tuple(displayed), tuple(omitted)


def attachment_ownership_remainder_model_task_input(task: AttachmentResidualOwnershipTask) -> bytes:
    """Render the frozen CEA-1.17 task without identifiers or offsets."""
    ranges, _ = attachment_ownership_remainder_ranges(task)
    lines = [
        attachment_edge_filter_model_task_input(task.edge_filter_task).decode().rstrip(),
        "",
        "Candidate Remainder parts:",
    ]
    lines.extend(
        f"R{index}: <remainder>{item.text}</remainder>" for index, item in enumerate(ranges, 1)
    )
    return ("\n".join(lines) + "\n").encode()


def attachment_residual_transfer_fingerprint(value: BaseModel) -> str:
    """Return a canonical CEA-1.17 DTO fingerprint."""
    payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
