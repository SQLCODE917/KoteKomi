"""Pipeline readiness and next-step orchestration use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionType,
    Briefing,
    Document,
    Entity,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    Relationship,
    Source,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.ports import AcceptedCanonicalRecord
from kotekomi_application.review_queue_packet import (
    ReviewQueuePacketLedger,
    ReviewReadinessBlocker,
    ReviewReadinessInput,
    get_review_readiness,
)

SOURCE_INGEST_COMMAND = "kotekomi source add-file <path>"
ASSERTION_PROPOSAL_COMMAND = (
    "kotekomi source propose-assertions --document-id <document_id> "
    "--model-output-fixture <path>"
)
REVIEW_LIST_COMMAND = "kotekomi review list"
GRAPH_PROJECT_COMMAND = "kotekomi graph project"
GRAPH_MINE_COMMAND = "kotekomi graph mine"
BRIEFING_GENERATE_COMMAND = "kotekomi briefing generate --title <title>"


class PipelineStage(StrEnum):
    READY_FOR_SOURCE_INGEST = "ready_for_source_ingest"
    READY_FOR_ASSERTION_PROPOSAL = "ready_for_assertion_proposal"
    REVIEW_REQUIRED = "review_required"
    READY_FOR_GRAPH_PROJECTION = "ready_for_graph_projection"
    READY_FOR_GRAPH_MINING = "ready_for_graph_mining"
    READY_FOR_BRIEFING = "ready_for_briefing"
    BRIEFING_CURRENT = "briefing_current"


class PipelineReadinessLedger(ReviewQueuePacketLedger, Protocol):
    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]: ...
    def list_briefings(self) -> tuple[Briefing, ...]: ...


@dataclass(frozen=True)
class PipelineStatusInput:
    pass


@dataclass(frozen=True)
class PipelineBlocker:
    command: str
    reason: str
    blocker_type: str
    blocker_id: str


@dataclass(frozen=True)
class PipelineStatus:
    stage: PipelineStage
    next_command: str | None
    safe_commands: tuple[str, ...]
    blocked_commands: tuple[str, ...]
    blockers: tuple[PipelineBlocker, ...]
    review_required: bool
    pending_count: int
    missing_reference_count: int
    source_count: int
    document_count: int
    accepted_assertion_count: int
    relationship_count: int
    outcome_count: int
    argument_edge_count: int
    briefing_count: int
    candidate_document_ids: tuple[str, ...]


@dataclass(frozen=True)
class PipelineNextStep:
    command: str | None
    reason: str
    stage: PipelineStage
    requires_human_review: bool
    blocked: bool
    blockers: tuple[PipelineBlocker, ...]


def get_pipeline_status(
    pipeline_input: PipelineStatusInput,
    ledger_repository: PipelineReadinessLedger,
) -> PipelineStatus:
    del pipeline_input
    review_readiness = get_review_readiness(ReviewReadinessInput(), ledger_repository)
    records = ledger_repository.list_accepted_canonical_records()
    indexes = _record_indexes(records)
    briefings = ledger_repository.list_briefings()
    candidate_document_ids = tuple(sorted(document.id for document in indexes.documents))

    if review_readiness.review_required:
        return PipelineStatus(
            stage=PipelineStage.REVIEW_REQUIRED,
            next_command=REVIEW_LIST_COMMAND,
            safe_commands=(REVIEW_LIST_COMMAND,),
            blocked_commands=(
                GRAPH_PROJECT_COMMAND,
                GRAPH_MINE_COMMAND,
                BRIEFING_GENERATE_COMMAND,
            ),
            blockers=_review_blockers(review_readiness.blockers),
            review_required=True,
            pending_count=review_readiness.pending_count,
            missing_reference_count=review_readiness.missing_reference_count,
            source_count=len(indexes.sources),
            document_count=len(indexes.documents),
            accepted_assertion_count=len(indexes.assertions),
            relationship_count=len(indexes.relationships),
            outcome_count=len(indexes.outcomes),
            argument_edge_count=len(indexes.argument_edges),
            briefing_count=len(briefings),
            candidate_document_ids=candidate_document_ids,
        )

    latest_briefing_at = _latest_briefing_at(briefings)
    if not indexes.sources:
        stage = PipelineStage.READY_FOR_SOURCE_INGEST
        next_command = SOURCE_INGEST_COMMAND
        safe_commands = (SOURCE_INGEST_COMMAND,)
    elif indexes.documents and not indexes.assertions:
        stage = PipelineStage.READY_FOR_ASSERTION_PROPOSAL
        next_command = ASSERTION_PROPOSAL_COMMAND
        safe_commands = (ASSERTION_PROPOSAL_COMMAND,)
    elif latest_briefing_at is not None and not _records_after(records, latest_briefing_at):
        stage = PipelineStage.BRIEFING_CURRENT
        next_command = None
        safe_commands = ()
    elif _has_analytic_records_after(indexes, latest_briefing_at):
        stage = PipelineStage.READY_FOR_BRIEFING
        next_command = BRIEFING_GENERATE_COMMAND
        safe_commands = (BRIEFING_GENERATE_COMMAND,)
    elif indexes.assertions and indexes.relationships and indexes.outcomes:
        stage = PipelineStage.READY_FOR_GRAPH_MINING
        next_command = GRAPH_MINE_COMMAND
        safe_commands = (GRAPH_PROJECT_COMMAND, GRAPH_MINE_COMMAND)
    elif indexes.assertions:
        stage = PipelineStage.READY_FOR_GRAPH_PROJECTION
        next_command = GRAPH_PROJECT_COMMAND
        safe_commands = (GRAPH_PROJECT_COMMAND,)
    else:
        stage = PipelineStage.READY_FOR_SOURCE_INGEST
        next_command = SOURCE_INGEST_COMMAND
        safe_commands = (SOURCE_INGEST_COMMAND,)

    return PipelineStatus(
        stage=stage,
        next_command=next_command,
        safe_commands=safe_commands,
        blocked_commands=(),
        blockers=(),
        review_required=False,
        pending_count=0,
        missing_reference_count=0,
        source_count=len(indexes.sources),
        document_count=len(indexes.documents),
        accepted_assertion_count=len(indexes.assertions),
        relationship_count=len(indexes.relationships),
        outcome_count=len(indexes.outcomes),
        argument_edge_count=len(indexes.argument_edges),
        briefing_count=len(briefings),
        candidate_document_ids=candidate_document_ids,
    )


def get_pipeline_next(
    pipeline_input: PipelineStatusInput,
    ledger_repository: PipelineReadinessLedger,
) -> PipelineNextStep:
    status = get_pipeline_status(pipeline_input, ledger_repository)
    return PipelineNextStep(
        command=status.next_command,
        reason=_next_step_reason(status),
        stage=status.stage,
        requires_human_review=status.review_required,
        blocked=status.next_command is None,
        blockers=status.blockers,
    )


def pipeline_status_to_json(status: PipelineStatus) -> dict[str, JsonValue]:
    return {
        "stage": status.stage.value,
        "next_command": status.next_command,
        "safe_commands": list(status.safe_commands),
        "blocked_commands": list(status.blocked_commands),
        "blockers": [_blocker_to_json(blocker) for blocker in status.blockers],
        "review_required": status.review_required,
        "pending_count": status.pending_count,
        "missing_reference_count": status.missing_reference_count,
        "source_count": status.source_count,
        "document_count": status.document_count,
        "accepted_assertion_count": status.accepted_assertion_count,
        "relationship_count": status.relationship_count,
        "outcome_count": status.outcome_count,
        "argument_edge_count": status.argument_edge_count,
        "briefing_count": status.briefing_count,
        "candidate_document_ids": list(status.candidate_document_ids),
    }


def pipeline_next_to_json(next_step: PipelineNextStep) -> dict[str, JsonValue]:
    return {
        "command": next_step.command,
        "reason": next_step.reason,
        "stage": next_step.stage.value,
        "requires_human_review": next_step.requires_human_review,
        "blocked": next_step.blocked,
        "blockers": [_blocker_to_json(blocker) for blocker in next_step.blockers],
    }


@dataclass(frozen=True)
class _RecordIndexes:
    entities: tuple[Entity, ...]
    actors: tuple[Actor, ...]
    organizations: tuple[Organization, ...]
    places: tuple[Place, ...]
    events: tuple[Event, ...]
    sources: tuple[Source, ...]
    documents: tuple[Document, ...]
    evidence_spans: tuple[EvidenceSpan, ...]
    assertions: tuple[Assertion, ...]
    relationships: tuple[Relationship, ...]
    outcomes: tuple[Outcome, ...]
    argument_edges: tuple[ArgumentEdge, ...]


def _record_indexes(records: tuple[AcceptedCanonicalRecord, ...]) -> _RecordIndexes:
    return _RecordIndexes(
        entities=tuple(record for record in records if isinstance(record, Entity)),
        actors=tuple(record for record in records if isinstance(record, Actor)),
        organizations=tuple(record for record in records if isinstance(record, Organization)),
        places=tuple(record for record in records if isinstance(record, Place)),
        events=tuple(record for record in records if isinstance(record, Event)),
        sources=tuple(record for record in records if isinstance(record, Source)),
        documents=tuple(record for record in records if isinstance(record, Document)),
        evidence_spans=tuple(record for record in records if isinstance(record, EvidenceSpan)),
        assertions=tuple(record for record in records if isinstance(record, Assertion)),
        relationships=tuple(record for record in records if isinstance(record, Relationship)),
        outcomes=tuple(record for record in records if isinstance(record, Outcome)),
        argument_edges=tuple(record for record in records if isinstance(record, ArgumentEdge)),
    )


def _review_blockers(
    review_blockers: tuple[ReviewReadinessBlocker, ...],
) -> tuple[PipelineBlocker, ...]:
    return tuple(
        PipelineBlocker(
            command=REVIEW_LIST_COMMAND,
            reason=(
                f"{blocker.record_type} {blocker.stable_label} references "
                f"{blocker.referenced_type} {blocker.referenced_id} "
                f"with {blocker.resolution_status.value} resolution."
            ),
            blocker_type=blocker.referenced_type,
            blocker_id=blocker.referenced_id,
        )
        for blocker in review_blockers
    )


def _latest_briefing_at(briefings: tuple[Briefing, ...]) -> datetime | None:
    if not briefings:
        return None
    return max(briefing.generated_at for briefing in briefings)


def _records_after(records: tuple[AcceptedCanonicalRecord, ...], boundary: datetime) -> bool:
    return any(_record_timestamp(record) > boundary for record in records)


def _record_timestamp(record: AcceptedCanonicalRecord) -> datetime:
    if isinstance(record, (ArgumentEdge, EvidenceSpan)):
        return record.created_at
    return record.updated_at


def _has_analytic_records_after(
    indexes: _RecordIndexes,
    latest_briefing_at: datetime | None,
) -> bool:
    analytic_assertions = tuple(
        assertion
        for assertion in indexes.assertions
        if assertion.assertion_type is AssertionType.ANALYTIC_INFERENCE
    )
    if latest_briefing_at is None:
        return bool(analytic_assertions or indexes.argument_edges)
    return any(
        assertion.updated_at > latest_briefing_at for assertion in analytic_assertions
    ) or any(
        argument_edge.created_at > latest_briefing_at
        for argument_edge in indexes.argument_edges
    )


def _next_step_reason(status: PipelineStatus) -> str:
    if status.stage is PipelineStage.REVIEW_REQUIRED:
        return "Pending ProposedChange records require review before downstream commands."
    if status.stage is PipelineStage.READY_FOR_SOURCE_INGEST:
        return "No Source records exist in the Ledger."
    if status.stage is PipelineStage.READY_FOR_ASSERTION_PROPOSAL:
        return "Documents exist but no accepted Assertions exist."
    if status.stage is PipelineStage.READY_FOR_GRAPH_PROJECTION:
        return "Accepted Assertions exist and graph projection is the next safe derived step."
    if status.stage is PipelineStage.READY_FOR_GRAPH_MINING:
        return "Accepted Assertions, Relationships, and Outcomes can feed graph mining."
    if status.stage is PipelineStage.READY_FOR_BRIEFING:
        return "Accepted analytic records are ready for Briefing generation."
    if status.stage is PipelineStage.BRIEFING_CURRENT:
        return "The latest Briefing is current for accepted Ledger records."
    raise ValueError(f"Unsupported Pipeline stage: {status.stage}")


def _blocker_to_json(blocker: PipelineBlocker) -> dict[str, JsonValue]:
    return {
        "command": blocker.command,
        "reason": blocker.reason,
        "blocker_type": blocker.blocker_type,
        "blocker_id": blocker.blocker_id,
    }
