"""Canonical terminal-state checks for Hybrid semantic evaluation."""

from __future__ import annotations

from typing import Any

type JsonObject = dict[str, Any]

_EVENT_STAGE_CHECKS = (
    ("source_segment", "source_observed"),
    ("trigger_discovery", "trigger_observed"),
    ("governed_semantics", "semantics_match"),
    ("source_support", "support_match"),
    ("proposal_admission", "proposal_match"),
    ("candidate_wiki", "wiki_match"),
    ("audit_lineage", "audit_match"),
)


def final_gold_findings(gold_results: list[JsonObject]) -> list[JsonObject]:
    """Require reviewed cases to reach their expected terminal semantic state."""
    mismatches = [
        item
        for item in gold_results
        if item["observed"]
        and (
            not item["lineage_complete"]
            or not item["disposition_matches"]
            or not item["proposal_presence_matches"]
        )
    ]
    if not mismatches:
        return []
    return [
        {
            "code": "reviewed_event_final_disposition_mismatch",
            "mismatches": mismatches,
        }
    ]


def first_failed_event_stage(result: JsonObject) -> str | None:
    """Return the earliest failed source-to-Wiki stage for one required Gold event."""
    for stage, field in _EVENT_STAGE_CHECKS:
        if result.get(field) is not True:
            return stage
    return None


def required_event_findings(gold_results: list[JsonObject]) -> list[JsonObject]:
    """Require every source-bound event to survive through Wiki audit evidence."""
    mismatches = [
        {**item, "first_failed_stage": first_failed_event_stage(item)}
        for item in gold_results
        if first_failed_event_stage(item) is not None
    ]
    if not mismatches:
        return []
    return [{"code": "required_event_pipeline_mismatch", "mismatches": mismatches}]


def gold_source_text_matches(actual: str, expected: str) -> bool:
    """Apply the pinned narrow Gold boundary policy to one exact source target."""
    return actual == expected or (
        len(actual) == len(expected) + 1
        and actual[-1] in {",", ";", "."}
        and actual[:-1] == expected
    )
