"""Compact handoffs omit geometry and resolve selection to canonical IDs."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from kotekomi_application.ingestion_debug_summary import (
    DebugSummary,
    SnapshotOperation,
    build_debug_summary,
)
from kotekomi_application.ingestion_inspection import InspectionContext

from packages.pipelines.tests.test_replay_reader import example_profile


def snapshot() -> DebugSummary:
    profile = replace(example_profile(), stage_statuses=(("hp3_grounding", "partial"),))
    return build_debug_summary(
        profile,
        ordinal=1,
        paragraph_status="processing",
        operation=SnapshotOperation(mode="ingestion", status="running"),
        visible_stages=profile.present_stages,
        selected_key="hp2_references:0",
        context=InspectionContext("igr_fixture", "/local/state"),
        errors=("A presentation error",),
    )


def test_compact_roundtrip_has_text_once_and_selected_handles() -> None:
    captured = snapshot()
    payload = captured.clipboard_json()
    assert DebugSummary.model_validate_json(payload) == captured
    raw = json.loads(payload)
    assert raw["schema_version"] == "kotekomi_debug_summary_v2"
    assert "view" not in raw and "annotations" not in raw and "status_messages" not in raw
    assert payload.count(captured.source.text) == 1
    assert captured.spans == ((0, 9),)
    assert captured.selected_record_id == "ref_fixture"
    assert captured.records["hp2_references"][0].related_ids == ("alias_fixture",)
    assert captured.records["hp2_references"][0].trace_ids == ("trace_fixture",)
    assert next(p for p in captured.phases if p.stage == "hp3_grounding").status == "partial"
    assert len(payload.encode()) < 2048


@pytest.mark.parametrize("invalid", ["span", "reference", "selection", "phase"])
def test_invalid_summary_references_fail(invalid: str) -> None:
    raw = json.loads(snapshot().model_dump_json())
    if invalid == "span":
        raw["spans"] = [[0, 100]]
    elif invalid == "reference":
        raw["records"]["hp1_mentions"][0]["spans"] = [42]
    elif invalid == "selection":
        raw["selected_record_id"] = "missing"
    else:
        raw["phases"][0]["enabled"] = False
    with pytest.raises(ValueError):
        DebugSummary.model_validate_json(json.dumps(raw))
