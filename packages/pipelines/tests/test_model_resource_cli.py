from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from kotekomi_application import (
    REQUIRED_MODEL_RESOURCE_IDS,
    ModelResourceInstallDisposition,
    ModelResourceInstallResult,
    ModelResourceReadiness,
    ModelResourceReadinessReport,
    ModelResourceStatus,
)
from kotekomi_pipelines import cli
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import (
    EntityLinkingConfig,
    ModelExecutionConfig,
    PipelineConfig,
    load_config,
)


def _config(tmp_path: Path, *, adapter: str = "lm_studio") -> PipelineConfig:
    return PipelineConfig(
        ledger_path=tmp_path / "ledger.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            adapter,
            "http://127.0.0.1:1234/v1",
            "fixture-model",
            300.0,
            16_384,
            512,
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
        model_resource_root=(tmp_path / "model-resources").resolve(),
        entity_linking=EntityLinkingConfig("refined", 300.0),
    )


def _report(config: PipelineConfig, *, ready: bool) -> ModelResourceReadinessReport:
    resources = tuple(
        ModelResourceReadiness(
            resource_id=resource_id,
            status=ModelResourceStatus.READY if ready else ModelResourceStatus.MISSING,
            root=(config.model_resource_root / resource_id.value).resolve(),
            expected_identity=f"expected:{resource_id.value}",
            observed_identity=f"expected:{resource_id.value}" if ready else None,
            diagnostics=() if ready else (f"{resource_id.value} is missing.",),
        )
        for resource_id in REQUIRED_MODEL_RESOURCE_IDS
    )
    return ModelResourceReadinessReport(config.model_resource_root, resources)


def _config_loader(config: PipelineConfig) -> Callable[..., PipelineConfig]:
    def load(**_kwargs: object) -> PipelineConfig:
        return config

    return load


def _processing_loader(**_kwargs: object) -> object:
    return object()


def test_model_resource_status_is_typed_actionable_and_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    monkeypatch.setattr(cli, "load_config", _config_loader(config))

    def inspect(_config: PipelineConfig) -> ModelResourceReadinessReport:
        return _report(config, ready=False)

    monkeypatch.setattr(
        cli,
        "inspect_configured_model_resources",
        inspect,
    )

    result = main(["--config", "user.toml", "model", "resources", "status"])

    assert result == 1
    output = capsys.readouterr().out
    assert "gliner_mention_proposer_v1: missing" in output
    assert "uv run kotekomi --config user.toml model resources install" in output


def test_model_resource_status_has_stable_json_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    report = _report(config, ready=True)
    monkeypatch.setattr(cli, "load_config", _config_loader(config))

    def inspect(_config: PipelineConfig) -> ModelResourceReadinessReport:
        return report

    monkeypatch.setattr(cli, "inspect_configured_model_resources", inspect)

    assert main(["model", "resources", "status", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "model_resource_status_v1"
    assert payload["status"] == "ready"
    assert [item["resource_id"] for item in payload["resources"]] == [
        item.value for item in REQUIRED_MODEL_RESOURCE_IDS
    ]


def test_model_resource_install_routes_selection_and_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    report = _report(config, ready=True)
    received: list[tuple[tuple[object, ...], bool]] = []

    def install(
        _config: PipelineConfig,
        *,
        selected: tuple[object, ...],
        repair: bool,
    ) -> tuple[ModelResourceInstallResult, ...]:
        received.append((selected, repair))
        readiness = report.resources[1]
        return (ModelResourceInstallResult(ModelResourceInstallDisposition.REPAIRED, readiness),)

    monkeypatch.setattr(cli, "load_config", _config_loader(config))
    monkeypatch.setattr(cli, "install_configured_model_resources", install)

    def inspect(_config: PipelineConfig) -> ModelResourceReadinessReport:
        return report

    monkeypatch.setattr(cli, "inspect_configured_model_resources", inspect)

    assert (
        main(
            [
                "model",
                "resources",
                "install",
                "--resource",
                "refined",
                "--repair",
            ]
        )
        == 0
    )

    assert received == [((REQUIRED_MODEL_RESOURCE_IDS[1],), True)]
    assert "refined_wikipedia_v1: repaired" in capsys.readouterr().out


def test_targeted_model_resource_install_succeeds_while_reporting_aggregate_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    not_ready_report = _report(config, ready=False)
    installed_readiness = ModelResourceReadiness(
        resource_id=REQUIRED_MODEL_RESOURCE_IDS[0],
        status=ModelResourceStatus.READY,
        root=(config.model_resource_root / REQUIRED_MODEL_RESOURCE_IDS[0].value).resolve(),
        expected_identity="expected:gliner",
        observed_identity="expected:gliner",
        diagnostics=(),
    )

    def install(
        _config: PipelineConfig,
        *,
        selected: tuple[object, ...],
        repair: bool,
    ) -> tuple[ModelResourceInstallResult, ...]:
        assert selected == (REQUIRED_MODEL_RESOURCE_IDS[0],)
        assert repair is False
        return (
            ModelResourceInstallResult(
                ModelResourceInstallDisposition.INSTALLED,
                installed_readiness,
            ),
        )

    monkeypatch.setattr(cli, "load_config", _config_loader(config))
    monkeypatch.setattr(cli, "install_configured_model_resources", install)

    def inspect(_config: PipelineConfig) -> ModelResourceReadinessReport:
        return not_ready_report

    monkeypatch.setattr(
        cli,
        "inspect_configured_model_resources",
        inspect,
    )

    assert main(["model", "resources", "install", "--resource", "gliner"]) == 0
    output = capsys.readouterr().out
    assert "gliner_mention_proposer_v1: installed" in output
    assert "Model resources: not ready" in output


def test_ingestion_resource_preflight_precedes_storage_and_run_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    storage_touched = False

    class ForbiddenInitializer:
        def __init__(self, _path: Path) -> None:
            nonlocal storage_touched
            storage_touched = True

    monkeypatch.setattr(cli, "load_processing_config", _processing_loader)
    monkeypatch.setattr(cli, "load_config", _config_loader(config))

    def inspect(_config: PipelineConfig) -> ModelResourceReadinessReport:
        return _report(config, ready=False)

    monkeypatch.setattr(
        cli,
        "inspect_configured_model_resources",
        inspect,
    )
    monkeypatch.setattr(cli, "SQLiteLedgerInitializer", ForbiddenInitializer)

    result = cli.ingest_user_file(
        config_path=Path("user.toml"),
        source_file_path=tmp_path / "source.pdf",
        source_url="https://example.test/source",
    )

    assert result == 1
    assert storage_touched is False
    assert not config.ledger_path.exists()
    assert not config.archive_path.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("model_resources_not_ready\n")
    assert "model resources install" in captured.err


def test_fixture_ingestion_does_not_require_specialized_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path, adapter="fixture")
    inspected = False

    def inspect(_config: PipelineConfig) -> ModelResourceReadinessReport:
        nonlocal inspected
        inspected = True
        return cast(ModelResourceReadinessReport, object())

    class FailingInitializer:
        def __init__(self, _path: Path) -> None:
            pass

        def initialize(self) -> None:
            raise OSError("stop after preflight")

    monkeypatch.setattr(cli, "load_processing_config", _processing_loader)
    monkeypatch.setattr(cli, "load_config", _config_loader(config))
    monkeypatch.setattr(cli, "inspect_configured_model_resources", inspect)
    monkeypatch.setattr(cli, "SQLiteLedgerInitializer", FailingInitializer)

    assert (
        cli.ingest_user_file(
            config_path=None,
            source_file_path=tmp_path / "source.pdf",
            source_url="https://example.test/source",
        )
        == 1
    )
    assert inspected is False


def test_model_resource_root_defaults_to_shared_user_data_and_is_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "shared"))

    config = load_config(
        config_path=None,
        ledger_path_override=tmp_path / "ledger.db",
        archive_path_override=tmp_path / "archive",
    )

    assert (
        config.model_resource_root
        == (tmp_path / "shared" / "kotekomi" / "model-resources").resolve()
    )

    invalid = tmp_path / "invalid.toml"
    invalid.write_text('[model_resources]\nroot = "resources"\nextra = true\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown model_resources config keys: extra"):
        load_config(
            config_path=invalid,
            ledger_path_override=None,
            archive_path_override=None,
        )
