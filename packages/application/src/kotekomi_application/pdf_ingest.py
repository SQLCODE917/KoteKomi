"""PDF ingestion use case over a tool-neutral, structure-preserving parser Port."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    Document,
    DocumentRepresentationBundle,
    OutputDisposition,
    ProcessingArtifactKind,
    ProcessingArtifactRef,
    ProcessingAttempt,
    ProcessingAttemptStatus,
    ProcessingBlocker,
    ProcessingFailure,
    ProcessingStage,
    ProvenanceActivity,
    RawBlob,
    RepresentationAnalyzability,
)

from kotekomi_application.processing import (
    BuildIdentity,
    ProcessingAttemptIdFactory,
    ProcessingLedger,
    execute_processing_task,
    processing_attempt_outcome,
    processing_task_fingerprint,
)
from kotekomi_application.representation_identity import (
    BundleCommitDisposition,
    DocumentRepresentationBundleLedger,
)

HASH_ID_LENGTH = 24
PDF_INGEST_ACTIVITY = "pdf_document_ingest"


@dataclass(frozen=True)
class PdfPagePreflight:
    page_index: int
    width: float
    height: float
    rotation: int
    embedded_text_character_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfPreflight:
    parser_name: str
    parser_version: str
    encrypted: bool
    page_count: int
    pages: tuple[PdfPagePreflight, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfParseInput:
    document: Document
    raw_bytes: bytes
    policy_id: str
    processing_task_fingerprint_id: str
    parsed_at: datetime


@dataclass(frozen=True)
class PdfParseResult:
    preflight: PdfPreflight
    representation_bundle: DocumentRepresentationBundle | None
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfProcessorIdentity:
    processor_name: str
    processor_version: str
    processor_config_digest: str
    output_contract_version: str


class PdfDocumentParser(Protocol):
    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity: ...

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult: ...


class PdfIngestLedger(DocumentRepresentationBundleLedger, ProcessingLedger, Protocol):
    def get_document(self, record_id: str) -> Document | None: ...
    def get_raw_blob(self, record_id: str) -> RawBlob | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...


@dataclass(frozen=True)
class PdfIngestInput:
    document_id: str
    raw_bytes: bytes
    policy_id: str
    ingested_at: datetime
    raw_blob_id: str
    build_identity: BuildIdentity


@dataclass(frozen=True)
class PdfIngestOutcome:
    document_id: str
    preflight: PdfPreflight
    representation_id: str | None
    provenance_activity_id: str | None
    blocking_reasons: tuple[str, ...]


def ingest_pdf(
    ingest_input: PdfIngestInput,
    ledger_repository: PdfIngestLedger,
    parser: PdfDocumentParser,
    attempt_id_factory: ProcessingAttemptIdFactory,
) -> PdfIngestOutcome:
    # Validate the build before consulting the parser or writing any task/attempt.
    ingest_input.build_identity.snapshot()
    document = ledger_repository.get_document(ingest_input.document_id)
    if document is None:
        raise ValueError(f"Document not found: {ingest_input.document_id}")
    actual_digest = hashlib.sha256(ingest_input.raw_bytes).hexdigest()
    if actual_digest != document.content_sha256:
        raise ValueError("PDF bytes do not match the immutable Document content_sha256.")
    raw_blob = ledger_repository.get_raw_blob(ingest_input.raw_blob_id)
    if raw_blob is None or raw_blob.digest != actual_digest:
        raise ValueError("PDF input must reference the immutable RawBlob for its bytes.")
    processor = parser.processing_identity(ingest_input.policy_id)
    task = processing_task_fingerprint(
        task_kind="pdf_document_representation",
        document_id=document.id,
        blob_id=raw_blob.id,
        input_digest=actual_digest,
        processor_name=processor.processor_name,
        processor_version=processor.processor_version,
        processor_config_digest=processor.processor_config_digest,
        build_identity=ingest_input.build_identity,
        policy_id=ingest_input.policy_id,
        output_contract_version=processor.output_contract_version,
    )
    attempt, parse_result = execute_processing_task(
        task=task,
        ledger=ledger_repository,
        attempt_id_factory=attempt_id_factory,
        started_at=ingest_input.ingested_at,
        invocation_id=f"pdf:{document.id}:{ingest_input.ingested_at.isoformat()}",
        operation=lambda _attempt: parser.parse(
            PdfParseInput(
                document=document,
                raw_bytes=ingest_input.raw_bytes,
                policy_id=ingest_input.policy_id,
                processing_task_fingerprint_id=task.id,
                parsed_at=ingest_input.ingested_at,
            )
        ),
        failure_for_exception=lambda exc: ProcessingFailure(
            code="pdf_processor_failure",
            failure_type=type(exc).__name__,
            stage=ProcessingStage.PARSER,
            safe_message="PDF processor failed before producing a result.",
            retryable=False,
        ),
    )
    bundle = parse_result.representation_bundle
    if bundle is None:
        blocking_reasons = parse_result.blocking_reasons or (
            "PDF parser did not produce a representation bundle.",
        )
        ledger_repository.append_processing_attempt_outcome(
            processing_attempt_outcome(
                attempt=attempt,
                status=ProcessingAttemptStatus.BLOCKED,
                finished_at=ingest_input.ingested_at,
                blocking_reasons=tuple(
                    ProcessingBlocker(
                        code="pdf_blocked",
                        stage=ProcessingStage.PARSER,
                        safe_message=reason,
                    )
                    for reason in blocking_reasons
                ),
            )
        )
        return PdfIngestOutcome(
            document_id=document.id,
            preflight=parse_result.preflight,
            representation_id=None,
            provenance_activity_id=None,
            blocking_reasons=blocking_reasons,
        )
    if bundle.representation.document_id != document.id:
        error = ValueError("PDF parser returned a representation for a different Document.")
        _record_pdf_failure(
            ledger_repository=ledger_repository,
            attempt=attempt,
            finished_at=ingest_input.ingested_at,
            exception=error,
            code="pdf_representation_validation_failure",
            stage=ProcessingStage.REPRESENTATION_VALIDATION,
            safe_message="PDF parser returned an invalid representation.",
        )
        raise error
    provenance_activity_id = _provenance_id(
        document.id, bundle.representation.id, ingest_input.policy_id
    )
    provenance = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=PDF_INGEST_ACTIVITY,
        agent=parse_result.preflight.parser_name,
        input_ids=(document.id, ingest_input.policy_id),
        output_ids=(
            bundle.representation.id,
            *(view.id for view in bundle.text_views),
            *(node.id for node in bundle.nodes),
            *(region.id for region in bundle.source_regions),
            *(edge.id for edge in bundle.edges),
            bundle.quality_report.id,
        ),
        occurred_at=ingest_input.ingested_at,
    )
    artifact_refs = (
        ProcessingArtifactRef(
            kind=ProcessingArtifactKind.DOCUMENT_REPRESENTATION,
            artifact_id=bundle.representation.id,
            role="canonical_document_representation",
            digest=bundle.representation.canonical_output_digest,
        ),
        ProcessingArtifactRef(
            kind=ProcessingArtifactKind.QUALITY_REPORT,
            artifact_id=bundle.quality_report.id,
            role="quality_report",
        ),
    )
    blockers = tuple(
        ProcessingBlocker(
            code="pdf_blocked",
            stage=ProcessingStage.PARSER,
            safe_message=reason,
        )
        for reason in (
            parse_result.blocking_reasons
            or ("PDF representation is blocked by its quality report.",)
        )
    )
    is_blocked = bundle.quality_report.analyzability is RepresentationAnalyzability.BLOCKED
    terminal_status = (
        ProcessingAttemptStatus.BLOCKED if is_blocked else ProcessingAttemptStatus.SUCCEEDED
    )
    created_outcome = processing_attempt_outcome(
        attempt=attempt,
        status=terminal_status,
        finished_at=ingest_input.ingested_at,
        output_disposition=None if is_blocked else OutputDisposition.CREATED,
        output_artifacts=artifact_refs
        + (
            ProcessingArtifactRef(
                kind=ProcessingArtifactKind.PROVENANCE_ACTIVITY,
                artifact_id=provenance.id,
                role="production_provenance",
            ),
        ),
        blocking_reasons=blockers if is_blocked else (),
        provenance_activity_id=provenance.id,
    )
    reused_outcome = processing_attempt_outcome(
        attempt=attempt,
        status=terminal_status,
        finished_at=ingest_input.ingested_at,
        output_disposition=None if is_blocked else OutputDisposition.REUSED,
        output_artifacts=artifact_refs,
        blocking_reasons=blockers if is_blocked else (),
    )
    try:
        commit_outcome = ledger_repository.commit_document_representation_processing(
            bundle=bundle,
            created_provenance_activity=provenance,
            created_outcome=created_outcome,
            reused_outcome=reused_outcome,
        )
    except Exception as exc:
        _record_pdf_failure(
            ledger_repository=ledger_repository,
            attempt=attempt,
            finished_at=ingest_input.ingested_at,
            exception=exc,
            code="pdf_persistence_failure",
            stage=ProcessingStage.PERSISTENCE,
            safe_message="PDF representation could not be committed.",
        )
        raise
    return PdfIngestOutcome(
        document_id=document.id,
        preflight=parse_result.preflight,
        representation_id=bundle.representation.id,
        provenance_activity_id=(
            provenance_activity_id
            if commit_outcome.disposition is BundleCommitDisposition.CREATED
            else None
        ),
        blocking_reasons=parse_result.blocking_reasons,
    )


def _provenance_id(document_id: str, representation_id: str, policy_id: str) -> str:
    value = f"{document_id}:{representation_id}:{policy_id}:{PDF_INGEST_ACTIVITY}"
    return f"prv_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"


def _record_pdf_failure(
    *,
    ledger_repository: PdfIngestLedger,
    attempt: ProcessingAttempt,
    finished_at: datetime,
    exception: Exception,
    code: str,
    stage: ProcessingStage,
    safe_message: str,
) -> None:
    ledger_repository.record_failed_processing_attempt_outcome(
        processing_attempt_outcome(
            attempt=attempt,
            status=ProcessingAttemptStatus.FAILED,
            finished_at=finished_at,
            failure=ProcessingFailure(
                code=code,
                failure_type=type(exception).__name__,
                stage=stage,
                safe_message=safe_message,
                retryable=False,
            ),
        )
    )
