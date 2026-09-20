"""Paired evaluation and review rendering for CEA-1.9."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from kotekomi_application import (
    AttachmentCandidateRemainderArm,
    AttachmentCandidateRemainderCase,
    AttachmentCandidateRemainderObservation,
    AttachmentCandidateRemainderOutcome,
    AttachmentCandidateRemainderPreflight,
    AttachmentCandidateRemainderReport,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentResidualCueAblationPreflight,
    AttachmentResidualCueAblationReport,
    attachment_candidate_remainder_fingerprint,
)


def validate_candidate_remainder_prompt_pair(baseline: str, remainder: str) -> None:
    """Require preserved demonstrations plus an explicit Remainder contract."""
    preserved = (
        "Jordan arrived before Casey <candidate>criticized the policy in March</candidate>.",
        "Jordan arrived before Casey <event>criticized</event> the policy in March.",
        'E1: "arrived"',
        "Jordan handed <candidate>the report to Casey, who criticized the policy</candidate>.",
        "Jordan handed the report to Casey, who <event>criticized</event> the policy.",
        'E1: "handed"',
        "Answer: `Y`",
        "Answer: `N`",
        "Return exactly one answer character: `Y`, `N`, or `U`.",
    )
    if any(item not in baseline or item not in remainder for item in preserved):
        raise ValueError("Candidate Remainder prompt changed preserved demonstration semantics.")
    required = (
        "The Candidate Remainder is the Candidate text outside the Target Event.",
        "Each Candidate Remainder part is between `<remainder>` and `</remainder>`.",
        "Candidate Remainder parts:",
        "R1: <remainder> the policy in March</remainder>",
        "R1: <remainder>the report to Casey, who </remainder>",
        "R2: <remainder> the policy</remainder>",
    )
    if any(item not in remainder for item in required):
        raise ValueError("Candidate Remainder prompt lacks its explicit Remainder contract.")
    if "Candidate Remainder parts:" in baseline:
        raise ValueError("Candidate Remainder Baseline Prompt already exposes the intervention.")


def build_candidate_remainder_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    baseline_prompt: AttachmentEvidenceReference,
    remainder_prompt: AttachmentEvidenceReference,
    baseline_prompt_text: str,
    remainder_prompt_text: str,
    cue_preflight: AttachmentResidualCueAblationPreflight,
    cue_report: AttachmentResidualCueAblationReport,
    configured_max_output_tokens: int,
) -> AttachmentCandidateRemainderPreflight:
    """Bind one paired task-contract experiment to sealed CEA-1.8 evidence."""
    validate_candidate_remainder_prompt_pair(baseline_prompt_text, remainder_prompt_text)
    if cue_preflight.cue_prompt.sha256 != baseline_prompt.sha256:
        raise ValueError("Candidate Remainder Baseline Prompt differs from CEA-1.8.")
    if cue_report.outcome.value != "supported" or cue_report.validation_executed:
        raise ValueError("Candidate Remainder requires the development-only CEA-1.8 result.")
    if tuple(item.task_id for item in cue_report.cases) != tuple(
        item.id for item in cue_preflight.tasks
    ):
        raise ValueError("Candidate Remainder CEA-1.8 task inventory drifted.")
    if (
        sum(item.expected_answer == "Y" for item in cue_report.cases) != 8
        or sum(item.expected_answer == "N" for item in cue_report.cases) != 2
    ):
        raise ValueError("Candidate Remainder corrected Gold inventory drifted.")
    draft = AttachmentCandidateRemainderPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        baseline_prompt=baseline_prompt,
        remainder_prompt=remainder_prompt,
        tasks=cue_preflight.tasks,
        gold_adjudications=cue_preflight.gold_adjudications,
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentCandidateRemainderPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_candidate_remainder_fingerprint(draft),
    )


def build_candidate_remainder_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    preflight: AttachmentCandidateRemainderPreflight,
    cue_report: AttachmentResidualCueAblationReport,
    baseline_observations: Sequence[AttachmentCandidateRemainderObservation],
    remainder_observations: Sequence[AttachmentCandidateRemainderObservation],
) -> AttachmentCandidateRemainderReport:
    """Compare paired answers and probabilities by exact task occurrence."""
    task_by_id = {item.id: item for item in preflight.tasks}
    cue_by_id = {item.task_id: item for item in cue_report.cases}
    baseline_by_id = _observations_by_task(
        baseline_observations,
        AttachmentCandidateRemainderArm.BASELINE,
    )
    remainder_by_id = _observations_by_task(
        remainder_observations,
        AttachmentCandidateRemainderArm.REMAINDER,
    )
    inventories = (set(task_by_id), set(cue_by_id), set(baseline_by_id), set(remainder_by_id))
    if any(values != inventories[0] for values in inventories[1:]):
        raise ValueError("Candidate Remainder paired task inventory differs.")
    cases: list[AttachmentCandidateRemainderCase] = []
    for task_id in sorted(task_by_id):
        task = task_by_id[task_id]
        cue_case = cue_by_id[task_id]
        baseline = baseline_by_id[task_id]
        remainder = remainder_by_id[task_id]
        if cue_case.edge_id != task.edge_filter_task.edge.id:
            raise ValueError("Candidate Remainder Gold references a foreign Edge.")
        baseline_score = (
            baseline.probability.attachment_score if baseline.probability is not None else None
        )
        remainder_score = (
            remainder.probability.attachment_score if remainder.probability is not None else None
        )
        delta = (
            remainder_score - baseline_score
            if baseline_score is not None and remainder_score is not None
            else None
        )
        baseline_answer = _answer(baseline)
        remainder_answer = _answer(remainder)
        cases.append(
            AttachmentCandidateRemainderCase(
                task=task,
                inherited_expected_answer=cue_case.inherited_expected_answer,
                expected_answer=cue_case.expected_answer,
                baseline=baseline,
                remainder=remainder,
                baseline_attachment_score=baseline_score,
                remainder_attachment_score=remainder_score,
                score_delta=delta,
                positive_recovery=(
                    cue_case.expected_answer == "Y"
                    and baseline_answer is AttachmentEdgeFilterAnswerValue.NO
                    and remainder_answer is AttachmentEdgeFilterAnswerValue.YES
                ),
                negative_regression=(
                    cue_case.expected_answer == "N"
                    and baseline_answer is AttachmentEdgeFilterAnswerValue.NO
                    and remainder_answer is not AttachmentEdgeFilterAnswerValue.NO
                ),
            )
        )
    values = tuple(cases)
    positive_deltas = tuple(
        item.score_delta
        for item in values
        if item.expected_answer == "Y" and item.score_delta is not None
    )
    negative_deltas = tuple(
        item.score_delta
        for item in values
        if item.expected_answer == "N" and item.score_delta is not None
    )
    probability_count = sum(
        observation.probability is not None
        for item in values
        for observation in (item.baseline, item.remainder)
    )
    baseline_correct = sum(item.baseline.passed for item in values)
    remainder_correct = sum(item.remainder.passed for item in values)
    positive_recoveries = sum(item.positive_recovery for item in values)
    negative_regressions = sum(item.negative_regression for item in values)
    positive_median = median(positive_deltas) if len(positive_deltas) == 8 else None
    negative_max = max(negative_deltas) if len(negative_deltas) == 2 else None
    complete = probability_count == 20 and all(
        _answer(item.baseline) is not None and _answer(item.remainder) is not None
        for item in values
    )
    selective = (
        positive_median is not None and negative_max is not None and positive_median > negative_max
    )
    if not complete:
        outcome = AttachmentCandidateRemainderOutcome.INCONCLUSIVE
    elif positive_recoveries == 0:
        outcome = AttachmentCandidateRemainderOutcome.FALSIFIED
    elif remainder_correct > baseline_correct and not negative_regressions and selective:
        outcome = AttachmentCandidateRemainderOutcome.SUPPORTED
    else:
        outcome = AttachmentCandidateRemainderOutcome.MIXED
    draft = AttachmentCandidateRemainderReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        baseline_prompt=preflight.baseline_prompt,
        remainder_prompt=preflight.remainder_prompt,
        gold_adjudications=preflight.gold_adjudications,
        cases=values,
        baseline_correct_count=baseline_correct,
        remainder_correct_count=remainder_correct,
        baseline_positive_correct_count=sum(
            item.expected_answer == "Y" and item.baseline.passed for item in values
        ),
        remainder_positive_correct_count=sum(
            item.expected_answer == "Y" and item.remainder.passed for item in values
        ),
        baseline_negative_correct_count=sum(
            item.expected_answer == "N" and item.baseline.passed for item in values
        ),
        remainder_negative_correct_count=sum(
            item.expected_answer == "N" and item.remainder.passed for item in values
        ),
        positive_recovery_count=positive_recoveries,
        negative_regression_count=negative_regressions,
        probability_evidence_count=probability_count,
        positive_median_score_delta=positive_median,
        negative_max_score_delta=negative_max,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentCandidateRemainderReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_candidate_remainder_fingerprint(draft),
    )


def render_candidate_remainder_review(report: AttachmentCandidateRemainderReport) -> str:
    """Render exact paired data-in and data-out for human review."""
    lines = [
        "# CEA-1.9 Explicit Candidate Remainder Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Correct cases: Baseline `{report.baseline_correct_count}/10`; "
        f"Remainder `{report.remainder_correct_count}/10`",
        "",
        f"Positive cases: Baseline `{report.baseline_positive_correct_count}/8`; "
        f"Remainder `{report.remainder_positive_correct_count}/8`",
        "",
        f"Negative cases: Baseline `{report.baseline_negative_correct_count}/2`; "
        f"Remainder `{report.remainder_negative_correct_count}/2`",
        "",
        f"Positive recoveries: `{report.positive_recovery_count}`",
        "",
        f"Negative regressions: `{report.negative_regression_count}`",
        "",
        f"Positive median Score Delta: `{report.positive_median_score_delta}`",
        "",
        f"Negative maximum Score Delta: `{report.negative_max_score_delta}`",
        "",
    ]
    for case in report.cases:
        edge = case.task.edge_filter_task.edge
        baseline_answer = _answer_text(case.baseline)
        remainder_answer = _answer_text(case.remainder)
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
                f"Expected: `{case.expected_answer}`",
                "",
                f"Baseline: `{baseline_answer}`; score `{case.baseline_attachment_score}`",
                "",
                f"Remainder: `{remainder_answer}`; score `{case.remainder_attachment_score}`",
                "",
                f"Score Delta: `{case.score_delta}`",
                "",
                f"Baseline execution: `{case.baseline.execution_record.path}`",
                "",
                f"Remainder execution: `{case.remainder.execution_record.path}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_candidate_remainder_handoff(
    report: AttachmentCandidateRemainderReport,
    *,
    baseline_prompt_text: str,
    remainder_prompt_text: str,
    package_files: tuple[AttachmentEvidenceReference, ...],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render one self-contained independent-review package."""
    lines = [
        "# CEA-1.9 Explicit Candidate Remainder Handoff",
        "",
        "## Hypothesis",
        "",
        "> Explicit Candidate Remainder text improves selective Residual Ownership judgment "
        "without regressing Gold-negative cases.",
        "",
        "## Intervention",
        "",
        "Both arms use the same ten exact tasks, corrected Gold inventory, model, and generation "
        "settings.",
        "",
        "The Baseline Arm uses the CEA-1.8 Cue-Balanced Prompt and Candidate renderer.",
        "",
        "The Remainder Arm gives Qwen the exact Candidate text outside the Target Event.",
        "",
        "KoteKomi derives every Remainder part from authoritative source ranges.",
        "",
        "Each arm executes once because CEA-1.8 established deterministic repeated outputs.",
        "",
        "Production integration remains inactive.",
        "",
        "## Source implementation",
        "",
        f"Public repository: `{source_repository_url}`",
        "",
        f"Source revision: `{source_revision}`",
        "",
        "## Baseline Prompt",
        "",
        "~~~~text",
        baseline_prompt_text.rstrip(),
        "~~~~",
        "",
        "## Remainder Prompt",
        "",
        "~~~~text",
        remainder_prompt_text.rstrip(),
        "~~~~",
        "",
        "## Results",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Comparison report fingerprint: `{report.result_fingerprint}`",
        "",
        f"Correct cases: Baseline `{report.baseline_correct_count}/10`; "
        f"Remainder `{report.remainder_correct_count}/10`",
        "",
        f"Positive recoveries: `{report.positive_recovery_count}`",
        "",
        f"Negative regressions: `{report.negative_regression_count}`",
        "",
        f"Positive median Score Delta: `{report.positive_median_score_delta}`",
        "",
        f"Negative maximum Score Delta: `{report.negative_max_score_delta}`",
        "",
        "The corrected evaluation inventory contains eight positive and two negative cases.",
        "",
        "One positive case preserves inherited Attachment Gold `N` and operator-approved "
        "Residual Ownership Gold `Y`.",
        "",
        "A supported result establishes this bounded task-contract effect only.",
        "",
        "It does not authorize production integration or establish frozen validation quality.",
        "",
        "## Package files",
        "",
    ]
    lines.extend(f"- `{item.label}`: `{item.path}` (`{item.sha256}`)" for item in package_files)
    lines.extend(
        (
            "",
            "## Review questions",
            "",
            "1. Does the paired design isolate explicit Candidate Remainder judgment?",
            "2. Do the Score Deltas show selective gain rather than uniform answer bias?",
            "3. Do any Gold answers conflict with the exact source?",
            "4. What is the smallest justified next experiment?",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _observations_by_task(
    observations: Sequence[AttachmentCandidateRemainderObservation],
    arm: AttachmentCandidateRemainderArm,
) -> dict[str, AttachmentCandidateRemainderObservation]:
    values = tuple(observations)
    if len(values) != 10 or any(item.arm is not arm for item in values):
        raise ValueError(f"Candidate Remainder {arm.value} observation inventory drifted.")
    result = {item.task_id: item for item in values}
    if len(result) != len(values):
        raise ValueError(f"Candidate Remainder {arm.value} observations are not distinct.")
    return result


def _answer(
    observation: AttachmentCandidateRemainderObservation,
) -> AttachmentEdgeFilterAnswerValue | None:
    if observation.decision.status is not AttachmentEdgeFilterDecisionStatus.COMPLETE:
        return None
    return observation.decision.answer


def _answer_text(observation: AttachmentCandidateRemainderObservation) -> str:
    answer = _answer(observation)
    return answer.value if answer is not None else "UNRESOLVED"
