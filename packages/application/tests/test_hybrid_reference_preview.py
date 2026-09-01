from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    HybridPreviewStatus,
    HybridReferencePreview,
    HybridReferencePreviewCommand,
    build_hybrid_extraction_preview,
    canonical_hybrid_extraction_preview_bytes,
    run_hybrid_reference_preview,
)
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

NOW = datetime(2026, 9, 1, tzinfo=UTC)


class FixtureLedger:
    def __init__(self, bundle: DocumentRepresentationBundle | None) -> None:
        self.bundle = bundle

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        if self.bundle is not None and self.bundle.representation.id == record_id:
            return self.bundle
        return None


class FixtureArchive:
    def __init__(self, parent_payload: bytes) -> None:
        self.parent_payload = parent_payload
        self.reference_previews: dict[str, bytes] = {}

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes:
        del preview_id
        return self.parent_payload

    def put_hybrid_extraction_preview(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("HP-2 must not publish an HP-1 Preview.")

    def put_hybrid_reference_preview(
        self,
        preview: HybridReferencePreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        self.reference_previews[preview.id] = payload
        return object()

    def read_hybrid_reference_preview(self, preview_id: str) -> bytes:
        return self.reference_previews[preview_id]


def test_run_hybrid_reference_preview_loads_parent_and_publishes_result() -> None:
    bundle = _bundle()
    parent = build_hybrid_extraction_preview(
        representation_id=bundle.representation.id,
        paragraph_node_id="nod_reference_paragraph",
        context_manifest_id="ctx_reference",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    parent_payload = canonical_hybrid_extraction_preview_bytes(parent)
    archive = FixtureArchive(parent_payload)

    result = run_hybrid_reference_preview(
        command=HybridReferencePreviewCommand(parent.id),
        ledger=FixtureLedger(bundle),
        archive=archive,
    )

    assert result.preview.parent_preview_id == parent.id
    assert result.preview.parent_preview_sha256 == hashlib.sha256(parent_payload).hexdigest()
    assert result.archive_path == f"extraction/reference-previews/{result.preview.id}.json"
    assert archive.read_hybrid_reference_preview(result.preview.id)


def test_run_rejects_noncanonical_parent_bytes() -> None:
    bundle = _bundle()
    parent = build_hybrid_extraction_preview(
        representation_id=bundle.representation.id,
        paragraph_node_id="nod_reference_paragraph",
        context_manifest_id="ctx_reference",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    noncanonical = json.dumps(parent.model_dump(mode="json"), indent=2).encode()

    with pytest.raises(ValueError, match="canonical"):
        run_hybrid_reference_preview(
            command=HybridReferencePreviewCommand(parent.id),
            ledger=FixtureLedger(bundle),
            archive=FixtureArchive(noncanonical),
        )


def test_run_rejects_missing_representation_before_publication() -> None:
    parent = build_hybrid_extraction_preview(
        representation_id="rep_missing",
        paragraph_node_id="nod_missing",
        context_manifest_id="ctx_reference",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )
    archive = FixtureArchive(canonical_hybrid_extraction_preview_bytes(parent))

    with pytest.raises(ValueError, match="missing representation"):
        run_hybrid_reference_preview(
            command=HybridReferencePreviewCommand(parent.id),
            ledger=FixtureLedger(None),
            archive=archive,
        )
    assert archive.reference_previews == {}


def _bundle() -> DocumentRepresentationBundle:
    text = "Aliases\nNational Institute of Standards and Technology (NIST) acted."
    representation_id = "rep_reference_use_case"
    view = TextView(
        id="tvw_reference_use_case",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id="nod_reference_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=view.id,
        start_char=0,
        end_char=len(text),
    )
    heading = DocumentNode(
        id="nod_reference_heading",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="heading",
        order_index=1,
        text_view_id=view.id,
        start_char=0,
        end_char=7,
    )
    paragraph = DocumentNode(
        id="nod_reference_paragraph",
        representation_id=representation_id,
        parent_node_id=heading.id,
        node_type="paragraph",
        order_index=2,
        text_view_id=view.id,
        start_char=8,
        end_char=len(text),
    )
    nodes = (root, heading, paragraph)
    quality = ParseQualityReport(
        id="pqr_reference_use_case",
        representation_id=representation_id,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id="doc_reference_use_case",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_reference_use_case",
        input_blob_digest=hashlib.sha256(text.encode()).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(view,),
                nodes=nodes,
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(view,),
        nodes=nodes,
        quality_report=quality,
    )
