"""Public-operation-only structured-news path through coverage and restart."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters import (
    LocalArchiveStore,
    NewsMLG2Adapter,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
    AnalysisCoverageState,
    AnalysisRunInput,
    AnalysisRunItemInput,
    BoundedExtractionInput,
    BoundedExtractionOutcome,
    BuildIdentity,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ExecutionSetting,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelTaskRequest,
    ModelTaskResponse,
    NewsAnalysisPlanningInput,
    NewsDeliveryEnvelope,
    NewsIngestInput,
    NewsIngestStatus,
    SemanticDraftTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    Uuid4ProcessingAttemptIdFactory,
    build_context_manifest,
    build_coverage_report,
    freeze_analysis_plan,
    generation_parameters_digest,
    ingest_structured_news,
    model_identity_snapshot_digest,
    plan_news_analysis_units,
    record_analysis_item_attempt,
    run_bounded_extraction,
    semantic_draft_text_schema_bytes,
    start_analysis_run,
    verify_evidence_target,
)
from kotekomi_domain import ModelRunStatus

FIXTURES = Path(__file__).parent / "fixtures" / "news"
NOW = datetime(2026, 7, 14, 14, tzinfo=UTC)
PROMPT = b"Return one bounded, source-grounded claim or explicitly abstain."
BUILD = BuildIdentity("news-public-path", "news-public-path", "b" * 64, "1")


class _Clock:
    def now(self) -> datetime:
        return NOW


class _ExactTokenizer:
    tokenizer_id = "news_public_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


def _model_identity() -> ModelIdentitySnapshot:
    return ModelIdentitySnapshot(
        "news_public_fixture_model",
        "c" * 64,
        "fixture-runtime-v1",
        _ExactTokenizer.tokenizer_id,
        (ExecutionSetting("seed", 11), ExecutionSetting("temperature", 0)),
    )


def _execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=_model_identity(),
        generation_parameters=(
            ExecutionSetting("seed", 11),
            ExecutionSetting("temperature", 0),
        ),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=manifest.schema_id,
        schema_digest=manifest.schema_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="semantic_draft_text_v1",
    )


class _FixtureRuntime:
    def __init__(self, raw_output: bytes) -> None:
        self._raw_output = raw_output

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return _model_identity()

    @property
    def task_deadline_seconds(self) -> float:
        return 300.0

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        return ModelTaskResponse(
            self._raw_output,
            ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(
                    task.execution_spec.model_identity
                ),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=task.rendered_input_digest,
                input_token_count=len(task.rendered_input.decode().split()),
                output_token_count=len(self._raw_output.decode().split()),
            ),
        )


def _delivery(payload: bytes) -> NewsDeliveryEnvelope:
    envelope_bytes = (FIXTURES / "envelope.json").read_bytes()
    return NewsDeliveryEnvelope(
        payload=payload,
        media_type="application/newsml+xml",
        envelope_bytes=envelope_bytes,
        envelope_media_type="application/json",
        retrieval_method="recorded_fixture",
        requested_uri="fixture://news/public-path",
        canonical_uri=None,
        response_status=200,
        safe_metadata=json.loads(envelope_bytes),
    )


def test_newsml_public_path_reaches_proposal_coverage_and_restart(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    payload = (FIXTURES / "newsml" / "original.xml").read_bytes()
    with sqlite_ledger_transaction(ledger_path) as repository:
        ingest = ingest_structured_news(
            NewsIngestInput(_delivery(payload), NOW, NOW, "public-path", BUILD),
            repository,
            archive,
            NewsMLG2Adapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        assert ingest.status is NewsIngestStatus.CREATED
        planning = plan_news_analysis_units(
            NewsAnalysisPlanningInput(
                representation_id=ingest.representation_id or "",
                policy_id="news_public_plan_v1",
                task_type="claim_extraction",
                as_of=NOW,
                max_focus_nodes_per_unit=1,
            ),
            ledger=repository,
        )
        assert planning.authorization.allowed
        bundle = repository.get_document_representation_bundle(ingest.representation_id or "")
        assert bundle is not None
        plan = planning.plan
        assert plan is not None
        focus_unit = next(
            unit
            for unit in plan.units
            if any(
                node.id in unit.focus_node_ids
                and "Project Atlas entered public evaluation"
                in next(
                    text_view.text[node.start_char : node.end_char]
                    for text_view in bundle.text_views
                    if text_view.id == node.text_view_id
                )
                for node in bundle.nodes
            )
        )
        frozen = freeze_analysis_plan(plan, repository)
        claim_output = (
            b"outcome: claim\n"
            b"subject: Project Atlas\n"
            b"relation: reported event\n"
            b"object_kind: literal\n"
            b"object: public evaluation\n"
        )
        manifests: dict[str, ContextManifest] = {}
        extractions: dict[str, BoundedExtractionOutcome] = {}
        for unit in plan.units:
            manifest_for_unit = build_context_manifest(
                ContextManifestInput(
                    analysis_unit=unit,
                    model_profile=ContextModelProfile("news_public_fixture_model", 4096, 128, 32),
                    prompt_id="news_public_claim_v1",
                    prompt_bytes=PROMPT,
                    schema_id="semantic_draft_text_v1",
                    schema_bytes=semantic_draft_text_schema_bytes(),
                    renderer_version="news_public_renderer_v1",
                    evidence_selection_policy_id="direct_prose_evidence_v1",
                ),
                repository,
                _ExactTokenizer(),
            ).manifest
            assert manifest_for_unit.status is ContextManifestStatus.READY
            raw_output = (
                claim_output
                if unit.id == focus_unit.id
                else b"outcome: abstain\nreason: fixture does not propose a claim\n"
            )
            manifests[unit.id] = manifest_for_unit
            extractions[unit.id] = run_bounded_extraction(
                BoundedExtractionInput(
                    source_id=ingest.source_id or "",
                    document_id=ingest.document_id or "",
                    representation_id=bundle.representation.id,
                    context_manifest_id=manifest_for_unit.id,
                    prompt_bytes=PROMPT,
                    execution_spec=_execution_spec(manifest_for_unit),
                    validator_version="news-public-validator-v1",
                ),
                repository,
                archive,
                _FixtureRuntime(raw_output),
                Uuid4ModelRunIdFactory(),
                _ExactTokenizer(),
                SemanticDraftTaskSchemaRegistry(),
            )
        manifest = manifests[focus_unit.id]
        extraction = extractions[focus_unit.id]
        assert extraction.model_run.status is ModelRunStatus.SUCCEEDED
        assert extraction.proposed_change_batch is not None
        proposal_ids = extraction.proposed_change_batch.proposed_change_ids_by_local_id
        evidence_id = extraction.proposed_change_batch.evidence_target_ids_by_local_id[
            "evidence_01"
        ]
        validation_id = (
            extraction.proposed_change_batch.validation_attempt_ids_by_evidence_local_id[
                "evidence_01"
            ]
        )
        assert proposal_ids["assertion_01"]
        evidence = repository.get_evidence_target(evidence_id)
        validation = repository.get_evidence_validation_attempt(validation_id)
        assert evidence is not None and validation is not None
        assert verify_evidence_target(evidence, validation, repository).valid
        analysis_run = start_analysis_run(
            AnalysisRunInput(
                document_id=ingest.document_id or "",
                frozen_plan_id=frozen.id,
                coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
                started_at=NOW,
                items=tuple(
                    AnalysisRunItemInput(
                        analysis_unit_id=unit.id,
                        task_type=unit.task_type,
                        input_fingerprint=extractions[unit.id].extraction_task.task_fingerprint,
                        expected_manifest_id=manifests[unit.id].id,
                    )
                    for unit in plan.units
                ),
            ),
            repository,
        )
        for unit in plan.units:
            record_analysis_item_attempt(
                analysis_run_id=analysis_run.id,
                analysis_unit_id=unit.id,
                model_run_id=extractions[unit.id].model_run.id,
                ledger_repository=repository,
            )
        report = build_coverage_report(analysis_run.id, repository)
        assert report.state is AnalysisCoverageState.COMPLETE
        run_proposal_ids = tuple(
            sorted(
                proposal.id
                for proposal in repository.list_proposed_changes_for_model_run(
                    extraction.model_run.id
                )
            )
        )
        focus_coverage = next(
            coverage
            for coverage in report.coverage_records
            if coverage.analysis_unit_id == focus_unit.id
        )
        assert focus_coverage.selected_proposal_ids == run_proposal_ids
        assert proposal_ids["assertion_01"] in run_proposal_ids

    with sqlite_ledger_transaction(ledger_path) as repository:
        restarted_bundle = repository.get_document_representation_bundle(
            ingest.representation_id or ""
        )
        restarted_manifest = repository.get_context_manifest_artifact(manifest.id)
        restarted_report = build_coverage_report(analysis_run.id, repository)
        restarted_proposal = repository.get_proposed_change(proposal_ids["assertion_01"])
    assert restarted_bundle == bundle
    assert restarted_manifest is not None
    assert restarted_report == report
    assert restarted_proposal is not None
