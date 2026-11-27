"""Foreground review wake for one enrolled PR and terminal Cline session."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.sync.client import connect
from websockets.sync.connection import Connection
from websockets.typing import Subprotocol

type JsonObject = dict[str, object]

_MARKER = re.compile(
    r"<!-- kotekomi-review-request:v1 "
    r"repo=(\S+) pr=(\d+) head=([0-9a-f]{40}) pin=([0-9a-f]{40}) -->"
)
_HANDOFF = re.compile(r"^## +Current Handoff *$(.*?)(?=^#{1,2} |\Z)", re.M | re.S)
_PIN = re.compile(r"^ *[-*] +Spec commit *: *`?([0-9a-f]{40})`? *$", re.M)
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_USER_INPUT = re.compile(r'<user_input mode="(?:act|plan|yolo)">(.*)</user_input>', re.S)
_HUB_TIMEOUT = 5.0
_MAX_MESSAGE = 16 * 1024 * 1024
_MAX_QUEUE = 256
_RECEIPT_DEADLINE = 30.0
_RECEIPT_SAMPLE_TIMEOUT = 5.0
_RECEIPT_POLL = 1.0
_HUB_LOGGER = logging.Logger("kotekomi.review_wake.hub_transport", level=logging.CRITICAL + 1)
_HUB_LOGGER.addHandler(logging.NullHandler())
_HUB_LOGGER.propagate = False
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
        if not isinstance(url, str) or not isinstance(token, str) or not token:
            raise _HubError("hub_discovery_invalid")
        parsed = urlsplit(url)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "ws" or not loopback or parsed.port is None:
            raise _HubError("hub_loopback_required")
        self.checkout = Path(checkout).resolve()
        self.branch, self.session_id, self.token = branch, session, token
        self.client_id = f"kotekomi-review-wake-{os.getpid()}"
        self.events: list[JsonObject] = []
        expected = f"cline-hub-auth.{token}"
        try:
            self.connection: Connection = connect(
                url,
                subprotocols=[Subprotocol(expected)],
                compression=None,
                proxy=None,
                open_timeout=_HUB_TIMEOUT,
                close_timeout=_HUB_TIMEOUT,
                ping_interval=None,
                ping_timeout=None,
                max_size=_MAX_MESSAGE,
                max_queue=_MAX_QUEUE,
                logger=_HUB_LOGGER,
            )
        except TimeoutError:
            raise _HubError("hub_unavailable") from None
        except OSError:
            raise _HubError("hub_unavailable") from None
        except WebSocketException:
            raise _HubError("hub_handshake_rejected") from None
        if self.connection.subprotocol != expected:
            self.close()
            raise _HubError("hub_auth_rejected")
        try:
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
                {
                    "kind": "stream.subscribe",
                    "clientId": self.client_id,
                    "sessionId": self.session_id,
                }
            )
        except _HubError:
            self.close()
            raise

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
        while time.monotonic() < deadline:
            try:
                raw = self.connection.recv(timeout=max(0.1, deadline - time.monotonic()))
            except TimeoutError:
                raise _HubError("hub_timeout") from None
            except ConnectionClosed as error:
                if error.code == 1009:
                    raise _HubError("hub_message_too_large") from None
                raise _HubError("hub_connection_closed") from None
            except (OSError, WebSocketException):
                raise _HubError("hub_connection_closed") from None
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                raise _HubError("hub_protocol_invalid") from None
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
        raise _HubError("hub_timeout")

    def _send(self, value: JsonObject) -> None:
        try:
            self.connection.send(json.dumps(value))
        except ConnectionClosed:
            raise _HubError("hub_connection_closed") from None
        except (OSError, WebSocketException):
            raise _HubError("hub_send_failed") from None

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

    def history(self, comment_id: int) -> tuple[list[JsonObject], JsonObject]:
        payload = self._call(
            "session.messages",
            {"sessionId": self.session_id},
            self.session_id,
            f"kotekomi-history-{comment_id}",
        )
        rows = _transcript_rows(payload, self.session_id)
        return rows, {"count": len(rows), "sha256": _history_digest(rows)}

    def send(self, message: str, comment_id: int, boundary: JsonObject) -> JsonObject:
        request = f"kotekomi-send-{comment_id}"
        prompt: JsonObject = {"prompt": message, "delivery": "queue", "timeoutSeconds": 60}
        self.events.clear()
        self._call("session.send_input", prompt, self.session_id, request, 30.0)
        deadline = time.monotonic() + _RECEIPT_DEADLINE
        count = cast(int, boundary["count"])
        digest = cast(str, boundary["sha256"])
        confirmed: JsonObject | None = None
        event_seen = False
        receipt_seen = False
        sample = 0
        while time.monotonic() < deadline:
            sample += 1
            remaining = deadline - time.monotonic()
            try:
                payload = self._call(
                    "session.messages",
                    {"sessionId": self.session_id},
                    self.session_id,
                    f"kotekomi-receipt-{comment_id}-{sample}",
                    min(remaining, _RECEIPT_SAMPLE_TIMEOUT),
                )
            except _HubError as error:
                if str(error) == "hub_timeout":
                    continue
                raise
            rows = _transcript_rows(payload, self.session_id)
            if len(rows) < count or _history_digest(rows[:count]) != digest:
                raise _HubError("history_changed_unconfirmed")
            matches = [
                row
                for row in rows[count:]
                if row.get("role") == "user" and _message_text(row) == message
            ]
            if len(matches) > 1:
                raise _HubError("duplicate_transcript_entry")
            event_seen = _correlated_started(self.events, request, self.session_id)
            if matches:
                receipt_seen = True
                if event_seen:
                    if confirmed is None:
                        confirmed = matches[0]
                    elif confirmed.get("id") != matches[0].get("id"):
                        raise _HubError("duplicate_transcript_entry")
                    else:
                        return {
                            "history_count": count,
                            "history_sha256": digest,
                            "received_message_id": matches[0]["id"],
                        }
                elif confirmed is not None:
                    raise _HubError("history_changed_unconfirmed")
            elif confirmed is not None:
                raise _HubError("history_changed_unconfirmed")
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(_RECEIPT_POLL, remaining))
        if receipt_seen:
            raise _HubError("run_started_unconfirmed")
        if event_seen:
            raise _HubError("transcript_entry_missing")
        raise _HubError("run_started_unconfirmed")

    def close(self) -> None:
        self.connection.close()


def _correlated_started(events: list[JsonObject], request: str, session_id: str) -> bool:
    matched = False
    for event in events:
        if event.get("event") != "run.started":
            continue
        payload = _dict(event.get("payload"))
        if payload.get("requestId") != request:
            continue
        if event.get("sessionId") != session_id:
            raise _HubError("event_identity_unproven")
        matched = True
    return matched


def _transcript_rows(payload: JsonObject, session_id: str) -> list[JsonObject]:
    if payload.get("sessionId") != session_id:
        raise _HubError("transcript_identity_unproven")
    return _history_rows(payload)


def _history_rows(payload: JsonObject) -> list[JsonObject]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise _HubError("transcript_unreadable")
    rows: list[JsonObject] = []
    for item in cast(list[object], messages):
        if not isinstance(item, dict):
            raise _HubError("history_unverifiable")
        row = cast(JsonObject, item)
        message_id, role, content = row.get("id"), row.get("role"), row.get("content")
        if (
            not isinstance(message_id, str)
            or not message_id
            or role not in {"user", "assistant", "tool"}
            or not isinstance(content, (str, list))
        ):
            raise _HubError("history_unverifiable")
        rows.append(row)
    ids = [cast(str, row["id"]) for row in rows]
    if len(set(ids)) != len(ids):
        raise _HubError("history_duplicate_ids")
    return rows


def _history_digest(rows: list[JsonObject]) -> str:
    value = [
        {"id": row.get("id"), "role": row.get("role"), "content": row.get("content")}
        for row in rows
    ]
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _message_text(row: JsonObject) -> str | None:
    content = row.get("content")
    if not isinstance(content, list):
        return None
    rows = cast(list[object], content)
    if len(rows) != 1:
        return None
    block = _dict(rows[0])
    value = block.get("text")
    if block.get("type") != "text" or not isinstance(value, str):
        return None
    wrapped = _USER_INPUT.fullmatch(value)
    return wrapped.group(1) if wrapped else value


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


def _fresh_outcome(enrollment: JsonObject, key: str) -> JsonObject:
    repo, number = str(enrollment["repo"]), cast(int, enrollment["pr"])
    url = f"https://github.com/{repo}/pull/{number}#issuecomment-{key}"
    pull = _gh("api", f"repos/{repo}/pulls/{number}")
    if not isinstance(pull, dict):
        raise ReviewWakeError("review_wake.github", "/github/pull", "object")
    pr = cast(JsonObject, pull)
    if pr.get("state") != "open":
        return _outcome(int(key), url, "blocked", "pull_request_closed")
    if pr.get("number") != number:
        return _outcome(int(key), url, "invalid", "marker_targets_enrollment")
    head = cast(JsonObject, pr["head"]).get("sha") if isinstance(pr.get("head"), dict) else None
    body = pr.get("body")
    section = _HANDOFF.search(body) if isinstance(body, str) else None
    found = _PIN.findall(section.group(1)) if section is not None else []
    pin = found[0] if len(found) == 1 else None
    comment = _gh("api", f"repos/{repo}/issues/comments/{key}")
    if not isinstance(comment, dict):
        return _outcome(int(key), url, "invalid", "comment_missing")
    item = cast(JsonObject, comment)
    expected = f"https://api.github.com/repos/{repo}/issues/{number}"
    if item.get("issue_url") != expected:
        return _outcome(int(key), url, "invalid", "comment_targets_enrollment")
    outcome = _evaluate(enrollment, item, head, pin)
    if outcome is None:
        return _outcome(int(key), url, "invalid", "authorized_marker")
    return outcome


def _deliver(
    state_path: Path, data: JsonObject, enrollment: JsonObject, key: str, outcome: JsonObject
) -> JsonObject:
    hub_value = enrollment.get("hub")
    if not isinstance(hub_value, str):
        return {**outcome, "status": "blocked", "detail": "hub_discovery_invalid"}
    hub: _Hub | None = None
    intent = False
    record = outcome
    try:
        fresh = _fresh_outcome(enrollment, key)
        if fresh.get("status") != "eligible":
            return fresh
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
        _, boundary = hub.history(int(key))
        status = hub.status()
        if status in {"running", "pending"}:
            return {**outcome, "status": "queued", "detail": "target_busy"}
        if status not in {"idle", "completed", "aborted"}:
            return {**outcome, "status": "blocked", "detail": "session_binding_unproven"}
        fresh = _fresh_outcome(enrollment, key)
        if fresh.get("status") != "eligible":
            return fresh
        record = {
            **outcome,
            "history_count": boundary["count"],
            "history_sha256": boundary["sha256"],
        }
        alerts = cast(dict[str, JsonObject], data["alerts"])
        alerts[key] = {**record, "status": "sending", "detail": "send_intent_recorded"}
        _save(state_path, data)
        intent = True
        receipt = hub.send(str(outcome["message"]), int(key), boundary)
        return {
            **record,
            "status": "delivered",
            "detail": "one_matching_transcript_entry",
            **receipt,
        }
    except ReviewWakeError:
        return {**outcome, "status": "queued", "detail": "routing_unavailable"}
    except _HubError as error:
        detail = str(error)
        if intent:
            detail = "hub_send_rejected" if detail.endswith("_rejected") else detail
            status = "failed" if detail == "hub_send_rejected" else "unknown"
            return {**record, "status": status, "detail": detail}
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
