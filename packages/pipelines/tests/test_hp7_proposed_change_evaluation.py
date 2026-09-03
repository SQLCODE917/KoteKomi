from __future__ import annotations

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

REPOSITORY = Path(__file__).resolve().parents[3]
HP6_GOLD_PATH = REPOSITORY / "docs" / "hp6-event-semantics-gold-v1.json"
HP7_GOLD_PATH = REPOSITORY / "docs" / "hp7-proposal-admission-gold-v1.json"
SCRIPT_PATH = REPOSITORY / "scripts" / "verify_hp7_proposed_changes.py"
_validate_catalog = cast(
    Callable[[dict[str, Any], dict[str, Any]], None],
    runpy.run_path(str(SCRIPT_PATH), run_name="hp7_verifier")["_validate_catalog"],
)


def test_hp7_gold_catalog_covers_seven_gold_events_and_the_known_false_event() -> None:
    hp6_gold = json.loads(HP6_GOLD_PATH.read_text())
    hp7_gold = json.loads(HP7_GOLD_PATH.read_text())
    hp6_locators = {
        (item["case_id"], item["trigger"], item["source_text"]) for item in hp6_gold["events"]
    }
    cases = hp7_gold["cases"]
    approved = [item for item in cases if item["review_outcome"] == "approved"]
    rejected = [item for item in cases if item["review_outcome"] == "rejected"]

    assert hp7_gold["schema_version"] == "hp7_proposal_admission_gold_v1"
    assert len(cases) == 8
    assert {
        (item["case_id"], item["trigger"], item["source_text"]) for item in approved
    } == hp6_locators
    assert len(rejected) == 1
    assert rejected[0]["trigger"] == "said"
    assert "Amodei said Anthropic did not know whether" in rejected[0]["source_text"]
    assert all(item["expected_disposition"] == "proposed" for item in cases)


def test_hp7_catalog_validation_requires_complete_review_outcomes() -> None:
    gold = json.loads(HP7_GOLD_PATH.read_text())
    report = {
        "schema_version": "hp6_event_semantics_evaluation_v1",
        "runs": [
            {"case_id": case_id, "repetition": 1}
            for case_id in sorted({item["case_id"] for item in gold["cases"]})
        ],
    }

    _validate_catalog(report, gold)

    invalid = {**gold, "cases": gold["cases"][:-1]}
    try:
        _validate_catalog(report, invalid)
    except ValueError as error:
        assert str(error) == "HP-7 Gold requires seven approved events and one rejection."
    else:
        raise AssertionError("An incomplete HP-7 review catalog must fail validation.")
