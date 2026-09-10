#!/usr/bin/env python3
"""Run HSQ-7 mention/reference experiments without downstream ingestion stages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from kotekomi_adapters import FCorefAdapter, FCorefConfig, GlinerMentionProposer, LocalArchiveStore
from kotekomi_adapters.model_resources import (
    fcoref_expected_resource_identity,
    fcoref_model_path,
    fcoref_python_path,
    gliner_model_path,
)
from kotekomi_application import (
    ContextModelProfile,
    CoreferenceExecution,
    CoreferenceInput,
    ExecutionSetting,
    HybridMentionPreviewCommand,
    HybridPreviewStatus,
    HybridReferencePreviewCommand,
    Uuid4ModelRunIdFactory,
    run_hybrid_mention_preview,
    run_hybrid_reference_preview,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
)
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
    HYBRID_MENTION_BOUNDARY_ADJUDICATION_SCHEMA_ID,
    boundary_candidate_judgment_schema_bytes,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HYBRID_MENTION_BOUNDARY_POLICY_ID,
    HYBRID_MENTION_INTERPRETATION_SCHEMA_ID,
    HYBRID_MENTION_PREVIEW_POLICY_ID,
    HYBRID_MENTION_PROPOSAL_SCHEMA_ID,
    HybridExtractionPreview,
    mention_interpretation_schema_bytes,
    mention_proposal_schema_bytes,
)
from kotekomi_application.hybrid_mention_preview import HybridMentionArchive, HybridMentionLedger
from kotekomi_application.hybrid_reference_preview import (
    HybridReferenceArchive,
    HybridReferenceLedger,
)
from kotekomi_application.mention_proposer import (
    MentionProposalBatch,
    MentionProposalInput,
    MentionProposer,
)
from kotekomi_application.semantic_reference_challenge_model_output import (
    semantic_reference_challenge_schema_bytes,
)
from kotekomi_application.semantic_reference_validation_model_output import (
    semantic_reference_candidate_validation_schema_bytes,
)
from kotekomi_application.semantic_references import (
    SEMANTIC_REFERENCE_POLICY_ID,
    CoreferenceProposerPort,
    CoreferenceTokenizer,
)
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ExtractionTask,
    ModelRun,
    ParseQualityReport,
    RepresentationAnalyzability,
    Source,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from kotekomi_pipelines.task_allocation_stage_local import (
    StageLocalCaseEvaluation,
    StageLocalInput,
    StageLocalPhase,
    build_stage_local_report,
    evaluate_stage_local_boundary_contract,
    evaluate_stage_local_case,
    load_stage_local_inputs,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT = REPOSITORY_ROOT / "docs" / "hsq-stage-local-split-v2.json"
EVALUATOR_CORRECTIONS = REPOSITORY_ROOT / "docs" / "hsq-stage-local-evaluator-corrections-v1.json"
_FIXED_TIME = datetime(2026, 9, 9, tzinfo=UTC)


class _ExperimentLedger:
    """Narrow ephemeral repository that rejects every accepted-state write."""

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
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.context_manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
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
        self, *, model_run: ModelRun, batch: object
    ) -> None:
        del model_run, batch
        self.accepted_ledger_change_count += 1
        raise AssertionError("Stage-local evaluation cannot write ProposedChanges.")

    def to_json(self) -> dict[str, object]:
        return {
            "source": self.source.model_dump(mode="json"),
            "document": self.document.model_dump(mode="json"),
            "bundle": self.bundle.model_dump(mode="json"),
            "analysis_units": [
                item.model_dump(mode="json")
                for item in sorted(self.analysis_units.values(), key=lambda value: value.id)
            ],
            "context_manifests": [
                item.model_dump(mode="json")
                for item in sorted(self.context_manifests.values(), key=lambda value: value.id)
            ],
            "extraction_tasks": [
                item.model_dump(mode="json")
                for item in sorted(self.extraction_tasks.values(), key=lambda value: value.id)
            ],
            "model_runs": [
                item.model_dump(mode="json")
                for item in sorted(self.model_runs.values(), key=lambda value: value.id)
            ],
            "accepted_ledger_change_count": self.accepted_ledger_change_count,
        }

    @classmethod
    def from_json(cls, value: dict[str, object]) -> _ExperimentLedger:
        ledger = cls(
            Source.model_validate_json(_canonical_json(value["source"])),
            Document.model_validate_json(_canonical_json(value["document"])),
            DocumentRepresentationBundle.model_validate_json(_canonical_json(value["bundle"])),
        )
        ledger.analysis_units = {
            item.id: item
            for item in (
                AnalysisUnitArtifact.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["analysis_units"])
            )
        }
        ledger.context_manifests = {
            item.id: item
            for item in (
                ContextManifestArtifact.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["context_manifests"])
            )
        }
        ledger.extraction_tasks = {
            item.id: item
            for item in (
                ExtractionTask.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["extraction_tasks"])
            )
        }
        ledger.model_runs = {
            item.id: item
            for item in (
                ModelRun.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["model_runs"])
            )
        }
        ledger.accepted_ledger_change_count = cast(int, value["accepted_ledger_change_count"])
        return ledger


@dataclass(frozen=True)
class _PreparedRun:
    root: Path
    phase: StageLocalPhase
    inputs: tuple[StageLocalInput, ...]


class _FixtureMentionProposer:
    """Explicit no-candidate proposer for fast runner contract tests."""

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        del proposal_input
        return MentionProposalBatch(
            proposer_id="hsq-stage-local-fixture:1",
            model_id="hsq-stage-local-fixture",
            model_revision="1",
            configuration=(),
            load_elapsed_milliseconds=0,
            inference_elapsed_milliseconds=0,
            proposals=(),
        )


class _FixtureCoreference:
    tokenizer_id = "hsq-stage-local-fixture-tokenizer"

    def count_tokens(self, rendered_input: bytes) -> int:
        return max(1, len(rendered_input.decode("utf-8").split()))

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        del request
        return CoreferenceExecution(
            model_id="hsq-stage-local-fixture",
            model_revision="1",
            resource_identity="hsq-stage-local-fixture",
            clusters=(),
            elapsed_milliseconds=0,
            raw_output=b'{"clusters":[]}',
        )

    def close(self) -> None:
        return None


class _CoreferenceRuntime(CoreferenceProposerPort, CoreferenceTokenizer, Protocol):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    _common_run_arguments(prepare, needs_config=False)
    mentions = subparsers.add_parser("run-mentions")
    _common_run_arguments(mentions, needs_config=True)
    references = subparsers.add_parser("run-references")
    _common_run_arguments(references, needs_config=True)
    finalize = subparsers.add_parser("finalize")
    _common_run_arguments(finalize, needs_config=False)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--development-report", type=Path, required=True)
    compare.add_argument("--validation-report", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "run-mentions":
        return _run_mentions(args)
    if args.command == "run-references":
        return _run_references(args)
    if args.command == "finalize":
        return _finalize(args)
    return _compare(args)


def _common_run_arguments(parser: argparse.ArgumentParser, *, needs_config: bool) -> None:
    parser.add_argument("--phase", choices=("development", "validation"), required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument(
        "--item-id",
        action="append",
        default=[],
        help="Prepare a diagnostic subset; later commands reuse the prepared item IDs.",
    )
    if needs_config:
        parser.add_argument("--config", type=Path, required=True)


def _prepare(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    if run_root.exists() and any(run_root.iterdir()):
        raise ValueError("Stage-local prepare requires an absent or empty run root.")
    run_root.mkdir(parents=True, exist_ok=True)
    _, inputs = load_stage_local_inputs(args.split.resolve(), repository_root=REPOSITORY_ROOT)
    selected = _select_run_inputs(inputs, phase=args.phase, item_ids=tuple(args.item_id))
    _write_jsonl(run_root / "inputs.jsonl", [item.model_dump(mode="json") for item in selected])
    metadata = {
        "schema_version": "hsq_stage_local_run_v2",
        "phase": args.phase,
        "split_path": _relative_or_absolute(args.split.resolve()),
        "split_sha256": _sha(args.split.read_bytes()),
        "item_count": len(selected),
        "item_ids": [item.item.item_id for item in selected],
        "unique_source_segment_count": len({item.source_text_sha256 for item in selected}),
        "experiment": _experiment_contract(),
        "status": "prepared",
    }
    _write_json(run_root / "run.json", metadata)
    print(json.dumps(metadata, sort_keys=True))
    return 0


def _run_mentions(args: argparse.Namespace) -> int:
    prepared = _load_prepared(args)
    _require_not_finalized(prepared)
    config = _config(args.config)
    archive = LocalArchiveStore(prepared.root / "archive")
    archive.initialize()
    proposer: MentionProposer = (
        _FixtureMentionProposer()
        if config.model_execution.adapter == "fixture"
        else GlinerMentionProposer(model_directory=gliner_model_path(config.model_resource_root))
    )
    runtime = build_model_task_runtime(config.model_execution)
    profile = _profile(config)
    prompts = _prompts()
    unique_inputs = _unique_segment_inputs(prepared.inputs)
    try:
        for ordinal, stage_input in enumerate(unique_inputs, start=1):
            target = prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
            if target.exists():
                print(f"Mention segment {ordinal}/{len(unique_inputs)}: reused")
                continue
            ledger = _synthetic_ledger(stage_input)
            result = run_hybrid_mention_preview(
                command=HybridMentionPreviewCommand(
                    representation_id=ledger.bundle.representation.id,
                    paragraph_node_id=_paragraph_node(ledger.bundle).id,
                    model_profile=profile,
                    generation_parameters=_generation(config),
                ),
                ledger=cast(HybridMentionLedger, ledger),
                archive=cast(HybridMentionArchive, archive),
                proposer=proposer,
                model_runtime=runtime,
                model_run_id_factory=Uuid4ModelRunIdFactory(),
                tokenizer=runtime,
                proposal_prompt_bytes=prompts["proposal"],
                boundary_adjudication_prompt_bytes=prompts["boundary_adjudication"],
                interpretation_prompt_bytes=prompts["interpretation"],
                ontology_card_bytes=prompts["ontology"],
            )
            if ledger.accepted_ledger_change_count:
                raise AssertionError("Mention evaluation changed accepted Ledger state.")
            _write_json(
                prepared.root / "state" / f"{stage_input.source_text_sha256}.json",
                ledger.to_json(),
            )
            _write_json(
                target,
                _stage_record(
                    stage_input=stage_input,
                    preview=result.preview.model_dump(mode="json"),
                    ledger=ledger,
                    archive=archive,
                    stage="mentions",
                ),
            )
            print(
                f"Mention segment {ordinal}/{len(unique_inputs)}: "
                f"{result.preview.terminal_status.value}"
            )
    finally:
        _close_runtime(runtime)
    _update_run_status(prepared.root, "mentions_complete")
    return 0


def _run_references(args: argparse.Namespace) -> int:
    prepared = _load_prepared(args)
    _require_not_finalized(prepared)
    _require_run_status(prepared.root, "mentions_complete")
    config = _config(args.config)
    archive = LocalArchiveStore(prepared.root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    root = config.model_resource_root
    coreference: _CoreferenceRuntime = (
        _FixtureCoreference()
        if config.model_execution.adapter == "fixture"
        else FCorefAdapter(
            FCorefConfig(
                python_executable=fcoref_python_path(root),
                worker_script=(REPOSITORY_ROOT / "scripts" / "fcoref_worker.py").resolve(),
                model_directory=fcoref_model_path(root).resolve(),
                resource_identity=fcoref_expected_resource_identity(),
            )
        )
    )
    prompts = _prompts()
    unique_inputs = _unique_segment_inputs(prepared.inputs)
    try:
        for ordinal, stage_input in enumerate(unique_inputs, start=1):
            target = prepared.root / "references" / f"{stage_input.source_text_sha256}.json"
            if target.exists():
                print(f"Reference segment {ordinal}/{len(unique_inputs)}: reused")
                continue
            related = tuple(
                item
                for item in prepared.inputs
                if item.source_text_sha256 == stage_input.source_text_sha256
            )
            if not any(item.item.expected_references for item in related):
                _write_json(
                    target,
                    {
                        "schema_version": "hsq_stage_local_execution_v1",
                        "stage": "references",
                        "source_text_sha256": stage_input.source_text_sha256,
                        "status": "not_applicable",
                        "preview": None,
                        "model_executions": [],
                    },
                )
                print(f"Reference segment {ordinal}/{len(unique_inputs)}: not applicable")
                continue
            ledger = _ExperimentLedger.from_json(
                _read_json(prepared.root / "state" / f"{stage_input.source_text_sha256}.json")
            )
            mention_record = _read_json(
                prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
            )
            mention = HybridExtractionPreview.model_validate_json(
                _canonical_json(mention_record["preview"])
            )
            before_ids = set(ledger.model_runs)
            if mention.terminal_status is HybridPreviewStatus.BLOCKED:
                reference_preview = None
                status = "parent_blocked"
            else:
                result = run_hybrid_reference_preview(
                    command=HybridReferencePreviewCommand(
                        mention.id,
                        model_profile=_profile(config),
                        generation_parameters=_generation(config),
                    ),
                    ledger=cast(HybridReferenceLedger, ledger),
                    archive=cast(HybridReferenceArchive, archive),
                    coreference_proposer=coreference,
                    coreference_tokenizer=coreference,
                    model_runtime=runtime,
                    model_run_id_factory=Uuid4ModelRunIdFactory(),
                    challenge_prompt_bytes=prompts["reference_selection"],
                    validation_prompt_bytes=prompts["reference_validation"],
                )
                reference_preview = result.preview
                status = "complete"
            if ledger.accepted_ledger_change_count:
                raise AssertionError("Reference evaluation changed accepted Ledger state.")
            _write_json(
                prepared.root / "state" / f"{stage_input.source_text_sha256}.json",
                ledger.to_json(),
            )
            _write_json(
                target,
                {
                    "schema_version": "hsq_stage_local_execution_v1",
                    "stage": "references",
                    "source_text_sha256": stage_input.source_text_sha256,
                    "status": status,
                    "preview": (
                        reference_preview.model_dump(mode="json")
                        if reference_preview is not None
                        else None
                    ),
                    "model_executions": _model_execution_records(
                        ledger, archive, set(ledger.model_runs) - before_ids
                    ),
                },
            )
            print(f"Reference segment {ordinal}/{len(unique_inputs)}: {status}")
    finally:
        close_coreference = getattr(coreference, "close", None)
        if callable(close_coreference):
            close_coreference()
        _close_runtime(runtime)
    _update_run_status(prepared.root, "references_complete")
    return 0


def _finalize(args: argparse.Namespace) -> int:
    prepared = _load_prepared(args)
    _require_not_finalized(prepared)
    _require_run_status(prepared.root, "references_complete")
    evaluations: list[StageLocalCaseEvaluation] = []
    elapsed: dict[str, int] = {}
    alias_opportunity_items = 0
    alias_opportunity_segments: set[str] = set()
    mention_by_source_digest: dict[str, HybridExtractionPreview] = {}
    for stage_input in prepared.inputs:
        mention_record = _read_json(
            prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
        )
        reference_record = _read_json(
            prepared.root / "references" / f"{stage_input.source_text_sha256}.json"
        )
        mention = HybridExtractionPreview.model_validate_json(
            _canonical_json(mention_record["preview"])
        )
        mention_by_source_digest[stage_input.source_text_sha256] = mention
        reference_value = reference_record.get("preview")
        references = (
            HybridReferencePreview.model_validate_json(_canonical_json(reference_value))
            if reference_value is not None
            else None
        )
        evaluation = evaluate_stage_local_case(stage_input, mention, references)
        evaluations.append(evaluation)
        if evaluation.first_failed_stage == "mention_proposal":
            alias_opportunity_items += 1
            alias_opportunity_segments.add(stage_input.source_text_sha256)
    avoidable_interpretations = 0
    for stage_input in _unique_segment_inputs(prepared.inputs):
        mention_record = _read_json(
            prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
        )
        mention = HybridExtractionPreview.model_validate_json(
            _canonical_json(mention_record["preview"])
        )
        related_inputs = tuple(
            item
            for item in prepared.inputs
            if item.source_text_sha256 == stage_input.source_text_sha256
        )
        required_candidate_ids = {
            candidate.id
            for candidate in mention.candidates
            if candidate.source_text_sha256 == stage_input.source_text_sha256
            and any(_candidate_is_required(candidate.text, item) for item in related_inputs)
        }
        avoidable_interpretations += sum(
            item.candidate_id not in required_candidate_ids for item in mention.interpretations
        )
    for path in sorted((prepared.root / "mentions").glob("*.json")) + sorted(
        (prepared.root / "references").glob("*.json")
    ):
        executions = cast(list[dict[str, object]], _read_json(path).get("model_executions", []))
        for execution in executions:
            producer = str(execution["producer"])
            elapsed[producer] = elapsed.get(producer, 0) + _required_int(
                execution["elapsed_milliseconds"], "model elapsed milliseconds"
            )
    for path in sorted((prepared.root / "references").glob("*.json")):
        preview = _read_json(path).get("preview")
        if isinstance(preview, dict):
            preview_object = cast(dict[str, object], preview)
            observations = cast(
                list[dict[str, object]],
                preview_object.get("coreference_observations", []),
            )
            for observation in observations:
                producer = str(observation["model_id"])
                elapsed[producer] = elapsed.get(producer, 0) + _required_int(
                    observation["elapsed_milliseconds"],
                    "specialist elapsed milliseconds",
                )
    report = build_stage_local_report(
        phase=prepared.phase,
        evaluations=tuple(evaluations),
        producer_elapsed_milliseconds=elapsed,
        boundary_contract=evaluate_stage_local_boundary_contract(
            tuple(mention_by_source_digest[key] for key in sorted(mention_by_source_digest))
        ),
        optional_experiment_measurements={
            "source_alias_rescue_opportunity_item_count": alias_opportunity_items,
            "source_alias_rescue_opportunity_segment_count": len(alias_opportunity_segments),
            "selective_interpretation_avoidable_call_count": avoidable_interpretations,
        },
    )
    payload = report.model_dump(mode="json")
    report_path = prepared.root / "report.json"
    _write_json(report_path, payload)
    _write_review(prepared.root / "review.md", prepared.inputs, payload)
    evidence_paths = [
        prepared.root / "inputs.jsonl",
        report_path,
        prepared.root / "review.md",
        *sorted((prepared.root / "mentions").glob("*.json")),
        *sorted((prepared.root / "references").glob("*.json")),
    ]
    manifest = {
        "schema_version": "hsq_stage_local_manifest_v1",
        "phase": prepared.phase,
        "files": [
            {
                "path": path.relative_to(prepared.root).as_posix(),
                "sha256": _sha(path.read_bytes()),
            }
            for path in evidence_paths
        ],
    }
    _write_json(prepared.root / "manifest.json", manifest)
    if prepared.phase == "validation":
        (prepared.root / "FINALIZED").write_text(_sha(_canonical_json(manifest)), encoding="utf-8")
    _update_run_status(prepared.root, "finalized")
    print(
        json.dumps(
            {
                "phase": prepared.phase,
                "passed_count": payload["passed_count"],
                "item_count": payload["item_count"],
                "first_failed_stage_counts": payload["first_failed_stage_counts"],
                "report": str(report_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _compare(args: argparse.Namespace) -> int:
    _validate_evidence_manifest(args.development_report.resolve().parent)
    _validate_evidence_manifest(args.validation_report.resolve().parent, require_marker=True)
    development = _read_json(args.development_report)
    validation = _read_json(args.validation_report)
    result = {
        "schema_version": "hsq_stage_local_comparison_v1",
        "development": _comparison_summary(development),
        "validation": _comparison_summary(validation),
        "quality_regression_gate": "manual_baseline_comparison_required",
        "production_adoption": {
            "source_alias_rescue": "not_activated",
            "selective_interpretation": "not_activated",
        },
    }
    _write_json(args.output.resolve(), result)
    print(json.dumps(result, sort_keys=True))
    return 0


def _load_prepared(args: argparse.Namespace) -> _PreparedRun:
    root = args.run_root.resolve()
    if (root / "FINALIZED").exists():
        _validate_evidence_manifest(root, require_marker=True)
    metadata = _read_json(root / "run.json")
    if metadata.get("phase") != args.phase:
        raise ValueError("Stage-local run phase does not match its prepared metadata.")
    selected_split = args.split.resolve()
    if metadata.get("split_path") != _relative_or_absolute(selected_split):
        raise ValueError("Stage-local run split path changed after preparation.")
    if metadata.get("split_sha256") != _sha(selected_split.read_bytes()):
        raise ValueError("Stage-local run split bytes changed after preparation.")
    if metadata.get("experiment") != _experiment_contract():
        raise ValueError("Stage-local prompt, schema, or policy changed after preparation.")
    inputs = tuple(
        StageLocalInput.model_validate_json(line)
        for line in (root / "inputs.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    )
    _, current_inputs = load_stage_local_inputs(
        selected_split,
        repository_root=REPOSITORY_ROOT,
    )
    raw_item_ids = metadata.get("item_ids")
    if not isinstance(raw_item_ids, list):
        raise ValueError("Stage-local run metadata does not contain valid item IDs.")
    item_id_values = cast(list[object], raw_item_ids)
    if not all(isinstance(item, str) for item in item_id_values):
        raise ValueError("Stage-local run metadata does not contain valid item IDs.")
    item_ids = tuple(cast(list[str], item_id_values))
    if args.item_id and tuple(args.item_id) != item_ids:
        raise ValueError("Stage-local command item IDs differ from the prepared run.")
    expected_inputs = _select_run_inputs(
        current_inputs,
        phase=args.phase,
        item_ids=item_ids,
    )
    if inputs != expected_inputs:
        raise ValueError("Stage-local prepared inputs changed or no longer match the split.")
    if not inputs or any(item.phase != args.phase for item in inputs):
        raise ValueError("Stage-local prepared inputs are incomplete.")
    phase = cast(StageLocalPhase, args.phase)
    return _PreparedRun(root, phase, inputs)


def _require_not_finalized(prepared: _PreparedRun) -> None:
    if (prepared.root / "FINALIZED").exists():
        raise ValueError("A finalized validation run is immutable.")


def _validate_evidence_manifest(root: Path, *, require_marker: bool = False) -> None:
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != "hsq_stage_local_manifest_v1":
        raise ValueError("Stage-local evidence manifest schema is unknown.")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("Stage-local evidence manifest has no files.")
    files = cast(list[object], raw_files)
    seen: set[str] = set()
    for value in files:
        if not isinstance(value, dict):
            raise ValueError("Stage-local evidence manifest entry is invalid.")
        entry = cast(dict[str, object], value)
        relative = entry.get("path")
        digest = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
        ):
            raise ValueError("Stage-local evidence manifest entry is unsafe or duplicated.")
        seen.add(relative)
        evidence_path = root / relative
        if not evidence_path.is_file() or _sha(evidence_path.read_bytes()) != digest:
            raise ValueError(f"Stage-local evidence changed after finalization: {relative}")
    marker = root / "FINALIZED"
    if require_marker:
        expected_marker = _sha(manifest_path.read_bytes())
        if not marker.is_file() or marker.read_text(encoding="utf-8") != expected_marker:
            raise ValueError("Stage-local validation finalization marker is missing or invalid.")


def _require_run_status(root: Path, expected: str) -> None:
    observed = _read_json(root / "run.json").get("status")
    if observed != expected:
        raise ValueError(f"Stage-local run requires status {expected}; found {observed}.")


def _update_run_status(root: Path, status: str) -> None:
    metadata = _read_json(root / "run.json")
    metadata["status"] = status
    _write_json(root / "run.json", metadata)


def _unique_segment_inputs(inputs: tuple[StageLocalInput, ...]) -> tuple[StageLocalInput, ...]:
    by_sha: dict[str, StageLocalInput] = {}
    for item in inputs:
        existing = by_sha.setdefault(item.source_text_sha256, item)
        if existing.source_text != item.source_text:
            raise ValueError("One SourceSegment SHA-256 identifies conflicting text.")
    return tuple(by_sha[key] for key in sorted(by_sha))


def _select_run_inputs(
    inputs: tuple[StageLocalInput, ...],
    *,
    phase: StageLocalPhase,
    item_ids: tuple[str, ...],
) -> tuple[StageLocalInput, ...]:
    phase_inputs = tuple(item for item in inputs if item.phase == phase)
    if not item_ids:
        return phase_inputs
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("Stage-local diagnostic item IDs must be distinct.")
    by_id = {item.item.item_id: item for item in phase_inputs}
    unknown = set(item_ids) - set(by_id)
    if unknown:
        raise ValueError(
            "Stage-local diagnostic items are absent from the selected phase: "
            + ", ".join(sorted(unknown))
        )
    return tuple(by_id[item_id] for item_id in item_ids)


def _candidate_is_required(candidate_text: str, stage_input: StageLocalInput) -> bool:
    candidate = _normalized_literal(candidate_text)
    focus_literals = {_normalized_literal(stage_input.focus_entity_name)}
    if stage_input.focus_record_type == "Actor":
        focus_literals.add(
            _normalized_literal(stage_input.focus_entity_name.rsplit(" ", maxsplit=1)[-1])
        )
    reference_literals = {
        _normalized_literal(item.reference_text) for item in stage_input.item.expected_references
    }
    return candidate in focus_literals | reference_literals


def _normalized_literal(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    if normalized.endswith(("'s", "’s")):
        normalized = normalized[:-2]
    return normalized.removeprefix("the ")


def _synthetic_ledger(stage_input: StageLocalInput) -> _ExperimentLedger:
    digest = stage_input.source_text_sha256
    suffix = digest[:24]
    source = Source(
        id=f"src_{suffix}",
        source_type=SourceType.MANUAL_FILE,
        identity_policy_id="hsq_stage_local_source_v1",
        canonical_identity_key=f"hsq-stage-local:{digest}",
    )
    document = Document(id=f"doc_{suffix}", source_id=source.id, content_sha256=digest)
    representation_id = f"rep_{suffix}"
    text_view = TextView(
        id=f"tvw_{suffix}",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=digest,
        text=stage_input.source_text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id=f"nod_{suffix}_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(stage_input.source_text),
    )
    paragraph = DocumentNode(
        id=f"nod_{suffix}_paragraph",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(stage_input.source_text),
    )
    quality = ParseQualityReport(
        id=f"pqr_{suffix}",
        representation_id=representation_id,
        metric_values={"text_char_count": len(stage_input.source_text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document.id,
        parser_name="hsq-stage-local",
        parser_version="1",
        parser_config_digest=_sha(b"hsq-stage-local-v1"),
        processing_task_fingerprint_id=f"ptf_{suffix}",
        input_blob_digest=digest,
        canonical_output_digest="0" * 64,
        created_at=_FIXED_TIME,
    )
    nodes = (root, paragraph)
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=nodes,
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    bundle = DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=nodes,
        quality_report=quality,
    )
    return _ExperimentLedger(source, document, bundle)


def _paragraph_node(bundle: DocumentRepresentationBundle) -> DocumentNode:
    return next(item for item in bundle.nodes if item.node_type == "paragraph")


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


def _prompts() -> dict[str, bytes]:
    prompt_root = REPOSITORY_ROOT / "prompts"
    return {
        "proposal": (prompt_root / "hybrid_mention_occurrence_selection_v2.md").read_bytes(),
        "boundary_adjudication": (
            prompt_root / "hybrid_mention_boundary_adjudication_v2.md"
        ).read_bytes(),
        "interpretation": (prompt_root / "hybrid_mention_interpretation_task_v2.md").read_bytes(),
        "ontology": (prompt_root / "hybrid_mention_ontology_card_v1.md").read_bytes(),
        "reference_selection": (prompt_root / "semantic_reference_challenge_v4.md").read_bytes(),
        "reference_validation": (
            prompt_root / "semantic_reference_candidate_validation_v1.md"
        ).read_bytes(),
    }


def _experiment_contract() -> dict[str, object]:
    prompts = _prompts()
    policies = {
        "mention_boundary": HYBRID_MENTION_BOUNDARY_POLICY_ID,
        "mention_boundary_adjudication": HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
        "mention_preview": HYBRID_MENTION_PREVIEW_POLICY_ID,
        "semantic_reference": SEMANTIC_REFERENCE_POLICY_ID,
    }
    return {
        "experiment_id": "hsq7_stage_local_contrastive_reference_v10",
        "parent_experiment_id": "hsq7_stage_local_adaptive_reference_v9",
        "changed_hypotheses": [
            "h17_complete_catalog_contrastive_fallback",
        ],
        "prompt_sha256": {name: _sha(payload) for name, payload in sorted(prompts.items())},
        "schema_sha256": {
            HYBRID_MENTION_PROPOSAL_SCHEMA_ID: _sha(mention_proposal_schema_bytes()),
            HYBRID_MENTION_BOUNDARY_ADJUDICATION_SCHEMA_ID: _sha(
                boundary_candidate_judgment_schema_bytes()
            ),
            HYBRID_MENTION_INTERPRETATION_SCHEMA_ID: _sha(mention_interpretation_schema_bytes()),
            "semantic_reference_challenge_text_v2": _sha(
                semantic_reference_challenge_schema_bytes()
            ),
            "semantic_reference_candidate_validation_text_v1": _sha(
                semantic_reference_candidate_validation_schema_bytes()
            ),
        },
        "policy_sha256": _sha(_canonical_json(policies)),
        "evaluator_correction_sha256": _sha(EVALUATOR_CORRECTIONS.read_bytes()),
        "optional_hypotheses": {
            "h6_source_alias_rescue": "measured_not_activated",
            "h7_selective_interpretation": "measured_not_activated",
        },
    }


def _stage_record(
    *,
    stage_input: StageLocalInput,
    preview: dict[str, object],
    ledger: _ExperimentLedger,
    archive: LocalArchiveStore,
    stage: str,
) -> dict[str, object]:
    model_executions = _model_execution_records(ledger, archive, set(ledger.model_runs))
    trace_input_by_run = {
        str(execution_id): trace["input"].get("model_visible_input")
        for trace in cast(list[dict[str, Any]], preview.get("traces", []))
        for execution_id in cast(list[str], trace.get("execution_record_ids", []))
        if isinstance(trace.get("input"), dict)
        and isinstance(cast(dict[str, object], trace["input"]).get("model_visible_input"), str)
    }
    for execution in model_executions:
        if execution["exact_model_input"] is None:
            execution["exact_model_input"] = trace_input_by_run.get(str(execution["model_run_id"]))
    return {
        "schema_version": "hsq_stage_local_execution_v1",
        "stage": stage,
        "source_text_sha256": stage_input.source_text_sha256,
        "exact_input": stage_input.source_text,
        "preview": preview,
        "model_executions": model_executions,
        "accepted_ledger_change_count": ledger.accepted_ledger_change_count,
    }


def _model_execution_records(
    ledger: _ExperimentLedger,
    archive: LocalArchiveStore,
    run_ids: set[str],
) -> list[dict[str, object]]:
    task_by_id = {item.id: item for item in ledger.extraction_tasks.values()}
    records: list[dict[str, object]] = []
    for run_id in sorted(run_ids):
        run = ledger.model_runs[run_id]
        task = task_by_id[run.extraction_task_id]
        try:
            raw_output = archive.read_model_run_output(run.id).decode("utf-8")
        except FileNotFoundError:
            raw_output = None
        records.append(
            {
                "extraction_task_id": task.id,
                "model_run_id": run.id,
                "task_type": task.task_type,
                "producer": str(run.model_identity.get("name", "unknown")),
                "status": run.status.value,
                "elapsed_milliseconds": _required_int(
                    run.execution_diagnostics["elapsed_milliseconds"],
                    "ModelRun elapsed milliseconds",
                ),
                "exact_model_input": _model_visible_input(task),
                "raw_output": raw_output,
                "raw_output_sha256": run.output_digest,
                "parsed_outcome_metadata": run.outcome_metadata,
            }
        )
    return records


def _model_visible_input(task: ExtractionTask) -> str | None:
    import base64

    task_payload = cast(dict[str, object], task.context_manifest_payload)
    rendered_input_base64 = task_payload.get("rendered_input_base64")
    if not isinstance(rendered_input_base64, str):
        return None
    context = base64.b64decode(rendered_input_base64)
    task_local_base64 = task_payload.get("task_local_input_base64")
    if not isinstance(task_local_base64, str) or not task_local_base64:
        return context.decode("utf-8")
    local = base64.b64decode(task_local_base64)
    return (context + b"\n\n[task]\n" + local).decode("utf-8")


def _write_review(
    path: Path,
    inputs: tuple[StageLocalInput, ...],
    report: dict[str, object],
) -> None:
    by_id = {item.item.item_id: item for item in inputs}
    lines = [
        f"# HSQ-7 {report['phase']} stage-local review",
        "",
        f"Passed: {report['passed_count']}/{report['item_count']}",
        "",
        "Boundary output-contract coverage:",
        "",
        "```json",
        json.dumps(report["boundary_contract"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    for result in cast(list[dict[str, object]], report["cases"]):
        stage_input = by_id[str(result["item_id"])]
        lines.extend(
            (
                f"## {result['item_id']}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {stage_input.source_text}",
                "",
                f"Expected: {stage_input.item.expected_summary}",
                "",
                f"First failed stage: {result['first_failed_stage'] or 'none'}",
                "",
                "Exact execution evidence:",
                "",
                f"- `mentions/{stage_input.source_text_sha256}.json`",
                f"- `references/{stage_input.source_text_sha256}.json`",
                "",
            )
        )
        for check in cast(list[dict[str, object]], result["checks"]):
            lines.extend(
                (
                    f"### {check['stage_id']} — {'pass' if check['passed'] else 'fail'}",
                    "",
                    "Expected:",
                    "",
                    "```json",
                    json.dumps(check["expected"], ensure_ascii=False, indent=2, sort_keys=True),
                    "```",
                    "",
                    "Actual:",
                    "",
                    "```json",
                    json.dumps(check["actual"], ensure_ascii=False, indent=2, sort_keys=True),
                    "```",
                    "",
                )
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _comparison_summary(value: dict[str, object]) -> dict[str, object]:
    return {
        "passed_count": value["passed_count"],
        "item_count": value["item_count"],
        "first_failed_stage_counts": value["first_failed_stage_counts"],
        "producer_elapsed_milliseconds": value["producer_elapsed_milliseconds"],
        "optional_experiment_measurements": value.get("optional_experiment_measurements", {}),
        "boundary_contract": value["boundary_contract"],
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(_canonical_json(value))
    os.replace(temporary, path)


def _write_jsonl(path: Path, values: list[object]) -> None:
    payload = b"".join(_canonical_json(value) + b"\n" for value in values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, Any], value)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_or_absolute(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path)


def _required_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer.")
    return value


def _close_runtime(runtime: object) -> None:
    close = getattr(runtime, "close", None)
    if callable(close):
        close()


if __name__ == "__main__":
    raise SystemExit(main())
