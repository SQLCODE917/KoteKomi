"""Deterministic R12 runner that recovers the frozen run-005 label-mismatch answer.

This runner reads the sealed run-005 report, its frozen raw answers, constituent
selection tasks, selectable pools, pinned dependency tokens, and event frames,
then recovers exactly the recoverable ``rejection_label_mismatch`` Event
(``AHE-004``) into a completed selection and re-measures it through the
deterministic composer. Non-recoverable Events are confirmed to stay out of
automatic recovery. It is model-free and writes only its own run root.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    ConstituentCandidateInventory,
    ConstituentSelectionTask,
    EventEntityLinguisticToken,
    LabelMismatchRecoveryHalt,
    ParserConstituent,
    SelectionFailureSlot,
    build_label_mismatch_recovery,
    build_label_mismatch_recovery_report,
    classify_selection_failure,
    recover_label_mismatch,
    remeasure_recovered_selection,
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


def _load_constituent(item: dict[str, Any]) -> ParserConstituent:
    item["token_ids"] = tuple(item["token_ids"])
    return ParserConstituent.model_validate(item)


def _load_selectable(path: Path) -> dict[str, tuple[ParserConstituent, ...]]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    result: dict[str, tuple[ParserConstituent, ...]] = {}
    for entry in cast(list[dict[str, Any]], payload):
        result[entry["event_id"]] = tuple(
            _load_constituent(item) for item in cast(list[dict[str, Any]], entry["constituents"])
        )
    return result


def _load_frames(path: Path) -> dict[str, tuple[int, int]]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    result: dict[str, tuple[int, int]] = {}
    for entry in cast(list[dict[str, Any]], payload):
        trigger = entry["trigger"]
        result[entry["event_id"]] = (int(trigger["start"]), int(trigger["end"]))
    return result


def _load_tokens(path: Path) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return {
        digest: tuple(EventEntityLinguisticToken.model_validate(item) for item in records)
        for digest, records in cast(dict[str, list[dict[str, Any]]], payload).items()
    }


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
    frames = _load_frames(source_root / "frames.json")
    tokens_by_digest = _load_tokens(source_root / "tokens.json")
    selectable = _load_selectable(source_root / "selectable.json")

    recoveries: list[Any] = []
    recovered_event_ids: list[str] = []
    observations: dict[str, str] = {}
    for event_id in sorted(residual_event_ids):
        task = tasks[event_id]
        raw_answer = raw_answers[event_id]
        diagnosis = classify_selection_failure(raw_answer=raw_answer, task=task)
        if diagnosis.slot is SelectionFailureSlot.REJECTION_LABEL_MISMATCH:
            recovered = recover_label_mismatch(raw_answer=raw_answer, task=task)
            inventory = ConstituentCandidateInventory(
                event_id=task.event_id,
                source_text_sha256=task.source_text_sha256,
                constituents=selectable[event_id],
            )
            trigger_start, trigger_end = frames[event_id]
            remeasured = remeasure_recovered_selection(
                recovered=recovered,
                source_text=task.source_text,
                source_text_sha256=task.source_text_sha256,
                inventory=inventory,
                trigger_head_start=trigger_start,
                trigger_head_end=trigger_end,
                tokens=tokens_by_digest[task.source_text_sha256],
                entities=(),
            )
            recoveries.append(
                build_label_mismatch_recovery(
                    recovered=recovered, raw_answer=raw_answer, remeasured=remeasured
                )
            )
            recovered_event_ids.append(event_id)
            reason = f" ({remeasured.hold_reason.value})" if remeasured.hold_reason else ""
            observations[event_id] = (
                f"selected_label_indexes={recovered.selected_label_indexes}; "
                f"{remeasured.status.value}{reason}"
            )
            print(f"{event_id}: recovered {observations[event_id]}")
        else:
            assert diagnosis.recoverable is False
            try:
                recover_label_mismatch(raw_answer=raw_answer, task=task)
                raise AssertionError(f"{event_id} entered automatic recovery unexpectedly.")
            except LabelMismatchRecoveryHalt:
                pass
            print(f"{event_id}: {diagnosis.slot.value} (non-recoverable, halted)")

    sealed = build_label_mismatch_recovery_report(recoveries=tuple(recoveries))

    (run_root / "recoveries.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in recoveries], indent=2) + "\n"
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
                "recovered_event_ids": recovered_event_ids,
                "observations": observations,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(f"fingerprint: {sealed.result_fingerprint}")
    print(f"recovered_event_ids: {recovered_event_ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
