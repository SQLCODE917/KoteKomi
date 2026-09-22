from __future__ import annotations

import hashlib
from base64 import b64encode
from typing import Literal

import pytest
from kotekomi_application import (
    AttachmentBlindReviewCase,
    AttachmentBlindReviewDecision,
    AttachmentBlindReviewEvaluation,
    AttachmentBlindReviewOutcome,
    AttachmentBlindReviewReport,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentNestedEventCase,
    AttachmentNestedEventObservation,
    AttachmentNestedEventOutcome,
    AttachmentNestedEventPreflight,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    CompetitiveAttachmentMatrix,
    PropositionFragmentReason,
    attachment_blind_review_case_id,
    attachment_nested_event_case_id,
    attachment_nested_event_ownership_model_task_input,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
    competitive_attachment_matrix_id,
)
from kotekomi_pipelines.competitive_attachment_nested_event_ownership import (
    build_attachment_nested_event_preflight,
    build_attachment_nested_event_report,
    render_attachment_nested_event_handoff,
)


def test_nested_event_preflight_derives_five_exclusions_and_hides_labels() -> None:
    values = tuple(
        _matrix_and_blind_evaluation(
            index,
            phase="development" if index < 5 else "validation",
            answer="N" if index == 1 else "Y",
        )
        for index in range(1, 6)
    )
    matrices = tuple(item[0] for item in values)
    evaluations = tuple(item[1] for item in values)
    blind = AttachmentBlindReviewReport.model_construct(
        outcome=AttachmentBlindReviewOutcome.MIXED,
        evaluations=evaluations,
        excluded_yes_count=4,
        excluded_no_count=1,
        excluded_unclear_count=0,
    )
    prompt = AttachmentEvidenceReference(
        label="prompt",
        path="/tmp/prompt.md",
        sha256="d" * 64,
    )

    preflight = build_attachment_nested_event_preflight(
        inputs=(),
        prompt=prompt,
        blind_report=blind,
        matrices=matrices,
    )

    assert preflight.case_count == 5
    assert preflight.expected_yes_count == 4
    assert preflight.expected_no_count == 1
    for case in preflight.cases:
        rendered = attachment_nested_event_ownership_model_task_input(case.task).decode()
        assert "expected" not in rendered.casefold()
        assert case.blind_case_id not in rendered


def test_nested_event_report_counts_two_complete_repetitions_per_case() -> None:
    cases = tuple(_case(index, "Y" if index < 5 else "N") for index in range(1, 6))
    preflight = AttachmentNestedEventPreflight.model_construct(cases=cases)
    observations = tuple(
        _observation(case, repetition, case.expected_answer)
        for case in cases
        for repetition in (1, 2)
    )

    report = build_attachment_nested_event_report(
        inputs=(),
        preflight=preflight,
        observations=observations,
    )

    assert report.outcome is AttachmentNestedEventOutcome.SUPPORTED
    assert report.case_count == 5
    assert report.observation_count == 10
    assert report.complete_observation_count == 10
    assert report.stable_case_count == 5
    assert report.positive_correct_decision_count == 8
    assert report.negative_correct_decision_count == 2
    assert report.model_identity_digests == ("a" * 64,)
    assert report.model_execution_count == 10
    assert report.model_elapsed_milliseconds == 50
    assert report.proposed_change_count == 0
    assert report.accepted_ledger_change_count == 0
    handoff = render_attachment_nested_event_handoff(
        report,
        prompt_text="Prompt.",
        package_files=(),
        source_repository_url="https://example.test/repository",
        source_revision="f" * 40,
    )
    assert "one-document diagnostic cannot establish transfer" in handoff
    assert "same-model-family consistency check" in handoff


def test_nested_event_report_rejects_missing_repetition() -> None:
    case = _case(1, "Y")
    preflight = AttachmentNestedEventPreflight.model_construct(cases=(case,))

    with pytest.raises(ValueError, match="two observations"):
        build_attachment_nested_event_report(
            inputs=(),
            preflight=preflight,
            observations=(_observation(case, 1, "Y"),),
        )


def _case(index: int, expected: Literal["Y", "N"]) -> AttachmentNestedEventCase:
    task = _task()
    blind_case_id = f"ubr_{index:024x}"
    return AttachmentNestedEventCase(
        id=attachment_nested_event_case_id(
            blind_case_id=blind_case_id,
            task_id=task.task_id,
        ),
        blind_case_id=blind_case_id,
        phase="development",
        task=task,
        contained_event_ids=tuple(item.source_grounded_event_id for item in task.event_options[1:]),
        expected_answer=expected,
        expected_rationale="Sealed test rationale.",
    )


def _observation(
    case: AttachmentNestedEventCase,
    repetition: Literal[1, 2],
    answer: Literal["Y", "N"],
) -> AttachmentNestedEventObservation:
    raw_output = answer.encode()
    decision = AttachmentEdgeFilterDecision(
        task_id=case.task.task_id,
        edge_id=case.task.edge.id,
        status=AttachmentEdgeFilterDecisionStatus.COMPLETE,
        answer=AttachmentEdgeFilterAnswerValue(answer),
        retained=answer == "Y",
        unresolved=False,
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        trace_id="xst_" + "1" * 24,
        raw_output_sha256=hashlib.sha256(raw_output).hexdigest(),
        diagnostic_code=None,
    )
    return AttachmentNestedEventObservation(
        case_id=case.id,
        repetition=repetition,
        decision=decision,
        execution_record=AttachmentEvidenceReference(
            label=f"execution_{case.id}_{repetition}",
            path=f"/tmp/{case.id}-{repetition}.json",
            sha256="c" * 64,
        ),
        exact_model_input="input",
        raw_output_base64=b64encode(raw_output).decode(),
        model_identity_digest="a" * 64,
        elapsed_milliseconds=5,
        runtime_invoked=True,
    )


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
                source_grounded_event_id=f"sge_{ordinal:024x}",
                event_trigger_id=f"etd_{ordinal:024x}",
                source_segment_id="seg_fixture",
                source_text_sha256=digest,
                start=source.index(text),
                end=source.index(text) + len(text),
                text=text,
            ),
            label=f"E{ordinal}",
            source_grounded_event_id=f"sge_{ordinal:024x}",
            event_trigger_id=f"etd_{ordinal:024x}",
            source_segment_id="seg_fixture",
            source_text_sha256=digest,
            start=source.index(text),
            end=source.index(text) + len(text),
            text=text,
        )
        for ordinal, text in enumerate(event_texts, start=1)
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


def _matrix_and_blind_evaluation(
    index: int,
    *,
    phase: Literal["development", "validation"],
    answer: Literal["Y", "N"],
) -> tuple[CompetitiveAttachmentMatrix, AttachmentBlindReviewEvaluation]:
    source = f"Agent {index} denied cancellation {index}."
    digest = hashlib.sha256(source.encode()).hexdigest()
    candidate_start = source.index("denied")
    candidate_end = source.index(".")
    reasons = (PropositionFragmentReason.EVENT_EXPRESSION,)
    parent_ids = (f"pfc_{index:024x}",)
    source_record_ids = (f"source_record_{index}",)
    segment_id = f"seg_fixture_{index}"
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id=segment_id,
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
        source_segment_id=segment_id,
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
                source_grounded_event_id=f"sge_{index * 10 + ordinal:024x}",
                event_trigger_id=f"etd_{index * 10 + ordinal:024x}",
                source_segment_id=segment_id,
                source_text_sha256=digest,
                start=source.index(text),
                end=source.index(text) + len(text),
                text=text,
            ),
            label=f"E{ordinal}",
            source_grounded_event_id=f"sge_{index * 10 + ordinal:024x}",
            event_trigger_id=f"etd_{index * 10 + ordinal:024x}",
            source_segment_id=segment_id,
            source_text_sha256=digest,
            start=source.index(text),
            end=source.index(text) + len(text),
            text=text,
        )
        for ordinal, text in enumerate(("denied", "cancellation"), start=1)
    )
    matrix_id = competitive_attachment_matrix_id(
        source_segment_id=segment_id,
        source_text_sha256=digest,
        candidate_ids=(candidate.id,),
        event_option_ids=tuple(item.id for item in options),
        decision_ids=(),
    )
    matrix = CompetitiveAttachmentMatrix(
        id=matrix_id,
        source_segment_id=segment_id,
        source_text_sha256=digest,
        candidates=(candidate,),
        event_options=options,
        decisions=(),
    )
    case_id = attachment_blind_review_case_id(
        phase=phase,
        matrix_id=matrix.id,
        candidate_id=candidate.id,
        event_id=options[0].source_grounded_event_id,
    )
    blind_case = AttachmentBlindReviewCase.model_construct(
        id=case_id,
        phase=phase,
        matrix_id=matrix.id,
        source_text=source,
        source_text_sha256=digest,
        candidate_id=candidate.id,
        event_id=options[0].source_grounded_event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate.start,
            end=candidate.end,
            text=candidate.text,
        ),
        event_range=AttachmentSourceRange(
            start=options[0].start,
            end=options[0].end,
            text=options[0].text,
        ),
        foreign_event_ids=(options[1].source_grounded_event_id,),
        structural_selected=False,
    )
    decision = AttachmentBlindReviewDecision(
        case_id=case_id,
        answer=answer,
        rationale="Sealed blind rationale.",
    )
    evaluation = AttachmentBlindReviewEvaluation.model_construct(
        case=blind_case,
        decision=decision,
    )
    return matrix, evaluation
