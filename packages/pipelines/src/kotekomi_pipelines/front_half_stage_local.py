"""Front-half mention and reference evaluation for the reviewed HSQ corpus."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal, Self, cast

from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V3,
    paragraph_source_segments,
)
from kotekomi_application.hybrid_document_references import HybridReferencePreview
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    MentionBoundaryCandidateStatus,
    effective_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    MentionBoundaryStatus,
    Referentiality,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.evaluation_contracts import EvaluationPhase


class FrontHalfSource(BaseModel):
    """One exact paragraph used by Front-Half Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: Annotated[str, Field(min_length=1)]
    paragraph_ordinal: Annotated[int, Field(ge=0)]
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    source_text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Front-Half source digest does not match its exact text.")
        return self


class FrontHalfFocusEntity(BaseModel):
    """The entity whose mention boundary each catalog evaluates."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: Annotated[str, Field(min_length=1)]
    record_type: Literal["Actor", "Organization"]
    accepted_source_literals: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_literals(self) -> Self:
        if not self.accepted_source_literals or len(set(self.accepted_source_literals)) != len(
            self.accepted_source_literals
        ):
            raise ValueError("Front-Half focus literals must be non-empty and distinct.")
        return self


class FrontHalfReferenceExpectation(BaseModel):
    """One exact reference and its accepted exact antecedent texts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    reference_text: Annotated[str, Field(min_length=1)]
    accepted_antecedent_texts: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if not self.accepted_antecedent_texts or len(set(self.accepted_antecedent_texts)) != len(
            self.accepted_antecedent_texts
        ):
            raise ValueError("Front-Half antecedent alternatives must be non-empty and distinct.")
        return self


class FrontHalfGoldItem(BaseModel):
    """One reviewed mention and reference expectation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")]
    source_id: Annotated[str, Field(min_length=1)]
    source_segment_label: Annotated[str, Field(pattern=r"^s[1-9][0-9]*$")]
    source_segment_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    expected_summary: Annotated[str, Field(min_length=1)]
    expected_references: tuple[FrontHalfReferenceExpectation, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        references = tuple(item.reference_text for item in self.expected_references)
        if len(set(references)) != len(references):
            raise ValueError("Front-Half reference expectations must be distinct.")
        return self


class FrontHalfGoldCatalog(BaseModel):
    """Twenty reviewed source cases for one focus entity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_front_half_gold_v1"] = "hsq_front_half_gold_v1"
    catalog_id: Annotated[str, Field(min_length=1)]
    fixture_path: Annotated[str, Field(min_length=1)]
    fixture_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    focus_entity: FrontHalfFocusEntity
    sources: tuple[FrontHalfSource, ...]
    items: tuple[FrontHalfGoldItem, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        if len(self.items) != 20:
            raise ValueError("Front-Half Gold requires exactly twenty items.")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("Front-Half Gold item IDs must be distinct.")
        sources = {item.source_id: item for item in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Front-Half source IDs must be distinct.")
        for item in self.items:
            source = sources.get(item.source_id)
            if source is None:
                raise ValueError("Front-Half Gold item references an unknown source.")
            segments = {
                segment.label: segment
                for segment in paragraph_source_segments(source.source_text, PARAGRAPH_SEGMENT_V3)
            }
            segment = segments.get(item.source_segment_label)
            if segment is None:
                raise ValueError("Front-Half Gold item references an unknown SourceSegment.")
            if hashlib.sha256(segment.exact_text.encode()).hexdigest() != (
                item.source_segment_sha256
            ):
                raise ValueError("Front-Half SourceSegment digest does not match.")
            if not any(
                literal in segment.exact_text
                for literal in self.focus_entity.accepted_source_literals
            ):
                raise ValueError("Front-Half SourceSegment omits its focus entity.")
            for expectation in item.expected_references:
                if expectation.reference_text not in segment.exact_text:
                    raise ValueError("Front-Half reference is absent from its SourceSegment.")
                if any(
                    value not in segment.exact_text
                    for value in expectation.accepted_antecedent_texts
                ):
                    raise ValueError("Front-Half antecedent is absent from its SourceSegment.")
        return self


def load_front_half_gold(path: Path) -> FrontHalfGoldCatalog:
    """Load one strict Front-Half Gold catalog."""
    return FrontHalfGoldCatalog.model_validate_json(path.read_bytes())


class FrontHalfCatalogPin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        path = Path(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Front-Half pinned paths must be repository-relative and contained.")
        return self


class FrontHalfSplit(BaseModel):
    """Pinned 20/20 split with SourceSegment-level leakage prevention."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_front_half_split_v1"] = "hsq_front_half_split_v1"
    catalogs: tuple[FrontHalfCatalogPin, ...]
    development_item_ids: tuple[Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")], ...]
    validation_item_ids: tuple[Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")], ...]

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if len(self.catalogs) != 2:
            raise ValueError("Front-Half evaluation requires exactly two Gold catalogs.")
        if len(self.development_item_ids) != 20 or len(self.validation_item_ids) != 20:
            raise ValueError("Front-Half evaluation requires a 20/20 item split.")
        development = set(self.development_item_ids)
        validation = set(self.validation_item_ids)
        if len(development) != 20 or len(validation) != 20 or development & validation:
            raise ValueError("Front-Half item partitions must be distinct and non-overlapping.")
        return self


class FrontHalfInput(BaseModel):
    """Exact authoritative input and Gold expectations for one item."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: EvaluationPhase
    catalog_id: str
    item: FrontHalfGoldItem
    focus_entity_name: str
    focus_record_type: Literal["Actor", "Organization"]
    accepted_focus_literals: tuple[Annotated[str, Field(min_length=1)], ...]
    source_text: str
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @property
    def expected_references(self) -> tuple[FrontHalfReferenceExpectation, ...]:
        return self.item.expected_references

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Front-Half source text does not match its SHA-256.")
        if self.item.source_segment_sha256 != self.source_text_sha256:
            raise ValueError("Front-Half item and source text identify different segments.")
        if any(
            value not in self.source_text
            for expectation in self.expected_references
            for value in expectation.accepted_antecedent_texts
        ):
            raise ValueError("Front-Half antecedent text is absent from its SourceSegment.")
        return self


class FrontHalfCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    check_id: str
    stage_id: str
    passed: bool
    expected: object
    actual: object


class FrontHalfCaseEvaluation(BaseModel):
    """Ordered first-failure evaluation for one Gold item."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: str
    phase: EvaluationPhase
    source_text_sha256: str
    checks: tuple[FrontHalfCheck, ...]
    first_failed_stage: str | None
    passed: bool

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        first_failure = next((item.stage_id for item in self.checks if not item.passed), None)
        if self.first_failed_stage != first_failure or self.passed != (first_failure is None):
            raise ValueError("Front-Half case outcome does not match its ordered checks.")
        return self


class FrontHalfBoundaryContractCase(BaseModel):
    """Candidate-completeness evidence for one ambiguous boundary component."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    boundary_decision_id: Annotated[str, Field(min_length=1)]
    adjudication_id: str | None
    candidate_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    supplied_candidate_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    deterministic_complete_candidate_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    terminal_judgment_candidate_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    unresolved_candidate_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    rejection_codes: tuple[Annotated[str, Field(min_length=1)], ...]
    contract_complete: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("candidate IDs", self.candidate_ids),
            ("supplied candidate IDs", self.supplied_candidate_ids),
            ("deterministic candidate IDs", self.deterministic_complete_candidate_ids),
            ("terminal judgment candidate IDs", self.terminal_judgment_candidate_ids),
            ("unresolved candidate IDs", self.unresolved_candidate_ids),
        ):
            if tuple(sorted(values)) != values or len(set(values)) != len(values):
                raise ValueError(f"Front-Half boundary {label} must be ordered and distinct.")
        supplied = set(self.supplied_candidate_ids)
        deterministic = set(self.deterministic_complete_candidate_ids)
        terminal = set(self.terminal_judgment_candidate_ids)
        unresolved = set(self.unresolved_candidate_ids)
        if deterministic & supplied:
            raise ValueError("A deterministic boundary candidate cannot also be model-visible.")
        if terminal & unresolved or terminal | unresolved != supplied:
            raise ValueError(
                "Terminal and unresolved judgments must partition supplied candidates."
            )
        if deterministic | supplied != set(self.candidate_ids):
            raise ValueError("Boundary contract evidence must cover its parent candidates.")
        expected_complete = (
            self.adjudication_id is not None
            and not unresolved
            and not self.rejection_codes
            and len(terminal) == len(supplied)
        )
        if self.contract_complete != expected_complete:
            raise ValueError("Boundary contract completion does not match its evidence.")
        return self


class FrontHalfBoundaryContractSummary(BaseModel):
    """All-candidate output-contract coverage, independent of Gold focus accuracy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ambiguous_component_count: Annotated[int, Field(ge=0)]
    adjudication_count: Annotated[int, Field(ge=0)]
    supplied_candidate_count: Annotated[int, Field(ge=0)]
    valid_terminal_judgment_count: Annotated[int, Field(ge=0)]
    deterministic_completion_count: Annotated[int, Field(ge=0)]
    unresolved_candidate_count: Annotated[int, Field(ge=0)]
    rejected_line_count: Annotated[int, Field(ge=0)]
    duplicate_label_count: Annotated[int, Field(ge=0)]
    unknown_label_count: Annotated[int, Field(ge=0)]
    contract_complete: bool
    cases: tuple[FrontHalfBoundaryContractCase, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        cases = self.cases
        expected = {
            "ambiguous_component_count": len(cases),
            "adjudication_count": sum(item.adjudication_id is not None for item in cases),
            "supplied_candidate_count": sum(len(item.supplied_candidate_ids) for item in cases),
            "valid_terminal_judgment_count": sum(
                len(item.terminal_judgment_candidate_ids) for item in cases
            ),
            "deterministic_completion_count": sum(
                len(item.deterministic_complete_candidate_ids) for item in cases
            ),
            "unresolved_candidate_count": sum(len(item.unresolved_candidate_ids) for item in cases),
            "rejected_line_count": sum(len(item.rejection_codes) for item in cases),
            "duplicate_label_count": sum(
                item.rejection_codes.count("duplicate_candidate_label") for item in cases
            ),
            "unknown_label_count": sum(
                item.rejection_codes.count("unknown_candidate_label") for item in cases
            ),
        }
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise ValueError(f"Front-Half boundary {field_name} drifted.")
        if self.contract_complete != all(item.contract_complete for item in cases):
            raise ValueError("Boundary contract summary does not match its cases.")
        return self


class FrontHalfPhaseReport(BaseModel):
    """Auditable mention/reference result for one split phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_front_half_phase_report_v1"] = "hsq_front_half_phase_report_v1"
    phase: EvaluationPhase
    item_count: int
    unique_source_segment_count: int
    passed_count: int
    first_failed_stage_counts: dict[str, int]
    producer_elapsed_milliseconds: dict[str, int]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    optional_experiments: dict[str, str]
    optional_experiment_measurements: dict[str, int] = Field(default_factory=dict)
    boundary_contract: FrontHalfBoundaryContractSummary
    cases: tuple[FrontHalfCaseEvaluation, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.item_count != len(self.cases):
            raise ValueError("Front-Half report item count drifted.")
        if self.passed_count != sum(item.passed for item in self.cases):
            raise ValueError("Front-Half report pass count drifted.")
        counts: dict[str, int] = {}
        for item in self.cases:
            if item.first_failed_stage is not None:
                counts[item.first_failed_stage] = counts.get(item.first_failed_stage, 0) + 1
        if self.first_failed_stage_counts != dict(sorted(counts.items())):
            raise ValueError("Front-Half first-failure counts drifted.")
        return self


class FrontHalfPartitionSummary(BaseModel):
    """One current Front-Half Gold partition summary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: EvaluationPhase
    item_count: Annotated[int, Field(ge=0)]
    passed_count: Annotated[int, Field(ge=0)]
    first_failed_stage_counts: dict[str, int]
    passed: bool


class FrontHalfEvaluationReport(BaseModel):
    """Current mention/reference evaluation over both reviewed partitions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_front_half_evaluation_v1"] = "hsq_front_half_evaluation_v1"
    item_count: Annotated[int, Field(ge=0)]
    passed_count: Annotated[int, Field(ge=0)]
    partitions: tuple[FrontHalfPartitionSummary, ...]
    cases: tuple[FrontHalfCaseEvaluation, ...]
    passed: bool

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if tuple(item.phase for item in self.partitions) != ("development", "validation"):
            raise ValueError("Front-Half evaluation requires both ordered partitions.")
        if self.item_count != len(self.cases) or self.passed_count != sum(
            item.passed for item in self.cases
        ):
            raise ValueError("Front-Half evaluation counts drifted.")
        for partition in self.partitions:
            cases = tuple(item for item in self.cases if item.phase == partition.phase)
            if partition != _front_half_partition(partition.phase, cases):
                raise ValueError("Front-Half partition summary drifted.")
        if self.passed != all(item.passed for item in self.cases):
            raise ValueError("Front-Half evaluation pass state drifted.")
        return self


def build_front_half_evaluation_report(
    evaluations: tuple[FrontHalfCaseEvaluation, ...],
) -> FrontHalfEvaluationReport:
    """Build the current read-only Front-Half report."""
    ordered = tuple(sorted(evaluations, key=lambda item: item.item_id))
    partitions = tuple(
        _front_half_partition(
            phase,
            tuple(item for item in ordered if item.phase == phase),
        )
        for phase in ("development", "validation")
    )
    return FrontHalfEvaluationReport(
        item_count=len(ordered),
        passed_count=sum(item.passed for item in ordered),
        partitions=partitions,
        cases=ordered,
        passed=all(item.passed for item in ordered),
    )


def _front_half_partition(
    phase: EvaluationPhase,
    cases: tuple[FrontHalfCaseEvaluation, ...],
) -> FrontHalfPartitionSummary:
    failures: dict[str, int] = {}
    for item in cases:
        if item.first_failed_stage is not None:
            failures[item.first_failed_stage] = failures.get(item.first_failed_stage, 0) + 1
    return FrontHalfPartitionSummary(
        phase=phase,
        item_count=len(cases),
        passed_count=sum(item.passed for item in cases),
        first_failed_stage_counts=dict(sorted(failures.items())),
        passed=all(item.passed for item in cases),
    )


def load_front_half_inputs(
    split_path: Path,
    *,
    repository_root: Path,
) -> tuple[FrontHalfSplit, tuple[FrontHalfInput, ...]]:
    """Validate catalog pins, split coverage, and SourceSegment leakage."""
    split = FrontHalfSplit.model_validate_json(split_path.read_bytes())
    catalogs: list[FrontHalfGoldCatalog] = []
    for pin in split.catalogs:
        catalog_path = repository_root / pin.path
        payload = catalog_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != pin.sha256:
            raise ValueError(f"Front-Half Gold catalog pin drifted: {pin.path}")
        catalogs.append(load_front_half_gold(catalog_path))
    by_item: dict[str, tuple[FrontHalfGoldCatalog, FrontHalfGoldItem, str]] = {}
    for catalog in catalogs:
        sources = {item.source_id: item for item in catalog.sources}
        for item in catalog.items:
            source = sources[item.source_id]
            segment = next(
                value
                for value in paragraph_source_segments(source.source_text, PARAGRAPH_SEGMENT_V3)
                if value.label == item.source_segment_label
            )
            by_item[item.item_id] = (catalog, item, segment.exact_text)
    expected_ids = set(by_item)
    actual_ids = set(split.development_item_ids) | set(split.validation_item_ids)
    if actual_ids != expected_ids:
        raise ValueError("Front-Half split does not cover the forty Gold items exactly.")
    development_sha = {
        by_item[item_id][1].source_segment_sha256 for item_id in split.development_item_ids
    }
    validation_sha = {
        by_item[item_id][1].source_segment_sha256 for item_id in split.validation_item_ids
    }
    overlap = development_sha & validation_sha
    if overlap:
        raise ValueError(
            "Front-Half SourceSegment leakage crosses split phases: " + ", ".join(sorted(overlap))
        )
    phase_by_id: dict[str, EvaluationPhase] = {
        **{item_id: "development" for item_id in split.development_item_ids},
        **{item_id: "validation" for item_id in split.validation_item_ids},
    }
    inputs = tuple(
        FrontHalfInput(
            phase=phase_by_id[item_id],
            catalog_id=catalog.catalog_id,
            item=item,
            focus_entity_name=catalog.focus_entity.name,
            focus_record_type=catalog.focus_entity.record_type,
            accepted_focus_literals=catalog.focus_entity.accepted_source_literals,
            source_text=source_text,
            source_text_sha256=item.source_segment_sha256,
        )
        for item_id, (catalog, item, source_text) in sorted(by_item.items())
    )
    return split, inputs


def evaluate_front_half_case(
    stage_input: FrontHalfInput,
    mention: HybridExtractionPreview,
    references: HybridReferencePreview | None,
) -> FrontHalfCaseEvaluation:
    """Find the first faulty mention/reference boundary for one Gold item."""
    target_candidates = tuple(
        item
        for item in mention.candidates
        if item.source_text_sha256 == stage_input.source_text_sha256
    )
    accepted_focus_literals = _focus_literals(stage_input)
    focus_candidates = tuple(
        item
        for item in target_candidates
        if _normalized_entity_literal(item.text) in accepted_focus_literals
    )
    selected_ids = set(
        effective_mention_candidate_ids(
            mention.boundary_decisions,
            mention.boundary_adjudications,
        )
    )
    decision_by_candidate = {
        candidate_id: decision
        for decision in mention.boundary_decisions
        for candidate_id in decision.candidate_ids
    }
    reconciled_focus = tuple(
        item
        for item in focus_candidates
        if (
            (decision := decision_by_candidate[item.id]).status is MentionBoundaryStatus.AMBIGUOUS
            or item.id in decision.selected_candidate_ids
        )
    )
    selected_focus = tuple(item for item in focus_candidates if item.id in selected_ids)
    interpretation_by_candidate = {item.candidate_id: item for item in mention.interpretations}
    observation_by_id = {item.id: item for item in mention.observations}
    reference_marker_candidate_ids = {
        candidate.id
        for candidate in target_candidates
        if any(
            observation_by_id[observation_id].producer_id == "kotekomi_reference_marker_v1"
            for observation_id in candidate.observation_ids
        )
    }
    expected_kind = "person" if stage_input.focus_record_type == "Actor" else "organization"
    interpreted_focus = tuple(
        item
        for item in selected_focus
        if item.id in interpretation_by_candidate
        and interpretation_by_candidate[item.id].referentiality is Referentiality.SPECIFIC_ENTITY
        and interpretation_by_candidate[item.id].contextual_kind.value == expected_kind
    )
    checks = [
        FrontHalfCheck(
            check_id="focus_mention",
            stage_id="mention_proposal",
            passed=bool(focus_candidates),
            expected=sorted(accepted_focus_literals),
            actual=[item.text for item in target_candidates],
        ),
        FrontHalfCheck(
            check_id="focus_boundary",
            stage_id="mention_boundary_reconciliation",
            passed=bool(reconciled_focus),
            expected="at least one focus candidate retained for deterministic or semantic routing",
            actual=[item.text for item in reconciled_focus],
        ),
        FrontHalfCheck(
            check_id="focus_boundary_adjudication",
            stage_id="mention_boundary_adjudication",
            passed=bool(selected_focus),
            expected="at least one effective focus candidate",
            actual=[item.text for item in selected_focus],
        ),
        FrontHalfCheck(
            check_id="focus_interpretation",
            stage_id="mention_interpretation",
            passed=bool(interpreted_focus),
            expected={"referentiality": "specific_entity", "contextual_kind": expected_kind},
            actual=[
                interpretation_by_candidate[item.id].model_dump(mode="json")
                for item in selected_focus
                if item.id in interpretation_by_candidate
            ],
        ),
    ]
    for ordinal, expectation in enumerate(stage_input.expected_references, start=1):
        reference_candidates = tuple(
            item
            for item in target_candidates
            if _reference_literal_matches(item.text, expectation.reference_text)
        )
        selected_references = tuple(
            item for item in reference_candidates if item.id in selected_ids
        )
        routed_references = tuple(
            item
            for item in selected_references
            if item.id in reference_marker_candidate_ids
            or (
                item.id in interpretation_by_candidate
                and interpretation_by_candidate[item.id].referentiality is Referentiality.ANAPHORIC
            )
        )
        checks.append(
            FrontHalfCheck(
                check_id=f"reference_marker_{ordinal}",
                stage_id="reference_marker",
                passed=bool(reference_candidates),
                expected=expectation.reference_text,
                actual=[item.text for item in reference_candidates],
            )
        )
        checks.append(
            FrontHalfCheck(
                check_id=f"reference_routing_{ordinal}",
                stage_id="reference_routing",
                passed=bool(routed_references),
                expected="deterministic_reference_marker_or_anaphoric_interpretation",
                actual={
                    "routed_candidate_ids": [item.id for item in routed_references],
                    "deterministic_reference_marker_candidate_ids": sorted(
                        reference_marker_candidate_ids
                    ),
                    "interpretations": [
                        interpretation_by_candidate[item.id].model_dump(mode="json")
                        for item in selected_references
                        if item.id in interpretation_by_candidate
                    ],
                },
            )
        )
        decisions = ()
        antecedent_texts: list[str] = []
        if references is not None:
            candidate_ids = {item.id for item in routed_references}
            decisions = tuple(
                item
                for item in references.reference_decisions
                if item.candidate_id in candidate_ids
            )
            spans = {item.id: item for item in references.semantic_antecedent_spans}
            antecedent_texts = [
                spans[span_id].text
                for decision in decisions
                if decision.status.value == "resolved"
                for span_id in decision.antecedent_span_ids
                if span_id in spans
            ]
        checks.append(
            FrontHalfCheck(
                check_id=f"reference_resolution_{ordinal}",
                stage_id="reference_resolution",
                passed=any(
                    text in expectation.accepted_antecedent_texts for text in antecedent_texts
                ),
                expected=list(expectation.accepted_antecedent_texts),
                actual={
                    "antecedent_texts": antecedent_texts,
                    "decisions": [item.model_dump(mode="json") for item in decisions],
                },
            )
        )
    ordered = tuple(checks)
    first_failure = next((item.stage_id for item in ordered if not item.passed), None)
    return FrontHalfCaseEvaluation(
        item_id=stage_input.item.item_id,
        phase=stage_input.phase,
        source_text_sha256=stage_input.source_text_sha256,
        checks=ordered,
        first_failed_stage=first_failure,
        passed=first_failure is None,
    )


def build_front_half_report(
    *,
    phase: EvaluationPhase,
    evaluations: tuple[FrontHalfCaseEvaluation, ...],
    producer_elapsed_milliseconds: dict[str, int],
    boundary_contract: FrontHalfBoundaryContractSummary,
    optional_experiment_measurements: dict[str, int] | None = None,
) -> FrontHalfPhaseReport:
    failures: dict[str, int] = {}
    for item in evaluations:
        if item.first_failed_stage is not None:
            failures[item.first_failed_stage] = failures.get(item.first_failed_stage, 0) + 1
    return FrontHalfPhaseReport(
        phase=phase,
        item_count=len(evaluations),
        unique_source_segment_count=len({item.source_text_sha256 for item in evaluations}),
        passed_count=sum(item.passed for item in evaluations),
        first_failed_stage_counts=dict(sorted(failures.items())),
        producer_elapsed_milliseconds=dict(sorted(producer_elapsed_milliseconds.items())),
        optional_experiments={
            "source_alias_rescue": "measured_not_activated",
            "selective_interpretation": "not_activated_pending_correctness_gates",
        },
        optional_experiment_measurements=(optional_experiment_measurements or {}),
        boundary_contract=boundary_contract,
        cases=tuple(sorted(evaluations, key=lambda item: item.item_id)),
    )


def evaluate_front_half_boundary_contract(
    previews: tuple[HybridExtractionPreview, ...],
) -> FrontHalfBoundaryContractSummary:
    """Evaluate every ambiguous component once, independently from focus-item Gold."""
    segment_digests: set[str] = set()
    cases: list[FrontHalfBoundaryContractCase] = []
    for preview in previews:
        preview_digests = {item.source_text_sha256 for item in preview.candidates}
        overlap = segment_digests & preview_digests
        if overlap:
            raise ValueError(
                "Front-Half boundary contract received duplicate SourceSegment evidence: "
                + ", ".join(sorted(overlap))
            )
        segment_digests.update(preview_digests)
        candidate_by_id = {item.id: item for item in preview.candidates}
        adjudication_by_decision = {
            item.boundary_decision_id: item for item in preview.boundary_adjudications
        }
        trace_by_id = {item.id: item for item in preview.traces}
        boundary_trace_by_decision = {
            trace.input_record_ids[0]: trace
            for trace in preview.traces
            if trace.stage_id == "mention_boundary_adjudication" and trace.input_record_ids
        }
        for decision in preview.boundary_decisions:
            if decision.status is not MentionBoundaryStatus.AMBIGUOUS:
                continue
            candidate_ids = tuple(sorted(decision.candidate_ids))
            source_digests = {
                candidate_by_id[candidate_id].source_text_sha256
                for candidate_id in decision.candidate_ids
            }
            if len(source_digests) != 1:
                raise ValueError(
                    "One boundary component must have one authoritative source digest."
                )
            adjudication = adjudication_by_decision.get(decision.id)
            trace = (
                trace_by_id[adjudication.trace_id]
                if adjudication is not None
                else boundary_trace_by_decision.get(decision.id)
            )
            if trace is None:
                supplied_candidate_ids = candidate_ids
                deterministic_candidate_ids: tuple[str, ...] = ()
            else:
                supplied_candidate_ids = _boundary_trace_supplied_candidate_ids(trace.input)
                deterministic_candidate_ids = _boundary_trace_deterministic_candidate_ids(
                    trace.input
                )
            if set(supplied_candidate_ids) | set(deterministic_candidate_ids) != set(candidate_ids):
                raise ValueError("Boundary trace candidates do not match their parent decision.")
            if adjudication is None:
                terminal_candidate_ids: tuple[str, ...] = ()
                unresolved_candidate_ids = supplied_candidate_ids
                rejection_codes: tuple[str, ...] = ()
            else:
                status_by_candidate = {
                    item.candidate_id: item.status for item in adjudication.judgments
                }
                if set(status_by_candidate) != set(candidate_ids):
                    raise ValueError(
                        "Boundary adjudication judgments do not match their parent candidates."
                    )
                terminal_candidate_ids = tuple(
                    sorted(
                        candidate_id
                        for candidate_id in supplied_candidate_ids
                        if status_by_candidate[candidate_id]
                        in {
                            MentionBoundaryCandidateStatus.COMPLETE,
                            MentionBoundaryCandidateStatus.INCOMPLETE,
                            MentionBoundaryCandidateStatus.UNCLEAR,
                        }
                    )
                )
                unresolved_candidate_ids = tuple(
                    sorted(
                        candidate_id
                        for candidate_id in supplied_candidate_ids
                        if status_by_candidate[candidate_id]
                        is MentionBoundaryCandidateStatus.UNRESOLVED
                    )
                )
                rejection_codes = tuple(item.code for item in adjudication.rejected_lines)
            contract_complete = (
                adjudication is not None
                and not unresolved_candidate_ids
                and not rejection_codes
                and len(terminal_candidate_ids) == len(supplied_candidate_ids)
            )
            cases.append(
                FrontHalfBoundaryContractCase(
                    source_segment_id=decision.source_segment_id,
                    source_text_sha256=next(iter(source_digests)),
                    boundary_decision_id=decision.id,
                    adjudication_id=(adjudication.id if adjudication is not None else None),
                    candidate_ids=candidate_ids,
                    supplied_candidate_ids=tuple(sorted(supplied_candidate_ids)),
                    deterministic_complete_candidate_ids=tuple(sorted(deterministic_candidate_ids)),
                    terminal_judgment_candidate_ids=terminal_candidate_ids,
                    unresolved_candidate_ids=tuple(sorted(unresolved_candidate_ids)),
                    rejection_codes=rejection_codes,
                    contract_complete=contract_complete,
                )
            )
    ordered = tuple(
        sorted(cases, key=lambda item: (item.source_text_sha256, item.boundary_decision_id))
    )
    return FrontHalfBoundaryContractSummary(
        ambiguous_component_count=len(ordered),
        adjudication_count=sum(item.adjudication_id is not None for item in ordered),
        supplied_candidate_count=sum(len(item.supplied_candidate_ids) for item in ordered),
        valid_terminal_judgment_count=sum(
            len(item.terminal_judgment_candidate_ids) for item in ordered
        ),
        deterministic_completion_count=sum(
            len(item.deterministic_complete_candidate_ids) for item in ordered
        ),
        unresolved_candidate_count=sum(len(item.unresolved_candidate_ids) for item in ordered),
        rejected_line_count=sum(len(item.rejection_codes) for item in ordered),
        duplicate_label_count=sum(
            item.rejection_codes.count("duplicate_candidate_label") for item in ordered
        ),
        unknown_label_count=sum(
            item.rejection_codes.count("unknown_candidate_label") for item in ordered
        ),
        contract_complete=all(item.contract_complete for item in ordered),
        cases=ordered,
    )


def _boundary_trace_supplied_candidate_ids(
    value: Mapping[str, JsonValue],
) -> tuple[str, ...]:
    raw = value.get("candidate_labels")
    if not isinstance(raw, dict):
        raise ValueError("Boundary trace candidate labels are malformed.")
    labels = cast(dict[str, JsonValue], raw)
    if not all(isinstance(candidate_id, str) for candidate_id in labels.values()):
        raise ValueError("Boundary trace candidate labels are malformed.")
    return tuple(sorted(cast(str, item) for item in labels.values()))


def _boundary_trace_deterministic_candidate_ids(
    value: Mapping[str, JsonValue],
) -> tuple[str, ...]:
    raw = value.get("deterministic_complete_candidate_ids")
    if not isinstance(raw, list):
        raise ValueError("Boundary trace deterministic candidate IDs are malformed.")
    values = cast(list[JsonValue], raw)
    if not all(isinstance(item, str) for item in values):
        raise ValueError("Boundary trace deterministic candidate IDs are malformed.")
    return tuple(sorted(cast(str, item) for item in values))


def _focus_literals(stage_input: FrontHalfInput) -> set[str]:
    return {_normalized_entity_literal(item) for item in stage_input.accepted_focus_literals}


def _reference_literal_matches(actual: str, expected: str) -> bool:
    normalized_actual = " ".join(actual.casefold().split())
    normalized_expected = " ".join(expected.casefold().split())
    return (
        normalized_actual == normalized_expected
        or normalized_actual == f"the {normalized_expected}"
    )


def _normalized_entity_literal(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    if normalized.endswith(("'s", "’s")):
        normalized = normalized[:-2]
    return normalized.removeprefix("the ")
