"""Source-bound HP-4 event trigger evidence contracts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageTrace,
    validate_extraction_stage_trace_chain,
)

HYBRID_EVENT_TRIGGER_POLICY_ID = "hybrid_event_trigger_v3"
_SHA256 = r"^[a-f0-9]{64}$"
_OPEN_LABEL = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$"


class HybridEventTriggerStatus(StrEnum):
    """Terminal status for one HP-4 trigger Preview."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class EventTriggerDraft(BaseModel):
    """One model trigger mapped to an exact authoritative SourceSegment range."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    event_type_label: Annotated[str, Field(pattern=_OPEN_LABEL)]
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("EventTriggerDraft range does not match its text.")
        expected = event_trigger_id(
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            start=self.start,
            end=self.end,
            text=self.text,
            event_type_label=self.event_type_label,
            extraction_task_id=self.extraction_task_id,
            model_run_id=self.model_run_id,
            trace_id=self.trace_id,
        )
        if self.id != expected:
            raise ValueError("EventTriggerDraft ID does not match its evidence.")
        return self


class HybridEventTriggerPreview(BaseModel):
    """Immutable derived evidence for one terminal HP-4 paragraph run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_event_trigger_preview_v2"] = "hybrid_event_trigger_preview_v2"
    id: Annotated[str, Field(pattern=r"^htp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hgp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    reference_preview_id: Annotated[str, Field(pattern=r"^hrp_[a-f0-9]{24}$")]
    reference_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    mention_preview_id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    mention_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    context_manifest_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    policy_id: Literal["hybrid_event_trigger_v3"] = HYBRID_EVENT_TRIGGER_POLICY_ID
    triggers: tuple[EventTriggerDraft, ...] = ()
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: HybridEventTriggerStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("ContextManifest IDs", self.context_manifest_ids),
            ("ExtractionTask IDs", self.extraction_task_ids),
            ("ModelRun IDs", self.model_run_ids),
            ("diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        if len({item.id for item in self.triggers}) != len(self.triggers):
            raise ValueError("HybridEventTriggerPreview repeats a trigger.")
        if len(self.extraction_task_ids) != len(self.model_run_ids):
            raise ValueError("HP-4 task and ModelRun coverage must match.")
        trace_ids = {item.id for item in self.traces}
        if len(trace_ids) != len(self.traces):
            raise ValueError("HybridEventTriggerPreview repeats a trace.")
        if any(item.trace_id not in trace_ids for item in self.triggers):
            raise ValueError("HP-4 trigger trace lineage is missing.")
        execution_ids = set(self.extraction_task_ids) | set(self.model_run_ids)
        traced_execution_ids = {
            item for trace in self.traces for item in trace.execution_record_ids
        }
        if traced_execution_ids != execution_ids:
            raise ValueError("HP-4 Preview must trace every execution record.")
        traces_by_run: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_run[trace.trace_run_id].append(trace)
        for trace_run in traces_by_run.values():
            validate_extraction_stage_trace_chain(tuple(trace_run))
        if self.terminal_status is HybridEventTriggerStatus.PARTIAL and not self.diagnostics:
            raise ValueError("A partial HP-4 Preview requires a diagnostic.")
        if self.terminal_status is HybridEventTriggerStatus.BLOCKED:
            if self.triggers or not self.diagnostics:
                raise ValueError("A blocked HP-4 Preview requires only diagnostics.")
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridEventTriggerPreview ID does not match its contents.")
        return self


def event_trigger_id(
    *,
    source_segment_id: str,
    source_text_sha256: str,
    start: int,
    end: int,
    text: str,
    event_type_label: str,
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
) -> str:
    return _id(
        "etd",
        source_segment_id,
        source_text_sha256,
        str(start),
        str(end),
        text,
        event_type_label,
        extraction_task_id,
        model_run_id,
        trace_id,
    )


def build_hybrid_event_trigger_preview(**values: object) -> HybridEventTriggerPreview:
    payload = dict(values)
    payload.pop("id", None)
    payload.setdefault("schema_version", "hybrid_event_trigger_preview_v2")
    payload.setdefault("policy_id", HYBRID_EVENT_TRIGGER_POLICY_ID)
    for name in (
        "context_manifest_ids",
        "triggers",
        "extraction_task_ids",
        "model_run_ids",
        "traces",
        "diagnostics",
    ):
        payload.setdefault(name, ())
    payload["triggers"] = [
        item.model_dump(mode="json")
        for item in cast(tuple[EventTriggerDraft, ...], payload["triggers"])
    ]
    payload["traces"] = [
        item.model_dump(mode="json")
        for item in cast(tuple[ExtractionStageTrace, ...], payload["traces"])
    ]
    normalized = cast(dict[str, JsonValue], json.loads(json.dumps(payload)))
    normalized["id"] = _preview_id(normalized)
    return HybridEventTriggerPreview.model_validate_json(_canonical_json(normalized))


def canonical_hybrid_event_trigger_preview_bytes(preview: HybridEventTriggerPreview) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode()


def hybrid_event_trigger_preview_sha256(preview: HybridEventTriggerPreview) -> str:
    return hashlib.sha256(canonical_hybrid_event_trigger_preview_bytes(preview)).hexdigest()


def hybrid_event_trigger_preview_from_bytes(payload: bytes) -> HybridEventTriggerPreview:
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("HybridEventTriggerPreview is not valid JSON.") from error
    preview = HybridEventTriggerPreview.model_validate_json(payload)
    if canonical_hybrid_event_trigger_preview_bytes(preview) != payload:
        raise ValueError("HybridEventTriggerPreview does not use canonical encoding.")
    return preview


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


def _preview_id(payload: dict[str, JsonValue]) -> str:
    return f"htp_{hashlib.sha256(_canonical_json(payload).encode()).hexdigest()[:24]}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"{label} must be ordered and distinct.")
