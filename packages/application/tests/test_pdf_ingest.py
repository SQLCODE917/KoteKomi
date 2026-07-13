import hashlib
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from kotekomi_application import (
    BuildIdentity,
    BundleCommitDisposition,
    PdfDocumentParser,
    PdfExtractionPolicy,
    PdfIngestInput,
    PdfIngestLedger,
    PdfPagePreflight,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
    PdfProcessorIdentity,
    ProcessingTaskDisposition,
    ingest_pdf,
    processing_task_fingerprint,
)
from kotekomi_domain import (
    Document,
    PdfExtractionPath,
    PdfPageAccountingBundle,
    PdfPageQualityStatus,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingTaskFingerprint,
    ProvenanceActivity,
    RawBlob,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)
RAW_PDF = b"%PDF-1.7\nfixture"
BUILD_IDENTITY = BuildIdentity("fixture", "fixture", "a" * 64, "1")


def test_pdf_extraction_policy_emits_explicit_terminal_page_decisions() -> None:
    policy = PdfExtractionPolicy("pdf_policy_v1")
    page = PdfPagePreflight(1, 612, 792, 0, 120)

    acceptable = policy.select_page_outcome(
        page=page,
        page_has_output=True,
        representation_analyzability=None,
        source_blocked=False,
    )
    omitted = policy.select_page_outcome(
        page=page,
        page_has_output=False,
        representation_analyzability=None,
        source_blocked=False,
    )

    assert acceptable.extraction_path is PdfExtractionPath.EMBEDDED
    assert acceptable.status is PdfPageQualityStatus.ACCEPTABLE
    assert omitted.extraction_path is PdfExtractionPath.INACCESSIBLE
    assert omitted.status is PdfPageQualityStatus.BLOCKED
    assert omitted.reasons == ("parser_omitted_page_output",)

    low_rate = policy.select_page_outcome(
        page=PdfPagePreflight(1, 612, 792, 0, 120, suspicious_glyph_rate=0.009),
        page_has_output=True,
        representation_analyzability=None,
        source_blocked=False,
    )
    high_rate = policy.select_page_outcome(
        page=PdfPagePreflight(1, 612, 792, 0, 120, suspicious_glyph_rate=0.01),
        page_has_output=True,
        representation_analyzability=None,
        source_blocked=False,
    )
    recovered_high_rate = policy.select_page_outcome(
        page=PdfPagePreflight(1, 612, 792, 0, 120, suspicious_glyph_rate=0.01),
        page_has_output=True,
        representation_analyzability=None,
        source_blocked=False,
        selected_path=PdfExtractionPath.OCR,
        ocr_confidence=0.75,
    )
    assert low_rate.status is PdfPageQualityStatus.ACCEPTABLE
    assert high_rate.status is PdfPageQualityStatus.BLOCKED
    assert high_rate.reasons == ("selected_ocr_output_missing",)
    assert recovered_high_rate.extraction_path is PdfExtractionPath.OCR
    assert recovered_high_rate.status is PdfPageQualityStatus.DEGRADED


class SequenceAttemptIdFactory:
    def __init__(self) -> None:
        self.next_id = 1

    def new_attempt_id(self) -> str:
        attempt_id = f"pat_{self.next_id:024d}"
        self.next_id += 1
        return attempt_id


class FixedProcessingClock:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        return self._value


class FakePdfParser:
    def __init__(self) -> None:
        self.identity_calls = 0

    def processing_identity(self, _policy_id: str) -> PdfProcessorIdentity:
        self.identity_calls += 1
        return PdfProcessorIdentity("fake_pdf", "1", "b" * 64, "1")

    def parse(self, _parse_input: PdfParseInput) -> PdfParseResult:
        return PdfParseResult(
            preflight=PdfPreflight(
                parser_name="fake_pdf",
                parser_version="1",
                preflight_tool="fixture_preflight",
                preflight_tool_version="1",
                encrypted=False,
                page_count=0,
                pages=(),
            ),
            representation_bundle=None,
            blocking_reasons=("fixture parser blocked",),
        )


class FailingPdfParser(FakePdfParser):
    def parse(self, _parse_input: PdfParseInput) -> PdfParseResult:
        raise RuntimeError("fixture parser crash")


class FakePdfLedger:
    def __init__(self) -> None:
        self.document = Document(
            id="doc_pdf_fixture",
            source_id="src_pdf_fixture",
            content_sha256=hashlib.sha256(RAW_PDF).hexdigest(),
        )
        self.raw_blob = RawBlob(
            id="blb_pdf_fixture",
            hash_algorithm="sha256",
            digest=self.document.content_sha256,
            byte_length=len(RAW_PDF),
            media_type="application/pdf",
            storage_locator="sources/raw/blb_pdf_fixture.bin",
        )
        self.tasks: dict[str, ProcessingTaskFingerprint] = {}
        self.attempts: dict[str, ProcessingAttempt] = {}
        self.outcomes: dict[str, ProcessingAttemptOutcome] = {}
        self.page_accounting: PdfPageAccountingBundle | None = None
        self.provenance: dict[str, ProvenanceActivity] = {}

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_raw_blob(self, record_id: str) -> RawBlob | None:
        return self.raw_blob if record_id == self.raw_blob.id else None

    def ensure_processing_task_fingerprint(
        self, record: ProcessingTaskFingerprint
    ) -> ProcessingTaskDisposition:
        if record.id not in self.tasks:
            self.tasks[record.id] = record
            return ProcessingTaskDisposition.CREATED
        return ProcessingTaskDisposition.REUSED

    def append_processing_attempt(self, record: ProcessingAttempt) -> None:
        self.attempts[record.id] = record

    def append_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        self.outcomes[record.id] = record

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance[record.id] = record

    def commit_blocked_pdf_processing(
        self,
        *,
        expected_task_fingerprint_id: str,
        page_accounting: PdfPageAccountingBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitDisposition:
        assert page_accounting.preflight_report.processing_task_fingerprint_id == (
            expected_task_fingerprint_id
        )
        if self.page_accounting is None:
            self.page_accounting = page_accounting
            self.save_provenance_activity(created_provenance_activity)
            self.append_processing_attempt_outcome(created_outcome)
            return BundleCommitDisposition.CREATED
        assert self.page_accounting == page_accounting
        self.append_processing_attempt_outcome(reused_outcome)
        return BundleCommitDisposition.REUSED

    def commit_processing_attempt_start(self) -> None:
        return None

    def record_failed_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        self.append_processing_attempt_outcome(record)

    def get_processing_attempt_outcome(self, attempt_id: str) -> ProcessingAttemptOutcome | None:
        return next(
            (outcome for outcome in self.outcomes.values() if outcome.attempt_id == attempt_id),
            None,
        )

    def list_processing_attempts(
        self, fingerprint_id: str, *, after: str | None = None, limit: int = 100
    ) -> tuple[ProcessingAttempt, ...]:
        attempts = tuple(
            attempt
            for attempt in self.attempts.values()
            if attempt.task_fingerprint_id == fingerprint_id
        )
        if after is not None:
            attempts = tuple(attempt for attempt in attempts if attempt.id > after)
        return attempts[:limit]

    def list_open_processing_attempts(
        self, fingerprint_id: str, *, after: str | None = None, limit: int = 100
    ) -> tuple[ProcessingAttempt, ...]:
        attempts = tuple(
            attempt
            for attempt in self.attempts.values()
            if attempt.task_fingerprint_id == fingerprint_id
        )
        if after is not None:
            attempts = tuple(attempt for attempt in attempts if attempt.id > after)
        closed_attempt_ids = {outcome.attempt_id for outcome in self.outcomes.values()}
        return tuple(attempt for attempt in attempts if attempt.id not in closed_attempt_ids)[
            :limit
        ]


def test_ingest_pdf_returns_typed_blocked_outcome_without_publishing_representation() -> None:
    ledger = FakePdfLedger()
    outcome = ingest_pdf(
        PdfIngestInput(
            "doc_pdf_fixture", RAW_PDF, "pdf_policy_v1", NOW, "blb_pdf_fixture", BUILD_IDENTITY
        ),
        cast(PdfIngestLedger, ledger),
        cast(PdfDocumentParser, FakePdfParser()),
        SequenceAttemptIdFactory(),
    )

    assert outcome.representation_id is None
    assert outcome.provenance_activity_id is not None
    assert ledger.page_accounting is not None
    assert outcome.preflight_report_id == ledger.page_accounting.preflight_report.id
    assert ledger.page_accounting.preflight_report.page_count == 0
    assert outcome.blocking_reasons == ("fixture parser blocked",)


def test_ingest_pdf_rejects_bytes_that_do_not_match_the_immutable_document() -> None:
    with pytest.raises(ValueError, match="content_sha256"):
        ingest_pdf(
            PdfIngestInput(
                "doc_pdf_fixture", b"wrong", "pdf_policy_v1", NOW, "blb_pdf_fixture", BUILD_IDENTITY
            ),
            cast(PdfIngestLedger, FakePdfLedger()),
            cast(PdfDocumentParser, FakePdfParser()),
            SequenceAttemptIdFactory(),
        )


def test_ingest_pdf_rejects_invalid_build_identity_before_parser_work() -> None:
    parser = FakePdfParser()
    with pytest.raises(ValueError, match="artifact_digest"):
        ingest_pdf(
            PdfIngestInput(
                "doc_pdf_fixture",
                RAW_PDF,
                "pdf_policy_v1",
                NOW,
                "blb_pdf_fixture",
                BuildIdentity("fixture", "fixture", "not-a-digest", "1"),
            ),
            cast(PdfIngestLedger, FakePdfLedger()),
            cast(PdfDocumentParser, parser),
            SequenceAttemptIdFactory(),
        )

    assert parser.identity_calls == 0


def test_ingest_pdf_records_failure_and_reraises_processor_exception() -> None:
    ledger = FakePdfLedger()
    with pytest.raises(RuntimeError, match="fixture parser crash"):
        ingest_pdf(
            PdfIngestInput(
                "doc_pdf_fixture", RAW_PDF, "pdf_policy_v1", NOW, "blb_pdf_fixture", BUILD_IDENTITY
            ),
            cast(PdfIngestLedger, ledger),
            cast(PdfDocumentParser, FailingPdfParser()),
            SequenceAttemptIdFactory(),
        )

    assert len(ledger.attempts) == 1
    assert len(ledger.outcomes) == 1
    outcome = next(iter(ledger.outcomes.values()))
    assert outcome.status.value == "failed"
    assert outcome.failure is not None
    assert outcome.failure.code == "pdf_processor_failure"


def test_ingest_pdf_reconciles_unclosed_attempt_before_a_retry() -> None:
    ledger = FakePdfLedger()
    parser = FakePdfParser()
    task = processing_task_fingerprint(
        task_kind="pdf_document_representation",
        document_id=ledger.document.id,
        blob_id=ledger.raw_blob.id,
        input_digest=ledger.document.content_sha256,
        processor_name="fake_pdf",
        processor_version="1",
        processor_config_digest="b" * 64,
        build_identity=BUILD_IDENTITY,
        policy_id="pdf_policy_v1",
        output_contract_version="1",
    )
    prior_attempt = ProcessingAttempt(
        id="pat_interrupted_pdf_attempt",
        task_fingerprint_id=task.id,
        started_at=NOW,
        invocation_id="pdf:interrupted",
    )
    ledger.ensure_processing_task_fingerprint(task)
    ledger.append_processing_attempt(prior_attempt)
    clock = FixedProcessingClock(NOW + timedelta(minutes=5))

    ingest_pdf(
        PdfIngestInput(
            "doc_pdf_fixture", RAW_PDF, "pdf_policy_v1", NOW, "blb_pdf_fixture", BUILD_IDENTITY
        ),
        cast(PdfIngestLedger, ledger),
        cast(PdfDocumentParser, parser),
        SequenceAttemptIdFactory(),
        clock,
    )

    prior_outcome = ledger.get_processing_attempt_outcome(prior_attempt.id)
    retry_outcome = next(
        outcome for outcome in ledger.outcomes.values() if outcome.attempt_id != prior_attempt.id
    )
    assert prior_outcome is not None
    assert prior_outcome.status is ProcessingAttemptStatus.INTERRUPTED
    assert prior_outcome.finished_at == clock.now()
    assert retry_outcome.status is ProcessingAttemptStatus.BLOCKED
    assert retry_outcome.finished_at == clock.now()
