import hashlib

import pytest
from kotekomi_domain import (
    DocumentSemanticRepresentation,
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
