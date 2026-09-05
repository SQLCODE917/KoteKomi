"""Isolated ReFinED V1 worker for caller-supplied source spans.

This file intentionally depends only on the standard library until a request loads
the separately installed ReFinED environment. Standard output is reserved for the
line-delimited JSON protocol; runtime diagnostics go to standard error.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, cast

REFINED_PACKAGE_REVISION = "7c98036f72c39a8d6d2c097bbde89ea3731901f0"
REFINED_MODEL_ID = "wikipedia_model"
REFINED_MODEL_REVISION = "refined-v1-wikipedia-model"
REFINED_ENTITY_SET = "wikipedia"
REFINED_PACKAGE_VERSION = "1.0"
REFINED_RESOURCE_MANIFEST_SHA256 = (
    "75ca7833e4fbcc94bf05b129c591d7656900f1f61edb55cdb0b20f2d6518094b"
)
EXCHANGE_SCHEMA_VERSION = "refined_worker_exchange_v1"
_EXCHANGE_FIELDS = {"schema_version", "request_id", "payload"}
_REQUEST_ID_PATTERN = re.compile(r"^rwr_[a-f0-9]{32}$")
_UNCORRELATED_REQUEST_ID = "rwr_00000000000000000000000000000000"

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
_CANDIDATE_FIELDS = {"candidate_id", "text", "start", "end"}

_processor: Any | None = None
_processor_data_dir: Path | None = None
_resource_manifest_sha256: str | None = None
_load_elapsed_ms: int | None = None


def main() -> int:
    """Serve strict requests until standard input closes."""
    for line in sys.stdin:
        request_id = _UNCORRELATED_REQUEST_ID
        try:
            request_id, payload = _exchange_request(json.loads(line))
            response = process_request(payload)
        except Exception as error:  # noqa: BLE001 - external worker boundary
            response = _failure_response(error)
        sys.stdout.write(_canonical_json(_exchange_response(request_id, response)) + "\n")
        sys.stdout.flush()
    return 0


def _exchange_request(value: object) -> tuple[str, dict[str, object]]:
    exchange = _mapping("exchange", value)
    _require_fields("exchange", exchange, _EXCHANGE_FIELDS)
    if exchange["schema_version"] != EXCHANGE_SCHEMA_VERSION:
        raise WorkerFailure("unsupported_protocol", "Worker exchange schema is unsupported.")
    request_id = _string(exchange, "request_id")
    if _REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise WorkerFailure("invalid_request", "WorkerRequestId is invalid.")
    return request_id, _mapping("payload", exchange["payload"])


def _exchange_response(request_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": EXCHANGE_SCHEMA_VERSION,
        "request_id": request_id,
        "payload": payload,
    }


def process_request(value: object) -> dict[str, object]:
    """Validate one request, run official predetermined-span mode, and normalize output."""
    request = _mapping("request", value)
    _require_fields("request", request, _REQUEST_FIELDS)
    if request["schema_version"] != "refined_contextual_type_request_v1":
        raise WorkerFailure("unsupported_protocol", "Worker request schema is unsupported.")
    _require_identity(request)
    if request["download_files"] is not False:
        raise WorkerFailure("network_not_disabled", "Evaluation requests must disable downloads.")
    source_text = _string(request, "source_text")
    source_digest = _string(request, "source_text_sha256")
    if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != source_digest:
        raise WorkerFailure("source_drift", "Source text digest does not match request text.")
    candidates_value = request["candidates"]
    if not isinstance(candidates_value, list):
        raise WorkerFailure("invalid_request", "Worker candidates must be a list.")
    candidate_items = cast(list[object], candidates_value)
    candidates = tuple(_candidate(item, source_text) for item in candidate_items)
    if tuple(sorted(candidates, key=lambda item: (item[2], item[3], item[0]))) != candidates:
        raise WorkerFailure("invalid_request", "Worker candidates must be source ordered.")
    if len({candidate[0] for candidate in candidates}) != len(candidates):
        raise WorkerFailure("invalid_request", "Worker candidate identities must be unique.")
    data_dir = Path(_string(request, "data_dir"))
    processor = _load_processor(data_dir)
    span_type = cast(Any, importlib.import_module("refined.data_types.base_types")).Span

    supplied_spans = [span_type(text, start, end - start) for _, text, start, end in candidates]
    started = time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):
        returned_spans = processor.process_text(
            source_text,
            spans=supplied_spans,
            prune_ner_types=True,
            apply_class_check=True,
            return_special_spans=False,
        )
    inference_elapsed_ms = round((time.monotonic() - started) * 1000)
    if len(returned_spans) != len(candidates):
        raise WorkerFailure(
            "span_alignment_failure",
            "ReFinED did not return one result for every caller-supplied span.",
        )
    evidences: list[dict[str, object]] = []
    for candidate, span in zip(candidates, returned_spans, strict=True):
        candidate_id, text, start, end = candidate
        if span.text != text or span.start != start or span.start + span.ln != end:
            raise WorkerFailure(
                "span_alignment_failure",
                "ReFinED changed or reordered a caller-supplied span.",
            )
        evidences.append(_span_evidence(candidate_id, span))
    assert _resource_manifest_sha256 is not None
    assert _load_elapsed_ms is not None
    return {
        "schema_version": "refined_contextual_type_response_v1",
        "status": "completed",
        "producer_id": f"refined:{REFINED_PACKAGE_VERSION}",
        "model_id": REFINED_MODEL_ID,
        "model_revision": REFINED_MODEL_REVISION,
        "entity_set": REFINED_ENTITY_SET,
        "package_revision": REFINED_PACKAGE_REVISION,
        "resource_manifest_sha256": _resource_manifest_sha256,
        "load_elapsed_ms": _load_elapsed_ms,
        "inference_elapsed_ms": inference_elapsed_ms,
        "evidences": evidences,
    }


class WorkerFailure(RuntimeError):
    """Expected worker failure with a stable diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _load_processor(data_dir: Path) -> Any:
    global _load_elapsed_ms, _processor, _processor_data_dir, _resource_manifest_sha256
    if _processor is not None:
        if data_dir != _processor_data_dir:
            raise WorkerFailure(
                "resource_identity_conflict",
                "A running worker cannot switch ReFinED resource directories.",
            )
        return _processor
    if not data_dir.is_dir():
        raise WorkerFailure("resources_unavailable", "Pinned ReFinED resources are not installed.")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        installed_version = importlib.metadata.version("ReFinED")
    except importlib.metadata.PackageNotFoundError as error:
        raise WorkerFailure(
            "runtime_unavailable", "ReFinED is not installed in this worker."
        ) from error
    if installed_version != REFINED_PACKAGE_VERSION:
        raise WorkerFailure(
            "runtime_identity_drift",
            f"Expected ReFinED {REFINED_PACKAGE_VERSION}; found {installed_version}.",
        )
    refined_type = cast(Any, importlib.import_module("refined.inference.processor")).Refined

    started = time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):
        processor = refined_type.from_pretrained(
            model_name=REFINED_MODEL_ID,
            entity_set=REFINED_ENTITY_SET,
            data_dir=str(data_dir),
            device="cpu",
            use_precomputed_descriptions=True,
            download_files=False,
            return_titles=True,
        )
    resource_digest = resource_tree_digest(data_dir)
    if resource_digest != REFINED_RESOURCE_MANIFEST_SHA256:
        raise WorkerFailure(
            "resource_identity_drift",
            "ReFinED resource tree does not match the pinned manifest.",
        )
    _load_elapsed_ms = round((time.monotonic() - started) * 1000)
    _processor = processor
    _processor_data_dir = data_dir
    _resource_manifest_sha256 = resource_digest
    return processor


def resource_tree_digest(data_dir: Path) -> str:
    files = tuple(sorted(path for path in data_dir.rglob("*") if path.is_file()))
    if not files:
        raise WorkerFailure("resources_unavailable", "ReFinED resource directory is empty.")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(data_dir).as_posix().encode("utf-8")
        file_digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                file_digest.update(block)
        digest.update(relative)
        digest.update(b"\x00")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\x00")
        digest.update(file_digest.hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _span_evidence(candidate_id: str, span: Any) -> dict[str, object]:
    top_entities = [
        _entity(entity, score=float(score))
        for entity, score in (span.top_k_predicted_entities or ())
    ]
    type_predictions = [
        {"type_id": type_id, "type_label": type_label, "confidence": float(confidence)}
        for type_id, type_label, confidence in (span.predicted_entity_types or ())
    ]
    return {
        "candidate_id": candidate_id,
        "returned_text": span.text,
        "start": span.start,
        "end": span.start + span.ln,
        "coarse_type": span.coarse_type,
        "coarse_mention_type": span.coarse_mention_type,
        "predicted_entity": (
            None if span.predicted_entity is None else _entity(span.predicted_entity, score=None)
        ),
        "entity_linking_score": span.entity_linking_model_confidence_score,
        "top_k_entities": top_entities,
        "predicted_entity_types": type_predictions,
        "failed_class_check": span.failed_class_check,
    }


def _entity(entity: Any, *, score: float | None) -> dict[str, object]:
    return {
        "wikidata_entity_id": entity.wikidata_entity_id,
        "wikipedia_entity_title": entity.wikipedia_entity_title,
        "human_readable_name": entity.human_readable_name,
        "parsed_string": entity.parsed_string,
        "score": score,
    }


def _candidate(value: object, source_text: str) -> tuple[str, str, int, int]:
    candidate = _mapping("candidate", value)
    _require_fields("candidate", candidate, _CANDIDATE_FIELDS)
    candidate_id = _string(candidate, "candidate_id")
    text = _string(candidate, "text")
    start = _integer(candidate, "start")
    end = _integer(candidate, "end")
    if start < 0 or end <= start or end > len(source_text) or source_text[start:end] != text:
        raise WorkerFailure("source_drift", "Candidate does not match source characters.")
    return candidate_id, text, start, end


def _require_identity(request: dict[str, object]) -> None:
    actual = (
        request["model_id"],
        request["model_revision"],
        request["entity_set"],
        request["package_revision"],
    )
    expected = (
        REFINED_MODEL_ID,
        REFINED_MODEL_REVISION,
        REFINED_ENTITY_SET,
        REFINED_PACKAGE_REVISION,
    )
    if actual != expected:
        raise WorkerFailure("runtime_identity_drift", "Worker request identity is not pinned.")


def _failure_response(error: Exception) -> dict[str, object]:
    if isinstance(error, WorkerFailure):
        failure = error.code
        message = str(error)
    else:
        failure = "worker_failure"
        message = f"{type(error).__name__}: {error}"
    return {
        "schema_version": "refined_contextual_type_response_v1",
        "status": "blocked",
        "failure": failure,
        "diagnostics": [message],
    }


def _mapping(label: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise WorkerFailure("invalid_request", f"Worker {label} must be an object.")
    raw_mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_mapping):
        raise WorkerFailure("invalid_request", f"Worker {label} must use string keys.")
    return {cast(str, key): item for key, item in raw_mapping.items()}


def _require_fields(label: str, value: dict[str, object], fields: set[str]) -> None:
    if set(value) != fields:
        raise WorkerFailure("invalid_request", f"Worker {label} fields do not match protocol.")


def _string(value: dict[str, object], key: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item:
        raise WorkerFailure("invalid_request", f"Worker {key} must be a non-empty string.")
    return item


def _integer(value: dict[str, object], key: str) -> int:
    item = value[key]
    if type(item) is not int:
        raise WorkerFailure("invalid_request", f"Worker {key} must be an integer.")
    return item


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
