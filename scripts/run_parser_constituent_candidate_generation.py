#!/usr/bin/env python3
"""Run the R3 parser-constituent candidate generation pipeline.

This runner exposes four phases over one run root:

- ``prepare``: model-free.  It binds the frozen Proposition Gold, trigger Gold,
  connection Gold, and pinned Stanza runtime by SHA-256; re-derives the
  Corrected Attachment Gold with the R2 splitter; runs Stanza once per unique
  SourceSegment to derive dependency tokens; builds one Constituent Candidate
  Inventory per Event; measures Boundary Fidelity; and renders one finite
  selection task per Event.  It writes derived evidence only and changes no
  canonical state.

- ``execute``: the local-model phase.  It verifies the configured runtime is
  reachable before running one finite selection per Event.  Each rendered task
  is admitted through model input admission, executed through the
  ``ModelTaskRuntime`` Port under a pinned ``ModelExecutionSpec``, and its raw
  finite answer is validated with the selection parser before being written to
  ``answers.jsonl``.  No model output enters accepted state.

- ``score``: model-free.  It parses the finite answers in ``answers.jsonl``
  through the selection parser and scores each partition against the corrected
  Gold Attachment Set.

- ``report``: model-free.  It seals the Constituent Selection Report (fidelity
  and selection censuses), renders the Markdown review, and records the final
  run status with zero canonical writes and zero ProposedChanges.

All inputs and outputs are explicit paths or a TOML config file.  No
environment variables are assumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
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
    CorrectedAttachmentGold,
    EventEntityLinguisticToken,
    ExecutionSetting,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    ModelExecutionSpec,
    ModelInputAdmissionRequest,
    ModelTaskRequest,
    admit_model_input,
    parse_constituent_selection_answer,
)
from kotekomi_application.context_planning import derive_source_copy_view
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_domain import ModelInputAdmissionStatus
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    TriggerGoldEvent,
    TriggerGoldSegment,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from kotekomi_pipelines.parser_constituent_candidate_generation import (
    EventConstituentContract,
    build_event_inventories,
    build_partition_fidelity_censuses,
    build_partition_selection_censuses,
    build_r3_constituent_selection_report,
    derive_event_constituent_contracts,
    inventory_lookup,
    rederive_corrected_attachment_gold,
    render_constituent_selection_review,
    render_event_selection_tasks,
    verify_frozen_evidence_digests,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    load_proposition_gold_catalog,
)
from kotekomi_pipelines.trigger_containment_candidate_split import corrected_gold_file_bytes

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
DEFAULT_TRIGGER_GOLD = REPOSITORY_ROOT / "docs/hsq-event-trigger-gold-v1.json"
DEFAULT_CONNECTION_GOLD = REPOSITORY_ROOT / "docs/hsq-event-entity-connection-gold-v2.json"
DEFAULT_STANZA_LOCK = (
    REPOSITORY_ROOT / "packages/adapters/src/kotekomi_adapters/stanza-model-lock.json"
)
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-25-parser-constituent-candidate-generation.md"

RUN_SCHEMA_VERSION = "parser_constituent_candidate_generation_run_v1"
STATUS_SCHEMA_VERSION = "parser_constituent_candidate_generation_status_v1"
CORRECTED_GOLD_FILENAME = "corrected-gold.json"

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


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    prepare.add_argument("--trigger-gold", type=Path, default=DEFAULT_TRIGGER_GOLD)
    prepare.add_argument("--connection-gold", type=Path, default=DEFAULT_CONNECTION_GOLD)
    prepare.add_argument("--stanza-lock", type=Path, default=DEFAULT_STANZA_LOCK)
    prepare.add_argument("--run-root", type=Path, required=True)

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
    raise ValueError(f"Unsupported R3 command: {args.command}")


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("R3 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    verify_frozen_evidence_digests(
        proposition_gold=args.gold.resolve(),
        trigger_gold=args.trigger_gold.resolve(),
        connection_gold=args.connection_gold.resolve(),
        stanza_lock=args.stanza_lock.resolve(),
    )
    config = _config(args.config)
    catalog = load_proposition_gold_catalog(args.gold.resolve(), repository_root=REPOSITORY_ROOT)
    if catalog.review_status.value != "approved":
        raise ValueError("R3 requires approved Proposition Gold.")
    trigger_gold = TriggerGoldCatalog.model_validate_json(args.trigger_gold.read_bytes())

    corrected = rederive_corrected_attachment_gold(
        catalog=catalog,
        trigger_gold=trigger_gold,
        source_catalog_sha256=_sha_file(args.gold.resolve()),
    )
    corrected_bytes = corrected_gold_file_bytes(catalog=catalog, corrected=corrected)
    corrected_path = root / CORRECTED_GOLD_FILENAME

    analyzer = StanzaLinguisticAnalyzer(
        model_directory=stanza_model_path(config.model_resource_root),
        resource_identity=stanza_expected_resource_identity(),
    )
    tokens_by_digest = _build_tokens_by_digest(catalog, analyzer)
    expressions, literals = _event_expressions_and_literals(trigger_gold, catalog)

    contracts = derive_event_constituent_contracts(
        catalog=catalog,
        tokens_by_digest=tokens_by_digest,
        expressions_by_event=expressions,
        literals_by_event=literals,
    )
    inventories = build_event_inventories(contracts)
    lookup = inventory_lookup(inventories)
    development_fidelity, validation_fidelity = build_partition_fidelity_censuses(
        catalog=catalog, inventories=lookup
    )
    tasks = render_event_selection_tasks(contracts=contracts, inventories=lookup)

    corrected_path.write_bytes(corrected_bytes)
    _write_json(root / "catalog.json", catalog.model_dump(mode="json"))
    _write_json(root / "contracts.json", [_contract_payload(item) for item in contracts])
    _write_json(root / "inventories.json", [item.model_dump(mode="json") for item in inventories])
    _write_json(
        root / "fidelity.json",
        {
            "development": development_fidelity.model_dump(mode="json"),
            "validation": validation_fidelity.model_dump(mode="json"),
        },
    )
    _write_json(root / "tasks.json", [item.model_dump(mode="json") for item in tasks])
    _write_jsonl(root / "inputs.jsonl", [item.model_dump(mode="json") for item in tasks])

    _write_json(
        root / "config.json",
        {
            "adapter": config.model_execution.adapter,
            "endpoint": config.model_execution.endpoint,
            "model": config.model_execution.model,
            "context_tokens": config.model_execution.context_tokens,
            "max_output_tokens": config.model_execution.max_output_tokens,
            "timeout_seconds": config.model_execution.timeout_seconds,
            "model_resource_root": str(config.model_resource_root),
            "stanza_lock": str(args.stanza_lock.resolve()),
            "stanza_lock_sha256": _sha_file(args.stanza_lock.resolve()),
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
            "event_count": len(catalog.events),
            "task_count": len(tasks),
            "gold_path": str(args.gold.resolve()),
            "trigger_gold_path": str(args.trigger_gold.resolve()),
            "connection_gold_path": str(args.connection_gold.resolve()),
            "inputs": {
                "tdd": _sha_file(TDD_PATH),
                "proposition_gold": _sha_file(args.gold.resolve()),
                "trigger_gold": _sha_file(args.trigger_gold.resolve()),
                "connection_gold": _sha_file(args.connection_gold.resolve()),
                "stanza_lock": _sha_file(args.stanza_lock.resolve()),
            },
            "outputs": {
                "corrected_gold": _sha_bytes(corrected_bytes),
                "catalog": _sha_file(root / "catalog.json"),
                "contracts": _sha_file(root / "contracts.json"),
                "inventories": _sha_file(root / "inventories.json"),
                "fidelity": _sha_file(root / "fidelity.json"),
                "tasks": _sha_file(root / "tasks.json"),
                "inputs": _sha_file(root / "inputs.jsonl"),
            },
        },
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "run_root": str(root),
                "corrected_gold": str(corrected_path),
                "corrected_gold_sha256": _sha_bytes(corrected_bytes),
                "event_count": len(catalog.events),
                "task_count": len(tasks),
                "development_pool_ceiling": development_fidelity.pool_ceiling,
                "validation_pool_ceiling": validation_fidelity.pool_ceiling,
                "development_covered": len(development_fidelity.covered_fragment_ids),
                "development_missed": len(development_fidelity.missed_fragments),
                "validation_covered": len(validation_fidelity.covered_fragment_ids),
                "validation_missed": len(validation_fidelity.missed_fragments),
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
    _require_schema(metadata, RUN_SCHEMA_VERSION, "R3 run")
    if metadata.get("status") != "prepared":
        raise ValueError("R3 execute requires a run root prepared first.")
    prepared = _load_prepared(root)
    config = _config(args.config)
    runtime = build_model_task_runtime(config.model_execution)
    readiness = runtime.check_readiness()
    if not readiness.ready:
        _close_runtime(runtime)
        raise RuntimeError(f"R3 model runtime is not ready: {readiness}.")

    profile_id = config.model_execution.profile_name or config.model_execution.adapter
    generation = _selection_generation_parameters(config)
    prompt_digest = _sha_bytes(_CONSTITUENT_SELECTION_PROMPT_BYTES)
    schema_digest = _sha_bytes(_CONSTITUENT_SELECTION_SCHEMA_BYTES)

    answers: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for event_id in sorted(prepared.tasks):
        task = prepared.tasks[event_id]
        rendered_input = task.rendered_input.encode("utf-8")
        if _sha_bytes(rendered_input) != task.rendered_input_sha256:
            raise ValueError(f"R3 rendered task digest drifted for {event_id}.")
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
                f"R3 selection task for {event_id} is blocked by input admission: "
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
        answer = parse_constituent_selection_answer(raw_answer=raw_answer, task=task)
        answers.append({"event_id": event_id, "raw_answer": raw_answer})
        diagnostics.append(
            {
                "event_id": event_id,
                "model_run_id": run_id,
                "admission_id": admission.id,
                "selection_status": answer.status.value,
                "selected_label_indexes": list(answer.selected_label_indexes),
            }
        )
    _close_runtime(runtime)
    _write_jsonl(root / "answers.jsonl", answers)
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
            "diagnostics": diagnostics,
        },
    )
    _update_run_after_execute(root, model_execution_count=len(answers))
    print(
        json.dumps(
            {
                "status": "executed",
                "run_root": str(root),
                "model_execution_count": len(answers),
                "answer_count": len(answers),
                "answers": str(root / "answers.jsonl"),
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
    )
    if tuple(sorted(settings, key=lambda item: item.key)) != settings:
        raise ValueError("R3 selection generation settings are not canonically ordered.")
    return settings


def _update_run_after_execute(root: Path, *, model_execution_count: int) -> None:
    metadata = _read_json(root / "run.json")
    outputs = cast(dict[str, Any], metadata.get("outputs", {}))
    metadata.update(
        {
            "model_execution_count": model_execution_count,
            "outputs": {**outputs, "answers": _sha_file(root / "answers.jsonl")},
        }
    )
    _write_json(root / "run.json", metadata)


def _decode_raw_answer(raw_output: bytes) -> str:
    try:
        text = raw_output.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise ValueError("R3 selection model output must be UTF-8 text.") from error
    return text


def _score(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    prepared = _load_prepared(root)
    answers = _parse_answers(root, prepared.tasks)
    corrected, selection_bytes = _corrected_attachment_gold(root)
    development_selection, validation_selection = build_partition_selection_censuses(
        catalog=prepared.catalog,
        inventories=prepared.lookup,
        answers=answers,
        corrected=corrected,
    )
    _write_json(
        root / "selection-answers.json",
        [item.model_dump(mode="json") for item in answers.values()],
    )
    _write_json(
        root / "selection-census.json",
        {
            "development": development_selection.model_dump(mode="json"),
            "validation": validation_selection.model_dump(mode="json"),
        },
    )
    print(
        json.dumps(
            {
                "status": "scored",
                "run_root": str(root),
                "answer_count": len(answers),
                "corrected_gold_sha256": _sha_bytes(selection_bytes),
                "development": _selection_summary(development_selection),
                "validation": _selection_summary(validation_selection),
            },
            sort_keys=True,
        )
    )
    return 0


def _report(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    prepared = _load_prepared(root)
    answers = _parse_answers(root, prepared.tasks)
    corrected, selection_bytes = _corrected_attachment_gold(root)
    report = build_r3_constituent_selection_report(
        catalog=prepared.catalog,
        inventories=prepared.lookup,
        answers=answers,
        corrected=corrected,
        corrected_gold_sha256=_sha_bytes(selection_bytes),
        model_execution_count=len(answers),
    )
    report_path = root / "report.json"
    review_path = root / "review.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_constituent_selection_review(report=report), encoding="utf-8")
    _write_json(
        root / "status.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "status": "complete",
            "result_fingerprint": report.result_fingerprint,
            "model_execution_count": report.model_execution_count,
            "canonical_write_count": report.canonical_write_count,
            "proposed_change_count": report.proposed_change_count,
            "report": str(report_path),
            "review": str(review_path),
        },
    )
    metadata = _read_json(root / "run.json")
    outputs = cast(dict[str, Any], metadata.get("outputs", {}))
    metadata.update(
        {
            "status": "complete",
            "result_fingerprint": report.result_fingerprint,
            "model_execution_count": report.model_execution_count,
            "canonical_write_count": report.canonical_write_count,
            "proposed_change_count": report.proposed_change_count,
            "outputs": {
                **outputs,
                "report": _sha_file(report_path),
                "review": _sha_file(review_path),
            },
        }
    )
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "status": "complete",
                "run_root": str(root),
                "report": str(report_path),
                "review": str(review_path),
                "result_fingerprint": report.result_fingerprint,
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
                "proposed_change_count": report.proposed_change_count,
                "development_pool_ceiling": report.development_fidelity.pool_ceiling,
                "validation_pool_ceiling": report.validation_fidelity.pool_ceiling,
            },
            sort_keys=True,
        )
    )
    return 0


@dataclass(frozen=True)
class _PreparedState:
    catalog: PropositionGoldCatalog
    lookup: dict[str, ConstituentCandidateInventory]
    tasks: dict[str, ConstituentSelectionTask]


def _load_prepared(root: Path) -> _PreparedState:
    catalog = PropositionGoldCatalog.model_validate_json((root / "catalog.json").read_bytes())
    inventories = tuple(_load_models(ConstituentCandidateInventory, root / "inventories.json"))
    lookup = {item.event_id: item for item in inventories}
    tasks = {
        item.event_id: item for item in _load_models(ConstituentSelectionTask, root / "tasks.json")
    }
    return _PreparedState(catalog=catalog, lookup=lookup, tasks=tasks)


def _corrected_attachment_gold(root: Path) -> tuple[CorrectedAttachmentGold, bytes]:
    """Recover the corrected-Gold record from its persisted file form.

    The prepared corrected-gold file is a superset that preserves every
    unchanged Event for full-file review; ``CorrectedAttachmentGold`` drops
    that provenance-only ``events`` field.
    """
    selection_bytes = (root / CORRECTED_GOLD_FILENAME).read_bytes()
    raw = json.loads(selection_bytes)
    fields = {
        key: raw[key]
        for key in (
            "schema_version",
            "catalog_id",
            "source_catalog_sha256",
            "corrected_labels",
            "resizes",
        )
    }
    return CorrectedAttachmentGold.model_validate_json(_canonical_json(fields)), selection_bytes


def _parse_answers(
    root: Path,
    tasks: dict[str, ConstituentSelectionTask],
) -> dict[str, ConstituentSelectionAnswer]:
    answers_path = root / "answers.jsonl"
    if not answers_path.exists():
        raise ValueError("R3 requires answers.jsonl before scoring; run the execute phase first.")
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
        raise ValueError("R3 answers.jsonl must answer every rendered task exactly once.")
    return answers


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


def _build_tokens_by_digest(
    catalog: PropositionGoldCatalog,
    analyzer: StanzaLinguisticAnalyzer,
) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    sources: dict[str, str] = {}
    for event in catalog.events:
        prior = sources.get(event.source_text_sha256)
        if prior is None:
            sources[event.source_text_sha256] = event.source_text
        elif prior != event.source_text:
            raise ValueError("Proposition Gold repeats a digest with different text.")
    result: dict[str, tuple[EventEntityLinguisticToken, ...]] = {}
    for digest, text in sources.items():
        analysis = analyzer.analyze(LinguisticAnalysisInput(source_text=text))
        if analysis.source_text_sha256 != digest:
            raise ValueError("Stanza analysis digest drifted from its source text.")
        result[digest] = _linguistic_tokens(analysis)
    return result


def _event_expressions_and_literals(
    trigger_gold: TriggerGoldCatalog,
    catalog: PropositionGoldCatalog,
) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
    event_ids = {event.event_id for event in catalog.events}
    expressions: dict[str, tuple[int, int]] = {}
    literals: dict[str, str] = {}
    for segment in trigger_gold.segments:
        for event in segment.events:
            if event.event_id not in event_ids:
                continue
            start, end = _authoritative_head_span(segment, event)
            expressions[event.event_id] = (start, end)
            literals[event.event_id] = segment.source_text[start:end]
    if set(expressions) != event_ids:
        missing = sorted(event_ids - set(expressions))
        raise ValueError(f"Trigger Gold does not cover every R3 Event expression: {missing}.")
    return expressions, literals


def _authoritative_head_span(
    segment: TriggerGoldSegment, event: TriggerGoldEvent
) -> tuple[int, int]:
    source_copy = derive_source_copy_view(segment.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    head = occurrences[event.head_occurrence_id]
    return source_copy.authoritative_range(head.start, head.end)


def _contract_payload(contract: EventConstituentContract) -> dict[str, Any]:
    return {
        "event_id": contract.event_id,
        "phase": contract.phase,
        "source_text_sha256": contract.source_text_sha256,
        "source_text": contract.source_text,
        "event_literal": contract.event_literal,
        "event_expression_start": contract.event_expression_start,
        "event_expression_end": contract.event_expression_end,
        "token_ids": [item.token_id for item in contract.tokens],
    }


def _selection_summary(census: Any) -> dict[str, int]:
    return {
        "event_count": census.event_count,
        "selected_event_count": census.selected_event_count,
        "none_event_count": census.none_event_count,
        "rejected_event_count": census.rejected_event_count,
        "exact_attachment_count": census.exact_attachment_count,
        "gold_attachment_span_count": census.gold_attachment_span_count,
        "false_positive_span_count": census.false_positive_span_count,
        "false_negative_span_count": census.false_negative_span_count,
    }


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
