"""UI-neutral accumulation of phase results through inspection Ports."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from threading import Event

from kotekomi_domain import DocumentRepresentationBundle

from kotekomi_application.ingestion_inspection import (
    STAGE_ORDER,
    ArtifactHandle,
    HybridParagraphProgress,
    HybridParagraphStageProgress,
    InspectionArtifactPort,
    InspectionContext,
    InspectionProgressPort,
    InspectionSourcePort,
    ParagraphInput,
    ParagraphSnapshot,
    build_profile,
)


@dataclass(frozen=True)
class _ParagraphMeta:
    text: str
    representation_id: str
    paragraph_node_id: str
    node_start_char: int
    bundle: DocumentRepresentationBundle | None = None


class InspectionSession:
    """Build validated snapshots; preserve the last valid view on presentation errors."""

    def __init__(
        self,
        source: InspectionSourcePort,
        *,
        context: InspectionContext | None = None,
        artifacts_port: InspectionArtifactPort | None = None,
        on_snapshot: InspectionProgressPort | None = None,
        select_ordinal: int | None = None,
    ) -> None:
        self._artifact_port = artifacts_port
        self._source = source
        self._context = context
        self._on_snapshot = on_snapshot
        self._select_ordinal = select_ordinal
        self._artifacts: tuple[ArtifactHandle, ...] = ()
        self._phase_states: tuple[tuple[str, str], ...] = ()
        self._phase_diagnostics: tuple[tuple[str, tuple[str, ...]], ...] = ()
        self._bundle: DocumentRepresentationBundle | None = None
        self._outputs: dict[int, dict[str, object]] = {}
        self._snapshots: dict[int, ParagraphSnapshot] = {}

    @property
    def presentation_failed(self) -> bool:
        return any(snapshot.error is not None for snapshot in self._snapshots.values())

    def on_stage_progress(self, event: HybridParagraphStageProgress) -> None:
        if self._select_ordinal is not None and event.ordinal != self._select_ordinal:
            return
        if event.finished:
            self._outputs.pop(event.ordinal, None)
            return
        meta = self._meta(event.representation_id, event.paragraph_node_id)
        if event.stage_id is None and not event.finished:
            self._artifacts = ()
            self._phase_states = ()
            self._phase_diagnostics = ()
        outputs = self._outputs.setdefault(event.ordinal, {})
        if event.stage_id is not None and event.stage_output is not None:
            outputs[event.stage_id.value] = event.stage_output
            output_id = getattr(event.stage_output, "id", None)
            if self._artifact_port is not None and isinstance(output_id, str):
                self._artifacts = tuple(
                    a for a in self._artifacts if a.stage != event.stage_id.value
                ) + (self._artifact_port.describe_stage(event.stage_id, output_id),)
        self._publish(meta, outputs, event.ordinal, event.total)

    def on_paragraph_progress(self, event: HybridParagraphProgress) -> None:
        snapshot = self._snapshots.get(event.ordinal)
        if snapshot is not None:
            snapshot = replace(snapshot, status=event.status, receipt_reused=event.receipt_reused)
            self._emit(snapshot)

    def _meta(self, representation_id: str, paragraph_node_id: str) -> _ParagraphMeta:
        if self._bundle is None or self._bundle.representation.id != representation_id:
            self._bundle = self._source.get_document_representation_bundle(representation_id)
            if self._bundle is None:
                raise ValueError("paragraph references a missing document representation.")
        node = next((item for item in self._bundle.nodes if item.id == paragraph_node_id), None)
        if node is None:
            raise ValueError("paragraph references a missing document node.")
        view = next(item for item in self._bundle.text_views if item.id == node.text_view_id)
        return _ParagraphMeta(
            view.text[node.start_char : node.end_char],
            representation_id,
            paragraph_node_id,
            node.start_char,
            self._bundle,
        )

    def _publish(
        self,
        meta: _ParagraphMeta,
        outputs: dict[str, object],
        ordinal: int,
        total: int,
        status: str = "processing",
        gap_reasons: tuple[str, ...] = (),
    ) -> None:
        try:
            profile = build_profile(
                text=meta.text,
                representation_id=meta.representation_id,
                paragraph_node_id=meta.paragraph_node_id,
                node_start_char=meta.node_start_char,
                stage_outputs=outputs,
                bundle=meta.bundle,
            )
            profile = replace(
                profile,
                artifacts=tuple(a for a in self._artifacts if a.stage in outputs),
                stage_statuses=profile.stage_statuses
                + tuple((s, v) for s, v in self._phase_states if s in outputs or v == "not run"),
                phase_diagnostics=profile.phase_diagnostics
                + tuple(
                    (s, d)
                    for s, d in self._phase_diagnostics
                    if s in outputs or dict(self._phase_states).get(s) == "not run"
                ),
            )
            snapshot = ParagraphSnapshot(
                ordinal, total, profile, status, context=self._context, gap_reasons=gap_reasons
            )
        except Exception as error:
            # Derived presentation failure: never changes canonical ingestion state.
            previous = self._snapshots.get(ordinal)
            if previous is None:
                empty = build_profile(
                    text=meta.text,
                    representation_id=meta.representation_id,
                    paragraph_node_id=meta.paragraph_node_id,
                    node_start_char=meta.node_start_char,
                    stage_outputs={},
                    bundle=meta.bundle,
                )
                previous = ParagraphSnapshot(ordinal, total, empty, status, context=self._context)
            snapshot = replace(previous, error=f"Presentation error: {error}")
        self._emit(snapshot)

    def _emit(self, snapshot: ParagraphSnapshot) -> None:
        self._snapshots[snapshot.ordinal] = snapshot
        if self._on_snapshot is not None:
            self._on_snapshot(snapshot)

    def replay_stored(
        self,
        paragraphs: Sequence[ParagraphInput],
        select_ordinal: int | None,
        delay: float = 0.0,
        stop: Event | None = None,
    ) -> None:
        for paragraph in paragraphs:
            if stop is not None and stop.is_set():
                return
            if select_ordinal is not None and paragraph.ordinal != select_ordinal:
                continue
            meta = _ParagraphMeta(
                paragraph.text,
                paragraph.representation_id,
                paragraph.paragraph_node_id,
                paragraph.node_start_char,
                paragraph.bundle,
            )
            self._context = paragraph.context or self._context
            self._artifacts = paragraph.artifacts
            self._phase_states = paragraph.phase_states
            self._phase_diagnostics = paragraph.phase_diagnostics
            outputs: dict[str, object] = {}
            self._publish(meta, outputs, paragraph.ordinal, len(paragraphs), "replaying")
            for stage in STAGE_ORDER:
                if stop is not None and stop.is_set():
                    return
                if stage not in paragraph.stage_outputs:
                    continue
                if delay:
                    if stop is None:
                        time.sleep(delay)
                    elif stop.wait(delay):
                        return
                outputs[stage] = paragraph.stage_outputs[stage]
                self._publish(meta, outputs, paragraph.ordinal, len(paragraphs), "replaying")
            self._publish(
                meta,
                outputs,
                paragraph.ordinal,
                len(paragraphs),
                paragraph.status,
                paragraph.gap_reasons,
            )
