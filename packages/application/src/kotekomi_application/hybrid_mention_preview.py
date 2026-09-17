"""HP-1 orchestration over authoritative context and fallible model Ports."""

from __future__ import annotations

import hashlib
import json
import re
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
    SourceSegment,
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
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
    HYBRID_MENTION_BOUNDARY_ADJUDICATION_SCHEMA_ID,
    MAX_BOUNDARY_ADJUDICATION_CANDIDATES,
    BoundaryCandidateJudgmentBatch,
    MentionBoundaryAdjudication,
    MentionBoundaryAdjudicationJudgment,
    MentionBoundaryAdjudicationLineRejection,
    MentionBoundaryCandidateStatus,
    build_mention_boundary_adjudication,
    effective_mention_candidate_ids,
    unresolved_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HYBRID_MENTION_BOUNDARY_POLICY_ID,
    HYBRID_MENTION_PREVIEW_POLICY_ID,
    HYBRID_MENTION_PROPOSAL_SCHEMA_ID,
    PROPOSER_CONTEXTUAL_KINDS,
    HybridExtractionPreview,
    HybridModelOutputArchive,
    HybridPreviewStatus,
    MentionBoundaryDecision,
    MentionCandidate,
    MentionInterpretation,
    MentionInterpretationDraft,
    MentionObservation,
    PreviewStore,
    build_hybrid_extraction_preview,
    canonical_hybrid_extraction_preview_bytes,
    canonical_mention_proposal_input_bytes,
    fuse_mention_observations,
    hybrid_extraction_preview_sha256,
    hybrid_source_segment_id,
    map_occurrence_selections_to_observations,
    observation_from_proposal,
    reconcile_mention_boundaries,
    resolve_mention_interpretation,
    run_recorded_mention_proposer,
)
from kotekomi_application.mention_proposer import (
    MentionProposal,
    MentionProposalInput,
    MentionProposer,
)
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    ExecutionSetting,
    HybridMentionBoundaryAdjudicationTaskSchemaRegistry,
    HybridMentionInterpretationTaskSchemaRegistry,
    HybridMentionProposalTaskSchemaRegistry,
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


_REFERENCE_MARKER = re.compile(
    r"\b(?:he|him|his|she|her|hers|it|its|they|them|their|theirs|"
    r"the\s+(?:administration|agency|company|court|department|firm|government|institute|organization))"
    r"(?:['’]s)?\b",
    re.IGNORECASE,
)
_PERSON_REFERENCE_MARKERS = frozenset({"he", "him", "his", "she", "her", "hers"})
_PLURAL_REFERENCE_MARKERS = frozenset({"they", "them", "their", "theirs"})
_NAMED_SYMBOL_TOKEN = re.compile(r"(?<!\w)[A-Za-z][A-Za-z0-9]*(?!\w)")
_EXACT_NAMED_SYMBOL_BOUNDARY_RULE_ID = "exact_named_symbol_boundary_v1"
_EXACT_POSSESSOR_BOUNDARY_RULE_ID = "exact_possessor_boundary_v1"
_DETERMINISTIC_BOUNDARY_RULE_IDS = (
    _EXACT_NAMED_SYMBOL_BOUNDARY_RULE_ID,
    _EXACT_POSSESSOR_BOUNDARY_RULE_ID,
)


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


@dataclass(frozen=True)
class _InterpretationExecution:
    representative_candidate_id: str
    extraction_task_id: str
    model_run_id: str
    trace_id: str
    draft: MentionInterpretationDraft | None
    status: ExtractionStageStatus
    output_payload: dict[str, JsonValue]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class _BoundaryAdjudicationResult:
    adjudications: tuple[MentionBoundaryAdjudication, ...]
    traces: tuple[ExtractionStageTrace, ...]
    extraction_task_ids: tuple[str, ...]
    model_run_ids: tuple[str, ...]
    parent_trace_by_candidate: dict[str, str]
    next_ordinal_by_segment: dict[str, int]
    diagnostics: tuple[str, ...]


def run_hybrid_mention_preview(
    *,
    command: HybridMentionPreviewCommand,
    ledger: HybridMentionLedger,
    archive: HybridMentionArchive,
    proposer: MentionProposer,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    proposal_prompt_bytes: bytes,
    boundary_adjudication_prompt_bytes: bytes,
    interpretation_prompt_bytes: bytes,
    ontology_card_bytes: bytes,
    proposal_schema_registry: TaskSchemaRegistry | None = None,
    boundary_adjudication_schema_registry: TaskSchemaRegistry | None = None,
    interpretation_schema_registry: TaskSchemaRegistry | None = None,
) -> HybridMentionPreviewResult:
    """Run HP-1 and publish one immutable terminal preview."""
    if (
        not proposal_prompt_bytes
        or not boundary_adjudication_prompt_bytes
        or not interpretation_prompt_bytes
        or not ontology_card_bytes
    ):
        raise ValueError(
            "Hybrid mention preview requires pinned proposal, adjudication, interpretation, "
            "and ontology bytes."
        )
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
    proposal_registry = proposal_schema_registry or HybridMentionProposalTaskSchemaRegistry()
    boundary_registry = (
        boundary_adjudication_schema_registry
        or HybridMentionBoundaryAdjudicationTaskSchemaRegistry()
    )
    interpretation_registry = (
        interpretation_schema_registry or HybridMentionInterpretationTaskSchemaRegistry()
    )
    proposal_schema = proposal_registry.resolve(HYBRID_MENTION_PROPOSAL_SCHEMA_ID)
    boundary_schema = boundary_registry.resolve(HYBRID_MENTION_BOUNDARY_ADJUDICATION_SCHEMA_ID)
    interpretation_schema = interpretation_registry.resolve("hybrid_mention_interpretation_text_v2")
    unit = create_analysis_unit_from_retrieval_selection(
        RetrievalSelectionAnalysisUnitInput(
            representation_id=command.representation_id,
            focus_node_ids=(command.paragraph_node_id,),
            policy_id=HYBRID_MENTION_PREVIEW_POLICY_ID,
            task_type="hybrid_mention_preview",
        ),
        ledger,
    )
    proposal_planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=command.model_profile,
            prompt_id="hybrid_mention_occurrence_selection_v2",
            prompt_bytes=proposal_prompt_bytes,
            schema_id=proposal_schema.schema_id,
            schema_bytes=proposal_schema.canonical_schema_bytes,
            renderer_version="hybrid_mention_occurrence_selection_context_v2",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V2,
        ),
        ledger,
        tokenizer,
    )
    proposal_manifest = proposal_planning.manifest
    if proposal_manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Hybrid mention proposal ContextManifest is not ready: "
            f"{proposal_manifest.blocked_reason or proposal_manifest.status.value}"
        )
    verify_context_manifest(
        proposal_manifest.id,
        ledger,
        tokenizer,
        proposal_prompt_bytes,
        proposal_schema.canonical_schema_bytes,
    )
    interpretation_planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=command.model_profile,
            prompt_id="hybrid_mention_interpretation_task_v2",
            prompt_bytes=interpretation_prompt_bytes,
            schema_id=interpretation_schema.schema_id,
            schema_bytes=interpretation_schema.canonical_schema_bytes,
            renderer_version="hybrid_mention_interpretation_context_v2",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V2,
        ),
        ledger,
        tokenizer,
    )
    interpretation_manifest = interpretation_planning.manifest
    if interpretation_manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Hybrid mention interpretation ContextManifest is not ready: "
            f"{interpretation_manifest.blocked_reason or interpretation_manifest.status.value}"
        )
    verify_context_manifest(
        interpretation_manifest.id,
        ledger,
        tokenizer,
        interpretation_prompt_bytes,
        interpretation_schema.canonical_schema_bytes,
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
        "id": proposal_manifest.id,
        "manifest_digest": proposal_manifest.manifest_digest,
        "representation_id": proposal_manifest.representation_id,
        "source_segment_ids": cast(JsonValue, segment_ids),
    }
    proposer_input = MentionProposalInput(segments, PROPOSER_CONTEXTUAL_KINDS)
    gliner_visible_input = canonical_mention_proposal_input_bytes(proposer_input)
    gliner = run_recorded_mention_proposer(
        representation_id=command.representation_id,
        context_manifest_id=proposal_manifest.id,
        context_manifest_digest=proposal_manifest.manifest_digest,
        context_manifest_payload=common_manifest_payload,
        proposal_input=proposer_input,
        proposer=proposer,
        ledger=ledger,
        archive=archive,
    )
    qwen_proposal_input = _mention_selection_task_input(segments)
    qwen_visible_input = proposal_manifest.rendered_input + b"\n\n[task]\n" + qwen_proposal_input
    qwen = run_bounded_extraction(
        BoundedExtractionInput(
            source_id=source.id,
            document_id=document.id,
            representation_id=command.representation_id,
            context_manifest_id=proposal_manifest.id,
            prompt_bytes=proposal_prompt_bytes,
            execution_spec=_execution_spec(
                proposal_manifest,
                model_runtime,
                command.generation_parameters,
                proposal_schema,
                qwen_proposal_input,
            ),
            validator_version="hybrid_mention_occurrence_selection_validator_v1",
            task_type="hybrid_mention_proposal",
            task_local_input=qwen_proposal_input,
        ),
        ledger,
        archive,
        model_runtime,
        model_run_id_factory,
        tokenizer,
        proposal_registry,
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
    gliner_valid = gliner.batch is not None and gliner.model_run.status is ModelRunStatus.SUCCEEDED
    qwen_valid = qwen.model_run.status is ModelRunStatus.ABSTAINED or (
        qwen.model_run.status is ModelRunStatus.SUCCEEDED
        and qwen.mention_occurrence_selections is not None
        and (
            bool(qwen.mention_occurrence_selections.selections)
            or not qwen.mention_occurrence_selections.rejections
        )
    )
    proposer_failures: dict[str, str] = {}
    if not gliner_valid:
        proposer_failures["gliner"] = f"gliner_proposer_failed:{gliner.model_run.status.value}"
    if not qwen_valid:
        qwen_failure = (
            "output_contract"
            if qwen.model_run.status is ModelRunStatus.SUCCEEDED
            else qwen.model_run.status.value
        )
        proposer_failures["qwen2.5"] = f"qwen_proposer_failed:{qwen_failure}"
    diagnostics.extend(proposer_failures.values())
    proposal_line_rejections = (
        qwen.mention_occurrence_selections.rejections
        if qwen.mention_occurrence_selections is not None
        else ()
    )
    diagnostics.extend(
        f"qwen_proposal_line_rejected:{item.line_number}:{item.code}"
        for item in proposal_line_rejections
    )
    if not gliner_valid and not qwen_valid:
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
                        model_visible_input=gliner_visible_input,
                        raw_output_sha256=gliner.model_run.output_digest,
                        status=ExtractionStageStatus.FAILED,
                        diagnostics=(proposer_failures["gliner"],),
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
                        model_visible_input=qwen_visible_input,
                        raw_output_sha256=qwen.model_run.output_digest,
                        status=ExtractionStageStatus.FAILED,
                        diagnostics=(proposer_failures["qwen2.5"],),
                    ),
                )
            )
        return _publish_preview(
            archive=archive,
            representation_id=command.representation_id,
            paragraph_node_id=node.id,
            manifest=proposal_manifest,
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
    segment_by_label = {item.label: item for item in segments}
    if gliner_valid:
        assert gliner.batch is not None
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
                    f"invalid_observation:gliner:{gliner.model_run.id}:{index}:"
                    f"{type(error).__name__}"
                )
                invalid_observations.append(diagnostic)
                source_segment_id = segment_ids.get(proposal.source_segment_label)
                if source_segment_id is not None:
                    invalid_by_producer_segment.setdefault(
                        ("gliner", source_segment_id), []
                    ).append(diagnostic)
    if qwen.mention_occurrence_selections is not None:
        for index, selection in enumerate(qwen.mention_occurrence_selections.selections):
            try:
                mapped = map_occurrence_selections_to_observations(
                    selections=(selection,),
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
                source_segment_id = segment_ids.get(selection.source_segment_label)
                if source_segment_id is not None:
                    invalid_by_producer_segment.setdefault(
                        ("qwen2.5", source_segment_id), []
                    ).append(diagnostic)
    diagnostics.extend(invalid_observations)
    deterministic_observations, deterministic_traces = _reference_marker_observations(
        segments=segments,
        segment_ids=segment_ids,
        trace_runs=trace_runs,
    )
    for observation in deterministic_observations:
        if observation.id not in seen_observation_ids:
            seen_observation_ids.add(observation.id)
            observations.append(observation)
    traces.extend(deterministic_traces)
    named_symbol_observations, named_symbol_traces = _named_symbol_observations(
        segments=segments,
        segment_ids=segment_ids,
        trace_runs=trace_runs,
    )
    for observation in named_symbol_observations:
        if observation.id not in seen_observation_ids:
            seen_observation_ids.add(observation.id)
            observations.append(observation)
    traces.extend(named_symbol_traces)
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
                    model_visible_input=gliner_visible_input,
                    raw_output_sha256=gliner.model_run.output_digest,
                    status=(
                        ExtractionStageStatus.COMPLETED
                        if gliner_valid
                        else ExtractionStageStatus.FAILED
                    ),
                    observations=gliner_observations,
                    diagnostics=tuple(
                        sorted(
                            (
                                *invalid_by_producer_segment.get(("gliner", source_segment_id), []),
                                *((proposer_failures["gliner"],) if not gliner_valid else ()),
                            )
                        )
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
                    model_visible_input=qwen_visible_input,
                    raw_output_sha256=qwen.model_run.output_digest,
                    status=(
                        ExtractionStageStatus.COMPLETED
                        if qwen_valid
                        else ExtractionStageStatus.FAILED
                    ),
                    observations=qwen_observations,
                    diagnostics=tuple(
                        sorted(
                            (
                                *invalid_by_producer_segment.get(
                                    ("qwen2.5", source_segment_id), []
                                ),
                                *((proposer_failures["qwen2.5"],) if not qwen_valid else ()),
                            )
                        )
                    ),
                    abstention_reason=qwen.model_run.abstention_reason,
                    rejected_lines=tuple(
                        {
                            "line_number": item.line_number,
                            "line": item.line,
                            "code": item.code,
                        }
                        for item in proposal_line_rejections
                    ),
                ),
            )
        )
    candidates = fuse_mention_observations(
        source_segments=source_text_by_id,
        observations=ordered_observations,
    )
    decisions, _ = reconcile_mention_boundaries(
        source_segments=source_text_by_id,
        observations=ordered_observations,
        candidates=candidates,
    )
    reconciliation_trace_by_segment: dict[str, str] = {}
    for segment in segments:
        segment_id = segment_ids[segment.label]
        trace = build_extraction_stage_trace(
            trace_run_id=trace_runs[segment_id],
            ordinal=4,
            stage_id="mention_boundary_reconciliation",
            stage_version=HYBRID_MENTION_BOUNDARY_POLICY_ID,
            producer_id="kotekomi_application",
            source_segment_id=segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            parent_trace_ids=tuple(
                sorted(item.id for item in traces if item.source_segment_id == segment_id)
            ),
            execution_record_ids=tuple(sorted(model_run_ids)),
            configuration={"policy_id": HYBRID_MENTION_BOUNDARY_POLICY_ID},
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
    ambiguous_decisions = tuple(item for item in decisions if item.status.value == "ambiguous")
    observations_by_id = {item.id: item for item in ordered_observations}
    boundary_manifest: ContextManifest | None = None
    boundary_manifest_diagnostic: str | None = None
    if ambiguous_decisions:
        boundary_planning = build_context_manifest(
            ContextManifestInput(
                analysis_unit=unit,
                model_profile=command.model_profile,
                prompt_id="hybrid_mention_boundary_adjudication_v2",
                prompt_bytes=boundary_adjudication_prompt_bytes,
                schema_id=boundary_schema.schema_id,
                schema_bytes=boundary_schema.canonical_schema_bytes,
                renderer_version="hybrid_mention_boundary_adjudication_context_v2",
                evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
                source_segment_policy_id=PARAGRAPH_SEGMENT_V2,
            ),
            ledger,
            tokenizer,
        )
        if boundary_planning.manifest.status is ContextManifestStatus.READY:
            verify_context_manifest(
                boundary_planning.manifest.id,
                ledger,
                tokenizer,
                boundary_adjudication_prompt_bytes,
                boundary_schema.canonical_schema_bytes,
            )
            boundary_manifest = boundary_planning.manifest
        else:
            boundary_blocked_reason = (
                boundary_planning.manifest.blocked_reason or boundary_planning.manifest.status.value
            )
            boundary_manifest_diagnostic = f"boundary_context_not_ready:{boundary_blocked_reason}"
    boundary_result = _run_boundary_adjudications(
        decisions=ambiguous_decisions,
        candidates=candidates,
        observations_by_id=observations_by_id,
        source_text_by_id=source_text_by_id,
        source_label_by_id=source_label_by_id,
        reconciliation_trace_by_segment=reconciliation_trace_by_segment,
        trace_runs=trace_runs,
        manifest=boundary_manifest,
        manifest_diagnostic=boundary_manifest_diagnostic,
        prompt_bytes=boundary_adjudication_prompt_bytes,
        schema=boundary_schema,
        schema_registry=boundary_registry,
        source_id=source.id,
        document_id=document.id,
        representation_id=command.representation_id,
        generation_parameters=command.generation_parameters,
        ledger=ledger,
        archive=archive,
        model_runtime=model_runtime,
        model_run_id_factory=model_run_id_factory,
        tokenizer=tokenizer,
    )
    adjudications = boundary_result.adjudications
    traces.extend(boundary_result.traces)
    extraction_task_ids.extend(boundary_result.extraction_task_ids)
    model_run_ids.extend(boundary_result.model_run_ids)
    diagnostics.extend(boundary_result.diagnostics)
    effective_candidate_id_set = set(effective_mention_candidate_ids(decisions, adjudications))
    selected_candidates = tuple(
        item for item in candidates if item.id in effective_candidate_id_set
    )
    interpretations: list[MentionInterpretation] = []
    failed_interpretations = 0
    next_ordinal = boundary_result.next_ordinal_by_segment
    interpretation_executions: dict[tuple[str, str], _InterpretationExecution] = {}
    for candidate in selected_candidates:
        if _candidate_has_reference_marker(candidate, observations_by_id):
            continue
        reuse_key = (candidate.source_segment_id, candidate.text)
        reused = interpretation_executions.get(reuse_key)
        if reused is not None:
            ordinal = next_ordinal[candidate.source_segment_id]
            next_ordinal[candidate.source_segment_id] += 1
            trace_diagnostics = (
                ()
                if reused.status is ExtractionStageStatus.COMPLETED
                else tuple(sorted({*reused.diagnostics, "interpretation_reused_failure"}))
            )
            output_payload = {
                **reused.output_payload,
                "reused_from_candidate_id": reused.representative_candidate_id,
                "reused_from_trace_id": reused.trace_id,
            }
            trace = build_extraction_stage_trace(
                trace_run_id=trace_runs[candidate.source_segment_id],
                ordinal=ordinal,
                stage_id="mention_interpretation_reuse",
                stage_version="hybrid_mention_interpretation_reuse_v1",
                producer_id="kotekomi_application",
                source_segment_id=candidate.source_segment_id,
                source_text_sha256=candidate.source_text_sha256,
                parent_trace_ids=(reused.trace_id,),
                input_record_ids=tuple(sorted((candidate.id, reused.representative_candidate_id))),
                execution_record_ids=(reused.extraction_task_id, reused.model_run_id),
                configuration={
                    "ontology_card_sha256": card_digest,
                    "reuse_policy_id": "same_segment_exact_text_v1",
                },
                input_payload={
                    "candidate_id": candidate.id,
                    "candidate_source_label": source_label_by_id[candidate.source_segment_id],
                    "candidate_text": candidate.text,
                },
                output_payload=output_payload,
                status=reused.status,
                diagnostics=trace_diagnostics,
            )
            traces.append(trace)
            if reused.status is ExtractionStageStatus.COMPLETED:
                assert reused.draft is not None
                interpretations.append(
                    resolve_mention_interpretation(
                        draft=reused.draft,
                        candidate_labels={"c1": candidate},
                        source_segment_ids=segment_ids,
                        model_run_id=reused.model_run_id,
                        trace_id=trace.id,
                    )
                )
            else:
                failed_interpretations += 1
                diagnostics.append(
                    f"interpretation_reused_failure:{candidate.id}:{reused.model_run_id}"
                )
            continue
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
                context_manifest_id=interpretation_manifest.id,
                prompt_bytes=interpretation_prompt_bytes,
                execution_spec=_execution_spec(
                    interpretation_manifest,
                    model_runtime,
                    command.generation_parameters,
                    interpretation_schema,
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
            interpretation_registry,
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
            parent_trace_ids=(
                boundary_result.parent_trace_by_candidate.get(
                    candidate.id,
                    reconciliation_trace_by_segment[candidate.source_segment_id],
                ),
            ),
            input_record_ids=(candidate.id,),
            execution_record_ids=(outcome.extraction_task.id, outcome.model_run.id),
            configuration={"ontology_card_sha256": card_digest},
            input_payload={
                "candidate_label": "c1",
                "candidate_source_label": source_label_by_id[candidate.source_segment_id],
                "candidate_text": candidate.text,
                "model_visible_input": (
                    interpretation_manifest.rendered_input + b"\n\n[task]\n" + local_input
                ).decode("utf-8"),
            },
            output_payload={
                **output_payload,
                "raw_output_sha256": outcome.model_run.output_digest,
            },
            status=status,
            diagnostics=trace_diagnostics,
        )
        traces.append(trace)
        interpretation_executions[reuse_key] = _InterpretationExecution(
            representative_candidate_id=candidate.id,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            trace_id=trace.id,
            draft=draft,
            status=status,
            output_payload=output_payload,
            diagnostics=trace_diagnostics,
        )
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
    unresolved_boundary_ids = unresolved_mention_candidate_ids(decisions, adjudications)
    diagnostics.extend(
        f"boundary_adjudication_unresolved:{candidate_id}"
        for candidate_id in unresolved_boundary_ids
    )
    terminal_status = (
        HybridPreviewStatus.PARTIAL
        if (
            proposer_failures
            or proposal_line_rejections
            or boundary_result.diagnostics
            or failed_interpretations
            or unresolved_boundary_ids
        )
        else HybridPreviewStatus.COMPLETE
    )
    return _publish_preview(
        archive=archive,
        representation_id=command.representation_id,
        paragraph_node_id=node.id,
        manifest=proposal_manifest,
        card_digest=card_digest,
        observations=ordered_observations,
        candidates=candidates,
        decisions=decisions,
        adjudications=adjudications,
        interpretations=tuple(interpretations),
        extraction_task_ids=extraction_task_ids,
        model_run_ids=model_run_ids,
        traces=traces,
        terminal_status=terminal_status,
        diagnostics=diagnostics,
    )


def _run_boundary_adjudications(
    *,
    decisions: tuple[MentionBoundaryDecision, ...],
    candidates: tuple[MentionCandidate, ...],
    observations_by_id: dict[str, MentionObservation],
    source_text_by_id: dict[str, str],
    source_label_by_id: dict[str, str],
    reconciliation_trace_by_segment: dict[str, str],
    trace_runs: dict[str, str],
    manifest: ContextManifest | None,
    manifest_diagnostic: str | None,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    schema_registry: TaskSchemaRegistry,
    source_id: str,
    document_id: str,
    representation_id: str,
    generation_parameters: tuple[ExecutionSetting, ...],
    ledger: HybridMentionLedger,
    archive: HybridMentionArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
) -> _BoundaryAdjudicationResult:
    """Run one bounded completeness task for each ambiguous overlap component."""
    candidate_by_id = {item.id: item for item in candidates}
    adjudications: list[MentionBoundaryAdjudication] = []
    traces: list[ExtractionStageTrace] = []
    extraction_task_ids: list[str] = []
    model_run_ids: list[str] = []
    parent_trace_by_candidate: dict[str, str] = {}
    diagnostics: list[str] = []
    next_ordinal = {source_segment_id: 5 for source_segment_id in source_text_by_id}
    for decision in decisions:
        component_candidates = tuple(
            sorted(
                (candidate_by_id[item] for item in decision.candidate_ids),
                key=lambda item: (item.start, item.end, item.id),
            )
        )
        source_text = source_text_by_id[decision.source_segment_id]
        deterministic_complete_candidates = _deterministic_complete_boundary_candidates(
            candidates=component_candidates,
            observations_by_id=observations_by_id,
            source_text=source_text,
        )
        deterministic_complete_ids: set[str] = {
            item.id for item in deterministic_complete_candidates
        }
        semantic_candidates = tuple(
            item for item in component_candidates if item.id not in deterministic_complete_ids
        )
        if not semantic_candidates:
            semantic_candidates = component_candidates
            deterministic_complete_candidates = ()
            deterministic_complete_ids = set()
        deterministic_complete_payload = cast(
            JsonValue,
            sorted(deterministic_complete_ids),
        )
        source_digest = hashlib.sha256(source_text.encode()).hexdigest()
        ordinal = next_ordinal[decision.source_segment_id]
        next_ordinal[decision.source_segment_id] += 1
        task_input, candidate_labels = _boundary_adjudication_task_input(
            candidates=semantic_candidates,
            source_segment_label=source_label_by_id[decision.source_segment_id],
            source_text=source_text,
        )
        blocked_reason: str | None = None
        if len(semantic_candidates) > MAX_BOUNDARY_ADJUDICATION_CANDIDATES:
            blocked_reason = "boundary_candidate_limit_exceeded"
        elif manifest is None:
            blocked_reason = manifest_diagnostic or "boundary_context_not_ready"
        if blocked_reason is not None:
            trace = build_extraction_stage_trace(
                trace_run_id=trace_runs[decision.source_segment_id],
                ordinal=ordinal,
                stage_id="mention_boundary_adjudication",
                stage_version=HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
                producer_id="kotekomi_application",
                source_segment_id=decision.source_segment_id,
                source_text_sha256=source_digest,
                parent_trace_ids=(reconciliation_trace_by_segment[decision.source_segment_id],),
                input_record_ids=tuple(sorted((decision.id, *decision.candidate_ids))),
                configuration={
                    "deterministic_completion_rule_ids": cast(
                        JsonValue, list(_DETERMINISTIC_BOUNDARY_RULE_IDS)
                    ),
                    "max_candidates": MAX_BOUNDARY_ADJUDICATION_CANDIDATES,
                    "policy_id": HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
                },
                input_payload={
                    "candidate_labels": {
                        label: candidate.id for label, candidate in candidate_labels.items()
                    },
                    "deterministic_complete_candidate_ids": deterministic_complete_payload,
                    "model_visible_input": task_input.decode(),
                    "source_text": source_text,
                },
                output_payload={"judgments": [], "rejected_lines": []},
                status=ExtractionStageStatus.BLOCKED,
                diagnostics=(blocked_reason,),
            )
            traces.append(trace)
            diagnostics.append(f"{blocked_reason}:{decision.id}")
            continue
        if manifest is None:
            raise AssertionError("A ready boundary task requires its ContextManifest.")
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=source_id,
                document_id=document_id,
                representation_id=representation_id,
                context_manifest_id=manifest.id,
                prompt_bytes=prompt_bytes,
                execution_spec=_execution_spec(
                    manifest,
                    model_runtime,
                    generation_parameters,
                    schema,
                    task_input,
                ),
                validator_version="hybrid_mention_boundary_adjudication_validator_v2",
                task_type="hybrid_mention_boundary_adjudication",
                input_candidate_ids=tuple(item.id for item in semantic_candidates),
                task_local_input=task_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            schema_registry,
        )
        extraction_task_ids.append(outcome.extraction_task.id)
        model_run_ids.append(outcome.model_run.id)
        mapped, rejected_lines, trace_diagnostics = _map_boundary_judgments(
            outcome.boundary_candidate_judgments,
            candidate_labels,
            deterministic_complete_candidates=deterministic_complete_candidates,
        )
        if outcome.boundary_candidate_judgments is None:
            trace_status = ExtractionStageStatus.FAILED
            trace_diagnostics = tuple(
                sorted({*trace_diagnostics, "boundary_adjudication_output_unavailable"})
            )
        elif trace_diagnostics:
            trace_status = ExtractionStageStatus.REJECTED
        else:
            trace_status = ExtractionStageStatus.COMPLETED
        trace = build_extraction_stage_trace(
            trace_run_id=trace_runs[decision.source_segment_id],
            ordinal=ordinal,
            stage_id="mention_boundary_adjudication",
            stage_version=HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
            producer_id="kotekomi_application",
            source_segment_id=decision.source_segment_id,
            source_text_sha256=source_digest,
            parent_trace_ids=(reconciliation_trace_by_segment[decision.source_segment_id],),
            input_record_ids=tuple(sorted((decision.id, *decision.candidate_ids))),
            execution_record_ids=tuple(sorted((outcome.extraction_task.id, outcome.model_run.id))),
            configuration={
                "deterministic_completion_rule_ids": cast(
                    JsonValue, list(_DETERMINISTIC_BOUNDARY_RULE_IDS)
                ),
                "max_candidates": MAX_BOUNDARY_ADJUDICATION_CANDIDATES,
                "policy_id": HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
                "semantic_producer_id": "qwen2.5",
            },
            input_payload={
                "candidate_labels": {
                    label: candidate.id for label, candidate in candidate_labels.items()
                },
                "deterministic_complete_candidate_ids": deterministic_complete_payload,
                "model_visible_input": (
                    manifest.rendered_input + b"\n\n[task]\n" + task_input
                ).decode(),
                "source_text": source_text,
            },
            output_payload={
                "judgments": [item.model_dump(mode="json") for item in mapped],
                "deterministic_complete_candidate_ids": deterministic_complete_payload,
                "model_run_status": outcome.model_run.status.value,
                "raw_output_sha256": outcome.model_run.output_digest,
                "rejected_lines": [item.model_dump(mode="json") for item in rejected_lines],
            },
            status=trace_status,
            diagnostics=trace_diagnostics,
        )
        traces.append(trace)
        adjudication = build_mention_boundary_adjudication(
            boundary_decision_id=decision.id,
            source_segment_id=decision.source_segment_id,
            source_text_sha256=source_digest,
            judgments=mapped,
            rejected_lines=rejected_lines,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            trace_id=trace.id,
        )
        adjudications.append(adjudication)
        parent_trace_by_candidate.update(
            {candidate.id: trace.id for candidate in component_candidates}
        )
        diagnostics.extend(f"{item}:{decision.id}" for item in trace_diagnostics)
    return _BoundaryAdjudicationResult(
        adjudications=tuple(adjudications),
        traces=tuple(traces),
        extraction_task_ids=tuple(extraction_task_ids),
        model_run_ids=tuple(model_run_ids),
        parent_trace_by_candidate=parent_trace_by_candidate,
        next_ordinal_by_segment=next_ordinal,
        diagnostics=tuple(diagnostics),
    )


def _boundary_adjudication_task_input(
    *,
    candidates: tuple[MentionCandidate, ...],
    source_segment_label: str,
    source_text: str,
) -> tuple[bytes, dict[str, MentionCandidate]]:
    labels = {f"c{index}": item for index, item in enumerate(candidates, start=1)}
    lines = [
        "task: judge_mention_boundary_completeness",
        f"source_segment: {source_segment_label}",
        f"source_text_json: {json.dumps(source_text, ensure_ascii=False)}",
        "candidate_catalog:",
    ]
    lines.extend(
        f"{label} | {json.dumps(candidate.text, ensure_ascii=False)}"
        for label, candidate in labels.items()
    )
    lines.append("required_output_prefixes:")
    lines.extend(f"{label} |" for label in labels)
    return "\n".join(lines).encode(), labels


def _map_boundary_judgments(
    batch: BoundaryCandidateJudgmentBatch | None,
    candidate_labels: dict[str, MentionCandidate],
    *,
    deterministic_complete_candidates: tuple[MentionCandidate, ...] = (),
) -> tuple[
    tuple[MentionBoundaryAdjudicationJudgment, ...],
    tuple[MentionBoundaryAdjudicationLineRejection, ...],
    tuple[str, ...],
]:
    by_candidate: dict[str, MentionBoundaryCandidateStatus] = {
        item.id: MentionBoundaryCandidateStatus.COMPLETE
        for item in deterministic_complete_candidates
    }
    rejected: list[MentionBoundaryAdjudicationLineRejection] = []
    diagnostics: list[str] = []
    if batch is not None:
        rejected.extend(
            MentionBoundaryAdjudicationLineRejection(
                line_number=item.line_number,
                line=item.line,
                code=item.code,
            )
            for item in batch.rejections
        )
        diagnostics.extend(
            f"boundary_line_rejected:{item.line_number}:{item.code}" for item in batch.rejections
        )
        for item in batch.judgments:
            candidate = candidate_labels.get(item.candidate_label)
            if candidate is None:
                rejected.append(
                    MentionBoundaryAdjudicationLineRejection(
                        line_number=item.line_number,
                        line=item.line,
                        code="unknown_candidate_label",
                    )
                )
                diagnostics.append(
                    f"boundary_line_rejected:{item.line_number}:unknown_candidate_label"
                )
                continue
            by_candidate[candidate.id] = MentionBoundaryCandidateStatus(item.judgment.value)
    judgments: list[MentionBoundaryAdjudicationJudgment] = []
    all_candidates = tuple(
        sorted(
            (*deterministic_complete_candidates, *candidate_labels.values()),
            key=lambda item: (item.start, item.end, item.id),
        )
    )
    label_by_candidate_id = {candidate.id: label for label, candidate in candidate_labels.items()}
    for candidate in all_candidates:
        status = by_candidate.get(candidate.id, MentionBoundaryCandidateStatus.UNRESOLVED)
        if status is MentionBoundaryCandidateStatus.UNRESOLVED:
            diagnostics.append(f"boundary_candidate_omitted:{label_by_candidate_id[candidate.id]}")
        judgments.append(
            MentionBoundaryAdjudicationJudgment(candidate_id=candidate.id, status=status)
        )
    return (
        tuple(judgments),
        tuple(sorted(rejected, key=lambda item: item.line_number)),
        tuple(sorted(set(diagnostics))),
    )


def _exact_possessor_boundary_candidates(
    *,
    candidates: tuple[MentionCandidate, ...],
    source_text: str,
) -> tuple[MentionCandidate, ...]:
    """Select candidates whose exact end is proven by a following possessive clitic."""
    selected: list[MentionCandidate] = []
    for candidate in candidates:
        suffix = source_text[candidate.end : candidate.end + 2]
        if suffix not in {"'s", "’s"}:
            continue
        if any(
            other.id != candidate.id
            and other.start == candidate.start
            and other.end > candidate.end + len(suffix)
            for other in candidates
        ):
            selected.append(candidate)
    return tuple(sorted(selected, key=lambda item: (item.start, item.end, item.id)))


def _deterministic_complete_boundary_candidates(
    *,
    candidates: tuple[MentionCandidate, ...],
    observations_by_id: dict[str, MentionObservation],
    source_text: str,
) -> tuple[MentionCandidate, ...]:
    """Preserve boundaries established directly from authoritative characters."""
    selected = {
        candidate.id: candidate
        for candidate in _exact_possessor_boundary_candidates(
            candidates=candidates,
            source_text=source_text,
        )
    }
    for candidate in candidates:
        if any(
            observations_by_id[observation_id].producer_id == "kotekomi_named_symbol_v1"
            for observation_id in candidate.observation_ids
        ):
            selected[candidate.id] = candidate
    return tuple(sorted(selected.values(), key=lambda item: (item.start, item.end, item.id)))


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


def _mention_selection_task_input(segments: tuple[SourceSegment, ...]) -> bytes:
    """Render only KoteKomi-owned occurrence choices for mention proposal."""
    lines = [
        "task: select_mention_occurrence_ranges",
        "source_occurrence_catalog:",
    ]
    for segment in segments:
        lines.append(f"source_segment: {segment.label}")
        lines.extend(
            f"{item.occurrence_id} | {item.text}" for item in source_occurrences(segment.exact_text)
        )
    return "\n".join(lines).encode()


def _candidate_has_reference_marker(
    candidate: MentionCandidate,
    observations_by_id: dict[str, MentionObservation],
) -> bool:
    return any(
        observations_by_id[observation_id].producer_id == "kotekomi_reference_marker_v1"
        for observation_id in candidate.observation_ids
    )


def _reference_marker_observations(
    *,
    segments: tuple[SourceSegment, ...],
    segment_ids: dict[str, str],
    trace_runs: dict[str, str],
) -> tuple[tuple[MentionObservation, ...], tuple[ExtractionStageTrace, ...]]:
    """Discover bounded reference expressions without asking a named-entity proposer."""
    observations: list[MentionObservation] = []
    traces: list[ExtractionStageTrace] = []
    for segment in segments:
        segment_id = segment_ids[segment.label]
        proposals = tuple(
            MentionProposal(
                source_segment_label=segment.label,
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                type_hints=_reference_marker_type_hints(match.group(0)),
            )
            for match in _REFERENCE_MARKER.finditer(segment.exact_text)
        )
        trace = build_extraction_stage_trace(
            trace_run_id=trace_runs[segment_id],
            ordinal=2,
            stage_id="semantic_reference_discovery",
            stage_version="exact_reference_markers_v1",
            producer_id="kotekomi_application",
            source_segment_id=segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            configuration={"policy_id": "exact_reference_markers_v1"},
            input_payload={"source_text": segment.exact_text},
            output_payload={
                "markers": [
                    {
                        "end": item.end,
                        "start": item.start,
                        "text": item.text,
                        "type_hints": list(item.type_hints),
                    }
                    for item in proposals
                ]
            },
            status=ExtractionStageStatus.COMPLETED,
        )
        traces.append(trace)
        observations.extend(
            observation_from_proposal(
                proposal=proposal,
                source_segment_id=segment_id,
                producer_id="kotekomi_reference_marker_v1",
                execution_record_id=trace.id,
            )
            for proposal in proposals
        )
    return tuple(sorted(observations, key=_observation_key)), tuple(traces)


def _reference_marker_type_hints(text: str) -> tuple[str, ...]:
    marker = " ".join(text.casefold().split())
    if marker.endswith(("'s", "’s")):
        marker = marker[:-2]
    if marker in _PERSON_REFERENCE_MARKERS:
        return ("person",)
    if marker in _PLURAL_REFERENCE_MARKERS:
        return ("government", "organization", "person")
    nominal = marker.removeprefix("the ")
    nominal_hints = {
        "administration": ("government",),
        "agency": ("government", "organization"),
        "company": ("organization",),
        "court": ("government", "organization"),
        "department": ("government", "organization"),
        "firm": ("organization",),
        "government": ("government",),
        "institute": ("organization",),
        "organization": ("organization",),
    }
    return nominal_hints.get(
        nominal,
        (
            "event",
            "government",
            "initiative",
            "organization",
            "policy",
            "product",
            "project",
            "publication",
        ),
    )


def _named_symbol_observations(
    *,
    segments: tuple[SourceSegment, ...],
    segment_ids: dict[str, str],
    trace_runs: dict[str, str],
) -> tuple[tuple[MentionObservation, ...], tuple[ExtractionStageTrace, ...]]:
    """Propose exact acronym-like names without assigning semantic meaning."""
    observations: list[MentionObservation] = []
    traces: list[ExtractionStageTrace] = []
    for segment in segments:
        segment_id = segment_ids[segment.label]
        proposals = tuple(
            MentionProposal(
                source_segment_label=segment.label,
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                type_hints=PROPOSER_CONTEXTUAL_KINDS,
            )
            for match in _NAMED_SYMBOL_TOKEN.finditer(segment.exact_text)
            if sum(character.isupper() for character in match.group(0)) >= 2
        )
        trace = build_extraction_stage_trace(
            trace_run_id=trace_runs[segment_id],
            ordinal=3,
            stage_id="named_symbol_discovery",
            stage_version="exact_named_symbol_v1",
            producer_id="kotekomi_application",
            source_segment_id=segment_id,
            source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
            configuration={
                "policy_id": "exact_named_symbol_v1",
                "minimum_uppercase_character_count": 2,
            },
            input_payload={"source_text": segment.exact_text},
            output_payload={
                "symbols": [
                    {
                        "end": item.end,
                        "start": item.start,
                        "text": item.text,
                    }
                    for item in proposals
                ]
            },
            status=ExtractionStageStatus.COMPLETED,
        )
        traces.append(trace)
        observations.extend(
            observation_from_proposal(
                proposal=proposal,
                source_segment_id=segment_id,
                producer_id="kotekomi_named_symbol_v1",
                execution_record_id=trace.id,
            )
            for proposal in proposals
        )
    return tuple(sorted(observations, key=_observation_key)), tuple(traces)


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
    model_visible_input: bytes,
    raw_output_sha256: str | None,
    status: ExtractionStageStatus,
    observations: tuple[MentionObservation, ...] = (),
    diagnostics: tuple[str, ...] = (),
    abstention_reason: str | None = None,
    rejected_lines: tuple[dict[str, JsonValue], ...] = (),
) -> ExtractionStageTrace:
    trace_diagnostics = diagnostics
    if status is not ExtractionStageStatus.COMPLETED:
        trace_diagnostics = tuple(sorted({*diagnostics, "proposer_failed"}))
    output_payload: dict[str, JsonValue] = {
        "model_run_id": model_run_id,
        "model_run_status": model_run_status.value,
        "observations": [item.model_dump(mode="json") for item in observations],
        "raw_output_sha256": raw_output_sha256,
        "rejected_lines": list(rejected_lines),
    }
    if abstention_reason is not None:
        output_payload["abstention_reason"] = abstention_reason
    occurrence_selection = producer_id == "qwen2.5"
    return build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=ordinal,
        stage_id="mention_proposal",
        stage_version=(
            "hybrid_mention_occurrence_selection_v2"
            if occurrence_selection
            else "hybrid_specialist_mention_proposal_v1"
        ),
        producer_id=producer_id,
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration=(
            {
                "selection_unit": "source_occurrence_range",
                "occurrence_id_scope": "source_segment_local",
                "model_assigns_ontology_kind": False,
                "model_copies_source_text": False,
            }
            if occurrence_selection
            else {"type_hints": list(PROPOSER_CONTEXTUAL_KINDS)}
        ),
        input_payload={
            "model_visible_input": model_visible_input.decode("utf-8"),
            "source_text": source_text,
        },
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
    adjudications: tuple[MentionBoundaryAdjudication, ...] = (),
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
        boundary_adjudications=tuple(
            sorted(
                adjudications,
                key=lambda item: (item.source_segment_id, item.boundary_decision_id, item.id),
            )
        ),
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
