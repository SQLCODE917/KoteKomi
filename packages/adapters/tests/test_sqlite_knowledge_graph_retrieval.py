import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters.sqlite_knowledge_graph_retrieval import SQLiteKnowledgeGraphRetrievalAdapter
from kotekomi_application.evidence_graph_projection import (
    EvidenceGraphError,
    EvidenceGraphFailureCode,
    EvidenceGraphProjectionBuildInput,
)
from kotekomi_application.knowledge_graph_retrieval import KnowledgeGraphProjectionBuildInput
from kotekomi_domain import (
    AssertionStatus,
    CrossSourceRelationState,
    EvidenceGraphContribution,
    EvidenceGraphEdge,
    EvidenceGraphLineageCluster,
    EvidenceGraphLineageMembership,
    EvidenceGraphProjectionManifest,
    EvidenceNecessity,
    EvidencePolarity,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphRetrievalIndexManifest,
    KnowledgeGraphRetrievalUnit,
    LedgerRetrievalRecordType,
    RetrievalChannel,
)
from pytest import raises


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


def _evidence_build() -> EvidenceGraphProjectionBuildInput:
    edge = EvidenceGraphEdge(
        evidence_graph_edge_id="ege_contract",
        relationship_id="rel_contract",
        subject_id="org_anthropic",
        predicate="is_subject_to_policy",
        object_id="org_department",
        contribution_ids=("egc_contract",),
    )
    contribution = EvidenceGraphContribution(
        contribution_id="egc_contract",
        evidence_graph_edge_id=edge.evidence_graph_edge_id,
        relationship_id=edge.relationship_id,
        supporting_assertion_id="ast_contract",
        terminal_assertion_ids=("ast_contract",),
        assertion_evidence_link_ids=("ael_contract",),
        validation_attempt_ids=("eva_contract",),
        evidence_target_ids=("etg_contract",),
        source_document_ids=("doc_contract",),
        lineage_memberships=(
            EvidenceGraphLineageMembership(
                document_id="doc_contract",
                lineage_cluster_id="lcl_contract",
                cross_source_relation_state=CrossSourceRelationState.NO_CROSS_SOURCE_RELATION_RECORDED,
            ),
        ),
        assertion_status=AssertionStatus.REPORTED,
        source_authorities=(),
        evidence_polarities=(EvidencePolarity.SUPPORTS,),
        evidence_necessities=(EvidenceNecessity.REQUIRED,),
    )
    cluster = EvidenceGraphLineageCluster(
        lineage_cluster_id="lcl_contract",
        document_ids=("doc_contract",),
        cross_source_relation_state=CrossSourceRelationState.NO_CROSS_SOURCE_RELATION_RECORDED,
        source_snapshot_digest="a" * 64,
        policy_id="reviewed_exact_content_sha256_v1",
        cluster_fingerprint="d" * 64,
    )
    manifest = EvidenceGraphProjectionManifest(
        projection_manifest_id="egm_contract",
        source_snapshot_digest="a" * 64,
        projection_policy_id="evidence_graph_relationship_contributions_v1",
        builder_version="dr6_1_evidence_graph_projection_v1",
        adapter_identity="sqlite_evidence_graph_projection_v1",
        adapter_configuration_digest="b" * 64,
        edge_count=1,
        contribution_count=1,
        lineage_cluster_count=1,
        content_fingerprint="c" * 64,
        publication_status="complete",
        published_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    return EvidenceGraphProjectionBuildInput(manifest, (edge,), (contribution,), (cluster,))


def test_sqlite_evidence_graph_projection_publishes_and_rebuilds(tmp_path: Path) -> None:
    projection = SQLiteKnowledgeGraphRetrievalAdapter(tmp_path / "graph.sqlite")
    try:
        manifest, reused = projection.publish_evidence_graph(_evidence_build())

        assert reused is False
        assert projection.get_complete_evidence_graph_manifest() == manifest
        edge = projection.load_evidence_graph_edge(manifest, "rel_contract")
        assert edge is not None
        assert edge.evidence_graph_edge_id == "ege_contract"
        assert projection.load_evidence_graph_contributions(manifest, edge.evidence_graph_edge_id)[
            0
        ].evidence_target_ids == ("etg_contract",)
        clusters = projection.load_evidence_graph_lineage_clusters(manifest, ("lcl_contract",))
        assert clusters[0].document_ids == ("doc_contract",)
        projection.delete_evidence_graph_projection()
        assert projection.get_complete_evidence_graph_manifest() is None
        assert projection.publish_evidence_graph(_evidence_build())[1] is False
    finally:
        projection.close()


def test_sqlite_evidence_graph_projection_rejects_manifest_with_missing_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "graph.sqlite"
    projection = SQLiteKnowledgeGraphRetrievalAdapter(database_path)
    try:
        projection.publish_evidence_graph(_evidence_build())
        with sqlite3.connect(database_path) as connection:
            connection.execute("DELETE FROM evidence_graph_contributions")

        with raises(EvidenceGraphError) as raised:
            projection.get_complete_evidence_graph_manifest()

        assert raised.value.code is EvidenceGraphFailureCode.PROJECTION_CORRUPT
    finally:
        projection.close()
