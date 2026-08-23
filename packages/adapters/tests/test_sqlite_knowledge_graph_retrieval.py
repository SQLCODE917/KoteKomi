from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters.sqlite_knowledge_graph_retrieval import SQLiteKnowledgeGraphRetrievalAdapter
from kotekomi_application.knowledge_graph_retrieval import KnowledgeGraphProjectionBuildInput
from kotekomi_domain import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphRetrievalIndexManifest,
    KnowledgeGraphRetrievalUnit,
    LedgerRetrievalRecordType,
    RetrievalChannel,
)


def _build() -> KnowledgeGraphProjectionBuildInput:
    unit = KnowledgeGraphRetrievalUnit(
        retrieval_unit_id="gru_contract",
        source_record_id="rel_contract",
        record_type=LedgerRetrievalRecordType.RELATIONSHIP,
        evidence_assertion_ids=("ast_contract",),
        source_snapshot_digest="a" * 64,
        source_order=0,
        unit_policy_id="knowledge_graph_current_unit_v1",
        unit_fingerprint="b" * 64,
    )
    nodes = (
        KnowledgeGraphNode(
            node_id="org_anthropic",
            node_type="Organization",
            label="Anthropic",
            normalized_label="anthropic",
            source_order=0,
        ),
        KnowledgeGraphNode(
            node_id="rel_contract",
            node_type="Relationship",
            label="is_subject_to_policy",
            normalized_label="is_subject_to_policy",
            source_order=1,
        ),
    )
    edge = KnowledgeGraphEdge(
        edge_id="gre_contract",
        source_node_id="rel_contract",
        target_node_id="org_anthropic",
        edge_type="relationship_subject",
        source_record_id="rel_contract",
        evidence_assertion_ids=("ast_contract",),
    )
    manifest = KnowledgeGraphRetrievalIndexManifest(
        index_manifest_id="grm_contract",
        channels=(
            RetrievalChannel.EXACT,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.GRAPH_TRAVERSAL,
        ),
        source_snapshot_digest="a" * 64,
        unit_policy_id=unit.unit_policy_id,
        projection_policy_id="knowledge_graph_current_projection_v1",
        query_policy_compatibility="knowledge_graph_current_traversal_v1",
        adapter_identity="sqlite_knowledge_graph_retrieval_v1",
        adapter_configuration_digest="c" * 64,
        unit_count=1,
        node_count=2,
        edge_count=1,
        content_fingerprint="d" * 64,
        publication_status="complete",
        published_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    return KnowledgeGraphProjectionBuildInput(manifest, (unit,), nodes, (edge,))


def test_sqlite_graph_retrieval_publishes_labels_and_edges(tmp_path: Path) -> None:
    projection = SQLiteKnowledgeGraphRetrievalAdapter(tmp_path / "graph.sqlite")
    try:
        manifest, reused = projection.publish(_build())

        exact = projection.exact_seed_matches(manifest, "anthropic")
        assert reused is False
        assert exact[0].node_id == "org_anthropic"
        assert projection.load_edges(manifest)[0].edge_id == "gre_contract"
        assert projection.publish(_build())[1] is True
    finally:
        projection.close()
