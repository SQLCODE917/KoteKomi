from kotekomi_adapters import NetworkXGraphAnalyzer
from kotekomi_application import GraphEdge, GraphNode, GraphProjection


def test_networkx_graph_analyzer_projects_nodes_and_edges() -> None:
    analyzer = NetworkXGraphAnalyzer()
    nodes = (
        GraphNode(id="org_lab_a", node_type="Organization", label="Lab A"),
        GraphNode(id="act_person_a", node_type="Actor", label="Person A"),
    )
    edges = (
        GraphEdge(
            id="ged_actor_org",
            source_id="act_person_a",
            target_id="org_lab_a",
            edge_type="actor_organization",
            label="actor_organization",
            source_record_id="act_person_a",
        ),
    )

    projection = analyzer.project(nodes=nodes, edges=edges)

    assert projection == GraphProjection(
        nodes=(
            GraphNode(id="act_person_a", node_type="Actor", label="Person A"),
            GraphNode(id="org_lab_a", node_type="Organization", label="Lab A"),
        ),
        edges=edges,
    )


def test_networkx_graph_analyzer_sorts_edges_by_id() -> None:
    analyzer = NetworkXGraphAnalyzer()
    nodes = (
        GraphNode(id="act_person_a", node_type="Actor", label="Person A"),
        GraphNode(id="org_lab_a", node_type="Organization", label="Lab A"),
        GraphNode(id="evt_model_forum", node_type="Event", label="Model Forum"),
    )
    edges = (
        GraphEdge(
            id="ged_z",
            source_id="evt_model_forum",
            target_id="act_person_a",
            edge_type="event_actor",
            label="event_actor",
            source_record_id="evt_model_forum",
        ),
        GraphEdge(
            id="ged_a",
            source_id="act_person_a",
            target_id="org_lab_a",
            edge_type="actor_organization",
            label="actor_organization",
            source_record_id="act_person_a",
        ),
    )

    projection = analyzer.project(nodes=nodes, edges=edges)

    assert tuple(edge.id for edge in projection.edges) == ("ged_a", "ged_z")


def test_networkx_graph_analyzer_projects_empty_graph() -> None:
    analyzer = NetworkXGraphAnalyzer()

    projection = analyzer.project(nodes=(), edges=())

    assert projection == GraphProjection(nodes=(), edges=())
