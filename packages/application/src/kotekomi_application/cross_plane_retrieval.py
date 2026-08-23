"""Role-aware orchestration across existing Ledger and Knowledge-Graph retrieval planes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    CrossPlaneQueryPhase,
    CrossPlaneQueryRecord,
    CrossPlaneTransition,
    LedgerContextResult,
    RetrievalPlane,
)

from kotekomi_application.context_planning import ContextTokenizer
from kotekomi_application.knowledge_graph_retrieval import (
    KnowledgeGraphLedger,
    KnowledgeGraphProjectionPort,
    KnowledgeGraphRetrievalFailureCode,
    QueryKnowledgeGraphCommand,
    QueryKnowledgeGraphResult,
    query_knowledge_graph,
)
from kotekomi_application.ledger_retrieval import (
    LEDGER_CURRENT_RELEVANCE_POLICY_ID,
    LedgerRetrievalLedger,
    LedgerRetrievalProjectionPort,
    QueryLedgerRetrievalCommand,
    QueryLedgerRetrievalResult,
    query_ledger_retrieval,
)

CROSS_PLANE_QUERY_POLICY_ID = "cross_plane_ledger_graph_evidence_v1"


class CrossPlaneFailureCode(StrEnum):
    LEDGER_EMPTY = "cross_plane_ledger_empty"
    SEED_MISSING = "cross_plane_seed_missing"
    SEED_AMBIGUOUS = "cross_plane_seed_ambiguous"
    EVIDENCE_MISSING = "cross_plane_evidence_missing"
    CONTEXT_PLANNING_FAILED = "cross_plane_context_planning_failed"
    LEDGER_QUERY_FAILED = "cross_plane_ledger_query_failed"
    GRAPH_QUERY_FAILED = "cross_plane_graph_query_failed"


@dataclass(frozen=True)
class CrossPlaneQueryPolicy:
    policy_id: str
    ledger_policy_id: str
    ledger_maximum_hits: int
    graph_maximum_hops: int
    graph_maximum_hits: int
    context_profile_id: str


CROSS_PLANE_LEDGER_GRAPH_EVIDENCE_POLICY = CrossPlaneQueryPolicy(
    policy_id=CROSS_PLANE_QUERY_POLICY_ID,
    ledger_policy_id=LEDGER_CURRENT_RELEVANCE_POLICY_ID,
    ledger_maximum_hits=5,
    graph_maximum_hops=2,
    graph_maximum_hits=5,
    context_profile_id="retrieval-validation-v1",
)


@dataclass(frozen=True)
class QueryCrossPlaneCommand:
    query_text: str
    policy_id: str = CROSS_PLANE_QUERY_POLICY_ID


@dataclass(frozen=True)
class QueryCrossPlaneResult:
    status: str
    cross_plane_query_id: str
    transitions: tuple[CrossPlaneTransition, ...]
    selected_record_ids: tuple[str, ...]
    terminal_evidence_target_ids: tuple[str, ...]
    context_results: tuple[LedgerContextResult, ...]
    failure: CrossPlaneFailureCode | None = None


class CrossPlaneLedger(LedgerRetrievalLedger, KnowledgeGraphLedger, Protocol):
    pass


class CrossPlaneGraphProjectionPort(KnowledgeGraphProjectionPort, Protocol):
    def save_cross_plane_query_record(self, record: CrossPlaneQueryRecord) -> None: ...


def query_cross_plane(
    command: QueryCrossPlaneCommand,
    *,
    ledger_repository: CrossPlaneLedger,
    ledger_projection: LedgerRetrievalProjectionPort,
    graph_projection: CrossPlaneGraphProjectionPort,
    tokenizer: ContextTokenizer,
) -> QueryCrossPlaneResult:
    policy = _policy(command.policy_id)
    ledger_result = query_ledger_retrieval(
        QueryLedgerRetrievalCommand(
            query_text=command.query_text,
            policy_id=policy.ledger_policy_id,
            maximum_hits=policy.ledger_maximum_hits,
            context_profile_id=policy.context_profile_id,
        ),
        ledger_repository=ledger_repository,
        projection=ledger_projection,
        tokenizer=tokenizer,
    )
    transitions = [_ledger_transition(ledger_result)]
    if ledger_result.status != "complete":
        return _finish(
            command,
            graph_projection,
            tuple(transitions),
            (),
            (),
            (),
            CrossPlaneFailureCode.LEDGER_QUERY_FAILED,
        )
    if not ledger_result.selected_record_ids:
        return _finish(
            command,
            graph_projection,
            tuple(transitions),
            (),
            (),
            (),
            CrossPlaneFailureCode.LEDGER_EMPTY,
        )

    graph_result = query_knowledge_graph(
        QueryKnowledgeGraphCommand(
            seed_text=command.query_text,
            maximum_hops=policy.graph_maximum_hops,
            maximum_hits=policy.graph_maximum_hits,
            context_profile_id=policy.context_profile_id,
        ),
        ledger_repository=ledger_repository,
        projection=graph_projection,
        tokenizer=tokenizer,
    )
    transitions.append(_graph_transition(graph_result))
    if graph_result.status != "complete":
        return _finish(
            command,
            graph_projection,
            tuple(transitions),
            (),
            (),
            (),
            _graph_failure(graph_result),
        )

    evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for hit in graph_result.hits
                if hit.selected
                for evidence_id in hit.terminal_evidence_target_ids
            }
        )
    )
    transitions.append(
        CrossPlaneTransition(
            phase=CrossPlaneQueryPhase.DOCUMENT_EVIDENCE,
            plane=RetrievalPlane.DOCUMENT,
            status="complete" if evidence_ids else "blocked",
            selected_record_ids=graph_result.selected_record_ids,
            terminal_evidence_target_ids=evidence_ids,
            failure_code=None if evidence_ids else CrossPlaneFailureCode.EVIDENCE_MISSING.value,
        )
    )
    if not evidence_ids:
        return _finish(
            command,
            graph_projection,
            tuple(transitions),
            graph_result.selected_record_ids,
            (),
            (),
            CrossPlaneFailureCode.EVIDENCE_MISSING,
        )

    context_failed = not graph_result.context_results or any(
        item.status != "ready" for item in graph_result.context_results
    )
    transitions.append(
        CrossPlaneTransition(
            phase=CrossPlaneQueryPhase.CONTEXT_PLANNING,
            status="blocked" if context_failed else "complete",
            selected_record_ids=graph_result.selected_record_ids,
            terminal_evidence_target_ids=evidence_ids,
            failure_code=(
                CrossPlaneFailureCode.CONTEXT_PLANNING_FAILED.value if context_failed else None
            ),
        )
    )
    return _finish(
        command,
        graph_projection,
        tuple(transitions),
        graph_result.selected_record_ids,
        evidence_ids,
        graph_result.context_results,
        CrossPlaneFailureCode.CONTEXT_PLANNING_FAILED if context_failed else None,
    )


def _policy(policy_id: str) -> CrossPlaneQueryPolicy:
    if policy_id != CROSS_PLANE_QUERY_POLICY_ID:
        raise ValueError(f"Unknown Cross-plane policy: {policy_id}.")
    return CROSS_PLANE_LEDGER_GRAPH_EVIDENCE_POLICY


def _ledger_transition(result: QueryLedgerRetrievalResult) -> CrossPlaneTransition:
    return CrossPlaneTransition(
        phase=CrossPlaneQueryPhase.LEDGER_DISCOVERY,
        plane=RetrievalPlane.LEDGER,
        status="complete" if result.status == "complete" else "blocked",
        local_query_record_id=result.retrieval_query_id,
        index_manifest_id=result.index_manifest_id,
        selected_record_ids=result.selected_record_ids,
        failure_code=result.failure.value if result.failure is not None else None,
    )


def _graph_transition(result: QueryKnowledgeGraphResult) -> CrossPlaneTransition:
    return CrossPlaneTransition(
        phase=CrossPlaneQueryPhase.GRAPH_EXPANSION,
        plane=RetrievalPlane.KNOWLEDGE_GRAPH,
        status="complete" if result.status == "complete" else "blocked",
        local_query_record_id=result.retrieval_query_id,
        index_manifest_id=result.index_manifest_id,
        selected_record_ids=result.selected_record_ids,
        terminal_evidence_target_ids=tuple(
            sorted(
                {
                    evidence_id
                    for hit in result.hits
                    if hit.selected
                    for evidence_id in hit.terminal_evidence_target_ids
                }
            )
        ),
        failure_code=result.failure.value if result.failure is not None else None,
    )


def _graph_failure(result: QueryKnowledgeGraphResult) -> CrossPlaneFailureCode:
    if result.failure is KnowledgeGraphRetrievalFailureCode.SEED_AMBIGUOUS:
        return CrossPlaneFailureCode.SEED_AMBIGUOUS
    if result.failure is KnowledgeGraphRetrievalFailureCode.SEED_MISSING:
        return CrossPlaneFailureCode.SEED_MISSING
    return CrossPlaneFailureCode.GRAPH_QUERY_FAILED


def _finish(
    command: QueryCrossPlaneCommand,
    projection: CrossPlaneGraphProjectionPort,
    transitions: tuple[CrossPlaneTransition, ...],
    selected_record_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    context_results: tuple[LedgerContextResult, ...],
    failure: CrossPlaneFailureCode | None,
) -> QueryCrossPlaneResult:
    record = CrossPlaneQueryRecord(
        cross_plane_query_id=_query_id(command, transitions, selected_record_ids, evidence_ids),
        query_text=command.query_text,
        normalized_query_text=" ".join(command.query_text.casefold().split()),
        policy_id=command.policy_id,
        transitions=transitions,
        selected_record_ids=selected_record_ids,
        terminal_evidence_target_ids=evidence_ids,
        context_results=tuple(context_results),
        failure_code=failure.value if failure is not None else None,
    )
    projection.save_cross_plane_query_record(record)
    return QueryCrossPlaneResult(
        status="failed" if failure is not None else "complete",
        cross_plane_query_id=record.cross_plane_query_id,
        transitions=record.transitions,
        selected_record_ids=record.selected_record_ids,
        terminal_evidence_target_ids=record.terminal_evidence_target_ids,
        context_results=record.context_results,
        failure=failure,
    )


def _query_id(
    command: QueryCrossPlaneCommand,
    transitions: tuple[CrossPlaneTransition, ...],
    selected_record_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
) -> str:
    value = {
        "query": command.query_text,
        "policy": command.policy_id,
        "transitions": [item.model_dump(mode="json") for item in transitions],
        "selected_record_ids": selected_record_ids,
        "terminal_evidence_target_ids": evidence_ids,
    }
    digest = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"cpq_{digest[:24]}"
