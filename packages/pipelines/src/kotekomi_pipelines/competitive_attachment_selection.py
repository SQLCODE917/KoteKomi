"""Model-free CEA-1.3 bounded hybrid selection diagnostic."""

from __future__ import annotations

import json
from typing import Literal

from kotekomi_application import (
    AttachmentComparisonRange,
    AttachmentEvidenceReference,
    AttachmentHeadAwareTriggerObservation,
    AttachmentHeadAwareTriggerSummary,
    AttachmentMetricSnapshot,
    AttachmentNormalizationChange,
    AttachmentOracleCeiling,
    AttachmentOracleCeilingKind,
    AttachmentPolicyPhaseResult,
    AttachmentRepeatedOccurrenceSeparation,
    AttachmentRescueMetrics,
    AttachmentReviewVerificationReport,
    AttachmentSelectionOutcome,
    AttachmentSelectionPhaseResult,
    AttachmentSelectionPolicyReport,
    AttachmentSyntaxObservation,
    AttachmentSyntaxPolicy,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentPhaseReport,
    attachment_selection_policy_fingerprint,
    attachment_syntax_policies,
    normalize_attachment_comparison_range,
    syntax_policy_supports,
)

from kotekomi_pipelines.event_entity_connection_stage_local import EventEntityExperimentInput
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragmentRequirement,
)

type _Oracle = dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]
type _Bindings = dict[str, str]
type _Predictions = dict[str, tuple[str, ...]]

_PRIMARY_POLICY_ID = "path_1_plus_complement"
_EXPECTED_NORMALIZATION_CHANGE_IDS = {
    "cac_35f4643f592ddd49a2afb9ce",
    "cac_38f29566aedd1d0ae5d51022",
    "cac_80f4e4057884ad3c44344c45",
}


def build_attachment_selection_policy_report(
    *,
    input_references: tuple[AttachmentEvidenceReference, ...],
    development_report: CompetitiveAttachmentPhaseReport,
    development_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    development_oracle: _Oracle,
    development_inputs: tuple[EventEntityExperimentInput, ...],
    development_bindings: _Bindings,
    validation_report: CompetitiveAttachmentPhaseReport,
    validation_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    validation_oracle: _Oracle,
    validation_inputs: tuple[EventEntityExperimentInput, ...],
    validation_bindings: _Bindings,
    review_report: AttachmentReviewVerificationReport,
    gold_catalog: PropositionGoldCatalog,
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
) -> AttachmentSelectionPolicyReport:
    """Build one complete CEA-1.3 report without executing a model."""
    _validate_inventory(
        development_report=development_report,
        development_matrices=development_matrices,
        development_inputs=development_inputs,
        validation_report=validation_report,
        validation_matrices=validation_matrices,
        validation_inputs=validation_inputs,
        review_report=review_report,
    )
    gold_by_sge = _gold_by_source_grounded_event(
        catalog=gold_catalog,
        development_bindings=development_bindings,
        validation_bindings=validation_bindings,
    )
    development_result = _build_phase_result(
        phase="development",
        report=development_report,
        matrices=development_matrices,
        original_oracle=_gold_sets(development_oracle),
        inputs=development_inputs,
        observations=review_report.development.observations,
        gold_by_sge=gold_by_sge,
        entity_occurrences_by_event=entity_occurrences_by_event,
    )
    validation_result = _build_phase_result(
        phase="validation",
        report=validation_report,
        matrices=validation_matrices,
        original_oracle=_gold_sets(validation_oracle),
        inputs=validation_inputs,
        observations=review_report.validation.observations,
        gold_by_sge=gold_by_sge,
        entity_occurrences_by_event=entity_occurrences_by_event,
    )
    comparisons = tuple(
        sorted(
            (*development_result.comparisons, *validation_result.comparisons),
            key=lambda item: (item.phase, item.source_text_sha256, item.candidate_id),
        )
    )
    changes = tuple(
        sorted(
            (*development_result.changes, *validation_result.changes),
            key=lambda item: (item.phase, item.source_text_sha256, item.candidate_id),
        )
    )
    observed_change_ids = {item.candidate_id for item in changes}
    if observed_change_ids != _EXPECTED_NORMALIZATION_CHANGE_IDS:
        raise ValueError(
            f"CEA-1.3 normalized Gold changes drifted: {sorted(observed_change_ids)!r}."
        )
    normalized_gold = {
        **development_result.normalized_gold,
        **validation_result.normalized_gold,
    }
    primary_predictions = {
        **development_result.primary_predictions,
        **validation_result.primary_predictions,
    }
    head_aware = _head_aware_trigger_summary(
        review_report=review_report,
        normalized_gold=normalized_gold,
    )
    matrices = (*development_matrices, *validation_matrices)
    source_by_digest = {
        item.event.source_text_sha256: item.source_text
        for item in (*development_inputs, *validation_inputs)
    }
    candidate_by_id = {
        candidate.id: (matrix, candidate) for matrix in matrices for candidate in matrix.candidates
    }
    repeated = tuple(
        AttachmentRepeatedOccurrenceSeparation(
            candidate_id=item.candidate_id,
            candidate_range=item.candidate_range,
            linguistic_token_ids=item.linguistic_token_ids,
            equal_text_occurrence_count=_source_occurrence_count(
                source_by_digest[candidate_by_id[item.candidate_id][0].source_text_sha256],
                item.candidate_range.text,
            ),
            occurrence_identity_preserved=True,
            gold_event_ids=normalized_gold[item.candidate_id],
            primary_policy_event_ids=primary_predictions[item.candidate_id],
            semantic_attachment_exact=(
                normalized_gold[item.candidate_id] == primary_predictions[item.candidate_id]
            ),
        )
        for item in review_report.repeated_occurrences
    )
    development = development_result.phase_result
    validation = validation_result.phase_result
    outcome = _outcome(development=development, validation=validation)
    draft = AttachmentSelectionPolicyReport.model_construct(
        inputs=tuple(sorted(input_references, key=lambda item: item.label)),
        comparison_ranges=comparisons,
        normalization_changes=changes,
        development=development,
        validation=validation,
        head_aware_trigger=head_aware,
        repeated_occurrences=repeated,
        primary_policy_id=_PRIMARY_POLICY_ID,
        outcome=outcome,
        validation_interpretation="diagnostic_only",
        production_integration="not_activated",
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint="0" * 64,
    )
    return AttachmentSelectionPolicyReport(
        inputs=draft.inputs,
        comparison_ranges=draft.comparison_ranges,
        normalization_changes=draft.normalization_changes,
        development=draft.development,
        validation=draft.validation,
        head_aware_trigger=draft.head_aware_trigger,
        repeated_occurrences=draft.repeated_occurrences,
        primary_policy_id=draft.primary_policy_id,
        outcome=draft.outcome,
        validation_interpretation=draft.validation_interpretation,
        production_integration=draft.production_integration,
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint=attachment_selection_policy_fingerprint(draft),
    )


def attachment_selection_policy_summary(
    report: AttachmentSelectionPolicyReport,
) -> dict[str, object]:
    """Return the bounded machine-readable CEA-1.3 summary."""
    return {
        "schema_version": "attachment_selection_policy_summary_v1",
        "status": "complete",
        "outcome": report.outcome.value,
        "result_fingerprint": report.result_fingerprint,
        "normalization_change_count": len(report.normalization_changes),
        "primary_policy_id": report.primary_policy_id,
        "development": _phase_summary(report.development),
        "validation": _phase_summary(report.validation),
        "head_aware_trigger": report.head_aware_trigger.model_dump(
            mode="json", exclude={"observations"}
        ),
        "repeated_occurrence_identity_preserved_count": sum(
            item.occurrence_identity_preserved for item in report.repeated_occurrences
        ),
        "repeated_occurrence_semantic_exact_count": sum(
            item.semantic_attachment_exact for item in report.repeated_occurrences
        ),
        "model_execution_count": 0,
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
        "production_integration": "not_activated",
    }


def render_attachment_selection_policy_review(
    report: AttachmentSelectionPolicyReport,
) -> str:
    """Render inspectable CEA-1.3 data in and data out."""
    lines = [
        "# CEA-1.3 Bounded Hybrid Selection Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Result fingerprint: `{report.result_fingerprint}`",
        "",
        "Validation remains diagnostic because this corpus informed earlier development.",
        "",
        "## Normalization changes",
        "",
    ]
    for item in report.normalization_changes:
        comparison = item.comparison
        lines.extend(
            (
                f"### {item.phase} — {item.candidate_id}",
                "",
                f"> {item.source_text}",
                "",
                "Authoritative Candidate: "
                f"`{comparison.authoritative_range.text}` "
                f"`[{comparison.authoritative_range.start}, "
                f"{comparison.authoritative_range.end})`",
                "",
                "Comparison Range: "
                f"`{comparison.comparison_text}` "
                f"`[{comparison.comparison_start}, {comparison.comparison_end})`",
                "",
                "Operations: "
                f"`{', '.join(value.value for value in comparison.operations) or 'none'}`",
                "",
                f"Original Gold: `{_ids(item.original_gold_event_ids)}`",
                "",
                f"Normalized Gold: `{_ids(item.normalized_gold_event_ids)}`",
                "",
            )
        )
    lines.extend(("## Policy sweep", ""))
    for phase in (report.development, report.validation):
        lines.extend(
            (
                f"### {phase.phase}",
                "",
                _metric_line("Prompt-v3 baseline", phase.prompt_v3_baseline_metrics),
                "",
                _metric_line("Competitive Qwen", phase.competitive_qwen_metrics),
                "",
            )
        )
        for item in phase.policies:
            lines.extend(
                (
                    f"#### {item.policy.policy_id}",
                    "",
                    _metric_line("Syntax", item.syntax_metrics),
                    "",
                    _metric_line("Qwen union syntax", item.union_metrics),
                    "",
                    _metric_line("Qwen intersection syntax", item.intersection_metrics),
                    "",
                    "Rescue: "
                    f"`{item.rescue.rescued_gold_edge_count}/"
                    f"{item.rescue.added_syntax_edge_count}` added edges are Gold; "
                    f"Qwen false-negative coverage "
                    f"`{item.rescue.qwen_false_negative_coverage:.6f}`.",
                    "",
                )
            )
        for ceiling in phase.oracle_ceilings:
            lines.extend(
                (
                    f"#### Non-deployable {ceiling.kind.value} Oracle Ceiling",
                    "",
                    _metric_line("Gold-dependent ceiling", ceiling.metrics),
                    "",
                )
            )
    lines.extend(("## Head-aware trigger diagnostic", ""))
    trigger = report.head_aware_trigger
    lines.extend(
        (
            f"Flagged Candidates: `{trigger.flagged_candidate_count}`",
            "",
            f"Anchor-gap Candidates: `{trigger.gap_candidate_count}`",
            "",
            f"Gold-NONE precision: `{trigger.precision:.6f}`",
            "",
            f"Gold-NONE recall: `{trigger.recall:.6f}`",
            "",
        )
    )
    for item in trigger.observations:
        lines.extend(
            (
                f"### {item.candidate_id} -> {item.source_grounded_event_id}",
                "",
                f"Candidate: `{item.candidate_range.text}`",
                "",
                f"Contained Event head: `{item.event_head_range.text}`",
                "",
                f"Candidate anchor: `{item.candidate_anchor_token_id or 'gap'}`",
                "",
                f"Event anchor: `{item.event_anchor_token_id or 'gap'}`",
                "",
                "Result: `"
                + (
                    item.gap_code
                    if item.gap_code is not None
                    else ("foreign" if item.foreign_trigger else "own_head")
                )
                + "`",
                "",
                f"Normalized Gold NONE: `{str(item.normalized_gold_none).lower()}`",
                "",
            )
        )
    lines.extend(("## Repeated occurrences", ""))
    for item in report.repeated_occurrences:
        lines.extend(
            (
                f"### {item.candidate_id}",
                "",
                f"Candidate: `{item.candidate_range.text}` "
                f"`[{item.candidate_range.start}, {item.candidate_range.end})`",
                "",
                f"Exact token IDs: `{', '.join(item.linguistic_token_ids)}`",
                "",
                f"Equal source occurrences: `{item.equal_text_occurrence_count}`",
                "",
                "Occurrence identity preserved: "
                f"`{str(item.occurrence_identity_preserved).lower()}`",
                "",
                f"Gold: `{_ids(item.gold_event_ids)}`",
                "",
                f"Primary policy: `{_ids(item.primary_policy_event_ids)}`",
                "",
                f"Semantic exactness: `{str(item.semantic_attachment_exact).lower()}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_selection_policy_handoff(
    report: AttachmentSelectionPolicyReport,
) -> str:
    """Render one compact self-contained CEA-1.3 reviewer handoff."""
    primary_dev = _primary(report.development)
    primary_val = _primary(report.validation)
    lines = [
        "# CEA-1.3 Bounded Hybrid Selection Handoff",
        "",
        "## Question",
        "",
        "Can deterministic boundary normalization and bounded syntax safely "
        "complement archived competitive Qwen decisions?",
        "",
        "## Fixed constraints",
        "",
        "- No model was executed.",
        "- Gold was not edited.",
        "- Authoritative Candidate ranges were not edited.",
        "- No ProposedChange or accepted Ledger state was written.",
        "- Production integration remains inactive.",
        "- Validation is diagnostic rather than an independent transfer test.",
        "",
        "## Result",
        "",
        f"Outcome: `{report.outcome.value}`.",
        "",
        f"Boundary-normalized Gold changes: `{len(report.normalization_changes)}`.",
        "",
        _metric_line("Development competitive Qwen", report.development.competitive_qwen_metrics),
        "",
        _metric_line("Development primary union", primary_dev.union_metrics),
        "",
        _metric_line("Validation competitive Qwen", report.validation.competitive_qwen_metrics),
        "",
        _metric_line("Validation primary union", primary_val.union_metrics),
        "",
        "## Mechanism evidence",
        "",
        f"Head-aware trigger precision: `{report.head_aware_trigger.precision:.6f}`.",
        "",
        f"Head-aware trigger recall: `{report.head_aware_trigger.recall:.6f}`.",
        "",
        "Repeated occurrence identity preservation: "
        f"`{sum(item.occurrence_identity_preserved for item in report.repeated_occurrences)}/3`.",
        "",
        "Repeated occurrence semantic exactness under the primary policy: "
        f"`{sum(item.semantic_attachment_exact for item in report.repeated_occurrences)}/3`.",
        "",
        "## Evidence package",
        "",
        "Use `report.json` for every exact range, policy metric, and diagnostic observation.",
        "Use `review.md` for the human-readable data-in/data-out review.",
        "Use `manifest.json` to verify the complete input and output digest chain.",
        "",
        f"Result fingerprint: `{report.result_fingerprint}`.",
    ]
    return "\n".join(lines).rstrip() + "\n"


class _PhaseBuild:
    def __init__(
        self,
        *,
        phase_result: AttachmentSelectionPhaseResult,
        comparisons: tuple[AttachmentComparisonRange, ...],
        changes: tuple[AttachmentNormalizationChange, ...],
        normalized_gold: _Predictions,
        primary_predictions: _Predictions,
    ) -> None:
        self.phase_result = phase_result
        self.comparisons = comparisons
        self.changes = changes
        self.normalized_gold = normalized_gold
        self.primary_predictions = primary_predictions


def _build_phase_result(
    *,
    phase: Literal["development", "validation"],
    report: CompetitiveAttachmentPhaseReport,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    original_oracle: _Predictions,
    inputs: tuple[EventEntityExperimentInput, ...],
    observations: tuple[AttachmentSyntaxObservation, ...],
    gold_by_sge: dict[str, PropositionGoldEvent],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
) -> _PhaseBuild:
    source_by_digest = {item.event.source_text_sha256: item.source_text for item in inputs}
    comparisons = tuple(
        sorted(
            (
                normalize_attachment_comparison_range(
                    phase=phase,
                    source_segment_id=matrix.source_segment_id,
                    source_text=source_by_digest[matrix.source_text_sha256],
                    candidate_id=candidate.id,
                    authoritative_start=candidate.start,
                    authoritative_end=candidate.end,
                )
                for matrix in matrices
                for candidate in matrix.candidates
            ),
            key=lambda item: (item.source_text_sha256, item.candidate_id),
        )
    )
    comparison_by_id = {item.candidate_id: item for item in comparisons}
    normalized_gold = _normalized_gold_sets(
        matrices=matrices,
        comparisons=comparison_by_id,
        gold_by_sge=gold_by_sge,
        source_by_digest=source_by_digest,
    )
    changes = tuple(
        AttachmentNormalizationChange(
            phase=phase,
            source_segment_id=comparison_by_id[candidate_id].source_segment_id,
            source_text_sha256=comparison_by_id[candidate_id].source_text_sha256,
            source_text=source_by_digest[comparison_by_id[candidate_id].source_text_sha256],
            candidate_id=candidate_id,
            comparison=comparison_by_id[candidate_id],
            original_gold_event_ids=original_oracle[candidate_id],
            normalized_gold_event_ids=normalized,
        )
        for candidate_id, normalized in sorted(normalized_gold.items())
        if original_oracle[candidate_id] != normalized
    )
    qwen = {item.candidate_id: item.competitive_event_ids for item in report.cases}
    baseline = {item.candidate_id: item.baseline_event_ids for item in report.cases}
    qwen_unresolved = {item.candidate_id for item in report.cases if item.competitive_unresolved}
    baseline_unresolved = {
        item.candidate_id for item in report.cases if item.baseline_unresolved_event_ids
    }

    def measure(
        predictions: _Predictions,
        *,
        unresolved: set[str],
        anchor_gaps: int,
    ) -> AttachmentMetricSnapshot:
        return _metric_snapshot(
            matrices=matrices,
            gold_sets=normalized_gold,
            predicted_sets=predictions,
            comparisons=comparison_by_id,
            gold_by_sge=gold_by_sge,
            source_by_digest=source_by_digest,
            entity_occurrences_by_event=entity_occurrences_by_event,
            unresolved_candidate_ids=unresolved,
            anchor_gap_count=anchor_gaps,
        )

    qwen_metrics = measure(qwen, unresolved=qwen_unresolved, anchor_gaps=0)
    baseline_metrics = measure(baseline, unresolved=baseline_unresolved, anchor_gaps=0)
    policies: list[AttachmentPolicyPhaseResult] = []
    prediction_by_policy: dict[str, _Predictions] = {}
    gap_count = sum(item.gap_code is not None for item in observations)
    for policy in attachment_syntax_policies():
        syntax = _syntax_predictions(
            candidate_ids=set(normalized_gold),
            observations=observations,
            policy=policy,
        )
        union = combine_attachment_predictions(qwen, syntax, operation="union")
        intersection = combine_attachment_predictions(qwen, syntax, operation="intersection")
        prediction_by_policy[policy.policy_id] = syntax
        policies.append(
            AttachmentPolicyPhaseResult(
                phase=phase,
                policy=policy,
                syntax_metrics=measure(syntax, unresolved=set(), anchor_gaps=gap_count),
                union_metrics=measure(
                    union,
                    unresolved=qwen_unresolved,
                    anchor_gaps=gap_count,
                ),
                intersection_metrics=measure(
                    intersection,
                    unresolved=qwen_unresolved,
                    anchor_gaps=gap_count,
                ),
                rescue=build_attachment_rescue_metrics(
                    gold_sets=normalized_gold,
                    qwen=qwen,
                    syntax=syntax,
                ),
            )
        )
    primary_syntax = prediction_by_policy[_PRIMARY_POLICY_ID]
    primary_union = combine_attachment_predictions(qwen, primary_syntax, operation="union")
    candidate_source_ceiling = build_candidate_source_oracle(
        gold_sets=normalized_gold,
        qwen=qwen,
        syntax=primary_syntax,
    )
    per_edge_ceiling = build_per_edge_oracle(
        gold_sets=normalized_gold,
        qwen=qwen,
        syntax=primary_syntax,
    )
    ceilings = tuple(
        AttachmentOracleCeiling(
            phase=phase,
            kind=kind,
            policy_id=_PRIMARY_POLICY_ID,
            metrics=measure(predictions, unresolved=set(), anchor_gaps=gap_count),
        )
        for kind, predictions in (
            (AttachmentOracleCeilingKind.CANDIDATE_SOURCE, candidate_source_ceiling),
            (AttachmentOracleCeilingKind.PER_EDGE, per_edge_ceiling),
        )
    )
    return _PhaseBuild(
        phase_result=AttachmentSelectionPhaseResult(
            phase=phase,
            candidate_count=len(normalized_gold),
            prompt_v3_baseline_metrics=baseline_metrics,
            competitive_qwen_metrics=qwen_metrics,
            policies=tuple(policies),
            oracle_ceilings=ceilings,
        ),
        comparisons=comparisons,
        changes=changes,
        normalized_gold=normalized_gold,
        primary_predictions=primary_union,
    )


def _metric_snapshot(
    *,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_sets: _Predictions,
    predicted_sets: _Predictions,
    comparisons: dict[str, AttachmentComparisonRange],
    gold_by_sge: dict[str, PropositionGoldEvent],
    source_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    unresolved_candidate_ids: set[str],
    anchor_gap_count: int,
) -> AttachmentMetricSnapshot:
    if set(gold_sets) != set(predicted_sets) or set(gold_sets) != set(comparisons):
        raise ValueError("Selection metrics require complete Candidate inventories.")
    tp = fp = fn = leakage = exact = 0
    shared_total = shared_matched = 0
    none_total = none_correct = 0
    for candidate_id, gold_ids in gold_sets.items():
        gold = set(gold_ids)
        predicted = set(predicted_sets[candidate_id])
        exact += candidate_id not in unresolved_candidate_ids and gold == predicted
        tp += len(gold & predicted)
        fp += len(predicted - gold)
        fn += len(gold - predicted)
        if gold:
            leakage += len(predicted - gold)
        else:
            none_total += 1
            none_correct += candidate_id not in unresolved_candidate_ids and not predicted
        if len(gold) > 1:
            shared_total += len(gold)
            shared_matched += len(gold & predicted)
    candidate_by_id = {
        candidate.id: candidate for matrix in matrices for candidate in matrix.candidates
    }
    phase_event_ids = tuple(
        sorted(
            {
                option.source_grounded_event_id
                for matrix in matrices
                for option in matrix.event_options
            }
        )
    )
    character_tp = character_fp = character_fn = 0
    exact_events = 0
    entity_total = entity_matched = 0
    qualification_total = qualification_matched = 0
    for event_id in phase_event_ids:
        gold_event = gold_by_sge[event_id]
        source = source_by_digest[gold_event.source_text_sha256]
        required = _positions(
            source,
            tuple((item.start, item.end) for item in gold_event.fragments),
        )
        selected = _positions(
            source,
            tuple(
                (
                    comparisons[candidate_id].comparison_start,
                    comparisons[candidate_id].comparison_end,
                )
                for candidate_id, candidate in candidate_by_id.items()
                if event_id in predicted_sets[candidate_id]
                and candidate.source_text_sha256 == gold_event.source_text_sha256
                and comparisons[candidate_id].comparison_start
                < comparisons[candidate_id].comparison_end
            ),
        )
        character_tp += len(required & selected)
        character_fp += len(selected - required)
        character_fn += len(required - selected)
        exact_events += selected == required
        qualifications = tuple(
            item
            for item in gold_event.fragments
            if any(
                requirement is not PropositionGoldFragmentRequirement.CORE_EVENT
                for requirement in item.requirements
            )
        )
        qualification_total += len(qualifications)
        qualification_matched += sum(
            _positions(source, ((item.start, item.end),)) <= selected for item in qualifications
        )
        occurrences = entity_occurrences_by_event.get(event_id, ())
        entity_total += len(occurrences)
        entity_matched += sum(
            _positions(source, (occurrence,)) <= selected for occurrence in occurrences
        )
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    character_precision = _ratio(character_tp, character_tp + character_fp)
    character_recall = _ratio(character_tp, character_tp + character_fn)
    return AttachmentMetricSnapshot(
        candidate_count=len(gold_sets),
        event_count=len(phase_event_ids),
        exact_set_count=exact,
        exact_set_accuracy=_ratio(exact, len(gold_sets)),
        true_positive_edge_count=tp,
        false_positive_edge_count=fp,
        false_negative_edge_count=fn,
        edge_precision=precision,
        edge_recall=recall,
        edge_f1=_f1(precision, recall),
        sibling_event_leakage_count=leakage,
        shared_gold_edge_count=shared_total,
        shared_matched_edge_count=shared_matched,
        shared_fragment_recall=_ratio(shared_matched, shared_total),
        none_case_count=none_total,
        none_correct_count=none_correct,
        none_accuracy=_ratio(none_correct, none_total),
        exact_event_count=exact_events,
        character_precision=character_precision,
        character_recall=character_recall,
        character_f1=_f1(character_precision, character_recall),
        entity_gold_edge_count=entity_total,
        entity_matched_edge_count=entity_matched,
        entity_recall=_ratio(entity_matched, entity_total),
        qualification_gold_edge_count=qualification_total,
        qualification_matched_edge_count=qualification_matched,
        qualification_recall=_ratio(qualification_matched, qualification_total),
        anchor_gap_count=anchor_gap_count,
    )


def _normalized_gold_sets(
    *,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    comparisons: dict[str, AttachmentComparisonRange],
    gold_by_sge: dict[str, PropositionGoldEvent],
    source_by_digest: dict[str, str],
) -> _Predictions:
    result: _Predictions = {}
    for matrix in matrices:
        source = source_by_digest[matrix.source_text_sha256]
        relevant = tuple(item.source_grounded_event_id for item in matrix.event_options)
        for candidate in matrix.candidates:
            comparison = comparisons[candidate.id]
            candidate_positions = _positions(
                source,
                ((comparison.comparison_start, comparison.comparison_end),),
            )
            result[candidate.id] = tuple(
                sorted(
                    event_id
                    for event_id in relevant
                    if candidate_positions
                    and candidate_positions
                    <= _positions(
                        source,
                        tuple((item.start, item.end) for item in gold_by_sge[event_id].fragments),
                    )
                )
            )
    return result


def _syntax_predictions(
    *,
    candidate_ids: set[str],
    observations: tuple[AttachmentSyntaxObservation, ...],
    policy: AttachmentSyntaxPolicy,
) -> _Predictions:
    result: dict[str, set[str]] = {candidate_id: set() for candidate_id in candidate_ids}
    for observation in observations:
        if observation.candidate_id not in result:
            raise ValueError("Syntax observation references a foreign Candidate.")
        if syntax_policy_supports(observation, policy):
            result[observation.candidate_id].add(observation.source_grounded_event_id)
    return {key: tuple(sorted(value)) for key, value in result.items()}


def combine_attachment_predictions(
    left: _Predictions,
    right: _Predictions,
    *,
    operation: Literal["union", "intersection"],
) -> _Predictions:
    if set(left) != set(right):
        raise ValueError("Attachment prediction inventories differ.")
    return {
        candidate_id: tuple(
            sorted(
                set(left[candidate_id]) | set(right[candidate_id])
                if operation == "union"
                else set(left[candidate_id]) & set(right[candidate_id])
            )
        )
        for candidate_id in left
    }


def build_attachment_rescue_metrics(
    *,
    gold_sets: _Predictions,
    qwen: _Predictions,
    syntax: _Predictions,
) -> AttachmentRescueMetrics:
    qwen_false_negatives = added = rescued = false = 0
    for candidate_id, gold_ids in gold_sets.items():
        gold = set(gold_ids)
        qwen_edges = set(qwen[candidate_id])
        added_edges = set(syntax[candidate_id]) - qwen_edges
        qwen_false_negatives += len(gold - qwen_edges)
        added += len(added_edges)
        rescued += len(added_edges & gold)
        false += len(added_edges - gold)
    return AttachmentRescueMetrics(
        qwen_false_negative_edge_count=qwen_false_negatives,
        added_syntax_edge_count=added,
        rescued_gold_edge_count=rescued,
        added_false_edge_count=false,
        rescue_precision=_ratio(rescued, added),
        qwen_false_negative_coverage=_ratio(rescued, qwen_false_negatives),
    )


def build_candidate_source_oracle(
    *,
    gold_sets: _Predictions,
    qwen: _Predictions,
    syntax: _Predictions,
) -> _Predictions:
    """Choose the lower-error whole source for each Candidate using Gold."""
    if set(gold_sets) != set(qwen) or set(gold_sets) != set(syntax):
        raise ValueError("Attachment Oracle inventories differ.")
    result: _Predictions = {}
    for candidate_id, gold_ids in gold_sets.items():
        gold = set(gold_ids)
        qwen_error = len(set(qwen[candidate_id]) ^ gold)
        syntax_error = len(set(syntax[candidate_id]) ^ gold)
        result[candidate_id] = (
            syntax[candidate_id] if syntax_error < qwen_error else qwen[candidate_id]
        )
    return result


def build_per_edge_oracle(
    *,
    gold_sets: _Predictions,
    qwen: _Predictions,
    syntax: _Predictions,
) -> _Predictions:
    """Build the non-deployable per-edge Gold-selection ceiling."""
    if set(gold_sets) != set(qwen) or set(gold_sets) != set(syntax):
        raise ValueError("Attachment Oracle inventories differ.")
    return {
        candidate_id: tuple(
            sorted((set(qwen[candidate_id]) | set(syntax[candidate_id])) & set(gold))
        )
        for candidate_id, gold in gold_sets.items()
    }


def _head_aware_trigger_summary(
    *,
    review_report: AttachmentReviewVerificationReport,
    normalized_gold: _Predictions,
) -> AttachmentHeadAwareTriggerSummary:
    syntax = {
        (item.candidate_id, item.source_grounded_event_id): item
        for item in (
            *review_report.development.observations,
            *review_report.validation.observations,
        )
    }
    observations: list[AttachmentHeadAwareTriggerObservation] = []
    flagged: set[str] = set()
    gaps: set[str] = set()
    candidates: set[str] = set()
    for item in review_report.trigger_containment.observations:
        candidates.add(item.candidate_id)
        for event_id in item.contained_event_ids:
            path = syntax[(item.candidate_id, event_id)]
            gap_code: Literal["candidate_anchor_missing", "event_anchor_missing"] | None = None
            candidate_anchor = path.candidate_anchor
            event_anchor = path.event_anchor
            if candidate_anchor is None:
                gap_code = "candidate_anchor_missing"
            elif event_anchor is None:
                gap_code = "event_anchor_missing"
            if gap_code is None:
                assert candidate_anchor is not None
                assert event_anchor is not None
                foreign = candidate_anchor.token_id != event_anchor.token_id
            else:
                foreign = None
            if foreign is True:
                flagged.add(item.candidate_id)
            if gap_code is not None:
                gaps.add(item.candidate_id)
            observations.append(
                AttachmentHeadAwareTriggerObservation(
                    phase=item.phase,
                    candidate_id=item.candidate_id,
                    source_grounded_event_id=event_id,
                    candidate_range=item.candidate_range,
                    event_head_range=path.event_head_range,
                    candidate_anchor_token_id=(
                        None if candidate_anchor is None else candidate_anchor.token_id
                    ),
                    event_anchor_token_id=(None if event_anchor is None else event_anchor.token_id),
                    foreign_trigger=foreign,
                    gap_code=gap_code,
                    normalized_gold_none=not normalized_gold[item.candidate_id],
                )
            )
    gold_none = {candidate_id for candidate_id, value in normalized_gold.items() if not value}
    flagged_gold_none = flagged & gold_none
    return AttachmentHeadAwareTriggerSummary(
        observation_count=len(observations),
        candidate_count=len(candidates),
        flagged_candidate_count=len(flagged),
        gap_candidate_count=len(gaps),
        normalized_gold_none_count=len(gold_none),
        flagged_gold_none_count=len(flagged_gold_none),
        precision=_ratio(len(flagged_gold_none), len(flagged)),
        recall=_ratio(len(flagged_gold_none), len(gold_none)),
        observations=tuple(
            sorted(
                observations,
                key=lambda value: (
                    value.phase,
                    value.candidate_id,
                    value.source_grounded_event_id,
                ),
            )
        ),
    )


def _outcome(
    *,
    development: AttachmentSelectionPhaseResult,
    validation: AttachmentSelectionPhaseResult,
) -> AttachmentSelectionOutcome:
    development_primary = _primary(development).union_metrics
    validation_primary = _primary(validation).union_metrics
    development_improved = development_primary.exact_set_accuracy > (
        development.competitive_qwen_metrics.exact_set_accuracy
    )
    validation_improved = validation_primary.exact_set_accuracy > (
        validation.competitive_qwen_metrics.exact_set_accuracy
    )
    protected = all(
        _protected_recall_preserved(_primary(phase).union_metrics, phase.competitive_qwen_metrics)
        for phase in (development, validation)
    )
    if development_improved and validation_improved and protected:
        return AttachmentSelectionOutcome.SUPPORTED
    oracle_headroom = any(
        ceiling.metrics.exact_set_accuracy > phase.competitive_qwen_metrics.exact_set_accuracy
        for phase in (development, validation)
        for ceiling in phase.oracle_ceilings
    )
    if development_improved or validation_improved or oracle_headroom:
        return AttachmentSelectionOutcome.MIXED
    return AttachmentSelectionOutcome.FALSIFIED


def _protected_recall_preserved(
    candidate: AttachmentMetricSnapshot,
    baseline: AttachmentMetricSnapshot,
) -> bool:
    return (
        candidate.entity_recall >= baseline.entity_recall
        and candidate.qualification_recall >= baseline.qualification_recall
        and candidate.shared_fragment_recall >= baseline.shared_fragment_recall
        and candidate.character_recall >= baseline.character_recall
    )


def _primary(phase: AttachmentSelectionPhaseResult) -> AttachmentPolicyPhaseResult:
    return next(item for item in phase.policies if item.policy.policy_id == _PRIMARY_POLICY_ID)


def _phase_summary(phase: AttachmentSelectionPhaseResult) -> dict[str, object]:
    primary = _primary(phase)
    return {
        "competitive_qwen": phase.competitive_qwen_metrics.model_dump(mode="json"),
        "primary_union": primary.union_metrics.model_dump(mode="json"),
        "primary_rescue": primary.rescue.model_dump(mode="json"),
        "oracle_ceilings": [item.model_dump(mode="json") for item in phase.oracle_ceilings],
    }


def _validate_inventory(
    *,
    development_report: CompetitiveAttachmentPhaseReport,
    development_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    development_inputs: tuple[EventEntityExperimentInput, ...],
    validation_report: CompetitiveAttachmentPhaseReport,
    validation_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    validation_inputs: tuple[EventEntityExperimentInput, ...],
    review_report: AttachmentReviewVerificationReport,
) -> None:
    observed = (
        development_report.phase,
        development_report.metrics.candidate_count,
        sum(len(item.candidates) for item in development_matrices),
        len(development_inputs),
        validation_report.phase,
        validation_report.metrics.candidate_count,
        sum(len(item.candidates) for item in validation_matrices),
        len(validation_inputs),
        len(review_report.development.candidates),
        len(review_report.validation.candidates),
    )
    expected = ("development", 162, 162, 20, "validation", 179, 179, 20, 162, 179)
    if observed != expected:
        raise ValueError(f"CEA-1.3 frozen inventory drifted: {observed!r}.")
    if review_report.model_execution_count != 0:
        raise ValueError("CEA-1.3 predecessor review unexpectedly executed a model.")


def _gold_by_source_grounded_event(
    *,
    catalog: PropositionGoldCatalog,
    development_bindings: _Bindings,
    validation_bindings: _Bindings,
) -> dict[str, PropositionGoldEvent]:
    bindings = {**development_bindings, **validation_bindings}
    if set(bindings) != {item.event_id for item in catalog.events}:
        raise ValueError("CEA-1.3 Gold bindings do not cover forty Events.")
    return {bindings[item.event_id]: item for item in catalog.events}


def _gold_sets(oracle: _Oracle) -> _Predictions:
    result: _Predictions = {}
    for decisions in oracle.values():
        for value in decisions:
            result[value.candidate_id] = tuple(sorted(value.source_grounded_event_ids))
    return result


def _positions(source: str, ranges: tuple[tuple[int, int], ...]) -> set[int]:
    result: set[int] = set()
    for start, end in ranges:
        if not (0 <= start <= end <= len(source)):
            raise ValueError("Attachment comparison range leaves its SourceSegment.")
        result.update(index for index in range(start, end) if not source[index].isspace())
    return result


def _source_occurrence_count(source: str, text: str) -> int:
    return source.count(text)


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _ids(values: tuple[str, ...]) -> str:
    return ", ".join(values) or "NONE"


def _metric_line(label: str, metrics: AttachmentMetricSnapshot) -> str:
    return (
        f"{label}: exact-set `{metrics.exact_set_accuracy:.6f}`, "
        f"edge precision `{metrics.edge_precision:.6f}`, "
        f"edge recall `{metrics.edge_recall:.6f}`, "
        f"edge F1 `{metrics.edge_f1:.6f}`, "
        f"NONE `{metrics.none_accuracy:.6f}`, "
        f"leakage `{metrics.sibling_event_leakage_count}`, "
        f"entity recall `{metrics.entity_recall:.6f}`, "
        f"qualification recall `{metrics.qualification_recall:.6f}`, "
        f"character recall `{metrics.character_recall:.6f}`."
    )


def canonical_attachment_selection_json(value: object) -> bytes:
    """Serialize one CEA-1.3 boundary value canonically."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
