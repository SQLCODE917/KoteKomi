"""Foreground review wake for one enrolled PR and terminal Cline session."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

type JsonObject = dict[str, object]

_MARKER = re.compile(
    r"<!-- kotekomi-review-request:v1 "
    r"repo=(\S+) pr=(\d+) head=([0-9a-f]{40}) pin=([0-9a-f]{40}) -->"
)
_HANDOFF = re.compile(r"^## +Current Handoff *$(.*?)(?=^#{1,2} |\Z)", re.M | re.S)
_PIN = re.compile(r"^ *[-*] +Spec commit *: *`?([0-9a-f]{40})`? *$", re.M)
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_HUB_TIMEOUT = 5.0
_TARGET = {
    "status": "unproven",
    "detail": "same_session_delivery_unproven",
    "delivery": "notification-only",
}


class ReviewWakeError(Exception):
    def __init__(self, code: str, location: str, rule: str) -> None:
        self.code, self.location, self.rule = code, location, rule


class _HubError(Exception):
    pass


def _dict(value: object) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def review_wake(action: str, state_path: Path, **values: Any) -> tuple[int, JsonObject]:
    """Enroll or check one review-wake binding."""
    try:
        if action == "enroll":
            enrollment = _new_enrollment(state_path, values)
            if state_path.exists() and not values.get("replace"):
                raise ReviewWakeError("review_wake.state", "/state", "enrollment_exists")
            data = _load(state_path) if state_path.exists() else {}
            data = data or {"schema_version": 1, "enrollment": enrollment, "alerts": {}}
            data["enrollment"] = enrollment
            _save(state_path, data)
            return 0, {"schema_version": 1, "status": "enrolled", "enrollment": enrollment}
        data = _load(state_path)
        if action == "check":
            return _check(state_path, data, cast(JsonObject, data["enrollment"]))
        raise ReviewWakeError("review_wake.action", "/action", "enroll_or_check")
    except ReviewWakeError as error:
        diagnostic = {"code": error.code, "location": error.location, "rule": error.rule}
        return 1, {"schema_version": 1, "status": "blocked", "diagnostics": [diagnostic]}


def _new_enrollment(state_path: Path, values: JsonObject) -> JsonObject:
    checkout = values.get("checkout")
    resolved = checkout.expanduser().resolve() if isinstance(checkout, Path) else None
    pr_value = values.get("pr")
    hub_value = values.get("hub")
    hub = hub_value.expanduser().resolve() if isinstance(hub_value, Path) else None
    checks: tuple[tuple[bool, str, str], ...] = (
        (resolved is not None and resolved.is_dir(), "checkout", "existing_directory"),
        (
            resolved is not None and not state_path.resolve().is_relative_to(resolved),
            "state",
            "outside_checkout",
        ),
        (_valid(values.get("repo"), _REPO), "repo", "owner_name"),
        (isinstance(pr_value, int) and pr_value > 0, "pr", "positive_integer"),
        (_valid(values.get("branch")), "branch", "branch_name"),
        (_valid(values.get("pin"), _SHA), "pin", "full_lowercase_sha1"),
        (_valid(values.get("session_id")), "session_id", "cline_session_id"),
        (hub is not None and hub.is_file(), "hub", "existing_file"),
        (_valid(values.get("author")) and _valid(values.get("operator")), "author", "author_login"),
        (
            resolved is not None and _git_branch(str(resolved)) == values.get("branch"),
            "branch",
            "checkout_current_branch",
        ),
    )
    for valid, field, rule in checks:
        if not valid:
            raise ReviewWakeError("review_wake.enrollment", f"/enrollment/{field}", rule)
    fields = ("repo", "pr", "branch", "pin", "session_id", "author", "operator", "harness_run")
    return {
        "checkout": str(resolved),
        **{key: values.get(key) for key in fields},
        "hub": str(hub) if hub is not None else "",
        "shared_account_authorized": bool(values.get("authorize_shared_account")),
    }


class _Hub:
    def __init__(self, discovery: Path, checkout: str, branch: str, session: str) -> None:
        try:
            value = _dict(json.loads(discovery.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            raise _HubError("hub_discovery_unreadable") from None
        if not value:
            raise _HubError("hub_discovery_invalid")
        url, token = value.get("url"), value.get("authToken")
        if not isinstance(url, str) or not isinstance(token, str):
            raise _HubError("hub_discovery_invalid")
        parsed = urlsplit(url)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "ws" or not loopback or parsed.port is None:
            raise _HubError("hub_loopback_required")
        self.checkout = Path(checkout).resolve()
        self.branch, self.session_id, self.token = branch, session, token
        self.client_id = f"kotekomi-review-wake-{os.getpid()}"
        self.events: list[JsonObject] = []
        try:
            self.socket = socket.create_connection(
                (parsed.hostname, parsed.port), timeout=_HUB_TIMEOUT
            )
        except OSError:
            raise _HubError("hub_unavailable") from None
        self.socket.settimeout(_HUB_TIMEOUT)
        self.reader = self.socket.makefile("rb")
        try:
            self._open(parsed.path or "/", cast(str, parsed.hostname), parsed.port)
        except OSError:
            self.close()
            raise _HubError("hub_unavailable") from None
        except _HubError:
            self.close()
            raise

    def _open(self, path: str, host: str, port: int) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: cline-hub-auth.{self.token}\r\n\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        if b" 101 " not in self.reader.readline(1024):
            raise _HubError("hub_handshake_rejected")
        while self.reader.readline(8192) not in {b"\r\n", b""}:
            pass
        self._call(
            "client.register",
            {
                "clientId": self.client_id,
                "clientType": "kotekomi-review-wake",
                "transport": "native",
                "workspaceContext": {
                    "workspaceRoot": str(self.checkout),
                    "cwd": str(self.checkout),
                },
            },
            None,
            "kotekomi-register",
        )
        self._send(
            {"kind": "stream.subscribe", "clientId": self.client_id, "sessionId": self.session_id}
        )

    def _read(self, size: int) -> bytes:
        data = self.reader.read(size)
        if len(data) != size:
            raise _HubError("hub_connection_closed")
        return data

    def _frame(self) -> tuple[int, bytes]:
        while True:
            head = self._read(2)
            opcode, size = head[0] & 15, head[1] & 127
            if size in {126, 127}:
                size = int.from_bytes(self._read(2 if size == 126 else 8), "big")
            mask = self._read(4) if head[1] & 128 else None
            data = self._read(size)
            if mask is not None:
                data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
            if opcode == 8:
                raise _HubError("hub_connection_closed")
            if opcode != 9:
                return opcode, data
            self._write(data, 10)

    def _write(self, data: bytes, opcode: int) -> None:
        size = len(data)
        second = size if size < 126 else 126 if size < 65536 else 127
        extra = b"" if size < 126 else size.to_bytes(2 if size < 65536 else 8, "big")
        mask = os.urandom(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
        self.socket.sendall(bytes([0x80 | opcode, 0x80 | second]) + extra + mask + masked)

    def _send(self, value: JsonObject) -> None:
        self._write(json.dumps(value).encode("utf-8"), 1)

    def close(self) -> None:
        self.reader.close()
        self.socket.close()

    def _call(
        self,
        command: str,
        payload: JsonObject | None,
        session: str | None,
        request: str,
        timeout: float = _HUB_TIMEOUT,
    ) -> JsonObject:
        self._send(
            {
                "kind": "command",
                "envelope": {
                    "version": "v1",
                    "command": command,
                    "requestId": request,
                    "clientId": self.client_id,
                    "sessionId": session,
                    "timeoutMs": int(timeout * 1000),
                    "payload": payload,
                },
            }
        )
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                self.socket.settimeout(max(0.1, deadline - time.monotonic()))
                _, data = self._frame()
                frame = json.loads(data)
                if not isinstance(frame, dict):
                    raise _HubError("hub_protocol_invalid")
                reply = cast(JsonObject, frame)
                value = _dict(reply.get("envelope"))
                if not value:
                    continue
                if reply.get("kind") == "reply" and value.get("requestId") == request:
                    if not value.get("ok"):
                        raise _HubError(f"hub_{command.replace('.', '_')}_rejected")
                    return _dict(value.get("payload"))
                if reply.get("kind") == "event":
                    self.events.append(value)
        except TimeoutError:
            raise _HubError("hub_timeout") from None
        raise _HubError("hub_timeout")

    def status(self) -> str:
        payload = self._call("session.get", {}, self.session_id, "kotekomi-session")
        row = _dict(payload.get("session"))
        if row.get("sessionId") != self.session_id:
            raise _HubError("session_binding_unproven")
        root = row.get("cwd") or row.get("workspaceRoot")
        git = _dict(_dict(row.get("metadata")).get("git"))
        value = row.get("status")
        if (
            not isinstance(root, str)
            or Path(root).expanduser().resolve() != self.checkout
            or git.get("branch") != self.branch
            or not isinstance(value, str)
        ):
            raise _HubError("session_binding_unproven")
        if value == "failed":
            raise _HubError("session_unavailable")
        return value

    def send(self, message: str, comment_id: int) -> None:
        request = f"kotekomi-send-{comment_id}"
        prompt: JsonObject = {"prompt": message, "delivery": "queue", "timeoutSeconds": 60}
        self._call("session.send_input", prompt, self.session_id, request, 30.0)
        query: JsonObject = {"sessionId": self.session_id}
        payload = self._call(
            "session.messages", query, self.session_id, f"kotekomi-messages-{comment_id}"
        )
        started = sum(
            (event.get("event"), event.get("requestId"), event.get("sessionId"))
            == ("run.started", request, self.session_id)
            for event in self.events
        )
        if started != 1:
            raise _HubError("run_started_unconfirmed")
        messages = payload.get("messages")
        rows = cast(list[object], messages) if isinstance(messages, list) else []
        matches = [row for row in rows if message in json.dumps(row, sort_keys=True)]
        if len(matches) != 1:
            raise _HubError("duplicate_transcript_entry" if matches else "transcript_entry_missing")


def _check(state_path: Path, data: JsonObject, enrollment: JsonObject) -> tuple[int, JsonObject]:
    alerts = cast(dict[str, JsonObject], data["alerts"])
    for record in alerts.values():
        if record.get("status") == "sending":
            record["status"], record["detail"] = "unknown", "send_outcome_unknown"
    _save(state_path, data)
    checkout, repo = str(enrollment["checkout"]), str(enrollment["repo"])
    branch, number = str(enrollment["branch"]), cast(int, enrollment["pr"])
    if _git_branch(checkout) != branch:
        return 0, _suppressed("review_wake.checkout_branch", "current_branch_matches_enrollment")
    pull = _gh("api", f"repos/{repo}/pulls/{number}")
    if not isinstance(pull, dict):
        raise ReviewWakeError("review_wake.github", "/github/pull", "object")
    pr = cast(JsonObject, pull)
    if pr.get("state") != "open":
        return 0, _suppressed("review_wake.pr", "open_pull_request")
    if pr.get("number") != number:
        raise ReviewWakeError("review_wake.github", "/github/pull", "enrolled_pull_request")
    head = cast(JsonObject, pr["head"]).get("sha") if isinstance(pr.get("head"), dict) else None
    body = pr.get("body")
    section = _HANDOFF.search(body) if isinstance(body, str) else None
    found = _PIN.findall(section.group(1)) if section is not None else []
    pin = found[0] if len(found) == 1 else None
    endpoint = f"repos/{repo}/issues/{number}/comments?per_page=100"
    page_value = _gh("api", endpoint, "--paginate", "--slurp")
    if not isinstance(page_value, list):
        raise ReviewWakeError("review_wake.github", "/github/comments", "comment_pages")
    pages = cast(list[object], page_value)
    if not all(isinstance(page, list) for page in pages):
        raise ReviewWakeError("review_wake.github", "/github/comments", "comment_pages")
    page_rows = cast(list[list[object]], pages)
    delivered: list[JsonObject] = []
    final = {"delivered", "notified", "blocked", "stale", "invalid", "unknown", "failed"}
    for comment in (item for page in page_rows for item in page):
        outcome = _evaluate(enrollment, comment, head, pin)
        if outcome is None:
            continue
        key = str(outcome.pop("_id"))
        prior = alerts.get(key)
        if prior is not None and (
            prior.get("status") in final
            or (prior.get("status") == "queued" and outcome["status"] == "queued")
        ):
            continue
        if outcome["status"] == "eligible":
            outcome = _deliver(state_path, data, enrollment, key, outcome)
        alerts[key] = outcome
        if outcome["status"] not in {"stale", "invalid"}:
            delivered.append({"comment_id": int(key), **outcome})
    _save(state_path, data)
    return 0, {
        "schema_version": 1,
        "status": "processed",
        "target": {
            "status": "proven",
            "detail": "one_matching_transcript_entry",
            "delivery": "session-input",
        }
        if any(item["status"] == "delivered" for item in delivered)
        else dict(_TARGET),
        "alerts": delivered,
    }


def _evaluate(
    enrollment: JsonObject,
    comment: object,
    head: object,
    canonical_pin: str | None,
) -> JsonObject | None:
    if not isinstance(comment, dict):
        return None
    item = cast(JsonObject, comment)
    comment_id, body, user = item.get("id"), item.get("body"), item.get("user")
    if not isinstance(comment_id, int) or comment_id < 1 or not isinstance(body, str):
        return None
    if not isinstance(user, dict) or cast(JsonObject, user).get("login") != enrollment["author"]:
        return None
    if "kotekomi-review-request:" not in body:
        return None
    repo = str(enrollment["repo"])
    pin = str(enrollment["pin"])
    number = cast(int, enrollment["pr"])
    url = f"https://github.com/{repo}/pull/{number}#issuecomment-{comment_id}"
    found = _MARKER.findall(body)
    if len(found) != 1:
        return _outcome(comment_id, url, "invalid", "exactly_one_versioned_marker")
    marker_repo, marker_pr, reviewed, pinned = found[0]
    if marker_repo != repo or int(cast(str, marker_pr)) != number:
        return _outcome(comment_id, url, "invalid", "marker_targets_enrollment")
    if not isinstance(head, str) or reviewed != head:
        return _outcome(comment_id, url, "stale", "reviewed_head_is_current")
    if canonical_pin is None or pinned != canonical_pin or pinned != pin:
        return _outcome(comment_id, url, "stale", "pinned_spec_is_canonical")
    shared = enrollment["author"] == enrollment["operator"]
    if shared and not enrollment["shared_account_authorized"]:
        return _outcome(comment_id, url, "notified", "shared_account_requires_authorization")
    return _outcome(comment_id, url, "eligible", "authorized_marker")


def _deliver(
    state_path: Path, data: JsonObject, enrollment: JsonObject, key: str, outcome: JsonObject
) -> JsonObject:
    hub_value = enrollment.get("hub")
    if not isinstance(hub_value, str):
        return {**outcome, "status": "blocked", "detail": "hub_discovery_invalid"}
    hub: _Hub | None = None
    intent = False
    try:
        hub = _Hub(
            Path(hub_value),
            str(enrollment["checkout"]),
            str(enrollment["branch"]),
            str(enrollment["session_id"]),
        )
        status = hub.status()
        if status in {"running", "pending"}:
            return {**outcome, "status": "queued", "detail": "target_busy"}
        if status not in {"idle", "completed", "aborted"}:
            return {**outcome, "status": "blocked", "detail": "session_binding_unproven"}
        alerts = cast(dict[str, JsonObject], data["alerts"])
        alerts[key] = {**outcome, "status": "sending", "detail": "send_intent_recorded"}
        _save(state_path, data)
        intent = True
        hub.send(str(outcome["message"]), int(key))
        return {**outcome, "status": "delivered", "detail": "one_matching_transcript_entry"}
    except _HubError as error:
        detail = str(error)
        if intent:
            detail = "hub_send_rejected" if detail.endswith("_rejected") else detail
            status = "failed" if detail == "hub_send_rejected" else "unknown"
            return {**outcome, "status": status, "detail": detail}
        if detail in {"hub_unavailable", "hub_timeout", "hub_discovery_unreadable"}:
            return {**outcome, "status": "queued", "detail": "target_unavailable"}
        return {**outcome, "status": "blocked", "detail": detail}
    finally:
        if hub is not None:
            hub.close()


def _gh(*arguments: str) -> object:
    executable = shutil.which("gh")
    if executable is None:
        raise ReviewWakeError("review_wake.github", "/github", "authenticated_cli")
    result = _run([executable, *arguments], None)
    if result.returncode != 0:
        raise ReviewWakeError("review_wake.github", "/github", "authenticated_read")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ReviewWakeError("review_wake.github", "/github", "json_response") from None


def _run(arguments: list[str], cwd: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, check=False)


def _git_branch(checkout: str) -> str:
    result = _run(["git", "-C", checkout, "branch", "--show-current"], None)
    return result.stdout.strip() if result.returncode == 0 else ""


def _load(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ReviewWakeError("review_wake.state", "/state", "readable_json") from None
    if not isinstance(value, dict):
        raise ReviewWakeError("review_wake.state", "/state", "enrollment_and_alerts")
    data = cast(JsonObject, value)
    if not isinstance(data.get("enrollment"), dict) or not isinstance(data.get("alerts"), dict):
        raise ReviewWakeError("review_wake.state", "/state", "enrollment_and_alerts")
    return data


def _save(path: Path, data: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _suppressed(code: str, rule: str) -> JsonObject:
    return {
        "schema_version": 1,
        "status": "suppressed",
        "diagnostics": [{"code": code, "location": "/checkout", "rule": rule}],
        "alerts": [],
    }


def _outcome(comment_id: int, url: str, status: str, detail: str) -> JsonObject:
    message = f"New review comment on your current PR: {url}. Please check it."
    return {"_id": comment_id, "status": status, "url": url, "detail": detail, "message": message}


def _valid(value: object, pattern: re.Pattern[str] | None = None) -> bool:
    text = value.strip() if isinstance(value, str) else None
    return bool(text) and (pattern is None or pattern.fullmatch(text) is not None)
