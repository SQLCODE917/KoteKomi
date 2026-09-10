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
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    HybridStageId,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_pipeline_policy_manifest_from_bytes,
)
from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    WikiEventPresentation,
    build_candidate_knowledge_view,
    plan_candidate_wiki,
    select_candidate_ingestions,
)
from kotekomi_domain import IngestionChangeSetOrigin, ReviewStatus
from kotekomi_exporters import MarkdownCandidateWikiRenderer
from kotekomi_pipelines.cli import ingest_user_file
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.semantic_quality_oracle import (
    final_gold_findings,
    first_failed_event_stage,
    gold_source_text_matches,
    required_event_findings,
)
from kotekomi_pipelines.task_allocation_evaluation import (
    TaskAllocationBaselineComparison,
    TaskAllocationCatalogEvaluation,
    TaskAllocationRunCost,
    compare_task_allocation_baseline,
    evaluate_task_allocation_catalog,
    load_task_allocation_baseline,
    load_task_allocation_evaluator_corrections,
    load_task_allocation_gold,
    task_allocation_item_has_wrong_forced_frame,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json"
HP7_GOLD = ROOT / "docs/hp7-proposal-admission-gold-v1.json"
AMODEI_GOLD = ROOT / "docs/hsq-amodei-intelligence-gold-v1.json"
TASK_ALLOCATION_AMODEI_GOLD = ROOT / "docs/hsq-task-allocation-amodei-gold-v1.json"
TASK_ALLOCATION_ANTHROPIC_GOLD = ROOT / "docs/hsq-task-allocation-anthropic-gold-v1.json"
TASK_ALLOCATION_BASELINE = ROOT / "docs/hsq-task-allocation-baseline-2026-09-08.json"
TASK_ALLOCATION_EVALUATOR_CORRECTIONS = ROOT / "docs/hsq-stage-local-evaluator-corrections-v1.json"
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
        gold_results = _gold_event_results(paragraphs)
        proposed_records = _proposed_records(ledger_path)
        amodei_results = _amodei_event_results(paragraphs, proposed_records)
        wiki_evidence, wiki_plan = _publish_candidate_wiki(
            source.name,
            ledger_path,
            archive_path,
        )
        _add_wiki_results(amodei_results, wiki_plan, LocalArchiveStore(archive_path))
        evaluator_corrections = load_task_allocation_evaluator_corrections(
            TASK_ALLOCATION_EVALUATOR_CORRECTIONS
        )
        task_allocation_evaluations = tuple(
            evaluate_task_allocation_catalog(
                load_task_allocation_gold(path),
                paragraphs,
                wiki_plan=wiki_plan,
                evaluator_corrections=evaluator_corrections,
            )
            for path in (TASK_ALLOCATION_AMODEI_GOLD, TASK_ALLOCATION_ANTHROPIC_GOLD)
        )
        task_allocation_cost = _task_allocation_run_cost(first_counts, model_performance)
        task_allocation_baseline = load_task_allocation_baseline(TASK_ALLOCATION_BASELINE)
        if (
            task_allocation_baseline.source_fixture_sha256
            != hashlib.sha256(source.read_bytes()).hexdigest()
        ):
            raise ValueError("Task-allocation baseline source fixture does not match this run.")
        task_allocation_comparison = compare_task_allocation_baseline(
            task_allocation_baseline,
            task_allocation_evaluations,
            task_allocation_cost,
        )
        findings = _findings(
            configured=configured,
            report=report,
            manifest=manifest,
            first_counts=first_counts,
            second_counts=second_counts,
            origins=origins,
            gold_results=gold_results,
            amodei_results=amodei_results,
            paragraphs=paragraphs,
        )
        findings.extend(
            _task_allocation_findings(
                task_allocation_evaluations,
                task_allocation_comparison,
            )
        )
        approved_gold = [item for item in gold_results if item["review_outcome"] == "approved"]
        rejected_gold = [item for item in gold_results if item["review_outcome"] == "rejected"]
        payload = {
            "schema_version": "hp8_document_orchestration_evaluation_v1",
            "source_path": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "policy_manifest": manifest,
            "coverage_report": report,
            "paragraphs": paragraphs,
            "gold_event_retention": gold_results,
            "amodei_gold_event_retention": amodei_results,
            "task_allocation_evaluations": [
                item.model_dump(mode="json") for item in task_allocation_evaluations
            ],
            "task_allocation_baseline_comparison": task_allocation_comparison.model_dump(
                mode="json"
            ),
            "task_allocation_evaluator_corrections": {
                "path": TASK_ALLOCATION_EVALUATOR_CORRECTIONS.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(
                    TASK_ALLOCATION_EVALUATOR_CORRECTIONS.read_bytes()
                ).hexdigest(),
                "parent_validation_manifest_sha256": (
                    evaluator_corrections.parent_validation_manifest_sha256
                ),
                "parent_validation_report_sha256": (
                    evaluator_corrections.parent_validation_report_sha256
                ),
            },
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
                "gold_events_observed": sum(item["observed"] for item in gold_results),
                "gold_events_with_complete_lineage": sum(
                    item["lineage_complete"] for item in gold_results
                ),
                "gold_events_expected": len(gold_results),
                "approved_gold_events_observed": sum(item["observed"] for item in approved_gold),
                "approved_gold_events_with_complete_lineage": sum(
                    item["lineage_complete"] for item in approved_gold
                ),
                "approved_gold_events_expected": len(approved_gold),
                "approved_gold_events_proposed": sum(
                    item["disposition_matches"] and item["proposal_presence_matches"]
                    for item in approved_gold
                ),
                "known_false_events_observed": sum(item["observed"] for item in rejected_gold),
                "known_false_events_expected": len(rejected_gold),
                "known_false_events_excluded": sum(
                    item["disposition_matches"] and item["proposal_presence_matches"]
                    for item in rejected_gold
                ),
                "amodei_events_expected": len(amodei_results),
                "amodei_events_complete": sum(
                    first_failed_event_stage(item) is None for item in amodei_results
                ),
                "task_allocation_items_expected": sum(
                    item.item_count for item in task_allocation_evaluations
                ),
                "task_allocation_items_complete": sum(
                    item.passed_count for item in task_allocation_evaluations
                ),
                "task_allocation_items_at_review": sum(
                    item.review_count for item in task_allocation_evaluations
                ),
                "task_allocation_items_on_wiki": sum(
                    item.wiki_visible_count for item in task_allocation_evaluations
                ),
                "task_allocation_wrong_forced_frames": sum(
                    item.wrong_forced_frame_count for item in task_allocation_evaluations
                ),
                "task_allocation_newly_complete": sum(
                    len(item.newly_complete_item_ids)
                    for item in task_allocation_comparison.catalogs
                ),
                "task_allocation_regressed": sum(
                    len(item.regressed_item_ids) for item in task_allocation_comparison.catalogs
                ),
                "task_allocation_model_run_delta": (
                    task_allocation_comparison.model_run_count_delta
                ),
                "task_allocation_model_elapsed_milliseconds_delta": (
                    task_allocation_comparison.total_model_elapsed_milliseconds_delta
                ),
                "replay_model_calls": second_counts["model_runs"] - first_counts["model_runs"],
            },
        }
    finally:
        if temporary is not None:
            temporary.cleanup()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0 if not findings else 1


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


def _gold_event_results(paragraphs: list[JsonObject]) -> list[JsonObject]:
    observed: dict[str, list[JsonObject]] = {}
    for paragraph in paragraphs:
        stage_outputs = cast(JsonObject, paragraph["stage_outputs"])
        hp4 = cast(
            JsonObject | None,
            stage_outputs.get(HybridStageId.HP4_EVENT_TRIGGERS.value),
        )
        if hp4 is None:
            continue
        hp6 = cast(
            JsonObject | None,
            stage_outputs.get(HybridStageId.HP6_EVENT_SEMANTICS.value),
        )
        hp7 = cast(
            JsonObject | None,
            stage_outputs.get(HybridStageId.HP7_PROPOSAL_PLAN.value),
        )
        source_text_by_segment = {
            str(trace["source_segment_id"]): str(cast(JsonObject, trace["input"])["source_text"])
            for trace in cast(list[JsonObject], hp4["traces"])
            if cast(JsonObject, trace["input"]).get("source_text") is not None
        }
        semantic_by_trigger: dict[str, JsonObject] = {}
        if hp6 is not None:
            semantic_by_trigger = {
                str(event["trigger_id"]): event
                for event in cast(list[JsonObject], hp6["semantic_events"])
            }
        decision_by_event: dict[str, JsonObject] = {}
        if hp7 is not None:
            decision_by_event = {
                str(decision["event_semantic_id"]): decision
                for decision in cast(list[JsonObject], hp7["decisions"])
            }
        for trigger in cast(list[JsonObject], hp4["triggers"]):
            semantic = semantic_by_trigger.get(str(trigger["id"]))
            decision = decision_by_event.get(str(semantic["id"])) if semantic is not None else None
            key = _normalize(source_text_by_segment[str(trigger["source_segment_id"])])
            observed.setdefault(key, []).append(
                {
                    "paragraph_ordinal": paragraph["ordinal"],
                    "trigger_id": trigger["id"],
                    "trigger_text": trigger["text"],
                    "event_semantic_id": semantic["id"] if semantic is not None else None,
                    "frame_id": semantic["frame_id"] if semantic is not None else None,
                    "admission_decision_id": decision["id"] if decision is not None else None,
                    "admission_disposition": (
                        decision["disposition"] if decision is not None else None
                    ),
                    "proposed_change_ids": (
                        decision["proposed_change_ids"] if decision is not None else []
                    ),
                }
            )
    gold = _read_json(HP7_GOLD)
    results: list[JsonObject] = []
    for item in cast(list[JsonObject], gold["cases"]):
        expected_trigger = _normalize(str(item["trigger"]))
        expected_frame_id = str(item["frame_id"])
        matches = [
            match
            for match in observed.get(_normalize(str(item["source_text"])), [])
            if _trigger_retains_gold(expected_trigger, _normalize(str(match["trigger_text"])))
            and match["frame_id"] == expected_frame_id
        ]
        match = matches[0] if len(matches) == 1 else None
        excluded = item["expected_disposition"] == "excluded"
        results.append(
            {
                "case_id": item["case_id"],
                "source_text": item["source_text"],
                "trigger": item["trigger"],
                "frame_id": expected_frame_id,
                "expected_disposition": item["expected_disposition"],
                "review_outcome": item["review_outcome"],
                "observed": bool(matches),
                "trigger_match": (
                    "exact"
                    if match is not None
                    and _normalize(str(match["trigger_text"])) == expected_trigger
                    else "expanded_literal"
                    if match is not None
                    else None
                ),
                "lineage_complete": (
                    all(
                        candidate["event_semantic_id"] is not None
                        and candidate["admission_decision_id"] is not None
                        for candidate in matches
                    )
                    if excluded
                    else match is not None
                    and match["event_semantic_id"] is not None
                    and match["admission_decision_id"] is not None
                ),
                "disposition_matches": (
                    all(candidate["admission_disposition"] == "held" for candidate in matches)
                    if excluded
                    else match is not None
                    and match["admission_disposition"] == item["expected_disposition"]
                ),
                "proposal_presence_matches": (
                    all(not candidate["proposed_change_ids"] for candidate in matches)
                    if excluded
                    else match is not None and bool(match["proposed_change_ids"])
                ),
                "matches": matches,
            }
        )
    return results


def _amodei_event_results(
    paragraphs: list[JsonObject],
    proposed_records: dict[str, JsonObject],
) -> list[JsonObject]:
    observed_by_source: dict[str, list[JsonObject]] = {}
    for paragraph in paragraphs:
        stages = cast(JsonObject, paragraph["stage_outputs"])
        hp1 = cast(JsonObject | None, stages.get(HybridStageId.HP1_MENTIONS.value))
        hp4 = cast(JsonObject | None, stages.get(HybridStageId.HP4_EVENT_TRIGGERS.value))
        hp6 = cast(JsonObject | None, stages.get(HybridStageId.HP6_EVENT_SEMANTICS.value))
        hp7 = cast(JsonObject | None, stages.get(HybridStageId.HP7_PROPOSAL_PLAN.value))
        if hp4 is None:
            continue
        candidates = (
            {str(item["id"]): item for item in cast(list[JsonObject], hp1["candidates"])}
            if hp1 is not None
            else {}
        )
        source_by_segment = {
            str(trace["source_segment_id"]): str(cast(JsonObject, trace["input"])["source_text"])
            for trace in cast(list[JsonObject], hp4["traces"])
            if cast(JsonObject, trace["input"]).get("source_text") is not None
        }
        semantic_by_trigger = {
            str(item["trigger_id"]): item
            for item in cast(list[JsonObject], hp6["semantic_events"] if hp6 else [])
        }
        assignments = cast(list[JsonObject], hp6["assignments"] if hp6 else [])
        targets = {
            str(item["id"]): item for item in cast(list[JsonObject], hp6["targets"] if hp6 else [])
        }
        qualifiers = cast(list[JsonObject], hp6["qualifiers"] if hp6 else [])
        propositions = {
            str(item["subject_record_id"]): item
            for item in cast(list[JsonObject], hp6["propositions"] if hp6 else [])
        }
        proposition_decisions = {
            str(item["proposition_id"]): item
            for item in cast(list[JsonObject], hp6["proposition_decisions"] if hp6 else [])
        }
        admission_by_event = {
            str(item["event_semantic_id"]): item
            for item in cast(list[JsonObject], hp7["decisions"] if hp7 else [])
        }
        for source_segment_id, source_text in source_by_segment.items():
            observations = observed_by_source.setdefault(_normalize(source_text), [])
            segment_candidates = {
                candidate_id: item
                for candidate_id, item in candidates.items()
                if item.get("source_segment_id") == source_segment_id
            }
            for trigger in cast(list[JsonObject], hp4["triggers"]):
                if trigger.get("source_segment_id") != source_segment_id:
                    continue
                semantic = semantic_by_trigger.get(str(trigger["id"]))
                event_assignments = (
                    [
                        item
                        for item in assignments
                        if item.get("event_subject_id") == semantic.get("event_subject_id")
                    ]
                    if semantic is not None
                    else []
                )
                event_qualifiers = (
                    [
                        item
                        for item in qualifiers
                        if item.get("event_subject_id") == semantic.get("event_subject_id")
                    ]
                    if semantic is not None
                    else []
                )
                proposition = propositions.get(str(semantic["id"])) if semantic else None
                support = (
                    proposition_decisions.get(str(proposition["id"]))
                    if proposition is not None
                    else None
                )
                admission = admission_by_event.get(str(semantic["id"])) if semantic else None
                proposal_ids = (
                    cast(list[str], admission["proposed_change_ids"])
                    if admission is not None
                    else []
                )
                observations.append(
                    {
                        "paragraph_ordinal": paragraph["ordinal"],
                        "source_segment_id": source_segment_id,
                        "source_text": source_text,
                        "trigger": trigger,
                        "semantic": semantic,
                        "assignments": event_assignments,
                        "targets": targets,
                        "qualifiers": event_qualifiers,
                        "candidates": segment_candidates,
                        "support": support,
                        "admission": admission,
                        "event_record_id": _event_record_id(proposal_ids, proposed_records),
                    }
                )

    gold = _read_json(AMODEI_GOLD)
    results: list[JsonObject] = []
    for case in cast(list[JsonObject], gold["cases"]):
        source_text = str(case["source_text"])
        source_observations = observed_by_source.get(_normalize(source_text), [])
        for expected in cast(list[JsonObject], case["expected_events"]):
            expected_trigger = _normalize(str(expected["trigger_text"]))
            trigger_matches = [
                item
                for item in source_observations
                if _trigger_retains_gold(
                    expected_trigger,
                    _normalize(str(cast(JsonObject, item["trigger"])["text"])),
                )
            ]
            evaluated = [
                (item, *_semantic_contract_match(expected, item)) for item in trigger_matches
            ]
            selected_tuple = next((item for item in evaluated if item[1]), None)
            if selected_tuple is None and evaluated:
                selected_tuple = evaluated[0]
            selected = selected_tuple[0] if selected_tuple is not None else None
            semantics_match = selected_tuple[1] if selected_tuple is not None else False
            semantic_mismatches = selected_tuple[2] if selected_tuple is not None else []
            support = cast(JsonObject | None, selected["support"] if selected else None)
            admission = cast(JsonObject | None, selected["admission"] if selected else None)
            result: JsonObject = {
                "case_id": case["case_id"],
                "event_key": expected["event_key"],
                "source_text": source_text,
                "expected_summary": expected["expected_summary"],
                "source_observed": bool(source_observations),
                "trigger_observed": bool(trigger_matches),
                "semantics_match": semantics_match,
                "semantic_mismatches": semantic_mismatches,
                "support_match": support is not None and support.get("disposition") == "supported",
                "proposal_match": admission is not None
                and admission.get("disposition") == expected["expected_disposition"]
                and bool(admission.get("proposed_change_ids")),
                "event_record_id": selected["event_record_id"] if selected else None,
                "wiki_match": False,
                "audit_match": False,
                "observed": selected,
            }
            results.append(result)
    return results


def _semantic_contract_match(
    expected: JsonObject, observation: JsonObject
) -> tuple[bool, list[JsonObject]]:
    semantic = cast(JsonObject | None, observation["semantic"])
    if semantic is None:
        return False, [{"field": "semantic_event", "expected": "present", "actual": None}]
    mismatches: list[JsonObject] = []
    for field, actual_field in (
        ("frame_id", "frame_id"),
        ("polarity", "polarity"),
        ("modality", "modality"),
        ("attribution", "attribution_kind"),
    ):
        if semantic.get(actual_field) != expected.get(field):
            mismatches.append(
                {
                    "field": field,
                    "expected": expected.get(field),
                    "actual": semantic.get(actual_field),
                }
            )
    assignments = cast(list[JsonObject], observation["assignments"])
    targets = cast(dict[str, JsonObject], observation["targets"])
    candidates = cast(dict[str, JsonObject], observation["candidates"])
    for role in cast(list[JsonObject], expected.get("roles", [])):
        matching_assignments = [
            item for item in assignments if item.get("frame_role_id") == role["frame_role_id"]
        ]
        target_matches: list[JsonObject] = []
        for assignment in matching_assignments:
            target = targets.get(str(assignment["target_id"]))
            if target is None:
                continue
            embedded_texts = {
                _normalize(str(candidates[candidate_id]["text"]))
                for candidate_id in cast(list[str], target.get("embedded_candidate_ids", []))
                if candidate_id in candidates
            }
            expected_embedded = {
                _normalize(str(item["exact_text"]))
                for item in cast(list[JsonObject], role.get("referenced_entities", []))
            }
            if (
                target.get("kind") == role["target_kind"]
                and gold_source_text_matches(
                    _normalize(str(target.get("text", ""))),
                    _normalize(str(role["exact_text"])),
                )
                and (
                    role.get("start") is None
                    or (target.get("start") == role["start"] and target.get("end") == role["end"])
                )
                and expected_embedded.issubset(embedded_texts)
            ):
                target_matches.append(target)
        if len(target_matches) != 1:
            mismatches.append(
                {
                    "field": str(role["frame_role_id"]),
                    "expected": role,
                    "actual": [
                        targets.get(str(item["target_id"])) for item in matching_assignments
                    ],
                }
            )
    actual_qualifiers = cast(list[JsonObject], observation["qualifiers"])
    for qualifier in cast(list[JsonObject], expected.get("qualifiers", [])):
        if not any(
            item.get("kind") == qualifier["kind"]
            and _normalize(str(item.get("text", ""))) == _normalize(str(qualifier["exact_text"]))
            and (
                qualifier.get("relation") is None
                or item.get("temporal_relation") == qualifier["relation"]
            )
            for item in actual_qualifiers
        ):
            mismatches.append(
                {
                    "field": f"qualifier:{qualifier['kind']}",
                    "expected": qualifier,
                    "actual": actual_qualifiers,
                }
            )
    return not mismatches, mismatches


def _event_record_id(
    proposal_ids: list[str], proposed_records: dict[str, JsonObject]
) -> str | None:
    matches = [
        cast(JsonObject, proposed_records[item]["record"])["id"]
        for item in proposal_ids
        if item in proposed_records and proposed_records[item].get("record_type") == "Event"
    ]
    return str(matches[0]) if len(matches) == 1 else None


def _proposed_records(ledger_path: Path) -> dict[str, JsonObject]:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        return {
            item.id: cast(JsonObject, item.proposed_json) for item in ledger.list_proposed_changes()
        }


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


def _add_wiki_results(
    results: list[JsonObject], plan: CandidateWikiPlan, archive: LocalArchiveStore
) -> None:
    rendered = MarkdownCandidateWikiRenderer().render(plan)
    build_id = rendered.manifest.build_id
    audit = archive.read_candidate_wiki_audit_bundle(build_id)
    audit_by_id = {item.record_id: item for item in audit.audit_catalog.records}
    evidence_by_number = {item.citation_number: item for item in plan.citation_registry.citations}
    actor_pages = [
        page
        for page in plan.pages
        if page.page_kind == "actor" and page.display_label in {"Amodei", "Dario Amodei"}
    ]
    for result in results:
        event_id = result.get("event_record_id")
        presentations = [
            presentation
            for page in actor_pages
            for presentation in page.presentations
            if isinstance(presentation, WikiEventPresentation) and presentation.event_id == event_id
        ]
        source_text = _normalize(str(result["source_text"]))
        source_visible = any(
            _normalize(evidence_by_number[number].exact_text) == source_text
            for presentation in presentations
            for number in presentation.citation_numbers
        )
        result["wiki_match"] = len(presentations) == 1 and source_visible
        presentation = presentations[0] if len(presentations) == 1 else None
        audit_ids: set[str] = (
            {presentation.event_id, *presentation.assertion_ids}
            if presentation is not None
            else set()
        )
        result["audit_match"] = bool(audit_ids) and audit_ids.issubset(audit_by_id)
        result["wiki_pages"] = [page.relative_path for page in actor_pages]
        result["first_failed_stage"] = first_failed_event_stage(result)


def _findings(
    *,
    configured: PipelineConfig,
    report: JsonObject,
    manifest: JsonObject,
    first_counts: JsonObject,
    second_counts: JsonObject,
    origins: list[str],
    gold_results: list[JsonObject],
    amodei_results: list[JsonObject],
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
    required_gold = [item for item in gold_results if item["expected_disposition"] == "proposed"]
    if not all(bool(item["observed"]) for item in required_gold):
        findings.append(
            {
                "code": "reviewed_event_not_reproduced",
                "missing": [item for item in required_gold if not item["observed"]],
            }
        )
    findings.extend(final_gold_findings(gold_results))
    findings.extend(required_event_findings(amodei_results))
    return findings


def _task_allocation_findings(
    evaluations: tuple[TaskAllocationCatalogEvaluation, ...],
    comparison: TaskAllocationBaselineComparison,
) -> list[JsonObject]:
    findings: list[JsonObject] = []
    if sum(item.item_count for item in evaluations) != 40:
        findings.append(
            {
                "code": "task_allocation_gold_incomplete",
                "actual": sum(item.item_count for item in evaluations),
            }
        )
    wrong_frames = [
        result.item_id
        for evaluation in evaluations
        for result in evaluation.items
        if task_allocation_item_has_wrong_forced_frame(result)
    ]
    if wrong_frames:
        findings.append(
            {
                "code": "task_allocation_wrong_forced_frame",
                "item_ids": wrong_frames,
            }
        )
    for catalog in comparison.catalogs:
        if catalog.regressed_item_ids:
            findings.append(
                {
                    "code": "task_allocation_baseline_regressed",
                    "catalog_id": catalog.catalog_id,
                    "item_ids": list(catalog.regressed_item_ids),
                }
            )
        if not catalog.newly_complete_item_ids:
            findings.append(
                {
                    "code": "task_allocation_no_newly_complete_item",
                    "catalog_id": catalog.catalog_id,
                }
            )
    development = next(
        (item for item in evaluations if item.catalog_role == "development"),
        None,
    )
    if development is None:
        findings.append({"code": "task_allocation_development_evaluation_missing"})
    else:
        gold = load_task_allocation_gold(TASK_ALLOCATION_AMODEI_GOLD)
        assert gold.baseline_partition is not None
        by_id = {item.item_id: item for item in development.items}
        regressions = [
            item_id
            for item_id in gold.baseline_partition.previously_demonstrated_item_ids
            if item_id not in by_id or not by_id[item_id].passed
        ]
        if regressions:
            findings.append(
                {
                    "code": "task_allocation_demonstrated_behavior_regressed",
                    "item_ids": regressions,
                }
            )
    return findings


def _task_allocation_run_cost(
    counts: JsonObject,
    model_performance: JsonObject,
) -> TaskAllocationRunCost:
    task_types_value = model_performance.get("by_task_type")
    task_types = cast(list[object], task_types_value) if isinstance(task_types_value, list) else []
    elapsed_total = 0
    for value in task_types:
        if not isinstance(value, dict):
            raise ValueError("Model performance task type must be an object.")
        elapsed = cast(dict[str, object], value).get("elapsed_milliseconds")
        if not isinstance(elapsed, dict):
            raise ValueError("Model performance elapsed time must be an object.")
        total = cast(dict[str, object], elapsed).get("total")
        if type(total) is not int:
            raise ValueError("Model performance elapsed total must be an integer.")
        elapsed_total += total
    return TaskAllocationRunCost(
        extraction_task_count=_required_count(counts, "extraction_tasks"),
        model_run_count=_required_count(counts, "model_runs"),
        proposed_change_count=_required_count(counts, "proposed_changes"),
        total_model_elapsed_milliseconds=elapsed_total,
    )


def _required_count(counts: JsonObject, name: str) -> int:
    value = counts.get(name)
    if type(value) is not int:
        raise ValueError(f"Ledger count {name!r} must be an integer.")
    return value


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


def _normalize(value: str) -> str:
    return " ".join(value.split())


def _trigger_retains_gold(expected: str, actual: str) -> bool:
    """Recognize a reviewed trigger retained inside one exact source-literal expansion."""
    return actual == expected or actual.startswith(f"{expected} ")


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
