"""HP-4 trigger discovery over immutable HP-3, HP-2, and HP-1 evidence."""

from __future__ import annotations

import hashlib
import re
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
    SourceCopyView,
    SourceSegmentAnalysisUnitInput,
    build_context_manifest,
    create_analysis_unit_from_source_segment,
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
from kotekomi_application.hybrid_event_trigger_model_output import (
    EventTriggerLineRejection,
    EventTriggerProposal,
    event_trigger_schema_bytes,
    parse_event_trigger_output,
)
from kotekomi_application.hybrid_event_triggers import (
    HYBRID_EVENT_TRIGGER_POLICY_ID,
    EventTriggerDraft,
    HybridEventTriggerPreview,
    HybridEventTriggerStatus,
    build_hybrid_event_trigger_preview,
    canonical_hybrid_event_trigger_preview_bytes,
    event_trigger_id,
    hybrid_event_trigger_preview_from_bytes,
    hybrid_event_trigger_preview_sha256,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    HybridPreviewStatus,
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

TRIGGER_SCHEMA_ID = "hybrid_event_trigger_text_v3"
TRIGGER_RECONCILIATION_POLICY_ID = "shortest_non_overlapping_event_trigger_v1"
_STATIVE_NON_EVENT = re.compile(r"\bremain(?:s|ed)?\s+in\s+effect\b", re.IGNORECASE)
_SOURCE_OCCURRENCE = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*", re.UNICODE)


class HybridEventTriggerLedger(StagedExtractionLedger, ContextPlanningLedger, Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class HybridEventTriggerArchive(Protocol):
    def read_hybrid_event_trigger_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_entity_grounding_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes: ...

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object: ...

    def put_hybrid_event_trigger_preview(
        self,
        preview: HybridEventTriggerPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...


@dataclass(frozen=True)
class HybridEventTriggerCommand:
    parent_preview_id: str
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]


@dataclass(frozen=True)
class HybridEventTriggerResult:
    preview: HybridEventTriggerPreview
    sha256: str
    archive_path: str


@dataclass(frozen=True)
class SourceOccurrence:
    """One KoteKomi-owned local choice over exact source characters."""

    occurrence_id: str
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if re.fullmatch(r"o[1-9][0-9]*", self.occurrence_id) is None:
            raise ValueError("SourceOccurrence requires one ordered local ID.")
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("SourceOccurrence range does not match its text.")


@dataclass(frozen=True)
class _SourceContext:
    bundle: DocumentRepresentationBundle
    mentions: HybridExtractionPreview
    references: HybridReferencePreview
    grounding: HybridEntityGroundingPreview
    paragraph_text: str


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


def load_hybrid_event_trigger_preview(
    preview_id: str,
    archive: HybridEventTriggerArchive,
) -> HybridEventTriggerPreview:
    """Reload one canonical HP-4 Preview and verify its complete parent chain."""
    payload = archive.read_hybrid_event_trigger_preview(preview_id)
    preview = hybrid_event_trigger_preview_from_bytes(payload)
    if preview.id != preview_id or canonical_hybrid_event_trigger_preview_bytes(preview) != payload:
        raise ValueError("HP-4 Preview identity or canonical encoding is invalid.")
    grounding_payload = archive.read_hybrid_entity_grounding_preview(preview.parent_preview_id)
    grounding = hybrid_entity_grounding_preview_from_bytes(grounding_payload)
    if (
        grounding.id != preview.parent_preview_id
        or canonical_hybrid_entity_grounding_preview_bytes(grounding) != grounding_payload
        or hashlib.sha256(grounding_payload).hexdigest() != preview.parent_preview_sha256
    ):
        raise ValueError("HP-4 HP-3 parent evidence does not match its pinned digest.")
    reference_payload = archive.read_hybrid_reference_preview(preview.reference_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    if (
        references.id != preview.reference_preview_id
        or references.id != grounding.parent_preview_id
        or canonical_hybrid_reference_preview_bytes(references) != reference_payload
        or hashlib.sha256(reference_payload).hexdigest() != preview.reference_preview_sha256
        or grounding.parent_preview_sha256 != preview.reference_preview_sha256
    ):
        raise ValueError("HP-4 HP-2 parent evidence does not match its pinned lineage.")
    mention_payload = archive.read_hybrid_extraction_preview(preview.mention_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
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


def run_hybrid_event_trigger_preview(
    *,
    command: HybridEventTriggerCommand,
    ledger: HybridEventTriggerLedger,
    archive: HybridEventTriggerArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    trigger_prompt_bytes: bytes,
) -> HybridEventTriggerResult:
    """Detect source triggers and publish one immutable HP-4 Preview."""
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
    source_copy_by_label = {
        item.label: derive_source_copy_view(item.exact_text) for item in segments
    }
    segment_order_by_id = {
        segment_ids[item.label]: ordinal for ordinal, item in enumerate(segments)
    }
    registry: TaskSchemaRegistry = _TriggerSchemaRegistry()
    schema = registry.resolve(TRIGGER_SCHEMA_ID)
    document = ledger.get_document(context.bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-4 representation references a missing Document.")
    source = ledger.get_source(document.source_id)
    if source is None:
        raise ValueError("HP-4 Document references a missing Source.")

    task_ids: list[str] = []
    run_ids: list[str] = []
    manifest_ids: list[str] = []
    traces: list[ExtractionStageTrace] = []
    diagnostics: list[str] = []
    triggers: list[EventTriggerDraft] = []
    task_successes = 0
    for segment in segments:
        unit = create_analysis_unit_from_source_segment(
            SourceSegmentAnalysisUnitInput(
                representation_id=context.mentions.representation_id,
                paragraph_node_id=context.mentions.paragraph_node_id,
                source_segment_label=segment.label,
                policy_id=HYBRID_EVENT_TRIGGER_POLICY_ID,
                task_type="hybrid_event_trigger_preview",
            ),
            ledger,
        )
        manifest = _build_manifest(
            unit=unit,
            profile=command.model_profile,
            prompt_bytes=trigger_prompt_bytes,
            schema=schema,
            ledger=ledger,
            tokenizer=tokenizer,
        )
        manifest_ids.append(manifest.id)
        segment_id = segment_ids[segment.label]
        source_copy = source_copy_by_label[segment.label]
        occurrences = source_occurrences(source_copy)
        occurrence_by_id = {item.occurrence_id: item for item in occurrences}
        task_input = _trigger_task_input(segment.label, occurrences)
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=source.id,
                document_id=document.id,
                representation_id=context.mentions.representation_id,
                context_manifest_id=manifest.id,
                prompt_bytes=trigger_prompt_bytes,
                execution_spec=_execution_spec(
                    manifest,
                    model_runtime,
                    command.generation_parameters,
                    schema,
                    task_input,
                ),
                validator_version="hybrid_event_trigger_validator_v3",
                task_type="hybrid_event_trigger_detection",
                task_local_input=task_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        task_ids.append(outcome.extraction_task.id)
        run_ids.append(outcome.model_run.id)
        batch = outcome.event_trigger_proposals
        succeeded = outcome.model_run.status in {
            ModelRunStatus.SUCCEEDED,
            ModelRunStatus.ABSTAINED,
        }
        output_payload: dict[str, JsonValue] = {
            "model_run_id": outcome.model_run.id,
            "model_run_status": outcome.model_run.status.value,
            "raw_output_sha256": outcome.model_run.output_digest,
            "proposals": [],
            "line_rejections": [],
        }
        if batch is not None:
            output_payload["proposals"] = [_proposal_payload(item) for item in batch.proposals]
            output_payload["line_rejections"] = [
                _line_rejection_payload(item) for item in batch.rejections
            ]
        detection_trace = build_extraction_stage_trace(
            trace_run_id=f"event_trigger:{context.grounding.id}:{segment_id}",
            ordinal=0,
            stage_id="event_trigger_detection",
            stage_version=TRIGGER_SCHEMA_ID,
            producer_id="qwen2.5",
            source_segment_id=segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            input_record_ids=(context.grounding.id,),
            execution_record_ids=(outcome.extraction_task.id, outcome.model_run.id),
            configuration={
                "prompt_sha256": hashlib.sha256(trigger_prompt_bytes).hexdigest(),
                "schema_sha256": schema.digest,
            },
            input_payload={
                "rendered_task": task_input.decode(),
                "source_segment_label": segment.label,
                "source_text": segment.exact_text,
                "source_copy_text": source_copy.text,
                "source_occurrences": [_occurrence_payload(item) for item in occurrences],
            },
            output_payload=output_payload,
            status=ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED,
            diagnostics=() if succeeded else ("trigger_output_unavailable",),
        )
        traces.append(detection_trace)
        if not succeeded:
            diagnostics.append(f"trigger_task_failed:{segment_id}:{outcome.model_run.status.value}")
            continue
        selected: tuple[EventTriggerProposal, ...] = ()
        mapped: list[EventTriggerDraft] = []
        mapping_rejections: list[EventTriggerLineRejection] = []
        valid_proposals: list[EventTriggerProposal] = []
        if batch is not None:
            for proposal in batch.proposals:
                if proposal.occurrence_id not in occurrence_by_id:
                    mapping_rejections.append(
                        EventTriggerLineRejection(
                            proposal.line_number,
                            _proposal_line(proposal),
                            "unknown_occurrence_id",
                        )
                    )
                    continue
                valid_proposals.append(proposal)
            selected = select_non_overlapping_trigger_proposals(
                tuple(valid_proposals),
                occurrences=occurrence_by_id,
                source_copy=source_copy,
            )
            mapped = [
                _resolve_trigger(
                    item,
                    occurrence=occurrence_by_id[item.occurrence_id],
                    segment_id=segment_id,
                    source_text=segment.exact_text,
                    source_copy=source_copy,
                    extraction_task_id=outcome.extraction_task.id,
                    model_run_id=outcome.model_run.id,
                    trace_id=detection_trace.id,
                )
                for item in selected
            ]
            all_rejections = (*batch.rejections, *mapping_rejections)
            diagnostics.extend(
                f"trigger_line_rejected:{segment_id}:{item.line_number}:{item.code}"
                for item in all_rejections
            )
        task_successes += 1
        triggers.extend(mapped)
        traces.append(
            _trigger_reconciliation_trace(
                trace_run_id=detection_trace.trace_run_id,
                source_segment_id=segment_id,
                source_text=segment.exact_text,
                occurrences=occurrences,
                raw_proposals=batch.proposals if batch is not None else (),
                selected_proposals=selected,
                line_rejections=(
                    (*batch.rejections, *mapping_rejections) if batch is not None else ()
                ),
                parent_trace_id=detection_trace.id,
            )
        )

    if context.grounding.terminal_status.value != "complete":
        diagnostics.append(f"hp3_status:{context.grounding.terminal_status.value}")
    if context.mentions.terminal_status is HybridPreviewStatus.PARTIAL:
        diagnostics.append("hp1_status:partial")
    if task_successes == 0:
        status = HybridEventTriggerStatus.BLOCKED
    elif context.mentions.terminal_status is HybridPreviewStatus.COMPLETE and not diagnostics:
        status = HybridEventTriggerStatus.COMPLETE
    else:
        status = HybridEventTriggerStatus.PARTIAL
    preview = build_hybrid_event_trigger_preview(
        parent_preview_id=context.grounding.id,
        parent_preview_sha256=digests["grounding"],
        reference_preview_id=context.references.id,
        reference_preview_sha256=digests["references"],
        mention_preview_id=context.mentions.id,
        mention_preview_sha256=digests["mentions"],
        representation_id=context.mentions.representation_id,
        paragraph_node_id=context.mentions.paragraph_node_id,
        context_manifest_ids=tuple(sorted(set(manifest_ids))),
        triggers=tuple(
            sorted(
                triggers,
                key=lambda item: (
                    segment_order_by_id[item.source_segment_id],
                    item.start,
                    item.end,
                    item.id,
                ),
            )
        ),
        extraction_task_ids=tuple(sorted(set(task_ids))),
        model_run_ids=tuple(sorted(set(run_ids))),
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
    payload = canonical_hybrid_event_trigger_preview_bytes(preview)
    digest = hybrid_event_trigger_preview_sha256(preview)
    archive.put_hybrid_event_trigger_preview(preview, payload, digest)
    return HybridEventTriggerResult(
        preview,
        digest,
        f"extraction/event-trigger-previews/{preview.id}.json",
    )


def _load_source_context(
    parent_id: str,
    ledger: HybridEventTriggerLedger,
    archive: HybridEventTriggerArchive,
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
    return (
        _SourceContext(
            bundle,
            mentions,
            references,
            grounding,
            text_view.text[node.start_char : node.end_char],
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
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    ledger: HybridEventTriggerLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=profile,
            prompt_id="hybrid_event_trigger_task_v3",
            prompt_bytes=prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="hybrid_event_trigger_context_v3",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "HP-4 ContextManifest is not ready: "
            f"{planning.manifest.blocked_reason or planning.manifest.status.value}"
        )
    verify_context_manifest(
        planning.manifest.id,
        ledger,
        tokenizer,
        prompt_bytes,
        schema.canonical_schema_bytes,
    )
    return planning.manifest


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


def source_occurrences(source_copy: SourceCopyView) -> tuple[SourceOccurrence, ...]:
    """Build an ordered model-choice catalog over exact Source copy ranges."""
    return tuple(
        SourceOccurrence(
            occurrence_id=f"o{ordinal}",
            text=match.group(),
            start=match.start(),
            end=match.end(),
        )
        for ordinal, match in enumerate(_SOURCE_OCCURRENCE.finditer(source_copy.text), start=1)
    )


def _trigger_task_input(
    segment_label: str,
    occurrences: tuple[SourceOccurrence, ...],
) -> bytes:
    lines = [
        "task: detect_event_trigger_occurrences",
        f"target_source_segment: {segment_label}",
        "source_occurrence_catalog:",
    ]
    lines.extend(f"{item.occurrence_id} | {item.text}" for item in occurrences)
    lines.append("Select every explicit event-evoking occurrence from this catalog.")
    return "\n".join(lines).encode()


def _resolve_trigger(
    proposal: EventTriggerProposal,
    *,
    occurrence: SourceOccurrence,
    segment_id: str,
    source_text: str,
    source_copy: SourceCopyView,
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
) -> EventTriggerDraft:
    start, end = source_copy.authoritative_range(occurrence.start, occurrence.end)
    text = source_text[start:end]
    if text != occurrence.text:
        raise ValueError("source_occurrence_mapping_drift")
    digest = hashlib.sha256(source_text.encode()).hexdigest()
    return EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id=segment_id,
            source_text_sha256=digest,
            start=start,
            end=end,
            text=text,
            event_type_label=proposal.event_type_label,
            extraction_task_id=extraction_task_id,
            model_run_id=model_run_id,
            trace_id=trace_id,
        ),
        source_segment_id=segment_id,
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
        event_type_label=proposal.event_type_label,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )


def select_non_overlapping_trigger_proposals(
    proposals: tuple[EventTriggerProposal, ...],
    *,
    occurrences: dict[str, SourceOccurrence],
    source_copy: SourceCopyView,
) -> tuple[EventTriggerProposal, ...]:
    """Keep the most local source trigger when model proposals overlap."""
    ranged = tuple(
        (
            occurrences[item.occurrence_id].start,
            occurrences[item.occurrence_id].end,
            item,
        )
        for item in proposals
    )
    stative_ranges = tuple(
        (item.start(), item.end()) for item in _STATIVE_NON_EVENT.finditer(source_copy.text)
    )
    selected: list[tuple[int, int, EventTriggerProposal]] = []
    for candidate in sorted(
        ranged,
        key=lambda item: (item[1] - item[0], item[0], item[1], item[2].occurrence_id),
    ):
        if any(start <= candidate[0] and candidate[1] <= end for start, end in stative_ranges):
            continue
        if any(candidate[0] < item[1] and item[0] < candidate[1] for item in selected):
            continue
        selected.append(candidate)
    return tuple(item[2] for item in sorted(selected, key=lambda item: (item[0], item[1])))


_select_non_overlapping_trigger_proposals = select_non_overlapping_trigger_proposals


def _trigger_reconciliation_trace(
    *,
    trace_run_id: str,
    source_segment_id: str,
    source_text: str,
    occurrences: tuple[SourceOccurrence, ...],
    raw_proposals: tuple[EventTriggerProposal, ...],
    selected_proposals: tuple[EventTriggerProposal, ...],
    line_rejections: tuple[EventTriggerLineRejection, ...],
    parent_trace_id: str,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=1,
        stage_id="event_trigger_reconciliation",
        stage_version=TRIGGER_RECONCILIATION_POLICY_ID,
        producer_id="kotekomi_application",
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        parent_trace_ids=(parent_trace_id,),
        configuration={"policy_id": TRIGGER_RECONCILIATION_POLICY_ID},
        input_payload={
            "source_occurrences": [_occurrence_payload(item) for item in occurrences],
            "raw_proposals": [_proposal_payload(item) for item in raw_proposals],
        },
        output_payload={
            "selected_proposals": [_proposal_payload(item) for item in selected_proposals],
            "line_rejections": [_line_rejection_payload(item) for item in line_rejections],
            "suppressed_count": len(raw_proposals) - len(selected_proposals),
        },
        status=ExtractionStageStatus.COMPLETED,
    )


def _proposal_payload(item: EventTriggerProposal) -> dict[str, JsonValue]:
    return {
        "line_number": item.line_number,
        "occurrence_id": item.occurrence_id,
        "event_type_label": item.event_type_label,
    }


def _occurrence_payload(item: SourceOccurrence) -> dict[str, JsonValue]:
    return {
        "occurrence_id": item.occurrence_id,
        "text": item.text,
        "start": item.start,
        "end": item.end,
    }


def _line_rejection_payload(item: EventTriggerLineRejection) -> dict[str, JsonValue]:
    return {
        "line_number": item.line_number,
        "line": item.line,
        "code": item.code,
    }


def _proposal_line(item: EventTriggerProposal) -> str:
    return f"event: {item.occurrence_id} | {item.event_type_label}"
