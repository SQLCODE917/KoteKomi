"""Shared HTTP boundary helpers for local ModelRuntime Adapters."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import httpx
from kotekomi_application import (
    ModelRuntimeDeadlineExceeded,
    ModelRuntimeResponseError,
    ModelRuntimeUnavailableError,
)
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
    first_response_event_milliseconds: int | None = None


@dataclass(frozen=True)
class SseCompletion:
    body: str
    first_response_event_milliseconds: int | None


class JsonHttpClient(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue] | None,
        timeout_seconds: float,
    ) -> HttpResponse: ...


class StreamingJsonHttpClient(Protocol):
    """A task-only streaming HTTP boundary with a total wall-clock deadline."""

    def stream_request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue],
        deadline_seconds: float,
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


class HttpxSseJsonHttpClient:
    """Read one SSE response under a cancellable total wall-clock deadline."""

    def __init__(
        self,
        monotonic_clock: Callable[[], float] = time.monotonic,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._monotonic_clock = monotonic_clock
        self._transport = transport

    def stream_request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, JsonValue],
        deadline_seconds: float,
    ) -> HttpResponse:
        if deadline_seconds <= 0:
            raise ValueError("Streaming request deadline must be positive.")
        try:
            return asyncio.run(
                _stream_httpx_sse_request(
                    method=method,
                    url=url,
                    payload=payload,
                    deadline_seconds=deadline_seconds,
                    monotonic_clock=self._monotonic_clock,
                    transport=self._transport,
                )
            )
        except TimeoutError as exc:
            raise ModelRuntimeDeadlineExceeded(
                "Model task exceeded its configured wall-clock deadline."
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelRuntimeUnavailableError(f"Model runtime request failed: {url}") from exc


async def _stream_httpx_sse_request(
    *,
    method: str,
    url: str,
    payload: dict[str, JsonValue],
    deadline_seconds: float,
    monotonic_clock: Callable[[], float],
    transport: httpx.AsyncBaseTransport | None,
) -> HttpResponse:
    started_at = monotonic_clock()
    async with httpx.AsyncClient(timeout=None, transport=transport) as client, asyncio.timeout(
        deadline_seconds
    ):
        async with client.stream(
            method,
            url,
            json=payload,
            headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
        ) as response:
            if response.status_code != 200:
                return HttpResponse(
                    status_code=response.status_code,
                    body=(await response.aread()).decode(),
                )
            completion = await _read_httpx_sse_completion(response, started_at, monotonic_clock)
            return HttpResponse(
                status_code=response.status_code,
                body=completion.body,
                first_response_event_milliseconds=completion.first_response_event_milliseconds,
            )


async def _read_httpx_sse_completion(
    response: httpx.Response,
    started_at: float,
    monotonic_clock: Callable[[], float],
) -> SseCompletion:
    event_name: str | None = None
    data_lines: list[str] = []
    first_response_event_milliseconds: int | None = None
    async for decoded in response.aiter_lines():
        if not decoded:
            completed = _completed_sse_payload(event_name, data_lines)
            if completed is not None:
                return SseCompletion(completed, first_response_event_milliseconds)
            event_name = None
            data_lines = []
            continue
        if decoded.startswith("event:"):
            if first_response_event_milliseconds is None:
                first_response_event_milliseconds = _elapsed_milliseconds(
                    started_at, monotonic_clock
                )
            event_name = decoded.removeprefix("event:").strip()
            continue
        if decoded.startswith("data:"):
            if first_response_event_milliseconds is None:
                first_response_event_milliseconds = _elapsed_milliseconds(
                    started_at, monotonic_clock
                )
            data_lines.append(decoded.removeprefix("data:").lstrip())
            continue
        raise ModelRuntimeResponseError("LM Studio SSE event is malformed.")
    completed = _completed_sse_payload(event_name, data_lines)
    if completed is not None:
        return SseCompletion(completed, first_response_event_milliseconds)
    raise ModelRuntimeResponseError("LM Studio SSE ended before response.completed.")


def _elapsed_milliseconds(started_at: float, monotonic_clock: Callable[[], float]) -> int:
    elapsed_milliseconds = int(round((monotonic_clock() - started_at) * 1000))
    if elapsed_milliseconds < 0:
        raise ModelRuntimeResponseError("LM Studio SSE monotonic clock moved backwards.")
    return elapsed_milliseconds


def _completed_sse_payload(event_name: str | None, data_lines: list[str]) -> str | None:
    if not data_lines:
        return None
    payload = parse_json_object("\n".join(data_lines), "LM Studio SSE")
    event_type = event_name or payload.get("type")
    if event_type in {"response.failed", "error"}:
        raise ModelRuntimeResponseError("LM Studio reported a terminal streaming response failure.")
    if event_type != "response.completed":
        return None
    completed = payload.get("response")
    if not isinstance(completed, dict):
        raise ModelRuntimeResponseError("LM Studio response.completed requires a response object.")
    return json.dumps(completed, separators=(",", ":"), ensure_ascii=False)


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
