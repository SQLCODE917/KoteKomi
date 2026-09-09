from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from kotekomi_domain import HYBRID_EVENT_SEMANTICS_V4
from kotekomi_pipelines.semantic_quality_oracle import gold_source_text_matches

GOLD_PATH = Path(__file__).resolve().parents[3] / "docs" / "hp6-event-semantics-gold-v1.json"


def test_hp6_gold_catalog_is_bounded_source_valid_and_ontology_valid() -> None:
    catalog = json.loads(GOLD_PATH.read_text())
    events = cast(list[dict[str, object]], catalog["events"])
    frame_by_id = {item.id: item for item in HYBRID_EVENT_SEMANTICS_V4.frames}

    assert catalog["schema_version"] == "hp6_event_semantics_gold_v1"
    assert catalog["ontology_profile_id"] == HYBRID_EVENT_SEMANTICS_V4.id
    assert catalog["scope"] == {
        "parent_evidence_target_count": 14,
        "detailed_scenario_count": 5,
        "detailed_event_count": 7,
        "expected_semantic_statement_support": "directly_supported",
        "target_boundary_comparison_policy": "exact_or_one_trailing_clause_delimiter_v1",
        "unlisted_event_policy": "not_scored",
    }
    assert len(events) == 7
    assert len({cast(str, item["case_id"]) for item in events}) == 5
    for event in events:
        source_text = cast(str, event["source_text"])
        trigger = cast(str, event["trigger"])
        frame = frame_by_id[cast(str, event["frame_id"])]
        roles = {item.id: item for item in frame.roles}
        assert source_text.count(trigger) == 1
        for argument in cast(list[dict[str, str]], event["arguments"]):
            role = roles[argument["frame_role_id"]]
            assert argument["target_kind"] in {item.value for item in role.allowed_target_kinds}
            assert source_text.count(argument["target_text"]) == 1
        for qualifier in cast(list[dict[str, str]], event["qualifiers"]):
            assert qualifier["kind"] in {"place", "time"}
            assert source_text.count(qualifier["text"]) == 1
        attribution_target = event.get("attribution_target_text")
        if attribution_target is not None:
            assert source_text.count(cast(str, attribution_target)) == 1


def test_hp6_gold_target_boundary_policy_is_narrow() -> None:
    assert gold_source_text_matches("one complete action", "one complete action")
    assert gold_source_text_matches("one complete action,", "one complete action")
    assert gold_source_text_matches("one complete action;", "one complete action")
    assert gold_source_text_matches("one complete action.", "one complete action")
    assert not gold_source_text_matches("a different action", "one complete action")
    assert not gold_source_text_matches("one complete action: detail", "one complete action")
    assert not gold_source_text_matches("one complete action", "one complete action.")
