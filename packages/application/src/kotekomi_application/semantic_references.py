"""Bounded source-span coreference observations and deterministic decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Protocol, Self

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)

SEMANTIC_REFERENCE_POLICY_ID = "bounded_semantic_reference_v2"
SEMANTIC_REFERENCE_MAX_INPUT_TOKENS = 1024


class SemanticReferenceStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class SemanticReferenceReason(StrEnum):
    UNIQUE_PRECEDING_ANTECEDENT = "unique_preceding_antecedent"
    MULTIPLE_PRECEDING_ANTECEDENTS = "multiple_preceding_antecedents"
    NO_PRECEDING_ANTECEDENT = "no_preceding_antecedent"
    TARGET_CLUSTER_MISSING = "target_cluster_missing"


@dataclass(frozen=True)
class CoreferenceAntecedentInput:
    """One upstream, source-validated candidate eligible to anchor a reference."""

    source_candidate_id: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.source_candidate_id:
            raise ValueError("A coreference antecedent requires its source candidate ID.")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("A coreference antecedent requires a valid half-open range.")


@dataclass(frozen=True)
class CoreferenceInput:
    source_segment_id: str
    source_text: str
    target_start: int
    target_end: int
    antecedent_candidates: tuple[CoreferenceAntecedentInput, ...] = ()
    max_input_tokens: int = SEMANTIC_REFERENCE_MAX_INPUT_TOKENS

    def __post_init__(self) -> None:
        if not self.source_segment_id or not self.source_text:
            raise ValueError("Coreference input requires source identity and text.")
        if not (0 <= self.target_start < self.target_end <= len(self.source_text)):
            raise ValueError("Coreference target range is outside the source text.")
        if self.max_input_tokens <= 0:
            raise ValueError("Coreference token limit must be positive.")
        if (
            tuple(
                sorted(
                    self.antecedent_candidates,
                    key=lambda item: (item.start, item.end, item.source_candidate_id),
                )
            )
            != self.antecedent_candidates
        ):
            raise ValueError("Coreference antecedent candidates must use source order.")
        candidate_ids = [item.source_candidate_id for item in self.antecedent_candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("Coreference antecedent candidate IDs must be distinct.")
        for candidate in self.antecedent_candidates:
            if candidate.end > self.target_start:
                raise ValueError("Coreference antecedent candidates must precede the target.")

    @property
    def target_text(self) -> str:
        return self.source_text[self.target_start : self.target_end]


@dataclass(frozen=True)
class CoreferenceSpanProposal:
    start: int
    end: int


@dataclass(frozen=True)
class CoreferenceExecution:
    model_id: str
    model_revision: str
    resource_identity: str
    clusters: tuple[tuple[CoreferenceSpanProposal, ...], ...]
    elapsed_milliseconds: int
    raw_output: bytes

    def __post_init__(self) -> None:
        if not self.model_id or not self.model_revision or not self.resource_identity:
            raise ValueError("Coreference execution requires complete model identity.")
        if self.elapsed_milliseconds < 0:
            raise ValueError("Coreference elapsed time must be non-negative.")
        if not self.raw_output:
            raise ValueError("Coreference execution requires exact Adapter output.")


class CoreferenceProposerPort(Protocol):
    def propose(self, request: CoreferenceInput) -> CoreferenceExecution: ...


class CoreferenceTokenizer(Protocol):
    @property
    def tokenizer_id(self) -> str: ...

    def count_tokens(self, rendered_input: bytes) -> int: ...


class CoreferenceSpan(BaseModel):
    """One exact half-open source range returned by a coreference model."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^cfs_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.id != _id("cfs", self.source_segment_id, str(self.start), str(self.end), self.text):
            raise ValueError("CoreferenceSpan ID does not match its source range.")
        return self


class CoreferenceAntecedentCandidate(BaseModel):
    """One source-valid upstream candidate reconciled against model clusters."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^cfa_[a-f0-9]{24}$")]
    source_candidate_id: Annotated[str, Field(min_length=1)]
    span: CoreferenceSpan
    literal_key: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        expected = _id(
            "cfa",
            self.source_candidate_id,
            self.span.id,
            self.literal_key,
        )
        if self.id != expected:
            raise ValueError("CoreferenceAntecedentCandidate ID does not match its source.")
        return self


class CoreferenceObservation(BaseModel):
    """One fallible specialist-model observation over exact source spans."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^cfo_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    target_span: CoreferenceSpan
    clusters: tuple[tuple[CoreferenceSpan, ...], ...]
    antecedent_candidates: tuple[CoreferenceAntecedentCandidate, ...]
    model_id: Annotated[str, Field(min_length=1)]
    model_revision: Annotated[str, Field(min_length=1)]
    resource_identity: Annotated[str, Field(min_length=1)]
    tokenizer_id: Annotated[str, Field(min_length=1)]
    input_token_count: Annotated[int, Field(ge=1)]
    elapsed_milliseconds: Annotated[int, Field(ge=0)]
    raw_output_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.target_span.source_segment_id != self.source_segment_id:
            raise ValueError("Coreference target belongs to another source context.")
        if (
            tuple(
                sorted(
                    self.antecedent_candidates,
                    key=lambda item: (item.span.start, item.span.end, item.id),
                )
            )
            != self.antecedent_candidates
        ):
            raise ValueError("Coreference antecedent candidates must use source order.")
        if len({item.id for item in self.antecedent_candidates}) != len(self.antecedent_candidates):
            raise ValueError("CoreferenceObservation repeats an antecedent candidate.")
        if len({item.source_candidate_id for item in self.antecedent_candidates}) != len(
            self.antecedent_candidates
        ):
            raise ValueError("CoreferenceObservation repeats a source candidate.")
        if any(
            item.span.source_segment_id != self.source_segment_id
            or item.span.end > self.target_span.start
            for item in self.antecedent_candidates
        ):
            raise ValueError("Coreference antecedent candidate is outside its source context.")
        if any(
            span.source_segment_id != self.source_segment_id
            for cluster in self.clusters
            for span in cluster
        ):
            raise ValueError("Coreference cluster span belongs to another source context.")
        expected = _observation_id(self.model_dump(mode="json", exclude={"id"}))
        if self.id != expected:
            raise ValueError("CoreferenceObservation ID does not match its contents.")
        return self


class SemanticReferenceDecision(BaseModel):
    """KoteKomi's terminal decision for one bounded semantic reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^srd_[a-f0-9]{24}$")]
    observation_id: Annotated[str, Field(pattern=r"^cfo_[a-f0-9]{24}$")]
    target_span_id: Annotated[str, Field(pattern=r"^cfs_[a-f0-9]{24}$")]
    antecedent_span_ids: tuple[Annotated[str, Field(pattern=r"^cfs_[a-f0-9]{24}$")], ...]
    status: SemanticReferenceStatus
    reason: SemanticReferenceReason

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(set(self.antecedent_span_ids)) != len(self.antecedent_span_ids):
            raise ValueError("Semantic antecedent IDs must be distinct.")
        if self.status is SemanticReferenceStatus.RESOLVED:
            if (
                len(self.antecedent_span_ids) != 1
                or self.reason is not SemanticReferenceReason.UNIQUE_PRECEDING_ANTECEDENT
            ):
                raise ValueError("Resolved semantic reference requires one antecedent.")
        elif self.status is SemanticReferenceStatus.AMBIGUOUS:
            if (
                len(self.antecedent_span_ids) < 2
                or self.reason is not SemanticReferenceReason.MULTIPLE_PRECEDING_ANTECEDENTS
            ):
                raise ValueError("Ambiguous semantic reference requires multiple antecedents.")
        elif self.antecedent_span_ids:
            raise ValueError("Unresolved semantic reference cannot name an antecedent.")
        expected = _id(
            "srd",
            self.observation_id,
            self.target_span_id,
            self.status.value,
            self.reason.value,
            *self.antecedent_span_ids,
        )
        if self.id != expected:
            raise ValueError("SemanticReferenceDecision ID does not match its evidence.")
        return self


@dataclass(frozen=True)
class SemanticReferenceResult:
    observation: CoreferenceObservation
    decision: SemanticReferenceDecision
    trace: ExtractionStageTrace


def resolve_semantic_reference(
    request: CoreferenceInput,
    proposer: CoreferenceProposerPort,
    tokenizer: CoreferenceTokenizer,
) -> SemanticReferenceResult:
    """Validate one specialist observation and decide without inventing identity."""
    input_tokens = tokenizer.count_tokens(request.source_text.encode())
    if input_tokens > request.max_input_tokens:
        raise ValueError("Coreference input exceeds its bounded token limit.")
    execution = proposer.propose(request)
    target = _span(request, request.target_start, request.target_end)
    candidates = tuple(
        _antecedent_candidate(request, item) for item in request.antecedent_candidates
    )
    clusters = tuple(
        tuple(_span(request, item.start, item.end) for item in cluster)
        for cluster in execution.clusters
    )
    target_clusters = tuple(
        cluster for cluster in clusters if any(item.id == target.id for item in cluster)
    )
    if len(target_clusters) > 1:
        raise ValueError("Coreference output repeats the target across clusters.")
    raw_digest = hashlib.sha256(execution.raw_output).hexdigest()
    observation_payload: dict[str, JsonValue] = {
        "source_segment_id": request.source_segment_id,
        "source_text_sha256": hashlib.sha256(request.source_text.encode()).hexdigest(),
        "target_span": target.model_dump(mode="json"),
        "clusters": [[item.model_dump(mode="json") for item in cluster] for cluster in clusters],
        "antecedent_candidates": [item.model_dump(mode="json") for item in candidates],
        "model_id": execution.model_id,
        "model_revision": execution.model_revision,
        "resource_identity": execution.resource_identity,
        "tokenizer_id": tokenizer.tokenizer_id,
        "input_token_count": input_tokens,
        "elapsed_milliseconds": execution.elapsed_milliseconds,
        "raw_output_sha256": raw_digest,
    }
    observation = CoreferenceObservation(
        id=_observation_id(observation_payload),
        source_segment_id=request.source_segment_id,
        source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
        target_span=target,
        clusters=clusters,
        antecedent_candidates=candidates,
        model_id=execution.model_id,
        model_revision=execution.model_revision,
        resource_identity=execution.resource_identity,
        tokenizer_id=tokenizer.tokenizer_id,
        input_token_count=input_tokens,
        elapsed_milliseconds=execution.elapsed_milliseconds,
        raw_output_sha256=raw_digest,
    )
    status, reason, selected = _decide(target_clusters, candidates, target)
    decision_id = _id(
        "srd",
        observation.id,
        target.id,
        status.value,
        reason.value,
        *(item.id for item in selected),
    )
    decision = SemanticReferenceDecision(
        id=decision_id,
        observation_id=observation.id,
        target_span_id=target.id,
        antecedent_span_ids=tuple(item.id for item in selected),
        status=status,
        reason=reason,
    )
    trace = build_extraction_stage_trace(
        trace_run_id=f"hsq4:{observation.id}",
        ordinal=0,
        stage_id="bounded_semantic_reference",
        stage_version=SEMANTIC_REFERENCE_POLICY_ID,
        producer_id=execution.model_id,
        source_segment_id=request.source_segment_id,
        source_text_sha256=observation.source_text_sha256,
        configuration={
            "max_input_tokens": request.max_input_tokens,
            "model_revision": execution.model_revision,
            "resource_identity": execution.resource_identity,
            "tokenizer_id": tokenizer.tokenizer_id,
        },
        input_payload={
            "source_text": request.source_text,
            "target_start": request.target_start,
            "target_end": request.target_end,
            "target_text": request.target_text,
            "antecedent_candidates": [item.model_dump(mode="json") for item in candidates],
        },
        output_payload={
            "raw_output": execution.raw_output.decode("utf-8"),
            "observation": observation.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
        },
        status=ExtractionStageStatus.COMPLETED,
        input_record_ids=(target.id,),
    )
    return SemanticReferenceResult(observation, decision, trace)


def _span(request: CoreferenceInput, start: int, end: int) -> CoreferenceSpan:
    if not (0 <= start < end <= len(request.source_text)):
        raise ValueError("Coreference model returned an out-of-range source span.")
    text = request.source_text[start:end]
    return CoreferenceSpan(
        id=_id("cfs", request.source_segment_id, str(start), str(end), text),
        source_segment_id=request.source_segment_id,
        start=start,
        end=end,
        text=text,
    )


def _antecedent_candidate(
    request: CoreferenceInput,
    candidate: CoreferenceAntecedentInput,
) -> CoreferenceAntecedentCandidate:
    span = _span(request, candidate.start, candidate.end)
    literal_key = " ".join(span.text.casefold().split())
    return CoreferenceAntecedentCandidate(
        id=_id("cfa", candidate.source_candidate_id, span.id, literal_key),
        source_candidate_id=candidate.source_candidate_id,
        span=span,
        literal_key=literal_key,
    )


def _decide(
    target_clusters: tuple[tuple[CoreferenceSpan, ...], ...],
    candidates: tuple[CoreferenceAntecedentCandidate, ...],
    target: CoreferenceSpan,
) -> tuple[
    SemanticReferenceStatus,
    SemanticReferenceReason,
    tuple[CoreferenceSpan, ...],
]:
    if not target_clusters:
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.TARGET_CLUSTER_MISSING,
            (),
        )
    model_antecedents = tuple(
        item for item in target_clusters[0] if item.end <= target.start and item.id != target.id
    )
    reconciled = _reconcile_candidates(model_antecedents, candidates)
    if not reconciled:
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.NO_PRECEDING_ANTECEDENT,
            (),
        )
    by_literal: dict[str, list[CoreferenceAntecedentCandidate]] = {}
    for candidate in reconciled:
        by_literal.setdefault(candidate.literal_key, []).append(candidate)
    selected = tuple(
        max(group, key=lambda item: (item.span.end, item.span.start, item.id)).span
        for _, group in sorted(by_literal.items())
    )
    selected = tuple(sorted(selected, key=lambda item: (item.start, item.end, item.id)))
    if len(selected) > 1:
        return (
            SemanticReferenceStatus.AMBIGUOUS,
            SemanticReferenceReason.MULTIPLE_PRECEDING_ANTECEDENTS,
            selected,
        )
    return (
        SemanticReferenceStatus.RESOLVED,
        SemanticReferenceReason.UNIQUE_PRECEDING_ANTECEDENT,
        selected,
    )


def _reconcile_candidates(
    model_antecedents: tuple[CoreferenceSpan, ...],
    candidates: tuple[CoreferenceAntecedentCandidate, ...],
) -> tuple[CoreferenceAntecedentCandidate, ...]:
    """Map each fallible model mention to its best source-owned candidate boundary."""
    reconciled: dict[str, CoreferenceAntecedentCandidate] = {}
    for model_span in model_antecedents:
        ranked: list[tuple[tuple[Fraction, int, int], CoreferenceAntecedentCandidate]] = []
        for candidate in candidates:
            overlap = min(model_span.end, candidate.span.end) - max(
                model_span.start, candidate.span.start
            )
            if overlap <= 0:
                continue
            union = max(model_span.end, candidate.span.end) - min(
                model_span.start, candidate.span.start
            )
            ranked.append(
                (
                    (
                        Fraction(overlap, union),
                        overlap,
                        candidate.span.end - candidate.span.start,
                    ),
                    candidate,
                )
            )
        if not ranked:
            continue
        best_score = max(score for score, _ in ranked)
        for score, candidate in ranked:
            if score == best_score:
                reconciled[candidate.id] = candidate
    return tuple(
        sorted(reconciled.values(), key=lambda item: (item.span.start, item.span.end, item.id))
    )


def _observation_id(payload: dict[str, JsonValue]) -> str:
    return "cfo_" + hashlib.sha256(_canonical_json(payload)).hexdigest()[:24]


def _id(prefix: str, *parts: str) -> str:
    return prefix + "_" + hashlib.sha256("\0".join(parts).encode()).hexdigest()[:24]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
