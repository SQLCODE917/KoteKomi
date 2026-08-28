"""Assemble the policy-aligned PHP-1 mention and relation baseline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from php1_diagnostic_support import (
    Php1Expectation,
    run_relation_pairs_for_candidate_runs,
)
from php1_relation_benchmark import (
    CompleteRelationSegment,
    load_and_validate_relation_benchmark,
    score_relation_run,
    validate_relation_segment_source,
)
from verify_php1_packet import packet_cases
from verify_php1_span_proposers import CATALOG_PATH as MENTION_CATALOG_PATH
from verify_php1_span_proposers import POLICY_PATH as MENTION_POLICY_PATH
from verify_php1_span_proposers import ROOT
from verify_php1_span_proposers import run as run_span_comparison

RELATION_BENCHMARK_PATH = ROOT / "docs/php1-direct-organization-relation-benchmark-v2.json"
MENTION_PROMPT_PATH = ROOT / "prompts/paragraph_organization_mention_v1.md"
PAIR_PROMPT_PATH = ROOT / "prompts/paragraph_organization_pair_relation_v1.md"


def run_corrected_baseline(
    config_path: Path | None = None,
    *,
    span_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the repaired three-repetition mention and relation benchmark."""
    comparison = span_comparison or run_span_comparison(config_path)
    if comparison["status"] != "completed":
        return comparison
    benchmark = load_and_validate_relation_benchmark(RELATION_BENCHMARK_PATH)
    qwen = _proposer(comparison, "qwen2.5-h2-mention-v1")
    relation_result = run_relation_pairs_for_candidate_runs(
        config_path,
        packet_cases(),
        relation_expectations(benchmark),
        cast(list[dict[str, Any]], qwen["runs"]),
    )
    if relation_result["status"] != "completed":
        return relation_result
    _validate_relation_sources(benchmark, relation_result)
    relation_scores = [
        score_relation_run(
            benchmark,
            run,
            cast(dict[str, list[str]], relation_result["expectation_segment_keys"]),
        )
        for run in cast(list[dict[str, Any]], relation_result["runs"])
    ]
    return {
        "status": "completed",
        "schema_version": "php1_corrected_baseline_v1",
        "input_digests": corrected_baseline_input_digests(),
        "span_comparison": comparison,
        "relation_benchmark_path": str(RELATION_BENCHMARK_PATH.relative_to(ROOT)),
        "relation_benchmark": [_segment_value(item) for item in benchmark],
        "relation_runs": relation_result,
        "relation_scores": relation_scores,
    }


def compact_baseline_summary(result: dict[str, Any], full_report_bytes: bytes) -> dict[str, Any]:
    """Build the repository-sized summary that binds the disposable full report."""
    if result["status"] != "completed":
        raise ValueError("A compact baseline summary requires a completed report.")
    comparison = cast(dict[str, Any], result["span_comparison"])
    proposers = cast(list[dict[str, Any]], comparison["proposers"])
    return {
        "schema_version": "php1_corrected_baseline_summary_v1",
        "status": "completed",
        "full_report_sha256": hashlib.sha256(full_report_bytes).hexdigest(),
        "input_digests": result["input_digests"],
        "source_segment_count": comparison["source_segment_count"],
        "model_eligible_segment_count": sum(
            segment["status"] != "not_applicable_nonlexical"
            for segment in proposers[0]["runs"][0]["segments"]
        ),
        "mention_quality": {
            str(proposer["proposer_id"]): proposer["quality_runs"][0]["micro"]
            for proposer in proposers
        },
        "mention_stability": {
            str(proposer["proposer_id"]): {
                key: value
                for key, value in proposer["stability"].items()
                if key != "unstable_segments"
            }
            for proposer in proposers
        },
        "relation_quality_runs": [
            {
                "repetition": score["repetition"],
                "target_count": score["target_count"],
                "matched_target_count": score["matched_target_count"],
                "missing_target_count": score["missing_target_count"],
                "unexpected_accepted_relation_count": len(score["unexpected_accepted_relations"]),
                "pair_task_count": score["pair_task_count"],
                "all_pair_tasks_terminal": score["all_pair_tasks_terminal"],
            }
            for score in result["relation_scores"]
        ],
        "proposer_identities": {
            str(proposer["proposer_id"]): proposer["identity"] for proposer in proposers
        },
        "proposer_identity_digests": proposer_identity_digests(comparison),
    }


def proposer_identity_digests(comparison: dict[str, Any]) -> dict[str, str]:
    """Digest each complete proposer identity snapshot canonically."""
    return {
        str(proposer["proposer_id"]): hashlib.sha256(
            json.dumps(
                proposer["identity"],
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        for proposer in cast(list[dict[str, Any]], comparison["proposers"])
    }


def relation_expectations(
    benchmark: tuple[CompleteRelationSegment, ...],
) -> tuple[Php1Expectation, ...]:
    return tuple(
        Php1Expectation(
            relation.expectation_id,
            segment.case_ids,
            segment.fixture_path,
            segment.paragraph_anchor,
            segment.source_segment_anchor,
            relation.subject_text,
            relation.object_text,
            relation.relationship_shape,
        )
        for segment in benchmark
        for relation in segment.relations
    )


def _validate_relation_sources(
    benchmark: tuple[CompleteRelationSegment, ...], relation_result: dict[str, Any]
) -> None:
    keys = cast(dict[str, list[str]], relation_result["expectation_segment_keys"])
    first_run = cast(list[dict[str, Any]], relation_result["runs"])[0]
    runtime_segments = {
        (
            str(segment["fixture_path"]),
            str(segment["paragraph_node_id"]),
            str(segment["source_segment_label"]),
        ): segment
        for segment in cast(list[dict[str, Any]], first_run["segments"])
    }
    for segment in benchmark:
        key = tuple(keys[segment.relations[0].expectation_id])
        validate_relation_segment_source(
            segment,
            str(runtime_segments[cast(tuple[str, str, str], key)]["source_copy_text"]),
        )


def _proposer(comparison: dict[str, Any], proposer_id: str) -> dict[str, Any]:
    values = [item for item in comparison["proposers"] if item["proposer_id"] == proposer_id]
    if len(values) != 1:
        raise ValueError("Corrected baseline requires one named proposer result.")
    return cast(dict[str, Any], values[0])


def corrected_baseline_input_digests() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            MENTION_POLICY_PATH,
            MENTION_CATALOG_PATH,
            RELATION_BENCHMARK_PATH,
            MENTION_PROMPT_PATH,
            PAIR_PROMPT_PATH,
        )
    }


def _segment_value(segment: CompleteRelationSegment) -> dict[str, Any]:
    return {
        "case_ids": list(segment.case_ids),
        "fixture_path": segment.fixture_path,
        "paragraph_anchor": segment.paragraph_anchor,
        "source_segment_anchor": segment.source_segment_anchor,
        "relations": [relation.__dict__ for relation in segment.relations],
        "excluded_pair_decisions": list(segment.excluded_pair_decisions),
    }
