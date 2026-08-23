from datetime import UTC, datetime
from typing import cast

from kotekomi_application.knowledge_graph_retrieval import (
    KnowledgeGraphLedger,
    KnowledgeGraphProjectionPort,
    KnowledgeGraphSeedMatch,
    QueryKnowledgeGraphCommand,
    build_knowledge_graph_retrieval_state,
    query_knowledge_graph,
)
from kotekomi_application.ports import AcceptedCanonicalRecord
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    KnowledgeGraphRetrievalIndexManifest,
    Organization,
    Relationship,
    RetrievalChannel,
    SourceAuthority,
)

NOW = datetime(2026, 8, 23, tzinfo=UTC)


class FakeLedger:
    def __init__(self) -> None:
        self.anthropic = Organization(id="org_anthropic", name="Anthropic")
        self.department = Organization(id="org_department", name="Department of Defense")
        self.old = _assertion("ast_old", supersedes=None)
        self.current = _assertion("ast_current", supersedes="ast_old")
        self.relationship = Relationship(
            id="rel_policy",
            subject_id=self.anthropic.id,
            predicate="is_subject_to_policy",
            object_id=self.department.id,
            assertion_ids=(self.current.id,),
            created_at=NOW,
            updated_at=NOW,
        )

    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]:
        return (self.anthropic, self.department, self.old, self.current, self.relationship)


def _assertion(assertion_id: str, supersedes: str | None) -> Assertion:
    return Assertion(
        id=assertion_id,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="is_subject_to_policy",
        object_value="Directive 3000.09",
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=("src_test",),
        evidence_target_ids=("etg_test",),
        supersedes_assertion_id=supersedes,
        provenance_activity_ids=("prv_test",),
        created_at=NOW,
        updated_at=NOW,
    )


def test_graph_state_excludes_superseded_predecessors_and_keeps_evidence_links() -> None:
    units, nodes, edges, snapshot = build_knowledge_graph_retrieval_state(FakeLedger())

    assert snapshot
    assert {unit.source_record_id for unit in units} == {"ast_current", "rel_policy"}
    assert {node.node_id for node in nodes} >= {
        "org_anthropic",
        "org_department",
        "ast_current",
        "rel_policy",
    }
    relationship_edges = [edge for edge in edges if edge.source_record_id == "rel_policy"]
    assert {edge.edge_type for edge in relationship_edges} == {
        "relationship_assertion",
        "relationship_object",
        "relationship_subject",
    }
    assert all(edge.evidence_assertion_ids == ("ast_current",) for edge in relationship_edges)


class AmbiguousProjection:
    def __init__(self, manifest: KnowledgeGraphRetrievalIndexManifest) -> None:
        self.manifest = manifest
        self.saved_records: list[object] = []

    def get_complete_manifest(self) -> KnowledgeGraphRetrievalIndexManifest:
        return self.manifest

    def exact_seed_matches(
        self, manifest: KnowledgeGraphRetrievalIndexManifest, normalized_seed: str
    ) -> tuple[KnowledgeGraphSeedMatch, ...]:
        del manifest, normalized_seed
        return (
            KnowledgeGraphSeedMatch(
                node_id="org_anthropic_a",
                node_type="Organization",
                label="Anthropic",
                channel=RetrievalChannel.EXACT,
                channel_rank=1,
            ),
            KnowledgeGraphSeedMatch(
                node_id="org_anthropic_b",
                node_type="Organization",
                label="Anthropic",
                channel=RetrievalChannel.EXACT,
                channel_rank=2,
            ),
        )

    def lexical_seed_matches(
        self, manifest: KnowledgeGraphRetrievalIndexManifest, seed_text: str
    ) -> tuple[KnowledgeGraphSeedMatch, ...]:
        del manifest, seed_text
        return ()

    def load_edges(self, manifest: KnowledgeGraphRetrievalIndexManifest) -> tuple[object, ...]:
        del manifest
        return ()

    def save_query_record(self, record: object) -> None:
        self.saved_records.append(record)


class NoopTokenizer:
    tokenizer_id = "test"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input)


def test_ambiguous_seed_records_candidates_and_typed_failure() -> None:
    ledger = FakeLedger()
    _, _, _, snapshot = build_knowledge_graph_retrieval_state(ledger)
    manifest = KnowledgeGraphRetrievalIndexManifest(
        index_manifest_id="grm_ambiguous",
        channels=(
            RetrievalChannel.EXACT,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.GRAPH_TRAVERSAL,
        ),
        source_snapshot_digest=snapshot,
        unit_policy_id="knowledge_graph_current_unit_v1",
        projection_policy_id="knowledge_graph_current_projection_v1",
        query_policy_compatibility="knowledge_graph_current_traversal_v1",
        adapter_identity="test",
        adapter_configuration_digest="a" * 64,
        unit_count=0,
        node_count=0,
        edge_count=0,
        content_fingerprint="b" * 64,
        publication_status="complete",
        published_at=NOW,
    )
    projection = AmbiguousProjection(manifest)

    result = query_knowledge_graph(
        QueryKnowledgeGraphCommand(seed_text="Anthropic"),
        ledger_repository=cast(KnowledgeGraphLedger, ledger),
        projection=cast(KnowledgeGraphProjectionPort, projection),
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.value == "knowledge_graph_seed_ambiguous"
    assert len(result.seed_candidates) == 2
    assert len(projection.saved_records) == 1


def test_stale_graph_manifest_blocks_query_before_seed_resolution() -> None:
    ledger = FakeLedger()
    manifest = KnowledgeGraphRetrievalIndexManifest(
        index_manifest_id="grm_stale",
        channels=(
            RetrievalChannel.EXACT,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.GRAPH_TRAVERSAL,
        ),
        source_snapshot_digest="f" * 64,
        unit_policy_id="knowledge_graph_current_unit_v1",
        projection_policy_id="knowledge_graph_current_projection_v1",
        query_policy_compatibility="knowledge_graph_current_traversal_v1",
        adapter_identity="test",
        adapter_configuration_digest="a" * 64,
        unit_count=0,
        node_count=0,
        edge_count=0,
        content_fingerprint="b" * 64,
        publication_status="complete",
        published_at=NOW,
    )

    result = query_knowledge_graph(
        QueryKnowledgeGraphCommand(seed_text="Anthropic"),
        ledger_repository=cast(KnowledgeGraphLedger, ledger),
        projection=cast(KnowledgeGraphProjectionPort, AmbiguousProjection(manifest)),
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.value == "knowledge_graph_index_stale"
