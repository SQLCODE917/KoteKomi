"""LM Studio Responses implementation of the staged ModelTaskRuntime Port."""

from __future__ import annotations

import hashlib
from typing import Protocol, cast
from urllib.parse import urlsplit

import lmstudio as lms
from kotekomi_application import (
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelRuntimeResponseError,
    ModelRuntimeStatus,
    ModelRuntimeUnavailableError,
    ModelTaskRequest,
    ModelTaskResponse,
    generation_parameters_digest,
    model_identity_snapshot_digest,
)
from kotekomi_domain.models import JsonValue

from kotekomi_adapters.model_http import (
    HttpxSseJsonHttpClient,
    JsonHttpClient,
    StreamingJsonHttpClient,
    UrllibJsonHttpClient,
    error_message,
    parse_json_object,
    required_list,
)

ADAPTER_NAME = "lm_studio"
TOKENIZER_CONTRACT = "lm_studio_loaded_model_tokenizer_v1"
_PROMPT_TEMPLATE_PROBE = "kotekomi_prompt_template_identity_v1"


class LMStudioInputInspector(Protocol):
    @property
    def tokenizer_id(self) -> str: ...

    def count_tokens(self, logical_input: bytes) -> int: ...

    def get_loaded_context_limit(self) -> int: ...

    def inspect(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement: ...

    def close(self) -> None: ...


class LMStudioSdkInputInspector:
    """Inspect one configured, already-loaded model through LM Studio's supported SDK."""

    def __init__(self, *, endpoint: str, model: str) -> None:
        self._model_name = model
        try:
            self._client = lms.Client(_sdk_api_host(endpoint))
        except lms.LMStudioError as error:
            raise ModelRuntimeUnavailableError(
                "LM Studio SDK client could not connect for input inspection."
            ) from error

    @property
    def tokenizer_id(self) -> str:
        return f"{TOKENIZER_CONTRACT}:{self._model_name}"

    def count_tokens(self, logical_input: bytes) -> int:
        try:
            model, _ = self._loaded_model()
            return model.count_tokens(logical_input.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise ModelRuntimeResponseError("LM Studio input must be UTF-8.") from error
        except lms.LMStudioError as error:
            raise ModelRuntimeResponseError("LM Studio SDK tokenization failed.") from error

    def get_loaded_context_limit(self) -> int:
        try:
            model, _ = self._loaded_model()
            return model.get_context_length()
        except lms.LMStudioError as error:
            raise ModelRuntimeResponseError("LM Studio SDK context inspection failed.") from error

    def inspect(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        if request.model_identity.name != self._model_name:
            raise ModelRuntimeResponseError(
                "LM Studio inspection model does not match runtime configuration."
            )
        try:
            model, model_instance_id = self._loaded_model()
            logical_text = request.logical_input.decode("utf-8")
            formatted_input = model.apply_prompt_template(logical_text)
            prompt_template_probe = model.apply_prompt_template(_PROMPT_TEMPLATE_PROBE)
            return ModelInputMeasurement(
                model_identity_digest=model_identity_snapshot_digest(request.model_identity),
                runtime_identity=ADAPTER_NAME,
                model_instance_id=model_instance_id,
                tokenizer_id=self.tokenizer_id,
                prompt_template_identity=(
                    "sha256:" + hashlib.sha256(prompt_template_probe.encode()).hexdigest()
                ),
                logical_input_digest=request.logical_input_digest,
                formatted_input_digest=hashlib.sha256(formatted_input.encode()).hexdigest(),
                formatted_input_token_count=model.count_tokens(formatted_input),
                loaded_context_limit=model.get_context_length(),
            )
        except UnicodeDecodeError as error:
            raise ModelRuntimeResponseError("LM Studio input must be UTF-8.") from error
        except lms.LMStudioError as error:
            raise ModelRuntimeResponseError("LM Studio SDK input inspection failed.") from error

    def close(self) -> None:
        try:
            self._client.close()
        except lms.LMStudioError as error:
            raise ModelRuntimeResponseError("LM Studio SDK client close failed.") from error

    def _loaded_model(self) -> tuple[lms.LLM, str]:
        matches: list[tuple[lms.LLM, str]] = []
        for model in self._client.llm.list_loaded():
            info = model.get_info()
            identifiers = {str(info.identifier), str(info.model_key)}
            if self._model_name in identifiers:
                matches.append((model, str(info.identifier)))
        if not matches:
            raise ModelRuntimeUnavailableError(
                f"Configured LM Studio model is not loaded: {self._model_name}."
            )
        if len(matches) != 1:
            raise ModelRuntimeResponseError(
                "Configured LM Studio model resolves to multiple loaded instances: "
                f"{self._model_name}."
            )
        return matches[0]


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
        input_inspector: LMStudioInputInspector | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.context_tokens = context_tokens
        self.max_output_tokens = max_output_tokens
        self.http_client = http_client or UrllibJsonHttpClient()
        self.streaming_http_client = streaming_http_client or HttpxSseJsonHttpClient()
        self.input_inspector = input_inspector or LMStudioSdkInputInspector(
            endpoint=endpoint,
            model=model,
        )

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return ModelIdentitySnapshot(
            name=self.model,
            weights_digest=None,
            runtime=ADAPTER_NAME,
            tokenizer_id=self.input_inspector.tokenizer_id,
        )

    @property
    def task_deadline_seconds(self) -> float:
        return self.timeout_seconds

    @property
    def tokenizer_id(self) -> str:
        return self.input_inspector.tokenizer_id

    def count_tokens(self, rendered_input: bytes) -> int:
        return self.input_inspector.count_tokens(rendered_input)

    def inspect_model_input(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        return self.input_inspector.inspect(request)

    def close(self) -> None:
        self.input_inspector.close()

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
            loaded_context_limit = self.input_inspector.get_loaded_context_limit()
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
                configured_context_limit=self.context_tokens,
                loaded_context_limit=loaded_context_limit,
                effective_context_limit=min(self.context_tokens, loaded_context_limit),
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
        _require_ready_admission(
            task,
            self.inspect_model_input(_inspection_request(task)),
            configured_context_limit=self.context_tokens,
            configured_output_reserve=self.max_output_tokens,
        )
        generation_parameters = _generation_parameters_payload(task, self.max_output_tokens)
        response = self.streaming_http_client.stream_request(
            method="POST",
            url=f"{self.endpoint}/responses",
            payload={
                "model": self.model,
                "input": task.rendered_input.decode("utf-8"),
                "stream": True,
                **generation_parameters,
            },
            deadline_seconds=self.timeout_seconds,
        )
        if response.status_code != 200:
            raise ModelRuntimeResponseError(
                "LM Studio Responses returned HTTP "
                f"{response.status_code}: {error_message(response.body)}"
            )
        response_payload = parse_json_object(response.body, "LM Studio Responses")
        if response_payload.get("model") != self.model:
            raise ModelRuntimeResponseError(
                "LM Studio response model does not match configuration."
            )
        raw_output = _output_text(response_payload)
        input_tokens = _input_tokens(response_payload)
        output_tokens = _output_tokens(response_payload)
        settings = task.execution_spec.generation_parameters
        receipt = ModelExecutionReceipt(
            model_identity_digest=model_identity_snapshot_digest(self.configured_identity),
            generation_parameters_digest=generation_parameters_digest(settings),
            rendered_input_digest=hashlib.sha256(task.rendered_input).hexdigest(),
            input_token_count=input_tokens,
            output_token_count=output_tokens,
        )
        return ModelTaskResponse(
            raw_output=raw_output,
            execution_receipt=receipt,
            first_response_event_milliseconds=response.first_response_event_milliseconds,
        )


def _generation_parameters_payload(
    task: ModelTaskRequest, configured_max_output_tokens: int
) -> dict[str, JsonValue]:
    supported = frozenset({"max_output_tokens", "seed", "temperature"})
    values = {setting.key: setting.value for setting in task.execution_spec.generation_parameters}
    unknown = sorted(set(values) - supported)
    if unknown:
        raise ModelRuntimeResponseError(
            "LM Studio does not support declared generation parameters: " + ", ".join(unknown)
        )
    max_output_tokens = values.get("max_output_tokens")
    if max_output_tokens is None:
        raise ModelRuntimeResponseError("LM Studio task must declare max_output_tokens.")
    if max_output_tokens != configured_max_output_tokens:
        raise ModelRuntimeResponseError(
            "LM Studio task max_output_tokens does not match configured runtime."
        )
    return cast(dict[str, JsonValue], values)


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


def _input_tokens(payload: dict[str, object]) -> int:
    value = _usage_token_count(payload, "input_tokens", required=True)
    assert value is not None
    return value


def _output_tokens(payload: dict[str, object]) -> int | None:
    return _usage_token_count(payload, "output_tokens", required=False)


def _usage_token_count(payload: dict[str, object], key: str, *, required: bool) -> int | None:
    usage = payload.get("usage")
    if usage is None:
        if required:
            raise ModelRuntimeResponseError("LM Studio response usage is required.")
        return None
    if not isinstance(usage, dict):
        raise ModelRuntimeResponseError("LM Studio response usage must be an object.")
    value = cast(dict[str, object], usage).get(key)
    if value is None and not required:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ModelRuntimeResponseError(f"LM Studio response usage.{key} must be non-negative.")
    return value


def _inspection_request(task: ModelTaskRequest) -> ModelInputInspectionRequest:
    return ModelInputInspectionRequest(
        model_identity=task.execution_spec.model_identity,
        logical_input=task.rendered_input,
        logical_input_digest=task.rendered_input_digest,
    )


def _require_ready_admission(
    task: ModelTaskRequest,
    measurement: ModelInputMeasurement,
    *,
    configured_context_limit: int,
    configured_output_reserve: int,
) -> None:
    admission = task.input_admission
    if admission.status.value != "ready":
        raise ModelRuntimeResponseError("LM Studio task input admission is not ready.")
    if (
        admission.configured_context_limit != configured_context_limit
        or admission.reserved_output_tokens != configured_output_reserve
    ):
        raise ModelRuntimeResponseError(
            "LM Studio task input admission does not match runtime configuration."
        )
    expected = {
        "model_identity_digest": measurement.model_identity_digest,
        "runtime_identity": measurement.runtime_identity,
        "model_instance_id": measurement.model_instance_id,
        "tokenizer_id": measurement.tokenizer_id,
        "prompt_template_identity": measurement.prompt_template_identity,
        "logical_input_digest": measurement.logical_input_digest,
        "formatted_input_digest": measurement.formatted_input_digest,
        "loaded_context_limit": measurement.loaded_context_limit,
        "formatted_input_token_count": measurement.formatted_input_token_count,
    }
    observed = {
        "model_identity_digest": admission.model_identity_digest,
        "runtime_identity": admission.runtime_identity,
        "model_instance_id": admission.model_instance_id,
        "tokenizer_id": admission.tokenizer_id,
        "prompt_template_identity": admission.prompt_template_identity,
        "logical_input_digest": admission.logical_input_digest,
        "formatted_input_digest": admission.formatted_input_digest,
        "loaded_context_limit": admission.loaded_context_limit,
        "formatted_input_token_count": admission.formatted_input_token_count,
    }
    if observed != expected:
        raise ModelRuntimeResponseError("LM Studio loaded model changed after input admission.")


def _sdk_api_host(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("LM Studio endpoint must be an HTTP URL.")
    default_port = 443 if parsed.scheme == "https" else 80
    return f"{parsed.hostname}:{parsed.port or default_port}"
