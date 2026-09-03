"""HP-6 governed event normalization and independent source-support orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from kotekomi_domain import (
    HYBRID_EVENT_SEMANTICS_V1,
    DocumentRepresentationBundle,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ModelRunStatus,
    SemanticArgumentTargetKind,
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
    RetrievalSelectionAnalysisUnitInput,
    SourceSegment,
    build_context_manifest,
    create_analysis_unit_from_retrieval_selection,
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
from kotekomi_application.hybrid_atomic_claim_preview import (
    HybridAtomicClaimArchive,
    HybridAtomicClaimLedger,
    load_hybrid_atomic_claim_preview,
)
from kotekomi_application.hybrid_atomic_claims import (
    AtomicClaimObjectKind,
    EventSubjectDraft,
    HybridAtomicClaimPreview,
    HybridAtomicClaimStatus,
    canonical_hybrid_atomic_claim_preview_bytes,
)
from kotekomi_application.hybrid_event_frame_preview import load_hybrid_event_frame_preview
from kotekomi_application.hybrid_event_frames import EventFrameDraft, EventTriggerDraft
from kotekomi_application.hybrid_event_semantics import (
    HYBRID_EVENT_NORMALIZATION_PROMPT_ID,
    HYBRID_EVENT_NORMALIZATION_SCHEMA_ID,
    HYBRID_EVENT_ROLE_COMPLETION_PROMPT_ID,
    HYBRID_EVENT_ROLE_COMPLETION_SCHEMA_ID,
    HYBRID_EVENT_SEMANTICS_POLICY_ID,
    HYBRID_SEMANTIC_SUPPORT_PROMPT_ID,
    HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID,
    EventArgumentAssignmentDraft,
    EventArgumentTargetDraft,
    EventAttributionKind,
    EventSemanticDraft,
    HybridEventSemanticsPreview,
    HybridEventSemanticsStatus,
    SemanticCoverageGap,
    SemanticCoverageGapCode,
    SemanticQualifierDraft,
    SemanticStatement,
    SemanticStatementKind,
    SemanticSupportJudgment,
    build_event_argument_assignment_draft,
    build_event_argument_target_draft,
    build_event_semantic_draft,
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
    EventSemanticArgumentProposal,
    EventSemanticProposal,
    EventSemanticRoleTargetProposal,
    SemanticSupportModelJudgment,
    event_semantic_role_target_schema_bytes,
    event_semantic_schema_bytes,
    parse_event_semantic_output,
    parse_event_semantic_role_target_output,
    parse_semantic_support_output,
    semantic_support_schema_bytes,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    MentionCandidate,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)
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


class HybridEventSemanticsLedger(HybridAtomicClaimLedger, StagedExtractionLedger, Protocol):
    pass


class HybridEventSemanticsArchive(HybridAtomicClaimArchive, Protocol):
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
    parent: HybridAtomicClaimPreview
    bundle: DocumentRepresentationBundle
    mentions: HybridExtractionPreview
    frames: dict[str, EventFrameDraft]
    triggers: dict[str, EventTriggerDraft]
    candidates: dict[str, MentionCandidate]
    segments: dict[str, _SegmentContext]
    source_id: str
    document_id: str


@dataclass(frozen=True)
class _LocalInputs:
    candidates: dict[str, MentionCandidate]
    sibling_events: dict[str, EventSubjectDraft]


@dataclass(frozen=True)
class _ConstructedEvent:
    event: EventSemanticDraft | None
    targets: tuple[EventArgumentTargetDraft, ...]
    assignments: tuple[EventArgumentAssignmentDraft, ...]
    qualifiers: tuple[SemanticQualifierDraft, ...]
    gaps: tuple[SemanticCoverageGap, ...]
    statements: tuple[SemanticStatement, ...]
    evidence_targets: tuple[EvidenceTarget, ...]
    evidence_attempts: tuple[EvidenceValidationAttempt, ...]


class _SemanticSchemaRegistry:
    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id == HYBRID_EVENT_NORMALIZATION_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                event_semantic_schema_bytes(),
                schema_id,
                parse_event_semantic_output,
            )
        if schema_id == HYBRID_EVENT_ROLE_COMPLETION_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                event_semantic_role_target_schema_bytes(),
                schema_id,
                parse_event_semantic_role_target_output,
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
    normalization_prompt_bytes: bytes,
    role_completion_prompt_bytes: bytes,
    support_prompt_bytes: bytes,
) -> HybridEventSemanticsResult:
    """Build governed semantic drafts and independently verify every statement."""
    context = _load_context(command.parent_preview_id, ledger, archive)
    registry: TaskSchemaRegistry = _SemanticSchemaRegistry()
    normalization_schema = registry.resolve(HYBRID_EVENT_NORMALIZATION_SCHEMA_ID)
    role_completion_schema = registry.resolve(HYBRID_EVENT_ROLE_COMPLETION_SCHEMA_ID)
    support_schema = registry.resolve(HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID)
    parent_sha256 = hashlib.sha256(
        canonical_hybrid_atomic_claim_preview_bytes(context.parent)
    ).hexdigest()
    common = _preview_common(
        context,
        parent_sha256,
        normalization_prompt_bytes,
        normalization_schema,
        role_completion_prompt_bytes,
        role_completion_schema,
        support_prompt_bytes,
        support_schema,
    )
    if context.parent.terminal_status is HybridAtomicClaimStatus.BLOCKED:
        preview = build_hybrid_event_semantics_preview(
            **common,
            terminal_status=HybridEventSemanticsStatus.BLOCKED,
            diagnostics=("hp5_status:blocked",),
        )
        return _result(preview)

    unit = create_analysis_unit_from_retrieval_selection(
        RetrievalSelectionAnalysisUnitInput(
            representation_id=context.parent.representation_id,
            focus_node_ids=(context.parent.paragraph_node_id,),
            policy_id=HYBRID_EVENT_SEMANTICS_POLICY_ID,
            task_type="hybrid_event_semantics_preview",
        ),
        ledger,
    )
    normalization_manifest = _build_manifest(
        unit=unit,
        profile=command.model_profile,
        prompt_id=HYBRID_EVENT_NORMALIZATION_PROMPT_ID,
        prompt_bytes=normalization_prompt_bytes,
        schema=normalization_schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )
    role_completion_manifest = _build_manifest(
        unit=unit,
        profile=command.model_profile,
        prompt_id=HYBRID_EVENT_ROLE_COMPLETION_PROMPT_ID,
        prompt_bytes=role_completion_prompt_bytes,
        schema=role_completion_schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )
    support_manifest = _build_manifest(
        unit=unit,
        profile=command.model_profile,
        prompt_id=HYBRID_SEMANTIC_SUPPORT_PROMPT_ID,
        prompt_bytes=support_prompt_bytes,
        schema=support_schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )

    events: list[EventSemanticDraft] = []
    targets: list[EventArgumentTargetDraft] = []
    assignments: list[EventArgumentAssignmentDraft] = []
    qualifiers: list[SemanticQualifierDraft] = []
    gaps: list[SemanticCoverageGap] = []
    statements: list[SemanticStatement] = []
    judgments: list[SemanticSupportJudgment] = []
    evidence_targets: dict[str, EvidenceTarget] = {}
    evidence_attempts: dict[str, EvidenceValidationAttempt] = {}
    task_ids: list[str] = []
    run_ids: list[str] = []
    traces: list[ExtractionStageTrace] = []
    diagnostics: list[str] = []

    for subject in context.parent.event_subjects:
        frame = context.frames[subject.frame_id]
        trigger = context.triggers[subject.trigger_id]
        segment = context.segments[trigger.source_segment_id]
        local_inputs = _local_inputs(context, subject, segment.segment_id)
        task_input = _normalization_task_input(
            context=context,
            subject=subject,
            frame=frame,
            trigger=trigger,
            segment=segment,
            local_inputs=local_inputs,
        )
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=context.source_id,
                document_id=context.document_id,
                representation_id=context.parent.representation_id,
                context_manifest_id=normalization_manifest.id,
                prompt_bytes=normalization_prompt_bytes,
                execution_spec=_execution_spec(
                    normalization_manifest,
                    model_runtime,
                    command.generation_parameters,
                    normalization_schema,
                    task_input,
                ),
                validator_version="hybrid_event_normalization_validator_v1",
                task_type="hybrid_event_semantic_normalization",
                input_candidate_ids=(subject.id,),
                task_local_input=task_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        task_ids.append(outcome.extraction_task.id)
        run_ids.append(outcome.model_run.id)
        proposal = outcome.event_semantic_proposal
        normalization_trace = _normalization_trace(
            context=context,
            subject=subject,
            frame=frame,
            trigger=trigger,
            segment=segment,
            local_inputs=local_inputs,
            task_input=task_input,
            prompt_bytes=normalization_prompt_bytes,
            schema=normalization_schema,
            task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            model_status=outcome.model_run.status,
            raw_output_sha256=outcome.model_run.output_digest,
            proposal=proposal,
        )
        traces.append(normalization_trace)
        if proposal is None or outcome.model_run.status is not ModelRunStatus.SUCCEEDED:
            diagnostics.append(
                f"normalization_task_failed:{subject.id}:{outcome.model_run.status.value}"
            )
            continue
        if proposal.frame_id is None:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.UNMAPPED_FRAME,
                    field_value=frame.id,
                    detail="No governed frame accurately represented the source event.",
                )
            )
            diagnostics.append(f"unmapped_frame:{subject.id}")
            continue
        try:
            frame_definition = _frame_definition(proposal.frame_id)
        except ValueError as error:
            diagnostics.append(f"normalization_mapping_failed:{subject.id}:{error}")
            continue
        role_by_id = {item.id: item for item in frame_definition.roles}
        proposal_roles = [item.frame_role_id for item in proposal.arguments]
        if any(item not in role_by_id for item in proposal_roles) or len(
            set(proposal_roles)
        ) != len(proposal_roles):
            diagnostics.append(f"normalization_mapping_failed:{subject.id}:invalid_role_shape")
            continue
        primary_arguments: dict[str, EventSemanticArgumentProposal] = {}
        invalid_targets: dict[str, str] = {}
        for argument in proposal.arguments:
            role = role_by_id[argument.frame_role_id]
            try:
                _resolve_target(
                    context=context,
                    segment=segment,
                    local_inputs=local_inputs,
                    value=argument.target_value,
                    allowed_target_kinds=role.allowed_target_kinds,
                    ledger=ledger,
                )
            except ValueError as error:
                invalid_targets[role.id] = f"{error}:{argument.target_value}"
            else:
                primary_arguments[role.id] = argument

        normalization_traces = [normalization_trace]
        selected_arguments: dict[str, EventSemanticArgumentProposal] = {}
        for role in frame_definition.roles:
            completed_argument: EventSemanticArgumentProposal | None = None
            rejected_target: str | None = None
            role_outcome = None
            parent_trace_id = normalization_trace.id
            for attempt_ordinal in range(2):
                role_input = _role_completion_task_input(
                    context=context,
                    trigger=trigger,
                    segment=segment,
                    local_inputs=local_inputs,
                    frame=frame_definition,
                    role=role,
                    rejected_target=rejected_target,
                )
                role_outcome = run_bounded_extraction(
                    BoundedExtractionInput(
                        source_id=context.source_id,
                        document_id=context.document_id,
                        representation_id=context.parent.representation_id,
                        context_manifest_id=role_completion_manifest.id,
                        prompt_bytes=role_completion_prompt_bytes,
                        execution_spec=_execution_spec(
                            role_completion_manifest,
                            model_runtime,
                            command.generation_parameters,
                            role_completion_schema,
                            role_input,
                        ),
                        validator_version="hybrid_event_role_completion_validator_v1",
                        task_type="hybrid_event_role_completion",
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
                role_trace = _role_completion_trace(
                    subject=subject,
                    frame=frame_definition,
                    role=role,
                    trigger=trigger,
                    segment=segment,
                    task_input=role_input,
                    prompt_bytes=role_completion_prompt_bytes,
                    schema=role_completion_schema,
                    task_id=role_outcome.extraction_task.id,
                    model_run_id=role_outcome.model_run.id,
                    model_status=role_outcome.model_run.status,
                    raw_output_sha256=role_outcome.model_run.output_digest,
                    proposal=role_proposal,
                    parent_trace_id=parent_trace_id,
                )
                traces.append(role_trace)
                normalization_traces.append(role_trace)
                parent_trace_id = role_trace.id
                if role_proposal is None:
                    if (
                        attempt_ordinal == 0
                        and role_outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
                    ):
                        rejected_target = "invalid_model_output"
                        continue
                    break
                if role_proposal.target_value is None:
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
                    reconciled = _reconcile_redundant_catalog_target(
                        role_proposal,
                        role,
                        context,
                        local_inputs,
                    )
                    if reconciled is not None:
                        completed_argument = _completed_role_argument(
                            reconciled,
                            role,
                            context,
                            segment,
                            local_inputs,
                            ledger,
                        )
                        reconciliation_trace = _role_target_reconciliation_trace(
                            subject=subject,
                            role=role,
                            trigger=trigger,
                            segment=segment,
                            original=role_proposal,
                            reconciled=reconciled,
                            parent_trace_id=role_trace.id,
                        )
                        traces.append(reconciliation_trace)
                        normalization_traces.append(reconciliation_trace)
                        break
                    if attempt_ordinal == 0:
                        rejected_target = f"{error}:{role_proposal.target_value}"
                        continue
                break
            assert role_outcome is not None
            if completed_argument is None:
                if (
                    role_outcome.model_run.status is not ModelRunStatus.SUCCEEDED
                    or role.required
                    or role.id in invalid_targets
                    or role.id in primary_arguments
                ):
                    diagnostics.append(
                        f"role_completion_unresolved:{subject.id}:{role.id}:"
                        f"{role_outcome.model_run.status.value}"
                    )
            else:
                selected_arguments[role.id] = completed_argument

        proposal = EventSemanticProposal(
            proposal.frame_id,
            tuple(
                selected_arguments[item.id]
                for item in frame_definition.roles
                if item.id in selected_arguments
            ),
            proposal.qualifiers,
            proposal.reason,
        )
        try:
            constructed = _construct_event(
                context=context,
                subject=subject,
                parent_frame=frame,
                trigger=trigger,
                segment=segment,
                local_inputs=local_inputs,
                proposal=proposal,
                task_id=outcome.extraction_task.id,
                model_run_id=outcome.model_run.id,
                normalization_traces=tuple(normalization_traces),
                ledger=ledger,
            )
        except ValueError as error:
            diagnostics.append(f"normalization_mapping_failed:{subject.id}:{error}")
            continue
        events.append(cast(EventSemanticDraft, constructed.event))
        targets.extend(constructed.targets)
        assignments.extend(constructed.assignments)
        qualifiers.extend(constructed.qualifiers)
        gaps.extend(constructed.gaps)
        statements.extend(constructed.statements)
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
                normalization_traces=tuple(normalization_traces),
                constructed=constructed,
            )
        )

        for statement in constructed.statements:
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

    if context.parent.terminal_status is HybridAtomicClaimStatus.PARTIAL:
        diagnostics.append("hp5_status:partial")
    status = HybridEventSemanticsStatus.COMPLETE
    if (
        len(events) != len(context.parent.event_subjects)
        or gaps
        or len(judgments) != len(statements)
        or context.parent.terminal_status is HybridAtomicClaimStatus.PARTIAL
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
    parent = load_hybrid_atomic_claim_preview(preview.parent_preview_id, ledger, archive)
    if (
        hashlib.sha256(canonical_hybrid_atomic_claim_preview_bytes(parent)).hexdigest()
        != preview.parent_preview_sha256
        or parent.representation_id != preview.representation_id
        or parent.paragraph_node_id != preview.paragraph_node_id
        or preview.ontology_profile_sha256 != hybrid_event_semantics_profile_sha256()
    ):
        raise ValueError("HP-6 parent or ontology lineage does not match pinned identities.")
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
    parent = load_hybrid_atomic_claim_preview(parent_id, ledger, archive)
    hp4 = load_hybrid_event_frame_preview(parent.parent_preview_id, archive)
    mentions = hybrid_extraction_preview_from_bytes(
        archive.read_hybrid_extraction_preview(parent.mention_preview_id)
    )
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
    attempts = {
        item.evidence_target_id: item
        for attempt_id in parent.evidence_validation_attempt_ids
        if (item := ledger.get_evidence_validation_attempt(attempt_id)) is not None
    }
    segment_contexts: dict[str, _SegmentContext] = {}
    for target_id in parent.evidence_target_ids:
        target = ledger.get_evidence_target(target_id)
        attempt = attempts.get(target_id)
        if target is None or attempt is None:
            raise ValueError("HP-6 parent evidence records are missing.")
        replay = verify_evidence_target(target, attempt, ledger)
        if not replay.valid:
            raise ValueError(f"HP-6 parent EvidenceTarget replay failed: {replay.error_message}")
        segment_id = next(
            (
                item_id
                for item_id, item in source_segments.items()
                if node.start_char + item.start_char == target.start_char
                and node.start_char + item.end_char == target.end_char
                and item.exact_text == target.exact_text
            ),
            None,
        )
        if segment_id is None:
            raise ValueError("HP-6 parent EvidenceTarget is not one SourceSegment.")
        segment_contexts[segment_id] = _SegmentContext(
            source_segments[segment_id], segment_id, target, attempt
        )
    frames = {item.id: item for item in hp4.frames}
    triggers = {item.id: item for item in hp4.triggers}
    candidates = {item.id: item for item in mentions.candidates}
    if any(
        item.frame_id not in frames or item.trigger_id not in triggers
        for item in parent.event_subjects
    ):
        raise ValueError("HP-6 event subjects do not match HP-4.")
    if any(
        triggers[item.trigger_id].source_segment_id not in segment_contexts
        for item in parent.event_subjects
    ):
        raise ValueError("HP-6 lacks support evidence for one event subject.")
    return _SourceContext(
        parent,
        bundle,
        mentions,
        frames,
        triggers,
        candidates,
        segment_contexts,
        document.source_id,
        document.id,
    )


def _local_inputs(
    context: _SourceContext,
    subject: EventSubjectDraft,
    segment_id: str,
) -> _LocalInputs:
    candidates = {
        f"c{ordinal}": item
        for ordinal, item in enumerate(
            sorted(
                (
                    candidate
                    for candidate in context.candidates.values()
                    if candidate.source_segment_id == segment_id
                ),
                key=lambda item: (item.start, item.end, item.id),
            ),
            start=1,
        )
    }
    siblings = {
        f"e{ordinal}": item
        for ordinal, item in enumerate(
            sorted(
                (
                    sibling
                    for sibling in context.parent.event_subjects
                    if sibling.id != subject.id
                    and context.triggers[sibling.trigger_id].source_segment_id == segment_id
                ),
                key=lambda item: (
                    context.triggers[item.trigger_id].start,
                    context.triggers[item.trigger_id].end,
                    item.id,
                ),
            ),
            start=1,
        )
    }
    return _LocalInputs(candidates, siblings)


def _construct_event(
    *,
    context: _SourceContext,
    subject: EventSubjectDraft,
    parent_frame: EventFrameDraft,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    proposal: EventSemanticProposal,
    task_id: str,
    model_run_id: str,
    normalization_traces: tuple[ExtractionStageTrace, ...],
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
    parent_claims = tuple(
        item for item in context.parent.atomic_claims if item.frame_id == parent_frame.id
    )
    primary_normalization_trace = normalization_traces[0]
    parent_trace_ids = tuple(
        sorted(
            {
                *(item.id for item in normalization_traces),
                parent_frame.trace_id,
                *(trace_id for claim in parent_claims for trace_id in claim.source_trace_ids),
            }
        )
    )
    represented_parent_candidates: set[str] = set()
    for argument in proposal.arguments:
        role = role_by_id.get(argument.frame_role_id)
        if role is None:
            raise ValueError("unknown_frame_role")
        if argument.frame_role_id in seen_roles:
            raise ValueError("repeated_frame_role")
        candidate_label = _candidate_label(argument.target_value, local_inputs.candidates)
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
        if candidate_label is not None:
            represented_parent_candidates.add(local_inputs.candidates[candidate_label].id)
        proposed_labels = tuple(
            sorted(
                {
                    claim.role_label
                    for claim in parent_claims
                    if claim.object_kind is AtomicClaimObjectKind.MENTION_CANDIDATE
                    and claim.object_reference_id == target.reference_id
                    and claim.role_label is not None
                }
            )
        )
        assignments.append(
            build_event_argument_assignment_draft(
                event_subject_id=subject.id,
                frame_id=frame_definition.id,
                target_id=target.id,
                frame_role_id=role.id,
                upper_role=role.upper_role,
                proposed_role_labels=proposed_labels,
                support_evidence_target_id=segment.support_target.id,
                source_trace_ids=parent_trace_ids,
            )
        )

    gaps: list[SemanticCoverageGap] = []
    qualifier_records: list[SemanticQualifierDraft] = []
    represented_parent_qualifiers: set[tuple[str, str]] = set()
    parent_qualifier_keys = {(item.kind, item.text) for item in parent_frame.qualifiers}
    qualifier_by_label = {
        f"q{index}": item for index, item in enumerate(parent_frame.qualifiers, start=1)
    }
    for qualifier in proposal.qualifiers:
        parent_qualifier = qualifier_by_label.get(qualifier.qualifier_label)
        if parent_qualifier is None:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.UNSUPPORTED_QUALIFIER_PROPOSAL,
                    field_value=qualifier.qualifier_label,
                    detail="Model qualifier label was not supplied by the parent frame.",
                )
            )
            continue
        target, evidence, attempt = _source_span_target(
            context, segment, parent_qualifier.text, ledger
        )
        qualifier_key = (parent_qualifier.kind, target.text)
        if qualifier_key not in parent_qualifier_keys:
            raise ValueError("parent_qualifier_source_mismatch")
        represented_parent_qualifiers.add(qualifier_key)
        evidence_records[evidence.id] = (evidence, attempt)
        qualifier_records.append(
            build_semantic_qualifier_draft(
                event_subject_id=subject.id,
                kind=cast(Literal["time", "place"], parent_qualifier.kind),
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
    if frame_definition.attribution_role_id is not None:
        attribution_assignment = next(
            (
                item
                for item in assignments
                if item.frame_role_id == frame_definition.attribution_role_id
            ),
            None,
        )
        if attribution_assignment is None:
            attribution_kind = EventAttributionKind.UNRESOLVED
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.MISSING_GOVERNED_ATTRIBUTION,
                    field_value=frame_definition.attribution_role_id,
                    detail="The governed reporting role has no source-backed target.",
                )
            )
        else:
            attribution_target = target_records[attribution_assignment.target_id]
            attribution_kind = EventAttributionKind(attribution_target.kind.value)

    parent_attribution_matches = (
        parent_frame.source_narrator_attribution
        and attribution_kind is EventAttributionKind.SOURCE_NARRATOR
    ) or (
        not parent_frame.source_narrator_attribution
        and attribution_target is not None
        and attribution_target.reference_id is not None
        and parent_frame.attribution_candidate_ids == (attribution_target.reference_id,)
    )
    if not parent_attribution_matches:
        parent_value = (
            "source_narrator"
            if parent_frame.source_narrator_attribution
            else ",".join(parent_frame.attribution_candidate_ids)
        )
        gaps.append(
            build_semantic_coverage_gap(
                event_subject_id=subject.id,
                code=SemanticCoverageGapCode.PARENT_ATTRIBUTION_DISAGREEMENT,
                field_value=parent_value,
                detail=(
                    "The open parent attribution disagrees with the governed frame "
                    "attribution policy."
                ),
            )
        )

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
    for claim in parent_claims:
        if (
            claim.object_kind is AtomicClaimObjectKind.MENTION_CANDIDATE
            and claim.object_reference_id not in represented_parent_candidates
        ):
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.OMITTED_PARENT_ARGUMENT,
                    field_value=cast(str, claim.object_reference_id),
                    detail=(
                        "Parent argument was not represented by a governed role: "
                        f"{claim.role_label}."
                    ),
                )
            )
    for qualifier in parent_frame.qualifiers:
        if (qualifier.kind, qualifier.text) not in represented_parent_qualifiers:
            gaps.append(
                build_semantic_coverage_gap(
                    event_subject_id=subject.id,
                    code=SemanticCoverageGapCode.OMITTED_PARENT_QUALIFIER,
                    field_value=f"{qualifier.kind}:{qualifier.text}",
                    detail="Parent time or place qualifier was not represented.",
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
        polarity=parent_frame.polarity.value,
        modality=parent_frame.modality.value,
        attribution_kind=attribution_kind,
        attribution_target_id=(attribution_target.id if attribution_target is not None else None),
        support_evidence_target_id=segment.support_target.id,
        normalization_task_id=task_id,
        normalization_model_run_id=model_run_id,
        normalization_trace_id=primary_normalization_trace.id,
    )
    statements = _statements(
        event,
        frame_definition,
        ordered_assignments,
        target_records,
        ordered_qualifiers,
        attribution_target,
    )
    return _ConstructedEvent(
        event,
        tuple(sorted(target_records.values(), key=lambda item: item.id)),
        ordered_assignments,
        ordered_qualifiers,
        tuple(sorted(gaps, key=lambda item: item.id)),
        statements,
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
    sibling = local_inputs.sibling_events.get(value)
    if sibling is not None:
        trigger = context.triggers[sibling.trigger_id]
        if SemanticArgumentTargetKind.EVENT_SUBJECT in allowed_target_kinds:
            return _referenced_target(
                context,
                segment,
                SemanticArgumentTargetKind.EVENT_SUBJECT,
                sibling.id,
                trigger.text,
                trigger.start,
                trigger.end,
                ledger,
            )
        if SemanticArgumentTargetKind.SOURCE_SPAN in allowed_target_kinds:
            return _source_span_target(context, segment, trigger.text, ledger)
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
    )
    return draft, target, attempt


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


def _normalization_task_input(
    *,
    context: _SourceContext,
    subject: EventSubjectDraft,
    frame: EventFrameDraft,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
) -> bytes:
    candidate_label_by_id = {
        candidate.id: label for label, candidate in local_inputs.candidates.items()
    }
    lines = [
        "task: normalize_one_event",
        f"target_trigger: {trigger.text}",
        f"open_event_label_proposal: {trigger.event_type_label}",
        f"polarity_from_parent: {frame.polarity.value}",
        f"modality_from_parent: {frame.modality.value}",
        f"source_segment: {segment.segment.exact_text}",
        f"source_before_target_trigger: {segment.segment.exact_text[: trigger.start]}",
        f"source_after_target_trigger: {segment.segment.exact_text[trigger.end :]}",
        "parent_argument_proposals:",
    ]
    lines.extend(
        " | ".join(
            (
                candidate_label_by_id.get(item.candidate_id, "not_in_source_segment"),
                item.role_label,
            )
        )
        for item in frame.arguments
    )
    lines.append("mention_candidate_catalog:")
    lines.extend(
        f"{label} | {candidate.text}" for label, candidate in local_inputs.candidates.items()
    )
    lines.append("sibling_event_catalog:")
    lines.extend(
        " | ".join(
            (
                label,
                context.triggers[item.trigger_id].text,
                context.triggers[item.trigger_id].event_type_label,
            )
        )
        for label, item in local_inputs.sibling_events.items()
    )
    lines.append("parent_qualifier_proposals:")
    lines.extend(
        f"q{index} | {item.kind} | {item.text}"
        for index, item in enumerate(frame.qualifiers, start=1)
    )
    lines.append("ontology_profile:")
    for profile_frame in HYBRID_EVENT_SEMANTICS_V1.frames:
        lines.append(f"frame | {profile_frame.id} | {profile_frame.definition}")
        lines.extend(
            " | ".join(
                (
                    "role",
                    role.id,
                    "required" if role.required else "optional",
                    ",".join(item.value for item in role.allowed_target_kinds),
                    role.upper_role.value,
                    role.definition,
                )
            )
            for role in profile_frame.roles
        )
    lines.append(f"normalize_only_target_trigger: {trigger.text}")
    return "\n".join(lines).encode()


def _role_completion_task_input(
    *,
    context: _SourceContext,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    frame: EventFrameDefinition,
    role: FrameRoleDefinition,
    rejected_target: str | None,
) -> bytes:
    lines = [
        "task: select_one_frame_role",
        f"target_trigger: {trigger.text}",
        f"selected_frame: {frame.id} | {frame.definition}",
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
    lines.extend(
        f"{label} | {candidate.text}"
        for label, candidate in local_inputs.candidates.items()
        if SemanticArgumentTargetKind.MENTION_CANDIDATE in role.allowed_target_kinds
    )
    lines.append("sibling_event_catalog:")
    lines.extend(
        " | ".join(
            (
                label,
                context.triggers[item.trigger_id].text,
                context.triggers[item.trigger_id].event_type_label,
            )
        )
        for label, item in local_inputs.sibling_events.items()
        if SemanticArgumentTargetKind.EVENT_SUBJECT in role.allowed_target_kinds
    )
    if rejected_target is not None:
        lines.append(f"rejected_previous_target: {rejected_target}")
    lines.append(f"select_only_frame_role: {role.id}")
    return "\n".join(lines).encode()


def _completed_role_argument(
    proposal: EventSemanticRoleTargetProposal | None,
    role: FrameRoleDefinition,
    context: _SourceContext,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    ledger: HybridEventSemanticsLedger,
) -> EventSemanticArgumentProposal | None:
    if proposal is None or proposal.target_value is None:
        return None
    target_value = proposal.target_value
    if (
        target_value in local_inputs.candidates
        and SemanticArgumentTargetKind.MENTION_CANDIDATE not in role.allowed_target_kinds
    ) or (
        target_value in local_inputs.sibling_events
        and SemanticArgumentTargetKind.EVENT_SUBJECT not in role.allowed_target_kinds
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


def _reconcile_redundant_catalog_target(
    proposal: EventSemanticRoleTargetProposal,
    role: FrameRoleDefinition,
    context: _SourceContext,
    local_inputs: _LocalInputs,
) -> EventSemanticRoleTargetProposal | None:
    parts = proposal.target_value.split(" | ", maxsplit=1) if proposal.target_value else []
    if len(parts) != 2:
        return None
    label, copied_text = parts
    candidate = local_inputs.candidates.get(label)
    if (
        candidate is not None
        and SemanticArgumentTargetKind.MENTION_CANDIDATE in role.allowed_target_kinds
        and _normalized_text(copied_text) == _normalized_text(candidate.text)
    ):
        return EventSemanticRoleTargetProposal(label, proposal.reason)
    sibling = local_inputs.sibling_events.get(label)
    if sibling is None or SemanticArgumentTargetKind.EVENT_SUBJECT not in role.allowed_target_kinds:
        return None
    trigger = context.triggers[sibling.trigger_id]
    if _normalized_text(copied_text) != _normalized_text(trigger.text):
        return None
    return EventSemanticRoleTargetProposal(label, proposal.reason)


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


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


def _normalization_trace(
    *,
    context: _SourceContext,
    subject: EventSubjectDraft,
    frame: EventFrameDraft,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    local_inputs: _LocalInputs,
    task_input: bytes,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    task_id: str,
    model_run_id: str,
    model_status: ModelRunStatus,
    raw_output_sha256: str | None,
    proposal: EventSemanticProposal | None,
    stage_id: str = "hybrid_event_normalization",
    parent_trace_ids: tuple[str, ...] = (),
) -> ExtractionStageTrace:
    completed = proposal is not None and model_status is ModelRunStatus.SUCCEEDED
    return build_extraction_stage_trace(
        trace_run_id=f"hp6:normalize:{subject.id}:{model_run_id}",
        ordinal=0,
        stage_id=stage_id,
        stage_version="1",
        producer_id="qwen2.5",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        parent_trace_ids=parent_trace_ids,
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
                "parent_frame": frame.model_dump(mode="json"),
                "trigger": trigger.model_dump(mode="json"),
                "local_candidates": {
                    label: item.model_dump(mode="json")
                    for label, item in local_inputs.candidates.items()
                },
                "local_sibling_events": {
                    label: item.model_dump(mode="json")
                    for label, item in local_inputs.sibling_events.items()
                },
                "model_visible_task": task_input.decode(),
            },
        ),
        output_payload={
            "model_run_status": model_status.value,
            "raw_output_sha256": raw_output_sha256,
            "parsed_proposal": _model_payload(proposal),
        },
        status=ExtractionStageStatus.COMPLETED if completed else ExtractionStageStatus.FAILED,
        diagnostics=() if completed else (f"model_run_status:{model_status.value}",),
        input_record_ids=tuple(sorted({subject.id, frame.id, trigger.id})),
        execution_record_ids=(task_id, model_run_id),
    )


def _role_completion_trace(
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
        trace_run_id=f"hp6:complete-role:{subject.id}:{role.id}:{model_run_id}",
        ordinal=0,
        stage_id="hybrid_event_role_completion",
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


def _role_target_reconciliation_trace(
    *,
    subject: EventSubjectDraft,
    role: FrameRoleDefinition,
    trigger: EventTriggerDraft,
    segment: _SegmentContext,
    original: EventSemanticRoleTargetProposal,
    reconciled: EventSemanticRoleTargetProposal,
    parent_trace_id: str,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=f"hp6:reconcile-role:{subject.id}:{role.id}:{parent_trace_id}",
        ordinal=0,
        stage_id="hybrid_event_role_target_reconciliation",
        stage_version="1",
        producer_id="kotekomi",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        parent_trace_ids=(parent_trace_id,),
        configuration={
            "rule_id": "redundant_catalog_label_text_v1",
            "policy_id": HYBRID_EVENT_SEMANTICS_POLICY_ID,
        },
        input_payload={
            "event_subject_id": subject.id,
            "frame_role": role.model_dump(mode="json"),
            "trigger": trigger.model_dump(mode="json"),
            "model_target_proposal": _model_payload(original),
        },
        output_payload={
            "reconciled_target_proposal": _model_payload(reconciled),
        },
        status=ExtractionStageStatus.COMPLETED,
        input_record_ids=tuple(sorted((subject.id, trigger.id))),
    )


def _construction_trace(
    *,
    subject: EventSubjectDraft,
    segment: _SegmentContext,
    proposal: EventSemanticProposal,
    normalization_traces: tuple[ExtractionStageTrace, ...],
    constructed: _ConstructedEvent,
) -> ExtractionStageTrace:
    return build_extraction_stage_trace(
        trace_run_id=normalization_traces[0].trace_run_id,
        ordinal=1,
        stage_id="hybrid_event_semantic_construction",
        stage_version="1",
        producer_id="kotekomi",
        source_segment_id=segment.segment_id,
        source_text_sha256=hashlib.sha256(segment.segment.exact_text.encode()).hexdigest(),
        parent_trace_ids=tuple(sorted(item.id for item in normalization_traces)),
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
    frame = next((item for item in HYBRID_EVENT_SEMANTICS_V1.frames if item.id == frame_id), None)
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
    normalization_prompt: bytes,
    normalization_schema: PinnedTaskSchema,
    role_completion_prompt: bytes,
    role_completion_schema: PinnedTaskSchema,
    support_prompt: bytes,
    support_schema: PinnedTaskSchema,
) -> dict[str, object]:
    return {
        "parent_preview_id": context.parent.id,
        "parent_preview_sha256": parent_sha256,
        "representation_id": context.parent.representation_id,
        "paragraph_node_id": context.parent.paragraph_node_id,
        "ontology_profile_id": HYBRID_EVENT_SEMANTICS_V1.id,
        "ontology_profile_sha256": hybrid_event_semantics_profile_sha256(),
        "normalization_prompt_sha256": hashlib.sha256(normalization_prompt).hexdigest(),
        "normalization_schema_sha256": normalization_schema.digest,
        "role_completion_prompt_sha256": hashlib.sha256(role_completion_prompt).hexdigest(),
        "role_completion_schema_sha256": role_completion_schema.digest,
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
