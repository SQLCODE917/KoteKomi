#!/usr/bin/env python3
"""Compare HP-8 model compaction against exact baseline evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from verify_hp8_document_orchestration import model_evidence

type JsonObject = dict[str, Any]
type Adjudication = tuple[str, str]

STAGES = {
    "mention": ("hp1_mentions", "mention_interpretation"),
    "support": ("hp6_event_semantics", "hybrid_semantic_source_support"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-state-root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-state-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()

    baseline = _read(args.baseline)
    candidate = _read(args.candidate)
    baseline_executions = _executions(baseline, args.baseline_state_root)
    candidate_executions = _executions(candidate, args.candidate_state_root)
    comparison = _compare(
        stage=args.stage,
        baseline=baseline,
        candidate=candidate,
        baseline_executions=baseline_executions,
        candidate_executions=candidate_executions,
        adjudications=_adjudications(args.adjudications, args.stage),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_canonical_json(comparison) + "\n", encoding="utf-8")
    args.review.parent.mkdir(parents=True, exist_ok=True)
    args.review.write_text(_review_markdown(comparison), encoding="utf-8")
    print(json.dumps(comparison["summary"], sort_keys=True))
    return 0 if cast(JsonObject, comparison["summary"])["passed"] else 1


def _executions(report: JsonObject, state_root: Path) -> list[JsonObject]:
    retained = report.get("model_executions")
    if isinstance(retained, list):
        return cast(list[JsonObject], retained)
    _, executions = model_evidence(state_root / "kotekomi.db", state_root / "archive")
    return executions


def _compare(
    *,
    stage: str,
    baseline: JsonObject,
    candidate: JsonObject,
    baseline_executions: list[JsonObject],
    candidate_executions: list[JsonObject],
    adjudications: dict[tuple[int, str], Adjudication] | None = None,
) -> JsonObject:
    stage_output, trace_stage = STAGES[stage]
    baseline_by_ordinal = {
        int(item["ordinal"]): item for item in cast(list[JsonObject], baseline["paragraphs"])
    }
    candidate_by_ordinal = {
        int(item["ordinal"]): item for item in cast(list[JsonObject], candidate["paragraphs"])
    }
    if set(baseline_by_ordinal) != set(candidate_by_ordinal):
        raise ValueError("HP-8 comparison requires identical paragraph ordinals.")
    baseline_runs = {str(item["model_run_id"]): item for item in baseline_executions}
    candidate_runs = {str(item["model_run_id"]): item for item in candidate_executions}
    paragraphs: list[JsonObject] = []
    faster = 0
    matched = 0
    semantic_changes = 0
    used_adjudications: set[tuple[int, str]] = set()
    for ordinal in sorted(baseline_by_ordinal):
        before = baseline_by_ordinal[ordinal]
        after = candidate_by_ordinal[ordinal]
        if before["authoritative_text"] != after["authoritative_text"]:
            raise ValueError("HP-8 comparison found changed authoritative paragraph text.")
        before_output = cast(JsonObject, before["stage_outputs"]).get(stage_output)
        after_output = cast(JsonObject, after["stage_outputs"]).get(stage_output)
        before_signature = _stage_signature(stage, cast(JsonObject | None, before_output))
        after_signature = _stage_signature(stage, cast(JsonObject | None, after_output))
        before_ids = _trace_model_run_ids(cast(JsonObject | None, before_output), trace_stage)
        after_ids = _trace_model_run_ids(cast(JsonObject | None, after_output), trace_stage)
        before_elapsed = _elapsed(before_ids, baseline_runs)
        after_elapsed = _elapsed(after_ids, candidate_runs)
        if before_ids and after_ids:
            matched += 1
            faster += after_elapsed < before_elapsed
        changed = before_signature != after_signature
        semantic_changes += changed
        source_text_sha256 = hashlib.sha256(str(after["authoritative_text"]).encode()).hexdigest()
        assessment = "equivalent"
        rationale = "The source-grounded semantic output is unchanged."
        if changed:
            key = (ordinal, source_text_sha256)
            decision = (adjudications or {}).get(key)
            if decision is None:
                assessment = "inconclusive"
                rationale = "A reviewer has not adjudicated this semantic difference."
            else:
                assessment, rationale = decision
                used_adjudications.add(key)
        paragraphs.append(
            {
                "ordinal": ordinal,
                "paragraph_node_id": cast(JsonObject, after["paragraph_work"])["paragraph_node_id"],
                "authoritative_text": after["authoritative_text"],
                "source_text_sha256": source_text_sha256,
                "assessment": assessment,
                "assessment_rationale": rationale,
                "baseline": {
                    "semantic_output": before_signature,
                    "elapsed_milliseconds": before_elapsed,
                    "model_executions": [baseline_runs[item] for item in before_ids],
                },
                "candidate": {
                    "semantic_output": after_signature,
                    "elapsed_milliseconds": after_elapsed,
                    "model_executions": [candidate_runs[item] for item in after_ids],
                },
            }
        )
    unused_adjudications = set(adjudications or {}) - used_adjudications
    if unused_adjudications:
        raise ValueError("HP-8 adjudications contain unknown or unchanged paragraph decisions.")
    baseline_ids = {
        item
        for paragraph in baseline_by_ordinal.values()
        for item in _trace_model_run_ids(
            cast(JsonObject | None, cast(JsonObject, paragraph["stage_outputs"]).get(stage_output)),
            trace_stage,
        )
    }
    candidate_ids = {
        item
        for paragraph in candidate_by_ordinal.values()
        for item in _trace_model_run_ids(
            cast(JsonObject | None, cast(JsonObject, paragraph["stage_outputs"]).get(stage_output)),
            trace_stage,
        )
    }
    baseline_elapsed = _elapsed(sorted(baseline_ids), baseline_runs)
    candidate_elapsed = _elapsed(sorted(candidate_ids), candidate_runs)
    faster_fraction = faster / matched if matched else 0.0
    integrity_passed = _integrity_passed(candidate)
    gold_passed = _gold_passed(candidate)
    performance_passed = (
        len(candidate_ids) < len(baseline_ids) and candidate_elapsed < baseline_elapsed
    )
    assessment_counts = {
        value: sum(item["assessment"] == value for item in paragraphs)
        for value in ("equivalent", "improvement", "regression", "inconclusive")
    }
    quality_passed = (
        assessment_counts["regression"] == 0
        and assessment_counts["inconclusive"] == 0
        and integrity_passed
        and gold_passed
    )
    return {
        "schema_version": "hp8_model_compaction_comparison_v1",
        "stage": stage,
        "baseline_source_sha256": baseline["source_sha256"],
        "candidate_source_sha256": candidate["source_sha256"],
        "performance": {
            "baseline_run_count": len(baseline_ids),
            "candidate_run_count": len(candidate_ids),
            "baseline_elapsed_milliseconds": baseline_elapsed,
            "candidate_elapsed_milliseconds": candidate_elapsed,
            "elapsed_delta_milliseconds": candidate_elapsed - baseline_elapsed,
            "matched_context_count": matched,
            "faster_context_count": faster,
            "faster_context_fraction": faster_fraction,
        },
        "baseline_summary": baseline["summary"],
        "candidate_summary": candidate["summary"],
        "paragraphs": paragraphs,
        "summary": {
            "passed": quality_passed and performance_passed,
            "quality_passed": quality_passed,
            "performance_passed": performance_passed,
            "integrity_passed": integrity_passed,
            "gold_passed": gold_passed,
            "semantic_change_count": semantic_changes,
            "assessment_counts": assessment_counts,
        },
    }


def _stage_signature(stage: str, output: JsonObject | None) -> JsonObject | None:
    if output is None:
        return None
    if stage == "mention":
        candidate_by_id = {
            str(item["id"]): item for item in cast(list[JsonObject], output["candidates"])
        }
        source_sha_by_id = {
            str(item["source_segment_id"]): str(item["source_text_sha256"])
            for item in candidate_by_id.values()
        }
        interpretations = [
            {
                "candidate": {
                    "source_text_sha256": candidate_by_id[str(item["candidate_id"])][
                        "source_text_sha256"
                    ],
                    "start": candidate_by_id[str(item["candidate_id"])]["start"],
                    "end": candidate_by_id[str(item["candidate_id"])]["end"],
                    "text": candidate_by_id[str(item["candidate_id"])]["text"],
                },
                "referentiality": item["referentiality"],
                "contextual_kind": item["contextual_kind"],
                "discourse_role": item["discourse_role"],
                "support_source_text_sha256": source_sha_by_id[str(item["support_segment_id"])],
            }
            for item in cast(list[JsonObject], output["interpretations"])
        ]
        interpreted_ids = {
            str(item["candidate_id"]) for item in cast(list[JsonObject], output["interpretations"])
        }
        missing_candidates = [
            {
                "source_text_sha256": item["source_text_sha256"],
                "start": item["start"],
                "end": item["end"],
                "text": item["text"],
            }
            for candidate_id, item in candidate_by_id.items()
            if candidate_id not in interpreted_ids
        ]
        return {
            "terminal_status": output["terminal_status"],
            "interpretations": sorted(interpretations, key=_canonical_json),
            "missing_candidates": sorted(missing_candidates, key=_canonical_json),
        }
    traces = [
        item
        for item in cast(list[JsonObject], output["traces"])
        if item["stage_id"] == "hybrid_semantic_source_support"
    ]
    return {
        "terminal_status": output["terminal_status"],
        "judgments": sorted(
            (
                {
                    "evidence_target": _evidence_target_signature(
                        cast(JsonObject, cast(JsonObject, item["input"])["evidence_target"])
                    ),
                    "semantic_statement": _semantic_statement_signature(
                        cast(JsonObject, cast(JsonObject, item["input"])["semantic_statement"])
                    ),
                    "support_judgment": _support_judgment_signature(
                        cast(JsonObject, item["output"]).get("support_judgment")
                    ),
                    "model_run_status": cast(JsonObject, item["output"])["model_run_status"],
                }
                for item in traces
            ),
            key=_canonical_json,
        ),
    }


def _evidence_target_signature(target: JsonObject) -> JsonObject:
    return {
        key: target.get(key)
        for key in (
            "dom_selector",
            "end_char",
            "exact_text",
            "normalization_policy",
            "prefix_text",
            "start_char",
            "suffix_text",
            "table_selector",
            "text_view_digest",
        )
    }


def _semantic_statement_signature(statement: JsonObject) -> JsonObject:
    return {key: statement[key] for key in ("governed_definition", "kind", "text")}


def _support_judgment_signature(value: object) -> JsonObject | None:
    if value is None:
        return None
    judgment = cast(JsonObject, value)
    return {key: judgment[key] for key in ("outcome", "reason")}


def _trace_model_run_ids(output: JsonObject | None, stage_id: str) -> list[str]:
    if output is None:
        return []
    return sorted(
        {
            str(record_id)
            for trace in cast(list[JsonObject], output["traces"])
            if trace["stage_id"] == stage_id
            for record_id in cast(list[str], trace["execution_record_ids"])
            if str(record_id).startswith("mrn_")
        }
    )


def _elapsed(run_ids: list[str], executions: dict[str, JsonObject]) -> int:
    return sum(
        int(cast(JsonObject, executions[item]["execution_diagnostics"])["elapsed_milliseconds"])
        for item in run_ids
    )


def _integrity_passed(report: JsonObject) -> bool:
    counts = cast(JsonObject, report["first_ledger_counts"])
    return (
        all(
            int(counts[field]) == 0
            for field in (
                "accepted_actors",
                "accepted_organizations",
                "accepted_events",
                "accepted_assertions",
            )
        )
        and int(cast(JsonObject, report["summary"])["replay_model_calls"]) == 0
    )


def _gold_passed(report: JsonObject) -> bool:
    summary = cast(JsonObject, report["summary"])
    return (
        bool(summary["passed"])
        and summary["approved_gold_events_observed"] == summary["approved_gold_events_expected"]
        and summary["known_false_events_observed"] == summary["known_false_events_expected"]
    )


def _review_markdown(comparison: JsonObject) -> str:
    performance = cast(JsonObject, comparison["performance"])
    summary = cast(JsonObject, comparison["summary"])
    faster_contexts = (
        f"{performance['faster_context_count']}/{performance['matched_context_count']}"
    )
    lines = [
        f"# HP-8 {comparison['stage']} compaction review",
        "",
        f"- Overall result: `{summary['passed']}`",
        f"- Quality result: `{summary['quality_passed']}`",
        f"- Performance result: `{summary['performance_passed']}`",
        f"- Baseline calls: `{performance['baseline_run_count']}`",
        f"- Candidate calls: `{performance['candidate_run_count']}`",
        f"- Baseline elapsed milliseconds: `{performance['baseline_elapsed_milliseconds']}`",
        f"- Candidate elapsed milliseconds: `{performance['candidate_elapsed_milliseconds']}`",
        f"- Faster matched contexts: `{faster_contexts}`",
        f"- Semantic changes: `{summary['semantic_change_count']}`",
        "",
    ]
    for paragraph in cast(list[JsonObject], comparison["paragraphs"]):
        if paragraph["assessment"] == "equivalent":
            continue
        lines.extend(
            (
                f"## Paragraph {paragraph['ordinal']}",
                "",
                str(paragraph["authoritative_text"]),
                "",
                f"Assessment: `{paragraph['assessment']}`",
                "",
                f"Rationale: {paragraph['assessment_rationale']}",
                "",
                "Baseline semantic output:",
                "",
                "```json",
                json.dumps(cast(JsonObject, paragraph["baseline"])["semantic_output"], indent=2),
                "```",
                "",
                "Candidate semantic output:",
                "",
                "```json",
                json.dumps(cast(JsonObject, paragraph["candidate"])["semantic_output"], indent=2),
                "```",
                "",
            )
        )
    return "\n".join(lines)


def _read(path: Path) -> JsonObject:
    return cast(JsonObject, json.loads(path.read_text(encoding="utf-8")))


def _adjudications(
    path: Path | None,
    stage: str,
) -> dict[tuple[int, str], Adjudication]:
    if path is None:
        return {}
    payload = _read(path)
    if set(payload) != {"schema_version", "stage", "decisions"}:
        raise ValueError("HP-8 adjudication fields are invalid.")
    if payload["schema_version"] != "hp8_compaction_adjudications_v1":
        raise ValueError("HP-8 adjudication schema version is invalid.")
    if payload["stage"] != stage:
        raise ValueError("HP-8 adjudication stage does not match the comparison stage.")
    decisions_value = payload["decisions"]
    if not isinstance(decisions_value, list):
        raise ValueError("HP-8 adjudication decisions must be a list.")
    decisions = cast(list[object], decisions_value)
    result: dict[tuple[int, str], Adjudication] = {}
    for raw_item in decisions:
        if not isinstance(raw_item, dict):
            raise ValueError("HP-8 adjudication decision fields are invalid.")
        item = cast(JsonObject, raw_item)
        if set(item) != {
            "ordinal",
            "source_text_sha256",
            "assessment",
            "rationale",
        }:
            raise ValueError("HP-8 adjudication decision fields are invalid.")
        ordinal = item["ordinal"]
        digest = item["source_text_sha256"]
        assessment = item["assessment"]
        rationale = item["rationale"]
        if (
            not isinstance(ordinal, int)
            or isinstance(ordinal, bool)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or assessment not in {"equivalent", "improvement", "regression"}
            or not isinstance(rationale, str)
            or not rationale.strip()
            or rationale != rationale.strip()
        ):
            raise ValueError("HP-8 adjudication decision value is invalid.")
        key = (ordinal, digest)
        if key in result:
            raise ValueError("HP-8 adjudication repeats a paragraph decision.")
        result[key] = (assessment, rationale)
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
