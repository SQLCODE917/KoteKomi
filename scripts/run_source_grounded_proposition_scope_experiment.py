#!/usr/bin/env python3
"""Prepare, run, and evaluate the bounded proposition-scope experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    ContextModelProfile,
    EventEntityConnectionCandidate,
    ExecutionSetting,
    ExtractionStageTrace,
    PropositionFragmentCandidate,
    PropositionFragmentDecision,
    SourceGroundedPropositionScope,
    SourceSegmentAnalysisUnitInput,
    Uuid4ModelRunIdFactory,
    build_event_entity_connection_candidates,
    build_proposition_fragment_candidates,
    create_analysis_unit_from_source_segment,
    proposition_fragment_answer_schema_bytes,
    run_source_grounded_proposition_scope,
    source_grounded_proposition_result_sha256,
)
from kotekomi_application.source_grounded_proposition_preview import (
    PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID,
    PROPOSITION_SCOPE_POLICY_ID,
    PropositionScopeArchive,
    PropositionScopeCommand,
    PropositionScopeLedger,
)
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentRepresentationBundle,
    ExtractionTask,
    ModelRun,
    Source,
)
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
    load_connection_gold_catalog,
)
from kotekomi_pipelines.event_entity_experiment_inputs import (
    load_event_entity_experiment_inputs,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionScopeCaseEvaluation,
    PropositionScopePhaseReport,
    PropositionScopePreflight,
    build_proposition_scope_phase_report,
    evaluate_proposition_candidate_preflight,
    evaluate_proposition_scope_case,
    load_proposition_gold_catalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
DEFAULT_PROMPT = REPOSITORY_ROOT / "prompts/source_grounded_proposition_fragment_membership_v1.md"


class _ExperimentLedger:
    """Ephemeral experiment repository with no accepted-state write path."""

    def __init__(
        self,
        source: Source,
        document: Document,
        bundle: DocumentRepresentationBundle,
    ) -> None:
        self.source = source
        self.document = document
        self.bundle = bundle
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.context_manifests: dict[str, ContextManifestArtifact] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.accepted_ledger_change_count = 0

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self,
        record_id: str,
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.context_manifests[record.id] = record

    def get_context_manifest_artifact(
        self,
        record_id: str,
    ) -> ContextManifestArtifact | None:
        return self.context_manifests.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.context_manifests[manifest.id] = manifest
        self.analysis_units.update({item.id: item for item in child_analysis_units})

    def save_extraction_task(self, record: ExtractionTask) -> None:
        self.extraction_tasks[record.id] = record

    def save_model_run(self, record: ModelRun) -> None:
        self.model_runs[record.id] = record

    def commit_successful_model_run_and_candidate_batch(
        self,
        *,
        model_run: ModelRun,
        batch: object,
    ) -> None:
        del model_run, batch
        self.accepted_ledger_change_count += 1
        raise AssertionError("Proposition experiment cannot write accepted Ledger state.")


@dataclass(frozen=True)
class _CanonicalState:
    source: Source
    document: Document
    bundle: DocumentRepresentationBundle


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--coverage-report-id", required=True)
    prepare.add_argument("--phase", choices=("development", "validation"), required=True)
    prepare.add_argument("--repetition", type=int, required=True)
    prepare.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    prepare.add_argument("--run-root", type=Path, required=True)

    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    finalize.add_argument("--run-root", type=Path, required=True)

    compare = commands.add_parser("compare")
    compare.add_argument("--development-report", type=Path, action="append", required=True)
    compare.add_argument("--validation-report", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "run":
        return _run(args)
    if args.command == "finalize":
        return _finalize(args)
    return _compare(args)


def _prepare(args: argparse.Namespace) -> int:
    _validate_repetition(args.phase, args.repetition)
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Proposition prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    gold_path = args.gold.resolve()
    catalog = load_proposition_gold_catalog(gold_path, repository_root=REPOSITORY_ROOT)
    connection_path = (REPOSITORY_ROOT / catalog.connection_gold_path).resolve()
    connection, _, trigger = load_connection_gold_catalog(
        connection_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
    )
    selected_connection = tuple(item for item in connection.events if item.phase == args.phase)
    config = _config(args.config)
    canonical = load_event_entity_experiment_inputs(
        config=config,
        coverage_report_id=args.coverage_report_id,
        selected_gold=selected_connection,
        trigger_gold=trigger,
    )
    _write_json(
        root / "canonical-state.json",
        {
            "source": canonical.source.model_dump(mode="json"),
            "document": canonical.document.model_dump(mode="json"),
            "bundle": canonical.bundle.model_dump(mode="json"),
        },
    )
    _write_jsonl(
        root / "inputs.jsonl",
        [item.model_dump(mode="json") for item in canonical.inputs],
    )
    gold_by_id = {item.event_id: item for item in catalog.events if item.phase == args.phase}
    proposition_candidates = {
        item.gold_event_id: _proposition_candidates(item) for item in canonical.inputs
    }
    preflights = tuple(
        evaluate_proposition_candidate_preflight(
            gold_by_id[event_id],
            proposition_candidates[event_id],
        )
        for event_id in sorted(gold_by_id)
    )
    _write_json(
        root / "preflight.json",
        {
            "schema_version": "source_grounded_proposition_preflight_v1",
            "phase": args.phase,
            "events": [item.model_dump(mode="json") for item in preflights],
            "passed": all(item.passed for item in preflights),
        },
    )
    (root / "preflight-review.md").write_text(
        _render_preflight_review(catalog, canonical.inputs, proposition_candidates, preflights),
        encoding="utf-8",
    )
    status = (
        "gold_review_required"
        if catalog.review_status.value != "approved"
        else ("candidate_gap" if not all(item.passed for item in preflights) else "prepared")
    )
    prompt = DEFAULT_PROMPT.read_bytes()
    metadata = {
        "schema_version": "source_grounded_proposition_experiment_run_v1",
        "status": status,
        "phase": args.phase,
        "repetition": args.repetition,
        "coverage_report_id": canonical.coverage.id,
        "coverage_report_sha256": _sha(canonical.coverage_payload),
        "gold_path": _relative_or_absolute(gold_path),
        "gold_sha256": _sha(gold_path.read_bytes()),
        "gold_review_status": catalog.review_status.value,
        "prompt_path": _relative_or_absolute(DEFAULT_PROMPT),
        "prompt_sha256": _sha(prompt),
        "schema_id": PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID,
        "schema_sha256": _sha(proposition_fragment_answer_schema_bytes()),
        "policy_id": PROPOSITION_SCOPE_POLICY_ID,
        "runtime": _runtime_contract(config),
        "input_count": len(canonical.inputs),
        "candidate_count": sum(len(items) for items in proposition_candidates.values()),
        "model_candidate_count": sum(len(items) - 1 for items in proposition_candidates.values()),
        "canonical_state_sha256": _sha((root / "canonical-state.json").read_bytes()),
        "inputs_sha256": _sha((root / "inputs.jsonl").read_bytes()),
        "preflight_sha256": _sha((root / "preflight.json").read_bytes()),
        "preflight_review_sha256": _sha((root / "preflight-review.md").read_bytes()),
    }
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "candidate_count": metadata["candidate_count"],
                "gold_review_status": catalog.review_status.value,
                "missing_fragment_count": sum(
                    len(item.missing_fragment_ids) for item in preflights
                ),
                "model_candidate_count": metadata["model_candidate_count"],
                "phase": args.phase,
                "preflight": str(root / "preflight.json"),
                "preflight_review": str(root / "preflight-review.md"),
                "run_root": str(root),
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if status == "prepared" else 2


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root)
    if metadata["status"] not in {"prepared", "run_complete"}:
        raise ValueError("Proposition run is not prepared: " + str(metadata["status"]))
    config = _config(args.config)
    if metadata["runtime"] != _runtime_contract(config):
        raise ValueError("Proposition runtime configuration changed after preparation.")
    _validate_static_contract(root, metadata)
    inputs = _load_inputs(root / "inputs.jsonl")
    state = _load_canonical_state(root / "canonical-state.json")
    output_dir = root / "events"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    prompt = DEFAULT_PROMPT.read_bytes()
    try:
        for ordinal, prepared in enumerate(inputs, start=1):
            output = output_dir / f"{prepared.gold_event_id}.json"
            if output.exists():
                print(f"Proposition Event {ordinal}/{len(inputs)}: reused")
                continue
            ledger = _ExperimentLedger(state.source, state.document, state.bundle)
            unit = create_analysis_unit_from_source_segment(
                SourceSegmentAnalysisUnitInput(
                    representation_id=prepared.representation_id,
                    paragraph_node_id=prepared.paragraph_node_id,
                    source_segment_label=prepared.source_segment_label,
                    policy_id=PROPOSITION_SCOPE_POLICY_ID,
                    task_type="source_grounded_proposition_scope_experiment",
                    source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
                ),
                ledger,
            )
            result = run_source_grounded_proposition_scope(
                PropositionScopeCommand(
                    source_id=prepared.source_id,
                    document_id=prepared.document_id,
                    representation_id=prepared.representation_id,
                    source_text=prepared.source_text,
                    event=prepared.event,
                    trigger=prepared.trigger,
                    entity_candidates=_entity_candidates(prepared),
                    linguistic_evidence=prepared.linguistic_evidence,
                    analysis_unit=unit,
                    model_profile=_profile(config),
                    generation_parameters=_generation(config),
                    prompt_bytes=prompt,
                ),
                ledger=cast(PropositionScopeLedger, ledger),
                archive=cast(PropositionScopeArchive, archive),
                model_runtime=runtime,
                model_run_id_factory=Uuid4ModelRunIdFactory(),
                tokenizer=runtime,
            )
            if ledger.accepted_ledger_change_count:
                raise AssertionError("Proposition experiment changed accepted Ledger state.")
            _write_json(
                output,
                {
                    "schema_version": "source_grounded_proposition_execution_v1",
                    "gold_event_id": prepared.gold_event_id,
                    "prepared_input": prepared.model_dump(mode="json"),
                    "candidates": [item.model_dump(mode="json") for item in result.candidates],
                    "decisions": [item.model_dump(mode="json") for item in result.decisions],
                    "scope": result.scope.model_dump(mode="json"),
                    "traces": [item.model_dump(mode="json") for item in result.traces],
                    "diagnostics": list(result.diagnostics),
                    "result_sha256": result.sha256,
                    "model_runs": [
                        item.model_dump(mode="json")
                        for item in sorted(ledger.model_runs.values(), key=lambda value: value.id)
                    ],
                    "accepted_ledger_change_count": ledger.accepted_ledger_change_count,
                },
            )
            print(
                f"Proposition Event {ordinal}/{len(inputs)}: "
                f"{result.scope.status.value} "
                f"({len(result.model_run_ids)} model executions)"
            )
    finally:
        close = getattr(runtime, "close", None)
        if callable(close):
            close()
    metadata["status"] = "run_complete"
    _write_json(root / "run.json", metadata)
    return 0


def _finalize(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root)
    if metadata["status"] not in {"run_complete", "finalized"}:
        raise ValueError("Proposition experiment has not completed model execution.")
    _validate_static_contract(root, metadata)
    gold_path = args.gold.resolve()
    if metadata["gold_path"] != _relative_or_absolute(gold_path):
        raise ValueError("Proposition Gold path changed after preparation.")
    catalog = load_proposition_gold_catalog(gold_path, repository_root=REPOSITORY_ROOT)
    if catalog.review_status.value != "approved":
        raise ValueError("Proposition finalization requires approved Gold.")
    connection_path = (REPOSITORY_ROOT / catalog.connection_gold_path).resolve()
    connection, _, _ = load_connection_gold_catalog(
        connection_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
    )
    phase = cast(Literal["development", "validation"], metadata["phase"])
    gold_by_id = {item.event_id: item for item in catalog.events if item.phase == phase}
    connection_by_id = {item.event_id: item for item in connection.events if item.phase == phase}
    cases: list[PropositionScopeCaseEvaluation] = []
    records: dict[str, dict[str, Any]] = {}
    model_execution_count = 0
    model_elapsed_milliseconds = 0
    for path in sorted((root / "events").glob("*.json")):
        record = _read_json(path)
        event_id = str(record["gold_event_id"])
        candidates = tuple(
            PropositionFragmentCandidate.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["candidates"])
        )
        decisions = tuple(
            PropositionFragmentDecision.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["decisions"])
        )
        scope = SourceGroundedPropositionScope.model_validate_json(_canonical_json(record["scope"]))
        traces = tuple(
            ExtractionStageTrace.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["traces"])
        )
        diagnostics = tuple(cast(list[str], record["diagnostics"]))
        expected_digest = source_grounded_proposition_result_sha256(
            candidates=candidates,
            decisions=decisions,
            scope=scope,
            traces=traces,
            diagnostics=diagnostics,
        )
        if record["result_sha256"] != expected_digest:
            raise ValueError("Proposition execution result digest is invalid.")
        if record.get("accepted_ledger_change_count") != 0:
            raise ValueError("Proposition execution changed accepted Ledger state.")
        cases.append(
            evaluate_proposition_scope_case(
                gold=gold_by_id[event_id],
                scope=scope,
                expected_entities=connection_by_id[event_id].expected_entities,
            )
        )
        records[event_id] = record
        model_runs = tuple(
            ModelRun.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["model_runs"])
        )
        model_execution_count += len(model_runs)
        model_elapsed_milliseconds += sum(
            _required_int(
                item.execution_diagnostics["elapsed_milliseconds"],
                "model elapsed milliseconds",
            )
            for item in model_runs
        )
    if set(records) != set(gold_by_id):
        raise ValueError("Proposition executions do not cover the complete Gold phase.")
    report = build_proposition_scope_phase_report(
        catalog=catalog,
        catalog_sha256=_sha(gold_path.read_bytes()),
        phase=phase,
        repetition=_required_int(metadata["repetition"], "repetition"),
        cases=tuple(cases),
    )
    report_path = root / "report.json"
    review_path = root / "review.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(
        _render_result_review(report, catalog, records),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "source_grounded_proposition_manifest_v1",
        "phase": phase,
        "repetition": report.repetition,
        "report_sha256": _sha(report_path.read_bytes()),
        "review_sha256": _sha(review_path.read_bytes()),
        "result_fingerprint": report.result_fingerprint,
        "model_execution_count": model_execution_count,
        "model_elapsed_milliseconds": model_elapsed_milliseconds,
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
        "passed": report.passed,
    }
    _write_json(root / "manifest.json", manifest)
    if phase == "validation":
        (root / "FINALIZED").write_text(_sha(_canonical_json(manifest)), encoding="utf-8")
    metadata["status"] = "finalized"
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "metrics": report.metrics.model_dump(mode="json"),
                "model_elapsed_milliseconds": model_elapsed_milliseconds,
                "model_execution_count": model_execution_count,
                "passed": report.passed,
                "report": str(report_path),
                "review": str(review_path),
            },
            sort_keys=True,
        )
    )
    return 0 if report.passed else 1


def _compare(args: argparse.Namespace) -> int:
    development = tuple(
        PropositionScopePhaseReport.model_validate_json(path.resolve().read_bytes())
        for path in args.development_report
    )
    validation = PropositionScopePhaseReport.model_validate_json(
        args.validation_report.resolve().read_bytes()
    )
    if len(development) != 3 or {item.repetition for item in development} != {1, 2, 3}:
        raise ValueError("Proposition comparison requires development repetitions 1, 2, and 3.")
    if any(item.phase != "development" for item in development):
        raise ValueError("Proposition development reports have the wrong phase.")
    if validation.phase != "validation" or validation.repetition != 1:
        raise ValueError("Proposition validation report has the wrong phase or repetition.")
    stable = len({item.result_fingerprint for item in development}) == 1
    result = {
        "schema_version": "source_grounded_proposition_comparison_v1",
        "development": [
            {
                "passed": item.passed,
                "repetition": item.repetition,
                "result_fingerprint": item.result_fingerprint,
            }
            for item in sorted(development, key=lambda value: value.repetition)
        ],
        "development_stable": stable,
        "validation": {
            "passed": validation.passed,
            "result_fingerprint": validation.result_fingerprint,
        },
        "production_integration": "not_activated",
        "passed": stable and all(item.passed for item in development) and validation.passed,
    }
    _write_json(args.output.resolve(), result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


def _entity_candidates(
    prepared: EventEntityExperimentInput,
) -> tuple[EventEntityConnectionCandidate, ...]:
    return build_event_entity_connection_candidates(
        prepared.event,
        prepared.candidate_selection.mentions,
        source_text=prepared.source_text,
    )


def _proposition_candidates(
    prepared: EventEntityExperimentInput,
) -> tuple[PropositionFragmentCandidate, ...]:
    return build_proposition_fragment_candidates(
        source_text=prepared.source_text,
        trigger=prepared.trigger,
        event=prepared.event,
        linguistic_evidence=prepared.linguistic_evidence,
        entity_candidates=_entity_candidates(prepared),
    )


def _render_preflight_review(
    catalog: PropositionGoldCatalog,
    inputs: tuple[EventEntityExperimentInput, ...],
    candidates: dict[str, tuple[PropositionFragmentCandidate, ...]],
    preflights: tuple[PropositionScopePreflight, ...],
) -> str:
    gold_by_id = {item.event_id: item for item in catalog.events}
    input_by_id = {item.gold_event_id: item for item in inputs}
    preflight_by_id = {item.event_id: item for item in preflights}
    lines = ["# Proposition Scope Candidate Preflight", ""]
    for event_id in sorted(input_by_id):
        prepared = input_by_id[event_id]
        gold = gold_by_id[event_id]
        preflight = preflight_by_id[event_id]
        lines.extend(
            (
                f"## {event_id}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {prepared.source_text}",
                "",
                f"Expected meaning: {gold.event_meaning}",
                "",
                f"Preflight passed: `{str(preflight.passed).lower()}`",
                "",
                (
                    "Missing Gold fragments: `"
                    + (", ".join(preflight.missing_fragment_ids) or "none")
                    + "`"
                ),
                "",
                "Candidate data out:",
                "",
            )
        )
        for candidate in candidates[event_id]:
            reasons = ", ".join(item.value for item in candidate.reasons)
            lines.append(f"- `{candidate.text}` — [{candidate.start}, {candidate.end}) — {reasons}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_result_review(
    report: PropositionScopePhaseReport,
    catalog: PropositionGoldCatalog,
    records: dict[str, dict[str, Any]],
) -> str:
    gold_by_id = {item.event_id: item for item in catalog.events}
    evaluation_by_id = {item.event_id: item for item in report.cases}
    lines = [
        f"# Proposition Scope {report.phase} Review",
        "",
        f"Repetition: `{report.repetition}`",
        "",
    ]
    for event_id in sorted(records):
        record = records[event_id]
        prepared = EventEntityExperimentInput.model_validate_json(
            _canonical_json(record["prepared_input"])
        )
        gold = gold_by_id[event_id]
        evaluation = evaluation_by_id[event_id]
        candidates = tuple(
            PropositionFragmentCandidate.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["candidates"])
        )
        decisions = tuple(
            PropositionFragmentDecision.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["decisions"])
        )
        traces = tuple(
            ExtractionStageTrace.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["traces"])
        )
        decision_by_candidate = {item.candidate_id: item for item in decisions}
        trace_by_candidate = {
            cast(dict[str, Any], item.input["candidate"])["id"]: item for item in traces
        }
        lines.extend(
            (
                f"## {event_id}",
                "",
                "Exact data in:",
                "",
                f"> {prepared.source_text}",
                "",
                f"Expected meaning: {gold.event_meaning}",
                "",
                "Expected exact fragments:",
                "",
            )
        )
        lines.extend(f"- `{item.text}`" for item in gold.fragments)
        lines.extend(("", "Candidate decisions:", ""))
        for candidate in candidates:
            decision = decision_by_candidate[candidate.id]
            trace = trace_by_candidate.get(candidate.id)
            lines.extend(
                (
                    f"### `{candidate.text}`",
                    "",
                    f"KoteKomi decision: `{decision.disposition.value}`",
                    "",
                    f"Route: `{decision.route.value}`",
                    "",
                )
            )
            if trace is not None:
                lines.extend(
                    (
                        "Exact model input:",
                        "",
                        "~~~~text",
                        str(trace.input["exact_model_input"]),
                        "~~~~",
                        "",
                        f"Raw model output: `{trace.output['raw_output_text']}`",
                        "",
                    )
                )
        scope = SourceGroundedPropositionScope.model_validate_json(_canonical_json(record["scope"]))
        lines.extend(("Selected exact fragments:", ""))
        lines.extend(f"- `{item.text}`" for item in scope.fragments)
        lines.extend(
            (
                "",
                f"Required character recall: `{_case_recall(evaluation):.6f}`",
                "",
                f"Passed: `{str(evaluation.passed).lower()}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _validate_static_contract(root: Path, metadata: dict[str, Any]) -> None:
    gold_path = _stored_path(metadata["gold_path"], "Proposition Gold")
    if metadata["gold_sha256"] != _sha(gold_path.read_bytes()):
        raise ValueError("Proposition Gold changed after preparation.")
    if metadata["prompt_sha256"] != _sha(DEFAULT_PROMPT.read_bytes()):
        raise ValueError("Proposition prompt changed after preparation.")
    if metadata["schema_sha256"] != _sha(proposition_fragment_answer_schema_bytes()):
        raise ValueError("Proposition output contract changed after preparation.")
    if metadata["schema_id"] != PROPOSITION_FRAGMENT_MEMBERSHIP_SCHEMA_ID:
        raise ValueError("Proposition output schema identity changed.")
    if metadata["policy_id"] != PROPOSITION_SCOPE_POLICY_ID:
        raise ValueError("Proposition policy identity changed.")
    for field_name, filename in (
        ("canonical_state_sha256", "canonical-state.json"),
        ("inputs_sha256", "inputs.jsonl"),
        ("preflight_sha256", "preflight.json"),
        ("preflight_review_sha256", "preflight-review.md"),
    ):
        if metadata[field_name] != _sha((root / filename).read_bytes()):
            raise ValueError(f"Proposition {filename} changed after preparation.")
    preflight = _read_json(root / "preflight.json")
    if metadata["status"] in {"prepared", "run_complete", "finalized"} and (
        metadata["gold_review_status"] != "approved" or not preflight["passed"]
    ):
        raise ValueError("Proposition execution requires approved Gold and passing preflight.")


def _validate_repetition(phase: str, repetition: int) -> None:
    if phase == "development" and repetition not in {1, 2, 3}:
        raise ValueError("Development repetitions are one through three.")
    if phase == "validation" and repetition != 1:
        raise ValueError("Validation runs exactly once.")


def _load_metadata(root: Path) -> dict[str, Any]:
    value = _read_json(root / "run.json")
    if value.get("schema_version") != "source_grounded_proposition_experiment_run_v1":
        raise ValueError("Proposition run metadata schema is unknown.")
    return value


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _load_canonical_state(path: Path) -> _CanonicalState:
    value = _read_json(path)
    return _CanonicalState(
        Source.model_validate_json(_canonical_json(value["source"])),
        Document.model_validate_json(_canonical_json(value["document"])),
        DocumentRepresentationBundle.model_validate_json(_canonical_json(value["bundle"])),
    )


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _profile(config: PipelineConfig) -> ContextModelProfile:
    return ContextModelProfile(
        config.model_execution.profile_name or "lm-studio",
        config.model_execution.context_tokens,
        config.model_execution.max_output_tokens,
        256,
    )


def _generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )


def _runtime_contract(config: PipelineConfig) -> dict[str, object]:
    value = config.model_execution
    return {
        "adapter": value.adapter,
        "context_tokens": value.context_tokens,
        "endpoint": value.endpoint,
        "max_output_tokens": value.max_output_tokens,
        "model": value.model,
        "profile_name": value.profile_name,
        "timeout_seconds": value.timeout_seconds,
    }


def _case_recall(case: PropositionScopeCaseEvaluation) -> float:
    return (
        case.true_positive_character_count / case.required_character_count
        if case.required_character_count
        else 1.0
    )


def _required_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_canonical_json(item) + "\n" for item in values), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, Any], value)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha(payload: bytes | str) -> str:
    value = payload.encode() if isinstance(payload, str) else payload
    return hashlib.sha256(value).hexdigest()


def _relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(REPOSITORY_ROOT).as_posix()
        if resolved.is_relative_to(REPOSITORY_ROOT)
        else str(resolved)
    )


def _stored_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} path is invalid.")
    raw = Path(value)
    path = raw.resolve() if raw.is_absolute() else (REPOSITORY_ROOT / raw).resolve()
    if not raw.is_absolute() and not path.is_relative_to(REPOSITORY_ROOT):
        raise ValueError(f"{label} path leaves the repository.")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
