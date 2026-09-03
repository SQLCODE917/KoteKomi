from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    ContextModelProfile,
    EventAttributionKind,
    ExecutionSetting,
    HybridEntityGroundingPreview,
    HybridEntityGroundingStatus,
    HybridEventFrameCommand,
    HybridEventFramePreview,
    HybridEventFrameResult,
    HybridEventFrameStatus,
    HybridEventSemanticsCommand,
    HybridEventSemanticsPreview,
    HybridEventSemanticsResult,
    HybridEventSemanticsStatus,
    HybridExtractionPreview,
    HybridMentionPreviewCommand,
    HybridMentionPreviewResult,
    HybridProposalPlan,
    HybridReferencePreview,
    HybridReferencePreviewCommand,
    MentionProposal,
    MentionProposalBatch,
    MentionProposalInput,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelTaskRequest,
    ModelTaskResponse,
    ProposalAdmissionReason,
    ProposalDisposition,
    ReviewProposedChangeInput,
    SemanticCoverageGapCode,
    approve_proposed_change,
    build_hybrid_entity_grounding_preview_record,
    build_hybrid_proposal_plan,
    canonical_hybrid_entity_grounding_preview_bytes,
    generation_parameters_digest,
    hybrid_entity_grounding_preview_sha256,
    hybrid_proposal_plan_from_bytes,
    load_hybrid_event_frame_preview,
    load_hybrid_event_semantics_preview,
    load_hybrid_proposal_plan,
    model_identity_snapshot_digest,
    publish_hybrid_event_semantics_preview,
    reject_proposed_change,
    run_hybrid_event_frame_preview,
    run_hybrid_event_semantics_preview,
    run_hybrid_mention_preview,
    run_hybrid_proposal_submission,
    run_hybrid_reference_preview,
)
from kotekomi_application.hybrid_atomic_claim_preview import (
    HybridAtomicClaimArchive,
    HybridAtomicClaimCommand,
    HybridAtomicClaimLedger,
    HybridAtomicClaimResult,
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
from kotekomi_application.hybrid_event_semantics import (
    build_event_argument_assignment_draft,
    build_event_semantic_draft,
    build_hybrid_event_semantics_preview,
)
from kotekomi_application.hybrid_event_semantics_preview import (
    HybridEventSemanticsArchive,
    HybridEventSemanticsLedger,
)
from kotekomi_application.hybrid_mention_preview import HybridMentionArchive, HybridMentionLedger
from kotekomi_application.hybrid_reference_preview import (
    HybridReferenceArchive,
    HybridReferenceLedger,
)
from kotekomi_application.proposed_change_review import ProposedChangeReviewLedger
from kotekomi_domain import (
    Actor,
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    Event,
    EvidenceTarget,
    EvidenceValidationAttempt,
    ExtractionTask,
    ModelRun,
    Organization,
    ParseQualityReport,
    ProposedAssertion,
    ProposedChange,
    ProvenanceActivity,
    RepresentationAnalyzability,
    ReviewStatus,
    SemanticArgumentTargetKind,
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
        self.proposed_changes: dict[str, ProposedChange] = {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}
        self.actors: dict[str, Actor] = {}
        self.organizations: dict[str, Organization] = {}
        self.events: dict[str, Event] = {}

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

    def get_actor(self, record_id: str) -> Actor | None:
        return self.actors.get(record_id)

    def get_organization(self, record_id: str) -> Organization | None:
        return self.organizations.get(record_id)

    def get_event(self, record_id: str) -> Event | None:
        return self.events.get(record_id)

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self.provenance_activities.get(record_id)

    def save_actor(self, record: Actor) -> None:
        self.actors[record.id] = record

    def save_organization(self, record: Organization) -> None:
        self.organizations[record.id] = record

    def save_event(self, record: Event) -> None:
        self.events[record.id] = record

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposed_changes[record.id] = record

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record

    def commit_hybrid_proposal_batch(
        self,
        *,
        provenance_activity: ProvenanceActivity,
        proposed_changes: tuple[ProposedChange, ...],
    ) -> None:
        self.provenance_activities[provenance_activity.id] = provenance_activity
        self.proposed_changes.update({item.id: item for item in proposed_changes})

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
        self.event_semantics_previews: dict[str, bytes] = {}
        self.proposal_plans: dict[str, bytes] = {}

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

    def put_hybrid_event_semantics_preview(
        self,
        preview: HybridEventSemanticsPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        existing = self.event_semantics_previews.get(preview.id)
        assert existing is None or existing == payload
        self.event_semantics_previews[preview.id] = payload
        return object()

    def read_hybrid_event_semantics_preview(self, preview_id: str) -> bytes:
        return self.event_semantics_previews[preview_id]

    def put_hybrid_proposal_plan(
        self,
        plan: HybridProposalPlan,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        existing = self.proposal_plans.get(plan.id)
        assert existing is None or existing == payload
        self.proposal_plans[plan.id] = payload
        return object()

    def read_hybrid_proposal_plan(self, plan_id: str) -> bytes:
        return self.proposal_plans[plan_id]


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
        semantic_output: bytes | None = None,
        role_output: bytes | None = None,
        role_outputs: dict[str, tuple[bytes, ...]] | None = None,
        support_outputs: tuple[bytes, ...] | None = None,
    ) -> None:
        self.stage = stage
        self.trigger_output = trigger_output
        self.frame_output = frame_output
        self.frame_outputs = frame_outputs
        self.frame_ordinal = 0
        self.semantic_output = semantic_output
        self.role_output = role_output
        self.role_outputs = role_outputs or {}
        self.role_ordinals: dict[str, int] = {}
        self.support_outputs = support_outputs
        self.support_ordinal = 0
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
        elif self.stage == "semantics" and b"task: select_one_frame_role" in task.rendered_input:
            selected_role = next(
                line.removeprefix("select_only_frame_role: ")
                for line in task.rendered_input.decode().splitlines()
                if line.startswith("select_only_frame_role: ")
            )
            configured_role_outputs = self.role_outputs.get(selected_role)
            if configured_role_outputs is not None:
                ordinal = self.role_ordinals.get(selected_role, 0)
                output = configured_role_outputs[ordinal]
                self.role_ordinals[selected_role] = ordinal + 1
            elif (
                self.role_output is not None
                and selected_role == "classification.assigned_classification"
            ):
                output = self.role_output
            else:
                semantic_output = self.semantic_output or (
                    b"frame: classification\n"
                    b"argument: classification.classifier | c1\n"
                    b"argument: classification.classified_entity | Directive 3000.09\n"
                    b"argument: classification.assigned_classification | 3000.09\n"
                    b"qualifier: q1\n"
                    b"reason: The source presents the agency, subject, label, and time.\n"
                )
                target = next(
                    (
                        line.split(" | ", maxsplit=1)[1]
                        for line in semantic_output.decode().splitlines()
                        if line.startswith(f"argument: {selected_role} | ")
                    ),
                    None,
                )
                output = (
                    f"target: {target or 'absent'}\n"
                    "reason: The bounded fixture selects only the supplied frame role.\n"
                ).encode()
        elif self.stage == "semantics" and b"task: normalize_one_event" in task.rendered_input:
            output = self.semantic_output or (
                b"frame: classification\n"
                b"argument: classification.classifier | c1\n"
                b"argument: classification.classified_entity | "
                b"Directive 3000.09\n"
                b"argument: classification.assigned_classification | 3000.09\n"
                b"qualifier: q1\n"
                b"reason: The source presents the agency, subject, label, and time.\n"
            )
        elif (
            self.stage == "semantics"
            and b'"task":"judge_one_semantic_statement"' in task.rendered_input
        ):
            outputs = self.support_outputs or (
                b"outcome: directly_supported\n"
                b"reason: The exact source segment states the semantic component.\n",
            )
            output = outputs[self.support_ordinal % len(outputs)]
            self.support_ordinal += 1
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


def test_hp6_builds_governed_semantics_and_independent_support_evidence() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    hp4 = _run_hp4(ledger, archive, grounding.id, _Runtime("events"))
    hp5 = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(hp5, cast(HybridAtomicClaimArchive, archive))
    runtime = _Runtime("semantics")

    result = run_hybrid_event_semantics_preview(
        command=HybridEventSemanticsCommand(
            hp5.preview.id,
            ContextModelProfile("fixture-model", 4096, 256, 16),
            _generation(),
        ),
        ledger=cast(HybridEventSemanticsLedger, ledger),
        archive=cast(HybridEventSemanticsArchive, archive),
        model_runtime=runtime,
        model_run_id_factory=_RunIds("semantics"),
        tokenizer=_Tokenizer(),
        normalization_prompt_bytes=b"Select supplied governed semantics.",
        role_completion_prompt_bytes=b"Select one target for the supplied governed role.",
        support_prompt_bytes=b"Judge one statement against exact source evidence.",
    )
    publish_hybrid_event_semantics_preview(result, cast(HybridEventSemanticsArchive, archive))

    assert result.preview.terminal_status is HybridEventSemanticsStatus.COMPLETE
    assert len(result.preview.semantic_events) == 1
    assert result.preview.semantic_events[0].frame_id == "classification"
    assert {item.frame_role_id for item in result.preview.assignments} == {
        "classification.assigned_classification",
        "classification.classified_entity",
        "classification.classifier",
    }
    assert {item.upper_role.value for item in result.preview.assignments} == {
        "agent",
        "result",
        "theme",
    }
    assert any(
        item.proposed_role_labels == ("policy_establisher",) for item in result.preview.assignments
    )
    assert {item.text for item in result.preview.targets} == {
        "3000.09",
        "Department of Defense",
        "Directive 3000.09",
    }
    assert {item.text for item in result.preview.qualifiers} == {"2012"}
    assert len(result.preview.statements) == len(result.preview.judgments) == 8
    assert len(result.preview.extraction_task_ids) == len(result.preview.model_run_ids) == 13
    assert len(result.preview.traces) == 14
    role_traces = [
        item for item in result.preview.traces if item.stage_id == "hybrid_event_role_completion"
    ]
    assert {cast(dict[str, object], item.input["target_role"])["id"] for item in role_traces} == {
        "classification.assigned_classification",
        "classification.classified_entity",
        "classification.classifier",
        "classification.stated_reason",
    }
    assert all(
        item.configuration["prompt_sha256"] == result.preview.role_completion_prompt_sha256
        for item in role_traces
    )
    assert all(
        "reason" not in cast(str, trace.input.get("model_visible_task", ""))
        for trace in result.preview.traces
        if trace.stage_id == "hybrid_semantic_source_support"
    )
    assert all(
        b"policy_establisher" not in request.rendered_input for request in runtime.requests[1:]
    )
    assert ledger.accepted_state_called is False
    assert (
        load_hybrid_event_semantics_preview(
            result.preview.id,
            cast(HybridEventSemanticsLedger, ledger),
            cast(HybridEventSemanticsArchive, archive),
        )
        == result.preview
    )


def test_hp6_preview_rejects_an_assignment_from_another_event() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    result = _run_hp6_fixture(ledger, archive, hp5, _Runtime("semantics"), "cross-event")
    preview = result.preview
    event = preview.semantic_events[0]
    original = preview.assignments[0]
    alien = build_event_argument_assignment_draft(
        event_subject_id="esd_" + "f" * 24,
        frame_id=original.frame_id,
        target_id=original.target_id,
        frame_role_id=original.frame_role_id,
        upper_role=original.upper_role,
        proposed_role_labels=original.proposed_role_labels,
        support_evidence_target_id=original.support_evidence_target_id,
        source_trace_ids=original.source_trace_ids,
    )
    assignment_ids = tuple(
        alien.id if item == original.id else item for item in event.argument_assignment_ids
    )
    changed_event = build_event_semantic_draft(
        event_subject_id=event.event_subject_id,
        trigger_id=event.trigger_id,
        trigger_text=event.trigger_text,
        frame_id=event.frame_id,
        proposed_event_label=event.proposed_event_label,
        argument_assignment_ids=assignment_ids,
        qualifier_ids=event.qualifier_ids,
        polarity=event.polarity,
        modality=event.modality,
        attribution_kind=event.attribution_kind,
        attribution_target_id=event.attribution_target_id,
        support_evidence_target_id=event.support_evidence_target_id,
        normalization_task_id=event.normalization_task_id,
        normalization_model_run_id=event.normalization_model_run_id,
        normalization_trace_id=event.normalization_trace_id,
    )
    values = preview.model_dump(mode="python", exclude={"id"})
    for field in (
        "semantic_events",
        "targets",
        "assignments",
        "qualifiers",
        "gaps",
        "statements",
        "judgments",
        "traces",
    ):
        values[field] = getattr(preview, field)
    values["semantic_events"] = (changed_event,)
    values["assignments"] = tuple(
        alien if item.id == original.id else item for item in preview.assignments
    )

    with pytest.raises(ValueError, match="assignment from another event"):
        build_hybrid_event_semantics_preview(**values)


def test_hp6_invalid_normalization_contributes_no_partial_semantic_draft() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.invented | 3000.09\n"
            b"reason: This uses an invented role.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "invalid-role")

    assert result.preview.terminal_status is HybridEventSemanticsStatus.PARTIAL
    assert result.preview.semantic_events == ()
    assert result.preview.assignments == ()
    assert len(runtime.requests) == 1
    assert any(
        item.startswith("normalization_mapping_failed:") for item in result.preview.diagnostics
    )
    assert tuple(archive.model_outputs.values())[-1] == runtime.semantic_output


def test_hp6_unknown_model_frame_is_archived_as_a_partial_result() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: invented_frame\n"
            b"reason: The model invented a frame outside the governed profile.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "unknown-frame")

    assert result.preview.terminal_status is HybridEventSemanticsStatus.PARTIAL
    assert result.preview.semantic_events == ()
    assert result.preview.assignments == ()
    assert len(runtime.requests) == 1
    assert any(item.endswith(":unknown_event_frame") for item in result.preview.diagnostics)
    assert tuple(archive.model_outputs.values())[-1] == runtime.semantic_output


def test_hp6_reuses_a_unique_candidate_named_by_a_source_literal() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.classifier | Department of Defense\n"
            b"argument: classification.classified_entity | Directive 3000.09\n"
            b"argument: classification.assigned_classification | 3000.09\n"
            b"reason: The source presents a classifier, subject, and assigned label.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "candidate-reuse")

    classifier = next(
        item
        for item in result.preview.assignments
        if item.frame_role_id == "classification.classifier"
    )
    target = next(item for item in result.preview.targets if item.id == classifier.target_id)
    assert target.kind is SemanticArgumentTargetKind.MENTION_CANDIDATE
    assert target.text == "Department of Defense"
    assert target.reference_id is not None


def test_hp6_counts_a_candidate_converted_to_a_source_span_as_represented() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.assigned_classification | Department of Defense\n"
            b"reason: The candidate is used as a role that admits only a source span.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "candidate-as-span")

    assert all(item.code.value != "omitted_parent_argument" for item in result.preview.gaps)
    assignment = result.preview.assignments[0]
    target = next(item for item in result.preview.targets if item.id == assignment.target_id)
    assert target.kind is SemanticArgumentTargetKind.SOURCE_SPAN
    assert target.text == "Department of Defense"


def test_hp6_replaces_an_invalid_model_target_only_with_a_valid_bounded_completion() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.classifier | c1\n"
            b"argument: classification.classified_entity | Directive 3000.09\n"
            b"argument: classification.assigned_classification | s1\n"
            b"qualifier: q1\n"
            b"reason: The primary output contains one invalid local label.\n"
        ),
        role_output=(
            b"target: 3000.09\nreason: The bounded completion copies one exact source value.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "role-completion")

    assert len(result.preview.semantic_events) == 1
    assert any(
        item.frame_role_id == "classification.assigned_classification"
        and next(target for target in result.preview.targets if target.id == item.target_id).text
        == "3000.09"
        for item in result.preview.assignments
    )
    assert any(item.stage_id == "hybrid_event_role_completion" for item in result.preview.traces)
    assert all("normalization_mapping_failed" not in item for item in result.preview.diagnostics)


def test_hp6_reconciles_redundant_catalog_text_without_hiding_model_output() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.classified_entity | c1\n"
            b"reason: The broad proposal supplies one source-backed target.\n"
        ),
        role_outputs={
            "classification.classified_entity": (
                b"target: c1 | Department of Defense\n"
                b"reason: This repeats a supplied label and its text.\n",
            )
        },
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "role-retry")

    role_traces = [
        item
        for item in result.preview.traces
        if item.stage_id == "hybrid_event_role_completion"
        and cast(dict[str, object], item.input["target_role"])["id"]
        == "classification.classified_entity"
    ]
    assert len(role_traces) == 1
    reconciliation = next(
        item
        for item in result.preview.traces
        if item.stage_id == "hybrid_event_role_target_reconciliation"
    )
    assert reconciliation.parent_trace_ids == (role_traces[0].id,)
    assert reconciliation.configuration["rule_id"] == "redundant_catalog_label_text_v1"
    assert any(
        item.frame_role_id == "classification.classified_entity"
        and next(target for target in result.preview.targets if target.id == item.target_id).text
        == "Department of Defense"
        for item in result.preview.assignments
    )
    assert any(
        output.startswith(b"target: c1 | Department of Defense")
        for output in archive.model_outputs.values()
    )


def test_hp6_retries_one_source_invalid_role_target() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.assigned_classification | 3000.09\n"
            b"reason: The broad proposal supplies one source-backed target.\n"
        ),
        role_outputs={
            "classification.assigned_classification": (
                b"target: 3000.09.\nreason: This first target invents terminal punctuation.\n",
                b"target: 3000.09\nreason: This retry copies the exact source literal.\n",
            )
        },
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "role-retry")

    role_traces = [
        item
        for item in result.preview.traces
        if item.stage_id == "hybrid_event_role_completion"
        and cast(dict[str, object], item.input["target_role"])["id"]
        == "classification.assigned_classification"
    ]
    assert len(role_traces) == 2
    retry_trace = next(
        item
        for item in role_traces
        if "rejected_previous_target:" in cast(str, item.input["model_visible_task"])
    )
    first_trace = next(item for item in role_traces if item is not retry_trace)
    assert "rejected_previous_target: source_literal_not_unique:3000.09." in cast(
        str, retry_trace.input["model_visible_task"]
    )
    assert retry_trace.parent_trace_ids == (first_trace.id,)
    assert any(
        item.frame_role_id == "classification.assigned_classification"
        and next(target for target in result.preview.targets if target.id == item.target_id).text
        == "3000.09"
        for item in result.preview.assignments
    )


def test_hp6_does_not_reconcile_mismatched_catalog_text() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\nreason: The broad proposal identifies only the frame.\n"
        ),
        role_outputs={
            "classification.classified_entity": (
                b"target: c1 | A different entity\nreason: This catalog text does not match c1.\n",
                b"target: absent\nreason: The retry does not invent a replacement.\n",
            )
        },
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "role-mismatch")

    assert not any(
        item.stage_id == "hybrid_event_role_target_reconciliation" for item in result.preview.traces
    )
    assert any(
        item.code is SemanticCoverageGapCode.MISSING_REQUIRED_ROLE
        and item.field_value == "classification.classified_entity"
        for item in result.preview.gaps
    )


def test_hp6_governs_attribution_without_model_serialization() -> None:
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
                b"argument: c1 | policy_establisher | s1\n"
                b"qualifier: time | s1 | 2012\n"
            ),
        ),
    )
    hp5 = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(hp5, cast(HybridAtomicClaimArchive, archive))
    runtime = _Runtime("semantics")

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "parent-attribution")

    event = result.preview.semantic_events[0]
    assert event.attribution_kind is EventAttributionKind.SOURCE_NARRATOR
    assert event.attribution_target_id is None
    assert any(item.code.value == "parent_attribution_disagreement" for item in result.preview.gaps)
    assert b"attribution:" not in runtime.requests[0].rendered_input


def test_hp6_derives_reporting_attribution_from_the_governed_agent_role() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: recommendation\n"
            b"argument: recommendation.recommender | c1\n"
            b"argument: recommendation.recommended_action | established  Directive 3000.09\n"
            b"reason: The bounded fixture exercises governed reporting attribution.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "reporting-attribution")

    event = result.preview.semantic_events[0]
    assert event.attribution_kind is EventAttributionKind.MENTION_CANDIDATE
    target = next(item for item in result.preview.targets if item.id == event.attribution_target_id)
    assert target.text == "Department of Defense"
    assert any(item.code.value == "parent_attribution_disagreement" for item in result.preview.gaps)


def test_hp6_unresolved_event_is_explicit_and_does_not_guess_semantics() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: unresolved\n"
            b"reason: No supplied frame accurately represents policy establishment.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "unresolved")

    assert result.preview.terminal_status is HybridEventSemanticsStatus.PARTIAL
    assert result.preview.semantic_events == ()
    assert [item.code.value for item in result.preview.gaps] == ["unmapped_frame"]
    assert len(runtime.requests) == 1


def test_hp6_reports_missing_required_roles_and_omitted_parent_arguments() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.assigned_classification | 3000.09\n"
            b"reason: Only the classification literal was selected.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "coverage-gaps")

    assert result.preview.terminal_status is HybridEventSemanticsStatus.PARTIAL
    assert len(result.preview.semantic_events) == 1
    parent_argument_id = cast(
        str,
        next(
            item.object_reference_id
            for item in hp5.preview.atomic_claims
            if item.predicate.value == "has_argument"
        ),
    )
    assert {(item.code.value, item.field_value) for item in result.preview.gaps} == {
        ("missing_required_role", "classification.classified_entity"),
        ("missing_required_role", "classification.classifier"),
        ("omitted_parent_argument", parent_argument_id),
        ("omitted_parent_qualifier", "time:2012"),
    }


def test_hp6_quarantines_a_qualifier_not_supplied_by_the_parent_frame() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime(
        "semantics",
        semantic_output=(
            b"frame: classification\n"
            b"argument: classification.classifier | c1\n"
            b"argument: classification.classified_entity | Directive 3000.09\n"
            b"argument: classification.assigned_classification | 3000.09\n"
            b"qualifier: q999\n"
            b"reason: This incorrectly treats a place as a parent time qualifier.\n"
        ),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "invented-qualifier")

    assert len(result.preview.semantic_events) == 1
    assert result.preview.qualifiers == ()
    assert {(item.code.value, item.field_value) for item in result.preview.gaps} >= {
        ("unsupported_qualifier_proposal", "q999"),
        ("omitted_parent_qualifier", "time:2012"),
    }


def test_hp6_support_failure_is_isolated_from_later_statements() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    valid = (
        b"outcome: directly_supported\n"
        b"reason: The exact source segment states the semantic component.\n"
    )
    runtime = _Runtime(
        "semantics",
        support_outputs=(b'{"outcome":"directly_supported"}\n', *(valid for _ in range(7))),
    )

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "support-failure")

    assert result.preview.terminal_status is HybridEventSemanticsStatus.PARTIAL
    assert len(result.preview.semantic_events) == 1
    assert len(result.preview.statements) == 8
    assert len(result.preview.judgments) == 7
    assert len(runtime.requests) == 13
    assert any(item.startswith("support_task_failed:") for item in result.preview.diagnostics)


def test_hp6_blocked_parent_runs_no_model_task() -> None:
    ledger, archive, hp5 = _hp5_parent(
        _Runtime(
            "events",
            trigger_output=b"event: e1 | s1 | missing literal | invented\n",
        )
    )
    runtime = _Runtime("semantics")

    result = _run_hp6_fixture(ledger, archive, hp5, runtime, "blocked")

    assert hp5.preview.terminal_status is HybridAtomicClaimStatus.BLOCKED
    assert result.preview.terminal_status is HybridEventSemanticsStatus.BLOCKED
    assert result.preview.diagnostics == ("hp5_status:blocked",)
    assert result.preview.semantic_events == ()
    assert runtime.requests == []


def test_hp7_builds_a_reviewable_typed_graph_with_exact_lineage() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    runtime = _Runtime("semantics")
    hp6 = _run_hp6_fixture(ledger, archive, hp5, runtime, "hp7-proposed")
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )
    request_count = len(runtime.requests)

    result = run_hybrid_proposal_submission(
        preview_id=hp6.preview.id,
        submitted_at=NOW,
        ledger=ledger,
        archive=archive,
    )

    assert result.publication_disposition == "created"
    assert len(runtime.requests) == request_count
    assert len(result.plan.decisions) == 1
    decision = result.plan.decisions[0]
    assert decision.disposition is ProposalDisposition.PROPOSED
    assert decision.reason_codes == ()
    assert decision.statement_ids == tuple(sorted(item.id for item in hp6.preview.statements))
    assert decision.judgment_ids == tuple(sorted(item.id for item in hp6.preview.judgments))
    assert set(decision.model_run_ids).issubset(hp6.preview.model_run_ids)
    assert hp6.preview.semantic_events[0].normalization_trace_id in decision.source_trace_ids
    assert all(item.startswith("xst_") for item in decision.source_trace_ids)

    record_types = [
        cast(str, item.proposed_json["record_type"]) for item in result.plan.proposed_changes
    ]
    assert record_types.count("Organization") == 1
    assert record_types.count("Event") == 1
    assert record_types.count("Assertion") == 7
    event_change = next(
        item
        for item in result.plan.proposed_changes
        if item.proposed_json["record_type"] == "Event"
    )
    event = Event.model_validate_json(json.dumps(event_change.proposed_json["record"]))
    organization_change = next(
        item
        for item in result.plan.proposed_changes
        if item.proposed_json["record_type"] == "Organization"
    )
    organization = Organization.model_validate_json(
        json.dumps(organization_change.proposed_json["record"])
    )
    assert organization.name == "Department of Defense"
    assert event.participant_organization_ids == (organization.id,)

    assertions = [
        ProposedAssertion.model_validate_json(json.dumps(item.proposed_json["record"]))
        for item in result.plan.proposed_changes
        if item.proposed_json["record_type"] == "Assertion"
    ]
    role_assertions = [item for item in assertions if item.relation_label == "has_argument"]
    assert len(role_assertions) == 3
    assert any(item.object_entity_id == organization.id for item in role_assertions)
    assert any(item.object_value == "Directive 3000.09" for item in role_assertions)
    assert all(item.evidence_target_ids for item in assertions)
    for item in result.plan.proposed_changes:
        lineage = cast(dict[str, object], item.proposed_json["hybrid_lineage"])
        assert lineage["hp1_preview_id"] == hp5.preview.mention_preview_id
        assert lineage["hp2_preview_id"] == hp5.preview.reference_preview_id
        assert lineage["hp3_preview_id"] == hp5.preview.grounding_preview_id
        assert lineage["hp4_preview_id"] == hp5.preview.parent_preview_id
        assert lineage["hp5_preview_id"] == hp5.preview.id
        assert lineage["hp6_preview_id"] == hp6.preview.id
    trace = result.plan.traces[0]
    assert trace.input["event"] == hp6.preview.semantic_events[0].model_dump(mode="json")
    assert trace.output["decision"] == decision.model_dump(mode="json")
    assert trace.output["proposed_changes"]
    assert ledger.accepted_state_called is False
    assert set(ledger.proposed_changes) == {item.id for item in result.plan.proposed_changes}
    assert result.plan.provenance_activity_id in ledger.provenance_activities
    assert hybrid_proposal_plan_from_bytes(archive.proposal_plans[result.plan.id]) == result.plan
    assert load_hybrid_proposal_plan(result.plan.id, ledger, archive) == result.plan


def test_hp7_holds_non_direct_support_and_preserves_exact_data_in_and_out() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    directly_supported = (
        b"outcome: directly_supported\n"
        b"reason: The exact source segment states the semantic component.\n"
    )
    runtime = _Runtime(
        "semantics",
        support_outputs=(
            b"outcome: partially_supported\nreason: The statement overstates the source.\n",
            *(directly_supported for _ in range(7)),
        ),
    )
    hp6 = _run_hp6_fixture(ledger, archive, hp5, runtime, "hp7-held")
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )

    result = run_hybrid_proposal_submission(
        preview_id=hp6.preview.id,
        submitted_at=NOW,
        ledger=ledger,
        archive=archive,
    )

    assert result.publication_disposition == "created"
    assert result.plan.proposed_changes == ()
    assert ledger.proposed_changes == {}
    assert len(ledger.provenance_activities) == 1
    decision = result.plan.decisions[0]
    assert decision.disposition is ProposalDisposition.HELD
    assert decision.reason_codes == (ProposalAdmissionReason.NON_DIRECT_SUPPORT,)
    assert result.plan.traces[0].status.value == "rejected"
    assert result.plan.traces[0].input["judgments"] == [
        item.model_dump(mode="json") for item in hp6.preview.judgments
    ]
    assert result.plan.traces[0].output == {
        "decision": decision.model_dump(mode="json"),
        "proposed_changes": [],
    }


def test_hp7_holds_an_event_with_incomplete_support_coverage() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    directly_supported = (
        b"outcome: directly_supported\n"
        b"reason: The exact source segment states the semantic component.\n"
    )
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime(
            "semantics",
            support_outputs=(
                b'{"outcome":"directly_supported"}\n',
                *(directly_supported for _ in range(7)),
            ),
        ),
        "hp7-missing-support",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )

    plan = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)

    assert plan.decisions[0].disposition is ProposalDisposition.HELD
    assert plan.decisions[0].reason_codes == (ProposalAdmissionReason.MISSING_SUPPORT_JUDGMENT,)
    assert plan.proposed_changes == ()


def test_hp7_keeps_optional_parent_coverage_gaps_advisory() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime(
            "semantics",
            semantic_output=(
                b"frame: classification\n"
                b"argument: classification.classifier | c1\n"
                b"argument: classification.classified_entity | Directive 3000.09\n"
                b"argument: classification.assigned_classification | 3000.09\n"
                b"qualifier: q999\n"
                b"reason: The proposed qualifier is not one of the supplied qualifiers.\n"
            ),
        ),
        "hp7-advisory-gap",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )

    plan = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)

    assert plan.decisions[0].disposition is ProposalDisposition.PROPOSED
    assert plan.decisions[0].reason_codes == ()
    assert plan.decisions[0].advisory_gap_ids
    assert plan.proposed_changes


def test_hp7_reuses_identical_proposals_without_resetting_review_status() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime("semantics"),
        "hp7-reuse",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )
    first = run_hybrid_proposal_submission(
        preview_id=hp6.preview.id,
        submitted_at=NOW,
        ledger=ledger,
        archive=archive,
    )
    reviewed_id = first.plan.proposed_changes[0].id
    ledger.proposed_changes[reviewed_id] = ledger.proposed_changes[reviewed_id].model_copy(
        update={"review_status": ReviewStatus.REJECTED}
    )

    second = run_hybrid_proposal_submission(
        preview_id=hp6.preview.id,
        submitted_at=datetime(2026, 9, 2, tzinfo=UTC),
        ledger=ledger,
        archive=archive,
    )

    assert second.plan == first.plan
    assert second.sha256 == first.sha256
    assert second.publication_disposition == "reused"
    assert ledger.proposed_changes[reviewed_id].review_status is ReviewStatus.REJECTED
    assert len(ledger.proposed_changes) == len(first.plan.proposed_changes)
    assert len(ledger.provenance_activities) == 1


def test_hp7_reuses_one_typed_target_across_multiple_event_bundles() -> None:
    ledger, archive, _, grounding = _parent_evidence()
    hp4 = _run_hp4(
        ledger,
        archive,
        grounding.id,
        _Runtime(
            "events",
            trigger_output=(
                b"event: e1 | s1 | announced | announcement\n"
                b"event: e2 | s1 | established | policy_establishment\n"
            ),
            frame_outputs=(
                b"event: e1\n"
                b"polarity: affirmed\n"
                b"modality: actual\n"
                b"attribution: source_narrator\n"
                b"argument: c1 | actor | s1\n",
                b"event: e2\n"
                b"polarity: affirmed\n"
                b"modality: actual\n"
                b"attribution: source_narrator\n"
                b"argument: c1 | actor | s1\n",
            ),
        ),
    )
    hp5 = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(hp5, cast(HybridAtomicClaimArchive, archive))
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime("semantics"),
        "hp7-shared-target",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )

    result = run_hybrid_proposal_submission(
        preview_id=hp6.preview.id,
        submitted_at=NOW,
        ledger=ledger,
        archive=archive,
    )

    organization_changes = [
        item
        for item in result.plan.proposed_changes
        if item.proposed_json["record_type"] == "Organization"
    ]
    assert len(result.plan.decisions) == 2
    assert len(organization_changes) == 1
    assert all(
        organization_changes[0].id in item.proposed_change_ids for item in result.plan.decisions
    )


def test_hp7_gold_event_enters_accepted_state_only_through_existing_review() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime("semantics"),
        "hp7-review-gold",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )
    result = run_hybrid_proposal_submission(
        preview_id=hp6.preview.id,
        submitted_at=NOW,
        ledger=ledger,
        archive=archive,
    )
    organization_change = next(
        item
        for item in result.plan.proposed_changes
        if item.proposed_json["record_type"] == "Organization"
    )
    event_change = next(
        item
        for item in result.plan.proposed_changes
        if item.proposed_json["record_type"] == "Event"
    )
    review_ledger = cast(ProposedChangeReviewLedger, ledger)

    approve_proposed_change(
        ReviewProposedChangeInput(
            organization_change.id,
            "fixture-reviewer",
            datetime(2026, 9, 2, tzinfo=UTC),
        ),
        review_ledger,
    )
    event_review = approve_proposed_change(
        ReviewProposedChangeInput(
            event_change.id,
            "fixture-reviewer",
            datetime(2026, 9, 2, tzinfo=UTC),
        ),
        review_ledger,
    )

    assert event_review.review_status is ReviewStatus.APPROVED
    assert event_review.accepted_record_id in ledger.events
    assert ledger.proposed_changes[event_change.id].review_status is ReviewStatus.APPROVED
    evidence = cast(dict[str, object], event_change.proposed_json["evidence"])
    assert evidence["exact_text"] == PARAGRAPH
    review_provenance = ledger.provenance_activities[event_review.provenance_activity_id]
    assert review_provenance.input_ids == (event_change.id,)
    assert event_review.accepted_record_id in review_provenance.output_ids


def test_hp7_reviewer_can_reject_a_fully_supported_event_without_accepted_state() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime("semantics"),
        "hp7-review-false",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )
    result = run_hybrid_proposal_submission(
        preview_id=hp6.preview.id,
        submitted_at=NOW,
        ledger=ledger,
        archive=archive,
    )
    event_change = next(
        item
        for item in result.plan.proposed_changes
        if item.proposed_json["record_type"] == "Event"
    )

    review = reject_proposed_change(
        ReviewProposedChangeInput(
            event_change.id,
            "fixture-reviewer",
            datetime(2026, 9, 2, tzinfo=UTC),
            reason="The source reports uncertainty, not a recommendation.",
        ),
        cast(ProposedChangeReviewLedger, ledger),
    )

    assert review.review_status is ReviewStatus.REJECTED
    assert ledger.proposed_changes[event_change.id].review_status is ReviewStatus.REJECTED
    assert ledger.events == {}


def test_hp7_parent_tampering_stops_before_archive_or_ledger_mutation() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime("semantics"),
        "hp7-tamper",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )
    archive.event_semantics_previews[hp6.preview.id] += b"\n"

    with pytest.raises(ValueError, match="canonical encoding"):
        run_hybrid_proposal_submission(
            preview_id=hp6.preview.id,
            submitted_at=NOW,
            ledger=ledger,
            archive=archive,
        )

    assert archive.proposal_plans == {}
    assert ledger.proposed_changes == {}
    assert ledger.provenance_activities == {}


def test_hp7_retains_an_unmapped_hp5_event_as_a_plan_diagnostic() -> None:
    ledger, archive, hp5 = _hp5_parent(_Runtime("events"))
    hp6 = _run_hp6_fixture(
        ledger,
        archive,
        hp5,
        _Runtime(
            "semantics",
            semantic_output=(
                b"frame: unresolved\n"
                b"reason: No governed frame accurately represents the source event.\n"
            ),
        ),
        "hp7-unmapped",
    )
    publish_hybrid_event_semantics_preview(
        hp6,
        cast(HybridEventSemanticsArchive, archive),
    )

    plan = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)

    assert plan.decisions == ()
    assert plan.proposed_changes == ()
    assert len(plan.diagnostics) == 1
    assert plan.diagnostics[0].startswith("unmaterialized_event_subject:")
    assert ":unmapped_frame:" in plan.diagnostics[0]


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


def _hp5_parent(
    runtime: _Runtime,
) -> tuple[_Ledger, _Archive, HybridAtomicClaimResult]:
    ledger, archive, _, grounding = _parent_evidence()
    hp4 = _run_hp4(ledger, archive, grounding.id, runtime)
    hp5 = run_hybrid_atomic_claim_preview(
        command=HybridAtomicClaimCommand(hp4.preview.id, NOW),
        ledger=cast(HybridAtomicClaimLedger, ledger),
        archive=cast(HybridAtomicClaimArchive, archive),
    )
    publish_hybrid_atomic_claim_preview(hp5, cast(HybridAtomicClaimArchive, archive))
    return ledger, archive, hp5


def _run_hp6_fixture(
    ledger: _Ledger,
    archive: _Archive,
    hp5: HybridAtomicClaimResult,
    runtime: _Runtime,
    run_prefix: str,
) -> HybridEventSemanticsResult:
    return run_hybrid_event_semantics_preview(
        command=HybridEventSemanticsCommand(
            hp5.preview.id,
            ContextModelProfile("fixture-model", 4096, 256, 16),
            _generation(),
        ),
        ledger=cast(HybridEventSemanticsLedger, ledger),
        archive=cast(HybridEventSemanticsArchive, archive),
        model_runtime=runtime,
        model_run_id_factory=_RunIds(run_prefix),
        tokenizer=_Tokenizer(),
        normalization_prompt_bytes=b"Select supplied governed semantics.",
        role_completion_prompt_bytes=b"Select one target for the supplied governed role.",
        support_prompt_bytes=b"Judge one statement against exact source evidence.",
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
