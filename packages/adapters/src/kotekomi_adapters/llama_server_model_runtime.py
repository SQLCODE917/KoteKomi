"""llama-server implementation of the ModelRuntime Ports."""

from __future__ import annotations

from typing import cast
from urllib.parse import urlencode, urlsplit, urlunsplit

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
    parse_json_array,
    parse_json_object,
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


def _model_states(body: str) -> dict[str, str]:
    payload = parse_json_object(body, "llama-server models")
    model_values = required_list(payload, "data", "llama-server models")
    result: dict[str, str] = {}
    for index, model_value in enumerate(model_values):
        if not isinstance(model_value, dict):
            raise ModelRuntimeResponseError(f"llama-server models.data[{index}] must be an object.")
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
