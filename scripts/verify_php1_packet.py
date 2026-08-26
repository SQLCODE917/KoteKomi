"""Run every PHP-1 annotation-packet row as a non-gating local diagnostic."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, cast

from php1_diagnostic_support import ROOT, Php1DiagnosticCase, run_cases

PACKET_PATH = ROOT / "docs/2026-08-26-cir-evaluation-annotation-packet.md"
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


def run(config_path: Path | None) -> dict[str, Any]:
    return run_cases(
        config_path,
        packet_cases(),
        representation_policy_version="php1-packet-diagnostic-v2",
        include_raw_output=True,
    )


def summary(result: dict[str, Any]) -> dict[str, Any]:
    cases = cast(list[dict[str, Any]], result.get("cases", []))
    statuses: Counter[str] = Counter(str(item["status"]) for item in cases if "status" in item)
    by_eligibility: dict[str, Counter[str]] = {}
    for item in cases:
        label = str(item.get("provisional_eligibility", "unlabeled"))
        by_eligibility.setdefault(label, Counter())[str(item["status"])] += 1
    return {
        "status": result["status"],
        "case_count": len(cases),
        "status_counts": dict(sorted(statuses.items())),
        "status_counts_by_provisional_eligibility": {
            label: dict(sorted(counts.items())) for label, counts in sorted(by_eligibility.items())
        },
    }


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
