"""Source-bound HP-4 event frame evidence contracts."""

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

HYBRID_EVENT_FRAME_POLICY_ID = "hybrid_event_frame_v1"
_SHA256 = r"^[a-f0-9]{64}$"
_ID = r"^[a-z]+_[a-f0-9]{24}$"
_OPEN_LABEL = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$"


class EventPolarity(StrEnum):
    AFFIRMED = "affirmed"
    NEGATED = "negated"


class EventModality(StrEnum):
    ACTUAL = "actual"
    PLANNED = "planned"
    POSSIBLE = "possible"
    UNCERTAIN = "uncertain"
    RECOMMENDED = "recommended"
    HYPOTHETICAL = "hypothetical"


class EventQualifierKind(StrEnum):
    TIME = "time"
    PLACE = "place"


class EventArgumentReferenceStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class HybridEventFrameStatus(StrEnum):
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
        expected = _id(
            "etd",
            self.source_segment_id,
            self.source_text_sha256,
            str(self.start),
            str(self.end),
            self.text,
            self.event_type_label,
            self.extraction_task_id,
            self.model_run_id,
            self.trace_id,
        )
        if self.id != expected:
            raise ValueError("EventTriggerDraft ID does not match its evidence.")
        return self


class EventArgumentDraft(BaseModel):
    """One model role mapped to one source-valid MentionCandidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=_ID)]
    role_label: Annotated[str, Field(pattern=_OPEN_LABEL)]
    support_segment_id: Annotated[str, Field(min_length=1)]
    reference_status: EventArgumentReferenceStatus
    reference_decision_id: Annotated[str, Field(pattern=_ID)] | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.reference_status is EventArgumentReferenceStatus.NOT_APPLICABLE:
            if self.reference_decision_id is not None:
                raise ValueError("A non-reference event argument cannot name a decision.")
        elif self.reference_decision_id is None:
            raise ValueError("A reference-bearing event argument requires its decision.")
        return self


class EventQualifierDraft(BaseModel):
    """One exact source qualifier for an event frame."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: EventQualifierKind
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("EventQualifierDraft range does not match its text.")
        return self


class EventFrameDraft(BaseModel):
    """One validated but non-authoritative event interpretation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^efd_[a-f0-9]{24}$")]
    trigger_id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]
    polarity: EventPolarity
    modality: EventModality
    source_narrator_attribution: bool
    attribution_candidate_ids: tuple[Annotated[str, Field(pattern=_ID)], ...] = ()
    arguments: tuple[EventArgumentDraft, ...] = ()
    qualifiers: tuple[EventQualifierDraft, ...] = ()
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.source_narrator_attribution == bool(self.attribution_candidate_ids):
            raise ValueError("Event attribution requires exactly one attribution form.")
        _ordered_distinct("attribution candidate IDs", self.attribution_candidate_ids)
        if len(set(self.arguments)) != len(self.arguments):
            raise ValueError("EventFrameDraft repeats an argument.")
        if len(set(self.qualifiers)) != len(self.qualifiers):
            raise ValueError("EventFrameDraft repeats a qualifier.")
        expected = _id(
            "efd",
            self.trigger_id,
            self.polarity.value,
            self.modality.value,
            str(self.source_narrator_attribution),
            *self.attribution_candidate_ids,
            *(_canonical_json(item.model_dump(mode="json")) for item in self.arguments),
            *(_canonical_json(item.model_dump(mode="json")) for item in self.qualifiers),
            self.extraction_task_id,
            self.model_run_id,
            self.trace_id,
        )
        if self.id != expected:
            raise ValueError("EventFrameDraft ID does not match its evidence.")
        return self


class HybridEventFramePreview(BaseModel):
    """Immutable derived evidence for one terminal HP-4 paragraph run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_event_frame_preview_v1"] = "hybrid_event_frame_preview_v1"
    id: Annotated[str, Field(pattern=r"^hep_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hgp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    reference_preview_id: Annotated[str, Field(pattern=r"^hrp_[a-f0-9]{24}$")]
    reference_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    mention_preview_id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    mention_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    trigger_context_manifest_id: Annotated[str, Field(min_length=1)]
    frame_context_manifest_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["hybrid_event_frame_v1"] = HYBRID_EVENT_FRAME_POLICY_ID
    triggers: tuple[EventTriggerDraft, ...] = ()
    frames: tuple[EventFrameDraft, ...] = ()
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: HybridEventFrameStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("ExtractionTask IDs", self.extraction_task_ids),
            ("ModelRun IDs", self.model_run_ids),
            ("diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        trigger_by_id = {item.id: item for item in self.triggers}
        if len(trigger_by_id) != len(self.triggers):
            raise ValueError("HybridEventFramePreview repeats a trigger.")
        if len({item.id for item in self.frames}) != len(self.frames):
            raise ValueError("HybridEventFramePreview repeats a frame.")
        if any(item.trigger_id not in trigger_by_id for item in self.frames):
            raise ValueError("EventFrameDraft references an unknown trigger.")
        if len({item.trigger_id for item in self.frames}) != len(self.frames):
            raise ValueError("HybridEventFramePreview repeats a trigger frame.")
        if self.terminal_status is HybridEventFrameStatus.COMPLETE and len(self.frames) != len(
            self.triggers
        ):
            raise ValueError("A complete HP-4 Preview requires one frame per trigger.")
        if self.terminal_status is HybridEventFrameStatus.PARTIAL and not self.diagnostics:
            raise ValueError("A partial HP-4 Preview requires a diagnostic.")
        if self.terminal_status is HybridEventFrameStatus.BLOCKED and self.frames:
            raise ValueError("A blocked HP-4 Preview cannot contain frames.")
        if self.terminal_status is HybridEventFrameStatus.BLOCKED and not self.diagnostics:
            raise ValueError("A blocked HP-4 Preview requires a diagnostic.")
        trace_ids = {item.id for item in self.traces}
        if len(trace_ids) != len(self.traces):
            raise ValueError("HybridEventFramePreview repeats a trace.")
        if any(item.trace_id not in trace_ids for item in (*self.triggers, *self.frames)):
            raise ValueError("HP-4 draft trace lineage is missing.")
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
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridEventFramePreview ID does not match its contents.")
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


def event_frame_id(
    *,
    trigger_id: str,
    polarity: EventPolarity,
    modality: EventModality,
    source_narrator_attribution: bool,
    attribution_candidate_ids: tuple[str, ...],
    arguments: tuple[EventArgumentDraft, ...],
    qualifiers: tuple[EventQualifierDraft, ...],
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
) -> str:
    return _id(
        "efd",
        trigger_id,
        polarity.value,
        modality.value,
        str(source_narrator_attribution),
        *attribution_candidate_ids,
        *(_canonical_json(item.model_dump(mode="json")) for item in arguments),
        *(_canonical_json(item.model_dump(mode="json")) for item in qualifiers),
        extraction_task_id,
        model_run_id,
        trace_id,
    )


def build_hybrid_event_frame_preview(**values: object) -> HybridEventFramePreview:
    payload = dict(values)
    payload.pop("id", None)
    payload.setdefault("schema_version", "hybrid_event_frame_preview_v1")
    payload.setdefault("policy_id", HYBRID_EVENT_FRAME_POLICY_ID)
    for name in (
        "triggers",
        "frames",
        "extraction_task_ids",
        "model_run_ids",
        "traces",
        "diagnostics",
    ):
        payload.setdefault(name, ())
    for name in ("triggers", "frames", "traces"):
        payload[name] = [
            item.model_dump(mode="json") for item in cast(tuple[BaseModel, ...], payload[name])
        ]
    normalized = cast(dict[str, JsonValue], json.loads(_canonical_json(payload)))
    normalized["id"] = _preview_id(normalized)
    return HybridEventFramePreview.model_validate_json(_canonical_json(normalized))


def canonical_hybrid_event_frame_preview_bytes(preview: HybridEventFramePreview) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode()


def hybrid_event_frame_preview_sha256(preview: HybridEventFramePreview) -> str:
    return hashlib.sha256(canonical_hybrid_event_frame_preview_bytes(preview)).hexdigest()


def hybrid_event_frame_preview_from_bytes(payload: bytes) -> HybridEventFramePreview:
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("HybridEventFramePreview is not valid JSON.") from error
    preview = HybridEventFramePreview.model_validate_json(payload)
    if canonical_hybrid_event_frame_preview_bytes(preview) != payload:
        raise ValueError("HybridEventFramePreview does not use canonical encoding.")
    return preview


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _preview_id(payload: dict[str, JsonValue]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode()).hexdigest()
    return f"hep_{digest[:24]}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"HP-4 {label} must be ordered and distinct.")
