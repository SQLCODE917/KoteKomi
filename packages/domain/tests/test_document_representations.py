import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_domain import (
    DocumentEdge,
    DocumentEdgeProvenanceKind,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
    SourceCoordinateSystem,
    SourceRegion,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)
INPUT_DIGEST = "a" * 64


def _valid_bundle() -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_plain_text",
        representation_id="rep_plain_text",
        kind=TextViewKind.LOGICAL,
        content_digest="b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        text="hello world",
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id="nod_plain_text",
        representation_id="rep_plain_text",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=11,
    )
    quality_report = ParseQualityReport(
        id="pqr_plain_text",
        representation_id="rep_plain_text",
        metric_values={"text_char_count": 11},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_plain_text",
        document_id="doc_plain_text",
        parser_name="plain_text",
        parser_version="1",
        parser_config_digest=INPUT_DIGEST,
        processing_task_fingerprint_id="ptf_plain_text_fixture",
        input_blob_digest=INPUT_DIGEST,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root,),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root,),
        quality_report=quality_report,
    )


def _valid_spatial_bundle() -> DocumentRepresentationBundle:
    base = _valid_bundle()
    root = base.nodes[0]
    region = SourceRegion(
        id="srg_plain_text_page_1",
        representation_id=base.representation.id,
        coordinate_system=SourceCoordinateSystem.PDF_POINTS_TOP_LEFT_V1,
        page_number=1,
        page_width=612,
        page_height=792,
        left=36,
        top=36,
        right=576,
        bottom=72,
        rotation_applied=0,
    )
    paragraph = DocumentNode(
        id="nod_plain_text_paragraph",
        representation_id=base.representation.id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=base.text_views[0].id,
        start_char=0,
        end_char=11,
        source_region_ids=(region.id,),
        source_page_numbers=(1,),
        source_text_digest=hashlib.sha256(b"hello world").hexdigest(),
    )
    representation = base.representation.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                base.representation,
                text_views=base.text_views,
                nodes=(root, paragraph),
                edges=(),
                source_regions=(region,),
                quality_report=base.quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=base.text_views,
        nodes=(root, paragraph),
        source_regions=(region,),
        quality_report=base.quality_report,
    )


def test_document_representation_bundle_validates_stable_output_digest() -> None:
    bundle = _valid_bundle()

    assert bundle.representation.canonical_output_digest == canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
    )


def test_document_representation_bundle_rejects_node_range_outside_its_view() -> None:
    bundle = _valid_bundle()
    invalid_node = bundle.nodes[0].model_copy(update={"end_char": 12})

    with pytest.raises(ValueError, match="DocumentNode range must lie"):
        DocumentRepresentationBundle(
            representation=bundle.representation,
            text_views=bundle.text_views,
            nodes=(invalid_node,),
            quality_report=bundle.quality_report,
        )


def test_document_representation_bundle_rejects_digest_mismatch() -> None:
    bundle = _valid_bundle()
    invalid_representation = bundle.representation.model_copy(
        update={"canonical_output_digest": "f" * 64}
    )

    with pytest.raises(ValueError, match="canonical_output_digest"):
        DocumentRepresentationBundle(
            representation=invalid_representation,
            text_views=bundle.text_views,
            nodes=bundle.nodes,
            quality_report=bundle.quality_report,
        )


def test_representation_digest_ignores_execution_time() -> None:
    bundle = _valid_bundle()
    replay = bundle.representation.model_copy(update={"created_at": NOW + timedelta(minutes=1)})

    assert canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
    ) == canonical_representation_digest(
        replay,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
    )


def test_bundle_rejects_node_region_page_disagreement() -> None:
    bundle = _valid_spatial_bundle()
    root, paragraph = bundle.nodes
    paragraph = paragraph.model_copy(update={"source_page_numbers": (2,)})

    with pytest.raises(ValueError, match="source_page_numbers"):
        DocumentRepresentationBundle(
            representation=bundle.representation,
            text_views=bundle.text_views,
            nodes=(root, paragraph),
            source_regions=bundle.source_regions,
            quality_report=bundle.quality_report,
        )


def test_bundle_rejects_node_region_text_disagreement() -> None:
    bundle = _valid_spatial_bundle()
    root, paragraph = bundle.nodes
    paragraph = paragraph.model_copy(update={"source_text_digest": "f" * 64})

    with pytest.raises(ValueError, match="text range must agree"):
        DocumentRepresentationBundle(
            representation=bundle.representation,
            text_views=bundle.text_views,
            nodes=(root, paragraph),
            source_regions=bundle.source_regions,
            quality_report=bundle.quality_report,
        )


def test_bundle_rejects_duplicate_region_geometry_for_one_node() -> None:
    bundle = _valid_spatial_bundle()
    root, paragraph = bundle.nodes
    region = bundle.source_regions[0]
    duplicate = region.model_copy(update={"id": "srg_plain_text_page_1_duplicate"})
    paragraph = paragraph.model_copy(update={"source_region_ids": (region.id, duplicate.id)})

    with pytest.raises(ValueError, match="duplicate contradictory"):
        DocumentRepresentationBundle(
            representation=bundle.representation,
            text_views=bundle.text_views,
            nodes=(root, paragraph),
            source_regions=(region, duplicate),
            quality_report=bundle.quality_report,
        )


def test_bundle_rejects_reading_order_cycles() -> None:
    bundle = _valid_spatial_bundle()
    root, paragraph = bundle.nodes
    forward = DocumentEdge(
        id="deg_plain_text_forward",
        representation_id=bundle.representation.id,
        from_node_id=root.id,
        to_node_id=paragraph.id,
        edge_type="reading_order",
        provenance_kind=DocumentEdgeProvenanceKind.DETERMINISTIC,
        provenance_id="fixture_v1",
    )
    backward = forward.model_copy(
        update={
            "id": "deg_plain_text_backward",
            "from_node_id": paragraph.id,
            "to_node_id": root.id,
        }
    )

    with pytest.raises(ValueError, match="reading order must not contain a cycle"):
        DocumentRepresentationBundle(
            representation=bundle.representation,
            text_views=bundle.text_views,
            nodes=bundle.nodes,
            edges=(forward, backward),
            source_regions=bundle.source_regions,
            quality_report=bundle.quality_report,
        )
