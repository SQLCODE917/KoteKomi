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
    EntityInvolvementAnswer,
    entity_involvement_answer_schema_bytes,
    parse_entity_involvement_answer,
)
from kotekomi_application.event_entity_connections import (
    EVENT_ENTITY_CONNECTION_POLICY_ID,
    EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID,
    EntityInvolvementJudgment,
    EventEntityCandidateGap,
    EventEntityConnectionCandidate,
    EventEntityConnectionDecision,
    EventEntityConnectionDraft,
    EventEntityConnectionPreview,
    EventEntityConnectionPreviewStatus,
    EventEntityMentionInput,
    build_entity_involvement_judgment,
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

BOUNDED_INVOLVEMENT_OUTPUT_TOKENS = 2


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
    candidate_gaps: tuple[EventEntityCandidateGap, ...]
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
    """Pinned finite contract for one involvement judgment."""

    schema_id = EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported entity involvement schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=entity_involvement_answer_schema_bytes(),
            output_contract_version=self.schema_id,
            parse=parse_entity_involvement_answer,
        )


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
    for gap in command.candidate_gaps:
        if (
            gap.source_segment_id != command.event.source_segment_id
            or gap.source_text_sha256 != source_digest
            or gap.mention_end > len(command.source_text)
            or command.source_text[gap.mention_start : gap.mention_end] != gap.mention_text
        ):
            raise ValueError("Connection candidate gap does not match the Event source.")
    candidates = build_event_entity_connection_candidates(
        command.event,
        command.entity_mentions,
        source_text=command.source_text,
    )
    registry: TaskSchemaRegistry = EntityInvolvementTaskSchemaRegistry()
    schema = registry.resolve(EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID)
    manifest = _build_manifest(
        command=command,
        schema=schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )
    judgments: list[EntityInvolvementJudgment] = []
    decisions: list[EventEntityConnectionDecision] = []
    drafts: list[EventEntityConnectionDraft] = []
    traces: list[ExtractionStageTrace] = []
    task_ids: list[str] = []
    run_ids: list[str] = []
    diagnostics: list[str] = []
    for candidate in candidates:
        task_input = event_entity_model_task_input(command.source_text, candidate)
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
                    _bounded_generation_parameters(command.generation_parameters),
                    schema,
                    task_input,
                ),
                validator_version="event_entity_involvement_validator_v1",
                task_type="event_entity_involvement",
                input_candidate_ids=(candidate.id,),
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
            candidate=candidate,
            manifest=manifest,
            schema=schema,
            task_input=task_input,
            model_run_status=outcome.model_run.status,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            raw_output=outcome.raw_model_output,
            parsed_answer=outcome.entity_involvement_answer,
            producer_id=model_runtime.configured_identity.name,
        )
        traces.append(trace)
        judgment = (
            build_entity_involvement_judgment(
                candidate_id=candidate.id,
                answer=outcome.entity_involvement_answer.value,
                extraction_task_id=outcome.extraction_task.id,
                model_run_id=outcome.model_run.id,
                trace_id=trace.id,
            )
            if outcome.model_run.status is ModelRunStatus.SUCCEEDED
            and outcome.entity_involvement_answer is not None
            else None
        )
        if judgment is not None:
            judgments.append(judgment)
        else:
            diagnostics.append(f"entity_involvement_failed:{candidate.id}")
        decision, draft = decide_event_entity_connection(candidate, judgment)
        decisions.append(decision)
        if draft is not None:
            drafts.append(draft)
        if decision.disposition.value == "unresolved":
            diagnostics.append(f"entity_involvement_unresolved:{candidate.id}")
    diagnostics.extend(
        f"candidate_gap:{item.id}:{item.reason.value}" for item in command.candidate_gaps
    )
    status = (
        EventEntityConnectionPreviewStatus.PARTIAL
        if diagnostics
        else EventEntityConnectionPreviewStatus.COMPLETE
    )
    preview = build_event_entity_connection_preview(
        parent_preview_id=command.parent_preview_id,
        parent_preview_sha256=command.parent_preview_sha256,
        candidate_gaps=command.candidate_gaps,
        candidates=tuple(candidates),
        judgments=tuple(judgments),
        decisions=tuple(decisions),
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
            prompt_id="event_entity_involvement_v1",
            prompt_bytes=command.prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="event_entity_involvement_context_v1",
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
) -> tuple[ExecutionSetting, ...]:
    if sum(item.key == "max_output_tokens" for item in settings) != 1:
        raise ValueError("Entity involvement requires one max_output_tokens setting.")
    return tuple(
        ExecutionSetting(
            item.key,
            BOUNDED_INVOLVEMENT_OUTPUT_TOKENS if item.key == "max_output_tokens" else item.value,
        )
        for item in settings
    )


def _judgment_trace(
    *,
    command: EventEntityConnectionCommand,
    candidate: EventEntityConnectionCandidate,
    manifest: ContextManifest,
    schema: PinnedTaskSchema,
    task_input: bytes,
    model_run_status: ModelRunStatus,
    extraction_task_id: str,
    model_run_id: str,
    raw_output: bytes | None,
    parsed_answer: EntityInvolvementAnswer | None,
    producer_id: str,
) -> ExtractionStageTrace:
    succeeded = model_run_status is ModelRunStatus.SUCCEEDED and parsed_answer is not None
    rendered_input = manifest.rendered_input + b"\n\n[task]\n" + task_input
    raw_text: str | None = None
    if raw_output is not None:
        try:
            raw_text = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            pass
    return build_extraction_stage_trace(
        trace_run_id=f"event_entity:{command.event.id}:{candidate.id}",
        ordinal=0,
        stage_id="event_entity_involvement",
        stage_version=EVENT_ENTITY_CONNECTION_POLICY_ID,
        producer_id=producer_id,
        source_segment_id=command.event.source_segment_id,
        source_text_sha256=command.event.source_text_sha256,
        input_record_ids=tuple(
            sorted(
                (
                    command.event.id,
                    candidate.id,
                    *(item.mention_candidate_id for item in candidate.source_spans),
                    *candidate.reference_decision_ids,
                )
            )
        ),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration={
            "policy_id": EVENT_ENTITY_CONNECTION_POLICY_ID,
            "prompt_sha256": hashlib.sha256(command.prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "candidate": cast(
                JsonValue,
                candidate.model_dump(mode="json"),
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
            "parsed_answer": parsed_answer.value.value if parsed_answer is not None else None,
        },
        status=ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED,
        diagnostics=() if succeeded else ("event_entity_involvement_failed",),
    )
