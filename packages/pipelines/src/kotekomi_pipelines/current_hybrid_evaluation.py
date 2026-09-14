"""Strict top-level contract for current Hybrid Pipeline evaluation evidence."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[a-f0-9]{64}$"


class CurrentHybridEvaluationSummary(BaseModel):
    """Operator-facing counts from only current evaluation contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    passed: bool
    required_paragraphs: Annotated[int, Field(ge=0)]
    complete_paragraphs: Annotated[int, Field(ge=0)]
    gap_paragraphs: Annotated[int, Field(ge=0)]
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
        if self.complete_paragraphs + self.gap_paragraphs != self.required_paragraphs:
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
