#!/usr/bin/env python3
"""Run the model-free R17 semantic selection contract evaluation.

R17 pins the four selection decisions and the five independent acceptance
signals into one versioned, digest-bound contract.  This runner loads the frozen
contract, reference policy records, and observed answers, renders each selection
task from the eligibility rule and the frozen Event frame and Candidate pool, and
seals one report.  It invokes no model and writes no canonical state and no
ProposedChanges.

Phases:

* ``evaluate`` -- load the frozen contract and records, evaluate every observed
  answer once through the R16 strict parser, and seal the report.
* ``show`` -- re-open a sealed report and print its fingerprint and counts.

All inputs are explicit repository-relative paths; no environment variables are
assumed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kotekomi_application import (
    EvaluationItem,
    ReferencePolicyRecord,
    SemanticSelectionReport,
    build_semantic_selection_report,
    evaluate_selection,
    frozen_semantic_selection_contract,
    load_observed_answers,
    load_reference_policy_records,
    semantic_selection_report_fingerprint,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPOSITORY_ROOT / "data/r17-semantic-selection-contract"
RUN_ROOT = REPOSITORY_ROOT / "data/r17-semantic-selection-contract-runs/run-001"
RUN_SCHEMA_VERSION = "semantic_selection_contract_run_v1"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _evaluate() -> tuple[tuple[ReferencePolicyRecord, ...], SemanticSelectionReport]:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    records = load_reference_policy_records(contract=contract, directory=DATA_DIR)
    answers = load_observed_answers(contract=contract, directory=DATA_DIR, records=records)
    by_event = {record.event_id: record for record in records}
    evaluations = tuple(
        EvaluationItem(
            observation_id=answer.observation_id,
            event_id=answer.event_id,
            route=answer.route,
            signals=evaluate_selection(
                contract=contract,
                policy_record=by_event[answer.event_id],
                observed_answer=answer,
            ),
        )
        for answer in answers
    )
    report = build_semantic_selection_report(
        contract=contract,
        policy_records=records,
        observed_answers=answers,
        evaluations=evaluations,
    )
    return records, report


def _run_summary(
    records: tuple[ReferencePolicyRecord, ...], report: SemanticSelectionReport
) -> dict[str, object]:
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "contract_version": report.contract_version,
        "policy_record_count": report.policy_record_count,
        "observed_answer_count": report.observed_answer_count,
        "evaluation_count": report.evaluation_count,
        "model_execution_count": report.model_execution_count,
        "canonical_write_count": report.canonical_write_count,
        "proposed_change_count": report.proposed_change_count,
        "role_coverage": sorted(
            {role.role for record in records for role in record.expected_source_ranges}
        ),
        "result_fingerprint": report.result_fingerprint,
    }


def _evaluate_command() -> int:
    records, report = _evaluate()
    _write_json(RUN_ROOT / "report.json", report.model_dump(mode="json"))
    _write_json(RUN_ROOT / "run.json", _run_summary(records, report))
    print(json.dumps(_run_summary(records, report), sort_keys=True))
    return 0


def _show_command() -> int:
    sealed = SemanticSelectionReport.model_validate_json((RUN_ROOT / "report.json").read_text())
    expected = sealed.result_fingerprint
    if expected != semantic_selection_report_fingerprint(sealed):
        raise ValueError("Sealed report fingerprint drifted from its contents.")
    print(
        json.dumps(
            {
                "result_fingerprint": expected,
                "evaluation_count": sealed.evaluation_count,
                "model_execution_count": sealed.model_execution_count,
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the R17 semantic selection contract.")
    parser.add_argument(
        "phase",
        choices=["evaluate", "show"],
        help="evaluate seals the report; show re-opens and re-verifies it",
    )
    args = parser.parse_args()
    if args.phase == "evaluate":
        return _evaluate_command()
    return _show_command()


if __name__ == "__main__":
    raise SystemExit(main())
