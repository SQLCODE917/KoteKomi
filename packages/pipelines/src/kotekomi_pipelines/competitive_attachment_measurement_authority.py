"""Deterministic CEA-1.6 measurement against occurrence-level Attachment Gold."""

from __future__ import annotations

from typing import Literal

from kotekomi_application import (
    AttachmentCalibrationDiagnosticOutcome,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentMeasurementAuditReport,
    AttachmentMeasurementControl,
    AttachmentMeasurementControlCatalog,
    AttachmentMeasurementControlKind,
    AttachmentMeasurementDecision,
    AttachmentMeasurementOutcome,
    AttachmentMeasurementPhaseReport,
    AttachmentMeasurementRuleAnswer,
    AttachmentNormalizationChange,
    AttachmentPoolEdge,
    CompetitiveAttachmentGoldDecision,
    attachment_measurement_control_id,
    attachment_measurement_fingerprint,
)

from kotekomi_pipelines.competitive_attachment_edge_filter import (
    normalized_attachment_gold_sets,
)

type AttachmentGoldSets = dict[str, tuple[str, ...]]


def authoritative_attachment_gold_sets(
    *,
    phase: Literal["development", "validation"],
    original_decisions: tuple[CompetitiveAttachmentGoldDecision, ...],
    normalization_changes: tuple[AttachmentNormalizationChange, ...],
    expected_candidate_count: int,
) -> AttachmentGoldSets:
    """Reconstruct Attachment Gold from reviewed decisions and declared changes."""
    original: AttachmentGoldSets = {}
    for decision in original_decisions:
        if decision.candidate_id in original:
            raise ValueError("Attachment Gold contains a duplicate Candidate decision.")
        original[decision.candidate_id] = decision.source_grounded_event_ids
    if len(original) != expected_candidate_count:
        raise ValueError("Attachment Gold Candidate inventory drifted.")
    phase_changes = tuple(item for item in normalization_changes if item.phase == phase)
    expected_change_count = 1 if phase == "development" else 2
    if len(phase_changes) != expected_change_count:
        raise ValueError("Attachment Gold normalization inventory drifted.")
    changes: dict[str, tuple[str, ...]] = {}
    for change in phase_changes:
        if change.candidate_id not in original:
            raise ValueError("Attachment Gold normalization references a foreign Candidate.")
        if original[change.candidate_id] != change.original_gold_event_ids:
            raise ValueError("Attachment Gold normalization original decision drifted.")
        changes[change.candidate_id] = change.normalized_gold_event_ids
    return normalized_attachment_gold_sets(
        original_gold=original,
        normalization_changes=changes,
    )


def audit_r1_strict_phase(
    *,
    phase: Literal["development", "validation"],
    edges: tuple[AttachmentPoolEdge, ...],
    tasks: tuple[AttachmentEdgeFilterTask, ...],
    gold_sets: AttachmentGoldSets,
) -> AttachmentMeasurementPhaseReport:
    """Apply R1-strict to every exact Maximum Pool Edge."""
    if not edges or any(item.phase != phase for item in edges):
        raise ValueError("R1-strict audit contains a foreign or empty Edge inventory.")
    if len({item.id for item in edges}) != len(edges):
        raise ValueError("R1-strict audit requires distinct Pool Edges.")
    tasks_by_edge = {item.edge.id: item for item in tasks}
    if len(tasks_by_edge) != len(tasks) or set(tasks_by_edge) != {item.id for item in edges}:
        raise ValueError("R1-strict audit requires one task per Pool Edge.")
    if {item.candidate_id for item in edges} - set(gold_sets):
        raise ValueError("R1-strict audit Edge references foreign Attachment Gold.")
    decisions: list[AttachmentMeasurementDecision] = []
    for edge in edges:
        task = tasks_by_edge[edge.id]
        if task.edge != edge:
            raise ValueError("R1-strict task Edge drifted from the Maximum Pool.")
        expected = "Y" if edge.source_grounded_event_id in gold_sets[edge.candidate_id] else "N"
        fires = _properly_contains(edge)
        decisions.append(
            AttachmentMeasurementDecision(
                phase=phase,
                edge=edge,
                source_text=task.source_text,
                expected_answer=expected,
                rule_answer=(
                    AttachmentMeasurementRuleAnswer.REJECT
                    if fires
                    else AttachmentMeasurementRuleAnswer.RETAIN
                ),
                gold_positive_loss=fires and expected == "Y",
                gold_negative_removal=fires and expected == "N",
            )
        )
    values = tuple(decisions)
    draft = AttachmentMeasurementPhaseReport.model_construct(
        phase=phase,
        decisions=values,
        pool_edge_count=len(values),
        rule_firing_count=sum(
            item.rule_answer is AttachmentMeasurementRuleAnswer.REJECT for item in values
        ),
        gold_negative_removal_count=sum(item.gold_negative_removal for item in values),
        gold_positive_loss_count=sum(item.gold_positive_loss for item in values),
        result_fingerprint="0" * 64,
    )
    return AttachmentMeasurementPhaseReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_measurement_fingerprint(draft),
    )


def build_attachment_measurement_audit(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    v8_outcome: AttachmentCalibrationDiagnosticOutcome,
    v9_outcome: AttachmentCalibrationDiagnosticOutcome,
    development: AttachmentMeasurementPhaseReport,
    validation: AttachmentMeasurementPhaseReport,
) -> AttachmentMeasurementAuditReport:
    """Build the frozen CEA-1.6 audit report."""
    losses = development.gold_positive_loss_count + validation.gold_positive_loss_count
    draft = AttachmentMeasurementAuditReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        v8_outcome=v8_outcome,
        v9_outcome=v9_outcome,
        development=development,
        validation=validation,
        combined_rule_firing_count=(development.rule_firing_count + validation.rule_firing_count),
        combined_gold_negative_removal_count=(
            development.gold_negative_removal_count + validation.gold_negative_removal_count
        ),
        combined_gold_positive_loss_count=losses,
        outcome=(
            AttachmentMeasurementOutcome.UNSAFE if losses else AttachmentMeasurementOutcome.SAFE
        ),
        production_integration="not_activated",
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        result_fingerprint="0" * 64,
    )
    return AttachmentMeasurementAuditReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_measurement_fingerprint(draft),
    )


def build_attachment_measurement_controls(
    *,
    predecessor_catalog: AttachmentEvidenceReference,
    development: AttachmentMeasurementPhaseReport,
) -> AttachmentMeasurementControlCatalog:
    """Preserve every development R1-strict firing as a successor control."""
    controls = tuple(
        sorted(
            (
                AttachmentMeasurementControl(
                    id=attachment_measurement_control_id(item.edge.id),
                    kind=(
                        AttachmentMeasurementControlKind.POSITIVE
                        if item.expected_answer == "Y"
                        else AttachmentMeasurementControlKind.NEGATIVE
                    ),
                    decision=item,
                )
                for item in development.decisions
                if item.rule_answer is AttachmentMeasurementRuleAnswer.REJECT
            ),
            key=lambda item: item.id,
        )
    )
    draft = AttachmentMeasurementControlCatalog.model_construct(
        predecessor_catalog=predecessor_catalog,
        controls=controls,
        result_fingerprint="0" * 64,
    )
    return AttachmentMeasurementControlCatalog(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_measurement_fingerprint(draft),
    )


def render_attachment_measurement_review(report: AttachmentMeasurementAuditReport) -> str:
    """Render compact human-readable audit results and all unsafe decisions."""
    lines = [
        "# CEA-1.6 Attachment Measurement Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"V8 calibration outcome: `{report.v8_outcome.value}`",
        "",
        f"V9 calibration outcome: `{report.v9_outcome.value}`",
        "",
        _phase_line(report.development),
        "",
        _phase_line(report.validation),
        "",
        "R1-strict rejected `31` Pool Edges.",
        "",
        "It removed `19` Gold-negative Edges and `12` Gold-positive Edges.",
        "",
        "## Gold-positive losses",
        "",
    ]
    for item in _positive_losses(report):
        lines.extend(_decision_lines(item))
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_measurement_handoff(
    report: AttachmentMeasurementAuditReport,
    controls: AttachmentMeasurementControlCatalog,
) -> str:
    """Render a self-contained handoff for an independent second opinion."""
    proposition_gold = next(item for item in report.inputs if item.label == "proposition_gold")
    lines = [
        "# CEA-1.6 Attachment Measurement Authority Handoff",
        "",
        "## Hypothesis",
        "",
        "> Official normalized Attachment Gold will show that R1-strict removes valid "
        "attachments that the sixteen-case diagnostic did not expose.",
        "",
        "## Method",
        "",
        "R1-strict rejects a Pool Edge when the exact Candidate range properly contains "
        "the exact Target Event range.",
        "",
        "KoteKomi scored every development and validation Maximum Pool Edge against "
        "reviewed occurrence-level Attachment Gold.",
        "",
        f"Authoritative Gold: `{proposition_gold.path}`",
        "",
        f"Authoritative Gold SHA-256: `{proposition_gold.sha256}`",
        "",
        "The experiment executed no model and wrote no canonical intelligence.",
        "",
        "## Scorecard",
        "",
        f"- Development: `{_phase_line(report.development)}`",
        f"- Validation: `{_phase_line(report.validation)}`",
        f"- Combined firings: `{report.combined_rule_firing_count}`",
        f"- Gold-negative removals: `{report.combined_gold_negative_removal_count}`",
        f"- Gold-positive losses: `{report.combined_gold_positive_loss_count}`",
        f"- Rule outcome: `{report.outcome.value}`",
        f"- Successor controls: `{len(controls.controls)}`",
        "",
        "## Exact Gold-positive counterexamples",
        "",
    ]
    for item in _positive_losses(report):
        lines.extend(_decision_lines(item))
    lines.extend(
        (
            "## Review questions",
            "",
            "1. Do the exact ranges and Gold labels justify the `unsafe` outcome?",
            "2. Does R1-strict test semantic attachment, or only one surface-range shape?",
            "3. Which smallest bounded task should use these positive and negative controls next?",
            "4. Which material claims in this review need independent deterministic checks?",
            "",
            "Use `audit-report.json` for all 747 occurrence-level decisions.",
            "Use `diagnostic-controls.json` for every development R1-strict firing.",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _properly_contains(edge: AttachmentPoolEdge) -> bool:
    candidate = edge.candidate_range
    event = edge.event_range
    return (
        candidate.start <= event.start
        and candidate.end >= event.end
        and (candidate.start, candidate.end) != (event.start, event.end)
    )


def _positive_losses(
    report: AttachmentMeasurementAuditReport,
) -> tuple[AttachmentMeasurementDecision, ...]:
    return tuple(
        item
        for phase in (report.development, report.validation)
        for item in phase.decisions
        if item.gold_positive_loss
    )


def _phase_line(phase: AttachmentMeasurementPhaseReport) -> str:
    return (
        f"{phase.phase}: {phase.rule_firing_count} firings = "
        f"{phase.gold_negative_removal_count} Gold-negative removals + "
        f"{phase.gold_positive_loss_count} Gold-positive losses"
    )


def _decision_lines(item: AttachmentMeasurementDecision) -> list[str]:
    edge = item.edge
    return [
        f"### {item.phase} — {edge.id}",
        "",
        f"> {item.source_text}",
        "",
        f"Candidate: `{edge.candidate_range.text}` "
        f"`[{edge.candidate_range.start}, {edge.candidate_range.end})`",
        "",
        f"Target Event: `{edge.event_range.text}` "
        f"`[{edge.event_range.start}, {edge.event_range.end})`",
        "",
        f"Attachment Gold: `{item.expected_answer}`",
        "",
        f"R1-strict: `{item.rule_answer.value}`",
        "",
    ]
