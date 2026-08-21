"""LM Studio implementation of the Application embedding Port."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import cast

from kotekomi_application import (
    DocumentRetrievalError,
    EmbeddingBatch,
    EmbeddingProfile,
    RetrievalFailureCode,
    embedding_profile_configuration_digest,
)
from kotekomi_domain import EmbeddingModelIdentity

from kotekomi_adapters.model_http import (
    JsonHttpClient,
    UrllibJsonHttpClient,
    error_message,
    parse_json_object,
    required_list,
)

ADAPTER_NAME = "lm_studio"


class LMStudioEmbeddingAdapter:
    """Translate OpenAI-compatible LM Studio embeddings to ordered Port results."""

    def __init__(self, http_client: JsonHttpClient | None = None) -> None:
        self._http_client = http_client or UrllibJsonHttpClient()

    def embed(self, profile: EmbeddingProfile, inputs: tuple[str, ...]) -> EmbeddingBatch:
        return embed_openai_compatible(
            profile,
            inputs,
            expected_adapter=ADAPTER_NAME,
            runtime_name="LM Studio",
            http_client=self._http_client,
        )


def embed_openai_compatible(
    profile: EmbeddingProfile,
    inputs: tuple[str, ...],
    *,
    expected_adapter: str,
    runtime_name: str,
    http_client: JsonHttpClient,
) -> EmbeddingBatch:
    validate_embedding_profile(profile, expected_adapter)
    if not inputs:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
            "Embedding input must not be empty.",
        )
    models = http_client.request(
        method="GET",
        url=f"{profile.endpoint.rstrip('/')}/models",
        payload=None,
        timeout_seconds=profile.timeout_seconds,
    )
    if models.status_code != 200:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_PROFILE_MISMATCH,
            f"{runtime_name} model list returned HTTP "
            f"{models.status_code}: {error_message(models.body)}",
        )
    if profile.model_id not in _model_ids(models.body, runtime_name):
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_PROFILE_MISMATCH,
            f"{runtime_name} does not have the requested embedding model: {profile.model_id}.",
        )
    response = http_client.request(
        method="POST",
        url=f"{profile.endpoint.rstrip('/')}/embeddings",
        payload={"model": profile.model_id, "input": list(inputs)},
        timeout_seconds=profile.timeout_seconds,
    )
    if response.status_code != 200:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
            f"{runtime_name} embeddings returned HTTP "
            f"{response.status_code}: {error_message(response.body)}",
        )
    payload = parse_json_object(response.body, f"{runtime_name} embeddings")
    response_model = payload.get("model")
    if response_model != profile.model_id:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_PROFILE_MISMATCH,
            f"{runtime_name} embedding response model does not match the selected profile.",
        )
    data = required_list(payload, "data", f"{runtime_name} embeddings")
    vectors: list[tuple[float, ...]] = []
    for expected_index, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                f"{runtime_name} embeddings.data entries must be objects.",
            )
        row = cast(dict[str, object], raw)
        if row.get("index") != expected_index:
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                f"{runtime_name} embeddings must preserve input order through consecutive indices.",
            )
        raw_vector_value = row.get("embedding")
        if not isinstance(raw_vector_value, list) or not raw_vector_value:
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                f"{runtime_name} embedding row must contain a non-empty vector.",
            )
        raw_vector = cast(list[object], raw_vector_value)
        vector = tuple(
            float(value)
            for value in raw_vector
            if isinstance(value, int | float) and not isinstance(value, bool)
        )
        if len(vector) != len(raw_vector) or not all(math.isfinite(value) for value in vector):
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                f"{runtime_name} embedding values must be finite numbers.",
            )
        vectors.append(vector)
    if len(vectors) != len(inputs):
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
            f"{runtime_name} returned a vector count different from the input count.",
        )
    return EmbeddingBatch(
        model_identity=EmbeddingModelIdentity(
            adapter_id=expected_adapter,
            model_id=profile.model_id,
            model_digest=profile.model_digest,
            vector_dimension=profile.expected_vector_dimension,
            configuration_digest=embedding_profile_configuration_digest(profile),
        ),
        vectors=tuple(vectors),
    )


def validate_embedding_profile(profile: EmbeddingProfile, expected_adapter: str) -> None:
    if profile.adapter_id != expected_adapter:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_PROFILE_MISMATCH,
            f"Embedding profile {profile.profile_id} is not for {expected_adapter}.",
        )
    path = Path(profile.model_path)
    if not path.is_file():
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_PROFILE_MISMATCH,
            f"Pinned embedding model is unavailable: {path}.",
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != profile.model_digest:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_PROFILE_MISMATCH,
            "Pinned embedding model bytes do not match the selected profile.",
        )


def _model_ids(body: str, runtime_name: str) -> set[str]:
    payload = parse_json_object(body, f"{runtime_name} models")
    values = required_list(payload, "data", f"{runtime_name} models")
    result: set[str] = set()
    for raw_value in values:
        if not isinstance(raw_value, dict):
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                f"{runtime_name} models.data entries require a string id.",
            )
        raw = cast(dict[str, object], raw_value)
        model_id = raw.get("id")
        if not isinstance(model_id, str):
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                f"{runtime_name} models.data entries require a string id.",
            )
        result.add(model_id)
    return result
