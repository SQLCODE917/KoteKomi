"""Ingestion composition pass (R20).

After a normal ingestion finalizes, this pass derives every applicable Event's
dependencies and persists one composition outcome per Event. It runs from the
ingestion worker, never from a test-only shortcut.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionRecord,
    EventCompositionStatus,
    EventEntityLinguisticToken,
    IngestionTokenArtifact,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticAnalyzer,
)
from kotekomi_application.ingestion_inspection import ParagraphInput, build_profile

from kotekomi_pipelines.ingestion_composition_stage import compose_paragraph_events
from kotekomi_pipelines.ingestion_token_artifact import LocalTokenArtifactWriter
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs


def analyzer_identity(analysis: LinguisticAnalysis) -> str:
    """Return the analyzer's actual identity for the token artifact binding."""
    return (
        f"{analysis.producer_id}:{analysis.model_id}:"
        f"{analysis.model_version}:{analysis.resource_identity}"
    )


def event_entity_tokens(
    analysis: LinguisticAnalysis,
) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(
        EventEntityLinguisticToken(
            token_id=token.token_id,
            sentence_id=token.sentence_id,
            text=token.text,
            start=token.start,
            end=token.end,
            lemma=token.lemma,
            part_of_speech=token.part_of_speech.value,
            dependency_relation=token.dependency_relation,
            head_token_id=token.head_token_id,
        )
        for token in analysis.tokens
    )


def compose_ingested_run(
    *,
    ledger_path: Path,
    archive_path: Path,
    analyzer: LinguisticAnalyzer,
    ingestion_run_id: str,
) -> tuple[EventCompositionRecord, ...]:
    """Analyze every paragraph with an Event and persist each composition.

    The pass is bound to the IngestionRun that the worker was assigned, so a
    concurrent ingestion cannot make it compose another run's source. A paragraph
    without a realized Event yields no record. A paragraph with an Event yields a
    composed record or a typed hold; none is skipped.
    """
    paragraphs = load_paragraph_inputs(ledger_path, archive_path, ingestion_run_id=ingestion_run_id)
    store = CompositionOutcomeStore(ledger_path.parent / "composition-outcomes")
    token_root = ledger_path.parent / "token-artifacts"
    records: list[EventCompositionRecord] = []
    with sqlite_ledger_transaction(ledger_path) as repository:
        for paragraph in paragraphs:
            profile = build_profile(
                text=paragraph.text,
                representation_id=paragraph.representation_id,
                paragraph_node_id=paragraph.paragraph_node_id,
                node_start_char=paragraph.node_start_char,
                stage_outputs=paragraph.stage_outputs,
                bundle=paragraph.bundle,
            )
            if not profile.events:
                continue
            events = tuple(
                (event.event_id, event.trigger_span.start, event.trigger_span.end)
                for event in profile.events
            )
            try:
                analysis = analyzer.analyze(LinguisticAnalysisInput(paragraph.text))
            except (ValueError, RuntimeError):
                # A recoverable analyzer failure stays visible as a typed hold.
                records.extend(
                    _paragraph_holds(
                        paragraph=paragraph,
                        events=events,
                        store=store,
                        hold_reason="inventory_unavailable",
                    )
                )
                continue
            # An invalid deterministic binding is a defect, not a recoverable hold.
            artifact = IngestionTokenArtifact(
                representation_id=paragraph.representation_id,
                text_view_id=profile.text_view_id or "",
                paragraph_node_id=paragraph.paragraph_node_id,
                node_start_char=paragraph.node_start_char,
                node_end_char=paragraph.node_start_char + len(paragraph.text),
                source_text_sha256=hashlib.sha256(paragraph.text.encode()).hexdigest(),
                analyzer_identity=analyzer_identity(analysis),
                tokens=event_entity_tokens(analysis),
            )
            try:
                LocalTokenArtifactWriter(token_root).write(artifact)
            except OSError:
                # Persistence failure stays durable before it reaches the error stream.
                records.extend(
                    _paragraph_holds(
                        paragraph=paragraph,
                        events=events,
                        store=store,
                        hold_reason="artifact_persistence_failed",
                    )
                )
                raise
            records.extend(
                compose_paragraph_events(
                    repository=repository,
                    source_text=paragraph.text,
                    tokens=artifact.tokens,
                    events=events,
                    assertion_inputs_by_event={},
                    representation_id=paragraph.representation_id,
                    text_view_id=artifact.text_view_id,
                    store=store,
                    node_start_char=paragraph.node_start_char,
                )
            )
    return tuple(records)


def _paragraph_holds(
    *,
    paragraph: ParagraphInput,
    events: tuple[tuple[str, int, int], ...],
    store: CompositionOutcomeStore,
    hold_reason: str,
) -> tuple[EventCompositionRecord, ...]:
    """Persist one typed hold per Event when the paragraph cannot be composed."""
    source_text_sha256 = hashlib.sha256(paragraph.text.encode()).hexdigest()
    records: list[EventCompositionRecord] = []
    for event_id, _, _ in events:
        record = EventCompositionRecord(
            event_id=event_id,
            source_text_sha256=source_text_sha256,
            status=EventCompositionStatus.HELD,
            hold_reason=hold_reason,
        )
        store.save(record)
        records.append(record)
    return tuple(records)
