"""Bounded model orchestration for competitive Event attachment."""

from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from dataclasses import dataclass
from typing import Protocol

from kotekomi_domain import ModelRunStatus

from kotekomi_application.competitive_event_attachment import (
    COMPETITIVE_ATTACHMENT_TASK_RENDERER_ID,
    CompetitiveAttachmentDecision,
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentEventOrder,
    CompetitiveAttachmentMatrix,
    build_competitive_attachment_decision,
    canonicalize_competitive_attachment_answer,
    competitive_attachment_model_task_input,
    competitive_attachment_task_event_options,
    complete_competitive_attachment_matrix,
)
from kotekomi_application.competitive_event_attachment_model_output import (
    CompetitiveAttachmentAnswer,
    CompetitiveAttachmentAnswerKind,
    competitive_attachment_answer_schema_bytes,
    parse_competitive_attachment_answer,
)
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
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
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

COMPETITIVE_ATTACHMENT_POLICY_ID = "competitive_event_attachment_v1"
COMPETITIVE_ATTACHMENT_SCHEMA_ID = "competitive_event_attachment_labels_v1"
COMPETITIVE_ATTACHMENT_PROMPT_ID = "competitive_event_attachment_v1"


class CompetitiveAttachmentLedger(StagedExtractionLedger, ContextPlanningLedger, Protocol):
    """Ledger operations needed by the experimental attachment use case."""


class CompetitiveAttachmentArchive(Protocol):
    """Archive operation needed to retain exact raw model output."""

    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...


@dataclass(frozen=True)
class CompetitiveAttachmentCommand:
    """Complete caller-owned input for one SourceSegment matrix."""

    source_id: str
    document_id: str
    representation_id: str
    source_text: str
    matrix: CompetitiveAttachmentMatrix
    analysis_unit: AnalysisUnit
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]
    prompt_bytes: bytes
    prompt_id: str = COMPETITIVE_ATTACHMENT_PROMPT_ID
    event_order: CompetitiveAttachmentEventOrder = CompetitiveAttachmentEventOrder.SOURCE


@dataclass(frozen=True)
class CompetitiveAttachmentResult:
    """Published derived evidence for one competitive matrix."""

    matrix: CompetitiveAttachmentMatrix
    traces: tuple[ExtractionStageTrace, ...]
    extraction_task_ids: tuple[str, ...]
    model_run_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]
    sha256: str


class CompetitiveAttachmentTaskSchemaRegistry:
    """Invocation-bound finite Event-label contract."""

    schema_id = COMPETITIVE_ATTACHMENT_SCHEMA_ID

    def __init__(self, event_labels: tuple[str, ...]) -> None:
        self._event_labels = event_labels

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported competitive attachment schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=competitive_attachment_answer_schema_bytes(self._event_labels),
            output_contract_version=self.schema_id,
            parse=lambda payload: parse_competitive_attachment_answer(
                payload,
                allowed_event_labels=self._event_labels,
            ),
        )


def run_competitive_event_attachment(
    command: CompetitiveAttachmentCommand,
    *,
    ledger: CompetitiveAttachmentLedger,
    archive: CompetitiveAttachmentArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
) -> CompetitiveAttachmentResult:
    """Judge every exact candidate against all co-occurring Event occurrences."""
    if command.matrix.decisions:
        raise ValueError("Competitive Attachment execution requires an unexecuted matrix.")
    source_digest = hashlib.sha256(command.source_text.encode()).hexdigest()
    if source_digest != command.matrix.source_text_sha256:
        raise ValueError("Competitive Attachment source changed after matrix construction.")
    task_event_options = competitive_attachment_task_event_options(
        command.matrix.event_options,
        command.event_order,
    )
    labels = tuple(item.label for item in task_event_options)
    registry: TaskSchemaRegistry = CompetitiveAttachmentTaskSchemaRegistry(labels)
    schema = registry.resolve(COMPETITIVE_ATTACHMENT_SCHEMA_ID)
    manifest = _build_manifest(command, schema, ledger, tokenizer)
    decisions: list[CompetitiveAttachmentDecision] = []
    traces: list[ExtractionStageTrace] = []
    task_ids: list[str] = []
    run_ids: list[str] = []
    diagnostics: list[str] = []
    for ordinal, candidate in enumerate(command.matrix.candidates):
        task_input = competitive_attachment_model_task_input(
            source_text=command.source_text,
            candidate=candidate,
            event_options=task_event_options,
        )
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=command.source_id,
                document_id=command.document_id,
                representation_id=command.representation_id,
                context_manifest_id=manifest.id,
                prompt_bytes=command.prompt_bytes,
                execution_spec=_execution_spec(
                    manifest=manifest,
                    runtime=model_runtime,
                    generation_parameters=_bounded_generation_parameters(
                        command.generation_parameters,
                        event_count=len(labels),
                    ),
                    schema=schema,
                    task_input=task_input,
                ),
                validator_version="competitive_event_attachment_validator_v1",
                task_type="competitive_event_attachment",
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
        task_answer = (
            outcome.competitive_attachment_answer
            if outcome.model_run.status is ModelRunStatus.SUCCEEDED
            else None
        )
        status, diagnostic = _decision_status(outcome.model_run.status, task_answer)
        canonical_answer = (
            canonicalize_competitive_attachment_answer(
                task_answer,
                task_event_options=task_event_options,
                canonical_event_options=command.matrix.event_options,
            )
            if task_answer is not None
            else None
        )
        trace = _attachment_trace(
            command=command,
            candidate_id=candidate.id,
            manifest=manifest,
            schema=schema,
            task_input=task_input,
            model_run_status=outcome.model_run.status,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            raw_output=outcome.raw_model_output,
            answer=task_answer,
            producer_id=model_runtime.configured_identity.name,
            ordinal=ordinal,
            diagnostic=diagnostic,
        )
        traces.append(trace)
        decisions.append(
            build_competitive_attachment_decision(
                candidate=candidate,
                event_options=command.matrix.event_options,
                status=status,
                answer=canonical_answer,
                extraction_task_id=outcome.extraction_task.id,
                model_run_id=outcome.model_run.id,
                trace_id=trace.id,
                raw_output=outcome.raw_model_output,
                diagnostic_code=diagnostic,
            )
        )
        if diagnostic is not None:
            diagnostics.append(f"{diagnostic}:{candidate.id}")
    completed = complete_competitive_attachment_matrix(command.matrix, tuple(decisions))
    digest = competitive_attachment_result_sha256(
        completed,
        tuple(traces),
        tuple(sorted(diagnostics)),
    )
    return CompetitiveAttachmentResult(
        matrix=completed,
        traces=tuple(traces),
        extraction_task_ids=tuple(task_ids),
        model_run_ids=tuple(run_ids),
        diagnostics=tuple(sorted(diagnostics)),
        sha256=digest,
    )


def competitive_attachment_result_sha256(
    matrix: CompetitiveAttachmentMatrix,
    traces: tuple[ExtractionStageTrace, ...],
    diagnostics: tuple[str, ...],
) -> str:
    """Digest the complete derived result evidence."""
    payload = {
        "diagnostics": list(diagnostics),
        "matrix": matrix.model_dump(mode="json"),
        "traces": [item.model_dump(mode="json") for item in traces],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _build_manifest(
    command: CompetitiveAttachmentCommand,
    schema: PinnedTaskSchema,
    ledger: CompetitiveAttachmentLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=command.analysis_unit,
            model_profile=command.model_profile,
            prompt_id=command.prompt_id,
            prompt_bytes=command.prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="competitive_event_attachment_context_v1",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Competitive Attachment ContextManifest is not ready: "
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
    *,
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
    event_count: int,
) -> tuple[ExecutionSetting, ...]:
    if sum(item.key == "max_output_tokens" for item in settings) != 1:
        raise ValueError("Competitive Attachment requires one max_output_tokens setting.")
    configured = next(item.value for item in settings if item.key == "max_output_tokens")
    task_limit = 2 * event_count + 3
    if type(configured) is not int or configured < task_limit:
        raise ValueError("Competitive Attachment answer exceeds configured output limit.")
    return tuple(
        ExecutionSetting(
            item.key,
            task_limit if item.key == "max_output_tokens" else item.value,
        )
        for item in settings
    )


def _decision_status(
    model_status: ModelRunStatus,
    answer: CompetitiveAttachmentAnswer | None,
) -> tuple[CompetitiveAttachmentDecisionStatus, str | None]:
    if model_status is ModelRunStatus.SUCCEEDED and answer is not None:
        if answer.kind is CompetitiveAttachmentAnswerKind.UNCLEAR:
            return CompetitiveAttachmentDecisionStatus.UNCLEAR, "model_unclear"
        return CompetitiveAttachmentDecisionStatus.COMPLETE, None
    if model_status is ModelRunStatus.INPUT_BLOCKED:
        return (
            CompetitiveAttachmentDecisionStatus.CONTEXT_BUDGET_BLOCKED,
            "context_budget_blocked",
        )
    if model_status is ModelRunStatus.INVALID_OUTPUT:
        return CompetitiveAttachmentDecisionStatus.INVALID_OUTPUT, "invalid_model_output"
    return CompetitiveAttachmentDecisionStatus.MODEL_FAILED, "model_execution_failed"


def _attachment_trace(
    *,
    command: CompetitiveAttachmentCommand,
    candidate_id: str,
    manifest: ContextManifest,
    schema: PinnedTaskSchema,
    task_input: bytes,
    model_run_status: ModelRunStatus,
    extraction_task_id: str,
    model_run_id: str,
    raw_output: bytes | None,
    answer: CompetitiveAttachmentAnswer | None,
    producer_id: str,
    ordinal: int,
    diagnostic: str | None,
) -> ExtractionStageTrace:
    rendered = manifest.rendered_input + b"\n\n[task]\n" + task_input
    raw_text: str | None = None
    if raw_output is not None:
        try:
            raw_text = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            pass
    succeeded = model_run_status is ModelRunStatus.SUCCEEDED and answer is not None
    return build_extraction_stage_trace(
        trace_run_id=f"competitive_attachment:{command.matrix.id}",
        ordinal=ordinal,
        stage_id="competitive_event_attachment",
        stage_version=COMPETITIVE_ATTACHMENT_POLICY_ID,
        producer_id=producer_id,
        source_segment_id=command.matrix.source_segment_id,
        source_text_sha256=command.matrix.source_text_sha256,
        input_record_ids=tuple(
            sorted(
                (
                    candidate_id,
                    *(item.id for item in command.matrix.event_options),
                )
            )
        ),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration={
            "policy_id": COMPETITIVE_ATTACHMENT_POLICY_ID,
            "prompt_sha256": hashlib.sha256(command.prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
            "task_renderer_id": COMPETITIVE_ATTACHMENT_TASK_RENDERER_ID,
        },
        input_payload={
            "candidate_id": candidate_id,
            "model_visible_task": task_input.decode("utf-8"),
            "exact_model_input": rendered.decode("utf-8"),
            "exact_model_input_sha256": hashlib.sha256(rendered).hexdigest(),
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
            "answer_kind": answer.kind.value if answer is not None else None,
            "event_labels": list(answer.event_labels) if answer is not None else [],
        },
        status=ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED,
        diagnostics=(diagnostic,) if diagnostic is not None else (),
    )
