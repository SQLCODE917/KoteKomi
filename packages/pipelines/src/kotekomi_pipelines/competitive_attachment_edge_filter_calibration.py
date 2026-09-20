"""Deterministic CEA-1.5 probability calibration and aggregate evaluation."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Literal

from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentBinaryMetrics,
    AttachmentCalibratedEdgeDecision,
    AttachmentCalibrationArmResult,
    AttachmentCalibrationDiagnosticOutcome,
    AttachmentCalibrationObservation,
    AttachmentCalibrationOutcome,
    AttachmentCalibrationPhaseResult,
    AttachmentCalibrationPromptArm,
    AttachmentCalibrationPromptResult,
    AttachmentCalibrationThresholdEvaluation,
    AttachmentComparisonRange,
    AttachmentEdgeFilterAnswerValue,
    AttachmentExpectedExactCandidate,
    AttachmentExpectedExactProfile,
    AttachmentMetricSnapshot,
    AttachmentPoolArm,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    CompetitiveAttachmentMatrix,
    ModelExecutionReceipt,
    attachment_calibration_fingerprint,
    parse_attachment_edge_filter_answer,
)

from kotekomi_pipelines.competitive_attachment_edge_filter import (
    measure_attachment_edge_filter_predictions,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldEvent,
)

type AttachmentPredictions = dict[str, tuple[str, ...]]


def attachment_answer_probability(
    receipt: ModelExecutionReceipt,
    *,
    emitted_answer: AttachmentEdgeFilterAnswerValue,
) -> AttachmentAnswerProbability:
    """Map first meaningful runtime token alternatives into canonical Y/N/U evidence."""
    for item in receipt.output_token_probabilities:
        try:
            emitted = parse_attachment_edge_filter_answer(item.token.encode("utf-8"))
        except ValueError:
            if not item.token.strip():
                continue
            raise ValueError(
                "Output probability evidence precedes the finite answer with a foreign token."
            ) from None
        if emitted is not emitted_answer:
            raise ValueError("Probability evidence emitted answer differs from raw output.")
        grouped: dict[AttachmentEdgeFilterAnswerValue, list[float]] = defaultdict(list)
        for alternative in item.alternatives:
            try:
                answer = parse_attachment_edge_filter_answer(alternative.token.encode("utf-8"))
            except ValueError:
                continue
            grouped[answer].append(alternative.log_probability)
        missing = tuple(answer for answer in AttachmentEdgeFilterAnswerValue if not grouped[answer])
        if missing:
            raise ValueError(
                "Output probability evidence does not contain every Y/N/U alternative: "
                + ", ".join(item.value for item in missing)
                + "."
            )
        yes_mass = _logsumexp(tuple(grouped[AttachmentEdgeFilterAnswerValue.YES]))
        no_mass = _logsumexp(tuple(grouped[AttachmentEdgeFilterAnswerValue.NO]))
        unclear_mass = _logsumexp(tuple(grouped[AttachmentEdgeFilterAnswerValue.UNCLEAR]))
        finite_answer_mass = _logsumexp((yes_mass, no_mass, unclear_mass))
        yes = yes_mass - finite_answer_mass
        no = no_mass - finite_answer_mass
        unclear = unclear_mass - finite_answer_mass
        return AttachmentAnswerProbability(
            token_position=item.position,
            emitted_answer=emitted,
            yes_log_probability=yes,
            no_log_probability=no,
            unclear_log_probability=unclear,
            attachment_score=yes - _logsumexp((no, unclear)),
        )
    raise ValueError("Output probability evidence contains no finite Y/N/U answer token.")


def build_expected_exact_profile(
    *,
    phase: Literal["development", "validation"],
    edges: tuple[AttachmentPoolEdge, ...],
    gold_sets: AttachmentPredictions,
    baseline_exact_set_accuracy: float,
) -> AttachmentExpectedExactProfile:
    """Describe the exact-set feasibility surface without assuming model performance."""
    edges_by_candidate: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        edges_by_candidate[edge.candidate_id].add(edge.source_grounded_event_id)
    candidates = tuple(
        AttachmentExpectedExactCandidate(
            candidate_id=candidate_id,
            true_edge_count=len(set(gold_event_ids) & edges_by_candidate[candidate_id]),
            false_edge_count=len(edges_by_candidate[candidate_id] - set(gold_event_ids)),
            missing_gold_edge_count=len(set(gold_event_ids) - edges_by_candidate[candidate_id]),
        )
        for candidate_id, gold_event_ids in sorted(gold_sets.items())
    )
    return AttachmentExpectedExactProfile(
        phase=phase,
        baseline_exact_set_accuracy=baseline_exact_set_accuracy,
        candidates=candidates,
    )


def expected_exact_set_accuracy(
    profile: AttachmentExpectedExactProfile,
    *,
    sensitivity: float,
    specificity: float,
) -> float:
    """Apply the declared homogeneous-independent feasibility model."""
    if not 0 <= sensitivity <= 1 or not 0 <= specificity <= 1:
        raise ValueError("Expected-exact sensitivity and specificity must be probabilities.")
    exact_probability = 0.0
    for candidate in profile.candidates:
        if candidate.missing_gold_edge_count:
            continue
        exact_probability += sensitivity**candidate.true_edge_count * (
            specificity**candidate.false_edge_count
        )
    return exact_probability / len(profile.candidates)


def binary_metrics(
    observations: tuple[AttachmentCalibrationObservation, ...],
    *,
    threshold: float,
) -> AttachmentBinaryMetrics:
    """Measure one finite score threshold against occurrence-level Gold edges."""
    if not observations or not math.isfinite(threshold):
        raise ValueError("Binary metrics require observations and a finite threshold.")
    tp = fp = tn = fn = 0
    for item in observations:
        retained = item.probability.attachment_score >= threshold
        if item.expected_answer == "Y" and retained:
            tp += 1
        elif item.expected_answer == "Y":
            fn += 1
        elif retained:
            fp += 1
        else:
            tn += 1
    sensitivity = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    precision = _ratio(tp, tp + fp)
    return AttachmentBinaryMetrics(
        true_positive_count=tp,
        false_positive_count=fp,
        true_negative_count=tn,
        false_negative_count=fn,
        sensitivity=sensitivity,
        specificity=specificity,
        precision=precision,
        f1=_f1(precision, sensitivity),
        accuracy=_ratio(tp + tn, len(observations)),
    )


def attachment_score_auroc(
    observations: tuple[AttachmentCalibrationObservation, ...],
) -> float:
    """Return tie-aware pairwise AUROC for one repetition."""
    positive = tuple(
        item.probability.attachment_score for item in observations if item.expected_answer == "Y"
    )
    negative = tuple(
        item.probability.attachment_score for item in observations if item.expected_answer == "N"
    )
    if not positive or not negative:
        raise ValueError("AUROC requires positive and negative observations.")
    credit = sum(
        1.0 if yes > no else 0.5 if yes == no else 0.0 for yes in positive for no in negative
    )
    return credit / (len(positive) * len(negative))


def attachment_score_average_precision(
    observations: tuple[AttachmentCalibrationObservation, ...],
) -> float:
    """Return tie-grouped average precision for one repetition."""
    positive_count = sum(item.expected_answer == "Y" for item in observations)
    if not positive_count:
        raise ValueError("Average precision requires positive observations.")
    by_score: dict[float, list[AttachmentCalibrationObservation]] = defaultdict(list)
    for item in observations:
        by_score[item.probability.attachment_score].append(item)
    seen = true_positive = 0
    result = 0.0
    for score in sorted(by_score, reverse=True):
        group = by_score[score]
        group_positive = sum(item.expected_answer == "Y" for item in group)
        seen += len(group)
        true_positive += group_positive
        result += _ratio(true_positive, seen) * _ratio(group_positive, positive_count)
    return result


def build_calibration_prompt_result(
    *,
    prompt_arm: AttachmentCalibrationPromptArm,
    prompt_sha256: str,
    observations: tuple[AttachmentCalibrationObservation, ...],
    development_profile: AttachmentExpectedExactProfile,
    validation_profile: AttachmentExpectedExactProfile,
) -> AttachmentCalibrationPromptResult:
    """Select a diagnostic threshold only when safety and break-even gates pass."""
    repetitions = (
        tuple(item for item in observations if item.repetition == 1),
        tuple(item for item in observations if item.repetition == 2),
    )
    if any(len(items) != 16 for items in repetitions):
        raise ValueError("Calibration requires sixteen observations in both repetitions.")
    expected_keys = tuple((item.task_id, item.expected_answer) for item in repetitions[0])
    if tuple((item.task_id, item.expected_answer) for item in repetitions[1]) != expected_keys:
        raise ValueError("Calibration repetitions do not cover the same ordered tasks.")
    evaluations = tuple(
        _threshold_evaluation(
            threshold,
            repetitions=repetitions,
            development_profile=development_profile,
            validation_profile=validation_profile,
        )
        for threshold in _threshold_candidates(observations)
    )
    safe = tuple(
        item
        for item in evaluations
        if item.protected_positive_retained and item.hard_negative_rejected
    )
    eligible = tuple(item for item in safe if item.clears_break_even)
    selected = (
        max(
            eligible,
            key=lambda item: (
                sum(metric.accuracy for metric in item.repetition_metrics),
                sum(metric.f1 for metric in item.repetition_metrics),
                _threshold_margin(observations, item.threshold),
                item.threshold,
            ),
        )
        if eligible
        else None
    )
    ranking_stable = _score_ranking_stable(repetitions)
    if not ranking_stable:
        outcome = AttachmentCalibrationDiagnosticOutcome.RANKING_UNSTABLE
    elif not safe:
        outcome = AttachmentCalibrationDiagnosticOutcome.NOT_SEPARABLE
    elif selected is None:
        outcome = AttachmentCalibrationDiagnosticOutcome.INCONCLUSIVE
    else:
        outcome = AttachmentCalibrationDiagnosticOutcome.CALIBRATABLE
    if outcome is not AttachmentCalibrationDiagnosticOutcome.CALIBRATABLE:
        selected = None
    draft = AttachmentCalibrationPromptResult.model_construct(
        prompt_arm=prompt_arm,
        prompt_sha256=prompt_sha256,
        observations=observations,
        repetition_auroc=tuple(attachment_score_auroc(items) for items in repetitions),
        repetition_average_precision=tuple(
            attachment_score_average_precision(items) for items in repetitions
        ),
        selected_threshold=selected,
        score_ranking_stable=ranking_stable,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentCalibrationPromptResult(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_calibration_fingerprint(draft),
    )


def build_calibrated_phase_result(
    *,
    phase: Literal["development", "validation"],
    prompt_arm: AttachmentCalibrationPromptArm,
    prompt_sha256: str,
    threshold: float,
    observations: tuple[AttachmentCalibrationObservation, ...],
    edges: tuple[AttachmentPoolEdge, ...],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_sets: AttachmentPredictions,
    comparisons: dict[str, AttachmentComparisonRange],
    gold_by_event_id: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    baseline_metrics: AttachmentMetricSnapshot,
    frozen_selected_arm: AttachmentPoolArm | None = None,
) -> AttachmentCalibrationPhaseResult:
    """Apply one threshold without changing any preserved model answer."""
    if len(observations) != len(edges):
        raise ValueError("Calibrated phase requires one observation per Maximum-Pool edge.")
    by_edge = {item.edge_id: item for item in observations}
    if set(by_edge) != {item.id for item in edges}:
        raise ValueError("Calibrated observations do not cover the Maximum Pool exactly.")
    decisions = tuple(
        AttachmentCalibratedEdgeDecision(
            edge_id=edge.id,
            model_answer=by_edge[edge.id].probability.emitted_answer,
            probability=by_edge[edge.id].probability,
            threshold=threshold,
            retained=by_edge[edge.id].probability.attachment_score >= threshold,
        )
        for edge in edges
    )
    retained_by_edge = {item.edge_id: item.retained for item in decisions}
    candidate_ids = tuple(sorted(gold_sets))
    arm_results: list[AttachmentCalibrationArmResult] = []
    for arm in AttachmentPoolArm:
        arm_edges = tuple(
            edge
            for edge in edges
            if AttachmentProposalOrigin.QWEN in edge.origins or arm in edge.syntax_arms
        )
        predicted = {
            candidate_id: tuple(
                sorted(
                    edge.source_grounded_event_id
                    for edge in arm_edges
                    if edge.candidate_id == candidate_id and retained_by_edge[edge.id]
                )
            )
            for candidate_id in candidate_ids
        }
        arm_results.append(
            AttachmentCalibrationArmResult(
                arm=arm,
                edge_count=len(arm_edges),
                retained_edge_count=sum(retained_by_edge[item.id] for item in arm_edges),
                metrics=measure_attachment_edge_filter_predictions(
                    matrices=matrices,
                    gold_sets=gold_sets,
                    predicted_sets=predicted,
                    comparisons=comparisons,
                    gold_by_event_id=gold_by_event_id,
                    source_text_by_digest=source_text_by_digest,
                    entity_occurrences_by_event=entity_occurrences_by_event,
                ),
            )
        )
    arms = tuple(arm_results)
    selected_arm = (
        frozen_selected_arm
        or max(
            arms,
            key=lambda item: (
                item.metrics.exact_set_accuracy,
                item.metrics.edge_f1,
                -item.metrics.sibling_event_leakage_count,
                -item.edge_count,
            ),
        ).arm
    )
    draft = AttachmentCalibrationPhaseResult.model_construct(
        phase=phase,
        prompt_arm=prompt_arm,
        prompt_sha256=prompt_sha256,
        threshold=threshold,
        decisions=decisions,
        arms=arms,
        baseline_name="cea13_primary",
        baseline_metrics=baseline_metrics,
        selected_arm=selected_arm,
        result_fingerprint="0" * 64,
    )
    return AttachmentCalibrationPhaseResult(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_calibration_fingerprint(draft),
    )


def select_development_calibration(
    *,
    prompt_arm: AttachmentCalibrationPromptArm,
    prompt_sha256: str,
    observations: tuple[AttachmentCalibrationObservation, ...],
    edges: tuple[AttachmentPoolEdge, ...],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_sets: AttachmentPredictions,
    comparisons: dict[str, AttachmentComparisonRange],
    gold_by_event_id: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    protected_baseline: AttachmentMetricSnapshot,
) -> AttachmentCalibrationPhaseResult:
    """Freeze the best safe development threshold using the preregistered tie-breaks."""
    candidates: list[AttachmentCalibrationPhaseResult] = []
    for threshold in _threshold_candidates(observations):
        result = build_calibrated_phase_result(
            phase="development",
            prompt_arm=prompt_arm,
            prompt_sha256=prompt_sha256,
            threshold=threshold,
            observations=observations,
            edges=edges,
            matrices=matrices,
            gold_sets=gold_sets,
            comparisons=comparisons,
            gold_by_event_id=gold_by_event_id,
            source_text_by_digest=source_text_by_digest,
            entity_occurrences_by_event=entity_occurrences_by_event,
            baseline_metrics=protected_baseline,
        )
        selected = next(item for item in result.arms if item.arm is result.selected_arm)
        if _protected_recall_preserved(selected.metrics, protected_baseline):
            candidates.append(result)
    if not candidates:
        raise ValueError("No development calibration preserves protected recall.")
    return max(
        candidates,
        key=lambda result: _phase_selection_key(result),
    )


def attachment_calibration_outcome(
    development: AttachmentCalibrationPhaseResult,
    validation: AttachmentCalibrationPhaseResult,
) -> AttachmentCalibrationOutcome:
    """Classify aggregate transfer without activating production."""
    if (
        development.phase != "development"
        or validation.phase != "validation"
        or development.prompt_arm is not validation.prompt_arm
        or development.prompt_sha256 != validation.prompt_sha256
        or development.threshold != validation.threshold
        or development.selected_arm is not validation.selected_arm
    ):
        raise ValueError("Calibration validation did not preserve the frozen contract.")
    results = tuple(
        next(item for item in phase.arms if item.arm is phase.selected_arm)
        for phase in (development, validation)
    )
    baselines = (development.baseline_metrics, validation.baseline_metrics)
    improvement = tuple(
        result.metrics.exact_set_accuracy > baseline.exact_set_accuracy
        and result.metrics.edge_precision > baseline.edge_precision
        and result.metrics.sibling_event_leakage_count < baseline.sibling_event_leakage_count
        for result, baseline in zip(results, baselines, strict=True)
    )
    safety = tuple(
        _protected_recall_preserved(result.metrics, baseline)
        for result, baseline in zip(results, baselines, strict=True)
    )
    if all(improvement) and all(safety):
        return AttachmentCalibrationOutcome.SUPPORTED
    if any(improvement) or any(safety):
        return AttachmentCalibrationOutcome.MIXED
    return AttachmentCalibrationOutcome.FALSIFIED


def _threshold_evaluation(
    threshold: float,
    *,
    repetitions: tuple[
        tuple[AttachmentCalibrationObservation, ...],
        tuple[AttachmentCalibrationObservation, ...],
    ],
    development_profile: AttachmentExpectedExactProfile,
    validation_profile: AttachmentExpectedExactProfile,
) -> AttachmentCalibrationThresholdEvaluation:
    metrics = (
        binary_metrics(repetitions[0], threshold=threshold),
        binary_metrics(repetitions[1], threshold=threshold),
    )
    development = (
        expected_exact_set_accuracy(
            development_profile,
            sensitivity=metrics[0].sensitivity,
            specificity=metrics[0].specificity,
        ),
        expected_exact_set_accuracy(
            development_profile,
            sensitivity=metrics[1].sensitivity,
            specificity=metrics[1].specificity,
        ),
    )
    validation = (
        expected_exact_set_accuracy(
            validation_profile,
            sensitivity=metrics[0].sensitivity,
            specificity=metrics[0].specificity,
        ),
        expected_exact_set_accuracy(
            validation_profile,
            sensitivity=metrics[1].sensitivity,
            specificity=metrics[1].specificity,
        ),
    )
    return AttachmentCalibrationThresholdEvaluation(
        threshold=threshold,
        repetition_metrics=metrics,
        development_expected_exact_accuracy=development,
        validation_expected_exact_accuracy=validation,
        protected_positive_retained=all(
            item.probability.attachment_score >= threshold
            for values in repetitions
            for item in values
            if item.protected_positive
        ),
        hard_negative_rejected=all(
            item.probability.attachment_score < threshold
            for values in repetitions
            for item in values
            if item.hard_negative
        ),
        clears_break_even=all(
            value > profile.baseline_exact_set_accuracy
            for profile, values in (
                (development_profile, development),
                (validation_profile, validation),
            )
            for value in values
        ),
    )


def _threshold_candidates(
    observations: tuple[AttachmentCalibrationObservation, ...],
) -> tuple[float, ...]:
    scores = tuple(sorted({item.probability.attachment_score for item in observations}))
    if not scores:
        raise ValueError("Threshold selection requires score observations.")
    return (
        scores[0] - 1.0,
        *(left + (right - left) / 2 for left, right in zip(scores, scores[1:], strict=False)),
        scores[-1] + 1.0,
    )


def _score_ranking_stable(
    repetitions: tuple[
        tuple[AttachmentCalibrationObservation, ...],
        tuple[AttachmentCalibrationObservation, ...],
    ],
) -> bool:
    first = {item.task_id: item.probability.attachment_score for item in repetitions[0]}
    second = {item.task_id: item.probability.attachment_score for item in repetitions[1]}
    expected = {item.task_id: item.expected_answer for item in repetitions[0]}
    identifiers = tuple(sorted(first))
    return all(
        _sign(first[left] - first[right]) == _sign(second[left] - second[right])
        for index, left in enumerate(identifiers)
        for right in identifiers[index + 1 :]
        if expected[left] != expected[right]
    )


def _threshold_margin(
    observations: tuple[AttachmentCalibrationObservation, ...], threshold: float
) -> float:
    return min(abs(item.probability.attachment_score - threshold) for item in observations)


def _phase_selection_key(
    result: AttachmentCalibrationPhaseResult,
) -> tuple[float, float, int, float]:
    selected = next(item for item in result.arms if item.arm is result.selected_arm)
    return (
        selected.metrics.exact_set_accuracy,
        selected.metrics.edge_f1,
        -selected.metrics.sibling_event_leakage_count,
        result.threshold,
    )


def _protected_recall_preserved(
    candidate: AttachmentMetricSnapshot,
    baseline: AttachmentMetricSnapshot,
) -> bool:
    return (
        candidate.entity_recall >= baseline.entity_recall
        and candidate.qualification_recall >= baseline.qualification_recall
        and candidate.shared_fragment_recall >= baseline.shared_fragment_recall
        and candidate.character_recall >= baseline.character_recall
        and candidate.none_accuracy >= baseline.none_accuracy
    )


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _logsumexp(values: tuple[float, ...]) -> float:
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))
