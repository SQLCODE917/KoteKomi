"""Fixture-backed implementation of the ModelRuntime Port."""

from __future__ import annotations

from pathlib import Path

from kotekomi_application import ModelProposal, parse_model_proposal_batch_json

FIXTURE_MODEL_NAME = "fixture-extraction-runtime"
FIXTURE_PROMPT_ID = "propose_assertions"


class FixtureModelRuntime:
    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path
        self._proposals = _load_proposals(fixture_path)

    @property
    def model_name(self) -> str:
        return FIXTURE_MODEL_NAME

    @property
    def prompt_id(self) -> str:
        return FIXTURE_PROMPT_ID

    def propose_assertions(
        self,
        *,
        document_id: str,
        source_id: str,
        document_text: str,
    ) -> tuple[ModelProposal, ...]:
        del document_id, source_id, document_text
        return self._proposals


def _load_proposals(fixture_path: Path) -> tuple[ModelProposal, ...]:
    try:
        return parse_model_proposal_batch_json(fixture_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"Invalid model output fixture {fixture_path}: {exc}") from exc
