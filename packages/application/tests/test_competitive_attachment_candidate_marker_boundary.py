from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from kotekomi_application import (
    AttachmentCandidateMarkerArm,
    AttachmentCandidateMarkerArmEvaluation,
    AttachmentCandidateMarkerObservation,
    AttachmentCandidateMarkerOutcome,
    AttachmentCandidateMarkerView,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentResidualOwnershipTask,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_candidate_marker_outcome,
    attachment_pool_edge_id,
    attachment_residual_remainder_model_task_input,
    build_attachment_candidate_marker_view,
    build_attachment_edge_filter_task,
    build_attachment_residual_ownership_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)
from kotekomi_domain import ModelRunStatus


def test_marker_views_preserve_source_and_move_only_declared_boundaries() -> None:
    source = ",  that Acme announced policy,"
    task = _task(source, 0, len(source), source.index("announced"), len("announced"))

    structural = build_attachment_candidate_marker_view(
        task,
        AttachmentCandidateMarkerArm.STRUCTURAL_TRIM,
    )
    introducer = build_attachment_candidate_marker_view(
        task,
        AttachmentCandidateMarkerArm.INTRODUCER_TRIM,
    )

    assert task.edge_filter_task.candidate.text == source
    assert structural.rendered_task.edge_filter_task.candidate.text == "that Acme announced policy"
    assert structural.removed_prefix is not None
    assert structural.removed_prefix.text == ",  "
    assert structural.removed_suffix is not None
    assert structural.removed_suffix.text == ","
    assert structural.removed_introducer is None
    assert introducer.rendered_task.edge_filter_task.candidate.text == "Acme announced policy"
    assert introducer.removed_prefix is not None
    assert introducer.removed_prefix.text == ",  that "
    assert introducer.removed_introducer is not None
    assert introducer.removed_introducer.text == "that "
    assert introducer.removed_suffix is not None
    assert introducer.removed_suffix.text == ","


def test_marker_renderer_keeps_full_passage_and_recomputes_remainder_parts() -> None:
    source = "Companies that offered services."
    event_start = source.index("offered")
    task = _task(
        source,
        source.index("that"),
        source.index("."),
        event_start,
        len("offered"),
    )
    view = build_attachment_candidate_marker_view(
        task,
        AttachmentCandidateMarkerArm.INTRODUCER_TRIM,
    )

    rendered = attachment_residual_remainder_model_task_input(
        view.rendered_task.edge_filter_task
    ).decode()

    assert "<source>Companies that <candidate>offered services</candidate>.</source>" in rendered
    assert "<source>Companies that <event>offered</event> services.</source>" in rendered
    assert "R1: <remainder> services</remainder>" in rendered
    assert "<remainder>that " not in rendered
    assert view.authoritative_task.edge_filter_task.candidate.text == "that offered services"


def test_introducer_after_target_event_is_not_removed() -> None:
    source = "Acme announced that policy."
    event_start = source.index("announced")
    task = _task(source, 0, source.index("."), event_start, len("announced"))

    view = build_attachment_candidate_marker_view(
        task,
        AttachmentCandidateMarkerArm.INTRODUCER_TRIM,
    )

    assert view.rendered_task.edge_filter_task.candidate.text == "Acme announced that policy"
    assert view.removed_introducer is None


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        ({}, AttachmentCandidateMarkerOutcome.SUPPORTED),
        (
            {"introducer_regressed_count": 1},
            AttachmentCandidateMarkerOutcome.MIXED,
        ),
        (
            {"introducer_correct_count": 7},
            AttachmentCandidateMarkerOutcome.FALSIFIED,
        ),
        (
            {"introducer_recovered_count": 0},
            AttachmentCandidateMarkerOutcome.FALSIFIED,
        ),
        (
            {"stable_introducer_count": 9},
            AttachmentCandidateMarkerOutcome.INCONCLUSIVE,
        ),
    ),
)
def test_marker_outcome_uses_mutually_exclusive_gates(
    overrides: dict[str, int],
    expected: AttachmentCandidateMarkerOutcome,
) -> None:
    values = {
        "strict_finite_output_count": 40,
        "unresolved_output_count": 0,
        "stable_structural_count": 10,
        "stable_introducer_count": 10,
        "baseline_correct_count": 7,
        "introducer_correct_count": 9,
        "introducer_recovered_count": 2,
        "introducer_regressed_count": 0,
    }

    assert attachment_candidate_marker_outcome(**(values | overrides)) is expected


def test_marker_view_rejects_changed_rendered_task() -> None:
    source = "that Acme announced policy"
    task = _task(source, 0, len(source), source.index("announced"), len("announced"))
    view = build_attachment_candidate_marker_view(
        task,
        AttachmentCandidateMarkerArm.INTRODUCER_TRIM,
    )

    with pytest.raises(ValueError, match="drifted from authoritative"):
        payload = view.model_dump(mode="python")
        payload["rendered_task"] = task
        AttachmentCandidateMarkerView.model_validate(payload)


@pytest.mark.parametrize("failure", ("missing", "duplicate", "foreign"))
def test_marker_arm_rejects_incomplete_or_foreign_observations(failure: str) -> None:
    source = "that Acme announced policy"
    task = _task(source, 0, len(source), source.index("announced"), len("announced"))
    view = build_attachment_candidate_marker_view(
        task,
        AttachmentCandidateMarkerArm.INTRODUCER_TRIM,
    )
    first = _observation(view, 1)
    second = _observation(view, 2)
    observations = (first, second)
    if failure == "missing":
        observations = (first,)
    elif failure == "duplicate":
        observations = (first, first)
    else:
        observations = (
            first,
            second.model_copy(update={"view_id": "amv_" + "f" * 24}),
        )

    with pytest.raises(ValueError, match="ordered observations|foreign observation"):
        AttachmentCandidateMarkerArmEvaluation(
            view=view,
            expected_answer="Y",
            baseline_passed=False,
            observations=observations,
            answers=tuple("Y" for _ in observations),
            stable=True,
            passed=True,
            recovered=True,
            regressed=False,
        )


def _observation(
    view: AttachmentCandidateMarkerView,
    repetition: Literal[1, 2],
) -> AttachmentCandidateMarkerObservation:
    task = view.rendered_task.edge_filter_task
    raw = "Y"
    return AttachmentCandidateMarkerObservation(
        arm=view.arm,
        repetition=repetition,
        view_id=view.id,
        authoritative_task_id=view.authoritative_task.id,
        rendered_task_id=view.rendered_task.id,
        decision=AttachmentEdgeFilterDecision(
            task_id=task.task_id,
            edge_id=task.edge.id,
            status=AttachmentEdgeFilterDecisionStatus.COMPLETE,
            answer=AttachmentEdgeFilterAnswerValue.YES,
            retained=True,
            unresolved=False,
            extraction_task_id=f"ext_fixture_{repetition}",
            model_run_id=f"mrn_fixture_{repetition}",
            trace_id="xst_" + f"{repetition:024x}",
            raw_output_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            diagnostic_code=None,
        ),
        execution_record=AttachmentEvidenceReference(
            label=f"execution_{repetition}",
            path=f"/execution-{repetition}.json",
            sha256="a" * 64,
        ),
        exact_model_input="exact input",
        raw_output_text=raw,
        model_identity_digest="b" * 64,
        model_run_status=ModelRunStatus.SUCCEEDED,
        output_token_count=1,
        probability_positions=(0,),
        elapsed_milliseconds=1,
        strict_finite_answer=True,
    )


def _task(
    source: str,
    candidate_start: int,
    candidate_end: int,
    event_start: int,
    event_length: int,
) -> AttachmentResidualOwnershipTask:
    digest = hashlib.sha256(source.encode()).hexdigest()
    event_end = event_start + event_length
    reasons = (PropositionFragmentReason.CLAUSE_LOCAL_CONSTITUENT,)
    parent_candidate_ids = ("pfc_" + "1" * 24,)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=candidate_start,
        end=candidate_end,
        text=source[candidate_start:candidate_end],
        reasons=reasons,
        parent_candidate_ids=parent_candidate_ids,
        linguistic_token_ids=(),
        source_record_ids=("source_record_fixture",),
    )
    candidate = CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=candidate_start,
        end=candidate_end,
        text=source[candidate_start:candidate_end],
        reasons=reasons,
        parent_candidate_ids=parent_candidate_ids,
        linguistic_token_ids=(),
        source_record_ids=("source_record_fixture",),
    )
    option_id = competitive_attachment_event_option_id(
        source_grounded_event_id="sge_" + "1" * 24,
        event_trigger_id="etd_" + "1" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=event_start,
        end=event_end,
        text=source[event_start:event_end],
    )
    option = CompetitiveAttachmentEventOption(
        id=option_id,
        label="E1",
        source_grounded_event_id="sge_" + "1" * 24,
        event_trigger_id="etd_" + "1" * 24,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=event_start,
        end=event_end,
        text=source[event_start:event_end],
    )
    edge_values = {
        "phase": "development",
        "source_segment_id": "seg_fixture",
        "source_text_sha256": digest,
        "candidate_id": candidate.id,
        "source_grounded_event_id": option.source_grounded_event_id,
        "candidate_start": candidate_start,
        "candidate_end": candidate_end,
        "event_start": event_start,
        "event_end": event_end,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**edge_values),
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        candidate_id=candidate.id,
        source_grounded_event_id=option.source_grounded_event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate_start,
            end=candidate_end,
            text=source[candidate_start:candidate_end],
        ),
        event_range=AttachmentSourceRange(
            start=event_start,
            end=event_end,
            text=source[event_start:event_end],
        ),
        origins=(AttachmentProposalOrigin.QWEN,),
        syntax_arms=(),
    )
    edge_task = build_attachment_edge_filter_task(
        source_text=source,
        edge=edge,
        candidate=candidate,
        event_options=(option,),
    )
    return build_attachment_residual_ownership_task(edge_task)
