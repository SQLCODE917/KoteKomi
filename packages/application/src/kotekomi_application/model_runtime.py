"""Tool-neutral local model runtime contracts."""

from __future__ import annotations

import hashlib

from kotekomi_domain.models import JsonValue

from kotekomi_application.ports import ModelRuntimeStatus


class ModelRuntimeError(RuntimeError):
    """Base failure raised by a ModelRuntime Adapter."""


class ModelRuntimeUnavailableError(ModelRuntimeError):
    """The configured model server cannot be reached."""


class ModelNotAvailableError(ModelRuntimeError):
    """The configured model is not available from the server."""


class ModelRuntimeBusyError(ModelRuntimeError):
    """The configured local model server has no idle inference slot."""


class ModelRuntimeResponseError(ModelRuntimeError):
    """The model server returned an invalid HTTP or response envelope."""


class ModelOutputValidationError(ModelRuntimeError, ValueError):
    """The non-deterministic completion failed the proposal DTO contract."""


def prompt_id_for_text(prompt_name: str, prompt_text: str) -> str:
    digest = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    return f"{prompt_name}@sha256:{digest}"


def model_runtime_status_to_json(status: ModelRuntimeStatus) -> dict[str, JsonValue]:
    return {
        "adapter": status.adapter,
        "endpoint": status.endpoint,
        "model": status.model,
        "reachable": status.reachable,
        "model_available": status.model_available,
        "model_state": status.model_state,
        "idle_slots": status.idle_slots,
        "total_slots": status.total_slots,
        "ready": status.ready,
        "error_code": status.error_code,
        "error_message": status.error_message,
    }
