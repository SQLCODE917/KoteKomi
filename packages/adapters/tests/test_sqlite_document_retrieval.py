import hashlib
import struct
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters.sqlite_document_retrieval import SQLiteDocumentRetrievalAdapter
from kotekomi_application.document_retrieval import (
    ProjectionBuildInput,
    SemanticProjectionBuildInput,
    SemanticVectorRecord,
)
from kotekomi_domain import (
    DocumentExactLexicalRepresentation,
    DocumentRetrievalUnit,
    DocumentSemanticRepresentation,
    EmbeddingModelIdentity,
    RetrievalChannel,
    RetrievalIndexManifest,
    deterministic_document_retrieval_unit_id,
    deterministic_retrieval_representation_id,
    document_exact_lexical_representation_fingerprint,
    document_retrieval_unit_fingerprint,
    document_semantic_representation_fingerprint,
)


def _build() -> ProjectionBuildInput:
    original_text_digest = hashlib.sha256(b"Needle phrase").hexdigest()
    unit_fingerprint = document_retrieval_unit_fingerprint(
        source_snapshot_id="a" * 64,
        representation_id="rep_retrieval_fixture",
        node_ids=("nod_retrieval_fixture",),
        source_order=1,
        structural_role="paragraph",
        section_path=("Fixture",),
        source_page_numbers=(1,),
        original_text_digest=original_text_digest,
        unit_policy_id="document_node_unit_v1",
    )
    unit = DocumentRetrievalUnit(
        retrieval_unit_id=deterministic_document_retrieval_unit_id(unit_fingerprint),
        source_snapshot_id="a" * 64,
        representation_id="rep_retrieval_fixture",
        node_ids=("nod_retrieval_fixture",),
        source_order=1,
        structural_role="paragraph",
        section_path=("Fixture",),
        source_page_numbers=(1,),
        original_text_digest=original_text_digest,
        unit_fingerprint=unit_fingerprint,
    )
    exact_fields = {
        "body_nfc": "Needle phrase",
        "body_casefold": "needle phrase",
        "source_title_nfc": "Fixture title",
        "heading_path_nfc": "Fixture",
    }
    lexical_fields = {
        "body": "Needle phrase lexical retrieval",
        "heading_path": "Fixture",
        "source_title": "Fixture title",
        "structural_role": "paragraph",
    }
    field_digests = {
        name: hashlib.sha256(value.encode("utf-8")).hexdigest()
        for name, value in {**exact_fields, **lexical_fields}.items()
    }
    representation_fingerprint = document_exact_lexical_representation_fingerprint(
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint="b" * 64,
        projection_policy_id="document_exact_lexical_projection_v1",
        projection_builder_version="fixture-v1",
        exact_fields=exact_fields,
        lexical_fields=lexical_fields,
        field_digests=field_digests,
    )
    representation = DocumentExactLexicalRepresentation(
        retrieval_representation_id=deterministic_retrieval_representation_id(
            representation_fingerprint
        ),
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint="b" * 64,
        projection_builder_version="fixture-v1",
        exact_fields=exact_fields,
        lexical_fields=lexical_fields,
        field_digests=field_digests,
        representation_fingerprint=representation_fingerprint,
    )
    manifest = RetrievalIndexManifest(
        index_manifest_id="rim_retrieval_fixture",
        channels=(RetrievalChannel.EXACT, RetrievalChannel.LEXICAL),
        source_snapshot_id=unit.source_snapshot_id,
        representation_id=unit.representation_id,
        representation_digest="b" * 64,
        unit_policy_id="document_node_unit_v1",
        projection_policy_id="document_exact_lexical_projection_v1",
        query_policy_compatibility="document_exact_before_lexical_v1",
        adapter_identity="fixture",
        adapter_configuration_digest="c" * 64,
        unit_count=1,
        representation_count=1,
        content_fingerprint="d" * 64,
        publication_status="complete",
        published_at=datetime(2026, 8, 21, tzinfo=UTC),
    )
    return ProjectionBuildInput(manifest, (unit,), (representation,))


def test_sqlite_document_retrieval_is_exact_lexical_and_rebuildable(tmp_path: Path) -> None:
    build = _build()
    adapter = SQLiteDocumentRetrievalAdapter(tmp_path / "retrieval.sqlite")
    try:
        manifest, reused = adapter.publish(build)
        repeated, repeated_reused = adapter.publish(build)

        assert not reused
        assert repeated_reused
        assert repeated == manifest
        exact = adapter.exact_candidates(manifest, "needle")
        lexical = adapter.lexical_candidates(manifest, "lexical")
        assert [candidate.retrieval_unit_id for candidate in exact] == [
            build.units[0].retrieval_unit_id
        ]
        assert [candidate.retrieval_unit_id for candidate in lexical] == [
            build.units[0].retrieval_unit_id
        ]

        adapter.delete_projection(manifest.representation_id)

        assert adapter.get_complete_manifest(manifest.representation_id) is None
        rebuilt, rebuilt_reused = adapter.publish(build)
        assert not rebuilt_reused
        assert rebuilt == manifest
        assert adapter.exact_candidates(rebuilt, "Needle") == adapter.exact_candidates(
            manifest, "Needle"
        )
    finally:
        adapter.close()


def test_sqlite_document_retrieval_keeps_semantic_projection_separate(tmp_path: Path) -> None:
    exact_build = _build()
    unit = exact_build.units[0]
    vector = struct.pack("<3f", 1.0, 0.0, 0.0)
    semantic_fingerprint = document_semantic_representation_fingerprint(
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint="b" * 64,
        projection_policy_id="document_semantic_projection_v1",
        projection_builder_version="fixture-v1",
        renderer_policy_id="document_structural_context_v1",
        embedding_input_digest="e" * 64,
    )
    semantic_representation = DocumentSemanticRepresentation(
        retrieval_representation_id=deterministic_retrieval_representation_id(semantic_fingerprint),
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint="b" * 64,
        projection_builder_version="fixture-v1",
        renderer_policy_id="document_structural_context_v1",
        embedding_input_digest="e" * 64,
        representation_fingerprint=semantic_fingerprint,
    )
    semantic_manifest = RetrievalIndexManifest(
        index_manifest_id="rim_semantic_fixture",
        channels=(RetrievalChannel.SEMANTIC,),
        source_snapshot_id=unit.source_snapshot_id,
        representation_id=unit.representation_id,
        representation_digest="b" * 64,
        unit_policy_id="document_node_unit_v1",
        projection_policy_id="document_semantic_projection_v1",
        query_policy_compatibility="document_semantic_v1",
        adapter_identity="fixture",
        adapter_configuration_digest="c" * 64,
        embedding_profile_id="semantic-validation-v1",
        embedding_model_identity=EmbeddingModelIdentity(
            adapter_id="lm_studio",
            model_id="nomic",
            model_digest="f" * 64,
            vector_dimension=3,
            configuration_digest="c" * 64,
        ),
        unit_count=1,
        representation_count=1,
        content_fingerprint="d" * 64,
        publication_status="complete",
        published_at=datetime(2026, 8, 21, tzinfo=UTC),
    )
    build = SemanticProjectionBuildInput(
        semantic_manifest,
        (unit,),
        (semantic_representation,),
        (
            SemanticVectorRecord(
                unit.retrieval_unit_id,
                vector,
                hashlib.sha256(vector).hexdigest(),
            ),
        ),
    )
    adapter = SQLiteDocumentRetrievalAdapter(tmp_path / "retrieval.sqlite")
    try:
        adapter.publish(exact_build)
        manifest, reused = adapter.publish_semantic(build)

        assert not reused
        assert adapter.get_complete_manifest(unit.representation_id) is not None
        assert (
            adapter.get_complete_semantic_manifest(unit.representation_id, "semantic-validation-v1")
            == manifest
        )
        assert adapter.semantic_candidates(manifest, vector)[0].raw_score == 1.0

        adapter.delete_semantic_projection(unit.representation_id, "semantic-validation-v1")

        assert (
            adapter.get_complete_semantic_manifest(unit.representation_id, "semantic-validation-v1")
            is None
        )
        assert adapter.get_complete_manifest(unit.representation_id) is not None
    finally:
        adapter.close()
