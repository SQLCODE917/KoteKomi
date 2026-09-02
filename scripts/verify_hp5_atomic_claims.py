#!/usr/bin/env python3
"""Replay reviewed HP-4 evidence through deterministic HP-5 atomization."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import canonical_record_json


def main() -> int:
    args = _parser().parse_args()
    hp4_report = _object(json.loads(args.hp4_report.read_text(encoding="utf-8")))
    if hp4_report.get("schema_version") != "hp4_event_frame_evaluation_v1":
        raise ValueError("HP-5 evaluation requires an HP-4 evaluation report.")
    initialization = SQLiteLedgerInitializer(args.ledger_path).initialize()
    args.archive_path.mkdir(parents=True, exist_ok=True)
    before = _intelligence_state_snapshot(args.ledger_path)
    report: dict[str, object] = {
        "schema_version": "hp5_atomic_claim_evaluation_v1",
        "hp4_report_path": str(args.hp4_report),
        "hp4_report_sha256": hashlib.sha256(args.hp4_report.read_bytes()).hexdigest(),
        "representation_id": hp4_report.get("representation_id"),
        "ledger_migrations_applied": list(initialization.applied_migrations),
        "intelligence_state_before": before,
        "cases": [],
    }
    output_cases = cast(list[object], report["cases"])
    for raw_case in _list(hp4_report, "cases"):
        hp4_case = _object(raw_case)
        case_result = _evaluate_case(args, hp4_case)
        output_cases.append(case_result)
        _write_report(args.output, report)
        print(
            json.dumps(
                {
                    "case_id": case_result["case_id"],
                    "status": case_result["evaluation_status"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    after = _intelligence_state_snapshot(args.ledger_path)
    report["intelligence_state_after"] = after
    report["intelligence_state_unchanged"] = after == before
    report["summary"] = _summary(output_cases)
    _write_report(args.output, report)
    if after != before:
        raise RuntimeError("HP-5 evaluation changed accepted or proposed intelligence state.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hp4-report", type=Path, required=True)
    parser.add_argument("--ledger-path", type=Path, required=True)
    parser.add_argument("--archive-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _evaluate_case(args: argparse.Namespace, hp4_case: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "case_id": _string(hp4_case, "case_id"),
        "expected_semantic_work": _string(hp4_case, "expected_semantic_work"),
        "paragraph_node_id": _string(hp4_case, "paragraph_node_id"),
        "paragraph_text": _string(hp4_case, "paragraph_text"),
        "paragraph_text_sha256": _string(hp4_case, "paragraph_text_sha256"),
    }
    raw_hp4 = hp4_case.get("hp4")
    if not isinstance(raw_hp4, dict):
        result.update(
            {
                "evaluation_status": "upstream_unavailable",
                "owning_stage": hp4_case.get("failed_stage", "pre_hp4"),
                "diagnostics": ["hp4_preview_unavailable"],
            }
        )
        return result
    hp4 = cast(dict[str, object], raw_hp4)
    if not isinstance(hp4.get("preview_id"), str):
        result.update(
            {
                "evaluation_status": "upstream_unavailable",
                "owning_stage": hp4_case.get("failed_stage", "pre_hp4"),
                "diagnostics": ["hp4_preview_unavailable"],
            }
        )
        return result
    hp4_preview = _object(hp4_case["preview"])
    parent_preview_id = _string(hp4, "preview_id")
    first = _run_command(args, parent_preview_id)
    if "preview_id" not in first:
        result.update(
            {
                "evaluation_status": "hp5_failed",
                "owning_stage": "hp5_execution",
                "hp4_preview": hp4_preview,
                "hp5_first": first,
            }
        )
        return result
    preview_path = args.archive_path / _string(first, "archive_path")
    first_bytes = preview_path.read_bytes()
    preview = _object(json.loads(first_bytes))
    evidence = _evidence_records(args.ledger_path, preview)
    second = _run_command(args, parent_preview_id)
    second_path = args.archive_path / _string(second, "archive_path")
    second_bytes = second_path.read_bytes()
    replay_equivalent = (
        _string(first, "preview_id") == _string(second, "preview_id")
        and first_bytes == second_bytes
        and _public_counts(first) == _public_counts(second)
    )
    findings = [
        finding
        for raw_report in _list(preview, "ontology_reports")
        for finding in _list(_object(raw_report), "findings")
    ]
    ownership = [_finding_ownership(_object(item)) for item in findings]
    result.update(
        {
            "evaluation_status": "evaluated",
            "owning_stage": "none" if not ownership else "classified_per_finding",
            "hp4_preview": hp4_preview,
            "hp5_first": first,
            "hp5_second": second,
            "hp5_preview": preview,
            "evidence_records": evidence,
            "finding_ownership": ownership,
            "replay_equivalent": replay_equivalent,
            "preview_sha256": hashlib.sha256(first_bytes).hexdigest(),
        }
    )
    return result


def _run_command(args: argparse.Namespace, preview_id: str) -> dict[str, object]:
    command = (
        sys.executable,
        "-m",
        "kotekomi_pipelines.cli",
        "extraction",
        "build-atomic-claims",
        "--preview-id",
        preview_id,
        "--ledger-path",
        str(args.ledger_path),
        "--archive-path",
        str(args.archive_path),
    )
    started_at = time.perf_counter()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    payload: dict[str, object] = {
        "argv": list(command[2:]),
        "elapsed_milliseconds": round((time.perf_counter() - started_at) * 1000),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    for line in reversed(completed.stdout.splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payload.update(cast(dict[str, object], parsed))
            break
    return payload


def _evidence_records(ledger_path: Path, preview: dict[str, object]) -> list[dict[str, object]]:
    targets = _strings(preview, "evidence_target_ids")
    attempt_ids = _strings(preview, "evidence_validation_attempt_ids")
    records: list[dict[str, object]] = []
    with sqlite_ledger_transaction(ledger_path) as repository:
        attempts = {
            attempt.evidence_target_id: attempt
            for attempt_id in attempt_ids
            if (attempt := repository.get_evidence_validation_attempt(attempt_id)) is not None
        }
        if len(attempts) != len(attempt_ids):
            raise ValueError("HP-5 evaluation cannot load all validation attempts.")
        for target_id in targets:
            target = repository.get_evidence_target(target_id)
            attempt = attempts.get(target_id)
            if target is None or attempt is None:
                raise ValueError("HP-5 evaluation cannot load referenced evidence records.")
            records.append(
                {
                    "evidence_target": target.model_dump(mode="json"),
                    "validation_attempt": attempt.model_dump(mode="json"),
                }
            )
    return records


def _finding_ownership(finding: dict[str, object]) -> dict[str, object]:
    code = _string(finding, "code")
    if code in {"unmapped_event_type", "unmapped_argument_role"}:
        owner = "hp4_open_label_proposal"
    elif code == "attribution_support_missing":
        owner = "hp4_candidate_attribution_contract"
    else:
        owner = "hp5_ontology_validation"
    return {"finding": finding, "owning_stage": owner}


def _public_counts(result: dict[str, object]) -> tuple[object, ...]:
    return tuple(
        result.get(name)
        for name in (
            "status",
            "claim_count",
            "ontology_finding_count",
            "evidence_target_count",
            "report_count",
            "subject_count",
        )
    )


def _intelligence_state_snapshot(ledger_path: Path) -> dict[str, object]:
    with sqlite_ledger_transaction(ledger_path) as repository:
        records = (
            *repository.list_events(),
            *repository.list_assertions(),
            *repository.list_relationships(),
            *repository.list_proposed_changes(),
        )
    identities = [
        {
            "id": record.id,
            "record_type": type(record).__name__,
            "sha256": hashlib.sha256(canonical_record_json(record).encode()).hexdigest(),
        }
        for record in records
    ]
    canonical = json.dumps(identities, separators=(",", ":"), sort_keys=True).encode()
    return {
        "record_count": len(identities),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _summary(raw_cases: list[object]) -> dict[str, object]:
    cases = [_object(item) for item in raw_cases]
    evaluated = [item for item in cases if item["evaluation_status"] == "evaluated"]
    previews = [_object(item["hp5_preview"]) for item in evaluated]
    reports = [item for preview in previews for item in _list(preview, "ontology_reports")]
    findings = [item for report in reports for item in _list(_object(report), "findings")]
    finding_codes: dict[str, int] = {}
    for raw_finding in findings:
        code = _string(_object(raw_finding), "code")
        finding_codes[code] = finding_codes.get(code, 0) + 1
    return {
        "case_count": len(cases),
        "evaluated_case_count": len(evaluated),
        "upstream_unavailable_case_count": len(cases) - len(evaluated),
        "replay_equivalent_case_count": sum(
            item.get("replay_equivalent") is True for item in evaluated
        ),
        "event_subject_count": sum(len(_list(item, "event_subjects")) for item in previews),
        "atomic_claim_count": sum(len(_list(item, "atomic_claims")) for item in previews),
        "ontology_report_count": len(reports),
        "ontology_finding_count": len(findings),
        "ontology_finding_codes": finding_codes,
        "evidence_target_count": sum(len(_list(item, "evidence_target_ids")) for item in previews),
    }


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object.")
    return cast(dict[str, object], value)


def _list(value: dict[str, object], key: str) -> list[object]:
    result = value[key]
    if not isinstance(result, list):
        raise TypeError(f"Expected {key} to be a JSON list.")
    return cast(list[object], result)


def _string(value: dict[str, object], key: str) -> str:
    result = value[key]
    if not isinstance(result, str):
        raise TypeError(f"Expected {key} to be a string.")
    return result


def _strings(value: dict[str, object], key: str) -> list[str]:
    result = _list(value, key)
    if not all(isinstance(item, str) for item in result):
        raise TypeError(f"Expected {key} to contain only strings.")
    return cast(list[str], result)


if __name__ == "__main__":
    raise SystemExit(main())
