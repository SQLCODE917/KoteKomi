from kotekomi_adapters import NetworkXGraphAnalyzer
from kotekomi_application import GraphConnectionCandidate, GraphEdge, GraphNode, GraphProjection


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


def test_networkx_graph_analyzer_mines_outcome_backed_organization_candidate() -> None:
    analyzer = NetworkXGraphAnalyzer()
    projection = GraphProjection(
        nodes=(
            GraphNode(id="org_anthropic", node_type="Organization", label="Anthropic"),
            GraphNode(
                id="org_commerce_department",
                node_type="Organization",
                label="Commerce Department",
            ),
            GraphNode(id="ast_delay", node_type="Assertion", label="postponed_rollout"),
            GraphNode(id="ast_suspension", node_type="Assertion", label="suspended_access"),
            GraphNode(id="out_monitoring_update", node_type="Outcome", label="Access restored"),
        ),
        edges=(
            graph_edge("ged_1", "out_monitoring_update", "org_anthropic", "outcome_organization"),
            graph_edge(
                "ged_2",
                "out_monitoring_update",
                "org_commerce_department",
                "outcome_organization",
            ),
            graph_edge("ged_3", "out_monitoring_update", "ast_delay", "outcome_assertion"),
            graph_edge("ged_4", "out_monitoring_update", "ast_suspension", "outcome_assertion"),
        ),
    )

    candidates = analyzer.mine_connections(projection)

    assert candidates == (
        GraphConnectionCandidate(
            subject_organization_id="org_anthropic",
            object_organization_id="org_commerce_department",
            outcome_id="out_monitoring_update",
            supporting_assertion_ids=("ast_delay", "ast_suspension"),
        ),
    )


def test_networkx_graph_analyzer_sorts_mined_candidates() -> None:
    analyzer = NetworkXGraphAnalyzer()
    projection = GraphProjection(
        nodes=(
            GraphNode(id="org_z", node_type="Organization", label="Z"),
            GraphNode(id="org_a", node_type="Organization", label="A"),
            GraphNode(id="org_m", node_type="Organization", label="M"),
            GraphNode(id="ast_b", node_type="Assertion", label="b"),
            GraphNode(id="ast_a", node_type="Assertion", label="a"),
            GraphNode(id="out_z", node_type="Outcome", label="Z outcome"),
        ),
        edges=(
            graph_edge("ged_1", "out_z", "org_z", "outcome_organization"),
            graph_edge("ged_2", "out_z", "org_a", "outcome_organization"),
            graph_edge("ged_3", "out_z", "org_m", "outcome_organization"),
            graph_edge("ged_4", "out_z", "ast_b", "outcome_assertion"),
            graph_edge("ged_5", "out_z", "ast_a", "outcome_assertion"),
        ),
    )

    candidates = analyzer.mine_connections(projection)

    assert tuple(
        (candidate.subject_organization_id, candidate.object_organization_id)
        for candidate in candidates
    ) == (("org_a", "org_m"), ("org_a", "org_z"), ("org_m", "org_z"))
    assert {candidate.supporting_assertion_ids for candidate in candidates} == {("ast_a", "ast_b")}


def test_networkx_graph_analyzer_ignores_outcomes_without_enough_support() -> None:
    analyzer = NetworkXGraphAnalyzer()
    projection = GraphProjection(
        nodes=(
            GraphNode(id="org_anthropic", node_type="Organization", label="Anthropic"),
            GraphNode(
                id="org_commerce_department",
                node_type="Organization",
                label="Commerce Department",
            ),
            GraphNode(id="ast_delay", node_type="Assertion", label="postponed_rollout"),
            GraphNode(id="out_monitoring_update", node_type="Outcome", label="Access restored"),
        ),
        edges=(
            graph_edge("ged_1", "out_monitoring_update", "org_anthropic", "outcome_organization"),
            graph_edge(
                "ged_2",
                "out_monitoring_update",
                "org_commerce_department",
                "outcome_organization",
            ),
            graph_edge("ged_3", "out_monitoring_update", "ast_delay", "outcome_assertion"),
        ),
    )

    assert analyzer.mine_connections(projection) == ()


def graph_edge(
    edge_id: str,
    source_id: str,
    target_id: str,
    edge_type: str,
) -> GraphEdge:
    return GraphEdge(
        id=edge_id,
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        label=edge_type,
        source_record_id=source_id,
    )
