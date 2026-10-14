#!/usr/bin/env python3
"""Run the R16 corrective re-selection execution experiment.

R16 executes the two R15 corrective re-selection tasks exactly once against the
local LM Studio runtime, applies each closure route's strict answer grammar, and
re-measures every selected answer through the deterministic composer.  Runner
phases over one run root:

* ``prepare`` -- model-free.  Validates the frozen run-005 records and the
  sealed R15 evidence through their declared DTOs, re-verifies the frozen file
  digests, recomputes the R15 report fingerprint, and binds the two corrective
  tasks with their frozen source, selectable constituents, event frame, and
  dependency tokens.  It reads no Gold, catalog, PDF, or model-derived
  replacement.
* ``execute`` -- admits and runs each corrected prompt at most once, archives
  the raw response, parses the route grammar, and re-measures selected answers.
  Blocked admissions and runtime errors become terminal execution items.
* ``report`` -- rebuilds the sealed report deterministically from the archived
  responses without another model call.
* ``show`` / ``artifacts`` / ``trace`` -- bounded inspection of the run root.

R16 records zero accepted Ledger changes and zero ProposedChanges.  All inputs
and outputs are explicit paths or a TOML config file; no environment variables
are assumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    ConstituentCandidateInventory,
    ConstituentSelectionTask,
    CorrectiveReselectionAttempt,
    CorrectiveReselectionExecutionItem,
    CorrectiveReselectionExecutionOutcome,
    CorrectiveReselectionExecutionRequest,
    CorrectiveReselectionOutcome,
    CorrectiveReselectionReport,
    CorrectiveSelectionTask,
    EventEntityLinguisticToken,
    EventFrame,
    ExecutionAttemptStatus,
    ExecutionSetting,
    ParserConstituent,
    ResidualClosureReport,
    ResidualClosureRouting,
    build_corrective_reselection_report,
    build_corrective_selection_task,
    build_residual_closure_report,
    generation_parameters_digest,
    model_execution_receipt_from_payload,
    model_execution_spec_from_payload,
    model_identity_snapshot_digest,
    rebuild_corrective_reselection_report,
    run_corrective_reselection_attempt,
)
from kotekomi_domain import ModelInputAdmission, ModelInputAdmissionStatus
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-10-06-corrective-reselection-execution.md"
DEFAULT_RUN_005_ROOT = REPOSITORY_ROOT / "data/r6-calibrated-residual-ownership-runs/run-005"
DEFAULT_R15_ROOT = REPOSITORY_ROOT / "data/r15-residual-selection-failure-closure-runs/run-001"
DEFAULT_RUN_ROOT = REPOSITORY_ROOT / "data/r16-corrective-reselection-execution-runs/run-001"
DEFAULT_CONFIG = REPOSITORY_ROOT / "docs/r6-calibrated-residual-ownership-run-config.toml"

RUN_SCHEMA_VERSION = "corrective_reselection_execution_run_v1"
CORRECTIVE_RESELECTION_SCHEMA_ID = "corrective_reselection_label_v1"
CORRECTIVE_RESELECTION_OUTPUT_CONTRACT = "constituent_selection_label_v1"
_CORRECTIVE_RESELECTION_PROMPT_BYTES = (
    b"Render the corrected constituent selection answer as a bare Candidate label set.\n"
)
_CORRECTIVE_RESELECTION_SCHEMA_BYTES = (
    b"comma-separated Candidate labels, or the exact token NONE for the best-choice route\n"
)
_CORRECTIVE_RESELECTION_SAFETY_MARGIN_TOKENS = 256
EXPECTED_EVENT_IDS = ("AHE-022", "AHE-051")
REQUIRED_ADAPTER = "lm_studio"
REQUIRED_MODEL = "qwen2.5-14b-instruct"


@dataclass(frozen=True)
class _PreparedState:
    schema_version: str
    tdd_digest: str
    run_005_root: Path
    source_report_fingerprint: str
    closure_report_fingerprint: str
    routed_event_ids: tuple[str, ...]
    adapter: str
    endpoint: str
    model: str
    profile_name: str
    timeout_seconds: float
    context_tokens: int
    max_output_tokens: int
    frozen_digests: dict[str, str]
    corrective_tasks: dict[str, CorrectiveSelectionTask]
    tasks: dict[str, ConstituentSelectionTask]
    inventories: dict[str, ConstituentCandidateInventory]
    frames: dict[str, EventFrame]
    tokens: dict[str, tuple[EventEntityLinguisticToken, ...]]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure R16 corrective re-selection on the frozen residual Events."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    prepare.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    prepare.add_argument("--run-005-root", type=Path, default=DEFAULT_RUN_005_ROOT)
    prepare.add_argument("--r15-root", type=Path, default=DEFAULT_R15_ROOT)

    execute = commands.add_parser("execute")
    execute.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    execute.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    report = commands.add_parser("report")
    report.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    show = commands.add_parser("show")
    show.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    artifacts = commands.add_parser("artifacts")
    artifacts.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    trace = commands.add_parser("trace")
    trace.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    trace.add_argument("--event-id", required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "execute":
        return _execute(args)
    if args.command == "report":
        return _report(args)
    if args.command == "show":
        return _show(args)
    if args.command == "artifacts":
        return _artifacts(args)
    if args.command == "trace":
        return _trace(args)
    raise ValueError(f"Unsupported R16 command: {args.command}")


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _generation_parameters(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    settings = (
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )
    if tuple(sorted(settings, key=lambda item: item.key)) != settings:
        raise ValueError("R16 generation settings are not canonically ordered.")
    return settings


# --------------------------------------------------------------------------- #
# Shared file helpers
# --------------------------------------------------------------------------- #


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _read_json_list(path: Path) -> list[Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    return cast(list[Any], value)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n",
        encoding="utf-8",
    )


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _deterministic_id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{_sha_bytes(('\x1f'.join(parts)).encode('utf-8'))[:24]}"


def _close_runtime(runtime: Any) -> None:
    close = getattr(runtime, "close", None)
    if callable(close):
        close()


# --------------------------------------------------------------------------- #
# Frozen run-005 loaders and validators
# --------------------------------------------------------------------------- #


def _load_frozen_tasks(path: Path) -> dict[str, ConstituentSelectionTask]:
    result: dict[str, ConstituentSelectionTask] = {}
    for item in _read_json_list(path):
        record = dict(cast(dict[str, Any], item))
        record["constituent_labels"] = tuple(record["constituent_labels"])
        task = ConstituentSelectionTask.model_validate(record)
        result[task.event_id] = task
    return result


def _load_selectable(path: Path) -> dict[str, tuple[ParserConstituent, ...]]:
    result: dict[str, tuple[ParserConstituent, ...]] = {}
    for entry in _read_json_list(path):
        record = cast(dict[str, Any], entry)
        constituents: list[ParserConstituent] = []
        for item in cast(list[Any], record["constituents"]):
            constituent = dict(cast(dict[str, Any], item))
            constituent["token_ids"] = tuple(constituent["token_ids"])
            constituents.append(ParserConstituent.model_validate(constituent))
        result[cast(str, record["event_id"])] = tuple(constituents)
    return result


def _load_frames(path: Path) -> dict[str, EventFrame]:
    result: dict[str, EventFrame] = {}
    for item in _read_json_list(path):
        record = dict(cast(dict[str, Any], item))
        record["core_constituents"] = tuple(record["core_constituents"])
        frame = EventFrame.model_validate(record)
        result[frame.event_id] = frame
    return result


def _load_tokens(path: Path) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    payload = json.loads(path.read_bytes())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    table = cast(dict[str, Any], payload)
    result: dict[str, tuple[EventEntityLinguisticToken, ...]] = {}
    for digest, records in table.items():
        if not isinstance(records, list):
            raise ValueError(f"Malformed dependency-token table: {path}.")
        result[digest] = tuple(
            EventEntityLinguisticToken.model_validate(item) for item in cast(list[Any], records)
        )
    return result


def _verify_required_frozen(
    run_005_root: Path,
    run_005_run: dict[str, Any],
) -> tuple[
    dict[str, ConstituentSelectionTask],
    dict[str, tuple[ParserConstituent, ...]],
    dict[str, EventFrame],
    dict[str, tuple[EventEntityLinguisticToken, ...]],
    dict[str, str],
]:
    outputs = run_005_run.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("run-005 run.json is missing its outputs table.")
    output_digests = cast(dict[str, Any], outputs)

    frozen: dict[str, Path] = {
        "tasks": run_005_root / "tasks.json",
        "selectable": run_005_root / "selectable.json",
        "frames": run_005_root / "frames.json",
        "tokens": run_005_root / "tokens.json",
    }
    frozen_digests: dict[str, str] = {}
    for key, path in frozen.items():
        expected = output_digests.get(key)
        if not isinstance(expected, str):
            raise ValueError(f"run-005 run.json is missing the '{key}' digest.")
        if _sha_file(path) != expected:
            raise ValueError(f"Frozen run-005 file drifted from its sealed digest: {path}.")
        frozen_digests[key] = expected

    tasks = _load_frozen_tasks(frozen["tasks"])
    selectable = _load_selectable(frozen["selectable"])
    frames = _load_frames(frozen["frames"])
    tokens = _load_tokens(frozen["tokens"])
    return tasks, selectable, frames, tokens, frozen_digests


# --------------------------------------------------------------------------- #
# R15 evidence loaders and corrections
# --------------------------------------------------------------------------- #


def _load_r15_evidence(
    r15_root: Path,
) -> tuple[ResidualClosureReport, tuple[ResidualClosureRouting, ...]]:
    r15_run = _read_json(r15_root / "run.json")
    source_report_fingerprint = r15_run.get("source_report_fingerprint")
    if not isinstance(source_report_fingerprint, str):
        raise ValueError("R15 run.json is missing source_report_fingerprint.")

    report_payload = _read_json(r15_root / "report.json")
    report_payload["items"] = tuple(report_payload["items"])
    report = ResidualClosureReport.model_validate(report_payload, strict=False)
    routings = tuple(
        ResidualClosureRouting.model_validate(item, strict=False)
        for item in _read_json_list(r15_root / "items.json")
    )
    rebuilt = build_residual_closure_report(items=routings)
    if rebuilt.result_fingerprint != report.result_fingerprint:
        raise ValueError("R15 report fingerprint does not rebuild from its items.")
    if tuple(item.event_id for item in routings) != EXPECTED_EVENT_IDS:
        raise ValueError(
            f"R16 requires exactly {EXPECTED_EVENT_IDS}, "
            f"got {tuple(item.event_id for item in routings)}."
        )
    return report, routings


def _bind_frozen_inputs(
    routings: tuple[ResidualClosureRouting, ...],
    tasks: dict[str, ConstituentSelectionTask],
    selectable: dict[str, tuple[ParserConstituent, ...]],
    tokens: dict[str, tuple[EventEntityLinguisticToken, ...]],
) -> tuple[
    dict[str, ConstituentCandidateInventory],
    dict[str, tuple[EventEntityLinguisticToken, ...]],
]:
    """Verify corrective prompts and bind the frozen composition inputs."""
    inventories: dict[str, ConstituentCandidateInventory] = {}
    event_tokens: dict[str, tuple[EventEntityLinguisticToken, ...]] = {}
    for routing in routings:
        event_id = routing.event_id
        task = tasks[event_id]
        rebuilt = build_corrective_selection_task(task=task, route=routing.closure_route)
        original = routing.corrective_task
        if (
            rebuilt.corrected_prompt != original.corrected_prompt
            or rebuilt.corrected_prompt_sha256 != original.corrected_prompt_sha256
            or rebuilt.corrected_instruction != original.corrected_instruction
            or rebuilt.original_rendered_input_sha256 != original.original_rendered_input_sha256
        ):
            raise ValueError(f"{event_id} corrective prompt drifted from the frozen task.")

        constituents = selectable[event_id]
        if len(constituents) != len(task.constituent_labels):
            raise ValueError(f"{event_id} labels do not match its selectable constituents.")
        inventory = ConstituentCandidateInventory(
            event_id=task.event_id,
            source_text_sha256=task.source_text_sha256,
            constituents=constituents,
        )
        for constituent in constituents:
            span = constituent.constituent_range
            if task.source_text[span.start : span.end] != span.text:
                raise ValueError(
                    f"{event_id} constituent {constituent.constituent_id} is not source-exact."
                )
        inventories[event_id] = inventory
        event_tokens[event_id] = tokens[task.source_text_sha256]
    return inventories, event_tokens


# --------------------------------------------------------------------------- #
# Command implementations
# --------------------------------------------------------------------------- #


def _prepare(args: argparse.Namespace) -> int:
    config = _config(args.config)
    if (
        config.model_execution.adapter != REQUIRED_ADAPTER
        or config.model_execution.model != REQUIRED_MODEL
    ):
        raise ValueError(
            f"R16 requires adapter={REQUIRED_ADAPTER!r} and model={REQUIRED_MODEL!r}; "
            f"got adapter={config.model_execution.adapter!r} "
            f"and model={config.model_execution.model!r}. "
            "A different runtime or model requires a separately named experiment."
        )
    run_005_root = args.run_005_root.resolve()
    r15_root = args.r15_root.resolve()
    run_root = args.run_root.resolve()

    if (run_root / "preparation.json").exists():
        raise ValueError("R16 run root is already prepared; use a new run root.")
    run_root.mkdir(parents=True, exist_ok=True)

    run_005_run = _read_json(run_005_root / "run.json")
    tasks, selectable, frames, tokens, frozen_digests = _verify_required_frozen(
        run_005_root, run_005_run
    )
    report, routings = _load_r15_evidence(r15_root)

    run_005_report = _read_json(run_005_root / "report.json")
    run_005_fingerprint = run_005_report.get("result_fingerprint")
    if not isinstance(run_005_fingerprint, str):
        raise ValueError("run-005 report.json is missing result_fingerprint.")
    r15_run = _read_json(r15_root / "run.json")
    source_report_fingerprint = r15_run.get("source_report_fingerprint")
    if source_report_fingerprint != run_005_fingerprint:
        raise ValueError(
            "R15 source_report_fingerprint does not match the run-005 report fingerprint."
        )

    inventories, event_tokens = _bind_frozen_inputs(routings, tasks, selectable, tokens)

    corrective_tasks = {routing.event_id: routing.corrective_task for routing in routings}
    routed_event_ids = EXPECTED_EVENT_IDS

    state = _PreparedState(
        schema_version=RUN_SCHEMA_VERSION,
        tdd_digest=_sha_file(TDD_PATH),
        run_005_root=run_005_root,
        source_report_fingerprint=cast(str, source_report_fingerprint),
        closure_report_fingerprint=report.result_fingerprint,
        routed_event_ids=routed_event_ids,
        adapter=config.model_execution.adapter,
        endpoint=config.model_execution.endpoint,
        model=config.model_execution.model,
        profile_name=config.model_execution.profile_name or config.model_execution.adapter,
        timeout_seconds=config.model_execution.timeout_seconds,
        context_tokens=config.model_execution.context_tokens,
        max_output_tokens=config.model_execution.max_output_tokens,
        frozen_digests=frozen_digests,
        corrective_tasks=corrective_tasks,
        tasks=tasks,
        inventories=inventories,
        frames=frames,
        tokens=event_tokens,
    )

    model_execution = config.model_execution
    _write_json(
        run_root / "preparation.json",
        {
            "schema_version": state.schema_version,
            "tdd_digest": state.tdd_digest,
            "run_005_root": str(state.run_005_root),
            "source_report_fingerprint": state.source_report_fingerprint,
            "closure_report_fingerprint": state.closure_report_fingerprint,
            "routed_event_ids": list(state.routed_event_ids),
            "model_execution": {
                "adapter": model_execution.adapter,
                "endpoint": model_execution.endpoint,
                "model": model_execution.model,
                "profile_name": state.profile_name,
                "timeout_seconds": model_execution.timeout_seconds,
                "context_tokens": model_execution.context_tokens,
                "max_output_tokens": model_execution.max_output_tokens,
            },
            "frozen_digests": state.frozen_digests,
        },
    )
    _write_json(
        run_root / "tasks.json",
        [
            task.model_dump(mode="json")
            for task in _ordered_tasks(corrective_tasks, routed_event_ids)
        ],
    )
    _write_json(
        run_root / "status.json",
        {
            "status": "prepared",
            "run_root": str(run_root),
            "routed_event_ids": list(routed_event_ids),
        },
    )

    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(run_root),
                "source_report_fingerprint": state.source_report_fingerprint,
                "closure_report_fingerprint": state.closure_report_fingerprint,
                "routed_event_ids": list(routed_event_ids),
            },
            sort_keys=True,
        )
    )
    return 0


def _ordered_tasks(
    tasks: dict[str, CorrectiveSelectionTask], event_ids: tuple[str, ...]
) -> list[CorrectiveSelectionTask]:
    return [tasks[event_id] for event_id in event_ids]


def _rehydrate_state(run_root: Path, config: PipelineConfig) -> _PreparedState:
    """Re-read the prepared run root plus its frozen inputs, verified end-to-end."""
    prep = _read_json(run_root / "preparation.json")
    if prep.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ValueError("R16 preparation schema drifted.")
    model_execution = prep.get("model_execution")
    if not isinstance(model_execution, dict):
        raise ValueError("R16 preparation is missing its model_execution table.")
    model_execution = cast(dict[str, Any], model_execution)
    run_005_root = Path(cast(str, prep["run_005_root"]))
    routed_event_ids = tuple(cast(str, item) for item in prep["routed_event_ids"])
    if routed_event_ids != EXPECTED_EVENT_IDS:
        raise ValueError(f"R16 requires exactly {EXPECTED_EVENT_IDS}, got {routed_event_ids}.")

    me = config.model_execution
    candidate = {
        "adapter": me.adapter,
        "endpoint": me.endpoint,
        "model": me.model,
        "profile_name": me.profile_name or me.adapter,
        "timeout_seconds": me.timeout_seconds,
        "context_tokens": me.context_tokens,
        "max_output_tokens": me.max_output_tokens,
    }
    if candidate != model_execution:
        raise ValueError("R16 execute config drifted from the prepared model binding.")

    corrective_list = [
        CorrectiveSelectionTask.model_validate(item, strict=False)
        for item in _read_json_list(run_root / "tasks.json")
    ]
    corrective_tasks = {task.event_id: task for task in corrective_list}
    if tuple(corrective_tasks.keys()) != routed_event_ids:
        raise ValueError("R16 tasks.json drifted from the prepared event order.")

    run_005_run = _read_json(run_005_root / "run.json")
    tasks, selectable, frames, tokens, frozen_digests = _verify_required_frozen(
        run_005_root, run_005_run
    )
    recorded_digests = prep.get("frozen_digests")
    if not isinstance(recorded_digests, dict) or recorded_digests != frozen_digests:
        raise ValueError("Frozen digests drifted from the R16 preparation record.")

    inventories: dict[str, ConstituentCandidateInventory] = {}
    event_tokens: dict[str, tuple[EventEntityLinguisticToken, ...]] = {}
    for event_id in routed_event_ids:
        task = tasks[event_id]
        corrective = corrective_tasks[event_id]
        rebuilt = build_corrective_selection_task(task=task, route=corrective.closure_route)
        if rebuilt != corrective:
            raise ValueError(f"{event_id} corrective prompt drifted from its frozen task.")
        constituents = selectable[event_id]
        if len(constituents) != len(task.constituent_labels):
            raise ValueError(f"{event_id} labels do not match its selectable constituents.")
        inventory = ConstituentCandidateInventory(
            event_id=task.event_id,
            source_text_sha256=task.source_text_sha256,
            constituents=constituents,
        )
        for constituent in constituents:
            span = constituent.constituent_range
            if task.source_text[span.start : span.end] != span.text:
                raise ValueError(
                    f"{event_id} constituent {constituent.constituent_id} is not source-exact."
                )
        inventories[event_id] = inventory
        event_tokens[event_id] = tokens[task.source_text_sha256]

    return _PreparedState(
        schema_version=RUN_SCHEMA_VERSION,
        tdd_digest=cast(str, prep["tdd_digest"]),
        run_005_root=run_005_root,
        source_report_fingerprint=cast(str, prep["source_report_fingerprint"]),
        closure_report_fingerprint=cast(str, prep["closure_report_fingerprint"]),
        routed_event_ids=routed_event_ids,
        adapter=me.adapter,
        endpoint=me.endpoint,
        model=me.model,
        profile_name=me.profile_name or me.adapter,
        timeout_seconds=me.timeout_seconds,
        context_tokens=me.context_tokens,
        max_output_tokens=me.max_output_tokens,
        frozen_digests=frozen_digests,
        corrective_tasks=corrective_tasks,
        tasks=tasks,
        inventories=inventories,
        frames=frames,
        tokens=event_tokens,
    )


def _require_status(run_root: Path, expected: str) -> None:
    status = _read_json(run_root / "status.json")
    if status.get("status") != expected:
        raise ValueError(f"R16 requires a '{expected}' run before this command: {run_root}.")


def _execute(args: argparse.Namespace) -> int:
    config = _config(args.config)
    run_root = args.run_root.resolve()
    state = _rehydrate_state(run_root, config)
    _require_status(run_root, "prepared")

    runtime = build_model_task_runtime(config.model_execution)
    readiness = runtime.check_readiness()
    if not readiness.ready:
        _close_runtime(runtime)
        raise RuntimeError(
            f"R16 model runtime is not ready: adapter={readiness.adapter!r}, "
            f"model={readiness.model!r}, available={readiness.model_available}."
        )

    profile_id = state.profile_name
    generation = _generation_parameters(config)
    prompt_digest = _sha_bytes(_CORRECTIVE_RESELECTION_PROMPT_BYTES)
    schema_digest = _sha_bytes(_CORRECTIVE_RESELECTION_SCHEMA_BYTES)

    for directory in ("responses", "attempts", "items"):
        (run_root / directory).mkdir(exist_ok=True)
    _write_json(
        run_root / "status.json",
        {"status": "running", "run_root": str(run_root)},
    )

    outcomes: list[CorrectiveReselectionExecutionOutcome] = []
    try:
        for event_id in state.routed_event_ids:
            outcomes.append(
                _execute_one(
                    event_id=event_id,
                    state=state,
                    runtime=runtime,
                    run_root=run_root,
                    profile_id=profile_id,
                    generation=generation,
                    prompt_digest=prompt_digest,
                    schema_digest=schema_digest,
                )
            )
    finally:
        _close_runtime(runtime)

    report = _seal(run_root, state, tuple(outcome.item for outcome in outcomes))
    print(
        json.dumps(
            {
                "status": _terminal_status(report.items),
                "run_root": str(run_root),
                "result_fingerprint": report.result_fingerprint,
                "outcomes": {item.event_id: item.outcome.value for item in report.items},
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
                "proposed_change_count": report.proposed_change_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _execute_one(
    *,
    event_id: str,
    state: _PreparedState,
    runtime: Any,
    run_root: Path,
    profile_id: str,
    generation: tuple[ExecutionSetting, ...],
    prompt_digest: str,
    schema_digest: str,
) -> CorrectiveReselectionExecutionOutcome:
    corrective = state.corrective_tasks[event_id]
    corrected_prompt = corrective.corrected_prompt
    corrected_prompt_sha256 = corrective.corrected_prompt_sha256
    attempt_id = _deterministic_id("atc", event_id, corrected_prompt_sha256)
    extraction_task_id = _deterministic_id("ext", event_id, corrected_prompt_sha256)
    model_run_id = _deterministic_id("mrn", event_id, corrected_prompt_sha256)
    context_manifest_id = _deterministic_id("cxm", event_id, corrected_prompt_sha256)
    context_manifest_digest = _sha_bytes(
        corrected_prompt.encode("utf-8")
        + _CORRECTIVE_RESELECTION_PROMPT_BYTES
        + _CORRECTIVE_RESELECTION_SCHEMA_BYTES
    )

    def persist_running_attempt(attempt: Any) -> None:
        _write_json(run_root / "attempts" / f"{event_id}.json", attempt.model_dump(mode="json"))

    def store_response(raw_output: bytes) -> str:
        path = run_root / "responses" / f"{event_id}.bin"
        path.write_bytes(raw_output)
        return _sha_bytes(raw_output)

    request = CorrectiveReselectionExecutionRequest(
        attempt_id=attempt_id,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        event_id=event_id,
        closure_route=corrective.closure_route,
        corrected_prompt=corrected_prompt,
        corrected_prompt_sha256=corrected_prompt_sha256,
        task=state.tasks[event_id],
        inventory=state.inventories[event_id],
        trigger_head_start=state.frames[event_id].trigger.start,
        trigger_head_end=state.frames[event_id].trigger.end,
        tokens=state.tokens[event_id],
        entities=(),
        model_profile_id=profile_id,
        model_identity=runtime.configured_identity,
        generation_parameters=generation,
        configured_context_limit=state.context_tokens,
        reserved_output_tokens=state.max_output_tokens,
        safety_margin_tokens=_CORRECTIVE_RESELECTION_SAFETY_MARGIN_TOKENS,
        prompt_id=CORRECTIVE_RESELECTION_SCHEMA_ID,
        prompt_digest=prompt_digest,
        schema_id=CORRECTIVE_RESELECTION_SCHEMA_ID,
        schema_digest=schema_digest,
        context_manifest_id=context_manifest_id,
        context_manifest_digest=context_manifest_digest,
        output_contract_version=CORRECTIVE_RESELECTION_OUTPUT_CONTRACT,
    )

    outcome = run_corrective_reselection_attempt(
        request,
        runtime=runtime,
        persist_running_attempt=persist_running_attempt,
        store_response=store_response,
    )
    _write_json(run_root / "attempts" / f"{event_id}.json", outcome.attempt.model_dump(mode="json"))
    _write_json(run_root / "items" / f"{event_id}.json", outcome.item.model_dump(mode="json"))
    return outcome


def _terminal_status(items: tuple[CorrectiveReselectionExecutionItem, ...]) -> str:
    """Return ``failed`` when any item is blocked or runtime-failed, else ``complete``."""
    if any(
        item.outcome
        in {
            CorrectiveReselectionOutcome.INPUT_BLOCKED,
            CorrectiveReselectionOutcome.RUNTIME_FAILED,
        }
        for item in items
    ):
        return "failed"
    return "complete"


def _write_terminal_status(
    run_root: Path,
    report: CorrectiveReselectionReport,
    status: str,
) -> None:
    _write_json(
        run_root / "status.json",
        {
            "status": status,
            "run_root": str(run_root),
            "terminal_item_count": len(report.items),
            "result_fingerprint": report.result_fingerprint,
            "model_execution_count": report.model_execution_count,
            "canonical_write_count": report.canonical_write_count,
            "proposed_change_count": report.proposed_change_count,
        },
    )


def _seal(
    run_root: Path,
    state: _PreparedState,
    items: tuple[CorrectiveReselectionExecutionItem, ...],
) -> CorrectiveReselectionReport:
    report = build_corrective_reselection_report(
        source_report_fingerprint=state.source_report_fingerprint,
        closure_report_fingerprint=state.closure_report_fingerprint,
        items=items,
    )
    _write_json(run_root / "report.json", report.model_dump(mode="json"))
    (run_root / "review.md").write_text(
        _render_review(
            state.source_report_fingerprint,
            state.closure_report_fingerprint,
            report,
        ),
        encoding="utf-8",
    )
    _write_terminal_status(run_root, report, _terminal_status(items))
    return report


def _render_review(
    source_report_fingerprint: str,
    closure_report_fingerprint: str,
    report: CorrectiveReselectionReport,
) -> str:
    lines = ["# R16 Corrective Re-Selection Execution", ""]
    lines.append(f"Source report fingerprint: `{source_report_fingerprint}`")
    lines.append(f"Closure report fingerprint: `{closure_report_fingerprint}`")
    lines.append(f"Result fingerprint: `{report.result_fingerprint}`")
    lines.append("")
    lines.append(
        f"Model executions: {report.model_execution_count} | "
        f"canonical writes: {report.canonical_write_count} | "
        f"proposed changes: {report.proposed_change_count}"
    )
    lines.append("")
    lines.append("| Event | Route | Outcome | Detail |")
    lines.append("|---|---|---|---|")
    for item in report.items:
        detail = _item_detail(item)
        lines.append(
            f"| {item.event_id} | {item.closure_route.value} | {item.outcome.value} | {detail} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _item_detail(item: CorrectiveReselectionExecutionItem) -> str:
    if item.error is not None:
        return item.error
    if item.parsed_answer is not None:
        status = item.parsed_answer.status.value
        indexes = list(item.parsed_answer.selected_label_indexes)
        return f"answer={status} labels={indexes}"
    raise ValueError(f"Execution item {item.event_id} carries no detail.")


def _validate_terminal_pair(
    event_id: str,
    attempt: CorrectiveReselectionAttempt,
    item: CorrectiveReselectionExecutionItem,
    run_root: Path,
    *,
    expected_input_digest: str,
) -> None:
    if attempt.attempt_id != item.attempt_id:
        raise ValueError(f"{event_id} item and attempt attempt IDs drifted.")
    if attempt.event_id != item.event_id or attempt.event_id != event_id:
        raise ValueError(f"{event_id} item and attempt Event IDs drifted.")
    if attempt.rendered_input_digest != expected_input_digest:
        raise ValueError(f"{event_id} attempt input digest drifted from its task.")
    response_path = run_root / "responses" / f"{event_id}.bin"
    if item.raw_response_sha256 is not None:
        if attempt.status is not ExecutionAttemptStatus.ANSWERED:
            raise ValueError(f"{event_id} archived a response without an answered attempt.")
        if not response_path.exists():
            raise ValueError(f"{event_id} is missing its archived response.")
        if _sha_file(response_path) != item.raw_response_sha256:
            raise ValueError(f"{event_id} archived response digest drifted.")
    elif response_path.exists():
        raise ValueError(f"{event_id} archived an unexpected response.")
    if item.outcome is CorrectiveReselectionOutcome.INPUT_BLOCKED:
        if attempt.status is not ExecutionAttemptStatus.INPUT_BLOCKED:
            raise ValueError(f"{event_id} input-blocked item requires a blocked attempt.")
    elif item.outcome is CorrectiveReselectionOutcome.RUNTIME_FAILED:
        if attempt.status is not ExecutionAttemptStatus.RUNTIME_FAILED:
            raise ValueError(f"{event_id} runtime-failed item requires a failed attempt.")
    elif attempt.status is not ExecutionAttemptStatus.ANSWERED:
        raise ValueError(f"{event_id} answered item requires an answered attempt.")
    if item.model_invoked != (attempt.execution_spec is not None):
        raise ValueError(f"{event_id} invocation evidence drifted from its attempt.")
    if attempt.admission is None:
        if item.model_invoked:
            raise ValueError(f"{event_id} invoked the model without a recorded admission.")
    else:
        admission = ModelInputAdmission.model_validate(attempt.admission, strict=False)
        if admission.extraction_task_id != attempt.extraction_task_id:
            raise ValueError(f"{event_id} admission redirected to another extraction task.")
        if admission.model_profile_id != attempt.model_profile_id:
            raise ValueError(f"{event_id} admission redirected to another model profile.")
        if admission.model_identity_digest != attempt.model_identity_digest:
            raise ValueError(f"{event_id} admission identity drifted from its attempt.")
        if admission.logical_input_digest != expected_input_digest:
            raise ValueError(f"{event_id} admission input digest drifted from its task.")
        if attempt.status is ExecutionAttemptStatus.INPUT_BLOCKED:
            if admission.status is not ModelInputAdmissionStatus.CONTEXT_BUDGET_BLOCKED:
                raise ValueError(f"{event_id} blocked attempt requires a blocked admission.")
        elif admission.status is not ModelInputAdmissionStatus.READY:
            raise ValueError(f"{event_id} non-blocked attempt requires a ready admission.")
    if attempt.execution_spec is not None:
        spec = model_execution_spec_from_payload(attempt.execution_spec)
        if spec.model_profile_id != attempt.model_profile_id:
            raise ValueError(f"{event_id} execution spec redirected to another model profile.")
        if spec.rendered_input_digest != expected_input_digest:
            raise ValueError(f"{event_id} execution spec input digest drifted from its task.")
        if model_identity_snapshot_digest(spec.model_identity) != attempt.model_identity_digest:
            raise ValueError(f"{event_id} execution spec identity drifted from its attempt.")
        spec_generation_digest = generation_parameters_digest(spec.generation_parameters)
        if spec_generation_digest != attempt.generation_parameters_digest:
            raise ValueError(
                f"{event_id} execution spec generation parameters drifted from its attempt."
            )
    if item.receipt is not None:
        receipt = model_execution_receipt_from_payload(item.receipt)
        if receipt.model_identity_digest != attempt.model_identity_digest:
            raise ValueError(f"{event_id} receipt identity drifted from its attempt.")
        if receipt.generation_parameters_digest != attempt.generation_parameters_digest:
            raise ValueError(f"{event_id} receipt generation parameters drifted from its attempt.")


def _load_evidence(
    run_root: Path,
) -> tuple[str, str, tuple[CorrectiveReselectionExecutionItem, ...]]:
    """Validate the complete R16 evidence chain and return its sealed inputs."""
    prep = _read_json(run_root / "preparation.json")
    if prep.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ValueError("R16 preparation schema drifted.")
    routed_event_ids = tuple(cast(str, item) for item in prep["routed_event_ids"])
    if routed_event_ids != EXPECTED_EVENT_IDS:
        raise ValueError(f"R16 requires exactly {EXPECTED_EVENT_IDS}, got {routed_event_ids}.")
    source_report_fingerprint = cast(str, prep["source_report_fingerprint"])
    closure_report_fingerprint = cast(str, prep["closure_report_fingerprint"])

    corrective_list = [
        CorrectiveSelectionTask.model_validate(item, strict=False)
        for item in _read_json_list(run_root / "tasks.json")
    ]
    if tuple(task.event_id for task in corrective_list) != routed_event_ids:
        raise ValueError("R16 tasks do not match the routed Events in order.")
    task_by_event = {task.event_id: task for task in corrective_list}

    items: list[CorrectiveReselectionExecutionItem] = []
    for event_id in routed_event_ids:
        attempt = CorrectiveReselectionAttempt.model_validate(
            _read_json(run_root / "attempts" / f"{event_id}.json"), strict=False
        )
        item = CorrectiveReselectionExecutionItem.model_validate(
            _read_json(run_root / "items" / f"{event_id}.json"), strict=False
        )
        _validate_terminal_pair(
            event_id,
            attempt,
            item,
            run_root,
            expected_input_digest=task_by_event[event_id].corrected_prompt_sha256,
        )
        items.append(item)
    return source_report_fingerprint, closure_report_fingerprint, tuple(items)


def _report(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    source_report_fingerprint, closure_report_fingerprint, items = _load_evidence(run_root)
    report = build_corrective_reselection_report(
        source_report_fingerprint=source_report_fingerprint,
        closure_report_fingerprint=closure_report_fingerprint,
        items=items,
    )
    existing = run_root / "report.json"
    if existing.exists():
        sealed = rebuild_corrective_reselection_report(_read_json(existing))
        if sealed.result_fingerprint != report.result_fingerprint:
            raise ValueError("Rebuilt R16 report drifted from the sealed report.")
    _write_json(existing, report.model_dump(mode="json"))
    (run_root / "review.md").write_text(
        _render_review(
            source_report_fingerprint,
            closure_report_fingerprint,
            report,
        ),
        encoding="utf-8",
    )
    status = _terminal_status(items)
    _write_terminal_status(run_root, report, status)
    print(
        json.dumps(
            {
                "status": status,
                "run_root": str(run_root),
                "result_fingerprint": report.result_fingerprint,
                "outcomes": {item.event_id: item.outcome.value for item in report.items},
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
                "proposed_change_count": report.proposed_change_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _show(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    status = _read_json(run_root / "status.json")
    summary: dict[str, Any] = {
        "run_root": str(run_root),
        "status": status.get("status"),
    }
    if (run_root / "report.json").exists():
        source_fp, closure_fp, items = _load_evidence(run_root)
        sealed = rebuild_corrective_reselection_report(_read_json(run_root / "report.json"))
        rebuilt = build_corrective_reselection_report(
            source_report_fingerprint=source_fp,
            closure_report_fingerprint=closure_fp,
            items=items,
        )
        if rebuilt.result_fingerprint != sealed.result_fingerprint:
            raise ValueError("R16 sealed report drifted from its evidence chain.")
        summary["result_fingerprint"] = sealed.result_fingerprint
        summary["terminal_item_count"] = len(sealed.items)
        summary["model_execution_count"] = sealed.model_execution_count
        summary["canonical_write_count"] = sealed.canonical_write_count
        summary["proposed_change_count"] = sealed.proposed_change_count
        summary["outcomes"] = {
            item.event_id: {"outcome": item.outcome.value, "detail": _item_detail(item)}
            for item in sealed.items
        }
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


def _artifacts(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    if (run_root / "report.json").exists():
        _load_evidence(run_root)
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in run_root.rglob("*") if item.is_file()):
        records.append(
            {
                "path": str(path.relative_to(run_root)),
                "sha256": _sha_file(path),
                "bytes": path.stat().st_size,
            }
        )
    print(json.dumps({"run_root": str(run_root), "artifacts": records}, sort_keys=True, indent=2))
    return 0


def _trace(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    event_id = cast(str, args.event_id)
    if event_id not in EXPECTED_EVENT_IDS:
        raise ValueError(f"R16 trace requires one of {EXPECTED_EVENT_IDS}, got {event_id}.")
    prep = _read_json(run_root / "preparation.json")
    if prep.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ValueError("R16 preparation schema drifted.")

    task = CorrectiveSelectionTask.model_validate(
        next(
            item
            for item in _read_json_list(run_root / "tasks.json")
            if item.get("event_id") == event_id
        ),
        strict=False,
    )
    attempt = CorrectiveReselectionAttempt.model_validate(
        _read_json(run_root / "attempts" / f"{event_id}.json"), strict=False
    )
    item = CorrectiveReselectionExecutionItem.model_validate(
        _read_json(run_root / "items" / f"{event_id}.json"), strict=False
    )
    _validate_terminal_pair(
        event_id,
        attempt,
        item,
        run_root,
        expected_input_digest=task.corrected_prompt_sha256,
    )

    completed_answer: str | None = None
    if item.raw_response_sha256 is not None:
        response_bytes = (run_root / "responses" / f"{event_id}.bin").read_bytes()
        try:
            completed_answer = response_bytes.decode("utf-8")
        except UnicodeDecodeError:
            completed_answer = None

    parsed = (
        {
            "status": item.parsed_answer.status.value,
            "selected_label_indexes": list(item.parsed_answer.selected_label_indexes),
        }
        if item.parsed_answer is not None
        else None
    )
    trace: dict[str, Any] = {
        "run_root": str(run_root),
        "event_id": event_id,
        "closure_route": item.closure_route.value,
        "corrected_prompt": task.corrected_prompt,
        "corrected_prompt_sha256": task.corrected_prompt_sha256,
        "completed_answer": completed_answer,
        "raw_response_sha256": item.raw_response_sha256,
        "parsed_answer": parsed,
        "outcome": item.outcome.value,
    }
    if item.error is not None:
        trace["error"] = item.error
    print(json.dumps(trace, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
