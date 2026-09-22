"""Typed evidence for CEA-1.20 exact Event self-attachment."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSourceRange,
)

_SHA256 = r"^[a-f0-9]{64}$"
type _Answer = Literal["Y", "N"]


class AttachmentSelfRoutingOutcome(StrEnum):
    """The terminal CEA-1.20 result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class AttachmentExactSelfCase(BaseModel):
    """One equal-range Candidate and Event pair from the complete inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    matrix_id: Annotated[str, Field(pattern=r"^cam_[a-f0-9]{24}$")]
    source_text: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    candidate_range: AttachmentSourceRange
    event_range: AttachmentSourceRange
    original_gold: _Answer
    reviewed_gold: _Answer | None
    gold_conflict: bool
    answer: Literal["Y"] = "Y"
    original_gold_correct: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Exact self-attachment source digest drifted.")
        for value in (self.candidate_range, self.event_range):
            if self.source_text[value.start : value.end] != value.text:
                raise ValueError("Exact self-attachment range is not source-exact.")
        if (self.candidate_range.start, self.candidate_range.end) != (
            self.event_range.start,
            self.event_range.end,
        ):
            raise ValueError("Exact self-attachment requires equal source ranges.")
        if self.candidate_range.text != self.event_range.text:
            raise ValueError("Equal exact self-attachment ranges require equal source text.")
        if self.gold_conflict != (
            self.reviewed_gold is not None and self.reviewed_gold != self.original_gold
        ):
            raise ValueError("Exact self-attachment Gold conflict flag drifted.")
        if self.original_gold_correct != (self.original_gold == "Y"):
            raise ValueError("Exact self-attachment Original Gold evaluation drifted.")
        return self


class AttachmentSelfRoutingPhase(BaseModel):
    """One complete-inventory phase evaluated for equal source ranges."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    exact_self_cases: tuple[AttachmentExactSelfCase, ...]
    all_edge_count: Annotated[int, Field(ge=0)]
    exact_self_count: Annotated[int, Field(ge=0)]
    unequal_range_count: Annotated[int, Field(ge=0)]
    exact_self_original_positive_count: Annotated[int, Field(ge=0)]
    exact_self_original_negative_count: Annotated[int, Field(ge=0)]
    exact_self_reviewed_count: Annotated[int, Field(ge=0)]
    exact_self_gold_conflict_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if any(item.phase != self.phase for item in self.exact_self_cases):
            raise ValueError("Exact self-attachment phase contains a foreign case.")
        if (
            tuple(
                sorted(
                    self.exact_self_cases,
                    key=lambda item: (
                        item.matrix_id,
                        item.candidate_range.start,
                        item.candidate_range.end,
                        item.event_id,
                    ),
                )
            )
            != self.exact_self_cases
        ):
            raise ValueError("Exact self-attachment cases must use canonical order.")
        observed = (
            self.exact_self_count,
            self.unequal_range_count,
            self.exact_self_original_positive_count,
            self.exact_self_original_negative_count,
            self.exact_self_reviewed_count,
            self.exact_self_gold_conflict_count,
        )
        expected = (
            len(self.exact_self_cases),
            self.all_edge_count - len(self.exact_self_cases),
            sum(item.original_gold == "Y" for item in self.exact_self_cases),
            sum(item.original_gold == "N" for item in self.exact_self_cases),
            sum(item.reviewed_gold is not None for item in self.exact_self_cases),
            sum(item.gold_conflict for item in self.exact_self_cases),
        )
        if self.all_edge_count < len(self.exact_self_cases) or observed != expected:
            raise ValueError("Exact self-attachment phase counts drifted.")
        return self


class AttachmentReviewedNegativeControl(BaseModel):
    """One independently reviewed negative and its exact-self route result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_id: Annotated[str, Field(pattern=r"^aro_[a-f0-9]{24}$")]
    phase: Literal["development", "validation"]
    source_text: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_range: AttachmentSourceRange
    event_range: AttachmentSourceRange
    expected_answer: Literal["N"] = "N"
    exact_self_selected: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Exact self-attachment control source digest drifted.")
        for value in (self.candidate_range, self.event_range):
            if self.source_text[value.start : value.end] != value.text:
                raise ValueError("Exact self-attachment control range is not source-exact.")
        expected = (
            self.candidate_range.start == self.event_range.start
            and self.candidate_range.end == self.event_range.end
        )
        if self.exact_self_selected != expected:
            raise ValueError("Exact self-attachment control route drifted from source ranges.")
        return self


class AttachmentSelfRoutingReport(BaseModel):
    """The complete CEA-1.20 exact self-attachment result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inputs: tuple[AttachmentEvidenceReference, ...]
    development: AttachmentSelfRoutingPhase
    validation: AttachmentSelfRoutingPhase
    reviewed_negative_controls: tuple[AttachmentReviewedNegativeControl, ...]
    outcome: AttachmentSelfRoutingOutcome
    all_edge_count: Annotated[int, Field(ge=0)]
    exact_self_count: Annotated[int, Field(ge=0)]
    unequal_range_count: Annotated[int, Field(ge=0)]
    exact_self_original_negative_count: Annotated[int, Field(ge=0)]
    exact_self_gold_conflict_count: Annotated[int, Field(ge=0)]
    head_aligned_count: Annotated[int, Field(ge=0)]
    head_aligned_exact_self_count: Annotated[int, Field(ge=0)]
    head_aligned_unequal_range_count: Annotated[int, Field(ge=0)]
    head_aligned_gold_conflict_count: Annotated[int, Field(ge=0)]
    reviewed_negative_control_count: Annotated[int, Field(ge=0)]
    routed_reviewed_negative_control_count: Annotated[int, Field(ge=0)]
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        phases = (self.development, self.validation)
        observed = (
            self.all_edge_count,
            self.exact_self_count,
            self.unequal_range_count,
            self.exact_self_original_negative_count,
            self.exact_self_gold_conflict_count,
            self.head_aligned_unequal_range_count,
            self.reviewed_negative_control_count,
            self.routed_reviewed_negative_control_count,
        )
        expected = (
            sum(item.all_edge_count for item in phases),
            sum(item.exact_self_count for item in phases),
            sum(item.unequal_range_count for item in phases),
            sum(item.exact_self_original_negative_count for item in phases),
            sum(item.exact_self_gold_conflict_count for item in phases),
            self.head_aligned_count - self.head_aligned_exact_self_count,
            len(self.reviewed_negative_controls),
            sum(item.exact_self_selected for item in self.reviewed_negative_controls),
        )
        if observed != expected:
            raise ValueError("Exact self-attachment report counts drifted.")
        if self.head_aligned_exact_self_count > self.exact_self_count:
            raise ValueError("Head-aligned exact pairs exceed the complete exact inventory.")
        if self.head_aligned_exact_self_count > self.head_aligned_count:
            raise ValueError("Head-aligned exact pairs exceed Head-Aligned inventory.")
        if (
            tuple(sorted(self.reviewed_negative_controls, key=lambda item: item.task_id))
            != self.reviewed_negative_controls
        ):
            raise ValueError("Exact self-attachment controls must use canonical order.")
        expected_outcome = classify_attachment_self_routing_outcome(
            exact_self_original_negative_count=self.exact_self_original_negative_count,
            routed_reviewed_negative_control_count=self.routed_reviewed_negative_control_count,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Exact self-attachment outcome drifted.")
        if self.result_fingerprint != attachment_self_routing_fingerprint(self):
            raise ValueError("Exact self-attachment result fingerprint drifted.")
        return self


def classify_attachment_self_routing_outcome(
    *,
    exact_self_original_negative_count: int,
    routed_reviewed_negative_control_count: int,
) -> AttachmentSelfRoutingOutcome:
    """Classify the exact source-range route against both evidence sets."""
    if exact_self_original_negative_count:
        return AttachmentSelfRoutingOutcome.FALSIFIED
    if routed_reviewed_negative_control_count:
        return AttachmentSelfRoutingOutcome.MIXED
    return AttachmentSelfRoutingOutcome.SUPPORTED


def attachment_self_routing_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.20 DTO."""
    payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
