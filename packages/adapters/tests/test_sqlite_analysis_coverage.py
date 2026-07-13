import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from kotekomi_adapters import (
    LocalArchiveStore,
    SQLiteLedgerInitializer,
    SQLiteLedgerRepository,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
    AnalysisCoverageState,
    AnalysisRunInput,
    AnalysisRunItemInput,
    AnalysisUnitPlanningInput,
    BoundedExtractionInput,
    BoundedExtractionOutcome,
    BuildIdentity,
    ContextManifest,
    ContextManifestInput,
    ContextModelProfile,
    CoverageIntegrityFailureReason,
    CoveragePolicyDecision,
    CoverageReport,
    CoverageTerminalStatus,
    ExecutionSetting,
    FrozenAnalysisPlan,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelTaskRequest,
    ModelTaskResponse,
    StagedClaimTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    build_context_manifest,
    build_coverage_report,
    deterministic_representation_id,
    freeze_analysis_plan,
    generation_parameters_digest,
    model_identity_snapshot_digest,
    plan_analysis_units,
    processing_task_fingerprint,
    record_analysis_item_attempt,
    run_bounded_extraction,
    staged_claim_output_schema_bytes,
    start_analysis_run,
)
from kotekomi_domain import (
    AnalysisRun,
    AnalysisRunState,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ModelRunStatus,
    ParseQualityReport,
    PlannedAnalysisItem,
    RawBlob,
    RepresentationAnalyzability,
    Source,
    SourceRegion,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)
PROMPT = b"Extract one task-local source claim."
MODEL_IDENTITY = ModelIdentitySnapshot(
    name="sqlite-coverage-fixture",
    weights_digest="d" * 64,
    runtime="fixture-runtime",
    tokenizer_id="sqlite_coverage_whitespace_v1",
    determinism_settings=(ExecutionSetting("temperature", 0),),
)


class ExactWhitespaceTokenizer:
    tokenizer_id = "sqlite_coverage_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


class FixtureModelRuntime:
    def __init__(self, raw_output: bytes) -> None:
        self.raw_output = raw_output

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return MODEL_IDENTITY

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        return ModelTaskResponse(
            raw_output=self.raw_output,
            execution_receipt=ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(
                    task.execution_spec.model_identity
                ),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=task.rendered_input_digest,
                input_token_count=len(task.rendered_input.decode("utf-8").split()),
                output_token_count=None,
            ),
        )


@dataclass(frozen=True)
class DocumentFixture:
    source: Source
    document: Document
    bundle: DocumentRepresentationBundle
    paragraph_text: str
    paragraph_node_id: str


@dataclass(frozen=True)
class AnalyzedRunFixture:
    document: DocumentFixture
    frozen_plan: FrozenAnalysisPlan
    manifest: ContextManifest
    extraction: BoundedExtractionOutcome
    analysis_run: AnalysisRun
    report: CoverageReport


def _initialize(tmp_path: Path) -> tuple[Path, LocalArchiveStore]:
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    return ledger_path, archive


def _install_document(repository: SQLiteLedgerRepository, key: str) -> DocumentFixture:
    paragraph_text = f"Document {key} reports a community health priority."
    payload = paragraph_text.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    source = Source(
        id=f"src_coverage_{key}",
        source_type=SourceType.MANUAL_FILE,
        identity_policy_id="sqlite_coverage_fixture_v1",
        canonical_identity_key=f"coverage:{key}",
        created_at=NOW,
        updated_at=NOW,
    )
    document = Document(
        id=f"doc_coverage_{key}",
        source_id=source.id,
        content_sha256=digest,
        created_at=NOW,
        updated_at=NOW,
    )
    blob = RawBlob(
        id=f"blb_coverage_{key}",
        hash_algorithm="sha256",
        digest=digest,
        byte_length=len(payload),
        media_type="text/plain",
        storage_locator=f"fixture/{key}.txt",
        created_at=NOW,
    )
    repository.save_source(source)
    repository.save_document(document)
    repository.save_raw_blob(blob)
    task = processing_task_fingerprint(
        task_kind="sqlite_coverage_representation",
        document_id=document.id,
        blob_id=blob.id,
        input_digest=digest,
        processor_name="sqlite-coverage-fixture",
        processor_version="1",
        processor_config_digest="a" * 64,
        build_identity=BuildIdentity("sqlite-coverage", "sqlite-coverage", "b" * 64, "1"),
        policy_id="sqlite_coverage_representation_v1",
        output_contract_version="1",
    )
    repository.ensure_processing_task_fingerprint(task)
    representation_id = deterministic_representation_id(task.id)
    text_view = TextView(
        id=f"tvw_coverage_{key}",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=digest,
        text=paragraph_text,
        normalization_policy="utf8_identity_v1",
    )
    region = SourceRegion(
        id=f"srg_coverage_{key}",
        representation_id=representation_id,
        coordinate_system="fixture_points_v1",
        page_number=1,
        page_width=612,
        page_height=792,
        left=36,
        top=36,
        right=576,
        bottom=72,
    )
    root = DocumentNode(
        id=f"nod_coverage_{key}_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(paragraph_text),
        source_region_ids=(region.id,),
    )
    paragraph = DocumentNode(
        id=f"nod_coverage_{key}_paragraph",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(paragraph_text),
        source_region_ids=(region.id,),
    )
    quality = ParseQualityReport(
        id=f"pqr_coverage_{key}",
        representation_id=representation_id,
        metric_values={"text_char_count": len(paragraph_text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document.id,
        parser_name="sqlite-coverage-fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id=task.id,
        input_blob_digest=digest,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root, paragraph),
                edges=(),
                source_regions=(region,),
                quality_report=quality,
            )
        }
    )
    bundle = DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, paragraph),
        source_regions=(region,),
        quality_report=quality,
    )
    repository.commit_document_representation_bundle(bundle)
    return DocumentFixture(source, document, bundle, paragraph_text, paragraph.id)


def _execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=MODEL_IDENTITY,
        generation_parameters=(ExecutionSetting("temperature", 0),),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=manifest.schema_id,
        schema_digest=manifest.schema_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="staged_claim_output_v1",
    )


def _candidate_output(document: DocumentFixture) -> bytes:
    return json.dumps(
        {
            "kind": "candidates",
            "schema_id": "staged_claim_output_v1",
            "organizations": [{"local_id": "subject", "name": "Fixture Health Department"}],
            "evidence": [
                {
                    "local_id": "support",
                    "node_id": document.paragraph_node_id,
                    "exact_quote": document.paragraph_text,
                    "node_local_start": 0,
                    "node_local_end": len(document.paragraph_text),
                }
            ],
            "assertions": [
                {
                    "local_id": "claim",
                    "subject_organization_local_id": "subject",
                    "evidence_local_id": "support",
                    "predicate": "reported_health_priority",
                    "object_value": document.paragraph_text,
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _build_manifest(
    repository: SQLiteLedgerRepository,
    document: DocumentFixture,
    *,
    planner_policy_id: str,
    prompt: bytes = PROMPT,
) -> tuple[FrozenAnalysisPlan, ContextManifest]:
    plan = plan_analysis_units(
        AnalysisUnitPlanningInput(
            representation_id=document.bundle.representation.id,
            policy_id=planner_policy_id,
            task_type="claim_extraction",
        ),
        repository,
    )
    frozen = freeze_analysis_plan(plan, repository)
    manifest = build_context_manifest(
        ContextManifestInput(
            analysis_unit=plan.units[0],
            model_profile=ContextModelProfile("sqlite-coverage-model", 512, 32, 8),
            prompt_id=f"{planner_policy_id}_prompt_v1",
            prompt_bytes=prompt,
            schema_id="staged_claim_output_v1",
            schema_bytes=staged_claim_output_schema_bytes(),
            renderer_version="sqlite_coverage_renderer_v1",
        ),
        repository,
        ExactWhitespaceTokenizer(),
    ).manifest
    return frozen, manifest


def _run_extraction(
    repository: SQLiteLedgerRepository,
    archive: LocalArchiveStore,
    document: DocumentFixture,
    manifest: ContextManifest,
    raw_output: bytes,
    *,
    started_at: datetime = NOW,
) -> BoundedExtractionOutcome:
    return run_bounded_extraction(
        BoundedExtractionInput(
            source_id=document.source.id,
            document_id=document.document.id,
            representation_id=document.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_execution_spec(manifest),
            validator_version="sqlite-coverage-validator-v1",
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=1),
        ),
        repository,
        archive,
        FixtureModelRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        ExactWhitespaceTokenizer(),
        StagedClaimTaskSchemaRegistry(),
    )


def _start_run(
    repository: SQLiteLedgerRepository,
    document: DocumentFixture,
    frozen: FrozenAnalysisPlan,
    manifest: ContextManifest | None,
    input_fingerprint: str,
) -> AnalysisRun:
    unit = frozen.units[0]
    return start_analysis_run(
        AnalysisRunInput(
            document_id=document.document.id,
            frozen_plan_id=frozen.id,
            coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
            started_at=NOW,
            items=(
                AnalysisRunItemInput(
                    analysis_unit_id=unit.id,
                    task_type=unit.task_type,
                    input_fingerprint=input_fingerprint,
                    expected_manifest_id=manifest.id if manifest is not None else None,
                ),
            ),
        ),
        repository,
    )


def _create_complete_run(
    repository: SQLiteLedgerRepository,
    archive: LocalArchiveStore,
    document: DocumentFixture,
    *,
    planner_policy_id: str,
) -> AnalyzedRunFixture:
    frozen, manifest = _build_manifest(
        repository,
        document,
        planner_policy_id=planner_policy_id,
    )
    extraction = _run_extraction(
        repository,
        archive,
        document,
        manifest,
        _candidate_output(document),
    )
    analysis_run = _start_run(
        repository,
        document,
        frozen,
        manifest,
        extraction.extraction_task.task_fingerprint,
    )
    record_analysis_item_attempt(
        analysis_run_id=analysis_run.id,
        analysis_unit_id=frozen.units[0].id,
        model_run_id=extraction.model_run.id,
        ledger_repository=repository,
    )
    report = build_coverage_report(analysis_run.id, repository)
    assert report.state is AnalysisCoverageState.COMPLETE
    return AnalyzedRunFixture(document, frozen, manifest, extraction, analysis_run, report)


def _assert_restarted_report(
    ledger_path: Path,
    analysis_run_id: str,
    expected: CoverageReport,
) -> None:
    with sqlite_ledger_transaction(ledger_path) as repository:
        restarted = build_coverage_report(analysis_run_id, repository)
    assert restarted == expected
    assert restarted.report_digest == expected.report_digest
    assert tuple(record.policy_decision for record in restarted.coverage_records) == tuple(
        record.policy_decision for record in expected.coverage_records
    )


def test_sqlite_coverage_isolates_unrelated_document_model_runs_after_restart(
    tmp_path: Path,
) -> None:
    ledger_path, archive = _initialize(tmp_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        document_a = _install_document(repository, "a")
        run_a = _create_complete_run(
            repository,
            archive,
            document_a,
            planner_policy_id="document_a_plan_v1",
        )
        report_before_b = run_a.report
        document_b = _install_document(repository, "b")
        _, manifest_b = _build_manifest(
            repository,
            document_b,
            planner_policy_id="document_b_plan_v1",
        )
        model_run_b = _run_extraction(
            repository,
            archive,
            document_b,
            manifest_b,
            _candidate_output(document_b),
        ).model_run
        report_after_b = build_coverage_report(run_a.analysis_run.id, repository)

    assert report_after_b == report_before_b
    assert model_run_b.id not in report_after_b.orphan_model_run_ids
    _assert_restarted_report(ledger_path, run_a.analysis_run.id, report_before_b)


def test_sqlite_coverage_isolates_two_plans_for_one_representation_after_restart(
    tmp_path: Path,
) -> None:
    ledger_path, archive = _initialize(tmp_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = _install_document(repository, "shared")
        run_a = _create_complete_run(
            repository,
            archive,
            document,
            planner_policy_id="shared_plan_a_v1",
        )
        run_b = _create_complete_run(
            repository,
            archive,
            document,
            planner_policy_id="shared_plan_b_v1",
        )

    assert run_a.frozen_plan.id != run_b.frozen_plan.id
    assert run_a.manifest.id != run_b.manifest.id
    assert tuple(record.planned_item_id for record in run_a.report.coverage_records) != tuple(
        record.planned_item_id for record in run_b.report.coverage_records
    )
    assert {record.context_manifest_id for record in run_a.report.coverage_records} == {
        run_a.manifest.id
    }
    assert {record.context_manifest_id for record in run_b.report.coverage_records} == {
        run_b.manifest.id
    }
    assert all(
        record.terminal_status is CoverageTerminalStatus.PROCESSED_WITH_PROPOSALS
        for record in (*run_a.report.coverage_records, *run_b.report.coverage_records)
    )
    _assert_restarted_report(ledger_path, run_a.analysis_run.id, run_a.report)
    _assert_restarted_report(ledger_path, run_b.analysis_run.id, run_b.report)


@pytest.mark.parametrize(
    ("retry_status", "expected_terminal_status"),
    (
        (ModelRunStatus.SUCCEEDED, CoverageTerminalStatus.PROCESSED_NO_PROPOSALS),
        (ModelRunStatus.ABSTAINED, CoverageTerminalStatus.ABSTAINED),
        (ModelRunStatus.INVALID_OUTPUT, CoverageTerminalStatus.MODEL_FAILED),
        (ModelRunStatus.PUBLISH_FAILED, CoverageTerminalStatus.MODEL_FAILED),
    ),
)
def test_sqlite_selected_run_never_inherits_historical_proposals_after_restart(
    tmp_path: Path,
    retry_status: ModelRunStatus,
    expected_terminal_status: CoverageTerminalStatus,
) -> None:
    ledger_path, archive = _initialize(tmp_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = _install_document(repository, retry_status.value)
        fixture = _create_complete_run(
            repository,
            archive,
            document,
            planner_policy_id=f"selected_{retry_status.value}_plan_v1",
        )
        historical_proposal_ids = tuple(
            proposal.id
            for proposal in repository.list_proposed_changes_for_model_run(
                fixture.extraction.model_run.id
            )
        )
        assert historical_proposal_ids

    retry_started_at = NOW + timedelta(minutes=1)
    if retry_status is ModelRunStatus.PUBLISH_FAILED:

        class FaultingRepository(SQLiteLedgerRepository):
            def _successful_model_run_publication_checkpoint(self, name: str) -> None:
                if name == "BEFORE_SUCCESSFUL_MODEL_RUN":
                    raise OSError("injected publication failure")

        with sqlite3.connect(ledger_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            faulting_repository = FaultingRepository(connection)
            retry = _run_extraction(
                faulting_repository,
                archive,
                document,
                fixture.manifest,
                _candidate_output(document),
                started_at=retry_started_at,
            )
            connection.commit()
    else:
        raw_output = (
            _candidate_output(document)
            if retry_status is ModelRunStatus.SUCCEEDED
            else b'{"kind":"abstain","schema_id":"staged_claim_output_v1",'
            b'"reason":"insufficient task-local evidence"}'
            if retry_status is ModelRunStatus.ABSTAINED
            else b"{}"
        )
        with sqlite_ledger_transaction(ledger_path) as repository:
            retry = _run_extraction(
                repository,
                archive,
                document,
                fixture.manifest,
                raw_output,
                started_at=retry_started_at,
            )

    assert retry.model_run.status is retry_status
    with sqlite_ledger_transaction(ledger_path) as repository:
        record_analysis_item_attempt(
            analysis_run_id=fixture.analysis_run.id,
            analysis_unit_id=fixture.frozen_plan.units[0].id,
            model_run_id=retry.model_run.id,
            ledger_repository=repository,
        )
        report = build_coverage_report(fixture.analysis_run.id, repository)
        historical_run = repository.get_model_run(fixture.extraction.model_run.id)
        historical_proposals = tuple(
            proposal.id
            for proposal in repository.list_proposed_changes_for_model_run(
                fixture.extraction.model_run.id
            )
        )

    record = report.coverage_records[0]
    assert record.terminal_status is expected_terminal_status
    assert record.selected_model_run_id == retry.model_run.id
    assert record.selected_proposal_ids == ()
    assert record.all_model_run_ids == tuple(
        sorted((fixture.extraction.model_run.id, retry.model_run.id))
    )
    assert record.policy_decision is (
        CoveragePolicyDecision.SELECTED_LATEST_COMPLETED_VALID_ATTEMPT
    )
    assert historical_run == fixture.extraction.model_run
    assert historical_proposals == historical_proposal_ids
    _assert_restarted_report(ledger_path, fixture.analysis_run.id, report)
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.get_model_run(fixture.extraction.model_run.id) == historical_run
        assert (
            tuple(
                proposal.id
                for proposal in repository.list_proposed_changes_for_model_run(
                    fixture.extraction.model_run.id
                )
            )
            == historical_proposal_ids
        )


def test_sqlite_zero_expected_manifests_remains_incomplete_after_restart(
    tmp_path: Path,
) -> None:
    ledger_path, _ = _initialize(tmp_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = _install_document(repository, "missing")
        frozen, _ = _build_manifest(
            repository,
            document,
            planner_policy_id="missing_manifest_plan_v1",
        )
        run = _start_run(
            repository,
            document,
            frozen,
            None,
            hashlib.sha256(b"pending-manifest").hexdigest(),
        )
        report = build_coverage_report(run.id, repository)

    assert report.state is AnalysisCoverageState.INCOMPLETE
    assert report.integrity_failure_reasons == ()
    assert report.coverage_records[0].blocking_reason == "missing_manifest"
    _assert_restarted_report(ledger_path, run.id, report)


def test_sqlite_multiple_manifests_for_one_unit_fails_after_restart(tmp_path: Path) -> None:
    ledger_path, _ = _initialize(tmp_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = _install_document(repository, "multiple")
        frozen, manifest_a = _build_manifest(
            repository,
            document,
            planner_policy_id="multiple_manifest_plan_v1",
            prompt=b"Extract using manifest A.",
        )
        manifest_b = build_context_manifest(
            ContextManifestInput(
                analysis_unit=frozen.units[0],
                model_profile=ContextModelProfile("sqlite-coverage-model", 512, 32, 8),
                prompt_id="multiple_manifest_prompt_b_v1",
                prompt_bytes=b"Extract using manifest B.",
                schema_id="staged_claim_output_v1",
                schema_bytes=staged_claim_output_schema_bytes(),
                renderer_version="sqlite_coverage_renderer_v1",
            ),
            repository,
            ExactWhitespaceTokenizer(),
        ).manifest
        run = AnalysisRun(
            id="arn_sqlite_multiple_manifests",
            document_id=document.document.id,
            representation_id=document.bundle.representation.id,
            frozen_analysis_plan_id=frozen.id,
            coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
            state=AnalysisRunState.RUNNING,
            started_at=NOW,
        )
        repository.commit_analysis_run_scope(
            analysis_run=run,
            planned_items=(
                PlannedAnalysisItem(
                    id="pai_sqlite_manifest_a",
                    analysis_run_id=run.id,
                    analysis_unit_id=frozen.units[0].id,
                    task_type=frozen.units[0].task_type,
                    required=True,
                    expected_manifest_id=manifest_a.id,
                    input_fingerprint=hashlib.sha256(b"manifest-a").hexdigest(),
                ),
                PlannedAnalysisItem(
                    id="pai_sqlite_manifest_b",
                    analysis_run_id=run.id,
                    analysis_unit_id=frozen.units[0].id,
                    task_type=frozen.units[0].task_type,
                    required=True,
                    expected_manifest_id=manifest_b.id,
                    input_fingerprint=hashlib.sha256(b"manifest-b").hexdigest(),
                ),
            ),
        )
        report = build_coverage_report(run.id, repository)

    assert report.state is AnalysisCoverageState.FAILED
    assert report.integrity_failure_reasons == (CoverageIntegrityFailureReason.MULTIPLE_MANIFESTS,)
    assert tuple(record.blocking_reason for record in report.coverage_records) == (
        "multiple_manifests",
        "multiple_manifests",
    )
    _assert_restarted_report(ledger_path, run.id, report)
