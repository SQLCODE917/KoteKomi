"""Typed, source-bound diagnostics for staged information extraction."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Any, Literal, Self, cast

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_TRACE_ID_PATTERN = r"^xst_[a-f0-9]{24}$"


class ExtractionStageStatus(StrEnum):
    """Terminal outcome of one bounded extraction stage."""

    COMPLETED = "completed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"
    FAILED = "failed"


class ExtractionStageTrace(BaseModel):
    """Derived evidence of one stage's exact input, output, and lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["extraction_stage_trace_v1"] = "extraction_stage_trace_v1"
    id: Annotated[str, Field(pattern=_TRACE_ID_PATTERN)]
    trace_run_id: Annotated[str, Field(min_length=1)]
    ordinal: Annotated[int, Field(ge=0)]
    stage_id: Annotated[str, Field(min_length=1)]
    stage_version: Annotated[str, Field(min_length=1)]
    producer_id: Annotated[str, Field(min_length=1)]
    authority: Literal["derived_diagnostic"] = "derived_diagnostic"
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    parent_trace_ids: tuple[Annotated[str, Field(pattern=_TRACE_ID_PATTERN)], ...] = ()
    input_record_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    execution_record_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    configuration: dict[str, JsonValue]
    configuration_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    input: dict[str, JsonValue]
    input_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    output: dict[str, JsonValue]
    output_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    status: ExtractionStageStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _require_ordered_distinct("parent trace IDs", self.parent_trace_ids)
        _require_ordered_distinct("input record IDs", self.input_record_ids)
        _require_ordered_distinct("execution record IDs", self.execution_record_ids)
        _require_ordered_distinct("diagnostics", self.diagnostics)
        if self.configuration_sha256 != _payload_sha256(self.configuration):
            raise ValueError("Extraction stage configuration digest does not match its payload.")
        if self.input_sha256 != _payload_sha256(self.input):
            raise ValueError("Extraction stage input digest does not match its payload.")
        if self.output_sha256 != _payload_sha256(self.output):
            raise ValueError("Extraction stage output digest does not match its payload.")
        if self.status is not ExtractionStageStatus.COMPLETED and not self.diagnostics:
            raise ValueError("A non-completed extraction stage requires a diagnostic.")
        if self.id != _trace_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("Extraction stage trace ID does not match its contents.")
        return self


def build_extraction_stage_trace(
    *,
    trace_run_id: str,
    ordinal: int,
    stage_id: str,
    stage_version: str,
    producer_id: str,
    source_segment_id: str,
    source_text_sha256: str,
    configuration: dict[str, JsonValue],
    input_payload: dict[str, JsonValue],
    output_payload: dict[str, JsonValue],
    status: ExtractionStageStatus,
    parent_trace_ids: tuple[str, ...] = (),
    input_record_ids: tuple[str, ...] = (),
    execution_record_ids: tuple[str, ...] = (),
    diagnostics: tuple[str, ...] = (),
) -> ExtractionStageTrace:
    """Validate and construct one deterministic derived stage trace."""
    configuration_copy = _json_copy(configuration)
    input_copy = _json_copy(input_payload)
    output_copy = _json_copy(output_payload)
    identity_payload: dict[str, JsonValue] = {
        "schema_version": "extraction_stage_trace_v1",
        "trace_run_id": trace_run_id,
        "ordinal": ordinal,
        "stage_id": stage_id,
        "stage_version": stage_version,
        "producer_id": producer_id,
        "authority": "derived_diagnostic",
        "source_segment_id": source_segment_id,
        "source_text_sha256": source_text_sha256,
        "parent_trace_ids": list(parent_trace_ids),
        "input_record_ids": list(input_record_ids),
        "execution_record_ids": list(execution_record_ids),
        "configuration": configuration_copy,
        "configuration_sha256": _payload_sha256(configuration_copy),
        "input": input_copy,
        "input_sha256": _payload_sha256(input_copy),
        "output": output_copy,
        "output_sha256": _payload_sha256(output_copy),
        "status": status.value,
        "diagnostics": list(diagnostics),
    }
    model_payload: dict[str, Any] = {
        **identity_payload,
        "id": _trace_id(identity_payload),
        "parent_trace_ids": parent_trace_ids,
        "input_record_ids": input_record_ids,
        "execution_record_ids": execution_record_ids,
        "status": status,
        "diagnostics": diagnostics,
    }
    return ExtractionStageTrace.model_validate(model_payload)


def validate_extraction_stage_trace_chain(
    traces: tuple[ExtractionStageTrace, ...],
) -> None:
    """Reject incomplete, cross-source, or non-causal stage lineage."""
    if not traces:
        raise ValueError("An extraction stage trace chain cannot be empty.")
    trace_run_ids = {trace.trace_run_id for trace in traces}
    source_identities = {(trace.source_segment_id, trace.source_text_sha256) for trace in traces}
    if len(trace_run_ids) != 1 or len(source_identities) != 1:
        raise ValueError("An extraction stage trace chain must bind one Source segment run.")
    ordered = tuple(sorted(traces, key=lambda trace: trace.ordinal))
    if tuple(trace.ordinal for trace in ordered) != tuple(range(len(ordered))):
        raise ValueError("Extraction stage trace ordinals must be contiguous from zero.")
    seen: set[str] = set()
    for trace in ordered:
        if trace.id in seen:
            raise ValueError("Extraction stage trace IDs must be unique.")
        if not set(trace.parent_trace_ids).issubset(seen):
            raise ValueError("Extraction stage parents must be earlier records in the same chain.")
        seen.add(trace.id)


def extraction_stage_trace_to_json(trace: ExtractionStageTrace) -> dict[str, JsonValue]:
    """Serialize a validated trace for a diagnostic artifact boundary."""
    return cast(dict[str, JsonValue], trace.model_dump(mode="json"))


def extraction_stage_trace_from_json(payload: dict[str, JsonValue]) -> ExtractionStageTrace:
    """Parse a structured JSON boundary through the strict trace DTO."""
    return ExtractionStageTrace.model_validate_json(_canonical_json(payload))


def canonical_extraction_stage_trace_json(trace: ExtractionStageTrace) -> str:
    """Return canonical UTF-8 JSON text for hashing or persistence."""
    return _canonical_json(extraction_stage_trace_to_json(trace))


def _payload_sha256(payload: dict[str, JsonValue]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _trace_id(payload: dict[str, JsonValue]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"xst_{digest[:24]}"


def _canonical_json(value: JsonValue) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Extraction stage trace values must be finite JSON values.") from error


def _json_copy(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], json.loads(_canonical_json(value)))


def _require_ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"Extraction stage {label} must be ordered and distinct.")
