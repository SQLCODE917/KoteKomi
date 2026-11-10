"""Deterministic, model-free source-grounded Constituent selection (R19).

The selector derives each required content role (subject or object) from the
trigger head's direct dependents, reduces each role to its canonical boundary
through one reviewed, Event-independent role-boundary policy, and selects one
eligible Candidate per realized role (one per conjunct for a ``conj``
coordination). It never reads a model answer, never substitutes the frozen
Reference selected set, and never reads a reviewed ``expected_source_range`` or
``canonical_candidate_label``. Selection is by reduction to the canonical
boundary — never by longest span.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.decontextualization_composition import DecontextualizationRoleKind
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ParserConstituent,
)
from kotekomi_application.source_ranges import SourceRange

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[
    str, Field(pattern=r"^(?:(?:TGE|AHE)-[0-9]{3}|sge_[A-Za-z0-9][A-Za-z0-9_-]*)$")
]

_SUBJECT_DEPENDENCY_RELATIONS = frozenset({"nsubj", "nsubj:pass"})
_OBJECT_DEPENDENCY_RELATIONS = frozenset({"obj", "iobj"})
_REQUIRED_CONTENT_RELATIONS = frozenset({"det", "amod", "flat", "nmod:poss"})
_OPTIONAL_CONTENT_RELATIONS = frozenset(
    {"case", "mark", "acl", "advmod", "aux", "cop", "neg", "punct", "nmod"}
)
_COORDINATION_RELATIONS = frozenset({"conj", "cc"})
_COMPLETION_CONTENT_RELATIONS = frozenset(
    {
        "det",
        "amod",
        "compound",
        "compound:prt",
        "flat",
        "nummod",
        "punct",
        "case",
        "fixed",
        "nmod",
        "nmod:poss",
    }
)


class SourceGroundedSelectionStatus(StrEnum):
    """Terminal state of one deterministic source-grounded selection."""

    SELECTED = "selected"
    EMPTY = "empty"
    BOUNDARY_GAP = "boundary_gap"


class SourceGroundedBoundaryGap(StrEnum):
    """Typed reason the canonical-boundary reduction did not select a Candidate."""

    NO_COVERING_CANDIDATE = "no_covering_candidate"
    MULTI_HEAD_AMBIGUITY = "multi_head_ambiguity"
    UNTERMINATED_TIE = "unterminated_tie"
    UNSUPPORTED_RELATION = "unsupported_relation"


class SourceGroundedConjunctSelection(BaseModel):
    """One conjunct's canonical boundary and its selected Candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    canonical_boundary: SourceRange
    selected_label: Annotated[str, Field(pattern=r"^C[1-9][0-9]*$")]


class SourceGroundedRoleSelection(BaseModel):
    """One realized content role reduced to its canonical selection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role: DecontextualizationRoleKind
    argument_head_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")]
    conjuncts: tuple[SourceGroundedConjunctSelection, ...]


class SourceGroundedSelectionResult(BaseModel):
    """One Event's production selection or a typed boundary gap."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    status: SourceGroundedSelectionStatus
    answer: ConstituentSelectionAnswer | None = None
    boundary_gap: SourceGroundedBoundaryGap | None = None
    realized_roles: tuple[SourceGroundedRoleSelection, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self):
        if self.status is SourceGroundedSelectionStatus.SELECTED:
            if self.answer is None or self.boundary_gap is not None or not self.realized_roles:
                raise ValueError("A selected result requires an answer, roles, and no gap.")
        elif self.status is SourceGroundedSelectionStatus.EMPTY:
            if self.answer is None or self.boundary_gap is not None or self.realized_roles:
                raise ValueError("An empty result requires a NONE answer and no roles or gap.")
        elif self.boundary_gap is None or self.answer is not None:
            raise ValueError("A boundary-gap result requires a gap and no answer.")
        return self


class SourceGroundedSelectionError(ValueError):
    """One deterministic selection failed at the canonical-boundary reduction."""

    def __init__(self, gap: SourceGroundedBoundaryGap) -> None:
        super().__init__(f"Source-grounded selection boundary gap: {gap.value}")
        self.gap = gap


def _trigger_head_token(
    head_start: int,
    head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> EventEntityLinguisticToken | None:
    matches = [token for token in tokens if token.start <= head_start and head_end <= token.end]
    if len(matches) == 1:
        return matches[0]
    return None


def _dependents(
    head: EventEntityLinguisticToken,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(
        token
        for token in tokens
        if token.head_token_id == head.token_id and token.sentence_id == head.sentence_id
    )


def _children_by_head(
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    grouped: dict[str, list[EventEntityLinguisticToken]] = {}
    for token in tokens:
        if token.head_token_id is not None:
            grouped.setdefault(token.head_token_id, []).append(token)
    return {token_id: tuple(items) for token_id, items in grouped.items()}


def _is_required_content(token: EventEntityLinguisticToken) -> bool:
    if token.dependency_relation == "compound":
        return token.part_of_speech == "PROPN"
    return token.dependency_relation in _REQUIRED_CONTENT_RELATIONS


def _is_optional_content(token: EventEntityLinguisticToken) -> bool:
    if token.dependency_relation == "compound":
        return token.part_of_speech != "PROPN"
    return token.dependency_relation in _OPTIONAL_CONTENT_RELATIONS


def _is_supported_direct_dependent(token: EventEntityLinguisticToken) -> bool:
    """Return whether one argument-head dependent uses a supported relation."""
    if token.dependency_relation in _COORDINATION_RELATIONS:
        return True
    return _is_required_content(token) or _is_optional_content(token)


def _conjuncts(
    head: EventEntityLinguisticToken,
    children: dict[str, tuple[EventEntityLinguisticToken, ...]],
) -> tuple[EventEntityLinguisticToken, ...]:
    """Return every conjunct of a coordination, the first conjunct first."""
    conjunct_tokens: list[EventEntityLinguisticToken] = [head]
    for dependent in children.get(head.token_id, ()):
        if dependent.dependency_relation == "conj":
            conjunct_tokens.append(dependent)
    return tuple(conjunct_tokens)


def _canonical_boundary_tokens(
    head: EventEntityLinguisticToken,
    children: dict[str, tuple[EventEntityLinguisticToken, ...]],
) -> frozenset[str]:
    """Reduce one argument head to its required-content canonical-boundary tokens."""
    included: set[str] = {head.token_id}
    pending: list[EventEntityLinguisticToken] = [head]
    while pending:
        parent = pending.pop()
        for dependent in children.get(parent.token_id, ()):
            if not _is_required_content(dependent) or dependent.token_id in included:
                continue
            included.add(dependent.token_id)
            pending.append(dependent)
            if dependent.dependency_relation == "nmod:poss":
                for child in children.get(dependent.token_id, ()):
                    if child.dependency_relation == "case":
                        included.add(child.token_id)
    return frozenset(included)


def _source_range(
    source_text: str,
    token_ids: frozenset[str],
    tokens_by_id: dict[str, EventEntityLinguisticToken],
) -> SourceRange:
    ordered = sorted(
        (tokens_by_id[token_id] for token_id in token_ids), key=lambda item: (item.start, item.end)
    )
    for token in ordered:
        if source_text[token.start : token.end] != token.text:
            raise ValueError("Source-grounded boundary token offsets drifted from source text.")
    return SourceRange(
        start=ordered[0].start,
        end=ordered[-1].end,
        text=source_text[ordered[0].start : ordered[-1].end],
    )


def _span_equals(constituent: ParserConstituent, boundary: SourceRange) -> bool:
    return (
        constituent.constituent_range.start == boundary.start
        and constituent.constituent_range.end == boundary.end
    )


def _span_covers(constituent: ParserConstituent, boundary: SourceRange) -> bool:
    return (
        constituent.constituent_range.start <= boundary.start
        and boundary.end <= constituent.constituent_range.end
    )


def _label_for(inventory: ConstituentCandidateInventory, constituent: ParserConstituent) -> str:
    for ordinal, item in enumerate(inventory.constituents, 1):
        if item.constituent_id == constituent.constituent_id:
            return f"C{ordinal}"
    raise ValueError("Selected constituent is absent from the Candidate inventory.")


def _completion_is_permitted(
    *,
    candidate: ParserConstituent,
    boundary: SourceRange,
    tokens_by_id: dict[str, EventEntityLinguisticToken],
) -> bool:
    """Return whether one covering candidate only completes the role's own noun phrase.

    The candidate may add noun-phrase content that is inside it: determiners,
    modifiers, compounds, punctuation, and at most one prepositional complement
    rooted directly in the canonical boundary tokens. Any clause, appositive,
    coordination, or adverbial material leaves the candidate unsuitable.
    """
    boundary_ids = _boundary_token_ids(boundary, tokens_by_id)
    candidate_ids = frozenset(candidate.token_ids)
    extras = candidate_ids - boundary_ids
    if not extras or not boundary_ids <= candidate_ids:
        return False
    selected = [tokens_by_id[token_id] for token_id in candidate_ids]
    start = min(token.start for token in selected)
    end = max(token.end for token in selected)
    # A covering span must not hide a token assigned to a different role.
    if any(
        token.start < end and start < token.end and token.token_id not in candidate_ids
        for token in tokens_by_id.values()
    ):
        return False
    sentence_ids = {tokens_by_id[token_id].sentence_id for token_id in boundary_ids}
    outer_complements: set[str] = set()
    for token_id in extras:
        current_id = token_id
        visited: set[str] = set()
        outer_complement: str | None = None
        while current_id not in boundary_ids:
            if current_id not in extras or current_id in visited:
                return False
            visited.add(current_id)
            token = tokens_by_id[current_id]
            if (
                token.dependency_relation not in _COMPLETION_CONTENT_RELATIONS
                or token.sentence_id not in sentence_ids
                or token.head_token_id is None
            ):
                return False
            if token.dependency_relation == "nmod":
                if not any(
                    child.head_token_id == current_id and child.dependency_relation == "case"
                    for child in selected
                ):
                    return False
                outer_complement = current_id
            current_id = token.head_token_id
        if outer_complement is not None:
            outer_complements.add(outer_complement)
    return len(outer_complements) <= 1


def _boundary_token_ids(
    boundary: SourceRange, tokens_by_id: dict[str, EventEntityLinguisticToken]
) -> frozenset[str]:
    return frozenset(
        token_id
        for token_id, token in tokens_by_id.items()
        if boundary.start <= token.start and token.end <= boundary.end
    )


def _select_conjunct(
    *,
    head: EventEntityLinguisticToken,
    trigger_head: EventEntityLinguisticToken,
    inventory: ConstituentCandidateInventory,
    source_text: str,
    tokens_by_id: dict[str, EventEntityLinguisticToken],
    children: dict[str, tuple[EventEntityLinguisticToken, ...]],
) -> SourceGroundedConjunctSelection:
    # REQ-BND-04: an unlisted relation on the argument head is a boundary gap.
    for dependent in children.get(head.token_id, ()):
        if not _is_supported_direct_dependent(dependent):
            raise SourceGroundedSelectionError(SourceGroundedBoundaryGap.UNSUPPORTED_RELATION)

    boundary = _source_range(source_text, _canonical_boundary_tokens(head, children), tokens_by_id)
    candidates = [
        item
        for item in inventory.constituents
        if head.token_id in item.token_ids and trigger_head.token_id not in item.token_ids
    ]
    equal = [item for item in candidates if _span_equals(item, boundary)]
    if len(equal) == 1:
        return SourceGroundedConjunctSelection(
            canonical_boundary=boundary, selected_label=_label_for(inventory, equal[0])
        )
    covering = [item for item in candidates if _span_covers(item, boundary)]
    if not covering:
        raise SourceGroundedSelectionError(SourceGroundedBoundaryGap.NO_COVERING_CANDIDATE)
    if len(covering) == 1 and _completion_is_permitted(
        candidate=covering[0], boundary=boundary, tokens_by_id=tokens_by_id
    ):
        return SourceGroundedConjunctSelection(
            canonical_boundary=covering[0].constituent_range,
            selected_label=_label_for(inventory, covering[0]),
        )
    raise SourceGroundedSelectionError(SourceGroundedBoundaryGap.UNTERMINATED_TIE)


def _realize_role(
    *,
    role: DecontextualizationRoleKind,
    role_head: EventEntityLinguisticToken,
    trigger_head: EventEntityLinguisticToken,
    inventory: ConstituentCandidateInventory,
    source_text: str,
    tokens_by_id: dict[str, EventEntityLinguisticToken],
    children: dict[str, tuple[EventEntityLinguisticToken, ...]],
) -> SourceGroundedRoleSelection:
    """Reduce one realized role to its per-conjunct canonical selections."""
    selections = tuple(
        _select_conjunct(
            head=conjunct,
            trigger_head=trigger_head,
            inventory=inventory,
            source_text=source_text,
            tokens_by_id=tokens_by_id,
            children=children,
        )
        for conjunct in _conjuncts(role_head, children)
    )
    return SourceGroundedRoleSelection(
        role=role,
        argument_head_token_id=role_head.token_id,
        conjuncts=selections,
    )


def select_source_grounded_constituents(
    *,
    event_id: str,
    source_text: str,
    inventory: ConstituentCandidateInventory,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> SourceGroundedSelectionResult:
    """Select one Candidate per realized role from the trigger-head dependents."""
    if inventory.event_id != event_id:
        raise ValueError("Source-grounded selection received an inventory for another Event.")
    if hashlib.sha256(source_text.encode()).hexdigest() != inventory.source_text_sha256:
        raise ValueError("Source-grounded selection source digest drifted from its text.")

    head = _trigger_head_token(trigger_head_start, trigger_head_end, tokens)
    if head is None:
        return SourceGroundedSelectionResult(
            event_id=event_id,
            status=SourceGroundedSelectionStatus.BOUNDARY_GAP,
            boundary_gap=SourceGroundedBoundaryGap.MULTI_HEAD_AMBIGUITY,
        )

    dependents = _dependents(head, tokens)
    children = _children_by_head(tokens)
    tokens_by_id = {token.token_id: token for token in tokens}

    subject_heads = tuple(
        token for token in dependents if token.dependency_relation in _SUBJECT_DEPENDENCY_RELATIONS
    )
    object_heads = tuple(
        token for token in dependents if token.dependency_relation in _OBJECT_DEPENDENCY_RELATIONS
    )

    if not subject_heads and not object_heads:
        return SourceGroundedSelectionResult(
            event_id=event_id,
            status=SourceGroundedSelectionStatus.EMPTY,
            answer=ConstituentSelectionAnswer(
                event_id=event_id,
                status=ConstituentSelectionStatus.NONE,
                selected_label_indexes=(),
            ),
        )

    realized_roles: list[SourceGroundedRoleSelection] = []
    answer_targets: set[str] = set()

    if len(subject_heads) > 1 or len(object_heads) > 1:
        return SourceGroundedSelectionResult(
            event_id=event_id,
            status=SourceGroundedSelectionStatus.BOUNDARY_GAP,
            boundary_gap=SourceGroundedBoundaryGap.MULTI_HEAD_AMBIGUITY,
        )

    try:
        if subject_heads:
            realized_roles.append(
                _realize_role(
                    role=DecontextualizationRoleKind.SUBJECT,
                    role_head=subject_heads[0],
                    trigger_head=head,
                    inventory=inventory,
                    source_text=source_text,
                    tokens_by_id=tokens_by_id,
                    children=children,
                )
            )
        if object_heads:
            realized_roles.append(
                _realize_role(
                    role=DecontextualizationRoleKind.OBJECT,
                    role_head=object_heads[0],
                    trigger_head=head,
                    inventory=inventory,
                    source_text=source_text,
                    tokens_by_id=tokens_by_id,
                    children=children,
                )
            )
    except SourceGroundedSelectionError as error:
        return SourceGroundedSelectionResult(
            event_id=event_id,
            status=SourceGroundedSelectionStatus.BOUNDARY_GAP,
            boundary_gap=error.gap,
        )

    for role_selection in realized_roles:
        for conjunct in role_selection.conjuncts:
            answer_targets.add(conjunct.selected_label)

    indexes = tuple(
        ordinal
        for ordinal, item in enumerate(inventory.constituents, 1)
        if _label_for(inventory, item) in answer_targets
    )
    return SourceGroundedSelectionResult(
        event_id=event_id,
        status=SourceGroundedSelectionStatus.SELECTED,
        answer=ConstituentSelectionAnswer(
            event_id=event_id,
            status=ConstituentSelectionStatus.SELECTED,
            selected_label_indexes=indexes,
        ),
        realized_roles=tuple(realized_roles),
    )
