"""HP-4 orchestration over immutable HP-3, HP-2, and HP-1 evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from kotekomi_domain import DocumentRepresentationBundle, ModelRunStatus
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V3,
    AnalysisUnit,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ContextPlanningLedger,
    ContextTokenizer,
    RetrievalSelectionAnalysisUnitInput,
    SourceCopyView,
    build_context_manifest,
    create_analysis_unit_from_retrieval_selection,
    derive_source_copy_view,
    load_context_manifest,
    paragraph_source_segments,
    verify_context_manifest,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_entity_grounding import (
    HybridEntityGroundingPreview,
    canonical_hybrid_entity_grounding_preview_bytes,
    hybrid_entity_grounding_preview_from_bytes,
)
from kotekomi_application.hybrid_event_frames import (
    EventArgumentDraft,
    EventArgumentReferenceStatus,
    EventFrameDraft,
    EventQualifierDraft,
    EventQualifierKind,
    EventTriggerDraft,
    HybridEventFramePreview,
    HybridEventFrameStatus,
    build_hybrid_event_frame_preview,
    canonical_hybrid_event_frame_preview_bytes,
    event_frame_id,
    event_trigger_id,
    hybrid_event_frame_preview_from_bytes,
    hybrid_event_frame_preview_sha256,
)
from kotekomi_application.hybrid_event_model_output import (
    EventFrameProposal,
    EventTriggerProposal,
    EventTriggerProposalBatch,
    event_frame_schema_bytes,
    event_trigger_schema_bytes,
    parse_event_frame_output,
    parse_event_trigger_output,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    HybridPreviewStatus,
    MentionBoundaryStatus,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    ExecutionSetting,
    ModelExecutionSpec,
    ModelRunIdFactory,
    ModelTaskRuntime,
    PinnedTaskSchema,
    StagedExtractionLedger,
    TaskSchemaRegistry,
    run_bounded_extraction,
)

TRIGGER_SCHEMA_ID = "hybrid_event_trigger_text_v1"
FRAME_SCHEMA_ID = "hybrid_event_frame_text_v1"


class HybridEventFrameLedger(StagedExtractionLedger, ContextPlanningLedger, Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class HybridEventFrameArchive(Protocol):
    def read_hybrid_event_frame_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_entity_grounding_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes: ...

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object: ...

    def put_hybrid_event_frame_preview(
        self,
        preview: HybridEventFramePreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...


@dataclass(frozen=True)
class HybridEventFrameCommand:
    parent_preview_id: str
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]


@dataclass(frozen=True)
class HybridEventFrameResult:
    preview: HybridEventFramePreview
    sha256: str
    archive_path: str


@dataclass(frozen=True)
class _SourceContext:
    bundle: DocumentRepresentationBundle
    mentions: HybridExtractionPreview
    references: HybridReferencePreview
    grounding: HybridEntityGroundingPreview
    paragraph_text: str
    source_id: str
    document_id: str


class _TriggerSchemaRegistry:
    schema_id = TRIGGER_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported HP-4 trigger schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id,
            event_trigger_schema_bytes(),
            schema_id,
            parse_event_trigger_output,
        )


def load_hybrid_event_frame_preview(
    preview_id: str,
    archive: HybridEventFrameArchive,
) -> HybridEventFramePreview:
    """Reload one canonical HP-4 Preview and verify its complete parent chain."""
    payload = archive.read_hybrid_event_frame_preview(preview_id)
    preview = hybrid_event_frame_preview_from_bytes(payload)
    if preview.id != preview_id or canonical_hybrid_event_frame_preview_bytes(preview) != payload:
        raise ValueError("HP-4 Preview identity or canonical encoding is invalid.")
    grounding_payload = archive.read_hybrid_entity_grounding_preview(preview.parent_preview_id)
    try:
        grounding = hybrid_entity_grounding_preview_from_bytes(grounding_payload)
    except ValueError as error:
        raise ValueError("HP-4 HP-3 parent evidence does not match its pinned digest.") from error
    if (
        grounding.id != preview.parent_preview_id
        or canonical_hybrid_entity_grounding_preview_bytes(grounding) != grounding_payload
        or hashlib.sha256(grounding_payload).hexdigest() != preview.parent_preview_sha256
    ):
        raise ValueError("HP-4 HP-3 parent evidence does not match its pinned digest.")
    reference_payload = archive.read_hybrid_reference_preview(preview.reference_preview_id)
    try:
        references = hybrid_reference_preview_from_bytes(reference_payload)
    except ValueError as error:
        raise ValueError("HP-4 HP-2 parent evidence does not match its pinned lineage.") from error
    if (
        references.id != preview.reference_preview_id
        or references.id != grounding.parent_preview_id
        or canonical_hybrid_reference_preview_bytes(references) != reference_payload
        or hashlib.sha256(reference_payload).hexdigest() != preview.reference_preview_sha256
        or grounding.parent_preview_sha256 != preview.reference_preview_sha256
    ):
        raise ValueError("HP-4 HP-2 parent evidence does not match its pinned lineage.")
    mention_payload = archive.read_hybrid_extraction_preview(preview.mention_preview_id)
    try:
        mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    except ValueError as error:
        raise ValueError("HP-4 HP-1 parent evidence does not match its pinned lineage.") from error
    if (
        mentions.id != preview.mention_preview_id
        or mentions.id != references.parent_preview_id
        or mentions.id != grounding.mention_preview_id
        or canonical_hybrid_extraction_preview_bytes(mentions) != mention_payload
        or hashlib.sha256(mention_payload).hexdigest() != preview.mention_preview_sha256
        or grounding.mention_preview_sha256 != preview.mention_preview_sha256
    ):
        raise ValueError("HP-4 HP-1 parent evidence does not match its pinned lineage.")
    if (
        len(
            {
                preview.representation_id,
                grounding.representation_id,
                references.representation_id,
                mentions.representation_id,
            }
        )
        != 1
    ):
        raise ValueError("HP-4 representation lineage is inconsistent.")
    return preview


class _FrameSchemaRegistry:
    schema_id = FRAME_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported HP-4 frame schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id,
            event_frame_schema_bytes(),
            schema_id,
            parse_event_frame_output,
        )


def run_hybrid_event_frame_preview(
    *,
    command: HybridEventFrameCommand,
    ledger: HybridEventFrameLedger,
    archive: HybridEventFrameArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    trigger_prompt_bytes: bytes,
    frame_prompt_bytes: bytes,
) -> HybridEventFrameResult:
    """Detect source triggers, assign frames, and publish one immutable HP-4 Preview."""
    context, digests = _load_source_context(command.parent_preview_id, ledger, archive)
    segments = paragraph_source_segments(context.paragraph_text, PARAGRAPH_SEGMENT_V3)
    segment_ids = {
        item.label: hybrid_source_segment_id(
            context.mentions.representation_id,
            context.mentions.paragraph_node_id,
            item,
        )
        for item in segments
    }
    source_by_label = {item.label: item.exact_text for item in segments}
    source_copy_by_label = {
        item.label: derive_source_copy_view(item.exact_text) for item in segments
    }
    segment_order_by_id = {
        segment_ids[item.label]: ordinal for ordinal, item in enumerate(segments)
    }
    trigger_registry: TaskSchemaRegistry = _TriggerSchemaRegistry()
    frame_registry: TaskSchemaRegistry = _FrameSchemaRegistry()
    trigger_schema = trigger_registry.resolve(TRIGGER_SCHEMA_ID)
    frame_schema = frame_registry.resolve(FRAME_SCHEMA_ID)
    unit = create_analysis_unit_from_retrieval_selection(
        RetrievalSelectionAnalysisUnitInput(
            representation_id=context.mentions.representation_id,
            focus_node_ids=(context.mentions.paragraph_node_id,),
            policy_id="hybrid_event_frame_v1",
            task_type="hybrid_event_frame_preview",
        ),
        ledger,
    )
    trigger_manifest = _build_manifest(
        unit=unit,
        profile=command.model_profile,
        prompt_id="hybrid_event_trigger_task_v1",
        prompt_bytes=trigger_prompt_bytes,
        schema=trigger_schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )
    frame_manifest = _build_manifest(
        unit=unit,
        profile=command.model_profile,
        prompt_id="hybrid_event_frame_task_v1",
        prompt_bytes=frame_prompt_bytes,
        schema=frame_schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )
    document = ledger.get_document(context.bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-4 representation references a missing Document.")
    source = ledger.get_source(document.source_id)
    if source is None:
        raise ValueError("HP-4 Document references a missing Source.")

    extraction_task_ids: list[str] = []
    model_run_ids: list[str] = []
    traces: list[ExtractionStageTrace] = []
    diagnostics: list[str] = []
    triggers: list[EventTriggerDraft] = []
    trigger_local_labels: dict[str, str] = {}
    trigger_trace_by_segment: dict[str, ExtractionStageTrace] = {}
    trigger_task_successes = 0
    next_trace_ordinal: dict[str, int] = {}
    for segment in segments:
        source_segment_id = segment_ids[segment.label]
        source_copy = source_copy_by_label[segment.label]
        task_input = _trigger_task_input(segment.label)
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=source.id,
                document_id=document.id,
                representation_id=context.mentions.representation_id,
                context_manifest_id=trigger_manifest.id,
                prompt_bytes=trigger_prompt_bytes,
                execution_spec=_execution_spec(
                    trigger_manifest,
                    model_runtime,
                    command.generation_parameters,
                    trigger_schema,
                    task_input,
                ),
                validator_version="hybrid_event_trigger_validator_v1",
                task_type="hybrid_event_trigger_detection",
                task_local_input=task_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            trigger_registry,
        )
        extraction_task_ids.append(outcome.extraction_task.id)
        model_run_ids.append(outcome.model_run.id)
        batch = outcome.event_trigger_proposals
        model_succeeded = outcome.model_run.status in {
            ModelRunStatus.SUCCEEDED,
            ModelRunStatus.ABSTAINED,
        }
        raw_digest = outcome.model_run.output_digest
        output_payload: dict[str, JsonValue] = {
            "model_run_id": outcome.model_run.id,
            "model_run_status": outcome.model_run.status.value,
            "raw_output_sha256": raw_digest,
            "proposals": [],
        }
        if batch is not None:
            output_payload["proposals"] = [
                {
                    "event_label": item.event_label,
                    "event_type_label": item.event_type_label,
                    "source_segment_label": item.source_segment_label,
                    "trigger_text": item.trigger_text,
                }
                for item in batch.proposals
            ]
        trace_status = (
            ExtractionStageStatus.COMPLETED if model_succeeded else ExtractionStageStatus.FAILED
        )
        trace_diagnostics: tuple[str, ...] = (
            () if model_succeeded else ("trigger_output_unavailable",)
        )
        trace = build_extraction_stage_trace(
            trace_run_id=f"event_frame:{context.grounding.id}:{source_segment_id}",
            ordinal=0,
            stage_id="event_trigger_detection",
            stage_version=TRIGGER_SCHEMA_ID,
            producer_id="qwen2.5",
            source_segment_id=source_segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            input_record_ids=(context.grounding.id,),
            execution_record_ids=(outcome.extraction_task.id, outcome.model_run.id),
            configuration={
                "prompt_sha256": hashlib.sha256(trigger_prompt_bytes).hexdigest(),
                "schema_sha256": trigger_schema.digest,
            },
            input_payload={
                "rendered_task": task_input.decode(),
                "source_segment_label": segment.label,
                "source_text": segment.exact_text,
                "source_copy_text": source_copy.text,
            },
            output_payload=output_payload,
            status=trace_status,
            diagnostics=trace_diagnostics,
        )
        next_trace_ordinal[source_segment_id] = 1
        if not model_succeeded:
            diagnostics.append(
                f"trigger_task_failed:{source_segment_id}:{outcome.model_run.status.value}"
            )
            traces.append(trace)
            trigger_trace_by_segment[source_segment_id] = trace
            continue
        mapped_triggers: list[EventTriggerDraft] = []
        mapping_error: ValueError | None = None
        if batch is not None:
            try:
                _validate_trigger_batch(
                    batch,
                    expected_segment_label=segment.label,
                    source_copy=source_copy,
                )
                mapped_triggers = [
                    _resolve_trigger(
                        proposal,
                        expected_segment_label=segment.label,
                        segment_id=source_segment_id,
                        source_text=segment.exact_text,
                        source_copy=source_copy,
                        extraction_task_id=outcome.extraction_task.id,
                        model_run_id=outcome.model_run.id,
                        trace_id=trace.id,
                    )
                    for proposal in batch.proposals
                ]
            except ValueError as error:
                mapping_error = error
        if mapping_error is not None:
            mapping_diagnostic = f"trigger_mapping_failed:{source_segment_id}:{mapping_error}"
            diagnostics.append(mapping_diagnostic)
            trace = build_extraction_stage_trace(
                trace_run_id=trace.trace_run_id,
                ordinal=trace.ordinal,
                stage_id=trace.stage_id,
                stage_version=trace.stage_version,
                producer_id=trace.producer_id,
                source_segment_id=trace.source_segment_id,
                source_text_sha256=trace.source_text_sha256,
                input_record_ids=trace.input_record_ids,
                execution_record_ids=trace.execution_record_ids,
                configuration=trace.configuration,
                input_payload=trace.input,
                output_payload=trace.output,
                status=ExtractionStageStatus.REJECTED,
                diagnostics=("trigger_source_mapping_rejected",),
            )
        else:
            trigger_task_successes += 1
            triggers.extend(mapped_triggers)
            if batch is not None:
                trigger_local_labels.update(
                    {
                        trigger.id: proposal.event_label
                        for trigger, proposal in zip(mapped_triggers, batch.proposals, strict=True)
                    }
                )
        traces.append(trace)
        trigger_trace_by_segment[source_segment_id] = trace

    frames: list[EventFrameDraft] = []
    for trigger in triggers:
        source_segment_id = trigger.source_segment_id
        local_event_label = trigger_local_labels[trigger.id]
        task_input, candidate_labels = _frame_task_input(
            trigger,
            local_event_label,
            context.mentions,
            context.references,
            segment_ids,
        )
        candidate_catalog = _candidate_catalog(
            context.mentions,
            context.references,
            candidate_labels,
        )
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=source.id,
                document_id=document.id,
                representation_id=context.mentions.representation_id,
                context_manifest_id=frame_manifest.id,
                prompt_bytes=frame_prompt_bytes,
                execution_spec=_execution_spec(
                    frame_manifest,
                    model_runtime,
                    command.generation_parameters,
                    frame_schema,
                    task_input,
                ),
                validator_version="hybrid_event_frame_validator_v1",
                task_type="hybrid_event_frame_assignment",
                input_candidate_ids=tuple(sorted(candidate_labels.values())),
                task_local_input=task_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            frame_registry,
        )
        extraction_task_ids.append(outcome.extraction_task.id)
        model_run_ids.append(outcome.model_run.id)
        proposal = outcome.event_frame_proposal
        successful = outcome.model_run.status is ModelRunStatus.SUCCEEDED and proposal is not None
        abstained = outcome.model_run.status is ModelRunStatus.ABSTAINED
        if abstained:
            diagnostics.append(f"frame_task_abstained:{trigger.id}")
        elif not successful:
            diagnostics.append(f"frame_task_failed:{trigger.id}:{outcome.model_run.status.value}")
        ordinal = next_trace_ordinal[source_segment_id]
        next_trace_ordinal[source_segment_id] += 1
        output_payload = {
            "model_run_id": outcome.model_run.id,
            "model_run_status": outcome.model_run.status.value,
            "raw_output_sha256": outcome.model_run.output_digest,
            "proposal": _frame_proposal_payload(proposal),
        }
        parent_trace = trigger_trace_by_segment[source_segment_id]
        trace = build_extraction_stage_trace(
            trace_run_id=parent_trace.trace_run_id,
            ordinal=ordinal,
            stage_id="event_frame_assignment",
            stage_version=FRAME_SCHEMA_ID,
            producer_id="qwen2.5",
            source_segment_id=source_segment_id,
            source_text_sha256=trigger.source_text_sha256,
            parent_trace_ids=(parent_trace.id,),
            input_record_ids=tuple(
                sorted((context.grounding.id, trigger.id, *candidate_labels.values()))
            ),
            execution_record_ids=(outcome.extraction_task.id, outcome.model_run.id),
            configuration={
                "prompt_sha256": hashlib.sha256(frame_prompt_bytes).hexdigest(),
                "schema_sha256": frame_schema.digest,
            },
            input_payload={
                "candidate_catalog": candidate_catalog,
                "rendered_task": task_input.decode(),
                "trigger_id": trigger.id,
            },
            output_payload=output_payload,
            status=(
                ExtractionStageStatus.COMPLETED
                if successful
                else (
                    ExtractionStageStatus.NOT_APPLICABLE
                    if abstained
                    else ExtractionStageStatus.FAILED
                )
            ),
            diagnostics=(
                ()
                if successful
                else (("frame_task_abstained",) if abstained else ("frame_output_unavailable",))
            ),
        )
        if proposal is None:
            traces.append(trace)
            continue
        try:
            frame = _resolve_frame(
                proposal,
                expected_event_label=local_event_label,
                trigger=trigger,
                candidate_labels=candidate_labels,
                mentions=context.mentions,
                references=context.references,
                segment_ids=segment_ids,
                source_by_label=source_by_label,
                source_copy_by_label=source_copy_by_label,
                extraction_task_id=outcome.extraction_task.id,
                model_run_id=outcome.model_run.id,
                trace_id=trace.id,
            )
        except ValueError as error:
            diagnostics.append(f"frame_mapping_failed:{trigger.id}:{error}")
            trace = build_extraction_stage_trace(
                trace_run_id=trace.trace_run_id,
                ordinal=trace.ordinal,
                stage_id=trace.stage_id,
                stage_version=trace.stage_version,
                producer_id=trace.producer_id,
                source_segment_id=trace.source_segment_id,
                source_text_sha256=trace.source_text_sha256,
                parent_trace_ids=trace.parent_trace_ids,
                input_record_ids=trace.input_record_ids,
                execution_record_ids=trace.execution_record_ids,
                configuration=trace.configuration,
                input_payload=trace.input,
                output_payload=trace.output,
                status=ExtractionStageStatus.REJECTED,
                diagnostics=("frame_source_mapping_rejected",),
            )
            traces.append(trace)
            continue
        traces.append(trace)
        frames.append(frame)

    if trigger_task_successes == 0:
        status = HybridEventFrameStatus.BLOCKED
    elif (
        context.mentions.terminal_status is HybridPreviewStatus.COMPLETE
        and not diagnostics
        and len(frames) == len(triggers)
    ):
        status = HybridEventFrameStatus.COMPLETE
    else:
        status = HybridEventFrameStatus.PARTIAL
    if context.grounding.terminal_status.value != "complete":
        diagnostics.append(f"hp3_status:{context.grounding.terminal_status.value}")
    if context.mentions.terminal_status is HybridPreviewStatus.PARTIAL:
        diagnostics.append("hp1_status:partial")
    preview = build_hybrid_event_frame_preview(
        parent_preview_id=context.grounding.id,
        parent_preview_sha256=digests["grounding"],
        reference_preview_id=context.references.id,
        reference_preview_sha256=digests["references"],
        mention_preview_id=context.mentions.id,
        mention_preview_sha256=digests["mentions"],
        representation_id=context.mentions.representation_id,
        paragraph_node_id=context.mentions.paragraph_node_id,
        trigger_context_manifest_id=trigger_manifest.id,
        frame_context_manifest_id=frame_manifest.id,
        triggers=tuple(triggers),
        frames=tuple(frames),
        extraction_task_ids=tuple(sorted(set(extraction_task_ids))),
        model_run_ids=tuple(sorted(set(model_run_ids))),
        traces=tuple(
            sorted(
                traces,
                key=lambda item: (
                    segment_order_by_id[item.source_segment_id],
                    item.ordinal,
                    item.id,
                ),
            )
        ),
        terminal_status=status,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    payload = canonical_hybrid_event_frame_preview_bytes(preview)
    digest = hybrid_event_frame_preview_sha256(preview)
    archive.put_hybrid_event_frame_preview(preview, payload, digest)
    return HybridEventFrameResult(
        preview,
        digest,
        f"extraction/event-frame-previews/{preview.id}.json",
    )


def _load_source_context(
    parent_id: str,
    ledger: HybridEventFrameLedger,
    archive: HybridEventFrameArchive,
) -> tuple[_SourceContext, dict[str, str]]:
    grounding_payload = archive.read_hybrid_entity_grounding_preview(parent_id)
    grounding = hybrid_entity_grounding_preview_from_bytes(grounding_payload)
    if (
        grounding.id != parent_id
        or canonical_hybrid_entity_grounding_preview_bytes(grounding) != grounding_payload
    ):
        raise ValueError("HP-4 parent HP-3 Preview identity or encoding is invalid.")
    reference_payload = archive.read_hybrid_reference_preview(grounding.parent_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    reference_digest = hashlib.sha256(reference_payload).hexdigest()
    if (
        references.id != grounding.parent_preview_id
        or reference_digest != grounding.parent_preview_sha256
    ):
        raise ValueError("HP-4 HP-2 parent digest does not match HP-3 lineage.")
    mention_payload = archive.read_hybrid_extraction_preview(references.parent_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    mention_digest = hashlib.sha256(mention_payload).hexdigest()
    if (
        mentions.id != references.parent_preview_id
        or mentions.id != grounding.mention_preview_id
        or mention_digest != references.parent_preview_sha256
        or mention_digest != grounding.mention_preview_sha256
    ):
        raise ValueError("HP-4 HP-1 parent digest does not match parent lineage.")
    if (
        len(
            {
                grounding.representation_id,
                references.representation_id,
                mentions.representation_id,
            }
        )
        != 1
    ):
        raise ValueError("HP-4 parent representation lineage is inconsistent.")
    if mentions.terminal_status is HybridPreviewStatus.BLOCKED:
        raise ValueError("HP-4 cannot consume a blocked HP-1 Preview.")
    bundle = ledger.get_document_representation_bundle(mentions.representation_id)
    if bundle is None:
        raise ValueError("HP-4 parent references a missing representation.")
    manifest = load_context_manifest(mentions.context_manifest_id, ledger, verified_bundle=bundle)
    if manifest.representation_id != mentions.representation_id:
        raise ValueError("HP-4 HP-1 ContextManifest lineage drifted.")
    node = next((item for item in bundle.nodes if item.id == mentions.paragraph_node_id), None)
    if node is None or node.node_type != "paragraph":
        raise ValueError("HP-4 parent paragraph is missing or invalid.")
    text_view = next((item for item in bundle.text_views if item.id == node.text_view_id), None)
    if text_view is None:
        raise ValueError("HP-4 paragraph TextView is missing.")
    paragraph_text = text_view.text[node.start_char : node.end_char]
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-4 representation Document is missing.")
    return (
        _SourceContext(
            bundle,
            mentions,
            references,
            grounding,
            paragraph_text,
            document.source_id,
            document.id,
        ),
        {
            "grounding": hashlib.sha256(grounding_payload).hexdigest(),
            "references": reference_digest,
            "mentions": mention_digest,
        },
    )


def _build_manifest(
    *,
    unit: AnalysisUnit,
    profile: ContextModelProfile,
    prompt_id: str,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    ledger: HybridEventFrameLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=profile,
            prompt_id=prompt_id,
            prompt_bytes=prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="hybrid_event_context_v1",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    manifest = planning.manifest
    if manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            f"HP-4 ContextManifest is not ready: {manifest.blocked_reason or manifest.status.value}"
        )
    verify_context_manifest(
        manifest.id, ledger, tokenizer, prompt_bytes, schema.canonical_schema_bytes
    )
    return manifest


def _execution_spec(
    manifest: ContextManifest,
    runtime: ModelTaskRuntime,
    generation: tuple[ExecutionSetting, ...],
    schema: PinnedTaskSchema,
    task_input: bytes,
) -> ModelExecutionSpec:
    rendered = manifest.rendered_input + b"\n\n[task]\n" + task_input
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=runtime.configured_identity,
        generation_parameters=generation,
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=schema.schema_id,
        schema_digest=schema.digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=hashlib.sha256(rendered).hexdigest(),
        output_contract_version=schema.output_contract_version,
    )


def _trigger_task_input(segment_label: str) -> bytes:
    return (
        b"task: detect_event_triggers\n"
        + f"target_source_segment: {segment_label}\n".encode()
        + b"Detect every explicit event whose trigger literal occurs in the target SourceSegment."
    )


def _frame_task_input(
    trigger: EventTriggerDraft,
    local_event_label: str,
    mentions: HybridExtractionPreview,
    references: HybridReferencePreview,
    segment_ids: dict[str, str],
) -> tuple[bytes, dict[str, str]]:
    selected = {
        item
        for decision in mentions.boundary_decisions
        if decision.status is not MentionBoundaryStatus.AMBIGUOUS
        for item in decision.selected_candidate_ids
    }
    interpretation_by_candidate = {item.candidate_id: item for item in mentions.interpretations}
    candidates = [
        item
        for item in mentions.candidates
        if item.id in selected and item.id in interpretation_by_candidate
    ]
    label_by_candidate = {item.id: f"c{index}" for index, item in enumerate(candidates, start=1)}
    reference_by_candidate = {item.candidate_id: item for item in references.reference_decisions}
    antecedent_text_by_id = {
        item.expanded_span.id: item.expanded_span.text for item in references.alias_declarations
    }
    segment_label_by_id = {value: key for key, value in segment_ids.items()}
    trigger_segment_label = segment_label_by_id[trigger.source_segment_id]
    lines = [
        "task: assign_event_frame",
        f"event: {local_event_label}",
        f"trigger_source_segment: {trigger_segment_label}",
        f"trigger_text: {derive_source_copy_view(trigger.text).text}",
        f"event_type_proposal: {trigger.event_type_label}",
        f"valid_source_segments: {','.join(segment_ids)}",
        "candidate_catalog:",
    ]
    for candidate in candidates:
        interpretation = interpretation_by_candidate[candidate.id]
        reference = reference_by_candidate.get(candidate.id)
        reference_text = "not_applicable"
        antecedent_text = "none"
        if reference is not None:
            reference_text = reference.status.value
            if reference.status.value == "resolved":
                antecedent_text = ", ".join(
                    antecedent_text_by_id[item] for item in reference.antecedent_span_ids
                )
        lines.append(
            " | ".join(
                (
                    label_by_candidate[candidate.id],
                    segment_label_by_id[candidate.source_segment_id],
                    derive_source_copy_view(candidate.text).text,
                    interpretation.referentiality.value,
                    interpretation.contextual_kind.value,
                    interpretation.discourse_role.value,
                    reference_text,
                    antecedent_text,
                )
            )
        )
    return "\n".join(lines).encode(), label_by_candidate


def _resolve_trigger(
    proposal: EventTriggerProposal,
    *,
    expected_segment_label: str,
    segment_id: str,
    source_text: str,
    source_copy: SourceCopyView,
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
) -> EventTriggerDraft:
    if proposal.source_segment_label != expected_segment_label:
        raise ValueError("trigger_target_segment_mismatch")
    if source_copy.text.count(proposal.trigger_text) != 1:
        raise ValueError("trigger_literal_not_unique")
    copy_start = source_copy.text.index(proposal.trigger_text)
    copy_end = copy_start + len(proposal.trigger_text)
    start, end = source_copy.authoritative_range(copy_start, copy_end)
    authoritative_text = source_text[start:end]
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    identifier = event_trigger_id(
        source_segment_id=segment_id,
        source_text_sha256=source_digest,
        start=start,
        end=end,
        text=authoritative_text,
        event_type_label=proposal.event_type_label,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )
    return EventTriggerDraft(
        id=identifier,
        source_segment_id=segment_id,
        source_text_sha256=source_digest,
        start=start,
        end=end,
        text=authoritative_text,
        event_type_label=proposal.event_type_label,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )


def _validate_trigger_batch(
    batch: EventTriggerProposalBatch,
    *,
    expected_segment_label: str,
    source_copy: SourceCopyView,
) -> None:
    identities: set[tuple[str, str]] = set()
    for proposal in batch.proposals:
        if proposal.source_segment_label != expected_segment_label:
            raise ValueError("trigger_target_segment_mismatch")
        if source_copy.text.count(proposal.trigger_text) != 1:
            raise ValueError("trigger_literal_not_unique")
        identity = (proposal.source_segment_label, proposal.trigger_text)
        if identity in identities:
            raise ValueError("trigger_literal_repeated")
        identities.add(identity)


def _resolve_frame(
    proposal: EventFrameProposal,
    *,
    expected_event_label: str,
    trigger: EventTriggerDraft,
    candidate_labels: dict[str, str],
    mentions: HybridExtractionPreview,
    references: HybridReferencePreview,
    segment_ids: dict[str, str],
    source_by_label: dict[str, str],
    source_copy_by_label: dict[str, SourceCopyView],
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
) -> EventFrameDraft:
    if proposal.event_label != expected_event_label:
        raise ValueError("frame_event_label_mismatch")
    candidate_id_by_label = {
        label: candidate_id for candidate_id, label in candidate_labels.items()
    }
    candidate_ids = {item.id for item in mentions.candidates}
    references_by_candidate = {item.candidate_id: item for item in references.reference_decisions}
    arguments: list[EventArgumentDraft] = []
    for item in proposal.arguments:
        candidate_id = candidate_id_by_label.get(item.candidate_label)
        support_id = segment_ids.get(item.support_segment_label)
        if candidate_id is None or candidate_id not in candidate_ids:
            raise ValueError("frame_argument_candidate_unknown")
        if support_id is None:
            raise ValueError("frame_argument_support_unknown")
        decision = references_by_candidate.get(candidate_id)
        status = EventArgumentReferenceStatus.NOT_APPLICABLE
        decision_id = None
        if decision is not None:
            status = EventArgumentReferenceStatus(decision.status.value)
            decision_id = decision.id
        arguments.append(
            EventArgumentDraft(
                candidate_id=candidate_id,
                role_label=item.role_label,
                support_segment_id=support_id,
                reference_status=status,
                reference_decision_id=decision_id,
            )
        )
    qualifiers: list[EventQualifierDraft] = []
    for item in proposal.qualifiers:
        source_text = source_by_label.get(item.source_segment_label)
        source_copy = source_copy_by_label.get(item.source_segment_label)
        source_segment_id = segment_ids.get(item.source_segment_label)
        if source_text is None or source_copy is None or source_segment_id is None:
            raise ValueError("frame_qualifier_segment_unknown")
        if source_copy.text.count(item.literal_text) != 1:
            raise ValueError("frame_qualifier_literal_not_unique")
        copy_start = source_copy.text.index(item.literal_text)
        copy_end = copy_start + len(item.literal_text)
        start, end = source_copy.authoritative_range(copy_start, copy_end)
        authoritative_text = source_text[start:end]
        qualifiers.append(
            EventQualifierDraft(
                kind=EventQualifierKind(item.kind.value),
                source_segment_id=source_segment_id,
                source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
                start=start,
                end=end,
                text=authoritative_text,
            )
        )
    attribution_ids: tuple[str, ...] = ()
    if not proposal.source_narrator_attribution:
        try:
            attribution_ids = tuple(
                sorted(
                    candidate_id_by_label[item] for item in proposal.attribution_candidate_labels
                )
            )
        except KeyError as error:
            raise ValueError("frame_attribution_candidate_unknown") from error
    ordered_arguments = tuple(
        sorted(
            arguments,
            key=lambda item: (item.candidate_id, item.role_label, item.support_segment_id),
        )
    )
    ordered_qualifiers = tuple(
        sorted(qualifiers, key=lambda item: (item.source_segment_id, item.start, item.kind.value))
    )
    identifier = event_frame_id(
        trigger_id=trigger.id,
        polarity=proposal.polarity,
        modality=proposal.modality,
        source_narrator_attribution=proposal.source_narrator_attribution,
        attribution_candidate_ids=attribution_ids,
        arguments=ordered_arguments,
        qualifiers=ordered_qualifiers,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )
    return EventFrameDraft(
        id=identifier,
        trigger_id=trigger.id,
        polarity=proposal.polarity,
        modality=proposal.modality,
        source_narrator_attribution=proposal.source_narrator_attribution,
        attribution_candidate_ids=attribution_ids,
        arguments=ordered_arguments,
        qualifiers=ordered_qualifiers,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )


def _candidate_catalog(
    mentions: HybridExtractionPreview,
    references: HybridReferencePreview,
    candidate_labels: dict[str, str],
) -> list[JsonValue]:
    selected = {
        candidate_id
        for decision in mentions.boundary_decisions
        if decision.status is not MentionBoundaryStatus.AMBIGUOUS
        for candidate_id in decision.selected_candidate_ids
    }
    interpretations = {item.candidate_id: item for item in mentions.interpretations}
    reference_by_candidate = {item.candidate_id: item for item in references.reference_decisions}
    antecedent_text_by_id = {
        item.expanded_span.id: item.expanded_span.text for item in references.alias_declarations
    }
    output: list[JsonValue] = []
    for candidate in mentions.candidates:
        if candidate.id not in selected or candidate.id not in candidate_labels:
            continue
        interpretation = interpretations.get(candidate.id)
        if interpretation is None:
            continue
        reference = reference_by_candidate.get(candidate.id)
        output.append(
            {
                "candidate_id": candidate.id,
                "candidate_label": candidate_labels[candidate.id],
                "contextual_kind": interpretation.contextual_kind.value,
                "discourse_role": interpretation.discourse_role.value,
                "reference_status": reference.status.value if reference else "not_applicable",
                "referentiality": interpretation.referentiality.value,
                "model_text": derive_source_copy_view(candidate.text).text,
                "resolved_antecedent_span_ids": (
                    list(reference.antecedent_span_ids)
                    if reference is not None and reference.status.value == "resolved"
                    else []
                ),
                "resolved_antecedent_texts": (
                    [antecedent_text_by_id[item] for item in reference.antecedent_span_ids]
                    if reference is not None and reference.status.value == "resolved"
                    else []
                ),
                "source_segment_id": candidate.source_segment_id,
                "text": candidate.text,
            }
        )
    return output


def _frame_proposal_payload(proposal: EventFrameProposal | None) -> JsonValue:
    if proposal is None:
        return None
    return {
        "arguments": [
            {
                "candidate_label": item.candidate_label,
                "role_label": item.role_label,
                "support_segment_label": item.support_segment_label,
            }
            for item in proposal.arguments
        ],
        "attribution_candidate_labels": list(proposal.attribution_candidate_labels),
        "event_label": proposal.event_label,
        "modality": proposal.modality.value,
        "polarity": proposal.polarity.value,
        "qualifiers": [
            {
                "kind": item.kind.value,
                "literal_text": item.literal_text,
                "source_segment_label": item.source_segment_label,
            }
            for item in proposal.qualifiers
        ],
        "source_narrator_attribution": proposal.source_narrator_attribution,
    }
