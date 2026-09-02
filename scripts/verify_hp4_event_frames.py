#!/usr/bin/env python3
"""Run the reviewed HP-4 development cases through the public extraction commands."""

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

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPOSITORY_ROOT / "docs" / "hp4-event-frame-development-v1.json"


def main() -> int:
    args = _parser().parse_args()
    catalog = _object(json.loads(args.catalog.read_text(encoding="utf-8")))
    _verify_fixture(catalog)
    cases = [_object(item) for item in _list(catalog, "cases")]
    if args.case_id:
        requested = set(args.case_id)
        cases = [item for item in cases if _string(item, "case_id") in requested]
        missing = requested - {_string(item, "case_id") for item in cases}
        if missing:
            raise ValueError(f"Unknown HP-4 case IDs: {', '.join(sorted(missing))}")
    initialization = SQLiteLedgerInitializer(args.ledger_path).initialize()
    paragraph_by_case = _resolve_paragraphs(
        args.ledger_path,
        args.representation_id,
        cases,
    )
    args.archive_path.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "schema_version": "hp4_event_frame_evaluation_v1",
        "catalog_path": str(args.catalog),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "representation_id": args.representation_id,
        "ledger_migrations_applied": list(initialization.applied_migrations),
        "accepted_state_before": _accepted_state_snapshot(args.ledger_path),
        "cases": [],
    }
    output_cases = cast(list[object], report["cases"])
    for case in cases:
        case_id = _string(case, "case_id")
        node_id, paragraph_text = paragraph_by_case[case_id]
        hp1 = _run_command(
            args,
            (
                "extraction",
                "preview-mentions",
                "--representation-id",
                args.representation_id,
                "--node-id",
                node_id,
            ),
        )
        if "preview_id" not in hp1 or hp1.get("status") == "blocked":
            output_cases.append(
                _failed_case(
                    case,
                    node_id,
                    paragraph_text,
                    "hp1",
                    {"hp1": hp1},
                    args.archive_path,
                )
            )
            _write_report(args.output, report)
            continue
        hp2 = _run_command(
            args,
            ("extraction", "resolve-references", "--preview-id", _string(hp1, "preview_id")),
        )
        if "preview_id" not in hp2 or hp2.get("status") == "blocked":
            output_cases.append(
                _failed_case(
                    case,
                    node_id,
                    paragraph_text,
                    "hp2",
                    {"hp1": hp1, "hp2": hp2},
                    args.archive_path,
                )
            )
            _write_report(args.output, report)
            continue
        hp3 = _run_command(
            args,
            ("extraction", "ground-entities", "--preview-id", _string(hp2, "preview_id")),
        )
        if "preview_id" not in hp3:
            output_cases.append(
                _failed_case(
                    case,
                    node_id,
                    paragraph_text,
                    "hp3",
                    {"hp1": hp1, "hp2": hp2, "hp3": hp3},
                    args.archive_path,
                )
            )
            _write_report(args.output, report)
            continue
        hp4 = _run_command(
            args,
            (
                "extraction",
                "draft-event-frames",
                "--preview-id",
                _string(hp3, "preview_id"),
            ),
        )
        case_result: dict[str, object] = {
            "case_id": case_id,
            "expected_semantic_work": _string(case, "expected_semantic_work"),
            "paragraph_node_id": node_id,
            "paragraph_text": paragraph_text,
            "paragraph_text_sha256": hashlib.sha256(paragraph_text.encode()).hexdigest(),
            "hp1": hp1,
            "hp2": hp2,
            "hp3": hp3,
            "hp4": hp4,
        }
        if "preview_id" in hp4:
            preview_path = (
                args.archive_path
                / "extraction"
                / "event-frame-previews"
                / f"{_string(hp4, 'preview_id')}.json"
            )
            preview = _object(json.loads(preview_path.read_text(encoding="utf-8")))
            case_result["preview"] = preview
            case_result["raw_model_outputs"] = _raw_outputs(args.archive_path, preview)
            case_result["stage_summary"] = _stage_summary(preview)
        output_cases.append(case_result)
        _write_report(args.output, report)
        print(json.dumps({"case_id": case_id, "hp4": hp4}, sort_keys=True), flush=True)
    accepted_state_after = _accepted_state_snapshot(args.ledger_path)
    report["accepted_state_after"] = accepted_state_after
    report["accepted_state_unchanged"] = accepted_state_after == report["accepted_state_before"]
    report["summary"] = _summary(output_cases)
    _write_report(args.output, report)
    if not report["accepted_state_unchanged"]:
        raise RuntimeError("HP-4 evaluation changed accepted canonical Ledger state.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--representation-id", required=True)
    parser.add_argument("--ledger-path", type=Path, required=True)
    parser.add_argument("--archive-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    return parser


def _verify_fixture(catalog: dict[str, object]) -> None:
    fixture = REPOSITORY_ROOT / _string(catalog, "fixture_path")
    if not fixture.is_file():
        raise FileNotFoundError(f"HP-4 fixture is missing: {fixture}")
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if digest != _string(catalog, "fixture_sha256"):
        raise ValueError("HP-4 fixture bytes do not match the reviewed catalog.")


def _resolve_paragraphs(
    ledger_path: Path,
    representation_id: str,
    cases: list[dict[str, object]],
) -> dict[str, tuple[str, str]]:
    with sqlite_ledger_transaction(ledger_path) as repository:
        bundle = repository.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError(f"Representation is missing: {representation_id}")
    text_by_view = {item.id: item.text for item in bundle.text_views}
    paragraphs = [item for item in bundle.nodes if item.node_type == "paragraph"]
    output: dict[str, tuple[str, str]] = {}
    used_nodes: set[str] = set()
    for case in cases:
        case_id = _string(case, "case_id")
        anchor = _string(case, "paragraph_anchor")
        matches: list[tuple[str, str]] = []
        for node in paragraphs:
            text = text_by_view[node.text_view_id][node.start_char : node.end_char]
            if anchor in text:
                matches.append((node.id, text))
        if len(matches) != 1:
            raise ValueError(f"{case_id} anchor resolved {len(matches)} paragraphs, expected one.")
        if matches[0][0] in used_nodes:
            raise ValueError(f"{case_id} repeats an HP-4 development paragraph.")
        used_nodes.add(matches[0][0])
        output[case_id] = matches[0]
    return output


def _run_command(args: argparse.Namespace, operation: tuple[str, ...]) -> dict[str, object]:
    command = (
        sys.executable,
        "-m",
        "kotekomi_pipelines.cli",
        "--config",
        str(args.config),
        *operation,
        "--ledger-path",
        str(args.ledger_path),
        "--archive-path",
        str(args.archive_path),
    )
    started_at = time.perf_counter()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    elapsed_milliseconds = round((time.perf_counter() - started_at) * 1000)
    payload: dict[str, object] = {
        "argv": list(command[2:]),
        "elapsed_milliseconds": elapsed_milliseconds,
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


def _raw_outputs(
    archive_path: Path,
    preview: dict[str, object],
    *,
    require_all: bool = True,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for model_run_id in _strings(preview, "model_run_ids"):
        path = archive_path / "model-runs" / f"{model_run_id}.json"
        if not path.is_file():
            if require_all:
                raise FileNotFoundError(f"HP-4 raw model output is missing: {model_run_id}")
            output.append(
                {
                    "archive_status": "not_archived_by_parent_stage",
                    "model_run_id": model_run_id,
                }
            )
            continue
        output.append(
            {
                "model_run_id": model_run_id,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "raw_output": path.read_text(encoding="utf-8"),
            }
        )
    return output


def _stage_summary(preview: dict[str, object]) -> dict[str, object]:
    traces = [_object(item) for item in _list(preview, "traces")]
    statuses: dict[str, int] = {}
    for trace in traces:
        key = f"{_string(trace, 'stage_id')}:{_string(trace, 'status')}"
        statuses[key] = statuses.get(key, 0) + 1
    return {
        "status": _string(preview, "terminal_status"),
        "trigger_count": len(_list(preview, "triggers")),
        "frame_count": len(_list(preview, "frames")),
        "trace_outcomes": statuses,
        "diagnostics": _strings(preview, "diagnostics"),
    }


def _failed_case(
    case: dict[str, object],
    node_id: str,
    paragraph_text: str,
    failed_stage: str,
    stage_results: dict[str, object],
    archive_path: Path,
) -> dict[str, object]:
    output: dict[str, object] = {
        "case_id": _string(case, "case_id"),
        "expected_semantic_work": _string(case, "expected_semantic_work"),
        "paragraph_node_id": node_id,
        "paragraph_text": paragraph_text,
        "paragraph_text_sha256": hashlib.sha256(paragraph_text.encode()).hexdigest(),
        "failed_stage": failed_stage,
    }
    output.update(stage_results)
    stage_result = _object(stage_results[failed_stage])
    relative_path = stage_result.get("archive_path")
    if isinstance(relative_path, str):
        preview_path = (archive_path / relative_path).resolve()
        if not preview_path.is_relative_to(archive_path.resolve()):
            raise ValueError("Evaluation Preview path escapes the configured Archive.")
        preview = _object(json.loads(preview_path.read_text(encoding="utf-8")))
        output["failed_preview"] = preview
        if "model_run_ids" in preview:
            output["raw_model_outputs"] = _raw_outputs(
                archive_path,
                preview,
                require_all=False,
            )
    return output


def _accepted_state_snapshot(ledger_path: Path) -> dict[str, object]:
    with sqlite_ledger_transaction(ledger_path) as repository:
        records = repository.list_accepted_canonical_records()
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
    hp4_results = [_object(item["hp4"]) for item in cases if "hp4" in item]
    previews = [_object(item["preview"]) for item in cases if "preview" in item]
    statuses: dict[str, int] = {}
    for preview in previews:
        status = _string(preview, "terminal_status")
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "case_count": len(cases),
        "hp4_result_count": len(hp4_results),
        "preview_count": len(previews),
        "preview_statuses": statuses,
        "trigger_count": sum(len(_list(item, "triggers")) for item in previews),
        "frame_count": sum(len(_list(item, "frames")) for item in previews),
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
