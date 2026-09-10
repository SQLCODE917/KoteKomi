"""HP-6 bounded governed-event semantics and independent source-support orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

from kotekomi_domain import (
    HYBRID_EVENT_SEMANTICS_V4,
    AssignmentOrigin,
    DocumentNode,
    DocumentRepresentationBundle,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ModelRunStatus,
    SemanticArgumentTargetKind,
    TemporalRelation,
    canonical_evidence_target_digest,
    hybrid_event_semantics_profile_sha256,
)
from kotekomi_domain.hybrid_event_ontology import EventFrameDefinition, FrameRoleDefinition
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V3,
    AnalysisUnit,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ContextTokenizer,
    SourceCopyView,
    SourceSegment,
    SourceSegmentAnalysisUnitInput,
    build_context_manifest,
    create_analysis_unit_from_source_segment,
    derive_source_copy_view,
    paragraph_source_segments,
    verify_context_manifest,
)
from kotekomi_application.evidence_targets import (
    validate_evidence_target_record,
    verify_evidence_target,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceDecision,
    ReferenceSpan,
    ReferenceStatus,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_event_semantics import (
    HYBRID_EVENT_FRAME_FIT_PROMPT_ID,
    HYBRID_EVENT_FRAME_FIT_SCHEMA_ID,
    HYBRID_EVENT_FRAME_SELECTION_PROMPT_ID,
    HYBRID_EVENT_FRAME_SELECTION_SCHEMA_ID,
    HYBRID_EVENT_PRESENTATION_PROMPT_ID,
    HYBRID_EVENT_PRESENTATION_SCHEMA_ID,
    HYBRID_EVENT_ROLE_SELECTION_PROMPT_ID,
    HYBRID_EVENT_ROLE_SELECTION_SCHEMA_ID,
    HYBRID_EVENT_SEMANTICS_POLICY_ID,
    HYBRID_SEMANTIC_SUPPORT_PROMPT_ID,
    HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID,
    EventArgumentAssignmentDraft,
    EventArgumentTargetDraft,
    EventAttributionKind,
    EventSemanticDraft,
    EventSubjectDraft,
    HybridEventSemanticsPreview,
    HybridEventSemanticsStatus,
    SemanticCoverageGap,
    SemanticCoverageGapCode,
    SemanticQualifierDraft,
    SemanticStatement,
    SemanticStatementKind,
    SemanticSupportJudgment,
    SupportOutcome,
    build_event_argument_assignment_draft,
    build_event_argument_target_draft,
    build_event_semantic_draft,
    build_event_subject_draft,
    build_hybrid_event_semantics_preview,
    build_semantic_coverage_gap,
    build_semantic_qualifier_draft,
    build_semantic_statement,
    build_semantic_support_judgment,
    canonical_hybrid_event_semantics_preview_bytes,
    hybrid_event_semantics_preview_from_bytes,
    hybrid_event_semantics_preview_sha256,
    resolve_unique_source_literal,
)
from kotekomi_application.hybrid_event_semantics_model_output import (
    EventFrameFitDecision,
    EventFrameSelection,
    EventPresentationSelection,
    EventSemanticArgumentProposal,
    EventSemanticLineRejection,
    EventSemanticProposal,
    EventSemanticQualifierProposal,
    EventSemanticRoleTargetProposal,
    SemanticSupportModelJudgment,
    event_frame_fit_schema_bytes,
    event_frame_selection_schema_bytes,
    event_presentation_schema_bytes,
    event_semantic_role_target_schema_bytes,
    parse_event_frame_fit_output,
    parse_event_frame_selection_output,
    parse_event_presentation_output,
    parse_event_semantic_role_target_output,
    parse_semantic_support_output,
    semantic_support_schema_bytes,
)
from kotekomi_application.hybrid_event_trigger_preview import (
    HybridEventTriggerArchive,
    HybridEventTriggerLedger,
    load_hybrid_event_trigger_preview,
    source_occurrences,
)
from kotekomi_application.hybrid_event_triggers import (
    EventTriggerDraft,
    HybridEventTriggerPreview,
    HybridEventTriggerStatus,
    canonical_hybrid_event_trigger_preview_bytes,
)
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    effective_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    ContextualKind,
    HybridExtractionPreview,
    MentionCandidate,
    MentionInterpretation,
    Referentiality,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)
from kotekomi_application.semantic_proposition import (
    CompleteProposition,
    NaturalLanguageInferenceInput,
    NaturalLanguageInferencePort,
    NliObservation,
    PropositionDecision,
    PropositionDisposition,
    PropositionKind,
    build_complete_proposition,
    build_nli_observation,
    build_proposition_decision,
)
from kotekomi_application.source_occurrences import SourceOccurrence
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    ExecutionSetting,
    ModelExecutionSpec,
    ModelRunIdFactory,
    ModelTaskRuntime,
    PinnedTaskSchema,
    StagedExtractionLedger,
    TaskSchemaRegistry,
    run_bounded_extraction,
)

HYBRID_EVENT_SEMANTICS_EVIDENCE_VALIDATOR = "hybrid_event_semantics_evidence_v1"
HYBRID_EVENT_SEMANTICS_SOURCE_ALIGNMENT = "exact_then_whitespace_equivalent_unique_v1"
HYBRID_EVENT_NLI_ENTAILMENT_THRESHOLD = 0.5


class HybridEventSemanticsLedger(HybridEventTriggerLedger, StagedExtractionLedger, Protocol):
    pass


class HybridEventSemanticsArchive(HybridEventTriggerArchive, Protocol):
    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object: ...

    def put_hybrid_event_semantics_preview(
        self,
        preview: HybridEventSemanticsPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_event_semantics_preview(self, preview_id: str) -> bytes: ...


@dataclass(frozen=True)
class HybridEventSemanticsCommand:
    parent_preview_id: str
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]


@dataclass(frozen=True)
class HybridEventSemanticsResult:
    preview: HybridEventSemanticsPreview
    sha256: str
    archive_path: str


@dataclass(frozen=True)
class _SegmentContext:
    segment: SourceSegment
    segment_id: str
    support_target: EvidenceTarget
    support_attempt: EvidenceValidationAttempt


@dataclass(frozen=True)
class _SourceContext:
    parent: HybridEventTriggerPreview
    bundle: DocumentRepresentationBundle
    mentions: HybridExtractionPreview
    references: HybridReferencePreview
    triggers: dict[str, EventTriggerDraft]
    candidates: dict[str, MentionCandidate]
    segments: dict[str, _SegmentContext]
    source_id: str
    document_id: str


@dataclass(frozen=True)
class _LocalInputs:
    candidates: dict[str, MentionCandidate]
    reference_metadata: dict[str, tuple[ReferenceDecision, tuple[ReferenceSpan, ...]]]
    source_text: str
    source_copy: SourceCopyView
    occurrences: dict[str, SourceOccurrence]


@dataclass(frozen=True)
class _ConstructedEvent:
    event: EventSemanticDraft | None
    targets: tuple[EventArgumentTargetDraft, ...]
    assignments: tuple[EventArgumentAssignmentDraft, ...]
    qualifiers: tuple[SemanticQualifierDraft, ...]
    gaps: tuple[SemanticCoverageGap, ...]
    statements: tuple[SemanticStatement, ...]
    proposition: CompleteProposition
    evidence_targets: tuple[EvidenceTarget, ...]
    evidence_attempts: tuple[EvidenceValidationAttempt, ...]


class _SemanticSchemaRegistry:
    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id == HYBRID_EVENT_FRAME_SELECTION_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                event_frame_selection_schema_bytes(),
                schema_id,
                parse_event_frame_selection_output,
            )
        if schema_id == HYBRID_EVENT_FRAME_FIT_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                event_frame_fit_schema_bytes(),
                schema_id,
                parse_event_frame_fit_output,
            )
        if schema_id == HYBRID_EVENT_ROLE_SELECTION_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                event_semantic_role_target_schema_bytes(),
                schema_id,
                parse_event_semantic_role_target_output,
            )
        if schema_id == HYBRID_EVENT_PRESENTATION_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                event_presentation_schema_bytes(),
                schema_id,
                parse_event_presentation_output,
            )
        if schema_id == HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                semantic_support_schema_bytes(),
                schema_id,
                parse_semantic_support_output,
            )
        raise ValueError(f"Unsupported HP-6 task schema: {schema_id}")


def run_hybrid_event_semantics_preview(
    *,
    command: HybridEventSemanticsCommand,
    ledger: HybridEventSemanticsLedger,
    archive: HybridEventSemanticsArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    frame_selection_prompt_bytes: bytes,
    frame_fit_prompt_bytes: bytes,
    role_selection_prompt_bytes: bytes,
    presentation_prompt_bytes: bytes,
    support_prompt_bytes: bytes,
    nli_runtime: NaturalLanguageInferencePort,
) -> HybridEventSemanticsResult:
    """Build governed semantic drafts and independently verify every statement."""
    context = _load_context(command.parent_preview_id, ledger, archive)
    registry: TaskSchemaRegistry = _SemanticSchemaRegistry()
    frame_selection_schema = registry.resolve(HYBRID_EVENT_FRAME_SELECTION_SCHEMA_ID)
    frame_fit_schema = registry.resolve(HYBRID_EVENT_FRAME_FIT_SCHEMA_ID)
    role_selection_schema = registry.resolve(HYBRID_EVENT_ROLE_SELECTION_SCHEMA_ID)
    presentation_schema = registry.resolve(HYBRID_EVENT_PRESENTATION_SCHEMA_ID)
    support_schema = registry.resolve(HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID)
    parent_sha256 = hashlib.sha256(
        canonical_hybrid_event_trigger_preview_bytes(context.parent)
    ).hexdigest()
    common = _preview_common(
        context,
        parent_sha256,
        frame_selection_prompt_bytes,
        frame_selection_schema,
        frame_fit_prompt_bytes,
        frame_fit_schema,
        role_selection_prompt_bytes,
        role_selection_schema,
        presentation_prompt_bytes,
        presentation_schema,
        support_prompt_bytes,
        support_schema,
    )
    if context.parent.terminal_status is HybridEventTriggerStatus.BLOCKED:
        preview = build_hybrid_event_semantics_preview(
            **common,
            terminal_status=HybridEventSemanticsStatus.BLOCKED,
            diagnostics=("hp4_status:blocked",),
        )
        return _result(preview)

    events: list[EventSemanticDraft] = []
    targets: list[EventArgumentTargetDraft] = []
    assignments: list[EventArgumentAssignmentDraft] = []
    qualifiers: list[SemanticQualifierDraft] = []
    gaps: list[SemanticCoverageGap] = []
    statements: list[SemanticStatement] = []
    judgments: list[SemanticSupportJudgment] = []
    propositions: list[CompleteProposition] = []
    nli_observations: list[NliObservation] = []
    proposition_decisions: list[PropositionDecision] = []
    evidence_targets: dict[str, EvidenceTarget] = {}
    evidence_attempts: dict[str, EvidenceValidationAttempt] = {}
    task_ids: list[str] = []
    run_ids: list[str] = []
    traces: list[ExtractionStageTrace] = []
    diagnostics: list[str] = []
    manifest_cache: dict[
        str,
        tuple[
            ContextManifest,
            ContextManifest,
            ContextManifest,
            ContextManifest,
            ContextManifest,
        ],
    ] = {}

    subjects = tuple(
        build_event_subject_draft(parent_preview_id=context.parent.id, trigger_id=item.id)
        for item in context.parent.triggers
    )
    for subject in subjects:
        trigger = context.triggers[subject.trigger_id]
        segment = context.segments[trigger.source_segment_id]
        manifests = manifest_cache.get(segment.segment_id)
        if manifests is None:
            unit = create_analysis_unit_from_source_segment(
                SourceSegmentAnalysisUnitInput(
                    representation_id=context.parent.representation_id,
                    paragraph_node_id=context.parent.paragraph_node_id,
                    source_segment_label=segment.segment.label,
                    policy_id=HYBRID_EVENT_SEMANTICS_POLICY_ID,
                    task_type="hybrid_event_semantics_preview",
                ),
                ledger,
            )
            manifests = (
                _build_manifest(
                    unit=unit,
                    profile=command.model_profile,
                    prompt_id=HYBRID_EVENT_FRAME_SELECTION_PROMPT_ID,
                    prompt_bytes=frame_selection_prompt_bytes,
                    schema=frame_selection_schema,
                    ledger=ledger,
                    tokenizer=tokenizer,
                ),
                _build_manifest(
                    unit=unit,
                    profile=command.model_profile,
                    prompt_id=HYBRID_EVENT_FRAME_FIT_PROMPT_ID,
                    prompt_bytes=frame_fit_prompt_bytes,
                    schema=frame_fit_schema,
                    ledger=ledger,
                    tokenizer=tokenizer,
                ),
                _build_manifest(
                    unit=unit,
                    profile=command.model_profile,
                    prompt_id=HYBRID_EVENT_ROLE_SELECTION_PROMPT_ID,
                    prompt_bytes=role_selection_prompt_bytes,
                    schema=role_selection_schema,
                    ledger=ledger,
                    tokenizer=tokenizer,
                ),
                _build_manifest(
                    unit=unit,
                    profile=command.model_profile,
                    prompt_id=HYBRID_EVENT_PRESENTATION_PROMPT_ID,
                    prompt_bytes=presentation_prompt_bytes,
                    schema=presentation_schema,
                    ledger=ledger,
                    tokenizer=tokenizer,
                ),
                _build_manifest(
                    unit=unit,
                    profile=command.model_profile,
                    prompt_id=HYBRID_SEMANTIC_SUPPORT_PROMPT_ID,
                    prompt_bytes=support_prompt_bytes,
                    schema=support_schema,
                    ledger=ledger,
                    tokenizer=tokenizer,
                ),
            )
            manifest_cache[segment.segment_id] = manifests
        (
            frame_manifest,
            frame_fit_manifest,
            role_manifest,
            presentation_manifest,
            support_manifest,
        ) = manifests
        local_inputs = _local_inputs(context, segment)
        frame_input = _frame_selection_task_input(
            trigger=trigger,
            segment=segment,
        )
        frame_outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=context.source_id,
                document_id=context.document_id,
                representation_id=context.parent.representation_id,
                context_manifest_id=frame_manifest.id,
                prompt_bytes=frame_selection_prompt_bytes,
                execution_spec=_execution_spec(
                    frame_manifest,
                    model_runtime,
                    command.generation_parameters,
                    frame_selection_schema,
                    frame_input,
                ),
                validator_version="hybrid_event_frame_selection_validator_v1",
                task_type="hybrid_event_frame_selection",
                input_candidate_ids=(subject.id,),
                task_local_input=frame_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        task_ids.append(frame_outcome.extraction_task.id)
        run_ids.append(frame_outcome.model_run.id)
        frame_selection = frame_outcome.event_frame_selection
        frame_trace = _frame_selection_trace(
            subject=subject,
            trigger=trigger,
            segment=segment,
            task_input=frame_input,
            prompt_bytes=frame_selection_prompt_bytes,
            schema=frame_selection_schema,
            task_id=frame_outcome.extraction_task.id,
            model_run_id=frame_outcome.model_run.id,
            model_status=frame_outcome.model_run.status,
            raw_output_sha256=frame_outcome.model_run.output_digest,
            selection=frame_selection,
        )
        traces.append(frame_trace)
        if (
            frame_selection is None
            or frame_outcome.model_run.status is not ModelRunStatus.SUCCEEDED
        ):
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.INVALID_REQUIRED_ENVELOPE,
                    field_value=frame_outcome.model_run.status.value,
                    detail="The frame-selection task did not return a valid decision.",
                )
            )
            diagnostics.append(
                f"frame_selection_failed:{subject.id}:{frame_outcome.model_run.status.value}"
            )
            continue
        if frame_selection.frame_id is None:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.UNMAPPED_FRAME,
                    field_value=trigger.event_type_label,
                    detail="No governed frame accurately represented the source event.",
                )
            )
            diagnostics.append(f"unmapped_frame:{subject.id}")
            continue
        try:
            frame_definition = _frame_definition(frame_selection.frame_id)
        except ValueError as error:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.UNMAPPED_FRAME,
                    field_value=frame_selection.frame_id,
                    detail="The selected frame is not in the governed event profile.",
                )
            )
            diagnostics.append(f"frame_selection_mapping_failed:{subject.id}:{error}")
            continue
        frame_fit_input = _frame_fit_task_input(
            trigger=trigger,
            segment=segment,
            frame=frame_definition,
        )
        frame_fit_outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=context.source_id,
                document_id=context.document_id,
                representation_id=context.parent.representation_id,
                context_manifest_id=frame_fit_manifest.id,
                prompt_bytes=frame_fit_prompt_bytes,
                execution_spec=_execution_spec(
                    frame_fit_manifest,
                    model_runtime,
                    command.generation_parameters,
                    frame_fit_schema,
                    frame_fit_input,
                ),
                validator_version="hybrid_event_frame_fit_validator_v1",
                task_type="hybrid_event_frame_fit",
                input_candidate_ids=(subject.id,),
                task_local_input=frame_fit_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        task_ids.append(frame_fit_outcome.extraction_task.id)
        run_ids.append(frame_fit_outcome.model_run.id)
        frame_fit = frame_fit_outcome.event_frame_fit_decision
        frame_fit_trace = _frame_fit_trace(
            subject=subject,
            trigger=trigger,
            segment=segment,
            frame=frame_definition,
            task_input=frame_fit_input,
            prompt_bytes=frame_fit_prompt_bytes,
            schema=frame_fit_schema,
            task_id=frame_fit_outcome.extraction_task.id,
            model_run_id=frame_fit_outcome.model_run.id,
            model_status=frame_fit_outcome.model_run.status,
            raw_output_sha256=frame_fit_outcome.model_run.output_digest,
            decision=frame_fit,
            parent_trace_id=frame_trace.id,
        )
        traces.append(frame_fit_trace)
        if frame_fit is None or frame_fit_outcome.model_run.status is not ModelRunStatus.SUCCEEDED:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.INVALID_REQUIRED_ENVELOPE,
                    field_value=frame_fit_outcome.model_run.status.value,
                    detail="The frame-fit task did not return a valid decision.",
                )
            )
            diagnostics.append(
                f"frame_fit_failed:{subject.id}:{frame_fit_outcome.model_run.status.value}"
            )
            continue
        if not frame_fit.fits:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.UNMAPPED_FRAME,
                    field_value=frame_definition.id,
                    detail="The selected governed frame failed its independent fit challenge.",
                )
            )
            diagnostics.append(f"frame_fit_rejected:{subject.id}:{frame_definition.id}")
            continue
        semantic_traces = [frame_trace, frame_fit_trace]
        selected_arguments: dict[str, EventSemanticArgumentProposal] = {}
        assignment_origins: dict[str, AssignmentOrigin] = {}
        ordered_roles = tuple(item for item in frame_definition.roles if item.required) + tuple(
            item for item in frame_definition.roles if not item.required
        )
        for role in ordered_roles:
            completed_argument: EventSemanticArgumentProposal | None = None
            rejected_target: str | None = None
            role_outcome = None
            parent_trace_id = frame_fit_trace.id
            for attempt_ordinal in range(2):
                role_input = _role_selection_task_input(
                    trigger=trigger,
                    segment=segment,
                    local_inputs=local_inputs,
                    frame=frame_definition,
                    role=role,
                    selected_arguments=selected_arguments,
                    rejected_target=rejected_target,
                )
                role_outcome = run_bounded_extraction(
                    BoundedExtractionInput(
                        source_id=context.source_id,
                        document_id=context.document_id,
                        representation_id=context.parent.representation_id,
                        context_manifest_id=role_manifest.id,
                        prompt_bytes=role_selection_prompt_bytes,
                        execution_spec=_execution_spec(
                            role_manifest,
                            model_runtime,
                            command.generation_parameters,
                            role_selection_schema,
                            role_input,
                        ),
                        validator_version="hybrid_event_role_selection_validator_v1",
                        task_type="hybrid_event_role_selection",
                        input_candidate_ids=(subject.id,),
                        task_local_input=role_input,
                    ),
                    ledger,
                    archive,
                    model_runtime,
                    model_run_id_factory,
                    tokenizer,
                    registry,
                )
                task_ids.append(role_outcome.extraction_task.id)
                run_ids.append(role_outcome.model_run.id)
                role_proposal = role_outcome.event_semantic_role_target_proposal
                role_trace = _role_selection_trace(
                    subject=subject,
                    frame=frame_definition,
                    role=role,
                    trigger=trigger,
                    segment=segment,
                    task_input=role_input,
                    prompt_bytes=role_selection_prompt_bytes,
                    schema=role_selection_schema,
                    task_id=role_outcome.extraction_task.id,
                    model_run_id=role_outcome.model_run.id,
                    model_status=role_outcome.model_run.status,
                    raw_output_sha256=role_outcome.model_run.output_digest,
                    proposal=role_proposal,
                    parent_trace_id=parent_trace_id,
                )
                traces.append(role_trace)
                semantic_traces.append(role_trace)
                parent_trace_id = role_trace.id
                if role_proposal is None:
                    if (
                        attempt_ordinal == 0
                        and role_outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
                    ):
                        rejected_target = "invalid_model_output"
                        continue
                    break
                if role_proposal.target_selector is None:
                    break
                try:
                    completed_argument = _completed_role_argument(
                        role_proposal,
                        role,
                        context,
                        segment,
                        local_inputs,
                        ledger,
                    )
                except ValueError as error:
                    if attempt_ordinal == 0:
                        rejected_target = f"{error}:{role_proposal.target_selector}"
                        continue
                break
            assert role_outcome is not None
            if completed_argument is None:
                if role_outcome.model_run.status is not ModelRunStatus.SUCCEEDED or role.required:
                    diagnostics.append(
                        f"role_selection_unresolved:{subject.id}:{role.id}:"
                        f"{role_outcome.model_run.status.value}"
                    )
            else:
                selected_arguments[role.id] = completed_argument
                assignment_origins[role.id] = AssignmentOrigin.ROLE_SELECTION

        presentation_input = _event_presentation_task_input(
            trigger=trigger,
            segment=segment,
            local_inputs=local_inputs,
            frame=frame_definition,
            selected_arguments=selected_arguments,
        )
        presentation_outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=context.source_id,
                document_id=context.document_id,
                representation_id=context.parent.representation_id,
                context_manifest_id=presentation_manifest.id,
                prompt_bytes=presentation_prompt_bytes,
                execution_spec=_execution_spec(
                    presentation_manifest,
                    model_runtime,
                    command.generation_parameters,
                    presentation_schema,
                    presentation_input,
                ),
                validator_version="hybrid_event_presentation_validator_v1",
                task_type="hybrid_event_presentation",
                input_candidate_ids=(subject.id,),
                task_local_input=presentation_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        task_ids.append(presentation_outcome.extraction_task.id)
        run_ids.append(presentation_outcome.model_run.id)
        presentation = presentation_outcome.event_presentation_selection
        presentation_trace = _event_presentation_trace(
            subject=subject,
            frame=frame_definition,
            trigger=trigger,
            segment=segment,
            task_input=presentation_input,
            prompt_bytes=presentation_prompt_bytes,
            schema=presentation_schema,
            task_id=presentation_outcome.extraction_task.id,
            model_run_id=presentation_outcome.model_run.id,
            model_status=presentation_outcome.model_run.status,
            raw_output_sha256=presentation_outcome.model_run.output_digest,
            selection=presentation,
            rejections=presentation_outcome.event_presentation_line_rejections,
            parent_trace_ids=tuple(item.id for item in semantic_traces),
        )
        traces.append(presentation_trace)
        semantic_traces.append(presentation_trace)
        for rejection in presentation_outcome.event_presentation_line_rejections:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.INVALID_OPTIONAL_LINE,
                    field_value=f"line:{rejection.line_number}",
                    detail=f"{rejection.code}: {rejection.line}",
                )
            )
        if (
            presentation is None
            or presentation_outcome.model_run.status is not ModelRunStatus.SUCCEEDED
        ):
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.INVALID_REQUIRED_ENVELOPE,
                    field_value=presentation_outcome.model_run.status.value,
                    detail="The event-presentation task did not return a valid decision.",
                )
            )
            diagnostics.append(
                f"presentation_task_failed:{subject.id}:"
                f"{presentation_outcome.model_run.status.value}"
            )
            continue

        try:
            attribution_value = _resolve_model_selector(
                presentation.attribution_selector,
                local_inputs,
                allow_reserved=True,
            )
            resolved_qualifiers = tuple(
                EventSemanticQualifierProposal(
                    item.kind,
                    _resolve_source_selector(item.source_selector, local_inputs),
                    item.temporal_relation,
                )
                for item in presentation.qualifiers
            )
        except ValueError as error:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.INVALID_REQUIRED_ENVELOPE,
                    field_value=presentation.attribution_selector,
                    detail=f"Event presentation used an invalid source selector: {error}",
                )
            )
            diagnostics.append(f"presentation_mapping_failed:{subject.id}:{error}")
            continue

        proposal = EventSemanticProposal(
            frame_definition.id,
            presentation.polarity,
            presentation.modality,
            attribution_value,
            tuple(
                selected_arguments[item.id]
                for item in frame_definition.roles
                if item.id in selected_arguments
            ),
            resolved_qualifiers,
            f"{frame_selection.reason} {frame_fit.reason} {presentation.reason}",
        )
        try:
            constructed = _construct_event(
                context=context,
                subject=subject,
                trigger=trigger,
                segment=segment,
                local_inputs=local_inputs,
                proposal=proposal,
                assignment_origins=assignment_origins,
                task_id=frame_outcome.extraction_task.id,
                model_run_id=frame_outcome.model_run.id,
                selection_traces=tuple(semantic_traces),
                ledger=ledger,
            )
        except ValueError as error:
            diagnostics.append(f"semantic_construction_failed:{subject.id}:{error}")
            continue
        events.append(cast(EventSemanticDraft, constructed.event))
        targets.extend(constructed.targets)
        assignments.extend(constructed.assignments)
        qualifiers.extend(constructed.qualifiers)
        gaps.extend(constructed.gaps)
        statements.extend(constructed.statements)
        propositions.append(constructed.proposition)
        for target in constructed.evidence_targets:
            evidence_targets[target.id] = target
        for attempt in constructed.evidence_attempts:
            evidence_attempts[attempt.id] = attempt
        _persist_evidence(constructed, ledger)
        traces.append(
            _construction_trace(
                subject=subject,
                segment=segment,
                proposal=proposal,
                selection_traces=tuple(semantic_traces),
                constructed=constructed,
            )
        )

        complete_statement = next(
            item
            for item in constructed.statements
            if item.kind is SemanticStatementKind.COMPLETE_PROPOSITION
        )
        for statement in (complete_statement,):
            support_input = _support_task_input(
                segment.support_target.exact_text,
                statement,
            )
            support_outcome = run_bounded_extraction(
                BoundedExtractionInput(
                    source_id=context.source_id,
                    document_id=context.document_id,
                    representation_id=context.parent.representation_id,
                    context_manifest_id=support_manifest.id,
                    prompt_bytes=support_prompt_bytes,
                    execution_spec=_execution_spec(
                        support_manifest,
                        model_runtime,
                        command.generation_parameters,
                        support_schema,
                        support_input,
                    ),
                    validator_version="hybrid_semantic_support_validator_v1",
                    task_type="hybrid_semantic_source_support",
                    input_candidate_ids=(statement.id,),
                    task_local_input=support_input,
                ),
                ledger,
                archive,
                model_runtime,
                model_run_id_factory,
                tokenizer,
                registry,
            )
            task_ids.append(support_outcome.extraction_task.id)
            run_ids.append(support_outcome.model_run.id)
            parsed_support = support_outcome.semantic_support_judgment
            judgment = _support_judgment(
                statement,
                parsed_support,
                support_outcome.extraction_task.id,
                support_outcome.model_run.id,
                support_outcome.model_run.status,
            )
            if judgment is None:
                diagnostics.append(
                    f"support_task_failed:{statement.id}:{support_outcome.model_run.status.value}"
                )
            else:
                judgments.append(judgment)
            traces.append(
                _support_trace(
                    statement=statement,
                    segment=segment,
                    task_input=support_input,
                    prompt_bytes=support_prompt_bytes,
                    schema=support_schema,
                    task_id=support_outcome.extraction_task.id,
                    model_run_id=support_outcome.model_run.id,
                    model_status=support_outcome.model_run.status,
                    raw_output_sha256=support_outcome.model_run.output_digest,
                    judgment=judgment,
                )
            )
            if statement.kind is SemanticStatementKind.COMPLETE_PROPOSITION:
                proposition = constructed.proposition
                observation: NliObservation | None = None
                nli_error: str | None = None
                try:
                    execution = nli_runtime.classify(
                        NaturalLanguageInferenceInput(
                            premise=segment.support_target.exact_text,
                            hypothesis=proposition.text,
                        )
                    )
                    observation = build_nli_observation(
                        proposition_id=proposition.id,
                        premise=segment.support_target.exact_text,
                        hypothesis=proposition.text,
                        execution=execution,
                    )
                    nli_observations.append(observation)
                except (OSError, RuntimeError, ValueError) as error:
                    nli_error = str(error)
                    diagnostics.append(f"nli_task_failed:{proposition.id}:{type(error).__name__}")
                decision = build_proposition_decision(
                    proposition_id=proposition.id,
                    qwen_judgment_id=judgment.id if judgment is not None else None,
                    nli_observation=observation,
                    qwen_directly_supported=(
                        judgment.outcome is SupportOutcome.DIRECTLY_SUPPORTED
                        if judgment is not None
                        else None
                    ),
                    entailment_threshold=HYBRID_EVENT_NLI_ENTAILMENT_THRESHOLD,
                )
                proposition_decisions.append(decision)
                if decision.disposition is not PropositionDisposition.SUPPORTED:
                    assert decision.hold_reason is not None
                    diagnostics.append(
                        f"complete_proposition_held:{proposition.id}:{decision.hold_reason.value}"
                    )
                traces.append(
                    _nli_trace(
                        proposition=proposition,
                        premise=segment.support_target.exact_text,
                        source_segment_id=segment.segment_id,
                        observation=observation,
                        decision=decision,
                        error=nli_error,
                        parent_trace_id=traces[-1].id,
                    )
                )

    if context.parent.terminal_status is HybridEventTriggerStatus.PARTIAL:
        diagnostics.append("hp4_status:partial")
    status = HybridEventSemanticsStatus.COMPLETE
    if (
        len(events) != len(context.parent.triggers)
        or gaps
        or len(judgments) != len(propositions)
        or any(
            item.disposition is not PropositionDisposition.SUPPORTED
            for item in proposition_decisions
        )
        or context.parent.terminal_status is HybridEventTriggerStatus.PARTIAL
    ):
        status = HybridEventSemanticsStatus.PARTIAL
    preview = build_hybrid_event_semantics_preview(
        **common,
        semantic_events=tuple(sorted(events, key=lambda item: item.event_subject_id)),
        targets=tuple(
            sorted({item.id: item for item in targets}.values(), key=lambda item: item.id)
        ),
        assignments=tuple(sorted(assignments, key=lambda item: item.id)),
        qualifiers=tuple(sorted(qualifiers, key=lambda item: item.id)),
        gaps=tuple(sorted(gaps, key=lambda item: item.id)),
        statements=tuple(sorted(statements, key=lambda item: item.id)),
        judgments=tuple(sorted(judgments, key=lambda item: item.id)),
        propositions=tuple(sorted(propositions, key=lambda item: item.id)),
        nli_observations=tuple(sorted(nli_observations, key=lambda item: item.id)),
        proposition_decisions=tuple(sorted(proposition_decisions, key=lambda item: item.id)),
        evidence_target_ids=tuple(sorted(evidence_targets)),
        evidence_validation_attempt_ids=tuple(sorted(evidence_attempts)),
        extraction_task_ids=tuple(task_ids),
        model_run_ids=tuple(run_ids),
        traces=tuple(sorted(traces, key=lambda item: item.id)),
        terminal_status=status,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    return _result(preview)


def publish_hybrid_event_semantics_preview(
    result: HybridEventSemanticsResult,
    archive: HybridEventSemanticsArchive,
) -> None:
    payload = canonical_hybrid_event_semantics_preview_bytes(result.preview)
    if hashlib.sha256(payload).hexdigest() != result.sha256:
        raise ValueError("HP-6 result digest changed before Archive publication.")
    archive.put_hybrid_event_semantics_preview(result.preview, payload, result.sha256)


def load_hybrid_event_semantics_preview(
    preview_id: str,
    ledger: HybridEventSemanticsLedger,
    archive: HybridEventSemanticsArchive,
) -> HybridEventSemanticsPreview:
    """Reload canonical HP-6 evidence and replay every source selector."""
    payload = archive.read_hybrid_event_semantics_preview(preview_id)
    preview = hybrid_event_semantics_preview_from_bytes(payload)
    if (
        preview.id != preview_id
        or canonical_hybrid_event_semantics_preview_bytes(preview) != payload
    ):
        raise ValueError("HP-6 Preview identity or canonical encoding is invalid.")
    parent = load_hybrid_event_trigger_preview(preview.parent_preview_id, archive)
    if (
        hashlib.sha256(canonical_hybrid_event_trigger_preview_bytes(parent)).hexdigest()
        != preview.parent_preview_sha256
        or parent.representation_id != preview.representation_id
        or parent.paragraph_node_id != preview.paragraph_node_id
        or preview.ontology_profile_sha256 != hybrid_event_semantics_profile_sha256()
    ):
        raise ValueError(
            "HP-6 trigger parent or ontology lineage does not match pinned identities."
        )
    attempts = {
        item.evidence_target_id: item
        for attempt_id in preview.evidence_validation_attempt_ids
        if (item := ledger.get_evidence_validation_attempt(attempt_id)) is not None
    }
    for target_id in preview.evidence_target_ids:
        target = ledger.get_evidence_target(target_id)
        attempt = attempts.get(target_id)
        if target is None or attempt is None:
            raise ValueError("HP-6 evidence records are missing.")
        replay = verify_evidence_target(target, attempt, ledger)
        if not replay.valid:
            raise ValueError(f"HP-6 EvidenceTarget replay failed: {replay.error_message}")
    return preview


def _load_context(
    parent_id: str,
    ledger: HybridEventSemanticsLedger,
    archive: HybridEventSemanticsArchive,
) -> _SourceContext:
    parent = load_hybrid_event_trigger_preview(parent_id, archive)
    mentions = hybrid_extraction_preview_from_bytes(
        archive.read_hybrid_extraction_preview(parent.mention_preview_id)
    )
    reference_payload = archive.read_hybrid_reference_preview(parent.reference_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    if (
        references.id != parent.reference_preview_id
        or hashlib.sha256(reference_payload).hexdigest() != parent.reference_preview_sha256
        or canonical_hybrid_reference_preview_bytes(references) != reference_payload
    ):
        raise ValueError("HP-6 reference evidence does not match HP-4 lineage.")
    bundle = ledger.get_document_representation_bundle(parent.representation_id)
    if bundle is None:
        raise ValueError("HP-6 DocumentRepresentationBundle is missing.")
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-6 source Document is missing.")
    node = next((item for item in bundle.nodes if item.id == parent.paragraph_node_id), None)
    if node is None or node.node_type != "paragraph":
        raise ValueError("HP-6 paragraph node is missing or invalid.")
    text_view = next((item for item in bundle.text_views if item.id == node.text_view_id), None)
    if text_view is None:
        raise ValueError("HP-6 paragraph TextView is missing.")
    segments = paragraph_source_segments(
        text_view.text[node.start_char : node.end_char], PARAGRAPH_SEGMENT_V3
    )
    source_segments = {
        hybrid_source_segment_id(parent.representation_id, parent.paragraph_node_id, item): item
        for item in segments
    }
    segment_contexts: dict[str, _SegmentContext] = {}
    for segment_id, segment in source_segments.items():
        target, attempt = _build_segment_evidence(
            bundle=bundle,
            node=node,
            segment=segment,
            segment_id=segment_id,
            source_id=document.source_id,
            ledger=ledger,
        )
        segment_contexts[segment_id] = _SegmentContext(segment, segment_id, target, attempt)
    triggers = {item.id: item for item in parent.triggers}
    candidates = {item.id: item for item in mentions.candidates}
    if any(item.source_segment_id not in segment_contexts for item in parent.triggers):
        raise ValueError("HP-6 lacks support evidence for one event subject.")
    return _SourceContext(
        parent,
        bundle,
        mentions,
        references,
        triggers,
        candidates,
        segment_contexts,
        document.source_id,
        document.id,
    )


def _local_inputs(
    context: _SourceContext,
    segment: _SegmentContext,
) -> _LocalInputs:
    selected_candidate_ids = set(
        effective_mention_candidate_ids(
            context.mentions.boundary_decisions,
            context.mentions.boundary_adjudications,
        )
    )
    interpretations = {item.candidate_id: item for item in context.mentions.interpretations}
    decisions = {item.candidate_id: item for item in context.references.reference_decisions}
    candidates = {
        f"c{ordinal}": item
        for ordinal, item in enumerate(
            sorted(
                (
                    candidate
                    for candidate in context.candidates.values()
                    if candidate.source_segment_id == segment.segment_id
                    and candidate.id in selected_candidate_ids
                    and _candidate_is_role_eligible(
                        candidate,
                        interpretations,
                        decisions,
                    )
                ),
                key=lambda item: (item.start, item.end, item.id),
            ),
            start=1,
        )
    }
    spans = {
        item.id: item
        for item in (
            *(declaration.expanded_span for declaration in context.references.alias_declarations),
            *context.references.semantic_antecedent_spans,
        )
    }
    reference_metadata = {
        label: (
            decision,
            tuple(spans[item] for item in decision.antecedent_span_ids if item in spans),
        )
        for label, candidate in candidates.items()
        if (decision := decisions.get(candidate.id)) is not None
    }
    source_copy = derive_source_copy_view(segment.segment.exact_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy)}
    return _LocalInputs(
        candidates,
        reference_metadata,
        segment.segment.exact_text,
        source_copy,
        occurrences,
    )


def _candidate_is_role_eligible(
    candidate: MentionCandidate,
    interpretations: dict[str, MentionInterpretation],
    decisions: dict[str, ReferenceDecision],
) -> bool:
    interpretation = interpretations.get(candidate.id)
    if interpretation is None:
        return False
    referentiality = interpretation.referentiality
    if referentiality is Referentiality.SPECIFIC_ENTITY:
        return True
    decision = decisions.get(candidate.id)
    return (
        referentiality is Referentiality.ANAPHORIC
        and decision is not None
        and decision.status is ReferenceStatus.RESOLVED
    )


def _build_segment_evidence(
    *,
    bundle: DocumentRepresentationBundle,
    node: DocumentNode,
    segment: SourceSegment,
    segment_id: str,
    source_id: str,
    ledger: HybridEventSemanticsLedger,
) -> tuple[EvidenceTarget, EvidenceValidationAttempt]:
    text_view = next(item for item in bundle.text_views if item.id == node.text_view_id)
    start = node.start_char + segment.start_char
    end = node.start_char + segment.end_char
    created_at = datetime.now(UTC)
    target = EvidenceTarget(
        id=_id(
            "etg",
            bundle.representation.id,
            text_view.id,
            segment_id,
            str(start),
            str(end),
            segment.exact_text,
        ),
        source_id=source_id,
        document_id=bundle.representation.document_id,
        representation_id=bundle.representation.id,
        text_view_id=text_view.id,
        text_view_digest=text_view.content_digest,
        start_char=start,
        end_char=end,
        exact_text=segment.exact_text,
        normalization_policy=text_view.normalization_policy,
        prefix_text=text_view.text[max(0, start - 32) : start],
        suffix_text=text_view.text[end : min(len(text_view.text), end + 32)],
        node_ids=(node.id,),
        pdf_region_ids=node.source_region_ids,
        created_at=created_at,
    )
    existing = ledger.get_evidence_target(target.id)
    if existing is not None:
        if _without_time(existing) != _without_time(target):
            raise ValueError("HP-6 conflicts with an existing SourceSegment EvidenceTarget.")
        target = existing
    validate_evidence_target_record(target, ledger)
    attempt = EvidenceValidationAttempt(
        id=_id("eva", target.id, HYBRID_EVENT_SEMANTICS_EVIDENCE_VALIDATOR),
        evidence_target_id=target.id,
        target_digest=canonical_evidence_target_digest(target),
        validator_version=HYBRID_EVENT_SEMANTICS_EVIDENCE_VALIDATOR,
        status=EvidenceValidationAttemptStatus.SUCCEEDED,
        attempted_at=created_at,
    )
    existing_attempt = ledger.get_evidence_validation_attempt(attempt.id)
    if existing_attempt is not None:
        if _without_time(existing_attempt) != _without_time(attempt):
            raise ValueError("HP-6 conflicts with an existing evidence validation attempt.")
        attempt = existing_attempt
    return target, attempt


def _construct_event(
    *,
    context: _SourceContext,
    subject: EventSubjectDraft,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    proposal: EventSemanticProposal,
    assignment_origins: dict[str, AssignmentOrigin],
    task_id: str,
    model_run_id: str,
    selection_traces: tuple[ExtractionStageTrace, ...],
    ledger: HybridEventSemanticsLedger,
) -> _ConstructedEvent:
    frame_definition = _frame_definition(cast(str, proposal.frame_id))
    role_by_id = {item.id: item for item in frame_definition.roles}
    seen_roles: set[str] = set()
    seen_targets: set[tuple[SemanticArgumentTargetKind, str]] = set()
    target_records: dict[str, EventArgumentTargetDraft] = {}
    evidence_records: dict[str, tuple[EvidenceTarget, EvidenceValidationAttempt]] = {
        segment.support_target.id: (segment.support_target, segment.support_attempt)
    }
    assignments: list[EventArgumentAssignmentDraft] = []
    frame_selection_trace = selection_traces[0]
    parent_trace_ids = tuple(
        sorted(
            {
                *(item.id for item in selection_traces),
                trigger.trace_id,
            }
        )
    )
    for argument in proposal.arguments:
        role = role_by_id.get(argument.frame_role_id)
        if role is None:
            raise ValueError("unknown_frame_role")
        if argument.frame_role_id in seen_roles:
            raise ValueError("repeated_frame_role")
        target, evidence, attempt = _resolve_target(
            context=context,
            segment=segment,
            local_inputs=local_inputs,
            value=argument.target_value,
            allowed_target_kinds=role.allowed_target_kinds,
            ledger=ledger,
        )
        target_key = (target.kind, target.reference_id or target.text)
        if target_key in seen_targets:
            raise ValueError("repeated_argument_target")
        seen_roles.add(argument.frame_role_id)
        seen_targets.add(target_key)
        target_records[target.id] = target
        evidence_records[evidence.id] = (evidence, attempt)
        assignments.append(
            build_event_argument_assignment_draft(
                event_subject_id=subject.id,
                frame_id=frame_definition.id,
                target_id=target.id,
                frame_role_id=role.id,
                upper_role=role.upper_role,
                assignment_origin=assignment_origins[role.id],
                proposed_role_labels=(),
                support_evidence_target_id=segment.support_target.id,
                source_trace_ids=parent_trace_ids,
            )
        )

    gaps: list[SemanticCoverageGap] = []
    qualifier_records: list[SemanticQualifierDraft] = []
    for qualifier in proposal.qualifiers:
        try:
            target, evidence, attempt = _source_span_target(
                context, segment, qualifier.literal_text, ledger
            )
        except ValueError:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.UNSUPPORTED_QUALIFIER_PROPOSAL,
                    field_value=qualifier.literal_text,
                    detail="The qualifier does not resolve to one exact source span.",
                )
            )
            continue
        evidence_records[evidence.id] = (evidence, attempt)
        qualifier_records.append(
            build_semantic_qualifier_draft(
                event_subject_id=subject.id,
                kind=qualifier.kind,
                temporal_relation=qualifier.temporal_relation,
                source_segment_id=segment.segment_id,
                text=target.text,
                start=target.start,
                end=target.end,
                evidence_target_id=evidence.id,
                evidence_validation_attempt_id=attempt.id,
            )
        )

    attribution_target: EventArgumentTargetDraft | None = None
    attribution_kind = EventAttributionKind.SOURCE_NARRATOR
    if proposal.attribution_value == "unresolved":
        attribution_kind = EventAttributionKind.UNRESOLVED
        gaps.append(
            build_semantic_coverage_gap(
                event_subject_id=subject.id,
                code=SemanticCoverageGapCode.MISSING_GOVERNED_ATTRIBUTION,
                field_value="unresolved",
                detail="The event-presentation task could not resolve attribution.",
            )
        )
    elif proposal.attribution_value != "source_narrator":
        try:
            attribution_target, evidence, attempt = _resolve_target(
                context=context,
                segment=segment,
                local_inputs=local_inputs,
                value=proposal.attribution_value,
                allowed_target_kinds=tuple(SemanticArgumentTargetKind),
                ledger=ledger,
            )
        except ValueError:
            attribution_kind = EventAttributionKind.UNRESOLVED
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.MISSING_GOVERNED_ATTRIBUTION,
                    field_value=proposal.attribution_value,
                    detail="The selected attribution does not resolve to source evidence.",
                )
            )
        else:
            attribution_kind = EventAttributionKind(attribution_target.kind.value)
            target_records[attribution_target.id] = attribution_target
            evidence_records[evidence.id] = (evidence, attempt)

    for role in frame_definition.roles:
        if role.required and role.id not in seen_roles:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.MISSING_REQUIRED_ROLE,
                    field_value=role.id,
                    detail=f"Required frame role {role.id} has no source-backed target.",
                )
            )
        if not role.required and role.id not in seen_roles:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.MISSING_OPTIONAL_ROLE,
                    field_value=role.id,
                    detail=f"Optional frame role {role.id} has no source-backed target.",
                )
            )
    ordered_assignments = tuple(sorted(assignments, key=lambda item: item.id))
    ordered_qualifiers = tuple(sorted(qualifier_records, key=lambda item: item.id))
    event = build_event_semantic_draft(
        event_subject_id=subject.id,
        trigger_id=trigger.id,
        trigger_text=trigger.text,
        frame_id=frame_definition.id,
        proposed_event_label=trigger.event_type_label,
        argument_assignment_ids=tuple(item.id for item in ordered_assignments),
        qualifier_ids=tuple(item.id for item in ordered_qualifiers),
        polarity=cast(Literal["affirmed", "negated"], proposal.polarity),
        modality=cast(
            Literal[
                "actual",
                "planned",
                "possible",
                "uncertain",
                "recommended",
                "hypothetical",
            ],
            proposal.modality,
        ),
        attribution_kind=attribution_kind,
        attribution_target_id=(attribution_target.id if attribution_target is not None else None),
        support_evidence_target_id=segment.support_target.id,
        frame_selection_task_id=task_id,
        frame_selection_model_run_id=model_run_id,
        frame_selection_trace_id=frame_selection_trace.id,
    )
    proposition = build_complete_proposition(
        kind=PropositionKind.EVENT,
        subject_record_id=event.id,
        text=_render_complete_event_proposition(
            event,
            frame_definition,
            ordered_assignments,
            target_records,
            ordered_qualifiers,
        ),
        evidence_target_id=event.support_evidence_target_id,
    )
    statements = (
        *_statements(
            event,
            frame_definition,
            ordered_assignments,
            target_records,
            ordered_qualifiers,
            attribution_target,
        ),
        build_semantic_statement(
            event_semantic_id=event.id,
            kind=SemanticStatementKind.COMPLETE_PROPOSITION,
            subject_record_id=event.id,
            text=proposition.text,
            governed_definition=(
                "The complete proposition preserves the event frame, roles, qualifiers, "
                "polarity, modality, and attribution as one meaning."
            ),
            evidence_target_id=event.support_evidence_target_id,
        ),
    )
    return _ConstructedEvent(
        event,
        tuple(sorted(target_records.values(), key=lambda item: item.id)),
        ordered_assignments,
        ordered_qualifiers,
        tuple(sorted(gaps, key=lambda item: item.id)),
        tuple(sorted(statements, key=lambda item: item.id)),
        proposition,
        tuple(sorted((item[0] for item in evidence_records.values()), key=lambda item: item.id)),
        tuple(sorted((item[1] for item in evidence_records.values()), key=lambda item: item.id)),
    )


def _resolve_target(
    *,
    context: _SourceContext,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    value: str,
    allowed_target_kinds: tuple[SemanticArgumentTargetKind, ...],
    ledger: HybridEventSemanticsLedger,
) -> tuple[EventArgumentTargetDraft, EvidenceTarget, EvidenceValidationAttempt]:
    candidate_label = _candidate_label(value, local_inputs.candidates)
    if candidate_label is not None:
        candidate = local_inputs.candidates[candidate_label]
        if SemanticArgumentTargetKind.MENTION_CANDIDATE in allowed_target_kinds:
            return _referenced_target(
                context,
                segment,
                SemanticArgumentTargetKind.MENTION_CANDIDATE,
                candidate.id,
                candidate.text,
                candidate.start,
                candidate.end,
                ledger,
            )
        if SemanticArgumentTargetKind.SOURCE_SPAN in allowed_target_kinds:
            return _source_span_target(context, segment, candidate.text, ledger)
        raise ValueError("target_kind_not_allowed")
    if SemanticArgumentTargetKind.SOURCE_SPAN not in allowed_target_kinds:
        raise ValueError("target_kind_not_allowed")
    return _source_span_target(context, segment, value, ledger)


def _unique_candidate_label(
    proposed_literal: str, candidates: dict[str, MentionCandidate]
) -> str | None:
    normalized = " ".join(proposed_literal.split())
    matches = [
        label
        for label, candidate in candidates.items()
        if " ".join(candidate.text.split()) == normalized
    ]
    return matches[0] if len(matches) == 1 else None


def _candidate_label(proposed_value: str, candidates: dict[str, MentionCandidate]) -> str | None:
    if proposed_value in candidates:
        return proposed_value
    return _unique_candidate_label(proposed_value, candidates)


def _source_span_target(
    context: _SourceContext,
    segment: _SegmentContext,
    literal: str,
    ledger: HybridEventSemanticsLedger,
) -> tuple[EventArgumentTargetDraft, EvidenceTarget, EvidenceValidationAttempt]:
    exact_text, start = resolve_unique_source_literal(segment.segment.exact_text, literal)
    return _referenced_target(
        context,
        segment,
        SemanticArgumentTargetKind.SOURCE_SPAN,
        None,
        exact_text,
        start,
        start + len(exact_text),
        ledger,
    )


def _referenced_target(
    context: _SourceContext,
    segment: _SegmentContext,
    kind: SemanticArgumentTargetKind,
    reference_id: str | None,
    text: str,
    local_start: int,
    local_end: int,
    ledger: HybridEventSemanticsLedger,
) -> tuple[EventArgumentTargetDraft, EvidenceTarget, EvidenceValidationAttempt]:
    if segment.segment.exact_text[local_start:local_end] != text:
        raise ValueError("target_range_text_mismatch")
    support = segment.support_target
    text_view = next(item for item in context.bundle.text_views if item.id == support.text_view_id)
    start = support.start_char + local_start
    end = support.start_char + local_end
    target_id = _id(
        "etg",
        context.parent.representation_id,
        text_view.id,
        segment.segment_id,
        str(start),
        str(end),
        text,
    )
    target = EvidenceTarget(
        id=target_id,
        source_id=support.source_id,
        document_id=support.document_id,
        representation_id=support.representation_id,
        text_view_id=support.text_view_id,
        text_view_digest=support.text_view_digest,
        start_char=start,
        end_char=end,
        exact_text=text,
        normalization_policy=support.normalization_policy,
        prefix_text=text_view.text[max(0, start - 32) : start],
        suffix_text=text_view.text[end : min(len(text_view.text), end + 32)],
        node_ids=support.node_ids,
        pdf_region_ids=support.pdf_region_ids,
        dom_selector=support.dom_selector,
        table_selector=support.table_selector,
        created_at=support.created_at,
    )
    existing = ledger.get_evidence_target(target.id)
    if existing is not None:
        if _without_time(existing) != _without_time(target):
            raise ValueError("evidence_target_identity_conflict")
        target = existing
    validate_evidence_target_record(target, ledger)
    attempt_id = _id("eva", target.id, HYBRID_EVENT_SEMANTICS_EVIDENCE_VALIDATOR)
    attempt = EvidenceValidationAttempt(
        id=attempt_id,
        evidence_target_id=target.id,
        target_digest=canonical_evidence_target_digest(target),
        validator_version=HYBRID_EVENT_SEMANTICS_EVIDENCE_VALIDATOR,
        status=EvidenceValidationAttemptStatus.SUCCEEDED,
        attempted_at=support.created_at,
    )
    existing_attempt = ledger.get_evidence_validation_attempt(attempt.id)
    if existing_attempt is not None:
        if _without_time(existing_attempt) != _without_time(attempt):
            raise ValueError("evidence_attempt_identity_conflict")
        attempt = existing_attempt
    draft = build_event_argument_target_draft(
        kind=kind,
        reference_id=reference_id,
        source_segment_id=segment.segment_id,
        text=text,
        start=local_start,
        end=local_end,
        evidence_target_id=target.id,
        evidence_validation_attempt_id=attempt.id,
        embedded_candidate_ids=(
            _embedded_entity_candidate_ids(context, segment, local_start, local_end)
            if kind is SemanticArgumentTargetKind.SOURCE_SPAN
            else ()
        ),
    )
    return draft, target, attempt


def _embedded_entity_candidate_ids(
    context: _SourceContext,
    segment: _SegmentContext,
    start: int,
    end: int,
) -> tuple[str, ...]:
    selected = set(
        effective_mention_candidate_ids(
            context.mentions.boundary_decisions,
            context.mentions.boundary_adjudications,
        )
    )
    typed = {
        item.candidate_id
        for item in context.mentions.interpretations
        if item.contextual_kind
        in {
            ContextualKind.PERSON,
            ContextualKind.GOVERNMENT,
            ContextualKind.ORGANIZATION,
        }
    }
    return tuple(
        sorted(
            item.id
            for item in context.candidates.values()
            if item.id in selected
            and item.id in typed
            and item.source_segment_id == segment.segment_id
            and start <= item.start
            and item.end <= end
        )
    )


def _persist_evidence(
    constructed: _ConstructedEvent,
    ledger: HybridEventSemanticsLedger,
) -> None:
    attempts = {item.evidence_target_id: item for item in constructed.evidence_attempts}
    for target in constructed.evidence_targets:
        if ledger.get_evidence_target(target.id) is None:
            ledger.save_evidence_target(target)
        attempt = attempts[target.id]
        if ledger.get_evidence_validation_attempt(attempt.id) is None:
            ledger.save_evidence_validation_attempt(attempt)
        replay = verify_evidence_target(target, attempt, ledger)
        if not replay.valid:
            raise ValueError(f"HP-6 EvidenceTarget failed replay: {replay.error_message}")


def _statements(
    event: EventSemanticDraft,
    frame: EventFrameDefinition,
    assignments: tuple[EventArgumentAssignmentDraft, ...],
    targets: dict[str, EventArgumentTargetDraft],
    qualifiers: tuple[SemanticQualifierDraft, ...],
    attribution_target: EventArgumentTargetDraft | None,
) -> tuple[SemanticStatement, ...]:
    frame_label = frame.label.replace("_", " ")
    article = "an" if frame_label[0].lower() in "aeiou" else "a"
    statements = [
        build_semantic_statement(
            event_semantic_id=event.id,
            kind=SemanticStatementKind.FRAME,
            subject_record_id=event.id,
            text=(
                f"The event expressed by {json.dumps(event.trigger_text)} is {article} "
                f"{frame_label} event."
            ),
            governed_definition=frame.definition,
            evidence_target_id=event.support_evidence_target_id,
        )
    ]
    roles = {item.id: item for item in frame.roles}
    for assignment in assignments:
        role = roles[assignment.frame_role_id]
        target = targets[assignment.target_id]
        statements.append(
            build_semantic_statement(
                event_semantic_id=event.id,
                kind=SemanticStatementKind.ARGUMENT,
                subject_record_id=assignment.id,
                text=(
                    f"In the {frame.label.replace('_', ' ')} event expressed by "
                    f"{json.dumps(event.trigger_text)}, {json.dumps(target.text)} is the "
                    f"{role.label.replace('_', ' ')}."
                ),
                governed_definition=role.definition,
                evidence_target_id=event.support_evidence_target_id,
            )
        )
    statements.extend(
        (
            build_semantic_statement(
                event_semantic_id=event.id,
                kind=SemanticStatementKind.POLARITY,
                subject_record_id=event.id,
                text=(
                    f"The event expressed by {json.dumps(event.trigger_text)} has "
                    f"polarity {event.polarity}."
                ),
                governed_definition=(
                    "Polarity records whether the source affirms or negates an event."
                ),
                evidence_target_id=event.support_evidence_target_id,
            ),
            build_semantic_statement(
                event_semantic_id=event.id,
                kind=SemanticStatementKind.MODALITY,
                subject_record_id=event.id,
                text=(
                    f"The event expressed by {json.dumps(event.trigger_text)} has "
                    f"modality {event.modality}."
                ),
                governed_definition=(
                    "Modality records how the source presents the event's realization."
                ),
                evidence_target_id=event.support_evidence_target_id,
            ),
        )
    )
    for qualifier in qualifiers:
        statements.append(
            build_semantic_statement(
                event_semantic_id=event.id,
                kind=SemanticStatementKind.QUALIFIER,
                subject_record_id=qualifier.id,
                text=(
                    f"The event expressed by {json.dumps(event.trigger_text)} has "
                    f"{qualifier.kind} {json.dumps(qualifier.text)}."
                ),
                governed_definition=f"A {qualifier.kind} qualifier copied exactly from the source.",
                evidence_target_id=event.support_evidence_target_id,
            )
        )
    if event.attribution_kind is EventAttributionKind.UNRESOLVED:
        return tuple(sorted(statements, key=lambda item: item.id))
    if attribution_target is None:
        attribution_text = (
            "The document source directly supplies the event claim expressed by "
            f"{json.dumps(event.trigger_text)}."
        )
    else:
        attribution_text = (
            f"{json.dumps(attribution_target.text)} supplies the reported content "
            f"expressed by {json.dumps(event.trigger_text)}."
        )
    statements.append(
        build_semantic_statement(
            event_semantic_id=event.id,
            kind=SemanticStatementKind.ATTRIBUTION,
            subject_record_id=event.id,
            text=attribution_text,
            governed_definition=(
                "Attribution distinguishes a claim made directly by the document source from "
                "reported content supplied by an explicitly named speaker or reporter."
            ),
            evidence_target_id=event.support_evidence_target_id,
        )
    )
    return tuple(sorted(statements, key=lambda item: item.id))


def _render_complete_event_proposition(
    event: EventSemanticDraft,
    frame: EventFrameDefinition,
    assignments: tuple[EventArgumentAssignmentDraft, ...],
    targets: dict[str, EventArgumentTargetDraft],
    qualifiers: tuple[SemanticQualifierDraft, ...],
) -> str:
    """Render one complete proposition through explicit governed-frame dispatch."""
    values = {
        assignment.frame_role_id.split(".", maxsplit=1)[1]: targets[assignment.target_id].text
        for assignment in assignments
    }
    if frame.id == "agreement":
        clause = _frame_clause(values, "agreeing_party", "counterparty", verb="agreed with")
        if content := values.get("agreement_content"):
            clause += f" concerning {content}"
    elif frame.id == "authorization":
        clause = _frame_clause(values, "authorizer", "authorized_party", "permitted_action")
        if resource := values.get("authorized_resource"):
            clause += f" using {resource}"
    elif frame.id == "causation":
        clause = _frame_clause(values, "cause", "effect", verb="caused")
    elif frame.id == "communication":
        clause = _frame_clause(values, "communicator", "counterparty", verb="communicated with")
        if topic := values.get("topic"):
            clause += f" about {topic}"
    elif frame.id == "change_in_intensity":
        clause = (
            f"{values.get('affected_process', '[missing affected process]')} {event.trigger_text}"
        )
    elif frame.id == "characterization":
        clause = (
            f"{values.get('evaluator', '[missing evaluator]')} characterized "
            f"{values.get('evaluated_subject', '[missing evaluated subject]')} as "
            f"{values.get('characterization', '[missing characterization]')}"
        )
    elif frame.id == "classification":
        clause = (
            f"{values.get('classifier', '[missing classifier]')} classified "
            f"{values.get('classified_entity', '[missing classified entity]')} as "
            f"{values.get('assigned_classification', '[missing classification]')}"
        )
        if reason := values.get("stated_reason"):
            clause += f" because {reason}"
    elif frame.id == "criticism":
        clause = (
            f"{values.get('critic', '[missing critic]')} criticized "
            f"{values.get('target', '[missing target]')}"
        )
        if assessment := values.get("assessment"):
            clause += f" as {assessment}"
        if topic := values.get("topic"):
            clause += f" about {topic}"
        if reason := values.get("reason"):
            clause += f" because {reason}"
    elif frame.id == "investment_abandonment":
        abandoned_asset = values.get("abandoned_asset", "[missing abandoned asset]")
        clause = f"{values.get('disinvestor', '[missing disinvestor]')} abandoned {abandoned_asset}"
        if investee := values.get("investee"):
            normalized_asset = f" {' '.join(abandoned_asset.casefold().split())} "
            normalized_investee = f" {' '.join(investee.casefold().split())} "
            if normalized_investee not in normalized_asset:
                clause += f" in {investee}"
    elif frame.id == "legal_ruling":
        clause = (
            f"{values.get('deciding_authority', '[missing deciding authority]')} issued "
            f"{values.get('ruling', '[missing ruling]')} concerning "
            f"{values.get('matter', '[missing matter]')}"
        )
        if affected_party := values.get("affected_party"):
            clause += f", affecting {affected_party}"
    elif frame.id == "policy_change":
        clause = (
            f"{values.get('policy_actor', '[missing policy actor]')} made "
            f"{values.get('change', '[missing change]')} to "
            f"{values.get('policy', '[missing policy]')}"
        )
    elif frame.id == "publication":
        clause = (
            f"{values.get('publisher', '[missing publisher]')} published "
            f"{values.get('published_work', '[missing published work]')}"
        )
        if topic := values.get("topic"):
            clause += f" about {topic}"
        if outlet := values.get("outlet"):
            clause += f" in {outlet}"
        if audience := values.get("audience"):
            clause += f" for {audience}"
    elif frame.id == "rebuttal":
        clause = (
            f"{values.get('rebutter', '[missing rebutter]')} rebutted "
            f"{values.get('challenged_claim', '[missing challenged claim]')}"
        )
        if source := values.get("claim_source"):
            clause += f" from {source}"
        if medium := values.get("medium"):
            clause += f" in {medium}"
    elif frame.id == "recommendation":
        clause = (
            f"{values.get('recommender', '[missing recommender]')} recommended "
            f"{values.get('recommended_action', '[missing recommended action]')}"
        )
        if subject := values.get("recommendation_subject"):
            clause += f" concerning {subject}"
    elif frame.id == "refusal":
        clause = _frame_clause(values, "refuser", "refused_action", verb="refused")
    elif frame.id == "threat":
        clause = _frame_clause(values, "threatener", "threatened_action", verb="threatened")
        if target := values.get("target"):
            clause += f" against {target}"
    else:
        raise ValueError(f"Unsupported governed frame renderer: {frame.id}")
    if event.polarity == "negated":
        clause = f"It is not the case that {clause}"
    if event.modality != "actual":
        clause = f"The source presents as {event.modality} that {clause}"
    for qualifier in sorted(qualifiers, key=lambda item: (item.kind, item.start, item.id)):
        preposition = (
            "at"
            if qualifier.kind == "place"
            else cast(TemporalRelation, qualifier.temporal_relation).value
        )
        clause += f" {preposition} {qualifier.text}"
    return f"{clause}."


def _frame_clause(
    values: dict[str, str],
    first: str,
    second: str,
    third: str | None = None,
    *,
    verb: str = "authorized",
) -> str:
    first_value = values.get(first, f"[missing {first}]")
    second_value = values.get(second, f"[missing {second}]")
    clause = f"{first_value} {verb} {second_value}"
    if third is not None:
        clause += f" to {values.get(third, f'[missing {third}]')}"
    return clause


def _frame_selection_task_input(
    *,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
) -> bytes:
    lines = [
        "task: select_one_event_frame",
        f"target_trigger_expression: {trigger.text}",
        f"target_trigger_head: {trigger.head_text}",
        f"open_event_label_proposal: {trigger.event_type_label}",
        f"source_segment: {segment.segment.exact_text}",
        f"source_before_target_trigger: {segment.segment.exact_text[: trigger.start]}",
        f"source_after_target_trigger: {segment.segment.exact_text[trigger.end :]}",
        "governed_frame_catalog:",
    ]
    for profile_frame in HYBRID_EVENT_SEMANTICS_V4.frames:
        lines.append(f"frame | {profile_frame.id} | {profile_frame.definition}")
    lines.append(f"classify_only_target_trigger_expression: {trigger.text}")
    return "\n".join(lines).encode()


def _frame_fit_task_input(
    *,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    frame: EventFrameDefinition,
) -> bytes:
    return "\n".join(
        (
            "task: challenge_one_event_frame_fit",
            f"target_trigger_expression: {trigger.text}",
            f"target_trigger_head: {trigger.head_text}",
            f"selected_frame: {frame.id} | {frame.definition}",
            f"source_segment: {segment.segment.exact_text}",
            "judge_only_whether_selected_frame_fits: yes",
        )
    ).encode()


def _role_selection_task_input(
    *,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    frame: EventFrameDefinition,
    role: FrameRoleDefinition,
    selected_arguments: dict[str, EventSemanticArgumentProposal],
    rejected_target: str | None,
) -> bytes:
    lines = [
        "task: select_one_frame_role",
        f"target_trigger_expression: {trigger.text}",
        f"target_trigger_head: {trigger.head_text}",
        f"selected_frame: {frame.id} | {frame.definition}",
        "sibling_role_catalog:",
    ]
    lines.extend(
        " | ".join(
            (
                sibling.id,
                "required" if sibling.required else "optional",
                ",".join(item.value for item in sibling.allowed_target_kinds),
                sibling.upper_role.value,
                sibling.definition,
            )
        )
        for sibling in frame.roles
    )
    lines.append("selected_sibling_targets:")
    lines.extend(
        f"{sibling.id} | {selected_arguments[sibling.id].target_value}"
        for sibling in frame.roles
        if sibling.id in selected_arguments
    )
    lines.extend(
        [
            "target_role: "
            + " | ".join(
                (
                    role.id,
                    "required" if role.required else "optional",
                    ",".join(item.value for item in role.allowed_target_kinds),
                    role.upper_role.value,
                    role.definition,
                )
            ),
            f"source_segment: {segment.segment.exact_text}",
            f"source_before_target_trigger: {segment.segment.exact_text[: trigger.start]}",
            f"source_after_target_trigger: {segment.segment.exact_text[trigger.end :]}",
            "mention_candidate_catalog:",
        ]
    )
    lines.extend(
        f"{label} | {candidate.text}"
        for label, candidate in local_inputs.candidates.items()
        if SemanticArgumentTargetKind.MENTION_CANDIDATE in role.allowed_target_kinds
    )
    lines.append("reference_metadata:")
    lines.extend(
        " | ".join(
            (
                label,
                decision.status.value,
                ", ".join(span.text for span in antecedents) or "none",
            )
        )
        for label, (decision, antecedents) in local_inputs.reference_metadata.items()
        if label in local_inputs.candidates
    )
    lines.append("source_occurrence_catalog:")
    lines.extend(
        f"{item.occurrence_id} | {item.text}" for item in local_inputs.occurrences.values()
    )
    if rejected_target is not None:
        lines.append(f"rejected_previous_target: {rejected_target}")
    lines.append(f"select_only_frame_role: {role.id}")
    return "\n".join(lines).encode()


def _event_presentation_task_input(
    *,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    frame: EventFrameDefinition,
    selected_arguments: dict[str, EventSemanticArgumentProposal],
) -> bytes:
    lines = [
        "task: classify_one_event_presentation",
        f"target_trigger_expression: {trigger.text}",
        f"target_trigger_head: {trigger.head_text}",
        f"selected_frame: {frame.id} | {frame.definition}",
        f"source_segment: {segment.segment.exact_text}",
        "selected_role_targets:",
    ]
    lines.extend(
        f"{role.id} | {selected_arguments[role.id].target_value}"
        for role in frame.roles
        if role.id in selected_arguments
    )
    lines.append("mention_candidate_catalog:")
    lines.extend(
        f"{label} | {candidate.text}" for label, candidate in local_inputs.candidates.items()
    )
    lines.append("reference_metadata:")
    lines.extend(
        " | ".join(
            (
                label,
                decision.status.value,
                ", ".join(span.text for span in antecedents) or "none",
            )
        )
        for label, (decision, antecedents) in local_inputs.reference_metadata.items()
    )
    lines.append("source_occurrence_catalog:")
    lines.extend(
        f"{item.occurrence_id} | {item.text}" for item in local_inputs.occurrences.values()
    )
    lines.append(f"classify_only_presentation_for: {trigger.text}")
    return "\n".join(lines).encode()


def _completed_role_argument(
    proposal: EventSemanticRoleTargetProposal | None,
    role: FrameRoleDefinition,
    context: _SourceContext,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    ledger: HybridEventSemanticsLedger,
) -> EventSemanticArgumentProposal | None:
    if proposal is None or proposal.target_selector is None:
        return None
    target_value = _resolve_model_selector(proposal.target_selector, local_inputs)
    if (
        target_value in local_inputs.candidates
        and SemanticArgumentTargetKind.MENTION_CANDIDATE not in role.allowed_target_kinds
    ):
        raise ValueError("target_kind_not_allowed")
    _resolve_target(
        context=context,
        segment=segment,
        local_inputs=local_inputs,
        value=target_value,
        allowed_target_kinds=role.allowed_target_kinds,
        ledger=ledger,
    )
    return EventSemanticArgumentProposal(role.id, target_value)


def _resolve_model_selector(
    selector: str,
    local_inputs: _LocalInputs,
    *,
    allow_reserved: bool = False,
) -> str:
    if allow_reserved and selector in {"source_narrator", "unresolved"}:
        return selector
    if selector in local_inputs.candidates:
        return selector
    return _resolve_source_selector(selector, local_inputs)


def _resolve_source_selector(selector: str, local_inputs: _LocalInputs) -> str:
    endpoints = selector.split("-", maxsplit=1)
    first = local_inputs.occurrences.get(endpoints[0])
    last = local_inputs.occurrences.get(endpoints[-1])
    if first is None or last is None or first.start > last.start:
        raise ValueError("unknown_or_reversed_source_selector")
    start, end = local_inputs.source_copy.authoritative_range(first.start, last.end)
    return local_inputs.source_text[start:end]


def _support_task_input(evidence_text: str, statement: SemanticStatement) -> bytes:
    return _canonical_json(
        cast(
            JsonValue,
            {
                "task": "judge_one_semantic_statement",
                "evidence_target": evidence_text,
                "semantic_statement": statement.text,
                "governed_definition": statement.governed_definition,
            },
        )
    ).encode()


def _frame_selection_trace(
    *,
    subject: EventSubjectDraft,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    task_input: bytes,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_id: str,
    model_run_id: str,
    model_status: ModelRunStatus,
    raw_output_sha256: str | None,
    selection: EventFrameSelection | None,
) -> ExtractionStageTrace:
    completed = selection is not None and model_status is ModelRunStatus.SUCCEEDED
    return build_extraction_stage_trace(
        trace_run_id=f"hp6:frame:{subject.id}:{model_run_id}",
        ordinal=0,
        stage_id="hybrid_event_frame_selection",
        stage_version="1",
        producer_id="qwen2.5",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        configuration={
            "policy_id": HYBRID_EVENT_SEMANTICS_POLICY_ID,
            "ontology_sha256": hybrid_event_semantics_profile_sha256(),
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload=cast(
            dict[str, JsonValue],
            {
                "event_subject": subject.model_dump(mode="json"),
                "trigger": trigger.model_dump(mode="json"),
                "model_visible_task": task_input.decode(),
            },
        ),
        output_payload={
            "model_run_status": model_status.value,
            "raw_output_sha256": raw_output_sha256,
            "parsed_selection": _model_payload(selection),
        },
        status=ExtractionStageStatus.COMPLETED if completed else ExtractionStageStatus.FAILED,
        diagnostics=() if completed else (f"model_run_status:{model_status.value}",),
        input_record_ids=tuple(sorted({subject.id, trigger.id})),
        execution_record_ids=(task_id, model_run_id),
    )


def _role_selection_trace(
    *,
    subject: EventSubjectDraft,
    frame: EventFrameDefinition,
    role: FrameRoleDefinition,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    task_input: bytes,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_id: str,
    model_run_id: str,
    model_status: ModelRunStatus,
    raw_output_sha256: str | None,
    proposal: EventSemanticRoleTargetProposal | None,
    parent_trace_id: str,
) -> ExtractionStageTrace:
    completed = proposal is not None and model_status is ModelRunStatus.SUCCEEDED
    return build_extraction_stage_trace(
        trace_run_id=f"hp6:select-role:{subject.id}:{role.id}:{model_run_id}",
        ordinal=0,
        stage_id="hybrid_event_role_selection",
        stage_version="1",
        producer_id="qwen2.5",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        parent_trace_ids=(parent_trace_id,),
        configuration={
            "policy_id": HYBRID_EVENT_SEMANTICS_POLICY_ID,
            "ontology_sha256": hybrid_event_semantics_profile_sha256(),
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload=cast(
            dict[str, JsonValue],
            {
                "event_subject": subject.model_dump(mode="json"),
                "selected_frame": frame.model_dump(mode="json"),
                "target_role": role.model_dump(mode="json"),
                "trigger": trigger.model_dump(mode="json"),
                "model_visible_task": task_input.decode(),
            },
        ),
        output_payload={
            "model_run_status": model_status.value,
            "raw_output_sha256": raw_output_sha256,
            "parsed_target_proposal": _model_payload(proposal),
        },
        status=ExtractionStageStatus.COMPLETED if completed else ExtractionStageStatus.FAILED,
        diagnostics=() if completed else (f"model_run_status:{model_status.value}",),
        input_record_ids=tuple(sorted({subject.id, trigger.id})),
        execution_record_ids=(task_id, model_run_id),
    )


def _frame_fit_trace(
    *,
    subject: EventSubjectDraft,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    frame: EventFrameDefinition,
    task_input: bytes,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_id: str,
    model_run_id: str,
    model_status: ModelRunStatus,
    raw_output_sha256: str | None,
    decision: EventFrameFitDecision | None,
    parent_trace_id: str,
) -> ExtractionStageTrace:
    completed = decision is not None and model_status is ModelRunStatus.SUCCEEDED
    return build_extraction_stage_trace(
        trace_run_id=f"hp6:frame-fit:{subject.id}:{model_run_id}",
        ordinal=0,
        stage_id="hybrid_event_frame_fit",
        stage_version="1",
        producer_id="qwen2.5",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        parent_trace_ids=(parent_trace_id,),
        configuration={
            "policy_id": HYBRID_EVENT_SEMANTICS_POLICY_ID,
            "ontology_sha256": hybrid_event_semantics_profile_sha256(),
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload=cast(
            dict[str, JsonValue],
            {
                "event_subject": subject.model_dump(mode="json"),
                "trigger": trigger.model_dump(mode="json"),
                "selected_frame": frame.model_dump(mode="json"),
                "model_visible_task": task_input.decode(),
            },
        ),
        output_payload={
            "model_run_status": model_status.value,
            "raw_output_sha256": raw_output_sha256,
            "parsed_decision": _model_payload(decision),
        },
        status=ExtractionStageStatus.COMPLETED if completed else ExtractionStageStatus.FAILED,
        diagnostics=() if completed else (f"model_run_status:{model_status.value}",),
        input_record_ids=tuple(sorted({subject.id, trigger.id})),
        execution_record_ids=(task_id, model_run_id),
    )


def _event_presentation_trace(
    *,
    subject: EventSubjectDraft,
    frame: EventFrameDefinition,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    task_input: bytes,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_id: str,
    model_run_id: str,
    model_status: ModelRunStatus,
    raw_output_sha256: str | None,
    selection: EventPresentationSelection | None,
    rejections: tuple[EventSemanticLineRejection, ...],
    parent_trace_ids: tuple[str, ...],
) -> ExtractionStageTrace:
    completed = selection is not None and model_status is ModelRunStatus.SUCCEEDED
    return build_extraction_stage_trace(
        trace_run_id=f"hp6:presentation:{subject.id}:{model_run_id}",
        ordinal=0,
        stage_id="hybrid_event_presentation",
        stage_version="1",
        producer_id="qwen2.5",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        parent_trace_ids=tuple(sorted(parent_trace_ids)),
        configuration={
            "policy_id": HYBRID_EVENT_SEMANTICS_POLICY_ID,
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "event_subject": subject.model_dump(mode="json"),
            "selected_frame": frame.model_dump(mode="json"),
            "trigger": trigger.model_dump(mode="json"),
            "model_visible_task": task_input.decode(),
        },
        output_payload={
            "model_run_status": model_status.value,
            "raw_output_sha256": raw_output_sha256,
            "parsed_selection": _model_payload(selection),
            "line_rejections": [_model_payload(item) for item in rejections],
        },
        status=ExtractionStageStatus.COMPLETED if completed else ExtractionStageStatus.FAILED,
        diagnostics=() if completed else (f"model_run_status:{model_status.value}",),
        input_record_ids=tuple(sorted({subject.id, trigger.id})),
        execution_record_ids=(task_id, model_run_id),
    )


def _construction_trace(
    *,
    subject: EventSubjectDraft,
    segment: _SegmentContext,
    proposal: EventSemanticProposal,
    selection_traces: tuple[ExtractionStageTrace, ...],
    constructed: _ConstructedEvent,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=selection_traces[0].trace_run_id,
        ordinal=1,
        stage_id="hybrid_event_semantic_construction",
        stage_version="1",
        producer_id="kotekomi",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        parent_trace_ids=tuple(sorted(item.id for item in selection_traces)),
        configuration={
            "policy_id": HYBRID_EVENT_SEMANTICS_POLICY_ID,
            "evidence_validator": HYBRID_EVENT_SEMANTICS_EVIDENCE_VALIDATOR,
            "source_alignment": HYBRID_EVENT_SEMANTICS_SOURCE_ALIGNMENT,
        },
        input_payload={
            "event_subject_id": subject.id,
            "parsed_proposal": _model_payload(proposal),
        },
        output_payload=cast(
            dict[str, JsonValue],
            {
                "event": constructed.event.model_dump(mode="json") if constructed.event else None,
                "targets": [item.model_dump(mode="json") for item in constructed.targets],
                "assignments": [item.model_dump(mode="json") for item in constructed.assignments],
                "qualifiers": [item.model_dump(mode="json") for item in constructed.qualifiers],
                "gaps": [item.model_dump(mode="json") for item in constructed.gaps],
                "statements": [item.model_dump(mode="json") for item in constructed.statements],
            },
        ),
        status=ExtractionStageStatus.COMPLETED,
        input_record_ids=(subject.id,),
    )


def _support_trace(
    *,
    statement: SemanticStatement,
    segment: _SegmentContext,
    task_input: bytes,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_id: str,
    model_run_id: str,
    model_status: ModelRunStatus,
    raw_output_sha256: str | None,
    judgment: SemanticSupportJudgment | None,
) -> ExtractionStageTrace:
    completed = judgment is not None and model_status is ModelRunStatus.SUCCEEDED
    return build_extraction_stage_trace(
        trace_run_id=f"hp6:support:{statement.id}:{model_run_id}",
        ordinal=0,
        stage_id="hybrid_semantic_source_support",
        stage_version="1",
        producer_id="qwen2.5",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        configuration={
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload=cast(
            dict[str, JsonValue],
            {
                "semantic_statement": statement.model_dump(mode="json"),
                "evidence_target": segment.support_target.model_dump(mode="json"),
                "model_visible_task": task_input.decode(),
            },
        ),
        output_payload=cast(
            dict[str, JsonValue],
            {
                "model_run_status": model_status.value,
                "raw_output_sha256": raw_output_sha256,
                "support_judgment": judgment.model_dump(mode="json") if judgment else None,
            },
        ),
        status=ExtractionStageStatus.COMPLETED if completed else ExtractionStageStatus.FAILED,
        diagnostics=() if completed else (f"model_run_status:{model_status.value}",),
        input_record_ids=tuple(sorted((statement.id, segment.support_target.id))),
        execution_record_ids=(task_id, model_run_id),
    )


def _nli_trace(
    *,
    proposition: CompleteProposition,
    premise: str,
    source_segment_id: str,
    observation: NliObservation | None,
    decision: PropositionDecision,
    error: str | None,
    parent_trace_id: str,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=f"hsq3:nli:{proposition.id}",
        ordinal=0,
        stage_id="complete_proposition_nli_challenge",
        stage_version="1",
        producer_id="deberta-nli",
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(premise.encode()).hexdigest(),
        parent_trace_ids=(parent_trace_id,),
        configuration={
            "entailment_threshold": HYBRID_EVENT_NLI_ENTAILMENT_THRESHOLD,
        },
        input_payload={
            "premise": premise,
            "hypothesis": proposition.text,
            "proposition_id": proposition.id,
        },
        output_payload={
            "observation": observation.model_dump(mode="json") if observation else None,
            "decision": decision.model_dump(mode="json"),
        },
        status=(
            ExtractionStageStatus.COMPLETED
            if observation is not None
            else ExtractionStageStatus.FAILED
        ),
        diagnostics=(f"nli_error:{error}",) if error else (),
        input_record_ids=(proposition.id,),
    )


def _support_judgment(
    statement: SemanticStatement,
    parsed: SemanticSupportModelJudgment | None,
    task_id: str,
    model_run_id: str,
    model_status: ModelRunStatus,
) -> SemanticSupportJudgment | None:
    if parsed is None or model_status is not ModelRunStatus.SUCCEEDED:
        return None
    return build_semantic_support_judgment(
        statement_id=statement.id,
        evidence_target_id=statement.evidence_target_id,
        outcome=parsed.outcome,
        reason=parsed.reason,
        extraction_task_id=task_id,
        model_run_id=model_run_id,
    )


def _frame_definition(frame_id: str) -> EventFrameDefinition:
    frame = next((item for item in HYBRID_EVENT_SEMANTICS_V4.frames if item.id == frame_id), None)
    if frame is None:
        raise ValueError("unknown_event_frame")
    return frame


def _build_manifest(
    *,
    unit: AnalysisUnit,
    profile: ContextModelProfile,
    prompt_id: str,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    ledger: HybridEventSemanticsLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=profile,
            prompt_id=prompt_id,
            prompt_bytes=prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="hybrid_event_semantics_context_v1",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "HP-6 ContextManifest is not ready: "
            f"{planning.manifest.blocked_reason or planning.manifest.status.value}"
        )
    verify_context_manifest(
        planning.manifest.id,
        ledger,
        tokenizer,
        prompt_bytes,
        schema.canonical_schema_bytes,
    )
    return planning.manifest


def _execution_spec(
    manifest: ContextManifest,
    runtime: ModelTaskRuntime,
    generation: tuple[ExecutionSetting, ...],
    schema: PinnedTaskSchema,
    task_input: bytes,
) -> ModelExecutionSpec:
    rendered = manifest.rendered_input + b"\n\n[task]\n" + task_input
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=runtime.configured_identity,
        generation_parameters=generation,
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=schema.schema_id,
        schema_digest=schema.digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=hashlib.sha256(rendered).hexdigest(),
        output_contract_version=schema.output_contract_version,
    )


def _preview_common(
    context: _SourceContext,
    parent_sha256: str,
    frame_selection_prompt: bytes,
    frame_selection_schema: PinnedTaskSchema,
    frame_fit_prompt: bytes,
    frame_fit_schema: PinnedTaskSchema,
    role_selection_prompt: bytes,
    role_selection_schema: PinnedTaskSchema,
    presentation_prompt: bytes,
    presentation_schema: PinnedTaskSchema,
    support_prompt: bytes,
    support_schema: PinnedTaskSchema,
) -> dict[str, object]:
    return {
        "parent_preview_id": context.parent.id,
        "parent_preview_sha256": parent_sha256,
        "representation_id": context.parent.representation_id,
        "paragraph_node_id": context.parent.paragraph_node_id,
        "ontology_profile_id": HYBRID_EVENT_SEMANTICS_V4.id,
        "ontology_profile_sha256": hybrid_event_semantics_profile_sha256(),
        "frame_selection_prompt_sha256": hashlib.sha256(frame_selection_prompt).hexdigest(),
        "frame_selection_schema_sha256": frame_selection_schema.digest,
        "frame_fit_prompt_sha256": hashlib.sha256(frame_fit_prompt).hexdigest(),
        "frame_fit_schema_sha256": frame_fit_schema.digest,
        "role_selection_prompt_sha256": hashlib.sha256(role_selection_prompt).hexdigest(),
        "role_selection_schema_sha256": role_selection_schema.digest,
        "presentation_prompt_sha256": hashlib.sha256(presentation_prompt).hexdigest(),
        "presentation_schema_sha256": presentation_schema.digest,
        "support_prompt_sha256": hashlib.sha256(support_prompt).hexdigest(),
        "support_schema_sha256": support_schema.digest,
    }


def _result(preview: HybridEventSemanticsPreview) -> HybridEventSemanticsResult:
    return HybridEventSemanticsResult(
        preview,
        hybrid_event_semantics_preview_sha256(preview),
        f"extraction/event-semantic-previews/{preview.id}.json",
    )


def _model_payload(value: object) -> JsonValue:
    return cast(JsonValue, json.loads(json.dumps(value, default=lambda item: item.__dict__)))


def _without_time(value: object) -> dict[str, object]:
    payload = cast(dict[str, object], value.model_dump(mode="python"))  # type: ignore[attr-defined]
    payload.pop("created_at", None)
    payload.pop("attempted_at", None)
    return payload


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
