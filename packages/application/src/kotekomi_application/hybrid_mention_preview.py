"""HP-1 orchestration over authoritative context and fallible model Ports."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, cast

from kotekomi_domain import Document, ModelRunStatus, Source
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V2,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ContextTokenizer,
    RetrievalSelectionAnalysisUnitInput,
    build_context_manifest,
    create_analysis_unit_from_retrieval_selection,
    paragraph_source_segments,
    verify_context_manifest,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HYBRID_MENTION_PREVIEW_POLICY_ID,
    PROPOSER_CONTEXTUAL_KINDS,
    HybridExtractionPreview,
    HybridModelOutputArchive,
    HybridPreviewStatus,
    MentionBoundaryDecision,
    MentionCandidate,
    MentionInterpretation,
    MentionObservation,
    PreviewStore,
    build_hybrid_extraction_preview,
    canonical_hybrid_extraction_preview_bytes,
    fuse_mention_observations,
    hybrid_extraction_preview_sha256,
    hybrid_source_segment_id,
    map_proposal_drafts_to_observations,
    observation_from_proposal,
    reconcile_mention_boundaries,
    resolve_mention_interpretation,
    run_recorded_mention_proposer,
)
from kotekomi_application.mention_proposer import MentionProposalInput, MentionProposer
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    ExecutionSetting,
    HybridMentionTaskSchemaRegistry,
    ModelExecutionSpec,
    ModelRunIdFactory,
    ModelTaskRuntime,
    PinnedTaskSchema,
    StagedExtractionLedger,
    TaskSchemaRegistry,
    run_bounded_extraction,
)


class HybridMentionLedger(StagedExtractionLedger, Protocol):
    def get_document(self, record_id: str) -> Document | None: ...
    def get_source(self, record_id: str) -> Source | None: ...


class HybridMentionArchive(HybridModelOutputArchive, PreviewStore, Protocol):
    pass


@dataclass(frozen=True)
class HybridMentionPreviewCommand:
    representation_id: str
    paragraph_node_id: str
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]


@dataclass(frozen=True)
class HybridMentionPreviewResult:
    preview: HybridExtractionPreview
    sha256: str
    archive_path: str


def run_hybrid_mention_preview(
    *,
    command: HybridMentionPreviewCommand,
    ledger: HybridMentionLedger,
    archive: HybridMentionArchive,
    proposer: MentionProposer,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    prompt_bytes: bytes,
    ontology_card_bytes: bytes,
    schema_registry: TaskSchemaRegistry | None = None,
) -> HybridMentionPreviewResult:
    """Run HP-1 and publish one immutable terminal preview."""
    if not prompt_bytes or not ontology_card_bytes:
        raise ValueError("Hybrid mention preview requires pinned prompt and ontology card bytes.")
    bundle = ledger.get_document_representation_bundle(command.representation_id)
    if bundle is None:
        raise ValueError("Hybrid mention preview references a missing DocumentRepresentation.")
    node = next((item for item in bundle.nodes if item.id == command.paragraph_node_id), None)
    if node is None:
        raise ValueError("Hybrid mention preview references a missing DocumentNode.")
    if node.representation_id != command.representation_id:
        raise ValueError("Hybrid mention preview DocumentNode belongs to another representation.")
    if node.node_type != "paragraph":
        raise ValueError("Hybrid mention preview requires a paragraph DocumentNode.")
    text_view = next((item for item in bundle.text_views if item.id == node.text_view_id), None)
    if text_view is None:
        raise ValueError("Hybrid mention preview paragraph references a missing TextView.")
    paragraph_text = text_view.text[node.start_char : node.end_char]
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("Hybrid mention preview representation references a missing Document.")
    source = ledger.get_source(document.source_id)
    if source is None:
        raise ValueError("Hybrid mention preview Document references a missing Source.")
    registry = schema_registry or HybridMentionTaskSchemaRegistry()
    schema = registry.resolve("hybrid_mention_task_text_v1")
    unit = create_analysis_unit_from_retrieval_selection(
        RetrievalSelectionAnalysisUnitInput(
            representation_id=command.representation_id,
            focus_node_ids=(command.paragraph_node_id,),
            policy_id=HYBRID_MENTION_PREVIEW_POLICY_ID,
            task_type="hybrid_mention_preview",
        ),
        ledger,
    )
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=command.model_profile,
            prompt_id="hybrid_mention_task_v1",
            prompt_bytes=prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="hybrid_mention_context_v1",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V2,
        ),
        ledger,
        tokenizer,
    )
    manifest = planning.manifest
    if manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Hybrid mention ContextManifest is not ready: "
            f"{manifest.blocked_reason or manifest.status.value}"
        )
    verify_context_manifest(
        manifest.id,
        ledger,
        tokenizer,
        prompt_bytes,
        schema.canonical_schema_bytes,
    )
    segments = paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V2)
    segment_ids = {
        segment.label: hybrid_source_segment_id(command.representation_id, node.id, segment)
        for segment in segments
    }
    source_text_by_id = {segment_ids[item.label]: item.exact_text for item in segments}
    source_label_by_id = {value: key for key, value in segment_ids.items()}
    card_digest = hashlib.sha256(ontology_card_bytes).hexdigest()
    common_manifest_payload: dict[str, JsonValue] = {
        "id": manifest.id,
        "manifest_digest": manifest.manifest_digest,
        "representation_id": manifest.representation_id,
        "source_segment_ids": cast(JsonValue, segment_ids),
    }
    proposer_input = MentionProposalInput(segments, PROPOSER_CONTEXTUAL_KINDS)
    gliner = run_recorded_mention_proposer(
        representation_id=command.representation_id,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        context_manifest_payload=common_manifest_payload,
        proposal_input=proposer_input,
        proposer=proposer,
        ledger=ledger,
        archive=archive,
    )
    qwen_proposal_input = b"task: propose_mentions"
    qwen = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=source.id,
            document_id=document.id,
            representation_id=command.representation_id,
            context_manifest_id=manifest.id,
            prompt_bytes=prompt_bytes,
            execution_spec=_execution_spec(
                manifest,
                model_runtime,
                command.generation_parameters,
                schema,
                qwen_proposal_input,
            ),
            validator_version="hybrid_mention_proposal_validator_v1",
            task_type="hybrid_mention_proposal",
            task_local_input=qwen_proposal_input,
        ),
        ledger,
        archive,
        model_runtime,
        model_run_id_factory,
        tokenizer,
        registry,
    )
    extraction_task_ids = [gliner.extraction_task.id, qwen.extraction_task.id]
    model_run_ids = [gliner.model_run.id, qwen.model_run.id]
    diagnostics: list[str] = []
    traces: list[ExtractionStageTrace] = []
    trace_runs = {
        segment_ids[item.label]: _trace_run_id(
            segment_ids[item.label], gliner.model_run.id, qwen.model_run.id
        )
        for item in segments
    }
    if gliner.batch is None or gliner.model_run.status is not ModelRunStatus.SUCCEEDED:
        diagnostics.append("gliner_proposer_blocked")
    if qwen.model_run.status not in {ModelRunStatus.SUCCEEDED, ModelRunStatus.ABSTAINED}:
        diagnostics.append("qwen_proposer_blocked")
    if diagnostics:
        for segment in segments:
            source_segment_id = segment_ids[segment.label]
            traces.extend(
                (
                    _proposal_trace(
                        trace_run_id=trace_runs[source_segment_id],
                        ordinal=0,
                        source_segment_id=source_segment_id,
                        source_text=segment.exact_text,
                        producer_id="gliner",
                        extraction_task_id=gliner.extraction_task.id,
                        model_run_id=gliner.model_run.id,
                        model_run_status=gliner.model_run.status,
                        status=(
                            ExtractionStageStatus.COMPLETED
                            if gliner.batch is not None
                            and gliner.model_run.status is ModelRunStatus.SUCCEEDED
                            else ExtractionStageStatus.BLOCKED
                        ),
                    ),
                    _proposal_trace(
                        trace_run_id=trace_runs[source_segment_id],
                        ordinal=1,
                        source_segment_id=source_segment_id,
                        source_text=segment.exact_text,
                        producer_id="qwen2.5",
                        extraction_task_id=qwen.extraction_task.id,
                        model_run_id=qwen.model_run.id,
                        model_run_status=qwen.model_run.status,
                        status=(
                            ExtractionStageStatus.COMPLETED
                            if qwen.model_run.status
                            in {ModelRunStatus.SUCCEEDED, ModelRunStatus.ABSTAINED}
                            else ExtractionStageStatus.BLOCKED
                        ),
                    ),
                )
            )
        return _publish_preview(
            archive=archive,
            representation_id=command.representation_id,
            paragraph_node_id=node.id,
            manifest=manifest,
            card_digest=card_digest,
            extraction_task_ids=extraction_task_ids,
            model_run_ids=model_run_ids,
            traces=traces,
            terminal_status=HybridPreviewStatus.BLOCKED,
            diagnostics=diagnostics,
        )
    observations: list[MentionObservation] = []
    seen_observation_ids: set[str] = set()
    invalid_observations: list[str] = []
    invalid_by_producer_segment: dict[tuple[str, str], list[str]] = {}
    assert gliner.batch is not None
    segment_by_label = {item.label: item for item in segments}
    for index, proposal in enumerate(gliner.batch.proposals):
        try:
            segment = segment_by_label[proposal.source_segment_label]
            if (
                proposal.end > len(segment.exact_text)
                or segment.exact_text[proposal.start : proposal.end] != proposal.text
            ):
                raise ValueError("source mismatch")
            if not set(proposal.type_hints).issubset(proposer_input.type_hints):
                raise ValueError("unrequested type hint")
            observation = observation_from_proposal(
                proposal=proposal,
                source_segment_id=segment_ids[proposal.source_segment_label],
                producer_id=gliner.batch.proposer_id,
                execution_record_id=gliner.model_run.id,
            )
            if observation.id in seen_observation_ids:
                raise ValueError("duplicate observation")
            seen_observation_ids.add(observation.id)
            observations.append(observation)
        except (KeyError, ValueError) as error:
            diagnostic = (
                f"invalid_observation:gliner:{gliner.model_run.id}:{index}:{type(error).__name__}"
            )
            invalid_observations.append(diagnostic)
            source_segment_id = segment_ids.get(proposal.source_segment_label)
            if source_segment_id is not None:
                invalid_by_producer_segment.setdefault(("gliner", source_segment_id), []).append(
                    diagnostic
                )
    if qwen.mention_proposal_drafts is not None:
        for index, draft in enumerate(qwen.mention_proposal_drafts.proposals):
            try:
                mapped = map_proposal_drafts_to_observations(
                    drafts=(draft,),
                    source_segments=segments,
                    source_segment_ids=segment_ids,
                    producer_id="qwen2.5",
                    execution_record_id=qwen.model_run.id,
                )
                if any(item.id in seen_observation_ids for item in mapped):
                    raise ValueError("duplicate observation")
                seen_observation_ids.update(item.id for item in mapped)
                observations.extend(mapped)
            except ValueError as error:
                diagnostic = (
                    f"invalid_observation:qwen2.5:{qwen.model_run.id}:{index}:"
                    f"{type(error).__name__}"
                )
                invalid_observations.append(diagnostic)
                source_segment_id = segment_ids.get(draft.source_segment_label)
                if source_segment_id is not None:
                    invalid_by_producer_segment.setdefault(
                        ("qwen2.5", source_segment_id), []
                    ).append(diagnostic)
    diagnostics.extend(invalid_observations)
    ordered_observations = tuple(sorted(observations, key=_observation_key))
    for segment in segments:
        source_segment_id = segment_ids[segment.label]
        gliner_observations = tuple(
            item
            for item in ordered_observations
            if item.source_segment_id == source_segment_id
            and item.execution_record_id == gliner.model_run.id
        )
        qwen_observations = tuple(
            item
            for item in ordered_observations
            if item.source_segment_id == source_segment_id
            and item.execution_record_id == qwen.model_run.id
        )
        traces.extend(
            (
                _proposal_trace(
                    trace_run_id=trace_runs[source_segment_id],
                    ordinal=0,
                    source_segment_id=source_segment_id,
                    source_text=segment.exact_text,
                    producer_id="gliner",
                    extraction_task_id=gliner.extraction_task.id,
                    model_run_id=gliner.model_run.id,
                    model_run_status=gliner.model_run.status,
                    status=ExtractionStageStatus.COMPLETED,
                    observations=gliner_observations,
                    diagnostics=tuple(
                        sorted(invalid_by_producer_segment.get(("gliner", source_segment_id), []))
                    ),
                ),
                _proposal_trace(
                    trace_run_id=trace_runs[source_segment_id],
                    ordinal=1,
                    source_segment_id=source_segment_id,
                    source_text=segment.exact_text,
                    producer_id="qwen2.5",
                    extraction_task_id=qwen.extraction_task.id,
                    model_run_id=qwen.model_run.id,
                    model_run_status=qwen.model_run.status,
                    status=ExtractionStageStatus.COMPLETED,
                    observations=qwen_observations,
                    diagnostics=tuple(
                        sorted(invalid_by_producer_segment.get(("qwen2.5", source_segment_id), []))
                    ),
                    abstention_reason=qwen.model_run.abstention_reason,
                ),
            )
        )
    candidates = fuse_mention_observations(
        source_segments=source_text_by_id,
        observations=ordered_observations,
    )
    decisions, selected_candidates = reconcile_mention_boundaries(
        source_segments=source_text_by_id,
        observations=ordered_observations,
        candidates=candidates,
    )
    reconciliation_trace_by_segment: dict[str, str] = {}
    for segment in segments:
        segment_id = segment_ids[segment.label]
        trace = build_extraction_stage_trace(
            trace_run_id=trace_runs[segment_id],
            ordinal=2,
            stage_id="mention_boundary_reconciliation",
            stage_version="hybrid_mention_boundary_v1",
            producer_id="kotekomi_application",
            source_segment_id=segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            parent_trace_ids=tuple(
                sorted(item.id for item in traces if item.source_segment_id == segment_id)
            ),
            execution_record_ids=tuple(sorted(model_run_ids)),
            configuration={"policy_id": "hybrid_mention_boundary_v1"},
            input_payload={
                "candidate_ids": [
                    item.id for item in candidates if item.source_segment_id == segment_id
                ]
            },
            output_payload={
                "decision_ids": [
                    item.id for item in decisions if item.source_segment_id == segment_id
                ]
            },
            status=ExtractionStageStatus.COMPLETED,
        )
        traces.append(trace)
        reconciliation_trace_by_segment[segment_id] = trace.id
    interpretations: list[MentionInterpretation] = []
    failed_interpretations = 0
    next_ordinal = {segment_ids[item.label]: 3 for item in segments}
    for candidate in selected_candidates:
        local_input = _interpretation_task_input(
            candidate,
            source_label_by_id[candidate.source_segment_id],
            ontology_card_bytes,
            card_digest,
        )
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=source.id,
                document_id=document.id,
                representation_id=command.representation_id,
                context_manifest_id=manifest.id,
                prompt_bytes=prompt_bytes,
                execution_spec=_execution_spec(
                    manifest,
                    model_runtime,
                    command.generation_parameters,
                    schema,
                    local_input,
                ),
                validator_version="hybrid_mention_interpretation_validator_v1",
                task_type="hybrid_mention_interpretation",
                input_candidate_ids=(candidate.id,),
                task_local_input=local_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        extraction_task_ids.append(outcome.extraction_task.id)
        model_run_ids.append(outcome.model_run.id)
        ordinal = next_ordinal[candidate.source_segment_id]
        next_ordinal[candidate.source_segment_id] += 1
        status = ExtractionStageStatus.COMPLETED
        trace_diagnostics: tuple[str, ...] = ()
        output_payload: dict[str, JsonValue] = {"model_run_status": outcome.model_run.status.value}
        draft = outcome.mention_interpretation_draft
        if draft is None:
            status = ExtractionStageStatus.FAILED
            trace_diagnostics = ("interpretation_output_unavailable",)
            failed_interpretations += 1
            diagnostics.append(f"interpretation_failed:{candidate.id}:{outcome.model_run.id}")
        elif draft.candidate_label != "c1":
            status = ExtractionStageStatus.FAILED
            trace_diagnostics = ("interpretation_candidate_label_unknown",)
            failed_interpretations += 1
            diagnostics.append(
                f"interpretation_mapping_failed:{candidate.id}:{outcome.model_run.id}"
            )
        elif draft.support_segment_label not in segment_ids:
            status = ExtractionStageStatus.FAILED
            trace_diagnostics = ("interpretation_support_label_unknown",)
            failed_interpretations += 1
            diagnostics.append(
                f"interpretation_mapping_failed:{candidate.id}:{outcome.model_run.id}"
            )
        else:
            output_payload.update(
                {
                    "referentiality": draft.referentiality.value,
                    "contextual_kind": draft.contextual_kind.value,
                    "discourse_role": draft.discourse_role.value,
                    "support_label": draft.support_segment_label,
                }
            )
        trace = build_extraction_stage_trace(
            trace_run_id=trace_runs[candidate.source_segment_id],
            ordinal=ordinal,
            stage_id="mention_interpretation",
            stage_version="hybrid_mention_interpretation_v1",
            producer_id="qwen2.5",
            source_segment_id=candidate.source_segment_id,
            source_text_sha256=candidate.source_text_sha256,
            parent_trace_ids=(reconciliation_trace_by_segment[candidate.source_segment_id],),
            input_record_ids=(candidate.id,),
            execution_record_ids=(outcome.extraction_task.id, outcome.model_run.id),
            configuration={"ontology_card_sha256": card_digest},
            input_payload={
                "candidate_label": "c1",
                "candidate_source_label": source_label_by_id[candidate.source_segment_id],
                "candidate_text": candidate.text,
            },
            output_payload=output_payload,
            status=status,
            diagnostics=trace_diagnostics,
        )
        traces.append(trace)
        if status is ExtractionStageStatus.COMPLETED:
            assert draft is not None
            interpretations.append(
                resolve_mention_interpretation(
                    draft=draft,
                    candidate_labels={"c1": candidate},
                    source_segment_ids=segment_ids,
                    model_run_id=outcome.model_run.id,
                    trace_id=trace.id,
                )
            )
    terminal_status = (
        HybridPreviewStatus.PARTIAL if failed_interpretations else HybridPreviewStatus.COMPLETE
    )
    diagnostics.extend(
        f"interpretation_pending_boundary:{item.id}"
        for item in decisions
        if item.status.value == "ambiguous"
    )
    return _publish_preview(
        archive=archive,
        representation_id=command.representation_id,
        paragraph_node_id=node.id,
        manifest=manifest,
        card_digest=card_digest,
        observations=ordered_observations,
        candidates=candidates,
        decisions=decisions,
        interpretations=tuple(interpretations),
        extraction_task_ids=extraction_task_ids,
        model_run_ids=model_run_ids,
        traces=traces,
        terminal_status=terminal_status,
        diagnostics=diagnostics,
    )


def _execution_spec(
    manifest: ContextManifest,
    runtime: ModelTaskRuntime,
    generation_parameters: tuple[ExecutionSetting, ...],
    schema: PinnedTaskSchema,
    task_local_input: bytes,
) -> ModelExecutionSpec:
    rendered_input = manifest.rendered_input + b"\n\n[task]\n" + task_local_input
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=runtime.configured_identity,
        generation_parameters=generation_parameters,
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=schema.schema_id,
        schema_digest=schema.digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=hashlib.sha256(rendered_input).hexdigest(),
        output_contract_version=schema.output_contract_version,
    )


def _interpretation_task_input(
    candidate: MentionCandidate,
    source_segment_label: str,
    ontology_card_bytes: bytes,
    card_digest: str,
) -> bytes:
    return (
        b"task: interpret_mention\n"
        + b"candidate: c1\n"
        + f"candidate_source: {source_segment_label}\n".encode()
        + f"candidate_text: {candidate.text}\n".encode()
        + f"ontology_card_sha256: {card_digest}\n".encode()
        + b"ontology_guideline_card:\n"
        + ontology_card_bytes
    )


def _proposal_trace(
    *,
    trace_run_id: str,
    ordinal: int,
    source_segment_id: str,
    source_text: str,
    producer_id: str,
    extraction_task_id: str,
    model_run_id: str,
    model_run_status: ModelRunStatus,
    status: ExtractionStageStatus,
    observations: tuple[MentionObservation, ...] = (),
    diagnostics: tuple[str, ...] = (),
    abstention_reason: str | None = None,
) -> ExtractionStageTrace:
    trace_diagnostics = diagnostics
    if status is not ExtractionStageStatus.COMPLETED:
        trace_diagnostics = tuple(sorted({*diagnostics, "proposer_blocked"}))
    output_payload: dict[str, JsonValue] = {
        "model_run_id": model_run_id,
        "model_run_status": model_run_status.value,
        "observations": [item.model_dump(mode="json") for item in observations],
    }
    if abstention_reason is not None:
        output_payload["abstention_reason"] = abstention_reason
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=ordinal,
        stage_id="mention_proposal",
        stage_version="hybrid_mention_proposal_v1",
        producer_id=producer_id,
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration={"type_hints": list(PROPOSER_CONTEXTUAL_KINDS)},
        input_payload={"source_text": source_text},
        output_payload=output_payload,
        status=status,
        diagnostics=trace_diagnostics,
    )


def _publish_preview(
    *,
    archive: HybridMentionArchive,
    representation_id: str,
    paragraph_node_id: str,
    manifest: ContextManifest,
    card_digest: str,
    extraction_task_ids: list[str],
    model_run_ids: list[str],
    traces: list[ExtractionStageTrace],
    terminal_status: HybridPreviewStatus,
    diagnostics: list[str],
    observations: tuple[MentionObservation, ...] = (),
    candidates: tuple[MentionCandidate, ...] = (),
    decisions: tuple[MentionBoundaryDecision, ...] = (),
    interpretations: tuple[MentionInterpretation, ...] = (),
) -> HybridMentionPreviewResult:
    preview = build_hybrid_extraction_preview(
        representation_id=representation_id,
        paragraph_node_id=paragraph_node_id,
        context_manifest_id=manifest.id,
        ontology_card_sha256=card_digest,
        observations=observations,
        candidates=candidates,
        boundary_decisions=decisions,
        interpretations=tuple(
            sorted(
                interpretations,
                key=lambda item: (
                    _observation_source_key(candidates, item.candidate_id),
                    item.id,
                ),
            )
        ),
        extraction_task_ids=tuple(sorted(set(extraction_task_ids))),
        model_run_ids=tuple(sorted(set(model_run_ids))),
        traces=tuple(
            sorted(traces, key=lambda item: (item.source_segment_id, item.ordinal, item.id))
        ),
        terminal_status=terminal_status,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    payload = canonical_hybrid_extraction_preview_bytes(preview)
    digest = hybrid_extraction_preview_sha256(preview)
    archive.put_hybrid_extraction_preview(preview, payload, digest)
    return HybridMentionPreviewResult(
        preview=preview,
        sha256=digest,
        archive_path=f"extraction/previews/{preview.id}.json",
    )


def _trace_run_id(source_segment_id: str, *model_run_ids: str) -> str:
    payload = "\x1f".join((source_segment_id, *model_run_ids))
    return f"hpr_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def _observation_key(item: MentionObservation) -> tuple[str, int, int, str, str]:
    return item.source_segment_id, item.start, item.end, item.text, item.id


def _observation_source_key(
    candidates: tuple[MentionCandidate, ...], candidate_id: str
) -> tuple[str, int, int, str, str]:
    candidate = next(item for item in candidates if item.id == candidate_id)
    return (
        candidate.source_segment_id,
        candidate.start,
        candidate.end,
        candidate.text,
        candidate.id,
    )
