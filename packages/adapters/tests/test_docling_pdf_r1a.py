import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kotekomi_adapters import (
    LocalArchiveStore,
    SQLiteLedgerInitializer,
    SQLiteLedgerRepository,
    sqlite_ledger_transaction,
)
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import (
    AnalysisUnitPlanningInput,
    BoundedExtractionInput,
    BoundedExtractionOutcome,
    BuildIdentity,
    CaptureRequest,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ExecutionSetting,
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedCandidateContext,
    GroundedCandidateContextInput,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelTaskRequest,
    ModelTaskResponse,
    PdfIngestInput,
    PdfPagePreflight,
    PdfParseInput,
    PdfParseResult,
    PdfProcessorIdentity,
    ReviewProposedChangeInput,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    StagedClaimTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    Uuid4ProcessingAttemptIdFactory,
    approve_proposed_change,
    build_context_manifest,
    build_grounded_candidate_context,
    capture_identity,
    capture_source,
    generation_parameters_digest,
    ingest_pdf,
    load_context_manifest,
    load_split_analysis_units,
    model_identity_snapshot_digest,
    plan_analysis_units,
    render_context,
    run_bounded_extraction,
    staged_claim_output_schema_bytes,
    submit_grounded_candidate_batch,
    verify_evidence_target,
)
from kotekomi_domain import (
    AssertionEvidenceRole,
    DocumentRepresentationBundle,
    DocumentVersionKind,
    ModelRunStatus,
    RepresentationAnalyzability,
    ReviewStatus,
    SourceType,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)
RAW_PDF = FIXTURE_PATH.read_bytes()
RAW_PDF_DIGEST = "510e8700c0afde7206599f9d0ebd8374b1034204f02e36066aec57d8054b43b7"
NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
BUILD_IDENTITY = BuildIdentity("r1a-pdf", "r1a-pdf", "a" * 64, "1")
POLICY_ID = "r1a_born_digital_pdf_v1"
PRIORITY_SENTENCE = (
    "The CHIP highlights four key health prioritieshealthcare access, mental health, housing, "
    "and food security -identified through community input and data collection in the "
    "community health assessment."
)
PRIORITY_SUFFIX = " These priorities reflect HealthyJoCo's shared vision"


class RecordingDoclingParser:
    def __init__(self) -> None:
        self._parser = DoclingPdfParser(DoclingPdfParserConfig())
        self.results: list[PdfParseResult] = []

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        return self._parser.processing_identity(policy_id)

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        result = self._parser.parse(parse_input)
        self.results.append(result)
        return result


class FixtureProcessingClock:
    def now(self) -> datetime:
        return NOW


class FixtureExactTokenizer:
    tokenizer_id = "r1c_fixture_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def _fixture_model_identity() -> ModelIdentitySnapshot:
    return ModelIdentitySnapshot(
        "r1d_fixture_model",
        "b" * 64,
        "fixture-runtime-v1",
        FixtureExactTokenizer.tokenizer_id,
        (ExecutionSetting("seed", 7), ExecutionSetting("temperature", 0)),
    )


def _fixture_execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=_fixture_model_identity(),
        generation_parameters=(ExecutionSetting("seed", 7), ExecutionSetting("temperature", 0)),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=manifest.schema_id,
        schema_digest=manifest.schema_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="staged_claim_output_v1",
    )


class FixtureModelTaskRuntime:
    def __init__(self, raw_output: bytes) -> None:
        self.raw_output = raw_output
        self.requests: list[ModelTaskRequest] = []

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return _fixture_model_identity()

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        return ModelTaskResponse(
            self.raw_output,
            ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(
                    task.execution_spec.model_identity
                ),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=task.rendered_input_digest,
                input_token_count=None,
                output_token_count=None,
            ),
        )


def _capture_request() -> CaptureRequest:
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title="2025 Community Health Improvement Plan Press Release",
            stable_key="johnson-county-2025-community-health-improvement-plan-press-release",
            uri="fixture://2025-community-health-improvement-plan-press-release.pdf",
        ),
        payload=RAW_PDF,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{RAW_PDF_DIGEST}.bin",
        idempotency_key="r1a-community-health-press-release-v1",
        retrieval_method="fixture",
        requested_uri="fixture://2025-community-health-improvement-plan-press-release.pdf",
        canonical_uri="fixture://2025-community-health-improvement-plan-press-release.pdf",
        provider_item_id=None,
        provider_version="2025-03-18",
        version_kind=DocumentVersionKind.ORIGINAL,
        publication_time=None,
        provider_update_time=None,
        captured_at=NOW,
        transaction_time=NOW,
        rights_profile_id=None,
        embargo_until=None,
        request_metadata={},
        response_metadata={},
    )


def _ingest_input(document_id: str, raw_blob_id: str) -> PdfIngestInput:
    return PdfIngestInput(
        document_id=document_id,
        raw_bytes=RAW_PDF,
        policy_id=POLICY_ID,
        ingested_at=NOW,
        raw_blob_id=raw_blob_id,
        build_identity=BUILD_IDENTITY,
    )


def test_docling_r1a_ingests_the_press_release_as_an_analyzeable_representation(
    tmp_path: Path,
) -> None:
    assert hashlib.sha256(RAW_PDF).hexdigest() == RAW_PDF_DIGEST
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    capture_identity_result = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(
        capture_identity_result.raw_blob_id,
        RAW_PDF,
        RAW_PDF_DIGEST,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)

    parser = RecordingDoclingParser()
    with sqlite_ledger_transaction(ledger_path) as repository:
        first = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
            FixtureProcessingClock(),
        )
        assert first.representation_id is not None
        stored_bundle = repository.get_document_representation_bundle(first.representation_id)

    with sqlite_ledger_transaction(ledger_path) as repository:
        second = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
            FixtureProcessingClock(),
        )
        assert second.representation_id is not None
        replayed_bundle = repository.get_document_representation_bundle(second.representation_id)

    assert archive.read_raw_source(capture.raw_blob.id) == RAW_PDF
    assert first.representation_id == second.representation_id
    assert first.provenance_activity_id is not None
    assert second.provenance_activity_id is None
    assert len(parser.results) == 2
    first_result, second_result = parser.results
    assert first_result.preflight == second_result.preflight
    assert first_result.representation_bundle is not None
    assert first_result.representation_bundle == second_result.representation_bundle
    assert stored_bundle is not None
    assert replayed_bundle is not None
    _assert_persisted_bundle(first_result.representation_bundle, stored_bundle)
    _assert_persisted_bundle(first_result.representation_bundle, replayed_bundle)

    _assert_r1a_representation(first_result.representation_bundle, first_result)


def test_docling_r1b_replays_the_priority_sentence_after_review_and_restart(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive_path = tmp_path / "archive"
    archive = LocalArchiveStore(archive_path)
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    capture_identity_result = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(
        capture_identity_result.raw_blob_id,
        RAW_PDF,
        RAW_PDF_DIGEST,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)
        ingest_outcome = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
            FixtureProcessingClock(),
        )
        assert ingest_outcome.representation_id is not None
        bundle = repository.get_document_representation_bundle(ingest_outcome.representation_id)
        assert bundle is not None
        priority_node = next(
            node
            for node in bundle.nodes
            if PRIORITY_SENTENCE in bundle.text_views[0].text[node.start_char : node.end_char]
        )
        manifest = build_grounded_candidate_context(
            GroundedCandidateContextInput(
                source_id=capture.source.id,
                document_id=capture.document.id,
                representation_id=bundle.representation.id,
                node_ids=(priority_node.id,),
            ),
            repository,
        )
        batch = submit_grounded_candidate_batch(
            _priority_sentence_batch(capture.source.id, capture.document.id, manifest),
            repository,
        )
        approve_proposed_change(
            ReviewProposedChangeInput(
                batch.proposed_change_ids_by_local_id["healthy_joco"], "reviewer", NOW
            ),
            repository,
        )
        review = approve_proposed_change(
            ReviewProposedChangeInput(
                batch.proposed_change_ids_by_local_id["priority_claim"], "reviewer", NOW
            ),
            repository,
        )
        assert review.accepted_record_id is not None

    reopened_archive = LocalArchiveStore(archive_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        evidence_target_id = batch.evidence_target_ids_by_local_id["priority_sentence"]
        evidence = repository.get_evidence_target(evidence_target_id)
        assertion = repository.get_assertion(review.accepted_record_id)
        link = repository.get_assertion_evidence_link(review.assertion_evidence_link_ids[0])
        assert evidence is not None
        assert assertion is not None
        assert link is not None
        assert link.role is AssertionEvidenceRole.DIRECT_SUPPORT
        validation_attempt = repository.get_evidence_validation_attempt(link.validation_attempt_id)
        assert validation_attempt is not None
        assert verify_evidence_target(evidence, validation_attempt, repository).valid
        replayed_manifest = build_grounded_candidate_context(
            GroundedCandidateContextInput(
                evidence.source_id,
                evidence.document_id,
                evidence.representation_id,
                evidence.node_ids,
            ),
            repository,
        )
        assert replayed_manifest == manifest
        bundle = repository.get_document_representation_bundle(evidence.representation_id)
        assert bundle is not None
        text_view = next(view for view in bundle.text_views if view.id == evidence.text_view_id)
        priority_node = next(node for node in bundle.nodes if node.id == evidence.node_ids[0])
        priority_region = next(
            region for region in bundle.source_regions if region.id == evidence.pdf_region_ids[0]
        )

    assert reopened_archive.read_raw_source(capture.raw_blob.id) == RAW_PDF
    assert assertion.id == review.accepted_record_id
    assert evidence.exact_text == PRIORITY_SENTENCE
    assert text_view.text.count(PRIORITY_SENTENCE) == 1
    assert text_view.text[evidence.start_char : evidence.end_char] == PRIORITY_SENTENCE
    assert (
        priority_node.start_char
        <= evidence.start_char
        < evidence.end_char
        <= priority_node.end_char
    )
    assert evidence.pdf_region_ids == priority_node.source_region_ids
    assert priority_region.page_number == 1
    assert (priority_region.page_width, priority_region.page_height) == (612.0, 792.0)
    assert abs(priority_region.left - 72.024) < 0.000001
    assert abs(priority_region.top - 344.09288) < 0.000001
    assert abs(priority_region.right - 539.12056) < 0.000001
    assert abs(priority_region.bottom - 404.6349670718232) < 0.000001


def test_docling_r1c_includes_chip_definition_and_excludes_furniture_deterministically(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    capture_identity_result = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(
        capture_identity_result.raw_blob_id,
        RAW_PDF,
        RAW_PDF_DIGEST,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)
        ingest_outcome = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
            FixtureProcessingClock(),
        )
        assert ingest_outcome.representation_id is not None
        bundle = repository.get_document_representation_bundle(ingest_outcome.representation_id)
        assert bundle is not None
        plan = plan_analysis_units(
            AnalysisUnitPlanningInput(bundle.representation.id, "r1c_pdf_v1", "extract"),
            repository,
        )
        priority_node = next(
            node
            for node in bundle.nodes
            if PRIORITY_SENTENCE in bundle.text_views[0].text[node.start_char : node.end_char]
        )
        focus_unit = next(unit for unit in plan.units if unit.focus_node_ids == (priority_node.id,))
        manifest_input = ContextManifestInput(
            analysis_unit=focus_unit,
            model_profile=ContextModelProfile("r1c_fixture_model", 512, 64, 16),
            prompt_id="r1c_fixture_prompt",
            prompt_bytes=b"Extract a grounded source claim.",
            schema_id="r1c_fixture_schema",
            schema_bytes=b'{"type":"object"}',
            renderer_version="r1c_renderer_v1",
        )
        tokenizer = FixtureExactTokenizer()
        first = build_context_manifest(manifest_input, repository, tokenizer)
        second = build_context_manifest(manifest_input, repository, tokenizer)
        blocked = build_context_manifest(
            ContextManifestInput(
                analysis_unit=focus_unit,
                model_profile=ContextModelProfile("r1c_fixture_model", 8, 4, 2),
                prompt_id=manifest_input.prompt_id,
                prompt_bytes=manifest_input.prompt_bytes,
                schema_id=manifest_input.schema_id,
                schema_bytes=manifest_input.schema_bytes,
                renderer_version=manifest_input.renderer_version,
            ),
            repository,
            tokenizer,
        )
        grouped_plan = plan_analysis_units(
            AnalysisUnitPlanningInput(
                bundle.representation.id,
                "r1c_paragraph_group_v1",
                "extract",
                max_focus_nodes_per_unit=100,
            ),
            repository,
        )
        split_unit = next(
            unit for unit in grouped_plan.units if priority_node.id in unit.focus_node_ids
        )
        assert len(split_unit.focus_node_ids) > 1
        split = build_context_manifest(
            ContextManifestInput(
                analysis_unit=split_unit,
                model_profile=ContextModelProfile("r1c_fixture_model", 8, 4, 2),
                prompt_id=manifest_input.prompt_id,
                prompt_bytes=manifest_input.prompt_bytes,
                schema_id=manifest_input.schema_id,
                schema_bytes=manifest_input.schema_bytes,
                renderer_version=manifest_input.renderer_version,
            ),
            repository,
            tokenizer,
        )

    assert first == second
    assert first.manifest.status is ContextManifestStatus.READY
    selected = first.manifest.selected_candidates
    assert tuple(candidate.role.value for candidate in selected) == (
        "focus",
        "heading",
        "definition",
    )
    definition_node = next(node for node in bundle.nodes if node.id == selected[2].node_id)
    assert (
        "Community Health Improvement Plan (CHIP)"
        in bundle.text_views[0].text[definition_node.start_char : definition_node.end_char]
    )
    assert all(candidate.required for candidate in selected)
    assert all(
        item.reason_code == "furniture_excluded" for item in first.manifest.excluded_candidates
    )
    assert len(first.manifest.excluded_candidates) == 2
    assert b"A community where all can achieve optimal health." not in first.manifest.rendered_input
    assert b"855 S. DUBUQUE STREET" not in first.manifest.rendered_input
    assert tokenizer.count_tokens(first.manifest.rendered_input) == first.manifest.input_token_count
    assert blocked.manifest.status is ContextManifestStatus.CONTEXT_BUDGET_BLOCKED
    assert blocked.blocked_reason == "required_context_exceeds_budget"
    assert split.manifest.status is ContextManifestStatus.SPLIT
    assert split.manifest.split_strategy_id == "paragraph_focus_split_v1"
    assert split.manifest.child_analysis_unit_ids == tuple(unit.id for unit in split.split_units)

    with sqlite_ledger_transaction(ledger_path) as repository:
        persisted_split = load_context_manifest(split.manifest.id, repository)
        restarted_children = load_split_analysis_units(persisted_split.id, repository)
        assert persisted_split == split.manifest
        assert tuple(child.id for child in restarted_children) == (
            persisted_split.child_analysis_unit_ids
        )
        assert tuple(child.focus_node_ids for child in restarted_children) == tuple(
            (node_id,) for node_id in split_unit.focus_node_ids
        )
        child_outcomes = tuple(
            build_context_manifest(
                ContextManifestInput(
                    analysis_unit=child,
                    model_profile=ContextModelProfile("r1c_fixture_model", 512, 64, 16),
                    prompt_id=manifest_input.prompt_id,
                    prompt_bytes=manifest_input.prompt_bytes,
                    schema_id=manifest_input.schema_id,
                    schema_bytes=manifest_input.schema_bytes,
                    renderer_version=manifest_input.renderer_version,
                ),
                repository,
                tokenizer,
            )
            for child in restarted_children
        )

    assert all(
        outcome.manifest.status
        in {ContextManifestStatus.READY, ContextManifestStatus.CONTEXT_BUDGET_BLOCKED}
        for outcome in child_outcomes
    )


def test_docling_r1d_staged_extraction_publishes_one_task_local_candidate(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive_path = tmp_path / "archive"
    archive = LocalArchiveStore(archive_path)
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    capture_identity_result = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(
        capture_identity_result.raw_blob_id,
        RAW_PDF,
        RAW_PDF_DIGEST,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)
        ingest_outcome = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
            FixtureProcessingClock(),
        )
        assert ingest_outcome.representation_id is not None
        bundle = repository.get_document_representation_bundle(ingest_outcome.representation_id)
        assert bundle is not None
        priority_node = next(
            node
            for node in bundle.nodes
            if PRIORITY_SENTENCE in bundle.text_views[0].text[node.start_char : node.end_char]
        )
        focus_unit = next(
            unit
            for unit in plan_analysis_units(
                AnalysisUnitPlanningInput(
                    bundle.representation.id, "r1d_pdf_v1", "claim_extraction"
                ),
                repository,
            ).units
            if unit.focus_node_ids == (priority_node.id,)
        )
        manifest = build_context_manifest(
            ContextManifestInput(
                analysis_unit=focus_unit,
                model_profile=ContextModelProfile("r1d_fixture_model", 512, 64, 16),
                prompt_id="r1d_claim_extraction",
                prompt_bytes=b"Extract one grounded source claim.",
                schema_id="staged_claim_output_v1",
                schema_bytes=staged_claim_output_schema_bytes(),
                renderer_version="r1d_renderer_v1",
            ),
            repository,
            FixtureExactTokenizer(),
        ).manifest
        text_view = bundle.text_views[0]
        start_char = text_view.text.index(PRIORITY_SENTENCE)
        fixture_output = json.dumps(
            {
                "kind": "candidates",
                "schema_id": "staged_claim_output_v1",
                "organizations": [
                    {"local_id": "model_subject", "name": "HealthyJoCo"},
                ],
                "evidence": [
                    {
                        "local_id": "model_evidence",
                        "node_id": priority_node.id,
                        "exact_quote": PRIORITY_SENTENCE,
                        "node_local_start": start_char - priority_node.start_char,
                        "node_local_end": (
                            start_char + len(PRIORITY_SENTENCE) - priority_node.start_char
                        ),
                    }
                ],
                "assertions": [
                    {
                        "local_id": "model_claim",
                        "subject_organization_local_id": "model_subject",
                        "evidence_local_id": "model_evidence",
                        "predicate": "identified_community_health_priorities",
                        "object_value": (
                            "healthcare access, mental health, housing, and food security"
                        ),
                    }
                ],
            },
            separators=(",", ":"),
        ).encode()
        runtime = FixtureModelTaskRuntime(fixture_output)
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=capture.source.id,
                document_id=capture.document.id,
                representation_id=bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"Extract one grounded source claim.",
                execution_spec=_fixture_execution_spec(manifest),
                validator_version="r1d-evidence-validator-v1",
                started_at=NOW,
                completed_at=NOW,
            ),
            repository,
            archive,
            runtime,
            Uuid4ModelRunIdFactory(),
            FixtureExactTokenizer(),
            StagedClaimTaskSchemaRegistry(),
        )
        assert outcome.model_run.status is ModelRunStatus.SUCCEEDED, outcome.model_run.error_message
        assert outcome.proposed_change_batch is not None
        assertion_change = repository.get_proposed_change(
            outcome.proposed_change_batch.proposed_change_ids_by_local_id["model_claim"]
        )
        assert assertion_change is not None
        assert assertion_change.proposed_json["stable_label"] != "model_claim"
        assert outcome.model_run.extraction_task_id == outcome.extraction_task.id
        assert repository.get_extraction_task(outcome.extraction_task.id) == outcome.extraction_task
        assert repository.get_model_run(outcome.model_run.id) == outcome.model_run
        reviewed_change = assertion_change.model_copy(
            update={
                "review_status": ReviewStatus.REJECTED,
                "updated_at": NOW + timedelta(minutes=1),
            }
        )
        repository.save_proposed_change(reviewed_change)
        retry_outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=capture.source.id,
                document_id=capture.document.id,
                representation_id=bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"Extract one grounded source claim.",
                execution_spec=_fixture_execution_spec(manifest),
                validator_version="r1d-evidence-validator-v1",
                started_at=NOW + timedelta(minutes=2),
                completed_at=NOW + timedelta(minutes=3),
            ),
            repository,
            archive,
            runtime,
            Uuid4ModelRunIdFactory(),
            FixtureExactTokenizer(),
            StagedClaimTaskSchemaRegistry(),
        )
        assert retry_outcome.model_run.status is ModelRunStatus.SUCCEEDED
        assert retry_outcome.model_run.id != outcome.model_run.id
        assert retry_outcome.extraction_task == outcome.extraction_task
        assert retry_outcome.proposed_change_batch is not None
        assert (
            retry_outcome.proposed_change_batch.evidence_target_ids_by_local_id
            == outcome.proposed_change_batch.evidence_target_ids_by_local_id
        )
        assert (
            retry_outcome.proposed_change_batch.validation_attempt_ids_by_evidence_local_id
            != outcome.proposed_change_batch.validation_attempt_ids_by_evidence_local_id
        )
        assert repository.get_proposed_change(assertion_change.id) == reviewed_change
        assertion_change_id = assertion_change.id
        alternate_output = fixture_output.replace(
            b'"predicate":"identified_community_health_priorities"',
            b'"predicate":"reported_community_health_priorities"',
        )
        alternate_runtime = FixtureModelTaskRuntime(alternate_output)
        alternate_outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=capture.source.id,
                document_id=capture.document.id,
                representation_id=bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"Extract one grounded source claim.",
                execution_spec=_fixture_execution_spec(manifest),
                validator_version="r1d-evidence-validator-v1",
                started_at=NOW + timedelta(minutes=4),
                completed_at=NOW + timedelta(minutes=5),
            ),
            repository,
            archive,
            alternate_runtime,
            Uuid4ModelRunIdFactory(),
            FixtureExactTokenizer(),
            StagedClaimTaskSchemaRegistry(),
        )
        assert alternate_outcome.model_run.status is ModelRunStatus.SUCCEEDED
        assert alternate_outcome.model_run.output_digest != outcome.model_run.output_digest
        assert alternate_outcome.proposed_change_batch is not None
        alternate_assertion_change_id = (
            alternate_outcome.proposed_change_batch.proposed_change_ids_by_local_id["model_claim"]
        )
        assert alternate_assertion_change_id != assertion_change.id
        assert repository.get_proposed_change(assertion_change.id) == reviewed_change

    reopened_archive = LocalArchiveStore(archive_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        replayed_task = repository.get_extraction_task(outcome.extraction_task.id)
        replayed_run = repository.get_model_run(outcome.model_run.id)
        replayed_change = repository.get_proposed_change(assertion_change_id)
        replayed_alternate_change = repository.get_proposed_change(alternate_assertion_change_id)
        assert replayed_task is not None
        assert replayed_run is not None
        assert replayed_change is not None
        assert replayed_alternate_change is not None
        assert replayed_task.context_manifest_id == manifest.id
        assert replayed_run.extraction_task_id == replayed_task.id
        assert (
            render_context(
                manifest.id,
                repository,
                FixtureExactTokenizer(),
                b"Extract one grounded source claim.",
                staged_claim_output_schema_bytes(),
            )
            == runtime.requests[0].rendered_input
        )
        evidence_links = replayed_change.proposed_json["evidence_links"]
        assert isinstance(evidence_links, list)
        assert isinstance(evidence_links[0], dict)
        evidence_target_id = evidence_links[0]["evidence_target_id"]
        assert isinstance(evidence_target_id, str)
        evidence = repository.get_evidence_target(evidence_target_id)
        assert evidence is not None
        assert evidence.node_ids == (priority_node.id,)
        runs = repository.list_model_runs_for_task(replayed_task.id)
        assert len(runs) == 3
        assert {run.output_digest for run in runs} == {
            outcome.model_run.output_digest,
            alternate_outcome.model_run.output_digest,
        }
        first_provenance = repository.get_provenance_activity(
            outcome.proposed_change_batch.provenance_activity_id
        )
        alternate_provenance = repository.get_provenance_activity(
            alternate_outcome.proposed_change_batch.provenance_activity_id
        )
        assert first_provenance is not None
        assert alternate_provenance is not None
        assert first_provenance != alternate_provenance

    assert len(runtime.requests) == 2
    assert runtime.requests[0].context_manifest_id == manifest.id
    assert runtime.requests[0].execution_spec.model_profile_id == manifest.model_profile_id
    assert runtime.requests[0].execution_spec.model_identity.tokenizer_id == manifest.tokenizer_id
    assert runtime.requests[0].execution_spec.context_manifest_digest == manifest.manifest_digest
    assert outcome.extraction_task.execution_spec_digest == outcome.model_run.execution_spec_digest
    assert reopened_archive.read_model_run_output(outcome.model_run.id) == fixture_output
    assert reopened_archive.read_model_run_output(retry_outcome.model_run.id) == fixture_output
    assert (
        reopened_archive.read_model_run_output(alternate_outcome.model_run.id) == alternate_output
    )


def _r1d_output(
    *,
    node_id: str,
    node_local_start: int,
    node_local_end: int,
    organization_name: str,
    predicate: str,
) -> bytes:
    return json.dumps(
        {
            "kind": "candidates",
            "schema_id": "staged_claim_output_v1",
            "organizations": [{"local_id": "model_subject", "name": organization_name}],
            "evidence": [
                {
                    "local_id": "model_evidence",
                    "node_id": node_id,
                    "exact_quote": PRIORITY_SENTENCE,
                    "node_local_start": node_local_start,
                    "node_local_end": node_local_end,
                }
            ],
            "assertions": [
                {
                    "local_id": "model_claim",
                    "subject_organization_local_id": "model_subject",
                    "evidence_local_id": "model_evidence",
                    "predicate": predicate,
                    "object_value": "healthcare access, mental health, housing, and food security",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()


def test_sqlite_model_run_publication_fault_matrix_is_atomic_and_retryable(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request()
    identity_policy = StableSourceIdentityPolicy()
    capture_identity_result = capture_identity(request, identity_policy)
    archive.put_if_absent_or_identical(
        capture_identity_result.raw_blob_id,
        RAW_PDF,
        RAW_PDF_DIGEST,
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, identity_policy)
        ingest_outcome = ingest_pdf(
            _ingest_input(capture.document.id, capture.raw_blob.id),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
            FixtureProcessingClock(),
        )
        assert ingest_outcome.representation_id is not None
        bundle = repository.get_document_representation_bundle(ingest_outcome.representation_id)
        assert bundle is not None
        priority_node = next(
            node
            for node in bundle.nodes
            if PRIORITY_SENTENCE in bundle.text_views[0].text[node.start_char : node.end_char]
        )
        focus_unit = next(
            unit
            for unit in plan_analysis_units(
                AnalysisUnitPlanningInput(
                    bundle.representation.id, "r1d_fault_matrix_v1", "claim_extraction"
                ),
                repository,
            ).units
            if unit.focus_node_ids == (priority_node.id,)
        )
        manifest = build_context_manifest(
            ContextManifestInput(
                analysis_unit=focus_unit,
                model_profile=ContextModelProfile("r1d_fixture_model", 512, 64, 16),
                prompt_id="r1d_claim_extraction",
                prompt_bytes=b"Extract one grounded source claim.",
                schema_id="staged_claim_output_v1",
                schema_bytes=staged_claim_output_schema_bytes(),
                renderer_version="r1d_renderer_v1",
            ),
            repository,
            FixtureExactTokenizer(),
        ).manifest
        text_view = bundle.text_views[0]
        local_start = text_view.text.index(PRIORITY_SENTENCE) - priority_node.start_char
        local_end = local_start + len(PRIORITY_SENTENCE)
        baseline_output = _r1d_output(
            node_id=priority_node.id,
            node_local_start=local_start,
            node_local_end=local_end,
            organization_name="HealthyJoCo",
            predicate="identified_community_health_priorities",
        )
        baseline_outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=capture.source.id,
                document_id=capture.document.id,
                representation_id=bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"Extract one grounded source claim.",
                execution_spec=_fixture_execution_spec(manifest),
                validator_version="r1d-fault-validator-v1",
                started_at=NOW,
                completed_at=NOW,
            ),
            repository,
            archive,
            FixtureModelTaskRuntime(baseline_output),
            Uuid4ModelRunIdFactory(),
            FixtureExactTokenizer(),
            StagedClaimTaskSchemaRegistry(),
        )
        assert baseline_outcome.proposed_change_batch is not None
        baseline_assertion_id = (
            baseline_outcome.proposed_change_batch.proposed_change_ids_by_local_id["model_claim"]
        )
        baseline_assertion = repository.get_proposed_change(baseline_assertion_id)
        assert baseline_assertion is not None
        reviewed_assertion = baseline_assertion.model_copy(
            update={
                "review_status": ReviewStatus.REJECTED,
                "updated_at": NOW + timedelta(seconds=1),
            }
        )
        repository.save_proposed_change(reviewed_assertion)

    def publication_state(repository: SQLiteLedgerRepository) -> tuple[object, ...]:
        return (
            repository.list_provenance_activities(),
            repository.list_evidence_targets(),
            repository.list_evidence_validation_attempts(),
            repository.list_proposed_changes(),
        )

    fault_points = (
        "AFTER_PROVENANCE",
        "AFTER_EVIDENCE_TARGET",
        "AFTER_VALIDATION_ATTEMPT",
        "AFTER_ORGANIZATION_PROPOSAL",
        "AFTER_ASSERTION_PROPOSAL",
        "BEFORE_SUCCESSFUL_MODEL_RUN",
        "AFTER_SUCCESSFUL_MODEL_RUN",
        "BEFORE_SAVEPOINT_RELEASE",
    )

    class FaultingRepository(SQLiteLedgerRepository):
        def __init__(self, connection: sqlite3.Connection, fault_point: str) -> None:
            super().__init__(connection)
            self._fault_point = fault_point

        def _successful_model_run_publication_checkpoint(self, name: str) -> None:
            if name == self._fault_point:
                raise OSError(f"injected {self._fault_point}")

    failed_outcomes: list[BoundedExtractionOutcome] = []
    retry_outcomes: list[BoundedExtractionOutcome] = []
    for index, fault_point in enumerate(fault_points, start=1):
        output = _r1d_output(
            node_id=priority_node.id,
            node_local_start=local_start,
            node_local_end=local_end,
            organization_name=f"HealthyJoCo fault {index}",
            predicate=f"reported_community_health_priorities_{index}",
        )
        with sqlite3.connect(ledger_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")

            repository = FaultingRepository(connection, fault_point)
            before = publication_state(repository)
            failed = run_bounded_extraction(
                BoundedExtractionInput(
                    source_id=capture.source.id,
                    document_id=capture.document.id,
                    representation_id=bundle.representation.id,
                    context_manifest_id=manifest.id,
                    prompt_bytes=b"Extract one grounded source claim.",
                    execution_spec=_fixture_execution_spec(manifest),
                    validator_version="r1d-fault-validator-v1",
                    started_at=NOW + timedelta(minutes=index * 2),
                    completed_at=NOW + timedelta(minutes=index * 2, seconds=1),
                ),
                repository,
                archive,
                FixtureModelTaskRuntime(output),
                Uuid4ModelRunIdFactory(),
                FixtureExactTokenizer(),
                StagedClaimTaskSchemaRegistry(),
            )
            assert failed.model_run.status is ModelRunStatus.PUBLISH_FAILED
            assert publication_state(repository) == before
            assert repository.get_proposed_change(baseline_assertion_id) == reviewed_assertion
            connection.commit()
        assert archive.read_model_run_output(failed.model_run.id) == output
        failed_outcomes.append(failed)

        with sqlite_ledger_transaction(ledger_path) as repository:
            retried = run_bounded_extraction(
                BoundedExtractionInput(
                    source_id=capture.source.id,
                    document_id=capture.document.id,
                    representation_id=bundle.representation.id,
                    context_manifest_id=manifest.id,
                    prompt_bytes=b"Extract one grounded source claim.",
                    execution_spec=_fixture_execution_spec(manifest),
                    validator_version="r1d-fault-validator-v1",
                    started_at=NOW + timedelta(minutes=index * 2, seconds=2),
                    completed_at=NOW + timedelta(minutes=index * 2, seconds=3),
                ),
                repository,
                archive,
                FixtureModelTaskRuntime(output),
                Uuid4ModelRunIdFactory(),
                FixtureExactTokenizer(),
                StagedClaimTaskSchemaRegistry(),
            )
            assert retried.model_run.status is ModelRunStatus.SUCCEEDED
            assert repository.get_proposed_change(baseline_assertion_id) == reviewed_assertion
            retry_outcomes.append(retried)

    reopened_archive = LocalArchiveStore(archive.archive_root)
    with sqlite_ledger_transaction(ledger_path) as repository:
        runs = repository.list_model_runs_for_task(baseline_outcome.extraction_task.id)
        assert len(runs) == 1 + 2 * len(fault_points)
        assert sum(run.status is ModelRunStatus.PUBLISH_FAILED for run in runs) == len(fault_points)
        assert sum(run.status is ModelRunStatus.SUCCEEDED for run in runs) == 1 + len(fault_points)
        assert repository.get_proposed_change(baseline_assertion_id) == reviewed_assertion
    for outcome in (*failed_outcomes, *retry_outcomes):
        assert reopened_archive.read_model_run_output(outcome.model_run.id)


def _priority_sentence_batch(
    source_id: str,
    document_id: str,
    manifest: GroundedCandidateContext,
) -> GroundedCandidateBatchInput:
    assert len(manifest.text_views) == 1
    assert len(manifest.nodes) == 1
    text_view = manifest.text_views[0]
    priority_node = manifest.nodes[0]
    start_char = text_view.text.index(PRIORITY_SENTENCE)
    end_char = start_char + len(PRIORITY_SENTENCE)
    return GroundedCandidateBatchInput(
        task_fingerprint="d" * 64,
        source_id=source_id,
        document_id=document_id,
        representation_id=manifest.representation_id,
        model_name="r1b-bounded-fixture-producer",
        prompt_id="r1b-priority-sentence",
        validator_version="r1b-v1",
        submitted_at=NOW,
        organizations=(GroundedOrganizationCandidate("healthy_joco", "HealthyJoCo"),),
        evidence=(
            GroundedEvidenceCandidate(
                local_id="priority_sentence",
                text_view_id=text_view.id,
                start_char=start_char,
                end_char=end_char,
                exact_text=PRIORITY_SENTENCE,
                node_ids=(priority_node.id,),
                pdf_region_ids=priority_node.source_region_ids,
                suffix_text=PRIORITY_SUFFIX,
            ),
        ),
        assertions=(
            GroundedAssertionCandidate(
                local_id="priority_claim",
                subject_organization_local_id="healthy_joco",
                evidence_local_id="priority_sentence",
                predicate="identified_community_health_priorities",
                object_value="healthcare access, mental health, housing, and food security",
            ),
        ),
    )


def _assert_persisted_bundle(
    expected: DocumentRepresentationBundle,
    actual: DocumentRepresentationBundle,
) -> None:
    assert actual.representation == expected.representation
    assert actual.text_views == expected.text_views
    assert actual.nodes == tuple(sorted(expected.nodes, key=lambda node: node.id))
    assert actual.edges == tuple(sorted(expected.edges, key=lambda edge: edge.id))
    assert actual.source_regions == tuple(
        sorted(expected.source_regions, key=lambda region: region.id)
    )
    assert actual.quality_report == expected.quality_report


def _assert_r1a_representation(
    bundle: DocumentRepresentationBundle,
    parse_result: PdfParseResult,
) -> None:
    preflight = parse_result.preflight
    assert preflight.page_count == 1
    assert preflight.warnings == ()
    assert preflight.pages == (
        PdfPagePreflight(
            page_index=1,
            width=612.0,
            height=792.0,
            rotation=0,
            embedded_text_character_count=2463,
        ),
    )
    assert parse_result.blocking_reasons == ()

    assert bundle.quality_report.analyzability is RepresentationAnalyzability.ACCEPTABLE
    assert bundle.quality_report.issues == ()
    assert bundle.quality_report.metric_values == {
        "page_count": 1,
        "covered_page_count": 1,
        "logical_text_char_count": 2481,
        "reading_order_node_count": 19,
        "heading_node_count": 2,
        "paragraph_node_count": 15,
        "furniture_node_count": 2,
        "source_region_count": 19,
    }
    assert len(bundle.text_views) == 1
    text_view = bundle.text_views[0]
    assert text_view.text.startswith("For Immediate Release March 18, 2025\nContact\n")

    root, *content_nodes = bundle.nodes
    assert root.node_type == "document"
    assert (root.start_char, root.end_char) == (0, len(text_view.text))
    assert tuple(node.order_index for node in bundle.nodes) == tuple(range(len(bundle.nodes)))
    assert {node.node_type for node in content_nodes} == {"furniture", "heading", "paragraph"}
    assert all(text_view.text[node.start_char : node.end_char] for node in content_nodes)
    assert all(node.source_region_ids for node in content_nodes)
    assert tuple(edge.from_node_id for edge in bundle.edges) == (root.id,) * len(content_nodes)
    assert tuple(edge.to_node_id for edge in bundle.edges) == tuple(
        node.id for node in content_nodes
    )

    preflight_pages = {page.page_index: page for page in preflight.pages}
    assert {region.page_number for region in bundle.source_regions} == set(preflight_pages)
    for region in bundle.source_regions:
        page = preflight_pages[region.page_number]
        assert region.coordinate_system == "pdf_points_top_left_v1"
        assert (region.page_width, region.page_height) == (page.width, page.height)
        assert 0 <= region.left < region.right <= page.width
        assert 0 <= region.top < region.bottom <= page.height

    selected_paragraph = next(
        node
        for node in content_nodes
        if text_view.text[node.start_char : node.end_char].startswith("IOWA CITY, Iowa")
    )
    selected_region = next(
        region
        for region in bundle.source_regions
        if region.id == selected_paragraph.source_region_ids[0]
    )
    assert selected_region.page_number == 1
    assert abs(selected_region.left - 72.024) < 0.000001
    assert abs(selected_region.top - 268.25288) < 0.000001
    assert abs(selected_region.right - 538.12912) < 0.000001
    assert abs(selected_region.bottom - 328.67496707182323) < 0.000001
