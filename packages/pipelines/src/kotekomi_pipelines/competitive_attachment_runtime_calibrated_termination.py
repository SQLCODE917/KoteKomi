"""Deterministic evaluation for CEA-1.12 runtime-calibrated termination."""

from __future__ import annotations

from kotekomi_application import (
    AttachmentCalibratedTerminationCase,
    AttachmentCalibratedTerminationObservation,
    AttachmentCalibratedTerminationPreflight,
    AttachmentCalibratedTerminationReport,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEvidenceReference,
    AttachmentProductionSuitabilityCondition,
    AttachmentResidualOwnershipTask,
    attachment_calibrated_termination_fingerprint,
    attachment_calibrated_termination_mechanism_proof,
    attachment_calibrated_termination_outcome,
)
from kotekomi_domain import ModelRunStatus


def build_calibrated_termination_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    bare_prompt: AttachmentEvidenceReference,
    tasks: tuple[AttachmentResidualOwnershipTask, ...],
    archived_bare_argmax_by_task: dict[str, AttachmentEdgeFilterAnswerValue],
    archived_position_zero_sha256_by_task: dict[str, str],
    expected_model_identity_digest: str,
    configured_max_output_tokens: int,
) -> AttachmentCalibratedTerminationPreflight:
    """Build one digest-bound CEA-1.12 preflight."""
    ordered_tasks = tuple(sorted(tasks, key=lambda item: item.id))
    ordered_argmax = {item.id: archived_bare_argmax_by_task[item.id] for item in ordered_tasks}
    ordered_distributions = {
        item.id: archived_position_zero_sha256_by_task[item.id] for item in ordered_tasks
    }
    draft = AttachmentCalibratedTerminationPreflight.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        bare_prompt=bare_prompt,
        tasks=ordered_tasks,
        archived_bare_argmax_by_task=ordered_argmax,
        archived_position_zero_sha256_by_task=ordered_distributions,
        expected_model_identity_digest=expected_model_identity_digest,
        configured_max_output_tokens=configured_max_output_tokens,
        result_fingerprint="0" * 64,
    )
    return AttachmentCalibratedTerminationPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_calibrated_termination_fingerprint(draft),
    )


def build_calibrated_termination_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    preflight: AttachmentCalibratedTerminationPreflight,
    observations: tuple[AttachmentCalibratedTerminationObservation, ...],
) -> AttachmentCalibratedTerminationReport:
    """Align two repetitions and build one terminal CEA-1.12 report."""
    by_key = {(item.task_id, item.repetition): item for item in observations}
    expected_keys = {(task.id, repetition) for task in preflight.tasks for repetition in (1, 2)}
    if len(by_key) != 20 or set(by_key) != expected_keys:
        raise ValueError("Calibrated Termination observations do not cover both repetitions.")
    cases: list[AttachmentCalibratedTerminationCase] = []
    for task in preflight.tasks:
        values = (by_key[(task.id, 1)], by_key[(task.id, 2)])
        answers = tuple(item.decision.answer for item in values)
        distributions = tuple(item.position_zero_sha256 for item in values)
        cases.append(
            AttachmentCalibratedTerminationCase(
                task=task,
                archived_bare_argmax=preflight.archived_bare_argmax_by_task[task.id],
                archived_position_zero_sha256=(
                    preflight.archived_position_zero_sha256_by_task[task.id]
                ),
                observations=values,
                repetition_answer_agrees=(
                    all(item.exact_raw_finite_answer for item in values)
                    and answers[0] is answers[1]
                ),
                repetition_distribution_agrees=(
                    distributions[0] is not None and distributions[0] == distributions[1]
                ),
            )
        )
    case_values = tuple(cases)
    flat = tuple(item for case in case_values for item in case.observations)
    counts = {
        "successful_execution_count": sum(
            item.model_run_status is ModelRunStatus.SUCCEEDED for item in flat
        ),
        "probability_evidence_count": sum(item.finite_label_evidence is not None for item in flat),
        "one_position_zero_count": sum(item.probability_positions == (0,) for item in flat),
        "one_output_token_count": sum(item.output_token_count == 1 for item in flat),
        "output_count_witness_agreement_count": sum(
            item.output_count_witnesses_agree for item in flat
        ),
        "exact_raw_finite_answer_count": sum(item.exact_raw_finite_answer for item in flat),
        "observed_answer_argmax_match_count": sum(
            item.observed_answer_matches_live_argmax for item in flat
        ),
        "archived_distribution_match_count": sum(
            item.live_distribution_matches_archived for item in flat
        ),
        "repetition_answer_agreement_count": sum(
            item.repetition_answer_agrees for item in case_values
        ),
        "repetition_distribution_agreement_count": sum(
            item.repetition_distribution_agrees for item in case_values
        ),
    }
    mechanism = attachment_calibrated_termination_mechanism_proof(**counts)
    outcome = attachment_calibrated_termination_outcome(
        successful_execution_count=counts["successful_execution_count"],
        probability_evidence_count=counts["probability_evidence_count"],
        exact_raw_finite_answer_count=counts["exact_raw_finite_answer_count"],
        mechanism_proof=mechanism,
    )
    draft = AttachmentCalibratedTerminationReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        prompt=preflight.bare_prompt,
        cases=case_values,
        successful_execution_count=counts["successful_execution_count"],
        probability_evidence_count=counts["probability_evidence_count"],
        one_position_zero_count=counts["one_position_zero_count"],
        one_output_token_count=counts["one_output_token_count"],
        output_count_witness_agreement_count=counts["output_count_witness_agreement_count"],
        exact_raw_finite_answer_count=counts["exact_raw_finite_answer_count"],
        observed_answer_argmax_match_count=counts["observed_answer_argmax_match_count"],
        archived_distribution_match_count=counts["archived_distribution_match_count"],
        repetition_answer_agreement_count=counts["repetition_answer_agreement_count"],
        repetition_distribution_agreement_count=counts["repetition_distribution_agreement_count"],
        mechanism_proof=mechanism,
        unmet_suitability_conditions=tuple(AttachmentProductionSuitabilityCondition),
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentCalibratedTerminationReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_calibrated_termination_fingerprint(draft),
    )


def render_calibrated_termination_review(
    report: AttachmentCalibratedTerminationReport,
) -> str:
    """Render exact CEA-1.12 data-in and data-out for human review."""
    lines = [
        "# CEA-1.12 Runtime-Calibrated Finite Termination Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Mechanism Proof: `{str(report.mechanism_proof).lower()}`",
        "",
        "Production Suitability: `unmet`",
        "",
        f"Successful executions: `{report.successful_execution_count}/20`",
        "",
        f"Probability Evidence: `{report.probability_evidence_count}/20`",
        "",
        f"One position-zero witness: `{report.one_position_zero_count}/20`",
        "",
        f"One runtime output token: `{report.one_output_token_count}/20`",
        "",
        f"Output-count witness agreement: `{report.output_count_witness_agreement_count}/20`",
        "",
        f"Exact raw finite answers: `{report.exact_raw_finite_answer_count}/20`",
        "",
        f"Observed Answer-to-live-Argmax matches: `{report.observed_answer_argmax_match_count}/20`",
        "",
        f"Archived distribution matches: `{report.archived_distribution_match_count}/20`",
        "",
        f"Repetition answer agreements: `{report.repetition_answer_agreement_count}/10`",
        "",
        "Repetition distribution agreements: "
        f"`{report.repetition_distribution_agreement_count}/10`",
        "",
        "Unmet Production Suitability conditions:",
        "",
    ]
    lines.extend(f"- `{item.value}`" for item in report.unmet_suitability_conditions)
    lines.append("")
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
                f"Archived position-zero digest: `{case.archived_position_zero_sha256}`",
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
                    f"Repetition {observation.repetition} raw output JSON string: "
                    f"`{_raw_output_json(observation.raw_output_text)}`",
                    "",
                    f"Repetition {observation.repetition} runtime output count: "
                    f"`{observation.output_token_count}`",
                    "",
                    f"Repetition {observation.repetition} probability positions: "
                    f"`{list(observation.probability_positions)}`",
                    "",
                    f"Repetition {observation.repetition} position-zero digest: "
                    f"`{observation.position_zero_sha256}`",
                    "",
                    f"Repetition {observation.repetition} exact finite answer: "
                    f"`{str(observation.exact_raw_finite_answer).lower()}`",
                    "",
                    f"Repetition {observation.repetition} ModelRun status: "
                    f"`{observation.model_run_status.value}`",
                    "",
                    f"Repetition {observation.repetition} runtime error: "
                    f"`{_runtime_error(observation)}`",
                    "",
                    f"Repetition {observation.repetition} execution: "
                    f"`{observation.execution_record.path}`",
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def render_calibrated_termination_handoff(
    report: AttachmentCalibratedTerminationReport,
    *,
    prompt_text: str,
    package_files: tuple[AttachmentEvidenceReference, ...],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render one self-contained CEA-1.12 second-opinion package."""
    lines = [
        "# CEA-1.12 Runtime-Calibrated Finite Termination Handoff",
        "",
        "## Hypothesis",
        "",
        "> A two-token request yields one exact finite answer for every sealed task "
        "while preserving its archived position-zero distribution.",
        "",
        "## Interpretation boundary",
        "",
        "This experiment can establish a bounded Mechanism Proof.",
        "",
        "It cannot establish Production Suitability or semantic accuracy against Gold.",
        "",
        "Gold did not enter model input or outcome classification.",
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
        f"Mechanism Proof: `{str(report.mechanism_proof).lower()}`",
        "",
        "Production Suitability: `unmet`",
        "",
        f"Report fingerprint: `{report.result_fingerprint}`",
        "",
        render_calibrated_termination_review(report).rstrip(),
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
            "1. Do the two output-count witnesses independently establish one emitted token?",
            "2. Does exact raw-byte validation exclude whitespace-normalized false success?",
            "3. Do the distribution comparisons isolate output termination from model preference?",
            "4. Does the report keep Mechanism Proof separate from Production Suitability?",
            "5. What is the smallest next experiment after this result?",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _raw_output_json(value: str | None) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def _runtime_error(observation: AttachmentCalibratedTerminationObservation) -> str:
    if observation.model_error_code is None:
        return "none"
    return f"{observation.model_error_code}: {observation.model_error_message}"
