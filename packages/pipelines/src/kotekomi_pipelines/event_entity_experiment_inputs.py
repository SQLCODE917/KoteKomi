"""Load canonical front-half evidence for stage-local Event experiments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    HybridDocumentCoverageReport,
    HybridStageId,
    derive_source_copy_view,
    event_entity_linguistic_evidence_from_trace,
    hybrid_document_coverage_report_from_bytes,
    hybrid_entity_grounding_preview_from_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_reference_preview_from_bytes,
    hybrid_source_segment_id,
    load_hybrid_event_semantics_preview,
    load_hybrid_event_trigger_preview,
    paragraph_source_segments,
    select_event_entity_mentions,
)
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_domain import Document, DocumentRepresentationBundle, Source

from kotekomi_pipelines.config import PipelineConfig
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldEvent,
    EventEntityExperimentInput,
)
from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    TriggerGoldEvent,
)


@dataclass(frozen=True)
class EventEntityCanonicalInputs:
    """Pinned authoritative and derived inputs shared by bounded experiments."""

    source: Source
    document: Document
    bundle: DocumentRepresentationBundle
    inputs: tuple[EventEntityExperimentInput, ...]
    coverage: HybridDocumentCoverageReport
    coverage_payload: bytes


def load_event_entity_experiment_inputs(
    *,
    config: PipelineConfig,
    coverage_report_id: str,
    selected_gold: tuple[ConnectionGoldEvent, ...],
    trigger_gold: TriggerGoldCatalog,
) -> EventEntityCanonicalInputs:
    """Load one exact canonical inventory without rerunning ingestion or models."""
    canonical_archive = LocalArchiveStore(config.archive_path)
    coverage_payload = canonical_archive.read_hybrid_document_coverage_report(coverage_report_id)
    coverage = hybrid_document_coverage_report_from_bytes(coverage_payload)
    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(coverage.representation_id)
        if bundle is None:
            raise ValueError("Coverage report references a missing representation.")
        document = ledger.get_document(bundle.representation.document_id)
        if document is None:
            raise ValueError("Representation references a missing Document.")
        source = ledger.get_source(document.source_id)
        if source is None:
            raise ValueError("Document references a missing Source.")
        inputs = _collect_inputs(
            coverage=coverage,
            selected_gold=selected_gold,
            trigger_gold=trigger_gold,
            bundle=bundle,
            source=source,
            document=document,
            ledger=ledger,
            archive=canonical_archive,
        )
    return EventEntityCanonicalInputs(
        source=source,
        document=document,
        bundle=bundle,
        inputs=inputs,
        coverage=coverage,
        coverage_payload=coverage_payload,
    )


def match_trigger_gold_event_id(
    trigger: EventTriggerDraft,
    trigger_by_id: dict[str, tuple[str, TriggerGoldEvent]],
) -> str | None:
    """Resolve one exact Trigger Draft to one reviewed Trigger Gold Event."""
    matches: list[str] = []
    for event_id, (source_text, gold) in trigger_by_id.items():
        if _sha(source_text.encode()) != trigger.source_text_sha256:
            continue
        source_copy = derive_source_copy_view(source_text)
        occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
        head = occurrences[gold.head_occurrence_id]
        head_span = source_copy.authoritative_range(head.start, head.end)
        expressions = {
            source_copy.authoritative_range(
                occurrences[item.start_occurrence_id].start,
                occurrences[item.end_occurrence_id].end,
            )
            for item in gold.accepted_expression_ranges
        }
        if (trigger.head_start, trigger.head_end) == head_span and (
            trigger.start,
            trigger.end,
        ) in expressions:
            matches.append(event_id)
    if len(matches) > 1:
        raise ValueError("One Event trigger matches multiple Gold Events.")
    return matches[0] if matches else None


def _collect_inputs(
    *,
    coverage: HybridDocumentCoverageReport,
    selected_gold: tuple[ConnectionGoldEvent, ...],
    trigger_gold: TriggerGoldCatalog,
    bundle: DocumentRepresentationBundle,
    source: Source,
    document: Document,
    ledger: Any,
    archive: LocalArchiveStore,
) -> tuple[EventEntityExperimentInput, ...]:
    selected_by_id = {item.event_id: item for item in selected_gold}
    trigger_by_id = {
        item.event_id: (segment.source_text, item)
        for segment in trigger_gold.segments
        for item in segment.events
        if item.event_id in selected_by_id
    }
    node_by_id = {item.id: item for item in bundle.nodes}
    view_by_id = {item.id: item for item in bundle.text_views}
    found: dict[str, EventEntityExperimentInput] = {}
    for coverage_record in coverage.records:
        receipt = hybrid_paragraph_receipt_from_bytes(
            archive.read_hybrid_paragraph_receipt(coverage_record.receipt_id)
        )
        semantics_stage = next(
            (item for item in receipt.stages if item.stage_id is HybridStageId.HP6_EVENT_SEMANTICS),
            None,
        )
        if semantics_stage is None or semantics_stage.output_id is None:
            continue
        semantics_payload = archive.read_hybrid_event_semantics_preview(semantics_stage.output_id)
        if _sha(semantics_payload) != semantics_stage.output_sha256:
            raise ValueError("Paragraph receipt references changed Event evidence.")
        semantics = load_hybrid_event_semantics_preview(
            semantics_stage.output_id,
            ledger,
            archive,
        )
        triggers = load_hybrid_event_trigger_preview(semantics.parent_preview_id, archive)
        mention = hybrid_extraction_preview_from_bytes(
            archive.read_hybrid_extraction_preview(triggers.mention_preview_id)
        )
        references = hybrid_reference_preview_from_bytes(
            archive.read_hybrid_reference_preview(triggers.reference_preview_id)
        )
        grounding = hybrid_entity_grounding_preview_from_bytes(
            archive.read_hybrid_entity_grounding_preview(triggers.parent_preview_id)
        )
        paragraph = node_by_id[semantics.paragraph_node_id]
        text_view = view_by_id[paragraph.text_view_id]
        paragraph_text = text_view.text[paragraph.start_char : paragraph.end_char]
        segments = paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3)
        trigger_records = {item.id: item for item in triggers.triggers}
        for event in semantics.source_grounded_events:
            trigger = trigger_records[event.trigger_id]
            gold_id = match_trigger_gold_event_id(trigger, trigger_by_id)
            if gold_id is None:
                continue
            gold = selected_by_id[gold_id]
            matching_segments = tuple(
                item
                for item in segments
                if hybrid_source_segment_id(
                    bundle.representation.id,
                    paragraph.id,
                    item,
                )
                == event.source_segment_id
            )
            if len(matching_segments) != 1:
                raise ValueError("Event does not identify one paragraph SourceSegment.")
            segment = matching_segments[0]
            linguistic_traces = tuple(
                trace
                for trace in triggers.traces
                if trace.source_segment_id == event.source_segment_id
                and trace.stage_id == "linguistic_analysis"
            )
            if len(linguistic_traces) != 1:
                raise ValueError("Event requires one upstream linguistic-analysis trace.")
            linguistic_evidence = event_entity_linguistic_evidence_from_trace(
                linguistic_traces[0],
                source_text=segment.exact_text,
            )
            selection = select_event_entity_mentions(
                source_text=segment.exact_text,
                event=event,
                mention_preview=mention,
                reference_preview=references,
                grounding_preview=grounding,
            )
            prepared = EventEntityExperimentInput(
                phase=gold.phase,
                gold_event_id=gold.event_id,
                source_id=source.id,
                document_id=document.id,
                representation_id=bundle.representation.id,
                paragraph_node_id=paragraph.id,
                source_segment_label=segment.label,
                source_text=segment.exact_text,
                event_semantics_preview_id=semantics.id,
                event_semantics_preview_sha256=_sha(semantics_payload),
                trigger=trigger,
                event=event,
                candidate_selection=selection,
                linguistic_evidence=linguistic_evidence,
            )
            if gold_id in found and found[gold_id] != prepared:
                raise ValueError("Canonical evidence repeats one Gold Event with changed input.")
            found[gold_id] = prepared
    missing = sorted(set(selected_by_id) - set(found))
    if missing:
        raise ValueError(f"Canonical evidence is missing selected Events: {', '.join(missing)}")
    return tuple(found[key] for key in sorted(found))


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
