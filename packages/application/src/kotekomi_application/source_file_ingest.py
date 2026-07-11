"""Local file Source ingest use case."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from kotekomi_domain import (
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentVersionKind,
    OutputDisposition,
    ParseQualityReport,
    ProcessingArtifactKind,
    ProcessingArtifactRef,
    ProcessingAttempt,
    ProcessingAttemptStatus,
    ProcessingFailure,
    ProcessingStage,
    ProvenanceActivity,
    RepresentationAnalyzability,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

from kotekomi_application.ports import ArchiveStore, StagedArchiveObject
from kotekomi_application.processing import (
    BuildIdentity,
    ProcessingAttemptIdFactory,
    ProcessingLedger,
    Uuid4ProcessingAttemptIdFactory,
    execute_processing_task,
    processing_attempt_outcome,
    processing_task_fingerprint,
    reconcile_interrupted_processing_attempts,
)
from kotekomi_application.representation_identity import (
    DocumentRepresentationBundleLedger,
    deterministic_representation_id,
)
from kotekomi_application.source_capture import (
    CaptureLedger,
    CaptureRequest,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    capture_identity,
    capture_source,
)

SUPPORTED_TEXT_SUFFIXES = frozenset({".md", ".txt"})
HASH_ID_LENGTH = 24
MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


class SourceFileLedger(
    CaptureLedger, DocumentRepresentationBundleLedger, ProcessingLedger, Protocol
):
    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


@dataclass(frozen=True)
class AuthoritativeCaptureRequest:
    local_file_path: str
    filename: str
    raw_bytes: bytes
    ingested_at: datetime
    build_identity: BuildIdentity
    source_identity_key: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class AuthoritativeCaptureOutcome:
    source_id: str
    document_id: str
    representation_id: str
    provenance_activity_id: str
    raw_path: str
    extracted_text_path: str
    created: bool


def commit_authoritative_capture(
    ingest_input: AuthoritativeCaptureRequest,
    archive_store: ArchiveStore,
    ledger_repository: SourceFileLedger,
    attempt_id_factory: ProcessingAttemptIdFactory | None = None,
) -> AuthoritativeCaptureOutcome:
    suffix = Path(ingest_input.filename).suffix.lower()
    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_TEXT_SUFFIXES))
        raise ValueError(
            f"Unsupported Source file suffix {suffix!r}; supported suffixes: {supported}"
        )

    ingest_input.build_identity.snapshot()
    resolved_attempt_id_factory = attempt_id_factory or Uuid4ProcessingAttemptIdFactory()
    extracted_text = ingest_input.raw_bytes.decode("utf-8")
    source_type = infer_source_type(extracted_text)
    source_title = extract_source_title(ingest_input.filename, extracted_text)
    published_at = parse_dateline_date(extracted_text)
    content_sha256 = hashlib.sha256(ingest_input.raw_bytes).hexdigest()
    source_key = ingest_input.source_identity_key or str(
        Path(ingest_input.local_file_path).resolve()
    )
    idempotency_key = ingest_input.idempotency_key or _local_file_request_fingerprint(
        source_key, content_sha256
    )
    request = CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=source_type,
            title=source_title,
            stable_key=source_key,
            uri=ingest_input.local_file_path,
        ),
        payload=ingest_input.raw_bytes,
        media_type="text/markdown" if suffix == ".md" else "text/plain",
        storage_locator="pending",
        idempotency_key=idempotency_key,
        retrieval_method="local_file",
        requested_uri=ingest_input.local_file_path,
        canonical_uri=ingest_input.local_file_path,
        provider_item_id=None,
        provider_version=None,
        version_kind=DocumentVersionKind.ORIGINAL,
        publication_time=published_at,
        provider_update_time=None,
        captured_at=ingest_input.ingested_at,
        transaction_time=ingest_input.ingested_at,
        rights_profile_id=None,
        embargo_until=None,
        request_metadata={},
        response_metadata={},
    )
    identity_policy = StableSourceIdentityPolicy()
    identity = capture_identity(request, identity_policy)
    prior_documents = ledger_repository.list_documents_for_source(identity.source_id)
    existing_document = ledger_repository.get_document(identity.document_id)
    if existing_document is None and prior_documents:
        raise ValueError(
            "UNCLASSIFIED_REVISION: changed local-file bytes require an explicit revision decision."
        )
    request = replace(
        request,
        storage_locator=f"sources/raw/{identity.raw_blob_id}.bin",
        extracted_text_locator=f"documents/extracted/{identity.document_id}.txt",
    )
    provenance_activity_id = f"prv_{identity.source_capture_id.removeprefix('cap_')}"
    task = processing_task_fingerprint(
        task_kind="local_file_document_representation",
        document_id=identity.document_id,
        blob_id=identity.raw_blob_id,
        input_digest=content_sha256,
        processor_name="local_file",
        processor_version="1",
        processor_config_digest=hashlib.sha256(b"utf8_identity_v1").hexdigest(),
        build_identity=ingest_input.build_identity,
        policy_id="local_file_v1",
        output_contract_version="1",
    )
    representation_id = deterministic_representation_id(task.id)
    representation_key = representation_id.removeprefix("rep_")
    text_view_id = f"tvw_{representation_key}_logical"
    document_node_id = f"nod_{representation_key}_document"
    quality_report_id = f"pqr_{representation_key}_quality_v1"
    reconcile_interrupted_processing_attempts(
        task_fingerprint_id=task.id,
        ledger=ledger_repository,
        reconciled_at=ingest_input.ingested_at,
        interruption_basis="authoritative capture retry found an unclosed attempt",
    )

    existing_capture = ledger_repository.get_source_capture(identity.source_capture_id)
    existing_provenance = ledger_repository.get_provenance_activity(provenance_activity_id)
    if (
        existing_capture is not None
        and existing_document is not None
        and existing_provenance is not None
    ):
        outcome = capture_source(request, ledger_repository, identity_policy)
        attempt, _ = execute_processing_task(
            task=task,
            ledger=ledger_repository,
            attempt_id_factory=resolved_attempt_id_factory,
            started_at=ingest_input.ingested_at,
            invocation_id=f"source_file:{identity.document_id}:{idempotency_key}",
            operation=lambda _attempt: _require_complete_existing_closure(
                archive_store=archive_store,
                ledger_repository=ledger_repository,
                raw_blob_id=identity.raw_blob_id,
                raw_bytes=ingest_input.raw_bytes,
                document_id=existing_document.id,
                representation_id=representation_id,
            ),
            failure_for_exception=lambda exc: ProcessingFailure(
                code="incomplete_closure",
                failure_type=type(exc).__name__,
                stage=ProcessingStage.RECONCILIATION,
                safe_message="Existing processing closure is incomplete.",
                retryable=False,
            ),
        )
        ledger_repository.append_processing_attempt_outcome(
            processing_attempt_outcome(
                attempt=attempt,
                status=ProcessingAttemptStatus.SUCCEEDED,
                finished_at=ingest_input.ingested_at,
                output_disposition=OutputDisposition.REUSED,
                output_artifacts=(
                    ProcessingArtifactRef(
                        kind=ProcessingArtifactKind.DOCUMENT_REPRESENTATION,
                        artifact_id=representation_id,
                        role="canonical_document_representation",
                    ),
                ),
            )
        )
        return AuthoritativeCaptureOutcome(
            source_id=outcome.source.id,
            document_id=outcome.document.id,
            representation_id=representation_id,
            provenance_activity_id=provenance_activity_id,
            raw_path=f"sources/raw/{outcome.raw_blob.id}.bin",
            extracted_text_path=f"documents/extracted/{outcome.document.id}.txt",
            created=False,
        )

    staged_objects: list[StagedArchiveObject] = []
    try:
        archive_store.put_if_absent_or_identical(
            identity.raw_blob_id,
            ingest_input.raw_bytes,
            content_sha256,
        )
        if existing_document is None:
            try:
                archived_text = archive_store.read_document_text(identity.document_id)
            except FileNotFoundError:
                staged_text = archive_store.stage_document_text(
                    identity.document_id,
                    extracted_text,
                )
                staged_objects.append(staged_text)
            else:
                if archived_text != extracted_text:
                    raise ValueError(
                        "Existing archived document text conflicts with the deterministic "
                        "local-file extraction."
                    )
        for staged_object in staged_objects:
            archive_store.promote_staged_object(staged_object)

        outcome = capture_source(request, ledger_repository, identity_policy)
        document = outcome.document

        def commit_representation(attempt: ProcessingAttempt) -> None:
            if existing_document is not None:
                _require_repairable_capture_closure(
                    archive_store=archive_store,
                    ledger_repository=ledger_repository,
                    raw_blob_id=identity.raw_blob_id,
                    raw_bytes=ingest_input.raw_bytes,
                    document_id=existing_document.id,
                    representation_id=representation_id,
                )
            text_digest = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
            text_view = TextView(
                id=text_view_id,
                representation_id=representation_id,
                kind=TextViewKind.LOGICAL,
                content_digest=text_digest,
                text=extracted_text,
                normalization_policy="utf8_identity_v1",
            )
            document_node = DocumentNode(
                id=document_node_id,
                representation_id=representation_id,
                node_type="document",
                order_index=0,
                text_view_id=text_view_id,
                start_char=0,
                end_char=len(extracted_text),
                text=extracted_text,
            )
            quality_report = ParseQualityReport(
                id=quality_report_id,
                representation_id=representation_id,
                metric_values={"text_char_count": len(extracted_text)},
                issues=("empty_text",) if not extracted_text else (),
                analyzability=(
                    RepresentationAnalyzability.BLOCKED
                    if not extracted_text
                    else RepresentationAnalyzability.ACCEPTABLE
                ),
            )
            representation_template = DocumentRepresentation(
                id=representation_id,
                document_id=document.id,
                parser_name="local_file",
                parser_version="1",
                parser_config_digest=hashlib.sha256(b"utf8_identity_v1").hexdigest(),
                processing_task_fingerprint_id=task.id,
                input_blob_digest=content_sha256,
                canonical_output_digest="0" * 64,
                created_at=ingest_input.ingested_at,
            )
            representation = representation_template.model_copy(
                update={
                    "canonical_output_digest": canonical_representation_digest(
                        representation_template,
                        text_views=(text_view,),
                        nodes=(document_node,),
                        edges=(),
                        source_regions=(),
                        quality_report=quality_report,
                    )
                }
            )
            representation_bundle = DocumentRepresentationBundle(
                representation=representation,
                text_views=(text_view,),
                nodes=(document_node,),
                quality_report=quality_report,
            )
            provenance_activity = ProvenanceActivity(
                id=provenance_activity_id,
                activity_type="source_file_ingest",
                agent="kotekomi",
                input_ids=(ingest_input.local_file_path,),
                output_ids=(
                    outcome.source.id,
                    outcome.raw_blob.id,
                    outcome.source_capture.id,
                    document.id,
                    representation_id,
                    text_view_id,
                    document_node_id,
                    quality_report_id,
                ),
                occurred_at=ingest_input.ingested_at,
            )
            ledger_repository.commit_document_representation_processing(
                bundle=representation_bundle,
                created_provenance_activity=provenance_activity,
                created_outcome=processing_attempt_outcome(
                    attempt=attempt,
                    status=ProcessingAttemptStatus.SUCCEEDED,
                    finished_at=ingest_input.ingested_at,
                    output_disposition=OutputDisposition.CREATED,
                    output_artifacts=(
                        ProcessingArtifactRef(
                            kind=ProcessingArtifactKind.DOCUMENT_REPRESENTATION,
                            artifact_id=representation_id,
                            role="canonical_document_representation",
                        ),
                        ProcessingArtifactRef(
                            kind=ProcessingArtifactKind.QUALITY_REPORT,
                            artifact_id=quality_report_id,
                            role="quality_report",
                        ),
                        ProcessingArtifactRef(
                            kind=ProcessingArtifactKind.PROVENANCE_ACTIVITY,
                            artifact_id=provenance_activity.id,
                            role="production_provenance",
                        ),
                    ),
                    provenance_activity_id=provenance_activity.id,
                ),
                reused_outcome=processing_attempt_outcome(
                    attempt=attempt,
                    status=ProcessingAttemptStatus.SUCCEEDED,
                    finished_at=ingest_input.ingested_at,
                    output_disposition=OutputDisposition.REUSED,
                    output_artifacts=(
                        ProcessingArtifactRef(
                            kind=ProcessingArtifactKind.DOCUMENT_REPRESENTATION,
                            artifact_id=representation_id,
                            role="canonical_document_representation",
                        ),
                        ProcessingArtifactRef(
                            kind=ProcessingArtifactKind.QUALITY_REPORT,
                            artifact_id=quality_report_id,
                            role="quality_report",
                        ),
                    ),
                ),
            )

        execute_processing_task(
            task=task,
            ledger=ledger_repository,
            attempt_id_factory=resolved_attempt_id_factory,
            started_at=ingest_input.ingested_at,
            invocation_id=f"source_file:{identity.document_id}:{idempotency_key}",
            operation=commit_representation,
            failure_for_exception=lambda exc: ProcessingFailure(
                code="local_file_processing_failure",
                failure_type=type(exc).__name__,
                stage=ProcessingStage.PERSISTENCE,
                safe_message=(
                    "Local-file processing failed before a complete closure was committed."
                ),
                retryable=False,
            ),
        )
    except Exception:
        _cleanup_archive_objects(archive_store, staged_objects)
        raise

    return AuthoritativeCaptureOutcome(
        source_id=outcome.source.id,
        document_id=document.id,
        representation_id=representation_id,
        provenance_activity_id=provenance_activity_id,
        raw_path=f"sources/raw/{outcome.raw_blob.id}.bin",
        extracted_text_path=f"documents/extracted/{document.id}.txt",
        created=outcome.created,
    )


def _require_complete_existing_closure(
    *,
    archive_store: ArchiveStore,
    ledger_repository: SourceFileLedger,
    raw_blob_id: str,
    raw_bytes: bytes,
    document_id: str,
    representation_id: str,
) -> None:
    try:
        archived_raw = archive_store.read_raw_source(raw_blob_id)
        archived_text = archive_store.read_document_text(document_id)
    except FileNotFoundError as exc:
        raise ValueError("INCOMPLETE_CLOSURE: required archive object is missing.") from exc
    if archived_raw != raw_bytes:
        raise ValueError("INCOMPLETE_CLOSURE: archived raw bytes disagree with capture input.")
    bundle = ledger_repository.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError("INCOMPLETE_CLOSURE: DocumentRepresentationBundle is missing.")
    text_view = next(
        (view for view in bundle.text_views if view.kind is TextViewKind.LOGICAL), None
    )
    if text_view is None or text_view.text != archived_text:
        raise ValueError("INCOMPLETE_CLOSURE: logical TextView disagrees with extracted text.")


def _require_repairable_capture_closure(
    *,
    archive_store: ArchiveStore,
    ledger_repository: SourceFileLedger,
    raw_blob_id: str,
    raw_bytes: bytes,
    document_id: str,
    representation_id: str,
) -> None:
    try:
        archived_raw = archive_store.read_raw_source(raw_blob_id)
        archive_store.read_document_text(document_id)
    except FileNotFoundError as exc:
        raise ValueError("INCOMPLETE_CLOSURE: required archive object is missing.") from exc
    if archived_raw != raw_bytes:
        raise ValueError("INCOMPLETE_CLOSURE: archived raw bytes disagree with capture input.")
    if ledger_repository.get_document_representation_bundle(representation_id) is not None:
        raise ValueError(
            "INCOMPLETE_CLOSURE: representation exists without its production provenance."
        )


def _local_file_request_fingerprint(source_key: str, content_sha256: str) -> str:
    return hashlib.sha256(f"local_file_v1:{source_key}:{content_sha256}".encode()).hexdigest()


def _cleanup_archive_objects(
    archive_store: ArchiveStore,
    staged_objects: list[StagedArchiveObject],
) -> None:
    for staged_object in reversed(staged_objects):
        archive_store.delete_object(staged_object.staged_relative_path)


def extract_source_title(filename: str, extracted_text: str) -> str:
    for line in extracted_text.splitlines():
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            if title:
                return title
    return Path(filename).stem


def infer_source_type(extracted_text: str) -> SourceType:
    for line in extracted_text.splitlines():
        if line.strip().lower() == "source type: synthetic news fixture":
            return SourceType.ARTICLE
    return SourceType.MANUAL_FILE


def parse_dateline_date(extracted_text: str) -> datetime | None:
    for line in extracted_text.splitlines():
        if not line.startswith("Dateline: "):
            continue
        _, _, dateline = line.partition(": ")
        _, separator, date_text = dateline.partition(", ")
        if not separator:
            raise ValueError("Dateline must include a location followed by a comma.")
        parts = date_text.split()
        if len(parts) != 3:
            raise ValueError("Dateline date must use 'Month D, YYYY' format.")
        month_name, day_text, year_text = parts
        month = MONTHS.get(month_name)
        if month is None:
            raise ValueError(f"Dateline month is not recognized: {month_name}")
        try:
            day = int(day_text.rstrip(","))
            year = int(year_text)
        except ValueError as exc:
            raise ValueError("Dateline day and year must be numeric.") from exc
        return datetime(year, month, day, tzinfo=UTC)
    return None
