"""End-to-end R20 held -> composed -> replay transition test."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import (
    AssertionConstructionInputs,
    AttachmentSourceRange,
    BuildIdentity,
    ConstituentCandidateInventory,
    EventCompositionRecord,
    EventCompositionStatus,
    EventEntityLinguisticToken,
    GroundingCandidate,
    IdentityOccurrenceProposalInput,
    ParserConstituent,
    accept_identity_occurrence,
    load_event_composition_record,
    parser_constituent_id,
    processing_task_fingerprint,
    propose_identity_occurrence,
    write_event_composition_record,
)
from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    IdentityOccurrenceKind,
    ParseQualityReport,
    RawBlob,
    RepresentationAnalyzability,
    Source,
    SourceAuthority,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from kotekomi_pipelines.ingestion_composition_command import (
    RecompositionRequest,
    run_recomposition,
)
from kotekomi_pipelines.ingestion_composition_stage import (
    compose_ingested_event,
    compose_paragraph_events,
)
from kotekomi_pipelines.live_identity_reference_provider import LiveIdentityReferenceLedger

NOW = datetime(2026, 10, 30, tzinfo=UTC)
TEXT = "Alpha supports the reviewed assertion."
TEXT_DIGEST = hashlib.sha256(TEXT.encode()).hexdigest()
REP_ID = "rep_r20"
TVW_ID = "tvw_r20"
NOD_ID = "nod_r20"
DOC_ID = "doc_r20"
SOURCE_ID = "src_r20"
EVENT_ID = "AHE-001"


def _tokens() -> tuple[EventEntityLinguisticToken, ...]:
    def token(
        token_id: str,
        text: str,
        start: int,
        end: int,
        relation: str,
        head: str | None,
        pos: str,
        lemma: str | None = None,
    ) -> EventEntityLinguisticToken:
        return EventEntityLinguisticToken(
            token_id=token_id,
            sentence_id="s1",
            text=text,
            start=start,
            end=end,
            lemma=lemma or text.casefold(),
            part_of_speech=pos,
            dependency_relation=relation,
            head_token_id=head,
        )

    return (
        token("t1", "Alpha", 0, 5, "nsubj", "t2", "PROPN"),
        token("t2", "supports", 6, 14, "root", None, "VERB", lemma="support"),
        token("t3", "the", 15, 18, "det", "t5", "DET"),
        token("t4", "reviewed", 19, 27, "amod", "t5", "VERB"),
        token("t5", "assertion", 28, 37, "obj", "t2", "NOUN"),
        token("t6", ".", 37, 38, "punct", "t2", "PUNCT"),
    )


def _inventory() -> ConstituentCandidateInventory:
    def constituent(
        start: int, end: int, text: str, token_ids: tuple[str, ...]
    ) -> ParserConstituent:
        return ParserConstituent(
            constituent_id=parser_constituent_id(TEXT_DIGEST, start, end),
            event_id=EVENT_ID,
            source_text_sha256=TEXT_DIGEST,
            constituent_range=AttachmentSourceRange(start=start, end=end, text=text),
            token_ids=token_ids,
        )

    return ConstituentCandidateInventory(
        event_id=EVENT_ID,
        source_text_sha256=TEXT_DIGEST,
        constituents=(
            constituent(0, 5, "Alpha", ("t1",)),
            constituent(6, 14, "supports", ("t2",)),
            constituent(15, 37, "the reviewed assertion", ("t3", "t4", "t5")),
            constituent(28, 37, "assertion", ("t5",)),
        ),
    )


def _bundle() -> DocumentRepresentationBundle:
    text_view = TextView(
        id=TVW_ID,
        representation_id=REP_ID,
        kind=TextViewKind.LOGICAL,
        content_digest=TEXT_DIGEST,
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
        parser_name="fixture",
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


def _representation_task():
    return processing_task_fingerprint(
        task_kind="r20_composition_fixture",
        document_id=DOC_ID,
        blob_id="blb_r20",
        input_digest="b" * 64,
        processor_name="fixture",
        processor_version="1",
        processor_config_digest="a" * 64,
        build_identity=BuildIdentity("fixture", "fixture", "c" * 64, "1"),
        policy_id="fixture_policy",
        output_contract_version="1",
    ).model_copy(update={"id": "ptf_r20"})


def _seed(db: Path) -> None:
    SQLiteLedgerInitializer(db).initialize()
    with sqlite_ledger_transaction(db) as repository:
        repository.save_source(
            Source(
                id=SOURCE_ID,
                source_type=SourceType.ARTICLE,
                identity_policy_id="fixture_v1",
                canonical_identity_key="r20",
            )
        )
        repository.save_document(Document(id=DOC_ID, source_id=SOURCE_ID, content_sha256="b" * 64))
        repository.save_raw_blob(
            RawBlob(
                id="blb_r20",
                hash_algorithm="sha256",
                digest="b" * 64,
                byte_length=1,
                media_type="application/octet-stream",
                storage_locator="sources/raw/blb_r20.bin",
            )
        )
        repository.ensure_processing_task_fingerprint(_representation_task())
        repository.commit_document_representation_bundle(_bundle())


def _alpha_identity_id() -> str:
    return "act_" + hashlib.sha256(b"actor:Alpha").hexdigest()[:24]


def _proposal() -> IdentityOccurrenceProposalInput:
    return IdentityOccurrenceProposalInput(
        identity_kind=IdentityOccurrenceKind.ACTOR,
        decision="new_identity",
        existing_identity_id=None,
        identity_name="Alpha",
        source_id=SOURCE_ID,
        document_id=DOC_ID,
        representation_id=REP_ID,
        text_view_id=TVW_ID,
        text_view_digest=TEXT_DIGEST,
        start_char=0,
        end_char=5,
        exact_text="Alpha",
        node_id=NOD_ID,
    )


def _assertion_inputs(evidence_target_id: str, alpha_id: str) -> AssertionConstructionInputs:
    return AssertionConstructionInputs(
        predicate_by_label={"support": "supports"},
        identity_by_entity={alpha_id: alpha_id},
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id=SOURCE_ID,
        evidence_target_id=evidence_target_id,
    )


def _compose(
    repository: LiveIdentityReferenceLedger,
    evidence_target_id: str,
    alpha_id: str,
    pending: tuple[str, ...],
) -> EventCompositionRecord:
    return compose_ingested_event(
        repository=repository,
        event_id=EVENT_ID,
        source_text=TEXT,
        source_text_sha256=TEXT_DIGEST,
        inventory=_inventory(),
        trigger_head_start=6,
        trigger_head_end=14,
        tokens=_tokens(),
        assertion_inputs=_assertion_inputs(evidence_target_id, alpha_id),
        representation_id=REP_ID,
        text_view_id=TVW_ID,
        pending_identity_ids=pending,
    )


def test_held_then_approved_then_composed_and_replayed(tmp_path: Path) -> None:
    db = tmp_path / "kotekomi.db"
    _seed(db)
    alpha_id = _alpha_identity_id()
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Alpha",
    )
    proposal = propose_identity_occurrence(
        candidate, _proposal(), proposal_id="pcg_r20_e2e", now=NOW
    )
    replay = tmp_path / "composition.json"

    with sqlite_ledger_transaction(db) as repository:
        repository.save_proposed_change(proposal)

        held = _compose(repository, "etg_placeholder", alpha_id, (alpha_id,))
        write_event_composition_record(replay, held)

        reloaded = load_event_composition_record(replay)
        assert reloaded.status is EventCompositionStatus.HELD
        assert reloaded.hold_reason == "awaiting_acceptance"
        assert reloaded.unavailable_reference == alpha_id

        occurrence = accept_identity_occurrence(
            proposal, repository, agent="kotekomi_agent", now=NOW
        )

        composed = _compose(repository, occurrence.evidence_target_id, alpha_id, ())
        write_event_composition_record(replay, composed)

    final = load_event_composition_record(replay)
    assert final.status is EventCompositionStatus.COMPOSED
    assert final.assertion is not None
    assert final.assertion.predicate == "supports"
    assert final.assertion.subject_entity_id == alpha_id
    assert final.assertion.object_value == "the reviewed assertion"
    assert final.supporting_subject_span is not None
    assert final.supporting_subject_span.text == "Alpha"
    assert final.supporting_object_span is not None
    assert final.supporting_object_span.text == "the reviewed assertion"


def test_recomposition_command_composes_after_approval(tmp_path: Path) -> None:
    db = tmp_path / "kotekomi.db"
    _seed(db)
    alpha_id = _alpha_identity_id()
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Alpha",
    )
    proposal = propose_identity_occurrence(
        candidate, _proposal(), proposal_id="pcg_r20_command", now=NOW
    )
    with sqlite_ledger_transaction(db) as repository:
        repository.save_proposed_change(proposal)
        occurrence = accept_identity_occurrence(
            proposal, repository, agent="kotekomi_agent", now=NOW
        )
        request = RecompositionRequest(
            event_id=EVENT_ID,
            source_text=TEXT,
            source_text_sha256=TEXT_DIGEST,
            inventory=_inventory(),
            trigger_head_start=6,
            trigger_head_end=14,
            tokens=_tokens(),
            representation_id=REP_ID,
            text_view_id=TVW_ID,
            predicate_by_label={"support": "supports"},
            identity_by_entity={alpha_id: alpha_id},
            assertion_type=AssertionType.REPORTED_OBSERVATION,
            source_authority=SourceAuthority.SECONDARY,
            attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
            source_id=SOURCE_ID,
            evidence_target_id=occurrence.evidence_target_id,
        )
        record = run_recomposition(request, repository)

    assert record.status is EventCompositionStatus.COMPOSED
    assert record.assertion is not None
    assert record.assertion.subject_entity_id == alpha_id


def test_compose_paragraph_events_persists_every_outcome(tmp_path: Path) -> None:
    db = tmp_path / "kotekomi.db"
    _seed(db)
    alpha_id = _alpha_identity_id()
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name="Alpha",
    )
    proposal = propose_identity_occurrence(
        candidate, _proposal(), proposal_id="pcg_r20_paragraph", now=NOW
    )
    root = tmp_path / "composition-outcomes"
    events = ((EVENT_ID, 6, 14),)

    with sqlite_ledger_transaction(db) as repository:
        repository.save_proposed_change(proposal)

        held = compose_paragraph_events(
            repository=repository,
            source_text=TEXT,
            tokens=_tokens(),
            events=events,
            assertion_inputs_by_event={},
            representation_id=REP_ID,
            text_view_id=TVW_ID,
            composition_root=root,
        )
        assert held[0].status is EventCompositionStatus.HELD
        assert held[0].hold_reason == "assertion_inputs_unavailable"
        assert (root / f"{EVENT_ID}.json").exists()

        no_inventory = compose_paragraph_events(
            repository=repository,
            source_text=TEXT,
            tokens=(),
            events=events,
            assertion_inputs_by_event={},
            representation_id=REP_ID,
            text_view_id=TVW_ID,
            composition_root=root,
        )
        assert no_inventory[0].hold_reason == "inventory_unavailable"

        occurrence = accept_identity_occurrence(
            proposal, repository, agent="kotekomi_agent", now=NOW
        )
        composed = compose_paragraph_events(
            repository=repository,
            source_text=TEXT,
            tokens=_tokens(),
            events=events,
            assertion_inputs_by_event={
                EVENT_ID: _assertion_inputs(occurrence.evidence_target_id, alpha_id)
            },
            representation_id=REP_ID,
            text_view_id=TVW_ID,
            composition_root=root,
        )
        assert composed[0].status is EventCompositionStatus.COMPOSED

    reloaded = load_event_composition_record(root / f"{EVENT_ID}.json")
    assert reloaded.status is EventCompositionStatus.COMPOSED
    assert reloaded.assertion is not None
    assert reloaded.supporting_subject_span is not None
    assert reloaded.supporting_subject_span.text == "Alpha"
