from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    ContextModelProfile,
    ExecutionSetting,
    HybridEntityGroundingStatus,
    HybridEventSemanticsCommand,
    HybridEventTriggerCommand,
    HybridEventTriggerResult,
    HybridEventTriggerStatus,
    HybridMentionPreviewCommand,
    HybridProposalPlan,
    HybridReferencePreviewCommand,
    MentionProposal,
    MentionProposalBatch,
    MentionProposalInput,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelTaskRequest,
    ModelTaskResponse,
    NaturalLanguageInferenceExecution,
    NaturalLanguageInferenceInput,
    PlannedProposedChange,
    ProposalDisposition,
    SemanticCoverageGapCode,
    build_hybrid_entity_grounding_preview_record,
    build_hybrid_proposal_plan,
    build_hybrid_proposal_plan_record,
    canonical_hybrid_entity_grounding_preview_bytes,
    canonical_hybrid_event_semantics_preview_bytes,
    generation_parameters_digest,
    model_identity_snapshot_digest,
    run_hybrid_event_semantics_preview,
    run_hybrid_event_trigger_preview,
    run_hybrid_mention_preview,
    run_hybrid_reference_preview,
)
from kotekomi_application.hybrid_document_references import HybridReferencePreview
from kotekomi_application.hybrid_event_semantics import HybridEventSemanticsPreview
from kotekomi_application.hybrid_event_semantics_preview import (
    HybridEventSemanticsArchive,
    HybridEventSemanticsLedger,
)
from kotekomi_application.hybrid_event_trigger_preview import (
    HybridEventTriggerArchive,
    HybridEventTriggerLedger,
)
from kotekomi_application.hybrid_event_triggers import HybridEventTriggerPreview
from kotekomi_application.hybrid_mention_interpretation import HybridExtractionPreview
from kotekomi_application.hybrid_mention_preview import HybridMentionArchive, HybridMentionLedger
from kotekomi_application.hybrid_reference_preview import (
    HybridReferenceArchive,
    HybridReferenceLedger,
)
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
    HybridEventStructuralPredicate,
    ModelRun,
    Organization,
    ParseQualityReport,
    ProposedChange,
    ProvenanceActivity,
    RepresentationAnalyzability,
    SemanticArgumentTargetKind,
    Source,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 9, 7, tzinfo=UTC)
type JsonObject = dict[str, JsonValue]


class _Tokenizer:
    tokenizer_id = "fixture_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())


class _NliRuntime:
    def classify(self, request: NaturalLanguageInferenceInput) -> NaturalLanguageInferenceExecution:
        assert request.premise
        assert request.hypothesis
        return NaturalLanguageInferenceExecution(
            model_id="fixture-nli",
            model_revision="v1",
            resource_identity="fixture-nli-resource",
            contradiction_score=0.01,
            entailment_score=0.98,
            neutral_score=0.01,
            elapsed_milliseconds=1,
        )


class _RunIds:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.ordinal = 0

    def new_model_run_id(self) -> str:
        self.ordinal += 1
        return f"mrn_{self.prefix}_{self.ordinal}"


class _MentionProposer:
    def __init__(self, mentions: tuple[tuple[str, str], ...]) -> None:
        self.mentions = mentions

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        segment = proposal_input.source_segments[0]
        proposals: list[MentionProposal] = []
        for text, kind in self.mentions:
            start = segment.exact_text.index(text)
            proposals.append(
                MentionProposal(
                    segment.label,
                    text,
                    start,
                    start + len(text),
                    (kind,),
                    0.95,
                )
            )
        return MentionProposalBatch(
            proposer_id="fixture-gliner",
            model_id="fixture-gliner",
            model_revision="v1",
            configuration=(),
            load_elapsed_milliseconds=0,
            inference_elapsed_milliseconds=0,
            proposals=tuple(proposals),
        )


class _Runtime:
    def __init__(
        self,
        *,
        mentions: tuple[tuple[str, str], ...],
        trigger_output: bytes,
        semantic_output: bytes | dict[str, bytes],
    ) -> None:
        self.mentions = mentions
        self.trigger_output = trigger_output
        self.semantic_output = semantic_output
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

    @property
    def tokenizer_id(self) -> str:
        return self._identity.tokenizer_id

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode().split())

    def inspect_model_input(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        return ModelInputMeasurement(
            model_identity_digest=model_identity_snapshot_digest(request.model_identity),
            runtime_identity=self._identity.runtime,
            model_instance_id=self._identity.name,
            tokenizer_id=self.tokenizer_id,
            prompt_template_identity="fixture_no_prompt_template_v1",
            logical_input_digest=request.logical_input_digest,
            formatted_input_digest=request.logical_input_digest,
            formatted_input_token_count=self.count_tokens(request.logical_input),
            loaded_context_limit=65_536,
        )

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        rendered = task.rendered_input
        if b"task: propose_mentions" in rendered:
            output = b"".join(
                f"mention: s1 | {kind} | {text}\n".encode() for text, kind in self.mentions
            )
        elif b"task: interpret_mention" in rendered:
            candidate_text = next(
                line.removeprefix("candidate_text: ")
                for line in rendered.decode().splitlines()
                if line.startswith("candidate_text: ")
            )
            kind = dict(self.mentions)[candidate_text]
            contextual_kind = "person" if kind == "person" else "organization"
            output = (
                "candidate: c1\n"
                "referentiality: specific_entity\n"
                f"contextual_kind: {contextual_kind}\n"
                "discourse_role: actor\n"
                "support: s1\n"
            ).encode()
        elif b"task: detect_event_trigger_occurrences" in rendered:
            output = self.trigger_output
        elif b"task: select_one_event_frame" in rendered:
            output = self._frame_selection_output(rendered)
        elif b"task: select_one_frame_role" in rendered:
            output = self._role_selection_output(rendered)
        elif b"task: classify_one_event_presentation" in rendered:
            output = self._presentation_output(rendered)
        elif b'"task":"judge_one_semantic_statement"' in rendered:
            output = (
                b"outcome: directly_supported\n"
                b"reason: The exact source segment directly states this component.\n"
            )
        else:
            raise AssertionError(f"Unexpected fixture model task: {rendered!r}")
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
                input_token_count=task.input_admission.formatted_input_token_count,
                output_token_count=len(output.decode().split()),
            ),
        )

    def _semantic_lines(self, rendered: bytes) -> tuple[str, ...]:
        if isinstance(self.semantic_output, bytes):
            output = self.semantic_output
        else:
            trigger = next(
                line.removeprefix("target_trigger: ")
                for line in rendered.decode().splitlines()
                if line.startswith("target_trigger: ")
            )
            output = self.semantic_output[trigger]
        return tuple(output.decode().splitlines())

    def _frame_selection_output(self, rendered: bytes) -> bytes:
        frame = next(
            (line for line in self._semantic_lines(rendered) if line.startswith("frame: ")),
            "frame: unresolved",
        )
        reason = next(
            (
                line
                for line in reversed(self._semantic_lines(rendered))
                if line.startswith("reason: ")
            ),
            "reason: The fixture has no governed frame decision.",
        )
        return f"{frame}\n{reason}\n".encode()

    def _role_selection_output(self, rendered: bytes) -> bytes:
        target_role = next(
            line.removeprefix("target_role: ").split(" | ", maxsplit=1)[0]
            for line in rendered.decode().splitlines()
            if line.startswith("target_role: ")
        )
        argument = next(
            (
                line.removeprefix(f"argument: {target_role} | ")
                for line in self._semantic_lines(rendered)
                if line.startswith(f"argument: {target_role} | ")
            ),
            "absent",
        )
        return (f"target: {argument}\nreason: The fixture selected only {target_role}.\n").encode()

    def _presentation_output(self, rendered: bytes) -> bytes:
        prefixes = ("polarity: ", "modality: ", "attribution: ", "qualifier: ")
        lines = [line for line in self._semantic_lines(rendered) if line.startswith(prefixes)]
        reason = next(
            (
                line
                for line in reversed(self._semantic_lines(rendered))
                if line.startswith("reason: ")
            ),
            "reason: The fixture classified only event presentation.",
        )
        return ("\n".join((*lines, reason)) + "\n").encode()


class _Ledger:
    def __init__(self, text: str) -> None:
        self.source = Source(
            id="src_hsq6_fixture",
            source_type=SourceType.MANUAL_FILE,
            identity_policy_id="fixture_v1",
            canonical_identity_key="hsq6-fixture",
        )
        self.document = Document(
            id="doc_hsq6_fixture",
            source_id=self.source.id,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        self.bundle = _bundle(self.document.id, text)
        self.manifests: dict[str, ContextManifestArtifact] = {}
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.evidence_targets: dict[str, EvidenceTarget] = {}
        self.evidence_attempts: dict[str, EvidenceValidationAttempt] = {}
        self.proposed_changes: dict[str, ProposedChange] = {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}
        self.actors: dict[str, Actor] = {}
        self.organizations: dict[str, Organization] = {}
        self.events: dict[str, Event] = {}
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
        raise AssertionError("Derived extraction must not create accepted state.")


class _Archive:
    def __init__(self) -> None:
        self.model_outputs: dict[str, bytes] = {}
        self.mention_previews: dict[str, bytes] = {}
        self.reference_previews: dict[str, bytes] = {}
        self.grounding_previews: dict[str, bytes] = {}
        self.trigger_previews: dict[str, bytes] = {}
        self.semantic_previews: dict[str, bytes] = {}
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

    def put_hybrid_event_trigger_preview(
        self,
        preview: HybridEventTriggerPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        self.trigger_previews[preview.id] = payload
        return object()

    def read_hybrid_event_trigger_preview(self, preview_id: str) -> bytes:
        return self.trigger_previews[preview_id]

    def put_hybrid_event_semantics_preview(
        self,
        preview: HybridEventSemanticsPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        self.semantic_previews[preview.id] = payload
        return object()

    def read_hybrid_event_semantics_preview(self, preview_id: str) -> bytes:
        return self.semantic_previews[preview_id]

    def put_hybrid_proposal_plan(
        self,
        plan: HybridProposalPlan,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        self.proposal_plans[plan.id] = payload
        return object()

    def read_hybrid_proposal_plan(self, plan_id: str) -> bytes:
        return self.proposal_plans[plan_id]


def test_source_bound_event_reaches_review_without_accepted_state() -> None:
    text = 'Events\nDario Amodei criticized Stargate as "chaotic" in January 2025.'
    mentions = (("Dario Amodei", "person"), ("Stargate", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | criticism\n",
        semantic_output=(
            b"frame: criticism\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: criticism.critic | c1\n"
            b"argument: criticism.target | c2\n"
            b"argument: criticism.assessment | o6\n"
            b"qualifier: time | at | o8-o9\n"
            b"reason: The source explicitly states the criticism.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)
    plan = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)

    assert hp4.preview.terminal_status is HybridEventTriggerStatus.PARTIAL
    assert [item.text for item in hp4.preview.triggers] == ["criticized"]
    assert len(hp6.preview.semantic_events) == 1
    assert hp6.preview.semantic_events[0].frame_id == "criticism"
    assert {item.text for item in hp6.preview.targets} >= {
        "Dario Amodei",
        "Stargate",
        "chaotic",
    }
    time_qualifier = hp6.preview.qualifiers[0]
    assert time_qualifier.temporal_relation is not None
    assert time_qualifier.temporal_relation.value == "at"
    assert any(
        item.code is SemanticCoverageGapCode.MISSING_OPTIONAL_ROLE for item in hp6.preview.gaps
    )
    role_requests = tuple(
        request
        for request in runtime.requests
        if request.task_type == "hybrid_event_role_selection"
    )
    frame_requests = tuple(
        request
        for request in runtime.requests
        if request.task_type == "hybrid_event_frame_selection"
    )
    assert len(frame_requests) == 1
    assert b"governed_frame_catalog:" in frame_requests[0].rendered_input
    assert b"target_role:" not in frame_requests[0].rendered_input
    assert b"role |" not in frame_requests[0].rendered_input
    assert len(role_requests) == 5
    assert all(request.rendered_input.count(b"target_role: ") == 1 for request in role_requests)
    presentation_requests = tuple(
        request for request in runtime.requests if request.task_type == "hybrid_event_presentation"
    )
    assert len(presentation_requests) == 1
    assert b"selected_role_targets:" in presentation_requests[0].rendered_input
    assert b"target_role:" not in presentation_requests[0].rendered_input
    support_requests = tuple(
        request
        for request in runtime.requests
        if request.task_type == "hybrid_semantic_source_support"
    )
    assert len(support_requests) == 1
    assert b'"task":"judge_one_semantic_statement"' in support_requests[0].rendered_input
    event_requests = tuple(
        request for request in runtime.requests if request.task_type.startswith("hybrid_event_")
    )
    assert event_requests
    assert all(b"[heading]" not in request.rendered_input for request in event_requests)
    assert all(
        b'Dario Amodei criticized Stargate as "chaotic" in January 2025.' in request.rendered_input
        for request in event_requests
    )
    assert plan.decisions[0].disposition is ProposalDisposition.PROPOSED
    assert any(item.proposed_json.get("record_type") == "Event" for item in plan.proposed_changes)
    assert ledger.accepted_state_called is False
    assert not ledger.actors
    assert not ledger.organizations
    assert not ledger.events


def test_bounded_publication_roles_retain_an_optional_outlet() -> None:
    text = "Events\nDario Amodei wrote an op-ed in The New York Times about AI regulation."
    mentions = (("Dario Amodei", "person"), ("The New York Times", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | publication\n",
        semantic_output=(
            b"frame: publication\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: publication.publisher | c1\n"
            b"argument: publication.published_work | o4-o5\n"
            b"argument: publication.outlet | c2\n"
            b"argument: publication.topic | o12-o13\n"
            b"reason: The source explicitly states the publication.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)

    role_targets = {
        item.frame_role_id: next(
            target.text for target in hp6.preview.targets if target.id == item.target_id
        )
        for item in hp6.preview.assignments
    }
    assert role_targets == {
        "publication.outlet": "The New York Times",
        "publication.published_work": "an op-ed",
        "publication.publisher": "Dario Amodei",
        "publication.topic": "AI regulation",
    }


def test_trigger_discovery_retains_distinct_publication_and_characterization_events() -> None:
    text = "Events\nAmodei wrote an op-ed describing Trump as a feudal warlord."
    mentions = (("Amodei", "person"), ("Trump", "person"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=(b"event: o2 | publication\nevent: o5 | characterization\n"),
        semantic_output=b"",
    )

    _, _, hp4 = _run_to_triggers(text, mentions, runtime)

    assert [item.text for item in hp4.preview.triggers] == [
        "wrote",
        "describing",
    ]


def test_unknown_trigger_occurrence_does_not_erase_a_valid_selection() -> None:
    text = "Events\nDario Amodei criticized Stargate."
    mentions = (("Dario Amodei", "person"), ("Stargate", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=(b"event: o3 | criticism\nevent: o999 | criticism\n"),
        semantic_output=b"",
    )

    _, _, hp4 = _run_to_triggers(text, mentions, runtime)

    assert [item.text for item in hp4.preview.triggers] == ["criticized"]
    assert any(item.endswith(":2:unknown_occurrence_id") for item in hp4.preview.diagnostics)


def test_composite_source_target_retains_contained_entity_reference() -> None:
    text = "Events\n1789 Capital abandoned an investment in Anthropic."
    mentions = (("1789 Capital", "organization"), ("Anthropic", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | investment_abandonment\n",
        semantic_output=(
            b"frame: investment_abandonment\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: investment_abandonment.disinvestor | c1\n"
            b"argument: investment_abandonment.abandoned_asset | o4-o7\n"
            b"argument: investment_abandonment.investee | c2\n"
            b"reason: The source explicitly states the abandoned investment.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)
    plan = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)

    composite = next(
        item for item in hp6.preview.targets if item.kind is SemanticArgumentTargetKind.SOURCE_SPAN
    )
    assert composite.text == "an investment in Anthropic"
    assert len(composite.embedded_candidate_ids) == 1
    organization = next(
        item
        for item in plan.proposed_changes
        if item.proposed_json.get("record_type") == "Organization"
        and cast(JsonObject, item.proposed_json["record"]).get("name") == "Anthropic"
    )
    organization_evidence = cast(JsonObject, organization.proposed_json["evidence"])
    assert organization_evidence["exact_text"] == "Anthropic"
    record_ids = [
        cast(JsonObject, item.proposed_json["record"])["id"] for item in plan.proposed_changes
    ]
    assert len(set(record_ids)) == len(record_ids)
    conflicting_json = cast(
        JsonObject,
        json.loads(json.dumps(organization.proposed_json)),
    )
    conflicting_evidence = cast(JsonObject, conflicting_json["evidence"])
    conflicting_evidence["prefix_text"] = "different source selector"
    canonical = json.dumps(
        conflicting_json,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    conflicting = PlannedProposedChange(
        id=(
            "pcg_"
            + hashlib.sha256(
                f"{organization.provenance_activity_id}\x1f{canonical}".encode()
            ).hexdigest()[:24]
        ),
        proposed_json=conflicting_json,
        source_id=organization.source_id,
        document_id=organization.document_id,
        provenance_activity_id=organization.provenance_activity_id,
    )
    with pytest.raises(ValueError, match="planned record identities must be distinct"):
        build_hybrid_proposal_plan_record(
            parent_preview_id=plan.parent_preview_id,
            parent_preview_sha256=plan.parent_preview_sha256,
            representation_id=plan.representation_id,
            paragraph_node_id=plan.paragraph_node_id,
            provenance_activity_id=plan.provenance_activity_id,
            decisions=plan.decisions,
            proposed_changes=tuple(
                sorted((*plan.proposed_changes, conflicting), key=lambda item: item.id)
            ),
            traces=plan.traces,
            diagnostics=plan.diagnostics,
        )
    structural: list[PlannedProposedChange] = []
    for item in plan.proposed_changes:
        record = cast(JsonObject, item.proposed_json["record"])
        if (
            record.get("relation_label")
            == HybridEventStructuralPredicate.HAS_ARGUMENT_ENTITY_REFERENCE.value
        ):
            structural.append(item)
    assert len(structural) == 1
    structural_record = cast(JsonObject, structural[0].proposed_json["record"])
    assert structural_record["qualifiers"] == {
        "frame_role_id": "investment_abandonment.abandoned_asset",
        "upper_role": "theme",
    }


def test_two_governed_events_in_one_source_segment_retain_distinct_semantics() -> None:
    text = (
        "Events\nThe dispute caused 1789 Capital, a venture capital firm associated with "
        "Donald Trump Jr., to abandon an investment in Anthropic worth hundreds of "
        "millions of dollars."
    )
    mentions = (
        ("The dispute", "event"),
        ("1789 Capital", "organization"),
        ("Donald Trump Jr.", "person"),
        ("Anthropic", "organization"),
    )
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=(b"event: o3 | caused_change\nevent: o16 | abandon_investment\n"),
        semantic_output={
            "caused": (
                b"frame: causation\n"
                b"polarity: affirmed\n"
                b"modality: actual\n"
                b"attribution: source_narrator\n"
                b"argument: causation.cause | o2\n"
                b"argument: causation.effect | o16-o26\n"
                b"reason: The dispute explicitly caused the abandoned investment.\n"
            ),
            "abandon": (
                b"frame: investment_abandonment\n"
                b"polarity: affirmed\n"
                b"modality: actual\n"
                b"attribution: source_narrator\n"
                b"argument: investment_abandonment.disinvestor | c2\n"
                b"argument: investment_abandonment.abandoned_asset | o18-o26\n"
                b"argument: investment_abandonment.investee | c4\n"
                b"reason: The source explicitly states the abandoned investment.\n"
            ),
        },
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)

    assert sorted(item.frame_id for item in hp6.preview.semantic_events) == [
        "causation",
        "investment_abandonment",
    ]
    assert len(hp6.preview.propositions) == 2
    assert len(hp6.preview.proposition_decisions) == 2
    assert len(hp6.preview.judgments) == 2
    assert len(hp6.preview.statements) > len(hp6.preview.judgments)
    judged_statement_ids = {item.statement_id for item in hp6.preview.judgments}
    assert judged_statement_ids == {
        item.id for item in hp6.preview.statements if item.kind.value == "complete_proposition"
    }


def test_composite_source_target_excludes_a_partially_contained_entity() -> None:
    text = "Events\n1789 Capital abandoned an Anthropic investment."
    mentions = (("1789 Capital", "organization"), ("Anthropic investment", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | investment_abandonment\n",
        semantic_output=(
            b"frame: investment_abandonment\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: investment_abandonment.disinvestor | c1\n"
            b"argument: investment_abandonment.abandoned_asset | o6\n"
            b"reason: The source explicitly states the abandoned investment.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)

    composite = next(item for item in hp6.preview.targets if item.text == "investment")
    assert composite.embedded_candidate_ids == ()


def test_invalid_optional_line_does_not_erase_a_valid_event() -> None:
    text = 'Events\nDario Amodei criticized Stargate as "chaotic".'
    mentions = (("Dario Amodei", "person"), ("Stargate", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | criticism\n",
        semantic_output=(
            b"frame: criticism\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: criticism.critic | c1\n"
            b"qualifier: time | eventually | o1-o2\n"
            b"argument: criticism.target | c2\n"
            b"reason: The source explicitly states the criticism.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)

    assert len(hp6.preview.semantic_events) == 1
    assert any(
        item.code is SemanticCoverageGapCode.INVALID_OPTIONAL_LINE for item in hp6.preview.gaps
    )


def test_invalid_required_envelope_produces_a_typed_event_gap() -> None:
    text = "Events\nDario Amodei criticized Stargate."
    mentions = (("Dario Amodei", "person"), ("Stargate", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | criticism\n",
        semantic_output=(
            b"frame: criticism\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"argument: criticism.critic | c1\n"
            b"argument: criticism.target | c2\n"
            b"reason: The source explicitly states the criticism.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)

    assert hp6.preview.semantic_events == ()
    assert any(
        item.code is SemanticCoverageGapCode.INVALID_REQUIRED_ENVELOPE for item in hp6.preview.gaps
    )


def test_relationship_termination_outside_the_profile_remains_a_typed_ontology_gap() -> None:
    text = "Events\nDario Amodei cut ties with Skadden."
    mentions = (("Dario Amodei", "person"), ("Skadden", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o3 | relationship_termination\n",
        semantic_output=(
            b"frame: unresolved\nreason: No governed frame represents relationship termination.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)

    assert hp6.preview.semantic_events == ()
    assert [item.code for item in hp6.preview.gaps] == [SemanticCoverageGapCode.UNMAPPED_FRAME]
    assert [
        request.task_type
        for request in runtime.requests
        if request.task_type
        in {
            "hybrid_event_frame_selection",
            "hybrid_event_role_selection",
            "hybrid_event_presentation",
            "hybrid_semantic_source_support",
        }
    ] == ["hybrid_event_frame_selection"]


def test_governed_task_exposes_resolved_reference_metadata_without_transferring_identity() -> None:
    text = "Events\nThe New York Times (NYT) published an op-ed."
    mentions = (("The New York Times", "organization"), ("NYT", "organization"))
    runtime = _Runtime(
        mentions=mentions,
        trigger_output=b"event: o6 | publication\n",
        semantic_output=(
            b"frame: publication\n"
            b"polarity: affirmed\n"
            b"modality: actual\n"
            b"attribution: source_narrator\n"
            b"argument: publication.publisher | c2\n"
            b"argument: publication.published_work | o7-o8\n"
            b"reason: The source explicitly states the publication.\n"
        ),
    )

    ledger, archive, hp4 = _run_to_triggers(text, mentions, runtime)
    hp6 = _run_semantics(ledger, archive, hp4, runtime)
    plan = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)

    role_selection = next(
        request
        for request in runtime.requests
        if request.task_type == "hybrid_event_role_selection"
        and b"target_role: publication.publisher" in request.rendered_input
    )
    assert b"c2 | resolved | New York Times" in role_selection.rendered_input
    proposed_organizations = (
        cast(JsonObject, item.proposed_json["record"])
        for item in plan.proposed_changes
        if item.proposed_json.get("record_type") == "Organization"
    )
    assert any(item.get("name") == "New York Times" for item in proposed_organizations)


def _run_to_triggers(
    text: str,
    mentions: tuple[tuple[str, str], ...],
    runtime: _Runtime,
) -> tuple[_Ledger, _Archive, HybridEventTriggerResult]:
    ledger = _Ledger(text)
    archive = _Archive()
    mention = run_hybrid_mention_preview(
        command=HybridMentionPreviewCommand(
            representation_id=ledger.bundle.representation.id,
            paragraph_node_id="nod_hsq6_paragraph",
            model_profile=ContextModelProfile("fixture-model", 4096, 256, 16),
            generation_parameters=_generation(),
        ),
        ledger=cast(HybridMentionLedger, ledger),
        archive=cast(HybridMentionArchive, archive),
        proposer=_MentionProposer(mentions),
        model_runtime=runtime,
        model_run_id_factory=_RunIds("mention"),
        tokenizer=_Tokenizer(),
        prompt_bytes=b"Perform only the named mention task.",
        ontology_card_bytes=b"Classify people and organizations from exact source text.",
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
    archive.grounding_previews[grounding.id] = canonical_hybrid_entity_grounding_preview_bytes(
        grounding
    )
    hp4 = run_hybrid_event_trigger_preview(
        command=HybridEventTriggerCommand(
            grounding.id,
            ContextModelProfile("fixture-model", 4096, 256, 16),
            _generation(),
        ),
        ledger=cast(HybridEventTriggerLedger, ledger),
        archive=cast(HybridEventTriggerArchive, archive),
        model_runtime=runtime,
        model_run_id_factory=_RunIds("trigger"),
        tokenizer=_Tokenizer(),
        trigger_prompt_bytes=b"Detect every explicit event trigger.",
    )
    return ledger, archive, hp4


def _run_semantics(
    ledger: _Ledger,
    archive: _Archive,
    hp4: HybridEventTriggerResult,
    runtime: _Runtime,
):
    result = run_hybrid_event_semantics_preview(
        command=HybridEventSemanticsCommand(
            hp4.preview.id,
            ContextModelProfile("fixture-model", 4096, 256, 16),
            _generation(),
        ),
        ledger=cast(HybridEventSemanticsLedger, ledger),
        archive=cast(HybridEventSemanticsArchive, archive),
        model_runtime=runtime,
        model_run_id_factory=_RunIds("semantic"),
        tokenizer=_Tokenizer(),
        frame_selection_prompt_bytes=b"Select one governed event frame.",
        role_selection_prompt_bytes=b"Select one target for one governed role.",
        presentation_prompt_bytes=b"Classify one event presentation.",
        support_prompt_bytes=b"Judge source support for one governed statement.",
        nli_runtime=_NliRuntime(),
    )
    payload = canonical_hybrid_event_semantics_preview_bytes(result.preview)
    archive.put_hybrid_event_semantics_preview(result.preview, payload, result.sha256)
    return result


def _generation() -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting("max_output_tokens", 256),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )


def _bundle(document_id: str, text: str) -> DocumentRepresentationBundle:
    representation_id = "rep_hsq6_fixture"
    text_view = TextView(
        id="tvw_hsq6_fixture",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    heading_end = text.index("\n")
    paragraph_start = heading_end + 1
    root = DocumentNode(
        id="nod_hsq6_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    heading = DocumentNode(
        id="nod_hsq6_heading",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="heading",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=heading_end,
    )
    paragraph = DocumentNode(
        id="nod_hsq6_paragraph",
        representation_id=representation_id,
        parent_node_id=heading.id,
        node_type="paragraph",
        order_index=2,
        text_view_id=text_view.id,
        start_char=paragraph_start,
        end_char=len(text),
    )
    quality = ParseQualityReport(
        id="pqr_hsq6_fixture",
        representation_id=representation_id,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document_id,
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_hsq6_fixture",
        input_blob_digest=hashlib.sha256(text.encode()).hexdigest(),
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
