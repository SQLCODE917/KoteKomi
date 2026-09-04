import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from kotekomi_application.ingestion_observability import (
    IngestionObservabilityArchive,
    IngestionObservabilityLedger,
    InspectIngestionInput,
    ListIngestionHistoryInput,
    ingestion_history_to_json,
    inspect_ingestion,
    list_ingestion_history,
)
from kotekomi_domain import (
    AnalysisItemAttempt,
    AnalysisPlanArtifact,
    AnalysisRun,
    AnalysisRunState,
    IngestionChangeSet,
    IngestionChangeSetOrigin,
    IngestionRun,
    IngestionRunStatus,
    ModelRun,
    ModelRunStatus,
    PlannedAnalysisItem,
)
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class _Ledger:
    def __init__(self) -> None:
        self.runs: tuple[IngestionRun, ...] = ()
        self.analysis: AnalysisRun | None = None
        self.plan: AnalysisPlanArtifact | None = None
        self.change_set: IngestionChangeSet | None = None
        self.items: tuple[PlannedAnalysisItem, ...] = ()
        self.attempts: tuple[AnalysisItemAttempt, ...] = ()
        self.model_runs: tuple[ModelRun, ...] = ()

    def get_ingestion_run(self, record_id: str) -> IngestionRun | None:
        return next((item for item in self.runs if item.id == record_id), None)

    def list_ingestion_runs(self) -> tuple[IngestionRun, ...]:
        return self.runs

    def get_analysis_run(self, record_id: str) -> AnalysisRun | None:
        return self.analysis if self.analysis and self.analysis.id == record_id else None

    def get_analysis_plan_artifact(self, record_id: str) -> AnalysisPlanArtifact | None:
        return self.plan if self.plan and self.plan.id == record_id else None

    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None:
        return self.change_set if self.change_set and self.change_set.id == record_id else None

    def list_planned_items_for_analysis_run(
        self, analysis_run_id: str
    ) -> tuple[PlannedAnalysisItem, ...]:
        return tuple(item for item in self.items if item.analysis_run_id == analysis_run_id)

    def list_analysis_item_attempts_for_items(
        self, item_ids: tuple[str, ...]
    ) -> tuple[AnalysisItemAttempt, ...]:
        return tuple(item for item in self.attempts if item.planned_item_id in item_ids)

    def list_model_runs_by_ids(self, record_ids: tuple[str, ...]) -> tuple[ModelRun, ...]:
        return tuple(item for item in self.model_runs if item.id in record_ids)


class _Archive:
    def __init__(self, outputs: dict[str, bytes] | None = None) -> None:
        self.outputs = outputs or {}

    def read_model_run_output(self, model_run_id: str) -> bytes:
        return self.outputs[model_run_id]

    def ingestion_evidence_path(self, record_type: str, record_id: str) -> str:
        return f"{record_type}/{record_id}.json"


def test_ingestion_history_is_bounded_and_safe() -> None:
    ledger = _Ledger()
    ledger.runs = (_running("igr_new"), _running("igr_old"))

    result = list_ingestion_history(
        ListIngestionHistoryInput(limit=1),
        cast(IngestionObservabilityLedger, ledger),
    )

    assert tuple(item.ingestion_run_id for item in result.entries) == ("igr_new",)
    assert ingestion_history_to_json(result) == {
        "ingestions": [
            {
                "ingestion_run_id": "igr_new",
                "display_filename": "example.pdf",
                "requested_source_url": "https://example.test/source",
                "status": "running",
                "started_at": NOW.isoformat(),
                "completed_at": None,
                "failure_code": None,
            }
        ]
    }


def test_inspection_follows_explicit_analysis_and_model_links() -> None:
    raw_output = b'{"answer":"safe fixture"}'
    ledger = _complete_ledger(hashlib.sha256(raw_output).hexdigest())

    result = inspect_ingestion(
        InspectIngestionInput("igr_fixture"),
        cast(IngestionObservabilityLedger, ledger),
        cast(IngestionObservabilityArchive, _Archive({"mrn_fixture": raw_output})),
    )

    assert result.summary.status == "captured"
    assert result.summary.analysis_state == "complete"
    assert result.summary.elapsed_milliseconds == 2000
    assert result.summary.model_run_count == 1
    assert result.summary.trace_count == 0
    assert result.model_runs[0].model_run_id == "mrn_fixture"
    assert ("AnalysisItemAttempt", "aia_fixture") in {
        (item.record_type, item.record_id) for item in result.evidence
    }
    output = next(item for item in result.evidence if item.record_type == "ModelRunOutput")
    assert output.archive_path == "ModelRunOutput/mrn_fixture.json"
    assert output.sha256 == hashlib.sha256(raw_output).hexdigest()


def test_inspection_rejects_missing_linked_model_run() -> None:
    ledger = _complete_ledger("a" * 64)
    ledger.model_runs = ()

    with pytest.raises(ValueError, match="missing ModelRun"):
        inspect_ingestion(
            InspectIngestionInput("igr_fixture"),
            cast(IngestionObservabilityLedger, ledger),
            cast(IngestionObservabilityArchive, _Archive()),
        )


def test_inspection_of_running_ingestion_needs_no_analysis_evidence() -> None:
    ledger = _Ledger()
    ledger.runs = (_running("igr_running"),)

    result = inspect_ingestion(
        InspectIngestionInput("igr_running"),
        cast(IngestionObservabilityLedger, ledger),
        cast(IngestionObservabilityArchive, _Archive()),
    )

    assert result.summary.status == "running"
    assert result.summary.elapsed_milliseconds is None
    assert result.summary.analysis_state is None
    assert result.summary.evidence_count == 1


def _running(record_id: str) -> IngestionRun:
    return IngestionRun(
        id=record_id,
        requested_path="raw/example.pdf",
        display_filename="example.pdf",
        requested_source_url="https://example.test/source",
        status=IngestionRunStatus.RUNNING,
        started_at=NOW,
    )


def _complete_ledger(output_digest: str) -> _Ledger:
    ledger = _Ledger()
    plan_payload: dict[str, JsonValue] = {
        "representation_id": "rep_fixture",
        "policy_id": "fixture_policy_v1",
        "units": [],
    }
    plan_digest = hashlib.sha256(
        json.dumps(plan_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    plan_id = f"anp_{plan_digest[:24]}"
    ledger.analysis = AnalysisRun(
        id="arn_fixture",
        document_id="doc_fixture",
        representation_id="rep_fixture",
        frozen_analysis_plan_id=plan_id,
        coverage_policy_id="fixture_policy_v1",
        state=AnalysisRunState.COMPLETE,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=2),
    )
    ledger.plan = AnalysisPlanArtifact(
        id=plan_id,
        representation_id="rep_fixture",
        plan_digest=plan_digest,
        payload=plan_payload,
        created_at=NOW,
    )
    ledger.items = (
        PlannedAnalysisItem(
            id="pai_fixture",
            analysis_run_id="arn_fixture",
            analysis_unit_id="anu_fixture",
            task_type="fixture_task",
            required=True,
            input_fingerprint="c" * 64,
        ),
    )
    ledger.attempts = (
        AnalysisItemAttempt(
            id="aia_fixture",
            planned_item_id="pai_fixture",
            execution_role="primary",
            model_run_id="mrn_fixture",
        ),
    )
    ledger.model_runs = (_model_run(output_digest),)
    change_set_payload: dict[str, JsonValue] = {
        "ingestion_run_id": "igr_fixture",
        "analysis_run_id": "arn_fixture",
        "representation_id": "rep_fixture",
        "coverage_report_digest": "d" * 64,
        "proposed_change_ids": [],
        "analysis_origin": "executed",
    }
    change_set_digest = hashlib.sha256(
        json.dumps(change_set_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    change_set_id = f"ics_{change_set_digest[:24]}"
    ledger.change_set = IngestionChangeSet(
        id=change_set_id,
        ingestion_run_id="igr_fixture",
        analysis_run_id="arn_fixture",
        representation_id="rep_fixture",
        coverage_report_digest="d" * 64,
        analysis_origin=IngestionChangeSetOrigin.EXECUTED,
        closed_at=NOW + timedelta(seconds=2),
        change_set_digest=change_set_digest,
    )
    ledger.runs = (
        _running("igr_fixture").model_copy(
            update={
                "status": IngestionRunStatus.CAPTURED,
                "completed_at": NOW + timedelta(seconds=2),
                "normalized_source_url": "https://example.test/source",
                "source_id": "src_fixture",
                "document_id": "doc_fixture",
                "representation_id": "rep_fixture",
                "provenance_activity_id": "prv_fixture",
                "analysis_run_id": "arn_fixture",
                "ingestion_change_set_id": change_set_id,
            }
        ),
    )
    return ledger


def _model_run(output_digest: str) -> ModelRun:
    return ModelRun(
        id="mrn_fixture",
        extraction_task_id="ext_fixture",
        task_fingerprint="c" * 64,
        model_identity={"name": "fixture"},
        runtime_identity="fixture",
        tokenizer_id="fixture_v1",
        prompt_digest="f" * 64,
        schema_digest="1" * 64,
        execution_spec_digest="2" * 64,
        generation_parameters={"max_output_tokens": 64},
        raw_output_artifact_id="mrn_fixture",
        output_digest=output_digest,
        status=ModelRunStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        execution_diagnostics={
            "elapsed_milliseconds": 1000,
            "deadline_milliseconds": 5000,
            "first_response_event_milliseconds": 100,
        },
        execution_receipt={
            "model_identity_digest": "3" * 64,
            "generation_parameters_digest": "4" * 64,
            "rendered_input_digest": "5" * 64,
            "input_token_count": 10,
            "output_token_count": 5,
        },
    )
