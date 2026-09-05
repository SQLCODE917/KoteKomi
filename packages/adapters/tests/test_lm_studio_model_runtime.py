import asyncio
import hashlib
import json
import os
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from kotekomi_adapters.lm_studio_model_runtime import (
    LMStudioModelRuntime,
    LMStudioSdkInputInspector,
)
from kotekomi_adapters.model_http import HttpResponse, HttpxSseJsonHttpClient
from kotekomi_application import (
    ExecutionSetting,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelRuntimeDeadlineExceeded,
    ModelRuntimeResponseError,
    ModelRuntimeUnavailableError,
    ModelTaskRequest,
    model_identity_snapshot_digest,
)
from kotekomi_domain import ModelInputAdmission, ModelInputAdmissionStatus
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


class FakeInputInspector:
    tokenizer_id = "lm_studio_loaded_model_tokenizer_v1:fixture-model"

    def __init__(self) -> None:
        self.formatted_input_token_count = 2
        self.loaded_context_limit = 100
        self.inspections: list[ModelInputInspectionRequest] = []
        self.closed = False

    def count_tokens(self, logical_input: bytes) -> int:
        return len(logical_input.decode("utf-8").split())

    def get_loaded_context_limit(self) -> int:
        return self.loaded_context_limit

    def inspect(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        self.inspections.append(request)
        return ModelInputMeasurement(
            model_identity_digest=model_identity_snapshot_digest(request.model_identity),
            runtime_identity="lm_studio",
            model_instance_id="fixture-model",
            tokenizer_id=self.tokenizer_id,
            prompt_template_identity="sha256:" + "f" * 64,
            logical_input_digest=request.logical_input_digest,
            formatted_input_digest=hashlib.sha256(
                b"<fixture-template>" + request.logical_input
            ).hexdigest(),
            formatted_input_token_count=self.formatted_input_token_count,
            loaded_context_limit=self.loaded_context_limit,
        )

    def close(self) -> None:
        self.closed = True


class FakeSdkModel:
    def __init__(self, *, identifier: str = "fixture-model") -> None:
        self.identifier = identifier
        self.counted_text: list[str] = []
        self.templated_text: list[str] = []

    def get_info(self) -> SimpleNamespace:
        return SimpleNamespace(identifier=self.identifier, model_key=self.identifier)

    def apply_prompt_template(self, text: str) -> str:
        self.templated_text.append(text)
        return f"<|user|>{text}<|end|>"

    def count_tokens(self, text: str) -> int:
        self.counted_text.append(text)
        return len(text.encode("utf-8"))

    def get_context_length(self) -> int:
        return 16_384


class FakeSdkClient:
    def __init__(self, models: list[FakeSdkModel]) -> None:
        self.models = models
        self.llm = SimpleNamespace(list_loaded=lambda: self.models)
        self.closed = False

    def close(self) -> None:
        self.closed = True


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
    *,
    input_inspector: FakeInputInspector | None = None,
) -> LMStudioModelRuntime:
    return LMStudioModelRuntime(
        endpoint="http://127.0.0.1:1234/v1",
        model="fixture-model",
        timeout_seconds=1,
        context_tokens=100,
        max_output_tokens=10,
        http_client=client,
        streaming_http_client=streaming_client,
        input_inspector=input_inspector or FakeInputInspector(),
    )


def _task(runtime: LMStudioModelRuntime) -> ModelTaskRequest:
    digest = "a" * 64
    rendered_input = b"one two"
    rendered_input_digest = hashlib.sha256(rendered_input).hexdigest()
    spec = ModelExecutionSpec(
        model_profile_id="lm-studio",
        model_identity=runtime.configured_identity,
        generation_parameters=(
            ExecutionSetting("max_output_tokens", 10),
            ExecutionSetting("seed", 17),
            ExecutionSetting("temperature", 0),
        ),
        prompt_id="fixture",
        prompt_digest=digest,
        schema_id="semantic_draft_text_v1",
        schema_digest=digest,
        context_manifest_id="ctx_fixture",
        context_manifest_digest=digest,
        rendered_input_digest=rendered_input_digest,
        output_contract_version="semantic_draft_text_v1",
    )
    measurement = runtime.inspect_model_input(
        ModelInputInspectionRequest(
            model_identity=runtime.configured_identity,
            logical_input=rendered_input,
            logical_input_digest=rendered_input_digest,
        )
    )
    admission = ModelInputAdmission(
        id="mia_fixture",
        extraction_task_id="ext_fixture",
        model_profile_id="lm-studio",
        model_identity_digest=measurement.model_identity_digest,
        runtime_identity=measurement.runtime_identity,
        model_instance_id=measurement.model_instance_id,
        tokenizer_id=measurement.tokenizer_id,
        prompt_template_identity=measurement.prompt_template_identity,
        logical_input_digest=measurement.logical_input_digest,
        formatted_input_digest=measurement.formatted_input_digest,
        configured_context_limit=100,
        loaded_context_limit=measurement.loaded_context_limit,
        effective_context_limit=100,
        formatted_input_token_count=measurement.formatted_input_token_count,
        reserved_output_tokens=10,
        safety_margin_tokens=0,
        required_capacity=measurement.formatted_input_token_count + 10,
        status=ModelInputAdmissionStatus.READY,
    )
    return ModelTaskRequest(
        extraction_task_id="ext_fixture",
        task_fingerprint=digest,
        task_type="claim_extraction",
        context_manifest_id="ctx_fixture",
        context_manifest_digest=digest,
        rendered_input=rendered_input,
        rendered_input_digest=rendered_input_digest,
        execution_spec=spec,
        input_admission=admission,
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
                            {
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "outcome: abstain\nreason: fixture",
                                    }
                                ]
                            }
                        ],
                        "usage": {"input_tokens": 11, "output_tokens": 3},
                    }
                ),
                first_response_event_milliseconds=25,
            )
        ]
    )

    runtime = _runtime(client, streaming_client)
    task = _task(runtime)
    response = runtime.run_model_task(task)

    assert response.raw_output == b"outcome: abstain\nreason: fixture"
    assert response.execution_receipt.input_token_count == 11
    assert task.input_admission.formatted_input_token_count == 2
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
                "seed": 17,
                "stream": True,
                "temperature": 0,
            },
            1,
        )
    ]


def test_lm_studio_readiness_reports_configured_loaded_and_effective_limits() -> None:
    runtime = _runtime(
        FakeHttpClient(
            [
                HttpResponse(
                    200,
                    json.dumps({"data": [{"id": "fixture-model"}]}),
                )
            ]
        )
    )

    status = runtime.check_readiness()

    assert status.ready is True
    assert status.configured_context_limit == 100
    assert status.loaded_context_limit == 100
    assert status.effective_context_limit == 100


def test_sdk_inspection_uses_loaded_prompt_template_tokenizer_and_context() -> None:
    model = FakeSdkModel()
    client = FakeSdkClient([model])
    with patch(
        "kotekomi_adapters.lm_studio_model_runtime.lms.Client",
        return_value=client,
    ):
        inspector = LMStudioSdkInputInspector(
            endpoint="http://127.0.0.1:1234/v1",
            model="fixture-model",
        )
    logical_input = "why—this?日本語".encode()
    logical_digest = hashlib.sha256(logical_input).hexdigest()
    identity = LMStudioModelRuntime(
        endpoint="http://127.0.0.1:1234/v1",
        model="fixture-model",
        timeout_seconds=1,
        context_tokens=8_192,
        max_output_tokens=10,
        http_client=FakeHttpClient([]),
        streaming_http_client=FakeStreamingHttpClient([]),
        input_inspector=inspector,
    ).configured_identity

    measurement = inspector.inspect(
        ModelInputInspectionRequest(identity, logical_input, logical_digest)
    )

    formatted = "<|user|>why—this?日本語<|end|>"
    assert measurement.formatted_input_token_count == len(formatted.encode())
    assert measurement.formatted_input_token_count != 1
    assert measurement.loaded_context_limit == 16_384
    assert measurement.formatted_input_digest == hashlib.sha256(formatted.encode()).hexdigest()
    assert model.templated_text == [
        "why—this?日本語",
        "kotekomi_prompt_template_identity_v1",
    ]
    assert model.counted_text == [formatted]


def test_sdk_inspection_fails_when_configured_model_is_not_loaded() -> None:
    client = FakeSdkClient([])
    with patch(
        "kotekomi_adapters.lm_studio_model_runtime.lms.Client",
        return_value=client,
    ):
        inspector = LMStudioSdkInputInspector(
            endpoint="http://127.0.0.1:1234/v1",
            model="fixture-model",
        )
    logical_input = b"fixture"

    with pytest.raises(ModelRuntimeUnavailableError, match="not loaded"):
        inspector.inspect(
            ModelInputInspectionRequest(
                ModelIdentitySnapshot(
                    "fixture-model",
                    None,
                    "lm_studio",
                    inspector.tokenizer_id,
                ),
                logical_input,
                hashlib.sha256(logical_input).hexdigest(),
            )
        )


def test_sdk_inspection_fails_when_configured_model_is_ambiguous() -> None:
    client = FakeSdkClient([FakeSdkModel(), FakeSdkModel()])
    with patch(
        "kotekomi_adapters.lm_studio_model_runtime.lms.Client",
        return_value=client,
    ):
        inspector = LMStudioSdkInputInspector(
            endpoint="http://127.0.0.1:1234/v1",
            model="fixture-model",
        )
    logical_input = b"fixture"

    with pytest.raises(ModelRuntimeResponseError, match="multiple loaded instances"):
        inspector.inspect(
            ModelInputInspectionRequest(
                ModelIdentitySnapshot(
                    "fixture-model",
                    None,
                    "lm_studio",
                    inspector.tokenizer_id,
                ),
                logical_input,
                hashlib.sha256(logical_input).hexdigest(),
            )
        )


def test_lm_studio_runtime_rejects_loaded_model_drift_before_transport() -> None:
    inspector = FakeInputInspector()
    streaming_client = FakeStreamingHttpClient([])
    runtime = _runtime(
        FakeHttpClient([]),
        streaming_client,
        input_inspector=inspector,
    )
    task = _task(runtime)
    inspector.formatted_input_token_count = 3

    with pytest.raises(ModelRuntimeResponseError, match="changed after input admission"):
        runtime.run_model_task(task)

    assert streaming_client.calls == []


def test_lm_studio_runtime_rejects_response_without_input_usage() -> None:
    streaming_client = FakeStreamingHttpClient(
        [
            HttpResponse(
                200,
                json.dumps(
                    {
                        "model": "fixture-model",
                        "output": [
                            {
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "outcome: abstain\nreason: fixture",
                                    }
                                ]
                            }
                        ],
                        "usage": {"output_tokens": 3},
                    }
                ),
            )
        ]
    )
    runtime = _runtime(FakeHttpClient([]), streaming_client)

    with pytest.raises(ModelRuntimeResponseError, match="usage.input_tokens"):
        runtime.run_model_task(_task(runtime))


def test_lm_studio_runtime_rejects_unsupported_generation_parameters() -> None:
    runtime = _runtime(FakeHttpClient([]), FakeStreamingHttpClient([]))
    task = _task(runtime)
    task = replace(
        task,
        execution_spec=replace(
            task.execution_spec,
            generation_parameters=(
                ExecutionSetting("max_output_tokens", 10),
                ExecutionSetting("top_p", 1),
            ),
        ),
    )

    with pytest.raises(ModelRuntimeResponseError, match="top_p"):
        runtime.run_model_task(task)


def test_lm_studio_runtime_rejects_missing_output_text() -> None:
    streaming_client = FakeStreamingHttpClient(
        [HttpResponse(200, json.dumps({"model": "fixture-model", "output": []}))]
    )
    runtime = _runtime(FakeHttpClient([]), streaming_client)

    with pytest.raises(ModelRuntimeResponseError, match="output_text"):
        runtime.run_model_task(_task(runtime))


@pytest.mark.skipif(
    "KOTEKOMI_LIVE_LM_STUDIO_MODEL" not in os.environ,
    reason="requires an explicitly selected loaded LM Studio model",
)
def test_live_lm_studio_preserves_preflight_and_responses_usage_separately() -> None:
    model = os.environ["KOTEKOMI_LIVE_LM_STUDIO_MODEL"]
    endpoint = os.environ.get("KOTEKOMI_LIVE_LM_STUDIO_ENDPOINT", "http://127.0.0.1:1234/v1")
    runtime = LMStudioModelRuntime(
        endpoint=endpoint,
        model=model,
        timeout_seconds=60,
        context_tokens=16_384,
        max_output_tokens=16,
    )
    logical_input = b"Reply with the single word OK."
    logical_digest = hashlib.sha256(logical_input).hexdigest()
    identity = runtime.configured_identity
    inspection_request = ModelInputInspectionRequest(identity, logical_input, logical_digest)
    measurement = runtime.inspect_model_input(inspection_request)
    effective_limit = min(16_384, measurement.loaded_context_limit)
    admission = ModelInputAdmission(
        id="mia_live_conformance",
        extraction_task_id="ext_live_conformance",
        model_profile_id="live-lm-studio",
        model_identity_digest=measurement.model_identity_digest,
        runtime_identity=measurement.runtime_identity,
        model_instance_id=measurement.model_instance_id,
        tokenizer_id=measurement.tokenizer_id,
        prompt_template_identity=measurement.prompt_template_identity,
        logical_input_digest=measurement.logical_input_digest,
        formatted_input_digest=measurement.formatted_input_digest,
        configured_context_limit=16_384,
        loaded_context_limit=measurement.loaded_context_limit,
        effective_context_limit=effective_limit,
        formatted_input_token_count=measurement.formatted_input_token_count,
        reserved_output_tokens=16,
        safety_margin_tokens=0,
        required_capacity=measurement.formatted_input_token_count + 16,
        status=ModelInputAdmissionStatus.READY,
    )
    spec = ModelExecutionSpec(
        model_profile_id="live-lm-studio",
        model_identity=identity,
        generation_parameters=(
            ExecutionSetting("max_output_tokens", 16),
            ExecutionSetting("seed", 17),
            ExecutionSetting("temperature", 0),
        ),
        prompt_id="live-conformance",
        prompt_digest="a" * 64,
        schema_id="live-conformance",
        schema_digest="b" * 64,
        context_manifest_id="ctx_live_conformance",
        context_manifest_digest="c" * 64,
        rendered_input_digest=logical_digest,
        output_contract_version="live-conformance-v1",
    )
    task = ModelTaskRequest(
        extraction_task_id="ext_live_conformance",
        task_fingerprint="d" * 64,
        task_type="live_conformance",
        context_manifest_id="ctx_live_conformance",
        context_manifest_digest="c" * 64,
        rendered_input=logical_input,
        rendered_input_digest=logical_digest,
        execution_spec=spec,
        input_admission=admission,
    )

    try:
        response = runtime.run_model_task(task)
    finally:
        runtime.close()

    assert measurement.formatted_input_token_count > 0
    assert response.execution_receipt.input_token_count >= 0
    assert response.execution_receipt.rendered_input_digest == logical_digest


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
