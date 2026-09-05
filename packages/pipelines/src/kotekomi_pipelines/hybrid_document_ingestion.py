"""HP-8 public document-wide composition of the HP-1 through HP-7 use cases."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from kotekomi_adapters import GlinerMentionProposer, LocalArchiveStore
from kotekomi_adapters.gliner_organization_mention_proposer import (
    GLINER_DEVICE,
    GLINER_MODEL_ID,
    GLINER_MODEL_REVISION,
    GLINER_PACKAGE_VERSION,
    GLINER_THRESHOLD,
)
from kotekomi_adapters.model_resources import (
    gliner_expected_resource_identity,
    gliner_model_path,
    refined_data_path,
    refined_python_path,
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
from kotekomi_application.hybrid_atomic_claim_preview import (
    HybridAtomicClaimCommand,
    HybridAtomicClaimResult,
    publish_hybrid_atomic_claim_preview,
    run_hybrid_atomic_claim_preview,
)
from kotekomi_application.hybrid_atomic_claims import HYBRID_ATOMIC_CLAIM_POLICY_ID
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
from kotekomi_application.hybrid_event_frame_preview import (
    FRAME_SCHEMA_ID,
    TRIGGER_SCHEMA_ID,
    HybridEventFrameCommand,
    HybridEventFrameResult,
    run_hybrid_event_frame_preview,
)
from kotekomi_application.hybrid_event_frames import HYBRID_EVENT_FRAME_POLICY_ID
from kotekomi_application.hybrid_event_model_output import (
    event_frame_schema_bytes,
    event_trigger_schema_bytes,
)
from kotekomi_application.hybrid_event_semantics import (
    HYBRID_EVENT_NORMALIZATION_SCHEMA_ID,
    HYBRID_EVENT_ROLE_COMPLETION_SCHEMA_ID,
    HYBRID_EVENT_SEMANTICS_POLICY_ID,
    HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID,
)
from kotekomi_application.hybrid_event_semantics_model_output import (
    event_semantic_role_target_schema_bytes,
    event_semantic_schema_bytes,
    semantic_support_schema_bytes,
)
from kotekomi_application.hybrid_event_semantics_preview import (
    HybridEventSemanticsCommand,
    HybridEventSemanticsResult,
    publish_hybrid_event_semantics_preview,
    run_hybrid_event_semantics_preview,
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
    HybridReferencePreviewCommand,
    HybridReferencePreviewResult,
    run_hybrid_reference_preview,
)
from kotekomi_application.mention_proposer import (
    MentionProposalBatch,
    MentionProposalInput,
    MentionProposer,
)
from kotekomi_application.staged_model_extraction import (
    ExecutionSetting,
    HybridMentionTaskSchemaRegistry,
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
    "hybrid_mention_task_v1.md",
    "hybrid_mention_ontology_card_v1.md",
    "hybrid_event_trigger_task_v1.md",
    "hybrid_event_frame_task_v1.md",
    "hybrid_event_normalization_v1.md",
    "hybrid_event_role_completion_v1.md",
    "hybrid_semantic_support_v1.md",
)

type _StageResult = (
    HybridMentionPreviewResult
    | HybridReferencePreviewResult
    | HybridEntityGroundingResult
    | HybridEventFrameResult
    | HybridAtomicClaimResult
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


class _RuntimeResources:
    """Create expensive optional Adapters only after the first receipt cache miss."""

    def __init__(self, config: PipelineConfig, runtime: ModelTaskRuntime) -> None:
        self._config = config
        self.runtime = runtime
        self._proposer: MentionProposer | None = None
        self._linker: EntityLinkingPort | None = None
        self._refined: RefinedEntityLinkingAdapter | None = None

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

    def close(self) -> None:
        if self._refined is not None:
            self._refined.close()
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
    model_run_id_factory: ModelRunIdFactory,
) -> HybridDocumentIngestionResult:
    """Run or replay HP-1 through HP-8 for every authoritative paragraph."""
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
                )
            else:
                reused_count += 1
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


def _run_paragraph(
    *,
    config: PipelineConfig,
    manifest: HybridPipelinePolicyManifest,
    work_ordinal: int,
    archive: LocalArchiveStore,
    resources: _RuntimeResources,
    model_run_id_factory: ModelRunIdFactory,
    prompts: dict[str, bytes],
) -> HybridParagraphReceipt:
    work = manifest.work_items[work_ordinal]
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
            prompt_bytes=prompts["hybrid_mention_task_v1.md"],
            ontology_card_bytes=prompts["hybrid_mention_ontology_card_v1.md"],
        )
    stages.append(_stage(HybridStageId.HP1_MENTIONS, hp1))
    if hp1.preview.terminal_status is HybridPreviewStatus.BLOCKED:
        stages.extend(_not_run_stages(HybridStageId.HP1_MENTIONS, "blocked"))
        receipt = build_hybrid_paragraph_receipt(
            manifest=manifest,
            work=work,
            context_manifest_id=hp1.preview.context_manifest_id,
            stages=tuple(stages),
        )
        publish_hybrid_paragraph_receipt(receipt, archive)
        return receipt

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp2 = run_hybrid_reference_preview(
            command=HybridReferencePreviewCommand(hp1.preview.id),
            ledger=ledger,
            archive=archive,
        )
    stages.append(_stage(HybridStageId.HP2_REFERENCES, hp2))

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp3 = run_hybrid_entity_grounding_preview(
            command=HybridEntityGroundingCommand(hp2.preview.id),
            ledger=ledger,
            archive=archive,
            linker=resources.linker,
        )
    stages.append(_stage(HybridStageId.HP3_GROUNDING, hp3))

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp4 = run_hybrid_event_frame_preview(
            command=HybridEventFrameCommand(hp3.preview.id, profile, generation),
            ledger=ledger,
            archive=archive,
            model_runtime=resources.runtime,
            model_run_id_factory=model_run_id_factory,
            tokenizer=resources.runtime,
            trigger_prompt_bytes=prompts["hybrid_event_trigger_task_v1.md"],
            frame_prompt_bytes=prompts["hybrid_event_frame_task_v1.md"],
        )
    stages.append(_stage(HybridStageId.HP4_EVENT_FRAMES, hp4))

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp5 = run_hybrid_atomic_claim_preview(
            command=HybridAtomicClaimCommand(hp4.preview.id, datetime.now(UTC)),
            ledger=ledger,
            archive=archive,
        )
    publish_hybrid_atomic_claim_preview(hp5, archive)
    stages.append(_stage(HybridStageId.HP5_ATOMIC_CLAIMS, hp5))

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp6 = run_hybrid_event_semantics_preview(
            command=HybridEventSemanticsCommand(hp5.preview.id, profile, generation),
            ledger=ledger,
            archive=archive,
            model_runtime=resources.runtime,
            model_run_id_factory=model_run_id_factory,
            tokenizer=resources.runtime,
            normalization_prompt_bytes=prompts["hybrid_event_normalization_v1.md"],
            role_completion_prompt_bytes=prompts["hybrid_event_role_completion_v1.md"],
            support_prompt_bytes=prompts["hybrid_semantic_support_v1.md"],
        )
    publish_hybrid_event_semantics_preview(hp6, archive)
    stages.append(_stage(HybridStageId.HP6_EVENT_SEMANTICS, hp6))

    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        hp7 = build_hybrid_proposal_plan(hp6.preview.id, ledger, archive)
    hp7_sha256, _ = publish_hybrid_proposal_plan(hp7, archive)
    held_count = sum(item.disposition.value == "held" for item in hp7.decisions)
    hp7_diagnostics = tuple(
        sorted((*hp7.diagnostics, *((f"held_events:{held_count}",) if held_count else ())))
    )
    stages.append(
        HybridParagraphStageRecord(
            stage_id=HybridStageId.HP7_PROPOSAL_PLAN,
            disposition=HybridStageDisposition.CREATED,
            output_id=hp7.id,
            output_sha256=hp7_sha256,
            terminal_status="complete",
            diagnostics=hp7_diagnostics,
        )
    )
    receipt = build_hybrid_paragraph_receipt(
        manifest=manifest,
        work=work,
        context_manifest_id=hp1.preview.context_manifest_id,
        stages=tuple(stages),
        proposed_change_ids=tuple(item.id for item in hp7.proposed_changes),
    )
    publish_hybrid_paragraph_receipt(receipt, archive)
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
    mention_schema = HybridMentionTaskSchemaRegistry().resolve("hybrid_mention_task_text_v1")
    schema_bytes = {
        mention_schema.schema_id: mention_schema.canonical_schema_bytes,
        TRIGGER_SCHEMA_ID: event_trigger_schema_bytes(),
        FRAME_SCHEMA_ID: event_frame_schema_bytes(),
        HYBRID_EVENT_NORMALIZATION_SCHEMA_ID: event_semantic_schema_bytes(),
        HYBRID_EVENT_ROLE_COMPLETION_SCHEMA_ID: event_semantic_role_target_schema_bytes(),
        HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID: semantic_support_schema_bytes(),
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
                identity="hybrid_event_semantics_v1",
                sha256=hybrid_event_semantics_profile_sha256(),
            ),
        )
    )
    for policy_id in (
        HYBRID_MENTION_PREVIEW_POLICY_ID,
        HYBRID_REFERENCE_POLICY_ID,
        HYBRID_ENTITY_GROUNDING_POLICY_ID,
        HYBRID_EVENT_FRAME_POLICY_ID,
        HYBRID_ATOMIC_CLAIM_POLICY_ID,
        HYBRID_EVENT_SEMANTICS_POLICY_ID,
        HYBRID_PROPOSAL_POLICY_ID,
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
