from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import (
    GenericArticleAdapter,
    LocalArchiveStore,
    NewsMLG2Adapter,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    BuildIdentity,
    EvidenceValidationInput,
    ExplicitNewsRightsPolicy,
    NewsAnalysisPlanningInput,
    NewsDeliveryEnvelope,
    NewsIngestInput,
    NewsIngestOutcome,
    NewsIngestStatus,
    Uuid4ProcessingAttemptIdFactory,
    authorize_news_representation_use,
    authorize_news_use,
    ingest_structured_news,
    plan_news_analysis_units,
    select_current_news_revision,
    validate_evidence_target,
)
from kotekomi_domain import (
    DocumentRepresentationBundle,
    DocumentVersionKind,
    EvidenceTarget,
    NewsFormatPrecedence,
    NewsUsePurpose,
    ProcessingAttemptStatus,
    ProcessingStage,
    RepresentationAnalyzability,
)

FIXTURES = Path(__file__).parent / "fixtures" / "news"
NOW = datetime(2026, 7, 14, 14, tzinfo=UTC)
BUILD = BuildIdentity(
    package_version="test",
    source_revision="news-test",
    artifact_digest="a" * 64,
    representation_policy_version="structured-news-v1",
)


class _Clock:
    def now(self) -> datetime:
        return NOW


def _delivery(
    payload: bytes, *, media_type: str = "application/newsml+xml"
) -> NewsDeliveryEnvelope:
    envelope_bytes = (FIXTURES / "envelope.json").read_bytes()
    return NewsDeliveryEnvelope(
        payload=payload,
        media_type=media_type,
        envelope_bytes=envelope_bytes,
        envelope_media_type="application/json",
        retrieval_method="recorded_fixture",
        requested_uri="fixture://news/item",
        canonical_uri=None,
        response_status=200,
        safe_metadata=json.loads(envelope_bytes),
    )


def _ingest(
    *,
    ledger_path: Path,
    archive: LocalArchiveStore,
    payload: bytes,
    idempotency_key: str,
) -> NewsIngestOutcome:
    with sqlite_ledger_transaction(ledger_path) as repository:
        return ingest_structured_news(
            NewsIngestInput(
                delivery=_delivery(payload),
                captured_at=NOW,
                transaction_time=NOW,
                idempotency_key=idempotency_key,
                build_identity=BUILD,
            ),
            repository,
            archive,
            NewsMLG2Adapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )


def _revision(payload: bytes, version: int, signal: str) -> bytes:
    value = payload.replace(b'version="1"', f'version="{version}"'.encode(), 1)
    value = value.replace(b"sig:newscontent", signal.encode(), 1)
    value = value.replace(
        b"Project Atlas entered public evaluation on Monday.",
        f"Project Atlas revision {version} entered the provider wire.".encode(),
    )
    return value


def test_newsml_ingest_revision_chain_restart_and_withdrawal(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    original = (FIXTURES / "newsml" / "original.xml").read_bytes()

    first = _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=original,
        idempotency_key="atlas-v1",
    )
    assert first.status is NewsIngestStatus.CREATED
    replay = _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=original,
        idempotency_key="atlas-v1",
    )
    assert replay.status is NewsIngestStatus.REUSED
    assert replay.representation_id == first.representation_id

    expected_kinds = (
        DocumentVersionKind.UPDATE,
        DocumentVersionKind.CORRECTION,
        DocumentVersionKind.CLARIFICATION,
        DocumentVersionKind.WITHDRAWAL,
    )
    payload = original
    for version, signal, expected_kind in zip(
        range(2, 6),
        ("sig:update", "sig:correction", "sig:clarification", "sig:kill"),
        expected_kinds,
        strict=True,
    ):
        payload = _revision(original, version, signal)
        outcome = _ingest(
            ledger_path=ledger_path,
            archive=archive,
            payload=payload,
            idempotency_key=f"atlas-v{version}",
        )
        assert outcome.status is (
            NewsIngestStatus.BLOCKED
            if expected_kind is DocumentVersionKind.WITHDRAWAL
            else NewsIngestStatus.CREATED
        )

    with sqlite_ledger_transaction(ledger_path) as repository:
        sources = repository.list_sources()
        documents = repository.list_documents()
        revisions = repository.list_news_revisions_for_source(sources[0].id)
        bundle = repository.get_document_representation_bundle(first.representation_id or "")
        metadata = repository.get_news_representation_metadata(first.representation_id or "")
        public_profile = repository.get_news_rights_profile(
            metadata.rights_profile_id if metadata else ""
        )
        task_ids = {
            representation.processing_task_fingerprint_id
            for representation in repository.list_document_representations()
        }
        attempts = tuple(
            attempt
            for task_id in task_ids
            for attempt in repository.list_processing_attempts(task_id)
        )
        outcomes = tuple(repository.get_processing_attempt_outcome(item.id) for item in attempts)
    assert len(sources) == 1
    assert sources[0].provider_namespace == "kotekomi-test-wire"
    assert len(documents) == 5
    assert tuple(item.generic_kind for item in revisions) == (
        DocumentVersionKind.ORIGINAL,
        *expected_kinds,
    )
    assert select_current_news_revision(revisions) is None
    assert bundle is not None
    assert metadata is not None
    assert bundle.text_views[0].text.count("Project Atlas") >= 2
    assert len(bundle.source_selectors) == len(bundle.nodes) - 1
    assert metadata.format_precedence is NewsFormatPrecedence.NEWSML_G2
    assert public_profile is not None
    assert NewsUsePurpose.PUBLIC_FIXTURE in public_profile.allowed_purposes
    assert len(attempts) == 6
    assert all(item is not None for item in outcomes)
    assert (
        sum(
            item is not None and item.status is ProcessingAttemptStatus.BLOCKED for item in outcomes
        )
        == 1
    )
    corrupted_payload = bundle.model_dump()
    corrupted_payload["source_selectors"][0]["element_digest"] = "0" * 64
    with pytest.raises(ValueError, match="DocumentSourceSelector digest"):
        DocumentRepresentationBundle.model_validate(corrupted_payload)

    with sqlite_ledger_transaction(ledger_path) as repository:
        restarted = repository.get_document_representation_bundle(first.representation_id or "")
        restarted_revisions = repository.list_news_revisions_for_source(sources[0].id)
    assert restarted == bundle
    assert restarted_revisions == revisions


def test_generic_jsonld_is_explicitly_weaker_and_rights_are_operational(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    payload = (FIXTURES / "html" / "jsonld.html").read_bytes()
    delivery = _delivery(payload, media_type="text/html")
    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_structured_news(
            NewsIngestInput(delivery, NOW, NOW, "generic-v1", BUILD),
            repository,
            archive,
            GenericArticleAdapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        metadata = repository.get_news_representation_metadata(outcome.representation_id or "")
        profile = repository.get_news_rights_profile(outcome.rights_profile_id or "")
        bundle = repository.get_document_representation_bundle(outcome.representation_id or "")
        assert bundle is not None
        paragraph = next(node for node in bundle.nodes if node.node_type == "paragraph")
        selector = next(item for item in bundle.source_selectors if item.node_id == paragraph.id)
        view = bundle.text_views[0]
        target = EvidenceTarget(
            id="etg_generic_article_paragraph",
            source_id=outcome.source_id or "",
            document_id=outcome.document_id or "",
            representation_id=bundle.representation.id,
            text_view_id=view.id,
            text_view_digest=view.content_digest,
            start_char=paragraph.start_char,
            end_char=paragraph.end_char,
            exact_text=view.text[paragraph.start_char : paragraph.end_char],
            normalization_policy=view.normalization_policy,
            prefix_text=view.text[max(0, paragraph.start_char - 16) : paragraph.start_char],
            suffix_text=view.text[paragraph.end_char : paragraph.end_char + 16],
            node_ids=(paragraph.id,),
            dom_selector={"selector_id": selector.id, "path": list(selector.path)},
            created_at=NOW,
        )
        repository.save_evidence_target(target)
        validation = validate_evidence_target(
            EvidenceValidationInput(target.id, "eva_generic_article", "news-v1", NOW),
            repository,
        )
    assert outcome.status is NewsIngestStatus.CREATED
    assert metadata is not None
    assert metadata.format_precedence is NewsFormatPrecedence.NEWSARTICLE_JSON_LD
    assert profile is not None
    assert validation.valid
    assert authorize_news_use(profile, NewsUsePurpose.MODEL_CONTEXT, as_of=NOW).allowed
    assert NewsUsePurpose.PUBLIC_FIXTURE not in profile.allowed_purposes

    embargoed = profile.model_copy(
        update={
            "id": "nrp_embargoed",
            "embargo_until": datetime(2026, 7, 15, tzinfo=UTC),
        }
    )
    decision = ExplicitNewsRightsPolicy().authorize(embargoed, NewsUsePurpose.EXPORT, as_of=NOW)
    assert not decision.allowed
    assert decision.reason == "embargo_active"


@pytest.mark.parametrize(
    ("status", "expected_status", "code"),
    [
        (401, NewsIngestStatus.BLOCKED, "provider_entitlement"),
        (429, NewsIngestStatus.BLOCKED, "provider_rate_limit"),
        (503, NewsIngestStatus.FAILED, "provider_server_error"),
    ],
)
def test_provider_delivery_failure_creates_no_authoritative_records(
    tmp_path: Path,
    status: int,
    expected_status: NewsIngestStatus,
    code: str,
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    delivery = _delivery((FIXTURES / "newsml" / "original.xml").read_bytes())
    delivery = replace(delivery, response_status=status)
    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_structured_news(
            NewsIngestInput(delivery, NOW, NOW, f"failure-{status}", BUILD),
            repository,
            archive,
            NewsMLG2Adapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        assert repository.list_sources() == ()
        assert repository.list_documents() == ()
        assert repository.list_raw_blobs() == ()
    assert outcome.status is expected_status
    assert outcome.blocking_code == code or outcome.failure_code == code


@pytest.mark.parametrize(
    ("fixture_name", "expected_precedence", "expected_analyzability"),
    [
        (
            "semantic.html",
            NewsFormatPrecedence.SEMANTIC_HTML,
            RepresentationAnalyzability.ACCEPTABLE,
        ),
        (
            "main-text.html",
            NewsFormatPrecedence.MAIN_TEXT_FALLBACK,
            RepresentationAnalyzability.DEGRADED,
        ),
    ],
)
def test_generic_html_precedence_is_explicit(
    tmp_path: Path,
    fixture_name: str,
    expected_precedence: NewsFormatPrecedence,
    expected_analyzability: RepresentationAnalyzability,
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    delivery = _delivery((FIXTURES / "html" / fixture_name).read_bytes(), media_type="text/html")
    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_structured_news(
            NewsIngestInput(delivery, NOW, NOW, fixture_name, BUILD),
            repository,
            archive,
            GenericArticleAdapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        metadata = repository.get_news_representation_metadata(outcome.representation_id or "")
        bundle = repository.get_document_representation_bundle(outcome.representation_id or "")
    assert outcome.status is NewsIngestStatus.CREATED
    assert metadata is not None and metadata.format_precedence is expected_precedence
    assert bundle is not None and bundle.quality_report.analyzability is expected_analyzability


def test_archive_restriction_blocks_before_mutation_and_embargo_blocks_downstream_use(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    original = (FIXTURES / "newsml" / "original.xml").read_bytes()
    no_archive = original.replace(b"sig:newscontent", b"sig:noarchive")
    with sqlite_ledger_transaction(ledger_path) as repository:
        blocked = ingest_structured_news(
            NewsIngestInput(_delivery(no_archive), NOW, NOW, "no-archive", BUILD),
            repository,
            archive,
            NewsMLG2Adapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        assert repository.list_sources() == ()
        assert repository.list_raw_blobs() == ()
    assert blocked.status is NewsIngestStatus.BLOCKED
    assert blocked.blocking_code == "news_archive_not_permitted"

    embargoed = original.replace(
        b"<firstCreated>2026-07-14T12:00:00Z</firstCreated>",
        b"<firstCreated>2026-07-14T12:00:00Z</firstCreated>"
        b"<embargoed>2026-07-15T12:00:00Z</embargoed>",
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        captured = ingest_structured_news(
            NewsIngestInput(_delivery(embargoed), NOW, NOW, "embargoed", BUILD),
            repository,
            archive,
            NewsMLG2Adapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        authorization = authorize_news_representation_use(
            captured.representation_id or "",
            NewsUsePurpose.MODEL_CONTEXT,
            as_of=NOW,
            ledger=repository,
        )
        planning = plan_news_analysis_units(
            NewsAnalysisPlanningInput(
                representation_id=captured.representation_id or "",
                policy_id="embargoed-news-plan-v1",
                task_type="claim_extraction",
                as_of=NOW,
            ),
            repository,
        )
        profile = repository.get_news_rights_profile(captured.rights_profile_id or "")
    assert captured.status is NewsIngestStatus.CREATED
    assert not authorization.allowed and authorization.reason == "embargo_active"
    assert not planning.authorization.allowed and planning.plan is None
    assert profile is not None
    assert profile.provider_signals == ("sig:newscontent", "sig:public-fixture")
    assert profile.archive_permitted
    assert NewsUsePurpose.PUBLIC_FIXTURE not in profile.allowed_purposes


def test_same_provider_version_with_changed_bytes_fails_without_new_records(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    original = (FIXTURES / "newsml" / "original.xml").read_bytes()
    first = _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=original,
        idempotency_key="original",
    )
    conflict_payload = original.replace(b"monthly safety summaries", b"weekly safety summaries")
    conflict = _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=conflict_payload,
        idempotency_key="conflict",
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert len(repository.list_documents()) == 1
        assert len(repository.list_document_representations()) == 1
    assert first.status is NewsIngestStatus.CREATED
    assert conflict.status is NewsIngestStatus.FAILED
    assert conflict.failure_code == "provider_identity_version_conflict"


def test_provider_version_regression_fails_without_branching_revision_history(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    original = (FIXTURES / "newsml" / "original.xml").read_bytes()
    _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=original,
        idempotency_key="version-1",
    )
    _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=_revision(original, 3, "sig:update"),
        idempotency_key="version-3",
    )
    regressed = _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=_revision(original, 2, "sig:update"),
        idempotency_key="version-2-late",
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        source = repository.list_sources()[0]
        revisions = repository.list_news_revisions_for_source(source.id)
    assert regressed.status is NewsIngestStatus.FAILED
    assert regressed.failure_code == "provider_revision_invalid"
    assert tuple(revision.provider_version for revision in revisions) == ("1", "3")


def test_malformed_and_entity_expanding_newsml_fail_before_mutation(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    payloads = (
        b"<newsItem>",
        b'<!DOCTYPE newsItem [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
        b'<newsItem guid="&secret;" version="1"/>',
    )
    for index, payload in enumerate(payloads):
        outcome = _ingest(
            ledger_path=ledger_path,
            archive=archive,
            payload=payload,
            idempotency_key=f"malformed-{index}",
        )
        assert outcome.status is NewsIngestStatus.FAILED
        assert outcome.failure_code == "provider_payload_invalid"
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.list_sources() == ()
        assert repository.list_raw_blobs() == ()


def test_delivery_envelope_rejects_nested_secret_metadata() -> None:
    payload = (FIXTURES / "newsml" / "original.xml").read_bytes()
    with pytest.raises(ValueError, match="must not contain secrets"):
        replace(
            _delivery(payload),
            safe_metadata={"response": {"headers": {"Authorization": "secret"}}},
        )


class _ParseFailureAdapter(NewsMLG2Adapter):
    def parse(self, delivery: NewsDeliveryEnvelope):  # type: ignore[no-untyped-def]
        del delivery
        raise RuntimeError("fixture parser failure")


def test_parser_failure_is_terminal_and_not_mislabeled(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    payload = (FIXTURES / "newsml" / "original.xml").read_bytes()
    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_structured_news(
            NewsIngestInput(_delivery(payload), NOW, NOW, "parse-failure", BUILD),
            repository,
            archive,
            _ParseFailureAdapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        attempt_outcome = repository.get_processing_attempt_outcome(
            outcome.processing_attempt_id or ""
        )
        assert repository.list_document_representations() == ()
    assert outcome.status is NewsIngestStatus.FAILED
    assert outcome.failure_code == "structured_news_parser_failure"
    assert attempt_outcome is not None
    assert attempt_outcome.status is ProcessingAttemptStatus.FAILED
    assert attempt_outcome.failure is not None
    assert attempt_outcome.failure.stage is ProcessingStage.PARSER


def test_news_bundle_commit_rolls_back_and_records_persistence_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    payload = (FIXTURES / "newsml" / "original.xml").read_bytes()
    with sqlite_ledger_transaction(ledger_path) as repository:

        def fail_metadata(_record: object) -> None:
            raise RuntimeError("fixture metadata commit failure")

        monkeypatch.setattr(repository, "save_news_representation_metadata", fail_metadata)
        outcome = ingest_structured_news(
            NewsIngestInput(_delivery(payload), NOW, NOW, "commit-failure", BUILD),
            repository,
            archive,
            NewsMLG2Adapter(),
            Uuid4ProcessingAttemptIdFactory(),
            _Clock(),
        )
        attempt_outcome = repository.get_processing_attempt_outcome(
            outcome.processing_attempt_id or ""
        )
        assert repository.list_document_representations() == ()
        assert repository.list_document_nodes() == ()
    assert outcome.status is NewsIngestStatus.FAILED
    assert outcome.failure_code == "structured_news_persistence_failure"
    assert attempt_outcome is not None and attempt_outcome.failure is not None
    assert attempt_outcome.failure.stage is ProcessingStage.PERSISTENCE
    with sqlite_ledger_transaction(ledger_path) as restarted_repository:
        restarted_outcome = restarted_repository.get_processing_attempt_outcome(
            outcome.processing_attempt_id or ""
        )
        assert restarted_repository.list_document_representations() == ()
    assert restarted_outcome == attempt_outcome
    retried = _ingest(
        ledger_path=ledger_path,
        archive=archive,
        payload=payload,
        idempotency_key="commit-retry",
    )
    assert retried.status is NewsIngestStatus.CREATED
    with sqlite_ledger_transaction(ledger_path) as retried_repository:
        assert len(retried_repository.list_document_representations()) == 1
        assert (
            retried_repository.get_processing_attempt_outcome(outcome.processing_attempt_id or "")
            == attempt_outcome
        )


def test_public_gold_matrix_declares_every_required_outcome() -> None:
    matrix = json.loads((FIXTURES / "gold_matrix.json").read_text())
    assert {row["id"] for row in matrix["rows"]} == {
        "newsml_original",
        "idempotent_reuse",
        "newsml_update",
        "newsml_correction",
        "newsml_clarification",
        "newsml_withdrawal",
        "jsonld_article",
        "semantic_html_article",
        "main_text_fallback",
        "archive_rights_blocked",
        "embargo_export_blocked",
        "same_version_identity_conflict",
        "malformed_payload",
        "expired_credentials",
        "rate_limit",
        "provider_server_error",
        "parser_failure",
        "persistence_failure",
    }
