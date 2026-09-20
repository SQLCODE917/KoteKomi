from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterTask,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_candidate_remainder_ranges,
    attachment_contained_foreign_event_ids,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    build_attachment_residual_ownership_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)


def test_residual_task_preserves_exact_candidate_remainder() -> None:
    task = _contained_task(with_foreign_event=False)

    result = build_attachment_residual_ownership_task(task)

    assert tuple(item.text for item in result.remainder_ranges) == ("announced ",)
    assert attachment_contained_foreign_event_ids(task) == ()


def test_residual_task_rejects_a_contained_foreign_event() -> None:
    task = _contained_task(with_foreign_event=True)

    assert attachment_contained_foreign_event_ids(task) == (
        task.event_options[0].source_grounded_event_id,
    )
    with pytest.raises(ValueError, match="Foreign Event"):
        build_attachment_residual_ownership_task(task)


def test_candidate_remainder_requires_proper_containment() -> None:
    task = _separate_task()

    with pytest.raises(ValueError, match="proper Target Event containment"):
        attachment_candidate_remainder_ranges(task)


def _contained_task(*, with_foreign_event: bool) -> AttachmentEdgeFilterTask:
    source = "Acme announced acquisition."
    candidate_start = source.index("announced")
    candidate_end = source.index(".")
    target_start = source.index("acquisition")
    target_end = target_start + len("acquisition")
    event_ranges = (
        ((candidate_start, candidate_start + len("announced")),) if with_foreign_event else ()
    )
    event_ranges += ((target_start, target_end),)
    return _task(source, candidate_start, candidate_end, event_ranges, len(event_ranges) - 1)


def _separate_task() -> AttachmentEdgeFilterTask:
    source = "Acme announced acquisition."
    candidate_start = 0
    candidate_end = len("Acme")
    target_start = source.index("acquisition")
    target_end = target_start + len("acquisition")
    return _task(source, candidate_start, candidate_end, ((target_start, target_end),), 0)


def _task(
    source: str,
    candidate_start: int,
    candidate_end: int,
    event_ranges: tuple[tuple[int, int], ...],
    target_index: int,
) -> AttachmentEdgeFilterTask:
    digest = hashlib.sha256(source.encode()).hexdigest()
    reasons = (PropositionFragmentReason.ENTITY_OCCURRENCE,)
    parent_candidate_ids = ("pfc_" + "1" * 24,)
    linguistic_token_ids: tuple[str, ...] = ()
    source_record_ids = ("source_record_fixture",)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        start=candidate_start,
        end=candidate_end,
        text=source[candidate_start:candidate_end],
        reasons=reasons,
        parent_candidate_ids=parent_candidate_ids,
        linguistic_token_ids=linguistic_token_ids,
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
        parent_candidate_ids=parent_candidate_ids,
        linguistic_token_ids=linguistic_token_ids,
        source_record_ids=source_record_ids,
    )
    options = tuple(
        CompetitiveAttachmentEventOption(
            id=competitive_attachment_event_option_id(
                event_trigger_id=f"etd_{index + 1:024x}",
                source_segment_id="seg_fixture",
                source_text_sha256=digest,
                source_grounded_event_id=f"sge_{index + 1:024x}",
                start=start,
                end=end,
                text=source[start:end],
            ),
            label=f"E{index + 1}",
            source_grounded_event_id=f"sge_{index + 1:024x}",
            event_trigger_id=f"etd_{index + 1:024x}",
            source_segment_id="seg_fixture",
            source_text_sha256=digest,
            start=start,
            end=end,
            text=source[start:end],
        )
        for index, (start, end) in enumerate(event_ranges)
    )
    target = options[target_index]
    values = {
        "phase": "development",
        "source_segment_id": "seg_fixture",
        "source_text_sha256": digest,
        "candidate_id": candidate_id,
        "source_grounded_event_id": target.source_grounded_event_id,
        "candidate_start": candidate_start,
        "candidate_end": candidate_end,
        "event_start": target.start,
        "event_end": target.end,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**values),
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=digest,
        candidate_id=candidate_id,
        source_grounded_event_id=target.source_grounded_event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate_start,
            end=candidate_end,
            text=source[candidate_start:candidate_end],
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
