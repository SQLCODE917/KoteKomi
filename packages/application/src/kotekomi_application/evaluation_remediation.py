"""Evaluation-remediation records and pure evaluator functions for the R5 deliverable.

R5 measures transfer on the held-out Anthropic/DoD partition that never informed a
Competitive Event Attachment decision. This module carries the derived evaluation
evidence only: token probability receipts, per-label Selection Scores, the closed
error-type census, and the sealed transfer report. Nothing here invokes a model,
writes canonical state, or reads the held-out partition to tune a decision.

One Held-out Event outcome is compared against Transfer Gold by exact source span for
attachment and by typed disagreement for composition. The error-type census counts
and lists every member Event per error type, allows one Event to appear in more than
one error-type member list, and records the exact-set score without gating on it.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.decontextualization_composition import (
    DecontextualizationAttributionKind,
    DecontextualizationStatus,
    DecontextualizedProposition,
)
from kotekomi_application.hybrid_event_semantics import EventModality, EventPolarity
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    selected_constituent_spans,
)
from kotekomi_application.staged_model_extraction import (
    ModelExecutionReceipt,
)

_SHA256 = r"^[a-f0-9]{64}$"
_HeldOutEventId = Annotated[str, Field(pattern=r"^AHE-[0-9]{3}$")]
_HeldOutFragmentId = Annotated[str, Field(pattern=r"^PGF-AHE-[0-9]{3}-[0-9]{2}$")]


class HeldOutErrorType(StrEnum):
    """One named way a Held-out Event outcome disagrees with Transfer Gold."""

    BOUNDARY_MISS = "boundary_miss"
    SELECTION_ERROR = "selection_error"
    COMPOSITION_HOLD = "composition_hold"
    CONTENT_ERROR = "content_error"
    ATTRIBUTION_ERROR = "attribution_error"
    POLARITY_MODALITY_ERROR = "polarity_modality_error"


class HeldOutFragmentRequirement(StrEnum):
    """Closed Transfer Gold fragment meaning vocabulary used for evaluation."""

    CORE_EVENT = "core_event"
    ATTRIBUTION = "attribution"
    NEGATION = "negation"
    MODALITY = "modality"
    PURPOSE = "purpose"
    COMPARISON = "comparison"
    TEMPORAL = "temporal"


class HeldOutGoldFragment(BaseModel):
    """One exact Transfer Gold source range plus its required Event meanings."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fragment_id: _HeldOutFragmentId
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    requirements: tuple[HeldOutFragmentRequirement, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Held-out Gold fragment range does not match its text.")
        if self.requirements != tuple(sorted(set(self.requirements), key=lambda item: item.value)):
            raise ValueError("Held-out Gold requirements must be ordered and distinct.")
        if not self.requirements:
            raise ValueError("Held-out Gold fragment requires one meaning classification.")
        return self


class HeldOutGoldEvent(BaseModel):
    """One reviewed Transfer Gold Event: its meaning and exact required fragments."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _HeldOutEventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    event_meaning: Annotated[str, Field(min_length=1)]
    fragments: tuple[HeldOutGoldFragment, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.fragments:
            raise ValueError("Held-out Gold Event requires one exact fragment.")
        if tuple(sorted(self.fragments, key=lambda item: (item.start, item.end))) != self.fragments:
            raise ValueError("Held-out Gold fragments must use source order.")
        if len({item.fragment_id for item in self.fragments}) != len(self.fragments):
            raise ValueError("Held-out Gold Event repeats a fragment ID.")
        if any(
            prior.end > current.start
            for prior, current in zip(self.fragments, self.fragments[1:], strict=False)
        ):
            raise ValueError("Held-out Gold fragments must not overlap.")
        return self


class SelectionTokenAlternative(BaseModel):
    """One unmodified runtime-reported token alternative with its log probability."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    token: Annotated[str, Field(min_length=1)]
    log_probability: float
    token_bytes: tuple[Annotated[int, Field(ge=0, le=255)], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not math.isfinite(self.log_probability) or self.log_probability > 0:
            raise ValueError("Selection token alternative log probability must be non-positive.")
        return self


class SelectionProbabilityReceipt(BaseModel):
    """One held-out selection execution with its unmodified alternative inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _HeldOutEventId
    model_execution_id: Annotated[str, Field(min_length=1)]
    alternatives: tuple[SelectionTokenAlternative, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.alternatives:
            raise ValueError("Selection Probability Receipt requires one alternative.")
        identities = tuple((item.token, item.token_bytes) for item in self.alternatives)
        if len(set(identities)) != len(identities):
            raise ValueError("Selection Probability Receipt alternatives must be distinct.")
        return self


class SelectionScore(BaseModel):
    """One allowed selection label, its first-position log probability, and censored flag."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _HeldOutEventId
    label: Annotated[str, Field(pattern=r"^(C[1-9][0-9]*|NONE)$")]
    log_probability: float | None = None
    censored: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.censored:
            if self.log_probability is not None:
                raise ValueError("A censored Selection Score cannot record a probability.")
        elif self.log_probability is None or not math.isfinite(self.log_probability):
            raise ValueError("An uncensored Selection Score requires a finite probability.")
        elif self.log_probability > 0:
            raise ValueError("An uncensored Selection Score probability must be non-positive.")
        return self


class HeldOutErrorCensus(BaseModel):
    """One closed error-type census over the Held-out partition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_count: Annotated[int, Field(ge=0)]
    boundary_miss_count: Annotated[int, Field(ge=0)]
    boundary_miss_event_ids: tuple[_HeldOutEventId, ...]
    boundary_miss_fragment_ids: tuple[_HeldOutFragmentId, ...]
    selection_error_count: Annotated[int, Field(ge=0)]
    selection_error_event_ids: tuple[_HeldOutEventId, ...]
    composition_hold_count: Annotated[int, Field(ge=0)]
    composition_hold_event_ids: tuple[_HeldOutEventId, ...]
    content_error_count: Annotated[int, Field(ge=0)]
    content_error_event_ids: tuple[_HeldOutEventId, ...]
    attribution_error_count: Annotated[int, Field(ge=0)]
    attribution_error_event_ids: tuple[_HeldOutEventId, ...]
    polarity_modality_error_count: Annotated[int, Field(ge=0)]
    polarity_modality_error_event_ids: tuple[_HeldOutEventId, ...]
    ok_count: Annotated[int, Field(ge=0)]
    ok_event_ids: tuple[_HeldOutEventId, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        pairs = (
            (self.boundary_miss_count, self.boundary_miss_event_ids),
            (self.selection_error_count, self.selection_error_event_ids),
            (self.composition_hold_count, self.composition_hold_event_ids),
            (self.content_error_count, self.content_error_event_ids),
            (self.attribution_error_count, self.attribution_error_event_ids),
            (self.polarity_modality_error_count, self.polarity_modality_error_event_ids),
            (self.ok_count, self.ok_event_ids),
        )
        for count, ids in pairs:
            if count != len(ids):
                raise ValueError("Held-out census count does not match its member list.")
            if ids != tuple(sorted(set(ids))):
                raise ValueError("Held-out census member lists must be ordered and distinct.")
        if self.boundary_miss_fragment_ids != tuple(sorted(set(self.boundary_miss_fragment_ids))):
            raise ValueError("Held-out boundary-miss fragments must be ordered and distinct.")
        if bool(self.boundary_miss_fragment_ids) != (self.boundary_miss_count > 0):
            raise ValueError("Held-out boundary-miss fragments vs count mismatch.")
        error_ids = set(self.boundary_miss_event_ids)
        error_ids.update(self.selection_error_event_ids)
        error_ids.update(self.composition_hold_event_ids)
        error_ids.update(self.content_error_event_ids)
        error_ids.update(self.attribution_error_event_ids)
        error_ids.update(self.polarity_modality_error_event_ids)
        if set(self.ok_event_ids) & error_ids:
            raise ValueError("Held-out census ok Events must not join any error member list.")
        if len(set(self.ok_event_ids) | error_ids) != self.event_count:
            raise ValueError("Held-out census Event count drifted from ok and error lists.")
        return self


class HeldOutTransferReport(BaseModel):
    """Sealed R5 transfer report: census, selection scores, and recorded-only exact-set score."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    census: HeldOutErrorCensus
    exact_set_score: Annotated[float, Field(ge=0.0, le=1.0)]
    selection_scores: tuple[SelectionScore, ...]
    model_execution_count: Annotated[int, Field(ge=0)]
    canonical_write_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.canonical_write_count != 0:
            raise ValueError("R5 report records canonical writes from a derived-only phase.")
        if self.proposed_change_count != 0:
            raise ValueError("R5 report records ProposedChanges from a derived-only phase.")
        expected = held_out_transfer_report_fingerprint(self)
        if self.result_fingerprint != expected:
            raise ValueError("R5 transfer report fingerprint does not match its contents.")
        event_ids = tuple(sorted({item.event_id for item in self.selection_scores}))
        if len(event_ids) != len({item.event_id for item in self.selection_scores}):
            raise ValueError("R5 transfer report repeats a scored Event.")
        return self


def held_out_transfer_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one Held-out transfer report draft."""
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


def build_selection_probability_receipt(
    *,
    event_id: str,
    model_execution_id: str,
    receipt: ModelExecutionReceipt,
) -> SelectionProbabilityReceipt:
    """Preserve the unmodified runtime alternative inventory at the first answer position."""
    if not receipt.output_token_probabilities:
        raise ValueError("Selection Probability Receipt requires output token probabilities.")
    first = receipt.output_token_probabilities[0]
    if first.position != 0:
        raise ValueError("Selection Probability Receipt requires token position zero.")
    alternatives = tuple(
        SelectionTokenAlternative(
            token=item.token,
            log_probability=item.log_probability,
            token_bytes=item.token_bytes,
        )
        for item in first.alternatives
    )
    return SelectionProbabilityReceipt(
        event_id=event_id,
        model_execution_id=model_execution_id,
        alternatives=alternatives,
    )


def build_selection_scores(
    *,
    event_id: str,
    allowed_labels: tuple[str, ...],
    receipt: SelectionProbabilityReceipt,
) -> tuple[SelectionScore, ...]:
    """Record one first-position log probability per allowed label, censoring misses."""
    if receipt.event_id != event_id:
        raise ValueError("Selection scores reference a mismatched Event.")
    if allowed_labels != tuple(sorted(set(allowed_labels), key=_label_ordinal)):
        raise ValueError("Allowed selection labels must be ordered and distinct.")
    closest: dict[str, float] = {}
    for item in receipt.alternatives:
        label = item.token.strip()
        if label not in closest:
            closest[label] = item.log_probability
    return tuple(
        SelectionScore(
            event_id=event_id,
            label=label,
            log_probability=(closest[label] if label in closest else None),
            censored=label not in closest,
        )
        for label in allowed_labels
    )


def build_held_out_exact_set_score(
    *,
    events: Mapping[str, HeldOutGoldEvent],
    inventories: Mapping[str, ConstituentCandidateInventory],
    answers: Mapping[str, ConstituentSelectionAnswer],
) -> float:
    """Record-only exact-set attachment score; never gates acceptance."""
    if not events:
        return 0.0
    exact = 0
    for event_id in sorted(events):
        gold_spans = {(item.start, item.end) for item in events[event_id].fragments}
        selected = {
            (item.start, item.end)
            for item in selected_constituent_spans(
                answer=answers[event_id], inventory=inventories[event_id]
            )
        }
        if selected == gold_spans:
            exact += 1
    return exact / len(events)


def build_held_out_error_census(
    *,
    events: Mapping[str, HeldOutGoldEvent],
    inventories: Mapping[str, ConstituentCandidateInventory],
    answers: Mapping[str, ConstituentSelectionAnswer],
    propositions: Mapping[str, DecontextualizedProposition],
) -> HeldOutErrorCensus:
    """Score one error type (or `ok`) per Held-out Event against frozen Transfer Gold."""
    _require_shared_keys(events, inventories, answers, propositions)
    members: dict[HeldOutErrorType, list[str]] = {item: [] for item in HeldOutErrorType}
    boundary_miss_fragments: list[str] = []
    for event_id in sorted(events):
        error_types, missed_fragment_ids = _evaluate_event(
            gold=events[event_id],
            inventory=inventories[event_id],
            answer=answers[event_id],
            proposition=propositions[event_id],
        )
        boundary_miss_fragments.extend(missed_fragment_ids)
        for error_type in error_types:
            members[error_type].append(event_id)
    ok_events = sorted(
        event_id for event_id in events if all(event_id not in members[item] for item in members)
    )
    return HeldOutErrorCensus(
        event_count=len(events),
        boundary_miss_count=len(members[HeldOutErrorType.BOUNDARY_MISS]),
        boundary_miss_event_ids=tuple(members[HeldOutErrorType.BOUNDARY_MISS]),
        boundary_miss_fragment_ids=tuple(sorted(set(boundary_miss_fragments))),
        selection_error_count=len(members[HeldOutErrorType.SELECTION_ERROR]),
        selection_error_event_ids=tuple(members[HeldOutErrorType.SELECTION_ERROR]),
        composition_hold_count=len(members[HeldOutErrorType.COMPOSITION_HOLD]),
        composition_hold_event_ids=tuple(members[HeldOutErrorType.COMPOSITION_HOLD]),
        content_error_count=len(members[HeldOutErrorType.CONTENT_ERROR]),
        content_error_event_ids=tuple(members[HeldOutErrorType.CONTENT_ERROR]),
        attribution_error_count=len(members[HeldOutErrorType.ATTRIBUTION_ERROR]),
        attribution_error_event_ids=tuple(members[HeldOutErrorType.ATTRIBUTION_ERROR]),
        polarity_modality_error_count=len(members[HeldOutErrorType.POLARITY_MODALITY_ERROR]),
        polarity_modality_error_event_ids=tuple(members[HeldOutErrorType.POLARITY_MODALITY_ERROR]),
        ok_count=len(ok_events),
        ok_event_ids=tuple(ok_events),
    )


def build_held_out_transfer_report(
    *,
    census: HeldOutErrorCensus,
    exact_set_score: float,
    selection_scores: tuple[SelectionScore, ...],
    model_execution_count: int,
) -> HeldOutTransferReport:
    """Assemble and seal the R5 transfer report with zero canonical writes."""
    draft = HeldOutTransferReport.model_construct(
        census=census,
        exact_set_score=exact_set_score,
        selection_scores=selection_scores,
        model_execution_count=model_execution_count,
        canonical_write_count=0,
        proposed_change_count=0,
        result_fingerprint="0" * 64,
    )
    return HeldOutTransferReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=held_out_transfer_report_fingerprint(draft),
    )


def _evaluate_event(
    *,
    gold: HeldOutGoldEvent,
    inventory: ConstituentCandidateInventory,
    answer: ConstituentSelectionAnswer,
    proposition: DecontextualizedProposition,
) -> tuple[tuple[HeldOutErrorType, ...], tuple[str, ...]]:
    """Return one Event's error-types and its boundary-miss fragment IDs."""
    error_types: set[HeldOutErrorType] = set()
    gold_spans = {(item.start, item.end) for item in gold.fragments}
    inventory_spans = {
        (item.constituent_range.start, item.constituent_range.end)
        for item in inventory.constituents
    }
    missed_fragment_ids = tuple(
        sorted(
            item.fragment_id
            for item in gold.fragments
            if (item.start, item.end) not in inventory_spans
        )
    )
    if missed_fragment_ids:
        error_types.add(HeldOutErrorType.BOUNDARY_MISS)

    selected = {
        (item.start, item.end)
        for item in selected_constituent_spans(answer=answer, inventory=inventory)
    }
    covered_unselected = any(
        (item.start, item.end) in inventory_spans and (item.start, item.end) not in selected
        for item in gold.fragments
    )
    false_selection = any(span not in gold_spans for span in selected)
    if covered_unselected or false_selection:
        error_types.add(HeldOutErrorType.SELECTION_ERROR)

    if proposition.status is DecontextualizationStatus.HELD:
        if any(
            HeldOutFragmentRequirement.CORE_EVENT in item.requirements for item in gold.fragments
        ):
            error_types.add(HeldOutErrorType.COMPOSITION_HOLD)
    else:
        subject_ok = proposition.subject is not None and _span_covered(
            proposition.subject.exact_fragment.start,
            proposition.subject.exact_fragment.end,
            gold.fragments,
        )
        object_ok = True
        if proposition.object is not None:
            object_ok = _span_covered(
                proposition.object.exact_fragment.start,
                proposition.object.exact_fragment.end,
                gold.fragments,
            )
        if not subject_ok or not object_ok:
            error_types.add(HeldOutErrorType.CONTENT_ERROR)

        attributed = tuple(
            item
            for item in gold.fragments
            if HeldOutFragmentRequirement.ATTRIBUTION in item.requirements
        )
        composed_targeted = (
            proposition.attribution is not None
            and proposition.attribution.kind is DecontextualizationAttributionKind.TARGETED
        )
        attribution_ok = bool(attributed) == composed_targeted
        if attribution_ok and composed_targeted:
            carrier = proposition.attribution.exact_carrier if proposition.attribution else None
            attribution_ok = carrier is not None and _span_covered(
                carrier.start, carrier.end, attributed
            )
        if not attribution_ok:
            error_types.add(HeldOutErrorType.ATTRIBUTION_ERROR)

        gold_negated = any(
            HeldOutFragmentRequirement.NEGATION in item.requirements for item in gold.fragments
        )
        gold_modal = any(
            HeldOutFragmentRequirement.MODALITY in item.requirements for item in gold.fragments
        )
        polarity_ok = (proposition.polarity is EventPolarity.NEGATED) == gold_negated
        modality_ok = (proposition.modality is not EventModality.ACTUAL) == gold_modal
        if not polarity_ok or not modality_ok:
            error_types.add(HeldOutErrorType.POLARITY_MODALITY_ERROR)

    return tuple(sorted(error_types, key=lambda item: item.value)), missed_fragment_ids


def _require_shared_keys(
    events: Mapping[str, object],
    inventories: Mapping[str, object],
    answers: Mapping[str, object],
    propositions: Mapping[str, object],
) -> None:
    keys = set(events)
    if keys != set(inventories) or keys != set(answers) or keys != set(propositions):
        raise ValueError("Held-out census requires one Event entry per input mapping.")


def _span_covered(start: int, end: int, fragments: tuple[HeldOutGoldFragment, ...]) -> bool:
    return any(item.start <= start and end <= item.end for item in fragments)


def _label_ordinal(label: str) -> tuple[int, int]:
    if label == "NONE":
        return (10**9, 0)
    return (0, int(label.removeprefix("C")))
