import hashlib
import json
from pathlib import Path
from typing import cast

from kotekomi_domain import HYBRID_EVENT_SEMANTICS_V4
from kotekomi_pipelines.semantic_quality_oracle import (
    final_gold_findings,
    first_failed_event_stage,
    required_event_findings,
)

AMODEI_GOLD = Path(__file__).resolve().parents[3] / "docs/hsq-amodei-intelligence-gold-v1.json"


def _result(
    *,
    expected: str,
    actual: str,
    proposals: bool,
    lineage: bool = True,
    observed: bool = True,
) -> dict[str, object]:
    return {
        "case_id": "fixture",
        "observed": observed,
        "lineage_complete": lineage,
        "disposition_matches": actual == expected
        or (expected == "excluded" and actual in {"absent", "held"}),
        "proposal_presence_matches": proposals == (expected == "proposed"),
    }


def test_canonical_oracle_accepts_matching_terminal_dispositions() -> None:
    results = [
        _result(expected="proposed", actual="proposed", proposals=True),
        _result(expected="excluded", actual="held", proposals=False),
        _result(
            expected="excluded",
            actual="absent",
            proposals=False,
            observed=False,
        ),
    ]

    assert final_gold_findings(results) == []


def test_canonical_oracle_rejects_a_false_event_that_reaches_review() -> None:
    result = _result(expected="excluded", actual="proposed", proposals=True)

    findings = final_gold_findings([result])

    assert findings[0]["code"] == "reviewed_event_final_disposition_mismatch"
    assert findings[0]["mismatches"] == [result]


def test_canonical_oracle_requires_complete_final_lineage() -> None:
    result = _result(expected="proposed", actual="proposed", proposals=True, lineage=False)

    assert final_gold_findings([result]) != []


def test_source_bound_oracle_reports_the_first_failed_stage() -> None:
    result = {
        "case_id": "gold-event",
        "source_observed": True,
        "trigger_observed": True,
        "semantics_match": False,
        "support_match": False,
        "proposal_match": False,
        "wiki_match": False,
        "audit_match": False,
    }

    assert first_failed_event_stage(result) == "governed_semantics"
    assert (
        required_event_findings([result])[0]["mismatches"][0]["first_failed_stage"]
        == "governed_semantics"
    )


def test_source_bound_oracle_accepts_a_complete_auditable_event() -> None:
    result = {
        "case_id": "gold-event",
        "source_observed": True,
        "trigger_observed": True,
        "semantics_match": True,
        "support_match": True,
        "proposal_match": True,
        "wiki_match": True,
        "audit_match": True,
    }

    assert first_failed_event_stage(result) is None
    assert required_event_findings([result]) == []


def test_amodei_gold_is_source_bound_and_conforms_to_the_governed_profile() -> None:
    catalog = json.loads(AMODEI_GOLD.read_text())
    frames = {item.id: item for item in HYBRID_EVENT_SEMANTICS_V4.frames}
    events = [
        event
        for case in cast(list[dict[str, object]], catalog["cases"])
        for event in cast(list[dict[str, object]], case["expected_events"])
    ]

    assert len(events) == 5
    for case in cast(list[dict[str, object]], catalog["cases"]):
        source = cast(str, case["source_text"])
        assert hashlib.sha256(source.encode()).hexdigest() == case["source_segment_sha256"]
        for event in cast(list[dict[str, object]], case["expected_events"]):
            assert source.count(cast(str, event["trigger_text"])) == 1
            frame = frames[cast(str, event["frame_id"])]
            roles = {item.id: item for item in frame.roles}
            for expected_role in cast(list[dict[str, object]], event["roles"]):
                role = roles[cast(str, expected_role["frame_role_id"])]
                assert expected_role["target_kind"] in {
                    item.value for item in role.allowed_target_kinds
                }
                exact_text = cast(str, expected_role["exact_text"])
                if "start" in expected_role:
                    start = cast(int, expected_role["start"])
                    end = cast(int, expected_role["end"])
                    assert source[start:end] == exact_text
                else:
                    assert source.count(exact_text) == 1
