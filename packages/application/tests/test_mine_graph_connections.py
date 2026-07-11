import json
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    GRAPH_CONNECTION_MINING_ACTIVITY,
    GRAPH_CONNECTION_PREDICATE,
    GraphAnalyzer,
    GraphConnectionCandidate,
    GraphConnectionMiningInput,
    GraphEdge,
    GraphNode,
    GraphProjection,
    deterministic_mined_assertion_id,
    deterministic_mined_relationship_id,
    mine_graph_connections,
)
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Document,
    EpistemicScope,
    Event,
    EvidenceTarget,
    Organization,
    Outcome,
    Place,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    ReviewStatus,
    Source,
    SourceAuthority,
)

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


class FakeMiningLedger:
    def __init__(
        self,
        *,
        relationships: tuple[Relationship, ...] = (),
        proposed_changes: tuple[ProposedChange, ...] = (),
    ) -> None:
        self.organizations = (
            Organization(id="org_anthropic", name="Anthropic"),
            Organization(id="org_commerce_department", name="Commerce Department"),
        )
        self.assertions = (
            Assertion(
                id="ast_delay",
                assertion_type=AssertionType.SOURCE_CLAIM,
                epistemic_scope=EpistemicScope.WORLD_STATE,
                subject_entity_id="org_anthropic",
                predicate="postponed_rollout",
                object_value={"model": "Claude Fable 5"},
                status=AssertionStatus.REPORTED,
                source_authority=SourceAuthority.NOT_APPLICABLE,
                attribution_basis=AttributionBasis.NOT_APPLICABLE,
                provenance_activity_ids=("prv_review_delay",),
            ),
            Assertion(
                id="ast_suspension",
                assertion_type=AssertionType.SOURCE_CLAIM,
                epistemic_scope=EpistemicScope.WORLD_STATE,
                subject_entity_id="org_anthropic",
                predicate="suspended_enterprise_access",
                object_value={"date": "2026-06-23"},
                status=AssertionStatus.REPORTED,
                source_authority=SourceAuthority.NOT_APPLICABLE,
                attribution_basis=AttributionBasis.NOT_APPLICABLE,
                provenance_activity_ids=("prv_review_suspension",),
            ),
        )
        self.outcomes = (
            Outcome(
                id="out_monitoring_update",
                description="Anthropic resumed access with additional notice commitments.",
                organization_ids=("org_anthropic", "org_commerce_department"),
                assertion_ids=("ast_delay", "ast_suspension"),
            ),
        )
        self.relationships = relationships
        self.proposed_changes = {record.id: record for record in proposed_changes}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}

    def list_actors(self) -> tuple[Actor, ...]:
        return ()

    def list_organizations(self) -> tuple[Organization, ...]:
        return self.organizations

    def list_places(self) -> tuple[Place, ...]:
        return ()

    def list_events(self) -> tuple[Event, ...]:
        return ()

    def list_sources(self) -> tuple[Source, ...]:
        return ()

    def list_documents(self) -> tuple[Document, ...]:
        return ()

    def list_evidence_targets(self) -> tuple[EvidenceTarget, ...]:
        return ()

    def list_assertions(self) -> tuple[Assertion, ...]:
        return self.assertions

    def list_relationships(self) -> tuple[Relationship, ...]:
        return self.relationships

    def list_outcomes(self) -> tuple[Outcome, ...]:
        return self.outcomes

    def list_argument_edges(self) -> tuple[ArgumentEdge, ...]:
        return ()

    def list_proposed_changes(self) -> tuple[ProposedChange, ...]:
        return tuple(self.proposed_changes.values())

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record

    def save_proposed_change(self, record: ProposedChange) -> None:
        self.proposed_changes[record.id] = record


class FakeGraphAnalyzer(GraphAnalyzer):
    def project(
        self,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> GraphProjection:
        return GraphProjection(nodes=nodes, edges=edges)


def test_mine_graph_connections_creates_pending_proposal_bundle() -> None:
    candidate = graph_candidate()
    ledger = FakeMiningLedger()

    result = mine_graph_connections(
        GraphConnectionMiningInput(mined_at=NOW),
        ledger,
        FakeGraphAnalyzer(),
    )

    assert result.candidate_count == 1
    assert len(result.proposed_change_ids) == 4
    assert result.provenance_activity_id is not None
    activity = ledger.provenance_activities[result.provenance_activity_id]
    proposed_changes = tuple(
        ledger.proposed_changes[record_id] for record_id in result.proposed_change_ids
    )
    assert activity.activity_type == GRAPH_CONNECTION_MINING_ACTIVITY
    assert activity.input_ids == ("out_monitoring_update",)
    assert activity.output_ids == result.proposed_change_ids
    assert {change.review_status for change in proposed_changes} == {ReviewStatus.PENDING}
    assert {change.provenance_activity_id for change in proposed_changes} == {
        result.provenance_activity_id
    }
    record_types = [change.proposed_json["record_type"] for change in proposed_changes]
    assert record_types == ["Assertion", "Relationship", "ArgumentEdge", "ArgumentEdge"]

    assertion_record = proposed_changes[0].proposed_json["record"]
    relationship_record = proposed_changes[1].proposed_json["record"]
    mining_context = proposed_changes[0].proposed_json["mining_context"]
    assert isinstance(assertion_record, dict)
    assert isinstance(relationship_record, dict)
    assert isinstance(mining_context, dict)
    assert proposed_changes[0].proposed_json.get("evidence") is None
    assert mining_context["mining_rule"] == "outcome_organization_assertion_cooccurrence"
    assert mining_context["outcome_id"] == "out_monitoring_update"
    assert mining_context["supporting_assertion_ids"] == ["ast_delay", "ast_suspension"]
    assert assertion_record["id"] == deterministic_mined_assertion_id(candidate)
    assert assertion_record["assertion_type"] == "analytic_inference"
    assert assertion_record["epistemic_scope"] == "analytic_inference"
    assert assertion_record["source_authority"] == "not_applicable"
    assert assertion_record["attribution_basis"] == "not_applicable"
    assert assertion_record["status"] == "proposed"
    assert assertion_record["predicate"] == GRAPH_CONNECTION_PREDICATE
    assert assertion_record["current_assessment"] == ""
    Assertion.model_validate_json(json.dumps(assertion_record))
    assert relationship_record["id"] == deterministic_mined_relationship_id(candidate)
    assert relationship_record["assertion_ids"] == [assertion_record["id"]]


def test_mine_graph_connections_skips_existing_accepted_relationship() -> None:
    ledger = FakeMiningLedger(
        relationships=(
            Relationship(
                id="rel_existing",
                subject_id="org_anthropic",
                predicate=GRAPH_CONNECTION_PREDICATE,
                object_id="org_commerce_department",
                assertion_ids=("ast_delay",),
            ),
        )
    )

    result = mine_graph_connections(
        GraphConnectionMiningInput(mined_at=NOW),
        ledger,
        FakeGraphAnalyzer(),
    )

    assert result.candidate_count == 0
    assert result.provenance_activity_id is None
    assert result.proposed_change_ids == ()
    assert ledger.provenance_activities == {}
    assert ledger.proposed_changes == {}


def test_mine_graph_connections_rerun_does_not_overwrite_existing_proposed_changes() -> None:
    ledger = FakeMiningLedger()
    first_result = mine_graph_connections(
        GraphConnectionMiningInput(mined_at=NOW),
        ledger,
        FakeGraphAnalyzer(),
    )
    reviewed_record_id = first_result.proposed_change_ids[0]
    existing_change = ledger.proposed_changes[reviewed_record_id]
    ledger.proposed_changes[reviewed_record_id] = ProposedChange(
        id=existing_change.id,
        review_status=ReviewStatus.REJECTED,
        proposed_json=existing_change.proposed_json,
        provenance_activity_id=existing_change.provenance_activity_id,
        created_at=existing_change.created_at,
        updated_at=NOW,
    )

    second_result = mine_graph_connections(
        GraphConnectionMiningInput(mined_at=NOW),
        ledger,
        FakeGraphAnalyzer(),
    )

    assert second_result.candidate_count == 1
    assert second_result.provenance_activity_id is None
    assert second_result.proposed_change_ids == ()
    assert ledger.proposed_changes[reviewed_record_id].review_status is ReviewStatus.REJECTED


def test_mine_graph_connections_rejects_missing_supporting_assertion() -> None:
    ledger = FakeMiningLedger()
    ledger.outcomes = (
        Outcome(
            id="out_monitoring_update",
            description="Anthropic resumed access with additional notice commitments.",
            organization_ids=("org_anthropic", "org_commerce_department"),
            assertion_ids=("ast_delay", "ast_missing"),
        ),
    )

    with pytest.raises(ValueError, match="target_id=ast_missing"):
        mine_graph_connections(
            GraphConnectionMiningInput(mined_at=NOW),
            ledger,
            FakeGraphAnalyzer(),
        )

    assert ledger.provenance_activities == {}


def graph_candidate() -> GraphConnectionCandidate:
    return GraphConnectionCandidate(
        subject_organization_id="org_anthropic",
        object_organization_id="org_commerce_department",
        outcome_id="out_monitoring_update",
        supporting_assertion_ids=("ast_delay", "ast_suspension"),
    )
