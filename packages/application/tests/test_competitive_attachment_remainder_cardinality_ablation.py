from __future__ import annotations

import hashlib
import math

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentFiniteLabelEvidence,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentRemainderCardinalityObservation,
    AttachmentRemainderCardinalityOutcome,
    AttachmentResidualOwnershipTask,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_pool_edge_id,
    attachment_remainder_cardinality_outcome,
    attachment_split_remainder_model_task_input,
    attachment_split_remainder_ranges,
    build_attachment_edge_filter_task,
    build_attachment_remainder_cardinality_view,
    build_attachment_remainder_enumeration_view,
    build_attachment_residual_ownership_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)
from kotekomi_domain import ModelRunStatus


def test_split_changes_only_one_remainder_boundary() -> None:
    task = _task()
    predecessor = build_attachment_remainder_enumeration_view(task)
    view = build_attachment_remainder_cardinality_view(predecessor)
    rendered = attachment_split_remainder_model_task_input(task).decode()

    assert view.predecessor_view == predecessor
    assert tuple(item.text for item in predecessor.filtered_remainder_ranges) == (
        " services with FedRAMP authorization",
    )
    assert tuple(item.text for item in view.split_remainder_ranges) == (
        " services",
        " with FedRAMP authorization",
    )
    assert "".join(item.text for item in view.split_remainder_ranges) == (
        predecessor.filtered_remainder_ranges[0].text
    )
    assert view.split_remainder_ranges[0].end == view.split_remainder_ranges[1].start
    assert "<candidate>that offered services with FedRAMP authorization</candidate>" in rendered
    assert "<event>offered</event>" in rendered
    assert "R1: <remainder> services</remainder>" in rendered
    assert "R2: <remainder> with FedRAMP authorization</remainder>" in rendered


def test_split_rejects_drifted_control_content() -> None:
    task = _task("Companies that offered products with FedRAMP authorization.")

    with pytest.raises(ValueError, match="one-part control drifted"):
        attachment_split_remainder_ranges(task)


@pytest.mark.parametrize(
    ("answer", "argmax", "strict", "expected"),
    (
        (
            "N",
            AttachmentEdgeFilterAnswerValue.NO,
            True,
            AttachmentRemainderCardinalityOutcome.SUPPORTED,
        ),
        (
            "Y",
            AttachmentEdgeFilterAnswerValue.YES,
            True,
            AttachmentRemainderCardinalityOutcome.FALSIFIED,
        ),
        (
            "U",
            AttachmentEdgeFilterAnswerValue.UNCLEAR,
            True,
            AttachmentRemainderCardinalityOutcome.INCONCLUSIVE,
        ),
        (
            "Y",
            AttachmentEdgeFilterAnswerValue.NO,
            True,
            AttachmentRemainderCardinalityOutcome.INCONCLUSIVE,
        ),
        (
            "Y",
            AttachmentEdgeFilterAnswerValue.YES,
            False,
            AttachmentRemainderCardinalityOutcome.INCONCLUSIVE,
        ),
    ),
)
def test_cardinality_outcome_requires_observed_and_probability_agreement(
    answer: str,
    argmax: AttachmentEdgeFilterAnswerValue,
    strict: bool,
    expected: AttachmentRemainderCardinalityOutcome,
) -> None:
    observation = _observation(answer, argmax, strict)

    assert attachment_remainder_cardinality_outcome(observation) is expected


def _observation(
    answer: str,
    argmax: AttachmentEdgeFilterAnswerValue,
    strict: bool,
) -> AttachmentRemainderCardinalityObservation:
    task = _task()
    view = build_attachment_remainder_cardinality_view(
        build_attachment_remainder_enumeration_view(task)
    )
    raw = answer
    decision_answer = AttachmentEdgeFilterAnswerValue(answer)
    probabilities = {
        value: (
            0.0 if value is argmax else -5.0 - tuple(AttachmentEdgeFilterAnswerValue).index(value)
        )
        for value in AttachmentEdgeFilterAnswerValue
    }
    competing = _logsumexp(
        tuple(
            probability
            for value, probability in probabilities.items()
            if value is not AttachmentEdgeFilterAnswerValue.YES
        )
    )
    evidence = AttachmentFiniteLabelEvidence(
        emitted_token=argmax.value,
        emitted_log_probability=0.0,
        yes_log_probability=probabilities[AttachmentEdgeFilterAnswerValue.YES],
        no_log_probability=probabilities[AttachmentEdgeFilterAnswerValue.NO],
        unclear_log_probability=probabilities[AttachmentEdgeFilterAnswerValue.UNCLEAR],
        finite_label_argmax=argmax,
        attachment_score=probabilities[AttachmentEdgeFilterAnswerValue.YES] - competing,
        answer_label_observed=False,
        answer_label_log_probability=None,
        lowest_alternative_log_probability=min(probabilities.values()),
        conservative_answer_log_probability=min(probabilities.values()),
    )
    return AttachmentRemainderCardinalityObservation(
        view_id=view.id,
        authoritative_task_id=task.id,
        decision=AttachmentEdgeFilterDecision(
            task_id=task.edge_filter_task.task_id,
            edge_id=task.edge_filter_task.edge.id,
            status=(
                AttachmentEdgeFilterDecisionStatus.UNCLEAR
                if decision_answer is AttachmentEdgeFilterAnswerValue.UNCLEAR
                else AttachmentEdgeFilterDecisionStatus.COMPLETE
            ),
            answer=decision_answer,
            retained=decision_answer is AttachmentEdgeFilterAnswerValue.YES,
            unresolved=decision_answer is AttachmentEdgeFilterAnswerValue.UNCLEAR,
            extraction_task_id="ext_fixture",
            model_run_id="mrn_fixture",
            trace_id="xst_" + "1" * 24,
            raw_output_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            diagnostic_code=(
                "model_unclear"
                if decision_answer is AttachmentEdgeFilterAnswerValue.UNCLEAR
                else None
            ),
        ),
        execution_record=AttachmentEvidenceReference(
            label="execution",
            path="/execution.json",
            sha256="a" * 64,
        ),
        exact_model_input="exact input",
        raw_output_text=raw,
        finite_label_evidence=evidence,
        model_identity_digest="b" * 64,
        model_run_status=ModelRunStatus.SUCCEEDED,
        output_token_count=1 if strict else 2,
        elapsed_milliseconds=1,
        strict_finite_answer=strict,
    )


def _task(
    source: str = "Companies that offered services with FedRAMP authorization.",
) -> AttachmentResidualOwnershipTask:
    candidate_start = source.index("that")
    candidate_end = source.index(".")
    event_start = source.index("offered")
    event_end = event_start + len("offered")
    digest = hashlib.sha256(source.encode()).hexdigest()
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


def _logsumexp(values: tuple[float, ...]) -> float:
    anchor = max(values)
    return anchor + math.log(sum(math.exp(item - anchor) for item in values))
