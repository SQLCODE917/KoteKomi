from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters.sqlite_ledger_retrieval import SQLiteLedgerRetrievalAdapter
from kotekomi_application.ledger_retrieval import LedgerProjectionBuildInput, LedgerRetrievalFilters
from kotekomi_domain import (
    AssertionStatus,
    LedgerExactLexicalRepresentation,
    LedgerRetrievalIndexManifest,
    LedgerRetrievalRecordType,
    LedgerRetrievalUnit,
    RetrievalChannel,
)


def _build() -> LedgerProjectionBuildInput:
    unit = LedgerRetrievalUnit(
        retrieval_unit_id="lru_contract",
        source_record_id="ast_contract",
        record_type=LedgerRetrievalRecordType.ASSERTION,
        evidence_assertion_ids=("ast_contract",),
        assertion_status=AssertionStatus.REPORTED,
        subject_id="org_anthropic",
        predicate="received_contract",
        updated_at=datetime(2026, 8, 23, tzinfo=UTC),
        source_snapshot_digest="a" * 64,
        source_order=0,
        unit_policy_id="ledger_accepted_record_unit_v1",
        unit_fingerprint="b" * 64,
    )
    representation = LedgerExactLexicalRepresentation(
        retrieval_representation_id="lrr_contract",
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_digest=unit.source_snapshot_digest,
        projection_policy_id="ledger_exact_lexical_projection_v1",
        projection_builder_version="dr5_ledger_projection_v1",
        exact_text="Anthropic received Directive 3000.09",
        lexical_text="Anthropic received Directive 3000.09",
        representation_fingerprint="c" * 64,
    )
    manifest = LedgerRetrievalIndexManifest(
        index_manifest_id="lrm_contract",
        channels=(
            RetrievalChannel.EXACT,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.STRUCTURED_FILTER,
        ),
        source_snapshot_digest=unit.source_snapshot_digest,
        unit_policy_id=unit.unit_policy_id,
        projection_policy_id=representation.projection_policy_id,
        query_policy_compatibility="ledger_current_relevance_v1",
        adapter_identity="sqlite_ledger_retrieval_v1",
        adapter_configuration_digest="d" * 64,
        unit_count=1,
        representation_count=1,
        content_fingerprint="e" * 64,
        publication_status="complete",
        published_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    return LedgerProjectionBuildInput(
        manifest=manifest,
        units=(unit,),
        representations=(representation,),
    )


def test_sqlite_ledger_retrieval_publishes_and_queries_derived_rows(tmp_path: Path) -> None:
    projection = SQLiteLedgerRetrievalAdapter(tmp_path / "ledger.retrieval.sqlite")
    build = _build()
    try:
        manifest, reused = projection.publish(build)
        exact = projection.exact_candidates(
            manifest,
            "directive 3000.09",
            LedgerRetrievalFilters(record_type=LedgerRetrievalRecordType.ASSERTION),
        )
        structured = projection.structured_candidates(
            manifest,
            LedgerRetrievalFilters(subject_id="org_anthropic"),
        )

        assert reused is False
        assert projection.get_complete_manifest() == manifest
        assert exact[0].retrieval_unit_id == "lru_contract"
        assert structured[0].channel is RetrievalChannel.STRUCTURED_FILTER
    finally:
        projection.close()


def test_sqlite_ledger_retrieval_reuses_the_same_complete_manifest(tmp_path: Path) -> None:
    projection = SQLiteLedgerRetrievalAdapter(tmp_path / "ledger.retrieval.sqlite")
    try:
        _, first_reused = projection.publish(_build())
        _, second_reused = projection.publish(_build())

        assert first_reused is False
        assert second_reused is True
    finally:
        projection.close()
