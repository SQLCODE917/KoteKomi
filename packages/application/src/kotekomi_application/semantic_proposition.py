"""Typed complete-proposition and independent NLI evidence contracts."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PropositionKind(StrEnum):
    EVENT = "event"
    STANDING_ASSERTION = "standing_assertion"


class NliLabel(StrEnum):
    CONTRADICTION = "contradiction"
    ENTAILMENT = "entailment"
    NEUTRAL = "neutral"


class PropositionDisposition(StrEnum):
    SUPPORTED = "supported"
    HELD = "held"


class PropositionHoldReason(StrEnum):
    NLI_CONTRADICTION = "nli_contradiction"
    NLI_LOW_CONFIDENCE = "nli_low_confidence"
    NLI_NEUTRAL = "nli_neutral"
    NLI_UNAVAILABLE = "nli_unavailable"
    QWEN_NON_DIRECT_SUPPORT = "qwen_non_direct_support"
    QWEN_UNAVAILABLE = "qwen_unavailable"


@dataclass(frozen=True)
class NaturalLanguageInferenceInput:
    premise: str
    hypothesis: str

    def __post_init__(self) -> None:
        if not self.premise or not self.hypothesis:
            raise ValueError("NLI premise and hypothesis must be non-empty.")


@dataclass(frozen=True)
class NaturalLanguageInferenceExecution:
    model_id: str
    model_revision: str
    resource_identity: str
    contradiction_score: float
    entailment_score: float
    neutral_score: float
    elapsed_milliseconds: int

    def __post_init__(self) -> None:
        if not self.model_id or not self.model_revision or not self.resource_identity:
            raise ValueError("NLI execution requires complete model identity.")
        scores = (self.contradiction_score, self.entailment_score, self.neutral_score)
        if any(not math.isfinite(item) or item < 0 or item > 1 for item in scores):
            raise ValueError("NLI execution scores must be finite probabilities.")
        if not math.isclose(sum(scores), 1.0, rel_tol=0, abs_tol=1e-5):
            raise ValueError("NLI execution scores must sum to one.")
        if self.elapsed_milliseconds < 0:
            raise ValueError("NLI execution elapsed time must be non-negative.")

    @property
    def selected_label(self) -> NliLabel:
        values = {
            NliLabel.CONTRADICTION: self.contradiction_score,
            NliLabel.ENTAILMENT: self.entailment_score,
            NliLabel.NEUTRAL: self.neutral_score,
        }
        return max(values, key=values.__getitem__)


class NaturalLanguageInferencePort(Protocol):
    def classify(
        self, request: NaturalLanguageInferenceInput
    ) -> NaturalLanguageInferenceExecution: ...


class CompleteProposition(BaseModel):
    """One deterministic complete meaning submitted for source-support review."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["complete_proposition_v1"] = "complete_proposition_v1"
    id: Annotated[str, Field(pattern=r"^cpr_[a-f0-9]{24}$")]
    kind: PropositionKind
    subject_record_id: Annotated[str, Field(min_length=1)]
    text: Annotated[str, Field(min_length=1)]
    evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.text != self.text.strip() or "\n" in self.text or "\r" in self.text:
            raise ValueError("Complete proposition text must be one trimmed line.")
        if self.id != complete_proposition_id(
            kind=self.kind,
            subject_record_id=self.subject_record_id,
            text=self.text,
            evidence_target_id=self.evidence_target_id,
        ):
            raise ValueError("CompleteProposition ID does not match its contents.")
        return self


class NliObservation(BaseModel):
    """One fallible specialist observation over one CompleteProposition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["nli_observation_v1"] = "nli_observation_v1"
    id: Annotated[str, Field(pattern=r"^nlo_[a-f0-9]{24}$")]
    proposition_id: Annotated[str, Field(pattern=r"^cpr_[a-f0-9]{24}$")]
    premise_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    hypothesis_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    model_id: Annotated[str, Field(min_length=1)]
    model_revision: Annotated[str, Field(min_length=1)]
    resource_identity: Annotated[str, Field(min_length=1)]
    contradiction_score: Annotated[float, Field(ge=0, le=1)]
    entailment_score: Annotated[float, Field(ge=0, le=1)]
    neutral_score: Annotated[float, Field(ge=0, le=1)]
    selected_label: NliLabel
    elapsed_milliseconds: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        execution = NaturalLanguageInferenceExecution(
            model_id=self.model_id,
            model_revision=self.model_revision,
            resource_identity=self.resource_identity,
            contradiction_score=self.contradiction_score,
            entailment_score=self.entailment_score,
            neutral_score=self.neutral_score,
            elapsed_milliseconds=self.elapsed_milliseconds,
        )
        if self.selected_label is not execution.selected_label:
            raise ValueError("NLI selected label does not match its scores.")
        if self.id != nli_observation_id(
            proposition_id=self.proposition_id,
            premise_sha256=self.premise_sha256,
            hypothesis_sha256=self.hypothesis_sha256,
            execution=execution,
        ):
            raise ValueError("NliObservation ID does not match its contents.")
        return self


class PropositionDecision(BaseModel):
    """KoteKomi's admission decision over Qwen and NLI evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["proposition_decision_v1"] = "proposition_decision_v1"
    id: Annotated[str, Field(pattern=r"^pdc_[a-f0-9]{24}$")]
    proposition_id: Annotated[str, Field(pattern=r"^cpr_[a-f0-9]{24}$")]
    qwen_judgment_id: Annotated[str, Field(pattern=r"^spj_[a-f0-9]{24}$")] | None
    nli_observation_id: Annotated[str, Field(pattern=r"^nlo_[a-f0-9]{24}$")] | None
    disposition: PropositionDisposition
    hold_reason: PropositionHoldReason | None
    entailment_threshold: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.disposition is PropositionDisposition.SUPPORTED:
            if self.hold_reason is not None or self.nli_observation_id is None:
                raise ValueError("A supported proposition requires complete evidence.")
        elif self.hold_reason is None:
            raise ValueError("A held proposition requires a reason.")
        expected = _id(
            "pdc",
            self.proposition_id,
            self.qwen_judgment_id or "",
            self.nli_observation_id or "",
            self.disposition.value,
            self.hold_reason.value if self.hold_reason else "",
            format(self.entailment_threshold, ".8f"),
        )
        if self.id != expected:
            raise ValueError("PropositionDecision ID does not match its contents.")
        return self


def complete_proposition_id(
    *, kind: PropositionKind, subject_record_id: str, text: str, evidence_target_id: str
) -> str:
    return _id("cpr", kind.value, subject_record_id, text, evidence_target_id)


def build_complete_proposition(
    *, kind: PropositionKind, subject_record_id: str, text: str, evidence_target_id: str
) -> CompleteProposition:
    return CompleteProposition(
        id=complete_proposition_id(
            kind=kind,
            subject_record_id=subject_record_id,
            text=text,
            evidence_target_id=evidence_target_id,
        ),
        kind=kind,
        subject_record_id=subject_record_id,
        text=text,
        evidence_target_id=evidence_target_id,
    )


def build_nli_observation(
    *,
    proposition_id: str,
    premise: str,
    hypothesis: str,
    execution: NaturalLanguageInferenceExecution,
) -> NliObservation:
    premise_digest = hashlib.sha256(premise.encode()).hexdigest()
    hypothesis_digest = hashlib.sha256(hypothesis.encode()).hexdigest()
    return NliObservation(
        id=nli_observation_id(
            proposition_id=proposition_id,
            premise_sha256=premise_digest,
            hypothesis_sha256=hypothesis_digest,
            execution=execution,
        ),
        proposition_id=proposition_id,
        premise_sha256=premise_digest,
        hypothesis_sha256=hypothesis_digest,
        model_id=execution.model_id,
        model_revision=execution.model_revision,
        resource_identity=execution.resource_identity,
        contradiction_score=execution.contradiction_score,
        entailment_score=execution.entailment_score,
        neutral_score=execution.neutral_score,
        selected_label=execution.selected_label,
        elapsed_milliseconds=execution.elapsed_milliseconds,
    )


def nli_observation_id(
    *,
    proposition_id: str,
    premise_sha256: str,
    hypothesis_sha256: str,
    execution: NaturalLanguageInferenceExecution,
) -> str:
    return _id(
        "nlo",
        proposition_id,
        premise_sha256,
        hypothesis_sha256,
        execution.model_id,
        execution.model_revision,
        execution.resource_identity,
        format(execution.contradiction_score, ".8f"),
        format(execution.entailment_score, ".8f"),
        format(execution.neutral_score, ".8f"),
        str(execution.elapsed_milliseconds),
    )


def build_proposition_decision(
    *,
    proposition_id: str,
    qwen_judgment_id: str | None,
    nli_observation: NliObservation | None,
    qwen_directly_supported: bool | None,
    entailment_threshold: float,
) -> PropositionDecision:
    disposition = PropositionDisposition.HELD
    reason: PropositionHoldReason | None = PropositionHoldReason.QWEN_UNAVAILABLE
    if qwen_directly_supported is False:
        reason = PropositionHoldReason.QWEN_NON_DIRECT_SUPPORT
    elif qwen_directly_supported:
        if nli_observation is None:
            reason = PropositionHoldReason.NLI_UNAVAILABLE
        elif nli_observation.selected_label is NliLabel.CONTRADICTION:
            reason = PropositionHoldReason.NLI_CONTRADICTION
        elif nli_observation.selected_label is NliLabel.NEUTRAL:
            reason = PropositionHoldReason.NLI_NEUTRAL
        elif nli_observation.entailment_score < entailment_threshold:
            reason = PropositionHoldReason.NLI_LOW_CONFIDENCE
        else:
            disposition = PropositionDisposition.SUPPORTED
            reason = None
    identifier = _id(
        "pdc",
        proposition_id,
        qwen_judgment_id or "",
        nli_observation.id if nli_observation else "",
        disposition.value,
        reason.value if reason else "",
        format(entailment_threshold, ".8f"),
    )
    return PropositionDecision(
        id=identifier,
        proposition_id=proposition_id,
        qwen_judgment_id=qwen_judgment_id,
        nli_observation_id=nli_observation.id if nli_observation else None,
        disposition=disposition,
        hold_reason=reason,
        entailment_threshold=entailment_threshold,
    )


def canonical_complete_proposition_bytes(proposition: CompleteProposition) -> bytes:
    return _canonical_bytes(proposition)


def _canonical_bytes(value: BaseModel) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    ).encode()


def _id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode()
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"
