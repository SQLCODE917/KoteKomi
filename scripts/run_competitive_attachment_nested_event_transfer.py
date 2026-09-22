#!/usr/bin/env python3
"""Run the CEA-1.23 Nested Event ownership transfer experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from base64 import b64encode
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_adapters import LocalArchiveStore
from kotekomi_application import (
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
    ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
    PARAGRAPH_SEGMENT_V3,
    AttachmentEdgeFilterCommand,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentNestedEventReport,
    AttachmentNestedTransferCase,
    AttachmentNestedTransferCatalog,
    AttachmentNestedTransferObservation,
    AttachmentNestedTransferSelectorCatalog,
    AttachmentNestedTransferSubmission,
    ContextModelProfile,
    ExecutionSetting,
    ExtractionStageTrace,
    RetrievalSelectionAnalysisUnitInput,
    SourceSegmentAnalysisUnitInput,
    Uuid4ModelRunIdFactory,
    attachment_nested_event_ownership_model_task_input,
    create_analysis_unit_from_retrieval_selection,
    create_analysis_unit_from_source_segment,
    run_attachment_edge_filter,
)
from kotekomi_application.competitive_attachment_edge_filter_preview import (
    AttachmentEdgeFilterArchive,
    AttachmentEdgeFilterLedger,
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
from kotekomi_pipelines.competitive_attachment_nested_event_transfer import (
    build_attachment_nested_transfer_catalog,
    build_attachment_nested_transfer_report,
    render_attachment_nested_transfer_blind_request,
    render_attachment_nested_transfer_catalog,
    render_attachment_nested_transfer_handoff,
    render_attachment_nested_transfer_review,
    validate_attachment_nested_transfer_submission,
)
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime

ROOT = Path(__file__).resolve().parents[1]
TDD = ROOT / "docs/2026-09-21-competitive-attachment-nested-event-transfer.md"
PROGRAM = ROOT / "docs/2026-09-18-competitive-event-attachment-program.md"
SELECTORS = ROOT / "docs/cea123-nested-event-transfer-catalog-v1.json"
PROMPT = ROOT / "prompts/competitive_attachment_nested_event_ownership_v1.md"
OUTPUT_TOKEN_LIMIT = 2
_FIXED_TIME = datetime(2026, 9, 21, tzinfo=UTC)


class _ExperimentLedger:
    """Ephemeral repository that rejects accepted-state writes."""

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
        self,
        *,
        model_run: ModelRun,
        batch: object,
    ) -> None:
        del model_run, batch
        self.accepted_ledger_change_count += 1
        raise AssertionError("CEA-1.23 cannot write accepted Ledger state.")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--predecessor-root", type=Path, required=True)
    prepare.add_argument("--run-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    run.add_argument("--review-response", type=Path, required=True)
    args = parser.parse_args()
    return {"prepare": _prepare, "run": _run}[args.command](args)


def _prepare(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CEA-1.23 prepare requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    predecessor_root = args.predecessor_root.resolve()
    predecessor = _validated_predecessor(predecessor_root)
    selectors = AttachmentNestedTransferSelectorCatalog.model_validate_json(SELECTORS.read_bytes())
    source_catalog_path = ROOT / selectors.source_catalog_path
    if _sha_file(source_catalog_path) != selectors.source_catalog_sha256:
        raise ValueError("CEA-1.23 reviewed SourceSegment catalog digest drifted.")
    source_catalog = _read_json(source_catalog_path)
    prompt = _reference("frozen_prompt", PROMPT)
    predecessor_prompt = next(item for item in predecessor.inputs if item.label == "preflight")
    preflight = _read_json(Path(predecessor_prompt.path))
    predecessor_prompt_value = preflight.get("prompt")
    if not isinstance(predecessor_prompt_value, dict):
        raise ValueError("CEA-1.22 preflight lacks its Frozen Prompt reference.")
    predecessor_prompt_reference = cast(dict[str, object], predecessor_prompt_value)
    if predecessor_prompt_reference.get("sha256") != prompt.sha256:
        raise ValueError("CEA-1.23 Frozen Prompt drifted from CEA-1.22.")
    inputs = tuple(
        sorted(
            (
                _reference("predecessor_handoff", predecessor_root / "second-opinion-handoff.md"),
                _reference("predecessor_report", predecessor_root / "report.json"),
                _reference("predecessor_review", predecessor_root / "comparison-review.md"),
                _reference(
                    "predecessor_second_opinion", predecessor_root / "claude-opus-review.md"
                ),
                _reference("program", PROGRAM),
                _reference("selector_catalog", SELECTORS),
                _reference("source_catalog", source_catalog_path),
                _reference("tdd", TDD),
            ),
            key=lambda item: item.label,
        )
    )
    catalog = build_attachment_nested_transfer_catalog(
        selector_catalog=selectors,
        source_catalog=source_catalog,
        inputs=inputs,
        prompt=prompt,
    )
    catalog_path = root / "catalog.json"
    catalog_review_path = root / "catalog-review.md"
    blind_request_path = root / "blind-review-request.md"
    _write_json(catalog_path, catalog.model_dump(mode="json"))
    catalog_review_path.write_text(
        render_attachment_nested_transfer_catalog(catalog),
        encoding="utf-8",
    )
    blind_request_path.write_text(
        render_attachment_nested_transfer_blind_request(catalog),
        encoding="utf-8",
    )
    metadata = {
        "schema_version": "attachment_nested_transfer_run_v1",
        "status": "prepared",
        "predecessor_root": str(predecessor_root),
        "prompt_path": str(PROMPT),
        "prompt_sha256": prompt.sha256,
        "prompt_id": ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
        "task_renderer_id": ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
        "effective_max_output_tokens": OUTPUT_TOKEN_LIMIT,
        "catalog_fingerprint": catalog.result_fingerprint,
        "catalog_sha256": _sha_file(catalog_path),
        "catalog_review_sha256": _sha_file(catalog_review_path),
        "blind_request_sha256": _sha_file(blind_request_path),
        "production_integration": "not_activated",
    }
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        {
            "schema_version": "attachment_nested_transfer_status_v1",
            "status": "awaiting_blind_review",
            "run_root": str(root),
            "catalog": str(catalog_path),
            "blind_review_request": str(blind_request_path),
            "blind_review_response": str(root / "blind-review-response.json"),
        },
    )
    print(
        json.dumps(
            {
                "status": "awaiting_blind_review",
                "run_root": str(root),
                "catalog": str(catalog_path),
                "review_request": str(blind_request_path),
                "review_response": str(root / "blind-review-response.json"),
            },
            sort_keys=True,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    metadata = _read_json(root / "run.json")
    if metadata.get("status") not in {"prepared", "running", "complete"}:
        raise ValueError("CEA-1.23 run metadata is not prepared.")
    catalog_path = root / "catalog.json"
    catalog_review_path = root / "catalog-review.md"
    blind_request_path = root / "blind-review-request.md"
    catalog = AttachmentNestedTransferCatalog.model_validate_json(catalog_path.read_bytes())
    if (
        catalog.result_fingerprint != metadata.get("catalog_fingerprint")
        or _sha_file(catalog_path) != metadata.get("catalog_sha256")
        or _sha_file(catalog_review_path) != metadata.get("catalog_review_sha256")
        or _sha_file(blind_request_path) != metadata.get("blind_request_sha256")
    ):
        raise ValueError("CEA-1.23 prepared evidence drifted.")
    for reference in (*catalog.inputs, catalog.prompt):
        _validate_reference(reference)
    response_bytes = args.review_response.resolve().read_bytes()
    submission = AttachmentNestedTransferSubmission.model_validate_json(response_bytes)
    validate_attachment_nested_transfer_submission(catalog, submission)
    response_path = root / "blind-review-response.json"
    if response_path.exists() and response_path.read_bytes() != response_bytes:
        raise ValueError("CEA-1.23 blind review response changed after execution began.")
    response_path.write_bytes(response_bytes)
    raw_response_path = root / "blind-review-response.raw.md"
    raw_response_reference = (
        _reference("blind_review_response_raw", raw_response_path)
        if raw_response_path.is_file()
        else None
    )
    config = _config(args.config)
    runtime_contract = cea14.attachment_edge_filter_runtime_contract(config)
    generation = _generation(config)
    generation_payload = _generation_payload(generation)
    stored_runtime_contract = metadata.get("runtime_contract")
    if stored_runtime_contract is not None and stored_runtime_contract != runtime_contract:
        raise ValueError("CEA-1.23 runtime contract drifted.")
    stored_generation = metadata.get("generation_parameters")
    if stored_generation is not None and stored_generation != generation_payload:
        raise ValueError("CEA-1.23 generation settings drifted.")
    metadata.update(
        {
            "status": "running",
            "config_path": str(args.config.resolve()),
            "runtime_contract": runtime_contract,
            "generation_parameters": generation_payload,
            "blind_review_response_sha256": _sha(response_bytes),
            "blind_review_response_raw_sha256": (
                raw_response_reference.sha256 if raw_response_reference is not None else None
            ),
        }
    )
    _write_json(root / "run.json", metadata)
    execute_attachment_nested_transfer_tasks(
        root=root,
        config=config,
        catalog=catalog,
        metadata=metadata,
        generation=generation,
        prompt=PROMPT.read_bytes(),
        prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
        task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
        model_task_input=attachment_nested_event_ownership_model_task_input,
        progress_label="Nested transfer case",
        policy_id="competitive_attachment_nested_transfer_v1",
        task_type="competitive_attachment_nested_transfer",
    )
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    observations = tuple(
        load_attachment_nested_transfer_observation(
            path=root / "executions" / f"{case.task.task_id}.json",
            archive=archive,
            config=config,
            case=case,
            prompt_sha256=catalog.prompt.sha256,
            prompt_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_PROMPT_ID,
            task_renderer_id=ATTACHMENT_NESTED_EVENT_OWNERSHIP_RENDERER_ID,
            model_task_input=attachment_nested_event_ownership_model_task_input,
        )
        for case in catalog.cases
    )
    identities = {
        item.model_identity_digest
        for item in observations
        if item.model_identity_digest is not None
    }
    if len(identities) > 1:
        raise ValueError("CEA-1.23 used more than one model identity.")
    report = build_attachment_nested_transfer_report(
        inputs=(
            _reference("catalog", catalog_path),
            _reference("catalog_review", catalog_review_path),
            _reference("blind_review_request", blind_request_path),
            _reference("blind_review_response", response_path),
            *((raw_response_reference,) if raw_response_reference is not None else ()),
            *tuple(
                sorted(
                    (item.execution_record for item in observations),
                    key=lambda item: item.label,
                )
            ),
        ),
        catalog=catalog,
        submission=submission,
        observations=observations,
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    handoff_path = root / "second-opinion-handoff.md"
    _write_json(report_path, report.model_dump(mode="json"))
    prompt_text = PROMPT.read_text(encoding="utf-8")
    review_path.write_text(
        render_attachment_nested_transfer_review(report, prompt_text=prompt_text),
        encoding="utf-8",
    )
    package_files = tuple(
        sorted(
            (
                *catalog.inputs,
                catalog.prompt,
                *report.inputs,
                _reference(
                    "application_contract",
                    ROOT / "packages/application/src/kotekomi_application/"
                    "competitive_attachment_nested_event_transfer.py",
                ),
                _reference(
                    "pipeline_policy",
                    ROOT / "packages/pipelines/src/kotekomi_pipelines/"
                    "competitive_attachment_nested_event_transfer.py",
                ),
                _reference("report", report_path),
                _reference("review", review_path),
                _reference("runner", Path(__file__)),
            ),
            key=lambda item: item.label,
        )
    )
    handoff_path.write_text(
        render_attachment_nested_transfer_handoff(
            report,
            prompt_text=prompt_text,
            package_files=package_files,
            source_repository_url="https://github.com/SQLCODE917/KoteKomi",
            source_revision=_git_revision(),
        ),
        encoding="utf-8",
    )
    metadata.update(
        {
            "status": "complete",
            "report_fingerprint": report.result_fingerprint,
            "report_sha256": _sha_file(report_path),
            "review_sha256": _sha_file(review_path),
            "handoff_sha256": _sha_file(handoff_path),
        }
    )
    _write_json(root / "run.json", metadata)
    _write_json(
        root / "status.json",
        {
            "schema_version": "attachment_nested_transfer_status_v1",
            "status": "complete",
            "outcome": report.outcome.value,
            "run_root": str(root),
            "report": str(report_path),
            "review": str(review_path),
            "handoff": str(handoff_path),
            "claude_review": str(root / "claude-opus-review.md"),
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "outcome": report.outcome.value,
                "run_root": str(root),
                "report": str(report_path),
                "review": str(review_path),
                "handoff": str(handoff_path),
            },
            sort_keys=True,
        )
    )
    return 0


def execute_attachment_nested_transfer_tasks(
    *,
    root: Path,
    config: PipelineConfig,
    catalog: AttachmentNestedTransferCatalog,
    metadata: dict[str, Any],
    generation: tuple[ExecutionSetting, ...],
    prompt: bytes,
    prompt_id: str,
    task_renderer_id: str,
    model_task_input: Callable[[AttachmentEdgeFilterTask], bytes],
    progress_label: str,
    policy_id: str,
    task_type: str,
    exact_source_context: bool = False,
    effective_max_output_tokens: int = OUTPUT_TOKEN_LIMIT,
) -> None:
    output_directory = root / "executions"
    output_directory.mkdir(parents=True, exist_ok=True)
    archive = LocalArchiveStore(root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    if _sha(prompt) != catalog.prompt.sha256:
        raise ValueError("Nested transfer execution changed the frozen semantic prompt.")
    for ordinal, case in enumerate(catalog.cases, start=1):
        output = output_directory / f"{case.task.task_id}.json"
        if output.exists():
            cea14.validate_attachment_edge_filter_execution_record(
                output,
                case.task,
                archive=archive,
                expected_prompt_sha256=catalog.prompt.sha256,
                expected_runtime_contract=cast(dict[str, object], metadata["runtime_contract"]),
                expected_prompt_id=prompt_id,
                expected_task_renderer_id=task_renderer_id,
            )
            print(f"{progress_label} {ordinal}/{len(catalog.cases)}: reused")
            continue
        ledger = _synthetic_ledger(case.task.source_text)
        paragraph = next(item for item in ledger.bundle.nodes if item.node_type == "paragraph")
        if exact_source_context:
            unit = create_analysis_unit_from_retrieval_selection(
                RetrievalSelectionAnalysisUnitInput(
                    representation_id=ledger.bundle.representation.id,
                    focus_node_ids=(paragraph.id,),
                    policy_id=policy_id,
                    task_type=task_type,
                ),
                ledger,
            )
        else:
            unit = create_analysis_unit_from_source_segment(
                SourceSegmentAnalysisUnitInput(
                    representation_id=ledger.bundle.representation.id,
                    paragraph_node_id=paragraph.id,
                    source_segment_label="s1",
                    policy_id=policy_id,
                    task_type=task_type,
                    source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
                ),
                ledger,
            )
        result = run_attachment_edge_filter(
            AttachmentEdgeFilterCommand(
                source_id=ledger.source.id,
                document_id=ledger.document.id,
                representation_id=ledger.bundle.representation.id,
                task=case.task,
                analysis_unit=unit,
                model_profile=_profile(config),
                generation_parameters=generation,
                prompt_bytes=prompt,
                prompt_id=prompt_id,
                task_renderer_id=task_renderer_id,
                source_segment_policy_id=(None if exact_source_context else PARAGRAPH_SEGMENT_V3),
                effective_max_output_tokens=effective_max_output_tokens,
            ),
            ledger=cast(AttachmentEdgeFilterLedger, ledger),
            archive=cast(AttachmentEdgeFilterArchive, archive),
            model_runtime=runtime,
            model_run_id_factory=Uuid4ModelRunIdFactory(),
            tokenizer=runtime,
        )
        if ledger.accepted_ledger_change_count:
            raise AssertionError("CEA-1.23 changed accepted Ledger state.")
        _write_json(
            output,
            {
                "schema_version": "attachment_edge_filter_execution_v1",
                "task": case.task.model_dump(mode="json"),
                "decision": result.decision.model_dump(mode="json"),
                "trace": result.trace.model_dump(mode="json"),
                "extraction_task": ledger.extraction_tasks[result.extraction_task_id].model_dump(
                    mode="json"
                ),
                "model_run": ledger.model_runs[result.model_run_id].model_dump(mode="json"),
                "result_sha256": result.sha256,
                "prompt_sha256": _sha(prompt),
                "runtime_contract": metadata["runtime_contract"],
                "accepted_ledger_change_count": 0,
            },
        )
        print(f"{progress_label} {ordinal}/{len(catalog.cases)}: {result.decision.status.value}")

        trace = result.trace
        visible_task = trace.input.get("model_visible_task")
        if visible_task != model_task_input(case.task).decode():
            raise ValueError("Nested transfer execution used another model-visible task.")


def load_attachment_nested_transfer_observation(
    *,
    path: Path,
    archive: LocalArchiveStore,
    config: PipelineConfig,
    case: AttachmentNestedTransferCase,
    prompt_sha256: str,
    prompt_id: str,
    task_renderer_id: str,
    model_task_input: Callable[[AttachmentEdgeFilterTask], bytes],
) -> AttachmentNestedTransferObservation:
    decision, value = cea14.validate_attachment_edge_filter_execution_record(
        path,
        case.task,
        archive=archive,
        expected_prompt_sha256=prompt_sha256,
        expected_runtime_contract=cea14.attachment_edge_filter_runtime_contract(config),
        expected_prompt_id=prompt_id,
        expected_task_renderer_id=task_renderer_id,
    )
    trace = ExtractionStageTrace.model_validate_json(_canonical(value["trace"]))
    model_run = ModelRun.model_validate_json(_canonical(value["model_run"]))
    exact_input = trace.input.get("exact_model_input")
    visible_task = trace.input.get("model_visible_task")
    if not isinstance(exact_input, str) or not isinstance(visible_task, str):
        raise ValueError("CEA-1.23 execution lacks exact model input evidence.")
    if visible_task != model_task_input(case.task).decode():
        raise ValueError("CEA-1.23 model-visible task drifted.")
    raw_output = (
        archive.read_model_run_output(model_run.id) if model_run.output_digest is not None else None
    )
    admission = model_run.input_admission
    identity = (
        admission.model_identity_digest
        if admission is not None and admission.status.value == "ready"
        else None
    )
    return AttachmentNestedTransferObservation(
        case_id=case.id,
        decision=decision,
        execution_record=_reference(f"execution_{case.id}", path),
        exact_model_input=exact_input,
        raw_output_base64=(b64encode(raw_output).decode() if raw_output is not None else None),
        model_identity_digest=identity,
        elapsed_milliseconds=_elapsed_milliseconds(model_run),
        runtime_invoked=model_run.runtime_invoked,
    )


def _synthetic_ledger(source_text: str) -> _ExperimentLedger:
    digest = _sha(source_text.encode())
    suffix = digest[:24]
    source = Source(
        id=f"src_{suffix}",
        source_type=SourceType.MANUAL_FILE,
        identity_policy_id="cea123_transfer_source_v1",
        canonical_identity_key=f"cea123-transfer:{digest}",
    )
    document = Document(id=f"doc_{suffix}", source_id=source.id, content_sha256=digest)
    representation_id = f"rep_{suffix}"
    text_view = TextView(
        id=f"tvw_{suffix}",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=digest,
        text=source_text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id=f"nod_{suffix}_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(source_text),
    )
    paragraph = DocumentNode(
        id=f"nod_{suffix}_paragraph",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(source_text),
    )
    quality = ParseQualityReport(
        id=f"pqr_{suffix}",
        representation_id=representation_id,
        metric_values={"text_char_count": len(source_text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document.id,
        parser_name="cea123-transfer",
        parser_version="1",
        parser_config_digest=_sha(b"cea123-transfer-v1"),
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


def _validated_predecessor(root: Path) -> AttachmentNestedEventReport:
    status = _read_json(root / "status.json")
    if (
        status.get("schema_version") != "attachment_nested_event_status_v1"
        or status.get("status") != "complete"
        or status.get("outcome") != "supported"
    ):
        raise ValueError("CEA-1.23 requires the completed supported CEA-1.22 package.")
    report_path = root / "report.json"
    if status.get("report") not in {None, str(report_path)}:
        raise ValueError("CEA-1.22 status references another report.")
    if not (root / "claude-opus-review.md").is_file():
        raise ValueError("CEA-1.23 requires the completed CEA-1.22 second opinion.")
    report = AttachmentNestedEventReport.model_validate_json(report_path.read_bytes())
    for reference in report.inputs:
        _validate_reference(reference)
    return report


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
        ExecutionSetting(key="frequency_penalty", value=0.0),
        ExecutionSetting(key="max_output_tokens", value=config.model_execution.max_output_tokens),
        ExecutionSetting(key="seed", value=17),
        ExecutionSetting(key="temperature", value=0),
        ExecutionSetting(key="top_logprobs", value=10),
    )


def _generation_payload(values: tuple[ExecutionSetting, ...]) -> dict[str, object]:
    return {item.key: item.value for item in values}


def _elapsed_milliseconds(model_run: ModelRun) -> int:
    value = model_run.execution_diagnostics.get("elapsed_milliseconds")
    if type(value) is not int or value < 0:
        raise ValueError("CEA-1.23 execution lacks elapsed milliseconds.")
    return value


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"CEA-1.23 evidence is missing: {label}.")
    return AttachmentEvidenceReference(
        label=label,
        path=str(resolved),
        sha256=_sha_file(resolved),
    )


def _validate_reference(reference: AttachmentEvidenceReference) -> None:
    path = Path(reference.path)
    if not path.is_file() or _sha_file(path) != reference.sha256:
        raise ValueError(f"CEA-1.23 evidence digest drifted: {reference.label}.")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha(path.read_bytes())


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
