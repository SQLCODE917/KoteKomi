"""Source-bound semantic qualification of Organization mention candidates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol

from kotekomi_application.organization_mention_boundary_reconciliation import (
    MentionBoundaryDecision,
    MentionBoundaryDecisionStatus,
    OrganizationBoundaryReconciliationResult,
)
from kotekomi_application.organization_mention_qualification import MentionCandidate

QWEN_ORGANIZATION_QUALIFICATION_POLICY_ID = "qwen_organization_qualification_v2"
REFINED_ORGANIZATION_TYPE_MAPPING_POLICY_ID = "refined_coarse_mention_type_v1"

_EXPLICIT_NON_ORGANIZATION_TYPES = frozenset(
    {
        "CARDINAL",
        "DATE",
        "EVENT",
        "FAC",
        "GPE",
        "LANGUAGE",
        "LAW",
        "LOC",
        "MONEY",
        "NORP",
        "ORDINAL",
        "PERCENT",
        "PERSON",
        "PRODUCT",
        "QUANTITY",
        "TIME",
        "WORK_OF_ART",
    }
)


class OrganizationQualificationJudgment(StrEnum):
    """Semantic judgment about one immutable source-literal candidate."""

    ORGANIZATION = "organization"
    NOT_ORGANIZATION = "not_organization"
    AMBIGUOUS = "ambiguous"


class OrganizationQualificationExecutionStatus(StrEnum):
    """Execution outcome kept separate from semantic abstention."""

    COMPLETED = "completed"
    INVALID_OUTPUT = "invalid_output"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    BLOCKED = "blocked"


class OrganizationQualificationEligibility(StrEnum):
    """Whether Gold can score one candidate as a semantic decision."""

    EXACT_GOLD = "exact_gold"
    DISJOINT_GOLD = "disjoint_gold"
    BOUNDARY_CASE = "boundary_case"


@dataclass(frozen=True)
class GoldOrganizationSpan:
    """One reviewed literal Gold Organization boundary."""

    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            not self.text
            or self.start < 0
            or self.end <= self.start
            or len(self.text) != self.end - self.start
        ):
            raise ValueError("Gold Organization span must be a valid non-empty interval.")


@dataclass(frozen=True)
class QualificationGoldClassification:
    """Gold expectation that does not mislabel boundary errors as semantic errors."""

    candidate_id: str
    eligibility: OrganizationQualificationEligibility
    expected_judgment: OrganizationQualificationJudgment | None
    overlapping_gold_spans: tuple[GoldOrganizationSpan, ...]


@dataclass(frozen=True)
class QualificationCandidate:
    """One ORG-R1 candidate whose source characters cannot change in ORG-R2."""

    id: str
    source_segment_id: str
    source_text_sha256: str
    text: str
    start: int
    end: int
    boundary_decision_id: str
    boundary_status: MentionBoundaryDecisionStatus
    boundary_rule_id: str
    source_candidate_ids: tuple[str, ...]
    proposer_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.source_segment_id or not self.boundary_decision_id:
            raise ValueError("Qualification candidate identity must be complete.")
        if not _is_sha256(self.source_text_sha256):
            raise ValueError("Qualification candidate requires a SHA-256 source digest.")
        if (
            not self.text
            or self.start < 0
            or self.end <= self.start
            or len(self.text) != self.end - self.start
        ):
            raise ValueError("Qualification candidate requires a valid non-empty source span.")
        if not self.source_candidate_ids or not self.proposer_ids:
            raise ValueError("Qualification candidate requires complete ORG-R1 provenance.")
        _require_ordered_distinct("source candidate IDs", self.source_candidate_ids)
        _require_ordered_distinct("proposer IDs", self.proposer_ids)


@dataclass(frozen=True)
class ContextualLinkedEntity:
    """Project-owned projection of one ReFinED entity candidate."""

    wikidata_entity_id: str | None
    wikipedia_entity_title: str | None
    human_readable_name: str | None
    parsed_string: str | None
    score: float | None

    def __post_init__(self) -> None:
        if self.score is not None and not math.isfinite(self.score):
            raise ValueError("Contextual linked-entity score must be finite.")


@dataclass(frozen=True)
class ContextualEntityTypePrediction:
    """Project-owned projection of one ReFinED fine-type prediction."""

    type_id: str
    type_label: str | None
    confidence: float | None

    def __post_init__(self) -> None:
        if not self.type_id:
            raise ValueError("Contextual entity-type prediction requires a type identity.")
        if self.confidence is not None and not math.isfinite(self.confidence):
            raise ValueError("Contextual entity-type confidence must be finite.")


@dataclass(frozen=True)
class ContextualOrganizationTypeEvidence:
    """Complete observable ReFinED evidence for one caller-supplied span."""

    candidate_id: str
    returned_text: str
    start: int
    end: int
    coarse_type: str | None
    coarse_mention_type: str | None
    predicted_entity: ContextualLinkedEntity | None
    entity_linking_score: float | None
    top_k_entities: tuple[ContextualLinkedEntity, ...]
    predicted_entity_types: tuple[ContextualEntityTypePrediction, ...]
    failed_class_check: bool | None

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.returned_text:
            raise ValueError("Contextual type evidence identity and text must be complete.")
        if (
            self.start < 0
            or self.end <= self.start
            or len(self.returned_text) != self.end - self.start
        ):
            raise ValueError("Contextual type evidence has an invalid source span.")
        if self.entity_linking_score is not None and not math.isfinite(self.entity_linking_score):
            raise ValueError("Contextual type evidence score must be finite.")


@dataclass(frozen=True)
class ContextualOrganizationTypeInput:
    """One exact Source segment and its ordered ORG-R1 candidates."""

    source_segment_id: str
    source_text_sha256: str
    source_text: str
    candidates: tuple[QualificationCandidate, ...]

    def __post_init__(self) -> None:
        digest = hashlib.sha256(self.source_text.encode("utf-8")).hexdigest()
        if not self.source_segment_id or not self.source_text:
            raise ValueError("Contextual type input requires source identity and text.")
        if digest != self.source_text_sha256:
            raise ValueError("Contextual type input source digest does not match its text.")
        expected_order = tuple(
            sorted(self.candidates, key=lambda item: (item.start, item.end, item.id))
        )
        if expected_order != self.candidates:
            raise ValueError("Contextual type input candidates must be ordered by source position.")
        for candidate in self.candidates:
            if candidate.source_segment_id != self.source_segment_id:
                raise ValueError("Contextual type input candidate Source segment drifted.")
            if candidate.source_text_sha256 != self.source_text_sha256:
                raise ValueError("Contextual type input candidate source digest drifted.")
            if (
                candidate.end > len(self.source_text)
                or self.source_text[candidate.start : candidate.end] != candidate.text
            ):
                raise ValueError(
                    "Contextual type input candidate does not match source characters."
                )


@dataclass(frozen=True)
class ContextualOrganizationTypeBatch:
    """Typed Adapter result for one predetermined-span ReFinED request."""

    producer_id: str
    model_id: str
    model_revision: str
    entity_set: str
    package_revision: str
    resource_manifest_sha256: str
    load_elapsed_ms: int
    inference_elapsed_ms: int
    evidences: tuple[ContextualOrganizationTypeEvidence, ...]

    def __post_init__(self) -> None:
        identity = (
            self.producer_id,
            self.model_id,
            self.model_revision,
            self.entity_set,
            self.package_revision,
        )
        if any(not value for value in identity):
            raise ValueError("Contextual type batch producer identity must be complete.")
        if not _is_sha256(self.resource_manifest_sha256):
            raise ValueError("Contextual type batch requires a resource manifest SHA-256.")
        if self.load_elapsed_ms < 0 or self.inference_elapsed_ms < 0:
            raise ValueError("Contextual type batch timings cannot be negative.")


class ContextualOrganizationTypePort(Protocol):
    """Use contextual typing on exact caller-owned source spans."""

    def qualify(
        self,
        request: ContextualOrganizationTypeInput,
    ) -> ContextualOrganizationTypeBatch:
        """Return one validated evidence item per ordered input candidate."""
        ...


@dataclass(frozen=True)
class OrganizationQualificationDecision:
    """One source-bound semantic result with complete execution lineage."""

    id: str
    candidate_id: str
    candidate_text: str
    candidate_start: int
    candidate_end: int
    source_segment_id: str
    source_text_sha256: str
    producer_id: str
    judgment: OrganizationQualificationJudgment | None
    execution_status: OrganizationQualificationExecutionStatus
    evidence_record_id: str
    execution_record_ids: tuple[str, ...]
    terminal_trace_id: str
    mapping_policy_id: str
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        identity = (
            self.id,
            self.candidate_id,
            self.source_segment_id,
            self.producer_id,
            self.evidence_record_id,
            self.terminal_trace_id,
            self.mapping_policy_id,
        )
        if any(not value for value in identity):
            raise ValueError("Qualification decision identity and lineage must be complete.")
        if not _is_sha256(self.source_text_sha256):
            raise ValueError("Qualification decision requires a SHA-256 source digest.")
        if (
            not self.candidate_text
            or self.candidate_start < 0
            or self.candidate_end <= self.candidate_start
            or len(self.candidate_text) != self.candidate_end - self.candidate_start
        ):
            raise ValueError("Qualification decision candidate span is invalid.")
        _require_ordered_distinct("execution record IDs", self.execution_record_ids)
        _require_ordered_distinct("diagnostics", self.diagnostics)
        if self.execution_status is OrganizationQualificationExecutionStatus.COMPLETED:
            if self.judgment is None or self.diagnostics:
                raise ValueError("Completed qualification decision state is inconsistent.")
        elif self.judgment is not None or not self.diagnostics:
            raise ValueError("Non-completed qualification decision state is inconsistent.")


def qualification_candidates_from_reconciliation(
    *,
    source_text: str,
    candidates: tuple[MentionCandidate, ...],
    reconciliation: OrganizationBoundaryReconciliationResult,
) -> tuple[QualificationCandidate, ...]:
    """Rebuild every preserved ORG-R1 candidate without changing its boundary."""
    source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if source_digest != reconciliation.source_text_digest:
        raise ValueError("ORG-R1 source digest does not match authoritative source text.")
    if not source_text:
        raise ValueError("Qualification candidate catalog requires source text.")
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    if len(candidate_by_id) != len(candidates):
        raise ValueError("Qualification candidate catalog repeats a candidate identity.")
    decision_by_candidate: dict[str, MentionBoundaryDecision] = {}
    for decision in reconciliation.decisions:
        if decision.source_segment_id != reconciliation.source_segment_id:
            raise ValueError("ORG-R1 boundary decision Source segment drifted.")
        if decision.source_text_digest != source_digest:
            raise ValueError("ORG-R1 boundary decision source digest drifted.")
        if tuple(sorted(set(decision.preserved_candidate_ids))) != tuple(
            sorted(decision.preserved_candidate_ids)
        ):
            raise ValueError("ORG-R1 boundary decision repeats a preserved candidate.")
        for candidate_id in decision.preserved_candidate_ids:
            if candidate_id in decision_by_candidate:
                raise ValueError("ORG-R1 candidate appears in more than one boundary decision.")
            decision_by_candidate[candidate_id] = decision
    if set(decision_by_candidate) != set(candidate_by_id):
        raise ValueError(
            "ORG-R1 decisions must preserve every qualification candidate exactly once."
        )
    qualified: list[QualificationCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.start, item.end, item.id)):
        if candidate.source_segment_id != reconciliation.source_segment_id:
            raise ValueError("Mention candidate Source segment drifted from ORG-R1 evidence.")
        if candidate.source_text_digest != source_digest:
            raise ValueError("Mention candidate source digest drifted from ORG-R1 evidence.")
        if (
            candidate.end > len(source_text)
            or source_text[candidate.start : candidate.end] != candidate.text
        ):
            raise ValueError("Mention candidate does not match authoritative source characters.")
        decision = decision_by_candidate[candidate.id]
        qualified.append(
            QualificationCandidate(
                id=_id("qfc", candidate.id, decision.id),
                source_segment_id=candidate.source_segment_id,
                source_text_sha256=source_digest,
                text=candidate.text,
                start=candidate.start,
                end=candidate.end,
                boundary_decision_id=decision.id,
                boundary_status=decision.status,
                boundary_rule_id=decision.rule_id,
                source_candidate_ids=tuple(sorted(decision.candidate_ids)),
                proposer_ids=tuple(
                    sorted({observation.proposer_id for observation in candidate.observations})
                ),
            )
        )
    return tuple(qualified)


def parse_organization_qualification_output(raw_output: str) -> OrganizationQualificationJudgment:
    """Parse the deliberately literal Qwen ORG-R2 output contract."""
    try:
        return OrganizationQualificationJudgment(raw_output)
    except ValueError as error:
        raise ValueError("Model output must be exactly one qualification literal.") from error


def classify_qualification_candidate(
    candidate: QualificationCandidate,
    gold_spans: tuple[GoldOrganizationSpan, ...],
) -> QualificationGoldClassification:
    """Classify exact, disjoint, and non-exact overlapping Gold boundaries."""
    exact = tuple(
        span
        for span in gold_spans
        if span.start == candidate.start
        and span.end == candidate.end
        and span.text == candidate.text
    )
    if exact:
        return QualificationGoldClassification(
            candidate.id,
            OrganizationQualificationEligibility.EXACT_GOLD,
            OrganizationQualificationJudgment.ORGANIZATION,
            exact,
        )
    overlaps = tuple(
        span
        for span in gold_spans
        if max(span.start, candidate.start) < min(span.end, candidate.end)
    )
    if overlaps:
        return QualificationGoldClassification(
            candidate.id,
            OrganizationQualificationEligibility.BOUNDARY_CASE,
            None,
            overlaps,
        )
    return QualificationGoldClassification(
        candidate.id,
        OrganizationQualificationEligibility.DISJOINT_GOLD,
        OrganizationQualificationJudgment.NOT_ORGANIZATION,
        (),
    )


def map_contextual_type_evidence(
    evidence: ContextualOrganizationTypeEvidence,
) -> OrganizationQualificationJudgment:
    """Apply the explicit, inspectable ReFinED-to-KoteKomi mapping policy."""
    if evidence.failed_class_check:
        return OrganizationQualificationJudgment.AMBIGUOUS
    coarse_type = evidence.coarse_mention_type
    if coarse_type == "ORG":
        return OrganizationQualificationJudgment.ORGANIZATION
    if coarse_type in _EXPLICIT_NON_ORGANIZATION_TYPES:
        return OrganizationQualificationJudgment.NOT_ORGANIZATION
    return OrganizationQualificationJudgment.AMBIGUOUS


def build_organization_qualification_decision(
    *,
    candidate: QualificationCandidate,
    producer_id: str,
    judgment: OrganizationQualificationJudgment | None,
    execution_status: OrganizationQualificationExecutionStatus,
    evidence_record_id: str,
    execution_record_ids: tuple[str, ...],
    terminal_trace_id: str,
    mapping_policy_id: str,
    diagnostics: tuple[str, ...] = (),
) -> OrganizationQualificationDecision:
    """Construct one decision while copying, never editing, its candidate boundary."""
    if not producer_id or not evidence_record_id or not terminal_trace_id or not mapping_policy_id:
        raise ValueError("Qualification decision lineage must be complete.")
    _require_ordered_distinct("execution record IDs", execution_record_ids)
    _require_ordered_distinct("diagnostics", diagnostics)
    if execution_status is OrganizationQualificationExecutionStatus.COMPLETED:
        if judgment is None:
            raise ValueError("A completed qualification decision requires a semantic judgment.")
        if diagnostics:
            raise ValueError("A completed qualification decision cannot carry failure diagnostics.")
    else:
        if judgment is not None:
            raise ValueError("A non-completed decision cannot carry a semantic judgment.")
        if not diagnostics:
            raise ValueError("A non-completed qualification decision requires diagnostics.")
    decision_id = _id(
        "oqd",
        candidate.id,
        producer_id,
        execution_status.value,
        judgment.value if judgment is not None else "",
        evidence_record_id,
        *execution_record_ids,
        terminal_trace_id,
        mapping_policy_id,
        *diagnostics,
    )
    return OrganizationQualificationDecision(
        id=decision_id,
        candidate_id=candidate.id,
        candidate_text=candidate.text,
        candidate_start=candidate.start,
        candidate_end=candidate.end,
        source_segment_id=candidate.source_segment_id,
        source_text_sha256=candidate.source_text_sha256,
        producer_id=producer_id,
        judgment=judgment,
        execution_status=execution_status,
        evidence_record_id=evidence_record_id,
        execution_record_ids=execution_record_ids,
        terminal_trace_id=terminal_trace_id,
        mapping_policy_id=mapping_policy_id,
        diagnostics=diagnostics,
    )


def canonical_organization_qualification_decision_json(
    decision: OrganizationQualificationDecision,
) -> str:
    """Serialize one semantic decision canonically for retained evidence."""
    return json.dumps(asdict(decision), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _id(prefix: str, *values: str) -> str:
    payload = "\x1f".join(values).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _require_ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"Qualification {label} must be ordered and distinct.")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
