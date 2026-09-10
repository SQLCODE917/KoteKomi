"""Pinned, offline F-Coref Adapter returning source-character clusters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from kotekomi_application import (
    CoreferenceExecution,
    CoreferenceInput,
    CoreferenceSpanProposal,
)

from .correlated_worker_transport import (
    CorrelatedWorkerTransport,
    SubprocessCorrelatedWorkerTransport,
)

FCOREF_MODEL_ID = "biu-nlp/f-coref"
FCOREF_MODEL_REVISION = "e91dfff12879495d882ba9460d0c5d5dd44ade59"
FCOREF_PACKAGE_REVISION = "ae224139196d122b225af5a7e73b5fc0b6e1076d"
FCOREF_RUNTIME_IDENTITY = "isolated:fcoref-worker-exchange-v1"
FCOREF_TOKENIZER_ID = f"{FCOREF_MODEL_ID}@{FCOREF_MODEL_REVISION}"

_RESPONSE_FIELDS = {
    "schema_version",
    "status",
    "model_id",
    "model_revision",
    "package_revision",
    "resource_identity",
    "elapsed_milliseconds",
    "clusters",
}


class _Predictor(Protocol):
    def __call__(self, text: str) -> tuple[tuple[tuple[int, int], ...], ...]: ...


@dataclass(frozen=True)
class FCorefConfig:
    python_executable: Path
    worker_script: Path
    model_directory: Path
    resource_identity: str
    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        for label, path in (
            ("Python executable", self.python_executable),
            ("worker script", self.worker_script),
            ("model directory", self.model_directory),
        ):
            if not path.is_absolute():
                raise ValueError(f"F-Coref {label} path must be absolute.")
        if not self.resource_identity:
            raise ValueError("F-Coref resource identity must be non-empty.")
        if self.timeout_seconds <= 0:
            raise ValueError("F-Coref timeout must be positive.")


class FCorefAdapter:
    """Translate one isolated F-Coref worker into Application Port results."""

    tokenizer_id = FCOREF_TOKENIZER_ID

    def __init__(
        self,
        config: FCorefConfig,
        *,
        transport: CorrelatedWorkerTransport | None = None,
        predictor: _Predictor | None = None,
    ) -> None:
        self._config = config
        self._predictor = predictor
        self._transport = transport
        if transport is None and predictor is None:
            self._transport = SubprocessCorrelatedWorkerTransport(
                python_executable=config.python_executable,
                worker_script=config.worker_script,
                timeout_seconds=config.timeout_seconds,
            )

    def count_tokens(self, rendered_input: bytes) -> int:
        """Measure the exact worker input with the pinned F-Coref tokenizer."""
        try:
            text = rendered_input.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("F-Coref tokenizer input must be UTF-8.") from error
        if self._predictor is not None:
            return max(1, len(text.split()))
        response, _raw = self._request({"task": "count_tokens", "source_text": text})
        _raise_worker_failure(response)
        if set(response) != {"schema_version", "status", "token_count", "tokenizer_id"}:
            raise RuntimeError("F-Coref token-count response shape drifted.")
        if response["schema_version"] != "fcoref_token_count_response_v1":
            raise RuntimeError("F-Coref token-count response schema is unsupported.")
        if response["status"] != "completed" or response["tokenizer_id"] != self.tokenizer_id:
            raise RuntimeError("F-Coref token-count response identity drifted.")
        value = response["token_count"]
        if type(value) is not int or value < 1:
            raise RuntimeError("F-Coref token-count response is invalid.")
        return value

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        if self._predictor is not None:
            clusters = self._predictor(request.source_text)
            raw_output = _canonical_json(
                {"clusters": [[[start, end] for start, end in cluster] for cluster in clusters]}
            )
            return CoreferenceExecution(
                model_id=FCOREF_MODEL_ID,
                model_revision=FCOREF_MODEL_REVISION,
                resource_identity=self._config.resource_identity,
                clusters=tuple(
                    tuple(CoreferenceSpanProposal(start, end) for start, end in cluster)
                    for cluster in clusters
                ),
                elapsed_milliseconds=0,
                raw_output=raw_output,
            )
        response, raw_output = self._request(
            {
                "task": "propose",
                "source_segment_id": request.source_segment_id,
                "source_text": request.source_text,
                "source_text_sha256": hashlib.sha256(request.source_text.encode()).hexdigest(),
                "max_input_tokens": request.max_input_tokens,
            }
        )
        _raise_worker_failure(response)
        if set(response) != _RESPONSE_FIELDS:
            raise RuntimeError("F-Coref response shape drifted.")
        if response["schema_version"] != "fcoref_response_v1" or response["status"] != "completed":
            raise RuntimeError("F-Coref worker did not complete its request.")
        if (
            response["model_id"] != FCOREF_MODEL_ID
            or response["model_revision"] != FCOREF_MODEL_REVISION
            or response["package_revision"] != FCOREF_PACKAGE_REVISION
            or response["resource_identity"] != self._config.resource_identity
        ):
            raise RuntimeError("F-Coref response identity drifted from pinned configuration.")
        elapsed = response["elapsed_milliseconds"]
        if type(elapsed) is not int or elapsed < 0:
            raise RuntimeError("F-Coref response elapsed time is invalid.")
        clusters = _parse_clusters(response["clusters"])
        return CoreferenceExecution(
            model_id=FCOREF_MODEL_ID,
            model_revision=FCOREF_MODEL_REVISION,
            resource_identity=self._config.resource_identity,
            clusters=clusters,
            elapsed_milliseconds=elapsed,
            raw_output=raw_output,
        )

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()

    def _request(self, payload: dict[str, object]) -> tuple[dict[str, object], bytes]:
        if self._transport is None:
            raise RuntimeError("F-Coref worker transport is unavailable.")
        request = {
            "schema_version": "fcoref_request_v1",
            "model_directory": str(self._config.model_directory),
            "resource_identity": self._config.resource_identity,
            **payload,
        }
        exchange = self._transport.request(request)
        return exchange.payload, exchange.raw_output


def _parse_clusters(value: object) -> tuple[tuple[CoreferenceSpanProposal, ...], ...]:
    if not isinstance(value, list):
        raise RuntimeError("F-Coref clusters must be a list.")
    clusters: list[tuple[CoreferenceSpanProposal, ...]] = []
    for cluster_value in cast(list[object], value):
        if not isinstance(cluster_value, list):
            raise RuntimeError("F-Coref cluster must be a list.")
        cluster: list[CoreferenceSpanProposal] = []
        for span_value in cast(list[object], cluster_value):
            span_items = cast(list[object], span_value) if isinstance(span_value, list) else []
            if len(span_items) != 2 or any(type(item) is not int for item in span_items):
                raise RuntimeError("F-Coref span must contain two integer offsets.")
            start, end = cast(list[int], span_items)
            cluster.append(CoreferenceSpanProposal(start, end))
        clusters.append(tuple(cluster))
    return tuple(clusters)


def _raise_worker_failure(response: dict[str, object]) -> None:
    if response.get("schema_version") != "fcoref_failure_v1":
        return
    if set(response) != {"schema_version", "status", "failure", "diagnostics"}:
        raise RuntimeError("F-Coref failure response shape drifted.")
    failure = response["failure"]
    diagnostics = response["diagnostics"]
    if not isinstance(diagnostics, list):
        raise RuntimeError("F-Coref failure response is invalid.")
    diagnostic_items = cast(list[object], diagnostics)
    if (
        response["status"] != "blocked"
        or not isinstance(failure, str)
        or not failure
        or not all(isinstance(item, str) for item in diagnostic_items)
    ):
        raise RuntimeError("F-Coref failure response is invalid.")
    detail = "; ".join(cast(list[str], diagnostic_items))
    raise RuntimeError(f"F-Coref worker blocked ({failure}): {detail}")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
