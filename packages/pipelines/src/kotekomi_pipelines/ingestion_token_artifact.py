"""Filesystem persistence for the R20 ingestion token artifact.

The Application Layer owns ``IngestionTokenArtifact`` and its validation
(``kotekomi_application.ingestion_token_artifact``). This module implements the
``TokenArtifactWriter`` Port on the local filesystem and re-exports the contract.
"""

from __future__ import annotations

from pathlib import Path

from kotekomi_application.ingestion_token_artifact import (
    IngestionTokenArtifact,
    TokenArtifactWriter,
    ingestion_token_artifact_digest,
    load_ingestion_token_artifact,
)

__all__ = [
    "IngestionTokenArtifact",
    "LocalTokenArtifactWriter",
    "TokenArtifactWriter",
    "ingestion_token_artifact_digest",
    "load_ingestion_token_artifact",
    "write_ingestion_token_artifact",
]


def write_ingestion_token_artifact(path: Path, artifact: IngestionTokenArtifact) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")


class LocalTokenArtifactWriter:
    """Filesystem ``TokenArtifactWriter`` keyed by paragraph node ID."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def write(self, artifact: IngestionTokenArtifact) -> None:
        write_ingestion_token_artifact(self._root / f"{artifact.paragraph_node_id}.json", artifact)

    def path_for(self, paragraph_node_id: str) -> Path:
        return self._root / f"{paragraph_node_id}.json"
