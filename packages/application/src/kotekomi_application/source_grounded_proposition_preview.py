"""Bounded model orchestration for source-grounded proposition scope."""

from __future__ import annotations

import hashlib
import json
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
from kotekomi_application.event_entity_connections import (
    EventEntityConnectionCandidate,
    EventEntityLinguisticEvidence,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_event_semantics import SourceGroundedEventDraft
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft
from kotekomi_application.source_grounded_proposition_model_output import (
    PropositionFragmentAnswer,
    PropositionFragmentAnswerValue,
    parse_proposition_fragment_answer,
    proposition_fragment_answer_schema_bytes,
)
from kotekomi_application.source_grounded_proposition_scope import (
    PropositionFragmentCandidate,
    PropositionFragmentDecision,
    PropositionFragmentDisposition,
    PropositionFragmentReason,
    PropositionFragmentRoute,
    PropositionFragmentTaskInput,
    PropositionFragmentTaskInputStatus,
    SourceGroundedPropositionScope,
    build_proposition_fragment_candidates,
    build_proposition_fragment_decision,
    build_source_grounded_proposition_scope,
    marker_free_proposition_fragment_model_task_input,
    proposition_fragment_model_task_input,
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

PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID = "proposition_fragment_membership_text_v2"
PROPOSITION_SCOPE_POLICY_ID = "source_grounded_proposition_scope_v1"
PROPOSITION_SCOPE_OUTPUT_TOKEN_LIMIT = 3
MARKER_FREE_PROPOSITION_PROMPT_ID = "source_grounded_proposition_fragment_membership_v6"
MARKER_FREE_PROPOSITION_POLICY_ID = "marker_free_unique_occurrence_diagnostic_v1"


class PropositionScopeLedger(StagedExtractionLedger, ContextPlanningLedger, Protocol):
    """Ledger operations needed by the proposition-scope experiment."""


class PropositionScopeArchive(Protocol):
    """Archive operation needed to preserve raw model output."""

    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...


@dataclass(frozen=True)
class PropositionScopeCommand:
    """Complete caller-owned input for one source-grounded Event."""

    source_id: str
    document_id: str
    representation_id: str
    source_text: str
    event: SourceGroundedEventDraft
    trigger: EventTriggerDraft
    entity_candidates: tuple[EventEntityConnectionCandidate, ...]
    linguistic_evidence: EventEntityLinguisticEvidence
    analysis_unit: AnalysisUnit
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]
    prompt_bytes: bytes


@dataclass(frozen=True)
class PropositionScopeResult:
    """Published in-memory evidence for one bounded scope experiment."""

    candidates: tuple[PropositionFragmentCandidate, ...]
    decisions: tuple[PropositionFragmentDecision, ...]
    scope: SourceGroundedPropositionScope
    traces: tuple[ExtractionStageTrace, ...]
    extraction_task_ids: tuple[str, ...]
    model_run_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class MarkerFreePropositionMembershipCommand:
    """Caller-owned input for one marker-free diagnostic judgment."""

    source_id: str
    document_id: str
    representation_id: str
    source_text: str
    event: SourceGroundedEventDraft
    trigger: EventTriggerDraft
    candidate: PropositionFragmentCandidate
    analysis_unit: AnalysisUnit
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]
    prompt_bytes: bytes
    ordinal: int


@dataclass(frozen=True)
class MarkerFreePropositionMembershipResult:
    """Exact diagnostic result for one marker-free candidate judgment."""

    task_input: PropositionFragmentTaskInput
    answer: PropositionFragmentAnswer | None
    trace: ExtractionStageTrace
    extraction_task_id: str | None
    model_run_id: str | None


class PropositionFragmentTaskSchemaRegistry:
    """Pinned finite contract for one fragment-membership judgment."""

    schema_id = PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported proposition fragment schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=proposition_fragment_answer_schema_bytes(),
            output_contract_version=self.schema_id,
            parse=parse_proposition_fragment_answer,
        )


def run_source_grounded_proposition_scope(
    command: PropositionScopeCommand,
    *,
    ledger: PropositionScopeLedger,
    archive: PropositionScopeArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
) -> PropositionScopeResult:
    """Select exact proposition fragments without assigning semantic roles."""
    candidates = build_proposition_fragment_candidates(
        source_text=command.source_text,
        trigger=command.trigger,
        event=command.event,
        linguistic_evidence=command.linguistic_evidence,
        entity_candidates=command.entity_candidates,
    )
    registry: TaskSchemaRegistry = PropositionFragmentTaskSchemaRegistry()
    schema = registry.resolve(PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID)
    manifest = _build_manifest(
        analysis_unit=command.analysis_unit,
        model_profile=command.model_profile,
        prompt_id="source_grounded_proposition_fragment_membership_v3",
        prompt_bytes=command.prompt_bytes,
        schema=schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )
    decisions: list[PropositionFragmentDecision] = []
    traces: list[ExtractionStageTrace] = []
    task_ids: list[str] = []
    run_ids: list[str] = []
    diagnostics: list[str] = []
    model_ordinal = 0
    for candidate in candidates:
        if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons:
            decisions.append(
                build_proposition_fragment_decision(
                    candidate=candidate,
                    route=PropositionFragmentRoute.DETERMINISTIC_REQUIRED,
                    disposition=PropositionFragmentDisposition.INCLUDED,
                    reason_code="event_expression_required",
                )
            )
            continue
        task_input = proposition_fragment_model_task_input(
            source_text=command.source_text,
            trigger=command.trigger,
            candidate=candidate,
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
                        command.generation_parameters
                    ),
                    schema=schema,
                    task_input=task_input,
                ),
                validator_version="proposition_fragment_membership_validator_v2",
                task_type="proposition_fragment_membership",
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
        answer = (
            outcome.proposition_fragment_answer
            if outcome.model_run.status is ModelRunStatus.SUCCEEDED
            else None
        )
        trace = _fragment_trace(
            command=command,
            candidate=candidate,
            manifest=manifest,
            schema=schema,
            task_input=task_input,
            model_run_status=outcome.model_run.status,
            extraction_task_id=outcome.extraction_task.id,
            model_run_id=outcome.model_run.id,
            raw_output=outcome.raw_model_output,
            answer=answer,
            producer_id=model_runtime.configured_identity.name,
            ordinal=model_ordinal,
        )
        traces.append(trace)
        model_ordinal += 1
        disposition, reason_code = _answer_disposition(answer)
        decisions.append(
            build_proposition_fragment_decision(
                candidate=candidate,
                route=PropositionFragmentRoute.MODEL_JUDGMENT,
                disposition=disposition,
                reason_code=reason_code,
                extraction_task_id=outcome.extraction_task.id,
                model_run_id=outcome.model_run.id,
                trace_id=trace.id,
            )
        )
        if disposition is PropositionFragmentDisposition.UNRESOLVED:
            diagnostics.append(f"proposition_fragment_unresolved:{candidate.id}")
    ordered_decisions = tuple(
        sorted(
            decisions,
            key=lambda item: next(
                index
                for index, candidate in enumerate(candidates)
                if candidate.id == item.candidate_id
            ),
        )
    )
    scope = build_source_grounded_proposition_scope(
        source_text=command.source_text,
        event=command.event,
        trigger=command.trigger,
        candidates=candidates,
        decisions=ordered_decisions,
    )
    digest = source_grounded_proposition_result_sha256(
        candidates=candidates,
        decisions=ordered_decisions,
        scope=scope,
        traces=tuple(traces),
        diagnostics=tuple(sorted(diagnostics)),
    )
    return PropositionScopeResult(
        candidates=candidates,
        decisions=ordered_decisions,
        scope=scope,
        traces=tuple(traces),
        extraction_task_ids=tuple(task_ids),
        model_run_ids=tuple(run_ids),
        diagnostics=tuple(sorted(diagnostics)),
        sha256=digest,
    )


def run_marker_free_proposition_fragment_membership(
    command: MarkerFreePropositionMembershipCommand,
    *,
    ledger: PropositionScopeLedger,
    archive: PropositionScopeArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
) -> MarkerFreePropositionMembershipResult:
    """Judge one uniquely identifiable candidate without modifying source characters."""
    task = marker_free_proposition_fragment_model_task_input(
        source_text=command.source_text,
        trigger=command.trigger,
        candidate=command.candidate,
    )
    if task.status is PropositionFragmentTaskInputStatus.OCCURRENCE_AMBIGUOUS:
        trace = _marker_free_blocked_trace(command, task)
        return MarkerFreePropositionMembershipResult(task, None, trace, None, None)
    if task.rendered_input is None:
        raise ValueError("A ready marker-free proposition task has no rendered input.")
    registry: TaskSchemaRegistry = PropositionFragmentTaskSchemaRegistry()
    schema = registry.resolve(PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID)
    manifest = _build_manifest(
        analysis_unit=command.analysis_unit,
        model_profile=command.model_profile,
        prompt_id=MARKER_FREE_PROPOSITION_PROMPT_ID,
        prompt_bytes=command.prompt_bytes,
        schema=schema,
        ledger=ledger,
        tokenizer=tokenizer,
    )
    task_input = task.rendered_input.encode()
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
                generation_parameters=_bounded_generation_parameters(command.generation_parameters),
                schema=schema,
                task_input=task_input,
            ),
            validator_version="proposition_fragment_membership_validator_v2",
            task_type="proposition_fragment_membership_marker_free_diagnostic",
            input_candidate_ids=(command.candidate.id,),
            task_local_input=task_input,
        ),
        ledger,
        archive,
        model_runtime,
        model_run_id_factory,
        tokenizer,
        registry,
    )
    answer = (
        outcome.proposition_fragment_answer
        if outcome.model_run.status is ModelRunStatus.SUCCEEDED
        else None
    )
    trace = _marker_free_execution_trace(
        command=command,
        task=task,
        manifest=manifest,
        schema=schema,
        model_run_status=outcome.model_run.status,
        extraction_task_id=outcome.extraction_task.id,
        model_run_id=outcome.model_run.id,
        raw_output=outcome.raw_model_output,
        answer=answer,
        producer_id=model_runtime.configured_identity.name,
    )
    return MarkerFreePropositionMembershipResult(
        task,
        answer,
        trace,
        outcome.extraction_task.id,
        outcome.model_run.id,
    )


def _answer_disposition(
    answer: PropositionFragmentAnswer | None,
) -> tuple[PropositionFragmentDisposition, str]:
    if answer is None or answer.value is PropositionFragmentAnswerValue.UNCERTAIN:
        return PropositionFragmentDisposition.UNRESOLVED, (
            "model_judgment_failed" if answer is None else "model_uncertain"
        )
    if answer.value is PropositionFragmentAnswerValue.YES:
        return PropositionFragmentDisposition.INCLUDED, "model_included"
    return PropositionFragmentDisposition.EXCLUDED, "model_excluded"


def _build_manifest(
    *,
    analysis_unit: AnalysisUnit,
    model_profile: ContextModelProfile,
    prompt_id: str,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    ledger: PropositionScopeLedger,
    tokenizer: ContextTokenizer,
) -> ContextManifest:
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=analysis_unit,
            model_profile=model_profile,
            prompt_id=prompt_id,
            prompt_bytes=prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="source_grounded_proposition_context_v1",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "Proposition ContextManifest is not ready: "
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
) -> tuple[ExecutionSetting, ...]:
    if sum(item.key == "max_output_tokens" for item in settings) != 1:
        raise ValueError("Proposition membership requires one max_output_tokens setting.")
    configured_limit = next(item.value for item in settings if item.key == "max_output_tokens")
    if type(configured_limit) is not int or configured_limit < PROPOSITION_SCOPE_OUTPUT_TOKEN_LIMIT:
        raise ValueError("Proposition membership output limit exceeds its configured maximum.")
    return tuple(
        ExecutionSetting(
            item.key,
            PROPOSITION_SCOPE_OUTPUT_TOKEN_LIMIT if item.key == "max_output_tokens" else item.value,
        )
        for item in settings
    )


def _fragment_trace(
    *,
    command: PropositionScopeCommand,
    candidate: PropositionFragmentCandidate,
    manifest: ContextManifest,
    schema: PinnedTaskSchema,
    task_input: bytes,
    model_run_status: ModelRunStatus,
    extraction_task_id: str,
    model_run_id: str,
    raw_output: bytes | None,
    answer: PropositionFragmentAnswer | None,
    producer_id: str,
    ordinal: int,
) -> ExtractionStageTrace:
    rendered_input = manifest.rendered_input + b"\n\n[task]\n" + task_input
    raw_text: str | None = None
    if raw_output is not None:
        try:
            raw_text = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            pass
    succeeded = model_run_status is ModelRunStatus.SUCCEEDED and answer is not None
    return build_extraction_stage_trace(
        trace_run_id=f"proposition_scope:{command.event.id}",
        ordinal=ordinal,
        stage_id="proposition_fragment_membership",
        stage_version=PROPOSITION_SCOPE_POLICY_ID,
        producer_id=producer_id,
        source_segment_id=command.event.source_segment_id,
        source_text_sha256=command.event.source_text_sha256,
        input_record_ids=tuple(sorted((command.event.id, command.trigger.id, candidate.id))),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration={
            "policy_id": PROPOSITION_SCOPE_POLICY_ID,
            "prompt_sha256": hashlib.sha256(command.prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "candidate": cast(JsonValue, candidate.model_dump(mode="json")),
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
            "parsed_answer": answer.value.value if answer is not None else None,
        },
        status=ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED,
        diagnostics=() if succeeded else ("proposition_fragment_membership_failed",),
    )


def _marker_free_blocked_trace(
    command: MarkerFreePropositionMembershipCommand,
    task: PropositionFragmentTaskInput,
) -> ExtractionStageTrace:
    reason = task.reason_code or "occurrence_ambiguous_for_marker_free_diagnostic"
    return build_extraction_stage_trace(
        trace_run_id=f"proposition_marker_free:{command.event.id}",
        ordinal=command.ordinal,
        stage_id="proposition_fragment_membership_marker_free",
        stage_version=MARKER_FREE_PROPOSITION_POLICY_ID,
        producer_id="kotekomi",
        source_segment_id=command.event.source_segment_id,
        source_text_sha256=command.event.source_text_sha256,
        input_record_ids=tuple(
            sorted((command.event.id, command.trigger.id, command.candidate.id))
        ),
        configuration={
            "policy_id": MARKER_FREE_PROPOSITION_POLICY_ID,
            "prompt_sha256": hashlib.sha256(command.prompt_bytes).hexdigest(),
        },
        input_payload={
            "candidate": cast(JsonValue, command.candidate.model_dump(mode="json")),
            "task_input": cast(JsonValue, task.model_dump(mode="json")),
        },
        output_payload={
            "parsed_answer": None,
            "reason_code": reason,
        },
        status=ExtractionStageStatus.BLOCKED,
        diagnostics=tuple(sorted({"occurrence_ambiguous_for_marker_free_diagnostic", reason})),
    )


def _marker_free_execution_trace(
    *,
    command: MarkerFreePropositionMembershipCommand,
    task: PropositionFragmentTaskInput,
    manifest: ContextManifest,
    schema: PinnedTaskSchema,
    model_run_status: ModelRunStatus,
    extraction_task_id: str,
    model_run_id: str,
    raw_output: bytes | None,
    answer: PropositionFragmentAnswer | None,
    producer_id: str,
) -> ExtractionStageTrace:
    if task.rendered_input is None:
        raise ValueError("A marker-free model trace requires rendered task input.")
    task_input = task.rendered_input.encode()
    rendered_input = manifest.rendered_input + b"\n\n[task]\n" + task_input
    raw_text: str | None = None
    if raw_output is not None:
        try:
            raw_text = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            pass
    succeeded = model_run_status is ModelRunStatus.SUCCEEDED and answer is not None
    return build_extraction_stage_trace(
        trace_run_id=f"proposition_marker_free:{command.event.id}",
        ordinal=command.ordinal,
        stage_id="proposition_fragment_membership_marker_free",
        stage_version=MARKER_FREE_PROPOSITION_POLICY_ID,
        producer_id=producer_id,
        source_segment_id=command.event.source_segment_id,
        source_text_sha256=command.event.source_text_sha256,
        input_record_ids=tuple(
            sorted((command.event.id, command.trigger.id, command.candidate.id))
        ),
        execution_record_ids=tuple(sorted((extraction_task_id, model_run_id))),
        configuration={
            "policy_id": MARKER_FREE_PROPOSITION_POLICY_ID,
            "prompt_sha256": hashlib.sha256(command.prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "candidate": cast(JsonValue, command.candidate.model_dump(mode="json")),
            "task_input": cast(JsonValue, task.model_dump(mode="json")),
            "model_visible_task": task.rendered_input,
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
            "parsed_answer": answer.value.value if answer is not None else None,
        },
        status=ExtractionStageStatus.COMPLETED if succeeded else ExtractionStageStatus.FAILED,
        diagnostics=() if succeeded else ("proposition_fragment_membership_failed",),
    )


def source_grounded_proposition_result_sha256(
    *,
    candidates: tuple[PropositionFragmentCandidate, ...],
    decisions: tuple[PropositionFragmentDecision, ...],
    scope: SourceGroundedPropositionScope,
    traces: tuple[ExtractionStageTrace, ...],
    diagnostics: tuple[str, ...],
) -> str:
    payload = {
        "candidates": [item.model_dump(mode="json") for item in candidates],
        "decisions": [item.model_dump(mode="json") for item in decisions],
        "diagnostics": list(diagnostics),
        "scope": scope.model_dump(mode="json"),
        "traces": [item.model_dump(mode="json") for item in traces],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
