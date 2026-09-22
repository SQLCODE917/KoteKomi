"""Prepare and evaluate the CEA-1.22 Nested Event Ownership diagnostic."""

from __future__ import annotations

import json
from base64 import b64decode
from collections.abc import Mapping, Sequence

from kotekomi_application import (
    AttachmentBlindReviewOutcome,
    AttachmentBlindReviewReport,
    AttachmentEvidenceReference,
    AttachmentNestedEventCase,
    AttachmentNestedEventEvaluation,
    AttachmentNestedEventObservation,
    AttachmentNestedEventPreflight,
    AttachmentNestedEventReport,
    AttachmentPoolArm,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    CompetitiveAttachmentMatrix,
    attachment_nested_event_case_id,
    attachment_nested_event_fingerprint,
    attachment_nested_event_ownership_model_task_input,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    classify_attachment_nested_event_outcome,
)


def build_attachment_nested_event_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
    blind_report: AttachmentBlindReviewReport,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
) -> AttachmentNestedEventPreflight:
    """Build the exact five-case diagnostic from CEA-1.21 exclusions."""
    if (
        blind_report.outcome is not AttachmentBlindReviewOutcome.MIXED
        or blind_report.excluded_yes_count != 4
        or blind_report.excluded_no_count != 1
        or blind_report.excluded_unclear_count != 0
    ):
        raise ValueError("CEA-1.22 requires the completed mixed CEA-1.21 result.")
    matrix_by_id = {item.id: item for item in matrices}
    if len(matrix_by_id) != len(matrices):
        raise ValueError("CEA-1.22 matrices contain duplicate IDs.")
    cases: list[AttachmentNestedEventCase] = []
    for evaluation in blind_report.evaluations:
        blind_case = evaluation.case
        if blind_case.structural_selected:
            continue
        if evaluation.decision.answer == "U":
            raise ValueError("CEA-1.22 cannot use an unclear blind label.")
        matrix = matrix_by_id.get(blind_case.matrix_id)
        if matrix is None:
            raise ValueError("CEA-1.22 lacks one blind-review matrix.")
        candidate = next(
            (item for item in matrix.candidates if item.id == blind_case.candidate_id),
            None,
        )
        target = next(
            (
                item
                for item in matrix.event_options
                if item.source_grounded_event_id == blind_case.event_id
            ),
            None,
        )
        if candidate is None or target is None:
            raise ValueError("CEA-1.22 matrix lacks one Candidate or target Event.")
        if (
            candidate.start,
            candidate.end,
            candidate.text,
            target.start,
            target.end,
            target.text,
        ) != (
            blind_case.candidate_range.start,
            blind_case.candidate_range.end,
            blind_case.candidate_range.text,
            blind_case.event_range.start,
            blind_case.event_range.end,
            blind_case.event_range.text,
        ):
            raise ValueError("CEA-1.22 exact ranges drifted from CEA-1.21.")
        edge_values = {
            "phase": blind_case.phase,
            "source_segment_id": matrix.source_segment_id,
            "source_text_sha256": matrix.source_text_sha256,
            "candidate_id": candidate.id,
            "source_grounded_event_id": target.source_grounded_event_id,
            "candidate_start": candidate.start,
            "candidate_end": candidate.end,
            "event_start": target.start,
            "event_end": target.end,
        }
        edge = AttachmentPoolEdge(
            id=attachment_pool_edge_id(**edge_values),
            phase=blind_case.phase,
            source_segment_id=matrix.source_segment_id,
            source_text_sha256=matrix.source_text_sha256,
            candidate_id=candidate.id,
            source_grounded_event_id=target.source_grounded_event_id,
            candidate_range=AttachmentSourceRange(
                start=candidate.start,
                end=candidate.end,
                text=candidate.text,
            ),
            event_range=AttachmentSourceRange(
                start=target.start,
                end=target.end,
                text=target.text,
            ),
            origins=(AttachmentProposalOrigin.SYNTAX,),
            syntax_arms=tuple(AttachmentPoolArm),
        )
        task = build_attachment_edge_filter_task(
            source_text=blind_case.source_text,
            edge=edge,
            candidate=candidate,
            event_options=matrix.event_options,
        )
        cases.append(
            AttachmentNestedEventCase(
                id=attachment_nested_event_case_id(
                    blind_case_id=blind_case.id,
                    task_id=task.task_id,
                ),
                blind_case_id=blind_case.id,
                phase=blind_case.phase,
                task=task,
                contained_event_ids=blind_case.foreign_event_ids,
                expected_answer=evaluation.decision.answer,
                expected_rationale=evaluation.decision.rationale,
            )
        )
    ordered = tuple(
        sorted(
            cases,
            key=lambda item: (
                item.phase,
                item.task.edge.source_text_sha256,
                item.task.candidate.start,
                item.task.candidate.end,
                item.task.edge.event_range.start,
                item.id,
            ),
        )
    )
    if len(ordered) != 5:
        raise ValueError("CEA-1.22 requires exactly five excluded cases.")
    draft = AttachmentNestedEventPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=prompt,
        cases=ordered,
        case_count=len(ordered),
        expected_yes_count=sum(item.expected_answer == "Y" for item in ordered),
        expected_no_count=sum(item.expected_answer == "N" for item in ordered),
        result_fingerprint="0" * 64,
    )
    return AttachmentNestedEventPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_nested_event_fingerprint(draft),
    )


def build_attachment_nested_event_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    preflight: AttachmentNestedEventPreflight,
    observations: tuple[AttachmentNestedEventObservation, ...],
) -> AttachmentNestedEventReport:
    """Evaluate two complete repetitions against the blind labels."""
    by_case: dict[str, list[AttachmentNestedEventObservation]] = {}
    for item in observations:
        by_case.setdefault(item.case_id, []).append(item)
    expected_ids = {item.id for item in preflight.cases}
    if set(by_case) != expected_ids:
        raise ValueError("CEA-1.22 observation case inventory drifted.")
    evaluations: list[AttachmentNestedEventEvaluation] = []
    for case in preflight.cases:
        repeated = tuple(sorted(by_case[case.id], key=lambda item: item.repetition))
        if len(repeated) != 2:
            raise ValueError("CEA-1.22 requires two observations per case.")
        answers = tuple(item.decision.answer for item in repeated)
        complete = all(item.decision.status.value == "complete" for item in repeated)
        stable = complete and answers[0] is answers[1]
        evaluations.append(
            AttachmentNestedEventEvaluation(
                case=case,
                observations=repeated,
                complete=complete,
                stable=stable,
                correct_decision_count=sum(
                    answer is not None and answer.value == case.expected_answer
                    for answer in answers
                ),
            )
        )
    values = tuple(evaluations)
    flat = tuple(item for value in values for item in value.observations)
    positives = tuple(item for item in values if item.case.expected_answer == "Y")
    negatives = tuple(item for item in values if item.case.expected_answer == "N")
    draft = AttachmentNestedEventReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        evaluations=values,
        outcome=classify_attachment_nested_event_outcome(evaluations=values),
        case_count=len(values),
        observation_count=len(flat),
        complete_observation_count=sum(item.decision.status.value == "complete" for item in flat),
        unresolved_observation_count=sum(item.decision.status.value != "complete" for item in flat),
        stable_case_count=sum(item.stable for item in values),
        positive_correct_decision_count=sum(item.correct_decision_count for item in positives),
        negative_correct_decision_count=sum(item.correct_decision_count for item in negatives),
        model_identity_digests=tuple(
            sorted(
                {
                    item.model_identity_digest
                    for item in flat
                    if item.model_identity_digest is not None
                }
            )
        ),
        model_execution_count=sum(item.runtime_invoked for item in flat),
        model_elapsed_milliseconds=sum(item.elapsed_milliseconds for item in flat),
        result_fingerprint="0" * 64,
    )
    return AttachmentNestedEventReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_nested_event_fingerprint(draft),
    )


def render_attachment_nested_event_preflight(
    preflight: AttachmentNestedEventPreflight,
) -> str:
    """Render every exact task before model execution."""
    lines = [
        "# CEA-1.22 Nested Event Ownership Preflight",
        "",
        f"Cases: `{preflight.case_count}`",
        "",
        f"Blind Y/N labels: `{preflight.expected_yes_count}` / `{preflight.expected_no_count}`",
        "",
    ]
    for case in preflight.cases:
        lines.extend(
            [
                f"## {case.id}",
                "",
                "Expected answer is sealed from the model task.",
                "",
                "Exact model task input:",
                "",
                "~~~~text",
                attachment_nested_event_ownership_model_task_input(case.task)
                .decode("utf-8")
                .rstrip(),
                "~~~~",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_nested_event_review(
    report: AttachmentNestedEventReport,
    *,
    prompt_text: str,
) -> str:
    """Render exact model input, output, and evaluation for every case."""
    lines = [
        "# CEA-1.22 Nested Event Ownership Diagnostic",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Cases: `{report.case_count}`",
        "",
        f"Observations: `{report.observation_count}`",
        "",
        f"Stable cases: `{report.stable_case_count}`",
        "",
        f"Correct positive decisions: `{report.positive_correct_decision_count}` / `8`",
        "",
        f"Correct negative decisions: `{report.negative_correct_decision_count}` / `2`",
        "",
        f"Model executions: `{report.model_execution_count}`",
        "",
        f"Model elapsed milliseconds: `{report.model_elapsed_milliseconds}`",
        "",
        "## Prompt",
        "",
        "~~~~text",
        prompt_text.rstrip(),
        "~~~~",
        "",
    ]
    for evaluation in report.evaluations:
        case = evaluation.case
        lines.extend(
            [
                f"## {case.id}",
                "",
                f"Blind expected answer: `{case.expected_answer}`",
                "",
                f"Blind rationale: {case.expected_rationale}",
                "",
                "Exact task input:",
                "",
                "~~~~text",
                attachment_nested_event_ownership_model_task_input(case.task)
                .decode("utf-8")
                .rstrip(),
                "~~~~",
                "",
            ]
        )
        for observation in evaluation.observations:
            raw = (
                b64decode(observation.raw_output_base64).decode("utf-8", errors="replace")
                if observation.raw_output_base64 is not None
                else "<no output>"
            )
            answer = (
                observation.decision.answer.value
                if observation.decision.answer is not None
                else "none"
            )
            lines.extend(
                [
                    f"Repetition {observation.repetition} status: "
                    f"`{observation.decision.status.value}`",
                    "",
                    f"Repetition {observation.repetition} answer: `{answer}`",
                    "",
                    f"Repetition {observation.repetition} exact complete model input:",
                    "",
                    "~~~~text",
                    observation.exact_model_input.rstrip(),
                    "~~~~",
                    "",
                    f"Repetition {observation.repetition} raw output: "
                    f"`{json.dumps(raw, ensure_ascii=False)}`",
                    "",
                ]
            )
        lines.extend(
            [
                f"Complete: `{evaluation.complete}`",
                "",
                f"Stable: `{evaluation.stable}`",
                "",
                f"Correct decisions: `{evaluation.correct_decision_count}` / `2`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_nested_event_handoff(
    report: AttachmentNestedEventReport,
    *,
    prompt_text: str,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained second-opinion request."""
    return "\n".join(
        [
            "# CEA-1.22 Nested Event Ownership Diagnostic Handoff",
            "",
            "Verify each expected answer against the exact source.",
            "",
            "Verify that the task asks only Nested Event ownership.",
            "",
            "Verify the two-repetition result and terminal outcome.",
            "",
            "Assess whether the task can proceed to a cross-document transfer catalog.",
            "",
            "This five-case, one-document diagnostic cannot establish transfer.",
            "",
            "CEA-1.21 labels came from Claude Opus; another Claude Opus review is a "
            "same-model-family consistency check, not independent human validation.",
            "",
            render_attachment_nested_event_review(report, prompt_text=prompt_text).rstrip(),
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


def attachment_nested_event_case_by_task_id(
    cases: tuple[AttachmentNestedEventCase, ...],
) -> Mapping[str, AttachmentNestedEventCase]:
    """Return a complete one-to-one task lookup."""
    result = {item.task.task_id: item for item in cases}
    if len(result) != len(cases):
        raise ValueError("CEA-1.22 cases contain duplicate task IDs.")
    return result
