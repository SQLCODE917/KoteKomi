from pathlib import Path

import pytest
from kotekomi_application import ModelRuntimeStatus
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import ModelRuntimeConfig, load_config


def test_ledger_init_creates_ledger_and_archive_from_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"

    exit_code = main(
        [
            "ledger",
            "init",
            "--ledger-path",
            str(ledger_path),
            "--archive-path",
            str(archive_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert ledger_path.exists()
    assert archive_path.is_dir()
    assert "Applied migrations: 001" in output


def test_ledger_init_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive_path = tmp_path / "archive"
    args = [
        "ledger",
        "init",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]

    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0

    output = capsys.readouterr().out
    assert "Applied migrations: none" in output


def test_load_config_reads_paths_relative_to_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text('ledger_path = "state/kotekomi.db"\narchive_path = "state/archive"\n')

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.ledger_path == (tmp_path / "state" / "kotekomi.db").resolve()
    assert config.archive_path == (tmp_path / "state" / "archive").resolve()


def test_load_config_allows_flag_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text('ledger_path = "state/kotekomi.db"\narchive_path = "state/archive"\n')

    config = load_config(
        config_path=config_path,
        ledger_path_override=Path("override.db"),
        archive_path_override=Path("override_archive"),
    )

    assert config.ledger_path == Path("override.db").resolve()
    assert config.archive_path == Path("override_archive").resolve()


def test_load_config_defaults_to_mac_llama_server_profile() -> None:
    config = load_config(
        config_path=None,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.model_runtime.adapter == "llama_server"
    assert config.model_runtime.endpoint == "http://127.0.0.1:8080/v1"
    assert config.model_runtime.model == "Qwen/Qwen3-14B-GGUF:Q4_K_M"
    assert config.model_runtime.context_tokens == 16384
    assert config.model_runtime.max_output_tokens == 8192
    assert config.model_runtime.prompt_path.name == "propose_assertions.md"


def test_load_config_reads_wsl_ollama_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    prompt_path = tmp_path / "prompts" / "propose_assertions.md"
    config_path.write_text(
        """
[model_runtime]
adapter = "ollama"
endpoint = "http://127.0.0.1:11434"
model = "qwen3:30b-a3b-instruct-2507-q4_K_M"
prompt_path = "prompts/propose_assertions.md"
timeout_seconds = 240
context_tokens = 16384
max_output_tokens = 8192
"""
    )

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.model_runtime.adapter == "ollama"
    assert config.model_runtime.endpoint == "http://127.0.0.1:11434"
    assert config.model_runtime.model == "qwen3:30b-a3b-instruct-2507-q4_K_M"
    assert config.model_runtime.prompt_path == prompt_path
    assert config.model_runtime.timeout_seconds == 240
    assert config.model_runtime.context_tokens == 16384


def test_load_config_rejects_unknown_model_runtime_key(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text('[model_runtime]\nmodel_nmae = "typo"\n')

    with pytest.raises(ValueError, match="Unknown model_runtime config keys: model_nmae"):
        load_config(
            config_path=config_path,
            ledger_path_override=None,
            archive_path_override=None,
        )


class FakeReadyRuntime:
    def check_readiness(self) -> ModelRuntimeStatus:
        return ModelRuntimeStatus(
            adapter="llama_server",
            endpoint="http://127.0.0.1:8080/v1",
            model="Qwen/Qwen3-14B-GGUF:Q4_K_M",
            reachable=True,
            model_available=True,
            model_state="loaded",
            idle_slots=1,
            total_slots=1,
            ready=True,
        )


def fake_build_model_runtime_readiness(config: ModelRuntimeConfig) -> FakeReadyRuntime:
    del config
    return FakeReadyRuntime()


def test_model_status_emits_agent_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "kotekomi_pipelines.cli.build_model_runtime_readiness",
        fake_build_model_runtime_readiness,
    )

    exit_code = main(["model", "status", "--format", "json"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"ready": true' in output
    assert '"adapter": "llama_server"' in output


def test_model_server_status_emits_agent_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    from kotekomi_pipelines.managed_llama_server import ManagedLlamaServerStatus

    def fake_status(*, home_path: Path) -> ManagedLlamaServerStatus:
        del home_path
        return ManagedLlamaServerStatus(
            installed=True,
            loaded=True,
            path_guarded=True,
            agent_path=tmp_path / "llama-server.plist",
        )

    monkeypatch.setattr(
        "kotekomi_pipelines.cli.get_managed_llama_server_status",
        fake_status,
    )

    exit_code = main(["model", "server", "status", "--format", "json"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"installed": true' in output
    assert '"loaded": true' in output
    assert '"path_guarded": true' in output
