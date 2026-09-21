from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterTask,
    AttachmentPartwiseArm,
    AttachmentPartwiseObservation,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentRemainderPartKind,
    AttachmentRemainderPartTask,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    aggregate_attachment_remainder_part_answers,
    attachment_candidate_remainder_ranges,
    attachment_contained_foreign_event_ids,
    attachment_edge_filter_model_task_input,
    attachment_partwise_outcome,
    attachment_pool_edge_id,
    attachment_remainder_part_kind,
    attachment_remainder_part_model_task_input,
    attachment_residual_remainder_model_task_input,
    build_attachment_edge_filter_task,
    build_attachment_remainder_part_tasks,
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


def test_remainder_renderer_exposes_exact_parts_without_ids_or_offsets() -> None:
    source = "Acme announced acquisition today."
    candidate_start = source.index("Acme")
    candidate_end = source.index(" today")
    target_start = source.index("announced")
    target_end = target_start + len("announced")
    task = _task(
        source,
        candidate_start,
        candidate_end,
        ((target_start, target_end),),
        0,
    )

    rendered = attachment_residual_remainder_model_task_input(task).decode()
    baseline = attachment_edge_filter_model_task_input(task).decode().rstrip()

    assert rendered.startswith(baseline + "\n\nCandidate Remainder parts:\n")
    assert "R1: <remainder>Acme </remainder>" in rendered
    assert "R2: <remainder> acquisition</remainder>" in rendered
    assert task.edge.id not in rendered
    assert task.candidate.id not in rendered
    assert str(candidate_start) not in rendered


def test_part_tasks_preserve_each_exact_remainder_range() -> None:
    source = "Acme announced acquisition today."
    task = _task(
        source,
        source.index("Acme"),
        source.index(" today"),
        ((source.index("announced"), source.index("announced") + len("announced")),),
        0,
    )
    residual = build_attachment_residual_ownership_task(task)

    parts = build_attachment_remainder_part_tasks(residual)

    assert tuple(item.source_range.text for item in parts) == ("Acme ", " acquisition")
    assert all(item.kind is AttachmentRemainderPartKind.SUBSTANTIVE for item in parts)
    rendered = attachment_remainder_part_model_task_input(task, 2).decode()
    assert rendered.endswith("Remainder Part:\n<remainder> acquisition</remainder>\n")
    assert "R1:" not in rendered
    assert parts[1].id not in rendered


def test_part_task_rejects_a_foreign_residual_task_reference() -> None:
    residual = build_attachment_residual_ownership_task(_contained_task(with_foreign_event=False))
    part = build_attachment_remainder_part_tasks(residual)[0]

    with pytest.raises(ValueError, match="foreign Residual Ownership"):
        AttachmentRemainderPartTask(
            id=part.id,
            residual_task_id="aro_" + "f" * 24,
            edge_filter_task=part.edge_filter_task,
            part_number=part.part_number,
            source_range=part.source_range,
            kind=part.kind,
            task_fingerprint=part.task_fingerprint,
        )


def test_part_character_class_is_unicode_deterministic() -> None:
    assert attachment_remainder_part_kind(" , [11] ") is AttachmentRemainderPartKind.SUBSTANTIVE
    assert attachment_remainder_part_kind(" , — ") is AttachmentRemainderPartKind.STRUCTURAL
    assert attachment_remainder_part_kind(" 日本 ") is AttachmentRemainderPartKind.SUBSTANTIVE


def test_part_answers_use_declared_candidate_level_aggregation() -> None:
    source = "Acme announced acquisition today."
    task = _task(
        source,
        source.index("Acme"),
        source.index(" today"),
        ((source.index("announced"), source.index("announced") + len("announced")),),
        0,
    )
    parts = build_attachment_remainder_part_tasks(build_attachment_residual_ownership_task(task))

    assert (
        aggregate_attachment_remainder_part_answers(
            parts,
            tuple(
                _part_observation(item, answer)
                for item, answer in zip(parts, ("Y", "Y"), strict=True)
            ),
        )
        == "Y"
    )
    assert (
        aggregate_attachment_remainder_part_answers(
            parts,
            tuple(
                _part_observation(item, answer)
                for item, answer in zip(parts, ("Y", "N"), strict=True)
            ),
        )
        == "N"
    )
    assert (
        aggregate_attachment_remainder_part_answers(
            parts,
            tuple(
                _part_observation(item, answer)
                for item, answer in zip(parts, ("Y", "U"), strict=True)
            ),
        )
        == "U"
    )
    with pytest.raises(ValueError, match="inventory"):
        aggregate_attachment_remainder_part_answers(parts, (_part_observation(parts[0], "Y"),))


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        ({}, "supported"),
        ({"regressed_case_count": 1}, "mixed"),
        ({"recovered_case_count": 0, "part_correct_count": 7}, "falsified"),
        ({"strict_finite_output_count": 51, "unresolved_output_count": 1}, "inconclusive"),
    ),
)
def test_partwise_outcome_uses_declared_safety_gates(
    overrides: dict[str, int],
    expected: str,
) -> None:
    values = {
        "strict_finite_output_count": 54,
        "unresolved_output_count": 0,
        "stable_whole_case_count": 10,
        "stable_part_case_count": 10,
        "whole_correct_count": 7,
        "part_correct_count": 10,
        "recovered_case_count": 3,
        "regressed_case_count": 0,
        "part_negative_correct_count": 2,
    }

    assert attachment_partwise_outcome(**(values | overrides)).value == expected


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


def _part_observation(
    part: AttachmentRemainderPartTask,
    answer: str,
) -> AttachmentPartwiseObservation:
    typed_answer = AttachmentEdgeFilterAnswerValue(answer)
    decision = AttachmentEdgeFilterDecision.model_construct(
        edge_id=part.edge_filter_task.edge.id,
        answer=typed_answer,
    )
    return AttachmentPartwiseObservation.model_construct(
        arm=AttachmentPartwiseArm.PART,
        part_task_id=part.id,
        decision=decision,
        strict_finite_answer=True,
    )
