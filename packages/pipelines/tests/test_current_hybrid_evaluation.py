from __future__ import annotations

import pytest
from kotekomi_pipelines.current_hybrid_evaluation import CurrentHybridEvaluationReport
from pydantic import ValidationError


def test_current_report_rejects_a_retired_evaluation_key() -> None:
    payload = _payload()
    payload["task_allocation_evaluations"] = []

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CurrentHybridEvaluationReport.model_validate(payload)


def test_current_report_passes_exactly_when_findings_are_empty() -> None:
    report = CurrentHybridEvaluationReport.model_validate(_payload())

    assert report.summary.passed is True

    payload = _payload()
    payload["findings"] = [{"code": "front_half_gold_mismatch"}]
    with pytest.raises(ValidationError, match="pass state must equal an empty findings list"):
        CurrentHybridEvaluationReport.model_validate(payload)


def _payload() -> dict[str, object]:
    summary_fields = {
        "required_paragraphs": 0,
        "complete_paragraphs": 0,
        "gap_paragraphs": 0,
        "paragraph_proposed_changes": 0,
        "reconciled_proposed_changes": 0,
        "source_grounded_events_expected": 0,
        "source_grounded_events_observed": 0,
        "source_grounded_events_exact": 0,
        "source_grounded_events_missing": 0,
        "source_grounded_events_extra": 0,
        "source_grounded_events_incorrect": 0,
        "front_half_items_expected": 0,
        "front_half_items_exact": 0,
        "standing_facts_expected": 0,
        "standing_facts_exact": 0,
        "standing_facts_missing": 0,
        "standing_facts_incorrect": 0,
        "standing_facts_not_proposed": 0,
        "standing_facts_lineage_incomplete": 0,
        "standing_facts_not_visible": 0,
        "replay_model_calls": 0,
    }
    return {
        "schema_version": "hp8_document_orchestration_evaluation_v3",
        "source_path": "raw/source.pdf",
        "source_sha256": "a" * 64,
        "policy_manifest": {},
        "coverage_report": {},
        "paragraphs": [],
        "source_grounded_event_evaluation": {
            "schema_version": "hsq_source_grounded_event_report_v1"
        },
        "front_half_evaluation": {"schema_version": "hsq_front_half_evaluation_v1"},
        "standing_fact_evaluation": {"schema_version": "hsq_standing_fact_evaluation_v1"},
        "candidate_wiki": {},
        "first_public_output": {},
        "replay_public_output": {},
        "first_ledger_counts": {},
        "model_performance": {},
        "model_executions": [],
        "replay_ledger_counts": {},
        "ingestion_change_set_origins": [],
        "findings": [],
        "summary": {"passed": True, **summary_fields},
    }
