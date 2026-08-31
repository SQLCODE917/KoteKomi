"""Compile the reviewed Organization held-out packet into exact Source spans."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    derive_source_copy_view,
    paragraph_source_segments,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = ROOT / "docs/2026-08-28-organization-mention-held-out-annotation-packet.md"
DEFAULT_DEVELOPMENT_GOLD = ROOT / "docs/php1-organization-mention-gold-v1.json"
DEFAULT_OUTPUT = ROOT / "docs/organization-mention-held-out-gold-v1.json"

CATALOG_SCHEMA_VERSION = "organization_mention_held_out_gold_v1"
ANNOTATION_POLICY_ID = "named_organization_mention_v1"
ANNOTATION_STATUS = "human_reviewed_held_out_gold"

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


def compile_held_out_catalog(
    packet_path: Path = DEFAULT_PACKET,
    development_gold_path: Path = DEFAULT_DEVELOPMENT_GOLD,
    *,
    verify_fixture_bytes: bool = True,
) -> dict[str, Any]:
    """Compile one exact, source-bound held-out Gold catalog."""
    packet_bytes = packet_path.read_bytes()
    packet = packet_bytes.decode("utf-8")
    development = cast(
        dict[str, Any], json.loads(development_gold_path.read_text(encoding="utf-8"))
    )
    development_digests = {
        (str(segment["fixture_path"]), str(segment["source_text_sha256"]))
        for segment in cast(list[dict[str, Any]], development["segments"])
    }
    segments: list[dict[str, Any]] = []
    resolved_references: list[dict[str, Any]] = []
    paragraph_records: list[dict[str, Any]] = []
    literal_count = 0
    entries = list(_ENTRY.finditer(packet))
    if len(entries) != 50:
        raise ValueError("Held-out packet must contain exactly 50 paragraphs.")
    for match in entries:
        case_id = f"HO-{match.group('number')}"
        body = match.group("body").rstrip()
        fixture_path = _metadata(body, "Fixture")
        fixture_sha256 = _metadata(body, "Fixture SHA-256")
        representation_id = _metadata(body, "Representation")
        paragraph_node_id = _metadata(body, "Paragraph node")
        paragraph_sha256 = _metadata(body, "Paragraph text SHA-256")
        source = _required_match(_SOURCE_TEXT, body, "authoritative paragraph text").group("text")
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != paragraph_sha256:
            raise ValueError(f"{case_id} paragraph text drifted from its digest.")
        fixture = ROOT / fixture_path
        if verify_fixture_bytes:
            if not fixture.is_file():
                raise FileNotFoundError(f"Held-out fixture is missing: {fixture_path}")
            if hashlib.sha256(fixture.read_bytes()).hexdigest() != fixture_sha256:
                raise ValueError(f"Held-out fixture bytes drifted: {fixture_path}")
        gold_match = _required_match(_GOLD, body, "Gold Organization Mentions")
        gold_lines = tuple(
            line[2:] for line in gold_match.group("value").splitlines() if line.startswith("- ")
        )
        if gold_lines == ("None",):
            literal_expressions: tuple[str, ...] = ()
            resolved_values: tuple[tuple[str, tuple[str, ...]], ...] = ()
        else:
            literal_expressions = tuple(
                value for value in gold_lines if not value.startswith("resolved: ")
            )
            resolved_values = tuple(
                _resolved_gold(value) for value in gold_lines if value.startswith("resolved: ")
            )
        literal_spans = _allocate_literal_spans(source, literal_expressions)
        source_segments = paragraph_source_segments(source, PARAGRAPH_SEGMENT_V3)
        segment_records: list[dict[str, Any]] = []
        segment_id_by_label: dict[str, str] = {}
        for source_segment in source_segments:
            exact_text = source_segment.exact_text
            exact_digest = hashlib.sha256(exact_text.encode("utf-8")).hexdigest()
            copy_view = derive_source_copy_view(exact_text)
            source_text_digest = hashlib.sha256(copy_view.text.encode("utf-8")).hexdigest()
            if (fixture_path, source_text_digest) in development_digests:
                raise ValueError(f"{case_id} overlaps the development Gold catalog.")
            source_segment_id = _id(
                "src",
                fixture_sha256,
                paragraph_node_id,
                source_segment.label,
                exact_digest,
            )
            segment_id_by_label[source_segment.label] = source_segment_id
            record = {
                "case_ids": [case_id],
                "fixture_path": fixture_path,
                "fixture_sha256": fixture_sha256,
                "representation_id": representation_id,
                "paragraph_node_id": paragraph_node_id,
                "paragraph_text_sha256": paragraph_sha256,
                "source_segment_id": source_segment_id,
                "source_segment_label": source_segment.label,
                "source_text": copy_view.text,
                "source_text_sha256": source_text_digest,
                "authoritative_text": exact_text,
                "authoritative_text_sha256": exact_digest,
                "paragraph_start": source_segment.start_char,
                "paragraph_end": source_segment.end_char,
                "copy_to_authoritative_boundaries": list(
                    copy_view.copy_to_authoritative_boundaries
                ),
                "gold_mentions": [],
            }
            segment_records.append(record)
        for annotation_ordinal, (expression, paragraph_start, paragraph_end) in enumerate(
            literal_spans, start=1
        ):
            segment, record = _containing_segment(
                source_segments, segment_records, paragraph_start, paragraph_end
            )
            local_start = paragraph_start - segment.start_char
            local_end = paragraph_end - segment.start_char
            copy_start = _copy_boundary_index(record, local_start)
            copy_end = _copy_boundary_index(record, local_end)
            source_copy_expression = str(record["source_text"])[copy_start:copy_end]
            if " ".join(expression.split()) != source_copy_expression:
                raise ValueError(f"{case_id} Gold expression does not survive Source copy mapping.")
            cast(list[dict[str, Any]], record["gold_mentions"]).append(
                {
                    "annotation_ordinal": annotation_ordinal,
                    "text": source_copy_expression,
                    "authoritative_text": expression,
                    "start": copy_start,
                    "end": copy_end,
                    "authoritative_start": local_start,
                    "authoritative_end": local_end,
                    "paragraph_start": paragraph_start,
                    "paragraph_end": paragraph_end,
                }
            )
            literal_count += 1
        for record in segment_records:
            cast(list[dict[str, Any]], record["gold_mentions"]).sort(
                key=lambda item: (int(item["start"]), int(item["end"]), str(item["text"]))
            )
        for expected_name, component_expressions in resolved_values:
            components: list[dict[str, Any]] = []
            for component in component_expressions:
                occurrences = _eligible_occurrences(source, component)
                if not occurrences:
                    raise ValueError(
                        f"{case_id} resolved source component {component!r} is missing."
                    )
                paragraph_start, paragraph_end = occurrences[0]
                source_segment, record = _containing_segment(
                    source_segments, segment_records, paragraph_start, paragraph_end
                )
                local_start = paragraph_start - source_segment.start_char
                local_end = paragraph_end - source_segment.start_char
                components.append(
                    {
                        "text": component,
                        "source_segment_id": record["source_segment_id"],
                        "source_segment_label": source_segment.label,
                        "authoritative_start": local_start,
                        "authoritative_end": local_end,
                        "paragraph_start": paragraph_start,
                        "paragraph_end": paragraph_end,
                    }
                )
            resolved_references.append(
                {
                    "case_id": case_id,
                    "fixture_path": fixture_path,
                    "paragraph_node_id": paragraph_node_id,
                    "expected_organization_name": expected_name,
                    "source_components": components,
                    "scoring_status": "excluded_reference_resolution_gold",
                }
            )
        segments.extend(segment_records)
        paragraph_records.append(
            {
                "case_id": case_id,
                "fixture_path": fixture_path,
                "fixture_sha256": fixture_sha256,
                "representation_id": representation_id,
                "paragraph_node_id": paragraph_node_id,
                "paragraph_text_sha256": paragraph_sha256,
                "source_segment_ids": [
                    segment_id_by_label[source_segment.label] for source_segment in source_segments
                ],
                "reviewer_notes": (gold_match.group("notes") or "").strip(),
            }
        )
    if literal_count != 150 or len(resolved_references) != 5:
        raise ValueError("Held-out Gold counts do not match the reviewed contract.")
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "annotation_policy_id": ANNOTATION_POLICY_ID,
        "annotation_status": ANNOTATION_STATUS,
        "source_segment_policy_id": PARAGRAPH_SEGMENT_V3,
        "packet_path": str(packet_path.relative_to(ROOT)),
        "packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
        "paragraph_count": len(paragraph_records),
        "literal_gold_count": literal_count,
        "resolved_reference_count": len(resolved_references),
        "development_overlap_count": 0,
        "paragraphs": paragraph_records,
        "segments": sorted(
            segments,
            key=lambda item: (
                str(item["fixture_path"]),
                str(item["paragraph_node_id"]),
                str(item["source_segment_label"]),
            ),
        ),
        "resolved_references": sorted(
            resolved_references,
            key=lambda item: (str(item["case_id"]), str(item["expected_organization_name"])),
        ),
    }


def canonical_catalog_json(catalog: dict[str, Any]) -> str:
    return json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _allocate_literal_spans(
    source: str, expressions: tuple[str, ...]
) -> tuple[tuple[str, int, int], ...]:
    counts = Counter(expressions)
    occupied: list[tuple[int, int]] = []
    allocated: list[tuple[str, int, int]] = []
    for expression in sorted(counts, key=lambda item: (-len(item), item.casefold(), item)):
        eligible = [
            span
            for span in _eligible_occurrences(source, expression)
            if not any(max(span[0], start) < min(span[1], end) for start, end in occupied)
        ]
        required = counts[expression]
        if len(eligible) < required:
            raise ValueError(
                f"Gold expression {expression!r} has {len(eligible)} eligible source occurrences; "
                f"{required} are required."
            )
        for start, end in eligible[:required]:
            occupied.append((start, end))
            allocated.append((expression, start, end))
    return tuple(sorted(allocated, key=lambda item: (item[1], item[2], item[0])))


def _eligible_occurrences(source: str, expression: str) -> tuple[tuple[int, int], ...]:
    if not expression:
        raise ValueError("Gold expressions must be non-empty.")
    occurrences: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = source.find(expression, cursor)
        if start < 0:
            return tuple(occurrences)
        end = start + len(expression)
        left_valid = not expression[0].isalnum() or start == 0 or not source[start - 1].isalnum()
        right_valid = (
            not expression[-1].isalnum() or end == len(source) or not source[end].isalnum()
        )
        if left_valid and right_valid:
            occurrences.append((start, end))
        cursor = start + 1


def _containing_segment(
    source_segments: tuple[Any, ...],
    records: list[dict[str, Any]],
    paragraph_start: int,
    paragraph_end: int,
) -> tuple[Any, dict[str, Any]]:
    matches = [
        (segment, record)
        for segment, record in zip(source_segments, records, strict=True)
        if segment.start_char <= paragraph_start and segment.end_char >= paragraph_end
    ]
    if len(matches) != 1:
        raise ValueError("Gold expression must fit wholly inside one V3 Source segment.")
    return matches[0]


def _copy_boundary_index(record: dict[str, Any], authoritative_offset: int) -> int:
    boundaries = cast(list[int], record["copy_to_authoritative_boundaries"])
    matches = [index for index, value in enumerate(boundaries) if value == authoritative_offset]
    if len(matches) != 1:
        raise ValueError("Gold boundary does not map uniquely into the Source copy.")
    return matches[0]


def _resolved_gold(value: str) -> tuple[str, tuple[str, ...]]:
    expression = value.removeprefix("resolved: ")
    parts = tuple(part.strip() for part in expression.split("<=", maxsplit=1))
    if len(parts) != 2 or not parts[0]:
        raise ValueError("Resolved Organization must declare source components.")
    components = tuple(part.strip() for part in parts[1].split("|") if part.strip())
    if len(components) < 2:
        raise ValueError("Resolved Organization requires at least two source components.")
    return parts[0], components


def _metadata(body: str, label: str) -> str:
    matched = re.search(rf"^- {re.escape(label)}: `(?P<value>[^`]+)`$", body, re.M)
    if matched is None:
        raise ValueError(f"Held-out packet {label} metadata is invalid.")
    return matched.group("value")


def _required_match(pattern: re.Pattern[str], value: str, label: str) -> re.Match[str]:
    matched = pattern.search(value)
    if matched is None:
        raise ValueError(f"Held-out packet misses {label}.")
    return matched


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode('utf-8')).hexdigest()[:24]}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--development-gold", type=Path, default=DEFAULT_DEVELOPMENT_GOLD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-fixture-byte-check", action="store_true")
    arguments = parser.parse_args()
    catalog = compile_held_out_catalog(
        arguments.packet,
        arguments.development_gold,
        verify_fixture_bytes=not arguments.skip_fixture_byte_check,
    )
    arguments.output.write_text(canonical_catalog_json(catalog), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "complete",
                "output": str(arguments.output),
                "paragraph_count": catalog["paragraph_count"],
                "source_segment_count": len(catalog["segments"]),
                "literal_gold_count": catalog["literal_gold_count"],
                "resolved_reference_count": catalog["resolved_reference_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
