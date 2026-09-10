"""Frozen Gold contracts and exact stage evidence for HSQ-7 task allocation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    WikiEventPresentation,
)
from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V3,
    paragraph_source_segments,
)
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    MentionBoundaryAdjudication,
    effective_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import MentionBoundaryDecision
from kotekomi_domain import HYBRID_EVENT_SEMANTICS_V4
from pydantic import BaseModel, ConfigDict, Field, model_validator

type CatalogRole = Literal["development", "held_out"]
type ExpectedRoute = Literal["event", "standing_fact", "typed_ontology_gap"]
type ExpectedDisposition = Literal["proposed", "typed_ontology_gap"]

TASK_ALLOCATION_CASES = frozenset(
    {
        "source_occurrence_selection",
        "bounded_frame_and_roles",
        "proposition_gate",
        "parallel_routes",
        "reference_challenge",
        "typed_ontology_gap",
    }
)


class TaskAllocationSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: Annotated[str, Field(min_length=1)]
    paragraph_ordinal: Annotated[int, Field(ge=0)]
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    source_text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Task-allocation source digest does not match its exact text.")
        return self


class TaskAllocationRoleExpectation(BaseModel):
    """One role and its acceptable source-backed target boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    frame_role_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")]
    accepted_source_texts: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_expectation(self) -> Self:
        if not self.accepted_source_texts or len(set(self.accepted_source_texts)) != len(
            self.accepted_source_texts
        ):
            raise ValueError("Role target alternatives must be non-empty and distinct.")
        return self


class TaskAllocationQualifierExpectation(BaseModel):
    """One source-backed event qualifier expected from presentation selection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["place", "time"]
    relation: Literal["before", "during", "after", "at"] | None = None
    accepted_source_texts: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_expectation(self) -> Self:
        if not self.accepted_source_texts or len(set(self.accepted_source_texts)) != len(
            self.accepted_source_texts
        ):
            raise ValueError("Qualifier alternatives must be non-empty and distinct.")
        if (self.kind == "time") != (self.relation is not None):
            raise ValueError("Only a time qualifier requires a temporal relation.")
        return self


class TaskAllocationReferenceExpectation(BaseModel):
    """One pronoun or generic expression and its source-backed antecedent."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    reference_text: Annotated[str, Field(min_length=1)]
    antecedent_text: Annotated[str, Field(min_length=1)]


class TaskAllocationEvaluatorCorrection(BaseModel):
    """One explicit evaluator amendment that does not alter Gold or system output."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    correction_id: Annotated[str, Field(min_length=1)]
    classification: Literal["evaluator_false_negative"]
    item_id: Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")]
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    reference_text: Annotated[str, Field(min_length=1)]
    previous_antecedent_text: Annotated[str, Field(min_length=1)]
    accepted_antecedent_texts: tuple[Annotated[str, Field(min_length=1)], ...]
    observed_antecedent_texts: tuple[Annotated[str, Field(min_length=1)], ...]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        for label, values in (
            ("accepted antecedents", self.accepted_antecedent_texts),
            ("observed antecedents", self.observed_antecedent_texts),
        ):
            if not values or len(set(values)) != len(values):
                raise ValueError(f"Evaluator correction {label} must be non-empty and distinct.")
        return self


class TaskAllocationEvaluatorCorrectionCatalog(BaseModel):
    """Pinned amendments to a finalized evaluator with parent evidence identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_stage_local_evaluator_corrections_v1"]
    parent_validation_manifest_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    parent_validation_report_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    corrections: tuple[TaskAllocationEvaluatorCorrection, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        keys = [(item.item_id, item.reference_text) for item in self.corrections]
        if not self.corrections or len(set(keys)) != len(keys):
            raise ValueError("Evaluator corrections must be non-empty and uniquely targeted.")
        return self


class TaskAllocationStandingExpectation(BaseModel):
    """The minimum source-backed triple shape required from a standing route."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    subject_text: Annotated[str, Field(min_length=1)]
    relation_terms: tuple[Annotated[str, Field(min_length=1)], ...]
    object_text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_expectation(self) -> Self:
        if not self.relation_terms or len(set(self.relation_terms)) != len(self.relation_terms):
            raise ValueError("Standing-fact relation terms must be non-empty and distinct.")
        return self


class TaskAllocationItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")]
    source_id: Annotated[str, Field(min_length=1)]
    source_segment_label: Annotated[str, Field(pattern=r"^s[1-9][0-9]*$")]
    source_segment_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    expected_summary: Annotated[str, Field(min_length=1)]
    expected_route: ExpectedRoute
    expected_trigger_head_text: str | None = None
    accepted_trigger_expression_texts: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    expected_frame_id: str | None = None
    expected_gap_code: str | None = None
    expected_roles: tuple[TaskAllocationRoleExpectation, ...] = ()
    expected_qualifiers: tuple[TaskAllocationQualifierExpectation, ...] = ()
    expected_references: tuple[TaskAllocationReferenceExpectation, ...] = ()
    expected_standing_fact: TaskAllocationStandingExpectation | None = None
    expected_polarity: Literal["affirmed", "negated"] | None = None
    expected_modality: (
        Literal["actual", "planned", "possible", "uncertain", "recommended", "hypothetical"] | None
    ) = None
    expected_attribution: (
        Literal["mention_candidate", "source_narrator", "source_span", "unresolved"] | None
    ) = None
    expected_disposition: ExpectedDisposition
    allocation_cases: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_expectation(self) -> Self:
        if not self.allocation_cases or len(set(self.allocation_cases)) != len(
            self.allocation_cases
        ):
            raise ValueError("Task-allocation cases must be non-empty and distinct.")
        unknown = set(self.allocation_cases) - TASK_ALLOCATION_CASES
        if unknown:
            raise ValueError(f"Task-allocation item uses unknown cases: {sorted(unknown)}")
        if self.expected_route == "event":
            if (
                self.expected_trigger_head_text is None
                or not self.accepted_trigger_expression_texts
                or self.expected_frame_id is None
            ):
                raise ValueError("An event expectation requires trigger and frame.")
            if (
                self.expected_gap_code is not None
                or self.expected_disposition != "proposed"
                or self.expected_standing_fact is not None
                or self.expected_polarity is None
                or self.expected_modality is None
                or self.expected_attribution is None
            ):
                raise ValueError("An event expectation cannot also be an ontology gap.")
            if not self.expected_roles:
                raise ValueError("An event expectation requires its source-backed role contract.")
        elif self.expected_route == "standing_fact":
            if any(
                value is not None
                for value in (
                    self.expected_trigger_head_text,
                    self.accepted_trigger_expression_texts or None,
                    self.expected_frame_id,
                    self.expected_gap_code,
                    self.expected_polarity,
                    self.expected_modality,
                    self.expected_attribution,
                )
            ) or (
                self.expected_disposition != "proposed"
                or self.expected_standing_fact is None
                or self.expected_roles
                or self.expected_qualifiers
            ):
                raise ValueError(
                    "A standing-fact expectation must contain only standing semantics."
                )
        elif (
            self.expected_trigger_head_text is None
            or not self.accepted_trigger_expression_texts
            or self.expected_gap_code is None
            or self.expected_disposition != "typed_ontology_gap"
            or self.expected_roles
            or self.expected_qualifiers
            or self.expected_standing_fact is not None
            or self.expected_polarity is not None
            or self.expected_modality is not None
            or self.expected_attribution is not None
        ):
            raise ValueError(
                "A typed ontology gap requires a trigger and one explicit gap outcome."
            )
        if len({item.frame_role_id for item in self.expected_roles}) != len(self.expected_roles):
            raise ValueError("Task-allocation role expectations must be distinct.")
        if len(
            {
                (item.kind, item.relation, item.accepted_source_texts)
                for item in self.expected_qualifiers
            }
        ) != len(self.expected_qualifiers):
            raise ValueError("Task-allocation qualifier expectations must be distinct.")
        if len({item.reference_text for item in self.expected_references}) != len(
            self.expected_references
        ):
            raise ValueError("Task-allocation reference expectations must be distinct.")
        return self


class TaskAllocationFocusEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: Annotated[str, Field(min_length=1)]
    record_type: Literal["Actor", "Organization"]


class TaskAllocationBaselinePartition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    previously_missing_item_ids: tuple[str, ...]
    previously_demonstrated_item_ids: tuple[str, ...]


class TaskAllocationGoldCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_task_allocation_gold_v2"]
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_role: CatalogRole
    fixture_path: Annotated[str, Field(min_length=1)]
    fixture_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    focus_entity: TaskAllocationFocusEntity
    baseline_partition: TaskAllocationBaselinePartition | None = None
    sources: tuple[TaskAllocationSource, ...]
    items: tuple[TaskAllocationItem, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        if len(self.items) != 20:
            raise ValueError("A task-allocation Gold catalog requires exactly twenty items.")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("Task-allocation Gold item IDs must be distinct.")
        sources = {item.source_id: item for item in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Task-allocation source IDs must be distinct.")
        for item in self.items:
            source = sources.get(item.source_id)
            if source is None:
                raise ValueError("Task-allocation item references an unknown source.")
            segments = {
                segment.label: segment
                for segment in paragraph_source_segments(
                    source.source_text,
                    PARAGRAPH_SEGMENT_V3,
                )
            }
            segment = segments.get(item.source_segment_label)
            if segment is None:
                raise ValueError("Task-allocation item references an unknown SourceSegment.")
            if hashlib.sha256(segment.exact_text.encode()).hexdigest() != (
                item.source_segment_sha256
            ):
                raise ValueError("Task-allocation SourceSegment digest does not match.")
            if (
                item.expected_trigger_head_text is not None
                and item.expected_trigger_head_text not in segment.exact_text
            ):
                raise ValueError(
                    f"{item.item_id} trigger is absent from its authoritative source text."
                )
            if any(
                expression not in segment.exact_text
                for expression in item.accepted_trigger_expression_texts
            ):
                raise ValueError(
                    f"{item.item_id} trigger expression is absent from its "
                    "authoritative source text."
                )
            normalized_segment = _normalized(segment.exact_text)
            for expectation in (
                *(role for role in item.expected_roles),
                *(qualifier for qualifier in item.expected_qualifiers),
            ):
                if not all(
                    _normalized(value) in normalized_segment
                    for value in expectation.accepted_source_texts
                ):
                    raise ValueError(f"{item.item_id} expects text absent from its SourceSegment.")
            for expectation in item.expected_references:
                if _normalized(expectation.reference_text) not in normalized_segment:
                    raise ValueError(f"{item.item_id} reference is absent from its SourceSegment.")
                if _normalized(expectation.antecedent_text) not in normalized_segment:
                    raise ValueError(f"{item.item_id} antecedent is absent from its SourceSegment.")
            if item.expected_standing_fact is not None and not all(
                _normalized(value) in normalized_segment
                for value in (
                    item.expected_standing_fact.subject_text,
                    item.expected_standing_fact.object_text,
                )
            ):
                raise ValueError(
                    f"{item.item_id} standing-fact boundary is absent from its SourceSegment."
                )
        frames = {frame.id: frame for frame in HYBRID_EVENT_SEMANTICS_V4.frames}
        frame_ids = set(frames)
        if any(
            item.expected_frame_id is not None and item.expected_frame_id not in frame_ids
            for item in self.items
        ):
            raise ValueError("Task-allocation Gold references an unknown governed frame.")
        for item in self.items:
            if item.expected_frame_id is None or not item.expected_roles:
                continue
            frame = frames[item.expected_frame_id]
            role_ids = {role.id for role in frame.roles}
            expected_role_ids = {role.frame_role_id for role in item.expected_roles}
            if not expected_role_ids.issubset(role_ids):
                raise ValueError("Task-allocation Gold references an unknown frame role.")
            required_role_ids = {role.id for role in frame.roles if role.required}
            if not required_role_ids.issubset(expected_role_ids):
                raise ValueError("Task-allocation Gold omits a required governed frame role.")
        if self.catalog_role == "development":
            if self.baseline_partition is None:
                raise ValueError("The development catalog requires its frozen baseline partition.")
            missing = set(self.baseline_partition.previously_missing_item_ids)
            demonstrated = set(self.baseline_partition.previously_demonstrated_item_ids)
            if len(missing) != 17 or len(demonstrated) != 3:
                raise ValueError(
                    "Development Gold requires seventeen missing and three demonstrated."
                )
            if missing & demonstrated or missing | demonstrated != {x.item_id for x in self.items}:
                raise ValueError(
                    "Development baseline partition must cover each item exactly once."
                )
        elif self.baseline_partition is not None:
            raise ValueError("Held-out Gold cannot encode development baseline outcomes.")
        return self


class TaskAllocationStageEvidence(BaseModel):
    """Exact data-in/data-out evidence for one model-facing or deterministic stage."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: Annotated[str, Field(min_length=1)]
    stage_id: Annotated[str, Field(min_length=1)]
    exact_input: Annotated[str, Field(min_length=1)]
    raw_output: str | None
    parsed_output: object | None
    terminal_outcome: Annotated[str, Field(min_length=1)]


class TaskAllocationCheck(BaseModel):
    """One exact expected-versus-observed task-allocation decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    check_id: Annotated[str, Field(min_length=1)]
    stage_id: Annotated[str, Field(min_length=1)]
    passed: bool
    expected: object
    actual: object


class TaskAllocationItemEvaluation(BaseModel):
    """One Gold item followed through every applicable extraction stage."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")]
    expected_summary: Annotated[str, Field(min_length=1)]
    expected_route: ExpectedRoute
    source_segment_text: Annotated[str, Field(min_length=1)]
    source_segment_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    checks: tuple[TaskAllocationCheck, ...]
    first_failed_stage: str | None
    reached_review: bool
    wiki_visible: bool | None
    wiki_page_paths: tuple[str, ...]
    stage_evidence: tuple[TaskAllocationStageEvidence, ...]
    actual: dict[str, object]
    passed: bool

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        failed = next((item.stage_id for item in self.checks if not item.passed), None)
        if self.first_failed_stage != failed or self.passed != (failed is None):
            raise ValueError("Task-allocation result does not match its ordered checks.")
        return self


class TaskAllocationCatalogEvaluation(BaseModel):
    """Frozen development or held-out evaluation with auditable stage evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_task_allocation_evaluation_v1"] = (
        "hsq_task_allocation_evaluation_v1"
    )
    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_role: CatalogRole
    focus_entity_name: Annotated[str, Field(min_length=1)]
    item_count: Annotated[int, Field(ge=1)]
    passed_count: Annotated[int, Field(ge=0)]
    review_count: Annotated[int, Field(ge=0)]
    wiki_visible_count: Annotated[int, Field(ge=0)]
    wrong_forced_frame_count: Annotated[int, Field(ge=0)]
    first_failed_stage_counts: dict[str, int]
    items: tuple[TaskAllocationItemEvaluation, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.item_count != len(self.items):
            raise ValueError("Task-allocation item count does not match its results.")
        if self.passed_count != sum(item.passed for item in self.items):
            raise ValueError("Task-allocation passed count does not match its results.")
        if self.review_count != sum(item.reached_review for item in self.items):
            raise ValueError("Task-allocation review count does not match its results.")
        if self.wiki_visible_count != sum(item.wiki_visible is True for item in self.items):
            raise ValueError("Task-allocation Wiki count does not match its results.")
        expected_failures: dict[str, int] = {}
        for item in self.items:
            if item.first_failed_stage is not None:
                expected_failures[item.first_failed_stage] = (
                    expected_failures.get(item.first_failed_stage, 0) + 1
                )
        if self.first_failed_stage_counts != dict(sorted(expected_failures.items())):
            raise ValueError("Task-allocation failure counts do not match item results.")
        return self


class TaskAllocationRunCost(BaseModel):
    """Aggregate execution cost retained for one canonical comparison run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    extraction_task_count: Annotated[int, Field(ge=0)]
    model_run_count: Annotated[int, Field(ge=0)]
    proposed_change_count: Annotated[int, Field(ge=0)]
    total_model_elapsed_milliseconds: Annotated[int, Field(ge=0)]


class TaskAllocationBaselineItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")]
    passed: bool
    reached_review: bool
    wiki_visible: bool | None
    first_failed_stage: str | None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.passed != (self.first_failed_stage is None):
            raise ValueError("A baseline item must agree with its first failed stage.")
        return self


class TaskAllocationBaselineCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_role: CatalogRole
    items: tuple[TaskAllocationBaselineItem, ...]

    @model_validator(mode="after")
    def validate_items(self) -> Self:
        item_ids = tuple(item.item_id for item in self.items)
        if len(self.items) != 20 or item_ids != tuple(sorted(set(item_ids))):
            raise ValueError("A baseline catalog requires twenty ordered distinct items.")
        return self


class TaskAllocationBaseline(BaseModel):
    """Pinned canonical quality and cost evidence from before HSQ-7 correction."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_task_allocation_baseline_v1"]
    recorded_on: Annotated[str, Field(pattern=r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}$")]
    source_fixture_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    evaluator_corrections: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    cost: TaskAllocationRunCost
    catalogs: tuple[TaskAllocationBaselineCatalog, ...]

    @model_validator(mode="after")
    def validate_catalogs(self) -> Self:
        identities = tuple(item.catalog_id for item in self.catalogs)
        if len(self.catalogs) != 2 or identities != tuple(sorted(set(identities))):
            raise ValueError("The task-allocation baseline requires two ordered catalogs.")
        if {item.catalog_role for item in self.catalogs} != {"development", "held_out"}:
            raise ValueError("The task-allocation baseline requires both catalog roles.")
        return self


class TaskAllocationBaselineItemComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    item_id: Annotated[str, Field(pattern=r"^(AMO|ANT)-[0-9]{2}$")]
    baseline_passed: bool
    current_passed: bool
    baseline_first_failed_stage: str | None
    current_first_failed_stage: str | None
    newly_complete: bool
    regressed: bool


class TaskAllocationBaselineCatalogComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    catalog_id: Annotated[str, Field(min_length=1)]
    catalog_role: CatalogRole
    baseline_passed_count: Annotated[int, Field(ge=0)]
    current_passed_count: Annotated[int, Field(ge=0)]
    newly_complete_item_ids: tuple[str, ...]
    regressed_item_ids: tuple[str, ...]
    items: tuple[TaskAllocationBaselineItemComparison, ...]


class TaskAllocationBaselineComparison(BaseModel):
    """Per-item quality and aggregate cost delta against pinned evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_task_allocation_baseline_comparison_v1"] = (
        "hsq_task_allocation_baseline_comparison_v1"
    )
    baseline_recorded_on: str
    baseline_cost: TaskAllocationRunCost
    current_cost: TaskAllocationRunCost
    extraction_task_count_delta: int
    model_run_count_delta: int
    proposed_change_count_delta: int
    total_model_elapsed_milliseconds_delta: int
    catalogs: tuple[TaskAllocationBaselineCatalogComparison, ...]


def load_task_allocation_gold(path: Path) -> TaskAllocationGoldCatalog:
    return TaskAllocationGoldCatalog.model_validate_json(path.read_bytes())


def load_task_allocation_evaluator_corrections(
    path: Path,
) -> TaskAllocationEvaluatorCorrectionCatalog:
    return TaskAllocationEvaluatorCorrectionCatalog.model_validate_json(path.read_bytes())


def load_task_allocation_baseline(path: Path) -> TaskAllocationBaseline:
    return TaskAllocationBaseline.model_validate_json(path.read_bytes())


def compare_task_allocation_baseline(
    baseline: TaskAllocationBaseline,
    evaluations: tuple[TaskAllocationCatalogEvaluation, ...],
    current_cost: TaskAllocationRunCost,
) -> TaskAllocationBaselineComparison:
    """Compare one canonical run to the exact pinned per-item baseline."""
    evaluations_by_id = {item.catalog_id: item for item in evaluations}
    if set(evaluations_by_id) != {item.catalog_id for item in baseline.catalogs}:
        raise ValueError("Current task-allocation catalogs do not match the baseline.")
    comparisons: list[TaskAllocationBaselineCatalogComparison] = []
    for baseline_catalog in baseline.catalogs:
        current_catalog = evaluations_by_id[baseline_catalog.catalog_id]
        if current_catalog.catalog_role != baseline_catalog.catalog_role:
            raise ValueError("Current task-allocation catalog role drifted from baseline.")
        current_by_id = {item.item_id: item for item in current_catalog.items}
        baseline_by_id = {item.item_id: item for item in baseline_catalog.items}
        if set(current_by_id) != set(baseline_by_id):
            raise ValueError("Current task-allocation items do not match the baseline.")
        items = tuple(
            TaskAllocationBaselineItemComparison(
                item_id=item_id,
                baseline_passed=baseline_by_id[item_id].passed,
                current_passed=current_by_id[item_id].passed,
                baseline_first_failed_stage=baseline_by_id[item_id].first_failed_stage,
                current_first_failed_stage=current_by_id[item_id].first_failed_stage,
                newly_complete=(
                    not baseline_by_id[item_id].passed and current_by_id[item_id].passed
                ),
                regressed=(baseline_by_id[item_id].passed and not current_by_id[item_id].passed),
            )
            for item_id in sorted(baseline_by_id)
        )
        comparisons.append(
            TaskAllocationBaselineCatalogComparison(
                catalog_id=baseline_catalog.catalog_id,
                catalog_role=baseline_catalog.catalog_role,
                baseline_passed_count=sum(item.passed for item in baseline_catalog.items),
                current_passed_count=current_catalog.passed_count,
                newly_complete_item_ids=tuple(
                    item.item_id for item in items if item.newly_complete
                ),
                regressed_item_ids=tuple(item.item_id for item in items if item.regressed),
                items=items,
            )
        )
    return TaskAllocationBaselineComparison(
        baseline_recorded_on=baseline.recorded_on,
        baseline_cost=baseline.cost,
        current_cost=current_cost,
        extraction_task_count_delta=(
            current_cost.extraction_task_count - baseline.cost.extraction_task_count
        ),
        model_run_count_delta=current_cost.model_run_count - baseline.cost.model_run_count,
        proposed_change_count_delta=(
            current_cost.proposed_change_count - baseline.cost.proposed_change_count
        ),
        total_model_elapsed_milliseconds_delta=(
            current_cost.total_model_elapsed_milliseconds
            - baseline.cost.total_model_elapsed_milliseconds
        ),
        catalogs=tuple(sorted(comparisons, key=lambda item: item.catalog_id)),
    )


def evaluate_task_allocation_catalog(
    catalog: TaskAllocationGoldCatalog,
    paragraphs: list[dict[str, Any]],
    *,
    wiki_plan: CandidateWikiPlan | None = None,
    evaluator_corrections: TaskAllocationEvaluatorCorrectionCatalog | None = None,
) -> TaskAllocationCatalogEvaluation:
    """Evaluate one frozen Gold catalog against canonical orchestration evidence."""
    paragraphs_by_ordinal = {int(item["ordinal"]): item for item in paragraphs}
    sources = {item.source_id: item for item in catalog.sources}
    results: list[TaskAllocationItemEvaluation] = []
    for item in catalog.items:
        source = sources[item.source_id]
        segment = next(
            segment
            for segment in paragraph_source_segments(source.source_text, PARAGRAPH_SEGMENT_V3)
            if segment.label == item.source_segment_label
        )
        paragraph = paragraphs_by_ordinal.get(source.paragraph_ordinal)
        results.append(
            _evaluate_item(
                catalog,
                item,
                segment.exact_text,
                paragraph,
                wiki_plan,
                evaluator_corrections,
            )
        )
    failed_counts: dict[str, int] = {}
    for result in results:
        if result.first_failed_stage is not None:
            failed_counts[result.first_failed_stage] = (
                failed_counts.get(result.first_failed_stage, 0) + 1
            )
    return TaskAllocationCatalogEvaluation(
        catalog_id=catalog.catalog_id,
        catalog_role=catalog.catalog_role,
        focus_entity_name=catalog.focus_entity.name,
        item_count=len(results),
        passed_count=sum(item.passed for item in results),
        review_count=sum(item.reached_review for item in results),
        wiki_visible_count=sum(item.wiki_visible is True for item in results),
        wrong_forced_frame_count=sum(
            task_allocation_item_has_wrong_forced_frame(item) for item in results
        ),
        first_failed_stage_counts=dict(sorted(failed_counts.items())),
        items=tuple(results),
    )


def _evaluate_item(
    catalog: TaskAllocationGoldCatalog,
    expected: TaskAllocationItem,
    source_segment_text: str,
    paragraph: dict[str, Any] | None,
    wiki_plan: CandidateWikiPlan | None,
    evaluator_corrections: TaskAllocationEvaluatorCorrectionCatalog | None,
) -> TaskAllocationItemEvaluation:
    stages = cast(dict[str, Any], paragraph.get("stage_outputs", {})) if paragraph else {}
    raw_outputs = cast(dict[str, Any], paragraph.get("raw_model_outputs", {})) if paragraph else {}
    hp1 = _stage(stages, "hp1_mentions")
    hp2 = _stage(stages, "hp2_references")
    hp4 = _stage(stages, "hp4_event_triggers")
    hp6 = _stage(stages, "hp6_event_semantics")
    hp7 = _stage(stages, "hp7_proposal_plan")
    hp10 = _stage(stages, "hp10_standing_facts")
    trigger_matches = [
        item
        for item in _records(hp4, "triggers")
        if item.get("source_text_sha256") == expected.source_segment_sha256
        and _normalized(str(item.get("head_text", "")))
        == _normalized(expected.expected_trigger_head_text or "")
        and _normalized(str(item.get("text", "")))
        in {_normalized(value) for value in expected.accepted_trigger_expression_texts}
    ]
    trigger = trigger_matches[0] if len(trigger_matches) == 1 else None
    subject_id = _event_subject_id(hp6, trigger)
    semantic = _semantic_event(hp6, trigger)
    assignments = [
        item for item in _records(hp6, "assignments") if item.get("event_subject_id") == subject_id
    ]
    targets = {str(item.get("id")): item for item in _records(hp6, "targets")}
    qualifiers = [
        item for item in _records(hp6, "qualifiers") if item.get("event_subject_id") == subject_id
    ]
    gaps = [item for item in _records(hp6, "gaps") if item.get("event_subject_id") == subject_id]
    proposition = next(
        (
            item
            for item in _records(hp6, "propositions")
            if semantic is not None and item.get("subject_record_id") == semantic.get("id")
        ),
        None,
    )
    proposition_decision = next(
        (
            item
            for item in _records(hp6, "proposition_decisions")
            if proposition is not None and item.get("proposition_id") == proposition.get("id")
        ),
        None,
    )
    admission = next(
        (
            item
            for item in _records(hp7, "decisions")
            if semantic is not None and item.get("event_semantic_id") == semantic.get("id")
        ),
        None,
    )
    mention_checks, mention_actual = _mention_checks(
        catalog,
        hp1,
        expected.source_segment_sha256,
    )
    checks: list[TaskAllocationCheck] = list(mention_checks)
    actual: dict[str, object] = {
        "mention": mention_actual,
        "trigger_matches": trigger_matches,
        "semantic_event": semantic,
        "role_assignments": assignments,
        "role_targets": [targets.get(str(item.get("target_id"))) for item in assignments],
        "qualifiers": qualifiers,
        "coverage_gaps": gaps,
        "proposition": proposition,
        "proposition_decision": proposition_decision,
        "admission_decision": admission,
    }
    reached_review = False
    proposal_ids: tuple[str, ...] = ()
    proposed_record_ids: tuple[str, ...] = ()
    if expected.expected_route == "event":
        checks.extend(
            _reference_checks(
                expected,
                hp1,
                hp2,
                expected.source_segment_sha256,
                source_segment_text,
                evaluator_corrections,
            )
        )
        checks.append(
            _check(
                "trigger",
                "source_occurrence_selection",
                len(trigger_matches) == 1,
                {
                    "head": expected.expected_trigger_head_text,
                    "expressions": list(expected.accepted_trigger_expression_texts),
                },
                [
                    {"head": item.get("head_text"), "expression": item.get("text")}
                    for item in trigger_matches
                ],
            )
        )
        selected_frame = _selected_frame(hp6, trigger)
        checks.append(
            _check(
                "frame",
                "bounded_frame_selection",
                selected_frame == expected.expected_frame_id,
                expected.expected_frame_id,
                selected_frame,
            )
        )
        frame_fit = _frame_fit(hp6, trigger)
        checks.append(
            _check(
                "frame_fit",
                "bounded_frame_fit",
                frame_fit is True,
                True,
                frame_fit,
            )
        )
        checks.extend(_role_checks(expected, assignments, targets))
        checks.extend(_presentation_checks(expected, semantic, qualifiers))
        checks.append(
            _check(
                "complete_proposition",
                "complete_proposition_gate",
                proposition_decision is not None
                and proposition_decision.get("disposition") == "supported",
                "supported",
                proposition_decision,
            )
        )
        proposal_ids = tuple(
            sorted(str(value) for value in (admission or {}).get("proposed_change_ids", []))
        )
        proposed_record_ids = _proposed_record_ids(hp7, proposal_ids)
        reached_review = (
            admission is not None
            and admission.get("disposition") == "proposed"
            and bool(proposal_ids)
        )
        checks.append(
            _check(
                "proposal",
                "proposal_admission",
                reached_review,
                "proposed",
                admission,
            )
        )
    elif expected.expected_route == "typed_ontology_gap":
        checks.extend(
            _reference_checks(
                expected,
                hp1,
                hp2,
                expected.source_segment_sha256,
                source_segment_text,
                evaluator_corrections,
            )
        )
        checks.append(
            _check(
                "trigger",
                "source_occurrence_selection",
                len(trigger_matches) == 1,
                {
                    "head": expected.expected_trigger_head_text,
                    "expressions": list(expected.accepted_trigger_expression_texts),
                },
                [
                    {"head": item.get("head_text"), "expression": item.get("text")}
                    for item in trigger_matches
                ],
            )
        )
        selected_frame = _selected_frame(hp6, trigger)
        frame_fit = _frame_fit(hp6, trigger)
        if expected.expected_frame_id is None:
            frame_matches = semantic is None and (selected_frame is None or frame_fit is False)
        else:
            frame_matches = selected_frame == expected.expected_frame_id and frame_fit is True
        checks.append(
            _check(
                "gap_frame",
                "bounded_frame_selection",
                frame_matches,
                expected.expected_frame_id or "unresolved",
                {"selected_frame": selected_frame, "frame_fit": frame_fit},
            )
        )
        matching_gaps = [item for item in gaps if item.get("code") == expected.expected_gap_code]
        checks.append(
            _check(
                "typed_gap",
                "typed_ontology_gap",
                bool(matching_gaps),
                expected.expected_gap_code,
                gaps,
            )
        )
        actual["selected_frame"] = selected_frame
        reached_review = False
    else:
        standing = _standing_observation(hp10, expected, expected.source_segment_sha256)
        actual["standing_fact"] = standing
        draft = cast(dict[str, Any] | None, standing.get("draft"))
        decision = cast(dict[str, Any] | None, standing.get("decision"))
        checks.append(
            _check(
                "standing_fact",
                "parallel_semantic_routes",
                bool(standing.get("semantic_match")),
                expected.expected_standing_fact.model_dump(mode="json")
                if expected.expected_standing_fact
                else None,
                draft,
            )
        )
        proposal_ids = tuple(
            sorted(str(value) for value in (decision or {}).get("proposed_change_ids", []))
        )
        proposed_record_ids = _proposed_record_ids(hp10, proposal_ids)
        reached_review = (
            decision is not None
            and decision.get("disposition") == "proposed"
            and bool(proposal_ids)
        )
        checks.append(
            _check(
                "standing_proposal",
                "proposal_admission",
                reached_review,
                "proposed",
                decision,
            )
        )

    wiki_visible: bool | None = None
    wiki_paths: tuple[str, ...] = ()
    if expected.expected_disposition == "proposed" and wiki_plan is not None:
        wiki_visible, wiki_paths = _wiki_result(
            catalog,
            proposed_record_ids,
            expected.source_segment_sha256,
            wiki_plan,
        )
        checks.append(
            _check(
                "candidate_wiki",
                "candidate_wiki_projection",
                wiki_visible,
                {"focus_entity": catalog.focus_entity.name, "source_visible": True},
                {"visible": wiki_visible, "page_paths": list(wiki_paths)},
            )
        )
    elif expected.expected_disposition == "proposed":
        wiki_visible = None

    all_traces = _matching_traces(
        expected.item_id,
        expected.source_segment_sha256,
        (hp1, hp2, hp4, hp6, hp7, hp10),
        raw_outputs,
        associated_trace_ids=_reference_trace_ids(
            expected,
            hp1,
            hp2,
            expected.source_segment_sha256,
        ),
    )
    failed = next((item.stage_id for item in checks if not item.passed), None)
    return TaskAllocationItemEvaluation(
        item_id=expected.item_id,
        expected_summary=expected.expected_summary,
        expected_route=expected.expected_route,
        source_segment_text=source_segment_text,
        source_segment_sha256=expected.source_segment_sha256,
        checks=tuple(checks),
        first_failed_stage=failed,
        reached_review=reached_review,
        wiki_visible=wiki_visible,
        wiki_page_paths=wiki_paths,
        stage_evidence=all_traces,
        actual=actual,
        passed=failed is None,
    )


def _mention_checks(
    catalog: TaskAllocationGoldCatalog,
    hp1: dict[str, Any] | None,
    source_segment_sha256: str,
) -> tuple[list[TaskAllocationCheck], dict[str, object]]:
    candidates = [
        item
        for item in _records(hp1, "candidates")
        if item.get("source_text_sha256") == source_segment_sha256
    ]
    focus_literals = _focus_literals(catalog)
    focus_candidates = [
        item
        for item in candidates
        if _normalized_entity_literal(str(item.get("text", ""))) in focus_literals
    ]
    selected_ids = _effective_mention_candidate_id_set(hp1)
    decisions = _records(hp1, "boundary_decisions")
    decision_by_candidate = {
        str(candidate_id): decision
        for decision in decisions
        for candidate_id in cast(list[str], decision.get("candidate_ids", []))
    }
    deterministic_selected_ids = {
        str(candidate_id)
        for decision in decisions
        for candidate_id in cast(list[str], decision.get("selected_candidate_ids", []))
    }
    reconciled_focus = [
        item
        for item in focus_candidates
        if (
            (
                (decision := decision_by_candidate.get(str(item.get("id")))) is not None
                and decision.get("status") == "ambiguous"
            )
            or str(item.get("id")) in deterministic_selected_ids
        )
    ]
    selected_focus = [item for item in focus_candidates if item.get("id") in selected_ids]
    interpretations = {
        str(item.get("candidate_id")): item for item in _records(hp1, "interpretations")
    }
    expected_kind = "person" if catalog.focus_entity.record_type == "Actor" else "organization"
    interpreted_focus = [
        item
        for item in selected_focus
        if (interpretation := interpretations.get(str(item.get("id")))) is not None
        and interpretation.get("referentiality") == "specific_entity"
        and interpretation.get("contextual_kind") == expected_kind
    ]
    checks = [
        _check(
            "focus_mention",
            "mention_proposal",
            bool(focus_candidates),
            sorted(focus_literals),
            [item.get("text") for item in candidates],
        ),
        _check(
            "focus_boundary",
            "mention_boundary_reconciliation",
            bool(reconciled_focus),
            "at least one focus candidate retained for deterministic or semantic routing",
            [item.get("text") for item in reconciled_focus],
        ),
        _check(
            "focus_boundary_adjudication",
            "mention_boundary_adjudication",
            bool(selected_focus),
            "at least one effective focus candidate",
            [item.get("text") for item in selected_focus],
        ),
        _check(
            "focus_interpretation",
            "mention_interpretation",
            bool(interpreted_focus),
            {"referentiality": "specific_entity", "contextual_kind": expected_kind},
            [
                interpretations[str(item.get("id"))]
                for item in selected_focus
                if str(item.get("id")) in interpretations
            ],
        ),
    ]
    return checks, {
        "target_segment_candidates": candidates,
        "focus_candidates": focus_candidates,
        "selected_focus_candidates": selected_focus,
        "interpreted_focus_candidates": interpreted_focus,
    }


def _reference_checks(
    expected: TaskAllocationItem,
    hp1: dict[str, Any] | None,
    hp2: dict[str, Any] | None,
    source_segment_sha256: str,
    source_segment_text: str,
    evaluator_corrections: TaskAllocationEvaluatorCorrectionCatalog | None,
) -> list[TaskAllocationCheck]:
    checks: list[TaskAllocationCheck] = []
    target_candidates = [
        item
        for item in _records(hp1, "candidates")
        if item.get("source_text_sha256") == source_segment_sha256
    ]
    selected_ids = _effective_mention_candidate_id_set(hp1)
    interpretations = {
        str(item.get("candidate_id")): item for item in _records(hp1, "interpretations")
    }
    observations = {str(item.get("id")): item for item in _records(hp1, "observations")}
    marker_candidate_ids = {
        str(candidate.get("id"))
        for candidate in target_candidates
        if any(
            observations.get(str(observation_id), {}).get("producer_id")
            == "kotekomi_reference_marker_v1"
            for observation_id in cast(list[str], candidate.get("observation_ids", []))
        )
    }
    spans = {
        str(item.get("id")): str(item.get("text", ""))
        for item in _records(hp2, "semantic_antecedent_spans")
    }
    for index, reference in enumerate(expected.expected_references, start=1):
        reference_candidates = [
            item
            for item in target_candidates
            if _reference_literal_matches(str(item.get("text", "")), reference.reference_text)
        ]
        selected_references = [
            item for item in reference_candidates if item.get("id") in selected_ids
        ]
        routed_references = [
            item
            for item in selected_references
            if str(item.get("id")) in marker_candidate_ids
            or (
                (interpretation := interpretations.get(str(item.get("id")))) is not None
                and interpretation.get("referentiality") == "anaphoric"
            )
        ]
        candidate_ids = {str(item.get("id")) for item in routed_references}
        matching = [
            item
            for item in _records(hp2, "reference_decisions")
            if item.get("candidate_id") in candidate_ids
        ]
        selected_texts = [
            spans[span_id]
            for item in matching
            for span_id in cast(list[str], item.get("antecedent_span_ids", []))
            if span_id in spans
        ]
        checks.append(
            _check(
                f"reference_marker_{index}",
                "reference_marker",
                bool(reference_candidates),
                reference.reference_text,
                [item.get("text") for item in reference_candidates],
            )
        )
        checks.append(
            _check(
                f"reference_routing_{index}",
                "reference_routing",
                bool(routed_references),
                "deterministic_reference_marker_or_anaphoric_interpretation",
                {
                    "routed_candidate_ids": [item.get("id") for item in routed_references],
                    "deterministic_reference_marker_candidate_ids": sorted(marker_candidate_ids),
                    "interpretations": [
                        interpretations[str(item.get("id"))]
                        for item in selected_references
                        if str(item.get("id")) in interpretations
                    ],
                },
            )
        )
        accepted_antecedent_texts = _accepted_reference_antecedent_texts(
            expected=expected,
            reference=reference,
            source_segment_text=source_segment_text,
            evaluator_corrections=evaluator_corrections,
        )
        checks.append(
            _check(
                f"reference_resolution_{index}",
                "reference_resolution",
                len(matching) == 1
                and matching[0].get("status") == "resolved"
                and any(value in accepted_antecedent_texts for value in selected_texts),
                {
                    "reference_text": reference.reference_text,
                    "accepted_antecedent_texts": list(accepted_antecedent_texts),
                },
                {"decisions": matching, "selected_texts": selected_texts},
            )
        )
    return checks


def _accepted_reference_antecedent_texts(
    *,
    expected: TaskAllocationItem,
    reference: TaskAllocationReferenceExpectation,
    source_segment_text: str,
    evaluator_corrections: TaskAllocationEvaluatorCorrectionCatalog | None,
) -> tuple[str, ...]:
    if evaluator_corrections is None:
        return (reference.antecedent_text,)
    correction = next(
        (
            item
            for item in evaluator_corrections.corrections
            if item.item_id == expected.item_id and item.reference_text == reference.reference_text
        ),
        None,
    )
    if correction is None:
        return (reference.antecedent_text,)
    if (
        correction.source_text_sha256 != expected.source_segment_sha256
        or correction.previous_antecedent_text != reference.antecedent_text
    ):
        raise ValueError("Evaluator correction does not match its parent Gold contract.")
    if any(value not in source_segment_text for value in correction.accepted_antecedent_texts):
        raise ValueError("Evaluator correction names text absent from its SourceSegment.")
    return correction.accepted_antecedent_texts


def _reference_trace_ids(
    expected: TaskAllocationItem,
    hp1: dict[str, Any] | None,
    hp2: dict[str, Any] | None,
    source_segment_sha256: str,
) -> set[str]:
    reference_literals = {item.reference_text for item in expected.expected_references}
    candidate_ids = {
        str(item.get("id"))
        for item in _records(hp1, "candidates")
        if item.get("source_text_sha256") == source_segment_sha256
        and any(
            _reference_literal_matches(str(item.get("text", "")), literal)
            for literal in reference_literals
        )
    }
    return {
        str(item.get("trace_id"))
        for item in _records(hp2, "reference_decisions")
        if item.get("candidate_id") in candidate_ids and item.get("trace_id") is not None
    }


def _role_checks(
    expected: TaskAllocationItem,
    assignments: list[dict[str, Any]],
    targets: dict[str, dict[str, Any]],
) -> list[TaskAllocationCheck]:
    checks: list[TaskAllocationCheck] = []
    for role in expected.expected_roles:
        matching_assignments = [
            item for item in assignments if item.get("frame_role_id") == role.frame_role_id
        ]
        actual_targets = [
            targets[str(item.get("target_id"))]
            for item in matching_assignments
            if str(item.get("target_id")) in targets
        ]
        checks.append(
            _check(
                role.frame_role_id,
                "bounded_role_selection",
                len(actual_targets) == 1
                and any(
                    _normalized(str(actual_targets[0].get("text", ""))) == _normalized(value)
                    for value in role.accepted_source_texts
                ),
                role.model_dump(mode="json"),
                actual_targets,
            )
        )
    return checks


def _presentation_checks(
    expected: TaskAllocationItem,
    semantic: dict[str, Any] | None,
    qualifiers: list[dict[str, Any]],
) -> list[TaskAllocationCheck]:
    checks = [
        _check(
            "event_presentation",
            "event_presentation",
            semantic is not None
            and semantic.get("polarity") == expected.expected_polarity
            and semantic.get("modality") == expected.expected_modality
            and semantic.get("attribution_kind") == expected.expected_attribution,
            {
                "polarity": expected.expected_polarity,
                "modality": expected.expected_modality,
                "attribution": expected.expected_attribution,
            },
            (
                {
                    "polarity": semantic.get("polarity"),
                    "modality": semantic.get("modality"),
                    "attribution": semantic.get("attribution_kind"),
                }
                if semantic
                else None
            ),
        )
    ]
    for index, qualifier in enumerate(expected.expected_qualifiers, start=1):
        matches = [
            item
            for item in qualifiers
            if item.get("kind") == qualifier.kind
            and (qualifier.relation is None or item.get("temporal_relation") == qualifier.relation)
            and any(
                _normalized(str(item.get("text", ""))) == _normalized(value)
                for value in qualifier.accepted_source_texts
            )
        ]
        checks.append(
            _check(
                f"qualifier_{index}",
                "event_presentation",
                len(matches) == 1,
                qualifier.model_dump(mode="json"),
                matches,
            )
        )
    return checks


def _standing_observation(
    hp10: dict[str, Any] | None,
    expected: TaskAllocationItem,
    segment_sha256: str,
) -> dict[str, object]:
    contract = expected.expected_standing_fact
    if hp10 is None or contract is None:
        return {"semantic_match": False, "draft": None, "decision": None}
    segment_ids = {
        str(trace.get("source_segment_id"))
        for trace in _records(hp10, "traces")
        if trace.get("source_text_sha256") == segment_sha256
    }
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for trace in _records(hp10, "traces"):
        if trace.get("source_text_sha256") != segment_sha256:
            continue
        for candidate in _records(
            cast(dict[str, Any], trace.get("input", {})), "candidate_catalog"
        ):
            candidate_by_id[str(candidate.get("candidate_id"))] = candidate
    matching: list[dict[str, Any]] = []
    for draft in _records(hp10, "drafts"):
        if draft.get("source_segment_id") not in segment_ids:
            continue
        subject = candidate_by_id.get(str(draft.get("subject_candidate_id")), {})
        if draft.get("object_candidate_id") is not None:
            object_text = _candidate_text(
                candidate_by_id.get(str(draft.get("object_candidate_id")), {})
            )
        else:
            object_text = str(draft.get("object_label_or_literal", "")).strip('"')
        subject_text = _candidate_text(subject)
        relation = _normalized(str(draft.get("relation_label", ""))).casefold()
        if (
            _normalized(subject_text).casefold() == _normalized(contract.subject_text).casefold()
            and _normalized(object_text).casefold() == _normalized(contract.object_text).casefold()
            and all(term.casefold() in relation for term in contract.relation_terms)
        ):
            matching.append(draft)
    draft = matching[0] if len(matching) == 1 else None
    decision = next(
        (
            item
            for item in _records(hp10, "decisions")
            if draft is not None and item.get("draft_id") == draft.get("id")
        ),
        None,
    )
    return {
        "semantic_match": len(matching) == 1,
        "draft": draft,
        "decision": decision,
        "matching_drafts": matching,
    }


def _candidate_text(candidate: dict[str, Any]) -> str:
    return str(candidate.get("display_name") or candidate.get("exact_text") or "")


def _selected_frame(
    hp6: dict[str, Any] | None,
    trigger: dict[str, Any] | None,
) -> str | None:
    if hp6 is None or trigger is None:
        return None
    for trace in _records(hp6, "traces"):
        if trace.get("stage_id") != "hybrid_event_frame_selection":
            continue
        trace_trigger = cast(
            dict[str, Any], cast(dict[str, Any], trace.get("input", {})).get("trigger", {})
        )
        if trace_trigger.get("id") != trigger.get("id"):
            continue
        selection = cast(
            dict[str, Any] | None,
            cast(dict[str, Any], trace.get("output", {})).get("parsed_selection"),
        )
        return str(selection["frame_id"]) if selection and selection.get("frame_id") else None
    return None


def _frame_fit(
    hp6: dict[str, Any] | None,
    trigger: dict[str, Any] | None,
) -> bool | None:
    if hp6 is None or trigger is None:
        return None
    for trace in _records(hp6, "traces"):
        if trace.get("stage_id") != "hybrid_event_frame_fit":
            continue
        trace_trigger = cast(
            dict[str, Any], cast(dict[str, Any], trace.get("input", {})).get("trigger", {})
        )
        if trace_trigger.get("id") != trigger.get("id"):
            continue
        decision = cast(
            dict[str, Any] | None,
            cast(dict[str, Any], trace.get("output", {})).get("parsed_decision"),
        )
        if decision is None:
            return None
        fits = decision.get("fits")
        return fits if type(fits) is bool else None
    return None


def _event_subject_id(
    hp6: dict[str, Any] | None,
    trigger: dict[str, Any] | None,
) -> str | None:
    if hp6 is None or trigger is None:
        return None
    semantic = _semantic_event(hp6, trigger)
    if semantic is not None:
        return str(semantic["event_subject_id"])
    for trace in _records(hp6, "traces"):
        trace_input = cast(dict[str, Any], trace.get("input", {}))
        trace_trigger = cast(dict[str, Any], trace_input.get("trigger", {}))
        subject = cast(dict[str, Any], trace_input.get("event_subject", {}))
        if trace_trigger.get("id") == trigger.get("id") and subject.get("id") is not None:
            return str(subject["id"])
    return None


def _semantic_event(
    hp6: dict[str, Any] | None,
    trigger: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if hp6 is None or trigger is None:
        return None
    return next(
        (
            item
            for item in _records(hp6, "semantic_events")
            if item.get("trigger_id") == trigger.get("id")
        ),
        None,
    )


def _matching_traces(
    item_id: str,
    source_sha256: str,
    stages: tuple[dict[str, Any] | None, ...],
    raw_outputs: dict[str, Any],
    *,
    associated_trace_ids: set[str] | None = None,
) -> tuple[TaskAllocationStageEvidence, ...]:
    evidence: list[TaskAllocationStageEvidence] = []
    associated = associated_trace_ids or set()
    for stage in stages:
        for trace in _records(stage, "traces"):
            if (
                trace.get("source_text_sha256") != source_sha256
                and trace.get("id") not in associated
            ):
                continue
            trace_input = cast(dict[str, Any], trace.get("input", {}))
            model_visible = trace_input.get("model_visible_input") or trace_input.get(
                "model_visible_task"
            )
            exact_input = (
                str(model_visible)
                if isinstance(model_visible, str) and model_visible
                else _canonical_json(trace_input)
            )
            raw_values: list[str] = []
            for execution_id in cast(list[str], trace.get("execution_record_ids", [])):
                if not execution_id.startswith("mrn_"):
                    continue
                raw_record = raw_outputs.get(execution_id)
                if isinstance(raw_record, dict):
                    raw_value = cast(dict[str, Any], raw_record).get("raw_output")
                elif isinstance(raw_record, str):
                    raw_value = raw_record
                else:
                    raw_value = None
                if isinstance(raw_value, str):
                    raw_values.append(raw_value)
            raw = raw_values[0] if len(raw_values) == 1 else None
            evidence.append(
                TaskAllocationStageEvidence(
                    item_id=item_id,
                    stage_id=str(trace.get("stage_id", "unknown")),
                    exact_input=exact_input,
                    raw_output=str(raw) if raw is not None else None,
                    parsed_output=trace.get("output"),
                    terminal_outcome=str(trace.get("status", "unknown")),
                )
            )
    return tuple(evidence)


def _focus_literals(catalog: TaskAllocationGoldCatalog) -> set[str]:
    names = {catalog.focus_entity.name}
    if catalog.focus_entity.record_type == "Actor":
        names.add(catalog.focus_entity.name.rsplit(" ", maxsplit=1)[-1])
    return {_normalized_entity_literal(item) for item in names}


def _reference_literal_matches(actual: str, expected: str) -> bool:
    normalized_actual = " ".join(actual.casefold().split())
    normalized_expected = " ".join(expected.casefold().split())
    return normalized_actual in {normalized_expected, f"the {normalized_expected}"}


def _normalized_entity_literal(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    if normalized.endswith(("'s", "’s")):
        normalized = normalized[:-2]
    return normalized.removeprefix("the ")


def _wiki_result(
    catalog: TaskAllocationGoldCatalog,
    record_ids: tuple[str, ...],
    source_sha256: str,
    plan: CandidateWikiPlan,
) -> tuple[bool, tuple[str, ...]]:
    pages = tuple(
        page
        for page in plan.pages
        if page.display_label == catalog.focus_entity.name
        or (
            catalog.focus_entity.record_type == "Actor"
            and page.display_label == catalog.focus_entity.name.rsplit(" ", maxsplit=1)[-1]
        )
    )
    citations = {item.citation_number: item for item in plan.citation_registry.citations}
    matched_paths: set[str] = set()
    for page in pages:
        for presentation in page.presentations:
            if isinstance(presentation, WikiEventPresentation):
                presentation_record_id = presentation.event_id
            else:
                presentation_record_id = presentation.edge.assertion_id
            if presentation_record_id not in record_ids:
                continue
            if any(
                hashlib.sha256(citations[number].exact_text.encode()).hexdigest() == source_sha256
                for number in presentation.citation_numbers
                if number in citations
            ):
                matched_paths.add(page.relative_path)
    return bool(matched_paths), tuple(sorted(matched_paths))


def _proposed_record_ids(
    stage: dict[str, Any] | None,
    proposal_ids: tuple[str, ...],
) -> tuple[str, ...]:
    wanted = set(proposal_ids)
    record_ids: set[str] = set()
    for proposal in _records(stage, "proposed_changes"):
        if proposal.get("id") not in wanted:
            continue
        proposed_json = proposal.get("proposed_json")
        if not isinstance(proposed_json, dict):
            continue
        record = cast(dict[str, object], proposed_json).get("record")
        if not isinstance(record, dict):
            continue
        typed_record = cast(dict[str, object], record)
        record_id = typed_record.get("id")
        if isinstance(record_id, str):
            record_ids.add(record_id)
    return tuple(sorted(record_ids))


def task_allocation_item_has_wrong_forced_frame(
    item: TaskAllocationItemEvaluation,
) -> bool:
    """Return whether a typed gap survived an inaccurate governed-frame choice."""
    if item.expected_route != "typed_ontology_gap":
        return False
    expected = next(
        (check.expected for check in item.checks if check.check_id == "gap_frame"), None
    )
    actual = next((check.actual for check in item.checks if check.check_id == "gap_frame"), None)
    if expected != "unresolved" or not isinstance(actual, dict):
        return False
    typed_actual = cast(dict[str, object], actual)
    return (
        typed_actual.get("selected_frame") is not None
        and typed_actual.get("frame_fit") is not False
    )


def _stage(stages: dict[str, Any], stage_id: str) -> dict[str, Any] | None:
    value = stages.get(stage_id)
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _effective_mention_candidate_id_set(
    hp1: dict[str, Any] | None,
) -> set[str]:
    if hp1 is None:
        return set()
    if "boundary_adjudications" not in hp1:
        # Finalized pre-v4 evaluation evidence is immutable and contains only
        # deterministic boundary selections. It is never written back or routed
        # into the production extraction pipeline.
        return {
            str(candidate_id)
            for decision in _records(hp1, "boundary_decisions")
            for candidate_id in cast(list[str], decision.get("selected_candidate_ids", []))
        }
    decisions = tuple(
        MentionBoundaryDecision.model_validate_json(_canonical_json(item))
        for item in _records(hp1, "boundary_decisions")
    )
    adjudications = tuple(
        MentionBoundaryAdjudication.model_validate_json(_canonical_json(item))
        for item in _records(hp1, "boundary_adjudications")
    )
    return set(effective_mention_candidate_ids(decisions, adjudications))


def _records(container: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if container is None:
        return []
    value = container.get(key, [])
    if not isinstance(value, list):
        return []
    return [
        cast(dict[str, Any], item) for item in cast(list[object], value) if isinstance(item, dict)
    ]


def _check(
    check_id: str,
    stage_id: str,
    passed: bool,
    expected: object,
    actual: object,
) -> TaskAllocationCheck:
    return TaskAllocationCheck(
        check_id=check_id,
        stage_id=stage_id,
        passed=passed,
        expected=expected,
        actual=actual,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalized(value: str) -> str:
    return " ".join(value.split())
