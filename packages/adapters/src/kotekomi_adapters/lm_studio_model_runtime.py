"""LM Studio Responses implementation of the staged ModelTaskRuntime Port."""

from __future__ import annotations

import hashlib
from typing import cast

from kotekomi_application import (
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelRuntimeResponseError,
    ModelRuntimeStatus,
    ModelRuntimeUnavailableError,
    ModelTaskRequest,
    ModelTaskResponse,
    generation_parameters_digest,
    model_identity_snapshot_digest,
)

from kotekomi_adapters.model_http import (
    JsonHttpClient,
    StreamingJsonHttpClient,
    UrllibJsonHttpClient,
    UrllibSseJsonHttpClient,
    error_message,
    parse_json_object,
    required_list,
)

ADAPTER_NAME = "lm_studio"


class LMStudioModelRuntime:
    """Translate the LM Studio OpenAI-compatible Responses endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        timeout_seconds: float,
        context_tokens: int,
        max_output_tokens: int,
        http_client: JsonHttpClient | None = None,
        streaming_http_client: StreamingJsonHttpClient | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.context_tokens = context_tokens
        self.max_output_tokens = max_output_tokens
        self.http_client = http_client or UrllibJsonHttpClient()
        self.streaming_http_client = streaming_http_client or UrllibSseJsonHttpClient()

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return ModelIdentitySnapshot(
            name=self.model,
            weights_digest=None,
            runtime=ADAPTER_NAME,
            tokenizer_id="lm_studio_whitespace_v1",
        )

    def check_readiness(self) -> ModelRuntimeStatus:
        try:
            response = self.http_client.request(
                method="GET",
                url=f"{self.endpoint}/models",
                payload=None,
                timeout_seconds=self.timeout_seconds,
            )
            if response.status_code != 200:
                raise ModelRuntimeResponseError(
                    f"LM Studio HTTP {response.status_code}: {error_message(response.body)}"
                )
            available = _model_ids(response.body)
            if self.model not in available:
                return ModelRuntimeStatus(
                    adapter=ADAPTER_NAME,
                    endpoint=self.endpoint,
                    model=self.model,
                    reachable=True,
                    model_available=False,
                    model_state=None,
                    idle_slots=None,
                    total_slots=None,
                    ready=False,
                    error_code="model_unavailable",
                    error_message=f"Configured model is unavailable: {self.model}.",
                )
            return ModelRuntimeStatus(
                adapter=ADAPTER_NAME,
                endpoint=self.endpoint,
                model=self.model,
                reachable=True,
                model_available=True,
                model_state="available",
                idle_slots=None,
                total_slots=None,
                ready=True,
            )
        except ModelRuntimeUnavailableError as exc:
            return ModelRuntimeStatus(
                adapter=ADAPTER_NAME,
                endpoint=self.endpoint,
                model=self.model,
                reachable=False,
                model_available=False,
                model_state=None,
                idle_slots=None,
                total_slots=None,
                ready=False,
                error_code="runtime_unavailable",
                error_message=str(exc),
            )
        except ModelRuntimeResponseError as exc:
            return ModelRuntimeStatus(
                adapter=ADAPTER_NAME,
                endpoint=self.endpoint,
                model=self.model,
                reachable=True,
                model_available=False,
                model_state=None,
                idle_slots=None,
                total_slots=None,
                ready=False,
                error_code="runtime_response_error",
                error_message=str(exc),
            )

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        if task.execution_spec.model_identity != self.configured_identity:
            raise ModelRuntimeResponseError("LM Studio task identity does not match configuration.")
        response = self.streaming_http_client.stream_request(
            method="POST",
            url=f"{self.endpoint}/responses",
            payload={
                "model": self.model,
                "input": task.rendered_input.decode("utf-8"),
                "max_output_tokens": self.max_output_tokens,
                "stream": True,
            },
            deadline_seconds=self.timeout_seconds,
        )
        if response.status_code != 200:
            raise ModelRuntimeResponseError(
                "LM Studio Responses returned HTTP "
                f"{response.status_code}: {error_message(response.body)}"
            )
        payload = parse_json_object(response.body, "LM Studio Responses")
        if payload.get("model") != self.model:
            raise ModelRuntimeResponseError(
                "LM Studio response model does not match configuration."
            )
        raw_output = _output_text(payload)
        output_tokens = _output_tokens(payload)
        settings = task.execution_spec.generation_parameters
        receipt = ModelExecutionReceipt(
            model_identity_digest=model_identity_snapshot_digest(self.configured_identity),
            generation_parameters_digest=generation_parameters_digest(settings),
            rendered_input_digest=hashlib.sha256(task.rendered_input).hexdigest(),
            input_token_count=_count_tokens(task.rendered_input),
            output_token_count=output_tokens,
        )
        return ModelTaskResponse(raw_output=raw_output, execution_receipt=receipt)


def _model_ids(body: str) -> set[str]:
    payload = parse_json_object(body, "LM Studio models")
    result: set[str] = set()
    for row in required_list(payload, "data", "LM Studio models"):
        if not isinstance(row, dict):
            raise ModelRuntimeResponseError("LM Studio model entries require a string id.")
        value = cast(dict[str, object], row).get("id")
        if not isinstance(value, str) or not value:
            raise ModelRuntimeResponseError("LM Studio model entries require a string id.")
        result.add(value)
    return result


def _output_text(payload: dict[str, object]) -> bytes:
    output = required_list(payload, "output", "LM Studio Responses")
    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            raise ModelRuntimeResponseError("LM Studio output entries must be objects.")
        content = cast(dict[str, object], item).get("content")
        if not isinstance(content, list):
            continue
        for part in cast(list[object], content):
            if isinstance(part, dict):
                values = cast(dict[str, object], part)
                if values.get("type") != "output_text":
                    continue
                text = values.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
    if len(text_parts) != 1:
        raise ModelRuntimeResponseError(
            "LM Studio response must contain exactly one output_text value."
        )
    return text_parts[0].encode("utf-8")


def _output_tokens(payload: dict[str, object]) -> int | None:
    usage = payload.get("usage")
    if usage is None:
        return None
    if not isinstance(usage, dict):
        raise ModelRuntimeResponseError("LM Studio response usage must be an object.")
    value = cast(dict[str, object], usage).get("output_tokens")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ModelRuntimeResponseError(
            "LM Studio response usage.output_tokens must be non-negative."
        )
    return value


def _count_tokens(value: bytes) -> int:
    return len(value.decode("utf-8").split())
