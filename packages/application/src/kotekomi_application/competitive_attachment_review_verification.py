"""Derived contracts for model-free verification of CEA review claims."""

from __future__ import annotations

import base64
import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
)
from kotekomi_application.event_entity_connections import (
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
)
from kotekomi_application.event_entity_predicate_arguments import (
    PredicateArgumentGapCode,
    PredicateArgumentHypothesis,
    PredicateArgumentPathDirection,
    PredicateArgumentPathStep,
    PredicateArgumentToken,
    classify_predicate_argument_path,
    predicate_argument_is_structurally_supported,
)

_SHA256 = r"^[a-f0-9]{64}$"
type _EventId = Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
type _CandidateId = Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]


class AttachmentRangeRelation(StrEnum):
    """Set relation between meaningful Candidate and Gold characters."""

    CANDIDATE_WITHIN_GOLD = "candidate_within_gold"
    GOLD_WITHIN_CANDIDATE = "gold_within_candidate"
    PARTIAL_OVERLAP = "partial_overlap"
    DISJOINT = "disjoint"


class ReviewClaimVerdict(StrEnum):
    """Terminal interpretation of one review claim."""

    CONFIRMED = "confirmed"
    PARTLY_CONFIRMED = "partly_confirmed"
    FALSIFIED = "falsified"
    NOT_TESTABLE = "not_testable"


class AttachmentReviewClaimId(StrEnum):
    """Selected second-opinion claims tested by CEA-1.2."""

    SEGMENTATION_DEPENDENT_GOLD = "segmentation_dependent_gold"
    TRIGGER_CONTAINMENT_CATCHES_MOST = "trigger_containment_catches_most"
    SYNTAX_RECOVERS_GOVERNING_CASES = "syntax_recovers_governing_cases"
    SYNTAX_CAN_REPLACE_QWEN = "syntax_can_replace_qwen"
    REPEATED_OCCURRENCES_ROUTE_DETERMINISTICALLY = "repeated_occurrences_route_deterministically"
    UNORDERED_FAILURES_ARE_FORMAT_ONLY = "unordered_failures_are_format_only"
    EXAMPLE_CARDINALITY_CONFOUND = "example_cardinality_confound"
    STATISTICAL_SIGNIFICANCE = "statistical_significance"
    GENERALIZATION = "generalization"
    TRUE_MODEL_ERROR_IS_LOWER = "true_model_error_is_lower"
    SYNTAX_THRESHOLD_IS_VALIDATED = "syntax_threshold_is_validated"


class AttachmentSourceRange(BaseModel):
    """One source-exact half-open range in a diagnostic record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Attachment source range does not match its text length.")
        return self


class AttachmentRangeObservation(BaseModel):
    """One Candidate-to-Event Gold range relation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_id: _CandidateId
    source_grounded_event_id: _EventId
    candidate_range: AttachmentSourceRange
    gold_ranges: tuple[AttachmentSourceRange, ...]
    relation: AttachmentRangeRelation

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.gold_ranges:
            raise ValueError("Attachment range observation requires Gold ranges.")
        if tuple(sorted(self.gold_ranges, key=lambda item: (item.start, item.end))) != (
            self.gold_ranges
        ):
            raise ValueError("Attachment Gold ranges must use source order.")
        return self


class AttachmentNestedCandidateFlip(BaseModel):
    """One nested Candidate pair whose Gold Attachment Set changes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    inner_candidate_id: _CandidateId
    inner_range: AttachmentSourceRange
    inner_gold_event_ids: tuple[_EventId, ...]
    outer_candidate_id: _CandidateId
    outer_range: AttachmentSourceRange
    outer_gold_event_ids: tuple[_EventId, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Nested Candidate source digest drifted.")
        if not (
            self.outer_range.start <= self.inner_range.start
            and self.inner_range.end <= self.outer_range.end
            and (
                self.outer_range.start < self.inner_range.start
                or self.inner_range.end < self.outer_range.end
            )
        ):
            raise ValueError("Nested Candidate ranges do not form a strict containment pair.")
        for item in (self.inner_range, self.outer_range):
            if self.source_text[item.start : item.end] != item.text:
                raise ValueError("Nested Candidate range is not source-exact.")
        if self.inner_gold_event_ids == self.outer_gold_event_ids:
            raise ValueError("A Segmentation Flip requires different Gold Attachment Sets.")
        _ordered_distinct("inner Gold Event IDs", self.inner_gold_event_ids)
        _ordered_distinct("outer Gold Event IDs", self.outer_gold_event_ids)
        return self


class AttachmentSyntaxObservation(BaseModel):
    """One source-exact structural observation for a Candidate and Event occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_syntax_observation_v1"] = "attachment_syntax_observation_v1"
    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    linguistic_trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]
    linguistic_resource_identity: Annotated[str, Field(pattern=_SHA256)]
    candidate_id: _CandidateId
    source_grounded_event_id: _EventId
    candidate_range: AttachmentSourceRange
    event_range: AttachmentSourceRange
    event_head_range: AttachmentSourceRange
    event_anchor: PredicateArgumentToken | None
    candidate_anchor: PredicateArgumentToken | None
    path_tokens: tuple[PredicateArgumentToken, ...]
    path_steps: tuple[PredicateArgumentPathStep, ...]
    hypothesis: PredicateArgumentHypothesis
    gap_code: PredicateArgumentGapCode | None
    own_event_expression: bool
    structurally_supported: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        is_gap = self.hypothesis is PredicateArgumentHypothesis.DIAGNOSTIC_GAP
        if is_gap != (self.gap_code is not None):
            raise ValueError("Attachment syntax gap requires one gap code.")
        if is_gap:
            if self.path_tokens or self.path_steps:
                raise ValueError("Attachment syntax gap cannot contain a dependency path.")
        elif self.hypothesis is PredicateArgumentHypothesis.DIFFERENT_SENTENCE:
            if self.event_anchor is None or self.candidate_anchor is None:
                raise ValueError("Different-sentence syntax requires both anchors.")
            if self.path_tokens or self.path_steps:
                raise ValueError("Different-sentence syntax cannot contain a dependency path.")
        else:
            if self.event_anchor is None or self.candidate_anchor is None:
                raise ValueError("Attachment syntax path requires both anchors.")
            if not self.path_tokens:
                raise ValueError("Attachment syntax observation requires path tokens.")
            if self.path_tokens[0] != self.event_anchor:
                raise ValueError("Attachment syntax path must start at the Event anchor.")
            if self.path_tokens[-1] != self.candidate_anchor:
                raise ValueError("Attachment syntax path must end at the Candidate anchor.")
            if len(self.path_steps) != len(self.path_tokens) - 1:
                raise ValueError("Attachment syntax path edge count drifted.")
        expected_supported = self.own_event_expression or (
            not is_gap
            and self.hypothesis is not PredicateArgumentHypothesis.DIFFERENT_SENTENCE
            and predicate_argument_is_structurally_supported(self.hypothesis)
        )
        if self.structurally_supported != expected_supported:
            raise ValueError("Attachment syntax support status drifted from its path.")
        return self


class AttachmentCandidateEvaluation(BaseModel):
    """One occurrence-level Gold and syntax-derived Attachment Set comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    candidate_id: _CandidateId
    candidate_range: AttachmentSourceRange
    gold_event_ids: tuple[_EventId, ...]
    syntax_event_ids: tuple[_EventId, ...]
    exact: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("Candidate Gold Event IDs", self.gold_event_ids)
        _ordered_distinct("Candidate syntax Event IDs", self.syntax_event_ids)
        if self.exact != (self.gold_event_ids == self.syntax_event_ids):
            raise ValueError("Candidate syntax exact status drifted.")
        return self


class AttachmentMetricSnapshot(BaseModel):
    """Comparable occurrence and proposition metrics for one attachment path."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_count: Annotated[int, Field(ge=0)]
    event_count: Annotated[int, Field(ge=0)]
    exact_set_count: Annotated[int, Field(ge=0)]
    exact_set_accuracy: Annotated[float, Field(ge=0, le=1)]
    true_positive_edge_count: Annotated[int, Field(ge=0)]
    false_positive_edge_count: Annotated[int, Field(ge=0)]
    false_negative_edge_count: Annotated[int, Field(ge=0)]
    edge_precision: Annotated[float, Field(ge=0, le=1)]
    edge_recall: Annotated[float, Field(ge=0, le=1)]
    edge_f1: Annotated[float, Field(ge=0, le=1)]
    sibling_event_leakage_count: Annotated[int, Field(ge=0)]
    shared_gold_edge_count: Annotated[int, Field(ge=0)]
    shared_matched_edge_count: Annotated[int, Field(ge=0)]
    shared_fragment_recall: Annotated[float, Field(ge=0, le=1)]
    none_case_count: Annotated[int, Field(ge=0)]
    none_correct_count: Annotated[int, Field(ge=0)]
    none_accuracy: Annotated[float, Field(ge=0, le=1)]
    exact_event_count: Annotated[int, Field(ge=0)]
    character_precision: Annotated[float, Field(ge=0, le=1)]
    character_recall: Annotated[float, Field(ge=0, le=1)]
    character_f1: Annotated[float, Field(ge=0, le=1)]
    entity_gold_edge_count: Annotated[int, Field(ge=0)]
    entity_matched_edge_count: Annotated[int, Field(ge=0)]
    entity_recall: Annotated[float, Field(ge=0, le=1)]
    qualification_gold_edge_count: Annotated[int, Field(ge=0)]
    qualification_matched_edge_count: Annotated[int, Field(ge=0)]
    qualification_recall: Annotated[float, Field(ge=0, le=1)]
    anchor_gap_count: Annotated[int, Field(ge=0)]


class AttachmentSyntaxPhaseResult(BaseModel):
    """Complete model-free syntax result for one frozen phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    observations: tuple[AttachmentSyntaxObservation, ...]
    candidates: tuple[AttachmentCandidateEvaluation, ...]
    syntax_metrics: AttachmentMetricSnapshot
    archived_qwen_metrics: AttachmentMetricSnapshot

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(sorted(self.candidates, key=lambda item: item.candidate_id)) != self.candidates:
            raise ValueError("Attachment syntax candidates must use canonical order.")
        if any(item.phase != self.phase for item in (*self.observations, *self.candidates)):
            raise ValueError("Attachment syntax phase contains foreign evidence.")
        return self


class AttachmentTriggerContainmentObservation(BaseModel):
    """One Candidate that strictly contains one or more Event expressions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    candidate_id: _CandidateId
    candidate_range: AttachmentSourceRange
    contained_event_ids: tuple[_EventId, ...]
    contained_event_ranges: tuple[AttachmentSourceRange, ...]
    split_ranges: tuple[AttachmentSourceRange, ...]
    gold_event_ids: tuple[_EventId, ...]
    validation_false_none: bool
    challenge_none: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Trigger-containment source digest drifted.")
        if not self.contained_event_ids:
            raise ValueError("Trigger containment requires one contained Event.")
        if len(self.contained_event_ids) != len(self.contained_event_ranges):
            raise ValueError("Contained Event IDs and ranges must align.")
        if len(set(self.contained_event_ids)) != len(self.contained_event_ids):
            raise ValueError("Contained Event IDs must be distinct.")
        _ordered_distinct("trigger-containment Gold Event IDs", self.gold_event_ids)
        for item in (
            self.candidate_range,
            *self.contained_event_ranges,
            *self.split_ranges,
        ):
            if self.source_text[item.start : item.end] != item.text:
                raise ValueError("Trigger-containment range is not source-exact.")
        return self


class AttachmentTriggerContainmentSummary(BaseModel):
    """Coverage of deterministic trigger containment across declared populations."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    all_candidate_count: Annotated[int, Field(ge=0)]
    trigger_containing_candidate_count: Annotated[int, Field(ge=0)]
    gold_none_candidate_count: Annotated[int, Field(ge=0)]
    trigger_containing_gold_none_count: Annotated[int, Field(ge=0)]
    validation_false_none_count: Literal[13]
    trigger_containing_validation_false_none_count: Annotated[int, Field(ge=0, le=13)]
    challenge_none_count: Literal[4]
    trigger_containing_challenge_none_count: Annotated[int, Field(ge=0, le=4)]
    observations: tuple[AttachmentTriggerContainmentObservation, ...]


class AttachmentRepeatedOccurrenceResult(BaseModel):
    """One CEA-1.1 repeated-text case routed by exact occurrence syntax."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    source_segment_id: Annotated[str, Field(min_length=1)]
    candidate_range: AttachmentSourceRange
    linguistic_token_ids: tuple[Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")], ...]
    gold_event_ids: tuple[_EventId, ...]
    syntax_event_ids: tuple[_EventId, ...]
    exact: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.linguistic_token_ids:
            raise ValueError("Repeated occurrence requires linguistic token identities.")
        _ordered_distinct("repeated occurrence Gold Event IDs", self.gold_event_ids)
        _ordered_distinct("repeated occurrence syntax Event IDs", self.syntax_event_ids)
        if self.exact != (self.gold_event_ids == self.syntax_event_ids):
            raise ValueError("Repeated occurrence exact status drifted.")
        return self


class AttachmentUnorderedCounterfactual(BaseModel):
    """One archived invalid output parsed as an unordered label set."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    condition: Annotated[str, Field(min_length=1)]
    candidate_id: _CandidateId
    raw_output_base64: str
    raw_output_sha256: Annotated[str, Field(pattern=_SHA256)]
    emitted_labels: tuple[Annotated[str, Field(pattern=r"^E[1-9][0-9]*$")], ...]
    canonical_labels: tuple[Annotated[str, Field(pattern=r"^E[1-9][0-9]*$")], ...]
    predicted_event_ids: tuple[_EventId, ...]
    gold_event_ids: tuple[_EventId, ...]
    semantically_exact: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        raw = base64.b64decode(self.raw_output_base64, validate=True)
        if hashlib.sha256(raw).hexdigest() != self.raw_output_sha256:
            raise ValueError("Unordered counterfactual output digest drifted.")
        _ordered_distinct("counterfactual canonical labels", self.canonical_labels)
        _ordered_distinct("counterfactual predicted Event IDs", self.predicted_event_ids)
        _ordered_distinct("counterfactual Gold Event IDs", self.gold_event_ids)
        if set(self.emitted_labels) != set(self.canonical_labels):
            raise ValueError("Counterfactual label canonicalization changed its set.")
        if self.semantically_exact != (self.predicted_event_ids == self.gold_event_ids):
            raise ValueError("Counterfactual semantic result drifted.")
        return self


class AttachmentPromptCardinalityObservation(BaseModel):
    """Maximum nonempty answer cardinality demonstrated by one Prompt Arm."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt_arm: Annotated[str, Field(min_length=1)]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    answer_cardinalities: tuple[Annotated[int, Field(ge=0)], ...]
    maximum_answer_cardinality: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.answer_cardinalities:
            raise ValueError("Prompt cardinality requires at least one example answer.")
        if self.maximum_answer_cardinality != max(self.answer_cardinalities):
            raise ValueError("Prompt maximum answer cardinality drifted.")
        return self


class AttachmentSegmentCount(BaseModel):
    """Candidate count for one SourceSegment in the CEA-1.1 catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_segment_id: Annotated[str, Field(min_length=1)]
    candidate_count: Annotated[int, Field(ge=1)]


class AttachmentCatalogConcentration(BaseModel):
    """SourceSegment concentration in the 24-case discrimination catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_count: Literal[24]
    source_segment_count: Annotated[int, Field(ge=1)]
    maximum_segment_candidate_count: Annotated[int, Field(ge=1, le=24)]
    segments: tuple[AttachmentSegmentCount, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(sorted(self.segments, key=lambda item: item.source_segment_id)) != self.segments:
            raise ValueError("Catalog SourceSegments must use canonical order.")
        if self.source_segment_count != len(self.segments):
            raise ValueError("Catalog SourceSegment count drifted.")
        if sum(item.candidate_count for item in self.segments) != self.candidate_count:
            raise ValueError("Catalog Candidate count drifted.")
        if self.maximum_segment_candidate_count != max(
            item.candidate_count for item in self.segments
        ):
            raise ValueError("Catalog maximum SourceSegment count drifted.")
        return self


class AttachmentReviewClaimResult(BaseModel):
    """One evidence-backed verdict for one selected second-opinion claim."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    claim_id: AttachmentReviewClaimId
    statement: Annotated[str, Field(min_length=1)]
    verdict: ReviewClaimVerdict
    observed_count: Annotated[int, Field(ge=0)]
    population_count: Annotated[int, Field(ge=0)]
    evidence_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.observed_count > self.population_count:
            raise ValueError("Review claim observed count exceeds its population.")
        _ordered_distinct("review claim evidence IDs", self.evidence_ids)
        return self


class AttachmentEvidenceReference(BaseModel):
    """One path and digest bound into the diagnostic evidence chain."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    label: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern=_SHA256)]


class AttachmentReviewVerificationReport(BaseModel):
    """Complete model-free verification of selected CEA review claims."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_review_verification_report_v1"] = (
        "attachment_review_verification_report_v1"
    )
    policy_id: Literal["competitive_attachment_review_verification_v1"] = (
        "competitive_attachment_review_verification_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    range_observations: tuple[AttachmentRangeObservation, ...]
    segmentation_flips: tuple[AttachmentNestedCandidateFlip, ...]
    trigger_containment: AttachmentTriggerContainmentSummary
    development: AttachmentSyntaxPhaseResult
    validation: AttachmentSyntaxPhaseResult
    repeated_occurrences: tuple[AttachmentRepeatedOccurrenceResult, ...]
    unordered_counterfactuals: tuple[AttachmentUnorderedCounterfactual, ...]
    prompt_cardinalities: tuple[AttachmentPromptCardinalityObservation, ...]
    catalog_concentration: AttachmentCatalogConcentration
    claims: tuple[AttachmentReviewClaimResult, ...]
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("evidence labels", tuple(item.label for item in self.inputs))
        if tuple(sorted(self.claims, key=lambda item: item.claim_id.value)) != self.claims:
            raise ValueError("Review claims must use canonical order.")
        if len(self.repeated_occurrences) != 3:
            raise ValueError("CEA-1.2 requires three repeated-occurrence cases.")
        if len(self.unordered_counterfactuals) != 3:
            raise ValueError("CEA-1.2 requires three archived invalid-output cases.")
        expected = attachment_review_verification_fingerprint(self)
        if self.result_fingerprint != expected:
            raise ValueError("Review-verification result fingerprint drifted.")
        return self


class AttachmentReviewVerificationManifest(BaseModel):
    """Digest chain for one terminal CEA-1.2 evidence package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_review_verification_manifest_v1"] = (
        "attachment_review_verification_manifest_v1"
    )
    policy_id: Literal["competitive_attachment_review_verification_v1"] = (
        "competitive_attachment_review_verification_v1"
    )
    tdd: AttachmentEvidenceReference
    inputs: tuple[AttachmentEvidenceReference, ...]
    outputs: tuple[AttachmentEvidenceReference, ...]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("manifest input labels", tuple(item.label for item in self.inputs))
        _ordered_distinct("manifest output labels", tuple(item.label for item in self.outputs))
        return self


class AttachmentReviewVerificationStatus(BaseModel):
    """Terminal, machine-readable status for one CEA-1.2 run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_review_verification_status_v1"] = (
        "attachment_review_verification_status_v1"
    )
    status: Literal["complete"] = "complete"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    report_path: Annotated[str, Field(min_length=1)]
    review_path: Annotated[str, Field(min_length=1)]
    summary_path: Annotated[str, Field(min_length=1)]
    second_opinion_summary_path: Annotated[str, Field(min_length=1)]


def classify_attachment_range_relation(
    *,
    source_text: str,
    candidate_start: int,
    candidate_end: int,
    gold_ranges: tuple[tuple[int, int], ...],
) -> AttachmentRangeRelation:
    """Classify one Candidate range against one Event's meaningful Gold characters."""
    candidate = _meaningful_positions(source_text, ((candidate_start, candidate_end),))
    gold = _meaningful_positions(source_text, gold_ranges)
    if not candidate or not gold:
        raise ValueError("Attachment range relation requires meaningful source characters.")
    if candidate <= gold:
        return AttachmentRangeRelation.CANDIDATE_WITHIN_GOLD
    if gold <= candidate:
        return AttachmentRangeRelation.GOLD_WITHIN_CANDIDATE
    if candidate & gold:
        return AttachmentRangeRelation.PARTIAL_OVERLAP
    return AttachmentRangeRelation.DISJOINT


def build_attachment_syntax_observation(
    *,
    phase: Literal["development", "validation"],
    source_text: str,
    candidate: CompetitiveAttachmentCandidate,
    event: CompetitiveAttachmentEventOption,
    event_head_start: int,
    event_head_end: int,
    event_head_text: str,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> AttachmentSyntaxObservation:
    """Build one exact Candidate-to-Event dependency-path observation."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if (
        candidate.source_segment_id != event.source_segment_id
        or candidate.source_segment_id != linguistic_evidence.source_segment_id
        or candidate.source_text_sha256 != source_digest
        or event.source_text_sha256 != source_digest
        or linguistic_evidence.source_text_sha256 != source_digest
    ):
        raise ValueError("Attachment syntax inputs do not share authoritative source evidence.")
    exact_ranges = (
        (candidate.start, candidate.end, candidate.text),
        (event.start, event.end, event.text),
        (event_head_start, event_head_end, event_head_text),
        *tuple((item.start, item.end, item.text) for item in linguistic_evidence.tokens),
    )
    if any(
        end > len(source_text) or source_text[start:end] != text
        for start, end, text in exact_ranges
    ):
        raise ValueError("Attachment syntax input is not source-exact.")
    token_by_id = {item.token_id: item for item in linguistic_evidence.tokens}
    event_matches = tuple(
        item
        for item in linguistic_evidence.tokens
        if (item.start, item.end) == (event_head_start, event_head_end)
    )
    event_anchor = event_matches[0] if len(event_matches) == 1 else None
    unknown_candidate_token_ids = tuple(
        token_id for token_id in candidate.linguistic_token_ids if token_id not in token_by_id
    )
    if unknown_candidate_token_ids:
        raise ValueError("Attachment Candidate references unknown linguistic tokens.")
    candidate_tokens = tuple(token_by_id[token_id] for token_id in candidate.linguistic_token_ids)
    candidate_token_ids = {item.token_id for item in candidate_tokens}
    candidate_heads = tuple(
        item
        for item in candidate_tokens
        if item.part_of_speech.casefold() != "punct"
        and item.head_token_id not in candidate_token_ids
    )
    candidate_anchor = candidate_heads[0] if len(candidate_heads) == 1 else None
    gap_code = _attachment_anchor_gap(event_matches, candidate_tokens, candidate_heads)
    own_event_expression = (candidate.start, candidate.end) == (event.start, event.end)
    if gap_code is not None:
        return _syntax_observation(
            phase=phase,
            candidate=candidate,
            event=event,
            event_head_start=event_head_start,
            event_head_end=event_head_end,
            event_head_text=event_head_text,
            linguistic_evidence=linguistic_evidence,
            event_anchor=event_anchor,
            candidate_anchor=candidate_anchor,
            path_tokens=(),
            path_steps=(),
            hypothesis=PredicateArgumentHypothesis.DIAGNOSTIC_GAP,
            gap_code=gap_code,
            own_event_expression=own_event_expression,
        )
    assert event_anchor is not None
    assert candidate_anchor is not None
    if event_anchor.sentence_id != candidate_anchor.sentence_id:
        return _syntax_observation(
            phase=phase,
            candidate=candidate,
            event=event,
            event_head_start=event_head_start,
            event_head_end=event_head_end,
            event_head_text=event_head_text,
            linguistic_evidence=linguistic_evidence,
            event_anchor=event_anchor,
            candidate_anchor=candidate_anchor,
            path_tokens=(),
            path_steps=(),
            hypothesis=PredicateArgumentHypothesis.DIFFERENT_SENTENCE,
            gap_code=None,
            own_event_expression=own_event_expression,
        )
    path_ids, path_gap = _dependency_path_ids(
        event_anchor.token_id,
        candidate_anchor.token_id,
        token_by_id,
    )
    if path_gap is not None:
        return _syntax_observation(
            phase=phase,
            candidate=candidate,
            event=event,
            event_head_start=event_head_start,
            event_head_end=event_head_end,
            event_head_text=event_head_text,
            linguistic_evidence=linguistic_evidence,
            event_anchor=event_anchor,
            candidate_anchor=candidate_anchor,
            path_tokens=(),
            path_steps=(),
            hypothesis=PredicateArgumentHypothesis.DIAGNOSTIC_GAP,
            gap_code=path_gap,
            own_event_expression=own_event_expression,
        )
    path_tokens = tuple(_predicate_token(token_by_id[item]) for item in path_ids)
    path_steps = _path_steps(path_ids, token_by_id)
    return _syntax_observation(
        phase=phase,
        candidate=candidate,
        event=event,
        event_head_start=event_head_start,
        event_head_end=event_head_end,
        event_head_text=event_head_text,
        linguistic_evidence=linguistic_evidence,
        event_anchor=event_anchor,
        candidate_anchor=candidate_anchor,
        path_tokens=path_tokens,
        path_steps=path_steps,
        hypothesis=classify_predicate_argument_path(path_steps),
        gap_code=None,
        own_event_expression=own_event_expression,
    )


def parse_unordered_attachment_labels(
    raw_output: bytes,
    *,
    allowed_event_labels: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Parse distinct known labels as a set while retaining their emitted order."""
    try:
        payload = raw_output.decode("utf-8").strip(" \t\r\n")
    except UnicodeDecodeError as error:
        raise ValueError("Counterfactual attachment output must be UTF-8 text.") from error
    labels = tuple(payload.split(","))
    if not labels or any(not item.startswith("E") or not item[1:].isdigit() for item in labels):
        raise ValueError("Counterfactual attachment output is not a label set.")
    if len(set(labels)) != len(labels):
        raise ValueError("Counterfactual attachment output repeats a label.")
    positions = {label: index for index, label in enumerate(allowed_event_labels)}
    if any(label not in positions for label in labels):
        raise ValueError("Counterfactual attachment output contains an unknown label.")
    return labels, tuple(sorted(labels, key=positions.__getitem__))


def attachment_review_verification_fingerprint(
    report: AttachmentReviewVerificationReport,
) -> str:
    """Return the semantic fingerprint for one complete verification report."""
    payload = report.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _syntax_observation(
    *,
    phase: Literal["development", "validation"],
    candidate: CompetitiveAttachmentCandidate,
    event: CompetitiveAttachmentEventOption,
    event_head_start: int,
    event_head_end: int,
    event_head_text: str,
    linguistic_evidence: EventEntityLinguisticEvidence,
    event_anchor: EventEntityLinguisticToken | None,
    candidate_anchor: EventEntityLinguisticToken | None,
    path_tokens: tuple[PredicateArgumentToken, ...],
    path_steps: tuple[PredicateArgumentPathStep, ...],
    hypothesis: PredicateArgumentHypothesis,
    gap_code: PredicateArgumentGapCode | None,
    own_event_expression: bool,
) -> AttachmentSyntaxObservation:
    supported = own_event_expression or (
        hypothesis
        not in {
            PredicateArgumentHypothesis.DIAGNOSTIC_GAP,
            PredicateArgumentHypothesis.DIFFERENT_SENTENCE,
        }
        and predicate_argument_is_structurally_supported(hypothesis)
    )
    return AttachmentSyntaxObservation(
        phase=phase,
        source_segment_id=candidate.source_segment_id,
        source_text_sha256=candidate.source_text_sha256,
        linguistic_trace_id=linguistic_evidence.trace_id,
        linguistic_resource_identity=linguistic_evidence.resource_identity,
        candidate_id=candidate.id,
        source_grounded_event_id=event.source_grounded_event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate.start,
            end=candidate.end,
            text=candidate.text,
        ),
        event_range=AttachmentSourceRange(start=event.start, end=event.end, text=event.text),
        event_head_range=AttachmentSourceRange(
            start=event_head_start,
            end=event_head_end,
            text=event_head_text,
        ),
        event_anchor=None if event_anchor is None else _predicate_token(event_anchor),
        candidate_anchor=(None if candidate_anchor is None else _predicate_token(candidate_anchor)),
        path_tokens=path_tokens,
        path_steps=path_steps,
        hypothesis=hypothesis,
        gap_code=gap_code,
        own_event_expression=own_event_expression,
        structurally_supported=supported,
    )


def _attachment_anchor_gap(
    event_matches: tuple[EventEntityLinguisticToken, ...],
    candidate_tokens: tuple[EventEntityLinguisticToken, ...],
    candidate_heads: tuple[EventEntityLinguisticToken, ...],
) -> PredicateArgumentGapCode | None:
    if not event_matches:
        return PredicateArgumentGapCode.PREDICATE_ANCHOR_MISSING
    if len(event_matches) > 1:
        return PredicateArgumentGapCode.PREDICATE_ANCHOR_AMBIGUOUS
    if not candidate_tokens or not candidate_heads:
        return PredicateArgumentGapCode.ENTITY_ANCHOR_MISSING
    if len(candidate_heads) > 1:
        return PredicateArgumentGapCode.ENTITY_ANCHOR_AMBIGUOUS
    return None


def _dependency_path_ids(
    event_id: str,
    candidate_id: str,
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> tuple[tuple[str, ...], PredicateArgumentGapCode | None]:
    event_chain, event_invalid = _ancestor_chain(event_id, token_by_id)
    candidate_chain, candidate_invalid = _ancestor_chain(candidate_id, token_by_id)
    if event_invalid or candidate_invalid:
        return (), PredicateArgumentGapCode.INVALID_DEPENDENCY_TREE
    candidate_positions = {token_id: index for index, token_id in enumerate(candidate_chain)}
    common = next((token_id for token_id in event_chain if token_id in candidate_positions), None)
    if common is None:
        return (), PredicateArgumentGapCode.DISCONNECTED_DEPENDENCY_TREE
    event_end = event_chain.index(common)
    candidate_end = candidate_positions[common]
    return (
        *event_chain[: event_end + 1],
        *reversed(candidate_chain[:candidate_end]),
    ), None


def _ancestor_chain(
    token_id: str,
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> tuple[tuple[str, ...], bool]:
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = token_id
    while current is not None:
        if current in seen or current not in token_by_id:
            return tuple(chain), True
        seen.add(current)
        chain.append(current)
        current = token_by_id[current].head_token_id
    return tuple(chain), False


def _path_steps(
    path_ids: tuple[str, ...],
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> tuple[PredicateArgumentPathStep, ...]:
    steps: list[PredicateArgumentPathStep] = []
    for left_id, right_id in zip(path_ids, path_ids[1:], strict=False):
        left = token_by_id[left_id]
        right = token_by_id[right_id]
        if left.head_token_id == right_id:
            direction = PredicateArgumentPathDirection.TOWARD_HEAD
            relation = left.dependency_relation
        elif right.head_token_id == left_id:
            direction = PredicateArgumentPathDirection.TOWARD_DEPENDENT
            relation = right.dependency_relation
        else:
            raise ValueError("Attachment syntax path contains a non-edge.")
        steps.append(
            PredicateArgumentPathStep(
                from_token_id=left_id,
                to_token_id=right_id,
                direction=direction,
                dependency_relation=relation,
            )
        )
    return tuple(steps)


def _predicate_token(value: EventEntityLinguisticToken) -> PredicateArgumentToken:
    return PredicateArgumentToken.model_validate(value.model_dump(mode="json"))


def _meaningful_positions(
    source_text: str,
    ranges: tuple[tuple[int, int], ...],
) -> set[int]:
    return {
        position
        for start, end in ranges
        for position in range(start, end)
        if not source_text[position].isspace()
    }


def _ordered_distinct(label: str, values: tuple[object, ...]) -> None:
    if tuple(sorted(set(values), key=str)) != values:
        raise ValueError(f"Attachment {label} must be ordered and distinct.")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
