from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
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
    assert "Entities: 0" in output
    assert "Actors: 2" in output
    assert "Organizations: 4" in output
    assert "Places: 0" in output
    assert "Events: 1" in output
    assert "Sources: 1" in output
    assert "Documents: 1" in output
    assert "Assertions: 3" in output
    assert "Relationships: 2" in output
    assert "Outcomes: 1" in output
    assert "ArgumentEdges: 2" in output
    assert "EvidenceSpans: 2" in output
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
    assert briefing.actor_ids == ("act_dario_amodei", "act_lina_rahman")
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
    assert len(briefing.assertion_ids) == 3
    assert len(briefing.relationship_ids) == 2
    assert briefing.outcome_ids == ("out_monitoring_update_and_notice_commitment",)
    assert len(briefing.argument_edge_ids) == 2
    assert len(briefing.evidence_span_ids) == 2
    assert len(briefing.analytic_inference_assertion_ids) == 1

    markdown = (archive_path / briefing.markdown_path).read_text(encoding="utf-8")
    assert "# Daily Briefing" in markdown
    assert "Anthropic" in markdown
    assert "Commerce Department" in markdown
    assert "Treasury Department" in markdown
    assert "White House" in markdown
    assert "Dario Amodei" in markdown
    assert "Lina Rahman" in markdown
    assert "June 21 emergency Claude Fable 5 release review call" in markdown
    assert (
        "Anthropic resumed most access while agreeing to incident summaries and extra notice "
        "before major capability increases." in markdown
    )
    assert "`src_aa67767133655af72fbcf0a8`" in markdown
    assert "`doc_aa67767133655af72fbcf0a8`" in markdown
    assert "`evs_delay_after_us_cyber_concerns`" in markdown
    assert "`evs_enterprise_pilots_suspended`" in markdown
    assert "Analytic inference" in markdown


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
