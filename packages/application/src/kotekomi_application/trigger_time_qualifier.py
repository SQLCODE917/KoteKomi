"""Deterministic derivation of one Event's trigger time qualifier.

The composer refuses an Event whose trigger head carries a plain oblique
dependent. This module separates the one case the Assertion can represent: a
simple source-exact time expression. Everything else stays a typed hold.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.source_ranges import SourceRange

_EventId = Annotated[
    str, Field(pattern=r"^(?:(?:TGE|AHE)-[0-9]{3}|sge_[A-Za-z0-9][A-Za-z0-9_-]*)$")
]

_TRIGGER_ADJUNCT_RELATION = "obl"
_TEMPORAL_PREPOSITIONS = frozenset(
    {
        "in",
        "on",
        "at",
        "since",
        "during",
        "until",
        "after",
        "before",
        "by",
        "from",
        "prior",
        "as",
        "through",
        "within",
    }
)
_MONTH_LEMMAS = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
)
_TEMPORAL_NOUN_LEMMAS = frozenset(
    {
        "year",
        "month",
        "week",
        "day",
        "decade",
        "century",
        "morning",
        "afternoon",
        "evening",
        "night",
        "today",
        "yesterday",
        "tomorrow",
        "tonight",
        "spring",
        "summer",
        "autumn",
        "winter",
    }
)
_PERMITTED_ADJUNCT_RELATIONS = frozenset(
    {
        "case",
        "det",
        "amod",
        "nummod",
        "compound",
        "flat",
        "fixed",
        "punct",
        "nmod:tmod",
        "advmod",
    }
)
_YEAR = re.compile(r"^(1[0-9]{3}|2[0-9]{3})$")


class TriggerTimeUnsupported(ValueError):
    """The trigger's oblique content is not a time expression this Assertion can carry."""


class TriggerTimeQualifier(BaseModel):
    """One exact source time expression attached to a trigger head."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    exact_range: SourceRange


def _trigger_head_token(
    start: int, end: int, tokens: tuple[EventEntityLinguisticToken, ...]
) -> EventEntityLinguisticToken | None:
    matches = [token for token in tokens if token.start <= start and end <= token.end]
    if len(matches) == 1:
        return matches[0]
    return None


def _children_by_head(
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    grouped: dict[str, list[EventEntityLinguisticToken]] = {}
    for token in tokens:
        if token.head_token_id is not None:
            grouped.setdefault(token.head_token_id, []).append(token)
    return {key: tuple(value) for key, value in grouped.items()}


def _subtree(
    head: EventEntityLinguisticToken,
    children: dict[str, tuple[EventEntityLinguisticToken, ...]],
) -> tuple[EventEntityLinguisticToken, ...]:
    collected = [head]
    pending = [head]
    while pending:
        current = pending.pop()
        for child in children.get(current.token_id, ()):
            collected.append(child)
            pending.append(child)
    return tuple(sorted(collected, key=lambda token: (token.start, token.end)))


def _has_temporal_evidence(tokens: tuple[EventEntityLinguisticToken, ...]) -> bool:
    for token in tokens:
        lemma = token.lemma.casefold()
        if token.part_of_speech == "NUM" and _YEAR.match(token.text):
            return True
        if lemma in _MONTH_LEMMAS or lemma in _TEMPORAL_NOUN_LEMMAS:
            return True
    return False

    @model_validator(mode="after")
    def validate_contract(self) -> TriggerTimeQualifier:
        if not self.exact_range.text.strip():
            raise ValueError("A trigger time qualifier requires text.")
        return self


def derive_trigger_time_qualifier(
    *,
    event_id: str,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    trigger_head_start: int,
    trigger_head_end: int,
) -> TriggerTimeQualifier | None:
    """Return one exact time expression, None without an oblique, or raise."""
    head = _trigger_head_token(trigger_head_start, trigger_head_end, tokens)
    if head is None:
        raise TriggerTimeUnsupported("The trigger head is not one token.")
    children = _children_by_head(tokens)
    adjuncts = [
        child
        for child in children.get(head.token_id, ())
        if child.dependency_relation == _TRIGGER_ADJUNCT_RELATION
        and child.sentence_id == head.sentence_id
    ]
    if not adjuncts:
        return None
    if len(adjuncts) > 1:
        raise TriggerTimeUnsupported("The trigger carries more than one oblique dependent.")
    adjunct = adjuncts[0]
    subtree = _subtree(adjunct, children)
    relations = {token.dependency_relation for token in subtree if token is not adjunct}
    if not relations <= _PERMITTED_ADJUNCT_RELATIONS:
        raise TriggerTimeUnsupported("The oblique carries content this Assertion cannot represent.")
    for token in subtree:
        if token.dependency_relation == "nmod":
            raise TriggerTimeUnsupported("The oblique carries a second prepositional complement.")
    identifiers = {token.token_id for token in subtree}
    span_start = subtree[0].start
    span_end = subtree[-1].end
    for token in tokens:
        if span_start <= token.start and token.end <= span_end:
            if token.token_id not in identifiers:
                raise TriggerTimeUnsupported("The oblique subtree is not contiguous.")
    cases = [token for token in subtree if token.dependency_relation == "case"]
    if len(cases) != 1:
        raise TriggerTimeUnsupported("The oblique requires exactly one case marker.")
    preposition = cases[0].lemma.casefold()
    if preposition not in _TEMPORAL_PREPOSITIONS:
        raise TriggerTimeUnsupported("The oblique does not open with a temporal preposition.")
    if preposition != "prior" and not _has_temporal_evidence(subtree):
        raise TriggerTimeUnsupported("The oblique carries no temporal evidence.")
    kept = [token for token in subtree if token.dependency_relation != "punct"]
    if not kept:
        raise TriggerTimeUnsupported("The oblique is only punctuation.")
    start = kept[0].start
    end = kept[-1].end
    return TriggerTimeQualifier(
        event_id=event_id,
        exact_range=SourceRange(start=start, end=end, text=source_text[start:end]),
    )
