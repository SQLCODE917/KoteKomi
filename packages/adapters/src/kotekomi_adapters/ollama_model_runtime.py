"""Ollama implementation of the ModelRuntime Ports."""

from __future__ import annotations

from typing import cast

from kotekomi_application import (
    ModelNotAvailableError,
    ModelProposal,
    ModelRuntimeError,
    ModelRuntimeResponseError,
    ModelRuntimeStatus,
    ModelRuntimeUnavailableError,
    model_proposal_batch_json_schema,
    prompt_id_for_text,
)
from kotekomi_domain.models import JsonValue

from kotekomi_adapters.model_http import (
    JsonHttpClient,
    UrllibJsonHttpClient,
    error_message,
    parse_json_object,
    parse_proposal_content,
    proposal_messages,
    required_list,
    required_object,
    required_string,
)

ADAPTER_NAME = "ollama"


class OllamaModelRuntime:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        prompt_text: str,
        timeout_seconds: float,
        context_tokens: int,
        max_output_tokens: int,
        http_client: JsonHttpClient | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.prompt_text = prompt_text
        self.timeout_seconds = timeout_seconds
        self.context_tokens = context_tokens
        self.max_output_tokens = max_output_tokens
        self.http_client = http_client or UrllibJsonHttpClient()

    @property
    def model_name(self) -> str:
        return f"{ADAPTER_NAME}:{self.model}"

    @property
    def prompt_id(self) -> str:
        return prompt_id_for_text("propose_assertions", self.prompt_text)

    def propose_assertions(
        self,
        *,
        document_id: str,
        source_id: str,
        document_text: str,
    ) -> tuple[ModelProposal, ...]:
        schema = model_proposal_batch_json_schema()
        response = self.http_client.request(
            method="POST",
            url=f"{self.endpoint}/api/chat",
            payload=self._chat_payload(
                messages=proposal_messages(
                    prompt_text=self.prompt_text,
                    source_id=source_id,
                    document_id=document_id,
                    document_text=document_text,
                    schema=schema,
                ),
                schema=schema,
                max_tokens=self.max_output_tokens,
            ),
            timeout_seconds=self.timeout_seconds,
        )
        if response.status_code == 404:
            raise ModelNotAvailableError(
                f"Ollama model is unavailable: {self.model} at {self.endpoint}."
            )
        if response.status_code != 200:
            raise ModelRuntimeResponseError(
                f"Ollama HTTP {response.status_code}: {error_message(response.body)}"
            )
        return parse_proposal_content(_completion_content(response.body))

    def check_readiness(self) -> ModelRuntimeStatus:
        try:
            tags_response = self.http_client.request(
                method="GET",
                url=f"{self.endpoint}/api/tags",
                payload=None,
                timeout_seconds=self.timeout_seconds,
            )
            if tags_response.status_code != 200:
                raise ModelRuntimeResponseError(
                    f"Ollama HTTP {tags_response.status_code}: {error_message(tags_response.body)}"
                )
            available_models = _model_names(tags_response.body)
            if self.model not in available_models:
                return self._status(
                    reachable=True,
                    model_available=False,
                    model_state=None,
                    error_code="model_unavailable",
                    error_message=f"Configured model is not installed: {self.model}.",
                )
            return self._status(True, True, "available")
        except ModelRuntimeError as exc:
            return self._status(
                reachable=not isinstance(exc, ModelRuntimeUnavailableError),
                model_available=False,
                model_state=None,
                error_code=_error_code(exc),
                error_message=str(exc),
            )

    def _chat_payload(
        self,
        *,
        messages: list[JsonValue],
        schema: dict[str, JsonValue],
        max_tokens: int,
    ) -> dict[str, JsonValue]:
        return {
            "model": self.model,
            "messages": messages,
            "format": schema,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "num_ctx": self.context_tokens,
                "num_predict": max_tokens,
            },
        }

    def _status(
        self,
        reachable: bool,
        model_available: bool,
        model_state: str | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ModelRuntimeStatus:
        return ModelRuntimeStatus(
            adapter=ADAPTER_NAME,
            endpoint=self.endpoint,
            model=self.model,
            reachable=reachable,
            model_available=model_available,
            model_state=model_state,
            idle_slots=None,
            total_slots=None,
            ready=reachable and model_available and model_state == "available",
            error_code=error_code,
            error_message=error_message,
        )


def _completion_content(body: str) -> str:
    payload = parse_json_object(body, "Ollama")
    message = required_object(payload, "message", "Ollama")
    return required_string(message, "content", "Ollama.message")


def _model_names(body: str) -> tuple[str, ...]:
    payload = parse_json_object(body, "Ollama tags")
    model_values = required_list(payload, "models", "Ollama tags")
    result: list[str] = []
    for index, model_value in enumerate(model_values):
        if not isinstance(model_value, dict):
            raise ModelRuntimeResponseError(f"Ollama tags.models[{index}] must be an object.")
        model_object = cast(dict[str, object], model_value)
        name_value = model_object.get("name", model_object.get("model"))
        if not isinstance(name_value, str) or not name_value:
            raise ModelRuntimeResponseError(
                f"Ollama tags.models[{index}].name must be a non-empty string."
            )
        result.append(name_value)
    return tuple(result)


def _error_code(exc: ModelRuntimeError) -> str:
    if isinstance(exc, ModelRuntimeUnavailableError):
        return "runtime_unavailable"
    return "runtime_response_error"
