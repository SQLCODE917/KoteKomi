"""Centralized identity resolution for the R14 deliverable.

R14 links one vague eventive activity mention to one later concrete mention
through one deterministic identity-resolution step that serves every statement
shape.

The closed deterministic identity keys are:

- ``explicit_supersede``: the concrete mention's Assertion names the vague
  Assertion through ``supersedes_assertion_id``;
- ``shared_subject_reference``: both mentions carry the same non-null subject
  reference;
- ``no_shared_identity_key``: every pair that matches no other key.

One resolver handles every shape. It reads only the Assertion id, the subject
reference, and the supersedes field; it never reads the statement shape. A
resolved pair returns one keep-and-link record whose concrete Assertion
supersedes the vague Assertion and whose predecessor keeps its original record.
An unresolved pair returns one typed hold; the resolver never fabricates a
subject reference to resolve a pair.

R14 writes no canonical state, records no ProposedChanges, and executes no
model. The report seals one fingerprint over the ordered resolution set with
three zero counters.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.eventive_statement_recognition import (
    ReificationDraft,
    ReificationSubject,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]
_AssertionId = Annotated[str, Field(pattern=r"^ast_[A-Za-z0-9][A-Za-z0-9_-]*$")]


class IdentityResolutionSignal(StrEnum):
    """The closed set of identity keys one resolver can select."""

    EXPLICIT_SUPERSEDE = "explicit_supersede"
    SHARED_SUBJECT_REFERENCE = "shared_subject_reference"
    NO_SHARED_IDENTITY_KEY = "no_shared_identity_key"


class IdentityResolutionOutcome(StrEnum):
    """Whether one pair resolves to the same activity."""

    RESOLVED_SAME_ACTIVITY = "resolved_same_activity"
    UNRESOLVED = "unresolved"


class IdentityResolutionHoldReason(StrEnum):
    """The closed hold reason one unresolved pair books."""

    NO_SHARED_IDENTITY_KEY = "no_shared_identity_key"


class IdentityResolutionMention(BaseModel):
    """One shape-agnostic mention: an Assertion id, an Event id, and a subject."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    assertion_id: _AssertionId
    event_id: _EventId
    subject: ReificationSubject
    supersedes_assertion_id: _AssertionId | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.supersedes_assertion_id == self.assertion_id:
            raise ValueError("A mention Assertion cannot supersede itself.")
        return self


class IdentityResolutionLink(BaseModel):
    """The keep-and-link record: one successor that supersedes one predecessor."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    successor_assertion_id: _AssertionId
    predecessor_assertion_id: _AssertionId

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.successor_assertion_id == self.predecessor_assertion_id:
            raise ValueError("A keep-and-link successor must differ from its predecessor.")
        return self


class IdentityResolution(BaseModel):
    """One resolution: a selected identity key plus a link or a typed hold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    vague_event_id: _EventId
    concrete_event_id: _EventId
    vague_assertion_id: _AssertionId
    concrete_assertion_id: _AssertionId
    signal: IdentityResolutionSignal
    outcome: IdentityResolutionOutcome
    link: IdentityResolutionLink | None = None
    hold_reason: IdentityResolutionHoldReason | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.outcome is IdentityResolutionOutcome.RESOLVED_SAME_ACTIVITY:
            if self.link is None or self.hold_reason is not None:
                raise ValueError("A resolved pair requires one link and no hold reason.")
            if self.signal is IdentityResolutionSignal.NO_SHARED_IDENTITY_KEY:
                raise ValueError("A resolved pair cannot carry no_shared_identity_key.")
            if self.link.successor_assertion_id != self.concrete_assertion_id:
                raise ValueError("The keep-and-link successor must be the concrete Assertion.")
            if self.link.predecessor_assertion_id != self.vague_assertion_id:
                raise ValueError("The keep-and-link predecessor must be the vague Assertion.")
        else:
            if self.link is not None or self.hold_reason is None:
                raise ValueError("An unresolved pair requires no link and one hold reason.")
            if self.signal is not IdentityResolutionSignal.NO_SHARED_IDENTITY_KEY:
                raise ValueError("An unresolved pair must carry no_shared_identity_key.")
            if self.hold_reason is not IdentityResolutionHoldReason.NO_SHARED_IDENTITY_KEY:
                raise ValueError(
                    "An unresolved pair must book the no_shared_identity_key hold reason."
                )
        return self


def _identity_resolution_signal(
    *,
    vague: IdentityResolutionMention,
    concrete: IdentityResolutionMention,
) -> IdentityResolutionSignal:
    """Select one closed identity key for one vague-and-concrete pair."""

    if concrete.supersedes_assertion_id == vague.assertion_id:
        return IdentityResolutionSignal.EXPLICIT_SUPERSEDE
    if (
        vague.subject.reference_id is not None
        and vague.subject.reference_id == concrete.subject.reference_id
    ):
        return IdentityResolutionSignal.SHARED_SUBJECT_REFERENCE
    return IdentityResolutionSignal.NO_SHARED_IDENTITY_KEY


def resolve_identity(
    *,
    vague: IdentityResolutionMention,
    concrete: IdentityResolutionMention,
) -> IdentityResolution:
    """Resolve one vague and one concrete mention through one centralized step."""

    if vague.assertion_id == concrete.assertion_id:
        raise ValueError("Identity resolution requires two distinct Assertions.")
    signal = _identity_resolution_signal(vague=vague, concrete=concrete)
    if signal is IdentityResolutionSignal.NO_SHARED_IDENTITY_KEY:
        return IdentityResolution(
            vague_event_id=vague.event_id,
            concrete_event_id=concrete.event_id,
            vague_assertion_id=vague.assertion_id,
            concrete_assertion_id=concrete.assertion_id,
            signal=signal,
            outcome=IdentityResolutionOutcome.UNRESOLVED,
            hold_reason=IdentityResolutionHoldReason.NO_SHARED_IDENTITY_KEY,
        )
    return IdentityResolution(
        vague_event_id=vague.event_id,
        concrete_event_id=concrete.event_id,
        vague_assertion_id=vague.assertion_id,
        concrete_assertion_id=concrete.assertion_id,
        signal=signal,
        outcome=IdentityResolutionOutcome.RESOLVED_SAME_ACTIVITY,
        link=IdentityResolutionLink(
            successor_assertion_id=concrete.assertion_id,
            predecessor_assertion_id=vague.assertion_id,
        ),
    )


def mention_from_reification(
    *,
    draft: ReificationDraft,
    assertion_id: str,
) -> IdentityResolutionMention:
    """Convert one reification draft into one shape-agnostic mention."""

    return IdentityResolutionMention(
        assertion_id=assertion_id,
        event_id=draft.event_id,
        subject=draft.subject,
    )


class IdentityResolutionReport(BaseModel):
    """Sealed R14 report: the ordered resolution set plus zero counters."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    items: tuple[IdentityResolution, ...]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        keys = tuple((item.vague_event_id, item.concrete_event_id) for item in self.items)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("R14 report items must be ordered and distinct.")
        if (
            self.canonical_write_count != 0
            or self.proposed_change_count != 0
            or self.model_execution_count != 0
        ):
            raise ValueError(
                "R14 report must record zero writes, proposals, and model executions."
            )
        return self


def identity_resolution_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one R14 report draft."""

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


def build_identity_resolution_report(
    *,
    items: tuple[IdentityResolution, ...],
) -> IdentityResolutionReport:
    """Assemble and seal the R14 report with zero writes, proposals, and model executions."""

    draft = IdentityResolutionReport.model_construct(
        items=items,
        canonical_write_count=0,
        proposed_change_count=0,
        model_execution_count=0,
        result_fingerprint="0" * 64,
    )
    return IdentityResolutionReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=identity_resolution_report_fingerprint(draft),
    )