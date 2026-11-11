"""Complete captured announcement through supported review and disposable acceptance."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from pathlib import Path
from threading import Event
from time import perf_counter
from unittest.mock import patch

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionStatus,
    EventConstructionDecisionInput,
    ReviewProposedChangeInput,
    approve_proposed_change,
    build_constituent_candidate_inventory,
)
from kotekomi_application.composition_inspection import composition_inspection_records
from kotekomi_application.evidence_targets import validate_evidence_target_record
from kotekomi_application.ingestion_inspection import ParagraphSnapshot
from kotekomi_domain import AssertionType, AttributionBasis, IdentityOccurrenceKind, SourceAuthority
from kotekomi_pipelines import event_review_workflow
from kotekomi_pipelines.event_review_workflow import record_review_decision
from kotekomi_pipelines.ingestion_token_artifact import load_ingestion_token_artifact
from kotekomi_pipelines.replay_reader.live import create_inspection_session
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs

from packages.application.tests.test_announcement_completion import (
    EVENT,
    EXPECTED_OBJECT,
    EXPECTED_SUBJECT,
)
from packages.pipelines.tests.test_ipi_production_promotion import RUN, _seed_capture
from packages.pipelines.tests.test_operator_journey import NOW, Journey

FIXTURE = Path(__file__).parent / "fixtures" / "announcement"


def test_complete_announcement_review_acceptance_and_saved_replay(tmp_path: Path) -> None:
    """Agent-reviewed Source report; this is development evidence, not independent validation."""
    journey = Journey(tmp_path)
    _seed_capture(journey, overlay=FIXTURE)
    journey.event_id = EVENT
    packet = journey.packet()
    assert packet.subject_text == EXPECTED_SUBJECT
    assert packet.object_text == EXPECTED_OBJECT
    assert packet.time_qualifier_text == "In  December  2025"
    assert (packet.statement_start, packet.statement_end) == (0, 155)
    assert not packet.accepted_identity_ids
    assert packet.object_completion is not None
    assert packet.object_completion.selected_object_range.text == "GenAI.mil"
    candidate = next(c for c in packet.candidates if c.exact_text == "Pete  Hegseth")
    decision = EventConstructionDecisionInput(
        candidate_start=candidate.start,
        candidate_end=candidate.end,
        exact_text=candidate.exact_text,
        identity_kind=IdentityOccurrenceKind.ACTOR,
        identity_decision="new_identity",
        existing_identity_id=None,
        identity_name="Pete Hegseth",
        predicate="announced",
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        reviewer="delegated-agent-development-review",
    )
    review = record_review_decision(
        ledger_path=journey.ledger,
        archive_path=journey.archive,
        ingestion_run_id=RUN,
        event_id=EVENT,
        now=NOW,
        decision=decision,
    )
    with (
        patch.object(
            event_review_workflow,
            "load_paragraph_inputs",
            wraps=load_paragraph_inputs,
        ) as paragraphs_loaded,
        patch.object(
            event_review_workflow,
            "load_ingestion_token_artifact",
            wraps=load_ingestion_token_artifact,
        ) as tokens_loaded,
        patch.object(
            event_review_workflow,
            "build_constituent_candidate_inventory",
            wraps=build_constituent_candidate_inventory,
        ) as inventory_built,
    ):
        started = perf_counter()
        result = journey.recompose()
        print(f"announcement first recomposition: {perf_counter() - started:.6f}s")
        assert paragraphs_loaded.call_count == 1
        assert tokens_loaded.call_count == 1
        assert inventory_built.call_count == 1
        started = perf_counter()
        assert journey.recompose().assertion == result.assertion
        print(f"announcement retry recomposition: {perf_counter() - started:.6f}s")
        assert paragraphs_loaded.call_count == 2
        assert tokens_loaded.call_count == 2
        assert inventory_built.call_count == 2
    artifact_path = journey.state / "token-artifacts" / f"{packet.paragraph_node_id}.json"
    artifact_bytes = artifact_path.read_bytes()
    corrupted = json.loads(artifact_bytes)
    corrupted["source_text_sha256"] = "f" * 64
    try:
        artifact_path.write_text(json.dumps(corrupted))
        with pytest.raises(ValueError, match="Token artifact source digest does not match"):
            journey.recompose()
    finally:
        artifact_path.write_bytes(artifact_bytes)
    assert result.status is EventCompositionStatus.COMPOSED
    assertion = result.assertion
    assert assertion is not None
    assert assertion.subject_entity_id == review.subject_identity_id
    assert assertion.predicate == "announced"
    assert assertion.object_value == EXPECTED_OBJECT
    assert assertion.qualifiers == {
        "time": "In  December  2025",
        "polarity": "affirmed",
        "modality": "actual",
    }
    assert result.supporting_subject_span is not None
    assert result.supporting_subject_span.text == EXPECTED_SUBJECT
    assert result.supporting_object_span is not None
    assert result.supporting_object_span.text == EXPECTED_OBJECT
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
        for target_id in assertion.evidence_target_ids:
            target = ledger.get_evidence_target(target_id)
            assert target is not None
            validate_evidence_target_record(target, ledger)
            assert target.exact_text == packet.source_text[:155]
        # Delegated semantic assessment: the Source explicitly reports the announcement,
        # including platform description and month/year. This accepts a source_report.
        accepted = approve_proposed_change(
            ReviewProposedChangeInput(
                proposed_change_id=proposal.id,
                reviewer="delegated-agent-development-review",
                reviewed_at=NOW,
                canonical_predicate="announced",
            ),
            ledger,
        )
    with sqlite_ledger_transaction(journey.ledger) as ledger:
        stored = ledger.get_assertion(assertion.id)
        assert stored is not None
        assert stored.status.value == "reported"
        assert stored.epistemic_scope.value == "source_report"
        assert stored.subject_entity_id == assertion.subject_entity_id
        assert stored.subject_entity_id is not None
        assert ledger.get_actor(stored.subject_entity_id) is not None
        assert stored.predicate == "announced"
        assert stored.object_value == EXPECTED_OBJECT
        assert stored.qualifiers == assertion.qualifiers
        reviewed = ledger.get_proposed_change(proposal.id)
        assert reviewed is not None and reviewed.review_status.value == "approved"
        assert accepted.provenance_activity_id in stored.provenance_activity_ids
        activity = ledger.get_provenance_activity(accepted.provenance_activity_id)
        assert activity is not None and stored.id in activity.output_ids
        assert len(accepted.assertion_evidence_link_ids) == 1
        for link_id in accepted.assertion_evidence_link_ids:
            link = ledger.get_assertion_evidence_link(link_id)
            assert link is not None and link.assertion_id == stored.id
            target = ledger.get_evidence_target(link.evidence_target_id)
            assert target is not None
            validate_evidence_target_record(target, ledger)
            assert target.exact_text == packet.source_text[:155]
    assert CompositionOutcomeStore(journey.state / "composition-outcomes").load(EVENT) == result
    paragraphs = load_paragraph_inputs(journey.ledger, journey.archive, ingestion_run_id=RUN)
    assert len(paragraphs) == 1
    snapshots: list[ParagraphSnapshot] = []
    session = create_inspection_session(journey.ledger, on_snapshot=snapshots.append)
    session.replay_stored(paragraphs, None, 0.0, Event())
    assert not session.presentation_failed
    rows = [
        row
        for snapshot in snapshots
        for row in composition_inspection_records(snapshot.profile)
        if row.record_id == assertion.id
    ]
    assert rows
    assert rows[-1].data["qualifiers"] == assertion.qualifiers
    assert rows[-1].data["proposals"] == [{"id": proposal.id, "review_status": "approved"}]
