"""Read-only preflight for one PR Current Handoff against the current checkout."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tomllib
from pathlib import Path

from kotekomi_devtools.tdd_binding import derive_task_id

type Diagnostics = list[dict[str, str]]
type JsonObject = dict[str, object]

_SECTION = re.compile(r"^##\s+Current Handoff\s*$(.*?)(?=^#{1,2}\s+|\Z)", re.M | re.S)
_TDD_HEADING = re.compile(r"^\s{0,3}#+\s+(.+?)\s*#*\s*$")
_FIELD = re.compile(r"^\s*[-*]\s+(Status|Spec commit|TDD|Prerequisite)\s*:\s*(.*?)\s*$")
_SPEC_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_FIELDS = ("Status", "Spec commit", "TDD", "Prerequisite")
_HANDOFF = "/current_handoff"
_SPEC = "/current_handoff/spec_commit"
_TDD = "/current_handoff/tdd"
_IMPLEMENT = ("kotekomi-agent", "implement-tdd")


def preflight_handoff(description: Path) -> tuple[int, JsonObject]:
    """Check one declarative handoff without writing repository or state."""
    values, diagnostics = _read_handoff(description)
    if diagnostics:
        return _blocked(*diagnostics)
    spec_commit, tdd_path = values["Spec commit"], values["TDD"]
    root = _repository_root()
    if root is None:
        return _blocked(_diagnostic("repository_unavailable", "/repository", "repository_root"))
    resolved = _git("rev-parse", "--verify", f"{spec_commit}^{{commit}}")
    if resolved.stdout.decode().strip() != spec_commit:
        return _blocked(_diagnostic("spec_commit_unresolved", _SPEC, "pin_resolves"))
    if _git("merge-base", "--is-ancestor", spec_commit, "HEAD").returncode != 0:
        return _blocked(_diagnostic("spec_commit_unreachable", _SPEC, "pin_on_checkout_branch"))
    pinned_tdd = _git("show", f"{spec_commit}:{tdd_path}")
    if pinned_tdd.returncode != 0:
        return _blocked(_diagnostic("tdd_missing_at_pin", _TDD, "tdd_at_pin"))
    if _bytes(root / tdd_path) != pinned_tdd.stdout:
        return _blocked(_diagnostic("tdd_checkout_drift", _TDD, "tdd_matches_pin"))
    manifests = _manifests_at_pin(spec_commit, tdd_path)
    if len(manifests) != 1:
        code = "manifest_missing" if not manifests else "manifest_ambiguous"
        return _blocked(_diagnostic(code, "/manifest", "one_manifest_at_pin"))
    manifest_path, manifest_bytes, manifest = manifests[0]
    tdd_digest = hashlib.sha256(pinned_tdd.stdout).hexdigest()
    title = _tdd_title(pinned_tdd.stdout, Path(tdd_path).stem)
    expected_task_id = derive_task_id(title, tdd_digest)
    task_id = manifest.get("task_id")
    if (
        manifest.get("schema_version") != 2
        or manifest.get("tdd_sha256") != tdd_digest
        or not isinstance(task_id, str)
        or Path(manifest_path).stem != task_id
    ):
        return _blocked(_diagnostic("manifest_invalid", "/manifest", "task_manifest_v2_binds_tdd"))
    if task_id != expected_task_id:
        return _blocked(_diagnostic("manifest_invalid", "/manifest", "task_id_matches_tdd_binding"))
    if _bytes(root / manifest_path) != manifest_bytes:
        return _blocked(_diagnostic("manifest_checkout_drift", "/manifest", "manifest_matches_pin"))
    return 0, {
        "schema_version": 1,
        "status": "ready",
        "spec_commit": spec_commit,
        "tdd_path": tdd_path,
        "manifest_path": manifest_path,
        "task_id": task_id,
        "start_command": [*_IMPLEMENT, tdd_path, "--specification-commit", spec_commit],
        "diagnostics": [],
    }


def _read_handoff(description: Path) -> tuple[dict[str, str], Diagnostics]:
    try:
        text = description.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, [_diagnostic("description_unreadable", "/", "utf8_description")]
    sections = _SECTION.findall(text)
    if len(sections) != 1:
        code = "section_missing" if not sections else "section_duplicate"
        return {}, [_diagnostic(code, _HANDOFF, "exactly_one_current_handoff")]
    pairs = [
        (found.group(1), found.group(2).strip("`"))
        for line in sections[0].splitlines()
        if (found := _FIELD.match(line))
    ]
    values: dict[str, str] = {}
    diagnostics: Diagnostics = []
    for name, value in pairs:
        if name in values:
            diagnostics.append(_diagnostic("field_duplicate", _HANDOFF, name))
        else:
            values[name] = value
    for name in _FIELDS:
        if name not in values:
            diagnostics.append(_diagnostic("field_missing", _HANDOFF, name))
    if diagnostics:
        return values, diagnostics
    if values["Status"] != "ready":
        code = "status_blocked" if values["Status"] == "blocked" else "status_invalid"
        diagnostics.append(_diagnostic(code, f"{_HANDOFF}/status", "status_ready"))
    if not _SPEC_COMMIT.fullmatch(values["Spec commit"]):
        diagnostics.append(_diagnostic("spec_commit_invalid", _SPEC, "full_lowercase_sha1"))
    if not _repository_relative(values["TDD"]):
        diagnostics.append(_diagnostic("tdd_path_invalid", _TDD, "repository_relative_posix"))
    if values["Prerequisite"].lower() != "none":
        diagnostics.append(_diagnostic("prerequisite_pending", _HANDOFF + "/prerequisite", "none"))
    return values, diagnostics


def _manifests_at_pin(revision: str, tdd_path: str) -> list[tuple[str, bytes, JsonObject]]:
    listing = _git("ls-tree", "-r", "-z", "--name-only", revision, "--", ".agent/tasks")
    manifests: list[tuple[str, bytes, JsonObject]] = []
    for path in listing.stdout.decode().split("\0"):
        if not path.endswith(".toml"):
            continue
        blob = _git("show", f"{revision}:{path}")
        try:
            parsed = tomllib.loads(blob.stdout.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            continue
        if parsed.get("tdd_path") == tdd_path:
            manifests.append((path, blob.stdout, parsed))
    return manifests


def _tdd_title(content: bytes, fallback: str) -> str:
    for line in content.decode("utf-8", "replace").splitlines():
        found = _TDD_HEADING.match(line)
        if found and found.group(1).strip():
            return found.group(1).strip()
    return fallback


def _repository_root() -> Path | None:
    result = _git("rev-parse", "--show-toplevel")
    root = Path(result.stdout.decode().strip())
    return root if result.returncode == 0 and root.resolve() == Path.cwd().resolve() else None


def _repository_relative(path: str) -> bool:
    parts = path.split("/")
    valid = bool(path) and not path.startswith(("/", "~")) and "\\" not in path
    return valid and not {"", ".", ".."}.intersection(parts) and not set("*?[]").intersection(path)


def _bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return b""


def _blocked(*diagnostics: dict[str, str]) -> tuple[int, JsonObject]:
    return 1, {"schema_version": 1, "status": "blocked", "diagnostics": list(diagnostics)}


def _diagnostic(code: str, location: str, rule: str) -> dict[str, str]:
    return {"code": f"handoff.{code}", "location": location, "rule": rule}


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *arguments], capture_output=True, check=False)
