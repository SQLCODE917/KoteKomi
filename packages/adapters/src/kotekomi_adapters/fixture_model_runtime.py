"""Fixture-backed implementation of the ModelRuntime Port."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from kotekomi_application import ModelProposal
from kotekomi_application.model_proposal_validation import validate_model_proposal
from kotekomi_domain.models import JsonValue

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
        payload: object = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed model output fixture JSON: {fixture_path}") from exc

    root = _object_mapping(payload, "fixture root")
    proposals_value = root.get("proposals")
    if not isinstance(proposals_value, list):
        raise ValueError("Model output fixture must contain a 'proposals' array.")

    proposals: list[ModelProposal] = []
    proposal_values = cast(list[object], proposals_value)
    for index, proposal_value in enumerate(proposal_values):
        context = f"proposals[{index}]"
        proposal = _object_mapping(proposal_value, context)
        record_type = _required_string(proposal, "record_type", context)
        stable_label = _required_string(proposal, "stable_label", context)
        record = _json_object(proposal.get("record"), f"{context}.record")
        evidence = _json_object(proposal.get("evidence"), f"{context}.evidence")
        proposals.append(
            validate_model_proposal(
                ModelProposal(
                    record_type=record_type,
                    stable_label=stable_label,
                    record=record,
                    evidence=evidence,
                )
            )
        )
    return tuple(proposals)


def _object_mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"Model output fixture {context} must be an object.")
    result: dict[str, object] = {}
    object_items = cast(dict[object, object], value)
    for key, item in object_items.items():
        if not isinstance(key, str):
            raise ValueError(f"Model output fixture {context} contains a non-string key.")
        result[key] = item
    return result


def _required_string(payload: dict[str, object], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Model output fixture {context}.{key} must be a non-empty string.")
    return value


def _json_object(value: object, context: str) -> dict[str, JsonValue]:
    converted = _json_value(value, context)
    if not isinstance(converted, dict):
        raise ValueError(f"Model output fixture {context} must be an object.")
    return cast(dict[str, JsonValue], converted)


def _json_value(value: object, context: str) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        json_items = cast(list[object], value)
        return [_json_value(item, f"{context}[]") for item in json_items]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        object_items = cast(dict[object, object], value)
        for key, item in object_items.items():
            if not isinstance(key, str):
                raise ValueError(f"Model output fixture {context} contains a non-string key.")
            result[key] = _json_value(item, f"{context}.{key}")
        return result
    raise ValueError(f"Model output fixture {context} contains a non-JSON value.")
