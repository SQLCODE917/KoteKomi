"""Ollama implementation of the Application embedding Port."""

from __future__ import annotations

import math
from typing import cast

from kotekomi_application import (
    DocumentRetrievalError,
    EmbeddingBatch,
    EmbeddingProfile,
    RetrievalFailureCode,
    embedding_profile_configuration_digest,
)
from kotekomi_domain import EmbeddingModelIdentity

from kotekomi_adapters.lm_studio_embeddings import validate_embedding_profile
from kotekomi_adapters.model_http import (
    JsonHttpClient,
    UrllibJsonHttpClient,
    error_message,
    parse_json_object,
    required_list,
)

ADAPTER_NAME = "ollama"


class OllamaEmbeddingAdapter:
    def __init__(self, http_client: JsonHttpClient | None = None) -> None:
        self._http_client = http_client or UrllibJsonHttpClient()

    def embed(self, profile: EmbeddingProfile, inputs: tuple[str, ...]) -> EmbeddingBatch:
        validate_embedding_profile(profile, ADAPTER_NAME)
        response = self._http_client.request(
            method="POST",
            url=f"{profile.endpoint.rstrip('/')}/api/embed",
            payload={"model": profile.model_id, "input": list(inputs)},
            timeout_seconds=profile.timeout_seconds,
        )
        if response.status_code != 200:
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                "Ollama embeddings returned HTTP "
                f"{response.status_code}: {error_message(response.body)}",
            )
        payload = parse_json_object(response.body, "Ollama embeddings")
        vectors = _vectors(payload)
        if len(vectors) != len(inputs):
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                "Ollama returned a vector count different from the input count.",
            )
        return EmbeddingBatch(
            model_identity=EmbeddingModelIdentity(
                adapter_id=ADAPTER_NAME,
                model_id=profile.model_id,
                model_digest=profile.model_digest,
                vector_dimension=profile.expected_vector_dimension,
                configuration_digest=embedding_profile_configuration_digest(profile),
            ),
            vectors=vectors,
        )


def _vectors(payload: dict[str, object]) -> tuple[tuple[float, ...], ...]:
    values = required_list(payload, "embeddings", "Ollama embeddings")
    result: list[tuple[float, ...]] = []
    for raw_value in values:
        if not isinstance(raw_value, list) or not raw_value:
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                "Ollama embeddings must contain non-empty vectors.",
            )
        raw = cast(list[object], raw_value)
        vector = tuple(
            float(value)
            for value in raw
            if isinstance(value, int | float) and not isinstance(value, bool)
        )
        if len(vector) != len(raw) or not all(math.isfinite(value) for value in vector):
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                "Ollama embeddings must contain finite numeric values.",
            )
        result.append(vector)
    return tuple(result)
