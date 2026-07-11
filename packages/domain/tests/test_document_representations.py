from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
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
        text="hello world",
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


def test_document_representation_bundle_rejects_node_text_outside_its_view() -> None:
    bundle = _valid_bundle()
    invalid_node = bundle.nodes[0].model_copy(update={"text": "different"})

    with pytest.raises(ValueError, match="DocumentNode text must match"):
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
