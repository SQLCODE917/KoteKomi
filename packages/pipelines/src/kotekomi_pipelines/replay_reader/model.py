"""Pure per-paragraph annotation model for the replay reader.

Two persisted coordinate systems are collapsed into paragraph-global offsets:

* Segment-local spans are rebuilt by re-running the HP-1 segmenter and deriving
  each ``SourceSegment`` identity with ``hybrid_source_segment_id``.
* Text-View absolute spans (``ReferenceSpan``) are shifted by the paragraph
  node's own start offset inside its Text View.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from kotekomi_application import (
    HYBRID_STAGE_ORDER,
    PARAGRAPH_SEGMENT_V3,
    HybridEntityGroundingPreview,
    HybridEventSemanticsPreview,
    HybridEventTriggerPreview,
    HybridExtractionPreview,
    HybridProposalPlan,
    HybridReferencePreview,
    HybridStageId,
    PlannedProposedChange,
    SourceSegment,
    StandingFactPlan,
    hybrid_source_segment_id,
    paragraph_source_segments,
)

STAGE_ORDER: tuple[str, ...] = tuple(item.value for item in HYBRID_STAGE_ORDER)

STAGE_LABELS: dict[str, str] = {
    HybridStageId.HP1_MENTIONS.value: "Mentions",
    HybridStageId.HP2_REFERENCES.value: "References",
    HybridStageId.HP3_GROUNDING.value: "Grounding",
    HybridStageId.HP4_EVENT_TRIGGERS.value: "Event triggers",
    HybridStageId.HP6_EVENT_SEMANTICS.value: "Events",
    HybridStageId.HP7_PROPOSAL_PLAN.value: "Proposal plan",
    HybridStageId.HP10_STANDING_FACTS.value: "Standing facts",
}


@dataclass(frozen=True)
class Span:
    """One exact half-open range in paragraph-local character offsets."""

    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Segment:
    """One authoritative paragraph SourceSegment with its HP-1 identity."""

    segment_id: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class MentionAnnotation:
    span: Span
    type_hints: tuple[str, ...]
    selected: bool
    producers: int


@dataclass(frozen=True)
class ReferenceAnnotation:
    source_span: Span
    target_spans: tuple[Span, ...]
    kind: str
    status: str
    reason: str


@dataclass(frozen=True)
class GroundingAnnotation:
    span: Span
    top_id: str | None
    top_label: str | None
    score: float | None


@dataclass(frozen=True)
class TriggerAnnotation:
    trigger_id: str
    span: Span
    head_span: Span
    label: str


@dataclass(frozen=True)
class EventAnnotation:
    trigger_span: Span | None
    trigger_label: str
    head_text: str
    expression_text: str


@dataclass(frozen=True)
class StandingFactAnnotation:
    subject_span: Span | None
    relation_span: Span
    object_span: Span | None
    subject_label: str
    relation_label: str
    object_selector: str
    disposition: str


@dataclass(frozen=True)
class ProposedChangeAnnotation:
    """One display-resolved PlannedProposedChange for the HP-7 plan."""

    change_id: str
    record_type: str
    record_id: str
    name: str


@dataclass(frozen=True)
class ProposalPlanAnnotation:
    """One HP-7 proposal decision binding a source event to its changes."""

    event_id: str
    event_text: str
    proposed_changes: tuple[ProposedChangeAnnotation, ...]


@dataclass(frozen=True)
class ParagraphAnnotationProfile:
    """UI-neutral derived intelligence for exactly one authoritative paragraph."""

    text: str
    segments: tuple[Segment, ...]
    mentions: tuple[MentionAnnotation, ...]
    references: tuple[ReferenceAnnotation, ...]
    groundings: tuple[GroundingAnnotation, ...]
    triggers: tuple[TriggerAnnotation, ...]
    events: tuple[EventAnnotation, ...]
    standing_facts: tuple[StandingFactAnnotation, ...]
    present_stages: frozenset[str]
    proposal_plan: tuple[ProposalPlanAnnotation, ...] = ()


def _source_segments(text: str) -> tuple[SourceSegment, ...]:
    return paragraph_source_segments(text, PARAGRAPH_SEGMENT_V3)


def _to_segment(representation_id: str, node_id: str, segment: SourceSegment) -> Segment:
    return Segment(
        segment_id=hybrid_source_segment_id(representation_id, node_id, segment),
        start=segment.start_char,
        end=segment.end_char,
        text=segment.exact_text,
    )


def build_segments(text: str, representation_id: str, node_id: str) -> tuple[Segment, ...]:
    """Rebuild the authoritative SourceSegments with their HP-1 identities."""
    return tuple(_to_segment(representation_id, node_id, seg) for seg in _source_segments(text))


def _segment_by_id(text: str, representation_id: str, node_id: str) -> dict[str, SourceSegment]:
    return {
        hybrid_source_segment_id(representation_id, node_id, seg): seg
        for seg in _source_segments(text)
    }


def normalize_segment_span(*, segment: SourceSegment, start: int, end: int) -> Span:
    """Map a segment-local start/end pair to a paragraph-global ``Span``."""
    if start < 0 or end <= start or end > len(segment.exact_text):
        raise ValueError("segment-local span falls outside its SourceSegment.")
    return Span(
        start=segment.start_char + start,
        end=segment.start_char + end,
        text=segment.exact_text[start:end],
    )


def normalize_text_view_span(
    *, start_char: int, end_char: int, text: str, node_start_char: int
) -> Span:
    """Map a Text-View absolute span to a paragraph-global ``Span``."""
    start = start_char - node_start_char
    end = end_char - node_start_char
    if start < 0 or end <= start:
        raise ValueError("reference span falls outside its paragraph node.")
    return Span(start=start, end=end, text=text)


def _resolve_segment(by_id: Mapping[str, SourceSegment], source_segment_id: str) -> SourceSegment:
    segment = by_id.get(source_segment_id)
    if segment is None:
        raise ValueError(f"stage output references unknown SourceSegment {source_segment_id}.")
    return segment


def _optional_span(segment: SourceSegment, start: int | None, end: int | None) -> Span | None:
    if start is None or end is None:
        return None
    return normalize_segment_span(segment=segment, start=start, end=end)


def _stage[T](
    stage_outputs: Mapping[str, object], stage: HybridStageId, expected: type[T]
) -> T | None:
    value = stage_outputs.get(stage.value)
    if value is None:
        return None
    if not isinstance(value, expected):
        raise ValueError(f"{stage.value} output is not a {expected.__name__}.")
    return value


def _mentions(
    preview: HybridExtractionPreview, by_id: Mapping[str, SourceSegment]
) -> tuple[MentionAnnotation, ...]:
    selected_ids = {
        candidate_id
        for decision in preview.boundary_decisions
        for candidate_id in decision.selected_candidate_ids
    }
    mentions: list[MentionAnnotation] = []
    for candidate in preview.candidates:
        segment = _resolve_segment(by_id, candidate.source_segment_id)
        mentions.append(
            MentionAnnotation(
                span=normalize_segment_span(
                    segment=segment, start=candidate.start, end=candidate.end
                ),
                type_hints=tuple(item.value for item in candidate.type_hints),
                selected=candidate.id in selected_ids,
                producers=len(candidate.observation_ids),
            )
        )
    return tuple(mentions)


def _references(
    preview: HybridReferencePreview, node_start_char: int
) -> tuple[ReferenceAnnotation, ...]:
    spans_by_id = {span.id: span for span in preview.semantic_antecedent_spans}
    references: list[ReferenceAnnotation] = []
    for decision in preview.reference_decisions:
        source = normalize_text_view_span(
            start_char=decision.reference_span.start_char,
            end_char=decision.reference_span.end_char,
            text=decision.reference_span.text,
            node_start_char=node_start_char,
        )
        targets = tuple(
            normalize_text_view_span(
                start_char=spans_by_id[span_id].start_char,
                end_char=spans_by_id[span_id].end_char,
                text=spans_by_id[span_id].text,
                node_start_char=node_start_char,
            )
            for span_id in decision.antecedent_span_ids
        )
        references.append(
            ReferenceAnnotation(
                source_span=source,
                target_spans=targets,
                kind=decision.reference_kind.value,
                status=decision.status.value,
                reason=decision.reason.value,
            )
        )
    return tuple(references)


def _groundings(
    preview: HybridEntityGroundingPreview, by_id: Mapping[str, SourceSegment]
) -> tuple[GroundingAnnotation, ...]:
    groundings: list[GroundingAnnotation] = []
    for link in preview.link_evidence:
        segment = _resolve_segment(by_id, link.source_segment_id)
        top = link.candidates[0] if link.candidates else None
        groundings.append(
            GroundingAnnotation(
                span=normalize_segment_span(segment=segment, start=link.start, end=link.end),
                top_id=top.wikidata_id if top else None,
                top_label=top.label if top else None,
                score=top.score if top else None,
            )
        )
    return tuple(groundings)


def _triggers(
    preview: HybridEventTriggerPreview, by_id: Mapping[str, SourceSegment]
) -> tuple[TriggerAnnotation, ...]:
    triggers: list[TriggerAnnotation] = []
    for trigger in preview.triggers:
        segment = _resolve_segment(by_id, trigger.source_segment_id)
        triggers.append(
            TriggerAnnotation(
                trigger_id=trigger.id,
                span=normalize_segment_span(segment=segment, start=trigger.start, end=trigger.end),
                head_span=normalize_segment_span(
                    segment=segment, start=trigger.head_start, end=trigger.head_end
                ),
                label=trigger.event_type_label,
            )
        )
    return tuple(triggers)


def _events(
    preview: HybridEventSemanticsPreview, triggers: tuple[TriggerAnnotation, ...]
) -> tuple[EventAnnotation, ...]:
    trigger_by_id = {trigger.trigger_id: trigger for trigger in triggers}
    events: list[EventAnnotation] = []
    for event in preview.source_grounded_events:
        trigger = trigger_by_id.get(event.trigger_id)
        events.append(
            EventAnnotation(
                trigger_span=trigger.span if trigger else None,
                trigger_label=trigger.label if trigger else "unresolved",
                head_text=event.head_text,
                expression_text=event.expression_text,
            )
        )
    return tuple(events)


def _standing_facts(
    plan: StandingFactPlan, by_id: Mapping[str, SourceSegment]
) -> tuple[StandingFactAnnotation, ...]:
    decision_by_draft = {decision.draft_id: decision for decision in plan.decisions}
    facts: list[StandingFactAnnotation] = []
    for draft in plan.drafts:
        segment = _resolve_segment(by_id, draft.source_segment_id)
        decision = decision_by_draft.get(draft.id)
        facts.append(
            StandingFactAnnotation(
                subject_span=_optional_span(segment, draft.subject_start, draft.subject_end),
                relation_span=normalize_segment_span(
                    segment=segment, start=draft.relation_start, end=draft.relation_end
                ),
                object_span=_optional_span(segment, draft.object_start, draft.object_end),
                subject_label=draft.subject_label,
                relation_label=draft.relation_label,
                object_selector=draft.object_selector,
                disposition=decision.disposition.value if decision else "unrecorded",
            )
        )
    return tuple(facts)


def _proposed_change_annotation(change: PlannedProposedChange) -> ProposedChangeAnnotation:
    """Resolve one planned change body into a display summary.

    HP-7 plans only ever plan ``Actor``, ``Organization``, and ``Event`` records,
    all of which carry a ``name``. Fall back to the record identity when a name is
    absent so an unsupported type still renders deterministically.
    """
    record = cast(dict[str, object], change.proposed_json["record"])
    record_type = cast(str, change.proposed_json["record_type"])
    record_id = cast(str, record["id"])
    name = cast(str, record["name"]) if isinstance(record.get("name"), str) else record_id
    return ProposedChangeAnnotation(
        change_id=change.id,
        record_type=record_type,
        record_id=record_id,
        name=name,
    )


def _proposals(
    plan: HybridProposalPlan,
    semantics_preview: HybridEventSemanticsPreview | None,
) -> tuple[ProposalPlanAnnotation, ...]:
    event_text_by_id = (
        {event.id: event.expression_text for event in semantics_preview.source_grounded_events}
        if semantics_preview is not None
        else {}
    )
    change_by_id = {
        change.id: _proposed_change_annotation(change) for change in plan.proposed_changes
    }
    proposals: list[ProposalPlanAnnotation] = []
    for decision in plan.decisions:
        proposals.append(
            ProposalPlanAnnotation(
                event_id=decision.source_grounded_event_id,
                event_text=event_text_by_id.get(
                    decision.source_grounded_event_id, decision.source_grounded_event_id
                ),
                proposed_changes=tuple(
                    change_by_id[change_id] for change_id in decision.proposed_change_ids
                ),
            )
        )
    return tuple(proposals)


def _check(span: Span, text: str) -> None:
    if not (0 <= span.start < span.end <= len(text)):
        raise ValueError("annotation span is outside the paragraph.")
    if text[span.start : span.end] != span.text:
        raise ValueError("annotation span text does not match the paragraph.")


def build_profile(
    *,
    text: str,
    representation_id: str,
    paragraph_node_id: str,
    node_start_char: int,
    stage_outputs: Mapping[str, object],
) -> ParagraphAnnotationProfile:
    """Derive one paragraph's annotation profile from persisted stage output."""
    by_id = _segment_by_id(text, representation_id, paragraph_node_id)

    mentions_preview = _stage(stage_outputs, HybridStageId.HP1_MENTIONS, HybridExtractionPreview)
    references_preview = _stage(stage_outputs, HybridStageId.HP2_REFERENCES, HybridReferencePreview)
    grounding_preview = _stage(
        stage_outputs, HybridStageId.HP3_GROUNDING, HybridEntityGroundingPreview
    )
    triggers_preview = _stage(
        stage_outputs, HybridStageId.HP4_EVENT_TRIGGERS, HybridEventTriggerPreview
    )
    semantics_preview = _stage(
        stage_outputs, HybridStageId.HP6_EVENT_SEMANTICS, HybridEventSemanticsPreview
    )
    standing_facts_plan = _stage(stage_outputs, HybridStageId.HP10_STANDING_FACTS, StandingFactPlan)
    proposal_plan = _stage(stage_outputs, HybridStageId.HP7_PROPOSAL_PLAN, HybridProposalPlan)

    mentions = _mentions(mentions_preview, by_id) if mentions_preview else ()
    references = _references(references_preview, node_start_char) if references_preview else ()
    groundings = _groundings(grounding_preview, by_id) if grounding_preview else ()
    triggers = _triggers(triggers_preview, by_id) if triggers_preview else ()
    events = _events(semantics_preview, triggers) if semantics_preview else ()
    standing_facts = _standing_facts(standing_facts_plan, by_id) if standing_facts_plan else ()
    proposals = _proposals(proposal_plan, semantics_preview) if proposal_plan else ()

    for mention in mentions:
        _check(mention.span, text)
    for reference in references:
        _check(reference.source_span, text)
        for target in reference.target_spans:
            _check(target, text)
    for grounding in groundings:
        _check(grounding.span, text)
    for trigger in triggers:
        _check(trigger.span, text)
        _check(trigger.head_span, text)
    for event in events:
        if event.trigger_span is not None:
            _check(event.trigger_span, text)
    for fact in standing_facts:
        if fact.subject_span is not None:
            _check(fact.subject_span, text)
        _check(fact.relation_span, text)
        if fact.object_span is not None:
            _check(fact.object_span, text)

    return ParagraphAnnotationProfile(
        text=text,
        segments=build_segments(text, representation_id, paragraph_node_id),
        mentions=mentions,
        references=references,
        groundings=groundings,
        triggers=triggers,
        events=events,
        standing_facts=standing_facts,
        present_stages=frozenset(stage_outputs),
        proposal_plan=proposals,
    )
