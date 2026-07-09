from pathlib import Path

import pytest
from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    read_briefing_citation_registry,
)
from kotekomi_domain import Briefing, ReviewStatus
from kotekomi_pipelines.cli import main

from packages.pipelines.tests.review_helpers import approve_proposed_changes_in_review_order

SOURCE_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "source_files"
    / "anthropic_model_release_review.md"
)
MODEL_OUTPUT_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "model_outputs"
    / "anthropic_model_release_review_proposals.json"
)


def ledger_init_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "ledger",
        "init",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def source_add_file_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "source",
        "add-file",
        str(SOURCE_FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def propose_assertions_args(
    ledger_path: Path,
    archive_path: Path,
    document_id: str,
) -> list[str]:
    return [
        "source",
        "propose-assertions",
        "--document-id",
        document_id,
        "--model-output-fixture",
        str(MODEL_OUTPUT_FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def review_approve_args(ledger_path: Path, proposed_change_id: str) -> list[str]:
    return [
        "review",
        "approve",
        "--proposed-change-id",
        proposed_change_id,
        "--reviewer",
        "analyst",
        "--ledger-path",
        str(ledger_path),
    ]


def graph_mine_args(ledger_path: Path) -> list[str]:
    return [
        "graph",
        "mine",
        "--ledger-path",
        str(ledger_path),
    ]


def briefing_generate_args(ledger_path: Path, archive_path: Path) -> list[str]:
    return [
        "briefing",
        "generate",
        "--title",
        "Daily Briefing",
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def run_fixture_article_to_briefing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> tuple[Path, Path, str]:
    ledger_path = tmp_path / "ledger" / "kotekomi.db"
    archive_path = tmp_path / "archive"
    assert main(ledger_init_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    assert main(source_add_file_args(ledger_path, archive_path)) == 0
    capsys.readouterr()
    with sqlite_ledger_transaction(ledger_path) as repository:
        document = repository.list_documents()[0]

    assert main(propose_assertions_args(ledger_path, archive_path, document.id)) == 0
    capsys.readouterr()
    with sqlite_ledger_transaction(ledger_path) as repository:
        initial_changes = repository.list_proposed_changes()
    approve_proposed_changes_in_review_order(
        ledger_path=ledger_path,
        proposed_changes=initial_changes,
        main=main,
        review_approve_args=review_approve_args,
        clear_output=capsys.readouterr,
    )

    assert main(graph_mine_args(ledger_path)) == 0
    capsys.readouterr()
    with sqlite_ledger_transaction(ledger_path) as repository:
        mined_changes = tuple(
            change
            for change in repository.list_proposed_changes()
            if change.review_status is ReviewStatus.PENDING
        )
    approve_proposed_changes_in_review_order(
        ledger_path=ledger_path,
        proposed_changes=mined_changes,
        main=main,
        review_approve_args=review_approve_args,
        clear_output=capsys.readouterr,
    )

    exit_code = main(briefing_generate_args(ledger_path, archive_path))

    output = capsys.readouterr().out
    assert exit_code == 0
    return ledger_path, archive_path, output


def briefing_canonical_record_ids(briefing: Briefing) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *briefing.entity_ids,
                *briefing.actor_ids,
                *briefing.organization_ids,
                *briefing.place_ids,
                *briefing.event_ids,
                *briefing.source_ids,
                *briefing.document_ids,
                *briefing.evidence_span_ids,
                *briefing.assertion_ids,
                *briefing.relationship_ids,
                *briefing.outcome_ids,
                *briefing.argument_edge_ids,
            }
        )
    )


def test_briefing_generate_writes_markdown_and_briefing_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, archive_path, output = run_fixture_article_to_briefing(tmp_path, capsys)

    assert "Briefing: brf_" in output
    assert "ProvenanceActivity: prv_" in output
    assert "Markdown path: briefings/daily/brf_" in output
    assert "Citations path: briefings/daily/brf_" in output
    assert "Entities: 0" in output
    assert "Actors: 3" in output
    assert "Organizations: 4" in output
    assert "Places: 0" in output
    assert "Events: 1" in output
    assert "Sources: 1" in output
    assert "Documents: 1" in output
    assert "Assertions: 4" in output
    assert "Relationships: 2" in output
    assert "Outcomes: 1" in output
    assert "ArgumentEdges: 3" in output
    assert "EvidenceSpans: 3" in output
    assert "Analytic inferences: 1" in output
    with sqlite_ledger_transaction(ledger_path) as repository:
        briefings = repository.list_briefings()
        activities = tuple(
            activity
            for activity in repository.list_provenance_activities()
            if activity.activity_type == "briefing_generation"
        )

    assert len(briefings) == 1
    assert len(activities) == 1
    briefing = briefings[0]
    assert briefing.markdown_path is not None
    assert briefing.provenance_activity_id == activities[0].id
    assert briefing.entity_ids == ()
    assert briefing.actor_ids == ("act_dario_amodei", "act_howard_lutnick", "act_lina_rahman")
    assert briefing.organization_ids == (
        "org_anthropic",
        "org_commerce_department",
        "org_treasury_department",
        "org_white_house",
    )
    assert briefing.place_ids == ()
    assert briefing.event_ids == ("evt_june_21_emergency_release_review_call",)
    assert briefing.source_ids == ("src_aa67767133655af72fbcf0a8",)
    assert briefing.document_ids == ("doc_aa67767133655af72fbcf0a8",)
    assert len(briefing.assertion_ids) == 4
    assert len(briefing.relationship_ids) == 2
    assert briefing.outcome_ids == ("out_monitoring_update_and_notice_commitment",)
    assert len(briefing.argument_edge_ids) == 3
    assert len(briefing.evidence_span_ids) == 3
    assert len(briefing.analytic_inference_assertion_ids) == 1

    markdown = (archive_path / briefing.markdown_path).read_text(encoding="utf-8")
    citation_registry_path = archive_path / "briefings" / "daily" / f"{briefing.id}.citations.json"
    assert citation_registry_path.is_file()
    registry = read_briefing_citation_registry(
        briefing_id=briefing.id,
        archive_store=LocalArchiveStore(archive_path),
    )
    delay_citation = next(
        citation
        for citation in registry.citations
        if citation.assertion_ids == ("ast_anthropic_postponed_fable5_after_us_review",)
    )
    suspension_citation = next(
        citation
        for citation in registry.citations
        if citation.assertion_ids == ("ast_enterprise_pilots_suspended_on_june_23",)
    )
    lutnick_citation = next(
        citation
        for citation in registry.citations
        if citation.assertion_ids == ("ast_lutnick_pressed_pause_for_customer_separation_review",)
    )
    analytic_citations = tuple(
        citation for citation in registry.citations if citation.is_analytic_inference
    )
    assert delay_citation.assertion_ids == ("ast_anthropic_postponed_fable5_after_us_review",)
    assert delay_citation.summary == (
        "Source report: U.S. cyber-safety concerns delayed Anthropic's broader "
        "Claude Fable 5 rollout."
    )
    assert delay_citation.source_ids == ("src_aa67767133655af72fbcf0a8",)
    assert delay_citation.document_ids == ("doc_aa67767133655af72fbcf0a8",)
    assert delay_citation.evidence_span_ids == ("evs_delay_after_us_cyber_concerns",)
    assert suspension_citation.assertion_ids == ("ast_enterprise_pilots_suspended_on_june_23",)
    assert suspension_citation.evidence_span_ids == ("evs_enterprise_pilots_suspended",)
    assert lutnick_citation.evidence_span_ids == (
        "evs_lutnick_pressed_pause_for_customer_separation_review",
    )
    assert len(analytic_citations) == 1
    assert "ast_anthropic_postponed_fable5_after_us_review" in analytic_citations[0].assertion_ids
    assert "ast_enterprise_pilots_suspended_on_june_23" in analytic_citations[0].assertion_ids
    assert (
        "ast_lutnick_pressed_pause_for_customer_separation_review"
        in analytic_citations[0].assertion_ids
    )
    assert analytic_citations[0].argument_edge_ids == briefing.argument_edge_ids
    assert "# Daily Briefing" in markdown
    expected_sections = (
        "## Executive Judgment",
        "## What Changed",
        "## Judgment Basis",
        "## Evidence and Source Quality",
        "## Open Questions and Collection Gaps",
        "## Indicators to Watch",
        "## Implications",
        "## Reference Appendix",
    )
    rendered_sections = tuple(line for line in markdown.splitlines() if line.startswith("## "))
    assert rendered_sections == expected_sections
    for removed_heading in (
        "## Bottom Line",
        "## Judgment",
        "## Key Judgments",
        "## Evidence Basis",
        "## Analytic Trace",
        "## Citations",
    ):
        assert removed_heading not in rendered_sections
    assert (
        "Source report: U.S. cyber-safety concerns delayed Anthropic's broader "
        "Claude Fable 5 rollout." in markdown
    )
    assert (
        "Source report: Anthropic suspended several enterprise pilots while preserving a smaller "
        "approved evaluation program." in markdown
    )
    assert (
        "KoteKomi assesses that Commerce review pressure became a release-governance "
        "constraint on Anthropic's Claude Fable 5 rollout." in markdown
    )
    assert (
        "The article states that Commerce Secretary Howard Lutnick pressed for a pause until "
        "Commerce could assess customer-separation controls." in markdown
    )
    assert (
        "The article attributes the broader delay account to people involved in the review "
        "and described documents, so KoteKomi treats it as secondary reporting rather than "
        "primary-source confirmation." in markdown
    )
    assert (
        "KoteKomi infers a release-governance constraint because Commerce's pause request, "
        "the rollout delay, and the enterprise pilot suspension connect government review to "
        "Anthropic release timing." in markdown
    )
    assert "Confidence: Moderate" in markdown
    assert "Analytic inference" in markdown
    assert "Secondary" in markdown
    assert "Anonymous Source" in markdown
    assert "Reported By Source" in markdown
    assert "Treasury Department" in markdown
    assert "White House" in markdown
    assert "not directly stated by a Source" in markdown
    assert "No primary-source record confirms" in markdown
    assert "No independent Source corroborates" in markdown
    assert (
        "U.S. cyber-safety concerns delayed Anthropic's broader Claude Fable 5 rollout"
        in markdown
    )
    assert "Commerce Secretary Howard Lutnick pressed for a pause" in markdown
    assert "source-backed Assertions" not in markdown
    assert "Watch for primary-source statements" in markdown
    assert "Watch for renewed enterprise pilot suspensions" in markdown
    assert "government review as an operational release constraint" in markdown
    expected_appendix_sections = (
        "### Citation Register",
        "### Source Quality Register",
        "### Analytic Trace",
        "### Collection Requirements",
        "### Entity and Event Index",
    )
    rendered_appendix_sections = tuple(
        line for line in markdown.splitlines() if line.startswith("### ")
    )
    assert rendered_appendix_sections == expected_appendix_sections
    for removed_appendix_heading in (
        "### Citations",
        "### Key Entities",
        "### Key Organizations",
        "### Key Actors",
        "### Key Places",
        "### Key Events",
        "### Outcomes",
        "### Sources",
    ):
        assert removed_appendix_heading not in markdown
    assert (
        "| [2] | Source-backed Assertion | Source report: U.S. cyber-safety concerns delayed"
        in markdown
    )
    assert (
        "| [4] | Analytic inference | Inference: Anthropic and Commerce Department share"
        in markdown
    )
    assert "Source-backed Assertion: Source report" not in markdown
    assert "Source-backed Assertion: The article" not in markdown
    assert "ArgumentEdge:" not in markdown
    assert "Support link" in markdown
    assert "ArgumentEdge |" not in markdown
    assert "Relationship:" not in markdown
    assert "Outcome:" not in markdown
    assert "### Analytic Trace" in markdown
    assert "| Finding | Support | Relation | Confidence |" in markdown
    assert "Relationship derived from selected claims" not in markdown
    assert "### Collection Requirements" in markdown
    assert "A primary government or Anthropic record confirming the review basis." in markdown
    assert "### Entity and Event Index" in markdown
    assert "Source report: U.S. cyber-safety concerns delayed" in markdown
    assert "Source report: Anthropic suspended several enterprise pilots" in markdown
    assert "Anthropic" in markdown
    assert "Commerce Department" in markdown
    assert "Treasury Department" in markdown
    assert "White House" in markdown
    assert "Dario Amodei" in markdown
    assert "Howard Lutnick" in markdown
    assert "Lina Rahman" in markdown
    assert "June 21 emergency Claude Fable 5 release review call" in markdown
    assert (
        "Anthropic resumed most access while agreeing to incident summaries and extra notice "
        "before major capability increases." in markdown
    )
    assert (
        "Inference: Anthropic and Commerce Department share a release-governance outcome"
        in markdown
    )
    assert "Analytic inference" in markdown
    assert "appears to" not in markdown
    assert "Graph mining" not in markdown
    assert "Accepted Relationship" not in markdown
    assert "ArgumentEdges" not in markdown
    assert "source-backed claim that The Source reports" not in markdown
    for raw_prefix in (
        "act_",
        "arg_",
        "ast_",
        "ctn_",
        "doc_",
        "evs_",
        "evt_",
        "org_",
        "rel_",
        "src_",
    ):
        assert raw_prefix not in markdown


def test_fixture_article_briefing_records_every_accepted_canonical_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _, _ = run_fixture_article_to_briefing(tmp_path, capsys)

    with sqlite_ledger_transaction(ledger_path) as repository:
        briefing = repository.list_briefings()[0]
        canonical_record_ids = tuple(
            record.id for record in repository.list_accepted_canonical_records()
        )

    assert canonical_record_ids == briefing_canonical_record_ids(briefing)
