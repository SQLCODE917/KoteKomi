from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import cast

from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    ContextModelProfile,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventTriggerDraft,
    ExecutionSetting,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelTaskRequest,
    ModelTaskResponse,
    PropositionScopeStatus,
    SourceGroundedEventDraft,
    SourceSegmentAnalysisUnitInput,
    build_proposition_fragment_candidates,
    build_source_grounded_event_draft,
    create_analysis_unit_from_source_segment,
    generation_parameters_digest,
    model_identity_snapshot_digest,
    paragraph_source_segments,
)
from kotekomi_application.hybrid_event_triggers import event_trigger_id
from kotekomi_application.source_grounded_proposition_preview import (
    MarkerFreePropositionMembershipCommand,
    PropositionScopeCommand,
    PropositionScopeLedger,
    PropositionScopeResult,
    run_marker_free_proposition_fragment_membership,
    run_source_grounded_proposition_scope,
)
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
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

NOW = datetime(2026, 9, 17, tzinfo=UTC)
SOURCE_TEXT = "Sacks stated that Anthropic was running a strategy."


class FixtureLedger:
    def __init__(self, source_text: str = SOURCE_TEXT) -> None:
        self.source = Source(
            id="src_proposition_preview",
            source_type=SourceType.MANUAL_FILE,
            identity_policy_id="fixture",
            canonical_identity_key="proposition-preview",
        )
        self.document = Document(
            id="doc_proposition_preview",
            source_id=self.source.id,
            content_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        )
        self.bundle = _bundle(self.document.id, source_text)
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.context_manifests: dict[str, ContextManifestArtifact] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.accepted_write_attempted = False

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self,
        record_id: str,
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.context_manifests[record.id] = record

    def get_context_manifest_artifact(
        self,
        record_id: str,
    ) -> ContextManifestArtifact | None:
        return self.context_manifests.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.context_manifests[manifest.id] = manifest
        self.analysis_units.update({item.id: item for item in child_analysis_units})

    def save_extraction_task(self, record: ExtractionTask) -> None:
        self.extraction_tasks[record.id] = record

    def save_model_run(self, record: ModelRun) -> None:
        self.model_runs[record.id] = record

    def commit_successful_model_run_and_candidate_batch(
        self,
        *,
        model_run: ModelRun,
        batch: object,
    ) -> None:
        del model_run, batch
        self.accepted_write_attempted = True
        raise AssertionError("The proposition experiment cannot publish accepted state.")


class FixtureArchive:
    def __init__(self) -> None:
        self.outputs: dict[str, bytes] = {}

    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_digest
        self.outputs[model_run_id] = payload
        return object()


class FixtureRuntime:
    def __init__(self, outputs: tuple[bytes, ...]) -> None:
        self._outputs = iter(outputs)
        self.requests: list[ModelTaskRequest] = []
        self._identity = ModelIdentitySnapshot(
            "qwen2.5-fixture",
            "a" * 64,
            "fixture-runtime",
            "fixture-tokenizer",
        )

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return self._identity

    @property
    def task_deadline_seconds(self) -> float:
        return 30.0

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
            prompt_template_identity="fixture_no_template_v1",
            logical_input_digest=request.logical_input_digest,
            formatted_input_digest=request.logical_input_digest,
            formatted_input_token_count=self.count_tokens(request.logical_input),
            loaded_context_limit=4_096,
        )

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        output = next(self._outputs)
        return ModelTaskResponse(
            raw_output=output,
            execution_receipt=ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(
                    task.execution_spec.model_identity
                ),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=task.rendered_input_digest,
                input_token_count=task.input_admission.formatted_input_token_count,
                output_token_count=1,
            ),
            first_response_event_milliseconds=None,
        )


class FixtureRunIds:
    def __init__(self) -> None:
        self.ordinal = 0

    def new_model_run_id(self) -> str:
        self.ordinal += 1
        return f"mrn_{self.ordinal:032x}"


def test_preview_asks_one_bounded_question_per_non_event_fragment() -> None:
    result, ledger, runtime, archive = _run_preview((b"Y",) * 6)

    assert len(runtime.requests) == 6
    assert all(
        request.execution_spec.generation_parameters[0].value == 3 for request in runtime.requests
    )
    assert result.scope.status is PropositionScopeStatus.COMPLETE
    assert {item.text for item in result.scope.fragments} == {
        "Sacks",
        "stated",
        "that",
        "Anthropic",
        "was",
        "running",
        "a strategy",
    }
    assert len(result.traces) == 6
    assert all(item.input["exact_model_input"] for item in result.traces)
    assert all(item.output["raw_output_text"] == "Y" for item in result.traces)
    assert all(item.output["parsed_answer"] == "Y" for item in result.traces)
    assert set(archive.outputs) == set(result.model_run_ids)
    assert ledger.accepted_write_attempted is False


def test_one_malformed_answer_leaves_only_its_fragment_unresolved() -> None:
    result, ledger, runtime, archive = _run_preview((b"YES", *(b"Y",) * 5))

    assert len(runtime.requests) == 6
    assert result.scope.status is PropositionScopeStatus.PARTIAL
    assert len(result.scope.unresolved_candidate_ids) == 1
    assert len(result.diagnostics) == 1
    assert result.traces[0].output["raw_output_text"] == "YES"
    assert result.traces[0].output["parsed_answer"] is None
    assert set(archive.outputs) == set(result.model_run_ids)
    assert ledger.accepted_write_attempted is False


def test_marker_free_diagnostic_preserves_unmodified_passage_and_exact_output() -> None:
    ledger = FixtureLedger()
    runtime = FixtureRuntime((b"Y",))
    archive = FixtureArchive()
    paragraph = next(item for item in ledger.bundle.nodes if item.node_type == "paragraph")
    segment = paragraph_source_segments(SOURCE_TEXT, PARAGRAPH_SEGMENT_V3)[0]
    unit = create_analysis_unit_from_source_segment(
        SourceSegmentAnalysisUnitInput(
            representation_id=ledger.bundle.representation.id,
            paragraph_node_id=paragraph.id,
            source_segment_label=segment.label,
            policy_id="marker_free_unique_occurrence_diagnostic_v1",
            task_type="proposition_fragment_membership_marker_free_diagnostic",
        ),
        ledger,
    )
    trigger, event, linguistic = _event_inputs()
    candidates = build_proposition_fragment_candidates(
        source_text=SOURCE_TEXT,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic,
        entity_candidates=(),
    )
    candidate = next(item for item in candidates if item.text == "Sacks")

    result = run_marker_free_proposition_fragment_membership(
        MarkerFreePropositionMembershipCommand(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            source_text=SOURCE_TEXT,
            event=event,
            trigger=trigger,
            candidate=candidate,
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture", 4_096, 32, 32),
            generation_parameters=(
                ExecutionSetting("max_output_tokens", 32),
                ExecutionSetting("temperature", 0),
            ),
            prompt_bytes=b"Return Y, N, or U.\n",
            ordinal=0,
        ),
        ledger=cast(PropositionScopeLedger, ledger),
        archive=archive,
        model_runtime=runtime,
        model_run_id_factory=FixtureRunIds(),
        tokenizer=runtime,
    )

    assert result.answer is not None
    assert result.answer.value.value == "Y"
    assert result.task_input.rendered_input is not None
    assert f"Passage:\n{SOURCE_TEXT}\n" in result.task_input.rendered_input
    assert "<source>" not in result.task_input.rendered_input
    assert "<event>" not in result.task_input.rendered_input
    assert "<candidate>" not in result.task_input.rendered_input
    assert result.trace.input["model_visible_task"] == result.task_input.rendered_input
    assert result.trace.output["raw_output_text"] == "Y"
    assert result.trace.output["parsed_answer"] == "Y"
    assert len(runtime.requests) == 1
    assert ledger.accepted_write_attempted is False


def _run_preview(
    outputs: tuple[bytes, ...],
) -> tuple[PropositionScopeResult, FixtureLedger, FixtureRuntime, FixtureArchive]:
    ledger = FixtureLedger()
    runtime = FixtureRuntime(outputs)
    archive = FixtureArchive()
    paragraph = next(item for item in ledger.bundle.nodes if item.node_type == "paragraph")
    segment = paragraph_source_segments(SOURCE_TEXT, PARAGRAPH_SEGMENT_V3)[0]
    unit = create_analysis_unit_from_source_segment(
        SourceSegmentAnalysisUnitInput(
            representation_id=ledger.bundle.representation.id,
            paragraph_node_id=paragraph.id,
            source_segment_label=segment.label,
            policy_id="source_grounded_proposition_scope_v1",
            task_type="source_grounded_proposition_scope_experiment",
        ),
        ledger,
    )
    trigger, event, linguistic = _event_inputs()
    result = run_source_grounded_proposition_scope(
        PropositionScopeCommand(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            source_text=SOURCE_TEXT,
            event=event,
            trigger=trigger,
            entity_candidates=(),
            linguistic_evidence=linguistic,
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture", 4_096, 32, 32),
            generation_parameters=(
                ExecutionSetting("max_output_tokens", 32),
                ExecutionSetting("temperature", 0),
            ),
            prompt_bytes=b"Answer one proposition-fragment question with Y, N, or U.\n",
        ),
        ledger=cast(PropositionScopeLedger, ledger),
        archive=archive,
        model_runtime=runtime,
        model_run_id_factory=FixtureRunIds(),
        tokenizer=runtime,
    )
    return result, ledger, runtime, archive


def _event_inputs() -> tuple[
    EventTriggerDraft,
    SourceGroundedEventDraft,
    EventEntityLinguisticEvidence,
]:
    source_digest = hashlib.sha256(SOURCE_TEXT.encode()).hexdigest()
    expression_start = SOURCE_TEXT.index("running")
    expression_end = expression_start + len("running")
    trace_id = "xst_" + "1" * 24
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id="seg_proposition_preview",
            source_text_sha256=source_digest,
            start=expression_start,
            end=expression_end,
            text="running",
            head_start=expression_start,
            head_end=expression_end,
            head_text="running",
            event_type_label="unmapped",
            extraction_task_id="ext_trigger_fixture",
            model_run_id="mrn_trigger_fixture",
            trace_id=trace_id,
        ),
        source_segment_id="seg_proposition_preview",
        source_text_sha256=source_digest,
        start=expression_start,
        end=expression_end,
        text="running",
        head_start=expression_start,
        head_end=expression_end,
        head_text="running",
        event_type_label="unmapped",
        extraction_task_id="ext_trigger_fixture",
        model_run_id="mrn_trigger_fixture",
        trace_id=trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "1" * 24,
        trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        expression_text=trigger.text,
        head_text=trigger.head_text,
        head_evidence_target_id="etg_" + "1" * 24,
        expression_evidence_target_id="etg_" + "2" * 24,
        support_evidence_target_id="etg_" + "3" * 24,
    )
    raw = tuple(
        (match.start(), match.end(), match.group())
        for match in re.finditer(r"\w+|[^\w\s]", SOURCE_TEXT)
    )
    heads = {
        "Sacks": ("t2", "nsubj"),
        "stated": (None, "root"),
        "that": ("t6", "mark"),
        "Anthropic": ("t6", "nsubj"),
        "was": ("t6", "aux"),
        "running": ("t2", "ccomp"),
        "a": ("t8", "det"),
        "strategy": ("t6", "obj"),
        ".": ("t2", "punct"),
    }
    tokens = tuple(
        EventEntityLinguisticToken(
            token_id=f"t{ordinal}",
            sentence_id="s1",
            text=text,
            start=start,
            end=end,
            lemma=text.casefold(),
            part_of_speech="PUNCT" if text == "." else "X",
            dependency_relation=heads[text][1],
            head_token_id=heads[text][0],
        )
        for ordinal, (start, end, text) in enumerate(raw, start=1)
    )
    linguistic = EventEntityLinguisticEvidence(
        trace_id="xst_" + "2" * 24,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=source_digest,
        producer_id="stanza_pipeline_v1",
        model_id="stanza_english_ewt",
        model_version="fixture",
        resource_identity="4" * 64,
        tokens=tokens,
    )
    return trigger, event, linguistic


def _bundle(document_id: str, source_text: str = SOURCE_TEXT) -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_proposition_preview",
        representation_id="rep_proposition_preview",
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(source_text.encode()).hexdigest(),
        text=source_text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id="nod_proposition_preview_root",
        representation_id="rep_proposition_preview",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(source_text),
    )
    paragraph = DocumentNode(
        id="nod_proposition_preview_paragraph",
        representation_id="rep_proposition_preview",
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(source_text),
    )
    quality = ParseQualityReport(
        id="pqr_proposition_preview",
        representation_id="rep_proposition_preview",
        metric_values={"text_char_count": len(source_text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_proposition_preview",
        document_id=document_id,
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="b" * 64,
        processing_task_fingerprint_id="ptf_proposition_preview",
        input_blob_digest=hashlib.sha256(source_text.encode()).hexdigest(),
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
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, paragraph),
        quality_report=quality,
    )
