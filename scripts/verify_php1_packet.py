"""Run every PHP-1 annotation-packet row as a non-gating local diagnostic."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, cast

from php1_diagnostic_support import ROOT, Php1DiagnosticCase, Php1Expectation, run_cases

PACKET_PATH = ROOT / "docs/2026-08-26-cir-evaluation-annotation-packet.md"
EXPECTATION_CATALOG_PATH = ROOT / "docs/php1-evaluation-expectations-v1.json"
EXPECTATION_CATALOG_SCHEMA_VERSION = "php1_evaluation_expectations_v1"
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
