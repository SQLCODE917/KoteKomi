import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters import LocalArchiveStore, SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import (
    AuthoritativeCaptureRequest,
    BuildIdentity,
    EvidenceValidationInput,
    ReviewProposedChangeInput,
    approve_proposed_change,
    canonical_record_json,
    commit_authoritative_capture,
    deterministic_representation_id,
    validate_evidence_target,
    verify_evidence_target,
)
from kotekomi_domain import (
    AssertionEvidenceRole,
    EvidenceTarget,
    Organization,
    ProposedChange,
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
    evidence: EvidenceTarget
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


def _evidence_target(
    *, source_id: str, document_id: str, representation_id: str, text_view_id: str
) -> EvidenceTarget:
    return EvidenceTarget(
        id="etg_final_proof",
        source_id=source_id,
        document_id=document_id,
        exact_text=EVIDENCE_TEXT,
        representation_id=representation_id,
        text_view_id=text_view_id,
        text_view_digest=hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        start_char=EVIDENCE_START,
        end_char=EVIDENCE_START + len(EVIDENCE_TEXT),
        node_ids=(f"nod_{representation_id.removeprefix('rep_')}_document",),
        normalization_policy="utf8_identity_v1",
    )


def _assertion_proposed_change(source_id: str, document_id: str) -> ProposedChange:
    return ProposedChange(
        id="pcg_final_proof",
        review_status=ReviewStatus.PENDING,
        proposed_json={
            "record_type": "Assertion",
            "stable_label": "final_proof_assertion",
            "record": {
                "id": "ast_final_proof",
                "assertion_type": "source_claim",
                "epistemic_scope": "source_report",
                "subject_entity_id": "org_final_proof",
                "predicate": "reported_alpha",
                "object_value": "Alpha",
                "status": "proposed",
                "source_authority": "secondary",
                "attribution_basis": "reported_by_source",
                "source_ids": [source_id],
                "evidence_target_ids": ["etg_final_proof"],
                "provenance_activity_ids": [],
            },
            "evidence_links": [
                {
                    "evidence_target_id": "etg_final_proof",
                    "validation_attempt_id": "eva_final_proof",
                    "role": "direct_support",
                    "polarity": "supports",
                    "necessity": "required",
                }
            ],
        },
        source_id=source_id,
        document_id=document_id,
        model_name="bounded-final-proof-fixture",
        prompt_id="bounded-final-proof-task",
        provenance_activity_id="prv_final_proof_model",
        created_at=NOW,
        updated_at=NOW,
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
        repository.save_organization(Organization(id="org_final_proof", name="Final Proof Org"))
        evidence = _evidence_target(
            source_id=capture.source_id,
            document_id=capture.document_id,
            representation_id=bundle.representation.id,
            text_view_id=bundle.text_views[0].id,
        )
        repository.save_evidence_target(evidence)
        validation = validate_evidence_target(
            EvidenceValidationInput(evidence.id, "eva_final_proof", "final-proof-v1", NOW),
            repository,
        )
        assert validation.valid
        repository.save_proposed_change(
            _assertion_proposed_change(capture.source_id, capture.document_id)
        )
        review = approve_proposed_change(
            ReviewProposedChangeInput("pcg_final_proof", "reviewer", NOW), repository
        )

    return AuthoritativeFixture(
        ledger_path=ledger_path,
        archive_path=archive_path,
        ingest_request=ingest_request,
        evidence=evidence,
        assertion_id="ast_final_proof",
        evidence_link_id=review.assertion_evidence_link_ids[0],
    )


def test_final_proof_public_path_restarts_and_replays_archived_bytes(tmp_path: Path) -> None:
    fixture = _create_public_path_fixture(tmp_path)

    reopened_archive = LocalArchiveStore(fixture.archive_path)
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        assertion = repository.get_assertion(fixture.assertion_id)
        link = repository.get_assertion_evidence_link(fixture.evidence_link_id)
        evidence = repository.get_evidence_target(fixture.evidence.id)
        proposed_change = repository.get_proposed_change("pcg_final_proof")
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
        archived_text = reopened_archive.read_document_text(document.id)
        assert archived_raw == fixture.ingest_request.raw_bytes
        assert archived_raw.decode("utf-8") == archived_text == bundle.text_views[0].text
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
            evidence.text_view_digest == hashlib.sha256(archived_text.encode("utf-8")).hexdigest()
        )
        assert validation_attempt.target_digest == canonical_evidence_target_digest(evidence)
        stored_assertion = repository.get_assertion(assertion.id)
        assert stored_assertion is not None
        assert canonical_record_json(assertion) == canonical_record_json(stored_assertion)
