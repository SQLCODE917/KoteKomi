#!/usr/bin/env python3
"""Run the R18 semantic instruction discrimination experiment.

R18 measures whether naming the eligibility rule and the complete-selected-set
rules improves the three instruction-sensitive signals over the format-only
instruction, across the 11 frozen R17 reference policy records and two variants
per record.  Runner phases over one run root:

* ``prepare`` -- model-free.  Loads the frozen R17 contract and its 11 reference
  policy records, verifies the frozen four-digest contract binding, renders the
  two prompts per record, and binds the run to the frozen R6 runtime
  configuration.  It writes no canonical state and no ProposedChanges.
* ``execute`` -- admits each of the 22 prompts through the tokenizer contract,
  runs the model at most once per pair, and archives every raw response and
  execution receipt, recording a terminal ``answered``, ``blocked``, or
  ``failed`` outcome per pair.
* ``report`` -- rebuilds the sealed report deterministically from the archived
  responses without another model call.
* ``show`` -- prints the validated report fingerprint, the per-signal counts, and
  the predeclared verdict.

All inputs and outputs are explicit paths or a TOML config file; no environment
variables are assumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from kotekomi_application import (
    DiscriminationExecutionBinding,
    DiscriminationExecutionRequest,
    DiscriminationObservationItem,
    DiscriminationPreparedPrompt,
    ExecutionSetting,
    ReferencePolicyRecord,
    build_discrimination_report,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
    rebuild_discrimination_item,
    rebuild_discrimination_report,
    render_discrimination_prompts,
    run_discrimination_attempt,
    verify_contract_binding,
)
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from pydantic import BaseModel, ConfigDict, Field

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPOSITORY_ROOT / "data/r17-semantic-selection-contract"
DEFAULT_RUN_ROOT = REPOSITORY_ROOT / "data/r18-semantic-instruction-discrimination-runs/run-001"
DEFAULT_CONFIG = REPOSITORY_ROOT / "docs/r6-calibrated-residual-ownership-run-config.toml"

RUN_SCHEMA_VERSION = "semantic_instruction_discrimination_run_v1"
PROMPT_ID = "semantic_instruction_discrimination_prompt_v1"
SCHEMA_ID = "semantic_instruction_discrimination_schema_v1"
OUTPUT_CONTRACT_VERSION = "constituent_selection_label_v1"
_PROMPT_BYTES = b"Render one constituent selection answer per instruction variant.\n"
_SCHEMA_BYTES = (
    b"comma-separated Candidate labels, or the exact token NONE for the best-choice route\n"
)
SAFETY_MARGIN_TOKENS = 256
REQUIRED_ADAPTER = "lm_studio"
REQUIRED_MODEL = "qwen2.5-14b-instruct"


class _PreparedModelExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    adapter: Literal["lm_studio"]
    endpoint: Annotated[str, Field(min_length=1)]
    model: Literal["qwen2.5-14b-instruct"]
    profile_name: Annotated[str, Field(min_length=1)]
    timeout_seconds: Annotated[float, Field(gt=0)]
    context_tokens: Annotated[int, Field(gt=0)]
    max_output_tokens: Annotated[int, Field(gt=0)]


class _Preparation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["semantic_instruction_discrimination_run_v1"]
    contract_version: Annotated[int, Field(ge=1)]
    model_execution: _PreparedModelExecution
    record_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class _PreparedState:
    schema_version: str
    contract_version: int
    adapter: str
    endpoint: str
    model: str
    profile_name: str
    timeout_seconds: float
    context_tokens: int
    max_output_tokens: int
    records: tuple[ReferencePolicyRecord, ...]
    prompts: tuple[DiscriminationPreparedPrompt, ...]


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _generation_parameters(max_output_tokens: int) -> tuple[ExecutionSetting, ...]:
    settings = (
        ExecutionSetting("max_output_tokens", max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )
    if tuple(sorted(settings, key=lambda item: item.key)) != settings:
        raise ValueError("R18 generation settings are not canonically ordered.")
    return settings


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


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _deterministic_id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{_sha_bytes(('\x1f'.join(parts)).encode('utf-8'))[:24]}"


def _close_runtime(runtime: Any) -> None:
    close = getattr(runtime, "close", None)
    if callable(close):
        close()


def _raw_policy_records(directory: Path) -> list[Any]:
    document = _read_json(directory / "reference_policy_records.json")
    records = document.get("records")
    if not isinstance(records, list):
        raise ValueError("R17 reference policy records are missing their records list.")
    return cast(list[Any], records)


def _load_contract_and_records(
    directory: Path,
) -> tuple[Any, tuple[ReferencePolicyRecord, ...]]:
    contract = frozen_semantic_selection_contract(directory=directory)
    records_raw = _raw_policy_records(directory)
    verify_contract_binding(contract=contract, records=records_raw)
    records = load_reference_policy_records(contract=contract, directory=directory)
    return contract, records


def _render_all_prompts(
    contract: Any, records: tuple[ReferencePolicyRecord, ...]
) -> tuple[DiscriminationPreparedPrompt, ...]:
    prompts: list[DiscriminationPreparedPrompt] = []
    for record in records:
        input_path = (REPOSITORY_ROOT / record.input_binding.input_file.path).resolve()
        if not input_path.is_relative_to(REPOSITORY_ROOT):
            raise ValueError("R18 frozen input handle escapes the repository.")
        format_prompt, semantic_prompt = render_discrimination_prompts(
            record=record, contract=contract, frozen_input=input_path.read_bytes()
        )
        prompts.extend((format_prompt, semantic_prompt))
    ordered = tuple(sorted(prompts, key=lambda prompt: prompt.pair_id))
    if len(ordered) != 2 * len(records):
        raise ValueError("R18 must render exactly two prompts per record.")
    return ordered


def _require_status(run_root: Path, expected: str) -> None:
    status = _read_json(run_root / "status.json")
    if status.get("status") != expected:
        raise ValueError(f"R18 requires a '{expected}' run before this command: {run_root}.")


def _prepare(args: argparse.Namespace) -> int:
    config = _config(args.config)
    run_root = args.run_root.resolve()
    if (run_root / "preparation.json").exists():
        raise ValueError("R18 run root is already prepared; use a new run root.")
    run_root.mkdir(parents=True, exist_ok=True)

    contract, records = _load_contract_and_records(DATA_DIR)
    prompts = _render_all_prompts(contract, records)

    model_execution = config.model_execution
    if model_execution.adapter != REQUIRED_ADAPTER:
        raise ValueError(
            f"R18 requires the {REQUIRED_ADAPTER} adapter, got {model_execution.adapter}."
        )
    if model_execution.model != REQUIRED_MODEL:
        raise ValueError(f"R18 requires the {REQUIRED_MODEL} model, got {model_execution.model}.")

    profile_name = model_execution.profile_name or model_execution.adapter
    preparation = _Preparation.model_validate_json(
        json.dumps(
            {
                "schema_version": RUN_SCHEMA_VERSION,
                "contract_version": contract.version,
                "model_execution": {
                    "adapter": model_execution.adapter,
                    "endpoint": model_execution.endpoint,
                    "model": model_execution.model,
                    "profile_name": profile_name,
                    "timeout_seconds": model_execution.timeout_seconds,
                    "context_tokens": model_execution.context_tokens,
                    "max_output_tokens": model_execution.max_output_tokens,
                },
                "record_event_ids": [record.event_id for record in records],
            }
        )
    )
    _write_json(run_root / "preparation.json", preparation.model_dump(mode="json"))
    _write_json(
        run_root / "prompts.json",
        [prompt.model_dump(mode="json") for prompt in prompts],
    )
    _write_json(
        run_root / "status.json",
        {"status": "prepared", "run_root": str(run_root)},
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(run_root),
                "contract_version": contract.version,
                "prompt_count": len(prompts),
            },
            sort_keys=True,
        )
    )
    return 0


def _load_prepared_state(run_root: Path) -> _PreparedState:
    prep = _Preparation.model_validate_json((run_root / "preparation.json").read_bytes())
    model_execution = prep.model_execution
    contract, records = _load_contract_and_records(DATA_DIR)
    if prep.contract_version != contract.version:
        raise ValueError("R18 prepared contract version drifted from the frozen contract.")
    if prep.record_event_ids != tuple(record.event_id for record in records):
        raise ValueError("R18 prepared records drifted from the frozen records.")
    prompts = tuple(
        DiscriminationPreparedPrompt.model_validate(item, strict=False)
        for item in _read_json_list(run_root / "prompts.json")
    )
    if prompts != _render_all_prompts(contract, records):
        raise ValueError("R18 prepared prompts drifted from the frozen render.")

    return _PreparedState(
        schema_version=RUN_SCHEMA_VERSION,
        contract_version=prep.contract_version,
        adapter=model_execution.adapter,
        endpoint=model_execution.endpoint,
        model=model_execution.model,
        profile_name=model_execution.profile_name,
        timeout_seconds=model_execution.timeout_seconds,
        context_tokens=model_execution.context_tokens,
        max_output_tokens=model_execution.max_output_tokens,
        records=records,
        prompts=prompts,
    )


def _rehydrate(run_root: Path, config: PipelineConfig) -> _PreparedState:
    state = _load_prepared_state(run_root)
    candidate = config.model_execution
    if (
        state.adapter != candidate.adapter
        or state.endpoint != candidate.endpoint
        or state.model != candidate.model
        or state.profile_name != (candidate.profile_name or candidate.adapter)
        or state.timeout_seconds != candidate.timeout_seconds
        or state.context_tokens != candidate.context_tokens
        or state.max_output_tokens != candidate.max_output_tokens
    ):
        raise ValueError("R18 execute config drifted from the prepared model binding.")
    return state


def _execute_one(
    *,
    prompt: DiscriminationPreparedPrompt,
    record: ReferencePolicyRecord,
    state: _PreparedState,
    runtime: Any,
    run_root: Path,
    profile_id: str,
    generation: tuple[ExecutionSetting, ...],
    prompt_digest: str,
    schema_digest: str,
) -> Any:
    observation_id = _deterministic_id("obs", prompt.pair_id, prompt.prompt_sha256)
    model_run_id = _deterministic_id("mrn", prompt.pair_id, prompt.prompt_sha256)
    extraction_task_id = _deterministic_id("ext", prompt.pair_id, prompt.prompt_sha256)
    context_manifest_id = _deterministic_id("cxm", prompt.pair_id, prompt.prompt_sha256)
    context_manifest_digest = _sha_bytes(
        prompt.prompt.encode("utf-8") + _PROMPT_BYTES + _SCHEMA_BYTES
    )

    def store_response(raw_output: bytes) -> str:
        path = run_root / "responses" / f"{prompt.pair_id}.bin"
        path.write_bytes(raw_output)
        return _sha_bytes(raw_output)

    request = DiscriminationExecutionRequest(
        observation_id=observation_id,
        event_id=prompt.event_id,
        route=prompt.route,
        variant=prompt.variant,
        prompt=prompt.prompt,
        prompt_sha256=prompt.prompt_sha256,
        prepared_prompt=prompt,
        task=record.task,
        policy_record=record,
        model_profile_id=profile_id,
        model_identity=runtime.configured_identity,
        generation_parameters=generation,
        model_run_id=model_run_id,
        extraction_task_id=extraction_task_id,
        configured_context_limit=state.context_tokens,
        reserved_output_tokens=state.max_output_tokens,
        safety_margin_tokens=SAFETY_MARGIN_TOKENS,
        prompt_id=PROMPT_ID,
        prompt_digest=prompt_digest,
        schema_id=SCHEMA_ID,
        schema_digest=schema_digest,
        context_manifest_id=context_manifest_id,
        context_manifest_digest=context_manifest_digest,
        output_contract_version=OUTPUT_CONTRACT_VERSION,
    )
    item = run_discrimination_attempt(request, runtime=runtime, store_response=store_response)
    _write_json(run_root / "items" / f"{prompt.pair_id}.json", item.model_dump(mode="json"))
    return item


def _execute(args: argparse.Namespace) -> int:
    config = _config(args.config)
    run_root = args.run_root.resolve()
    state = _rehydrate(run_root, config)
    _require_status(run_root, "prepared")

    runtime = build_model_task_runtime(config.model_execution)
    readiness = runtime.check_readiness()
    if not readiness.ready:
        _close_runtime(runtime)
        raise RuntimeError(
            f"R18 model runtime is not ready: adapter={readiness.adapter!r}, "
            f"model={readiness.model!r}, available={readiness.model_available}."
        )

    profile_id = state.profile_name
    generation = _generation_parameters(state.max_output_tokens)
    execution_binding = DiscriminationExecutionBinding(
        model_identity=runtime.configured_identity,
        generation_parameters=generation,
    )
    if (
        execution_binding.model_identity.name != state.model
        or execution_binding.model_identity.runtime != state.adapter
    ):
        _close_runtime(runtime)
        raise ValueError("R18 runtime identity differs from its prepared model binding.")
    _write_json(run_root / "execution.json", execution_binding.model_dump(mode="json"))
    prompt_digest = _sha_bytes(_PROMPT_BYTES)
    schema_digest = _sha_bytes(_SCHEMA_BYTES)

    for directory in ("responses", "items"):
        (run_root / directory).mkdir(exist_ok=True)
    _write_json(run_root / "status.json", {"status": "running", "run_root": str(run_root)})

    record_by_event = {record.event_id: record for record in state.records}
    try:
        for prompt in state.prompts:
            _execute_one(
                prompt=prompt,
                record=record_by_event[prompt.event_id],
                state=state,
                runtime=runtime,
                run_root=run_root,
                profile_id=profile_id,
                generation=generation,
                prompt_digest=prompt_digest,
                schema_digest=schema_digest,
            )
    finally:
        _close_runtime(runtime)

    contract, records = _load_contract_and_records(DATA_DIR)
    verified_items = _load_evidence(run_root)
    report = build_discrimination_report(contract=contract, records=records, items=verified_items)
    _write_json(run_root / "report.json", report.model_dump(mode="json"))
    status = "complete" if report.comparison_complete else "incomplete"
    _write_json(
        run_root / "status.json",
        {
            "status": status,
            "run_root": str(run_root),
            "result_fingerprint": report.result_fingerprint,
            "model_execution_count": report.model_execution_count,
            "canonical_write_count": report.canonical_write_count,
            "proposed_change_count": report.proposed_change_count,
        },
    )
    print(
        json.dumps(
            {
                "status": status,
                "run_root": str(run_root),
                "result_fingerprint": report.result_fingerprint,
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
                "proposed_change_count": report.proposed_change_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _load_evidence(run_root: Path) -> tuple[DiscriminationObservationItem, ...]:
    state = _load_prepared_state(run_root)
    binding = DiscriminationExecutionBinding.model_validate_json(
        (run_root / "execution.json").read_bytes()
    )
    if (
        binding.model_identity.name != state.model
        or binding.model_identity.runtime != state.adapter
    ):
        raise ValueError("R18 execution identity differs from its prepared model binding.")
    if binding.generation_parameters != _generation_parameters(state.max_output_tokens):
        raise ValueError("R18 execution settings differ from its prepared model binding.")
    record_by_event = {record.event_id: record for record in state.records}
    items: list[DiscriminationObservationItem] = []
    for prompt in state.prompts:
        item = DiscriminationObservationItem.model_validate(
            _read_json(run_root / "items" / f"{prompt.pair_id}.json"), strict=False
        )
        response_path = run_root / "responses" / f"{prompt.pair_id}.bin"
        items.append(
            rebuild_discrimination_item(
                prepared=prompt,
                policy_record=record_by_event[prompt.event_id],
                item=item,
                raw_response=response_path.read_bytes() if response_path.exists() else None,
                execution_binding=binding,
            )
        )
    return tuple(items)


def _report(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    contract, records = _load_contract_and_records(DATA_DIR)
    items = _load_evidence(run_root)
    report = build_discrimination_report(contract=contract, records=records, items=items)
    existing = run_root / "report.json"
    if existing.exists():
        sealed = rebuild_discrimination_report(_read_json(existing))
        if sealed.result_fingerprint != report.result_fingerprint:
            raise ValueError("Rebuilt R18 report drifted from the sealed report.")
    _write_json(existing, report.model_dump(mode="json"))
    status = "complete" if report.comparison_complete else "incomplete"
    _write_json(
        run_root / "status.json",
        {
            "status": status,
            "run_root": str(run_root),
            "result_fingerprint": report.result_fingerprint,
            "model_execution_count": report.model_execution_count,
            "canonical_write_count": report.canonical_write_count,
            "proposed_change_count": report.proposed_change_count,
        },
    )
    print(
        json.dumps(
            {
                "status": status,
                "run_root": str(run_root),
                "result_fingerprint": report.result_fingerprint,
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
        report = rebuild_discrimination_report(_read_json(run_root / "report.json"))
        summary.update(
            {
                "result_fingerprint": report.result_fingerprint,
                "comparison_complete": report.comparison_complete,
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
                "proposed_change_count": report.proposed_change_count,
                "signal_comparisons": [
                    {
                        "signal": comparison.signal.value,
                        "group": comparison.group.value,
                        "verdict": comparison.verdict.value,
                        "denominator": comparison.denominator,
                        "format_value_counts": comparison.format_value_counts,
                        "semantic_value_counts": comparison.semantic_value_counts,
                    }
                    for comparison in report.signal_comparisons
                ],
            }
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure R18 semantic instruction discrimination on the frozen R17 records."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    prepare.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    execute = commands.add_parser("execute")
    execute.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    execute.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    report = commands.add_parser("report")
    report.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    show = commands.add_parser("show")
    show.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "execute":
        return _execute(args)
    if args.command == "report":
        return _report(args)
    if args.command == "show":
        return _show(args)
    raise ValueError(f"Unsupported R18 command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
