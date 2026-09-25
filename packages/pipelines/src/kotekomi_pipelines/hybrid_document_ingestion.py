"""HP-8 public document-wide composition of the HP-1 through HP-7 use cases."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from kotekomi_adapters import (
    DebertaNliAdapter,
    FCorefAdapter,
    FCorefConfig,
    GlinerMentionProposer,
    LocalArchiveStore,
    QANomNominalizationAnalyzer,
    StanzaLinguisticAnalyzer,
)
from kotekomi_adapters.gliner_organization_mention_proposer import (
    GLINER_DEVICE,
    GLINER_MODEL_ID,
    GLINER_MODEL_REVISION,
    GLINER_PACKAGE_VERSION,
    GLINER_THRESHOLD,
)
from kotekomi_adapters.model_resources import (
    fcoref_expected_resource_identity,
    fcoref_model_path,
    fcoref_python_path,
    gliner_expected_resource_identity,
    gliner_model_path,
    nli_expected_resource_identity,
    nli_model_path,
    qanom_expected_resource_identity,
    qanom_lexical_resource_path,
    qanom_model_path,
    refined_data_path,
    refined_python_path,
    stanza_expected_resource_identity,
    stanza_model_path,
)
from kotekomi_adapters.refined_entity_linking import (
    REFINED_ENTITY_SET,
    REFINED_MODEL_ID,
    REFINED_MODEL_REVISION,
    REFINED_PACKAGE_REVISION,
    REFINED_RESOURCE_MANIFEST_SHA256,
    REFINED_RUNTIME_IDENTITY,
    RefinedEntityLinkingAdapter,
    RefinedEntityLinkingConfig,
)
from kotekomi_adapters.sqlite_ledger import sqlite_ledger_transaction
from kotekomi_application.context_planning import ContextModelProfile
from kotekomi_application.hybrid_document_orchestration import (
    HYBRID_STAGE_ORDER,
    HybridDocumentClosureInput,
    HybridDocumentClosureResult,
    HybridDocumentCoverageReport,
    HybridDocumentPlan,
    HybridParagraphReceipt,
    HybridParagraphStageRecord,
    HybridPipelinePolicyManifest,
    HybridPolicyManifestInput,
    HybridPolicyPin,
    HybridStageDisposition,
    HybridStageId,
    build_hybrid_document_coverage_report,
    build_hybrid_paragraph_receipt,
    close_hybrid_document_ingestion,
    load_reusable_hybrid_paragraph_receipt,
    plan_hybrid_document,
    publish_hybrid_paragraph_receipt,
)
from kotekomi_application.hybrid_document_references import HYBRID_REFERENCE_POLICY_ID
from kotekomi_application.hybrid_entity_grounding import (
    HYBRID_ENTITY_GROUNDING_POLICY_ID,
    EntityLinkerIdentity,
    EntityLinkingExecution,
    EntityLinkingInput,
    EntityLinkingPort,
)
from kotekomi_application.hybrid_entity_grounding_preview import (
    HybridEntityGroundingCommand,
    HybridEntityGroundingResult,
    run_hybrid_entity_grounding_preview,
)
from kotekomi_application.hybrid_event_semantics import (
    HYBRID_EVENT_FRAME_SELECTION_SCHEMA_ID,
    HYBRID_EVENT_PRESENTATION_SCHEMA_ID,
    HYBRID_EVENT_ROLE_SELECTION_SCHEMA_ID,
    HYBRID_EVENT_SEMANTICS_POLICY_ID,
    HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID,
)
from kotekomi_application.hybrid_event_semantics_model_output import (
    event_frame_selection_schema_bytes,
    event_presentation_schema_bytes,
    event_semantic_role_target_schema_bytes,
    semantic_support_schema_bytes,
)
from kotekomi_application.hybrid_event_semantics_preview import (
    HybridEventSemanticsCommand,
    HybridEventSemanticsResult,
    publish_hybrid_event_semantics_preview,
    run_hybrid_event_semantics_preview,
)
from kotekomi_application.hybrid_event_trigger_model_output import (
    binary_semantic_answer_schema_bytes,
    event_head_answer_schema_bytes,
    event_verb_role_answer_schema_bytes,
)
from kotekomi_application.hybrid_event_trigger_preview import (
    EVENT_BINARY_SEMANTIC_SCHEMA_ID,
    EVENT_HEAD_JUDGMENT_SCHEMA_ID,
    EVENT_VERB_ROLE_SCHEMA_ID,
    HybridEventTriggerCommand,
    HybridEventTriggerPrompts,
    HybridEventTriggerResult,
    run_hybrid_event_trigger_preview,
)
from kotekomi_application.hybrid_event_triggers import HYBRID_EVENT_TRIGGER_POLICY_ID
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HYBRID_MENTION_PREVIEW_POLICY_ID,
    PROPOSER_CONTEXTUAL_KINDS,
    HybridPreviewStatus,
)
from kotekomi_application.hybrid_mention_preview import (
    HybridMentionPreviewCommand,
    HybridMentionPreviewResult,
    run_hybrid_mention_preview,
)
from kotekomi_application.hybrid_proposed_changes import (
    HYBRID_PROPOSAL_POLICY_ID,
    build_hybrid_proposal_plan,
    publish_hybrid_proposal_plan,
)
from kotekomi_application.hybrid_reference_preview import (
    SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID,
    SEMANTIC_REFERENCE_VALIDATION_SCHEMA_ID,
    HybridReferencePreviewCommand,
    HybridReferencePreviewResult,
    run_hybrid_reference_preview,
)
from kotekomi_application.hybrid_standing_fact_model_output import standing_fact_schema_bytes
from kotekomi_application.hybrid_standing_fact_qualification_model_output import (
    standing_fact_qualification_schema_bytes,
)
from kotekomi_application.hybrid_standing_facts import (
    HYBRID_STANDING_FACT_POLICY_ID,
    HYBRID_STANDING_FACT_QUALIFICATION_SCHEMA_ID,
    HYBRID_STANDING_FACT_SCHEMA_ID,
    HybridStandingFactCommand,
    run_hybrid_standing_fact_plan,
)
from kotekomi_application.linguistic_analysis import (
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticAnalyzer,
    LinguisticToken,
    UniversalPartOfSpeech,
)
from kotekomi_application.mention_proposer import (
    MentionProposalBatch,
    MentionProposalInput,
    MentionProposer,
)
from kotekomi_application.nominalization_analysis import (
    NominalizationAnalysis,
    NominalizationAnalysisInput,
    NominalizationAnalyzer,
    NominalizationCandidate,
)
from kotekomi_application.semantic_proposition import (
    NaturalLanguageInferenceExecution,
    NaturalLanguageInferenceInput,
    NaturalLanguageInferencePort,
)
from kotekomi_application.semantic_reference_challenge_model_output import (
    semantic_reference_challenge_schema_bytes,
)
from kotekomi_application.semantic_reference_validation_model_output import (
    semantic_reference_candidate_validation_schema_bytes,
)
from kotekomi_application.semantic_references import (
    CoreferenceExecution,
    CoreferenceInput,
    CoreferenceProposerPort,
    CoreferenceTokenizer,
)
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_application.staged_model_extraction import (
    ExecutionSetting,
    HybridMentionBoundaryAdjudicationTaskSchemaRegistry,
    HybridMentionInterpretationTaskSchemaRegistry,
    HybridMentionProposalTaskSchemaRegistry,
    ModelRunIdFactory,
    ModelTaskRuntime,
)
from kotekomi_domain import (
    IngestionChangeSetOrigin,
    hybrid_event_ontology_slice_sha256,
    hybrid_event_semantics_profile_sha256,
)
from kotekomi_domain.models import JsonValue

from kotekomi_pipelines.config import PipelineConfig
from kotekomi_pipelines.model_runtime import build_model_task_runtime

_PROMPT_NAMES = (
    "hybrid_mention_occurrence_selection_v2.md",
    "hybrid_mention_boundary_adjudication_v2.md",
    "hybrid_mention_interpretation_task_v2.md",
    "hybrid_mention_ontology_card_v1.md",
    "semantic_reference_challenge_v4.md",
    "semantic_reference_candidate_validation_v1.md",
    "event_verb_role_v1.md",
    "event_verb_similarity_v1.md",
    "event_noun_inventory_v1.md",
    "event_noun_dependent_kind_v1.md",
    "event_noun_media_artifact_v1.md",
    "event_noun_governor_distinct_v1.md",
    "event_noun_reaction_v1.md",
    "event_noun_standing_v1.md",
    "hybrid_event_frame_selection_v1.md",
    "hybrid_event_frame_fit_v1.md",
    "hybrid_event_role_selection_v1.md",
    "hybrid_event_presentation_v1.md",
    "hybrid_semantic_support_v1.md",
    "hybrid_standing_fact_task_v3.md",
    "hybrid_standing_fact_qualification_v1.md",
)

type _StageResult = (
    HybridMentionPreviewResult
    | HybridReferencePreviewResult
    | HybridEntityGroundingResult
    | HybridEventTriggerResult
    | HybridEventSemanticsResult
)


@dataclass(frozen=True)
class HybridDocumentIngestionInput:
    ingestion_run_id: str
    source_id: str
    document_id: str
    representation_id: str
    capture_provenance_activity_id: str
    normalized_source_url: str


@dataclass(frozen=True)
class HybridParagraphProgress:
    ordinal: int
    total: int
    status: str
    receipt_reused: bool


@dataclass(frozen=True)
class HybridParagraphStageProgress:
    """One live event inside a single paragraph route.

    ``stage_id`` is ``None`` for the paragraph-started and paragraph-finished
    boundary events; otherwise it names the stage that just completed and
    ``stage_output`` carries that stage's parsed preview or plan object.
    """

    ordinal: int
    total: int
    representation_id: str
    paragraph_node_id: str
    stage_id: HybridStageId | None
    stage_output: object | None
    finished: bool


@dataclass(frozen=True)
class HybridDocumentIngestionResult:
    closure: HybridDocumentClosureResult
    plan: HybridDocumentPlan
    coverage_report: HybridDocumentCoverageReport
    reused_paragraph_count: int


@dataclass(frozen=True)
class _UnavailableEntityLinker:
    error: Exception
    identity: EntityLinkerIdentity

    def link(self, request: EntityLinkingInput) -> EntityLinkingExecution:
        del request
        raise self.error


@dataclass(frozen=True)
class _UnavailableMentionProposer:
    error: Exception

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        del proposal_input
        raise self.error


class _FixtureMentionProposer:
    """Deterministic empty proposer used only by the explicit fixture runtime."""

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        del proposal_input
        return MentionProposalBatch(
            proposer_id="fixture:1",
            model_id="fixture-empty-mention-proposer",
            model_revision="1",
            configuration=(),
            load_elapsed_milliseconds=0,
            inference_elapsed_milliseconds=0,
            proposals=(),
        )


@dataclass(frozen=True)
class _FixtureNli:
    def classify(self, request: NaturalLanguageInferenceInput) -> NaturalLanguageInferenceExecution:
        del request
        return NaturalLanguageInferenceExecution(
            model_id="fixture-nli",
            model_revision="1",
            resource_identity="fixture-nli-resource",
            contradiction_score=0.01,
            entailment_score=0.98,
            neutral_score=0.01,
            elapsed_milliseconds=0,
        )


@dataclass(frozen=True)
class _UnavailableNli:
    error: Exception

    def classify(self, request: NaturalLanguageInferenceInput) -> NaturalLanguageInferenceExecution:
        del request
        raise RuntimeError(f"The NLI Resource is unavailable: {self.error}") from self.error


@dataclass(frozen=True)
class _FixtureCoreference:
    tokenizer_id: str = "fixture-coreference-tokenizer"

    def count_tokens(self, rendered_input: bytes) -> int:
        return max(1, len(rendered_input.decode().split()))

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        del request
        return CoreferenceExecution(
            model_id="fixture-coreference",
            model_revision="1",
            resource_identity="fixture-coreference-resource",
            clusters=(),
            elapsed_milliseconds=0,
            raw_output=b'{"clusters":[]}',
        )


class _FixtureLinguisticAnalyzer:
    """Deterministic broad candidate annotations for fixture-only composition tests."""

    def analyze(self, request: LinguisticAnalysisInput) -> LinguisticAnalysis:
        occurrences = source_occurrences(request.source_text)
        return LinguisticAnalysis(
            source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
            producer_id="fixture-linguistic-analyzer",
            model_id="fixture-linguistic-model",
            model_version="1",
            resource_identity="f" * 64,
            tokens=tuple(
                LinguisticToken(
                    token_id=f"t{ordinal}",
                    sentence_id="s1",
                    text=occurrence.text,
                    start=occurrence.start,
                    end=occurrence.end,
                    lemma=occurrence.text.casefold(),
                    part_of_speech=UniversalPartOfSpeech.NOUN,
                    dependency_relation="root" if ordinal == 1 else "dep",
                    head_token_id=None if ordinal == 1 else "t1",
                )
                for ordinal, occurrence in enumerate(occurrences, start=1)
            ),
        )


class _FixtureNominalizationAnalyzer:
    def analyze(self, request: NominalizationAnalysisInput) -> NominalizationAnalysis:
        return NominalizationAnalysis(
            source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
            producer_id="fixture-nominalization-analyzer",
            model_id="fixture-nominalization-model",
            model_revision="1",
            resource_identity="f" * 64,
            threshold=0.45,
            candidates=tuple(
                NominalizationCandidate(
                    linguistic_token_id=token.token_id,
                    text=token.text,
                    start=token.start,
                    end=token.end,
                    lexical_candidate=True,
                    positive_logit=1.0,
                    negative_logit=-1.0,
                    nominalization_probability=0.7310585786300049,
                )
                for token in request.linguistic_analysis.tokens
                if token.part_of_speech is UniversalPartOfSpeech.NOUN
            ),
        )


@dataclass(frozen=True)
class _UnavailableCoreference:
    error: Exception
    tokenizer_id: str = "unavailable-coreference-tokenizer"

    def count_tokens(self, rendered_input: bytes) -> int:
        del rendered_input
        raise RuntimeError(f"The F-Coref Resource is unavailable: {self.error}") from self.error

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        del request
        raise RuntimeError(f"The F-Coref Resource is unavailable: {self.error}") from self.error


class _CoreferenceRuntime(CoreferenceProposerPort, CoreferenceTokenizer, Protocol):
    pass


class _RuntimeResources:
    """Create expensive optional Adapters only after the first receipt cache miss."""

    def __init__(self, config: PipelineConfig, runtime: ModelTaskRuntime) -> None:
        self._config = config
        self.runtime = runtime
        self._proposer: MentionProposer | None = None
        self._linker: EntityLinkingPort | None = None
        self._nli: NaturalLanguageInferencePort | None = None
        self._coreference: _CoreferenceRuntime | None = None
        self._fcoref: FCorefAdapter | None = None
        self._refined: RefinedEntityLinkingAdapter | None = None
        self._linguistic_analyzer: LinguisticAnalyzer | None = None
        self._nominalization_analyzer: NominalizationAnalyzer | None = None

    @property
    def proposer(self) -> MentionProposer:
        if self._proposer is None:
            if self._config.model_execution.adapter == "fixture":
                self._proposer = _FixtureMentionProposer()
            else:
                try:
                    self._proposer = GlinerMentionProposer(
                        model_directory=gliner_model_path(self._config.model_resource_root)
                    )
                except Exception as error:
                    self._proposer = _UnavailableMentionProposer(error)
        return self._proposer

    @property
    def linker(self) -> EntityLinkingPort:
        if self._linker is None:
            self._linker = self._build_linker()
        return self._linker

    @property
    def nli(self) -> NaturalLanguageInferencePort:
        if self._nli is None:
            if self._config.model_execution.adapter == "fixture":
                self._nli = _FixtureNli()
            else:
                try:
                    self._nli = DebertaNliAdapter(
                        model_directory=nli_model_path(self._config.model_resource_root).resolve(),
                        resource_identity=nli_expected_resource_identity(),
                    )
                except (OSError, RuntimeError, ValueError) as error:
                    self._nli = _UnavailableNli(error)
        return self._nli

    @property
    def coreference(self) -> _CoreferenceRuntime:
        if self._coreference is None:
            if self._config.model_execution.adapter == "fixture":
                self._coreference = _FixtureCoreference()
            else:
                try:
                    root = self._config.model_resource_root
                    self._fcoref = FCorefAdapter(
                        FCorefConfig(
                            python_executable=fcoref_python_path(root),
                            worker_script=(
                                Path(__file__).resolve().parents[4] / "scripts" / "fcoref_worker.py"
                            ),
                            model_directory=fcoref_model_path(root).resolve(),
                            resource_identity=fcoref_expected_resource_identity(),
                        )
                    )
                    self._coreference = self._fcoref
                except (OSError, RuntimeError, ValueError) as error:
                    self._coreference = _UnavailableCoreference(error)
        assert self._coreference is not None
        return self._coreference

    @property
    def linguistic_analyzer(self) -> LinguisticAnalyzer:
        if self._linguistic_analyzer is None:
            if self._config.model_execution.adapter == "fixture":
                self._linguistic_analyzer = _FixtureLinguisticAnalyzer()
            else:
                self._linguistic_analyzer = StanzaLinguisticAnalyzer(
                    model_directory=stanza_model_path(self._config.model_resource_root),
                    resource_identity=stanza_expected_resource_identity(),
                )
        return self._linguistic_analyzer

    @property
    def nominalization_analyzer(self) -> NominalizationAnalyzer:
        if self._nominalization_analyzer is None:
            if self._config.model_execution.adapter == "fixture":
                self._nominalization_analyzer = _FixtureNominalizationAnalyzer()
            else:
                self._nominalization_analyzer = QANomNominalizationAnalyzer(
                    model_directory=qanom_model_path(self._config.model_resource_root).resolve(),
                    lexical_resource_directory=qanom_lexical_resource_path(
                        self._config.model_resource_root
                    ).resolve(),
                    resource_identity=qanom_expected_resource_identity(),
                )
        return self._nominalization_analyzer

    def close(self) -> None:
        if self._refined is not None:
            self._refined.close()
        if self._fcoref is not None:
            self._fcoref.close()
        close_runtime = getattr(self.runtime, "close", None)
        if close_runtime is not None:
            close_runtime()

    def _build_linker(self) -> EntityLinkingPort:
        identity = _entity_linker_identity(self._config)
        worker_script = (
            Path(__file__).resolve().parents[4] / "scripts" / "refined_entity_linking_worker.py"
        )
        try:
            self._refined = RefinedEntityLinkingAdapter(
                RefinedEntityLinkingConfig(
                    python_executable=refined_python_path(self._config.model_resource_root),
                    worker_script=worker_script,
                    data_dir=refined_data_path(self._config.model_resource_root),
                    timeout_seconds=self._config.entity_linking.timeout_seconds,
                )
            )
        except (OSError, RuntimeError, ValueError) as error:
            return _UnavailableEntityLinker(error, identity)
        return self._refined


def run_hybrid_document_ingestion(
    *,
    input: HybridDocumentIngestionInput,
    config: PipelineConfig,
    archive: LocalArchiveStore,
    progress: Callable[[HybridParagraphProgress], None] | None = None,
    stage_progress: Callable[[HybridParagraphStageProgress], None] | None = None,
    model_run_id_factory: ModelRunIdFactory,
) -> HybridDocumentIngestionResult:
    """Run or replay every paragraph route before document reconciliation."""
    prompts = _prompt_bytes()
    runtime = build_model_task_runtime(config.model_execution)
    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        plan = plan_hybrid_document(
            _policy_input(input.representation_id, config, runtime, prompts),
            ledger,
            archive,
        )
    resources = _RuntimeResources(config, runtime)
    receipts: list[HybridParagraphReceipt] = []
    reused_count = 0
    total = len(plan.manifest.work_items)
    try:
        for work in plan.manifest.work_items:
            with sqlite_ledger_transaction(config.ledger_path) as ledger:
                receipt = load_reusable_hybrid_paragraph_receipt(
                    manifest=plan.manifest,
                    work=work,
                    ledger=ledger,
                    archive=archive,
                )
            reused = receipt is not None
            if receipt is None:
                receipt = _run_paragraph(
                    config=config,
                    manifest=plan.manifest,
                    work_ordinal=work.ordinal,
                    archive=archive,
                    resources=resources,
                    model_run_id_factory=model_run_id_factory,
                    prompts=prompts,
                    stage_progress=stage_progress,
                    total=total,
                )
            else:
                reused_count += 1
                _emit_stage_progress(
                    stage_progress,
                    ordinal=work.ordinal,
                    total=total,
                    representation_id=plan.manifest.representation_id,
                    paragraph_node_id=work.paragraph_node_id,
                )
                _emit_stage_progress(
                    stage_progress,
                    ordinal=work.ordinal,
                    total=total,
                    representation_id=plan.manifest.representation_id,
                    paragraph_node_id=work.paragraph_node_id,
                    finished=True,
                )
            receipts.append(receipt)
            if progress is not None:
                progress(
                    HybridParagraphProgress(
                        ordinal=work.ordinal,
                        total=len(plan.manifest.work_items),
                        status=receipt.status.value,
                        receipt_reused=reused,
                    )
                )
        with sqlite_ledger_transaction(config.ledger_path) as ledger:
            report = build_hybrid_document_coverage_report(
                manifest=plan.manifest,
                ledger=ledger,
                archive=archive,
            )
            closure = close_hybrid_document_ingestion(
                HybridDocumentClosureInput(
                    ingestion_run_id=input.ingestion_run_id,
                    source_id=input.source_id,
                    document_id=input.document_id,
                    representation_id=input.representation_id,
                    capture_provenance_activity_id=input.capture_provenance_activity_id,
                    normalized_source_url=input.normalized_source_url,
                    report_id=report.id,
                    analysis_origin=(
                        IngestionChangeSetOrigin.REUSED
                        if reused_count == len(receipts)
                        else IngestionChangeSetOrigin.EXECUTED
                    ),
                    closed_at=datetime.now(UTC),
                ),
                ledger=ledger,
                archive=archive,
            )
    finally:
        resources.close()
    return HybridDocumentIngestionResult(closure, plan, report, reused_count)


def _emit_stage_progress(
    stage_progress: Callable[[HybridParagraphStageProgress], None] | None,
    *,
    ordinal: int,
    total: int,
    representation_id: str,
    paragraph_node_id: str,
    stage_id: HybridStageId | None = None,
    stage_output: object | None = None,
    finished: bool = False,
) -> None:
    if stage_progress is None:
        return
    stage_progress(
        HybridParagraphStageProgress(
            ordinal=ordinal,
            total=total,
            representation_id=representation_id,
            paragraph_node_id=paragraph_node_id,
            stage_id=stage_id,
            stage_output=stage_output,
            finished=finished,
        )
    )


def _run_paragraph(
    *,
    config: PipelineConfig,
    manifest: HybridPipelinePolicyManifest,
    work_ordinal: int,
    archive: LocalArchiveStore,
    resources: _RuntimeResources,
    model_run_id_factory: ModelRunIdFactory,
    prompts: dict[str, bytes],
    stage_progress: Callable[[HybridParagraphStageProgress], None] | None = None,
    total: int = 1,
) -> HybridParagraphReceipt:
    work = manifest.work_items[work_ordinal]
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
    )
    profile = ContextModelProfile(
        config.model_execution.profile_name or "lm-studio",
        config.model_execution.context_tokens,
        config.model_execution.max_output_tokens,
        256,
    )
    generation = _generation_parameters(config)
    stages: list[HybridParagraphStageRecord] = []
    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp1 = run_hybrid_mention_preview(
            command=HybridMentionPreviewCommand(
                representation_id=manifest.representation_id,
                paragraph_node_id=work.paragraph_node_id,
                model_profile=profile,
                generation_parameters=generation,
            ),
            ledger=ledger,
            archive=archive,
            proposer=resources.proposer,
            model_runtime=resources.runtime,
            model_run_id_factory=model_run_id_factory,
            tokenizer=resources.runtime,
            proposal_prompt_bytes=prompts["hybrid_mention_occurrence_selection_v2.md"],
            boundary_adjudication_prompt_bytes=prompts[
                "hybrid_mention_boundary_adjudication_v2.md"
            ],
            interpretation_prompt_bytes=prompts["hybrid_mention_interpretation_task_v2.md"],
            ontology_card_bytes=prompts["hybrid_mention_ontology_card_v1.md"],
        )
    stages.append(_stage(HybridStageId.HP1_MENTIONS, hp1))
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        stage_id=HybridStageId.HP1_MENTIONS,
        stage_output=hp1.preview,
    )
    if hp1.preview.terminal_status is HybridPreviewStatus.BLOCKED:
        stages.extend(_not_run_stages(HybridStageId.HP1_MENTIONS, "blocked"))
        receipt = build_hybrid_paragraph_receipt(
            manifest=manifest,
            work=work,
            context_manifest_id=hp1.preview.context_manifest_id,
            stages=tuple(stages),
        )
        publish_hybrid_paragraph_receipt(receipt, archive)
        _emit_stage_progress(
            stage_progress,
            ordinal=work_ordinal,
            total=total,
            representation_id=manifest.representation_id,
            paragraph_node_id=work.paragraph_node_id,
            finished=True,
        )
        return receipt

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp2 = run_hybrid_reference_preview(
            command=HybridReferencePreviewCommand(hp1.preview.id, profile, generation),
            ledger=ledger,
            archive=archive,
            coreference_proposer=resources.coreference,
            coreference_tokenizer=resources.coreference,
            model_runtime=resources.runtime,
            model_run_id_factory=model_run_id_factory,
            challenge_prompt_bytes=prompts["semantic_reference_challenge_v4.md"],
            validation_prompt_bytes=prompts["semantic_reference_candidate_validation_v1.md"],
        )
    stages.append(_stage(HybridStageId.HP2_REFERENCES, hp2))
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        stage_id=HybridStageId.HP2_REFERENCES,
        stage_output=hp2.preview,
    )

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp3 = run_hybrid_entity_grounding_preview(
            command=HybridEntityGroundingCommand(hp2.preview.id),
            ledger=ledger,
            archive=archive,
            linker=resources.linker,
        )
    stages.append(_stage(HybridStageId.HP3_GROUNDING, hp3))
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        stage_id=HybridStageId.HP3_GROUNDING,
        stage_output=hp3.preview,
    )

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp4 = run_hybrid_event_trigger_preview(
            command=HybridEventTriggerCommand(hp3.preview.id, profile, generation),
            ledger=ledger,
            archive=archive,
            model_runtime=resources.runtime,
            model_run_id_factory=model_run_id_factory,
            tokenizer=resources.runtime,
            prompts=HybridEventTriggerPrompts(
                verb_role=prompts["event_verb_role_v1.md"],
                verb_similarity=prompts["event_verb_similarity_v1.md"],
                noun_inventory=prompts["event_noun_inventory_v1.md"],
                noun_dependent_kind=prompts["event_noun_dependent_kind_v1.md"],
                noun_media_artifact=prompts["event_noun_media_artifact_v1.md"],
                noun_governor_distinct=prompts["event_noun_governor_distinct_v1.md"],
                noun_reaction=prompts["event_noun_reaction_v1.md"],
                noun_standing=prompts["event_noun_standing_v1.md"],
            ),
            linguistic_analyzer=resources.linguistic_analyzer,
            nominalization_analyzer=resources.nominalization_analyzer,
        )
    stages.append(_stage(HybridStageId.HP4_EVENT_TRIGGERS, hp4))
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        stage_id=HybridStageId.HP4_EVENT_TRIGGERS,
        stage_output=hp4.preview,
    )

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp6 = run_hybrid_event_semantics_preview(
            command=HybridEventSemanticsCommand(
                hp4.preview.id,
                profile,
                generation,
                governed_enrichment_requested=False,
            ),
            ledger=ledger,
            archive=archive,
            model_runtime=resources.runtime,
            model_run_id_factory=model_run_id_factory,
            tokenizer=resources.runtime,
            frame_selection_prompt_bytes=prompts["hybrid_event_frame_selection_v1.md"],
            frame_fit_prompt_bytes=prompts["hybrid_event_frame_fit_v1.md"],
            role_selection_prompt_bytes=prompts["hybrid_event_role_selection_v1.md"],
            presentation_prompt_bytes=prompts["hybrid_event_presentation_v1.md"],
            support_prompt_bytes=prompts["hybrid_semantic_support_v1.md"],
            nli_runtime=resources.nli,
        )
    publish_hybrid_event_semantics_preview(hp6, archive)
    stages.append(_stage(HybridStageId.HP6_EVENT_SEMANTICS, hp6))
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        stage_id=HybridStageId.HP6_EVENT_SEMANTICS,
        stage_output=hp6.preview,
    )

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp7 = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)
    hp7_sha256, _ = publish_hybrid_proposal_plan(hp7, archive)
    stages.append(
        HybridParagraphStageRecord(
            stage_id=HybridStageId.HP7_PROPOSAL_PLAN,
            disposition=HybridStageDisposition.CREATED,
            output_id=hp7.id,
            output_sha256=hp7_sha256,
            terminal_status="complete",
            diagnostics=hp7.diagnostics,
        )
    )
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        stage_id=HybridStageId.HP7_PROPOSAL_PLAN,
        stage_output=hp7,
    )
    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp10 = run_hybrid_standing_fact_plan(
            command=HybridStandingFactCommand(
                hp7.id,
                profile,
                generation,
                datetime.now(UTC),
            ),
            ledger=ledger,
            archive=archive,
            model_runtime=resources.runtime,
            model_run_id_factory=model_run_id_factory,
            tokenizer=resources.runtime,
            prompt_bytes=prompts["hybrid_standing_fact_task_v3.md"],
            qualification_prompt_bytes=prompts["hybrid_standing_fact_qualification_v1.md"],
            nli_runtime=resources.nli,
        )
    held_fact_count = sum(item.disposition.value == "held" for item in hp10.plan.decisions)
    hp10_diagnostics = tuple(
        sorted(
            (
                *hp10.plan.diagnostics,
                *((f"held_standing_facts:{held_fact_count}",) if held_fact_count else ()),
            )
        )
    )
    stages.append(
        HybridParagraphStageRecord(
            stage_id=HybridStageId.HP10_STANDING_FACTS,
            disposition=HybridStageDisposition.CREATED,
            output_id=hp10.plan.id,
            output_sha256=hp10.sha256,
            terminal_status=hp10.plan.terminal_status.value,
            diagnostics=hp10_diagnostics,
        )
    )
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        stage_id=HybridStageId.HP10_STANDING_FACTS,
        stage_output=hp10.plan,
    )
    receipt = build_hybrid_paragraph_receipt(
        manifest=manifest,
        work=work,
        context_manifest_id=hp1.preview.context_manifest_id,
        stages=tuple(stages),
        proposed_change_ids=tuple(item.id for item in hp10.plan.proposed_changes),
    )
    publish_hybrid_paragraph_receipt(receipt, archive)
    _emit_stage_progress(
        stage_progress,
        ordinal=work_ordinal,
        total=total,
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        finished=True,
    )
    return receipt


def _stage(stage_id: HybridStageId, result: _StageResult) -> HybridParagraphStageRecord:
    preview = result.preview
    terminal = getattr(preview, "terminal_status", "complete")
    return HybridParagraphStageRecord(
        stage_id=stage_id,
        disposition=HybridStageDisposition.CREATED,
        output_id=preview.id,
        output_sha256=result.sha256,
        terminal_status=cast(str, getattr(terminal, "value", terminal)),
        diagnostics=tuple(cast(tuple[str, ...], getattr(preview, "diagnostics", ()))),
    )


def _not_run_stages(
    stopped_stage: HybridStageId,
    terminal_status: str,
) -> tuple[HybridParagraphStageRecord, ...]:
    start = HYBRID_STAGE_ORDER.index(stopped_stage) + 1
    diagnostic = f"stopped_after:{stopped_stage.value}:{terminal_status}"
    return tuple(
        HybridParagraphStageRecord(
            stage_id=stage,
            disposition=HybridStageDisposition.NOT_RUN,
            diagnostics=(diagnostic,),
        )
        for stage in HYBRID_STAGE_ORDER[start:]
    )


def _policy_input(
    representation_id: str,
    config: PipelineConfig,
    runtime: ModelTaskRuntime,
    prompts: dict[str, bytes],
) -> HybridPolicyManifestInput:
    identity = runtime.configured_identity
    pins = [
        HybridPolicyPin(kind="prompt", identity=name.removesuffix(".md"), sha256=_sha(payload))
        for name, payload in prompts.items()
    ]
    mention_proposal_schema = HybridMentionProposalTaskSchemaRegistry().resolve(
        "hybrid_mention_occurrence_selection_text_v1"
    )
    boundary_adjudication_schema = HybridMentionBoundaryAdjudicationTaskSchemaRegistry().resolve(
        "hybrid_mention_boundary_adjudication_text_v2"
    )
    mention_interpretation_schema = HybridMentionInterpretationTaskSchemaRegistry().resolve(
        "hybrid_mention_interpretation_text_v2"
    )
    schema_bytes = {
        mention_proposal_schema.schema_id: mention_proposal_schema.canonical_schema_bytes,
        boundary_adjudication_schema.schema_id: (
            boundary_adjudication_schema.canonical_schema_bytes
        ),
        mention_interpretation_schema.schema_id: (
            mention_interpretation_schema.canonical_schema_bytes
        ),
        SEMANTIC_REFERENCE_CHALLENGE_SCHEMA_ID: semantic_reference_challenge_schema_bytes(),
        SEMANTIC_REFERENCE_VALIDATION_SCHEMA_ID: (
            semantic_reference_candidate_validation_schema_bytes()
        ),
        EVENT_HEAD_JUDGMENT_SCHEMA_ID: event_head_answer_schema_bytes(),
        EVENT_VERB_ROLE_SCHEMA_ID: event_verb_role_answer_schema_bytes(),
        EVENT_BINARY_SEMANTIC_SCHEMA_ID: binary_semantic_answer_schema_bytes(),
        HYBRID_EVENT_FRAME_SELECTION_SCHEMA_ID: event_frame_selection_schema_bytes(),
        HYBRID_EVENT_ROLE_SELECTION_SCHEMA_ID: event_semantic_role_target_schema_bytes(),
        HYBRID_EVENT_PRESENTATION_SCHEMA_ID: event_presentation_schema_bytes(),
        HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID: semantic_support_schema_bytes(),
        HYBRID_STANDING_FACT_SCHEMA_ID: standing_fact_schema_bytes(),
        HYBRID_STANDING_FACT_QUALIFICATION_SCHEMA_ID: (standing_fact_qualification_schema_bytes()),
    }
    pins.extend(
        HybridPolicyPin(kind="schema", identity=name, sha256=_sha(payload))
        for name, payload in schema_bytes.items()
    )
    pins.extend(
        (
            HybridPolicyPin(
                kind="ontology",
                identity="hybrid_event_core_v1",
                sha256=hybrid_event_ontology_slice_sha256(),
            ),
            HybridPolicyPin(
                kind="ontology",
                identity="hybrid_event_semantics_v4",
                sha256=hybrid_event_semantics_profile_sha256(),
            ),
            HybridPolicyPin(
                kind="model_resource",
                identity="nli_deberta_v3_base_v1",
                sha256=nli_expected_resource_identity(),
            ),
            HybridPolicyPin(
                kind="model_resource",
                identity="fcoref_v1",
                sha256=fcoref_expected_resource_identity(),
            ),
            HybridPolicyPin(
                kind="model_resource",
                identity="stanza_english_v1",
                sha256=stanza_expected_resource_identity(),
            ),
            HybridPolicyPin(
                kind="model_resource",
                identity="qanom_nominalization_v1",
                sha256=qanom_expected_resource_identity(),
            ),
        )
    )
    for policy_id in (
        HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
        HYBRID_MENTION_PREVIEW_POLICY_ID,
        HYBRID_REFERENCE_POLICY_ID,
        HYBRID_ENTITY_GROUNDING_POLICY_ID,
        HYBRID_EVENT_TRIGGER_POLICY_ID,
        HYBRID_EVENT_SEMANTICS_POLICY_ID,
        HYBRID_PROPOSAL_POLICY_ID,
        HYBRID_STANDING_FACT_POLICY_ID,
    ):
        pins.append(
            HybridPolicyPin(
                kind="policy",
                identity=policy_id,
                sha256=_sha(policy_id.encode()),
            )
        )
    model_identity: dict[str, JsonValue] = {
        "adapter": config.model_execution.adapter,
        "endpoint": config.model_execution.endpoint,
        "name": identity.name,
        "weights_digest": identity.weights_digest,
        "runtime": identity.runtime,
        "tokenizer_id": identity.tokenizer_id,
        "context_tokens": config.model_execution.context_tokens,
        "reserved_output_tokens": config.model_execution.max_output_tokens,
        "safety_margin_tokens": 256,
        "timeout_seconds": config.model_execution.timeout_seconds,
    }
    proposer_identity: dict[str, JsonValue]
    if config.model_execution.adapter == "fixture":
        proposer_identity = {
            "producer_id": "fixture:1",
            "model_id": "fixture-empty-mention-proposer",
            "model_revision": "1",
            "requested_kinds": cast(JsonValue, list(PROPOSER_CONTEXTUAL_KINDS)),
        }
    else:
        proposer_identity = {
            "producer_id": f"gliner:{GLINER_PACKAGE_VERSION}",
            "model_id": GLINER_MODEL_ID,
            "model_revision": GLINER_MODEL_REVISION,
            "resource_identity": gliner_expected_resource_identity(),
            "device": GLINER_DEVICE,
            "threshold": GLINER_THRESHOLD,
            "requested_kinds": cast(JsonValue, list(PROPOSER_CONTEXTUAL_KINDS)),
        }
    linker_identity = cast(
        dict[str, JsonValue],
        _entity_linker_identity(config).model_dump(mode="json"),
    )
    linker_identity["configured"] = True
    return HybridPolicyManifestInput(
        representation_id=representation_id,
        model_identity=model_identity,
        generation_parameters=cast(
            dict[str, JsonValue],
            {item.key: item.value for item in _generation_parameters(config)},
        ),
        mention_proposer_identity=proposer_identity,
        entity_linker_identity=linker_identity,
        pins=tuple(sorted(pins, key=lambda item: (item.kind, item.identity))),
    )


def _entity_linker_identity(config: PipelineConfig) -> EntityLinkerIdentity:
    return EntityLinkerIdentity(
        producer_id="refined:1.0",
        model_id=REFINED_MODEL_ID,
        model_revision=REFINED_MODEL_REVISION,
        entity_set=REFINED_ENTITY_SET,
        package_revision=REFINED_PACKAGE_REVISION,
        resource_manifest_sha256=REFINED_RESOURCE_MANIFEST_SHA256,
        runtime_identity=REFINED_RUNTIME_IDENTITY,
        timeout_seconds=config.entity_linking.timeout_seconds,
    )


def _generation_parameters(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )


def _prompt_bytes() -> dict[str, bytes]:
    root = Path(__file__).resolve().parents[4] / "prompts"
    return {name: (root / name).read_bytes() for name in _PROMPT_NAMES}


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
