"""Build and score ORG-R2 evidence over immutable ORG-R1 candidates."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from kotekomi_application.organization_mention_boundary_reconciliation import (
    canonical_boundary_reconciliation_json,
    reconcile_organization_mention_boundaries,
)
from kotekomi_application.organization_mention_qualification import (
    MentionCandidate,
    MentionProposalObservation,
)
from kotekomi_application.organization_semantic_qualification import (
    GoldOrganizationSpan,
    OrganizationQualificationEligibility,
    OrganizationQualificationJudgment,
    classify_qualification_candidate,
    qualification_candidates_from_reconciliation,
)

REPETITIONS = 3
QUALIFICATION_CATALOG_SCHEMA_VERSION = "organization_qualification_catalog_v1"
QUALIFICATION_EXECUTION_SCHEMA_VERSION = "organization_qualification_execution_v1"


def build_qualification_catalog(
    boundary_evaluation: dict[str, Any],
    *,
    phase: str,
    boundary_evaluation_sha256: str,
) -> dict[str, Any]:
    """Compile one repetition-independent ORG-R2 catalog from complete ORG-R1 evidence."""
    if phase not in {"development", "held_out"}:
        raise ValueError("Qualification phase must be development or held_out.")
    _require_sha256(boundary_evaluation_sha256, "boundary evaluation")
    if boundary_evaluation.get("status") != "completed":
        raise ValueError("Qualification catalog requires completed ORG-R1 evidence.")
    if boundary_evaluation.get("policy_id") != "organization_boundary_reconciliation_v1":
        raise ValueError("Qualification catalog requires the pinned ORG-R1 policy.")
    if boundary_evaluation.get("phase") != phase:
        raise ValueError("Qualification phase does not match ORG-R1 evidence.")
    runs = cast(list[dict[str, Any]], boundary_evaluation.get("runs", []))
    if [run.get("repetition") for run in runs] != [1, 2, 3]:
        raise ValueError("Qualification catalog requires three ordered ORG-R1 repetitions.")
    compiled_runs = tuple(_compile_run(run) for run in runs)
    first = compiled_runs[0]
    first_payload = _catalog_comparison_payload(first)
    for repetition, compiled in enumerate(compiled_runs[1:], start=2):
        if _catalog_comparison_payload(compiled) != first_payload:
            raise ValueError(
                f"ORG-R1 repetition {repetition} changed qualification candidate boundaries."
            )
    sources = tuple(first[0])
    candidates = tuple(first[1])
    return {
        "schema_version": QUALIFICATION_CATALOG_SCHEMA_VERSION,
        "phase": phase,
        "org_r1_policy_id": "organization_boundary_reconciliation_v1",
        "org_r1_boundary_evaluation_sha256": boundary_evaluation_sha256,
        "org_r1_proposal_report_sha256": boundary_evaluation["proposal_report_sha256"],
        "gold_catalog_sha256": boundary_evaluation["catalog_sha256"],
        "repetitions_verified": REPETITIONS,
        "source_count": len(sources),
        "candidate_count": len(candidates),
        "sources": list(sources),
        "candidates": list(candidates),
    }


def score_qualification_executions(
    catalog: dict[str, Any],
    executions: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Score semantic labels while excluding non-exact Gold boundary cases."""
    candidate_by_id = {
        str(item["candidate"]["id"]): item
        for item in cast(list[dict[str, Any]], catalog["candidates"])
    }
    source_by_id = {
        str(item["id"]): item for item in cast(list[dict[str, Any]], catalog["sources"])
    }
    counts = Counter[str]()
    seen: set[tuple[str, int, str]] = set()
    wrong: list[dict[str, Any]] = []
    executions_by_candidate: dict[tuple[str, str], list[dict[str, Any]]] = {}
    elapsed_milliseconds: list[int] = []
    for execution in executions:
        if execution.get("schema_version") != QUALIFICATION_EXECUTION_SCHEMA_VERSION:
            raise ValueError("Qualification execution schema is unsupported.")
        candidate_id = str(execution["candidate_id"])
        producer_id = str(execution["producer_id"])
        repetition = int(execution["repetition"])
        key = (producer_id, repetition, candidate_id)
        if key in seen:
            raise ValueError("Qualification executions repeat a producer/repetition/candidate key.")
        seen.add(key)
        if candidate_id not in candidate_by_id:
            raise ValueError("Qualification execution references an unknown candidate.")
        catalog_item = candidate_by_id[candidate_id]
        source = source_by_id[str(catalog_item["source_record_id"])]
        classification = cast(dict[str, Any], catalog_item["gold_classification"])
        status = str(execution["execution_status"])
        eligibility = str(classification["eligibility"])
        counts["execution_count"] += 1
        counts[f"execution_status:{status}"] += 1
        counts[f"eligibility:{eligibility}"] += 1
        executions_by_candidate.setdefault((producer_id, candidate_id), []).append(execution)
        elapsed = _execution_elapsed_milliseconds(execution)
        if elapsed is not None:
            elapsed_milliseconds.append(elapsed)
        if status in {"completed", "invalid_output"}:
            counts["runtime_available_count"] += 1
        if eligibility == OrganizationQualificationEligibility.BOUNDARY_CASE.value:
            counts["boundary_case_count"] += 1
            wrong.append(
                _review_record(
                    catalog_item,
                    source,
                    execution,
                    "boundary_case" if status == "completed" else "execution_failure",
                )
            )
            continue
        counts["eligible_attempt_count"] += 1
        if status != "completed":
            wrong.append(_review_record(catalog_item, source, execution, "execution_failure"))
            continue
        counts["completed_eligible_count"] += 1
        judgment = str(execution["judgment"])
        counts[f"judgment:{judgment}"] += 1
        expected = str(classification["expected_judgment"])
        if judgment != OrganizationQualificationJudgment.AMBIGUOUS.value:
            counts["decisive_count"] += 1
        if judgment == expected:
            counts["correct_count"] += 1
        else:
            counts["wrong_count"] += 1
            wrong.append(
                _review_record(
                    catalog_item,
                    source,
                    execution,
                    "wrong_semantic_judgment",
                )
            )
        if judgment == OrganizationQualificationJudgment.AMBIGUOUS.value:
            counts["ambiguous_eligible_count"] += 1
        elif expected == OrganizationQualificationJudgment.ORGANIZATION.value:
            counts[
                "true_positive_count"
                if judgment == OrganizationQualificationJudgment.ORGANIZATION.value
                else "false_negative_count"
            ] += 1
        else:
            counts[
                "true_negative_count"
                if judgment == OrganizationQualificationJudgment.NOT_ORGANIZATION.value
                else "false_positive_count"
            ] += 1
    for candidate_executions in executions_by_candidate.values():
        counts["stability_candidate_count"] += 1
        completed_labels = {
            str(execution["judgment"])
            for execution in candidate_executions
            if execution["execution_status"] == "completed"
        }
        if (
            len(candidate_executions) == REPETITIONS
            and len(completed_labels) == 1
            and all(
                execution["execution_status"] == "completed" for execution in candidate_executions
            )
        ):
            counts["stable_candidate_count"] += 1
    completed_eligible = counts["completed_eligible_count"]
    decisive = counts["decisive_count"]
    true_positive = counts["true_positive_count"]
    false_positive = counts["false_positive_count"]
    true_negative = counts["true_negative_count"]
    false_negative = counts["false_negative_count"]
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "schema_version": "organization_qualification_metrics_v1",
        "counts": dict(sorted(counts.items())),
        "organization_precision": precision,
        "organization_recall": recall,
        "organization_f1": _f1(precision, recall),
        "specificity": _ratio(true_negative, true_negative + false_positive),
        "exact_accuracy": _ratio(counts["correct_count"], completed_eligible),
        "decisive_accuracy": _ratio(counts["correct_count"], decisive),
        "coverage": _ratio(decisive, completed_eligible),
        "ambiguity_rate": _ratio(counts["ambiguous_eligible_count"], completed_eligible),
        "invalid_output_rate": _ratio(
            counts["execution_status:invalid_output"], counts["execution_count"]
        ),
        "runtime_availability": _ratio(
            counts["runtime_available_count"], counts["execution_count"]
        ),
        "valid_output_rate": _ratio(
            counts["execution_status:completed"], counts["execution_count"]
        ),
        "exact_label_stability": _ratio(
            counts["stable_candidate_count"], counts["stability_candidate_count"]
        ),
        "latency_milliseconds": _latency_summary(elapsed_milliseconds),
        "review_records": wrong,
    }


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def write_canonical_jsonl(path: Path, records: tuple[dict[str, Any], ...]) -> None:
    """Write ordered, identity-distinct records as canonical UTF-8 JSON Lines."""
    ids = tuple(str(record["id"]) for record in records)
    if tuple(sorted(set(ids))) != ids:
        raise ValueError("Qualification JSONL record IDs must be ordered and distinct.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(record) + "\n" for record in records), encoding="utf-8")


def append_execution_record(path: Path, record: dict[str, Any]) -> bool:
    """Append one missing execution or accept an exact idempotent replay."""
    if record.get("schema_version") != QUALIFICATION_EXECUTION_SCHEMA_VERSION:
        raise ValueError("Qualification execution schema is unsupported.")
    record_id = str(record.get("id", ""))
    if not record_id:
        raise ValueError("Qualification execution requires an identity.")
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            payload = cast(dict[str, Any], json.loads(line))
            existing[str(payload["id"])] = canonical_json(payload)
    serialized = canonical_json(record)
    if record_id in existing:
        if existing[record_id] != serialized:
            raise ValueError("Qualification execution conflicts with retained evidence.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")
    return True


def seal_bundle(
    output_dir: Path,
    *,
    phase: str,
    expected_files: tuple[str, ...],
) -> dict[str, Any]:
    """Hash every complete bundle file and refuse a held-out reseal."""
    manifest_path = output_dir / "manifest.json"
    if phase == "held_out" and manifest_path.exists():
        raise FileExistsError("Completed held-out qualification evidence is sealed.")
    files: list[dict[str, Any]] = []
    for relative in expected_files:
        path = output_dir / relative
        if not path.is_file():
            raise ValueError(f"Qualification bundle is missing {relative}.")
        payload = path.read_bytes()
        files.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "record_count": len(path.read_text(encoding="utf-8").splitlines())
                if path.suffix == ".jsonl"
                else 1,
            }
        )
    manifest = {
        "schema_version": "organization_qualification_bundle_manifest_v1",
        "phase": phase,
        "status": "complete",
        "files": files,
    }
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest


def _compile_run(
    run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    candidates_out: list[dict[str, Any]] = []
    for segment in cast(list[dict[str, Any]], run.get("segments", [])):
        source_text = str(segment["source_text"])
        source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        if source_digest != segment.get("source_text_sha256"):
            raise ValueError("ORG-R1 Source text digest drifted.")
        source_id = _id(
            "qfs",
            str(segment["fixture_path"]),
            str(segment["paragraph_node_id"]),
            str(segment["source_segment_label"]),
            source_digest,
        )
        source_record = {
            "id": source_id,
            "fixture_path": segment["fixture_path"],
            "paragraph_node_id": segment["paragraph_node_id"],
            "source_segment_id": segment["source_segment_id"],
            "source_segment_label": segment["source_segment_label"],
            "source_text": source_text,
            "source_text_sha256": source_digest,
            "gold_mentions": segment["gold_mentions"],
        }
        sources.append(source_record)
        mention_candidates = _mention_candidates(segment, source_text)
        reconciliation = reconcile_organization_mention_boundaries(
            source_text=source_text,
            source_segment_id=str(segment["source_segment_id"]),
            candidates=mention_candidates,
        )
        if canonical_json(
            json.loads(canonical_boundary_reconciliation_json(reconciliation))
        ) != canonical_json(segment["reconciliation"]):
            raise ValueError(
                "ORG-R1 reconciliation payload drifted during qualification compilation."
            )
        qualification_candidates = qualification_candidates_from_reconciliation(
            source_text=source_text,
            candidates=mention_candidates,
            reconciliation=reconciliation,
        )
        gold = tuple(
            GoldOrganizationSpan(str(item["text"]), int(item["start"]), int(item["end"]))
            for item in cast(list[dict[str, Any]], segment["gold_mentions"])
        )
        decision_by_id = {decision.id: decision for decision in reconciliation.decisions}
        for candidate in qualification_candidates:
            classification = classify_qualification_candidate(candidate, gold)
            candidates_out.append(
                {
                    "id": candidate.id,
                    "source_record_id": source_id,
                    "candidate": asdict(candidate),
                    "boundary_decision": asdict(decision_by_id[candidate.boundary_decision_id]),
                    "gold_classification": asdict(classification),
                }
            )
    sources.sort(key=lambda item: str(item["id"]))
    candidates_out.sort(key=lambda item: str(item["id"]))
    return sources, candidates_out


def _mention_candidates(
    segment: dict[str, Any],
    source_text: str,
) -> tuple[MentionCandidate, ...]:
    values: list[MentionCandidate] = []
    for value in cast(list[dict[str, Any]], segment["fused_candidates"]):
        observations = tuple(
            MentionProposalObservation(
                proposer_id=str(item["proposer_id"]),
                text=str(item["text"]),
                start=int(item["start"]),
                end=int(item["end"]),
                score=float(item["score"]) if item.get("score") is not None else None,
                model_run_id=str(item["model_run_id"])
                if item.get("model_run_id") is not None
                else None,
            )
            for item in cast(list[dict[str, Any]], value["observations"])
        )
        candidate = MentionCandidate(
            id=str(value["id"]),
            source_segment_id=str(value["source_segment_id"]),
            source_text_digest=str(value["source_text_digest"]),
            text=str(value["text"]),
            start=int(value["start"]),
            end=int(value["end"]),
            observations=observations,
        )
        if source_text[candidate.start : candidate.end] != candidate.text:
            raise ValueError("ORG-R1 candidate no longer matches Source characters.")
        values.append(candidate)
    return tuple(values)


def _catalog_comparison_payload(
    compiled: tuple[list[dict[str, Any]], list[dict[str, Any]]],
) -> str:
    sources, candidates = compiled
    normalized_sources = [
        {key: value for key, value in source.items() if key != "source_segment_id"}
        for source in sources
    ]
    return canonical_json({"sources": normalized_sources, "candidates": candidates})


def _review_record(
    catalog_item: dict[str, Any],
    source: dict[str, Any],
    execution: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "candidate_id": execution["candidate_id"],
        "producer_id": execution["producer_id"],
        "repetition": execution["repetition"],
        "reason": reason,
        "source_record_id": catalog_item["source_record_id"],
        "source": source,
        "candidate": catalog_item["candidate"],
        "gold_classification": catalog_item["gold_classification"],
        "execution_id": execution["id"],
        "producer_input_reference": {
            "record_id": execution.get("input_record_id"),
            "path": "qwen-inputs.jsonl"
            if execution["producer_id"] == "qwen"
            else "refined-batches.jsonl",
        },
        "producer_output_reference": {
            "execution_id": execution["id"],
            "field": "output",
        },
        "actual": {
            "execution_status": execution["execution_status"],
            "judgment": execution.get("judgment"),
        },
        "root_cause_hypotheses": ["unresolved"],
        "semantic_case_tags": ["other"],
    }


def _execution_elapsed_milliseconds(execution: dict[str, Any]) -> int | None:
    retained_value = execution.get("elapsed_milliseconds")
    if type(retained_value) is int and retained_value >= 0:
        return retained_value
    producer_id = execution.get("producer_id")
    if producer_id == "qwen":
        diagnostics = (
            cast(dict[str, Any], execution.get("output", {}))
            .get("model_run", {})
            .get("execution_diagnostics", {})
        )
        value = diagnostics.get("elapsed_milliseconds")
    elif producer_id == "refined":
        value = cast(dict[str, Any], execution.get("worker_batch", {})).get("inference_elapsed_ms")
    else:
        return None
    if type(value) is not int or value < 0:
        return None
    return value


def _latency_summary(values: list[int]) -> dict[str, int] | None:
    if not values:
        return None
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "median": _nearest_rank(ordered, 0.5),
        "p95": _nearest_rank(ordered, 0.95),
        "maximum": ordered[-1],
    }


def _nearest_rank(values: list[int], percentile: float) -> int:
    return values[max(0, math.ceil(percentile * len(values)) - 1)]


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 6)


def _require_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"Qualification {label} digest must be SHA-256 hex.")


def _id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"
