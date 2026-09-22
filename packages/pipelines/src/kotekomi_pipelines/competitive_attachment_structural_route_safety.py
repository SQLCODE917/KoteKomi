"""Model-free full-inventory safety sweep for CEA-1.19."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Literal

from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentGoldAuthority,
    AttachmentResidualTransferReport,
    AttachmentStructuralEligibility,
    AttachmentStructuralSafetyCase,
    AttachmentStructuralSafetyPhase,
    AttachmentStructuralSafetyReport,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    attachment_candidate_root_evidence,
    attachment_complete_foreign_event_ids,
    attachment_structural_safety_fingerprint,
    attachment_syntax_is_head_aligned,
    build_attachment_syntax_observation,
    classify_attachment_structural_safety_outcome,
)

from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
)

type _Answer = Literal["Y", "N"]
type _EdgeKey = tuple[Literal["development", "validation"], str, str]


def validate_attachment_structural_safety_frozen_inventory(
    report: AttachmentStructuralSafetyReport,
) -> None:
    """Reject evidence that differs from the registered CEA-1.19 inventory."""
    observed = (
        report.total_edge_count,
        report.head_aligned_count,
        report.gold_conflict_count,
        report.foreign_event_exclusion_count,
        report.eligible_count,
    )
    expected = (935, 58, 3, 5, 53)
    if observed != expected:
        raise ValueError("CEA-1.19 frozen inventory counts drifted.")


def build_attachment_structural_safety_phase(
    *,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    oracle: Mapping[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    inputs: tuple[EventEntityExperimentInput, ...],
    reviewed_gold: Mapping[_EdgeKey, _Answer],
) -> AttachmentStructuralSafetyPhase:
    """Evaluate every Head-Aligned edge in one finalized CEA-1 phase."""
    input_by_event = {item.event.id: item for item in inputs}
    if len(input_by_event) != len(inputs):
        raise ValueError("Structural safety inputs contain duplicate Events.")
    if any(item.phase != phase for item in inputs):
        raise ValueError("Structural safety inputs contain a foreign phase.")
    matrix_ids = tuple(item.id for item in matrices)
    if set(matrix_ids) != set(oracle):
        raise ValueError("Structural safety oracle does not cover the exact matrix inventory.")

    total_edge_count = 0
    cases: list[AttachmentStructuralSafetyCase] = []
    for matrix in matrices:
        decisions = oracle[matrix.id]
        gold_by_candidate = {
            item.candidate_id: set(item.source_grounded_event_ids) for item in decisions
        }
        if set(gold_by_candidate) != {item.id for item in matrix.candidates}:
            raise ValueError("Structural safety oracle does not cover every Candidate.")
        for candidate in matrix.candidates:
            for event in matrix.event_options:
                total_edge_count += 1
                prepared = input_by_event.get(event.source_grounded_event_id)
                if prepared is None:
                    raise ValueError("Structural safety phase lacks one Event input.")
                syntax = build_attachment_syntax_observation(
                    phase=phase,
                    source_text=prepared.source_text,
                    candidate=candidate,
                    event=event,
                    event_head_start=prepared.trigger.head_start,
                    event_head_end=prepared.trigger.head_end,
                    event_head_text=prepared.trigger.head_text,
                    linguistic_evidence=prepared.linguistic_evidence,
                )
                root_evidence = attachment_candidate_root_evidence(
                    candidate,
                    prepared.linguistic_evidence,
                )
                if not attachment_syntax_is_head_aligned(syntax, root_evidence.roots):
                    continue
                original: _Answer = (
                    "Y"
                    if event.source_grounded_event_id in gold_by_candidate[candidate.id]
                    else "N"
                )
                edge_key: _EdgeKey = (phase, candidate.id, event.source_grounded_event_id)
                reviewed = reviewed_gold.get(edge_key)
                effective, authority, conflict = select_attachment_effective_gold(
                    original=original,
                    reviewed=reviewed,
                )
                foreign_event_ids = attachment_complete_foreign_event_ids(
                    candidate,
                    event,
                    matrix.event_options,
                )
                eligibility = (
                    AttachmentStructuralEligibility.FOREIGN_EVENT
                    if foreign_event_ids
                    else AttachmentStructuralEligibility.ELIGIBLE
                )
                cases.append(
                    AttachmentStructuralSafetyCase(
                        phase=phase,
                        matrix_id=matrix.id,
                        source_text=prepared.source_text,
                        candidate=candidate,
                        event=event,
                        syntax=syntax,
                        candidate_root_evidence=root_evidence,
                        original_gold=original,
                        reviewed_gold=reviewed,
                        effective_gold=effective,
                        gold_authority=authority,
                        gold_conflict=conflict,
                        foreign_event_ids=foreign_event_ids,
                        eligibility=eligibility,
                        structural_answer=(
                            "Y" if eligibility is AttachmentStructuralEligibility.ELIGIBLE else None
                        ),
                        correctly_routed=(effective == "Y")
                        == (eligibility is AttachmentStructuralEligibility.ELIGIBLE),
                    )
                )
    ordered = tuple(
        sorted(
            cases,
            key=lambda item: (
                item.matrix_id,
                item.candidate.start,
                item.candidate.end,
                item.event.start,
                item.event.end,
                item.event.source_grounded_event_id,
            ),
        )
    )
    eligible = tuple(
        item for item in ordered if item.eligibility is AttachmentStructuralEligibility.ELIGIBLE
    )
    excluded = tuple(
        item
        for item in ordered
        if item.eligibility is AttachmentStructuralEligibility.FOREIGN_EVENT
    )
    return AttachmentStructuralSafetyPhase(
        phase=phase,
        total_edge_count=total_edge_count,
        cases=ordered,
        head_aligned_count=len(ordered),
        original_positive_count=sum(item.original_gold == "Y" for item in ordered),
        original_negative_count=sum(item.original_gold == "N" for item in ordered),
        reviewed_edge_count=sum(item.reviewed_gold is not None for item in ordered),
        gold_conflict_count=sum(item.gold_conflict for item in ordered),
        effective_positive_count=sum(item.effective_gold == "Y" for item in ordered),
        effective_negative_count=sum(item.effective_gold == "N" for item in ordered),
        eligible_count=len(eligible),
        excluded_count=len(excluded),
        eligible_positive_count=sum(item.effective_gold == "Y" for item in eligible),
        eligible_negative_count=sum(item.effective_gold == "N" for item in eligible),
        excluded_positive_count=sum(item.effective_gold == "Y" for item in excluded),
        excluded_negative_count=sum(item.effective_gold == "N" for item in excluded),
    )


def select_attachment_effective_gold(
    *,
    original: _Answer,
    reviewed: _Answer | None,
) -> tuple[_Answer, AttachmentGoldAuthority, bool]:
    """Select later Reviewed Gold for one exact edge when it exists."""
    if reviewed is None:
        return original, AttachmentGoldAuthority.ORIGINAL, False
    return reviewed, AttachmentGoldAuthority.REVIEWED, reviewed != original


def build_attachment_structural_safety_report(
    *,
    evidence: tuple[AttachmentEvidenceReference, ...],
    predecessor: AttachmentResidualTransferReport,
    development_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    development_oracle: Mapping[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    development_inputs: tuple[EventEntityExperimentInput, ...],
    validation_matrices: tuple[CompetitiveAttachmentMatrix, ...],
    validation_oracle: Mapping[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    validation_inputs: tuple[EventEntityExperimentInput, ...],
) -> AttachmentStructuralSafetyReport:
    """Build one complete CEA-1.19 report from frozen evidence."""
    reviewed_gold = _reviewed_gold(predecessor)
    development = build_attachment_structural_safety_phase(
        phase="development",
        matrices=development_matrices,
        oracle=development_oracle,
        inputs=development_inputs,
        reviewed_gold=reviewed_gold,
    )
    validation = build_attachment_structural_safety_phase(
        phase="validation",
        matrices=validation_matrices,
        oracle=validation_oracle,
        inputs=validation_inputs,
        reviewed_gold=reviewed_gold,
    )
    phases = (development, validation)
    eligible_negative_count = sum(item.eligible_negative_count for item in phases)
    excluded_positive_count = sum(item.excluded_positive_count for item in phases)
    draft = AttachmentStructuralSafetyReport.model_construct(
        inputs=tuple(sorted(evidence, key=lambda item: item.label)),
        development=development,
        validation=validation,
        outcome=classify_attachment_structural_safety_outcome(
            eligible_negative_count=eligible_negative_count,
            excluded_positive_count=excluded_positive_count,
        ),
        total_edge_count=sum(item.total_edge_count for item in phases),
        head_aligned_count=sum(item.head_aligned_count for item in phases),
        gold_conflict_count=sum(item.gold_conflict_count for item in phases),
        foreign_event_exclusion_count=sum(item.excluded_count for item in phases),
        eligible_count=sum(item.eligible_count for item in phases),
        eligible_negative_count=eligible_negative_count,
        excluded_positive_count=excluded_positive_count,
        result_fingerprint="0" * 64,
    )
    return AttachmentStructuralSafetyReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_structural_safety_fingerprint(draft),
    )


def render_attachment_structural_safety_review(
    report: AttachmentStructuralSafetyReport,
) -> str:
    """Render every Head-Aligned edge with exact data-in and data-out."""
    lines = [
        "# CEA-1.19 Structural Route Safety Sweep",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"All Candidate/Event edges: `{report.total_edge_count}`",
        "",
        f"Head-Aligned edges: `{report.head_aligned_count}`",
        "",
        f"Gold conflicts resolved by Reviewed Gold: `{report.gold_conflict_count}`",
        "",
        f"Foreign Event exclusions: `{report.foreign_event_exclusion_count}`",
        "",
        f"Eligible Structural Decisions: `{report.eligible_count}`",
        "",
        f"Eligible Gold-negative edges: `{report.eligible_negative_count}`",
        "",
        f"Excluded Gold-positive edges: `{report.excluded_positive_count}`",
        "",
        _phase_summary(report.development),
        "",
        _phase_summary(report.validation),
        "",
    ]
    for phase in (report.development, report.validation):
        for case in phase.cases:
            root = case.candidate_root_evidence.roots[0]
            reviewed = case.reviewed_gold if case.reviewed_gold is not None else "not reviewed"
            lines.extend(
                [
                    f"## {phase.phase} — {case.candidate.id} → "
                    f"{case.event.source_grounded_event_id}",
                    "",
                    "Exact SourceSegment:",
                    "",
                    "~~~~text",
                    case.source_text,
                    "~~~~",
                    "",
                    f"Candidate: `{json.dumps(case.candidate.text, ensure_ascii=False)}`",
                    "",
                    f"Event: `{json.dumps(case.event.text, ensure_ascii=False)}`",
                    "",
                    f"Candidate Root: `{root.token_id}` "
                    f"`{json.dumps(root.text, ensure_ascii=False)}`",
                    "",
                    f"Original Gold: `{case.original_gold}`",
                    "",
                    f"Reviewed Gold: `{reviewed}`",
                    "",
                    f"Effective Gold: `{case.effective_gold}` from `{case.gold_authority.value}`",
                    "",
                    f"Gold conflict: `{case.gold_conflict}`",
                    "",
                    "Foreign Events: "
                    f"`{case.foreign_event_ids if case.foreign_event_ids else 'none'}`",
                    "",
                    f"Eligibility: `{case.eligibility.value}`",
                    "",
                    f"Structural answer: `{case.structural_answer}`",
                    "",
                    f"Evaluation: `{'correct' if case.correctly_routed else 'wrong'}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_attachment_structural_safety_handoff(
    report: AttachmentStructuralSafetyReport,
    *,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained independent-review handoff."""
    return "\n".join(
        [
            "# CEA-1.19 Structural Route Safety Sweep Handoff",
            "",
            "Verify the composed policy, not head alignment in isolation.",
            "",
            "The policy applies later human-reviewed Gold to exact edge conflicts.",
            "",
            "The policy excludes a Candidate when it contains a complete Other Event.",
            "",
            "The policy assigns deterministic `Y` only after that exclusion and exact "
            "dependency-head alignment.",
            "",
            "This frozen-source result cannot establish safety on unseen syntax or parser errors.",
            "",
            render_attachment_structural_safety_review(report).rstrip(),
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


def _reviewed_gold(predecessor: AttachmentResidualTransferReport) -> dict[_EdgeKey, _Answer]:
    values: dict[_EdgeKey, _Answer] = {}
    for phase in (predecessor.development, predecessor.validation):
        for case in phase.cases:
            task = case.task.edge_filter_task
            key: _EdgeKey = (
                phase.phase,
                task.candidate.id,
                task.edge.source_grounded_event_id,
            )
            if key in values:
                raise ValueError("Structural safety Reviewed Gold contains a duplicate edge.")
            values[key] = case.gold.expected_answer
    return values


def _phase_summary(phase: AttachmentStructuralSafetyPhase) -> str:
    return (
        f"{phase.phase.title()}: edges `{phase.total_edge_count}`; Head-Aligned "
        f"`{phase.head_aligned_count}`; Gold conflicts `{phase.gold_conflict_count}`; "
        f"eligible `{phase.eligible_count}`; excluded `{phase.excluded_count}`; "
        f"eligible negatives `{phase.eligible_negative_count}`; excluded positives "
        f"`{phase.excluded_positive_count}`"
    )
