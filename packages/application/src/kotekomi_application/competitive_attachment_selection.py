"""Derived contracts for the CEA-1.3 bounded hybrid selection diagnostic."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentMetricSnapshot,
    AttachmentSourceRange,
    AttachmentSyntaxObservation,
)

_SHA256 = r"^[a-f0-9]{64}$"
type _CandidateId = Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
type _EventId = Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]


class AttachmentNormalizationOperation(StrEnum):
    """One deterministic boundary operation applied to a comparison range."""

    LEADING_WHITESPACE = "leading_whitespace"
    LEADING_DELIMITER = "leading_delimiter"
    TERMINAL_CITATION_MARKERS = "terminal_citation_markers"


class AttachmentComparisonGapCode(StrEnum):
    """Typed reason that a Candidate has no comparison characters."""

    EMPTY_AFTER_NORMALIZATION = "empty_after_normalization"


class AttachmentSelectionOutcome(StrEnum):
    """Terminal CEA-1.3 hypothesis result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class AttachmentOracleCeilingKind(StrEnum):
    """Gold-dependent non-deployable upper-bound policy."""

    CANDIDATE_SOURCE = "candidate_source"
    PER_EDGE = "per_edge"


class AttachmentComparisonRange(BaseModel):
    """Authoritative Candidate range plus its evaluation-only comparison range."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_comparison_range_v1"] = "attachment_comparison_range_v1"
    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_id: _CandidateId
    authoritative_range: AttachmentSourceRange
    comparison_start: Annotated[int, Field(ge=0)]
    comparison_end: Annotated[int, Field(ge=0)]
    comparison_text: str
    operations: tuple[AttachmentNormalizationOperation, ...]
    gap_code: AttachmentComparisonGapCode | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not (
            self.authoritative_range.start
            <= self.comparison_start
            <= self.comparison_end
            <= self.authoritative_range.end
        ):
            raise ValueError("Comparison range must remain inside its authoritative range.")
        if self.comparison_end - self.comparison_start != len(self.comparison_text):
            raise ValueError("Comparison range does not match its text length.")
        if len(set(self.operations)) != len(self.operations):
            raise ValueError("Comparison operations must be distinct.")
        expected_gap = (
            AttachmentComparisonGapCode.EMPTY_AFTER_NORMALIZATION
            if self.comparison_start == self.comparison_end
            else None
        )
        if self.gap_code != expected_gap:
            raise ValueError("Comparison gap status drifted from its range.")
        return self


class AttachmentNormalizationChange(BaseModel):
    """One Candidate whose Gold Attachment Set changes after normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    candidate_id: _CandidateId
    comparison: AttachmentComparisonRange
    original_gold_event_ids: tuple[_EventId, ...]
    normalized_gold_event_ids: tuple[_EventId, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Normalization-change source digest drifted.")
        authoritative = self.comparison.authoritative_range
        if self.source_text[authoritative.start : authoritative.end] != authoritative.text:
            raise ValueError("Normalization-change authoritative range is not source-exact.")
        if (
            self.source_text[self.comparison.comparison_start : self.comparison.comparison_end]
            != self.comparison.comparison_text
        ):
            raise ValueError("Normalization-change comparison range is not source-exact.")
        _ordered_distinct("original Gold Event IDs", self.original_gold_event_ids)
        _ordered_distinct("normalized Gold Event IDs", self.normalized_gold_event_ids)
        if self.original_gold_event_ids == self.normalized_gold_event_ids:
            raise ValueError("Normalization change requires different Attachment Sets.")
        return self


class AttachmentSyntaxPolicy(BaseModel):
    """One bounded deterministic syntax-selection policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    policy_id: Annotated[str, Field(pattern=r"^path_(?:[1-4]|unbounded)(?:_plus_complement)?$")]
    maximum_path_length: Annotated[int, Field(ge=1, le=4)] | None
    governed_complement_scope: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = attachment_syntax_policy_id(
            maximum_path_length=self.maximum_path_length,
            governed_complement_scope=self.governed_complement_scope,
        )
        if self.policy_id != expected:
            raise ValueError("Syntax policy ID drifted from its settings.")
        return self


class AttachmentRescueMetrics(BaseModel):
    """Gold coverage and precision of syntax edges absent from archived Qwen."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    qwen_false_negative_edge_count: Annotated[int, Field(ge=0)]
    added_syntax_edge_count: Annotated[int, Field(ge=0)]
    rescued_gold_edge_count: Annotated[int, Field(ge=0)]
    added_false_edge_count: Annotated[int, Field(ge=0)]
    rescue_precision: Annotated[float, Field(ge=0, le=1)]
    qwen_false_negative_coverage: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.rescued_gold_edge_count + self.added_false_edge_count != (
            self.added_syntax_edge_count
        ):
            raise ValueError("Rescue edge counts do not partition added syntax edges.")
        expected_precision = _ratio(
            self.rescued_gold_edge_count,
            self.added_syntax_edge_count,
        )
        expected_coverage = _ratio(
            self.rescued_gold_edge_count,
            self.qwen_false_negative_edge_count,
        )
        if self.rescue_precision != expected_precision:
            raise ValueError("Rescue precision drifted from its edge counts.")
        if self.qwen_false_negative_coverage != expected_coverage:
            raise ValueError("False-negative coverage drifted from its edge counts.")
        return self


class AttachmentPolicyPhaseResult(BaseModel):
    """One syntax and hybrid policy result for one frozen phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    policy: AttachmentSyntaxPolicy
    syntax_metrics: AttachmentMetricSnapshot
    union_metrics: AttachmentMetricSnapshot
    intersection_metrics: AttachmentMetricSnapshot
    rescue: AttachmentRescueMetrics


class AttachmentOracleCeiling(BaseModel):
    """One explicitly Gold-dependent and non-deployable upper bound."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    kind: AttachmentOracleCeilingKind
    policy_id: Annotated[str, Field(min_length=1)]
    metrics: AttachmentMetricSnapshot
    deployable: Literal[False] = False


class AttachmentSelectionPhaseResult(BaseModel):
    """Normalized baselines and all selection policies for one phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    candidate_count: Annotated[int, Field(ge=1)]
    prompt_v3_baseline_metrics: AttachmentMetricSnapshot
    competitive_qwen_metrics: AttachmentMetricSnapshot
    policies: tuple[AttachmentPolicyPhaseResult, ...]
    oracle_ceilings: tuple[AttachmentOracleCeiling, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.policies) != 10:
            raise ValueError("Selection phase requires ten syntax-policy variants.")
        if tuple(sorted(self.policies, key=lambda item: _policy_sort_key(item.policy))) != (
            self.policies
        ):
            raise ValueError("Selection policies must use canonical order.")
        if any(item.phase != self.phase for item in self.policies):
            raise ValueError("Selection phase contains a foreign policy result.")
        if tuple(item.kind for item in self.oracle_ceilings) != tuple(AttachmentOracleCeilingKind):
            raise ValueError("Selection phase requires both canonical Oracle Ceilings.")
        if any(item.phase != self.phase for item in self.oracle_ceilings):
            raise ValueError("Selection phase contains a foreign Oracle Ceiling.")
        return self


class AttachmentHeadAwareTriggerObservation(BaseModel):
    """One contained Event classified against the Candidate's exact anchor."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    candidate_id: _CandidateId
    source_grounded_event_id: _EventId
    candidate_range: AttachmentSourceRange
    event_head_range: AttachmentSourceRange
    candidate_anchor_token_id: str | None
    event_anchor_token_id: str | None
    foreign_trigger: bool | None
    gap_code: Literal["candidate_anchor_missing", "event_anchor_missing"] | None
    normalized_gold_none: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.gap_code is None:
            if self.candidate_anchor_token_id is None or self.event_anchor_token_id is None:
                raise ValueError("Head-aware trigger decision requires both anchors.")
            expected = self.candidate_anchor_token_id != self.event_anchor_token_id
            if self.foreign_trigger != expected:
                raise ValueError("Foreign-trigger status drifted from exact anchors.")
        elif self.foreign_trigger is not None:
            raise ValueError("Head-aware trigger gap cannot make a foreign-trigger decision.")
        return self


class AttachmentHeadAwareTriggerSummary(BaseModel):
    """Normalized Gold-NONE performance of the head-aware trigger diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    observation_count: Annotated[int, Field(ge=0)]
    candidate_count: Annotated[int, Field(ge=0)]
    flagged_candidate_count: Annotated[int, Field(ge=0)]
    gap_candidate_count: Annotated[int, Field(ge=0)]
    normalized_gold_none_count: Annotated[int, Field(ge=0)]
    flagged_gold_none_count: Annotated[int, Field(ge=0)]
    precision: Annotated[float, Field(ge=0, le=1)]
    recall: Annotated[float, Field(ge=0, le=1)]
    observations: tuple[AttachmentHeadAwareTriggerObservation, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.observation_count != len(self.observations):
            raise ValueError("Head-aware trigger observation count drifted.")
        if self.precision != _ratio(
            self.flagged_gold_none_count,
            self.flagged_candidate_count,
        ):
            raise ValueError("Head-aware trigger precision drifted.")
        if self.recall != _ratio(
            self.flagged_gold_none_count,
            self.normalized_gold_none_count,
        ):
            raise ValueError("Head-aware trigger recall drifted.")
        return self


class AttachmentRepeatedOccurrenceSeparation(BaseModel):
    """Occurrence identity and semantic exactness scored as separate facts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    candidate_range: AttachmentSourceRange
    linguistic_token_ids: tuple[Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")], ...]
    equal_text_occurrence_count: Annotated[int, Field(ge=2)]
    occurrence_identity_preserved: bool
    gold_event_ids: tuple[_EventId, ...]
    primary_policy_event_ids: tuple[_EventId, ...]
    semantic_attachment_exact: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.linguistic_token_ids:
            raise ValueError("Repeated occurrence requires linguistic token identities.")
        _ordered_distinct("repeated-occurrence Gold IDs", self.gold_event_ids)
        _ordered_distinct(
            "repeated-occurrence primary policy IDs",
            self.primary_policy_event_ids,
        )
        if self.occurrence_identity_preserved is not True:
            raise ValueError("CEA-1.3 requires preserved repeated-occurrence identity.")
        if self.semantic_attachment_exact != (self.gold_event_ids == self.primary_policy_event_ids):
            raise ValueError("Repeated-occurrence semantic exactness drifted.")
        return self


class AttachmentSelectionPolicyReport(BaseModel):
    """Complete model-free CEA-1.3 bounded hybrid selection report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_selection_policy_report_v1"] = (
        "attachment_selection_policy_report_v1"
    )
    policy_id: Literal["competitive_attachment_bounded_hybrid_selection_v1"] = (
        "competitive_attachment_bounded_hybrid_selection_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    comparison_ranges: tuple[AttachmentComparisonRange, ...]
    normalization_changes: tuple[AttachmentNormalizationChange, ...]
    development: AttachmentSelectionPhaseResult
    validation: AttachmentSelectionPhaseResult
    head_aware_trigger: AttachmentHeadAwareTriggerSummary
    repeated_occurrences: tuple[AttachmentRepeatedOccurrenceSeparation, ...]
    primary_policy_id: Literal["path_1_plus_complement"] = "path_1_plus_complement"
    outcome: AttachmentSelectionOutcome
    validation_interpretation: Literal["diagnostic_only"] = "diagnostic_only"
    production_integration: Literal["not_activated"] = "not_activated"
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("selection evidence labels", tuple(item.label for item in self.inputs))
        if len(self.comparison_ranges) != 341:
            raise ValueError("CEA-1.3 requires all 341 frozen Candidate ranges.")
        if len(self.normalization_changes) != 3:
            raise ValueError("CEA-1.3 requires exactly three normalized Gold changes.")
        if self.development.candidate_count != 162 or self.validation.candidate_count != 179:
            raise ValueError("CEA-1.3 frozen phase inventory drifted.")
        if len(self.repeated_occurrences) != 3:
            raise ValueError("CEA-1.3 requires three repeated-occurrence cases.")
        expected = attachment_selection_policy_fingerprint(self)
        if self.result_fingerprint != expected:
            raise ValueError("Selection-policy result fingerprint drifted.")
        return self


class AttachmentSelectionPolicyManifest(BaseModel):
    """Digest chain for one terminal CEA-1.3 evidence package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_selection_policy_manifest_v1"] = (
        "attachment_selection_policy_manifest_v1"
    )
    policy_id: Literal["competitive_attachment_bounded_hybrid_selection_v1"] = (
        "competitive_attachment_bounded_hybrid_selection_v1"
    )
    tdd: AttachmentEvidenceReference
    inputs: tuple[AttachmentEvidenceReference, ...]
    outputs: tuple[AttachmentEvidenceReference, ...]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("selection manifest inputs", tuple(item.label for item in self.inputs))
        _ordered_distinct("selection manifest outputs", tuple(item.label for item in self.outputs))
        return self


class AttachmentSelectionPolicyStatus(BaseModel):
    """Terminal machine-readable status for one CEA-1.3 run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_selection_policy_status_v1"] = (
        "attachment_selection_policy_status_v1"
    )
    status: Literal["complete"] = "complete"
    outcome: AttachmentSelectionOutcome
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    report_path: Annotated[str, Field(min_length=1)]
    review_path: Annotated[str, Field(min_length=1)]
    summary_path: Annotated[str, Field(min_length=1)]
    handoff_path: Annotated[str, Field(min_length=1)]


def normalize_attachment_comparison_range(
    *,
    phase: Literal["development", "validation"],
    source_segment_id: str,
    source_text: str,
    candidate_id: str,
    authoritative_start: int,
    authoritative_end: int,
) -> AttachmentComparisonRange:
    """Derive one evaluation-only range without changing source authority."""
    if not (0 <= authoritative_start < authoritative_end <= len(source_text)):
        raise ValueError("Authoritative Candidate range leaves its SourceSegment.")
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    start = authoritative_start
    end = authoritative_end
    operations: list[AttachmentNormalizationOperation] = []
    while start < end and source_text[start].isspace():
        start += 1
    if start != authoritative_start:
        operations.append(AttachmentNormalizationOperation.LEADING_WHITESPACE)
    delimiter_removed = False
    while start < end and source_text[start] in ",;:":
        delimiter_removed = True
        start += 1
        while start < end and source_text[start].isspace():
            start += 1
    if delimiter_removed:
        operations.append(AttachmentNormalizationOperation.LEADING_DELIMITER)
    terminal = re.search(r"(?:\s*\[[0-9]+\])+\s*$", source_text[start:end])
    if terminal is not None:
        end = start + terminal.start()
        operations.append(AttachmentNormalizationOperation.TERMINAL_CITATION_MARKERS)
    return AttachmentComparisonRange(
        phase=phase,
        source_segment_id=source_segment_id,
        source_text_sha256=source_digest,
        candidate_id=candidate_id,
        authoritative_range=AttachmentSourceRange(
            start=authoritative_start,
            end=authoritative_end,
            text=source_text[authoritative_start:authoritative_end],
        ),
        comparison_start=start,
        comparison_end=end,
        comparison_text=source_text[start:end],
        operations=tuple(operations),
        gap_code=(AttachmentComparisonGapCode.EMPTY_AFTER_NORMALIZATION if start == end else None),
    )


def attachment_syntax_policy_id(
    *,
    maximum_path_length: int | None,
    governed_complement_scope: bool,
) -> str:
    """Return the canonical ID for one bounded syntax policy."""
    path = "unbounded" if maximum_path_length is None else str(maximum_path_length)
    suffix = "_plus_complement" if governed_complement_scope else ""
    return f"path_{path}{suffix}"


def attachment_syntax_policies() -> tuple[AttachmentSyntaxPolicy, ...]:
    """Return the complete canonical CEA-1.3 policy sweep."""
    return tuple(
        AttachmentSyntaxPolicy(
            policy_id=attachment_syntax_policy_id(
                maximum_path_length=maximum,
                governed_complement_scope=complement,
            ),
            maximum_path_length=maximum,
            governed_complement_scope=complement,
        )
        for maximum in (1, 2, 3, 4, None)
        for complement in (False, True)
    )


def governed_complement_scope_supports(observation: AttachmentSyntaxObservation) -> bool:
    """Recognize one direct governed complement subtree without recursive propagation."""
    if (
        observation.event_anchor is None
        or observation.candidate_anchor is None
        or observation.event_anchor.sentence_id != observation.candidate_anchor.sentence_id
        or not observation.path_steps
    ):
        return False
    first, *remaining = observation.path_steps
    if first.direction.value != "toward_dependent":
        return False
    if first.dependency_relation.split(":", maxsplit=1)[0] not in {"obj", "ccomp", "xcomp"}:
        return False
    return all(item.direction.value == "toward_dependent" for item in remaining)


def syntax_policy_supports(
    observation: AttachmentSyntaxObservation,
    policy: AttachmentSyntaxPolicy,
) -> bool:
    """Apply one bounded syntax policy to one frozen observation."""
    if observation.own_event_expression:
        return True
    path_supported = observation.structurally_supported and (
        policy.maximum_path_length is None
        or len(observation.path_steps) <= policy.maximum_path_length
    )
    complement_supported = policy.governed_complement_scope and governed_complement_scope_supports(
        observation
    )
    return path_supported or complement_supported


def attachment_selection_policy_fingerprint(
    value: BaseModel | dict[str, object],
) -> str:
    """Return the semantic digest of a CEA-1.3 report or payload."""
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    else:
        payload = {key: item for key, item in value.items() if key != "result_fingerprint"}
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _policy_sort_key(policy: AttachmentSyntaxPolicy) -> tuple[int, bool]:
    maximum = 5 if policy.maximum_path_length is None else policy.maximum_path_length
    return maximum, policy.governed_complement_scope


def _ordered_distinct(label: str, values: tuple[object, ...]) -> None:
    if len(set(values)) != len(values) or tuple(sorted(values, key=str)) != values:
        raise ValueError(f"{label} must be ordered and distinct.")


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
