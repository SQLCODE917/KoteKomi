"""Prepare, execute, and seal the ORG-R2 semantic qualification comparison."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters.refined_organization_type import (
    REFINED_ENTITY_SET,
    REFINED_MODEL_ID,
    REFINED_MODEL_REVISION,
    REFINED_PACKAGE_REVISION,
    REFINED_RESOURCE_MANIFEST_SHA256,
    RefinedContextualOrganizationTypeAdapter,
    RefinedWorkerConfig,
    RefinedWorkerError,
)
from kotekomi_application.context_planning import (
    DIRECT_PROSE_EVIDENCE_SELECTION_V1,
    AnalysisUnitPlanningInput,
    ContextManifest,
    ContextManifestInput,
    ContextModelProfile,
    build_context_manifest,
    plan_analysis_units,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    build_extraction_stage_trace,
    extraction_stage_trace_to_json,
)
from kotekomi_application.organization_mention_boundary_reconciliation import (
    MentionBoundaryDecisionStatus,
)
from kotekomi_application.organization_semantic_qualification import (
    QWEN_ORGANIZATION_QUALIFICATION_POLICY_ID,
    REFINED_ORGANIZATION_TYPE_MAPPING_POLICY_ID,
    ContextualOrganizationTypeInput,
    OrganizationQualificationExecutionStatus,
    OrganizationQualificationJudgment,
    QualificationCandidate,
    build_organization_qualification_decision,
    map_contextual_type_evidence,
)
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    ExecutionSetting,
    ModelExecutionSpec,
    OrganizationQualificationLabelTaskSchemaRegistry,
    StagedExtractionLedger,
    Uuid4ModelRunIdFactory,
    run_bounded_extraction,
)
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ModelRunStatus,
    ParseQualityReport,
    RepresentationAnalyzability,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from kotekomi_pipelines.config import load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from organization_semantic_qualification_evaluation import (
    QUALIFICATION_EXECUTION_SCHEMA_VERSION,
    append_execution_record,
    build_qualification_catalog,
    canonical_json,
    score_qualification_executions,
    seal_bundle,
    write_canonical_jsonl,
)
from php1_diagnostic_support import DiagnosticTokenizer, RecordingRuntime
from verify_organization_boundary_reconciliation import run as run_boundary_evaluation

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts/paragraph_organization_qualification_v2.md"
REPETITIONS = 3
QWEN_MAX_OUTPUT_TOKENS = 16


def prepare(
    *,
    proposal_report_path: Path,
    gold_catalog_path: Path,
    output_dir: Path,
    phase: str,
) -> dict[str, Any]:
    """Rebuild and retain the immutable ORG-R2 input catalog."""
    if phase == "held_out" and output_dir.exists():
        raise FileExistsError("Held-out ORG-R2 evidence cannot reuse an output directory.")
    boundary = run_boundary_evaluation(proposal_report_path, gold_catalog_path, phase=phase)
    boundary_bytes = (canonical_json(boundary) + "\n").encode("utf-8")
    catalog = build_qualification_catalog(
        boundary,
        phase=phase,
        boundary_evaluation_sha256=hashlib.sha256(boundary_bytes).hexdigest(),
    )
    records = tuple(
        sorted(
            (
                *(
                    {"record_type": "source", **source}
                    for source in cast(list[dict[str, Any]], catalog["sources"])
                ),
                *(
                    {"record_type": "candidate", **candidate}
                    for candidate in cast(list[dict[str, Any]], catalog["candidates"])
                ),
            ),
            key=lambda item: str(item["id"]),
        )
    )
    state = {
        "schema_version": "organization_qualification_run_state_v1",
        "status": "prepared",
        "phase": phase,
        "proposal_report_path": str(proposal_report_path.resolve().relative_to(ROOT)),
        "proposal_report_sha256": hashlib.sha256(proposal_report_path.read_bytes()).hexdigest(),
        "gold_catalog_path": str(gold_catalog_path.resolve().relative_to(ROOT)),
        "gold_catalog_sha256": hashlib.sha256(gold_catalog_path.read_bytes()).hexdigest(),
        "boundary_evaluation_sha256": hashlib.sha256(boundary_bytes).hexdigest(),
        "prompt_path": str(PROMPT_PATH.relative_to(ROOT)),
        "prompt_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        "source_count": catalog["source_count"],
        "candidate_count": catalog["candidate_count"],
        "repetitions": REPETITIONS,
    }
    inputs_path = output_dir / "inputs.jsonl"
    run_path = output_dir / "run.json"
    inputs_payload = "".join(canonical_json(record) + "\n" for record in records)
    run_payload = canonical_json(state) + "\n"
    if inputs_path.exists() or run_path.exists():
        if not inputs_path.is_file() or not run_path.is_file():
            raise ValueError("Qualification resume requires both inputs.jsonl and run.json.")
        if inputs_path.read_text(encoding="utf-8") != inputs_payload:
            raise ValueError("Qualification resume input catalog conflicts with retained evidence.")
        if run_path.read_text(encoding="utf-8") != run_payload:
            raise ValueError("Qualification resume state conflicts with retained evidence.")
        return state
    output_dir.mkdir(parents=True, exist_ok=True)
    write_canonical_jsonl(inputs_path, records)
    run_path.write_text(run_payload, encoding="utf-8")
    return state


def run_refined(
    *,
    output_dir: Path,
    python_executable: Path,
    data_dir: Path,
) -> dict[str, Any]:
    """Run or resume three ReFinED repetitions, batching exact spans by source."""
    state, sources, candidates = _load_inputs(output_dir)
    _write_immutable_json(
        output_dir / "refined-runtime.json",
        {
            "schema_version": "refined_runtime_identity_v1",
            "python_executable": str(python_executable),
            "worker_script": str(
                (ROOT / "scripts/refined_organization_type_worker.py").relative_to(ROOT)
            ),
            "worker_script_sha256": hashlib.sha256(
                (ROOT / "scripts/refined_organization_type_worker.py").read_bytes()
            ).hexdigest(),
            "requirements_lock": "tools/refined-worker/requirements.txt",
            "requirements_lock_sha256": hashlib.sha256(
                (ROOT / "tools/refined-worker/requirements.txt").read_bytes()
            ).hexdigest(),
            "data_dir": str(data_dir),
            "resource_manifest_sha256": REFINED_RESOURCE_MANIFEST_SHA256,
            "model_id": REFINED_MODEL_ID,
            "model_revision": REFINED_MODEL_REVISION,
            "entity_set": REFINED_ENTITY_SET,
            "package_revision": REFINED_PACKAGE_REVISION,
            "download_files": False,
        },
    )
    output_path = output_dir / "executions-refined.jsonl"
    existing = _execution_ids(output_path)
    try:
        adapter = RefinedContextualOrganizationTypeAdapter(
            RefinedWorkerConfig(
                python_executable=python_executable,
                worker_script=ROOT / "scripts/refined_organization_type_worker.py",
                data_dir=data_dir,
            )
        )
    except (OSError, RuntimeError, TimeoutError) as error:
        return _write_refined_blocked_result(
            output_dir,
            failure="worker_unavailable",
            diagnostics=(f"{type(error).__name__}: {error}",),
            retained=len(existing),
        )
    written = 0
    try:
        for repetition in range(1, REPETITIONS + 1):
            for index, source in enumerate(sources, start=1):
                source_candidates = _source_candidates(source, candidates)
                pending = tuple(
                    candidate
                    for candidate in source_candidates
                    if _execution_id("refined", repetition, candidate.id) not in existing
                )
                if not pending:
                    continue
                request = ContextualOrganizationTypeInput(
                    source_segment_id=str(source["source_segment_id"]),
                    source_text_sha256=str(source["source_text_sha256"]),
                    source_text=str(source["source_text"]),
                    candidates=pending,
                )
                batch = adapter.qualify(request)
                batch_id = _id(
                    "rfx",
                    str(state["phase"]),
                    str(repetition),
                    str(source["id"]),
                    batch.resource_manifest_sha256,
                )
                for candidate, evidence in zip(pending, batch.evidences, strict=True):
                    execution: dict[str, Any] = {
                        "schema_version": QUALIFICATION_EXECUTION_SCHEMA_VERSION,
                        "id": _execution_id("refined", repetition, candidate.id),
                        "phase": state["phase"],
                        "producer_id": "refined",
                        "repetition": repetition,
                        "source_record_id": source["id"],
                        "candidate_id": candidate.id,
                        "candidate_text": candidate.text,
                        "candidate_start": candidate.start,
                        "candidate_end": candidate.end,
                        "execution_status": "completed",
                        "judgment": map_contextual_type_evidence(evidence).value,
                        "worker_batch_id": batch_id,
                        "worker_batch": asdict(batch) | {"evidences": []},
                        "input": {
                            "source_segment_id": request.source_segment_id,
                            "source_text_sha256": request.source_text_sha256,
                            "source_text": request.source_text,
                            "candidate": asdict(candidate),
                        },
                        "output": asdict(evidence),
                        "diagnostics": [],
                    }
                    if append_execution_record(output_path, execution):
                        existing.add(str(execution["id"]))
                        written += 1
                _progress(
                    "refined_progress",
                    repetition=repetition,
                    completed_sources=index,
                    total_sources=len(sources),
                    retained_executions=len(existing),
                )
    except RefinedWorkerError as error:
        return _write_refined_blocked_result(
            output_dir,
            failure=error.failure,
            diagnostics=error.diagnostics,
            retained=len(existing),
        )
    except (OSError, RuntimeError, TimeoutError) as error:
        return _write_refined_blocked_result(
            output_dir,
            failure="worker_unavailable",
            diagnostics=(f"{type(error).__name__}: {error}",),
            retained=len(existing),
        )
    finally:
        adapter.close()
    return {"status": "completed", "written": written, "retained": len(existing)}


def run_qwen(
    *,
    output_dir: Path,
    config_path: Path | None,
) -> dict[str, Any]:
    """Run or resume tri-state Qwen judgments through ContextPlanner and ModelRun."""
    state, sources, candidates = _load_inputs(output_dir)
    output_path = output_dir / "executions-qwen.jsonl"
    existing = _execution_ids(output_path)
    config = load_config(
        config_path=config_path, ledger_path_override=None, archive_path_override=None
    )
    runtime_config = replace(
        config.model_execution,
        max_output_tokens=QWEN_MAX_OUTPUT_TOKENS,
    )
    runtime = RecordingRuntime(build_model_task_runtime(runtime_config))
    readiness = runtime.check_readiness()
    if not readiness.ready:
        raise RuntimeError(f"Qwen runtime is unavailable: {readiness}")
    prompt_base = PROMPT_PATH.read_bytes()
    schema = OrganizationQualificationLabelTaskSchemaRegistry().resolve(
        "organization_qualification_label_v1"
    )
    tokenizer = DiagnosticTokenizer()
    written = 0
    for source_index, source in enumerate(sources, start=1):
        ledger = _EvaluationLedger(_evaluation_bundle(source))
        unit = plan_analysis_units(
            AnalysisUnitPlanningInput(
                ledger.bundle.representation.id,
                "organization_qualification_context_v1",
                "organization_qualification_label",
            ),
            ledger,
        ).units[0]
        archive = _EvaluationArchive()
        for candidate in _source_candidates(source, candidates):
            for repetition in range(1, REPETITIONS + 1):
                execution_id = _execution_id("qwen", repetition, candidate.id)
                if execution_id in existing:
                    continue
                prompt = prompt_base + b"\n\nMENTION CANDIDATE:\n" + candidate.text.encode("utf-8")
                manifest = build_context_manifest(
                    ContextManifestInput(
                        analysis_unit=unit,
                        model_profile=ContextModelProfile(
                            config.model_execution.profile_name or "lm-studio",
                            config.model_execution.context_tokens,
                            QWEN_MAX_OUTPUT_TOKENS,
                            256,
                        ),
                        prompt_id="paragraph_organization_qualification_v2",
                        prompt_bytes=prompt,
                        schema_id=schema.schema_id,
                        schema_bytes=schema.canonical_schema_bytes,
                        renderer_version="organization_qualification_context_v1",
                        evidence_selection_policy_id=DIRECT_PROSE_EVIDENCE_SELECTION_V1,
                    ),
                    ledger,
                    tokenizer,
                ).manifest
                spec = ModelExecutionSpec(
                    model_profile_id=config.model_execution.profile_name or "lm-studio",
                    model_identity=runtime.configured_identity,
                    generation_parameters=(
                        ExecutionSetting("max_output_tokens", QWEN_MAX_OUTPUT_TOKENS),
                        ExecutionSetting("seed", 17),
                        ExecutionSetting("temperature", 0),
                    ),
                    prompt_id=manifest.prompt_id,
                    prompt_digest=manifest.prompt_digest,
                    schema_id=schema.schema_id,
                    schema_digest=schema.digest,
                    context_manifest_id=manifest.id,
                    context_manifest_digest=manifest.manifest_digest,
                    rendered_input_digest=manifest.rendered_input_digest,
                    output_contract_version=schema.output_contract_version,
                )
                response_count = len(runtime.responses)
                outcome = run_bounded_extraction(
                    BoundedExtractionInput(
                        source_id=_id("src", str(source["id"])),
                        document_id=ledger.bundle.representation.document_id,
                        representation_id=ledger.bundle.representation.id,
                        context_manifest_id=manifest.id,
                        prompt_bytes=prompt,
                        execution_spec=spec,
                        validator_version="organization_qualification_label_validator_v1",
                        task_type="organization_qualification_label",
                    ),
                    cast(StagedExtractionLedger, ledger),
                    archive,
                    runtime,
                    Uuid4ModelRunIdFactory(),
                    tokenizer,
                    OrganizationQualificationLabelTaskSchemaRegistry(),
                )
                responses = runtime.responses[response_count:]
                response = responses[0] if responses else None
                status, judgment, diagnostics = _qwen_outcome(outcome)
                execution = {
                    "schema_version": QUALIFICATION_EXECUTION_SCHEMA_VERSION,
                    "id": execution_id,
                    "phase": state["phase"],
                    "producer_id": "qwen",
                    "repetition": repetition,
                    "source_record_id": source["id"],
                    "candidate_id": candidate.id,
                    "candidate_text": candidate.text,
                    "candidate_start": candidate.start,
                    "candidate_end": candidate.end,
                    "execution_status": status,
                    "judgment": judgment,
                    "input": {
                        "prompt_id": manifest.prompt_id,
                        "prompt_text": prompt.decode("utf-8"),
                        "schema_text": schema.canonical_schema_bytes.decode("utf-8"),
                        "source_segment_id": source["source_segment_id"],
                        "source_text_sha256": source["source_text_sha256"],
                        "source_text": source["source_text"],
                        "candidate": asdict(candidate),
                        "rendered_input": manifest.rendered_input.decode("utf-8"),
                        "context_manifest": _manifest_evidence(manifest),
                    },
                    "output": {
                        "raw_output": response.raw_output.decode("utf-8", errors="replace")
                        if response is not None
                        else None,
                        "execution_receipt": asdict(response.execution_receipt)
                        if response is not None
                        else None,
                        "model_run": outcome.model_run.model_dump(mode="json"),
                    },
                    "model_run_id": outcome.model_run.id,
                    "diagnostics": diagnostics,
                }
                if append_execution_record(output_path, execution):
                    existing.add(execution_id)
                    written += 1
        _progress(
            "qwen_progress",
            completed_sources=source_index,
            total_sources=len(sources),
            retained_executions=len(existing),
        )
    return {"status": "completed", "written": written, "retained": len(existing)}


def finalize(output_dir: Path) -> dict[str, Any]:
    """Validate all executions, create traces/decisions/metrics, and seal the bundle."""
    state, sources, candidates = _load_inputs(output_dir)
    if state.get("phase") == "held_out" and (output_dir / "manifest.json").exists():
        raise FileExistsError("Completed held-out qualification evidence is sealed.")
    source_by_id = {str(source["id"]): source for source in sources}
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    expected = len(candidates) * REPETITIONS
    qwen = _read_jsonl(output_dir / "executions-qwen.jsonl")
    refined = _read_jsonl(output_dir / "executions-refined.jsonl")
    if len(qwen) != expected or len(refined) != expected:
        raise ValueError(
            f"Qualification execution evidence is incomplete: qwen={len(qwen)}, "
            f"refined={len(refined)}, expected={expected}."
        )
    qwen, refined = _normalize_execution_evidence(output_dir, state, qwen, refined)
    executions = tuple(qwen + refined)
    traces: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for execution in sorted(executions, key=lambda item: str(item["id"])):
        candidate = candidate_by_id[str(execution["candidate_id"])]
        source = source_by_id[str(execution["source_record_id"])]
        execution_status = OrganizationQualificationExecutionStatus(
            str(execution["execution_status"])
        )
        judgment = (
            OrganizationQualificationJudgment(str(execution["judgment"]))
            if execution.get("judgment") is not None
            else None
        )
        diagnostics = tuple(sorted(cast(list[str], execution.get("diagnostics", []))))
        trace_status = (
            ExtractionStageStatus.COMPLETED
            if execution_status is OrganizationQualificationExecutionStatus.COMPLETED
            else ExtractionStageStatus.REJECTED
            if execution_status is OrganizationQualificationExecutionStatus.INVALID_OUTPUT
            else ExtractionStageStatus.FAILED
        )
        trace = build_extraction_stage_trace(
            trace_run_id=_id("oqr", str(state["phase"]), str(execution["id"])),
            ordinal=0,
            stage_id="organization_semantic_qualification",
            stage_version="organization_semantic_qualification_v1",
            producer_id=str(execution["producer_id"]),
            source_segment_id=str(source["source_segment_id"]),
            source_text_sha256=str(source["source_text_sha256"]),
            configuration={
                "mapping_policy_id": _mapping_policy(str(execution["producer_id"])),
            },
            input_payload={
                "source_record_id": str(source["id"]),
                "candidate_id": candidate.id,
                "candidate_text": candidate.text,
                "candidate_start": candidate.start,
                "candidate_end": candidate.end,
                "boundary_decision_id": candidate.boundary_decision_id,
            },
            output_payload={
                "execution_record_id": str(execution["id"]),
                "execution_status": execution_status.value,
                "judgment": judgment.value if judgment is not None else None,
            },
            status=trace_status,
            input_record_ids=tuple(
                sorted((candidate.boundary_decision_id, candidate.id, str(source["id"])))
            ),
            execution_record_ids=tuple(
                sorted(
                    value
                    for value in (
                        str(execution.get("model_run_id", "")),
                        str(execution.get("worker_batch_id", "")),
                    )
                    if value
                )
            ),
            diagnostics=diagnostics if trace_status is not ExtractionStageStatus.COMPLETED else (),
        )
        decision = build_organization_qualification_decision(
            candidate=candidate,
            producer_id=str(execution["producer_id"]),
            judgment=judgment,
            execution_status=execution_status,
            evidence_record_id=str(execution["id"]),
            execution_record_ids=trace.execution_record_ids,
            terminal_trace_id=trace.id,
            mapping_policy_id=_mapping_policy(str(execution["producer_id"])),
            diagnostics=diagnostics,
        )
        traces.append(cast(dict[str, Any], extraction_stage_trace_to_json(trace)))
        decisions.append(asdict(decision))
    traces.sort(key=lambda item: str(item["id"]))
    decisions.sort(key=lambda item: str(item["id"]))
    write_canonical_jsonl(output_dir / "traces.jsonl", tuple(traces))
    write_canonical_jsonl(output_dir / "decisions.jsonl", tuple(decisions))
    producer_metrics = {
        producer: score_qualification_executions(
            _catalog_from_inputs(state, sources, output_dir),
            tuple(item for item in executions if item["producer_id"] == producer),
        )
        for producer in ("qwen", "refined")
    }
    disagreements = _disagreement_reviews(executions, output_dir)
    reviews = _deduplicated_reviews(
        [
            *cast(list[dict[str, Any]], producer_metrics["qwen"].pop("review_records")),
            *cast(list[dict[str, Any]], producer_metrics["refined"].pop("review_records")),
            *disagreements,
        ]
    )
    metrics = {
        "schema_version": "organization_qualification_comparison_metrics_v1",
        "phase": state["phase"],
        "candidate_count": len(candidates),
        "repetitions": REPETITIONS,
        "producers": producer_metrics,
        "disagreement_count": len(disagreements),
        "review_record_count": len(reviews),
    }
    (output_dir / "metrics.json").write_text(canonical_json(metrics) + "\n", encoding="utf-8")
    review_records = tuple(
        {"id": _id("oqv", str(index), canonical_json(record)), **record}
        for index, record in enumerate(reviews, start=1)
    )
    write_canonical_jsonl(
        output_dir / "review.jsonl",
        tuple(sorted(review_records, key=lambda item: str(item["id"]))),
    )
    (output_dir / "review.md").write_text(_render_review(metrics, reviews), encoding="utf-8")
    state["status"] = "complete"
    (output_dir / "run.json").write_text(canonical_json(state) + "\n", encoding="utf-8")
    optional_evidence = tuple(
        path
        for path in (
            "attempts-qwen.jsonl",
            "attempts-refined-pre-freeze.jsonl",
            "attempts-refined-pre-freeze-runtime.json",
            "refined-blocked.json",
        )
        if (output_dir / path).is_file()
    )
    manifest = seal_bundle(
        output_dir,
        phase=str(state["phase"]),
        expected_files=(
            "run.json",
            "inputs.jsonl",
            "prompt.json",
            "qwen-inputs.jsonl",
            "refined-runtime.json",
            "refined-batches.jsonl",
            "executions-qwen.jsonl",
            "executions-refined.jsonl",
            "decisions.jsonl",
            "traces.jsonl",
            "metrics.json",
            "review.jsonl",
            "review.md",
            *optional_evidence,
        ),
    )
    return {"status": "complete", "manifest": manifest, "metrics": metrics}


def write_result_record(
    *,
    development_dir: Path,
    held_out_dir: Path,
    org_r1_result_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Bind both sealed phases into one compact, immutable ORG-R2 outcome."""
    org_r1_dependency = _validate_org_r1_dependency(
        org_r1_result_path,
        development_dir=development_dir,
        held_out_dir=held_out_dir,
    )
    phases: dict[str, dict[str, Any]] = {}
    for phase, directory in (("development", development_dir), ("held_out", held_out_dir)):
        manifest_path = directory / "manifest.json"
        metrics_path = directory / "metrics.json"
        manifest = _validate_sealed_manifest(directory, phase)
        metrics = cast(dict[str, Any], json.loads(metrics_path.read_text(encoding="utf-8")))
        if manifest.get("status") != "complete" or manifest.get("phase") != phase:
            raise ValueError(f"ORG-R2 {phase} manifest is not a complete sealed phase.")
        if metrics.get("phase") != phase:
            raise ValueError(f"ORG-R2 {phase} metrics do not match their phase.")
        phases[phase] = {
            "manifest_path": str(manifest_path.resolve().relative_to(ROOT)),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "metrics_path": str(metrics_path.resolve().relative_to(ROOT)),
            "metrics_sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
            "candidate_count": metrics["candidate_count"],
            "producer_metrics": metrics["producers"],
        }
    tdd_path = ROOT / "docs/2026-08-31-organization-semantic-qualification-comparison.md"
    result = {
        "schema_version": "organization_semantic_qualification_result_v1",
        "status": "completed",
        "program_increment": "ORG-R2",
        "tdd_path": str(tdd_path.relative_to(ROOT)),
        "tdd_sha256": hashlib.sha256(tdd_path.read_bytes()).hexdigest(),
        "org_r1_dependency": org_r1_dependency,
        "development": phases["development"],
        "held_out": phases["held_out"],
        "production_selection": "unchanged",
        "accepted_ledger_writes": 0,
    }
    _write_immutable_json(output_path, result)
    return result


def render_comparison_report(
    *,
    development_dir: Path,
    held_out_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Render every paired execution with exact input and Gold-relative evaluation."""
    lines = [
        "# ORG-R2 paired semantic-qualification results",
        "",
        "Each entry compares Qwen2.5 and ReFinED on the same immutable ORG-R1 candidate.",
        "The evaluation is derived from the reviewed Gold catalog; neither producer is authority.",
        "Boundary cases are shown but excluded from semantic scoring.",
        "",
    ]
    rendered_runs = 0
    for phase, directory in (
        ("development", development_dir),
        ("held_out", held_out_dir),
    ):
        _validate_sealed_manifest(directory, phase)
        records = _read_jsonl(directory / "inputs.jsonl")
        source_by_id = {
            str(record["id"]): record for record in records if record.get("record_type") == "source"
        }
        candidates = sorted(
            (record for record in records if record.get("record_type") == "candidate"),
            key=lambda record: (
                str(source_by_id[str(record["source_record_id"])].get("fixture_path")),
                str(source_by_id[str(record["source_record_id"])].get("paragraph_node_id")),
                str(source_by_id[str(record["source_record_id"])].get("source_segment_label")),
                int(cast(dict[str, Any], record["candidate"])["start"]),
                int(cast(dict[str, Any], record["candidate"])["end"]),
                str(record["id"]),
            ),
        )
        executions = {
            (
                int(record["repetition"]),
                str(record["candidate_id"]),
                str(record["producer_id"]),
            ): record
            for record in (
                *_read_jsonl(directory / "executions-qwen.jsonl"),
                *_read_jsonl(directory / "executions-refined.jsonl"),
            )
        }
        lines.extend((f"# {phase.replace('_', '-')} phase", ""))
        for candidate_record in candidates:
            candidate = cast(dict[str, Any], candidate_record["candidate"])
            source = source_by_id[str(candidate_record["source_record_id"])]
            gold = cast(dict[str, Any], candidate_record["gold_classification"])
            lines.extend(
                (
                    f"## {phase.replace('_', '-')} — {candidate['id']}",
                    "",
                    f"Fixture: `{source['fixture_path']}`",
                    f"Paragraph node: `{source['paragraph_node_id']}`",
                    f"Source segment: `{source['source_segment_id']}` "
                    f"(`{source['source_segment_label']}`)",
                    f"Source SHA-256: `{source['source_text_sha256']}`",
                    "",
                    "Exact data in for all three runs — authoritative source segment:",
                    "",
                    *_markdown_quote(str(source["source_text"])),
                    "",
                    f"Exact candidate: {json.dumps(candidate['text'], ensure_ascii=False)}",
                    f"Half-open offsets: `[{candidate['start']}, {candidate['end']})`",
                    f"ORG-R1 boundary decision: `{candidate['boundary_decision_id']}` "
                    f"({candidate['boundary_status']}, `{candidate['boundary_rule_id']}`)",
                    f"Gold expectation: {_gold_expectation(gold)}",
                    "",
                )
            )
            for repetition in range(1, REPETITIONS + 1):
                qwen = executions[(repetition, str(candidate["id"]), "qwen")]
                refined = executions[(repetition, str(candidate["id"]), "refined")]
                qwen_evaluation = _qualification_result_evaluation(qwen, gold)
                refined_evaluation = _qualification_result_evaluation(refined, gold)
                lines.extend(
                    (
                        f"### Run {repetition}",
                        "",
                        f"Qwen2.5 — `{qwen['execution_status']}` / "
                        f"`{qwen.get('judgment')}`; exact raw output "
                        f"{json.dumps(_qwen_raw_output(qwen), ensure_ascii=False)}; "
                        f"{qwen_evaluation}. Evidence: `{qwen['id']}`.",
                        f"ReFinED — `{refined['execution_status']}` / "
                        f"`{refined.get('judgment')}`; "
                        f"{_compact_refined_result(cast(dict[str, Any], refined['output']))}; "
                        f"{refined_evaluation}. Evidence: `{refined['id']}`.",
                        f"Comparative evaluation: "
                        f"{_comparative_evaluation(qwen_evaluation, refined_evaluation, gold)}",
                        "",
                    )
                )
                rendered_runs += 1
    payload = "\n".join(lines).rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    return {
        "status": "completed",
        "output": str(output_path),
        "run_count": rendered_runs,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def _qualification_result_evaluation(
    execution: dict[str, Any],
    gold: dict[str, Any],
) -> str:
    if gold["eligibility"] == "boundary_case":
        return "not scored: non-exact Gold overlap is an ORG-R1 boundary case"
    if execution["execution_status"] != "completed":
        return f"not a semantic result: {execution['execution_status']}"
    judgment = execution.get("judgment")
    expected = gold["expected_judgment"]
    if judgment == expected:
        return "correct"
    if judgment == "ambiguous":
        return f"incorrect abstention; Gold expects {expected}"
    return f"incorrect; Gold expects {expected}"


def _comparative_evaluation(
    qwen_evaluation: str,
    refined_evaluation: str,
    gold: dict[str, Any],
) -> str:
    if gold["eligibility"] == "boundary_case":
        return "neither result is semantically scored because the candidate boundary is unresolved"
    qwen_correct = qwen_evaluation == "correct"
    refined_correct = refined_evaluation == "correct"
    if qwen_correct and refined_correct:
        return "both producers agree with Gold"
    if qwen_correct:
        return "only Qwen2.5 agrees with Gold"
    if refined_correct:
        return "only ReFinED agrees with Gold"
    return "neither producer agrees with Gold"


def _gold_expectation(gold: dict[str, Any]) -> str:
    if gold["eligibility"] == "boundary_case":
        overlaps = ", ".join(
            json.dumps(span["text"], ensure_ascii=False)
            for span in cast(list[dict[str, Any]], gold["overlapping_gold_spans"])
        )
        return f"boundary case, excluded from semantic scoring; overlaps {overlaps}"
    return f"`{gold['expected_judgment']}` ({gold['eligibility']})"


def _markdown_quote(value: str) -> tuple[str, ...]:
    return tuple(f"> {line}" if line else ">" for line in value.splitlines())


def _qwen_raw_output(execution: dict[str, Any]) -> object:
    return cast(dict[str, Any], execution["output"]).get("raw_output")


def _compact_refined_result(output: dict[str, Any]) -> str:
    predicted_entity = output.get("predicted_entity")
    if isinstance(predicted_entity, dict):
        entity = cast(dict[str, Any], predicted_entity)
        entity_text = json.dumps(
            {
                "wikidata_entity_id": entity.get("wikidata_entity_id"),
                "wikipedia_entity_title": entity.get("wikipedia_entity_title"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    else:
        entity_text = "null"
    return (
        f"returned {json.dumps(output.get('returned_text'), ensure_ascii=False)} at "
        f"[{output.get('start')}, {output.get('end')}); coarse mention "
        f"`{output.get('coarse_mention_type')}`; failed class check "
        f"`{output.get('failed_class_check')}`; entity `{entity_text}`; link score "
        f"`{output.get('entity_linking_score')}`"
    )


def _validate_org_r1_dependency(
    result_path: Path,
    *,
    development_dir: Path,
    held_out_dir: Path,
) -> dict[str, Any]:
    result = cast(dict[str, Any], json.loads(result_path.read_text(encoding="utf-8")))
    policy_id = result.get("policy_id")
    freeze_commit = result.get("policy_freeze_commit")
    if policy_id != "organization_boundary_reconciliation_v1":
        raise ValueError("ORG-R2 requires the pinned ORG-R1 policy result.")
    if not isinstance(freeze_commit, str) or len(freeze_commit) != 40:
        raise ValueError("ORG-R1 result requires a freeze commit.")
    for phase, directory in (("development", development_dir), ("held_out", held_out_dir)):
        expected_value = result.get(phase)
        if not isinstance(expected_value, dict):
            raise ValueError(f"ORG-R1 result is missing {phase} evidence.")
        expected = cast(dict[str, object], expected_value)
        run = cast(
            dict[str, Any],
            json.loads((directory / "run.json").read_text(encoding="utf-8")),
        )
        bindings = {
            "proposal_report_sha256": run.get("proposal_report_sha256"),
            "catalog_sha256": run.get("gold_catalog_sha256"),
            "reconciliation_report_sha256": run.get("boundary_evaluation_sha256"),
        }
        if any(expected.get(key) != value for key, value in bindings.items()):
            raise ValueError(f"ORG-R2 {phase} catalog drifted from the frozen ORG-R1 result.")
    return {
        "result_path": str(result_path.resolve().relative_to(ROOT)),
        "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
        "policy_id": policy_id,
        "policy_freeze_commit": freeze_commit,
    }


def _validate_sealed_manifest(directory: Path, phase: str) -> dict[str, Any]:
    manifest_path = directory / "manifest.json"
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    if (
        manifest.get("schema_version") != "organization_qualification_bundle_manifest_v1"
        or manifest.get("status") != "complete"
        or manifest.get("phase") != phase
    ):
        raise ValueError(f"ORG-R2 {phase} manifest is not a complete sealed phase.")
    files_value = manifest.get("files")
    if not isinstance(files_value, list) or not files_value:
        raise ValueError(f"ORG-R2 {phase} manifest requires file records.")
    file_records = cast(list[object], files_value)
    seen: set[str] = set()
    for value in file_records:
        if not isinstance(value, dict):
            raise ValueError(f"ORG-R2 {phase} manifest file record is invalid.")
        record = cast(dict[str, object], value)
        if set(record) != {"path", "sha256", "record_count"}:
            raise ValueError(f"ORG-R2 {phase} manifest file record shape drifted.")
        relative_value = record["path"]
        digest_value = record["sha256"]
        count_value = record["record_count"]
        if not isinstance(relative_value, str) or not relative_value:
            raise ValueError(f"ORG-R2 {phase} manifest path is invalid.")
        relative = Path(relative_value)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != relative_value
        ):
            raise ValueError(f"ORG-R2 {phase} manifest path escapes its bundle.")
        if relative_value in seen:
            raise ValueError(f"ORG-R2 {phase} manifest repeats a path.")
        seen.add(relative_value)
        path = directory / relative
        if not path.is_file() or not isinstance(digest_value, str):
            raise ValueError(f"ORG-R2 {phase} manifest references missing evidence.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest_value:
            raise ValueError(f"ORG-R2 {phase} evidence digest mismatch: {relative_value}.")
        expected_count = (
            len(path.read_text(encoding="utf-8").splitlines()) if path.suffix == ".jsonl" else 1
        )
        if type(count_value) is not int or count_value != expected_count:
            raise ValueError(f"ORG-R2 {phase} record count mismatch: {relative_value}.")
    _validate_bundle_lineage(directory, phase)
    return manifest


def _validate_bundle_lineage(directory: Path, phase: str) -> None:
    """Prove that every terminal decision retains its complete causal evidence chain."""
    input_records = _read_jsonl(directory / "inputs.jsonl")
    source_records = {
        str(record["id"]): record
        for record in input_records
        if record.get("record_type") == "source"
    }
    candidate_records = {
        str(record["id"]): record
        for record in input_records
        if record.get("record_type") == "candidate"
    }
    if not source_records or not candidate_records:
        raise ValueError(f"ORG-R2 {phase} lineage requires sources and candidates.")
    if len(source_records) + len(candidate_records) != len(input_records):
        raise ValueError(f"ORG-R2 {phase} input catalog contains an unsupported record type.")

    for candidate_id, record in candidate_records.items():
        candidate = cast(dict[str, Any], record.get("candidate"))
        if candidate.get("id") != candidate_id:
            raise ValueError(f"ORG-R2 {phase} candidate identity drifted.")
        source = source_records.get(str(record.get("source_record_id")))
        if source is None:
            raise ValueError(f"ORG-R2 {phase} candidate references a missing source.")
        start = candidate.get("start")
        end = candidate.get("end")
        if type(start) is not int or type(end) is not int:
            raise ValueError(f"ORG-R2 {phase} candidate offsets are invalid.")
        source_text = str(source["source_text"])
        if source_text[start:end] != candidate.get("text"):
            raise ValueError(f"ORG-R2 {phase} candidate no longer matches source characters.")
        if candidate.get("source_segment_id") != source.get("source_segment_id") or candidate.get(
            "source_text_sha256"
        ) != source.get("source_text_sha256"):
            raise ValueError(f"ORG-R2 {phase} candidate source identity drifted.")

    qwen_inputs = _unique_records(
        _read_jsonl(directory / "qwen-inputs.jsonl"),
        phase=phase,
        label="Qwen input",
    )
    refined_batches = _unique_records(
        _read_jsonl(directory / "refined-batches.jsonl"),
        phase=phase,
        label="ReFinED batch",
    )
    execution_records = _unique_records(
        [
            *_read_jsonl(directory / "executions-qwen.jsonl"),
            *_read_jsonl(directory / "executions-refined.jsonl"),
        ],
        phase=phase,
        label="execution",
    )
    trace_records = _unique_records(
        _read_jsonl(directory / "traces.jsonl"),
        phase=phase,
        label="trace",
    )
    decision_records = _unique_records(
        _read_jsonl(directory / "decisions.jsonl"),
        phase=phase,
        label="decision",
    )
    expected_execution_count = len(candidate_records) * REPETITIONS * 2
    if not (
        len(execution_records)
        == len(trace_records)
        == len(decision_records)
        == expected_execution_count
    ):
        raise ValueError(f"ORG-R2 {phase} terminal evidence is incomplete.")

    for execution_id, execution in execution_records.items():
        candidate_record = candidate_records.get(str(execution.get("candidate_id")))
        source = source_records.get(str(execution.get("source_record_id")))
        if candidate_record is None or source is None:
            raise ValueError(f"ORG-R2 {phase} execution references missing input evidence.")
        candidate = cast(dict[str, Any], candidate_record["candidate"])
        if candidate_record.get("source_record_id") != source.get("id"):
            raise ValueError(f"ORG-R2 {phase} execution crossed source boundaries.")
        if any(
            execution.get(key) != candidate.get(candidate_key)
            for key, candidate_key in (
                ("candidate_text", "text"),
                ("candidate_start", "start"),
                ("candidate_end", "end"),
            )
        ):
            raise ValueError(f"ORG-R2 {phase} execution candidate boundary drifted.")
        input_record_id = str(execution.get("input_record_id"))
        producer_id = execution.get("producer_id")
        if producer_id == "qwen":
            producer_input = qwen_inputs.get(input_record_id)
            if (
                producer_input is None
                or producer_input.get("candidate_id") != candidate.get("id")
                or producer_input.get("source_record_id") != source.get("id")
            ):
                raise ValueError(f"ORG-R2 {phase} Qwen execution input drifted.")
        elif producer_id == "refined":
            producer_input = refined_batches.get(input_record_id)
            if (
                producer_input is None
                or candidate.get("id") not in producer_input.get("candidate_ids", [])
                or execution_id not in producer_input.get("execution_ids", [])
                or producer_input.get("source_record_id") != source.get("id")
            ):
                raise ValueError(f"ORG-R2 {phase} ReFinED execution input drifted.")
        else:
            raise ValueError(f"ORG-R2 {phase} execution producer is unsupported.")

    for decision in decision_records.values():
        execution = execution_records.get(str(decision.get("evidence_record_id")))
        candidate_record = candidate_records.get(str(decision.get("candidate_id")))
        trace = trace_records.get(str(decision.get("terminal_trace_id")))
        if execution is None or candidate_record is None or trace is None:
            raise ValueError(f"ORG-R2 {phase} decision lineage is incomplete.")
        candidate = cast(dict[str, Any], candidate_record["candidate"])
        if any(
            decision.get(key) != expected
            for key, expected in (
                ("producer_id", execution.get("producer_id")),
                ("execution_status", execution.get("execution_status")),
                ("judgment", execution.get("judgment")),
                ("candidate_text", candidate.get("text")),
                ("candidate_start", candidate.get("start")),
                ("candidate_end", candidate.get("end")),
            )
        ):
            raise ValueError(f"ORG-R2 {phase} decision disagrees with its evidence.")
        trace_input = cast(dict[str, Any], trace.get("input"))
        trace_output = cast(dict[str, Any], trace.get("output"))
        expected_input_ids = {
            str(candidate.get("boundary_decision_id")),
            str(candidate.get("id")),
            str(candidate_record.get("source_record_id")),
        }
        if (
            trace.get("producer_id") != execution.get("producer_id")
            or trace_input.get("candidate_id") != candidate.get("id")
            or trace_output.get("execution_record_id") != execution.get("id")
            or set(cast(list[str], trace.get("input_record_ids"))) != expected_input_ids
        ):
            raise ValueError(f"ORG-R2 {phase} terminal trace lineage drifted.")


def _unique_records(
    records: list[dict[str, Any]],
    *,
    phase: str,
    label: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id or record_id in indexed:
            raise ValueError(f"ORG-R2 {phase} {label} identity is invalid or repeated.")
        indexed[record_id] = record
    return indexed


class _EvaluationLedger:
    """In-memory derived ledger used only to exercise ContextPlanner and ModelRun."""

    def __init__(self, bundle: DocumentRepresentationBundle) -> None:
        self.bundle = bundle
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.manifests: dict[str, ContextManifestArtifact] = {}
        self.extraction_tasks: dict[str, Any] = {}
        self.model_runs: dict[str, Any] = {}

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.manifests.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.manifests[manifest.id] = manifest
        self.analysis_units.update({item.id: item for item in child_analysis_units})

    def save_extraction_task(self, record: Any) -> None:
        self.extraction_tasks[record.id] = record

    def save_model_run(self, record: Any) -> None:
        self.model_runs[record.id] = record

    def commit_successful_model_run_and_candidate_batch(self, **values: object) -> None:
        raise AssertionError(f"ORG-R2 must never publish candidate changes: {values!r}")


class _EvaluationArchive:
    def __init__(self) -> None:
        self.outputs: dict[str, bytes] = {}

    def put_model_run_output(
        self,
        model_run_id: str,
        payload: bytes,
        expected_digest: str,
    ) -> str:
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            raise ValueError("Evaluation model output digest mismatch.")
        self.outputs[model_run_id] = payload
        return model_run_id


def _evaluation_bundle(source: dict[str, Any]) -> DocumentRepresentationBundle:
    source_id = str(source["id"])
    text = str(source["source_text"])
    representation_id = _id("rep", source_id)
    text_view = TextView(
        id=_id("tvw", source_id),
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id=_id("nod", source_id, "root"),
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    paragraph = DocumentNode(
        id=_id("nod", source_id, "paragraph"),
        representation_id=representation_id,
        node_type="paragraph",
        parent_node_id=root.id,
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(text),
    )
    quality = ParseQualityReport(
        id=_id("pqr", source_id),
        representation_id=representation_id,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=_id("doc", source_id),
        parser_name="org-r2-frozen-source",
        parser_version="1",
        parser_config_digest=hashlib.sha256(b"org-r2-frozen-source-v1").hexdigest(),
        processing_task_fingerprint_id=_id("ptf", source_id),
        input_blob_digest=str(source["source_text_sha256"]),
        canonical_output_digest="0" * 64,
        created_at=datetime(2026, 8, 31, tzinfo=UTC),
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(root, paragraph),
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(root, paragraph),
        quality_report=quality,
    )


def _load_inputs(
    output_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[QualificationCandidate]]:
    state = cast(dict[str, Any], json.loads((output_dir / "run.json").read_text()))
    records = _read_jsonl(output_dir / "inputs.jsonl")
    sources = sorted(
        (record for record in records if record["record_type"] == "source"),
        key=lambda item: str(item["id"]),
    )
    candidates = [
        _candidate_from_json(cast(dict[str, Any], record["candidate"]))
        for record in records
        if record["record_type"] == "candidate"
    ]
    candidates.sort(key=lambda item: item.id)
    return state, sources, candidates


def _candidate_from_json(value: dict[str, Any]) -> QualificationCandidate:
    return QualificationCandidate(
        id=str(value["id"]),
        source_segment_id=str(value["source_segment_id"]),
        source_text_sha256=str(value["source_text_sha256"]),
        text=str(value["text"]),
        start=int(value["start"]),
        end=int(value["end"]),
        boundary_decision_id=str(value["boundary_decision_id"]),
        boundary_status=MentionBoundaryDecisionStatus(str(value["boundary_status"])),
        boundary_rule_id=str(value["boundary_rule_id"]),
        source_candidate_ids=tuple(cast(list[str], value["source_candidate_ids"])),
        proposer_ids=tuple(cast(list[str], value["proposer_ids"])),
    )


def _source_candidates(
    source: dict[str, Any],
    candidates: list[QualificationCandidate],
) -> tuple[QualificationCandidate, ...]:
    return tuple(
        sorted(
            (
                candidate
                for candidate in candidates
                if candidate.source_segment_id == source["source_segment_id"]
            ),
            key=lambda item: (item.start, item.end, item.id),
        )
    )


def _qwen_outcome(outcome: Any) -> tuple[str, str | None, list[str]]:
    status = outcome.model_run.status
    if status is ModelRunStatus.SUCCEEDED and outcome.organization_qualification_judgment:
        return "completed", outcome.organization_qualification_judgment.value, []
    if status is ModelRunStatus.INVALID_OUTPUT:
        return "invalid_output", None, [f"invalid_output:{outcome.model_run.error_message}"]
    return (
        "failed",
        None,
        [f"model_run_status:{status.value}", str(outcome.model_run.error_message)],
    )


def _manifest_evidence(manifest: ContextManifest) -> dict[str, Any]:
    return {
        "id": manifest.id,
        "analysis_unit_id": manifest.analysis_unit_id,
        "representation_id": manifest.representation_id,
        "prompt_digest": manifest.prompt_digest,
        "schema_digest": manifest.schema_digest,
        "rendered_input_digest": manifest.rendered_input_digest,
        "rendered_input_base64": base64.b64encode(manifest.rendered_input).decode("ascii"),
        "input_token_count": manifest.input_token_count,
        "manifest_digest": manifest.manifest_digest,
        "status": manifest.status.value,
        "selected_node_ids": [item.node_id for item in manifest.selected_candidates],
        "evidence_candidate_ids": [item.id for item in manifest.evidence_candidates],
    }


def _catalog_from_inputs(
    state: dict[str, Any],
    sources: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    records = _read_jsonl(output_dir / "inputs.jsonl")
    return {
        "phase": state["phase"],
        "sources": sources,
        "candidates": [
            {key: value for key, value in record.items() if key != "record_type"}
            for record in records
            if record["record_type"] == "candidate"
        ],
    }


def _normalize_execution_evidence(
    output_dir: Path,
    state: dict[str, Any],
    qwen: list[dict[str, Any]],
    refined: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Factor shared payloads into immutable records without losing observable evidence."""
    if qwen and "input_record_id" in qwen[0]:
        required = (
            output_dir / "prompt.json",
            output_dir / "qwen-inputs.jsonl",
            output_dir / "refined-batches.jsonl",
        )
        if not all(path.is_file() for path in required):
            raise ValueError("Normalized qualification evidence is incomplete.")
        return qwen, refined

    qwen_inputs: dict[str, dict[str, Any]] = {}
    normalized_qwen: list[dict[str, Any]] = []
    for execution in qwen:
        input_payload = cast(dict[str, Any], execution.get("input"))
        if not input_payload:
            raise ValueError("Qwen execution is missing retained input evidence.")
        shared_payload = {
            "schema_version": "organization_qualification_qwen_input_v1",
            "source_record_id": execution["source_record_id"],
            "candidate_id": execution["candidate_id"],
            "prompt_sha256": state["prompt_sha256"],
            "source_segment_id": input_payload["source_segment_id"],
            "source_text_sha256": input_payload["source_text_sha256"],
            "context_manifest": input_payload["context_manifest"],
        }
        input_id = _id("oqi", canonical_json(shared_payload))
        input_record = {"id": input_id, **shared_payload}
        _retain_identical(qwen_inputs, input_id, input_record, "Qwen input")
        normalized_qwen.append(
            {
                **{key: value for key, value in execution.items() if key != "input"},
                "input_record_id": input_id,
            }
        )

    attempt_path = output_dir / "attempts-qwen.jsonl"
    normalized_attempts: list[dict[str, Any]] = []
    for execution in _read_jsonl(attempt_path):
        input_payload = cast(dict[str, Any], execution.get("input"))
        if not input_payload:
            raise ValueError("Qwen attempt is missing retained input evidence.")
        shared_payload = {
            "schema_version": "organization_qualification_qwen_input_v1",
            "source_record_id": execution["source_record_id"],
            "candidate_id": execution["candidate_id"],
            "prompt_sha256": state["prompt_sha256"],
            "source_segment_id": input_payload["source_segment_id"],
            "source_text_sha256": input_payload["source_text_sha256"],
            "context_manifest": input_payload["context_manifest"],
        }
        input_id = _id("oqi", canonical_json(shared_payload))
        input_record = {"id": input_id, **shared_payload}
        _retain_identical(qwen_inputs, input_id, input_record, "Qwen input")
        normalized_attempts.append(
            {
                **{key: value for key, value in execution.items() if key != "input"},
                "input_record_id": input_id,
            }
        )

    refined_batches: dict[str, dict[str, Any]] = {}
    normalized_refined: list[dict[str, Any]] = []
    for execution in refined:
        batch_id = str(execution.get("worker_batch_id", ""))
        worker_batch = cast(dict[str, Any], execution.get("worker_batch"))
        input_payload = cast(dict[str, Any], execution.get("input"))
        if not batch_id or not worker_batch or not input_payload:
            raise ValueError("ReFinED execution is missing batch evidence.")
        existing_batch = refined_batches.get(batch_id)
        if existing_batch is None:
            refined_batches[batch_id] = {
                "id": batch_id,
                "schema_version": "organization_qualification_refined_batch_v1",
                "phase": execution["phase"],
                "producer_id": execution["producer_id"],
                "repetition": execution["repetition"],
                "source_record_id": execution["source_record_id"],
                "source_segment_id": input_payload["source_segment_id"],
                "source_text_sha256": input_payload["source_text_sha256"],
                "candidate_ids": [execution["candidate_id"]],
                "execution_ids": [execution["id"]],
                "worker_output": worker_batch,
            }
        else:
            comparison = {
                key: existing_batch[key]
                for key in (
                    "phase",
                    "producer_id",
                    "repetition",
                    "source_record_id",
                    "source_segment_id",
                    "source_text_sha256",
                    "worker_output",
                )
            }
            candidate_comparison = {
                "phase": execution["phase"],
                "producer_id": execution["producer_id"],
                "repetition": execution["repetition"],
                "source_record_id": execution["source_record_id"],
                "source_segment_id": input_payload["source_segment_id"],
                "source_text_sha256": input_payload["source_text_sha256"],
                "worker_output": worker_batch,
            }
            if comparison != candidate_comparison:
                raise ValueError("ReFinED batch evidence conflicts within one batch identity.")
            cast(list[str], existing_batch["candidate_ids"]).append(str(execution["candidate_id"]))
            cast(list[str], existing_batch["execution_ids"]).append(str(execution["id"]))
        normalized_refined.append(
            {
                **{
                    key: value
                    for key, value in execution.items()
                    if key not in {"input", "worker_batch"}
                },
                "input_record_id": batch_id,
                "elapsed_milliseconds": worker_batch["inference_elapsed_ms"],
            }
        )

    prompt_payload = {
        "schema_version": "organization_qualification_prompt_v1",
        "prompt_path": state["prompt_path"],
        "prompt_sha256": state["prompt_sha256"],
        "prompt_text": PROMPT_PATH.read_text(encoding="utf-8"),
        "task_schema_id": "organization_qualification_label_v1",
        "task_schema_text": OrganizationQualificationLabelTaskSchemaRegistry()
        .resolve("organization_qualification_label_v1")
        .canonical_schema_bytes.decode("utf-8"),
    }
    _write_immutable_json(output_dir / "prompt.json", prompt_payload)
    write_canonical_jsonl(
        output_dir / "qwen-inputs.jsonl",
        tuple(sorted(qwen_inputs.values(), key=lambda item: str(item["id"]))),
    )
    write_canonical_jsonl(
        output_dir / "refined-batches.jsonl",
        tuple(sorted(refined_batches.values(), key=lambda item: str(item["id"]))),
    )
    write_canonical_jsonl(
        output_dir / "executions-qwen.jsonl",
        tuple(sorted(normalized_qwen, key=lambda item: str(item["id"]))),
    )
    write_canonical_jsonl(
        output_dir / "executions-refined.jsonl",
        tuple(sorted(normalized_refined, key=lambda item: str(item["id"]))),
    )
    if normalized_attempts:
        write_canonical_jsonl(
            attempt_path,
            tuple(sorted(normalized_attempts, key=lambda item: str(item["id"]))),
        )
    return normalized_qwen, normalized_refined


def _disagreement_reviews(
    executions: tuple[dict[str, Any], ...],
    output_dir: Path,
) -> list[dict[str, Any]]:
    records = _read_jsonl(output_dir / "inputs.jsonl")
    candidate_by_id = {
        str(record["candidate"]["id"]): record
        for record in records
        if record["record_type"] == "candidate"
    }
    by_key: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
    for execution in executions:
        by_key.setdefault((int(execution["repetition"]), str(execution["candidate_id"])), {})[
            str(execution["producer_id"])
        ] = execution
    reviews: list[dict[str, Any]] = []
    for (repetition, candidate_id), values in sorted(by_key.items()):
        if set(values) != {"qwen", "refined"}:
            continue
        judgments = {value.get("judgment") for value in values.values()}
        statuses = {value.get("execution_status") for value in values.values()}
        if len(judgments) == 1 and len(statuses) == 1:
            continue
        catalog_item = candidate_by_id[candidate_id]
        reviews.append(
            {
                "candidate_id": candidate_id,
                "repetition": repetition,
                "reason": "producer_disagreement",
                "source_record_id": catalog_item["source_record_id"],
                "candidate": catalog_item["candidate"],
                "gold_classification": catalog_item["gold_classification"],
                "execution_ids": sorted(value["id"] for value in values.values()),
                "producer_results": {
                    producer: {
                        "execution_status": value["execution_status"],
                        "judgment": value["judgment"],
                    }
                    for producer, value in sorted(values.items())
                },
                "root_cause_hypotheses": ["unresolved"],
                "semantic_case_tags": ["other"],
            }
        )
    return reviews


def _deduplicated_reviews(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = {canonical_json(record): record for record in records}
    return [unique[key] for key in sorted(unique)]


def _render_review(metrics: dict[str, Any], records: list[dict[str, Any]]) -> str:
    lines = [
        "# ORG-R2 semantic qualification review",
        "",
        f"Phase: {metrics['phase']}",
        f"Candidates: {metrics['candidate_count']}",
        f"Disagreements: {metrics['disagreement_count']}",
        f"Review records: {metrics['review_record_count']}",
        "",
    ]
    for record in records:
        lines.extend(
            (
                f"## {record['candidate_id']} — {record['reason']}",
                "",
                f"Candidate: {record['candidate']['text']}",
                f"Gold: {record['gold_classification']}",
                f"Evidence: {canonical_json(record)}",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _mapping_policy(producer_id: str) -> str:
    if producer_id == "qwen":
        return QWEN_ORGANIZATION_QUALIFICATION_POLICY_ID
    if producer_id == "refined":
        return REFINED_ORGANIZATION_TYPE_MAPPING_POLICY_ID
    raise ValueError(f"Unsupported qualification producer: {producer_id}")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [cast(dict[str, Any], json.loads(line)) for line in path.read_text().splitlines()]


def _execution_ids(path: Path) -> set[str]:
    return {str(record["id"]) for record in _read_jsonl(path)}


def _write_immutable_json(path: Path, value: dict[str, Any]) -> None:
    payload = canonical_json(value) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise ValueError(f"Retained evidence conflicts at {path.name}.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _write_refined_blocked_result(
    output_dir: Path,
    *,
    failure: str,
    diagnostics: tuple[str, ...],
    retained: int,
) -> dict[str, Any]:
    result = {
        "schema_version": "organization_qualification_blocked_v1",
        "status": "blocked",
        "producer_id": "refined",
        "failure": failure,
        "diagnostics": list(diagnostics),
        "retained": retained,
    }
    _write_immutable_json(output_dir / "refined-blocked.json", result)
    return result


def _retain_identical(
    records: dict[str, dict[str, Any]],
    record_id: str,
    record: dict[str, Any],
    label: str,
) -> None:
    existing = records.get(record_id)
    if existing is not None and canonical_json(existing) != canonical_json(record):
        raise ValueError(f"{label} conflicts for one content identity.")
    records[record_id] = record


def _execution_id(producer: str, repetition: int, candidate_id: str) -> str:
    return _id("oqe", producer, str(repetition), candidate_id)


def _id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _progress(event: str, **values: Any) -> None:
    print(canonical_json({"event": event, **values}), file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--phase", choices=("development", "held_out"), required=True)
    prepare_parser.add_argument("--proposal-report", type=Path, required=True)
    prepare_parser.add_argument("--gold-catalog", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)
    refined_parser = subparsers.add_parser("run-refined")
    refined_parser.add_argument("--output-dir", type=Path, required=True)
    refined_parser.add_argument("--python", type=Path, required=True)
    refined_parser.add_argument("--data-dir", type=Path, required=True)
    qwen_parser = subparsers.add_parser("run-qwen")
    qwen_parser.add_argument("--output-dir", type=Path, required=True)
    qwen_parser.add_argument("--config", type=Path, default=None)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--output-dir", type=Path, required=True)
    result_parser = subparsers.add_parser("write-result")
    result_parser.add_argument("--development-dir", type=Path, required=True)
    result_parser.add_argument("--held-out-dir", type=Path, required=True)
    result_parser.add_argument("--org-r1-result", type=Path, required=True)
    result_parser.add_argument("--output", type=Path, required=True)
    comparison_parser = subparsers.add_parser("render-comparison")
    comparison_parser.add_argument("--development-dir", type=Path, required=True)
    comparison_parser.add_argument("--held-out-dir", type=Path, required=True)
    comparison_parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "prepare":
        result = prepare(
            proposal_report_path=arguments.proposal_report,
            gold_catalog_path=arguments.gold_catalog,
            output_dir=arguments.output_dir,
            phase=arguments.phase,
        )
    elif arguments.command == "run-refined":
        result = run_refined(
            output_dir=arguments.output_dir,
            python_executable=arguments.python,
            data_dir=arguments.data_dir,
        )
    elif arguments.command == "run-qwen":
        result = run_qwen(output_dir=arguments.output_dir, config_path=arguments.config)
    elif arguments.command == "finalize":
        result = finalize(arguments.output_dir)
    elif arguments.command == "write-result":
        result = write_result_record(
            development_dir=arguments.development_dir,
            held_out_dir=arguments.held_out_dir,
            org_r1_result_path=arguments.org_r1_result,
            output_path=arguments.output,
        )
    else:
        result = render_comparison_report(
            development_dir=arguments.development_dir,
            held_out_dir=arguments.held_out_dir,
            output_path=arguments.output,
        )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
