#!/usr/bin/env python3
"""Prepare a review-required proposition Gold proposal from approved parent Gold."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from kotekomi_application import PARAGRAPH_SEGMENT_V3, paragraph_source_segments
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_pipelines.event_entity_connection_stage_local import (
    load_connection_gold_catalog,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragment,
    PropositionGoldFragmentRequirement,
    PropositionGoldReviewStatus,
    render_proposition_gold_review,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONNECTION_GOLD = REPOSITORY_ROOT / "docs/hsq-event-entity-connection-gold-v2.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection-gold", type=Path, default=DEFAULT_CONNECTION_GOLD)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()

    connection_path = args.connection_gold.resolve()
    connection, _, trigger = load_connection_gold_catalog(
        connection_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
    )
    trigger_by_id = {
        item.event_id: (segment.source_text, item)
        for segment in trigger.segments
        for item in segment.events
    }
    events: list[PropositionGoldEvent] = []
    for parent in connection.events:
        source_text, trigger_event = trigger_by_id[parent.event_id]
        occurrences = {item.occurrence_id: item for item in source_occurrences(source_text)}
        head = occurrences[trigger_event.head_occurrence_id]
        sentence = next(
            item
            for item in paragraph_source_segments(source_text, PARAGRAPH_SEGMENT_V3)
            if item.start_char <= head.start < head.end <= item.end_char
        )
        start, end = _trim_proposed_fragment(
            source_text,
            sentence.start_char,
            sentence.end_char,
        )
        requirements = _proposed_requirements(parent.event_meaning)
        events.append(
            PropositionGoldEvent(
                event_id=parent.event_id,
                phase=parent.phase,
                source_text_sha256=parent.source_text_sha256,
                source_text=source_text,
                event_meaning=parent.event_meaning,
                fragments=(
                    PropositionGoldFragment(
                        fragment_id=f"PGF-{parent.event_id}-01",
                        start=start,
                        end=end,
                        text=source_text[start:end],
                        requirements=requirements,
                    ),
                ),
                review_rationale=(
                    "Initial sentence-bound proposal only. A human must narrow or split this "
                    "range so it preserves this Event's complete meaning without importing "
                    "another proposition."
                ),
            )
        )
    trigger_path = (REPOSITORY_ROOT / connection.trigger_gold_path).resolve()
    catalog = PropositionGoldCatalog(
        catalog_id="hsq-source-grounded-proposition-gold-v1",
        review_status=PropositionGoldReviewStatus.PROPOSED,
        connection_gold_path=_relative(connection_path),
        connection_gold_sha256=_sha(connection_path.read_bytes()),
        trigger_gold_path=_relative(trigger_path),
        trigger_gold_sha256=_sha(trigger_path.read_bytes()),
        events=tuple(sorted(events, key=lambda item: (item.phase, item.event_id))),
    )
    output = args.output.resolve()
    review = args.review.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    review.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            catalog.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    review.write_text(render_proposition_gold_review(catalog), encoding="utf-8")
    print(
        json.dumps(
            {
                "catalog": str(output),
                "catalog_sha256": _sha(output.read_bytes()),
                "event_count": len(catalog.events),
                "review": str(review),
                "review_status": catalog.review_status.value,
            },
            sort_keys=True,
        )
    )
    return 0


def _trim_proposed_fragment(source_text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and source_text[start].isspace():
        start += 1
    while end > start and source_text[end - 1].isspace():
        end -= 1
    leading = re.match(r"\[[0-9]+\]\s*", source_text[start:end])
    if leading is not None:
        start += leading.end()
    trailing = re.search(r"\s*\[[0-9]+\]$", source_text[start:end])
    if trailing is not None:
        end = start + trailing.start()
    return start, end


def _proposed_requirements(
    meaning: str,
) -> tuple[PropositionGoldFragmentRequirement, ...]:
    lowered = meaning.casefold()
    requirements = {PropositionGoldFragmentRequirement.CORE_EVENT}
    if re.search(r"\b(said|stated|according to|viewed|assessed|noted|described)\b", lowered):
        requirements.add(PropositionGoldFragmentRequirement.ATTRIBUTION)
    if re.search(r"\b(not|no|refused|denied)\b", lowered):
        requirements.add(PropositionGoldFragmentRequirement.NEGATION)
    if re.search(r"\b(would|could|might|may|intended|sought)\b", lowered):
        requirements.add(PropositionGoldFragmentRequirement.MODALITY)
    if re.search(r"\b(instead of|same views|as evidence|over trump)\b", lowered):
        requirements.add(PropositionGoldFragmentRequirement.COMPARISON)
    if re.search(
        r"\b(january|february|march|april|may|june|july|august|september|"
        r"october|november|december|prior to|following month|that month|since|after|by)\b|"
        r"\b20[0-9]{2}\b",
        lowered,
    ):
        requirements.add(PropositionGoldFragmentRequirement.TEMPORAL)
    return tuple(sorted(requirements, key=lambda item: item.value))


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
