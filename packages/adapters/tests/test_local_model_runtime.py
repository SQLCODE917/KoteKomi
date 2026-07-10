from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from kotekomi_adapters.local_model_runtime import (
    LlamaCppModelRuntime,
    LocalModelRuntimeConfig,
    LocalModelRuntimeError,
    OllamaModelRuntime,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "tests"
    / "fixtures"
    / "model_outputs"
    / "anthropic_model_release_review_proposals.json"
)


class FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _proposal_json() -> str:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return json.dumps({"proposals": [fixture["proposals"][0]]})


def _config(base_url: str = "http://runtime.local") -> LocalModelRuntimeConfig:
    return LocalModelRuntimeConfig(
        base_url=base_url,
        model_name="test-model",
        context_window=16384,
        timeout_seconds=3,
    )


def test_ollama_runtime_maps_request_and_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        captured["payload"] = json.loads(request.data)  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        return FakeHttpResponse({"message": {"content": _proposal_json()}})

    monkeypatch.setattr("kotekomi_adapters.local_model_runtime.urlopen", fake_urlopen)
    runtime = OllamaModelRuntime(_config(), "prompt instructions")

    proposals = runtime.propose_assertions(
        document_id="doc_article_a",
        source_id="src_article_a",
        document_text="Document body",
    )

    assert captured["url"] == "http://runtime.local/api/chat"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["options"] == {"num_ctx": 16384}
    assert captured["payload"]["think"] is False
    assert captured["payload"]["messages"][1]["content"].endswith("Document body")
    assert captured["timeout"] == 3
    assert proposals[0].record_type == "Organization"


def test_llama_cpp_runtime_maps_openai_request_and_valid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        captured["payload"] = json.loads(request.data)  # type: ignore[attr-defined]
        return FakeHttpResponse(
            {"choices": [{"message": {"content": _proposal_json()}}]}
        )

    monkeypatch.setattr("kotekomi_adapters.local_model_runtime.urlopen", fake_urlopen)
    runtime = LlamaCppModelRuntime(_config("http://runtime.local/v1"), "prompt instructions")

    proposals = runtime.propose_assertions(
        document_id="doc_article_a",
        source_id="src_article_a",
        document_text="Document body",
    )

    assert captured["url"] == "http://runtime.local/v1/chat/completions"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["temperature"] == 0
    assert proposals[0].stable_label == "anthropic_ai_lab"


def test_runtime_rejects_malformed_model_content(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float) -> FakeHttpResponse:
        del request, timeout
        return FakeHttpResponse({"message": {"content": "not json"}})

    monkeypatch.setattr("kotekomi_adapters.local_model_runtime.urlopen", fake_urlopen)
    runtime = OllamaModelRuntime(_config(), "prompt instructions")

    with pytest.raises(LocalModelRuntimeError, match="not valid JSON"):
        runtime.propose_assertions(
            document_id="doc_article_a",
            source_id="src_article_a",
            document_text="Document body",
        )
