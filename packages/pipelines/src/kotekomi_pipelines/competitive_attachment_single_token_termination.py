"""Deterministic evaluation for CEA-1.11 single-token termination."""

from __future__ import annotations

from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEvidenceReference,
    AttachmentResidualOwnershipTask,
    AttachmentSingleTokenCase,
    AttachmentSingleTokenObservation,
    AttachmentSingleTokenPreflight,
    AttachmentSingleTokenReport,
    attachment_single_token_fingerprint,
    attachment_single_token_outcome,
)


def build_single_token_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    bare_prompt: AttachmentEvidenceReference,
    tasks: tuple[AttachmentResidualOwnershipTask, ...],
    archived_bare_argmax_by_task: dict[str, AttachmentEdgeFilterAnswerValue],
    configured_max_output_tokens: int,
) -> AttachmentSingleTokenPreflight:
    """Build one digest-bound CEA-1.11 preflight."""
    ordered_tasks = tuple(sorted(tasks, key=lambda item: item.id))
    ordered_argmax = {item.id: archived_bare_argmax_by_task[item.id] for item in ordered_tasks}
    draft = AttachmentSingleTokenPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        bare_prompt=bare_prompt,
        tasks=ordered_tasks,
        archived_bare_argmax_by_task=ordered_argmax,
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentSingleTokenPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_single_token_fingerprint(draft),
    )


def build_single_token_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    preflight: AttachmentSingleTokenPreflight,
    observations: tuple[AttachmentSingleTokenObservation, ...],
) -> AttachmentSingleTokenReport:
    """Align two repetitions and build one terminal report."""
    by_key = {(item.task_id, item.repetition): item for item in observations}
    expected_keys = {(task.id, repetition) for task in preflight.tasks for repetition in (1, 2)}
    if len(by_key) != 20 or set(by_key) != expected_keys:
        raise ValueError("Single-Token observations do not cover both repetitions.")
    cases: list[AttachmentSingleTokenCase] = []
    for task in preflight.tasks:
        values = (by_key[(task.id, 1)], by_key[(task.id, 2)])
        answers = tuple(item.decision.answer for item in values)
        evidence = tuple(item.finite_label_evidence for item in values)
        cases.append(
            AttachmentSingleTokenCase(
                task=task,
                archived_bare_argmax=preflight.archived_bare_argmax_by_task[task.id],
                observations=values,
                repetition_answer_agrees=(
                    all(item.strict_valid_output for item in values) and answers[0] is answers[1]
                ),
                repetition_argmax_agrees=(
                    evidence[0] is not None
                    and evidence[1] is not None
                    and evidence[0].finite_label_argmax is evidence[1].finite_label_argmax
                ),
            )
        )
    case_values = tuple(cases)
    flat = tuple(item for case in case_values for item in case.observations)
    probability_count = sum(item.finite_label_evidence is not None for item in flat)
    one_token_count = sum(item.output_is_one_token for item in flat)
    strict_count = sum(item.strict_valid_output for item in flat)
    observed_argmax_count = sum(item.observed_answer_matches_live_argmax for item in flat)
    archived_argmax_count = sum(item.live_argmax_matches_archived for item in flat)
    answer_agreement_count = sum(item.repetition_answer_agrees for item in case_values)
    argmax_agreement_count = sum(item.repetition_argmax_agrees for item in case_values)
    outcome = attachment_single_token_outcome(
        probability_evidence_count=probability_count,
        one_token_output_count=one_token_count,
        strict_valid_output_count=strict_count,
        observed_answer_argmax_match_count=observed_argmax_count,
        archived_argmax_match_count=archived_argmax_count,
        repetition_answer_agreement_count=answer_agreement_count,
        repetition_argmax_agreement_count=argmax_agreement_count,
    )
    draft = AttachmentSingleTokenReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=preflight.bare_prompt,
        cases=case_values,
        probability_evidence_count=probability_count,
        one_token_output_count=one_token_count,
        strict_valid_output_count=strict_count,
        observed_answer_argmax_match_count=observed_argmax_count,
        archived_argmax_match_count=archived_argmax_count,
        repetition_answer_agreement_count=answer_agreement_count,
        repetition_argmax_agreement_count=argmax_agreement_count,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentSingleTokenReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_single_token_fingerprint(draft),
    )


def render_single_token_review(report: AttachmentSingleTokenReport) -> str:
    """Render exact data-in and data-out for human review."""
    lines = [
        "# CEA-1.11 Single-Token Termination Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Probability Evidence: `{report.probability_evidence_count}/20`",
        "",
        f"One-token outputs: `{report.one_token_output_count}/20`",
        "",
        f"Strict valid outputs: `{report.strict_valid_output_count}/20`",
        "",
        f"Observed Answer-to-live-Argmax matches: `{report.observed_answer_argmax_match_count}/20`",
        "",
        f"Archived Bare Argmax matches: `{report.archived_argmax_match_count}/20`",
        "",
        f"Repetition answer agreements: `{report.repetition_answer_agreement_count}/10`",
        "",
        f"Repetition Argmax agreements: `{report.repetition_argmax_agreement_count}/10`",
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
                f"Archived Bare Argmax: `{case.archived_bare_argmax.value}`",
                "",
            )
        )
        for observation in case.observations:
            lines.extend(
                (
                    f"Repetition {observation.repetition} exact model input:",
                    "",
                    "~~~~text",
                    observation.exact_model_input.rstrip(),
                    "~~~~",
                    "",
                    f"Repetition {observation.repetition} raw output: "
                    f"`{observation.raw_output_text}`",
                    "",
                    f"Repetition {observation.repetition} Observed Answer: "
                    f"`{_observed_answer(observation)}`",
                    "",
                    f"Repetition {observation.repetition} live Argmax: "
                    f"`{_live_argmax(observation)}`",
                    "",
                    f"Repetition {observation.repetition} execution: "
                    f"`{observation.execution_record.path}`",
                    "",
                    f"Repetition {observation.repetition} ModelRun status: "
                    f"`{observation.model_run_status.value}`",
                    "",
                    f"Repetition {observation.repetition} runtime error: "
                    f"`{_runtime_error(observation)}`",
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def render_single_token_handoff(
    report: AttachmentSingleTokenReport,
    *,
    prompt_text: str,
    package_files: tuple[AttachmentEvidenceReference, ...],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render one self-contained second-opinion package."""
    lines = [
        "# CEA-1.11 Single-Token Termination Handoff",
        "",
        "## Hypothesis",
        "",
        "> A one-token generation limit preserves each archived Bare Arm first-token "
        "decision and produces exact, repeatable finite answers.",
        "",
        "## Boundaries",
        "",
        "The two repetitions use the same ten tasks, Bare Prompt, Candidate Remainder "
        "renderer, model, seed, temperature, and finite answer schema.",
        "",
        "The effective output limit is the only change from the archived Bare Arm.",
        "",
        "Gold does not determine the outcome.",
        "",
        "Invalid output is not repaired.",
        "",
        "Production integration remains inactive.",
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
        f"Report fingerprint: `{report.result_fingerprint}`",
        "",
        f"Probability Evidence: `{report.probability_evidence_count}/20`",
        "",
        f"One-token outputs: `{report.one_token_output_count}/20`",
        "",
        f"Strict valid outputs: `{report.strict_valid_output_count}/20`",
        "",
        f"Observed Answer-to-live-Argmax matches: `{report.observed_answer_argmax_match_count}/20`",
        "",
        f"Archived Bare Argmax matches: `{report.archived_argmax_match_count}/20`",
        "",
        f"Repetition answer agreements: `{report.repetition_answer_agreement_count}/10`",
        "",
        f"Repetition Argmax agreements: `{report.repetition_argmax_agreement_count}/10`",
        "",
        "## Exact cases",
        "",
        render_single_token_review(report).rstrip(),
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
            "1. Does the experiment isolate output length from semantic task content?",
            "2. Does it establish exact-output reliability without post-hoc repair?",
            "3. Does it establish same-contract semantic repeatability?",
            "4. Is per-Remainder-part attachment now the smallest useful semantic test?",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _observed_answer(observation: AttachmentSingleTokenObservation) -> str:
    answer = observation.decision.answer
    return answer.value if observation.strict_valid_output and answer is not None else "invalid"


def _live_argmax(observation: AttachmentSingleTokenObservation) -> str:
    evidence = observation.finite_label_evidence
    return evidence.finite_label_argmax.value if evidence is not None else "missing"


def _runtime_error(observation: AttachmentSingleTokenObservation) -> str:
    if observation.model_error_code is None:
        return "none"
    return f"{observation.model_error_code}: {observation.model_error_message}"
