"""Deterministic Stanza predicate-argument observations for Event candidates."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.event_entity_connections import (
    EventEntityConnectionCandidate,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventEntitySourceSpan,
)
from kotekomi_application.hybrid_event_semantics import SourceGroundedEventDraft
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft

_SHA256 = r"^[a-f0-9]{64}$"
_ID = r"^[a-z][a-z0-9_]*_[A-Za-z0-9][A-Za-z0-9_-]*$"


class PredicateArgumentPathDirection(StrEnum):
    """The direction traveled across one dependency edge."""

    TOWARD_HEAD = "toward_head"
    TOWARD_DEPENDENT = "toward_dependent"


class PredicateArgumentHypothesis(StrEnum):
    """One deterministic interpretation of a dependency path."""

    DIRECT_ARGUMENT = "direct_argument"
    COORDINATED_ARGUMENT = "coordinated_argument"
    RELATIVE_CLAUSE_ARGUMENT = "relative_clause_argument"
    INHERITED_ARGUMENT = "inherited_argument"
    QUALIFIED_ARGUMENT = "qualified_argument"
    SEMANTIC_REMAINDER = "semantic_remainder"
    DIFFERENT_SENTENCE = "different_sentence"
    DIAGNOSTIC_GAP = "diagnostic_gap"


class PredicateArgumentGapCode(StrEnum):
    """The first deterministic boundary that prevented one observation."""

    PREDICATE_ANCHOR_MISSING = "predicate_anchor_missing"
    PREDICATE_ANCHOR_AMBIGUOUS = "predicate_anchor_ambiguous"
    ENTITY_ANCHOR_MISSING = "entity_anchor_missing"
    ENTITY_ANCHOR_AMBIGUOUS = "entity_anchor_ambiguous"
    INVALID_DEPENDENCY_TREE = "invalid_dependency_tree"
    DISCONNECTED_DEPENDENCY_TREE = "disconnected_dependency_tree"


class PredicateArgumentToken(BaseModel):
    """One source-exact Stanza token preserved in a diagnostic path."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")]
    sentence_id: Annotated[str, Field(pattern=r"^s[1-9][0-9]*$")]
    text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    lemma: Annotated[str, Field(min_length=1)]
    part_of_speech: Annotated[str, Field(min_length=1)]
    dependency_relation: Annotated[str, Field(min_length=1)]
    head_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")] | None = None

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Predicate-argument token range does not match its text.")
        return self


class PredicateArgumentPathStep(BaseModel):
    """One directed dependency edge in source order from predicate to entity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    from_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")]
    to_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")]
    direction: PredicateArgumentPathDirection
    dependency_relation: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_edge(self) -> Self:
        if self.from_token_id == self.to_token_id:
            raise ValueError("Predicate-argument path step must connect distinct tokens.")
        return self


class PredicateArgumentObservation(BaseModel):
    """One source-exact structural observation for one Event-entity candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["predicate_argument_observation_v1"] = (
        "predicate_argument_observation_v1"
    )
    id: Annotated[str, Field(pattern=r"^pao_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    event_trigger_id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    linguistic_trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]
    linguistic_resource_identity: Annotated[str, Field(pattern=_SHA256)]
    event_expression_start: Annotated[int, Field(ge=0)]
    event_expression_end: Annotated[int, Field(gt=0)]
    event_expression_text: Annotated[str, Field(min_length=1)]
    event_head_start: Annotated[int, Field(ge=0)]
    event_head_end: Annotated[int, Field(gt=0)]
    event_head_text: Annotated[str, Field(min_length=1)]
    entity_span_id: Annotated[str, Field(pattern=r"^ees_[a-f0-9]{24}$")]
    entity_start: Annotated[int, Field(ge=0)]
    entity_end: Annotated[int, Field(gt=0)]
    entity_text: Annotated[str, Field(min_length=1)]
    predicate_anchor: PredicateArgumentToken | None
    entity_anchor: PredicateArgumentToken | None
    path_tokens: tuple[PredicateArgumentToken, ...]
    path_steps: tuple[PredicateArgumentPathStep, ...]
    hypothesis: PredicateArgumentHypothesis
    gap_code: PredicateArgumentGapCode | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.event_expression_end - self.event_expression_start != len(
            self.event_expression_text
        ):
            raise ValueError("Predicate-argument Event expression range does not match its text.")
        if self.event_head_end - self.event_head_start != len(self.event_head_text):
            raise ValueError("Predicate-argument Event head range does not match its text.")
        if not (
            self.event_expression_start
            <= self.event_head_start
            < self.event_head_end
            <= self.event_expression_end
        ):
            raise ValueError("Predicate-argument Event head leaves its expression.")
        if self.entity_end - self.entity_start != len(self.entity_text):
            raise ValueError("Predicate-argument entity range does not match its text.")
        is_gap = self.hypothesis is PredicateArgumentHypothesis.DIAGNOSTIC_GAP
        if is_gap != (self.gap_code is not None):
            raise ValueError("Predicate-argument Diagnostic Gap requires one gap code.")
        if self.hypothesis is PredicateArgumentHypothesis.DIFFERENT_SENTENCE:
            if self.predicate_anchor is None or self.entity_anchor is None:
                raise ValueError("Different-sentence evidence requires both anchors.")
            if self.predicate_anchor.sentence_id == self.entity_anchor.sentence_id:
                raise ValueError("Different-sentence evidence requires distinct sentences.")
            if self.path_tokens or self.path_steps:
                raise ValueError("Different-sentence evidence has no dependency path.")
        elif not is_gap:
            if self.predicate_anchor is None or self.entity_anchor is None:
                raise ValueError("Predicate-argument evidence requires both anchors.")
            if self.predicate_anchor.sentence_id != self.entity_anchor.sentence_id:
                raise ValueError("A dependency path cannot cross linguistic sentences.")
            if not self.path_tokens:
                raise ValueError("Predicate-argument evidence requires path tokens.")
            if self.path_tokens[0] != self.predicate_anchor:
                raise ValueError("Predicate-argument path must begin at its predicate anchor.")
            if self.path_tokens[-1] != self.entity_anchor:
                raise ValueError("Predicate-argument path must end at its entity anchor.")
            if len(self.path_steps) != len(self.path_tokens) - 1:
                raise ValueError("Predicate-argument path step count does not match its tokens.")
            for left, right, step in zip(
                self.path_tokens,
                self.path_tokens[1:],
                self.path_steps,
                strict=False,
            ):
                if step.from_token_id != left.token_id or step.to_token_id != right.token_id:
                    raise ValueError("Predicate-argument path step does not match its tokens.")
        token_ids = tuple(item.token_id for item in self.path_tokens)
        if len(set(token_ids)) != len(token_ids):
            raise ValueError("Predicate-argument path cannot repeat a token.")
        expected_id = _observation_id(
            source_grounded_event_id=self.source_grounded_event_id,
            event_trigger_id=self.event_trigger_id,
            candidate_id=self.candidate_id,
            linguistic_trace_id=self.linguistic_trace_id,
            linguistic_resource_identity=self.linguistic_resource_identity,
            predicate_anchor=self.predicate_anchor,
            entity_anchor=self.entity_anchor,
            path_steps=self.path_steps,
            hypothesis=self.hypothesis,
            gap_code=self.gap_code,
        )
        if self.id != expected_id:
            raise ValueError("Predicate-argument observation ID does not match its evidence.")
        return self


def build_predicate_argument_observation(
    *,
    source_text: str,
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    candidate: EventEntityConnectionCandidate,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> PredicateArgumentObservation:
    """Build one deterministic observation without deciding Event involvement."""
    _validate_inputs(
        source_text=source_text,
        trigger=trigger,
        event=event,
        candidate=candidate,
        linguistic_evidence=linguistic_evidence,
    )
    token_by_id = {item.token_id: item for item in linguistic_evidence.tokens}
    predicate_matches = tuple(
        item
        for item in linguistic_evidence.tokens
        if (item.start, item.end) == (trigger.head_start, trigger.head_end)
    )
    predicate_anchor = _single_token(predicate_matches)
    primary_span = next(
        item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
    )
    entity_tokens = tuple(
        item
        for item in linguistic_evidence.tokens
        if primary_span.start <= item.start and item.end <= primary_span.end
    )
    entity_heads = _phrase_heads(entity_tokens)
    entity_anchor = _single_token(entity_heads)
    gap_code = _anchor_gap_code(predicate_matches, entity_tokens, entity_heads)
    if gap_code is not None:
        return _observation(
            trigger=trigger,
            event=event,
            candidate=candidate,
            primary_span=primary_span,
            linguistic_evidence=linguistic_evidence,
            predicate_anchor=predicate_anchor,
            entity_anchor=entity_anchor,
            path_tokens=(),
            path_steps=(),
            hypothesis=PredicateArgumentHypothesis.DIAGNOSTIC_GAP,
            gap_code=gap_code,
        )
    assert predicate_anchor is not None
    assert entity_anchor is not None
    if predicate_anchor.sentence_id != entity_anchor.sentence_id:
        return _observation(
            trigger=trigger,
            event=event,
            candidate=candidate,
            primary_span=primary_span,
            linguistic_evidence=linguistic_evidence,
            predicate_anchor=predicate_anchor,
            entity_anchor=entity_anchor,
            path_tokens=(),
            path_steps=(),
            hypothesis=PredicateArgumentHypothesis.DIFFERENT_SENTENCE,
            gap_code=None,
        )
    path_ids, path_gap = _dependency_path_ids(
        predicate_anchor.token_id,
        entity_anchor.token_id,
        token_by_id,
    )
    if path_gap is not None:
        return _observation(
            trigger=trigger,
            event=event,
            candidate=candidate,
            primary_span=primary_span,
            linguistic_evidence=linguistic_evidence,
            predicate_anchor=predicate_anchor,
            entity_anchor=entity_anchor,
            path_tokens=(),
            path_steps=(),
            hypothesis=PredicateArgumentHypothesis.DIAGNOSTIC_GAP,
            gap_code=path_gap,
        )
    path_tokens = tuple(_token(token_by_id[item]) for item in path_ids)
    path_steps = _path_steps(path_ids, token_by_id)
    hypothesis = classify_predicate_argument_path(path_steps)
    return _observation(
        trigger=trigger,
        event=event,
        candidate=candidate,
        primary_span=primary_span,
        linguistic_evidence=linguistic_evidence,
        predicate_anchor=predicate_anchor,
        entity_anchor=entity_anchor,
        path_tokens=path_tokens,
        path_steps=path_steps,
        hypothesis=hypothesis,
        gap_code=None,
    )


def predicate_argument_is_structurally_supported(
    hypothesis: PredicateArgumentHypothesis,
) -> bool:
    """Return whether one diagnostic class proposes positive structural evidence."""
    return hypothesis in {
        PredicateArgumentHypothesis.DIRECT_ARGUMENT,
        PredicateArgumentHypothesis.COORDINATED_ARGUMENT,
        PredicateArgumentHypothesis.RELATIVE_CLAUSE_ARGUMENT,
        PredicateArgumentHypothesis.INHERITED_ARGUMENT,
        PredicateArgumentHypothesis.QUALIFIED_ARGUMENT,
    }


def _validate_inputs(
    *,
    source_text: str,
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    candidate: EventEntityConnectionCandidate,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> None:
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if source_digest != event.source_text_sha256:
        raise ValueError("Predicate-argument source digest does not match its Event.")
    if (
        trigger.id != event.trigger_id
        or trigger.source_segment_id != event.source_segment_id
        or trigger.source_text_sha256 != source_digest
        or trigger.text != event.expression_text
        or trigger.head_text != event.head_text
    ):
        raise ValueError("Predicate-argument trigger does not match its source-grounded Event.")
    if (
        candidate.source_grounded_event_id != event.id
        or candidate.event_mention_id != event.mention.id
        or candidate.source_segment_id != event.source_segment_id
        or candidate.source_text_sha256 != source_digest
        or candidate.event_expression_text != trigger.text
    ):
        raise ValueError("Predicate-argument candidate does not match its Event.")
    if (
        linguistic_evidence.source_segment_id != event.source_segment_id
        or linguistic_evidence.source_text_sha256 != source_digest
    ):
        raise ValueError("Predicate-argument linguistic evidence does not match its Event.")
    exact_ranges = (
        (trigger.start, trigger.end, trigger.text),
        (trigger.head_start, trigger.head_end, trigger.head_text),
        *tuple((item.start, item.end, item.text) for item in candidate.source_spans),
        *tuple((item.start, item.end, item.text) for item in linguistic_evidence.tokens),
    )
    if any(
        end > len(source_text) or source_text[start:end] != text
        for start, end, text in exact_ranges
    ):
        raise ValueError("Predicate-argument evidence does not match authoritative characters.")


def _single_token(
    values: tuple[EventEntityLinguisticToken, ...],
) -> EventEntityLinguisticToken | None:
    return values[0] if len(values) == 1 else None


def _phrase_heads(
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[EventEntityLinguisticToken, ...]:
    token_ids = {item.token_id for item in tokens}
    content = tuple(item for item in tokens if item.part_of_speech.casefold() != "punct")
    return tuple(item for item in content if item.head_token_id not in token_ids)


def _anchor_gap_code(
    predicate_matches: tuple[EventEntityLinguisticToken, ...],
    entity_tokens: tuple[EventEntityLinguisticToken, ...],
    entity_heads: tuple[EventEntityLinguisticToken, ...],
) -> PredicateArgumentGapCode | None:
    if not predicate_matches:
        return PredicateArgumentGapCode.PREDICATE_ANCHOR_MISSING
    if len(predicate_matches) > 1:
        return PredicateArgumentGapCode.PREDICATE_ANCHOR_AMBIGUOUS
    if not entity_tokens or not entity_heads:
        return PredicateArgumentGapCode.ENTITY_ANCHOR_MISSING
    if len(entity_heads) > 1:
        return PredicateArgumentGapCode.ENTITY_ANCHOR_AMBIGUOUS
    return None


def _dependency_path_ids(
    predicate_id: str,
    entity_id: str,
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> tuple[tuple[str, ...], PredicateArgumentGapCode | None]:
    predicate_chain, predicate_invalid = _ancestor_chain(predicate_id, token_by_id)
    entity_chain, entity_invalid = _ancestor_chain(entity_id, token_by_id)
    if predicate_invalid or entity_invalid:
        return (), PredicateArgumentGapCode.INVALID_DEPENDENCY_TREE
    entity_positions = {token_id: index for index, token_id in enumerate(entity_chain)}
    common = next((token_id for token_id in predicate_chain if token_id in entity_positions), None)
    if common is None:
        return (), PredicateArgumentGapCode.DISCONNECTED_DEPENDENCY_TREE
    predicate_end = predicate_chain.index(common)
    entity_end = entity_positions[common]
    path = (
        *predicate_chain[: predicate_end + 1],
        *reversed(entity_chain[:entity_end]),
    )
    return tuple(path), None


def _ancestor_chain(
    token_id: str,
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> tuple[tuple[str, ...], bool]:
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = token_id
    while current is not None:
        if current in seen or current not in token_by_id:
            return tuple(chain), True
        seen.add(current)
        chain.append(current)
        current = token_by_id[current].head_token_id
    return tuple(chain), False


def _path_steps(
    path_ids: tuple[str, ...],
    token_by_id: dict[str, EventEntityLinguisticToken],
) -> tuple[PredicateArgumentPathStep, ...]:
    steps: list[PredicateArgumentPathStep] = []
    for left_id, right_id in zip(path_ids, path_ids[1:], strict=False):
        left = token_by_id[left_id]
        right = token_by_id[right_id]
        if left.head_token_id == right_id:
            direction = PredicateArgumentPathDirection.TOWARD_HEAD
            relation = left.dependency_relation
        elif right.head_token_id == left_id:
            direction = PredicateArgumentPathDirection.TOWARD_DEPENDENT
            relation = right.dependency_relation
        else:
            raise ValueError("Predicate-argument path contains a non-edge.")
        steps.append(
            PredicateArgumentPathStep(
                from_token_id=left_id,
                to_token_id=right_id,
                direction=direction,
                dependency_relation=relation,
            )
        )
    return tuple(steps)


def classify_predicate_argument_path(
    steps: tuple[PredicateArgumentPathStep, ...],
) -> PredicateArgumentHypothesis:
    """Classify one complete directed dependency path through the frozen relation policy."""
    if not steps:
        return PredicateArgumentHypothesis.SEMANTIC_REMAINDER
    relations = tuple(item.dependency_relation.casefold() for item in steps)
    bases = tuple(item.split(":", 1)[0] for item in relations)
    core = {"nsubj", "csubj", "obj", "iobj", "obl"}
    expansion = {"conj", "appos", "flat", "compound", "fixed"}
    bridge = {"xcomp", "ccomp", "advcl", "acl"}
    nominal = {"nmod"}
    allowed = core | expansion | bridge | nominal
    if any(item == "acl:relcl" for item in relations):
        return PredicateArgumentHypothesis.RELATIVE_CLAUSE_ARGUMENT
    if set(bases) <= allowed and set(bases) & bridge and set(bases) & core:
        return PredicateArgumentHypothesis.INHERITED_ARGUMENT
    if set(bases) <= core and len(steps) == 1:
        return PredicateArgumentHypothesis.DIRECT_ARGUMENT
    if (
        set(bases) <= core | expansion | nominal
        and set(bases) & core
        and set(bases) & {"conj", "appos"}
    ):
        return PredicateArgumentHypothesis.COORDINATED_ARGUMENT
    if set(bases) <= core | expansion | nominal and set(bases) & (
        nominal | {"compound", "flat", "fixed"}
    ):
        return PredicateArgumentHypothesis.QUALIFIED_ARGUMENT
    if set(bases) <= nominal and nominal & set(bases):
        return PredicateArgumentHypothesis.QUALIFIED_ARGUMENT
    return PredicateArgumentHypothesis.SEMANTIC_REMAINDER


def _observation(
    *,
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    candidate: EventEntityConnectionCandidate,
    primary_span: EventEntitySourceSpan,
    linguistic_evidence: EventEntityLinguisticEvidence,
    predicate_anchor: EventEntityLinguisticToken | None,
    entity_anchor: EventEntityLinguisticToken | None,
    path_tokens: tuple[PredicateArgumentToken, ...],
    path_steps: tuple[PredicateArgumentPathStep, ...],
    hypothesis: PredicateArgumentHypothesis,
    gap_code: PredicateArgumentGapCode | None,
) -> PredicateArgumentObservation:
    span = next(
        item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
    )
    if primary_span != span:
        raise ValueError("Predicate-argument primary entity span changed during analysis.")
    predicate_value = _token(predicate_anchor) if predicate_anchor is not None else None
    entity_value = _token(entity_anchor) if entity_anchor is not None else None
    observation_id = _observation_id(
        source_grounded_event_id=event.id,
        event_trigger_id=trigger.id,
        candidate_id=candidate.id,
        linguistic_trace_id=linguistic_evidence.trace_id,
        linguistic_resource_identity=linguistic_evidence.resource_identity,
        predicate_anchor=predicate_value,
        entity_anchor=entity_value,
        path_steps=path_steps,
        hypothesis=hypothesis,
        gap_code=gap_code,
    )
    return PredicateArgumentObservation(
        id=observation_id,
        source_grounded_event_id=event.id,
        event_trigger_id=trigger.id,
        candidate_id=candidate.id,
        source_segment_id=event.source_segment_id,
        source_text_sha256=event.source_text_sha256,
        linguistic_trace_id=linguistic_evidence.trace_id,
        linguistic_resource_identity=linguistic_evidence.resource_identity,
        event_expression_start=trigger.start,
        event_expression_end=trigger.end,
        event_expression_text=trigger.text,
        event_head_start=trigger.head_start,
        event_head_end=trigger.head_end,
        event_head_text=trigger.head_text,
        entity_span_id=span.id,
        entity_start=span.start,
        entity_end=span.end,
        entity_text=span.text,
        predicate_anchor=predicate_value,
        entity_anchor=entity_value,
        path_tokens=path_tokens,
        path_steps=path_steps,
        hypothesis=hypothesis,
        gap_code=gap_code,
    )


def _token(value: EventEntityLinguisticToken) -> PredicateArgumentToken:
    return PredicateArgumentToken.model_validate(value.model_dump(mode="python"))


def _observation_id(
    *,
    source_grounded_event_id: str,
    event_trigger_id: str,
    candidate_id: str,
    linguistic_trace_id: str,
    linguistic_resource_identity: str,
    predicate_anchor: PredicateArgumentToken | None,
    entity_anchor: PredicateArgumentToken | None,
    path_steps: tuple[PredicateArgumentPathStep, ...],
    hypothesis: PredicateArgumentHypothesis,
    gap_code: PredicateArgumentGapCode | None,
) -> str:
    value = {
        "source_grounded_event_id": source_grounded_event_id,
        "event_trigger_id": event_trigger_id,
        "candidate_id": candidate_id,
        "linguistic_trace_id": linguistic_trace_id,
        "linguistic_resource_identity": linguistic_resource_identity,
        "predicate_anchor_id": predicate_anchor.token_id if predicate_anchor is not None else None,
        "entity_anchor_id": entity_anchor.token_id if entity_anchor is not None else None,
        "path_steps": [item.model_dump(mode="json") for item in path_steps],
        "hypothesis": hypothesis.value,
        "gap_code": gap_code.value if gap_code is not None else None,
    }
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "pao_" + hashlib.sha256(payload).hexdigest()[:24]
