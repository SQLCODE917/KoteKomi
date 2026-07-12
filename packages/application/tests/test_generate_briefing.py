from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_application import (
    AcceptedCanonicalRecord,
    ArchiveObject,
    ArchivePutDisposition,
    ArchivePutOutcome,
    BriefingGenerationInput,
    BriefingMarkdown,
    BriefingRenderInput,
    StagedArchiveObject,
    generate_briefing,
    read_briefing_citation_registry,
    resolve_briefing_citation,
)
from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Briefing,
    Document,
    EpistemicScope,
    Event,
    EvidenceTarget,
    Organization,
    Outcome,
    ProvenanceActivity,
    Relationship,
    Source,
    SourceAuthority,
    SourceType,
)

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
BEFORE = NOW - timedelta(days=1)
AFTER = NOW + timedelta(minutes=1)


class FakeArchiveStore:
    def __init__(self) -> None:
        self.staged: dict[str, bytes] = {}
        self.markdown: dict[str, str] = {}
        self.citations_json: dict[str, str] = {}
        self.deleted_paths: list[str] = []

    def initialize(self) -> None:
        return None

    def put_if_absent_or_identical(
        self, object_id: str, payload: bytes, expected_digest: str
    ) -> ArchivePutOutcome:
        return ArchivePutOutcome(
            ArchivePutDisposition.CREATED,
            ArchiveObject(f"sources/raw/{object_id}.bin", len(payload)),
        )

    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject:
        raise NotImplementedError

    def read_raw_source(self, source_id: str) -> bytes:
        raise NotImplementedError

    def read_briefing_markdown(self, briefing_id: str) -> str:
        return self.markdown[briefing_id]

    def read_briefing_citations_json(self, briefing_id: str) -> str:
        return self.citations_json[briefing_id]

    def stage_raw_source(self, source_id: str, content: bytes) -> StagedArchiveObject:
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

    def stage_briefing_citations_json(
        self,
        briefing_id: str,
        citations_json: str,
    ) -> StagedArchiveObject:
        staged_path = f".staging/briefings/daily/{briefing_id}.citations.json.tmp"
        self.staged[staged_path] = citations_json.encode("utf-8")
        return StagedArchiveObject(
            staged_relative_path=staged_path,
            final_object=ArchiveObject(
                relative_path=f"briefings/daily/{briefing_id}.citations.json",
                size_bytes=len(citations_json.encode("utf-8")),
            ),
        )

    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject:
        content = self.staged.pop(staged_object.staged_relative_path)
        relative_path = staged_object.final_object.relative_path
        if relative_path.endswith(".citations.json"):
            briefing_id = relative_path.removeprefix("briefings/daily/").removesuffix(
                ".citations.json"
            )
            self.citations_json[briefing_id] = content.decode("utf-8")
        else:
            briefing_id = relative_path.removeprefix("briefings/daily/").removesuffix(".md")
            self.markdown[briefing_id] = content.decode("utf-8")
        return staged_object.final_object

    def delete_object(self, relative_path: str) -> None:
        self.deleted_paths.append(relative_path)
        self.staged.pop(relative_path, None)
        if relative_path.startswith("briefings/daily/"):
            if relative_path.endswith(".citations.json"):
                briefing_id = relative_path.removeprefix("briefings/daily/").removesuffix(
                    ".citations.json"
                )
                self.citations_json.pop(briefing_id, None)
            else:
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
        records: tuple[AcceptedCanonicalRecord, ...] = (),
        briefings: tuple[Briefing, ...] = (),
    ) -> None:
        self.records = records
        self.briefings = {record.id: record for record in briefings}
        self.provenance_activities: dict[str, ProvenanceActivity] = {}

    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]:
        return self.records

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
    document = document_fixture(updated_at=BEFORE)
    evidence_target = evidence_target_fixture(created_at=BEFORE)
    assertion = source_assertion_fixture(updated_at=BEFORE)
    analytic_assertion = analytic_assertion_fixture(updated_at=BEFORE)
    relationship = relationship_fixture(updated_at=BEFORE)
    argument_edge = argument_edge_fixture(created_at=BEFORE)
    ledger = FakeBriefingLedger(
        records=(
            organization_fixture(),
            organization_fixture("org_commerce_department", "Commerce Department"),
            source,
            document,
            evidence_target,
            analytic_assertion,
            assertion,
            relationship,
            argument_edge,
        ),
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
    assert result.document_count == 1
    assert result.organization_count == 2
    assert result.assertion_count == 2
    assert result.relationship_count == 1
    assert result.argument_edge_count == 1
    assert result.evidence_target_count == 1
    assert result.analytic_inference_count == 1
    assert briefing.source_ids == (source.id,)
    assert briefing.document_ids == (document.id,)
    assert briefing.organization_ids == ("org_anthropic", "org_commerce_department")
    assert briefing.assertion_ids == (assertion.id, analytic_assertion.id)
    assert briefing.relationship_ids == (relationship.id,)
    assert briefing.argument_edge_ids == (argument_edge.id,)
    assert briefing.evidence_target_ids == (evidence_target.id,)
    assert briefing.analytic_inference_assertion_ids == (analytic_assertion.id,)
    assert briefing.provenance_activity_id == result.provenance_activity_id
    assert archive.markdown[result.briefing_id] == "# Daily Briefing\n"
    assert result.citation_registry_path == f"briefings/daily/{result.briefing_id}.citations.json"
    assert archive.staged == {}
    assert renderer.calls[0].previous_briefing_id is None
    assert renderer.calls[0].analytic_inference_assertion_ids == (analytic_assertion.id,)
    registry = read_briefing_citation_registry(
        briefing_id=result.briefing_id,
        archive_store=archive,
    )
    assert renderer.calls[0].citation_registry == registry
    narrative = renderer.calls[0].narrative
    assert len(narrative.what_changed) == 1
    assert narrative.what_changed[0].text == "Source report: The rollout was delayed."
    assert narrative.what_changed[0].citation_numbers == (1,)
    what_changed_citation = resolve_briefing_citation(
        registry,
        narrative.what_changed[0].citation_numbers[0],
    )
    assert what_changed_citation.assertion_ids == (assertion.id,)
    assert what_changed_citation.source_ids == (source.id,)
    assert what_changed_citation.document_ids == (document.id,)
    assert what_changed_citation.evidence_target_ids == (evidence_target.id,)
    assert narrative.executive_judgment is None
    assert narrative.judgment_basis == ()
    analytic_citation = resolve_briefing_citation(
        registry,
        narrative.reference_appendix.analytic_trace[0].citation_numbers[0],
    )
    assert analytic_citation.is_analytic_inference is True
    assert analytic_citation.assertion_ids == (assertion.id, analytic_assertion.id)
    assert analytic_citation.argument_edge_ids == (argument_edge.id,)
    assert analytic_citation.source_ids == (source.id,)
    assert analytic_citation.evidence_target_ids == (evidence_target.id,)
    assert narrative.evidence_quality[0].source_count == 1
    assert narrative.evidence_quality[0].evidence_target_count == 1
    assert narrative.evidence_quality[0].source_authority is SourceAuthority.SECONDARY
    assert narrative.evidence_quality[0].attribution_basis is AttributionBasis.REPORTED_BY_SOURCE
    assert len(narrative.reference_appendix.analytic_trace) == 1
    assert narrative.reference_appendix.analytic_trace[0].finding == (
        "Anthropic and Commerce Department share a release-governance outcome."
    )
    assert narrative.reference_appendix.analytic_trace[0].support == "The rollout was delayed."
    assert narrative.reference_appendix.analytic_trace[0].relation == "supports"
    collection_gap_text = "\n".join(gap.text for gap in narrative.collection_gaps)
    assert (
        "The inference that Anthropic and Commerce Department share a release-governance "
        "outcome is derived from source-backed claims" in collection_gap_text
    )
    assert (
        narrative.reference_appendix.collection_requirements[-1].closes_with
        == "A Source that directly states the inferred governance relationship."
    )
    activity = ledger.provenance_activities[result.provenance_activity_id]
    assert activity.activity_type == "briefing_generation"
    assert activity.output_ids == (result.briefing_id,)


def test_generate_briefing_builds_outcome_narrative_with_uncertainties() -> None:
    source = source_fixture(updated_at=BEFORE)
    document = document_fixture(updated_at=BEFORE)
    evidence_target = evidence_target_fixture(created_at=BEFORE)
    assertion = source_assertion_fixture(updated_at=BEFORE)
    outcome = Outcome(
        id="out_monitoring_commitment",
        description="Anthropic resumed access with notice commitments.",
        organization_ids=("org_anthropic", "org_commerce_department"),
        event_ids=("evt_review_call",),
        assertion_ids=(assertion.id,),
        created_at=BEFORE,
        updated_at=BEFORE,
    )
    event = Event(
        id="evt_review_call",
        name="Emergency release review call",
        participant_organization_ids=(
            "org_anthropic",
            "org_commerce_department",
            "org_treasury_department",
        ),
        created_at=BEFORE,
        updated_at=BEFORE,
    )
    ledger = FakeBriefingLedger(
        records=(
            organization_fixture(),
            organization_fixture("org_commerce_department", "Commerce Department"),
            organization_fixture("org_treasury_department", "Treasury Department"),
            event,
            source,
            document,
            evidence_target,
            assertion,
            outcome,
        ),
    )
    renderer = FakeBriefingRenderer()

    result = generate_briefing(
        BriefingGenerationInput(title="Daily Briefing", generated_at=NOW),
        ledger,
        FakeArchiveStore(),
        renderer,
    )

    narrative = renderer.calls[0].narrative
    registry = renderer.calls[0].citation_registry
    assert registry.briefing_id == result.briefing_id
    assert tuple(sentence.text for sentence in narrative.what_changed) == (
        "Source report: The rollout was delayed.",
        "Anthropic resumed access with notice commitments.",
        "The result connects Anthropic, Commerce Department, and Emergency release review call.",
    )
    assert narrative.what_changed[0].citation_numbers == (1,)
    assert narrative.what_changed[1].citation_numbers == (2,)
    assert narrative.what_changed[2].citation_numbers == (2,)
    source_citation = resolve_briefing_citation(registry, 1)
    outcome_citation = resolve_briefing_citation(registry, 2)
    assert source_citation.assertion_ids == (assertion.id,)
    assert source_citation.source_ids == (source.id,)
    assert source_citation.evidence_target_ids == (evidence_target.id,)
    assert outcome_citation.outcome_ids == (outcome.id,)
    assert outcome_citation.assertion_ids == (assertion.id,)
    assert outcome_citation.organization_ids == (
        "org_anthropic",
        "org_commerce_department",
    )
    assert outcome_citation.event_ids == (event.id,)
    assert narrative.evidence_quality[0].claim.text == "Source report: The rollout was delayed."
    assert narrative.evidence_quality[0].source_authority is SourceAuthority.SECONDARY
    assert narrative.evidence_quality[0].attribution_basis is AttributionBasis.REPORTED_BY_SOURCE
    collection_gap_text = "\n".join(gap.text for gap in narrative.collection_gaps)
    assert "no Place recorded" not in collection_gap_text
    assert "Treasury Department" not in collection_gap_text
    assert "No independent Source corroborates" in collection_gap_text
    assert "The rollout was delayed" in collection_gap_text
    assert "source-backed Assertions" not in collection_gap_text
    assert "No primary-source record confirms" in collection_gap_text


def test_generate_briefing_builds_sharp_judgment_from_canonical_support() -> None:
    source = source_fixture(updated_at=BEFORE)
    document = document_fixture(updated_at=BEFORE)
    pause_evidence = EvidenceTarget(
        id="etg_pause",
        source_id=source.id,
        document_id=document.id,
        exact_text="Commerce Secretary Howard Lutnick pressed for a pause.",
        representation_id="rep_article_a",
        text_view_id="tvw_article_a",
        text_view_digest="0" * 64,
        start_char=0,
        end_char=56,
        normalization_policy="fixture_v1",
        node_ids=("nod_article_a",),
        created_at=BEFORE,
    )
    delay_evidence = EvidenceTarget(
        id="etg_delay",
        source_id=source.id,
        document_id=document.id,
        exact_text="Anthropic postponed broader Fable 5 rollout.",
        representation_id="rep_article_a",
        text_view_id="tvw_article_a",
        text_view_digest="0" * 64,
        start_char=0,
        end_char=44,
        normalization_policy="fixture_v1",
        node_ids=("nod_article_a",),
        created_at=BEFORE,
    )
    suspension_evidence = EvidenceTarget(
        id="etg_suspension",
        source_id=source.id,
        document_id=document.id,
        exact_text="Anthropic suspended enterprise pilots on June 23.",
        representation_id="rep_article_a",
        text_view_id="tvw_article_a",
        text_view_digest="0" * 64,
        start_char=0,
        end_char=49,
        normalization_policy="fixture_v1",
        node_ids=("nod_article_a",),
        created_at=BEFORE,
    )
    pause_assertion = Assertion(
        id="ast_pause",
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_commerce_department",
        predicate="pressed_for_pause_pending_customer_separation_review",
        object_value={"target": "Anthropic Claude Fable 5 rollout"},
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=(source.id,),
        evidence_target_ids=(pause_evidence.id,),
        provenance_activity_ids=("prv_review_pause",),
        current_assessment=(
            "The article states that Commerce Secretary Howard Lutnick pressed for a pause "
            "until Commerce could assess customer-separation controls."
        ),
        created_at=BEFORE,
        updated_at=BEFORE,
    )
    delay_assertion = Assertion(
        id="ast_delay",
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="postponed_broader_rollout_after_review",
        object_value={"model": "Claude Fable 5"},
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.ANONYMOUS_SOURCE,
        source_ids=(source.id,),
        evidence_target_ids=(delay_evidence.id,),
        provenance_activity_ids=("prv_review_delay",),
        qualifiers={"reported_by": "people involved in the review and described documents"},
        current_assessment="The Source reports that Anthropic postponed broader Fable 5 rollout.",
        created_at=BEFORE,
        updated_at=BEFORE,
    )
    suspension_assertion = Assertion(
        id="ast_suspension",
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="temporarily_suspended_enterprise_pilot_access",
        object_value={"date": "2026-06-23"},
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=(source.id,),
        evidence_target_ids=(suspension_evidence.id,),
        provenance_activity_ids=("prv_review_suspension",),
        current_assessment="The Source reports that Anthropic suspended enterprise pilots.",
        created_at=BEFORE,
        updated_at=BEFORE,
    )
    analytic_assertion = analytic_assertion_fixture(updated_at=BEFORE)
    edges = tuple(
        ArgumentEdge(
            id=edge_id,
            from_assertion_id=from_assertion_id,
            to_assertion_id=analytic_assertion.id,
            relation=ArgumentEdgeRelation.INFERS,
            rationale="The source-backed Assertion supports the governance inference.",
            confidence=0.7,
            evidence_target_ids=(evidence_target_id,),
            created_at=BEFORE,
        )
        for edge_id, from_assertion_id, evidence_target_id in (
            ("arg_pause", pause_assertion.id, pause_evidence.id),
            ("arg_delay", delay_assertion.id, delay_evidence.id),
            ("arg_suspension", suspension_assertion.id, suspension_evidence.id),
        )
    )
    ledger = FakeBriefingLedger(
        records=(
            organization_fixture(),
            organization_fixture("org_commerce_department", "Commerce Department"),
            source,
            document,
            pause_evidence,
            delay_evidence,
            suspension_evidence,
            pause_assertion,
            delay_assertion,
            suspension_assertion,
            analytic_assertion,
            *edges,
        ),
    )
    renderer = FakeBriefingRenderer()

    generate_briefing(
        BriefingGenerationInput(title="Daily Briefing", generated_at=NOW),
        ledger,
        FakeArchiveStore(),
        renderer,
    )

    narrative = renderer.calls[0].narrative
    assert narrative.executive_judgment is not None
    judgment_basis = narrative.judgment_basis[0]
    assert narrative.executive_judgment.text == (
        "KoteKomi assesses that Commerce review pressure became a release-governance "
        "constraint on Anthropic's Claude Fable 5 rollout."
    )
    assert judgment_basis.source_basis[0].text == (
        "The article states that Commerce Secretary Howard Lutnick pressed for a pause until "
        "Commerce could assess customer-separation controls."
    )
    assert "secondary reporting rather than primary-source confirmation" in (
        judgment_basis.source_basis[1].text
    )
    assert len(judgment_basis.observed_effects) == 2
    assert "appears" not in narrative.executive_judgment.text
    assert "one Source" in judgment_basis.confidence.text


def test_generate_briefing_uses_latest_previous_briefing_as_change_boundary() -> None:
    previous = Briefing(
        id="brf_previous",
        title="Previous Briefing",
        provenance_activity_id="prv_previous",
        generated_at=NOW,
    )
    older_source = source_fixture(updated_at=BEFORE)
    document = document_fixture(updated_at=BEFORE)
    newer_source = Source(
        id="src_newer",
        source_type=SourceType.ARTICLE,
        identity_policy_id="fixture_v1",
        canonical_identity_key="newer",
        created_at=AFTER,
        updated_at=AFTER,
    )
    newer_assertion = source_assertion_fixture(updated_at=AFTER)
    newer_evidence_target = evidence_target_fixture(created_at=AFTER)
    ledger = FakeBriefingLedger(
        records=(
            organization_fixture(),
            older_source,
            newer_source,
            document,
            newer_assertion,
            newer_evidence_target,
        ),
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
    assert briefing.organization_ids == ("org_anthropic",)
    assert briefing.document_ids == (document.id,)
    assert briefing.assertion_ids == (newer_assertion.id,)
    assert briefing.evidence_target_ids == (newer_evidence_target.id,)


def test_generate_briefing_rejects_source_backed_assertion_missing_evidence_target() -> None:
    ledger = FakeBriefingLedger(
        records=(
            organization_fixture(),
            source_fixture(),
            document_fixture(),
            source_assertion_fixture(),
        ),
    )
    archive = FakeArchiveStore()

    with pytest.raises(ValueError, match="references missing EvidenceTarget"):
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
        identity_policy_id="fixture_v1",
        canonical_identity_key="article_a",
        created_at=updated_at,
        updated_at=updated_at,
    )


def document_fixture(updated_at: datetime = BEFORE) -> Document:
    return Document(
        id="doc_article_a",
        source_id="src_article_a",
        content_sha256="a" * 64,
        created_at=updated_at,
        updated_at=updated_at,
    )


def organization_fixture(
    organization_id: str = "org_anthropic",
    name: str = "Anthropic",
    updated_at: datetime = BEFORE,
) -> Organization:
    return Organization(
        id=organization_id,
        name=name,
        created_at=updated_at,
        updated_at=updated_at,
    )


def evidence_target_fixture(created_at: datetime = BEFORE) -> EvidenceTarget:
    return EvidenceTarget(
        id="etg_article_a_claim",
        source_id="src_article_a",
        document_id="doc_article_a",
        exact_text="Article A says the rollout was delayed.",
        representation_id="rep_article_a",
        text_view_id="tvw_article_a",
        text_view_digest="0" * 64,
        start_char=0,
        end_char=37,
        normalization_policy="fixture_v1",
        node_ids=("nod_article_a",),
        created_at=created_at,
    )


def source_assertion_fixture(updated_at: datetime = BEFORE) -> Assertion:
    return Assertion(
        id="ast_article_a_claim",
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="delayed_rollout",
        object_value={"model": "Claude Fable 5"},
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        world_truth_confidence=0.6,
        source_ids=("src_article_a",),
        evidence_target_ids=("etg_article_a_claim",),
        provenance_activity_ids=("prv_review_claim",),
        current_assessment="The Source reports the rollout was delayed.",
        created_at=updated_at,
        updated_at=updated_at,
    )


def analytic_assertion_fixture(updated_at: datetime = BEFORE) -> Assertion:
    return Assertion(
        id="ast_shared_governance",
        assertion_type=AssertionType.ANALYTIC_INFERENCE,
        epistemic_scope=EpistemicScope.ANALYTIC_INFERENCE,
        subject_entity_id="org_anthropic",
        predicate="shared_governance_outcome_with",
        object_entity_id="org_commerce_department",
        status=AssertionStatus.CORROBORATED,
        source_authority=SourceAuthority.NOT_APPLICABLE,
        attribution_basis=AttributionBasis.NOT_APPLICABLE,
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
        evidence_target_ids=("etg_article_a_claim",),
        confidence=0.7,
        created_at=created_at,
    )
