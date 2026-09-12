"""Deterministic construction and validation for source-grounded Events."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from kotekomi_domain import Event, EvidenceTarget

from kotekomi_application.hybrid_event_semantics import (
    SourceGroundedEventDraft,
    source_grounded_event_record_id,
)


def source_grounded_event_id(draft_id: str) -> str:
    """Derive an Event identity without optional semantic enrichment."""
    return source_grounded_event_record_id(draft_id)


def build_source_grounded_event(draft: SourceGroundedEventDraft) -> Event:
    """Construct the reviewable Event body from exact source grounding."""
    return Event(
        id=source_grounded_event_id(draft.id),
        name=draft.expression_text,
        mentions=(draft.mention,),
    )


def validate_source_grounded_event(
    event: Event,
    evidence_by_id: Mapping[str, EvidenceTarget],
) -> None:
    """Validate one Event and its embedded mention against authoritative targets."""
    if len(event.mentions) != 1:
        raise ValueError("A source-grounded Event requires exactly one EventMention.")
    mention = event.mentions[0]
    target_ids = (
        mention.head_evidence_target_id,
        mention.expression_evidence_target_id,
        mention.support_evidence_target_id,
    )
    missing = tuple(item for item in target_ids if item not in evidence_by_id)
    if missing:
        raise ValueError(
            "A source-grounded Event references missing EvidenceTarget records: "
            + ", ".join(missing)
        )
    head, expression, support = (evidence_by_id[item] for item in target_ids)
    lineage = {
        (
            target.source_id,
            target.document_id,
            target.representation_id,
            target.text_view_id,
            target.text_view_digest,
        )
        for target in (head, expression, support)
    }
    if len(lineage) != 1:
        raise ValueError("EventMention EvidenceTargets must share authoritative lineage.")
    if not (support.start_char <= expression.start_char < expression.end_char <= support.end_char):
        raise ValueError("EventMention expression must lie inside its support evidence.")
    if not (expression.start_char <= head.start_char < head.end_char <= expression.end_char):
        raise ValueError("EventMention head must lie inside its expression evidence.")
    if event.name != expression.exact_text:
        raise ValueError("A source-grounded Event name must equal its exact expression text.")


def load_event_mention_evidence(
    event: Event,
    get_evidence_target: Callable[[str], EvidenceTarget | None],
) -> dict[str, EvidenceTarget]:
    """Load every embedded EventMention target through one declared Ledger Port."""
    evidence: dict[str, EvidenceTarget] = {}
    for mention in event.mentions:
        for target_id in (
            mention.head_evidence_target_id,
            mention.expression_evidence_target_id,
            mention.support_evidence_target_id,
        ):
            target = get_evidence_target(target_id)
            if target is not None:
                evidence[target.id] = target
    return evidence
