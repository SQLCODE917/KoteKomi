"""Model-free exact Event self-attachment evaluation for CEA-1.20."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Literal

from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentExactSelfCase,
    AttachmentResidualTransferCase,
    AttachmentResidualTransferReport,
    AttachmentReviewedNegativeControl,
    AttachmentSelfRoutingPhase,
    AttachmentSelfRoutingReport,
    AttachmentSourceRange,
    AttachmentStructuralSafetyReport,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    attachment_self_routing_fingerprint,
    classify_attachment_self_routing_outcome,
)

type _Answer = Literal["Y", "N"]
type _EdgeKey = tuple[Literal["development", "validation"], str, str]


def build_attachment_self_routing_phase(
    *,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: Mapping[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    source_text_by_event: Mapping[str, str],
    reviewed_gold: Mapping[_EdgeKey, _Answer],
) -> AttachmentSelfRoutingPhase:
    """Evaluate equal Candidate and Event ranges across one complete phase."""
    if {item.id for item in matrices} != set(oracle):
        raise ValueError("Exact self-attachment oracle does not cover the matrix inventory.")
    all_edge_count = 0
    cases: list[AttachmentExactSelfCase] = []
    for matrix in matrices:
        gold_by_candidate = {
            item.candidate_id: set(item.source_grounded_event_ids) for item in oracle[matrix.id]
        }
        if set(gold_by_candidate) != {item.id for item in matrix.candidates}:
            raise ValueError("Exact self-attachment oracle does not cover every Candidate.")
        for candidate in matrix.candidates:
            for event in matrix.event_options:
                all_edge_count += 1
                if (candidate.start, candidate.end) != (event.start, event.end):
                    continue
                source_text = source_text_by_event.get(event.source_grounded_event_id)
                if source_text is None:
                    raise ValueError("Exact self-attachment lacks authoritative source text.")
                source_digest = hashlib.sha256(source_text.encode()).hexdigest()
                if (
                    source_digest != matrix.source_text_sha256
                    or source_text[candidate.start : candidate.end] != candidate.text
                    or source_text[event.start : event.end] != event.text
                ):
                    raise ValueError("Exact self-attachment matrix is not source-exact.")
                original: _Answer = (
                    "Y"
                    if event.source_grounded_event_id in gold_by_candidate[candidate.id]
                    else "N"
                )
                reviewed = reviewed_gold.get((phase, candidate.id, event.source_grounded_event_id))
                cases.append(
                    AttachmentExactSelfCase(
                        phase=phase,
                        matrix_id=matrix.id,
                        source_text=source_text,
                        source_text_sha256=source_digest,
                        candidate_id=candidate.id,
                        event_id=event.source_grounded_event_id,
                        candidate_range=AttachmentSourceRange(
                            start=candidate.start,
                            end=candidate.end,
                            text=candidate.text,
                        ),
                        event_range=AttachmentSourceRange(
                            start=event.start,
                            end=event.end,
                            text=event.text,
                        ),
                        original_gold=original,
                        reviewed_gold=reviewed,
                        gold_conflict=reviewed is not None and reviewed != original,
                        original_gold_correct=original == "Y",
                    )
                )
    ordered = tuple(
        sorted(
            cases,
            key=lambda item: (
                item.matrix_id,
                item.candidate_range.start,
                item.candidate_range.end,
                item.event_id,
            ),
        )
    )
    return AttachmentSelfRoutingPhase(
        phase=phase,
        exact_self_cases=ordered,
        all_edge_count=all_edge_count,
        exact_self_count=len(ordered),
        unequal_range_count=all_edge_count - len(ordered),
        exact_self_original_positive_count=sum(item.original_gold == "Y" for item in ordered),
        exact_self_original_negative_count=sum(item.original_gold == "N" for item in ordered),
        exact_self_reviewed_count=sum(item.reviewed_gold is not None for item in ordered),
        exact_self_gold_conflict_count=sum(item.gold_conflict for item in ordered),
    )


def build_attachment_self_routing_report(
    *,
    evidence: tuple[AttachmentEvidenceReference, ...],
    residual_transfer: AttachmentResidualTransferReport,
    structural_safety: AttachmentStructuralSafetyReport,
    development_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    development_oracle: Mapping[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    development_source_text_by_event: Mapping[str, str],
    validation_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    validation_oracle: Mapping[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    validation_source_text_by_event: Mapping[str, str],
) -> AttachmentSelfRoutingReport:
    """Build the complete CEA-1.20 model-free report."""
    reviewed_gold = _reviewed_gold(structural_safety)
    development = build_attachment_self_routing_phase(
        phase="development",
        matrices=development_matrices,
        oracle=development_oracle,
        source_text_by_event=development_source_text_by_event,
        reviewed_gold=reviewed_gold,
    )
    validation = build_attachment_self_routing_phase(
        phase="validation",
        matrices=validation_matrices,
        oracle=validation_oracle,
        source_text_by_event=validation_source_text_by_event,
        reviewed_gold=reviewed_gold,
    )
    controls = tuple(
        sorted(
            (
                AttachmentReviewedNegativeControl(
                    task_id=case.task.id,
                    phase=case.task.phase,
                    source_text=case.task.edge_filter_task.source_text,
                    source_text_sha256=case.task.edge_filter_task.candidate.source_text_sha256,
                    candidate_range=AttachmentSourceRange(
                        start=case.task.edge_filter_task.candidate.start,
                        end=case.task.edge_filter_task.candidate.end,
                        text=case.task.edge_filter_task.candidate.text,
                    ),
                    event_range=case.task.edge_filter_task.edge.event_range,
                    exact_self_selected=_transfer_case_has_equal_ranges(case),
                )
                for phase_report in (residual_transfer.development, residual_transfer.validation)
                for case in phase_report.cases
                if case.gold.expected_answer == "N"
            ),
            key=lambda item: item.task_id,
        )
    )
    phases = (development, validation)
    exact_keys = {
        (item.phase, item.candidate_id, item.event_id)
        for phase_report in phases
        for item in phase_report.exact_self_cases
    }
    head_aligned_keys = {
        (item.phase, item.candidate.id, item.event.source_grounded_event_id)
        for phase_report in (structural_safety.development, structural_safety.validation)
        for item in phase_report.cases
    }
    exact_negative_count = sum(item.exact_self_original_negative_count for item in phases)
    exact_conflict_count = sum(item.exact_self_gold_conflict_count for item in phases)
    routed_control_count = sum(item.exact_self_selected for item in controls)
    draft = AttachmentSelfRoutingReport.model_construct(
        inputs=tuple(sorted(evidence, key=lambda item: item.label)),
        development=development,
        validation=validation,
        reviewed_negative_controls=controls,
        outcome=classify_attachment_self_routing_outcome(
            exact_self_original_negative_count=exact_negative_count,
            routed_reviewed_negative_control_count=routed_control_count,
        ),
        all_edge_count=sum(item.all_edge_count for item in phases),
        exact_self_count=sum(item.exact_self_count for item in phases),
        unequal_range_count=sum(item.unequal_range_count for item in phases),
        exact_self_original_negative_count=exact_negative_count,
        exact_self_gold_conflict_count=exact_conflict_count,
        head_aligned_count=structural_safety.head_aligned_count,
        head_aligned_exact_self_count=len(exact_keys & head_aligned_keys),
        head_aligned_unequal_range_count=(
            structural_safety.head_aligned_count - len(exact_keys & head_aligned_keys)
        ),
        head_aligned_gold_conflict_count=structural_safety.gold_conflict_count,
        reviewed_negative_control_count=len(controls),
        routed_reviewed_negative_control_count=routed_control_count,
        result_fingerprint="0" * 64,
    )
    if draft.all_edge_count != structural_safety.total_edge_count:
        raise ValueError("Exact self-attachment and structural inventories disagree.")
    return AttachmentSelfRoutingReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_self_routing_fingerprint(draft),
    )


def render_attachment_self_routing_review(report: AttachmentSelfRoutingReport) -> str:
    """Render every exact self-attachment and the complete inventory counts."""
    lines = [
        "# CEA-1.20 Exact Event Self-Attachment",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"All Candidate/Event edges: `{report.all_edge_count}`",
        "",
        f"Exact Self-Attachment edges: `{report.exact_self_count}`",
        "",
        f"Unequal-range edges: `{report.unequal_range_count}`",
        "",
        "Exact Self-Attachment Original Gold negatives: "
        f"`{report.exact_self_original_negative_count}`",
        "",
        f"Exact Self-Attachment Gold conflicts: `{report.exact_self_gold_conflict_count}`",
        "",
        f"Head-Aligned edges: `{report.head_aligned_count}`",
        "",
        f"Head-Aligned Exact Self-Attachment edges: `{report.head_aligned_exact_self_count}`",
        "",
        f"Head-Aligned unequal-range edges: `{report.head_aligned_unequal_range_count}`",
        "",
        f"Head-Aligned Gold conflicts: `{report.head_aligned_gold_conflict_count}`",
        "",
        f"Reviewed Negative Controls: `{report.reviewed_negative_control_count}`",
        "",
        "Reviewed Negative Controls selected by the exact route: "
        f"`{report.routed_reviewed_negative_control_count}`",
        "",
        _phase_summary(report.development),
        "",
        _phase_summary(report.validation),
        "",
        "## Reviewed Negative Controls",
        "",
    ]
    for control in report.reviewed_negative_controls:
        lines.extend(
            [
                f"### {control.task_id}",
                "",
                "> " + control.source_text,
                "",
                f"Candidate: `{json.dumps(control.candidate_range.text, ensure_ascii=False)}`",
                "",
                f"Event: `{json.dumps(control.event_range.text, ensure_ascii=False)}`",
                "",
                f"Exact Self-Attachment selected: `{control.exact_self_selected}`",
                "",
            ]
        )
    lines.extend(["## Complete Exact Self-Attachment Inventory", ""])
    for phase_report in (report.development, report.validation):
        for case in phase_report.exact_self_cases:
            lines.extend(
                [
                    f"### {phase_report.phase} — {case.candidate_id} → {case.event_id}",
                    "",
                    "> " + case.source_text,
                    "",
                    f"Exact text: `{json.dumps(case.candidate_range.text, ensure_ascii=False)}`",
                    "",
                    f"Answer: `{case.answer}`",
                    "",
                    f"Original Gold: `{case.original_gold}`",
                    "",
                    f"Reviewed Gold: `{case.reviewed_gold}`",
                    "",
                    f"Gold conflict: `{case.gold_conflict}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_self_routing_handoff(
    report: AttachmentSelfRoutingReport,
    *,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained independent-review handoff."""
    return "\n".join(
        [
            "# CEA-1.20 Exact Event Self-Attachment Handoff",
            "",
            "Verify the exact-range claim against the complete Candidate/Event inventory.",
            "",
            "The complete frozen inventory contains "
            f"{report.all_edge_count} Candidate and Event pairs.",
            "",
            f"CEA-1.19 reached {report.head_aligned_count} Head-Aligned pairs.",
            "",
            "CEA-1.20 independently scans the complete inventory for equal source ranges.",
            "",
            "It assigns no answer to unequal-range pairs.",
            "",
            "The route uses Original Gold and does not rely on disputed relabels.",
            "",
            "This result is an oracle consistency check over the easiest "
            f"{report.exact_self_count} of {report.all_edge_count} pairs.",
            "",
            "This result cannot establish safety for unequal-range candidates or unseen documents.",
            "",
            render_attachment_self_routing_review(report).rstrip(),
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


def _reviewed_gold(report: AttachmentStructuralSafetyReport) -> dict[_EdgeKey, _Answer]:
    return {
        (item.phase, item.candidate.id, item.event.source_grounded_event_id): item.reviewed_gold
        for phase_report in (report.development, report.validation)
        for item in phase_report.cases
        if item.reviewed_gold is not None
    }


def _transfer_case_has_equal_ranges(case: AttachmentResidualTransferCase) -> bool:
    task = case.task.edge_filter_task
    return (
        task.candidate.start == task.edge.event_range.start
        and task.candidate.end == task.edge.event_range.end
    )


def _phase_summary(phase: AttachmentSelfRoutingPhase) -> str:
    return (
        f"{phase.phase.title()}: all edges `{phase.all_edge_count}`; "
        f"Exact Self-Attachment `{phase.exact_self_count}`; "
        f"unequal range `{phase.unequal_range_count}`; "
        f"exact Original Gold negatives `{phase.exact_self_original_negative_count}`; "
        f"exact Gold conflicts `{phase.exact_self_gold_conflict_count}`"
    )
