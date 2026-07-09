from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    ReviewEditableRecordExportInput,
    ReviewPacketInput,
    ReviewQueueInput,
    ReviewReadinessInput,
    ReviewReferenceResolution,
    export_review_editable_record,
    get_review_packet,
    get_review_readiness,
    list_review_queue,
    review_packet_to_json,
    review_queue_result_to_json,
    review_readiness_to_json,
)
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    Document,
    Entity,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProposedChange,
    Relationship,
    ReviewStatus,
    SelectorType,
    Source,
    SourceType,
)
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


class FakeReviewQueueLedger:
    def __init__(self, proposed_changes: tuple[ProposedChange, ...]) -> None:
        self.proposed_changes = {record.id: record for record in proposed_changes}
        self.sources: dict[str, Source] = {}
        self.documents: dict[str, Document] = {}
        self.entities: dict[str, Entity] = {}
        self.actors: dict[str, Actor] = {}
        self.organizations: dict[str, Organization] = {}
        self.places: dict[str, Place] = {}
        self.events: dict[str, Event] = {}
        self.evidence_spans: dict[str, EvidenceSpan] = {}
        self.assertions: dict[str, Assertion] = {}
        self.relationships: dict[str, Relationship] = {}
        self.outcomes: dict[str, Outcome] = {}
        self.argument_edges: dict[str, ArgumentEdge] = {}

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def list_proposed_changes(self) -> tuple[ProposedChange, ...]:
        return tuple(self.proposed_changes.values())

    def get_source(self, record_id: str) -> Source | None:
        return self.sources.get(record_id)

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_entity(self, record_id: str) -> Entity | None:
        return self.entities.get(record_id)

    def get_actor(self, record_id: str) -> Actor | None:
        return self.actors.get(record_id)

    def get_organization(self, record_id: str) -> Organization | None:
        return self.organizations.get(record_id)

    def get_event(self, record_id: str) -> Event | None:
        return self.events.get(record_id)

    def get_place(self, record_id: str) -> Place | None:
        return self.places.get(record_id)

    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None:
        return self.evidence_spans.get(record_id)

    def get_assertion(self, record_id: str) -> Assertion | None:
        return self.assertions.get(record_id)

    def get_relationship(self, record_id: str) -> Relationship | None:
        return self.relationships.get(record_id)

    def get_outcome(self, record_id: str) -> Outcome | None:
        return self.outcomes.get(record_id)

    def get_argument_edge(self, record_id: str) -> ArgumentEdge | None:
        return self.argument_edges.get(record_id)


def test_review_queue_defaults_to_pending_and_sorts_by_review_order() -> None:
    ledger = FakeReviewQueueLedger(
        (
            proposed_change("pcg_assertion", "Assertion", assertion_json()),
            proposed_change(
                "pcg_approved_actor",
                "Actor",
                actor_json("act_approved", "Approved Actor"),
                review_status=ReviewStatus.APPROVED,
            ),
            proposed_change(
                "pcg_actor",
                "Actor",
                actor_json("act_dario_amodei", "Dario Amodei"),
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                organization_json(),
            ),
        )
    )

    result = list_review_queue(ReviewQueueInput(), ledger)

    assert [item.record_type for item in result.items] == [
        "Organization",
        "Actor",
        "Assertion",
    ]
    assert [item.proposed_change_id for item in result.items] == [
        "pcg_organization",
        "pcg_actor",
        "pcg_assertion",
    ]


def test_review_queue_filters_by_status_type_source_and_document() -> None:
    ledger = FakeReviewQueueLedger(
        (
            proposed_change("pcg_actor", "Actor", actor_json("act_a", "Actor A")),
            proposed_change(
                "pcg_rejected_assertion",
                "Assertion",
                assertion_json(),
                review_status=ReviewStatus.REJECTED,
            ),
            proposed_change(
                "pcg_other_source",
                "Assertion",
                assertion_json("ast_other_source"),
                source_id="src_other",
                document_id="doc_other",
            ),
        )
    )

    result = list_review_queue(
        ReviewQueueInput(
            review_status=ReviewStatus.REJECTED,
            record_type="Assertion",
            source_id="src_article_a",
            document_id="doc_article_a",
        ),
        ledger,
    )

    assert [item.proposed_change_id for item in result.items] == ["pcg_rejected_assertion"]


def test_review_packet_includes_evidence_assertion_context_and_reference_resolution() -> None:
    pending_evidence_change = proposed_change(
        "pcg_evidence",
        "EvidenceSpan",
        evidence_span_json("evs_pending"),
        stable_label="pending_evidence",
    )
    assertion_change = proposed_change(
        "pcg_assertion",
        "Assertion",
        assertion_json(evidence_span_ids=["evs_accepted", "evs_pending", "evs_missing"]),
    )
    ledger = seeded_ledger((pending_evidence_change, assertion_change))
    ledger.evidence_spans["evs_accepted"] = EvidenceSpan(
        id="evs_accepted",
        source_id="src_article_a",
        document_id="doc_article_a",
        selector_type=SelectorType.EXACT_TEXT,
        exact_text="Accepted evidence text.",
        prefix_text="Accepted prefix.",
        suffix_text="Accepted suffix.",
        location={"section": "accepted"},
    )

    packet = get_review_packet(ReviewPacketInput("pcg_assertion"), ledger)

    assert packet.record_type == "Assertion"
    assert packet.assertion_context is not None
    assert packet.assertion_context.epistemic_scope == "source_report"
    assert packet.assertion_context.source_authority == "secondary"
    assert packet.assertion_context.attribution_basis == "reported_by_source"
    assert packet.assertion_context.source_report_confidence == 0.91
    assert {context.exact_text for context in packet.evidence_contexts} == {
        "Model evidence text.",
        "Accepted evidence text.",
        "Pending evidence text.",
    }
    resolutions = {
        (reference.referenced_type, reference.referenced_id): reference.resolution_status
        for reference in packet.reference_contexts
    }
    assert resolutions[("Organization", "org_anthropic")] is ReviewReferenceResolution.ACCEPTED
    assert resolutions[("Source", "src_article_a")] is ReviewReferenceResolution.ACCEPTED
    assert resolutions[("EvidenceSpan", "evs_accepted")] is ReviewReferenceResolution.ACCEPTED
    assert resolutions[("EvidenceSpan", "evs_pending")] is ReviewReferenceResolution.PENDING
    assert resolutions[("EvidenceSpan", "evs_missing")] is ReviewReferenceResolution.MISSING


def test_review_packet_fails_fast_on_malformed_or_unsupported_proposed_change() -> None:
    malformed = ProposedChange(
        id="pcg_malformed",
        proposed_json={"record_type": "Assertion", "stable_label": "malformed"},
        created_at=NOW,
        updated_at=NOW,
    )
    unsupported = proposed_change(
        "pcg_place",
        "Place",
        {"id": "plc_washington", "name": "Washington"},
    )

    malformed_ledger = FakeReviewQueueLedger((malformed,))
    unsupported_ledger = FakeReviewQueueLedger((unsupported,))

    with pytest.raises(ValueError, match="missing record object"):
        get_review_packet(ReviewPacketInput("pcg_malformed"), malformed_ledger)
    with pytest.raises(ValueError, match="Unsupported ProposedChange record_type: Place"):
        get_review_packet(ReviewPacketInput("pcg_place"), unsupported_ledger)


def test_export_review_editable_record_returns_only_proposed_record_json() -> None:
    ledger = seeded_ledger((proposed_change("pcg_actor", "Actor", actor_json()),))

    result = export_review_editable_record(ReviewEditableRecordExportInput("pcg_actor"), ledger)

    assert result.proposed_change_id == "pcg_actor"
    assert result.record_type == "Actor"
    assert result.stable_label == "pcg_actor"
    assert result.record_json == actor_json()
    assert "record_type" not in result.record_json
    assert "stable_label" not in result.record_json
    assert "record" not in result.record_json


def test_review_readiness_reports_pending_and_missing_references() -> None:
    pending_evidence_change = proposed_change(
        "pcg_evidence",
        "EvidenceSpan",
        evidence_span_json("evs_pending"),
        stable_label="pending_evidence",
    )
    assertion_change = proposed_change(
        "pcg_assertion",
        "Assertion",
        assertion_json(evidence_span_ids=["evs_pending", "evs_missing"]),
    )
    ledger = seeded_ledger((pending_evidence_change, assertion_change))

    status = get_review_readiness(ReviewReadinessInput(), ledger)

    assert status.review_required is True
    assert status.pending_count == 2
    assert status.pending_record_type_counts == {"Assertion": 1, "EvidenceSpan": 1}
    assert status.pending_reference_count == 1
    assert status.missing_reference_count == 1
    assert status.can_project_graph is False
    assert status.can_generate_briefing is False
    assert status.next_recommended_command == "kotekomi review list"
    blocker_keys = {
        (blocker.proposed_change_id, blocker.referenced_type, blocker.referenced_id)
        for blocker in status.blockers
    }
    assert ("pcg_assertion", "EvidenceSpan", "evs_pending") in blocker_keys
    assert ("pcg_assertion", "EvidenceSpan", "evs_missing") in blocker_keys


def test_review_readiness_reports_downstream_ready_when_no_pending_records() -> None:
    ledger = seeded_ledger(())

    status = get_review_readiness(ReviewReadinessInput(), ledger)

    assert status.review_required is False
    assert status.pending_count == 0
    assert status.pending_record_type_counts == {}
    assert status.pending_reference_count == 0
    assert status.missing_reference_count == 0
    assert status.can_project_graph is True
    assert status.can_generate_briefing is True
    assert status.next_recommended_command == "kotekomi graph project"
    assert status.blockers == ()


def test_review_readiness_filters_by_type_source_and_document() -> None:
    ledger = seeded_ledger(
        (
            proposed_change("pcg_actor", "Actor", actor_json()),
            proposed_change(
                "pcg_assertion",
                "Assertion",
                assertion_json(),
            ),
            proposed_change(
                "pcg_other_source_assertion",
                "Assertion",
                assertion_json("ast_other_source"),
                source_id="src_other",
                document_id="doc_other",
            ),
        )
    )

    status = get_review_readiness(
        ReviewReadinessInput(
            record_type="Assertion",
            source_id="src_article_a",
            document_id="doc_article_a",
        ),
        ledger,
    )

    assert status.pending_count == 1
    assert status.pending_record_type_counts == {"Assertion": 1}


def test_review_state_json_serializers_return_structured_objects() -> None:
    assertion_change = proposed_change(
        "pcg_assertion",
        "Assertion",
        assertion_json(evidence_span_ids=["evs_missing"]),
    )
    ledger = seeded_ledger((assertion_change,))
    queue = list_review_queue(ReviewQueueInput(), ledger)
    packet = get_review_packet(ReviewPacketInput("pcg_assertion"), ledger)
    readiness = get_review_readiness(ReviewReadinessInput(), ledger)

    queue_json = review_queue_result_to_json(queue)
    packet_json = review_packet_to_json(packet)
    readiness_json = review_readiness_to_json(readiness)

    queue_items = cast(list[dict[str, JsonValue]], queue_json["items"])
    assert isinstance(queue_items, list)
    assert queue_items[0]["review_status"] == "pending"
    assert packet_json["review_status"] == "pending"
    assert isinstance(packet_json["reference_contexts"], list)
    assert packet_json["assertion_context"] == {
        "attribution_basis": "reported_by_source",
        "causal_confidence": None,
        "epistemic_scope": "source_report",
        "extraction_confidence": 0.89,
        "source_authority": "secondary",
        "source_report_confidence": 0.91,
        "world_truth_confidence": 0.62,
    }
    assert readiness_json["review_required"] is True
    assert readiness_json["pending_count"] == 1
    assert isinstance(readiness_json["blockers"], list)


def seeded_ledger(proposed_changes: tuple[ProposedChange, ...]) -> FakeReviewQueueLedger:
    ledger = FakeReviewQueueLedger(proposed_changes)
    ledger.sources["src_article_a"] = Source(
        id="src_article_a",
        source_type=SourceType.ARTICLE,
        title="Article A",
    )
    ledger.documents["doc_article_a"] = Document(
        id="doc_article_a",
        source_id="src_article_a",
        raw_path="sources/raw/src_article_a.bin",
        extracted_text_path="documents/extracted/doc_article_a.txt",
        content_sha256="a" * 64,
    )
    ledger.organizations["org_anthropic"] = Organization(id="org_anthropic", name="Anthropic")
    return ledger


def proposed_change(
    proposed_change_id: str,
    record_type: str,
    record: dict[str, JsonValue],
    *,
    stable_label: str | None = None,
    review_status: ReviewStatus = ReviewStatus.PENDING,
    source_id: str = "src_article_a",
    document_id: str = "doc_article_a",
) -> ProposedChange:
    return ProposedChange(
        id=proposed_change_id,
        review_status=review_status,
        proposed_json={
            "record_type": record_type,
            "stable_label": stable_label or proposed_change_id,
            "record": record,
            "evidence": {
                "selector_type": "exact_text",
                "exact_text": "Model evidence text.",
                "prefix_text": "Model prefix.",
                "suffix_text": "Model suffix.",
                "location": {"section": "model"},
                "source_id": source_id,
                "document_id": document_id,
            },
        },
        source_id=source_id,
        document_id=document_id,
        model_name="fixture-extraction-runtime",
        prompt_id="propose_assertions",
        provenance_activity_id="prv_model_run",
        created_at=NOW,
        updated_at=NOW,
    )


def actor_json(
    actor_id: str = "act_dario_amodei",
    name: str = "Dario Amodei",
) -> dict[str, JsonValue]:
    return {
        "id": actor_id,
        "name": name,
        "role_names": ["Anthropic executive"],
        "organization_ids": ["org_anthropic"],
    }


def organization_json() -> dict[str, JsonValue]:
    return {
        "id": "org_anthropic",
        "name": "Anthropic",
        "organization_type": "ai_lab",
    }


def evidence_span_json(evidence_span_id: str) -> dict[str, JsonValue]:
    return {
        "id": evidence_span_id,
        "source_id": "src_article_a",
        "document_id": "doc_article_a",
        "assertion_id": None,
        "selector_type": "exact_text",
        "exact_text": "Pending evidence text.",
        "prefix_text": "Pending prefix.",
        "suffix_text": "Pending suffix.",
        "location": {"section": "pending"},
    }


def assertion_json(
    assertion_id: str = "ast_delay",
    *,
    evidence_span_ids: list[str] | None = None,
) -> dict[str, JsonValue]:
    evidence_ids: list[JsonValue] = list(evidence_span_ids or ["evs_accepted"])
    return {
        "id": assertion_id,
        "assertion_type": "source_claim",
        "epistemic_scope": "source_report",
        "subject_entity_id": "org_anthropic",
        "predicate": "postponed_rollout",
        "object_value": {"model": "Claude Fable 5"},
        "status": "proposed",
        "source_authority": "secondary",
        "attribution_basis": "reported_by_source",
        "source_report_confidence": 0.91,
        "extraction_confidence": 0.89,
        "world_truth_confidence": 0.62,
        "source_ids": ["src_article_a"],
        "evidence_span_ids": evidence_ids,
        "provenance_activity_ids": [],
    }
