from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterTask,
    AttachmentNestedEventCase,
    AttachmentNestedEventEvaluation,
    AttachmentNestedEventOutcome,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_nested_event_case_id,
    attachment_nested_event_ownership_model_task_input,
    attachment_nested_event_ownership_nonthinking_model_task_input,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    classify_attachment_nested_event_outcome,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)


def test_nested_event_renderer_exposes_only_plain_source_task_terms() -> None:
    task = _task()

    rendered = attachment_nested_event_ownership_model_task_input(task).decode()

    assert "Passage:\nRina denied the committee's cancellation and planned a review." in rendered
    assert 'Candidate:\n"denied the committee\'s cancellation and planned a review"' in rendered
    assert 'Target Event:\n"denied"' in rendered
    assert 'C1: "cancellation"' in rendered
    assert 'C2: "planned"' in rendered
    assert "sge_" not in rendered
    assert "Expected" not in rendered
    assert "offset" not in rendered.casefold()


def test_qwen3_nonthinking_control_follows_the_complete_semantic_task() -> None:
    task = _task()

    semantic = attachment_nested_event_ownership_model_task_input(task)
    rendered = attachment_nested_event_ownership_nonthinking_model_task_input(task)

    assert rendered == semantic + b"\n/no_think\n"
    assert rendered.rstrip().endswith(b"/no_think")


def test_nested_event_case_requires_every_contained_event_in_source_order() -> None:
    task = _task()
    blind_case_id = "ubr_" + "8" * 24

    with pytest.raises(ValueError, match="inventory drifted"):
        AttachmentNestedEventCase(
            id=attachment_nested_event_case_id(
                blind_case_id=blind_case_id,
                task_id=task.task_id,
            ),
            blind_case_id=blind_case_id,
            phase="development",
            task=task,
            contained_event_ids=(task.event_options[1].source_grounded_event_id,),
            expected_answer="Y",
            expected_rationale="Both embedded events belong to the denial content.",
        )


@pytest.mark.parametrize(
    ("evaluations", "expected"),
    (
        (
            (("Y", True, True, 2),) * 4 + (("N", True, True, 2),),
            AttachmentNestedEventOutcome.SUPPORTED,
        ),
        (
            (("Y", True, True, 2),) * 3 + (("Y", True, True, 0), ("N", True, True, 2)),
            AttachmentNestedEventOutcome.MIXED,
        ),
        (
            (("Y", True, True, 2),) * 4 + (("N", True, True, 0),),
            AttachmentNestedEventOutcome.FALSIFIED,
        ),
        (
            (("Y", False, False, 1),) + (("Y", True, True, 2),) * 3 + (("N", True, True, 2),),
            AttachmentNestedEventOutcome.INCONCLUSIVE,
        ),
    ),
)
def test_nested_event_outcome_uses_declared_safety_gates(
    evaluations: tuple[tuple[str, bool, bool, int], ...],
    expected: AttachmentNestedEventOutcome,
) -> None:
    values = tuple(
        AttachmentNestedEventEvaluation.model_construct(
            case=AttachmentNestedEventCase.model_construct(expected_answer=answer),
            observations=(),
            complete=complete,
            stable=stable,
            correct_decision_count=correct,
        )
        for answer, complete, stable, correct in evaluations
    )

    assert classify_attachment_nested_event_outcome(evaluations=values) is expected


def _task() -> AttachmentEdgeFilterTask:
    source = "Rina denied the committee's cancellation and planned a review."
    candidate_start = source.index("denied")
    candidate_end = source.index(".")
    event_texts = ("denied", "cancellation", "planned")
    digest = hashlib.sha256(source.encode()).hexdigest()
    reasons = (PropositionFragmentReason.EVENT_EXPRESSION,)
    parent_ids = ("pfc_" + "1" * 24,)
    source_record_ids = ("source_record_fixture",)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=candidate_start,
        end=candidate_end,
        text=source[candidate_start:candidate_end],
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=(),
        source_record_ids=source_record_ids,
    )
    candidate = CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=candidate_start,
        end=candidate_end,
        text=source[candidate_start:candidate_end],
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=(),
        source_record_ids=source_record_ids,
    )
    options = tuple(
        CompetitiveAttachmentEventOption(
            id=competitive_attachment_event_option_id(
                source_grounded_event_id=f"sge_{index:024x}",
                event_trigger_id=f"etd_{index:024x}",
                source_segment_id="seg_fixture",
                source_text_sha256=digest,
                start=source.index(text),
                end=source.index(text) + len(text),
                text=text,
            ),
            label=f"E{index}",
            source_grounded_event_id=f"sge_{index:024x}",
            event_trigger_id=f"etd_{index:024x}",
            source_segment_id="seg_fixture",
            source_text_sha256=digest,
            start=source.index(text),
            end=source.index(text) + len(text),
            text=text,
        )
        for index, text in enumerate(event_texts, start=1)
    )
    target = options[0]
    edge_values = {
        "phase": "development",
        "source_segment_id": "seg_fixture",
        "source_text_sha256": digest,
        "candidate_id": candidate.id,
        "source_grounded_event_id": target.source_grounded_event_id,
        "candidate_start": candidate.start,
        "candidate_end": candidate.end,
        "event_start": target.start,
        "event_end": target.end,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**edge_values),
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        candidate_id=candidate.id,
        source_grounded_event_id=target.source_grounded_event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate.start,
            end=candidate.end,
            text=candidate.text,
        ),
        event_range=AttachmentSourceRange(
            start=target.start,
            end=target.end,
            text=target.text,
        ),
        origins=(AttachmentProposalOrigin.QWEN,),
        syntax_arms=(),
    )
    return build_attachment_edge_filter_task(
        source_text=source,
        edge=edge,
        candidate=candidate,
        event_options=options,
    )
