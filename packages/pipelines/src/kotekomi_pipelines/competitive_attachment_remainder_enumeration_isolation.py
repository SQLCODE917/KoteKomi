"""Evaluation and review rendering for CEA-1.15."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Literal, cast

from kotekomi_application import (
    ATTACHMENT_ENUMERATION_HARD_CONTROL_TASK_ID,
    ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID,
    AttachmentCandidateMarkerArm,
    AttachmentCandidateMarkerCaseEvaluation,
    AttachmentCandidateMarkerReport,
    AttachmentEvidenceReference,
    AttachmentRemainderEnumerationCaseEvaluation,
    AttachmentRemainderEnumerationObservation,
    AttachmentRemainderEnumerationPreflight,
    AttachmentRemainderEnumerationReport,
    attachment_remainder_enumeration_fingerprint,
    attachment_remainder_enumeration_mechanism,
    attachment_remainder_enumeration_outcome,
    build_attachment_remainder_enumeration_view,
)


def build_remainder_enumeration_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    prompt: AttachmentEvidenceReference,
    predecessor: AttachmentCandidateMarkerReport,
    configured_max_output_tokens: int,
) -> AttachmentRemainderEnumerationPreflight:
    """Build the exact two-case inventory from sealed CEA-1.14 evidence."""
    if (
        predecessor.outcome.value != "supported"
        or predecessor.baseline_correct_count != 7
        or predecessor.structural_correct_count != 7
        or predecessor.introducer_correct_count != 8
        or predecessor.introducer_recovered_count != 1
        or predecessor.introducer_regressed_count != 0
    ):
        raise ValueError("CEA-1.15 requires the exact reviewed CEA-1.14 result.")
    selected_ids = {
        ATTACHMENT_ENUMERATION_HARD_CONTROL_TASK_ID,
        ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID,
    }
    selected = tuple(
        item for item in predecessor.cases if item.authoritative_task.id in selected_ids
    )
    if tuple(item.authoritative_task.id for item in selected) != tuple(sorted(selected_ids)):
        raise ValueError("CEA-1.14 does not contain the exact CEA-1.15 cases.")
    if any(item.expected_answer != "Y" for item in selected):
        raise ValueError("CEA-1.15 inherited Gold answers drifted.")
    views = tuple(
        build_attachment_remainder_enumeration_view(item.authoritative_task) for item in selected
    )
    structural = {
        item.authoritative_task.id: _sealed_answers(
            item,
            AttachmentCandidateMarkerArm.STRUCTURAL_TRIM,
        )
        for item in selected
    }
    introducer = {
        item.authoritative_task.id: _sealed_answers(
            item,
            AttachmentCandidateMarkerArm.INTRODUCER_TRIM,
        )
        for item in selected
    }
    identities = {
        observation.model_identity_digest
        for case in selected
        for arm in case.arms
        for observation in arm.observations
    }
    if len(identities) != 1:
        raise ValueError("CEA-1.14 selected cases used more than one model identity.")
    draft = AttachmentRemainderEnumerationPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=prompt,
        views=views,
        expected_answer_by_task={item.authoritative_task.id: "Y" for item in selected},
        structural_answers_by_task=structural,
        introducer_answers_by_task=introducer,
        expected_model_identity_digest=next(iter(identities)),
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentRemainderEnumerationPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_remainder_enumeration_fingerprint(draft),
    )


def build_remainder_enumeration_report(
    *,
    preflight: AttachmentRemainderEnumerationPreflight,
    inputs: tuple[AttachmentEvidenceReference, ...],
    observations: Sequence[AttachmentRemainderEnumerationObservation],
) -> AttachmentRemainderEnumerationReport:
    """Evaluate four fresh observations against sealed controls."""
    grouped: dict[str, list[AttachmentRemainderEnumerationObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.authoritative_task_id, []).append(observation)
    cases: list[AttachmentRemainderEnumerationCaseEvaluation] = []
    for view in preflight.views:
        task_id = view.authoritative_task.id
        case_observations = tuple(
            sorted(grouped.get(task_id, ()), key=lambda item: item.repetition)
        )
        answers = tuple(_answer(item) for item in case_observations)
        cases.append(
            AttachmentRemainderEnumerationCaseEvaluation(
                view=view,
                expected_answer="Y",
                structural_answers=preflight.structural_answers_by_task[task_id],
                introducer_answers=preflight.introducer_answers_by_task[task_id],
                observations=case_observations,
                fresh_answers=cast(
                    tuple[Literal["Y", "N", "U"] | None, ...],
                    answers,
                ),
                stable=len(answers) == 2 and answers[0] == answers[1],
                passed=len(answers) == 2 and answers == ("Y", "Y"),
            )
        )
    values = tuple(cases)
    all_observations = tuple(item for case in values for item in case.observations)
    stable_count = sum(item.stable for item in values)
    strict_count = sum(item.strict_finite_answer for item in all_observations)
    unresolved_count = sum(_answer(item) is None for item in all_observations)
    recovered = _case(values, ATTACHMENT_ENUMERATION_RECOVERED_TASK_ID)
    control = _case(values, ATTACHMENT_ENUMERATION_HARD_CONTROL_TASK_ID)
    outcome = attachment_remainder_enumeration_outcome(
        strict_finite_output_count=strict_count,
        unresolved_output_count=unresolved_count,
        stable_case_count=stable_count,
        recovered_answers=recovered.fresh_answers,
    )
    mechanism = attachment_remainder_enumeration_mechanism(
        outcome=outcome,
        recovered_answers=recovered.fresh_answers,
        hard_control_answers=control.fresh_answers,
    )
    draft = AttachmentRemainderEnumerationReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=preflight.prompt,
        cases=values,
        stable_case_count=stable_count,
        strict_finite_output_count=strict_count,
        unresolved_output_count=unresolved_count,
        outcome=outcome,
        mechanism=mechanism,
        result_fingerprint="0" * 64,
    )
    return AttachmentRemainderEnumerationReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_remainder_enumeration_fingerprint(draft),
    )


def render_remainder_enumeration_review(
    report: AttachmentRemainderEnumerationReport,
) -> str:
    """Render exact data-in and data-out for human inspection."""
    lines = [
        "# CEA-1.15 Remainder Enumeration Isolation Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Mechanism: `{report.mechanism.value}`",
        "",
        f"Stable cases: `{report.stable_case_count}/2`",
        "",
        f"Strict finite outputs: `{report.strict_finite_output_count}/4`",
        "",
    ]
    for case in report.cases:
        task = case.view.authoritative_task
        edge = task.edge_filter_task.edge
        lines.extend(
            [
                f"## {task.id}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {_json(task.edge_filter_task.source_text)}",
                "",
                f"Authoritative Candidate: `{_json(edge.candidate_range.text)}`",
                "",
                f"Target Event: `{_json(edge.event_range.text)}`",
                "",
                "Authoritative Remainders:",
                "",
                *(f"- `{_json(item.text)}`" for item in task.remainder_ranges),
                "",
                "Filtered Remainders:",
                "",
                *(f"- `{_json(item.text)}`" for item in case.view.filtered_remainder_ranges),
                "",
                "Omitted exact ranges:",
                "",
                *(f"- `{_json(item.text)}`" for item in case.view.omitted_ranges),
                "",
                f"Expected answer: `{case.expected_answer}`",
                "",
                f"Sealed Structural answers: `{_answers(case.structural_answers)}`",
                "",
                f"Sealed Introducer answers: `{_answers(case.introducer_answers)}`",
                "",
                f"Fresh answers: `{_answers(case.fresh_answers)}`",
                "",
            ]
        )
        for observation in case.observations:
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


def render_remainder_enumeration_handoff(
    report: AttachmentRemainderEnumerationReport,
    *,
    prompt_text: str,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained independent-review package."""
    lines = [
        "# CEA-1.15 Remainder Enumeration Isolation Handoff",
        "",
        "## Review question",
        "",
        "Does changing only explicit Remainder enumeration reproduce the CEA-1.14 "
        "recovery while the Candidate marker remains fixed?",
        "",
        "## Result summary",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Mechanism: `{report.mechanism.value}`",
        "",
        f"Stable cases: `{report.stable_case_count}/2`",
        "",
        f"Strict finite outputs: `{report.strict_finite_output_count}/4`",
        "",
        "False-positive safety tested: `false`",
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
        "This probe can identify whether explicit Remainder enumeration is sufficient "
        "for the recovered case.",
        "",
        "It cannot establish false-positive safety because neither eligible case has "
        "Gold answer `N`.",
        "",
        "It cannot activate a production trimming or enumeration policy.",
        "",
        "## Questions for independent review",
        "",
        "1. Do all report counts and fingerprints reconcile?",
        "2. Did Candidate markers, Event markers, passage text, prompt, and model settings "
        "remain fixed?",
        "3. Did only the exact leading `that` enumeration change?",
        "4. Does the mechanism label follow from both exact cases?",
        "5. What is the smallest next falsifiable experiment?",
        "",
        "## Exact prompt",
        "",
        "~~~~text",
        prompt_text,
        "~~~~",
        "",
        "## Exact case evidence",
        "",
        render_remainder_enumeration_review(report).rstrip(),
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


def _sealed_answers(
    case: AttachmentCandidateMarkerCaseEvaluation,
    arm: AttachmentCandidateMarkerArm,
) -> tuple[Literal["Y", "N", "U"], Literal["Y", "N", "U"]]:
    values = next(item for item in case.arms if item.view.arm is arm).answers
    if len(values) != 2 or any(item not in {"Y", "N", "U"} for item in values):
        raise ValueError("CEA-1.14 selected answer evidence is incomplete.")
    return cast(
        tuple[Literal["Y", "N", "U"], Literal["Y", "N", "U"]],
        values,
    )


def _case(
    cases: tuple[AttachmentRemainderEnumerationCaseEvaluation, ...],
    task_id: str,
) -> AttachmentRemainderEnumerationCaseEvaluation:
    return next(item for item in cases if item.view.authoritative_task.id == task_id)


def _answer(
    observation: AttachmentRemainderEnumerationObservation,
) -> Literal["Y", "N", "U"] | None:
    return observation.decision.answer.value if observation.decision.answer is not None else None


def _answers(values: Sequence[str | None]) -> str:
    return "/".join(item or "unresolved" for item in values)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
