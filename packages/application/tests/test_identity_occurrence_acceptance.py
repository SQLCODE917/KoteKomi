"""Tests for R20 identity-occurrence proposal and atomic acceptance."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    GroundingCandidate,
    IdentityOccurrenceAcceptanceLedger,
    IdentityOccurrenceHold,
    IdentityOccurrenceHoldReason,
    IdentityOccurrenceProposalInput,
    accept_identity_occurrence,
    propose_identity_occurrence,
)
from kotekomi_domain import (
    Actor,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EvidenceTarget,
    IdentityOccurrence,
    IdentityOccurrenceKind,
    Organization,
    ParseQualityReport,
    ProposedChange,
    ProvenanceActivity,
    RepresentationAnalyzability,
    ReviewStatus,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 10, 30, tzinfo=UTC)
TEXT = "Mira greeted Tomas."
REP_ID = "rep_r20"
TVW_ID = "tvw_r20"
NOD_ID = "nod_r20"
DOC_ID = "doc_r20"
SOURCE_ID = "src_r20"


def _bundle() -> DocumentRepresentationBundle:
    text_view = TextView(
        id=TVW_ID,
        representation_id=REP_ID,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )
    node = DocumentNode(
        id=NOD_ID,
        representation_id=REP_ID,
        node_type="document",
        order_index=0,
        text_view_id=TVW_ID,
        start_char=0,
        end_char=len(TEXT),
    )
    quality_report = ParseQualityReport(
        id="pqr_r20",
        representation_id=REP_ID,
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=REP_ID,
        document_id=DOC_ID,
        parser_name="test",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_r20",
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


class _Ledger:
    def __init__(self) -> None:
        self.actors: dict[str, Actor] = {}
        self.organizations: dict[str, Organization] = {}
        self.evidence_targets: dict[str, EvidenceTarget] = {}
        self.occurrences: dict[str, IdentityOccurrence] = {}
        self.provenance: dict[str, ProvenanceActivity] = {}
        self.proposals: dict[str, ProposedChange] = {}
        self._bundle = _bundle()

    def get_actor(self, record_id: str) -> Actor | None:
        return self.actors.get(record_id)

    def get_organization(self, record_id: str) -> Organization | None:
        return self.organizations.get(record_id)

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.evidence_targets.get(record_id)

    def get_document(self, record_id: str) -> Document | None:
        return Document(id=DOC_ID, source_id=SOURCE_ID, content_sha256="c" * 64)

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self._bundle

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposals.get(record_id)

    def save_actor(self, record: Actor) -> None:
        self.actors[record.id] = record

    def save_organization(self, record: Organization) -> None:
        self.organizations[record.id] = record

    def save_evidence_target(self, record: EvidenceTarget) -> None:
        self.evidence_targets[record.id] = record

    def save_identity_occurrence(self, record: IdentityOccurrence) -> None:
        self.occurrences[record.id] = record

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance[record.id] = record

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposals[record.id] = record


def _ledger() -> tuple[_Ledger, IdentityOccurrenceAcceptanceLedger]:
    ledger = _Ledger()
    return ledger, cast(IdentityOccurrenceAcceptanceLedger, ledger)


def _proposal(
    *, decision: str = "new_identity", identity_name: str | None = "Mira"
) -> IdentityOccurrenceProposalInput:
    return IdentityOccurrenceProposalInput(
        identity_kind=IdentityOccurrenceKind.ACTOR,
        decision="new_identity" if decision == "new_identity" else "existing_identity",
        existing_identity_id=None if decision == "new_identity" else "act_existing",
        identity_name=identity_name,
        source_id=SOURCE_ID,
        document_id=DOC_ID,
        representation_id=REP_ID,
        text_view_id=TVW_ID,
        text_view_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        start_char=0,
        end_char=4,
        exact_text="Mira",
        node_id=NOD_ID,
    )


def test_nil_candidate_produces_a_typed_hold() -> None:
    candidate = GroundingCandidate(
        candidate_kind="nil", eligible=False, ambiguous=False, identity_name=None
    )
    with pytest.raises(IdentityOccurrenceHold) as error:
        propose_identity_occurrence(candidate, _proposal(), proposal_id="pcg_proposal", now=NOW)
    assert error.value.reason is IdentityOccurrenceHoldReason.CANDIDATE_NOT_ACCEPTABLE


def test_acceptance_commits_new_identity_atomically() -> None:
    ledger, repository = _ledger()
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Mira",
    )
    proposal = propose_identity_occurrence(
        candidate, _proposal(), proposal_id="pcg_new_mira", now=NOW
    )
    assert proposal.review_status is ReviewStatus.PENDING

    occurrence = accept_identity_occurrence(proposal, repository, agent="kotekomi_agent", now=NOW)

    assert occurrence.identity_kind is IdentityOccurrenceKind.ACTOR
    assert occurrence.identity_id in ledger.actors
    assert ledger.actors[occurrence.identity_id].name == "Mira"
    assert occurrence.evidence_target_id in ledger.evidence_targets
    assert occurrence.provenance_activity_id in ledger.provenance
    assert ledger.provenance[occurrence.provenance_activity_id].output_ids == (
        occurrence.identity_id,
        occurrence.evidence_target_id,
        occurrence.id,
    )
    assert ledger.occurrences[occurrence.id] == occurrence
    assert ledger.proposals["pcg_new_mira"].review_status is ReviewStatus.APPROVED


def test_acceptance_links_an_existing_identity() -> None:
    ledger, repository = _ledger()
    ledger.actors["act_existing"] = Actor(id="act_existing", name="Mira")
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Mira",
    )
    proposal = propose_identity_occurrence(
        candidate,
        _proposal(decision="existing_identity", identity_name="Mira"),
        proposal_id="pcg_existing_mira",
        now=NOW,
    )

    occurrence = accept_identity_occurrence(proposal, repository, agent="kotekomi_agent", now=NOW)

    assert occurrence.identity_id == "act_existing"
    assert tuple(ledger.actors) == ("act_existing",)
    assert occurrence.id in ledger.occurrences


def test_acceptance_rolls_back_on_unreplayable_evidence() -> None:
    ledger, repository = _ledger()
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Mira",
    )
    malformed = IdentityOccurrenceProposalInput(
        identity_kind=IdentityOccurrenceKind.ACTOR,
        decision="new_identity",
        existing_identity_id=None,
        identity_name="Mira",
        source_id=SOURCE_ID,
        document_id=DOC_ID,
        representation_id=REP_ID,
        text_view_id=TVW_ID,
        text_view_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        start_char=0,
        end_char=5,
        exact_text="Mira",
        node_id=NOD_ID,
    )
    proposal = propose_identity_occurrence(
        candidate, malformed, proposal_id="pcg_bad_span", now=NOW
    )

    with pytest.raises(IdentityOccurrenceHold) as error:
        accept_identity_occurrence(proposal, repository, agent="kotekomi_agent", now=NOW)

    assert error.value.reason is IdentityOccurrenceHoldReason.EVIDENCE_UNREPLAYABLE
    assert ledger.evidence_targets == {}
    assert ledger.occurrences == {}
    assert ledger.actors == {}
