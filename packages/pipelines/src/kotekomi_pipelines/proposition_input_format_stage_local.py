"""Stage-local evaluation for marker-free proposition membership input."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_application import (
    PropositionFragmentAnswerValue,
    PropositionFragmentCandidate,
    PropositionFragmentTaskInput,
    PropositionFragmentTaskInputStatus,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[a-f0-9]{64}$"


class PropositionInputGoldClass(StrEnum):
    """Gold expectation for one deterministic Fragment Candidate."""

    COMPATIBLE = "gold_compatible"
    OVERREACHING = "gold_overreaching"


class PropositionInputHypothesisOutcome(StrEnum):
    """Direction of the paired marker-free result."""

    SUPPORTED = "supported"
    FALSIFIED = "falsified"
    MIXED = "mixed"


class PropositionInputFormatInventoryItem(BaseModel):
    """Pinned baseline candidate and exact v3 evidence for one paired replay."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["proposition_input_format_inventory_item_v1"] = (
        "proposition_input_format_inventory_item_v1"
    )
    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    source_text: Annotated[str, Field(min_length=1)]
    event_text: Annotated[str, Field(min_length=1)]
    candidate: PropositionFragmentCandidate
    gold_class: PropositionInputGoldClass
    task_input: PropositionFragmentTaskInput
    baseline_exact_model_input: Annotated[str, Field(min_length=1)]
    baseline_raw_output: Annotated[str, Field(min_length=1)]
    baseline_answer: PropositionFragmentAnswerValue
    baseline_trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        source_digest = hashlib.sha256(self.source_text.encode()).hexdigest()
        if self.candidate.source_text_sha256 != source_digest:
            raise ValueError("Proposition input inventory candidate names another source.")
        if self.source_text[self.candidate.start : self.candidate.end] != self.candidate.text:
            raise ValueError("Proposition input inventory candidate does not replay its source.")
        if self.task_input.candidate_id != self.candidate.id:
            raise ValueError("Proposition input inventory task names another candidate.")
        if self.task_input.source_text_sha256 != source_digest:
            raise ValueError("Proposition input inventory task names another source.")
        if self.baseline_raw_output.strip(" \t\r\n\f\v") != self.baseline_answer.value:
            raise ValueError("Proposition input inventory baseline output is inconsistent.")
        return self


class PropositionInputFormatObservation(BaseModel):
    """Exact paired data-in/data-out for one unchanged Fragment Candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["proposition_input_format_observation_v1"] = (
        "proposition_input_format_observation_v1"
    )
    event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    candidate_id: Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")]
    source_text: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    event_text: Annotated[str, Field(min_length=1)]
    candidate_start: Annotated[int, Field(ge=0)]
    candidate_end: Annotated[int, Field(gt=0)]
    candidate_text: Annotated[str, Field(min_length=1)]
    gold_class: PropositionInputGoldClass
    task_input: PropositionFragmentTaskInput
    baseline_exact_model_input: Annotated[str, Field(min_length=1)]
    baseline_raw_output: Annotated[str, Field(min_length=1)]
    baseline_answer: PropositionFragmentAnswerValue
    baseline_trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]
    marker_free_exact_model_input: str | None
    marker_free_raw_output: str | None
    marker_free_answer: PropositionFragmentAnswerValue | None
    marker_free_execution_status: Literal["completed", "failed", "not_run"]
    marker_free_trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]
    marker_free_model_run_id: str | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Proposition input observation source digest is invalid.")
        if self.candidate_end - self.candidate_start != len(self.candidate_text):
            raise ValueError("Proposition input observation candidate range is invalid.")
        if self.source_text[self.candidate_start : self.candidate_end] != self.candidate_text:
            raise ValueError("Proposition input observation candidate does not replay its source.")
        if self.task_input.candidate_id != self.candidate_id:
            raise ValueError("Proposition input observation task names another candidate.")
        if self.task_input.source_text_sha256 != self.source_text_sha256:
            raise ValueError("Proposition input observation task names another source.")
        if self.baseline_raw_output.strip(" \t\r\n\f\v") != self.baseline_answer.value:
            raise ValueError("Proposition baseline raw output does not match its parsed answer.")
        marker_values = (
            self.marker_free_exact_model_input,
            self.marker_free_model_run_id,
        )
        if self.task_input.status is PropositionFragmentTaskInputStatus.READY:
            if any(value is None for value in marker_values):
                raise ValueError(
                    "A ready marker-free observation requires model execution evidence."
                )
            if self.marker_free_execution_status == "not_run":
                raise ValueError("A ready marker-free observation cannot be marked not run.")
            if self.task_input.rendered_input is None:
                raise ValueError("A ready marker-free observation requires visible task input.")
            if self.task_input.rendered_input not in (self.marker_free_exact_model_input or ""):
                raise ValueError("Marker-free exact input omits its visible task input.")
            if self.marker_free_execution_status == "completed":
                if self.marker_free_raw_output is None or self.marker_free_answer is None:
                    raise ValueError("A completed marker-free observation requires one answer.")
                if (
                    self.marker_free_raw_output.strip(" \t\r\n\f\v")
                    != self.marker_free_answer.value
                ):
                    raise ValueError("Marker-free raw output does not match its parsed answer.")
            elif self.marker_free_answer is not None:
                raise ValueError("A failed marker-free observation cannot have a parsed answer.")
        elif (
            any(value is not None for value in marker_values)
            or self.marker_free_raw_output is not None
            or self.marker_free_answer is not None
            or self.marker_free_execution_status != "not_run"
        ):
            raise ValueError("An ambiguous marker-free observation cannot have model evidence.")
        return self


class PropositionInputBinaryMetrics(BaseModel):
    """Binary compatibility metrics over one identical eligible subset."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_count: Annotated[int, Field(ge=0)]
    true_positive_count: Annotated[int, Field(ge=0)]
    true_negative_count: Annotated[int, Field(ge=0)]
    false_positive_count: Annotated[int, Field(ge=0)]
    false_negative_count: Annotated[int, Field(ge=0)]
    unresolved_count: Annotated[int, Field(ge=0)]
    accuracy: Annotated[float, Field(ge=0.0, le=1.0)]
    precision: Annotated[float, Field(ge=0.0, le=1.0)]
    recall: Annotated[float, Field(ge=0.0, le=1.0)]
    f1: Annotated[float, Field(ge=0.0, le=1.0)]

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        observed = (
            self.true_positive_count
            + self.true_negative_count
            + self.false_positive_count
            + self.false_negative_count
            + self.unresolved_count
        )
        if observed != self.candidate_count:
            raise ValueError("Proposition input metrics do not partition their candidates.")
        return self


class PropositionInputAnswerTransition(BaseModel):
    """Count of one baseline-to-marker-free answer transition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    baseline_answer: PropositionFragmentAnswerValue
    marker_free_answer: PropositionFragmentAnswerValue
    count: Annotated[int, Field(gt=0)]


class PropositionInputFormatReport(BaseModel):
    """Complete paired diagnostic over one pinned candidate inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["proposition_input_format_report_v1"] = (
        "proposition_input_format_report_v1"
    )
    baseline_run_sha256: Annotated[str, Field(pattern=_SHA256)]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    observation_count: Annotated[int, Field(gt=0)]
    eligible_candidate_count: Annotated[int, Field(gt=0)]
    excluded_ambiguous_candidate_count: Annotated[int, Field(ge=0)]
    baseline_metrics: PropositionInputBinaryMetrics
    marker_free_metrics: PropositionInputBinaryMetrics
    transitions: tuple[PropositionInputAnswerTransition, ...]
    hypothesis_outcome: PropositionInputHypothesisOutcome
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    observations: tuple[PropositionInputFormatObservation, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.observation_count != len(self.observations):
            raise ValueError("Proposition input report observation count is invalid.")
        eligible = sum(
            item.task_input.status is PropositionFragmentTaskInputStatus.READY
            for item in self.observations
        )
        if eligible != self.eligible_candidate_count:
            raise ValueError("Proposition input report eligible count is invalid.")
        if self.observation_count - eligible != self.excluded_ambiguous_candidate_count:
            raise ValueError("Proposition input report exclusion count is invalid.")
        if self.baseline_metrics.candidate_count != eligible:
            raise ValueError("Proposition baseline metrics use the wrong candidate subset.")
        if self.marker_free_metrics.candidate_count != eligible:
            raise ValueError("Marker-free metrics use the wrong candidate subset.")
        if tuple(
            sorted(self.observations, key=lambda item: (item.event_id, item.candidate_id))
        ) != (self.observations):
            raise ValueError("Proposition input observations must be ordered by identity.")
        if len({item.candidate_id for item in self.observations}) != len(self.observations):
            raise ValueError("Proposition input observations must name distinct candidates.")
        return self


def build_proposition_input_format_report(
    *,
    baseline_run_sha256: str,
    prompt_sha256: str,
    observations: tuple[PropositionInputFormatObservation, ...],
) -> PropositionInputFormatReport:
    """Compare marker-free answers with v3 over the identical eligible subset."""
    ordered = tuple(sorted(observations, key=lambda item: (item.event_id, item.candidate_id)))
    eligible = tuple(
        item
        for item in ordered
        if item.task_input.status is PropositionFragmentTaskInputStatus.READY
    )
    baseline = _metrics(eligible, marker_free=False)
    marker_free = _metrics(eligible, marker_free=True)
    transitions: dict[
        tuple[PropositionFragmentAnswerValue, PropositionFragmentAnswerValue], int
    ] = {}
    for item in eligible:
        if item.marker_free_answer is None:
            continue
        key = (item.baseline_answer, item.marker_free_answer)
        transitions[key] = transitions.get(key, 0) + 1
    transition_records = tuple(
        PropositionInputAnswerTransition(
            baseline_answer=key[0],
            marker_free_answer=key[1],
            count=count,
        )
        for key, count in sorted(
            transitions.items(),
            key=lambda item: (item[0][0].value, item[0][1].value),
        )
    )
    if marker_free.f1 > baseline.f1 and marker_free.accuracy > baseline.accuracy:
        outcome = PropositionInputHypothesisOutcome.SUPPORTED
    elif marker_free.f1 < baseline.f1 and marker_free.accuracy < baseline.accuracy:
        outcome = PropositionInputHypothesisOutcome.FALSIFIED
    else:
        outcome = PropositionInputHypothesisOutcome.MIXED
    return PropositionInputFormatReport(
        baseline_run_sha256=baseline_run_sha256,
        prompt_sha256=prompt_sha256,
        observation_count=len(ordered),
        eligible_candidate_count=len(eligible),
        excluded_ambiguous_candidate_count=len(ordered) - len(eligible),
        baseline_metrics=baseline,
        marker_free_metrics=marker_free,
        transitions=transition_records,
        hypothesis_outcome=outcome,
        observations=ordered,
    )


def _metrics(
    observations: tuple[PropositionInputFormatObservation, ...],
    *,
    marker_free: bool,
) -> PropositionInputBinaryMetrics:
    tp = tn = fp = fn = unresolved = 0
    for item in observations:
        answer = item.marker_free_answer if marker_free else item.baseline_answer
        if answer is None or answer is PropositionFragmentAnswerValue.UNCERTAIN:
            unresolved += 1
        elif item.gold_class is PropositionInputGoldClass.COMPATIBLE:
            if answer is PropositionFragmentAnswerValue.YES:
                tp += 1
            else:
                fn += 1
        elif answer is PropositionFragmentAnswerValue.NO:
            tn += 1
        else:
            fp += 1
    count = len(observations)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return PropositionInputBinaryMetrics(
        candidate_count=count,
        true_positive_count=tp,
        true_negative_count=tn,
        false_positive_count=fp,
        false_negative_count=fn,
        unresolved_count=unresolved,
        accuracy=(tp + tn) / count if count else 0.0,
        precision=precision,
        recall=recall,
        f1=(2 * precision * recall / (precision + recall)) if precision + recall else 0.0,
    )
