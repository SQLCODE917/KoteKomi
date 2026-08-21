"""llama-server OpenAI-compatible implementation of the embedding Port."""

from __future__ import annotations

from kotekomi_application import EmbeddingBatch, EmbeddingProfile

from kotekomi_adapters.lm_studio_embeddings import embed_openai_compatible
from kotekomi_adapters.model_http import JsonHttpClient, UrllibJsonHttpClient

ADAPTER_NAME = "llama_server"


class LlamaServerEmbeddingAdapter:
    def __init__(self, http_client: JsonHttpClient | None = None) -> None:
        self._http_client = http_client or UrllibJsonHttpClient()

    def embed(self, profile: EmbeddingProfile, inputs: tuple[str, ...]) -> EmbeddingBatch:
        return embed_openai_compatible(
            profile,
            inputs,
            expected_adapter=ADAPTER_NAME,
            runtime_name="llama-server",
            http_client=self._http_client,
        )
