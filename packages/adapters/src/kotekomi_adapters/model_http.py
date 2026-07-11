"""Shared HTTP boundary helpers for local ModelRuntime Adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from kotekomi_application import ModelRuntimeResponseError, ModelRuntimeUnavailableError
from kotekomi_domain.models import JsonValue

READINESS_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {"ready": {"type": "boolean"}},
    "required": ["ready"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: str


class JsonHttpClient(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue] | None,
        timeout_seconds: float,
    ) -> HttpResponse: ...


class UrllibJsonHttpClient:
    def request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue] | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(
                    status_code=response.status,
                    body=response.read().decode("utf-8"),
                )
        except HTTPError as exc:
            return HttpResponse(status_code=exc.code, body=exc.read().decode("utf-8"))
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelRuntimeUnavailableError(f"Model runtime request failed: {url}") from exc


def parse_json_object(body: str, context: str) -> dict[str, object]:
    try:
        value: object = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ModelRuntimeResponseError(f"{context} returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise ModelRuntimeResponseError(f"{context} response must be an object.")
    return cast(dict[str, object], value)


def parse_json_array(body: str, context: str) -> list[object]:
    try:
        value: object = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ModelRuntimeResponseError(f"{context} returned malformed JSON.") from exc
    if not isinstance(value, list):
        raise ModelRuntimeResponseError(f"{context} response must be an array.")
    return cast(list[object], value)


def required_object(payload: dict[str, object], key: str, context: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ModelRuntimeResponseError(f"{context}.{key} must be an object.")
    return cast(dict[str, object], value)


def required_list(payload: dict[str, object], key: str, context: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ModelRuntimeResponseError(f"{context}.{key} must be an array.")
    return cast(list[object], value)


def required_string(payload: dict[str, object], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ModelRuntimeResponseError(f"{context}.{key} must be a non-empty string.")
    return value


def parse_readiness_content(content: str) -> bool:
    payload = parse_json_object(content, "Structured output probe")
    if payload != {"ready": True}:
        raise ModelRuntimeResponseError("Structured output probe must return ready=true.")
    return True


def error_message(body: str) -> str:
    try:
        payload = parse_json_object(body, "Model runtime error")
    except ModelRuntimeResponseError:
        return "Model runtime returned an HTTP error."
    value = payload.get("error")
    if isinstance(value, str) and value:
        return value
    return "Model runtime returned an HTTP error."
