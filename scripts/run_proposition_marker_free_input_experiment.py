#!/usr/bin/env python3
"""Run the paired marker-free proposition-input diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    MARKER_FREE_PROPOSITION_POLICY_ID,
    PARAGRAPH_SEGMENT_V3,
    ContextModelProfile,
    ExecutionSetting,
    ExtractionStageTrace,
    MarkerFreePropositionMembershipCommand,
    PropositionFragmentAnswerValue,
    PropositionFragmentCandidate,
    PropositionFragmentReason,
    PropositionFragmentTaskInputStatus,
    SourceSegmentAnalysisUnitInput,
    Uuid4ModelRunIdFactory,
    create_analysis_unit_from_source_segment,
    marker_free_proposition_fragment_model_task_input,
    run_marker_free_proposition_fragment_membership,
)
from kotekomi_application.source_grounded_proposition_preview import (
    PropositionScopeArchive,
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
from kotekomi_pipelines.event_entity_connection_stage_local import EventEntityExperimentInput
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from kotekomi_pipelines.proposition_input_format_stage_local import (
    PropositionInputFormatInventoryItem,
    PropositionInputFormatObservation,
    PropositionInputFormatReport,
    PropositionInputGoldClass,
    build_proposition_input_format_report,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT = REPOSITORY_ROOT / "prompts/source_grounded_proposition_fragment_membership_v6.md"


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
        raise AssertionError("Marker-free diagnostic cannot write accepted Ledger state.")


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
    prepare.add_argument("--baseline-run-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    prepare.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)

    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--run-root", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "run":
        return _run(args)
    return _finalize(args)


def _prepare(args: argparse.Namespace) -> int:
    baseline = args.baseline_run_root.resolve()
    root = args.run_root.resolve()
    prompt_path = args.prompt.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Marker-free prepare requires an absent or empty run root.")
    metadata = _read_json(baseline / "run.json")
    if metadata.get("status") != "finalized" or metadata.get("phase") != "development":
        raise ValueError("Marker-free diagnostic requires one finalized development baseline.")
    config = _config(args.config)
    if metadata.get("runtime") != _runtime_contract(config):
        raise ValueError("Marker-free runtime differs from the v3 baseline runtime.")
    root.mkdir(parents=True, exist_ok=True)
    baseline_binding = _baseline_binding(baseline)
    baseline_sha256 = _sha(_canonical_json(baseline_binding))
    state_payload = (baseline / "canonical-state.json").read_bytes()
    inputs_payload = (baseline / "inputs.jsonl").read_bytes()
    (root / "canonical-state.json").write_bytes(state_payload)
    (root / "inputs.jsonl").write_bytes(inputs_payload)
    preflight = _read_json(baseline / "preflight.json")
    preflight_events = tuple(
        cast(dict[str, Any], item) for item in cast(list[object], preflight["events"])
    )
    preflight_by_event = {str(item["event_id"]): item for item in preflight_events}
    inputs = _load_inputs(root / "inputs.jsonl")
    prepared_by_event = {item.gold_event_id: item for item in inputs}
    inventory: list[PropositionInputFormatInventoryItem] = []
    for event_id, prepared in sorted(prepared_by_event.items()):
        record = _read_json(baseline / "events" / f"{event_id}.json")
        candidates = tuple(
            PropositionFragmentCandidate.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["candidates"])
        )
        traces = tuple(
            ExtractionStageTrace.model_validate_json(_canonical_json(item))
            for item in cast(list[object], record["traces"])
        )
        traces_by_candidate = {
            str(cast(dict[str, Any], item.input["candidate"])["id"]): item for item in traces
        }
        event_preflight = preflight_by_event[event_id]
        compatible = set(cast(list[str], event_preflight["gold_compatible_candidate_ids"]))
        overreaching = set(cast(list[str], event_preflight["gold_overreaching_candidate_ids"]))
        for candidate in candidates:
            if PropositionFragmentReason.EVENT_EXPRESSION in candidate.reasons:
                continue
            if candidate.id in compatible:
                gold_class = PropositionInputGoldClass.COMPATIBLE
            elif candidate.id in overreaching:
                gold_class = PropositionInputGoldClass.OVERREACHING
            else:
                raise ValueError(f"Baseline preflight does not classify {candidate.id}.")
            trace = traces_by_candidate[candidate.id]
            parsed = trace.output["parsed_answer"]
            raw = trace.output["raw_output_text"]
            exact_input = trace.input["exact_model_input"]
            if (
                not isinstance(parsed, str)
                or not isinstance(raw, str)
                or not isinstance(exact_input, str)
            ):
                raise ValueError("The v3 baseline lacks one complete finite-answer trace.")
            inventory.append(
                PropositionInputFormatInventoryItem(
                    event_id=event_id,
                    source_text=prepared.source_text,
                    event_text=prepared.trigger.text,
                    candidate=candidate,
                    gold_class=gold_class,
                    task_input=marker_free_proposition_fragment_model_task_input(
                        source_text=prepared.source_text,
                        trigger=prepared.trigger,
                        candidate=candidate,
                    ),
                    baseline_exact_model_input=exact_input,
                    baseline_raw_output=raw,
                    baseline_answer=PropositionFragmentAnswerValue(parsed),
                    baseline_trace_id=trace.id,
                )
            )
    _write_jsonl(
        root / "inventory.jsonl",
        [item.model_dump(mode="json") for item in inventory],
    )
    _write_json(root / "baseline-binding.json", baseline_binding)
    prompt = prompt_path.read_bytes()
    ready_count = sum(
        item.task_input.status is PropositionFragmentTaskInputStatus.READY for item in inventory
    )
    run_metadata = {
        "schema_version": "proposition_marker_free_input_run_v1",
        "status": "prepared",
        "baseline_run_root": str(baseline),
        "baseline_run_sha256": baseline_sha256,
        "prompt_path": _relative_or_absolute(prompt_path),
        "prompt_sha256": _sha(prompt),
        "runtime": _runtime_contract(config),
        "inventory_count": len(inventory),
        "eligible_candidate_count": ready_count,
        "excluded_ambiguous_candidate_count": len(inventory) - ready_count,
        "canonical_state_sha256": _sha(state_payload),
        "inputs_sha256": _sha(inputs_payload),
        "inventory_sha256": _sha((root / "inventory.jsonl").read_bytes()),
        "baseline_binding_sha256": _sha((root / "baseline-binding.json").read_bytes()),
    }
    _write_json(root / "run.json", run_metadata)
    print(
        json.dumps(
            {
                "baseline_run_sha256": baseline_sha256,
                "eligible_candidate_count": ready_count,
                "excluded_ambiguous_candidate_count": len(inventory) - ready_count,
                "inventory_count": len(inventory),
                "run_root": str(root),
                "status": "prepared",
            },
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _load_metadata(root)
    if metadata["status"] not in {"prepared", "run_complete"}:
        raise ValueError("Marker-free diagnostic is not prepared.")
    config = _config(args.config)
    if metadata["runtime"] != _runtime_contract(config):
        raise ValueError("Marker-free runtime changed after preparation.")
    _validate_static_contract(root, metadata)
    state = _load_canonical_state(root / "canonical-state.json")
    inputs = _load_inputs(root / "inputs.jsonl")
    prepared_by_event = {item.gold_event_id: item for item in inputs}
    inventory = _load_inventory(root / "inventory.jsonl")
    inventory_by_event: dict[str, list[PropositionInputFormatInventoryItem]] = {}
    for item in inventory:
        inventory_by_event.setdefault(item.event_id, []).append(item)
    output_root = root / "observations"
    output_root.mkdir(parents=True, exist_ok=True)
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    prompt = _stored_path(metadata["prompt_path"], "Marker-free prompt").read_bytes()
    completed = 0
    try:
        for event_ordinal, event_id in enumerate(sorted(inventory_by_event), start=1):
            prepared = prepared_by_event[event_id]
            ledger = _ExperimentLedger(state.source, state.document, state.bundle)
            unit = create_analysis_unit_from_source_segment(
                SourceSegmentAnalysisUnitInput(
                    representation_id=prepared.representation_id,
                    paragraph_node_id=prepared.paragraph_node_id,
                    source_segment_label=prepared.source_segment_label,
                    policy_id=MARKER_FREE_PROPOSITION_POLICY_ID,
                    task_type="proposition_fragment_membership_marker_free_diagnostic",
                    source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
                ),
                ledger,
            )
            ordered = sorted(
                inventory_by_event[event_id],
                key=lambda item: (
                    item.candidate.start,
                    item.candidate.end,
                    item.candidate.id,
                ),
            )
            for candidate_ordinal, item in enumerate(ordered):
                output = output_root / event_id / f"{item.candidate.id}.json"
                if output.exists():
                    _validate_observation_output(output, item)
                    completed += 1
                    continue
                result = run_marker_free_proposition_fragment_membership(
                    MarkerFreePropositionMembershipCommand(
                        source_id=prepared.source_id,
                        document_id=prepared.document_id,
                        representation_id=prepared.representation_id,
                        source_text=prepared.source_text,
                        event=prepared.event,
                        trigger=prepared.trigger,
                        candidate=item.candidate,
                        analysis_unit=unit,
                        model_profile=_profile(config),
                        generation_parameters=_generation(config),
                        prompt_bytes=prompt,
                        ordinal=candidate_ordinal,
                    ),
                    ledger=cast(PropositionScopeLedger, ledger),
                    archive=cast(PropositionScopeArchive, archive),
                    model_runtime=runtime,
                    model_run_id_factory=Uuid4ModelRunIdFactory(),
                    tokenizer=runtime,
                )
                raw_output = result.trace.output.get("raw_output_text")
                exact_input = result.trace.input.get("exact_model_input")
                observation = PropositionInputFormatObservation(
                    event_id=item.event_id,
                    candidate_id=item.candidate.id,
                    source_text=item.source_text,
                    source_text_sha256=item.candidate.source_text_sha256,
                    event_text=item.event_text,
                    candidate_start=item.candidate.start,
                    candidate_end=item.candidate.end,
                    candidate_text=item.candidate.text,
                    gold_class=item.gold_class,
                    task_input=result.task_input,
                    baseline_exact_model_input=item.baseline_exact_model_input,
                    baseline_raw_output=item.baseline_raw_output,
                    baseline_answer=item.baseline_answer,
                    baseline_trace_id=item.baseline_trace_id,
                    marker_free_exact_model_input=(
                        exact_input if isinstance(exact_input, str) else None
                    ),
                    marker_free_raw_output=(raw_output if isinstance(raw_output, str) else None),
                    marker_free_answer=(result.answer.value if result.answer is not None else None),
                    marker_free_execution_status=(
                        "not_run"
                        if result.task_input.status
                        is PropositionFragmentTaskInputStatus.OCCURRENCE_AMBIGUOUS
                        else ("completed" if result.answer is not None else "failed")
                    ),
                    marker_free_trace_id=result.trace.id,
                    marker_free_model_run_id=result.model_run_id,
                )
                extraction_task = (
                    ledger.extraction_tasks[result.extraction_task_id]
                    if result.extraction_task_id is not None
                    else None
                )
                model_run = (
                    ledger.model_runs[result.model_run_id]
                    if result.model_run_id is not None
                    else None
                )
                payload: dict[str, object] = {
                    "schema_version": "proposition_marker_free_observation_output_v1",
                    "observation": observation.model_dump(mode="json"),
                    "trace": result.trace.model_dump(mode="json"),
                    "extraction_task": (
                        extraction_task.model_dump(mode="json")
                        if extraction_task is not None
                        else None
                    ),
                    "model_run": (
                        model_run.model_dump(mode="json") if model_run is not None else None
                    ),
                    "accepted_ledger_change_count": ledger.accepted_ledger_change_count,
                }
                payload["payload_sha256"] = _sha(_canonical_json(payload))
                _write_json(output, payload)
                completed += 1
            print(
                f"Marker-free Event {event_ordinal}/{len(inventory_by_event)}: "
                f"{completed}/{len(inventory)} observations"
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
        raise ValueError("Marker-free diagnostic has not completed execution.")
    _validate_static_contract(root, metadata)
    inventory = _load_inventory(root / "inventory.jsonl")
    observations: list[PropositionInputFormatObservation] = []
    model_elapsed_milliseconds = 0
    model_execution_count = 0
    for item in inventory:
        path = root / "observations" / item.event_id / f"{item.candidate.id}.json"
        observation, model_run = _validate_observation_output(path, item)
        observations.append(observation)
        if model_run is not None:
            model_execution_count += 1
            elapsed = model_run.execution_diagnostics["elapsed_milliseconds"]
            if isinstance(elapsed, bool) or not isinstance(elapsed, int):
                raise ValueError("Marker-free ModelRun elapsed time is invalid.")
            model_elapsed_milliseconds += elapsed
    report = build_proposition_input_format_report(
        baseline_run_sha256=str(metadata["baseline_run_sha256"]),
        prompt_sha256=str(metadata["prompt_sha256"]),
        observations=tuple(observations),
    )
    report_path = root / "report.json"
    review_path = root / "review.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(_render_review(report), encoding="utf-8")
    manifest = {
        "schema_version": "proposition_marker_free_input_manifest_v1",
        "report_sha256": _sha(report_path.read_bytes()),
        "review_sha256": _sha(review_path.read_bytes()),
        "model_execution_count": model_execution_count,
        "model_elapsed_milliseconds": model_elapsed_milliseconds,
        "accepted_ledger_change_count": 0,
        "hypothesis_outcome": report.hypothesis_outcome.value,
        "production_integration": "not_activated",
        "completed": True,
    }
    _write_json(root / "manifest.json", manifest)
    (root / "FINALIZED").write_text(_sha(_canonical_json(manifest)), encoding="utf-8")
    metadata["status"] = "finalized"
    _write_json(root / "run.json", metadata)
    print(
        json.dumps(
            {
                "baseline_metrics": report.baseline_metrics.model_dump(mode="json"),
                "excluded_ambiguous_candidate_count": (report.excluded_ambiguous_candidate_count),
                "hypothesis_outcome": report.hypothesis_outcome.value,
                "marker_free_metrics": report.marker_free_metrics.model_dump(mode="json"),
                "model_elapsed_milliseconds": model_elapsed_milliseconds,
                "model_execution_count": model_execution_count,
                "report": str(report_path),
                "review": str(review_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _validate_observation_output(
    path: Path,
    expected: PropositionInputFormatInventoryItem,
) -> tuple[PropositionInputFormatObservation, ModelRun | None]:
    payload = _read_json(path)
    digest = payload.pop("payload_sha256", None)
    if digest != _sha(_canonical_json(payload)):
        raise ValueError(f"Marker-free observation digest is invalid: {path}")
    if payload.get("schema_version") != "proposition_marker_free_observation_output_v1":
        raise ValueError(f"Marker-free observation schema is unknown: {path}")
    observation = PropositionInputFormatObservation.model_validate_json(
        _canonical_json(payload["observation"])
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical_json(payload["trace"]))
    if observation.candidate_id != expected.candidate.id:
        raise ValueError(f"Marker-free observation candidate drifted: {path}")
    if observation.task_input != expected.task_input:
        raise ValueError(f"Marker-free observation task input drifted: {path}")
    if observation.marker_free_trace_id != trace.id:
        raise ValueError(f"Marker-free observation trace drifted: {path}")
    if payload.get("accepted_ledger_change_count") != 0:
        raise ValueError(f"Marker-free observation changed accepted state: {path}")
    extraction_task_payload = payload.get("extraction_task")
    model_run_payload = payload.get("model_run")
    if extraction_task_payload is None and model_run_payload is None:
        if observation.marker_free_model_run_id is not None:
            raise ValueError(f"Marker-free blocked observation names a ModelRun: {path}")
        return observation, None
    if extraction_task_payload is None or model_run_payload is None:
        raise ValueError(f"Marker-free observation has partial execution evidence: {path}")
    extraction_task = ExtractionTask.model_validate_json(_canonical_json(extraction_task_payload))
    model_run = ModelRun.model_validate_json(_canonical_json(model_run_payload))
    if (
        observation.marker_free_model_run_id != model_run.id
        or extraction_task.id not in trace.execution_record_ids
        or model_run.id not in trace.execution_record_ids
    ):
        raise ValueError(f"Marker-free observation execution lineage drifted: {path}")
    return observation, model_run


def _baseline_binding(root: Path) -> dict[str, object]:
    paths = (
        root / "run.json",
        root / "report.json",
        root / "manifest.json",
        root / "preflight.json",
        root / "canonical-state.json",
        root / "inputs.jsonl",
        *sorted((root / "events").glob("*.json")),
    )
    if any(not path.is_file() for path in paths):
        raise ValueError("The v3 baseline is missing required finalized evidence.")
    return {
        "schema_version": "proposition_marker_free_baseline_binding_v1",
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha(path.read_bytes()),
            }
            for path in paths
        ],
    }


def _render_review(report: PropositionInputFormatReport) -> str:
    lines = [
        "# Marker-Free Proposition Input Review",
        "",
        f"Hypothesis outcome: `{report.hypothesis_outcome.value}`",
        "",
        f"Eligible paired candidates: `{report.eligible_candidate_count}`",
        "",
        (f"Excluded repeated-literal candidates: `{report.excluded_ambiguous_candidate_count}`"),
        "",
        "## Paired metrics",
        "",
        f"Baseline accuracy: `{report.baseline_metrics.accuracy:.6f}`",
        "",
        f"Marker-free accuracy: `{report.marker_free_metrics.accuracy:.6f}`",
        "",
        f"Baseline F1: `{report.baseline_metrics.f1:.6f}`",
        "",
        f"Marker-free F1: `{report.marker_free_metrics.f1:.6f}`",
        "",
    ]
    for item in report.observations:
        lines.extend(
            (
                f"## {item.event_id} / {item.candidate_id}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {item.source_text}",
                "",
                f"Event: `{item.event_text}`",
                "",
                f"Candidate: `{item.candidate_text}`",
                "",
                f"Gold class: `{item.gold_class.value}`",
                "",
                f"Marker-free input status: `{item.task_input.status.value}`",
                "",
                f"Baseline answer: `{item.baseline_answer.value}`",
                "",
            )
        )
        if item.task_input.status is PropositionFragmentTaskInputStatus.READY:
            lines.extend(
                (
                    "Exact marker-free model input:",
                    "",
                    "~~~~text",
                    item.marker_free_exact_model_input or "",
                    "~~~~",
                    "",
                    f"Raw marker-free output: `{item.marker_free_raw_output}`",
                    "",
                    (
                        "Parsed marker-free answer: `"
                        + (
                            item.marker_free_answer.value
                            if item.marker_free_answer is not None
                            else "none"
                        )
                        + "`"
                    ),
                    "",
                )
            )
        else:
            lines.extend(
                (
                    f"Typed exclusion: `{item.task_input.reason_code}`",
                    "",
                    (f"Candidate occurrence count: `{item.task_input.candidate_occurrence_count}`"),
                    "",
                    f"Event occurrence count: `{item.task_input.event_occurrence_count}`",
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def _load_metadata(root: Path) -> dict[str, Any]:
    metadata = _read_json(root / "run.json")
    if metadata.get("schema_version") != "proposition_marker_free_input_run_v1":
        raise ValueError("Marker-free run metadata schema is unknown.")
    return metadata


def _validate_static_contract(root: Path, metadata: dict[str, Any]) -> None:
    prompt = _stored_path(metadata["prompt_path"], "Marker-free prompt")
    for field, path in (
        ("prompt_sha256", prompt),
        ("canonical_state_sha256", root / "canonical-state.json"),
        ("inputs_sha256", root / "inputs.jsonl"),
        ("inventory_sha256", root / "inventory.jsonl"),
        ("baseline_binding_sha256", root / "baseline-binding.json"),
    ):
        if metadata[field] != _sha(path.read_bytes()):
            raise ValueError(f"Marker-free pinned input changed: {path}")
    inventory = _load_inventory(root / "inventory.jsonl")
    if metadata["inventory_count"] != len(inventory):
        raise ValueError("Marker-free inventory count changed.")


def _load_inventory(path: Path) -> tuple[PropositionInputFormatInventoryItem, ...]:
    return tuple(
        PropositionInputFormatInventoryItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


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
