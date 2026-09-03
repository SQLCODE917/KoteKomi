from __future__ import annotations

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

from kotekomi_domain import HYBRID_EVENT_SEMANTICS_V1

GOLD_PATH = Path(__file__).resolve().parents[3] / "docs" / "hp6-event-semantics-gold-v1.json"
SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "verify_hp6_event_semantics.py"
_target_text_matches = cast(
    Callable[[str, str], bool],
    runpy.run_path(str(SCRIPT_PATH), run_name="hp6_verifier")["_target_text_matches"],
)


def test_hp6_gold_catalog_is_bounded_source_valid_and_ontology_valid() -> None:
    catalog = json.loads(GOLD_PATH.read_text())
    events = cast(list[dict[str, object]], catalog["events"])
    frame_by_id = {item.id: item for item in HYBRID_EVENT_SEMANTICS_V1.frames}

    assert catalog["schema_version"] == "hp6_event_semantics_gold_v1"
    assert catalog["ontology_profile_id"] == HYBRID_EVENT_SEMANTICS_V1.id
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
    assert _target_text_matches("one complete action", "one complete action")
    assert _target_text_matches("one complete action,", "one complete action")
    assert _target_text_matches("one complete action;", "one complete action")
    assert _target_text_matches("one complete action.", "one complete action")
    assert not _target_text_matches("a different action", "one complete action")
    assert not _target_text_matches("one complete action: detail", "one complete action")
    assert not _target_text_matches("one complete action", "one complete action.")
