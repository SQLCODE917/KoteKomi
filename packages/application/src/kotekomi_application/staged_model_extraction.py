"""Bounded staged model extraction with immutable task and run lineage."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import Literal, Protocol, cast

from kotekomi_domain import DocumentNode, ExtractionTask, ModelRun, ModelRunStatus, TextView
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from kotekomi_application.context_planning import (
    ContextManifest,
    ContextManifestStatus,
    ContextPlanningLedger,
    ContextTokenizer,
    render_context,
    verify_context_manifest,
)
from kotekomi_application.grounded_candidates import (
    GroundedAssertionCandidate,
    GroundedCandidateBatchCommit,
    GroundedCandidateBatchInput,
    GroundedCandidateLedger,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    ProposedChangeBatchOutcome,
    prepare_grounded_candidate_batch,
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


class ModelTaskRuntime(Protocol):
    @property
    def configured_identity(self) -> ModelIdentitySnapshot: ...

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse: ...


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
    parse: Callable[[bytes], _CandidateOutput | _AbstentionOutput]

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_schema_bytes).hexdigest()


class TaskSchemaRegistry(Protocol):
    def resolve(self, schema_id: str) -> PinnedTaskSchema: ...


class StagedClaimTaskSchemaRegistry:
    """The versioned pinned schema registry for the initial claim task."""

    schema_id = "staged_claim_output_v1"

    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id != self.schema_id:
            raise ValueError(f"Unsupported staged task schema: {schema_id}")
        return PinnedTaskSchema(
            schema_id=self.schema_id,
            canonical_schema_bytes=staged_claim_output_schema_bytes(),
            output_contract_version="staged_claim_output_v1",
            parse=_parse_staged_claim_output,
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
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class BoundedExtractionOutcome:
    extraction_task: ExtractionTask
    model_run: ModelRun
    proposed_change_batch: ProposedChangeBatchOutcome | None


class _OrganizationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    local_id: str
    name: str
    organization_type: str | None = None


class _EvidenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    local_id: str
    node_id: str
    exact_quote: str
    node_local_start: int
    node_local_end: int


class _AssertionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    local_id: str
    subject_organization_local_id: str
    evidence_local_id: str
    predicate: str
    object_value: str


class _CandidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["candidates"]
    schema_id: str
    organizations: list[_OrganizationOutput]
    evidence: list[_EvidenceOutput]
    assertions: list[_AssertionOutput]


class _AbstentionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["abstain"]
    schema_id: str
    reason: str


def run_bounded_extraction(
    extraction_input: BoundedExtractionInput,
    ledger_repository: StagedExtractionLedger,
    archive_store: ModelOutputArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    schema_registry: TaskSchemaRegistry,
) -> BoundedExtractionOutcome:
    """Archive one raw response, validate its task-local candidates, then publish atomically."""
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
    rendered_input = render_context(
        manifest.id,
        ledger_repository,
        tokenizer,
        extraction_input.prompt_bytes,
        schema.canonical_schema_bytes,
    )
    _validate_execution_spec(execution_spec, manifest, rendered_input, schema)
    if model_runtime.configured_identity != execution_spec.model_identity:
        raise ValueError("Model runtime configured identity does not match the execution spec.")
    task = _extraction_task(extraction_input, manifest)
    ledger_repository.save_extraction_task(task)
    model_run_id = model_run_id_factory.new_model_run_id()
    request = ModelTaskRequest(
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        task_type="claim_extraction",
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input=rendered_input,
        rendered_input_digest=hashlib.sha256(rendered_input).hexdigest(),
        execution_spec=execution_spec,
    )
    try:
        response = model_runtime.run_model_task(request)
    except Exception as exc:
        run = _model_run(
            extraction_input, manifest, task, model_run_id, ModelRunStatus.RUNTIME_FAILED, error=exc
        )
        ledger_repository.save_model_run(run)
        return BoundedExtractionOutcome(task, run, None)

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
            execution_receipt=response.execution_receipt,
            error=exc,
        )
        ledger_repository.save_model_run(run)
        return BoundedExtractionOutcome(task, run, None)
    try:
        _validate_execution_receipt(response.execution_receipt, execution_spec, manifest)
        parsed = _parse_output(response.raw_output, manifest, schema)
        if isinstance(parsed, _AbstentionOutput):
            run = _model_run(
                extraction_input,
                manifest,
                task,
                model_run_id,
                ModelRunStatus.ABSTAINED,
                output_digest=output_digest,
                execution_receipt=response.execution_receipt,
                abstention_reason=parsed.reason,
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(task, run, None)
        _validate_task_local_references(parsed, manifest)
        batch_input = _grounded_batch(
            extraction_input, manifest, task, model_run_id, parsed, ledger_repository
        )
        batch_commit = prepare_grounded_candidate_batch(batch_input, ledger_repository)
    except (ValidationError, ValueError) as exc:
        run = _model_run(
            extraction_input,
            manifest,
            task,
            model_run_id,
            ModelRunStatus.INVALID_OUTPUT,
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
        output_digest=output_digest,
        execution_receipt=response.execution_receipt,
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
            output_digest=output_digest,
            execution_receipt=response.execution_receipt,
            error=exc,
        )
        ledger_repository.save_model_run(failed_run)
        return BoundedExtractionOutcome(task, failed_run, None)
    return BoundedExtractionOutcome(task, run, batch_commit.outcome)


def _extraction_task(
    extraction_input: BoundedExtractionInput, manifest: ContextManifest
) -> ExtractionTask:
    fingerprint = _digest(
        {
            "task_type": "claim_extraction",
            "source_id": extraction_input.source_id,
            "document_id": extraction_input.document_id,
            "representation_id": extraction_input.representation_id,
            "context_manifest_digest": manifest.manifest_digest,
            "prompt_id": manifest.prompt_id,
            "schema_id": manifest.schema_id,
            "execution_spec_digest": model_execution_spec_digest(extraction_input.execution_spec),
            "validator_version": extraction_input.validator_version,
        }
    )
    return ExtractionTask(
        id=f"ext_{fingerprint[:HASH_ID_LENGTH]}",
        task_type="claim_extraction",
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        context_manifest_payload=cast(dict[str, JsonValue], _manifest_payload(manifest)),
        prompt_id=manifest.prompt_id,
        schema_id=manifest.schema_id,
        model_profile_id=extraction_input.execution_spec.model_profile_id,
        execution_spec_digest=model_execution_spec_digest(extraction_input.execution_spec),
        task_fingerprint=fingerprint,
        created_at=None,
    )


def _model_run(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    task: ExtractionTask,
    model_run_id: str,
    status: ModelRunStatus,
    *,
    output_digest: str | None = None,
    execution_receipt: ModelExecutionReceipt | None = None,
    abstention_reason: str | None = None,
    error: Exception | None = None,
) -> ModelRun:
    return ModelRun(
        id=model_run_id,
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        model_identity=_model_identity_payload(extraction_input.execution_spec.model_identity),
        runtime_identity=extraction_input.execution_spec.model_identity.runtime,
        tokenizer_id=extraction_input.execution_spec.model_identity.tokenizer_id,
        prompt_digest=extraction_input.execution_spec.prompt_digest,
        schema_digest=extraction_input.execution_spec.schema_digest,
        execution_spec_digest=model_execution_spec_digest(extraction_input.execution_spec),
        generation_parameters=cast(
            dict[str, JsonValue],
            _settings_payload(extraction_input.execution_spec.generation_parameters),
        ),
        raw_output_artifact_id=(model_run_id if output_digest is not None else None),
        output_digest=output_digest,
        status=status,
        abstention_reason=abstention_reason,
        error_code=(type(error).__name__ if error is not None else None),
        error_message=(str(error) if error is not None else None),
        started_at=extraction_input.started_at,
        completed_at=extraction_input.completed_at,
        execution_receipt=(
            _execution_receipt_payload(execution_receipt) if execution_receipt is not None else None
        ),
    )


def _parse_output(
    raw_output: bytes, manifest: ContextManifest, schema: PinnedTaskSchema
) -> _CandidateOutput | _AbstentionOutput:
    if manifest.schema_id != schema.schema_id or manifest.schema_digest != schema.digest:
        raise ValueError("ContextManifest schema does not match the pinned task schema.")
    parsed = schema.parse(raw_output)
    if parsed.schema_id != schema.schema_id:
        raise ValueError("Model task output schema_id does not match the pinned task schema.")
    return parsed


def _parse_staged_claim_output(raw_output: bytes) -> _CandidateOutput | _AbstentionOutput:
    decoded = json.loads(raw_output)
    if not isinstance(decoded, dict):
        raise ValueError("Model task output must be a JSON object.")
    payload = cast(dict[str, object], decoded)
    kind = payload.get("kind")
    if kind == "candidates":
        parsed: _CandidateOutput | _AbstentionOutput = _CandidateOutput.model_validate(payload)
    elif kind == "abstain":
        parsed = _AbstentionOutput.model_validate(payload)
    else:
        raise ValueError("Model task output kind must be candidates or abstain.")
    return parsed


def _validate_task_local_references(
    output: _CandidateOutput,
    manifest: ContextManifest,
) -> None:
    visible_node_ids = {
        node_id
        for candidate in manifest.selected_candidates
        for node_id in candidate.source_node_ids
    }
    if not output.assertions:
        raise ValueError("Candidate output requires at least one assertion or an abstention.")
    for candidate in output.evidence:
        if not candidate.node_id:
            raise ValueError("Candidate evidence requires at least one node reference.")
        unknown = {candidate.node_id} - visible_node_ids
        if unknown:
            raise ValueError("Candidate evidence references nodes absent from the ContextManifest.")
    organization_ids = {candidate.local_id for candidate in output.organizations}
    evidence_ids = {candidate.local_id for candidate in output.evidence}
    if len(organization_ids) != len(output.organizations) or len(evidence_ids) != len(
        output.evidence
    ):
        raise ValueError("Candidate output local IDs must be unique within their task.")
    for candidate in output.assertions:
        if candidate.subject_organization_local_id not in organization_ids:
            raise ValueError("Candidate assertion references an unknown task-local organization.")
        if candidate.evidence_local_id not in evidence_ids:
            raise ValueError(
                "Candidate assertion references an unknown task-local evidence record."
            )


def _grounded_batch(
    extraction_input: BoundedExtractionInput,
    manifest: ContextManifest,
    task: ExtractionTask,
    model_run_id: str,
    output: _CandidateOutput,
    ledger_repository: StagedExtractionLedger,
) -> GroundedCandidateBatchInput:
    bundle = ledger_repository.get_document_representation_bundle(
        extraction_input.representation_id
    )
    if bundle is None:
        raise ValueError("Bounded extraction references a missing DocumentRepresentation.")
    nodes = {node.id: node for node in bundle.nodes}
    text_views = {text_view.id: text_view for text_view in bundle.text_views}
    evidence = tuple(
        _resolved_evidence_candidate(item, nodes, text_views) for item in output.evidence
    )
    return GroundedCandidateBatchInput(
        task_fingerprint=task.task_fingerprint,
        source_id=extraction_input.source_id,
        document_id=extraction_input.document_id,
        representation_id=extraction_input.representation_id,
        model_name=extraction_input.execution_spec.model_identity.name,
        prompt_id=manifest.prompt_id,
        validator_version=extraction_input.validator_version,
        submitted_at=extraction_input.completed_at,
        organizations=tuple(
            GroundedOrganizationCandidate(item.local_id, item.name, item.organization_type)
            for item in output.organizations
        ),
        evidence=evidence,
        assertions=tuple(
            GroundedAssertionCandidate(
                item.local_id,
                item.subject_organization_local_id,
                item.evidence_local_id,
                item.predicate,
                item.object_value,
            )
            for item in output.assertions
        ),
        originating_model_run_id=model_run_id,
    )


def _resolved_evidence_candidate(
    output: _EvidenceOutput,
    nodes: Mapping[str, DocumentNode],
    text_views: Mapping[str, TextView],
) -> GroundedEvidenceCandidate:
    node = nodes.get(output.node_id)
    if not isinstance(node, DocumentNode):
        raise ValueError("Candidate evidence references an unknown task-local DocumentNode.")
    text_view = text_views.get(node.text_view_id)
    if not isinstance(text_view, TextView):
        raise ValueError("Candidate evidence DocumentNode references a missing TextView.")
    if output.node_local_start < 0 or output.node_local_end > node.end_char - node.start_char:
        raise ValueError("Candidate evidence node-local offsets lie outside its visible node.")
    start_char = node.start_char + output.node_local_start
    end_char = node.start_char + output.node_local_end
    exact_text = text_view.text[start_char:end_char]
    if exact_text != output.exact_quote:
        raise ValueError("Candidate evidence exact_quote does not match its visible node offsets.")
    return GroundedEvidenceCandidate(
        local_id=output.local_id,
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
def staged_claim_output_schema_bytes() -> bytes:
    schema = TypeAdapter(_CandidateOutput | _AbstentionOutput).json_schema()
    return json.dumps(schema, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _manifest_payload(manifest: ContextManifest) -> dict[str, object]:
    return {
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
    if receipt.input_token_count != manifest.input_token_count:
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
