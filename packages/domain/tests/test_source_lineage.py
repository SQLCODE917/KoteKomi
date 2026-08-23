from datetime import UTC, datetime

from kotekomi_domain import (
    CrossSourceRelationState,
    EvidenceGraphLineageCluster,
    SourceLineageRelation,
    SourceLineageRelationType,
)
from pydantic import ValidationError
from pytest import raises

NOW = datetime(2026, 8, 23, tzinfo=UTC)


def test_source_lineage_relation_requires_two_ordered_distinct_documents() -> None:
    with raises(ValidationError, match="distinct and lexically ordered"):
        SourceLineageRelation(
            id="slr_contract",
            document_ids=("doc_second", "doc_first"),
            relation_type=SourceLineageRelationType.VERBATIM_REPUBLICATION,
            shared_content_sha256="a" * 64,
            rationale="The archived bytes are identical.",
            review_provenance_activity_id="prv_contract",
            reviewed_at=NOW,
        )


def test_recorded_lineage_cluster_requires_a_reviewed_relation() -> None:
    with raises(ValidationError, match="require accepted relations"):
        EvidenceGraphLineageCluster(
            lineage_cluster_id="lcl_contract",
            document_ids=("doc_first", "doc_second"),
            cross_source_relation_state=CrossSourceRelationState.RECORDED_RELATION,
            source_snapshot_digest="a" * 64,
            policy_id="reviewed_exact_content_sha256_v1",
            cluster_fingerprint="b" * 64,
        )
