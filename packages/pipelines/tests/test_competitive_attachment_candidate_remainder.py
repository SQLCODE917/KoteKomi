from __future__ import annotations

import hashlib
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest
from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentCandidateRemainderArm,
    AttachmentCandidateRemainderObservation,
    AttachmentCandidateRemainderPreflight,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentResidualCueAblationReport,
    AttachmentResidualGoldAdjudication,
    AttachmentResidualOwnershipTask,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    build_attachment_residual_ownership_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)
from kotekomi_pipelines.competitive_attachment_candidate_remainder import (
    build_candidate_remainder_report,
    validate_candidate_remainder_prompt_pair,
)

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "a" * 64


def test_candidate_remainder_prompt_preserves_demonstrations_and_adds_remainder() -> None:
    baseline = (ROOT / "prompts/competitive_attachment_residual_ownership_v2.md").read_text()
    remainder = (ROOT / "prompts/competitive_attachment_residual_ownership_v3.md").read_text()

    validate_candidate_remainder_prompt_pair(baseline, remainder)

    with pytest.raises(ValueError, match="explicit Remainder contract"):
        validate_candidate_remainder_prompt_pair(baseline, baseline)


@pytest.mark.parametrize(
    ("mode", "expected_outcome"),
    (
        ("supported", "supported"),
        ("mixed", "mixed"),
        ("falsified", "falsified"),
        ("inconclusive", "inconclusive"),
    ),
)
def test_paired_report_classifies_exact_candidate_remainder_effect(
    mode: str,
    expected_outcome: str,
) -> None:
    tasks = tuple(sorted((_residual_task(index) for index in range(10)), key=lambda item: item.id))
    adjudicated = tasks[0]
    adjudication = AttachmentResidualGoldAdjudication(
        task_id=adjudicated.id,
        edge_id=adjudicated.edge_filter_task.edge.id,
        candidate_range=adjudicated.edge_filter_task.edge.candidate_range,
        target_event_range=adjudicated.edge_filter_task.edge.event_range,
        inherited_answer="N",
        corrected_answer="Y",
        rationale="exact_attachment_range_does_not_answer_residual_ownership",
    )
    expected_by_task: dict[str, Literal["Y", "N"]] = {
        task.id: ("Y" if index < 8 else "N") for index, task in enumerate(tasks)
    }
    cue_cases = tuple(
        SimpleNamespace(
            task_id=task.id,
            edge_id=task.edge_filter_task.edge.id,
            inherited_expected_answer=(
                "N" if task.id == adjudicated.id else expected_by_task[task.id]
            ),
            expected_answer=expected_by_task[task.id],
        )
        for task in tasks
    )
    cue_report = cast(AttachmentResidualCueAblationReport, SimpleNamespace(cases=cue_cases))
    baseline_observations: list[AttachmentCandidateRemainderObservation] = []
    remainder_observations: list[AttachmentCandidateRemainderObservation] = []
    for index, task in enumerate(tasks):
        expected = expected_by_task[task.id]
        baseline_observations.append(
            _observation(task, AttachmentCandidateRemainderArm.BASELINE, expected, "N", 0.1, 0.85)
        )
        answer: str | None = "N"
        yes_probability = 0.1
        no_probability = 0.85
        if expected == "Y" and mode in {"supported", "mixed", "inconclusive"}:
            answer = "Y"
            yes_probability = 0.8
            no_probability = 0.15
        if mode == "mixed" and expected == "N" and index == 8:
            answer = "Y"
            yes_probability = 0.95
            no_probability = 0.04
        if mode == "inconclusive" and index == 0:
            answer = None
        remainder_observations.append(
            _observation(
                task,
                AttachmentCandidateRemainderArm.REMAINDER,
                expected,
                answer,
                yes_probability,
                no_probability,
            )
        )
    reference = AttachmentEvidenceReference(label="input", path="/input", sha256=DIGEST)
    preflight = cast(
        AttachmentCandidateRemainderPreflight,
        SimpleNamespace(
            tasks=tasks,
            baseline_prompt=reference,
            remainder_prompt=AttachmentEvidenceReference(
                label="remainder", path="/remainder", sha256="b" * 64
            ),
            gold_adjudications=(adjudication,),
        ),
    )

    report = build_candidate_remainder_report(
        inputs=(reference,),
        preflight=preflight,
        cue_report=cue_report,
        baseline_observations=tuple(baseline_observations),
        remainder_observations=tuple(remainder_observations),
    )

    assert report.outcome.value == expected_outcome
    assert report.probability_evidence_count == (19 if mode == "inconclusive" else 20)
    if mode == "supported":
        assert report.positive_recovery_count == 8
        assert report.negative_regression_count == 0
        assert report.remainder_correct_count == 10
        assert report.positive_median_score_delta is not None
        assert report.negative_max_score_delta == 0.0


def _observation(
    task: AttachmentResidualOwnershipTask,
    arm: AttachmentCandidateRemainderArm,
    expected: Literal["Y", "N"],
    answer: str | None,
    yes_probability: float,
    no_probability: float,
) -> AttachmentCandidateRemainderObservation:
    typed_task = task.edge_filter_task
    raw = answer
    status = (
        AttachmentEdgeFilterDecisionStatus.COMPLETE
        if answer is not None
        else AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT
    )
    typed_answer = AttachmentEdgeFilterAnswerValue(answer) if answer is not None else None
    raw_digest = hashlib.sha256(raw.encode()).hexdigest() if raw is not None else None
    decision = AttachmentEdgeFilterDecision(
        task_id=typed_task.task_id,
        edge_id=typed_task.edge.id,
        status=status,
        answer=typed_answer,
        retained=typed_answer is AttachmentEdgeFilterAnswerValue.YES,
        unresolved=answer is None,
        extraction_task_id="ext_" + "1" * 24 if answer is not None else None,
        model_run_id="mrn_" + "2" * 32 if answer is not None else None,
        trace_id="xst_" + "3" * 24 if answer is not None else None,
        raw_output_sha256=raw_digest,
        diagnostic_code="invalid_model_output" if answer is None else None,
    )
    probability = (
        _probability(typed_answer, yes_probability, no_probability)
        if typed_answer is not None
        else None
    )
    return AttachmentCandidateRemainderObservation(
        arm=arm,
        task_id=task.id,
        edge_id=typed_task.edge.id,
        expected_answer=expected,
        decision=decision,
        probability=probability,
        model_identity_digest="f" * 64 if probability is not None else None,
        execution_record=AttachmentEvidenceReference(
            label=f"{arm.value}_{task.id}",
            path=f"/{arm.value}/{typed_task.task_id}.json",
            sha256=DIGEST,
        ),
        exact_model_input="exact input",
        raw_output_text=raw,
        elapsed_milliseconds=1,
        passed=answer == expected,
    )


def _probability(
    answer: AttachmentEdgeFilterAnswerValue,
    yes_probability: float,
    no_probability: float,
) -> AttachmentAnswerProbability:
    unclear_probability = 1.0 - yes_probability - no_probability
    yes = math.log(yes_probability)
    no = math.log(no_probability)
    unclear = math.log(unclear_probability)
    score = yes - math.log(no_probability + unclear_probability)
    return AttachmentAnswerProbability(
        token_position=0,
        emitted_answer=answer,
        yes_log_probability=yes,
        no_log_probability=no,
        unclear_log_probability=unclear,
        attachment_score=score,
    )


def _residual_task(index: int) -> AttachmentResidualOwnershipTask:
    source = f"Actor{index} criticized policy{index}."
    candidate_start = 0
    candidate_end = source.index(".")
    event_start = source.index("criticized")
    event_end = event_start + len("criticized")
    digest = hashlib.sha256(source.encode()).hexdigest()
    reasons = (PropositionFragmentReason.ENTITY_OCCURRENCE,)
    parent_candidate_ids = (f"pfc_{index + 1:024x}",)
    source_record_ids = (f"source_record_{index}",)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id=f"seg_{index}",
        source_text_sha256=digest,
        start=candidate_start,
        end=candidate_end,
        text=source[candidate_start:candidate_end],
        reasons=reasons,
        parent_candidate_ids=parent_candidate_ids,
        linguistic_token_ids=(),
        source_record_ids=source_record_ids,
    )
    candidate = CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id=f"seg_{index}",
        source_text_sha256=digest,
        start=candidate_start,
        end=candidate_end,
        text=source[candidate_start:candidate_end],
        reasons=reasons,
        parent_candidate_ids=parent_candidate_ids,
        linguistic_token_ids=(),
        source_record_ids=source_record_ids,
    )
    event_id = f"sge_{index + 1:024x}"
    trigger_id = f"etd_{index + 1:024x}"
    option = CompetitiveAttachmentEventOption(
        id=competitive_attachment_event_option_id(
            event_trigger_id=trigger_id,
            source_segment_id=f"seg_{index}",
            source_text_sha256=digest,
            source_grounded_event_id=event_id,
            start=event_start,
            end=event_end,
            text="criticized",
        ),
        label="E1",
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id=f"seg_{index}",
        source_text_sha256=digest,
        start=event_start,
        end=event_end,
        text="criticized",
    )
    edge_values = {
        "phase": "development",
        "source_segment_id": f"seg_{index}",
        "source_text_sha256": digest,
        "candidate_id": candidate_id,
        "source_grounded_event_id": event_id,
        "candidate_start": candidate_start,
        "candidate_end": candidate_end,
        "event_start": event_start,
        "event_end": event_end,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**edge_values),
        phase="development",
        source_segment_id=f"seg_{index}",
        source_text_sha256=digest,
        candidate_id=candidate_id,
        source_grounded_event_id=event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate_start,
            end=candidate_end,
            text=source[candidate_start:candidate_end],
        ),
        event_range=AttachmentSourceRange(
            start=event_start,
            end=event_end,
            text="criticized",
        ),
        origins=(AttachmentProposalOrigin.QWEN,),
        syntax_arms=(),
    )
    return build_attachment_residual_ownership_task(
        build_attachment_edge_filter_task(
            source_text=source,
            edge=edge,
            candidate=candidate,
            event_options=(option,),
        )
    )
