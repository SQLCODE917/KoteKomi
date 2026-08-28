"""Exact-span scoring and report assembly for the PHP-1 H2.1 comparison."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, cast

CATALOG_SCHEMA_VERSION = "php1_organization_mention_gold_v1"
REPETITIONS = 3


def source_segment_key(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(value["fixture_path"]),
        str(value["paragraph_node_id"]),
        str(value["source_segment_label"]),
    )


def review_segment_key(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(value["fixture_path"]),
        str(value["source_text_sha256"]),
        str(value["source_segment_label"]),
    )


def catalog_anchor_key(value: dict[str, Any]) -> tuple[str, tuple[str, ...], str]:
    return (
        str(value["fixture_path"]),
        tuple(str(item) for item in value["case_ids"]),
        str(value["source_segment_label"]),
    )


def load_and_validate_catalog(
    path: Path,
    source_result: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Load a complete exact-span catalog and reject source drift."""
    raw_value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_value, dict):
        raise ValueError("H2.1 Mention catalog must be an object.")
    raw = cast(dict[str, object], raw_value)
    if set(raw) != {"schema_version", "annotation_status", "segments"}:
        raise ValueError("H2.1 Mention catalog fields do not match the contract.")
    if raw["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise ValueError("H2.1 Mention catalog schema version does not match the contract.")
    if raw["annotation_status"] != "provisional_agent_authored":
        raise ValueError("H2.1 Mention catalog annotation status does not match the contract.")
    raw_segments = raw["segments"]
    if not isinstance(raw_segments, list):
        raise ValueError("H2.1 Mention catalog segments must be an array.")
    sources = {
        catalog_anchor_key(item): item
        for item in cast(list[dict[str, Any]], source_result.get("segments", []))
    }
    catalog: dict[tuple[str, tuple[str, ...], str], dict[str, Any]] = {}
    for index, raw_segment_value in enumerate(cast(list[object], raw_segments)):
        if not isinstance(raw_segment_value, dict):
            raise ValueError(f"H2.1 Mention catalog segment {index} must be an object.")
        segment = cast(dict[str, Any], raw_segment_value)
        required = {
            "case_ids",
            "fixture_path",
            "fixture_sha256",
            "paragraph_node_id",
            "source_segment_label",
            "source_text_sha256",
            "gold_mentions",
        }
        if set(segment) != required:
            raise ValueError(f"H2.1 Mention catalog segment {index} fields do not match.")
        key = catalog_anchor_key(segment)
        if key in catalog:
            raise ValueError("H2.1 Mention catalog repeats a Source segment.")
        source = sources.get(key)
        if source is None:
            raise ValueError("H2.1 Mention catalog references an unknown Source segment.")
        for field in ("case_ids", "fixture_sha256", "source_text_sha256"):
            if segment[field] != source[field]:
                raise ValueError(f"H2.1 Mention catalog {field} drifted from the Source segment.")
        source_text = str(source["source_text"])
        mentions = segment["gold_mentions"]
        if not isinstance(mentions, list):
            raise ValueError("H2.1 Gold mentions must be an array.")
        seen: set[tuple[int, int]] = set()
        previous: tuple[int, int, str] | None = None
        for mention_value in cast(list[object], mentions):
            if not isinstance(mention_value, dict):
                raise ValueError("H2.1 Gold mention fields do not match the contract.")
            mention = cast(dict[str, Any], mention_value)
            if set(mention) != {
                "text",
                "start",
                "end",
            }:
                raise ValueError("H2.1 Gold mention fields do not match the contract.")
            text = mention["text"]
            start = mention["start"]
            end = mention["end"]
            if not isinstance(text, str) or not text:
                raise ValueError("H2.1 Gold mention text must be non-empty.")
            if type(start) is not int or type(end) is not int or start < 0 or end <= start:
                raise ValueError("H2.1 Gold mention positions are invalid.")
            if end > len(source_text) or source_text[start:end] != text:
                raise ValueError("H2.1 Gold mention does not match the Source segment.")
            identity = (start, end)
            if identity in seen:
                raise ValueError("H2.1 Mention catalog repeats a Gold mention span.")
            seen.add(identity)
            order = (start, end, text)
            if previous is not None and order < previous:
                raise ValueError("H2.1 Gold mentions must use source order.")
            previous = order
        catalog[key] = {
            **segment,
            "catalog_paragraph_node_id": segment["paragraph_node_id"],
            "paragraph_node_id": source["paragraph_node_id"],
        }
    if set(catalog) != set(sources):
        raise ValueError("H2.1 Mention catalog does not cover every unique Source segment.")
    return tuple(catalog[key] for key in sorted(catalog))


def exact_name_occurrences(source_text: str, organization_text: str) -> tuple[dict[str, Any], ...]:
    """Map one distinct Qwen name to every exact non-overlapping source occurrence."""
    if not organization_text:
        raise ValueError("Qwen Organization text must be non-empty.")
    occurrences: list[dict[str, Any]] = []
    cursor = 0
    while True:
        start = source_text.find(organization_text, cursor)
        if start < 0:
            break
        end = start + len(organization_text)
        occurrences.append({"text": organization_text, "start": start, "end": end, "score": None})
        cursor = end
    if not occurrences:
        raise ValueError("Qwen Organization text does not occur in its Source segment.")
    return tuple(occurrences)


def normalize_qwen_segment(value: dict[str, Any]) -> dict[str, Any]:
    source_text = str(value["source_copy_text"])
    proposals: dict[tuple[int, int], dict[str, Any]] = {}
    if value["status"] == "complete":
        for mention in cast(list[dict[str, Any]], value["mention_candidates"]):
            for occurrence in exact_name_occurrences(
                source_text, str(mention["organization_text"])
            ):
                key = (int(occurrence["start"]), int(occurrence["end"]))
                existing = proposals.get(key)
                if existing is not None and existing["text"] != occurrence["text"]:
                    raise ValueError("Qwen names map different text to one Source span.")
                proposals[key] = occurrence
    diagnostics_value = value.get("execution_diagnostics")
    elapsed: int | None = None
    if isinstance(diagnostics_value, dict):
        diagnostics = cast(dict[str, object], diagnostics_value)
        elapsed_value = diagnostics.get("elapsed_milliseconds")
        if type(elapsed_value) is int:
            elapsed = elapsed_value
    return {
        "fixture_path": value["fixture_path"],
        "paragraph_node_id": value["paragraph_node_id"],
        "source_segment_label": value["source_segment_label"],
        "source_text_sha256": value["source_text_sha256"],
        "source_text": source_text,
        "status": value["status"],
        "latency_milliseconds": elapsed,
        "proposals": [proposals[key] for key in sorted(proposals)],
        "model_run_id": value["model_run_id"],
        "context_manifest_id": value["context_manifest_id"],
        "prompt_digest": value["prompt_digest"],
        "raw_output": value["raw_output"],
        "diagnostics": value["diagnostics"],
    }


def score_segment(
    gold_mentions: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    gold = {(int(item["start"]), int(item["end"]), str(item["text"])) for item in gold_mentions}
    predicted = {(int(item["start"]), int(item["end"]), str(item["text"])) for item in proposals}
    true_positives = gold & predicted
    false_positives = predicted - gold
    false_negatives = gold - predicted
    boundaries = Counter[str]()
    for start, end, text in sorted(gold):
        if (start, end, text) in predicted:
            boundaries["exact"] += 1
            continue
        overlaps = sorted(
            (
                (
                    max(0, min(end, candidate_end) - max(start, candidate_start)),
                    candidate_start,
                    candidate_end,
                )
                for candidate_start, candidate_end, _ in predicted
                if candidate_start < end and candidate_end > start
            ),
            reverse=True,
        )
        if not overlaps:
            boundaries["missing"] += 1
            continue
        _, candidate_start, candidate_end = overlaps[0]
        if candidate_start >= start and candidate_end <= end:
            boundaries["truncated"] += 1
        elif candidate_start <= start and candidate_end >= end:
            boundaries["expanded"] += 1
        else:
            boundaries["crossing"] += 1
    return {
        "true_positive_count": len(true_positives),
        "false_positive_count": len(false_positives),
        "false_negative_count": len(false_negatives),
        "boundary_counts": {
            label: boundaries[label]
            for label in ("exact", "truncated", "expanded", "crossing", "missing")
        },
        "false_positives": [_span_value(item) for item in sorted(false_positives)],
        "false_negatives": [_span_value(item) for item in sorted(false_negatives)],
    }


def _span_value(value: tuple[int, int, str]) -> dict[str, Any]:
    return {"start": value[0], "end": value[1], "text": value[2]}


def _quality_counts(values: list[dict[str, Any]]) -> dict[str, Any]:
    true_positives = sum(int(item["true_positive_count"]) for item in values)
    false_positives = sum(int(item["false_positive_count"]) for item in values)
    false_negatives = sum(int(item["false_negative_count"]) for item in values)
    precision = _ratio(true_positives, true_positives + false_positives)
    recall = _ratio(true_positives, true_positives + false_negatives)
    f1 = _ratio(2 * precision * recall, precision + recall)
    boundaries = Counter[str]()
    for item in values:
        boundaries.update(cast(dict[str, int], item["boundary_counts"]))
    return {
        "true_positive_count": true_positives,
        "false_positive_count": false_positives,
        "false_negative_count": false_negatives,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "boundary_counts": {
            label: boundaries[label]
            for label in ("exact", "truncated", "expanded", "crossing", "missing")
        },
    }


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 1.0


def score_run(
    catalog: tuple[dict[str, Any], ...],
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_by_key = {source_segment_key(item): item for item in catalog}
    segment_by_key = {source_segment_key(item): item for item in segments}
    if set(gold_by_key) != set(segment_by_key):
        raise ValueError("H2.1 proposer run does not cover the Mention catalog.")
    scored: list[dict[str, Any]] = []
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors: list[dict[str, Any]] = []
    for key in sorted(gold_by_key):
        gold = gold_by_key[key]
        result = segment_by_key[key]
        score = score_segment(gold["gold_mentions"], result["proposals"])
        scored.append(score)
        by_document[key[0]].append(score)
        if score["false_positives"] or score["false_negatives"]:
            errors.append(
                {
                    "fixture_path": key[0],
                    "paragraph_node_id": key[1],
                    "source_segment_label": key[2],
                    "case_ids": gold["case_ids"],
                    "source_text": result["source_text"],
                    "false_positives": score["false_positives"],
                    "false_negatives": score["false_negatives"],
                }
            )
    return {
        "micro": _quality_counts(scored),
        "by_document": {
            path: _quality_counts(values) for path, values in sorted(by_document.items())
        },
        "errors": errors,
    }


def latency_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    values = sorted(
        int(segment["latency_milliseconds"])
        for run in runs
        for segment in cast(list[dict[str, Any]], run["segments"])
        if type(segment.get("latency_milliseconds")) is int
    )
    return {
        "measured_segment_count": len(values),
        "p50_milliseconds": _percentile(values, 0.50),
        "p95_milliseconds": _percentile(values, 0.95),
        "total_milliseconds": sum(values),
    }


def _percentile(values: list[int], quantile: float) -> int | None:
    if not values:
        return None
    position = max(0, math.ceil(quantile * len(values)) - 1)
    return values[position]


def stability_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if len(runs) != REPETITIONS:
        raise ValueError("H2.1 stability requires exactly three proposer runs.")
    run_maps = [
        {
            source_segment_key(segment): {
                (int(item["start"]), int(item["end"]), str(item["text"]))
                for item in cast(list[dict[str, Any]], segment["proposals"])
            }
            for segment in cast(list[dict[str, Any]], run["segments"])
        }
        for run in runs
    ]
    keys = set(run_maps[0])
    if any(set(run_map) != keys for run_map in run_maps[1:]):
        raise ValueError("H2.1 stability runs do not cover identical Source segments.")
    stable = 0
    jaccards: list[float] = []
    unstable: list[dict[str, Any]] = []
    for key in sorted(keys):
        span_sets = [run_map[key] for run_map in run_maps]
        if span_sets[0] == span_sets[1] == span_sets[2]:
            stable += 1
        else:
            unstable.append(
                {
                    "fixture_path": key[0],
                    "paragraph_node_id": key[1],
                    "source_segment_label": key[2],
                    "run_proposals": [
                        [_span_value(item) for item in sorted(span_set)] for span_set in span_sets
                    ],
                }
            )
        for first, second in combinations(span_sets, 2):
            union = first | second
            jaccards.append(len(first & second) / len(union) if union else 1.0)
    return {
        "segment_count": len(keys),
        "exact_set_stable_segment_count": stable,
        "exact_set_stable_segment_rate": round(_ratio(stable, len(keys)), 6),
        "mean_pairwise_jaccard": round(statistics.fmean(jaccards), 6),
        "unstable_segments": unstable,
    }


def proposer_report(
    proposer_id: str,
    identity: dict[str, Any],
    catalog: tuple[dict[str, Any], ...],
    runs: list[dict[str, Any]],
    *,
    load_elapsed_milliseconds: int | None,
) -> dict[str, Any]:
    quality = [
        {"repetition": int(run["repetition"]), **score_run(catalog, run["segments"])}
        for run in runs
    ]
    return {
        "proposer_id": proposer_id,
        "identity": identity,
        "load_elapsed_milliseconds": load_elapsed_milliseconds,
        "quality_runs": quality,
        "latency": latency_summary(runs),
        "stability": stability_summary(runs),
        "runs": runs,
    }


def render_review_report(
    result: dict[str, Any],
    catalog: tuple[dict[str, Any], ...],
) -> str:
    lines = [
        "PHP-1 H2.1 specialized Organization span proposer comparison",
        f"Status: {result['status']}",
        f"Unique Source segments: {result['source_segment_count']}",
        "",
    ]
    for proposer in cast(list[dict[str, Any]], result["proposers"]):
        first_quality = proposer["quality_runs"][0]["micro"]
        stability = {
            key: value for key, value in proposer["stability"].items() if key != "unstable_segments"
        }
        lines.extend(
            (
                f"Proposer: {proposer['proposer_id']}",
                f"Identity: {json.dumps(proposer['identity'], sort_keys=True)}",
                f"Run 1 precision: {first_quality['precision']}",
                f"Run 1 recall: {first_quality['recall']}",
                f"Run 1 F1: {first_quality['f1']}",
                f"Boundary counts: {json.dumps(first_quality['boundary_counts'], sort_keys=True)}",
                f"Latency: {json.dumps(proposer['latency'], sort_keys=True)}",
                f"Stability: {json.dumps(stability, sort_keys=True)}",
                "",
            )
        )

    catalog_by_key = {review_segment_key(item): item for item in catalog}
    run_maps: dict[str, list[dict[tuple[str, str, str], dict[str, Any]]]] = {}
    for proposer in cast(list[dict[str, Any]], result["proposers"]):
        run_maps[str(proposer["proposer_id"])] = [
            {
                review_segment_key(segment): segment
                for segment in cast(list[dict[str, Any]], run["segments"])
            }
            for run in cast(list[dict[str, Any]], proposer["runs"])
        ]
    for proposer_id, proposer_runs in run_maps.items():
        if len(proposer_runs) != REPETITIONS or any(
            set(run_map) != set(catalog_by_key) for run_map in proposer_runs
        ):
            raise ValueError(
                f"H2.1 review data for {proposer_id} does not cover the Mention catalog."
            )

    lines.extend(("Source segment review", ""))
    for key in sorted(catalog_by_key):
        gold = catalog_by_key[key]
        first_proposer_id = str(result["proposers"][0]["proposer_id"])
        source = run_maps[first_proposer_id][0][key]
        lines.extend(
            (
                f"Cases: {', '.join(gold['case_ids'])}",
                f"Fixture: {gold['fixture_path']}",
                f"Source segment: {gold['source_segment_label']}",
                f"Catalog DocumentNode: {gold['catalog_paragraph_node_id']}",
                f"Current DocumentNode: {gold['paragraph_node_id']}",
                f"Source: {source['source_text']}",
                "Gold mentions: "
                + json.dumps(gold["gold_mentions"], ensure_ascii=False, sort_keys=True),
            )
        )
        for proposer in cast(list[dict[str, Any]], result["proposers"]):
            proposer_id = str(proposer["proposer_id"])
            for repetition, run_map in enumerate(run_maps[proposer_id], start=1):
                lines.append(
                    f"{proposer_id} repetition {repetition}: "
                    + json.dumps(run_map[key]["proposals"], ensure_ascii=False, sort_keys=True)
                )
        lines.append("")

    lines.extend(("Scored errors", ""))
    for proposer in cast(list[dict[str, Any]], result["proposers"]):
        for quality in proposer["quality_runs"]:
            for error in quality["errors"]:
                lines.extend(
                    (
                        f"Repetition {quality['repetition']} error",
                        f"Cases: {', '.join(error['case_ids'])}",
                        f"Source: {error['source_text']}",
                        "False positives: "
                        + json.dumps(error["false_positives"], ensure_ascii=False, sort_keys=True),
                        "False negatives: "
                        + json.dumps(error["false_negatives"], ensure_ascii=False, sort_keys=True),
                        "",
                    )
                )
    return "\n".join(lines).rstrip() + "\n"
