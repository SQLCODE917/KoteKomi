import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore, SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import (
    AuthoritativeCaptureRequest,
    BuildIdentity,
    GroundedAssertionCandidate,
    GroundedCandidateBatchInput,
    GroundedEvidenceCandidate,
    GroundedOrganizationCandidate,
    ReviewProposedChangeInput,
    approve_proposed_change,
    canonical_record_json,
    commit_authoritative_capture,
    deterministic_representation_id,
    submit_grounded_candidate_batch,
    verify_evidence_target,
)
from kotekomi_domain import (
    AssertionEvidenceRole,
    ReviewStatus,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)
SOURCE_KEY = "final-proof-source"
PAYLOAD = b"# Final proof source\n\nAlpha supports the accepted assertion.\n"
TEXT = PAYLOAD.decode("utf-8")
EVIDENCE_TEXT = "Alpha supports the accepted assertion."
EVIDENCE_START = TEXT.index(EVIDENCE_TEXT)
BUILD_IDENTITY = BuildIdentity("final-proof", "final-proof", "a" * 64, "1")


@dataclass(frozen=True)
class AuthoritativeFixture:
    ledger_path: Path
    archive_path: Path
    ingest_request: AuthoritativeCaptureRequest
    evidence_target_id: str
    assertion_proposed_change_id: str
    assertion_id: str
    evidence_link_id: str


def _ingest_request() -> AuthoritativeCaptureRequest:
    return AuthoritativeCaptureRequest(
        local_file_path="final-proof.md",
        filename="final-proof.md",
        raw_bytes=PAYLOAD,
        ingested_at=NOW,
        build_identity=BUILD_IDENTITY,
        source_identity_key=SOURCE_KEY,
        idempotency_key="final-proof-v1",
    )


def _grounded_batch(
    *, source_id: str, document_id: str, representation_id: str, text_view_id: str
) -> GroundedCandidateBatchInput:
    return GroundedCandidateBatchInput(
        task_key="final-proof-grounded-task",
        source_id=source_id,
        document_id=document_id,
        representation_id=representation_id,
        model_name="bounded-final-proof-fixture",
        prompt_id="bounded-final-proof-task",
        validator_version="final-proof-v1",
        submitted_at=NOW,
        organizations=(
            GroundedOrganizationCandidate(
                local_id="subject_organization",
                name="Final Proof Org",
            ),
        ),
        evidence=(
            GroundedEvidenceCandidate(
                local_id="supporting_span",
                text_view_id=text_view_id,
                start_char=EVIDENCE_START,
                end_char=EVIDENCE_START + len(EVIDENCE_TEXT),
                exact_text=EVIDENCE_TEXT,
                node_ids=(f"nod_{representation_id.removeprefix('rep_')}_document",),
            ),
        ),
        assertions=(
            GroundedAssertionCandidate(
                local_id="reported_alpha",
                subject_organization_local_id="subject_organization",
                evidence_local_id="supporting_span",
                predicate="reported_alpha",
                object_value="Alpha",
            ),
        ),
    )


def _create_public_path_fixture(tmp_path: Path) -> AuthoritativeFixture:
    ledger_path = tmp_path / "ledger.db"
    archive_path = tmp_path / "archive"
    archive = LocalArchiveStore(archive_path)
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    ingest_request = _ingest_request()

    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = commit_authoritative_capture(ingest_request, archive, repository)
        bundle = repository.get_document_representation_bundle(capture.representation_id)
        assert bundle is not None
        assert bundle.text_views[0].text == TEXT
        batch = submit_grounded_candidate_batch(
            _grounded_batch(
                source_id=capture.source_id,
                document_id=capture.document_id,
                representation_id=bundle.representation.id,
                text_view_id=bundle.text_views[0].id,
            ),
            repository,
        )
        approve_proposed_change(
            ReviewProposedChangeInput(
                batch.proposed_change_ids_by_local_id["subject_organization"],
                "reviewer",
                NOW,
            ),
            repository,
        )
        review = approve_proposed_change(
            ReviewProposedChangeInput(
                batch.proposed_change_ids_by_local_id["reported_alpha"],
                "reviewer",
                NOW,
            ),
            repository,
        )
        assert review.accepted_record_id is not None

    return AuthoritativeFixture(
        ledger_path=ledger_path,
        archive_path=archive_path,
        ingest_request=ingest_request,
        evidence_target_id=batch.evidence_target_ids_by_local_id["supporting_span"],
        assertion_proposed_change_id=batch.proposed_change_ids_by_local_id["reported_alpha"],
        assertion_id=review.accepted_record_id,
        evidence_link_id=review.assertion_evidence_link_ids[0],
    )


def test_grounded_candidate_batch_rejects_evidence_disagreement_without_partial_records(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()

    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = commit_authoritative_capture(_ingest_request(), archive, repository)
        bundle = repository.get_document_representation_bundle(capture.representation_id)
        assert bundle is not None
        batch = _grounded_batch(
            source_id=capture.source_id,
            document_id=capture.document_id,
            representation_id=bundle.representation.id,
            text_view_id=bundle.text_views[0].id,
        )
        invalid_batch = replace(
            batch,
            evidence=(replace(batch.evidence[0], exact_text="not present"),),
        )

        with pytest.raises(ValueError, match="exact_text does not match"):
            submit_grounded_candidate_batch(invalid_batch, repository)

        assert repository.list_evidence_targets() == ()
        assert repository.list_evidence_validation_attempts() == ()
        assert repository.list_proposed_changes() == ()
        assert all(
            activity.activity_type != "grounded_candidate_batch_submitted"
            for activity in repository.list_provenance_activities()
        )


def test_final_proof_public_path_restarts_and_replays_archived_bytes(tmp_path: Path) -> None:
    fixture = _create_public_path_fixture(tmp_path)

    reopened_archive = LocalArchiveStore(fixture.archive_path)
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        assertion = repository.get_assertion(fixture.assertion_id)
        link = repository.get_assertion_evidence_link(fixture.evidence_link_id)
        evidence = repository.get_evidence_target(fixture.evidence_target_id)
        proposed_change = repository.get_proposed_change(fixture.assertion_proposed_change_id)
        assert assertion is not None
        assert link is not None
        assert evidence is not None
        assert proposed_change is not None
        assert proposed_change.review_status is ReviewStatus.APPROVED
        assert link.assertion_id == assertion.id
        assert link.evidence_target_id == evidence.id
        assert link.role is AssertionEvidenceRole.DIRECT_SUPPORT
        validation_attempt = repository.get_evidence_validation_attempt(link.validation_attempt_id)
        assert validation_attempt is not None
        assert verify_evidence_target(evidence, validation_attempt, repository).valid

        bundle = repository.get_document_representation_bundle(evidence.representation_id)
        assert bundle is not None
        document = repository.get_document(bundle.representation.document_id)
        assert document is not None
        resolutions = tuple(
            resolution
            for resolution in repository.list_capture_document_resolutions()
            if resolution.document_id == document.id
        )
        assert len(resolutions) == 1
        capture = repository.get_source_capture(resolutions[0].capture_id)
        assert capture is not None
        raw_blob = repository.get_raw_blob(capture.blob_id)
        assert raw_blob is not None
        source = repository.get_source(capture.source_id)
        assert source is not None
        attempts = repository.list_processing_attempts(
            bundle.representation.processing_task_fingerprint_id
        )
        assert len(attempts) == 1
        assert repository.get_processing_attempt_outcome(attempts[0].id) is not None

        archived_raw = reopened_archive.read_raw_source(raw_blob.id)
        assert archived_raw == fixture.ingest_request.raw_bytes
        assert archived_raw.decode("utf-8") == bundle.text_views[0].text
        assert raw_blob.digest == hashlib.sha256(archived_raw).hexdigest()
        assert document.content_sha256 == raw_blob.digest
        assert source.id == evidence.source_id
        assert bundle.representation.id == deterministic_representation_id(
            bundle.representation.processing_task_fingerprint_id
        )
        assert bundle.representation.canonical_output_digest == canonical_representation_digest(
            bundle.representation,
            text_views=bundle.text_views,
            nodes=bundle.nodes,
            edges=bundle.edges,
            source_regions=bundle.source_regions,
            quality_report=bundle.quality_report,
        )
        assert (
            evidence.text_view_digest
            == hashlib.sha256(bundle.text_views[0].text.encode("utf-8")).hexdigest()
        )
        assert validation_attempt.target_digest == canonical_evidence_target_digest(evidence)
        stored_assertion = repository.get_assertion(assertion.id)
        assert stored_assertion is not None
        assert canonical_record_json(assertion) == canonical_record_json(stored_assertion)
