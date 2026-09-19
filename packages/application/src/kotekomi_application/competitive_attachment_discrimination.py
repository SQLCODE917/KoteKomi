"""Strict derived-evidence contracts for CEA-1.1 discrimination experiments."""

from __future__ import annotations

import base64
import hashlib
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentEventOption,
)
from kotekomi_application.source_grounded_proposition_scope import PropositionFragmentReason

_SHA256 = r"^[a-f0-9]{64}$"
type _EventId = Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
type _CandidateId = Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]


class CompetitiveDiscriminationPromptArm(StrEnum):
    """One predeclared CEA-1.1 prompt factor combination."""

    CONTROL = "control"
    SCOPE = "scope"
    EXAMPLES = "examples"
    COMBINED = "combined"


class CompetitiveAttachmentFailureShape(StrEnum):
    """Exact set relation between Gold and one predicted Attachment Set."""

    COMPLETE_OMISSION = "complete_omission"
    UNDER_ATTACHMENT = "under_attachment"
    FALSE_POSITIVE_NONE = "false_positive_none"
    OVER_ATTACHMENT = "over_attachment"
    WRONG_SET_SUBSTITUTION = "wrong_set_substitution"


class CompetitiveAttachmentMechanismLabel(StrEnum):
    """Reviewer explanation for one nonexact Attachment Set."""

    SCOPE_WORDING = "scope_wording"
    POSITION_BIAS = "position_bias"
    SHARED_FRAGMENT = "shared_fragment"
    REPEATED_OCCURRENCE = "repeated_occurrence"
    NONE_OVERSELECTION = "none_overselection"
    GENUINE_AMBIGUITY = "genuine_ambiguity"
    GOLD_OR_CANDIDATE_ISSUE = "gold_or_candidate_issue"
    OTHER = "other"


class CompetitiveDiscriminationCategory(StrEnum):
    """Deterministic reason that selected one development candidate."""

    NON_PREFIX_GOLD = "non_prefix_gold"
    GOVERNING_CONTEXT = "governing_context"
    SHARED_UNDER_ATTACHMENT = "shared_under_attachment"
    NONE_FALSE_POSITIVE = "none_false_positive"
    REPEATED_TEXT = "repeated_text"
    EXACT_CONTROL = "exact_control"
    NONEXACT_FILL = "nonexact_fill"


class CompetitiveDiscriminationOutcome(StrEnum):
    """Terminal CEA-1.1 experimental interpretation."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class CompetitiveAttachmentFailureAuditCase(BaseModel):
    """Complete inspectable evidence for one nonexact CEA-1 candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_start: Annotated[int, Field(ge=0)]
    candidate_end: Annotated[int, Field(gt=0)]
    candidate_text: Annotated[str, Field(min_length=1)]
    candidate_reasons: tuple[PropositionFragmentReason, ...]
    event_options: tuple[CompetitiveAttachmentEventOption, ...]
    gold_event_ids: tuple[_EventId, ...]
    baseline_event_ids: tuple[_EventId, ...]
    competitive_event_ids: tuple[_EventId, ...]
    missing_event_ids: tuple[_EventId, ...]
    extra_event_ids: tuple[_EventId, ...]
    failure_shape: CompetitiveAttachmentFailureShape
    gold_requirement_labels: tuple[Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")], ...]
    shared_gold: bool
    repeated_text_count: Annotated[int, Field(ge=1)]
    gold_is_prefix: bool
    prediction_is_prefix: bool
    model_input: Annotated[str, Field(min_length=1)]
    model_input_sha256: Annotated[str, Field(pattern=_SHA256)]
    raw_output_base64: str | None
    raw_output_sha256: Annotated[str, Field(pattern=_SHA256)] | None
    mechanism_labels: tuple[CompetitiveAttachmentMechanismLabel, ...] = ()
    review_rationale: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Failure audit source digest drifted.")
        if self.source_text[self.candidate_start : self.candidate_end] != self.candidate_text:
            raise ValueError("Failure audit Candidate is not source-exact.")
        for label, values in (
            ("Candidate reasons", self.candidate_reasons),
            ("Gold Event IDs", self.gold_event_ids),
            ("baseline Event IDs", self.baseline_event_ids),
            ("competitive Event IDs", self.competitive_event_ids),
            ("missing Event IDs", self.missing_event_ids),
            ("extra Event IDs", self.extra_event_ids),
            ("Gold requirements", self.gold_requirement_labels),
            ("mechanism labels", self.mechanism_labels),
        ):
            if tuple(sorted(set(values), key=str)) != values:
                raise ValueError(f"Failure audit {label} must be ordered and distinct.")
        gold = set(self.gold_event_ids)
        predicted = set(self.competitive_event_ids)
        if self.missing_event_ids != tuple(sorted(gold - predicted)):
            raise ValueError("Failure audit missing Event IDs drifted.")
        if self.extra_event_ids != tuple(sorted(predicted - gold)):
            raise ValueError("Failure audit extra Event IDs drifted.")
        if self.failure_shape is not competitive_attachment_failure_shape(
            self.gold_event_ids,
            self.competitive_event_ids,
        ):
            raise ValueError("Failure audit shape drifted.")
        if self.shared_gold != (len(self.gold_event_ids) > 1):
            raise ValueError("Failure audit shared-Gold observation drifted.")
        if self.model_input_sha256 != hashlib.sha256(self.model_input.encode()).hexdigest():
            raise ValueError("Failure audit model-input digest drifted.")
        if self.raw_output_base64 is None:
            if self.raw_output_sha256 is not None:
                raise ValueError("Missing failure-audit output cannot have a digest.")
        else:
            raw = base64.b64decode(self.raw_output_base64, validate=True)
            if hashlib.sha256(raw).hexdigest() != self.raw_output_sha256:
                raise ValueError("Failure audit raw-output digest drifted.")
        if bool(self.mechanism_labels) != (self.review_rationale is not None):
            raise ValueError("Reviewed mechanisms and rationale must appear together.")
        return self


class CompetitiveAttachmentFailureAudit(BaseModel):
    """Exhaustive typed audit of the CEA-1 validation errors."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_attachment_failure_audit_v1"] = (
        "competitive_attachment_failure_audit_v1"
    )
    cea1_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    error_count: Annotated[int, Field(ge=1)]
    complete_omission_count: Annotated[int, Field(ge=0)]
    under_attachment_count: Annotated[int, Field(ge=0)]
    false_positive_none_count: Annotated[int, Field(ge=0)]
    over_attachment_count: Annotated[int, Field(ge=0)]
    wrong_set_substitution_count: Annotated[int, Field(ge=0)]
    cases: tuple[CompetitiveAttachmentFailureAuditCase, ...]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.error_count != len(self.cases):
            raise ValueError("Failure audit error count drifted.")
        if (
            tuple(
                sorted(
                    self.cases,
                    key=lambda item: (
                        item.source_text_sha256,
                        item.candidate_start,
                        item.candidate_end,
                        item.candidate_id,
                    ),
                )
            )
            != self.cases
        ):
            raise ValueError("Failure audit cases must use source order.")
        expected = {
            shape: sum(item.failure_shape is shape for item in self.cases)
            for shape in CompetitiveAttachmentFailureShape
        }
        observed = {
            CompetitiveAttachmentFailureShape.COMPLETE_OMISSION: self.complete_omission_count,
            CompetitiveAttachmentFailureShape.UNDER_ATTACHMENT: self.under_attachment_count,
            CompetitiveAttachmentFailureShape.FALSE_POSITIVE_NONE: self.false_positive_none_count,
            CompetitiveAttachmentFailureShape.OVER_ATTACHMENT: self.over_attachment_count,
            CompetitiveAttachmentFailureShape.WRONG_SET_SUBSTITUTION: (
                self.wrong_set_substitution_count
            ),
        }
        if observed != expected:
            raise ValueError("Failure audit shape counts drifted.")
        return self


class CompetitiveDiscriminationCatalogCase(BaseModel):
    """One development Candidate selected for the CEA-1.1 ablation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ordinal: Annotated[int, Field(ge=1, le=24)]
    matrix_id: Annotated[str, Field(pattern=r"^cam_[a-f0-9]{24}$")]
    candidate_id: _CandidateId
    categories: tuple[CompetitiveDiscriminationCategory, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.categories:
            raise ValueError("A discrimination catalog case requires a category.")
        if tuple(sorted(set(self.categories), key=lambda value: value.value)) != self.categories:
            raise ValueError("Discrimination categories must be ordered and distinct.")
        return self


class CompetitiveDiscriminationCatalog(BaseModel):
    """Frozen development-only catalog for one CEA-1.1 experiment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_discrimination_catalog_v1"] = (
        "competitive_discrimination_catalog_v1"
    )
    cea1_development_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    cases: tuple[CompetitiveDiscriminationCatalogCase, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) != 24:
            raise ValueError("Discrimination catalog requires 24 cases.")
        if tuple(item.ordinal for item in self.cases) != tuple(range(1, 25)):
            raise ValueError("Discrimination catalog ordinals must be contiguous.")
        if len({item.candidate_id for item in self.cases}) != 24:
            raise ValueError("Discrimination catalog candidates must be unique.")
        return self


class CompetitiveDiscriminationPromptReference(BaseModel):
    """Pinned Prompt Arm evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    arm: CompetitiveDiscriminationPromptArm
    prompt_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]


class CompetitiveDiscriminationApproval(BaseModel):
    """Operator approval for one catalog and four Prompt Arms."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_discrimination_approval_v1"] = (
        "competitive_discrimination_approval_v1"
    )
    reviewer: Annotated[str, Field(min_length=1)]
    failure_audit_sha256: Annotated[str, Field(pattern=_SHA256)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    prompts: tuple[CompetitiveDiscriminationPromptReference, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.arm for item in self.prompts) != tuple(CompetitiveDiscriminationPromptArm):
            raise ValueError("Discrimination approval must cover every Prompt Arm in order.")
        return self


class CompetitiveDiscriminationCaseResult(BaseModel):
    """Canonical result for one candidate under one Prompt Arm and Event Order."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    gold_event_ids: tuple[_EventId, ...]
    predicted_event_ids: tuple[_EventId, ...]
    status: CompetitiveAttachmentDecisionStatus
    exact: bool
    jaccard_similarity: Annotated[float, Field(ge=0, le=1)]
    hamming_error_count: Annotated[int, Field(ge=0)]
    hamming_cell_count: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("Gold Event IDs", self.gold_event_ids),
            ("predicted Event IDs", self.predicted_event_ids),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"Discrimination result {label} must be ordered and distinct.")
        expected_exact = (
            self.status is CompetitiveAttachmentDecisionStatus.COMPLETE
            and self.gold_event_ids == self.predicted_event_ids
        )
        if self.exact != expected_exact:
            raise ValueError("Discrimination exact result drifted.")
        if self.jaccard_similarity != attachment_set_jaccard(
            self.gold_event_ids,
            self.predicted_event_ids,
        ):
            raise ValueError("Discrimination Jaccard Similarity drifted.")
        if self.hamming_error_count != len(
            set(self.gold_event_ids) ^ set(self.predicted_event_ids)
        ):
            raise ValueError("Discrimination Hamming error count drifted.")
        return self


class CompetitiveDiscriminationMetrics(BaseModel):
    """Occurrence-level metrics for one Prompt Arm, Event Order, and repetition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_count: Literal[24]
    exact_set_accuracy: Annotated[float, Field(ge=0, le=1)]
    mean_jaccard_similarity: Annotated[float, Field(ge=0, le=1)]
    hamming_loss: Annotated[float, Field(ge=0, le=1)]
    edge_precision: Annotated[float, Field(ge=0, le=1)]
    edge_recall: Annotated[float, Field(ge=0, le=1)]
    complete_omission_count: Annotated[int, Field(ge=0)]
    under_attachment_count: Annotated[int, Field(ge=0)]
    false_positive_none_count: Annotated[int, Field(ge=0)]
    over_attachment_count: Annotated[int, Field(ge=0)]
    wrong_set_substitution_count: Annotated[int, Field(ge=0)]
    sibling_event_leakage_count: Annotated[int, Field(ge=0)]
    non_prefix_case_count: Annotated[int, Field(ge=0)]
    non_prefix_exact_count: Annotated[int, Field(ge=0)]
    governing_gold_edge_count: Annotated[int, Field(ge=0)]
    governing_matched_edge_count: Annotated[int, Field(ge=0)]
    shared_gold_edge_count: Annotated[int, Field(ge=0)]
    shared_matched_edge_count: Annotated[int, Field(ge=0)]
    none_case_count: Annotated[int, Field(ge=0)]
    none_correct_count: Annotated[int, Field(ge=0)]
    entity_gold_edge_count: Annotated[int, Field(ge=0)]
    entity_matched_edge_count: Annotated[int, Field(ge=0)]
    qualification_gold_edge_count: Annotated[int, Field(ge=0)]
    qualification_matched_edge_count: Annotated[int, Field(ge=0)]
    unclear_count: Annotated[int, Field(ge=0)]
    invalid_output_count: Annotated[int, Field(ge=0)]
    model_failed_count: Annotated[int, Field(ge=0)]
    context_budget_blocked_count: Annotated[int, Field(ge=0)]
    unresolved_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, matched, total in (
            ("non-prefix", self.non_prefix_exact_count, self.non_prefix_case_count),
            ("governing", self.governing_matched_edge_count, self.governing_gold_edge_count),
            ("shared", self.shared_matched_edge_count, self.shared_gold_edge_count),
            ("NONE", self.none_correct_count, self.none_case_count),
            ("entity", self.entity_matched_edge_count, self.entity_gold_edge_count),
            (
                "qualification",
                self.qualification_matched_edge_count,
                self.qualification_gold_edge_count,
            ),
        ):
            if matched > total:
                raise ValueError(f"Discrimination {label} matched count exceeds its total.")
        return self


class CompetitiveDiscriminationConditionReport(BaseModel):
    """Complete result for one Prompt Arm, Event Order, and repetition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_discrimination_condition_report_v1"] = (
        "competitive_discrimination_condition_report_v1"
    )
    arm: CompetitiveDiscriminationPromptArm
    event_order: Literal["source", "reversed"]
    repetition: Annotated[int, Field(ge=1, le=2)]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    cases: tuple[CompetitiveDiscriminationCaseResult, ...]
    metrics: CompetitiveDiscriminationMetrics
    model_execution_count: Literal[24]
    input_token_count: Annotated[int, Field(ge=0)]
    output_token_count: Annotated[int, Field(ge=0)]
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    source_validity: Annotated[float, Field(ge=0, le=1)] = 1.0
    gold_coverage: Annotated[float, Field(ge=0, le=1)] = 1.0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) != 24 or self.metrics.candidate_count != len(self.cases):
            raise ValueError("Discrimination condition report requires 24 cases.")
        if tuple(sorted(self.cases, key=lambda item: item.candidate_id)) != self.cases:
            raise ValueError("Discrimination condition cases must use canonical order.")
        if self.source_validity != 1.0 or self.gold_coverage != 1.0:
            raise ValueError("Discrimination evidence must remain source-valid and Gold-complete.")
        exact_count = sum(item.exact for item in self.cases)
        hamming_errors = sum(item.hamming_error_count for item in self.cases)
        hamming_cells = sum(item.hamming_cell_count for item in self.cases)
        true_positive_edges = sum(
            len(set(item.gold_event_ids) & set(item.predicted_event_ids)) for item in self.cases
        )
        false_positive_edges = sum(
            len(set(item.predicted_event_ids) - set(item.gold_event_ids)) for item in self.cases
        )
        false_negative_edges = sum(
            len(set(item.gold_event_ids) - set(item.predicted_event_ids)) for item in self.cases
        )
        expected_primary = (
            exact_count / len(self.cases),
            sum(item.jaccard_similarity for item in self.cases) / len(self.cases),
            hamming_errors / hamming_cells,
            _ratio(true_positive_edges, true_positive_edges + false_positive_edges),
            _ratio(true_positive_edges, true_positive_edges + false_negative_edges),
        )
        observed_primary = (
            self.metrics.exact_set_accuracy,
            self.metrics.mean_jaccard_similarity,
            self.metrics.hamming_loss,
            self.metrics.edge_precision,
            self.metrics.edge_recall,
        )
        if any(
            abs(left - right) > 1e-12
            for left, right in zip(observed_primary, expected_primary, strict=True)
        ):
            raise ValueError("Discrimination primary metrics drifted from occurrence results.")
        expected_status_counts = {
            status: sum(item.status is status for item in self.cases)
            for status in CompetitiveAttachmentDecisionStatus
        }
        if (
            self.metrics.unclear_count
            != expected_status_counts[CompetitiveAttachmentDecisionStatus.UNCLEAR]
            or self.metrics.invalid_output_count
            != expected_status_counts[CompetitiveAttachmentDecisionStatus.INVALID_OUTPUT]
            or self.metrics.model_failed_count
            != expected_status_counts[CompetitiveAttachmentDecisionStatus.MODEL_FAILED]
            or self.metrics.context_budget_blocked_count
            != expected_status_counts[CompetitiveAttachmentDecisionStatus.CONTEXT_BUDGET_BLOCKED]
            or self.metrics.unresolved_count
            != sum(
                item.status is not CompetitiveAttachmentDecisionStatus.COMPLETE
                for item in self.cases
            )
        ):
            raise ValueError("Discrimination status metrics drifted from occurrence results.")
        expected_shapes = {
            shape: sum(
                item.gold_event_ids != item.predicted_event_ids
                and competitive_attachment_failure_shape(
                    item.gold_event_ids,
                    item.predicted_event_ids,
                )
                is shape
                for item in self.cases
            )
            for shape in CompetitiveAttachmentFailureShape
        }
        observed_shapes = {
            CompetitiveAttachmentFailureShape.COMPLETE_OMISSION: (
                self.metrics.complete_omission_count
            ),
            CompetitiveAttachmentFailureShape.UNDER_ATTACHMENT: (
                self.metrics.under_attachment_count
            ),
            CompetitiveAttachmentFailureShape.FALSE_POSITIVE_NONE: (
                self.metrics.false_positive_none_count
            ),
            CompetitiveAttachmentFailureShape.OVER_ATTACHMENT: (self.metrics.over_attachment_count),
            CompetitiveAttachmentFailureShape.WRONG_SET_SUBSTITUTION: (
                self.metrics.wrong_set_substitution_count
            ),
        }
        if observed_shapes != expected_shapes:
            raise ValueError("Discrimination Failure Shape metrics drifted from results.")
        expected_sibling_leakage = sum(
            len(set(item.predicted_event_ids) - set(item.gold_event_ids))
            for item in self.cases
            if item.gold_event_ids
        )
        expected_none_cases = sum(not item.gold_event_ids for item in self.cases)
        expected_none_correct = sum(
            not item.gold_event_ids and not item.predicted_event_ids for item in self.cases
        )
        if (
            self.metrics.sibling_event_leakage_count != expected_sibling_leakage
            or self.metrics.none_case_count != expected_none_cases
            or self.metrics.none_correct_count != expected_none_correct
        ):
            raise ValueError("Discrimination leakage or NONE metrics drifted from results.")
        return self


class CompetitiveDiscriminationArmComparison(BaseModel):
    """Paired Event-order evidence for one Prompt Arm."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    arm: CompetitiveDiscriminationPromptArm
    source_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    reversed_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    order_sensitive_candidate_count: Annotated[int, Field(ge=0, le=24)]


class CompetitiveDiscriminationComparison(BaseModel):
    """Terminal CEA-1.1 interpretation without production activation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_discrimination_comparison_v1"] = (
        "competitive_discrimination_comparison_v1"
    )
    failure_audit_sha256: Annotated[str, Field(pattern=_SHA256)]
    catalog_sha256: Annotated[str, Field(pattern=_SHA256)]
    arms: tuple[CompetitiveDiscriminationArmComparison, ...]
    combined_repeat_stable: bool
    exact_accuracy_improved_both_orders: bool
    jaccard_improved_both_orders: bool
    hamming_reduced_both_orders: bool
    order_sensitivity_reduced: bool
    leakage_not_increased: bool
    protected_recall_preserved: bool
    none_accuracy_preserved: bool
    scope_factor_improved: bool
    examples_factor_improved: bool
    safety_gates_passed: bool
    outcome: CompetitiveDiscriminationOutcome
    production_integration: Literal["not_activated"] = "not_activated"

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.arm for item in self.arms) != tuple(CompetitiveDiscriminationPromptArm):
            raise ValueError("Discrimination comparison must cover every Prompt Arm in order.")
        supported = all(
            (
                self.combined_repeat_stable,
                self.exact_accuracy_improved_both_orders,
                self.jaccard_improved_both_orders,
                self.hamming_reduced_both_orders,
                self.order_sensitivity_reduced,
                self.leakage_not_increased,
                self.protected_recall_preserved,
                self.none_accuracy_preserved,
                self.safety_gates_passed,
            )
        )
        falsified = (
            not self.scope_factor_improved
            and not self.examples_factor_improved
            and not self.exact_accuracy_improved_both_orders
            and not self.jaccard_improved_both_orders
            and not self.hamming_reduced_both_orders
        )
        expected = (
            CompetitiveDiscriminationOutcome.SUPPORTED
            if supported
            else (
                CompetitiveDiscriminationOutcome.FALSIFIED
                if falsified
                else CompetitiveDiscriminationOutcome.MIXED
            )
        )
        if self.outcome is not expected:
            raise ValueError("Discrimination outcome drifted from its gates.")
        return self


def competitive_attachment_failure_shape(
    gold_event_ids: tuple[str, ...],
    predicted_event_ids: tuple[str, ...],
) -> CompetitiveAttachmentFailureShape:
    """Classify one nonexact Attachment Set by exact set relation."""
    gold = set(gold_event_ids)
    predicted = set(predicted_event_ids)
    if gold == predicted:
        raise ValueError("An exact Attachment Set has no Failure Shape.")
    if gold and not predicted:
        return CompetitiveAttachmentFailureShape.COMPLETE_OMISSION
    if not gold and predicted:
        return CompetitiveAttachmentFailureShape.FALSE_POSITIVE_NONE
    if predicted < gold:
        return CompetitiveAttachmentFailureShape.UNDER_ATTACHMENT
    if gold < predicted:
        return CompetitiveAttachmentFailureShape.OVER_ATTACHMENT
    return CompetitiveAttachmentFailureShape.WRONG_SET_SUBSTITUTION


def attachment_set_jaccard(
    gold_event_ids: tuple[str, ...],
    predicted_event_ids: tuple[str, ...],
) -> float:
    """Measure one canonical Attachment Set pair."""
    gold = set(gold_event_ids)
    predicted = set(predicted_event_ids)
    union = gold | predicted
    return 1.0 if not union else len(gold & predicted) / len(union)


def attachment_set_is_prefix(
    event_ids: tuple[str, ...],
    canonical_event_ids: tuple[str, ...],
) -> bool:
    """Report whether a nonempty Attachment Set is a canonical Event prefix."""
    if not event_ids:
        return False
    selected = set(event_ids)
    prefix = tuple(canonical_event_ids[: len(selected)])
    return set(prefix) == selected


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator
