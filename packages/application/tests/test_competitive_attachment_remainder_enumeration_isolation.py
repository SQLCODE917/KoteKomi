from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentRemainderEnumerationCaseEvaluation,
    AttachmentRemainderEnumerationMechanism,
    AttachmentRemainderEnumerationObservation,
    AttachmentRemainderEnumerationOutcome,
    AttachmentRemainderEnumerationView,
    AttachmentResidualOwnershipTask,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_filtered_remainder_model_task_input,
    attachment_filtered_remainder_ranges,
    attachment_ownership_remainder_model_task_input,
    attachment_ownership_remainder_ranges,
    attachment_pool_edge_id,
    attachment_remainder_enumeration_mechanism,
    attachment_remainder_enumeration_outcome,
    attachment_residual_remainder_model_task_input,
    build_attachment_edge_filter_task,
    build_attachment_remainder_enumeration_view,
    build_attachment_residual_ownership_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)
from kotekomi_domain import ModelRunStatus


def test_function_only_that_remainder_is_omitted_without_moving_candidate() -> None:
    source = "Companies that offered services."
    candidate_start = source.index("that")
    event_start = source.index("offered")
    task = _task(source, candidate_start, source.index("."), event_start, len("offered"))

    view = build_attachment_remainder_enumeration_view(task)
    rendered = attachment_filtered_remainder_model_task_input(task).decode()

    assert view.authoritative_task == task
    assert tuple(item.text for item in view.omitted_ranges) == ("that ",)
    assert tuple(item.text for item in view.filtered_remainder_ranges) == (" services",)
    assert "<candidate>that offered services</candidate>" in rendered
    assert "R1: <remainder> services</remainder>" in rendered
    assert "<remainder>that </remainder>" not in rendered


def test_that_is_filtered_but_semantic_prefix_remainder_is_retained() -> None:
    source = "They said that Anthropic had held discussions with officials."
    candidate_start = source.index("that")
    event_start = source.index("discussions")
    task = _task(source, candidate_start, source.index("."), event_start, len("discussions"))

    filtered, omitted = attachment_filtered_remainder_ranges(task)
    rendered = attachment_filtered_remainder_model_task_input(task).decode()

    assert tuple(item.text for item in omitted) == ("that ",)
    assert tuple(item.text for item in filtered) == (
        "Anthropic had held ",
        " with officials",
    )
    assert "<candidate>that Anthropic had held discussions with officials</candidate>" in rendered
    assert "R1: <remainder>Anthropic had held </remainder>" in rendered
    assert "R2: <remainder> with officials</remainder>" in rendered


def test_filter_rejects_task_without_leading_that_remainder() -> None:
    source = "Companies offered services."
    event_start = source.index("offered")
    task = _task(source, 0, source.index("."), event_start, len("offered"))

    with pytest.raises(ValueError, match="requires a leading `that`"):
        attachment_filtered_remainder_ranges(task)


def test_transfer_renderer_matches_whole_task_without_leading_that() -> None:
    source = "Companies offered services."
    event_start = source.index("offered")
    task = _task(source, 0, source.index("."), event_start, len("offered"))

    displayed, omitted = attachment_ownership_remainder_ranges(task)

    assert omitted == ()
    assert displayed == task.remainder_ranges
    assert attachment_ownership_remainder_model_task_input(
        task
    ) == attachment_residual_remainder_model_task_input(task.edge_filter_task)


def test_transfer_renderer_matches_filtered_task_with_leading_that() -> None:
    source = "Companies that offered services."
    event_start = source.index("offered")
    task = _task(source, source.index("that"), source.index("."), event_start, len("offered"))

    displayed, omitted = attachment_ownership_remainder_ranges(task)

    assert tuple(item.text for item in displayed) == (" services",)
    assert tuple(item.text for item in omitted) == ("that ",)
    assert attachment_ownership_remainder_model_task_input(
        task
    ) == attachment_filtered_remainder_model_task_input(task)


@pytest.mark.parametrize("failure", ("missing", "duplicate", "foreign"))
def test_case_evaluation_rejects_missing_duplicate_or_foreign_observations(
    failure: str,
) -> None:
    source = "Companies that offered services."
    task = _task(
        source,
        source.index("that"),
        source.index("."),
        source.index("offered"),
        len("offered"),
    )
    view = build_attachment_remainder_enumeration_view(task)
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
            second.model_copy(update={"view_id": "are_" + "f" * 24}),
        )

    with pytest.raises(ValueError, match="requires repetitions|foreign observation"):
        AttachmentRemainderEnumerationCaseEvaluation(
            view=view,
            expected_answer="Y",
            structural_answers=("N", "N"),
            introducer_answers=("Y", "Y"),
            observations=observations,
            fresh_answers=tuple("Y" for _ in observations),
            stable=True,
            passed=True,
        )


@pytest.mark.parametrize(
    ("recovered", "control", "outcome", "mechanism"),
    (
        (
            ("Y", "Y"),
            ("N", "N"),
            AttachmentRemainderEnumerationOutcome.SUPPORTED,
            AttachmentRemainderEnumerationMechanism.PART_INVENTORY_SUFFICIENT,
        ),
        (
            ("Y", "Y"),
            ("Y", "Y"),
            AttachmentRemainderEnumerationOutcome.SUPPORTED,
            AttachmentRemainderEnumerationMechanism.INTRODUCER_ENUMERATION_SUFFICIENT,
        ),
        (
            ("N", "N"),
            ("N", "N"),
            AttachmentRemainderEnumerationOutcome.FALSIFIED,
            AttachmentRemainderEnumerationMechanism.MARKER_EFFECT_REMAINS,
        ),
        (
            ("Y", "U"),
            ("N", "N"),
            AttachmentRemainderEnumerationOutcome.INCONCLUSIVE,
            AttachmentRemainderEnumerationMechanism.INCONCLUSIVE,
        ),
    ),
)
def test_outcome_and_mechanism_are_explicit(
    recovered: tuple[str, str],
    control: tuple[str, str],
    outcome: AttachmentRemainderEnumerationOutcome,
    mechanism: AttachmentRemainderEnumerationMechanism,
) -> None:
    actual_outcome = attachment_remainder_enumeration_outcome(
        strict_finite_output_count=4,
        unresolved_output_count=0,
        stable_case_count=2,
        recovered_answers=recovered,  # type: ignore[arg-type]
    )
    actual_mechanism = attachment_remainder_enumeration_mechanism(
        outcome=actual_outcome,
        recovered_answers=recovered,  # type: ignore[arg-type]
        hard_control_answers=control,  # type: ignore[arg-type]
    )

    assert actual_outcome is outcome
    assert actual_mechanism is mechanism


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
    edge_id = attachment_pool_edge_id(
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        candidate_id=candidate.id,
        source_grounded_event_id=option.source_grounded_event_id,
        candidate_start=candidate_start,
        candidate_end=candidate_end,
        event_start=event_start,
        event_end=event_end,
    )
    edge = AttachmentPoolEdge(
        id=edge_id,
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


def _observation(
    view: AttachmentRemainderEnumerationView,
    repetition: Literal[1, 2],
) -> AttachmentRemainderEnumerationObservation:
    task = view.authoritative_task.edge_filter_task
    raw = "Y"
    return AttachmentRemainderEnumerationObservation(
        repetition=repetition,
        view_id=view.id,
        authoritative_task_id=view.authoritative_task.id,
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
