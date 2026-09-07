"""Pinned offline F-Coref worker for bounded source-span observations.

Standard output is reserved for canonical correlated JSON lines. Dependency
diagnostics go to standard error. Normal execution never downloads resources.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, cast

FCOREF_MODEL_ID = "biu-nlp/f-coref"
FCOREF_MODEL_REVISION = "e91dfff12879495d882ba9460d0c5d5dd44ade59"
FCOREF_PACKAGE_REVISION = "ae224139196d122b225af5a7e73b5fc0b6e1076d"
FCOREF_TOKENIZER_ID = f"{FCOREF_MODEL_ID}@{FCOREF_MODEL_REVISION}"
EXCHANGE_SCHEMA_VERSION = "model_worker_exchange_v1"
_REQUEST_ID_PATTERN = re.compile(r"^rwr_[a-f0-9]{32}$")
_UNCORRELATED_REQUEST_ID = "rwr_00000000000000000000000000000000"

_model: Any | None = None
_tokenizer: Any | None = None
_model_directory: Path | None = None


class WorkerFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def main() -> int:
    _configure_offline_runtime()
    for line in sys.stdin:
        request_id = _UNCORRELATED_REQUEST_ID
        try:
            request_id, request = _parse_exchange(json.loads(line))
            response = process_request(request)
        except Exception as error:  # noqa: BLE001 - isolated dependency boundary
            response = _failure_response(error)
        sys.stdout.write(_canonical_json(_exchange(request_id, response)) + "\n")
        sys.stdout.flush()
    return 0


def process_request(value: object) -> dict[str, object]:
    request = _mapping("request", value)
    if request.get("schema_version") != "fcoref_request_v1":
        raise WorkerFailure("unsupported_protocol", "F-Coref request schema is unsupported.")
    model_directory = Path(_string(request, "model_directory"))
    resource_identity = _string(request, "resource_identity")
    if not model_directory.is_absolute() or not model_directory.is_dir():
        raise WorkerFailure("resources_unavailable", "Pinned F-Coref resources are unavailable.")
    task = _string(request, "task")
    if task == "count_tokens":
        tokenizer = _load_tokenizer(model_directory)
        source_text = _string(request, "source_text")
        token_count = len(tokenizer.encode(source_text, add_special_tokens=True))
        return {
            "schema_version": "fcoref_token_count_response_v1",
            "status": "completed",
            "token_count": token_count,
            "tokenizer_id": FCOREF_TOKENIZER_ID,
        }
    if task != "propose":
        raise WorkerFailure("invalid_task", "F-Coref task is unsupported.")
    source_text = _string(request, "source_text")
    if hashlib.sha256(source_text.encode()).hexdigest() != _string(request, "source_text_sha256"):
        raise WorkerFailure("source_drift", "F-Coref source digest does not match its text.")
    max_input_tokens = _integer(request, "max_input_tokens")
    if len(_load_tokenizer(model_directory).encode(source_text, add_special_tokens=True)) > (
        max_input_tokens
    ):
        raise WorkerFailure("input_too_large", "F-Coref input exceeds its declared token limit.")
    model = _load_model(model_directory)
    started = time.monotonic()
    with contextlib.redirect_stdout(sys.stderr):
        results = model.predict(texts=[source_text], max_tokens_in_batch=max_input_tokens)
    if len(results) != 1:
        raise WorkerFailure("invalid_output", "F-Coref returned an unexpected result count.")
    result = results[0]
    clusters = result.get_clusters(as_strings=False)
    result.release_logits()
    normalized = _clusters(clusters, source_text)
    return {
        "schema_version": "fcoref_response_v1",
        "status": "completed",
        "model_id": FCOREF_MODEL_ID,
        "model_revision": FCOREF_MODEL_REVISION,
        "package_revision": FCOREF_PACKAGE_REVISION,
        "resource_identity": resource_identity,
        "elapsed_milliseconds": round((time.monotonic() - started) * 1000),
        "clusters": normalized,
    }


def _load_tokenizer(model_directory: Path) -> Any:
    global _tokenizer, _model_directory
    if _tokenizer is not None:
        _require_same_directory(model_directory)
        return _tokenizer
    transformers = importlib.import_module("transformers")
    with contextlib.redirect_stdout(sys.stderr):
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            str(model_directory), local_files_only=True
        )
    _tokenizer = tokenizer
    _model_directory = model_directory
    return tokenizer


def _load_model(model_directory: Path) -> Any:
    global _model, _model_directory
    if _model is not None:
        _require_same_directory(model_directory)
        return _model
    fastcoref = importlib.import_module("fastcoref")
    with contextlib.redirect_stdout(sys.stderr):
        model = fastcoref.FCoref(model_name_or_path=str(model_directory), device="cpu")
    _model = model
    _model_directory = model_directory
    return model


def _require_same_directory(model_directory: Path) -> None:
    if model_directory != _model_directory:
        raise WorkerFailure(
            "resource_identity_conflict", "A running F-Coref worker cannot change resources."
        )


def _clusters(value: object, source_text: str) -> list[list[list[int]]]:
    if not isinstance(value, list):
        raise WorkerFailure("invalid_output", "F-Coref clusters must be a list.")
    normalized: list[list[list[int]]] = []
    for raw_cluster in cast(list[object], value):
        if not isinstance(raw_cluster, list):
            raise WorkerFailure("invalid_output", "F-Coref cluster must be a list.")
        cluster: list[list[int]] = []
        for raw_span in cast(list[object], raw_cluster):
            span_items = (
                cast(list[object] | tuple[object, ...], raw_span)
                if isinstance(raw_span, (tuple, list))
                else ()
            )
            if len(span_items) != 2 or any(type(item) is not int for item in span_items):
                raise WorkerFailure("invalid_output", "F-Coref span offsets are invalid.")
            start, end = cast(tuple[int, int] | list[int], span_items)
            if not (0 <= start < end <= len(source_text)):
                raise WorkerFailure("invalid_output", "F-Coref span lies outside source text.")
            cluster.append([start, end])
        normalized.append(cluster)
    return normalized


def _parse_exchange(value: object) -> tuple[str, dict[str, object]]:
    exchange = _mapping("exchange", value)
    if set(exchange) != {"schema_version", "request_id", "payload"}:
        raise WorkerFailure("invalid_request", "Worker exchange shape is invalid.")
    if exchange["schema_version"] != EXCHANGE_SCHEMA_VERSION:
        raise WorkerFailure("unsupported_protocol", "Worker exchange schema is unsupported.")
    request_id = _string(exchange, "request_id")
    if _REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise WorkerFailure("invalid_request", "Worker request ID is invalid.")
    return request_id, _mapping("payload", exchange["payload"])


def _exchange(request_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": EXCHANGE_SCHEMA_VERSION,
        "request_id": request_id,
        "payload": payload,
    }


def _failure_response(error: Exception) -> dict[str, object]:
    return {
        "schema_version": "fcoref_failure_v1",
        "status": "blocked",
        "failure": error.code if isinstance(error, WorkerFailure) else "worker_error",
        "diagnostics": [str(error)],
    }


def _mapping(label: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise WorkerFailure("invalid_request", f"F-Coref {label} must be an object.")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise WorkerFailure("invalid_request", f"F-Coref {label} keys must be strings.")
    return {cast(str, key): item for key, item in raw.items()}


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise WorkerFailure("invalid_request", f"F-Coref {key} must be a non-empty string.")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if type(value) is not int or value <= 0:
        raise WorkerFailure("invalid_request", f"F-Coref {key} must be a positive integer.")
    return value


def _configure_offline_runtime() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"


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
