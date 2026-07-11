"""Ollama implementation of the ModelRuntime Ports."""

from __future__ import annotations

from typing import cast

from kotekomi_application import (
    ModelRuntimeError,
    ModelRuntimeResponseError,
    ModelRuntimeStatus,
    ModelRuntimeUnavailableError,
)

from kotekomi_adapters.model_http import (
    JsonHttpClient,
    UrllibJsonHttpClient,
    error_message,
    parse_json_object,
    required_list,
)

ADAPTER_NAME = "ollama"


class OllamaModelRuntime:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        timeout_seconds: float,
        context_tokens: int,
        max_output_tokens: int,
        http_client: JsonHttpClient | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.context_tokens = context_tokens
        self.max_output_tokens = max_output_tokens
        self.http_client = http_client or UrllibJsonHttpClient()

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
