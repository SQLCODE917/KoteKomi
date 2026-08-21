import hashlib
from pathlib import Path

import pytest
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import load_config


def test_load_config_reads_a_pinned_embedding_profile(tmp_path: Path) -> None:
    model_path = tmp_path / "nomic.gguf"
    model_path.write_bytes(b"pinned-nomic-model")
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        f"""
[embedding_profiles.semantic-validation-v1]
adapter = "lm_studio"
endpoint = "http://127.0.0.1:1234/v1"
model = "text-embedding-nomic-embed-text-v1.5"
model_path = "{model_path.name}"
model_digest = "{hashlib.sha256(model_path.read_bytes()).hexdigest()}"
vector_dimension = 768
maximum_rendered_characters = 16000
timeout_seconds = 300
"""
    )

    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )

    profile = config.embedding_profiles["semantic-validation-v1"]
    assert profile.model_path == str(model_path)
    assert profile.expected_vector_dimension == 768


def test_retrieval_without_a_channel_passes_the_configured_normal_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    model_path = tmp_path / "nomic.gguf"
    model_path.write_bytes(b"pinned-nomic-model")
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        f'''\
[document_retrieval]
default_embedding_profile = "semantic-validation-v1"

[embedding_profiles.semantic-validation-v1]
adapter = "lm_studio"
endpoint = "http://127.0.0.1:1234/v1"
model = "text-embedding-nomic-embed-text-v1.5"
model_path = "{model_path.name}"
model_digest = "{hashlib.sha256(model_path.read_bytes()).hexdigest()}"
vector_dimension = 768
maximum_rendered_characters = 16000
timeout_seconds = 300
'''
    )

    def fake_build_document_retrieval_index(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(
        "kotekomi_pipelines.cli.build_document_retrieval_index",
        fake_build_document_retrieval_index,
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "retrieval",
            "build-document",
            "--representation-id",
            "rep_fixture",
        ]
    )

    assert exit_code == 0
    assert captured["channel"] is None
    assert captured["embedding_profile"] is not None


def test_query_without_a_channel_passes_the_configured_normal_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    model_path = tmp_path / "nomic.gguf"
    model_path.write_bytes(b"pinned-nomic-model")
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        f'''\
[document_retrieval]
default_embedding_profile = "semantic-validation-v1"

[embedding_profiles.semantic-validation-v1]
adapter = "lm_studio"
endpoint = "http://127.0.0.1:1234/v1"
model = "text-embedding-nomic-embed-text-v1.5"
model_path = "{model_path.name}"
model_digest = "{hashlib.sha256(model_path.read_bytes()).hexdigest()}"
vector_dimension = 768
maximum_rendered_characters = 16000
timeout_seconds = 300
'''
    )

    def fake_query_document_retrieval_index(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(
        "kotekomi_pipelines.cli.query_document_retrieval_index",
        fake_query_document_retrieval_index,
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "retrieval",
            "query",
            "--representation-id",
            "rep_fixture",
            "--query",
            "needle",
            "--maximum-hits",
            "1",
            "--context-profile",
            "retrieval-validation-v1",
        ]
    )

    assert exit_code == 0
    assert captured["channel"] is None
    assert captured["embedding_profile"] is not None


def test_retrieval_rejects_an_embedding_profile_without_semantic_channel() -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "retrieval",
                "query",
                "--representation-id",
                "rep_fixture",
                "--query",
                "needle",
                "--maximum-hits",
                "1",
                "--context-profile",
                "retrieval-validation-v1",
                "--embedding-profile",
                "semantic-validation-v1",
            ]
        )

    assert error.value.code == 2


def test_load_config_rejects_a_missing_document_retrieval_profile(tmp_path: Path) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        '[document_retrieval]\ndefault_embedding_profile = "missing-profile"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="default_embedding_profile is unknown"):
        load_config(
            config_path=config_path,
            ledger_path_override=None,
            archive_path_override=None,
        )
