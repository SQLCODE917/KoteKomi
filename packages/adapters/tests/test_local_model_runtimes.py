import json
from pathlib import Path

import pytest
from kotekomi_adapters import (
    HttpResponse,
    LlamaServerModelRuntime,
    OllamaModelRuntime,
)
from kotekomi_application import (
    ModelNotAvailableError,
    ModelOutputValidationError,
    ModelRuntimeBusyError,
    ModelRuntimeResponseError,
    ModelRuntimeUnavailableError,
)
from kotekomi_domain.models import JsonValue

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "tests"
    / "fixtures"
    / "model_outputs"
    / "anthropic_model_release_review_proposals.json"
)
PROMPT = "Return KoteKomi proposals."
MODEL = "extraction-model"


class FakeHttpClient:
    def __init__(self, responses: list[HttpResponse], unavailable: bool = False) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, JsonValue] | None, float]] = []
        self.unavailable = unavailable

    def request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue] | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append((method, url, payload, timeout_seconds))
        if self.unavailable:
            raise ModelRuntimeUnavailableError(f"Model runtime request failed: {url}")
        return self.responses.pop(0)


def llama_runtime(client: FakeHttpClient) -> LlamaServerModelRuntime:
    return LlamaServerModelRuntime(
        endpoint="http://127.0.0.1:8080/v1",
        model=MODEL,
        prompt_text=PROMPT,
        timeout_seconds=30,
        context_tokens=32768,
        max_output_tokens=8192,
        http_client=client,
    )


def ollama_runtime(client: FakeHttpClient) -> OllamaModelRuntime:
    return OllamaModelRuntime(
        endpoint="http://127.0.0.1:11434",
        model=MODEL,
        prompt_text=PROMPT,
        timeout_seconds=30,
        context_tokens=16384,
        max_output_tokens=8192,
        http_client=client,
    )


def test_llama_server_maps_schema_constrained_completion_to_model_proposals() -> None:
    fixture = FIXTURE_PATH.read_text(encoding="utf-8")
    client = FakeHttpClient(
        [
            llama_models(MODEL, "loaded"),
            llama_slots(False),
            llama_completion(fixture),
        ]
    )
    runtime = llama_runtime(client)

    proposals = runtime.propose_assertions(
        document_id="doc_article_a",
        source_id="src_article_a",
        document_text="Document text",
    )

    assert len(proposals) == 16
    assert runtime.model_name == "llama_server:extraction-model"
    assert runtime.prompt_id.startswith("propose_assertions@sha256:")
    method, url, payload, timeout = client.calls[2]
    assert (method, url, timeout) == (
        "POST",
        "http://127.0.0.1:8080/v1/chat/completions",
        30,
    )
    assert payload is not None
    assert payload["temperature"] == 0
    assert payload["stream"] is False
    response_format = payload["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"


def test_ollama_maps_schema_constrained_completion_to_model_proposals() -> None:
    fixture = FIXTURE_PATH.read_text(encoding="utf-8")
    client = FakeHttpClient([ollama_completion(fixture)])
    runtime = ollama_runtime(client)

    proposals = runtime.propose_assertions(
        document_id="doc_article_a",
        source_id="src_article_a",
        document_text="Document text",
    )

    assert len(proposals) == 16
    assert runtime.model_name == "ollama:extraction-model"
    method, url, payload, timeout = client.calls[0]
    assert (method, url, timeout) == ("POST", "http://127.0.0.1:11434/api/chat", 30)
    assert payload is not None
    assert payload["stream"] is False
    assert payload["think"] is False
    options = payload["options"]
    assert isinstance(options, dict)
    assert options == {"temperature": 0, "num_ctx": 16384, "num_predict": 8192}


@pytest.mark.parametrize("runtime_name", ["llama", "ollama"])
def test_local_runtime_rejects_invalid_model_output(runtime_name: str) -> None:
    completion = llama_completion("{}") if runtime_name == "llama" else ollama_completion("{}")
    client = (
        FakeHttpClient([llama_models(MODEL, "loaded"), llama_slots(False), completion])
        if runtime_name == "llama"
        else FakeHttpClient([completion])
    )
    runtime = llama_runtime(client) if runtime_name == "llama" else ollama_runtime(client)

    with pytest.raises(ModelOutputValidationError, match="Invalid model proposal batch"):
        runtime.propose_assertions(
            document_id="doc_article_a",
            source_id="src_article_a",
            document_text="Document text",
        )


@pytest.mark.parametrize("runtime_name", ["llama", "ollama"])
def test_local_runtime_reports_missing_model(runtime_name: str) -> None:
    client = (
        FakeHttpClient([llama_models("other-model", "loaded")])
        if runtime_name == "llama"
        else FakeHttpClient([HttpResponse(404, '{"error":"model not found"}')])
    )
    runtime = llama_runtime(client) if runtime_name == "llama" else ollama_runtime(client)

    with pytest.raises(ModelNotAvailableError, match="model is unavailable"):
        runtime.propose_assertions(
            document_id="doc_article_a",
            source_id="src_article_a",
            document_text="Document text",
        )


def test_llama_server_reports_http_failure_without_exposing_completion() -> None:
    client = FakeHttpClient(
        [
            llama_models(MODEL, "loaded"),
            llama_slots(False),
            HttpResponse(500, '{"error":"generation failed"}'),
        ]
    )

    with pytest.raises(ModelRuntimeResponseError, match="HTTP 500: generation failed"):
        llama_runtime(client).propose_assertions(
            document_id="doc_article_a",
            source_id="src_article_a",
            document_text="Document text",
        )


def test_ollama_rejects_malformed_response_envelope() -> None:
    client = FakeHttpClient([HttpResponse(200, '{"done":true}')])

    with pytest.raises(ModelRuntimeResponseError, match=r"Ollama\.message must be an object"):
        ollama_runtime(client).propose_assertions(
            document_id="doc_article_a",
            source_id="src_article_a",
            document_text="Document text",
        )


def test_llama_server_readiness_passively_checks_inventory_and_slots() -> None:
    client = FakeHttpClient(
        [
            llama_models(MODEL, "loaded"),
            llama_slots(False),
        ]
    )

    status = llama_runtime(client).check_readiness()

    assert status.ready is True
    assert status.reachable is True
    assert status.model_available is True
    assert status.model_state == "loaded"
    assert (status.idle_slots, status.total_slots) == (1, 1)
    assert [call[1] for call in client.calls] == [
        "http://127.0.0.1:8080/v1/models",
        "http://127.0.0.1:8080/slots?model=extraction-model&autoload=false",
    ]


def test_ollama_readiness_passively_checks_inventory() -> None:
    client = FakeHttpClient(
        [
            HttpResponse(200, json.dumps({"models": [{"name": MODEL}]})),
        ]
    )

    status = ollama_runtime(client).check_readiness()

    assert status.ready is True
    assert status.model_available is True
    assert status.model_state == "available"
    assert status.idle_slots is None


def test_readiness_returns_structured_unavailable_status() -> None:
    client = FakeHttpClient([], unavailable=True)

    status = llama_runtime(client).check_readiness()

    assert status.ready is False
    assert status.reachable is False
    assert status.error_code == "runtime_unavailable"
    assert "http://127.0.0.1:8080/v1/models" in (status.error_message or "")


def test_readiness_returns_structured_missing_model_status() -> None:
    client = FakeHttpClient([HttpResponse(200, json.dumps({"models": []}))])

    status = ollama_runtime(client).check_readiness()

    assert status.ready is False
    assert status.reachable is True
    assert status.model_available is False
    assert status.error_code == "model_unavailable"
    assert len(client.calls) == 1


def test_llama_server_unloaded_model_is_ready_for_router_autoload() -> None:
    client = FakeHttpClient([llama_models(MODEL, "unloaded")])

    status = llama_runtime(client).check_readiness()

    assert status.ready is True
    assert status.model_state == "unloaded"
    assert (status.idle_slots, status.total_slots) == (0, 0)


def test_llama_server_reports_busy_without_submitting_a_completion() -> None:
    client = FakeHttpClient([llama_models(MODEL, "loaded"), llama_slots(True)])

    with pytest.raises(ModelRuntimeBusyError, match="no idle inference slot"):
        llama_runtime(client).propose_assertions(
            document_id="doc_article_a",
            source_id="src_article_a",
            document_text="Document text",
        )

    assert [call[0] for call in client.calls] == ["GET", "GET"]


def llama_models(model: str, state: str) -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps({"data": [{"id": model, "status": {"value": state}}]}),
    )


def llama_slots(is_processing: bool) -> HttpResponse:
    return HttpResponse(200, json.dumps([{"id": 0, "is_processing": is_processing}]))


def llama_completion(content: str) -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}),
    )


def ollama_completion(content: str) -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps({"message": {"role": "assistant", "content": content}, "done": True}),
    )
