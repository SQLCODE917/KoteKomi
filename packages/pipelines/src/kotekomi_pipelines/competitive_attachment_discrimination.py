"""Deterministic audit and scoring for the CEA-1.1 experiment."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from typing import Literal

from kotekomi_application import (
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentFailureAudit,
    CompetitiveAttachmentFailureAuditCase,
    CompetitiveAttachmentFailureShape,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentPhaseReport,
    CompetitiveDiscriminationArmComparison,
    CompetitiveDiscriminationCaseResult,
    CompetitiveDiscriminationCatalog,
    CompetitiveDiscriminationCatalogCase,
    CompetitiveDiscriminationCategory,
    CompetitiveDiscriminationComparison,
    CompetitiveDiscriminationConditionReport,
    CompetitiveDiscriminationMetrics,
    CompetitiveDiscriminationOutcome,
    CompetitiveDiscriminationPromptArm,
    PropositionFragmentReason,
    attachment_set_is_prefix,
    attachment_set_jaccard,
    competitive_attachment_failure_shape,
    competitive_attachment_model_task_input,
)
from kotekomi_domain import ModelRun

from kotekomi_pipelines.competitive_event_attachment_stage_local import (
    CompetitiveAttachmentBaselineDecision,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldFragmentRequirement,
)


def build_competitive_attachment_failure_audit(
    *,
    report_bytes: bytes,
    report: CompetitiveAttachmentPhaseReport,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    baseline: dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]],
    catalog: PropositionGoldCatalog,
    gold_bindings: dict[str, str],
    source_text_by_digest: dict[str, str],
) -> CompetitiveAttachmentFailureAudit:
    """Build complete inspectable evidence for every nonexact validation case."""
    if report.phase != "validation":
        raise ValueError("CEA-1.1 failure audit requires a validation report.")
    matrix_by_candidate = {
        candidate.id: matrix for matrix in matrices for candidate in matrix.candidates
    }
    decision_by_candidate = {
        decision.candidate_id: decision for matrix in matrices for decision in matrix.decisions
    }
    oracle_by_candidate = {item.candidate_id: item for values in oracle.values() for item in values}
    baseline_by_candidate = {
        item.candidate_id: item for values in baseline.values() for item in values
    }
    gold_by_sge = {
        gold_bindings[item.event_id]: item for item in catalog.events if item.phase == "validation"
    }
    cases: list[CompetitiveAttachmentFailureAuditCase] = []
    for evaluation in report.cases:
        if evaluation.competitive_exact:
            continue
        matrix = matrix_by_candidate[evaluation.candidate_id]
        candidate = next(item for item in matrix.candidates if item.id == evaluation.candidate_id)
        decision = decision_by_candidate[candidate.id]
        gold = oracle_by_candidate[candidate.id]
        baseline_decision = baseline_by_candidate[candidate.id]
        source_text = source_text_by_digest[matrix.source_text_sha256]
        requirements = tuple(
            sorted(
                {
                    requirement.value
                    for event_id in gold.source_grounded_event_ids
                    for fragment in gold_by_sge[event_id].fragments
                    if _overlaps(candidate.start, candidate.end, fragment.start, fragment.end)
                    for requirement in fragment.requirements
                }
            )
        )
        model_input = competitive_attachment_model_task_input(
            source_text=source_text,
            candidate=candidate,
            event_options=matrix.event_options,
        ).decode()
        canonical_event_ids = tuple(item.source_grounded_event_id for item in matrix.event_options)
        cases.append(
            CompetitiveAttachmentFailureAuditCase(
                candidate_id=candidate.id,
                source_segment_id=matrix.source_segment_id,
                source_text=source_text,
                source_text_sha256=matrix.source_text_sha256,
                candidate_start=candidate.start,
                candidate_end=candidate.end,
                candidate_text=candidate.text,
                candidate_reasons=candidate.reasons,
                event_options=matrix.event_options,
                gold_event_ids=tuple(sorted(gold.source_grounded_event_ids)),
                baseline_event_ids=baseline_decision.attached_event_ids,
                competitive_event_ids=evaluation.competitive_event_ids,
                missing_event_ids=tuple(
                    sorted(
                        set(gold.source_grounded_event_ids) - set(evaluation.competitive_event_ids)
                    )
                ),
                extra_event_ids=tuple(
                    sorted(
                        set(evaluation.competitive_event_ids) - set(gold.source_grounded_event_ids)
                    )
                ),
                failure_shape=competitive_attachment_failure_shape(
                    tuple(sorted(gold.source_grounded_event_ids)),
                    evaluation.competitive_event_ids,
                ),
                gold_requirement_labels=requirements,
                shared_gold=len(gold.source_grounded_event_ids) > 1,
                repeated_text_count=_occurrence_count(source_text, candidate.text),
                gold_is_prefix=attachment_set_is_prefix(
                    tuple(sorted(gold.source_grounded_event_ids)), canonical_event_ids
                ),
                prediction_is_prefix=attachment_set_is_prefix(
                    evaluation.competitive_event_ids, canonical_event_ids
                ),
                model_input=model_input,
                model_input_sha256=hashlib.sha256(model_input.encode()).hexdigest(),
                raw_output_base64=decision.raw_output_base64,
                raw_output_sha256=decision.raw_output_sha256,
            )
        )
    ordered = tuple(
        sorted(
            cases,
            key=lambda item: (
                item.source_text_sha256,
                item.candidate_start,
                item.candidate_end,
                item.candidate_id,
            ),
        )
    )
    counts = Counter(item.failure_shape for item in ordered)
    return CompetitiveAttachmentFailureAudit(
        cea1_report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        error_count=len(ordered),
        complete_omission_count=counts[CompetitiveAttachmentFailureShape.COMPLETE_OMISSION],
        under_attachment_count=counts[CompetitiveAttachmentFailureShape.UNDER_ATTACHMENT],
        false_positive_none_count=counts[CompetitiveAttachmentFailureShape.FALSE_POSITIVE_NONE],
        over_attachment_count=counts[CompetitiveAttachmentFailureShape.OVER_ATTACHMENT],
        wrong_set_substitution_count=counts[
            CompetitiveAttachmentFailureShape.WRONG_SET_SUBSTITUTION
        ],
        cases=ordered,
    )


def build_competitive_discrimination_catalog(
    *,
    report_bytes: bytes,
    report: CompetitiveAttachmentPhaseReport,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    source_text_by_digest: dict[str, str],
) -> CompetitiveDiscriminationCatalog:
    """Select the predeclared 24 development candidates without Gold leakage to Qwen."""
    if report.phase != "development":
        raise ValueError("CEA-1.1 catalog requires a development report.")
    matrix_by_candidate = {
        candidate.id: matrix for matrix in matrices for candidate in matrix.candidates
    }
    evaluation_by_candidate = {item.candidate_id: item for item in report.cases}
    gold_by_candidate = {item.candidate_id: item for values in oracle.values() for item in values}
    ordered_candidates = tuple(
        candidate
        for matrix in sorted(matrices, key=lambda item: item.source_text_sha256)
        for candidate in matrix.candidates
    )
    selected: list[str] = []
    categories_by_candidate: dict[str, set[CompetitiveDiscriminationCategory]] = {}

    def select(
        category: CompetitiveDiscriminationCategory,
        quota: int,
        predicate: Callable[[CompetitiveAttachmentCandidate], bool],
    ) -> None:
        matches = tuple(
            candidate
            for candidate in ordered_candidates
            if candidate.id not in selected and predicate(candidate)
        )
        for candidate in matches[:quota]:
            selected.append(candidate.id)
            categories_by_candidate.setdefault(candidate.id, set()).add(category)

    def non_prefix(candidate: CompetitiveAttachmentCandidate) -> bool:
        matrix = matrix_by_candidate[candidate.id]
        canonical = tuple(item.source_grounded_event_id for item in matrix.event_options)
        gold = tuple(sorted(gold_by_candidate[candidate.id].source_grounded_event_ids))
        return bool(gold) and not attachment_set_is_prefix(gold, canonical)

    select(CompetitiveDiscriminationCategory.NON_PREFIX_GOLD, 6, non_prefix)
    select(
        CompetitiveDiscriminationCategory.GOVERNING_CONTEXT,
        4,
        lambda candidate: (
            not evaluation_by_candidate[candidate.id].competitive_exact
            and PropositionFragmentReason.GOVERNING_CONTEXT in candidate.reasons
        ),
    )
    select(
        CompetitiveDiscriminationCategory.SHARED_UNDER_ATTACHMENT,
        4,
        lambda candidate: (
            evaluation_by_candidate[candidate.id].false_negative_edge_count > 0
            and len(gold_by_candidate[candidate.id].source_grounded_event_ids) > 1
        ),
    )
    select(
        CompetitiveDiscriminationCategory.NONE_FALSE_POSITIVE,
        4,
        lambda candidate: (
            not gold_by_candidate[candidate.id].source_grounded_event_ids
            and evaluation_by_candidate[candidate.id].false_positive_edge_count > 0
        ),
    )
    select(
        CompetitiveDiscriminationCategory.REPEATED_TEXT,
        3,
        lambda candidate: (
            _occurrence_count(
                source_text_by_digest[matrix_by_candidate[candidate.id].source_text_sha256],
                candidate.text,
            )
            > 1
        ),
    )
    select(
        CompetitiveDiscriminationCategory.EXACT_CONTROL,
        3,
        lambda candidate: evaluation_by_candidate[candidate.id].competitive_exact,
    )
    if len(selected) < 24:
        select(
            CompetitiveDiscriminationCategory.NONEXACT_FILL,
            24 - len(selected),
            lambda candidate: not evaluation_by_candidate[candidate.id].competitive_exact,
        )
    if len(selected) != 24:
        raise ValueError("CEA-1.1 could not select 24 unique development candidates.")
    cases = tuple(
        CompetitiveDiscriminationCatalogCase(
            ordinal=ordinal,
            matrix_id=matrix_by_candidate[candidate_id].id,
            candidate_id=candidate_id,
            categories=tuple(
                sorted(categories_by_candidate[candidate_id], key=lambda value: value.value)
            ),
        )
        for ordinal, candidate_id in enumerate(selected, start=1)
    )
    return CompetitiveDiscriminationCatalog(
        cea1_development_report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        cases=cases,
    )


def build_competitive_discrimination_condition_report(
    *,
    arm: CompetitiveDiscriminationPromptArm,
    event_order: Literal["source", "reversed"],
    repetition: int,
    prompt_bytes: bytes,
    catalog: CompetitiveDiscriminationCatalog,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    gold_catalog: PropositionGoldCatalog,
    gold_bindings: dict[str, str],
    model_runs: tuple[ModelRun, ...],
) -> CompetitiveDiscriminationConditionReport:
    """Score one exact Prompt Arm and Event Order against the frozen catalog."""
    matrix_by_candidate = {
        candidate.id: matrix for matrix in matrices for candidate in matrix.candidates
    }
    gold_by_candidate = {item.candidate_id: item for values in oracle.values() for item in values}
    case_by_candidate = {item.candidate_id: item for item in catalog.cases}
    gold_by_sge = {
        gold_bindings[item.event_id]: item
        for item in gold_catalog.events
        if item.phase == "development"
    }
    results: list[CompetitiveDiscriminationCaseResult] = []
    tp = fp = fn = 0
    sibling_leakage = 0
    non_prefix_cases = non_prefix_exact = 0
    governing_total = governing_matched = 0
    shared_total = shared_matched = 0
    none_total = none_correct = 0
    entity_total = entity_matched = 0
    qualification_total = qualification_matched = 0
    unresolved = 0
    status_counts: Counter[CompetitiveAttachmentDecisionStatus] = Counter()
    failure_shape_counts: Counter[CompetitiveAttachmentFailureShape] = Counter()
    for candidate_id in sorted(case_by_candidate):
        matrix = matrix_by_candidate[candidate_id]
        candidate = next(item for item in matrix.candidates if item.id == candidate_id)
        decision = next(item for item in matrix.decisions if item.candidate_id == candidate_id)
        gold_ids = tuple(sorted(gold_by_candidate[candidate_id].source_grounded_event_ids))
        predicted_ids = tuple(sorted(item.source_grounded_event_id for item in decision.edges))
        gold_set = set(gold_ids)
        predicted_set = set(predicted_ids)
        tp += len(gold_set & predicted_set)
        fp += len(predicted_set - gold_set)
        fn += len(gold_set - predicted_set)
        sibling_leakage += len(predicted_set - gold_set) if gold_set else 0
        canonical_ids = tuple(item.source_grounded_event_id for item in matrix.event_options)
        if gold_ids and not attachment_set_is_prefix(gold_ids, canonical_ids):
            non_prefix_cases += 1
            non_prefix_exact += gold_ids == predicted_ids
        if not gold_ids:
            none_total += 1
            none_correct += not predicted_ids
        if len(gold_ids) > 1:
            shared_total += len(gold_ids)
            shared_matched += len(gold_set & predicted_set)
        for gold_id in gold_ids:
            requirements = {
                requirement
                for fragment in gold_by_sge[gold_id].fragments
                if _overlaps(candidate.start, candidate.end, fragment.start, fragment.end)
                for requirement in fragment.requirements
            }
            matched = gold_id in predicted_set
            if PropositionFragmentReason.GOVERNING_CONTEXT in candidate.reasons:
                governing_total += 1
                governing_matched += matched
            if PropositionFragmentReason.ENTITY_OCCURRENCE in candidate.reasons:
                entity_total += 1
                entity_matched += matched
            if any(
                item is not PropositionGoldFragmentRequirement.CORE_EVENT for item in requirements
            ):
                qualification_total += 1
                qualification_matched += matched
        unresolved += decision.status is not CompetitiveAttachmentDecisionStatus.COMPLETE
        status_counts[decision.status] += 1
        if gold_ids != predicted_ids:
            failure_shape_counts[competitive_attachment_failure_shape(gold_ids, predicted_ids)] += 1
        results.append(
            CompetitiveDiscriminationCaseResult(
                candidate_id=candidate_id,
                gold_event_ids=gold_ids,
                predicted_event_ids=predicted_ids,
                status=decision.status,
                exact=(
                    decision.status is CompetitiveAttachmentDecisionStatus.COMPLETE
                    and gold_ids == predicted_ids
                ),
                jaccard_similarity=attachment_set_jaccard(gold_ids, predicted_ids),
                hamming_error_count=len(gold_set ^ predicted_set),
                hamming_cell_count=len(matrix.event_options),
            )
        )
    ordered_results = tuple(sorted(results, key=lambda item: item.candidate_id))
    exact_count = sum(item.exact for item in ordered_results)
    hamming_errors = sum(item.hamming_error_count for item in ordered_results)
    hamming_cells = sum(item.hamming_cell_count for item in ordered_results)
    metrics = CompetitiveDiscriminationMetrics(
        candidate_count=24,
        exact_set_accuracy=_ratio(exact_count, 24),
        mean_jaccard_similarity=sum(item.jaccard_similarity for item in ordered_results) / 24,
        hamming_loss=_ratio(hamming_errors, hamming_cells),
        edge_precision=_ratio(tp, tp + fp),
        edge_recall=_ratio(tp, tp + fn),
        complete_omission_count=failure_shape_counts[
            CompetitiveAttachmentFailureShape.COMPLETE_OMISSION
        ],
        under_attachment_count=failure_shape_counts[
            CompetitiveAttachmentFailureShape.UNDER_ATTACHMENT
        ],
        false_positive_none_count=failure_shape_counts[
            CompetitiveAttachmentFailureShape.FALSE_POSITIVE_NONE
        ],
        over_attachment_count=failure_shape_counts[
            CompetitiveAttachmentFailureShape.OVER_ATTACHMENT
        ],
        wrong_set_substitution_count=failure_shape_counts[
            CompetitiveAttachmentFailureShape.WRONG_SET_SUBSTITUTION
        ],
        sibling_event_leakage_count=sibling_leakage,
        non_prefix_case_count=non_prefix_cases,
        non_prefix_exact_count=non_prefix_exact,
        governing_gold_edge_count=governing_total,
        governing_matched_edge_count=governing_matched,
        shared_gold_edge_count=shared_total,
        shared_matched_edge_count=shared_matched,
        none_case_count=none_total,
        none_correct_count=none_correct,
        entity_gold_edge_count=entity_total,
        entity_matched_edge_count=entity_matched,
        qualification_gold_edge_count=qualification_total,
        qualification_matched_edge_count=qualification_matched,
        unclear_count=status_counts[CompetitiveAttachmentDecisionStatus.UNCLEAR],
        invalid_output_count=status_counts[CompetitiveAttachmentDecisionStatus.INVALID_OUTPUT],
        model_failed_count=status_counts[CompetitiveAttachmentDecisionStatus.MODEL_FAILED],
        context_budget_blocked_count=status_counts[
            CompetitiveAttachmentDecisionStatus.CONTEXT_BUDGET_BLOCKED
        ],
        unresolved_count=unresolved,
    )
    fingerprint = _sha_json(
        {
            "arm": arm,
            "event_order": event_order,
            "cases": [item.model_dump(mode="json") for item in ordered_results],
            "metrics": metrics.model_dump(mode="json"),
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        }
    )
    if len(model_runs) != 24:
        raise ValueError("A discrimination condition requires exactly 24 ModelRuns.")
    return CompetitiveDiscriminationConditionReport(
        arm=arm,
        event_order=event_order,
        repetition=repetition,
        prompt_sha256=hashlib.sha256(prompt_bytes).hexdigest(),
        cases=ordered_results,
        metrics=metrics,
        model_execution_count=24,
        input_token_count=sum(
            _model_run_token_count(item, "input_token_count") for item in model_runs
        ),
        output_token_count=sum(
            _model_run_token_count(item, "output_token_count") for item in model_runs
        ),
        elapsed_milliseconds=sum(_model_run_elapsed_milliseconds(item) for item in model_runs),
        result_fingerprint=fingerprint,
    )


def compare_competitive_discrimination_reports(
    *,
    failure_audit_sha256: str,
    catalog_sha256: str,
    reports: tuple[CompetitiveDiscriminationConditionReport, ...],
    report_sha256s: dict[tuple[CompetitiveDiscriminationPromptArm, str, int], str],
) -> CompetitiveDiscriminationComparison:
    """Classify CEA-1.1 without activating production behavior."""
    by_key = {(item.arm, item.event_order, item.repetition): item for item in reports}
    required = {
        (arm, order, 1)
        for arm in CompetitiveDiscriminationPromptArm
        for order in ("source", "reversed")
    } | {
        (CompetitiveDiscriminationPromptArm.COMBINED, order, 2) for order in ("source", "reversed")
    }
    if set(by_key) != required or set(report_sha256s) != required:
        raise ValueError("CEA-1.1 comparison requires its exact ten condition reports.")
    arms: list[CompetitiveDiscriminationArmComparison] = []
    sensitivity: dict[CompetitiveDiscriminationPromptArm, int] = {}
    for arm in CompetitiveDiscriminationPromptArm:
        source = by_key[(arm, "source", 1)]
        reversed_report = by_key[(arm, "reversed", 1)]
        source_by_candidate = {item.candidate_id: item for item in source.cases}
        reversed_by_candidate = {item.candidate_id: item for item in reversed_report.cases}
        count = sum(
            source_by_candidate[key].predicted_event_ids
            != reversed_by_candidate[key].predicted_event_ids
            for key in source_by_candidate
        )
        sensitivity[arm] = count
        arms.append(
            CompetitiveDiscriminationArmComparison(
                arm=arm,
                source_report_sha256=report_sha256s[(arm, "source", 1)],
                reversed_report_sha256=report_sha256s[(arm, "reversed", 1)],
                order_sensitive_candidate_count=count,
            )
        )
    orders = ("source", "reversed")
    control = tuple(
        by_key[(CompetitiveDiscriminationPromptArm.CONTROL, order, 1)] for order in orders
    )
    scope = tuple(by_key[(CompetitiveDiscriminationPromptArm.SCOPE, order, 1)] for order in orders)
    examples = tuple(
        by_key[(CompetitiveDiscriminationPromptArm.EXAMPLES, order, 1)] for order in orders
    )
    combined = tuple(
        by_key[(CompetitiveDiscriminationPromptArm.COMBINED, order, 1)] for order in orders
    )
    combined_repeat = tuple(
        by_key[(CompetitiveDiscriminationPromptArm.COMBINED, order, 2)] for order in orders
    )
    combined_repeat_stable = all(
        first.result_fingerprint == second.result_fingerprint
        for first, second in zip(combined, combined_repeat, strict=True)
    )
    exact_accuracy_improved_both_orders = all(
        candidate.metrics.exact_set_accuracy > baseline.metrics.exact_set_accuracy
        for candidate, baseline in zip(combined, control, strict=True)
    )
    jaccard_improved_both_orders = all(
        candidate.metrics.mean_jaccard_similarity > baseline.metrics.mean_jaccard_similarity
        for candidate, baseline in zip(combined, control, strict=True)
    )
    hamming_reduced_both_orders = all(
        candidate.metrics.hamming_loss < baseline.metrics.hamming_loss
        for candidate, baseline in zip(combined, control, strict=True)
    )
    order_sensitivity_reduced = (
        sensitivity[CompetitiveDiscriminationPromptArm.COMBINED]
        < sensitivity[CompetitiveDiscriminationPromptArm.CONTROL]
    )
    leakage_not_increased = all(
        candidate.metrics.sibling_event_leakage_count
        <= baseline.metrics.sibling_event_leakage_count
        for candidate, baseline in zip(combined, control, strict=True)
    )
    protected_recall_preserved = all(
        _ratio(
            candidate.metrics.entity_matched_edge_count,
            candidate.metrics.entity_gold_edge_count,
        )
        >= _ratio(
            baseline.metrics.entity_matched_edge_count,
            baseline.metrics.entity_gold_edge_count,
        )
        and _ratio(
            candidate.metrics.qualification_matched_edge_count,
            candidate.metrics.qualification_gold_edge_count,
        )
        >= _ratio(
            baseline.metrics.qualification_matched_edge_count,
            baseline.metrics.qualification_gold_edge_count,
        )
        and _ratio(
            candidate.metrics.shared_matched_edge_count,
            candidate.metrics.shared_gold_edge_count,
        )
        >= _ratio(
            baseline.metrics.shared_matched_edge_count,
            baseline.metrics.shared_gold_edge_count,
        )
        for candidate, baseline in zip(combined, control, strict=True)
    )
    none_accuracy_preserved = all(
        _ratio(
            candidate.metrics.none_correct_count,
            candidate.metrics.none_case_count,
        )
        >= _ratio(
            baseline.metrics.none_correct_count,
            baseline.metrics.none_case_count,
        )
        for candidate, baseline in zip(combined, control, strict=True)
    )
    scope_factor_improved = _factor_improved(
        scope,
        control,
        lambda metrics: metrics.governing_matched_edge_count,
    )
    examples_factor_improved = _factor_improved(
        examples,
        control,
        lambda metrics: metrics.non_prefix_exact_count,
    )
    safety_gates_passed = all(
        item.source_validity == 1.0
        and item.gold_coverage == 1.0
        and item.proposed_change_count == 0
        and item.accepted_ledger_change_count == 0
        and item.metrics.unresolved_count == 0
        for item in reports
    )
    supported = all(
        (
            combined_repeat_stable,
            exact_accuracy_improved_both_orders,
            jaccard_improved_both_orders,
            hamming_reduced_both_orders,
            order_sensitivity_reduced,
            leakage_not_increased,
            protected_recall_preserved,
            none_accuracy_preserved,
            safety_gates_passed,
        )
    )
    falsified = (
        not scope_factor_improved
        and not examples_factor_improved
        and not exact_accuracy_improved_both_orders
        and not jaccard_improved_both_orders
        and not hamming_reduced_both_orders
    )
    return CompetitiveDiscriminationComparison(
        failure_audit_sha256=failure_audit_sha256,
        catalog_sha256=catalog_sha256,
        arms=tuple(arms),
        combined_repeat_stable=combined_repeat_stable,
        exact_accuracy_improved_both_orders=exact_accuracy_improved_both_orders,
        jaccard_improved_both_orders=jaccard_improved_both_orders,
        hamming_reduced_both_orders=hamming_reduced_both_orders,
        order_sensitivity_reduced=order_sensitivity_reduced,
        leakage_not_increased=leakage_not_increased,
        protected_recall_preserved=protected_recall_preserved,
        none_accuracy_preserved=none_accuracy_preserved,
        scope_factor_improved=scope_factor_improved,
        examples_factor_improved=examples_factor_improved,
        safety_gates_passed=safety_gates_passed,
        outcome=(
            CompetitiveDiscriminationOutcome.SUPPORTED
            if supported
            else (
                CompetitiveDiscriminationOutcome.FALSIFIED
                if falsified
                else CompetitiveDiscriminationOutcome.MIXED
            )
        ),
    )


def _factor_improved(
    candidate: tuple[CompetitiveDiscriminationConditionReport, ...],
    baseline: tuple[CompetitiveDiscriminationConditionReport, ...],
    select: Callable[[CompetitiveDiscriminationMetrics], int],
) -> bool:
    differences = tuple(
        select(left.metrics) - select(right.metrics)
        for left, right in zip(candidate, baseline, strict=True)
    )
    return any(item > 0 for item in differences) and all(item >= 0 for item in differences)


def _occurrence_count(source_text: str, value: str) -> int:
    count = 0
    start = 0
    while True:
        position = source_text.find(value, start)
        if position < 0:
            return count
        count += 1
        start = position + 1


def _overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _model_run_token_count(
    model_run: ModelRun,
    key: Literal["input_token_count", "output_token_count"],
) -> int:
    receipt = model_run.execution_receipt
    if receipt is None:
        return 0
    value = receipt[key]
    if value is None and key == "output_token_count":
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"ModelRun {key} is not a nonnegative integer.")
    return value


def _model_run_elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics["elapsed_milliseconds"]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("ModelRun elapsed time is not a nonnegative integer.")
    return value


def _sha_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
