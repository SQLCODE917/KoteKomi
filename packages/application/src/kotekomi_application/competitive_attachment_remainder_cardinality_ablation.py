"""Typed evidence for CEA-1.16 Remainder cardinality ablation."""

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
    attachment_edge_filter_model_task_input,
)
from kotekomi_application.competitive_attachment_finite_answer_format import (
    AttachmentFiniteLabelEvidence,
)
from kotekomi_application.competitive_attachment_remainder_enumeration_isolation import (
    ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID,
    AttachmentRemainderEnumerationView,
    attachment_filtered_remainder_ranges,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSourceRange,
)

_SHA256 = r"^[a-f0-9]{64}$"
_ONE_PART_TEXT = " services with FedRAMP authorization"
_FIRST_PART_TEXT = " services"
_SECOND_PART_TEXT = " with FedRAMP authorization"

ATTACHMENT_SPLIT_REMAINDER_RENDERER_ID = "attachment_split_remainder_task_v1"


class AttachmentRemainderCardinalityOutcome(StrEnum):
    """Terminal result for the CEA-1.16 cardinality hypothesis."""

    SUPPORTED = "supported"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentRemainderCardinalityPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.16 package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentRemainderCardinalityView(BaseModel):
    """One content-preserving two-part view of the recovered Remainder."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_cardinality_view_v1"] = (
        "attachment_remainder_cardinality_view_v1"
    )
    id: Annotated[str, Field(pattern=r"^arc_[a-f0-9]{24}$")]
    predecessor_view: AttachmentRemainderEnumerationView
    split_remainder_ranges: tuple[AttachmentSourceRange, AttachmentSourceRange]
    view_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = attachment_split_remainder_ranges(self.predecessor_view.authoritative_task)
        if self.split_remainder_ranges != expected:
            raise ValueError("Remainder cardinality ranges drifted from authoritative source.")
        fingerprint = attachment_remainder_cardinality_view_fingerprint(
            self.predecessor_view,
            expected,
        )
        if self.view_fingerprint != fingerprint or self.id != _identifier("arc", fingerprint):
            raise ValueError("Remainder cardinality view identity drifted.")
        return self


class AttachmentRemainderCardinalityObservation(BaseModel):
    """One bounded model observation for the Split view."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_cardinality_observation_v1"] = (
        "attachment_remainder_cardinality_observation_v1"
    )
    view_id: Annotated[str, Field(pattern=r"^arc_[a-f0-9]{24}$")]
    authoritative_task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    decision: AttachmentEdgeFilterDecision
    execution_record: AttachmentEvidenceReference
    exact_model_input: Annotated[str, Field(min_length=1)]
    raw_output_text: str | None
    finite_label_evidence: AttachmentFiniteLabelEvidence | None
    model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    model_run_status: ModelRunStatus
    output_token_count: Annotated[int, Field(ge=0)] | None
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    strict_finite_answer: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Remainder cardinality observation lacks raw output text.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Remainder cardinality raw output digest drifted.")
        expected_strict = (
            self.raw_output_text in {item.value for item in AttachmentEdgeFilterAnswerValue}
            and self.decision.answer is not None
            and self.decision.answer.value == self.raw_output_text
            and self.output_token_count == 1
            and self.finite_label_evidence is not None
        )
        if self.strict_finite_answer != expected_strict:
            raise ValueError("Remainder cardinality finite-answer result drifted.")
        return self


class AttachmentRemainderCardinalityPreflight(BaseModel):
    """Digest-bound CEA-1.16 input and one-case inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_cardinality_preflight_v1"] = (
        "attachment_remainder_cardinality_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    view: AttachmentRemainderCardinalityView
    expected_answer: Literal["Y"] = "Y"
    sealed_one_part_answers: tuple[Literal["Y"], Literal["Y"]] = ("Y", "Y")
    expected_model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    configured_max_output_tokens: Annotated[int, Field(ge=2)]
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.view.predecessor_view.authoritative_task.id != (
            ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID
        ):
            raise ValueError("Remainder cardinality preflight contains a foreign task.")
        if self.result_fingerprint != attachment_remainder_cardinality_fingerprint(self):
            raise ValueError("Remainder cardinality preflight fingerprint drifted.")
        return self


class AttachmentRemainderCardinalityReport(BaseModel):
    """Terminal CEA-1.16 causal report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_cardinality_report_v1"] = (
        "attachment_remainder_cardinality_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    view: AttachmentRemainderCardinalityView
    expected_answer: Literal["Y"] = "Y"
    sealed_one_part_answers: tuple[Literal["Y"], Literal["Y"]] = ("Y", "Y")
    observation: AttachmentRemainderCardinalityObservation
    outcome: AttachmentRemainderCardinalityOutcome
    model_execution_count: Literal[1] = 1
    false_positive_safety_tested: Literal[False] = False
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        task = self.view.predecessor_view.authoritative_task.edge_filter_task
        observation = self.observation
        if (
            observation.view_id != self.view.id
            or observation.authoritative_task_id != self.view.predecessor_view.authoritative_task.id
            or observation.decision.task_id != task.task_id
            or observation.decision.edge_id != task.edge.id
        ):
            raise ValueError("Remainder cardinality report contains a foreign observation.")
        expected = attachment_remainder_cardinality_outcome(observation)
        if self.outcome is not expected:
            raise ValueError("Remainder cardinality outcome drifted.")
        if self.result_fingerprint != attachment_remainder_cardinality_fingerprint(self):
            raise ValueError("Remainder cardinality report fingerprint drifted.")
        return self


class AttachmentRemainderCardinalityStatus(BaseModel):
    """Machine-readable state for one CEA-1.16 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_cardinality_status_v1"] = (
        "attachment_remainder_cardinality_status_v1"
    )
    status: AttachmentRemainderCardinalityPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentRemainderCardinalityOutcome | None
    model_execution_count: Annotated[int, Field(ge=0, le=1)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentRemainderCardinalityPackageStatus.COMPLETE
        paths = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
        )
        if complete != all(item is not None for item in paths):
            raise ValueError("Remainder cardinality status paths drifted.")
        if complete != (self.outcome is not None and self.model_execution_count == 1):
            raise ValueError("Remainder cardinality terminal state drifted.")
        return self


def build_attachment_remainder_cardinality_view(
    predecessor_view: AttachmentRemainderEnumerationView,
) -> AttachmentRemainderCardinalityView:
    """Build one content-preserving two-part view."""
    ranges = attachment_split_remainder_ranges(predecessor_view.authoritative_task)
    fingerprint = attachment_remainder_cardinality_view_fingerprint(predecessor_view, ranges)
    return AttachmentRemainderCardinalityView(
        id=_identifier("arc", fingerprint),
        predecessor_view=predecessor_view,
        split_remainder_ranges=ranges,
        view_fingerprint=fingerprint,
    )


def attachment_split_remainder_ranges(
    task: AttachmentResidualOwnershipTask,
) -> tuple[AttachmentSourceRange, AttachmentSourceRange]:
    """Split the recovered one-part Remainder without changing its characters."""
    filtered, omitted = attachment_filtered_remainder_ranges(task)
    if len(filtered) != 1 or len(omitted) != 1 or filtered[0].text != _ONE_PART_TEXT:
        raise ValueError("Remainder cardinality one-part control drifted.")
    source = task.edge_filter_task.source_text
    value = filtered[0]
    split = value.start + len(_FIRST_PART_TEXT)
    first = AttachmentSourceRange(start=value.start, end=split, text=source[value.start : split])
    second = AttachmentSourceRange(start=split, end=value.end, text=source[split : value.end])
    if first.text != _FIRST_PART_TEXT or second.text != _SECOND_PART_TEXT:
        raise ValueError("Remainder cardinality split boundary drifted.")
    return first, second


def attachment_split_remainder_model_task_input(
    task: AttachmentResidualOwnershipTask,
) -> bytes:
    """Render the unchanged task with two adjacent Remainder parts."""
    ranges = attachment_split_remainder_ranges(task)
    lines = [
        attachment_edge_filter_model_task_input(task.edge_filter_task).decode("utf-8").rstrip(),
        "",
        "Candidate Remainder parts:",
    ]
    lines.extend(
        f"R{index}: <remainder>{item.text}</remainder>"
        for index, item in enumerate(ranges, start=1)
    )
    return ("\n".join(lines) + "\n").encode()


def attachment_remainder_cardinality_outcome(
    observation: AttachmentRemainderCardinalityObservation,
) -> AttachmentRemainderCardinalityOutcome:
    """Classify the one-call cardinality hypothesis."""
    evidence = observation.finite_label_evidence
    if (
        not observation.strict_finite_answer
        or observation.decision.answer is None
        or evidence is None
        or observation.decision.answer is not evidence.finite_label_argmax
    ):
        return AttachmentRemainderCardinalityOutcome.INCONCLUSIVE
    if observation.decision.answer is AttachmentEdgeFilterAnswerValue.NO:
        return AttachmentRemainderCardinalityOutcome.SUPPORTED
    if observation.decision.answer is AttachmentEdgeFilterAnswerValue.YES:
        return AttachmentRemainderCardinalityOutcome.FALSIFIED
    return AttachmentRemainderCardinalityOutcome.INCONCLUSIVE


def attachment_remainder_cardinality_view_fingerprint(
    predecessor_view: AttachmentRemainderEnumerationView,
    split_ranges: tuple[AttachmentSourceRange, AttachmentSourceRange],
) -> str:
    """Bind the Split view to predecessor evidence and exact ranges."""
    return _sha(
        {
            "predecessor_view": predecessor_view.model_dump(mode="json"),
            "split_remainder_ranges": [item.model_dump(mode="json") for item in split_ranges],
        }
    )


def attachment_remainder_cardinality_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.16 DTO."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
