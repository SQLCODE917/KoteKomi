"""Deterministic R13 runner that recognizes and reifies the frozen ``AHE-004`` statement.

This runner reads the sealed R12 run (the recovered selection and its re-measured
result), binds them unchanged, then reads the frozen run-005 source data (tasks,
frames, tokens, and selectable constituents) to derive the ``AHE-004`` statement
slots deterministically. It recognizes exactly one ``eventive_state_change``
shape, reifies it into one Assertion draft, and seals one zero-write report.

It is model-free, never reads the held-out partition Gold, and writes only its
own run root.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    StatementSlots,
    build_eventive_statement_report,
    recognize_and_reify,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _load_tasks(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    return {item["event_id"]: item for item in cast(list[dict[str, Any]], payload)}


def _load_frames(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    return {item["event_id"]: item for item in cast(list[dict[str, Any]], payload)}


def _load_selectable(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    return {
        item["event_id"]: cast(list[dict[str, Any]], item["constituents"])
        for item in cast(list[dict[str, Any]], payload)
    }


def _root_lemma(tokens: list[dict[str, Any]]) -> str:
    for token in tokens:
        if token.get("dependency_relation") == "root":
            return cast(str, token["lemma"])
    raise ValueError("No root dependency token found for the recovered statement.")


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-012-root", required=True)
    parser.add_argument("--run-005-root", required=True)
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    r12_root = Path(args.run_012_root)
    r05_root = Path(args.run_005_root)
    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    # Bind the frozen recovered selection and re-measured result, unchanged.
    recoveries = cast(list[dict[str, Any]], _load_json(r12_root / "recoveries.json"))
    if len(recoveries) != 1:
        raise ValueError("R13 expects exactly one frozen recovery (AHE-004).")
    recovery = recoveries[0]
    event_id = cast(str, recovery["event_id"])
    completed = cast(dict[str, Any], recovery["completed_selection"])
    remeasured = cast(dict[str, Any], recovery["remeasured_result"])
    if event_id != "AHE-004":
        raise ValueError(f"Expected AHE-004, got {event_id}.")
    if completed.get("selected_label_indexes") != [1]:
        raise ValueError("R13 expected the recovered AHE-004 selection to be {C1}.")
    if remeasured.get("status") != "held" or remeasured.get("hold_reason") != "subject_unavailable":
        raise ValueError(
            "R13 expected the AHE-004 re-measured result to hold on subject_unavailable."
        )

    # Derive the statement slots from the frozen run-005 source data.
    tasks = _load_tasks(r05_root / "tasks.json")
    frames = _load_frames(r05_root / "frames.json")
    selectable = _load_selectable(r05_root / "selectable.json")
    tokens_by_digest = cast(dict[str, list[dict[str, Any]]], _load_json(r05_root / "tokens.json"))

    task = tasks[event_id]
    frame = frames[event_id]
    constituents = selectable[event_id]
    if len(constituents) < 2:
        raise ValueError("AHE-004 requires a subject and an object constituent.")

    source_text_sha256 = cast(str, task["source_text_sha256"])
    slots = StatementSlots(
        event_id=event_id,
        source_text_sha256=source_text_sha256,
        statement=cast(str, task["source_text"]),
        subject_text=constituents[0]["constituent_range"]["text"],
        subject_entity_ref=None,
        predicate_text=cast(str, frame["trigger"]["text"]),
        predicate_lemma=_root_lemma(tokens_by_digest[source_text_sha256]),
        object_text=constituents[1]["constituent_range"]["text"],
        object_entity_ref=None,
    )

    item = recognize_and_reify(slots=slots)
    report = build_eventive_statement_report(items=(item,))

    r12_report = cast(dict[str, Any], _load_json(r12_root / "report.json"))
    (run_root / "items.json").write_text(
        json.dumps([item.model_dump(mode="json")], indent=2, sort_keys=True) + "\n"
    )
    (run_root / "report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "source_report_fingerprint": r12_report["result_fingerprint"],
                "result_fingerprint": report.result_fingerprint,
                "recognized_event_ids": [event_id],
                "assigned_shape": item.recognition.shape.value,
                "reification_outcome": item.reification.outcome.value,
                "observations": {
                    event_id: (f"{item.recognition.shape.value} ({item.reification.outcome.value})")
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(f"fingerprint: {report.result_fingerprint}")
    print(f"assigned_shape: {item.recognition.shape.value}")
    print(f"reification_outcome: {item.reification.outcome.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
