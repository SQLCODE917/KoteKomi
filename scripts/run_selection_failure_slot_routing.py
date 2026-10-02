"""Deterministic R11 runner that slots the frozen run-005 residual selection answers.

This runner reads the sealed run-005 report, its frozen raw answers, and its
constituent selection tasks, then classifies exactly the residual-review Events
into one selection-failure slot each, validates slot/status agreement and set
alignment, and seals one R11 report. It is model-free and writes only its own
run root.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    ConstituentSelectionTask,
    SelectionFailureDiagnosis,
    build_selection_failure_report,
    classify_selection_failure,
    parse_constituent_selection_answer,
    validate_diagnosis_set_alignment,
    validate_diagnosis_status,
)


def _load_tasks(path: Path) -> tuple[ConstituentSelectionTask, ...]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    tasks: list[ConstituentSelectionTask] = []
    for item in cast(list[dict[str, Any]], payload):
        item["constituent_labels"] = tuple(item["constituent_labels"])
        tasks.append(ConstituentSelectionTask.model_validate(item))
    return tuple(tasks)


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

    report = json.loads((source_root / "report.json").read_text())
    residual_event_ids = tuple(report["residual_review_event_ids"])

    tasks = {task.event_id: task for task in _load_tasks(source_root / "tasks.json")}
    raw_answers = _load_raw_answers(source_root / "answers.jsonl")

    diagnosis_list: list[SelectionFailureDiagnosis] = []
    for event_id in sorted(residual_event_ids):
        task = tasks[event_id]
        raw_answer = raw_answers[event_id]
        diagnosis = classify_selection_failure(raw_answer=raw_answer, task=task)
        status = parse_constituent_selection_answer(raw_answer=raw_answer, task=task).status
        validate_diagnosis_status(diagnosis=diagnosis, status=status)
        diagnosis_list.append(diagnosis)

    diagnoses = tuple(diagnosis_list)
    validate_diagnosis_set_alignment(diagnoses=diagnoses, residual_event_ids=residual_event_ids)
    sealed = build_selection_failure_report(diagnoses=diagnoses)

    diagnoses_payload = [
        {
            "event_id": item.event_id,
            "raw_answer_sha256": item.raw_answer_sha256,
            "slot": item.slot.value,
            "recoverable": item.recoverable,
        }
        for item in diagnoses
    ]
    (run_root / "diagnoses.json").write_text(
        json.dumps(diagnoses_payload, indent=2, sort_keys=True) + "\n"
    )
    (run_root / "report.json").write_text(
        json.dumps(sealed.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "source_report_fingerprint": report["result_fingerprint"],
                "result_fingerprint": sealed.result_fingerprint,
                "residual_review_event_ids": list(residual_event_ids),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    for item in diagnoses:
        print(f"{item.event_id}: {item.slot.value} recoverable={item.recoverable}")
    print(f"fingerprint: {sealed.result_fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
