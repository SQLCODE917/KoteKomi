"""Deterministic model-free decontextualization composition (R4).

The composer assembles one decontextualized proposition per Event from the frozen
R3-A Selected Constituent Set, the pinned Stanza dependency tree, and the connection
Gold entity references. It never invokes a model, never reads the held-out partition,
and never writes canonical state.

One Event becomes either:

- a ``proposition`` carrying one content triple (subject role / relation label /
  object role) plus one attribution and one polarity/modality, or
- a ``held`` result carrying one typed hold reason and no composed content.

The relation label is the dependency-token lemma of the Event trigger head only,
never a model answer. The subject and object roles come from the selected core
event constituents whose token spans contain the trigger head's ``nsubj`` and
``obj``/``iobj``/``obl`` dependents respectively. Attribution reuses the
reporting-predicate detection patterns introduced by the deterministic
trigger-scope split: a reporting predicate governing the trigger clause yields a
``targeted`` attribution naming the carrier reporter; no reporting predicate yields
``source_narrator``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentSourceRange,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.hybrid_event_semantics import EventModality, EventPolarity
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ParserConstituent,
)
from kotekomi_application.trigger_scope_split import (
    ADJUNCT_RELATIONS,
    CARRIER_FUNCTION_RELATIONS,
    COMPLEMENT_FUNCTION_RELATIONS,
    COMPLEMENT_RELATIONS,
    REPORTING_PREDICATE_LEMMAS,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
_EntityId = Annotated[str, Field(pattern=r"^EGE-[0-9]{3}$")]

_SUBJECT_DEPENDENCY_RELATIONS = frozenset({"nsubj", "nsubj:pass"})
_OBJECT_DEPENDENCY_RELATIONS = frozenset({"obj", "iobj", "obl"})
_MODAL_MODALITY: tuple[tuple[str, EventModality], ...] = (
    ("can", EventModality.POSSIBLE),
    ("could", EventModality.POSSIBLE),
    ("may", EventModality.POSSIBLE),
    ("might", EventModality.POSSIBLE),
    ("must", EventModality.RECOMMENDED),
    ("should", EventModality.RECOMMENDED),
    ("will", EventModality.PLANNED),
    ("would", EventModality.HYPOTHETICAL),
    ("shall", EventModality.PLANNED),
)


class DecontextualizationStatus(StrEnum):
    """Terminal state of one deterministic decontextualization composition."""

    PROPOSITION = "proposition"
    HELD = "held"


class DecontextualizationHoldReason(StrEnum):
    """Typed reason one Event cannot be assembled deterministically."""

    SELECTION_REJECTED = "selection_rejected"
    SELECTION_EMPTY = "selection_empty"
    TRIGGER_HEAD_UNRESOLVED = "trigger_head_unresolved"
    SUBJECT_UNAVAILABLE = "subject_unavailable"
    ATTRIBUTION_AMBIGUOUS = "attribution_ambiguous"
    SOURCE_OFFSET_DRIFT = "source_offset_drift"


class DecontextualizationRoleKind(StrEnum):
    """The two core content-triple roles."""

    SUBJECT = "subject"
    OBJECT = "object"


class DecontextualizationAttributionKind(StrEnum):
    """How one Source credits the composed Event content."""

    TARGETED = "targeted"
    SOURCE_NARRATOR = "source_narrator"


class DecontextualizationEntityRef(BaseModel):
    """One connection Gold entity reference admitted for a composed role."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_id: _EntityId
    entity_kind: Literal["actor", "organization"]
    canonical_name: Annotated[str, Field(min_length=1)]
    accepted_source_occurrences: tuple[AttachmentSourceRange, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.accepted_source_occurrences:
            raise ValueError("A decontextualization entity requires one accepted occurrence.")
        ordered = tuple(
            sorted(self.accepted_source_occurrences, key=lambda item: (item.start, item.end))
        )
        if ordered != self.accepted_source_occurrences:
            raise ValueError("Decontextualization entity occurrences must be source-ordered.")
        return self


class DecontextualizedRole(BaseModel):
    """One exact selected core-event fragment and its resolved reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role: DecontextualizationRoleKind
    exact_fragment: AttachmentSourceRange
    entity_ref: _EntityId | None = None
    object_value: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.entity_ref is None and self.object_value is None:
            raise ValueError("A composed role requires an entity reference or an object value.")
        if self.entity_ref is not None and self.object_value is not None:
            raise ValueError("A composed role must name either an entity or an object value.")
        if self.role is DecontextualizationRoleKind.SUBJECT and self.object_value is not None:
            raise ValueError("A subject role cannot carry an object value.")
        return self


class DecontextualizedAttribution(BaseModel):
    """One reporting carrier and its resolved reporter with an attribution kind."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: DecontextualizationAttributionKind
    exact_carrier: AttachmentSourceRange | None = None
    reporter_ref: _EntityId | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.kind is DecontextualizationAttributionKind.TARGETED:
            if self.exact_carrier is None or self.reporter_ref is None:
                raise ValueError("A targeted attribution requires a carrier and a reporter.")
        elif self.exact_carrier is not None or self.reporter_ref is not None:
            raise ValueError("A source-narrator attribution cannot name a carrier or reporter.")
        return self


class DecontextualizedProposition(BaseModel):
    """One decontextualized Event proposition or a typed hold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    relation_label: Annotated[str, Field(min_length=1)] | None = None
    subject: DecontextualizedRole | None = None
    object: DecontextualizedRole | None = None
    polarity: EventPolarity | None = None
    modality: EventModality | None = None
    attribution: DecontextualizedAttribution | None = None
    status: DecontextualizationStatus
    hold_reason: DecontextualizationHoldReason | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is DecontextualizationStatus.PROPOSITION:
            if self.relation_label is None or self.subject is None or self.attribution is None:
                raise ValueError("A composed proposition requires the complete content triple.")
            if self.polarity is None or self.modality is None:
                raise ValueError("A composed proposition requires polarity and modality.")
            if self.hold_reason is not None:
                raise ValueError("A composed proposition cannot carry a hold reason.")
        else:
            if self.hold_reason is None:
                raise ValueError("A held result requires one hold reason.")
            if any(
                value is not None
                for value in (
                    self.relation_label,
                    self.subject,
                    self.object,
                    self.polarity,
                    self.modality,
                    self.attribution,
                )
            ):
                raise ValueError("A held result cannot carry composed content.")
        if (
            self.subject is not None
            and self.subject.role is not DecontextualizationRoleKind.SUBJECT
        ):
            raise ValueError("The subject field must carry a subject role.")
        if self.object is not None and self.object.role is not DecontextualizationRoleKind.OBJECT:
            raise ValueError("The object field must carry an object role.")
        return self


class DecontextualizationCensus(BaseModel):
    """One partition's composed and held Event counts with hold-reason counts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    event_count: Annotated[int, Field(ge=0)]
    composed_count: Annotated[int, Field(ge=0)]
    held_count: Annotated[int, Field(ge=0)]
    hold_reason_counts: dict[str, Annotated[int, Field(ge=0)]]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.event_count != self.composed_count + self.held_count:
            raise ValueError("Decontextualization census Event counts drifted.")
        if set(self.hold_reason_counts) - {item.value for item in DecontextualizationHoldReason}:
            raise ValueError("Decontextualization census names an unknown hold reason.")
        if sum(self.hold_reason_counts.values()) != self.held_count:
            raise ValueError("Decontextualization census hold-reason counts drifted.")
        return self


class DecontextualizationReport(BaseModel):
    """Sealed R4 report with both partition censuses and a semantic fingerprint."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    development: DecontextualizationCensus
    validation: DecontextualizationCensus
    model_execution_count: Annotated[int, Field(ge=0)]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = decontextualization_report_fingerprint(self)
        if self.result_fingerprint != expected:
            raise ValueError("Decontextualization report fingerprint does not match its contents.")
        if (
            self.development.partition_role != "development"
            or self.validation.partition_role != "validation"
        ):
            raise ValueError("Decontextualization report carries a misplaced partition census.")
        return self


def decontextualization_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one Decontextualization Report."""
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
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


class _ReportingCarrierStatus(StrEnum):
    """Terminal state of the reusable reporting-carrier detection."""

    COMPLETE = "complete"
    PREDICATE_MISSING = "reporting_predicate_missing"
    PREDICATE_AMBIGUOUS = "reporting_predicate_ambiguous"
    COMPLEMENT_MISSING = "governed_complement_missing"


def _selected_constituents(
    answer: ConstituentSelectionAnswer,
    inventory: ConstituentCandidateInventory,
) -> tuple[ParserConstituent, ...]:
    if answer.status is not ConstituentSelectionStatus.SELECTED:
        return ()
    return tuple(inventory.constituents[index - 1] for index in answer.selected_label_indexes)


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


def _maximal_constituent(
    token: EventEntityLinguisticToken,
    head: EventEntityLinguisticToken,
    constituents: tuple[ParserConstituent, ...],
) -> ParserConstituent | None:
    candidates = [
        item
        for item in constituents
        if token.token_id in item.token_ids and head.token_id not in item.token_ids
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item.constituent_range.end - item.constituent_range.start,
            -item.constituent_range.start,
        ),
    )


def _resolve_entity(
    exact_fragment: AttachmentSourceRange,
    entities: tuple[DecontextualizationEntityRef, ...],
) -> str | None:
    matches = [
        entity.entity_id
        for entity in entities
        for occurrence in entity.accepted_source_occurrences
        if exact_fragment.start <= occurrence.start and occurrence.end <= exact_fragment.end
    ]
    distinct = set(matches)
    if len(distinct) == 1:
        return next(iter(distinct))
    return None


def _held(
    event_id: str,
    source_text_sha256: str,
    hold_reason: DecontextualizationHoldReason,
) -> DecontextualizedProposition:
    return DecontextualizedProposition(
        event_id=event_id,
        source_text_sha256=source_text_sha256,
        status=DecontextualizationStatus.HELD,
        hold_reason=hold_reason,
    )


def _clause_ancestors(
    head: EventEntityLinguisticToken,
    by_id: Mapping[str, EventEntityLinguisticToken],
) -> tuple[EventEntityLinguisticToken, ...]:
    found: list[EventEntityLinguisticToken] = []
    seen: set[str] = set()
    cursor: EventEntityLinguisticToken = head
    while cursor.token_id not in seen:
        seen.add(cursor.token_id)
        found.append(cursor)
        if cursor.head_token_id is None:
            break
        cursor = by_id[cursor.head_token_id]
    return tuple(found)


def _subtree_ids(
    root_id: str,
    children: Mapping[str, tuple[EventEntityLinguisticToken, ...]],
) -> frozenset[str]:
    found: set[str] = set()
    pending = [root_id]
    while pending:
        token_id = pending.pop()
        if token_id in found:
            continue
        found.add(token_id)
        pending.extend(item.token_id for item in children.get(token_id, ()))
    return frozenset(found)


def _reporting_carrier(
    source_text: str,
    head: EventEntityLinguisticToken,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[AttachmentSourceRange | None, _ReportingCarrierStatus]:
    by_id = {token.token_id: token for token in tokens}
    grouped: dict[str, list[EventEntityLinguisticToken]] = {}
    for token in tokens:
        if token.head_token_id is not None:
            grouped.setdefault(token.head_token_id, []).append(token)
    children: dict[str, tuple[EventEntityLinguisticToken, ...]] = {
        token_id: tuple(value) for token_id, value in grouped.items()
    }

    sentence_tokens = tuple(token for token in tokens if token.sentence_id == head.sentence_id)
    ancestor_ids = {token.token_id for token in _clause_ancestors(head, by_id)}

    candidates: dict[str, tuple[EventEntityLinguisticToken, EventEntityLinguisticToken | None]] = {}
    cursor: EventEntityLinguisticToken = head
    seen: set[str] = set()
    while cursor.token_id not in seen:
        seen.add(cursor.token_id)
        parent_id = cursor.head_token_id
        if parent_id is None:
            break
        parent = by_id[parent_id]
        if (
            parent.lemma.casefold() in REPORTING_PREDICATE_LEMMAS
            and cursor.dependency_relation in COMPLEMENT_RELATIONS
        ):
            candidates[parent.token_id] = (parent, cursor)
        cursor = parent

    for token in sentence_tokens:
        if token.token_id in candidates:
            continue
        if token.lemma.casefold() not in REPORTING_PREDICATE_LEMMAS:
            continue
        if token.head_token_id not in ancestor_ids:
            continue
        if token.dependency_relation not in ADJUNCT_RELATIONS:
            continue
        candidates[token.token_id] = (token, None)

    if not candidates:
        return None, _ReportingCarrierStatus.PREDICATE_MISSING
    if len(candidates) > 1:
        return None, _ReportingCarrierStatus.PREDICATE_AMBIGUOUS

    reporting, complement_child = next(iter(candidates.values()))
    if complement_child is not None:
        complement_ids = _subtree_ids(complement_child.token_id, children)
        carrier_ids = _subtree_ids(reporting.token_id, children) - complement_ids
    else:
        carrier_ids = _subtree_ids(reporting.token_id, children)
        complement_ids = frozenset(token.token_id for token in sentence_tokens) - carrier_ids

    carrier_tokens = tuple(
        token
        for token in tokens
        if token.token_id in carrier_ids
        and token.dependency_relation not in CARRIER_FUNCTION_RELATIONS
    )
    complement_tokens = tuple(
        token
        for token in tokens
        if token.token_id in complement_ids
        and token.dependency_relation not in COMPLEMENT_FUNCTION_RELATIONS
    )
    carrier = _source_exact_range(source_text, carrier_tokens, sentence_tokens)
    complement = _source_exact_range(source_text, complement_tokens, sentence_tokens)
    if carrier is None or complement is None:
        return None, _ReportingCarrierStatus.COMPLEMENT_MISSING
    return carrier, _ReportingCarrierStatus.COMPLETE


def _modality(dependents: tuple[EventEntityLinguisticToken, ...]) -> EventModality:
    for lemma, modality in _MODAL_MODALITY:
        if any(token.lemma.casefold() == lemma for token in dependents):
            return modality
    return EventModality.ACTUAL


def _source_exact_range(
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    sentence_tokens: tuple[EventEntityLinguisticToken, ...],
) -> AttachmentSourceRange | None:
    if not tokens:
        return None
    selected_ids = {token.token_id for token in tokens}
    ordered = sorted(tokens, key=lambda token: (token.start, token.end))
    for token in ordered:
        if source_text[token.start : token.end] != token.text:
            raise ValueError("Decontextualization token offsets drifted from source text.")
    start = ordered[0].start
    end = ordered[-1].end
    for token in sentence_tokens:
        if token.token_id in selected_ids:
            continue
        if start < token.start and token.end < end:
            return None
    return AttachmentSourceRange(start=start, end=end, text=source_text[start:end])


def build_decontextualized_proposition(
    *,
    event_id: str,
    source_text: str,
    source_text_sha256: str,
    inventory: ConstituentCandidateInventory,
    answer: ConstituentSelectionAnswer,
    trigger_head_start: int,
    trigger_head_end: int,
    tokens: tuple[EventEntityLinguisticToken, ...],
    entities: tuple[DecontextualizationEntityRef, ...],
) -> DecontextualizedProposition:
    """Compose one Event's decontextualized proposition or a typed hold.

    The composer derives only from the frozen selection, the pinned dependency tree,
    and the connection Gold entity references. It never reads a model answer for the
    relation label, never invents a subject/object/reporter, and never writes state.
    """
    if inventory.event_id != event_id or answer.event_id != event_id:
        raise ValueError("Decontextualization inputs reference inconsistent Events.")
    if hashlib.sha256(source_text.encode()).hexdigest() != source_text_sha256:
        raise ValueError("Decontextualization source digest drifted from its text.")
    if inventory.source_text_sha256 != source_text_sha256:
        raise ValueError("Decontextualization inventory digest drifted from its source text.")

    if answer.status is ConstituentSelectionStatus.REJECTED:
        return _held(event_id, source_text_sha256, DecontextualizationHoldReason.SELECTION_REJECTED)
    if answer.status is ConstituentSelectionStatus.NONE:
        return _held(event_id, source_text_sha256, DecontextualizationHoldReason.SELECTION_EMPTY)

    selected = _selected_constituents(answer, inventory)
    for item in selected:
        exact = source_text[item.constituent_range.start : item.constituent_range.end]
        if exact != item.constituent_range.text:
            return _held(
                event_id,
                source_text_sha256,
                DecontextualizationHoldReason.SOURCE_OFFSET_DRIFT,
            )

    head = _trigger_head_token(trigger_head_start, trigger_head_end, tokens)
    if head is None:
        return _held(
            event_id,
            source_text_sha256,
            DecontextualizationHoldReason.TRIGGER_HEAD_UNRESOLVED,
        )

    relation_label = head.lemma.casefold()
    dependents = _dependents(head, tokens)

    subject_token = next(
        (
            token
            for token in dependents
            if token.dependency_relation in _SUBJECT_DEPENDENCY_RELATIONS
        ),
        None,
    )
    if subject_token is None:
        return _held(
            event_id,
            source_text_sha256,
            DecontextualizationHoldReason.SUBJECT_UNAVAILABLE,
        )
    subject_constituent = _maximal_constituent(subject_token, head, selected)
    if subject_constituent is None:
        return _held(
            event_id,
            source_text_sha256,
            DecontextualizationHoldReason.SUBJECT_UNAVAILABLE,
        )
    subject_entity = _resolve_entity(subject_constituent.constituent_range, entities)
    if subject_entity is None:
        return _held(
            event_id,
            source_text_sha256,
            DecontextualizationHoldReason.SUBJECT_UNAVAILABLE,
        )
    subject_role = DecontextualizedRole(
        role=DecontextualizationRoleKind.SUBJECT,
        exact_fragment=subject_constituent.constituent_range,
        entity_ref=subject_entity,
    )

    object_role: DecontextualizedRole | None = None
    object_token = next(
        (
            token
            for token in dependents
            if token.dependency_relation in _OBJECT_DEPENDENCY_RELATIONS
        ),
        None,
    )
    if object_token is not None:
        object_constituent = _maximal_constituent(object_token, head, selected)
        if object_constituent is not None:
            object_entity = _resolve_entity(object_constituent.constituent_range, entities)
            if object_entity is not None:
                object_role = DecontextualizedRole(
                    role=DecontextualizationRoleKind.OBJECT,
                    exact_fragment=object_constituent.constituent_range,
                    entity_ref=object_entity,
                )
            else:
                object_role = DecontextualizedRole(
                    role=DecontextualizationRoleKind.OBJECT,
                    exact_fragment=object_constituent.constituent_range,
                    object_value=object_constituent.constituent_range.text,
                )

    polarity = (
        EventPolarity.NEGATED
        if any(token.dependency_relation == "neg" for token in dependents)
        else EventPolarity.AFFIRMED
    )
    modality = _modality(dependents)

    carrier, carrier_status = _reporting_carrier(source_text, head, tokens)
    if carrier_status is _ReportingCarrierStatus.PREDICATE_AMBIGUOUS:
        return _held(
            event_id,
            source_text_sha256,
            DecontextualizationHoldReason.ATTRIBUTION_AMBIGUOUS,
        )
    if carrier_status is _ReportingCarrierStatus.COMPLEMENT_MISSING:
        return _held(
            event_id,
            source_text_sha256,
            DecontextualizationHoldReason.ATTRIBUTION_AMBIGUOUS,
        )
    if carrier_status is _ReportingCarrierStatus.PREDICATE_MISSING:
        attribution = DecontextualizedAttribution(
            kind=DecontextualizationAttributionKind.SOURCE_NARRATOR
        )
    else:
        assert carrier is not None
        reporter = _resolve_entity(carrier, entities)
        if reporter is None:
            return _held(
                event_id,
                source_text_sha256,
                DecontextualizationHoldReason.ATTRIBUTION_AMBIGUOUS,
            )
        attribution = DecontextualizedAttribution(
            kind=DecontextualizationAttributionKind.TARGETED,
            exact_carrier=carrier,
            reporter_ref=reporter,
        )

    return DecontextualizedProposition(
        event_id=event_id,
        source_text_sha256=source_text_sha256,
        relation_label=relation_label,
        subject=subject_role,
        object=object_role,
        polarity=polarity,
        modality=modality,
        attribution=attribution,
        status=DecontextualizationStatus.PROPOSITION,
    )


def build_decontextualization_census(
    *,
    partition_role: Literal["development", "validation"],
    event_ids: tuple[str, ...],
    propositions: Mapping[str, DecontextualizedProposition],
) -> DecontextualizationCensus:
    """Score one partition's composed and held Events with hold-reason counts."""
    composed_count = 0
    held_count = 0
    reason_counts: dict[str, int] = {}
    for event_id in event_ids:
        proposition = propositions[event_id]
        if proposition.event_id != event_id:
            raise ValueError("Decontextualization census encountered an Event ID mismatch.")
        if proposition.status is DecontextualizationStatus.PROPOSITION:
            composed_count += 1
        else:
            held_count += 1
            assert proposition.hold_reason is not None
            reason_counts[proposition.hold_reason.value] = (
                reason_counts.get(proposition.hold_reason.value, 0) + 1
            )
    return DecontextualizationCensus(
        partition_role=partition_role,
        event_count=len(event_ids),
        composed_count=composed_count,
        held_count=held_count,
        hold_reason_counts=reason_counts,
    )


def build_decontextualization_report(
    *,
    development: DecontextualizationCensus,
    validation: DecontextualizationCensus,
) -> DecontextualizationReport:
    """Assemble and seal the complete R4 report."""
    draft = DecontextualizationReport.model_construct(
        development=development,
        validation=validation,
        model_execution_count=0,
        canonical_write_count=0,
        proposed_change_count=0,
        result_fingerprint="0" * 64,
    )
    return DecontextualizationReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=decontextualization_report_fingerprint(draft),
    )
