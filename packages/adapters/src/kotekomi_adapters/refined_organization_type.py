"""Isolated ReFinED Adapter for contextual typing of caller-owned spans."""

from __future__ import annotations

import json
import math
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Protocol, cast

from kotekomi_application.organization_semantic_qualification import (
    ContextualEntityTypePrediction,
    ContextualLinkedEntity,
    ContextualOrganizationTypeBatch,
    ContextualOrganizationTypeEvidence,
    ContextualOrganizationTypeInput,
)

REFINED_PACKAGE_REVISION = "7c98036f72c39a8d6d2c097bbde89ea3731901f0"
REFINED_MODEL_ID = "wikipedia_model"
REFINED_MODEL_REVISION = "refined-v1-wikipedia-model"
REFINED_ENTITY_SET = "wikipedia"
REFINED_RESOURCE_MANIFEST_SHA256 = (
    "75ca7833e4fbcc94bf05b129c591d7656900f1f61edb55cdb0b20f2d6518094b"
)

_REQUEST_FIELDS = {
    "schema_version",
    "source_segment_id",
    "source_text_sha256",
    "source_text",
    "model_id",
    "model_revision",
    "entity_set",
    "package_revision",
    "data_dir",
    "download_files",
    "candidates",
}
_RESPONSE_FIELDS = {
    "schema_version",
    "status",
    "producer_id",
    "model_id",
    "model_revision",
    "entity_set",
    "package_revision",
    "resource_manifest_sha256",
    "load_elapsed_ms",
    "inference_elapsed_ms",
    "evidences",
}
_FAILURE_RESPONSE_FIELDS = {"schema_version", "status", "failure", "diagnostics"}
_EVIDENCE_FIELDS = {
    "candidate_id",
    "returned_text",
    "start",
    "end",
    "coarse_type",
    "coarse_mention_type",
    "predicted_entity",
    "entity_linking_score",
    "top_k_entities",
    "predicted_entity_types",
    "failed_class_check",
}
_ENTITY_FIELDS = {
    "wikidata_entity_id",
    "wikipedia_entity_title",
    "human_readable_name",
    "parsed_string",
    "score",
}
_TYPE_FIELDS = {"type_id", "type_label", "confidence"}


@dataclass(frozen=True)
class RefinedWorkerConfig:
    """Explicit isolated worker and resource configuration."""

    python_executable: Path
    worker_script: Path
    data_dir: Path
    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        if not self.python_executable.is_absolute() or not self.worker_script.is_absolute():
            raise ValueError("ReFinED worker executable and script paths must be absolute.")
        if not self.data_dir.is_absolute():
            raise ValueError("ReFinED worker data directory must be absolute.")
        if self.timeout_seconds <= 0:
            raise ValueError("ReFinED worker timeout must be positive.")


class RefinedWorkerTransport(Protocol):
    """Strict request/response transport for an isolated ReFinED runtime."""

    def request(self, payload: dict[str, object]) -> dict[str, object]: ...

    def close(self) -> None: ...


class RefinedWorkerError(RuntimeError):
    """Typed isolated-worker failure suitable for a blocked evaluation result."""

    def __init__(self, failure: str, diagnostics: tuple[str, ...]) -> None:
        self.failure = failure
        self.diagnostics = diagnostics
        super().__init__(f"ReFinED worker failed with {failure}: {'; '.join(diagnostics)}")


class SubprocessRefinedWorkerTransport:
    """Persistent line-delimited JSON transport to one pinned Python worker."""

    def __init__(self, config: RefinedWorkerConfig) -> None:
        if not config.python_executable.is_file():
            raise RuntimeError("ReFinED worker Python executable is unavailable.")
        if not config.worker_script.is_file():
            raise RuntimeError("ReFinED worker script is unavailable.")
        self._timeout_seconds = config.timeout_seconds
        self._process = subprocess.Popen(
            [str(config.python_executable), str(config.worker_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        process = self._process
        if process.poll() is not None or process.stdin is None or process.stdout is None:
            raise RuntimeError("ReFinED worker is not running.")
        request_text = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        process.stdin.write(request_text + "\n")
        process.stdin.flush()
        selector = selectors.DefaultSelector()
        try:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(self._timeout_seconds):
                raise TimeoutError("ReFinED worker exceeded its configured timeout.")
            response_text = process.stdout.readline()
        finally:
            selector.close()
        if not response_text:
            raise RuntimeError("ReFinED worker exited without a response.")
        try:
            response: object = json.loads(response_text)
        except json.JSONDecodeError as error:
            raise RuntimeError("ReFinED worker returned malformed JSON.") from error
        return _mapping("response", response)

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)

    def __enter__(self) -> SubprocessRefinedWorkerTransport:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()


class RefinedContextualOrganizationTypeAdapter:
    """Map official ReFinED predetermined-span results into Application DTOs."""

    def __init__(
        self,
        config: RefinedWorkerConfig,
        *,
        transport: RefinedWorkerTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or SubprocessRefinedWorkerTransport(config)

    def qualify(
        self,
        request: ContextualOrganizationTypeInput,
    ) -> ContextualOrganizationTypeBatch:
        payload = _request_payload(request, self._config)
        response = self._transport.request(payload)
        batch = _parse_response(response)
        _validate_response_identity(batch)
        _validate_evidence_alignment(request, batch)
        return batch

    def close(self) -> None:
        self._transport.close()


def _request_payload(
    request: ContextualOrganizationTypeInput,
    config: RefinedWorkerConfig,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "refined_contextual_type_request_v1",
        "source_segment_id": request.source_segment_id,
        "source_text_sha256": request.source_text_sha256,
        "source_text": request.source_text,
        "model_id": REFINED_MODEL_ID,
        "model_revision": REFINED_MODEL_REVISION,
        "entity_set": REFINED_ENTITY_SET,
        "package_revision": REFINED_PACKAGE_REVISION,
        "data_dir": str(config.data_dir),
        "download_files": False,
        "candidates": [
            {
                "candidate_id": candidate.id,
                "text": candidate.text,
                "start": candidate.start,
                "end": candidate.end,
            }
            for candidate in request.candidates
        ],
    }
    if set(payload) != _REQUEST_FIELDS:
        raise AssertionError("ReFinED request contract drifted.")
    return payload


def _parse_response(value: dict[str, object]) -> ContextualOrganizationTypeBatch:
    if "schema_version" not in value or "status" not in value:
        raise ValueError("ReFinED response requires schema_version and status.")
    if value["schema_version"] != "refined_contextual_type_response_v1":
        raise ValueError("ReFinED response schema version is unsupported.")
    if value["status"] != "completed":
        _require_fields("failure response", value, _FAILURE_RESPONSE_FIELDS)
        diagnostics_value = value["diagnostics"]
        if not isinstance(diagnostics_value, list):
            raise ValueError("ReFinED failure diagnostics must be non-empty strings.")
        diagnostic_items = cast(list[object], diagnostics_value)
        if not all(isinstance(item, str) and item for item in diagnostic_items):
            raise ValueError("ReFinED failure diagnostics must be non-empty strings.")
        raise RefinedWorkerError(
            _string(value, "failure"),
            tuple(cast(str, item) for item in diagnostic_items),
        )
    _require_fields("response", value, _RESPONSE_FIELDS)
    evidences_value = value["evidences"]
    if not isinstance(evidences_value, list):
        raise ValueError("ReFinED response evidences must be a list.")
    evidence_items = cast(list[object], evidences_value)
    return ContextualOrganizationTypeBatch(
        producer_id=_string(value, "producer_id"),
        model_id=_string(value, "model_id"),
        model_revision=_string(value, "model_revision"),
        entity_set=_string(value, "entity_set"),
        package_revision=_string(value, "package_revision"),
        resource_manifest_sha256=_string(value, "resource_manifest_sha256"),
        load_elapsed_ms=_integer(value, "load_elapsed_ms"),
        inference_elapsed_ms=_integer(value, "inference_elapsed_ms"),
        evidences=tuple(_parse_evidence(item) for item in evidence_items),
    )


def _parse_evidence(value: object) -> ContextualOrganizationTypeEvidence:
    mapping = _mapping("evidence", value)
    _require_fields("evidence", mapping, _EVIDENCE_FIELDS)
    top_k = mapping["top_k_entities"]
    predictions = mapping["predicted_entity_types"]
    if not isinstance(top_k, list) or not isinstance(predictions, list):
        raise ValueError("ReFinED evidence entity and type predictions must be lists.")
    top_k_items = cast(list[object], top_k)
    prediction_items = cast(list[object], predictions)
    predicted_entity_value = mapping["predicted_entity"]
    return ContextualOrganizationTypeEvidence(
        candidate_id=_string(mapping, "candidate_id"),
        returned_text=_string(mapping, "returned_text"),
        start=_integer(mapping, "start"),
        end=_integer(mapping, "end"),
        coarse_type=_optional_string(mapping, "coarse_type"),
        coarse_mention_type=_optional_string(mapping, "coarse_mention_type"),
        predicted_entity=(
            None if predicted_entity_value is None else _parse_entity(predicted_entity_value)
        ),
        entity_linking_score=_optional_number(mapping, "entity_linking_score"),
        top_k_entities=tuple(_parse_entity(item) for item in top_k_items),
        predicted_entity_types=tuple(_parse_type(item) for item in prediction_items),
        failed_class_check=_optional_bool(mapping, "failed_class_check"),
    )


def _parse_entity(value: object) -> ContextualLinkedEntity:
    mapping = _mapping("entity", value)
    _require_fields("entity", mapping, _ENTITY_FIELDS)
    return ContextualLinkedEntity(
        wikidata_entity_id=_optional_string(mapping, "wikidata_entity_id"),
        wikipedia_entity_title=_optional_string(mapping, "wikipedia_entity_title"),
        human_readable_name=_optional_string(mapping, "human_readable_name"),
        parsed_string=_optional_string(mapping, "parsed_string"),
        score=_optional_number(mapping, "score"),
    )


def _parse_type(value: object) -> ContextualEntityTypePrediction:
    mapping = _mapping("entity type", value)
    _require_fields("entity type", mapping, _TYPE_FIELDS)
    return ContextualEntityTypePrediction(
        type_id=_string(mapping, "type_id"),
        type_label=_optional_string(mapping, "type_label"),
        confidence=_optional_number(mapping, "confidence"),
    )


def _validate_response_identity(batch: ContextualOrganizationTypeBatch) -> None:
    expected = (
        REFINED_MODEL_ID,
        REFINED_MODEL_REVISION,
        REFINED_ENTITY_SET,
        REFINED_PACKAGE_REVISION,
    )
    actual = (batch.model_id, batch.model_revision, batch.entity_set, batch.package_revision)
    if actual != expected:
        raise ValueError("ReFinED response identity drifted from the pinned Adapter configuration.")
    if batch.resource_manifest_sha256 != REFINED_RESOURCE_MANIFEST_SHA256:
        raise ValueError("ReFinED resource manifest drifted from the pinned Adapter configuration.")


def _validate_evidence_alignment(
    request: ContextualOrganizationTypeInput,
    batch: ContextualOrganizationTypeBatch,
) -> None:
    if len(batch.evidences) != len(request.candidates):
        raise ValueError("ReFinED evidence must match all ordered input candidates.")
    for candidate, evidence in zip(request.candidates, batch.evidences, strict=True):
        if evidence.candidate_id != candidate.id:
            raise ValueError("ReFinED evidence must match ordered input candidates.")
        if (
            evidence.returned_text != candidate.text
            or evidence.start != candidate.start
            or evidence.end != candidate.end
            or request.source_text[evidence.start : evidence.end] != evidence.returned_text
        ):
            raise ValueError("ReFinED evidence does not match authoritative source characters.")


def _mapping(label: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"ReFinED {label} must be an object.")
    raw_mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_mapping):
        raise ValueError(f"ReFinED {label} must use string keys.")
    return {cast(str, key): item for key, item in raw_mapping.items()}


def _require_fields(label: str, value: dict[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        raise ValueError(f"ReFinED {label} fields do not match the pinned contract.")


def _string(value: dict[str, object], key: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item:
        raise ValueError(f"ReFinED {key} must be a non-empty string.")
    return item


def _optional_string(value: dict[str, object], key: str) -> str | None:
    item = value[key]
    if item is not None and not isinstance(item, str):
        raise ValueError(f"ReFinED {key} must be a string or null.")
    return item


def _integer(value: dict[str, object], key: str) -> int:
    item = value[key]
    if type(item) is not int:
        raise ValueError(f"ReFinED {key} must be an integer.")
    return item


def _optional_number(value: dict[str, object], key: str) -> float | None:
    item = value[key]
    if item is None:
        return None
    if not isinstance(item, (int, float)) or isinstance(item, bool):
        raise ValueError(f"ReFinED {key} must be numeric or null.")
    numeric = float(item)
    if not math.isfinite(numeric):
        raise ValueError(f"ReFinED {key} must be finite.")
    return numeric


def _optional_bool(value: dict[str, object], key: str) -> bool | None:
    item = value[key]
    if item is not None and type(item) is not bool:
        raise ValueError(f"ReFinED {key} must be Boolean or null.")
    return item
