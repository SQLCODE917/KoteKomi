import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import (
    ImmutableRecordConflict,
    LocalArchiveStore,
    NonDeterministicParserOutputConflict,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    CaptureRequest,
    EvidenceValidationInput,
    RepresentationFingerprintInput,
    ReviewProposedChangeInput,
    SourceIdentityHint,
    StableSourceIdentityPolicy,
    approve_proposed_change,
    canonical_record_json,
    capture_identity,
    capture_source,
    deterministic_representation_id,
    validate_evidence_target,
    verify_evidence_target,
)
from kotekomi_domain import (
    AssertionEvidenceRole,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentRevisionType,
    DocumentVersionKind,
    EvidenceTarget,
    Organization,
    ParseQualityReport,
    ProposedChange,
    RepresentationAnalyzability,
    ReviewStatus,
    SourceType,
    TextView,
    TextViewKind,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)
SOURCE_KEY = "final-proof-source"
PAYLOAD = b"Alpha supports the accepted assertion."
TEXT = PAYLOAD.decode("utf-8")
PARSER_CONFIG_DIGEST = hashlib.sha256(b"final_proof_v1").hexdigest()


@dataclass(frozen=True)
class AuthoritativeFixture:
    ledger_path: Path
    archive: LocalArchiveStore
    request: CaptureRequest
    representation: DocumentRepresentationBundle
    evidence: EvidenceTarget
    assertion_id: str
    evidence_link_id: str


def _request(
    payload: bytes,
    *,
    idempotency_key: str,
    provider_version: str,
    revision_of_document_id: str | None = None,
    revision_type: DocumentRevisionType | None = None,
) -> CaptureRequest:
    digest = hashlib.sha256(payload).hexdigest()
    return CaptureRequest(
        identity_hint=SourceIdentityHint(
            source_type=SourceType.ARTICLE,
            title="Final proof source",
            stable_key=SOURCE_KEY,
            uri="file:///final-proof.txt",
        ),
        payload=payload,
        media_type="text/plain",
        storage_locator=f"sources/raw/blb_{digest}.bin",
        idempotency_key=idempotency_key,
        retrieval_method="final_proof_fixture",
        requested_uri="file:///final-proof.txt",
        canonical_uri="file:///final-proof.txt",
        provider_item_id="final-proof-item",
        provider_version=provider_version,
        version_kind=(
            DocumentVersionKind.ORIGINAL
            if revision_of_document_id is None
            else DocumentVersionKind.UPDATE
        ),
        publication_time=NOW,
        provider_update_time=NOW,
        captured_at=NOW,
        transaction_time=NOW,
        rights_profile_id="final-proof-rights",
        embargo_until=None,
        request_metadata={"fixture": "authoritative_commit_boundary"},
        response_metadata={"etag": provider_version},
        extracted_text_locator=f"documents/extracted/doc_{digest[:24]}.txt",
        revision_of_document_id=revision_of_document_id,
        revision_type=revision_type,
    )


def _bundle(
    *,
    document_id: str,
    input_blob_digest: str,
    parser_config_digest: str = PARSER_CONFIG_DIGEST,
    text: str = TEXT,
) -> DocumentRepresentationBundle:
    representation_id = deterministic_representation_id(
        RepresentationFingerprintInput(
            document_id=document_id,
            input_blob_digest=input_blob_digest,
            parser_name="final_proof_parser",
            parser_version="1",
            parser_config_digest=parser_config_digest,
            code_revision="final-proof",
            representation_schema_version="1",
        )
    )
    representation_key = representation_id.removeprefix("rep_")
    text_view = TextView(
        id=f"tvw_{representation_key}_logical",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id=f"nod_{representation_key}_document",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
        text=text,
    )
    quality_report = ParseQualityReport(
        id=f"pqr_{representation_key}_quality_v1",
        representation_id=representation_id,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document_id,
        parser_name="final_proof_parser",
        parser_version="1",
        parser_config_digest=parser_config_digest,
        code_revision="final-proof",
        input_blob_digest=input_blob_digest,
        canonical_output_digest="0" * 64,
        created_at=NOW,
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


def _validated_evidence(
    *,
    source_id: str,
    document_id: str,
    bundle: DocumentRepresentationBundle,
) -> EvidenceTarget:
    text_view = bundle.text_views[0]
    node = bundle.nodes[0]
    return EvidenceTarget(
        id="evt_final_proof",
        source_id=source_id,
        document_id=document_id,
        exact_text=TEXT,
        representation_id=bundle.representation.id,
        text_view_id=text_view.id,
        text_view_digest=text_view.content_digest,
        start_char=0,
        end_char=len(TEXT),
        node_ids=(node.id,),
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
                "evidence_target_ids": ["evt_final_proof"],
                "provenance_activity_ids": [],
            },
            "evidence": {
                "selector_type": "exact_text",
                "exact_text": TEXT,
                "source_id": source_id,
                "document_id": document_id,
            },
            "evidence_links": [
                {
                    "evidence_target_id": "evt_final_proof",
                    "validation_attempt_id": "eva_final_proof",
                    "role": "direct_support",
                    "polarity": "supports",
                    "necessity": "required",
                }
            ],
        },
        source_id=source_id,
        document_id=document_id,
        model_name="final-proof-model",
        prompt_id="final-proof-prompt",
        provenance_activity_id="prv_final_proof_model",
        created_at=NOW,
        updated_at=NOW,
    )


def _seed_authoritative_fixture(tmp_path: Path) -> AuthoritativeFixture:
    ledger_path = tmp_path / "ledger.db"
    archive = LocalArchiveStore(tmp_path / "archive")
    archive.initialize()
    SQLiteLedgerInitializer(ledger_path).initialize()
    request = _request(PAYLOAD, idempotency_key="final-proof-v1", provider_version="v1")
    identity = capture_identity(request, StableSourceIdentityPolicy())
    archive.write_raw_source(identity.raw_blob_id, request.payload)
    with sqlite_ledger_transaction(ledger_path) as repository:
        capture = capture_source(request, repository, StableSourceIdentityPolicy())
        representation = _bundle(
            document_id=capture.document.id,
            input_blob_digest=capture.raw_blob.digest,
        )
        repository.commit_document_representation_bundle(representation)
        repository.save_organization(Organization(id="org_final_proof", name="Final Proof Org"))
        evidence = _validated_evidence(
            source_id=capture.source.id,
            document_id=capture.document.id,
            bundle=representation,
        )
        repository.save_evidence_target(evidence)
        validation = validate_evidence_target(
            EvidenceValidationInput(evidence.id, "eva_final_proof", "final-proof-v1", NOW),
            repository,
        )
        proposed_change = _assertion_proposed_change(capture.source.id, capture.document.id)
        repository.save_proposed_change(proposed_change)
        review = approve_proposed_change(
            ReviewProposedChangeInput("pcg_final_proof", "reviewer", NOW), repository
        )
    return AuthoritativeFixture(
        ledger_path=ledger_path,
        archive=archive,
        request=request,
        representation=representation,
        evidence=validation.evidence_target,
        assertion_id="ast_final_proof",
        evidence_link_id=review.assertion_evidence_link_ids[0],
    )


def _alter_evidence(evidence: EvidenceTarget, **changes: object) -> EvidenceTarget:
    return evidence.model_copy(update=changes)


def test_final_proof_reopens_and_replays_the_complete_authoritative_chain(tmp_path: Path) -> None:
    fixture = _seed_authoritative_fixture(tmp_path)

    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        assertion = repository.get_assertion(fixture.assertion_id)
        link = repository.get_assertion_evidence_link(fixture.evidence_link_id)
        evidence = repository.get_evidence_target(fixture.evidence.id)
        assert assertion is not None
        assert link is not None
        assert evidence is not None
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
        capture = repository.get_source_capture(document.created_from_capture_id or "")
        assert capture is not None
        raw_blob = repository.get_raw_blob(capture.blob_id)
        assert raw_blob is not None
        assert fixture.archive.read_raw_source(raw_blob.id) == fixture.request.payload
        assert raw_blob.digest == hashlib.sha256(fixture.request.payload).hexdigest()
        assert document.content_sha256 == raw_blob.digest
        assert bundle.representation.id == deterministic_representation_id(
            RepresentationFingerprintInput(
                document_id=document.id,
                input_blob_digest=raw_blob.digest,
                parser_name="final_proof_parser",
                parser_version="1",
                parser_config_digest=PARSER_CONFIG_DIGEST,
                code_revision="final-proof",
                representation_schema_version="1",
            )
        )
        assert bundle.representation.canonical_output_digest == canonical_representation_digest(
            bundle.representation,
            text_views=bundle.text_views,
            nodes=bundle.nodes,
            edges=bundle.edges,
            source_regions=bundle.source_regions,
            quality_report=bundle.quality_report,
        )
        assert evidence.text_view_digest == hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
        assert validation_attempt.target_digest == canonical_evidence_target_digest(evidence)
        stored_assertion = repository.get_assertion(assertion.id)
        assert stored_assertion is not None
        assert canonical_record_json(assertion) == canonical_record_json(stored_assertion)


def test_final_proof_raw_byte_mutation_creates_a_new_versioned_artifact(tmp_path: Path) -> None:
    fixture = _seed_authoritative_fixture(tmp_path)
    updated_payload = b"Beta supports the accepted assertion."
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        original_document = repository.get_document(fixture.evidence.document_id)
        assert original_document is not None
        update_request = _request(
            updated_payload,
            idempotency_key="final-proof-v2",
            provider_version="v2",
            revision_of_document_id=original_document.id,
            revision_type=DocumentRevisionType.UPDATES,
        )
        update_identity = capture_identity(update_request, StableSourceIdentityPolicy())
        fixture.archive.write_raw_source(update_identity.raw_blob_id, updated_payload)
        update = capture_source(update_request, repository, StableSourceIdentityPolicy())
        assert update.document.id != original_document.id
        assert update.revision_relation is not None
        assert repository.get_document(original_document.id) == original_document
    assert fixture.archive.read_raw_source("blb_" + hashlib.sha256(PAYLOAD).hexdigest()) == PAYLOAD


def test_final_proof_parser_configuration_mutation_creates_a_new_representation(
    tmp_path: Path,
) -> None:
    fixture = _seed_authoritative_fixture(tmp_path)
    changed_config = hashlib.sha256(b"final_proof_v2").hexdigest()
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        changed = _bundle(
            document_id=fixture.evidence.document_id,
            input_blob_digest=hashlib.sha256(PAYLOAD).hexdigest(),
            parser_config_digest=changed_config,
        )
        outcome = repository.commit_document_representation_bundle(changed)
        assert outcome.representation_id != fixture.representation.representation.id
        assert repository.get_document_representation_bundle(
            fixture.representation.representation.id
        ) == fixture.representation


def test_final_proof_representation_node_text_mutation_fails_without_history_change(
    tmp_path: Path,
) -> None:
    fixture = _seed_authoritative_fixture(tmp_path)
    changed_output = _bundle(
        document_id=fixture.evidence.document_id,
        input_blob_digest=hashlib.sha256(PAYLOAD).hexdigest(),
        text="Changed parser output.",
    )
    with pytest.raises(NonDeterministicParserOutputConflict):
        with sqlite_ledger_transaction(fixture.ledger_path) as repository:
            repository.commit_document_representation_bundle(changed_output)
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        assert repository.get_document_representation_bundle(
            fixture.representation.representation.id
        ) == fixture.representation


@pytest.mark.parametrize(
    ("changes", "expected_error"),
    [
        ({"text_view_digest": "0" * 64}, "EvidenceValidationAttempt target_digest is stale"),
        ({"start_char": 1}, "EvidenceValidationAttempt target_digest is stale"),
        ({"prefix_text": "wrong"}, "EvidenceValidationAttempt target_digest is stale"),
    ],
)
def test_final_proof_evidence_selector_mutations_fail_replay(
    tmp_path: Path,
    changes: dict[str, object],
    expected_error: str,
) -> None:
    fixture = _seed_authoritative_fixture(tmp_path)
    mutated = _alter_evidence(fixture.evidence, **changes)
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        validation_attempt = repository.get_evidence_validation_attempt("eva_final_proof")
        assert validation_attempt is not None
        replay = verify_evidence_target(mutated, validation_attempt, repository)
        assert replay.valid is False
        assert replay.error_message is not None
        assert expected_error in replay.error_message
        assert repository.get_evidence_target(fixture.evidence.id) == fixture.evidence


def test_final_proof_evidence_role_mutation_is_an_immutable_conflict(tmp_path: Path) -> None:
    fixture = _seed_authoritative_fixture(tmp_path)
    with pytest.raises(ImmutableRecordConflict):
        with sqlite_ledger_transaction(fixture.ledger_path) as repository:
            link = repository.get_assertion_evidence_link(fixture.evidence_link_id)
            assert link is not None
            repository.save_assertion_evidence_link(
                link.model_copy(update={"role": AssertionEvidenceRole.BACKGROUND})
            )
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        link = repository.get_assertion_evidence_link(fixture.evidence_link_id)
        assert link is not None
        assert link.role is AssertionEvidenceRole.DIRECT_SUPPORT


def test_final_proof_idempotency_input_mutation_fails_without_new_records(tmp_path: Path) -> None:
    fixture = _seed_authoritative_fixture(tmp_path)
    conflicting_request = _request(
        b"Conflicting retry bytes.",
        idempotency_key=fixture.request.idempotency_key,
        provider_version="v2",
    )
    with pytest.raises(ValueError, match="Capture idempotency conflict"):
        with sqlite_ledger_transaction(fixture.ledger_path) as repository:
            capture_source(conflicting_request, repository, StableSourceIdentityPolicy())
    with sqlite_ledger_transaction(fixture.ledger_path) as repository:
        assert len(repository.list_documents()) == 1
        assert len(repository.list_source_captures()) == 1
