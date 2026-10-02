"""Residual composition-hold routing for the R10 deliverable.

R10 maps each residual Event to one typed disposition.
It separates selection failure from composition hold and enforces held safety.
Nothing here invokes a model, writes canonical state, or reads a held-out partition.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.calibrated_residual_ownership import (
    ResidualReviewReason,
    SelectionRouting,
    SelectionRoutingDecision,
)
from kotekomi_application.decontextualization_composition import (
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DecontextualizedProposition,
)

_SHA256 = r"^[a-f0-9]{64}$"
_EventId = Annotated[str, Field(pattern=r"^(TGE|AHE)-[0-9]{3}$")]


class ResidualDispositionReason(StrEnum):
    """One closed reason an Event holds or composes."""

    SELECTION_REJECTED = "selection_rejected"
    SELECTION_CENSORED = "selection_censored"
    SELECTION_BELOW_THRESHOLD = "selection_below_threshold"
    SELECTION_ABSTAINED = "selection_abstained"
    COMPOSITION_HOLD = "composition_hold"
    COMPOSABLE = "composable"


_SELECTION_REASONS = frozenset(
    {
        ResidualDispositionReason.SELECTION_REJECTED,
        ResidualDispositionReason.SELECTION_CENSORED,
        ResidualDispositionReason.SELECTION_BELOW_THRESHOLD,
        ResidualDispositionReason.SELECTION_ABSTAINED,
    }
)


class ResidualDisposition(BaseModel):
    """One Event's typed disposition plus an optional hold reason or proposition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    reason: ResidualDispositionReason
    hold_reason: DecontextualizationHoldReason | None = None
    proposition: DecontextualizedProposition | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.reason in _SELECTION_REASONS:
            if self.hold_reason is not None or self.proposition is not None:
                raise ValueError("A selection disposition carries no hold reason or proposition.")
        elif self.reason is ResidualDispositionReason.COMPOSITION_HOLD:
            if self.hold_reason is None:
                raise ValueError("A composition-hold disposition requires one hold reason.")
            if self.proposition is not None:
                raise ValueError("A composition-hold disposition cannot carry a proposition.")
        elif self.reason is ResidualDispositionReason.COMPOSABLE:
            if self.hold_reason is not None:
                raise ValueError("A composable disposition cannot carry a hold reason.")
            if (
                self.proposition is None
                or self.proposition.status is not DecontextualizationStatus.PROPOSITION
            ):
                raise ValueError("A composable disposition requires one proposition.")
        return self


def _selection_reason(routing: SelectionRouting) -> ResidualDispositionReason:
    """Map one residual-review routing reason to one selection disposition reason."""
    reason = routing.reason
    if reason is ResidualReviewReason.REJECTED:
        return ResidualDispositionReason.SELECTION_REJECTED
    if reason is ResidualReviewReason.CENSORED:
        return ResidualDispositionReason.SELECTION_CENSORED
    if reason is ResidualReviewReason.BELOW_THRESHOLD:
        return ResidualDispositionReason.SELECTION_BELOW_THRESHOLD
    if reason is ResidualReviewReason.COMPOSITION_HOLD:
        return ResidualDispositionReason.SELECTION_ABSTAINED
    raise ValueError(f"Unsupported residual-review reason for R10: {reason}")


def dispose_residual_event(
    *,
    routing: SelectionRouting,
    composition: DecontextualizedProposition | None = None,
) -> ResidualDisposition:
    """Return one typed disposition for one Event's routing plus composer result."""
    if composition is not None and composition.event_id != routing.event_id:
        raise ValueError("Residual disposal references mismatched Events.")

    if routing.decision is SelectionRoutingDecision.RESIDUAL_REVIEW:
        return ResidualDisposition(
            event_id=routing.event_id,
            reason=_selection_reason(routing),
        )

    if routing.decision is not SelectionRoutingDecision.ACCEPTED_SELECTION:
        raise ValueError(f"Unsupported routing decision for R10: {routing.decision}")

    if composition is None:
        raise ValueError("An accepted selection requires one composition result.")
    if composition.status is DecontextualizationStatus.HELD:
        return ResidualDisposition(
            event_id=routing.event_id,
            reason=ResidualDispositionReason.COMPOSITION_HOLD,
            hold_reason=composition.hold_reason,
        )
    return ResidualDisposition(
        event_id=routing.event_id,
        reason=ResidualDispositionReason.COMPOSABLE,
        proposition=composition,
    )


def dispose_residual_set(
    *,
    routing: tuple[SelectionRouting, ...],
    compositions: Mapping[str, DecontextualizedProposition] | None = None,
) -> tuple[ResidualDisposition, ...]:
    """Return one ordered disposition per residual-review Event."""
    compositions = compositions or {}
    residual = sorted(
        (item for item in routing if item.decision is SelectionRoutingDecision.RESIDUAL_REVIEW),
        key=lambda item: item.event_id,
    )
    return tuple(
        dispose_residual_event(routing=item, composition=compositions.get(item.event_id))
        for item in residual
    )


def validate_held_safety(
    *,
    dispositions: tuple[ResidualDisposition, ...],
    residual_event_ids: tuple[str, ...],
) -> tuple[ResidualDisposition, ...]:
    """Reject a disposition set that drifts from the residual-review set."""
    ids = tuple(item.event_id for item in dispositions)
    if ids != tuple(sorted(set(ids))):
        raise ValueError("Residual dispositions must be ordered and distinct.")
    if ids != tuple(sorted(residual_event_ids)):
        raise ValueError("Residual dispositions drifted from the residual-review set.")
    return dispositions


class ResidualCompositionHoldReport(BaseModel):
    """Sealed R10 report: residual dispositions and zero-write safety."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    dispositions: tuple[ResidualDisposition, ...]
    residual_review_event_ids: tuple[str, ...]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    model_execution_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.event_id for item in self.dispositions)
        if ids != self.residual_review_event_ids:
            raise ValueError("Report dispositions drifted from the residual-review set.")
        if (
            self.canonical_write_count != 0
            or self.proposed_change_count != 0
            or self.model_execution_count != 0
        ):
            raise ValueError("R10 report must record zero writes, proposals, and model executions.")
        return self


def residual_composition_hold_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one R10 report draft."""
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


def build_residual_composition_hold_report(
    *,
    dispositions: tuple[ResidualDisposition, ...],
    residual_review_event_ids: tuple[str, ...],
) -> ResidualCompositionHoldReport:
    """Assemble and seal the R10 report with zero writes, proposals, and model executions."""
    draft = ResidualCompositionHoldReport.model_construct(
        dispositions=dispositions,
        residual_review_event_ids=residual_review_event_ids,
        canonical_write_count=0,
        proposed_change_count=0,
        model_execution_count=0,
        result_fingerprint="0" * 64,
    )
    return ResidualCompositionHoldReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=residual_composition_hold_report_fingerprint(draft),
    )