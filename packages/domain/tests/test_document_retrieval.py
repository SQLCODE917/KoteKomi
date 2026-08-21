import hashlib

import pytest
from kotekomi_domain import (
    DocumentSemanticRepresentation,
    RetrievalChannel,
    RetrievalChannelObservation,
    RetrievalHit,
    deterministic_retrieval_representation_id,
    document_semantic_representation_fingerprint,
)
from pydantic import ValidationError


def test_semantic_representation_has_only_rebuild_provenance() -> None:
    fingerprint = document_semantic_representation_fingerprint(
        retrieval_unit_id="dru_fixture",
        source_snapshot_id="a" * 64,
        source_fingerprint="b" * 64,
        projection_policy_id="document_semantic_projection_v1",
        projection_builder_version="dr2_document_semantic_v1",
        renderer_policy_id="document_structural_context_v1",
        embedding_input_digest=hashlib.sha256(b"derived input").hexdigest(),
    )

    representation = DocumentSemanticRepresentation(
        retrieval_representation_id=deterministic_retrieval_representation_id(fingerprint),
        retrieval_unit_id="dru_fixture",
        source_snapshot_id="a" * 64,
        source_fingerprint="b" * 64,
        projection_builder_version="dr2_document_semantic_v1",
        renderer_policy_id="document_structural_context_v1",
        embedding_input_digest=hashlib.sha256(b"derived input").hexdigest(),
        representation_fingerprint=fingerprint,
    )

    assert "derived input" not in representation.model_dump_json()
    assert "vector" not in representation.model_dump_json()


def test_semantic_representation_rejects_an_identity_that_does_not_match_inputs() -> None:
    with pytest.raises(ValidationError, match="fingerprint"):
        DocumentSemanticRepresentation(
            retrieval_representation_id="drp_" + "a" * 24,
            retrieval_unit_id="dru_fixture",
            source_snapshot_id="a" * 64,
            source_fingerprint="b" * 64,
            projection_builder_version="dr2_document_semantic_v1",
            renderer_policy_id="document_structural_context_v1",
            embedding_input_digest="c" * 64,
            representation_fingerprint="d" * 64,
        )


def test_retrieval_hit_records_each_channel_manifest_and_fusion_score() -> None:
    hit = RetrievalHit(
        retrieval_unit_id="dru_fixture",
        authoritative_node_ids=("nod_fixture",),
        original_text_digest="a" * 64,
        channel_observations=(
            RetrievalChannelObservation(
                channel=RetrievalChannel.EXACT,
                index_manifest_id="rim_exact",
                channel_rank=1,
            ),
            RetrievalChannelObservation(
                channel=RetrievalChannel.SEMANTIC,
                index_manifest_id="rim_semantic",
                channel_rank=2,
                raw_score=0.9,
            ),
        ),
        final_rank=1,
        selected=True,
        selection_reason="rrf60_fusion",
        fusion_score=(1 / 61) + (1 / 62),
    )

    assert {item.index_manifest_id for item in hit.channel_observations} == {
        "rim_exact",
        "rim_semantic",
    }
