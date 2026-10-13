"""Compact, typed debugging handoff for an agent with local Archive access."""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime
from typing import Literal

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.ingestion_inspection import (
    STAGE_ORDER,
    ArtifactHandle,
    InspectionContext,
    ParagraphAnnotationProfile,
)

OperationMode = Literal["ingestion", "replay"]


class SummaryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SnapshotOperation(SummaryRecord):
    mode: OperationMode
    status: Literal["running", "complete", "failed"]
    exit_code: int | None = None


class DebugSource(SummaryRecord):
    representation_id: str
    paragraph_node_id: str
    text_view_id: str | None = None
    node_start_char: int
    text: str
    coordinate_system: Literal["zero_based_paragraph_characters_half_open"] = (
        "zero_based_paragraph_characters_half_open"
    )


class DebugPhase(SummaryRecord):
    stage: str
    status: str
    enabled: bool
    diagnostic_count: int = Field(default=0, ge=0)


class DebugRecord(SummaryRecord):
    record_id: str
    record_type: str
    spans: tuple[int, ...]
    data: dict[str, JsonValue]
    related_ids: tuple[str, ...] = ()
    trace_ids: tuple[str, ...] = ()


class DebugSummary(SummaryRecord):
    schema_version: Literal["kotekomi_debug_summary_v2"] = "kotekomi_debug_summary_v2"
    captured_at: datetime
    context: InspectionContext | None = None
    operation: SnapshotOperation
    paragraph_ordinal: int = Field(ge=0)
    paragraph_status: str
    source: DebugSource
    spans: tuple[tuple[int, int], ...] = ()
    phases: tuple[DebugPhase, ...]
    records: dict[str, tuple[DebugRecord, ...]] = Field(default_factory=dict)
    artifacts: tuple[ArtifactHandle, ...] = ()
    selected_record_id: str | None = None
    errors: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_scope(self) -> DebugSummary:
        if tuple(p.stage for p in self.phases) != STAGE_ORDER:
            raise ValueError("Summary must cover every canonical phase.")
        visible = {p.stage for p in self.phases if p.enabled}
        for start, end in self.spans:
            if not 0 <= start < end <= len(self.source.text):
                raise ValueError("Summary span falls outside the paragraph.")
        for stage, records in self.records.items():
            if stage not in visible:
                raise ValueError("Summary record belongs to a hidden phase.")
            for record in records:
                if any(index < 0 or index >= len(self.spans) for index in record.spans):
                    raise ValueError("Summary record references a missing span.")
        for artifact in self.artifacts:
            if (
                artifact.stage not in STAGE_ORDER
                or len(artifact.sha256) != 64
                or any(c not in "0123456789abcdef" for c in artifact.sha256)
            ):
                raise ValueError("Invalid stage artifact handle.")
            if not artifact.path.startswith("archive/") or ".." in artifact.path.split("/"):
                raise ValueError("Artifact path must be relative to the state root.")
        if self.selected_record_id is not None and self.selected_record_id not in {
            r.record_id for records in self.records.values() for r in records
        }:
            raise ValueError("Selected record is not included in the summary.")
        return self

    def clipboard_json(self) -> str:
        # Version and coordinate convention remain explicit; optional empties are omitted.
        payload = self.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        payload["schema_version"] = self.schema_version
        payload["source"]["coordinate_system"] = self.source.coordinate_system
        import json

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def phase_statuses(
    profile: ParagraphAnnotationProfile, paragraph_status: str, finished: bool
) -> dict[str, str]:
    pending = (
        "not run" if finished or paragraph_status not in {"processing", "replaying"} else "pending"
    )
    recorded = dict(profile.stage_statuses)
    return {
        stage: recorded.get(stage, "received" if stage in profile.present_stages else pending)
        for stage in STAGE_ORDER
    }


def build_debug_summary(
    profile: ParagraphAnnotationProfile,
    *,
    ordinal: int,
    paragraph_status: str,
    operation: SnapshotOperation,
    visible_stages: Collection[str],
    selected_key: str | None,
    context: InspectionContext | None,
    errors: tuple[str, ...] = (),
) -> DebugSummary:
    if set(visible_stages) - set(STAGE_ORDER):
        raise ValueError("Unknown inspection layer.")
    spans: list[tuple[int, int]] = []
    records: dict[str, list[DebugRecord]] = {}
    selected_id = None
    for item in profile.records:
        if item.stage not in visible_stages:
            continue
        indices: list[int] = []
        for span in item.spans:
            if profile.text[span.start : span.end] != span.text:
                raise ValueError("Inspection span differs from authoritative text.")
            pair = (span.start, span.end)
            if pair not in spans:
                spans.append(pair)
            indices.append(spans.index(pair))
        selected = item.key == selected_key
        if selected:
            selected_id = item.record_id
        records.setdefault(item.stage, []).append(
            DebugRecord(
                record_id=item.record_id,
                record_type=item.record_type,
                spans=tuple(indices),
                data={
                    k: v
                    for k, v in item.data.items()
                    if selected
                    or item.stage != "hp1_mentions"
                    or k not in {"referentiality", "discourse_role"}
                },
                related_ids=item.related_ids if selected else (),
                trace_ids=item.trace_ids if selected else (),
            )
        )
    if selected_key is not None and selected_id is None:
        raise ValueError("Selected annotation has no canonical record in the enabled layers.")
    statuses = phase_statuses(profile, paragraph_status, operation.status != "running")
    diagnostics = dict(profile.phase_diagnostics)
    return DebugSummary(
        captured_at=datetime.now(UTC),
        context=context,
        operation=operation,
        paragraph_ordinal=ordinal,
        paragraph_status=paragraph_status,
        source=DebugSource(
            representation_id=profile.representation_id,
            paragraph_node_id=profile.paragraph_node_id,
            text_view_id=profile.text_view_id,
            node_start_char=profile.node_start_char,
            text=profile.text,
        ),
        spans=tuple(spans),
        phases=tuple(
            DebugPhase(
                stage=s,
                status=statuses[s],
                enabled=s in visible_stages,
                diagnostic_count=len(diagnostics.get(s, ())),
            )
            for s in STAGE_ORDER
        ),
        records={stage: tuple(rows) for stage, rows in records.items()},
        artifacts=profile.artifacts,
        selected_record_id=selected_id,
        errors=errors,
    )
