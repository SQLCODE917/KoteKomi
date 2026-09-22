from __future__ import annotations

import hashlib
from typing import cast

import pytest
from kotekomi_application import (
    ATTACHMENT_EDGE_FILTER_POLICY_ID,
    ATTACHMENT_EDGE_FILTER_RENDERER_ID,
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
    PARAGRAPH_SEGMENT_V3,
    AttachmentEdgeFilterCommand,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    ContextModelProfile,
    EventTriggerDraft,
    ExecutionSetting,
    PropositionFragmentCandidate,
    PropositionFragmentReason,
    RetrievalSelectionAnalysisUnitInput,
    SourceSegmentAnalysisUnitInput,
    attachment_pool_edge_id,
    build_attachment_edge_filter_task,
    build_competitive_attachment_matrix,
    build_source_grounded_event_draft,
    create_analysis_unit_from_retrieval_selection,
    create_analysis_unit_from_source_segment,
    paragraph_source_segments,
    proposition_fragment_candidate_id,
    run_attachment_edge_filter,
)
from kotekomi_application.competitive_attachment_edge_filter_preview import (
    AttachmentEdgeFilterArchive,
    AttachmentEdgeFilterLedger,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id

from packages.application.tests.test_source_grounded_proposition_preview import (
    SOURCE_TEXT,
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
    assert {
        item.key: item.value for item in runtime.requests[0].execution_spec.generation_parameters
    } == {"max_output_tokens": 3, "temperature": 0}
    assert set(archive.outputs) == {result.model_run_id}
    assert ledger.accepted_write_attempted is False


def test_edge_filter_preview_isolates_invalid_output_as_unresolved() -> None:
    result, ledger, _, _ = _run(b"Y because")

    assert result.decision.status is AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT
    assert result.decision.unresolved is True
    assert result.decision.retained is False
    assert result.trace.output["raw_output_text"] == "Y because"
    assert ledger.accepted_write_attempted is False


def test_exact_source_context_preserves_one_complete_multisentence_focus_node() -> None:
    source_text = SOURCE_TEXT + " Sacks repeated the claim later."

    _, _, runtime, _ = _run(
        b"Y",
        source_text=source_text,
        exact_source_context=True,
    )

    exact_input = runtime.requests[0].rendered_input.decode()
    assert exact_input.count(source_text) == 2
    assert f"[direct_prose]\n[paragraph]\n{source_text}" in exact_input
    assert f"Passage:\n{source_text}\n" in exact_input
    assert "SOURCE SEGMENT:" not in exact_input


def test_exact_source_context_rejects_derived_segment_before_model_execution() -> None:
    runtime = FixtureRuntime((b"Y",))

    with pytest.raises(ValueError, match="cannot carry a derived segment label"):
        _run(
            b"Y",
            exact_source_context=True,
            use_derived_unit=True,
            runtime=runtime,
        )

    assert runtime.requests == []


def _run(
    output: bytes,
    *,
    source_text: str = SOURCE_TEXT,
    exact_source_context: bool = False,
    use_derived_unit: bool = False,
    runtime: FixtureRuntime | None = None,
):  # type: ignore[no-untyped-def]
    ledger = FixtureLedger(source_text)
    selected_runtime = runtime or FixtureRuntime((output,))
    archive = FixtureArchive()
    paragraph = next(item for item in ledger.bundle.nodes if item.node_type == "paragraph")
    if exact_source_context and not use_derived_unit:
        unit = create_analysis_unit_from_retrieval_selection(
            RetrievalSelectionAnalysisUnitInput(
                representation_id=ledger.bundle.representation.id,
                focus_node_ids=(paragraph.id,),
                policy_id=ATTACHMENT_EDGE_FILTER_POLICY_ID,
                task_type="competitive_attachment_edge_filter_experiment",
            ),
            ledger,
        )
    else:
        segment = paragraph_source_segments(source_text, PARAGRAPH_SEGMENT_V3)[0]
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
    first_event, first_trigger = _event_fixture(source_text, "stated", 1)
    second_event, second_trigger = _event_fixture(source_text, "running", 2)
    candidate_start = source_text.index("stated") if exact_source_context else 0
    candidate_end = (
        source_text.index("strategy") + len("strategy") if exact_source_context else len("Sacks")
    )
    parent = _candidate_fixture(
        source_text,
        first_event.id,
        first_trigger.id,
        candidate_start,
        candidate_end,
        1,
    )
    matrix = build_competitive_attachment_matrix(
        source_text=source_text,
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
        source_text=source_text,
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
            task_renderer_id=(
                ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID
                if exact_source_context
                else ATTACHMENT_EDGE_FILTER_RENDERER_ID
            ),
            source_segment_policy_id=(None if exact_source_context else PARAGRAPH_SEGMENT_V3),
        ),
        ledger=cast(AttachmentEdgeFilterLedger, ledger),
        archive=cast(AttachmentEdgeFilterArchive, archive),
        model_runtime=selected_runtime,
        model_run_id_factory=FixtureRunIds(),
        tokenizer=selected_runtime,
    )
    return result, ledger, selected_runtime, archive


def _event_fixture(source_text: str, text: str, ordinal: int):  # type: ignore[no-untyped-def]
    digest = hashlib.sha256(source_text.encode()).hexdigest()
    start = source_text.index(text)
    end = start + len(text)
    trace_id = f"xst_{ordinal:024x}"
    trigger_id = event_trigger_id(
        source_segment_id="seg_proposition_preview",
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
        source_segment_id="seg_proposition_preview",
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


def _candidate_fixture(
    source_text: str,
    event_id: str,
    trigger_id: str,
    start: int,
    end: int,
    ordinal: int,
) -> PropositionFragmentCandidate:
    digest = hashlib.sha256(source_text.encode()).hexdigest()
    text = source_text[start:end]
    reasons = (PropositionFragmentReason.ENTITY_OCCURRENCE,)
    token_ids = (f"t{ordinal}",)
    record_ids = (f"record_{ordinal}",)
    candidate_id = proposition_fragment_candidate_id(
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_proposition_preview",
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
        source_segment_id="seg_proposition_preview",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
        reasons=reasons,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
