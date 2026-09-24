"""Strict top-level contract for current Hybrid Pipeline evaluation evidence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_application import (
    HybridParagraphStageRecord,
    HybridStageDisposition,
    HybridStageId,
    StandingFactHoldReason,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[a-f0-9]{64}$"

_COMPLETE = "complete"
_PARTIAL = "partial"

_BOUNDARY_LINE = "standing_fact_line_rejected:"
_BOUNDARY_RELATION = "standing_fact_relation_rejected:"
_STANDING_FACT_HELD = "standing_fact_held:"


class HybridParagraphGapClass(StrEnum):
    """One mutually-exclusive partial-cause class for a paragraph."""

    COMPLETE = _COMPLETE
    PROPOSAL_REJECTED = "proposal_rejected"
    BOUNDARY_HELD = "boundary_held"
    ROUTED = "routed"
    HELD = "held"
    INHERITED_PARTIAL = "inherited_partial"


class HybridParagraphGapBreakdown(BaseModel):
    """Non-complete paragraph classes; every paragraph is counted exactly once."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    proposal_rejected: Annotated[int, Field(ge=0)]
    boundary_held: Annotated[int, Field(ge=0)]
    routed: Annotated[int, Field(ge=0)]
    held: Annotated[int, Field(ge=0)]
    inherited_partial: Annotated[int, Field(ge=0)]

    @property
    def total(self) -> int:
        """Total non-complete paragraphs across every gap class."""
        return (
            self.proposal_rejected
            + self.boundary_held
            + self.routed
            + self.held
            + self.inherited_partial
        )

    @classmethod
    def from_classes(cls, classes: Iterable[HybridParagraphGapClass]) -> Self:
        counts = Counter(classes)
        return cls(
            proposal_rejected=counts[HybridParagraphGapClass.PROPOSAL_REJECTED],
            boundary_held=counts[HybridParagraphGapClass.BOUNDARY_HELD],
            routed=counts[HybridParagraphGapClass.ROUTED],
            held=counts[HybridParagraphGapClass.HELD],
            inherited_partial=counts[HybridParagraphGapClass.INHERITED_PARTIAL],
        )


def classify_hybrid_paragraph_gap(
    stages: tuple[HybridParagraphStageRecord, ...],
) -> HybridParagraphGapClass:
    """Classify one Paragraph Receipt into exactly one paragraph-gap class.

    Precedence collapses the HP-1 -> HP-3 partial cascade and the HP-3 ->
    HP-10 cascade so a partial paragraph is counted once: HP-1 partial wins
    outright, then HP-3 partial, then HP-10 partial.
    """
    by_stage = {stage.stage_id: stage for stage in stages}
    if set(by_stage) != set(HybridStageId):
        raise ValueError("Paragraph gap classification requires every HP stage exactly once.")
    resolved = {
        stage_id: _terminal_status(by_stage[stage_id])
        for stage_id in (
            HybridStageId.HP1_MENTIONS,
            HybridStageId.HP3_GROUNDING,
            HybridStageId.HP10_STANDING_FACTS,
        )
    }
    if resolved[HybridStageId.HP1_MENTIONS] == _PARTIAL:
        return HybridParagraphGapClass.PROPOSAL_REJECTED
    if resolved[HybridStageId.HP3_GROUNDING] == _PARTIAL:
        return HybridParagraphGapClass.INHERITED_PARTIAL
    if resolved[HybridStageId.HP10_STANDING_FACTS] == _PARTIAL:
        return _classify_hp10_partial(by_stage[HybridStageId.HP10_STANDING_FACTS])
    return HybridParagraphGapClass.COMPLETE


def _terminal_status(stage: HybridParagraphStageRecord) -> str:
    if stage.disposition is HybridStageDisposition.NOT_RUN:
        raise ValueError(
            f"Paragraph gap classification cannot evaluate a not-run {stage.stage_id.value} stage."
        )
    status = stage.terminal_status
    if status not in (_COMPLETE, _PARTIAL):
        raise ValueError(
            f"Paragraph gap classification cannot evaluate {stage.stage_id.value} "
            f"terminal status {status!r}."
        )
    return status


def _classify_hp10_partial(
    stage: HybridParagraphStageRecord,
) -> HybridParagraphGapClass:
    route_required = False
    for diagnostic in stage.diagnostics:
        if diagnostic.startswith(_BOUNDARY_LINE) or diagnostic.startswith(
            _BOUNDARY_RELATION
        ):
            return HybridParagraphGapClass.BOUNDARY_HELD
        if not diagnostic.startswith(_STANDING_FACT_HELD):
            continue
        reason = StandingFactHoldReason(diagnostic.rsplit(":", 1)[-1])
        if reason is StandingFactHoldReason.EVENT_ROUTE_REQUIRED:
            route_required = True
        elif reason is StandingFactHoldReason.COMPLETE_PROPOSITION_HELD:
            continue
        else:
            return HybridParagraphGapClass.BOUNDARY_HELD
    if route_required:
        return HybridParagraphGapClass.ROUTED
    return HybridParagraphGapClass.HELD


class CurrentHybridEvaluationSummary(BaseModel):
    """Operator-facing counts from only current evaluation contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    passed: bool
    required_paragraphs: Annotated[int, Field(ge=0)]
    complete_paragraphs: Annotated[int, Field(ge=0)]
    gap_breakdown: HybridParagraphGapBreakdown
    paragraph_proposed_changes: Annotated[int, Field(ge=0)]
    reconciled_proposed_changes: Annotated[int, Field(ge=0)]
    source_grounded_events_expected: Annotated[int, Field(ge=0)]
    source_grounded_events_observed: Annotated[int, Field(ge=0)]
    source_grounded_events_exact: Annotated[int, Field(ge=0)]
    source_grounded_events_missing: Annotated[int, Field(ge=0)]
    source_grounded_events_extra: Annotated[int, Field(ge=0)]
    source_grounded_events_incorrect: Annotated[int, Field(ge=0)]
    front_half_items_expected: Annotated[int, Field(ge=0)]
    front_half_items_exact: Annotated[int, Field(ge=0)]
    standing_facts_expected: Annotated[int, Field(ge=0)]
    standing_facts_exact: Annotated[int, Field(ge=0)]
    standing_facts_missing: Annotated[int, Field(ge=0)]
    standing_facts_incorrect: Annotated[int, Field(ge=0)]
    standing_facts_not_proposed: Annotated[int, Field(ge=0)]
    standing_facts_lineage_incomplete: Annotated[int, Field(ge=0)]
    standing_facts_not_visible: Annotated[int, Field(ge=0)]
    replay_model_calls: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_partition_counts(self) -> Self:
        if self.complete_paragraphs + self.gap_breakdown.total != self.required_paragraphs:
            raise ValueError("Current evaluation paragraph counts do not partition the scope.")
        return self


class CurrentHybridEvaluationReport(BaseModel):
    """The only supported full-document Hybrid evaluation report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hp8_document_orchestration_evaluation_v3"] = (
        "hp8_document_orchestration_evaluation_v3"
    )
    source_path: Annotated[str, Field(min_length=1)]
    source_sha256: Annotated[str, Field(pattern=_SHA256)]
    policy_manifest: dict[str, JsonValue]
    coverage_report: dict[str, JsonValue]
    paragraphs: list[dict[str, JsonValue]]
    source_grounded_event_evaluation: dict[str, JsonValue]
    front_half_evaluation: dict[str, JsonValue]
    standing_fact_evaluation: dict[str, JsonValue]
    candidate_wiki: dict[str, JsonValue]
    first_public_output: dict[str, JsonValue]
    replay_public_output: dict[str, JsonValue]
    first_ledger_counts: dict[str, JsonValue]
    model_performance: dict[str, JsonValue]
    model_executions: list[dict[str, JsonValue]]
    replay_ledger_counts: dict[str, JsonValue]
    ingestion_change_set_origins: list[str]
    findings: list[dict[str, JsonValue]]
    summary: CurrentHybridEvaluationSummary

    @model_validator(mode="after")
    def validate_current_contracts(self) -> Self:
        expected_schemas = (
            (
                self.source_grounded_event_evaluation,
                "hsq_source_grounded_event_report_v1",
            ),
            (self.front_half_evaluation, "hsq_front_half_evaluation_v1"),
            (self.standing_fact_evaluation, "hsq_standing_fact_evaluation_v1"),
        )
        for result, expected in expected_schemas:
            if result.get("schema_version") != expected:
                raise ValueError(f"Current evaluation requires {expected}.")
        if self.summary.passed != (not self.findings):
            raise ValueError("Current evaluation pass state must equal an empty findings list.")
        return self
