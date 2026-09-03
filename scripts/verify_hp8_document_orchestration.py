#!/usr/bin/env python3
"""Run and replay HP-8 over the locked Anthropic/DoD document."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    HybridStageId,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_pipeline_policy_manifest_from_bytes,
)
from kotekomi_domain import IngestionChangeSetOrigin, ReviewStatus
from kotekomi_pipelines.cli import ingest_user_file
from kotekomi_pipelines.config import PipelineConfig, load_config

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json"
HP7_GOLD = ROOT / "docs/hp7-proposal-admission-gold-v1.json"
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
        if root.exists():
            raise ValueError(f"HP-8 state root already exists: {root}")
        root.mkdir(parents=True)
    try:
        ledger_path = root / "kotekomi.db"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        config_path.write_text(
            _isolated_config(configured, ledger_path, archive_path),
            encoding="utf-8",
        )
        first = _ingest(config_path, source, args.url)
        first_counts = _ledger_counts(ledger_path)
        report, manifest, paragraphs = _document_evidence(ledger_path, archive_path)
        second = _ingest(config_path, source, args.url)
        second_counts = _ledger_counts(ledger_path)
        origins = _change_set_origins(ledger_path)
        gold_results = _gold_event_results(paragraphs)
        findings = _findings(
            configured=configured,
            report=report,
            manifest=manifest,
            first_counts=first_counts,
            second_counts=second_counts,
            origins=origins,
            gold_results=gold_results,
            paragraphs=paragraphs,
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
            "first_public_output": first,
            "replay_public_output": second,
            "first_ledger_counts": first_counts,
            "replay_ledger_counts": second_counts,
            "ingestion_change_set_origins": origins,
            "findings": findings,
            "summary": {
                "passed": not findings,
                "required_paragraphs": report["required_paragraph_count"],
                "complete_paragraphs": report["complete_paragraph_count"],
                "gap_paragraphs": report["gap_paragraph_count"],
                "proposed_changes": len(report["proposed_change_ids"]),
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
                "known_false_events_observed": sum(item["observed"] for item in rejected_gold),
                "known_false_events_expected": len(rejected_gold),
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
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = ingest_user_file(
            config_path=config_path,
            source_file_path=source,
            source_url=url,
        )
    result = {
        "exit_code": exit_code,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    }
    if exit_code != 0:
        raise ValueError(f"HP-8 public ingest failed: {result}")
    return result


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
        HybridStageId.HP4_EVENT_FRAMES: archive.read_hybrid_event_frame_preview,
        HybridStageId.HP5_ATOMIC_CLAIMS: archive.read_hybrid_atomic_claim_preview,
        HybridStageId.HP6_EVENT_SEMANTICS: archive.read_hybrid_event_semantics_preview,
        HybridStageId.HP7_PROPOSAL_PLAN: archive.read_hybrid_proposal_plan,
    }
    return cast(JsonObject, json.loads(readers[stage_id](output_id)))


def _gold_event_results(paragraphs: list[JsonObject]) -> list[JsonObject]:
    observed: dict[str, list[JsonObject]] = {}
    for paragraph in paragraphs:
        stage_outputs = cast(JsonObject, paragraph["stage_outputs"])
        hp4 = cast(JsonObject | None, stage_outputs.get(HybridStageId.HP4_EVENT_FRAMES.value))
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
        matches = [
            match
            for match in observed.get(_normalize(str(item["source_text"])), [])
            if _trigger_retains_gold(expected_trigger, _normalize(str(match["trigger_text"])))
        ]
        match = matches[0] if len(matches) == 1 else None
        results.append(
            {
                "case_id": item["case_id"],
                "source_text": item["source_text"],
                "trigger": item["trigger"],
                "expected_disposition": item["expected_disposition"],
                "review_outcome": item["review_outcome"],
                "observed": len(matches) == 1,
                "trigger_match": (
                    "exact"
                    if match is not None
                    and _normalize(str(match["trigger_text"])) == expected_trigger
                    else "expanded_literal"
                    if match is not None
                    else None
                ),
                "lineage_complete": (
                    match is not None
                    and match["event_semantic_id"] is not None
                    and match["admission_decision_id"] is not None
                ),
                "matches": matches,
            }
        )
    return results


def _findings(
    *,
    configured: PipelineConfig,
    report: JsonObject,
    manifest: JsonObject,
    first_counts: JsonObject,
    second_counts: JsonObject,
    origins: list[str],
    gold_results: list[JsonObject],
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
    if first_counts["proposed_changes"] != first_counts["pending_proposed_changes"] or first_counts[
        "proposed_changes"
    ] != len(cast(list[str], report["proposed_change_ids"])):
        findings.append(
            {
                "code": "pending_proposal_set_mismatch",
                "ledger": first_counts,
                "report_proposed_change_ids": report["proposed_change_ids"],
            }
        )
    if (
        origins.count(IngestionChangeSetOrigin.EXECUTED.value) != 1
        or origins.count(IngestionChangeSetOrigin.REUSED.value) != 1
    ):
        findings.append({"code": "replay_origin_invalid", "actual": origins})
    model = cast(JsonObject, manifest["model_identity"])
    proposer = cast(JsonObject, manifest["mention_proposer_identity"])
    linker = cast(JsonObject, manifest["entity_linker_identity"])
    if model.get("adapter") != "lm_studio" or "qwen2.5" not in str(model.get("name", "")).lower():
        findings.append({"code": "qwen25_runtime_not_pinned", "actual": model})
    if "gliner" not in str(proposer.get("producer_id", "")):
        findings.append({"code": "gliner_not_pinned", "actual": proposer})
    if configured.entity_linking is None or linker.get("configured") is not True:
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
    if not all(bool(item["observed"]) for item in gold_results):
        findings.append(
            {
                "code": "reviewed_event_not_reproduced",
                "missing": [item for item in gold_results if not item["observed"]],
            }
        )
    return findings


def _ledger_counts(ledger_path: Path) -> JsonObject:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        proposals = ledger.list_proposed_changes()
        return {
            "extraction_tasks": len(ledger.list_extraction_tasks()),
            "model_runs": len(ledger.list_model_runs()),
            "proposed_changes": len(proposals),
            "pending_proposed_changes": sum(
                item.review_status is ReviewStatus.PENDING for item in proposals
            ),
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
    ]
    if config.entity_linking is not None:
        linker = config.entity_linking
        lines.extend(
            (
                "",
                "[entity_linking]",
                f"adapter = {_toml(linker.adapter)}",
                f"python_executable = {_toml(linker.python_executable)}",
                f"data_dir = {_toml(linker.data_dir)}",
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
