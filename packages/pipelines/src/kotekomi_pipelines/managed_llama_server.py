"""User-scoped launchd management for the shared llama-server router."""

from __future__ import annotations

import os
import plistlib
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SERVICE_LABEL = "com.dserbarinov.llama-server"
PATH_GUARD_MARKER = "KOTEKOMI_MANAGED_LLAMA_SERVER"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_CONTEXT_TOKENS = 16384
DEFAULT_SLOTS = 1
DEFAULT_MODELS_MAX = 1


class ProcessRunner(Protocol):
    def run(self, args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class ManagedLlamaServerConfig:
    executable_path: Path
    home_path: Path
    context_tokens: int = DEFAULT_CONTEXT_TOKENS
    slots: int = DEFAULT_SLOTS
    models_max: int = DEFAULT_MODELS_MAX
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    def validate(self) -> None:
        if not self.executable_path.is_absolute():
            raise ValueError("llama-server executable path must be absolute.")
        if not self.executable_path.is_file():
            raise FileNotFoundError(
                f"llama-server executable does not exist: {self.executable_path}"
            )
        if self.context_tokens <= 0 or self.slots <= 0 or self.models_max <= 0 or self.port <= 0:
            raise ValueError("Managed llama-server numeric settings must be positive.")
        if self.host != DEFAULT_HOST:
            raise ValueError("Managed llama-server must bind only 127.0.0.1.")

    @property
    def agent_path(self) -> Path:
        return self.home_path / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"

    @property
    def log_directory(self) -> Path:
        return self.home_path / "Library" / "Logs" / "llama-server"


@dataclass(frozen=True)
class ManagedLlamaServerStatus:
    installed: bool
    loaded: bool
    path_guarded: bool
    agent_path: Path


class SubprocessRunner:
    def run(self, args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(args, check=check, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or "no diagnostic output"
            raise RuntimeError(f"launchctl command failed: {' '.join(args)}: {detail}") from exc


def render_launch_agent_plist(config: ManagedLlamaServerConfig) -> bytes:
    config.validate()
    plist = {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [
            str(config.executable_path),
            "-c",
            str(config.context_tokens),
            "-np",
            str(config.slots),
            "--models-max",
            str(config.models_max),
            "--slots",
            "--jinja",
            "--host",
            config.host,
            "--port",
            str(config.port),
        ],
        "EnvironmentVariables": {"HOME": str(config.home_path)},
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(config.log_directory / "stdout.log"),
        "StandardErrorPath": str(config.log_directory / "stderr.log"),
    }
    return plistlib.dumps(plist, sort_keys=True)


def install_managed_llama_server(
    config: ManagedLlamaServerConfig,
    *,
    runner: ProcessRunner | None = None,
    uid: int | None = None,
) -> Path:
    config.validate()
    config.agent_path.parent.mkdir(parents=True, exist_ok=True)
    config.log_directory.mkdir(parents=True, exist_ok=True)
    _install_path_guard(config)
    config.agent_path.write_bytes(render_launch_agent_plist(config))
    active_runner = runner or SubprocessRunner()
    domain = _launchd_domain(uid)
    active_runner.run(["launchctl", "bootout", f"{domain}/{SERVICE_LABEL}"], check=False)
    _wait_for_service_unload(active_runner, domain)
    active_runner.run(["launchctl", "bootstrap", domain, str(config.agent_path)], check=True)
    return config.agent_path


def uninstall_managed_llama_server(
    *,
    home_path: Path,
    runner: ProcessRunner | None = None,
    uid: int | None = None,
) -> Path:
    agent_path = home_path / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"
    active_runner = runner or SubprocessRunner()
    active_runner.run(
        ["launchctl", "bootout", f"{_launchd_domain(uid)}/{SERVICE_LABEL}"], check=False
    )
    if agent_path.exists():
        agent_path.unlink()
    _restore_path_launcher(home_path)
    return agent_path


def get_managed_llama_server_status(
    *,
    home_path: Path,
    runner: ProcessRunner | None = None,
    uid: int | None = None,
) -> ManagedLlamaServerStatus:
    agent_path = home_path / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"
    active_runner = runner or SubprocessRunner()
    result = active_runner.run(
        ["launchctl", "print", f"{_launchd_domain(uid)}/{SERVICE_LABEL}"],
        check=False,
    )
    return ManagedLlamaServerStatus(
        installed=agent_path.is_file(),
        loaded=result.returncode == 0,
        path_guarded=_is_path_guard(_path_launcher(home_path)),
        agent_path=agent_path,
    )


def _launchd_domain(uid: int | None) -> str:
    return f"gui/{os.getuid() if uid is None else uid}"


def _wait_for_service_unload(runner: ProcessRunner, domain: str) -> None:
    target = f"{domain}/{SERVICE_LABEL}"
    deadline = time.monotonic() + 5.0
    while runner.run(["launchctl", "print", target], check=False).returncode == 0:
        if time.monotonic() >= deadline:
            raise RuntimeError(f"launchd did not unload managed llama-server: {target}")
        time.sleep(0.1)


def _path_launcher(home_path: Path) -> Path:
    return home_path / ".local" / "bin" / "llama-server"


def _install_path_guard(config: ManagedLlamaServerConfig) -> None:
    launcher_path = _path_launcher(config.home_path)
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    if launcher_path.exists() or launcher_path.is_symlink():
        if _is_path_guard(launcher_path):
            return
        if (
            not launcher_path.is_symlink()
            or launcher_path.resolve() != config.executable_path.resolve()
        ):
            raise ValueError(
                f"Refusing to replace an unmanaged llama-server PATH launcher: {launcher_path}"
            )
        launcher_path.unlink()
    launcher_path.write_text(_path_guard_contents(config.executable_path), encoding="utf-8")
    launcher_path.chmod(0o755)


def _restore_path_launcher(home_path: Path) -> None:
    launcher_path = _path_launcher(home_path)
    original_path = _guarded_original_path(launcher_path)
    if original_path is None:
        return
    launcher_path.unlink()
    launcher_path.symlink_to(original_path)


def _is_path_guard(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        return PATH_GUARD_MARKER in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _guarded_original_path(path: Path) -> Path | None:
    if not _is_path_guard(path):
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# original-path: "):
            return Path(line.removeprefix("# original-path: "))
    raise ValueError(f"Managed llama-server PATH guard has no original path: {path}")


def _path_guard_contents(original_path: Path) -> str:
    return "\n".join(
        (
            "#!/bin/sh",
            f"# {PATH_GUARD_MARKER}",
            f"# original-path: {original_path}",
            "echo 'llama-server is managed by launchd; use an HTTP client at "
            "http://127.0.0.1:8080/v1.' >&2",
            "exit 64",
            "",
        )
    )
