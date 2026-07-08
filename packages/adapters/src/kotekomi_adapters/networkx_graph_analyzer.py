"""NetworkX implementation of the GraphAnalyzer Port."""

from __future__ import annotations

from itertools import combinations
from typing import Any, cast

import networkx as nx
from kotekomi_application import GraphConnectionCandidate, GraphEdge, GraphNode, GraphProjection

type NodeAttributes = dict[str, str]
type EdgeAttributes = dict[str, str]
type NodeRow = tuple[str, NodeAttributes]
type EdgeRow = tuple[str, str, str, EdgeAttributes]


class NetworkXGraphAnalyzer:
    def project(
        self,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> GraphProjection:
        graph = cast(Any, nx.MultiDiGraph())
        for node in nodes:
            graph.add_node(node.id, node_type=node.node_type, label=node.label)
        for edge in edges:
            graph.add_edge(
                edge.source_id,
                edge.target_id,
                key=edge.id,
                id=edge.id,
                edge_type=edge.edge_type,
                label=edge.label,
                source_record_id=edge.source_record_id,
            )
        node_rows = cast(tuple[NodeRow, ...], tuple(graph.nodes(data=True)))
        edge_rows = cast(tuple[EdgeRow, ...], tuple(graph.edges(keys=True, data=True)))
        projected_nodes = tuple(
            GraphNode(
                id=node_id,
                node_type=attributes["node_type"],
                label=attributes["label"],
            )
            for node_id, attributes in sorted(node_rows, key=lambda item: item[0])
        )
        projected_edges = tuple(
            GraphEdge(
                id=attributes["id"],
                source_id=source_id,
                target_id=target_id,
                edge_type=attributes["edge_type"],
                label=attributes["label"],
                source_record_id=attributes["source_record_id"],
            )
            for source_id, target_id, _key, attributes in sorted(
                edge_rows, key=lambda item: item[3]["id"]
            )
        )
        return GraphProjection(nodes=projected_nodes, edges=projected_edges)

    def mine_connections(
        self,
        projection: GraphProjection,
    ) -> tuple[GraphConnectionCandidate, ...]:
        graph = _graph_from_projection(projection)
        node_type_by_id = {node.id: node.node_type for node in projection.nodes}
        candidates: list[GraphConnectionCandidate] = []
        outcome_ids = sorted(node.id for node in projection.nodes if node.node_type == "Outcome")
        for outcome_id in outcome_ids:
            edge_rows = cast(
                tuple[EdgeRow, ...], tuple(graph.out_edges(outcome_id, keys=True, data=True))
            )
            organization_ids = sorted(
                target_id
                for _source_id, target_id, _key, attributes in edge_rows
                if attributes["edge_type"] == "outcome_organization"
                and node_type_by_id.get(target_id) == "Organization"
            )
            assertion_ids = sorted(
                target_id
                for _source_id, target_id, _key, attributes in edge_rows
                if attributes["edge_type"] == "outcome_assertion"
                and node_type_by_id.get(target_id) == "Assertion"
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
                for subject_organization_id, object_organization_id in combinations(
                    organization_ids, 2
                )
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


def _graph_from_projection(projection: GraphProjection) -> Any:
    graph = cast(Any, nx.MultiDiGraph())
    for node in projection.nodes:
        graph.add_node(node.id, node_type=node.node_type, label=node.label)
    for edge in projection.edges:
        graph.add_edge(
            edge.source_id,
            edge.target_id,
            key=edge.id,
            id=edge.id,
            edge_type=edge.edge_type,
            label=edge.label,
            source_record_id=edge.source_record_id,
        )
    return graph
