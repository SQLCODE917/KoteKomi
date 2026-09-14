#!/usr/bin/env python3
"""Prepare, run, finalize, and compare the Event-entity connection experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    ContextModelProfile,
    EventEntityConnectionPreview,
    ExecutionSetting,
    ExtractionStageTrace,
    HybridStageId,
    SourceSegmentAnalysisUnitInput,
    Uuid4ModelRunIdFactory,
    build_event_entity_connection_candidates,
    canonical_event_entity_connection_preview_bytes,
    create_analysis_unit_from_source_segment,
    derive_source_copy_view,
    hybrid_document_coverage_report_from_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_reference_preview_from_bytes,
    hybrid_source_segment_id,
    load_hybrid_event_semantics_preview,
    load_hybrid_event_trigger_preview,
    paragraph_source_segments,
    select_event_entity_mentions,
)
from kotekomi_application.event_entity_connection_model_output import (
    entity_involvement_answer_schema_bytes,
)
from kotekomi_application.event_entity_connection_preview import (
    EventEntityConnectionArchive,
    EventEntityConnectionCommand,
    EventEntityConnectionLedger,
    run_event_entity_connection_preview,
)
from kotekomi_application.event_entity_connections import (
    EVENT_ENTITY_CONNECTION_POLICY_ID,
    EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID,
)
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft
from kotekomi_application.source_occurrences import source_occurrences
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
    ConnectionGoldEvent,
    EventEntityCandidatePreflightReport,
    EventEntityCaseEvaluation,
    EventEntityExperimentInput,
    EventEntityPhaseReport,
    build_event_entity_candidate_preflight_report,
    build_event_entity_phase_report,
    evaluate_event_entity_case,
    event_entity_preparation_status,
    load_connection_gold_catalog,
    render_connection_gold_review,
    render_event_entity_candidate_preflight_review,
)
from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    TriggerGoldEvent,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs" / "hsq-event-entity-connection-gold-v1.json"
DEFAULT_PROMPT = REPOSITORY_ROOT / "prompts" / "event_entity_involvement_v1.md"


class _ExperimentLedger:
    """Ephemeral derived-state repository that exposes no accepted-state write."""

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
        raise AssertionError("Connection experiment cannot write accepted Ledger state.")


@dataclass(frozen=True)
class _CanonicalState:
    source: Source
    document: Document
    bundle: DocumentRepresentationBundle


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    review = commands.add_parser("render-gold")
    review.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    review.add_argument("--output", type=Path, required=True)

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
    if args.command == "render-gold":
        return _render_gold(args)
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "run":
        return _run(args)
    if args.command == "finalize":
        return _finalize(args)
    return _compare(args)


def _render_gold(args: argparse.Namespace) -> int:
    catalog, _, trigger_gold = load_connection_gold_catalog(
        args.gold.resolve(),
        repository_root=REPOSITORY_ROOT,
        require_approved=False,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_connection_gold_review(catalog, trigger_gold), encoding="utf-8")
    print(output)
    return 0


def _prepare(args: argparse.Namespace) -> int:
    if args.repetition < 1 or (args.phase == "development" and args.repetition > 3):
        raise ValueError("Development repetitions are one through three.")
    if args.phase == "validation" and args.repetition != 1:
        raise ValueError("Validation runs exactly once.")
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Connection prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    gold_path = args.gold.resolve()
    catalog, _, trigger_gold = load_connection_gold_catalog(
        gold_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=False,
    )
    config = _config(args.config)
    canonical_archive = LocalArchiveStore(config.archive_path)
    coverage_payload = canonical_archive.read_hybrid_document_coverage_report(
        args.coverage_report_id
    )
    coverage = hybrid_document_coverage_report_from_bytes(coverage_payload)
    selected_gold = tuple(item for item in catalog.events if item.phase == args.phase)
    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(coverage.representation_id)
        if bundle is None:
            raise ValueError("Coverage report references a missing representation.")
        document = ledger.get_document(bundle.representation.document_id)
        if document is None:
            raise ValueError("Representation references a missing Document.")
        source = ledger.get_source(document.source_id)
        if source is None:
            raise ValueError("Document references a missing Source.")
        inputs = _collect_inputs(
            coverage=coverage,
            selected_gold=selected_gold,
            trigger_gold=trigger_gold,
            bundle=bundle,
            source=source,
            document=document,
            ledger=ledger,
            archive=canonical_archive,
        )
    _write_json(
        root / "canonical-state.json",
        {
            "source": source.model_dump(mode="json"),
            "document": document.model_dump(mode="json"),
            "bundle": bundle.model_dump(mode="json"),
        },
    )
    _write_jsonl(
        root / "inputs.jsonl",
        [item.model_dump(mode="json") for item in inputs],
    )
    catalog_sha256 = _sha(gold_path.read_bytes())
    preflight = build_event_entity_candidate_preflight_report(
        catalog=catalog,
        catalog_sha256=catalog_sha256,
        phase=args.phase,
        inputs=inputs,
    )
    _write_json(root / "preflight.json", preflight.model_dump(mode="json"))
    (root / "preflight-review.md").write_text(
        render_event_entity_candidate_preflight_review(preflight, catalog, inputs),
        encoding="utf-8",
    )
    prompt = DEFAULT_PROMPT.read_bytes()
    candidate_count = sum(
        len(
            build_event_entity_connection_candidates(
                item.event,
                item.candidate_selection.mentions,
                source_text=item.source_text,
            )
        )
        for item in inputs
    )
    candidate_gap_count = sum(len(item.candidate_selection.gaps) for item in inputs)
    status = event_entity_preparation_status(
        gold_review_status=catalog.review_status,
        preflight_passed=preflight.passed,
    )
    metadata = {
        "schema_version": "event_entity_connection_experiment_run_v1",
        "status": status,
        "phase": args.phase,
        "repetition": args.repetition,
        "coverage_report_id": coverage.id,
        "coverage_report_sha256": _sha(coverage_payload),
        "gold_path": _relative_or_absolute(gold_path),
        "gold_sha256": catalog_sha256,
        "gold_review_status": catalog.review_status,
        "prompt_path": _relative_or_absolute(DEFAULT_PROMPT),
        "prompt_sha256": _sha(prompt),
        "schema_id": EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID,
        "schema_sha256": _sha(entity_involvement_answer_schema_bytes()),
        "policy_id": EVENT_ENTITY_CONNECTION_POLICY_ID,
        "runtime": _runtime_contract(config),
        "input_count": len(inputs),
        "candidate_count": candidate_count,
        "candidate_gap_count": candidate_gap_count,
        "canonical_state_sha256": _sha((root / "canonical-state.json").read_bytes()),
        "inputs_sha256": _sha((root / "inputs.jsonl").read_bytes()),
        "preflight_sha256": _sha((root / "preflight.json").read_bytes()),
        "preflight_review_sha256": _sha((root / "preflight-review.md").read_bytes()),
    }
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "phase": args.phase,
                "repetition": args.repetition,
                "input_count": len(inputs),
                "candidate_count": candidate_count,
                "candidate_gap_count": candidate_gap_count,
                "preflight_missing_entity_count": preflight.missing_entity_count,
                "preflight_violated_exclusion_count": preflight.violated_exclusion_count,
                "preflight_passed": preflight.passed,
                "status": status,
                "preflight": str(root / "preflight.json"),
                "preflight_review": str(root / "preflight-review.md"),
                "run_root": str(root),
            },
            sort_keys=True,
        )
    )
    return 0


def _collect_inputs(
    *,
    coverage: Any,
    selected_gold: tuple[ConnectionGoldEvent, ...],
    trigger_gold: TriggerGoldCatalog,
    bundle: DocumentRepresentationBundle,
    source: Source,
    document: Document,
    ledger: Any,
    archive: LocalArchiveStore,
) -> tuple[EventEntityExperimentInput, ...]:
    selected_by_id = {item.event_id: item for item in selected_gold}
    trigger_by_id = {
        item.event_id: (segment.source_text, item)
        for segment in trigger_gold.segments
        for item in segment.events
        if item.event_id in selected_by_id
    }
    node_by_id = {item.id: item for item in bundle.nodes}
    view_by_id = {item.id: item for item in bundle.text_views}
    found: dict[str, EventEntityExperimentInput] = {}
    for coverage_record in coverage.records:
        receipt = hybrid_paragraph_receipt_from_bytes(
            archive.read_hybrid_paragraph_receipt(coverage_record.receipt_id)
        )
        semantics_stage = next(
            (item for item in receipt.stages if item.stage_id is HybridStageId.HP6_EVENT_SEMANTICS),
            None,
        )
        if semantics_stage is None or semantics_stage.output_id is None:
            continue
        semantics_payload = archive.read_hybrid_event_semantics_preview(semantics_stage.output_id)
        if _sha(semantics_payload) != semantics_stage.output_sha256:
            raise ValueError("Paragraph receipt references changed Event evidence.")
        semantics = load_hybrid_event_semantics_preview(
            semantics_stage.output_id,
            ledger,
            archive,
        )
        triggers = load_hybrid_event_trigger_preview(semantics.parent_preview_id, archive)
        mention = hybrid_extraction_preview_from_bytes(
            archive.read_hybrid_extraction_preview(triggers.mention_preview_id)
        )
        references = hybrid_reference_preview_from_bytes(
            archive.read_hybrid_reference_preview(triggers.reference_preview_id)
        )
        paragraph = node_by_id[semantics.paragraph_node_id]
        text_view = view_by_id[paragraph.text_view_id]
        paragraph_text = text_view.text[paragraph.start_char : paragraph.end_char]
        segments = paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3)
        trigger_records = {item.id: item for item in triggers.triggers}
        for event in semantics.source_grounded_events:
            trigger = trigger_records[event.trigger_id]
            gold_id = _match_gold_event_id(trigger, trigger_by_id)
            if gold_id is None:
                continue
            gold = selected_by_id[gold_id]
            matching_segments = tuple(
                item
                for item in segments
                if hybrid_source_segment_id(
                    bundle.representation.id,
                    paragraph.id,
                    item,
                )
                == event.source_segment_id
            )
            if len(matching_segments) != 1:
                raise ValueError("Event does not identify one paragraph SourceSegment.")
            segment = matching_segments[0]
            selection = select_event_entity_mentions(
                source_text=segment.exact_text,
                event=event,
                mention_preview=mention,
                reference_preview=references,
            )
            prepared = EventEntityExperimentInput(
                phase=gold.phase,
                gold_event_id=gold.event_id,
                source_id=source.id,
                document_id=document.id,
                representation_id=bundle.representation.id,
                paragraph_node_id=paragraph.id,
                source_segment_label=segment.label,
                source_text=segment.exact_text,
                event_semantics_preview_id=semantics.id,
                event_semantics_preview_sha256=_sha(semantics_payload),
                event=event,
                candidate_selection=selection,
            )
            if gold_id in found and found[gold_id] != prepared:
                raise ValueError("Canonical evidence repeats one Gold Event with changed input.")
            found[gold_id] = prepared
    missing = sorted(set(selected_by_id) - set(found))
    if missing:
        raise ValueError(f"Canonical evidence is missing selected Events: {', '.join(missing)}")
    return tuple(found[key] for key in sorted(found))


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root)
    if metadata["status"] not in {"prepared", "run_complete"}:
        raise ValueError("Connection run is not prepared for execution: " + str(metadata["status"]))
    config = _config(args.config)
    if metadata["runtime"] != _runtime_contract(config):
        raise ValueError("Connection runtime configuration changed after preparation.")
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
                print(f"Connection Event {ordinal}/{len(inputs)}: reused")
                continue
            ledger = _ExperimentLedger(state.source, state.document, state.bundle)
            unit = create_analysis_unit_from_source_segment(
                SourceSegmentAnalysisUnitInput(
                    representation_id=prepared.representation_id,
                    paragraph_node_id=prepared.paragraph_node_id,
                    source_segment_label=prepared.source_segment_label,
                    policy_id=EVENT_ENTITY_CONNECTION_POLICY_ID,
                    task_type="event_entity_connection_experiment",
                ),
                ledger,
            )
            result = run_event_entity_connection_preview(
                EventEntityConnectionCommand(
                    source_id=prepared.source_id,
                    document_id=prepared.document_id,
                    representation_id=prepared.representation_id,
                    parent_preview_id=prepared.event_semantics_preview_id,
                    parent_preview_sha256=prepared.event_semantics_preview_sha256,
                    source_text=prepared.source_text,
                    event=prepared.event,
                    entity_mentions=prepared.candidate_selection.mentions,
                    candidate_gaps=prepared.candidate_selection.gaps,
                    analysis_unit=unit,
                    model_profile=_profile(config),
                    generation_parameters=_generation(config),
                    prompt_bytes=prompt,
                ),
                ledger=cast(EventEntityConnectionLedger, ledger),
                archive=cast(EventEntityConnectionArchive, archive),
                model_runtime=runtime,
                model_run_id_factory=Uuid4ModelRunIdFactory(),
                tokenizer=runtime,
            )
            if ledger.accepted_ledger_change_count:
                raise AssertionError("Connection experiment changed accepted Ledger state.")
            payload = canonical_event_entity_connection_preview_bytes(result.preview)
            if _sha(payload) != result.sha256:
                raise ValueError("Connection Preview result digest is invalid.")
            _write_json(
                output,
                {
                    "schema_version": "event_entity_connection_execution_v1",
                    "gold_event_id": prepared.gold_event_id,
                    "prepared_input": prepared.model_dump(mode="json"),
                    "preview": result.preview.model_dump(mode="json"),
                    "preview_sha256": result.sha256,
                    "model_runs": [
                        item.model_dump(mode="json")
                        for item in sorted(ledger.model_runs.values(), key=lambda value: value.id)
                    ],
                    "accepted_ledger_change_count": ledger.accepted_ledger_change_count,
                },
            )
            print(
                f"Connection Event {ordinal}/{len(inputs)}: "
                f"{result.preview.terminal_status.value} "
                f"({len(result.preview.candidates)} judgments)"
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
        raise ValueError("Connection experiment has not completed model execution.")
    _validate_static_contract(root, metadata)
    gold_path = args.gold.resolve()
    if metadata["gold_path"] != _relative_or_absolute(gold_path):
        raise ValueError("Connection Gold path changed after preparation.")
    gold_payload = gold_path.read_bytes()
    if metadata["gold_sha256"] != _sha(gold_payload):
        raise ValueError("Connection Gold changed after preparation.")
    phase = cast(str, metadata["phase"])
    catalog, _, _ = load_connection_gold_catalog(
        gold_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=phase == "validation",
    )
    gold_by_id = {item.event_id: item for item in catalog.events if item.phase == phase}
    evaluations: list[EventEntityCaseEvaluation] = []
    elapsed = 0
    event_records: dict[str, dict[str, object]] = {}
    for path in sorted((root / "events").glob("*.json")):
        record = _read_json(path)
        event_id = str(record["gold_event_id"])
        prepared = EventEntityExperimentInput.model_validate(record["prepared_input"])
        preview = EventEntityConnectionPreview.model_validate(record["preview"])
        if record.get("preview_sha256") != _sha(
            canonical_event_entity_connection_preview_bytes(preview)
        ):
            raise ValueError("Connection execution Preview digest is invalid.")
        if record.get("accepted_ledger_change_count") != 0:
            raise ValueError("Connection experiment execution changed accepted Ledger state.")
        model_runs = tuple(
            ModelRun.model_validate(raw) for raw in cast(list[object], record["model_runs"])
        )
        if {item.id for item in model_runs} != set(preview.model_run_ids):
            raise ValueError("Connection execution ModelRun evidence is incomplete.")
        evaluations.append(evaluate_event_entity_case(gold_by_id[event_id], prepared, preview))
        event_records[event_id] = record
        for model_run in model_runs:
            elapsed += _required_int(
                model_run.execution_diagnostics["elapsed_milliseconds"],
                "model elapsed milliseconds",
            )
    if set(event_records) != set(gold_by_id):
        raise ValueError("Connection execution does not cover its complete Gold phase.")
    report = build_event_entity_phase_report(
        catalog=catalog,
        catalog_sha256=_sha(gold_payload),
        phase=cast(Any, phase),
        repetition=_required_int(metadata["repetition"], "repetition"),
        evaluations=tuple(evaluations),
        model_elapsed_milliseconds=elapsed,
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    (root / "review.md").write_text(
        _render_result_review(report, gold_by_id, event_records),
        encoding="utf-8",
    )
    metadata["status"] = "finalized"
    _write_json(root / "run.json", metadata)
    evidence = [
        root / "canonical-state.json",
        root / "inputs.jsonl",
        root / "preflight.json",
        root / "preflight-review.md",
        root / "run.json",
        root / "report.json",
        root / "review.md",
        *sorted((root / "events").glob("*.json")),
    ]
    manifest = {
        "schema_version": "event_entity_connection_manifest_v1",
        "phase": report.phase,
        "repetition": report.repetition,
        "files": [
            {"path": item.relative_to(root).as_posix(), "sha256": _sha(item.read_bytes())}
            for item in evidence
        ],
    }
    _write_json(root / "manifest.json", manifest)
    if report.phase == "validation":
        (root / "FINALIZED").write_text(_sha(_canonical_json(manifest)), encoding="utf-8")
    print(
        json.dumps(
            {
                "phase": report.phase,
                "repetition": report.repetition,
                "passed": report.passed,
                "passed_event_count": report.passed_event_count,
                "event_count": report.event_count,
                "missing_entity_count": report.missing_entity_count,
                "candidate_missing_entity_count": report.candidate_missing_entity_count,
                "false_negative_entity_count": report.false_negative_entity_count,
                "extra_connection_count": report.extra_connection_count,
                "unresolved_connection_count": report.unresolved_connection_count,
                "candidate_gap_count": report.candidate_gap_count,
                "violated_exclusion_count": report.violated_exclusion_count,
                "report": str(root / "report.json"),
                "review": str(root / "review.md"),
            },
            sort_keys=True,
        )
    )
    return 0


def _compare(args: argparse.Namespace) -> int:
    if len(args.development_report) != 3:
        raise ValueError("Connection comparison requires three development reports.")
    development = tuple(
        EventEntityPhaseReport.model_validate(_read_json(path.resolve()))
        for path in args.development_report
    )
    validation = EventEntityPhaseReport.model_validate(_read_json(args.validation_report.resolve()))
    for path in (*args.development_report, args.validation_report):
        _validate_manifest(path.resolve().parent)
    if tuple(sorted(item.repetition for item in development)) != (1, 2, 3):
        raise ValueError("Development reports must cover repetitions one through three.")
    stable = len({item.result_fingerprint for item in development}) == 1
    passed = stable and all(item.passed for item in development) and validation.passed
    result = {
        "schema_version": "hsq_event_entity_connection_comparison_v1",
        "development_repetitions": [
            {
                "repetition": item.repetition,
                "passed": item.passed,
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
        "passed": passed,
    }
    _write_json(args.output.resolve(), result)
    print(json.dumps(result, sort_keys=True))
    return 0 if passed else 1


def _match_gold_event_id(
    trigger: EventTriggerDraft,
    trigger_by_id: dict[str, tuple[str, TriggerGoldEvent]],
) -> str | None:
    matches: list[str] = []
    for event_id, (source_text, gold) in trigger_by_id.items():
        if _sha(source_text.encode()) != trigger.source_text_sha256:
            continue
        source_copy = derive_source_copy_view(source_text)
        occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
        head = occurrences[gold.head_occurrence_id]
        head_span = source_copy.authoritative_range(head.start, head.end)
        expressions = {
            source_copy.authoritative_range(
                occurrences[item.start_occurrence_id].start,
                occurrences[item.end_occurrence_id].end,
            )
            for item in gold.accepted_expression_ranges
        }
        if (trigger.head_start, trigger.head_end) == head_span and (
            trigger.start,
            trigger.end,
        ) in expressions:
            matches.append(event_id)
    if len(matches) > 1:
        raise ValueError("One Event trigger matches multiple Gold Events.")
    return matches[0] if matches else None


def _render_result_review(
    report: EventEntityPhaseReport,
    gold_by_id: dict[str, ConnectionGoldEvent],
    event_records: dict[str, dict[str, object]],
) -> str:
    lines = [
        f"# Event-Entity Connection {report.phase} Review",
        "",
        f"Repetition: `{report.repetition}`",
        "",
        f"Passed Events: `{report.passed_event_count}/{report.event_count}`",
        "",
    ]
    evaluation_by_id = {item.event_id: item for item in report.events}
    for event_id in sorted(gold_by_id):
        gold = gold_by_id[event_id]
        record = event_records[event_id]
        prepared = EventEntityExperimentInput.model_validate(record["prepared_input"])
        preview = EventEntityConnectionPreview.model_validate(record["preview"])
        evaluation = evaluation_by_id[event_id]
        lines.extend(
            (
                f"## {event_id} — {'passed' if evaluation.passed else 'failed'}",
                "",
                f"Event: {gold.event_meaning}",
                "",
                "Exact SourceSegment:",
                "",
                "> " + prepared.source_text,
                "",
                "Expected entities: "
                + (", ".join(item.canonical_name for item in gold.expected_entities) or "none"),
                "",
            )
        )
        trace_by_candidate: dict[str, ExtractionStageTrace] = {}
        for trace in preview.traces:
            raw_candidate = trace.input.get("candidate")
            if not isinstance(raw_candidate, dict):
                continue
            candidate_id = raw_candidate.get("id")
            if isinstance(candidate_id, str):
                trace_by_candidate[candidate_id] = trace
        decision_by_candidate = {item.candidate_id: item for item in preview.decisions}
        for candidate in preview.candidates:
            trace = trace_by_candidate[candidate.id]
            lines.extend(
                (
                    f"### {candidate.entity_kind.value} — {candidate.entity_name}",
                    "",
                    "Exact model input:",
                    "",
                    "```text",
                    str(trace.input["exact_model_input"]),
                    "```",
                    "",
                    "Exact raw output:",
                    "",
                    "```text",
                    str(trace.output.get("raw_output_text")),
                    "```",
                    "",
                    (
                        "KoteKomi disposition: "
                        f"`{decision_by_candidate[candidate.id].disposition.value}`"
                    ),
                    "",
                )
            )
        if preview.candidate_gaps:
            lines.extend(("Candidate gaps:", ""))
            lines.extend(
                f"- `{item.reason.value}` — {json.dumps(item.mention_text, ensure_ascii=False)}"
                for item in preview.candidate_gaps
            )
            lines.append("")
        lines.extend(
            (
                f"Missing Gold entities: `{', '.join(evaluation.missing_entity_ids) or 'none'}`",
                "",
                (
                    "Missing before model judgment: "
                    f"`{', '.join(evaluation.candidate_missing_entity_ids) or 'none'}`"
                ),
                "",
                (
                    "Model false negatives: "
                    f"`{', '.join(evaluation.false_negative_entity_ids) or 'none'}`"
                ),
                "",
                f"Extra drafts: `{', '.join(evaluation.extra_draft_ids) or 'none'}`",
                "",
                (
                    "Violated contextual exclusions: "
                    f"`{', '.join(evaluation.violated_exclusion_ids) or 'none'}`"
                ),
                "",
            )
        )
    return "\n".join(lines)


def _load_metadata(root: Path) -> dict[str, Any]:
    metadata = _read_json(root / "run.json")
    if metadata.get("schema_version") != "event_entity_connection_experiment_run_v1":
        raise ValueError("Connection run metadata schema is unknown.")
    return metadata


def _validate_static_contract(root: Path, metadata: dict[str, Any]) -> None:
    gold_path = _stored_path(metadata["gold_path"], "Connection Gold")
    if metadata["gold_sha256"] != _sha(gold_path.read_bytes()):
        raise ValueError("Connection Gold changed after preparation.")
    if metadata["prompt_sha256"] != _sha(DEFAULT_PROMPT.read_bytes()):
        raise ValueError("Connection prompt changed after preparation.")
    if metadata["schema_sha256"] != _sha(entity_involvement_answer_schema_bytes()):
        raise ValueError("Connection output schema changed after preparation.")
    if metadata["schema_id"] != EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID:
        raise ValueError("Connection output schema identity changed.")
    if metadata["policy_id"] != EVENT_ENTITY_CONNECTION_POLICY_ID:
        raise ValueError("Connection policy changed after preparation.")
    for field_name, filename in (
        ("canonical_state_sha256", "canonical-state.json"),
        ("inputs_sha256", "inputs.jsonl"),
        ("preflight_sha256", "preflight.json"),
        ("preflight_review_sha256", "preflight-review.md"),
    ):
        if metadata.get(field_name) != _sha((root / filename).read_bytes()):
            raise ValueError(f"Connection {filename} changed after preparation.")
    preflight = EventEntityCandidatePreflightReport.model_validate(
        _read_json(root / "preflight.json")
    )
    if (
        preflight.catalog_sha256 != metadata["gold_sha256"]
        or preflight.gold_review_status != metadata["gold_review_status"]
        or preflight.phase != metadata["phase"]
    ):
        raise ValueError("Connection preflight lineage changed after preparation.")
    if metadata["status"] in {"prepared", "run_complete", "finalized"} and (
        metadata["gold_review_status"] != "approved" or not preflight.passed
    ):
        raise ValueError("Connection execution requires approved Gold and a passing preflight.")


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _load_canonical_state(path: Path) -> _CanonicalState:
    value = _read_json(path)
    return _CanonicalState(
        Source.model_validate(value["source"]),
        Document.model_validate(value["document"]),
        DocumentRepresentationBundle.model_validate(value["bundle"]),
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
        "endpoint": value.endpoint,
        "model": value.model,
        "timeout_seconds": value.timeout_seconds,
        "context_tokens": value.context_tokens,
        "max_output_tokens": value.max_output_tokens,
        "profile_name": value.profile_name,
    }


def _validate_manifest(root: Path) -> None:
    manifest = _read_json(root / "manifest.json")
    for raw in cast(list[dict[str, str]], manifest["files"]):
        path = (root / raw["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or _sha(path.read_bytes()) != raw["sha256"]:
            raise ValueError("Connection evidence manifest does not match its files.")
    if manifest["phase"] == "validation":
        marker = root / "FINALIZED"
        if not marker.is_file() or marker.read_text(encoding="utf-8") != _sha(
            _canonical_json(manifest)
        ):
            raise ValueError("Validation evidence lacks its immutable finalization marker.")


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
