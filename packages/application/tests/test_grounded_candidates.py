import hashlib
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from kotekomi_application import (
    LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
    PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V1,
    PARAGRAPH_SEGMENT_V3,
    AnalysisCoverageState,
    AnalysisRunInput,
    AnalysisRunItemInput,
    AnalysisUnitPlanningInput,
    AtomicHypothesis,
    BoundedExtractionInput,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    CoverageIntegrityFailureReason,
    CoveragePolicyDecision,
    CoverageTerminalStatus,
    ExecutionSetting,
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedCandidateContextInput,
    GroundedEvidenceCandidate,
    GroundedLiteralObject,
    GroundedOrganizationCandidate,
    GroundedOrganizationReferenceObject,
    HypothesisVerifierSpec,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelIdentitySnapshot,
    ModelRuntimeDeadlineExceeded,
    ModelTaskRequest,
    ModelTaskResponse,
    OrganizationMention,
    OrganizationMentionTaskSchemaRegistry,
    OrganizationQualification,
    OrganizationQualificationLabelTaskSchemaRegistry,
    OrganizationQualificationTaskSchemaRegistry,
    ParagraphHypothesisTaskSchemaRegistry,
    PinnedTaskSchema,
    SemanticDraftTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    build_context_manifest,
    build_coverage_report,
    build_grounded_candidate_context,
    context_manifest_digest,
    freeze_analysis_plan,
    generation_parameters_digest,
    load_frozen_analysis_plan,
    model_execution_spec_digest,
    model_identity_snapshot_digest,
    organization_mention_text_schema_bytes,
    organization_qualification_text_schema_bytes,
    paragraph_hypothesis_text_schema_bytes,
    paragraph_source_segments,
    plan_analysis_units,
    record_analysis_item_attempt,
    run_bounded_extraction,
    semantic_draft_text_schema_bytes,
    start_analysis_run,
    submit_grounded_candidate_batch,
)
from kotekomi_application.organization_semantic_qualification import (
    OrganizationQualificationJudgment,
)
from kotekomi_application.staged_model_extraction import (
    organization_qualification_label_schema_bytes,
)
from kotekomi_domain import (
    AnalysisItemAttempt,
    AnalysisPlanArtifact,
    AnalysisRun,
    AnalysisRunState,
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EvidenceTarget,
    EvidenceValidationAttempt,
    ExtractionTask,
    ModelRun,
    ModelRunStatus,
    ParseQualityReport,
    PdfPreflightReport,
    PlannedAnalysisItem,
    ProcessingAttempt,
    ProposedChange,
    ProvenanceActivity,
    RepresentationAnalyzability,
    Source,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
TEXT = (
    "Fixture Organization partners with Alpha. "
    "Fixture Organization supports Beta. "
    "Gamma collaborates with Delta."
)


class FakeGroundedCandidateLedger:
    def __init__(self) -> None:
        self.source = Source(
            id="src_grounded_fixture",
            source_type=SourceType.MANUAL_FILE,
            identity_policy_id="fixture",
            canonical_identity_key="grounded-fixture",
        )
        self.document = Document(
            id="doc_grounded_fixture",
            source_id=self.source.id,
            content_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        )
        self.bundle = _bundle(self.document.id)
        self.evidence_targets: dict[str, EvidenceTarget] = {}
        self.validation_attempts: dict[str, EvidenceValidationAttempt] = {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}
        self.proposed_changes: dict[str, ProposedChange] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.model_run_proposed_changes: dict[str, tuple[str, ...]] = {}
        self.manifests: dict[str, ContextManifestArtifact] = {}
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.analysis_plans: dict[str, AnalysisPlanArtifact] = {}
        self.analysis_runs: dict[str, AnalysisRun] = {}
        self.planned_analysis_items: dict[str, PlannedAnalysisItem] = {}
        self.analysis_item_attempts: dict[str, AnalysisItemAttempt] = {}
        self.context_manifest_query_extras: tuple[ContextManifestArtifact, ...] = ()
        self.fail_successful_commit = False

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def find_latest_complete_pdf_preflight_report_for_task(
        self,
        task_fingerprint_id: str,
    ) -> PdfPreflightReport | None:
        del task_fingerprint_id
        return None

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.evidence_targets.get(record_id)

    def save_evidence_target(self, record: EvidenceTarget) -> None:
        self.evidence_targets[record.id] = record

    def get_evidence_validation_attempt(self, record_id: str) -> EvidenceValidationAttempt | None:
        return self.validation_attempts.get(record_id)

    def save_evidence_validation_attempt(self, record: EvidenceValidationAttempt) -> None:
        self.validation_attempts[record.id] = record

    def commit_grounded_candidate_batch(
        self,
        *,
        evidence_targets: tuple[EvidenceTarget, ...],
        validation_attempts: tuple[EvidenceValidationAttempt, ...],
        provenance_activity: ProvenanceActivity,
        proposed_changes: tuple[ProposedChange, ...],
    ) -> None:
        self.evidence_targets.update({record.id: record for record in evidence_targets})
        self.validation_attempts.update({record.id: record for record in validation_attempts})
        self.provenance_activities[provenance_activity.id] = provenance_activity
        self.proposed_changes.update({record.id: record for record in proposed_changes})

    def save_extraction_task(self, record: ExtractionTask) -> None:
        self.extraction_tasks[record.id] = record

    def save_model_run(self, record: ModelRun) -> None:
        self.model_runs[record.id] = record

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def commit_successful_model_run_and_candidate_batch(
        self, *, model_run: ModelRun, batch: object
    ) -> None:
        from kotekomi_application.grounded_candidates import GroundedCandidateBatchCommit

        assert isinstance(batch, GroundedCandidateBatchCommit)
        if self.fail_successful_commit:
            raise RuntimeError("injected candidate batch commit failure")
        self.commit_grounded_candidate_batch(
            evidence_targets=batch.evidence_targets,
            validation_attempts=batch.validation_attempts,
            provenance_activity=batch.provenance_activity,
            proposed_changes=batch.proposed_changes,
        )
        self.save_model_run(model_run)
        self.model_run_proposed_changes[model_run.id] = tuple(
            record.id for record in batch.proposed_changes
        )

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.manifests.get(record_id)

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_analysis_plan_artifact(self, record: AnalysisPlanArtifact) -> None:
        self.analysis_plans[record.id] = record

    def get_analysis_plan_artifact(self, record_id: str) -> AnalysisPlanArtifact | None:
        return self.analysis_plans.get(record_id)

    def commit_analysis_run_scope(
        self,
        *,
        analysis_run: AnalysisRun,
        planned_items: tuple[PlannedAnalysisItem, ...],
    ) -> None:
        self.analysis_runs[analysis_run.id] = analysis_run
        self.planned_analysis_items.update({record.id: record for record in planned_items})

    def get_analysis_run(self, record_id: str) -> AnalysisRun | None:
        return self.analysis_runs.get(record_id)

    def list_planned_items_for_analysis_run(
        self, analysis_run_id: str
    ) -> tuple[PlannedAnalysisItem, ...]:
        return tuple(
            record
            for record in self.planned_analysis_items.values()
            if record.analysis_run_id == analysis_run_id
        )

    def save_analysis_item_attempt(self, record: AnalysisItemAttempt) -> None:
        self.analysis_item_attempts[record.id] = record

    def list_analysis_item_attempts_for_items(
        self, item_ids: tuple[str, ...]
    ) -> tuple[AnalysisItemAttempt, ...]:
        return tuple(
            record
            for record in self.analysis_item_attempts.values()
            if record.planned_item_id in item_ids
        )

    def list_context_manifests_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ContextManifestArtifact, ...]:
        return (
            *(self.manifests[record_id] for record_id in record_ids if record_id in self.manifests),
            *self.context_manifest_query_extras,
        )

    def list_extraction_tasks_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ExtractionTask, ...]:
        return tuple(
            self.extraction_tasks[record_id]
            for record_id in record_ids
            if record_id in self.extraction_tasks
        )

    def list_extraction_tasks_for_manifest_ids(
        self, manifest_ids: tuple[str, ...]
    ) -> tuple[ExtractionTask, ...]:
        return tuple(
            record
            for record in self.extraction_tasks.values()
            if record.context_manifest_id in manifest_ids
        )

    def list_model_runs_by_ids(self, record_ids: tuple[str, ...]) -> tuple[ModelRun, ...]:
        return tuple(
            self.model_runs[record_id] for record_id in record_ids if record_id in self.model_runs
        )

    def list_processing_attempts_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ProcessingAttempt, ...]:
        return ()

    def list_proposed_changes_for_model_run(self, model_run_id: str) -> tuple[ProposedChange, ...]:
        return tuple(
            self.proposed_changes[proposal_id]
            for proposal_id in sorted(self.model_run_proposed_changes.get(model_run_id, ()))
        )

    def list_provenance_activities_by_ids(
        self, record_ids: tuple[str, ...]
    ) -> tuple[ProvenanceActivity, ...]:
        return tuple(
            self.provenance_activities[record_id]
            for record_id in record_ids
            if record_id in self.provenance_activities
        )

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.analysis_units.update({record.id: record for record in child_analysis_units})
        self.manifests[manifest.id] = manifest


class FakeModelOutputArchive:
    def __init__(self) -> None:
        self.outputs: dict[str, bytes] = {}

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_digest
        self.outputs[model_run_id] = payload
        return object()


class FakeModelTaskRuntime:
    def __init__(
        self,
        raw_output: bytes,
        *,
        configured_identity: ModelIdentitySnapshot | None = None,
        receipt: ModelExecutionReceipt | None = None,
        first_response_event_milliseconds: int | None = None,
    ) -> None:
        self.raw_output = raw_output
        self.requests: list[ModelTaskRequest] = []
        self._configured_identity = configured_identity or _fixture_model_identity()
        self._receipt = receipt
        self._first_response_event_milliseconds = first_response_event_milliseconds

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return self._configured_identity

    @property
    def task_deadline_seconds(self) -> float:
        return 300.0

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        return ModelTaskResponse(
            self.raw_output,
            self._receipt
            or ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(
                    task.execution_spec.model_identity
                ),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=task.rendered_input_digest,
                input_token_count=len(task.rendered_input.decode().split()),
                output_token_count=None,
            ),
            self._first_response_event_milliseconds,
        )


class SequenceModelTaskRuntime(FakeModelTaskRuntime):
    def __init__(self, raw_outputs: tuple[bytes, ...]) -> None:
        super().__init__(raw_outputs[0])
        self._raw_outputs = iter(raw_outputs)

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.raw_output = next(self._raw_outputs)
        return super().run_model_task(task)


class FixedModelRunClock:
    def __init__(
        self, timestamps: tuple[datetime, ...], monotonic_values: tuple[float, ...]
    ) -> None:
        self._timestamps = iter(timestamps)
        self._monotonic_values = iter(monotonic_values)

    def now(self) -> datetime:
        return next(self._timestamps)

    def monotonic_seconds(self) -> float:
        return next(self._monotonic_values)


class FixtureTokenizer:
    tokenizer_id = "fixture_tokenizer_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


def _bundle(document_id: str, text: str = TEXT) -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_grounded_fixture",
        representation_id="rep_grounded_fixture",
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id="nod_grounded_root",
        representation_id="rep_grounded_fixture",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    node = DocumentNode(
        id="nod_grounded_fixture",
        representation_id="rep_grounded_fixture",
        node_type="paragraph",
        parent_node_id=root.id,
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    quality_report = ParseQualityReport(
        id="pqr_grounded_fixture",
        representation_id="rep_grounded_fixture",
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_grounded_fixture",
        document_id=document_id,
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_grounded_fixture",
        input_blob_digest=hashlib.sha256(text.encode()).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root, node),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, node),
        quality_report=quality_report,
    )


def _ready_manifest_for_staged_test(ledger: FakeGroundedCandidateLedger) -> ContextManifest:
    unit = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "fixture_policy_v1",
            "claim_extraction",
        ),
        ledger,
    ).units[0]
    return build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="fixture_prompt_v1",
            prompt_bytes=b"fixture prompt",
            schema_id="semantic_draft_text_v1",
            schema_bytes=semantic_draft_text_schema_bytes(),
            renderer_version="fixture_renderer_v1",
            evidence_selection_policy_id="direct_prose_evidence_v1",
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest


def _fixture_model_identity() -> ModelIdentitySnapshot:
    return ModelIdentitySnapshot(
        "fixture-model",
        "d" * 64,
        "fixture-runtime",
        FixtureTokenizer.tokenizer_id,
        (ExecutionSetting("temperature", 0),),
    )


def _fixture_execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=_fixture_model_identity(),
        generation_parameters=(ExecutionSetting("temperature", 0),),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=manifest.schema_id,
        schema_digest=manifest.schema_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="semantic_draft_text_v1",
    )


def _hypothesis_manifest_for_staged_test(
    ledger: FakeGroundedCandidateLedger,
    source_segment_policy_id: str = PARAGRAPH_SEGMENT_V1,
) -> ContextManifest:
    unit = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "paragraph_hypothesis_mvp_v1",
            "claim_extraction",
        ),
        ledger,
    ).units[0]
    schema = ParagraphHypothesisTaskSchemaRegistry().resolve("paragraph_hypothesis_text_v1")
    return build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="paragraph_hypothesis_mvp_v3",
            prompt_bytes=b"fixture paragraph hypothesis prompt",
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="paragraph_hypothesis_context_v3",
            evidence_selection_policy_id=PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=source_segment_policy_id,
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest


def _hypothesis_execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return replace(
        _fixture_execution_spec(manifest),
        schema_id="paragraph_hypothesis_text_v1",
        schema_digest=hashlib.sha256(paragraph_hypothesis_text_schema_bytes()).hexdigest(),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="paragraph_hypothesis_text_v1",
    )


def _mention_manifest_for_staged_test(ledger: FakeGroundedCandidateLedger) -> ContextManifest:
    unit = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "paragraph_hypothesis_mvp_v1",
            "claim_extraction",
        ),
        ledger,
    ).units[0]
    schema = OrganizationMentionTaskSchemaRegistry().resolve("organization_mention_text_v1")
    return build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="paragraph_organization_mention_v1",
            prompt_bytes=b"fixture organization mention prompt",
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="paragraph_hypothesis_segment_context_v3",
            evidence_selection_policy_id=PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest


def _mention_execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return replace(
        _fixture_execution_spec(manifest),
        schema_id="organization_mention_text_v1",
        schema_digest=hashlib.sha256(organization_mention_text_schema_bytes()).hexdigest(),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="organization_mention_text_v1",
    )


def _qualification_manifest_for_staged_test(
    ledger: FakeGroundedCandidateLedger,
) -> ContextManifest:
    unit = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "paragraph_hypothesis_mvp_v1",
            "claim_extraction",
        ),
        ledger,
    ).units[0]
    schema = OrganizationQualificationTaskSchemaRegistry().resolve(
        "organization_qualification_text_v1"
    )
    return build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="paragraph_organization_qualification_v1",
            prompt_bytes=b"fixture organization qualification prompt",
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="paragraph_hypothesis_segment_context_v3",
            evidence_selection_policy_id=PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest


def _qualification_execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return replace(
        _fixture_execution_spec(manifest),
        schema_id="organization_qualification_text_v1",
        schema_digest=hashlib.sha256(organization_qualification_text_schema_bytes()).hexdigest(),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="organization_qualification_text_v1",
    )


def _qualification_label_manifest_for_staged_test(
    ledger: FakeGroundedCandidateLedger,
) -> ContextManifest:
    unit = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "paragraph_hypothesis_mvp_v1",
            "claim_extraction",
        ),
        ledger,
    ).units[0]
    schema = OrganizationQualificationLabelTaskSchemaRegistry().resolve(
        "organization_qualification_label_v1"
    )
    return build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="paragraph_organization_qualification_v2",
            prompt_bytes=b"fixture tri-state organization qualification prompt",
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="paragraph_hypothesis_segment_context_v3",
            evidence_selection_policy_id=PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest


def _qualification_label_execution_spec(manifest: ContextManifest) -> ModelExecutionSpec:
    return replace(
        _fixture_execution_spec(manifest),
        schema_id="organization_qualification_label_v1",
        schema_digest=hashlib.sha256(organization_qualification_label_schema_bytes()).hexdigest(),
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=manifest.rendered_input_digest,
        output_contract_version="organization_qualification_label_v1",
    )


def _valid_staged_output() -> bytes:
    return (
        b"outcome: claim\n"
        b"subject: Fixture Organization\n"
        b"relation: supports\n"
        b"object_kind: literal\n"
        b"object: Alpha\n"
    )


def _batch(
    ledger: FakeGroundedCandidateLedger, *, evidence_text: str = TEXT
) -> GroundedCandidateBatchInput:
    return GroundedCandidateBatchInput(
        task_fingerprint="f" * 64,
        source_id=ledger.source.id,
        document_id=ledger.document.id,
        representation_id=ledger.bundle.representation.id,
        model_name="fixture-producer",
        prompt_id="fixture-grounded-task",
        validator_version="fixture-v1",
        submitted_at=NOW,
        organizations=(GroundedOrganizationCandidate("subject", "Fixture Organization"),),
        evidence=(
            GroundedEvidenceCandidate(
                local_id="support",
                text_view_id=ledger.bundle.text_views[0].id,
                start_char=0,
                end_char=len(evidence_text),
                exact_text=evidence_text,
                node_ids=(ledger.bundle.nodes[0].id,),
            ),
        ),
        assertions=(
            GroundedAssertionCandidate(
                local_id="claim",
                subject_organization_local_id="subject",
                evidence_local_id="support",
                relation_label="reported alpha",
                object=GroundedLiteralObject("Alpha"),
            ),
        ),
    )


def test_submit_grounded_candidate_batch_derives_records_and_pending_changes() -> None:
    ledger = FakeGroundedCandidateLedger()

    outcome = submit_grounded_candidate_batch(_batch(ledger), ledger)

    assert len(ledger.evidence_targets) == 1
    assert len(ledger.validation_attempts) == 1
    assert len(ledger.provenance_activities) == 1
    assert len(ledger.proposed_changes) == 2
    evidence = ledger.evidence_targets[outcome.evidence_target_ids_by_local_id["support"]]
    validation = ledger.validation_attempts[
        outcome.validation_attempt_ids_by_evidence_local_id["support"]
    ]
    assertion_change = ledger.proposed_changes[outcome.proposed_change_ids_by_local_id["claim"]]
    assertion_record = assertion_change.proposed_json["record"]
    assertion_links = assertion_change.proposed_json["evidence_links"]
    assert isinstance(assertion_record, dict)
    assert isinstance(assertion_links, list)
    assert validation.evidence_target_id == evidence.id
    assert assertion_record["evidence_target_ids"] == [evidence.id]
    assert assertion_record["object_value"] == "Alpha"
    assert "object_entity_id" not in assertion_record
    assert assertion_links == [
        {
            "evidence_target_id": evidence.id,
            "validation_attempt_id": validation.id,
            "role": "direct_support",
            "polarity": "supports",
            "necessity": "required",
        }
    ]


def test_grounded_candidate_batch_resolves_organization_object_reference() -> None:
    ledger = FakeGroundedCandidateLedger()
    batch = _batch(ledger)
    referenced = GroundedOrganizationCandidate("object", "Object Organization")
    entity_batch = replace(
        batch,
        organizations=(*batch.organizations, referenced),
        assertions=(
            replace(
                batch.assertions[0],
                object=GroundedOrganizationReferenceObject("object"),
            ),
        ),
    )

    outcome = submit_grounded_candidate_batch(entity_batch, ledger)

    assertion_change = ledger.proposed_changes[outcome.proposed_change_ids_by_local_id["claim"]]
    record = assertion_change.proposed_json["record"]
    assert isinstance(record, dict)
    assert record["object_entity_id"] == outcome.organization_ids_by_local_id["object"]
    assert "object_value" not in record


def test_grounded_candidate_batch_rejects_unknown_organization_object_reference() -> None:
    ledger = FakeGroundedCandidateLedger()
    batch = _batch(ledger)
    invalid = replace(
        batch,
        assertions=(
            replace(
                batch.assertions[0],
                object=GroundedOrganizationReferenceObject("missing"),
            ),
        ),
    )

    with pytest.raises(ValueError, match="unknown task-local Organization object"):
        submit_grounded_candidate_batch(invalid, ledger)

    assert ledger.proposed_changes == {}


def test_grounded_candidate_identities_do_not_depend_on_model_local_labels() -> None:
    first_ledger = FakeGroundedCandidateLedger()
    second_ledger = FakeGroundedCandidateLedger()
    first = submit_grounded_candidate_batch(_batch(first_ledger), first_ledger)
    original = _batch(second_ledger)
    renamed = replace(
        original,
        organizations=(GroundedOrganizationCandidate("renamed_subject", "Fixture Organization"),),
        evidence=(replace(original.evidence[0], local_id="renamed_support"),),
        assertions=(
            replace(
                original.assertions[0],
                local_id="renamed_claim",
                subject_organization_local_id="renamed_subject",
                evidence_local_id="renamed_support",
            ),
        ),
    )
    second = submit_grounded_candidate_batch(renamed, second_ledger)

    assert set(first.organization_ids_by_local_id.values()) == set(
        second.organization_ids_by_local_id.values()
    )
    assert set(first.evidence_target_ids_by_local_id.values()) == set(
        second.evidence_target_ids_by_local_id.values()
    )
    assert set(first.proposed_change_ids_by_local_id.values()) == set(
        second.proposed_change_ids_by_local_id.values()
    )


def test_grounded_candidate_context_is_deterministic_and_scoped_to_selected_nodes() -> None:
    ledger = FakeGroundedCandidateLedger()
    context_input = GroundedCandidateContextInput(
        source_id=ledger.source.id,
        document_id=ledger.document.id,
        representation_id=ledger.bundle.representation.id,
        node_ids=(ledger.bundle.nodes[0].id,),
    )

    first = build_grounded_candidate_context(context_input, ledger)
    second = build_grounded_candidate_context(context_input, ledger)

    assert first == second
    assert first.source_id == ledger.source.id
    assert first.document_id == ledger.document.id
    assert first.representation_id == ledger.bundle.representation.id
    assert first.text_views == ledger.bundle.text_views
    assert first.nodes == (ledger.bundle.nodes[0],)
    assert first.source_regions == ()


def test_grounded_candidate_context_rejects_missing_or_duplicate_node_selectors() -> None:
    ledger = FakeGroundedCandidateLedger()
    node_id = ledger.bundle.nodes[0].id

    with pytest.raises(ValueError, match="selectors must be unique"):
        build_grounded_candidate_context(
            GroundedCandidateContextInput(
                ledger.source.id,
                ledger.document.id,
                ledger.bundle.representation.id,
                (node_id, node_id),
            ),
            ledger,
        )
    with pytest.raises(ValueError, match="missing DocumentNode"):
        build_grounded_candidate_context(
            GroundedCandidateContextInput(
                ledger.source.id,
                ledger.document.id,
                ledger.bundle.representation.id,
                ("nod_missing",),
            ),
            ledger,
        )


def test_submit_grounded_candidate_batch_rejects_selector_disagreement_atomically() -> None:
    ledger = FakeGroundedCandidateLedger()

    with pytest.raises(ValueError, match="exact_text does not match"):
        submit_grounded_candidate_batch(_batch(ledger, evidence_text="not present"), ledger)

    assert ledger.evidence_targets == {}
    assert ledger.validation_attempts == {}
    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}


def test_staged_extraction_archives_invalid_task_local_output_without_proposals() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    raw_output = _valid_staged_output() + b"evidence_candidate: evidence_99\n"
    runtime = FakeModelTaskRuntime(raw_output)
    manifest = _ready_manifest_for_staged_test(ledger)
    prompt_bytes = manifest.prompt_bytes

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.model_run.error_message is not None
    assert "fields must match" in outcome.model_run.error_message
    assert outcome.proposed_change_batch is None
    assert outcome.verified_hypotheses == ()
    assert ledger.proposed_changes == {}
    assert archive.outputs[outcome.model_run.id] == raw_output


def test_staged_extraction_derives_whole_node_evidence_from_context_candidate() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _ready_manifest_for_staged_test(ledger)

    assert manifest.evidence_candidates[0].id == "evidence_01"
    assert b"[direct_prose]" in manifest.rendered_input
    assert b"nod_grounded_fixture" not in manifest.rendered_input

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v2",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(_valid_staged_output()),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED, outcome.model_run.error_message
    assert outcome.proposed_change_batch is not None
    assert "assertion_01" in outcome.proposed_change_batch.proposed_change_ids_by_local_id
    evidence_id = outcome.proposed_change_batch.evidence_target_ids_by_local_id["evidence_01"]
    target = ledger.evidence_targets[evidence_id]
    source_node = ledger.bundle.nodes[1]
    assert target.text_view_id == source_node.text_view_id
    assert target.start_char == source_node.start_char
    assert target.end_char == source_node.end_char
    assert target.exact_text == TEXT
    assert target.node_ids == (source_node.id,)


def test_paragraph_hypothesis_segments_reconstruct_the_authoritative_paragraph() -> None:
    segments = paragraph_source_segments(TEXT)

    assert [segment.label for segment in segments] == ["s1", "s2", "s3"]
    assert "".join(segment.exact_text for segment in segments) == TEXT


def test_organization_mention_task_records_mentions_without_proposed_changes() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _mention_manifest_for_staged_test(ledger)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_mention_execution_spec(manifest),
            validator_version="organization_mention_validator_v1",
            task_type="organization_mention_extraction",
        ),
        ledger,
        archive,
        FakeModelTaskRuntime(b"mention: s1 | Fixture Organization\nmention: s1 | Alpha\n"),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationMentionTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert outcome.proposed_change_batch is None
    assert outcome.organization_mentions == (
        OrganizationMention("s1", "Fixture Organization"),
        OrganizationMention("s1", "Alpha"),
    )
    assert outcome.model_run.outcome_metadata == {
        "contract": "organization_mention_text_v1",
        "unique_mention_count": 2,
    }
    assert outcome.extraction_task.task_type == "organization_mention_extraction"
    assert not ledger.proposed_changes


def test_organization_mention_task_rejects_duplicate_mentions() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _mention_manifest_for_staged_test(ledger)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_mention_execution_spec(manifest),
            validator_version="organization_mention_validator_v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(
            b"mention: s1 | Fixture Organization\nmention: s1 | Fixture Organization\n"
        ),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationMentionTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert "repeats a name" in str(outcome.model_run.error_message)
    assert not ledger.proposed_changes


def test_organization_mention_task_accepts_more_than_twelve_distinct_names() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _mention_manifest_for_staged_test(ledger)
    raw_output = "\n".join(f"mention: s1 | Organization {index}" for index in range(1, 15)).encode()

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_mention_execution_spec(manifest),
            validator_version="organization_mention_validator_v1",
            task_type="organization_mention_extraction",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationMentionTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert len(outcome.organization_mentions) == 14


def test_paragraph_hypothesis_batch_publishes_three_segment_grounded_proposals() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _hypothesis_manifest_for_staged_test(ledger)
    raw_output = (
        b"claim: s1 | Fixture Organization | partners with | Alpha\n"
        b"claim: s2 | Fixture Organization | supports | Beta\n"
        b"claim: s3 | Gamma | collaborates with | Delta\n"
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_hypothesis_execution_spec(manifest),
            validator_version="paragraph_hypothesis_validator_v1",
        ),
        ledger,
        archive,
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED, outcome.model_run.error_message
    assert outcome.model_run.task_metadata == {"source_segment_policy_id": "paragraph_segment_v1"}
    assert outcome.model_run.outcome_metadata["unique_claim_count"] == 3
    assert outcome.proposed_change_batch is not None
    assert tuple(item.hypothesis for item in outcome.verified_hypotheses) == (
        AtomicHypothesis("s1", "Fixture Organization", "partners with", "Alpha"),
        AtomicHypothesis("s2", "Fixture Organization", "supports", "Beta"),
        AtomicHypothesis("s3", "Gamma", "collaborates with", "Delta"),
    )
    assert tuple(item.proposed_change_id for item in outcome.verified_hypotheses) == tuple(
        outcome.proposed_change_batch.proposed_change_ids_by_local_id[f"assertion_{index:02d}"]
        for index in range(1, 4)
    )
    assert len(ledger.evidence_targets) == 3
    assert len(ledger.proposed_changes) == 8
    assert {target.exact_text for target in ledger.evidence_targets.values()} == {
        "Fixture Organization partners with Alpha.",
        " Fixture Organization supports Beta.",
        " Gamma collaborates with Delta.",
    }
    assert b"SOURCE SEGMENT: s1" in manifest.rendered_input
    assert b"Alpha.\nSOURCE SEGMENT: s2\n Fixture Organization" in manifest.rendered_input
    assert b"nod_grounded_fixture" not in manifest.rendered_input


def test_paragraph_hypothesis_v3_accepts_collapsed_layout_whitespace() -> None:
    ledger = FakeGroundedCandidateLedger()
    ledger.bundle = _bundle(ledger.document.id, "Fixture  Organization partners with Alpha.")
    manifest = _hypothesis_manifest_for_staged_test(ledger, PARAGRAPH_SEGMENT_V3)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            ledger.source.id,
            ledger.document.id,
            ledger.bundle.representation.id,
            manifest.id,
            manifest.prompt_bytes,
            _hypothesis_execution_spec(manifest),
            "paragraph_hypothesis_validator_v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(b"claim: s1 | Fixture Organization | partners with | Alpha\n"),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert next(iter(ledger.evidence_targets.values())).exact_text == (
        "Fixture  Organization partners with Alpha."
    )


def test_paragraph_hypothesis_v3_rejects_a_generic_organization_description() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _hypothesis_manifest_for_staged_test(ledger, PARAGRAPH_SEGMENT_V3)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            ledger.source.id,
            ledger.document.id,
            ledger.bundle.representation.id,
            manifest.id,
            manifest.prompt_bytes,
            _hypothesis_execution_spec(manifest),
            "paragraph_hypothesis_validator_v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(b"claim: s1 | It | partners with | Alpha\n"),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.proposed_change_batch is None


def test_hypothesis_faithfulness_verifier_publishes_only_accepted_claims() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _hypothesis_manifest_for_staged_test(ledger)
    runtime = SequenceModelTaskRuntime(
        (
            b"claim: s1 | Fixture Organization | partners with | Alpha\n"
            b"claim: s2 | Fixture Organization | supports | Beta\n",
            b"verdict: accept\nreason: direct relationship\n",
            b"verdict: reject\nreason: relation wording is not direct\n",
        )
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_hypothesis_execution_spec(manifest),
            validator_version="paragraph_hypothesis_validator_v1",
            hypothesis_verifier=HypothesisVerifierSpec("faithfulness-v1", b"verifier prompt"),
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert outcome.model_run.outcome_metadata["faithfulness_accepted_claim_count"] == 1
    assert outcome.model_run.outcome_metadata["faithfulness_rejected_claim_count"] == 1
    assert outcome.proposed_change_batch is not None
    assert len(ledger.proposed_changes) == 3
    verifier_runs = [
        run for run in ledger.model_runs.values() if run.task_metadata.get("verifies_model_run_id")
    ]
    assert len(verifier_runs) == 2
    assert all(archive.outputs[run.id] for run in verifier_runs)
    assert runtime.requests[1].task_type == "hypothesis_faithfulness_verification"
    assert b"Fixture Organization | partners with | Alpha" in runtime.requests[1].rendered_input


@pytest.mark.parametrize(
    "verifier_output",
    (
        b"verdict: reject\nreason: relation is inferred\n",
        b"verdict: maybe\nreason: invalid contract\n",
    ),
)
def test_hypothesis_faithfulness_verifier_blocks_rejected_or_invalid_claims(
    verifier_output: bytes,
) -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _hypothesis_manifest_for_staged_test(ledger)
    runtime = SequenceModelTaskRuntime(
        (
            b"claim: s1 | Fixture Organization | partners with | Alpha\n",
            verifier_output,
        )
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_hypothesis_execution_spec(manifest),
            validator_version="paragraph_hypothesis_validator_v1",
            hypothesis_verifier=HypothesisVerifierSpec("faithfulness-v1", b"verifier prompt"),
        ),
        ledger,
        FakeModelOutputArchive(),
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert outcome.proposed_change_batch is None
    assert ledger.proposed_changes == {}


@pytest.mark.parametrize(
    "raw_output",
    (
        b"claim: s4 | Fixture Organization | partners with | Alpha\n",
        b"claim: <s1> | Fixture Organization | partners with | Alpha\n",
        b"claim: s1 | Fixture Organization | partners with | Missing\n",
        b"abstain: no relation\nclaim: s1 | Fixture Organization | partners with | Alpha\n",
        b"\n".join(b"claim: s1 | Fixture Organization | partners with | Alpha" for _ in range(9))
        + b"\n",
    ),
)
def test_paragraph_hypothesis_invalid_batch_creates_no_proposals(raw_output: bytes) -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _hypothesis_manifest_for_staged_test(ledger)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_hypothesis_execution_spec(manifest),
            validator_version="paragraph_hypothesis_validator_v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert ledger.proposed_changes == {}


def test_paragraph_hypothesis_duplicate_claim_is_visible_but_published_once() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _hypothesis_manifest_for_staged_test(ledger)
    raw_output = (
        b"claim: s1 | Fixture Organization | partners with | Alpha\n"
        b"claim: s1 | Fixture Organization | partners with | Alpha\n"
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_hypothesis_execution_spec(manifest),
            validator_version="paragraph_hypothesis_validator_v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert outcome.model_run.outcome_metadata["unique_claim_count"] == 1
    assert outcome.model_run.outcome_metadata["duplicate_claim_lines"] == [
        "claim: s1 | Fixture Organization | partners with | Alpha"
    ]
    assert len(ledger.evidence_targets) == 1


def test_paragraph_hypothesis_reuses_one_evidence_target_for_two_claims_in_one_segment() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _hypothesis_manifest_for_staged_test(ledger)
    raw_output = (
        b"claim: s1 | Fixture Organization | partners with | Alpha\n"
        b"claim: s1 | Fixture Organization | supports | Alpha\n"
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            ledger.source.id,
            ledger.document.id,
            ledger.bundle.representation.id,
            manifest.id,
            manifest.prompt_bytes,
            _hypothesis_execution_spec(manifest),
            "paragraph_hypothesis_validator_v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        ParagraphHypothesisTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert len(ledger.evidence_targets) == 1
    assert outcome.proposed_change_batch is not None


@pytest.mark.parametrize(
    "raw_output",
    (
        b"outcome: claim\nsubject: Fixture Organization\nrelation: supports\n"
        b"object_kind: actor\nobject: Alpha\n",
        b"outcome: claim\nsubject: Fixture Organization\nrelation: supports\nobject: Alpha\n",
        b"outcome: claim\nsubject: Fixture Organization\nrelation: supports\n"
        b"object_kind: literal\n",
    ),
)
def test_staged_extraction_archives_invalid_semantic_draft_without_proposals(
    raw_output: bytes,
) -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _ready_manifest_for_staged_test(ledger)
    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v2",
        ),
        ledger,
        archive,
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.proposed_change_batch is None
    assert archive.outputs[outcome.model_run.id] == raw_output
    assert ledger.proposed_changes == {}


def test_staged_extraction_rejects_model_evidence_selection() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _ready_manifest_for_staged_test(ledger)
    raw_output = _valid_staged_output() + b"evidence_candidate: evidence_01\n"

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v2",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.model_run.error_message is not None
    assert "fields must match" in outcome.model_run.error_message
    assert ledger.proposed_changes == {}


@pytest.mark.parametrize(
    "raw_output",
    (
        b"outcome: claim\nsubject: Unknown Organization\nrelation: supports\n"
        b"object_kind: literal\nobject: Alpha\n",
        b"outcome: claim\nsubject: Fixture Organization\nrelation: supports\n"
        b"object_kind: literal\nobject: Unknown Value\n",
    ),
)
def test_staged_extraction_rejects_an_ungrounded_semantic_draft(raw_output: bytes) -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _ready_manifest_for_staged_test(ledger)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v2",
        ),
        ledger,
        archive,
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.proposed_change_batch is None
    assert archive.outputs[outcome.model_run.id] == raw_output
    assert ledger.proposed_changes == {}


def test_staged_extraction_persists_exact_abstention_reason_on_model_run() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _ready_manifest_for_staged_test(ledger)
    raw_output = b"outcome: abstain\nreason: insufficient task-local evidence\n"

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        archive,
        FakeModelTaskRuntime(raw_output),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.ABSTAINED
    assert outcome.model_run.abstention_reason == "insufficient task-local evidence"
    assert ledger.model_runs[outcome.model_run.id] == outcome.model_run
    assert archive.outputs[outcome.model_run.id] == raw_output
    assert outcome.proposed_change_batch is None
    with pytest.raises(ValueError, match="Only an abstained ModelRun"):
        ModelRun.model_validate(
            {**outcome.model_run.model_dump(), "status": ModelRunStatus.SUCCEEDED}
        )
    with pytest.raises(ValueError, match="requires an abstention reason"):
        ModelRun.model_validate({**outcome.model_run.model_dump(), "abstention_reason": None})


def test_staged_extraction_records_application_owned_execution_timing() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _ready_manifest_for_staged_test(ledger)
    completed_at = NOW + timedelta(seconds=2)
    clock = FixedModelRunClock((NOW, completed_at), (100.0, 102.25))
    raw_output = b"outcome: abstain\nreason: insufficient task-local evidence\n"

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        archive,
        FakeModelTaskRuntime(raw_output, first_response_event_milliseconds=125),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
        clock,
    )

    assert outcome.model_run.started_at == NOW
    assert outcome.model_run.completed_at == completed_at
    assert outcome.model_run.execution_diagnostics == {
        "elapsed_milliseconds": 2250,
        "deadline_milliseconds": 300000,
        "first_response_event_milliseconds": 125,
    }
    with pytest.raises(ValueError, match="execution diagnostics"):
        ModelRun.model_validate(
            {
                **outcome.model_run.model_dump(),
                "execution_diagnostics": {"elapsed_milliseconds": 2250},
            }
        )


def test_staged_extraction_rejects_a_mismatched_execution_receipt_after_archiving_output() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _ready_manifest_for_staged_test(ledger)
    runtime = FakeModelTaskRuntime(
        _valid_staged_output(),
        receipt=ModelExecutionReceipt(
            model_identity_digest="0" * 64,
            generation_parameters_digest="0" * 64,
            rendered_input_digest="0" * 64,
            input_token_count=1,
            output_token_count=1,
        ),
    )
    extraction_input = BoundedExtractionInput(
        source_id=ledger.source.id,
        document_id=ledger.document.id,
        representation_id=ledger.bundle.representation.id,
        context_manifest_id=manifest.id,
        prompt_bytes=manifest.prompt_bytes,
        execution_spec=_fixture_execution_spec(manifest),
        validator_version="fixture-validator-v1",
    )

    outcome = run_bounded_extraction(
        extraction_input,
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.model_run.error_message is not None
    assert "receipt identity" in outcome.model_run.error_message
    assert archive.outputs[outcome.model_run.id] == _valid_staged_output()
    assert ledger.proposed_changes == {}


def test_staged_extraction_rejects_and_persists_a_truncated_input_receipt() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    manifest = _ready_manifest_for_staged_test(ledger)
    execution_spec = _fixture_execution_spec(manifest)
    receipt = ModelExecutionReceipt(
        model_identity_digest=model_identity_snapshot_digest(execution_spec.model_identity),
        generation_parameters_digest=generation_parameters_digest(
            execution_spec.generation_parameters
        ),
        rendered_input_digest=execution_spec.rendered_input_digest,
        input_token_count=manifest.input_token_count - 1,
        output_token_count=9,
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=execution_spec,
            validator_version="fixture-validator-v1",
        ),
        ledger,
        archive,
        FakeModelTaskRuntime(_valid_staged_output(), receipt=receipt),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.model_run.error_message is not None
    assert "input token count" in outcome.model_run.error_message
    assert outcome.model_run.execution_receipt == {
        "model_identity_digest": receipt.model_identity_digest,
        "generation_parameters_digest": receipt.generation_parameters_digest,
        "rendered_input_digest": receipt.rendered_input_digest,
        "input_token_count": manifest.input_token_count - 1,
        "output_token_count": 9,
    }
    assert archive.outputs[outcome.model_run.id] == _valid_staged_output()
    assert ledger.proposed_changes == {}


def test_model_execution_spec_has_no_loose_or_colliding_settings() -> None:
    caller_settings = {"temperature": 0}
    immutable_identity = ModelIdentitySnapshot(
        "fixture-model",
        "d" * 64,
        "fixture-runtime",
        FixtureTokenizer.tokenizer_id,
        tuple(ExecutionSetting(key, value) for key, value in sorted(caller_settings.items())),
    )
    caller_settings["temperature"] = 1
    assert immutable_identity.determinism_settings == (ExecutionSetting("temperature", 0),)
    with pytest.raises(ValueError, match="reserved model identity field"):
        ModelIdentitySnapshot(
            "fixture-model",
            "d" * 64,
            "fixture-runtime",
            FixtureTokenizer.tokenizer_id,
            (ExecutionSetting("runtime", "shadowed"),),
        )
    with pytest.raises(ValueError, match="weights digest"):
        ModelIdentitySnapshot(
            "fixture-model", "not-a-digest", "fixture-runtime", FixtureTokenizer.tokenizer_id
        )


@pytest.mark.parametrize(
    ("failure_boundary", "expected_status"),
    (
        ("runtime", ModelRunStatus.RUNTIME_FAILED),
        ("archive", ModelRunStatus.OUTPUT_ARCHIVE_FAILED),
    ),
)
def test_staged_extraction_classifies_runtime_and_archive_failures_truthfully(
    failure_boundary: str,
    expected_status: ModelRunStatus,
) -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _ready_manifest_for_staged_test(ledger)

    class FailingArchive(FakeModelOutputArchive):
        def put_model_run_output(
            self, model_run_id: str, payload: bytes, expected_digest: str
        ) -> object:
            raise OSError("archive unavailable")

    class FailingRuntime(FakeModelTaskRuntime):
        def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
            raise RuntimeError("runtime unavailable")

    runtime = (
        FailingRuntime(_valid_staged_output())
        if failure_boundary == "runtime"
        else FakeModelTaskRuntime(_valid_staged_output())
    )
    archive = FailingArchive() if failure_boundary == "archive" else FakeModelOutputArchive()
    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is expected_status
    assert outcome.model_run.raw_output_artifact_id is None
    assert outcome.proposed_change_batch is None
    with pytest.raises(ValueError, match="ExecutionSetting records"):
        ModelExecutionSpec(
            "fixture-model",
            _fixture_model_identity(),
            cast(tuple[ExecutionSetting, ...], ({"temperature": 0},)),
            "fixture_prompt_v1",
            "a" * 64,
            "semantic_draft_text_v1",
            "b" * 64,
            "ctx_fixture",
            "c" * 64,
            "d" * 64,
            "semantic_draft_text_v1",
        )


def test_staged_extraction_records_task_deadline_without_partial_proposals() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _ready_manifest_for_staged_test(ledger)

    class DeadlineRuntime(FakeModelTaskRuntime):
        def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
            raise ModelRuntimeDeadlineExceeded(
                "Model task exceeded its configured wall-clock deadline."
            )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        DeadlineRuntime(_valid_staged_output()),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.RUNTIME_FAILED
    assert (
        outcome.model_run.error_message == "Model task exceeded its configured wall-clock deadline."
    )
    assert outcome.model_run.raw_output_artifact_id is None
    assert outcome.proposed_change_batch is None
    assert ledger.proposed_changes == {}


def test_staged_extraction_rejects_unpinned_prompt_before_model_invocation() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    runtime = FakeModelTaskRuntime(b"{}")
    manifest = _ready_manifest_for_staged_test(ledger)

    with pytest.raises(ValueError, match="prompt bytes"):
        run_bounded_extraction(
            BoundedExtractionInput(
                source_id=ledger.source.id,
                document_id=ledger.document.id,
                representation_id=ledger.bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"tampered prompt",
                execution_spec=_fixture_execution_spec(manifest),
                validator_version="fixture-validator-v1",
            ),
            ledger,
            archive,
            runtime,
            Uuid4ModelRunIdFactory(),
            FixtureTokenizer(),
            SemanticDraftTaskSchemaRegistry(),
        )

    assert runtime.requests == []
    assert ledger.extraction_tasks == {}
    assert ledger.model_runs == {}


def test_staged_extraction_rejects_runtime_identity_mismatch_before_invocation() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    runtime = FakeModelTaskRuntime(b"{}")
    manifest = _ready_manifest_for_staged_test(ledger)
    extraction_input = BoundedExtractionInput(
        source_id=ledger.source.id,
        document_id=ledger.document.id,
        representation_id=ledger.bundle.representation.id,
        context_manifest_id=manifest.id,
        prompt_bytes=manifest.prompt_bytes,
        execution_spec=_fixture_execution_spec(manifest),
        validator_version="fixture-validator-v1",
    )
    mismatches = (
        (
            replace(
                extraction_input,
                execution_spec=replace(
                    extraction_input.execution_spec, model_profile_id="wrong-model"
                ),
            ),
            "ContextManifest profile",
        ),
        (
            replace(
                extraction_input,
                execution_spec=replace(
                    extraction_input.execution_spec,
                    model_identity=replace(
                        extraction_input.execution_spec.model_identity,
                        tokenizer_id="wrong-tokenizer",
                    ),
                ),
            ),
            "tokenizer",
        ),
    )

    for invalid_input, message in mismatches:
        with pytest.raises(ValueError, match=message):
            run_bounded_extraction(
                invalid_input,
                ledger,
                archive,
                runtime,
                Uuid4ModelRunIdFactory(),
                FixtureTokenizer(),
                SemanticDraftTaskSchemaRegistry(),
            )

    with pytest.raises(ValueError, match="runtime configured identity"):
        run_bounded_extraction(
            extraction_input,
            ledger,
            archive,
            FakeModelTaskRuntime(
                b"{}",
                configured_identity=replace(_fixture_model_identity(), runtime="wrong-runtime"),
            ),
            Uuid4ModelRunIdFactory(),
            FixtureTokenizer(),
            SemanticDraftTaskSchemaRegistry(),
        )

    assert runtime.requests == []
    assert ledger.extraction_tasks == {}
    assert ledger.model_runs == {}


def test_staged_extraction_rejects_schema_bytes_that_differ_from_the_validator() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _ready_manifest_for_staged_test(ledger)
    archive = FakeModelOutputArchive()
    runtime = FakeModelTaskRuntime(b"{}")

    class MismatchedSchemaRegistry:
        def resolve(self, schema_id: str) -> PinnedTaskSchema:
            schema = SemanticDraftTaskSchemaRegistry().resolve(schema_id)
            return replace(schema, canonical_schema_bytes=b'{"type":"null"}')

    with pytest.raises(ValueError, match="schema bytes"):
        run_bounded_extraction(
            BoundedExtractionInput(
                source_id=ledger.source.id,
                document_id=ledger.document.id,
                representation_id=ledger.bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"fixture prompt",
                execution_spec=_fixture_execution_spec(manifest),
                validator_version="fixture-validator-v1",
            ),
            ledger,
            archive,
            runtime,
            Uuid4ModelRunIdFactory(),
            FixtureTokenizer(),
            MismatchedSchemaRegistry(),
        )

    assert runtime.requests == []
    assert ledger.extraction_tasks == {}
    assert ledger.model_runs == {}


def test_staged_extraction_schema_forbids_hidden_global_evidence_coordinates() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _ready_manifest_for_staged_test(ledger)
    archive = FakeModelOutputArchive()
    runtime = FakeModelTaskRuntime(_valid_staged_output() + b"node_id: nod_grounded_fixture\n")

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=b"fixture prompt",
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.proposed_change_batch is None
    assert ledger.proposed_changes == {}


def test_successful_model_run_and_candidate_batch_share_one_atomic_boundary() -> None:
    ledger = FakeGroundedCandidateLedger()
    ledger.fail_successful_commit = True
    manifest = _ready_manifest_for_staged_test(ledger)
    archive = FakeModelOutputArchive()
    runtime = FakeModelTaskRuntime(_valid_staged_output())

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=b"fixture prompt",
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.PUBLISH_FAILED
    assert outcome.proposed_change_batch is None
    assert ledger.evidence_targets == {}
    assert ledger.validation_attempts == {}
    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}
    assert len(ledger.model_runs) == 1


def test_organization_qualification_records_semantic_judgment_without_changes() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _qualification_manifest_for_staged_test(ledger)
    runtime = FakeModelTaskRuntime(b"organization: Fixture Organization\n")

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_qualification_execution_spec(manifest),
            validator_version="organization_qualification_validator_v1",
            task_type="organization_qualification",
        ),
        ledger,
        FakeModelOutputArchive(),
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationQualificationTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert outcome.organization_qualification == OrganizationQualification("Fixture Organization")
    assert outcome.proposed_change_batch is None
    assert runtime.requests[0].task_type == "organization_qualification"
    assert not ledger.proposed_changes


def test_organization_qualification_records_rejection_and_malformed_output() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _qualification_manifest_for_staged_test(ledger)
    extraction_input = BoundedExtractionInput(
        source_id=ledger.source.id,
        document_id=ledger.document.id,
        representation_id=ledger.bundle.representation.id,
        context_manifest_id=manifest.id,
        prompt_bytes=manifest.prompt_bytes,
        execution_spec=_qualification_execution_spec(manifest),
        validator_version="organization_qualification_validator_v1",
        task_type="organization_qualification",
    )

    rejected = run_bounded_extraction(
        extraction_input,
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(b"reject: not an organization\n"),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationQualificationTaskSchemaRegistry(),
    )
    invalid = run_bounded_extraction(
        extraction_input,
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(b"organization: elsewhere\nreason: guessed\n"),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationQualificationTaskSchemaRegistry(),
    )

    assert rejected.model_run.status is ModelRunStatus.ABSTAINED
    assert rejected.model_run.outcome_metadata["contract"] == ("organization_qualification_text_v1")
    assert invalid.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert not ledger.proposed_changes


@pytest.mark.parametrize(
    ("raw_output", "expected"),
    [
        (b"organization", OrganizationQualificationJudgment.ORGANIZATION),
        (b"not_organization", OrganizationQualificationJudgment.NOT_ORGANIZATION),
        (b"ambiguous", OrganizationQualificationJudgment.AMBIGUOUS),
    ],
)
def test_organization_qualification_label_records_exact_tri_state_model_run(
    raw_output: bytes,
    expected: OrganizationQualificationJudgment,
) -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _qualification_label_manifest_for_staged_test(ledger)
    runtime = FakeModelTaskRuntime(raw_output)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_qualification_label_execution_spec(manifest),
            validator_version="organization_qualification_label_validator_v1",
            task_type="organization_qualification_label",
        ),
        ledger,
        FakeModelOutputArchive(),
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationQualificationLabelTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert outcome.organization_qualification_judgment is expected
    assert outcome.model_run.outcome_metadata == {
        "contract": "organization_qualification_label_v1",
        "judgment": expected.value,
    }
    assert runtime.requests[0].rendered_input == manifest.rendered_input
    assert runtime.requests[0].task_type == "organization_qualification_label"
    assert not ledger.proposed_changes


def test_organization_qualification_label_rejects_nonliteral_output() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _qualification_label_manifest_for_staged_test(ledger)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_qualification_label_execution_spec(manifest),
            validator_version="organization_qualification_label_validator_v1",
            task_type="organization_qualification_label",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(b"organization\n"),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        OrganizationQualificationLabelTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.organization_qualification_judgment is None
    assert not ledger.proposed_changes


def test_retries_preserve_distinct_model_runs_for_one_task() -> None:
    ledger = FakeGroundedCandidateLedger()
    manifest = _ready_manifest_for_staged_test(ledger)
    archive = FakeModelOutputArchive()
    runtime = FakeModelTaskRuntime(_valid_staged_output())
    extraction_input = BoundedExtractionInput(
        source_id=ledger.source.id,
        document_id=ledger.document.id,
        representation_id=ledger.bundle.representation.id,
        context_manifest_id=manifest.id,
        prompt_bytes=b"fixture prompt",
        execution_spec=_fixture_execution_spec(manifest),
        validator_version="fixture-validator-v1",
    )
    first = run_bounded_extraction(
        extraction_input,
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )
    second = run_bounded_extraction(
        extraction_input,
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )

    assert first.extraction_task.id == second.extraction_task.id
    assert first.model_run.id != second.model_run.id
    assert {run.id for run in ledger.model_runs.values()} == {
        first.model_run.id,
        second.model_run.id,
    }
    assert archive.outputs[first.model_run.id] == _valid_staged_output()
    assert archive.outputs[second.model_run.id] == _valid_staged_output()
    execution_spec_digest = model_execution_spec_digest(extraction_input.execution_spec)
    assert runtime.requests[0].execution_spec == extraction_input.execution_spec
    assert (
        runtime.requests[0].rendered_input_digest
        == extraction_input.execution_spec.rendered_input_digest
    )
    assert first.extraction_task.execution_spec_digest == execution_spec_digest
    assert first.model_run.execution_spec_digest == execution_spec_digest
    assert first.model_run.execution_receipt is not None
    assert first.model_run.execution_receipt["input_token_count"] == manifest.input_token_count


def test_frozen_analysis_plan_requires_every_unit_to_reconcile_before_completion() -> None:
    ledger = FakeGroundedCandidateLedger()
    plan = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "fixture_coverage_policy_v1",
            "claim_extraction",
        ),
        ledger,
    )
    frozen = freeze_analysis_plan(plan, ledger)
    assert load_frozen_analysis_plan(frozen.id, ledger) == frozen

    with pytest.raises(ValueError, match="coverage policy identity is unknown"):
        start_analysis_run(
            AnalysisRunInput(
                document_id=ledger.document.id,
                frozen_plan_id=frozen.id,
                coverage_policy_id="undeclared_coverage_policy_v1",
                started_at=NOW,
                items=(
                    AnalysisRunItemInput(
                        analysis_unit_id=plan.units[0].id,
                        task_type="claim_extraction",
                        input_fingerprint=hashlib.sha256(b"unknown-policy").hexdigest(),
                        expected_manifest_id=None,
                    ),
                ),
            ),
            ledger,
        )

    incomplete_run = start_analysis_run(
        AnalysisRunInput(
            document_id=ledger.document.id,
            frozen_plan_id=frozen.id,
            coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
            started_at=NOW,
            items=(
                AnalysisRunItemInput(
                    analysis_unit_id=plan.units[0].id,
                    task_type="claim_extraction",
                    input_fingerprint=hashlib.sha256(b"no-task-yet").hexdigest(),
                    expected_manifest_id=None,
                ),
            ),
        ),
        ledger,
    )
    incomplete = build_coverage_report(incomplete_run.id, ledger)
    assert incomplete_run.state is AnalysisRunState.RUNNING
    assert incomplete_run.completed_at is None
    assert (
        ledger.list_planned_items_for_analysis_run(incomplete_run.id)[0].expected_manifest_id
        is None
    )
    assert incomplete.state is AnalysisCoverageState.INCOMPLETE
    assert incomplete.integrity_failure_reasons == ()
    assert incomplete.coverage_records[0].terminal_status is CoverageTerminalStatus.UNREPORTED
    assert incomplete.coverage_records[0].blocking_reason == "missing_manifest"
    assert incomplete.coverage_records[0].policy_decision is (
        CoveragePolicyDecision.SELECTION_NOT_APPLICABLE
    )

    manifest = build_context_manifest(
        ContextManifestInput(
            analysis_unit=plan.units[0],
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="fixture_prompt_v1",
            prompt_bytes=b"fixture prompt",
            schema_id="semantic_draft_text_v1",
            schema_bytes=semantic_draft_text_schema_bytes(),
            renderer_version="fixture_renderer_v1",
            evidence_selection_policy_id="focus_node_evidence_v1",
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest
    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(_valid_staged_output()),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
        FixedModelRunClock((NOW, NOW), (0.0, 0.0)),
    )
    assert outcome.proposed_change_batch is not None

    complete_run = start_analysis_run(
        AnalysisRunInput(
            document_id=ledger.document.id,
            frozen_plan_id=frozen.id,
            coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
            started_at=NOW,
            items=(
                AnalysisRunItemInput(
                    analysis_unit_id=plan.units[0].id,
                    task_type=outcome.extraction_task.task_type,
                    input_fingerprint=outcome.extraction_task.task_fingerprint,
                    expected_manifest_id=manifest.id,
                ),
            ),
        ),
        ledger,
    )
    record_analysis_item_attempt(
        analysis_run_id=complete_run.id,
        analysis_unit_id=plan.units[0].id,
        model_run_id=outcome.model_run.id,
        ledger_repository=ledger,
    )
    assert (
        ledger.list_planned_items_for_analysis_run(complete_run.id)[0].expected_manifest_id
        == manifest.id
    )
    complete = build_coverage_report(complete_run.id, ledger)
    assert complete.state is AnalysisCoverageState.COMPLETE
    assert complete.coverage_policy_id == LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID
    assert complete.integrity_failure_reasons == ()
    assert complete.coverage_records[0].terminal_status is (
        CoverageTerminalStatus.PROCESSED_WITH_PROPOSALS
    )
    assert complete.coverage_records[0].selected_proposal_ids == tuple(
        sorted(outcome.proposed_change_batch.proposed_change_ids_by_local_id.values())
    )
    assert complete.coverage_records[0].selected_model_run_id == outcome.model_run.id
    assert complete.coverage_records[0].all_model_run_ids == (outcome.model_run.id,)
    assert complete.coverage_records[0].policy_decision is (
        CoveragePolicyDecision.SELECTED_LATEST_COMPLETED_VALID_ATTEMPT
    )
    assert complete.orphan_model_run_ids == ()

    historical_proposal_ids = complete.coverage_records[0].selected_proposal_ids
    no_proposal_run = ModelRun.model_validate(
        {
            **outcome.model_run.model_dump(),
            "id": "mrn_coverage_no_proposals",
            "started_at": NOW + timedelta(minutes=1),
            "completed_at": NOW + timedelta(minutes=1),
        }
    )
    ledger.save_model_run(no_proposal_run)
    ledger.model_run_proposed_changes[no_proposal_run.id] = ()
    record_analysis_item_attempt(
        analysis_run_id=complete_run.id,
        analysis_unit_id=plan.units[0].id,
        model_run_id=no_proposal_run.id,
        ledger_repository=ledger,
    )
    no_proposal_coverage = build_coverage_report(complete_run.id, ledger)
    assert no_proposal_coverage.coverage_records[0].terminal_status is (
        CoverageTerminalStatus.PROCESSED_NO_PROPOSALS
    )
    assert no_proposal_coverage.coverage_records[0].selected_model_run_id == no_proposal_run.id
    assert no_proposal_coverage.coverage_records[0].selected_proposal_ids == ()
    assert no_proposal_coverage.coverage_records[0].all_model_run_ids == tuple(
        sorted((outcome.model_run.id, no_proposal_run.id))
    )
    assert (
        tuple(
            proposal.id
            for proposal in ledger.list_proposed_changes_for_model_run(outcome.model_run.id)
        )
        == historical_proposal_ids
    )

    abstained_run = ModelRun.model_validate(
        {
            **outcome.model_run.model_dump(),
            "id": "mrn_coverage_abstained",
            "status": ModelRunStatus.ABSTAINED,
            "abstention_reason": "insufficient task-local evidence",
            "started_at": NOW + timedelta(minutes=2),
            "completed_at": NOW + timedelta(minutes=2),
        }
    )
    ledger.save_model_run(abstained_run)
    ledger.model_run_proposed_changes[abstained_run.id] = ()
    record_analysis_item_attempt(
        analysis_run_id=complete_run.id,
        analysis_unit_id=plan.units[0].id,
        model_run_id=abstained_run.id,
        ledger_repository=ledger,
    )
    abstained_coverage = build_coverage_report(complete_run.id, ledger)
    assert (
        abstained_coverage.coverage_records[0].terminal_status is CoverageTerminalStatus.ABSTAINED
    )
    assert abstained_coverage.coverage_records[0].selected_model_run_id == abstained_run.id
    assert abstained_coverage.coverage_records[0].selected_proposal_ids == ()
    assert (
        abstained_coverage.coverage_records[0].abstention_reason
        == "insufficient task-local evidence"
    )

    publish_failed_run = ModelRun.model_validate(
        {
            **outcome.model_run.model_dump(),
            "id": "mrn_coverage_publish_failed",
            "status": ModelRunStatus.PUBLISH_FAILED,
            "abstention_reason": None,
            "error_code": "InjectedPublicationFailure",
            "error_message": "injected publication failure",
            "started_at": NOW + timedelta(minutes=3),
            "completed_at": NOW + timedelta(minutes=3),
        }
    )
    ledger.save_model_run(publish_failed_run)
    ledger.model_run_proposed_changes[publish_failed_run.id] = ()
    record_analysis_item_attempt(
        analysis_run_id=complete_run.id,
        analysis_unit_id=plan.units[0].id,
        model_run_id=publish_failed_run.id,
        ledger_repository=ledger,
    )
    failed_coverage = build_coverage_report(complete_run.id, ledger)
    assert (
        failed_coverage.coverage_records[0].terminal_status is CoverageTerminalStatus.MODEL_FAILED
    )
    assert failed_coverage.coverage_records[0].selected_model_run_id == publish_failed_run.id
    assert failed_coverage.coverage_records[0].selected_proposal_ids == ()
    assert (
        failed_coverage.coverage_records[0].blocking_reason == ModelRunStatus.PUBLISH_FAILED.value
    )
    assert build_coverage_report(incomplete_run.id, ledger) == incomplete


def _complete_coverage_fixture() -> tuple[
    FakeGroundedCandidateLedger, AnalysisRun, ContextManifest, ModelRun
]:
    ledger = FakeGroundedCandidateLedger()
    plan = plan_analysis_units(
        AnalysisUnitPlanningInput(
            ledger.bundle.representation.id,
            "fixture_integrity_policy_v1",
            "claim_extraction",
        ),
        ledger,
    )
    frozen = freeze_analysis_plan(plan, ledger)
    manifest = build_context_manifest(
        ContextManifestInput(
            analysis_unit=plan.units[0],
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="fixture_prompt_v1",
            prompt_bytes=b"fixture prompt",
            schema_id="semantic_draft_text_v1",
            schema_bytes=semantic_draft_text_schema_bytes(),
            renderer_version="fixture_renderer_v1",
            evidence_selection_policy_id="focus_node_evidence_v1",
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest
    extraction = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=manifest.prompt_bytes,
            execution_spec=_fixture_execution_spec(manifest),
            validator_version="fixture-validator-v1",
        ),
        ledger,
        FakeModelOutputArchive(),
        FakeModelTaskRuntime(_valid_staged_output()),
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        SemanticDraftTaskSchemaRegistry(),
    )
    run = start_analysis_run(
        AnalysisRunInput(
            document_id=ledger.document.id,
            frozen_plan_id=frozen.id,
            coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
            started_at=NOW,
            items=(
                AnalysisRunItemInput(
                    analysis_unit_id=plan.units[0].id,
                    task_type=extraction.extraction_task.task_type,
                    input_fingerprint=extraction.extraction_task.task_fingerprint,
                    expected_manifest_id=manifest.id,
                ),
            ),
        ),
        ledger,
    )
    record_analysis_item_attempt(
        analysis_run_id=run.id,
        analysis_unit_id=plan.units[0].id,
        model_run_id=extraction.model_run.id,
        ledger_repository=ledger,
    )
    return ledger, run, manifest, extraction.model_run


def test_coverage_reports_multiple_manifests_as_integrity_failure() -> None:
    ledger, run, manifest, _ = _complete_coverage_fixture()
    ledger.context_manifest_query_extras = (ledger.manifests[manifest.id],)

    report = build_coverage_report(run.id, ledger)

    assert report.state is AnalysisCoverageState.FAILED
    assert report.integrity_failure_reasons == (CoverageIntegrityFailureReason.MULTIPLE_MANIFESTS,)
    assert report.coverage_records[0].blocking_reason == "multiple_manifests"


def test_coverage_reports_unexpected_manifest_as_integrity_failure() -> None:
    ledger, run, manifest, _ = _complete_coverage_fixture()
    ledger.context_manifest_query_extras = (
        ledger.manifests[manifest.id].model_copy(update={"id": "ctx_unexpected"}),
    )

    report = build_coverage_report(run.id, ledger)

    assert report.state is AnalysisCoverageState.FAILED
    assert report.integrity_failure_reasons == (CoverageIntegrityFailureReason.UNEXPECTED_MANIFEST,)
    assert report.coverage_records[0].terminal_status is (
        CoverageTerminalStatus.PROCESSED_WITH_PROPOSALS
    )


def test_coverage_reports_missing_selected_run_as_integrity_failure() -> None:
    ledger, run, _, model_run = _complete_coverage_fixture()
    del ledger.model_runs[model_run.id]

    report = build_coverage_report(run.id, ledger)

    assert report.state is AnalysisCoverageState.FAILED
    assert report.integrity_failure_reasons == (
        CoverageIntegrityFailureReason.MISSING_SELECTED_RUN,
    )
    assert report.coverage_records[0].blocking_reason == "missing_selected_run"


def test_coverage_reports_run_task_mismatch_as_integrity_failure() -> None:
    ledger, run, _, model_run = _complete_coverage_fixture()
    ledger.model_runs[model_run.id] = model_run.model_copy(
        update={"extraction_task_id": "ext_wrong_task"}
    )

    report = build_coverage_report(run.id, ledger)

    assert report.state is AnalysisCoverageState.FAILED
    assert report.integrity_failure_reasons == (CoverageIntegrityFailureReason.RUN_TASK_MISMATCH,)
    assert report.coverage_records[0].blocking_reason == "run_task_mismatch"


def test_coverage_reports_proposal_run_mismatch_without_exposing_proposals() -> None:
    ledger, run, _, model_run = _complete_coverage_fixture()
    proposal_id = ledger.model_run_proposed_changes[model_run.id][0]
    provenance_id = ledger.proposed_changes[proposal_id].provenance_activity_id
    assert provenance_id is not None
    provenance = ledger.provenance_activities[provenance_id]
    ledger.provenance_activities[provenance_id] = provenance.model_copy(
        update={
            "input_ids": tuple(value for value in provenance.input_ids if value != model_run.id)
        }
    )

    report = build_coverage_report(run.id, ledger)

    assert report.state is AnalysisCoverageState.FAILED
    assert report.integrity_failure_reasons == (
        CoverageIntegrityFailureReason.PROPOSAL_RUN_MISMATCH,
    )
    assert report.coverage_records[0].blocking_reason == "proposal_run_mismatch"
    assert report.coverage_records[0].selected_proposal_ids == ()


def test_coverage_reports_split_cycle_as_integrity_failure() -> None:
    ledger, original_run, manifest, _ = _complete_coverage_fixture()
    original_item = ledger.list_planned_items_for_analysis_run(original_run.id)[0]
    cyclic_template = replace(
        manifest,
        status=ContextManifestStatus.SPLIT,
        selected_candidates=(),
        evidence_candidates=(),
        rendered_segments=(),
        rendered_input=b"",
        rendered_input_digest=hashlib.sha256(b"").hexdigest(),
        input_token_count=0,
        split_strategy_id="fixture_cycle_v1",
        child_analysis_unit_ids=(manifest.analysis_unit_id,),
    )
    cyclic_digest = context_manifest_digest(cyclic_template)
    cyclic_manifest = replace(
        cyclic_template,
        id=f"ctx_{cyclic_digest[:24]}",
        manifest_digest=cyclic_digest,
    )
    cyclic_payload = deepcopy(ledger.manifests[manifest.id].payload)
    integrity = cyclic_payload["integrity"]
    assert isinstance(integrity, dict)
    integrity["status"] = ContextManifestStatus.SPLIT.value
    integrity["selected"] = []
    integrity["evidence_candidates"] = []
    integrity["segments"] = []
    integrity["rendered_input_digest"] = hashlib.sha256(b"").hexdigest()
    integrity["input_token_count"] = 0
    integrity["split_strategy_id"] = "fixture_cycle_v1"
    integrity["child_analysis_unit_ids"] = [manifest.analysis_unit_id]
    cyclic_payload["rendered_input_base64"] = ""
    ledger.manifests[cyclic_manifest.id] = ContextManifestArtifact(
        id=cyclic_manifest.id,
        analysis_unit_id=cyclic_manifest.analysis_unit_id,
        representation_id=cyclic_manifest.representation_id,
        manifest_digest=cyclic_manifest.manifest_digest,
        payload=cyclic_payload,
    )
    cyclic_run = start_analysis_run(
        AnalysisRunInput(
            document_id=ledger.document.id,
            frozen_plan_id=original_run.frozen_analysis_plan_id,
            coverage_policy_id=LATEST_COMPLETED_VALID_ATTEMPT_POLICY_ID,
            started_at=NOW,
            items=(
                AnalysisRunItemInput(
                    analysis_unit_id=original_item.analysis_unit_id,
                    task_type=original_item.task_type,
                    input_fingerprint=original_item.input_fingerprint,
                    expected_manifest_id=cyclic_manifest.id,
                ),
            ),
        ),
        ledger,
    )

    report = build_coverage_report(cyclic_run.id, ledger)

    assert report.state is AnalysisCoverageState.FAILED
    assert report.integrity_failure_reasons == (CoverageIntegrityFailureReason.SPLIT_CYCLE,)
    assert report.coverage_records[0].blocking_reason == "split_cycle"
