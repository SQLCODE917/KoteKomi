import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from kotekomi_adapters import (
    ImmutableRecordConflict,
    NonDeterministicParserOutputConflict,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    BundleCommitDisposition,
    deterministic_representation_id,
)
from kotekomi_domain import (
    DocumentEdge,
    DocumentEdgeProvenanceKind,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
    SourceRegion,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

from .domain_fixtures import sample_domain_records

NOW = datetime(2026, 7, 11, tzinfo=UTC)
INPUT_DIGEST = "a" * 64
CONFIG_DIGEST = "b" * 64
LARGE_PARAGRAPH_COUNT = 4096
UNRELATED_REPRESENTATION_COUNT = 6
UNRELATED_PARAGRAPH_COUNT = 256
REPRESENTATION_CHILD_INDEXES = {
    "text_views": "idx_text_views_representation_id",
    "document_nodes": "idx_document_nodes_representation_id",
    "document_edges": "idx_document_edges_representation_id",
    "source_regions": "idx_source_regions_representation_id",
    "parse_quality_reports": "idx_parse_quality_reports_representation_id",
}


def initialize_ledger_with_representation_parent(ledger_path: Path) -> None:
    SQLiteLedgerInitializer(ledger_path).initialize()
    source, document = sample_domain_records()[5:7]
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_source(source)
        repository.save_document(document.model_copy(update={"id": "doc_representation_fixture"}))


def bundle(
    *,
    parser_version: str = "1",
    parser_config_digest: str = CONFIG_DIGEST,
    task_fingerprint_id: str | None = None,
    created_at: datetime = NOW,
    text: str = "hello",
) -> DocumentRepresentationBundle:
    resolved_task_id = task_fingerprint_id or (
        f"ptf_{hashlib.sha256(f'{parser_version}:{parser_config_digest}'.encode()).hexdigest()[:24]}"
    )
    representation_id = deterministic_representation_id(resolved_task_id)
    representation_key = representation_id.removeprefix("rep_")
    text_view = TextView(
        id=f"tvw_{representation_key}_logical",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="fixture_v1",
    )
    root = DocumentNode(
        id=f"nod_{representation_key}_document",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    quality_report = ParseQualityReport(
        id=f"pqr_{representation_key}_quality_v1",
        representation_id=representation_id,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id="doc_representation_fixture",
        parser_name="fixture_parser",
        parser_version=parser_version,
        parser_config_digest=parser_config_digest,
        processing_task_fingerprint_id=resolved_task_id,
        input_blob_digest=INPUT_DIGEST,
        canonical_output_digest="0" * 64,
        created_at=created_at,
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


def synthetic_bundle(
    *, task_fingerprint_id: str, paragraph_count: int
) -> DocumentRepresentationBundle:
    representation_id = deterministic_representation_id(task_fingerprint_id)
    representation_key = representation_id.removeprefix("rep_")
    text = "x" * paragraph_count
    text_view = TextView(
        id=f"tvw_{representation_key}_logical",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="synthetic_v1",
    )
    source_region = SourceRegion(
        id=f"srg_{representation_key}_page_1",
        representation_id=representation_id,
        coordinate_system="pdf_points",
        page_number=1,
        page_width=612,
        page_height=792,
        left=0,
        top=0,
        right=612,
        bottom=792,
    )
    root = DocumentNode(
        id=f"nod_{representation_key}_document",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    paragraphs = tuple(
        DocumentNode(
            id=f"nod_{representation_key}_paragraph_{index}",
            representation_id=representation_id,
            parent_node_id=root.id,
            node_type="paragraph",
            order_index=index,
            text_view_id=text_view.id,
            start_char=index,
            end_char=index + 1,
            source_region_ids=(source_region.id,),
        )
        for index in range(paragraph_count)
    )
    edge = DocumentEdge(
        id=f"deg_{representation_key}_root_to_first_paragraph",
        representation_id=representation_id,
        from_node_id=root.id,
        to_node_id=paragraphs[0].id,
        edge_type="contains",
        provenance_kind=DocumentEdgeProvenanceKind.DETERMINISTIC,
        provenance_id="synthetic_v1",
    )
    quality_report = ParseQualityReport(
        id=f"pqr_{representation_key}_quality_v1",
        representation_id=representation_id,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id="doc_representation_fixture",
        parser_name="synthetic_parser",
        parser_version="1",
        parser_config_digest=CONFIG_DIGEST,
        processing_task_fingerprint_id=task_fingerprint_id,
        input_blob_digest=INPUT_DIGEST,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root, *paragraphs),
                edges=(edge,),
                source_regions=(source_region,),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, *paragraphs),
        edges=(edge,),
        source_regions=(source_region,),
        quality_report=quality_report,
    )


def test_representation_bundle_reuses_a_semantic_replay_after_restart(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    initialize_ledger_with_representation_parent(ledger_path)
    original = bundle()
    replay = bundle(created_at=NOW + timedelta(minutes=1))

    with sqlite_ledger_transaction(ledger_path) as repository:
        created = repository.commit_document_representation_bundle(original)
    with sqlite_ledger_transaction(ledger_path) as repository:
        reused = repository.commit_document_representation_bundle(replay)
        stored = repository.get_document_representation_bundle(original.representation.id)

    assert created.disposition is BundleCommitDisposition.CREATED
    assert reused.disposition is BundleCommitDisposition.REUSED
    assert original.representation.id == replay.representation.id
    assert stored is not None
    assert stored.representation.created_at == NOW


def test_representation_bundle_load_uses_representation_ownership_indexes(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    initialize_ledger_with_representation_parent(ledger_path)
    first = bundle(parser_version="1")
    second = bundle(parser_version="2")

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.commit_document_representation_bundle(first)
        repository.commit_document_representation_bundle(second)
        assert repository.get_document_representation_bundle(first.representation.id) == first

    with sqlite3.connect(ledger_path) as connection:
        query_plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT payload_json FROM text_views WHERE representation_id = ?",
            (first.representation.id,),
        ).fetchall()
    assert any("idx_text_views_representation_id" in row[-1] for row in query_plan)


def test_large_representation_bundle_load_uses_only_owned_rows(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    initialize_ledger_with_representation_parent(ledger_path)
    target = synthetic_bundle(
        task_fingerprint_id="ptf_large_target",
        paragraph_count=LARGE_PARAGRAPH_COUNT,
    )
    unrelated_bundles = tuple(
        synthetic_bundle(
            task_fingerprint_id=f"ptf_unrelated_{index}",
            paragraph_count=UNRELATED_PARAGRAPH_COUNT,
        )
        for index in range(UNRELATED_REPRESENTATION_COUNT)
    )

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.commit_document_representation_bundle(target)
        for unrelated_bundle in unrelated_bundles:
            repository.commit_document_representation_bundle(unrelated_bundle)

    with sqlite_ledger_transaction(ledger_path) as repository:
        loaded = repository.get_document_representation_bundle(target.representation.id)

    assert loaded is not None
    assert loaded.representation == target.representation
    assert loaded.text_views == target.text_views
    assert loaded.nodes == tuple(sorted(target.nodes, key=lambda node: node.id))
    assert loaded.edges == target.edges
    assert loaded.source_regions == target.source_regions
    assert loaded.quality_report == target.quality_report
    with sqlite3.connect(ledger_path) as connection:
        for table_name, index_name in REPRESENTATION_CHILD_INDEXES.items():
            query_plan = connection.execute(
                f"EXPLAIN QUERY PLAN SELECT payload_json FROM {table_name} "
                "WHERE representation_id = ? ORDER BY id",
                (target.representation.id,),
            ).fetchall()
            assert any(index_name in row[-1] for row in query_plan)


def test_representation_bundle_rejects_nondeterministic_output_without_mutation(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    initialize_ledger_with_representation_parent(ledger_path)
    original = bundle()
    different_output = bundle(text="different")

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.commit_document_representation_bundle(original)
    with pytest.raises(NonDeterministicParserOutputConflict):
        with sqlite_ledger_transaction(ledger_path) as repository:
            repository.commit_document_representation_bundle(different_output)
    with sqlite_ledger_transaction(ledger_path) as repository:
        stored = repository.get_document_representation_bundle(original.representation.id)

    assert stored == original


def test_representation_bundle_rejects_partial_child_conflict_without_siblings(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    initialize_ledger_with_representation_parent(ledger_path)
    candidate = bundle()
    conflicting_view = candidate.text_views[0].model_copy(
        update={"representation_id": "rep_other", "text": "other"}
    )
    conflicting_view = conflicting_view.model_copy(
        update={"content_digest": hashlib.sha256(b"other").hexdigest()}
    )

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_document_representation(
            candidate.representation.model_copy(update={"id": "rep_other"})
        )
        repository.save_text_view(conflicting_view)
    with pytest.raises(ImmutableRecordConflict) as exc_info:
        with sqlite_ledger_transaction(ledger_path) as repository:
            repository.commit_document_representation_bundle(candidate)
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.get_document_representation(candidate.representation.id) is None
        assert repository.get_document_node(candidate.nodes[0].id) is None
        assert repository.get_parse_quality_report(candidate.quality_report.id) is None
    assert exc_info.value.record_type == "TextView"


def test_representation_bundle_rejects_a_partial_preexisting_representation(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    initialize_ledger_with_representation_parent(ledger_path)
    candidate = bundle()

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_document_representation(candidate.representation)
    with pytest.raises(ImmutableRecordConflict, match="DocumentRepresentationBundle"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            repository.commit_document_representation_bundle(candidate)
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert (
            repository.get_document_representation(candidate.representation.id)
            == candidate.representation
        )
        assert repository.get_text_view(candidate.text_views[0].id) is None


def test_representation_ownership_foreign_keys_reject_orphan_records(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    candidate = bundle()

    with pytest.raises(sqlite3.IntegrityError):
        with sqlite_ledger_transaction(ledger_path) as repository:
            repository.save_document_representation(candidate.representation)

    initialize_ledger_with_representation_parent(ledger_path)
    with pytest.raises(sqlite3.IntegrityError):
        with sqlite_ledger_transaction(ledger_path) as repository:
            repository.save_text_view(candidate.text_views[0])
