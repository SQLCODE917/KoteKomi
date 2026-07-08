"""NetworkX implementation of the GraphAnalyzer Port."""

from __future__ import annotations

from typing import Any, cast

import networkx as nx
from kotekomi_application import GraphEdge, GraphNode, GraphProjection

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
