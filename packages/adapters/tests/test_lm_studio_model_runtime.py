import json
from types import SimpleNamespace

import pytest
from kotekomi_adapters.lm_studio_model_runtime import LMStudioModelRuntime
from kotekomi_adapters.model_http import HttpResponse, read_sse_completion
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


class FakeSocket:
    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def settimeout(self, timeout_seconds: float) -> None:
        self.timeouts.append(timeout_seconds)


class FakeStreamResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines
        self.socket = FakeSocket()
        self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=self.socket))

    def readline(self) -> bytes:
        return self._lines.pop(0) if self._lines else b""


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
        schema_id="staged_claim_output_v1",
        schema_digest=digest,
        context_manifest_id="ctx_fixture",
        context_manifest_digest=digest,
        rendered_input_digest="b" * 64,
        output_contract_version="staged_claim_output_v1",
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


def test_sse_completion_returns_only_the_completed_response() -> None:
    response = FakeStreamResponse(
        [
            b"event: response.output_text.delta\n",
            b'data: {"type":"response.output_text.delta","delta":"partial"}\n',
            b"\n",
            b"event: response.completed\n",
            b'data: {"response":{"model":"fixture-model","output":[]}}\n',
            b"\n",
        ]
    )

    result = read_sse_completion(
        response,
        deadline=10.0,
        started_at=0.0,
        monotonic_clock=lambda: 0.0,
    )

    assert json.loads(result.body) == {"model": "fixture-model", "output": []}
    assert result.first_response_event_milliseconds == 0
    assert response.socket.timeouts == [10.0] * 6


def test_sse_activity_does_not_extend_the_wall_clock_deadline() -> None:
    response = FakeStreamResponse(
        [
            b"event: response.output_text.delta\n",
            b'data: {"type":"response.output_text.delta","delta":"partial"}\n',
            b"\n",
        ]
    )
    values = iter((0.0, 0.2, 0.4, 1.0))

    def clock() -> float:
        return next(values)

    with pytest.raises(ModelRuntimeDeadlineExceeded, match="wall-clock deadline"):
        read_sse_completion(response, deadline=1.0, started_at=0.0, monotonic_clock=clock)

    assert response.socket.timeouts == [1.0, 0.6]


def test_sse_terminal_failure_discards_partial_output() -> None:
    response = FakeStreamResponse(
        [
            b"event: response.output_text.delta\n",
            b'data: {"type":"response.output_text.delta","delta":"partial"}\n',
            b"\n",
            b"event: response.failed\n",
            b'data: {"type":"response.failed"}\n',
            b"\n",
        ]
    )

    with pytest.raises(ModelRuntimeResponseError, match="terminal streaming response failure"):
        read_sse_completion(
            response,
            deadline=10.0,
            started_at=0.0,
            monotonic_clock=lambda: 0.0,
        )
