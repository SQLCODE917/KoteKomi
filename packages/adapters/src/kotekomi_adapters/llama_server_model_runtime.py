"""llama-server implementation of the ModelRuntime Ports."""

from __future__ import annotations

from typing import cast
from urllib.parse import urlencode, urlsplit, urlunsplit

from kotekomi_application import (
    ModelNotAvailableError,
    ModelProposal,
    ModelRuntimeBusyError,
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
    parse_json_array,
    parse_json_object,
    parse_proposal_content,
    proposal_messages,
    required_list,
    required_object,
    required_string,
)

ADAPTER_NAME = "llama_server"


class LlamaServerModelRuntime:
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
        self._require_idle_model()
        schema = model_proposal_batch_json_schema()
        response = self.http_client.request(
            method="POST",
            url=f"{self.endpoint}/chat/completions",
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
                f"llama-server model is unavailable: {self.model} at {self.endpoint}."
            )
        if response.status_code != 200:
            raise ModelRuntimeResponseError(
                f"llama-server HTTP {response.status_code}: {error_message(response.body)}"
            )
        return parse_proposal_content(_completion_content(response.body))

    def check_readiness(self) -> ModelRuntimeStatus:
        try:
            models_response = self.http_client.request(
                method="GET",
                url=f"{self.endpoint}/models",
                payload=None,
                timeout_seconds=self.timeout_seconds,
            )
            if models_response.status_code != 200:
                raise ModelRuntimeResponseError(
                    f"llama-server HTTP {models_response.status_code}: "
                    f"{error_message(models_response.body)}"
                )
            model_states = _model_states(models_response.body)
            model_state = model_states.get(self.model)
            if model_state is None:
                return self._status(
                    reachable=True,
                    model_available=False,
                    model_state=None,
                    idle_slots=0,
                    total_slots=0,
                    error_code="model_unavailable",
                    error_message=f"Configured model is unavailable: {self.model}.",
                )
            if model_state == "unloaded":
                return self._status(
                    reachable=True,
                    model_available=True,
                    model_state=model_state,
                    idle_slots=0,
                    total_slots=0,
                )
            if model_state != "loaded":
                return self._status(
                    reachable=True,
                    model_available=True,
                    model_state=model_state,
                    idle_slots=0,
                    total_slots=0,
                    error_code="model_not_loaded",
                    error_message=f"Configured model is {model_state}: {self.model}.",
                )
            slots_response = self.http_client.request(
                method="GET",
                url=self._slots_url(),
                payload=None,
                timeout_seconds=self.timeout_seconds,
            )
            if slots_response.status_code != 200:
                raise ModelRuntimeResponseError(
                    f"llama-server slots HTTP {slots_response.status_code}: "
                    f"{error_message(slots_response.body)}"
                )
            idle_slots, total_slots = _slot_counts(slots_response.body)
            if idle_slots == 0:
                return self._status(
                    reachable=True,
                    model_available=True,
                    model_state=model_state,
                    idle_slots=idle_slots,
                    total_slots=total_slots,
                    error_code="runtime_busy",
                    error_message="Managed llama-server has no idle inference slot.",
                )
            return self._status(
                True,
                True,
                model_state,
                idle_slots,
                total_slots,
            )
        except ModelRuntimeError as exc:
            return self._status(
                reachable=not isinstance(exc, ModelRuntimeUnavailableError),
                model_available=False,
                model_state=None,
                idle_slots=0,
                total_slots=0,
                error_code=_error_code(exc),
                error_message=str(exc),
            )

    def _require_idle_model(self) -> None:
        status = self.check_readiness()
        if not status.reachable:
            raise ModelRuntimeUnavailableError(
                status.error_message or "llama-server is unavailable."
            )
        if not status.model_available or status.model_state not in ("unloaded", "loaded"):
            raise ModelNotAvailableError(
                status.error_message or "llama-server model is unavailable."
            )
        if status.model_state == "loaded" and status.idle_slots == 0:
            raise ModelRuntimeBusyError(status.error_message or "llama-server is busy.")

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
            "response_format": {"type": "json_schema", "schema": schema},
            "temperature": 0,
            "stream": False,
            "max_tokens": max_tokens,
        }

    def _status(
        self,
        reachable: bool,
        model_available: bool,
        model_state: str | None,
        idle_slots: int,
        total_slots: int,
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
            idle_slots=idle_slots,
            total_slots=total_slots,
            ready=reachable
            and model_available
            and (model_state == "unloaded" or (model_state == "loaded" and idle_slots > 0)),
            error_code=error_code,
            error_message=error_message,
        )

    def _slots_url(self) -> str:
        parsed = urlsplit(self.endpoint)
        if parsed.path != "/v1":
            raise ModelRuntimeResponseError(
                "llama-server endpoint must end with /v1 for managed-router slot checks."
            )
        query = urlencode({"model": self.model, "autoload": "false"})
        return urlunsplit((parsed.scheme, parsed.netloc, "/slots", query, ""))


def _completion_content(body: str) -> str:
    payload = parse_json_object(body, "llama-server")
    choices = required_list(payload, "choices", "llama-server")
    if len(choices) != 1 or not isinstance(choices[0], dict):
        raise ModelRuntimeResponseError("llama-server.choices must contain one object.")
    choice = cast(dict[str, object], choices[0])
    message = required_object(choice, "message", "llama-server.choices[0]")
    return required_string(message, "content", "llama-server.choices[0].message")


def _model_states(body: str) -> dict[str, str]:
    payload = parse_json_object(body, "llama-server models")
    model_values = required_list(payload, "data", "llama-server models")
    result: dict[str, str] = {}
    for index, model_value in enumerate(model_values):
        if not isinstance(model_value, dict):
            raise ModelRuntimeResponseError(
                f"llama-server models.data[{index}] must be an object."
            )
        model = cast(dict[str, object], model_value)
        model_id = required_string(model, "id", f"llama-server models.data[{index}]")
        status = required_object(model, "status", f"llama-server models.data[{index}]")
        result[model_id] = required_string(
            status,
            "value",
            f"llama-server models.data[{index}].status",
        )
    return result


def _slot_counts(body: str) -> tuple[int, int]:
    slots = parse_json_array(body, "llama-server slots")
    idle_slots = 0
    for index, value in enumerate(slots):
        if not isinstance(value, dict):
            raise ModelRuntimeResponseError(f"llama-server slots[{index}] must be an object.")
        slot = cast(dict[str, object], value)
        is_processing = slot.get("is_processing")
        if not isinstance(is_processing, bool):
            raise ModelRuntimeResponseError(
                f"llama-server slots[{index}].is_processing must be a boolean."
            )
        if not is_processing:
            idle_slots += 1
    return idle_slots, len(slots)


def _error_code(exc: ModelRuntimeError) -> str:
    if isinstance(exc, ModelRuntimeUnavailableError):
        return "runtime_unavailable"
    return "runtime_response_error"
