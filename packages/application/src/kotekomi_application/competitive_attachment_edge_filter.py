"""Contracts for the CEA-1.4 competitive Attachment Edge Filter."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentMetricSnapshot,
    AttachmentSourceRange,
)
from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
)

_SHA256 = r"^[a-f0-9]{64}$"
type _CandidateId = Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
type _EventId = Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
type _PoolEdgeId = Annotated[str, Field(pattern=r"^ape_[a-f0-9]{24}$")]


class AttachmentProposalOrigin(StrEnum):
    """One fallible source that proposed a Pool Edge."""

    QWEN = "qwen"
    SYNTAX = "syntax"


class AttachmentPoolArm(StrEnum):
    """One nested syntax pool combined with archived competitive Qwen."""

    PATH_1_PLUS_COMPLEMENT = "path_1_plus_complement"
    PATH_3_PLUS_COMPLEMENT = "path_3_plus_complement"
    PATH_UNBOUNDED_PLUS_COMPLEMENT = "path_unbounded_plus_complement"


class AttachmentEdgeFilterAnswerValue(StrEnum):
    """One finite semantic answer for one Target Edge."""

    YES = "Y"
    NO = "N"
    UNCLEAR = "U"


class AttachmentEdgeFilterDecisionStatus(StrEnum):
    """Terminal status of one Edge Filter task."""

    COMPLETE = "complete"
    UNCLEAR = "unclear"
    INPUT_BLOCKED = "input_blocked"
    INVALID_OUTPUT = "invalid_output"
    MODEL_FAILED = "model_failed"


class FilteredAttachmentSetStatus(StrEnum):
    """Semantic completeness of one filtered Candidate result."""

    COMPLETE = "complete"
    EVIDENCED_NONE = "evidenced_none"
    POOL_GAP = "pool_gap"
    UNRESOLVED = "unresolved"


class AttachmentEdgeFilterOutcome(StrEnum):
    """Terminal CEA-1.4 hypothesis result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class AttachmentPoolEdge(BaseModel):
    """One occurrence-specific edge in the Maximum Pool."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_pool_edge_v1"] = "attachment_pool_edge_v1"
    id: _PoolEdgeId
    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_id: _CandidateId
    source_grounded_event_id: _EventId
    candidate_range: AttachmentSourceRange
    event_range: AttachmentSourceRange
    origins: tuple[AttachmentProposalOrigin, ...]
    syntax_arms: tuple[AttachmentPoolArm, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.id != attachment_pool_edge_id(
            phase=self.phase,
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            candidate_id=self.candidate_id,
            source_grounded_event_id=self.source_grounded_event_id,
            candidate_start=self.candidate_range.start,
            candidate_end=self.candidate_range.end,
            event_start=self.event_range.start,
            event_end=self.event_range.end,
        ):
            raise ValueError("Pool Edge ID drifted from its occurrence identity.")
        _ordered_distinct("Pool Edge origins", self.origins)
        _ordered_distinct("Pool Edge syntax arms", self.syntax_arms)
        if tuple(
            sorted(self.origins, key=lambda item: tuple(AttachmentProposalOrigin).index(item))
        ) != (self.origins):
            raise ValueError("Pool Edge origins must use canonical order.")
        expected_arms = tuple(arm for arm in AttachmentPoolArm if arm in set(self.syntax_arms))
        if self.syntax_arms != expected_arms:
            raise ValueError("Pool Edge syntax arms must use canonical nested order.")
        if AttachmentProposalOrigin.SYNTAX in self.origins and not self.syntax_arms:
            raise ValueError("A syntax Pool Edge requires at least one syntax arm.")
        if AttachmentProposalOrigin.SYNTAX not in self.origins and self.syntax_arms:
            raise ValueError("A non-syntax Pool Edge cannot name syntax arms.")
        return self


class AttachmentEdgeFilterTask(BaseModel):
    """One exact model-visible Target Edge task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_task_v1"] = "attachment_edge_filter_task_v1"
    task_id: Annotated[str, Field(pattern=r"^aet_[a-f0-9]{24}$")]
    source_text: Annotated[str, Field(min_length=1)]
    edge: AttachmentPoolEdge
    candidate: CompetitiveAttachmentCandidate
    event_options: tuple[CompetitiveAttachmentEventOption, ...]
    target_event_label: Annotated[str, Field(pattern=r"^E[1-9][0-9]*$")]
    task_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        digest = hashlib.sha256(self.source_text.encode()).hexdigest()
        if digest != self.edge.source_text_sha256:
            raise ValueError("Edge Filter task source digest drifted.")
        if (
            self.candidate.id != self.edge.candidate_id
            or self.candidate.source_segment_id != self.edge.source_segment_id
            or self.candidate.source_text_sha256 != digest
            or self.candidate.start != self.edge.candidate_range.start
            or self.candidate.end != self.edge.candidate_range.end
            or self.candidate.text != self.edge.candidate_range.text
            or self.source_text[self.candidate.start : self.candidate.end] != self.candidate.text
        ):
            raise ValueError("Edge Filter task Candidate drifted from its Pool Edge.")
        if not self.event_options:
            raise ValueError("Edge Filter task requires a Competing Event Set.")
        labels = tuple(item.label for item in self.event_options)
        if labels != tuple(f"E{index}" for index in range(1, len(labels) + 1)):
            raise ValueError("Edge Filter Event labels must be contiguous and source ordered.")
        if self.event_options != tuple(
            sorted(self.event_options, key=lambda item: (item.start, item.end, item.id))
        ):
            raise ValueError("Edge Filter Event options must use source order.")
        target = next(
            (item for item in self.event_options if item.label == self.target_event_label),
            None,
        )
        if target is None or target.source_grounded_event_id != self.edge.source_grounded_event_id:
            raise ValueError("Edge Filter target label does not identify its Pool Edge Event.")
        for option in self.event_options:
            if (
                option.source_segment_id != self.edge.source_segment_id
                or option.source_text_sha256 != digest
                or self.source_text[option.start : option.end] != option.text
            ):
                raise ValueError("Edge Filter Event option is not source-exact.")
        expected_fingerprint = attachment_edge_filter_task_fingerprint(
            source_text=self.source_text,
            edge=self.edge,
            candidate=self.candidate,
            event_options=self.event_options,
            target_event_label=self.target_event_label,
        )
        if self.task_fingerprint != expected_fingerprint:
            raise ValueError("Edge Filter task fingerprint drifted.")
        expected_id = _identifier("aet", {"task_fingerprint": expected_fingerprint})
        if self.task_id != expected_id:
            raise ValueError("Edge Filter task ID drifted from its fingerprint.")
        return self


class AttachmentEdgeFilterDecision(BaseModel):
    """One typed result for one Target Edge."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_decision_v1"] = (
        "attachment_edge_filter_decision_v1"
    )
    task_id: Annotated[str, Field(pattern=r"^aet_[a-f0-9]{24}$")]
    edge_id: _PoolEdgeId
    status: AttachmentEdgeFilterDecisionStatus
    answer: AttachmentEdgeFilterAnswerValue | None
    retained: bool
    unresolved: bool
    extraction_task_id: str | None
    model_run_id: str | None
    trace_id: str | None
    raw_output_sha256: Annotated[str, Field(pattern=_SHA256)] | None
    diagnostic_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")] | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
        unclear = self.status is AttachmentEdgeFilterDecisionStatus.UNCLEAR
        if complete:
            if self.answer not in {
                AttachmentEdgeFilterAnswerValue.YES,
                AttachmentEdgeFilterAnswerValue.NO,
            }:
                raise ValueError("A complete Edge Filter decision requires Y or N.")
            if self.unresolved or self.diagnostic_code is not None:
                raise ValueError("A complete Edge Filter decision cannot be unresolved.")
            if self.retained != (self.answer is AttachmentEdgeFilterAnswerValue.YES):
                raise ValueError("Edge retention drifted from the Y/N answer.")
        elif unclear:
            if self.answer is not AttachmentEdgeFilterAnswerValue.UNCLEAR:
                raise ValueError("An unclear Edge Filter decision requires U.")
            if not self.unresolved or self.retained:
                raise ValueError("An unclear Edge Filter decision must remain unresolved.")
        else:
            if self.answer is not None or not self.unresolved or self.retained:
                raise ValueError("A failed Edge Filter decision must remain unresolved.")
        if complete or unclear:
            if not all((self.extraction_task_id, self.model_run_id, self.trace_id)):
                raise ValueError("A model result requires complete execution references.")
            if self.raw_output_sha256 is None:
                raise ValueError("A model result requires its raw-output digest.")
        if self.status is not AttachmentEdgeFilterDecisionStatus.COMPLETE and (
            self.diagnostic_code is None
        ):
            raise ValueError("A non-complete Edge Filter decision requires a diagnostic.")
        return self


class FilteredAttachmentSet(BaseModel):
    """One Candidate result under one Pool Arm."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    arm: AttachmentPoolArm
    candidate_id: _CandidateId
    pool_edge_ids: tuple[_PoolEdgeId, ...]
    retained_event_ids: tuple[_EventId, ...]
    rejected_event_ids: tuple[_EventId, ...]
    unresolved_event_ids: tuple[_EventId, ...]
    status: FilteredAttachmentSetStatus

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("Filtered pool edges", self.pool_edge_ids)
        _ordered_distinct("Filtered retained Events", self.retained_event_ids)
        _ordered_distinct("Filtered rejected Events", self.rejected_event_ids)
        _ordered_distinct("Filtered unresolved Events", self.unresolved_event_ids)
        groups = tuple(
            set(values)
            for values in (
                self.retained_event_ids,
                self.rejected_event_ids,
                self.unresolved_event_ids,
            )
        )
        if any(groups[left] & groups[right] for left, right in ((0, 1), (0, 2), (1, 2))):
            raise ValueError("Filtered Event outcomes must be disjoint.")
        expected = (
            FilteredAttachmentSetStatus.POOL_GAP
            if not self.pool_edge_ids
            else FilteredAttachmentSetStatus.UNRESOLVED
            if self.unresolved_event_ids
            else FilteredAttachmentSetStatus.EVIDENCED_NONE
            if not self.retained_event_ids
            else FilteredAttachmentSetStatus.COMPLETE
        )
        if self.status is not expected:
            raise ValueError("Filtered Attachment Set status drifted from its decisions.")
        return self


class AttachmentEdgeFilterArmResult(BaseModel):
    """Metrics and decision counts for one filtered Pool Arm."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    arm: AttachmentPoolArm
    raw_pool_metrics: AttachmentMetricSnapshot
    filtered_metrics: AttachmentMetricSnapshot
    edge_count: Annotated[int, Field(ge=0)]
    retained_edge_count: Annotated[int, Field(ge=0)]
    rejected_edge_count: Annotated[int, Field(ge=0)]
    unresolved_edge_count: Annotated[int, Field(ge=0)]
    pool_gap_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            self.retained_edge_count + self.rejected_edge_count + self.unresolved_edge_count
            != self.edge_count
        ):
            raise ValueError("Filtered edge counts do not partition the Pool Arm.")
        return self


class AttachmentEdgeFilterPhaseReport(BaseModel):
    """One complete phase result for the Edge Filter experiment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    candidate_count: Annotated[int, Field(ge=1)]
    maximum_pool_edge_count: Annotated[int, Field(ge=1)]
    task_count: Annotated[int, Field(ge=1)]
    competitive_qwen_metrics: AttachmentMetricSnapshot
    cea13_primary_metrics: AttachmentMetricSnapshot
    oracle_ceiling_metrics: AttachmentMetricSnapshot
    decisions: tuple[AttachmentEdgeFilterDecision, ...]
    filtered_sets: tuple[FilteredAttachmentSet, ...]
    arms: tuple[AttachmentEdgeFilterArmResult, ...]
    selected_arm: AttachmentPoolArm
    invalid_output_count: Annotated[int, Field(ge=0)]
    blocked_count: Annotated[int, Field(ge=0)]
    failed_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_inventory = {
            "development": (162, 490),
            "validation": (179, 257),
        }[self.phase]
        if (self.candidate_count, self.maximum_pool_edge_count) != expected_inventory:
            raise ValueError("Edge Filter phase inventory drifted from frozen evidence.")
        if self.task_count != self.maximum_pool_edge_count or self.task_count != len(
            self.decisions
        ):
            raise ValueError("Edge Filter phase requires one decision per Maximum Pool Edge.")
        if len({item.edge_id for item in self.decisions}) != len(self.decisions):
            raise ValueError("Edge Filter phase decisions must identify distinct Pool Edges.")
        if tuple(item.arm for item in self.arms) != tuple(AttachmentPoolArm):
            raise ValueError("Edge Filter phase requires all canonical Pool Arms.")
        if any(item.phase != self.phase for item in self.arms):
            raise ValueError("Edge Filter phase contains a foreign Pool Arm result.")
        if self.selected_arm not in {item.arm for item in self.arms}:
            raise ValueError("Edge Filter selected arm is absent from its results.")
        if self.candidate_count != len(self.filtered_sets) // len(AttachmentPoolArm):
            raise ValueError("Edge Filter phase requires one set per Candidate and Pool Arm.")
        filtered_keys = {(item.candidate_id, item.arm) for item in self.filtered_sets}
        if len(filtered_keys) != self.candidate_count * len(AttachmentPoolArm) or any(
            item.phase != self.phase for item in self.filtered_sets
        ):
            raise ValueError("Edge Filter phase Candidate/Arm result inventory is invalid.")
        if self.invalid_output_count != sum(
            item.status is AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT
            for item in self.decisions
        ):
            raise ValueError("Edge Filter invalid-output count drifted.")
        if self.blocked_count != sum(
            item.status is AttachmentEdgeFilterDecisionStatus.INPUT_BLOCKED
            for item in self.decisions
        ):
            raise ValueError("Edge Filter blocked count drifted.")
        if self.failed_count != sum(
            item.status is AttachmentEdgeFilterDecisionStatus.MODEL_FAILED
            for item in self.decisions
        ):
            raise ValueError("Edge Filter failed count drifted.")
        if self.result_fingerprint != _sha(
            self.model_dump(mode="json", exclude={"result_fingerprint"})
        ):
            raise ValueError("Edge Filter phase result fingerprint drifted.")
        return self


class AttachmentEdgeFilterDiagnosticCatalog(BaseModel):
    """Human-reviewable sixteen-edge development diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_diagnostic_catalog_v1"] = (
        "attachment_edge_filter_diagnostic_catalog_v1"
    )
    tasks: tuple[AttachmentEdgeFilterTask, ...]
    coverage_by_task_id: dict[str, tuple[str, ...]]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.tasks) != 16:
            raise ValueError("Edge Filter diagnostic requires sixteen tasks.")
        task_ids = tuple(item.task_id for item in self.tasks)
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("Edge Filter diagnostic tasks must be distinct.")
        if set(self.coverage_by_task_id) != set(task_ids):
            raise ValueError("Edge Filter diagnostic coverage must bind every task.")
        expected_categories = {
            "qwen_false_positive",
            "syntax_only_true",
            "syntax_only_false",
            "shared_fragment",
            "shared_entity",
            "gold_none",
            "repeated_occurrence",
            "attribution",
            "temporal",
            "long_dependency_path",
        }
        observed_categories = {
            category for values in self.coverage_by_task_id.values() for category in values
        }
        if observed_categories != expected_categories:
            raise ValueError("Edge Filter diagnostic category coverage is incomplete or foreign.")
        if len({item.edge.source_segment_id for item in self.tasks}) != 6:
            raise ValueError(
                "Edge Filter diagnostic must cover all six development SourceSegments."
            )
        expected_fingerprint = _sha(
            {
                "tasks": [item.model_dump(mode="json") for item in self.tasks],
                "coverage_by_task_id": self.coverage_by_task_id,
            }
        )
        if self.catalog_sha256 != expected_fingerprint:
            raise ValueError("Edge Filter diagnostic catalog fingerprint drifted.")
        return self


class AttachmentEdgeFilterDiagnosticApproval(BaseModel):
    """Human approval of two stable diagnostic executions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_diagnostic_approval_v1"] = (
        "attachment_edge_filter_diagnostic_approval_v1"
    )
    reviewer: Annotated[str, Field(min_length=1)]
    reviewed_at: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    runtime_contract_sha256: Annotated[str, Field(pattern=_SHA256)]
    repetition_1_sha256: Annotated[str, Field(pattern=_SHA256)]
    repetition_2_sha256: Annotated[str, Field(pattern=_SHA256)]
    review_sha256: Annotated[str, Field(pattern=_SHA256)]
    stable_semantic_results: Literal[True] = True
    decision: Literal["approved"] = "approved"


class AttachmentEdgeFilterDevelopmentFreeze(BaseModel):
    """Immutable selected development contract required by validation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_development_freeze_v1"] = (
        "attachment_edge_filter_development_freeze_v1"
    )
    selected_arm: AttachmentPoolArm
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    runtime_contract_sha256: Annotated[str, Field(pattern=_SHA256)]
    parser_sha256: Annotated[str, Field(pattern=_SHA256)]
    mapping_policy_id: Literal["attachment_edge_filter_mapping_v1"] = (
        "attachment_edge_filter_mapping_v1"
    )
    diagnostic_approval_sha256: Annotated[str, Field(pattern=_SHA256)]
    development_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]


class AttachmentEdgeFilterReport(BaseModel):
    """Terminal CEA-1.4 development and validation report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_report_v1"] = "attachment_edge_filter_report_v1"
    inputs: tuple[AttachmentEvidenceReference, ...]
    development: AttachmentEdgeFilterPhaseReport
    validation: AttachmentEdgeFilterPhaseReport
    selected_arm: AttachmentPoolArm
    outcome: AttachmentEdgeFilterOutcome
    validation_interpretation: Literal["diagnostic_only"] = "diagnostic_only"
    production_integration: Literal["not_activated"] = "not_activated"
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.development.phase != "development" or self.validation.phase != "validation":
            raise ValueError("Edge Filter terminal report phase order is invalid.")
        if (
            self.development.selected_arm is not self.selected_arm
            or self.validation.selected_arm is not self.selected_arm
        ):
            raise ValueError("Edge Filter terminal report selected arm drifted.")
        _ordered_distinct("Edge Filter input labels", tuple(item.label for item in self.inputs))
        if self.result_fingerprint != attachment_edge_filter_report_fingerprint(self):
            raise ValueError("Edge Filter terminal result fingerprint drifted.")
        return self


class AttachmentEdgeFilterManifest(BaseModel):
    """Digest chain for one terminal CEA-1.4 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_manifest_v1"] = (
        "attachment_edge_filter_manifest_v1"
    )
    tdd: AttachmentEvidenceReference
    inputs: tuple[AttachmentEvidenceReference, ...]
    outputs: tuple[AttachmentEvidenceReference, ...]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("Edge Filter manifest inputs", tuple(item.label for item in self.inputs))
        _ordered_distinct(
            "Edge Filter manifest outputs", tuple(item.label for item in self.outputs)
        )
        return self


class AttachmentEdgeFilterStatus(BaseModel):
    """Terminal machine-readable CEA-1.4 status."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_edge_filter_status_v1"] = "attachment_edge_filter_status_v1"
    status: Literal["complete"] = "complete"
    outcome: AttachmentEdgeFilterOutcome
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    report_path: Annotated[str, Field(min_length=1)]
    review_path: Annotated[str, Field(min_length=1)]
    summary_path: Annotated[str, Field(min_length=1)]
    handoff_path: Annotated[str, Field(min_length=1)]


def parse_attachment_edge_filter_answer(payload: bytes) -> AttachmentEdgeFilterAnswerValue:
    """Parse one exact Y, N, or U answer."""
    try:
        value = payload.decode("utf-8").strip(" \t\r\n")
    except UnicodeDecodeError as error:
        raise ValueError("Edge Filter answer must be UTF-8 text.") from error
    try:
        return AttachmentEdgeFilterAnswerValue(value)
    except ValueError as error:
        raise ValueError("Edge Filter answer must be exactly Y, N, or U.") from error


def attachment_edge_filter_schema_bytes() -> bytes:
    """Return the pinned finite model-output contract."""
    return b"Return exactly one answer character: Y, N, or U.\n"


def attachment_pool_edge_id(**values: object) -> str:
    """Return one stable Pool Edge identifier."""
    return _identifier("ape", values)


def build_attachment_edge_filter_task(
    *,
    source_text: str,
    edge: AttachmentPoolEdge,
    candidate: CompetitiveAttachmentCandidate,
    event_options: tuple[CompetitiveAttachmentEventOption, ...],
) -> AttachmentEdgeFilterTask:
    """Build one exact Target Edge task."""
    target = next(
        item
        for item in event_options
        if item.source_grounded_event_id == edge.source_grounded_event_id
    )
    fingerprint = attachment_edge_filter_task_fingerprint(
        source_text=source_text,
        edge=edge,
        candidate=candidate,
        event_options=event_options,
        target_event_label=target.label,
    )
    return AttachmentEdgeFilterTask(
        task_id=_identifier("aet", {"task_fingerprint": fingerprint}),
        source_text=source_text,
        edge=edge,
        candidate=candidate,
        event_options=event_options,
        target_event_label=target.label,
        task_fingerprint=fingerprint,
    )


def attachment_edge_filter_task_fingerprint(
    *,
    source_text: str,
    edge: AttachmentPoolEdge,
    candidate: CompetitiveAttachmentCandidate,
    event_options: tuple[CompetitiveAttachmentEventOption, ...],
    target_event_label: str,
) -> str:
    """Bind all semantic input to one reusable task fingerprint."""
    return _sha(
        {
            "source_text": source_text,
            "edge": edge.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "event_options": [item.model_dump(mode="json") for item in event_options],
            "target_event_label": target_event_label,
        }
    )


def attachment_edge_filter_model_task_input(task: AttachmentEdgeFilterTask) -> bytes:
    """Render model-visible source text without canonical identifiers or offsets."""
    candidate_view = _mark(
        task.source_text,
        task.candidate.start,
        task.candidate.end,
        "candidate",
    )
    target = next(item for item in task.event_options if item.label == task.target_event_label)
    target_view = _mark(task.source_text, target.start, target.end, "event")
    siblings = tuple(item for item in task.event_options if item.label != target.label)
    lines = [
        "Passage with the Candidate occurrence:",
        f"<source>{candidate_view}</source>",
        "",
        f"Target Event {target.label}:",
        f"<source>{target_view}</source>",
        "",
        "Other Events in the passage:",
    ]
    lines.extend(f'{item.label}: "{item.text}"' for item in siblings)
    if not siblings:
        lines.append("NONE")
    return ("\n".join(lines) + "\n").encode()


def build_filtered_attachment_set(
    *,
    phase: Literal["development", "validation"],
    arm: AttachmentPoolArm,
    candidate_id: str,
    edges: tuple[AttachmentPoolEdge, ...],
    decisions_by_edge_id: dict[str, AttachmentEdgeFilterDecision],
) -> FilteredAttachmentSet:
    """Construct one Candidate result without semantic repair."""
    arm_edges = tuple(
        edge
        for edge in edges
        if AttachmentProposalOrigin.QWEN in edge.origins or arm in edge.syntax_arms
    )
    if not arm_edges:
        return FilteredAttachmentSet(
            phase=phase,
            arm=arm,
            candidate_id=candidate_id,
            pool_edge_ids=(),
            retained_event_ids=(),
            rejected_event_ids=(),
            unresolved_event_ids=(),
            status=FilteredAttachmentSetStatus.POOL_GAP,
        )
    decisions = tuple(decisions_by_edge_id[edge.id] for edge in arm_edges)
    return FilteredAttachmentSet(
        phase=phase,
        arm=arm,
        candidate_id=candidate_id,
        pool_edge_ids=tuple(sorted(edge.id for edge in arm_edges)),
        retained_event_ids=tuple(
            sorted(
                edge.source_grounded_event_id
                for edge, decision in zip(arm_edges, decisions, strict=True)
                if decision.retained
            )
        ),
        rejected_event_ids=tuple(
            sorted(
                edge.source_grounded_event_id
                for edge, decision in zip(arm_edges, decisions, strict=True)
                if decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
                and not decision.retained
            )
        ),
        unresolved_event_ids=tuple(
            sorted(
                edge.source_grounded_event_id
                for edge, decision in zip(arm_edges, decisions, strict=True)
                if decision.unresolved
            )
        ),
        status=(
            FilteredAttachmentSetStatus.UNRESOLVED
            if any(item.unresolved for item in decisions)
            else FilteredAttachmentSetStatus.COMPLETE
            if any(item.retained for item in decisions)
            else FilteredAttachmentSetStatus.EVIDENCED_NONE
        ),
    )


def attachment_edge_filter_report_fingerprint(
    value: AttachmentEdgeFilterReport | dict[str, object],
) -> str:
    """Return the semantic fingerprint for one terminal report."""
    payload = (
        value.model_dump(mode="json", exclude={"result_fingerprint"})
        if isinstance(value, AttachmentEdgeFilterReport)
        else {key: item for key, item in value.items() if key != "result_fingerprint"}
    )
    return _sha(payload)


def _mark(source: str, start: int, end: int, tag: str) -> str:
    if not (0 <= start < end <= len(source)):
        raise ValueError("Edge Filter marker leaves the SourceSegment.")
    return f"{source[:start]}<{tag}>{source[start:end]}</{tag}>{source[end:]}"


def _identifier(prefix: str, values: object) -> str:
    return f"{prefix}_{_sha(values)[:24]}"


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _ordered_distinct(label: str, values: tuple[object, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be distinct.")
