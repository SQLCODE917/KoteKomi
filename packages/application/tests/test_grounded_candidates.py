import hashlib
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    BoundedExtractionInput,
    ContextCandidate,
    ContextCandidateRole,
    ContextManifest,
    ContextManifestStatus,
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedCandidateContextInput,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    ModelIdentity,
    ModelTaskRequest,
    ModelTaskResponse,
    build_grounded_candidate_context,
    run_bounded_extraction,
    submit_grounded_candidate_batch,
)
from kotekomi_domain import (
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
      "schema_id":"fixture_candidate_schema_v1",
      "organizations":[{"local_id":"subject","name":"Fixture Organization"}],
      "evidence":[{
        "local_id":"support",
        "text_view_id":"tvw_grounded_fixture",
        "start_char":0,
        "end_char":35,
        "exact_text":"Alpha supports the accepted assertion.",
        "node_ids":["nod_not_visible"]
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
    rendered_input = b"fixture prompt\nfixture schema\nfixture node"
    manifest = ContextManifest(
        id="ctx_fixture_candidate_v1",
        analysis_unit_id="anu_fixture_candidate_v1",
        representation_id=ledger.bundle.representation.id,
        prompt_id="fixture_prompt_v1",
        prompt_digest=hashlib.sha256(b"fixture prompt").hexdigest(),
        schema_id="fixture_candidate_schema_v1",
        schema_digest=hashlib.sha256(b"fixture schema").hexdigest(),
        renderer_version="fixture_renderer_v1",
        planner_policy_id="fixture_policy_v1",
        tokenizer_id="fixture_tokenizer_v1",
        model_context_limit=64,
        reserved_output_tokens=8,
        safety_margin_tokens=4,
        selected_candidates=(
            ContextCandidate(
                node_id=ledger.bundle.nodes[0].id,
                role=ContextCandidateRole.FOCUS,
                reason_code="focus_node",
                required=True,
                priority=1,
                dependency_path=(),
                source_node_ids=(ledger.bundle.nodes[0].id,),
                estimated_tokens=3,
            ),
        ),
        excluded_candidates=(),
        rendered_segments=(),
        rendered_input=rendered_input,
        rendered_input_digest=hashlib.sha256(rendered_input).hexdigest(),
        input_token_count=3,
        manifest_digest="c" * 64,
        status=ContextManifestStatus.READY,
    )

    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            context_manifest=manifest,
            model_run_id="mrn_invalid_task_local_ref",
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
    )

    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert "absent from the ContextManifest" in (outcome.model_run.error_message or "")
    assert outcome.proposed_change_batch is None
    assert ledger.proposed_changes == {}
    assert archive.outputs[outcome.model_run.id] == raw_output
