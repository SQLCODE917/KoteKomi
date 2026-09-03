#!/usr/bin/env python3
"""Replay HP-7 over reviewed HP-6 evidence and exercise the review boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import (
    LocalArchiveStore,
    SQLiteLedgerRepository,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    HybridProposalResult,
    ReviewPacketInput,
    ReviewProposedChangeInput,
    approve_proposed_change,
    get_review_packet,
    reject_proposed_change,
    review_packet_to_json,
    run_hybrid_proposal_submission,
)
from kotekomi_domain import ProposedAssertion, ReviewStatus

_REVIEWED_AT = datetime(2026, 9, 3, tzinfo=UTC)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hp6-report", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--ledger-path", type=Path, required=True)
    parser.add_argument("--archive-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    hp6 = _read_json(args.hp6_report)
    gold = _read_json(args.gold)
    _validate_catalog(hp6, gold)
    with tempfile.TemporaryDirectory(prefix="kotekomi-hp7-") as temporary:
        work_root = Path(temporary)
        ledger_path = work_root / "kotekomi.db"
        archive_path = work_root / "archive"
        _copy_sqlite(args.ledger_path, ledger_path)
        shutil.copytree(args.archive_path, archive_path)
        report = _evaluate(
            hp6=hp6,
            gold=gold,
            ledger_path=ledger_path,
            archive_path=archive_path,
        )
    report.update(
        {
            "hp6_report_path": str(args.hp6_report),
            "hp6_report_sha256": hashlib.sha256(args.hp6_report.read_bytes()).hexdigest(),
            "gold_path": str(args.gold),
            "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        }
    )
    args.output.write_text(_canonical_json(report) + "\n")
    summary = cast(dict[str, object], report["summary"])
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] is True else 1


def _validate_catalog(hp6: dict[str, Any], gold: dict[str, Any]) -> None:
    if hp6.get("schema_version") != "hp6_event_semantics_evaluation_v1":
        raise ValueError("HP-7 requires an HP-6 evaluation report.")
    if gold.get("schema_version") != "hp7_proposal_admission_gold_v1":
        raise ValueError("HP-7 Gold schema is unknown.")
    cases = cast(list[dict[str, Any]], gold.get("cases"))
    if len(cases) != 8:
        raise ValueError("HP-7 Gold requires seven approved events and one rejection.")
    outcomes = [item.get("review_outcome") for item in cases]
    if outcomes.count("approved") != 7 or outcomes.count("rejected") != 1:
        raise ValueError("HP-7 Gold review outcomes are incomplete.")
    if any(item.get("expected_disposition") != "proposed" for item in cases):
        raise ValueError("HP-7 Gold expects every reviewed event to reach review.")
    first_runs = {
        cast(str, item["case_id"]): item
        for item in cast(list[dict[str, Any]], hp6["runs"])
        if item.get("repetition") == 1
    }
    if any(item["case_id"] not in first_runs for item in cases):
        raise ValueError("HP-7 Gold references a missing HP-6 case.")


def _evaluate(
    *,
    hp6: dict[str, Any],
    gold: dict[str, Any],
    ledger_path: Path,
    archive_path: Path,
) -> dict[str, object]:
    archive = LocalArchiveStore(archive_path)
    first_runs = {
        cast(str, item["case_id"]): item
        for item in cast(list[dict[str, Any]], hp6["runs"])
        if item.get("repetition") == 1
    }
    results_by_preview: dict[str, tuple[HybridProposalResult, HybridProposalResult]] = {}
    selected: list[dict[str, Any]] = []
    findings: list[dict[str, object]] = []
    for expected in cast(list[dict[str, Any]], gold["cases"]):
        run = first_runs[cast(str, expected["case_id"])]
        preview = cast(dict[str, Any], run["preview"])
        preview_id = cast(str, preview["id"])
        if preview_id not in results_by_preview:
            with sqlite_ledger_transaction(ledger_path) as repository:
                first = run_hybrid_proposal_submission(
                    preview_id=preview_id,
                    submitted_at=_REVIEWED_AT,
                    ledger=repository,
                    archive=archive,
                )
                second = run_hybrid_proposal_submission(
                    preview_id=preview_id,
                    submitted_at=_REVIEWED_AT,
                    ledger=repository,
                    archive=archive,
                )
            results_by_preview[preview_id] = (first, second)
            if first.plan != second.plan or second.publication_disposition != "reused":
                findings.append(
                    {
                        "code": "non_idempotent_submission",
                        "owner": "implementation",
                        "preview_id": preview_id,
                    }
                )
        result = results_by_preview[preview_id][0]
        with sqlite_ledger_transaction(ledger_path) as repository:
            event = _select_event(preview, expected, repository)
        decision = next(
            (item for item in result.plan.decisions if item.event_semantic_id == event["id"]),
            None,
        )
        if decision is None:
            findings.append(
                {
                    "case_id": expected["case_id"],
                    "code": "admission_decision_missing",
                    "owner": "implementation",
                    "trigger": expected["trigger"],
                }
            )
            continue
        if decision.disposition.value != expected["expected_disposition"]:
            findings.append(
                {
                    "case_id": expected["case_id"],
                    "code": "unexpected_disposition",
                    "owner": "policy",
                    "expected": expected["expected_disposition"],
                    "actual": decision.disposition.value,
                    "trigger": expected["trigger"],
                }
            )
        changes = [
            item for item in result.plan.proposed_changes if item.id in decision.proposed_change_ids
        ]
        event_change = next(
            item for item in changes if item.proposed_json["record_type"] == "Event"
        )
        trace = next(
            item
            for item in result.plan.traces
            if cast(dict[str, Any], item.input["event"])["id"] == event["id"]
        )
        with sqlite_ledger_transaction(ledger_path) as repository:
            packet = get_review_packet(ReviewPacketInput(event_change.id), repository)
        selected.append(
            {
                "case_id": expected["case_id"],
                "trigger": expected["trigger"],
                "source_text": expected["source_text"],
                "expected_disposition": expected["expected_disposition"],
                "expected_review_outcome": expected["review_outcome"],
                "review_rationale": expected["review_rationale"],
                "preview_id": preview_id,
                "event_semantic_id": event["id"],
                "plan_id": result.plan.id,
                "retry_plan_id": results_by_preview[preview_id][1].plan.id,
                "retry_publication_disposition": results_by_preview[preview_id][
                    1
                ].publication_disposition,
                "exact_data_in": trace.input,
                "admission_output": decision.model_dump(mode="json"),
                "proposed_json": [item.model_dump(mode="json") for item in changes],
                "review_packet": review_packet_to_json(packet),
                "event_proposed_change_id": event_change.id,
            }
        )

    _execute_gold_reviews(selected, ledger_path)
    for item in selected:
        with sqlite_ledger_transaction(ledger_path) as repository:
            proposed = repository.get_proposed_change(item["event_proposed_change_id"])
            if proposed is None:
                raise ValueError("HP-7 reviewed ProposedChange disappeared.")
            record = cast(dict[str, Any], proposed.proposed_json["record"])
            accepted_event = repository.get_event(cast(str, record["id"]))
            proposal_statuses = {
                cast(str, change["id"]): _required_proposal_status(
                    repository,
                    cast(str, change["id"]),
                )
                for change in cast(list[dict[str, Any]], item["proposed_json"])
            }
        actual = proposed.review_status.value
        item["actual_review_outcome"] = actual
        item["accepted_event_id"] = accepted_event.id if accepted_event is not None else None
        item["proposal_review_statuses"] = proposal_statuses
        if actual != item["expected_review_outcome"]:
            findings.append(
                {
                    "case_id": item["case_id"],
                    "code": "review_outcome_mismatch",
                    "owner": "implementation",
                    "expected": item["expected_review_outcome"],
                    "actual": actual,
                    "trigger": item["trigger"],
                }
            )
        if actual == "rejected" and accepted_event is not None:
            findings.append(
                {
                    "case_id": item["case_id"],
                    "code": "rejected_event_entered_accepted_state",
                    "owner": "implementation",
                    "trigger": item["trigger"],
                }
            )
        if actual == "rejected":
            non_rejected_semantics = [
                cast(str, change["id"])
                for change in cast(list[dict[str, Any]], item["proposed_json"])
                if change["proposed_json"]["record_type"] in {"Event", "Assertion"}
                and proposal_statuses[cast(str, change["id"])] != "rejected"
            ]
            if non_rejected_semantics:
                findings.append(
                    {
                        "case_id": item["case_id"],
                        "code": "rejected_event_left_semantic_proposals_pending",
                        "owner": "implementation",
                        "proposed_change_ids": non_rejected_semantics,
                        "trigger": item["trigger"],
                    }
                )
    return {
        "schema_version": "hp7_proposal_admission_evaluation_v1",
        "cases": selected,
        "findings": findings,
        "summary": {
            "passed": not findings and len(selected) == 8,
            "case_count": len(selected),
            "approved_count": sum(item["actual_review_outcome"] == "approved" for item in selected),
            "rejected_count": sum(item["actual_review_outcome"] == "rejected" for item in selected),
            "finding_count": len(findings),
        },
    }


def _execute_gold_reviews(cases: list[dict[str, Any]], ledger_path: Path) -> None:
    approved_change_ids = {
        change["id"]
        for item in cases
        if item["expected_review_outcome"] == "approved"
        for change in item["proposed_json"]
    }
    rejected_semantic_change_ids = {
        cast(str, change["id"])
        for item in cases
        if item["expected_review_outcome"] == "rejected"
        for change in cast(list[dict[str, Any]], item["proposed_json"])
        if change["proposed_json"]["record_type"] in {"Event", "Assertion"}
    }
    with sqlite_ledger_transaction(ledger_path) as repository:
        approved = [
            item
            for change_id in sorted(approved_change_ids)
            if (item := repository.get_proposed_change(change_id)) is not None
        ]
        for record_type in ("Organization", "Actor", "Event", "Assertion"):
            for proposed in approved:
                if (
                    proposed.review_status is not ReviewStatus.PENDING
                    or proposed.proposed_json.get("record_type") != record_type
                ):
                    continue
                canonical_predicate: str | None = None
                if record_type == "Assertion":
                    assertion = ProposedAssertion.model_validate_json(
                        _canonical_json(proposed.proposed_json["record"])
                    )
                    canonical_predicate = assertion.relation_label
                approve_proposed_change(
                    ReviewProposedChangeInput(
                        proposed.id,
                        "hp7-gold-reviewer",
                        _REVIEWED_AT,
                        canonical_predicate=canonical_predicate,
                    ),
                    repository,
                )
        for change_id in sorted(rejected_semantic_change_ids):
            proposed = repository.get_proposed_change(change_id)
            if proposed is not None and proposed.review_status is ReviewStatus.PENDING:
                reject_proposed_change(
                    ReviewProposedChangeInput(
                        proposed.id,
                        "hp7-gold-reviewer",
                        _REVIEWED_AT,
                        reason="The reviewed source reports uncertainty, not a recommendation.",
                    ),
                    repository,
                )


def _required_proposal_status(
    repository: SQLiteLedgerRepository,
    proposed_change_id: str,
) -> str:
    proposed = repository.get_proposed_change(proposed_change_id)
    if proposed is None:
        raise ValueError("HP-7 reviewed proposal disappeared.")
    return proposed.review_status.value


def _select_event(
    preview: dict[str, Any],
    expected: dict[str, Any],
    repository: SQLiteLedgerRepository,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for event in cast(list[dict[str, Any]], preview["semantic_events"]):
        if event["trigger_text"] != expected["trigger"]:
            continue
        target = repository.get_evidence_target(event["support_evidence_target_id"])
        if target is not None and target.exact_text == expected["source_text"]:
            matches.append(event)
    if len(matches) != 1:
        raise ValueError(
            f"HP-7 Gold locator did not select one event: {expected['case_id']} / "
            f"{expected['trigger']}"
        )
    return matches[0]


def _copy_sqlite(source: Path, target: Path) -> None:
    with sqlite3.connect(source) as source_connection, sqlite3.connect(target) as target_connection:
        source_connection.backup(target_connection)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, Any], value)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
