#!/usr/bin/env python3
"""Validate and run the bounded HP-6 Qwen evaluation with full stage evidence."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application import hybrid_event_semantics_preview_from_bytes
from kotekomi_pipelines.cli import main as kotekomi_main


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    evaluate = subparsers.add_parser("evaluate")
    for command in (validate, evaluate):
        command.add_argument("--hp5-report", type=Path, required=True)
        command.add_argument("--gold", type=Path, required=True)
    evaluate.add_argument("--config", type=Path, required=True)
    evaluate.add_argument("--ledger-path", type=Path, required=True)
    evaluate.add_argument("--archive-path", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()
    hp5 = _read_json(args.hp5_report)
    gold = _read_json(args.gold)
    validation = _validate_inputs(hp5, gold)
    if args.command == "validate":
        print(json.dumps(validation, sort_keys=True))
        return 0
    if args.repetitions != 2:
        raise ValueError("HP-6 acceptance requires exactly two repetitions.")
    report = _evaluate(
        hp5=hp5,
        hp5_path=args.hp5_report,
        gold=gold,
        gold_path=args.gold,
        config_path=args.config,
        ledger_path=args.ledger_path,
        archive_path=args.archive_path,
        repetitions=args.repetitions,
        validation=validation,
    )
    args.output.write_text(_canonical_json(report) + "\n")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if cast(dict[str, object], report["summary"])["passed"] is True else 1


def _validate_inputs(hp5: dict[str, Any], gold: dict[str, Any]) -> dict[str, object]:
    if gold.get("schema_version") != "hp6_event_semantics_gold_v1":
        raise ValueError("HP-6 Gold schema is unknown.")
    cases = cast(list[dict[str, Any]], hp5.get("cases"))
    evaluated = [item for item in cases if item.get("evaluation_status") == "evaluated"]
    evidence_records = [
        record
        for item in evaluated
        for record in cast(list[dict[str, Any]], item.get("evidence_records", []))
    ]
    evidence_ids = {
        cast(dict[str, Any], item["evidence_target"])["id"] for item in evidence_records
    }
    expected_count = cast(dict[str, Any], gold["scope"])["parent_evidence_target_count"]
    if (
        cast(dict[str, Any], gold["scope"]).get("target_boundary_comparison_policy")
        != "exact_or_one_trailing_clause_delimiter_v1"
    ):
        raise ValueError("HP-6 Gold target-boundary comparison policy is unknown.")
    if len(evidence_ids) != expected_count:
        raise ValueError(
            f"HP-6 expected {expected_count} retained EvidenceTargets; found {len(evidence_ids)}."
        )
    case_by_id = {item["case_id"]: item for item in evaluated}
    for expected in cast(list[dict[str, Any]], gold["events"]):
        case = case_by_id.get(expected["case_id"])
        if case is None:
            raise ValueError(f"HP-6 Gold case is absent: {expected['case_id']}")
        source_text = expected["source_text"]
        matching = [
            record
            for record in cast(list[dict[str, Any]], case["evidence_records"])
            if cast(dict[str, Any], record["evidence_target"])["exact_text"] == source_text
        ]
        if len(matching) != 1:
            raise ValueError("HP-6 Gold source does not bind one exact parent EvidenceTarget.")
        if cast(str, source_text).count(cast(str, expected["trigger"])) != 1:
            raise ValueError("HP-6 Gold trigger is not unique in its exact source.")
        for argument in cast(list[dict[str, str]], expected["arguments"]):
            if cast(str, source_text).count(argument["target_text"]) != 1:
                raise ValueError("HP-6 Gold argument target is not unique in its exact source.")
    return {
        "evaluated_case_count": len(evaluated),
        "event_subject_count": sum(
            len(cast(dict[str, Any], item["hp5_preview"])["event_subjects"]) for item in evaluated
        ),
        "parent_evidence_target_count": len(evidence_ids),
        "detailed_event_count": len(cast(list[object], gold["events"])),
    }


def _evaluate(
    *,
    hp5: dict[str, Any],
    hp5_path: Path,
    gold: dict[str, Any],
    gold_path: Path,
    config_path: Path,
    ledger_path: Path,
    archive_path: Path,
    repetitions: int,
    validation: dict[str, object],
) -> dict[str, object]:
    cases = [
        item
        for item in cast(list[dict[str, Any]], hp5["cases"])
        if item.get("evaluation_status") == "evaluated"
    ]
    runs: list[dict[str, object]] = []
    for repetition in range(1, repetitions + 1):
        for case in cases:
            parent = cast(dict[str, Any], case["hp5_preview"])
            stdout = io.StringIO()
            stderr = io.StringIO()
            argv = [
                "--config",
                str(config_path),
                "extraction",
                "build-event-semantics",
                "--preview-id",
                parent["id"],
                "--ledger-path",
                str(ledger_path),
                "--archive-path",
                str(archive_path),
                "--format",
                "json",
            ]
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = kotekomi_main(argv)
            output_lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
            if not output_lines:
                raise ValueError("HP-6 command produced no JSON result.")
            command_result = cast(dict[str, Any], json.loads(output_lines[-1]))
            preview_path = archive_path / cast(str, command_result["archive_path"])
            preview = hybrid_event_semantics_preview_from_bytes(preview_path.read_bytes())
            model_outputs = {
                model_run_id: (archive_path / "model-runs" / f"{model_run_id}.json").read_text()
                for model_run_id in preview.model_run_ids
            }
            runs.append(
                {
                    "case_id": case["case_id"],
                    "repetition": repetition,
                    "argv": argv,
                    "exit_code": exit_code,
                    "stdout": stdout.getvalue(),
                    "stderr": stderr.getvalue(),
                    "command_result": command_result,
                    "preview": preview.model_dump(mode="json"),
                    "model_outputs": model_outputs,
                    "semantic_signature": _semantic_signature(preview.model_dump(mode="json")),
                }
            )
    expected_support = cast(dict[str, Any], gold["scope"])["expected_semantic_statement_support"]
    findings = _compare_gold(
        cases,
        runs,
        cast(list[dict[str, Any]], gold["events"]),
        cast(str, expected_support),
    )
    stability = _compare_repetitions(runs)
    passed = not findings and not stability
    return {
        "schema_version": "hp6_event_semantics_evaluation_v1",
        "hp5_report_path": str(hp5_path),
        "hp5_report_sha256": hashlib.sha256(hp5_path.read_bytes()).hexdigest(),
        "gold_path": str(gold_path),
        "gold_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        "validation": validation,
        "runs": runs,
        "findings": findings,
        "stability_findings": stability,
        "summary": {
            "passed": passed,
            "run_count": len(runs),
            "finding_count": len(findings),
            "stability_finding_count": len(stability),
        },
    }


def _compare_gold(
    cases: list[dict[str, Any]],
    runs: list[dict[str, object]],
    expected_events: list[dict[str, Any]],
    expected_support: str,
) -> list[dict[str, object]]:
    expected_by_case: dict[str, list[dict[str, Any]]] = {}
    for expected in expected_events:
        expected_by_case.setdefault(expected["case_id"], []).append(expected)
    findings: list[dict[str, object]] = []
    case_by_id = {item["case_id"]: item for item in cases}
    for run in runs:
        case_id = cast(str, run["case_id"])
        preview = cast(dict[str, Any], run["preview"])
        case = case_by_id[case_id]
        event_by_subject = {
            item["event_subject_id"]: item
            for item in cast(list[dict[str, Any]], preview["semantic_events"])
        }
        target_by_id = {item["id"]: item for item in cast(list[dict[str, Any]], preview["targets"])}
        assignment_by_event = {
            event["id"]: [
                item
                for item in cast(list[dict[str, Any]], preview["assignments"])
                if item["event_subject_id"] == event["event_subject_id"]
            ]
            for event in cast(list[dict[str, Any]], preview["semantic_events"])
        }
        qualifier_by_event = {
            event["id"]: [
                item
                for item in cast(list[dict[str, Any]], preview["qualifiers"])
                if item["event_subject_id"] == event["event_subject_id"]
            ]
            for event in cast(list[dict[str, Any]], preview["semantic_events"])
        }
        statements_by_event = {
            event["id"]: [
                item
                for item in cast(list[dict[str, Any]], preview["statements"])
                if item["event_semantic_id"] == event["id"]
            ]
            for event in cast(list[dict[str, Any]], preview["semantic_events"])
        }
        judgment_by_statement = {
            item["statement_id"]: item for item in cast(list[dict[str, Any]], preview["judgments"])
        }
        for expected in expected_by_case.get(case_id, []):
            subject_id = _subject_for_gold(case, expected)
            actual = event_by_subject.get(subject_id)
            if actual is None:
                findings.append(_finding(run, expected, "expected_event_missing", None))
                continue
            actual_arguments = sorted(
                (
                    item["frame_role_id"],
                    target_by_id[item["target_id"]]["kind"],
                    target_by_id[item["target_id"]]["text"],
                )
                for item in assignment_by_event[actual["id"]]
            )
            expected_arguments = sorted(
                (item["frame_role_id"], item["target_kind"], item["target_text"])
                for item in expected["arguments"]
            )
            actual_qualifiers = sorted(
                (item["kind"], item["text"]) for item in qualifier_by_event[actual["id"]]
            )
            expected_qualifiers = sorted(
                (item["kind"], item["text"]) for item in expected["qualifiers"]
            )
            attribution_text = None
            if actual["attribution_target_id"] is not None:
                attribution_text = target_by_id[actual["attribution_target_id"]]["text"]
            actual_signature = {
                "frame_id": actual["frame_id"],
                "arguments": actual_arguments,
                "qualifiers": actual_qualifiers,
                "attribution_kind": actual["attribution_kind"],
                "attribution_target_text": attribution_text,
            }
            expected_signature = {
                "frame_id": expected["frame_id"],
                "arguments": expected_arguments,
                "qualifiers": expected_qualifiers,
                "attribution_kind": expected["attribution_kind"],
                "attribution_target_text": expected.get("attribution_target_text"),
            }
            if not _semantic_signatures_match(actual_signature, expected_signature):
                findings.append(
                    _finding(
                        run, expected_signature, "semantic_signature_mismatch", actual_signature
                    )
                )
            support_results = [
                {
                    "kind": statement["kind"],
                    "statement": statement["text"],
                    "outcome": (
                        judgment_by_statement[statement["id"]]["outcome"]
                        if statement["id"] in judgment_by_statement
                        else "missing"
                    ),
                }
                for statement in statements_by_event[actual["id"]]
            ]
            if any(item["outcome"] != expected_support for item in support_results):
                findings.append(
                    _finding(
                        run,
                        {"every_semantic_statement": expected_support},
                        "semantic_support_mismatch",
                        support_results,
                    )
                )
    return findings


def _semantic_signatures_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    if any(
        actual[field] != expected[field]
        for field in (
            "frame_id",
            "qualifiers",
            "attribution_kind",
            "attribution_target_text",
        )
    ):
        return False
    actual_arguments = {
        (role, kind): target
        for role, kind, target in cast(list[tuple[str, str, str]], actual["arguments"])
    }
    expected_arguments = {
        (role, kind): target
        for role, kind, target in cast(list[tuple[str, str, str]], expected["arguments"])
    }
    if actual_arguments.keys() != expected_arguments.keys():
        return False
    return all(
        _target_text_matches(actual_arguments[key], expected_target)
        for key, expected_target in expected_arguments.items()
    )


def _target_text_matches(actual: str, expected: str) -> bool:
    return actual == expected or actual in {
        f"{expected},",
        f"{expected};",
        f"{expected}.",
    }


def _subject_for_gold(case: dict[str, Any], expected: dict[str, Any]) -> str:
    hp4 = cast(dict[str, Any], case["hp4_preview"])
    hp5 = cast(dict[str, Any], case["hp5_preview"])
    targets = {
        cast(dict[str, Any], record["evidence_target"])["id"]: cast(
            dict[str, Any], record["evidence_target"]
        )["exact_text"]
        for record in cast(list[dict[str, Any]], case["evidence_records"])
    }
    claim_target_by_frame = {
        claim["frame_id"]: claim["evidence_target_id"]
        for claim in cast(list[dict[str, Any]], hp5["atomic_claims"])
        if claim["predicate"] == "has_event_type"
    }
    triggers = {item["id"]: item for item in cast(list[dict[str, Any]], hp4["triggers"])}
    matches = [
        subject["id"]
        for subject in cast(list[dict[str, Any]], hp5["event_subjects"])
        if triggers[subject["trigger_id"]]["text"] == expected["trigger"]
        and targets[claim_target_by_frame[subject["frame_id"]]] == expected["source_text"]
    ]
    if len(matches) != 1:
        raise ValueError("HP-6 Gold event does not bind exactly one parent event subject.")
    return matches[0]


def _semantic_signature(preview: dict[str, Any]) -> list[dict[str, object]]:
    target_by_id = {item["id"]: item for item in cast(list[dict[str, Any]], preview["targets"])}
    assignments = cast(list[dict[str, Any]], preview["assignments"])
    qualifiers = cast(list[dict[str, Any]], preview["qualifiers"])
    gaps = cast(list[dict[str, Any]], preview["gaps"])
    judgments = cast(list[dict[str, Any]], preview["judgments"])
    statements = {item["id"]: item for item in cast(list[dict[str, Any]], preview["statements"])}
    result: list[dict[str, object]] = []
    for event in cast(list[dict[str, Any]], preview["semantic_events"]):
        result.append(
            {
                "event_subject_id": event["event_subject_id"],
                "frame_id": event["frame_id"],
                "arguments": sorted(
                    (
                        item["frame_role_id"],
                        item["upper_role"],
                        target_by_id[item["target_id"]]["kind"],
                        target_by_id[item["target_id"]]["text"],
                    )
                    for item in assignments
                    if item["event_subject_id"] == event["event_subject_id"]
                ),
                "qualifiers": sorted(
                    (item["kind"], item["text"])
                    for item in qualifiers
                    if item["event_subject_id"] == event["event_subject_id"]
                ),
                "attribution_kind": event["attribution_kind"],
                "attribution_target_text": (
                    target_by_id[event["attribution_target_id"]]["text"]
                    if event["attribution_target_id"] is not None
                    else None
                ),
                "support": sorted(
                    (
                        statements[item["statement_id"]]["kind"],
                        statements[item["statement_id"]]["text"],
                        item["outcome"],
                    )
                    for item in judgments
                    if statements[item["statement_id"]]["event_semantic_id"] == event["id"]
                ),
            }
        )
    result.extend(
        {"event_subject_id": item["event_subject_id"], "gap": item["code"]} for item in gaps
    )
    return sorted(result, key=_canonical_json)


def _compare_repetitions(runs: list[dict[str, object]]) -> list[dict[str, object]]:
    by_case: dict[str, list[dict[str, object]]] = {}
    for run in runs:
        by_case.setdefault(cast(str, run["case_id"]), []).append(run)
    findings: list[dict[str, object]] = []
    for case_id, case_runs in by_case.items():
        signatures = [item["semantic_signature"] for item in case_runs]
        if signatures[1:] != signatures[:-1]:
            findings.append(
                {
                    "case_id": case_id,
                    "code": "semantic_output_unstable",
                    "signatures": signatures,
                }
            )
    return findings


def _finding(
    run: dict[str, object],
    expected: object,
    code: str,
    actual: object,
) -> dict[str, object]:
    return {
        "case_id": run["case_id"],
        "repetition": run["repetition"],
        "code": code,
        "expected": expected,
        "actual": actual,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


if __name__ == "__main__":
    raise SystemExit(main())
