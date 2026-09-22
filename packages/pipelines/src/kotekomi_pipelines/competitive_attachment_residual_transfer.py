"""Deterministic calibration and reporting for CEA-1.17."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Sequence
from itertools import pairwise
from typing import Literal, cast

from kotekomi_application import (
    AttachmentBinaryMetrics,
    AttachmentEvidenceReference,
    AttachmentResidualOwnershipTask,
    AttachmentResidualTransferCase,
    AttachmentResidualTransferGoldCase,
    AttachmentResidualTransferObservation,
    AttachmentResidualTransferOutcome,
    AttachmentResidualTransferPhaseReport,
    AttachmentResidualTransferPreflight,
    AttachmentResidualTransferReport,
    attachment_ownership_remainder_ranges,
    attachment_residual_transfer_fingerprint,
)


def select_residual_transfer_threshold(
    observations: tuple[AttachmentResidualTransferObservation, ...],
) -> float:
    """Select one development threshold by accuracy, specificity, F1, margin, then value."""
    scores = sorted({item.evidence.attachment_score for item in observations})
    if len(scores) < 2:
        raise ValueError("Residual transfer calibration requires distinct scores.")
    candidates = tuple((left + right) / 2 for left, right in pairwise(scores))
    return max(
        candidates,
        key=lambda threshold: (
            sum(
                _score_metrics(observations, threshold, repetition).accuracy
                for repetition in (1, 2)
            ),
            sum(
                _score_metrics(observations, threshold, repetition).specificity
                for repetition in (1, 2)
            ),
            sum(_score_metrics(observations, threshold, repetition).f1 for repetition in (1, 2)),
            min(abs(item.evidence.attachment_score - threshold) for item in observations),
            threshold,
        ),
    )


def build_residual_transfer_phase(
    *,
    phase: str,
    tasks: tuple[AttachmentResidualOwnershipTask, ...],
    gold: tuple[AttachmentResidualTransferGoldCase, ...],
    observations: tuple[AttachmentResidualTransferObservation, ...],
    threshold: float,
) -> AttachmentResidualTransferPhaseReport:
    """Build one occurrence-level phase report from exact observations."""
    if phase not in {"development", "validation"}:
        raise ValueError("Residual transfer phase is unknown.")
    gold_by_id = {item.task_id: item for item in gold if item.phase == phase}
    if set(gold_by_id) != {item.id for item in tasks}:
        raise ValueError("Residual transfer Gold does not cover its task phase exactly.")
    by_task: dict[str, list[AttachmentResidualTransferObservation]] = defaultdict(list)
    for item in observations:
        by_task[item.task_id].append(item)
    cases: list[AttachmentResidualTransferCase] = []
    for task in sorted(tasks, key=lambda item: item.id):
        values = tuple(sorted(by_task[task.id], key=lambda item: item.repetition))
        if len(values) != 2 or any(
            item.expected_answer != gold_by_id[task.id].expected_answer for item in values
        ):
            raise ValueError("Residual transfer observation inventory drifted.")
        literal = cast(
            tuple[Literal["Y", "N", "U"], Literal["Y", "N", "U"]],
            tuple(item.decision.answer.value for item in values if item.decision.answer),
        )
        threshold_answers = cast(
            tuple[Literal["Y", "N"], Literal["Y", "N"]],
            tuple("Y" if item.evidence.attachment_score >= threshold else "N" for item in values),
        )
        displayed, omitted = attachment_ownership_remainder_ranges(task)
        cases.append(
            AttachmentResidualTransferCase(
                task=task,
                gold=gold_by_id[task.id],
                displayed_remainder_ranges=displayed,
                omitted_remainder_ranges=omitted,
                observations=values,
                literal_answers=literal,
                threshold_answers=threshold_answers,
                stable=literal[0] == literal[1] and threshold_answers[0] == threshold_answers[1],
            )
        )
    typed_phase = "development" if phase == "development" else "validation"
    return AttachmentResidualTransferPhaseReport(
        phase=typed_phase,
        threshold=threshold,
        cases=tuple(cases),
        literal_metrics=(
            _literal_metrics(observations, 1),
            _literal_metrics(observations, 2),
        ),
        threshold_metrics=(
            _score_metrics(observations, threshold, 1),
            _score_metrics(observations, threshold, 2),
        ),
        auroc=(_auroc(observations, 1), _auroc(observations, 2)),
        average_precision=(
            _average_precision(observations, 1),
            _average_precision(observations, 2),
        ),
        strict_observation_count=sum(item.strict_finite_answer for item in observations),
        stable_case_count=sum(item.stable for item in cases),
    )


def build_residual_transfer_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
    gold: tuple[AttachmentResidualTransferGoldCase, ...],
    development: AttachmentResidualTransferPhaseReport,
    validation_tasks: tuple[AttachmentResidualOwnershipTask, ...],
    expected_model_identity_digest: str,
) -> AttachmentResidualTransferPreflight:
    """Freeze development calibration before validation execution."""
    draft = AttachmentResidualTransferPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=prompt,
        gold=tuple(sorted(gold, key=lambda item: (item.phase, item.task_id))),
        development=development,
        validation_tasks=tuple(sorted(validation_tasks, key=lambda item: item.id)),
        expected_model_identity_digest=expected_model_identity_digest,
        selected_threshold=development.threshold,
        result_fingerprint="0" * 64,
    )
    return AttachmentResidualTransferPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_residual_transfer_fingerprint(draft),
    )


def build_residual_transfer_report(
    *,
    preflight: AttachmentResidualTransferPreflight,
    inputs: tuple[AttachmentEvidenceReference, ...],
    validation: AttachmentResidualTransferPhaseReport,
) -> AttachmentResidualTransferReport:
    """Classify frozen validation evidence without altering calibration."""
    outcome = classify_residual_transfer_outcome(validation)
    draft = AttachmentResidualTransferReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        preflight_fingerprint=preflight.result_fingerprint,
        development=preflight.development,
        validation=validation,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentResidualTransferReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_residual_transfer_fingerprint(draft),
    )


def classify_residual_transfer_outcome(
    validation: AttachmentResidualTransferPhaseReport,
) -> AttachmentResidualTransferOutcome:
    """Apply the complete CEA-1.17 terminal-outcome contract."""
    strict_complete = (
        validation.strict_observation_count == 14 and validation.stable_case_count == 7
    )
    threshold_ok = all(item.accuracy >= 6 / 7 for item in validation.threshold_metrics)
    negatives_rejected = all(
        item.false_positive_count == 0 for item in validation.threshold_metrics
    )
    non_regression = all(
        calibrated.accuracy >= literal.accuracy
        for calibrated, literal in zip(
            validation.threshold_metrics, validation.literal_metrics, strict=True
        )
    )
    if not strict_complete:
        return AttachmentResidualTransferOutcome.INCONCLUSIVE
    if threshold_ok and negatives_rejected and non_regression:
        return AttachmentResidualTransferOutcome.SUPPORTED
    if not negatives_rejected or not non_regression:
        return AttachmentResidualTransferOutcome.FALSIFIED
    return AttachmentResidualTransferOutcome.MIXED


def render_residual_transfer_review(report: AttachmentResidualTransferReport) -> str:
    """Render exact validation data-in/data-out plus compact phase metrics."""
    lines = [
        "# CEA-1.17 Residual Ownership Transfer Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Frozen threshold: `{report.development.threshold}`",
        "",
        _metric_line("Development literal", report.development.literal_metrics),
        "",
        _metric_line("Development threshold", report.development.threshold_metrics),
        "",
        _metric_line("Validation literal", report.validation.literal_metrics),
        "",
        _metric_line("Validation threshold", report.validation.threshold_metrics),
        "",
        f"Validation AUROC: `{report.validation.auroc}`",
        "",
        f"Validation average precision: `{report.validation.average_precision}`",
        "",
    ]
    for case in report.validation.cases:
        task = case.task.edge_filter_task
        lines.extend(
            [
                f"## {case.task.id}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {task.source_text}",
                "",
                f"Candidate: `{json.dumps(task.candidate.text, ensure_ascii=False)}`",
                "",
                f"Target Event: `{json.dumps(task.edge.event_range.text, ensure_ascii=False)}`",
                "",
                f"Expected: `{case.gold.expected_answer}`",
                "",
                f"Rationale: {case.gold.rationale}",
                "",
                "Displayed Remainders:",
                "",
                *[
                    f"- `{json.dumps(item.text, ensure_ascii=False)}`"
                    for item in case.displayed_remainder_ranges
                ],
                "",
                "Omitted Remainders:",
                "",
                *(
                    [
                        f"- `{json.dumps(item.text, ensure_ascii=False)}`"
                        for item in case.omitted_remainder_ranges
                    ]
                    or ["- none"]
                ),
                "",
            ]
        )
        for item, threshold_answer in zip(case.observations, case.threshold_answers, strict=True):
            probabilities = (
                item.evidence.yes_log_probability,
                item.evidence.no_log_probability,
                item.evidence.unclear_log_probability,
            )
            lines.extend(
                [
                    f"Repetition {item.repetition}",
                    "",
                    "~~~~text",
                    item.exact_model_input,
                    "~~~~",
                    "",
                    f"Raw output: `{json.dumps(item.raw_output_text)}`",
                    "",
                    f"Finite-label argmax: `{item.evidence.finite_label_argmax.value}`",
                    "",
                    f"Y/N/U log probabilities: `{probabilities}`",
                    "",
                    f"Attachment Score: `{item.evidence.attachment_score}`",
                    "",
                    f"Threshold decision: `{threshold_answer}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_residual_transfer_handoff(
    report: AttachmentResidualTransferReport,
    *,
    prompt_text: str,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render the self-contained independent-review handoff."""
    return "\n".join(
        [
            "# CEA-1.17 Residual Ownership Transfer Handoff",
            "",
            "Review whether the development-frozen Residual Ownership rendering and score "
            "threshold transfer to all seven eligible validation cases.",
            "",
            "The CEA-1.5 Maximum Pool is intentionally excluded because it mixes task shapes "
            "outside Residual Ownership.",
            "",
            render_residual_transfer_review(report).rstrip(),
            "",
            "## Exact prompt",
            "",
            "~~~~text",
            prompt_text,
            "~~~~",
            "",
            "## Package files",
            "",
            *[
                f"- `{item.label}`: `{item.path}` (`sha256:{item.sha256}`)"
                for item in sorted(package_files, key=lambda item: item.label)
            ],
            "",
            f"Source repository: {source_repository_url}",
            "",
            f"Source revision: `{source_revision}`",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
            "",
        ]
    )


def _literal_metrics(
    values: tuple[AttachmentResidualTransferObservation, ...], repetition: int
) -> AttachmentBinaryMetrics:
    selected = tuple(item for item in values if item.repetition == repetition)
    return _metrics(
        selected,
        lambda item: item.decision.answer is not None and item.decision.answer.value == "Y",
    )


def _score_metrics(
    values: tuple[AttachmentResidualTransferObservation, ...], threshold: float, repetition: int
) -> AttachmentBinaryMetrics:
    selected = tuple(item for item in values if item.repetition == repetition)
    return _metrics(selected, lambda item: item.evidence.attachment_score >= threshold)


def _metrics(
    values: tuple[AttachmentResidualTransferObservation, ...],
    retained: Callable[[AttachmentResidualTransferObservation], bool],
) -> AttachmentBinaryMetrics:
    tp = fp = tn = false_negative = 0
    for item in values:
        yes = retained(item)
        if item.expected_answer == "Y" and yes:
            tp += 1
        elif item.expected_answer == "Y":
            false_negative += 1
        elif yes:
            fp += 1
        else:
            tn += 1
    sensitivity = _ratio(tp, tp + false_negative)
    precision = _ratio(tp, tp + fp)
    return AttachmentBinaryMetrics(
        true_positive_count=tp,
        false_positive_count=fp,
        true_negative_count=tn,
        false_negative_count=false_negative,
        sensitivity=sensitivity,
        specificity=_ratio(tn, tn + fp),
        precision=precision,
        f1=_ratio(2 * precision * sensitivity, precision + sensitivity),
        accuracy=_ratio(tp + tn, len(values)),
    )


def _auroc(values: tuple[AttachmentResidualTransferObservation, ...], repetition: int) -> float:
    selected = tuple(item for item in values if item.repetition == repetition)
    positive = [item.evidence.attachment_score for item in selected if item.expected_answer == "Y"]
    negative = [item.evidence.attachment_score for item in selected if item.expected_answer == "N"]
    return sum(
        1 if yes > no else 0.5 if yes == no else 0 for yes in positive for no in negative
    ) / (len(positive) * len(negative))


def _average_precision(
    values: tuple[AttachmentResidualTransferObservation, ...], repetition: int
) -> float:
    selected = tuple(item for item in values if item.repetition == repetition)
    ranked = sorted(selected, key=lambda item: item.evidence.attachment_score, reverse=True)
    positives = sum(item.expected_answer == "Y" for item in ranked)
    seen_positive = 0
    result = 0.0
    for rank, item in enumerate(ranked, 1):
        if item.expected_answer == "Y":
            seen_positive += 1
            result += seen_positive / rank
    return result / positives


def _metric_line(
    label: str, values: tuple[AttachmentBinaryMetrics, AttachmentBinaryMetrics]
) -> str:
    accuracy = tuple(item.accuracy for item in values)
    f1 = tuple(item.f1 for item in values)
    return f"{label} accuracy: `{accuracy}`; F1: `{f1}`"


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
