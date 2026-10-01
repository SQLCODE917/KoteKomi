#!/usr/bin/env python3
"""Run the R6 calibrated-residual-ownership held-out transfer evaluation.

R6 closes the R5 transfer failures deterministically, then reserves the model for the
residual residue.  Runner phases over one run root:

* ``prepare`` -- model-free.  Re-derives the R3-A constituent pool, adds the full
  source-segment-content candidate so every Gold fragment boundary is carried by one
  candidate,
  fails fast with one typed :class:`~kotekomi_application.BoundaryGap` per fragment ID on
  any remaining gap, then renders one Event-frame selection task per Event over the
  R1-attached candidates only.
* ``execute`` -- local model selection with Token Probability Evidence.
* ``score`` -- one full token-sequence Selection Score per Event, threshold routing, and the
  residual-review set.
* ``report`` -- seals the R6 report with zero canonical writes and zero ProposedChanges
  and renders a human review.

All inputs and outputs are explicit paths or a TOML config file.  No environment
variables are assumed.  The Selection Score threshold is a required ``--threshold``
natural-log-probability scalar for ``score``; ``report`` reads the sealed ``score.json``
so the routing can never drift between phases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
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
    BoundaryGap,
    CalibratedResidualOwnershipReport,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    ConstituentSelectionTask,
    EventEntityLinguisticToken,
    EventFrame,
    ExecutionSetting,
    HeldOutGoldFragment,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    ModelExecutionSpec,
    ModelInputAdmissionRequest,
    ModelTaskRequest,
    ParserConstituent,
    ResidualReviewReason,
    SelectionProbabilityReceipt,
    SelectionRouting,
    SelectionRoutingDecision,
    SelectionScore,
    admit_model_input,
    attached_constituents,
    augment_candidate_inventory_with_segment_core,
    build_calibrated_residual_ownership_report,
    build_event_frame,
    build_representative_selection_score,
    build_selection_probability_receipt,
    build_selection_scores,
    derive_selectable_constituents,
    detect_boundary_gaps,
    parse_constituent_selection_answer,
    render_event_frame_selection_task,
    route_selection_scores,
)
from kotekomi_domain import ModelInputAdmissionStatus
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.evaluation_remediation import (
    HeldOutPropositionGoldCatalog,
    build_held_out_inventories,
    derive_held_out_trigger_head,
    load_held_out_proposition_gold,
    verify_held_out_frozen_evidence,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-29-calibrated-residual-ownership.md"
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json"
DEFAULT_FIXTURE = REPOSITORY_ROOT / "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf"
DEFAULT_STANZA_LOCK = (
    REPOSITORY_ROOT / "packages/adapters/src/kotekomi_adapters/stanza-model-lock.json"
)

RUN_SCHEMA_VERSION = "calibrated_residual_ownership_run_v1"
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
    parser = argparse.ArgumentParser(
        description="Measure R6 residual ownership on the held-out partition."
    )
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
    score.add_argument("--threshold", type=float, required=True)

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
    raise ValueError(f"Unsupported R6 command: {args.command}")


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("R6 prepare requires an absent or empty run root.")
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
    base_inventories = build_held_out_inventories(
        catalog=catalog, tokens_by_digest=tokens_by_digest
    )

    augmented: dict[str, ConstituentCandidateInventory] = {}
    frames: dict[str, EventFrame] = {}
    tasks: dict[str, ConstituentSelectionTask] = {}
    selectable_by_event: dict[str, tuple[ParserConstituent, ...]] = {}
    zero_candidate_event_ids: list[str] = []
    for event in sorted(catalog.events, key=lambda item: item.event_id):
        tokens = tokens_by_digest[event.source_text_sha256]
        head_start, head_end = derive_held_out_trigger_head(
            source_text=event.source_text, tokens=tokens
        )
        inventory = augment_candidate_inventory_with_segment_core(
            inventory=base_inventories[event.event_id],
            source_text=event.source_text,
            tokens=tokens,
            trigger_head_start=head_start,
            trigger_head_end=head_end,
        )
        augmented[event.event_id] = inventory
        frame = build_event_frame(
            event_id=event.event_id,
            source_text=event.source_text,
            tokens=tokens,
            trigger_head_start=head_start,
            trigger_head_end=head_end,
            inventory=inventory,
        )
        frames[event.event_id] = frame
        attached = attached_constituents(
            inventory=inventory,
            source_text=event.source_text,
            tokens=tokens,
            trigger_head_start=head_start,
            trigger_head_end=head_end,
        )
        selectable = derive_selectable_constituents(
            attached=attached,
            source_text=event.source_text,
            tokens=tokens,
            trigger=frame.trigger,
        )
        selectable_by_event[event.event_id] = selectable
        if not selectable:
            zero_candidate_event_ids.append(event.event_id)
            continue
        tasks[event.event_id] = render_event_frame_selection_task(
            event_id=event.event_id,
            source_text=event.source_text,
            inventory=inventory,
            selectable=selectable,
            frame=frame,
        )

    gold_fragments: dict[str, tuple[HeldOutGoldFragment, ...]] = {
        event.event_id: event.fragments for event in catalog.events
    }
    boundary_gaps = detect_boundary_gaps(gold_fragments=gold_fragments, inventories=augmented)

    ordered_events = sorted(catalog.events, key=lambda item: item.event_id)
    _write_json(root / "catalog.json", catalog.model_dump(mode="json"))
    _write_json(
        root / "inventories.json",
        [augmented[event.event_id].model_dump(mode="json") for event in ordered_events],
    )
    _write_json(
        root / "boundary_gaps.json",
        [item.model_dump(mode="json") for item in boundary_gaps],
    )
    _write_json(
        root / "frames.json",
        [frames[event.event_id].model_dump(mode="json") for event in ordered_events],
    )
    _write_json(
        root / "tasks.json",
        [tasks[event_id].model_dump(mode="json") for event_id in sorted(tasks)],
    )
    _write_jsonl(
        root / "inputs.jsonl",
        [tasks[event_id].model_dump(mode="json") for event_id in sorted(tasks)],
    )
    _write_json(
        root / "selectable.json",
        [
            {
                "event_id": event.event_id,
                "constituents": [
                    item.model_dump(mode="json") for item in selectable_by_event[event.event_id]
                ],
            }
            for event in ordered_events
        ],
    )
    _write_json(
        root / "tokens.json",
        {
            digest: [token.model_dump(mode="json") for token in tokens]
            for digest, tokens in sorted(tokens_by_digest.items())
        },
    )

    if boundary_gaps:
        for gap in boundary_gaps:
            print(
                f"R6 boundary gap: fragment={gap.fragment_id} start={gap.start} end={gap.end}",
                file=sys.stderr,
            )
        raise ValueError(
            f"R6 prepare failed fast: {len(boundary_gaps)} Gold fragment boundary "
            f"remained uncovered after segment-core augmentation.  See "
            f"{root / 'boundary_gaps.json'}."
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
            "boundary_gap_count": len(boundary_gaps),
            "zero_candidate_event_count": len(zero_candidate_event_ids),
            "zero_candidate_event_ids": sorted(zero_candidate_event_ids),
            "selectable_candidate_count": sum(len(items) for items in selectable_by_event.values()),
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
                "boundary_gaps": _sha_file(root / "boundary_gaps.json"),
                "frames": _sha_file(root / "frames.json"),
                "tasks": _sha_file(root / "tasks.json"),
                "selectable": _sha_file(root / "selectable.json"),
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
                "boundary_gap_count": len(boundary_gaps),
                "zero_candidate_event_count": len(zero_candidate_event_ids),
                "zero_candidate_event_ids": sorted(zero_candidate_event_ids),
                "selectable_candidate_count": sum(
                    len(items) for items in selectable_by_event.values()
                ),
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
    _require_schema(metadata, RUN_SCHEMA_VERSION, "R6 run")
    if metadata.get("status") != "prepared":
        raise ValueError("R6 execute requires a run root prepared first.")
    prepared = _load_prepared(root)
    config = _config(args.config.resolve())
    runtime = build_model_task_runtime(config.model_execution)
    readiness = runtime.check_readiness()
    if not readiness.ready:
        _close_runtime(runtime)
        raise RuntimeError(f"R6 model runtime is not ready: {readiness}.")

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
            raise ValueError(f"R6 rendered task digest drifted for {event_id}.")
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
                f"R6 selection task for {event_id} is blocked by input admission: "
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
        raise ValueError("R6 selection generation settings are not canonically ordered.")
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
        raise ValueError("R6 selection model output must be UTF-8 text.") from error
    return text


def _score(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if not _is_finite_non_positive(args.threshold):
        raise ValueError(
            "R6 Selection Score threshold must be a finite non-positive log probability."
        )
    threshold = float(args.threshold)
    prepared = _load_prepared(root)
    metadata = _read_json(root / "run.json")
    _require_schema(metadata, RUN_SCHEMA_VERSION, "R6 run")
    answers = _parse_answers(root, prepared.tasks)
    receipts = _load_receipts(root, prepared.tasks)

    representative_scores = _representative_scores(prepared, answers, receipts)
    per_label_scores = _per_label_scores(prepared, answers, receipts)
    routing = route_selection_scores(
        scores=representative_scores, answers=answers, threshold=threshold
    )
    zero_event_ids = _zero_candidate_event_ids(metadata)
    if zero_event_ids:
        routing = tuple(
            sorted(
                routing
                + tuple(
                    SelectionRouting(
                        event_id=event_id,
                        decision=SelectionRoutingDecision.RESIDUAL_REVIEW,
                        reason=ResidualReviewReason.NO_SELECTABLE,
                    )
                    for event_id in zero_event_ids
                ),
                key=lambda item: item.event_id,
            )
        )
    residual_event_ids = tuple(
        item.event_id
        for item in routing
        if item.decision is SelectionRoutingDecision.RESIDUAL_REVIEW
    )

    _write_json(
        root / "score.json",
        {
            "status": "scored",
            "threshold": threshold,
            "model_execution_count": cast(int, metadata.get("model_execution_count", 0)),
            "representative_scores": [
                item.model_dump(mode="json") for item in representative_scores.values()
            ],
            "per_label_scores": [item.model_dump(mode="json") for item in per_label_scores],
            "selection_routing": [item.model_dump(mode="json") for item in routing],
            "residual_review_event_ids": list(residual_event_ids),
        },
    )
    print(
        json.dumps(
            {
                "status": "scored",
                "run_root": str(root),
                "threshold": threshold,
                "accepted_selection_count": _count_decisions(routing, "accepted_selection"),
                "residual_review_count": _count_decisions(routing, "residual_review"),
                "residual_review_event_ids": list(residual_event_ids),
                "model_execution_count": cast(int, metadata.get("model_execution_count", 0)),
            },
            sort_keys=True,
        )
    )
    return 0


def _count_decisions(routing: tuple[SelectionRouting, ...], decision: str) -> int:
    return sum(1 for item in routing if item.decision.value == decision)


def _zero_candidate_event_ids(metadata: dict[str, Any]) -> tuple[str, ...]:
    values = _require_list(metadata, "zero_candidate_event_ids", "R6 run")
    return tuple(_require_event_id(item) for item in values)


def _report(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    prepared = _load_prepared(root)
    metadata = _read_json(root / "run.json")
    _require_schema(metadata, RUN_SCHEMA_VERSION, "R6 run")
    score = _read_json(root / "score.json")
    threshold = _require_finite_float(score, "threshold", "R6 score.json")
    model_execution_count = cast(int, metadata.get("model_execution_count", 0))

    boundary_gaps = _load_models(BoundaryGap, root / "boundary_gaps.json")
    routing = _validate_model_list(
        SelectionRouting, _require_list(score, "selection_routing", "R6 score.json")
    )
    residual_event_ids = tuple(
        _require_event_id(item)
        for item in _require_list(score, "residual_review_event_ids", "R6 score.json")
    )
    report = build_calibrated_residual_ownership_report(
        boundary_gaps=boundary_gaps,
        selection_routing=routing,
        residual_review_event_ids=residual_event_ids,
        model_execution_count=model_execution_count,
    )

    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "review.md").write_text(
        _render_review(
            catalog=prepared.catalog,
            threshold=threshold,
            routing={item.event_id: item for item in routing},
            residual_event_ids=residual_event_ids,
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
                "threshold": threshold,
                "boundary_gap_count": len(report.boundary_gaps),
                "accepted_selection_count": _count_decisions(routing, "accepted_selection"),
                "residual_review_count": _count_decisions(routing, "residual_review"),
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
    tasks: dict[str, ConstituentSelectionTask]


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
    tasks = {
        item.event_id: item for item in _load_models(ConstituentSelectionTask, root / "tasks.json")
    }
    return _PreparedState(catalog=catalog, tasks=tasks)


def _parse_answers(
    root: Path,
    tasks: dict[str, ConstituentSelectionTask],
) -> dict[str, ConstituentSelectionAnswer]:
    answers_path = root / "answers.jsonl"
    if not answers_path.exists():
        raise ValueError("R6 requires answers.jsonl before scoring; run execute first.")
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
        raise ValueError("R6 answers.jsonl must answer every rendered task exactly once.")
    return answers


def _load_receipts(
    root: Path,
    tasks: dict[str, ConstituentSelectionTask],
) -> dict[str, SelectionProbabilityReceipt]:
    receipts_path = root / "receipts.json"
    if not receipts_path.exists():
        raise ValueError("R6 requires receipts.json; run execute first.")
    receipts: dict[str, SelectionProbabilityReceipt] = {}
    for item in _load_models(SelectionProbabilityReceipt, receipts_path):
        if item.event_id not in tasks:
            raise ValueError(f"R6 receipts reference an unknown Event: {item.event_id}.")
        receipts[item.event_id] = item
    if set(receipts) != set(tasks):
        raise ValueError("R6 receipts must cover every rendered task exactly once.")
    return receipts


def _representative_scores(
    prepared: _PreparedState,
    answers: dict[str, ConstituentSelectionAnswer],
    receipts: dict[str, SelectionProbabilityReceipt],
) -> dict[str, SelectionScore]:
    """Return one representative Selection Score per Event.

    A Rejected answer carries a censored ``NONE`` score with no reconstructed label. A
    ``NONE`` answer carries its full ``NONE`` token-sequence score. A selected subset carries
    the most confident non-censored constituent label.
    """
    return {
        event_id: build_representative_selection_score(
            event_id=event_id,
            answer=answers[event_id],
            allowed_labels=prepared.tasks[event_id].constituent_labels,
            receipt=receipts[event_id],
        )
        for event_id in sorted(prepared.tasks)
    }


def _per_label_scores(
    prepared: _PreparedState,
    answers: dict[str, ConstituentSelectionAnswer],
    receipts: dict[str, SelectionProbabilityReceipt],
) -> tuple[SelectionScore, ...]:
    scores: list[SelectionScore] = []
    for event_id in sorted(prepared.tasks):
        if answers[event_id].status is ConstituentSelectionStatus.REJECTED:
            continue
        task = prepared.tasks[event_id]
        scores.extend(
            build_selection_scores(
                event_id=event_id,
                allowed_labels=task.constituent_labels,
                receipt=receipts[event_id],
            )
        )
    return tuple(scores)


def _render_review(
    *,
    catalog: HeldOutPropositionGoldCatalog,
    threshold: float,
    routing: Mapping[str, SelectionRouting],
    residual_event_ids: tuple[str, ...],
    report: CalibratedResidualOwnershipReport,
) -> str:
    lines = [
        "# R6 Calibrated Residual Ownership",
        "",
        f"Selection Score threshold: `{threshold}`.",
        f"Model executions: {report.model_execution_count}.",
        f"Canonical writes: {report.canonical_write_count}.",
        f"ProposedChanges: {report.proposed_change_count}.",
        "",
        "## Boundary gaps",
        "",
    ]
    gap_lines = [f"- `{gap.fragment_id}` {gap.start}..{gap.end}" for gap in report.boundary_gaps]
    lines.extend(gap_lines or ["- none"])
    lines.extend(
        [
            "",
            "## Residual review",
            "",
            f"Residual-review Events: {', '.join(residual_event_ids) or 'none'}.",
            "",
            "## Events",
            "",
        ]
    )
    for event in sorted(catalog.events, key=lambda item: item.event_id):
        decision = routing[event.event_id]
        lines.append(f"### {event.event_id}")
        lines.append("")
        lines.append(f"- decision: `{decision.decision.value}`")
        if decision.reason is not None:
            lines.append(f"- reason: `{decision.reason.value}`")
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


def _require_finite_float(value: dict[str, Any], key: str, label: str) -> float:
    raw = value.get(key)
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        raise ValueError(f"{label} requires a numeric '{key}'.")
    result = float(raw)
    if not _is_finite_non_positive(result):
        raise ValueError(f"{label} '{key}' must be a finite non-positive log probability.")
    return result


def _require_event_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("R6 residual-review entry must be an Event ID string.")
    return value


def _require_list(value: dict[str, Any], key: str, label: str) -> list[object]:
    raw = value.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"{label} requires a '{key}' list.")
    return cast(list[object], raw)


def _validate_model_list(model: type[Any], values: list[object]) -> tuple[Any, ...]:
    return tuple(model.model_validate_json(_canonical_json(item)) for item in values)


def _is_finite_non_positive(value: float) -> bool:
    return math.isfinite(value) and value <= 0


def _load_models(model: type[Any], path: Path) -> tuple[Any, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    return _validate_model_list(model, cast(list[object], value))


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
