import hashlib
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    AnalysisUnit,
    BoundedExtractionInput,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedCandidateContextInput,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    ModelIdentity,
    ModelTaskRequest,
    ModelTaskResponse,
    PinnedTaskSchema,
    StagedClaimTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    build_context_manifest,
    build_grounded_candidate_context,
    context_manifest_digest,
    persist_analysis_unit,
    persist_context_manifest,
    run_bounded_extraction,
    staged_claim_output_schema_bytes,
    submit_grounded_candidate_batch,
)
from kotekomi_domain import (
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
TEXT = "Alpha supports the accepted assertion."


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
        self.manifests: dict[str, ContextManifestArtifact] = {}
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.fail_successful_commit = False

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

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

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.manifests.get(record_id)

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)


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
    def __init__(self, raw_output: bytes) -> None:
        self.raw_output = raw_output
        self.requests: list[ModelTaskRequest] = []

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        return ModelTaskResponse(self.raw_output)


class FixtureTokenizer:
    tokenizer_id = "fixture_tokenizer_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


def _bundle(document_id: str) -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_grounded_fixture",
        representation_id="rep_grounded_fixture",
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )
    node = DocumentNode(
        id="nod_grounded_fixture",
        representation_id="rep_grounded_fixture",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(TEXT),
    )
    quality_report = ParseQualityReport(
        id="pqr_grounded_fixture",
        representation_id="rep_grounded_fixture",
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_grounded_fixture",
        document_id=document_id,
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_grounded_fixture",
        input_blob_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(node,),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(node,),
        quality_report=quality_report,
    )


def _ready_manifest_for_staged_test(ledger: FakeGroundedCandidateLedger) -> ContextManifest:
    unit = AnalysisUnit(
        id="anu_staged_ready_fixture",
        representation_id=ledger.bundle.representation.id,
        task_type="claim_extraction",
        focus_node_ids=(ledger.bundle.nodes[0].id,),
        dependency_node_ids=(),
        planner_policy_id="fixture_policy_v1",
        fingerprint="e" * 64,
    )
    persist_analysis_unit(unit, ledger)
    return build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture-model", 512, 8, 4),
            prompt_id="fixture_prompt_v1",
            prompt_bytes=b"fixture prompt",
            schema_id="staged_claim_output_v1",
            schema_bytes=staged_claim_output_schema_bytes(),
            renderer_version="fixture_renderer_v1",
        ),
        ledger,
        FixtureTokenizer(),
    ).manifest


def _valid_staged_output() -> bytes:
    return (
        b'{"kind":"candidates","schema_id":"staged_claim_output_v1",'
        b'"organizations":[{"local_id":"subject","name":"Fixture Organization"}],'
        b'"evidence":[{"local_id":"support","node_id":"nod_grounded_fixture",'
        b'"exact_quote":"Alpha supports the accepted assertion.",'
        b'"node_local_start":0,"node_local_end":38}],'
        b'"assertions":[{"local_id":"claim",'
        b'"subject_organization_local_id":"subject","evidence_local_id":"support",'
        b'"predicate":"reported_alpha","object_value":"Alpha"}]}'
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
                predicate="reported_alpha",
                object_value="Alpha",
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
    assert assertion_links == [
        {
            "evidence_target_id": evidence.id,
            "validation_attempt_id": validation.id,
            "role": "direct_support",
            "polarity": "supports",
            "necessity": "required",
        }
    ]


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
    assert first.nodes == ledger.bundle.nodes
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
    raw_output = b"""{
      "kind":"candidates",
      "schema_id":"staged_claim_output_v1",
      "organizations":[{"local_id":"subject","name":"Fixture Organization"}],
      "evidence":[{
        "local_id":"support",
        "node_id":"nod_not_visible",
        "exact_quote":"Alpha supports the accepted assertion.",
        "node_local_start":0,
        "node_local_end":38
      }],
      "assertions":[{
        "local_id":"claim",
        "subject_organization_local_id":"subject",
        "evidence_local_id":"support",
        "predicate":"reported_alpha",
        "object_value":"Alpha"
      }]
    }"""
    runtime = FakeModelTaskRuntime(raw_output)
    prompt_bytes = b"fixture prompt"
    schema_bytes = staged_claim_output_schema_bytes()
    analysis_unit = AnalysisUnit(
        id="anu_fixture_candidate_v1",
        representation_id=ledger.bundle.representation.id,
        task_type="claim_extraction",
        focus_node_ids=(),
        dependency_node_ids=(),
        planner_policy_id="fixture_policy_v1",
        fingerprint="a" * 64,
    )
    persist_analysis_unit(analysis_unit, ledger)
    rendered_input = prompt_bytes + b"\n\n" + schema_bytes
    manifest = ContextManifest(
        id="ctx_fixture_candidate_v1",
        analysis_unit_id="anu_fixture_candidate_v1",
        analysis_unit_payload={
            "id": analysis_unit.id,
            "representation_id": analysis_unit.representation_id,
            "task_type": analysis_unit.task_type,
            "focus_node_ids": [],
            "dependency_node_ids": [],
            "planner_policy_id": analysis_unit.planner_policy_id,
            "fingerprint": analysis_unit.fingerprint,
        },
        representation_id=ledger.bundle.representation.id,
        prompt_id="fixture_prompt_v1",
        prompt_bytes=prompt_bytes,
        prompt_digest=hashlib.sha256(prompt_bytes).hexdigest(),
        schema_id="staged_claim_output_v1",
        schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
        schema_bytes=schema_bytes,
        renderer_version="fixture_renderer_v1",
        planner_policy_id="fixture_policy_v1",
        tokenizer_id="fixture_tokenizer_v1",
        model_profile_id="fixture-model",
        model_context_limit=64,
        reserved_output_tokens=8,
        safety_margin_tokens=4,
        selected_candidates=(),
        excluded_candidates=(),
        rendered_segments=(),
        rendered_input=rendered_input,
        rendered_input_digest=hashlib.sha256(rendered_input).hexdigest(),
        input_token_count=FixtureTokenizer().count_tokens(rendered_input),
        manifest_digest="c" * 64,
        status=ContextManifestStatus.READY,
    )
    manifest = replace(manifest, manifest_digest=context_manifest_digest(manifest))
    persist_context_manifest(manifest, ledger)

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=prompt_bytes,
            model_identity=ModelIdentity(
                "fixture-model",
                "d" * 64,
                "fixture-runtime",
                "fixture-tokenizer-v1",
                {"temperature": 0},
            ),
            generation_parameters={"temperature": 0},
            validator_version="fixture-validator-v1",
            started_at=NOW,
            completed_at=NOW,
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        StagedClaimTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.model_run.error_message is not None
    assert "absent" in outcome.model_run.error_message
    assert outcome.proposed_change_batch is None
    assert ledger.proposed_changes == {}
    assert archive.outputs[outcome.model_run.id] == raw_output


def test_staged_extraction_rejects_unpinned_prompt_before_model_invocation() -> None:
    ledger = FakeGroundedCandidateLedger()
    archive = FakeModelOutputArchive()
    runtime = FakeModelTaskRuntime(b"{}")
    unit = AnalysisUnit(
        id="anu_schema_guard_fixture",
        representation_id=ledger.bundle.representation.id,
        task_type="claim_extraction",
        focus_node_ids=(),
        dependency_node_ids=(),
        planner_policy_id="fixture_policy_v1",
        fingerprint="b" * 64,
    )
    persist_analysis_unit(unit, ledger)
    prompt_bytes = b"fixture prompt"
    schema_bytes = staged_claim_output_schema_bytes()
    rendered_input = prompt_bytes + b"\n\n" + schema_bytes
    manifest = ContextManifest(
        id="ctx_schema_guard_fixture",
        analysis_unit_id=unit.id,
        analysis_unit_payload={
            "id": unit.id,
            "representation_id": unit.representation_id,
            "task_type": unit.task_type,
            "focus_node_ids": [],
            "dependency_node_ids": [],
            "planner_policy_id": unit.planner_policy_id,
            "fingerprint": unit.fingerprint,
        },
        representation_id=ledger.bundle.representation.id,
        prompt_id="fixture_prompt_v1",
        prompt_bytes=prompt_bytes,
        prompt_digest=hashlib.sha256(prompt_bytes).hexdigest(),
        schema_id="staged_claim_output_v1",
        schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
        schema_bytes=schema_bytes,
        renderer_version="fixture_renderer_v1",
        planner_policy_id=unit.planner_policy_id,
        tokenizer_id=FixtureTokenizer.tokenizer_id,
        model_profile_id="fixture-model",
        model_context_limit=512,
        reserved_output_tokens=8,
        safety_margin_tokens=4,
        selected_candidates=(),
        excluded_candidates=(),
        rendered_segments=(),
        rendered_input=rendered_input,
        rendered_input_digest=hashlib.sha256(rendered_input).hexdigest(),
        input_token_count=FixtureTokenizer().count_tokens(rendered_input),
        manifest_digest="c" * 64,
        status=ContextManifestStatus.READY,
    )
    manifest = replace(manifest, manifest_digest=context_manifest_digest(manifest))
    persist_context_manifest(manifest, ledger)

    with pytest.raises(ValueError, match="prompt bytes"):
        run_bounded_extraction(
            BoundedExtractionInput(
                source_id=ledger.source.id,
                document_id=ledger.document.id,
                representation_id=ledger.bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"tampered prompt",
                model_identity=ModelIdentity(
                    "fixture-model",
                    "d" * 64,
                    "fixture-runtime",
                    FixtureTokenizer.tokenizer_id,
                    {"temperature": 0},
                ),
                generation_parameters={"temperature": 0},
                validator_version="fixture-validator-v1",
                started_at=NOW,
                completed_at=NOW,
            ),
            ledger,
            archive,
            runtime,
            Uuid4ModelRunIdFactory(),
            FixtureTokenizer(),
            StagedClaimTaskSchemaRegistry(),
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
            schema = StagedClaimTaskSchemaRegistry().resolve(schema_id)
            return replace(schema, canonical_schema_bytes=b'{"type":"null"}')

    with pytest.raises(ValueError, match="schema bytes"):
        run_bounded_extraction(
            BoundedExtractionInput(
                source_id=ledger.source.id,
                document_id=ledger.document.id,
                representation_id=ledger.bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=b"fixture prompt",
                model_identity=ModelIdentity(
                    "fixture-model",
                    "d" * 64,
                    "fixture-runtime",
                    FixtureTokenizer.tokenizer_id,
                    {"temperature": 0},
                ),
                generation_parameters={"temperature": 0},
                validator_version="fixture-validator-v1",
                started_at=NOW,
                completed_at=NOW,
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
    runtime = FakeModelTaskRuntime(
        _valid_staged_output().replace(
            b'"node_id":"nod_grounded_fixture"',
            b'"text_view_id":"tvw_grounded_fixture","start_char":0,'
            b'"pdf_region_ids":[],"node_id":"nod_grounded_fixture"',
        )
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest_id=manifest.id,
            prompt_bytes=b"fixture prompt",
            model_identity=ModelIdentity(
                "fixture-model",
                "d" * 64,
                "fixture-runtime",
                FixtureTokenizer.tokenizer_id,
                {"temperature": 0},
            ),
            generation_parameters={"temperature": 0},
            validator_version="fixture-validator-v1",
            started_at=NOW,
            completed_at=NOW,
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        StagedClaimTaskSchemaRegistry(),
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
            model_identity=ModelIdentity(
                "fixture-model",
                "d" * 64,
                "fixture-runtime",
                FixtureTokenizer.tokenizer_id,
                {"temperature": 0},
            ),
            generation_parameters={"temperature": 0},
            validator_version="fixture-validator-v1",
            started_at=NOW,
            completed_at=NOW,
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        StagedClaimTaskSchemaRegistry(),
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert outcome.proposed_change_batch is None
    assert ledger.evidence_targets == {}
    assert ledger.validation_attempts == {}
    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}
    assert len(ledger.model_runs) == 1


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
        model_identity=ModelIdentity(
            "fixture-model",
            "d" * 64,
            "fixture-runtime",
            FixtureTokenizer.tokenizer_id,
            {"temperature": 0},
        ),
        generation_parameters={"temperature": 0},
        validator_version="fixture-validator-v1",
        started_at=NOW,
        completed_at=NOW,
    )
    first = run_bounded_extraction(
        extraction_input,
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        StagedClaimTaskSchemaRegistry(),
    )
    second = run_bounded_extraction(
        extraction_input,
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        FixtureTokenizer(),
        StagedClaimTaskSchemaRegistry(),
    )

    assert first.extraction_task.id == second.extraction_task.id
    assert first.model_run.id != second.model_run.id
    assert {run.id for run in ledger.model_runs.values()} == {
        first.model_run.id,
        second.model_run.id,
    }
    assert archive.outputs[first.model_run.id] == _valid_staged_output()
    assert archive.outputs[second.model_run.id] == _valid_staged_output()
