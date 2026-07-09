from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import ProposedChange, ReviewStatus
from kotekomi_pipelines.cli import main

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


def review_list_args(ledger_path: Path) -> list[str]:
    return [
        "review",
        "list",
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
