import json
from pathlib import Path

import kotekomi_pipelines.cli as cli
import pytest
from kotekomi_application import (
    ListModelRunLogsInput,
    ListModelRunLogsResult,
    ModelRunLogEntry,
    ModelRunLogLedger,
    ModelRuntimeStatus,
)
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import (
    CheckoutBuildIdentityError,
    ModelExecutionConfig,
    checkout_artifact_digest,
    derive_checkout_build_identity,
    load_config,
    load_processing_storage_config,
)

USER_INGEST_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)


def test_user_init_creates_xdg_config_and_no_config_ingestion_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_home = tmp_path / "config-home"
    data_home = tmp_path / "data-home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    initialized = capsys.readouterr()
    config_path = config_home / "kotekomi" / "kotekomi.toml"
    assert config_path.is_file()
    assert (data_home / "kotekomi" / "kotekomi.db").is_file()
    assert (data_home / "kotekomi" / "archive").is_dir()
    assert f"Created configuration: {config_path}" in initialized.out
    assert 'representation_policy_version = "deposited-source-v1"' in config_path.read_text()

    assert main(["ingestions", "list"]) == 0
    assert capsys.readouterr().out == ""


def test_user_init_is_idempotent_without_overwriting_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data-home"))
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    capsys.readouterr()
    config_path = tmp_path / "config-home" / "kotekomi" / "kotekomi.toml"
    first_contents = config_path.read_bytes()

    assert main(["init"]) == 0
    second = capsys.readouterr()
    assert config_path.read_bytes() == first_contents
    assert f"Using configuration: {config_path}" in second.out


def test_user_init_enables_no_config_ingest_and_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data-home"))
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    capsys.readouterr()
    config_path = tmp_path / "config-home" / "kotekomi" / "kotekomi.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'runtime_profile = "lm-studio"', 'runtime_profile = "fixture"'
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "ingest",
                str(USER_INGEST_FIXTURE),
                "--url",
                "https://example.test/articles/anthropic-review",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert captured.out.startswith("anthropic_model_release_review.md\t[CAPTURED]\t")
    assert main(["ingestions", "list"]) == 0
    assert capsys.readouterr().out == f"{captured.out.splitlines()[0]}\n"


def test_project_config_precedes_user_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_config = tmp_path / "config-home" / "kotekomi" / "kotekomi.toml"
    user_config.parent.mkdir(parents=True)
    user_config.write_text(
        'ledger_path = "user.db"\narchive_path = "user-archive"\n'
        '[processing]\nrepresentation_policy_version = "user-v1"\n',
        encoding="utf-8",
    )
    project_config = tmp_path / "project" / "kotekomi.toml"
    project_config.parent.mkdir()
    project_config.write_text(
        'ledger_path = "project.db"\narchive_path = "project-archive"\n'
        '[processing]\nrepresentation_policy_version = "project-v1"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    monkeypatch.chdir(project_config.parent)

    config = load_processing_storage_config(
        config_path=None,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.storage.ledger_path == (project_config.parent / "project.db").resolve()
    assert config.representation_policy_version == "project-v1"


def test_user_history_missing_config_is_actionable_and_creates_no_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config-home"))
    monkeypatch.chdir(tmp_path)

    assert main(["ingestions", "list"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "No KoteKomi configuration found at" in output.err
    assert "kotekomi init" in output.err
    assert not (tmp_path / "data").exists()


def test_user_history_does_not_require_processing_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        '[processing]\nrepresentation_policy_version = "test-v1"\n', encoding="utf-8"
    )

    def fail_identity(_: str) -> object:
        raise CheckoutBuildIdentityError("identity unavailable")

    monkeypatch.setattr("kotekomi_pipelines.config.derive_checkout_build_identity", fail_identity)
    assert main(["--config", str(config_path), "ingestions", "list"]) == 0
    assert capsys.readouterr().out == ""


def test_model_runs_renders_safe_durable_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        '[processing]\nrepresentation_policy_version = "test-v1"\n', encoding="utf-8"
    )
    result = ListModelRunLogsResult(
        entries=(
            ModelRunLogEntry(
                model_run_id="mrn_fixture",
                extraction_task_id="ext_fixture",
                runtime_identity="lm_studio",
                status="succeeded",
                started_at="2026-08-24T12:00:00+00:00",
                completed_at="2026-08-24T12:00:01+00:00",
                requested_max_output_tokens=8192,
                input_token_count=42,
                output_token_count=11,
                elapsed_milliseconds=1000,
                deadline_milliseconds=300000,
                first_response_event_milliseconds=250,
                error_code=None,
            ),
        )
    )

    def fake_list_model_run_logs(
        input: ListModelRunLogsInput,
        ledger_repository: ModelRunLogLedger,
    ) -> ListModelRunLogsResult:
        del input, ledger_repository
        return result

    monkeypatch.setattr(cli, "list_model_run_logs", fake_list_model_run_logs)

    assert main(["--config", str(config_path), "model", "runs", "--format", "json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "model_runs": [
            {
                "completed_at": "2026-08-24T12:00:01+00:00",
                "deadline_milliseconds": 300000,
                "elapsed_milliseconds": 1000,
                "error_code": None,
                "extraction_task_id": "ext_fixture",
                "first_response_event_milliseconds": 250,
                "input_token_count": 42,
                "model_run_id": "mrn_fixture",
                "output_token_count": 11,
                "requested_max_output_tokens": 8192,
                "runtime_identity": "lm_studio",
                "started_at": "2026-08-24T12:00:00+00:00",
                "status": "succeeded",
            }
        ]
    }


def test_model_runs_rejects_non_positive_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        '[processing]\nrepresentation_policy_version = "test-v1"\n', encoding="utf-8"
    )

    assert main(["--config", str(config_path), "model", "runs", "--limit", "0"]) == 1

    assert "positive integer" in capsys.readouterr().err


def test_checkout_build_identity_is_stable_and_binds_current_source() -> None:
    first = derive_checkout_build_identity("test-v1")
    second = derive_checkout_build_identity("test-v1")

    assert first == second
    assert len(first.artifact_digest) == 64
    assert len(first.source_revision) == 40


def test_checkout_artifact_digest_changes_with_package_source(tmp_path: Path) -> None:
    package_source = tmp_path / "packages" / "pipelines" / "src" / "kotekomi_pipelines"
    package_source.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    (tmp_path / "packages" / "pipelines" / "pyproject.toml").write_text("[project]\n")
    source_file = package_source / "module.py"
    source_file.write_text("value = 1\n")

    first = checkout_artifact_digest(tmp_path)
    source_file.write_text("value = 2\n")

    assert checkout_artifact_digest(tmp_path) != first


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


def test_load_config_defaults_to_lm_studio_profile() -> None:
    config = load_config(
        config_path=None,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.model_execution.adapter == "lm_studio"
    assert config.model_execution.endpoint == "http://127.0.0.1:1234/v1"
    assert config.model_execution.model == "qwen2.5-14b-instruct"
    assert config.model_execution.context_tokens == 16384
    assert config.model_execution.max_output_tokens == 2048
    assert config.model_execution.profile_name == "lm-studio"


def test_load_config_reads_wsl_ollama_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        """
[model_runtime]
adapter = "ollama"
endpoint = "http://127.0.0.1:11434"
model = "qwen3:30b-a3b-instruct-2507-q4_K_M"
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

    assert config.model_execution.adapter == "ollama"
    assert config.model_execution.endpoint == "http://127.0.0.1:11434"
    assert config.model_execution.model == "qwen3:30b-a3b-instruct-2507-q4_K_M"
    assert config.model_execution.timeout_seconds == 240
    assert config.model_execution.context_tokens == 16384


def test_load_config_selects_wsl_profile_without_redefining_model_runtime(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text('runtime_profile = "wsl-4090"\n', encoding="utf-8")

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.model_execution.profile_name == "wsl-4090"
    assert config.model_execution.adapter == "ollama"
    assert config.model_execution.endpoint == "http://127.0.0.1:11434"


def test_runtime_profile_override_precedes_model_runtime_field_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text('runtime_profile = "macbook"\n', encoding="utf-8")

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
        runtime_profile_override="wsl-4090",
        model_name_override="qwen3:custom",
    )

    assert config.model_execution.profile_name == "wsl-4090"
    assert config.model_execution.model == "qwen3:custom"


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


def fake_build_model_runtime_readiness(config: ModelExecutionConfig) -> FakeReadyRuntime:
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
