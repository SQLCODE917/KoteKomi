"""Correlated, deadline-bounded transport for persistent ReFinED workers."""

from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

EXCHANGE_SCHEMA_VERSION = "refined_worker_exchange_v1"
DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024
DEFAULT_CLEANUP_ALLOWANCE_SECONDS = 1.0
_EXCHANGE_FIELDS = {"schema_version", "request_id", "payload"}
_REQUEST_ID_PATTERN = re.compile(r"^rwr_[a-f0-9]{32}$")
_READ_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class RefinedWorkerExchange:
    """One validated worker response and its exact external bytes."""

    request_id: str
    payload: dict[str, object]
    raw_output: bytes


class RefinedWorkerTransport(Protocol):
    def request(self, payload: dict[str, object]) -> RefinedWorkerExchange: ...

    def discard(self) -> None: ...

    def close(self) -> None: ...


class RefinedWorkerChannelError(RuntimeError):
    """Typed failure from one worker exchange or worker cleanup."""

    def __init__(self, code: str, message: str, *, request_id: str | None = None) -> None:
        self.code = code
        self.message = message
        self.request_id = request_id
        request_detail = "" if request_id is None else f" [{request_id}]"
        super().__init__(f"{code}{request_detail}: {message}")


class SubprocessRefinedWorkerTransport:
    """One persistent worker with strict JSON-line framing and reset recovery."""

    def __init__(
        self,
        *,
        python_executable: Path,
        worker_script: Path,
        timeout_seconds: float,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        cleanup_allowance_seconds: float = DEFAULT_CLEANUP_ALLOWANCE_SECONDS,
        request_id_factory: Callable[[], str] | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not python_executable.is_file():
            raise RuntimeError("ReFinED worker Python executable is unavailable.")
        if not worker_script.is_file():
            raise RuntimeError("ReFinED worker script is unavailable.")
        if timeout_seconds <= 0:
            raise ValueError("ReFinED worker timeout must be positive.")
        if type(max_frame_bytes) is not int or max_frame_bytes <= 0:
            raise ValueError("ReFinED worker frame limit must be a positive integer.")
        if cleanup_allowance_seconds <= 0:
            raise ValueError("ReFinED worker cleanup allowance must be positive.")
        self._command = (str(python_executable), str(worker_script))
        self._timeout_seconds = timeout_seconds
        self._max_frame_bytes = max_frame_bytes
        self._cleanup_allowance_seconds = cleanup_allowance_seconds
        self._request_id_factory = request_id_factory or _new_request_id
        self._monotonic_clock = monotonic_clock
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    def request(self, payload: dict[str, object]) -> RefinedWorkerExchange:
        request_id = self._request_id_factory()
        _validate_request_id(request_id)
        request_bytes = _canonical_json(
            {
                "schema_version": EXCHANGE_SCHEMA_VERSION,
                "request_id": request_id,
                "payload": payload,
            }
        )
        if len(request_bytes) > self._max_frame_bytes:
            raise RefinedWorkerChannelError(
                "worker_request_too_large",
                "ReFinED worker request exceeds the frame limit.",
                request_id=request_id,
            )
        with self._lock:
            deadline = self._monotonic_clock() + self._timeout_seconds
            try:
                process = self._require_process(request_id)
                self._write_frame(process, request_bytes + b"\n", deadline, request_id)
                response_bytes = self._read_frame(process, deadline, request_id)
                return _decode_exchange(response_bytes, request_id)
            except RefinedWorkerChannelError as error:
                self._discard_after_failure(error)
                raise

    def discard(self) -> None:
        with self._lock:
            self._discard_process()

    def close(self) -> None:
        self.discard()

    def _require_process(self, request_id: str) -> subprocess.Popen[bytes]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._discard_process()
        try:
            process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=False,
                bufsize=0,
            )
        except OSError as error:
            raise RefinedWorkerChannelError(
                "worker_start_failed",
                "ReFinED worker could not start.",
                request_id=request_id,
            ) from error
        assert process.stdin is not None
        assert process.stdout is not None
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        self._process = process
        return process

    def _write_frame(
        self,
        process: subprocess.Popen[bytes],
        request_bytes: bytes,
        deadline: float,
        request_id: str,
    ) -> None:
        assert process.stdin is not None
        descriptor = process.stdin.fileno()
        offset = 0
        with selectors.DefaultSelector() as selector:
            selector.register(descriptor, selectors.EVENT_WRITE)
            while offset < len(request_bytes):
                self._wait_for_io(selector, deadline, request_id)
                try:
                    written = os.write(descriptor, request_bytes[offset:])
                except BlockingIOError:
                    continue
                except (BrokenPipeError, OSError) as error:
                    raise RefinedWorkerChannelError(
                        "worker_write_failed",
                        "ReFinED worker request write failed.",
                        request_id=request_id,
                    ) from error
                if written <= 0:
                    raise RefinedWorkerChannelError(
                        "worker_write_failed",
                        "ReFinED worker request write made no progress.",
                        request_id=request_id,
                    )
                offset += written

    def _read_frame(
        self,
        process: subprocess.Popen[bytes],
        deadline: float,
        request_id: str,
    ) -> bytes:
        assert process.stdout is not None
        descriptor = process.stdout.fileno()
        response = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(descriptor, selectors.EVENT_READ)
            while True:
                self._wait_for_io(selector, deadline, request_id)
                try:
                    chunk = os.read(descriptor, _READ_CHUNK_BYTES)
                except BlockingIOError:
                    continue
                except OSError as error:
                    raise RefinedWorkerChannelError(
                        "worker_exited",
                        "ReFinED worker response read failed.",
                        request_id=request_id,
                    ) from error
                if not chunk:
                    raise RefinedWorkerChannelError(
                        "worker_exited",
                        "ReFinED worker exited before a complete response.",
                        request_id=request_id,
                    )
                response.extend(chunk)
                newline = response.find(b"\n")
                if newline >= 0:
                    if newline > self._max_frame_bytes:
                        raise RefinedWorkerChannelError(
                            "worker_response_too_large",
                            "ReFinED worker response exceeds the frame limit.",
                            request_id=request_id,
                        )
                    if newline != len(response) - 1:
                        raise RefinedWorkerChannelError(
                            "worker_malformed_frame",
                            "ReFinED worker returned bytes after its response frame.",
                            request_id=request_id,
                        )
                    return bytes(response[:newline])
                if len(response) > self._max_frame_bytes:
                    raise RefinedWorkerChannelError(
                        "worker_response_too_large",
                        "ReFinED worker response exceeds the frame limit.",
                        request_id=request_id,
                    )

    def _wait_for_io(
        self,
        selector: selectors.BaseSelector,
        deadline: float,
        request_id: str,
    ) -> None:
        remaining = deadline - self._monotonic_clock()
        if remaining <= 0 or not selector.select(remaining):
            raise RefinedWorkerChannelError(
                "worker_timeout",
                "ReFinED worker exceeded its whole-exchange deadline.",
                request_id=request_id,
            )

    def _discard_after_failure(self, cause: RefinedWorkerChannelError) -> None:
        try:
            self._discard_process()
        except RefinedWorkerChannelError as cleanup_error:
            raise cleanup_error from cause

    def _discard_process(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        cleanup_deadline = self._monotonic_clock() + self._cleanup_allowance_seconds
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=_remaining(cleanup_deadline, self._monotonic_clock))
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=_remaining(cleanup_deadline, self._monotonic_clock))
                    except subprocess.TimeoutExpired as error:
                        raise RefinedWorkerChannelError(
                            "worker_cleanup_failed",
                            "ReFinED worker did not exit within its cleanup allowance.",
                        ) from error
        finally:
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    stream.close()


def _decode_exchange(raw_output: bytes, expected_request_id: str) -> RefinedWorkerExchange:
    try:
        value: object = json.loads(raw_output, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RefinedWorkerChannelError(
            "worker_malformed_frame",
            "ReFinED worker response is not JSON.",
            request_id=expected_request_id,
        ) from error
    if not isinstance(value, dict):
        raise RefinedWorkerChannelError(
            "worker_malformed_frame",
            "ReFinED worker response envelope must be an object.",
            request_id=expected_request_id,
        )
    raw_envelope = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_envelope):
        raise RefinedWorkerChannelError(
            "worker_malformed_frame",
            "ReFinED worker response envelope keys must be strings.",
            request_id=expected_request_id,
        )
    envelope = {cast(str, key): item for key, item in raw_envelope.items()}
    if _canonical_json(envelope) != raw_output or set(envelope) != _EXCHANGE_FIELDS:
        raise RefinedWorkerChannelError(
            "worker_malformed_frame",
            "ReFinED worker response envelope is not canonical.",
            request_id=expected_request_id,
        )
    if envelope["schema_version"] != EXCHANGE_SCHEMA_VERSION:
        raise RefinedWorkerChannelError(
            "worker_malformed_frame",
            "ReFinED worker response schema is unsupported.",
            request_id=expected_request_id,
        )
    observed_request_id = envelope["request_id"]
    if observed_request_id != expected_request_id:
        raise RefinedWorkerChannelError(
            "worker_correlation_mismatch",
            "ReFinED worker response belongs to another request.",
            request_id=expected_request_id,
        )
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise RefinedWorkerChannelError(
            "worker_malformed_frame",
            "ReFinED worker response payload must be an object.",
            request_id=expected_request_id,
        )
    raw_payload = cast(dict[object, object], payload)
    if not all(isinstance(key, str) for key in raw_payload):
        raise RefinedWorkerChannelError(
            "worker_malformed_frame",
            "ReFinED worker response payload keys must be strings.",
            request_id=expected_request_id,
        )
    return RefinedWorkerExchange(
        request_id=expected_request_id,
        payload={cast(str, key): item for key, item in raw_payload.items()},
        raw_output=raw_output,
    )


def _new_request_id() -> str:
    return f"rwr_{uuid.uuid4().hex}"


def _validate_request_id(request_id: str) -> None:
    if _REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise ValueError("ReFinED WorkerRequestId is invalid.")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"Non-finite JSON value is not permitted: {value}.")


def _remaining(deadline: float, monotonic_clock: Callable[[], float]) -> float:
    return max(0.001, deadline - monotonic_clock())
