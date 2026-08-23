import hashlib

import pytest
from kotekomi_domain import (
    AssertionStatus,
    DocumentRetrievalUnit,
    DocumentSemanticRepresentation,
    EvidenceGraphContribution,
    EvidenceGraphEdge,
    EvidenceNecessity,
    EvidencePolarity,
    RetrievalChannel,
    RetrievalChannelObservation,
    RetrievalHit,
    deterministic_document_retrieval_unit_id,
    deterministic_retrieval_representation_id,
    document_retrieval_unit_fingerprint,
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


def _hierarchical_unit(
    *,
    parent_node_id: str = "nod_section",
    ancestor_node_ids: tuple[str, ...] = ("nod_root", "nod_title", "nod_section"),
) -> DocumentRetrievalUnit:
    fingerprint = document_retrieval_unit_fingerprint(
        source_snapshot_id="a" * 64,
        representation_id="rep_fixture",
        node_ids=("nod_focus",),
        parent_node_id=parent_node_id,
        ancestor_node_ids=ancestor_node_ids,
        source_order=4,
        structural_role="paragraph",
        section_path=("Title", "Section"),
        source_page_numbers=(1,),
        original_text_digest="b" * 64,
        unit_policy_id="document_node_hierarchy_unit_v2",
    )
    return DocumentRetrievalUnit(
        retrieval_unit_id=deterministic_document_retrieval_unit_id(fingerprint),
        source_snapshot_id="a" * 64,
        representation_id="rep_fixture",
        node_ids=("nod_focus",),
        parent_node_id=parent_node_id,
        ancestor_node_ids=ancestor_node_ids,
        source_order=4,
        structural_role="paragraph",
        section_path=("Title", "Section"),
        source_page_numbers=(1,),
        original_text_digest="b" * 64,
        unit_policy_id="document_node_hierarchy_unit_v2",
        unit_fingerprint=fingerprint,
    )


def test_document_retrieval_unit_records_complete_ancestor_identity() -> None:
    unit = _hierarchical_unit()

    assert unit.parent_node_id == "nod_section"
    assert unit.ancestor_node_ids == ("nod_root", "nod_title", "nod_section")
    assert unit.retrieval_unit_id.startswith("dru_")


@pytest.mark.parametrize(
    ("parent_node_id", "ancestor_node_ids", "message"),
    (
        ("nod_section", (), "ancestor chain"),
        ("nod_section", ("nod_root", "nod_root", "nod_section"), "must not repeat"),
        ("nod_section", ("nod_root", "nod_focus", "nod_section"), "exclude its focal"),
        ("nod_other", ("nod_root", "nod_title", "nod_section"), "direct parent"),
    ),
)
def test_document_retrieval_unit_rejects_invalid_ancestor_identity(
    parent_node_id: str, ancestor_node_ids: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _hierarchical_unit(
            parent_node_id=parent_node_id,
            ancestor_node_ids=ancestor_node_ids,
        )


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


def test_evidence_graph_records_keep_the_validated_evidence_basis_explicit() -> None:
    contribution = EvidenceGraphContribution(
        contribution_id="egc_fixture",
        evidence_graph_edge_id="ege_fixture",
        relationship_id="rel_fixture",
        supporting_assertion_id="ast_inference",
        terminal_assertion_ids=("ast_direct",),
        assertion_evidence_link_ids=("ael_direct",),
        validation_attempt_ids=("eva_direct",),
        evidence_target_ids=("etg_direct",),
        assertion_status=AssertionStatus.CONFIRMED,
        source_authorities=(),
        evidence_polarities=(EvidencePolarity.SUPPORTS,),
        evidence_necessities=(EvidenceNecessity.REQUIRED,),
    )
    edge = EvidenceGraphEdge(
        evidence_graph_edge_id="ege_fixture",
        relationship_id="rel_fixture",
        subject_id="org_subject",
        predicate="is_subject_to_policy",
        object_id="org_object",
        contribution_ids=(contribution.contribution_id,),
    )

    assert edge.contribution_ids == ("egc_fixture",)
    assert contribution.evidence_target_ids == ("etg_direct",)


def test_evidence_graph_edge_rejects_an_empty_contribution_set() -> None:
    with pytest.raises(ValidationError, match="one or more contributions"):
        EvidenceGraphEdge(
            evidence_graph_edge_id="ege_fixture",
            relationship_id="rel_fixture",
            subject_id="org_subject",
            predicate="is_subject_to_policy",
            object_id="org_object",
            contribution_ids=(),
        )
