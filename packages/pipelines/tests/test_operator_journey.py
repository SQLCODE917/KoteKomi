"""IRA-05: the operator journey from normal ingestion to a proposed Assertion.

One real path: normal ingestion, review packet, reviewed decision, explicit
recomposition, replay reload, and the pending Assertion ProposedChange.
Nothing here seeds composition outcomes or accepted identity occurrences.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionStatus,
    EventConstructionDecisionInput,
    EventConstructionReviewConflict,
    EventConstructionReviewError,
    EventReviewPacket,
)
from kotekomi_domain import AssertionType, AttributionBasis, IdentityOccurrenceKind, SourceAuthority
from kotekomi_pipelines import cli
from kotekomi_pipelines.event_review_workflow import (
    build_event_review_packet,
    recompose_reviewed_event,
    record_review_decision,
)
from kotekomi_pipelines.ingestion_workflow import run_ingestion_workflow

from packages.pipelines.tests.support.operator_journey_fixtures import (
    PDF_FIXTURE,
    install_ingestion_fixtures,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SOURCE_URL = "https://example.test/pdf"


class Journey:
    """One ingested development run with its selected Event."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = root / "kotekomi.toml"
        self.state = root / "state"
        self.ledger = self.state / "kotekomi.db"
        self.archive = self.state / "archive"
        self.run_id = ""
        self.event_id = ""

    def prepare(self) -> None:
        self.config.write_text(
            f'ledger_path = "{self.ledger.as_posix()}"\n'
            f'archive_path = "{self.archive.as_posix()}"\n'
            'runtime_profile = "fixture"\n'
            "[processing]\n"
            'representation_policy_version = "deposited-source-v1"\n',
            encoding="utf-8",
        )

    def ingest(self) -> Any:
        return run_ingestion_workflow(
            config_path=self.config,
            source_file_path=PDF_FIXTURE,
            source_url=SOURCE_URL,
            stdout=__import__("io").StringIO(),
            stderr=__import__("io").StringIO(),
        )

    def packet(self) -> EventReviewPacket:
        return build_event_review_packet(
            ledger_path=self.ledger,
            archive_path=self.archive,
            ingestion_run_id=self.run_id,
            event_id=self.event_id,
        )

    def decide(
        self, packet: EventReviewPacket, *, predicate: str = "shared", reviewer: str = "operator"
    ):
        candidate = packet.candidates[0]
        decision = EventConstructionDecisionInput(
            candidate_start=candidate.start,
            candidate_end=candidate.end,
            exact_text=candidate.exact_text,
            identity_kind=IdentityOccurrenceKind.ORGANIZATION,
            identity_decision="new_identity",
            identity_name=candidate.identity_name,
            existing_identity_id=None,
            predicate=predicate,
            assertion_type=AssertionType.REPORTED_OBSERVATION,
            source_authority=SourceAuthority.SECONDARY,
            attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
            reviewer=reviewer,
        )
        return record_review_decision(
            ledger_path=self.ledger,
            archive_path=self.archive,
            ingestion_run_id=self.run_id,
            event_id=self.event_id,
            decision=decision,
            now=NOW,
        )

    def recompose(self):
        return recompose_reviewed_event(
            ledger_path=self.ledger,
            archive_path=self.archive,
            ingestion_run_id=self.run_id,
            event_id=self.event_id,
            now=NOW,
        )


@pytest.fixture
def journey(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Journey:
    install_ingestion_fixtures(monkeypatch)
    runner = Journey(tmp_path)
    runner.prepare()
    result = runner.ingest()
    assert result.ingestion_code == 0
    assert result.ingestion_run_id is not None
    runner.run_id = result.ingestion_run_id
    assert result.composition_records
    runner.event_id = result.composition_records[0].event_id
    return runner


def test_normal_ingestion_persists_event_candidate_and_hold(journey: Journey) -> None:
    """IRA-01-B/C: prerequisites and the visible hold precede any review."""
    packet = journey.packet()

    assert packet.paragraph_node_id.endswith("_0012")
    assert packet.subject_text == "HealthyJoCo"
    assert (packet.subject_start, packet.subject_end) == (49, 60)
    assert packet.object_text == "Plan"
    assert (packet.object_start, packet.object_end) == (114, 118)
    assert packet.relation_label == "share"
    assert packet.candidates
    assert packet.candidates[0].subject_role is True
    assert packet.candidates[0].exact_text == "HealthyJoCo"
    assert packet.hold_reason == "assertion_inputs_unavailable"
    assert set(packet.required_decisions) == {
        "identity",
        "predicate",
        "assertion_type",
        "source_authority",
        "attribution_basis",
    }
    assert packet.accepted_identity_ids == ()

    stored = CompositionOutcomeStore(journey.state / "composition-outcomes").load(journey.event_id)
    assert stored.status is EventCompositionStatus.HELD
    assert stored.hold_reason == "assertion_inputs_unavailable"


def test_review_packet_rejects_an_event_from_another_run(journey: Journey) -> None:
    """IRA-02-C: a packet cannot bind an Event from a different run."""
    with pytest.raises(EventConstructionReviewError):
        build_event_review_packet(
            ledger_path=journey.ledger,
            archive_path=journey.archive,
            ingestion_run_id="igr_00000000000000000000000000000000",
            event_id=journey.event_id,
        )
    with pytest.raises(EventConstructionReviewError):
        build_event_review_packet(
            ledger_path=journey.ledger,
            archive_path=journey.archive,
            ingestion_run_id=journey.run_id,
            event_id="sge_000000000000000000000000",
        )


def test_packet_rejects_a_changed_source_text(journey: Journey) -> None:
    """IRA-02-C: displayed spans must match the bound source text."""
    from dataclasses import replace

    from kotekomi_application import validate_packet_bindings

    packet = journey.packet()
    changed = replace(packet, source_text=packet.source_text.replace("Plan", "Plans"))

    with pytest.raises(EventConstructionReviewError):
        validate_packet_bindings(changed)


def test_decision_accepts_prerequisites_and_is_idempotent(journey: Journey) -> None:
    """IRA-03-A/B/D: one decision, one occurrence, one review on retry."""
    packet = journey.packet()
    review = journey.decide(packet)

    assert review.reviewer == "operator"
    assert review.predicate == "shared"
    assert review.identity_occurrence_id
    assert review.subject_identity_id.startswith("org_")

    again = journey.decide(packet)
    assert again.id == review.id

    with sqlite_ledger_transaction(journey.ledger) as repository:
        identities = [actor.id for actor in repository.list_actors()] + [
            org.id for org in repository.list_organizations()
        ]
        occurrences = repository.list_identity_occurrences()
        reviews = repository.list_event_construction_reviews()
        proposals = [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "IdentityOccurrence"
        ]
    assert identities.count(review.subject_identity_id) == 1
    assert len(occurrences) == 1
    assert len(reviews) == 1
    assert len(proposals) == 1


def test_decision_rejects_a_candidate_outside_the_packet(journey: Journey) -> None:
    """IRA-03-C: a rejected decision writes nothing."""

    packet = journey.packet()
    decision = EventConstructionDecisionInput(
        candidate_start=0,
        candidate_end=4,
        exact_text="IOWA",
        identity_kind=IdentityOccurrenceKind.ORGANIZATION,
        identity_decision="new_identity",
        identity_name="IOWA",
        existing_identity_id=None,
        predicate="shared",
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        reviewer="operator",
    )
    from kotekomi_application import record_event_construction_decision

    with sqlite_ledger_transaction(journey.ledger) as repository:
        with pytest.raises(EventConstructionReviewError):
            record_event_construction_decision(packet, decision, repository, now=NOW)

    assert journey.packet().existing_review_id is None
    with sqlite_ledger_transaction(journey.ledger) as repository:
        assert repository.list_identity_occurrences() == ()


def test_conflicting_decision_is_rejected(journey: Journey) -> None:
    """IRA-03-C/D: a different decision cannot overwrite an approved one."""
    packet = journey.packet()
    journey.decide(packet)

    with pytest.raises(EventConstructionReviewConflict):
        journey.decide(packet, predicate="viewed")

    with sqlite_ledger_transaction(journey.ledger) as repository:
        reviews = repository.list_event_construction_reviews()
    assert len(reviews) == 1
    assert reviews[0].predicate == "shared"


def test_recomposition_proposes_assertion_and_replay_shows_it(journey: Journey) -> None:
    """IRA-04: recomposition proposes one Assertion and replay shows it."""
    packet = journey.packet()
    review = journey.decide(packet)
    record = journey.recompose()

    assert record.status is EventCompositionStatus.COMPOSED
    assertion = record.assertion
    assert assertion is not None
    assert assertion.status.value == "proposed"
    assert assertion.predicate == "shared"
    assert assertion.subject_entity_id == review.subject_identity_id
    assert assertion.object_value == "Plan"
    assert assertion.qualifiers == {"polarity": "affirmed", "modality": "actual"}
    assert assertion.assertion_type is AssertionType.REPORTED_OBSERVATION
    assert assertion.source_authority is SourceAuthority.SECONDARY
    assert assertion.attribution_basis is AttributionBasis.DIRECT_DOCUMENT
    assert assertion.evidence_target_ids == (review.evidence_target_id,)
    assert record.supporting_subject_span is not None
    assert record.supporting_subject_span.text == "HealthyJoCo"
    assert record.supporting_object_span is not None
    assert record.supporting_object_span.text == "Plan"

    annotations = CompositionOutcomeStore(journey.state / "composition-outcomes").annotations(
        (journey.event_id,)
    )
    assert [item.status for item in annotations] == ["composed"]
    assert annotations[0].span is not None
    assert annotations[0].span.text == "HealthyJoCo"

    with sqlite_ledger_transaction(journey.ledger) as repository:
        proposals = [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "Assertion"
        ]
    assert len(proposals) == 1
    assert proposals[0].review_status.value == "pending"
    assert proposals[0].proposed_json["stable_label"] == assertion.id
    proposed_record = proposals[0].proposed_json["record"]
    assert isinstance(proposed_record, dict)
    assert proposed_record["relation_label"] == "reviewed"


def test_recomposition_retry_keeps_one_proposal(journey: Journey) -> None:
    """IRA-04-E: retry keeps the proposal and creates no duplicate."""
    packet = journey.packet()
    journey.decide(packet)
    first = journey.recompose()
    second = journey.recompose()

    assert first.assertion is not None and second.assertion is not None
    assert first.assertion.id == second.assertion.id
    with sqlite_ledger_transaction(journey.ledger) as repository:
        proposals = [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "Assertion"
        ]
    assert len(proposals) == 1


def test_recomposition_without_a_review_keeps_the_hold(journey: Journey) -> None:
    """IRA-03-C/IRA-04: no review means no Assertion and no proposal."""
    with pytest.raises(EventConstructionReviewError):
        journey.recompose()

    stored = CompositionOutcomeStore(journey.state / "composition-outcomes").load(journey.event_id)
    assert stored.status is EventCompositionStatus.HELD
    with sqlite_ledger_transaction(journey.ledger) as repository:
        assertions = [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "Assertion"
        ]
    assert assertions == []


def test_cli_commands_drive_the_journey_without_json_authoring(
    journey: Journey, capsys: pytest.CaptureFixture[str]
) -> None:
    """IRA-02-A/IRA-03-A/IRA-04-A: the supported commands drive the journey."""
    base = ["--config", str(journey.config)]

    assert (
        cli.main(
            base
            + [
                "review",
                "event-packet",
                "--run",
                journey.run_id,
                "--event",
                journey.event_id,
            ]
        )
        == 0
    )
    packet_json = json.loads(capsys.readouterr().out)
    assert packet_json["hold_reason"] == "assertion_inputs_unavailable"
    assert packet_json["candidates"][0]["exact_text"] == "HealthyJoCo"

    assert (
        cli.main(
            base
            + [
                "review",
                "decide",
                "--run",
                journey.run_id,
                "--event",
                journey.event_id,
                "--candidate-text",
                "HealthyJoCo",
                "--identity-kind",
                "organization",
                "--identity",
                "new:HealthyJoCo",
                "--predicate",
                "shared",
                "--assertion-type",
                "reported_observation",
                "--source-authority",
                "secondary",
                "--attribution-basis",
                "direct_document",
                "--reviewer",
                "operator",
            ]
        )
        == 0
    )
    decided = json.loads(capsys.readouterr().out)
    assert decided["predicate"] == "shared"

    assert (
        cli.main(
            base
            + [
                "review",
                "recompose",
                "--run",
                journey.run_id,
                "--event",
                journey.event_id,
            ]
        )
        == 0
    )
    recomposed = json.loads(capsys.readouterr().out)
    assert recomposed["status"] == "composed"
    assert recomposed["assertion_status"] == "proposed"
    assert recomposed["predicate"] == "shared"
