"""Public PDF ingestion proofs for inaccessible, damaged, and interrupted sources."""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from kotekomi_adapters import (
    LocalArchiveStore,
    SQLiteLedgerInitializer,
    docling_pdf_parser,
    sqlite_ledger_transaction,
)
from kotekomi_adapters.docling_pdf_parser import DoclingPdfParser, DoclingPdfParserConfig
from kotekomi_application import (
    BuildIdentity,
    CaptureRequest,
    PdfAccessCredential,
    PdfIngestInput,
    PdfParseInput,
    PdfParseResult,
    PdfProcessingError,
    PdfProcessorIdentity,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    Uuid4ProcessingAttemptIdFactory,
    capture_identity,
    capture_source,
    ingest_pdf,
)
from kotekomi_domain import (
    DocumentVersionKind,
    OutputDisposition,
    PdfTransformationType,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    RepresentationAnalyzability,
    SourceType,
)

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
BUILD_IDENTITY = BuildIdentity("pdf-failure-proof", "pdf-failure-proof", "7" * 64, "1")
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pdf"


class _FixedClock:
    def now(self) -> datetime:
        return NOW + timedelta(days=1)


def _capture_request(raw_pdf: bytes, fixture_key: str) -> CaptureRequest:
    digest = hashlib.sha256(raw_pdf).hexdigest()
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.PDF,
            title=f"PDF failure fixture {fixture_key}",
            stable_key=f"pdf-failure-{fixture_key}",
            uri=f"file:///pdf-failure-{fixture_key}.pdf",
        ),
        payload=raw_pdf,
        media_type="application/pdf",
        storage_locator=f"sources/raw/blb_{digest}.bin",
        idempotency_key=f"pdf-failure-{fixture_key}-v1",
        retrieval_method="fixture",
        requested_uri=f"file:///pdf-failure-{fixture_key}.pdf",
        canonical_uri=f"file:///pdf-failure-{fixture_key}.pdf",
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


def _capture_pdf(
    tmp_path: Path,
    raw_pdf: bytes,
    fixture_key: str,
) -> tuple[Path, LocalArchiveStore, str, str]:
    ledger_path = tmp_path / f"{fixture_key}.db"
    archive = LocalArchiveStore(tmp_path / f"{fixture_key}-archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _capture_request(raw_pdf, fixture_key)
    policy = StableSourceIdentityPolicy()
    identity = capture_identity(request, policy)
    archive.put_if_absent_or_identical(
        identity.raw_blob_id,
        raw_pdf,
        hashlib.sha256(raw_pdf).hexdigest(),
    )
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, policy)
    return ledger_path, archive, capture.document.id, capture.raw_blob.id


def _ingest_input(
    document_id: str,
    raw_blob_id: str,
    raw_pdf: bytes,
    credential: PdfAccessCredential | None = None,
) -> PdfIngestInput:
    return PdfIngestInput(
        document_id=document_id,
        raw_bytes=raw_pdf,
        policy_id="pdf_failure_matrix_v1",
        ingested_at=NOW,
        raw_blob_id=raw_blob_id,
        build_identity=BUILD_IDENTITY,
        access_credential=credential,
    )


def _only_attempt_outcome(ledger_path: Path) -> ProcessingAttemptOutcome:
    with sqlite3.connect(ledger_path) as connection:
        row = connection.execute("SELECT id FROM processing_task_fingerprints").fetchone()
    assert row is not None
    task_id = str(row[0])
    with sqlite_ledger_transaction(ledger_path) as repository:
        (attempt,) = repository.list_processing_attempts(task_id)
        outcome = repository.get_processing_attempt_outcome(attempt.id)
    assert outcome is not None
    return outcome


def _all_attempt_outcomes(ledger_path: Path) -> tuple[ProcessingAttemptOutcome, ...]:
    with sqlite3.connect(ledger_path) as connection:
        (task_id,) = connection.execute("SELECT id FROM processing_task_fingerprints").fetchone()
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = repository.list_processing_attempts(str(task_id))
        outcomes = tuple(repository.get_processing_attempt_outcome(item.id) for item in attempts)
    assert all(outcome is not None for outcome in outcomes)
    return tuple(outcome for outcome in outcomes if outcome is not None)


class _DirectDoclingParser:
    def __init__(
        self,
        config: DoclingPdfParserConfig,
        identity: PdfProcessorIdentity,
        *,
        worker: bool,
    ) -> None:
        self._config = config
        self._identity = identity
        self._worker = worker

    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity:
        del policy_id
        return self._identity

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult:
        if self._worker:
            return docling_pdf_parser._parse_with_large_stack_worker(parse_input, self._config)
        return DoclingPdfParser(self._config)._parse_in_process(parse_input)


CORRUPT_FIXTURES = (
    "corrupt/generated/corrupt_truncated_v1.pdf",
    "corrupt/generated/corrupt_bad_xref_v1.pdf",
    "corrupt/generated/corrupt_bad_stream_length_v1.pdf",
    "corrupt/generated/corrupt_missing_page_tree_v1.pdf",
    "corrupt/ocrmypdf-invalid.pdf",
    "corrupt/ocrmypdf-kcs-invalid-toc.pdf",
    "corrupt/ocrmypdf-overlay-content-stream-errors.pdf",
    "corrupt/pdfjs-ghostscript-698804-1-fuzzed.pdf",
    "corrupt/pdfjs-pdfbox-3148-2-fuzzed.pdf",
)


@pytest.mark.parametrize(
    ("credential", "expected_reason"),
    (
        (None, "password_required"),
        (PdfAccessCredential("fixture-password-wrong-v1", "wrong"), "invalid_password"),
    ),
)
def test_public_ingestion_blocks_encrypted_pdf_without_valid_credentials(
    tmp_path: Path,
    credential: PdfAccessCredential | None,
    expected_reason: str,
) -> None:
    raw_pdf = (FIXTURE_ROOT / "encrypted" / "encrypted_aes256_v1.pdf").read_bytes()
    ledger_path, archive, document_id, raw_blob_id = _capture_pdf(
        tmp_path, raw_pdf, expected_reason
    )

    with sqlite_ledger_transaction(ledger_path) as repository:
        result = ingest_pdf(
            _ingest_input(document_id, raw_blob_id, raw_pdf, credential),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
            clock=_FixedClock(),
            transformation_archive=archive,
        )
        assert repository.list_document_representations() == ()

    assert result.representation_id is None
    assert result.blocking_reasons == (expected_reason,)
    assert archive.read_raw_source(raw_blob_id) == raw_pdf
    outcome = _only_attempt_outcome(ledger_path)
    assert outcome.status is ProcessingAttemptStatus.BLOCKED
    assert outcome.failure is None
    assert all("test" not in blocker.safe_message for blocker in outcome.blocking_reasons)


def test_public_ingestion_decrypts_with_correct_credential_as_versioned_transformation(
    tmp_path: Path,
) -> None:
    raw_pdf = (FIXTURE_ROOT / "encrypted" / "encrypted_aes256_v1.pdf").read_bytes()
    ledger_path, archive, document_id, raw_blob_id = _capture_pdf(
        tmp_path, raw_pdf, "correct-password"
    )
    credential = PdfAccessCredential("fixture-password-test-v1", "test")

    with sqlite_ledger_transaction(ledger_path) as repository:
        result = ingest_pdf(
            _ingest_input(document_id, raw_blob_id, raw_pdf, credential),
            repository,
            DoclingPdfParser(DoclingPdfParserConfig()),
            Uuid4ProcessingAttemptIdFactory(),
            clock=_FixedClock(),
            transformation_archive=archive,
        )
        assert result.representation_id is not None
        accounting = repository.get_pdf_page_accounting_bundle(result.preflight_report_id)

    assert accounting is not None
    assert accounting.preflight_report.encrypted is True
    transformation = next(
        artifact
        for artifact in accounting.transformation_artifacts
        if artifact.activity_type is PdfTransformationType.REPAIR
    )
    assert transformation.activity_type is PdfTransformationType.REPAIR
    decrypted = archive.read_pdf_transformation_blob(transformation.output_blob_id)
    assert hashlib.sha256(decrypted).hexdigest() == next(
        blob.digest
        for blob in accounting.transformation_blobs
        if blob.id == transformation.output_blob_id
    )
    decrypted_path = tmp_path / "decrypted.pdf"
    decrypted_path.write_bytes(decrypted)
    encryption = subprocess.run(
        ("qpdf", "--show-encryption", decrypted_path),
        capture_output=True,
        check=True,
    )
    assert b"File is not encrypted" in encryption.stdout
    assert archive.read_raw_source(raw_blob_id) == raw_pdf
    assert b"fixture-password-test-v1" not in ledger_path.read_bytes()
    assert b"test" not in ledger_path.read_bytes()


@pytest.mark.parametrize("relative_path", CORRUPT_FIXTURES)
def test_public_ingestion_fails_closed_or_records_versioned_repair_for_corrupt_pdf(
    tmp_path: Path,
    relative_path: str,
) -> None:
    raw_pdf = (FIXTURE_ROOT / relative_path).read_bytes()
    fixture_key = Path(relative_path).stem
    ledger_path, archive, document_id, raw_blob_id = _capture_pdf(tmp_path, raw_pdf, fixture_key)
    result = None
    try:
        with sqlite_ledger_transaction(ledger_path) as repository:
            result = ingest_pdf(
                _ingest_input(document_id, raw_blob_id, raw_pdf),
                repository,
                DoclingPdfParser(DoclingPdfParserConfig(worker_timeout_seconds=10)),
                Uuid4ProcessingAttemptIdFactory(),
                clock=_FixedClock(),
                transformation_archive=archive,
            )
    except Exception:
        pass

    assert archive.read_raw_source(raw_blob_id) == raw_pdf
    outcome = _only_attempt_outcome(ledger_path)
    assert outcome.status in {
        ProcessingAttemptStatus.SUCCEEDED,
        ProcessingAttemptStatus.BLOCKED,
        ProcessingAttemptStatus.FAILED,
    }
    with sqlite_ledger_transaction(ledger_path) as repository:
        representations = repository.list_document_representations()
        if outcome.status is ProcessingAttemptStatus.FAILED:
            assert outcome.failure is not None
            assert outcome.failure.code.startswith("pdf_")
            assert outcome.failure.safe_message
            assert representations == ()
        elif outcome.status is ProcessingAttemptStatus.BLOCKED:
            assert outcome.failure is None
            assert outcome.blocking_reasons
            assert representations == ()
        else:
            assert result is not None and result.representation_id is not None
            bundle = repository.get_document_representation_bundle(result.representation_id)
            accounting = repository.get_pdf_page_accounting_bundle(result.preflight_report_id)
            assert bundle is not None and accounting is not None
            assert bundle.quality_report.analyzability is RepresentationAnalyzability.DEGRADED
            assert any(
                artifact.activity_type is PdfTransformationType.REPAIR
                for artifact in accounting.transformation_artifacts
            )


@pytest.mark.parametrize(
    ("fault", "expected_code"),
    (
        ("subprocess", "pdf_parser_subprocess_failure"),
        ("forced", "pdf_parser_forced_termination"),
        ("timeout", "pdf_parser_timeout"),
    ),
)
def test_public_ingestion_records_worker_failure_and_clean_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    expected_code: str,
) -> None:
    raw_pdf = (
        FIXTURE_ROOT / "2025-community-health-improvement-plan-press-release.pdf"
    ).read_bytes()
    ledger_path, archive, document_id, raw_blob_id = _capture_pdf(tmp_path, raw_pdf, fault)
    config = DoclingPdfParserConfig(worker_timeout_seconds=10)
    identity = DoclingPdfParser(config).processing_identity("pdf_failure_matrix_v1")
    parser = _DirectDoclingParser(config, identity, worker=True)
    real_run = subprocess.run

    def faulting_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command = cast(str | bytes | tuple[str, ...], args[0])
        if fault == "timeout":
            raise subprocess.TimeoutExpired(command, cast(float, kwargs["timeout"]))
        return subprocess.CompletedProcess(
            args=command,
            returncode=-9 if fault == "forced" else 1,
            stdout=b"",
            stderr=b"credential-safe diagnostic intentionally discarded",
        )

    monkeypatch.setattr(subprocess, "run", faulting_run)
    with pytest.raises(PdfProcessingError):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id, raw_pdf),
                repository,
                parser,
                Uuid4ProcessingAttemptIdFactory(),
                clock=_FixedClock(),
                transformation_archive=archive,
            )

    monkeypatch.setattr(subprocess, "run", real_run)
    first_outcome = _only_attempt_outcome(ledger_path)
    assert first_outcome.status is ProcessingAttemptStatus.FAILED
    assert first_outcome.failure is not None
    assert first_outcome.failure.code == expected_code
    assert first_outcome.failure.retryable is True
    assert "credential-safe diagnostic" not in first_outcome.failure.safe_message
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.list_document_representations() == ()

    with sqlite_ledger_transaction(ledger_path) as repository:
        recovered = ingest_pdf(
            _ingest_input(document_id, raw_blob_id, raw_pdf),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
            clock=_FixedClock(),
            transformation_archive=archive,
        )
    assert recovered.representation_id is not None
    outcomes = _all_attempt_outcomes(ledger_path)
    assert {outcome.status for outcome in outcomes} == {
        ProcessingAttemptStatus.FAILED,
        ProcessingAttemptStatus.SUCCEEDED,
    }
    assert first_outcome in outcomes
    assert archive.read_raw_source(raw_blob_id) == raw_pdf


def test_public_ingestion_records_ocr_failure_and_clean_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_pdf = (FIXTURE_ROOT / "ocr" / "ocrmypdf-linn.pdf").read_bytes()
    ledger_path, archive, document_id, raw_blob_id = _capture_pdf(tmp_path, raw_pdf, "ocr-failure")
    config = DoclingPdfParserConfig(worker_timeout_seconds=20)
    identity = DoclingPdfParser(config).processing_identity("pdf_failure_matrix_v1")
    parser = _DirectDoclingParser(config, identity, worker=False)
    real_ocr = docling_pdf_parser._ocr_selected_pages

    def fail_ocr(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("fixture OCR runtime crash")

    monkeypatch.setattr(docling_pdf_parser, "_ocr_selected_pages", fail_ocr)
    with pytest.raises(PdfProcessingError):
        with sqlite_ledger_transaction(ledger_path) as repository:
            ingest_pdf(
                _ingest_input(document_id, raw_blob_id, raw_pdf),
                repository,
                parser,
                Uuid4ProcessingAttemptIdFactory(),
                clock=_FixedClock(),
                transformation_archive=archive,
            )

    monkeypatch.setattr(docling_pdf_parser, "_ocr_selected_pages", real_ocr)
    failure = _only_attempt_outcome(ledger_path)
    assert failure.status is ProcessingAttemptStatus.FAILED
    assert failure.failure is not None
    assert failure.failure.code == "pdf_ocr_failure"
    assert failure.failure.retryable is True
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.list_document_representations() == ()
        recovered = ingest_pdf(
            _ingest_input(document_id, raw_blob_id, raw_pdf),
            repository,
            parser,
            Uuid4ProcessingAttemptIdFactory(),
            clock=_FixedClock(),
            transformation_archive=archive,
        )
    assert recovered.representation_id is not None
    outcomes = _all_attempt_outcomes(ledger_path)
    assert {outcome.status for outcome in outcomes} == {
        ProcessingAttemptStatus.FAILED,
        ProcessingAttemptStatus.SUCCEEDED,
    }
    assert failure in outcomes
    assert archive.read_raw_source(raw_blob_id) == raw_pdf


@pytest.mark.parametrize(
    ("relative_path", "creates_representation"),
    (
        ("corrupt/generated/corrupt_bad_xref_v1.pdf", True),
        ("corrupt/generated/corrupt_truncated_v1.pdf", False),
    ),
)
def test_corrupt_source_retry_after_restart_reaches_one_stable_closure(
    tmp_path: Path,
    relative_path: str,
    creates_representation: bool,
) -> None:
    raw_pdf = (FIXTURE_ROOT / relative_path).read_bytes()
    fixture_key = f"retry-{Path(relative_path).stem}"
    ledger_path, archive, document_id, raw_blob_id = _capture_pdf(tmp_path, raw_pdf, fixture_key)
    parser = DoclingPdfParser(DoclingPdfParserConfig(worker_timeout_seconds=10))
    ingest_input = _ingest_input(document_id, raw_blob_id, raw_pdf)

    representation_ids: list[str | None] = []
    for _ in range(2):
        with sqlite_ledger_transaction(ledger_path) as repository:
            result = ingest_pdf(
                ingest_input,
                repository,
                parser,
                Uuid4ProcessingAttemptIdFactory(),
                clock=_FixedClock(),
                transformation_archive=archive,
            )
            representation_ids.append(result.representation_id)

    outcomes = _all_attempt_outcomes(ledger_path)
    assert len(outcomes) == 2
    if creates_representation:
        assert representation_ids[0] is not None
        assert representation_ids[0] == representation_ids[1]
        assert {outcome.status for outcome in outcomes} == {ProcessingAttemptStatus.SUCCEEDED}
        assert {outcome.output_disposition for outcome in outcomes} == {
            OutputDisposition.CREATED,
            OutputDisposition.REUSED,
        }
        with sqlite_ledger_transaction(ledger_path) as repository:
            (representation,) = repository.list_document_representations()
        assert representation.id == representation_ids[0]
    else:
        assert representation_ids == [None, None]
        assert {outcome.status for outcome in outcomes} == {ProcessingAttemptStatus.BLOCKED}
        with sqlite_ledger_transaction(ledger_path) as repository:
            assert repository.list_document_representations() == ()
    assert archive.read_raw_source(raw_blob_id) == raw_pdf
