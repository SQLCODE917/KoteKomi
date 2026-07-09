"""Ledger graph connection mining use case."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from typing import Protocol, cast

from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    ReviewStatus,
    SourceAuthority,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.ledger_graph_projection import (
    LedgerGraphRepository,
    project_ledger_graph,
)
from kotekomi_application.ports import (
    GraphAnalyzer,
    GraphConnectionCandidate,
    GraphEdge,
    GraphProjection,
)

HASH_ID_LENGTH = 24
GRAPH_CONNECTION_MINING_ACTIVITY = "graph_connection_mining"
GRAPH_CONNECTION_MINING_AGENT = "kotekomi_graph_miner"
GRAPH_CONNECTION_PREDICATE = "shared_governance_outcome_with"
GRAPH_CONNECTION_MINING_RULE = "outcome_organization_assertion_cooccurrence"


class LedgerGraphMiningRepository(LedgerGraphRepository, Protocol):
    def list_proposed_changes(self) -> tuple[ProposedChange, ...]: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def save_proposed_change(self, record: ProposedChange) -> None: ...


@dataclass(frozen=True)
class GraphConnectionMiningInput:
    mined_at: datetime
    agent: str = GRAPH_CONNECTION_MINING_AGENT


@dataclass(frozen=True)
class GraphConnectionMiningResult:
    candidate_count: int
    provenance_activity_id: str | None
    proposed_change_ids: tuple[str, ...]


def mine_graph_connections(
    mining_input: GraphConnectionMiningInput,
    ledger_repository: LedgerGraphMiningRepository,
    graph_analyzer: GraphAnalyzer,
) -> GraphConnectionMiningResult:
    projection = project_ledger_graph(ledger_repository, graph_analyzer)
    candidates = _eligible_candidates(
        _mine_connection_candidates(projection),
        ledger_repository.list_relationships(),
    )
    assertion_by_id = {assertion.id: assertion for assertion in ledger_repository.list_assertions()}
    existing_proposed_change_ids = {
        proposed_change.id for proposed_change in ledger_repository.list_proposed_changes()
    }
    proposed_changes = tuple(
        proposed_change
        for candidate in candidates
        for proposed_change in _candidate_proposed_changes(
            candidate=candidate,
            assertion_by_id=assertion_by_id,
            mined_at=mining_input.mined_at,
        )
        if proposed_change.id not in existing_proposed_change_ids
    )
    proposed_change_ids = tuple(proposed_change.id for proposed_change in proposed_changes)
    if not proposed_changes:
        return GraphConnectionMiningResult(
            candidate_count=len(candidates),
            provenance_activity_id=None,
            proposed_change_ids=(),
        )

    provenance_activity_id = deterministic_graph_mining_provenance_activity_id(
        agent=mining_input.agent,
        output_ids=proposed_change_ids,
    )
    provenance_activity = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=GRAPH_CONNECTION_MINING_ACTIVITY,
        agent=mining_input.agent,
        input_ids=tuple(sorted({candidate.outcome_id for candidate in candidates})),
        output_ids=proposed_change_ids,
        occurred_at=mining_input.mined_at,
    )
    ledger_repository.save_provenance_activity(provenance_activity)
    for proposed_change in proposed_changes:
        ledger_repository.save_proposed_change(
            ProposedChange(
                id=proposed_change.id,
                review_status=proposed_change.review_status,
                proposed_json=proposed_change.proposed_json,
                provenance_activity_id=provenance_activity_id,
                created_at=proposed_change.created_at,
                updated_at=proposed_change.updated_at,
            )
        )

    return GraphConnectionMiningResult(
        candidate_count=len(candidates),
        provenance_activity_id=provenance_activity_id,
        proposed_change_ids=proposed_change_ids,
    )


def deterministic_graph_mining_provenance_activity_id(
    *,
    agent: str,
    output_ids: tuple[str, ...],
) -> str:
    digest = hashlib.sha256(
        f"{GRAPH_CONNECTION_MINING_ACTIVITY}:{agent}:{':'.join(output_ids)}".encode()
    ).hexdigest()
    return f"prv_{digest[:HASH_ID_LENGTH]}"


def deterministic_mined_assertion_id(candidate: GraphConnectionCandidate) -> str:
    digest = _candidate_digest(candidate)
    return f"ast_{digest[:HASH_ID_LENGTH]}"


def deterministic_mined_relationship_id(candidate: GraphConnectionCandidate) -> str:
    digest = _candidate_digest(candidate)
    return f"rel_{digest[:HASH_ID_LENGTH]}"


def deterministic_mined_argument_edge_id(
    *,
    supporting_assertion_id: str,
    analytic_assertion_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{supporting_assertion_id}:{GRAPH_CONNECTION_PREDICATE}:{analytic_assertion_id}".encode()
    ).hexdigest()
    return f"arg_{digest[:HASH_ID_LENGTH]}"


def deterministic_mined_proposed_change_id(
    *,
    record_type: str,
    stable_label: str,
) -> str:
    digest = hashlib.sha256(
        f"{GRAPH_CONNECTION_MINING_ACTIVITY}:{record_type}:{stable_label}".encode()
    ).hexdigest()
    return f"pcg_{digest[:HASH_ID_LENGTH]}"


def _eligible_candidates(
    candidates: tuple[GraphConnectionCandidate, ...],
    relationships: tuple[Relationship, ...],
) -> tuple[GraphConnectionCandidate, ...]:
    existing_relationship_keys = {
        (relationship.subject_id, relationship.predicate, relationship.object_id)
        for relationship in relationships
    }
    return tuple(
        candidate
        for candidate in candidates
        if (
            candidate.subject_organization_id,
            GRAPH_CONNECTION_PREDICATE,
            candidate.object_organization_id,
        )
        not in existing_relationship_keys
    )


def _mine_connection_candidates(
    projection: GraphProjection,
) -> tuple[GraphConnectionCandidate, ...]:
    node_type_by_id = {node.id: node.node_type for node in projection.nodes}
    edges_by_source_id: dict[str, list[GraphEdge]] = {}
    for edge in projection.edges:
        edges_by_source_id.setdefault(edge.source_id, []).append(edge)

    candidates: list[GraphConnectionCandidate] = []
    outcome_ids = sorted(node.id for node in projection.nodes if node.node_type == "Outcome")
    for outcome_id in outcome_ids:
        outcome_edges = edges_by_source_id.get(outcome_id, [])
        organization_ids = sorted(
            edge.target_id
            for edge in outcome_edges
            if edge.edge_type == "outcome_organization"
            and node_type_by_id.get(edge.target_id) == "Organization"
        )
        assertion_ids = sorted(
            edge.target_id
            for edge in outcome_edges
            if edge.edge_type == "outcome_assertion"
            and node_type_by_id.get(edge.target_id) == "Assertion"
        )
        if len(organization_ids) < 2 or len(assertion_ids) < 2:
            continue
        candidates.extend(
            GraphConnectionCandidate(
                subject_organization_id=subject_organization_id,
                object_organization_id=object_organization_id,
                outcome_id=outcome_id,
                supporting_assertion_ids=tuple(assertion_ids),
            )
            for subject_organization_id, object_organization_id in combinations(organization_ids, 2)
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.subject_organization_id,
                candidate.object_organization_id,
                candidate.outcome_id,
                candidate.supporting_assertion_ids,
            ),
        )
    )


def _candidate_proposed_changes(
    *,
    candidate: GraphConnectionCandidate,
    assertion_by_id: dict[str, Assertion],
    mined_at: datetime,
) -> tuple[ProposedChange, ...]:
    analytic_assertion_id = deterministic_mined_assertion_id(candidate)
    relationship_id = deterministic_mined_relationship_id(candidate)
    assertion = Assertion(
        id=analytic_assertion_id,
        assertion_type=AssertionType.ANALYTIC_INFERENCE,
        epistemic_scope=EpistemicScope.ANALYTIC_INFERENCE,
        subject_entity_id=candidate.subject_organization_id,
        predicate=GRAPH_CONNECTION_PREDICATE,
        object_entity_id=candidate.object_organization_id,
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.NOT_APPLICABLE,
        attribution_basis=AttributionBasis.NOT_APPLICABLE,
        world_truth_confidence=0.5,
        qualifiers={
            "mining_rule": GRAPH_CONNECTION_MINING_RULE,
            "outcome_id": candidate.outcome_id,
            "supporting_assertion_ids": list(candidate.supporting_assertion_ids),
        },
        created_at=mined_at,
        updated_at=mined_at,
    )
    relationship = Relationship(
        id=relationship_id,
        subject_id=candidate.subject_organization_id,
        predicate=GRAPH_CONNECTION_PREDICATE,
        object_id=candidate.object_organization_id,
        assertion_ids=(analytic_assertion_id,),
        created_at=mined_at,
        updated_at=mined_at,
    )
    argument_edges = tuple(
        ArgumentEdge(
            id=deterministic_mined_argument_edge_id(
                supporting_assertion_id=supporting_assertion_id,
                analytic_assertion_id=analytic_assertion_id,
            ),
            from_assertion_id=supporting_assertion_id,
            to_assertion_id=analytic_assertion_id,
            relation=ArgumentEdgeRelation.INFERS,
            rationale=(
                "The accepted Assertion participates in the same Outcome-backed graph pattern "
                "as the mined analytic inference."
            ),
            evidence_span_ids=_supporting_evidence_span_ids(
                assertion_by_id=assertion_by_id,
                supporting_assertion_id=supporting_assertion_id,
            ),
            confidence=0.7,
            created_at=mined_at,
        )
        for supporting_assertion_id in candidate.supporting_assertion_ids
    )
    records: tuple[tuple[str, str, Assertion | Relationship | ArgumentEdge], ...] = (
        ("Assertion", _stable_label("assertion", candidate), assertion),
        ("Relationship", _stable_label("relationship", candidate), relationship),
        *(
            (
                "ArgumentEdge",
                _stable_label("argument_edge", candidate, argument_edge.id),
                argument_edge,
            )
            for argument_edge in argument_edges
        ),
    )
    return tuple(
        _proposed_change(
            record_type=record_type,
            stable_label=stable_label,
            record=record,
            candidate=candidate,
            mined_at=mined_at,
        )
        for record_type, stable_label, record in records
    )


def _proposed_change(
    *,
    record_type: str,
    stable_label: str,
    record: Assertion | Relationship | ArgumentEdge,
    candidate: GraphConnectionCandidate,
    mined_at: datetime,
) -> ProposedChange:
    record_json = cast(dict[str, JsonValue], record.model_dump(mode="json"))
    proposed_json: dict[str, JsonValue] = {
        "record_type": record_type,
        "stable_label": stable_label,
        "record": record_json,
        "evidence": {
            "mining_rule": GRAPH_CONNECTION_MINING_RULE,
            "outcome_id": candidate.outcome_id,
            "supporting_assertion_ids": list(candidate.supporting_assertion_ids),
        },
    }
    return ProposedChange(
        id=deterministic_mined_proposed_change_id(
            record_type=record_type,
            stable_label=stable_label,
        ),
        review_status=ReviewStatus.PENDING,
        proposed_json=proposed_json,
        created_at=mined_at,
        updated_at=mined_at,
    )


def _candidate_digest(candidate: GraphConnectionCandidate) -> str:
    return hashlib.sha256(
        (
            f"{candidate.subject_organization_id}:{GRAPH_CONNECTION_PREDICATE}:"
            f"{candidate.object_organization_id}:{candidate.outcome_id}:"
            f"{':'.join(candidate.supporting_assertion_ids)}"
        ).encode()
    ).hexdigest()


def _stable_label(
    record_kind: str,
    candidate: GraphConnectionCandidate,
    record_id: str | None = None,
) -> str:
    parts = (
        record_kind,
        candidate.subject_organization_id,
        GRAPH_CONNECTION_PREDICATE,
        candidate.object_organization_id,
        candidate.outcome_id,
        record_id or "",
    )
    return "_".join(part for part in parts if part)


def _supporting_evidence_span_ids(
    *,
    assertion_by_id: dict[str, Assertion],
    supporting_assertion_id: str,
) -> tuple[str, ...]:
    assertion = assertion_by_id.get(supporting_assertion_id)
    if assertion is None:
        raise ValueError(
            f"Graph connection candidate references missing Assertion: {supporting_assertion_id}"
        )
    return assertion.evidence_span_ids
