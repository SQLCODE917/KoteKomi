from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_application import (
    ArchiveObject,
    BriefingGenerationInput,
    BriefingMarkdown,
    BriefingRenderInput,
    StagedArchiveObject,
    generate_briefing,
)
from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    Briefing,
    EvidenceSpan,
    ProvenanceActivity,
    Relationship,
    SelectorType,
    Source,
    SourceType,
)

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
BEFORE = NOW - timedelta(days=1)
AFTER = NOW + timedelta(minutes=1)


class FakeArchiveStore:
    def __init__(self) -> None:
        self.staged: dict[str, bytes] = {}
        self.markdown: dict[str, str] = {}
        self.deleted_paths: list[str] = []

    def initialize(self) -> None:
        return None

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        raise NotImplementedError

    def read_raw_source(self, source_id: str) -> bytes:
        raise NotImplementedError

    def write_document_text(self, document_id: str, text: str) -> ArchiveObject:
        raise NotImplementedError

    def read_document_text(self, document_id: str) -> str:
        raise NotImplementedError

    def read_briefing_markdown(self, briefing_id: str) -> str:
        return self.markdown[briefing_id]

    def stage_raw_source(self, source_id: str, content: bytes) -> StagedArchiveObject:
        raise NotImplementedError

    def stage_document_text(self, document_id: str, text: str) -> StagedArchiveObject:
        raise NotImplementedError

    def stage_briefing_markdown(
        self,
        briefing_id: str,
        markdown: str,
    ) -> StagedArchiveObject:
        staged_path = f".staging/briefings/daily/{briefing_id}.md.tmp"
        self.staged[staged_path] = markdown.encode("utf-8")
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(
                relative_path=f"briefings/daily/{briefing_id}.md",
                size_bytes=len(markdown.encode("utf-8")),
            ),
        )

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        content = self.staged.pop(staged_object.staged_relative_path)
        briefing_id = staged_object.final_object.relative_path.removeprefix(
            "briefings/daily/"
        ).removesuffix(".md")
        self.markdown[briefing_id] = content.decode("utf-8")
        return staged_object.final_object

    def delete_object(self, relative_path: str) -> None:
        self.deleted_paths.append(relative_path)
        self.staged.pop(relative_path, None)
        if relative_path.startswith("briefings/daily/"):
            briefing_id = relative_path.removeprefix("briefings/daily/").removesuffix(".md")
            self.markdown.pop(briefing_id, None)


class FakeBriefingRenderer:
    def __init__(self) -> None:
        self.calls: list[BriefingRenderInput] = []

    def render(self, render_input: BriefingRenderInput) -> BriefingMarkdown:
        self.calls.append(render_input)
        return BriefingMarkdown(markdown=f"# {render_input.title}\n")


class FakeBriefingLedger:
    def __init__(
        self,
        *,
        sources: tuple[Source, ...] = (),
        assertions: tuple[Assertion, ...] = (),
        relationships: tuple[Relationship, ...] = (),
        argument_edges: tuple[ArgumentEdge, ...] = (),
        evidence_spans: tuple[EvidenceSpan, ...] = (),
        briefings: tuple[Briefing, ...] = (),
    ) -> None:
        self.sources = sources
        self.assertions = assertions
        self.relationships = relationships
        self.argument_edges = argument_edges
        self.evidence_spans = evidence_spans
        self.briefings = {record.id: record for record in briefings}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}

    def list_sources(self) -> tuple[Source, ...]:
        return self.sources

    def list_assertions(self) -> tuple[Assertion, ...]:
        return self.assertions

    def list_relationships(self) -> tuple[Relationship, ...]:
        return self.relationships

    def list_argument_edges(self) -> tuple[ArgumentEdge, ...]:
        return self.argument_edges

    def list_evidence_spans(self) -> tuple[EvidenceSpan, ...]:
        return self.evidence_spans

    def list_briefings(self) -> tuple[Briefing, ...]:
        return tuple(self.briefings.values())

    def get_briefing(self, record_id: str) -> Briefing | None:
        return self.briefings.get(record_id)

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities[record.id] = record

    def save_briefing(self, record: Briefing) -> None:
        self.briefings[record.id] = record


def test_generate_briefing_creates_markdown_briefing_and_provenance() -> None:
    source = source_fixture(updated_at=BEFORE)
    evidence_span = evidence_span_fixture(created_at=BEFORE)
    assertion = source_assertion_fixture(updated_at=BEFORE)
    analytic_assertion = analytic_assertion_fixture(updated_at=BEFORE)
    relationship = relationship_fixture(updated_at=BEFORE)
    argument_edge = argument_edge_fixture(created_at=BEFORE)
    ledger = FakeBriefingLedger(
        sources=(source,),
        assertions=(analytic_assertion, assertion),
        relationships=(relationship,),
        argument_edges=(argument_edge,),
        evidence_spans=(evidence_span,),
    )
    archive = FakeArchiveStore()
    renderer = FakeBriefingRenderer()

    result = generate_briefing(
        BriefingGenerationInput(title="Daily Briefing", generated_at=NOW),
        ledger,
        archive,
        renderer,
    )

    briefing = ledger.briefings[result.briefing_id]
    assert result.markdown_path == f"briefings/daily/{result.briefing_id}.md"
    assert result.source_count == 1
    assert result.assertion_count == 2
    assert result.relationship_count == 1
    assert result.argument_edge_count == 1
    assert result.evidence_span_count == 1
    assert result.analytic_inference_count == 1
    assert briefing.source_ids == (source.id,)
    assert briefing.assertion_ids == (assertion.id, analytic_assertion.id)
    assert briefing.relationship_ids == (relationship.id,)
    assert briefing.argument_edge_ids == (argument_edge.id,)
    assert briefing.evidence_span_ids == (evidence_span.id,)
    assert briefing.analytic_inference_assertion_ids == (analytic_assertion.id,)
    assert briefing.provenance_activity_id == result.provenance_activity_id
    assert archive.markdown[result.briefing_id] == "# Daily Briefing\n"
    assert archive.staged == {}
    assert renderer.calls[0].previous_briefing_id is None
    assert renderer.calls[0].analytic_inference_assertion_ids == (analytic_assertion.id,)
    activity = ledger.provenance_activities[result.provenance_activity_id]
    assert activity.activity_type == "briefing_generation"
    assert activity.output_ids == (result.briefing_id,)


def test_generate_briefing_uses_latest_previous_briefing_as_change_boundary() -> None:
    previous = Briefing(
        id="brf_previous",
        title="Previous Briefing",
        provenance_activity_id="prv_previous",
        generated_at=NOW,
    )
    older_source = source_fixture(updated_at=BEFORE)
    newer_source = Source(
        id="src_newer",
        source_type=SourceType.ARTICLE,
        title="Newer Source",
        created_at=AFTER,
        updated_at=AFTER,
    )
    newer_assertion = source_assertion_fixture(updated_at=AFTER)
    newer_evidence_span = evidence_span_fixture(created_at=AFTER)
    ledger = FakeBriefingLedger(
        sources=(older_source, newer_source),
        assertions=(newer_assertion,),
        evidence_spans=(newer_evidence_span,),
        briefings=(previous,),
    )

    result = generate_briefing(
        BriefingGenerationInput(title="Daily Briefing", generated_at=AFTER),
        ledger,
        FakeArchiveStore(),
        FakeBriefingRenderer(),
    )

    briefing = ledger.briefings[result.briefing_id]
    assert briefing.previous_briefing_id == previous.id
    assert briefing.source_ids == (source_fixture().id, newer_source.id)
    assert briefing.assertion_ids == (newer_assertion.id,)
    assert briefing.evidence_span_ids == (newer_evidence_span.id,)


def test_generate_briefing_rejects_source_backed_assertion_missing_evidence_span() -> None:
    ledger = FakeBriefingLedger(
        sources=(source_fixture(),),
        assertions=(source_assertion_fixture(),),
        evidence_spans=(),
    )
    archive = FakeArchiveStore()

    with pytest.raises(ValueError, match="references missing EvidenceSpan"):
        generate_briefing(
            BriefingGenerationInput(title="Daily Briefing", generated_at=NOW),
            ledger,
            archive,
            FakeBriefingRenderer(),
        )

    assert archive.staged == {}
    assert archive.markdown == {}
    assert ledger.provenance_activities == {}


def source_fixture(updated_at: datetime = BEFORE) -> Source:
    return Source(
        id="src_article_a",
        source_type=SourceType.ARTICLE,
        title="Article A",
        created_at=updated_at,
        updated_at=updated_at,
    )


def evidence_span_fixture(created_at: datetime = BEFORE) -> EvidenceSpan:
    return EvidenceSpan(
        id="evs_article_a_claim",
        source_id="src_article_a",
        document_id="doc_article_a",
        selector_type=SelectorType.EXACT_TEXT,
        exact_text="Article A says the rollout was delayed.",
        created_at=created_at,
    )


def source_assertion_fixture(updated_at: datetime = BEFORE) -> Assertion:
    return Assertion(
        id="ast_article_a_claim",
        assertion_type=AssertionType.SOURCE_CLAIM,
        subject_entity_id="org_anthropic",
        predicate="delayed_rollout",
        object_value={"model": "Claude Fable 5"},
        status=AssertionStatus.REPORTED,
        source_ids=("src_article_a",),
        evidence_span_ids=("evs_article_a_claim",),
        provenance_activity_ids=("prv_review_claim",),
        current_assessment="The Source reports the rollout was delayed.",
        created_at=updated_at,
        updated_at=updated_at,
    )


def analytic_assertion_fixture(updated_at: datetime = BEFORE) -> Assertion:
    return Assertion(
        id="ast_shared_governance",
        assertion_type=AssertionType.ANALYTIC_INFERENCE,
        subject_entity_id="org_anthropic",
        predicate="shared_governance_outcome_with",
        object_entity_id="org_commerce_department",
        status=AssertionStatus.CORROBORATED,
        provenance_activity_ids=("prv_review_inference",),
        current_assessment="Anthropic and Commerce shared a governance outcome.",
        created_at=updated_at,
        updated_at=updated_at,
    )


def relationship_fixture(updated_at: datetime = BEFORE) -> Relationship:
    return Relationship(
        id="rel_shared_governance",
        subject_id="org_anthropic",
        predicate="shared_governance_outcome_with",
        object_id="org_commerce_department",
        assertion_ids=("ast_shared_governance",),
        created_at=updated_at,
        updated_at=updated_at,
    )


def argument_edge_fixture(created_at: datetime = BEFORE) -> ArgumentEdge:
    return ArgumentEdge(
        id="arg_claim_infers_governance",
        from_assertion_id="ast_article_a_claim",
        to_assertion_id="ast_shared_governance",
        relation=ArgumentEdgeRelation.INFERS,
        rationale="The Source claim participates in the governance outcome pattern.",
        evidence_span_ids=("evs_article_a_claim",),
        confidence=0.7,
        created_at=created_at,
    )
