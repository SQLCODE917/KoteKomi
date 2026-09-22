"""Typed evidence for the CEA-1.19 Structural Route safety sweep."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_dependency_head_routing import (
    AttachmentCandidateRootEvidence,
    attachment_syntax_is_head_aligned,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSyntaxObservation,
)
from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
)

_SHA256 = r"^[a-f0-9]{64}$"
type _Answer = Literal["Y", "N"]


class AttachmentGoldAuthority(StrEnum):
    """The Gold source selected for one exact edge."""

    ORIGINAL = "original"
    REVIEWED = "reviewed"


class AttachmentStructuralEligibility(StrEnum):
    """The deterministic Structural Route eligibility result."""

    ELIGIBLE = "eligible"
    FOREIGN_EVENT = "foreign_event"


class AttachmentStructuralSafetyOutcome(StrEnum):
    """The terminal CEA-1.19 result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class AttachmentStructuralSafetyCase(BaseModel):
    """One Head-Aligned edge with exact eligibility and Gold evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    matrix_id: Annotated[str, Field(pattern=r"^cam_[a-f0-9]{24}$")]
    source_text: Annotated[str, Field(min_length=1)]
    candidate: CompetitiveAttachmentCandidate
    event: CompetitiveAttachmentEventOption
    syntax: AttachmentSyntaxObservation
    candidate_root_evidence: AttachmentCandidateRootEvidence
    original_gold: _Answer
    reviewed_gold: _Answer | None
    effective_gold: _Answer
    gold_authority: AttachmentGoldAuthority
    gold_conflict: bool
    foreign_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    eligibility: AttachmentStructuralEligibility
    structural_answer: Literal["Y"] | None
    correctly_routed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        digest = hashlib.sha256(self.source_text.encode()).hexdigest()
        if (
            self.candidate.source_segment_id != self.event.source_segment_id
            or self.candidate.source_text_sha256 != digest
            or self.event.source_text_sha256 != digest
            or self.syntax.phase != self.phase
            or self.syntax.candidate_id != self.candidate.id
            or self.syntax.source_grounded_event_id != self.event.source_grounded_event_id
        ):
            raise ValueError("Structural safety case contains foreign source evidence.")
        if (
            self.source_text[self.candidate.start : self.candidate.end] != self.candidate.text
            or self.source_text[self.event.start : self.event.end] != self.event.text
        ):
            raise ValueError("Structural safety case is not source-exact.")
        tokens = self.candidate_root_evidence.tokens
        if tuple(item.token_id for item in tokens) != self.candidate.linguistic_token_ids:
            raise ValueError("Structural safety Candidate token inventory is incomplete.")
        if any(
            item.start < self.candidate.start
            or item.end > self.candidate.end
            or self.source_text[item.start : item.end] != item.text
            for item in tokens
        ):
            raise ValueError("Structural safety Candidate token is not source-exact.")
        if not attachment_syntax_is_head_aligned(
            self.syntax,
            self.candidate_root_evidence.roots,
        ):
            raise ValueError("Structural safety case must be Head-Aligned.")
        if self.foreign_event_ids != tuple(dict.fromkeys(self.foreign_event_ids)):
            raise ValueError("Structural safety Foreign Events must be ordered and distinct.")
        expected_authority = (
            AttachmentGoldAuthority.REVIEWED
            if self.reviewed_gold is not None
            else AttachmentGoldAuthority.ORIGINAL
        )
        expected_gold = self.reviewed_gold or self.original_gold
        if self.gold_authority is not expected_authority or self.effective_gold != expected_gold:
            raise ValueError("Structural safety Effective Gold drifted from its authority.")
        if self.gold_conflict != (
            self.reviewed_gold is not None and self.reviewed_gold != self.original_gold
        ):
            raise ValueError("Structural safety Gold conflict flag drifted.")
        expected_eligibility = (
            AttachmentStructuralEligibility.FOREIGN_EVENT
            if self.foreign_event_ids
            else AttachmentStructuralEligibility.ELIGIBLE
        )
        if self.eligibility is not expected_eligibility:
            raise ValueError("Structural safety eligibility drifted from Foreign Events.")
        expected_answer = (
            "Y" if expected_eligibility is AttachmentStructuralEligibility.ELIGIBLE else None
        )
        if self.structural_answer != expected_answer:
            raise ValueError("Structural safety answer drifted from eligibility.")
        expected_correct = (self.effective_gold == "Y") == (
            self.eligibility is AttachmentStructuralEligibility.ELIGIBLE
        )
        if self.correctly_routed != expected_correct:
            raise ValueError("Structural safety evaluation drifted.")
        return self


class AttachmentStructuralSafetyPhase(BaseModel):
    """One complete phase of the Structural Route safety sweep."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    total_edge_count: Annotated[int, Field(ge=0)]
    cases: tuple[AttachmentStructuralSafetyCase, ...]
    head_aligned_count: Annotated[int, Field(ge=0)]
    original_positive_count: Annotated[int, Field(ge=0)]
    original_negative_count: Annotated[int, Field(ge=0)]
    reviewed_edge_count: Annotated[int, Field(ge=0)]
    gold_conflict_count: Annotated[int, Field(ge=0)]
    effective_positive_count: Annotated[int, Field(ge=0)]
    effective_negative_count: Annotated[int, Field(ge=0)]
    eligible_count: Annotated[int, Field(ge=0)]
    excluded_count: Annotated[int, Field(ge=0)]
    eligible_positive_count: Annotated[int, Field(ge=0)]
    eligible_negative_count: Annotated[int, Field(ge=0)]
    excluded_positive_count: Annotated[int, Field(ge=0)]
    excluded_negative_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            tuple(
                sorted(
                    self.cases,
                    key=lambda item: (
                        item.matrix_id,
                        item.candidate.start,
                        item.candidate.end,
                        item.event.start,
                        item.event.end,
                        item.event.source_grounded_event_id,
                    ),
                )
            )
            != self.cases
        ):
            raise ValueError("Structural safety cases must use canonical order.")
        if any(item.phase != self.phase for item in self.cases):
            raise ValueError("Structural safety phase contains a foreign case.")
        eligible = tuple(
            item
            for item in self.cases
            if item.eligibility is AttachmentStructuralEligibility.ELIGIBLE
        )
        excluded = tuple(
            item
            for item in self.cases
            if item.eligibility is AttachmentStructuralEligibility.FOREIGN_EVENT
        )
        observed = (
            self.head_aligned_count,
            self.original_positive_count,
            self.original_negative_count,
            self.reviewed_edge_count,
            self.gold_conflict_count,
            self.effective_positive_count,
            self.effective_negative_count,
            self.eligible_count,
            self.excluded_count,
            self.eligible_positive_count,
            self.eligible_negative_count,
            self.excluded_positive_count,
            self.excluded_negative_count,
        )
        expected = (
            len(self.cases),
            sum(item.original_gold == "Y" for item in self.cases),
            sum(item.original_gold == "N" for item in self.cases),
            sum(item.reviewed_gold is not None for item in self.cases),
            sum(item.gold_conflict for item in self.cases),
            sum(item.effective_gold == "Y" for item in self.cases),
            sum(item.effective_gold == "N" for item in self.cases),
            len(eligible),
            len(excluded),
            sum(item.effective_gold == "Y" for item in eligible),
            sum(item.effective_gold == "N" for item in eligible),
            sum(item.effective_gold == "Y" for item in excluded),
            sum(item.effective_gold == "N" for item in excluded),
        )
        if observed != expected:
            raise ValueError("Structural safety phase counts drifted.")
        return self


class AttachmentStructuralSafetyReport(BaseModel):
    """The complete CEA-1.19 full-inventory safety result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inputs: tuple[AttachmentEvidenceReference, ...]
    development: AttachmentStructuralSafetyPhase
    validation: AttachmentStructuralSafetyPhase
    outcome: AttachmentStructuralSafetyOutcome
    total_edge_count: Annotated[int, Field(ge=0)]
    head_aligned_count: Annotated[int, Field(ge=0)]
    gold_conflict_count: Annotated[int, Field(ge=0)]
    foreign_event_exclusion_count: Annotated[int, Field(ge=0)]
    eligible_count: Annotated[int, Field(ge=0)]
    eligible_negative_count: Annotated[int, Field(ge=0)]
    excluded_positive_count: Annotated[int, Field(ge=0)]
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        phases = (self.development, self.validation)
        observed = (
            self.total_edge_count,
            self.head_aligned_count,
            self.gold_conflict_count,
            self.foreign_event_exclusion_count,
            self.eligible_count,
            self.eligible_negative_count,
            self.excluded_positive_count,
        )
        expected = (
            sum(item.total_edge_count for item in phases),
            sum(item.head_aligned_count for item in phases),
            sum(item.gold_conflict_count for item in phases),
            sum(item.excluded_count for item in phases),
            sum(item.eligible_count for item in phases),
            sum(item.eligible_negative_count for item in phases),
            sum(item.excluded_positive_count for item in phases),
        )
        if observed != expected:
            raise ValueError("Structural safety aggregate counts drifted.")
        expected_outcome = classify_attachment_structural_safety_outcome(
            eligible_negative_count=self.eligible_negative_count,
            excluded_positive_count=self.excluded_positive_count,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Structural safety outcome drifted.")
        if self.result_fingerprint != attachment_structural_safety_fingerprint(self):
            raise ValueError("Structural safety result fingerprint drifted.")
        return self


def attachment_complete_foreign_event_ids(
    candidate: CompetitiveAttachmentCandidate,
    event: CompetitiveAttachmentEventOption,
    event_options: tuple[CompetitiveAttachmentEventOption, ...],
) -> tuple[str, ...]:
    """Return complete Other Event ranges contained by one Candidate."""
    if event not in event_options:
        raise ValueError("Structural safety Target Event is absent from its Event options.")
    if any(
        item.source_segment_id != candidate.source_segment_id
        or item.source_text_sha256 != candidate.source_text_sha256
        for item in event_options
    ):
        raise ValueError("Structural safety Event options contain foreign source evidence.")
    return tuple(
        item.source_grounded_event_id
        for item in event_options
        if item.source_grounded_event_id != event.source_grounded_event_id
        and candidate.start <= item.start
        and item.end <= candidate.end
    )


def classify_attachment_structural_safety_outcome(
    *,
    eligible_negative_count: int,
    excluded_positive_count: int,
) -> AttachmentStructuralSafetyOutcome:
    """Classify the composed Structural Route against Effective Gold."""
    if eligible_negative_count:
        return AttachmentStructuralSafetyOutcome.FALSIFIED
    if excluded_positive_count:
        return AttachmentStructuralSafetyOutcome.MIXED
    return AttachmentStructuralSafetyOutcome.SUPPORTED


def attachment_structural_safety_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.19 DTO."""
    payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
