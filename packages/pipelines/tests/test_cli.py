import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import kotekomi_pipelines.cli as cli
import pytest
from kotekomi_application import (
    EntityLinkingInput,
    EntityLinkingPort,
    HybridEntityGroundingCommand,
    HybridEntityGroundingResult,
    HybridEntityGroundingStatus,
    HybridEventFrameCommand,
    HybridEventFrameResult,
    HybridEventFrameStatus,
    HybridMentionPreviewResult,
    HybridPreviewStatus,
    HybridReferencePreviewCommand,
    HybridReferencePreviewResult,
    ListModelRunLogsInput,
    ListModelRunLogsResult,
    ModelRunLogEntry,
    ModelRunLogLedger,
    ModelRuntimeStatus,
    build_hybrid_entity_grounding_preview_record,
    build_hybrid_event_frame_preview,
    build_hybrid_extraction_preview,
    build_hybrid_reference_preview_record,
    hybrid_entity_grounding_preview_sha256,
    hybrid_event_frame_preview_sha256,
    hybrid_extraction_preview_sha256,
    hybrid_reference_preview_sha256,
)
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import (
    CheckoutBuildIdentityError,
    EntityLinkingConfig,
    ModelExecutionConfig,
    PipelineConfig,
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


def test_review_commands_expose_optional_canonical_predicate() -> None:
    parser = cli.build_parser()

    approve = parser.parse_args(
        [
            "review",
            "approve",
            "--proposed-change-id",
            "pcg_assertion",
            "--reviewer",
            "analyst",
            "--canonical-predicate",
            "has_policy_conflict_with",
        ]
    )
    run_next = parser.parse_args(
        [
            "review",
            "run-next",
            "--decision",
            "approve",
            "--reviewer",
            "analyst",
            "--canonical-predicate",
            "has_policy_conflict_with",
        ]
    )
    edit = parser.parse_args(
        [
            "review",
            "edit",
            "--proposed-change-id",
            "pcg_assertion",
            "--reviewer",
            "analyst",
            "--accepted-record-json",
            "accepted.json",
            "--canonical-predicate",
            "has_policy_conflict_with",
        ]
    )

    assert approve.canonical_predicate == "has_policy_conflict_with"
    assert run_next.canonical_predicate == "has_policy_conflict_with"
    assert edit.canonical_predicate == "has_policy_conflict_with"


def test_hybrid_mention_preview_command_routes_explicit_source_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture",
            "fixture://local",
            "qwen2.5-fixture",
            300.0,
            16_384,
            512,
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    received: list[tuple[PipelineConfig, str, str]] = []

    def fake_load_model_config(**kwargs: object) -> PipelineConfig:
        del kwargs
        return config

    def fake_preview_hybrid_mentions(
        *, config: PipelineConfig, representation_id: str, paragraph_node_id: str
    ) -> int:
        received.append((config, representation_id, paragraph_node_id))
        return 0

    monkeypatch.setattr(cli, "_load_model_config", fake_load_model_config)
    monkeypatch.setattr(cli, "preview_hybrid_mentions", fake_preview_hybrid_mentions)

    assert (
        main(
            [
                "extraction",
                "preview-mentions",
                "--representation-id",
                "rep_fixture",
                "--node-id",
                "nod_fixture",
            ]
        )
        == 0
    )
    assert received == [(config, "rep_fixture", "nod_fixture")]


def test_hybrid_mention_preview_prints_exact_portable_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture",
            "fixture://local",
            "qwen2.5-fixture",
            300.0,
            16_384,
            512,
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    preview = build_hybrid_extraction_preview(
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        context_manifest_id="ctx_fixture",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    digest = hybrid_extraction_preview_sha256(preview)

    class FakeArchive:
        def __init__(self, archive_path: Path) -> None:
            assert archive_path == config.archive_path

        def initialize(self) -> None:
            pass

    @contextmanager
    def fake_transaction(ledger_path: Path) -> Generator[object]:
        assert ledger_path == config.ledger_path
        yield object()

    def fake_run(**kwargs: object) -> HybridMentionPreviewResult:
        assert kwargs["prompt_bytes"]
        assert kwargs["ontology_card_bytes"]
        return HybridMentionPreviewResult(
            preview,
            digest,
            f"extraction/previews/{preview.id}.json",
        )

    def fake_build_runtime(config_value: object) -> object:
        del config_value
        return object()

    monkeypatch.setattr(cli, "LocalArchiveStore", FakeArchive)
    monkeypatch.setattr(cli, "sqlite_ledger_transaction", fake_transaction)
    monkeypatch.setattr(cli, "build_model_task_runtime", fake_build_runtime)
    monkeypatch.setattr(cli, "GlinerMentionProposer", lambda: object())
    monkeypatch.setattr(cli, "run_hybrid_mention_preview", fake_run)

    assert (
        cli.preview_hybrid_mentions(
            config=config,
            representation_id="rep_fixture",
            paragraph_node_id="nod_fixture",
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "archive_path": f"extraction/previews/{preview.id}.json",
        "preview_id": preview.id,
        "sha256": digest,
        "status": "complete",
    }


def test_hybrid_reference_command_routes_parent_preview_without_model_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    received: list[tuple[PipelineConfig, str]] = []

    def fake_load_config(**kwargs: object) -> PipelineConfig:
        del kwargs
        return config

    def fake_resolve(*, config: PipelineConfig, parent_preview_id: str) -> int:
        received.append((config, parent_preview_id))
        return 0

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "resolve_hybrid_references", fake_resolve)

    assert main(["extraction", "resolve-references", "--preview-id", "hxp_fixture"]) == 0
    assert received == [(config, "hxp_fixture")]


def test_hybrid_reference_command_prints_exact_portable_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    parent = build_hybrid_extraction_preview(
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        context_manifest_id="ctx_fixture",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    preview = build_hybrid_reference_preview_record(
        parent_preview_id=parent.id,
        parent_preview_sha256=hybrid_extraction_preview_sha256(parent),
        representation_id="rep_fixture",
        alias_declarations=(),
        reference_decisions=(),
        traces=(),
    )
    digest = hybrid_reference_preview_sha256(preview)

    class FakeArchive:
        def __init__(self, archive_path: Path) -> None:
            assert archive_path == config.archive_path

        def initialize(self) -> None:
            pass

    @contextmanager
    def fake_transaction(ledger_path: Path) -> Generator[object]:
        assert ledger_path == config.ledger_path
        yield object()

    def fake_run(**kwargs: object) -> HybridReferencePreviewResult:
        assert kwargs["command"] == HybridReferencePreviewCommand(parent.id)
        return HybridReferencePreviewResult(
            preview,
            digest,
            f"extraction/reference-previews/{preview.id}.json",
        )

    monkeypatch.setattr(cli, "LocalArchiveStore", FakeArchive)
    monkeypatch.setattr(cli, "sqlite_ledger_transaction", fake_transaction)
    monkeypatch.setattr(cli, "run_hybrid_reference_preview", fake_run)

    assert cli.resolve_hybrid_references(config=config, parent_preview_id=parent.id) == 0
    assert json.loads(capsys.readouterr().out) == {
        "archive_path": f"extraction/reference-previews/{preview.id}.json",
        "parent_preview_id": parent.id,
        "preview_id": preview.id,
        "sha256": digest,
        "status": "complete",
    }


def test_hybrid_entity_grounding_command_routes_parent_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    received: list[tuple[PipelineConfig, str]] = []

    def fake_load_config(**kwargs: object) -> PipelineConfig:
        del kwargs
        return config

    def fake_ground(*, config: PipelineConfig, parent_preview_id: str) -> int:
        received.append((config, parent_preview_id))
        return 1

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "ground_hybrid_entities", fake_ground)

    assert main(["extraction", "ground-entities", "--preview-id", "hrp_fixture"]) == 1
    assert received == [(config, "hrp_fixture")]


def test_hybrid_entity_grounding_prints_exact_portable_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
        entity_linking=EntityLinkingConfig(
            adapter="refined",
            python_executable=Path("/fixture/python"),
            data_dir=Path("/fixture/resources"),
            timeout_seconds=300.0,
        ),
    )
    preview = build_hybrid_entity_grounding_preview_record(
        parent_preview_id="hrp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        mention_preview_id="hxp_" + "2" * 24,
        mention_preview_sha256="b" * 64,
        representation_id="rep_fixture",
        eligibility=(),
        link_evidence=(),
        extraction_task_ids=(),
        model_run_ids=(),
        traces=(),
        terminal_status=HybridEntityGroundingStatus.COMPLETE,
        diagnostics=(),
    )
    digest = hybrid_entity_grounding_preview_sha256(preview)

    class FakeArchive:
        def __init__(self, archive_path: Path) -> None:
            assert archive_path == config.archive_path

        def initialize(self) -> None:
            pass

    class FakeAdapter:
        def __init__(self, adapter_config: object) -> None:
            del adapter_config

        def close(self) -> None:
            pass

    @contextmanager
    def fake_transaction(ledger_path: Path) -> Generator[object]:
        assert ledger_path == config.ledger_path
        yield object()

    def fake_run(**kwargs: object) -> HybridEntityGroundingResult:
        command = cast(HybridEntityGroundingCommand, kwargs["command"])
        assert command.parent_preview_id == preview.parent_preview_id
        return HybridEntityGroundingResult(
            preview,
            digest,
            f"extraction/entity-grounding-previews/{preview.id}.json",
        )

    monkeypatch.setattr(cli, "LocalArchiveStore", FakeArchive)
    monkeypatch.setattr(cli, "RefinedEntityLinkingAdapter", FakeAdapter)
    monkeypatch.setattr(cli, "sqlite_ledger_transaction", fake_transaction)
    monkeypatch.setattr(cli, "run_hybrid_entity_grounding_preview", fake_run)

    assert (
        cli.ground_hybrid_entities(config=config, parent_preview_id=preview.parent_preview_id) == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "archive_path": f"extraction/entity-grounding-previews/{preview.id}.json",
        "parent_preview_id": preview.parent_preview_id,
        "preview_id": preview.id,
        "sha256": digest,
        "status": "complete",
    }


def test_hybrid_entity_grounding_missing_runtime_publishes_blocked_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    preview = build_hybrid_entity_grounding_preview_record(
        parent_preview_id="hrp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        mention_preview_id="hxp_" + "2" * 24,
        mention_preview_sha256="b" * 64,
        representation_id="rep_fixture",
        eligibility=(),
        link_evidence=(),
        extraction_task_ids=(),
        model_run_ids=(),
        traces=(),
        terminal_status=HybridEntityGroundingStatus.BLOCKED,
        diagnostics=("entity_linking_runtime_unavailable",),
    )
    digest = hybrid_entity_grounding_preview_sha256(preview)

    class FakeArchive:
        def __init__(self, archive_path: Path) -> None:
            assert archive_path == config.archive_path

        def initialize(self) -> None:
            pass

    @contextmanager
    def fake_transaction(ledger_path: Path) -> Generator[object]:
        assert ledger_path == config.ledger_path
        yield object()

    def fake_run(**kwargs: object) -> HybridEntityGroundingResult:
        linker = cast(EntityLinkingPort, kwargs["linker"])
        with pytest.raises(RuntimeError, match="not configured"):
            linker.link(cast(EntityLinkingInput, object()))
        return HybridEntityGroundingResult(
            preview,
            digest,
            f"extraction/entity-grounding-previews/{preview.id}.json",
        )

    monkeypatch.setattr(cli, "LocalArchiveStore", FakeArchive)
    monkeypatch.setattr(cli, "sqlite_ledger_transaction", fake_transaction)
    monkeypatch.setattr(cli, "run_hybrid_entity_grounding_preview", fake_run)

    assert (
        cli.ground_hybrid_entities(config=config, parent_preview_id=preview.parent_preview_id) == 1
    )
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "blocked"
    assert captured.err == "entity_linking_runtime_unavailable\n"


def test_hybrid_event_frame_command_routes_parent_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    received: list[tuple[PipelineConfig, str]] = []

    def fake_load_model_config(**kwargs: object) -> PipelineConfig:
        del kwargs
        return config

    def fake_draft(*, config: PipelineConfig, parent_preview_id: str) -> int:
        received.append((config, parent_preview_id))
        return 0

    monkeypatch.setattr(cli, "_load_model_config", fake_load_model_config)
    monkeypatch.setattr(cli, "draft_hybrid_event_frames", fake_draft)

    assert main(["extraction", "draft-event-frames", "--preview-id", "hgp_fixture"]) == 0
    assert received == [(config, "hgp_fixture")]


def test_hybrid_event_frame_command_prints_portable_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    preview = build_hybrid_event_frame_preview(
        parent_preview_id="hgp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        reference_preview_id="hrp_" + "2" * 24,
        reference_preview_sha256="b" * 64,
        mention_preview_id="hxp_" + "3" * 24,
        mention_preview_sha256="c" * 64,
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        trigger_context_manifest_id="ctx_trigger",
        frame_context_manifest_id="ctx_frame",
        terminal_status=HybridEventFrameStatus.COMPLETE,
    )
    digest = hybrid_event_frame_preview_sha256(preview)

    class FakeArchive:
        def __init__(self, archive_path: Path) -> None:
            assert archive_path == config.archive_path

        def initialize(self) -> None:
            pass

    @contextmanager
    def fake_transaction(ledger_path: Path) -> Generator[object]:
        assert ledger_path == config.ledger_path
        yield object()

    def fake_run(**kwargs: object) -> HybridEventFrameResult:
        command = cast(HybridEventFrameCommand, kwargs["command"])
        assert command.parent_preview_id == preview.parent_preview_id
        assert kwargs["trigger_prompt_bytes"]
        assert kwargs["frame_prompt_bytes"]
        return HybridEventFrameResult(
            preview,
            digest,
            f"extraction/event-frame-previews/{preview.id}.json",
        )

    def fake_runtime(runtime_config: ModelExecutionConfig) -> object:
        assert runtime_config == config.model_execution
        return object()

    monkeypatch.setattr(cli, "LocalArchiveStore", FakeArchive)
    monkeypatch.setattr(cli, "build_model_task_runtime", fake_runtime)
    monkeypatch.setattr(cli, "sqlite_ledger_transaction", fake_transaction)
    monkeypatch.setattr(cli, "run_hybrid_event_frame_preview", fake_run)

    assert (
        cli.draft_hybrid_event_frames(
            config=config,
            parent_preview_id=preview.parent_preview_id,
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "archive_path": f"extraction/event-frame-previews/{preview.id}.json",
        "parent_preview_id": preview.parent_preview_id,
        "preview_id": preview.id,
        "sha256": digest,
        "status": "complete",
    }


def test_hybrid_event_frame_command_returns_one_for_a_partial_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = PipelineConfig(
        ledger_path=tmp_path / "kotekomi.db",
        archive_path=tmp_path / "archive",
        model_execution=ModelExecutionConfig(
            "fixture", "fixture://local", "fixture", 300.0, 1024, 64
        ),
        embedding_profiles={},
        document_retrieval_embedding_profile_id=None,
    )
    preview = build_hybrid_event_frame_preview(
        parent_preview_id="hgp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        reference_preview_id="hrp_" + "2" * 24,
        reference_preview_sha256="b" * 64,
        mention_preview_id="hxp_" + "3" * 24,
        mention_preview_sha256="c" * 64,
        representation_id="rep_fixture",
        paragraph_node_id="nod_fixture",
        trigger_context_manifest_id="ctx_trigger",
        frame_context_manifest_id="ctx_frame",
        terminal_status=HybridEventFrameStatus.PARTIAL,
        diagnostics=("frame_task_failed:fixture",),
    )

    class FakeArchive:
        def __init__(self, archive_path: Path) -> None:
            assert archive_path == config.archive_path

        def initialize(self) -> None:
            pass

    @contextmanager
    def fake_transaction(ledger_path: Path) -> Generator[object]:
        assert ledger_path == config.ledger_path
        yield object()

    def fake_runtime(runtime_config: ModelExecutionConfig) -> object:
        assert runtime_config == config.model_execution
        return object()

    def fake_run(**kwargs: object) -> HybridEventFrameResult:
        del kwargs
        return HybridEventFrameResult(
            preview,
            hybrid_event_frame_preview_sha256(preview),
            f"extraction/event-frame-previews/{preview.id}.json",
        )

    monkeypatch.setattr(cli, "LocalArchiveStore", FakeArchive)
    monkeypatch.setattr(cli, "build_model_task_runtime", fake_runtime)
    monkeypatch.setattr(cli, "sqlite_ledger_transaction", fake_transaction)
    monkeypatch.setattr(cli, "run_hybrid_event_frame_preview", fake_run)

    assert (
        cli.draft_hybrid_event_frames(
            config=config,
            parent_preview_id=preview.parent_preview_id,
        )
        == 1
    )
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "partial"
    assert captured.err == "frame_task_failed:fixture\n"


def test_entrypoint_reports_application_validation_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def failing_main() -> int:
        raise ValueError("Assertion review requires canonical_predicate.")

    monkeypatch.setattr(cli, "main", failing_main)

    with pytest.raises(SystemExit) as error:
        cli.entrypoint()

    assert error.value.code == 2
    assert capsys.readouterr().err == "Error: Assertion review requires canonical_predicate.\n"


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


def test_load_config_reads_strict_entity_linking_paths_relative_to_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config" / "kotekomi.toml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
[entity_linking]
adapter = "refined"
python_executable = "runtime/bin/python"
data_dir = "runtime/resources"
timeout_seconds = 45
""".strip()
    )

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )

    assert config.entity_linking == EntityLinkingConfig(
        adapter="refined",
        python_executable=config_path.parent / "runtime/bin/python",
        data_dir=config_path.parent / "runtime/resources",
        timeout_seconds=45.0,
    )


def test_load_config_allows_missing_entity_linking_and_rejects_unknown_keys(
    tmp_path: Path,
) -> None:
    assert (
        load_config(
            config_path=None,
            ledger_path_override=tmp_path / "ledger.db",
            archive_path_override=tmp_path / "archive",
        ).entity_linking
        is None
    )
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
[entity_linking]
adapter = "refined"
python_executable = "/runtime/python"
data_dir = "/runtime/resources"
timeout_seconds = 45
worker_script = "/untrusted/worker.py"
""".strip()
    )

    with pytest.raises(ValueError, match="Unknown entity_linking"):
        load_config(
            config_path=config_path,
            ledger_path_override=None,
            archive_path_override=None,
        )


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (
            """
[entity_linking]
adapter = "unknown"
python_executable = "/runtime/python"
data_dir = "/runtime/resources"
timeout_seconds = 45
""",
            "adapter must be refined",
        ),
        (
            """
[entity_linking]
adapter = "refined"
python_executable = "/runtime/python"
data_dir = "/runtime/resources"
""",
            "Missing entity_linking config keys: timeout_seconds",
        ),
        (
            """
[entity_linking]
adapter = "refined"
python_executable = "/runtime/python"
data_dir = "/runtime/resources"
timeout_seconds = 0
""",
            "must be a positive",
        ),
    ],
)
def test_load_config_rejects_invalid_entity_linking_contract(
    tmp_path: Path,
    table: str,
    message: str,
) -> None:
    config_path = tmp_path / "invalid-entity-linking.toml"
    config_path.write_text(table.strip())

    with pytest.raises((TypeError, ValueError), match=message):
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
