"""Pinned offline ReFinED worker for HP-3 caller-owned entity-link spans.

Standard output is reserved for canonical JSON lines. ReFinED diagnostics are
redirected to standard error. The worker does not download resources.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import os
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
REFINED_RUNTIME_IDENTITY = "isolated:refined-v1"

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
_MENTION_FIELDS = {"candidate_id", "text", "start", "end"}
_OPTIONS = {
    "apply_class_check": False,
    "prune_ner_types": True,
    "return_special_spans": False,
}

_processor: Any | None = None
_processor_data_dir: Path | None = None
_load_elapsed_ms: int | None = None


class WorkerFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def main() -> int:
    for line in sys.stdin:
        try:
            response = process_request(json.loads(line))
        except Exception as error:  # noqa: BLE001 - isolated external boundary
            response = _failure_response(error)
        sys.stdout.write(_canonical_json(response) + "\n")
        sys.stdout.flush()
    return 0


def process_request(value: object) -> dict[str, object]:
    request = _mapping("request", value)
    _require_fields("request", request, _REQUEST_FIELDS)
    if request["schema_version"] != "refined_entity_linking_request_v1":
        raise WorkerFailure("unsupported_protocol", "Worker request schema is unsupported.")
    identity = _mapping("identity", request["identity"])
    _require_identity(identity)
    if request["download_files"] is not False:
        raise WorkerFailure("network_not_disabled", "Entity linking must disable downloads.")
    if request["options"] != _OPTIONS:
        raise WorkerFailure("option_drift", "ReFinED caller-span options are not pinned.")
    source_text = _string(request, "source_text")
    source_digest = _string(request, "source_text_sha256")
    if hashlib.sha256(source_text.encode()).hexdigest() != source_digest:
        raise WorkerFailure("source_drift", "Source text digest does not match request text.")
    raw_mentions = request["mentions"]
    if not isinstance(raw_mentions, list):
        raise WorkerFailure("invalid_request", "Worker mentions must be a list.")
    mention_items = cast(list[object], raw_mentions)
    mentions = tuple(_mention(item, source_text) for item in mention_items)
    if tuple(sorted(mentions, key=lambda item: (item[2], item[3], item[0]))) != mentions:
        raise WorkerFailure("invalid_request", "Worker mentions must use source order.")
    if len({item[0] for item in mentions}) != len(mentions):
        raise WorkerFailure("invalid_request", "Worker mention identities must be unique.")

    processor = _load_processor(Path(_string(request, "data_dir")))
    span_type = cast(Any, importlib.import_module("refined.data_types.base_types")).Span
    spans = [span_type(text, start, end - start) for _, text, start, end in mentions]
    started = time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):
        returned = processor.process_text(
            source_text,
            spans=spans,
            apply_class_check=False,
            prune_ner_types=True,
            return_special_spans=False,
        )
    inference_elapsed_ms = round((time.monotonic() - started) * 1000)
    if len(returned) != len(mentions):
        raise WorkerFailure(
            "span_alignment_failure", "ReFinED did not return every caller-owned span."
        )
    evidences: list[dict[str, object]] = []
    for mention, span in zip(mentions, returned, strict=True):
        candidate_id, text, start, end = mention
        if span.text != text or span.start != start or span.start + span.ln != end:
            raise WorkerFailure(
                "span_alignment_failure", "ReFinED changed or reordered a caller-owned span."
            )
        evidences.append(_evidence(processor, candidate_id, span))
    assert _load_elapsed_ms is not None
    return {
        "schema_version": "refined_entity_linking_response_v1",
        "status": "completed",
        "identity": identity,
        "load_elapsed_ms": _load_elapsed_ms,
        "inference_elapsed_ms": inference_elapsed_ms,
        "evidences": evidences,
    }


def _load_processor(data_dir: Path) -> Any:
    global _load_elapsed_ms, _processor, _processor_data_dir
    if _processor is not None:
        if data_dir != _processor_data_dir:
            raise WorkerFailure(
                "resource_identity_conflict", "A running worker cannot change resource directories."
            )
        return _processor
    if not data_dir.is_dir():
        raise WorkerFailure("resources_unavailable", "Pinned ReFinED resources are unavailable.")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        version = importlib.metadata.version("ReFinED")
    except importlib.metadata.PackageNotFoundError as error:
        raise WorkerFailure("runtime_unavailable", "ReFinED is not installed.") from error
    if version != REFINED_PACKAGE_VERSION:
        raise WorkerFailure("runtime_identity_drift", f"Expected ReFinED 1.0; found {version}.")
    refined = cast(Any, importlib.import_module("refined.inference.processor")).Refined
    started = time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):
        processor = refined.from_pretrained(
            model_name=REFINED_MODEL_ID,
            entity_set=REFINED_ENTITY_SET,
            data_dir=str(data_dir),
            device="cpu",
            use_precomputed_descriptions=True,
            download_files=False,
            return_titles=True,
        )
    if resource_tree_digest(data_dir) != REFINED_RESOURCE_MANIFEST_SHA256:
        raise WorkerFailure(
            "resource_identity_drift", "ReFinED resources do not match the pinned manifest."
        )
    _load_elapsed_ms = round((time.monotonic() - started) * 1000)
    _processor = processor
    _processor_data_dir = data_dir
    return processor


def _evidence(processor: Any, candidate_id: str, span: Any) -> dict[str, object]:
    ranked: list[tuple[Any | None, float]] = list(span.top_k_predicted_entities or ())
    predicted_id = (
        None if span.predicted_entity is None else span.predicted_entity.wikidata_entity_id
    )
    has_ranked_nil = any(
        entity is None or entity.wikidata_entity_id in {None, "Q0"} for entity, _score in ranked
    )
    if predicted_id in {None, "Q0"} and not has_ranked_nil:
        ranked.append((None, float(span.entity_linking_model_confidence_score or 0.0)))
        ranked.sort(key=lambda item: item[1], reverse=True)
    candidates = [
        _ranked_candidate(processor, rank, entity, float(score))
        for rank, (entity, score) in enumerate(ranked, start=1)
    ]
    return {
        "candidate_id": candidate_id,
        "returned_text": span.text,
        "start": span.start,
        "end": span.start + span.ln,
        "candidates": candidates,
    }


def _ranked_candidate(
    processor: Any, rank: int, entity: Any | None, score: float
) -> dict[str, object]:
    if entity is None or entity.wikidata_entity_id in {None, "Q0"}:
        return {
            "rank": rank,
            "kind": "nil",
            "wikidata_id": None,
            "wikipedia_title": None,
            "wikipedia_title_wikidata_id": None,
            "label": None,
            "score": score,
        }
    wikidata_id = str(entity.wikidata_entity_id)
    title_lookup = processor.preprocessor.qcode_to_wiki
    title = None if title_lookup is None else title_lookup.get(wikidata_id)
    return {
        "rank": rank,
        "kind": "knowledge_base_entity",
        "wikidata_id": wikidata_id,
        "wikipedia_title": title,
        "wikipedia_title_wikidata_id": wikidata_id,
        "label": entity.human_readable_name or entity.parsed_string,
        "score": score,
    }


def resource_tree_digest(data_dir: Path) -> str:
    files = tuple(sorted(path for path in data_dir.rglob("*") if path.is_file()))
    if not files:
        raise WorkerFailure("resources_unavailable", "ReFinED resource directory is empty.")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(data_dir).as_posix().encode()
        file_digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                file_digest.update(block)
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_digest.hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _require_identity(identity: dict[str, object]) -> None:
    expected = {
        "producer_id": "refined:1.0",
        "model_id": REFINED_MODEL_ID,
        "model_revision": REFINED_MODEL_REVISION,
        "entity_set": REFINED_ENTITY_SET,
        "package_revision": REFINED_PACKAGE_REVISION,
        "resource_manifest_sha256": REFINED_RESOURCE_MANIFEST_SHA256,
        "runtime_identity": REFINED_RUNTIME_IDENTITY,
        "timeout_seconds": identity.get("timeout_seconds"),
    }
    if identity != expected or not isinstance(identity.get("timeout_seconds"), (int, float)):
        raise WorkerFailure("runtime_identity_drift", "Worker identity is not pinned.")


def _mention(value: object, source_text: str) -> tuple[str, str, int, int]:
    mention = _mapping("mention", value)
    _require_fields("mention", mention, _MENTION_FIELDS)
    candidate_id = _string(mention, "candidate_id")
    text = _string(mention, "text")
    start = _integer(mention, "start")
    end = _integer(mention, "end")
    if start < 0 or end <= start or end > len(source_text) or source_text[start:end] != text:
        raise WorkerFailure("source_drift", "Mention does not match source characters.")
    return candidate_id, text, start, end


def _failure_response(error: Exception) -> dict[str, object]:
    if isinstance(error, WorkerFailure):
        code, message = error.code, str(error)
    else:
        code, message = "worker_failure", f"{type(error).__name__}: {error}"
    return {
        "schema_version": "refined_entity_linking_response_v1",
        "status": "blocked",
        "failure": code,
        "diagnostics": [message],
    }


def _mapping(label: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise WorkerFailure("invalid_request", f"Worker {label} must be an object.")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise WorkerFailure("invalid_request", f"Worker {label} keys must be strings.")
    return {cast(str, key): item for key, item in raw.items()}


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
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


if __name__ == "__main__":
    raise SystemExit(main())
