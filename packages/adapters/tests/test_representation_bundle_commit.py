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
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

from .domain_fixtures import sample_domain_records

NOW = datetime(2026, 7, 11, tzinfo=UTC)
INPUT_DIGEST = "a" * 64
CONFIG_DIGEST = "b" * 64


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
        text=text,
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
