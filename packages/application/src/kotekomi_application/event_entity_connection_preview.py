"""Bounded model orchestration for Event-entity connection experiments."""

from __future__ import annotations

import hashlib
from base64 import b64encode
from dataclasses import dataclass
from typing import Protocol, cast

from kotekomi_domain import ModelRunStatus
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V3,
    AnalysisUnit,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ContextPlanningLedger,
    ContextTokenizer,
    build_context_manifest,
    verify_context_manifest,
)
from kotekomi_application.event_entity_connection_model_output import (
    EntityInvolvementAnswerBatch,
    entity_involvement_answer_batch_schema_bytes,
    parse_entity_involvement_answer_batch,
)
from kotekomi_application.event_entity_connections import (
    EVENT_ENTITY_CONNECTION_POLICY_ID,
    EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID,
    EntityInvolvementJudgment,
    EventEntityCandidateGap,
    EventEntityCandidateRouteKind,
    EventEntityCandidateSelection,
    EventEntityConnectionCandidate,
    EventEntityConnectionDecision,
    EventEntityConnectionDraft,
    EventEntityConnectionPreview,
    EventEntityConnectionPreviewStatus,
    EventEntityDenotationDecision,
    EventEntityGapDependency,
    EventEntityLinguisticEvidence,
    EventEntityMentionInput,
    build_entity_involvement_judgment,
    build_event_entity_candidate_routes,
    build_event_entity_connection_candidates,
    build_event_entity_connection_preview,
    canonical_event_entity_connection_preview_bytes,
    decide_event_entity_connection,
    event_entity_model_task_input,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_event_semantics import SourceGroundedEventDraft
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

BOUNDED_INVOLVEMENT_OUTPUT_TOKEN_PADDING = 2


class EventEntityConnectionLedger(StagedExtractionLedger, ContextPlanningLedger, Protocol):
    """Ledger operations required by the bounded experiment."""


class EventEntityConnectionArchive(Protocol):
    """Archive operations required by the bounded experiment."""

    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...


@dataclass(frozen=True)
class EventEntityConnectionCommand:
    """Complete caller-owned input for one source-grounded Event."""

    source_id: str
    document_id: str
    representation_id: str
    parent_preview_id: str
    parent_preview_sha256: str
    source_text: str
    event: SourceGroundedEventDraft
    entity_mentions: tuple[EventEntityMentionInput, ...]
    denotation_decisions: tuple[EventEntityDenotationDecision, ...]
    candidate_gaps: tuple[EventEntityCandidateGap, ...]
    gap_dependencies: tuple[EventEntityGapDependency, ...]
    linguistic_evidence: EventEntityLinguisticEvidence
    analysis_unit: AnalysisUnit
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]
    prompt_bytes: bytes


@dataclass(frozen=True)
class EventEntityConnectionResult:
    """Published in-memory result for one experiment Event."""

    preview: EventEntityConnectionPreview
    sha256: str


class EntityInvolvementTaskSchemaRegistry:
    """Pinned finite contract for one ordered candidate inventory."""

    schema_id = EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID

    def __init__(self, answer_count: int) -> None:
        if answer_count <= 0:
            raise ValueError("Entity involvement schema requires a positive answer count.")
        self._answer_count = answer_count

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported entity involvement schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=entity_involvement_answer_batch_schema_bytes(),
            output_contract_version=self.schema_id,
            parse=self._parse,
        )

    def _parse(self, raw_output: bytes) -> EntityInvolvementAnswerBatch:
        parsed = parse_entity_involvement_answer_batch(raw_output)
        if len(parsed.values) != self._answer_count:
            raise ValueError(
                "Entity involvement answer count does not match the ordered candidate inventory."
            )
        return parsed


def run_event_entity_connection_preview(
    command: EventEntityConnectionCommand,
    *,
    ledger: EventEntityConnectionLedger,
    archive: EventEntityConnectionArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
) -> EventEntityConnectionResult:
    """Judge every KoteKomi-owned entity candidate for one source-grounded Event."""
    source_digest = hashlib.sha256(command.source_text.encode()).hexdigest()
    if source_digest != command.event.source_text_sha256:
        raise ValueError("Connection command SourceSegment does not match its Event.")
    if (
        command.linguistic_evidence.source_segment_id != command.event.source_segment_id
        or command.linguistic_evidence.source_text_sha256 != source_digest
    ):
        raise ValueError("Connection command linguistic evidence does not match its Event.")
    selection = EventEntityCandidateSelection(
        mentions=command.entity_mentions,
        denotation_decisions=command.denotation_decisions,
        gaps=command.candidate_gaps,
        gap_dependencies=command.gap_dependencies,
    )
    for gap in selection.gaps:
        if (
            gap.source_segment_id != command.event.source_segment_id
            or gap.source_text_sha256 != source_digest
            or gap.mention_end > len(command.source_text)
            or command.source_text[gap.mention_start : gap.mention_end] != gap.mention_text
        ):
            raise ValueError("Connection candidate gap does not match the Event source.")
    candidates = build_event_entity_connection_candidates(
        command.event,
        selection.mentions,
        source_text=command.source_text,
    )
    routes = build_event_entity_candidate_routes(
        source_text=command.source_text,
        candidates=candidates,
        linguistic_evidence=command.linguistic_evidence,
    )
    model_pairs = tuple(
        (candidate, route)
        for candidate, route in zip(candidates, routes, strict=True)
        if route.route is EventEntityCandidateRouteKind.MODEL_JUDGMENT
    )
    judgments: list[EntityInvolvementJudgment] = []
    decisions_by_candidate: dict[str, EventEntityConnectionDecision] = {}
    drafts: list[EventEntityConnectionDraft] = []
    traces: list[ExtractionStageTrace] = []
    task_ids: list[str] = []
    run_ids: list[str] = []
    diagnostics: list[str] = []
    for candidate, route in zip(candidates, routes, strict=True):
        if route.route is EventEntityCandidateRouteKind.DETERMINISTIC_NOT_CONNECTED:
            decision, _ = decide_event_entity_connection(candidate, route, None)
            decisions_by_candidate[candidate.id] = decision
    if model_pairs:
        model_candidates = tuple(item[0] for item in model_pairs)
        registry: TaskSchemaRegistry = EntityInvolvementTaskSchemaRegistry(len(model_candidates))
        schema = registry.resolve(EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID)
        manifest = _build_manifest(
            command=command,
            schema=schema,
            ledger=ledger,
            tokenizer=tokenizer,
        )
        task_input = event_entity_model_task_input(command.source_text, model_candidates)
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=command.source_id,
                document_id=command.document_id,
                representation_id=command.representation_id,
                context_manifest_id=manifest.id,
                prompt_bytes=command.prompt_bytes,
                execution_spec=_execution_spec(
                    manifest,
                    model_runtime,
                    _bounded_generation_parameters(
                        command.generation_parameters,
                        answer_count=len(model_candidates),
                    ),
                    schema,
                    task_input,
                ),
                validator_version="event_entity_involvement_validator_v3",
                task_type="event_entity_contrastive_involvement",
                input_candidate_ids=tuple(item.id for item in model_candidates),
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
        trace = _judgment_trace(
            command=command,
            candidates=model_candidates,
            manifest=manifest,
            schema=schema,
            task_input=task_input,
            model_run_status=outcome.model_run.status,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            raw_output=outcome.raw_model_output,
            parsed_answers=outcome.entity_involvement_answer_batch,
            producer_id=model_runtime.configured_identity.name,
        )
        traces.append(trace)
        parsed_values = (
            outcome.entity_involvement_answer_batch.values
            if outcome.model_run.status is ModelRunStatus.SUCCEEDED
            and outcome.entity_involvement_answer_batch is not None
            else None
        )
        if parsed_values is None:
            diagnostics.append("entity_involvement_batch_failed")
        for ordinal, (candidate, route) in enumerate(model_pairs):
            judgment = (
                build_entity_involvement_judgment(
                    candidate_id=candidate.id,
                    answer=parsed_values[ordinal],
                    extraction_task_id=outcome.extraction_task.id,
                    model_run_id=outcome.model_run.id,
                    trace_id=trace.id,
                )
                if parsed_values is not None
                else None
            )
            if judgment is not None:
                judgments.append(judgment)
            else:
                diagnostics.append(f"entity_involvement_failed:{candidate.id}")
            decision, draft = decide_event_entity_connection(candidate, route, judgment)
            decisions_by_candidate[candidate.id] = decision
            if draft is not None:
                drafts.append(draft)
            if decision.disposition.value == "unresolved":
                diagnostics.append(f"entity_involvement_unresolved:{candidate.id}")
    decisions = tuple(decisions_by_candidate[item.id] for item in candidates)
    diagnostics.extend(f"candidate_gap:{item.id}:{item.reason.value}" for item in selection.gaps)
    status = (
        EventEntityConnectionPreviewStatus.PARTIAL
        if diagnostics
        else EventEntityConnectionPreviewStatus.COMPLETE
    )
    preview = build_event_entity_connection_preview(
        parent_preview_id=command.parent_preview_id,
        parent_preview_sha256=command.parent_preview_sha256,
        denotation_decisions=selection.denotation_decisions,
        candidate_gaps=selection.gaps,
        gap_dependencies=selection.gap_dependencies,
        candidates=tuple(candidates),
        routes=routes,
        judgments=tuple(judgments),
        decisions=decisions,
        drafts=tuple(drafts),
        traces=tuple(traces),
        extraction_task_ids=tuple(task_ids),
        model_run_ids=tuple(run_ids),
        terminal_status=status,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    payload = canonical_event_entity_connection_preview_bytes(preview)
    return EventEntityConnectionResult(preview, hashlib.sha256(payload).hexdigest())


def _build_manifest(
    *,
    command: EventEntityConnectionCommand,
    schema: PinnedTaskSchema,
    ledger: EventEntityConnectionLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=command.analysis_unit,
            model_profile=command.model_profile,
            prompt_id="event_entity_involvement_v5",
            prompt_bytes=command.prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="event_entity_involvement_context_v5",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Event entity ContextManifest is not ready: "
            f"{planning.manifest.blocked_reason or planning.manifest.status.value}"
        )
    verify_context_manifest(
        planning.manifest.id,
        ledger,
        tokenizer,
        command.prompt_bytes,
        schema.canonical_schema_bytes,
    )
    return planning.manifest


def _execution_spec(
    manifest: ContextManifest,
    runtime: ModelTaskRuntime,
    generation_parameters: tuple[ExecutionSetting, ...],
    schema: PinnedTaskSchema,
    task_input: bytes,
) -> ModelExecutionSpec:
    rendered = manifest.rendered_input + b"\n\n[task]\n" + task_input
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
        rendered_input_digest=hashlib.sha256(rendered).hexdigest(),
        output_contract_version=schema.output_contract_version,
    )


def _bounded_generation_parameters(
    settings: tuple[ExecutionSetting, ...],
    *,
    answer_count: int,
) -> tuple[ExecutionSetting, ...]:
    if sum(item.key == "max_output_tokens" for item in settings) != 1:
        raise ValueError("Entity involvement requires one max_output_tokens setting.")
    configured_limit = next(item.value for item in settings if item.key == "max_output_tokens")
    if type(configured_limit) is not int or configured_limit <= 0:
        raise ValueError("Entity involvement requires a positive configured output limit.")
    task_limit = answer_count + BOUNDED_INVOLVEMENT_OUTPUT_TOKEN_PADDING
    if task_limit > configured_limit:
        raise ValueError("Entity involvement answer vector exceeds the configured output limit.")
    return tuple(
        ExecutionSetting(
            item.key,
            task_limit if item.key == "max_output_tokens" else item.value,
        )
        for item in settings
    )


def _judgment_trace(
    *,
    command: EventEntityConnectionCommand,
    candidates: tuple[EventEntityConnectionCandidate, ...],
    manifest: ContextManifest,
    schema: PinnedTaskSchema,
    task_input: bytes,
    model_run_status: ModelRunStatus,
    extraction_task_id: str,
    model_run_id: str,
    raw_output: bytes | None,
    parsed_answers: EntityInvolvementAnswerBatch | None,
    producer_id: str,
) -> ExtractionStageTrace:
    succeeded = model_run_status is ModelRunStatus.SUCCEEDED and parsed_answers is not None
    rendered_input = manifest.rendered_input + b"\n\n[task]\n" + task_input
    raw_text: str | None = None
    if raw_output is not None:
        try:
            raw_text = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            pass
    return build_extraction_stage_trace(
        trace_run_id=f"event_entity:{command.event.id}",
        ordinal=0,
        stage_id="event_entity_involvement",
        stage_version=EVENT_ENTITY_CONNECTION_POLICY_ID,
        producer_id=producer_id,
        source_segment_id=command.event.source_segment_id,
        source_text_sha256=command.event.source_text_sha256,
        input_record_ids=tuple(
            sorted(
                {
                    command.event.id,
                    *(candidate.id for candidate in candidates),
                    *(
                        item.mention_candidate_id
                        for candidate in candidates
                        for item in candidate.source_spans
                    ),
                    *(
                        reference_id
                        for candidate in candidates
                        for reference_id in candidate.reference_decision_ids
                    ),
                }
            )
        ),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration={
            "policy_id": EVENT_ENTITY_CONNECTION_POLICY_ID,
            "prompt_sha256": hashlib.sha256(command.prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "candidates": cast(
                JsonValue,
                [candidate.model_dump(mode="json") for candidate in candidates],
            ),
            "model_visible_task": task_input.decode("utf-8"),
            "exact_model_input": rendered_input.decode("utf-8"),
            "exact_model_input_sha256": hashlib.sha256(rendered_input).hexdigest(),
        },
        output_payload={
            "model_run_id": model_run_id,
            "model_run_status": model_run_status.value,
            "raw_output_base64": (
                b64encode(raw_output).decode("ascii") if raw_output is not None else None
            ),
            "raw_output_text": raw_text,
            "raw_output_sha256": (
                hashlib.sha256(raw_output).hexdigest() if raw_output is not None else None
            ),
            "parsed_answers": (
                "".join(item.value for item in parsed_answers.values)
                if parsed_answers is not None
                else None
            ),
        },
        status=ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED,
        diagnostics=() if succeeded else ("event_entity_involvement_failed",),
    )
