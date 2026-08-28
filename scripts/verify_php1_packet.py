"""Run every PHP-1 annotation-packet row as a non-gating local diagnostic."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, cast

from php1_diagnostic_support import (
    PHP1_SEGMENT_V6_PROMPT,
    ROOT,
    Php1DiagnosticCase,
    Php1Expectation,
    run_cases,
)
from php1_diagnostic_support import (
    run_h2 as run_h2_diagnostic,
)

PACKET_PATH = ROOT / "docs/2026-08-26-cir-evaluation-annotation-packet.md"
EXPECTATION_CATALOG_PATH = ROOT / "docs/php1-evaluation-expectations-v1.json"
EXPECTATION_CATALOG_SCHEMA_VERSION = "php1_evaluation_expectations_v1"
H1_SCORECARD_PATH = ROOT / "docs/php1-h1-evaluation-v1.json"
H1_SCORECARD_SCHEMA_VERSION = "php1_h1_evaluation_v1"
ROW_PATTERN = re.compile(
    r"^\| (?P<case_id>(?:AD|AI|CS)-\d{2}) \| .*? \| `(?P<anchor>.*?)` \| "
    r"(?P<case_class>.*?) \| (?P<expected>.*?) \|$"
)
ELIGIBILITY_PATTERN = re.compile(
    r"^\| (?P<case_id>(?:AD|AI|CS)-\d{2}) \| (?P<label>[a-z_]+) \| "
    r"(?P<reason>.*?) \|$"
)
ELIGIBILITY_LABELS = frozenset(
    {"eligible", "out_of_scope", "needs_coreference", "needs_multi_segment", "control"}
)
SOURCE_BY_PREFIX = {
    "AD": (
        "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf",
        "https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute",
    ),
    "AI": (
        "raw/Artificial_intelligence_safety_institute.pdf",
        "https://en.wikipedia.org/wiki/AI_Safety_Institute",
    ),
    "CS": (
        "raw/241030_Allen_Safety_Network.pdf",
        "https://csis.org/allen-safety-network",
    ),
}


def h1_scorecard(
    expectations: tuple[Php1Expectation, ...],
    scorecard_path: Path = H1_SCORECARD_PATH,
) -> dict[str, Any]:
    """Load the explicit held-out H1 threshold without hard-coding target IDs."""
    raw_value: object = json.loads(scorecard_path.read_text(encoding="utf-8"))
    if not isinstance(raw_value, dict):
        raise ValueError("PHP-1 H1 scorecard must be an object.")
    raw = cast(dict[str, object], raw_value)
    required = {
        "schema_version",
        "scored_expectation_ids",
        "observation_expectation_ids",
        "required_matched_expectation_ids",
        "required_any_matched_expectation_id_sets",
        "minimum_matched_count",
    }
    if set(raw) != required or raw.get("schema_version") != H1_SCORECARD_SCHEMA_VERSION:
        raise ValueError("PHP-1 H1 scorecard fields or schema version do not match the contract.")
    expectation_ids = {item.expectation_id for item in expectations}
    list_fields = (
        "scored_expectation_ids",
        "observation_expectation_ids",
        "required_matched_expectation_ids",
    )
    parsed: dict[str, list[str]] = {}
    for field_name in list_fields:
        value = raw[field_name]
        if not isinstance(value, list) or not value:
            raise ValueError(f"PHP-1 H1 scorecard {field_name} must be a non-empty string list.")
        values_value = cast(list[object], value)
        if any(not isinstance(item, str) or not item for item in values_value):
            raise ValueError(f"PHP-1 H1 scorecard {field_name} must be a non-empty string list.")
        values = cast(list[str], values_value)
        if len(set(values)) != len(values) or not set(values) <= expectation_ids:
            raise ValueError(f"PHP-1 H1 scorecard {field_name} must contain unique known targets.")
        parsed[field_name] = values
    scored = set(parsed["scored_expectation_ids"])
    observation = set(parsed["observation_expectation_ids"])
    required_matches = set(parsed["required_matched_expectation_ids"])
    if scored & observation or not required_matches <= scored:
        raise ValueError("PHP-1 H1 scorecard has conflicting scored and required targets.")
    groups_value = raw["required_any_matched_expectation_id_sets"]
    if not isinstance(groups_value, list) or not groups_value:
        raise ValueError("PHP-1 H1 scorecard must contain one or more required target groups.")
    groups: list[list[str]] = []
    for group_value in cast(list[object], groups_value):
        if not isinstance(group_value, list) or not group_value:
            raise ValueError("PHP-1 H1 scorecard target groups must be non-empty string lists.")
        group_values = cast(list[object], group_value)
        if any(not isinstance(item, str) or not item for item in group_values):
            raise ValueError("PHP-1 H1 scorecard target groups must be non-empty string lists.")
        group = cast(list[str], group_values)
        if len(set(group)) != len(group) or not set(group) <= scored:
            raise ValueError("PHP-1 H1 scorecard target groups must contain unique scored targets.")
        groups.append(group)
    minimum = raw["minimum_matched_count"]
    if not isinstance(minimum, int) or isinstance(minimum, bool) or not 0 < minimum <= len(scored):
        raise ValueError("PHP-1 H1 scorecard minimum_matched_count is invalid.")
    return {
        "schema_version": H1_SCORECARD_SCHEMA_VERSION,
        "scored_expectation_ids": parsed["scored_expectation_ids"],
        "observation_expectation_ids": parsed["observation_expectation_ids"],
        "required_matched_expectation_ids": parsed["required_matched_expectation_ids"],
        "required_any_matched_expectation_id_sets": groups,
        "minimum_matched_count": minimum,
    }


def packet_cases(packet_path: Path = PACKET_PATH) -> tuple[Php1DiagnosticCase, ...]:
    labels = _packet_labels(packet_path)
    cases: list[Php1DiagnosticCase] = []
    for line in packet_path.read_text(encoding="utf-8").splitlines():
        match = ROW_PATTERN.match(line)
        if match is None:
            continue
        prefix = match["case_id"].split("-", maxsplit=1)[0]
        relative_path, source_url = SOURCE_BY_PREFIX[prefix]
        label = labels.get(match["case_id"])
        if label is None:
            raise ValueError(
                f"PHP-1 packet case has no provisional eligibility label: {match['case_id']}."
            )
        cases.append(
            Php1DiagnosticCase(
                match["case_id"],
                relative_path,
                source_url,
                match["anchor"],
                {
                    "case_class": match["case_class"],
                    "expected_semantic_work": match["expected"],
                    "provisional_eligibility": label[0],
                    "provisional_eligibility_reason": label[1],
                },
            )
        )
    if len(cases) != 50:
        raise ValueError(f"PHP-1 packet must define 50 rows, found {len(cases)}.")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("PHP-1 packet case IDs must be unique.")
    if set(labels) != {case.case_id for case in cases}:
        raise ValueError("PHP-1 packet labels must identify each and only packet case.")
    return tuple(cases)


def _packet_labels(packet_path: Path) -> dict[str, tuple[str, str]]:
    labels: dict[str, tuple[str, str]] = {}
    for line in packet_path.read_text(encoding="utf-8").splitlines():
        match = ELIGIBILITY_PATTERN.match(line)
        if match is None:
            continue
        label = match["label"]
        reason = match["reason"]
        if label not in ELIGIBILITY_LABELS:
            raise ValueError(f"PHP-1 packet has an unknown provisional eligibility label: {label}.")
        if not reason:
            raise ValueError("PHP-1 packet provisional eligibility reason must not be empty.")
        if match["case_id"] in labels:
            raise ValueError(
                f"PHP-1 packet repeats a provisional eligibility label: {match['case_id']}."
            )
        labels[match["case_id"]] = (label, reason)
    return labels


def expectation_catalog(
    cases: tuple[Php1DiagnosticCase, ...],
    catalog_path: Path = EXPECTATION_CATALOG_PATH,
) -> tuple[Php1Expectation, ...]:
    raw_value: object = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(raw_value, dict):
        raise ValueError(
            "PHP-1 expectation catalog must contain only schema_version and expectations."
        )
    raw = cast(dict[str, object], raw_value)
    if set(raw) != {"schema_version", "expectations"}:
        raise ValueError(
            "PHP-1 expectation catalog must contain only schema_version and expectations."
        )
    if raw["schema_version"] != EXPECTATION_CATALOG_SCHEMA_VERSION:
        raise ValueError("PHP-1 expectation catalog has an unsupported schema version.")
    entries_value = raw["expectations"]
    if not isinstance(entries_value, list) or not entries_value:
        raise ValueError("PHP-1 expectation catalog must contain one or more expectations.")
    entries = cast(list[object], entries_value)
    cases_by_id = {case.case_id: case for case in cases}
    expectations: list[Php1Expectation] = []
    for entry_value in entries:
        if not isinstance(entry_value, dict):
            raise ValueError("PHP-1 expectation catalog entries must be objects.")
        entry = cast(dict[str, object], entry_value)
        required = {
            "expectation_id",
            "case_ids",
            "fixture_path",
            "paragraph_anchor",
            "source_segment_anchor",
            "subject_text",
            "object_text",
            "relationship_shape",
        }
        if set(entry) != required:
            raise ValueError("PHP-1 expectation catalog entry fields do not match the contract.")
        case_ids_value = entry["case_ids"]
        if not isinstance(case_ids_value, list):
            raise ValueError("PHP-1 expectation case_ids must be a non-empty unique string list.")
        case_id_values = cast(list[object], case_ids_value)
        if (
            not case_id_values
            or any(not isinstance(case_id, str) or not case_id for case_id in case_id_values)
            or len(set(cast(list[str], case_id_values))) != len(case_id_values)
        ):
            raise ValueError("PHP-1 expectation case_ids must be a non-empty unique string list.")
        case_ids = cast(list[str], case_id_values)
        values: dict[str, object] = {key: entry[key] for key in required - {"case_ids"}}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError("PHP-1 expectation catalog text fields must be non-empty strings.")
        expectation = Php1Expectation(
            expectation_id=cast(str, entry["expectation_id"]),
            case_ids=tuple(case_ids),
            fixture_path=cast(str, entry["fixture_path"]),
            paragraph_anchor=cast(str, entry["paragraph_anchor"]),
            source_segment_anchor=cast(str, entry["source_segment_anchor"]),
            subject_text=cast(str, entry["subject_text"]),
            object_text=cast(str, entry["object_text"]),
            relationship_shape=cast(str, entry["relationship_shape"]),
        )
        for case_id in expectation.case_ids:
            case = cases_by_id.get(case_id)
            if case is None:
                raise ValueError(f"PHP-1 expectation references unknown packet case: {case_id}.")
            if case.metadata.get("provisional_eligibility") != "eligible":
                raise ValueError(f"PHP-1 expectation case is not eligible: {case_id}.")
            if case.relative_path != expectation.fixture_path:
                raise ValueError(f"PHP-1 expectation fixture path does not match case: {case_id}.")
        expectations.append(expectation)
    if len({item.expectation_id for item in expectations}) != len(expectations):
        raise ValueError("PHP-1 expectation catalog repeats an expectation_id.")
    if len({item.target_identity for item in expectations}) != len(expectations):
        raise ValueError("PHP-1 expectation catalog repeats a target identity.")
    return tuple(expectations)


def run(config_path: Path | None) -> dict[str, Any]:
    cases = packet_cases()
    return run_cases(
        config_path,
        cases,
        representation_policy_version="php1-packet-diagnostic-v2",
        include_raw_output=True,
        expectations=expectation_catalog(cases),
    )


def h1_result(
    result: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    """Score H1 target coverage while retaining unexpected hypotheses for review."""
    target_report_value = result.get("target_report")
    if not isinstance(target_report_value, dict):
        return {
            "status": "blocked",
            "diagnostics": ["target_report_missing"],
            "unexpected_hypotheses": [],
        }
    target_report = cast(dict[str, Any], target_report_value)
    target_results = cast(list[dict[str, Any]], target_report.get("target_results", []))
    target_statuses = {
        str(item.get("expectation_id")): item.get("target_status") for item in target_results
    }
    scored_ids = cast(list[str], scorecard["scored_expectation_ids"])
    matched_ids = sorted(
        expectation_id
        for expectation_id in scored_ids
        if target_statuses.get(expectation_id) == "matched"
    )
    missing_required = sorted(
        expectation_id
        for expectation_id in cast(list[str], scorecard["required_matched_expectation_ids"])
        if target_statuses.get(expectation_id) != "matched"
    )
    missing_groups = [
        group
        for group in cast(list[list[str]], scorecard["required_any_matched_expectation_id_sets"])
        if not any(target_statuses.get(expectation_id) == "matched" for expectation_id in group)
    ]
    observation_ids = cast(list[str], scorecard["observation_expectation_ids"])
    observation_results = [
        {
            "expectation_id": expectation_id,
            "target_status": target_statuses.get(expectation_id),
        }
        for expectation_id in observation_ids
    ]
    minimum = cast(int, scorecard["minimum_matched_count"])
    status = (
        "passed"
        if len(matched_ids) >= minimum and not missing_required and not missing_groups
        else "failed"
    )
    return {
        "schema_version": "php1_h1_score_v1",
        "status": status,
        "minimum_matched_count": minimum,
        "matched_count": len(matched_ids),
        "matched_expectation_ids": matched_ids,
        "missing_expectation_ids": sorted(set(scored_ids) - set(matched_ids)),
        "missing_required_expectation_ids": missing_required,
        "missing_required_any_groups": missing_groups,
        "observation_results": observation_results,
        "unexpected_hypotheses": cast(
            list[dict[str, Any]], target_report.get("unexpected_hypotheses", [])
        ),
    }


def run_h1(config_path: Path | None) -> dict[str, Any]:
    """Run the historical V6 packet replay and add the H1 held-out scorecard."""
    cases = packet_cases()
    result = run_cases(
        config_path,
        cases,
        representation_policy_version="php1-packet-diagnostic-v2",
        include_raw_output=True,
        expectations=expectation_catalog(cases),
        prompt_contract=PHP1_SEGMENT_V6_PROMPT,
    )
    if result.get("status") != "completed":
        return {**result, "h1_scorecard": {"status": "blocked", "diagnostics": [result["status"]]}}
    return {
        **result,
        "h1_scorecard": h1_result(result, h1_scorecard(expectation_catalog(cases))),
    }


def run_h2(config_path: Path | None) -> dict[str, Any]:
    """Run the H2 mention and pair diagnostic for H0 Expectations."""
    cases = packet_cases()
    return run_h2_diagnostic(config_path, cases, expectation_catalog(cases))


def render_h2_prompt_reports(
    result: dict[str, Any], expectations: tuple[Php1Expectation, ...]
) -> tuple[str, str]:
    """Render one plain-text H2 review report for each model prompt."""
    if result.get("status") != "completed":
        raise ValueError("H2 prompt reports require a completed H2 result.")
    mentions = {
        (
            str(item["fixture_path"]),
            str(item["paragraph_node_id"]),
            str(item["source_segment_label"]),
        ): item
        for item in cast(list[dict[str, Any]], result["mention_results"])
    }
    pairs = {
        (
            str(item["fixture_path"]),
            str(item["paragraph_node_id"]),
            str(item["source_segment_label"]),
        ): item
        for item in cast(list[dict[str, Any]], result["pair_results"])
    }
    target_results = {
        str(item["expectation_id"]): item
        for item in cast(list[dict[str, Any]], result["h2_target_report"]["target_results"])
    }
    mention_groups: list[str] = ["Prompt file: prompts/paragraph_organization_mention_v1.md"]
    pair_groups: list[str] = ["Prompt file: prompts/paragraph_organization_pair_relation_v1.md"]
    for expectation in expectations:
        target = target_results.get(expectation.expectation_id)
        if target is None:
            raise ValueError("H2 prompt report is missing an Expectation result.")
        key = (
            expectation.fixture_path,
            str(target.get("paragraph_node_id", "")),
            str(target.get("source_segment_label", "")),
        )
        mention = mentions.get(key)
        if mention is None:
            raise ValueError("H2 prompt report is missing a Mention result.")
        source_segment = str(mention["source_copy_text"])
        mention_groups.append(
            "\n".join(
                (
                    f"Test: {expectation.expectation_id}",
                    "Source segment:",
                    source_segment,
                    "Expected result:",
                    "Find the complete literal Organization names "
                    f"`{expectation.subject_text}` and `{expectation.object_text}`.",
                    "Actual result:",
                    f"Mention status: {mention['status']}",
                    f"Model output: {mention['raw_output']}",
                )
            )
        )
        pair_groups.append(
            _render_h2_pair_group(expectation, target, source_segment, pairs.get(key))
        )
    return "\n\n".join(mention_groups) + "\n", "\n\n".join(pair_groups) + "\n"


def _render_h2_pair_group(
    expectation: Php1Expectation,
    target: dict[str, Any],
    source_segment: str,
    pair_result: dict[str, Any] | None,
) -> str:
    expected_pair = {expectation.subject_text, expectation.object_text}
    judgments = (
        cast(list[dict[str, Any]], pair_result["judgments"]) if pair_result is not None else []
    )
    judgment = next(
        (
            item
            for item in judgments
            if {str(item["first_organization_text"]), str(item["second_organization_text"])}
            == expected_pair
        ),
        None,
    )
    actual = (
        (
            f"Pair status: {judgment['status']}\n"
            f"Model output: {judgment['raw_output']}\n"
            f"Verifier accepted claim count: {judgment['faithfulness_accepted_claim_count']}\n"
            f"Verifier rejected claim count: {judgment['faithfulness_rejected_claim_count']}"
        )
        if judgment is not None
        else (
            f"Pair status: not_run\n"
            f"H2 target status: {target['target_status']}\n"
            f"Diagnostics: {', '.join(cast(list[str], target['diagnostics'])) or 'none'}"
        )
    )
    return "\n".join(
        (
            f"Test: {expectation.expectation_id}",
            "Source segment:",
            source_segment,
            "Expected result:",
            f"Find one source-stated {expectation.relationship_shape} relationship from "
            f"`{expectation.subject_text}` to `{expectation.object_text}`.",
            "Actual result:",
            actual,
        )
    )


def summary(result: dict[str, Any]) -> dict[str, Any]:
    cases = cast(list[dict[str, Any]], result.get("cases", []))
    statuses: Counter[str] = Counter(str(item["status"]) for item in cases if "status" in item)
    by_eligibility: dict[str, Counter[str]] = {}
    segment_statuses: Counter[str] = Counter()
    segment_statuses_by_eligibility: dict[str, Counter[str]] = {}
    for item in cases:
        label = str(item.get("provisional_eligibility", "unlabeled"))
        by_eligibility.setdefault(label, Counter())[str(item["status"])] += 1
        for segment in cast(list[dict[str, Any]], item.get("segments", [])):
            status = str(segment["status"])
            segment_statuses[status] += 1
            segment_statuses_by_eligibility.setdefault(label, Counter())[status] += 1
    summary_result = {
        "status": result["status"],
        "case_count": len(cases),
        "status_counts": dict(sorted(statuses.items())),
        "status_counts_by_provisional_eligibility": {
            label: dict(sorted(counts.items())) for label, counts in sorted(by_eligibility.items())
        },
        "source_segment_report": {
            "status_counts": dict(sorted(segment_statuses.items())),
            "status_counts_by_provisional_eligibility": {
                label: dict(sorted(counts.items()))
                for label, counts in sorted(segment_statuses_by_eligibility.items())
            },
        },
    }
    target_report_value = result.get("target_report")
    if isinstance(target_report_value, dict):
        target_report = cast(dict[str, Any], target_report_value)
        targets = cast(list[dict[str, Any]], target_report.get("target_results", []))
        target_counts = Counter(
            str(item["target_status"]) for item in targets if item.get("target_status") is not None
        )
        by_shape: dict[str, Counter[str]] = {}
        for item in targets:
            status = item.get("target_status")
            if status is not None:
                by_shape.setdefault(str(item["relationship_shape"]), Counter())[str(status)] += 1
        summary_result["target_report"] = {
            "expectation_count": len(targets),
            "target_status_counts": dict(sorted(target_counts.items())),
            "target_status_counts_by_relationship_shape": {
                shape: dict(sorted(counts.items())) for shape, counts in sorted(by_shape.items())
            },
            "unexpected_hypothesis_count": len(
                cast(list[dict[str, Any]], target_report.get("unexpected_hypotheses", []))
            ),
        }
    return summary_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    result = run(arguments.config)
    if arguments.output is not None:
        arguments.output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({**summary(result), "output": str(arguments.output)}, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
