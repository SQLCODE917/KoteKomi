"""Pure per-paragraph annotation model for the replay reader.

Two persisted coordinate systems are preserved for source-aware presentation:

* Segment-local spans are rebuilt by re-running the HP-1 segmenter and deriving
  each ``SourceSegment`` identity with ``hybrid_source_segment_id``.
* Text-View absolute spans (``ReferenceSpan``) retain their source identities.
  Local targets also receive paragraph offsets; external targets remain absolute.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol, cast

from kotekomi_domain import Actor, DocumentRepresentationBundle, Event, Organization
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V2,
    SourceSegment,
    paragraph_source_segments,
)
from kotekomi_application.hybrid_document_orchestration import (
    HYBRID_STAGE_ORDER,
    HybridParagraphStageRecord,
    HybridStageId,
)
from kotekomi_application.hybrid_document_references import HybridReferencePreview, ReferenceSpan
from kotekomi_application.hybrid_entity_grounding import HybridEntityGroundingPreview
from kotekomi_application.hybrid_event_semantics import HybridEventSemanticsPreview
from kotekomi_application.hybrid_event_triggers import HybridEventTriggerPreview
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    effective_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    hybrid_source_segment_id,
)
from kotekomi_application.hybrid_proposed_changes import HybridProposalPlan, PlannedProposedChange
from kotekomi_application.hybrid_standing_facts import StandingFactPlan

STAGE_ORDER: tuple[str, ...] = tuple(item.value for item in HYBRID_STAGE_ORDER)


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
class ReferenceTargetAnnotation:
    node_id: str
    text_view_id: str
    start_char: int
    end_char: int
    text: str
    local_span: Span | None


@dataclass(frozen=True)
class ReferenceAnnotation:
    source_span: Span
    targets: tuple[ReferenceTargetAnnotation, ...]
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
    event_id: str
    trigger_span: Span
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
    trigger_span: Span
    proposed_changes: tuple[ProposedChangeAnnotation, ...]


@dataclass(frozen=True)
class ParagraphAnnotationProfile:
    """UI-neutral derived intelligence for exactly one authoritative paragraph."""

    text: str
    representation_id: str
    paragraph_node_id: str
    node_start_char: int
    text_view_id: str | None
    segments: tuple[Segment, ...]
    mentions: tuple[MentionAnnotation, ...]
    references: tuple[ReferenceAnnotation, ...]
    groundings: tuple[GroundingAnnotation, ...]
    triggers: tuple[TriggerAnnotation, ...]
    events: tuple[EventAnnotation, ...]
    standing_facts: tuple[StandingFactAnnotation, ...]
    present_stages: frozenset[str]
    proposal_plan: tuple[ProposalPlanAnnotation, ...] = ()
    stage_statuses: tuple[tuple[str, str], ...] = ()
    records: tuple[InspectionRecord, ...] = ()
    artifacts: tuple[ArtifactHandle, ...] = ()
    phase_diagnostics: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class InspectionRecord:
    key: str
    stage: str
    record_id: str
    record_type: str
    spans: tuple[Span, ...]
    data: dict[str, JsonValue]
    related_ids: tuple[str, ...] = ()
    trace_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactHandle:
    stage: str
    output_id: str
    path: str
    sha256: str


@dataclass(frozen=True)
class InspectionContext:
    ingestion_run_id: str
    state_root: str
    receipt_id: str | None = None
    policy_manifest_id: str | None = None
    coverage_report_id: str | None = None


@dataclass(frozen=True)
class ParagraphSnapshot:
    ordinal: int
    total: int
    profile: ParagraphAnnotationProfile
    status: str = "processing"
    error: str | None = None
    context: InspectionContext | None = None
    receipt_reused: bool = False
    gap_reasons: tuple[str, ...] = ()


class InspectionSourcePort(Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class InspectionProgressPort(Protocol):
    def __call__(self, snapshot: ParagraphSnapshot, /) -> None: ...


class InspectionControlPort(Protocol):
    def __call__(self) -> None: ...


class InspectionClipboardPort(Protocol):
    def copy(self, text: str) -> str: ...


def _source_segments(text: str) -> tuple[SourceSegment, ...]:
    return paragraph_source_segments(text, PARAGRAPH_SEGMENT_V2)


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
    if (start is None) != (end is None):
        raise ValueError("optional annotation span has incomplete coordinates.")
    if start is None or end is None:
        return None
    return normalize_segment_span(segment=segment, start=start, end=end)


def _stage[T](
    stage_outputs: Mapping[str, object], stage: HybridStageId, expected: type[T]
) -> T | None:
    if stage.value not in stage_outputs:
        return None
    value = stage_outputs[stage.value]
    if not isinstance(value, expected):
        raise ValueError(f"{stage.value} output is not a {expected.__name__}.")
    return value


def _mentions(
    preview: HybridExtractionPreview, by_id: Mapping[str, SourceSegment]
) -> tuple[MentionAnnotation, ...]:
    selected_ids = set(
        effective_mention_candidate_ids(preview.boundary_decisions, preview.boundary_adjudications)
    )
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


def _reference_target(
    span: ReferenceSpan,
    bundle: DocumentRepresentationBundle,
    paragraph_node_id: str,
    node_start_char: int,
) -> ReferenceTargetAnnotation:
    nodes = {node.id: node for node in bundle.nodes}
    views = {view.id: view for view in bundle.text_views}
    node = nodes.get(span.node_id)
    view = views.get(span.text_view_id)
    if node is None or view is None:
        raise ValueError("reference target source is missing.")
    if (
        span.representation_id != bundle.representation.id
        or node.text_view_id != view.id
        or not node.start_char <= span.start_char < span.end_char <= node.end_char
        or view.text[span.start_char : span.end_char] != span.text
    ):
        raise ValueError("reference target does not match its source.")
    local = None
    if span.node_id == paragraph_node_id:
        local = normalize_text_view_span(
            start_char=span.start_char,
            end_char=span.end_char,
            text=span.text,
            node_start_char=node_start_char,
        )
    return ReferenceTargetAnnotation(
        node_id=span.node_id,
        text_view_id=span.text_view_id,
        start_char=span.start_char,
        end_char=span.end_char,
        text=span.text,
        local_span=local,
    )


def _references(
    preview: HybridReferencePreview,
    bundle: DocumentRepresentationBundle | None,
    paragraph_node_id: str,
    node_start_char: int,
) -> tuple[ReferenceAnnotation, ...]:
    if bundle is None:
        raise ValueError("reference annotations require source context.")
    spans_by_id = {item.expanded_span.id: item.expanded_span for item in preview.alias_declarations}
    spans_by_id.update({span.id: span for span in preview.semantic_antecedent_spans})
    references: list[ReferenceAnnotation] = []
    for decision in preview.reference_decisions:
        source = _reference_target(
            decision.reference_span, bundle, paragraph_node_id, node_start_char
        )
        if source.local_span is None:
            raise ValueError("reference source is outside its paragraph.")
        targets: list[ReferenceTargetAnnotation] = []
        for span_id in decision.antecedent_span_ids:
            target = spans_by_id.get(span_id)
            if target is None:
                raise ValueError("reference target is missing.")
            targets.append(_reference_target(target, bundle, paragraph_node_id, node_start_char))
        references.append(
            ReferenceAnnotation(
                source_span=source.local_span,
                targets=tuple(targets),
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
        if trigger is None:
            raise ValueError("Event references a missing source trigger.")
        events.append(
            EventAnnotation(
                event_id=event.id,
                trigger_span=trigger.span,
                trigger_label=trigger.label,
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
        if decision is None:
            raise ValueError("standing fact references a missing decision.")
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
                disposition=decision.disposition.value,
            )
        )
    return tuple(facts)


def _proposed_change_annotation(change: PlannedProposedChange) -> ProposedChangeAnnotation:
    """Resolve one planned change body into a display summary.

    HP-7 plans only ``Actor``, ``Organization``, and ``Event`` records.
    Parse their Domain records explicitly before displaying a planned change.
    """
    record = cast(dict[str, object], change.proposed_json["record"])
    record_type = cast(str, change.proposed_json["record_type"])
    record_bytes = json.dumps(record, ensure_ascii=False)
    if record_type == "Actor":
        parsed = Actor.model_validate_json(record_bytes)
    elif record_type == "Organization":
        parsed = Organization.model_validate_json(record_bytes)
    elif record_type == "Event":
        parsed = Event.model_validate_json(record_bytes)
    else:
        raise ValueError(f"unsupported HP-7 record type: {record_type}.")
    return ProposedChangeAnnotation(
        change_id=change.id,
        record_type=record_type,
        record_id=parsed.id,
        name=parsed.name,
    )


def _proposals(
    plan: HybridProposalPlan,
    events: tuple[EventAnnotation, ...],
) -> tuple[ProposalPlanAnnotation, ...]:
    event_by_id = {event.event_id: event for event in events}
    change_by_id = {
        change.id: _proposed_change_annotation(change) for change in plan.proposed_changes
    }
    proposals: list[ProposalPlanAnnotation] = []
    for decision in plan.decisions:
        event = event_by_id.get(decision.source_grounded_event_id)
        if event is None:
            raise ValueError("proposal references a missing source-grounded Event.")
        proposals.append(
            ProposalPlanAnnotation(
                event_id=decision.source_grounded_event_id,
                event_text=event.expression_text,
                trigger_span=event.trigger_span,
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
    bundle: DocumentRepresentationBundle | None = None,
) -> ParagraphAnnotationProfile:
    """Derive one paragraph's annotation profile from persisted stage output."""
    by_id = _segment_by_id(text, representation_id, paragraph_node_id)
    if set(stage_outputs) - set(STAGE_ORDER):
        raise ValueError("unknown replay stage.")
    if bundle is not None and bundle.representation.id != representation_id:
        raise ValueError("source context belongs to another representation.")

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
    for preview in (
        mentions_preview,
        references_preview,
        grounding_preview,
        triggers_preview,
        semantics_preview,
        standing_facts_plan,
        proposal_plan,
    ):
        if preview is not None and preview.representation_id != representation_id:
            raise ValueError("stage output belongs to another representation.")

    mentions = _mentions(mentions_preview, by_id) if mentions_preview else ()
    references = (
        _references(references_preview, bundle, paragraph_node_id, node_start_char)
        if references_preview
        else ()
    )
    groundings = _groundings(grounding_preview, by_id) if grounding_preview else ()
    triggers = _triggers(triggers_preview, by_id) if triggers_preview else ()
    events = _events(semantics_preview, triggers) if semantics_preview else ()
    standing_facts = _standing_facts(standing_facts_plan, by_id) if standing_facts_plan else ()
    proposals = _proposals(proposal_plan, events) if proposal_plan else ()

    for mention in mentions:
        _check(mention.span, text)
    for reference in references:
        _check(reference.source_span, text)
        for target in reference.targets:
            if target.local_span is not None:
                _check(target.local_span, text)
    for grounding in groundings:
        _check(grounding.span, text)
    for trigger in triggers:
        _check(trigger.span, text)
        _check(trigger.head_span, text)
    for event in events:
        _check(event.trigger_span, text)
    for fact in standing_facts:
        if fact.subject_span is not None:
            _check(fact.subject_span, text)
        _check(fact.relation_span, text)
        if fact.object_span is not None:
            _check(fact.object_span, text)
    for proposal in proposals:
        _check(proposal.trigger_span, text)

    profile = ParagraphAnnotationProfile(
        text=text,
        representation_id=representation_id,
        paragraph_node_id=paragraph_node_id,
        node_start_char=node_start_char,
        text_view_id=next(
            (node.text_view_id for node in bundle.nodes if node.id == paragraph_node_id), None
        )
        if bundle is not None
        else None,
        segments=build_segments(text, representation_id, paragraph_node_id),
        mentions=mentions,
        references=references,
        groundings=groundings,
        triggers=triggers,
        events=events,
        standing_facts=standing_facts,
        present_stages=frozenset(stage_outputs),
        proposal_plan=proposals,
        stage_statuses=tuple(
            (stage, str(preview.terminal_status))
            for stage, preview in (
                ("hp1_mentions", mentions_preview),
                ("hp2_references", references_preview),
                ("hp3_grounding", grounding_preview),
                ("hp4_event_triggers", triggers_preview),
                ("hp6_event_semantics", semantics_preview),
                ("hp10_standing_facts", standing_facts_plan),
            )
            if preview is not None
        )
        + ((("hp7_proposal_plan", "complete"),) if proposal_plan is not None else ()),
    )

    return replace(
        profile,
        records=inspection_records(stage_outputs, profile),
        phase_diagnostics=tuple(
            (stage, tuple(getattr(output, "diagnostics", ())))
            for stage, output in stage_outputs.items()
        ),
    )


@dataclass(frozen=True)
class HybridParagraphProgress:
    ordinal: int
    total: int
    status: str
    receipt_reused: bool


@dataclass(frozen=True)
class HybridParagraphStageProgress:
    """One live event inside a single paragraph route.

    ``stage_id`` is ``None`` for the paragraph-started and paragraph-finished
    boundary events; otherwise it names the stage that just completed and
    ``stage_output`` carries that stage's parsed preview or plan object.
    """

    ordinal: int
    total: int
    representation_id: str
    paragraph_node_id: str
    stage_id: HybridStageId | None
    stage_output: object | None
    finished: bool


@dataclass(frozen=True)
class ParagraphInput:
    """One authoritative paragraph plus the persisted stage outputs behind it."""

    ordinal: int
    text: str
    representation_id: str
    paragraph_node_id: str
    node_start_char: int
    status: str
    gap_reasons: tuple[str, ...]
    stage_outputs: Mapping[str, object]
    bundle: DocumentRepresentationBundle | None = None
    context: InspectionContext | None = None
    artifacts: tuple[ArtifactHandle, ...] = ()
    phase_states: tuple[tuple[str, str], ...] = ()
    phase_diagnostics: tuple[tuple[str, tuple[str, ...]], ...] = ()
    phase_records: tuple[HybridParagraphStageRecord, ...] = ()


def inspection_records(
    outputs: Mapping[str, object], profile: ParagraphAnnotationProfile
) -> tuple[InspectionRecord, ...]:
    """Canonical IDs and decisions; presentation never reinterprets candidates."""
    rows: list[InspectionRecord] = []

    def add(
        stage: str,
        record_id: str,
        kind: str,
        spans: tuple[Span, ...],
        data: dict[str, JsonValue],
        related: tuple[str, ...] = (),
        traces: tuple[str, ...] = (),
    ) -> None:
        index = sum(r.stage == stage for r in rows)
        rows.append(
            InspectionRecord(
                f"{stage}:{index}", stage, record_id, kind, spans, data, related, traces
            )
        )

    hp1 = _stage(outputs, HybridStageId.HP1_MENTIONS, HybridExtractionPreview)
    if hp1 is not None:
        interpretations = {i.candidate_id: i for i in hp1.interpretations}
        judgments = {
            j.candidate_id: j.status.value for a in hp1.boundary_adjudications for j in a.judgments
        }
        for c, item in zip(hp1.candidates, profile.mentions, strict=True):
            related = tuple(d.id for d in hp1.boundary_decisions if c.id in d.candidate_ids)
            adjudications = tuple(
                a
                for a in hp1.boundary_adjudications
                if any(j.candidate_id == c.id for j in a.judgments)
            )
            interpretation = interpretations.get(c.id)
            data: dict[str, JsonValue] = {
                "effective_selected": item.selected,
                "type_hints": list(item.type_hints),
                "boundary_status": judgments.get(
                    c.id, "selected" if item.selected else "unresolved"
                ),
            }
            if interpretation is not None:
                data.update(
                    contextual_kind=interpretation.contextual_kind.value,
                    referentiality=interpretation.referentiality.value,
                    discourse_role=interpretation.discourse_role.value,
                )
            add(
                "hp1_mentions",
                c.id,
                "MentionCandidate",
                (item.span,),
                data,
                related
                + tuple(a.id for a in adjudications)
                + (() if interpretation is None else (interpretation.id,)),
                tuple(a.trace_id for a in adjudications)
                + (() if interpretation is None else (interpretation.trace_id,)),
            )
    hp2 = _stage(outputs, HybridStageId.HP2_REFERENCES, HybridReferencePreview)
    if hp2 is not None:
        for d, item in zip(hp2.reference_decisions, profile.references, strict=True):
            add(
                "hp2_references",
                d.id,
                "ReferenceDecision",
                (item.source_span,),
                {
                    "kind": item.kind,
                    "status": item.status,
                    "reason": item.reason,
                    "targets": [
                        {
                            "node_id": t.node_id,
                            "text_view_id": t.text_view_id,
                            "range": [t.start_char, t.end_char],
                        }
                        for t in item.targets
                    ],
                },
                tuple(d.antecedent_span_ids) + tuple(d.declaration_ids),
                (d.trace_id,),
            )
    hp3 = _stage(outputs, HybridStageId.HP3_GROUNDING, HybridEntityGroundingPreview)
    if hp3 is not None:
        for evidence, item in zip(hp3.link_evidence, profile.groundings, strict=True):
            data = {
                "candidate_id": evidence.candidate_id,
                "score": item.score,
                "identity": item.top_id or "NIL",
            }
            add(
                "hp3_grounding",
                evidence.id,
                "EntityLinkEvidence",
                (item.span,),
                data,
                (evidence.candidate_id,),
                (evidence.trace_id,),
            )
    hp4 = _stage(outputs, HybridStageId.HP4_EVENT_TRIGGERS, HybridEventTriggerPreview)
    if hp4 is not None:
        for trigger, item in zip(hp4.triggers, profile.triggers, strict=True):
            add(
                "hp4_event_triggers",
                trigger.id,
                "EventTriggerDraft",
                (item.span, item.head_span),
                {"type": item.label},
                traces=(trigger.trace_id,),
            )
    hp6 = _stage(outputs, HybridStageId.HP6_EVENT_SEMANTICS, HybridEventSemanticsPreview)
    if hp6 is not None:
        for event, item in zip(hp6.source_grounded_events, profile.events, strict=True):
            add(
                "hp6_event_semantics",
                event.id,
                "SourceGroundedEventDraft",
                (item.trigger_span,),
                {"type": item.trigger_label},
                (event.trigger_id,),
                tuple(
                    e.frame_selection_trace_id
                    for e in hp6.semantic_events
                    if e.event_subject_id == event.event_subject_id
                ),
            )
    hp7 = _stage(outputs, HybridStageId.HP7_PROPOSAL_PLAN, HybridProposalPlan)
    if hp7 is not None:
        for decision, item in zip(hp7.decisions, profile.proposal_plan, strict=True):
            add(
                "hp7_proposal_plan",
                decision.id,
                "ProposalAdmissionDecision",
                (item.trigger_span,),
                {
                    "disposition": decision.disposition,
                    "proposed_change_ids": list(decision.proposed_change_ids),
                },
                (decision.source_grounded_event_id,),
                tuple(
                    t.id
                    for t in hp7.traces
                    if decision.source_grounded_event_id in t.input_record_ids
                ),
            )
    hp10 = _stage(outputs, HybridStageId.HP10_STANDING_FACTS, StandingFactPlan)
    if hp10 is not None:
        decisions = {d.draft_id: d for d in hp10.decisions}
        for draft, item in zip(hp10.drafts, profile.standing_facts, strict=True):
            decision = decisions[draft.id]
            add(
                "hp10_standing_facts",
                draft.id,
                "StandingFactDraft",
                (item.relation_span,)
                + tuple(s for s in (item.subject_span, item.object_span) if s is not None),
                {
                    "disposition": decision.disposition.value,
                    "reason_codes": [r.value for r in decision.reason_codes],
                    "span_roles": cast(
                        JsonValue,
                        ["relation"]
                        + (["subject"] if item.subject_span is not None else [])
                        + (["object"] if item.object_span is not None else []),
                    ),
                },
                (decision.id,)
                + tuple(
                    x
                    for x in (decision.qualification_id, decision.proposition_decision_id)
                    if x is not None
                ),
                tuple(t.id for t in hp10.traces if draft.model_run_id in t.execution_record_ids),
            )
    return tuple(rows)


class InspectionArtifactPort(Protocol):
    def describe_stage(self, stage: HybridStageId, output_id: str) -> ArtifactHandle: ...
