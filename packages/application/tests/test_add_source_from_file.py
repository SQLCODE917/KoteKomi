import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_application import (
    ArchiveObject,
    ArchivePutDisposition,
    ArchivePutOutcome,
    AuthoritativeCaptureRequest,
    BuildIdentity,
    BundleCommitDisposition,
    BundleCommitOutcome,
    ProcessingTaskDisposition,
    StagedArchiveObject,
    commit_authoritative_capture,
)
from kotekomi_domain import (
    CaptureDocumentResolution,
    Document,
    DocumentEdge,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentRevisionRelation,
    ParseQualityReport,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingAttemptStatus,
    ProcessingTaskFingerprint,
    ProvenanceActivity,
    RawBlob,
    Source,
    SourceCapture,
    SourceRegion,
    SourceType,
    TextView,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "tests"
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
BUILD_IDENTITY = BuildIdentity("fixture", "fixture", "a" * 64, "1")
FIXTURE_TITLE = "Anthropic delayed model rollout after U.S. review raised cyber-safety concerns"


class FakeArchiveStore:
    def __init__(self) -> None:
        self.raw_writes: dict[str, bytes] = {}
        self.text_writes: dict[str, str] = {}
        self.staged_writes: dict[str, bytes] = {}
        self.deleted_paths: list[str] = []

    def initialize(self) -> None:
        return None

    def put_if_absent_or_identical(
        self, object_id: str, payload: bytes, expected_digest: str
    ) -> ArchivePutOutcome:
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            raise ValueError("Archive payload does not match expected digest.")
        existing = self.raw_writes.get(object_id)
        if existing is not None:
            if existing != payload:
                raise ValueError("Archive object conflicts with its expected digest.")
            return ArchivePutOutcome(
                ArchivePutDisposition.REUSED,
                ArchiveObject(f"sources/raw/{object_id}.bin", len(existing)),
            )
        self.raw_writes[object_id] = payload
        return ArchivePutOutcome(
            ArchivePutDisposition.CREATED,
            ArchiveObject(f"sources/raw/{object_id}.bin", len(payload)),
        )

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        if source_id in self.raw_writes:
            raise FileExistsError(source_id)
        self.raw_writes[source_id] = content
        return ArchiveObject(
            relative_path=f"sources/raw/{source_id}.bin",
            size_bytes=len(content),
        )

    def read_raw_source(self, source_id: str) -> bytes:
        try:
            return self.raw_writes[source_id]
        except KeyError as exc:
            raise FileNotFoundError(source_id) from exc

    def write_document_text(self, document_id: str, text: str) -> ArchiveObject:
        if document_id in self.text_writes:
            raise FileExistsError(document_id)
        self.text_writes[document_id] = text
        return ArchiveObject(
            relative_path=f"documents/extracted/{document_id}.txt",
            size_bytes=len(text.encode("utf-8")),
        )

    def read_document_text(self, document_id: str) -> str:
        try:
            return self.text_writes[document_id]
        except KeyError as exc:
            raise FileNotFoundError(document_id) from exc

    def read_briefing_markdown(self, briefing_id: str) -> str:
        raise NotImplementedError

    def read_briefing_citations_json(self, briefing_id: str) -> str:
        raise NotImplementedError

    def stage_raw_source(self, source_id: str, content: bytes) -> StagedArchiveObject:
        staged_path = f".staging/sources/raw/{source_id}.bin.tmp"
        self.staged_writes[staged_path] = content
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(
                relative_path=f"sources/raw/{source_id}.bin",
                size_bytes=len(content),
            ),
        )

    def stage_document_text(self, document_id: str, text: str) -> StagedArchiveObject:
        content = text.encode("utf-8")
        staged_path = f".staging/documents/extracted/{document_id}.txt.tmp"
        self.staged_writes[staged_path] = content
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(
                relative_path=f"documents/extracted/{document_id}.txt",
                size_bytes=len(content),
            ),
        )

    def stage_briefing_markdown(
        self,
        briefing_id: str,
        markdown: str,
    ) -> StagedArchiveObject:
        raise NotImplementedError

    def stage_briefing_citations_json(
        self,
        briefing_id: str,
        citations_json: str,
    ) -> StagedArchiveObject:
        raise NotImplementedError

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        content = self.staged_writes.pop(staged_object.staged_relative_path)
        if staged_object.final_object.relative_path.startswith("sources/raw/"):
            source_id = staged_object.final_object.relative_path.removeprefix(
                "sources/raw/"
            ).removesuffix(".bin")
            self.raw_writes[source_id] = content
        else:
            document_id = staged_object.final_object.relative_path.removeprefix(
                "documents/extracted/"
            ).removesuffix(".txt")
            self.text_writes[document_id] = content.decode("utf-8")
        return staged_object.final_object

    def delete_object(self, relative_path: str) -> None:
        self.deleted_paths.append(relative_path)
        self.staged_writes.pop(relative_path, None)
        if relative_path.startswith("sources/raw/"):
            source_id = relative_path.removeprefix("sources/raw/").removesuffix(".bin")
            self.raw_writes.pop(source_id, None)
        if relative_path.startswith("documents/extracted/"):
            document_id = relative_path.removeprefix("documents/extracted/").removesuffix(".txt")
            self.text_writes.pop(document_id, None)


class FakeLedgerRepository:
    def __init__(self, fail_on_save_document: bool = False) -> None:
        self.sources: dict[str, Source] = {}
        self.documents: dict[str, Document] = {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}
        self.raw_blobs: dict[str, RawBlob] = {}
        self.source_captures: dict[str, SourceCapture] = {}
        self.capture_document_resolutions: dict[str, CaptureDocumentResolution] = {}
        self.document_revision_relations: dict[str, DocumentRevisionRelation] = {}
        self.document_representations: dict[str, DocumentRepresentation] = {}
        self.text_views: dict[str, TextView] = {}
        self.document_nodes: dict[str, DocumentNode] = {}
        self.document_edges: dict[str, DocumentEdge] = {}
        self.source_regions: dict[str, SourceRegion] = {}
        self.parse_quality_reports: dict[str, ParseQualityReport] = {}
        self.processing_tasks: dict[str, ProcessingTaskFingerprint] = {}
        self.processing_attempts: dict[str, ProcessingAttempt] = {}
        self.processing_outcomes: dict[str, ProcessingAttemptOutcome] = {}
        self.fail_on_save_document = fail_on_save_document

    def get_source(self, record_id: str) -> Source | None:
        return self.sources.get(record_id)

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_raw_blob(self, record_id: str) -> RawBlob | None:
        return self.raw_blobs.get(record_id)

    def get_source_capture(self, record_id: str) -> SourceCapture | None:
        return self.source_captures.get(record_id)

    def get_capture_document_resolution(self, record_id: str) -> CaptureDocumentResolution | None:
        return self.capture_document_resolutions.get(record_id)

    def list_documents(self) -> tuple[Document, ...]:
        return tuple(self.documents.values())

    def list_documents_for_source(self, source_id: str) -> tuple[Document, ...]:
        return tuple(
            document for document in self.documents.values() if document.source_id == source_id
        )

    def find_document_by_provider_version(
        self, source_id: str, provider_version: str
    ) -> Document | None:
        return next(
            (
                document
                for document in self.documents.values()
                if document.source_id == source_id and document.provider_version == provider_version
            ),
            None,
        )

    def list_document_revision_relations(self) -> tuple[DocumentRevisionRelation, ...]:
        return tuple(self.document_revision_relations.values())

    def get_document_revision_relation(self, record_id: str) -> DocumentRevisionRelation | None:
        return self.document_revision_relations.get(record_id)

    def list_document_revision_relations_from(
        self, document_id: str
    ) -> tuple[DocumentRevisionRelation, ...]:
        return tuple(
            relation
            for relation in self.document_revision_relations.values()
            if relation.earlier_document_id == document_id
        )

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self.provenance_activities.get(record_id)

    def save_source(self, record: Source) -> None:
        self.sources[record.id] = record

    def save_raw_blob(self, record: RawBlob) -> None:
        self.raw_blobs[record.id] = record

    def save_source_capture(self, record: SourceCapture) -> None:
        self.source_captures[record.id] = record

    def save_capture_document_resolution(self, record: CaptureDocumentResolution) -> None:
        self.capture_document_resolutions[record.id] = record

    def save_document(self, record: Document) -> None:
        if self.fail_on_save_document:
            raise RuntimeError("simulated Ledger failure")
        self.documents[record.id] = record

    def save_document_revision_relation(self, record: DocumentRevisionRelation) -> None:
        self.document_revision_relations[record.id] = record

    def ensure_processing_task_fingerprint(
        self, record: ProcessingTaskFingerprint
    ) -> ProcessingTaskDisposition:
        existing = self.processing_tasks.get(record.id)
        if existing is None:
            self.processing_tasks[record.id] = record
            return ProcessingTaskDisposition.CREATED
        if existing != record:
            raise ValueError("processing task conflict")
        return ProcessingTaskDisposition.REUSED

    def append_processing_attempt(self, record: ProcessingAttempt) -> None:
        if record.id in self.processing_attempts:
            raise ValueError("processing attempt conflict")
        self.processing_attempts[record.id] = record

    def append_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        outcome_attempt_ids = {outcome.attempt_id for outcome in self.processing_outcomes.values()}
        if record.attempt_id in outcome_attempt_ids:
            raise ValueError("processing outcome conflict")
        self.processing_outcomes[record.id] = record

    def commit_processing_attempt_start(self) -> None:
        return None

    def record_failed_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        self.append_processing_attempt_outcome(record)

    def get_processing_attempt_outcome(self, attempt_id: str) -> ProcessingAttemptOutcome | None:
        return next(
            (
                outcome
                for outcome in self.processing_outcomes.values()
                if outcome.attempt_id == attempt_id
            ),
            None,
        )

    def list_processing_attempts(
        self, fingerprint_id: str, *, after: str | None = None, limit: int = 100
    ) -> tuple[ProcessingAttempt, ...]:
        attempts = tuple(
            attempt
            for attempt in self.processing_attempts.values()
            if attempt.task_fingerprint_id == fingerprint_id
        )
        if after is not None:
            attempts = tuple(attempt for attempt in attempts if attempt.id > after)
        return attempts[:limit]

    def save_document_representation(self, record: DocumentRepresentation) -> None:
        self.document_representations[record.id] = record

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        representation = self.document_representations.get(record_id)
        if representation is None:
            return None
        quality_report = next(
            (
                report
                for report in self.parse_quality_reports.values()
                if report.representation_id == record_id
            ),
            None,
        )
        if quality_report is None:
            return None
        return DocumentRepresentationBundle(
            representation=representation,
            text_views=tuple(
                view for view in self.text_views.values() if view.representation_id == record_id
            ),
            nodes=tuple(
                node for node in self.document_nodes.values() if node.representation_id == record_id
            ),
            edges=tuple(
                edge for edge in self.document_edges.values() if edge.representation_id == record_id
            ),
            source_regions=tuple(
                region
                for region in self.source_regions.values()
                if region.representation_id == record_id
            ),
            quality_report=quality_report,
        )

    def commit_document_representation_bundle(
        self,
        bundle: DocumentRepresentationBundle,
    ) -> BundleCommitOutcome:
        if bundle.representation.id in self.document_representations:
            return BundleCommitOutcome(
                BundleCommitDisposition.REUSED,
                bundle.representation.id,
            )
        self.document_representations[bundle.representation.id] = bundle.representation
        self.text_views.update({view.id: view for view in bundle.text_views})
        self.document_nodes.update({node.id: node for node in bundle.nodes})
        self.document_edges.update({edge.id: edge for edge in bundle.edges})
        self.source_regions.update({region.id: region for region in bundle.source_regions})
        self.parse_quality_reports[bundle.quality_report.id] = bundle.quality_report
        return BundleCommitOutcome(BundleCommitDisposition.CREATED, bundle.representation.id)

    def commit_document_representation_processing(
        self,
        *,
        bundle: DocumentRepresentationBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitOutcome:
        outcome = self.commit_document_representation_bundle(bundle)
        if outcome.disposition is BundleCommitDisposition.CREATED:
            self.save_provenance_activity(created_provenance_activity)
            self.append_processing_attempt_outcome(created_outcome)
        else:
            self.append_processing_attempt_outcome(reused_outcome)
        return outcome

    def save_text_view(self, record: TextView) -> None:
        self.text_views[record.id] = record

    def save_document_node(self, record: DocumentNode) -> None:
        self.document_nodes[record.id] = record

    def save_parse_quality_report(self, record: ParseQualityReport) -> None:
        self.parse_quality_reports[record.id] = record

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record


def test_commit_authoritative_capture_creates_source_document_and_provenance() -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()

    result = commit_authoritative_capture(
        AuthoritativeCaptureRequest(
            local_file_path=str(FIXTURE_PATH),
            filename=FIXTURE_PATH.name,
            raw_bytes=raw_bytes,
            ingested_at=NOW,
            build_identity=BUILD_IDENTITY,
        ),
        archive,
        ledger,
    )

    source = ledger.sources[result.source_id]
    document = ledger.documents[result.document_id]
    provenance = ledger.provenance_activities[result.provenance_activity_id]
    assert result.created is True
    assert source.canonical_identity_key == str(FIXTURE_PATH.resolve())
    assert source.source_type is SourceType.ARTICLE
    raw_blob = ledger.raw_blobs[next(iter(ledger.raw_blobs))]
    assert raw_blob.storage_locator == f"sources/raw/{raw_blob.id}.bin"
    assert result.raw_path == raw_blob.storage_locator
    assert result.extracted_text_path == f"documents/extracted/{result.document_id}.txt"
    assert document.content_sha256 == hashlib.sha256(raw_bytes).hexdigest()
    assert provenance.activity_type == "source_file_representation"
    assert provenance.agent == "kotekomi"
    assert provenance.input_ids == (
        result.document_id,
        ledger.document_representations[result.representation_id].processing_task_fingerprint_id,
    )
    assert provenance.output_ids == (
        result.representation_id,
        f"tvw_{result.representation_id.removeprefix('rep_')}_logical",
        f"nod_{result.representation_id.removeprefix('rep_')}_document",
        f"pqr_{result.representation_id.removeprefix('rep_')}_quality_v1",
    )
    capture_provenance = next(
        activity
        for activity in ledger.provenance_activities.values()
        if activity.activity_type == "source_file_capture"
    )
    assert capture_provenance.input_ids == (str(FIXTURE_PATH),)
    assert capture_provenance.output_ids == (
        result.source_id,
        raw_blob.id,
        next(iter(ledger.source_captures)),
        result.document_id,
    )
    representation = ledger.document_representations[result.representation_id]
    representation_key = result.representation_id.removeprefix("rep_")
    text_view = ledger.text_views[f"tvw_{representation_key}_logical"]
    root_node = ledger.document_nodes[f"nod_{representation_key}_document"]
    quality_report = ledger.parse_quality_reports[f"pqr_{representation_key}_quality_v1"]
    assert representation.document_id == result.document_id
    assert text_view.text == raw_bytes.decode("utf-8")
    assert root_node.text == text_view.text
    assert quality_report.analyzability.value == "acceptable"
    assert archive.staged_writes == {}


def test_commit_authoritative_capture_is_idempotent_after_records_exist() -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()
    ingest_input = AuthoritativeCaptureRequest(
        local_file_path=str(FIXTURE_PATH),
        filename=FIXTURE_PATH.name,
        raw_bytes=raw_bytes,
        ingested_at=NOW,
        build_identity=BUILD_IDENTITY,
    )

    first = commit_authoritative_capture(ingest_input, archive, ledger)
    second = commit_authoritative_capture(ingest_input, archive, ledger)

    assert first.created is True
    assert second.created is False
    assert first.source_id == second.source_id
    assert first.document_id == second.document_id
    assert len(archive.raw_writes) == 1
    assert len(archive.text_writes) == 1
    assert len(ledger.sources) == 1
    assert len(ledger.documents) == 1
    assert len(ledger.document_representations) == 1
    assert len(ledger.text_views) == 1
    assert len(ledger.document_nodes) == 1
    assert len(ledger.parse_quality_reports) == 1
    assert len(ledger.provenance_activities) == 2


def test_commit_authoritative_capture_creates_new_representation_for_changed_build_identity() -> (
    None
):
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()
    first_request = AuthoritativeCaptureRequest(
        local_file_path=str(FIXTURE_PATH),
        filename=FIXTURE_PATH.name,
        raw_bytes=raw_bytes,
        ingested_at=NOW,
        build_identity=BUILD_IDENTITY,
    )
    second_request = AuthoritativeCaptureRequest(
        local_file_path=str(FIXTURE_PATH),
        filename=FIXTURE_PATH.name,
        raw_bytes=raw_bytes,
        ingested_at=NOW,
        build_identity=BuildIdentity("fixture", "changed-revision", "a" * 64, "1"),
    )

    first = commit_authoritative_capture(first_request, archive, ledger)
    first_bundle = ledger.get_document_representation_bundle(first.representation_id)
    first_provenance = ledger.provenance_activities[first.provenance_activity_id]
    second = commit_authoritative_capture(second_request, archive, ledger)

    assert first.source_id == second.source_id
    assert first.document_id == second.document_id
    assert first.representation_id != second.representation_id
    assert first_bundle == ledger.get_document_representation_bundle(first.representation_id)
    assert first_provenance == ledger.provenance_activities[first.provenance_activity_id]
    assert len(ledger.raw_blobs) == 1
    assert len(ledger.source_captures) == 1
    assert len(ledger.processing_tasks) == 2
    assert len(ledger.document_representations) == 2
    assert len(ledger.processing_attempts) == 2
    assert len(ledger.processing_outcomes) == 2
    assert len(ledger.provenance_activities) == 3
    assert {activity.activity_type for activity in ledger.provenance_activities.values()} == {
        "source_file_capture",
        "source_file_representation",
    }
    assert (
        sum(
            activity.activity_type == "source_file_representation"
            for activity in ledger.provenance_activities.values()
        )
        == 2
    )
    assert {outcome.status for outcome in ledger.processing_outcomes.values()} == {
        ProcessingAttemptStatus.SUCCEEDED
    }


def test_commit_authoritative_capture_records_failed_attempt_for_incomplete_reuse_closure() -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()
    ingest_input = AuthoritativeCaptureRequest(
        local_file_path=str(FIXTURE_PATH),
        filename=FIXTURE_PATH.name,
        raw_bytes=raw_bytes,
        ingested_at=NOW,
        build_identity=BUILD_IDENTITY,
    )

    result = commit_authoritative_capture(ingest_input, archive, ledger)
    archive.text_writes.pop(result.document_id)

    with pytest.raises(ValueError, match="INCOMPLETE_CLOSURE"):
        commit_authoritative_capture(ingest_input, archive, ledger)

    assert len(ledger.processing_attempts) == 2
    assert len(ledger.processing_outcomes) == 2
    latest_outcome = tuple(ledger.processing_outcomes.values())[-1]
    assert latest_outcome.status is ProcessingAttemptStatus.FAILED
    assert latest_outcome.failure is not None
    assert latest_outcome.failure.code == "incomplete_closure"


def test_commit_authoritative_capture_rejects_unsupported_suffix() -> None:
    with pytest.raises(ValueError, match="Unsupported Source file suffix"):
        commit_authoritative_capture(
            AuthoritativeCaptureRequest(
                local_file_path="fixture.pdf",
                filename="fixture.pdf",
                raw_bytes=b"%PDF",
                ingested_at=NOW,
                build_identity=BUILD_IDENTITY,
            ),
            FakeArchiveStore(),
            FakeLedgerRepository(),
        )


def test_commit_authoritative_capture_rejects_invalid_build_identity_before_mutation() -> None:
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()

    with pytest.raises(ValueError, match="artifact_digest"):
        commit_authoritative_capture(
            AuthoritativeCaptureRequest(
                local_file_path="notes.txt",
                filename="notes.txt",
                raw_bytes=b"note",
                ingested_at=NOW,
                build_identity=BuildIdentity("fixture", "fixture", "not-a-digest", "1"),
            ),
            archive,
            ledger,
        )

    assert archive.raw_writes == {}
    assert archive.text_writes == {}
    assert ledger.sources == {}
    assert ledger.documents == {}


def test_commit_authoritative_capture_defaults_text_file_metadata() -> None:
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()

    result = commit_authoritative_capture(
        AuthoritativeCaptureRequest(
            local_file_path="notes.txt",
            filename="notes.txt",
            raw_bytes=b"plain text note",
            ingested_at=NOW,
            build_identity=BUILD_IDENTITY,
        ),
        archive,
        ledger,
    )

    source = ledger.sources[result.source_id]
    assert source.canonical_identity_key == str(Path("notes.txt").resolve())
    assert source.source_type is SourceType.MANUAL_FILE


def test_commit_authoritative_capture_rejects_malformed_dateline() -> None:
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()

    with pytest.raises(ValueError, match="Dateline must include a location"):
        commit_authoritative_capture(
            AuthoritativeCaptureRequest(
                local_file_path="bad-dateline.md",
                filename="bad-dateline.md",
                raw_bytes=b"# Bad Dateline\n\nDateline: July 2 2026\n\nBody.",
                ingested_at=NOW,
                build_identity=BUILD_IDENTITY,
            ),
            archive,
            ledger,
        )

    assert archive.raw_writes == {}
    assert archive.text_writes == {}
    assert archive.staged_writes == {}
    assert ledger.sources == {}
    assert ledger.documents == {}
    assert ledger.provenance_activities == {}


def test_commit_authoritative_capture_rejects_changed_bytes_without_revision_decision() -> None:
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository()
    commit_authoritative_capture(
        AuthoritativeCaptureRequest(
            local_file_path="notes.txt",
            filename="notes.txt",
            raw_bytes=b"original note",
            ingested_at=NOW,
            build_identity=BUILD_IDENTITY,
        ),
        archive,
        ledger,
    )
    with pytest.raises(ValueError, match="UNCLASSIFIED_REVISION"):
        commit_authoritative_capture(
            AuthoritativeCaptureRequest(
                local_file_path="notes.txt",
                filename="notes.txt",
                raw_bytes=b"updated note",
                ingested_at=NOW.replace(hour=13),
                build_identity=BUILD_IDENTITY,
            ),
            archive,
            ledger,
        )

    assert len(ledger.sources) == 1
    assert len(ledger.raw_blobs) == len(ledger.source_captures) == len(ledger.documents) == 1
    assert len(ledger.document_revision_relations) == 0
    assert archive.read_raw_source(next(iter(ledger.raw_blobs))) == b"original note"


def test_commit_authoritative_capture_preserves_promoted_archive_objects_after_ledger_failure() -> (
    None
):
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository(fail_on_save_document=True)

    with pytest.raises(RuntimeError, match="simulated Ledger failure"):
        commit_authoritative_capture(
            AuthoritativeCaptureRequest(
                local_file_path=str(FIXTURE_PATH),
                filename=FIXTURE_PATH.name,
                raw_bytes=raw_bytes,
                ingested_at=NOW,
                build_identity=BUILD_IDENTITY,
            ),
            archive,
            ledger,
        )

    assert len(archive.raw_writes) == 1
    assert len(archive.text_writes) == 1
    assert archive.staged_writes == {}
    assert all(path.startswith(".staging/") for path in archive.deleted_paths)
    assert ledger.documents == {}
    assert ledger.provenance_activities == {}


def test_commit_authoritative_capture_repairs_capture_then_completes_representation() -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    archive = FakeArchiveStore()
    ledger = FakeLedgerRepository(fail_on_save_document=True)
    request = AuthoritativeCaptureRequest(
        local_file_path=str(FIXTURE_PATH),
        filename=FIXTURE_PATH.name,
        raw_bytes=raw_bytes,
        ingested_at=NOW,
        build_identity=BUILD_IDENTITY,
    )

    with pytest.raises(RuntimeError, match="simulated Ledger failure"):
        commit_authoritative_capture(request, archive, ledger)

    ledger.fail_on_save_document = False
    repaired = commit_authoritative_capture(request, archive, ledger)

    assert repaired.created is False
    assert len(ledger.documents) == 1
    assert len(ledger.document_representations) == 1
    assert len(ledger.provenance_activities) == 2
