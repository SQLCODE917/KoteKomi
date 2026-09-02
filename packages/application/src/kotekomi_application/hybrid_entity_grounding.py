"""HP-3 eligibility, entity-link evidence, and immutable Preview contracts."""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, cast

from kotekomi_domain import ExtractionTask, ModelRun, ModelRunStatus
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageTrace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceKind,
    ReferenceStatus,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    HybridPreviewStatus,
    MentionBoundaryStatus,
    MentionCandidate,
    Referentiality,
)

HYBRID_ENTITY_GROUNDING_POLICY_ID = "hybrid_entity_grounding_v1"
ENTITY_LINK_SCHEMA_ID = "entity_linking_batch_v1"

_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_RECORD_ID_PATTERN = r"^[a-z]+_[a-f0-9]{24}$"
_WIKIDATA_ID_PATTERN = r"^Q[1-9][0-9]*$"


class EntityGroundingEligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class EntityGroundingEligibilityReason(StrEnum):
    SPECIFIC_ENTITY = "specific_entity"
    BOUNDARY_NOT_SELECTED = "boundary_not_selected"
    BOUNDARY_AMBIGUOUS = "boundary_ambiguous"
    INTERPRETATION_MISSING = "interpretation_missing"
    GENERIC_CLASS = "generic_class"
    ANAPHORIC = "anaphoric"
    REFERENTIALITY_UNCLEAR = "referentiality_unclear"
    REFERENCE_AMBIGUOUS = "reference_ambiguous"
    REFERENCE_ANAPHORIC = "reference_anaphoric"


class EntityLinkCandidateKind(StrEnum):
    KNOWLEDGE_BASE_ENTITY = "knowledge_base_entity"
    NIL = "nil"


class HybridEntityGroundingStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class EntityGroundingEligibility(BaseModel):
    """One terminal HP-3 eligibility decision for one HP-1 candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ege_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=_RECORD_ID_PATTERN)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    status: EntityGroundingEligibilityStatus
    reason: EntityGroundingEligibilityReason
    reference_decision_id: Annotated[str, Field(pattern=_RECORD_ID_PATTERN)] | None = None
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (self.status is EntityGroundingEligibilityStatus.ELIGIBLE) != (
            self.reason is EntityGroundingEligibilityReason.SPECIFIC_ENTITY
        ):
            raise ValueError("Entity grounding eligibility status and reason disagree.")
        expected = _id(
            "ege",
            self.candidate_id,
            self.source_segment_id,
            self.status.value,
            self.reason.value,
            self.reference_decision_id or "",
        )
        if self.id != expected:
            raise ValueError("EntityGroundingEligibility ID does not match its decision.")
        return self


class EntityLinkMention(BaseModel):
    """One exact caller-owned span sent to the entity linker."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=_RECORD_ID_PATTERN)]
    text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end <= self.start:
            raise ValueError("EntityLinkMention requires a valid half-open range.")
        return self


class EntityLinkingInput(BaseModel):
    """One authoritative SourceSegment and its ordered eligible mentions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    source_text: Annotated[str, Field(min_length=1)]
    mentions: tuple[EntityLinkMention, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("EntityLinkingInput source digest does not match its text.")
        if not self.mentions:
            raise ValueError("EntityLinkingInput requires at least one mention.")
        if tuple(
            sorted(self.mentions, key=lambda item: (item.start, item.end, item.candidate_id))
        ) != (self.mentions):
            raise ValueError("EntityLinkingInput mentions must use source order.")
        if len({item.candidate_id for item in self.mentions}) != len(self.mentions):
            raise ValueError("EntityLinkingInput repeats a mention candidate.")
        for mention in self.mentions:
            if (
                mention.end > len(self.source_text)
                or self.source_text[mention.start : mention.end] != mention.text
            ):
                raise ValueError("EntityLinkingInput mention does not match source characters.")
        return self


class EntityLinkCandidate(BaseModel):
    """One ranked external-identity or NIL proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rank: Annotated[int, Field(ge=1)]
    kind: EntityLinkCandidateKind
    wikidata_id: Annotated[str, Field(pattern=_WIKIDATA_ID_PATTERN)] | None = None
    wikipedia_title: Annotated[str, Field(min_length=1)] | None = None
    label: Annotated[str, Field(min_length=1)] | None = None
    score: float

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not math.isfinite(self.score):
            raise ValueError("EntityLinkCandidate score must be finite.")
        if self.kind is EntityLinkCandidateKind.NIL:
            if self.wikidata_id is not None or self.wikipedia_title is not None:
                raise ValueError("A NIL candidate cannot name an external identity.")
        elif self.wikidata_id is None:
            raise ValueError("A knowledge-base candidate requires a Wikidata ID.")
        return self


class EntityLinkerIdentity(BaseModel):
    """Pinned execution identity exposed by one EntityLinkingPort."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    producer_id: Annotated[str, Field(min_length=1)]
    model_id: Annotated[str, Field(min_length=1)]
    model_revision: Annotated[str, Field(min_length=1)]
    entity_set: Annotated[str, Field(min_length=1)]
    package_revision: Annotated[str, Field(min_length=1)]
    resource_manifest_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    runtime_identity: Annotated[str, Field(min_length=1)]
    timeout_seconds: Annotated[float, Field(gt=0)]


class EntityLinkerEvidence(BaseModel):
    """Adapter output for one exact caller-owned mention."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=_RECORD_ID_PATTERN)]
    returned_text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    candidates: tuple[EntityLinkCandidate, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start:
            raise ValueError("EntityLinkerEvidence requires a valid half-open range.")
        if tuple(item.rank for item in self.candidates) != tuple(
            range(1, len(self.candidates) + 1)
        ):
            raise ValueError("EntityLinkCandidate ranks must be contiguous from one.")
        external_ids = tuple(
            item.wikidata_id for item in self.candidates if item.wikidata_id is not None
        )
        if len(set(external_ids)) != len(external_ids):
            raise ValueError("EntityLinkerEvidence repeats an external identity.")
        return self


class EntityLinkingBatch(BaseModel):
    """Complete parsed output from one entity-linking request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    identity: EntityLinkerIdentity
    load_elapsed_ms: Annotated[int, Field(ge=0)]
    inference_elapsed_ms: Annotated[int, Field(ge=0)]
    evidences: tuple[EntityLinkerEvidence, ...]


class EntityLinkingExecution(BaseModel):
    """Typed output plus the exact canonical worker response bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    batch: EntityLinkingBatch
    raw_output: bytes


class EntityLinkingPort(Protocol):
    @property
    def identity(self) -> EntityLinkerIdentity: ...

    def link(self, request: EntityLinkingInput) -> EntityLinkingExecution: ...


class EntityLinkingOutputError(ValueError):
    """Invalid external response whose exact bytes remain available for audit."""

    def __init__(self, message: str, raw_output: bytes) -> None:
        self.raw_output = raw_output
        super().__init__(message)


class EntityLinkingRuntimeResponseError(RuntimeError):
    """Typed worker failure whose valid response bytes remain available for audit."""

    def __init__(self, message: str, raw_output: bytes) -> None:
        self.raw_output = raw_output
        super().__init__(message)


class EntityLinkEvidence(BaseModel):
    """One source-bound HP-3 result with complete model lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ele_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=_RECORD_ID_PATTERN)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    candidates: tuple[EntityLinkCandidate, ...]
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start:
            raise ValueError("EntityLinkEvidence requires a valid source range.")
        expected = _id(
            "ele",
            self.candidate_id,
            self.source_segment_id,
            self.source_text_sha256,
            self.text,
            str(self.start),
            str(self.end),
            self.extraction_task_id,
            self.model_run_id,
            *(
                f"{item.rank}:{item.kind.value}:{item.wikidata_id or ''}:{item.score}"
                for item in self.candidates
            ),
        )
        if self.id != expected:
            raise ValueError("EntityLinkEvidence ID does not match its evidence.")
        return self


class HybridEntityGroundingPreview(BaseModel):
    """Immutable derived evidence for one terminal HP-3 run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_entity_grounding_preview_v1"] = (
        "hybrid_entity_grounding_preview_v1"
    )
    id: Annotated[str, Field(pattern=r"^hgp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hrp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    mention_preview_id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    mention_preview_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    representation_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["hybrid_entity_grounding_v1"] = HYBRID_ENTITY_GROUNDING_POLICY_ID
    eligibility: tuple[EntityGroundingEligibility, ...]
    link_evidence: tuple[EntityLinkEvidence, ...] = ()
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: HybridEntityGroundingStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("eligibility IDs", tuple(item.id for item in self.eligibility)),
            ("link evidence IDs", tuple(item.id for item in self.link_evidence)),
            ("ExtractionTask IDs", self.extraction_task_ids),
            ("ModelRun IDs", self.model_run_ids),
            ("diagnostics", self.diagnostics),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"HybridEntityGroundingPreview repeats {label}.")
        eligibility_by_candidate = {item.candidate_id: item for item in self.eligibility}
        linked_candidate_ids = {item.candidate_id for item in self.link_evidence}
        if any(
            eligibility_by_candidate.get(candidate_id) is None
            or eligibility_by_candidate[candidate_id].status
            is not EntityGroundingEligibilityStatus.ELIGIBLE
            for candidate_id in linked_candidate_ids
        ):
            raise ValueError("EntityLinkEvidence requires eligible candidate evidence.")
        if any(
            item.extraction_task_id not in self.extraction_task_ids for item in self.link_evidence
        ):
            raise ValueError("EntityLinkEvidence ExtractionTask lineage is missing.")
        if any(item.model_run_id not in self.model_run_ids for item in self.link_evidence):
            raise ValueError("EntityLinkEvidence ModelRun lineage is missing.")
        trace_ids = {item.id for item in self.traces}
        if any(item.trace_id not in trace_ids for item in self.link_evidence):
            raise ValueError("EntityLinkEvidence trace lineage is missing.")
        if any(
            item.trace_id is not None and item.trace_id not in trace_ids
            for item in self.eligibility
        ):
            raise ValueError("Eligibility trace lineage is missing.")
        traces_by_run: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_run[trace.trace_run_id].append(trace)
        for trace_run in traces_by_run.values():
            validate_extraction_stage_trace_chain(tuple(trace_run))
        if self.terminal_status is HybridEntityGroundingStatus.BLOCKED and not self.diagnostics:
            raise ValueError("A blocked grounding Preview requires a diagnostic.")
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridEntityGroundingPreview ID does not match its contents.")
        return self


def evaluate_entity_grounding_eligibility(
    parent: HybridExtractionPreview,
    references: HybridReferencePreview,
) -> tuple[EntityGroundingEligibility, ...]:
    """Produce one deterministic eligibility result for every HP-1 candidate."""
    if references.parent_preview_id != parent.id:
        raise ValueError("HP-3 reference Preview does not name the HP-1 parent.")
    selected: set[str] = set()
    ambiguous: set[str] = set()
    for decision in parent.boundary_decisions:
        selected.update(decision.selected_candidate_ids)
        if decision.status is MentionBoundaryStatus.AMBIGUOUS:
            ambiguous.update(decision.candidate_ids)
    interpretations = {item.candidate_id: item for item in parent.interpretations}
    reference_by_candidate = {item.candidate_id: item for item in references.reference_decisions}
    results: list[EntityGroundingEligibility] = []
    for candidate in parent.candidates:
        reference = reference_by_candidate.get(candidate.id)
        if candidate.id in ambiguous:
            status, reason = _ineligible(EntityGroundingEligibilityReason.BOUNDARY_AMBIGUOUS)
        elif candidate.id not in selected:
            status, reason = _ineligible(EntityGroundingEligibilityReason.BOUNDARY_NOT_SELECTED)
        elif candidate.id not in interpretations:
            status, reason = _ineligible(EntityGroundingEligibilityReason.INTERPRETATION_MISSING)
        elif interpretations[candidate.id].referentiality is Referentiality.GENERIC_CLASS:
            status, reason = _ineligible(EntityGroundingEligibilityReason.GENERIC_CLASS)
        elif interpretations[candidate.id].referentiality is Referentiality.ANAPHORIC:
            status, reason = _ineligible(EntityGroundingEligibilityReason.ANAPHORIC)
        elif interpretations[candidate.id].referentiality is Referentiality.UNCLEAR:
            status, reason = _ineligible(EntityGroundingEligibilityReason.REFERENTIALITY_UNCLEAR)
        elif reference is not None and reference.status is ReferenceStatus.AMBIGUOUS:
            status, reason = _ineligible(EntityGroundingEligibilityReason.REFERENCE_AMBIGUOUS)
        elif reference is not None and reference.reference_kind is ReferenceKind.ANAPHORIC:
            status, reason = _ineligible(EntityGroundingEligibilityReason.REFERENCE_ANAPHORIC)
        else:
            status = EntityGroundingEligibilityStatus.ELIGIBLE
            reason = EntityGroundingEligibilityReason.SPECIFIC_ENTITY
        reference_id = reference.id if reference is not None else None
        results.append(
            EntityGroundingEligibility(
                id=_id(
                    "ege",
                    candidate.id,
                    candidate.source_segment_id,
                    status.value,
                    reason.value,
                    reference_id or "",
                ),
                candidate_id=candidate.id,
                source_segment_id=candidate.source_segment_id,
                status=status,
                reason=reason,
                reference_decision_id=reference_id,
            )
        )
    return tuple(results)


def build_entity_linking_inputs(
    *,
    eligibility: tuple[EntityGroundingEligibility, ...],
    candidates: tuple[MentionCandidate, ...],
    source_text_by_id: dict[str, str],
) -> tuple[EntityLinkingInput, ...]:
    """Build exact per-SourceSegment requests without admitting ineligible mentions."""
    if tuple(item.candidate_id for item in eligibility) != tuple(item.id for item in candidates):
        raise ValueError("Entity-grounding eligibility must cover candidates in source order.")
    candidate_by_id = {item.id: item for item in candidates}
    eligible_by_segment: dict[str, list[MentionCandidate]] = {}
    for decision in eligibility:
        if decision.status is not EntityGroundingEligibilityStatus.ELIGIBLE:
            continue
        candidate = candidate_by_id[decision.candidate_id]
        eligible_by_segment.setdefault(candidate.source_segment_id, []).append(candidate)
    requests: list[EntityLinkingInput] = []
    for source_segment_id, segment_candidates in eligible_by_segment.items():
        try:
            source_text = source_text_by_id[source_segment_id]
        except KeyError as error:
            raise ValueError("Eligible mention references an unknown SourceSegment.") from error
        requests.append(
            EntityLinkingInput(
                source_segment_id=source_segment_id,
                source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
                source_text=source_text,
                mentions=tuple(
                    EntityLinkMention(
                        candidate_id=item.id,
                        text=item.text,
                        start=item.start,
                        end=item.end,
                    )
                    for item in segment_candidates
                ),
            )
        )
    return tuple(requests)


def entity_grounding_terminal_status(
    *,
    parent_status: HybridPreviewStatus,
    required_batches: int,
    successful_batches: int,
) -> HybridEntityGroundingStatus:
    """Derive the HP-3 terminal result from parent and batch outcomes."""
    if required_batches < 0 or successful_batches < 0:
        raise ValueError("Entity-grounding batch counts cannot be negative.")
    if successful_batches > required_batches:
        raise ValueError("Successful entity-grounding batches cannot exceed required batches.")
    if required_batches == 0:
        return (
            HybridEntityGroundingStatus.COMPLETE
            if parent_status is HybridPreviewStatus.COMPLETE
            else HybridEntityGroundingStatus.PARTIAL
        )
    if successful_batches == 0:
        return HybridEntityGroundingStatus.BLOCKED
    if successful_batches < required_batches or parent_status is HybridPreviewStatus.PARTIAL:
        return HybridEntityGroundingStatus.PARTIAL
    return HybridEntityGroundingStatus.COMPLETE


def build_hybrid_entity_grounding_preview_record(
    **values: object,
) -> HybridEntityGroundingPreview:
    payload = dict(values)
    payload.pop("id", None)
    payload.setdefault("schema_version", "hybrid_entity_grounding_preview_v1")
    payload.setdefault("policy_id", HYBRID_ENTITY_GROUNDING_POLICY_ID)
    normalized = cast(dict[str, JsonValue], json.loads(_canonical_json(payload)))
    normalized["id"] = _preview_id(normalized)
    return HybridEntityGroundingPreview.model_validate_json(_canonical_json(normalized))


def canonical_hybrid_entity_grounding_preview_bytes(
    preview: HybridEntityGroundingPreview,
) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode()


def hybrid_entity_grounding_preview_sha256(preview: HybridEntityGroundingPreview) -> str:
    return hashlib.sha256(canonical_hybrid_entity_grounding_preview_bytes(preview)).hexdigest()


def hybrid_entity_grounding_preview_from_bytes(payload: bytes) -> HybridEntityGroundingPreview:
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("HybridEntityGroundingPreview is not valid JSON.") from error
    preview = HybridEntityGroundingPreview.model_validate_json(payload)
    if canonical_hybrid_entity_grounding_preview_bytes(preview) != payload:
        raise ValueError("HybridEntityGroundingPreview does not use canonical encoding.")
    return preview


def entity_link_evidence_id(
    *,
    candidate_id: str,
    source_segment_id: str,
    source_text_sha256: str,
    text: str,
    start: int,
    end: int,
    extraction_task_id: str,
    model_run_id: str,
    candidates: tuple[EntityLinkCandidate, ...],
) -> str:
    return _id(
        "ele",
        candidate_id,
        source_segment_id,
        source_text_sha256,
        text,
        str(start),
        str(end),
        extraction_task_id,
        model_run_id,
        *(
            f"{item.rank}:{item.kind.value}:{item.wikidata_id or ''}:{item.score}"
            for item in candidates
        ),
    )


class EntityGroundingExecutionLedger(Protocol):
    def save_extraction_task(self, record: ExtractionTask) -> None: ...

    def save_model_run(self, record: ModelRun) -> None: ...


class EntityGroundingOutputArchive(Protocol):
    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object: ...


@dataclass(frozen=True)
class RecordedEntityLinkingOutcome:
    extraction_task: ExtractionTask
    model_run: ModelRun
    batch: EntityLinkingBatch | None


def run_recorded_entity_linking(
    *,
    representation_id: str,
    context_manifest_id: str,
    context_manifest_digest: str,
    context_manifest_payload: dict[str, JsonValue],
    request: EntityLinkingInput,
    linker: EntityLinkingPort,
    ledger: EntityGroundingExecutionLedger,
    archive: EntityGroundingOutputArchive,
) -> RecordedEntityLinkingOutcome:
    """Run one exact SourceSegment batch and retain its immutable task/run evidence."""
    identity = linker.identity
    input_bytes = _canonical_json(request.model_dump(mode="json")).encode()
    prompt_bytes = b"refined caller-owned spans; no semantic identity acceptance"
    schema_bytes = ENTITY_LINK_SCHEMA_ID.encode()
    task_payload: dict[str, JsonValue] = {
        "task_type": "hybrid_entity_grounding",
        "representation_id": representation_id,
        "context_manifest_id": context_manifest_id,
        "context_manifest_digest": context_manifest_digest,
        "source_segment_id": request.source_segment_id,
        "source_text_sha256": request.source_text_sha256,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "identity": identity.model_dump(mode="json"),
        "policy_id": HYBRID_ENTITY_GROUNDING_POLICY_ID,
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
    }
    task_fingerprint = hashlib.sha256(_canonical_json(task_payload).encode()).hexdigest()
    execution_spec_digest = hashlib.sha256(
        _canonical_json({"task": task_payload, "runtime": identity.runtime_identity}).encode()
    ).hexdigest()
    task = ExtractionTask(
        id=f"ext_{task_fingerprint[:24]}",
        task_type="hybrid_entity_grounding",
        context_manifest_id=context_manifest_id,
        context_manifest_digest=context_manifest_digest,
        context_manifest_payload=context_manifest_payload,
        input_candidate_ids=tuple(item.candidate_id for item in request.mentions),
        prompt_id="refined_caller_spans_v1",
        schema_id=ENTITY_LINK_SCHEMA_ID,
        model_profile_id=identity.model_revision,
        execution_spec_digest=execution_spec_digest,
        task_fingerprint=task_fingerprint,
    )
    ledger.save_extraction_task(task)
    model_run_id = f"mrn_{uuid.uuid4().hex}"
    started_at = datetime.now(UTC)
    monotonic_started = time.monotonic()
    try:
        execution = linker.link(request)
    except EntityLinkingRuntimeResponseError as error:
        return _record_failed_entity_linking_response(
            error=error,
            task=task,
            model_run_id=model_run_id,
            identity=identity,
            input_bytes=input_bytes,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            started_at=started_at,
            monotonic_started=monotonic_started,
            ledger=ledger,
            archive=archive,
        )
    except EntityLinkingOutputError as error:
        return _record_invalid_entity_linking_output(
            error=error,
            task=task,
            model_run_id=model_run_id,
            identity=identity,
            input_bytes=input_bytes,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            started_at=started_at,
            monotonic_started=monotonic_started,
            ledger=ledger,
            archive=archive,
        )
    except Exception as error:
        run = _entity_linking_model_run(
            model_run_id=model_run_id,
            task=task,
            identity=identity,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.RUNTIME_FAILED,
            started_at=started_at,
            elapsed_milliseconds=_elapsed_ms(monotonic_started),
            error=error,
        )
        ledger.save_model_run(run)
        return RecordedEntityLinkingOutcome(task, run, None)
    if execution.batch.identity != identity:
        raise ValueError("Entity-linking batch identity changed across the Port boundary.")
    output_digest = hashlib.sha256(execution.raw_output).hexdigest()
    receipt = _execution_receipt(identity, input_bytes, execution.raw_output)
    try:
        archive.put_model_run_output(model_run_id, execution.raw_output, output_digest)
    except Exception as error:
        run = _entity_linking_model_run(
            model_run_id=model_run_id,
            task=task,
            identity=identity,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.OUTPUT_ARCHIVE_FAILED,
            started_at=started_at,
            elapsed_milliseconds=_elapsed_ms(monotonic_started),
            execution_receipt=receipt,
            error=error,
        )
        ledger.save_model_run(run)
        return RecordedEntityLinkingOutcome(task, run, None)
    run = _entity_linking_model_run(
        model_run_id=model_run_id,
        task=task,
        identity=identity,
        prompt_bytes=prompt_bytes,
        schema_bytes=schema_bytes,
        execution_spec_digest=execution_spec_digest,
        status=ModelRunStatus.SUCCEEDED,
        started_at=started_at,
        elapsed_milliseconds=_elapsed_ms(monotonic_started),
        output_digest=output_digest,
        execution_receipt=receipt,
        outcome_metadata={
            "evidence_count": len(execution.batch.evidences),
            "candidate_count": sum(len(item.candidates) for item in execution.batch.evidences),
            "source_segment_id": request.source_segment_id,
        },
    )
    ledger.save_model_run(run)
    return RecordedEntityLinkingOutcome(task, run, execution.batch)


def _record_failed_entity_linking_response(
    *,
    error: EntityLinkingRuntimeResponseError,
    task: ExtractionTask,
    model_run_id: str,
    identity: EntityLinkerIdentity,
    input_bytes: bytes,
    prompt_bytes: bytes,
    schema_bytes: bytes,
    execution_spec_digest: str,
    started_at: datetime,
    monotonic_started: float,
    ledger: EntityGroundingExecutionLedger,
    archive: EntityGroundingOutputArchive,
) -> RecordedEntityLinkingOutcome:
    output_digest = hashlib.sha256(error.raw_output).hexdigest()
    receipt = _execution_receipt(identity, input_bytes, error.raw_output)
    try:
        archive.put_model_run_output(model_run_id, error.raw_output, output_digest)
    except Exception as archive_error:
        run = _entity_linking_model_run(
            model_run_id=model_run_id,
            task=task,
            identity=identity,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.OUTPUT_ARCHIVE_FAILED,
            started_at=started_at,
            elapsed_milliseconds=_elapsed_ms(monotonic_started),
            execution_receipt=receipt,
            error=archive_error,
        )
    else:
        run = _entity_linking_model_run(
            model_run_id=model_run_id,
            task=task,
            identity=identity,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.RUNTIME_FAILED,
            started_at=started_at,
            elapsed_milliseconds=_elapsed_ms(monotonic_started),
            output_digest=output_digest,
            execution_receipt=receipt,
            error=error,
        )
    ledger.save_model_run(run)
    return RecordedEntityLinkingOutcome(task, run, None)


def _record_invalid_entity_linking_output(
    *,
    error: EntityLinkingOutputError,
    task: ExtractionTask,
    model_run_id: str,
    identity: EntityLinkerIdentity,
    input_bytes: bytes,
    prompt_bytes: bytes,
    schema_bytes: bytes,
    execution_spec_digest: str,
    started_at: datetime,
    monotonic_started: float,
    ledger: EntityGroundingExecutionLedger,
    archive: EntityGroundingOutputArchive,
) -> RecordedEntityLinkingOutcome:
    output_digest = hashlib.sha256(error.raw_output).hexdigest()
    receipt = _execution_receipt(identity, input_bytes, error.raw_output)
    try:
        archive.put_model_run_output(model_run_id, error.raw_output, output_digest)
    except Exception as archive_error:
        run = _entity_linking_model_run(
            model_run_id=model_run_id,
            task=task,
            identity=identity,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.OUTPUT_ARCHIVE_FAILED,
            started_at=started_at,
            elapsed_milliseconds=_elapsed_ms(monotonic_started),
            execution_receipt=receipt,
            error=archive_error,
        )
    else:
        run = _entity_linking_model_run(
            model_run_id=model_run_id,
            task=task,
            identity=identity,
            prompt_bytes=prompt_bytes,
            schema_bytes=schema_bytes,
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.INVALID_OUTPUT,
            started_at=started_at,
            elapsed_milliseconds=_elapsed_ms(monotonic_started),
            output_digest=output_digest,
            execution_receipt=receipt,
            error=error,
        )
    ledger.save_model_run(run)
    return RecordedEntityLinkingOutcome(task, run, None)


def _entity_linking_model_run(
    *,
    model_run_id: str,
    task: ExtractionTask,
    identity: EntityLinkerIdentity,
    prompt_bytes: bytes,
    schema_bytes: bytes,
    execution_spec_digest: str,
    status: ModelRunStatus,
    started_at: datetime,
    elapsed_milliseconds: int,
    output_digest: str | None = None,
    execution_receipt: dict[str, JsonValue] | None = None,
    outcome_metadata: dict[str, JsonValue] | None = None,
    error: Exception | None = None,
) -> ModelRun:
    return ModelRun(
        id=model_run_id,
        extraction_task_id=task.id,
        task_fingerprint=task.task_fingerprint,
        model_identity=identity.model_dump(mode="json"),
        runtime_identity=identity.runtime_identity,
        tokenizer_id="character_offsets_v1",
        prompt_digest=hashlib.sha256(prompt_bytes).hexdigest(),
        schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
        execution_spec_digest=execution_spec_digest,
        generation_parameters={},
        raw_output_artifact_id=(model_run_id if output_digest is not None else None),
        output_digest=output_digest,
        status=status,
        error_code=type(error).__name__ if error is not None else None,
        error_message=str(error) if error is not None else None,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        execution_diagnostics={
            "elapsed_milliseconds": elapsed_milliseconds,
            "deadline_milliseconds": round(identity.timeout_seconds * 1000),
            "first_response_event_milliseconds": None,
        },
        execution_receipt=execution_receipt,
        task_metadata={"authority": "derived_diagnostic"},
        outcome_metadata=outcome_metadata or {},
    )


def _execution_receipt(
    identity: EntityLinkerIdentity, input_bytes: bytes, output_bytes: bytes
) -> dict[str, JsonValue]:
    return {
        "model_identity_digest": hashlib.sha256(
            _canonical_json(identity.model_dump(mode="json")).encode()
        ).hexdigest(),
        "generation_parameters_digest": hashlib.sha256(b"{}").hexdigest(),
        "rendered_input_digest": hashlib.sha256(input_bytes).hexdigest(),
        "input_token_count": len(input_bytes.decode()),
        "output_token_count": len(output_bytes.decode()),
    }


def _elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _ineligible(
    reason: EntityGroundingEligibilityReason,
) -> tuple[EntityGroundingEligibilityStatus, EntityGroundingEligibilityReason]:
    return EntityGroundingEligibilityStatus.INELIGIBLE, reason


def _preview_id(payload: dict[str, JsonValue]) -> str:
    return f"hgp_{hashlib.sha256(_canonical_json(payload).encode()).hexdigest()[:24]}"


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    raise TypeError(f"Unsupported entity-grounding value: {type(value).__name__}")


def utc_now() -> datetime:
    return datetime.now(UTC)
