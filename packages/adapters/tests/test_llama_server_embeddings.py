import hashlib
import json
from pathlib import Path

from kotekomi_adapters.llama_server_embeddings import LlamaServerEmbeddingAdapter
from kotekomi_adapters.model_http import HttpResponse
from kotekomi_application import EmbeddingProfile


class FakeHttpClient:
    def __init__(self) -> None:
        self.responses = [
            HttpResponse(200, json.dumps({"data": [{"id": "fixture-embed"}]})),
            HttpResponse(
                200,
                json.dumps({"model": "fixture-embed", "data": [{"index": 0, "embedding": [1, 0]}]}),
            ),
        ]

    def request(self, **_: object) -> HttpResponse:
        return self.responses.pop(0)


def test_llama_server_embedding_adapter_uses_openai_embeddings_contract(tmp_path: Path) -> None:
    model = tmp_path / "fixture.gguf"
    model.write_bytes(b"fixture")
    profile = EmbeddingProfile(
        profile_id="fixture",
        adapter_id="llama_server",
        endpoint="http://127.0.0.1:8080/v1",
        model_id="fixture-embed",
        model_path=str(model),
        model_digest=hashlib.sha256(model.read_bytes()).hexdigest(),
        expected_vector_dimension=2,
        maximum_rendered_characters=100,
    )

    result = LlamaServerEmbeddingAdapter(FakeHttpClient()).embed(profile, ("document",))

    assert result.model_identity.adapter_id == "llama_server"
    assert result.vectors == ((1.0, 0.0),)
