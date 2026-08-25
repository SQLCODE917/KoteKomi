import asyncio
import json

import httpx
import pytest
from kotekomi_adapters.lm_studio_model_runtime import LMStudioModelRuntime
from kotekomi_adapters.model_http import HttpResponse, HttpxSseJsonHttpClient
from kotekomi_application import (
    ExecutionSetting,
    ModelExecutionSpec,
    ModelRuntimeDeadlineExceeded,
    ModelRuntimeResponseError,
    ModelTaskRequest,
)
from kotekomi_domain.models import JsonValue


class FakeHttpClient:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, object]] = []

    def request(
        self, *, method: str, url: str, payload: object, timeout_seconds: float
    ) -> HttpResponse:
        del timeout_seconds
        self.calls.append((method, url, payload))
        return self.responses.pop(0)


class FakeStreamingHttpClient:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, JsonValue], float]] = []

    def stream_request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue],
        deadline_seconds: float,
    ) -> HttpResponse:
        self.calls.append((method, url, payload, deadline_seconds))
        return self.responses.pop(0)


class StalledAsyncStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self):  # type: ignore[override]
        await asyncio.Event().wait()
        yield b""

    async def aclose(self) -> None:
        self.closed = True


class FixedAsyncStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        self._chunks = chunks

    async def __aiter__(self):  # type: ignore[override]
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        return None


def _runtime(
    client: FakeHttpClient,
    streaming_client: FakeStreamingHttpClient | None = None,
) -> LMStudioModelRuntime:
    return LMStudioModelRuntime(
        endpoint="http://127.0.0.1:1234/v1",
        model="fixture-model",
        timeout_seconds=1,
        context_tokens=100,
        max_output_tokens=10,
        http_client=client,
        streaming_http_client=streaming_client,
    )


def _task(runtime: LMStudioModelRuntime) -> ModelTaskRequest:
    digest = "a" * 64
    spec = ModelExecutionSpec(
        model_profile_id="lm-studio",
        model_identity=runtime.configured_identity,
        generation_parameters=(ExecutionSetting("max_output_tokens", 10),),
        prompt_id="fixture",
        prompt_digest=digest,
        schema_id="staged_claim_output_v5",
        schema_digest=digest,
        context_manifest_id="ctx_fixture",
        context_manifest_digest=digest,
        rendered_input_digest="b" * 64,
        output_contract_version="staged_claim_output_v5",
    )
    return ModelTaskRequest(
        extraction_task_id="ext_fixture",
        task_fingerprint=digest,
        task_type="claim_extraction",
        context_manifest_id="ctx_fixture",
        context_manifest_digest=digest,
        rendered_input=b"one two",
        rendered_input_digest="b" * 64,
        execution_spec=spec,
    )


def test_lm_studio_runtime_returns_one_strict_output_text() -> None:
    client = FakeHttpClient([])
    streaming_client = FakeStreamingHttpClient(
        [
            HttpResponse(
                200,
                json.dumps(
                    {
                        "model": "fixture-model",
                        "output": [
                            {"content": [{"type": "output_text", "text": '{"kind":"abstain"}'}]}
                        ],
                        "usage": {"output_tokens": 3},
                    }
                ),
                first_response_event_milliseconds=25,
            )
        ]
    )

    runtime = _runtime(client, streaming_client)
    response = runtime.run_model_task(_task(runtime))

    assert response.raw_output == b'{"kind":"abstain"}'
    assert response.execution_receipt.input_token_count == 2
    assert response.first_response_event_milliseconds == 25
    assert runtime.task_deadline_seconds == 1
    assert streaming_client.calls == [
        (
            "POST",
            "http://127.0.0.1:1234/v1/responses",
            {
                "model": "fixture-model",
                "input": "one two",
                "max_output_tokens": 10,
                "stream": True,
            },
            1,
        )
    ]


def test_lm_studio_runtime_rejects_missing_output_text() -> None:
    streaming_client = FakeStreamingHttpClient(
        [HttpResponse(200, json.dumps({"model": "fixture-model", "output": []}))]
    )
    runtime = _runtime(FakeHttpClient([]), streaming_client)

    with pytest.raises(ModelRuntimeResponseError, match="output_text"):
        runtime.run_model_task(_task(runtime))


def test_httpx_sse_client_enforces_deadline_while_waiting_for_the_first_event() -> None:
    stream = StalledAsyncStream()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=stream,
            request=request,
        )
    )

    with pytest.raises(ModelRuntimeDeadlineExceeded, match="wall-clock deadline"):
        HttpxSseJsonHttpClient(transport=transport).stream_request(
            method="POST",
            url="http://model.test/v1/responses",
            payload={"stream": True},
            deadline_seconds=0.01,
        )

    assert stream.closed


def test_httpx_sse_client_returns_the_completed_response() -> None:
    output: list[object] = []
    completed: dict[str, object] = {"model": "fixture-model", "output": output}
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=FixedAsyncStream(
                (
                    b"event: response.created\n",
                    b'data: {"type":"response.created"}\n',
                    b"\n",
                    b"event: response.completed\n",
                    f"data: {json.dumps({'response': completed})}\n".encode(),
                    b"\n",
                )
            ),
            request=request,
        )
    )

    response = HttpxSseJsonHttpClient(transport=transport).stream_request(
        method="POST",
        url="http://model.test/v1/responses",
        payload={"stream": True},
        deadline_seconds=1.0,
    )

    assert json.loads(response.body) == completed
    assert response.first_response_event_milliseconds is not None


def test_sse_terminal_failure_discards_partial_output() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=FixedAsyncStream(
                (
                    b"event: response.output_text.delta\n",
                    b'data: {"type":"response.output_text.delta","delta":"partial"}\n',
                    b"\n",
                    b"event: response.failed\n",
                    b'data: {"type":"response.failed"}\n',
                    b"\n",
                )
            ),
            request=request,
        )
    )

    with pytest.raises(ModelRuntimeResponseError, match="terminal streaming response failure"):
        HttpxSseJsonHttpClient(transport=transport).stream_request(
            method="POST",
            url="http://model.test/v1/responses",
            payload={"stream": True},
            deadline_seconds=10.0,
        )
