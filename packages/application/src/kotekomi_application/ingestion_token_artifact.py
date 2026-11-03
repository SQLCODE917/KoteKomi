"""Application-owned ingestion dependency-token artifact contract (R20).

The artifact binds one paragraph's ordered dependency tokens to its
representation, TextView, paragraph node and range, source-text digest, and
analyzer identity. The Analysis stage owns the artifact shape and its
validation. Persistence implements ``TokenArtifactWriter`` outside this layer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.event_entity_connections import EventEntityLinguisticToken

_SHA256 = r"^[a-f0-9]{64}$"


class IngestionTokenArtifact(BaseModel):
    """One paragraph's pinned dependency tokens and their source bindings."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["r20_ingestion_token_artifact_v1"] = "r20_ingestion_token_artifact_v1"
    representation_id: Annotated[str, Field(min_length=1)]
    text_view_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    node_start_char: Annotated[int, Field(ge=0)]
    node_end_char: Annotated[int, Field(gt=0)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    analyzer_identity: Annotated[str, Field(min_length=1)]
    tokens: tuple[EventEntityLinguisticToken, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.node_end_char <= self.node_start_char:
            raise ValueError("Token artifact paragraph range must be nonempty.")
        if not self.tokens:
            raise ValueError("Token artifact requires at least one token.")
        token_ids = tuple(token.token_id for token in self.tokens)
        if token_ids != tuple(f"t{ordinal}" for ordinal in range(1, len(self.tokens) + 1)):
            raise ValueError("Token artifact tokens must be complete and ordered.")
        for prior, current in zip(self.tokens, self.tokens[1:], strict=False):
            if current.start < prior.start:
                raise ValueError("Token artifact tokens must use source order.")
        return self


class TokenArtifactWriter(Protocol):
    """Port that persists one validated token artifact outside the Application Layer."""

    def write(self, artifact: IngestionTokenArtifact) -> None: ...


def load_ingestion_token_artifact(
    path: Path,
    *,
    paragraph_text: str,
) -> IngestionTokenArtifact:
    """Load and validate one token artifact against the authoritative paragraph."""
    artifact = IngestionTokenArtifact.model_validate_json(path.read_bytes())
    if hashlib.sha256(paragraph_text.encode()).hexdigest() != artifact.source_text_sha256:
        raise ValueError("Token artifact source digest does not match the paragraph.")
    for token in artifact.tokens:
        if token.end > len(paragraph_text):
            raise ValueError("Token artifact coordinate lies outside the paragraph.")
        if paragraph_text[token.start : token.end] != token.text:
            raise ValueError("Token artifact token text does not match its coordinates.")
    return artifact


def ingestion_token_artifact_digest(artifact: IngestionTokenArtifact) -> str:
    """Return one stable digest over the artifact's binding and tokens."""
    payload = artifact.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
