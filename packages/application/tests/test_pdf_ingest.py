import hashlib
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    BuildIdentity,
    PdfDocumentParser,
    PdfIngestInput,
    PdfIngestLedger,
    PdfParseInput,
    PdfParseResult,
    PdfPreflight,
    PdfProcessorIdentity,
    ProcessingTaskDisposition,
    ingest_pdf,
)
from kotekomi_domain import (
    Document,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingTaskFingerprint,
    RawBlob,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)
RAW_PDF = b"%PDF-1.7\nfixture"
BUILD_IDENTITY = BuildIdentity("fixture", "fixture", "a" * 64, "1")


class SequenceAttemptIdFactory:
    def __init__(self) -> None:
        self.next_id = 1

    def new_attempt_id(self) -> str:
        attempt_id = f"pat_{self.next_id:024d}"
        self.next_id += 1
        return attempt_id


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
                encrypted=False,
                page_count=0,
                pages=(),
            ),
            representation_bundle=None,
            blocking_reasons=("fixture parser blocked",),
        )


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

    def commit_processing_attempt_start(self) -> None:
        return None

    def record_failed_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        self.append_processing_attempt_outcome(record)


def test_ingest_pdf_returns_typed_blocked_outcome_without_publishing_representation() -> None:
    outcome = ingest_pdf(
        PdfIngestInput(
            "doc_pdf_fixture", RAW_PDF, "pdf_policy_v1", NOW, "blb_pdf_fixture", BUILD_IDENTITY
        ),
        cast(PdfIngestLedger, FakePdfLedger()),
        cast(PdfDocumentParser, FakePdfParser()),
        SequenceAttemptIdFactory(),
    )

    assert outcome.representation_id is None
    assert outcome.provenance_activity_id is None
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
