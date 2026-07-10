import json
from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import ProposedChange, ReviewStatus
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
        "--model-runtime",
        "fixture",
        "--model-output-fixture",
        str(MODEL_OUTPUT_FIXTURE_PATH),
        "--ledger-path",
        str(ledger_path),
        "--archive-path",
        str(archive_path),
    ]


def review_list_args(ledger_path: Path) -> list[str]:
    return [
        "review",
        "list",
        "--ledger-path",
        str(ledger_path),
    ]


def review_list_json_args(ledger_path: Path) -> list[str]:
    return [
        "review",
        "list",
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
    ]


def review_next_args(ledger_path: Path) -> list[str]:
    return [
        "review",
        "next",
        "--ledger-path",
        str(ledger_path),
    ]


def review_next_json_args(ledger_path: Path) -> list[str]:
    return [
        "review",
        "next",
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
    ]


def review_show_args(ledger_path: Path, proposed_change_id: str) -> list[str]:
    return [
        "review",
        "show",
        "--proposed-change-id",
        proposed_change_id,
        "--ledger-path",
        str(ledger_path),
    ]


def review_show_json_args(ledger_path: Path, proposed_change_id: str) -> list[str]:
    return [
        "review",
        "show",
        "--proposed-change-id",
        proposed_change_id,
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
    ]


def review_status_args(ledger_path: Path) -> list[str]:
    return [
        "review",
        "status",
        "--ledger-path",
        str(ledger_path),
    ]


def review_status_json_args(ledger_path: Path) -> list[str]:
    return [
        "review",
        "status",
        "--format",
        "json",
        "--ledger-path",
        str(ledger_path),
    ]


def review_export_args(
    ledger_path: Path,
    proposed_change_id: str,
    output_path: Path,
) -> list[str]:
    return [
        "review",
        "export",
        "--proposed-change-id",
        proposed_change_id,
        "--output",
        str(output_path),
        "--ledger-path",
        str(ledger_path),
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


def review_edit_args(
    ledger_path: Path,
    proposed_change_id: str,
    accepted_record_json_path: Path,
) -> list[str]:
    return [
        "review",
        "edit",
        "--proposed-change-id",
        proposed_change_id,
        "--reviewer",
        "analyst",
        "--accepted-record-json",
        str(accepted_record_json_path),
        "--ledger-path",
        str(ledger_path),
    ]


def test_review_list_and_show_render_fixture_review_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)
    with sqlite_ledger_transaction(ledger_path) as repository:
        proposed_changes = repository.list_proposed_changes()
    assertion_change = proposed_change_by_stable_label(
        proposed_changes,
        "anthropic_postponed_fable5_after_us_review",
    )

    assert main(review_list_args(ledger_path)) == 0
    list_output = capsys.readouterr().out
    assert "Review Queue: 16" in list_output
    assert "ProposedChange | Status | RecordType | StableLabel" in list_output
    assert "anthropic_ai_lab" in list_output
    assert "anthropic_postponed_fable5_after_us_review" in list_output
    assert "fixture-extraction-runtime" in list_output

    assert main(review_show_args(ledger_path, assertion_change.id)) == 0
    show_output = capsys.readouterr().out
    assert "Record type: Assertion" in show_output
    assert "Stable label: anthropic_postponed_fable5_after_us_review" in show_output
    assert "Epistemic scope: source_report" in show_output
    assert "Source authority: secondary" in show_output
    assert "Attribution basis: anonymous_source" in show_output
    assert "Anthropic postponed a broader rollout of its Claude Fable 5 model" in show_output
    assert "Organization: org_anthropic (pending)" in show_output
    assert "EvidenceSpan: evs_delay_after_us_cyber_concerns (pending)" in show_output


def test_review_next_renders_fixture_packet_and_advances_after_approval(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert main(review_next_args(ledger_path)) == 0
    next_output = capsys.readouterr().out
    assert "Next ProposedChange:" in next_output
    assert "Record type: Organization" in next_output
    assert "Stable label: anthropic_ai_lab" in next_output
    assert "Review action plans:" in next_output
    assert "approve: kotekomi review run-next --decision approve (ready: no)" in next_output

    assert main(review_next_json_args(ledger_path)) == 0
    next_json = json.loads(capsys.readouterr().out)
    assert next_json["has_next"] is True
    assert next_json["item"]["record_type"] == "Organization"
    assert next_json["item"]["stable_label"] == "anthropic_ai_lab"
    assert next_json["packet"]["record_type"] == "Organization"
    assert [action_plan["action"] for action_plan in next_json["action_plans"]] == [
        "approve",
        "reject",
        "edit",
    ]

    first_change_id = next_json["item"]["proposed_change_id"]
    assert main(review_approve_args(ledger_path, first_change_id)) == 0
    capsys.readouterr()

    assert main(review_next_json_args(ledger_path)) == 0
    advanced_json = json.loads(capsys.readouterr().out)
    assert advanced_json["has_next"] is True
    assert advanced_json["item"]["proposed_change_id"] != first_change_id
    assert advanced_json["item"]["record_type"] == "Organization"


def test_review_export_writes_json_that_can_feed_review_edit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)
    with sqlite_ledger_transaction(ledger_path) as repository:
        organization_change = proposed_change_by_stable_label(
            repository.list_proposed_changes(),
            "anthropic_ai_lab",
        )
    exported_json_path = tmp_path / "exported_organization.json"

    assert main(review_export_args(ledger_path, organization_change.id, exported_json_path)) == 0
    export_output = capsys.readouterr().out
    assert "Record type: Organization" in export_output
    assert exported_json_path.exists()
    exported_json = exported_json_path.read_text(encoding="utf-8")
    assert '"id": "org_anthropic"' in exported_json
    assert "record_type" not in exported_json
    assert "stable_label" not in exported_json

    assert main(review_edit_args(ledger_path, organization_change.id, exported_json_path)) == 0
    edit_output = capsys.readouterr().out
    assert "Review status: edited" in edit_output
    assert "Accepted record type: Organization" in edit_output
    with sqlite_ledger_transaction(ledger_path) as repository:
        organization = repository.get_organization("org_anthropic")
        reviewed_change = repository.get_proposed_change(organization_change.id)
    assert organization is not None
    assert reviewed_change is not None
    assert reviewed_change.review_status is ReviewStatus.EDITED


def test_review_status_and_json_outputs_are_agent_readable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)
    with sqlite_ledger_transaction(ledger_path) as repository:
        proposed_changes = repository.list_proposed_changes()
    assertion_change = proposed_change_by_stable_label(
        proposed_changes,
        "anthropic_postponed_fable5_after_us_review",
    )

    assert main(review_status_args(ledger_path)) == 0
    status_text = capsys.readouterr().out
    assert "Review required: yes" in status_text
    assert "Pending ProposedChanges: 16" in status_text
    assert "Can project graph: no" in status_text
    assert "Next recommended command: kotekomi review next" in status_text

    assert main(review_status_json_args(ledger_path)) == 0
    status_json = json.loads(capsys.readouterr().out)
    assert status_json["review_required"] is True
    assert status_json["pending_count"] == 16
    assert status_json["can_project_graph"] is False
    assert status_json["can_generate_briefing"] is False
    assert status_json["pending_record_type_counts"]["Assertion"] == 3
    assert status_json["next_recommended_command"] == "kotekomi review next"

    assert main(review_list_json_args(ledger_path)) == 0
    list_json = json.loads(capsys.readouterr().out)
    assert len(list_json["items"]) == 16
    assert list_json["items"][0]["record_type"] == "Organization"

    assert main(review_show_json_args(ledger_path, assertion_change.id)) == 0
    packet_json = json.loads(capsys.readouterr().out)
    assert packet_json["record_type"] == "Assertion"
    assert packet_json["assertion_context"]["epistemic_scope"] == "source_report"
    assert packet_json["reference_contexts"][0]["resolution_status"] in {
        "accepted",
        "pending",
        "missing",
    }


def test_review_status_reports_ready_after_fixture_review_queue_resolves(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)
    with sqlite_ledger_transaction(ledger_path) as repository:
        proposed_changes = repository.list_proposed_changes()
    approve_proposed_changes_in_review_order(
        ledger_path=ledger_path,
        proposed_changes=proposed_changes,
        main=main,
        review_approve_args=review_approve_args,
        clear_output=capsys.readouterr,
    )

    assert main(review_status_json_args(ledger_path)) == 0
    status_json = json.loads(capsys.readouterr().out)
    assert status_json == {
        "blockers": [],
        "can_generate_briefing": True,
        "can_project_graph": True,
        "missing_reference_count": 0,
        "next_recommended_command": "kotekomi graph project",
        "pending_count": 0,
        "pending_record_type_counts": {},
        "pending_reference_count": 0,
        "review_required": False,
    }


def prepare_fixture_proposals(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> tuple[Path, Path]:
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
    return ledger_path, archive_path


def proposed_change_by_stable_label(
    proposed_changes: tuple[ProposedChange, ...],
    stable_label: str,
) -> ProposedChange:
    for proposed_change in proposed_changes:
        label = proposed_change.proposed_json["stable_label"]
        assert isinstance(label, str)
        if label == stable_label:
            return proposed_change
    raise AssertionError(f"Missing ProposedChange stable_label: {stable_label}")
