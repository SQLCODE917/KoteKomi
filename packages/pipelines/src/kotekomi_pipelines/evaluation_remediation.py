"""Evaluation remediation for the R5 deliverable (Pipeline layer).

This Pipeline composes the model-free Application Layer evaluator against the frozen
held-out Transfer Gold, the pinned Stanza dependency runtime, and the frozen fixture
and representation. It re-derives one Event trigger head and one Constituent Candidate
Inventory per Held-out Event and derives entity references for the trigger head's core
event dependents, all without a model and without reading Transfer Gold fragments or
meanings. It then lets the local model return one Constituent Selection per Event while
the runner preserves Token Probability Evidence, composes one DecontextualizedProposition
or typed hold, and seals one error-type census and transfer report with zero canonical
writes and zero ProposedChanges.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal, Self

from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionTask,
    DecontextualizationEntityRef,
    DecontextualizedProposition,
    EventEntityLinguisticToken,
    HeldOutGoldEvent,
    HeldOutGoldFragment,
    build_constituent_candidate_inventory,
    build_decontextualized_proposition,
    constituent_selection_labels,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[a-f0-9]{64}$"
_HELD_OUT_EVENT_ID = r"^AHE-[0-9]{3}$"

PINNED_GOLD_SHA256 = "3bbfd1bc76d3f78e8853e84303c47e46aa1d430ed3a5cc3b22391adceca4a270"
PINNED_FIXTURE_SHA256 = "c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624"
PINNED_STANZA_LOCK_SHA256 = "4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3"
HELD_OUT_REPRESENTATION_ID = "rep_e84869f6fcd4ed02c70a550a"
HELD_OUT_SOURCE_SEGMENT_POLICY_ID = "paragraph_segment_v3"
HELD_OUT_EVENT_COUNT = 53

_SUBJECT_RELATIONS = frozenset({"nsubj", "nsubj:pass"})
_OBJECT_RELATIONS = frozenset({"obj", "iobj", "obl"})


class HeldOutPropositionGoldEvent(BaseModel):
    """One held-out Transfer Gold Event with its authoritative source and fragments."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=_HELD_OUT_EVENT_ID)]
    phase: Literal["held_out"]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    authoritative_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    authoritative_text: Annotated[str, Field(min_length=1)]
    event_meaning: Annotated[str, Field(min_length=1)]
    fragments: tuple[HeldOutGoldFragment, ...]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_segment_label: Annotated[str, Field(min_length=1)]
    review_rationale: Annotated[str, Field(min_length=1)]
    reviewer_notes: Annotated[str, Field(default="")] = ""

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Held-out Gold SourceSegment digest does not match its text.")
        authoritative_digest = hashlib.sha256(self.authoritative_text.encode()).hexdigest()
        if authoritative_digest != self.authoritative_text_sha256:
            raise ValueError("Held-out Gold authoritative text digest does not match its text.")
        if not self.fragments:
            raise ValueError("Held-out Gold Event requires one fragment.")
        if any(
            item.end > len(self.source_text) or self.source_text[item.start : item.end] != item.text
            for item in self.fragments
        ):
            raise ValueError("Held-out Gold fragment does not replay its SourceSegment.")
        return self


class HeldOutPropositionGoldCatalog(BaseModel):
    """Frozen held-out Transfer Gold catalog that never informed a CEA decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["source_grounded_proposition_held_out_gold_v1"]
    catalog_id: Annotated[str, Field(min_length=1)]
    review_status: Literal["proposed", "approved"]
    annotation_status: Literal["human_reviewed_held_out_gold"]
    development_overlap_count: Literal[0]
    event_count: Annotated[int, Field(ge=0)]
    representation_id: Annotated[str, Field(min_length=1)]
    source_segment_policy_id: Annotated[str, Field(min_length=1)]
    fixture_path: Annotated[str, Field(min_length=1)]
    fixture_sha256: Annotated[str, Field(pattern=_SHA256)]
    packet_path: Annotated[str, Field(min_length=1)]
    packet_sha256: Annotated[str, Field(pattern=_SHA256)]
    events: tuple[HeldOutPropositionGoldEvent, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.event_count != len(self.events):
            raise ValueError("Held-out Gold event count does not match its events.")
        if any(item.phase != "held_out" for item in self.events):
            raise ValueError("Held-out Gold contains a non-held-out Event phase.")
        if len({item.event_id for item in self.events}) != len(self.events):
            raise ValueError("Held-out Gold repeats an Event ID.")
        return self


def verify_held_out_frozen_evidence(
    *,
    gold: Path,
    fixture: Path,
    stanza_lock: Path,
) -> None:
    """Reject any R5 frozen evidence that drifted from its pinned SHA-256 digest."""
    for path, pinned in (
        (gold, PINNED_GOLD_SHA256),
        (fixture, PINNED_FIXTURE_SHA256),
        (stanza_lock, PINNED_STANZA_LOCK_SHA256),
    ):
        if _sha256_file(path) != pinned:
            raise ValueError(f"R5 frozen evidence drifted from its pinned digest: {path}.")


def load_held_out_proposition_gold(path: Path) -> HeldOutPropositionGoldCatalog:
    """Load and validate the frozen held-out Transfer Gold catalog."""
    catalog = HeldOutPropositionGoldCatalog.model_validate_json(path.read_bytes())
    if catalog.review_status != "approved":
        raise ValueError("R5 requires approved held-out Transfer Gold.")
    if catalog.representation_id != HELD_OUT_REPRESENTATION_ID:
        raise ValueError("R5 held-out Gold representation drifted.")
    if catalog.source_segment_policy_id != HELD_OUT_SOURCE_SEGMENT_POLICY_ID:
        raise ValueError("R5 held-out Gold source segment policy drifted.")
    if catalog.event_count != HELD_OUT_EVENT_COUNT:
        raise ValueError("R5 held-out Gold event count drifted.")
    return catalog


def held_out_gold_events(catalog: HeldOutPropositionGoldCatalog) -> dict[str, HeldOutGoldEvent]:
    """Map one held-out Gold catalog into the Application Layer evaluator input."""
    return {
        item.event_id: HeldOutGoldEvent(
            event_id=item.event_id,
            source_text_sha256=item.source_text_sha256,
            event_meaning=item.event_meaning,
            fragments=item.fragments,
        )
        for item in catalog.events
    }


def derive_held_out_trigger_head(
    *,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[int, int]:
    """Return the first sentence-root dependency token span as the held-out Event trigger head.

    A Held-out SourceSegment is one paragraph and may parse into more than one sentence, so
    the root of the earliest sentence selects the held-out Event head deterministically and
    without reading Transfer Gold. The leading paragraph sentence carries the Event's main
    predicate; trailing sentences and standalone citation fragments never select the head.
    Reporting-predicate and complement errors surface later in the error-type census, not here.
    """
    roots = [token for token in tokens if token.head_token_id is None]
    if not roots:
        raise ValueError("Held-out trigger derivation requires at least one sentence root.")
    # Tokens are source-ordered, so the first root belongs to the earliest sentence.
    root = roots[0]
    if source_text[root.start : root.end] != root.text:
        raise ValueError("Held-out trigger head drifted from its source text.")
    return root.start, root.end


def derive_held_out_entities(
    *,
    source_text: str,
    source_text_sha256: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    inventory: ConstituentCandidateInventory,
) -> tuple[DecontextualizationEntityRef, ...]:
    """Derive held-out entity references for the trigger head's core event dependents.

    Each derived entity is a source-exact maximal constituent of one subject or object
    dependent of the trigger head. The entity kind defaults to ``actor`` because no model
    and no connection Gold is available; the kind does not gate any R5 error type.
    """
    if hashlib.sha256(source_text.encode()).hexdigest() != source_text_sha256:
        raise ValueError("Held-out entity derivation source digest drifted.")
    head = _head_token(tokens)
    spans: dict[tuple[int, int], AttachmentSourceRange] = {}
    for dependent in _dependents(head, tokens):
        if dependent.dependency_relation not in (_SUBJECT_RELATIONS | _OBJECT_RELATIONS):
            continue
        constituent = _maximal_constituent(dependent, head, inventory)
        if constituent is not None:
            spans[(constituent.start, constituent.end)] = constituent
    ordered = [spans[key] for key in sorted(spans)]
    entities: list[DecontextualizationEntityRef] = []
    for index, span in enumerate(ordered):
        if 101 + index > 999:
            raise ValueError("Held-out entity derivation exceeded the derived identity band.")
        entities.append(
            DecontextualizationEntityRef(
                entity_id=f"EGE-{101 + index:03d}",
                entity_kind="actor",
                canonical_name=span.text,
                accepted_source_occurrences=(span,),
            )
        )
    return tuple(entities)


def build_held_out_inventories(
    *,
    catalog: HeldOutPropositionGoldCatalog,
    tokens_by_digest: Mapping[str, tuple[EventEntityLinguisticToken, ...]],
) -> dict[str, ConstituentCandidateInventory]:
    """Derive one Constituent Candidate Inventory per Held-out Event without a model."""
    inventories: dict[str, ConstituentCandidateInventory] = {}
    for event in catalog.events:
        tokens = tokens_by_digest[event.source_text_sha256]
        head_start, head_end = derive_held_out_trigger_head(
            source_text=event.source_text, tokens=tokens
        )
        inventories[event.event_id] = build_constituent_candidate_inventory(
            source_text=event.source_text,
            event_id=event.event_id,
            tokens=tokens,
            event_expression_start=head_start,
            event_expression_end=head_end,
        )
    return inventories


def render_held_out_selection_tasks(
    *,
    catalog: HeldOutPropositionGoldCatalog,
    inventories: Mapping[str, ConstituentCandidateInventory],
) -> tuple[ConstituentSelectionTask, ...]:
    """Render one boundary-free selection task per Held-out Event.

    Each Held-out SourceSegment carries exactly one Event, so the renderer omits any
    Event-literal hint instead of requiring a unique trigger-head string. Everything in
    the task is source text plus the Event's own candidate labels; no Gold fragment,
    Event meaning, or constituent boundary enters the rendered input.
    """
    tasks: list[ConstituentSelectionTask] = []
    for event in catalog.events:
        tasks.append(
            _render_held_out_selection_task(
                event_id=event.event_id,
                source_text=event.source_text,
                inventory=inventories[event.event_id],
            )
        )
    return tuple(tasks)


def _render_held_out_selection_task(
    *,
    event_id: str,
    source_text: str,
    inventory: ConstituentCandidateInventory,
) -> ConstituentSelectionTask:
    if inventory.event_id != event_id:
        raise ValueError("Held-out selection renderer references a mismatched Event.")
    if hashlib.sha256(source_text.encode()).hexdigest() != inventory.source_text_sha256:
        raise ValueError("Held-out selection renderer source digest does not match the inventory.")
    labels = constituent_selection_labels(inventory)
    lines = [
        "Return a comma-separated subset of the Candidate labels, or NONE.",
        "Passage:",
        source_text,
        "Candidates:",
    ]
    for label, constituent in zip(labels, inventory.constituents, strict=True):
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


def build_held_out_propositions(
    *,
    catalog: HeldOutPropositionGoldCatalog,
    inventories: Mapping[str, ConstituentCandidateInventory],
    answers: Mapping[str, ConstituentSelectionAnswer],
    tokens_by_digest: Mapping[str, tuple[EventEntityLinguisticToken, ...]],
) -> dict[str, DecontextualizedProposition]:
    """Compose one DecontextualizedProposition or typed hold per Held-out Event.

    Derivation reads only the pinned dependency tokens and the frozen selection; it
    never reads Transfer Gold fragments or meanings and never invokes a model.
    """
    event_ids = {event.event_id for event in catalog.events}
    if event_ids != set(inventories) or event_ids != set(answers):
        raise ValueError("Held-out composition requires one selection per Event.")
    propositions: dict[str, DecontextualizedProposition] = {}
    for event in catalog.events:
        tokens = tokens_by_digest[event.source_text_sha256]
        trigger_head_start, trigger_head_end = derive_held_out_trigger_head(
            source_text=event.source_text, tokens=tokens
        )
        entities = derive_held_out_entities(
            source_text=event.source_text,
            source_text_sha256=event.source_text_sha256,
            tokens=tokens,
            inventory=inventories[event.event_id],
        )
        propositions[event.event_id] = build_decontextualized_proposition(
            event_id=event.event_id,
            source_text=event.source_text,
            source_text_sha256=event.source_text_sha256,
            inventory=inventories[event.event_id],
            answer=answers[event.event_id],
            trigger_head_start=trigger_head_start,
            trigger_head_end=trigger_head_end,
            tokens=tokens,
            entities=entities,
        )
    return propositions


def _head_token(tokens: tuple[EventEntityLinguisticToken, ...]) -> EventEntityLinguisticToken:
    roots = [token for token in tokens if token.head_token_id is None]
    if not roots:
        raise ValueError("Held-out entity derivation requires at least one sentence root.")
    # Tokens are source-ordered, so the first root is the earliest sentence's head.
    return roots[0]


def _dependents(
    head: EventEntityLinguisticToken, tokens: tuple[EventEntityLinguisticToken, ...]
) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(token for token in tokens if token.head_token_id == head.token_id)


def _maximal_constituent(
    token: EventEntityLinguisticToken,
    head: EventEntityLinguisticToken,
    inventory: ConstituentCandidateInventory,
) -> AttachmentSourceRange | None:
    candidates = [
        item
        for item in inventory.constituents
        if token.token_id in item.token_ids and head.token_id not in item.token_ids
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


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
