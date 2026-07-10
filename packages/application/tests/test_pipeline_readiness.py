from datetime import UTC, datetime, timedelta

import pytest
from kotekomi_application import (
    AcceptedCanonicalRecord,
    PipelineNextStep,
    PipelineRunNextResult,
    PipelineStage,
    PipelineStatusInput,
    get_pipeline_next,
    get_pipeline_status,
    pipeline_next_to_json,
    pipeline_status_to_json,
    run_next_result_to_json,
)
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    Briefing,
    Document,
    Entity,
    EpistemicScope,
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
    SourceAuthority,
    SourceType,
)

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
PLAN_INPUT = PipelineStatusInput(
    ledger_path="/tmp/kotekomi.db",
    archive_path="/tmp/archive",
)


class FakePipelineLedger:
    def __init__(
        self,
        *,
        records: tuple[AcceptedCanonicalRecord, ...] = (),
        proposed_changes: tuple[ProposedChange, ...] = (),
        briefings: tuple[Briefing, ...] = (),
    ) -> None:
        self.records = records
        self.proposed_changes = {record.id: record for record in proposed_changes}
        self.briefings = briefings
        self.sources = {
            record.id: record for record in records if isinstance(record, Source)
        }
        self.documents = {
            record.id: record for record in records if isinstance(record, Document)
        }
        self.entities = {
            record.id: record for record in records if isinstance(record, Entity)
        }
        self.actors = {record.id: record for record in records if isinstance(record, Actor)}
        self.organizations = {
            record.id: record for record in records if isinstance(record, Organization)
        }
        self.places = {record.id: record for record in records if isinstance(record, Place)}
        self.events = {record.id: record for record in records if isinstance(record, Event)}
        self.evidence_spans = {
            record.id: record for record in records if isinstance(record, EvidenceSpan)
        }
        self.assertions = {
            record.id: record for record in records if isinstance(record, Assertion)
        }
        self.relationships = {
            record.id: record for record in records if isinstance(record, Relationship)
        }
        self.outcomes = {
            record.id: record for record in records if isinstance(record, Outcome)
        }
        self.argument_edges = {
            record.id: record for record in records if isinstance(record, ArgumentEdge)
        }

    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]:
        return self.records

    def list_briefings(self) -> tuple[Briefing, ...]:
        return self.briefings

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

    def get_place(self, record_id: str) -> Place | None:
        return self.places.get(record_id)

    def get_event(self, record_id: str) -> Event | None:
        return self.events.get(record_id)

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


def test_pipeline_status_empty_ledger_recommends_source_ingest() -> None:
    status = get_pipeline_status(PipelineStatusInput(), FakePipelineLedger())

    assert status.stage is PipelineStage.READY_FOR_SOURCE_INGEST
    assert status.next_command == "kotekomi source add-file <path>"
    assert status.safe_commands == ("kotekomi source add-file <path>",)
    assert status.source_count == 0


def test_pipeline_status_document_without_assertions_recommends_assertion_proposal() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(),
        FakePipelineLedger(records=(source_fixture(), document_fixture())),
    )

    assert status.stage is PipelineStage.READY_FOR_ASSERTION_PROPOSAL
    assert status.next_command == (
        "kotekomi source propose-assertions --document-id <document_id> "
        "--model-output-fixture <path>"
    )
    assert status.candidate_document_ids == ("doc_article_a",)


def test_pipeline_status_pending_review_blocks_downstream_commands() -> None:
    ledger = FakePipelineLedger(
        records=(source_fixture(), document_fixture(), organization_fixture()),
        proposed_changes=(pending_assertion_change(evidence_span_ids=("evs_missing",)),),
    )

    status = get_pipeline_status(PipelineStatusInput(), ledger)
    next_step = get_pipeline_next(PipelineStatusInput(), ledger)

    assert status.stage is PipelineStage.REVIEW_REQUIRED
    assert status.review_required is True
    assert status.pending_count == 1
    assert status.missing_reference_count == 1
    assert status.blocked_commands == (
        "kotekomi graph project",
        "kotekomi graph mine",
        "kotekomi briefing generate --title <title>",
    )
    assert [(blocker.blocker_type, blocker.blocker_id) for blocker in status.blockers] == [
        ("EvidenceSpan", "evs_missing")
    ]
    assert next_step.command == "kotekomi review next"
    assert next_step.requires_human_review is True


def test_pipeline_status_recommends_graph_mining_for_accepted_fixture_shape() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(),
        FakePipelineLedger(records=graph_ready_records()),
    )

    assert status.stage is PipelineStage.READY_FOR_GRAPH_MINING
    assert status.next_command == "kotekomi graph mine"
    assert status.safe_commands == ("kotekomi graph project", "kotekomi graph mine")
    assert status.accepted_assertion_count == 1
    assert status.relationship_count == 1
    assert status.outcome_count == 1


def test_pipeline_status_recommends_briefing_after_analytic_records() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(),
        FakePipelineLedger(records=(*graph_ready_records(), analytic_assertion_fixture())),
    )

    assert status.stage is PipelineStage.READY_FOR_BRIEFING
    assert status.next_command == "kotekomi briefing generate --title <title>"


def test_pipeline_status_reports_briefing_current_when_no_newer_records_exist() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(),
        FakePipelineLedger(
            records=(*graph_ready_records(), analytic_assertion_fixture()),
            briefings=(briefing_fixture(generated_at=LATER),),
        ),
    )

    assert status.stage is PipelineStage.BRIEFING_CURRENT
    assert status.next_command is None
    assert status.briefing_count == 1


def test_pipeline_json_serializers_emit_agent_readable_values() -> None:
    ledger = FakePipelineLedger(records=graph_ready_records())

    status_json = pipeline_status_to_json(
        get_pipeline_status(PipelineStatusInput(), ledger)
    )
    next_json = pipeline_next_to_json(get_pipeline_next(PipelineStatusInput(), ledger))

    assert status_json["stage"] == "ready_for_graph_mining"
    assert status_json["safe_commands"] == [
        "kotekomi graph project",
        "kotekomi graph mine",
    ]
    assert next_json["command"] == "kotekomi graph mine"
    assert next_json["blocked"] is False


def test_run_next_result_json_serializes_execution_state_and_output() -> None:
    next_step = get_pipeline_next(
        PLAN_INPUT,
        FakePipelineLedger(records=graph_ready_records()),
    )
    result = PipelineRunNextResult(
        stage=next_step.stage,
        command=next_step.command,
        command_plan=next_step.command_plan,
        ready_to_execute=True,
        executed=True,
        dry_run=False,
        exit_code=0,
        stdout_lines=("Candidates: 1",),
        stderr_lines=(),
        reason=next_step.reason,
    )

    payload = run_next_result_to_json(result)

    assert payload["stage"] == "ready_for_graph_mining"
    assert payload["command"] == "kotekomi graph mine"
    assert payload["ready_to_execute"] is True
    assert payload["executed"] is True
    assert payload["dry_run"] is False
    assert payload["exit_code"] == 0
    assert payload["stdout_lines"] == ["Candidates: 1"]
    assert payload["command_plan"] == next_json_command_plan(next_step)


def test_run_next_result_json_serializes_missing_inputs_and_blockers() -> None:
    next_step = get_pipeline_next(PipelineStatusInput(), FakePipelineLedger())
    result = PipelineRunNextResult(
        stage=next_step.stage,
        command=next_step.command,
        command_plan=next_step.command_plan,
        ready_to_execute=False,
        executed=False,
        dry_run=False,
        exit_code=2,
        stdout_lines=(),
        stderr_lines=(),
        reason=next_step.reason,
    )

    payload = run_next_result_to_json(result)
    command_plan = payload["command_plan"]

    assert payload["ready_to_execute"] is False
    assert payload["executed"] is False
    assert payload["exit_code"] == 2
    assert isinstance(command_plan, dict)
    assert command_plan["missing_inputs"] == [
        {
            "allowed_values": [],
            "description": "Path to a local Source file.",
            "kind": "path",
            "name": "source_file_path",
            "required": True,
        },
        {
            "allowed_values": [],
            "description": "Path to the Ledger SQLite file.",
            "kind": "path",
            "name": "ledger_path",
            "required": True,
        },
        {
            "allowed_values": [],
            "description": "Path to the Archive root.",
            "kind": "path",
            "name": "archive_path",
            "required": True,
        },
    ]


def next_json_command_plan(next_step: PipelineNextStep) -> object:
    payload = pipeline_next_to_json(next_step)
    return payload["command_plan"]


def test_command_plan_requires_source_path_for_source_ingest() -> None:
    status = get_pipeline_status(PLAN_INPUT, FakePipelineLedger())

    assert status.next_command_plan.ready_to_execute is False
    assert status.next_command_plan.argv == ()
    assert [item.name for item in status.next_command_plan.missing_inputs] == [
        "source_file_path"
    ]


def test_command_plan_builds_source_ingest_argv_with_supplied_source_path() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(
            ledger_path="/tmp/kotekomi.db",
            archive_path="/tmp/archive",
            source_file_path="/tmp/article.md",
        ),
        FakePipelineLedger(),
    )

    assert status.next_command_plan.ready_to_execute is True
    assert status.next_command_plan.argv == (
        "source",
        "add-file",
        "/tmp/article.md",
        "--ledger-path",
        "/tmp/kotekomi.db",
        "--archive-path",
        "/tmp/archive",
    )


def test_command_plan_auto_selects_single_candidate_document_for_assertion_proposal() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(
            ledger_path="/tmp/kotekomi.db",
            archive_path="/tmp/archive",
            model_output_fixture_path="/tmp/proposals.json",
        ),
        FakePipelineLedger(records=(source_fixture(), document_fixture())),
    )

    assert status.next_command_plan.ready_to_execute is True
    assert status.next_command_plan.argv == (
        "source",
        "propose-assertions",
        "--document-id",
        "doc_article_a",
        "--model-output-fixture",
        "/tmp/proposals.json",
        "--ledger-path",
        "/tmp/kotekomi.db",
        "--archive-path",
        "/tmp/archive",
    )


def test_command_plan_requires_document_id_when_multiple_candidates_exist() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(
            ledger_path="/tmp/kotekomi.db",
            archive_path="/tmp/archive",
            model_output_fixture_path="/tmp/proposals.json",
        ),
        FakePipelineLedger(
            records=(
                source_fixture(),
                document_fixture(),
                document_fixture("doc_article_b", content_sha256="b" * 64),
            )
        ),
    )

    assert status.next_command_plan.ready_to_execute is False
    assert status.next_command_plan.missing_inputs[0].name == "document_id"
    assert status.next_command_plan.missing_inputs[0].allowed_values == (
        "doc_article_a",
        "doc_article_b",
    )


def test_command_plan_rejects_non_candidate_document_id() -> None:
    with pytest.raises(ValueError, match="is not a candidate Document"):
        get_pipeline_status(
            PipelineStatusInput(
                ledger_path="/tmp/kotekomi.db",
                archive_path="/tmp/archive",
                model_output_fixture_path="/tmp/proposals.json",
                document_id="doc_missing",
            ),
            FakePipelineLedger(records=(source_fixture(), document_fixture())),
        )


def test_command_plan_returns_review_next_argv_with_review_blockers() -> None:
    ledger = FakePipelineLedger(
        records=(source_fixture(), document_fixture(), organization_fixture()),
        proposed_changes=(pending_assertion_change(evidence_span_ids=("evs_missing",)),),
    )

    next_step = get_pipeline_next(PLAN_INPUT, ledger)

    assert next_step.command_plan.ready_to_execute is True
    assert next_step.command_plan.argv == (
        "review",
        "next",
        "--ledger-path",
        "/tmp/kotekomi.db",
    )
    assert next_step.command_plan.blockers[0].blocker_id == "evs_missing"


def test_command_plan_returns_graph_mining_argv() -> None:
    next_step = get_pipeline_next(
        PLAN_INPUT,
        FakePipelineLedger(records=graph_ready_records()),
    )

    assert next_step.command_plan.ready_to_execute is True
    assert next_step.command_plan.argv == (
        "graph",
        "mine",
        "--ledger-path",
        "/tmp/kotekomi.db",
    )


def test_command_plan_requires_briefing_title_for_briefing_generation() -> None:
    status = get_pipeline_status(
        PLAN_INPUT,
        FakePipelineLedger(records=(*graph_ready_records(), analytic_assertion_fixture())),
    )

    assert status.next_command_plan.ready_to_execute is False
    assert [item.name for item in status.next_command_plan.missing_inputs] == [
        "briefing_title"
    ]


def test_command_plan_returns_briefing_generation_argv_with_title() -> None:
    status = get_pipeline_status(
        PipelineStatusInput(
            ledger_path="/tmp/kotekomi.db",
            archive_path="/tmp/archive",
            briefing_title="Daily Briefing",
        ),
        FakePipelineLedger(records=(*graph_ready_records(), analytic_assertion_fixture())),
    )

    assert status.next_command_plan.ready_to_execute is True
    assert status.next_command_plan.argv == (
        "briefing",
        "generate",
        "--title",
        "Daily Briefing",
        "--ledger-path",
        "/tmp/kotekomi.db",
        "--archive-path",
        "/tmp/archive",
    )


def test_command_plan_has_no_argv_when_briefing_is_current() -> None:
    status = get_pipeline_status(
        PLAN_INPUT,
        FakePipelineLedger(
            records=(*graph_ready_records(), analytic_assertion_fixture()),
            briefings=(briefing_fixture(generated_at=LATER),),
        ),
    )

    assert status.next_command_plan.ready_to_execute is False
    assert status.next_command_plan.command is None
    assert status.next_command_plan.argv == ()
    assert status.next_command_plan.missing_inputs == ()


def source_fixture() -> Source:
    return Source(
        id="src_article_a",
        source_type=SourceType.ARTICLE,
        title="Article A",
        created_at=NOW,
        updated_at=NOW,
    )


def document_fixture(
    document_id: str = "doc_article_a",
    *,
    content_sha256: str = "a" * 64,
) -> Document:
    return Document(
        id=document_id,
        source_id="src_article_a",
        raw_path=f"sources/raw/{document_id}.bin",
        extracted_text_path=f"documents/extracted/{document_id}.txt",
        content_sha256=content_sha256,
        created_at=NOW,
        updated_at=NOW,
    )


def organization_fixture() -> Organization:
    return Organization(
        id="org_anthropic",
        name="Anthropic",
        organization_type="ai_lab",
        created_at=NOW,
        updated_at=NOW,
    )


def evidence_span_fixture() -> EvidenceSpan:
    return EvidenceSpan(
        id="evs_delay",
        source_id="src_article_a",
        document_id="doc_article_a",
        selector_type=SelectorType.EXACT_TEXT,
        exact_text="Anthropic delayed the rollout.",
        created_at=NOW,
    )


def assertion_fixture() -> Assertion:
    return Assertion(
        id="ast_delay",
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="delayed_rollout",
        object_value={"model": "Claude Fable 5"},
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_report_confidence=0.9,
        extraction_confidence=0.92,
        world_truth_confidence=0.6,
        source_ids=("src_article_a",),
        evidence_span_ids=("evs_delay",),
        provenance_activity_ids=("prv_review",),
        created_at=NOW,
        updated_at=NOW,
    )


def analytic_assertion_fixture() -> Assertion:
    return Assertion(
        id="ast_governance_constraint",
        assertion_type=AssertionType.ANALYTIC_INFERENCE,
        epistemic_scope=EpistemicScope.ANALYTIC_INFERENCE,
        subject_entity_id="org_anthropic",
        predicate="faced_governance_constraint",
        object_value={"from": "Commerce review pressure"},
        status=AssertionStatus.REPORTED,
        source_authority=SourceAuthority.NOT_APPLICABLE,
        attribution_basis=AttributionBasis.NOT_APPLICABLE,
        causal_confidence=0.7,
        qualifiers={"causal": True},
        provenance_activity_ids=("prv_graph_mining",),
        created_at=NOW,
        updated_at=NOW,
    )


def relationship_fixture() -> Relationship:
    return Relationship(
        id="rel_anthropic_reported_by_article",
        subject_id="org_anthropic",
        predicate="reported_in",
        object_id="org_anthropic",
        assertion_ids=("ast_delay",),
        created_at=NOW,
        updated_at=NOW,
    )


def outcome_fixture() -> Outcome:
    return Outcome(
        id="out_release_delay",
        description="The model rollout was delayed.",
        organization_ids=("org_anthropic",),
        assertion_ids=("ast_delay",),
        created_at=NOW,
        updated_at=NOW,
    )


def argument_edge_fixture() -> ArgumentEdge:
    return ArgumentEdge(
        id="arg_delay_supports_constraint",
        from_assertion_id="ast_delay",
        to_assertion_id="ast_governance_constraint",
        relation=ArgumentEdgeRelation.SUPPORTS,
        rationale="The delay supports the inferred governance constraint.",
        confidence=0.74,
        created_at=NOW,
    )


def graph_ready_records() -> tuple[AcceptedCanonicalRecord, ...]:
    return (
        source_fixture(),
        document_fixture(),
        organization_fixture(),
        evidence_span_fixture(),
        assertion_fixture(),
        relationship_fixture(),
        outcome_fixture(),
    )


def briefing_fixture(*, generated_at: datetime) -> Briefing:
    return Briefing(
        id="brf_daily",
        title="Daily Briefing",
        source_ids=("src_article_a",),
        document_ids=("doc_article_a",),
        organization_ids=("org_anthropic",),
        evidence_span_ids=("evs_delay",),
        assertion_ids=("ast_delay", "ast_governance_constraint"),
        relationship_ids=("rel_anthropic_reported_by_article",),
        outcome_ids=("out_release_delay",),
        provenance_activity_id="prv_briefing",
        generated_at=generated_at,
    )


def pending_assertion_change(
    *,
    evidence_span_ids: tuple[str, ...],
) -> ProposedChange:
    return ProposedChange(
        id="pcg_assertion",
        review_status=ReviewStatus.PENDING,
        proposed_json={
            "record_type": "Assertion",
            "stable_label": "delay_assertion",
            "record": {
                "id": "ast_pending_delay",
                "assertion_type": "source_claim",
                "epistemic_scope": "source_report",
                "subject_entity_id": "org_anthropic",
                "predicate": "delayed_rollout",
                "object_value": {"model": "Claude Fable 5"},
                "status": "proposed",
                "source_authority": "secondary",
                "attribution_basis": "reported_by_source",
                "source_report_confidence": 0.9,
                "extraction_confidence": 0.92,
                "world_truth_confidence": 0.6,
                "source_ids": ["src_article_a"],
                "evidence_span_ids": list(evidence_span_ids),
                "provenance_activity_ids": [],
            },
            "evidence": {
                "selector_type": "exact_text",
                "exact_text": "Anthropic delayed the rollout.",
                "prefix_text": "",
                "suffix_text": "",
                "location": {"section": "body"},
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
