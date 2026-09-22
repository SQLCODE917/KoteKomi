"""Typed evidence for the CEA-1.23 Nested Event ownership transfer experiment."""

from __future__ import annotations

import hashlib
import json
from base64 import b64decode
from binascii import Error as BinasciiError
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterTask,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentNestedTransferOutcome(StrEnum):
    """Terminal interpretation of the CEA-1.23 transfer experiment."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentNestedTransferSelector(BaseModel):
    """One source-exact case specification without an expected answer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: Annotated[str, Field(pattern=r"^NET-[0-9]{3}$")]
    source_segment_id: Annotated[str, Field(pattern=r"^src_[a-f0-9]{24}$")]
    candidate_text: Annotated[str, Field(min_length=1)]
    target_event_text: Annotated[str, Field(min_length=1)]
    contained_event_texts: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.contained_event_texts:
            raise ValueError("A transfer selector requires one Contained Event.")
        if self.contained_event_texts != tuple(dict.fromkeys(self.contained_event_texts)):
            raise ValueError("Transfer selector Contained Events must be distinct.")
        return self


class AttachmentNestedTransferSelectorCatalog(BaseModel):
    """The frozen, answer-free CEA-1.23 case specification."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_nested_transfer_selector_catalog_v1"] = (
        "attachment_nested_transfer_selector_catalog_v1"
    )
    source_catalog_path: Literal["docs/organization-mention-held-out-gold-v1.json"]
    source_catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    selectors: tuple[AttachmentNestedTransferSelector, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_ids = tuple(f"NET-{index:03d}" for index in range(1, 21))
        if tuple(item.case_id for item in self.selectors) != expected_ids:
            raise ValueError("The transfer selector catalog requires NET-001 through NET-020.")
        source_ids = tuple(item.source_segment_id for item in self.selectors)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("Transfer selectors must use distinct SourceSegments.")
        return self


class AttachmentNestedTransferCase(BaseModel):
    """One resolved cross-document ownership case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")]
    selector_id: Annotated[str, Field(pattern=r"^NET-[0-9]{3}$")]
    fixture_path: Annotated[str, Field(min_length=1)]
    source_segment_id: Annotated[str, Field(pattern=r"^src_[a-f0-9]{24}$")]
    task: AttachmentEdgeFilterTask
    contained_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.source_segment_id != self.task.edge.source_segment_id:
            raise ValueError("Transfer case SourceSegment drifted from its task.")
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
        if self.contained_event_ids != expected_contained:
            raise ValueError("Transfer case Contained Event inventory drifted.")
        expected_id = attachment_nested_transfer_case_id(
            selector_id=self.selector_id,
            task_id=self.task.task_id,
        )
        if self.id != expected_id:
            raise ValueError("Transfer case ID drifted.")
        return self


class AttachmentNestedTransferCatalog(BaseModel):
    """The exact twenty-case transfer inventory before semantic labeling."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_nested_transfer_catalog_v1"] = (
        "attachment_nested_transfer_catalog_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentNestedTransferCase, ...]
    case_count: Literal[20]
    document_count: Literal[2]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.selector_id for item in self.cases) != tuple(
            f"NET-{index:03d}" for index in range(1, 21)
        ):
            raise ValueError("Transfer cases must use selector order.")
        if len({item.id for item in self.cases}) != len(self.cases):
            raise ValueError("Transfer cases must be distinct.")
        if len({item.source_segment_id for item in self.cases}) != self.case_count:
            raise ValueError("Transfer cases must use distinct SourceSegments.")
        if len({item.fixture_path for item in self.cases}) != self.document_count:
            raise ValueError("Transfer cases must use exactly two Documents.")
        if self.result_fingerprint != attachment_nested_transfer_fingerprint(self):
            raise ValueError("Transfer catalog fingerprint drifted.")
        return self


class AttachmentNestedTransferDecision(BaseModel):
    """One blind semantic Ownership Label."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")]
    answer: Literal["Y", "N", "U"]
    rationale: Annotated[str, Field(min_length=1, max_length=1000)]


class AttachmentNestedTransferSubmission(BaseModel):
    """One complete blind review response."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_nested_transfer_submission_v1"] = (
        "attachment_nested_transfer_submission_v1"
    )
    reviewer: Annotated[str, Field(min_length=1, max_length=200)]
    decisions: tuple[AttachmentNestedTransferDecision, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.case_id for item in self.decisions)
        if len(set(ids)) != len(ids):
            raise ValueError("Transfer review decisions must be distinct.")
        if sum(item.answer == "Y" for item in self.decisions) < 6:
            raise ValueError("Transfer review requires at least six Y labels.")
        if sum(item.answer == "N" for item in self.decisions) < 6:
            raise ValueError("Transfer review requires at least six N labels.")
        return self


class AttachmentNestedTransferObservation(BaseModel):
    """One exact Qwen execution for one transfer case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")]
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
                raise ValueError("Transfer observation lacks raw output evidence.")
        else:
            try:
                raw = b64decode(self.raw_output_base64, validate=True)
            except (BinasciiError, ValueError) as error:
                raise ValueError("Transfer raw output must be valid base64.") from error
            if hashlib.sha256(raw).hexdigest() != self.decision.raw_output_sha256:
                raise ValueError("Transfer raw output digest drifted.")
        return self


class AttachmentNestedTransferEvaluation(BaseModel):
    """One Qwen decision evaluated against one blind semantic label."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case: AttachmentNestedTransferCase
    expected: AttachmentNestedTransferDecision
    observation: AttachmentNestedTransferObservation
    complete: bool
    correct: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.expected.case_id != self.case.id or self.observation.case_id != self.case.id:
            raise ValueError("Transfer evaluation contains a foreign case.")
        answer = self.observation.decision.answer
        expected_complete = (
            self.observation.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
        )
        expected_correct = answer is not None and answer.value == self.expected.answer
        if (self.complete, self.correct) != (expected_complete, expected_correct):
            raise ValueError("Transfer evaluation result drifted.")
        return self


class AttachmentNestedTransferGroupKind(StrEnum):
    """One declared transfer-report grouping dimension."""

    DOCUMENT = "document"
    EXPECTED_LABEL = "expected_label"


class AttachmentNestedTransferGroupMetrics(BaseModel):
    """Exact metrics for one Document or expected-label group."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    group_kind: AttachmentNestedTransferGroupKind
    group_value: Annotated[str, Field(min_length=1)]
    case_count: Annotated[int, Field(ge=1)]
    correct_count: Annotated[int, Field(ge=0)]
    unresolved_count: Annotated[int, Field(ge=0)]
    accuracy: Annotated[float, Field(ge=0.0, le=1.0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.correct_count > self.case_count or self.unresolved_count > self.case_count:
            raise ValueError("Transfer group counts cannot exceed its case count.")
        if self.accuracy != _ratio(self.correct_count, self.case_count):
            raise ValueError("Transfer group accuracy drifted.")
        return self


class AttachmentNestedTransferReport(BaseModel):
    """The terminal CEA-1.23 transfer report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_nested_transfer_report_v1"] = (
        "attachment_nested_transfer_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    reviewer: Annotated[str, Field(min_length=1, max_length=200)]
    evaluations: tuple[AttachmentNestedTransferEvaluation, ...]
    outcome: AttachmentNestedTransferOutcome
    case_count: Literal[20]
    expected_yes_count: Annotated[int, Field(ge=0)]
    expected_no_count: Annotated[int, Field(ge=0)]
    expected_unclear_count: Annotated[int, Field(ge=0)]
    complete_count: Annotated[int, Field(ge=0)]
    correct_count: Annotated[int, Field(ge=0)]
    actual_yes_count: Annotated[int, Field(ge=0)]
    actual_no_count: Annotated[int, Field(ge=0)]
    actual_unclear_count: Annotated[int, Field(ge=0)]
    invalid_output_count: Annotated[int, Field(ge=0)]
    input_blocked_count: Annotated[int, Field(ge=0)]
    model_failed_count: Annotated[int, Field(ge=0)]
    accuracy: Annotated[float, Field(ge=0.0, le=1.0)]
    yes_recall: Annotated[float, Field(ge=0.0, le=1.0)]
    no_recall: Annotated[float, Field(ge=0.0, le=1.0)]
    unresolved_count: Annotated[int, Field(ge=0)]
    group_metrics: tuple[AttachmentNestedTransferGroupMetrics, ...]
    model_identity_digests: tuple[Annotated[str, Field(pattern=_SHA256)], ...]
    model_execution_count: Annotated[int, Field(ge=0)]
    model_elapsed_milliseconds: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        yes = tuple(item for item in self.evaluations if item.expected.answer == "Y")
        no = tuple(item for item in self.evaluations if item.expected.answer == "N")
        unclear = tuple(item for item in self.evaluations if item.expected.answer == "U")
        observations = tuple(item.observation for item in self.evaluations)
        expected = (
            len(yes),
            len(no),
            len(unclear),
            sum(item.complete for item in self.evaluations),
            sum(item.correct for item in self.evaluations),
            sum(
                item.observation.decision.answer is AttachmentEdgeFilterAnswerValue.YES
                for item in self.evaluations
            ),
            sum(
                item.observation.decision.answer is AttachmentEdgeFilterAnswerValue.NO
                for item in self.evaluations
            ),
            sum(
                item.observation.decision.status is AttachmentEdgeFilterDecisionStatus.UNCLEAR
                for item in self.evaluations
            ),
            sum(
                item.observation.decision.status
                is AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT
                for item in self.evaluations
            ),
            sum(
                item.observation.decision.status is AttachmentEdgeFilterDecisionStatus.INPUT_BLOCKED
                for item in self.evaluations
            ),
            sum(
                item.observation.decision.status is AttachmentEdgeFilterDecisionStatus.MODEL_FAILED
                for item in self.evaluations
            ),
            _ratio(sum(item.correct for item in self.evaluations), len(self.evaluations)),
            _ratio(sum(item.correct for item in yes), len(yes)),
            _ratio(sum(item.correct for item in no), len(no)),
            sum(not item.complete for item in self.evaluations),
            attachment_nested_transfer_group_metrics(self.evaluations),
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
        observed = (
            self.expected_yes_count,
            self.expected_no_count,
            self.expected_unclear_count,
            self.complete_count,
            self.correct_count,
            self.actual_yes_count,
            self.actual_no_count,
            self.actual_unclear_count,
            self.invalid_output_count,
            self.input_blocked_count,
            self.model_failed_count,
            self.accuracy,
            self.yes_recall,
            self.no_recall,
            self.unresolved_count,
            self.group_metrics,
            self.model_identity_digests,
            self.model_execution_count,
            self.model_elapsed_milliseconds,
        )
        if observed != expected:
            raise ValueError("Transfer report metrics drifted.")
        if self.outcome is not classify_attachment_nested_transfer_outcome(
            evaluations=self.evaluations
        ):
            raise ValueError("Transfer report outcome drifted.")
        if self.result_fingerprint != attachment_nested_transfer_fingerprint(self):
            raise ValueError("Transfer report fingerprint drifted.")
        return self


def attachment_nested_transfer_case_id(*, selector_id: str, task_id: str) -> str:
    """Return one stable Transfer Case ID."""
    return "ntc_" + hashlib.sha256(f"{selector_id}\x1f{task_id}".encode()).hexdigest()[:24]


def classify_attachment_nested_transfer_outcome(
    *,
    evaluations: tuple[AttachmentNestedTransferEvaluation, ...],
) -> AttachmentNestedTransferOutcome:
    """Classify one complete cross-document transfer result."""
    if len(evaluations) != 20 or any(not item.complete for item in evaluations):
        return AttachmentNestedTransferOutcome.INCONCLUSIVE
    correct = sum(item.correct for item in evaluations)
    yes = tuple(item for item in evaluations if item.expected.answer == "Y")
    no = tuple(item for item in evaluations if item.expected.answer == "N")
    if (
        correct >= 18
        and _ratio(sum(item.correct for item in yes), len(yes)) >= 0.85
        and _ratio(sum(item.correct for item in no), len(no)) >= 0.85
    ):
        return AttachmentNestedTransferOutcome.SUPPORTED
    if correct >= 15:
        return AttachmentNestedTransferOutcome.MIXED
    return AttachmentNestedTransferOutcome.FALSIFIED


def attachment_nested_transfer_group_metrics(
    evaluations: tuple[AttachmentNestedTransferEvaluation, ...],
) -> tuple[AttachmentNestedTransferGroupMetrics, ...]:
    """Return canonical Document and expected-label metrics."""
    groups: list[AttachmentNestedTransferGroupMetrics] = []
    for fixture_path in sorted({item.case.fixture_path for item in evaluations}):
        members = tuple(item for item in evaluations if item.case.fixture_path == fixture_path)
        groups.append(
            _group_metrics(
                kind=AttachmentNestedTransferGroupKind.DOCUMENT,
                value=fixture_path,
                members=members,
            )
        )
    for label in ("Y", "N", "U"):
        members = tuple(item for item in evaluations if item.expected.answer == label)
        if members:
            groups.append(
                _group_metrics(
                    kind=AttachmentNestedTransferGroupKind.EXPECTED_LABEL,
                    value=label,
                    members=members,
                )
            )
    return tuple(groups)


def attachment_nested_transfer_fingerprint(value: BaseModel) -> str:
    """Return one canonical CEA-1.23 fingerprint."""
    payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _group_metrics(
    *,
    kind: AttachmentNestedTransferGroupKind,
    value: str,
    members: tuple[AttachmentNestedTransferEvaluation, ...],
) -> AttachmentNestedTransferGroupMetrics:
    correct = sum(item.correct for item in members)
    return AttachmentNestedTransferGroupMetrics(
        group_kind=kind,
        group_value=value,
        case_count=len(members),
        correct_count=correct,
        unresolved_count=sum(not item.complete for item in members),
        accuracy=_ratio(correct, len(members)),
    )
