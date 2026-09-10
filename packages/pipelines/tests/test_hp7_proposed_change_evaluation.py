from __future__ import annotations

import json
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
HP6_GOLD_PATH = REPOSITORY / "docs" / "hp6-event-semantics-gold-v1.json"
HP7_GOLD_PATH = REPOSITORY / "docs" / "hp7-proposal-admission-gold-v1.json"


def test_hp7_gold_catalog_covers_seven_gold_events_and_the_known_false_event() -> None:
    hp6_gold = json.loads(HP6_GOLD_PATH.read_text())
    hp7_gold = json.loads(HP7_GOLD_PATH.read_text())
    hp6_locators = {
        (item["case_id"], item["trigger"], item["frame_id"], item["source_text"])
        for item in hp6_gold["events"]
    }
    cases = hp7_gold["cases"]
    approved = [item for item in cases if item["review_outcome"] == "approved"]
    rejected = [item for item in cases if item["review_outcome"] == "rejected"]

    assert hp7_gold["schema_version"] == "hp7_proposal_admission_gold_v1"
    assert len(cases) == 8
    assert {
        (item["case_id"], item["trigger"], item["frame_id"], item["source_text"])
        for item in approved
    } == hp6_locators
    assert len(rejected) == 1
    assert rejected[0]["trigger"] == "said"
    assert rejected[0]["frame_id"] == "recommendation"
    assert "Amodei said Anthropic did not know whether" in rejected[0]["source_text"]
    assert all(item["expected_disposition"] == "proposed" for item in approved)
    assert rejected[0]["expected_disposition"] == "excluded"
