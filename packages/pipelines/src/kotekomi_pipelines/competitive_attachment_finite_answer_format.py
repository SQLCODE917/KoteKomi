"""Deterministic evaluation for the CEA-1.10 answer-format experiment."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median

from kotekomi_application import (
    AttachmentAnswerFormatCase,
    AttachmentAnswerFormatObservation,
    AttachmentAnswerFormatOutcome,
    AttachmentAnswerFormatPreflight,
    AttachmentAnswerFormatReport,
    AttachmentArchivedFiniteLabelObservation,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEvidenceReference,
    AttachmentFiniteLabelEvidence,
    AttachmentFiniteLabelRecoveryReport,
    AttachmentResidualOwnershipTask,
    ModelExecutionReceipt,
    attachment_answer_format_fingerprint,
    parse_attachment_edge_filter_answer,
)


def finite_label_evidence(receipt: ModelExecutionReceipt) -> AttachmentFiniteLabelEvidence:
    """Derive first-position Y/N/U evidence without repairing emitted model text."""
    if not receipt.output_token_probabilities:
        raise ValueError("Finite Label Evidence requires output token probabilities.")
    first = receipt.output_token_probabilities[0]
    if first.position != 0:
        raise ValueError("Finite Label Evidence requires token position zero.")
    grouped: dict[AttachmentEdgeFilterAnswerValue, list[float]] = defaultdict(list)
    answer_probabilities: list[float] = []
    for alternative in first.alternatives:
        try:
            answer = parse_attachment_edge_filter_answer(alternative.token.encode("utf-8"))
        except ValueError:
            answer = None
        if answer is not None:
            grouped[answer].append(alternative.log_probability)
        if alternative.token.strip() == "Answer":
            answer_probabilities.append(alternative.log_probability)
    missing = tuple(answer for answer in AttachmentEdgeFilterAnswerValue if not grouped[answer])
    if missing:
        raise ValueError(
            "Finite Label Evidence lacks alternatives for: "
            + ", ".join(item.value for item in missing)
            + "."
        )
    masses = {answer: _logsumexp(tuple(values)) for answer, values in grouped.items()}
    total = _logsumexp(tuple(masses.values()))
    normalized = {answer: value - total for answer, value in masses.items()}
    ordered = (
        AttachmentEdgeFilterAnswerValue.YES,
        AttachmentEdgeFilterAnswerValue.NO,
        AttachmentEdgeFilterAnswerValue.UNCLEAR,
    )
    argmax = max(ordered, key=lambda item: (normalized[item], -ordered.index(item)))
    answer_probability = max(answer_probabilities) if answer_probabilities else None
    lowest = min(item.log_probability for item in first.alternatives)
    draft = AttachmentFiniteLabelEvidence(
        emitted_token=first.token,
        emitted_log_probability=first.log_probability,
        yes_log_probability=normalized[AttachmentEdgeFilterAnswerValue.YES],
        no_log_probability=normalized[AttachmentEdgeFilterAnswerValue.NO],
        unclear_log_probability=normalized[AttachmentEdgeFilterAnswerValue.UNCLEAR],
        finite_label_argmax=argmax,
        attachment_score=normalized[AttachmentEdgeFilterAnswerValue.YES]
        - _logsumexp(
            (
                normalized[AttachmentEdgeFilterAnswerValue.NO],
                normalized[AttachmentEdgeFilterAnswerValue.UNCLEAR],
            )
        ),
        answer_label_observed=answer_probability is not None,
        answer_label_log_probability=answer_probability,
        lowest_alternative_log_probability=lowest,
        conservative_answer_log_probability=(
            answer_probability if answer_probability is not None else lowest
        ),
    )
    return draft


def validate_answer_format_prompt_pair(labeled: str, bare: str) -> None:
    """Require one prompt pair that differs only in demonstration answer format."""
    forbidden = "Return exactly one answer character"
    if forbidden in labeled or forbidden in bare:
        raise ValueError("Answer Format prompts must leave the output contract to the schema.")
    labeled_lines = labeled.splitlines()
    bare_lines = bare.splitlines()
    if len(labeled_lines) != len(bare_lines):
        raise ValueError("Answer Format prompts must have equal line counts.")
    differences = tuple(
        (left, right)
        for left, right in zip(labeled_lines, bare_lines, strict=True)
        if left != right
    )
    if differences != (("Answer: `Y`", "Y"), ("Answer: `N`", "N")):
        raise ValueError("Answer Format prompts may differ only in two answer lines.")


def build_answer_format_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    labeled_prompt: AttachmentEvidenceReference,
    bare_prompt: AttachmentEvidenceReference,
    labeled_prompt_text: str,
    bare_prompt_text: str,
    tasks: tuple[AttachmentResidualOwnershipTask, ...],
    configured_max_output_tokens: int,
    disputed_gold_task_ids: tuple[str, ...],
) -> AttachmentAnswerFormatPreflight:
    """Build one digest-bound CEA-1.10 preflight."""
    validate_answer_format_prompt_pair(labeled_prompt_text, bare_prompt_text)
    draft = AttachmentAnswerFormatPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        labeled_prompt=labeled_prompt,
        bare_prompt=bare_prompt,
        tasks=tuple(sorted(tasks, key=lambda item: item.id)),
        configured_max_output_tokens=configured_max_output_tokens,
        disputed_gold_task_ids=tuple(sorted(disputed_gold_task_ids)),
        result_fingerprint="0" * 64,
    )
    return AttachmentAnswerFormatPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_answer_format_fingerprint(draft),
    )


def build_finite_label_recovery_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    observations: tuple[AttachmentArchivedFiniteLabelObservation, ...],
) -> AttachmentFiniteLabelRecoveryReport:
    """Build the model-free recovery report over CEA-1.9 receipts."""
    values = tuple(sorted(observations, key=lambda item: (item.task_id, item.arm)))
    draft = AttachmentFiniteLabelRecoveryReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        observations=values,
        result_fingerprint="0" * 64,
    )
    return AttachmentFiniteLabelRecoveryReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_answer_format_fingerprint(draft),
    )


def build_answer_format_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    preflight: AttachmentAnswerFormatPreflight,
    labeled_observations: tuple[AttachmentAnswerFormatObservation, ...],
    bare_observations: tuple[AttachmentAnswerFormatObservation, ...],
) -> AttachmentAnswerFormatReport:
    """Evaluate one complete paired format experiment."""
    labeled = {item.task_id: item for item in labeled_observations}
    bare = {item.task_id: item for item in bare_observations}
    task_ids = {item.id for item in preflight.tasks}
    if set(labeled) != task_ids or set(bare) != task_ids:
        raise ValueError("Answer Format observations do not cover the prepared tasks.")
    cases: list[AttachmentAnswerFormatCase] = []
    for task in preflight.tasks:
        left = labeled[task.id]
        right = bare[task.id]
        left_evidence = left.finite_label_evidence
        right_evidence = right.finite_label_evidence
        cases.append(
            AttachmentAnswerFormatCase(
                task=task,
                labeled=left,
                bare=right,
                finite_label_argmax_agrees=(
                    left_evidence is not None
                    and right_evidence is not None
                    and left_evidence.finite_label_argmax is right_evidence.finite_label_argmax
                ),
                strict_validity_improved=(
                    not left.strict_valid_output and right.strict_valid_output
                ),
                answer_pressure_delta_upper_bound=(
                    right_evidence.conservative_answer_log_probability
                    - left_evidence.answer_label_log_probability
                    if left_evidence is not None
                    and left_evidence.answer_label_log_probability is not None
                    and right_evidence is not None
                    else None
                ),
            )
        )
    values = tuple(cases)
    evidence_count = sum(
        item.finite_label_evidence is not None
        for case in values
        for item in (case.labeled, case.bare)
    )
    labeled_valid = sum(item.labeled.strict_valid_output for item in values)
    bare_valid = sum(item.bare.strict_valid_output for item in values)
    labeled_answer = sum(
        item.labeled.finite_label_evidence is not None
        and item.labeled.finite_label_evidence.emitted_token.strip() == "Answer"
        for item in values
    )
    bare_answer = sum(
        item.bare.finite_label_evidence is not None
        and item.bare.finite_label_evidence.emitted_token.strip() == "Answer"
        for item in values
    )
    agreements = sum(item.finite_label_argmax_agrees for item in values)
    improvements = sum(item.strict_validity_improved for item in values)
    deltas = tuple(
        item.answer_pressure_delta_upper_bound
        for item in values
        if item.answer_pressure_delta_upper_bound is not None
    )
    pressure_comparisons = len(deltas)
    pressure_median = median(deltas) if pressure_comparisons == 10 else None
    outcome = answer_format_outcome(
        probability_evidence_count=evidence_count,
        answer_pressure_comparison_count=pressure_comparisons,
        labeled_valid_output_count=labeled_valid,
        bare_valid_output_count=bare_valid,
        labeled_answer_first_token_count=labeled_answer,
        bare_answer_first_token_count=bare_answer,
        finite_label_argmax_agreement_count=agreements,
        median_answer_pressure_delta_upper_bound=pressure_median,
    )
    draft = AttachmentAnswerFormatReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        labeled_prompt=preflight.labeled_prompt,
        bare_prompt=preflight.bare_prompt,
        disputed_gold_task_ids=preflight.disputed_gold_task_ids,
        cases=values,
        probability_evidence_count=evidence_count,
        labeled_valid_output_count=labeled_valid,
        bare_valid_output_count=bare_valid,
        labeled_answer_first_token_count=labeled_answer,
        bare_answer_first_token_count=bare_answer,
        finite_label_argmax_agreement_count=agreements,
        strict_validity_improvement_count=improvements,
        answer_pressure_comparison_count=pressure_comparisons,
        median_answer_pressure_delta_upper_bound=pressure_median,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentAnswerFormatReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_answer_format_fingerprint(draft),
    )


def answer_format_outcome(
    *,
    probability_evidence_count: int,
    answer_pressure_comparison_count: int,
    labeled_valid_output_count: int,
    bare_valid_output_count: int,
    labeled_answer_first_token_count: int,
    bare_answer_first_token_count: int,
    finite_label_argmax_agreement_count: int,
    median_answer_pressure_delta_upper_bound: float | None,
) -> AttachmentAnswerFormatOutcome:
    """Classify the predeclared CEA-1.10 causal gates."""
    if probability_evidence_count != 20 or answer_pressure_comparison_count != 10:
        return AttachmentAnswerFormatOutcome.INCONCLUSIVE
    if (
        bare_valid_output_count == 10
        and bare_answer_first_token_count == 0
        and labeled_answer_first_token_count >= 1
        and median_answer_pressure_delta_upper_bound is not None
        and median_answer_pressure_delta_upper_bound <= -5.0
        and finite_label_argmax_agreement_count >= 9
    ):
        return AttachmentAnswerFormatOutcome.SUPPORTED
    if bare_valid_output_count > labeled_valid_output_count:
        return AttachmentAnswerFormatOutcome.MIXED
    return AttachmentAnswerFormatOutcome.FALSIFIED


def render_answer_format_review(report: AttachmentAnswerFormatReport) -> str:
    """Render compact exact data-in and data-out for human review."""
    lines = [
        "# CEA-1.10 Finite Answer Format Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Strict valid outputs: Labeled `{report.labeled_valid_output_count}/10`; "
        f"Bare `{report.bare_valid_output_count}/10`",
        "",
        f"First token `Answer`: Labeled `{report.labeled_answer_first_token_count}/10`; "
        f"Bare `{report.bare_answer_first_token_count}/10`",
        "",
        f"Finite Label Argmax agreement: `{report.finite_label_argmax_agreement_count}/10`",
        "",
        f"Valid Answer pressure comparisons: `{report.answer_pressure_comparison_count}/10`",
        "",
        "Median conservative Answer pressure change: "
        f"`{report.median_answer_pressure_delta_upper_bound}`",
        "",
        "Disputed Gold labels were not used as outcome gates: "
        + ", ".join(f"`{item}`" for item in report.disputed_gold_task_ids),
        "",
    ]
    for case in report.cases:
        edge = case.task.edge_filter_task.edge
        lines.extend(
            (
                f"## {case.task.id}",
                "",
                f"> {case.task.edge_filter_task.source_text}",
                "",
                f"Candidate: `{edge.candidate_range.text}`",
                "",
                f"Target Event: `{edge.event_range.text}`",
                "",
                "Candidate Remainder: "
                + " | ".join(f"`{item.text}`" for item in case.task.remainder_ranges),
                "",
                f"Labeled raw output: `{case.labeled.raw_output_text}`",
                "",
                f"Labeled strict answer: `{_answer(case.labeled)}`",
                "",
                f"Labeled finite argmax: `{_argmax(case.labeled)}`",
                "",
                f"Bare raw output: `{case.bare.raw_output_text}`",
                "",
                f"Bare strict answer: `{_answer(case.bare)}`",
                "",
                f"Bare finite argmax: `{_argmax(case.bare)}`",
                "",
                f"Answer pressure change: `{case.answer_pressure_delta_upper_bound}`",
                "",
                f"Labeled execution: `{case.labeled.execution_record.path}`",
                "",
                f"Bare execution: `{case.bare.execution_record.path}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_answer_format_handoff(
    report: AttachmentAnswerFormatReport,
    *,
    recovery: AttachmentFiniteLabelRecoveryReport,
    labeled_prompt_text: str,
    bare_prompt_text: str,
    package_files: tuple[AttachmentEvidenceReference, ...],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render one self-contained second-opinion package."""
    lines = [
        "# CEA-1.10 Finite Answer Format Handoff",
        "",
        "## Hypothesis",
        "",
        "> Bare demonstration answers remove answer-label imitation without changing Qwen's "
        "finite-label semantic preference.",
        "",
        "## Boundaries",
        "",
        "Both arms use the same ten tasks, Candidate Remainder renderer, model, schema, and "
        "generation settings.",
        "",
        "The prompt files differ only in two demonstration answer lines.",
        "",
        "Observed Answer validity and Finite Label Evidence remain separate.",
        "",
        "Gold correctness does not determine this experiment's outcome.",
        "",
        "Production integration remains inactive.",
        "",
        "## Source implementation",
        "",
        f"Public repository: `{source_repository_url}`",
        "",
        f"Source revision: `{source_revision}`",
        "",
        "## Archived recovery",
        "",
        f"Finite Label Evidence records: `{recovery.finite_label_evidence_count}/20`",
        "",
        f"Sealed scores reproduced: `{recovery.sealed_score_match_count}/18`",
        "",
        f"Invalid Observed Answers retained: `{recovery.invalid_observed_answer_count}`",
        "",
        "## Labeled Prompt",
        "",
        "~~~~text",
        labeled_prompt_text.rstrip(),
        "~~~~",
        "",
        "## Bare Prompt",
        "",
        "~~~~text",
        bare_prompt_text.rstrip(),
        "~~~~",
        "",
        "## Results",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Report fingerprint: `{report.result_fingerprint}`",
        "",
        f"Strict outputs: Labeled `{report.labeled_valid_output_count}/10`; "
        f"Bare `{report.bare_valid_output_count}/10`",
        "",
        f"First-token Answer counts: Labeled `{report.labeled_answer_first_token_count}`; "
        f"Bare `{report.bare_answer_first_token_count}`",
        "",
        f"Finite Label Argmax agreement: `{report.finite_label_argmax_agreement_count}/10`",
        "",
        f"Valid Answer pressure comparisons: `{report.answer_pressure_comparison_count}/10`",
        "",
        "Median conservative Answer pressure change: "
        f"`{report.median_answer_pressure_delta_upper_bound}`",
        "",
        "## Package files",
        "",
    ]
    lines.extend(f"- `{item.label}`: `{item.path}` (`{item.sha256}`)" for item in package_files)
    lines.extend(
        (
            "",
            "## Reviewer questions",
            "",
            "1. Do the two prompt files differ only in answer format?",
            "2. Does the evidence separate invalid output from finite-label preference?",
            "3. Does the result establish a causal answer-format effect?",
            "4. Which smallest semantic experiment follows from this result?",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _answer(observation: AttachmentAnswerFormatObservation) -> str:
    answer = observation.decision.answer
    return answer.value if observation.strict_valid_output and answer is not None else "invalid"


def _argmax(observation: AttachmentAnswerFormatObservation) -> str:
    evidence = observation.finite_label_evidence
    return evidence.finite_label_argmax.value if evidence is not None else "missing"


def _logsumexp(values: tuple[float, ...]) -> float:
    maximum = max(values)
    return maximum + math.log(sum(math.exp(item - maximum) for item in values))
