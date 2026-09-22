"""Typed evidence for CEA-1.21 unequal-range blind review."""

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
from kotekomi_application.competitive_attachment_structural_route_safety import (
    AttachmentGoldAuthority,
)

_SHA256 = r"^[a-f0-9]{64}$"
type AttachmentBlindAnswer = Literal["Y", "N", "U"]


class AttachmentUnequalRangeRelation(StrEnum):
    """The exact interval relation between an unequal Candidate and Event."""

    CANDIDATE_CONTAINS_EVENT = "candidate_contains_event"
    EVENT_CONTAINS_CANDIDATE = "event_contains_candidate"
    PARTIAL_OVERLAP = "partial_overlap"
    DISJOINT = "disjoint"


class AttachmentBlindReviewOutcome(StrEnum):
    """The terminal CEA-1.21 comparison result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentBlindReviewCase(BaseModel):
    """One sealed unequal-range case with hidden evaluation authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ubr_[a-f0-9]{24}$")]
    phase: Literal["development", "validation"]
    matrix_id: Annotated[str, Field(pattern=r"^cam_[a-f0-9]{24}$")]
    source_text: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    candidate_range: AttachmentSourceRange
    event_range: AttachmentSourceRange
    relation: AttachmentUnequalRangeRelation
    foreign_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    structural_selected: bool
    original_gold: Literal["Y", "N"]
    reviewed_gold: Literal["Y", "N"] | None
    effective_gold: Literal["Y", "N"]
    gold_authority: AttachmentGoldAuthority

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Blind review source digest drifted.")
        for value in (self.candidate_range, self.event_range):
            if self.source_text[value.start : value.end] != value.text:
                raise ValueError("Blind review range is not source-exact.")
        if (self.candidate_range.start, self.candidate_range.end) == (
            self.event_range.start,
            self.event_range.end,
        ):
            raise ValueError("Blind unequal-range review cannot contain an exact pair.")
        expected_relation = classify_attachment_unequal_range_relation(
            self.candidate_range,
            self.event_range,
        )
        if self.relation is not expected_relation:
            raise ValueError("Blind review range relation drifted.")
        if self.foreign_event_ids != tuple(dict.fromkeys(self.foreign_event_ids)):
            raise ValueError("Blind review Foreign Event IDs must be ordered and distinct.")
        if self.structural_selected != (not self.foreign_event_ids):
            raise ValueError("Blind review Structural Selection drifted.")
        expected_authority = (
            AttachmentGoldAuthority.REVIEWED
            if self.reviewed_gold is not None
            else AttachmentGoldAuthority.ORIGINAL
        )
        if self.gold_authority is not expected_authority:
            raise ValueError("Blind review Gold authority drifted.")
        if self.effective_gold != (self.reviewed_gold or self.original_gold):
            raise ValueError("Blind review Effective Gold drifted.")
        if self.id != attachment_blind_review_case_id(
            phase=self.phase,
            matrix_id=self.matrix_id,
            candidate_id=self.candidate_id,
            event_id=self.event_id,
        ):
            raise ValueError("Blind review case ID drifted.")
        return self


class AttachmentBlindReviewCatalog(BaseModel):
    """The complete sealed inventory for CEA-1.21."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_blind_review_catalog_v1"] = (
        "attachment_blind_review_catalog_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    cases: tuple[AttachmentBlindReviewCase, ...]
    case_count: Annotated[int, Field(ge=0)]
    selected_count: Annotated[int, Field(ge=0)]
    excluded_count: Annotated[int, Field(ge=0)]
    candidate_contains_event_count: Annotated[int, Field(ge=0)]
    event_contains_candidate_count: Annotated[int, Field(ge=0)]
    partial_overlap_count: Annotated[int, Field(ge=0)]
    disjoint_count: Annotated[int, Field(ge=0)]
    catalog_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_order = tuple(
            sorted(
                self.cases,
                key=lambda item: (
                    item.phase,
                    item.matrix_id,
                    item.candidate_range.start,
                    item.candidate_range.end,
                    item.event_range.start,
                    item.event_range.end,
                    item.event_id,
                ),
            )
        )
        if self.cases != expected_order:
            raise ValueError("Blind review cases must use canonical order.")
        observed = (
            self.case_count,
            self.selected_count,
            self.excluded_count,
            self.candidate_contains_event_count,
            self.event_contains_candidate_count,
            self.partial_overlap_count,
            self.disjoint_count,
        )
        expected = (
            len(self.cases),
            sum(item.structural_selected for item in self.cases),
            sum(not item.structural_selected for item in self.cases),
            sum(
                item.relation is AttachmentUnequalRangeRelation.CANDIDATE_CONTAINS_EVENT
                for item in self.cases
            ),
            sum(
                item.relation is AttachmentUnequalRangeRelation.EVENT_CONTAINS_CANDIDATE
                for item in self.cases
            ),
            sum(
                item.relation is AttachmentUnequalRangeRelation.PARTIAL_OVERLAP
                for item in self.cases
            ),
            sum(item.relation is AttachmentUnequalRangeRelation.DISJOINT for item in self.cases),
        )
        if observed != expected:
            raise ValueError("Blind review catalog counts drifted.")
        if self.catalog_fingerprint != attachment_blind_review_fingerprint(self):
            raise ValueError("Blind review catalog fingerprint drifted.")
        return self


class AttachmentBlindReviewDecision(BaseModel):
    """One bounded semantic judgment from the blind reviewer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: Annotated[str, Field(pattern=r"^ubr_[a-f0-9]{24}$")]
    answer: AttachmentBlindAnswer
    rationale: Annotated[str, Field(min_length=1, max_length=500)]


class AttachmentBlindReviewSubmission(BaseModel):
    """One complete blind-review response."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_blind_review_submission_v1"]
    reviewer: Annotated[str, Field(min_length=1)]
    decisions: tuple[AttachmentBlindReviewDecision, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        case_ids = tuple(item.case_id for item in self.decisions)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Blind review decisions must be distinct.")
        return self


class AttachmentBlindReviewEvaluation(BaseModel):
    """One revealed comparison of a blind judgment with the sealed policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case: AttachmentBlindReviewCase
    decision: AttachmentBlindReviewDecision
    structural_expected_answer: Literal["Y", "N"]
    structural_correct: bool
    original_gold_agrees: bool | None
    reviewed_gold_agrees: bool | None
    effective_gold_agrees: bool | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision.case_id != self.case.id:
            raise ValueError("Blind review evaluation references a foreign decision.")
        expected = "Y" if self.case.structural_selected else "N"
        if self.structural_expected_answer != expected:
            raise ValueError("Blind review structural answer drifted.")
        if self.structural_correct != (self.decision.answer == expected):
            raise ValueError("Blind review structural evaluation drifted.")
        original_agrees = (
            None if self.decision.answer == "U" else self.decision.answer == self.case.original_gold
        )
        reviewed_agrees = (
            None
            if self.decision.answer == "U" or self.case.reviewed_gold is None
            else self.decision.answer == self.case.reviewed_gold
        )
        effective_agrees = (
            None
            if self.decision.answer == "U"
            else self.decision.answer == self.case.effective_gold
        )
        if (
            self.original_gold_agrees,
            self.reviewed_gold_agrees,
            self.effective_gold_agrees,
        ) != (original_agrees, reviewed_agrees, effective_agrees):
            raise ValueError("Blind review Gold agreement drifted.")
        return self


class AttachmentBlindReviewReport(BaseModel):
    """The terminal CEA-1.21 blind policy comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inputs: tuple[AttachmentEvidenceReference, ...]
    catalog_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    response_sha256: Annotated[str, Field(pattern=_SHA256)]
    reviewer: Annotated[str, Field(min_length=1)]
    evaluations: tuple[AttachmentBlindReviewEvaluation, ...]
    outcome: AttachmentBlindReviewOutcome
    case_count: Annotated[int, Field(ge=0)]
    selected_yes_count: Annotated[int, Field(ge=0)]
    selected_no_count: Annotated[int, Field(ge=0)]
    selected_unclear_count: Annotated[int, Field(ge=0)]
    excluded_yes_count: Annotated[int, Field(ge=0)]
    excluded_no_count: Annotated[int, Field(ge=0)]
    excluded_unclear_count: Annotated[int, Field(ge=0)]
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        selected = tuple(item for item in self.evaluations if item.case.structural_selected)
        excluded = tuple(item for item in self.evaluations if not item.case.structural_selected)
        observed = (
            self.case_count,
            self.selected_yes_count,
            self.selected_no_count,
            self.selected_unclear_count,
            self.excluded_yes_count,
            self.excluded_no_count,
            self.excluded_unclear_count,
        )
        expected = (
            len(self.evaluations),
            sum(item.decision.answer == "Y" for item in selected),
            sum(item.decision.answer == "N" for item in selected),
            sum(item.decision.answer == "U" for item in selected),
            sum(item.decision.answer == "Y" for item in excluded),
            sum(item.decision.answer == "N" for item in excluded),
            sum(item.decision.answer == "U" for item in excluded),
        )
        if observed != expected:
            raise ValueError("Blind review report counts drifted.")
        expected_outcome = classify_attachment_blind_review_outcome(
            selected_no_count=self.selected_no_count,
            selected_unclear_count=self.selected_unclear_count,
            excluded_yes_count=self.excluded_yes_count,
            excluded_unclear_count=self.excluded_unclear_count,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Blind review outcome drifted.")
        if self.result_fingerprint != attachment_blind_review_fingerprint(self):
            raise ValueError("Blind review report fingerprint drifted.")
        return self


def classify_attachment_unequal_range_relation(
    candidate: AttachmentSourceRange,
    event: AttachmentSourceRange,
) -> AttachmentUnequalRangeRelation:
    """Classify one unequal pair using half-open source intervals."""
    if (candidate.start, candidate.end) == (event.start, event.end):
        raise ValueError("Unequal-range classification cannot accept equal ranges.")
    if candidate.start <= event.start and candidate.end >= event.end:
        return AttachmentUnequalRangeRelation.CANDIDATE_CONTAINS_EVENT
    if event.start <= candidate.start and event.end >= candidate.end:
        return AttachmentUnequalRangeRelation.EVENT_CONTAINS_CANDIDATE
    if candidate.start < event.end and event.start < candidate.end:
        return AttachmentUnequalRangeRelation.PARTIAL_OVERLAP
    return AttachmentUnequalRangeRelation.DISJOINT


def classify_attachment_blind_review_outcome(
    *,
    selected_no_count: int,
    selected_unclear_count: int,
    excluded_yes_count: int,
    excluded_unclear_count: int,
) -> AttachmentBlindReviewOutcome:
    """Classify the revealed Structural Selection comparison."""
    if selected_no_count:
        return AttachmentBlindReviewOutcome.FALSIFIED
    if selected_unclear_count or excluded_unclear_count:
        return AttachmentBlindReviewOutcome.INCONCLUSIVE
    if excluded_yes_count:
        return AttachmentBlindReviewOutcome.MIXED
    return AttachmentBlindReviewOutcome.SUPPORTED


def attachment_blind_review_case_id(
    *,
    phase: str,
    matrix_id: str,
    candidate_id: str,
    event_id: str,
) -> str:
    """Return one stable opaque CEA-1.21 case ID."""
    digest = hashlib.sha256(
        "\x1f".join((phase, matrix_id, candidate_id, event_id)).encode()
    ).hexdigest()
    return "ubr_" + digest[:24]


def attachment_blind_review_fingerprint(value: BaseModel) -> str:
    """Return a canonical fingerprint for one CEA-1.21 DTO."""
    payload = value.model_dump(
        mode="json",
        exclude={"catalog_fingerprint", "result_fingerprint"},
    )
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
