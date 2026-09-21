"""Evaluation and review rendering for CEA-1.13."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, cast

from kotekomi_application import (
    AttachmentCalibratedTerminationPreflight,
    AttachmentCalibratedTerminationReport,
    AttachmentEvidenceReference,
    AttachmentPartwiseCaseEvaluation,
    AttachmentPartwiseObservation,
    AttachmentPartwisePreflight,
    AttachmentPartwiseReport,
    AttachmentRemainderPartKind,
    AttachmentRemainderPartTask,
    aggregate_attachment_remainder_part_answers,
    attachment_partwise_fingerprint,
    attachment_partwise_outcome,
    build_attachment_remainder_part_tasks,
)


def build_partwise_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    whole_prompt: AttachmentEvidenceReference,
    part_prompt: AttachmentEvidenceReference,
    calibrated_preflight: AttachmentCalibratedTerminationPreflight,
    calibrated_report: AttachmentCalibratedTerminationReport,
    expected_answer_by_task: Mapping[str, Literal["Y", "N"]],
    configured_max_output_tokens: int,
) -> AttachmentPartwisePreflight:
    """Build one Gold-separated input inventory from sealed CEA-1.12 evidence."""
    if not calibrated_report.mechanism_proof:
        raise ValueError("CEA-1.13 requires the supported CEA-1.12 mechanism proof.")
    tasks = calibrated_preflight.tasks
    report_by_id = {item.task.id: item for item in calibrated_report.cases}
    if set(report_by_id) != {item.id for item in tasks}:
        raise ValueError("CEA-1.12 preflight and report task inventories differ.")
    archived_answers: dict[str, Literal["Y", "N", "U"]] = {}
    for task in tasks:
        observations = report_by_id[task.id].observations
        answers = tuple(
            item.decision.answer.value if item.decision.answer is not None else None
            for item in observations
        )
        if len(observations) != 2 or answers[0] is None or answers[0] != answers[1]:
            raise ValueError("CEA-1.13 requires stable CEA-1.12 answers.")
        archived_answers[task.id] = cast(Literal["Y", "N", "U"], answers[0])
    part_tasks = tuple(
        part for task in tasks for part in build_attachment_remainder_part_tasks(task)
    )
    draft = AttachmentPartwisePreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        whole_prompt=whole_prompt,
        part_prompt=part_prompt,
        tasks=tasks,
        part_tasks=part_tasks,
        expected_answer_by_task=dict(sorted(expected_answer_by_task.items())),
        archived_whole_answer_by_task=dict(sorted(archived_answers.items())),
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentPartwisePreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_partwise_fingerprint(draft),
    )


def build_partwise_report(
    *,
    preflight: AttachmentPartwisePreflight,
    inputs: tuple[AttachmentEvidenceReference, ...],
    whole_observations: Sequence[AttachmentPartwiseObservation],
    part_observations: Sequence[AttachmentPartwiseObservation],
) -> AttachmentPartwiseReport:
    """Compare fresh Whole Arm answers with deterministic Part Aggregates."""
    whole_by_task: dict[str, list[AttachmentPartwiseObservation]] = {}
    for observation in whole_observations:
        whole_by_task.setdefault(observation.residual_task_id, []).append(observation)
    part_by_task: dict[str, list[AttachmentPartwiseObservation]] = {}
    for observation in part_observations:
        part_by_task.setdefault(observation.residual_task_id, []).append(observation)
    cases: list[AttachmentPartwiseCaseEvaluation] = []
    for task in preflight.tasks:
        part_tasks = tuple(
            item for item in preflight.part_tasks if item.residual_task_id == task.id
        )
        whole = tuple(sorted(whole_by_task.get(task.id, ()), key=lambda item: item.repetition))
        part_number = {item.id: item.part_number for item in part_tasks}
        part = tuple(
            sorted(
                part_by_task.get(task.id, ()),
                key=lambda item: (item.repetition, part_number[item.part_task_id or ""]),
            )
        )
        whole_answers = tuple(_answer(item) for item in whole)
        aggregate_answers: tuple[Literal["Y", "N", "U"] | None, ...] = tuple(
            _aggregate_for_repetition(part_tasks, part, repetition) for repetition in (1, 2)
        )
        expected = preflight.expected_answer_by_task[task.id]
        whole_passed = len(whole_answers) == 2 and all(item == expected for item in whole_answers)
        part_passed = all(item == expected for item in aggregate_answers)
        cases.append(
            AttachmentPartwiseCaseEvaluation(
                task=task,
                part_tasks=part_tasks,
                expected_answer=expected,
                archived_whole_answer=preflight.archived_whole_answer_by_task[task.id],
                whole_observations=whole,
                part_observations=part,
                whole_answers=cast(tuple[Literal["Y", "N", "U"] | None, ...], whole_answers),
                part_aggregate_answers=aggregate_answers,
                whole_stable=(len(whole_answers) == 2 and whole_answers[0] == whole_answers[1]),
                part_stable=aggregate_answers[0] == aggregate_answers[1],
                whole_passed=whole_passed,
                part_passed=part_passed,
                recovered=not whole_passed and part_passed,
                regressed=whole_passed and not part_passed,
            )
        )
    values = tuple(cases)
    observations = tuple(
        item for case in values for item in (*case.whole_observations, *case.part_observations)
    )
    whole_correct = sum(item.whole_passed for item in values)
    part_correct = sum(item.part_passed for item in values)
    recovered = sum(item.recovered for item in values)
    regressed = sum(item.regressed for item in values)
    strict_count = sum(item.strict_finite_answer for item in observations)
    unresolved_count = sum(_answer(item) is None for item in observations)
    part_negative_correct = sum(item.expected_answer == "N" and item.part_passed for item in values)
    outcome = attachment_partwise_outcome(
        strict_finite_output_count=strict_count,
        unresolved_output_count=unresolved_count,
        stable_whole_case_count=sum(item.whole_stable for item in values),
        stable_part_case_count=sum(item.part_stable for item in values),
        whole_correct_count=whole_correct,
        part_correct_count=part_correct,
        recovered_case_count=recovered,
        regressed_case_count=regressed,
        part_negative_correct_count=part_negative_correct,
    )
    draft = AttachmentPartwiseReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        whole_prompt=preflight.whole_prompt,
        part_prompt=preflight.part_prompt,
        cases=values,
        whole_correct_count=whole_correct,
        part_correct_count=part_correct,
        whole_positive_correct_count=sum(
            item.expected_answer == "Y" and item.whole_passed for item in values
        ),
        part_positive_correct_count=sum(
            item.expected_answer == "Y" and item.part_passed for item in values
        ),
        whole_negative_correct_count=sum(
            item.expected_answer == "N" and item.whole_passed for item in values
        ),
        part_negative_correct_count=part_negative_correct,
        recovered_case_count=recovered,
        regressed_case_count=regressed,
        stable_whole_case_count=sum(item.whole_stable for item in values),
        stable_part_case_count=sum(item.part_stable for item in values),
        strict_finite_output_count=strict_count,
        archived_whole_agreement_count=sum(
            answer == case.archived_whole_answer for case in values for answer in case.whole_answers
        ),
        unresolved_output_count=unresolved_count,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentPartwiseReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_partwise_fingerprint(draft),
    )


def render_partwise_review(report: AttachmentPartwiseReport) -> str:
    """Render exact data-in and data-out for human inspection."""
    lines = [
        "# CEA-1.13 Part-Wise Residual Ownership Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Candidate accuracy: Whole `{report.whole_correct_count}/10`; "
        f"Part `{report.part_correct_count}/10`",
        "",
        f"Positive accuracy: Whole `{report.whole_positive_correct_count}/8`; "
        f"Part `{report.part_positive_correct_count}/8`",
        "",
        f"Negative accuracy: Whole `{report.whole_negative_correct_count}/2`; "
        f"Part `{report.part_negative_correct_count}/2`",
        "",
        f"Recoveries: `{report.recovered_case_count}`",
        "",
        f"Regressions: `{report.regressed_case_count}`",
        "",
        f"Strict finite outputs: `{report.strict_finite_output_count}/54`",
        "",
        f"Fresh Whole answers matching CEA-1.12: `{report.archived_whole_agreement_count}/20`",
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
                f"Expected Candidate answer: `{case.expected_answer}`",
                "",
                f"Archived Whole answer: `{case.archived_whole_answer}`",
                "",
                "Fresh Whole answers: " + _answer_pair(case.whole_answers),
                "",
                "Part Aggregate answers: " + _answer_pair(case.part_aggregate_answers),
                "",
            )
        )
        observations: dict[str, list[AttachmentPartwiseObservation]] = {
            task.id: []
            for task in case.part_tasks
            if task.kind is AttachmentRemainderPartKind.SUBSTANTIVE
        }
        for item in case.part_observations:
            if item.part_task_id is None:
                raise ValueError("Part Arm observation lacks its Part task reference.")
            observations[item.part_task_id].append(item)
        for task in case.part_tasks:
            lines.extend(
                (
                    f"Part R{task.part_number} `{task.kind.value}`: `{task.source_range.text}`",
                    "",
                )
            )
            if task.kind is AttachmentRemainderPartKind.STRUCTURAL:
                lines.extend(("Decision: `deterministic Y`", ""))
                continue
            for observation in observations[task.id]:
                lines.extend(
                    (
                        f"Repetition {observation.repetition} raw output: "
                        f"`{_json_string(observation.raw_output_text)}`",
                        "",
                        f"Repetition {observation.repetition} exact model input:",
                        "",
                        "~~~~text",
                        observation.exact_model_input.rstrip(),
                        "~~~~",
                        "",
                        f"Execution: `{observation.execution_record.path}`",
                        "",
                    )
                )
        lines.extend(
            (
                f"Recovered: `{str(case.recovered).lower()}`",
                "",
                f"Regressed: `{str(case.regressed).lower()}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_partwise_handoff(
    report: AttachmentPartwiseReport,
    *,
    whole_prompt_text: str,
    part_prompt_text: str,
    package_files: tuple[AttachmentEvidenceReference, ...],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained package for independent review."""
    lines = [
        "# CEA-1.13 Part-Wise Residual Ownership Handoff",
        "",
        "## Hypothesis",
        "",
        "> Independent Remainder Part judgments improve corrected Residual Ownership "
        "accuracy without losing a correct Whole Arm answer.",
        "",
        "## Method",
        "",
        "KoteKomi derived eighteen exact Remainder Parts from authoritative source ranges.",
        "",
        "KoteKomi routed seventeen Substantive Parts to Qwen independently.",
        "",
        "KoteKomi retained one Structural Part without a model call.",
        "",
        "Both arms used two repetitions, a two-token request, and frequency penalty zero.",
        "",
        "KoteKomi aggregated Part answers with all-Y, any-N, otherwise-U rules.",
        "",
        "Gold remained outside every model input.",
        "",
        "Production integration remained inactive.",
        "",
        "## Source implementation",
        "",
        f"Public repository: `{source_repository_url}`",
        "",
        f"Source revision: `{source_revision}`",
        "",
        "## Whole Arm Prompt",
        "",
        "~~~~text",
        whole_prompt_text.rstrip(),
        "~~~~",
        "",
        "## Part Arm Prompt",
        "",
        "~~~~text",
        part_prompt_text.rstrip(),
        "~~~~",
        "",
        "## Results",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Report fingerprint: `{report.result_fingerprint}`",
        "",
        f"Candidate accuracy: Whole `{report.whole_correct_count}/10`; "
        f"Part `{report.part_correct_count}/10`",
        "",
        f"Recoveries: `{report.recovered_case_count}`",
        "",
        f"Regressions: `{report.regressed_case_count}`",
        "",
        f"Strict finite outputs: `{report.strict_finite_output_count}/54`",
        "",
        f"Archived Whole agreement: `{report.archived_whole_agreement_count}/20`",
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
            "1. Does the experiment isolate local part judgment from deterministic aggregation?",
            "2. Do the exact Part answers explain each recovery or regression?",
            "3. Does any Candidate-level Gold answer conflict with the source text?",
            "4. Is the declared runtime contract sufficient for semantic comparison?",
            "5. What is the smallest justified next event-attachment experiment?",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _aggregate_for_repetition(
    part_tasks: tuple[AttachmentRemainderPartTask, ...],
    observations: tuple[AttachmentPartwiseObservation, ...],
    repetition: int,
) -> Literal["Y", "N", "U"] | None:
    return aggregate_attachment_remainder_part_answers(
        part_tasks,
        tuple(item for item in observations if item.repetition == repetition),
    )


def _answer(
    observation: AttachmentPartwiseObservation,
) -> Literal["Y", "N", "U"] | None:
    if not observation.strict_finite_answer or observation.decision.answer is None:
        return None
    return observation.decision.answer.value


def _answer_pair(values: tuple[Literal["Y", "N", "U"] | None, ...]) -> str:
    return " | ".join(f"`{item or 'UNRESOLVED'}`" for item in values)


def _json_string(value: str | None) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
