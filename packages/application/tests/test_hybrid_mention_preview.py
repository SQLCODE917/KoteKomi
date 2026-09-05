from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    ContextModelProfile,
    ExecutionSetting,
    HybridExtractionPreview,
    HybridMentionPreviewCommand,
    HybridPreviewStatus,
    MentionProposal,
    MentionProposalBatch,
    MentionProposalInput,
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
    ModelTaskRequest,
    ModelTaskResponse,
    run_hybrid_mention_preview,
)
from kotekomi_application.hybrid_mention_preview import (
    HybridMentionArchive,
    HybridMentionLedger,
    HybridMentionPreviewResult,
)
from kotekomi_application.staged_model_extraction import (
    generation_parameters_digest,
    model_identity_snapshot_digest,
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

NOW = datetime(2026, 9, 1, tzinfo=UTC)
TEXT = "Institutions\nThe European Union issued guidance."
PARAGRAPH_TEXT = "The European Union issued guidance."


class FixtureTokenizer:
    tokenizer_id = "fixture_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


class FixtureLedger:
    def __init__(
        self,
        *,
        paragraph_node_type: str = "paragraph",
        paragraph_text: str = PARAGRAPH_TEXT,
    ) -> None:
        text = f"Institutions\n{paragraph_text}"
        self.source = Source(
            id="src_hybrid_fixture",
            source_type=SourceType.MANUAL_FILE,
            identity_policy_id="fixture_v1",
            canonical_identity_key="hybrid-fixture",
        )
        self.document = Document(
            id="doc_hybrid_fixture",
            source_id=self.source.id,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        self.bundle = _bundle(self.document.id, paragraph_node_type, text)
        self.manifests: dict[str, ContextManifestArtifact] = {}
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.candidate_commit_called = False

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

    def commit_successful_model_run_and_candidate_batch(
        self, *, model_run: ModelRun, batch: object
    ) -> None:
        del model_run, batch
        self.candidate_commit_called = True
        raise AssertionError("HP-1 must not create ProposedChanges.")


class FixtureArchive:
    def __init__(self) -> None:
        self.model_outputs: dict[str, bytes] = {}
        self.previews: dict[str, bytes] = {}

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_digest
        self.model_outputs[model_run_id] = payload
        return object()

    def put_hybrid_extraction_preview(
        self,
        preview: HybridExtractionPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        assert preview.id not in self.previews
        self.previews[preview.id] = payload
        return object()

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes:
        return self.previews[preview_id]


class FixtureProposer:
    def __init__(
        self,
        *,
        fail: bool = False,
        include_invalid: bool = False,
        empty: bool = False,
    ) -> None:
        self.fail = fail
        self.include_invalid = include_invalid
        self.empty = empty
        self.inputs: list[MentionProposalInput] = []

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        self.inputs.append(proposal_input)
        if self.fail:
            raise RuntimeError("GLiNER unavailable")
        segment = proposal_input.source_segments[0]
        start = segment.exact_text.index("European Union")
        proposals = (
            []
            if self.empty
            else [
                MentionProposal(
                    segment.label,
                    "European Union",
                    start,
                    start + len("European Union"),
                    ("geopolitical_entity", "organization"),
                    0.91,
                )
            ]
        )
        if self.include_invalid:
            proposals.append(
                MentionProposal(
                    segment.label,
                    "wrong",
                    0,
                    5,
                    ("organization",),
                    0.99,
                )
            )
        return MentionProposalBatch(
            proposer_id="fixture-gliner",
            model_id="fixture-gliner-model",
            model_revision="fixture-revision",
            configuration=(("threshold", 0.5),),
            load_elapsed_milliseconds=1,
            inference_elapsed_milliseconds=2,
            proposals=tuple(proposals),
        )


class FixtureModelRuntime:
    def __init__(
        self,
        *,
        proposal_abstains: bool = False,
        proposal_fails: bool = False,
        proposal_uses_wrong_contract: bool = False,
        proposal_output: bytes | None = None,
        invalid_interpretation: bool = False,
    ) -> None:
        self.requests: list[ModelTaskRequest] = []
        self.proposal_abstains = proposal_abstains
        self.proposal_fails = proposal_fails
        self.proposal_uses_wrong_contract = proposal_uses_wrong_contract
        self.proposal_output = proposal_output
        self.invalid_interpretation = invalid_interpretation
        self._identity = ModelIdentitySnapshot(
            "qwen2.5-fixture",
            "d" * 64,
            "fixture-runtime",
            FixtureTokenizer.tokenizer_id,
        )

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return self._identity

    @property
    def task_deadline_seconds(self) -> float:
        return 300.0

    @property
    def tokenizer_id(self) -> str:
        return self.configured_identity.tokenizer_id

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())

    def inspect_model_input(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        return ModelInputMeasurement(
            model_identity_digest=model_identity_snapshot_digest(request.model_identity),
            runtime_identity=self.configured_identity.runtime,
            model_instance_id=self.configured_identity.name,
            tokenizer_id=self.tokenizer_id,
            prompt_template_identity="fixture_no_prompt_template_v1",
            logical_input_digest=request.logical_input_digest,
            formatted_input_digest=request.logical_input_digest,
            formatted_input_token_count=self.count_tokens(request.logical_input),
            loaded_context_limit=65_536,
        )

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        self.requests.append(task)
        if b"task: propose_mentions" in task.rendered_input:
            if self.proposal_fails:
                raise RuntimeError("Qwen runtime unavailable")
            if self.proposal_output is not None:
                output = self.proposal_output
            elif self.proposal_uses_wrong_contract:
                output = (
                    b"candidate: c1\n"
                    b"referentiality: specific_entity\n"
                    b"contextual_kind: organization\n"
                    b"discourse_role: origin\n"
                    b"support: s1\n"
                )
            elif self.proposal_abstains:
                output = b"abstain: no source expressions qualify\n"
            else:
                output = b"mention: s1 | geopolitical_entity,organization | European Union\n"
        elif b"task: interpret_mention" in task.rendered_input:
            output = (
                b"candidate: c1\nreferentiality: specific_entity\n"
                if self.invalid_interpretation
                else (
                    b"candidate: c1\n"
                    b"referentiality: specific_entity\n"
                    b"contextual_kind: organization\n"
                    b"discourse_role: origin\n"
                    b"support: s1\n"
                )
            )
        else:
            raise AssertionError("Unknown hybrid task input.")
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


class FixtureRunIdFactory:
    def __init__(self, prefix: str = "fixture") -> None:
        self.ordinal = 0
        self.prefix = prefix

    def new_model_run_id(self) -> str:
        self.ordinal += 1
        return f"mrn_{self.prefix}_{self.ordinal}"


def test_hybrid_preview_runs_complete_source_grounded_path_without_state_change() -> None:
    ledger = FixtureLedger()
    archive = FixtureArchive()
    proposer = FixtureProposer()
    runtime = FixtureModelRuntime()

    result = _run(ledger, archive, proposer, runtime)

    assert result.preview.terminal_status is HybridPreviewStatus.COMPLETE
    assert len(result.preview.observations) == 2
    assert len(result.preview.candidates) == 1
    assert result.preview.candidates[0].text == "European Union"
    assert len(result.preview.candidates[0].observation_ids) == 2
    assert result.preview.interpretations[0].referentiality.value == "specific_entity"
    assert result.preview.interpretations[0].contextual_kind.value == "organization"
    assert result.preview.interpretations[0].discourse_role.value == "origin"
    assert len(ledger.extraction_tasks) == 3
    assert len(ledger.model_runs) == 3
    assert ledger.candidate_commit_called is False
    assert len(archive.model_outputs) == 3
    assert archive.previews[result.preview.id]
    assert proposer.inputs[0].source_segments[0].exact_text == PARAGRAPH_TEXT
    assert runtime.requests[0].rendered_input.count(PARAGRAPH_TEXT.encode()) == 1
    assert b"[heading]\nInstitutions" in runtime.requests[0].rendered_input
    assert b"task: propose_mentions" in runtime.requests[0].rendered_input
    assert b"ontology_guideline_card" in runtime.requests[1].rendered_input
    proposal_traces = [
        trace for trace in result.preview.traces if trace.stage_id == "mention_proposal"
    ]
    assert [trace.input["source_text"] for trace in proposal_traces] == [
        PARAGRAPH_TEXT,
        PARAGRAPH_TEXT,
    ]
    assert all(
        trace.output["model_run_id"] in result.preview.model_run_ids for trace in proposal_traces
    )


def test_failed_specialized_proposer_continues_from_qwen_as_partial() -> None:
    ledger = FixtureLedger()
    archive = FixtureArchive()
    runtime = FixtureModelRuntime()

    result = _run(ledger, archive, FixtureProposer(fail=True), runtime)

    assert result.preview.terminal_status is HybridPreviewStatus.PARTIAL
    assert result.preview.diagnostics == ("gliner_proposer_failed:runtime_failed",)
    assert len(result.preview.candidates) == 1
    assert len(result.preview.interpretations) == 1
    assert len(runtime.requests) == 2
    gliner_trace = next(
        trace
        for trace in result.preview.traces
        if trace.stage_id == "mention_proposal" and trace.producer_id == "gliner"
    )
    assert gliner_trace.status.value == "failed"
    assert gliner_trace.output["model_run_status"] == "runtime_failed"
    assert archive.previews[result.preview.id]


def test_failed_qwen_proposer_continues_from_gliner_as_partial() -> None:
    ledger = FixtureLedger()
    runtime = FixtureModelRuntime(proposal_fails=True)

    result = _run(ledger, FixtureArchive(), FixtureProposer(), runtime)

    assert result.preview.terminal_status is HybridPreviewStatus.PARTIAL
    assert result.preview.diagnostics == ("qwen_proposer_failed:runtime_failed",)
    assert len(result.preview.candidates) == 1
    assert len(result.preview.interpretations) == 1
    assert len(runtime.requests) == 2
    assert len(result.preview.extraction_task_ids) == 3
    assert len(result.preview.model_run_ids) == 3


def test_valid_qwen_abstention_and_failed_gliner_produce_partial_empty_preview() -> None:
    result = _run(
        FixtureLedger(),
        FixtureArchive(),
        FixtureProposer(fail=True),
        FixtureModelRuntime(proposal_abstains=True),
    )

    assert result.preview.terminal_status is HybridPreviewStatus.PARTIAL
    assert result.preview.diagnostics == ("gliner_proposer_failed:runtime_failed",)
    assert result.preview.observations == ()
    assert result.preview.candidates == ()
    assert result.preview.interpretations == ()
    assert len(result.preview.extraction_task_ids) == 2
    assert len(result.preview.model_run_ids) == 2


def test_two_failed_proposers_produce_blocked_preview() -> None:
    result = _run(
        FixtureLedger(),
        FixtureArchive(),
        FixtureProposer(fail=True),
        FixtureModelRuntime(proposal_fails=True),
    )

    assert result.preview.terminal_status is HybridPreviewStatus.BLOCKED
    assert result.preview.diagnostics == (
        "gliner_proposer_failed:runtime_failed",
        "qwen_proposer_failed:runtime_failed",
    )
    assert result.preview.candidates == ()
    assert {trace.status.value for trace in result.preview.traces} == {"failed"}


def test_wrong_qwen_proposer_output_contract_does_not_erase_gliner_result() -> None:
    archive = FixtureArchive()
    result = _run(
        FixtureLedger(),
        archive,
        FixtureProposer(),
        FixtureModelRuntime(proposal_uses_wrong_contract=True),
    )

    assert result.preview.terminal_status is HybridPreviewStatus.PARTIAL
    assert result.preview.diagnostics == ("qwen_proposer_failed:output_contract",)
    assert len(result.preview.candidates) == 1
    assert len(result.preview.interpretations) == 1
    qwen_proposal_run_id = next(
        trace.output["model_run_id"]
        for trace in result.preview.traces
        if trace.stage_id == "mention_proposal" and trace.producer_id == "qwen2.5"
    )
    assert isinstance(qwen_proposal_run_id, str)
    assert archive.model_outputs[qwen_proposal_run_id].startswith(b"candidate: c1\n")


def test_invalid_observation_is_reported_without_losing_valid_source_evidence() -> None:
    ledger = FixtureLedger()

    result = _run(
        ledger,
        FixtureArchive(),
        FixtureProposer(include_invalid=True),
        FixtureModelRuntime(),
    )

    assert result.preview.terminal_status is HybridPreviewStatus.COMPLETE
    assert result.preview.candidates[0].text == "European Union"
    invalid = [
        item for item in result.preview.diagnostics if item.startswith("invalid_observation:")
    ]
    assert len(invalid) == 1
    assert any(model_run_id in invalid[0] for model_run_id in result.preview.model_run_ids)
    gliner_trace = next(
        trace
        for trace in result.preview.traces
        if trace.stage_id == "mention_proposal" and trace.producer_id == "gliner"
    )
    assert gliner_trace.diagnostics == tuple(invalid)


def test_valid_qwen_abstention_continues_with_specialized_proposer_evidence() -> None:
    ledger = FixtureLedger()

    result = _run(
        ledger,
        FixtureArchive(),
        FixtureProposer(),
        FixtureModelRuntime(proposal_abstains=True),
    )

    assert result.preview.terminal_status is HybridPreviewStatus.COMPLETE
    assert len(result.preview.observations) == 1
    assert result.preview.candidates[0].text == "European Union"
    qwen_proposal_run = next(
        run
        for run in ledger.model_runs.values()
        if run.outcome_metadata.get("contract") == "hybrid_mention_proposal_text_v1"
    )
    assert qwen_proposal_run.status.value == "abstained"
    assert qwen_proposal_run.outcome_metadata["proposal_count"] == 0


def test_two_valid_empty_proposer_results_produce_complete_empty_preview() -> None:
    result = _run(
        FixtureLedger(),
        FixtureArchive(),
        FixtureProposer(empty=True),
        FixtureModelRuntime(proposal_abstains=True),
    )

    assert result.preview.terminal_status is HybridPreviewStatus.COMPLETE
    assert result.preview.observations == ()
    assert result.preview.candidates == ()
    assert result.preview.interpretations == ()


def test_same_segment_equal_literals_share_one_interpretation_execution() -> None:
    paragraph = "The European Union and European Union issued guidance."
    ledger = FixtureLedger(paragraph_text=paragraph)
    runtime = FixtureModelRuntime()

    result = _run(ledger, FixtureArchive(), FixtureProposer(), runtime)

    interpretation_requests = [
        request
        for request in runtime.requests
        if request.task_type == "hybrid_mention_interpretation"
    ]
    assert len(result.preview.candidates) == 2
    assert len(interpretation_requests) == 1
    assert len(result.preview.interpretations) == 2
    assert len({item.candidate_id for item in result.preview.interpretations}) == 2
    assert len({item.model_run_id for item in result.preview.interpretations}) == 1
    reuse_trace = next(
        trace for trace in result.preview.traces if trace.stage_id == "mention_interpretation_reuse"
    )
    original_trace = next(
        trace for trace in result.preview.traces if trace.id == reuse_trace.parent_trace_ids[0]
    )
    assert reuse_trace.producer_id == "kotekomi_application"
    assert reuse_trace.input["candidate_text"] == "European Union"
    assert reuse_trace.output["reused_from_candidate_id"] in {
        item.candidate_id for item in result.preview.interpretations
    }
    assert reuse_trace.output["reused_from_trace_id"] == original_trace.id
    assert reuse_trace.execution_record_ids == original_trace.execution_record_ids


def test_interpretation_reuse_does_not_cross_segment_or_literal_boundaries() -> None:
    paragraph = "The European Union and Council issued guidance. European Union responded."
    ledger = FixtureLedger(paragraph_text=paragraph)
    runtime = FixtureModelRuntime(
        proposal_output=(
            b"mention: s1 | organization | European Union\n"
            b"mention: s1 | organization | Council\n"
            b"mention: s2 | organization | European Union\n"
        )
    )

    result = _run(ledger, FixtureArchive(), FixtureProposer(), runtime)

    interpretation_requests = [
        request
        for request in runtime.requests
        if request.task_type == "hybrid_mention_interpretation"
    ]
    assert len(result.preview.candidates) == 3
    assert len(interpretation_requests) == 3
    assert all(trace.stage_id != "mention_interpretation_reuse" for trace in result.preview.traces)


def test_same_segment_interpretation_failure_is_recorded_once_and_reused() -> None:
    ledger = FixtureLedger(paragraph_text="The European Union and European Union issued guidance.")
    runtime = FixtureModelRuntime(invalid_interpretation=True)

    result = _run(ledger, FixtureArchive(), FixtureProposer(), runtime)

    interpretation_requests = [
        request
        for request in runtime.requests
        if request.task_type == "hybrid_mention_interpretation"
    ]
    interpretation_traces = [
        trace
        for trace in result.preview.traces
        if trace.stage_id in {"mention_interpretation", "mention_interpretation_reuse"}
    ]
    assert result.preview.terminal_status is HybridPreviewStatus.PARTIAL
    assert len(interpretation_requests) == 1
    assert len(interpretation_traces) == 2
    assert {trace.status.value for trace in interpretation_traces} == {"failed"}
    assert len({trace.execution_record_ids for trace in interpretation_traces}) == 1
    assert result.preview.interpretations == ()


def test_invalid_interpretation_preserves_candidate_and_publishes_partial_preview() -> None:
    ledger = FixtureLedger()

    result = _run(
        ledger,
        FixtureArchive(),
        FixtureProposer(),
        FixtureModelRuntime(invalid_interpretation=True),
    )

    assert result.preview.terminal_status is HybridPreviewStatus.PARTIAL
    assert result.preview.candidates[0].text == "European Union"
    assert result.preview.interpretations == ()
    assert any(item.startswith("interpretation_failed:") for item in result.preview.diagnostics)
    interpretation_run = next(
        run
        for run in ledger.model_runs.values()
        if ledger.extraction_tasks[run.extraction_task_id].task_type
        == "hybrid_mention_interpretation"
    )
    assert interpretation_run.status.value == "invalid_output"


def test_changed_ontology_card_changes_interpretation_task_fingerprint() -> None:
    first_ledger = FixtureLedger()
    second_ledger = FixtureLedger()

    _run(
        first_ledger,
        FixtureArchive(),
        FixtureProposer(),
        FixtureModelRuntime(),
        ontology_card_bytes=b"ontology guideline card v1",
    )
    _run(
        second_ledger,
        FixtureArchive(),
        FixtureProposer(),
        FixtureModelRuntime(),
        ontology_card_bytes=b"ontology guideline card v2",
    )

    first = next(
        item
        for item in first_ledger.extraction_tasks.values()
        if item.task_type == "hybrid_mention_interpretation"
    )
    second = next(
        item
        for item in second_ledger.extraction_tasks.values()
        if item.task_type == "hybrid_mention_interpretation"
    )
    assert first.task_fingerprint != second.task_fingerprint
    assert (
        first.context_manifest_payload["task_local_input_digest"]
        != (second.context_manifest_payload["task_local_input_digest"])
    )


def test_repeated_nondeterministic_runs_preserve_both_previews() -> None:
    ledger = FixtureLedger()
    archive = FixtureArchive()

    first = _run(
        ledger,
        archive,
        FixtureProposer(),
        FixtureModelRuntime(),
        run_id_factory=FixtureRunIdFactory("first"),
    )
    second = _run(
        ledger,
        archive,
        FixtureProposer(),
        FixtureModelRuntime(),
        run_id_factory=FixtureRunIdFactory("second"),
    )

    assert first.preview.id != second.preview.id
    assert set(archive.previews) == {first.preview.id, second.preview.id}


@pytest.mark.parametrize("node_type", ["heading", "list_item"])
def test_nonparagraph_node_fails_before_model_work(node_type: str) -> None:
    ledger = FixtureLedger(paragraph_node_type=node_type)
    archive = FixtureArchive()
    proposer = FixtureProposer()
    runtime = FixtureModelRuntime()

    with pytest.raises(ValueError, match="requires a paragraph"):
        _run(ledger, archive, proposer, runtime)

    assert proposer.inputs == []
    assert runtime.requests == []
    assert archive.previews == {}


def _run(
    ledger: FixtureLedger,
    archive: FixtureArchive,
    proposer: FixtureProposer,
    runtime: FixtureModelRuntime,
    *,
    ontology_card_bytes: bytes = b"ontology guideline card v1",
    run_id_factory: FixtureRunIdFactory | None = None,
) -> HybridMentionPreviewResult:
    return run_hybrid_mention_preview(
        command=HybridMentionPreviewCommand(
            representation_id=ledger.bundle.representation.id,
            paragraph_node_id="nod_hybrid_paragraph",
            model_profile=ContextModelProfile("fixture-model", 1024, 64, 16),
            generation_parameters=(
                ExecutionSetting("max_output_tokens", 64),
                ExecutionSetting("seed", 17),
                ExecutionSetting("temperature", 0),
            ),
        ),
        ledger=cast(HybridMentionLedger, ledger),
        archive=cast(HybridMentionArchive, archive),
        proposer=proposer,
        model_runtime=runtime,
        model_run_id_factory=run_id_factory or FixtureRunIdFactory(),
        tokenizer=FixtureTokenizer(),
        prompt_bytes=b"Perform the task block only.",
        ontology_card_bytes=ontology_card_bytes,
    )


def _bundle(
    document_id: str,
    paragraph_node_type: str,
    text: str = TEXT,
) -> DocumentRepresentationBundle:
    representation_id = "rep_hybrid_fixture"
    text_view = TextView(
        id="tvw_hybrid_fixture",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    heading_end = text.index("\n")
    paragraph_start = heading_end + 1
    root = DocumentNode(
        id="nod_hybrid_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    heading = DocumentNode(
        id="nod_hybrid_heading",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="heading",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=heading_end,
    )
    paragraph = DocumentNode(
        id="nod_hybrid_paragraph",
        representation_id=representation_id,
        parent_node_id=heading.id,
        node_type=paragraph_node_type,
        order_index=2,
        text_view_id=text_view.id,
        start_char=paragraph_start,
        end_char=len(text),
    )
    quality = ParseQualityReport(
        id="pqr_hybrid_fixture",
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
        processing_task_fingerprint_id="ptf_hybrid_fixture",
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
