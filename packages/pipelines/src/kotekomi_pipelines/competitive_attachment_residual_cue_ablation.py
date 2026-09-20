"""Deterministic evaluation and rendering for the CEA-1.8 cue ablation."""

from __future__ import annotations

from collections.abc import Mapping

from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentResidualCueAblationCase,
    AttachmentResidualCueAblationOutcome,
    AttachmentResidualCueAblationPreflight,
    AttachmentResidualCueAblationReport,
    AttachmentResidualGoldAdjudication,
    AttachmentResidualOwnershipReport,
    attachment_residual_cue_ablation_fingerprint,
)

_EXAMPLE_ONE = "Example 1:\n"
_EXAMPLE_TWO = "Example 2:\n"


def validate_residual_cue_prompt_pair(baseline: str, cue: str) -> None:
    """Require one changed positive example and no other prompt change."""
    baseline_prefix, baseline_example, baseline_suffix = _prompt_parts(baseline)
    cue_prefix, cue_example, cue_suffix = _prompt_parts(cue)
    if baseline_prefix != cue_prefix or baseline_suffix != cue_suffix:
        raise ValueError("Cue ablation changed text outside the positive example.")
    if baseline_example == cue_example:
        raise ValueError("Cue ablation did not change the positive example.")
    if "Other Events in the passage:\nNONE" not in baseline_example:
        raise ValueError("Baseline positive example lacks the confounded NONE cue.")
    required = (
        "Jordan arrived before Casey <candidate>criticized the policy in March</candidate>",
        "Jordan arrived before Casey <event>criticized</event> the policy in March",
        'Other Events in the passage:\nE1: "arrived"',
        "Answer: `Y`",
    )
    if any(item not in cue_example for item in required):
        raise ValueError("Cue ablation positive example contract drifted.")
    if "Other Events in the passage:\nNONE" in cue_example:
        raise ValueError("Cue ablation retained the confounded NONE cue.")


def build_residual_cue_ablation_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    baseline_prompt: AttachmentEvidenceReference,
    cue_prompt: AttachmentEvidenceReference,
    baseline_prompt_text: str,
    cue_prompt_text: str,
    baseline_report: AttachmentResidualOwnershipReport,
    gold_adjudications: tuple[AttachmentResidualGoldAdjudication, ...],
    configured_max_output_tokens: int,
) -> AttachmentResidualCueAblationPreflight:
    """Bind one prompt-only ablation to the sealed constant-N baseline."""
    validate_residual_cue_prompt_pair(baseline_prompt_text, cue_prompt_text)
    if (
        baseline_report.prompt.path != baseline_prompt.path
        or baseline_report.prompt.sha256 != baseline_prompt.sha256
    ):
        raise ValueError("Cue ablation baseline prompt differs from its report.")
    if baseline_report.task_count != 10 or baseline_report.observation_count != 20:
        raise ValueError("Cue ablation baseline inventory drifted.")
    baseline_answers = tuple(
        observation.decision.answer
        for case in baseline_report.cases
        for observation in case.observations
    )
    if baseline_answers != (AttachmentEdgeFilterAnswerValue.NO,) * 20:
        raise ValueError("Cue ablation requires the sealed constant-N baseline.")
    if baseline_report.stable_case_count != 10:
        raise ValueError("Cue ablation requires ten stable baseline cases.")
    tasks = tuple(case.task for case in baseline_report.cases)
    baseline_by_task = {item.task.id: item for item in baseline_report.cases}
    for adjudication in gold_adjudications:
        baseline = baseline_by_task.get(adjudication.task_id)
        if baseline is None or baseline.expected_answer != adjudication.inherited_answer:
            raise ValueError("Residual Gold adjudication differs from inherited Gold.")
    draft = AttachmentResidualCueAblationPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        baseline_prompt=baseline_prompt,
        cue_prompt=cue_prompt,
        tasks=tasks,
        gold_adjudications=gold_adjudications,
        baseline_report_fingerprint=baseline_report.result_fingerprint,
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentResidualCueAblationPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_residual_cue_ablation_fingerprint(draft),
    )


def build_residual_cue_ablation_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    baseline_prompt: AttachmentEvidenceReference,
    cue_prompt: AttachmentEvidenceReference,
    baseline_report: AttachmentResidualOwnershipReport,
    cue_report: AttachmentResidualOwnershipReport,
    gold_adjudications: tuple[AttachmentResidualGoldAdjudication, ...],
    probabilities: Mapping[tuple[str, int], AttachmentAnswerProbability | None],
) -> AttachmentResidualCueAblationReport:
    """Compare each cue answer with the exact CEA-1.7 baseline answer."""
    baseline_by_task = {item.task.id: item for item in baseline_report.cases}
    cue_by_task = {item.task.id: item for item in cue_report.cases}
    if set(baseline_by_task) != set(cue_by_task):
        raise ValueError("Cue ablation task inventory differs from the baseline.")
    adjudication_by_task = {item.task_id: item for item in gold_adjudications}
    cases: list[AttachmentResidualCueAblationCase] = []
    for task_id in sorted(baseline_by_task):
        baseline = baseline_by_task[task_id]
        cue = cue_by_task[task_id]
        if baseline.task != cue.task or baseline.expected_answer != cue.expected_answer:
            raise ValueError("Cue ablation case differs from its baseline task or Gold answer.")
        baseline_answers = tuple(item.decision.answer for item in baseline.observations)
        cue_answers = tuple(
            (
                item.decision.answer
                if item.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
                else None
            )
            for item in cue.observations
        )
        if len(baseline_answers) != 2 or len(cue_answers) != 2:
            raise ValueError("Cue ablation case requires two repetitions.")
        baseline_first, baseline_second = baseline_answers
        if baseline_first is None or baseline_second is None:
            raise ValueError("Cue ablation baseline contains an unresolved answer.")
        typed_cue = (cue_answers[0], cue_answers[1])
        case_probabilities = (
            probabilities.get((task_id, 1)),
            probabilities.get((task_id, 2)),
        )
        inherited_expected = baseline.expected_answer
        adjudication = adjudication_by_task.get(task_id)
        expected = adjudication.corrected_answer if adjudication is not None else inherited_expected
        cases.append(
            AttachmentResidualCueAblationCase(
                task_id=task_id,
                edge_id=baseline.task.edge_filter_task.edge.id,
                inherited_expected_answer=inherited_expected,
                expected_answer=expected,
                baseline_answers=(baseline_first, baseline_second),
                cue_answers=typed_cue,
                cue_probabilities=case_probabilities,
                stable_cue_result=(typed_cue[0] is not None and typed_cue[0] is typed_cue[1]),
                positive_yes_observation_count=(
                    sum(item is AttachmentEdgeFilterAnswerValue.YES for item in typed_cue)
                    if expected == "Y"
                    else 0
                ),
                positive_recovery=(
                    expected == "Y"
                    and typed_cue
                    == (
                        AttachmentEdgeFilterAnswerValue.YES,
                        AttachmentEdgeFilterAnswerValue.YES,
                    )
                ),
                negative_regression=(
                    expected == "N"
                    and any(item is not AttachmentEdgeFilterAnswerValue.NO for item in typed_cue)
                ),
            )
        )
    values = tuple(cases)
    answers = tuple(answer for case in values for answer in case.cue_answers)
    yes_count = sum(item is AttachmentEdgeFilterAnswerValue.YES for item in answers)
    no_count = sum(item is AttachmentEdgeFilterAnswerValue.NO for item in answers)
    unclear_count = sum(item is AttachmentEdgeFilterAnswerValue.UNCLEAR for item in answers)
    unresolved_count = sum(item is None for item in answers)
    probability_count = sum(item is not None for case in values for item in case.cue_probabilities)
    stable_count = sum(item.stable_cue_result for item in values)
    positive_yes = sum(item.positive_yes_observation_count for item in values)
    positive_recoveries = sum(item.positive_recovery for item in values)
    negative_regressions = sum(item.negative_regression for item in values)
    if unresolved_count or probability_count != 20:
        outcome = AttachmentResidualCueAblationOutcome.INCONCLUSIVE
    elif positive_yes == 0:
        outcome = AttachmentResidualCueAblationOutcome.FALSIFIED
    elif positive_recoveries and not negative_regressions and stable_count == 10:
        outcome = AttachmentResidualCueAblationOutcome.SUPPORTED
    else:
        outcome = AttachmentResidualCueAblationOutcome.MIXED
    draft = AttachmentResidualCueAblationReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        baseline_prompt=baseline_prompt,
        cue_prompt=cue_prompt,
        gold_adjudications=gold_adjudications,
        cases=values,
        cue_yes_count=yes_count,
        cue_no_count=no_count,
        cue_unclear_count=unclear_count,
        unresolved_count=unresolved_count,
        probability_evidence_count=probability_count,
        stable_case_count=stable_count,
        positive_yes_observation_count=positive_yes,
        positive_recovery_case_count=positive_recoveries,
        negative_regression_case_count=negative_regressions,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentResidualCueAblationReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_residual_cue_ablation_fingerprint(draft),
    )


def render_residual_cue_ablation_review(
    report: AttachmentResidualCueAblationReport,
    cue_report: AttachmentResidualOwnershipReport,
) -> str:
    """Render compact answer transitions and probability evidence."""
    cue_by_task = {item.task.id: item for item in cue_report.cases}
    positive_count = sum(item.expected_answer == "Y" for item in report.cases)
    negative_count = sum(item.expected_answer == "N" for item in report.cases)
    lines = [
        "# CEA-1.8 Demonstration Cue Ablation Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Answer distribution: `Y={report.cue_yes_count}`, `N={report.cue_no_count}`, "
        f"`U={report.cue_unclear_count}`, `unresolved={report.unresolved_count}`",
        "",
        f"Stable cases: `{report.stable_case_count}/10`",
        "",
        f"Positive recoveries: `{report.positive_recovery_case_count}/{positive_count}`",
        "",
        f"Negative regressions: `{report.negative_regression_case_count}/{negative_count}`",
        "",
        "## Cases",
        "",
    ]
    for case in report.cases:
        cue_case = cue_by_task[case.task_id]
        edge = cue_case.task.edge_filter_task.edge
        answer_text = "/".join(
            item.value if item is not None else "NONE" for item in case.cue_answers
        )
        score_text = "/".join(
            str(item.attachment_score) if item is not None else "NONE"
            for item in case.cue_probabilities
        )
        lines.extend(
            (
                f"### {case.task_id}",
                "",
                f"> {cue_case.task.edge_filter_task.source_text}",
                "",
                f"Candidate: `{edge.candidate_range.text}`",
                "",
                f"Target Event: `{edge.event_range.text}`",
                "",
                f"Expected: `{case.expected_answer}`",
                "",
                *(
                    (
                        f"Inherited Attachment Gold: `{case.inherited_expected_answer}`",
                        "",
                        "Residual Ownership Gold: operator-adjudicated",
                        "",
                    )
                    if case.inherited_expected_answer != case.expected_answer
                    else ()
                ),
                "Baseline: `N/N`",
                "",
                f"Cue-Balanced Prompt: `{answer_text}`",
                "",
                f"Cue attachment scores (rep1/rep2): `{score_text}`",
                "",
                "Execution records:",
                "",
                *(f"- `{item.execution_record.path}`" for item in cue_case.observations),
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_residual_cue_ablation_handoff(
    report: AttachmentResidualCueAblationReport,
    cue_report: AttachmentResidualOwnershipReport,
    *,
    baseline_prompt_text: str,
    cue_prompt_text: str,
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained independent-review package."""
    lines = [
        "# CEA-1.8 Demonstration Cue Ablation Handoff",
        "",
        "## Hypothesis",
        "",
        "> The `NONE` versus listed Other Event demonstration cue caused part of the "
        "CEA-1.7 constant-`N` collapse.",
        "",
        "## Intervention",
        "",
        "KoteKomi reused the exact ten CEA-1.7 tasks.",
        "",
        "Only the positive example block changed.",
        "",
        "The changed positive demonstration adds a second Event, lists that Other Event, "
        "and changes the Target Event label.",
        "",
        "The criterion, negative example, task renderer, model, seed, and temperature "
        "stayed fixed.",
        "",
        "The Baseline answers are inherited from CEA-1.7; CEA-1.8 did not re-execute the "
        "Baseline Prompt or collect Baseline Probability Evidence.",
        "",
        "KoteKomi requested ten token alternatives for Cue-Arm Probability Evidence.",
        "",
        "Production integration remained inactive.",
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
        "## Cue-Balanced Prompt",
        "",
        "~~~~text",
        cue_prompt_text.rstrip(),
        "~~~~",
        "",
        "## Results",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        "Baseline answers: `N=20`, `Y=0`, `U=0`",
        "",
        f"Cue answers: `N={report.cue_no_count}`, `Y={report.cue_yes_count}`, "
        f"`U={report.cue_unclear_count}`, `unresolved={report.unresolved_count}`",
        "",
        f"Positive recoveries: `{report.positive_recovery_case_count}/8`",
        "",
        f"Negative regressions: `{report.negative_regression_case_count}/2`",
        "",
        "`supported` means the complete positive-demonstration shape caused repeat-stable "
        "positive recoveries without a negative regression in this development diagnostic.",
        "",
        "It does not mean the attachment task is production-ready: four of eight positive "
        "cases remained false negatives, and frozen validation was not run.",
        "",
        f"Stable cases: `{report.stable_case_count}/10`",
        "",
        f"Cue-Arm Probability Evidence: `{report.probability_evidence_count}/20`",
        "",
        f"Comparison report fingerprint: `{report.result_fingerprint}`",
        "",
        f"Cue-arm report fingerprint: `{cue_report.result_fingerprint}`",
        "",
        f"The cue-arm report outcome is `{cue_report.outcome.value}` under inherited 7-positive/"
        "3-negative Attachment Gold.",
        "",
        "The comparison outcome uses operator-adjudicated 8-positive/2-negative Residual "
        "Ownership Gold.",
        "",
        "One inherited Attachment Gold answer was operator-adjudicated from `N` to `Y` because "
        "exact-range Attachment membership does not answer semantic Residual Ownership.",
        "",
        "## Exact evidence",
        "",
        "Use `comparison-review.md` for every answer transition and score.",
        "",
        "Use `ablation-report.json` for exact model inputs and raw outputs.",
        "",
        "Use each execution path in `comparison-review.md` for its ModelRun and stage trace.",
        "",
        "## Known limitations",
        "",
        "This experiment tests one complete positive-demonstration shape change.",
        "",
        "It does not isolate the listed Other Event as the sole cause.",
        "",
        "Repeat-stable means deterministic under the pinned runtime; it is not independent "
        "robustness evidence.",
        "",
        "Without paired Baseline Probability Evidence, the experiment cannot distinguish a "
        "selective repair from a general shift toward `Y`.",
        "",
        "It does not repair the Residual Ownership criterion or Candidate Remainder rendering.",
        "",
        "The `As ... targeted ...` case preserves inherited Attachment Gold `N` as historical "
        "evidence.",
        "",
        "CEA-1.8 applies the operator-approved Residual Ownership answer `Y` and keeps both "
        "answers visible.",
        "",
        "## Review questions",
        "",
        "1. Does the prompt diff isolate the declared cue?",
        "2. Do the answer transitions establish a Cue Effect?",
        "3. Do the probabilities show confident or marginal transitions?",
        "4. What is the smallest next task-contract experiment?",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _prompt_parts(value: str) -> tuple[str, str, str]:
    if value.count(_EXAMPLE_ONE) != 1 or value.count(_EXAMPLE_TWO) != 1:
        raise ValueError("Cue ablation prompt example markers drifted.")
    prefix, remainder = value.split(_EXAMPLE_ONE, 1)
    example, suffix = remainder.split(_EXAMPLE_TWO, 1)
    return prefix, example, suffix
