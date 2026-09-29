#!/usr/bin/env python3
"""Run the R5 evaluation-remediation held-out transfer evaluation.

Runner phases over one run root: ``prepare`` (model-free bind + derive), ``execute``
(local model selection with Token Probability Evidence), ``score`` (compose + census +
selection scores), and ``report`` (sealed report + review). All inputs and outputs are
explicit paths or a TOML config file; no environment variables are assumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import StanzaLinguisticAnalyzer
from kotekomi_adapters.model_resources import (
    stanza_expected_resource_identity,
    stanza_model_path,
)
from kotekomi_application import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionTask,
    EventEntityLinguisticToken,
    ExecutionSetting,
    HeldOutTransferReport,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    ModelExecutionSpec,
    ModelInputAdmissionRequest,
    ModelTaskRequest,
    SelectionProbabilityReceipt,
    SelectionScore,
    admit_model_input,
    build_held_out_error_census,
    build_held_out_exact_set_score,
    build_held_out_transfer_report,
    build_selection_probability_receipt,
    build_selection_scores,
    parse_constituent_selection_answer,
)
from kotekomi_domain import ModelInputAdmissionStatus
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.evaluation_remediation import (
    HeldOutPropositionGoldCatalog,
    build_held_out_inventories,
    build_held_out_propositions,
    held_out_gold_events,
    load_held_out_proposition_gold,
    render_held_out_selection_tasks,
    verify_held_out_frozen_evidence,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-28-evaluation-remediation.md"
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json"
DEFAULT_FIXTURE = REPOSITORY_ROOT / "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf"
DEFAULT_STANZA_LOCK = (
    REPOSITORY_ROOT / "packages/adapters/src/kotekomi_adapters/stanza-model-lock.json"
)

RUN_SCHEMA_VERSION = "evaluation_remediation_run_v1"
CONSTITUENT_SELECTION_SCHEMA_ID = "constituent_selection_label_v1"
CONSTITUENT_SELECTION_OUTPUT_CONTRACT = "constituent_selection_label_v1"
CONSTITUENT_SELECTION_TASK_TYPE = "constituent_selection"
_CONSTITUENT_SELECTION_PROMPT_BYTES = (
    b"Return a comma-separated subset of the Candidate labels, or NONE.\n"
)
_CONSTITUENT_SELECTION_SCHEMA_BYTES = (
    b"comma-separated subset of the named Candidate labels, or the exact token NONE\n"
)
_CONSTITUENT_SELECTION_SAFETY_MARGIN_TOKENS = 256
TOP_LOGPROBS = 10


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure R5 transfer on the held-out partition.")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    prepare.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    prepare.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    prepare.add_argument("--stanza-lock", type=Path, default=DEFAULT_STANZA_LOCK)

    execute = commands.add_parser("execute")
    execute.add_argument("--config", type=Path, required=True)
    execute.add_argument("--run-root", type=Path, required=True)

    score = commands.add_parser("score")
    score.add_argument("--run-root", type=Path, required=True)

    report = commands.add_parser("report")
    report.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "execute":
        return _execute(args)
    if args.command == "score":
        return _score(args)
    if args.command == "report":
        return _report(args)
    raise ValueError(f"Unsupported R5 command: {args.command}")


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("R5 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)

    verify_held_out_frozen_evidence(
        gold=args.gold.resolve(),
        fixture=args.fixture.resolve(),
        stanza_lock=args.stanza_lock.resolve(),
    )
    config = _config(args.config.resolve())
    catalog = load_held_out_proposition_gold(args.gold.resolve())

    analyzer = StanzaLinguisticAnalyzer(
        model_directory=stanza_model_path(config.model_resource_root),
        resource_identity=stanza_expected_resource_identity(),
    )
    tokens_by_digest = _build_tokens_by_digest(catalog, analyzer)
    inventories = build_held_out_inventories(catalog=catalog, tokens_by_digest=tokens_by_digest)
    tasks = render_held_out_selection_tasks(catalog=catalog, inventories=inventories)

    _write_json(root / "catalog.json", catalog.model_dump(mode="json"))
    _write_json(
        root / "inventories.json",
        [inventories[event.event_id].model_dump(mode="json") for event in catalog.events],
    )
    _write_json(root / "tasks.json", [task.model_dump(mode="json") for task in tasks])
    _write_jsonl(root / "inputs.jsonl", [task.model_dump(mode="json") for task in tasks])
    _write_json(
        root / "tokens.json",
        {
            digest: [token.model_dump(mode="json") for token in tokens]
            for digest, tokens in sorted(tokens_by_digest.items())
        },
    )
    _write_json(
        root / "run.json",
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "prepared",
            "result_fingerprint": None,
            "model_execution_count": 0,
            "canonical_write_count": 0,
            "proposed_change_count": 0,
            "event_count": catalog.event_count,
            "task_count": len(tasks),
            "gold_path": str(args.gold.resolve()),
            "fixture_path": str(args.fixture.resolve()),
            "inputs": {
                "tdd": _sha_file(TDD_PATH),
                "gold": _sha_file(args.gold.resolve()),
                "fixture": _sha_file(args.fixture.resolve()),
                "stanza_lock": _sha_file(args.stanza_lock.resolve()),
            },
            "outputs": {
                "catalog": _sha_file(root / "catalog.json"),
                "inventories": _sha_file(root / "inventories.json"),
                "tasks": _sha_file(root / "tasks.json"),
                "tokens": _sha_file(root / "tokens.json"),
                "inputs": _sha_file(root / "inputs.jsonl"),
            },
        },
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(root),
                "event_count": catalog.event_count,
                "task_count": len(tasks),
                "model_execution_count": 0,
                "canonical_write_count": 0,
                "proposed_change_count": 0,
            },
            sort_keys=True,
        )
    )
    return 0


def _execute(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    _require_schema(metadata, RUN_SCHEMA_VERSION, "R5 run")
    if metadata.get("status") != "prepared":
        raise ValueError("R5 execute requires a run root prepared first.")
    prepared = _load_prepared(root)
    config = _config(args.config.resolve())
    runtime = build_model_task_runtime(config.model_execution)
    readiness = runtime.check_readiness()
    if not readiness.ready:
        _close_runtime(runtime)
        raise RuntimeError(f"R5 model runtime is not ready: {readiness}.")

    profile_id = config.model_execution.profile_name or config.model_execution.adapter
    generation = _selection_generation_parameters(config)
    prompt_digest = _sha_bytes(_CONSTITUENT_SELECTION_PROMPT_BYTES)
    schema_digest = _sha_bytes(_CONSTITUENT_SELECTION_SCHEMA_BYTES)

    answers: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for event_id in sorted(prepared.tasks):
        task = prepared.tasks[event_id]
        rendered_input = task.rendered_input.encode("utf-8")
        if _sha_bytes(rendered_input) != task.rendered_input_sha256:
            raise ValueError(f"R5 rendered task digest drifted for {event_id}.")
        run_id = _deterministic_id("mrn", event_id, task.rendered_input_sha256)
        extraction_task_id = _deterministic_id("ext", event_id, task.rendered_input_sha256)
        manifest_id = _deterministic_id("cxm", event_id, task.rendered_input_sha256)
        manifest_digest = _sha_bytes(
            rendered_input
            + _CONSTITUENT_SELECTION_PROMPT_BYTES
            + _CONSTITUENT_SELECTION_SCHEMA_BYTES
        )
        admission = admit_model_input(
            ModelInputAdmissionRequest(
                model_run_id=run_id,
                extraction_task_id=extraction_task_id,
                model_profile_id=profile_id,
                model_identity=runtime.configured_identity,
                logical_input=rendered_input,
                configured_context_limit=config.model_execution.context_tokens,
                reserved_output_tokens=config.model_execution.max_output_tokens,
                safety_margin_tokens=_CONSTITUENT_SELECTION_SAFETY_MARGIN_TOKENS,
            ),
            runtime,
        )
        if admission.status is not ModelInputAdmissionStatus.READY:
            _close_runtime(runtime)
            raise ValueError(
                f"R5 selection task for {event_id} is blocked by input admission: "
                f"{admission.blocked_reason}."
            )
        spec = ModelExecutionSpec(
            model_profile_id=profile_id,
            model_identity=runtime.configured_identity,
            generation_parameters=generation,
            prompt_id=CONSTITUENT_SELECTION_SCHEMA_ID,
            prompt_digest=prompt_digest,
            schema_id=CONSTITUENT_SELECTION_SCHEMA_ID,
            schema_digest=schema_digest,
            context_manifest_id=manifest_id,
            context_manifest_digest=manifest_digest,
            rendered_input_digest=task.rendered_input_sha256,
            output_contract_version=CONSTITUENT_SELECTION_OUTPUT_CONTRACT,
        )
        response = runtime.run_model_task(
            ModelTaskRequest(
                extraction_task_id=extraction_task_id,
                task_fingerprint=task.rendered_input_sha256,
                task_type=CONSTITUENT_SELECTION_TASK_TYPE,
                context_manifest_id=manifest_id,
                context_manifest_digest=manifest_digest,
                rendered_input=rendered_input,
                rendered_input_digest=task.rendered_input_sha256,
                execution_spec=spec,
                input_admission=admission,
            )
        )
        raw_answer = _decode_raw_answer(response.raw_output)
        parse_constituent_selection_answer(raw_answer=raw_answer, task=task)
        probability_receipt = build_selection_probability_receipt(
            event_id=event_id,
            model_execution_id=run_id,
            receipt=response.execution_receipt,
        )
        answers.append({"event_id": event_id, "raw_answer": raw_answer})
        receipts.append(probability_receipt.model_dump(mode="json"))

    _close_runtime(runtime)
    _write_jsonl(root / "answers.jsonl", answers)
    _write_json(root / "receipts.json", receipts)
    _write_json(
        root / "execute.json",
        {
            "status": "executed",
            "adapter": config.model_execution.adapter,
            "endpoint": config.model_execution.endpoint,
            "model": config.model_execution.model,
            "runtime_ready": readiness.ready,
            "model_available": readiness.model_available,
            "model_execution_count": len(answers),
        },
    )
    _update_run_after_execute(root, model_execution_count=len(answers))
    print(
        json.dumps(
            {
                "status": "executed",
                "run_root": str(root),
                "model_execution_count": len(answers),
                "answers": str(root / "answers.jsonl"),
                "receipts": str(root / "receipts.json"),
            },
            sort_keys=True,
        )
    )
    return 0


def _selection_generation_parameters(
    config: PipelineConfig,
) -> tuple[ExecutionSetting, ...]:
    settings = (
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", TOP_LOGPROBS),
    )
    if tuple(sorted(settings, key=lambda item: item.key)) != settings:
        raise ValueError("R5 selection generation settings are not canonically ordered.")
    return settings


def _update_run_after_execute(root: Path, *, model_execution_count: int) -> None:
    metadata = _read_json(root / "run.json")
    outputs = cast(dict[str, Any], metadata.get("outputs", {}))
    metadata.update(
        {
            "model_execution_count": model_execution_count,
            "outputs": {
                **outputs,
                "answers": _sha_file(root / "answers.jsonl"),
                "receipts": _sha_file(root / "receipts.json"),
            },
        }
    )
    _write_json(root / "run.json", metadata)


def _decode_raw_answer(raw_output: bytes) -> str:
    try:
        text = raw_output.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise ValueError("R5 selection model output must be UTF-8 text.") from error
    return text


def _score(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    prepared = _load_prepared(root)
    metadata = _read_json(root / "run.json")
    _require_schema(metadata, RUN_SCHEMA_VERSION, "R5 run")
    answers = _parse_answers(root, prepared.tasks)
    receipts = _load_receipts(root, prepared.tasks)

    propositions = build_held_out_propositions(
        catalog=prepared.catalog,
        inventories=prepared.lookup,
        answers=answers,
        tokens_by_digest=prepared.tokens_by_digest,
    )
    events = held_out_gold_events(prepared.catalog)
    census = build_held_out_error_census(
        events=events,
        inventories=prepared.lookup,
        answers=answers,
        propositions=propositions,
    )
    exact = build_held_out_exact_set_score(
        events=events,
        inventories=prepared.lookup,
        answers=answers,
    )
    selection_scores = _selection_scores(prepared, receipts)

    _write_json(
        root / "propositions.json",
        [propositions[event.event_id].model_dump(mode="json") for event in prepared.catalog.events],
    )
    _write_json(root / "census.json", census.model_dump(mode="json"))
    _write_json(
        root / "score.json",
        {
            "status": "scored",
            "exact_set_score": exact,
            "selection_scores": [item.model_dump(mode="json") for item in selection_scores],
        },
    )
    print(
        json.dumps(
            {
                "status": "scored",
                "run_root": str(root),
                "event_count": census.event_count,
                "ok_count": census.ok_count,
                "boundary_miss_count": census.boundary_miss_count,
                "selection_error_count": census.selection_error_count,
                "exact_set_score": exact,
                "model_execution_count": metadata.get("model_execution_count", 0),
            },
            sort_keys=True,
        )
    )
    return 0


def _report(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    prepared = _load_prepared(root)
    metadata = _read_json(root / "run.json")
    _require_schema(metadata, RUN_SCHEMA_VERSION, "R5 run")
    answers = _parse_answers(root, prepared.tasks)
    receipts = _load_receipts(root, prepared.tasks)

    propositions = build_held_out_propositions(
        catalog=prepared.catalog,
        inventories=prepared.lookup,
        answers=answers,
        tokens_by_digest=prepared.tokens_by_digest,
    )
    events = held_out_gold_events(prepared.catalog)
    census = build_held_out_error_census(
        events=events,
        inventories=prepared.lookup,
        answers=answers,
        propositions=propositions,
    )
    exact = build_held_out_exact_set_score(
        events=events,
        inventories=prepared.lookup,
        answers=answers,
    )
    selection_scores = _selection_scores(prepared, receipts)
    report = build_held_out_transfer_report(
        census=census,
        exact_set_score=exact,
        selection_scores=selection_scores,
        model_execution_count=cast(int, metadata.get("model_execution_count", 0)),
    )

    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "review.md").write_text(
        _render_review(
            catalog=prepared.catalog,
            propositions=propositions,
            exact_set_score=exact,
            report=report,
        ),
        encoding="utf-8",
    )
    _write_json(
        root / "status.json",
        {
            "status": "complete",
            "run_root": str(root),
            "result_fingerprint": report.result_fingerprint,
            "model_execution_count": report.model_execution_count,
            "canonical_write_count": report.canonical_write_count,
            "proposed_change_count": report.proposed_change_count,
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "run_root": str(root),
                "result_fingerprint": report.result_fingerprint,
                "exact_set_score": report.exact_set_score,
                "boundary_miss_count": report.census.boundary_miss_count,
                "selection_error_count": report.census.selection_error_count,
                "composition_hold_count": report.census.composition_hold_count,
                "content_error_count": report.census.content_error_count,
                "attribution_error_count": report.census.attribution_error_count,
                "polarity_modality_error_count": report.census.polarity_modality_error_count,
                "ok_count": report.census.ok_count,
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
                "proposed_change_count": report.proposed_change_count,
            },
            sort_keys=True,
        )
    )
    return 0


@dataclass(frozen=True)
class _PreparedState:
    catalog: HeldOutPropositionGoldCatalog
    lookup: dict[str, ConstituentCandidateInventory]
    tasks: dict[str, ConstituentSelectionTask]
    tokens_by_digest: dict[str, tuple[EventEntityLinguisticToken, ...]]


def _build_tokens_by_digest(
    catalog: HeldOutPropositionGoldCatalog,
    analyzer: StanzaLinguisticAnalyzer,
) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    sources: dict[str, str] = {}
    for event in catalog.events:
        prior = sources.get(event.source_text_sha256)
        if prior is None:
            sources[event.source_text_sha256] = event.source_text
        elif prior != event.source_text:
            raise ValueError("Held-out Gold repeats a digest with different text.")
    result: dict[str, tuple[EventEntityLinguisticToken, ...]] = {}
    for digest, text in sources.items():
        analysis = analyzer.analyze(LinguisticAnalysisInput(source_text=text))
        if analysis.source_text_sha256 != digest:
            raise ValueError("Stanza analysis digest drifted from its source text.")
        result[digest] = _linguistic_tokens(analysis)
    return result


def _linguistic_tokens(analysis: LinguisticAnalysis) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(
        EventEntityLinguisticToken(
            token_id=item.token_id,
            sentence_id=item.sentence_id,
            text=item.text,
            start=item.start,
            end=item.end,
            lemma=item.lemma,
            part_of_speech=item.part_of_speech.value,
            dependency_relation=item.dependency_relation,
            head_token_id=item.head_token_id,
        )
        for item in analysis.tokens
    )


def _load_prepared(root: Path) -> _PreparedState:
    catalog = HeldOutPropositionGoldCatalog.model_validate_json(
        (root / "catalog.json").read_bytes()
    )
    inventories = tuple(_load_models(ConstituentCandidateInventory, root / "inventories.json"))
    lookup = {item.event_id: item for item in inventories}
    tasks = {
        item.event_id: item for item in _load_models(ConstituentSelectionTask, root / "tasks.json")
    }
    tokens_by_digest = _load_tokens_by_digest(root)
    return _PreparedState(
        catalog=catalog,
        lookup=lookup,
        tasks=tasks,
        tokens_by_digest=tokens_by_digest,
    )


def _load_tokens_by_digest(
    root: Path,
) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    raw = json.loads((root / "tokens.json").read_bytes())
    if not isinstance(raw, dict):
        raise ValueError("R5 tokens.json must be one JSON object.")
    return {
        digest: tuple(EventEntityLinguisticToken.model_validate(item) for item in items)
        for digest, items in cast(dict[str, list[object]], raw).items()
    }


def _parse_answers(
    root: Path,
    tasks: dict[str, ConstituentSelectionTask],
) -> dict[str, ConstituentSelectionAnswer]:
    answers_path = root / "answers.jsonl"
    if not answers_path.exists():
        raise ValueError("R5 requires answers.jsonl before scoring; run execute first.")
    answers: dict[str, ConstituentSelectionAnswer] = {}
    for line, payload in enumerate(_read_jsonl(answers_path), start=1):
        event_id = payload.get("event_id")
        raw_answer = payload.get("raw_answer")
        if not isinstance(event_id, str) or not isinstance(raw_answer, str):
            raise ValueError(f"answers.jsonl line {line} is not a valid finite answer record.")
        if event_id not in tasks:
            raise ValueError(f"answers.jsonl line {line} names an unknown Event: {event_id}.")
        answers[event_id] = parse_constituent_selection_answer(
            raw_answer=raw_answer, task=tasks[event_id]
        )
    if set(answers) != set(tasks):
        raise ValueError("R5 answers.jsonl must answer every rendered task exactly once.")
    return answers


def _load_receipts(
    root: Path,
    tasks: dict[str, ConstituentSelectionTask],
) -> dict[str, SelectionProbabilityReceipt]:
    receipts_path = root / "receipts.json"
    if not receipts_path.exists():
        raise ValueError("R5 requires receipts.json; run execute first.")
    receipts: dict[str, SelectionProbabilityReceipt] = {}
    for item in _load_models(SelectionProbabilityReceipt, receipts_path):
        if item.event_id not in tasks:
            raise ValueError(f"R5 receipts reference an unknown Event: {item.event_id}.")
        receipts[item.event_id] = item
    if set(receipts) != set(tasks):
        raise ValueError("R5 receipts must cover every rendered task exactly once.")
    return receipts


def _selection_scores(
    prepared: _PreparedState,
    receipts: dict[str, SelectionProbabilityReceipt],
) -> tuple[SelectionScore, ...]:
    scores: list[SelectionScore] = []
    for event in sorted(prepared.catalog.events, key=lambda item: item.event_id):
        task = prepared.tasks[event.event_id]
        scores.extend(
            build_selection_scores(
                event_id=event.event_id,
                allowed_labels=task.constituent_labels,
                receipt=receipts[event.event_id],
            )
        )
    return tuple(scores)


def _render_review(
    *,
    catalog: HeldOutPropositionGoldCatalog,
    propositions: Mapping[str, Any],
    exact_set_score: float,
    report: HeldOutTransferReport,
) -> str:
    census = report.census
    lines = [
        "# R5 Evaluation Remediation",
        "",
        f"Model executions: {report.model_execution_count}.",
        f"Canonical writes: {report.canonical_write_count}.",
        f"ProposedChanges: {report.proposed_change_count}.",
        "",
        "## Census",
        "",
        f"- exact-set score: `{exact_set_score:.6f}` (recorded only, not a gate)",
        f"- ok: `{census.ok_count}`",
        f"- boundary_miss: `{census.boundary_miss_count}`",
        f"- selection_error: `{census.selection_error_count}`",
        f"- composition_hold: `{census.composition_hold_count}`",
        f"- content_error: `{census.content_error_count}`",
        f"- attribution_error: `{census.attribution_error_count}`",
        f"- polarity_modality_error: `{census.polarity_modality_error_count}`",
        "",
        f"Boundary-miss fragments: {', '.join(census.boundary_miss_fragment_ids) or 'none'}.",
        "",
        "## Events",
        "",
    ]
    for event in sorted(catalog.events, key=lambda item: item.event_id):
        lines.append(f"### {event.event_id}")
        lines.append("")
        lines.append(f"- meaning: {event.event_meaning}")
        proposition = propositions[event.event_id]
        lines.append(f"- status: `{proposition.status.value}`")
        if proposition.status.value == "held":
            hold_reason = proposition.hold_reason
            lines.append(f"- hold reason: `{hold_reason.value if hold_reason else 'unknown'}`")
        else:
            lines.append(f"- relation: `{proposition.relation_label}`")
        lines.append("")
    return "\n".join(lines)


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _require_schema(value: dict[str, Any], expected: str, label: str) -> None:
    if value.get("schema_version") != expected:
        raise ValueError(f"{label} schema drifted: {value.get('schema_version')!r}.")


def _load_models(model: type[Any], path: Path) -> tuple[Any, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    return tuple(
        model.model_validate_json(_canonical_json(item)) for item in cast(list[object], value)
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected one JSON object per line: {path}.")
        records.append(cast(dict[str, Any], value))
    return records


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Sequence[object]) -> None:
    path.write_text(
        "\n".join(_canonical_json(item).decode() for item in values) + "\n",
        encoding="utf-8",
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


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


if __name__ == "__main__":
    raise SystemExit(main())
