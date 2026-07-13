"""PDF ingestion use case over a tool-neutral, structure-preserving parser Port."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    Document,
    DocumentRepresentationBundle,
    OutputDisposition,
    PdfExtractionPath,
    PdfPageAccountingBundle,
    PdfPageExtractionStatus,
    PdfPageInventory,
    PdfPageQualityStatus,
    PdfPreflightReport,
    PdfTransformationArtifact,
    PdfTransformationType,
    ProcessingArtifactKind,
    ProcessingArtifactRef,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingBlocker,
    ProcessingFailure,
    ProcessingStage,
    ProcessingTaskFingerprint,
    ProvenanceActivity,
    RawBlob,
    RepresentationAnalyzability,
    SourceCoordinateSystem,
    TextViewKind,
)

from kotekomi_application.processing import (
    BuildIdentity,
    ProcessingAttemptIdFactory,
    ProcessingClock,
    ProcessingLedger,
    UtcProcessingClock,
    execute_processing_task,
    processing_attempt_outcome,
    processing_task_fingerprint,
)
from kotekomi_application.representation_identity import (
    BundleCommitDisposition,
    BundleCommitOutcome,
    DocumentRepresentationBundleLedger,
    deterministic_representation_id,
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
    crop_left: float = 0.0
    crop_top: float = 0.0
    crop_right: float | None = None
    crop_bottom: float | None = None
    image_coverage: float = 0.0
    suspicious_glyph_rate: float = 0.0
    glyph_issue_count: int = 0

    def __post_init__(self) -> None:
        values = (self.width, self.height, self.crop_left, self.crop_top)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("PDF page geometry must contain only finite coordinates.")
        crop_right = self.width if self.crop_right is None else self.crop_right
        crop_bottom = self.height if self.crop_bottom is None else self.crop_bottom
        if not math.isfinite(crop_right) or not math.isfinite(crop_bottom):
            raise ValueError("PDF crop geometry must contain only finite coordinates.")
        if self.page_index < 1 or self.width <= 0 or self.height <= 0:
            raise ValueError("PDF page geometry must identify a positive page and bounds.")
        if not 0 <= self.image_coverage <= 1:
            raise ValueError("PDF page image coverage must be between zero and one.")
        if not 0 <= self.suspicious_glyph_rate <= 1 or self.glyph_issue_count < 0:
            raise ValueError("PDF page glyph metrics must be nonnegative bounded values.")
        if self.rotation not in {0, 90, 180, 270}:
            raise ValueError("PDF page rotation must be a cardinal rotation.")
        if (
            self.crop_left < 0
            or self.crop_top < 0
            or crop_right <= self.crop_left
            or crop_bottom <= self.crop_top
            or crop_right > self.width
            or crop_bottom > self.height
        ):
            raise ValueError("PDF CropBox must lie within the MediaBox.")

    @property
    def resolved_crop_right(self) -> float:
        return self.width if self.crop_right is None else self.crop_right

    @property
    def resolved_crop_bottom(self) -> float:
        return self.height if self.crop_bottom is None else self.crop_bottom


@dataclass(frozen=True)
class PdfPreflight:
    parser_name: str
    parser_version: str
    preflight_tool: str
    preflight_tool_version: str
    encrypted: bool
    page_count: int
    pages: tuple[PdfPagePreflight, ...]
    warnings: tuple[str, ...] = ()
    pdf_version: str = "unknown"
    permissions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.page_count != len(self.pages):
            raise ValueError("PDF preflight page_count must match its page inventory.")
        expected_page_indices = tuple(range(1, self.page_count + 1))
        actual_page_indices = tuple(page.page_index for page in self.pages)
        if actual_page_indices != expected_page_indices:
            raise ValueError("PDF preflight pages must be ordered and contiguous from page 1.")


@dataclass(frozen=True)
class PdfParseInput:
    document: Document
    raw_bytes: bytes
    policy_id: str
    processing_task_fingerprint_id: str
    parsed_at: datetime
    access_credential: PdfAccessCredential | None = None
    expected_processor_config_digest: str | None = None


@dataclass(frozen=True)
class PdfAccessCredential:
    """Ephemeral PDF access secret bound by a non-secret immutable identifier."""

    credential_id: str
    password: str = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.credential_id.strip() or not self.password:
            raise ValueError("PDF access credentials require an ID and a nonempty password.")


class PdfProcessingError(RuntimeError):
    """Typed, credential-safe failure emitted by a PDF processor Port implementation."""

    def __init__(
        self,
        *,
        code: str,
        failure_type: str,
        safe_message: str,
        retryable: bool,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.failure_type = failure_type
        self.safe_message = safe_message
        self.retryable = retryable


@dataclass(frozen=True)
class PdfParseResult:
    preflight: PdfPreflight
    representation_bundle: DocumentRepresentationBundle | None
    transformation_payloads: tuple[PdfTransformationPayload, ...] = ()
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfTransformationPayload:
    activity_type: PdfTransformationType
    input_digest: str
    output_payload: bytes
    output_media_type: str
    tool_name: str
    tool_version: str
    model_name: str
    model_version: str
    model_digest: str
    configuration_digest: str
    page_scope: tuple[int, ...]
    language_set: tuple[str, ...] = ()
    confidence: float | None = None

    def __post_init__(self) -> None:
        digests = (self.input_digest, self.model_digest, self.configuration_digest)
        if any(len(digest) != 64 or set(digest) - set("0123456789abcdef") for digest in digests):
            raise ValueError("PDF transformation payload digests must be lowercase SHA-256.")
        if not self.output_payload or not self.output_media_type:
            raise ValueError(
                "PDF transformation payload requires archived output bytes and media type."
            )
        if tuple(sorted(set(self.page_scope))) != self.page_scope:
            raise ValueError("PDF transformation payload requires sorted unique page scope.")
        if self.activity_type is not PdfTransformationType.REPAIR and not self.page_scope:
            raise ValueError("A page-derived PDF transformation requires a nonempty page scope.")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("PDF transformation confidence must be between zero and one.")
        if self.activity_type is PdfTransformationType.OCR:
            if len(self.page_scope) != 1:
                raise ValueError("An OCR payload must account for exactly one PDF page.")
            if not self.language_set:
                raise ValueError("An OCR payload requires its language set.")
            if self.confidence is None:
                raise ValueError("An OCR payload requires page confidence.")
        elif self.language_set or self.confidence is not None:
            raise ValueError("A non-OCR payload cannot claim OCR language or confidence.")

    @property
    def output_digest(self) -> str:
        return hashlib.sha256(self.output_payload).hexdigest()


@dataclass(frozen=True)
class PdfProcessorIdentity:
    processor_name: str
    processor_version: str
    processor_config_digest: str
    output_contract_version: str


@dataclass(frozen=True)
class PdfPagePolicyDecision:
    extraction_path: PdfExtractionPath
    status: PdfPageQualityStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PdfExtractionPolicy:
    """Versioned page-selection and terminal-accounting policy."""

    policy_id: str
    policy_version = "selective_pdf_page_policy_v1"

    def select_extraction_path(self, page: PdfPagePreflight) -> PdfExtractionPath:
        if (
            page.embedded_text_character_count == 0
            or page.suspicious_glyph_rate >= 0.01
            or (
                "font_unicode_mapping_unavailable" in page.warnings
                and page.embedded_text_character_count < 64
            )
        ):
            return PdfExtractionPath.OCR
        return PdfExtractionPath.EMBEDDED

    def select_page_outcome(
        self,
        *,
        page: PdfPagePreflight,
        page_has_output: bool,
        representation_analyzability: RepresentationAnalyzability | None,
        source_blocked: bool,
        selected_path: PdfExtractionPath | None = None,
        ocr_confidence: float | None = None,
    ) -> PdfPagePolicyDecision:
        if source_blocked:
            return PdfPagePolicyDecision(
                PdfExtractionPath.INACCESSIBLE,
                PdfPageQualityStatus.BLOCKED,
                ("source_inaccessible",),
            )
        if not page_has_output:
            return PdfPagePolicyDecision(
                PdfExtractionPath.INACCESSIBLE,
                PdfPageQualityStatus.BLOCKED,
                ("parser_omitted_page_output",),
            )
        selected = selected_path or self.select_extraction_path(page)
        if selected is PdfExtractionPath.OCR and ocr_confidence is None:
            return PdfPagePolicyDecision(
                PdfExtractionPath.INACCESSIBLE,
                PdfPageQualityStatus.BLOCKED,
                ("selected_ocr_output_missing",),
            )
        if representation_analyzability is RepresentationAnalyzability.BLOCKED:
            status = PdfPageQualityStatus.BLOCKED
            reason = "representation_quality_blocked"
        elif (
            selected is PdfExtractionPath.OCR
            and ocr_confidence is not None
            and ocr_confidence < 0.8
        ):
            status = PdfPageQualityStatus.DEGRADED
            reason = "ocr_confidence_requires_degraded_quality"
        elif representation_analyzability is RepresentationAnalyzability.DEGRADED or (
            selected is PdfExtractionPath.EMBEDDED and page.suspicious_glyph_rate >= 0.01
        ):
            status = PdfPageQualityStatus.DEGRADED
            reason = "embedded_text_requires_degraded_quality"
        else:
            status = PdfPageQualityStatus.ACCEPTABLE
            reason = (
                "usable_ocr_text" if selected is PdfExtractionPath.OCR else "usable_embedded_text"
            )
        return PdfPagePolicyDecision(
            selected,
            status,
            (reason,),
        )


class PdfTransformationArchive(Protocol):
    def put_pdf_transformation_blob(
        self,
        object_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> object: ...

    def read_pdf_transformation_blob(self, object_id: str) -> bytes: ...


class PdfDocumentParser(Protocol):
    def processing_identity(self, policy_id: str) -> PdfProcessorIdentity: ...

    def parse(self, parse_input: PdfParseInput) -> PdfParseResult: ...


class PdfIngestLedger(DocumentRepresentationBundleLedger, ProcessingLedger, Protocol):
    def get_document(self, record_id: str) -> Document | None: ...
    def get_raw_blob(self, record_id: str) -> RawBlob | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...

    def commit_pdf_document_processing(
        self,
        *,
        expected_task_fingerprint_id: str,
        bundle: DocumentRepresentationBundle,
        page_accounting: PdfPageAccountingBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitOutcome: ...

    def commit_blocked_pdf_processing(
        self,
        *,
        expected_task_fingerprint_id: str,
        page_accounting: PdfPageAccountingBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitDisposition: ...


@dataclass(frozen=True)
class PdfIngestInput:
    document_id: str
    raw_bytes: bytes
    policy_id: str
    ingested_at: datetime
    raw_blob_id: str
    build_identity: BuildIdentity
    access_credential: PdfAccessCredential | None = None


@dataclass(frozen=True)
class PdfIngestOutcome:
    document_id: str
    preflight: PdfPreflight
    representation_id: str | None
    provenance_activity_id: str | None
    blocking_reasons: tuple[str, ...]
    preflight_report_id: str


def ingest_pdf(
    ingest_input: PdfIngestInput,
    ledger_repository: PdfIngestLedger,
    parser: PdfDocumentParser,
    attempt_id_factory: ProcessingAttemptIdFactory,
    clock: ProcessingClock | None = None,
    transformation_archive: PdfTransformationArchive | None = None,
) -> PdfIngestOutcome:
    # Validate the build before consulting the parser or writing any task/attempt.
    ingest_input.build_identity.snapshot()
    extraction_policy = PdfExtractionPolicy(ingest_input.policy_id)
    processing_clock = clock or UtcProcessingClock()
    document = ledger_repository.get_document(ingest_input.document_id)
    if document is None:
        raise ValueError(f"Document not found: {ingest_input.document_id}")
    actual_digest = hashlib.sha256(ingest_input.raw_bytes).hexdigest()
    if actual_digest != document.content_sha256:
        raise ValueError("PDF bytes do not match the immutable Document content_sha256.")
    raw_blob = ledger_repository.get_raw_blob(ingest_input.raw_blob_id)
    if raw_blob is None or raw_blob.digest != actual_digest:
        raise ValueError("PDF input must reference the immutable RawBlob for its bytes.")
    processor = _bind_processor_identity_to_access_credential(
        parser.processing_identity(ingest_input.policy_id),
        ingest_input.access_credential,
    )
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
        clock=processing_clock,
        invocation_id=f"pdf:{document.id}:{ingest_input.ingested_at.isoformat()}",
        operation=lambda _attempt: parser.parse(
            PdfParseInput(
                document=document,
                raw_bytes=ingest_input.raw_bytes,
                policy_id=ingest_input.policy_id,
                processing_task_fingerprint_id=task.id,
                parsed_at=ingest_input.ingested_at,
                access_credential=ingest_input.access_credential,
                expected_processor_config_digest=processor.processor_config_digest,
            )
        ),
        failure_for_exception=_pdf_processor_failure,
    )
    try:
        transformation_blobs = _archive_pdf_transformation_payloads(
            parse_result.transformation_payloads,
            raw_blob,
            ingest_input.ingested_at,
            transformation_archive,
        )
    except Exception as exc:
        _record_pdf_failure(
            ledger_repository=ledger_repository,
            attempt=attempt,
            finished_at=processing_clock.now(),
            exception=exc,
            code="pdf_transformation_archive_failure",
            stage=ProcessingStage.ARCHIVE,
            safe_message="PDF transformation output could not be archived.",
        )
        raise
    bundle = parse_result.representation_bundle
    if bundle is None:
        blocking_reasons = parse_result.blocking_reasons or (
            "PDF parser did not produce a representation bundle.",
        )
        page_accounting = _build_pdf_page_accounting(
            task=task,
            document=document,
            raw_blob=raw_blob,
            parse_result=parse_result,
            extraction_policy=extraction_policy,
            transformation_blobs=transformation_blobs,
        )
        provenance = _pdf_page_accounting_provenance(
            document=document,
            page_accounting=page_accounting,
            policy_id=ingest_input.policy_id,
            occurred_at=ingest_input.ingested_at,
        )
        blockers = tuple(
            ProcessingBlocker(
                code="pdf_blocked",
                stage=ProcessingStage.PARSER,
                safe_message=reason,
            )
            for reason in blocking_reasons
        )
        accounting_refs = _page_accounting_artifact_refs(page_accounting)
        created_outcome = processing_attempt_outcome(
            attempt=attempt,
            status=ProcessingAttemptStatus.BLOCKED,
            finished_at=processing_clock.now(),
            output_artifacts=accounting_refs
            + (
                ProcessingArtifactRef(
                    kind=ProcessingArtifactKind.PROVENANCE_ACTIVITY,
                    artifact_id=provenance.id,
                    role="production_provenance",
                ),
            ),
            blocking_reasons=blockers,
            provenance_activity_id=provenance.id,
        )
        reused_outcome = processing_attempt_outcome(
            attempt=attempt,
            status=ProcessingAttemptStatus.BLOCKED,
            finished_at=processing_clock.now(),
            output_artifacts=accounting_refs,
            blocking_reasons=blockers,
        )
        page_disposition = ledger_repository.commit_blocked_pdf_processing(
            expected_task_fingerprint_id=task.id,
            page_accounting=page_accounting,
            created_provenance_activity=provenance,
            created_outcome=created_outcome,
            reused_outcome=reused_outcome,
        )
        return PdfIngestOutcome(
            document_id=document.id,
            preflight=parse_result.preflight,
            representation_id=None,
            provenance_activity_id=(
                provenance.id if page_disposition is BundleCommitDisposition.CREATED else None
            ),
            blocking_reasons=blocking_reasons,
            preflight_report_id=page_accounting.preflight_report.id,
        )
    try:
        validate_representation_for_processing_task(
            task=task,
            processor=processor,
            document=document,
            input_digest=actual_digest,
            parse_result=parse_result,
        )
        page_accounting = _build_pdf_page_accounting(
            task=task,
            document=document,
            raw_blob=raw_blob,
            parse_result=parse_result,
            extraction_policy=extraction_policy,
            transformation_blobs=transformation_blobs,
        )
        _validate_page_accounting_quality(bundle, page_accounting)
    except ValueError as error:
        _record_pdf_failure(
            ledger_repository=ledger_repository,
            attempt=attempt,
            finished_at=processing_clock.now(),
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
            *(table.id for table in bundle.tables),
            *(fragment.id for fragment in bundle.table_fragments),
            *(row.id for row in bundle.table_rows),
            *(cell.id for cell in bundle.table_cells),
            *(annotation.id for annotation in bundle.table_annotations),
            *(reference.id for reference in bundle.references),
            bundle.quality_report.id,
            page_accounting.preflight_report.id,
            *(page.id for page in page_accounting.page_inventory),
            *(status.id for status in page_accounting.page_extraction_statuses),
            *(artifact.id for artifact in page_accounting.transformation_artifacts),
            *(blob.id for blob in page_accounting.transformation_blobs),
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
    ) + _page_accounting_artifact_refs(page_accounting)
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
        finished_at=processing_clock.now(),
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
        finished_at=processing_clock.now(),
        output_disposition=None if is_blocked else OutputDisposition.REUSED,
        output_artifacts=artifact_refs,
        blocking_reasons=blockers if is_blocked else (),
    )
    try:
        commit_outcome = ledger_repository.commit_pdf_document_processing(
            expected_task_fingerprint_id=task.id,
            bundle=bundle,
            page_accounting=page_accounting,
            created_provenance_activity=provenance,
            created_outcome=created_outcome,
            reused_outcome=reused_outcome,
        )
    except Exception as exc:
        _record_pdf_failure(
            ledger_repository=ledger_repository,
            attempt=attempt,
            finished_at=processing_clock.now(),
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
        preflight_report_id=page_accounting.preflight_report.id,
    )


def _bind_processor_identity_to_access_credential(
    processor: PdfProcessorIdentity,
    credential: PdfAccessCredential | None,
) -> PdfProcessorIdentity:
    if credential is None:
        return processor
    bound_digest = hashlib.sha256(
        json.dumps(
            {
                "base_processor_config_digest": processor.processor_config_digest,
                "access_credential_id": credential.credential_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return replace(processor, processor_config_digest=bound_digest)


def _pdf_processor_failure(exception: Exception) -> ProcessingFailure:
    if isinstance(exception, PdfProcessingError):
        return ProcessingFailure(
            code=exception.code,
            failure_type=exception.failure_type,
            stage=ProcessingStage.PARSER,
            safe_message=exception.safe_message,
            retryable=exception.retryable,
        )
    return ProcessingFailure(
        code="pdf_processor_failure",
        failure_type=type(exception).__name__,
        stage=ProcessingStage.PARSER,
        safe_message="PDF processor failed before producing a result.",
        retryable=True,
    )


def validate_representation_for_processing_task(
    *,
    task: ProcessingTaskFingerprint,
    processor: PdfProcessorIdentity,
    document: Document,
    input_digest: str,
    parse_result: PdfParseResult,
) -> None:
    """Fail closed when parser output is not bound to this exact processing task."""
    bundle = parse_result.representation_bundle
    if bundle is None:
        return
    representation = bundle.representation
    expected_representation_id = deterministic_representation_id(task.id)
    _require_equal(representation.id, expected_representation_id, "representation ID")
    _require_equal(
        representation.processing_task_fingerprint_id,
        task.id,
        "processing task fingerprint",
    )
    _require_equal(representation.document_id, document.id, "document ID")
    _require_equal(representation.input_blob_digest, input_digest, "input blob digest")
    _require_equal(representation.parser_name, processor.processor_name, "processor name")
    _require_equal(representation.parser_version, processor.processor_version, "processor version")
    _require_equal(
        representation.parser_config_digest,
        processor.processor_config_digest,
        "processor configuration",
    )
    _require_equal(
        parse_result.preflight.parser_name, processor.processor_name, "preflight processor name"
    )
    _require_equal(
        parse_result.preflight.parser_version,
        processor.processor_version,
        "preflight processor version",
    )
    validated_bundle = DocumentRepresentationBundle.model_validate(bundle.model_dump())
    _validate_pdf_region_geometry(parse_result.preflight, validated_bundle)
    _validate_pdf_text_views_and_reading_order(validated_bundle)
    _validate_pdf_extraction_provenance(parse_result, validated_bundle)


def _build_pdf_page_accounting(
    *,
    task: ProcessingTaskFingerprint,
    document: Document,
    raw_blob: RawBlob,
    parse_result: PdfParseResult,
    extraction_policy: PdfExtractionPolicy,
    transformation_blobs: tuple[RawBlob, ...],
) -> PdfPageAccountingBundle:
    report_id = _derived_pdf_record_id("pfr", task.id, "preflight")
    page_inventory_ids = tuple(
        _derived_pdf_record_id("ppi", report_id, str(page.page_index))
        for page in parse_result.preflight.pages
    )
    status_ids = tuple(
        _derived_pdf_record_id("pes", report_id, str(page.page_index))
        for page in parse_result.preflight.pages
    )
    blob_id_by_digest = {
        raw_blob.digest: raw_blob.id,
        **{blob.digest: blob.id for blob in transformation_blobs},
    }
    transformation_artifacts = tuple(
        PdfTransformationArtifact(
            id=_derived_pdf_record_id(
                "pta",
                report_id,
                payload.activity_type.value,
                payload.output_digest,
            ),
            preflight_report_id=report_id,
            input_blob_id=blob_id_by_digest[payload.input_digest],
            output_blob_id=blob.id,
            activity_type=payload.activity_type,
            tool_name=payload.tool_name,
            tool_version=payload.tool_version,
            model_name=payload.model_name,
            model_version=payload.model_version,
            model_digest=payload.model_digest,
            configuration_digest=payload.configuration_digest,
            page_scope=payload.page_scope,
            language_set=payload.language_set,
            confidence=payload.confidence,
        )
        for payload, blob in zip(
            parse_result.transformation_payloads,
            transformation_blobs,
            strict=True,
        )
    )
    report = PdfPreflightReport(
        id=report_id,
        document_id=document.id,
        raw_blob_id=raw_blob.id,
        processing_task_fingerprint_id=task.id,
        pdf_version=parse_result.preflight.pdf_version,
        page_count=parse_result.preflight.page_count,
        encrypted=parse_result.preflight.encrypted,
        permissions=parse_result.preflight.permissions,
        page_inventory_ids=page_inventory_ids,
        page_extraction_status_ids=status_ids,
        transformation_artifact_ids=tuple(artifact.id for artifact in transformation_artifacts),
        global_issues=tuple(
            dict.fromkeys(
                (
                    ("pdf_version_unknown",)
                    if parse_result.preflight.pdf_version == "unknown"
                    else ()
                )
                + parse_result.preflight.warnings
                + parse_result.blocking_reasons
            )
        ),
        preflight_tool=parse_result.preflight.preflight_tool,
        tool_version=parse_result.preflight.preflight_tool_version,
    )
    page_inventory = tuple(
        PdfPageInventory(
            id=page_id,
            preflight_report_id=report.id,
            page_index=page.page_index,
            media_width=page.width,
            media_height=page.height,
            crop_left=page.crop_left,
            crop_top=page.crop_top,
            crop_right=page.resolved_crop_right,
            crop_bottom=page.resolved_crop_bottom,
            rotation=page.rotation,
            embedded_text_character_count=page.embedded_text_character_count,
            image_coverage=page.image_coverage,
            suspicious_glyph_rate=page.suspicious_glyph_rate,
            glyph_issue_count=page.glyph_issue_count,
            warnings=page.warnings,
        )
        for page_id, page in zip(page_inventory_ids, parse_result.preflight.pages, strict=True)
    )
    bundle = parse_result.representation_bundle
    covered_pages: set[int] = (
        {region.page_number for region in bundle.source_regions} if bundle is not None else set()
    )
    extracted_characters_by_page = {page.page_index: 0 for page in parse_result.preflight.pages}
    if bundle is not None:
        text_views = {view.id: view for view in bundle.text_views}
        for node in bundle.nodes:
            node_length = node.end_char - node.start_char
            if node.text_view_id not in text_views:
                continue
            for page_number in node.source_page_numbers:
                if page_number in extracted_characters_by_page:
                    extracted_characters_by_page[page_number] += node_length
    statuses: list[PdfPageExtractionStatus] = []
    for status_id, page_id, page in zip(
        status_ids,
        page_inventory_ids,
        parse_result.preflight.pages,
        strict=True,
    ):
        page_has_output = page.page_index in covered_pages
        selected_path = extraction_policy.select_extraction_path(page)
        page_transformations = tuple(
            artifact
            for artifact in transformation_artifacts
            if page.page_index in artifact.page_scope
        )
        ocr_artifact = next(
            (
                artifact
                for artifact in page_transformations
                if artifact.activity_type is PdfTransformationType.OCR
            ),
            None,
        )
        page_ocr_confidence = ocr_artifact.confidence if ocr_artifact is not None else None
        decision = extraction_policy.select_page_outcome(
            page=page,
            page_has_output=page_has_output,
            representation_analyzability=(
                bundle.quality_report.analyzability if bundle is not None else None
            ),
            source_blocked=bundle is None,
            selected_path=selected_path,
            ocr_confidence=page_ocr_confidence,
        )
        statuses.append(
            PdfPageExtractionStatus(
                id=status_id,
                preflight_report_id=report.id,
                page_inventory_id=page_id,
                page_index=page.page_index,
                representation_id=(
                    bundle.representation.id if bundle is not None and page_has_output else None
                ),
                extraction_path=decision.extraction_path,
                status=decision.status,
                extracted_character_count=extracted_characters_by_page[page.page_index],
                rotation_applied=page.rotation,
                warnings=page.warnings,
                policy_id=extraction_policy.policy_id,
                policy_version=extraction_policy.policy_version,
                policy_reasons=decision.reasons,
                ocr_confidence=(
                    page_ocr_confidence
                    if decision.extraction_path in {PdfExtractionPath.OCR, PdfExtractionPath.MIXED}
                    else None
                ),
                transformation_artifact_ids=tuple(
                    artifact.id
                    for artifact in page_transformations
                    if decision.extraction_path
                    in {
                        PdfExtractionPath.OCR,
                        PdfExtractionPath.MIXED,
                    }
                ),
            )
        )
    return PdfPageAccountingBundle(
        preflight_report=report,
        page_inventory=page_inventory,
        page_extraction_statuses=tuple(statuses),
        transformation_artifacts=transformation_artifacts,
        transformation_blobs=transformation_blobs,
    )


def _archive_pdf_transformation_payloads(
    payloads: tuple[PdfTransformationPayload, ...],
    raw_blob: RawBlob,
    created_at: datetime,
    archive: PdfTransformationArchive | None,
) -> tuple[RawBlob, ...]:
    if payloads and archive is None:
        raise ValueError("PDF transformation output requires an Archive capability.")
    if archive is None:
        return ()
    available_input_digests = {raw_blob.digest}
    blobs: list[RawBlob] = []
    for payload in payloads:
        if payload.input_digest not in available_input_digests:
            raise ValueError("PDF transformation input digest is not archived by this task.")
        output_digest = payload.output_digest
        blob_id = f"blb_{output_digest}"
        archive.put_pdf_transformation_blob(blob_id, payload.output_payload, output_digest)
        if archive.read_pdf_transformation_blob(blob_id) != payload.output_payload:
            raise ValueError("Archived PDF transformation bytes disagree with parser output.")
        blobs.append(
            RawBlob(
                id=blob_id,
                hash_algorithm="sha256",
                digest=output_digest,
                byte_length=len(payload.output_payload),
                media_type=payload.output_media_type,
                storage_locator=f"transformations/{blob_id}.bin",
                created_at=created_at,
            )
        )
        available_input_digests.add(output_digest)
    return tuple(blobs)


def _derived_pdf_record_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(":".join(parts).encode()).hexdigest()[:HASH_ID_LENGTH]
    return f"{prefix}_{digest}"


def _validate_page_accounting_quality(
    representation_bundle: DocumentRepresentationBundle,
    page_accounting: PdfPageAccountingBundle,
) -> None:
    has_blocked_page = any(
        status.status is PdfPageQualityStatus.BLOCKED
        for status in page_accounting.page_extraction_statuses
    )
    if (
        has_blocked_page
        and representation_bundle.quality_report.analyzability
        is not RepresentationAnalyzability.BLOCKED
    ):
        raise ValueError(
            "PDF parser reported an analyzable representation with an unaccounted page."
        )


def _page_accounting_artifact_refs(
    page_accounting: PdfPageAccountingBundle,
) -> tuple[ProcessingArtifactRef, ...]:
    return (
        ProcessingArtifactRef(
            kind=ProcessingArtifactKind.PDF_PREFLIGHT_REPORT,
            artifact_id=page_accounting.preflight_report.id,
            role="authoritative_pdf_preflight",
        ),
        *(
            ProcessingArtifactRef(
                kind=ProcessingArtifactKind.PDF_PAGE_INVENTORY,
                artifact_id=page.id,
                role=f"pdf_page_{page.page_index}_inventory",
            )
            for page in page_accounting.page_inventory
        ),
        *(
            ProcessingArtifactRef(
                kind=ProcessingArtifactKind.PDF_PAGE_EXTRACTION_STATUS,
                artifact_id=status.id,
                role=f"pdf_page_{status.page_index}_terminal_status",
            )
            for status in page_accounting.page_extraction_statuses
        ),
        *(
            ProcessingArtifactRef(
                kind=ProcessingArtifactKind.PDF_TRANSFORMATION_ARTIFACT,
                artifact_id=artifact.id,
                role=f"pdf_{artifact.activity_type.value}_transformation",
                digest=artifact.configuration_digest,
            )
            for artifact in page_accounting.transformation_artifacts
        ),
        *(
            ProcessingArtifactRef(
                kind=ProcessingArtifactKind.PDF_TRANSFORMATION_BLOB,
                artifact_id=blob.id,
                role="archived_pdf_transformation_bytes",
                digest=blob.digest,
            )
            for blob in page_accounting.transformation_blobs
        ),
    )


def _pdf_page_accounting_provenance(
    *,
    document: Document,
    page_accounting: PdfPageAccountingBundle,
    policy_id: str,
    occurred_at: datetime,
) -> ProvenanceActivity:
    report = page_accounting.preflight_report
    return ProvenanceActivity(
        id=_provenance_id(document.id, report.id, policy_id),
        activity_type=PDF_INGEST_ACTIVITY,
        agent=report.preflight_tool,
        input_ids=(document.id, policy_id),
        output_ids=(
            report.id,
            *(page.id for page in page_accounting.page_inventory),
            *(status.id for status in page_accounting.page_extraction_statuses),
            *(artifact.id for artifact in page_accounting.transformation_artifacts),
            *(blob.id for blob in page_accounting.transformation_blobs),
        ),
        occurred_at=occurred_at,
    )


def _require_equal(actual: str, expected: str, field: str) -> None:
    if actual != expected:
        raise ValueError(f"PDF parser returned a mismatched {field}.")


def _validate_pdf_region_geometry(
    preflight: PdfPreflight,
    bundle: DocumentRepresentationBundle,
) -> None:
    pages_by_number = {page.page_index: page for page in preflight.pages}
    for region in bundle.source_regions:
        if region.coordinate_system is not SourceCoordinateSystem.PDF_POINTS_TOP_LEFT_V1:
            raise ValueError("PDF SourceRegion uses a non-canonical coordinate system.")
        page = pages_by_number.get(region.page_number)
        if page is None:
            raise ValueError("PDF SourceRegion references a page outside the preflight inventory.")
        if region.page_width != page.width or region.page_height != page.height:
            raise ValueError("PDF SourceRegion MediaBox disagrees with preflight geometry.")
        if (
            region.left < page.crop_left
            or region.top < page.crop_top
            or region.right > page.resolved_crop_right
            or region.bottom > page.resolved_crop_bottom
        ):
            raise ValueError("PDF SourceRegion must lie within the page CropBox.")
        if region.rotation_applied != page.rotation:
            raise ValueError("PDF SourceRegion rotation transform disagrees with preflight.")


def _validate_pdf_text_views_and_reading_order(
    bundle: DocumentRepresentationBundle,
) -> None:
    views_by_kind = {view.kind: view for view in bundle.text_views}
    if set(views_by_kind) != {TextViewKind.LOGICAL, TextViewKind.DISPLAY}:
        raise ValueError("PDF representation requires one logical and one display TextView.")
    content_nodes = tuple(
        sorted(
            (node for node in bundle.nodes if node.parent_node_id is not None),
            key=lambda node: node.order_index,
        )
    )
    logical_nodes = tuple(node for node in content_nodes if node.node_type != "furniture")
    if any(node.text_view_id != views_by_kind[TextViewKind.LOGICAL].id for node in logical_nodes):
        raise ValueError("PDF analysis nodes must reference the logical TextView.")
    furniture_nodes = tuple(node for node in content_nodes if node.node_type == "furniture")
    if any(node.text_view_id != views_by_kind[TextViewKind.DISPLAY].id for node in furniture_nodes):
        raise ValueError("PDF furniture nodes must reference the display TextView.")
    reading_edges = tuple(edge for edge in bundle.edges if edge.edge_type == "reading_order")
    expected_pairs = tuple(
        (earlier.id, later.id)
        for earlier, later in zip(logical_nodes, logical_nodes[1:], strict=False)
    )
    actual_pairs = tuple((edge.from_node_id, edge.to_node_id) for edge in reading_edges)
    if actual_pairs != expected_pairs:
        raise ValueError("PDF reading-order edges must form one exact logical-node chain.")


def _validate_pdf_extraction_provenance(
    parse_result: PdfParseResult,
    bundle: DocumentRepresentationBundle,
) -> None:
    policy = PdfExtractionPolicy(parse_result.preflight.parser_name)
    selected_ocr_pages = {
        page.page_index
        for page in parse_result.preflight.pages
        if policy.select_extraction_path(page) is PdfExtractionPath.OCR
    }
    covered_pages = {region.page_number for region in bundle.source_regions}
    expected_transformed_pages = selected_ocr_pages & covered_pages
    ocr_payload_pages = {
        page
        for payload in parse_result.transformation_payloads
        if payload.activity_type is PdfTransformationType.OCR
        for page in payload.page_scope
    }
    render_payload_pages = {
        page
        for payload in parse_result.transformation_payloads
        if payload.activity_type is PdfTransformationType.RENDER
        for page in payload.page_scope
    }
    if (
        ocr_payload_pages != expected_transformed_pages
        or render_payload_pages != expected_transformed_pages
    ):
        raise ValueError("PDF OCR and render transformations must match selected pages exactly.")
    for node in bundle.nodes:
        if node.parent_node_id is None:
            continue
        expected_path = (
            PdfExtractionPath.OCR
            if any(page in selected_ocr_pages for page in node.source_page_numbers)
            else PdfExtractionPath.EMBEDDED
        )
        if node.extraction_path is not expected_path:
            raise ValueError("PDF node extraction provenance disagrees with page selection.")
        if expected_path is PdfExtractionPath.OCR and node.parser_confidence is None:
            raise ValueError("OCR-derived PDF nodes require parser confidence.")


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
