import hashlib
import json
from pathlib import Path

from kotekomi_adapters.model_http import HttpResponse
from kotekomi_adapters.ollama_embeddings import OllamaEmbeddingAdapter
from kotekomi_application import EmbeddingProfile


class FakeHttpClient:
    def request(self, **_: object) -> HttpResponse:
        return HttpResponse(200, json.dumps({"embeddings": [[1, 0], [0, 1]]}))


def test_ollama_embedding_adapter_preserves_response_order(tmp_path: Path) -> None:
    model = tmp_path / "fixture.gguf"
    model.write_bytes(b"fixture")
    profile = EmbeddingProfile(
        profile_id="fixture",
        adapter_id="ollama",
        endpoint="http://127.0.0.1:11434",
        model_id="fixture-embed",
        model_path=str(model),
        model_digest=hashlib.sha256(model.read_bytes()).hexdigest(),
        expected_vector_dimension=2,
        maximum_rendered_characters=100,
    )

    result = OllamaEmbeddingAdapter(FakeHttpClient()).embed(profile, ("one", "two"))

    assert result.model_identity.adapter_id == "ollama"
    assert result.vectors == ((1.0, 0.0), (0.0, 1.0))
