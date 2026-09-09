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
    expected_trigger_text: str | None = None
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
            if self.expected_trigger_text is None or self.expected_frame_id is None:
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
                    self.expected_trigger_text,
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
            self.expected_trigger_text is None
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

    schema_version: Literal["hsq_task_allocation_gold_v1"]
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
                item.expected_trigger_text is not None
                and item.expected_trigger_text not in segment.exact_text
            ):
                raise ValueError(
                    f"{item.item_id} trigger is absent from its authoritative source text."
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


def load_task_allocation_gold(path: Path) -> TaskAllocationGoldCatalog:
    return TaskAllocationGoldCatalog.model_validate_json(path.read_bytes())


def evaluate_task_allocation_catalog(
    catalog: TaskAllocationGoldCatalog,
    paragraphs: list[dict[str, Any]],
    *,
    wiki_plan: CandidateWikiPlan | None = None,
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
        wrong_forced_frame_count=sum(_wrong_forced_frame(item) for item in results),
        first_failed_stage_counts=dict(sorted(failed_counts.items())),
        items=tuple(results),
    )


def _evaluate_item(
    catalog: TaskAllocationGoldCatalog,
    expected: TaskAllocationItem,
    source_segment_text: str,
    paragraph: dict[str, Any] | None,
    wiki_plan: CandidateWikiPlan | None,
) -> TaskAllocationItemEvaluation:
    stages = cast(dict[str, Any], paragraph.get("stage_outputs", {})) if paragraph else {}
    raw_outputs = cast(dict[str, Any], paragraph.get("raw_model_outputs", {})) if paragraph else {}
    hp2 = _stage(stages, "hp2_references")
    hp4 = _stage(stages, "hp4_event_triggers")
    hp6 = _stage(stages, "hp6_event_semantics")
    hp7 = _stage(stages, "hp7_proposal_plan")
    hp10 = _stage(stages, "hp10_standing_facts")
    trigger_matches = [
        item
        for item in _records(hp4, "triggers")
        if item.get("source_text_sha256") == expected.source_segment_sha256
        and _normalized(str(item.get("text", "")))
        == _normalized(expected.expected_trigger_text or "")
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
    checks: list[TaskAllocationCheck] = []
    actual: dict[str, object] = {
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
    if expected.expected_route == "event":
        checks.append(
            _check(
                "trigger",
                "source_occurrence_selection",
                len(trigger_matches) == 1,
                expected.expected_trigger_text,
                [item.get("text") for item in trigger_matches],
            )
        )
        checks.extend(_reference_checks(expected, hp2, expected.source_segment_sha256))
        checks.append(
            _check(
                "frame",
                "bounded_frame_selection",
                semantic is not None and semantic.get("frame_id") == expected.expected_frame_id,
                expected.expected_frame_id,
                semantic.get("frame_id") if semantic else _selected_frame(hp6, trigger),
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
        checks.append(
            _check(
                "trigger",
                "source_occurrence_selection",
                len(trigger_matches) == 1,
                expected.expected_trigger_text,
                [item.get("text") for item in trigger_matches],
            )
        )
        checks.extend(_reference_checks(expected, hp2, expected.source_segment_sha256))
        selected_frame = _selected_frame(hp6, trigger)
        if expected.expected_frame_id is None:
            frame_matches = selected_frame is None and semantic is None
        else:
            frame_matches = selected_frame == expected.expected_frame_id
        checks.append(
            _check(
                "gap_frame",
                "bounded_frame_selection",
                frame_matches,
                expected.expected_frame_id or "unresolved",
                selected_frame,
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
            proposal_ids,
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
        (hp2, hp4, hp6, hp7, hp10),
        raw_outputs,
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


def _reference_checks(
    expected: TaskAllocationItem,
    hp2: dict[str, Any] | None,
    source_segment_sha256: str,
) -> list[TaskAllocationCheck]:
    checks: list[TaskAllocationCheck] = []
    segment_decision_ids = _reference_decision_ids_for_source(
        hp2,
        source_segment_sha256,
    )
    spans = {
        str(item.get("id")): str(item.get("text", ""))
        for item in _records(hp2, "semantic_antecedent_spans")
    }
    for index, reference in enumerate(expected.expected_references, start=1):
        matching = [
            item
            for item in _records(hp2, "reference_decisions")
            if item.get("semantic_reference_decision_id") in segment_decision_ids
            if _normalized(
                str(cast(dict[str, Any], item.get("reference_span", {})).get("text", ""))
            )
            == _normalized(reference.reference_text)
        ]
        selected_texts = [
            spans[span_id]
            for item in matching
            for span_id in cast(list[str], item.get("antecedent_span_ids", []))
            if span_id in spans
        ]
        checks.append(
            _check(
                f"reference_{index}",
                "reference_challenge",
                len(matching) == 1
                and matching[0].get("status") == "resolved"
                and any(
                    _normalized(value) == _normalized(reference.antecedent_text)
                    for value in selected_texts
                ),
                reference.model_dump(mode="json"),
                {"decisions": matching, "selected_texts": selected_texts},
            )
        )
    return checks


def _reference_decision_ids_for_source(
    hp2: dict[str, Any] | None,
    source_segment_sha256: str,
) -> set[str]:
    decision_ids: set[str] = set()
    for trace in _records(hp2, "traces"):
        if trace.get("source_text_sha256") != source_segment_sha256:
            continue
        output = trace.get("output")
        if not isinstance(output, dict):
            continue
        typed_output = cast(dict[str, object], output)
        decision = typed_output.get("decision")
        if not isinstance(decision, dict):
            continue
        typed_decision = cast(dict[str, object], decision)
        decision_id = typed_decision.get("id")
        if isinstance(decision_id, str):
            decision_ids.add(decision_id)
    return decision_ids


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
) -> tuple[TaskAllocationStageEvidence, ...]:
    evidence: list[TaskAllocationStageEvidence] = []
    for stage in stages:
        for trace in _records(stage, "traces"):
            if trace.get("source_text_sha256") != source_sha256:
                continue
            trace_input = cast(dict[str, Any], trace.get("input", {}))
            model_visible = trace_input.get("model_visible_task")
            exact_input = (
                str(model_visible)
                if isinstance(model_visible, str) and model_visible
                else _canonical_json(trace_input)
            )
            raw = None
            for execution_id in cast(list[str], trace.get("execution_record_ids", [])):
                if not execution_id.startswith("mrn_"):
                    continue
                raw_record = raw_outputs.get(execution_id)
                if isinstance(raw_record, dict):
                    raw = cast(dict[str, Any], raw_record).get("raw_output")
                elif isinstance(raw_record, str):
                    raw = raw_record
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


def _wiki_result(
    catalog: TaskAllocationGoldCatalog,
    proposal_ids: tuple[str, ...],
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
                presentation_proposals: set[str] = set(presentation.proposed_change_ids)
            else:
                presentation_proposals = (
                    {presentation.proposed_change_id}
                    if presentation.proposed_change_id is not None
                    else set()
                )
            if not set(proposal_ids) & presentation_proposals:
                continue
            if any(
                hashlib.sha256(citations[number].exact_text.encode()).hexdigest() == source_sha256
                for number in presentation.citation_numbers
                if number in citations
            ):
                matched_paths.add(page.relative_path)
    return bool(matched_paths), tuple(sorted(matched_paths))


def _wrong_forced_frame(item: TaskAllocationItemEvaluation) -> bool:
    if item.expected_route != "typed_ontology_gap":
        return False
    expected = next(
        (check.expected for check in item.checks if check.check_id == "gap_frame"), None
    )
    actual = next((check.actual for check in item.checks if check.check_id == "gap_frame"), None)
    return expected == "unresolved" and actual is not None


def _stage(stages: dict[str, Any], stage_id: str) -> dict[str, Any] | None:
    value = stages.get(stage_id)
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


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
