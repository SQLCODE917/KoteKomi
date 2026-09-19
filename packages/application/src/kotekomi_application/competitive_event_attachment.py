"""Exact-occurrence contracts and deterministic competitive Event attachment."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_event_attachment_model_output import (
    CompetitiveAttachmentAnswer,
    CompetitiveAttachmentAnswerKind,
)
from kotekomi_application.hybrid_event_semantics import SourceGroundedEventDraft
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft
from kotekomi_application.source_grounded_proposition_scope import (
    PropositionFragmentCandidate,
    PropositionFragmentReason,
)

_SHA256 = r"^[a-f0-9]{64}$"
COMPETITIVE_ATTACHMENT_TASK_RENDERER_ID = "competitive_event_attachment_task_v2"


class CompetitiveAttachmentDecisionStatus(StrEnum):
    """Terminal interpretation of one candidate task."""

    COMPLETE = "complete"
    UNCLEAR = "unclear"
    INVALID_OUTPUT = "invalid_output"
    MODEL_FAILED = "model_failed"
    CONTEXT_BUDGET_BLOCKED = "context_budget_blocked"


class CompetitiveAttachmentExperimentOutcome(StrEnum):
    """Terminal interpretation of one complete CEA-1 comparison."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class CompetitiveAttachmentEventOrder(StrEnum):
    """Task-local ordering of one canonical Competing Event Set."""

    SOURCE = "source"
    REVERSED = "reversed"


class CompetitiveAttachmentEdgeOrigin(StrEnum):
    """Why KoteKomi retained one exact Attachment Edge."""

    DETERMINISTIC_EVENT_EXPRESSION = "deterministic_event_expression"
    MODEL_SELECTION = "model_selection"


class CompetitiveAttachmentCandidate(BaseModel):
    """One exact source occurrence shared across all competing Events."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    reasons: tuple[PropositionFragmentReason, ...]
    parent_candidate_ids: tuple[Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")], ...]
    linguistic_token_ids: tuple[Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")], ...]
    source_record_ids: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Competitive Attachment Candidate range does not match its text.")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value)):
            raise ValueError(
                "Competitive Attachment candidate reasons must be ordered and distinct."
            )
        _ordered_distinct("parent candidate IDs", self.parent_candidate_ids)
        _ordered_distinct("linguistic token IDs", self.linguistic_token_ids)
        _ordered_distinct("source record IDs", self.source_record_ids)
        if not self.reasons or not self.parent_candidate_ids:
            raise ValueError("Competitive Attachment Candidate requires proposal lineage.")
        if self.id != competitive_attachment_candidate_id(
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            start=self.start,
            end=self.end,
            text=self.text,
            reasons=self.reasons,
            parent_candidate_ids=self.parent_candidate_ids,
            linguistic_token_ids=self.linguistic_token_ids,
            source_record_ids=self.source_record_ids,
        ):
            raise ValueError("Competitive Attachment Candidate ID drifted from its evidence.")
        return self


class CompetitiveAttachmentEventOption(BaseModel):
    """One source-grounded Event occurrence with an invocation-local label."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^cao_[a-f0-9]{24}$")]
    label: Annotated[str, Field(pattern=r"^E[1-9][0-9]*$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    event_trigger_id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Competitive Attachment Event range does not match its text.")
        if self.id != competitive_attachment_event_option_id(
            source_grounded_event_id=self.source_grounded_event_id,
            event_trigger_id=self.event_trigger_id,
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            start=self.start,
            end=self.end,
            text=self.text,
        ):
            raise ValueError("Competitive Attachment Event option ID drifted.")
        return self


class CompetitiveAttachmentGoldDecision(BaseModel):
    """Evaluation-only exact Attachment Set for one candidate occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    source_grounded_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("Gold Attachment Event IDs", self.source_grounded_event_ids)
        return self


class CompetitiveAttachmentEdge(BaseModel):
    """One derived exact candidate-to-Event occurrence edge."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^cae_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    event_option_id: Annotated[str, Field(pattern=r"^cao_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    origins: tuple[CompetitiveAttachmentEdgeOrigin, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.origins != tuple(sorted(set(self.origins), key=lambda value: value.value)):
            raise ValueError("Competitive Attachment Edge origins must be ordered and distinct.")
        if not self.origins:
            raise ValueError("A Competitive Attachment Edge requires lineage.")
        if self.id != competitive_attachment_edge_id(
            candidate_id=self.candidate_id,
            event_option_id=self.event_option_id,
            source_grounded_event_id=self.source_grounded_event_id,
            origins=self.origins,
        ):
            raise ValueError("Competitive Attachment Edge ID drifted from its evidence.")
        return self


class CompetitiveAttachmentDecision(BaseModel):
    """One deterministic mapping of a finite model answer to exact Events."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^cad_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    status: CompetitiveAttachmentDecisionStatus
    parsed_event_labels: tuple[Annotated[str, Field(pattern=r"^E[1-9][0-9]*$")], ...]
    deterministic_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    model_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    omitted_deterministic_event_ids: tuple[
        Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...
    ]
    edges: tuple[CompetitiveAttachmentEdge, ...]
    extraction_task_id: str
    model_run_id: str
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]
    raw_output_base64: str | None
    raw_output_sha256: Annotated[str, Field(pattern=_SHA256)] | None
    diagnostic_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")] | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("parsed Event labels", self.parsed_event_labels),
            ("deterministic Event IDs", self.deterministic_event_ids),
            ("model Event IDs", self.model_event_ids),
            ("omitted deterministic Event IDs", self.omitted_deterministic_event_ids),
        ):
            _ordered_distinct(label, values)
        if self.raw_output_base64 is None:
            if self.raw_output_sha256 is not None:
                raise ValueError("A missing raw output cannot have a digest.")
        else:
            raw = base64.b64decode(self.raw_output_base64, validate=True)
            if hashlib.sha256(raw).hexdigest() != self.raw_output_sha256:
                raise ValueError("Competitive Attachment raw output digest drifted.")
        if self.status is CompetitiveAttachmentDecisionStatus.COMPLETE:
            if self.diagnostic_code is not None:
                raise ValueError("A complete attachment decision cannot have a diagnostic.")
        elif self.diagnostic_code is None:
            raise ValueError("An incomplete attachment decision requires a diagnostic.")
        expected_edge_events = tuple(sorted({item.source_grounded_event_id for item in self.edges}))
        expected_selected = tuple(
            sorted(set(self.deterministic_event_ids) | set(self.model_event_ids))
        )
        if expected_edge_events != expected_selected:
            raise ValueError("Competitive Attachment edges drifted from selected Events.")
        expected_omitted = tuple(
            sorted(set(self.deterministic_event_ids) - set(self.model_event_ids))
        )
        if self.omitted_deterministic_event_ids != expected_omitted:
            raise ValueError("Competitive Attachment omitted deterministic Events drifted.")
        if self.id != competitive_attachment_decision_id(
            candidate_id=self.candidate_id,
            status=self.status,
            parsed_event_labels=self.parsed_event_labels,
            deterministic_event_ids=self.deterministic_event_ids,
            model_event_ids=self.model_event_ids,
            edge_ids=tuple(item.id for item in self.edges),
            extraction_task_id=self.extraction_task_id,
            model_run_id=self.model_run_id,
            trace_id=self.trace_id,
            raw_output_sha256=self.raw_output_sha256,
            diagnostic_code=self.diagnostic_code,
        ):
            raise ValueError("Competitive Attachment Decision ID drifted.")
        return self


class CompetitiveAttachmentMatrix(BaseModel):
    """One complete candidate-by-Event occurrence matrix for a SourceSegment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_attachment_matrix_v1"] = "competitive_attachment_matrix_v1"
    id: Annotated[str, Field(pattern=r"^cam_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidates: tuple[CompetitiveAttachmentCandidate, ...]
    event_options: tuple[CompetitiveAttachmentEventOption, ...]
    decisions: tuple[CompetitiveAttachmentDecision, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.candidates or not self.event_options:
            raise ValueError("Competitive Attachment Matrix requires candidates and Events.")
        if tuple(sorted(self.candidates, key=lambda item: (item.start, item.end, item.text))) != (
            self.candidates
        ):
            raise ValueError("Competitive Attachment candidates must use source order.")
        if (
            tuple(
                sorted(
                    self.event_options,
                    key=lambda item: (item.start, item.end, item.source_grounded_event_id),
                )
            )
            != self.event_options
        ):
            raise ValueError("Competitive Attachment Events must use source order.")
        if tuple(item.label for item in self.event_options) != tuple(
            f"E{index}" for index in range(1, len(self.event_options) + 1)
        ):
            raise ValueError("Competitive Attachment Event labels must be contiguous.")
        if any(
            item.source_segment_id != self.source_segment_id
            or item.source_text_sha256 != self.source_text_sha256
            for item in (*self.candidates, *self.event_options)
        ):
            raise ValueError("Competitive Attachment Matrix contains foreign source evidence.")
        if self.decisions:
            if tuple(item.candidate_id for item in self.decisions) != tuple(
                item.id for item in self.candidates
            ):
                raise ValueError("Competitive Attachment Matrix requires one ordered decision.")
            option_by_label = {item.label: item for item in self.event_options}
            option_by_id = {item.id: item for item in self.event_options}
            for candidate, decision in zip(self.candidates, self.decisions, strict=True):
                if any(label not in option_by_label for label in decision.parsed_event_labels):
                    raise ValueError(
                        "Competitive Attachment decision contains a foreign task-local label."
                    )
                expected_model_events = tuple(
                    sorted(
                        option_by_label[label].source_grounded_event_id
                        for label in decision.parsed_event_labels
                    )
                )
                expected_deterministic_events = tuple(
                    sorted(
                        option.source_grounded_event_id
                        for option in self.event_options
                        if (option.start, option.end) == (candidate.start, candidate.end)
                    )
                )
                if decision.model_event_ids != expected_model_events:
                    raise ValueError(
                        "Competitive Attachment model Events drifted from task-local labels."
                    )
                if decision.deterministic_event_ids != expected_deterministic_events:
                    raise ValueError("Competitive Attachment deterministic Event evidence drifted.")
                if any(
                    edge.candidate_id != candidate.id
                    or edge.event_option_id not in option_by_id
                    or option_by_id[edge.event_option_id].source_grounded_event_id
                    != edge.source_grounded_event_id
                    for edge in decision.edges
                ):
                    raise ValueError("Competitive Attachment Edge references foreign evidence.")
        if self.id != competitive_attachment_matrix_id(
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            candidate_ids=tuple(item.id for item in self.candidates),
            event_option_ids=tuple(item.id for item in self.event_options),
            decision_ids=tuple(item.id for item in self.decisions),
        ):
            raise ValueError("Competitive Attachment Matrix ID drifted.")
        return self


class CompetitiveAttachmentCaseEvaluation(BaseModel):
    """Occurrence-level baseline and competitive result for one candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    gold_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    baseline_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    competitive_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    baseline_unresolved_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    competitive_unresolved: bool
    true_positive_edge_count: Annotated[int, Field(ge=0)]
    false_positive_edge_count: Annotated[int, Field(ge=0)]
    false_negative_edge_count: Annotated[int, Field(ge=0)]
    sibling_event_leakage_count: Annotated[int, Field(ge=0)]
    shared_gold_edge_count: Annotated[int, Field(ge=0)]
    shared_matched_edge_count: Annotated[int, Field(ge=0)]
    baseline_exact: bool
    competitive_exact: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("Gold Event IDs", self.gold_event_ids),
            ("baseline Event IDs", self.baseline_event_ids),
            ("competitive Event IDs", self.competitive_event_ids),
            ("baseline unresolved Event IDs", self.baseline_unresolved_event_ids),
        ):
            _ordered_distinct(label, values)
        gold = set(self.gold_event_ids)
        predicted = set(self.competitive_event_ids)
        if self.true_positive_edge_count != len(gold & predicted):
            raise ValueError("Competitive Attachment true-positive count drifted.")
        if self.false_positive_edge_count != len(predicted - gold):
            raise ValueError("Competitive Attachment false-positive count drifted.")
        if self.false_negative_edge_count != len(gold - predicted):
            raise ValueError("Competitive Attachment false-negative count drifted.")
        expected_leakage = len(predicted - gold) if gold else 0
        if self.sibling_event_leakage_count != expected_leakage:
            raise ValueError("Competitive Attachment sibling leakage drifted.")
        expected_shared = len(gold) if len(gold) > 1 else 0
        if self.shared_gold_edge_count != expected_shared:
            raise ValueError("Competitive Attachment shared-edge count drifted.")
        if self.shared_matched_edge_count != (len(gold & predicted) if expected_shared else 0):
            raise ValueError("Competitive Attachment shared matched-edge count drifted.")
        if self.baseline_exact != (
            not self.baseline_unresolved_event_ids and set(self.baseline_event_ids) == gold
        ):
            raise ValueError("Competitive Attachment baseline exact status drifted.")
        if self.competitive_exact != (not self.competitive_unresolved and predicted == gold):
            raise ValueError("Competitive Attachment exact status drifted.")
        return self


class CompetitiveAttachmentMetrics(BaseModel):
    """Aggregate occurrence and reconstructed-proposition measurements."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_count: Annotated[int, Field(ge=0)]
    baseline_exact_set_accuracy: Annotated[float, Field(ge=0, le=1)]
    competitive_exact_set_accuracy: Annotated[float, Field(ge=0, le=1)]
    edge_precision: Annotated[float, Field(ge=0, le=1)]
    edge_recall: Annotated[float, Field(ge=0, le=1)]
    edge_f1: Annotated[float, Field(ge=0, le=1)]
    baseline_sibling_event_leakage_count: Annotated[int, Field(ge=0)]
    competitive_sibling_event_leakage_count: Annotated[int, Field(ge=0)]
    shared_fragment_recall: Annotated[float, Field(ge=0, le=1)]
    none_case_count: Annotated[int, Field(ge=0)]
    none_correct_count: Annotated[int, Field(ge=0)]
    none_accuracy: Annotated[float, Field(ge=0, le=1)]
    unclear_count: Annotated[int, Field(ge=0)]
    unclear_rate: Annotated[float, Field(ge=0, le=1)]
    invalid_output_count: Annotated[int, Field(ge=0)]
    invalid_output_rate: Annotated[float, Field(ge=0, le=1)]
    model_failed_count: Annotated[int, Field(ge=0)]
    model_failed_rate: Annotated[float, Field(ge=0, le=1)]
    context_budget_blocked_count: Annotated[int, Field(ge=0)]
    context_budget_blocked_rate: Annotated[float, Field(ge=0, le=1)]
    unresolved_count: Annotated[int, Field(ge=0)]
    unresolved_rate: Annotated[float, Field(ge=0, le=1)]
    silent_drop_count: Literal[0] = 0
    baseline_entity_recall: Annotated[float, Field(ge=0, le=1)]
    competitive_entity_recall: Annotated[float, Field(ge=0, le=1)]
    baseline_qualification_recall: Annotated[float, Field(ge=0, le=1)]
    competitive_qualification_recall: Annotated[float, Field(ge=0, le=1)]
    baseline_character_precision: Annotated[float, Field(ge=0, le=1)]
    baseline_character_recall: Annotated[float, Field(ge=0, le=1)]
    baseline_character_f1: Annotated[float, Field(ge=0, le=1)]
    competitive_character_precision: Annotated[float, Field(ge=0, le=1)]
    competitive_character_recall: Annotated[float, Field(ge=0, le=1)]
    competitive_character_f1: Annotated[float, Field(ge=0, le=1)]
    baseline_exact_event_count: Annotated[int, Field(ge=0)]
    competitive_exact_event_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.none_correct_count > self.none_case_count:
            raise ValueError("Competitive Attachment NONE count drifted.")
        if self.unresolved_count != (
            self.unclear_count
            + self.invalid_output_count
            + self.model_failed_count
            + self.context_budget_blocked_count
        ):
            raise ValueError("Competitive Attachment unresolved count drifted.")
        for label, count, rate in (
            ("NONE", self.none_correct_count, self.none_accuracy),
            ("UNCLEAR", self.unclear_count, self.unclear_rate),
            ("invalid output", self.invalid_output_count, self.invalid_output_rate),
            ("model failure", self.model_failed_count, self.model_failed_rate),
            (
                "context-budget block",
                self.context_budget_blocked_count,
                self.context_budget_blocked_rate,
            ),
            ("unresolved", self.unresolved_count, self.unresolved_rate),
        ):
            denominator = self.none_case_count if label == "NONE" else self.candidate_count
            expected = 1.0 if denominator == 0 else count / denominator
            if rate != expected:
                raise ValueError(f"Competitive Attachment {label} rate drifted.")
        return self


class CompetitiveAttachmentPhaseReport(BaseModel):
    """Complete typed evidence for one phase and repetition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_attachment_phase_report_v1"] = (
        "competitive_attachment_phase_report_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    phase: Literal["development", "validation"]
    repetition: Annotated[int, Field(ge=1)]
    cases: tuple[CompetitiveAttachmentCaseEvaluation, ...]
    metrics: CompetitiveAttachmentMetrics
    source_validity: Annotated[float, Field(ge=0, le=1)]
    gold_coverage: Annotated[float, Field(ge=0, le=1)]
    model_execution_count: Annotated[int, Field(ge=0)]
    input_token_count: Annotated[int, Field(ge=0)]
    output_token_count: Annotated[int, Field(ge=0)]
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) == 0:
            raise ValueError("Competitive Attachment phase report requires candidate cases.")
        if tuple(sorted(self.cases, key=lambda item: item.candidate_id)) != self.cases:
            raise ValueError("Competitive Attachment cases must use canonical order.")
        if self.metrics.candidate_count != len(self.cases):
            raise ValueError("Competitive Attachment report candidate count drifted.")
        if self.model_execution_count != len(self.cases):
            raise ValueError("Competitive Attachment report model execution count drifted.")
        return self


def build_competitive_attachment_matrix(
    *,
    source_text: str,
    event_inputs: tuple[tuple[SourceGroundedEventDraft, EventTriggerDraft], ...],
    candidates_by_event: dict[str, tuple[PropositionFragmentCandidate, ...]],
    decisions: tuple[CompetitiveAttachmentDecision, ...] = (),
) -> CompetitiveAttachmentMatrix:
    """Union Event-specific candidates into one exact occurrence inventory."""
    if not event_inputs:
        raise ValueError("Competitive Attachment requires at least one Event.")
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    ordered_inputs = tuple(
        sorted(event_inputs, key=lambda item: (item[1].start, item[1].end, item[0].id))
    )
    source_segment_ids = {item[0].source_segment_id for item in ordered_inputs}
    if len(source_segment_ids) != 1:
        raise ValueError("Competing Events must belong to one SourceSegment.")
    source_segment_id = next(iter(source_segment_ids))
    options: list[CompetitiveAttachmentEventOption] = []
    for ordinal, (event, trigger) in enumerate(ordered_inputs, start=1):
        if (
            event.trigger_id != trigger.id
            or event.source_segment_id != trigger.source_segment_id
            or event.source_text_sha256 != source_digest
            or trigger.source_text_sha256 != source_digest
            or source_text[trigger.start : trigger.end] != trigger.text
            or event.expression_text != trigger.text
        ):
            raise ValueError("Competitive Attachment Event evidence is not source-exact.")
        options.append(
            CompetitiveAttachmentEventOption(
                id=competitive_attachment_event_option_id(
                    source_grounded_event_id=event.id,
                    event_trigger_id=trigger.id,
                    source_segment_id=source_segment_id,
                    source_text_sha256=source_digest,
                    start=trigger.start,
                    end=trigger.end,
                    text=trigger.text,
                ),
                label=f"E{ordinal}",
                source_grounded_event_id=event.id,
                event_trigger_id=trigger.id,
                source_segment_id=source_segment_id,
                source_text_sha256=source_digest,
                start=trigger.start,
                end=trigger.end,
                text=trigger.text,
            )
        )
    if set(candidates_by_event) != {event.id for event, _ in ordered_inputs}:
        raise ValueError("Competitive Attachment candidate inventory does not cover its Events.")
    grouped: dict[tuple[int, int, str], list[PropositionFragmentCandidate]] = defaultdict(list)
    for event, _ in ordered_inputs:
        for candidate in candidates_by_event[event.id]:
            if (
                candidate.source_grounded_event_id != event.id
                or candidate.source_segment_id != source_segment_id
                or candidate.source_text_sha256 != source_digest
                or source_text[candidate.start : candidate.end] != candidate.text
            ):
                raise ValueError("Competitive Attachment Candidate is not source-exact.")
            grouped[(candidate.start, candidate.end, candidate.text)].append(candidate)
    candidates = tuple(
        _merge_candidate(source_segment_id, source_digest, key, tuple(parents))
        for key, parents in sorted(grouped.items())
    )
    matrix_id = competitive_attachment_matrix_id(
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        candidate_ids=tuple(item.id for item in candidates),
        event_option_ids=tuple(item.id for item in options),
        decision_ids=tuple(item.id for item in decisions),
    )
    return CompetitiveAttachmentMatrix(
        id=matrix_id,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        candidates=candidates,
        event_options=tuple(options),
        decisions=decisions,
    )


def competitive_attachment_model_task_input(
    *,
    source_text: str,
    candidate: CompetitiveAttachmentCandidate,
    event_options: tuple[CompetitiveAttachmentEventOption, ...],
) -> bytes:
    """Render one candidate and every competing Event without canonical identifiers."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if (
        candidate.source_text_sha256 != source_digest
        or source_text[candidate.start : candidate.end] != candidate.text
    ):
        raise ValueError("Competitive Attachment task candidate is not source-exact.")
    if not event_options or any(
        item.source_segment_id != candidate.source_segment_id
        or item.source_text_sha256 != source_digest
        or source_text[item.start : item.end] != item.text
        for item in event_options
    ):
        raise ValueError("Competitive Attachment task Events are not source-exact.")
    lines = [
        "Candidate occurrence:",
        f"<source>{_mark(source_text, candidate.start, candidate.end, 'candidate')}</source>",
        "",
        "Event options:",
    ]
    for option in event_options:
        marked = _mark_candidate_and_event(
            source_text,
            candidate_start=candidate.start,
            candidate_end=candidate.end,
            event_start=option.start,
            event_end=option.end,
        )
        lines.append(f"{option.label}:")
        if marked is None:
            candidate_view = _mark(source_text, candidate.start, candidate.end, "candidate")
            event_view = _mark(source_text, option.start, option.end, "event")
            lines.extend(
                (
                    "Candidate view:",
                    f"<source>{candidate_view}</source>",
                    "Event view:",
                    f"<source>{event_view}</source>",
                )
            )
        else:
            lines.append(f"<source>{marked}</source>")
    return ("\n".join(lines) + "\n").encode()


def competitive_attachment_task_event_options(
    event_options: tuple[CompetitiveAttachmentEventOption, ...],
    event_order: CompetitiveAttachmentEventOrder,
) -> tuple[CompetitiveAttachmentEventOption, ...]:
    """Assign task-local labels after applying one declared Event order."""
    if not event_options:
        raise ValueError("Competitive Attachment task order requires Event options.")
    ordered = (
        event_options
        if event_order is CompetitiveAttachmentEventOrder.SOURCE
        else tuple(reversed(event_options))
    )
    return tuple(
        CompetitiveAttachmentEventOption(
            id=option.id,
            label=f"E{ordinal}",
            source_grounded_event_id=option.source_grounded_event_id,
            event_trigger_id=option.event_trigger_id,
            source_segment_id=option.source_segment_id,
            source_text_sha256=option.source_text_sha256,
            start=option.start,
            end=option.end,
            text=option.text,
        )
        for ordinal, option in enumerate(ordered, start=1)
    )


def canonicalize_competitive_attachment_answer(
    answer: CompetitiveAttachmentAnswer,
    *,
    task_event_options: tuple[CompetitiveAttachmentEventOption, ...],
    canonical_event_options: tuple[CompetitiveAttachmentEventOption, ...],
) -> CompetitiveAttachmentAnswer:
    """Map task-local Event labels back to canonical source-order labels."""
    if answer.kind is not CompetitiveAttachmentAnswerKind.ATTACHED:
        return answer
    task_by_label = {item.label: item.source_grounded_event_id for item in task_event_options}
    canonical_by_event = {
        item.source_grounded_event_id: item.label for item in canonical_event_options
    }
    if set(task_by_label.values()) != set(canonical_by_event):
        raise ValueError("Task Event options do not match the canonical Competing Event Set.")
    canonical_labels = tuple(
        sorted(
            (canonical_by_event[task_by_label[label]] for label in answer.event_labels),
            key=lambda label: int(label[1:]),
        )
    )
    return CompetitiveAttachmentAnswer(
        CompetitiveAttachmentAnswerKind.ATTACHED,
        canonical_labels,
    )


def complete_competitive_attachment_matrix(
    matrix: CompetitiveAttachmentMatrix,
    decisions: tuple[CompetitiveAttachmentDecision, ...],
) -> CompetitiveAttachmentMatrix:
    """Attach one ordered terminal decision to every matrix candidate."""
    matrix_id = competitive_attachment_matrix_id(
        source_segment_id=matrix.source_segment_id,
        source_text_sha256=matrix.source_text_sha256,
        candidate_ids=tuple(item.id for item in matrix.candidates),
        event_option_ids=tuple(item.id for item in matrix.event_options),
        decision_ids=tuple(item.id for item in decisions),
    )
    return CompetitiveAttachmentMatrix(
        id=matrix_id,
        source_segment_id=matrix.source_segment_id,
        source_text_sha256=matrix.source_text_sha256,
        candidates=matrix.candidates,
        event_options=matrix.event_options,
        decisions=decisions,
    )


def build_competitive_attachment_decision(
    *,
    candidate: CompetitiveAttachmentCandidate,
    event_options: tuple[CompetitiveAttachmentEventOption, ...],
    status: CompetitiveAttachmentDecisionStatus,
    answer: CompetitiveAttachmentAnswer | None,
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
    raw_output: bytes | None,
    diagnostic_code: str | None,
) -> CompetitiveAttachmentDecision:
    """Map one invocation-bound answer to exact Event occurrences."""
    by_label = {item.label: item for item in event_options}
    deterministic = tuple(
        sorted(
            item.source_grounded_event_id
            for item in event_options
            if item.start == candidate.start and item.end == candidate.end
        )
    )
    labels = answer.event_labels if answer is not None else ()
    model_events = (
        tuple(sorted(by_label[label].source_grounded_event_id for label in labels))
        if answer is not None and answer.kind is CompetitiveAttachmentAnswerKind.ATTACHED
        else ()
    )
    origins_by_event: dict[str, set[CompetitiveAttachmentEdgeOrigin]] = defaultdict(set)
    for event_id in deterministic:
        origins_by_event[event_id].add(
            CompetitiveAttachmentEdgeOrigin.DETERMINISTIC_EVENT_EXPRESSION
        )
    for event_id in model_events:
        origins_by_event[event_id].add(CompetitiveAttachmentEdgeOrigin.MODEL_SELECTION)
    option_by_event = {item.source_grounded_event_id: item for item in event_options}
    edges = tuple(
        _edge(
            candidate.id,
            option_by_event[event_id],
            tuple(sorted(origins, key=lambda value: value.value)),
        )
        for event_id, origins in sorted(origins_by_event.items())
    )
    raw_digest = hashlib.sha256(raw_output).hexdigest() if raw_output is not None else None
    raw_base64 = base64.b64encode(raw_output).decode("ascii") if raw_output is not None else None
    omitted = tuple(sorted(set(deterministic) - set(model_events)))
    decision_id = competitive_attachment_decision_id(
        candidate_id=candidate.id,
        status=status,
        parsed_event_labels=labels,
        deterministic_event_ids=deterministic,
        model_event_ids=model_events,
        edge_ids=tuple(item.id for item in edges),
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
        raw_output_sha256=raw_digest,
        diagnostic_code=diagnostic_code,
    )
    return CompetitiveAttachmentDecision(
        id=decision_id,
        candidate_id=candidate.id,
        status=status,
        parsed_event_labels=labels,
        deterministic_event_ids=deterministic,
        model_event_ids=model_events,
        omitted_deterministic_event_ids=omitted,
        edges=edges,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
        raw_output_base64=raw_base64,
        raw_output_sha256=raw_digest,
        diagnostic_code=diagnostic_code,
    )


def competitive_attachment_candidate_id(**values: object) -> str:
    return _id("cac", values)


def competitive_attachment_event_option_id(**values: object) -> str:
    return _id("cao", values)


def competitive_attachment_edge_id(**values: object) -> str:
    return _id("cae", values)


def competitive_attachment_decision_id(**values: object) -> str:
    return _id("cad", values)


def competitive_attachment_matrix_id(**values: object) -> str:
    identity_values = dict(values)
    identity_values.pop("decision_ids", None)
    return _id("cam", identity_values)


def _merge_candidate(
    source_segment_id: str,
    source_digest: str,
    key: tuple[int, int, str],
    parents: tuple[PropositionFragmentCandidate, ...],
) -> CompetitiveAttachmentCandidate:
    start, end, text = key
    reasons = tuple(
        sorted(
            {reason for item in parents for reason in item.reasons},
            key=lambda value: value.value,
        )
    )
    parent_ids = tuple(sorted(item.id for item in parents))
    token_ids = tuple(sorted({value for item in parents for value in item.linguistic_token_ids}))
    record_ids = tuple(sorted({value for item in parents for value in item.source_record_ids}))
    values: dict[str, object] = {
        "source_segment_id": source_segment_id,
        "source_text_sha256": source_digest,
        "start": start,
        "end": end,
        "text": text,
        "reasons": reasons,
        "parent_candidate_ids": parent_ids,
        "linguistic_token_ids": token_ids,
        "source_record_ids": record_ids,
    }
    return CompetitiveAttachmentCandidate(
        id=competitive_attachment_candidate_id(**values),
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        start=start,
        end=end,
        text=text,
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )


def _edge(
    candidate_id: str,
    option: CompetitiveAttachmentEventOption,
    origins: tuple[CompetitiveAttachmentEdgeOrigin, ...],
) -> CompetitiveAttachmentEdge:
    values: dict[str, object] = {
        "candidate_id": candidate_id,
        "event_option_id": option.id,
        "source_grounded_event_id": option.source_grounded_event_id,
        "origins": origins,
    }
    return CompetitiveAttachmentEdge(
        id=competitive_attachment_edge_id(**values),
        candidate_id=candidate_id,
        event_option_id=option.id,
        source_grounded_event_id=option.source_grounded_event_id,
        origins=origins,
    )


def _mark(source_text: str, start: int, end: int, label: str) -> str:
    return (
        source_text[:start]
        + f"<{label}>"
        + source_text[start:end]
        + f"</{label}>"
        + source_text[end:]
    )


def _mark_candidate_and_event(
    source_text: str,
    *,
    candidate_start: int,
    candidate_end: int,
    event_start: int,
    event_end: int,
) -> str | None:
    if candidate_end <= event_start:
        return (
            source_text[:candidate_start]
            + "<candidate>"
            + source_text[candidate_start:candidate_end]
            + "</candidate>"
            + source_text[candidate_end:event_start]
            + "<event>"
            + source_text[event_start:event_end]
            + "</event>"
            + source_text[event_end:]
        )
    if event_end <= candidate_start:
        return (
            source_text[:event_start]
            + "<event>"
            + source_text[event_start:event_end]
            + "</event>"
            + source_text[event_end:candidate_start]
            + "<candidate>"
            + source_text[candidate_start:candidate_end]
            + "</candidate>"
            + source_text[candidate_end:]
        )
    if candidate_start <= event_start and event_end <= candidate_end:
        return (
            source_text[:candidate_start]
            + "<candidate>"
            + source_text[candidate_start:event_start]
            + "<event>"
            + source_text[event_start:event_end]
            + "</event>"
            + source_text[event_end:candidate_end]
            + "</candidate>"
            + source_text[candidate_end:]
        )
    if event_start <= candidate_start and candidate_end <= event_end:
        return (
            source_text[:event_start]
            + "<event>"
            + source_text[event_start:candidate_start]
            + "<candidate>"
            + source_text[candidate_start:candidate_end]
            + "</candidate>"
            + source_text[candidate_end:event_end]
            + "</event>"
            + source_text[event_end:]
        )
    return None


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"Competitive Attachment {label} must be ordered and distinct.")


def _id(prefix: str, values: object) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), default=_json_default)
    return f"{prefix}_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def _json_default(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError(f"Unsupported competitive attachment identity value: {type(value)!r}")
