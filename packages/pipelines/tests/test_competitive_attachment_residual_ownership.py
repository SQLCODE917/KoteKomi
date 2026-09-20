from __future__ import annotations

import hashlib
from typing import Literal

from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentResidualOwnershipObservation,
    AttachmentResidualOwnershipOutcome,
    AttachmentResidualOwnershipReport,
    AttachmentResidualOwnershipTask,
    AttachmentSourceRange,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PropositionFragmentReason,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)
from kotekomi_pipelines.competitive_attachment_residual_ownership import (
    build_attachment_residual_ownership_report,
    partition_containment_tasks,
)

DIGEST = "a" * 64


def test_partition_separates_foreign_event_and_residual_containment_without_gold() -> None:
    foreign = _task(1, with_foreign_event=True)
    residual = _task(2, with_foreign_event=False)

    mixed_ids, residual_tasks = partition_containment_tasks((foreign, residual))

    assert mixed_ids == (foreign.edge.id,)
    assert tuple(item.edge_filter_task.edge.id for item in residual_tasks) == (residual.edge.id,)


def test_report_classifies_supported_mixed_and_falsified_results() -> None:
    tasks = tuple(_task(index, with_foreign_event=False) for index in range(1, 11))
    _, residual_tasks = partition_containment_tasks(tasks)
    expected: dict[str, Literal["Y", "N"]] = {
        task.id: ("Y" if index < 7 else "N") for index, task in enumerate(residual_tasks)
    }

    supported = _report(residual_tasks, expected)
    mixed = _report(residual_tasks, expected, wrong_negative=True)
    falsified = _report(residual_tasks, expected, wrong_positive=True)

    assert supported.outcome is AttachmentResidualOwnershipOutcome.SUPPORTED
    assert supported.correct_observation_count == 20
    assert mixed.outcome is AttachmentResidualOwnershipOutcome.MIXED
    assert mixed.positive_retention_count == 14
    assert falsified.outcome is AttachmentResidualOwnershipOutcome.FALSIFIED
    assert falsified.positive_retention_count == 12


def _report(
    tasks: tuple[AttachmentResidualOwnershipTask, ...],
    expected: dict[str, Literal["Y", "N"]],
    *,
    wrong_negative: bool = False,
    wrong_positive: bool = False,
) -> AttachmentResidualOwnershipReport:
    observations: list[AttachmentResidualOwnershipObservation] = []
    negative_changed = False
    positive_changed = False
    for task in tasks:
        answer = expected[task.id]
        if wrong_negative and answer == "N" and not negative_changed:
            answer = "Y"
            negative_changed = True
        if wrong_positive and answer == "Y" and not positive_changed:
            answer = "N"
            positive_changed = True
        for repetition in (1, 2):
            raw = answer
            decision = AttachmentEdgeFilterDecision(
                task_id=task.edge_filter_task.task_id,
                edge_id=task.edge_filter_task.edge.id,
                status=AttachmentEdgeFilterDecisionStatus.COMPLETE,
                answer=AttachmentEdgeFilterAnswerValue(answer),
                retained=answer == "Y",
                unresolved=False,
                extraction_task_id=f"ext_{task.id[4:]}{repetition}",
                model_run_id=f"mrn_{task.id[4:]}{repetition}",
                trace_id=f"xst_{task.id[4:]}",
                raw_output_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                diagnostic_code=None,
            )
            observations.append(
                AttachmentResidualOwnershipObservation(
                    repetition=repetition,
                    task_id=task.id,
                    edge_id=task.edge_filter_task.edge.id,
                    expected_answer=expected[task.id],
                    decision=decision,
                    execution_record=AttachmentEvidenceReference(
                        label=f"execution_{task.id}_{repetition}",
                        path=f"/{task.id}-{repetition}.json",
                        sha256=DIGEST,
                    ),
                    exact_model_input="exact input",
                    raw_output_text=raw,
                    elapsed_milliseconds=1,
                    passed=answer == expected[task.id],
                )
            )
    reference = AttachmentEvidenceReference(label="input", path="/input.json", sha256=DIGEST)
    return build_attachment_residual_ownership_report(
        inputs=(reference,),
        prompt=AttachmentEvidenceReference(label="prompt", path="/prompt.md", sha256=DIGEST),
        tasks=tasks,
        expected_answers=expected,
        observations=tuple(observations),
    )


def _task(index: int, *, with_foreign_event: bool) -> AttachmentEdgeFilterTask:
    source = f"Actor {index} announced acquisition."
    candidate_start = source.index("announced")
    candidate_end = source.index(".")
    target_start = source.index("acquisition")
    target_end = target_start + len("acquisition")
    event_ranges = (
        ((candidate_start, candidate_start + len("announced")),) if with_foreign_event else ()
    )
    event_ranges += ((target_start, target_end),)
    digest = hashlib.sha256(source.encode()).hexdigest()
    segment_id = f"seg_fixture_{index}"
    reasons = (PropositionFragmentReason.ENTITY_OCCURRENCE,)
    parent_candidate_ids = (f"pfc_{index:024x}",)
    linguistic_token_ids: tuple[str, ...] = ()
    source_record_ids = (f"source_record_{index}",)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id=segment_id,
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
        source_segment_id=segment_id,
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
                event_trigger_id=f"etd_{index * 10 + ordinal:024x}",
                source_segment_id=segment_id,
                source_text_sha256=digest,
                source_grounded_event_id=f"sge_{index * 10 + ordinal:024x}",
                start=start,
                end=end,
                text=source[start:end],
            ),
            label=f"E{ordinal}",
            source_grounded_event_id=f"sge_{index * 10 + ordinal:024x}",
            event_trigger_id=f"etd_{index * 10 + ordinal:024x}",
            source_segment_id=segment_id,
            source_text_sha256=digest,
            start=start,
            end=end,
            text=source[start:end],
        )
        for ordinal, (start, end) in enumerate(event_ranges, start=1)
    )
    target = options[-1]
    edge_values = {
        "phase": "development",
        "source_segment_id": segment_id,
        "source_text_sha256": digest,
        "candidate_id": candidate_id,
        "source_grounded_event_id": target.source_grounded_event_id,
        "candidate_start": candidate_start,
        "candidate_end": candidate_end,
        "event_start": target.start,
        "event_end": target.end,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**edge_values),
        phase="development",
        source_segment_id=segment_id,
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
