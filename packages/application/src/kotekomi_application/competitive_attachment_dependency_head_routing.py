"""Typed evidence for CEA-1.18 dependency-head Residual routing."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter_calibration import (
    AttachmentBinaryMetrics,
)
from kotekomi_application.competitive_attachment_residual_transfer import (
    AttachmentResidualTransferCase,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
    AttachmentSyntaxObservation,
)
from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentCandidate,
)
from kotekomi_application.event_entity_connections import (
    EventEntityLinguisticEvidence,
)
from kotekomi_application.event_entity_predicate_arguments import (
    PredicateArgumentToken,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentHeadRoute(StrEnum):
    """The bounded route selected from exact dependency evidence."""

    STRUCTURAL = "structural"
    SEMANTIC = "semantic"


class AttachmentHeadRoutingOutcome(StrEnum):
    """Terminal CEA-1.18 experiment result."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"


class AttachmentCandidateRootEvidence(BaseModel):
    """Complete Candidate token inventory and its derived dependency roots."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tokens: tuple[PredicateArgumentToken, ...]
    roots: tuple[PredicateArgumentToken, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        token_ids = tuple(item.token_id for item in self.tokens)
        if token_ids != tuple(dict.fromkeys(token_ids)):
            raise ValueError("Dependency-head Candidate tokens must be ordered and distinct.")
        token_id_set = set(token_ids)
        expected_roots = tuple(
            item
            for item in self.tokens
            if item.part_of_speech.casefold() != "punct" and item.head_token_id not in token_id_set
        )
        if self.roots != expected_roots:
            raise ValueError("Dependency-head Candidate Roots are incomplete.")
        return self


class AttachmentHeadRoutingCase(BaseModel):
    """One exact Residual Edge, dependency observation, and route decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    transfer_case: AttachmentResidualTransferCase
    syntax: AttachmentSyntaxObservation
    candidate_root_evidence: AttachmentCandidateRootEvidence
    baseline_answers: tuple[Literal["Y", "N"], Literal["Y", "N"]]
    route: AttachmentHeadRoute
    routed_answers: tuple[Literal["Y", "N"], Literal["Y", "N"]]
    baseline_correct: bool
    routed_correct: bool
    recovered: bool
    regressed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        task = self.transfer_case.task
        edge_task = task.edge_filter_task
        candidate = edge_task.candidate
        event = edge_task.edge.event_range
        if self.syntax.phase != task.phase:
            raise ValueError("Dependency-head route phase drifted from its transfer case.")
        if (
            self.syntax.candidate_id != candidate.id
            or self.syntax.source_grounded_event_id != edge_task.edge.source_grounded_event_id
            or self.syntax.source_segment_id != candidate.source_segment_id
            or self.syntax.source_text_sha256 != candidate.source_text_sha256
        ):
            raise ValueError("Dependency-head route references foreign syntax evidence.")
        if (
            self.syntax.candidate_range.start,
            self.syntax.candidate_range.end,
            self.syntax.candidate_range.text,
        ) != (candidate.start, candidate.end, candidate.text):
            raise ValueError("Dependency-head Candidate range drifted.")
        if (
            self.syntax.event_range.start,
            self.syntax.event_range.end,
            self.syntax.event_range.text,
        ) != (event.start, event.end, event.text):
            raise ValueError("Dependency-head Event range drifted.")
        source = edge_task.source_text
        tokens = self.candidate_root_evidence.tokens
        if tuple(item.token_id for item in tokens) != candidate.linguistic_token_ids:
            raise ValueError("Dependency-head Candidate token inventory is incomplete.")
        if any(
            item.start < candidate.start
            or item.end > candidate.end
            or source[item.start : item.end] != item.text
            for item in tokens
        ):
            raise ValueError("Dependency-head Candidate token is not source-exact.")
        roots = self.candidate_root_evidence.roots
        aligned = attachment_syntax_is_head_aligned(self.syntax, roots)
        expected_route = AttachmentHeadRoute.STRUCTURAL if aligned else AttachmentHeadRoute.SEMANTIC
        if self.route is not expected_route:
            raise ValueError("Dependency-head route drifted from exact syntax evidence.")
        if self.baseline_answers != self.transfer_case.threshold_answers:
            raise ValueError("Dependency-head baseline drifted from CEA-1.17.")
        expected_routed = (
            ("Y", "Y") if self.route is AttachmentHeadRoute.STRUCTURAL else self.baseline_answers
        )
        if self.routed_answers != expected_routed:
            raise ValueError("Dependency-head answers drifted from the selected route.")
        expected = self.transfer_case.gold.expected_answer
        baseline_correct = all(item == expected for item in self.baseline_answers)
        routed_correct = all(item == expected for item in self.routed_answers)
        if self.baseline_correct != baseline_correct or self.routed_correct != routed_correct:
            raise ValueError("Dependency-head correctness flags drifted.")
        if self.recovered != (not baseline_correct and routed_correct):
            raise ValueError("Dependency-head recovery flag drifted.")
        if self.regressed != (baseline_correct and not routed_correct):
            raise ValueError("Dependency-head regression flag drifted.")
        return self


class AttachmentHeadRoutingPhase(BaseModel):
    """One complete phase of model-free dependency-head routing."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: Literal["development", "validation"]
    cases: tuple[AttachmentHeadRoutingCase, ...]
    baseline_metrics: tuple[AttachmentBinaryMetrics, AttachmentBinaryMetrics]
    routed_metrics: tuple[AttachmentBinaryMetrics, AttachmentBinaryMetrics]
    head_aligned_count: Annotated[int, Field(ge=0)]
    semantic_count: Annotated[int, Field(ge=0)]
    head_aligned_positive_count: Annotated[int, Field(ge=0)]
    head_aligned_negative_count: Annotated[int, Field(ge=0)]
    semantic_positive_count: Annotated[int, Field(ge=0)]
    semantic_negative_count: Annotated[int, Field(ge=0)]
    recovered_count: Annotated[int, Field(ge=0)]
    regressed_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_count = 10 if self.phase == "development" else 7
        if len(self.cases) != expected_count:
            raise ValueError("Dependency-head phase inventory drifted.")
        if tuple(sorted(self.cases, key=lambda item: item.transfer_case.task.id)) != self.cases:
            raise ValueError("Dependency-head cases must use canonical task order.")
        if any(item.transfer_case.task.phase != self.phase for item in self.cases):
            raise ValueError("Dependency-head phase contains foreign cases.")
        structural = tuple(
            item for item in self.cases if item.route is AttachmentHeadRoute.STRUCTURAL
        )
        semantic = tuple(item for item in self.cases if item.route is AttachmentHeadRoute.SEMANTIC)
        observed = (
            self.head_aligned_count,
            self.semantic_count,
            self.head_aligned_positive_count,
            self.head_aligned_negative_count,
            self.semantic_positive_count,
            self.semantic_negative_count,
            self.recovered_count,
            self.regressed_count,
        )
        expected = (
            len(structural),
            len(semantic),
            sum(item.transfer_case.gold.expected_answer == "Y" for item in structural),
            sum(item.transfer_case.gold.expected_answer == "N" for item in structural),
            sum(item.transfer_case.gold.expected_answer == "Y" for item in semantic),
            sum(item.transfer_case.gold.expected_answer == "N" for item in semantic),
            sum(item.recovered for item in self.cases),
            sum(item.regressed for item in self.cases),
        )
        if observed != expected:
            raise ValueError("Dependency-head phase counts drifted.")
        return self


class AttachmentHeadRoutingReport(BaseModel):
    """Complete CEA-1.18 model-free routing report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inputs: tuple[AttachmentEvidenceReference, ...]
    predecessor_result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    development: AttachmentHeadRoutingPhase
    validation: AttachmentHeadRoutingPhase
    outcome: AttachmentHeadRoutingOutcome
    baseline_case_count: Literal[17] = 17
    structural_route_count: Annotated[int, Field(ge=0)]
    semantic_route_count: Annotated[int, Field(ge=0)]
    projected_model_call_reduction: Annotated[float, Field(ge=0, le=1)]
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        structural = self.development.head_aligned_count + self.validation.head_aligned_count
        semantic = self.development.semantic_count + self.validation.semantic_count
        if (self.structural_route_count, self.semantic_route_count) != (structural, semantic):
            raise ValueError("Dependency-head report route counts drifted.")
        if structural + semantic != self.baseline_case_count:
            raise ValueError("Dependency-head report inventory drifted.")
        if self.projected_model_call_reduction != structural / self.baseline_case_count:
            raise ValueError("Dependency-head projected call reduction drifted.")
        expected_outcome = classify_dependency_head_routing_outcome(
            self.development,
            self.validation,
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Dependency-head report outcome drifted.")
        if self.result_fingerprint != attachment_head_routing_fingerprint(self):
            raise ValueError("Dependency-head report fingerprint drifted.")
        return self


def attachment_candidate_tokens(
    candidate: CompetitiveAttachmentCandidate,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> tuple[PredicateArgumentToken, ...]:
    """Return every exact linguistic token named by one Candidate."""
    if (
        candidate.source_segment_id != linguistic_evidence.source_segment_id
        or candidate.source_text_sha256 != linguistic_evidence.source_text_sha256
    ):
        raise ValueError("Dependency-head Candidate and linguistic evidence disagree.")
    token_by_id = {item.token_id: item for item in linguistic_evidence.tokens}
    unknown = tuple(
        token_id for token_id in candidate.linguistic_token_ids if token_id not in token_by_id
    )
    if unknown:
        raise ValueError("Dependency-head Candidate references unknown linguistic tokens.")
    return tuple(
        PredicateArgumentToken(
            token_id=item.token_id,
            sentence_id=item.sentence_id,
            text=item.text,
            start=item.start,
            end=item.end,
            lemma=item.lemma,
            part_of_speech=item.part_of_speech,
            dependency_relation=item.dependency_relation,
            head_token_id=item.head_token_id,
        )
        for item in (token_by_id[token_id] for token_id in candidate.linguistic_token_ids)
    )


def attachment_candidate_root_evidence(
    candidate: CompetitiveAttachmentCandidate,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> AttachmentCandidateRootEvidence:
    """Return a complete Candidate token inventory and its exact dependency roots."""
    tokens = attachment_candidate_tokens(candidate, linguistic_evidence)
    token_ids = {item.token_id for item in tokens}
    roots = tuple(
        item
        for item in tokens
        if item.part_of_speech.casefold() != "punct" and item.head_token_id not in token_ids
    )
    return AttachmentCandidateRootEvidence(tokens=tokens, roots=roots)


def attachment_candidate_root_tokens(
    candidate: CompetitiveAttachmentCandidate,
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> tuple[PredicateArgumentToken, ...]:
    """Return exact non-punctuation Candidate tokens whose head leaves the Candidate."""
    return attachment_candidate_root_evidence(candidate, linguistic_evidence).roots


def attachment_syntax_is_head_aligned(
    syntax: AttachmentSyntaxObservation,
    candidate_roots: tuple[PredicateArgumentToken, ...],
) -> bool:
    """Return whether one exact Candidate Root equals the exact Event Anchor."""
    return (
        len(candidate_roots) == 1
        and syntax.event_anchor is not None
        and syntax.gap_code is None
        and candidate_roots[0].token_id == syntax.event_anchor.token_id
    )


def classify_dependency_head_routing_outcome(
    development: AttachmentHeadRoutingPhase,
    validation: AttachmentHeadRoutingPhase,
) -> AttachmentHeadRoutingOutcome:
    """Apply the complete CEA-1.18 outcome contract."""
    structural_false_positive = any(
        item.route is AttachmentHeadRoute.STRUCTURAL
        and item.transfer_case.gold.expected_answer == "N"
        for phase in (development, validation)
        for item in phase.cases
    )
    baseline_validation = validation.baseline_metrics[0].accuracy
    routed_validation = validation.routed_metrics[0].accuracy
    if structural_false_positive or routed_validation <= baseline_validation:
        return AttachmentHeadRoutingOutcome.FALSIFIED
    quality_gates = (
        all(item.accuracy == 0.9 for item in development.routed_metrics)
        and all(item.accuracy == 1.0 for item in validation.routed_metrics)
        and all(
            item.false_positive_count == 0
            for phase in (development, validation)
            for item in phase.routed_metrics
        )
    )
    return (
        AttachmentHeadRoutingOutcome.SUPPORTED
        if quality_gates
        else AttachmentHeadRoutingOutcome.MIXED
    )


def attachment_head_routing_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.18 DTO."""
    payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
