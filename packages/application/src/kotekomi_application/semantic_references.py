"""Bounded source-span coreference observations and deterministic decisions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Protocol, Self

from kotekomi_domain import ModelRunStatus
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.semantic_reference_challenge_model_output import (
    SemanticReferenceChallengeSelection,
)
from kotekomi_application.semantic_reference_validation_model_output import (
    SemanticReferenceCandidateValidation,
    SemanticReferenceCandidateVerdict,
)

SEMANTIC_REFERENCE_POLICY_ID = "bounded_semantic_reference_v11"
SEMANTIC_REFERENCE_MAX_INPUT_TOKENS = 1024
SEMANTIC_REFERENCE_MAX_ANTECEDENT_CANDIDATES = 8
_ANTECEDENT_LABEL_PATTERN = re.compile(r"a[1-9][0-9]*")


class SemanticReferenceStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class SemanticReferenceReason(StrEnum):
    CHALLENGE_SELECTED_ANTECEDENT = "challenge_selected_antecedent"
    CHALLENGE_AMBIGUOUS = "challenge_ambiguous"
    CHALLENGE_UNRESOLVED = "challenge_unresolved"
    CHALLENGE_FAILED = "challenge_failed"
    CHALLENGE_INVALID = "challenge_invalid"
    SPECIALIST_CHALLENGE_DISAGREEMENT = "specialist_challenge_disagreement"
    SPECIALIST_VALIDATION_SUPPORTED = "specialist_validation_supported"
    SPECIALIST_VALIDATION_UNSUPPORTED = "specialist_validation_unsupported"
    SPECIALIST_VALIDATION_UNCLEAR = "specialist_validation_unclear"
    SPECIALIST_VALIDATION_FAILED = "specialist_validation_failed"
    SPECIALIST_VALIDATION_INVALID = "specialist_validation_invalid"
    SPECIALIST_CONTRASTIVE_CONFIRMATION = "specialist_contrastive_confirmation"
    SPECIALIST_REJECTED_CONTRASTIVE_SELECTION = "specialist_rejected_contrastive_selection"
    SPECIALIST_NO_ANTECEDENT = "specialist_no_antecedent"
    SPECIALIST_TARGET_CLUSTER_MISSING = "specialist_target_cluster_missing"


class SemanticReferenceModelTask(StrEnum):
    SPECIALIST_VALIDATION = "specialist_validation"
    CONTRASTIVE_SELECTION = "contrastive_selection"
    CATALOG_SELECTION = "catalog_selection"


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


@dataclass(frozen=True)
class SemanticReferenceChallengeInput:
    source_segment_id: str
    source_text: str
    target_span: CoreferenceSpan
    antecedent_candidates: tuple[CoreferenceAntecedentCandidate, ...]
    mode: SemanticReferenceModelTask = SemanticReferenceModelTask.CATALOG_SELECTION

    def __post_init__(self) -> None:
        if not self.antecedent_candidates:
            raise ValueError("A semantic-reference challenge requires source-valid candidates.")
        if len(self.antecedent_candidates) > SEMANTIC_REFERENCE_MAX_ANTECEDENT_CANDIDATES:
            raise ValueError("A semantic-reference challenge exceeds its candidate limit.")
        if self.mode not in {
            SemanticReferenceModelTask.CONTRASTIVE_SELECTION,
            SemanticReferenceModelTask.CATALOG_SELECTION,
        }:
            raise ValueError("A semantic-reference selection requires a selection task mode.")
        _validate_model_task_source(
            self.source_segment_id,
            self.source_text,
            self.target_span,
            self.antecedent_candidates,
        )


@dataclass(frozen=True)
class SemanticReferenceCandidateValidationInput:
    source_segment_id: str
    source_text: str
    target_span: CoreferenceSpan
    antecedent_candidate: CoreferenceAntecedentCandidate

    def __post_init__(self) -> None:
        _validate_model_task_source(
            self.source_segment_id,
            self.source_text,
            self.target_span,
            (self.antecedent_candidate,),
        )


def _validate_model_task_source(
    source_segment_id: str,
    source_text: str,
    target_span: CoreferenceSpan,
    candidates: tuple[CoreferenceAntecedentCandidate, ...],
) -> None:
    if (
        not source_segment_id
        or not source_text
        or target_span.source_segment_id != source_segment_id
        or target_span.end > len(source_text)
        or source_text[target_span.start : target_span.end] != target_span.text
    ):
        raise ValueError("A semantic-reference model task requires its exact target source text.")
    if len({item.id for item in candidates}) != len(candidates) or any(
        item.span.source_segment_id != source_segment_id
        or item.span.end > target_span.start
        or item.span.end > len(source_text)
        or source_text[item.span.start : item.span.end] != item.span.text
        for item in candidates
    ):
        raise ValueError(
            "A semantic-reference model task requires distinct preceding source-valid candidates."
        )


@dataclass(frozen=True)
class SemanticReferenceCandidateLabelBinding:
    """One task-local model label bound to a source-valid antecedent candidate."""

    label: str
    candidate_id: str

    def __post_init__(self) -> None:
        if _ANTECEDENT_LABEL_PATTERN.fullmatch(self.label) is None:
            raise ValueError("A semantic-reference candidate binding requires an aN label.")
        if not self.candidate_id:
            raise ValueError("A semantic-reference candidate binding requires a candidate ID.")


@dataclass(frozen=True)
class SemanticReferenceChallengeExecution:
    selection: SemanticReferenceChallengeSelection | None
    candidate_label_bindings: tuple[SemanticReferenceCandidateLabelBinding, ...]
    extraction_task_id: str
    model_run_id: str
    model_status: ModelRunStatus
    producer_id: str
    model_visible_task: bytes
    raw_output_sha256: str | None
    mode: SemanticReferenceModelTask = SemanticReferenceModelTask.CATALOG_SELECTION

    def __post_init__(self) -> None:
        if not self.extraction_task_id or not self.model_run_id or not self.producer_id:
            raise ValueError("A semantic-reference challenge requires execution identity.")
        if not self.model_visible_task:
            raise ValueError(
                "A semantic-reference challenge requires exact model-visible task data."
            )
        labels = tuple(item.label for item in self.candidate_label_bindings)
        candidate_ids = tuple(item.candidate_id for item in self.candidate_label_bindings)
        if (
            not labels
            or labels != tuple(f"a{ordinal}" for ordinal in range(1, len(labels) + 1))
            or len(set(candidate_ids)) != len(candidate_ids)
        ):
            raise ValueError(
                "A semantic-reference challenge requires ordered, distinct "
                "candidate-label bindings."
            )
        if self.mode not in {
            SemanticReferenceModelTask.CONTRASTIVE_SELECTION,
            SemanticReferenceModelTask.CATALOG_SELECTION,
        }:
            raise ValueError("A semantic-reference selection execution requires a selection mode.")


@dataclass(frozen=True)
class SemanticReferenceCandidateValidationExecution:
    validation: SemanticReferenceCandidateValidation | None
    candidate_id: str
    extraction_task_id: str
    model_run_id: str
    model_status: ModelRunStatus
    producer_id: str
    model_visible_task: bytes
    raw_output_sha256: str | None

    def __post_init__(self) -> None:
        if not all(
            (
                self.candidate_id,
                self.extraction_task_id,
                self.model_run_id,
                self.producer_id,
                self.model_visible_task,
            )
        ):
            raise ValueError(
                "A reference-candidate validation requires candidate and execution identity."
            )


class SemanticReferenceChallengerPort(Protocol):
    def validate(
        self, request: SemanticReferenceCandidateValidationInput
    ) -> SemanticReferenceCandidateValidationExecution: ...

    def challenge(
        self, request: SemanticReferenceChallengeInput
    ) -> SemanticReferenceChallengeExecution: ...


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
    specialist_proposed_antecedent_candidate_ids: tuple[
        Annotated[str, Field(pattern=r"^cfa_[a-f0-9]{24}$")], ...
    ]
    challenge_antecedent_candidate_ids: tuple[
        Annotated[str, Field(pattern=r"^cfa_[a-f0-9]{24}$")], ...
    ]
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
        candidate_ids = {item.id for item in self.antecedent_candidates}
        for label, values in (
            (
                "specialist proposed antecedents",
                self.specialist_proposed_antecedent_candidate_ids,
            ),
            ("challenge antecedents", self.challenge_antecedent_candidate_ids),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"CoreferenceObservation repeats {label}.")
            if not set(values).issubset(candidate_ids):
                raise ValueError(f"CoreferenceObservation contains unknown {label}.")
        if len(self.challenge_antecedent_candidate_ids) > (
            SEMANTIC_REFERENCE_MAX_ANTECEDENT_CANDIDATES
        ):
            raise ValueError("CoreferenceObservation exceeds the antecedent challenge limit.")
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


class SemanticReferenceModelExecutionReference(BaseModel):
    """One model task/run pair retained in causal decision order."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task: SemanticReferenceModelTask
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]


class SemanticReferenceDecision(BaseModel):
    """KoteKomi's terminal decision for one bounded semantic reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^srd_[a-f0-9]{24}$")]
    observation_id: Annotated[str, Field(pattern=r"^cfo_[a-f0-9]{24}$")]
    target_span_id: Annotated[str, Field(pattern=r"^cfs_[a-f0-9]{24}$")]
    antecedent_span_ids: tuple[Annotated[str, Field(pattern=r"^cfs_[a-f0-9]{24}$")], ...]
    status: SemanticReferenceStatus
    reason: SemanticReferenceReason
    model_executions: tuple[SemanticReferenceModelExecutionReference, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(set(self.antecedent_span_ids)) != len(self.antecedent_span_ids):
            raise ValueError("Semantic antecedent IDs must be distinct.")
        if self.status is SemanticReferenceStatus.RESOLVED:
            if len(self.antecedent_span_ids) != 1 or self.reason not in {
                SemanticReferenceReason.CHALLENGE_SELECTED_ANTECEDENT,
                SemanticReferenceReason.SPECIALIST_VALIDATION_SUPPORTED,
                SemanticReferenceReason.SPECIALIST_CONTRASTIVE_CONFIRMATION,
                SemanticReferenceReason.SPECIALIST_REJECTED_CONTRASTIVE_SELECTION,
            }:
                raise ValueError("Resolved semantic reference requires one antecedent.")
        elif self.status is SemanticReferenceStatus.AMBIGUOUS:
            if len(self.antecedent_span_ids) < 2 or self.reason not in {
                SemanticReferenceReason.CHALLENGE_AMBIGUOUS,
                SemanticReferenceReason.SPECIALIST_CHALLENGE_DISAGREEMENT,
            }:
                raise ValueError("Ambiguous semantic reference requires multiple antecedents.")
        elif self.antecedent_span_ids:
            raise ValueError("Unresolved semantic reference cannot name an antecedent.")
        execution_pairs = tuple(
            (item.extraction_task_id, item.model_run_id) for item in self.model_executions
        )
        if len(set(execution_pairs)) != len(execution_pairs):
            raise ValueError("Semantic reference model executions must be distinct.")
        execution_modes = tuple(item.task for item in self.model_executions)
        allowed_execution_modes = {
            (),
            (SemanticReferenceModelTask.SPECIALIST_VALIDATION,),
            (
                SemanticReferenceModelTask.SPECIALIST_VALIDATION,
                SemanticReferenceModelTask.CONTRASTIVE_SELECTION,
            ),
            (SemanticReferenceModelTask.CATALOG_SELECTION,),
        }
        if execution_modes not in allowed_execution_modes:
            raise ValueError("Semantic reference model executions are not in causal task order.")
        if self.reason in {
            SemanticReferenceReason.SPECIALIST_CONTRASTIVE_CONFIRMATION,
            SemanticReferenceReason.SPECIALIST_REJECTED_CONTRASTIVE_SELECTION,
        } and execution_modes != (
            SemanticReferenceModelTask.SPECIALIST_VALIDATION,
            SemanticReferenceModelTask.CONTRASTIVE_SELECTION,
        ):
            raise ValueError("A specialist contrastive decision requires both causal model tasks.")
        if (
            self.reason
            in {
                SemanticReferenceReason.CHALLENGE_SELECTED_ANTECEDENT,
                SemanticReferenceReason.CHALLENGE_AMBIGUOUS,
                SemanticReferenceReason.CHALLENGE_UNRESOLVED,
                SemanticReferenceReason.CHALLENGE_FAILED,
                SemanticReferenceReason.CHALLENGE_INVALID,
                SemanticReferenceReason.SPECIALIST_CHALLENGE_DISAGREEMENT,
                SemanticReferenceReason.SPECIALIST_VALIDATION_SUPPORTED,
                SemanticReferenceReason.SPECIALIST_CONTRASTIVE_CONFIRMATION,
                SemanticReferenceReason.SPECIALIST_REJECTED_CONTRASTIVE_SELECTION,
                SemanticReferenceReason.SPECIALIST_VALIDATION_UNSUPPORTED,
                SemanticReferenceReason.SPECIALIST_VALIDATION_UNCLEAR,
                SemanticReferenceReason.SPECIALIST_VALIDATION_FAILED,
                SemanticReferenceReason.SPECIALIST_VALIDATION_INVALID,
            }
            and not self.model_executions
        ):
            raise ValueError("A challenge decision requires its model execution identity.")
        expected = _id(
            "srd",
            self.observation_id,
            self.target_span_id,
            self.status.value,
            self.reason.value,
            *(
                f"{item.task.value}:{item.extraction_task_id}:{item.model_run_id}"
                for item in self.model_executions
            ),
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


type SemanticReferenceModelExecution = (
    SemanticReferenceCandidateValidationExecution | SemanticReferenceChallengeExecution
)


def resolve_semantic_reference(
    request: CoreferenceInput,
    proposer: CoreferenceProposerPort,
    tokenizer: CoreferenceTokenizer,
    challenger: SemanticReferenceChallengerPort,
) -> SemanticReferenceResult:
    """Use F-Coref to propose and a bounded semantic task to decide."""
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
    specialist_proposed, specialist_reason = _specialist_candidates(
        target_clusters,
        candidates,
        target,
    )
    challenge_candidates = _monotonic_candidate_union(specialist_proposed, candidates)
    raw_digest = hashlib.sha256(execution.raw_output).hexdigest()
    observation_payload: dict[str, JsonValue] = {
        "source_segment_id": request.source_segment_id,
        "source_text_sha256": hashlib.sha256(request.source_text.encode()).hexdigest(),
        "target_span": target.model_dump(mode="json"),
        "clusters": [[item.model_dump(mode="json") for item in cluster] for cluster in clusters],
        "antecedent_candidates": [item.model_dump(mode="json") for item in candidates],
        "specialist_proposed_antecedent_candidate_ids": [item.id for item in specialist_proposed],
        "challenge_antecedent_candidate_ids": [item.id for item in challenge_candidates],
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
        specialist_proposed_antecedent_candidate_ids=tuple(item.id for item in specialist_proposed),
        challenge_antecedent_candidate_ids=tuple(item.id for item in challenge_candidates),
        model_id=execution.model_id,
        model_revision=execution.model_revision,
        resource_identity=execution.resource_identity,
        tokenizer_id=tokenizer.tokenizer_id,
        input_token_count=input_tokens,
        elapsed_milliseconds=execution.elapsed_milliseconds,
        raw_output_sha256=raw_digest,
    )
    model_executions: list[SemanticReferenceModelExecution] = []
    selected: tuple[CoreferenceSpan, ...] = ()
    if not challenge_candidates:
        status = SemanticReferenceStatus.UNRESOLVED
        reason = specialist_reason
    elif len(specialist_proposed) == 1:
        specialist_candidate = specialist_proposed[0]
        validation_execution = challenger.validate(
            SemanticReferenceCandidateValidationInput(
                source_segment_id=request.source_segment_id,
                source_text=request.source_text,
                target_span=target,
                antecedent_candidate=specialist_candidate,
            )
        )
        model_executions.append(validation_execution)
        status, reason, selected = _candidate_validation_decision(
            specialist_candidate,
            validation_execution,
        )
        validation_reason = reason
        if reason in {
            SemanticReferenceReason.SPECIALIST_VALIDATION_UNSUPPORTED,
            SemanticReferenceReason.SPECIALIST_VALIDATION_UNCLEAR,
        }:
            if len(challenge_candidates) > 1:
                contrastive_execution = challenger.challenge(
                    SemanticReferenceChallengeInput(
                        source_segment_id=request.source_segment_id,
                        source_text=request.source_text,
                        target_span=target,
                        antecedent_candidates=challenge_candidates,
                        mode=SemanticReferenceModelTask.CONTRASTIVE_SELECTION,
                    )
                )
                model_executions.append(contrastive_execution)
                status, reason, selected = _challenge_decision(
                    challenge_candidates,
                    contrastive_execution,
                )
                status, reason, selected = _reconcile_single_specialist_contrastive_decision(
                    validation_reason=validation_reason,
                    status=status,
                    reason=reason,
                    selected=selected,
                    specialist_candidate=specialist_candidate,
                )
    else:
        challenge_execution = challenger.challenge(
            SemanticReferenceChallengeInput(
                source_segment_id=request.source_segment_id,
                source_text=request.source_text,
                target_span=target,
                antecedent_candidates=challenge_candidates,
                mode=SemanticReferenceModelTask.CATALOG_SELECTION,
            )
        )
        model_executions.append(challenge_execution)
        status, reason, selected = _challenge_decision(
            challenge_candidates,
            challenge_execution,
        )
        status, reason, selected = _apply_specialist_disagreement_policy(
            status=status,
            reason=reason,
            selected=selected,
            specialist_proposed=specialist_proposed,
        )
    execution_references = tuple(_execution_reference(item) for item in model_executions)
    decision_id = _id(
        "srd",
        observation.id,
        target.id,
        status.value,
        reason.value,
        *(
            f"{item.task.value}:{item.extraction_task_id}:{item.model_run_id}"
            for item in execution_references
        ),
        *(item.id for item in selected),
    )
    decision = SemanticReferenceDecision(
        id=decision_id,
        observation_id=observation.id,
        target_span_id=target.id,
        antecedent_span_ids=tuple(item.id for item in selected),
        status=status,
        reason=reason,
        model_executions=execution_references,
    )
    trace = build_extraction_stage_trace(
        trace_run_id=f"hsq4:{observation.id}",
        ordinal=0,
        stage_id="bounded_semantic_reference",
        stage_version=SEMANTIC_REFERENCE_POLICY_ID,
        producer_id=(model_executions[0].producer_id if model_executions else execution.model_id),
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
            "specialist_proposed_candidate_ids": [item.id for item in specialist_proposed],
            "challenge_candidate_ids": [item.id for item in challenge_candidates],
            "challenge_candidate_source": "monotonic_specialist_deterministic_union",
            "model_attempts": [_model_attempt_input_payload(item) for item in model_executions],
        },
        output_payload={
            "raw_output": execution.raw_output.decode("utf-8"),
            "model_attempts": [_model_attempt_output_payload(item) for item in model_executions],
            "observation": observation.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
        },
        status=_reference_trace_status(tuple(model_executions), reason),
        input_record_ids=(target.id,),
        execution_record_ids=tuple(
            sorted(
                value
                for item in model_executions
                for value in (item.extraction_task_id, item.model_run_id)
            )
        ),
        diagnostics=_reference_trace_diagnostics(tuple(model_executions), reason),
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


def _specialist_candidates(
    target_clusters: tuple[tuple[CoreferenceSpan, ...], ...],
    candidates: tuple[CoreferenceAntecedentCandidate, ...],
    target: CoreferenceSpan,
) -> tuple[tuple[CoreferenceAntecedentCandidate, ...], SemanticReferenceReason]:
    if not target_clusters:
        return (), SemanticReferenceReason.SPECIALIST_TARGET_CLUSTER_MISSING
    model_antecedents = tuple(
        item for item in target_clusters[0] if item.end <= target.start and item.id != target.id
    )
    reconciled = _reconcile_candidates(model_antecedents, candidates)
    if not reconciled:
        return (), SemanticReferenceReason.SPECIALIST_NO_ANTECEDENT
    by_literal: dict[str, list[CoreferenceAntecedentCandidate]] = {}
    for candidate in reconciled:
        by_literal.setdefault(candidate.literal_key, []).append(candidate)
    selected = tuple(
        max(group, key=lambda item: (item.span.end, item.span.start, item.id))
        for _, group in sorted(by_literal.items())
    )
    return (
        tuple(sorted(selected, key=lambda item: (item.span.start, item.span.end, item.id))),
        SemanticReferenceReason.SPECIALIST_NO_ANTECEDENT,
    )


def _nearest_candidates(
    candidates: tuple[CoreferenceAntecedentCandidate, ...],
) -> tuple[CoreferenceAntecedentCandidate, ...]:
    """Bound any challenge catalog to the nearest prior source-valid mentions."""
    return tuple(
        sorted(
            candidates,
            key=lambda item: (item.span.end, item.span.start, item.id),
            reverse=True,
        )[:SEMANTIC_REFERENCE_MAX_ANTECEDENT_CANDIDATES]
    )


def _monotonic_candidate_union(
    specialist_candidates: tuple[CoreferenceAntecedentCandidate, ...],
    deterministic_candidates: tuple[CoreferenceAntecedentCandidate, ...],
) -> tuple[CoreferenceAntecedentCandidate, ...]:
    """Let specialist proposals add evidence without vetoing source-valid candidates."""
    specialist = _nearest_candidates(specialist_candidates)
    specialist_ids = {item.id for item in specialist}
    fallback = _nearest_candidates(
        tuple(item for item in deterministic_candidates if item.id not in specialist_ids)
    )
    return (specialist + fallback)[:SEMANTIC_REFERENCE_MAX_ANTECEDENT_CANDIDATES]


def _candidate_validation_decision(
    candidate: CoreferenceAntecedentCandidate,
    execution: SemanticReferenceCandidateValidationExecution,
) -> tuple[SemanticReferenceStatus, SemanticReferenceReason, tuple[CoreferenceSpan, ...]]:
    if execution.model_status is not ModelRunStatus.SUCCEEDED:
        reason = (
            SemanticReferenceReason.SPECIALIST_VALIDATION_INVALID
            if execution.model_status is ModelRunStatus.INVALID_OUTPUT
            else SemanticReferenceReason.SPECIALIST_VALIDATION_FAILED
        )
        return SemanticReferenceStatus.UNRESOLVED, reason, ()
    if execution.validation is None or execution.candidate_id != candidate.id:
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.SPECIALIST_VALIDATION_INVALID,
            (),
        )
    if execution.validation.verdict is SemanticReferenceCandidateVerdict.SUPPORTED:
        return (
            SemanticReferenceStatus.RESOLVED,
            SemanticReferenceReason.SPECIALIST_VALIDATION_SUPPORTED,
            (candidate.span,),
        )
    if execution.validation.verdict is SemanticReferenceCandidateVerdict.UNSUPPORTED:
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.SPECIALIST_VALIDATION_UNSUPPORTED,
            (),
        )
    return (
        SemanticReferenceStatus.UNRESOLVED,
        SemanticReferenceReason.SPECIALIST_VALIDATION_UNCLEAR,
        (),
    )


def _challenge_decision(
    candidates: tuple[CoreferenceAntecedentCandidate, ...],
    execution: SemanticReferenceChallengeExecution,
) -> tuple[SemanticReferenceStatus, SemanticReferenceReason, tuple[CoreferenceSpan, ...]]:
    selection = execution.selection
    if execution.model_status is not ModelRunStatus.SUCCEEDED or selection is None:
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.CHALLENGE_FAILED,
            (),
        )
    if tuple(item.candidate_id for item in execution.candidate_label_bindings) != tuple(
        item.id for item in candidates
    ):
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.CHALLENGE_INVALID,
            (),
        )
    if selection.ambiguous:
        if len(candidates) < 2:
            return (
                SemanticReferenceStatus.UNRESOLVED,
                SemanticReferenceReason.CHALLENGE_INVALID,
                (),
            )
        return (
            SemanticReferenceStatus.AMBIGUOUS,
            SemanticReferenceReason.CHALLENGE_AMBIGUOUS,
            tuple(item.span for item in candidates),
        )
    if selection.antecedent_candidate_label is None:
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.CHALLENGE_UNRESOLVED,
            (),
        )
    selected_candidate_id = _mapped_challenge_candidate_id(execution)
    selected = next((item for item in candidates if item.id == selected_candidate_id), None)
    if selected is None:
        return (
            SemanticReferenceStatus.UNRESOLVED,
            SemanticReferenceReason.CHALLENGE_INVALID,
            (),
        )
    return (
        SemanticReferenceStatus.RESOLVED,
        SemanticReferenceReason.CHALLENGE_SELECTED_ANTECEDENT,
        (selected.span,),
    )


def _mapped_challenge_candidate_id(
    execution: SemanticReferenceChallengeExecution,
) -> str | None:
    if execution.selection is None or execution.selection.antecedent_candidate_label is None:
        return None
    return next(
        (
            item.candidate_id
            for item in execution.candidate_label_bindings
            if item.label == execution.selection.antecedent_candidate_label
        ),
        None,
    )


def _candidate_label_bindings_payload(
    bindings: tuple[SemanticReferenceCandidateLabelBinding, ...],
) -> list[JsonValue]:
    payload: list[JsonValue] = []
    for binding in bindings:
        payload.append({"label": binding.label, "candidate_id": binding.candidate_id})
    return payload


def _execution_reference(
    execution: SemanticReferenceModelExecution,
) -> SemanticReferenceModelExecutionReference:
    return SemanticReferenceModelExecutionReference(
        task=(
            SemanticReferenceModelTask.SPECIALIST_VALIDATION
            if isinstance(execution, SemanticReferenceCandidateValidationExecution)
            else execution.mode
        ),
        extraction_task_id=execution.extraction_task_id,
        model_run_id=execution.model_run_id,
    )


def _model_attempt_input_payload(
    execution: SemanticReferenceModelExecution,
) -> dict[str, JsonValue]:
    reference = _execution_reference(execution)
    payload: dict[str, JsonValue] = {
        "task": reference.task.value,
        "model_visible_task": execution.model_visible_task.decode("utf-8"),
    }
    if isinstance(execution, SemanticReferenceCandidateValidationExecution):
        payload["candidate_ids"] = [execution.candidate_id]
        payload["candidate_label_bindings"] = []
    else:
        payload["candidate_ids"] = [
            item.candidate_id for item in execution.candidate_label_bindings
        ]
        payload["candidate_label_bindings"] = _candidate_label_bindings_payload(
            execution.candidate_label_bindings
        )
    return payload


def _model_attempt_output_payload(
    execution: SemanticReferenceModelExecution,
) -> dict[str, JsonValue]:
    reference = _execution_reference(execution)
    result: dict[str, JsonValue] | None
    mapped_candidate_id: str | None
    if isinstance(execution, SemanticReferenceCandidateValidationExecution):
        result = (
            {
                "verdict": execution.validation.verdict.value,
                "reason": execution.validation.reason,
            }
            if execution.validation is not None
            else None
        )
        mapped_candidate_id = (
            execution.candidate_id
            if execution.validation is not None
            and execution.validation.verdict is SemanticReferenceCandidateVerdict.SUPPORTED
            else None
        )
    else:
        result = (
            _challenge_selection_payload(execution.selection)
            if execution.selection is not None
            else None
        )
        mapped_candidate_id = _mapped_challenge_candidate_id(execution)
    return {
        "task": reference.task.value,
        "extraction_task_id": execution.extraction_task_id,
        "model_run_id": execution.model_run_id,
        "model_status": execution.model_status.value,
        "raw_output_sha256": execution.raw_output_sha256,
        "model_result": result,
        "mapped_candidate_id": mapped_candidate_id,
    }


def _challenge_selection_payload(
    selection: SemanticReferenceChallengeSelection,
) -> dict[str, JsonValue]:
    return {
        "antecedent_candidate_label": selection.antecedent_candidate_label,
        "ambiguous": selection.ambiguous,
        "reason": selection.reason,
    }


def _reference_trace_status(
    executions: tuple[SemanticReferenceModelExecution, ...],
    reason: SemanticReferenceReason,
) -> ExtractionStageStatus:
    if reason in {
        SemanticReferenceReason.CHALLENGE_INVALID,
        SemanticReferenceReason.SPECIALIST_VALIDATION_INVALID,
    }:
        return ExtractionStageStatus.REJECTED
    if any(item.model_status is not ModelRunStatus.SUCCEEDED for item in executions):
        return ExtractionStageStatus.FAILED
    return ExtractionStageStatus.COMPLETED


def _reference_trace_diagnostics(
    executions: tuple[SemanticReferenceModelExecution, ...],
    reason: SemanticReferenceReason,
) -> tuple[str, ...]:
    diagnostics: set[str] = set()
    if reason is SemanticReferenceReason.CHALLENGE_INVALID:
        diagnostics.add("semantic_reference_challenge_invalid")
    if reason is SemanticReferenceReason.SPECIALIST_VALIDATION_INVALID:
        diagnostics.add("semantic_reference_specialist_validation_invalid")
    for execution in executions:
        if execution.model_status is ModelRunStatus.SUCCEEDED:
            continue
        diagnostics.add(
            "semantic_reference_specialist_validation_failed"
            if isinstance(execution, SemanticReferenceCandidateValidationExecution)
            else "semantic_reference_challenge_failed"
        )
    return tuple(sorted(diagnostics))


def _ordered_distinct_spans(
    spans: tuple[CoreferenceSpan, ...],
) -> tuple[CoreferenceSpan, ...]:
    return tuple(
        sorted(
            {item.id: item for item in spans}.values(),
            key=lambda item: (item.start, item.end, item.id),
        )
    )


def _apply_specialist_disagreement_policy(
    *,
    status: SemanticReferenceStatus,
    reason: SemanticReferenceReason,
    selected: tuple[CoreferenceSpan, ...],
    specialist_proposed: tuple[CoreferenceAntecedentCandidate, ...],
) -> tuple[SemanticReferenceStatus, SemanticReferenceReason, tuple[CoreferenceSpan, ...]]:
    """Prevent two disagreeing fallible models from producing a resolved fact."""
    if status is not SemanticReferenceStatus.RESOLVED or not specialist_proposed:
        return status, reason, selected
    selected_ids = {item.id for item in selected}
    specialist_span_ids = {item.span.id for item in specialist_proposed}
    if selected_ids.issubset(specialist_span_ids):
        return status, reason, selected
    ambiguous = _ordered_distinct_spans((*selected, *(item.span for item in specialist_proposed)))
    return (
        SemanticReferenceStatus.AMBIGUOUS,
        SemanticReferenceReason.SPECIALIST_CHALLENGE_DISAGREEMENT,
        ambiguous,
    )


def _reconcile_single_specialist_contrastive_decision(
    *,
    validation_reason: SemanticReferenceReason,
    status: SemanticReferenceStatus,
    reason: SemanticReferenceReason,
    selected: tuple[CoreferenceSpan, ...],
    specialist_candidate: CoreferenceAntecedentCandidate,
) -> tuple[SemanticReferenceStatus, SemanticReferenceReason, tuple[CoreferenceSpan, ...]]:
    """Reconcile one specialist proposal after its bounded semantic validation."""
    if status is not SemanticReferenceStatus.RESOLVED:
        return status, reason, selected
    if selected == (specialist_candidate.span,):
        return (
            status,
            SemanticReferenceReason.SPECIALIST_CONTRASTIVE_CONFIRMATION,
            selected,
        )
    if validation_reason is SemanticReferenceReason.SPECIALIST_VALIDATION_UNSUPPORTED:
        return (
            status,
            SemanticReferenceReason.SPECIALIST_REJECTED_CONTRASTIVE_SELECTION,
            selected,
        )
    return _apply_specialist_disagreement_policy(
        status=status,
        reason=reason,
        selected=selected,
        specialist_proposed=(specialist_candidate,),
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
