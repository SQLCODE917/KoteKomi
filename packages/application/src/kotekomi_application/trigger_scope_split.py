"""Deterministic model-free reporting-carrier and governed-complement split.

The splitter wires one governed Event trigger to its governing reporting clause and its
governed content clause without invoking a model. It recognizes two narrow patterns:

- Attribution adjunct (``advcl`` / ``obl`` / ``nmod`` / ``parataxis`` / ``discourse`` /
  ``advmod``): a reporting predicate modifies the Event clause and names the reporter, so
  the reporting carrier is the reporting predicate's subtree and the governed complement
  is the remainder of the clause. Example: ``According to Semafor, Trump officials
  chastised ...``.
- Reporting verb with a clausal complement (``ccomp`` / ``xcomp``): the Event head sits
  inside the complement of a reporting verb, so the reporting carrier is the reporting
  verb's non-complement subtree and the governed complement is the clausal-complement
  subtree. Example: ``Sacks stated that Anthropic ran ...``.

Any other structure produces a typed held result, never a merged proposition.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, NamedTuple, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.event_entity_connections import (
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
)
from kotekomi_application.hybrid_event_semantics import SourceGroundedEventDraft
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft

_SHA256 = r"^[a-f0-9]{64}$"

_REPORTING_PREDICATE_LEMMAS = frozenset(
    {
        "accord",
        "according",
        "say",
        "state",
        "tell",
        "report",
        "write",
        "announce",
        "claim",
        "allege",
        "argue",
        "note",
        "add",
        "explain",
        "describe",
        "warn",
        "suggest",
        "indicate",
        "reveal",
        "declare",
        "assert",
        "admit",
        "deny",
    }
)
_COMPLEMENT_RELATIONS = frozenset({"ccomp", "xcomp"})
_ADJUNCT_RELATIONS = frozenset({"advcl", "obl", "nmod", "parataxis", "discourse", "advmod"})
_CARRIER_FUNCTION_RELATIONS = frozenset({"punct"})
_COMPLEMENT_FUNCTION_RELATIONS = frozenset({"mark", "punct"})


class TriggerScopeStatus(StrEnum):
    """Terminal state of one deterministic trigger-scope split."""

    COMPLETE = "complete"
    HELD = "held"


class TriggerScopeHoldReason(StrEnum):
    """Typed reason that one trigger scope could not be split deterministically."""

    TRIGGER_HEAD_UNRESOLVED = "trigger_head_unresolved"
    REPORTING_PREDICATE_MISSING = "reporting_predicate_missing"
    REPORTING_PREDICATE_AMBIGUOUS = "reporting_predicate_ambiguous"
    GOVERNED_COMPLEMENT_MISSING = "governed_complement_missing"


class TriggerScopeSourceRange(BaseModel):
    """One exact authoritative half-open source range."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Trigger-scope source range does not match its text length.")
        return self


class TriggerScopeSplit(BaseModel):
    """One complete or held deterministic trigger-scope split."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^tss_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    trigger_id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    status: TriggerScopeStatus
    reporting_carrier: TriggerScopeSourceRange | None = None
    governed_complement: TriggerScopeSourceRange | None = None
    hold_reason: TriggerScopeHoldReason | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is TriggerScopeStatus.COMPLETE:
            if self.reporting_carrier is None or self.governed_complement is None:
                raise ValueError("A complete trigger-scope split requires both parts.")
            if self.hold_reason is not None:
                raise ValueError("A complete trigger-scope split cannot carry a hold reason.")
            if not (
                self.reporting_carrier.end <= self.governed_complement.start
                or self.governed_complement.end <= self.reporting_carrier.start
            ):
                raise ValueError("Trigger-scope parts must not overlap.")
        else:
            if self.reporting_carrier is not None or self.governed_complement is not None:
                raise ValueError("A held trigger-scope split cannot carry a part.")
            if self.hold_reason is None:
                raise ValueError("A held trigger-scope split requires a hold reason.")
        return self


def split_trigger_scope(
    *,
    source_text: str,
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> TriggerScopeSplit:
    """Split one governed Event into its reporting carrier and governed complement."""
    _validate_inputs(source_text, trigger, event, linguistic_evidence)

    by_id = {token.token_id: token for token in linguistic_evidence.tokens}
    children: dict[str, list[EventEntityLinguisticToken]] = {}
    for token in linguistic_evidence.tokens:
        if token.head_token_id is not None:
            children.setdefault(token.head_token_id, []).append(token)

    head_token = _trigger_head_token(trigger, by_id)
    if head_token is None:
        return _held(
            TriggerScopeHoldReason.TRIGGER_HEAD_UNRESOLVED, event, trigger, linguistic_evidence
        )

    sentence_tokens = [
        token for token in linguistic_evidence.tokens if token.sentence_id == head_token.sentence_id
    ]
    candidates = _reporting_predicate_candidates(head_token, sentence_tokens, by_id)
    distinct = {candidate.token.token_id: candidate for candidate in candidates}
    if not distinct:
        return _held(
            TriggerScopeHoldReason.REPORTING_PREDICATE_MISSING, event, trigger, linguistic_evidence
        )
    if len(distinct) > 1:
        return _held(
            TriggerScopeHoldReason.REPORTING_PREDICATE_AMBIGUOUS,
            event,
            trigger,
            linguistic_evidence,
        )
    candidate = next(iter(distinct.values()))

    if candidate.kind == "complement":
        complement_child = candidate.complement_child
        assert complement_child is not None
        complement_ids = _subtree_ids(complement_child, children)
        carrier_ids = _subtree_ids(candidate.token, children) - complement_ids
    else:
        carrier_ids = _subtree_ids(candidate.token, children)
        complement_ids = frozenset(token.token_id for token in sentence_tokens) - carrier_ids

    carrier_tokens = [
        token
        for token in by_id.values()
        if token.token_id in carrier_ids
        and token.dependency_relation not in _CARRIER_FUNCTION_RELATIONS
    ]
    complement_tokens = [
        token
        for token in by_id.values()
        if token.token_id in complement_ids
        and token.dependency_relation not in _COMPLEMENT_FUNCTION_RELATIONS
    ]

    carrier_range = _source_range(source_text, carrier_tokens, sentence_tokens)
    complement_range = _source_range(source_text, complement_tokens, sentence_tokens)
    if carrier_range is None or complement_range is None:
        return _held(
            TriggerScopeHoldReason.GOVERNED_COMPLEMENT_MISSING, event, trigger, linguistic_evidence
        )

    return TriggerScopeSplit(
        id=_split_id(event.id, trigger.id, "complete", carrier_range, complement_range, None),
        source_grounded_event_id=event.id,
        trigger_id=trigger.id,
        source_segment_id=event.source_segment_id,
        source_text_sha256=event.source_text_sha256,
        status=TriggerScopeStatus.COMPLETE,
        reporting_carrier=carrier_range,
        governed_complement=complement_range,
    )


class _ReportingPredicate(NamedTuple):
    kind: str
    token: EventEntityLinguisticToken
    complement_child: EventEntityLinguisticToken | None


def _validate_inputs(
    source_text: str,
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> None:
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if source_digest != event.source_text_sha256:
        raise ValueError("Trigger-scope source digest drifted from the source-grounded Event.")
    if source_digest != trigger.source_text_sha256:
        raise ValueError("Trigger-scope source digest drifted from the Event trigger.")
    if source_digest != linguistic_evidence.source_text_sha256:
        raise ValueError("Trigger-scope source digest drifted from the linguistic evidence.")
    if event.trigger_id != trigger.id:
        raise ValueError("Trigger-scope Event references a different trigger.")
    if len(
        {event.source_segment_id, trigger.source_segment_id, linguistic_evidence.source_segment_id}
    ) != 1:
        raise ValueError("Trigger-scope inputs reference different source segments.")


def _held(
    reason: TriggerScopeHoldReason,
    event: SourceGroundedEventDraft,
    trigger: EventTriggerDraft,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> TriggerScopeSplit:
    return TriggerScopeSplit(
        id=_split_id(event.id, trigger.id, "held", None, None, reason),
        source_grounded_event_id=event.id,
        trigger_id=trigger.id,
        source_segment_id=event.source_segment_id,
        source_text_sha256=event.source_text_sha256,
        status=TriggerScopeStatus.HELD,
        hold_reason=reason,
    )


def _split_id(
    event_id: str,
    trigger_id: str,
    status: str,
    carrier: TriggerScopeSourceRange | None,
    complement: TriggerScopeSourceRange | None,
    hold_reason: TriggerScopeHoldReason | None,
) -> str:
    value = {
        "event_id": event_id,
        "trigger_id": trigger_id,
        "status": status,
        "reporting_carrier": [carrier.start, carrier.end, carrier.text] if carrier else None,
        "governed_complement": [complement.start, complement.end, complement.text]
        if complement
        else None,
        "hold_reason": hold_reason.value if hold_reason else None,
    }
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "tss_" + hashlib.sha256(payload).hexdigest()[:24]


def _trigger_head_token(
    trigger: EventTriggerDraft,
    by_id: dict[str, EventEntityLinguisticToken],
) -> EventEntityLinguisticToken | None:
    matches = [
        token
        for token in by_id.values()
        if token.start <= trigger.head_start and trigger.head_end <= token.end
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _clause_ancestors(
    head_token: EventEntityLinguisticToken,
    by_id: dict[str, EventEntityLinguisticToken],
) -> tuple[EventEntityLinguisticToken, ...]:
    result: list[EventEntityLinguisticToken] = []
    cursor: EventEntityLinguisticToken = head_token
    seen: set[str] = set()
    while cursor.token_id not in seen:
        seen.add(cursor.token_id)
        result.append(cursor)
        if cursor.head_token_id is None:
            break
        cursor = by_id[cursor.head_token_id]
    return tuple(result)


def _reporting_predicate_candidates(
    head_token: EventEntityLinguisticToken,
    sentence_tokens: list[EventEntityLinguisticToken],
    by_id: dict[str, EventEntityLinguisticToken],
) -> list[_ReportingPredicate]:
    ancestors = _clause_ancestors(head_token, by_id)
    ancestor_ids = {token.token_id for token in ancestors}
    candidates: list[_ReportingPredicate] = []

    cursor: EventEntityLinguisticToken = head_token
    seen: set[str] = set()
    while cursor.token_id not in seen:
        seen.add(cursor.token_id)
        parent_id = cursor.head_token_id
        if parent_id is None:
            break
        parent = by_id[parent_id]
        if (
            parent.lemma.casefold() in _REPORTING_PREDICATE_LEMMAS
            and cursor.dependency_relation in _COMPLEMENT_RELATIONS
        ):
            candidates.append(_ReportingPredicate("complement", parent, cursor))
        cursor = parent

    known = {candidate.token.token_id for candidate in candidates}
    for token in sentence_tokens:
        if token.token_id in known:
            continue
        if token.lemma.casefold() not in _REPORTING_PREDICATE_LEMMAS:
            continue
        if token.head_token_id not in ancestor_ids:
            continue
        if token.dependency_relation not in _ADJUNCT_RELATIONS:
            continue
        candidates.append(_ReportingPredicate("adjunct", token, None))
    return candidates


def _subtree_ids(
    root: EventEntityLinguisticToken,
    children: dict[str, list[EventEntityLinguisticToken]],
) -> frozenset[str]:
    found: list[str] = []
    seen: set[str] = set()
    pending = [root.token_id]
    while pending:
        token_id = pending.pop()
        if token_id in seen:
            continue
        seen.add(token_id)
        found.append(token_id)
        pending.extend(item.token_id for item in children.get(token_id, ()))
    return frozenset(found)


def _source_range(
    source_text: str,
    tokens: list[EventEntityLinguisticToken],
    sentence_tokens: list[EventEntityLinguisticToken],
) -> TriggerScopeSourceRange | None:
    if not tokens:
        return None
    selected_ids = {token.token_id for token in tokens}
    ordered = sorted(tokens, key=lambda token: (token.start, token.end))
    for token in ordered:
        if source_text[token.start : token.end] != token.text:
            raise ValueError("Trigger-scope token offsets drifted from authoritative source text.")
    start = ordered[0].start
    end = ordered[-1].end
    for token in sentence_tokens:
        if token.token_id in selected_ids:
            continue
        if start < token.start and token.end < end:
            return None
    return TriggerScopeSourceRange(start=start, end=end, text=source_text[start:end])