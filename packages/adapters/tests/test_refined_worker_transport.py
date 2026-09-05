from __future__ import annotations

import json
import sys
import textwrap
import time
from pathlib import Path

import pytest
from kotekomi_adapters.refined_worker_transport import (
    RefinedWorkerChannelError,
    SubprocessRefinedWorkerTransport,
)

FIRST_REQUEST_ID = "rwr_11111111111111111111111111111111"
SECOND_REQUEST_ID = "rwr_22222222222222222222222222222222"


def _worker_script(tmp_path: Path) -> Path:
    path = tmp_path / "fixture_refined_worker.py"
    path.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import sys
            import time
            import uuid

            worker_instance_id = uuid.uuid4().hex
            with open(__file__ + ".starts", "a", encoding="utf-8") as start_log:
                start_log.write(worker_instance_id + "\\n")

            def canonical(value):
                return json.dumps(
                    value,
                    allow_nan=False,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()

            for line in sys.stdin.buffer:
                request = json.loads(line)
                request_id = request["request_id"]
                payload = request["payload"]
                behavior = payload["behavior"]
                response = {
                    "schema_version": "refined_worker_exchange_v1",
                    "request_id": request_id,
                    "payload": {
                        "behavior": behavior,
                        "worker_instance_id": worker_instance_id,
                    },
                }
                if behavior == "silence":
                    time.sleep(2)
                    continue
                if behavior == "partial":
                    sys.stdout.buffer.write(b"{")
                    sys.stdout.buffer.flush()
                    time.sleep(2)
                    continue
                if behavior == "late":
                    time.sleep(2)
                elif behavior == "wrong_id":
                    response["request_id"] = "rwr_ffffffffffffffffffffffffffffffff"
                elif behavior == "malformed":
                    sys.stdout.buffer.write(b"not-json\\n")
                    sys.stdout.buffer.flush()
                    continue
                elif behavior == "nonfinite":
                    sys.stdout.buffer.write(
                        b'{"payload":{"score":NaN},"request_id":"'
                        + request_id.encode()
                        + b'","schema_version":"refined_worker_exchange_v1"}\\n'
                    )
                    sys.stdout.buffer.flush()
                    continue
                elif behavior == "oversized":
                    sys.stdout.buffer.write(b"x" * 2048)
                    sys.stdout.buffer.flush()
                    time.sleep(2)
                    continue
                elif behavior == "exit":
                    raise SystemExit(0)
                elif behavior == "blocked":
                    response["payload"]["status"] = "blocked"
                sys.stdout.buffer.write(canonical(response) + b"\\n")
                sys.stdout.buffer.flush()
            """
        ),
        encoding="utf-8",
    )
    return path


def _transport(
    worker_script: Path,
    request_ids: tuple[str, ...],
    *,
    timeout_seconds: float = 0.25,
    max_frame_bytes: int = 1024,
) -> SubprocessRefinedWorkerTransport:
    iterator = iter(request_ids)
    return SubprocessRefinedWorkerTransport(
        python_executable=Path(sys.executable),
        worker_script=worker_script,
        timeout_seconds=timeout_seconds,
        max_frame_bytes=max_frame_bytes,
        cleanup_allowance_seconds=0.5,
        request_id_factory=lambda: next(iterator),
    )


def test_valid_requests_reuse_one_healthy_worker(tmp_path: Path) -> None:
    worker_script = _worker_script(tmp_path)
    transport = _transport(worker_script, (FIRST_REQUEST_ID, SECOND_REQUEST_ID))
    try:
        first = transport.request({"behavior": "echo"})
        second = transport.request({"behavior": "echo"})
    finally:
        transport.close()

    assert first.request_id == FIRST_REQUEST_ID
    assert second.request_id == SECOND_REQUEST_ID
    assert first.payload["worker_instance_id"] == second.payload["worker_instance_id"]
    assert json.loads(first.raw_output)["request_id"] == FIRST_REQUEST_ID
    assert _worker_starts(worker_script) == 1


@pytest.mark.parametrize(
    ("behavior", "expected_code"),
    (
        ("silence", "worker_timeout"),
        ("partial", "worker_timeout"),
        ("late", "worker_timeout"),
        ("wrong_id", "worker_correlation_mismatch"),
        ("malformed", "worker_malformed_frame"),
        ("nonfinite", "worker_malformed_frame"),
        ("oversized", "worker_response_too_large"),
        ("exit", "worker_exited"),
    ),
)
def test_channel_failure_discards_worker_and_next_request_is_clean(
    tmp_path: Path,
    behavior: str,
    expected_code: str,
) -> None:
    worker_script = _worker_script(tmp_path)
    transport = _transport(
        worker_script,
        (FIRST_REQUEST_ID, SECOND_REQUEST_ID),
        timeout_seconds=0.1,
        max_frame_bytes=512,
    )
    started = time.monotonic()
    try:
        with pytest.raises(RefinedWorkerChannelError) as captured:
            transport.request({"behavior": behavior})
        elapsed = time.monotonic() - started
        clean = transport.request({"behavior": "echo"})
    finally:
        transport.close()

    assert captured.value.code == expected_code
    assert captured.value.request_id == FIRST_REQUEST_ID
    assert str(captured.value).startswith(f"{expected_code} [{FIRST_REQUEST_ID}]:")
    assert elapsed < 0.8
    assert clean.request_id == SECOND_REQUEST_ID
    assert clean.payload["behavior"] == "echo"
    assert _worker_starts(worker_script) == 2


def test_valid_blocked_payload_keeps_worker_reusable(tmp_path: Path) -> None:
    worker_script = _worker_script(tmp_path)
    transport = _transport(worker_script, (FIRST_REQUEST_ID, SECOND_REQUEST_ID))
    try:
        blocked = transport.request({"behavior": "blocked"})
        completed = transport.request({"behavior": "echo"})
    finally:
        transport.close()

    assert blocked.payload["status"] == "blocked"
    assert blocked.payload["worker_instance_id"] == completed.payload["worker_instance_id"]
    assert _worker_starts(worker_script) == 1


def test_request_frame_limit_fails_before_worker_start(tmp_path: Path) -> None:
    transport = _transport(
        _worker_script(tmp_path),
        (FIRST_REQUEST_ID,),
        max_frame_bytes=128,
    )
    try:
        with pytest.raises(RefinedWorkerChannelError) as captured:
            transport.request({"behavior": "echo", "value": "x" * 256})
    finally:
        transport.close()

    assert captured.value.code == "worker_request_too_large"


@pytest.mark.parametrize(
    "worker_name",
    ("refined_entity_linking_worker.py", "refined_organization_type_worker.py"),
)
def test_repository_worker_returns_correlated_task_failure(worker_name: str) -> None:
    worker_script = Path(__file__).resolve().parents[3] / "scripts" / worker_name
    transport = _transport(worker_script, (FIRST_REQUEST_ID, SECOND_REQUEST_ID))
    try:
        first = transport.request({})
        second = transport.request({})
    finally:
        transport.close()

    assert first.request_id == FIRST_REQUEST_ID
    assert second.request_id == SECOND_REQUEST_ID
    assert first.payload["status"] == "blocked"
    assert first.payload["failure"] == "invalid_request"
    assert second.payload["status"] == "blocked"


def _worker_starts(worker_script: Path) -> int:
    return len(Path(f"{worker_script}.starts").read_text(encoding="utf-8").splitlines())
