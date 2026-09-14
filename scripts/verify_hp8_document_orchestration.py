#!/usr/bin/env python3
"""Run and replay HP-8 over the locked Anthropic/DoD document."""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    EventTriggerDraft,
    HybridExtractionPreview,
    HybridReferencePreview,
    HybridStageId,
    SourceGroundedEventDraft,
    hybrid_document_coverage_report_from_bytes,
    hybrid_event_semantics_preview_from_bytes,
    hybrid_event_trigger_preview_from_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_pipeline_policy_manifest_from_bytes,
    hybrid_reference_preview_from_bytes,
    paragraph_source_segments,
    standing_fact_plan_from_bytes,
)
from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    build_candidate_knowledge_view,
    plan_candidate_wiki,
    select_candidate_ingestions,
)
from kotekomi_domain import EvidenceTarget, IngestionChangeSetOrigin, ReviewStatus
from kotekomi_exporters import MarkdownCandidateWikiRenderer
from kotekomi_pipelines.cli import ingest_user_file
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.current_hybrid_evaluation import CurrentHybridEvaluationReport
from kotekomi_pipelines.front_half_stage_local import (
    FrontHalfCaseEvaluation,
    FrontHalfEvaluationReport,
    build_front_half_evaluation_report,
    evaluate_front_half_case,
    load_front_half_inputs,
)
from kotekomi_pipelines.source_grounded_event_evaluation import (
    SourceGroundedEventEvaluationReport,
    evaluate_source_grounded_event_corpus,
    load_source_grounded_event_gold,
)
from kotekomi_pipelines.standing_fact_evaluation import (
    StandingFactEvaluationReport,
    StandingFactRuntimeEvidence,
    evaluate_standing_fact_gold,
    load_standing_fact_gold,
    standing_fact_evidence_from_plan,
    standing_fact_reconciliation_from_proposed_changes,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json"
SOURCE_GROUNDED_EVENT_GOLD = ROOT / "docs/hsq-source-grounded-event-gold-v1.json"
FRONT_HALF_SPLIT = ROOT / "docs/hsq-front-half-split-v1.json"
STANDING_FACT_GOLD = ROOT / "docs/hsq-standing-fact-gold-v1.json"
type JsonObject = dict[str, Any]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--state-root",
        type=Path,
        help="Preserve the isolated Ledger and Archive under this new directory.",
    )
    parser.add_argument(
        "--reuse-state",
        action="store_true",
        help="Rebuild a report from an already completed isolated state root.",
    )
    args = parser.parse_args()
    source = args.source.resolve()
    _validate_locked_source(source)
    configured = load_config(
        config_path=args.config,
        ledger_path_override=None,
        archive_path_override=None,
    )
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.state_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="kotekomi-hp8-")
        root = Path(temporary.name)
    else:
        root = args.state_root.resolve()
        if root.exists() and not args.reuse_state:
            raise ValueError(f"HP-8 state root already exists: {root}")
        if not root.exists() and args.reuse_state:
            raise ValueError(f"HP-8 state root does not exist: {root}")
        root.mkdir(parents=True, exist_ok=args.reuse_state)
    try:
        ledger_path = root / "kotekomi.db"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        if not args.reuse_state:
            config_path.write_text(
                _isolated_config(configured, ledger_path, archive_path),
                encoding="utf-8",
            )
            first = _ingest(config_path, source, args.url)
        else:
            first = {
                "exit_code": 0,
                "elapsed_milliseconds": None,
                "stdout": "",
                "stderr": "",
                "recovered_existing_state": True,
            }
        first_counts = _ledger_counts(ledger_path)
        report, manifest, paragraphs = _document_evidence(ledger_path, archive_path)
        model_performance, model_executions = model_evidence(ledger_path, archive_path)
        if args.reuse_state:
            second = {
                "exit_code": 0,
                "elapsed_milliseconds": None,
                "stdout": "",
                "stderr": "",
                "recovered_existing_state": True,
            }
            second_counts = first_counts
        else:
            second = _ingest(config_path, source, args.url)
            second_counts = _ledger_counts(ledger_path)
        origins = _change_set_origins(ledger_path)
        source_grounded_event_evaluation = _source_grounded_event_evaluation(
            paragraphs=paragraphs,
            coverage_report=report,
            ledger_path=ledger_path,
            archive_path=archive_path,
        )
        wiki_evidence, wiki_plan = _publish_candidate_wiki(
            source.name,
            ledger_path,
            archive_path,
        )
        front_half_evaluation = _front_half_evaluation(paragraphs)
        standing_fact_evaluation = _standing_fact_evaluation(
            paragraphs,
            wiki_plan,
            ledger_path,
        )
        findings = _findings(
            configured=configured,
            report=report,
            manifest=manifest,
            first_counts=first_counts,
            second_counts=second_counts,
            origins=origins,
            front_half_evaluation=front_half_evaluation,
            source_grounded_event_evaluation=source_grounded_event_evaluation,
            standing_fact_evaluation=standing_fact_evaluation,
            paragraphs=paragraphs,
        )
        report_record = CurrentHybridEvaluationReport.model_validate(
            {
                "schema_version": "hp8_document_orchestration_evaluation_v3",
                "source_path": str(source),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "policy_manifest": manifest,
                "coverage_report": report,
                "paragraphs": paragraphs,
                "source_grounded_event_evaluation": source_grounded_event_evaluation.model_dump(
                    mode="json"
                ),
                "front_half_evaluation": front_half_evaluation.model_dump(mode="json"),
                "standing_fact_evaluation": standing_fact_evaluation.model_dump(mode="json"),
                "candidate_wiki": wiki_evidence,
                "first_public_output": first,
                "replay_public_output": second,
                "first_ledger_counts": first_counts,
                "model_performance": model_performance,
                "model_executions": model_executions,
                "replay_ledger_counts": second_counts,
                "ingestion_change_set_origins": origins,
                "findings": findings,
                "summary": {
                    "passed": not findings,
                    "required_paragraphs": report["required_paragraph_count"],
                    "complete_paragraphs": report["complete_paragraph_count"],
                    "gap_paragraphs": report["gap_paragraph_count"],
                    "paragraph_proposed_changes": len(report["proposed_change_ids"]),
                    "reconciled_proposed_changes": first_counts["proposed_changes"],
                    "source_grounded_events_expected": (
                        source_grounded_event_evaluation.expected_event_count
                    ),
                    "source_grounded_events_observed": (
                        source_grounded_event_evaluation.observed_event_count
                    ),
                    "source_grounded_events_exact": (
                        source_grounded_event_evaluation.grounded_event_count
                    ),
                    "source_grounded_events_missing": (
                        source_grounded_event_evaluation.missing_event_count
                    ),
                    "source_grounded_events_extra": (
                        source_grounded_event_evaluation.extra_event_count
                    ),
                    "source_grounded_events_incorrect": (
                        source_grounded_event_evaluation.incorrectly_grounded_event_count
                    ),
                    "front_half_items_expected": front_half_evaluation.item_count,
                    "front_half_items_exact": front_half_evaluation.passed_count,
                    "standing_facts_expected": standing_fact_evaluation.item_count,
                    "standing_facts_exact": standing_fact_evaluation.exact_count,
                    "standing_facts_missing": standing_fact_evaluation.missing_count,
                    "standing_facts_incorrect": standing_fact_evaluation.incorrect_count,
                    "standing_facts_not_proposed": standing_fact_evaluation.not_proposed_count,
                    "standing_facts_lineage_incomplete": (
                        standing_fact_evaluation.lineage_incomplete_count
                    ),
                    "standing_facts_not_visible": standing_fact_evaluation.not_visible_count,
                    "replay_model_calls": second_counts["model_runs"] - first_counts["model_runs"],
                },
            }
        )
    finally:
        if temporary is not None:
            temporary.cleanup()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        _canonical_json(report_record.model_dump(mode="json")) + "\n",
        encoding="utf-8",
    )
    print(report_record.summary.model_dump_json())
    return 0 if report_record.summary.passed else 1


def _ingest(config_path: Path, source: Path, url: str) -> JsonObject:
    stdout = io.StringIO()
    stderr = io.StringIO()
    started = time.monotonic()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = ingest_user_file(
            config_path=config_path,
            source_file_path=source,
            source_url=url,
        )
    result = {
        "exit_code": exit_code,
        "elapsed_milliseconds": round((time.monotonic() - started) * 1000),
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    }
    if exit_code != 0:
        raise ValueError(f"HP-8 public ingest failed: {result}")
    return result


def model_evidence(ledger_path: Path, archive_path: Path) -> tuple[JsonObject, list[JsonObject]]:
    archive = LocalArchiveStore(archive_path)
    with sqlite_ledger_transaction(ledger_path) as ledger:
        tasks = {item.id: item for item in ledger.list_extraction_tasks()}
        runs = tuple(ledger.list_model_runs())
    grouped: dict[tuple[str, str], list[JsonObject]] = {}
    executions: list[JsonObject] = []
    for run in runs:
        task = tasks[run.extraction_task_id]
        elapsed_value = run.execution_diagnostics["elapsed_milliseconds"]
        if type(elapsed_value) is not int:
            raise ValueError("ModelRun elapsed milliseconds must be an integer.")
        elapsed = elapsed_value
        receipt = run.execution_receipt or {}
        model_name = str(run.model_identity.get("name") or run.runtime_identity)
        grouped.setdefault((task.task_type, model_name), []).append(
            {
                "elapsed_milliseconds": elapsed,
                "first_response_event_milliseconds": run.execution_diagnostics[
                    "first_response_event_milliseconds"
                ],
                "input_token_count": receipt.get("input_token_count"),
                "output_token_count": receipt.get("output_token_count"),
                "status": run.status.value,
            }
        )
        manifest_payload = task.context_manifest_payload
        rendered_value = manifest_payload.get("rendered_input_base64")
        if rendered_value is None:
            rendered_input = None
        else:
            rendered_context = base64.b64decode(str(rendered_value))
            task_local_value = manifest_payload.get("task_local_input_base64")
            task_local_input = (
                base64.b64decode(str(task_local_value)) if task_local_value is not None else b""
            )
            rendered_input = (
                rendered_context + b"\n\n[task]\n" + task_local_input
                if task_local_input
                else rendered_context
            )
        try:
            raw_output = archive.read_model_run_output(run.id).decode("utf-8")
        except FileNotFoundError:
            raw_output = None
        executions.append(
            {
                "extraction_task_id": task.id,
                "model_run_id": run.id,
                "task_type": task.task_type,
                "model_name": model_name,
                "input_candidate_ids": list(task.input_candidate_ids),
                "rendered_input": (
                    rendered_input.decode("utf-8") if rendered_input is not None else None
                ),
                "context_manifest_payload": manifest_payload,
                "raw_output": raw_output,
                "status": run.status.value,
                "execution_diagnostics": run.execution_diagnostics,
                "execution_receipt": run.execution_receipt,
                "outcome_metadata": run.outcome_metadata,
            }
        )
    performance: list[JsonObject] = []
    for (task_type, model_name), records in sorted(grouped.items()):
        elapsed_values = sorted(int(item["elapsed_milliseconds"]) for item in records)
        input_tokens = sorted(
            int(item["input_token_count"])
            for item in records
            if item["input_token_count"] is not None
        )
        output_tokens = sorted(
            int(item["output_token_count"])
            for item in records
            if item["output_token_count"] is not None
        )
        performance.append(
            {
                "task_type": task_type,
                "model_name": model_name,
                "run_count": len(records),
                "elapsed_milliseconds": {
                    "total": sum(elapsed_values),
                    "p50": _percentile(elapsed_values, 0.50),
                    "p95": _percentile(elapsed_values, 0.95),
                    "maximum": max(elapsed_values),
                },
                "input_token_count": {
                    "total": sum(input_tokens),
                    "p50": _percentile(input_tokens, 0.50),
                    "p95": _percentile(input_tokens, 0.95),
                    "maximum": max(input_tokens, default=0),
                },
                "output_token_count": {
                    "total": sum(output_tokens),
                    "p50": _percentile(output_tokens, 0.50),
                    "p95": _percentile(output_tokens, 0.95),
                    "maximum": max(output_tokens, default=0),
                },
                "statuses": {
                    status: sum(item["status"] == status for item in records)
                    for status in sorted({str(item["status"]) for item in records})
                },
            }
        )
    return {"by_task_type": performance}, sorted(
        executions, key=lambda item: (str(item["task_type"]), str(item["extraction_task_id"]))
    )


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    return values[min(len(values) - 1, max(0, round((len(values) - 1) * fraction)))]


def _document_evidence(
    ledger_path: Path, archive_path: Path
) -> tuple[JsonObject, JsonObject, list[JsonObject]]:
    coverage_paths = tuple((archive_path / "extraction" / "document-coverage").glob("*.json"))
    if len(coverage_paths) != 1:
        raise ValueError("HP-8 canonical run did not produce one coverage report.")
    report_record = hybrid_document_coverage_report_from_bytes(coverage_paths[0].read_bytes())
    policy_path = (
        archive_path
        / "extraction"
        / "document-policies"
        / f"{report_record.policy_manifest_id}.json"
    )
    manifest_record = hybrid_pipeline_policy_manifest_from_bytes(policy_path.read_bytes())
    report = report_record.model_dump(mode="json")
    manifest = manifest_record.model_dump(mode="json")
    archive = LocalArchiveStore(archive_path)
    with sqlite_ledger_transaction(ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(report_record.representation_id)
    if bundle is None:
        raise ValueError("HP-8 coverage references a missing representation.")
    nodes = {item.id: item for item in bundle.nodes}
    text_views = {item.id: item for item in bundle.text_views}
    work_by_node = {item.paragraph_node_id: item for item in manifest_record.work_items}
    paragraphs: list[JsonObject] = []
    for coverage in report_record.records:
        receipt_payload = archive.read_hybrid_paragraph_receipt(coverage.receipt_id)
        receipt = hybrid_paragraph_receipt_from_bytes(receipt_payload)
        node = nodes[coverage.paragraph_node_id]
        text_view = text_views[node.text_view_id]
        stage_outputs = {
            stage.stage_id.value: _stage_output(archive, stage.stage_id, stage.output_id)
            for stage in receipt.stages
            if stage.output_id is not None
        }
        model_run_ids = sorted(_record_ids(stage_outputs, "mrn_"))
        raw_model_outputs = {
            model_run_id: _raw_model_output(archive, model_run_id) for model_run_id in model_run_ids
        }
        paragraphs.append(
            {
                "ordinal": coverage.ordinal,
                "authoritative_text": text_view.text[node.start_char : node.end_char],
                "paragraph_work": work_by_node[node.id].model_dump(mode="json"),
                "paragraph_receipt": receipt.model_dump(mode="json"),
                "stage_outputs": stage_outputs,
                "raw_model_outputs": raw_model_outputs,
            }
        )
    return report, manifest, paragraphs


def _stage_output(
    archive: LocalArchiveStore, stage_id: HybridStageId, output_id: str | None
) -> JsonObject:
    if output_id is None:
        raise ValueError("Executed HP-8 stage has no output identity.")
    readers = {
        HybridStageId.HP1_MENTIONS: archive.read_hybrid_extraction_preview,
        HybridStageId.HP2_REFERENCES: archive.read_hybrid_reference_preview,
        HybridStageId.HP3_GROUNDING: archive.read_hybrid_entity_grounding_preview,
        HybridStageId.HP4_EVENT_TRIGGERS: archive.read_hybrid_event_trigger_preview,
        HybridStageId.HP6_EVENT_SEMANTICS: archive.read_hybrid_event_semantics_preview,
        HybridStageId.HP7_PROPOSAL_PLAN: archive.read_hybrid_proposal_plan,
        HybridStageId.HP10_STANDING_FACTS: archive.read_standing_fact_plan,
    }
    return cast(JsonObject, json.loads(readers[stage_id](output_id)))


def _front_half_evaluation(paragraphs: list[JsonObject]) -> FrontHalfEvaluationReport:
    """Evaluate the reviewed mention/reference corpus against production stage records."""
    _, inputs = load_front_half_inputs(FRONT_HALF_SPLIT, repository_root=ROOT)
    wanted_digests = {item.source_text_sha256 for item in inputs}
    stages_by_digest: dict[str, tuple[HybridExtractionPreview, HybridReferencePreview | None]] = {}
    for paragraph in paragraphs:
        source_text = paragraph.get("authoritative_text")
        if not isinstance(source_text, str):
            raise ValueError("Paragraph evidence has no authoritative text.")
        stage_outputs = cast(JsonObject, paragraph["stage_outputs"])
        mention_payload = stage_outputs.get(HybridStageId.HP1_MENTIONS.value)
        if not isinstance(mention_payload, dict):
            raise ValueError("Current Front-Half evaluation requires mention evidence.")
        mention = hybrid_extraction_preview_from_bytes(
            _canonical_json(cast(JsonObject, mention_payload)).encode()
        )
        reference_payload = stage_outputs.get(HybridStageId.HP2_REFERENCES.value)
        references = (
            hybrid_reference_preview_from_bytes(
                _canonical_json(cast(JsonObject, reference_payload)).encode()
            )
            if isinstance(reference_payload, dict)
            else None
        )
        for segment in paragraph_source_segments(source_text, PARAGRAPH_SEGMENT_V3):
            digest = hashlib.sha256(segment.exact_text.encode()).hexdigest()
            if digest not in wanted_digests:
                continue
            if digest in stages_by_digest:
                raise ValueError("Front-Half evaluation found a repeated SourceSegment.")
            stages_by_digest[digest] = (mention, references)
    evaluations: list[FrontHalfCaseEvaluation] = []
    for stage_input in inputs:
        evidence = stages_by_digest.get(stage_input.source_text_sha256)
        if evidence is None:
            raise ValueError(
                f"Front-Half evaluation is missing SourceSegment {stage_input.source_text_sha256}."
            )
        evaluations.append(evaluate_front_half_case(stage_input, evidence[0], evidence[1]))
    return build_front_half_evaluation_report(tuple(evaluations))


def _standing_fact_evaluation(
    paragraphs: list[JsonObject],
    wiki_plan: CandidateWikiPlan,
    ledger_path: Path,
) -> StandingFactEvaluationReport:
    """Evaluate current Standing Fact plans and their Candidate Wiki projection."""
    evidence: dict[int, StandingFactRuntimeEvidence] = {}
    for paragraph in paragraphs:
        ordinal = paragraph.get("ordinal")
        if type(ordinal) is not int:
            raise ValueError("Paragraph evidence has no integer ordinal.")
        stage_outputs = cast(JsonObject, paragraph["stage_outputs"])
        payload = stage_outputs.get(HybridStageId.HP10_STANDING_FACTS.value)
        if isinstance(payload, dict):
            plan = standing_fact_plan_from_bytes(
                (_canonical_json(cast(JsonObject, payload)) + "\n").encode()
            )
            evidence[ordinal] = standing_fact_evidence_from_plan(ordinal, plan)
    with sqlite_ledger_transaction(ledger_path) as ledger:
        change_set = ledger.get_ingestion_change_set(wiki_plan.ingestion_change_set_id)
        if change_set is None:
            raise ValueError("Candidate Wiki references a missing IngestionChangeSet.")
        changes = tuple(
            change
            for change_id in change_set.proposed_change_ids
            if (change := ledger.get_proposed_change(change_id)) is not None
        )
        if len(changes) != len(change_set.proposed_change_ids):
            raise ValueError("IngestionChangeSet references a missing ProposedChange.")
    return evaluate_standing_fact_gold(
        load_standing_fact_gold(STANDING_FACT_GOLD),
        evidence,
        reconciled_records=standing_fact_reconciliation_from_proposed_changes(changes),
        wiki_plan=wiki_plan,
    )


def _source_grounded_event_evaluation(
    *,
    paragraphs: list[JsonObject],
    coverage_report: JsonObject,
    ledger_path: Path,
    archive_path: Path,
) -> SourceGroundedEventEvaluationReport:
    """Evaluate persisted source-grounded Events against the approved Gold catalog."""
    coverage_report_id = coverage_report.get("id")
    if not isinstance(coverage_report_id, str):
        raise ValueError("Document coverage report has no string identity.")
    archive = LocalArchiveStore(archive_path)
    coverage_payload = archive.read_hybrid_document_coverage_report(coverage_report_id)
    reloaded_coverage = hybrid_document_coverage_report_from_bytes(coverage_payload)
    if reloaded_coverage.model_dump(mode="json") != coverage_report:
        raise ValueError("Reloaded document coverage report does not match report evidence.")

    catalog, trigger_gold = load_source_grounded_event_gold(
        SOURCE_GROUNDED_EVENT_GOLD,
        repository_root=ROOT,
    )
    segment_counts: Counter[str] = Counter()
    triggers_by_digest: dict[str, dict[str, EventTriggerDraft]] = {}
    events_by_digest: dict[str, dict[str, SourceGroundedEventDraft]] = {}
    evidence_target_ids: set[str] = set()
    for paragraph in paragraphs:
        authoritative_text = paragraph.get("authoritative_text")
        if not isinstance(authoritative_text, str):
            raise ValueError("Paragraph evidence has no authoritative text.")
        for segment in paragraph_source_segments(authoritative_text, PARAGRAPH_SEGMENT_V3):
            segment_counts[hashlib.sha256(segment.exact_text.encode()).hexdigest()] += 1

        stage_outputs = cast(JsonObject, paragraph["stage_outputs"])
        trigger_payload = stage_outputs.get(HybridStageId.HP4_EVENT_TRIGGERS.value)
        event_payload = stage_outputs.get(HybridStageId.HP6_EVENT_SEMANTICS.value)
        if trigger_payload is None or event_payload is None:
            continue
        trigger_preview = hybrid_event_trigger_preview_from_bytes(
            _canonical_json(trigger_payload).encode()
        )
        event_preview = hybrid_event_semantics_preview_from_bytes(
            _canonical_json(event_payload).encode()
        )
        if event_preview.parent_preview_id != trigger_preview.id:
            raise ValueError("Source-grounded Event evidence has the wrong trigger parent.")
        for trigger in trigger_preview.triggers:
            _add_immutable(
                triggers_by_digest.setdefault(trigger.source_text_sha256, {}),
                trigger.id,
                trigger,
            )
        for event in event_preview.source_grounded_events:
            _add_immutable(
                events_by_digest.setdefault(event.source_text_sha256, {}),
                event.id,
                event,
            )
            evidence_target_ids.update(
                (
                    event.mention.head_evidence_target_id,
                    event.mention.expression_evidence_target_id,
                    event.mention.support_evidence_target_id,
                )
            )

    evidence_by_id: dict[str, EvidenceTarget] = {}
    with sqlite_ledger_transaction(ledger_path) as ledger:
        for evidence_target_id in sorted(evidence_target_ids):
            target = ledger.get_evidence_target(evidence_target_id)
            if target is None:
                raise ValueError("Source-grounded Event evidence is missing from the Ledger.")
            evidence_by_id[evidence_target_id] = target

    evaluation = evaluate_source_grounded_event_corpus(
        catalog=catalog,
        trigger_gold=trigger_gold,
        catalog_sha256=hashlib.sha256(SOURCE_GROUNDED_EVENT_GOLD.read_bytes()).hexdigest(),
        coverage_report_id=coverage_report_id,
        coverage_report_sha256=hashlib.sha256(coverage_payload).hexdigest(),
        representation_id=str(coverage_report["representation_id"]),
        source_segment_observation_counts=segment_counts,
        triggers_by_source_text_sha256={
            digest: tuple(sorted(items.values(), key=lambda item: item.id))
            for digest, items in triggers_by_digest.items()
        },
        source_events_by_source_text_sha256={
            digest: tuple(sorted(items.values(), key=lambda item: item.id))
            for digest, items in events_by_digest.items()
        },
        evidence_by_id=evidence_by_id,
    )
    return evaluation


def _add_immutable[T](records: dict[str, T], record_id: str, record: T) -> None:
    existing = records.get(record_id)
    if existing is not None and existing != record:
        raise ValueError(f"Conflicting immutable record: {record_id}")
    records[record_id] = record


def _publish_candidate_wiki(
    filename: str, ledger_path: Path, archive_path: Path
) -> tuple[JsonObject, CandidateWikiPlan]:
    archive = LocalArchiveStore(archive_path)
    archive.initialize()
    with sqlite_ledger_transaction(ledger_path) as ledger:
        selection = select_candidate_ingestions(filename, ledger)
        run = selection.matches[0]
        plan = plan_candidate_wiki(build_candidate_knowledge_view(run, ledger))
    published = archive.publish_candidate_wiki(MarkdownCandidateWikiRenderer().render(plan))
    archive.read_candidate_wiki_audit_bundle(published.build_id)
    return (
        {
            "build_id": published.build_id,
            "disposition": published.disposition,
            "active_path": str(archive_path / published.active_relative_path),
            "build_path": str(archive_path / "review/wiki-builds" / published.build_id),
        },
        plan,
    )


def _findings(
    *,
    configured: PipelineConfig,
    report: JsonObject,
    manifest: JsonObject,
    first_counts: JsonObject,
    second_counts: JsonObject,
    origins: list[str],
    front_half_evaluation: FrontHalfEvaluationReport,
    source_grounded_event_evaluation: SourceGroundedEventEvaluationReport,
    standing_fact_evaluation: StandingFactEvaluationReport,
    paragraphs: list[JsonObject],
) -> list[JsonObject]:
    findings: list[JsonObject] = []
    required = int(report["required_paragraph_count"])
    if required == 0 or required != int(report["complete_paragraph_count"]) + int(
        report["gap_paragraph_count"]
    ):
        findings.append({"code": "document_scope_unaccounted"})
    if first_counts["model_runs"] != second_counts["model_runs"]:
        findings.append({"code": "replay_created_model_runs"})
    if first_counts["extraction_tasks"] != second_counts["extraction_tasks"]:
        findings.append({"code": "replay_created_extraction_tasks"})
    accepted_counts = {
        key: first_counts[key]
        for key in (
            "accepted_actors",
            "accepted_organizations",
            "accepted_events",
            "accepted_assertions",
        )
        if first_counts[key] != 0
    }
    if accepted_counts:
        findings.append(
            {
                "code": "ingestion_created_accepted_intelligence",
                "actual": accepted_counts,
            }
        )
    ledger_proposal_ids = cast(list[str], first_counts["proposed_change_ids"])
    change_set_proposal_sets = cast(
        list[list[str]], first_counts["ingestion_change_set_proposal_sets"]
    )
    if (
        first_counts["proposed_changes"] != first_counts["pending_proposed_changes"]
        or not change_set_proposal_sets
        or any(item != ledger_proposal_ids for item in change_set_proposal_sets)
    ):
        findings.append(
            {
                "code": "pending_proposal_set_mismatch",
                "ledger": first_counts,
                "paragraph_proposed_change_ids": report["proposed_change_ids"],
            }
        )
    if origins.count(IngestionChangeSetOrigin.EXECUTED.value) != 1 or not any(
        item == IngestionChangeSetOrigin.REUSED.value for item in origins
    ):
        findings.append({"code": "replay_origin_invalid", "actual": origins})
    model = cast(JsonObject, manifest["model_identity"])
    proposer = cast(JsonObject, manifest["mention_proposer_identity"])
    linker = cast(JsonObject, manifest["entity_linker_identity"])
    if model.get("adapter") != "lm_studio" or "qwen2.5" not in str(model.get("name", "")).lower():
        findings.append({"code": "qwen25_runtime_not_pinned", "actual": model})
    if "gliner" not in str(proposer.get("producer_id", "")):
        findings.append({"code": "gliner_not_pinned", "actual": proposer})
    if linker.get("configured") is not True:
        findings.append({"code": "refined_not_configured", "actual": linker})
    producer_ids = sorted(
        {
            producer_id
            for paragraph in paragraphs
            for producer_id in _field_values(paragraph["stage_outputs"], "producer_id")
        }
    )
    for expected_producer in ("qwen2.5", "gliner", "refined"):
        if not any(expected_producer in item.lower() for item in producer_ids):
            findings.append(
                {
                    "code": "configured_producer_not_observed",
                    "expected": expected_producer,
                    "observed": producer_ids,
                }
            )
    if not front_half_evaluation.passed:
        findings.append(
            {
                "code": "front_half_gold_mismatch",
                "expected": front_half_evaluation.item_count,
                "exact": front_half_evaluation.passed_count,
                "failing_items": [
                    item.model_dump(mode="json")
                    for item in front_half_evaluation.cases
                    if not item.passed
                ],
            }
        )
    if not source_grounded_event_evaluation.passed:
        findings.append(
            {
                "code": "source_grounded_event_gold_mismatch",
                "missing_event_count": source_grounded_event_evaluation.missing_event_count,
                "extra_event_count": source_grounded_event_evaluation.extra_event_count,
                "incorrectly_grounded_event_count": (
                    source_grounded_event_evaluation.incorrectly_grounded_event_count
                ),
                "failing_segments": [
                    item.model_dump(mode="json")
                    for item in source_grounded_event_evaluation.segments
                    if not item.passed
                ],
            }
        )
    if not standing_fact_evaluation.passed:
        findings.append(
            {
                "code": "standing_fact_gold_mismatch",
                "expected": standing_fact_evaluation.item_count,
                "exact": standing_fact_evaluation.exact_count,
                "failing_items": [
                    item.model_dump(mode="json")
                    for item in standing_fact_evaluation.items
                    if not item.passed
                ],
            }
        )
    return findings


def _ledger_counts(ledger_path: Path) -> JsonObject:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        proposals = ledger.list_proposed_changes()
        proposal_ids = sorted(item.id for item in proposals)
        change_sets = [
            change_set
            for run in ledger.list_ingestion_runs()
            if run.ingestion_change_set_id is not None
            and (change_set := ledger.get_ingestion_change_set(run.ingestion_change_set_id))
            is not None
        ]
        return {
            "extraction_tasks": len(ledger.list_extraction_tasks()),
            "model_runs": len(ledger.list_model_runs()),
            "proposed_changes": len(proposals),
            "pending_proposed_changes": sum(
                item.review_status is ReviewStatus.PENDING for item in proposals
            ),
            "proposed_change_ids": proposal_ids,
            "ingestion_change_set_proposal_sets": [
                list(item.proposed_change_ids)
                for item in sorted(change_sets, key=lambda item: item.ingestion_run_id)
            ],
            "accepted_actors": len(ledger.list_actors()),
            "accepted_organizations": len(ledger.list_organizations()),
            "accepted_events": len(ledger.list_events()),
            "accepted_assertions": len(ledger.list_assertions()),
        }


def _change_set_origins(ledger_path: Path) -> list[str]:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        origins: list[str] = []
        for run in ledger.list_ingestion_runs():
            if run.ingestion_change_set_id is None:
                continue
            change_set = ledger.get_ingestion_change_set(run.ingestion_change_set_id)
            if change_set is None:
                raise ValueError("Captured HP-8 run lost its IngestionChangeSet.")
            origins.append(change_set.analysis_origin.value)
    return sorted(origins)


def _validate_locked_source(source: Path) -> None:
    scenario = _read_json(SCENARIO)
    fixture = cast(JsonObject, scenario["fixture"])
    lock = cast(JsonObject, fixture["fixture_lock"])
    if not source.is_file():
        raise ValueError(f"Canonical HP-8 source is missing: {source}")
    if hashlib.sha256(source.read_bytes()).hexdigest() != lock["sha256"]:
        raise ValueError("Canonical HP-8 source does not match its fixture lock.")


def _isolated_config(config: PipelineConfig, ledger: Path, archive: Path) -> str:
    runtime = config.model_execution
    lines = [
        f"ledger_path = {_toml(ledger)}",
        f"archive_path = {_toml(archive)}",
        'runtime_profile = "hp8-canonical"',
        "",
        "[processing]",
        'representation_policy_version = "deposited-source-v1"',
        "",
        "[runtime_profiles.hp8-canonical]",
        f"adapter = {_toml(runtime.adapter)}",
        f"endpoint = {_toml(runtime.endpoint)}",
        f"model = {_toml(runtime.model)}",
        f"timeout_seconds = {runtime.timeout_seconds}",
        f"context_tokens = {runtime.context_tokens}",
        f"max_output_tokens = {runtime.max_output_tokens}",
        "",
        "[model_resources]",
        f"root = {_toml(config.model_resource_root)}",
    ]
    linker = config.entity_linking
    lines.extend(
        (
            "",
            "[entity_linking]",
            f"adapter = {_toml(linker.adapter)}",
            f"timeout_seconds = {linker.timeout_seconds}",
        )
    )
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> JsonObject:
    return cast(JsonObject, json.loads(path.read_text(encoding="utf-8")))


def _toml(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _record_ids(value: object, prefix: str) -> set[str]:
    if isinstance(value, str):
        return {value} if value.startswith(prefix) else set()
    if isinstance(value, dict):
        return {
            record_id
            for item in cast(dict[object, object], value).values()
            for record_id in _record_ids(item, prefix)
        }
    if isinstance(value, list):
        return {
            record_id
            for item in cast(list[object], value)
            for record_id in _record_ids(item, prefix)
        }
    return set()


def _field_values(value: object, field: str) -> set[str]:
    if isinstance(value, dict):
        values = {
            str(item)
            for key, item in cast(dict[object, object], value).items()
            if key == field and isinstance(item, str)
        }
        return values | {
            found
            for item in cast(dict[object, object], value).values()
            for found in _field_values(item, field)
        }
    if isinstance(value, list):
        return {found for item in cast(list[object], value) for found in _field_values(item, field)}
    return set()


def _raw_model_output(archive: LocalArchiveStore, model_run_id: str) -> JsonObject:
    try:
        payload = archive.read_model_run_output(model_run_id)
    except FileNotFoundError:
        return {"archive_status": "not_archived", "raw_output": None}
    return {"archive_status": "available", "raw_output": payload.decode("utf-8")}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
