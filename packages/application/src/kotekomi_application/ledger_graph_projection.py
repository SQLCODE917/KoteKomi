"""Ledger graph projection use case."""

from __future__ import annotations

import hashlib
from typing import Protocol

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    Document,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    Relationship,
    Source,
)

from kotekomi_application.ports import GraphAnalyzer, GraphEdge, GraphNode, GraphProjection

HASH_ID_LENGTH = 24


class LedgerGraphRepository(Protocol):
    def list_actors(self) -> tuple[Actor, ...]: ...
    def list_organizations(self) -> tuple[Organization, ...]: ...
    def list_places(self) -> tuple[Place, ...]: ...
    def list_events(self) -> tuple[Event, ...]: ...
    def list_sources(self) -> tuple[Source, ...]: ...
    def list_documents(self) -> tuple[Document, ...]: ...
    def list_evidence_spans(self) -> tuple[EvidenceSpan, ...]: ...
    def list_assertions(self) -> tuple[Assertion, ...]: ...
    def list_relationships(self) -> tuple[Relationship, ...]: ...
    def list_outcomes(self) -> tuple[Outcome, ...]: ...
    def list_argument_edges(self) -> tuple[ArgumentEdge, ...]: ...


def project_ledger_graph(
    ledger_repository: LedgerGraphRepository,
    graph_analyzer: GraphAnalyzer,
) -> GraphProjection:
    nodes = _accepted_nodes(ledger_repository)
    node_ids = {node.id for node in nodes}
    edges = _accepted_edges(ledger_repository, node_ids)
    return graph_analyzer.project(
        nodes=tuple(sorted(nodes, key=lambda node: node.id)),
        edges=tuple(sorted(edges, key=lambda edge: edge.id)),
    )


def deterministic_graph_edge_id(
    *,
    edge_type: str,
    source_id: str,
    target_id: str,
    source_record_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{edge_type}:{source_id}:{target_id}:{source_record_id}".encode()
    ).hexdigest()
    return f"ged_{digest[:HASH_ID_LENGTH]}"


def _accepted_nodes(ledger_repository: LedgerGraphRepository) -> tuple[GraphNode, ...]:
    nodes: list[GraphNode] = []
    nodes.extend(
        GraphNode(id=record.id, node_type="Actor", label=record.name)
        for record in ledger_repository.list_actors()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Organization", label=record.name)
        for record in ledger_repository.list_organizations()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Place", label=record.name)
        for record in ledger_repository.list_places()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Event", label=record.name)
        for record in ledger_repository.list_events()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Source", label=record.title)
        for record in ledger_repository.list_sources()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Document", label=record.id)
        for record in ledger_repository.list_documents()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="EvidenceSpan", label=record.exact_text)
        for record in ledger_repository.list_evidence_spans()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Assertion", label=record.predicate)
        for record in ledger_repository.list_assertions()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Relationship", label=record.predicate)
        for record in ledger_repository.list_relationships()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="Outcome", label=record.description)
        for record in ledger_repository.list_outcomes()
    )
    nodes.extend(
        GraphNode(id=record.id, node_type="ArgumentEdge", label=record.relation.value)
        for record in ledger_repository.list_argument_edges()
    )
    return tuple(nodes)


def _accepted_edges(
    ledger_repository: LedgerGraphRepository,
    node_ids: set[str],
) -> tuple[GraphEdge, ...]:
    edges: list[GraphEdge] = []
    for actor in ledger_repository.list_actors():
        for organization_id in actor.organization_ids:
            _append_edge(edges, node_ids, actor.id, organization_id, "actor_organization", actor.id)

    for event in ledger_repository.list_events():
        if event.place_id is not None:
            _append_edge(edges, node_ids, event.id, event.place_id, "event_place", event.id)
        for actor_id in event.participant_actor_ids:
            _append_edge(edges, node_ids, event.id, actor_id, "event_actor", event.id)
        for organization_id in event.participant_organization_ids:
            _append_edge(edges, node_ids, event.id, organization_id, "event_organization", event.id)

    for document in ledger_repository.list_documents():
        _append_edge(
            edges,
            node_ids,
            document.id,
            document.source_id,
            "document_source",
            document.id,
        )

    for evidence_span in ledger_repository.list_evidence_spans():
        _append_edge(
            edges,
            node_ids,
            evidence_span.id,
            evidence_span.source_id,
            "evidence_source",
            evidence_span.id,
        )
        _append_edge(
            edges,
            node_ids,
            evidence_span.id,
            evidence_span.document_id,
            "evidence_document",
            evidence_span.id,
        )
        if evidence_span.assertion_id is not None:
            _append_edge(
                edges,
                node_ids,
                evidence_span.id,
                evidence_span.assertion_id,
                "evidence_assertion",
                evidence_span.id,
            )

    for assertion in ledger_repository.list_assertions():
        _append_edge(
            edges,
            node_ids,
            assertion.id,
            assertion.subject_entity_id,
            "assertion_subject",
            assertion.id,
        )
        if assertion.object_entity_id is not None:
            _append_edge(
                edges,
                node_ids,
                assertion.id,
                assertion.object_entity_id,
                "assertion_object",
                assertion.id,
            )
        for source_id in assertion.source_ids:
            _append_edge(edges, node_ids, assertion.id, source_id, "assertion_source", assertion.id)
        for evidence_span_id in assertion.evidence_span_ids:
            _append_edge(
                edges,
                node_ids,
                assertion.id,
                evidence_span_id,
                "assertion_evidence",
                assertion.id,
            )

    for relationship in ledger_repository.list_relationships():
        _append_edge(
            edges,
            node_ids,
            relationship.id,
            relationship.subject_id,
            "relationship_subject",
            relationship.id,
        )
        _append_edge(
            edges,
            node_ids,
            relationship.id,
            relationship.object_id,
            "relationship_object",
            relationship.id,
        )
        for assertion_id in relationship.assertion_ids:
            _append_edge(
                edges,
                node_ids,
                relationship.id,
                assertion_id,
                "relationship_assertion",
                relationship.id,
            )

    for outcome in ledger_repository.list_outcomes():
        for actor_id in outcome.actor_ids:
            _append_edge(edges, node_ids, outcome.id, actor_id, "outcome_actor", outcome.id)
        for organization_id in outcome.organization_ids:
            _append_edge(
                edges, node_ids, outcome.id, organization_id, "outcome_organization", outcome.id
            )
        for event_id in outcome.event_ids:
            _append_edge(edges, node_ids, outcome.id, event_id, "outcome_event", outcome.id)
        for assertion_id in outcome.assertion_ids:
            _append_edge(edges, node_ids, outcome.id, assertion_id, "outcome_assertion", outcome.id)

    for argument_edge in ledger_repository.list_argument_edges():
        _append_edge(
            edges,
            node_ids,
            argument_edge.id,
            argument_edge.from_assertion_id,
            "argument_from_assertion",
            argument_edge.id,
        )
        _append_edge(
            edges,
            node_ids,
            argument_edge.id,
            argument_edge.to_assertion_id,
            "argument_to_assertion",
            argument_edge.id,
        )
        for evidence_span_id in argument_edge.evidence_span_ids:
            _append_edge(
                edges,
                node_ids,
                argument_edge.id,
                evidence_span_id,
                "argument_evidence",
                argument_edge.id,
            )

    return tuple(edges)


def _append_edge(
    edges: list[GraphEdge],
    node_ids: set[str],
    source_id: str,
    target_id: str,
    edge_type: str,
    source_record_id: str,
) -> None:
    if source_id not in node_ids or target_id not in node_ids:
        return
    edges.append(
        GraphEdge(
            id=deterministic_graph_edge_id(
                edge_type=edge_type,
                source_id=source_id,
                target_id=target_id,
                source_record_id=source_record_id,
            ),
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            label=edge_type,
            source_record_id=source_record_id,
        )
    )
