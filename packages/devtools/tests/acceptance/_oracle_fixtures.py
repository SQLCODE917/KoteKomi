from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "KoteKomi Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "KoteKomi Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


def write_fixture_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(
    cwd: Path,
    args: Sequence[str],
    expected_exit_code: int | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    if expected_exit_code is not None and result.returncode != expected_exit_code:
        raise AssertionError(
            f"Command failed: {' '.join(args)}\n"
            f"expected exit code: {expected_exit_code}\n"
            f"actual exit code: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    return result


def run_json_command(
    cwd: Path,
    args: Sequence[str],
    expected_exit_code: int | None = 0,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[int, Any]:
    result = run_command(cwd, args, expected_exit_code, env=env)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"Command did not emit JSON: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        ) from error

    return result.returncode, payload


def _git_command(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        env=_GIT_ENV,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    return result


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _git_command(repo, *args)


def git_output(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def init_git_repo(repo: Path) -> str:
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "KoteKomi Test")
    git(repo, "config", "user.email", "test@example.invalid")
    write_fixture_text(repo / ".gitignore", "")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-m", "Initial fixture")
    return git_output(repo, "rev-parse", "HEAD")


def status_short(repo: Path) -> str:
    return git_output(repo, "status", "--porcelain=v1", "--untracked-files=all")


def index_sha(repo: Path) -> str:
    index = repo / ".git" / "index"
    return sha256_file(index) if index.exists() else ""


def status_then_index_baseline(repo: Path) -> tuple[str, str]:
    return status_short(repo), index_sha(repo)


def assert_status_and_index_unchanged(
    repo: Path,
    baseline: tuple[str, str],
) -> None:
    assert status_then_index_baseline(repo) == baseline


def protected_artifact(path: Path, kind: str) -> dict[str, str]:
    return {"kind": kind, "path": str(path), "sha256": sha256_file(path)}


def render_manifest(data: Mapping[str, Any]) -> str:
    lines: list[str] = []

    for key, value in data.items():
        if isinstance(value, Mapping):
            continue
        if _is_table_array(value):
            continue
        lines.append(f"{key} = {_toml_value(value)}")

    for key, value in data.items():
        if isinstance(value, Mapping):
            table = cast(Mapping[str, Any], value)
            lines.extend(("", f"[{key}]"))
            lines.extend(
                f"{child_key} = {_toml_value(child_value)}"
                for child_key, child_value in table.items()
            )
        elif _is_table_array(value):
            tables = cast(list[Mapping[str, Any]], value)
            for item in tables:
                lines.extend(("", f"[[{key}]]"))
                lines.extend(
                    f"{child_key} = {_toml_value(child_value)}"
                    for child_key, child_value in item.items()
                )

    return "\n".join(lines) + "\n"


def _is_table_array(value: Any) -> bool:
    if not isinstance(value, list):
        return False

    items = cast(list[Any], value)
    return bool(items) and isinstance(items[0], Mapping)


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        items = cast(list[Any], value)
        return "[" + ", ".join(_toml_value(item) for item in items) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")
