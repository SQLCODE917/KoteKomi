"""Foreground review wake for one enrolled PR and terminal Cline session."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

type JsonObject = dict[str, object]

_MARKER = re.compile(
    r"<!-- kotekomi-review-request:v1 "
    r"repo=(\S+) pr=(\d+) head=([0-9a-f]{40}) pin=([0-9a-f]{40}) -->"
)
_HANDOFF = re.compile(r"^## +Current Handoff *$(.*?)(?=^#{1,2} |\Z)", re.M | re.S)
_PIN = re.compile(r"^ *[-*] +Spec commit *: *`?([0-9a-f]{40})`? *$", re.M)
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_TARGET = {
    "status": "unproven",
    "detail": "same_session_delivery_unproven",
    "delivery": "notification-only",
}


class ReviewWakeError(Exception):
    def __init__(self, code: str, location: str, rule: str) -> None:
        self.code, self.location, self.rule = code, location, rule


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
        "shared_account_authorized": bool(values.get("authorize_shared_account")),
    }


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
        alerts[key] = outcome
        if outcome["status"] not in {"stale", "invalid"}:
            delivered.append({"comment_id": int(key), **outcome})
    _save(state_path, data)
    return 0, {
        "schema_version": 1,
        "status": "processed",
        "target": _TARGET,
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
    return _outcome(comment_id, url, "blocked", "same_session_delivery_unproven")


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
