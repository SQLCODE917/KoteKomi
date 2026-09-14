from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import cast

from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    ContextModelProfile,
    EventEntityConnectionPreviewStatus,
    EventEntityKind,
    EventEntityMentionInput,
    EventEntitySourceSpan,
    ExecutionSetting,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelTaskRequest,
    ModelTaskResponse,
    SourceSegmentAnalysisUnitInput,
    build_source_grounded_event_draft,
    create_analysis_unit_from_source_segment,
    generation_parameters_digest,
    model_identity_snapshot_digest,
    paragraph_source_segments,
)
from kotekomi_application.event_entity_connection_preview import (
    EventEntityConnectionCommand,
    EventEntityConnectionLedger,
    EventEntityConnectionResult,
    run_event_entity_connection_preview,
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

NOW = datetime(2026, 9, 12, tzinfo=UTC)
SOURCE_TEXT = "Anthropic criticized Stargate."


class FixtureLedger:
    def __init__(self) -> None:
        self.source = Source(
            id="src_connection_preview",
            source_type=SourceType.MANUAL_FILE,
            identity_policy_id="fixture",
            canonical_identity_key="connection-preview",
        )
        self.document = Document(
            id="doc_connection_preview",
            source_id=self.source.id,
            content_sha256=hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
        )
        self.bundle = _bundle(self.document.id)
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
        raise AssertionError("The experiment cannot publish accepted state.")


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


def test_preview_runs_one_bounded_question_per_candidate_and_preserves_exact_io() -> None:
    result, ledger, runtime, archive = _run_preview((b"Y", b"N"))

    assert len(runtime.requests) == 2
    assert all(
        request.execution_spec.generation_parameters[0].value == 2 for request in runtime.requests
    )
    assert [item.entity_name for item in result.preview.drafts] == ["Anthropic"]
    assert result.preview.terminal_status is EventEntityConnectionPreviewStatus.COMPLETE
    assert len(result.preview.traces) == 2
    assert all(trace.input["exact_model_input"] for trace in result.preview.traces)
    assert [trace.output["raw_output_text"] for trace in result.preview.traces] == ["Y", "N"]
    assert set(archive.outputs) == set(result.preview.model_run_ids)
    assert ledger.accepted_write_attempted is False


def test_one_malformed_judgment_is_isolated_without_erasing_its_sibling() -> None:
    result, ledger, runtime, archive = _run_preview((b"Y", b"not-a-finite-answer"))

    assert len(runtime.requests) == 2
    assert [item.entity_name for item in result.preview.drafts] == ["Anthropic"]
    assert result.preview.terminal_status is EventEntityConnectionPreviewStatus.PARTIAL
    assert len(result.preview.judgments) == 1
    assert any(item.reason_code == "model_judgment_failed" for item in result.preview.decisions)
    assert any(item.startswith("entity_involvement_failed:") for item in result.preview.diagnostics)
    assert set(archive.outputs) == set(result.preview.model_run_ids)
    assert ledger.accepted_write_attempted is False


def _run_preview(
    outputs: tuple[bytes, bytes],
) -> tuple[EventEntityConnectionResult, FixtureLedger, FixtureRuntime, FixtureArchive]:
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
            policy_id="event_entity_connection_pairwise_v1",
            task_type="event_entity_connection_experiment",
        ),
        ledger,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "1" * 24,
        trigger_id="etd_" + "2" * 24,
        source_segment_id="seg_connection_preview",
        source_text_sha256=hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
        expression_text="criticized",
        head_text="criticized",
        head_evidence_target_id="etg_" + "1" * 24,
        expression_evidence_target_id="etg_" + "2" * 24,
        support_evidence_target_id="etg_" + "3" * 24,
    )
    mentions = tuple(
        _mention(name, SOURCE_TEXT.index(name), str(index))
        for index, name in enumerate(("Anthropic", "Stargate"), start=1)
    )

    result = run_event_entity_connection_preview(
        EventEntityConnectionCommand(
            source_id=ledger.source.id,
            document_id=ledger.document.id,
            representation_id=ledger.bundle.representation.id,
            parent_preview_id="hsp_" + "4" * 24,
            parent_preview_sha256="5" * 64,
            source_text=SOURCE_TEXT,
            event=event,
            entity_mentions=mentions,
            candidate_gaps=(),
            analysis_unit=unit,
            model_profile=ContextModelProfile("fixture", 4_096, 32, 32),
            generation_parameters=(
                ExecutionSetting("max_output_tokens", 32),
                ExecutionSetting("temperature", 0),
            ),
            prompt_bytes=b"Answer Y, N, or U.\n",
        ),
        ledger=cast(EventEntityConnectionLedger, ledger),
        archive=archive,
        model_runtime=runtime,
        model_run_id_factory=FixtureRunIds(),
        tokenizer=runtime,
    )
    return result, ledger, runtime, archive


def _mention(name: str, start: int, suffix: str) -> EventEntityMentionInput:
    digest = hashlib.sha256(SOURCE_TEXT.encode()).hexdigest()
    mention_id = "mnc_" + suffix * 24
    values = (
        "seg_connection_preview",
        digest,
        str(start),
        str(start + len(name)),
        name,
        mention_id,
        "",
    )
    span = EventEntitySourceSpan(
        id="ees_" + hashlib.sha256(chr(31).join(values).encode()).hexdigest()[:24],
        source_segment_id="seg_connection_preview",
        source_text_sha256=digest,
        start=start,
        end=start + len(name),
        text=name,
        mention_candidate_id=mention_id,
    )
    return EventEntityMentionInput(
        entity_identity=f"organization:{name.casefold()}",
        entity_kind=EventEntityKind.ORGANIZATION,
        entity_name=name,
        source_span=span,
    )


def _bundle(document_id: str) -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_connection_preview",
        representation_id="rep_connection_preview",
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
        text=SOURCE_TEXT,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id="nod_connection_preview_root",
        representation_id="rep_connection_preview",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(SOURCE_TEXT),
    )
    paragraph = DocumentNode(
        id="nod_connection_preview_paragraph",
        representation_id="rep_connection_preview",
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(SOURCE_TEXT),
    )
    quality = ParseQualityReport(
        id="pqr_connection_preview",
        representation_id="rep_connection_preview",
        metric_values={"text_char_count": len(SOURCE_TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_connection_preview",
        document_id=document_id,
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="b" * 64,
        processing_task_fingerprint_id="ptf_connection_preview",
        input_blob_digest=hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
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
