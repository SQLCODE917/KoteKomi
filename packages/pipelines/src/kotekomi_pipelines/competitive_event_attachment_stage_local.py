"""Gold oracle, baseline import, and evaluation for CEA-1."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from kotekomi_application import (
    PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID,
    PROPOSITION_SCOPE_POLICY_ID,
    CompetitiveAttachmentCaseEvaluation,
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentExperimentOutcome,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentMetrics,
    CompetitiveAttachmentPhaseReport,
    ExtractionStageTrace,
    PropositionFragmentCandidate,
    PropositionFragmentDecision,
    SourceGroundedPropositionScope,
    proposition_fragment_answer_schema_bytes,
    source_grounded_proposition_result_sha256,
)
from kotekomi_domain import ModelRun
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragmentRequirement,
    PropositionScopePhaseReport,
)

_SHA256 = r"^[a-f0-9]{64}$"


class CompetitiveAttachmentBaselineDisposition(StrEnum):
    """One imported independent-task outcome."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNRESOLVED = "unresolved"
    MISSING = "missing"


class CompetitiveAttachmentBaselineEventResult(BaseModel):
    """Imported prompt-v3 disposition for one candidate/Event pair."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    parent_candidate_id: Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")] | None
    disposition: CompetitiveAttachmentBaselineDisposition
    reason_code: Annotated[str, Field(min_length=1)]
    parent_decision_id: Annotated[str, Field(pattern=r"^pfd_[a-f0-9]{24}$")] | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        missing = self.disposition is CompetitiveAttachmentBaselineDisposition.MISSING
        if missing != (self.parent_candidate_id is None and self.parent_decision_id is None):
            raise ValueError("Competitive Attachment baseline missing lineage drifted.")
        return self


class CompetitiveAttachmentBaselineDecision(BaseModel):
    """Complete independent baseline for one shared candidate occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]
    event_results: tuple[CompetitiveAttachmentBaselineEventResult, ...]
    attached_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]
    unresolved_event_ids: tuple[Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(sorted(self.event_results, key=lambda item: item.source_grounded_event_id)) != (
            self.event_results
        ):
            raise ValueError("Competitive Attachment baseline Events must use canonical order.")
        expected_attached = tuple(
            item.source_grounded_event_id
            for item in self.event_results
            if item.disposition is CompetitiveAttachmentBaselineDisposition.INCLUDED
        )
        expected_unresolved = tuple(
            item.source_grounded_event_id
            for item in self.event_results
            if item.disposition
            in {
                CompetitiveAttachmentBaselineDisposition.UNRESOLVED,
                CompetitiveAttachmentBaselineDisposition.MISSING,
            }
        )
        if self.attached_event_ids != expected_attached:
            raise ValueError("Competitive Attachment baseline attached Events drifted.")
        if self.unresolved_event_ids != expected_unresolved:
            raise ValueError("Competitive Attachment baseline unresolved Events drifted.")
        return self


class CompetitiveAttachmentPreflightEvent(BaseModel):
    """Exact candidate coverage for one reviewed Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    gold_event_id: Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    covered_fragment_ids: tuple[str, ...]
    missing_fragment_ids: tuple[str, ...]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.passed != (not self.missing_fragment_ids):
            raise ValueError("Competitive Attachment preflight status drifted.")
        return self


class CompetitiveAttachmentPreflightReport(BaseModel):
    """Model-free matrix and Gold coverage proof."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_attachment_preflight_v1"] = (
        "competitive_attachment_preflight_v1"
    )
    phase: Literal["development", "validation"]
    event_count: Annotated[int, Field(ge=1)]
    source_segment_count: Annotated[int, Field(ge=1)]
    candidate_count: Annotated[int, Field(ge=1)]
    shared_gold_candidate_count: Annotated[int, Field(ge=0)]
    empty_gold_candidate_count: Annotated[int, Field(ge=0)]
    events: tuple[CompetitiveAttachmentPreflightEvent, ...]
    source_validity: Annotated[float, Field(ge=0, le=1)]
    passed: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.event_count != len(self.events):
            raise ValueError("Competitive Attachment preflight Event count drifted.")
        expected = self.source_validity == 1.0 and all(item.passed for item in self.events)
        if self.passed != expected:
            raise ValueError("Competitive Attachment preflight terminal status drifted.")
        return self


class CompetitiveAttachmentDiagnosticApproval(BaseModel):
    """Human approval of one invariant competitive-task contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_attachment_diagnostic_approval_v2"] = (
        "competitive_attachment_diagnostic_approval_v2"
    )
    reviewer: Annotated[str, Field(min_length=1)]
    diagnostic_result_sha256: Annotated[str, Field(pattern=_SHA256)]
    diagnostic_review_sha256: Annotated[str, Field(pattern=_SHA256)]
    prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    execution_contract_sha256: Annotated[str, Field(pattern=_SHA256)]
    status: Literal["approved"] = "approved"

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.reviewer != self.reviewer.strip():
            raise ValueError("Competitive Attachment reviewer must be trimmed.")
        return self


class CompetitiveAttachmentComparison(BaseModel):
    """Frozen development and validation outcome for CEA-1."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["competitive_attachment_comparison_v1"] = (
        "competitive_attachment_comparison_v1"
    )
    development_report_sha256s: tuple[Annotated[str, Field(pattern=_SHA256)], ...]
    validation_report_sha256: Annotated[str, Field(pattern=_SHA256)]
    development_stable: bool
    exact_accuracy_improved_development: bool
    exact_accuracy_improved_validation: bool
    leakage_reduced_development: bool
    leakage_reduced_validation: bool
    protected_recall_preserved_development: bool
    protected_recall_preserved_validation: bool
    safety_gates_passed: bool
    outcome: CompetitiveAttachmentExperimentOutcome
    production_integration: Literal["not_activated"] = "not_activated"


def validate_competitive_attachment_diagnostic_approval(
    payload: object,
    *,
    expected_prompt_sha256: str,
    expected_execution_contract_sha256: str,
) -> CompetitiveAttachmentDiagnosticApproval:
    """Validate approval against invariant task behavior, not phase-local labels."""
    try:
        approval = CompetitiveAttachmentDiagnosticApproval.model_validate(payload)
    except ValidationError as error:
        raise ValueError("CEA-1 requires a valid approved diagnostic review.") from error
    if approval.prompt_sha256 != expected_prompt_sha256:
        raise ValueError("CEA-1 diagnostic approved a different prompt.")
    if approval.execution_contract_sha256 != expected_execution_contract_sha256:
        raise ValueError("CEA-1 diagnostic approved a different execution contract.")
    return approval


def build_competitive_attachment_oracle(
    *,
    catalog: PropositionGoldCatalog,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    source_grounded_event_by_gold_id: dict[str, str],
) -> tuple[
    dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    CompetitiveAttachmentPreflightReport,
]:
    """Derive occurrence-level Gold sets and prove candidate representability."""
    gold_events = tuple(item for item in catalog.events if item.phase == phase)
    if set(source_grounded_event_by_gold_id) != {item.event_id for item in gold_events}:
        raise ValueError("Competitive Attachment Gold binding does not cover its phase.")
    matrix_by_digest = {item.source_text_sha256: item for item in matrices}
    if len(matrix_by_digest) != len(matrices):
        raise ValueError("Competitive Attachment matrices repeat a SourceSegment digest.")
    gold_by_sge = {source_grounded_event_by_gold_id[item.event_id]: item for item in gold_events}
    decisions_by_matrix: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]] = {}
    preflight_events: list[CompetitiveAttachmentPreflightEvent] = []
    shared = 0
    empty = 0
    total_candidates = 0
    source_valid_count = 0
    for matrix in matrices:
        relevant = {
            event_id: gold_by_sge[event_id]
            for event_id in (option.source_grounded_event_id for option in matrix.event_options)
        }
        matrix_decisions: list[CompetitiveAttachmentGoldDecision] = []
        for candidate in matrix.candidates:
            if candidate.source_text_sha256 != matrix.source_text_sha256:
                raise ValueError("Competitive Attachment candidate source digest drifted.")
            source_valid_count += 1
            event_ids = tuple(
                sorted(
                    event_id
                    for event_id, gold in relevant.items()
                    if _candidate_belongs_to_gold(candidate.start, candidate.end, gold)
                )
            )
            if len(event_ids) > 1:
                shared += 1
            if not event_ids:
                empty += 1
            matrix_decisions.append(
                CompetitiveAttachmentGoldDecision(
                    candidate_id=candidate.id,
                    source_grounded_event_ids=event_ids,
                )
            )
        total_candidates += len(matrix.candidates)
        decisions_by_matrix[matrix.id] = tuple(matrix_decisions)
        for event_id, gold in relevant.items():
            compatible = tuple(
                candidate
                for candidate, decision in zip(matrix.candidates, matrix_decisions, strict=True)
                if event_id in decision.source_grounded_event_ids
            )
            positions = _positions(
                gold.source_text,
                tuple((item.start, item.end) for item in compatible),
            )
            covered = tuple(
                item.fragment_id
                for item in gold.fragments
                if _positions(gold.source_text, ((item.start, item.end),)) <= positions
            )
            missing = tuple(
                item.fragment_id for item in gold.fragments if item.fragment_id not in set(covered)
            )
            gold_id = next(
                key for key, value in source_grounded_event_by_gold_id.items() if value == event_id
            )
            preflight_events.append(
                CompetitiveAttachmentPreflightEvent(
                    gold_event_id=gold_id,
                    source_grounded_event_id=event_id,
                    covered_fragment_ids=tuple(sorted(covered)),
                    missing_fragment_ids=tuple(sorted(missing)),
                    passed=not missing,
                )
            )
    if set(matrix_by_digest) != {item.source_text_sha256 for item in gold_events}:
        raise ValueError("Competitive Attachment matrices do not cover every Gold SourceSegment.")
    source_validity = _ratio(source_valid_count, total_candidates)
    ordered_events = tuple(sorted(preflight_events, key=lambda item: item.gold_event_id))
    report = CompetitiveAttachmentPreflightReport(
        phase=phase,
        event_count=len(gold_events),
        source_segment_count=len(matrices),
        candidate_count=total_candidates,
        shared_gold_candidate_count=shared,
        empty_gold_candidate_count=empty,
        events=ordered_events,
        source_validity=source_validity,
        passed=source_validity == 1.0 and all(item.passed for item in ordered_events),
    )
    return decisions_by_matrix, report


def load_prompt_v3_baseline(
    *,
    run_root: Path,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_event_to_source_grounded_event: dict[str, str],
    expected_gold_sha256: str,
    expected_prompt_sha256: str,
    expected_runtime: dict[str, object] | None = None,
) -> dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]]:
    """Import one finalized independent run after replaying every stored digest."""
    metadata_path = run_root / "run.json"
    manifest_path = run_root / "manifest.json"
    report_path = run_root / "report.json"
    for path in (metadata_path, manifest_path, report_path):
        if not path.is_file():
            raise ValueError(f"Competitive Attachment baseline is missing {path.name}.")
    metadata = _read_json(metadata_path)
    manifest = _read_json(manifest_path)
    if metadata.get("schema_version") != "source_grounded_proposition_experiment_run_v1":
        raise ValueError("Competitive Attachment baseline run schema is unknown.")
    if metadata.get("status") != "finalized" or metadata.get("phase") != phase:
        raise ValueError("Competitive Attachment baseline phase is not finalized.")
    if metadata.get("gold_sha256") != expected_gold_sha256:
        raise ValueError("Competitive Attachment baseline Gold digest drifted.")
    if metadata.get("prompt_sha256") != expected_prompt_sha256:
        raise ValueError("Competitive Attachment baseline prompt digest drifted.")
    if manifest.get("report_sha256") != _sha(report_path.read_bytes()):
        raise ValueError("Competitive Attachment baseline report digest drifted.")
    baseline_report = PropositionScopePhaseReport.model_validate_json(report_path.read_bytes())
    if (
        baseline_report.phase != phase
        or manifest.get("phase") != phase
        or manifest.get("result_fingerprint") != baseline_report.result_fingerprint
    ):
        raise ValueError("Competitive Attachment baseline report identity drifted.")
    if expected_runtime is not None and metadata.get("runtime") != expected_runtime:
        raise ValueError("Competitive Attachment baseline runtime contract drifted.")
    if metadata.get("schema_id") != PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID:
        raise ValueError("Competitive Attachment baseline output schema identity drifted.")
    if metadata.get("schema_sha256") != _sha(proposition_fragment_answer_schema_bytes()):
        raise ValueError("Competitive Attachment baseline output schema digest drifted.")
    if metadata.get("policy_id") != PROPOSITION_SCOPE_POLICY_ID:
        raise ValueError("Competitive Attachment baseline policy identity drifted.")
    for field_name, filename in (
        ("canonical_state_sha256", "canonical-state.json"),
        ("inputs_sha256", "inputs.jsonl"),
        ("preflight_sha256", "preflight.json"),
        ("preflight_review_sha256", "preflight-review.md"),
    ):
        path = run_root / filename
        if not path.is_file() or metadata.get(field_name) != _sha(path.read_bytes()):
            raise ValueError(f"Competitive Attachment baseline {filename} digest drifted.")
    review_path = run_root / "review.md"
    if not review_path.is_file() or manifest.get("review_sha256") != _sha(review_path.read_bytes()):
        raise ValueError("Competitive Attachment baseline review digest drifted.")
    if (
        manifest.get("accepted_ledger_change_count") != 0
        or manifest.get("proposed_change_count") != 0
    ):
        raise ValueError("Competitive Attachment baseline changed accepted state.")
    records: dict[str, dict[str, Any]] = {}
    for path in sorted((run_root / "events").glob("*.json")):
        record = _read_json(path)
        prepared = _validate_baseline_record(record)
        gold_event_id = str(record["gold_event_id"])
        if prepared.gold_event_id != gold_event_id:
            raise ValueError("Competitive Attachment baseline Gold Event binding drifted.")
        if gold_event_id in records:
            raise ValueError("Competitive Attachment baseline repeats a Gold Event.")
        records[gold_event_id] = record
    if set(records) != set(gold_event_to_source_grounded_event):
        raise ValueError("Competitive Attachment baseline Event inventory drifted.")
    record_by_sge = {
        gold_event_to_source_grounded_event[gold_id]: record for gold_id, record in records.items()
    }
    for source_grounded_event_id, record in record_by_sge.items():
        prepared = EventEntityExperimentInput.model_validate_json(
            _canonical_json(record["prepared_input"])
        )
        if prepared.event.id != source_grounded_event_id:
            raise ValueError("Competitive Attachment baseline source Event binding drifted.")
    return reconstruct_prompt_v3_baseline(
        matrices=matrices,
        record_by_source_grounded_event_id=record_by_sge,
    )


def reconstruct_prompt_v3_baseline(
    *,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    record_by_source_grounded_event_id: dict[str, dict[str, Any]],
) -> dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]]:
    """Map validated independent decisions onto the shared candidate inventory."""
    result: dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]] = {}
    for matrix in matrices:
        matrix_results: list[CompetitiveAttachmentBaselineDecision] = []
        for candidate in matrix.candidates:
            event_results: list[CompetitiveAttachmentBaselineEventResult] = []
            for option in matrix.event_options:
                try:
                    record = record_by_source_grounded_event_id[option.source_grounded_event_id]
                except KeyError as error:
                    raise ValueError(
                        "Competitive Attachment baseline lacks one source Event."
                    ) from error
                parents = tuple(
                    item
                    for item in cast(list[dict[str, Any]], record["candidates"])
                    if item["id"] in candidate.parent_candidate_ids
                )
                if not parents:
                    event_results.append(
                        CompetitiveAttachmentBaselineEventResult(
                            source_grounded_event_id=option.source_grounded_event_id,
                            parent_candidate_id=None,
                            disposition=CompetitiveAttachmentBaselineDisposition.MISSING,
                            reason_code="candidate_not_offered_to_independent_event",
                            parent_decision_id=None,
                        )
                    )
                    continue
                if len(parents) != 1:
                    raise ValueError("Competitive Attachment baseline repeats a candidate range.")
                parent = parents[0]
                decisions = tuple(
                    item
                    for item in cast(list[dict[str, Any]], record["decisions"])
                    if item["candidate_id"] == parent["id"]
                )
                if len(decisions) != 1:
                    raise ValueError("Competitive Attachment baseline lacks one parent decision.")
                parent_decision = decisions[0]
                disposition = CompetitiveAttachmentBaselineDisposition(
                    str(parent_decision["disposition"])
                )
                event_results.append(
                    CompetitiveAttachmentBaselineEventResult(
                        source_grounded_event_id=option.source_grounded_event_id,
                        parent_candidate_id=str(parent["id"]),
                        disposition=disposition,
                        reason_code=str(parent_decision["reason_code"]),
                        parent_decision_id=str(parent_decision["id"]),
                    )
                )
            ordered = tuple(sorted(event_results, key=lambda item: item.source_grounded_event_id))
            matrix_results.append(
                CompetitiveAttachmentBaselineDecision(
                    candidate_id=candidate.id,
                    event_results=ordered,
                    attached_event_ids=tuple(
                        item.source_grounded_event_id
                        for item in ordered
                        if item.disposition is CompetitiveAttachmentBaselineDisposition.INCLUDED
                    ),
                    unresolved_event_ids=tuple(
                        item.source_grounded_event_id
                        for item in ordered
                        if item.disposition
                        in {
                            CompetitiveAttachmentBaselineDisposition.UNRESOLVED,
                            CompetitiveAttachmentBaselineDisposition.MISSING,
                        }
                    ),
                )
            )
        result[matrix.id] = tuple(matrix_results)
    return result


def build_competitive_attachment_phase_report(
    *,
    catalog: PropositionGoldCatalog,
    catalog_sha256: str,
    phase: Literal["development", "validation"],
    repetition: int,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_by_matrix: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
    baseline_by_matrix: dict[str, tuple[CompetitiveAttachmentBaselineDecision, ...]],
    source_grounded_event_by_gold_id: dict[str, str],
    entity_occurrences_by_gold_event: dict[str, tuple[tuple[int, int], ...]],
    model_execution_count: int,
    input_token_count: int,
    output_token_count: int,
    elapsed_milliseconds: int,
) -> CompetitiveAttachmentPhaseReport:
    """Build exact occurrence and proposition metrics from terminal matrices."""
    cases: list[CompetitiveAttachmentCaseEvaluation] = []
    baseline_edges: dict[str, set[str]] = {}
    competitive_edges: dict[str, set[str]] = {}
    gold_edges: dict[str, set[str]] = {}
    decision_statuses: dict[str, CompetitiveAttachmentDecisionStatus] = {}
    for matrix in matrices:
        if len(matrix.decisions) != len(matrix.candidates):
            raise ValueError("Competitive Attachment report requires terminal matrices.")
        gold_by_candidate = {item.candidate_id: item for item in gold_by_matrix[matrix.id]}
        baseline_by_candidate = {item.candidate_id: item for item in baseline_by_matrix[matrix.id]}
        for candidate, decision in zip(matrix.candidates, matrix.decisions, strict=True):
            gold = gold_by_candidate[candidate.id]
            baseline = baseline_by_candidate[candidate.id]
            competitive = tuple(sorted(item.source_grounded_event_id for item in decision.edges))
            gold_set = set(gold.source_grounded_event_ids)
            competitive_set = set(competitive)
            cases.append(
                CompetitiveAttachmentCaseEvaluation(
                    candidate_id=candidate.id,
                    gold_event_ids=gold.source_grounded_event_ids,
                    baseline_event_ids=baseline.attached_event_ids,
                    competitive_event_ids=competitive,
                    baseline_unresolved_event_ids=baseline.unresolved_event_ids,
                    competitive_unresolved=(
                        decision.status is not CompetitiveAttachmentDecisionStatus.COMPLETE
                    ),
                    true_positive_edge_count=len(gold_set & competitive_set),
                    false_positive_edge_count=len(competitive_set - gold_set),
                    false_negative_edge_count=len(gold_set - competitive_set),
                    sibling_event_leakage_count=(
                        len(competitive_set - gold_set) if gold_set else 0
                    ),
                    shared_gold_edge_count=len(gold_set) if len(gold_set) > 1 else 0,
                    shared_matched_edge_count=(
                        len(gold_set & competitive_set) if len(gold_set) > 1 else 0
                    ),
                    baseline_exact=(
                        not baseline.unresolved_event_ids
                        and set(baseline.attached_event_ids) == gold_set
                    ),
                    competitive_exact=(
                        decision.status is CompetitiveAttachmentDecisionStatus.COMPLETE
                        and competitive_set == gold_set
                    ),
                )
            )
            baseline_edges[candidate.id] = set(baseline.attached_event_ids)
            competitive_edges[candidate.id] = competitive_set
            gold_edges[candidate.id] = gold_set
            decision_statuses[candidate.id] = decision.status
    ordered_cases = tuple(sorted(cases, key=lambda item: item.candidate_id))
    metrics = _aggregate_metrics(
        catalog=catalog,
        phase=phase,
        matrices=matrices,
        cases=ordered_cases,
        baseline_edges=baseline_edges,
        competitive_edges=competitive_edges,
        gold_edges=gold_edges,
        decision_statuses=decision_statuses,
        source_grounded_event_by_gold_id=source_grounded_event_by_gold_id,
        entity_occurrences_by_gold_event=entity_occurrences_by_gold_event,
    )
    fingerprint_payload = {
        "catalog_sha256": catalog_sha256,
        "cases": [item.model_dump(mode="json") for item in ordered_cases],
        "metrics": metrics.model_dump(mode="json"),
        "phase": phase,
        "scoring_policy": "competitive_attachment_occurrence_v1",
    }
    fingerprint = _sha(_canonical_json(fingerprint_payload))
    return CompetitiveAttachmentPhaseReport(
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog_sha256,
        phase=phase,
        repetition=repetition,
        cases=ordered_cases,
        metrics=metrics,
        source_validity=1.0,
        gold_coverage=1.0,
        model_execution_count=model_execution_count,
        input_token_count=input_token_count,
        output_token_count=output_token_count,
        elapsed_milliseconds=elapsed_milliseconds,
        result_fingerprint=fingerprint,
    )


def compare_competitive_attachment_reports(
    development: tuple[CompetitiveAttachmentPhaseReport, ...],
    validation: CompetitiveAttachmentPhaseReport,
    *,
    development_report_sha256s: tuple[str, ...],
    validation_report_sha256: str,
) -> CompetitiveAttachmentComparison:
    """Classify the frozen CEA-1 hypothesis without activating production."""
    if len(development) != 3 or {item.repetition for item in development} != {1, 2, 3}:
        raise ValueError("CEA-1 comparison requires development repetitions 1, 2, and 3.")
    if any(item.phase != "development" for item in development):
        raise ValueError("CEA-1 development reports have the wrong phase.")
    if validation.phase != "validation" or validation.repetition != 1:
        raise ValueError("CEA-1 validation report has the wrong phase or repetition.")
    representative = sorted(development, key=lambda item: item.repetition)[0]
    stable = len({item.result_fingerprint for item in development}) == 1
    dev_accuracy = _accuracy_improved(representative.metrics)
    val_accuracy = _accuracy_improved(validation.metrics)
    dev_leakage = _leakage_reduced(representative.metrics)
    val_leakage = _leakage_reduced(validation.metrics)
    dev_recall = _protected_recall_preserved(representative.metrics)
    val_recall = _protected_recall_preserved(validation.metrics)
    safety = all(
        item.source_validity == 1.0
        and item.gold_coverage == 1.0
        and item.proposed_change_count == 0
        and item.accepted_ledger_change_count == 0
        for item in (*development, validation)
    )
    supported = (
        stable
        and safety
        and dev_accuracy
        and val_accuracy
        and dev_leakage
        and val_leakage
        and dev_recall
        and val_recall
    )
    falsified = not dev_accuracy and not val_accuracy and not dev_leakage and not val_leakage
    outcome = (
        CompetitiveAttachmentExperimentOutcome.SUPPORTED
        if supported
        else (
            CompetitiveAttachmentExperimentOutcome.FALSIFIED
            if falsified
            else CompetitiveAttachmentExperimentOutcome.MIXED
        )
    )
    return CompetitiveAttachmentComparison(
        development_report_sha256s=development_report_sha256s,
        validation_report_sha256=validation_report_sha256,
        development_stable=stable,
        exact_accuracy_improved_development=dev_accuracy,
        exact_accuracy_improved_validation=val_accuracy,
        leakage_reduced_development=dev_leakage,
        leakage_reduced_validation=val_leakage,
        protected_recall_preserved_development=dev_recall,
        protected_recall_preserved_validation=val_recall,
        safety_gates_passed=safety,
        outcome=outcome,
    )


def _aggregate_metrics(
    *,
    catalog: PropositionGoldCatalog,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    cases: tuple[CompetitiveAttachmentCaseEvaluation, ...],
    baseline_edges: dict[str, set[str]],
    competitive_edges: dict[str, set[str]],
    gold_edges: dict[str, set[str]],
    decision_statuses: dict[str, CompetitiveAttachmentDecisionStatus],
    source_grounded_event_by_gold_id: dict[str, str],
    entity_occurrences_by_gold_event: dict[str, tuple[tuple[int, int], ...]],
) -> CompetitiveAttachmentMetrics:
    tp = sum(item.true_positive_edge_count for item in cases)
    fp = sum(item.false_positive_edge_count for item in cases)
    fn = sum(item.false_negative_edge_count for item in cases)
    edge_precision = _ratio(tp, tp + fp)
    edge_recall = _ratio(tp, tp + fn)
    shared_total = sum(item.shared_gold_edge_count for item in cases)
    shared_matched = sum(item.shared_matched_edge_count for item in cases)
    baseline_leakage = sum(
        len(baseline_edges[item.candidate_id] - set(item.gold_event_ids))
        for item in cases
        if item.gold_event_ids
    )
    gold_by_sge = {
        source_grounded_event_by_gold_id[item.event_id]: item
        for item in catalog.events
        if item.phase == phase
    }
    matrix_by_digest = {item.source_text_sha256: item for item in matrices}
    baseline_character = [0, 0, 0]
    competitive_character = [0, 0, 0]
    baseline_exact_events = 0
    competitive_exact_events = 0
    qualification_total = 0
    baseline_qualification = 0
    competitive_qualification = 0
    entity_total = 0
    baseline_entities = 0
    competitive_entities = 0
    for event_id, gold in gold_by_sge.items():
        matrix = matrix_by_digest[gold.source_text_sha256]
        required = _positions(
            gold.source_text,
            tuple((item.start, item.end) for item in gold.fragments),
        )
        baseline_selected = _selected_positions(matrix, event_id, baseline_edges, gold.source_text)
        competitive_selected = _selected_positions(
            matrix, event_id, competitive_edges, gold.source_text
        )
        _add_character_counts(baseline_character, required, baseline_selected)
        _add_character_counts(competitive_character, required, competitive_selected)
        baseline_exact_events += baseline_selected == required
        competitive_exact_events += competitive_selected == required
        qualifications = tuple(
            item
            for item in gold.fragments
            if any(
                requirement is not PropositionGoldFragmentRequirement.CORE_EVENT
                for requirement in item.requirements
            )
        )
        qualification_total += len(qualifications)
        baseline_qualification += sum(
            _positions(gold.source_text, ((item.start, item.end),)) <= baseline_selected
            for item in qualifications
        )
        competitive_qualification += sum(
            _positions(gold.source_text, ((item.start, item.end),)) <= competitive_selected
            for item in qualifications
        )
        gold_id = next(
            key for key, value in source_grounded_event_by_gold_id.items() if value == event_id
        )
        occurrences = entity_occurrences_by_gold_event.get(gold_id, ())
        entity_total += len(occurrences)
        baseline_entities += sum(
            _positions(gold.source_text, (occurrence,)) <= baseline_selected
            for occurrence in occurrences
        )
        competitive_entities += sum(
            _positions(gold.source_text, (occurrence,)) <= competitive_selected
            for occurrence in occurrences
        )
    baseline_precision, baseline_recall, baseline_f1 = _character_metrics(baseline_character)
    competitive_precision, competitive_recall, competitive_f1 = _character_metrics(
        competitive_character
    )
    none_cases = tuple(item for item in cases if not item.gold_event_ids)
    status_count = len(decision_statuses)
    unclear_count = sum(
        status is CompetitiveAttachmentDecisionStatus.UNCLEAR
        for status in decision_statuses.values()
    )
    invalid_output_count = sum(
        status is CompetitiveAttachmentDecisionStatus.INVALID_OUTPUT
        for status in decision_statuses.values()
    )
    model_failed_count = sum(
        status is CompetitiveAttachmentDecisionStatus.MODEL_FAILED
        for status in decision_statuses.values()
    )
    context_budget_blocked_count = sum(
        status is CompetitiveAttachmentDecisionStatus.CONTEXT_BUDGET_BLOCKED
        for status in decision_statuses.values()
    )
    unresolved_count = (
        unclear_count + invalid_output_count + model_failed_count + context_budget_blocked_count
    )
    return CompetitiveAttachmentMetrics(
        candidate_count=len(cases),
        baseline_exact_set_accuracy=_ratio(sum(item.baseline_exact for item in cases), len(cases)),
        competitive_exact_set_accuracy=_ratio(
            sum(item.competitive_exact for item in cases), len(cases)
        ),
        edge_precision=edge_precision,
        edge_recall=edge_recall,
        edge_f1=_ratio(2 * edge_precision * edge_recall, edge_precision + edge_recall),
        baseline_sibling_event_leakage_count=baseline_leakage,
        competitive_sibling_event_leakage_count=sum(
            item.sibling_event_leakage_count for item in cases
        ),
        shared_fragment_recall=_ratio(shared_matched, shared_total),
        none_case_count=len(none_cases),
        none_correct_count=sum(item.competitive_exact for item in none_cases),
        none_accuracy=_ratio(sum(item.competitive_exact for item in none_cases), len(none_cases)),
        unclear_count=unclear_count,
        unclear_rate=_ratio(unclear_count, status_count),
        invalid_output_count=invalid_output_count,
        invalid_output_rate=_ratio(invalid_output_count, status_count),
        model_failed_count=model_failed_count,
        model_failed_rate=_ratio(model_failed_count, status_count),
        context_budget_blocked_count=context_budget_blocked_count,
        context_budget_blocked_rate=_ratio(context_budget_blocked_count, status_count),
        unresolved_count=unresolved_count,
        unresolved_rate=_ratio(unresolved_count, status_count),
        silent_drop_count=0,
        baseline_entity_recall=_ratio(baseline_entities, entity_total),
        competitive_entity_recall=_ratio(competitive_entities, entity_total),
        baseline_qualification_recall=_ratio(baseline_qualification, qualification_total),
        competitive_qualification_recall=_ratio(competitive_qualification, qualification_total),
        baseline_character_precision=baseline_precision,
        baseline_character_recall=baseline_recall,
        baseline_character_f1=baseline_f1,
        competitive_character_precision=competitive_precision,
        competitive_character_recall=competitive_recall,
        competitive_character_f1=competitive_f1,
        baseline_exact_event_count=baseline_exact_events,
        competitive_exact_event_count=competitive_exact_events,
    )


def _validate_baseline_record(record: dict[str, Any]) -> EventEntityExperimentInput:
    if record.get("schema_version") != "source_grounded_proposition_execution_v1":
        raise ValueError("Competitive Attachment baseline execution schema is unknown.")
    prepared = EventEntityExperimentInput.model_validate_json(
        _canonical_json(record.get("prepared_input"))
    )
    candidates = tuple(
        PropositionFragmentCandidate.model_validate_json(_canonical_json(item))
        for item in cast(list[object], record.get("candidates"))
    )
    decisions = tuple(
        PropositionFragmentDecision.model_validate_json(_canonical_json(item))
        for item in cast(list[object], record.get("decisions"))
    )
    scope = SourceGroundedPropositionScope.model_validate_json(_canonical_json(record.get("scope")))
    traces = tuple(
        ExtractionStageTrace.model_validate_json(_canonical_json(item))
        for item in cast(list[object], record.get("traces"))
    )
    diagnostics = tuple(cast(list[str], record.get("diagnostics")))
    expected = source_grounded_proposition_result_sha256(
        candidates=candidates,
        decisions=decisions,
        scope=scope,
        traces=traces,
        diagnostics=diagnostics,
    )
    if record.get("result_sha256") != expected:
        raise ValueError("Competitive Attachment baseline result digest drifted.")
    if record.get("accepted_ledger_change_count") != 0:
        raise ValueError("Competitive Attachment baseline changed accepted state.")
    tuple(
        ModelRun.model_validate_json(_canonical_json(item))
        for item in cast(list[object], record.get("model_runs"))
    )
    return prepared


def _candidate_belongs_to_gold(start: int, end: int, gold: PropositionGoldEvent) -> bool:
    candidate = _positions(gold.source_text, ((start, end),))
    required = _positions(
        gold.source_text,
        tuple((item.start, item.end) for item in gold.fragments),
    )
    return bool(candidate) and candidate <= required


def _selected_positions(
    matrix: CompetitiveAttachmentMatrix,
    event_id: str,
    edges: dict[str, set[str]],
    source_text: str,
) -> set[int]:
    return _positions(
        source_text,
        tuple(
            (candidate.start, candidate.end)
            for candidate in matrix.candidates
            if event_id in edges[candidate.id]
        ),
    )


def _positions(source_text: str, ranges: tuple[tuple[int, int], ...]) -> set[int]:
    result: set[int] = set()
    for start, end in ranges:
        if start < 0 or end > len(source_text) or start >= end:
            raise ValueError("Competitive Attachment range leaves its SourceSegment.")
        result.update(index for index in range(start, end) if not source_text[index].isspace())
    return result


def _add_character_counts(target: list[int], required: set[int], selected: set[int]) -> None:
    target[0] += len(required & selected)
    target[1] += len(selected - required)
    target[2] += len(required - selected)


def _character_metrics(counts: list[int]) -> tuple[float, float, float]:
    precision = _ratio(counts[0], counts[0] + counts[1])
    recall = _ratio(counts[0], counts[0] + counts[2])
    return precision, recall, _ratio(2 * precision * recall, precision + recall)


def _accuracy_improved(metrics: CompetitiveAttachmentMetrics) -> bool:
    return metrics.competitive_exact_set_accuracy > metrics.baseline_exact_set_accuracy


def _leakage_reduced(metrics: CompetitiveAttachmentMetrics) -> bool:
    return (
        metrics.competitive_sibling_event_leakage_count
        < metrics.baseline_sibling_event_leakage_count
    )


def _protected_recall_preserved(metrics: CompetitiveAttachmentMetrics) -> bool:
    return (
        metrics.competitive_entity_recall >= metrics.baseline_entity_recall
        and metrics.competitive_qualification_recall >= metrics.baseline_qualification_recall
        and metrics.competitive_character_recall >= metrics.baseline_character_recall
    )


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, Any], value)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
