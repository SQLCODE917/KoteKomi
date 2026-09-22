from __future__ import annotations

import hashlib
from types import SimpleNamespace

from kotekomi_application import (
    AttachmentResidualTransferCase,
    AttachmentResidualTransferPhaseReport,
    AttachmentResidualTransferReport,
    AttachmentSelfRoutingOutcome,
    AttachmentSourceRange,
    AttachmentStructuralSafetyCase,
    AttachmentStructuralSafetyPhase,
    AttachmentStructuralSafetyReport,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    PropositionFragmentReason,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
    competitive_attachment_matrix_id,
)
from kotekomi_pipelines.competitive_attachment_exact_self_routing import (
    build_attachment_self_routing_phase,
    build_attachment_self_routing_report,
    render_attachment_self_routing_handoff,
    render_attachment_self_routing_review,
)

SOURCE = "Alpha targeted Beta."
DIGEST = hashlib.sha256(SOURCE.encode()).hexdigest()
EVENT_ID = "sge_" + "1" * 24


def test_phase_scans_complete_matrix_and_retains_only_equal_ranges() -> None:
    matrix, oracle = _matrix_and_oracle()

    result = build_attachment_self_routing_phase(
        phase="development",
        matrices=(matrix,),
        oracle={matrix.id: oracle},
        source_text_by_event={EVENT_ID: SOURCE},
        reviewed_gold={},
    )

    assert result.all_edge_count == 2
    assert result.exact_self_count == 1
    assert result.unequal_range_count == 1
    assert result.exact_self_cases[0].candidate_range.text == "targeted"
    assert result.exact_self_original_positive_count == 1
    assert result.exact_self_original_negative_count == 0


def test_report_uses_complete_inventory_and_renders_observed_head_count() -> None:
    matrix, oracle = _matrix_and_oracle()
    exact = _source_case(
        "1",
        candidate=matrix.candidates[1],
        event=matrix.event_options[0],
        original_gold="Y",
    )
    unequal = _source_case(
        "2",
        candidate=matrix.candidates[0],
        event=matrix.event_options[0],
        original_gold="N",
        reviewed_gold="Y",
    )
    structural = AttachmentStructuralSafetyReport.model_construct(
        development=_safety_phase("development", (exact, unequal)),
        validation=_safety_phase("validation", ()),
        total_edge_count=2,
        head_aligned_count=2,
        gold_conflict_count=1,
    )
    negative = _transfer_case("3", candidate=(0, 5), event=(6, 14))
    transfer = AttachmentResidualTransferReport.model_construct(
        development=_transfer_phase((negative,)),
        validation=_transfer_phase(()),
    )

    report = build_attachment_self_routing_report(
        evidence=(),
        residual_transfer=transfer,
        structural_safety=structural,
        development_matrices=(matrix,),
        development_oracle={matrix.id: oracle},
        development_source_text_by_event={EVENT_ID: SOURCE},
        validation_matrices=(),
        validation_oracle={},
        validation_source_text_by_event={},
    )

    assert report.outcome is AttachmentSelfRoutingOutcome.SUPPORTED
    assert report.all_edge_count == 2
    assert report.exact_self_count == 1
    assert report.unequal_range_count == 1
    assert report.head_aligned_exact_self_count == 1
    assert report.head_aligned_unequal_range_count == 1
    assert report.head_aligned_gold_conflict_count == 1
    assert report.routed_reviewed_negative_control_count == 0
    assert "Unequal-range edges: `1`" in render_attachment_self_routing_review(report)
    handoff = render_attachment_self_routing_handoff(
        report,
        package_files=(),
        source_repository_url="https://example.test/repo",
        source_revision="a" * 40,
    )
    assert "CEA-1.19 reached 2 Head-Aligned pairs." in handoff
    assert "cannot establish safety for unequal-range candidates" in handoff


def _matrix_and_oracle() -> tuple[
    CompetitiveAttachmentMatrix,
    tuple[CompetitiveAttachmentGoldDecision, ...],
]:
    unequal = _candidate(0, 14, "1")
    exact = _candidate(6, 14, "2")
    event = _event(6, 14)
    matrix_id = competitive_attachment_matrix_id(
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        candidate_ids=(unequal.id, exact.id),
        event_option_ids=(event.id,),
        decision_ids=(),
    )
    matrix = CompetitiveAttachmentMatrix(
        id=matrix_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        candidates=(unequal, exact),
        event_options=(event,),
    )
    return matrix, (
        CompetitiveAttachmentGoldDecision(candidate_id=unequal.id, source_grounded_event_ids=()),
        CompetitiveAttachmentGoldDecision(
            candidate_id=exact.id,
            source_grounded_event_ids=(EVENT_ID,),
        ),
    )


def _candidate(start: int, end: int, suffix: str) -> CompetitiveAttachmentCandidate:
    reasons = (PropositionFragmentReason.EVENT_EXPRESSION,)
    parent_ids = ("pfc_" + suffix * 24,)
    token_ids = ("t" + suffix,)
    record_ids = ("record_" + suffix,)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=SOURCE[start:end],
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
    return CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=SOURCE[start:end],
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )


def _event(start: int, end: int) -> CompetitiveAttachmentEventOption:
    trigger_id = "etd_" + "3" * 24
    option_id = competitive_attachment_event_option_id(
        source_grounded_event_id=EVENT_ID,
        event_trigger_id=trigger_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=SOURCE[start:end],
    )
    return CompetitiveAttachmentEventOption(
        id=option_id,
        label="E1",
        source_grounded_event_id=EVENT_ID,
        event_trigger_id=trigger_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=SOURCE[start:end],
    )


def _source_case(
    suffix: str,
    *,
    candidate: CompetitiveAttachmentCandidate,
    event: CompetitiveAttachmentEventOption,
    original_gold: str,
    reviewed_gold: str | None = None,
) -> AttachmentStructuralSafetyCase:
    return AttachmentStructuralSafetyCase.model_construct(
        phase="development",
        matrix_id="cam_" + suffix * 24,
        source_text=SOURCE,
        candidate=candidate,
        event=event,
        original_gold=original_gold,
        reviewed_gold=reviewed_gold,
        gold_conflict=reviewed_gold is not None and reviewed_gold != original_gold,
    )


def _safety_phase(
    phase: str,
    cases: tuple[AttachmentStructuralSafetyCase, ...],
) -> AttachmentStructuralSafetyPhase:
    values = tuple(case.model_copy(update={"phase": phase}) for case in cases)
    return AttachmentStructuralSafetyPhase.model_construct(phase=phase, cases=values)


def _transfer_case(
    suffix: str,
    *,
    candidate: tuple[int, int],
    event: tuple[int, int],
) -> AttachmentResidualTransferCase:
    candidate_value = SimpleNamespace(
        start=candidate[0],
        end=candidate[1],
        text=SOURCE[candidate[0] : candidate[1]],
        source_text_sha256=DIGEST,
    )
    event_value = AttachmentSourceRange(
        start=event[0],
        end=event[1],
        text=SOURCE[event[0] : event[1]],
    )
    task = SimpleNamespace(
        id="aro_" + suffix * 24,
        phase="development",
        edge_filter_task=SimpleNamespace(
            source_text=SOURCE,
            candidate=candidate_value,
            edge=SimpleNamespace(event_range=event_value),
        ),
    )
    return AttachmentResidualTransferCase.model_construct(
        task=task,
        gold=SimpleNamespace(expected_answer="N"),
    )


def _transfer_phase(
    cases: tuple[AttachmentResidualTransferCase, ...],
) -> AttachmentResidualTransferPhaseReport:
    return AttachmentResidualTransferPhaseReport.model_construct(cases=cases)
