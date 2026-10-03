"""Deterministic R15 runner that prepares corrective re-selection tasks.

This runner reads the sealed run-005 report, its frozen raw answers, and its
constituent selection tasks, then routes each unrecovered residual selection
failure to one closure route and builds one corrective re-selection task per
residual Event. The recoverable ``rejection_label_mismatch`` Event (``AHE-004``)
stays out of the closure routing because R12 already closed it.

It is model-free, reads no held-out partition Gold, and writes only its own run
root. The corrective re-selection itself runs in the next deliverable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    ConstituentSelectionTask,
    SelectionFailureSlot,
    build_residual_closure_report,
    classify_selection_failure,
    route_residual_selection_failure,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _load_tasks(path: Path) -> dict[str, ConstituentSelectionTask]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    result: dict[str, ConstituentSelectionTask] = {}
    for item in cast(list[dict[str, Any]], payload):
        item["constituent_labels"] = tuple(item["constituent_labels"])
        task = ConstituentSelectionTask.model_validate(item)
        result[task.event_id] = task
    return result


def _load_raw_answers(path: Path) -> dict[str, str]:
    answers: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        answers[record["event_id"]] = record["raw_answer"]
    return answers


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-005-root", required=True)
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    source_root = Path(args.run_005_root)
    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    report = cast(dict[str, Any], _load_json(source_root / "report.json"))
    residual_review_event_ids = tuple(cast(list[str], report["residual_review_event_ids"]))
    tasks = _load_tasks(source_root / "tasks.json")
    raw_answers = _load_raw_answers(source_root / "answers.jsonl")

    routings: list[Any] = []
    closed_by_r12: list[str] = []
    observations: dict[str, str] = {}
    for event_id in sorted(residual_review_event_ids):
        task = tasks[event_id]
        raw_answer = raw_answers[event_id]
        diagnosis = classify_selection_failure(raw_answer=raw_answer, task=task)
        if diagnosis.slot is SelectionFailureSlot.REJECTION_LABEL_MISMATCH:
            closed_by_r12.append(event_id)
            observations[event_id] = "recovered by R12, closed"
            print(f"{event_id}: {diagnosis.slot.value} (recovered by R12, skipped)")
            continue
        routing = route_residual_selection_failure(raw_answer=raw_answer, task=task)
        routings.append(routing)
        observations[event_id] = f"{diagnosis.slot.value} -> {routing.closure_route.value}"
        print(f"{event_id}: {routing.slot.value} -> {routing.closure_route.value}")

    routed_event_ids = tuple(routing.event_id for routing in routings)
    if routed_event_ids != ("AHE-022", "AHE-051"):
        raise ValueError(f"R15 expected AHE-022 and AHE-051, got {routed_event_ids}.")
    if closed_by_r12 != ["AHE-004"]:
        raise ValueError(f"R15 expected AHE-004 closed by R12, got {closed_by_r12}.")

    sealed = build_residual_closure_report(items=tuple(routings))

    (run_root / "items.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in routings], indent=2) + "\n"
    )
    (run_root / "report.json").write_text(
        json.dumps(sealed.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "source_report_fingerprint": report["result_fingerprint"],
                "result_fingerprint": sealed.result_fingerprint,
                "closed_by_r12_event_ids": closed_by_r12,
                "routed_event_ids": [item.event_id for item in routings],
                "observations": observations,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(f"fingerprint: {sealed.result_fingerprint}")
    print(f"routed_event_ids: {routed_event_ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
