"""Deterministic selection and evaluation for CEA-1.7."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Literal

from kotekomi_application import (
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentResidualOwnershipCaseEvaluation,
    AttachmentResidualOwnershipObservation,
    AttachmentResidualOwnershipOutcome,
    AttachmentResidualOwnershipPreflight,
    AttachmentResidualOwnershipReport,
    AttachmentResidualOwnershipTask,
    attachment_candidate_remainder_ranges,
    attachment_contained_foreign_event_ids,
    attachment_residual_ownership_fingerprint,
    build_attachment_residual_ownership_task,
)


def partition_containment_tasks(
    tasks: tuple[AttachmentEdgeFilterTask, ...],
) -> tuple[tuple[str, ...], tuple[AttachmentResidualOwnershipTask, ...]]:
    """Partition Containment Edges without consulting Attachment Gold."""
    mixed: list[str] = []
    residual: list[AttachmentResidualOwnershipTask] = []
    for task in tasks:
        try:
            attachment_candidate_remainder_ranges(task)
        except ValueError:
            continue
        if attachment_contained_foreign_event_ids(task):
            mixed.append(task.edge.id)
        else:
            residual.append(build_attachment_residual_ownership_task(task))
    return tuple(sorted(mixed)), tuple(sorted(residual, key=lambda item: item.id))


def build_attachment_residual_ownership_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
    development_tasks: tuple[AttachmentEdgeFilterTask, ...],
    validation_tasks: tuple[AttachmentEdgeFilterTask, ...],
) -> AttachmentResidualOwnershipPreflight:
    """Build the complete Gold-free CEA-1.7 task inventory."""
    development_mixed, development_residual = partition_containment_tasks(development_tasks)
    validation_mixed, validation_residual = partition_containment_tasks(validation_tasks)
    draft = AttachmentResidualOwnershipPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=prompt,
        development_mixed_edge_ids=development_mixed,
        development_tasks=development_residual,
        validation_mixed_edge_ids=validation_mixed,
        validation_tasks=validation_residual,
        gold_entered_selection=False,
        gold_entered_model_task=False,
        validation_executed=False,
        production_integration="not_activated",
        result_fingerprint="0" * 64,
    )
    return AttachmentResidualOwnershipPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_residual_ownership_fingerprint(draft),
    )


def build_attachment_residual_ownership_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
    tasks: tuple[AttachmentResidualOwnershipTask, ...],
    expected_answers: Mapping[str, Literal["Y", "N"]],
    observations: tuple[AttachmentResidualOwnershipObservation, ...],
) -> AttachmentResidualOwnershipReport:
    """Score two development repetitions against occurrence-level Gold."""
    if set(expected_answers) != {item.id for item in tasks}:
        raise ValueError("Residual Ownership expected-answer inventory drifted.")
    by_task: dict[str, list[AttachmentResidualOwnershipObservation]] = defaultdict(list)
    for observation in observations:
        by_task[observation.task_id].append(observation)
    cases: list[AttachmentResidualOwnershipCaseEvaluation] = []
    for task in sorted(tasks, key=lambda item: item.id):
        task_observations = tuple(sorted(by_task[task.id], key=lambda item: item.repetition))
        expected = expected_answers[task.id]
        if expected not in {"Y", "N"}:
            raise ValueError("Residual Ownership Gold answer must be Y or N.")
        semantic_results = tuple(
            (item.decision.status, item.decision.answer) for item in task_observations
        )
        cases.append(
            AttachmentResidualOwnershipCaseEvaluation(
                task=task,
                expected_answer=expected,
                observations=task_observations,
                stable_semantic_result=(
                    len(semantic_results) == 2 and semantic_results[0] == semantic_results[1]
                ),
                passed_both_repetitions=(
                    len(task_observations) == 2 and all(item.passed for item in task_observations)
                ),
            )
        )
    all_observations = tuple(item for case in cases for item in case.observations)
    positive_loss = any(
        item.expected_answer == "Y" and not item.passed for item in all_observations
    )
    supported = (
        len(all_observations) == 20
        and all(item.passed for item in all_observations)
        and all(item.stable_semantic_result for item in cases)
        and all(
            item.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
            for item in all_observations
        )
    )
    outcome = (
        AttachmentResidualOwnershipOutcome.SUPPORTED
        if supported
        else AttachmentResidualOwnershipOutcome.FALSIFIED
        if positive_loss
        else AttachmentResidualOwnershipOutcome.MIXED
    )
    draft = AttachmentResidualOwnershipReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=prompt,
        cases=tuple(cases),
        task_count=10,
        observation_count=len(all_observations),
        expected_positive_count=sum(item.expected_answer == "Y" for item in cases),
        expected_negative_count=sum(item.expected_answer == "N" for item in cases),
        correct_observation_count=sum(item.passed for item in all_observations),
        positive_retention_count=sum(
            item.expected_answer == "Y" and item.passed for item in all_observations
        ),
        negative_rejection_count=sum(
            item.expected_answer == "N" and item.passed for item in all_observations
        ),
        stable_case_count=sum(item.stable_semantic_result for item in cases),
        unresolved_observation_count=sum(
            item.decision.status is not AttachmentEdgeFilterDecisionStatus.COMPLETE
            for item in all_observations
        ),
        model_execution_count=len(all_observations),
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        outcome=outcome,
        production_integration="not_activated",
        result_fingerprint="0" * 64,
    )
    return AttachmentResidualOwnershipReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_residual_ownership_fingerprint(draft),
    )


def render_attachment_residual_ownership_review(
    report: AttachmentResidualOwnershipReport,
) -> str:
    """Render exact data-in/data-out for every development case."""
    lines = [
        "# CEA-1.7 Residual Attachment Ownership Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Correct observations: `{report.correct_observation_count}/20`",
        "",
        f"Positive retention: `{report.positive_retention_count}/14`",
        "",
        f"Negative rejection: `{report.negative_rejection_count}/6`",
        "",
        f"Stable cases: `{report.stable_case_count}/10`",
        "",
        f"Unresolved observations: `{report.unresolved_observation_count}`",
        "",
    ]
    for case in report.cases:
        task = case.task
        edge = task.edge_filter_task.edge
        lines.extend(
            (
                f"## {task.id}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {task.edge_filter_task.source_text}",
                "",
                f"Candidate: `{edge.candidate_range.text}`",
                "",
                f"Target Event: `{edge.event_range.text}`",
                "",
                "Candidate Remainder:",
                "",
            )
        )
        lines.extend(f"- `{item.text}`" for item in task.remainder_ranges)
        lines.extend(("", f"Expected answer: `{case.expected_answer}`", ""))
        for item in case.observations:
            actual = item.decision.answer.value if item.decision.answer is not None else "NONE"
            lines.extend(
                (
                    f"Repetition {item.repetition} actual answer: `{actual}`",
                    "",
                    f"Raw output: `{item.raw_output_text}`",
                    "",
                    "Exact model input:",
                    "",
                    "~~~~text",
                    item.exact_model_input,
                    "~~~~",
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_residual_ownership_handoff(
    report: AttachmentResidualOwnershipReport,
    *,
    prompt_text: str,
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained handoff for human-run Claude review."""
    failed = tuple(
        case
        for case in report.cases
        if not case.passed_both_repetitions or not case.stable_semantic_result
    )
    lines = [
        "# CEA-1.7 Residual Attachment Ownership Handoff",
        "",
        "## Hypothesis",
        "",
        "> A bounded Residual Ownership task can distinguish valid and invalid Residual "
        "Edges without losing a Gold-positive Attachment.",
        "",
        "## Job allocation",
        "",
        "KoteKomi selected exact Containment Edges and detected complete Foreign Event ranges.",
        "",
        "Qwen judged only whether the remaining Candidate text belongs to the Target Event fact.",
        "",
        "KoteKomi created every identifier, trace, mapping, metric, and output file.",
        "",
        "Gold did not enter selection or model input.",
        "",
        "Production integration remained inactive.",
        "",
        "## Source implementation",
        "",
        f"Public repository: `{source_repository_url}`",
        "",
        f"Source revision: `{source_revision}`",
        "",
        "## Prompt",
        "",
        "~~~~text",
        prompt_text.rstrip(),
        "~~~~",
        "",
        "## Results",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Correct observations: `{report.correct_observation_count}/20`",
        "",
        f"Positive retention: `{report.positive_retention_count}/14`",
        "",
        f"Negative rejection: `{report.negative_rejection_count}/6`",
        "",
        f"Stable cases: `{report.stable_case_count}/10`",
        "",
        f"Unresolved observations: `{report.unresolved_observation_count}`",
        "",
        f"Failed or unstable cases: `{len(failed)}`",
        "",
        "## Failed or unstable cases",
        "",
    ]
    if not failed:
        lines.extend(("NONE", ""))
    for case in failed:
        task = case.task
        edge = task.edge_filter_task.edge
        answers = tuple(
            item.decision.answer.value if item.decision.answer is not None else "NONE"
            for item in case.observations
        )
        lines.extend(
            (
                f"### {task.id}",
                "",
                f"> {task.edge_filter_task.source_text}",
                "",
                f"Candidate: `{edge.candidate_range.text}`",
                "",
                f"Target Event: `{edge.event_range.text}`",
                "",
                "Candidate Remainder: "
                + " | ".join(f"`{item.text}`" for item in task.remainder_ranges),
                "",
                f"Expected: `{case.expected_answer}`",
                "",
                f"Actual repetitions: `{answers}`",
                "",
            )
        )
    lines.extend(
        (
            "## Review questions",
            "",
            "1. Does this task isolate Residual Ownership from deterministic range work?",
            "2. Do the expected answers follow the exact source text?",
            "3. Do the failures show prompt ambiguity, model limits, or a wrong task boundary?",
            "4. What is the smallest falsifiable next experiment?",
            "",
            "Use `diagnostic-review.md` for every exact model input and raw output.",
            "Use `report.json` for typed occurrence-level results.",
        )
    )
    return "\n".join(lines).rstrip() + "\n"
