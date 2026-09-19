from __future__ import annotations

import hashlib
from typing import cast

from kotekomi_application import (
    COMPETITIVE_ATTACHMENT_POLICY_ID,
    PARAGRAPH_SEGMENT_V3,
    CompetitiveAttachmentCommand,
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentEventOrder,
    ContextModelProfile,
    EventTriggerDraft,
    ExecutionSetting,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    PropositionFragmentCandidate,
    PropositionFragmentReason,
    SourceSegmentAnalysisUnitInput,
    build_competitive_attachment_matrix,
    build_source_grounded_event_draft,
    create_analysis_unit_from_source_segment,
    model_identity_snapshot_digest,
    paragraph_source_segments,
    proposition_fragment_candidate_id,
    run_competitive_event_attachment,
)
from kotekomi_application.competitive_event_attachment_preview import (
    CompetitiveAttachmentArchive,
    CompetitiveAttachmentLedger,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id

from packages.application.tests.test_source_grounded_proposition_preview import (
    SOURCE_TEXT,
    FixtureArchive,
    FixtureLedger,
    FixtureRunIds,
    FixtureRuntime,
)


def test_preview_asks_once_per_candidate_with_all_event_options() -> None:
    result, ledger, runtime, archive = _run((b"E1,E2", b"E1", b"NONE"))

    assert len(runtime.requests) == 3
    assert all("E1:" in request.rendered_input.decode() for request in runtime.requests)
    assert all("E2:" in request.rendered_input.decode() for request in runtime.requests)
    assert all(
        next(
            item.value
            for item in request.execution_spec.generation_parameters
            if item.key == "max_output_tokens"
        )
        == 7
        for request in runtime.requests
    )
    assert result.matrix.decisions[0].model_event_ids == tuple(
        sorted(item.source_grounded_event_id for item in result.matrix.event_options)
    )
    assert all(item.input["exact_model_input"] for item in result.traces)
    assert set(archive.outputs) == set(result.model_run_ids)
    assert ledger.accepted_write_attempted is False


def test_invalid_output_leaves_only_one_candidate_unresolved() -> None:
    result, ledger, runtime, _ = _run((b"E1 because", b"E1", b"E2"))

    assert len(runtime.requests) == 3
    assert result.matrix.decisions[0].status is CompetitiveAttachmentDecisionStatus.INVALID_OUTPUT
    assert all(
        item.status is CompetitiveAttachmentDecisionStatus.COMPLETE
        for item in result.matrix.decisions[1:]
    )
    assert len(result.diagnostics) == 1
    assert result.traces[0].output["raw_output_text"] == "E1 because"
    assert ledger.accepted_write_attempted is False


def test_preview_maps_reversed_task_labels_to_canonical_event_occurrences() -> None:
    result, ledger, runtime, _ = _run(
        (b"E1", b"E1", b"E1"),
        event_order=CompetitiveAttachmentEventOrder.REVERSED,
    )

    canonical_second_event = result.matrix.event_options[1].source_grounded_event_id
    assert result.matrix.decisions[0].model_event_ids == (canonical_second_event,)
    assert "E1:\n<source>" in runtime.requests[0].rendered_input.decode()
    assert "<event>running</event>" in runtime.requests[0].rendered_input.decode()
    assert ledger.accepted_write_attempted is False


def test_complete_formatted_input_blocks_without_invoking_runtime() -> None:
    runtime = BlockingRuntime(())
    result, ledger, runtime, _ = _run((), runtime=runtime)

    assert runtime.requests == []
    assert all(
        item.status is CompetitiveAttachmentDecisionStatus.CONTEXT_BUDGET_BLOCKED
        for item in result.matrix.decisions
    )
    assert all(item.output["raw_output_text"] is None for item in result.traces)
    assert ledger.accepted_write_attempted is False


class BlockingRuntime(FixtureRuntime):
    def inspect_model_input(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        return ModelInputMeasurement(
            model_identity_digest=model_identity_snapshot_digest(request.model_identity),
            runtime_identity=self.configured_identity.runtime,
            model_instance_id=self.configured_identity.name,
            tokenizer_id=self.tokenizer_id,
            prompt_template_identity="fixture_no_template_v1",
            logical_input_digest=request.logical_input_digest,
            formatted_input_digest=request.logical_input_digest,
            formatted_input_token_count=self.count_tokens(request.logical_input),
            loaded_context_limit=1,
        )


def _run(
    outputs: tuple[bytes, ...],
    *,
    runtime: FixtureRuntime | None = None,
    event_order: CompetitiveAttachmentEventOrder = CompetitiveAttachmentEventOrder.SOURCE,
):  # type: ignore[no-untyped-def]
    ledger = FixtureLedger()
    selected_runtime = runtime or FixtureRuntime(outputs)
    archive = FixtureArchive()
    paragraph = next(item for item in ledger.bundle.nodes if item.node_type == "paragraph")
    segment = paragraph_source_segments(SOURCE_TEXT, PARAGRAPH_SEGMENT_V3)[0]
    unit = create_analysis_unit_from_source_segment(
        SourceSegmentAnalysisUnitInput(
            representation_id=ledger.bundle.representation.id,
            paragraph_node_id=paragraph.id,
            source_segment_label=segment.label,
            policy_id=COMPETITIVE_ATTACHMENT_POLICY_ID,
            task_type="competitive_event_attachment_experiment",
        ),
        ledger,
    )
    first_event, first_trigger = event_fixture("stated", 1)
    second_event, second_trigger = event_fixture("running", 2)
    first_candidates = (
        candidate_fixture(first_event.id, first_trigger.id, 0, len("Sacks"), 1),
        candidate_fixture(
            first_event.id,
            first_trigger.id,
            first_trigger.start,
            first_trigger.end,
            2,
            PropositionFragmentReason.EVENT_EXPRESSION,
        ),
    )
    second_candidates = (
        candidate_fixture(second_event.id, second_trigger.id, 0, len("Sacks"), 3),
        candidate_fixture(
            second_event.id,
            second_trigger.id,
            second_trigger.start,
            second_trigger.end,
            4,
            PropositionFragmentReason.EVENT_EXPRESSION,
        ),
    )
    matrix = build_competitive_attachment_matrix(
        source_text=SOURCE_TEXT,
        event_inputs=((first_event, first_trigger), (second_event, second_trigger)),
        candidates_by_event={
            first_event.id: first_candidates,
            second_event.id: second_candidates,
        },
    )
    result = run_competitive_event_attachment(
        CompetitiveAttachmentCommand(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            source_text=SOURCE_TEXT,
            matrix=matrix,
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture", 4_096, 32, 32),
            generation_parameters=(
                ExecutionSetting("max_output_tokens", 32),
                ExecutionSetting("temperature", 0),
            ),
            prompt_bytes=b"Return only Event labels, NONE, or UNCLEAR.\n",
            event_order=event_order,
        ),
        ledger=cast(CompetitiveAttachmentLedger, ledger),
        archive=cast(CompetitiveAttachmentArchive, archive),
        model_runtime=selected_runtime,
        model_run_id_factory=FixtureRunIds(),
        tokenizer=selected_runtime,
    )
    return result, ledger, selected_runtime, archive


def event_fixture(text: str, ordinal: int):  # type: ignore[no-untyped-def]
    digest = hashlib.sha256(SOURCE_TEXT.encode()).hexdigest()
    start = SOURCE_TEXT.index(text)
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


def candidate_fixture(
    event_id: str,
    trigger_id: str,
    start: int,
    end: int,
    ordinal: int,
    reason: PropositionFragmentReason = PropositionFragmentReason.ENTITY_OCCURRENCE,
) -> PropositionFragmentCandidate:
    digest = hashlib.sha256(SOURCE_TEXT.encode()).hexdigest()
    text = SOURCE_TEXT[start:end]
    reasons = (reason,)
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
