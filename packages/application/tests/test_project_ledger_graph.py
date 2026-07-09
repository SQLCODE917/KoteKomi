from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    GraphAnalyzer,
    GraphEdge,
    GraphNode,
    GraphProjection,
    deterministic_graph_edge_id,
    project_ledger_graph,
)
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Document,
    EpistemicScope,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    SelectorType,
    Source,
    SourceAuthority,
    SourceType,
)

NOW = datetime(2026, 7, 8, tzinfo=UTC)
HASH = "a" * 64


class FakeGraphLedger:
    def __init__(self) -> None:
        self.actors = (
            Actor(
                id="act_person_a",
                name="Person A",
                role_names=("advisor",),
                organization_ids=("org_lab_a",),
            ),
        )
        self.organizations = (Organization(id="org_lab_a", name="Lab A"),)
        self.places = (Place(id="plc_event_hall", name="Event Hall"),)
        self.events = (
            Event(
                id="evt_model_forum",
                name="Model Forum",
                start_at=NOW,
                place_id="plc_event_hall",
                participant_actor_ids=("act_person_a",),
                participant_organization_ids=("org_lab_a",),
            ),
        )
        self.sources = (
            Source(
                id="src_article_a",
                source_type=SourceType.ARTICLE,
                title="Release review article",
            ),
        )
        self.documents = (
            Document(
                id="doc_article_a",
                source_id="src_article_a",
                raw_path="sources/raw/src_article_a.bin",
                extracted_text_path="documents/extracted/doc_article_a.txt",
                content_sha256=HASH,
            ),
        )
        self.evidence_spans = (
            EvidenceSpan(
                id="evs_article_a_release",
                source_id="src_article_a",
                document_id="doc_article_a",
                assertion_id="ast_release_review",
                selector_type=SelectorType.EXACT_TEXT,
                exact_text="Person A negotiated the release.",
            ),
        )
        self.assertions = (
            Assertion(
                id="ast_release_review",
                assertion_type=AssertionType.SOURCE_CLAIM,
                epistemic_scope=EpistemicScope.SOURCE_REPORT,
                subject_entity_id="act_person_a",
                predicate="negotiated_release",
                object_entity_id="org_lab_a",
                status=AssertionStatus.REPORTED,
                source_authority=SourceAuthority.SECONDARY,
                attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
                source_ids=("src_article_a",),
                evidence_span_ids=("evs_article_a_release",),
                provenance_activity_ids=("prv_human_review",),
            ),
        )
        self.relationships = (
            Relationship(
                id="rel_person_a_lab_a",
                subject_id="act_person_a",
                predicate="negotiated_release",
                object_id="org_lab_a",
                assertion_ids=("ast_release_review",),
            ),
        )
        self.outcomes = (
            Outcome(
                id="out_release_review",
                description="The release review became public.",
                actor_ids=("act_person_a",),
                organization_ids=("org_lab_a",),
                event_ids=("evt_model_forum",),
                assertion_ids=("ast_release_review",),
            ),
        )
        self.argument_edges = (
            ArgumentEdge(
                id="arg_release_support",
                from_assertion_id="ast_release_review",
                to_assertion_id="ast_release_review",
                relation=ArgumentEdgeRelation.SUPPORTS,
                rationale="The source claim supports itself as reported evidence.",
                evidence_span_ids=("evs_article_a_release",),
                confidence=0.8,
            ),
        )
        self.proposed_changes = (
            ProposedChange(
                id="pcg_ignore_me",
                proposed_json={"record_type": "Actor", "record": {"id": "act_ignored"}},
            ),
        )
        self.provenance_activities = (
            ProvenanceActivity(
                id="prv_human_review",
                activity_type="human_review",
                agent="analyst",
                input_ids=("pcg_release_review",),
                output_ids=("ast_release_review",),
                occurred_at=NOW,
            ),
        )

    def list_actors(self) -> tuple[Actor, ...]:
        return self.actors

    def list_organizations(self) -> tuple[Organization, ...]:
        return self.organizations

    def list_places(self) -> tuple[Place, ...]:
        return self.places

    def list_events(self) -> tuple[Event, ...]:
        return self.events

    def list_sources(self) -> tuple[Source, ...]:
        return self.sources

    def list_documents(self) -> tuple[Document, ...]:
        return self.documents

    def list_evidence_spans(self) -> tuple[EvidenceSpan, ...]:
        return self.evidence_spans

    def list_assertions(self) -> tuple[Assertion, ...]:
        return self.assertions

    def list_relationships(self) -> tuple[Relationship, ...]:
        return self.relationships

    def list_outcomes(self) -> tuple[Outcome, ...]:
        return self.outcomes

    def list_argument_edges(self) -> tuple[ArgumentEdge, ...]:
        return self.argument_edges


class FakeGraphAnalyzer(GraphAnalyzer):
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]] = []

    def project(
        self,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> GraphProjection:
        self.calls.append((nodes, edges))
        return GraphProjection(nodes=nodes, edges=edges)


def test_project_ledger_graph_builds_nodes_and_edges_from_accepted_records() -> None:
    analyzer = FakeGraphAnalyzer()

    projection = project_ledger_graph(FakeGraphLedger(), analyzer)

    assert analyzer.calls == [(projection.nodes, projection.edges)]
    assert {node.id for node in projection.nodes} == {
        "act_person_a",
        "arg_release_support",
        "ast_release_review",
        "doc_article_a",
        "evs_article_a_release",
        "evt_model_forum",
        "org_lab_a",
        "out_release_review",
        "plc_event_hall",
        "rel_person_a_lab_a",
        "src_article_a",
    }
    assert "pcg_ignore_me" not in {node.id for node in projection.nodes}
    edge_keys = {(edge.source_id, edge.target_id, edge.edge_type) for edge in projection.edges}
    assert ("act_person_a", "org_lab_a", "actor_organization") in edge_keys
    assert ("evt_model_forum", "act_person_a", "event_actor") in edge_keys
    assert ("evt_model_forum", "org_lab_a", "event_organization") in edge_keys
    assert ("evt_model_forum", "plc_event_hall", "event_place") in edge_keys
    assert ("doc_article_a", "src_article_a", "document_source") in edge_keys
    assert ("evs_article_a_release", "ast_release_review", "evidence_assertion") in edge_keys
    assert ("ast_release_review", "act_person_a", "assertion_subject") in edge_keys
    assert ("ast_release_review", "org_lab_a", "assertion_object") in edge_keys
    assert ("rel_person_a_lab_a", "ast_release_review", "relationship_assertion") in edge_keys
    assert ("out_release_review", "evt_model_forum", "outcome_event") in edge_keys
    assert ("arg_release_support", "evs_article_a_release", "argument_evidence") in edge_keys


def test_project_ledger_graph_uses_deterministic_edge_ids() -> None:
    projection = project_ledger_graph(FakeGraphLedger(), FakeGraphAnalyzer())

    document_source_edge = next(
        edge for edge in projection.edges if edge.edge_type == "document_source"
    )

    assert document_source_edge.id == deterministic_graph_edge_id(
        edge_type="document_source",
        source_id="doc_article_a",
        target_id="src_article_a",
        source_record_id="doc_article_a",
    )
    assert projection.edges == tuple(sorted(projection.edges, key=lambda edge: edge.id))


def test_project_ledger_graph_rejects_dangling_references() -> None:
    ledger = FakeGraphLedger()
    ledger.assertions = (
        Assertion(
            id="ast_dangling_evidence",
            assertion_type=AssertionType.SOURCE_CLAIM,
            epistemic_scope=EpistemicScope.SOURCE_REPORT,
            subject_entity_id="act_person_a",
            predicate="negotiated_release",
            object_entity_id="org_lab_a",
            status=AssertionStatus.REPORTED,
            source_authority=SourceAuthority.SECONDARY,
            attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
            source_ids=("src_article_a",),
            evidence_span_ids=("evs_missing",),
            provenance_activity_ids=("prv_human_review",),
        ),
    )

    with pytest.raises(ValueError, match="references missing node"):
        project_ledger_graph(ledger, FakeGraphAnalyzer())
