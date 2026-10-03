"""Eventive statement recognition and single-record reification (R13).

R13 turns the frozen ``AHE-004`` recovered selection and its re-measured result
into one recognized statement shape and one reification draft, without a model,
without a held-out read, and without a canonical write.

The Application Layer defines a closed shape vocabulary over one recovered
statement:

- ``connection``: the statement subject and object both resolve to published
  entity references;
- ``eventive_state_change``: the statement subject names an eventive activity and
  the predicate states a change;
- ``unknown_shape``: any statement the recognizer cannot assign to the first two.

The recognizer assigns exactly one shape per statement through an exhaustive
dispatch. The reifier then turns each recognized statement into exactly one
Assertion-in-proposed-shape draft, or books an ``unknown_shape`` into one typed
hold. The eventive subject slot widens to admit an Event, EventMention, or entity
reference; the reifier never fabricates an Actor or Organization to satisfy it.

The keep-and-link rules -- a superseded Assertion keeps its original record, a
successor names one predecessor through ``supersedes_assertion_id``, and a later
Assertion about the same activity joins through a ``Relationship`` or an analytic
inference -- are pinned as acceptance criteria and validated with record-shape
unit tests over the canonical ``Assertion`` and ``Relationship`` records. R13
itself writes no canonical state; centralized identity resolution is deferred to
R14+.

The report records one recognition plus one reification draft per statement,
ordered and distinct, with zero canonical writes, zero ProposedChanges, and zero
model executions.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]
_NonEmptyStr = Annotated[str, Field(min_length=1)]

# The closed change-predicate lemma vocabulary for R13. ``intensify`` is the
# trigger-head lemma of the recovered AHE-004 predicate ("intensified"), whose
# subject names the eventive activity ("Efforts"). R14+ widens this set when the
# recognizer is generalized beyond the single recovered statement.
CHANGE_PREDICATE_LEMMAS = frozenset({"intensify"})


class StatementShape(StrEnum):
    """The closed set of statement shapes one recognizer can assign."""

    CONNECTION = "connection"
    EVENTIVE_STATE_CHANGE = "eventive_state_change"
    UNKNOWN_SHAPE = "unknown_shape"


class ReificationSubjectKind(StrEnum):
    """The widened subject slot kinds the reifier admits."""

    ENTITY = "entity"
    EVENT = "event"
    EVENT_MENTION = "event_mention"


class ReificationOutcome(StrEnum):
    """Whether one reification produced an Assertion draft or a typed hold."""

    ASSERTION_DRAFT = "assertion_draft"
    HELD = "held"


class ReificationHoldReason(StrEnum):
    """The closed hold reasons one unknown shape can book."""

    UNKNOWN_SHAPE = "unknown_shape"


class StatementSlots(BaseModel):
    """One recovered statement's explicit subject, predicate, and object slots."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    statement: _NonEmptyStr
    subject_text: _NonEmptyStr | None = None
    subject_entity_ref: str | None = None
    predicate_text: _NonEmptyStr
    predicate_lemma: _NonEmptyStr
    object_text: _NonEmptyStr | None = None
    object_entity_ref: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.subject_entity_ref is not None and self.subject_text is None:
            raise ValueError("A resolved subject entity requires source-exact subject text.")
        if self.object_entity_ref is not None and self.object_text is None:
            raise ValueError("A resolved object entity requires source-exact object text.")
        return self


class StatementRecognition(BaseModel):
    """One recognized statement carrying an Event id, its text, and one shape."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    statement: _NonEmptyStr
    shape: StatementShape


class ReificationSubject(BaseModel):
    """One reified subject with a closed slot kind and a source-exact fragment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: ReificationSubjectKind
    exact_text: _NonEmptyStr
    reference_id: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.kind is ReificationSubjectKind.ENTITY and self.reference_id is None:
            raise ValueError("An entity reified subject requires a resolved reference id.")
        return self


class ReificationObject(BaseModel):
    """One reified object carrying an entity reference or a literal value."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    exact_text: _NonEmptyStr
    entity_ref: str | None = None
    value: _NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.entity_ref is None and self.value is None:
            raise ValueError("A reified object requires an entity reference or a value.")
        if self.entity_ref is not None and self.value is not None:
            raise ValueError("A reified object must name either an entity or a value.")
        return self


class ReificationDraft(BaseModel):
    """One Assertion-in-proposed-shape draft built from a recognized statement."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    statement: _NonEmptyStr
    shape: StatementShape
    subject: ReificationSubject
    predicate_text: _NonEmptyStr
    predicate_lemma: _NonEmptyStr
    object: ReificationObject

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.shape is StatementShape.CONNECTION:
            if self.subject.kind is not ReificationSubjectKind.ENTITY:
                raise ValueError("A connection draft requires an entity subject.")
        elif self.shape is StatementShape.EVENTIVE_STATE_CHANGE:
            if self.subject.kind not in {
                ReificationSubjectKind.EVENT,
                ReificationSubjectKind.EVENT_MENTION,
            }:
                raise ValueError("An eventive state change draft requires an eventive subject.")
            if self.subject.reference_id is not None:
                raise ValueError("An eventive subject must not fabricate a reference id.")
        else:
            raise ValueError("A reification draft cannot carry an unknown shape.")
        return self


class Reification(BaseModel):
    """One reification outcome: exactly one Assertion draft or one typed hold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    statement: _NonEmptyStr
    shape: StatementShape
    outcome: ReificationOutcome
    draft: ReificationDraft | None = None
    hold_reason: ReificationHoldReason | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.outcome is ReificationOutcome.ASSERTION_DRAFT:
            if self.draft is None or self.hold_reason is not None:
                raise ValueError("An assertion draft requires a draft and no hold reason.")
            if self.shape is StatementShape.UNKNOWN_SHAPE:
                raise ValueError("An assertion draft cannot carry an unknown shape.")
            if self.draft.event_id != self.event_id:
                raise ValueError("The reification draft references a different Event.")
            if self.draft.shape is not self.shape:
                raise ValueError("The reification draft shape drifted from the reification.")
        else:
            if self.draft is not None or self.hold_reason is None:
                raise ValueError("A held reification requires no draft and one hold reason.")
            if self.shape is not StatementShape.UNKNOWN_SHAPE:
                raise ValueError("A held reification must carry an unknown shape.")
            if self.hold_reason is not ReificationHoldReason.UNKNOWN_SHAPE:
                raise ValueError("A held reification must book the unknown_shape hold reason.")
        return self


class RecognitionAndReification(BaseModel):
    """One statement's recognition bound to its reification."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    recognition: StatementRecognition
    reification: Reification

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        recognition = self.recognition
        reification = self.reification
        if recognition.event_id != reification.event_id:
            raise ValueError("Recognition and reification drifted on Event id.")
        if recognition.source_text_sha256 != reification.source_text_sha256:
            raise ValueError("Recognition and reification drifted on source text digest.")
        if recognition.statement != reification.statement:
            raise ValueError("Recognition and reification drifted on statement text.")
        if recognition.shape is not reification.shape:
            raise ValueError("Recognition and reification drifted on statement shape.")
        return self


def _recognize_shape(
    *,
    subject_text: str | None,
    subject_entity_ref: str | None,
    predicate_lemma: str,
    object_entity_ref: str | None,
) -> StatementShape:
    """Exhaustive closed-shape dispatch over one statement's explicit slots."""
    if subject_entity_ref is not None and object_entity_ref is not None:
        return StatementShape.CONNECTION
    if (
        subject_text is not None
        and subject_entity_ref is None
        and predicate_lemma in CHANGE_PREDICATE_LEMMAS
    ):
        return StatementShape.EVENTIVE_STATE_CHANGE
    return StatementShape.UNKNOWN_SHAPE


def recognize_statement(*, slots: StatementSlots) -> StatementRecognition:
    """Assign one closed shape to one recovered statement."""
    return StatementRecognition(
        event_id=slots.event_id,
        source_text_sha256=slots.source_text_sha256,
        statement=slots.statement,
        shape=_recognize_shape(
            subject_text=slots.subject_text,
            subject_entity_ref=slots.subject_entity_ref,
            predicate_lemma=slots.predicate_lemma,
            object_entity_ref=slots.object_entity_ref,
        ),
    )


def _require_same_statement(
    *,
    recognition: StatementRecognition,
    slots: StatementSlots,
) -> None:
    if recognition.event_id != slots.event_id:
        raise ValueError("Recognition and statement slots drifted on Event id.")
    if recognition.source_text_sha256 != slots.source_text_sha256:
        raise ValueError("Recognition and statement slots drifted on source text digest.")
    if recognition.statement != slots.statement:
        raise ValueError("Recognition and statement slots drifted on statement text.")


def _reification_object(*, slots: StatementSlots, require_entity: bool) -> ReificationObject:
    if slots.object_entity_ref is not None:
        if slots.object_text is None:
            raise ValueError("A resolved object entity requires source-exact object text.")
        return ReificationObject(exact_text=slots.object_text, entity_ref=slots.object_entity_ref)
    if slots.object_text is not None:
        if require_entity:
            raise ValueError("A connection statement requires a resolved object entity.")
        return ReificationObject(exact_text=slots.object_text, value=slots.object_text)
    raise ValueError("A known-shape statement requires an object entity or value.")


def _reify_connection(recognition: StatementRecognition, slots: StatementSlots) -> Reification:
    if slots.subject_text is None or slots.subject_entity_ref is None:
        raise ValueError("A connection statement requires a resolved subject entity.")
    draft = ReificationDraft(
        event_id=recognition.event_id,
        source_text_sha256=recognition.source_text_sha256,
        statement=recognition.statement,
        shape=StatementShape.CONNECTION,
        subject=ReificationSubject(
            kind=ReificationSubjectKind.ENTITY,
            exact_text=slots.subject_text,
            reference_id=slots.subject_entity_ref,
        ),
        predicate_text=slots.predicate_text,
        predicate_lemma=slots.predicate_lemma,
        object=_reification_object(slots=slots, require_entity=True),
    )
    return Reification(
        event_id=recognition.event_id,
        source_text_sha256=recognition.source_text_sha256,
        statement=recognition.statement,
        shape=StatementShape.CONNECTION,
        outcome=ReificationOutcome.ASSERTION_DRAFT,
        draft=draft,
    )


def _reify_eventive_state_change(
    recognition: StatementRecognition,
    slots: StatementSlots,
) -> Reification:
    if slots.subject_text is None:
        raise ValueError("An eventive state change requires a source-exact eventive subject.")
    if slots.subject_entity_ref is not None:
        raise ValueError("An eventive state change subject must not resolve to an entity.")
    draft = ReificationDraft(
        event_id=recognition.event_id,
        source_text_sha256=recognition.source_text_sha256,
        statement=recognition.statement,
        shape=StatementShape.EVENTIVE_STATE_CHANGE,
        subject=ReificationSubject(
            kind=ReificationSubjectKind.EVENT,
            exact_text=slots.subject_text,
        ),
        predicate_text=slots.predicate_text,
        predicate_lemma=slots.predicate_lemma,
        object=_reification_object(slots=slots, require_entity=False),
    )
    return Reification(
        event_id=recognition.event_id,
        source_text_sha256=recognition.source_text_sha256,
        statement=recognition.statement,
        shape=StatementShape.EVENTIVE_STATE_CHANGE,
        outcome=ReificationOutcome.ASSERTION_DRAFT,
        draft=draft,
    )


def _reify_unknown_shape(recognition: StatementRecognition) -> Reification:
    return Reification(
        event_id=recognition.event_id,
        source_text_sha256=recognition.source_text_sha256,
        statement=recognition.statement,
        shape=StatementShape.UNKNOWN_SHAPE,
        outcome=ReificationOutcome.HELD,
        hold_reason=ReificationHoldReason.UNKNOWN_SHAPE,
    )


def reify_statement(*, recognition: StatementRecognition, slots: StatementSlots) -> Reification:
    """Turn one recognized statement into exactly one Assertion draft or one hold."""
    _require_same_statement(recognition=recognition, slots=slots)
    if recognition.shape is StatementShape.CONNECTION:
        return _reify_connection(recognition, slots)
    if recognition.shape is StatementShape.EVENTIVE_STATE_CHANGE:
        return _reify_eventive_state_change(recognition, slots)
    if recognition.shape is StatementShape.UNKNOWN_SHAPE:
        return _reify_unknown_shape(recognition)
    raise ValueError(f"Unsupported statement shape: {recognition.shape}")


def recognize_and_reify(*, slots: StatementSlots) -> RecognitionAndReification:
    """Recognize one statement then reify it into exactly one draft or hold."""
    recognition = recognize_statement(slots=slots)
    reification = reify_statement(recognition=recognition, slots=slots)
    return RecognitionAndReification(recognition=recognition, reification=reification)


class EventiveStatementReport(BaseModel):
    """Sealed R13 report: ordered recognition-and-reification set plus zero counters."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    items: tuple[RecognitionAndReification, ...]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.recognition.event_id for item in self.items)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("R13 report items must be ordered and distinct.")
        if (
            self.canonical_write_count != 0
            or self.proposed_change_count != 0
            or self.model_execution_count != 0
        ):
            raise ValueError("R13 report must record zero writes, proposals, and model executions.")
        return self


def eventive_statement_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one R13 report draft."""
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


def build_eventive_statement_report(
    *,
    items: tuple[RecognitionAndReification, ...],
) -> EventiveStatementReport:
    """Assemble and seal the R13 report with zero writes, proposals, and model executions."""
    draft = EventiveStatementReport.model_construct(
        items=items,
        canonical_write_count=0,
        proposed_change_count=0,
        model_execution_count=0,
        result_fingerprint="0" * 64,
    )
    return EventiveStatementReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=eventive_statement_report_fingerprint(draft),
    )
