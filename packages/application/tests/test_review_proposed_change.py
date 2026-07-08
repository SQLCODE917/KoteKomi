from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    ReviewProposedChangeInput,
    approve_proposed_change,
    edit_proposed_change,
    reject_proposed_change,
)
from kotekomi_domain import (
    Actor,
    Assertion,
    AssertionStatus,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    ReviewStatus,
)
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


class FakeReviewLedger:
    def __init__(self, proposed_changes: tuple[ProposedChange, ...]) -> None:
        self.proposed_changes = {record.id: record for record in proposed_changes}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}
        self.actors: dict[str, Actor] = {}
        self.organizations: dict[str, Organization] = {}
        self.events: dict[str, Event] = {}
        self.evidence_spans: dict[str, EvidenceSpan] = {}
        self.assertions: dict[str, Assertion] = {}
        self.relationships: dict[str, Relationship] = {}
        self.outcomes: dict[str, Outcome] = {}

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposed_changes[record.id] = record

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record

    def get_actor(self, record_id: str) -> Actor | None:
        return self.actors.get(record_id)

    def save_actor(self, record: Actor) -> None:
        self.actors[record.id] = record

    def get_organization(self, record_id: str) -> Organization | None:
        return self.organizations.get(record_id)

    def save_organization(self, record: Organization) -> None:
        self.organizations[record.id] = record

    def get_event(self, record_id: str) -> Event | None:
        return self.events.get(record_id)

    def save_event(self, record: Event) -> None:
        self.events[record.id] = record

    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None:
        return self.evidence_spans.get(record_id)

    def save_evidence_span(self, record: EvidenceSpan) -> None:
        self.evidence_spans[record.id] = record

    def get_assertion(self, record_id: str) -> Assertion | None:
        return self.assertions.get(record_id)

    def save_assertion(self, record: Assertion) -> None:
        self.assertions[record.id] = record

    def get_relationship(self, record_id: str) -> Relationship | None:
        return self.relationships.get(record_id)

    def save_relationship(self, record: Relationship) -> None:
        self.relationships[record.id] = record

    def get_outcome(self, record_id: str) -> Outcome | None:
        return self.outcomes.get(record_id)

    def save_outcome(self, record: Outcome) -> None:
        self.outcomes[record.id] = record


def proposed_change(
    record_id: str,
    record_type: str,
    record: dict[str, JsonValue],
    review_status: ReviewStatus = ReviewStatus.PENDING,
) -> ProposedChange:
    return ProposedChange(
        id=record_id,
        review_status=review_status,
        proposed_json={
            "record_type": record_type,
            "stable_label": record_id.removeprefix("pcg_"),
            "record": record,
            "evidence": {
                "selector_type": "exact_text",
                "exact_text": "evidence text",
                "source_id": "src_article_a",
                "document_id": "doc_article_a",
            },
        },
        source_id="src_article_a",
        document_id="doc_article_a",
        model_name="fixture-extraction-runtime",
        prompt_id="propose_assertions",
        provenance_activity_id="prv_model_run",
        created_at=NOW,
        updated_at=NOW,
    )


def review_input(proposed_change_id: str) -> ReviewProposedChangeInput:
    return ReviewProposedChangeInput(
        proposed_change_id=proposed_change_id,
        reviewer="analyst",
        reviewed_at=NOW,
    )


@pytest.mark.parametrize(
    ("record_id", "record_type", "record", "store_name", "accepted_id"),
    (
        (
            "pcg_actor",
            "Actor",
            {
                "id": "act_dario_amodei",
                "name": "Dario Amodei",
                "role_names": ["Anthropic executive"],
                "organization_ids": ["org_anthropic"],
            },
            "actors",
            "act_dario_amodei",
        ),
        (
            "pcg_organization",
            "Organization",
            {
                "id": "org_anthropic",
                "name": "Anthropic",
                "organization_type": "ai_lab",
            },
            "organizations",
            "org_anthropic",
        ),
        (
            "pcg_event",
            "Event",
            {
                "id": "evt_release_review",
                "name": "Release review",
                "start_at": "2026-06-21T00:00:00Z",
                "participant_actor_ids": ["act_dario_amodei"],
                "participant_organization_ids": ["org_anthropic"],
            },
            "events",
            "evt_release_review",
        ),
        (
            "pcg_evidence",
            "EvidenceSpan",
            {
                "id": "evs_delay",
                "source_id": "src_article_a",
                "document_id": "doc_article_a",
                "assertion_id": "ast_delay",
                "selector_type": "exact_text",
                "exact_text": "Anthropic postponed the rollout.",
            },
            "evidence_spans",
            "evs_delay",
        ),
        (
            "pcg_relationship",
            "Relationship",
            {
                "id": "rel_review_influenced_rollout",
                "subject_id": "org_commerce_department",
                "predicate": "influenced_release_timing_for",
                "object_id": "org_anthropic",
                "assertion_ids": ["ast_delay"],
            },
            "relationships",
            "rel_review_influenced_rollout",
        ),
        (
            "pcg_outcome",
            "Outcome",
            {
                "id": "out_access_restored",
                "description": "Anthropic restored most access.",
                "organization_ids": ["org_anthropic"],
                "event_ids": ["evt_release_review"],
                "assertion_ids": ["ast_delay"],
            },
            "outcomes",
            "out_access_restored",
        ),
    ),
)
def test_approve_proposed_change_creates_accepted_record(
    record_id: str,
    record_type: str,
    record: dict[str, JsonValue],
    store_name: str,
    accepted_id: str,
) -> None:
    ledger = FakeReviewLedger((proposed_change(record_id, record_type, record),))

    result = approve_proposed_change(review_input(record_id), ledger)

    reviewed_change = ledger.proposed_changes[record_id]
    accepted_store = cast(dict[str, object], getattr(ledger, store_name))
    provenance_activity = ledger.provenance_activities[result.provenance_activity_id]
    assert result.review_status is ReviewStatus.APPROVED
    assert result.accepted_record_id == accepted_id
    assert result.accepted_record_type == record_type
    assert accepted_id in accepted_store
    assert reviewed_change.review_status is ReviewStatus.APPROVED
    assert reviewed_change.accepted_json is not None
    assert reviewed_change.accepted_json["id"] == accepted_id
    assert provenance_activity.activity_type == "proposed_change_approved"
    assert provenance_activity.agent == "analyst"
    assert provenance_activity.input_ids == (record_id,)
    assert provenance_activity.output_ids == (accepted_id,)


def test_approve_proposed_assertion_marks_it_reported_and_adds_review_provenance() -> None:
    record_id = "pcg_assertion"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Assertion",
                {
                    "id": "ast_delay",
                    "assertion_type": "source_claim",
                    "subject_entity_id": "org_anthropic",
                    "predicate": "postponed_rollout",
                    "object_value": {"model": "Claude Fable 5"},
                    "status": "proposed",
                    "source_ids": ["src_article_a"],
                    "evidence_span_ids": ["evs_delay"],
                    "provenance_activity_ids": [],
                },
            ),
        )
    )

    result = approve_proposed_change(review_input(record_id), ledger)

    assertion = ledger.assertions["ast_delay"]
    reviewed_change = ledger.proposed_changes[record_id]
    assert assertion.status is AssertionStatus.REPORTED
    assert assertion.provenance_activity_ids == (result.provenance_activity_id,)
    assert reviewed_change.accepted_json is not None
    assert reviewed_change.accepted_json["status"] == "reported"
    assert reviewed_change.accepted_json["provenance_activity_ids"] == [
        result.provenance_activity_id
    ]


def test_reject_proposed_change_updates_status_without_accepted_record() -> None:
    record_id = "pcg_actor"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Actor",
                {
                    "id": "act_dario_amodei",
                    "name": "Dario Amodei",
                },
            ),
        )
    )

    result = reject_proposed_change(
        ReviewProposedChangeInput(
            proposed_change_id=record_id,
            reviewer="analyst",
            reviewed_at=NOW,
            reason="duplicate",
        ),
        ledger,
    )

    reviewed_change = ledger.proposed_changes[record_id]
    provenance_activity = ledger.provenance_activities[result.provenance_activity_id]
    assert result.review_status is ReviewStatus.REJECTED
    assert result.accepted_record_id is None
    assert reviewed_change.review_status is ReviewStatus.REJECTED
    assert reviewed_change.accepted_json is None
    assert ledger.actors == {}
    assert provenance_activity.activity_type == "proposed_change_rejected"
    assert provenance_activity.input_ids == (record_id,)
    assert provenance_activity.output_ids == (record_id,)


def test_edit_proposed_change_creates_accepted_record_from_corrected_json() -> None:
    record_id = "pcg_actor"
    proposed_record: dict[str, JsonValue] = {
        "id": "act_dario_amodei",
        "name": "D. Amodei",
        "role_names": ["executive"],
        "organization_ids": ["org_anthropic"],
    }
    edited_record: dict[str, JsonValue] = {
        "id": "act_dario_amodei",
        "name": "Dario Amodei",
        "role_names": ["Anthropic chief executive"],
        "organization_ids": ["org_anthropic"],
    }
    ledger = FakeReviewLedger((proposed_change(record_id, "Actor", proposed_record),))

    result = edit_proposed_change(
        ReviewProposedChangeInput(
            proposed_change_id=record_id,
            reviewer="analyst",
            reviewed_at=NOW,
            accepted_record_json=edited_record,
        ),
        ledger,
    )

    reviewed_change = ledger.proposed_changes[record_id]
    actor = ledger.actors["act_dario_amodei"]
    provenance_activity = ledger.provenance_activities[result.provenance_activity_id]
    assert result.review_status is ReviewStatus.EDITED
    assert result.accepted_record_id == "act_dario_amodei"
    assert result.accepted_record_type == "Actor"
    assert actor.name == "Dario Amodei"
    assert actor.role_names == ("Anthropic chief executive",)
    assert reviewed_change.review_status is ReviewStatus.EDITED
    assert (
        reviewed_change.original_proposed_json
        == proposed_change(record_id, "Actor", proposed_record).proposed_json
    )
    assert reviewed_change.accepted_json is not None
    assert reviewed_change.accepted_json["name"] == "Dario Amodei"
    assert provenance_activity.activity_type == "proposed_change_edited"
    assert provenance_activity.input_ids == (record_id,)
    assert provenance_activity.output_ids == ("act_dario_amodei",)


def test_edit_proposed_assertion_marks_it_reported_and_adds_review_provenance() -> None:
    record_id = "pcg_assertion"
    edited_record: dict[str, JsonValue] = {
        "id": "ast_delay",
        "assertion_type": "source_claim",
        "subject_entity_id": "org_anthropic",
        "predicate": "postponed_rollout",
        "object_value": {"model": "Claude Fable 5", "timing": "late June"},
        "status": "proposed",
        "source_report_confidence": 0.91,
        "extraction_confidence": 0.84,
        "world_truth_confidence": 0.62,
        "current_assessment": "The Source reports a delayed rollout after review.",
        "source_ids": ["src_article_a"],
        "evidence_span_ids": ["evs_delay"],
        "provenance_activity_ids": [],
    }
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Assertion",
                {
                    "id": "ast_delay",
                    "assertion_type": "source_claim",
                    "subject_entity_id": "org_anthropic",
                    "predicate": "postponed_rollout",
                    "object_value": {"model": "Claude Fable 5"},
                    "status": "proposed",
                    "source_ids": ["src_article_a"],
                    "evidence_span_ids": ["evs_delay"],
                    "provenance_activity_ids": [],
                },
            ),
        )
    )

    result = edit_proposed_change(
        ReviewProposedChangeInput(
            proposed_change_id=record_id,
            reviewer="analyst",
            reviewed_at=NOW,
            accepted_record_json=edited_record,
        ),
        ledger,
    )

    assertion = ledger.assertions["ast_delay"]
    reviewed_change = ledger.proposed_changes[record_id]
    assert assertion.status is AssertionStatus.REPORTED
    assert assertion.provenance_activity_ids == (result.provenance_activity_id,)
    assert assertion.current_assessment == "The Source reports a delayed rollout after review."
    assert reviewed_change.review_status is ReviewStatus.EDITED
    assert reviewed_change.accepted_json is not None
    assert reviewed_change.accepted_json["status"] == "reported"
    assert reviewed_change.accepted_json["provenance_activity_ids"] == [
        result.provenance_activity_id
    ]


def test_edit_rejects_missing_accepted_record_json() -> None:
    record_id = "pcg_actor"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Actor",
                {"id": "act_dario_amodei", "name": "Dario Amodei"},
            ),
        )
    )

    with pytest.raises(ValueError, match="requires accepted_record_json"):
        edit_proposed_change(review_input(record_id), ledger)


def test_edit_rejects_invalid_accepted_record_json() -> None:
    record_id = "pcg_actor"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Actor",
                {"id": "act_dario_amodei", "name": "Dario Amodei"},
            ),
        )
    )

    with pytest.raises(ValueError):
        edit_proposed_change(
            ReviewProposedChangeInput(
                proposed_change_id=record_id,
                reviewer="analyst",
                reviewed_at=NOW,
                accepted_record_json={"id": "plc_washington", "name": "Washington"},
            ),
            ledger,
        )


def test_review_rejects_missing_proposed_change() -> None:
    ledger = FakeReviewLedger(())

    with pytest.raises(ValueError, match="ProposedChange not found"):
        approve_proposed_change(review_input("pcg_missing"), ledger)


def test_review_rejects_non_pending_proposed_change() -> None:
    record_id = "pcg_actor"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Actor",
                {"id": "act_dario_amodei", "name": "Dario Amodei"},
                ReviewStatus.REJECTED,
            ),
        )
    )

    with pytest.raises(ValueError, match="ProposedChange is not pending"):
        reject_proposed_change(review_input(record_id), ledger)


def test_approve_rejects_unsupported_record_type() -> None:
    record_id = "pcg_place"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Place",
                {"id": "plc_washington", "name": "Washington"},
            ),
        )
    )

    with pytest.raises(ValueError, match="Unsupported ProposedChange record_type: Place"):
        approve_proposed_change(review_input(record_id), ledger)
