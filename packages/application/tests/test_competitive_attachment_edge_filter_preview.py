from __future__ import annotations

from typing import cast

from kotekomi_application import (
    ATTACHMENT_EDGE_FILTER_POLICY_ID,
    PARAGRAPH_SEGMENT_V3,
    AttachmentEdgeFilterCommand,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    ContextModelProfile,
    ExecutionSetting,
    SourceSegmentAnalysisUnitInput,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    build_competitive_attachment_matrix,
    create_analysis_unit_from_source_segment,
    paragraph_source_segments,
    run_attachment_edge_filter,
)
from kotekomi_application.competitive_attachment_edge_filter_preview import (
    AttachmentEdgeFilterArchive,
    AttachmentEdgeFilterLedger,
)

from packages.application.tests.test_competitive_event_attachment_preview import (
    SOURCE_TEXT,
    candidate_fixture,
    event_fixture,
)
from packages.application.tests.test_source_grounded_proposition_preview import (
    FixtureArchive,
    FixtureLedger,
    FixtureRunIds,
    FixtureRuntime,
)


def test_edge_filter_preview_preserves_exact_input_output_and_never_writes_state() -> None:
    result, ledger, runtime, archive = _run(b"Y")

    assert result.decision.status is AttachmentEdgeFilterDecisionStatus.COMPLETE
    assert result.decision.retained is True
    assert result.trace.input["exact_model_input"]
    assert result.trace.output["raw_output_text"] == "Y"
    assert len(runtime.requests) == 1
    assert set(archive.outputs) == {result.model_run_id}
    assert ledger.accepted_write_attempted is False


def test_edge_filter_preview_isolates_invalid_output_as_unresolved() -> None:
    result, ledger, _, _ = _run(b"Y because")

    assert result.decision.status is AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT
    assert result.decision.unresolved is True
    assert result.decision.retained is False
    assert result.trace.output["raw_output_text"] == "Y because"
    assert ledger.accepted_write_attempted is False


def _run(output: bytes):  # type: ignore[no-untyped-def]
    ledger = FixtureLedger()
    runtime = FixtureRuntime((output,))
    archive = FixtureArchive()
    paragraph = next(item for item in ledger.bundle.nodes if item.node_type == "paragraph")
    segment = paragraph_source_segments(SOURCE_TEXT, PARAGRAPH_SEGMENT_V3)[0]
    unit = create_analysis_unit_from_source_segment(
        SourceSegmentAnalysisUnitInput(
            representation_id=ledger.bundle.representation.id,
            paragraph_node_id=paragraph.id,
            source_segment_label=segment.label,
            policy_id=ATTACHMENT_EDGE_FILTER_POLICY_ID,
            task_type="competitive_attachment_edge_filter_experiment",
        ),
        ledger,
    )
    first_event, first_trigger = event_fixture("stated", 1)
    second_event, second_trigger = event_fixture("running", 2)
    parent = candidate_fixture(first_event.id, first_trigger.id, 0, len("Sacks"), 1)
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE_TEXT,
        event_inputs=((first_event, first_trigger), (second_event, second_trigger)),
        candidates_by_event={first_event.id: (parent,), second_event.id: ()},
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
        origins=(AttachmentProposalOrigin.QWEN,),
        syntax_arms=(),
    )
    task = build_attachment_edge_filter_task(
        source_text=SOURCE_TEXT,
        edge=edge,
        candidate=candidate,
        event_options=matrix.event_options,
    )
    result = run_attachment_edge_filter(
        AttachmentEdgeFilterCommand(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            task=task,
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture", 4_096, 32, 32),
            generation_parameters=(
                ExecutionSetting("max_output_tokens", 32),
                ExecutionSetting("temperature", 0),
            ),
            prompt_bytes=b"Return Y, N, or U.\n",
        ),
        ledger=cast(AttachmentEdgeFilterLedger, ledger),
        archive=cast(AttachmentEdgeFilterArchive, archive),
        model_runtime=runtime,
        model_run_id_factory=FixtureRunIds(),
        tokenizer=runtime,
    )
    return result, ledger, runtime, archive
