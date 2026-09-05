"""Strict offline ReFinED Adapter for HP-3 external-identity candidate evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from kotekomi_application.hybrid_entity_grounding import (
    EntityLinkCandidate,
    EntityLinkCandidateKind,
    EntityLinkerEvidence,
    EntityLinkerIdentity,
    EntityLinkingBatch,
    EntityLinkingExecution,
    EntityLinkingInput,
    EntityLinkingOutputError,
    EntityLinkingRuntimeResponseError,
)

from kotekomi_adapters.refined_worker_transport import (
    RefinedWorkerTransport,
    SubprocessRefinedWorkerTransport,
)

REFINED_PACKAGE_REVISION = "7c98036f72c39a8d6d2c097bbde89ea3731901f0"
REFINED_MODEL_ID = "wikipedia_model"
REFINED_MODEL_REVISION = "refined-v1-wikipedia-model"
REFINED_ENTITY_SET = "wikipedia"
REFINED_RESOURCE_MANIFEST_SHA256 = (
    "75ca7833e4fbcc94bf05b129c591d7656900f1f61edb55cdb0b20f2d6518094b"
)
REFINED_RUNTIME_IDENTITY = "isolated:refined-worker-exchange-v1"

_REQUEST_FIELDS = {
    "schema_version",
    "source_segment_id",
    "source_text_sha256",
    "source_text",
    "identity",
    "data_dir",
    "download_files",
    "options",
    "mentions",
}
_RESPONSE_FIELDS = {
    "schema_version",
    "status",
    "identity",
    "load_elapsed_ms",
    "inference_elapsed_ms",
    "evidences",
}
_FAILURE_FIELDS = {"schema_version", "status", "failure", "diagnostics"}
_EVIDENCE_FIELDS = {"candidate_id", "returned_text", "start", "end", "candidates"}
_CANDIDATE_FIELDS = {
    "rank",
    "kind",
    "wikidata_id",
    "wikipedia_title",
    "wikipedia_title_wikidata_id",
    "label",
    "score",
}


@dataclass(frozen=True)
class RefinedEntityLinkingConfig:
    python_executable: Path
    worker_script: Path
    data_dir: Path
    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        if not self.python_executable.is_absolute() or not self.worker_script.is_absolute():
            raise ValueError("ReFinED executable and worker script paths must be absolute.")
        if not self.data_dir.is_absolute():
            raise ValueError("ReFinED resource directory must be absolute.")
        if self.timeout_seconds <= 0:
            raise ValueError("ReFinED timeout must be positive.")


class RefinedEntityLinkingWorkerError(EntityLinkingRuntimeResponseError):
    def __init__(
        self,
        failure: str,
        diagnostics: tuple[str, ...],
        raw_output: bytes,
    ) -> None:
        self.failure = failure
        self.diagnostics = diagnostics
        super().__init__(
            f"ReFinED worker failed with {failure}: {'; '.join(diagnostics)}",
            raw_output,
        )


class RefinedEntityLinkingAdapter:
    """Map official ReFinED caller-span results into generic Application DTOs."""

    def __init__(
        self,
        config: RefinedEntityLinkingConfig,
        *,
        transport: RefinedWorkerTransport | None = None,
    ) -> None:
        self._config = config
        self._identity = _identity(config.timeout_seconds)
        self._transport = transport or SubprocessRefinedWorkerTransport(
            python_executable=config.python_executable,
            worker_script=config.worker_script,
            timeout_seconds=config.timeout_seconds,
        )

    @property
    def identity(self) -> EntityLinkerIdentity:
        return self._identity

    def link(self, request: EntityLinkingInput) -> EntityLinkingExecution:
        exchange = self._transport.request(_request_payload(request, self._config, self.identity))
        payload_bytes = _canonical_json(exchange.payload)
        try:
            return _parse_execution(
                payload_bytes,
                exchange.raw_output,
                self.identity,
                request,
            )
        except RefinedEntityLinkingWorkerError:
            raise
        except Exception as error:
            self._transport.discard()
            raise EntityLinkingOutputError(str(error), exchange.raw_output) from error

    def close(self) -> None:
        self._transport.close()


def _parse_execution(
    payload_bytes: bytes,
    raw_output: bytes,
    expected_identity: EntityLinkerIdentity,
    request: EntityLinkingInput,
) -> EntityLinkingExecution:
    response = _decode_canonical_response(payload_bytes)
    if response.get("schema_version") != "refined_entity_linking_response_v1":
        raise ValueError("ReFinED entity-linking response schema is unsupported.")
    if response.get("status") != "completed":
        _require_fields("failure response", response, _FAILURE_FIELDS)
        diagnostics = response["diagnostics"]
        if not isinstance(diagnostics, list):
            raise ValueError("ReFinED failure diagnostics must be non-empty strings.")
        diagnostic_items = cast(list[object], diagnostics)
        if not all(isinstance(item, str) and item for item in diagnostic_items):
            raise ValueError("ReFinED failure diagnostics must be non-empty strings.")
        raise RefinedEntityLinkingWorkerError(
            _string(response, "failure"),
            tuple(cast(str, item) for item in diagnostic_items),
            raw_output,
        )
    _require_fields("response", response, _RESPONSE_FIELDS)
    identity = EntityLinkerIdentity.model_validate(response["identity"])
    if identity != expected_identity:
        raise ValueError("ReFinED response identity drifted from pinned configuration.")
    evidence_values = response["evidences"]
    if not isinstance(evidence_values, list):
        raise ValueError("ReFinED entity-link evidences must be a list.")
    evidence_items = cast(list[object], evidence_values)
    batch = EntityLinkingBatch(
        identity=identity,
        load_elapsed_ms=_integer(response, "load_elapsed_ms"),
        inference_elapsed_ms=_integer(response, "inference_elapsed_ms"),
        evidences=tuple(_parse_evidence(item) for item in evidence_items),
    )
    _validate_alignment(request, batch)
    return EntityLinkingExecution(batch=batch, raw_output=raw_output)


def _identity(timeout_seconds: float) -> EntityLinkerIdentity:
    return EntityLinkerIdentity(
        producer_id="refined:1.0",
        model_id=REFINED_MODEL_ID,
        model_revision=REFINED_MODEL_REVISION,
        entity_set=REFINED_ENTITY_SET,
        package_revision=REFINED_PACKAGE_REVISION,
        resource_manifest_sha256=REFINED_RESOURCE_MANIFEST_SHA256,
        runtime_identity=REFINED_RUNTIME_IDENTITY,
        timeout_seconds=timeout_seconds,
    )


def _request_payload(
    request: EntityLinkingInput,
    config: RefinedEntityLinkingConfig,
    identity: EntityLinkerIdentity,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "refined_entity_linking_request_v1",
        "source_segment_id": request.source_segment_id,
        "source_text_sha256": request.source_text_sha256,
        "source_text": request.source_text,
        "identity": identity.model_dump(mode="json"),
        "data_dir": str(config.data_dir),
        "download_files": False,
        "options": {
            "apply_class_check": False,
            "prune_ner_types": True,
            "return_special_spans": False,
        },
        "mentions": [item.model_dump(mode="json") for item in request.mentions],
    }
    if set(payload) != _REQUEST_FIELDS:
        raise AssertionError("ReFinED entity-link request contract drifted.")
    return payload


def _parse_evidence(value: object) -> EntityLinkerEvidence:
    evidence = _mapping("evidence", value)
    _require_fields("evidence", evidence, _EVIDENCE_FIELDS)
    candidate_values = evidence["candidates"]
    if not isinstance(candidate_values, list):
        raise ValueError("ReFinED ranked candidates must be a list.")
    candidate_items = cast(list[object], candidate_values)
    return EntityLinkerEvidence(
        candidate_id=_string(evidence, "candidate_id"),
        returned_text=_string(evidence, "returned_text"),
        start=_integer(evidence, "start"),
        end=_integer(evidence, "end"),
        candidates=tuple(_parse_candidate(item) for item in candidate_items),
    )


def _parse_candidate(value: object) -> EntityLinkCandidate:
    candidate = _mapping("candidate", value)
    _require_fields("candidate", candidate, _CANDIDATE_FIELDS)
    wikidata_id = _optional_string(candidate, "wikidata_id")
    title_identity = _optional_string(candidate, "wikipedia_title_wikidata_id")
    if title_identity != wikidata_id:
        raise ValueError("ReFinED Wikipedia title was not looked up by its candidate Wikidata ID.")
    return EntityLinkCandidate(
        rank=_integer(candidate, "rank"),
        kind=EntityLinkCandidateKind(_string(candidate, "kind")),
        wikidata_id=wikidata_id,
        wikipedia_title=_optional_string(candidate, "wikipedia_title"),
        label=_optional_string(candidate, "label"),
        score=_number(candidate, "score"),
    )


def _validate_alignment(request: EntityLinkingInput, batch: EntityLinkingBatch) -> None:
    if len(batch.evidences) != len(request.mentions):
        raise ValueError("ReFinED evidence must match every ordered input mention.")
    for mention, evidence in zip(request.mentions, batch.evidences, strict=True):
        if evidence.candidate_id != mention.candidate_id:
            raise ValueError("ReFinED evidence must match ordered input mentions.")
        if (
            evidence.returned_text != mention.text
            or evidence.start != mention.start
            or evidence.end != mention.end
            or request.source_text[evidence.start : evidence.end] != evidence.returned_text
        ):
            raise ValueError("ReFinED evidence does not match authoritative source characters.")


def _decode_canonical_response(raw_output: bytes) -> dict[str, object]:
    try:
        value: object = json.loads(raw_output)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("ReFinED entity-linking worker returned malformed JSON.") from error
    response = _mapping("response", value)
    if _canonical_json(response) != raw_output:
        raise ValueError("ReFinED entity-linking response is not canonical JSON.")
    return response


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _mapping(label: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"ReFinED {label} must be an object.")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"ReFinED {label} keys must be strings.")
    return {cast(str, key): item for key, item in raw.items()}


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
    if item is not None and (not isinstance(item, str) or not item):
        raise ValueError(f"ReFinED {key} must be a non-empty string or null.")
    return item


def _integer(value: dict[str, object], key: str) -> int:
    item = value[key]
    if type(item) is not int:
        raise ValueError(f"ReFinED {key} must be an integer.")
    return item


def _number(value: dict[str, object], key: str) -> float:
    item = value[key]
    if not isinstance(item, (int, float)) or isinstance(item, bool):
        raise ValueError(f"ReFinED {key} must be numeric.")
    return float(item)
