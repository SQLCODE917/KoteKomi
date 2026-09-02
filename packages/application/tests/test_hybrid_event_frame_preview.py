from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import cast

from kotekomi_application import (
    ContextModelProfile,
    ExecutionSetting,
    HybridEntityGroundingPreview,
    HybridEntityGroundingStatus,
    HybridEventFrameCommand,
    HybridEventFramePreview,
    HybridEventFrameResult,
    HybridEventFrameStatus,
    HybridExtractionPreview,
    HybridMentionPreviewCommand,
    HybridMentionPreviewResult,
    HybridReferencePreview,
    HybridReferencePreviewCommand,
    MentionProposal,
    MentionProposalBatch,
    MentionProposalInput,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelTaskRequest,
    ModelTaskResponse,
    build_hybrid_entity_grounding_preview_record,
    canonical_hybrid_entity_grounding_preview_bytes,
    generation_parameters_digest,
    hybrid_entity_grounding_preview_sha256,
    load_hybrid_event_frame_preview,
    model_identity_snapshot_digest,
    run_hybrid_event_frame_preview,
    run_hybrid_mention_preview,
    run_hybrid_reference_preview,
)
from kotekomi_application.hybrid_atomic_claim_preview import (
    HybridAtomicClaimArchive,
    HybridAtomicClaimCommand,
    HybridAtomicClaimLedger,
    load_hybrid_atomic_claim_preview,
    publish_hybrid_atomic_claim_preview,
    run_hybrid_atomic_claim_preview,
)
from kotekomi_application.hybrid_atomic_claims import (
    HybridAtomicClaimPreview,
    HybridAtomicClaimStatus,
)
from kotekomi_application.hybrid_event_frame_preview import (
    HybridEventFrameArchive,
    HybridEventFrameLedger,
)
from kotekomi_application.hybrid_mention_preview import HybridMentionArchive, HybridMentionLedger
from kotekomi_application.hybrid_reference_preview import (
    HybridReferenceArchive,
    HybridReferenceLedger,
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
    ParseQualityReport,
    RepresentationAnalyzability,
    Source,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)
TEXT = (
    "Policy\nThe Department of Defense announced and established  Directive 3000.09 "
    "in Washington in  2012."
)
PARAGRAPH = (
    "The Department of Defense announced and established  Directive 3000.09 in Washington in  2012."
)


class _Tokenizer:
    tokenizer_id = "fixture_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


class _Ledger:
    def __init__(self) -> None:
        self.source = Source(
            id="src_hp4_fixture",
            source_type=SourceType.MANUAL_FILE,
            identity_policy_id="fixture_v1",
            canonical_identity_key="hp4-fixture",
        )
        self.document = Document(
            id="doc_hp4_fixture",
            source_id=self.source.id,
            content_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
        )
        self.bundle = _bundle(self.document.id)
        self.manifests: dict[str, ContextManifestArtifact] = {}
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.evidence_targets: dict[str, EvidenceTarget] = {}
        self.evidence_attempts: dict[str, EvidenceValidationAttempt] = {}
        self.accepted_state_called = False

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.manifests.get(record_id)

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.manifests[manifest.id] = manifest
        self.analysis_units.update({item.id: item for item in child_analysis_units})

    def save_extraction_task(self, record: ExtractionTask) -> None:
        self.extraction_tasks[record.id] = record

    def save_model_run(self, record: ModelRun) -> None:
        self.model_runs[record.id] = record

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.evidence_targets.get(record_id)

    def save_evidence_target(self, record: EvidenceTarget) -> None:
        self.evidence_targets[record.id] = record

    def get_evidence_validation_attempt(self, record_id: str) -> EvidenceValidationAttempt | None:
        return self.evidence_attempts.get(record_id)

    def save_evidence_validation_attempt(self, record: EvidenceValidationAttempt) -> None:
        self.evidence_attempts[record.id] = record

    def commit_successful_model_run_and_candidate_batch(
        self, *, model_run: ModelRun, batch: object
    ) -> None:
        del model_run, batch
        self.accepted_state_called = True
        raise AssertionError("HP-4 must not create accepted state.")


class _Archive:
    def __init__(self) -> None:
        self.model_outputs: dict[str, bytes] = {}
        self.mention_previews: dict[str, bytes] = {}
        self.reference_previews: dict[str, bytes] = {}
        self.grounding_previews: dict[str, bytes] = {}
        self.event_previews: dict[str, bytes] = {}
        self.atomic_claim_previews: dict[str, bytes] = {}

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_digest
        self.model_outputs[model_run_id] = payload
        return object()

    def put_hybrid_extraction_preview(
        self, preview: HybridExtractionPreview, payload: bytes, expected: str
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected
        self.mention_previews[preview.id] = payload
        return object()

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes:
        return self.mention_previews[preview_id]

    def put_hybrid_reference_preview(
        self, preview: HybridReferencePreview, payload: bytes, expected: str
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected
        self.reference_previews[preview.id] = payload
        return object()

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes:
        return self.reference_previews[preview_id]

    def read_hybrid_entity_grounding_preview(self, preview_id: str) -> bytes:
        return self.grounding_previews[preview_id]

    def put_hybrid_event_frame_preview(
        self,
        preview: HybridEventFramePreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        self.event_previews[preview.id] = payload
        return object()

    def read_hybrid_event_frame_preview(self, preview_id: str) -> bytes:
        return self.event_previews[preview_id]

    def put_hybrid_atomic_claim_preview(
        self,
        preview: HybridAtomicClaimPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        existing = self.atomic_claim_previews.get(preview.id)
        assert existing is None or existing == payload
        self.atomic_claim_previews[preview.id] = payload
        return object()

    def read_hybrid_atomic_claim_preview(self, preview_id: str) -> bytes:
        return self.atomic_claim_previews[preview_id]


class _MentionProposer:
    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        segment = proposal_input.source_segments[0]
        text = "Department of Defense"
        start = segment.exact_text.index(text)
        return MentionProposalBatch(
            proposer_id="fixture-gliner",
            model_id="fixture-gliner",
            model_revision="v1",
            configuration=(),
            load_elapsed_milliseconds=0,
            inference_elapsed_milliseconds=0,
            proposals=(
                MentionProposal(
                    segment.label,
                    text,
                    start,
                    start + len(text),
                    ("organization",),
                    0.9,
                ),
            ),
        )


class _Runtime:
    def __init__(
        self,
        stage: str,
        *,
        trigger_output: bytes | None = None,
        frame_output: bytes | None = None,
        frame_outputs: tuple[bytes, ...] | None = None,
    ) -> None:
        self.stage = stage
        self.trigger_output = trigger_output
        self.frame_output = frame_output
        self.frame_outputs = frame_outputs
        self.frame_ordinal = 0
        self.requests: list[ModelTaskRequest] = []
        self._identity = ModelIdentitySnapshot(
            "qwen2.5-fixture",
            "d" * 64,
            "fixture-runtime",
            _Tokenizer.tokenizer_id,
        )

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return self._identity

    @property
    def task_deadline_seconds(self) -> float:
        return 300.0

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        if self.stage == "mentions" and b"task: propose_mentions" in task.rendered_input:
            output = b"mention: s1 | organization | Department of Defense\n"
        elif self.stage == "mentions" and b"task: interpret_mention" in task.rendered_input:
            output = (
                b"candidate: c1\n"
                b"referentiality: specific_entity\n"
                b"contextual_kind: organization\n"
                b"discourse_role: actor\n"
                b"support: s1\n"
            )
        elif self.stage == "events" and b"task: detect_event_triggers" in task.rendered_input:
            output = self.trigger_output or (
                b"event: e1 | s1 | established | policy_establishment\n"
            )
        elif self.stage == "events" and b"task: assign_event_frame" in task.rendered_input:
            if self.frame_outputs is not None:
                output = self.frame_outputs[self.frame_ordinal]
                self.frame_ordinal += 1
            else:
                output = self.frame_output or (
                    b"event: e1\n"
                    b"polarity: affirmed\n"
                    b"modality: actual\n"
                    b"attribution: source_narrator\n"
                    b"argument: c1 | policy_establisher | s1\n"
                    b"qualifier: time | s1 | 2012\n"
                )
        else:
            raise AssertionError("Unexpected fixture model task.")
        return ModelTaskResponse(
            output,
            ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(
                    task.execution_spec.model_identity
                ),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=task.rendered_input_digest,
                input_token_count=len(task.rendered_input.decode().split()),
                output_token_count=len(output.decode().split()),
            ),
        )


class _RunIds:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.ordinal = 0

    def new_model_run_id(self) -> str:
        self.ordinal += 1
        return f"mrn_{self.prefix}_{self.ordinal}"


def test_hp4_runs_trigger_then_frame_with_exact_data_lineage_and_no_state_change() -> None:
    ledger, archive, mention, grounding = _parent_evidence()
    event_runtime = _Runtime("events")

    result = _run_hp4(ledger, archive, grounding.id, event_runtime)

    assert result.preview.terminal_status is HybridEventFrameStatus.COMPLETE
    assert result.preview.diagnostics == ("hp3_status:blocked",)
    assert [item.text for item in result.preview.triggers] == ["established"]
    frame = result.preview.frames[0]
    assert frame.arguments[0].candidate_id == mention.preview.candidates[0].id
    assert frame.arguments[0].role_label == "policy_establisher"
    assert frame.qualifiers[0].text == "2012"
    assert frame.source_narrator_attribution is True
    assert len(event_runtime.requests) == 2
    assert all(b"Q11209" not in item.rendered_input for item in event_runtime.requests)
    assert all(trace.input for trace in result.preview.traces)
    assert all(trace.output["raw_output_sha256"] for trace in result.preview.traces)
    assert set(result.preview.model_run_ids).issubset(archive.model_outputs)
    assert ledger.accepted_state_called is False
    assert load_hybrid_event_frame_preview(result.preview.id, archive) == result.preview
    assert (
        hybrid_entity_grounding_preview_sha256(grounding)
        == hashlib.sha256(archive.grounding_previews[grounding.id]).hexdigest()
    )


def test_hp4_reload_rejects_tampered_parent_evidence() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    result = _run_hp4(ledger, archive, grounding.id, _Runtime("events"))
    archive.grounding_previews[grounding.id] += b"\n"

    try:
        load_hybrid_event_frame_preview(result.preview.id, archive)
    except ValueError as error:
        assert str(error) == "HP-4 HP-3 parent evidence does not match its pinned digest."
    else:
        raise AssertionError("Tampered HP-3 evidence must prevent HP-4 reload.")


def test_hp4_rejects_an_entire_trigger_task_when_one_literal_is_not_source_valid() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    runtime = _Runtime(
        "events",
        trigger_output=(
            b"event: e1 | s1 | established | policy_establishment\n"
            b"event: e2 | s1 | missing literal | mention\n"
        ),
    )

    result = _run_hp4(ledger, archive, grounding.id, runtime)

    assert result.preview.terminal_status is HybridEventFrameStatus.BLOCKED
    assert result.preview.triggers == ()
    assert result.preview.frames == ()
    assert result.preview.traces[0].status.value == "rejected"
    assert result.preview.traces[0].diagnostics == ("trigger_source_mapping_rejected",)
    assert any(item.startswith("trigger_mapping_failed:") for item in result.preview.diagnostics)
    assert len(runtime.requests) == 1


def test_hp4_preserves_multiple_triggers_through_separate_frame_tasks() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    runtime = _Runtime(
        "events",
        trigger_output=(
            b"event: e1 | s1 | announced | announcement\n"
            b"event: e2 | s1 | established | policy_establishment\n"
        ),
        frame_outputs=(
            b"event: e1\npolarity: affirmed\nmodality: actual\nattribution: source_narrator\n",
            b"event: e2\npolarity: affirmed\nmodality: actual\nattribution: source_narrator\n",
        ),
    )

    result = _run_hp4(ledger, archive, grounding.id, runtime)

    assert result.preview.terminal_status is HybridEventFrameStatus.COMPLETE
    assert [item.text for item in result.preview.triggers] == ["announced", "established"]
    assert len(result.preview.frames) == 2
    assert len(runtime.requests) == 3


def test_hp4_all_segment_abstention_produces_an_empty_complete_preview() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    runtime = _Runtime(
        "events",
        trigger_output=b"abstain: no explicit event in the target segment\n",
    )

    result = _run_hp4(ledger, archive, grounding.id, runtime)

    assert result.preview.terminal_status is HybridEventFrameStatus.COMPLETE
    assert result.preview.triggers == ()
    assert result.preview.frames == ()
    assert len(runtime.requests) == 1


def test_hp4_rejects_a_malformed_frame_mapping_without_publishing_a_partial_frame() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    runtime = _Runtime(
        "events",
        frame_output=(
            b"event: e1\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: c99 | policy_establisher | s1\n"
        ),
    )

    result = _run_hp4(ledger, archive, grounding.id, runtime)

    assert result.preview.terminal_status is HybridEventFrameStatus.PARTIAL
    assert len(result.preview.triggers) == 1
    assert result.preview.frames == ()
    assert result.preview.traces[1].status.value == "rejected"
    assert result.preview.traces[1].diagnostics == ("frame_source_mapping_rejected",)
    assert any(item.startswith("frame_mapping_failed:") for item in result.preview.diagnostics)


def test_hp4_maps_a_whitespace_normalized_source_copy_back_to_authoritative_text() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    runtime = _Runtime(
        "events",
        trigger_output=(b"event: e1 | s1 | established Directive 3000.09 | policy_establishment\n"),
    )

    result = _run_hp4(ledger, archive, grounding.id, runtime)

    assert result.preview.terminal_status is HybridEventFrameStatus.COMPLETE
    assert result.preview.triggers[0].text == "established  Directive 3000.09"
    assert (
        result.preview.traces[0].input["source_copy_text"]
        == "The Department of Defense announced and established Directive 3000.09 "
        "in Washington in 2012."
    )


def test_hp4_maps_place_qualifier_and_explicit_attribution_candidate() -> None:
    ledger, archive, mention, grounding = _parent_evidence()
    runtime = _Runtime(
        "events",
        frame_output=(
            b"event: e1\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: c1\n"
            b"argument: c1 | policy_establisher | s1\n"
            b"qualifier: place | s1 | Washington\n"
        ),
    )

    result = _run_hp4(ledger, archive, grounding.id, runtime)

    frame = result.preview.frames[0]
    assert frame.source_narrator_attribution is False
    assert frame.attribution_candidate_ids == (mention.preview.candidates[0].id,)
    assert frame.qualifiers[0].kind.value == "place"
    assert frame.qualifiers[0].text == "Washington"


def test_hp5_atomizes_hp4_without_repairing_open_labels_or_creating_model_runs() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    hp4 = _run_hp4(ledger, archive, grounding.id, _Runtime("events"))

    first = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(first, cast(HybridAtomicClaimArchive, archive))
    second = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, datetime(2026, 9, 2, tzinfo=UTC)),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(second, cast(HybridAtomicClaimArchive, archive))

    assert first.preview.terminal_status is HybridAtomicClaimStatus.COMPLETE
    assert first.preview.id == second.preview.id
    assert len(first.preview.event_subjects) == 1
    assert len(first.preview.atomic_claims) == 6
    assert len(first.preview.evidence_target_ids) == 1
    assert len(first.preview.traces) == 2
    assert {item.code for item in first.preview.ontology_reports[0].findings} == {
        "unmapped_argument_role",
        "unmapped_event_type",
    }
    assert {item.role_label for item in first.preview.atomic_claims if item.role_label} == {
        "policy_establisher"
    }
    assert not any(trace.execution_record_ids for trace in first.preview.traces)
    assert (
        load_hybrid_atomic_claim_preview(
            first.preview.id,
            cast(HybridAtomicClaimLedger, ledger),
            cast(HybridAtomicClaimArchive, archive),
        )
        == first.preview
    )


def test_hp5_preserves_candidate_attribution_as_an_explicit_contract_gap() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    hp4 = _run_hp4(
        ledger,
        archive,
        grounding.id,
        _Runtime(
            "events",
            frame_output=(
                b"event: e1\n"
                b"polarity: affirmed\n"
                b"modality: actual\n"
                b"attribution: c1\n"
                b"argument: c1 | actor | s1\n"
            ),
        ),
    )

    result = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(result, cast(HybridAtomicClaimArchive, archive))

    report = result.preview.ontology_reports[0]
    assert "attribution_support_missing" in {item.code for item in report.findings}
    assert "according_to" not in {item.predicate.value for item in result.preview.atomic_claims}


def test_hp5_retains_valid_frames_from_a_partial_hp4_preview() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    hp4 = _run_hp4(
        ledger,
        archive,
        grounding.id,
        _Runtime(
            "events",
            trigger_output=(
                b"event: e1 | s1 | announced | event\nevent: e2 | s1 | established | event\n"
            ),
            frame_outputs=(
                b"event: e1\npolarity: affirmed\nmodality: actual\nattribution: source_narrator\n",
                b"event: e2\npolarity: affirmed\nmodality: actual\nattribution: c99\n",
            ),
        ),
    )
    assert hp4.preview.terminal_status is HybridEventFrameStatus.PARTIAL

    result = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(result, cast(HybridAtomicClaimArchive, archive))

    assert result.preview.terminal_status is HybridAtomicClaimStatus.PARTIAL
    assert len(result.preview.event_subjects) == 1
    assert result.preview.diagnostics == ("hp4_status:partial",)


def test_hp5_preserves_complete_empty_and_blocked_parent_states() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    complete_parent = _run_hp4(
        ledger,
        archive,
        grounding.id,
        _Runtime(
            "events",
            trigger_output=b"abstain: no explicit event in the target segment\n",
        ),
    )
    complete = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(complete_parent.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    assert complete.preview.terminal_status is HybridAtomicClaimStatus.COMPLETE
    assert complete.preview.event_subjects == ()
    assert complete.preview.evidence_target_ids == ()

    blocked_parent = _run_hp4(
        ledger,
        archive,
        grounding.id,
        _Runtime(
            "events",
            trigger_output=b"event: e1 | s1 | missing literal | event\n",
        ),
    )
    blocked = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(blocked_parent.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    assert blocked.preview.terminal_status is HybridAtomicClaimStatus.BLOCKED
    assert blocked.preview.diagnostics == ("hp4_status:blocked", "no_valid_event_frames")
    assert blocked.preview.evidence_target_ids == ()


def test_hp4_preserves_a_frame_abstention_as_typed_non_applicable_evidence() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    runtime = _Runtime(
        "events",
        frame_output=b"abstain: source does not assign event participants\n",
    )

    result = _run_hp4(ledger, archive, grounding.id, runtime)

    assert result.preview.terminal_status is HybridEventFrameStatus.PARTIAL
    assert result.preview.frames == ()
    assert result.preview.traces[1].status.value == "not_applicable"
    assert result.preview.traces[1].diagnostics == ("frame_task_abstained",)
    assert any(item.startswith("frame_task_abstained:") for item in result.preview.diagnostics)


def _parent_evidence() -> tuple[
    _Ledger,
    _Archive,
    HybridMentionPreviewResult,
    HybridEntityGroundingPreview,
]:
    ledger = _Ledger()
    archive = _Archive()
    mention_runtime = _Runtime("mentions")
    mention = run_hybrid_mention_preview(
        command=HybridMentionPreviewCommand(
            representation_id=ledger.bundle.representation.id,
            paragraph_node_id="nod_hp4_paragraph",
            model_profile=ContextModelProfile("fixture-model", 2048, 128, 16),
            generation_parameters=_generation(),
        ),
        ledger=cast(HybridMentionLedger, ledger),
        archive=cast(HybridMentionArchive, archive),
        proposer=_MentionProposer(),
        model_runtime=mention_runtime,
        model_run_id_factory=_RunIds("mention"),
        tokenizer=_Tokenizer(),
        prompt_bytes=b"Perform only the named mention task.",
        ontology_card_bytes=b"Organization means a coordinated body.",
    )
    references = run_hybrid_reference_preview(
        command=HybridReferencePreviewCommand(mention.preview.id),
        ledger=cast(HybridReferenceLedger, ledger),
        archive=cast(HybridReferenceArchive, archive),
    )
    grounding = build_hybrid_entity_grounding_preview_record(
        parent_preview_id=references.preview.id,
        parent_preview_sha256=references.sha256,
        mention_preview_id=mention.preview.id,
        mention_preview_sha256=mention.sha256,
        representation_id=mention.preview.representation_id,
        eligibility=(),
        link_evidence=(),
        extraction_task_ids=(),
        model_run_ids=(),
        traces=(),
        terminal_status=HybridEntityGroundingStatus.BLOCKED,
        diagnostics=("fixture_grounding_unavailable",),
    )
    grounding_payload = canonical_hybrid_entity_grounding_preview_bytes(grounding)
    archive.grounding_previews[grounding.id] = grounding_payload
    return ledger, archive, mention, grounding


def _run_hp4(
    ledger: _Ledger,
    archive: _Archive,
    grounding_id: str,
    event_runtime: _Runtime,
) -> HybridEventFrameResult:
    return run_hybrid_event_frame_preview(
        command=HybridEventFrameCommand(
            grounding_id,
            ContextModelProfile("fixture-model", 2048, 128, 16),
            _generation(),
        ),
        ledger=cast(HybridEventFrameLedger, ledger),
        archive=cast(HybridEventFrameArchive, archive),
        model_runtime=event_runtime,
        model_run_id_factory=_RunIds("event"),
        tokenizer=_Tokenizer(),
        trigger_prompt_bytes=b"Detect event triggers only.",
        frame_prompt_bytes=b"Assign roles to the supplied event only.",
    )


def _generation() -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting("max_output_tokens", 128),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )


def _bundle(document_id: str) -> DocumentRepresentationBundle:
    representation_id = "rep_hp4_fixture"
    text_view = TextView(
        id="tvw_hp4_fixture",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )
    heading_end = TEXT.index("\n")
    paragraph_start = heading_end + 1
    root = DocumentNode(
        id="nod_hp4_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(TEXT),
    )
    heading = DocumentNode(
        id="nod_hp4_heading",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="heading",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=heading_end,
    )
    paragraph = DocumentNode(
        id="nod_hp4_paragraph",
        representation_id=representation_id,
        parent_node_id=heading.id,
        node_type="paragraph",
        order_index=2,
        text_view_id=text_view.id,
        start_char=paragraph_start,
        end_char=len(TEXT),
    )
    quality = ParseQualityReport(
        id="pqr_hp4_fixture",
        representation_id=representation_id,
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document_id,
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_hp4_fixture",
        input_blob_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root, heading, paragraph),
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, heading, paragraph),
        quality_report=quality,
    )
