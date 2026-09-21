"""Evaluation and review rendering for CEA-1.14."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Literal, cast

from kotekomi_application import (
    AttachmentCandidateMarkerArm,
    AttachmentCandidateMarkerArmEvaluation,
    AttachmentCandidateMarkerCaseEvaluation,
    AttachmentCandidateMarkerObservation,
    AttachmentCandidateMarkerPreflight,
    AttachmentCandidateMarkerReport,
    AttachmentEvidenceReference,
    AttachmentPartwiseReport,
    AttachmentResidualOwnershipTask,
    attachment_candidate_marker_fingerprint,
    attachment_candidate_marker_outcome,
    build_attachment_candidate_marker_view,
)


def build_candidate_marker_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
    predecessor: AttachmentPartwiseReport,
    configured_max_output_tokens: int,
) -> AttachmentCandidateMarkerPreflight:
    """Build one Gold-separated input inventory from sealed CEA-1.13 evidence."""
    if (
        predecessor.whole_correct_count != 7
        or predecessor.part_correct_count != 3
        or predecessor.recovered_case_count != 1
        or predecessor.regressed_case_count != 5
        or predecessor.outcome.value != "mixed"
    ):
        raise ValueError("CEA-1.14 requires the exact reviewed CEA-1.13 result.")
    tasks = tuple(item.task for item in predecessor.cases)
    expected = {item.task.id: item.expected_answer for item in predecessor.cases}
    baseline = {
        item.task.id: cast(tuple[Literal["Y", "N", "U"], ...], item.whole_answers)
        for item in predecessor.cases
    }
    identities = {
        item.model_identity_digest for case in predecessor.cases for item in case.whole_observations
    }
    if len(identities) != 1:
        raise ValueError("CEA-1.13 Whole Arm used more than one model identity.")
    views = tuple(
        build_attachment_candidate_marker_view(task, arm)
        for task in tasks
        for arm in AttachmentCandidateMarkerArm
    )
    draft = AttachmentCandidateMarkerPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=prompt,
        tasks=tasks,
        views=views,
        expected_answer_by_task=dict(sorted(expected.items())),
        baseline_answers_by_task=dict(sorted(baseline.items())),
        expected_model_identity_digest=next(iter(identities)),
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentCandidateMarkerPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_candidate_marker_fingerprint(draft),
    )


def build_candidate_marker_report(
    *,
    preflight: AttachmentCandidateMarkerPreflight,
    inputs: tuple[AttachmentEvidenceReference, ...],
    observations: Sequence[AttachmentCandidateMarkerObservation],
) -> AttachmentCandidateMarkerReport:
    """Compare both marker arms with archived Whole Arm answers."""
    grouped: dict[
        tuple[str, AttachmentCandidateMarkerArm],
        list[AttachmentCandidateMarkerObservation],
    ] = {}
    for observation in observations:
        grouped.setdefault((observation.authoritative_task_id, observation.arm), []).append(
            observation
        )
    cases: list[AttachmentCandidateMarkerCaseEvaluation] = []
    for task in preflight.tasks:
        expected = preflight.expected_answer_by_task[task.id]
        baseline_answers = preflight.baseline_answers_by_task[task.id]
        baseline_passed = all(item == expected for item in baseline_answers)
        arm_results: list[AttachmentCandidateMarkerArmEvaluation] = []
        for arm in AttachmentCandidateMarkerArm:
            view = _view(preflight, task, arm)
            arm_observations = tuple(
                sorted(grouped.get((task.id, arm), ()), key=lambda item: item.repetition)
            )
            answers = tuple(_answer(item) for item in arm_observations)
            stable = len(answers) == 2 and answers[0] == answers[1]
            passed = len(answers) == 2 and all(item == expected for item in answers)
            arm_results.append(
                AttachmentCandidateMarkerArmEvaluation(
                    view=view,
                    expected_answer=expected,
                    baseline_passed=baseline_passed,
                    observations=arm_observations,
                    answers=cast(tuple[Literal["Y", "N", "U"] | None, ...], answers),
                    stable=stable,
                    passed=passed,
                    recovered=not baseline_passed and passed,
                    regressed=baseline_passed and not passed,
                )
            )
        cases.append(
            AttachmentCandidateMarkerCaseEvaluation(
                authoritative_task=task,
                expected_answer=expected,
                baseline_answers=baseline_answers,
                baseline_stable=baseline_answers[0] == baseline_answers[1],
                baseline_passed=baseline_passed,
                arms=tuple(arm_results),
            )
        )
    values = tuple(cases)
    structural = tuple(
        _case_arm(item, AttachmentCandidateMarkerArm.STRUCTURAL_TRIM) for item in values
    )
    introducer = tuple(
        _case_arm(item, AttachmentCandidateMarkerArm.INTRODUCER_TRIM) for item in values
    )
    all_observations = tuple(
        item for case in values for arm in case.arms for item in arm.observations
    )
    metrics = {
        "baseline_correct_count": sum(item.baseline_passed for item in values),
        "structural_correct_count": sum(item.passed for item in structural),
        "introducer_correct_count": sum(item.passed for item in introducer),
        "baseline_positive_correct_count": sum(
            item.expected_answer == "Y" and item.baseline_passed for item in values
        ),
        "structural_positive_correct_count": sum(
            item.expected_answer == "Y" and item.passed for item in structural
        ),
        "introducer_positive_correct_count": sum(
            item.expected_answer == "Y" and item.passed for item in introducer
        ),
        "baseline_negative_correct_count": sum(
            item.expected_answer == "N" and item.baseline_passed for item in values
        ),
        "structural_negative_correct_count": sum(
            item.expected_answer == "N" and item.passed for item in structural
        ),
        "introducer_negative_correct_count": sum(
            item.expected_answer == "N" and item.passed for item in introducer
        ),
        "structural_recovered_count": sum(item.recovered for item in structural),
        "structural_regressed_count": sum(item.regressed for item in structural),
        "introducer_recovered_count": sum(item.recovered for item in introducer),
        "introducer_regressed_count": sum(item.regressed for item in introducer),
        "stable_structural_count": sum(item.stable for item in structural),
        "stable_introducer_count": sum(item.stable for item in introducer),
        "strict_finite_output_count": sum(item.strict_finite_answer for item in all_observations),
        "unresolved_output_count": sum(_answer(item) is None for item in all_observations),
    }
    outcome = attachment_candidate_marker_outcome(
        strict_finite_output_count=metrics["strict_finite_output_count"],
        unresolved_output_count=metrics["unresolved_output_count"],
        stable_structural_count=metrics["stable_structural_count"],
        stable_introducer_count=metrics["stable_introducer_count"],
        baseline_correct_count=metrics["baseline_correct_count"],
        introducer_correct_count=metrics["introducer_correct_count"],
        introducer_recovered_count=metrics["introducer_recovered_count"],
        introducer_regressed_count=metrics["introducer_regressed_count"],
    )
    draft = AttachmentCandidateMarkerReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=preflight.prompt,
        cases=values,
        outcome=outcome,
        result_fingerprint="0" * 64,
        baseline_correct_count=metrics["baseline_correct_count"],
        structural_correct_count=metrics["structural_correct_count"],
        introducer_correct_count=metrics["introducer_correct_count"],
        baseline_positive_correct_count=metrics["baseline_positive_correct_count"],
        structural_positive_correct_count=metrics["structural_positive_correct_count"],
        introducer_positive_correct_count=metrics["introducer_positive_correct_count"],
        baseline_negative_correct_count=metrics["baseline_negative_correct_count"],
        structural_negative_correct_count=metrics["structural_negative_correct_count"],
        introducer_negative_correct_count=metrics["introducer_negative_correct_count"],
        structural_recovered_count=metrics["structural_recovered_count"],
        structural_regressed_count=metrics["structural_regressed_count"],
        introducer_recovered_count=metrics["introducer_recovered_count"],
        introducer_regressed_count=metrics["introducer_regressed_count"],
        stable_structural_count=metrics["stable_structural_count"],
        stable_introducer_count=metrics["stable_introducer_count"],
        strict_finite_output_count=metrics["strict_finite_output_count"],
        unresolved_output_count=metrics["unresolved_output_count"],
    )
    return AttachmentCandidateMarkerReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_candidate_marker_fingerprint(draft),
    )


def render_candidate_marker_review(report: AttachmentCandidateMarkerReport) -> str:
    """Render exact data-in and data-out for human inspection."""
    lines = [
        "# CEA-1.14 Candidate Marker Boundary Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Baseline correct: `{report.baseline_correct_count}/10`",
        "",
        f"Structural Trim correct: `{report.structural_correct_count}/10`",
        "",
        f"Introducer Trim correct: `{report.introducer_correct_count}/10`",
        "",
        f"Introducer recoveries: `{report.introducer_recovered_count}`",
        "",
        f"Introducer regressions: `{report.introducer_regressed_count}`",
        "",
        f"Strict finite outputs: `{report.strict_finite_output_count}/40`",
        "",
    ]
    for case in report.cases:
        edge = case.authoritative_task.edge_filter_task.edge
        lines.extend(
            [
                f"## {case.authoritative_task.id}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {_json(case.authoritative_task.edge_filter_task.source_text)}",
                "",
                f"Authoritative Candidate: `{_json(edge.candidate_range.text)}`",
                "",
                f"Target Event: `{_json(edge.event_range.text)}`",
                "",
                f"Expected answer: `{case.expected_answer}`",
                "",
                f"Baseline answers: `{_answer_pair(case.baseline_answers)}`",
                "",
            ]
        )
        for arm in case.arms:
            rendered = arm.view.rendered_task.edge_filter_task.edge.candidate_range.text
            lines.extend(
                [
                    f"### {arm.view.arm.value}",
                    "",
                    f"Rendered Candidate: `{_json(rendered)}`",
                    "",
                    f"Removed prefix: `{_json(_range_text(arm.view.removed_prefix))}`",
                    "",
                    f"Removed suffix: `{_json(_range_text(arm.view.removed_suffix))}`",
                    "",
                    f"Removed introducer: `{_json(_range_text(arm.view.removed_introducer))}`",
                    "",
                    f"Answers: `{_answer_pair(arm.answers)}`",
                    "",
                    f"Passed: `{str(arm.passed).lower()}`",
                    "",
                    f"Recovered: `{str(arm.recovered).lower()}`",
                    "",
                    f"Regressed: `{str(arm.regressed).lower()}`",
                    "",
                ]
            )
            for observation in arm.observations:
                lines.extend(
                    [
                        f"Repetition {observation.repetition} exact model input:",
                        "",
                        "~~~~text",
                        observation.exact_model_input,
                        "~~~~",
                        "",
                        f"Raw output: `{_json(observation.raw_output_text)}`",
                        "",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


def render_candidate_marker_handoff(
    report: AttachmentCandidateMarkerReport,
    *,
    prompt_text: str,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render one self-contained independent-review package."""
    lines = [
        "# CEA-1.14 Candidate Marker Boundary Handoff",
        "",
        "## Review question",
        "",
        "Does moving only the model-visible Candidate marker recover stable Whole Arm "
        "errors without hiding semantic errors or regressing correct decisions?",
        "",
        "## Hypothesis",
        "",
        "A source-preserving Candidate marker boundary can recover a stable Whole Arm "
        "false negative without regressing a correct Whole Arm answer.",
        "",
        "## Result summary",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        "Baseline / Structural / Introducer correct: "
        f"`{report.baseline_correct_count}/10`, "
        f"`{report.structural_correct_count}/10`, "
        f"`{report.introducer_correct_count}/10`",
        "",
        "Introducer recoveries / regressions: "
        f"`{report.introducer_recovered_count}` / "
        f"`{report.introducer_regressed_count}`",
        "",
        "Stable Structural / Introducer cases: "
        f"`{report.stable_structural_count}/10` / "
        f"`{report.stable_introducer_count}/10`",
        "",
        f"Strict finite outputs: `{report.strict_finite_output_count}/40`",
        "",
        f"Unresolved outputs: `{report.unresolved_output_count}`",
        "",
        "Validation executed: `false`",
        "",
        "Production integration: `not_activated`",
        "",
        "ProposedChanges: `0`",
        "",
        "Accepted Ledger changes: `0`",
        "",
        "## Interpretation constraints",
        "",
        "The Authoritative Candidate remains the scored occurrence.",
        "",
        "Each Rendered Candidate remains an exact inner source range.",
        "",
        "A successful development result does not establish a production boundary policy.",
        "",
        "The second `that` case contains a participant and light verb before its Target Event.",
        "",
        "The predecessor evidence did not isolate the complementizer in that case.",
        "",
        "## Questions for independent review",
        "",
        "1. Do all report counts reconcile from the exact cases?",
        "2. Did the experiment change only model-visible Candidate boundaries?",
        "3. Does any Removed Boundary carry semantic content that KoteKomi cannot treat "
        "as neutral?",
        "4. Do recoveries follow from marker placement or from asking a different semantic "
        "question?",
        "5. Are any correct Baseline decisions lost?",
        "6. Does the declared outcome follow from the mutually exclusive gates?",
        "7. What is the smallest next falsifiable experiment?",
        "",
        "## Exact prompt",
        "",
        "~~~~text",
        prompt_text,
        "~~~~",
        "",
        "## Exact case evidence",
        "",
        render_candidate_marker_review(report).rstrip(),
        "",
        "## Package files",
        "",
    ]
    lines.extend(
        f"- `{item.label}`: `{item.path}` (`sha256:{item.sha256}`)"
        for item in sorted(package_files, key=lambda value: value.label)
    )
    lines.extend(
        [
            "",
            f"Source repository: {source_repository_url}",
            "",
            f"Source revision: `{source_revision}`",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
            "",
        ]
    )
    return "\n".join(lines)


def _view(
    preflight: AttachmentCandidateMarkerPreflight,
    task: AttachmentResidualOwnershipTask,
    arm: AttachmentCandidateMarkerArm,
):
    return next(
        item
        for item in preflight.views
        if item.authoritative_task.id == task.id and item.arm is arm
    )


def _case_arm(
    case: AttachmentCandidateMarkerCaseEvaluation,
    arm: AttachmentCandidateMarkerArm,
) -> AttachmentCandidateMarkerArmEvaluation:
    return next(item for item in case.arms if item.view.arm is arm)


def _answer(
    observation: AttachmentCandidateMarkerObservation,
) -> Literal["Y", "N", "U"] | None:
    return observation.decision.answer.value if observation.decision.answer is not None else None


def _answer_pair(values: Sequence[str | None]) -> str:
    return "/".join(item or "unresolved" for item in values)


def _range_text(value: object) -> str | None:
    return cast(str | None, getattr(value, "text", None))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
