"""Stage-local mention and reference evaluation for the HSQ-7 Gold catalogs."""

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

from kotekomi_pipelines.task_allocation_evaluation import (
    TaskAllocationEvaluatorCorrection,
    TaskAllocationEvaluatorCorrectionCatalog,
    TaskAllocationGoldCatalog,
    TaskAllocationItem,
    load_task_allocation_gold,
)

type StageLocalPhase = Literal["development", "validation"]


class StageLocalCatalogPin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        path = Path(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Stage-local pinned paths must be repository-relative and contained.")
        return self


class StageLocalSplit(BaseModel):
    """Pinned 20/20 split with SourceSegment-level leakage prevention."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_stage_local_split_v1", "hsq_stage_local_split_v2"]
    catalogs: tuple[StageLocalCatalogPin, ...]
    evaluator_corrections: StageLocalCatalogPin | None = None
    development_item_ids: tuple[Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")], ...]
    validation_item_ids: tuple[Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")], ...]

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if len(self.catalogs) != 2:
            raise ValueError("Stage-local evaluation requires exactly two Gold catalogs.")
        if (self.schema_version == "hsq_stage_local_split_v2") != (
            self.evaluator_corrections is not None
        ):
            raise ValueError(
                "Stage-local split v2 requires one evaluator-correction pin, and v1 forbids it."
            )
        if len(self.development_item_ids) != 20 or len(self.validation_item_ids) != 20:
            raise ValueError("Stage-local evaluation requires a 20/20 item split.")
        development = set(self.development_item_ids)
        validation = set(self.validation_item_ids)
        if len(development) != 20 or len(validation) != 20 or development & validation:
            raise ValueError("Stage-local item partitions must be distinct and non-overlapping.")
        return self


class StageLocalReferenceExpectation(BaseModel):
    """Effective source-bound reference oracle after explicit evaluator corrections."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    reference_text: Annotated[str, Field(min_length=1)]
    accepted_antecedent_texts: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if not self.accepted_antecedent_texts or len(set(self.accepted_antecedent_texts)) != len(
            self.accepted_antecedent_texts
        ):
            raise ValueError("Effective antecedent alternatives must be non-empty and distinct.")
        return self


class StageLocalInput(BaseModel):
    """Exact authoritative input and Gold expectations for one item."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    phase: StageLocalPhase
    catalog_id: str
    item: TaskAllocationItem
    focus_entity_name: str
    focus_record_type: Literal["Actor", "Organization"]
    source_text: str
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    expected_references: tuple[StageLocalReferenceExpectation, ...]

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Stage-local source text does not match its SHA-256.")
        if self.item.source_segment_sha256 != self.source_text_sha256:
            raise ValueError("Stage-local item and source text identify different segments.")
        if tuple(item.reference_text for item in self.expected_references) != tuple(
            item.reference_text for item in self.item.expected_references
        ):
            raise ValueError("Effective reference expectations do not match the Gold item.")
        if any(
            value not in self.source_text
            for expectation in self.expected_references
            for value in expectation.accepted_antecedent_texts
        ):
            raise ValueError("Effective antecedent text is absent from its SourceSegment.")
        return self


class StageLocalCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    check_id: str
    stage_id: str
    passed: bool
    expected: object
    actual: object


class StageLocalCaseEvaluation(BaseModel):
    """Ordered first-failure evaluation for one Gold item."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: str
    phase: StageLocalPhase
    source_text_sha256: str
    checks: tuple[StageLocalCheck, ...]
    first_failed_stage: str | None
    passed: bool

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        first_failure = next((item.stage_id for item in self.checks if not item.passed), None)
        if self.first_failed_stage != first_failure or self.passed != (first_failure is None):
            raise ValueError("Stage-local case outcome does not match its ordered checks.")
        return self


class StageLocalBoundaryContractCase(BaseModel):
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
                raise ValueError(f"Stage-local boundary {label} must be ordered and distinct.")
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


class StageLocalBoundaryContractSummary(BaseModel):
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
    cases: tuple[StageLocalBoundaryContractCase, ...]

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
                raise ValueError(f"Stage-local boundary {field_name} drifted.")
        if self.contract_complete != all(item.contract_complete for item in cases):
            raise ValueError("Boundary contract summary does not match its cases.")
        return self


class StageLocalPhaseReport(BaseModel):
    """Auditable mention/reference result for one split phase."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_stage_local_phase_report_v2"] = "hsq_stage_local_phase_report_v2"
    phase: StageLocalPhase
    item_count: int
    unique_source_segment_count: int
    passed_count: int
    first_failed_stage_counts: dict[str, int]
    producer_elapsed_milliseconds: dict[str, int]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    optional_experiments: dict[str, str]
    optional_experiment_measurements: dict[str, int] = Field(default_factory=dict)
    boundary_contract: StageLocalBoundaryContractSummary
    cases: tuple[StageLocalCaseEvaluation, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.item_count != len(self.cases):
            raise ValueError("Stage-local report item count drifted.")
        if self.passed_count != sum(item.passed for item in self.cases):
            raise ValueError("Stage-local report pass count drifted.")
        counts: dict[str, int] = {}
        for item in self.cases:
            if item.first_failed_stage is not None:
                counts[item.first_failed_stage] = counts.get(item.first_failed_stage, 0) + 1
        if self.first_failed_stage_counts != dict(sorted(counts.items())):
            raise ValueError("Stage-local first-failure counts drifted.")
        return self


def load_stage_local_inputs(
    split_path: Path,
    *,
    repository_root: Path,
) -> tuple[StageLocalSplit, tuple[StageLocalInput, ...]]:
    """Validate catalog pins, split coverage, and SourceSegment leakage."""
    split = StageLocalSplit.model_validate_json(split_path.read_bytes())
    catalogs: list[TaskAllocationGoldCatalog] = []
    for pin in split.catalogs:
        catalog_path = repository_root / pin.path
        payload = catalog_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != pin.sha256:
            raise ValueError(f"Stage-local Gold catalog pin drifted: {pin.path}")
        catalogs.append(load_task_allocation_gold(catalog_path))
    by_item: dict[str, tuple[TaskAllocationGoldCatalog, TaskAllocationItem, str]] = {}
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
    corrections: dict[tuple[str, str], TaskAllocationEvaluatorCorrection] = {}
    if split.evaluator_corrections is not None:
        correction_path = repository_root / split.evaluator_corrections.path
        correction_payload = correction_path.read_bytes()
        if hashlib.sha256(correction_payload).hexdigest() != split.evaluator_corrections.sha256:
            raise ValueError(
                f"Stage-local evaluator-correction pin drifted: {split.evaluator_corrections.path}"
            )
        correction_catalog = TaskAllocationEvaluatorCorrectionCatalog.model_validate_json(
            correction_payload
        )
        for correction in correction_catalog.corrections:
            target = by_item.get(correction.item_id)
            if target is None:
                raise ValueError("Evaluator correction references an unknown Gold item.")
            _, item, source_text = target
            expected_reference = next(
                (
                    expectation
                    for expectation in item.expected_references
                    if expectation.reference_text == correction.reference_text
                ),
                None,
            )
            if expected_reference is None:
                raise ValueError("Evaluator correction references an unknown Gold reference.")
            if (
                correction.source_text_sha256 != item.source_segment_sha256
                or correction.previous_antecedent_text != expected_reference.antecedent_text
            ):
                raise ValueError("Evaluator correction does not match its parent Gold contract.")
            if any(value not in source_text for value in correction.accepted_antecedent_texts):
                raise ValueError("Evaluator correction names text absent from its SourceSegment.")
            corrections[(correction.item_id, correction.reference_text)] = correction
    expected_ids = set(by_item)
    actual_ids = set(split.development_item_ids) | set(split.validation_item_ids)
    if actual_ids != expected_ids:
        raise ValueError("Stage-local split does not cover the forty Gold items exactly.")
    development_sha = {
        by_item[item_id][1].source_segment_sha256 for item_id in split.development_item_ids
    }
    validation_sha = {
        by_item[item_id][1].source_segment_sha256 for item_id in split.validation_item_ids
    }
    overlap = development_sha & validation_sha
    if overlap:
        raise ValueError(
            "Stage-local SourceSegment leakage crosses split phases: " + ", ".join(sorted(overlap))
        )
    phase_by_id: dict[str, StageLocalPhase] = {
        **{item_id: "development" for item_id in split.development_item_ids},
        **{item_id: "validation" for item_id in split.validation_item_ids},
    }
    inputs = tuple(
        StageLocalInput(
            phase=phase_by_id[item_id],
            catalog_id=catalog.catalog_id,
            item=item,
            focus_entity_name=catalog.focus_entity.name,
            focus_record_type=catalog.focus_entity.record_type,
            source_text=source_text,
            source_text_sha256=item.source_segment_sha256,
            expected_references=tuple(
                StageLocalReferenceExpectation(
                    reference_text=expectation.reference_text,
                    accepted_antecedent_texts=(
                        corrections[
                            (item.item_id, expectation.reference_text)
                        ].accepted_antecedent_texts
                        if (item.item_id, expectation.reference_text) in corrections
                        else (expectation.antecedent_text,)
                    ),
                )
                for expectation in item.expected_references
            ),
        )
        for item_id, (catalog, item, source_text) in sorted(by_item.items())
    )
    return split, inputs


def evaluate_stage_local_case(
    stage_input: StageLocalInput,
    mention: HybridExtractionPreview,
    references: HybridReferencePreview | None,
) -> StageLocalCaseEvaluation:
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
        StageLocalCheck(
            check_id="focus_mention",
            stage_id="mention_proposal",
            passed=bool(focus_candidates),
            expected=sorted(accepted_focus_literals),
            actual=[item.text for item in target_candidates],
        ),
        StageLocalCheck(
            check_id="focus_boundary",
            stage_id="mention_boundary_reconciliation",
            passed=bool(reconciled_focus),
            expected="at least one focus candidate retained for deterministic or semantic routing",
            actual=[item.text for item in reconciled_focus],
        ),
        StageLocalCheck(
            check_id="focus_boundary_adjudication",
            stage_id="mention_boundary_adjudication",
            passed=bool(selected_focus),
            expected="at least one effective focus candidate",
            actual=[item.text for item in selected_focus],
        ),
        StageLocalCheck(
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
            StageLocalCheck(
                check_id=f"reference_marker_{ordinal}",
                stage_id="reference_marker",
                passed=bool(reference_candidates),
                expected=expectation.reference_text,
                actual=[item.text for item in reference_candidates],
            )
        )
        checks.append(
            StageLocalCheck(
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
            StageLocalCheck(
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
    return StageLocalCaseEvaluation(
        item_id=stage_input.item.item_id,
        phase=stage_input.phase,
        source_text_sha256=stage_input.source_text_sha256,
        checks=ordered,
        first_failed_stage=first_failure,
        passed=first_failure is None,
    )


def build_stage_local_report(
    *,
    phase: StageLocalPhase,
    evaluations: tuple[StageLocalCaseEvaluation, ...],
    producer_elapsed_milliseconds: dict[str, int],
    boundary_contract: StageLocalBoundaryContractSummary,
    optional_experiment_measurements: dict[str, int] | None = None,
) -> StageLocalPhaseReport:
    failures: dict[str, int] = {}
    for item in evaluations:
        if item.first_failed_stage is not None:
            failures[item.first_failed_stage] = failures.get(item.first_failed_stage, 0) + 1
    return StageLocalPhaseReport(
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


def evaluate_stage_local_boundary_contract(
    previews: tuple[HybridExtractionPreview, ...],
) -> StageLocalBoundaryContractSummary:
    """Evaluate every ambiguous component once, independently from focus-item Gold."""
    segment_digests: set[str] = set()
    cases: list[StageLocalBoundaryContractCase] = []
    for preview in previews:
        preview_digests = {item.source_text_sha256 for item in preview.candidates}
        overlap = segment_digests & preview_digests
        if overlap:
            raise ValueError(
                "Stage-local boundary contract received duplicate SourceSegment evidence: "
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
                StageLocalBoundaryContractCase(
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
    return StageLocalBoundaryContractSummary(
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


def _focus_literals(stage_input: StageLocalInput) -> set[str]:
    names = {stage_input.focus_entity_name}
    if stage_input.focus_record_type == "Actor":
        names.add(stage_input.focus_entity_name.rsplit(" ", maxsplit=1)[-1])
    return {_normalized_entity_literal(item) for item in names}


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
