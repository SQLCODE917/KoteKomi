"""Typed evidence for the CEA-1.14 Candidate marker boundary ablation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_domain import ModelRunStatus
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterTask,
    AttachmentPoolEdge,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    AttachmentResidualOwnershipTask,
    build_attachment_residual_ownership_task,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSourceRange,
)
from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentCandidate,
    competitive_attachment_candidate_id,
)

_SHA256 = r"^[a-f0-9]{64}$"
_INTRODUCER = re.compile(r"(?i:(that|which|who|to))(?P<space>\s+)")


class AttachmentCandidateMarkerArm(StrEnum):
    """One deterministic model-visible Candidate boundary policy."""

    STRUCTURAL_TRIM = "structural_trim"
    INTRODUCER_TRIM = "introducer_trim"


class AttachmentCandidateMarkerOutcome(StrEnum):
    """Terminal result for the CEA-1.14 hypothesis."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentCandidateMarkerPackageStatus(StrEnum):
    """Lifecycle state for one CEA-1.14 evidence package."""

    PREPARED = "prepared"
    COMPLETE = "complete"


class AttachmentCandidateMarkerView(BaseModel):
    """One source-exact Rendered Candidate mapped to its Authoritative Candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_marker_view_v1"] = (
        "attachment_candidate_marker_view_v1"
    )
    id: Annotated[str, Field(pattern=r"^amv_[a-f0-9]{24}$")]
    arm: AttachmentCandidateMarkerArm
    authoritative_task: AttachmentResidualOwnershipTask
    rendered_task: AttachmentResidualOwnershipTask
    removed_prefix: AttachmentSourceRange | None
    removed_suffix: AttachmentSourceRange | None
    removed_introducer: AttachmentSourceRange | None
    view_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = _candidate_marker_view_values(self.authoritative_task, self.arm)
        recorded = (
            self.rendered_task,
            self.removed_prefix,
            self.removed_suffix,
            self.removed_introducer,
        )
        if recorded != expected:
            raise ValueError("Candidate marker view drifted from authoritative characters.")
        expected_fingerprint = attachment_candidate_marker_view_fingerprint(
            authoritative_task=self.authoritative_task,
            arm=self.arm,
            rendered_task=self.rendered_task,
            removed_prefix=self.removed_prefix,
            removed_suffix=self.removed_suffix,
            removed_introducer=self.removed_introducer,
        )
        if self.view_fingerprint != expected_fingerprint:
            raise ValueError("Candidate marker view fingerprint drifted.")
        if self.id != _identifier("amv", expected_fingerprint):
            raise ValueError("Candidate marker view ID drifted.")
        return self


class AttachmentCandidateMarkerObservation(BaseModel):
    """One bounded Qwen observation for one Candidate marker view."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_marker_observation_v1"] = (
        "attachment_candidate_marker_observation_v1"
    )
    arm: AttachmentCandidateMarkerArm
    repetition: Literal[1, 2]
    view_id: Annotated[str, Field(pattern=r"^amv_[a-f0-9]{24}$")]
    authoritative_task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    rendered_task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
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
            raise ValueError("Candidate marker observation lacks raw output text.")
        if (
            self.raw_output_text is not None
            and hashlib.sha256(self.raw_output_text.encode()).hexdigest()
            != self.decision.raw_output_sha256
        ):
            raise ValueError("Candidate marker raw output digest drifted.")
        expected_strict = (
            self.raw_output_text in {item.value for item in AttachmentEdgeFilterAnswerValue}
            and self.decision.answer is not None
            and self.decision.answer.value == self.raw_output_text
            and self.output_token_count == 1
            and self.probability_positions == (0,)
        )
        if self.strict_finite_answer != expected_strict:
            raise ValueError("Candidate marker strict finite-answer result drifted.")
        return self


class AttachmentCandidateMarkerArmEvaluation(BaseModel):
    """Two repetitions for one marker view and Candidate occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_marker_arm_evaluation_v1"] = (
        "attachment_candidate_marker_arm_evaluation_v1"
    )
    view: AttachmentCandidateMarkerView
    expected_answer: Literal["Y", "N"]
    baseline_passed: bool
    observations: tuple[AttachmentCandidateMarkerObservation, ...]
    answers: tuple[Literal["Y", "N", "U"] | None, ...]
    stable: bool
    passed: bool
    recovered: bool
    regressed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.repetition for item in self.observations) != (1, 2):
            raise ValueError("Candidate marker arm requires two ordered observations.")
        rendered = self.view.rendered_task.edge_filter_task
        if any(
            item.arm is not self.view.arm
            or item.view_id != self.view.id
            or item.authoritative_task_id != self.view.authoritative_task.id
            or item.rendered_task_id != self.view.rendered_task.id
            or item.decision.task_id != rendered.task_id
            or item.decision.edge_id != rendered.edge.id
            for item in self.observations
        ):
            raise ValueError("Candidate marker arm contains a foreign observation.")
        answers = tuple(_observation_answer(item) for item in self.observations)
        stable = answers[0] == answers[1]
        passed = all(item == self.expected_answer for item in answers)
        expected = (
            answers,
            stable,
            passed,
            not self.baseline_passed and passed,
            self.baseline_passed and not passed,
        )
        recorded = (
            self.answers,
            self.stable,
            self.passed,
            self.recovered,
            self.regressed,
        )
        if recorded != expected:
            raise ValueError("Candidate marker arm evaluation drifted.")
        return self


class AttachmentCandidateMarkerCaseEvaluation(BaseModel):
    """Baseline and marker-arm results for one Authoritative Candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_marker_case_evaluation_v1"] = (
        "attachment_candidate_marker_case_evaluation_v1"
    )
    authoritative_task: AttachmentResidualOwnershipTask
    expected_answer: Literal["Y", "N"]
    baseline_answers: tuple[Literal["Y", "N", "U"], ...]
    baseline_stable: bool
    baseline_passed: bool
    arms: tuple[AttachmentCandidateMarkerArmEvaluation, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.baseline_answers) != 2:
            raise ValueError("Candidate marker case requires two Baseline answers.")
        baseline_stable = self.baseline_answers[0] == self.baseline_answers[1]
        baseline_passed = all(item == self.expected_answer for item in self.baseline_answers)
        if (self.baseline_stable, self.baseline_passed) != (
            baseline_stable,
            baseline_passed,
        ):
            raise ValueError("Candidate marker Baseline evaluation drifted.")
        if tuple(item.view.arm for item in self.arms) != tuple(AttachmentCandidateMarkerArm):
            raise ValueError("Candidate marker case arm inventory drifted.")
        if any(
            item.view.authoritative_task != self.authoritative_task
            or item.expected_answer != self.expected_answer
            or item.baseline_passed != self.baseline_passed
            for item in self.arms
        ):
            raise ValueError("Candidate marker case contains a foreign arm.")
        return self


class AttachmentCandidateMarkerPreflight(BaseModel):
    """Digest-bound CEA-1.14 input and marker-view inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_marker_preflight_v1"] = (
        "attachment_candidate_marker_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    tasks: tuple[AttachmentResidualOwnershipTask, ...]
    views: tuple[AttachmentCandidateMarkerView, ...]
    expected_answer_by_task: dict[str, Literal["Y", "N"]]
    baseline_answers_by_task: dict[str, tuple[Literal["Y", "N", "U"], ...]]
    expected_model_identity_digest: Annotated[str, Field(pattern=_SHA256)]
    configured_max_output_tokens: Annotated[int, Field(ge=2)]
    historical_predecessor_outcome: Literal["mixed"] = "mixed"
    reviewed_predecessor_outcome: Literal["falsified"] = "falsified"
    gold_entered_model_task: Literal[False] = False
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.tasks) != 10:
            raise ValueError("Candidate marker preflight requires ten tasks.")
        task_ids = tuple(item.id for item in self.tasks)
        if task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Candidate marker tasks must be ordered and distinct.")
        expected_views = tuple(
            build_attachment_candidate_marker_view(task, arm)
            for task in self.tasks
            for arm in AttachmentCandidateMarkerArm
        )
        if self.views != expected_views or len(self.views) != 20:
            raise ValueError("Candidate marker view inventory drifted.")
        if set(self.expected_answer_by_task) != set(task_ids):
            raise ValueError("Candidate marker Gold inventory drifted.")
        if sum(value == "Y" for value in self.expected_answer_by_task.values()) != 8:
            raise ValueError("Candidate marker preflight requires eight positive cases.")
        if sum(value == "N" for value in self.expected_answer_by_task.values()) != 2:
            raise ValueError("Candidate marker preflight requires two negative cases.")
        if set(self.baseline_answers_by_task) != set(task_ids) or any(
            len(value) != 2 or value[0] != value[1]
            for value in self.baseline_answers_by_task.values()
        ):
            raise ValueError("Candidate marker Baseline answer inventory drifted.")
        if self.result_fingerprint != attachment_candidate_marker_fingerprint(self):
            raise ValueError("Candidate marker preflight fingerprint drifted.")
        return self


class AttachmentCandidateMarkerReport(BaseModel):
    """Terminal CEA-1.14 occurrence-level comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_marker_report_v1"] = (
        "attachment_candidate_marker_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    prompt: AttachmentEvidenceReference
    cases: tuple[AttachmentCandidateMarkerCaseEvaluation, ...]
    task_count: Literal[10] = 10
    view_count: Literal[20] = 20
    model_execution_count: Literal[40] = 40
    baseline_correct_count: Annotated[int, Field(ge=0, le=10)]
    structural_correct_count: Annotated[int, Field(ge=0, le=10)]
    introducer_correct_count: Annotated[int, Field(ge=0, le=10)]
    baseline_positive_correct_count: Annotated[int, Field(ge=0, le=8)]
    structural_positive_correct_count: Annotated[int, Field(ge=0, le=8)]
    introducer_positive_correct_count: Annotated[int, Field(ge=0, le=8)]
    baseline_negative_correct_count: Annotated[int, Field(ge=0, le=2)]
    structural_negative_correct_count: Annotated[int, Field(ge=0, le=2)]
    introducer_negative_correct_count: Annotated[int, Field(ge=0, le=2)]
    structural_recovered_count: Annotated[int, Field(ge=0, le=10)]
    structural_regressed_count: Annotated[int, Field(ge=0, le=10)]
    introducer_recovered_count: Annotated[int, Field(ge=0, le=10)]
    introducer_regressed_count: Annotated[int, Field(ge=0, le=10)]
    stable_structural_count: Annotated[int, Field(ge=0, le=10)]
    stable_introducer_count: Annotated[int, Field(ge=0, le=10)]
    strict_finite_output_count: Annotated[int, Field(ge=0, le=40)]
    unresolved_output_count: Annotated[int, Field(ge=0, le=40)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    outcome: AttachmentCandidateMarkerOutcome
    validation_executed: Literal[False] = False
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) != 10:
            raise ValueError("Candidate marker report requires ten cases.")
        task_ids = tuple(item.authoritative_task.id for item in self.cases)
        if task_ids != tuple(sorted(set(task_ids))):
            raise ValueError("Candidate marker report cases must be ordered and distinct.")
        structural = tuple(
            _arm(case, AttachmentCandidateMarkerArm.STRUCTURAL_TRIM) for case in self.cases
        )
        introducer = tuple(
            _arm(case, AttachmentCandidateMarkerArm.INTRODUCER_TRIM) for case in self.cases
        )
        observations = tuple(
            observation
            for case in self.cases
            for arm in case.arms
            for observation in arm.observations
        )
        actual = (
            sum(item.baseline_passed for item in self.cases),
            sum(item.passed for item in structural),
            sum(item.passed for item in introducer),
            sum(item.expected_answer == "Y" and item.baseline_passed for item in self.cases),
            sum(item.expected_answer == "Y" and item.passed for item in structural),
            sum(item.expected_answer == "Y" and item.passed for item in introducer),
            sum(item.expected_answer == "N" and item.baseline_passed for item in self.cases),
            sum(item.expected_answer == "N" and item.passed for item in structural),
            sum(item.expected_answer == "N" and item.passed for item in introducer),
            sum(item.recovered for item in structural),
            sum(item.regressed for item in structural),
            sum(item.recovered for item in introducer),
            sum(item.regressed for item in introducer),
            sum(item.stable for item in structural),
            sum(item.stable for item in introducer),
            sum(item.strict_finite_answer for item in observations),
            sum(_observation_answer(item) is None for item in observations),
        )
        recorded = (
            self.baseline_correct_count,
            self.structural_correct_count,
            self.introducer_correct_count,
            self.baseline_positive_correct_count,
            self.structural_positive_correct_count,
            self.introducer_positive_correct_count,
            self.baseline_negative_correct_count,
            self.structural_negative_correct_count,
            self.introducer_negative_correct_count,
            self.structural_recovered_count,
            self.structural_regressed_count,
            self.introducer_recovered_count,
            self.introducer_regressed_count,
            self.stable_structural_count,
            self.stable_introducer_count,
            self.strict_finite_output_count,
            self.unresolved_output_count,
        )
        if recorded != actual:
            raise ValueError("Candidate marker report metrics drifted.")
        expected_outcome = attachment_candidate_marker_outcome(
            strict_finite_output_count=self.strict_finite_output_count,
            unresolved_output_count=self.unresolved_output_count,
            stable_structural_count=self.stable_structural_count,
            stable_introducer_count=self.stable_introducer_count,
            baseline_correct_count=self.baseline_correct_count,
            introducer_correct_count=self.introducer_correct_count,
            introducer_recovered_count=self.introducer_recovered_count,
            introducer_regressed_count=self.introducer_regressed_count,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Candidate marker outcome drifted from its evidence.")
        if self.result_fingerprint != attachment_candidate_marker_fingerprint(self):
            raise ValueError("Candidate marker report fingerprint drifted.")
        return self


class AttachmentCandidateMarkerStatus(BaseModel):
    """Machine-readable state for one CEA-1.14 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_candidate_marker_status_v1"] = (
        "attachment_candidate_marker_status_v1"
    )
    status: AttachmentCandidateMarkerPackageStatus
    run_root: Annotated[str, Field(min_length=1)]
    preflight_path: Annotated[str, Field(min_length=1)]
    report_path: str | None
    review_path: str | None
    handoff_path: str | None
    claude_review_path: str | None
    outcome: AttachmentCandidateMarkerOutcome | None
    model_execution_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentCandidateMarkerPackageStatus.COMPLETE
        terminal = (
            self.report_path,
            self.review_path,
            self.handoff_path,
            self.claude_review_path,
            self.outcome,
        )
        if complete != all(item is not None for item in terminal):
            raise ValueError("Complete Candidate marker status requires terminal paths.")
        if complete != (self.model_execution_count == 40):
            raise ValueError("Candidate marker execution count drifted from status.")
        return self


def build_attachment_candidate_marker_view(
    task: AttachmentResidualOwnershipTask,
    arm: AttachmentCandidateMarkerArm,
) -> AttachmentCandidateMarkerView:
    """Build one source-exact model-visible Candidate view."""
    rendered_task, removed_prefix, removed_suffix, removed_introducer = (
        _candidate_marker_view_values(task, arm)
    )
    fingerprint = attachment_candidate_marker_view_fingerprint(
        authoritative_task=task,
        arm=arm,
        rendered_task=rendered_task,
        removed_prefix=removed_prefix,
        removed_suffix=removed_suffix,
        removed_introducer=removed_introducer,
    )
    return AttachmentCandidateMarkerView(
        id=_identifier("amv", fingerprint),
        arm=arm,
        authoritative_task=task,
        rendered_task=rendered_task,
        removed_prefix=removed_prefix,
        removed_suffix=removed_suffix,
        removed_introducer=removed_introducer,
        view_fingerprint=fingerprint,
    )


def attachment_candidate_marker_outcome(
    *,
    strict_finite_output_count: int,
    unresolved_output_count: int,
    stable_structural_count: int,
    stable_introducer_count: int,
    baseline_correct_count: int,
    introducer_correct_count: int,
    introducer_recovered_count: int,
    introducer_regressed_count: int,
) -> AttachmentCandidateMarkerOutcome:
    """Classify CEA-1.14 with mutually exclusive evidence gates."""
    complete = (
        strict_finite_output_count == 40
        and unresolved_output_count == 0
        and stable_structural_count == 10
        and stable_introducer_count == 10
    )
    if not complete:
        return AttachmentCandidateMarkerOutcome.INCONCLUSIVE
    if introducer_recovered_count == 0 or introducer_correct_count <= baseline_correct_count:
        return AttachmentCandidateMarkerOutcome.FALSIFIED
    if introducer_regressed_count == 0:
        return AttachmentCandidateMarkerOutcome.SUPPORTED
    return AttachmentCandidateMarkerOutcome.MIXED


def attachment_candidate_marker_view_fingerprint(
    *,
    authoritative_task: AttachmentResidualOwnershipTask,
    arm: AttachmentCandidateMarkerArm,
    rendered_task: AttachmentResidualOwnershipTask,
    removed_prefix: AttachmentSourceRange | None,
    removed_suffix: AttachmentSourceRange | None,
    removed_introducer: AttachmentSourceRange | None,
) -> str:
    """Bind one marker view to both source-exact Candidate ranges."""
    return _sha(
        {
            "authoritative_task": authoritative_task.model_dump(mode="json"),
            "arm": arm.value,
            "rendered_task": rendered_task.model_dump(mode="json"),
            "removed_prefix": (
                removed_prefix.model_dump(mode="json") if removed_prefix is not None else None
            ),
            "removed_suffix": (
                removed_suffix.model_dump(mode="json") if removed_suffix is not None else None
            ),
            "removed_introducer": (
                removed_introducer.model_dump(mode="json")
                if removed_introducer is not None
                else None
            ),
        }
    )


def attachment_candidate_marker_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.14 DTO."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def _candidate_marker_view_values(
    task: AttachmentResidualOwnershipTask,
    arm: AttachmentCandidateMarkerArm,
) -> tuple[
    AttachmentResidualOwnershipTask,
    AttachmentSourceRange | None,
    AttachmentSourceRange | None,
    AttachmentSourceRange | None,
]:
    edge_task = task.edge_filter_task
    source = edge_task.source_text
    candidate = edge_task.edge.candidate_range
    event = edge_task.edge.event_range
    start = candidate.start
    end = candidate.end
    while start < event.start and _structural_character(source[start]):
        start += 1
    while end > event.end and _structural_character(source[end - 1]):
        end -= 1
    structural_start = start
    removed_introducer: AttachmentSourceRange | None = None
    if arm is AttachmentCandidateMarkerArm.INTRODUCER_TRIM:
        match = _INTRODUCER.match(source, start, event.start)
        if match is not None and match.end() <= event.start:
            removed_introducer = _source_range(source, start, match.end())
            start = match.end()
    if not (candidate.start <= start <= event.start < event.end <= end <= candidate.end):
        raise ValueError("Rendered Candidate does not contain its complete Target Event.")
    removed_prefix = (
        _source_range(source, candidate.start, start) if candidate.start < start else None
    )
    removed_suffix = _source_range(source, end, candidate.end) if end < candidate.end else None
    if removed_introducer is not None and removed_introducer.start != structural_start:
        raise ValueError("Removed introducer does not follow Structural Trim.")
    rendered_edge_task = _rendered_edge_filter_task(edge_task, start=start, end=end)
    rendered_task = build_attachment_residual_ownership_task(rendered_edge_task)
    return rendered_task, removed_prefix, removed_suffix, removed_introducer


def _rendered_edge_filter_task(
    task: AttachmentEdgeFilterTask,
    *,
    start: int,
    end: int,
) -> AttachmentEdgeFilterTask:
    source = task.source_text
    original = task.candidate
    text = source[start:end]
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id=original.source_segment_id,
        source_text_sha256=original.source_text_sha256,
        start=start,
        end=end,
        text=text,
        reasons=original.reasons,
        parent_candidate_ids=original.parent_candidate_ids,
        linguistic_token_ids=(),
        source_record_ids=original.source_record_ids,
    )
    rendered_candidate = CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id=original.source_segment_id,
        source_text_sha256=original.source_text_sha256,
        start=start,
        end=end,
        text=text,
        reasons=original.reasons,
        parent_candidate_ids=original.parent_candidate_ids,
        linguistic_token_ids=(),
        source_record_ids=original.source_record_ids,
    )
    original_edge = task.edge
    edge_values = {
        "phase": original_edge.phase,
        "source_segment_id": original_edge.source_segment_id,
        "source_text_sha256": original_edge.source_text_sha256,
        "candidate_id": rendered_candidate.id,
        "source_grounded_event_id": original_edge.source_grounded_event_id,
        "candidate_start": start,
        "candidate_end": end,
        "event_start": original_edge.event_range.start,
        "event_end": original_edge.event_range.end,
    }
    rendered_edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**edge_values),
        phase=original_edge.phase,
        source_segment_id=original_edge.source_segment_id,
        source_text_sha256=original_edge.source_text_sha256,
        candidate_id=rendered_candidate.id,
        source_grounded_event_id=original_edge.source_grounded_event_id,
        candidate_range=_source_range(source, start, end),
        event_range=original_edge.event_range,
        origins=original_edge.origins,
        syntax_arms=original_edge.syntax_arms,
    )
    return build_attachment_edge_filter_task(
        source_text=source,
        edge=rendered_edge,
        candidate=rendered_candidate,
        event_options=task.event_options,
    )


def _source_range(source: str, start: int, end: int) -> AttachmentSourceRange:
    return AttachmentSourceRange(start=start, end=end, text=source[start:end])


def _structural_character(value: str) -> bool:
    return unicodedata.category(value)[0] not in {"L", "N"}


def _observation_answer(
    observation: AttachmentCandidateMarkerObservation,
) -> Literal["Y", "N", "U"] | None:
    if observation.decision.answer is None:
        return None
    return observation.decision.answer.value


def _arm(
    case: AttachmentCandidateMarkerCaseEvaluation,
    arm: AttachmentCandidateMarkerArm,
) -> AttachmentCandidateMarkerArmEvaluation:
    return next(item for item in case.arms if item.view.arm is arm)


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
