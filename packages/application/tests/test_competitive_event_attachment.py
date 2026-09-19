from __future__ import annotations

import hashlib

import pytest
from kotekomi_application import (
    CompetitiveAttachmentAnswer,
    CompetitiveAttachmentAnswerKind,
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentEdgeOrigin,
    CompetitiveAttachmentEventOrder,
    EventTriggerDraft,
    PropositionFragmentCandidate,
    PropositionFragmentReason,
    build_competitive_attachment_decision,
    build_competitive_attachment_matrix,
    build_source_grounded_event_draft,
    canonicalize_competitive_attachment_answer,
    competitive_attachment_decision_id,
    competitive_attachment_model_task_input,
    competitive_attachment_task_event_options,
    complete_competitive_attachment_matrix,
    proposition_fragment_candidate_id,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id

SOURCE = "Alex criticized Plan A and opposed Plan B; Alex supported Plan C."


def test_matrix_deduplicates_equal_ranges_without_collapsing_repeated_text() -> None:
    event_one, trigger_one = event_fixture("criticized", 1)
    event_two, trigger_two = event_fixture("opposed", 2)
    first_alex = (0, 4)
    second_alex = (SOURCE.index("Alex", 5), SOURCE.index("Alex", 5) + 4)
    candidates = {
        event_one.id: (
            candidate_fixture(event_one.id, trigger_one.id, *first_alex, ordinal=1),
            candidate_fixture(event_one.id, trigger_one.id, *second_alex, ordinal=2),
        ),
        event_two.id: (candidate_fixture(event_two.id, trigger_two.id, *first_alex, ordinal=3),),
    }

    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event_two, trigger_two), (event_one, trigger_one)),
        candidates_by_event=candidates,
    )

    assert tuple(item.label for item in matrix.event_options) == ("E1", "E2")
    assert tuple(item.text for item in matrix.event_options) == ("criticized", "opposed")
    assert len(matrix.candidates) == 2
    assert len(matrix.candidates[0].parent_candidate_ids) == 2
    assert matrix.candidates[0].start == 0
    assert matrix.candidates[1].start == second_alex[0]


def test_model_task_comarks_candidate_with_every_competing_event() -> None:
    event_one, trigger_one = event_fixture("criticized", 1)
    event_two, trigger_two = event_fixture("opposed", 2)
    parent = candidate_fixture(event_one.id, trigger_one.id, 0, 4, ordinal=1)
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event_one, trigger_one), (event_two, trigger_two)),
        candidates_by_event={event_one.id: (parent,), event_two.id: ()},
    )

    rendered = competitive_attachment_model_task_input(
        source_text=SOURCE,
        candidate=matrix.candidates[0],
        event_options=matrix.event_options,
    ).decode()

    assert rendered.count("<candidate>Alex</candidate>") == 3
    assert rendered.count("<event>") == 2
    assert "<candidate>Alex</candidate> <event>criticized</event>" in rendered
    assert "<candidate>Alex</candidate> criticized Plan A and <event>opposed</event>" in rendered
    assert "E1:" in rendered and "E2:" in rendered
    assert "sge_" not in rendered
    assert "etd_" not in rendered


def test_model_task_nests_identical_candidate_and_event_occurrences() -> None:
    event, trigger = event_fixture("criticized", 1)
    parent = candidate_fixture(
        event.id,
        trigger.id,
        trigger.start,
        trigger.end,
        ordinal=1,
        reason=PropositionFragmentReason.EVENT_EXPRESSION,
    )
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event, trigger),),
        candidates_by_event={event.id: (parent,)},
    )

    rendered = competitive_attachment_model_task_input(
        source_text=SOURCE,
        candidate=matrix.candidates[0],
        event_options=matrix.event_options,
    ).decode()

    assert "<candidate><event>criticized</event></candidate>" in rendered


def test_model_task_uses_separate_views_for_crossing_ranges() -> None:
    event, trigger = event_fixture("criticized", 1)
    parent = candidate_fixture(event.id, trigger.id, 0, 10, ordinal=1)
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event, trigger),),
        candidates_by_event={event.id: (parent,)},
    )

    rendered = competitive_attachment_model_task_input(
        source_text=SOURCE,
        candidate=matrix.candidates[0],
        event_options=matrix.event_options,
    ).decode()

    assert "E1:\nCandidate view:" in rendered
    assert "</source>\nEvent view:\n<source>" in rendered
    assert "<candidate>Alex criti</candidate>" in rendered
    assert "<event>criticized</event>" in rendered


def test_reversed_event_order_relabels_without_changing_source_occurrences() -> None:
    event_one, trigger_one = event_fixture("criticized", 1)
    event_two, trigger_two = event_fixture("opposed", 2)
    parent = candidate_fixture(event_one.id, trigger_one.id, 0, 4, ordinal=1)
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event_one, trigger_one), (event_two, trigger_two)),
        candidates_by_event={event_one.id: (parent,), event_two.id: ()},
    )

    reversed_options = competitive_attachment_task_event_options(
        matrix.event_options,
        CompetitiveAttachmentEventOrder.REVERSED,
    )

    assert tuple(item.label for item in reversed_options) == ("E1", "E2")
    assert tuple(item.text for item in reversed_options) == ("opposed", "criticized")
    assert tuple((item.start, item.end) for item in reversed_options) == tuple(
        (item.start, item.end) for item in reversed(matrix.event_options)
    )
    assert tuple(item.id for item in reversed_options) == tuple(
        item.id for item in reversed(matrix.event_options)
    )


def test_reversed_event_answer_maps_back_to_canonical_event_labels() -> None:
    event_one, trigger_one = event_fixture("criticized", 1)
    event_two, trigger_two = event_fixture("opposed", 2)
    parent = candidate_fixture(event_one.id, trigger_one.id, 0, 4, ordinal=1)
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event_one, trigger_one), (event_two, trigger_two)),
        candidates_by_event={event_one.id: (parent,), event_two.id: ()},
    )
    reversed_options = competitive_attachment_task_event_options(
        matrix.event_options,
        CompetitiveAttachmentEventOrder.REVERSED,
    )

    canonical = canonicalize_competitive_attachment_answer(
        CompetitiveAttachmentAnswer(
            CompetitiveAttachmentAnswerKind.ATTACHED,
            ("E1",),
        ),
        task_event_options=reversed_options,
        canonical_event_options=matrix.event_options,
    )

    assert canonical.event_labels == ("E2",)


def test_deterministic_event_expression_survives_model_omission() -> None:
    event_one, trigger_one = event_fixture("criticized", 1)
    parent = candidate_fixture(
        event_one.id,
        trigger_one.id,
        trigger_one.start,
        trigger_one.end,
        ordinal=1,
        reason=PropositionFragmentReason.EVENT_EXPRESSION,
    )
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event_one, trigger_one),),
        candidates_by_event={event_one.id: (parent,)},
    )

    decision = build_competitive_attachment_decision(
        candidate=matrix.candidates[0],
        event_options=matrix.event_options,
        status=CompetitiveAttachmentDecisionStatus.COMPLETE,
        answer=CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.NONE),
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        trace_id="xst_" + "1" * 24,
        raw_output=b"NONE",
        diagnostic_code=None,
    )

    assert decision.model_event_ids == ()
    assert decision.deterministic_event_ids == (event_one.id,)
    assert decision.omitted_deterministic_event_ids == (event_one.id,)
    assert len(decision.edges) == 1
    assert decision.edges[0].origins == (
        CompetitiveAttachmentEdgeOrigin.DETERMINISTIC_EVENT_EXPRESSION,
    )


def test_matrix_rejects_candidate_text_that_does_not_replay_source() -> None:
    event, trigger = event_fixture("criticized", 1)
    candidate = candidate_fixture(event.id, trigger.id, 0, 4, ordinal=1)
    damaged = candidate.model_copy(update={"text": "Alec"})

    with pytest.raises(ValueError, match="not source-exact"):
        build_competitive_attachment_matrix(
            source_text=SOURCE,
            event_inputs=((event, trigger),),
            candidates_by_event={event.id: (damaged,)},
        )


def test_matrix_rejects_task_local_label_that_escapes_its_event_options() -> None:
    event, trigger = event_fixture("criticized", 1)
    parent = candidate_fixture(event.id, trigger.id, 0, 4, ordinal=1)
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((event, trigger),),
        candidates_by_event={event.id: (parent,)},
    )
    decision = build_competitive_attachment_decision(
        candidate=matrix.candidates[0],
        event_options=matrix.event_options,
        status=CompetitiveAttachmentDecisionStatus.COMPLETE,
        answer=CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.ATTACHED, ("E1",)),
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        trace_id="xst_" + "2" * 24,
        raw_output=b"E1",
        diagnostic_code=None,
    )
    escaped_labels = ("E2",)
    escaped_id = competitive_attachment_decision_id(
        candidate_id=decision.candidate_id,
        status=decision.status,
        parsed_event_labels=escaped_labels,
        deterministic_event_ids=decision.deterministic_event_ids,
        model_event_ids=decision.model_event_ids,
        edge_ids=tuple(item.id for item in decision.edges),
        extraction_task_id=decision.extraction_task_id,
        model_run_id=decision.model_run_id,
        trace_id=decision.trace_id,
        raw_output_sha256=decision.raw_output_sha256,
        diagnostic_code=decision.diagnostic_code,
    )
    escaped = decision.model_copy(update={"id": escaped_id, "parsed_event_labels": escaped_labels})

    with pytest.raises(ValueError, match="foreign task-local label"):
        complete_competitive_attachment_matrix(matrix, (escaped,))


def event_fixture(text: str, ordinal: int):  # type: ignore[no-untyped-def]
    digest = hashlib.sha256(SOURCE.encode()).hexdigest()
    start = SOURCE.index(text)
    end = start + len(text)
    trace_id = f"xst_{ordinal:024x}"
    trigger_id = event_trigger_id(
        source_segment_id="seg_competitive_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
        head_start=start,
        head_end=end,
        head_text=text,
        event_type_label="unmapped",
        extraction_task_id=f"ext_trigger_{ordinal}",
        model_run_id=f"mrn_trigger_{ordinal}",
        trace_id=trace_id,
    )
    trigger = EventTriggerDraft(
        id=trigger_id,
        source_segment_id="seg_competitive_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
        head_start=start,
        head_end=end,
        head_text=text,
        event_type_label="unmapped",
        extraction_task_id=f"ext_trigger_{ordinal}",
        model_run_id=f"mrn_trigger_{ordinal}",
        trace_id=trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id=f"esd_{ordinal:024x}",
        trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=digest,
        expression_text=text,
        head_text=text,
        head_evidence_target_id=f"etg_{ordinal * 3:024x}",
        expression_evidence_target_id=f"etg_{ordinal * 3 + 1:024x}",
        support_evidence_target_id=f"etg_{ordinal * 3 + 2:024x}",
    )
    return event, trigger


def candidate_fixture(
    event_id: str,
    trigger_id: str,
    start: int,
    end: int,
    *,
    ordinal: int,
    reason: PropositionFragmentReason = PropositionFragmentReason.ENTITY_OCCURRENCE,
) -> PropositionFragmentCandidate:
    digest = hashlib.sha256(SOURCE.encode()).hexdigest()
    text = SOURCE[start:end]
    reasons = (reason,)
    token_ids = (f"t{ordinal}",)
    record_ids = (f"record_{ordinal}",)
    candidate_id = proposition_fragment_candidate_id(
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_competitive_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
        reasons=reasons,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
    return PropositionFragmentCandidate(
        id=candidate_id,
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_competitive_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
        reasons=reasons,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
