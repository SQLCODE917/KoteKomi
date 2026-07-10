import json
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
        "--model-runtime",
        "fixture",
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


def review_run_next_args(
    ledger_path: Path,
    decision: str,
    *,
    reason: str | None = None,
    accepted_record_json_path: Path | None = None,
    dry_run: bool = False,
    output_format: str = "text",
) -> list[str]:
    args = [
        "review",
        "run-next",
        "--decision",
        decision,
        "--reviewer",
        "analyst",
        "--ledger-path",
        str(ledger_path),
    ]
    if reason is not None:
        args.extend(("--reason", reason))
    if accepted_record_json_path is not None:
        args.extend(("--accepted-record-json", str(accepted_record_json_path)))
    if dry_run:
        args.append("--dry-run")
    if output_format != "text":
        args.extend(("--format", output_format))
    return args


def review_drain_args(
    ledger_path: Path,
    decision: str,
    *,
    reason: str | None = None,
    accepted_record_json_path: Path | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    output_format: str = "text",
) -> list[str]:
    args = [
        "review",
        "drain",
        "--decision",
        decision,
        "--reviewer",
        "analyst",
        "--ledger-path",
        str(ledger_path),
    ]
    if reason is not None:
        args.extend(("--reason", reason))
    if accepted_record_json_path is not None:
        args.extend(("--accepted-record-json", str(accepted_record_json_path)))
    if limit is not None:
        args.extend(("--limit", str(limit)))
    if dry_run:
        args.append("--dry-run")
    if output_format != "text":
        args.extend(("--format", output_format))
    return args


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


def test_review_run_next_approves_next_fixture_proposed_change(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert (
        main(review_run_next_args(ledger_path, "approve", output_format="json"))
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["has_next"] is True
    assert payload["decision"] == "approve"
    assert payload["executed"] is True
    assert payload["item"]["stable_label"] == "anthropic_ai_lab"
    assert payload["review_result"]["review_status"] == "approved"
    with sqlite_ledger_transaction(ledger_path) as repository:
        organization = repository.get_organization("org_anthropic")
        proposed_change = repository.get_proposed_change(payload["item"]["proposed_change_id"])
    assert organization is not None
    assert proposed_change is not None
    assert proposed_change.review_status is ReviewStatus.APPROVED


def test_review_run_next_rejects_next_fixture_proposed_change(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert (
        main(
            review_run_next_args(
                ledger_path,
                "reject",
                reason="duplicate Organization",
                output_format="json",
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["decision"] == "reject"
    assert payload["executed"] is True
    assert payload["item"]["stable_label"] == "anthropic_ai_lab"
    assert payload["review_result"]["review_status"] == "rejected"
    with sqlite_ledger_transaction(ledger_path) as repository:
        proposed_change = repository.get_proposed_change(payload["item"]["proposed_change_id"])
        organization = repository.get_organization("org_anthropic")
    assert proposed_change is not None
    assert proposed_change.review_status is ReviewStatus.REJECTED
    assert organization is None


def test_review_run_next_edits_next_fixture_proposed_change(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)
    accepted_record_json_path = tmp_path / "edited_organization.json"
    accepted_record_json_path.write_text(
        json.dumps(
            {
                "id": "org_anthropic",
                "name": "Anthropic",
                "organization_type": "ai_lab",
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            review_run_next_args(
                ledger_path,
                "edit",
                accepted_record_json_path=accepted_record_json_path,
                output_format="json",
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["decision"] == "edit"
    assert payload["executed"] is True
    assert payload["item"]["stable_label"] == "anthropic_ai_lab"
    assert payload["review_result"]["review_status"] == "edited"
    with sqlite_ledger_transaction(ledger_path) as repository:
        proposed_change = repository.get_proposed_change(payload["item"]["proposed_change_id"])
        organization = repository.get_organization("org_anthropic")
    assert proposed_change is not None
    assert proposed_change.review_status is ReviewStatus.EDITED
    assert organization is not None


def test_review_run_next_dry_run_leaves_fixture_pending(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert (
        main(
            review_run_next_args(
                ledger_path,
                "approve",
                dry_run=True,
                output_format="json",
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["has_next"] is True
    assert payload["executed"] is False
    assert payload["dry_run"] is True
    assert payload["item"]["stable_label"] == "anthropic_ai_lab"
    with sqlite_ledger_transaction(ledger_path) as repository:
        proposed_change = repository.get_proposed_change(payload["item"]["proposed_change_id"])
        pending_changes = tuple(
            change
            for change in repository.list_proposed_changes()
            if change.review_status is ReviewStatus.PENDING
        )
    assert proposed_change is not None
    assert proposed_change.review_status is ReviewStatus.PENDING
    assert len(pending_changes) == 16


def test_review_drain_approves_fixture_queue(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert (
        main(review_drain_args(ledger_path, "approve", output_format="json"))
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["decision"] == "approve"
    assert payload["stopped_reason"] == "queue_empty"
    assert payload["executed_count"] == 16
    assert len(payload["item_results"]) == 16
    with sqlite_ledger_transaction(ledger_path) as repository:
        pending_changes = tuple(
            change
            for change in repository.list_proposed_changes()
            if change.review_status is ReviewStatus.PENDING
        )
        organization = repository.get_organization("org_anthropic")
    assert pending_changes == ()
    assert organization is not None


def test_review_drain_limit_approves_bounded_fixture_items(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert (
        main(
            review_drain_args(
                ledger_path,
                "approve",
                limit=2,
                output_format="json",
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["stopped_reason"] == "limit_reached"
    assert payload["executed_count"] == 2
    with sqlite_ledger_transaction(ledger_path) as repository:
        pending_changes = tuple(
            change
            for change in repository.list_proposed_changes()
            if change.review_status is ReviewStatus.PENDING
        )
    assert len(pending_changes) == 14


def test_review_drain_dry_run_leaves_fixture_pending(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert (
        main(
            review_drain_args(
                ledger_path,
                "approve",
                dry_run=True,
                output_format="json",
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["stopped_reason"] == "dry_run_complete"
    assert payload["attempted_count"] == 16
    assert payload["executed_count"] == 0
    with sqlite_ledger_transaction(ledger_path) as repository:
        pending_changes = tuple(
            change
            for change in repository.list_proposed_changes()
            if change.review_status is ReviewStatus.PENDING
        )
    assert len(pending_changes) == 16


def test_review_drain_rejects_one_fixture_item(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)

    assert (
        main(
            review_drain_args(
                ledger_path,
                "reject",
                reason="duplicate Organization",
                limit=1,
                output_format="json",
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["decision"] == "reject"
    assert payload["stopped_reason"] == "limit_reached"
    assert payload["executed_count"] == 1
    assert payload["item_results"][0]["review_result"]["review_status"] == "rejected"


def test_review_drain_edits_one_fixture_item(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path, _ = prepare_fixture_proposals(tmp_path, capsys)
    accepted_record_json_path = tmp_path / "edited_organization.json"
    accepted_record_json_path.write_text(
        json.dumps(
            {
                "id": "org_anthropic",
                "name": "Anthropic",
                "organization_type": "ai_lab",
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            review_drain_args(
                ledger_path,
                "edit",
                accepted_record_json_path=accepted_record_json_path,
                limit=1,
                output_format="json",
            )
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["decision"] == "edit"
    assert payload["stopped_reason"] == "limit_reached"
    assert payload["executed_count"] == 1
    assert payload["item_results"][0]["review_result"]["review_status"] == "edited"


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
    enterprise_evidence_change = proposed_change_by_stable_label(
        proposed_changes,
        "enterprise_pilots_suspended",
    )
    assertion_change = proposed_change_by_stable_label(
        proposed_changes,
        "anthropic_postponed_fable5_after_us_review",
    )
    edited_actor_change = proposed_change_by_stable_label(proposed_changes, "lina_rahman")
    edited_assertion_change = proposed_change_by_stable_label(
        proposed_changes,
        "enterprise_pilots_suspended_on_june_23",
    )
    actor_change = proposed_change_by_stable_label(proposed_changes, "dario_amodei")
    edited_actor_path = tmp_path / "edited_actor.json"
    edited_actor_path.write_text(
        json.dumps(
            {
                "id": "act_lina_rahman",
                "name": "Lina Rahman",
                "role_names": ["security lead for model deployment", "deployment reviewer"],
                "organization_ids": ["org_anthropic"],
            }
        )
    )
    edited_assertion_path = tmp_path / "edited_assertion.json"
    edited_assertion_path.write_text(
        json.dumps(
            {
                "id": "ast_enterprise_pilots_suspended_on_june_23",
                "assertion_type": "source_claim",
                "epistemic_scope": "source_report",
                "subject_entity_id": "org_anthropic",
                "predicate": "temporarily_suspended_enterprise_pilot_access",
                "object_value": {
                    "date": "2026-06-23",
                    "affected_customer_segments": [
                        "finance",
                        "defense contracting",
                        "pharmaceutical research",
                    ],
                    "exception": (
                        "smaller evaluation program for approved U.S. government and "
                        "safety researchers"
                    ),
                },
                "status": "proposed",
                "source_authority": "secondary",
                "attribution_basis": "reported_by_source",
                "source_report_confidence": 0.93,
                "extraction_confidence": 0.9,
                "world_truth_confidence": 0.66,
                "current_assessment": (
                    "The Source reports that Anthropic suspended several enterprise pilots "
                    "while keeping an approved evaluation program open."
                ),
                "source_ids": ["src_aa67767133655af72fbcf0a8"],
                "evidence_span_ids": ["evs_enterprise_pilots_suspended"],
                "provenance_activity_ids": [],
            }
        )
    )

    assert main(review_approve_args(ledger_path, organization_change.id)) == 0
    organization_output = capsys.readouterr().out
    assert "Review status: approved" in organization_output
    assert "Accepted record type: Organization" in organization_output
    assert main(review_approve_args(ledger_path, evidence_change.id)) == 0
    capsys.readouterr()
    assert main(review_approve_args(ledger_path, enterprise_evidence_change.id)) == 0
    capsys.readouterr()
    assert main(review_approve_args(ledger_path, assertion_change.id)) == 0
    assertion_output = capsys.readouterr().out
    assert "Accepted record type: Assertion" in assertion_output
    assert main(review_reject_args(ledger_path, actor_change.id)) == 0
    rejection_output = capsys.readouterr().out
    assert "Review status: rejected" in rejection_output
    assert main(review_edit_args(ledger_path, edited_actor_change.id, edited_actor_path)) == 0
    edited_actor_output = capsys.readouterr().out
    assert "Review status: edited" in edited_actor_output
    assert "Accepted record type: Actor" in edited_actor_output
    assert (
        main(review_edit_args(ledger_path, edited_assertion_change.id, edited_assertion_path)) == 0
    )
    edited_assertion_output = capsys.readouterr().out
    assert "Review status: edited" in edited_assertion_output
    assert "Accepted record type: Assertion" in edited_assertion_output

    with sqlite_ledger_transaction(ledger_path) as repository:
        organization = repository.get_organization("org_anthropic")
        evidence_span = repository.get_evidence_span("evs_delay_after_us_cyber_concerns")
        enterprise_evidence_span = repository.get_evidence_span("evs_enterprise_pilots_suspended")
        assertion = repository.get_assertion("ast_anthropic_postponed_fable5_after_us_review")
        edited_actor = repository.get_actor("act_lina_rahman")
        edited_assertion = repository.get_assertion("ast_enterprise_pilots_suspended_on_june_23")
        rejected_actor = repository.get_actor("act_dario_amodei")
        approved_changes = {
            organization_change.id: repository.get_proposed_change(organization_change.id),
            evidence_change.id: repository.get_proposed_change(evidence_change.id),
            enterprise_evidence_change.id: repository.get_proposed_change(
                enterprise_evidence_change.id
            ),
            assertion_change.id: repository.get_proposed_change(assertion_change.id),
        }
        edited_changes = {
            edited_actor_change.id: repository.get_proposed_change(edited_actor_change.id),
            edited_assertion_change.id: repository.get_proposed_change(edited_assertion_change.id),
        }
        rejected_change = repository.get_proposed_change(actor_change.id)
        review_activities = tuple(
            activity
            for activity in repository.list_provenance_activities()
            if activity.activity_type
            in {
                "proposed_change_approved",
                "proposed_change_rejected",
                "proposed_change_edited",
            }
        )

    assert organization is not None
    assert evidence_span is not None
    assert enterprise_evidence_span is not None
    assert assertion is not None
    assert assertion.status is AssertionStatus.REPORTED
    assert assertion.provenance_activity_ids
    assert edited_actor is not None
    assert edited_actor.role_names == ("security lead for model deployment", "deployment reviewer")
    assert edited_assertion is not None
    assert edited_assertion.status is AssertionStatus.REPORTED
    assert edited_assertion.current_assessment == (
        "The Source reports that Anthropic suspended several enterprise pilots while keeping "
        "an approved evaluation program open."
    )
    assert rejected_actor is None
    assert all(
        proposed_change is not None
        and proposed_change.review_status is ReviewStatus.APPROVED
        and proposed_change.accepted_json is not None
        for proposed_change in approved_changes.values()
    )
    assert all(
        proposed_change is not None
        and proposed_change.review_status is ReviewStatus.EDITED
        and proposed_change.original_proposed_json is not None
        and proposed_change.accepted_json is not None
        for proposed_change in edited_changes.values()
    )
    assert rejected_change is not None
    assert rejected_change.review_status is ReviewStatus.REJECTED
    assert rejected_change.accepted_json is None
    assert len(review_activities) == 7
