"""Bounded model orchestration for one competitive Attachment Pool Edge."""

from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from dataclasses import dataclass
from typing import Protocol

from kotekomi_domain import ModelRunStatus
from kotekomi_domain.models import JsonValue

from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterTask,
    attachment_edge_filter_model_task_input,
    attachment_edge_filter_schema_bytes,
    parse_attachment_edge_filter_answer,
)
from kotekomi_application.competitive_attachment_partwise_residual_ownership import (
    ATTACHMENT_REMAINDER_PART_RENDERER_ID,
    attachment_remainder_part_model_task_input,
)
from kotekomi_application.competitive_attachment_remainder_cardinality_ablation import (
    ATTACHMENT_SPLIT_REMAINDER_RENDERER_ID,
    attachment_split_remainder_model_task_input,
)
from kotekomi_application.competitive_attachment_remainder_enumeration_isolation import (
    ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID,
    attachment_filtered_remainder_model_task_input,
)
from kotekomi_application.competitive_attachment_residual_ownership import (
    ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID,
    attachment_residual_remainder_model_task_input,
    build_attachment_residual_ownership_task,
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
from kotekomi_application.source_grounded_proposition_model_output import (
    PropositionFragmentAnswer,
    PropositionFragmentAnswerValue,
)
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    ExecutionSetting,
    ModelExecutionReceipt,
    ModelExecutionSpec,
    ModelRunIdFactory,
    ModelTaskRuntime,
    PinnedTaskSchema,
    StagedExtractionLedger,
    TaskSchemaRegistry,
    model_execution_receipt_from_payload,
    run_bounded_extraction,
)

ATTACHMENT_EDGE_FILTER_POLICY_ID = "competitive_attachment_edge_filter_v1"
ATTACHMENT_EDGE_FILTER_PROMPT_ID = "competitive_attachment_edge_filter_v1"
ATTACHMENT_EDGE_FILTER_SCHEMA_ID = "competitive_attachment_edge_filter_answer_v1"
ATTACHMENT_EDGE_FILTER_RENDERER_ID = "competitive_attachment_edge_filter_task_v1"
ATTACHMENT_EDGE_FILTER_MAX_OUTPUT_TOKENS = 3


class AttachmentEdgeFilterLedger(StagedExtractionLedger, ContextPlanningLedger, Protocol):
    """Ledger operations needed by the experimental Edge Filter."""


class AttachmentEdgeFilterArchive(Protocol):
    """Archive operation needed to retain exact raw model output."""

    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...


@dataclass(frozen=True)
class AttachmentEdgeFilterCommand:
    """Caller-owned input for one exact Target Edge judgment."""

    source_id: str
    document_id: str
    representation_id: str
    task: AttachmentEdgeFilterTask
    analysis_unit: AnalysisUnit
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]
    prompt_bytes: bytes
    prompt_id: str = ATTACHMENT_EDGE_FILTER_PROMPT_ID
    task_renderer_id: str = ATTACHMENT_EDGE_FILTER_RENDERER_ID
    remainder_part_number: int | None = None
    effective_max_output_tokens: int = ATTACHMENT_EDGE_FILTER_MAX_OUTPUT_TOKENS


@dataclass(frozen=True)
class AttachmentEdgeFilterResult:
    """One typed decision plus complete model evidence."""

    decision: AttachmentEdgeFilterDecision
    trace: ExtractionStageTrace
    extraction_task_id: str
    model_run_id: str
    raw_output: bytes | None
    execution_receipt: ModelExecutionReceipt | None
    sha256: str


class AttachmentEdgeFilterTaskSchemaRegistry:
    """Pinned finite Y/N/U contract for one Target Edge."""

    schema_id = ATTACHMENT_EDGE_FILTER_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported Attachment Edge Filter schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=attachment_edge_filter_schema_bytes(),
            output_contract_version=self.schema_id,
            parse=_parse_runtime_answer,
        )


def run_attachment_edge_filter(
    command: AttachmentEdgeFilterCommand,
    *,
    ledger: AttachmentEdgeFilterLedger,
    archive: AttachmentEdgeFilterArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
) -> AttachmentEdgeFilterResult:
    """Judge one Pool Edge without creating canonical state."""
    registry: TaskSchemaRegistry = AttachmentEdgeFilterTaskSchemaRegistry()
    schema = registry.resolve(ATTACHMENT_EDGE_FILTER_SCHEMA_ID)
    manifest = _build_manifest(command, schema, ledger, tokenizer)
    task_input = _task_input(command)
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
                generation_parameters=attachment_edge_filter_generation_parameters(
                    command.generation_parameters,
                    effective_max_output_tokens=command.effective_max_output_tokens,
                ),
                schema=schema,
                task_input=task_input,
            ),
            validator_version="competitive_attachment_edge_filter_validator_v1",
            task_type="competitive_attachment_edge_filter",
            input_candidate_ids=(
                command.task.candidate.id,
                command.task.edge.source_grounded_event_id,
            ),
            task_local_input=task_input,
        ),
        ledger,
        archive,
        model_runtime,
        model_run_id_factory,
        tokenizer,
        registry,
    )
    answer = outcome.proposition_fragment_answer
    status, diagnostic = _decision_status(outcome.model_run.status, answer)
    mapped_answer = (
        AttachmentEdgeFilterAnswerValue(answer.value.value) if answer is not None else None
    )
    trace = _edge_filter_trace(
        command=command,
        manifest=manifest,
        schema=schema,
        task_input=task_input,
        model_run_status=outcome.model_run.status,
        extraction_task_id=outcome.extraction_task.id,
        model_run_id=outcome.model_run.id,
        raw_output=outcome.raw_model_output,
        answer=mapped_answer,
        producer_id=model_runtime.configured_identity.name,
        diagnostic=diagnostic,
    )
    decision = AttachmentEdgeFilterDecision(
        task_id=command.task.task_id,
        edge_id=command.task.edge.id,
        status=status,
        answer=mapped_answer,
        retained=mapped_answer is AttachmentEdgeFilterAnswerValue.YES,
        unresolved=status is not AttachmentEdgeFilterDecisionStatus.COMPLETE,
        extraction_task_id=outcome.extraction_task.id,
        model_run_id=outcome.model_run.id,
        trace_id=trace.id,
        raw_output_sha256=(
            hashlib.sha256(outcome.raw_model_output).hexdigest()
            if outcome.raw_model_output is not None
            else None
        ),
        diagnostic_code=diagnostic,
    )
    digest = attachment_edge_filter_result_sha256(decision, trace)
    return AttachmentEdgeFilterResult(
        decision=decision,
        trace=trace,
        extraction_task_id=outcome.extraction_task.id,
        model_run_id=outcome.model_run.id,
        raw_output=outcome.raw_model_output,
        execution_receipt=(
            model_execution_receipt_from_payload(outcome.model_run.execution_receipt)
            if outcome.model_run.execution_receipt is not None
            else None
        ),
        sha256=digest,
    )


def attachment_edge_filter_result_sha256(
    decision: AttachmentEdgeFilterDecision,
    trace: ExtractionStageTrace,
) -> str:
    """Digest one complete derived Edge Filter result."""
    return hashlib.sha256(
        json.dumps(
            {
                "decision": decision.model_dump(mode="json"),
                "trace": trace.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _task_input(command: AttachmentEdgeFilterCommand) -> bytes:
    if command.task_renderer_id == ATTACHMENT_EDGE_FILTER_RENDERER_ID:
        if command.remainder_part_number is not None:
            raise ValueError("The default Edge Filter renderer cannot select a Remainder Part.")
        return attachment_edge_filter_model_task_input(command.task)
    if command.task_renderer_id == ATTACHMENT_RESIDUAL_REMAINDER_RENDERER_ID:
        if command.remainder_part_number is not None:
            raise ValueError("The Candidate Remainder renderer cannot select one part.")
        return attachment_residual_remainder_model_task_input(command.task)
    if command.task_renderer_id == ATTACHMENT_FILTERED_REMAINDER_RENDERER_ID:
        if command.remainder_part_number is not None:
            raise ValueError("The Filtered Remainder renderer cannot select one part.")
        task = build_attachment_residual_ownership_task(command.task)
        return attachment_filtered_remainder_model_task_input(task)
    if command.task_renderer_id == ATTACHMENT_SPLIT_REMAINDER_RENDERER_ID:
        if command.remainder_part_number is not None:
            raise ValueError("The Split Remainder renderer cannot select one part.")
        task = build_attachment_residual_ownership_task(command.task)
        return attachment_split_remainder_model_task_input(task)
    if command.task_renderer_id == ATTACHMENT_REMAINDER_PART_RENDERER_ID:
        if command.remainder_part_number is None:
            raise ValueError("The Remainder Part renderer requires one part number.")
        return attachment_remainder_part_model_task_input(
            command.task,
            command.remainder_part_number,
        )
    raise ValueError(f"Unsupported Attachment Edge Filter renderer: {command.task_renderer_id}")


def _parse_runtime_answer(payload: bytes) -> PropositionFragmentAnswer:
    value = parse_attachment_edge_filter_answer(payload)
    return PropositionFragmentAnswer(PropositionFragmentAnswerValue(value.value))


def _build_manifest(
    command: AttachmentEdgeFilterCommand,
    schema: PinnedTaskSchema,
    ledger: AttachmentEdgeFilterLedger,
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
            renderer_version="competitive_attachment_edge_filter_context_v1",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Attachment Edge Filter ContextManifest is not ready: "
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


def attachment_edge_filter_generation_parameters(
    settings: tuple[ExecutionSetting, ...],
    *,
    effective_max_output_tokens: int = ATTACHMENT_EDGE_FILTER_MAX_OUTPUT_TOKENS,
) -> tuple[ExecutionSetting, ...]:
    """Return the effective settings for the finite Y/N/U task contract."""
    if type(effective_max_output_tokens) is not int or effective_max_output_tokens < 1:
        raise ValueError("Attachment Edge Filter output-token limit must be positive.")
    if sum(item.key == "max_output_tokens" for item in settings) != 1:
        raise ValueError("Attachment Edge Filter requires one max_output_tokens setting.")
    configured = next(item.value for item in settings if item.key == "max_output_tokens")
    if type(configured) is not int or configured < effective_max_output_tokens:
        raise ValueError(
            "Attachment Edge Filter configured output ceiling is below its task limit."
        )
    return tuple(
        ExecutionSetting(
            item.key,
            (effective_max_output_tokens if item.key == "max_output_tokens" else item.value),
        )
        for item in settings
    )


def _decision_status(
    model_status: ModelRunStatus,
    answer: PropositionFragmentAnswer | None,
) -> tuple[AttachmentEdgeFilterDecisionStatus, str | None]:
    if model_status is ModelRunStatus.SUCCEEDED and answer is not None:
        if answer.value is PropositionFragmentAnswerValue.UNCERTAIN:
            return AttachmentEdgeFilterDecisionStatus.UNCLEAR, "model_unclear"
        return AttachmentEdgeFilterDecisionStatus.COMPLETE, None
    if model_status is ModelRunStatus.INPUT_BLOCKED:
        return AttachmentEdgeFilterDecisionStatus.INPUT_BLOCKED, "context_budget_blocked"
    if model_status is ModelRunStatus.INVALID_OUTPUT:
        return AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT, "invalid_model_output"
    return AttachmentEdgeFilterDecisionStatus.MODEL_FAILED, "model_execution_failed"


def _edge_filter_trace(
    *,
    command: AttachmentEdgeFilterCommand,
    manifest: ContextManifest,
    schema: PinnedTaskSchema,
    task_input: bytes,
    model_run_status: ModelRunStatus,
    extraction_task_id: str,
    model_run_id: str,
    raw_output: bytes | None,
    answer: AttachmentEdgeFilterAnswerValue | None,
    producer_id: str,
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
    configuration: dict[str, JsonValue] = {
        "policy_id": ATTACHMENT_EDGE_FILTER_POLICY_ID,
        "prompt_sha256": hashlib.sha256(command.prompt_bytes).hexdigest(),
        "schema_sha256": schema.digest,
        "task_renderer_id": command.task_renderer_id,
    }
    input_payload: dict[str, JsonValue] = {
        "edge_id": command.task.edge.id,
        "task_fingerprint": command.task.task_fingerprint,
        "model_visible_task": task_input.decode("utf-8"),
        "exact_model_input": rendered.decode("utf-8"),
        "exact_model_input_sha256": hashlib.sha256(rendered).hexdigest(),
    }
    if command.remainder_part_number is not None:
        configuration["remainder_part_number"] = command.remainder_part_number
        input_payload["remainder_part_number"] = command.remainder_part_number
    return build_extraction_stage_trace(
        trace_run_id=f"attachment_edge_filter:{command.task.task_id}",
        ordinal=0,
        stage_id="competitive_attachment_edge_filter",
        stage_version=ATTACHMENT_EDGE_FILTER_POLICY_ID,
        producer_id=producer_id,
        source_segment_id=command.task.edge.source_segment_id,
        source_text_sha256=command.task.edge.source_text_sha256,
        input_record_ids=tuple(
            sorted(
                (
                    command.task.edge.id,
                    command.task.candidate.id,
                    *(item.id for item in command.task.event_options),
                )
            )
        ),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration=configuration,
        input_payload=input_payload,
        output_payload={
            "model_run_id": model_run_id,
            "model_run_status": model_run_status.value,
            "raw_output_base64": (
                b64encode(raw_output).decode("ascii") if raw_output is not None else None
            ),
            "raw_output_text": raw_text,
            "answer": answer.value if answer is not None else None,
            "diagnostic_code": diagnostic,
        },
        status=(ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED),
        diagnostics=(diagnostic,) if diagnostic is not None else (),
    )
