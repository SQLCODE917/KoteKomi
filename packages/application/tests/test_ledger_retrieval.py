from datetime import UTC, datetime, timedelta

from kotekomi_application.ledger_retrieval import (
    LEDGER_AUDIT_HISTORY_POLICY_ID,
    LEDGER_CURRENT_LATEST_POLICY_ID,
    LEDGER_CURRENT_RELEVANCE_POLICY_ID,
    LedgerChannelCandidate,
    LedgerProjectionBuildInput,
    LedgerRetrievalFilters,
    LedgerRetrievalLedger,
    LedgerRetrievalProjectionPort,
    QueryLedgerRetrievalCommand,
    build_ledger_retrieval_units,
    query_ledger_retrieval,
)
from kotekomi_application.ports import AcceptedCanonicalRecord
from kotekomi_domain import (
    Actor,
    AnalysisUnitArtifact,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    ContextManifestArtifact,
    DocumentRepresentationBundle,
    Entity,
    EpistemicScope,
    Event,
    EvidenceTarget,
    LedgerRetrievalIndexManifest,
    LedgerRetrievalQueryRecord,
    LedgerRetrievalRecordType,
    Organization,
    Place,
    RetrievalChannel,
    SourceAuthority,
)

NOW = datetime(2026, 8, 23, tzinfo=UTC)


class FakeLedger(LedgerRetrievalLedger):
    def __init__(self) -> None:
        self.organization = Organization(id="org_anthropic", name="Anthropic")
        self.assertions = {
            "ast_current": _assertion("ast_current", AssertionStatus.REPORTED, NOW),
            "ast_old": _assertion("ast_old", AssertionStatus.SUPERSEDED, NOW - timedelta(days=1)),
        }

    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]:
        return (self.organization, *self.assertions.values())

    def get_assertion(self, record_id: str) -> Assertion | None:
        return self.assertions.get(record_id)

    def get_entity(self, record_id: str) -> Entity | None:
        return None

    def get_actor(self, record_id: str) -> Actor | None:
        return None

    def get_organization(self, record_id: str) -> Organization | None:
        return self.organization if record_id == self.organization.id else None

    def get_event(self, record_id: str) -> Event | None:
        return None

    def get_place(self, record_id: str) -> Place | None:
        return None

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return None

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return None

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        del record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        del record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return None

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        del manifest, child_analysis_units


class FakeProjection(LedgerRetrievalProjectionPort):
    def __init__(
        self, manifest: LedgerRetrievalIndexManifest, candidates: tuple[LedgerChannelCandidate, ...]
    ):
        self.manifest = manifest
        self.candidates = candidates
        self.record: LedgerRetrievalQueryRecord | None = None
        self.published = 0

    def publish(
        self, build: LedgerProjectionBuildInput
    ) -> tuple[LedgerRetrievalIndexManifest, bool]:
        reused = self.manifest == build.manifest
        self.manifest = build.manifest
        self.published += 1
        return self.manifest, reused

    def get_complete_manifest(self) -> LedgerRetrievalIndexManifest | None:
        return self.manifest

    def exact_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        normalized_query: str,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]:
        del manifest, normalized_query, filters
        return self.candidates

    def lexical_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        query_text: str,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]:
        del manifest, query_text, filters
        return ()

    def structured_candidates(
        self, manifest: LedgerRetrievalIndexManifest, filters: LedgerRetrievalFilters
    ) -> tuple[LedgerChannelCandidate, ...]:
        del manifest, filters
        return self.candidates

    def save_query_record(self, record: LedgerRetrievalQueryRecord) -> None:
        self.record = record


class NoopTokenizer:
    tokenizer_id = "test"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input)


def _assertion(assertion_id: str, status: AssertionStatus, updated_at: datetime) -> Assertion:
    return Assertion(
        id=assertion_id,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="received_contract",
        object_value="Directive 3000.09",
        status=status,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=("src_anthropic",),
        evidence_target_ids=("etg_contract",),
        provenance_activity_ids=("prv_review",),
        updated_at=updated_at,
    )


def _manifest(snapshot: str, count: int) -> LedgerRetrievalIndexManifest:
    return LedgerRetrievalIndexManifest(
        index_manifest_id="lrm_test",
        channels=(
            RetrievalChannel.EXACT,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.STRUCTURED_FILTER,
        ),
        source_snapshot_digest=snapshot,
        unit_policy_id="ledger_accepted_record_unit_v1",
        projection_policy_id="ledger_exact_lexical_projection_v1",
        query_policy_compatibility="ledger_current_relevance_v1",
        adapter_identity="fake",
        adapter_configuration_digest="a" * 64,
        unit_count=count,
        representation_count=count,
        content_fingerprint="b" * 64,
        publication_status="complete",
        published_at=NOW,
    )


def test_units_include_only_accepted_searchable_records() -> None:
    ledger = FakeLedger()

    units, snapshot = build_ledger_retrieval_units(ledger)

    assert snapshot
    assert {unit.source_record_id for unit in units} == {"ast_current", "ast_old"}
    assert all(unit.evidence_assertion_ids == (unit.source_record_id,) for unit in units)


def test_ledger_retrieval_rebuilds_a_stale_projection_before_query() -> None:
    ledger = FakeLedger()
    units, _ = build_ledger_retrieval_units(ledger)
    projection = FakeProjection(_manifest("f" * 64, len(units)), ())

    result = query_ledger_retrieval(
        QueryLedgerRetrievalCommand(query_text="Directive 3000.09"),
        ledger_repository=ledger,
        projection=projection,
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "complete"
    assert projection.published == 1
    assert result.index_manifest_id == projection.manifest.index_manifest_id


def test_current_policy_excludes_superseded_hits_before_evidence_resolution() -> None:
    ledger = FakeLedger()
    units, snapshot = build_ledger_retrieval_units(ledger)
    projection = FakeProjection(
        _manifest(snapshot, len(units)),
        (
            LedgerChannelCandidate(
                retrieval_unit_id=next(
                    unit.retrieval_unit_id for unit in units if unit.source_record_id == "ast_old"
                ),
                channel=RetrievalChannel.STRUCTURED_FILTER,
                channel_rank=1,
            ),
        ),
    )

    result = query_ledger_retrieval(
        QueryLedgerRetrievalCommand(
            filters=LedgerRetrievalFilters(record_type=LedgerRetrievalRecordType.ASSERTION),
            policy_id=LEDGER_CURRENT_RELEVANCE_POLICY_ID,
        ),
        ledger_repository=ledger,
        projection=projection,
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "complete"
    assert result.selected_record_ids == ()


def test_latest_policy_allows_an_empty_query() -> None:
    ledger = FakeLedger()
    units, snapshot = build_ledger_retrieval_units(ledger)
    projection = FakeProjection(_manifest(snapshot, len(units)), ())

    result = query_ledger_retrieval(
        QueryLedgerRetrievalCommand(policy_id=LEDGER_CURRENT_LATEST_POLICY_ID),
        ledger_repository=ledger,
        projection=projection,
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "complete"
    assert result.query_policy_id == LEDGER_CURRENT_LATEST_POLICY_ID
    assert projection.record is not None


def test_audit_policy_preserves_historical_records() -> None:
    ledger = FakeLedger()
    units, snapshot = build_ledger_retrieval_units(ledger)
    projection = FakeProjection(_manifest(snapshot, len(units)), ())

    result = query_ledger_retrieval(
        QueryLedgerRetrievalCommand(
            query_text="Directive 3000.09",
            policy_id=LEDGER_AUDIT_HISTORY_POLICY_ID,
        ),
        ledger_repository=ledger,
        projection=projection,
        tokenizer=NoopTokenizer(),
    )

    assert result.status == "complete"
