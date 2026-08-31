"""Validate the source integrity and development separation of the held-out packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from kotekomi_application import PARAGRAPH_SEGMENT_V3, paragraph_source_segments, source_copy_view

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = ROOT / "docs/2026-08-28-organization-mention-held-out-annotation-packet.md"
DEFAULT_GOLD = ROOT / "docs/php1-organization-mention-gold-v1.json"

_ENTRY = re.compile(r"^## HO-(?P<number>[0-9]{3})\n\n(?P<body>.*?)(?=^## HO-|\Z)", re.M | re.S)
_SOURCE_TEXT = re.compile(
    r"^### Complete authoritative paragraph text\n\n```text\n(?P<text>.*?)\n```$",
    re.M | re.S,
)
_GOLD = re.compile(
    r"^### Gold Organization Mentions\n\n(?P<value>.*?)\n\n### Reviewer notes"
    r"(?:\n\n(?P<notes>.*))?$",
    re.M | re.S,
)


def validate_held_out_packet(
    packet_path: Path = DEFAULT_PACKET,
    gold_path: Path = DEFAULT_GOLD,
    *,
    verify_fixture_bytes: bool = True,
) -> dict[str, Any]:
    """Return a compact result or raise on any deterministic integrity failure."""
    packet = packet_path.read_text(encoding="utf-8")
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    development_digests: dict[str, set[str]] = {}
    for segment in gold["segments"]:
        development_digests.setdefault(str(segment["fixture_path"]), set()).add(
            str(segment["source_text_sha256"])
        )
    entries = list(_ENTRY.finditer(packet))
    if len(entries) != 50:
        raise ValueError("Held-out packet must contain exactly 50 paragraph entries.")
    expected_numbers = [f"{value:03d}" for value in range(1, 51)]
    actual_numbers = [match.group("number") for match in entries]
    if actual_numbers != expected_numbers:
        raise ValueError("Held-out packet entry IDs must be contiguous and ordered.")

    fixture_counts: dict[str, int] = {}
    identities: set[tuple[str, str]] = set()
    observed_tags: set[str] = set()
    annotated_count = 0
    literal_gold_count = 0
    resolved_gold_count = 0
    missing_fixtures: set[str] = set()
    for match in entries:
        body = match.group("body").rstrip()
        fixture_path = _metadata(body, "Fixture")
        fixture_sha256 = _metadata(body, "Fixture SHA-256")
        representation_id = _metadata(body, "Representation")
        paragraph_node_id = _metadata(body, "Paragraph node")
        paragraph_sha256 = _metadata(body, "Paragraph text SHA-256")
        source = _required_match(_SOURCE_TEXT, body, "authoritative paragraph text").group("text")
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != paragraph_sha256:
            raise ValueError(f"HO-{match.group('number')} paragraph digest does not match.")
        if not representation_id.startswith("rep_") or not paragraph_node_id.startswith(
            f"nod_{representation_id.removeprefix('rep_')}_"
        ):
            raise ValueError(f"HO-{match.group('number')} representation lineage is invalid.")
        identity = (fixture_sha256, paragraph_sha256)
        if identity in identities:
            raise ValueError("Held-out packet repeats one authoritative paragraph identity.")
        identities.add(identity)
        segment_digests = {
            hashlib.sha256(source_copy_view(segment.exact_text).encode("utf-8")).hexdigest()
            for segment in paragraph_source_segments(source, PARAGRAPH_SEGMENT_V3)
        }
        if segment_digests & development_digests.get(fixture_path, set()):
            raise ValueError(
                f"HO-{match.group('number')} overlaps the Organization development Gold."
            )
        fixture_counts[fixture_path] = fixture_counts.get(fixture_path, 0) + 1
        observed_tags.update(re.findall(r"`([^`]+)`", _metadata_line(body, "Selection conditions")))
        gold_match = _required_match(_GOLD, body, "Gold Organization Mentions")
        gold_value = gold_match.group("value")
        reviewer_notes = (gold_match.group("notes") or "").strip()
        gold_lines = tuple(line[2:] for line in gold_value.splitlines() if line.startswith("- "))
        if gold_value != "-":
            if not gold_lines:
                raise ValueError(f"HO-{match.group('number')} Gold field has an invalid shape.")
            if "None" in gold_lines and gold_lines != ("None",):
                raise ValueError(
                    f"HO-{match.group('number')} cannot mix None with Organization results."
                )
            for gold_result in gold_lines:
                if gold_result == "None":
                    continue
                if gold_result.startswith("resolved: "):
                    organization, components = _resolved_gold(gold_result)
                    if not reviewer_notes:
                        raise ValueError(
                            f"HO-{match.group('number')} resolved Organization "
                            f"{organization!r} requires Reviewer notes."
                        )
                    for component in components:
                        if component not in source:
                            raise ValueError(
                                f"HO-{match.group('number')} resolved source component "
                                f"{component!r} is not present in the source."
                            )
                    resolved_gold_count += 1
                    continue
                if gold_result not in source:
                    raise ValueError(
                        f"HO-{match.group('number')} Gold literal {gold_result!r} is not present "
                        "in the source."
                    )
                if gold_lines.count(gold_result) > source.count(gold_result):
                    raise ValueError(
                        f"HO-{match.group('number')} repeats Gold literal "
                        f"{gold_result!r} too many times."
                    )
                literal_gold_count += 1
            annotated_count += 1
        fixture = ROOT / fixture_path
        if verify_fixture_bytes:
            if not fixture.is_file():
                missing_fixtures.add(fixture_path)
            elif hashlib.sha256(fixture.read_bytes()).hexdigest() != fixture_sha256:
                raise ValueError(f"Held-out fixture bytes drifted: {fixture_path}")

    if missing_fixtures:
        return {
            "status": "fixture_missing",
            "entry_count": len(entries),
            "annotated_count": annotated_count,
            "missing_fixture_paths": sorted(missing_fixtures),
        }
    required_conditions = {
        "parenthetical_acronym",
        "possessive_boundary",
        "country_or_supranational",
        "organization_or_nonorganization",
        "generic_or_pronominal_reference",
        "context_dependent_reference",
        "acronym_reference",
        "negative_control",
    }
    if not required_conditions.issubset(observed_tags):
        raise ValueError("Held-out packet does not cover every required selection condition.")
    return {
        "status": "complete" if annotated_count == 50 else "awaiting_annotation",
        "entry_count": len(entries),
        "annotated_count": annotated_count,
        "unannotated_count": len(entries) - annotated_count,
        "fixture_counts": dict(sorted(fixture_counts.items())),
        "selection_conditions": sorted(observed_tags),
        "development_overlap_count": 0,
        "literal_gold_count": literal_gold_count,
        "resolved_gold_count": resolved_gold_count,
    }


def _metadata(body: str, label: str) -> str:
    line = _metadata_line(body, label)
    match = re.fullmatch(rf"- {re.escape(label)}: `(?P<value>[^`]+)`", line)
    if match is None:
        raise ValueError(f"Held-out packet {label} metadata is invalid.")
    return match.group("value")


def _metadata_line(body: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}: .+$", body, re.M)
    if match is None:
        raise ValueError(f"Held-out packet misses {label} metadata.")
    return match.group(0)


def _required_match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    match = pattern.search(value)
    if match is None:
        raise ValueError(f"Held-out packet misses {label}.")
    return match


def _resolved_gold(value: str) -> tuple[str, tuple[str, ...]]:
    expression = value.removeprefix("resolved: ")
    parts = tuple(part.strip() for part in expression.split("<=", maxsplit=1))
    if len(parts) != 2 or not parts[0]:
        raise ValueError("Resolved Organization must declare exact source components.")
    components = tuple(part.strip() for part in parts[1].split("|") if part.strip())
    if len(components) < 2:
        raise ValueError("Resolved Organization requires at least two source components.")
    return parts[0], components


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    args = parser.parse_args()
    result = validate_held_out_packet(args.packet, args.gold)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] != "fixture_missing" else 1


if __name__ == "__main__":
    raise SystemExit(main())
