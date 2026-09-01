"""Source-grounded hybrid mention proposal and interpretation contracts."""

from __future__ import annotations

import hashlib
import json
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

from kotekomi_application.context_planning import SourceSegment
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageTrace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.mention_proposer import (
    MentionProposal,
    MentionProposalBatch,
    MentionProposalInput,
    MentionProposer,
)
from kotekomi_application.organization_mention_boundary_reconciliation import (
    reconcile_organization_mention_boundaries,
)
from kotekomi_application.organization_mention_qualification import (
    MentionCandidate as OrganizationMentionCandidate,
)
from kotekomi_application.organization_mention_qualification import (
    MentionProposalObservation as OrganizationMentionProposalObservation,
)

HYBRID_MENTION_BOUNDARY_POLICY_ID = "hybrid_mention_boundary_v1"
HYBRID_MENTION_PREVIEW_POLICY_ID = "hybrid_mention_preview_v1"
HYBRID_MENTION_TASK_SCHEMA_ID = "hybrid_mention_task_text_v1"

_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_ID_PATTERN = r"^[a-z]+_[a-f0-9]{24}$"


class Referentiality(StrEnum):
    SPECIFIC_ENTITY = "specific_entity"
    GENERIC_CLASS = "generic_class"
    ANAPHORIC = "anaphoric"
    UNCLEAR = "unclear"


class ContextualKind(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    GOVERNMENT = "government"
    GEOPOLITICAL_ENTITY = "geopolitical_entity"
    PLACE = "place"
    EVENT = "event"
    PROJECT = "project"
    INITIATIVE = "initiative"
    PRODUCT = "product"
    POLICY = "policy"
    PUBLICATION = "publication"
    OTHER = "other"
    UNCLEAR = "unclear"


class DiscourseRole(StrEnum):
    ACTOR = "actor"
    PARTICIPANT = "participant"
    ORIGIN = "origin"
    LOCATION = "location"
    OBJECT = "object"
    MODIFIER = "modifier"
    OTHER = "other"
    UNCLEAR = "unclear"


class MentionBoundaryStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNCONTESTED = "uncontested"


class HybridPreviewStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


PROPOSER_CONTEXTUAL_KINDS = tuple(
    sorted(
        kind.value
        for kind in ContextualKind
        if kind not in {ContextualKind.OTHER, ContextualKind.UNCLEAR}
    )
)


class MentionObservation(BaseModel):
    """One source-valid observation with complete proposer lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=_ID_PATTERN)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    type_hints: tuple[ContextualKind, ...]
    producer_id: Annotated[str, Field(min_length=1)]
    execution_record_id: Annotated[str, Field(min_length=1)]
    score: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start:
            raise ValueError("MentionObservation requires a valid half-open range.")
        if not self.type_hints:
            raise ValueError("MentionObservation requires at least one type hint.")
        if tuple(sorted(set(self.type_hints), key=lambda item: item.value)) != self.type_hints:
            raise ValueError("MentionObservation type hints must be ordered and distinct.")
        if tuple(sorted(set(self.diagnostics))) != self.diagnostics:
            raise ValueError("MentionObservation diagnostics must be ordered and distinct.")
        expected = _id(
            "mob",
            self.source_segment_id,
            str(self.start),
            str(self.end),
            self.text,
            self.producer_id,
            self.execution_record_id,
            *(hint.value for hint in self.type_hints),
        )
        if self.id != expected:
            raise ValueError("MentionObservation ID does not match its contents.")
        return self


class MentionCandidate(BaseModel):
    """One exact source span with every matching proposer observation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=_ID_PATTERN)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    observation_ids: tuple[Annotated[str, Field(pattern=_ID_PATTERN)], ...]
    type_hints: tuple[ContextualKind, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start:
            raise ValueError("MentionCandidate requires a valid half-open range.")
        _require_ordered_distinct("observation IDs", self.observation_ids)
        if not self.observation_ids:
            raise ValueError("MentionCandidate requires proposer evidence.")
        if not self.type_hints:
            raise ValueError("MentionCandidate requires at least one type hint.")
        if tuple(sorted(set(self.type_hints), key=lambda item: item.value)) != self.type_hints:
            raise ValueError("MentionCandidate type hints must be ordered and distinct.")
        expected = _id(
            "mnc",
            self.source_segment_id,
            self.source_text_sha256,
            str(self.start),
            str(self.end),
            self.text,
        )
        if self.id != expected:
            raise ValueError("MentionCandidate ID does not match its source span.")
        return self


class MentionBoundaryDecision(BaseModel):
    """One deterministic decision over an overlapping candidate component."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=_ID_PATTERN)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    status: MentionBoundaryStatus
    rule_id: Annotated[str, Field(min_length=1)]
    candidate_ids: tuple[Annotated[str, Field(pattern=_ID_PATTERN)], ...]
    selected_candidate_ids: tuple[Annotated[str, Field(pattern=_ID_PATTERN)], ...]
    preserved_candidate_ids: tuple[Annotated[str, Field(pattern=_ID_PATTERN)], ...]
    alias_evidence_candidate_ids: tuple[Annotated[str, Field(pattern=_ID_PATTERN)], ...] = ()
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("candidate IDs", self.candidate_ids),
            ("selected candidate IDs", self.selected_candidate_ids),
            ("preserved candidate IDs", self.preserved_candidate_ids),
            ("alias evidence candidate IDs", self.alias_evidence_candidate_ids),
            ("diagnostics", self.diagnostics),
        ):
            _require_ordered_distinct(label, values)
        if self.preserved_candidate_ids != self.candidate_ids:
            raise ValueError("MentionBoundaryDecision must preserve every candidate.")
        if not set(self.selected_candidate_ids).issubset(self.candidate_ids):
            raise ValueError("MentionBoundaryDecision selected an unknown candidate.")
        expected = _id(
            "mbd",
            HYBRID_MENTION_BOUNDARY_POLICY_ID,
            self.source_segment_id,
            self.rule_id,
            *self.candidate_ids,
        )
        if self.id != expected:
            raise ValueError("MentionBoundaryDecision ID does not match its contents.")
        return self


class MentionInterpretation(BaseModel):
    """One model judgment mapped from task-local labels to source identities."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=_ID_PATTERN)]
    candidate_id: Annotated[str, Field(pattern=_ID_PATTERN)]
    referentiality: Referentiality
    contextual_kind: ContextualKind
    discourse_role: DiscourseRole
    support_segment_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = _id(
            "mit",
            self.candidate_id,
            self.referentiality.value,
            self.contextual_kind.value,
            self.discourse_role.value,
            self.support_segment_id,
            self.model_run_id,
            self.trace_id,
        )
        if self.id != expected:
            raise ValueError("MentionInterpretation ID does not match its contents.")
        return self


class HybridExtractionPreview(BaseModel):
    """Immutable derived evidence for one terminal HP-1 run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_extraction_preview_v1"] = "hybrid_extraction_preview_v1"
    id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    context_manifest_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["hybrid_mention_preview_v1"] = HYBRID_MENTION_PREVIEW_POLICY_ID
    ontology_card_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    observations: tuple[MentionObservation, ...] = ()
    candidates: tuple[MentionCandidate, ...] = ()
    boundary_decisions: tuple[MentionBoundaryDecision, ...] = ()
    interpretations: tuple[MentionInterpretation, ...] = ()
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: HybridPreviewStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("extraction task IDs", self.extraction_task_ids),
            ("model run IDs", self.model_run_ids),
            ("diagnostics", self.diagnostics),
        ):
            _require_ordered_distinct(label, values)
        if self.terminal_status is HybridPreviewStatus.PARTIAL and not self.candidates:
            raise ValueError("A partial HybridExtractionPreview requires a MentionCandidate.")
        if tuple(sorted(self.observations, key=_observation_key)) != self.observations:
            raise ValueError("HybridExtractionPreview observations must use source order.")
        if tuple(sorted(self.candidates, key=_candidate_key)) != self.candidates:
            raise ValueError("HybridExtractionPreview candidates must use source order.")
        if (
            tuple(
                sorted(self.boundary_decisions, key=lambda item: (item.source_segment_id, item.id))
            )
            != self.boundary_decisions
        ):
            raise ValueError("HybridExtractionPreview boundary decisions must be ordered.")
        candidate_by_id = {item.id: item for item in self.candidates}
        if len(candidate_by_id) != len(self.candidates):
            raise ValueError("HybridExtractionPreview repeats a MentionCandidate.")
        observation_ids = {item.id for item in self.observations}
        if len(observation_ids) != len(self.observations):
            raise ValueError("HybridExtractionPreview repeats a MentionObservation.")
        if any(
            not set(candidate.observation_ids).issubset(observation_ids)
            for candidate in self.candidates
        ):
            raise ValueError("HybridExtractionPreview candidate evidence is incomplete.")
        candidate_observation_ids = {
            observation_id
            for candidate in self.candidates
            for observation_id in candidate.observation_ids
        }
        if candidate_observation_ids != observation_ids:
            raise ValueError("HybridExtractionPreview must retain every valid observation.")
        if any(
            observation.execution_record_id not in self.model_run_ids
            for observation in self.observations
        ):
            raise ValueError("HybridExtractionPreview observation ModelRun is missing.")
        decided_candidate_ids = tuple(
            candidate_id
            for decision in self.boundary_decisions
            for candidate_id in decision.candidate_ids
        )
        if len(set(decided_candidate_ids)) != len(decided_candidate_ids) or set(
            decided_candidate_ids
        ) != set(candidate_by_id):
            raise ValueError("HybridExtractionPreview decisions must partition its candidates.")
        if any(
            candidate_by_id[candidate_id].source_segment_id != decision.source_segment_id
            for decision in self.boundary_decisions
            for candidate_id in decision.candidate_ids
        ):
            raise ValueError("HybridExtractionPreview boundary source identity drifted.")
        selected_candidate_ids = {
            candidate_id
            for decision in self.boundary_decisions
            for candidate_id in decision.selected_candidate_ids
        }
        interpretation_candidate_ids = tuple(item.candidate_id for item in self.interpretations)
        if len(set(interpretation_candidate_ids)) != len(interpretation_candidate_ids) or not set(
            interpretation_candidate_ids
        ).issubset(selected_candidate_ids):
            raise ValueError(
                "HybridExtractionPreview interpretations reference invalid candidates."
            )
        expected_interpretation_order = tuple(
            sorted(
                self.interpretations,
                key=lambda item: (*_candidate_key(candidate_by_id[item.candidate_id]), item.id),
            )
        )
        if expected_interpretation_order != self.interpretations:
            raise ValueError("HybridExtractionPreview interpretations must use source order.")
        if self.terminal_status is HybridPreviewStatus.COMPLETE and (
            set(interpretation_candidate_ids) != selected_candidate_ids
        ):
            raise ValueError("A complete HybridExtractionPreview requires every interpretation.")
        if self.terminal_status is HybridPreviewStatus.PARTIAL and (
            set(interpretation_candidate_ids) == selected_candidate_ids
        ):
            raise ValueError("A partial HybridExtractionPreview requires a failed interpretation.")
        if self.terminal_status is HybridPreviewStatus.BLOCKED and any(
            (
                self.observations,
                self.candidates,
                self.boundary_decisions,
                self.interpretations,
            )
        ):
            raise ValueError(
                "A blocked HybridExtractionPreview cannot contain reconciled evidence."
            )
        if self.terminal_status is HybridPreviewStatus.BLOCKED and not self.diagnostics:
            raise ValueError("A blocked HybridExtractionPreview requires a diagnostic.")
        if (
            tuple(
                sorted(
                    self.traces, key=lambda item: (item.source_segment_id, item.ordinal, item.id)
                )
            )
            != self.traces
        ):
            raise ValueError("HybridExtractionPreview traces must be ordered.")
        trace_ids = {item.id for item in self.traces}
        if len(trace_ids) != len(self.traces):
            raise ValueError("HybridExtractionPreview repeats an ExtractionStageTrace.")
        if any(item.trace_id not in trace_ids for item in self.interpretations):
            raise ValueError("HybridExtractionPreview interpretation trace is missing.")
        if any(item.model_run_id not in self.model_run_ids for item in self.interpretations):
            raise ValueError("HybridExtractionPreview interpretation ModelRun is missing.")
        execution_ids = set(self.extraction_task_ids) | set(self.model_run_ids)
        if any(
            not set(trace.execution_record_ids).issubset(execution_ids) for trace in self.traces
        ):
            raise ValueError("HybridExtractionPreview trace execution evidence is missing.")
        traced_execution_ids = {
            execution_id for trace in self.traces for execution_id in trace.execution_record_ids
        }
        if traced_execution_ids != execution_ids:
            raise ValueError("HybridExtractionPreview must trace every execution record.")
        traced_source_segment_ids = {trace.source_segment_id for trace in self.traces}
        if any(
            interpretation.support_segment_id not in traced_source_segment_ids
            for interpretation in self.interpretations
        ):
            raise ValueError("HybridExtractionPreview interpretation support is missing.")
        traces_by_segment: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_segment[trace.source_segment_id].append(trace)
        for segment_traces in traces_by_segment.values():
            validate_extraction_stage_trace_chain(tuple(segment_traces))
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridExtractionPreview ID does not match its contents.")
        return self


class PreviewStore(Protocol):
    """Publish and reload immutable HybridExtractionPreview evidence."""

    def put_hybrid_extraction_preview(
        self,
        preview: HybridExtractionPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes: ...


class HybridExecutionLedger(Protocol):
    def save_extraction_task(self, record: ExtractionTask) -> None: ...
    def save_model_run(self, record: ModelRun) -> None: ...


class HybridModelOutputArchive(Protocol):
    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...


@dataclass(frozen=True)
class MentionProposalDraft:
    source_segment_label: str
    type_hints: tuple[ContextualKind, ...]
    text: str


@dataclass(frozen=True)
class MentionProposalDraftBatch:
    proposals: tuple[MentionProposalDraft, ...]


@dataclass(frozen=True)
class MentionProposalAbstention:
    reason: str


@dataclass(frozen=True)
class MentionInterpretationDraft:
    candidate_label: str
    referentiality: Referentiality
    contextual_kind: ContextualKind
    discourse_role: DiscourseRole
    support_segment_label: str


@dataclass(frozen=True)
class RecordedMentionProposalOutcome:
    extraction_task: ExtractionTask
    model_run: ModelRun
    batch: MentionProposalBatch | None


def run_recorded_mention_proposer(
    *,
    representation_id: str,
    context_manifest_id: str,
    context_manifest_digest: str,
    context_manifest_payload: dict[str, JsonValue],
    proposal_input: MentionProposalInput,
    proposer: MentionProposer,
    ledger: HybridExecutionLedger,
    archive: HybridModelOutputArchive,
) -> RecordedMentionProposalOutcome:
    """Run one specialized proposer and retain the same task/run lineage as an LLM task."""
    input_bytes = _canonical_json(
        {
            "source_segments": [
                {
                    "end_char": item.end_char,
                    "exact_text": item.exact_text,
                    "label": item.label,
                    "start_char": item.start_char,
                }
                for item in proposal_input.source_segments
            ],
            "type_hints": list(proposal_input.type_hints),
        }
    ).encode()
    prompt_bytes = _canonical_json({"type_hints": list(proposal_input.type_hints)}).encode()
    schema_bytes = b"hybrid_mention_proposal_batch_v1"
    proposer_name = type(proposer).__name__
    task_payload: dict[str, JsonValue] = {
        "task_type": "hybrid_mention_proposal",
        "representation_id": representation_id,
        "context_manifest_id": context_manifest_id,
        "context_manifest_digest": context_manifest_digest,
        "proposer": proposer_name,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
    }
    fingerprint = hashlib.sha256(_canonical_json(task_payload).encode()).hexdigest()
    execution_spec_digest = hashlib.sha256(
        _canonical_json({**task_payload, "runtime": "in_process:gliner"}).encode()
    ).hexdigest()
    task = ExtractionTask(
        id=f"ext_{fingerprint[:24]}",
        task_type="hybrid_mention_proposal",
        context_manifest_id=context_manifest_id,
        context_manifest_digest=context_manifest_digest,
        context_manifest_payload=context_manifest_payload,
        prompt_id="hybrid_gliner_labels_v1",
        schema_id="hybrid_mention_proposal_batch_v1",
        model_profile_id="gliner-medium-v2.1",
        execution_spec_digest=execution_spec_digest,
        task_fingerprint=fingerprint,
    )
    ledger.save_extraction_task(task)
    model_run_id = f"mrn_{uuid.uuid4().hex}"
    started_at = datetime.now(UTC)
    monotonic_started = time.monotonic()
    try:
        batch = proposer.propose(proposal_input)
    except Exception as error:
        completed_at = datetime.now(UTC)
        run = _specialized_model_run(
            model_run_id=model_run_id,
            task=task,
            model_identity={"name": proposer_name, "weights_digest": None},
            prompt_digest=hashlib.sha256(prompt_bytes).hexdigest(),
            schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.RUNTIME_FAILED,
            started_at=started_at,
            completed_at=completed_at,
            elapsed_milliseconds=round((time.monotonic() - monotonic_started) * 1000),
            error=error,
        )
        ledger.save_model_run(run)
        return RecordedMentionProposalOutcome(task, run, None)
    payload = _mention_proposal_batch_bytes(batch)
    output_digest = hashlib.sha256(payload).hexdigest()
    model_identity: dict[str, JsonValue] = {
        "name": batch.model_id,
        "revision": batch.model_revision,
        "proposer_id": batch.proposer_id,
    }
    execution_receipt = _specialized_execution_receipt(
        model_identity=model_identity,
        input_bytes=input_bytes,
        output_bytes=payload,
    )
    try:
        archive.put_model_run_output(model_run_id, payload, output_digest)
    except Exception as error:
        completed_at = datetime.now(UTC)
        run = _specialized_model_run(
            model_run_id=model_run_id,
            task=task,
            model_identity=model_identity,
            prompt_digest=hashlib.sha256(prompt_bytes).hexdigest(),
            schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
            execution_spec_digest=execution_spec_digest,
            status=ModelRunStatus.OUTPUT_ARCHIVE_FAILED,
            started_at=started_at,
            completed_at=completed_at,
            elapsed_milliseconds=round((time.monotonic() - monotonic_started) * 1000),
            error=error,
            execution_receipt=execution_receipt,
        )
        ledger.save_model_run(run)
        return RecordedMentionProposalOutcome(task, run, None)
    completed_at = datetime.now(UTC)
    run = _specialized_model_run(
        model_run_id=model_run_id,
        task=task,
        model_identity=model_identity,
        prompt_digest=hashlib.sha256(prompt_bytes).hexdigest(),
        schema_digest=hashlib.sha256(schema_bytes).hexdigest(),
        execution_spec_digest=execution_spec_digest,
        status=ModelRunStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_milliseconds=round((time.monotonic() - monotonic_started) * 1000),
        output_digest=output_digest,
        execution_receipt=execution_receipt,
        outcome_metadata={
            "configuration": {key: value for key, value in batch.configuration},
            "proposal_count": len(batch.proposals),
        },
    )
    ledger.save_model_run(run)
    return RecordedMentionProposalOutcome(task, run, batch)


def observation_from_proposal(
    *,
    proposal: MentionProposal,
    source_segment_id: str,
    producer_id: str,
    execution_record_id: str,
) -> MentionObservation:
    hints = tuple(ContextualKind(value) for value in proposal.type_hints)
    return MentionObservation(
        id=_id(
            "mob",
            source_segment_id,
            str(proposal.start),
            str(proposal.end),
            proposal.text,
            producer_id,
            execution_record_id,
            *(hint.value for hint in hints),
        ),
        source_segment_id=source_segment_id,
        start=proposal.start,
        end=proposal.end,
        text=proposal.text,
        type_hints=hints,
        producer_id=producer_id,
        execution_record_id=execution_record_id,
        score=proposal.score,
    )


def map_proposal_drafts_to_observations(
    *,
    drafts: tuple[MentionProposalDraft, ...],
    source_segments: tuple[SourceSegment, ...],
    source_segment_ids: dict[str, str],
    producer_id: str,
    execution_record_id: str,
) -> tuple[MentionObservation, ...]:
    """Map model-authored literals to every exact task-local source occurrence."""
    segments = {segment.label: segment for segment in source_segments}
    observations: list[MentionObservation] = []
    for draft in drafts:
        segment = segments.get(draft.source_segment_label)
        if segment is None:
            raise ValueError("Mention proposal draft references an unknown SourceSegment.")
        start = 0
        matched = False
        while True:
            occurrence = segment.exact_text.find(draft.text, start)
            if occurrence < 0:
                break
            matched = True
            normalized_hints = tuple(sorted({item.value for item in draft.type_hints}))
            proposal = MentionProposal(
                source_segment_label=segment.label,
                text=draft.text,
                start=occurrence,
                end=occurrence + len(draft.text),
                type_hints=normalized_hints,
            )
            observations.append(
                observation_from_proposal(
                    proposal=proposal,
                    source_segment_id=source_segment_ids[segment.label],
                    producer_id=producer_id,
                    execution_record_id=execution_record_id,
                )
            )
            start = occurrence + 1
        if not matched:
            raise ValueError("Mention proposal literal does not occur in its SourceSegment.")
    return tuple(sorted(observations, key=_observation_key))


def fuse_mention_observations(
    *,
    source_segments: dict[str, str],
    observations: tuple[MentionObservation, ...],
) -> tuple[MentionCandidate, ...]:
    """Fuse equal source ranges while retaining every proposer observation."""
    grouped: dict[tuple[str, int, int, str], list[MentionObservation]] = defaultdict(list)
    for observation in observations:
        source = source_segments.get(observation.source_segment_id)
        if source is None:
            raise ValueError("MentionObservation references an unknown SourceSegment.")
        if (
            observation.end > len(source)
            or source[observation.start : observation.end] != observation.text
        ):
            raise ValueError("MentionObservation does not match authoritative source characters.")
        grouped[
            (
                observation.source_segment_id,
                observation.start,
                observation.end,
                observation.text,
            )
        ].append(observation)
    candidates: list[MentionCandidate] = []
    for (segment_id, start, end, text), values in sorted(grouped.items()):
        source_digest = hashlib.sha256(source_segments[segment_id].encode()).hexdigest()
        observation_ids = tuple(sorted(item.id for item in values))
        type_hints = tuple(
            sorted(
                {hint for item in values for hint in item.type_hints},
                key=lambda item: item.value,
            )
        )
        candidates.append(
            MentionCandidate(
                id=_id("mnc", segment_id, source_digest, str(start), str(end), text),
                source_segment_id=segment_id,
                source_text_sha256=source_digest,
                start=start,
                end=end,
                text=text,
                observation_ids=observation_ids,
                type_hints=type_hints,
            )
        )
    return tuple(candidates)


def reconcile_mention_boundaries(
    *,
    source_segments: dict[str, str],
    observations: tuple[MentionObservation, ...],
    candidates: tuple[MentionCandidate, ...],
) -> tuple[tuple[MentionBoundaryDecision, ...], tuple[MentionCandidate, ...]]:
    """Apply the sealed ORG-R1 source-literal rules through generic DTOs."""
    observations_by_id = {item.id: item for item in observations}
    candidates_by_id = {item.id: item for item in candidates}
    decisions: list[MentionBoundaryDecision] = []
    selected_ids: set[str] = set()
    for source_segment_id in sorted(source_segments):
        segment_candidates = tuple(
            candidate
            for candidate in candidates
            if candidate.source_segment_id == source_segment_id
        )
        if not segment_candidates:
            continue
        old_candidates = tuple(
            OrganizationMentionCandidate(
                id=candidate.id,
                source_segment_id=candidate.source_segment_id,
                source_text_digest=candidate.source_text_sha256,
                text=candidate.text,
                start=candidate.start,
                end=candidate.end,
                observations=tuple(
                    OrganizationMentionProposalObservation(
                        proposer_id=observations_by_id[observation_id].producer_id,
                        text=observations_by_id[observation_id].text,
                        start=observations_by_id[observation_id].start,
                        end=observations_by_id[observation_id].end,
                        score=observations_by_id[observation_id].score,
                        model_run_id=observations_by_id[observation_id].execution_record_id,
                    )
                    for observation_id in candidate.observation_ids
                ),
            )
            for candidate in segment_candidates
        )
        result = reconcile_organization_mention_boundaries(
            source_text=source_segments[source_segment_id],
            source_segment_id=source_segment_id,
            candidates=old_candidates,
        )
        for old_decision in result.decisions:
            status = MentionBoundaryStatus(old_decision.status.value)
            candidate_ids = tuple(sorted(old_decision.candidate_ids))
            selected = tuple(sorted(old_decision.selected_candidate_ids))
            selected_ids.update(selected)
            decisions.append(
                MentionBoundaryDecision(
                    id=_id(
                        "mbd",
                        HYBRID_MENTION_BOUNDARY_POLICY_ID,
                        source_segment_id,
                        old_decision.rule_id,
                        *candidate_ids,
                    ),
                    source_segment_id=source_segment_id,
                    status=status,
                    rule_id=old_decision.rule_id,
                    candidate_ids=candidate_ids,
                    selected_candidate_ids=selected,
                    preserved_candidate_ids=candidate_ids,
                    alias_evidence_candidate_ids=tuple(
                        sorted(old_decision.alias_evidence_candidate_ids)
                    ),
                    diagnostics=tuple(sorted(old_decision.diagnostics)),
                )
            )
    selected_candidates = tuple(
        candidates_by_id[candidate_id]
        for candidate_id in sorted(
            selected_ids,
            key=lambda item: _candidate_key(candidates_by_id[item]),
        )
    )
    ordered_decisions = tuple(sorted(decisions, key=lambda item: (item.source_segment_id, item.id)))
    return ordered_decisions, selected_candidates


def parse_mention_proposal_output(
    raw_output: bytes,
) -> MentionProposalDraftBatch | MentionProposalAbstention:
    text = _strict_utf8_lines(raw_output, "Mention proposal")
    lines = text.splitlines()
    if len(lines) == 1 and lines[0].startswith("abstain: "):
        reason = lines[0].removeprefix("abstain: ")
        if not reason:
            raise ValueError("Mention proposal abstention requires a reason.")
        return MentionProposalAbstention(reason)
    drafts: list[MentionProposalDraft] = []
    for line in lines:
        if not line.startswith("mention: "):
            raise ValueError("Mention proposal lines must begin with 'mention: '.")
        parts = line.removeprefix("mention: ").split(" | ")
        if len(parts) != 3 or any(not part for part in parts):
            raise ValueError("Mention proposal lines require segment, hints, and literal text.")
        segment, hints_text, literal = parts
        if not segment.startswith("s") or not segment[1:].isdigit():
            raise ValueError("Mention proposal SourceSegment labels must use the sN form.")
        try:
            hints = tuple(
                sorted(
                    {ContextualKind(item) for item in hints_text.split(",")},
                    key=lambda item: item.value,
                )
            )
        except ValueError as error:
            raise ValueError("Mention proposal contains an unknown contextual kind.") from error
        if any(item in {ContextualKind.OTHER, ContextualKind.UNCLEAR} for item in hints):
            raise ValueError("Mention proposer hints must use a concrete contextual kind.")
        drafts.append(MentionProposalDraft(segment, hints, literal))
    if len(set(drafts)) != len(drafts):
        raise ValueError("Mention proposal output repeats one proposal.")
    return MentionProposalDraftBatch(tuple(drafts))


def parse_mention_interpretation_output(raw_output: bytes) -> MentionInterpretationDraft:
    text = _strict_utf8_lines(raw_output, "Mention interpretation")
    lines = text.splitlines()
    expected_keys = ("candidate", "referentiality", "contextual_kind", "discourse_role", "support")
    if len(lines) != len(expected_keys):
        raise ValueError("Mention interpretation output must contain exactly five lines.")
    values: dict[str, str] = {}
    for line, expected_key in zip(lines, expected_keys, strict=True):
        key, separator, value = line.partition(": ")
        if not separator or key != expected_key or not value:
            raise ValueError("Mention interpretation fields or field order are invalid.")
        values[key] = value
    try:
        return MentionInterpretationDraft(
            candidate_label=values["candidate"],
            referentiality=Referentiality(values["referentiality"]),
            contextual_kind=ContextualKind(values["contextual_kind"]),
            discourse_role=DiscourseRole(values["discourse_role"]),
            support_segment_label=values["support"],
        )
    except ValueError as error:
        raise ValueError("Mention interpretation contains an unknown label value.") from error


def mention_proposal_schema_bytes() -> bytes:
    return (
        b"mention: <sN> | <contextual-kind>[,<contextual-kind>...] | <literal expression>\n"
        b"... one line for each proposal\n\n"
        b"or\n\n"
        b"abstain: <non-empty reason>\n"
    )


def mention_interpretation_schema_bytes() -> bytes:
    return (
        b"candidate: c1\n"
        b"referentiality: <allowed Referentiality value>\n"
        b"contextual_kind: <allowed ContextualKind value>\n"
        b"discourse_role: <allowed DiscourseRole value>\n"
        b"support: <sN>\n"
    )


def hybrid_mention_task_schema_bytes() -> bytes:
    return mention_proposal_schema_bytes() + b"\nor\n\n" + mention_interpretation_schema_bytes()


def parse_hybrid_mention_task_output(
    raw_output: bytes,
) -> MentionProposalDraftBatch | MentionProposalAbstention | MentionInterpretationDraft:
    try:
        first_line = raw_output.decode("utf-8").splitlines()[0]
    except (UnicodeDecodeError, IndexError) as error:
        raise ValueError("Hybrid mention task output must be non-empty UTF-8 text.") from error
    if first_line.startswith(("mention: ", "abstain: ")):
        return parse_mention_proposal_output(raw_output)
    if first_line.startswith("candidate: "):
        return parse_mention_interpretation_output(raw_output)
    raise ValueError("Hybrid mention task output does not match a supported contract.")


def resolve_mention_interpretation(
    *,
    draft: MentionInterpretationDraft,
    candidate_labels: dict[str, MentionCandidate],
    source_segment_ids: dict[str, str],
    model_run_id: str,
    trace_id: str,
) -> MentionInterpretation:
    candidate = candidate_labels.get(draft.candidate_label)
    if candidate is None:
        raise ValueError("Mention interpretation references an unknown candidate label.")
    support_segment_id = source_segment_ids.get(draft.support_segment_label)
    if support_segment_id is None:
        raise ValueError("Mention interpretation references an unknown support label.")
    interpretation_id = _id(
        "mit",
        candidate.id,
        draft.referentiality.value,
        draft.contextual_kind.value,
        draft.discourse_role.value,
        support_segment_id,
        model_run_id,
        trace_id,
    )
    return MentionInterpretation(
        id=interpretation_id,
        candidate_id=candidate.id,
        referentiality=draft.referentiality,
        contextual_kind=draft.contextual_kind,
        discourse_role=draft.discourse_role,
        support_segment_id=support_segment_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )


def build_hybrid_extraction_preview(**values: object) -> HybridExtractionPreview:
    payload = dict(values)
    payload.setdefault("schema_version", "hybrid_extraction_preview_v1")
    payload.setdefault("policy_id", HYBRID_MENTION_PREVIEW_POLICY_ID)
    for field_name in (
        "observations",
        "candidates",
        "boundary_decisions",
        "interpretations",
        "extraction_task_ids",
        "model_run_ids",
        "traces",
        "diagnostics",
    ):
        payload.setdefault(field_name, ())
    json_payload = cast(dict[str, JsonValue], _json_copy(payload))
    json_payload["id"] = _preview_id(json_payload)
    return HybridExtractionPreview.model_validate_json(_canonical_json(json_payload))


def canonical_hybrid_extraction_preview_bytes(preview: HybridExtractionPreview) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode("utf-8")


def hybrid_extraction_preview_sha256(preview: HybridExtractionPreview) -> str:
    return hashlib.sha256(canonical_hybrid_extraction_preview_bytes(preview)).hexdigest()


def hybrid_extraction_preview_from_bytes(payload: bytes) -> HybridExtractionPreview:
    return HybridExtractionPreview.model_validate_json(payload)


def _strict_utf8_lines(raw_output: bytes, label: str) -> str:
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} output must be UTF-8 text.") from error
    lines = text.splitlines()
    if not lines or any(not line or line != line.strip() for line in lines):
        raise ValueError(f"{label} output must contain only trimmed non-empty lines.")
    return text


def _mention_proposal_batch_bytes(batch: MentionProposalBatch) -> bytes:
    payload: dict[str, JsonValue] = {
        "schema_version": "hybrid_mention_proposal_batch_v1",
        "proposer_id": batch.proposer_id,
        "model_id": batch.model_id,
        "model_revision": batch.model_revision,
        "configuration": {key: value for key, value in batch.configuration},
        "load_elapsed_milliseconds": batch.load_elapsed_milliseconds,
        "inference_elapsed_milliseconds": batch.inference_elapsed_milliseconds,
        "proposals": [
            {
                "source_segment_label": item.source_segment_label,
                "text": item.text,
                "start": item.start,
                "end": item.end,
                "type_hints": list(item.type_hints),
                "score": item.score,
            }
            for item in batch.proposals
        ],
    }
    return _canonical_json(payload).encode()


def _specialized_model_run(
    *,
    model_run_id: str,
    task: ExtractionTask,
    model_identity: dict[str, JsonValue],
    prompt_digest: str,
    schema_digest: str,
    execution_spec_digest: str,
    status: ModelRunStatus,
    started_at: datetime,
    completed_at: datetime,
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
        model_identity=model_identity,
        runtime_identity="in_process:gliner",
        tokenizer_id="character_offsets_v1",
        prompt_digest=prompt_digest,
        schema_digest=schema_digest,
        execution_spec_digest=execution_spec_digest,
        generation_parameters={},
        raw_output_artifact_id=(model_run_id if output_digest is not None else None),
        output_digest=output_digest,
        status=status,
        error_code=type(error).__name__ if error is not None else None,
        error_message=str(error) if error is not None else None,
        started_at=started_at,
        completed_at=completed_at,
        execution_diagnostics={
            "elapsed_milliseconds": elapsed_milliseconds,
            "deadline_milliseconds": 300_000,
            "first_response_event_milliseconds": None,
        },
        execution_receipt=execution_receipt,
        task_metadata={"authority": "derived_diagnostic"},
        outcome_metadata=outcome_metadata or {},
    )


def _specialized_execution_receipt(
    *,
    model_identity: dict[str, JsonValue],
    input_bytes: bytes,
    output_bytes: bytes,
) -> dict[str, JsonValue]:
    return {
        "model_identity_digest": hashlib.sha256(
            _canonical_json(model_identity).encode()
        ).hexdigest(),
        "generation_parameters_digest": hashlib.sha256(b"{}").hexdigest(),
        "rendered_input_digest": hashlib.sha256(input_bytes).hexdigest(),
        "input_token_count": len(input_bytes.decode("utf-8")),
        "output_token_count": len(output_bytes.decode("utf-8")),
    }


def _preview_id(payload: dict[str, JsonValue]) -> str:
    return f"hxp_{hashlib.sha256(_canonical_json(payload).encode()).hexdigest()[:24]}"


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_copy(value: object) -> JsonValue:
    return cast(JsonValue, json.loads(json.dumps(value, default=_json_default)))


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    raise TypeError(f"Unsupported HybridExtractionPreview value: {type(value).__name__}")


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(chr(31).join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _require_ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"Hybrid extraction {label} must be ordered and distinct.")


def _observation_key(item: MentionObservation) -> tuple[str, int, int, str, str]:
    return item.source_segment_id, item.start, item.end, item.text, item.id


def _candidate_key(item: MentionCandidate) -> tuple[str, int, int, str, str]:
    return item.source_segment_id, item.start, item.end, item.text, item.id
