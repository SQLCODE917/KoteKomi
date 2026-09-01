"""Bounded staged model extraction with immutable task and run lineage."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from typing import Protocol, cast

from kotekomi_domain import DocumentNode, ExtractionTask, ModelRun, ModelRunStatus, TextView
from kotekomi_domain.models import JsonValue
from pydantic import ValidationError

from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V1,
    PARAGRAPH_SEGMENT_V2,
    PARAGRAPH_SEGMENT_V3,
    ContextManifest,
    ContextManifestStatus,
    ContextPlanningLedger,
    ContextTokenizer,
    EvidenceCandidate,
    paragraph_source_segments,
    render_context,
    source_copy_view,
    verify_context_manifest,
)
from kotekomi_application.grounded_candidates import (
    GroundedAssertionCandidate,
    GroundedCandidateBatchCommit,
    GroundedCandidateBatchInput,
    GroundedCandidateLedger,
    GroundedEvidenceCandidate,
    GroundedLiteralObject,
    GroundedOrganizationCandidate,
    GroundedOrganizationReferenceObject,
    ProposedChangeBatchOutcome,
    prepare_grounded_candidate_batch,
)
from kotekomi_application.hybrid_mention_interpretation import (
    MentionInterpretationDraft,
    MentionProposalAbstention,
    MentionProposalDraftBatch,
    hybrid_mention_task_schema_bytes,
    parse_hybrid_mention_task_output,
)
from kotekomi_application.organization_semantic_qualification import (
    OrganizationQualificationJudgment,
    parse_organization_qualification_output,
)

HASH_ID_LENGTH = 24


class StagedExtractionLedger(GroundedCandidateLedger, ContextPlanningLedger, Protocol):
    def save_extraction_task(self, record: ExtractionTask) -> None: ...
    def save_model_run(self, record: ModelRun) -> None: ...
    def commit_successful_model_run_and_candidate_batch(
        self,
        *,
        model_run: ModelRun,
        batch: GroundedCandidateBatchCommit,
    ) -> None: ...


class ModelOutputArchive(Protocol):
    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...


type ExecutionScalar = str | int | float | bool | None


@dataclass(frozen=True)
class ExecutionSetting:
    key: str
    value: ExecutionScalar

    def __post_init__(self) -> None:
        if not self.key or self.key != self.key.strip():
            raise ValueError("Model execution setting keys must be non-empty and trimmed.")


def _validate_settings(
    settings: tuple[object, ...],
    label: str,
    *,
    forbidden_keys: frozenset[str] = frozenset(),
) -> None:
    if any(not isinstance(setting, ExecutionSetting) for setting in settings):
        raise ValueError(f"{label} must contain only ExecutionSetting records.")
    validated_settings = cast(tuple[ExecutionSetting, ...], settings)
    if tuple(sorted(validated_settings, key=lambda setting: setting.key)) != validated_settings:
        raise ValueError(f"{label} must be in canonical key order.")
    if len({setting.key for setting in validated_settings}) != len(validated_settings):
        raise ValueError(f"{label} keys must be unique.")
    if any(setting.key in forbidden_keys for setting in validated_settings):
        raise ValueError(f"{label} may not use a reserved model identity field.")
    if any(
        isinstance(setting.value, float) and not math.isfinite(setting.value)
        for setting in validated_settings
    ):
        raise ValueError(f"{label} values must be finite JSON scalars.")
    if any(
        type(setting.value) not in {str, int, float, bool, type(None)}
        for setting in validated_settings
    ):
        raise ValueError(f"{label} values must be JSON scalars.")


@dataclass(frozen=True)
class ModelIdentitySnapshot:
    name: str
    weights_digest: str | None
    runtime: str
    tokenizer_id: str
    determinism_settings: tuple[ExecutionSetting, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.runtime or not self.tokenizer_id:
            raise ValueError("Model identity fields must be non-empty.")
        if self.weights_digest is not None and (
            len(self.weights_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.weights_digest)
        ):
            raise ValueError("Model weights digest must be SHA-256 hex when recorded.")
        _validate_settings(
            self.determinism_settings,
            "Model determinism settings",
            forbidden_keys=frozenset({"name", "weights_digest", "runtime", "tokenizer_id"}),
        )


@dataclass(frozen=True)
class ModelExecutionSpec:
    model_profile_id: str
    model_identity: ModelIdentitySnapshot
    generation_parameters: tuple[ExecutionSetting, ...]
    prompt_id: str
    prompt_digest: str
    schema_id: str
    schema_digest: str
    context_manifest_id: str
    context_manifest_digest: str
    rendered_input_digest: str
    output_contract_version: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.model_profile_id,
                self.prompt_id,
                self.schema_id,
                self.context_manifest_id,
                self.output_contract_version,
            )
        ):
            raise ValueError("Model execution specification identity fields must be non-empty.")
        for digest in (
            self.prompt_digest,
            self.schema_digest,
            self.context_manifest_digest,
            self.rendered_input_digest,
        ):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("Model execution specification digests must be SHA-256 hex.")
        _validate_settings(self.generation_parameters, "Model generation parameters")


@dataclass(frozen=True)
class ModelExecutionReceipt:
    model_identity_digest: str
    generation_parameters_digest: str
    rendered_input_digest: str
    input_token_count: int
    output_token_count: int | None

    def __post_init__(self) -> None:
        for digest in (
            self.model_identity_digest,
            self.generation_parameters_digest,
            self.rendered_input_digest,
        ):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("Model execution receipt digests must be SHA-256 hex.")
        if (
            type(self.input_token_count) is not int
            or self.input_token_count < 0
            or (
                self.output_token_count is not None
                and (type(self.output_token_count) is not int or self.output_token_count < 0)
            )
        ):
            raise ValueError("Model execution receipt token counts cannot be negative.")


@dataclass(frozen=True)
class ModelTaskRequest:
    extraction_task_id: str
    task_fingerprint: str
    task_type: str
    context_manifest_id: str
    context_manifest_digest: str
    rendered_input: bytes
    rendered_input_digest: str
    execution_spec: ModelExecutionSpec


@dataclass(frozen=True)
class ModelTaskResponse:
    raw_output: bytes
    execution_receipt: ModelExecutionReceipt
    first_response_event_milliseconds: int | None = None

    def __post_init__(self) -> None:
        if self.first_response_event_milliseconds is not None and (
            type(self.first_response_event_milliseconds) is not int
            or self.first_response_event_milliseconds < 0
        ):
            raise ValueError(
                "First response event milliseconds must be non-negative when recorded."
            )


class ModelTaskRuntime(Protocol):
    @property
    def configured_identity(self) -> ModelIdentitySnapshot: ...

    @property
    def task_deadline_seconds(self) -> float: ...

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse: ...


class ModelRunClock(Protocol):
    def now(self) -> datetime: ...

    def monotonic_seconds(self) -> float: ...


class UtcModelRunClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic_seconds(self) -> float:
        return time.monotonic()


class ModelRunIdFactory(Protocol):
    def new_model_run_id(self) -> str: ...


class Uuid4ModelRunIdFactory:
    def new_model_run_id(self) -> str:
        return f"mrn_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class PinnedTaskSchema:
    schema_id: str
    canonical_schema_bytes: bytes
    output_contract_version: str
    parse: Callable[[bytes], ParsedModelOutput]

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_schema_bytes).hexdigest()


class TaskSchemaRegistry(Protocol):
    def resolve(self, schema_id: str) -> PinnedTaskSchema: ...


class SemanticDraftTaskSchemaRegistry:
    """The versioned pinned schema registry for direct-prose claim tasks."""

    schema_id = "semantic_draft_text_v1"

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported semantic draft task schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=semantic_draft_text_schema_bytes(),
            output_contract_version="semantic_draft_text_v1",
            parse=_parse_semantic_draft,
        )


class ParagraphHypothesisTaskSchemaRegistry:
    """The versioned pinned schema registry for bounded paragraph hypotheses."""

    schema_id = "paragraph_hypothesis_text_v1"

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported paragraph hypothesis task schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=paragraph_hypothesis_text_schema_bytes(),
            output_contract_version="paragraph_hypothesis_text_v1",
            parse=_parse_hypothesis_batch,
        )


class OrganizationMentionTaskSchemaRegistry:
    """The versioned pinned schema registry for diagnostic Organization mentions."""

    schema_id = "organization_mention_text_v1"

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported Organization mention task schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=organization_mention_text_schema_bytes(),
            output_contract_version="organization_mention_text_v1",
            parse=_parse_organization_mention_batch,
        )


class OrganizationQualificationTaskSchemaRegistry:
    """The versioned pinned schema registry for one Organization judgment."""

    schema_id = "organization_qualification_text_v1"

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported Organization qualification task schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=organization_qualification_text_schema_bytes(),
            output_contract_version="organization_qualification_text_v1",
            parse=_parse_organization_qualification,
        )


class OrganizationQualificationLabelTaskSchemaRegistry:
    """The ORG-R2 tri-state schema for one immutable candidate boundary."""

    schema_id = "organization_qualification_label_v1"

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported Organization qualification label schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=organization_qualification_label_schema_bytes(),
            output_contract_version="organization_qualification_label_v1",
            parse=_parse_organization_qualification_label,
        )


class HybridMentionTaskSchemaRegistry:
    """The pinned proposal and contextual interpretation output contracts."""

    schema_id = "hybrid_mention_task_text_v1"

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported hybrid mention task schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=hybrid_mention_task_schema_bytes(),
            output_contract_version=self.schema_id,
            parse=parse_hybrid_mention_task_output,
        )


@dataclass(frozen=True)
class BoundedExtractionInput:
    source_id: str
    document_id: str
    representation_id: str
    context_manifest_id: str
    prompt_bytes: bytes
    execution_spec: ModelExecutionSpec
    validator_version: str
    hypothesis_verifier: HypothesisVerifierSpec | None = None
    task_type: str = "claim_extraction"
    input_candidate_ids: tuple[str, ...] = ()
    task_local_input: bytes = b""


@dataclass(frozen=True)
class BoundedExtractionOutcome:
    extraction_task: ExtractionTask
    model_run: ModelRun
    proposed_change_batch: ProposedChangeBatchOutcome | None
    verified_hypotheses: tuple[VerifiedHypothesis, ...] = ()
    organization_mentions: tuple[OrganizationMention, ...] = ()
    organization_qualification: OrganizationQualification | None = None
    organization_qualification_judgment: OrganizationQualificationJudgment | None = None
    mention_proposal_drafts: MentionProposalDraftBatch | None = None
    mention_interpretation_draft: MentionInterpretationDraft | None = None


@dataclass(frozen=True)
class SemanticDraft:
    subject: str
    relation: str
    object_kind: str
    object_value: str


@dataclass(frozen=True)
class SemanticDraftAbstention:
    reason: str


@dataclass(frozen=True)
class AtomicHypothesis:
    source_segment_label: str
    subject: str
    relation: str
    object_value: str


@dataclass(frozen=True)
class VerifiedHypothesis:
    """One verifier-accepted PHP-1 claim and its pending Assertion proposal."""

    hypothesis: AtomicHypothesis
    proposed_change_id: str


@dataclass(frozen=True)
class HypothesisBatch:
    claims: tuple[AtomicHypothesis, ...]


@dataclass(frozen=True)
class HypothesisBatchAbstention:
    reason: str


@dataclass(frozen=True)
class OrganizationMention:
    source_segment_label: str
    organization_text: str


@dataclass(frozen=True)
class OrganizationMentionBatch:
    mentions: tuple[OrganizationMention, ...]


@dataclass(frozen=True)
class OrganizationMentionBatchAbstention:
    reason: str


@dataclass(frozen=True)
class OrganizationQualification:
    organization_text: str


@dataclass(frozen=True)
class OrganizationQualificationRejection:
    reason: str


type ParsedModelOutput = (
    SemanticDraft
    | SemanticDraftAbstention
    | HypothesisBatch
    | HypothesisBatchAbstention
    | OrganizationMentionBatch
    | OrganizationMentionBatchAbstention
    | OrganizationQualification
    | OrganizationQualificationRejection
    | OrganizationQualificationJudgment
    | MentionProposalDraftBatch
    | MentionProposalAbstention
    | MentionInterpretationDraft
)


@dataclass(frozen=True)
class HypothesisVerifierSpec:
    """Pinned model contract for independent PHP-1 relation verification."""

    prompt_id: str
    prompt_bytes: bytes

    def __post_init__(self) -> None:
        if not self.prompt_id or not self.prompt_bytes:
            raise ValueError("Hypothesis verifier requires a non-empty pinned prompt.")


@dataclass(frozen=True)
class HypothesisFaithfulnessVerdict:
    accepted: bool
    reason: str


def run_bounded_extraction(
    extraction_input: BoundedExtractionInput,
    ledger_repository: StagedExtractionLedger,
    archive_store: ModelOutputArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    schema_registry: TaskSchemaRegistry,
    clock: ModelRunClock | None = None,
) -> BoundedExtractionOutcome:
    """Archive and validate task-local candidates, then publish eligible proposals atomically."""
    execution_spec = extraction_input.execution_spec
    schema = schema_registry.resolve(execution_spec.schema_id)
    verified = verify_context_manifest(
        extraction_input.context_manifest_id,
        ledger_repository,
        tokenizer,
        extraction_input.prompt_bytes,
        schema.canonical_schema_bytes,
    )
    manifest = verified.manifest
    if manifest.status is not ContextManifestStatus.READY:
        raise ValueError("Bounded extraction requires a ready ContextManifest.")
    if manifest.representation_id != extraction_input.representation_id:
        raise ValueError("Bounded extraction ContextManifest does not match its representation.")
    rendered_context = render_context(
        manifest.id,
        ledger_repository,
        tokenizer,
        extraction_input.prompt_bytes,
        schema.canonical_schema_bytes,
    )
    rendered_input = _compose_task_input(rendered_context, extraction_input.task_local_input)
    _validate_execution_spec(execution_spec, manifest, rendered_input, schema)
    if model_runtime.configured_identity != execution_spec.model_identity:
        raise ValueError("Model runtime configured identity does not match the execution spec.")
    model_run_clock = clock or UtcModelRunClock()
    deadline_milliseconds = _deadline_milliseconds(model_runtime.task_deadline_seconds)
    task = _extraction_task(extraction_input, manifest)
    ledger_repository.save_extraction_task(task)
    model_run_id = model_run_id_factory.new_model_run_id()
    request = ModelTaskRequest(
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        task_type=extraction_input.task_type,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input=rendered_input,
        rendered_input_digest=hashlib.sha256(rendered_input).hexdigest(),
        execution_spec=execution_spec,
    )
    started_at = model_run_clock.now()
    monotonic_started = model_run_clock.monotonic_seconds()
    try:
        response = model_runtime.run_model_task(request)
    except Exception as exc:
        completed_at, diagnostics = _completed_diagnostics(
            model_run_clock,
            monotonic_started,
            deadline_milliseconds,
            None,
        )
        run = _model_run(
            extraction_input,
            manifest,
            task,
            model_run_id,
            ModelRunStatus.RUNTIME_FAILED,
            started_at=started_at,
            completed_at=completed_at,
            execution_diagnostics=diagnostics,
            error=exc,
        )
        ledger_repository.save_model_run(run)
        return BoundedExtractionOutcome(task, run, None)

    completed_at, diagnostics = _completed_diagnostics(
        model_run_clock,
        monotonic_started,
        deadline_milliseconds,
        response.first_response_event_milliseconds,
    )

    output_digest = hashlib.sha256(response.raw_output).hexdigest()
    try:
        archive_store.put_model_run_output(
            model_run_id,
            response.raw_output,
            output_digest,
        )
    except Exception as exc:
        run = _model_run(
            extraction_input,
            manifest,
            task,
            model_run_id,
            ModelRunStatus.OUTPUT_ARCHIVE_FAILED,
            started_at=started_at,
            completed_at=completed_at,
            execution_diagnostics=diagnostics,
            execution_receipt=response.execution_receipt,
            error=exc,
        )
        ledger_repository.save_model_run(run)
        return BoundedExtractionOutcome(task, run, None)
    try:
        _validate_execution_receipt(
            response.execution_receipt,
            execution_spec,
            manifest,
            expected_input_token_count=tokenizer.count_tokens(rendered_input),
        )
        parsed = _parse_output(response.raw_output, manifest, schema)
        if isinstance(
            parsed,
            (
                SemanticDraftAbstention,
                HypothesisBatchAbstention,
                OrganizationMentionBatchAbstention,
                OrganizationQualificationRejection,
                MentionProposalAbstention,
            ),
        ):
            run = _model_run(
                extraction_input,
                manifest,
                task,
                model_run_id,
                ModelRunStatus.ABSTAINED,
                started_at=started_at,
                completed_at=completed_at,
                execution_diagnostics=diagnostics,
                output_digest=output_digest,
                execution_receipt=response.execution_receipt,
                abstention_reason=parsed.reason,
                outcome_metadata=_abstention_outcome_metadata(parsed),
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(task, run, None)
        verifier_metadata: dict[str, JsonValue] = {}
        if isinstance(parsed, HypothesisBatch) and extraction_input.hypothesis_verifier is not None:
            parsed, verifier_metadata = _verify_hypothesis_batch(
                extraction_input,
                manifest,
                task,
                model_run_id,
                parsed,
                ledger_repository,
                archive_store,
                model_runtime,
                model_run_id_factory,
                model_run_clock,
                completed_at,
            )
            if not parsed.claims:
                run = _model_run(
                    extraction_input,
                    manifest,
                    task,
                    model_run_id,
                    ModelRunStatus.SUCCEEDED,
                    started_at=started_at,
                    completed_at=completed_at,
                    execution_diagnostics=diagnostics,
                    output_digest=output_digest,
                    execution_receipt=response.execution_receipt,
                    outcome_metadata={
                        "contract": "paragraph_hypothesis_text_v1",
                        "unique_claim_count": 0,
                        "duplicate_claim_lines": [],
                        **verifier_metadata,
                    },
                )
                ledger_repository.save_model_run(run)
                return BoundedExtractionOutcome(task, run, None)
        if isinstance(parsed, OrganizationMentionBatch):
            run = _model_run(
                extraction_input,
                manifest,
                task,
                model_run_id,
                ModelRunStatus.SUCCEEDED,
                started_at=started_at,
                completed_at=completed_at,
                execution_diagnostics=diagnostics,
                output_digest=output_digest,
                execution_receipt=response.execution_receipt,
                outcome_metadata={
                    "contract": "organization_mention_text_v1",
                    "unique_mention_count": len(parsed.mentions),
                },
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(
                task,
                run,
                None,
                organization_mentions=parsed.mentions,
            )
        if isinstance(parsed, OrganizationQualification):
            run = _model_run(
                extraction_input,
                manifest,
                task,
                model_run_id,
                ModelRunStatus.SUCCEEDED,
                started_at=started_at,
                completed_at=completed_at,
                execution_diagnostics=diagnostics,
                output_digest=output_digest,
                execution_receipt=response.execution_receipt,
                outcome_metadata={
                    "contract": "organization_qualification_text_v1",
                    "qualified_organization_text": parsed.organization_text,
                },
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(
                task,
                run,
                None,
                organization_qualification=parsed,
            )
        if isinstance(parsed, OrganizationQualificationJudgment):
            run = _model_run(
                extraction_input,
                manifest,
                task,
                model_run_id,
                ModelRunStatus.SUCCEEDED,
                started_at=started_at,
                completed_at=completed_at,
                execution_diagnostics=diagnostics,
                output_digest=output_digest,
                execution_receipt=response.execution_receipt,
                outcome_metadata={
                    "contract": "organization_qualification_label_v1",
                    "judgment": parsed.value,
                },
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(
                task,
                run,
                None,
                organization_qualification_judgment=parsed,
            )
        if isinstance(parsed, MentionProposalDraftBatch):
            run = _model_run(
                extraction_input,
                manifest,
                task,
                model_run_id,
                ModelRunStatus.SUCCEEDED,
                started_at=started_at,
                completed_at=completed_at,
                execution_diagnostics=diagnostics,
                output_digest=output_digest,
                execution_receipt=response.execution_receipt,
                outcome_metadata={
                    "contract": "hybrid_mention_proposal_text_v1",
                    "proposal_count": len(parsed.proposals),
                },
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(
                task,
                run,
                None,
                mention_proposal_drafts=parsed,
            )
        if isinstance(parsed, MentionInterpretationDraft):
            run = _model_run(
                extraction_input,
                manifest,
                task,
                model_run_id,
                ModelRunStatus.SUCCEEDED,
                started_at=started_at,
                completed_at=completed_at,
                execution_diagnostics=diagnostics,
                output_digest=output_digest,
                execution_receipt=response.execution_receipt,
                outcome_metadata={
                    "contract": "hybrid_mention_interpretation_text_v1",
                    "referentiality": parsed.referentiality.value,
                    "contextual_kind": parsed.contextual_kind.value,
                    "discourse_role": parsed.discourse_role.value,
                },
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(
                task,
                run,
                None,
                mention_interpretation_draft=parsed,
            )
        batch_input, outcome_metadata = _grounded_batch(
            extraction_input,
            manifest,
            task,
            model_run_id,
            parsed,
            ledger_repository,
            completed_at,
        )
        outcome_metadata.update(verifier_metadata)
        batch_commit = prepare_grounded_candidate_batch(batch_input, ledger_repository)
    except (ValidationError, ValueError) as exc:
        run = _model_run(
            extraction_input,
            manifest,
            task,
            model_run_id,
            ModelRunStatus.INVALID_OUTPUT,
            started_at=started_at,
            completed_at=completed_at,
            execution_diagnostics=diagnostics,
            output_digest=output_digest,
            execution_receipt=response.execution_receipt,
            error=exc,
        )
        ledger_repository.save_model_run(run)
        return BoundedExtractionOutcome(task, run, None)

    run = _model_run(
        extraction_input,
        manifest,
        task,
        model_run_id,
        ModelRunStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=completed_at,
        execution_diagnostics=diagnostics,
        output_digest=output_digest,
        execution_receipt=response.execution_receipt,
        outcome_metadata=outcome_metadata,
    )
    try:
        ledger_repository.commit_successful_model_run_and_candidate_batch(
            model_run=run,
            batch=batch_commit,
        )
    except Exception as exc:
        failed_run = _model_run(
            extraction_input,
            manifest,
            task,
            model_run_id,
            ModelRunStatus.PUBLISH_FAILED,
            started_at=started_at,
            completed_at=completed_at,
            execution_diagnostics=diagnostics,
            output_digest=output_digest,
            execution_receipt=response.execution_receipt,
            error=exc,
        )
        ledger_repository.save_model_run(failed_run)
        return BoundedExtractionOutcome(task, failed_run, None)
    verified_hypotheses = ()
    if isinstance(parsed, HypothesisBatch):
        accepted_claims = _canonical_hypothesis_claims(parsed.claims)
        verified_hypotheses = tuple(
            VerifiedHypothesis(
                claim,
                batch_commit.outcome.proposed_change_ids_by_local_id[f"assertion_{index:02d}"],
            )
            for index, claim in enumerate(accepted_claims, start=1)
        )
    return BoundedExtractionOutcome(task, run, batch_commit.outcome, verified_hypotheses)


def _extraction_task(
    extraction_input: BoundedExtractionInput, manifest: ContextManifest
) -> ExtractionTask:
    fingerprint_payload: dict[str, JsonValue] = {
        "task_type": extraction_input.task_type,
        "source_id": extraction_input.source_id,
        "document_id": extraction_input.document_id,
        "representation_id": extraction_input.representation_id,
        "context_manifest_digest": manifest.manifest_digest,
        "prompt_id": manifest.prompt_id,
        "schema_id": manifest.schema_id,
        "execution_spec_digest": model_execution_spec_digest(extraction_input.execution_spec),
        "validator_version": extraction_input.validator_version,
    }
    if extraction_input.input_candidate_ids:
        fingerprint_payload["input_candidate_ids"] = list(extraction_input.input_candidate_ids)
    if extraction_input.task_local_input:
        fingerprint_payload["task_local_input_digest"] = hashlib.sha256(
            extraction_input.task_local_input
        ).hexdigest()
    fingerprint = _digest(fingerprint_payload)
    return ExtractionTask(
        id=f"ext_{fingerprint[:HASH_ID_LENGTH]}",
        task_type=extraction_input.task_type,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        context_manifest_payload=cast(
            dict[str, JsonValue],
            _manifest_payload(manifest, task_local_input=extraction_input.task_local_input),
        ),
        input_candidate_ids=extraction_input.input_candidate_ids,
        prompt_id=manifest.prompt_id,
        schema_id=manifest.schema_id,
        model_profile_id=extraction_input.execution_spec.model_profile_id,
        execution_spec_digest=model_execution_spec_digest(extraction_input.execution_spec),
        task_fingerprint=fingerprint,
        created_at=None,
    )


def bounded_extraction_task_fingerprint(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
) -> str:
    """Return the exact immutable task identity without running the model."""
    return _extraction_task(extraction_input, manifest).task_fingerprint


def _model_run(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    task: ExtractionTask,
    model_run_id: str,
    status: ModelRunStatus,
    *,
    started_at: datetime,
    completed_at: datetime,
    execution_diagnostics: dict[str, JsonValue],
    output_digest: str | None = None,
    execution_receipt: ModelExecutionReceipt | None = None,
    abstention_reason: str | None = None,
    outcome_metadata: dict[str, JsonValue] | None = None,
    execution_spec: ModelExecutionSpec | None = None,
    task_metadata_extra: dict[str, JsonValue] | None = None,
    error: Exception | None = None,
) -> ModelRun:
    effective_execution_spec = execution_spec or extraction_input.execution_spec
    task_metadata = _task_metadata(manifest)
    if task_metadata_extra is not None:
        task_metadata.update(task_metadata_extra)
    return ModelRun(
        id=model_run_id,
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        model_identity=_model_identity_payload(effective_execution_spec.model_identity),
        runtime_identity=effective_execution_spec.model_identity.runtime,
        tokenizer_id=effective_execution_spec.model_identity.tokenizer_id,
        prompt_digest=effective_execution_spec.prompt_digest,
        schema_digest=effective_execution_spec.schema_digest,
        execution_spec_digest=model_execution_spec_digest(effective_execution_spec),
        generation_parameters=cast(
            dict[str, JsonValue],
            _settings_payload(effective_execution_spec.generation_parameters),
        ),
        raw_output_artifact_id=(model_run_id if output_digest is not None else None),
        output_digest=output_digest,
        status=status,
        abstention_reason=abstention_reason,
        error_code=(type(error).__name__ if error is not None else None),
        error_message=(str(error) if error is not None else None),
        started_at=started_at,
        completed_at=completed_at,
        execution_diagnostics=execution_diagnostics,
        execution_receipt=(
            _execution_receipt_payload(execution_receipt) if execution_receipt is not None else None
        ),
        task_metadata=task_metadata,
        outcome_metadata=outcome_metadata or {},
    )


def _deadline_milliseconds(deadline_seconds: float) -> int:
    if not math.isfinite(deadline_seconds) or deadline_seconds <= 0:
        raise ValueError("Model task deadline must be a positive finite duration.")
    return int(round(deadline_seconds * 1000))


def _completed_diagnostics(
    clock: ModelRunClock,
    monotonic_started: float,
    deadline_milliseconds: int,
    first_response_event_milliseconds: int | None,
) -> tuple[datetime, dict[str, JsonValue]]:
    completed_at = clock.now()
    elapsed_milliseconds = int(round((clock.monotonic_seconds() - monotonic_started) * 1000))
    if elapsed_milliseconds < 0:
        raise ValueError("Model run monotonic clock moved backwards.")
    if (
        first_response_event_milliseconds is not None
        and first_response_event_milliseconds > elapsed_milliseconds
    ):
        raise ValueError("Model response event cannot occur after task completion.")
    return completed_at, {
        "elapsed_milliseconds": elapsed_milliseconds,
        "deadline_milliseconds": deadline_milliseconds,
        "first_response_event_milliseconds": first_response_event_milliseconds,
    }


def _parse_output(
    raw_output: bytes, manifest: ContextManifest, schema: PinnedTaskSchema
) -> ParsedModelOutput:
    if manifest.schema_id != schema.schema_id or manifest.schema_digest != schema.digest:
        raise ValueError("ContextManifest schema does not match the pinned task schema.")
    return schema.parse(raw_output)


def _parse_semantic_draft(raw_output: bytes) -> SemanticDraft | SemanticDraftAbstention:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("SemanticDraft output must be UTF-8 text.") from error
    lines = text.splitlines()
    fields = _semantic_draft_fields(lines)
    outcome = fields.get("outcome")
    if outcome == "abstain":
        _require_semantic_draft_keys(fields, ("outcome", "reason"))
        return SemanticDraftAbstention(reason=fields["reason"])
    if outcome == "claim":
        _require_semantic_draft_keys(
            fields,
            ("outcome", "subject", "relation", "object_kind", "object"),
        )
        object_kind = fields["object_kind"]
        if object_kind not in {"organization", "literal"}:
            raise ValueError("SemanticDraft object_kind must be organization or literal.")
        return SemanticDraft(
            subject=fields["subject"],
            relation=fields["relation"],
            object_kind=object_kind,
            object_value=fields["object"],
        )
    raise ValueError("SemanticDraft outcome must be claim or abstain.")


def _semantic_draft_fields(lines: list[str]) -> dict[str, str]:
    if not lines:
        raise ValueError("SemanticDraft output must not be empty.")
    fields: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition(": ")
        if not separator or not key or not value:
            raise ValueError("SemanticDraft lines must use non-empty key: value form.")
        if key in fields:
            raise ValueError(f"SemanticDraft repeats field: {key}")
        if key != key.strip() or value != value.strip():
            raise ValueError("SemanticDraft keys and values must be trimmed.")
        fields[key] = value
    return fields


def _require_semantic_draft_keys(fields: dict[str, str], expected: tuple[str, ...]) -> None:
    if tuple(fields) != expected:
        raise ValueError("SemanticDraft fields must match the output contract exactly.")


def _parse_hypothesis_batch(raw_output: bytes) -> HypothesisBatch | HypothesisBatchAbstention:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Hypothesis batch output must be UTF-8 text.") from error
    lines = text.splitlines()
    if not lines or any(not line or line != line.strip() for line in lines):
        raise ValueError("Hypothesis batch output must contain only trimmed non-empty lines.")
    if len(lines) == 1 and lines[0].startswith("abstain: "):
        reason = lines[0].removeprefix("abstain: ")
        if not reason:
            raise ValueError("Hypothesis batch abstention reason must be non-empty.")
        return HypothesisBatchAbstention(reason=reason)
    if len(lines) > 8:
        raise ValueError("Hypothesis batch contains more than eight claim lines.")
    claims: list[AtomicHypothesis] = []
    for line in lines:
        if not line.startswith("claim: "):
            raise ValueError("Hypothesis batch must contain claim lines or one abstention.")
        parts = line.removeprefix("claim: ").split(" | ")
        if len(parts) != 4 or any(not part or part != part.strip() for part in parts):
            raise ValueError("Hypothesis claim lines must contain four trimmed fields.")
        claims.append(AtomicHypothesis(*parts))
    return HypothesisBatch(claims=tuple(claims))


def _grounded_batch(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    task: ExtractionTask,
    model_run_id: str,
    output: SemanticDraft | HypothesisBatch,
    ledger_repository: StagedExtractionLedger,
    submitted_at: datetime,
) -> tuple[GroundedCandidateBatchInput, dict[str, JsonValue]]:
    bundle = ledger_repository.get_document_representation_bundle(
        extraction_input.representation_id
    )
    if bundle is None:
        raise ValueError("Bounded extraction references a missing DocumentRepresentation.")
    nodes = {node.id: node for node in bundle.nodes}
    text_views = {text_view.id: text_view for text_view in bundle.text_views}
    bound_candidate = _bound_evidence_candidate(manifest)
    evidence = _resolved_bound_evidence_candidate(
        bound_candidate,
        nodes,
        text_views,
    )
    if isinstance(output, HypothesisBatch):
        return _grounded_hypothesis_batch(
            extraction_input,
            manifest,
            task,
            model_run_id,
            output,
            evidence,
            submitted_at,
        )
    _require_source_grounded(output.subject, evidence.exact_text, "SemanticDraft subject")
    _require_source_grounded(output.object_value, evidence.exact_text, "SemanticDraft object")
    organizations = [GroundedOrganizationCandidate("org_01", output.subject)]
    if output.object_kind == "organization" and output.object_value != output.subject:
        organizations.append(GroundedOrganizationCandidate("org_02", output.object_value))
    assertion_object = (
        GroundedOrganizationReferenceObject(
            "org_01" if output.object_value == output.subject else "org_02"
        )
        if output.object_kind == "organization"
        else GroundedLiteralObject(output.object_value)
    )
    return GroundedCandidateBatchInput(
        task_fingerprint=task.task_fingerprint,
        source_id=extraction_input.source_id,
        document_id=extraction_input.document_id,
        representation_id=extraction_input.representation_id,
        model_name=extraction_input.execution_spec.model_identity.name,
        prompt_id=manifest.prompt_id,
        validator_version=extraction_input.validator_version,
        submitted_at=submitted_at,
        organizations=tuple(organizations),
        evidence=(evidence,),
        assertions=(
            GroundedAssertionCandidate(
                "assertion_01",
                "org_01",
                evidence.local_id,
                output.relation,
                assertion_object,
            ),
        ),
        originating_model_run_id=model_run_id,
    ), {"contract": "semantic_draft_text_v1", "unique_claim_count": 1, "duplicate_claim_lines": []}


def _grounded_hypothesis_batch(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    task: ExtractionTask,
    model_run_id: str,
    output: HypothesisBatch,
    bound_evidence: GroundedEvidenceCandidate,
    submitted_at: datetime,
) -> tuple[GroundedCandidateBatchInput, dict[str, JsonValue]]:
    if manifest.source_segment_policy_id not in {
        PARAGRAPH_SEGMENT_V1,
        PARAGRAPH_SEGMENT_V2,
        PARAGRAPH_SEGMENT_V3,
    }:
        raise ValueError("Hypothesis batch requires a paragraph source segment policy.")
    segments = paragraph_source_segments(
        bound_evidence.exact_text, manifest.source_segment_policy_id
    )
    by_label = {segment.label: segment for segment in segments}
    for claim in output.claims:
        segment = by_label.get(claim.source_segment_label)
        if segment is None:
            raise ValueError("Hypothesis claim references an unknown source segment.")
        _require_hypothesis_source_grounded(
            claim.subject,
            segment.exact_text,
            manifest.source_segment_policy_id,
            "Hypothesis subject",
        )
        _require_hypothesis_source_grounded(
            claim.object_value,
            segment.exact_text,
            manifest.source_segment_policy_id,
            "Hypothesis object",
        )
    ordered, duplicate_lines = _canonical_hypothesis_claims_with_duplicates(output.claims)
    if not ordered:
        raise ValueError("Hypothesis batch requires at least one claim or an abstention.")
    organizations: dict[str, str] = {}
    evidence: list[GroundedEvidenceCandidate] = []
    evidence_local_ids_by_segment: dict[str, str] = {}
    assertions: list[GroundedAssertionCandidate] = []
    for index, claim in enumerate(ordered, start=1):
        segment = by_label[claim.source_segment_label]
        subject_local_id = _organization_local_id(organizations, claim.subject)
        object_local_id = _organization_local_id(organizations, claim.object_value)
        evidence_local_id = evidence_local_ids_by_segment.get(claim.source_segment_label)
        if evidence_local_id is None:
            evidence_local_id = f"evidence_{len(evidence) + 1:02d}"
            evidence_local_ids_by_segment[claim.source_segment_label] = evidence_local_id
            evidence.append(
                GroundedEvidenceCandidate(
                    local_id=evidence_local_id,
                    text_view_id=bound_evidence.text_view_id,
                    start_char=bound_evidence.start_char + segment.start_char,
                    end_char=bound_evidence.start_char + segment.end_char,
                    exact_text=segment.exact_text,
                    node_ids=bound_evidence.node_ids,
                    pdf_region_ids=bound_evidence.pdf_region_ids,
                    prefix_text=bound_evidence.exact_text[
                        max(0, segment.start_char - 32) : segment.start_char
                    ],
                    suffix_text=bound_evidence.exact_text[segment.end_char : segment.end_char + 32],
                )
            )
        assertions.append(
            GroundedAssertionCandidate(
                local_id=f"assertion_{index:02d}",
                subject_organization_local_id=subject_local_id,
                evidence_local_id=evidence_local_id,
                relation_label=claim.relation,
                object=GroundedOrganizationReferenceObject(object_local_id),
            )
        )
    return (
        GroundedCandidateBatchInput(
            task_fingerprint=task.task_fingerprint,
            source_id=extraction_input.source_id,
            document_id=extraction_input.document_id,
            representation_id=extraction_input.representation_id,
            model_name=extraction_input.execution_spec.model_identity.name,
            prompt_id=manifest.prompt_id,
            validator_version=extraction_input.validator_version,
            submitted_at=submitted_at,
            organizations=tuple(
                GroundedOrganizationCandidate(local_id, name)
                for name, local_id in organizations.items()
            ),
            evidence=tuple(evidence),
            assertions=tuple(assertions),
            originating_model_run_id=model_run_id,
        ),
        {
            "contract": "paragraph_hypothesis_text_v1",
            "unique_claim_count": len(ordered),
            "duplicate_claim_lines": cast(list[JsonValue], duplicate_lines),
        },
    )


def _verify_hypothesis_batch(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    extraction_task: ExtractionTask,
    extraction_model_run_id: str,
    output: HypothesisBatch,
    ledger_repository: StagedExtractionLedger,
    archive_store: ModelOutputArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    clock: ModelRunClock,
    submitted_at: datetime,
) -> tuple[HypothesisBatch, dict[str, JsonValue]]:
    """Keep only hypotheses that a separately archived verifier accepts."""
    verifier = extraction_input.hypothesis_verifier
    if verifier is None:
        return output, {}
    bundle = ledger_repository.get_document_representation_bundle(
        extraction_input.representation_id
    )
    if bundle is None:
        raise ValueError("Hypothesis verifier references a missing DocumentRepresentation.")
    bound_evidence = _resolved_bound_evidence_candidate(
        _bound_evidence_candidate(manifest),
        {node.id: node for node in bundle.nodes},
        {text_view.id: text_view for text_view in bundle.text_views},
    )
    if manifest.source_segment_policy_id not in {
        PARAGRAPH_SEGMENT_V1,
        PARAGRAPH_SEGMENT_V2,
        PARAGRAPH_SEGMENT_V3,
    }:
        raise ValueError("Hypothesis verifier requires a paragraph source segment policy.")
    segments = {
        segment.label: segment
        for segment in paragraph_source_segments(
            bound_evidence.exact_text, manifest.source_segment_policy_id
        )
    }
    accepted: list[AtomicHypothesis] = []
    verifier_run_ids: list[str] = []
    rejected_count = 0
    for claim in output.claims:
        segment = segments.get(claim.source_segment_label)
        if segment is None:
            raise ValueError("Hypothesis claim references an unknown source segment.")
        _require_hypothesis_source_grounded(
            claim.subject,
            segment.exact_text,
            manifest.source_segment_policy_id,
            "Hypothesis subject",
        )
        _require_hypothesis_source_grounded(
            claim.object_value,
            segment.exact_text,
            manifest.source_segment_policy_id,
            "Hypothesis object",
        )
        verdict, verifier_run_id = _run_hypothesis_verifier(
            extraction_input,
            manifest,
            extraction_task,
            extraction_model_run_id,
            claim,
            segment.exact_text,
            ledger_repository,
            archive_store,
            model_runtime,
            model_run_id_factory,
            clock,
            submitted_at,
        )
        verifier_run_ids.append(verifier_run_id)
        if verdict.accepted:
            accepted.append(claim)
        else:
            rejected_count += 1
    return HypothesisBatch(tuple(accepted)), {
        "faithfulness_verifier_contract": "hypothesis_faithfulness_text_v1",
        "faithfulness_verifier_model_run_ids": cast(list[JsonValue], verifier_run_ids),
        "faithfulness_accepted_claim_count": len(accepted),
        "faithfulness_rejected_claim_count": rejected_count,
    }


def _run_hypothesis_verifier(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    extraction_task: ExtractionTask,
    extraction_model_run_id: str,
    claim: AtomicHypothesis,
    source_segment: str,
    ledger_repository: StagedExtractionLedger,
    archive_store: ModelOutputArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    clock: ModelRunClock,
    submitted_at: datetime,
) -> tuple[HypothesisFaithfulnessVerdict, str]:
    verifier = extraction_input.hypothesis_verifier
    if verifier is None:
        raise ValueError("Hypothesis verifier is required.")
    rendered_input = _render_hypothesis_verifier_input(verifier.prompt_bytes, claim, source_segment)
    execution_spec = ModelExecutionSpec(
        model_profile_id=extraction_input.execution_spec.model_profile_id,
        model_identity=extraction_input.execution_spec.model_identity,
        generation_parameters=extraction_input.execution_spec.generation_parameters,
        prompt_id=verifier.prompt_id,
        prompt_digest=hashlib.sha256(verifier.prompt_bytes).hexdigest(),
        schema_id="hypothesis_faithfulness_text_v1",
        schema_digest=hashlib.sha256(hypothesis_faithfulness_text_schema_bytes()).hexdigest(),
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=hashlib.sha256(rendered_input).hexdigest(),
        output_contract_version="hypothesis_faithfulness_text_v1",
    )
    task = _hypothesis_verification_task(
        extraction_input,
        manifest,
        extraction_model_run_id,
        claim,
        execution_spec,
        rendered_input,
    )
    ledger_repository.save_extraction_task(task)
    model_run_id = model_run_id_factory.new_model_run_id()
    request = ModelTaskRequest(
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        task_type="hypothesis_faithfulness_verification",
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input=rendered_input,
        rendered_input_digest=execution_spec.rendered_input_digest,
        execution_spec=execution_spec,
    )
    started_at = clock.now()
    monotonic_started = clock.monotonic_seconds()
    deadline_milliseconds = _deadline_milliseconds(model_runtime.task_deadline_seconds)
    try:
        response = model_runtime.run_model_task(request)
    except Exception as exc:
        completed_at, diagnostics = _completed_diagnostics(
            clock, monotonic_started, deadline_milliseconds, None
        )
        run = _model_run(
            extraction_input,
            manifest,
            task,
            model_run_id,
            ModelRunStatus.RUNTIME_FAILED,
            started_at=started_at,
            completed_at=completed_at,
            execution_diagnostics=diagnostics,
            execution_spec=execution_spec,
            task_metadata_extra={"verifies_model_run_id": extraction_model_run_id},
            error=exc,
        )
        ledger_repository.save_model_run(run)
        return HypothesisFaithfulnessVerdict(False, "verifier_runtime_failed"), model_run_id
    completed_at, diagnostics = _completed_diagnostics(
        clock,
        monotonic_started,
        deadline_milliseconds,
        response.first_response_event_milliseconds,
    )
    output_digest = hashlib.sha256(response.raw_output).hexdigest()
    try:
        archive_store.put_model_run_output(model_run_id, response.raw_output, output_digest)
        _validate_execution_receipt(
            response.execution_receipt,
            execution_spec,
            manifest,
            expected_input_token_count=len(rendered_input.decode("utf-8").split()),
        )
        verdict = _parse_hypothesis_faithfulness_verdict(response.raw_output)
    except (ValidationError, ValueError) as exc:
        run = _model_run(
            extraction_input,
            manifest,
            task,
            model_run_id,
            ModelRunStatus.INVALID_OUTPUT,
            started_at=started_at,
            completed_at=completed_at,
            execution_diagnostics=diagnostics,
            output_digest=output_digest,
            execution_receipt=response.execution_receipt,
            execution_spec=execution_spec,
            task_metadata_extra={"verifies_model_run_id": extraction_model_run_id},
            error=exc,
        )
        ledger_repository.save_model_run(run)
        return HypothesisFaithfulnessVerdict(False, "verifier_invalid_output"), model_run_id
    run = _model_run(
        extraction_input,
        manifest,
        task,
        model_run_id,
        ModelRunStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=completed_at,
        execution_diagnostics=diagnostics,
        output_digest=output_digest,
        execution_receipt=response.execution_receipt,
        execution_spec=execution_spec,
        task_metadata_extra={"verifies_model_run_id": extraction_model_run_id},
        outcome_metadata={
            "contract": "hypothesis_faithfulness_text_v1",
            "verdict": "accept" if verdict.accepted else "reject",
            "reason": verdict.reason,
        },
    )
    ledger_repository.save_model_run(run)
    return verdict, model_run_id


def _organization_local_id(organizations: dict[str, str], name: str) -> str:
    existing = organizations.get(name)
    if existing is not None:
        return existing
    local_id = f"org_{len(organizations) + 1:02d}"
    organizations[name] = local_id
    return local_id


def hypothesis_faithfulness_text_schema_bytes() -> bytes:
    return b"verdict: accept|reject\\nreason: <non-empty direct-prose rationale>\\n"


def _parse_hypothesis_faithfulness_verdict(raw_output: bytes) -> HypothesisFaithfulnessVerdict:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Hypothesis faithfulness output must be UTF-8 text.") from error
    fields = _semantic_draft_fields(text.splitlines())
    _require_semantic_draft_keys(fields, ("verdict", "reason"))
    if fields["verdict"] not in {"accept", "reject"}:
        raise ValueError("Hypothesis faithfulness verdict must be accept or reject.")
    return HypothesisFaithfulnessVerdict(fields["verdict"] == "accept", fields["reason"])


def _render_hypothesis_verifier_input(
    prompt_bytes: bytes, claim: AtomicHypothesis, source_segment: str
) -> bytes:
    return b"\n\n".join(
        (
            prompt_bytes.rstrip(),
            (
                "SOURCE SEGMENT:\n"
                f"{source_segment}\n\n"
                "HYPOTHESIS:\n"
                f"{claim.subject} | {claim.relation} | {claim.object_value}"
            ).encode(),
        )
    )


def _hypothesis_verification_task(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    extraction_model_run_id: str,
    claim: AtomicHypothesis,
    execution_spec: ModelExecutionSpec,
    rendered_input: bytes,
) -> ExtractionTask:
    fingerprint = _digest(
        {
            "task_type": "hypothesis_faithfulness_verification",
            "source_id": extraction_input.source_id,
            "document_id": extraction_input.document_id,
            "representation_id": extraction_input.representation_id,
            "context_manifest_digest": manifest.manifest_digest,
            "extraction_model_run_id": extraction_model_run_id,
            "claim": {
                "source_segment_label": claim.source_segment_label,
                "subject": claim.subject,
                "relation": claim.relation,
                "object_value": claim.object_value,
            },
            "rendered_input_digest": hashlib.sha256(rendered_input).hexdigest(),
            "execution_spec_digest": model_execution_spec_digest(execution_spec),
        }
    )
    return ExtractionTask(
        id=f"ext_{fingerprint[:HASH_ID_LENGTH]}",
        task_type="hypothesis_faithfulness_verification",
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        context_manifest_payload=cast(dict[str, JsonValue], _manifest_payload(manifest)),
        prompt_id=execution_spec.prompt_id,
        schema_id=execution_spec.schema_id,
        model_profile_id=execution_spec.model_profile_id,
        execution_spec_digest=model_execution_spec_digest(execution_spec),
        task_fingerprint=fingerprint,
        created_at=None,
    )


def _hypothesis_line(claim: AtomicHypothesis) -> str:
    return (
        f"claim: {claim.source_segment_label} | {claim.subject} | {claim.relation} | "
        f"{claim.object_value}"
    )


def _canonical_hypothesis_claims(
    claims: tuple[AtomicHypothesis, ...],
) -> tuple[AtomicHypothesis, ...]:
    return _canonical_hypothesis_claims_with_duplicates(claims)[0]


def _canonical_hypothesis_claims_with_duplicates(
    claims: tuple[AtomicHypothesis, ...],
) -> tuple[tuple[AtomicHypothesis, ...], list[str]]:
    """Keep the deterministic claim order that determines Assertion local IDs."""
    unique: dict[tuple[str, str, str, str], AtomicHypothesis] = {}
    duplicate_lines: list[str] = []
    for claim in claims:
        key = (claim.source_segment_label, claim.subject, claim.relation, claim.object_value)
        if key in unique:
            duplicate_lines.append(_hypothesis_line(claim))
        else:
            unique[key] = claim
    return (
        tuple(
            sorted(
                unique.values(),
                key=lambda claim: (
                    int(claim.source_segment_label.removeprefix("s")),
                    claim.subject,
                    claim.relation,
                    claim.object_value,
                ),
            )
        ),
        duplicate_lines,
    )


def _bound_evidence_candidate(manifest: ContextManifest) -> EvidenceCandidate:
    if len(manifest.evidence_candidates) != 1:
        raise ValueError("SemanticDraft task requires exactly one bound EvidenceCandidate.")
    return manifest.evidence_candidates[0]


def _resolved_bound_evidence_candidate(
    selected: EvidenceCandidate,
    nodes: Mapping[str, DocumentNode],
    text_views: Mapping[str, TextView],
) -> GroundedEvidenceCandidate:
    node = nodes.get(selected.node_id)
    if not isinstance(node, DocumentNode):
        raise ValueError("ContextManifest evidence candidate references an unknown DocumentNode.")
    text_view = text_views.get(node.text_view_id)
    if not isinstance(text_view, TextView):
        raise ValueError("ContextManifest evidence candidate references a missing TextView.")
    if (
        selected.text_view_id != text_view.id
        or selected.start_char != node.start_char
        or selected.end_char != node.end_char
        or selected.source_region_ids != node.source_region_ids
    ):
        raise ValueError(
            "ContextManifest evidence candidate does not match authoritative source state."
        )
    start_char = selected.start_char
    end_char = selected.end_char
    exact_text = text_view.text[start_char:end_char]
    return GroundedEvidenceCandidate(
        local_id="evidence_01",
        text_view_id=text_view.id,
        start_char=start_char,
        end_char=end_char,
        exact_text=exact_text,
        node_ids=(node.id,),
        pdf_region_ids=node.source_region_ids,
        prefix_text=text_view.text[max(node.start_char, start_char - 32) : start_char],
        suffix_text=text_view.text[end_char : min(node.end_char, end_char + 32)],
    )


@cache
def semantic_draft_text_schema_bytes() -> bytes:
    return (
        b"outcome: claim\n"
        b"subject: <source-grounded organization name>\n"
        b"relation: <ordinary-language relation label>\n"
        b"object_kind: organization|literal\n"
        b"object: <source-grounded object>\n\n"
        b"or\n\n"
        b"outcome: abstain\n"
        b"reason: <non-empty reason>\n"
    )


@cache
def paragraph_hypothesis_text_schema_bytes() -> bytes:
    return (
        b"claim: <sN> | <source-grounded organization subject> | "
        b"<ordinary-language relation label> | <source-grounded organization object>\n"
        b"... up to eight claim lines\n\n"
        b"or\n\n"
        b"abstain: <non-empty reason>\n"
    )


@cache
def organization_mention_text_schema_bytes() -> bytes:
    return (
        b"mention: <sN> | <literal organization name>\n"
        b"... one line for each distinct organization name\n\n"
        b"or\n\n"
        b"abstain: <non-empty reason>\n"
    )


@cache
def organization_qualification_text_schema_bytes() -> bytes:
    return (
        b"organization: <complete literal Organization expression>\n\n"
        b"or\n\n"
        b"reject: not an organization\n"
    )


@cache
def organization_qualification_label_schema_bytes() -> bytes:
    return b"organization\nnot_organization\nambiguous\n"


def _parse_organization_mention_batch(
    raw_output: bytes,
) -> OrganizationMentionBatch | OrganizationMentionBatchAbstention:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Organization mention output must be UTF-8 text.") from error
    lines = text.splitlines()
    if not lines or any(not line or line != line.strip() for line in lines):
        raise ValueError("Organization mention output must contain only trimmed non-empty lines.")
    if len(lines) == 1 and lines[0].startswith("abstain: "):
        reason = lines[0].removeprefix("abstain: ")
        if not reason:
            raise ValueError("Organization mention abstention requires a reason.")
        return OrganizationMentionBatchAbstention(reason)
    mentions: list[OrganizationMention] = []
    for line in lines:
        prefix, separator, remainder = line.partition(": ")
        if prefix != "mention" or not separator:
            raise ValueError("Organization mention lines must begin with 'mention: '.")
        parts = remainder.split(" | ")
        if len(parts) != 2 or any(not part for part in parts):
            raise ValueError("Organization mention lines must contain one label and one name.")
        source_segment_label, organization_text = parts
        if not source_segment_label.startswith("s") or not source_segment_label[1:].isdigit():
            raise ValueError("Organization mention labels must use the sN form.")
        mentions.append(OrganizationMention(source_segment_label, organization_text))
    if len({item.organization_text for item in mentions}) != len(mentions):
        raise ValueError("Organization mention output repeats a name.")
    return OrganizationMentionBatch(tuple(mentions))


def _parse_organization_qualification(
    raw_output: bytes,
) -> OrganizationQualification | OrganizationQualificationRejection:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Organization qualification output must be UTF-8 text.") from error
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0] or lines[0] != lines[0].strip():
        raise ValueError("Organization qualification output must contain one trimmed line.")
    line = lines[0]
    if line == "reject: not an organization":
        return OrganizationQualificationRejection("not an organization")
    if line.startswith("organization: "):
        organization_text = line.removeprefix("organization: ")
        if not organization_text:
            raise ValueError("Organization qualification requires a literal expression.")
        return OrganizationQualification(organization_text)
    raise ValueError("Organization qualification output does not match the contract.")


def _parse_organization_qualification_label(
    raw_output: bytes,
) -> OrganizationQualificationJudgment:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Organization qualification label must be UTF-8 text.") from error
    return parse_organization_qualification_output(text)


def _require_source_grounded(value: str, exact_text: str, label: str) -> None:
    if value not in exact_text:
        raise ValueError(f"{label} must occur in the bound EvidenceCandidate text.")


def _require_hypothesis_source_grounded(
    value: str, exact_text: str, source_segment_policy_id: str | None, label: str
) -> None:
    if value.casefold() in {"it", "the institute", "the company", "the department"}:
        raise ValueError(f"{label} must be a literal named organization mention.")
    source_text = (
        source_copy_view(exact_text)
        if source_segment_policy_id == PARAGRAPH_SEGMENT_V3
        else exact_text
    )
    _require_source_grounded(value, source_text, label)


def _task_metadata(manifest: ContextManifest) -> dict[str, JsonValue]:
    if manifest.source_segment_policy_id is None:
        return {}
    return {"source_segment_policy_id": manifest.source_segment_policy_id}


def _abstention_outcome_metadata(
    output: SemanticDraftAbstention
    | HypothesisBatchAbstention
    | OrganizationMentionBatchAbstention
    | OrganizationQualificationRejection
    | MentionProposalAbstention,
) -> dict[str, JsonValue]:
    if isinstance(output, MentionProposalAbstention):
        return {"contract": "hybrid_mention_proposal_text_v1", "proposal_count": 0}
    if isinstance(output, HypothesisBatchAbstention):
        contract = "paragraph_hypothesis_text_v1"
    elif isinstance(output, OrganizationMentionBatchAbstention):
        contract = "organization_mention_text_v1"
    elif isinstance(output, OrganizationQualificationRejection):
        contract = "organization_qualification_text_v1"
    else:
        contract = "semantic_draft_text_v1"
    return {"contract": contract, "unique_claim_count": 0, "duplicate_claim_lines": []}


def _manifest_payload(
    manifest: ContextManifest, *, task_local_input: bytes = b""
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": manifest.id,
        "manifest_digest": manifest.manifest_digest,
        "rendered_input_base64": base64.b64encode(manifest.rendered_input).decode("ascii"),
        "rendered_input_digest": manifest.rendered_input_digest,
        "selected_node_ids": [candidate.node_id for candidate in manifest.selected_candidates],
        "excluded": [
            {"node_id": item.candidate.node_id, "reason_code": item.reason_code}
            for item in manifest.excluded_candidates
        ],
    }
    if task_local_input:
        payload["task_local_input_base64"] = base64.b64encode(task_local_input).decode("ascii")
        payload["task_local_input_digest"] = hashlib.sha256(task_local_input).hexdigest()
    return payload


def _compose_task_input(rendered_context: bytes, task_local_input: bytes) -> bytes:
    if not task_local_input:
        return rendered_context
    return rendered_context + b"\n\n[task]\n" + task_local_input


def _settings_payload(settings: tuple[ExecutionSetting, ...]) -> dict[str, ExecutionScalar]:
    return {setting.key: setting.value for setting in settings}


def _model_identity_payload(identity: ModelIdentitySnapshot) -> dict[str, JsonValue]:
    return {
        "name": identity.name,
        "weights_digest": identity.weights_digest,
        "runtime": identity.runtime,
        "tokenizer_id": identity.tokenizer_id,
        "determinism_settings": cast(
            dict[str, JsonValue], _settings_payload(identity.determinism_settings)
        ),
    }


def model_identity_snapshot_digest(identity: ModelIdentitySnapshot) -> str:
    return _digest(_model_identity_payload(identity))


def generation_parameters_digest(settings: tuple[ExecutionSetting, ...]) -> str:
    return _digest(_settings_payload(settings))


def model_execution_spec_payload(spec: ModelExecutionSpec) -> dict[str, JsonValue]:
    return {
        "model_profile_id": spec.model_profile_id,
        "model_identity": _model_identity_payload(spec.model_identity),
        "generation_parameters": cast(
            dict[str, JsonValue], _settings_payload(spec.generation_parameters)
        ),
        "prompt_id": spec.prompt_id,
        "prompt_digest": spec.prompt_digest,
        "schema_id": spec.schema_id,
        "schema_digest": spec.schema_digest,
        "context_manifest_id": spec.context_manifest_id,
        "context_manifest_digest": spec.context_manifest_digest,
        "rendered_input_digest": spec.rendered_input_digest,
        "output_contract_version": spec.output_contract_version,
    }


def model_execution_spec_digest(spec: ModelExecutionSpec) -> str:
    return _digest(model_execution_spec_payload(spec))


def _validate_execution_spec(
    execution_spec: ModelExecutionSpec,
    manifest: ContextManifest,
    rendered_input: bytes,
    schema: PinnedTaskSchema,
) -> None:
    if execution_spec.model_profile_id != manifest.model_profile_id:
        raise ValueError("Model execution specification does not match ContextManifest profile.")
    if execution_spec.model_identity.tokenizer_id != manifest.tokenizer_id:
        raise ValueError("Model execution specification tokenizer does not match ContextManifest.")
    if (
        execution_spec.prompt_id != manifest.prompt_id
        or execution_spec.prompt_digest != manifest.prompt_digest
    ):
        raise ValueError("Model execution specification prompt does not match ContextManifest.")
    if (
        execution_spec.schema_id != manifest.schema_id
        or execution_spec.schema_digest != manifest.schema_digest
    ):
        raise ValueError("Model execution specification schema does not match ContextManifest.")
    if (
        execution_spec.context_manifest_id != manifest.id
        or execution_spec.context_manifest_digest != manifest.manifest_digest
    ):
        raise ValueError("Model execution specification does not match ContextManifest identity.")
    if execution_spec.rendered_input_digest != hashlib.sha256(rendered_input).hexdigest():
        raise ValueError("Model execution specification rendered input digest is incorrect.")
    if execution_spec.output_contract_version != schema.output_contract_version:
        raise ValueError(
            "Model execution specification output contract is not pinned by its schema."
        )


def _validate_execution_receipt(
    receipt: ModelExecutionReceipt,
    execution_spec: ModelExecutionSpec,
    manifest: ContextManifest,
    *,
    expected_input_token_count: int | None = None,
) -> None:
    if receipt.model_identity_digest != model_identity_snapshot_digest(
        execution_spec.model_identity
    ):
        raise ValueError("Model execution receipt identity does not match the execution spec.")
    if receipt.generation_parameters_digest != generation_parameters_digest(
        execution_spec.generation_parameters
    ):
        raise ValueError(
            "Model execution receipt generation parameters do not match the execution spec."
        )
    if receipt.rendered_input_digest != execution_spec.rendered_input_digest:
        raise ValueError("Model execution receipt input does not match the execution spec.")
    input_token_count = (
        manifest.input_token_count
        if expected_input_token_count is None
        else expected_input_token_count
    )
    if receipt.input_token_count != input_token_count:
        raise ValueError(
            "Model execution receipt input token count does not match ContextManifest."
        )


def _execution_receipt_payload(receipt: ModelExecutionReceipt) -> dict[str, JsonValue]:
    return {
        "model_identity_digest": receipt.model_identity_digest,
        "generation_parameters_digest": receipt.generation_parameters_digest,
        "rendered_input_digest": receipt.rendered_input_digest,
        "input_token_count": receipt.input_token_count,
        "output_token_count": receipt.output_token_count,
    }


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
