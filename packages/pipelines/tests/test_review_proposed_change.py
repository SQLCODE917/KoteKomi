from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import AssertionStatus, ProposedChange, ReviewStatus
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


def review_reject_args(ledger_path: Path, proposed_change_id: str) -> list[str]:
    return [
        "review",
        "reject",
        "--proposed-change-id",
        proposed_change_id,
        "--reviewer",
        "analyst",
        "--reason",
        "duplicate actor",
        "--ledger-path",
        str(ledger_path),
    ]


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


def test_review_commands_approve_and_reject_proposed_changes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
        proposed_changes = repository.list_proposed_changes()
    organization_change = proposed_change_by_stable_label(
        proposed_changes,
        "anthropic_ai_lab",
    )
    evidence_change = proposed_change_by_stable_label(
        proposed_changes,
        "delay_after_us_cyber_concerns",
    )
    assertion_change = proposed_change_by_stable_label(
        proposed_changes,
        "anthropic_postponed_fable5_after_us_review",
    )
    actor_change = proposed_change_by_stable_label(proposed_changes, "dario_amodei")

    assert main(review_approve_args(ledger_path, organization_change.id)) == 0
    organization_output = capsys.readouterr().out
    assert "Review status: approved" in organization_output
    assert "Accepted record type: Organization" in organization_output
    assert main(review_approve_args(ledger_path, evidence_change.id)) == 0
    capsys.readouterr()
    assert main(review_approve_args(ledger_path, assertion_change.id)) == 0
    assertion_output = capsys.readouterr().out
    assert "Accepted record type: Assertion" in assertion_output
    assert main(review_reject_args(ledger_path, actor_change.id)) == 0
    rejection_output = capsys.readouterr().out
    assert "Review status: rejected" in rejection_output

    with sqlite_ledger_transaction(ledger_path) as repository:
        organization = repository.get_organization("org_anthropic")
        evidence_span = repository.get_evidence_span("evs_delay_after_us_cyber_concerns")
        assertion = repository.get_assertion("ast_anthropic_postponed_fable5_after_us_review")
        rejected_actor = repository.get_actor("act_dario_amodei")
        approved_changes = {
            organization_change.id: repository.get_proposed_change(organization_change.id),
            evidence_change.id: repository.get_proposed_change(evidence_change.id),
            assertion_change.id: repository.get_proposed_change(assertion_change.id),
        }
        rejected_change = repository.get_proposed_change(actor_change.id)
        review_activities = tuple(
            activity
            for activity in repository.list_provenance_activities()
            if activity.activity_type in {"proposed_change_approved", "proposed_change_rejected"}
        )

    assert organization is not None
    assert evidence_span is not None
    assert assertion is not None
    assert assertion.status is AssertionStatus.REPORTED
    assert assertion.provenance_activity_ids
    assert rejected_actor is None
    assert all(
        proposed_change is not None
        and proposed_change.review_status is ReviewStatus.APPROVED
        and proposed_change.accepted_json is not None
        for proposed_change in approved_changes.values()
    )
    assert rejected_change is not None
    assert rejected_change.review_status is ReviewStatus.REJECTED
    assert rejected_change.accepted_json is None
    assert len(review_activities) == 4
