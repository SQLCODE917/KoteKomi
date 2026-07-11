import hashlib
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    ReviewDrainInput,
    ReviewDrainStoppedReason,
    ReviewNextDecision,
    ReviewNextDecisionInput,
    ReviewProposedChangeInput,
    approve_proposed_change,
    edit_proposed_change,
    reject_proposed_change,
    review_drain_result_to_json,
    review_next_decision_result_to_json,
    run_review_drain,
    run_review_next_decision,
)
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionEvidenceLink,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    Entity,
    EpistemicScope,
    Event,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    Organization,
    Outcome,
    ParseQualityReport,
    Place,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
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
from kotekomi_domain.models import JsonValue

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


class FakeReviewLedger:
    def __init__(self, proposed_changes: tuple[ProposedChange, ...]) -> None:
        self.proposed_changes = {record.id: record for record in proposed_changes}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}
        self.sources: dict[str, Source] = {}
        self.documents: dict[str, Document] = {}
        self.actors: dict[str, Actor] = {}
        self.organizations: dict[str, Organization] = {}
        self.events: dict[str, Event] = {}
        self.entities: dict[str, Entity] = {}
        self.places: dict[str, Place] = {}
        self.evidence_targets: dict[str, EvidenceTarget] = {}
        self.evidence_validation_attempts: dict[str, EvidenceValidationAttempt] = {}
        self.document_representation_bundles: dict[str, DocumentRepresentationBundle] = {}
        self.assertion_evidence_links: dict[str, AssertionEvidenceLink] = {}
        self.assertions: dict[str, Assertion] = {}
        self.relationships: dict[str, Relationship] = {}
        self.outcomes: dict[str, Outcome] = {}
        self.argument_edges: dict[str, ArgumentEdge] = {}

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self.proposed_changes.get(record_id)

    def list_proposed_changes(self) -> tuple[ProposedChange, ...]:
        return tuple(self.proposed_changes.values())

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposed_changes[record.id] = record

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self.provenance_activities.get(record_id)

    def get_entity(self, record_id: str) -> Entity | None:
        return self.entities.get(record_id)

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

    def get_place(self, record_id: str) -> Place | None:
        return self.places.get(record_id)

    def get_source(self, record_id: str) -> Source | None:
        return self.sources.get(record_id)

    def get_document(self, record_id: str) -> Document | None:
        return self.documents.get(record_id)

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.document_representation_bundles.get(record_id)

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.evidence_targets.get(record_id)

    def save_evidence_target(self, record: EvidenceTarget) -> None:
        self.evidence_targets[record.id] = record

    def get_evidence_validation_attempt(self, record_id: str) -> EvidenceValidationAttempt | None:
        return self.evidence_validation_attempts.get(record_id)

    def save_evidence_validation_attempt(self, record: EvidenceValidationAttempt) -> None:
        self.evidence_validation_attempts[record.id] = record

    def get_assertion(self, record_id: str) -> Assertion | None:
        return self.assertions.get(record_id)

    def save_assertion(self, record: Assertion) -> None:
        self.assertions[record.id] = record

    def commit_accepted_assertion_with_evidence(
        self,
        *,
        assertion: Assertion,
        evidence_links: tuple[AssertionEvidenceLink, ...],
        provenance_activity: ProvenanceActivity,
        reviewed_change: ProposedChange,
    ) -> None:
        self.provenance_activities[provenance_activity.id] = provenance_activity
        self.assertions[assertion.id] = assertion
        self.assertion_evidence_links.update({link.id: link for link in evidence_links})
        self.proposed_changes[reviewed_change.id] = reviewed_change

    def get_relationship(self, record_id: str) -> Relationship | None:
        return self.relationships.get(record_id)

    def save_relationship(self, record: Relationship) -> None:
        self.relationships[record.id] = record

    def get_outcome(self, record_id: str) -> Outcome | None:
        return self.outcomes.get(record_id)

    def save_outcome(self, record: Outcome) -> None:
        self.outcomes[record.id] = record

    def get_argument_edge(self, record_id: str) -> ArgumentEdge | None:
        return self.argument_edges.get(record_id)

    def save_argument_edge(self, record: ArgumentEdge) -> None:
        self.argument_edges[record.id] = record


def seed_reference_records(ledger: FakeReviewLedger) -> None:
    ledger.sources["src_article_a"] = Source(
        id="src_article_a",
        source_type=SourceType.ARTICLE,
        identity_policy_id="fixture_v1",
        canonical_identity_key="article_a",
    )
    ledger.documents["doc_article_a"] = Document(
        id="doc_article_a",
        source_id="src_article_a",
        content_sha256="a" * 64,
    )
    ledger.organizations["org_anthropic"] = Organization(id="org_anthropic", name="Anthropic")
    ledger.organizations["org_commerce_department"] = Organization(
        id="org_commerce_department",
        name="Commerce Department",
    )
    ledger.actors["act_dario_amodei"] = Actor(
        id="act_dario_amodei",
        name="Dario Amodei",
        organization_ids=("org_anthropic",),
    )
    ledger.events["evt_release_review"] = Event(
        id="evt_release_review",
        name="Release review",
        participant_actor_ids=("act_dario_amodei",),
        participant_organization_ids=("org_anthropic",),
    )
    evidence_text = "Anthropic postponed the rollout."
    text_digest = hashlib.sha256(evidence_text.encode("utf-8")).hexdigest()
    text_view = TextView(
        id="tvw_article_a",
        representation_id="rep_article_a",
        kind=TextViewKind.LOGICAL,
        content_digest=text_digest,
        text=evidence_text,
        normalization_policy="utf8_identity_v1",
    )
    node = DocumentNode(
        id="nod_article_a_document",
        representation_id="rep_article_a",
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(evidence_text),
        text=evidence_text,
    )
    quality_report = ParseQualityReport(
        id="pqr_article_a",
        representation_id="rep_article_a",
        metric_values={"text_char_count": len(evidence_text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    representation_template = DocumentRepresentation(
        id="rep_article_a",
        document_id="doc_article_a",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="b" * 64,
        processing_task_fingerprint_id="ptf_fixture",
        input_blob_digest="a" * 64,
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = representation_template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                representation_template,
                text_views=(text_view,),
                nodes=(node,),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    ledger.document_representation_bundles[representation.id] = DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(node,),
        quality_report=quality_report,
    )
    evidence = EvidenceTarget(
        id="etg_delay",
        source_id="src_article_a",
        document_id="doc_article_a",
        exact_text=evidence_text,
        representation_id=representation.id,
        text_view_id=text_view.id,
        text_view_digest=text_digest,
        start_char=0,
        end_char=len(evidence_text),
        node_ids=(node.id,),
        normalization_policy="utf8_identity_v1",
    )
    ledger.evidence_targets[evidence.id] = evidence
    ledger.evidence_validation_attempts["eva_delay"] = EvidenceValidationAttempt(
        id="eva_delay",
        evidence_target_id=evidence.id,
        target_digest=canonical_evidence_target_digest(evidence),
        validator_version="fixture",
        status=EvidenceValidationAttemptStatus.SUCCEEDED,
        attempted_at=NOW,
    )
    ledger.assertions["ast_delay"] = Assertion(
        id="ast_delay",
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="postponed_rollout",
        object_value={"model": "Claude Fable 5"},
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=("src_article_a",),
        evidence_target_ids=("etg_delay",),
        provenance_activity_ids=("prv_model_run",),
    )
    ledger.assertions["ast_shared_outcome"] = Assertion(
        id="ast_shared_outcome",
        assertion_type=AssertionType.ANALYTIC_INFERENCE,
        epistemic_scope=EpistemicScope.ANALYTIC_INFERENCE,
        subject_entity_id="org_anthropic",
        predicate="shared_governance_outcome_with",
        object_entity_id="org_commerce_department",
        status=AssertionStatus.CORROBORATED,
        source_authority=SourceAuthority.NOT_APPLICABLE,
        attribution_basis=AttributionBasis.NOT_APPLICABLE,
        provenance_activity_ids=("prv_model_run",),
    )
    ledger.provenance_activities["prv_model_run"] = ProvenanceActivity(
        id="prv_model_run",
        activity_type="model_assertion_proposal",
        agent="fixture-extraction-runtime",
        occurred_at=NOW,
    )


def proposed_change(
    record_id: str,
    record_type: str,
    record: dict[str, JsonValue],
    review_status: ReviewStatus = ReviewStatus.PENDING,
) -> ProposedChange:
    proposed_json: dict[str, JsonValue] = {
        "record_type": record_type,
        "stable_label": record_id.removeprefix("pcg_"),
        "record": record,
        "evidence": {
            "selector_type": "exact_text",
            "exact_text": "evidence text",
            "source_id": "src_article_a",
            "document_id": "doc_article_a",
        },
    }
    if record_type == "Assertion":
        evidence_target_ids = record.get("evidence_target_ids")
        if evidence_target_ids is None:
            if record.get("source_ids"):
                raise ValueError(
                    "Source-backed Assertion test proposal requires evidence_target_ids."
                )
        else:
            if not isinstance(evidence_target_ids, list) or not all(
                isinstance(evidence_target_id, str) for evidence_target_id in evidence_target_ids
            ):
                raise ValueError("Assertion test proposal requires string evidence_target_ids.")
            target_ids = tuple(
                cast(str, evidence_target_id) for evidence_target_id in evidence_target_ids
            )
            proposed_json["evidence_links"] = [
                {
                    "evidence_target_id": evidence_target_id,
                    "validation_attempt_id": (f"eva_{evidence_target_id.removeprefix('etg_')}"),
                    "role": "direct_support",
                    "polarity": "supports",
                    "necessity": "required",
                }
                for evidence_target_id in target_ids
            ]
    return ProposedChange(
        id=record_id,
        review_status=review_status,
        proposed_json=proposed_json,
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


def test_review_next_decision_approves_first_pending_queue_item() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_next_decision(
        ReviewNextDecisionInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
        ),
        ledger,
    )

    assert result.has_next is True
    assert result.executed is True
    assert result.item is not None
    assert result.item.proposed_change_id == "pcg_organization"
    assert result.review_result is not None
    assert result.review_result.review_status is ReviewStatus.APPROVED
    assert ledger.proposed_changes["pcg_organization"].review_status is ReviewStatus.APPROVED
    assert result.review_result.provenance_activity_id in ledger.provenance_activities


def test_review_next_decision_rejects_first_pending_queue_item() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_next_decision(
        ReviewNextDecisionInput(
            decision=ReviewNextDecision.REJECT,
            reviewer="analyst",
            reviewed_at=NOW,
            reason="duplicate Organization",
        ),
        ledger,
    )

    assert result.executed is True
    assert result.review_result is not None
    assert result.review_result.review_status is ReviewStatus.REJECTED
    assert result.review_result.accepted_record_id is None
    assert ledger.proposed_changes["pcg_organization"].review_status is ReviewStatus.REJECTED


def test_review_next_decision_edits_first_pending_queue_item() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_next_decision(
        ReviewNextDecisionInput(
            decision=ReviewNextDecision.EDIT,
            reviewer="analyst",
            reviewed_at=NOW,
            accepted_record_json={
                "id": "act_lina_rahman",
                "name": "Lina Rahman",
                "role_names": ["deployment reviewer"],
                "organization_ids": ["org_anthropic"],
            },
        ),
        ledger,
    )

    assert result.executed is True
    assert result.review_result is not None
    assert result.review_result.review_status is ReviewStatus.EDITED
    assert ledger.actors["act_lina_rahman"].role_names == ("deployment reviewer",)
    assert ledger.proposed_changes["pcg_actor"].accepted_json is not None


def test_review_next_decision_filters_and_empty_queue() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    actor_result = run_review_next_decision(
        ReviewNextDecisionInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
            record_type="Actor",
        ),
        ledger,
    )
    empty_result = run_review_next_decision(
        ReviewNextDecisionInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
            record_type="Relationship",
        ),
        ledger,
    )

    assert actor_result.item is not None
    assert actor_result.item.proposed_change_id == "pcg_actor"
    assert empty_result.has_next is False
    assert empty_result.executed is False
    assert empty_result.review_result is None


def test_review_next_decision_dry_run_does_not_mutate() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_next_decision(
        ReviewNextDecisionInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
            dry_run=True,
        ),
        ledger,
    )

    assert result.has_next is True
    assert result.executed is False
    assert result.dry_run is True
    assert ledger.proposed_changes["pcg_organization"].review_status is ReviewStatus.PENDING
    assert set(ledger.provenance_activities) == {"prv_model_run"}


def test_review_next_decision_fails_fast_on_missing_decision_inputs() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    with pytest.raises(ValueError, match="requires reason"):
        run_review_next_decision(
            ReviewNextDecisionInput(
                decision=ReviewNextDecision.REJECT,
                reviewer="analyst",
                reviewed_at=NOW,
            ),
            ledger,
        )
    with pytest.raises(ValueError, match="requires accepted_record_json"):
        run_review_next_decision(
            ReviewNextDecisionInput(
                decision=ReviewNextDecision.EDIT,
                reviewer="analyst",
                reviewed_at=NOW,
            ),
            ledger,
        )
    assert ledger.proposed_changes["pcg_organization"].review_status is ReviewStatus.PENDING


def test_review_next_decision_fails_fast_on_malformed_selected_proposed_change() -> None:
    ledger = FakeReviewLedger(
        (
            ProposedChange(
                id="pcg_malformed",
                proposed_json={"record_type": "Organization", "stable_label": "malformed"},
                created_at=NOW,
                updated_at=NOW,
            ),
        )
    )

    with pytest.raises(ValueError, match="missing record object"):
        run_review_next_decision(
            ReviewNextDecisionInput(
                decision=ReviewNextDecision.APPROVE,
                reviewer="analyst",
                reviewed_at=NOW,
            ),
            ledger,
        )


def test_review_next_decision_json_is_agent_readable() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_next_decision(
        ReviewNextDecisionInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
        ),
        ledger,
    )
    payload = review_next_decision_result_to_json(result)

    assert payload["has_next"] is True
    assert payload["decision"] == "approve"
    assert payload["executed"] is True
    assert isinstance(payload["item"], dict)
    assert isinstance(payload["packet"], dict)
    review_result = cast(dict[str, JsonValue], payload["review_result"])
    assert review_result["review_status"] == "approved"


def test_review_drain_approves_all_matching_pending_changes() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
        ),
        ledger,
    )

    assert result.stopped_reason is ReviewDrainStoppedReason.QUEUE_EMPTY
    assert result.attempted_count == 2
    assert result.executed_count == 2
    assert [item.item.proposed_change_id for item in result.item_results if item.item] == [
        "pcg_organization",
        "pcg_actor",
    ]
    assert ledger.proposed_changes["pcg_organization"].review_status is ReviewStatus.APPROVED
    assert ledger.proposed_changes["pcg_actor"].review_status is ReviewStatus.APPROVED


def test_review_drain_limit_executes_bounded_count() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
            limit=1,
        ),
        ledger,
    )

    assert result.stopped_reason is ReviewDrainStoppedReason.LIMIT_REACHED
    assert result.attempted_count == 1
    assert result.executed_count == 1
    assert ledger.proposed_changes["pcg_organization"].review_status is ReviewStatus.APPROVED
    assert ledger.proposed_changes["pcg_actor"].review_status is ReviewStatus.PENDING


def test_review_drain_rejects_matching_pending_changes() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.REJECT,
            reviewer="analyst",
            reviewed_at=NOW,
            reason="duplicate records",
        ),
        ledger,
    )

    assert result.stopped_reason is ReviewDrainStoppedReason.QUEUE_EMPTY
    assert result.executed_count == 2
    assert all(
        change.review_status is ReviewStatus.REJECTED for change in ledger.proposed_changes.values()
    )


def test_review_drain_edits_matching_pending_change() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.EDIT,
            reviewer="analyst",
            reviewed_at=NOW,
            accepted_record_json={
                "id": "org_anthropic",
                "name": "Anthropic",
                "organization_type": "ai_lab",
            },
        ),
        ledger,
    )

    assert result.executed_count == 1
    assert result.item_results[0].review_result is not None
    assert result.item_results[0].review_result.review_status is ReviewStatus.EDITED
    assert ledger.proposed_changes["pcg_organization"].accepted_json is not None


def test_review_drain_filters_and_empty_queue() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    actor_result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
            record_type="Actor",
        ),
        ledger,
    )
    empty_result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
            record_type="Relationship",
        ),
        ledger,
    )

    assert actor_result.executed_count == 1
    assert actor_result.item_results[0].item is not None
    assert actor_result.item_results[0].item.proposed_change_id == "pcg_actor"
    assert empty_result.stopped_reason is ReviewDrainStoppedReason.QUEUE_EMPTY
    assert empty_result.attempted_count == 0
    assert empty_result.executed_count == 0


def test_review_drain_dry_run_reports_sequence_without_mutation() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_actor",
                "Actor",
                {
                    "id": "act_lina_rahman",
                    "name": "Lina Rahman",
                    "organization_ids": ["org_anthropic"],
                },
            ),
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
            dry_run=True,
        ),
        ledger,
    )

    assert result.stopped_reason is ReviewDrainStoppedReason.DRY_RUN_COMPLETE
    assert result.attempted_count == 2
    assert result.executed_count == 0
    assert all(not item.executed for item in result.item_results)
    assert all(
        change.review_status is ReviewStatus.PENDING for change in ledger.proposed_changes.values()
    )


def test_review_drain_stops_on_validation_failure_preserving_prior_success() -> None:
    invalid_assertion: dict[str, JsonValue] = {
        "id": "ast_missing_evidence",
        "assertion_type": "source_claim",
        "epistemic_scope": "source_report",
        "subject_entity_id": "org_anthropic",
        "predicate": "postponed_rollout",
        "object_value": {"model": "Claude Fable 5"},
        "status": "proposed",
        "source_authority": "secondary",
        "attribution_basis": "reported_by_source",
        "source_ids": ["src_article_a"],
        "evidence_target_ids": ["etg_missing"],
        "provenance_activity_ids": [],
    }
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
            proposed_change("pcg_invalid_assertion", "Assertion", invalid_assertion),
        )
    )
    seed_reference_records(ledger)

    result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
        ),
        ledger,
    )

    assert result.stopped_reason is ReviewDrainStoppedReason.VALIDATION_FAILED
    assert result.attempted_count == 2
    assert result.executed_count == 1
    assert result.error_message is not None
    assert "references missing EvidenceTarget" in result.error_message
    assert ledger.proposed_changes["pcg_organization"].review_status is ReviewStatus.APPROVED
    assert ledger.proposed_changes["pcg_invalid_assertion"].review_status is ReviewStatus.PENDING


def test_review_drain_json_is_agent_readable() -> None:
    ledger = FakeReviewLedger(
        (
            proposed_change(
                "pcg_organization",
                "Organization",
                {
                    "id": "org_anthropic",
                    "name": "Anthropic",
                    "organization_type": "ai_lab",
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = run_review_drain(
        ReviewDrainInput(
            decision=ReviewNextDecision.APPROVE,
            reviewer="analyst",
            reviewed_at=NOW,
        ),
        ledger,
    )
    payload = review_drain_result_to_json(result)

    assert payload["decision"] == "approve"
    assert payload["executed_count"] == 1
    assert payload["stopped_reason"] == "queue_empty"
    item_results = cast(list[dict[str, JsonValue]], payload["item_results"])
    assert item_results[0]["executed"] is True


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
            "EvidenceTarget",
            {
                "id": "etg_delay",
                "source_id": "src_article_a",
                "document_id": "doc_article_a",
                "representation_id": "rep_delay",
                "text_view_id": "tvw_delay",
                "text_view_digest": "0" * 64,
                "start_char": 0,
                "end_char": 32,
                "exact_text": "Anthropic postponed the rollout.",
                "normalization_policy": "fixture_v1",
                "node_ids": ["nod_delay"],
            },
            "evidence_targets",
            "etg_delay",
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
        (
            "pcg_argument_edge",
            "ArgumentEdge",
            {
                "id": "arg_delay_infers_shared_outcome",
                "from_assertion_id": "ast_delay",
                "to_assertion_id": "ast_shared_outcome",
                "relation": "infers",
                "rationale": "The accepted Assertion supports the analytic inference.",
                "evidence_target_ids": ["etg_delay"],
                "confidence": 0.7,
            },
            "argument_edges",
            "arg_delay_infers_shared_outcome",
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
    seed_reference_records(ledger)

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
                    "epistemic_scope": "source_report",
                    "subject_entity_id": "org_anthropic",
                    "predicate": "postponed_rollout",
                    "object_value": {"model": "Claude Fable 5"},
                    "status": "proposed",
                    "source_authority": "secondary",
                    "attribution_basis": "reported_by_source",
                    "source_ids": ["src_article_a"],
                    "evidence_target_ids": ["etg_delay"],
                    "provenance_activity_ids": [],
                },
            ),
        )
    )
    seed_reference_records(ledger)

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
    seed_reference_records(ledger)

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
        "epistemic_scope": "source_report",
        "subject_entity_id": "org_anthropic",
        "predicate": "postponed_rollout",
        "object_value": {"model": "Claude Fable 5", "timing": "late June"},
        "status": "proposed",
        "source_authority": "secondary",
        "attribution_basis": "reported_by_source",
        "source_report_confidence": 0.91,
        "extraction_confidence": 0.84,
        "world_truth_confidence": 0.62,
        "current_assessment": "The Source reports a delayed rollout after review.",
        "source_ids": ["src_article_a"],
        "evidence_target_ids": ["etg_delay"],
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
                    "epistemic_scope": "source_report",
                    "subject_entity_id": "org_anthropic",
                    "predicate": "postponed_rollout",
                    "object_value": {"model": "Claude Fable 5"},
                    "status": "proposed",
                    "source_authority": "secondary",
                    "attribution_basis": "reported_by_source",
                    "source_ids": ["src_article_a"],
                    "evidence_target_ids": ["etg_delay"],
                    "provenance_activity_ids": [],
                },
            ),
        )
    )
    seed_reference_records(ledger)

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


def test_approve_rejects_assertion_with_missing_evidence_target_reference() -> None:
    record_id = "pcg_assertion"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Assertion",
                {
                    "id": "ast_missing_evidence",
                    "assertion_type": "source_claim",
                    "epistemic_scope": "source_report",
                    "subject_entity_id": "org_anthropic",
                    "predicate": "postponed_rollout",
                    "object_value": {"model": "Claude Fable 5"},
                    "status": "proposed",
                    "source_authority": "secondary",
                    "attribution_basis": "reported_by_source",
                    "source_ids": ["src_article_a"],
                    "evidence_target_ids": ["etg_missing"],
                    "provenance_activity_ids": [],
                },
            ),
        )
    )
    seed_reference_records(ledger)

    with pytest.raises(ValueError, match="references missing EvidenceTarget: etg_missing"):
        approve_proposed_change(review_input(record_id), ledger)

    assert "ast_missing_evidence" not in ledger.assertions
    assert ledger.provenance_activities.keys() == {"prv_model_run"}


def test_approve_rejects_relationship_with_missing_assertion_reference() -> None:
    record_id = "pcg_relationship"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Relationship",
                {
                    "id": "rel_missing_assertion",
                    "subject_id": "org_commerce_department",
                    "predicate": "influenced_release_timing_for",
                    "object_id": "org_anthropic",
                    "assertion_ids": ["ast_missing"],
                },
            ),
        )
    )
    seed_reference_records(ledger)

    with pytest.raises(ValueError, match="references missing Assertion: ast_missing"):
        approve_proposed_change(review_input(record_id), ledger)

    assert "rel_missing_assertion" not in ledger.relationships


def test_approve_rejects_argument_edge_with_missing_reference() -> None:
    record_id = "pcg_argument_edge"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "ArgumentEdge",
                {
                    "id": "arg_missing_to_assertion",
                    "from_assertion_id": "ast_delay",
                    "to_assertion_id": "ast_missing",
                    "relation": "infers",
                    "rationale": "The accepted Assertion supports the analytic inference.",
                    "evidence_target_ids": ["etg_delay"],
                    "confidence": 0.7,
                },
            ),
        )
    )
    seed_reference_records(ledger)

    with pytest.raises(ValueError, match="references missing Assertion: ast_missing"):
        approve_proposed_change(review_input(record_id), ledger)

    assert "arg_missing_to_assertion" not in ledger.argument_edges


def test_approve_proposed_analytic_assertion_marks_it_corroborated() -> None:
    record_id = "pcg_analytic_assertion"
    ledger = FakeReviewLedger(
        (
            proposed_change(
                record_id,
                "Assertion",
                {
                    "id": "ast_mined_shared_outcome",
                    "assertion_type": "analytic_inference",
                    "epistemic_scope": "analytic_inference",
                    "subject_entity_id": "org_anthropic",
                    "predicate": "shared_governance_outcome_with",
                    "object_entity_id": "org_commerce_department",
                    "status": "proposed",
                    "source_authority": "not_applicable",
                    "attribution_basis": "not_applicable",
                    "world_truth_confidence": 0.5,
                    "provenance_activity_ids": [],
                },
            ),
        )
    )
    seed_reference_records(ledger)

    result = approve_proposed_change(review_input(record_id), ledger)

    assertion = ledger.assertions["ast_mined_shared_outcome"]
    assert assertion.status is AssertionStatus.CORROBORATED
    assert assertion.provenance_activity_ids == (result.provenance_activity_id,)


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
