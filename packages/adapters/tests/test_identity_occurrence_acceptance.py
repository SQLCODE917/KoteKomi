"""Real-SQLite atomic acceptance test for R20 identity occurrences."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import (
    BuildIdentity,
    GroundingCandidate,
    IdentityOccurrenceAcceptanceLedger,
    IdentityOccurrenceProposalInput,
    accept_identity_occurrence,
    processing_task_fingerprint,
    propose_identity_occurrence,
)
from kotekomi_domain import (
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    IdentityOccurrenceKind,
    ParseQualityReport,
    RawBlob,
    RepresentationAnalyzability,
    ReviewStatus,
    Source,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 7, 11, tzinfo=UTC)
TEXT = "Alpha supports the reviewed assertion."
TEXT_DIGEST = hashlib.sha256(TEXT.encode()).hexdigest()


def _bundle() -> DocumentRepresentationBundle:
    text_view = TextView(
        id="tvw_atomic_logical",
        representation_id="rep_atomic",
        kind=TextViewKind.LOGICAL,
        content_digest=TEXT_DIGEST,
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )
    node = DocumentNode(
        id="nod_atomic_document",
        representation_id="rep_atomic",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(TEXT),
    )
    quality_report = ParseQualityReport(
        id="pqr_atomic",
        representation_id="rep_atomic",
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id="rep_atomic",
        document_id="doc_atomic",
        parser_name="fixture",
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


def _representation_task():
    return processing_task_fingerprint(
        task_kind="atomic_acceptance_fixture",
        document_id="doc_atomic",
        blob_id="blb_atomic",
        input_digest="b" * 64,
        processor_name="fixture",
        processor_version="1",
        processor_config_digest="a" * 64,
        build_identity=BuildIdentity("fixture", "fixture", "c" * 64, "1"),
        policy_id="fixture_policy",
        output_contract_version="1",
    ).model_copy(update={"id": "ptf_fixture"})


def _proposal() -> IdentityOccurrenceProposalInput:
    return IdentityOccurrenceProposalInput(
        identity_kind=IdentityOccurrenceKind.ACTOR,
        decision="new_identity",
        existing_identity_id=None,
        identity_name="Alpha",
        source_id="src_atomic",
        document_id="doc_atomic",
        representation_id="rep_atomic",
        text_view_id="tvw_atomic_logical",
        text_view_digest=TEXT_DIGEST,
        start_char=0,
        end_char=5,
        exact_text="Alpha",
        node_id="nod_atomic_document",
    )


class _FailOnProposalSave:
    def __init__(self, inner: object) -> None:
        self._inner = inner

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def save_proposed_change(self, record: object) -> None:
        del record
        raise RuntimeError("fail after earlier writes")


def _seed(db: Path) -> None:
    SQLiteLedgerInitializer(db).initialize()
    with sqlite_ledger_transaction(db) as repository:
        repository.save_source(
            Source(
                id="src_atomic",
                source_type=SourceType.ARTICLE,
                identity_policy_id="fixture_v1",
                canonical_identity_key="atomic",
            )
        )
        repository.save_document(
            Document(id="doc_atomic", source_id="src_atomic", content_sha256="b" * 64)
        )
        repository.save_raw_blob(
            RawBlob(
                id="blb_atomic",
                hash_algorithm="sha256",
                digest="b" * 64,
                byte_length=1,
                media_type="application/octet-stream",
                storage_locator="sources/raw/blb_atomic.bin",
            )
        )
        repository.ensure_processing_task_fingerprint(_representation_task())
        repository.commit_document_representation_bundle(_bundle())


def test_acceptance_rolls_back_every_write_after_an_earlier_write(tmp_path: Path) -> None:
    db = tmp_path / "kotekomi.db"
    _seed(db)
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Alpha",
    )
    proposal = propose_identity_occurrence(
        candidate, _proposal(), proposal_id="pcg_r20_rollback", now=NOW
    )
    with sqlite_ledger_transaction(db) as repository:
        repository.save_proposed_change(proposal)

    with pytest.raises(RuntimeError, match="fail after earlier writes"):
        with sqlite_ledger_transaction(db) as repository:
            accept_identity_occurrence(
                proposal,
                cast(IdentityOccurrenceAcceptanceLedger, _FailOnProposalSave(repository)),
                agent="kotekomi_agent",
                now=NOW,
            )

    with sqlite_ledger_transaction(db) as repository:
        assert repository.list_actors() == ()
        assert repository.list_evidence_targets() == ()
        assert repository.list_identity_occurrences() == ()
        assert repository.list_provenance_activities() == ()
        stored = repository.get_proposed_change("pcg_r20_rollback")
        assert stored is not None
        assert stored.review_status is ReviewStatus.PENDING


def test_acceptance_commits_atomically_on_a_real_ledger(tmp_path: Path) -> None:
    db = tmp_path / "kotekomi.db"
    _seed(db)
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Alpha",
    )
    proposal = propose_identity_occurrence(
        candidate, _proposal(), proposal_id="pcg_r20_commit", now=NOW
    )
    with sqlite_ledger_transaction(db) as repository:
        repository.save_proposed_change(proposal)
        occurrence = accept_identity_occurrence(
            proposal, repository, agent="kotekomi_agent", now=NOW
        )

    with sqlite_ledger_transaction(db) as repository:
        assert repository.get_identity_occurrence(occurrence.id) == occurrence
        assert repository.get_actor(occurrence.identity_id) is not None
        assert repository.get_evidence_target(occurrence.evidence_target_id) is not None
        assert repository.get_provenance_activity(occurrence.provenance_activity_id) is not None
        stored = repository.get_proposed_change("pcg_r20_commit")
        assert stored is not None
        assert stored.review_status is ReviewStatus.APPROVED
