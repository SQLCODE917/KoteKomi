import hashlib
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import (
    SQLiteLedgerInitializer,
    SQLiteLedgerRepository,
    sqlite_ledger_transaction,
)
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import (
    BuildIdentity,
    BundleCommitOutcome,
    CaptureRequest,
    PdfIngestInput,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
    PdfProcessorIdentity,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    Uuid4ProcessingAttemptIdFactory,
    capture_source,
    deterministic_representation_id,
    ingest_pdf,
    processing_task_fingerprint,
)
from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentVersionKind,
    ParseQualityReport,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingStage,
    ProvenanceActivity,
    RepresentationAnalyzability,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
RAW_PDF = b"%PDF-1.7\nproduction-path fixture\n"
BUILD_IDENTITY = BuildIdentity("pdf-proof", "pdf-proof", "a" * 64, "1")
POLICY_ID = "pdf_proof_v1"


class FixturePdfParser:
    def __init__(
        self,
        *,
        analyzability: RepresentationAnalyzability = RepresentationAnalyzability.ACCEPTABLE,
        target_document_id: str | None = None,
    ) -> None:
        self._analyzability = analyzability
        self._target_document_id = target_document_id
        self.parse_calls = 0

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        del policy_id
        return PdfProcessorIdentity("fixture_pdf", "1", "b" * 64, "1")

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        self.parse_calls += 1
        bundle = _representation_bundle(
            parse_input,
            analyzability=self._analyzability,
            document_id=self._target_document_id or parse_input.document.id,
        )
        blocking_reasons = (
            ("fixture parser retained diagnostic text but blocked analysis",)
            if self._analyzability is RepresentationAnalyzability.BLOCKED
            else ()
        )
        return PdfParseResult(
            preflight=PdfPreflight(
                parser_name="fixture_pdf",
                parser_version="1",
                encrypted=False,
                page_count=1,
                pages=(),
            ),
            representation_bundle=bundle,
            blocking_reasons=blocking_reasons,
        )


class InterruptedFixturePdfParser(FixturePdfParser):
    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        del parse_input
        self.parse_calls += 1
        raise KeyboardInterrupt("simulated PDF process interruption")


class MismatchedFixturePdfParser(FixturePdfParser):
    def __init__(self, mismatch: str, returned_bundle: DocumentRepresentationBundle | None = None):
        super().__init__()
        self._mismatch = mismatch
        self._returned_bundle = returned_bundle

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        result = super().parse(parse_input)
        bundle = self._returned_bundle or result.representation_bundle
        assert bundle is not None
        representation = bundle.representation
        preflight = result.preflight
        if self._mismatch == "unchanged":
            pass
        elif self._mismatch == "representation_id":
            representation = representation.model_copy(update={"id": "rep_wrong_task"})
        elif self._mismatch == "task":
            representation = representation.model_copy(
                update={"processing_task_fingerprint_id": "ptf_wrong_task"}
            )
        elif self._mismatch == "input_digest":
            representation = representation.model_copy(update={"input_blob_digest": "f" * 64})
        elif self._mismatch == "parser_name":
            representation = representation.model_copy(update={"parser_name": "wrong_parser"})
        elif self._mismatch == "parser_version":
            representation = representation.model_copy(update={"parser_version": "wrong"})
        elif self._mismatch == "parser_config":
            representation = representation.model_copy(update={"parser_config_digest": "f" * 64})
        elif self._mismatch == "preflight_name":
            preflight = PdfPreflight(
                parser_name="wrong_parser",
                parser_version=preflight.parser_version,
                encrypted=preflight.encrypted,
                page_count=preflight.page_count,
                pages=preflight.pages,
                warnings=preflight.warnings,
            )
        elif self._mismatch == "preflight_version":
            preflight = PdfPreflight(
                parser_name=preflight.parser_name,
                parser_version="wrong",
                encrypted=preflight.encrypted,
                page_count=preflight.page_count,
                pages=preflight.pages,
                warnings=preflight.warnings,
            )
        else:
            raise AssertionError(f"Unexpected mismatch: {self._mismatch}")
        return PdfParseResult(
            preflight=preflight,
            representation_bundle=bundle.model_copy(update={"representation": representation}),
            blocking_reasons=result.blocking_reasons,
        )


class PersistenceFailingRepository(SQLiteLedgerRepository):
    def commit_document_representation_processing(
        self,
        *,
        expected_task_fingerprint_id: str,
        bundle: DocumentRepresentationBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitOutcome:
        del (
            expected_task_fingerprint_id,
            bundle,
            created_provenance_activity,
            created_outcome,
            reused_outcome,
        )
        raise RuntimeError("simulated PDF persistence failure")


@contextmanager
def persistence_failing_transaction(
    ledger_path: Path,
) -> Generator[PersistenceFailingRepository]:
    connection = sqlite3.connect(ledger_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("BEGIN")
        yield PersistenceFailingRepository(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _capture_request() -> CaptureRequest:
    digest = hashlib.sha256(RAW_PDF).hexdigest()
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title="PDF production-path fixture",
            stable_key="pdf-production-path-fixture",
            uri="file:///pdf-production-path-fixture.pdf",
        ),
        payload=RAW_PDF,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{digest}.bin",
        idempotency_key="pdf-production-path-v1",
        retrieval_method="fixture",
        requested_uri="file:///pdf-production-path-fixture.pdf",
        canonical_uri="file:///pdf-production-path-fixture.pdf",
        provider_item_id=None,
        provider_version=None,
        version_kind=DocumentVersionKind.ORIGINAL,
        publication_time=None,
        provider_update_time=None,
        captured_at=NOW,
        transaction_time=NOW,
        rights_profile_id=None,
        embargo_until=None,
        request_metadata={},
        response_metadata={},
    )


def _initialize_captured_pdf(ledger_path: Path) -> tuple[str, str]:
    SQLiteLedgerInitializer(ledger_path).initialize()
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(_capture_request(), repository, StableSourceIdentityPolicy())
    return capture.document.id, capture.raw_blob.id


def _ingest_input(
    document_id: str,
    raw_blob_id: str,
    build_identity: BuildIdentity = BUILD_IDENTITY,
) -> PdfIngestInput:
    return PdfIngestInput(
        document_id=document_id,
        raw_bytes=RAW_PDF,
        policy_id=POLICY_ID,
        ingested_at=NOW,
        raw_blob_id=raw_blob_id,
        build_identity=build_identity,
    )


def _only_processing_task_id(ledger_path: Path) -> str:
    with sqlite3.connect(ledger_path) as connection:
        rows = connection.execute("SELECT id FROM processing_task_fingerprints").fetchall()
    assert len(rows) == 1
    return str(rows[0][0])


def _representation_bundle(
    parse_input: PdfParseInput,
    *,
    analyzability: RepresentationAnalyzability,
    document_id: str,
) -> DocumentRepresentationBundle:
    representation_id = deterministic_representation_id(parse_input.processing_task_fingerprint_id)
    representation_key = representation_id.removeprefix("rep_")
    text = "PDF production-path text"
    text_view = TextView(
        id=f"tvw_{representation_key}_logical",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
        normalization_policy="fixture_pdf_v1",
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
        metric_values={"logical_text_char_count": len(text)},
        issues=("fixture_blocked",) if analyzability is RepresentationAnalyzability.BLOCKED else (),
        analyzability=analyzability,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document_id,
        parser_name="fixture_pdf",
        parser_version="1",
        parser_config_digest="b" * 64,
        processing_task_fingerprint_id=parse_input.processing_task_fingerprint_id,
        input_blob_digest=hashlib.sha256(parse_input.raw_bytes).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=parse_input.parsed_at,
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


def test_pdf_production_path_creates_then_reuses_after_restart(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)
    parser = FixturePdfParser()

    with sqlite_ledger_transaction(ledger_path) as repository:
        created = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
    task_id = _only_processing_task_id(ledger_path)

    with sqlite_ledger_transaction(ledger_path) as repository:
        reused = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert created.representation_id is not None
        assert reused.representation_id == created.representation_id
        assert created.provenance_activity_id is not None
        assert reused.provenance_activity_id is None
        assert repository.get_document_representation_bundle(created.representation_id) is not None
        attempts = repository.list_processing_attempts(task_id)
        outcomes = tuple(
            repository.get_processing_attempt_outcome(attempt.id) for attempt in attempts
        )

    assert parser.parse_calls == 2
    assert len(attempts) == 2
    assert all(outcome is not None for outcome in outcomes)
    assert {
        outcome.output_disposition.value
        for outcome in outcomes
        if outcome is not None and outcome.output_disposition is not None
    } == {
        "created",
        "reused",
    }


def test_pdf_retry_reconciles_a_process_interrupted_attempt(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(KeyboardInterrupt, match="process interruption"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                InterruptedFixturePdfParser(),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        recovered = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(),
            Uuid4ProcessingAttemptIdFactory(),
        )
        attempts = repository.list_processing_attempts(task_id)
        outcomes = tuple(
            repository.get_processing_attempt_outcome(attempt.id) for attempt in attempts
        )

    assert recovered.representation_id is not None
    assert len(attempts) == 2
    assert [outcome.status for outcome in outcomes if outcome is not None] == [
        ProcessingAttemptStatus.INTERRUPTED,
        ProcessingAttemptStatus.SUCCEEDED,
    ]


def test_pdf_production_path_persists_blocked_diagnostic_bundle(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with sqlite_ledger_transaction(ledger_path) as repository:
        outcome = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(analyzability=RepresentationAnalyzability.BLOCKED),
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert outcome.representation_id is not None
        assert outcome.provenance_activity_id is not None
        assert outcome.blocking_reasons == (
            "fixture parser retained diagnostic text but blocked analysis",
        )

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert outcome.representation_id is not None
        bundle = repository.get_document_representation_bundle(outcome.representation_id)
        assert bundle is not None
        assert bundle.quality_report.analyzability is RepresentationAnalyzability.BLOCKED
        attempts = repository.list_processing_attempts(
            bundle.representation.processing_task_fingerprint_id
        )
        attempt_outcome = repository.get_processing_attempt_outcome(attempts[0].id)

    assert attempt_outcome is not None
    assert attempt_outcome.status is ProcessingAttemptStatus.BLOCKED
    assert attempt_outcome.output_artifacts


def test_pdf_production_path_records_docling_source_access_as_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from docling import exceptions
    from kotekomi_adapters import docling_pdf_parser

    def raise_security_error() -> tuple[object, object, object, object, object]:
        raise exceptions.SecurityError("fixture source access blocked")

    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)
    monkeypatch.setattr(docling_pdf_parser, "_load_docling_components", raise_security_error)

    with sqlite_ledger_transaction(ledger_path) as repository:
        result = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
        )

    assert result.representation_id is None
    assert result.blocking_reasons == (
        "PDF source is inaccessible under the configured security policy.",
    )
    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()

    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.BLOCKED
    assert outcome.failure is None


def test_pdf_production_path_records_validation_failure_without_representation(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(ValueError, match="mismatched document ID"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                FixturePdfParser(target_document_id="doc_wrong_fixture"),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()
        assert repository.list_provenance_activities() == ()

    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.FAILED
    assert outcome.failure is not None
    assert outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION


@pytest.mark.parametrize(
    "mismatch",
    (
        "representation_id",
        "task",
        "input_digest",
        "parser_name",
        "parser_version",
        "parser_config",
        "preflight_name",
        "preflight_version",
    ),
)
def test_pdf_processing_rejects_every_parser_task_binding_disagreement(
    tmp_path: Path,
    mismatch: str,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(ValueError, match="mismatched"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                MismatchedFixturePdfParser(mismatch),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        attempt_outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()
        assert repository.list_provenance_activities() == ()

    assert attempt_outcome is not None
    assert attempt_outcome.status is ProcessingAttemptStatus.FAILED
    assert attempt_outcome.failure is not None
    assert attempt_outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION


def test_pdf_processing_rejects_task_a_output_for_changed_build_identity_task_b(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with sqlite_ledger_transaction(ledger_path) as repository:
        first = ingest_pdf(
            _ingest_input(document_id, raw_blob_id),
            repository,
            FixturePdfParser(),
            Uuid4ProcessingAttemptIdFactory(),
        )
        assert first.representation_id is not None
        first_bundle = repository.get_document_representation_bundle(first.representation_id)
        assert first.provenance_activity_id is not None
        first_provenance = repository.get_provenance_activity(first.provenance_activity_id)
        assert first_bundle is not None
        assert first_provenance is not None

    changed_build_identity = BuildIdentity(
        "pdf-proof",
        "changed-revision",
        "a" * 64,
        "1",
    )
    changed_task = processing_task_fingerprint(
        task_kind="pdf_document_representation",
        document_id=document_id,
        blob_id=raw_blob_id,
        input_digest=hashlib.sha256(RAW_PDF).hexdigest(),
        processor_name="fixture_pdf",
        processor_version="1",
        processor_config_digest="b" * 64,
        build_identity=changed_build_identity,
        policy_id=POLICY_ID,
        output_contract_version="1",
    )
    with pytest.raises(ValueError, match="mismatched representation ID"):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id, changed_build_identity),
                repository,
                MismatchedFixturePdfParser("unchanged", first_bundle),
                Uuid4ProcessingAttemptIdFactory(),
            )

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert first.representation_id is not None
        assert (
            repository.get_document_representation_bundle(first.representation_id) == first_bundle
        )
        assert repository.get_provenance_activity(first.provenance_activity_id) == first_provenance
        assert len(repository.list_document_representations()) == 1
        task_ids = {
            first_bundle.representation.processing_task_fingerprint_id,
            changed_task.id,
        }
        attempts = tuple(
            attempt
            for task_id in task_ids
            for attempt in repository.list_processing_attempts(task_id)
        )
        outcomes = tuple(
            repository.get_processing_attempt_outcome(attempt.id) for attempt in attempts
        )
        assert all(
            repository.get_processing_task_fingerprint(task_id) is not None for task_id in task_ids
        )

    assert len(task_ids) == 2
    assert len(attempts) == 2
    assert {outcome.status for outcome in outcomes if outcome is not None} == {
        ProcessingAttemptStatus.SUCCEEDED,
        ProcessingAttemptStatus.FAILED,
    }
    failed_outcome = next(
        outcome
        for outcome in outcomes
        if outcome is not None and outcome.status is ProcessingAttemptStatus.FAILED
    )
    assert failed_outcome.failure is not None
    assert failed_outcome.failure.stage is ProcessingStage.REPRESENTATION_VALIDATION


def test_pdf_production_path_records_persistence_failure_without_representation(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    document_id, raw_blob_id = _initialize_captured_pdf(ledger_path)

    with pytest.raises(RuntimeError, match="simulated PDF persistence failure"):
        with persistence_failing_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id),
                repository,
                FixturePdfParser(),
                Uuid4ProcessingAttemptIdFactory(),
            )

    task_id = _only_processing_task_id(ledger_path)
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempts[0].id)
        assert repository.list_document_representations() == ()
        assert repository.list_provenance_activities() == ()

    assert outcome is not None
    assert outcome.status is ProcessingAttemptStatus.FAILED
    assert outcome.failure is not None
    assert outcome.failure.stage is ProcessingStage.PERSISTENCE
