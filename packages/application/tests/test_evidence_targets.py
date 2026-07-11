from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    EvidenceValidationInput,
    validate_evidence_target,
    verify_evidence_target,
)
from kotekomi_domain import (
    Assertion,
    AssertionEvidenceLink,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EpistemicScope,
    EvidenceTarget,
    EvidenceValidationAttempt,
    ParseQualityReport,
    ProvenanceActivity,
    RepresentationAnalyzability,
    SourceAuthority,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)
TEXT = "Alpha. Alpha."
TEXT_DIGEST = "77d913272bb8bdba48d318de4a6a4b033dace9770d8cd967b09285d1876449a4"


class FakeEvidenceLedger:
    def __init__(
        self, bundle: DocumentRepresentationBundle, evidence_target: EvidenceTarget
    ) -> None:
        self.bundle = bundle
        self.documents = {
            "doc_example": Document(
                id="doc_example",
                source_id="src_example",
                content_sha256="a" * 64,
            )
        }
        self.evidence_targets = {evidence_target.id: evidence_target}
        self.validation_attempts: dict[str, EvidenceValidationAttempt] = {}
        self.assertions = {
            "ast_alpha": Assertion(
                id="ast_alpha",
                assertion_type=AssertionType.SOURCE_CLAIM,
                epistemic_scope=EpistemicScope.SOURCE_REPORT,
                subject_entity_id="org_example",
                predicate="reported_alpha",
                object_value="Alpha",
                status=AssertionStatus.REPORTED,
                source_authority=SourceAuthority.SECONDARY,
                attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
                source_ids=("src_example",),
                evidence_target_ids=(evidence_target.id,),
                provenance_activity_ids=("prv_review",),
            )
        }
        self.provenance_activities = {
            "prv_review": ProvenanceActivity(
                id="prv_review",
                activity_type="review",
                agent="analyst",
                occurred_at=NOW,
            )
        }
        self.links: dict[str, AssertionEvidenceLink] = {}

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.evidence_targets.get(record_id)

    def save_evidence_target(self, record: EvidenceTarget) -> None:
        self.evidence_targets[record.id] = record

    def get_evidence_validation_attempt(self, record_id: str) -> EvidenceValidationAttempt | None:
        return self.validation_attempts.get(record_id)

    def save_evidence_validation_attempt(self, record: EvidenceValidationAttempt) -> None:
        self.validation_attempts[record.id] = record

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_assertion(self, record_id: str) -> Assertion | None:
        return self.assertions.get(record_id)

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self.provenance_activities.get(record_id)

    def get_assertion_evidence_link(self, record_id: str) -> AssertionEvidenceLink | None:
        return self.links.get(record_id)

    def save_assertion_evidence_link(self, record: AssertionEvidenceLink) -> None:
        self.links[record.id] = record


def _bundle() -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_example",
        representation_id="rep_example",
        kind=TextViewKind.LOGICAL,
        content_digest=TEXT_DIGEST,
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )
    node = DocumentNode(
        id="nod_example",
        representation_id="rep_example",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(TEXT),
        text=TEXT,
    )
    quality_report = ParseQualityReport(
        id="pqr_example",
        representation_id="rep_example",
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_example",
        document_id="doc_example",
        parser_name="test",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_fixture",
        input_blob_digest="b" * 64,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(node,),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(node,),
        quality_report=quality_report,
    )


def _evidence_target(*, prefix_text: str = "") -> EvidenceTarget:
    return EvidenceTarget(
        id="etg_alpha",
        source_id="src_example",
        document_id="doc_example",
        exact_text="Alpha",
        prefix_text=prefix_text,
        suffix_text=". Alpha.",
        representation_id="rep_example",
        text_view_id="tvw_example",
        text_view_digest=TEXT_DIGEST,
        start_char=0,
        end_char=5,
        node_ids=("nod_example",),
        normalization_policy="utf8_identity_v1",
        created_at=NOW,
    )


def test_validate_evidence_target_pins_one_repeated_text_occurrence() -> None:
    ledger = FakeEvidenceLedger(_bundle(), _evidence_target())

    result = validate_evidence_target(
        EvidenceValidationInput(
            evidence_target_id="etg_alpha",
            attempt_id="eva_success",
            validator_version="1",
            validated_at=NOW,
        ),
        ledger,
    )

    assert result.valid is True
    assert result.attempt.status.value == "succeeded"
    assert ledger.get_evidence_target("etg_alpha") == result.evidence_target


def test_validate_evidence_target_fails_closed_when_context_disagrees() -> None:
    ledger = FakeEvidenceLedger(_bundle(), _evidence_target(prefix_text="not present"))

    result = validate_evidence_target(
        EvidenceValidationInput(
            evidence_target_id="etg_alpha",
            attempt_id="eva_failed",
            validator_version="1",
            validated_at=NOW,
        ),
        ledger,
    )

    assert result.valid is False
    assert result.error_message == "EvidenceTarget prefix selector does not match its TextView."
    assert result.attempt.status.value == "failed"


def test_validate_evidence_target_appends_a_new_attempt_for_each_replay() -> None:
    ledger = FakeEvidenceLedger(_bundle(), _evidence_target())
    first = validate_evidence_target(
        EvidenceValidationInput("etg_alpha", "eva_first", "1", NOW),
        ledger,
    )
    second = validate_evidence_target(
        EvidenceValidationInput("etg_alpha", "eva_second", "2", NOW),
        ledger,
    )

    assert first.valid and second.valid
    assert first.attempt.id != second.attempt.id
    assert tuple(ledger.validation_attempts) == ("eva_first", "eva_second")


def test_verify_evidence_target_replays_a_validated_target_without_mutating_it() -> None:
    ledger = FakeEvidenceLedger(_bundle(), _evidence_target())
    validation = validate_evidence_target(
        EvidenceValidationInput("etg_alpha", "eva_success", "1", NOW),
        ledger,
    )
    validated = validation.evidence_target

    replay = verify_evidence_target(validated, validation.attempt, ledger)

    assert replay.valid is True
    assert ledger.get_evidence_target(validated.id) == validated


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("stale_text_view", "EvidenceValidationAttempt target_digest is stale."),
        ("selector_disagreement", "EvidenceValidationAttempt target_digest is stale."),
        ("missing_representation", "EvidenceValidationAttempt target_digest is stale."),
        ("corrupt_representation", "DocumentRepresentation canonical_output_digest is corrupted."),
    ],
)
def test_verify_evidence_target_rejects_corruption_without_mutating_it(
    mutation: str,
    expected_error: str,
) -> None:
    ledger = FakeEvidenceLedger(_bundle(), _evidence_target())
    validation = validate_evidence_target(
        EvidenceValidationInput("etg_alpha", "eva_success", "1", NOW),
        ledger,
    )
    validated = validation.evidence_target
    candidate = validated
    if mutation == "stale_text_view":
        candidate = candidate.model_copy(update={"text_view_digest": "0" * 64})
    elif mutation == "selector_disagreement":
        candidate = candidate.model_copy(update={"exact_text": "wrong"})
    elif mutation == "missing_representation":
        candidate = candidate.model_copy(update={"representation_id": "rep_missing"})
    elif mutation == "corrupt_representation":
        corrupted_representation = ledger.bundle.representation.model_copy(
            update={"canonical_output_digest": "0" * 64}
        )
        ledger.bundle = ledger.bundle.model_copy(
            update={"representation": corrupted_representation}
        )
    else:
        raise AssertionError(f"Unexpected mutation: {mutation}")
    replay = verify_evidence_target(candidate, validation.attempt, ledger)

    assert replay.valid is False
    assert replay.error_message == expected_error
    assert ledger.get_evidence_target(candidate.id) == validated
