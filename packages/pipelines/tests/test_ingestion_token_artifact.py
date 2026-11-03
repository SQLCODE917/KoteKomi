"""Tests for the R20 derived ingestion token artifact."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from kotekomi_application import EventEntityLinguisticToken
from kotekomi_pipelines.ingestion_token_artifact import (
    IngestionTokenArtifact,
    ingestion_token_artifact_digest,
    load_ingestion_token_artifact,
    write_ingestion_token_artifact,
)

TEXT = "Alpha supports."


def _token(token_id: str, text: str, start: int, end: int) -> EventEntityLinguisticToken:
    return EventEntityLinguisticToken(
        token_id=token_id,
        sentence_id="s1",
        text=text,
        start=start,
        end=end,
        lemma=text.casefold(),
        part_of_speech="X",
        dependency_relation="root" if token_id == "t2" else "dep",
        head_token_id=None if token_id == "t2" else "t2",
    )


def _artifact() -> IngestionTokenArtifact:
    return IngestionTokenArtifact(
        representation_id="rep_r20",
        text_view_id="tvw_r20",
        paragraph_node_id="nod_r20",
        node_start_char=0,
        node_end_char=len(TEXT),
        source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        analyzer_identity="stanza:en:test",
        tokens=(
            _token("t1", "Alpha", 0, 5),
            _token("t2", "supports", 6, 14),
            _token("t3", ".", 14, 15),
        ),
    )


def test_artifact_round_trips_and_validates(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    artifact = _artifact()
    write_ingestion_token_artifact(path, artifact)

    loaded = load_ingestion_token_artifact(path, paragraph_text=TEXT)

    assert loaded == artifact
    assert [token.token_id for token in loaded.tokens] == ["t1", "t2", "t3"]
    assert ingestion_token_artifact_digest(loaded) == ingestion_token_artifact_digest(artifact)


def test_load_rejects_source_digest_drift(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    write_ingestion_token_artifact(path, _artifact())

    with pytest.raises(ValueError, match="source digest"):
        load_ingestion_token_artifact(path, paragraph_text="Alpha supported.")


def test_load_rejects_coordinate_drift(tmp_path: Path) -> None:
    drifted = _artifact().model_copy(
        update={"tokens": (_token("t1", "Alphi", 0, 5), _token("t2", "supports", 6, 14))}
    )
    path = tmp_path / "tokens.json"
    write_ingestion_token_artifact(path, drifted)

    with pytest.raises(ValueError, match="coordinates"):
        load_ingestion_token_artifact(path, paragraph_text=TEXT)


def test_artifact_rejects_unordered_tokens() -> None:
    with pytest.raises(ValueError, match="complete and ordered"):
        IngestionTokenArtifact(
            representation_id="rep_r20",
            text_view_id="tvw_r20",
            paragraph_node_id="nod_r20",
            node_start_char=0,
            node_end_char=len(TEXT),
            source_text_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
            analyzer_identity="stanza:en:test",
            tokens=(_token("t2", "supports", 6, 14), _token("t1", "Alpha", 0, 5)),
        )
