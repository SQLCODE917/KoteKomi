"""Bounded staged model extraction with immutable task and run lineage."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast

from kotekomi_domain import ExtractionTask, ModelRun, ModelRunStatus
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from kotekomi_application.context_planning import (
    ContextManifest,
    ContextManifestStatus,
    ContextPlanningLedger,
    render_context,
)
from kotekomi_application.grounded_candidates import (
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedCandidateLedger,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    ProposedChangeBatchOutcome,
    submit_grounded_candidate_batch,
)

HASH_ID_LENGTH = 24


class StagedExtractionLedger(GroundedCandidateLedger, ContextPlanningLedger, Protocol):
    def save_extraction_task(self, record: ExtractionTask) -> None: ...
    def save_model_run(self, record: ModelRun) -> None: ...


class ModelOutputArchive(Protocol):
    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...


@dataclass(frozen=True)
class ModelIdentity:
    name: str
    weights_digest: str | None
    runtime: str
    tokenizer_id: str
    determinism_settings: dict[str, str | int | float | bool | None]


@dataclass(frozen=True)
class ModelTaskRequest:
    extraction_task_id: str
    task_fingerprint: str
    task_type: str
    context_manifest_id: str
    rendered_input: bytes
    schema_id: str


@dataclass(frozen=True)
class ModelTaskResponse:
    raw_output: bytes


class ModelTaskRuntime(Protocol):
    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse: ...


class ModelRunIdFactory(Protocol):
    def new_model_run_id(self) -> str: ...


class Uuid4ModelRunIdFactory:
    def new_model_run_id(self) -> str:
        return f"mrn_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class BoundedExtractionInput:
    source_id: str
    document_id: str
    representation_id: str
    context_manifest: ContextManifest
    model_identity: ModelIdentity
    generation_parameters: dict[str, str | int | float | bool | None]
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
) -> BoundedExtractionOutcome:
    """Archive one raw response, validate its task-local candidates, then publish atomically."""
    manifest = extraction_input.context_manifest
    if manifest.status is not ContextManifestStatus.READY:
        raise ValueError("Bounded extraction requires a ready ContextManifest.")
    if manifest.representation_id != extraction_input.representation_id:
        raise ValueError("Bounded extraction ContextManifest does not match its representation.")
    task = _extraction_task(extraction_input)
    ledger_repository.save_extraction_task(task)
    model_run_id = model_run_id_factory.new_model_run_id()
    request = ModelTaskRequest(
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        task_type="claim_extraction",
        context_manifest_id=manifest.id,
        rendered_input=render_context(manifest, ledger_repository),
        schema_id=manifest.schema_id,
    )
    try:
        response = model_runtime.run_model_task(request)
    except Exception as exc:
        run = _model_run(
            extraction_input, task, model_run_id, ModelRunStatus.RUNTIME_FAILED, error=exc
        )
        ledger_repository.save_model_run(run)
        return BoundedExtractionOutcome(task, run, None)

    output_digest = hashlib.sha256(response.raw_output).hexdigest()
    archive_store.put_model_run_output(
        model_run_id,
        response.raw_output,
        output_digest,
    )
    try:
        parsed = _parse_output(response.raw_output, manifest)
        if isinstance(parsed, _AbstentionOutput):
            run = _model_run(
                extraction_input,
                task,
                model_run_id,
                ModelRunStatus.ABSTAINED,
                output_digest=output_digest,
            )
            ledger_repository.save_model_run(run)
            return BoundedExtractionOutcome(task, run, None)
        _validate_task_local_references(parsed, manifest)
        batch_input = _grounded_batch(
            extraction_input, task, model_run_id, parsed, ledger_repository
        )
        batch = submit_grounded_candidate_batch(batch_input, ledger_repository)
    except (ValidationError, ValueError) as exc:
        run = _model_run(
            extraction_input,
            task,
            model_run_id,
            ModelRunStatus.INVALID_OUTPUT,
            output_digest=output_digest,
            error=exc,
        )
        ledger_repository.save_model_run(run)
        return BoundedExtractionOutcome(task, run, None)

    run = _model_run(
        extraction_input,
        task,
        model_run_id,
        ModelRunStatus.SUCCEEDED,
        output_digest=output_digest,
    )
    ledger_repository.save_model_run(run)
    return BoundedExtractionOutcome(task, run, batch)


def _extraction_task(extraction_input: BoundedExtractionInput) -> ExtractionTask:
    manifest = extraction_input.context_manifest
    fingerprint = _digest(
        {
            "task_type": "claim_extraction",
            "source_id": extraction_input.source_id,
            "document_id": extraction_input.document_id,
            "representation_id": extraction_input.representation_id,
            "context_manifest_digest": manifest.manifest_digest,
            "prompt_id": manifest.prompt_id,
            "schema_id": manifest.schema_id,
            "model_profile_id": extraction_input.model_identity.name,
            "model_identity": _model_identity_payload(extraction_input.model_identity),
            "generation_parameters": extraction_input.generation_parameters,
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
        model_profile_id=extraction_input.model_identity.name,
        task_fingerprint=fingerprint,
        created_at=extraction_input.started_at,
    )


def _model_run(
    extraction_input: BoundedExtractionInput,
    task: ExtractionTask,
    model_run_id: str,
    status: ModelRunStatus,
    *,
    output_digest: str | None = None,
    error: Exception | None = None,
) -> ModelRun:
    return ModelRun(
        id=model_run_id,
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        model_identity=cast(
            dict[str, JsonValue], _model_identity_payload(extraction_input.model_identity)
        ),
        runtime_identity=extraction_input.model_identity.runtime,
        tokenizer_id=extraction_input.model_identity.tokenizer_id,
        prompt_digest=extraction_input.context_manifest.prompt_digest,
        schema_digest=extraction_input.context_manifest.schema_digest,
        generation_parameters=cast(dict[str, JsonValue], extraction_input.generation_parameters),
        raw_output_artifact_id=(model_run_id if output_digest is not None else None),
        output_digest=output_digest,
        status=status,
        error_code=(type(error).__name__ if error is not None else None),
        error_message=(str(error) if error is not None else None),
        started_at=extraction_input.started_at,
        completed_at=extraction_input.completed_at,
    )


def _parse_output(
    raw_output: bytes, manifest: ContextManifest
) -> _CandidateOutput | _AbstentionOutput:
    if hashlib.sha256(manifest.schema_bytes).hexdigest() != manifest.schema_digest:
        raise ValueError("ContextManifest schema_digest is corrupted.")
    if manifest.schema_bytes != staged_claim_output_schema_bytes():
        raise ValueError("ContextManifest schema bytes do not match the staged claim schema.")
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
    if parsed.schema_id != manifest.schema_id:
        raise ValueError("Model task output schema_id does not match the pinned task schema.")
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
        if not candidate.node_ids:
            raise ValueError("Candidate evidence requires at least one node reference.")
        unknown = set(candidate.node_ids) - visible_node_ids
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
        model_name=extraction_input.model_identity.name,
        prompt_id=extraction_input.context_manifest.prompt_id,
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
    nodes: dict[str, object],
    text_views: dict[str, object],
) -> GroundedEvidenceCandidate:
    from kotekomi_domain import DocumentNode, TextView

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


def _model_identity_payload(identity: ModelIdentity) -> dict[str, str | int | float | bool | None]:
    return {
        "name": identity.name,
        "weights_digest": identity.weights_digest,
        "runtime": identity.runtime,
        "tokenizer_id": identity.tokenizer_id,
        **identity.determinism_settings,
    }


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
