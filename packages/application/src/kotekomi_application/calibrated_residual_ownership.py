"""Calibrated residual-ownership records and pure functions for the R6 deliverable.

R6 closes the R5 transfer failures with four deterministic constraints, all model-free
at the Application Layer:

1. Boundary coverage -- a sentence-core sub-span is added to every Constituent Candidate
   Inventory so the Event trigger head's sentence is carried end-to-end (first content
   token through the sentence terminal punctuation). Any Gold fragment whose exact span
   still stays uncovered raises one typed :class:`BoundaryGap`, never a silent miss.
2. Event frame and attachment -- the R1 dependency-path ladder (``path_1`` then governed
   complement, then ``model_review``, with no path as ``not_attached``) marks every
   candidate; only ``attached`` candidates enter the selection task under one Event frame
   (trigger plus core constituents).
3. Calibration -- every Event selection carries one :class:`SelectionScore`; a score at or
   below the calibrated threshold, or a censored score, routes the Event to residual
   review.
4. Residual reservation -- the residual-review set names exactly the Events the primary
   deterministic selection path cannot close, so the model is invoked for those Events
   only.

Nothing here invokes a model, writes canonical state, or reads a held-out partition to
tune a decision.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentSourceRange,
)
from kotekomi_application.evaluation_remediation import (
    HeldOutGoldFragment,
    SelectionScore,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionTask,
    ParserConstituent,
    parser_constituent_id,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]
_FragmentId = Annotated[str, Field(pattern=r"^PGF-[A-Z]{3}-[0-9]{3}-[0-9]{2}$")]

_TRAILING_TERMINALS = frozenset({".", "!", "?"})
_CITATION_MARKER = re.compile(r"\[\d+\]\s*")
_SUBJECT_RELATIONS = frozenset({"nsubj", "nsubj:pass"})
_OBJECT_RELATIONS = frozenset({"obj", "iobj", "obl"})
_COMPLEMENT_RELATIONS = frozenset({"obj", "ccomp", "xcomp"})
_PUNCT_POS = frozenset({"punct", "PUNCT"})


class CandidateAttachmentMark(StrEnum):
    """One R1-ladder attachment mark for a candidate against an Event trigger head."""

    ATTACHED = "attached"
    NOT_ATTACHED = "not_attached"
    MODEL_REVIEW = "model_review"


class BoundaryGap(BaseModel):
    """One Gold fragment whose exact source span no candidate carries."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fragment_id: _FragmentId
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.start >= self.end:
            raise ValueError("A Boundary Gap requires a non-empty source range.")
        return self


class EventFrame(BaseModel):
    """One Event trigger plus its syntax-attached core constituents only."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    trigger: AttachmentSourceRange
    core_constituents: tuple[AttachmentSourceRange, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        spans = [(item.start, item.end) for item in self.core_constituents]
        if spans != sorted(spans):
            raise ValueError("Event frame core constituents must use source order.")
        if len(set(spans)) != len(spans):
            raise ValueError("Event frame core constituents must be distinct by exact span.")
        if (self.trigger.start, self.trigger.end) in spans:
            raise ValueError("Event frame trigger must not repeat as a core constituent.")
        return self


class ResidualReviewReason(StrEnum):
    """One named reason an Event left the primary selection path."""

    BELOW_THRESHOLD = "below_threshold"
    CENSORED = "censored"
    COMPOSITION_HOLD = "composition_hold"
    ATTRIBUTION_AMBIGUOUS = "attribution_ambiguous"
    BOUNDARY_GAP = "boundary_gap"


class SelectionRoutingDecision(StrEnum):
    """Terminal routing state of one Event selection."""

    ACCEPTED_SELECTION = "accepted_selection"
    RESIDUAL_REVIEW = "residual_review"


class SelectionRouting(BaseModel):
    """One Event's threshold decision plus its named review reason, when any."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    decision: SelectionRoutingDecision
    reason: ResidualReviewReason | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision is SelectionRoutingDecision.RESIDUAL_REVIEW and self.reason is None:
            raise ValueError("A residual-review route requires one reason.")
        if self.decision is SelectionRoutingDecision.ACCEPTED_SELECTION and self.reason is not None:
            raise ValueError("An accepted selection must not carry a review reason.")
        return self


class ResidualReviewSet(BaseModel):
    """The ordered Event IDs routed off the primary selection path."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_ids: tuple[_EventId, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.event_ids != tuple(sorted(set(self.event_ids))):
            raise ValueError("Residual-review Event IDs must be ordered and distinct.")
        return self


class CalibratedResidualOwnershipReport(BaseModel):
    """Sealed R6 report: boundary gaps, routing, residual set, and zero-write safety."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    boundary_gaps: tuple[BoundaryGap, ...]
    selection_routing: tuple[SelectionRouting, ...]
    residual_review_event_ids: tuple[_EventId, ...]
    model_execution_count: Annotated[int, Field(ge=0)]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.canonical_write_count != 0:
            raise ValueError("R6 report records canonical writes from a derived-only phase.")
        if self.proposed_change_count != 0:
            raise ValueError("R6 report records ProposedChanges from a derived-only phase.")
        if self.boundary_gaps != tuple(
            sorted(self.boundary_gaps, key=lambda item: item.fragment_id)
        ):
            raise ValueError("R6 boundary gaps must use fragment ID order.")
        routing_event_ids = tuple(item.event_id for item in self.selection_routing)
        if routing_event_ids != tuple(sorted(set(routing_event_ids))):
            raise ValueError("R6 selection routing must be ordered and distinct by Event ID.")
        residual_from_routing = tuple(
            item.event_id
            for item in self.selection_routing
            if item.decision is SelectionRoutingDecision.RESIDUAL_REVIEW
        )
        if self.residual_review_event_ids != residual_from_routing:
            raise ValueError("R6 residual-review set drifted from its routing decisions.")
        expected = calibrated_residual_ownership_report_fingerprint(self)
        if self.result_fingerprint != expected:
            raise ValueError("R6 report fingerprint does not match its contents.")
        return self


def augment_candidate_inventory_with_sentence_core(
    *,
    inventory: ConstituentCandidateInventory,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    trigger_head_start: int,
    trigger_head_end: int,
) -> ConstituentCandidateInventory:
    """Add the trigger head sentence's core span without inventing source characters."""
    if hashlib.sha256(source_text.encode()).hexdigest() != inventory.source_text_sha256:
        raise ValueError("Sentence-core augmentation source digest does not match the inventory.")
    span = _sentence_core_span(
        source_text=source_text,
        tokens=tokens,
        trigger_head_start=trigger_head_start,
        trigger_head_end=trigger_head_end,
    )
    existing = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    }
    if (span.start, span.end) in existing:
        return inventory
    token_ids = tuple(
        item.token_id for item in tokens if item.start >= span.start and item.end <= span.end
    )
    if not token_ids:
        raise ValueError("Sentence-core span must cover at least one dependency token.")
    added = ParserConstituent(
        constituent_id=parser_constituent_id(
            inventory.source_text_sha256, span.start, span.end
        ),
        event_id=inventory.event_id,
        source_text_sha256=inventory.source_text_sha256,
        constituent_range=span,
        token_ids=token_ids,
    )
    merged = tuple(
        sorted(inventory.constituents + (added,), key=lambda item: item.constituent_range.start)
    )
    return ConstituentCandidateInventory(
        event_id=inventory.event_id,
        source_text_sha256=inventory.source_text_sha256,
        constituents=merged,
    )


def detect_boundary_gaps(
    *,
    gold_fragments: Mapping[str, tuple[HeldOutGoldFragment, ...]],
    inventories: Mapping[str, ConstituentCandidateInventory],
) -> tuple[BoundaryGap, ...]:
    """Return one typed Boundary Gap per exact span no inventory candidate carries."""
    if set(gold_fragments) != set(inventories):
        raise ValueError("Boundary-gap detection requires one inventory per Gold Event.")
    gaps: list[BoundaryGap] = []
    for event_id in sorted(gold_fragments):
        spans = {
            (item.constituent_range.start, item.constituent_range.end)
            for item in inventories[event_id].constituents
        }
        for fragment in gold_fragments[event_id]:
            if (fragment.start, fragment.end) not in spans:
                gaps.append(
                    BoundaryGap(
                        fragment_id=fragment.fragment_id, start=fragment.start, end=fragment.end
                    )
                )
    return tuple(sorted(gaps, key=lambda item: item.fragment_id))


def mark_candidate_attachment(
    *,
    candidate: ParserConstituent,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    trigger_head_start: int,
    trigger_head_end: int,
) -> CandidateAttachmentMark:
    """Apply the R1 dependency-path ladder to one candidate against one trigger head."""
    token_by_id = {item.token_id: item for item in tokens}
    event_matches = [
        item for item in tokens if (item.start, item.end) == (trigger_head_start, trigger_head_end)
    ]
    if len(event_matches) != 1:
        raise ValueError("Attachment marking requires one unique Event trigger head token.")
    trigger = event_matches[0]

    candidate_tokens = tuple(
        token_by_id[token_id] for token_id in candidate.token_ids if token_id in token_by_id
    )
    if len(candidate_tokens) != len(candidate.token_ids):
        raise ValueError("Attachment marking references unknown candidate tokens.")

    if (candidate.constituent_range.start, candidate.constituent_range.end) == (
        trigger.start,
        trigger.end,
    ):
        return CandidateAttachmentMark.ATTACHED

    candidate_token_ids = {item.token_id for item in candidate_tokens}
    heads = [
        item
        for item in candidate_tokens
        if item.part_of_speech not in _PUNCT_POS
        and item.head_token_id is not None
        and item.head_token_id not in candidate_token_ids
    ]
    if len(heads) == 0:
        if trigger.token_id in candidate_token_ids:
            return CandidateAttachmentMark.MODEL_REVIEW
        return CandidateAttachmentMark.NOT_ATTACHED
    if len(heads) != 1:
        return CandidateAttachmentMark.MODEL_REVIEW
    anchor = heads[0]

    if anchor.sentence_id != trigger.sentence_id:
        return CandidateAttachmentMark.NOT_ATTACHED

    distance = _dependency_distance(trigger, anchor, token_by_id)
    if distance is None:
        return CandidateAttachmentMark.NOT_ATTACHED
    if distance <= 1:
        return CandidateAttachmentMark.ATTACHED
    if _governed_complement_scope(trigger, anchor, token_by_id):
        return CandidateAttachmentMark.ATTACHED
    return CandidateAttachmentMark.MODEL_REVIEW


def attached_constituents(
    *,
    inventory: ConstituentCandidateInventory,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    trigger_head_start: int,
    trigger_head_end: int,
) -> tuple[ParserConstituent, ...]:
    """Return the ordered candidates the R1 ladder attaches to the Event trigger head."""
    return tuple(
        item
        for item in inventory.constituents
        if mark_candidate_attachment(
            candidate=item,
            source_text=source_text,
            tokens=tokens,
            trigger_head_start=trigger_head_start,
            trigger_head_end=trigger_head_end,
        )
        is CandidateAttachmentMark.ATTACHED
    )


def build_event_frame(
    *,
    event_id: str,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    trigger_head_start: int,
    trigger_head_end: int,
    inventory: ConstituentCandidateInventory,
) -> EventFrame:
    """Derive one Event trigger plus its subject and object core constituents only."""
    if inventory.event_id != event_id:
        raise ValueError("Event frame references a mismatched Event inventory.")
    event_matches = [
        item for item in tokens if (item.start, item.end) == (trigger_head_start, trigger_head_end)
    ]
    if len(event_matches) != 1:
        raise ValueError("Event frame requires one unique Event trigger head token.")
    trigger = event_matches[0]
    trigger_range = AttachmentSourceRange(
        start=trigger.start, end=trigger.end, text=source_text[trigger.start : trigger.end]
    )
    core: dict[tuple[int, int], AttachmentSourceRange] = {}
    for dependent in tokens:
        if dependent.head_token_id != trigger.token_id:
            continue
        if dependent.dependency_relation not in (_SUBJECT_RELATIONS | _OBJECT_RELATIONS):
            continue
        span = _maximal_constituent_for(dependent, trigger, inventory)
        if span is not None:
            core[(span.start, span.end)] = span
    ordered = [core[key] for key in sorted(core)]
    return EventFrame(
        event_id=event_id,
        trigger=trigger_range,
        core_constituents=tuple(ordered),
    )


def render_event_frame_selection_task(
    *,
    event_id: str,
    source_text: str,
    inventory: ConstituentCandidateInventory,
    tokens: tuple[EventEntityLinguisticToken, ...],
    frame: EventFrame,
) -> ConstituentSelectionTask:
    """Render one selection task over the syntax-attached candidates under one Event frame."""
    if inventory.event_id != event_id:
        raise ValueError("Event-frame renderer references a mismatched Event inventory.")
    if frame.event_id != event_id:
        raise ValueError("Event-frame renderer references a mismatched Event frame.")
    if hashlib.sha256(source_text.encode()).hexdigest() != inventory.source_text_sha256:
        raise ValueError("Event-frame renderer source digest does not match the inventory.")
    attached = attached_constituents(
        inventory=inventory,
        source_text=source_text,
        tokens=tokens,
        trigger_head_start=frame.trigger.start,
        trigger_head_end=frame.trigger.end,
    )
    labels = tuple(f"C{ordinal}" for ordinal in range(1, len(attached) + 1))
    lines = [
        "Return a comma-separated subset of the Candidate labels, or NONE.",
        f"Event: {frame.trigger.text}",
        "Passage:",
        source_text,
        "Candidates:",
    ]
    for label, constituent in zip(labels, attached, strict=True):
        lines.append(f"{label}: {constituent.constituent_range.text}")
    rendered = "\n".join(lines)
    return ConstituentSelectionTask(
        event_id=event_id,
        source_text_sha256=inventory.source_text_sha256,
        source_text=source_text,
        constituent_labels=labels,
        rendered_input=rendered,
        rendered_input_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
    )


def route_selection_scores(
    *,
    scores: Mapping[str, SelectionScore],
    threshold: float,
) -> tuple[SelectionRouting, ...]:
    """Route one Selection Score per Event through the calibrated threshold."""
    if not math.isfinite(threshold) or threshold > 0:
        raise ValueError("Selection Score threshold must be a finite non-positive log probability.")
    routing: list[SelectionRouting] = []
    for event_id in sorted(scores):
        score = scores[event_id]
        if score.event_id != event_id:
            raise ValueError("Selection routing references a mismatched Event score.")
        if score.censored:
            routing.append(
                SelectionRouting(
                    event_id=event_id,
                    decision=SelectionRoutingDecision.RESIDUAL_REVIEW,
                    reason=ResidualReviewReason.CENSORED,
                )
            )
        elif score.label == "NONE":
            routing.append(
                SelectionRouting(
                    event_id=event_id,
                    decision=SelectionRoutingDecision.RESIDUAL_REVIEW,
                    reason=ResidualReviewReason.COMPOSITION_HOLD,
                )
            )
        elif score.log_probability is not None and score.log_probability <= threshold:
            routing.append(
                SelectionRouting(
                    event_id=event_id,
                    decision=SelectionRoutingDecision.RESIDUAL_REVIEW,
                    reason=ResidualReviewReason.BELOW_THRESHOLD,
                )
            )
        else:
            routing.append(
                SelectionRouting(
                    event_id=event_id,
                    decision=SelectionRoutingDecision.ACCEPTED_SELECTION,
                    reason=None,
                )
            )
    return tuple(routing)


def build_residual_review_set(
    *,
    scores: Mapping[str, SelectionScore],
    threshold: float,
) -> ResidualReviewSet:
    """Return the Event IDs the threshold routing leaves to residual review."""
    routing = route_selection_scores(scores=scores, threshold=threshold)
    return ResidualReviewSet(
        event_ids=tuple(
            item.event_id
            for item in routing
            if item.decision is SelectionRoutingDecision.RESIDUAL_REVIEW
        )
    )


def build_calibrated_residual_ownership_report(
    *,
    boundary_gaps: tuple[BoundaryGap, ...],
    selection_routing: tuple[SelectionRouting, ...],
    residual_review_event_ids: tuple[str, ...],
    model_execution_count: int,
) -> CalibratedResidualOwnershipReport:
    """Assemble and seal the R6 report with zero canonical writes and zero ProposedChanges."""
    draft = CalibratedResidualOwnershipReport.model_construct(
        boundary_gaps=boundary_gaps,
        selection_routing=selection_routing,
        residual_review_event_ids=residual_review_event_ids,
        model_execution_count=model_execution_count,
        canonical_write_count=0,
        proposed_change_count=0,
        result_fingerprint="0" * 64,
    )
    return CalibratedResidualOwnershipReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=calibrated_residual_ownership_report_fingerprint(draft),
    )


def calibrated_residual_ownership_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one R6 report draft."""
    if isinstance(value, BaseModel):
        payload: object = value.model_dump(mode="json", exclude={"result_fingerprint"})
    else:
        payload = {key: item for key, item in value.items() if key != "result_fingerprint"}
    return hashlib.sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _sentence_core_span(
    *,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    trigger_head_start: int,
    trigger_head_end: int,
) -> AttachmentSourceRange:
    """Derive the trigger head sentence's core span, first content token through terminal."""
    matches = [
        item for item in tokens if (item.start, item.end) == (trigger_head_start, trigger_head_end)
    ]
    if len(matches) != 1:
        raise ValueError("Sentence core span requires one unique Event trigger head token.")
    trigger = matches[0]
    sentence_tokens = tuple(
        sorted(
            (item for item in tokens if item.sentence_id == trigger.sentence_id),
            key=lambda item: item.start,
        )
    )
    if not sentence_tokens:
        raise ValueError("Sentence core span requires one sentence of dependency tokens.")
    start = sentence_tokens[0].start
    citation = _CITATION_MARKER.match(source_text[start:])
    if citation is not None:
        start += citation.end()
    end = sentence_tokens[-1].end
    while end < len(source_text) and source_text[end] in _TRAILING_TERMINALS:
        end += 1
    if end <= start:
        raise ValueError("Sentence core span collapsed to an empty source range.")
    return AttachmentSourceRange(start=start, end=end, text=source_text[start:end])


def _maximal_constituent_for(
    token: EventEntityLinguisticToken,
    trigger: EventEntityLinguisticToken,
    inventory: ConstituentCandidateInventory,
) -> AttachmentSourceRange | None:
    candidates = [
        item
        for item in inventory.constituents
        if token.token_id in item.token_ids and trigger.token_id not in item.token_ids
    ]
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda item: (
            item.constituent_range.end - item.constituent_range.start,
            -item.constituent_range.start,
        ),
    )
    return best.constituent_range


def _dependency_distance(
    start: EventEntityLinguisticToken,
    target: EventEntityLinguisticToken,
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> int | None:
    """Return the undirected dependency edge count between two tokens, or None."""
    if start.sentence_id != target.sentence_id:
        return None
    if start.token_id == target.token_id:
        return 0
    pending: list[tuple[str, int]] = [(start.token_id, 0)]
    seen: set[str] = set()
    while pending:
        current, distance = pending.pop(0)
        if current == target.token_id:
            return distance
        if current in seen:
            continue
        seen.add(current)
        token = token_by_id.get(current)
        if token is None:
            continue
        neighbours: list[str | None] = [token.head_token_id] if token.head_token_id else []
        neighbours.extend(
            item.token_id for item in token_by_id.values() if item.head_token_id == current
        )
        for neighbour in neighbours:
            if neighbour is not None and neighbour not in seen:
                pending.append((neighbour, distance + 1))
    return None


def _governed_complement_scope(
    trigger: EventEntityLinguisticToken,
    anchor: EventEntityLinguisticToken,
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> bool:
    """Return whether the anchor sits inside a governed complement subtree of the trigger."""
    complement_children = [
        item
        for item in token_by_id.values()
        if item.head_token_id == trigger.token_id
        and item.dependency_relation.split(":", maxsplit=1)[0] in _COMPLEMENT_RELATIONS
    ]
    return any(_is_ancestor(anchor, child, token_by_id) for child in complement_children)


def _is_ancestor(
    node: EventEntityLinguisticToken,
    ancestor: EventEntityLinguisticToken,
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> bool:
    current: EventEntityLinguisticToken | None = node
    while current is not None:
        if current.token_id == ancestor.token_id:
            return True
        current = token_by_id.get(current.head_token_id) if current.head_token_id else None
    return False