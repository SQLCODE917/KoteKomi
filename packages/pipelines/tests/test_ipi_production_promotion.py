"""Captured-input review regressions; no ingestion, model calls, or accuracy claim.

Only captured ingestion records seed the disposable Ledger and Archive.
Review prerequisites and composition outcomes come from the supported workflow.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import EventCompositionStatus, EventConstructionDecisionInput
from kotekomi_application.composition_inspection import composition_inspection_records
from kotekomi_application.evidence_targets import validate_evidence_target_record
from kotekomi_application.ingestion_inspection import ParagraphSnapshot, build_profile
from kotekomi_domain import (
    AnalysisPlanArtifact,
    AnalysisRun,
    AssertionType,
    AttributionBasis,
    Document,
    DocumentRepresentationBundle,
    EvidenceTarget,
    EvidenceValidationAttempt,
    IdentityOccurrenceKind,
    IngestionChangeSet,
    IngestionRun,
    IngestionRunStatus,
    ProcessingTaskFingerprint,
    ProposedChange,
    ProvenanceActivity,
    RawBlob,
    Source,
    SourceAuthority,
)
from kotekomi_pipelines.replay_reader.live import create_inspection_session
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs

from packages.pipelines.tests.test_operator_journey import NOW, Journey

FIXTURE = Path(__file__).parent / "fixtures" / "ipi_promotion"
RUN = "igr_c4b8a09978114e49bb63e8c7df73a005"
CASES = (
    (
        "established",
        "The  Department  of  Defense",
        "a  policy  on  the  use  of  artificial intelligence",
        "in  2012",
    ),
    ("criticized", "Amodei", "Trump's approach to export restrictions on semiconductors", None),
    ("integrated", "the Trump administration", "Anthropic's services", "Prior to the dispute"),
)


def _seed_capture(journey: Journey) -> None:
    """Load declared Domain Core records through SQLite's typed fixture methods."""
    data: dict[str, list[dict[str, Any]]] = json.loads((FIXTURE / "ledger.json").read_text())
    assert set(data) == {
        "Source",
        "Document",
        "ProvenanceActivity",
        "DocumentRepresentationBundle",
        "EvidenceTarget",
        "EvidenceValidationAttempt",
        "AnalysisRun",
        "AnalysisPlanArtifact",
        "IngestionRun",
        "IngestionChangeSet",
        "ProposedChange",
        "ProcessingTaskFingerprint",
        "RawBlob",
    }
    journey.state.mkdir()
    shutil.copytree(FIXTURE / "archive", journey.archive)
    shutil.copytree(FIXTURE / "token-artifacts", journey.state / "token-artifacts")
    SQLiteLedgerInitializer(journey.ledger).initialize()
    with sqlite_ledger_transaction(journey.ledger) as ledger:
        for row in data["ProvenanceActivity"]:
            ledger.save_provenance_activity(ProvenanceActivity.model_validate_json(json.dumps(row)))
        for row in data["Source"]:
            ledger.save_source(Source.model_validate_json(json.dumps(row)))
        for row in data["Document"]:
            ledger.save_document(Document.model_validate_json(json.dumps(row)))
        for row in data["RawBlob"]:
            blob = RawBlob.model_validate_json(json.dumps(row))
            raw = (journey.archive / blob.storage_locator).read_bytes()
            assert len(raw) == blob.byte_length
            assert hashlib.sha256(raw).hexdigest() == blob.digest
            ledger.save_raw_blob(blob)
        for row in data["ProcessingTaskFingerprint"]:
            ledger.ensure_processing_task_fingerprint(
                ProcessingTaskFingerprint.model_validate_json(json.dumps(row))
            )
        for row in data["DocumentRepresentationBundle"]:
            ledger.commit_document_representation_bundle(
                DocumentRepresentationBundle.model_validate_json(json.dumps(row))
            )
        for row in data["EvidenceTarget"]:
            target = EvidenceTarget.model_validate_json(json.dumps(row))
            validate_evidence_target_record(target, ledger)
            ledger.save_evidence_target(target)
        for row in data["EvidenceValidationAttempt"]:
            ledger.save_evidence_validation_attempt(
                EvidenceValidationAttempt.model_validate_json(json.dumps(row))
            )
        for row in data["AnalysisPlanArtifact"]:
            ledger.save_analysis_plan_artifact(
                AnalysisPlanArtifact.model_validate_json(json.dumps(row))
            )
        for row in data["AnalysisRun"]:
            ledger.save_analysis_run(AnalysisRun.model_validate_json(json.dumps(row)))
        for row in data["ProposedChange"]:
            ledger.save_proposed_change(ProposedChange.model_validate_json(json.dumps(row)))
        terminal = IngestionRun.model_validate_json(json.dumps(data["IngestionRun"][0]))
        running = IngestionRun(
            id=terminal.id,
            requested_path=terminal.requested_path,
            display_filename=terminal.display_filename,
            requested_source_url=terminal.requested_source_url,
            status=IngestionRunStatus.RUNNING,
            started_at=terminal.started_at,
        )
        ledger.create_ingestion_run(running)
        for row in data["IngestionChangeSet"]:
            ledger.save_ingestion_change_set(
                IngestionChangeSet.model_validate_json(json.dumps(row))
            )
        assert ledger.complete_ingestion_run_if_running(terminal)
        assert ledger.list_identity_occurrences() == ()
        assert ledger.list_event_construction_reviews() == ()
        assert ledger.list_assertions() == ()
    assert not (journey.state / "composition-outcomes").exists()
    journey.run_id = RUN


def _journey(tmp_path: Path, trigger: str) -> Journey:
    journey = Journey(tmp_path)
    _seed_capture(journey)
    paragraphs = load_paragraph_inputs(journey.ledger, journey.archive, ingestion_run_id=RUN)
    events = [
        event
        for paragraph in paragraphs
        for event in build_profile(
            text=paragraph.text,
            representation_id=paragraph.representation_id,
            paragraph_node_id=paragraph.paragraph_node_id,
            node_start_char=paragraph.node_start_char,
            stage_outputs=paragraph.stage_outputs,
            bundle=paragraph.bundle,
        ).events
        if event.trigger_span.text == trigger
    ]
    assert len(events) == 1
    journey.event_id = events[0].event_id
    return journey


def _decide(journey: Journey, predicate: str):
    from kotekomi_pipelines.event_review_workflow import record_review_decision

    packet = journey.packet()
    candidate_text = {
        "established": "Department  of  Defense",
        "criticized": "Amodei",
        "integrated": "Trump administration",
    }[predicate]
    candidate = next(
        candidate for candidate in packet.candidates if candidate.exact_text == candidate_text
    )
    return record_review_decision(
        ledger_path=journey.ledger,
        archive_path=journey.archive,
        ingestion_run_id=RUN,
        event_id=journey.event_id,
        now=NOW,
        decision=EventConstructionDecisionInput(
            candidate_start=candidate.start,
            candidate_end=candidate.end,
            exact_text=candidate.exact_text,
            identity_kind=IdentityOccurrenceKind.ACTOR
            if predicate == "criticized"
            else IdentityOccurrenceKind.ORGANIZATION,
            identity_decision="new_identity",
            existing_identity_id=None,
            identity_name=candidate.identity_name,
            predicate=predicate,
            assertion_type=AssertionType.REPORTED_OBSERVATION,
            source_authority=SourceAuthority.SECONDARY,
            attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
            reviewer="captured-input-regression",
        ),
    )


@pytest.mark.parametrize(("predicate", "subject", "object_text", "time"), CASES)
def test_captured_input_packet_to_replay(
    tmp_path: Path, predicate: str, subject: str, object_text: str, time: str | None
) -> None:
    journey = _journey(tmp_path, predicate)
    packet = journey.packet()
    assert packet.subject_text == subject
    assert packet.object_text == object_text
    assert packet.time_qualifier_text == time
    assert packet.accepted_identity_ids == ()
    if time is not None:
        assert packet.time_qualifier_start is not None and packet.time_qualifier_end is not None
        assert packet.source_text[packet.time_qualifier_start : packet.time_qualifier_end] == time
        assert packet.statement_start <= packet.time_qualifier_start
        assert packet.time_qualifier_end <= packet.statement_end
    review = _decide(journey, predicate)
    assert _decide(journey, predicate).id == review.id
    first = journey.recompose()
    assert first.status is EventCompositionStatus.COMPOSED
    assertion = first.assertion
    assert assertion is not None
    assert assertion.predicate == predicate
    assert assertion.subject_entity_id == review.subject_identity_id
    assert assertion.object_value == object_text
    assert assertion.qualifiers == {
        "polarity": "affirmed",
        "modality": "actual",
        **({"time": time} if time else {}),
    }
    assert assertion.status.value == "proposed"
    assert (
        first.supporting_subject_span is not None and first.supporting_subject_span.text == subject
    )
    assert (
        first.supporting_object_span is not None
        and first.supporting_object_span.text == object_text
    )
    assert journey.recompose().assertion == assertion

    with sqlite_ledger_transaction(journey.ledger) as ledger:
        assert ledger.list_assertions() == ()
        proposals = [
            p
            for p in ledger.list_proposed_changes()
            if p.proposed_json.get("record_type") == "Assertion"
            and p.proposed_json.get("stable_label") == assertion.id
        ]
        assert len(proposals) == 1
        proposal = proposals[0]
        assert proposal.review_status.value == "pending"
        proposed: Any = proposal.proposed_json["record"]
        assert proposed["qualifiers"] == assertion.qualifiers
        assert proposed["object_value"] == object_text
        assert ledger.get_provenance_activity(review.provenance_activity_id) is not None
        for target_id in assertion.evidence_target_ids:
            target = ledger.get_evidence_target(target_id)
            assert target is not None
            validate_evidence_target_record(target, ledger)
            assert (
                target.exact_text
                == packet.source_text[packet.statement_start : packet.statement_end]
            )
            assert subject in target.exact_text and object_text in target.exact_text
            if time is not None:
                assert time in target.exact_text
    store = CompositionOutcomeStore(journey.state / "composition-outcomes")
    assert store.load(journey.event_id) == first
    annotations = store.annotations((journey.event_id,))
    assert annotations[0].assertion == assertion
    # Reload source records through the actual saved-replay boundary as well.
    paragraphs = load_paragraph_inputs(journey.ledger, journey.archive, ingestion_run_id=RUN)
    assert any(p.text == packet.source_text for p in paragraphs)

    snapshots: list[ParagraphSnapshot] = []
    session = create_inspection_session(journey.ledger, on_snapshot=snapshots.append)
    session.replay_stored(paragraphs, None, 0.0, Event())
    assert not session.presentation_failed
    records = [
        record
        for snapshot in snapshots
        for record in composition_inspection_records(snapshot.profile)
        if record.record_id == assertion.id
    ]
    assert records
    assert records[-1].data["qualifiers"] == assertion.qualifiers
    assert records[-1].data["proposals"] == [{"id": proposal.id, "review_status": "pending"}]


@pytest.mark.parametrize("failure_stage", ["decision", "proposal", "outcome"])
def test_captured_time_journey_preserves_transaction_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    from kotekomi_adapters.sqlite_ledger import SQLiteLedgerRepository

    journey = _journey(tmp_path, "established")
    with sqlite_ledger_transaction(journey.ledger) as ledger:
        target_count = len(ledger.list_evidence_targets())
        proposal_ids = {p.id for p in ledger.list_proposed_changes()}

    if failure_stage == "decision":

        def fail_review(self: Any, record: Any) -> None:
            raise OSError("injected review failure")

        with monkeypatch.context() as patch:
            patch.setattr(SQLiteLedgerRepository, "save_event_construction_review", fail_review)
            with pytest.raises(OSError, match="injected review failure"):
                _decide(journey, "established")
        with sqlite_ledger_transaction(journey.ledger) as ledger:
            assert ledger.list_identity_occurrences() == ()
            assert ledger.list_event_construction_reviews() == ()
            assert len(ledger.list_evidence_targets()) == target_count
            assert {p.id for p in ledger.list_proposed_changes()} == proposal_ids
        return

    _decide(journey, "established")
    if failure_stage == "proposal":
        original = SQLiteLedgerRepository.save_proposed_change

        def fail_proposal(self: SQLiteLedgerRepository, record: ProposedChange) -> None:
            if record.proposed_json.get("record_type") == "Assertion":
                raise OSError("injected proposal failure")
            original(self, record)

        with monkeypatch.context() as patch:
            patch.setattr(SQLiteLedgerRepository, "save_proposed_change", fail_proposal)
            with pytest.raises(OSError, match="injected proposal failure"):
                journey.recompose()
        with sqlite_ledger_transaction(journey.ledger) as ledger:
            assert not [
                p
                for p in ledger.list_proposed_changes()
                if p.proposed_json.get("record_type") == "Assertion"
            ]
    else:

        def fail_outcome(self: Any, record: Any) -> None:
            raise OSError("injected outcome failure")

        with monkeypatch.context() as patch:
            patch.setattr(CompositionOutcomeStore, "save", fail_outcome)
            with pytest.raises(OSError, match="injected outcome failure"):
                journey.recompose()
        with sqlite_ledger_transaction(journey.ledger) as ledger:
            proposals = [
                p
                for p in ledger.list_proposed_changes()
                if p.proposed_json.get("record_type") == "Assertion"
            ]
            assert len(proposals) == 1

    assert not (journey.state / "composition-outcomes" / f"{journey.event_id}.json").exists()
    record = journey.recompose()
    assert record.status is EventCompositionStatus.COMPOSED
    assert record.assertion is not None and record.assertion.qualifiers["time"] == "in  2012"
    with sqlite_ledger_transaction(journey.ledger) as ledger:
        proposals = [
            p
            for p in ledger.list_proposed_changes()
            if p.proposed_json.get("record_type") == "Assertion"
            and p.proposed_json.get("stable_label") == record.assertion.id
        ]
        assert len(proposals) == 1
        assert proposals[0].review_status.value == "pending"
        assert ledger.list_assertions() == ()
