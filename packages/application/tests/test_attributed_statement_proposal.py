"""Reviewed attributed-statement proposal submission use case tests.

Covers the reviewed submitter contracts: typed non-records for wrong scope and
already-rejected proposals, deterministic ProvenanceActivity/ProposedChange ids,
idempotent resubmission, and fail-fast reference validation on missing or
non-replayable evidence.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    AttributedStatementProposalFailure,
    SubmitAttributedStatementProposalInput,
    submit_attributed_statement_proposal,
)
from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EpistemicScope,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ParseQualityReport,
    ProposedAssertion,
    ProposedChange,
    ProvenanceActivity,
    RepresentationAnalyzability,
    ReviewStatus,
    Source,
    SourceAuthority,
    SourceType,
    TextView,
    TextViewKind,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)

NOW = datetime(2026, 9, 22, 0, 0, tzinfo=UTC)
TEXT = "Alpha. Alpha."
TEXT_DIGEST = "77d913272bb8bdba48d318de4a6a4b033dace9770d8cd967b09285d1876449a4"

_ASSERTION_ID = "ast_attributed_01"
_EVIDENCE_ID = "etg_alpha"
_ATTEMPT_ID = "eva_support_01"
_SOURCE_ID = "src_example"
_DOCUMENT_ID = "doc_example"


class _Ledger:
    def __init__(
        self,
        bundle: DocumentRepresentationBundle,
        evidence_target: EvidenceTarget,
        validation_attempt: EvidenceValidationAttempt,
    ) -> None:
        self.bundle = bundle
        self.sources: dict[str, Source] = {
            _SOURCE_ID: Source(
                id=_SOURCE_ID,
                source_type=SourceType.ARTICLE,
                identity_policy_id="pol_article",
                canonical_identity_key="key_article",
            )
        }
        self.documents: dict[str, Document] = {
            _DOCUMENT_ID: Document(
                id=_DOCUMENT_ID,
                source_id=_SOURCE_ID,
                content_sha256="a" * 64,
            )
        }
        self.evidence_targets: dict[str, EvidenceTarget] = {evidence_target.id: evidence_target}
        self.validation_attempts: dict[str, EvidenceValidationAttempt] = {
            validation_attempt.id: validation_attempt
        }
        self.proposed_changes: dict[str, ProposedChange] = {}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}

    def get_source(self, record_id: str) -> Source | None:
        return self.sources.get(record_id)

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.evidence_targets.get(record_id)

    def get_evidence_validation_attempt(
        self, record_id: str
    ) -> EvidenceValidationAttempt | None:
        return self.validation_attempts.get(record_id)

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposed_changes[record.id] = record


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
    )
    quality_report = ParseQualityReport(
        id="pqr_example",
        representation_id="rep_example",
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_example",
        document_id=_DOCUMENT_ID,
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


def _evidence_target() -> EvidenceTarget:
    return EvidenceTarget(
        id=_EVIDENCE_ID,
        source_id=_SOURCE_ID,
        document_id=_DOCUMENT_ID,
        exact_text="Alpha",
        prefix_text="",
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


def _validation_attempt(evidence_target: EvidenceTarget) -> EvidenceValidationAttempt:
    return EvidenceValidationAttempt(
        id=_ATTEMPT_ID,
        evidence_target_id=evidence_target.id,
        target_digest=canonical_evidence_target_digest(evidence_target),
        validator_version="1",
        status=EvidenceValidationAttemptStatus.SUCCEEDED,
        attempted_at=NOW,
    )


def _assertion(
    *, epistemic_scope: EpistemicScope = EpistemicScope.ATTRIBUTED_STATEMENT
) -> ProposedAssertion:
    return ProposedAssertion(
        id=_ASSERTION_ID,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=epistemic_scope,
        subject_entity_id="org_anthropic",
        relation_label="chastised_anthropic_hiring",
        object_value="Anthropic's hiring was chastised",
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        attributed_to_id="act_sacks",
        source_ids=(_SOURCE_ID,),
        evidence_target_ids=(_EVIDENCE_ID,),
    )


def _proposal(assertion: ProposedAssertion) -> SubmitAttributedStatementProposalInput:
    return SubmitAttributedStatementProposalInput(
        proposed_assertion=assertion,
        support_evidence_target_id=_EVIDENCE_ID,
        support_validation_attempt_id=_ATTEMPT_ID,
        proposer="analyst",
        document_id=_DOCUMENT_ID,
        submitted_at=NOW,
    )


def _ledger() -> _Ledger:
    evidence_target = _evidence_target()
    return _Ledger(_bundle(), evidence_target, _validation_attempt(evidence_target))


def _deterministic_id(prefix: str, *parts: str) -> str:
    value = "\x1f".join(parts)
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def test_submit_writes_pending_proposed_change_and_provenance_activity() -> None:
    ledger = _ledger()

    result = submit_attributed_statement_proposal(_proposal(_assertion()), ledger)

    assert result.status == "pending"
    assert result.proposed_change_id is not None
    assert result.provenance_activity_id is not None
    proposed_change_id = result.proposed_change_id
    provenance_activity_id = result.provenance_activity_id
    assert proposed_change_id == _deterministic_id(
        "pcg", "attributed_statement", _ASSERTION_ID
    )
    assert result.assertion_id == _ASSERTION_ID
    assert provenance_activity_id == _deterministic_id(
        "prv", "attributed_statement_proposed", proposed_change_id
    )

    change = ledger.get_proposed_change(proposed_change_id)
    assert change is not None
    assert change.review_status is ReviewStatus.PENDING
    assert change.proposed_json["record_type"] == "Assertion"
    assert change.proposed_json["stable_label"] == _ASSERTION_ID
    assert change.provenance_activity_id == provenance_activity_id

    activity = ledger.provenance_activities[provenance_activity_id]
    assert activity.activity_type == "attributed_statement_proposed"
    assert activity.agent == "analyst"
    assert activity.input_ids == (_SOURCE_ID, _DOCUMENT_ID, _EVIDENCE_ID, _ATTEMPT_ID)
    assert activity.output_ids == (proposed_change_id,)


def test_wrong_epistemic_scope_returns_typed_failure_without_writing() -> None:
    ledger = _ledger()

    result = submit_attributed_statement_proposal(
        _proposal(_assertion(epistemic_scope=EpistemicScope.SOURCE_REPORT)),
        ledger,
    )

    assert result.status == "failed"
    assert result.failure is AttributedStatementProposalFailure.WRONG_EPISTEMIC_SCOPE
    assert result.proposed_change_id is None
    assert ledger.proposed_changes == {}
    assert ledger.provenance_activities == {}


def test_resubmission_is_idempotent_and_reports_recorded_when_approved() -> None:
    ledger = _ledger()
    first = submit_attributed_statement_proposal(_proposal(_assertion()), ledger)
    assert first.proposed_change_id is not None
    assert first.provenance_activity_id is not None
    proposed_change_id = first.proposed_change_id

    second = submit_attributed_statement_proposal(_proposal(_assertion()), ledger)

    assert second.status == "pending"
    assert second.proposed_change_id == proposed_change_id
    assert second.provenance_activity_id == first.provenance_activity_id
    assert len(ledger.proposed_changes) == 1

    approved = ledger.get_proposed_change(proposed_change_id)
    assert approved is not None
    ledger.proposed_changes[proposed_change_id] = approved.model_copy(
        update={"review_status": ReviewStatus.APPROVED}
    )
    third = submit_attributed_statement_proposal(_proposal(_assertion()), ledger)
    assert third.status == "recorded"
    assert third.proposed_change_id == proposed_change_id


def test_already_rejected_proposal_returns_typed_failure() -> None:
    ledger = _ledger()
    rejected_id = _deterministic_id("pcg", "attributed_statement", _ASSERTION_ID)
    ledger.proposed_changes[rejected_id] = ProposedChange(
        id=rejected_id,
        review_status=ReviewStatus.REJECTED,
        proposed_json={"record_type": "Assertion"},
    )

    result = submit_attributed_statement_proposal(_proposal(_assertion()), ledger)

    assert result.status == "failed"
    assert result.failure is AttributedStatementProposalFailure.ALREADY_REJECTED
    assert result.proposed_change_id == rejected_id


def test_missing_source_fails_fast() -> None:
    ledger = _ledger()
    ledger.sources = {}

    with pytest.raises(ValueError, match="missing Source"):
        submit_attributed_statement_proposal(_proposal(_assertion()), ledger)


def test_document_from_another_source_fails_fast() -> None:
    ledger = _ledger()
    ledger.documents[_DOCUMENT_ID] = Document(
        id=_DOCUMENT_ID,
        source_id="src_other",
        content_sha256="a" * 64,
    )

    with pytest.raises(ValueError, match="does not belong to its Source"):
        submit_attributed_statement_proposal(_proposal(_assertion()), ledger)


def test_support_evidence_target_not_on_assertion_fails_fast() -> None:
    ledger = _ledger()
    assertion = _assertion().model_copy(update={"evidence_target_ids": ("etg_other",)})

    with pytest.raises(ValueError, match="support EvidenceTarget is not on the assertion"):
        submit_attributed_statement_proposal(_proposal(assertion), ledger)


def test_non_replayable_evidence_fails_fast() -> None:
    ledger = _ledger()
    stale = _evidence_target().model_copy(update={"exact_text": "wrong"})
    ledger.evidence_targets[_EVIDENCE_ID] = stale

    with pytest.raises(ValueError, match="replayable successful evidence"):
        submit_attributed_statement_proposal(_proposal(_assertion()), ledger)


def test_empty_proposer_fails_fast() -> None:
    ledger = _ledger()
    proposal = _proposal(_assertion())
    proposal = SubmitAttributedStatementProposalInput(
        proposed_assertion=proposal.proposed_assertion,
        support_evidence_target_id=proposal.support_evidence_target_id,
        support_validation_attempt_id=proposal.support_validation_attempt_id,
        proposer="   ",
        document_id=proposal.document_id,
        submitted_at=proposal.submitted_at,
    )

    with pytest.raises(ValueError, match="requires a proposer"):
        submit_attributed_statement_proposal(proposal, ledger)