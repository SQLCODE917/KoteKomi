"""Typed evidence for CEA-1.15 Remainder enumeration isolation."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_domain import ModelRunStatus
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    attachment_edge_filter_model_task_input,
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

ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID = "attachment_filtered_remainder_task_v1"
ATTACHMENT_ENUMERATION_HARD_CONTROL_TASK_ID = "aro_7d658622da90db3299ebee76"
ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID = "aro_e05ad7d4c4c93ca6ceac7a6d"


class AttachmentRemainderEnumerationOutcome(StrEnum):
    """Terminal result for the CEA-1.15 primary hypothesis."""

    SUPPORTED = "supported"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentRemainderEnumerationMechanism(StrEnum):
    """Secondary mechanism indicated by the two exact cases."""

    PART_INVENTORY_SUFFICIENT = "part_inventory_sufficient"
    INTRODUCER_ENUMERATION_SUFFICIENT = "introducer_enumeration_sufficient"
    MARKER_EFFECT_REMAINS = "marker_effect_remains"
    INCONCLUSIVE = "inconclusive"


class AttachmentRemainderEnumerationPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.15 package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentRemainderEnumerationView(BaseModel):
    """One unchanged Candidate task with source-exact filtered Remainders."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_enumeration_view_v1"] = (
        "attachment_remainder_enumeration_view_v1"
    )
    id: Annotated[str, Field(pattern=r"^are_[a-f0-9]{24}$")]
    authoritative_task: AttachmentResidualOwnershipTask
    filtered_remainder_ranges: tuple[AttachmentSourceRange, ...]
    omitted_ranges: tuple[AttachmentSourceRange, ...]
    view_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_ranges, expected_omitted = attachment_filtered_remainder_ranges(
            self.authoritative_task
        )
        if (
            self.filtered_remainder_ranges != expected_ranges
            or self.omitted_ranges != expected_omitted
        ):
            raise ValueError("Remainder enumeration view drifted from authoritative source.")
        expected_fingerprint = attachment_remainder_enumeration_view_fingerprint(
            self.authoritative_task,
            expected_ranges,
            expected_omitted,
        )
        if self.view_fingerprint != expected_fingerprint:
            raise ValueError("Remainder enumeration view fingerprint drifted.")
        if self.id != _identifier("are", expected_fingerprint):
            raise ValueError("Remainder enumeration view ID drifted.")
        return self


class AttachmentRemainderEnumerationObservation(BaseModel):
    """One bounded model observation for one enumeration-only task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_enumeration_observation_v1"] = (
        "attachment_remainder_enumeration_observation_v1"
    )
    repetition: Literal[1, 2]
    view_id: Annotated[str, Field(pattern=r"^are_[a-f0-9]{24}$")]
    authoritative_task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
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
        if self.raw_output_text is None and self.decision.raw_output_sha256 is not None:
            raise ValueError("Remainder enumeration observation lacks raw output text.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Remainder enumeration raw output digest drifted.")
        expected_strict = (
            self.raw_output_text in {item.value for item in AttachmentEdgeFilterAnswerValue}
            and self.decision.answer is not None
            and self.decision.answer.value == self.raw_output_text
            and self.output_token_count == 1
            and self.probability_positions == (0,)
        )
        if self.strict_finite_answer != expected_strict:
            raise ValueError("Remainder enumeration finite-answer result drifted.")
        return self


class AttachmentRemainderEnumerationCaseEvaluation(BaseModel):
    """Two fresh observations and sealed controls for one exact case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_enumeration_case_v1"] = (
        "attachment_remainder_enumeration_case_v1"
    )
    view: AttachmentRemainderEnumerationView
    expected_answer: Literal["Y"]
    structural_answers: tuple[Literal["Y", "N", "U"], Literal["Y", "N", "U"]]
    introducer_answers: tuple[Literal["Y", "N", "U"], Literal["Y", "N", "U"]]
    observations: tuple[AttachmentRemainderEnumerationObservation, ...]
    fresh_answers: tuple[Literal["Y", "N", "U"] | None, ...]
    stable: bool
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.repetition for item in self.observations) != (1, 2):
            raise ValueError("Remainder enumeration case requires repetitions one and two.")
        task = self.view.authoritative_task.edge_filter_task
        if any(
            item.view_id != self.view.id
            or item.authoritative_task_id != self.view.authoritative_task.id
            or item.decision.task_id != task.task_id
            or item.decision.edge_id != task.edge.id
            for item in self.observations
        ):
            raise ValueError("Remainder enumeration case contains a foreign observation.")
        answers = tuple(_observation_answer(item) for item in self.observations)
        stable = answers[0] == answers[1]
        passed = all(item == self.expected_answer for item in answers)
        if (self.fresh_answers, self.stable, self.passed) != (answers, stable, passed):
            raise ValueError("Remainder enumeration case evaluation drifted.")
        return self


class AttachmentRemainderEnumerationPreflight(BaseModel):
    """Digest-bound two-case CEA-1.15 inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_enumeration_preflight_v1"] = (
        "attachment_remainder_enumeration_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    views: tuple[AttachmentRemainderEnumerationView, ...]
    expected_answer_by_task: dict[str, Literal["Y"]]
    structural_answers_by_task: dict[
        str,
        tuple[Literal["Y", "N", "U"], Literal["Y", "N", "U"]],
    ]
    introducer_answers_by_task: dict[
        str,
        tuple[Literal["Y", "N", "U"], Literal["Y", "N", "U"]],
    ]
    expected_model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    configured_max_output_tokens: Annotated[int, Field(ge=2)]
    typed_predecessor_outcome: Literal["supported"] = "supported"
    reviewed_predecessor_mechanism: Literal["inconclusive"] = "inconclusive"
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_ids = (
            ATTACHMENT_ENUMERATION_HARD_CONTROL_TASK_ID,
            ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID,
        )
        task_ids = tuple(item.authoritative_task.id for item in self.views)
        if task_ids != expected_ids:
            raise ValueError("Remainder enumeration case inventory drifted.")
        if set(self.expected_answer_by_task) != set(expected_ids) or any(
            item != "Y" for item in self.expected_answer_by_task.values()
        ):
            raise ValueError("Remainder enumeration Gold inventory drifted.")
        for values in (
            self.structural_answers_by_task,
            self.introducer_answers_by_task,
        ):
            if set(values) != set(expected_ids) or any(len(item) != 2 for item in values.values()):
                raise ValueError("Remainder enumeration sealed answer inventory drifted.")
        if self.result_fingerprint != attachment_remainder_enumeration_fingerprint(self):
            raise ValueError("Remainder enumeration preflight fingerprint drifted.")
        return self


class AttachmentRemainderEnumerationReport(BaseModel):
    """Terminal CEA-1.15 mechanism report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_enumeration_report_v1"] = (
        "attachment_remainder_enumeration_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentRemainderEnumerationCaseEvaluation, ...]
    case_count: Literal[2] = 2
    model_execution_count: Literal[4] = 4
    stable_case_count: Annotated[int, Field(ge=0, le=2)]
    strict_finite_output_count: Annotated[int, Field(ge=0, le=4)]
    unresolved_output_count: Annotated[int, Field(ge=0, le=4)]
    outcome: AttachmentRemainderEnumerationOutcome
    mechanism: AttachmentRemainderEnumerationMechanism
    false_positive_safety_tested: Literal[False] = False
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_ids = (
            ATTACHMENT_ENUMERATION_HARD_CONTROL_TASK_ID,
            ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID,
        )
        task_ids = tuple(item.view.authoritative_task.id for item in self.cases)
        if task_ids != expected_ids:
            raise ValueError("Remainder enumeration report case inventory drifted.")
        observations = tuple(item for case in self.cases for item in case.observations)
        actual = (
            sum(item.stable for item in self.cases),
            sum(item.strict_finite_answer for item in observations),
            sum(_observation_answer(item) is None for item in observations),
        )
        recorded = (
            self.stable_case_count,
            self.strict_finite_output_count,
            self.unresolved_output_count,
        )
        if recorded != actual:
            raise ValueError("Remainder enumeration report metrics drifted.")
        recovered = _case(self.cases, ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID)
        control = _case(self.cases, ATTACHMENT_ENUMERATION_HARD_CONTROL_TASK_ID)
        expected_outcome = attachment_remainder_enumeration_outcome(
            strict_finite_output_count=self.strict_finite_output_count,
            unresolved_output_count=self.unresolved_output_count,
            stable_case_count=self.stable_case_count,
            recovered_answers=recovered.fresh_answers,
        )
        expected_mechanism = attachment_remainder_enumeration_mechanism(
            outcome=expected_outcome,
            recovered_answers=recovered.fresh_answers,
            hard_control_answers=control.fresh_answers,
        )
        if self.outcome is not expected_outcome or self.mechanism is not expected_mechanism:
            raise ValueError("Remainder enumeration mechanism result drifted.")
        if self.result_fingerprint != attachment_remainder_enumeration_fingerprint(self):
            raise ValueError("Remainder enumeration report fingerprint drifted.")
        return self


class AttachmentRemainderEnumerationStatus(BaseModel):
    """Machine-readable state for one CEA-1.15 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_remainder_enumeration_status_v1"] = (
        "attachment_remainder_enumeration_status_v1"
    )
    status: AttachmentRemainderEnumerationPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentRemainderEnumerationOutcome | None
    mechanism: AttachmentRemainderEnumerationMechanism | None
    model_execution_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentRemainderEnumerationPackageStatus.COMPLETE
        terminal = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
            self.mechanism,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete Remainder enumeration status requires terminal paths.")
        if complete != (self.model_execution_count == 4):
            raise ValueError("Remainder enumeration execution count drifted from status.")
        return self


def build_attachment_remainder_enumeration_view(
    task: AttachmentResidualOwnershipTask,
) -> AttachmentRemainderEnumerationView:
    """Build one exact enumeration-only view without moving the Candidate."""
    filtered, omitted = attachment_filtered_remainder_ranges(task)
    fingerprint = attachment_remainder_enumeration_view_fingerprint(task, filtered, omitted)
    return AttachmentRemainderEnumerationView(
        id=_identifier("are", fingerprint),
        authoritative_task=task,
        filtered_remainder_ranges=filtered,
        omitted_ranges=omitted,
        view_fingerprint=fingerprint,
    )


def attachment_filtered_remainder_ranges(
    task: AttachmentResidualOwnershipTask,
) -> tuple[tuple[AttachmentSourceRange, ...], tuple[AttachmentSourceRange, ...]]:
    """Move one leading `that` token outside explicit Remainder enumeration."""
    source = task.edge_filter_task.source_text
    event = task.edge_filter_task.edge.event_range
    filtered: list[AttachmentSourceRange] = []
    omitted: list[AttachmentSourceRange] = []
    matched = False
    for value in task.remainder_ranges:
        if not matched and value.end <= event.start:
            match = _LEADING_THAT.match(value.text)
            if match is not None:
                split = value.start + match.end()
                omitted.append(_source_range(source, value.start, split))
                if split < value.end:
                    filtered.append(_source_range(source, split, value.end))
                matched = True
                continue
        filtered.append(value)
    if not matched:
        raise ValueError("Remainder enumeration isolation requires a leading `that` range.")
    return tuple(filtered), tuple(omitted)


def attachment_filtered_remainder_model_task_input(
    task: AttachmentResidualOwnershipTask,
) -> bytes:
    """Render an unchanged Candidate with source-exact Filtered Remainders."""
    ranges, _ = attachment_filtered_remainder_ranges(task)
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


def attachment_remainder_enumeration_outcome(
    *,
    strict_finite_output_count: int,
    unresolved_output_count: int,
    stable_case_count: int,
    recovered_answers: tuple[Literal["Y", "N", "U"] | None, ...],
) -> AttachmentRemainderEnumerationOutcome:
    """Classify the primary CEA-1.15 hypothesis."""
    if (
        strict_finite_output_count != 4
        or unresolved_output_count != 0
        or stable_case_count != 2
        or len(recovered_answers) != 2
    ):
        return AttachmentRemainderEnumerationOutcome.INCONCLUSIVE
    if recovered_answers == ("Y", "Y"):
        return AttachmentRemainderEnumerationOutcome.SUPPORTED
    if recovered_answers == ("N", "N"):
        return AttachmentRemainderEnumerationOutcome.FALSIFIED
    return AttachmentRemainderEnumerationOutcome.INCONCLUSIVE


def attachment_remainder_enumeration_mechanism(
    *,
    outcome: AttachmentRemainderEnumerationOutcome,
    recovered_answers: tuple[Literal["Y", "N", "U"] | None, ...],
    hard_control_answers: tuple[Literal["Y", "N", "U"] | None, ...],
) -> AttachmentRemainderEnumerationMechanism:
    """Classify the bounded mechanism pattern without a production claim."""
    if outcome is AttachmentRemainderEnumerationOutcome.FALSIFIED:
        return AttachmentRemainderEnumerationMechanism.MARKER_EFFECT_REMAINS
    if outcome is not AttachmentRemainderEnumerationOutcome.SUPPORTED:
        return AttachmentRemainderEnumerationMechanism.INCONCLUSIVE
    if recovered_answers == ("Y", "Y") and hard_control_answers == ("N", "N"):
        return AttachmentRemainderEnumerationMechanism.PART_INVENTORY_SUFFICIENT
    if recovered_answers == ("Y", "Y") and hard_control_answers == ("Y", "Y"):
        return AttachmentRemainderEnumerationMechanism.INTRODUCER_ENUMERATION_SUFFICIENT
    return AttachmentRemainderEnumerationMechanism.INCONCLUSIVE


def attachment_remainder_enumeration_view_fingerprint(
    task: AttachmentResidualOwnershipTask,
    filtered_ranges: tuple[AttachmentSourceRange, ...],
    omitted_ranges: tuple[AttachmentSourceRange, ...],
) -> str:
    """Bind an enumeration view to authoritative source ranges."""
    return _sha(
        {
            "authoritative_task": task.model_dump(mode="json"),
            "filtered_remainder_ranges": [item.model_dump(mode="json") for item in filtered_ranges],
            "omitted_ranges": [item.model_dump(mode="json") for item in omitted_ranges],
        }
    )


def attachment_remainder_enumeration_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.15 DTO."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def _case(
    cases: tuple[AttachmentRemainderEnumerationCaseEvaluation, ...],
    task_id: str,
) -> AttachmentRemainderEnumerationCaseEvaluation:
    return next(item for item in cases if item.view.authoritative_task.id == task_id)


def _observation_answer(
    observation: AttachmentRemainderEnumerationObservation,
) -> Literal["Y", "N", "U"] | None:
    if observation.decision.answer is None:
        return None
    return observation.decision.answer.value


def _source_range(source: str, start: int, end: int) -> AttachmentSourceRange:
    return AttachmentSourceRange(start=start, end=end, text=source[start:end])


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
