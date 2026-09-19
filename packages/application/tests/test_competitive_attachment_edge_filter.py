from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterDiagnosticCatalog,
    AttachmentEdgeFilterTask,
    AttachmentPoolArm,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    CompetitiveAttachmentMatrix,
    FilteredAttachmentSetStatus,
    attachment_edge_filter_model_task_input,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    build_competitive_attachment_matrix,
    build_filtered_attachment_set,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
    parse_attachment_edge_filter_answer,
)

from packages.application.tests.test_competitive_event_attachment import (
    SOURCE,
    candidate_fixture,
    event_fixture,
)


def test_edge_filter_task_exposes_only_source_and_task_local_labels() -> None:
    matrix, edge = _matrix_and_edge()
    task = build_attachment_edge_filter_task(
        source_text=SOURCE,
        edge=edge,
        candidate=matrix.candidates[0],
        event_options=matrix.event_options,
    )

    rendered = attachment_edge_filter_model_task_input(task).decode()

    assert "<candidate>Alex</candidate>" in rendered
    assert "<event>criticized</event>" in rendered
    assert 'E2: "opposed"' in rendered
    assert task.target_event_label == "E1"
    assert all(
        forbidden not in rendered
        for forbidden in ("cac_", "sge_", "ape_", "Gold", "Qwen", "syntax", "offset")
    )


def test_edge_filter_answer_parser_accepts_only_finite_contract() -> None:
    assert parse_attachment_edge_filter_answer(b" Y\n") is AttachmentEdgeFilterAnswerValue.YES
    assert parse_attachment_edge_filter_answer(b"N") is AttachmentEdgeFilterAnswerValue.NO
    assert parse_attachment_edge_filter_answer(b"U") is AttachmentEdgeFilterAnswerValue.UNCLEAR

    for invalid in (b"YES", b"Y because", b'"Y"', b""):
        try:
            parse_attachment_edge_filter_answer(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid answer was accepted: {invalid!r}")


def test_edge_filter_prompt_requires_one_atomic_candidate_fact() -> None:
    prompt = (
        Path(__file__).parents[3] / "prompts/competitive_attachment_edge_filter_v1.md"
    ).read_text(encoding="utf-8")

    assert "the whole meaningful Candidate belongs" in prompt
    assert "mixes another Event into the Candidate" in prompt
    assert "Plan A and opposed Plan B</candidate>" in prompt
    assert "Orion partnered with <candidate>Nova</candidate>" in prompt
    assert "<candidate>with Nova and Cedar, companies that supplied sensors</candidate>" in prompt
    assert "<candidate>In March</candidate>" in prompt
    assert "<candidate>Orion</candidate> launched Model A. Later, Orion revised" in prompt
    assert "Judge only the marked Candidate occurrence" in prompt


def test_diagnostic_catalog_requires_all_six_development_source_segments() -> None:
    matrix, _ = _matrix_and_edge()
    tasks = tuple(
        _diagnostic_task(
            matrix,
            source_segment_id=f"seg_{index % 6}",
            candidate_index=index % len(matrix.candidates),
            target_index=(index // 2) % len(matrix.event_options),
            include_syntax=index >= 12,
        )
        for index in range(16)
    )
    categories = (
        "qwen_false_positive",
        "syntax_only_true",
        "syntax_only_false",
        "shared_fragment",
        "shared_entity",
        "gold_none",
        "repeated_occurrence",
        "attribution",
        "temporal",
        "long_dependency_path",
    )
    coverage = {
        task.task_id: ((categories[index],) if index < len(categories) else ())
        for index, task in enumerate(tasks)
    }

    catalog = _diagnostic_catalog(tasks, coverage)

    assert len({task.edge.source_segment_id for task in catalog.tasks}) == 6

    clustered = tuple(
        _diagnostic_task(
            matrix,
            source_segment_id="seg_one",
            candidate_index=(index // 4) % len(matrix.candidates),
            target_index=(index // 2) % len(matrix.event_options),
            include_syntax=bool(index % 2),
        )
        for index in range(16)
    )
    clustered_coverage = {
        task.task_id: ((categories[index],) if index < len(categories) else ())
        for index, task in enumerate(clustered)
    }
    with pytest.raises(ValueError, match="all six development SourceSegments"):
        _diagnostic_catalog(clustered, clustered_coverage)


def test_filtered_sets_distinguish_evidenced_none_unresolved_and_pool_gap() -> None:
    matrix, edge = _matrix_and_edge()
    no = _decision(edge, AttachmentEdgeFilterAnswerValue.NO)
    unclear = _decision(edge, AttachmentEdgeFilterAnswerValue.UNCLEAR)

    evidenced_none = build_filtered_attachment_set(
        phase="development",
        arm=AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT,
        candidate_id=matrix.candidates[0].id,
        edges=(edge,),
        decisions_by_edge_id={edge.id: no},
    )
    unresolved = build_filtered_attachment_set(
        phase="development",
        arm=AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT,
        candidate_id=matrix.candidates[0].id,
        edges=(edge,),
        decisions_by_edge_id={edge.id: unclear},
    )
    gap = build_filtered_attachment_set(
        phase="development",
        arm=AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT,
        candidate_id=matrix.candidates[0].id,
        edges=(),
        decisions_by_edge_id={},
    )

    assert evidenced_none.status is FilteredAttachmentSetStatus.EVIDENCED_NONE
    assert evidenced_none.rejected_event_ids == (edge.source_grounded_event_id,)
    assert unresolved.status is FilteredAttachmentSetStatus.UNRESOLVED
    assert unresolved.unresolved_event_ids == (edge.source_grounded_event_id,)
    assert gap.status is FilteredAttachmentSetStatus.POOL_GAP


def _matrix_and_edge():  # type: ignore[no-untyped-def]
    first_event, first_trigger = event_fixture("criticized", 1)
    second_event, second_trigger = event_fixture("opposed", 2)
    ranges = (
        (0, 4),
        (SOURCE.index("criticized"), SOURCE.index("criticized") + len("criticized")),
        (SOURCE.index("Plan A"), SOURCE.index("Plan A") + len("Plan A")),
        (SOURCE.rindex("Alex"), SOURCE.rindex("Alex") + len("Alex")),
    )
    parents = tuple(
        candidate_fixture(
            first_event.id,
            first_trigger.id,
            start,
            end,
            ordinal=ordinal,
        )
        for ordinal, (start, end) in enumerate(ranges, start=1)
    )
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE,
        event_inputs=((first_event, first_trigger), (second_event, second_trigger)),
        candidates_by_event={first_event.id: parents, second_event.id: ()},
    )
    candidate = matrix.candidates[0]
    option = matrix.event_options[0]
    values = {
        "phase": "development",
        "source_segment_id": matrix.source_segment_id,
        "source_text_sha256": matrix.source_text_sha256,
        "candidate_id": candidate.id,
        "source_grounded_event_id": option.source_grounded_event_id,
        "candidate_start": candidate.start,
        "candidate_end": candidate.end,
        "event_start": option.start,
        "event_end": option.end,
    }
    edge = AttachmentPoolEdge(
        id=attachment_pool_edge_id(**values),
        phase="development",
        source_segment_id=matrix.source_segment_id,
        source_text_sha256=matrix.source_text_sha256,
        candidate_id=candidate.id,
        source_grounded_event_id=option.source_grounded_event_id,
        candidate_range=AttachmentSourceRange(
            start=candidate.start,
            end=candidate.end,
            text=candidate.text,
        ),
        event_range=AttachmentSourceRange(
            start=option.start,
            end=option.end,
            text=option.text,
        ),
        origins=(AttachmentProposalOrigin.QWEN, AttachmentProposalOrigin.SYNTAX),
        syntax_arms=tuple(AttachmentPoolArm),
    )
    return matrix, edge


def _decision(
    edge: AttachmentPoolEdge,
    answer: AttachmentEdgeFilterAnswerValue,
) -> AttachmentEdgeFilterDecision:
    unclear = answer is AttachmentEdgeFilterAnswerValue.UNCLEAR
    return AttachmentEdgeFilterDecision(
        task_id="aet_" + "1" * 24,
        edge_id=edge.id,
        status=(
            AttachmentEdgeFilterDecisionStatus.UNCLEAR
            if unclear
            else AttachmentEdgeFilterDecisionStatus.COMPLETE
        ),
        answer=answer,
        retained=answer is AttachmentEdgeFilterAnswerValue.YES,
        unresolved=unclear,
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        trace_id="xst_" + "1" * 24,
        raw_output_sha256="a" * 64,
        diagnostic_code="model_unclear" if unclear else None,
    )


def _diagnostic_catalog(
    tasks: tuple[AttachmentEdgeFilterTask, ...],
    coverage: dict[str, tuple[str, ...]],
) -> AttachmentEdgeFilterDiagnosticCatalog:
    payload = {
        "tasks": [task.model_dump(mode="json") for task in tasks],
        "coverage_by_task_id": coverage,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return AttachmentEdgeFilterDiagnosticCatalog(
        tasks=tasks,
        coverage_by_task_id=coverage,
        catalog_sha256=digest,
    )


def _diagnostic_task(
    matrix: CompetitiveAttachmentMatrix,
    *,
    source_segment_id: str,
    candidate_index: int,
    target_index: int,
    include_syntax: bool,
) -> AttachmentEdgeFilterTask:
    original_candidate = matrix.candidates[candidate_index]
    candidate_values = {
        "source_segment_id": source_segment_id,
        "source_text_sha256": original_candidate.source_text_sha256,
        "start": original_candidate.start,
        "end": original_candidate.end,
        "text": original_candidate.text,
        "reasons": original_candidate.reasons,
        "parent_candidate_ids": original_candidate.parent_candidate_ids,
        "linguistic_token_ids": original_candidate.linguistic_token_ids,
        "source_record_ids": original_candidate.source_record_ids,
    }
    candidate = original_candidate.model_copy(
        update={
            "id": competitive_attachment_candidate_id(**candidate_values),
            "source_segment_id": source_segment_id,
        }
    )
    event_options = tuple(
        option.model_copy(
            update={
                "id": competitive_attachment_event_option_id(
                    source_grounded_event_id=option.source_grounded_event_id,
                    event_trigger_id=option.event_trigger_id,
                    source_segment_id=source_segment_id,
                    source_text_sha256=option.source_text_sha256,
                    start=option.start,
                    end=option.end,
                    text=option.text,
                ),
                "source_segment_id": source_segment_id,
            }
        )
        for option in matrix.event_options
    )
    target = event_options[target_index]
    edge_values = {
        "phase": "development",
        "source_segment_id": source_segment_id,
        "source_text_sha256": matrix.source_text_sha256,
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
        source_segment_id=source_segment_id,
        source_text_sha256=matrix.source_text_sha256,
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
        origins=(
            (AttachmentProposalOrigin.QWEN, AttachmentProposalOrigin.SYNTAX)
            if include_syntax
            else (AttachmentProposalOrigin.QWEN,)
        ),
        syntax_arms=tuple(AttachmentPoolArm) if include_syntax else (),
    )
    return build_attachment_edge_filter_task(
        source_text=SOURCE,
        edge=edge,
        candidate=candidate,
        event_options=event_options,
    )
