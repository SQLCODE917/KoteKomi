import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_adapters.lm_studio_embeddings import LMStudioEmbeddingAdapter
from kotekomi_adapters.model_http import HttpResponse
from kotekomi_application import DocumentRetrievalError, EmbeddingProfile, RetrievalFailureCode
from kotekomi_domain.models import JsonValue

MODEL_ID = "text-embedding-nomic-embed-text-v1.5"


class FakeHttpClient:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, JsonValue] | None]] = []

    def request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue] | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        del timeout_seconds
        self.calls.append((method, url, payload))
        return self.responses.pop(0)


def _profile(tmp_path: Path) -> EmbeddingProfile:
    model = tmp_path / "nomic.gguf"
    model.write_bytes(b"pinned-nomic-model")
    return EmbeddingProfile(
        profile_id="semantic-validation-v1",
        adapter_id="lm_studio",
        endpoint="http://127.0.0.1:1234/v1",
        model_id=MODEL_ID,
        model_path=str(model),
        model_digest=hashlib.sha256(model.read_bytes()).hexdigest(),
        expected_vector_dimension=3,
        maximum_rendered_characters=100,
    )


def test_lm_studio_embeddings_preserve_order_and_model_identity(tmp_path: Path) -> None:
    client = FakeHttpClient(
        [
            HttpResponse(200, json.dumps({"data": [{"id": MODEL_ID}]})),
            HttpResponse(
                200,
                json.dumps(
                    {
                        "model": MODEL_ID,
                        "data": [
                            {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                            {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                        ],
                    }
                ),
            ),
        ]
    )

    result = LMStudioEmbeddingAdapter(client).embed(_profile(tmp_path), ("one", "two"))

    assert result.model_identity.adapter_id == "lm_studio"
    assert result.model_identity.vector_dimension == 3
    assert result.vectors == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert client.calls[1][2] == {
        "model": MODEL_ID,
        "input": ["one", "two"],
    }


def test_lm_studio_embeddings_reject_unordered_response(tmp_path: Path) -> None:
    client = FakeHttpClient(
        [
            HttpResponse(200, json.dumps({"data": [{"id": MODEL_ID}]})),
            HttpResponse(
                200,
                json.dumps(
                    {
                        "model": MODEL_ID,
                        "data": [{"index": 1, "embedding": [1.0, 0.0, 0.0]}],
                    }
                ),
            ),
        ]
    )

    with pytest.raises(DocumentRetrievalError) as error:
        LMStudioEmbeddingAdapter(client).embed(_profile(tmp_path), ("one",))

    assert error.value.code is RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID
