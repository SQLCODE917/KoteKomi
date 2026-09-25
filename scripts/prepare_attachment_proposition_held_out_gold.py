#!/usr/bin/env python3
"""Compile the Anthropic/DoD held-out Attachment proposition Gold.

This script turns the human-reviewed annotation packet into one exact,
source-bound held-out Gold catalog:

    scripts/prepare_attachment_proposition_held_out_gold.py --check

The packet embeds the authoritative Docling representation text for every
proposed Event. This script derives the whitespace-normalized ``source_text``,
its digest, the ``src_`` source_segment_id, and each fragment's exact range
without touching the Ledger or the Archive.

The script is model-free and never writes canonical state: it only reads the
committed packet and fixture and writes the Gold catalog JSON. Overlap against
the development/validation Source-Grounded Proposition Gold is proven zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = ROOT / "docs/2026-09-24-attachment-proposition-held-out-annotation-packet.md"
DEFAULT_OUTPUT = ROOT / "docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json"
DEVELOPMENT_GOLD = ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"

FIXTURE_PATH = "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf"
FIXTURE_SHA256 = "c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624"
REPRESENTATION_ID = "rep_e84869f6fcd4ed02c70a550a"
SOURCE_SEGMENT_POLICY_ID = "paragraph_segment_v3"
ANNOTATION_STATUS = "human_reviewed_held_out_gold"
SCHEMA_VERSION = "source_grounded_proposition_held_out_gold_v1"
CATALOG_ID = "anthropic-dod-attachment-proposition-held-out-gold-v1"

_REQUIREMENTS = frozenset(
    {
        "core_event",
        "attribution",
        "negation",
        "modality",
        "purpose",
        "comparison",
        "temporal",
    }
)

_HEADER = re.compile(
    r"^## (?P<event_id>AHE-[0-9]{3})\n(?P<body>.*?)(?=^## AHE-|\Z)",
    re.M | re.S,
)
_META = re.compile(r"^- (?P<key>[^:`]+): `(?P<value>[^`]*)`\s*$", re.M)
_AUTH_TEXT = re.compile(
    r"^### Authoritative source text\n\n```text\n(?P<text>.*?)\n```$",
    re.M | re.S,
)
_FRAGMENT = re.compile(
    r"^### Proposed fragment\n\n```text\n(?P<text>.*?)\n```$",
    re.M | re.S,
)
_NOTES = re.compile(r"^### Reviewer notes\n\n(?P<notes>.*?)\Z", re.M | re.S)
_CITATION_LEAD = re.compile(r"\[\d+\](?:\[\d+\])*")
_CITATION_TRAIL = re.compile(r"(?:\[\d+\])+$")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{_sha(chr(31).join(parts).encode('utf-8'))[:24]}"


def _normalized_copy(authoritative_text: str) -> str:
    """Match ``derive_source_copy_view``: collapse all whitespace runs to one space."""
    return " ".join(authoritative_text.split())


def _trimmed_fragment(normalized: str) -> tuple[str, int, int]:
    """Strip leading and trailing citation-marker groups; return (text, start, end)."""
    text = normalized.strip()
    start = normalized.index(text)
    idx = 0
    while True:
        matched = _CITATION_LEAD.match(text[idx:])
        if matched is None:
            break
        idx += matched.end()
    whitespace = 0
    while idx + whitespace < len(text) and text[idx + whitespace].isspace():
        whitespace += 1
    content_start = idx + whitespace
    content = text[content_start:]
    trailing = _CITATION_TRAIL.search(content)
    if trailing is not None:
        content = content[: trailing.start()].rstrip()
    return content, start + content_start, start + content_start + len(content)


def _parse_requirements(value: str, event_id: str) -> tuple[str, ...]:
    items = tuple(part.strip() for part in value.split(",") if part.strip())
    ordered = tuple(sorted(set(items)))
    if not items or set(items) - _REQUIREMENTS:
        raise ValueError(f"{event_id} declares unknown requirements: {value!r}")
    if ordered != items:
        raise ValueError(f"{event_id} requirements must be ordered and distinct.")
    return ordered


def _parse_packet(packet_text: str) -> tuple[dict[str, str], list[dict[str, Any]]]:
    header, _, body = packet_text.partition("## AHE-")
    header_meta = {m.group("key"): m.group("value") for m in _META.finditer(header)}
    events: list[dict[str, Any]] = []
    for match in _HEADER.finditer("## AHE-" + body):
        event_body = match.group("body")
        meta = dict(_META.findall(event_body))
        auth = _AUTH_TEXT.search(event_body)
        fragment = _FRAGMENT.search(event_body)
        notes = _NOTES.search(event_body)
        if auth is None or fragment is None:
            raise ValueError(f"{match.group('event_id')} misses text or fragment.")
        events.append(
            {
                "event_id": match.group("event_id"),
                "paragraph_node_id": meta["Paragraph node"],
                "source_segment_label": meta["Source segment label"],
                "event_meaning": meta["Event meaning"],
                "requirements": _parse_requirements(meta["Requirements"], match.group("event_id")),
                "review_rationale": meta["Review rationale"],
                "reviewer_notes": (notes.group("notes") if notes else "").strip(),
                "authoritative_text": auth.group("text"),
                "proposed_fragment": fragment.group("text"),
            }
        )
    return header_meta, events


def compile_catalog(packet_path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet_bytes = packet_path.read_bytes()
    packet_text = packet_bytes.decode("utf-8")
    header_meta, drafts = _parse_packet(packet_text)

    fixture = ROOT / header_meta["Fixture"]
    if not fixture.is_file():
        raise FileNotFoundError(f"Held-out fixture is missing: {fixture}")
    if _sha(fixture.read_bytes()) != FIXTURE_SHA256:
        raise ValueError("Held-out fixture bytes drifted from the locked digest.")
    if header_meta["Fixture SHA-256"] != FIXTURE_SHA256:
        raise ValueError("Packet fixture SHA-256 drifted.")
    if header_meta["Representation"] != REPRESENTATION_ID:
        raise ValueError("Packet representation drifted.")

    development = json.loads(DEVELOPMENT_GOLD.read_text(encoding="utf-8"))
    development_digests = {str(item["source_text_sha256"]) for item in development["events"]}

    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for draft in drafts:
        event_id = draft["event_id"]
        if event_id in seen:
            raise ValueError(f"Repeated event ID: {event_id}")
        seen.add(event_id)

        authoritative = draft["authoritative_text"]
        authoritative_sha = _sha(authoritative.encode("utf-8"))
        source_text = _normalized_copy(authoritative)
        source_text_sha = _sha(source_text.encode("utf-8"))
        if source_text_sha in development_digests:
            raise ValueError(f"{event_id} overlaps the development/validation Gold.")

        fragment_text, start, end = _trimmed_fragment(source_text)
        if source_text[start:end] != fragment_text:
            raise ValueError(f"{event_id} fragment range does not match its text.")
        if draft["proposed_fragment"] != fragment_text:
            raise ValueError(f"{event_id} proposed fragment drifted from the text.")

        source_segment_id = _id(
            "src",
            FIXTURE_SHA256,
            draft["paragraph_node_id"],
            draft["source_segment_label"],
            authoritative_sha,
        )

        events.append(
            {
                "event_id": event_id,
                "phase": "held_out",
                "paragraph_node_id": draft["paragraph_node_id"],
                "source_segment_id": source_segment_id,
                "source_segment_label": draft["source_segment_label"],
                "source_text_sha256": source_text_sha,
                "source_text": source_text,
                "authoritative_text_sha256": authoritative_sha,
                "authoritative_text": authoritative,
                "event_meaning": draft["event_meaning"],
                "fragments": [
                    {
                        "fragment_id": f"PGF-{event_id}-01",
                        "start": start,
                        "end": end,
                        "text": fragment_text,
                        "requirements": list(draft["requirements"]),
                    }
                ],
                "review_rationale": draft["review_rationale"],
                "reviewer_notes": draft["reviewer_notes"],
            }
        )

    if not events:
        raise ValueError("Held-out packet produced zero Events.")

    return {
        "schema_version": SCHEMA_VERSION,
        "catalog_id": CATALOG_ID,
        "review_status": "proposed",
        "annotation_status": ANNOTATION_STATUS,
        "source_segment_policy_id": SOURCE_SEGMENT_POLICY_ID,
        "development_overlap_count": 0,
        "fixture_path": FIXTURE_PATH,
        "fixture_sha256": FIXTURE_SHA256,
        "representation_id": REPRESENTATION_ID,
        "packet_path": str(packet_path.relative_to(ROOT)),
        "packet_sha256": _sha(packet_bytes),
        "event_count": len(events),
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    catalog = compile_catalog(args.packet)
    if args.check:
        committed = json.loads(args.output.read_text(encoding="utf-8"))
        if committed != catalog:
            raise SystemExit("committed Gold does not match the packet; re-run without --check.")
        print(
            json.dumps(
                {
                    "status": "consistent",
                    "catalog": str(args.output),
                    "event_count": catalog["event_count"],
                    "development_overlap_count": catalog["development_overlap_count"],
                },
                sort_keys=True,
            )
        )
        return 0
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "catalog": str(args.output),
                "catalog_sha256": _sha(args.output.read_bytes()),
                "event_count": catalog["event_count"],
                "development_overlap_count": catalog["development_overlap_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
