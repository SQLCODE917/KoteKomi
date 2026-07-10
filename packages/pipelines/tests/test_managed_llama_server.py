import plistlib
import subprocess
from pathlib import Path

import pytest
from kotekomi_pipelines.managed_llama_server import (
    SERVICE_LABEL,
    ManagedLlamaServerConfig,
    get_managed_llama_server_status,
    install_managed_llama_server,
    render_launch_agent_plist,
    uninstall_managed_llama_server,
)


class FakeRunner:
    def __init__(self, returncode: int = 0, print_returncode: int | None = None) -> None:
        self.returncode = returncode
        self.print_returncode = print_returncode
        self.calls: list[tuple[list[str], bool]] = []

    def run(self, args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, check))
        returncode = self.returncode
        if args[1] == "print":
            returncode = 1 if self.print_returncode is None else self.print_returncode
        return subprocess.CompletedProcess(args, returncode, "", "")


def service_config(tmp_path: Path) -> ManagedLlamaServerConfig:
    executable = tmp_path / "bin" / "llama-server"
    executable.parent.mkdir()
    executable.write_text("binary", encoding="utf-8")
    return ManagedLlamaServerConfig(executable_path=executable, home_path=tmp_path / "home")


def test_rendered_launch_agent_owns_one_local_router(tmp_path: Path) -> None:
    plist = plistlib.loads(render_launch_agent_plist(service_config(tmp_path)))

    assert plist["Label"] == SERVICE_LABEL
    assert plist["ProgramArguments"][1:] == [
        "-c",
        "16384",
        "-np",
        "1",
        "--models-max",
        "1",
        "--slots",
        "--jinja",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
    ]
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] is True


def test_install_uses_current_user_launchd_domain(tmp_path: Path) -> None:
    config = service_config(tmp_path)
    runner = FakeRunner()

    agent_path = install_managed_llama_server(config, runner=runner, uid=502)

    assert agent_path.is_file()
    launcher_path = config.home_path / ".local" / "bin" / "llama-server"
    assert launcher_path.is_file()
    assert "KOTEKOMI_MANAGED_LLAMA_SERVER" in launcher_path.read_text(encoding="utf-8")
    assert runner.calls == [
        (["launchctl", "bootout", f"gui/502/{SERVICE_LABEL}"], False),
        (["launchctl", "print", f"gui/502/{SERVICE_LABEL}"], False),
        (["launchctl", "bootstrap", "gui/502", str(agent_path)], True),
    ]


def test_status_and_uninstall_use_current_user_launchd_domain(tmp_path: Path) -> None:
    config = service_config(tmp_path)
    config.agent_path.parent.mkdir(parents=True)
    config.agent_path.write_bytes(render_launch_agent_plist(config))
    runner = FakeRunner(returncode=0, print_returncode=0)

    status = get_managed_llama_server_status(home_path=config.home_path, runner=runner, uid=502)
    removed_path = uninstall_managed_llama_server(
        home_path=config.home_path,
        runner=runner,
        uid=502,
    )

    assert status.installed is True
    assert status.loaded is True
    assert status.path_guarded is False
    assert removed_path == config.agent_path
    assert not config.agent_path.exists()
    assert runner.calls == [
        (["launchctl", "print", f"gui/502/{SERVICE_LABEL}"], False),
        (["launchctl", "bootout", f"gui/502/{SERVICE_LABEL}"], False),
    ]


def test_rejects_nonlocal_bind_address(tmp_path: Path) -> None:
    config = service_config(tmp_path)
    with pytest.raises(ValueError, match="127.0.0.1"):
        render_launch_agent_plist(
            ManagedLlamaServerConfig(
                executable_path=config.executable_path,
                home_path=config.home_path,
                host="0.0.0.0",
            )
        )


def test_install_replaces_only_the_configured_path_launcher(tmp_path: Path) -> None:
    config = service_config(tmp_path)
    launcher_path = config.home_path / ".local" / "bin" / "llama-server"
    launcher_path.parent.mkdir(parents=True)
    launcher_path.symlink_to(config.executable_path)

    install_managed_llama_server(config, runner=FakeRunner(), uid=502)

    assert launcher_path.is_file()
    assert not launcher_path.is_symlink()


def test_uninstall_restores_guarded_path_launcher(tmp_path: Path) -> None:
    config = service_config(tmp_path)
    launcher_path = config.home_path / ".local" / "bin" / "llama-server"
    launcher_path.parent.mkdir(parents=True)
    launcher_path.symlink_to(config.executable_path)
    install_managed_llama_server(config, runner=FakeRunner(), uid=502)

    uninstall_managed_llama_server(home_path=config.home_path, runner=FakeRunner(), uid=502)

    assert launcher_path.is_symlink()
    assert launcher_path.resolve() == config.executable_path
