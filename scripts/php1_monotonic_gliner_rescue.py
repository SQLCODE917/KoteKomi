"""Assemble and score the PHP-1 H2.3 monotonic GLiNER rescue experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    MentionProposalObservation,
    fuse_monotonic_organization_candidates,
)
from php1_corrected_baseline import (
    corrected_baseline_input_digests,
    proposer_identity_digests,
    relation_expectations,
)
from php1_diagnostic_support import run_rescue_pairs_for_fusion_runs
from php1_relation_benchmark import load_and_validate_relation_benchmark, score_relation_run
from php1_span_proposer_evaluation import score_run
from verify_php1_packet import packet_cases
from verify_php1_span_proposers import ROOT

RELATION_BENCHMARK_PATH = ROOT / "docs/php1-direct-organization-relation-benchmark-v2.json"


def validate_baseline_binding(
    baseline: dict[str, Any], summary: dict[str, Any], baseline_bytes: bytes
) -> None:
    """Reject a baseline whose report or repository inputs drifted."""
    if baseline.get("status") != "completed" or baseline.get("schema_version") != (
        "php1_corrected_baseline_v1"
    ):
        raise ValueError("H2.3 requires one completed corrected baseline.")
    if summary.get("full_report_sha256") != hashlib.sha256(baseline_bytes).hexdigest():
        raise ValueError("H2.3 baseline summary does not bind the full report.")
    if baseline.get("input_digests") != corrected_baseline_input_digests():
        raise ValueError("H2.3 baseline repository inputs drifted.")
    comparison = cast(dict[str, Any], baseline["span_comparison"])
    if summary.get("proposer_identity_digests") != proposer_identity_digests(comparison):
        raise ValueError("H2.3 baseline model identities drifted.")


def build_monotonic_fusion_runs(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    """Retain Qwen spans and add source-valid GLiNER spans for every repetition."""
    comparison = cast(dict[str, Any], baseline["span_comparison"])
    catalog_segments = {
        _review_key(item): item for item in cast(list[dict[str, Any]], comparison["catalog"])
    }
    qwen = _proposer(comparison, "qwen2.5-h2-mention-v1")
    gliner = _proposer(comparison, "gliner-medium-v2.1")
    qwen_runs = cast(list[dict[str, Any]], qwen["runs"])
    gliner_runs = cast(list[dict[str, Any]], gliner["runs"])
    if len(qwen_runs) != 3 or len(gliner_runs) != 3:
        raise ValueError("H2.3 requires three baseline proposer runs.")
    results: list[dict[str, Any]] = []
    for qwen_run, gliner_run in zip(qwen_runs, gliner_runs, strict=True):
        if qwen_run["repetition"] != gliner_run["repetition"]:
            raise ValueError("H2.3 proposer repetition identities do not match.")
        gliner_segments = {
            _review_key(item): item for item in cast(list[dict[str, Any]], gliner_run["segments"])
        }
        segments: list[dict[str, Any]] = []
        for qwen_segment in cast(list[dict[str, Any]], qwen_run["segments"]):
            key = _review_key(qwen_segment)
            gliner_segment = gliner_segments.get(key)
            if gliner_segment is None:
                raise ValueError("H2.3 GLiNER run misses a Qwen Source segment.")
            source_text = str(qwen_segment["source_text"])
            if str(gliner_segment["source_text"]) != source_text:
                raise ValueError("H2.3 proposer Source segment text does not match.")
            if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != key[1]:
                raise ValueError("H2.3 proposer Source segment digest does not match.")
            gold_segment = catalog_segments.get(key)
            if gold_segment is None:
                raise ValueError("H2.3 Mention Gold misses a proposer Source segment.")
            baseline_observations = tuple(
                _observation("qwen2.5-h2-mention-v1", item)
                for item in cast(list[dict[str, Any]], qwen_segment["proposals"])
            )
            rescue_observations = tuple(
                _observation("gliner-medium-v2.1", item)
                for item in cast(list[dict[str, Any]], gliner_segment["proposals"])
            )
            source_segment_bytes = "\x1f".join(key).encode("utf-8")
            source_segment_id = hashlib.sha256(source_segment_bytes).hexdigest()[:24]
            fusion = fuse_monotonic_organization_candidates(
                source_text=source_text,
                source_segment_id=source_segment_id,
                baseline_observations=baseline_observations,
                rescue_observations=rescue_observations,
            )
            segments.append(
                {
                    "fixture_path": qwen_segment["fixture_path"],
                    "paragraph_node_id": qwen_segment["paragraph_node_id"],
                    "source_segment_label": qwen_segment["source_segment_label"],
                    "source_text_sha256": qwen_segment["source_text_sha256"],
                    "source_text": source_text,
                    "source_segment_id": source_segment_id,
                    "gold_mentions": gold_segment["gold_mentions"],
                    "baseline_input": _proposer_input_trace("qwen2.5-h2-mention-v1", qwen_segment),
                    "rescue_input": _proposer_input_trace("gliner-medium-v2.1", gliner_segment),
                    "status": "fused_candidates",
                    "proposals": [
                        {
                            "text": candidate.text,
                            "start": candidate.start,
                            "end": candidate.end,
                            "score": None,
                        }
                        for candidate in fusion.mention_candidates
                    ],
                    "mention_candidates": [
                        candidate.__dict__ for candidate in fusion.mention_candidates
                    ],
                    "candidate_groups": [group.__dict__ for group in fusion.candidate_groups],
                    "candidate_pairs": [pair.__dict__ for pair in fusion.candidate_pairs],
                    "pair_exclusions": [exclusion.__dict__ for exclusion in fusion.pair_exclusions],
                    "new_candidate_pairs": [
                        pair.__dict__
                        for pair in fusion.candidate_pairs
                        if pair.requires_new_judgment
                    ],
                }
            )
        if set(gliner_segments) != {_review_key(item) for item in qwen_run["segments"]}:
            raise ValueError("H2.3 proposer runs cover different Source segments.")
        if set(catalog_segments) != {_review_key(item) for item in qwen_run["segments"]}:
            raise ValueError("H2.3 proposer run does not cover the Mention Gold.")
        results.append({"repetition": int(qwen_run["repetition"]), "segments": segments})
    return results


def run_monotonic_rescue(
    baseline: dict[str, Any],
    baseline_full_report_sha256: str,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Run only the relation judgments introduced by monotonic rescue spans."""
    if len(baseline_full_report_sha256) != 64:
        raise ValueError("H2.3 requires the corrected baseline report digest.")
    benchmark = load_and_validate_relation_benchmark(RELATION_BENCHMARK_PATH)
    fusion_runs = build_monotonic_fusion_runs(baseline)
    baseline_relation = cast(dict[str, Any], baseline["relation_runs"])
    complete_fusion_runs = _complete_subset_fusion_runs(fusion_runs, baseline_relation)
    rescue_pair_runs = run_rescue_pairs_for_fusion_runs(
        config_path,
        packet_cases(),
        relation_expectations(benchmark),
        complete_fusion_runs,
    )
    if rescue_pair_runs["status"] != "completed":
        return rescue_pair_runs
    combined_relation_runs = _combined_relation_runs(baseline_relation, rescue_pair_runs)
    expectation_keys = cast(dict[str, list[str]], baseline_relation["expectation_segment_keys"])
    relation_scores = [
        score_relation_run(benchmark, run, expectation_keys) for run in combined_relation_runs
    ]
    catalog = tuple(cast(list[dict[str, Any]], baseline["span_comparison"]["catalog"]))
    mention_scores = [score_run(catalog, run["segments"]) for run in fusion_runs]
    baseline_qwen = _proposer(
        cast(dict[str, Any], baseline["span_comparison"]), "qwen2.5-h2-mention-v1"
    )
    gates = comparison_gates(
        baseline_qwen,
        cast(list[dict[str, Any]], baseline["relation_scores"]),
        fusion_runs,
        mention_scores,
        relation_scores,
    )
    return {
        "status": "completed",
        "schema_version": "php1_monotonic_gliner_rescue_v1",
        "baseline_full_report_sha256": baseline_full_report_sha256,
        "baseline_input_digests": baseline["input_digests"],
        "proposer_identities": {
            str(proposer["proposer_id"]): proposer["identity"]
            for proposer in baseline["span_comparison"]["proposers"]
        },
        "selection_status": ("selected_for_followup" if all(gates.values()) else "not_selected"),
        "gates": gates,
        "fusion_runs": fusion_runs,
        "mention_scores": mention_scores,
        "rescue_pair_runs": rescue_pair_runs,
        "combined_relation_runs": combined_relation_runs,
        "relation_scores": relation_scores,
    }


def comparison_gates(
    baseline_qwen: dict[str, Any],
    baseline_relation_scores: list[dict[str, Any]],
    fusion_runs: list[dict[str, Any]],
    fusion_mention_scores: list[dict[str, Any]],
    fusion_relation_scores: list[dict[str, Any]],
) -> dict[str, bool]:
    """Evaluate every H2.3 no-regression and end-to-end gain gate."""
    baseline_quality = cast(list[dict[str, Any]], baseline_qwen["quality_runs"])
    baseline_runs = cast(list[dict[str, Any]], baseline_qwen["runs"])
    return {
        "baseline_mentions_retained": all(
            _baseline_mentions_retained(baseline_run, fusion_run)
            for baseline_run, fusion_run in zip(baseline_runs, fusion_runs, strict=True)
        ),
        "mention_recall_improved": all(
            float(fusion["micro"]["recall"]) > float(baseline["micro"]["recall"])
            for baseline, fusion in zip(baseline_quality, fusion_mention_scores, strict=True)
        ),
        "baseline_targets_retained": all(
            _matched_ids(fusion).issuperset(_matched_ids(baseline))
            for baseline, fusion in zip(
                baseline_relation_scores, fusion_relation_scores, strict=True
            )
        ),
        "additional_relation_target_matched": all(
            int(fusion["matched_target_count"]) > int(baseline["matched_target_count"])
            for baseline, fusion in zip(
                baseline_relation_scores, fusion_relation_scores, strict=True
            )
        ),
        "no_unexpected_accepted_relation": all(
            not score["unexpected_accepted_relations"] for score in fusion_relation_scores
        ),
        "all_pair_tasks_terminal": all(
            bool(score["all_pair_tasks_terminal"]) for score in fusion_relation_scores
        ),
    }


def compact_rescue_summary(result: dict[str, Any], full_report_bytes: bytes) -> dict[str, Any]:
    if result["status"] != "completed":
        raise ValueError("A compact rescue summary requires a completed report.")
    return {
        "schema_version": "php1_monotonic_gliner_rescue_summary_v1",
        "status": result["status"],
        "selection_status": result["selection_status"],
        "full_report_sha256": hashlib.sha256(full_report_bytes).hexdigest(),
        "baseline_full_report_sha256": result["baseline_full_report_sha256"],
        "baseline_input_digests": result["baseline_input_digests"],
        "proposer_identities": result["proposer_identities"],
        "gates": result["gates"],
        "quality_runs": [
            {
                "repetition": relation["repetition"],
                "mention": mention["micro"],
                "matched_relation_target_count": relation["matched_target_count"],
                "unexpected_accepted_relation_count": len(
                    relation["unexpected_accepted_relations"]
                ),
                "pair_task_count": relation["pair_task_count"],
                "mention_candidate_count": sum(
                    len(segment["mention_candidates"]) for segment in fusion["segments"]
                ),
                "candidate_group_count": sum(
                    len(segment["candidate_groups"]) for segment in fusion["segments"]
                ),
                "candidate_pair_count": sum(
                    len(segment["candidate_pairs"]) for segment in fusion["segments"]
                ),
                "pair_exclusion_count": sum(
                    len(segment["pair_exclusions"]) for segment in fusion["segments"]
                ),
            }
            for mention, relation, fusion in zip(
                result["mention_scores"],
                result["relation_scores"],
                result["fusion_runs"],
                strict=True,
            )
        ],
    }


def render_rescue_review_report(result: dict[str, Any]) -> str:
    """Render the bounded evidence needed to review the H2.3 decision."""
    if result["status"] != "completed":
        raise ValueError("An H2.3 review report requires a completed result.")
    lines = [
        "PHP-1 H2.3 Monotonic GLiNER Rescue",
        f"Selection: {result['selection_status']}",
        f"Baseline report: {result['baseline_full_report_sha256']}",
        "Proposer identities: "
        + json.dumps(result["proposer_identities"], ensure_ascii=False, sort_keys=True),
        "",
        "Gates",
    ]
    lines.extend(
        f"{name}: {'pass' if passed else 'fail'}"
        for name, passed in sorted(cast(dict[str, bool], result["gates"]).items())
    )
    for mention, relation in zip(
        cast(list[dict[str, Any]], result["mention_scores"]),
        cast(list[dict[str, Any]], result["relation_scores"]),
        strict=True,
    ):
        micro = cast(dict[str, Any], mention["micro"])
        lines.extend(
            [
                "",
                f"Repetition {relation['repetition']}",
                f"Mention precision: {micro['precision']}",
                f"Mention recall: {micro['recall']}",
                f"Mention F1: {micro['f1']}",
                (
                    "Matched relation targets: "
                    f"{relation['matched_target_count']}/{relation['target_count']}"
                ),
                (
                    "Unexpected accepted relations: "
                    f"{len(relation['unexpected_accepted_relations'])}"
                ),
            ]
        )
        for unexpected in cast(list[dict[str, Any]], relation["unexpected_accepted_relations"]):
            lines.append(
                "unexpected: "
                f"{unexpected['subject_text']} | {unexpected['relation_text']} | "
                f"{unexpected['object_text']} @ {unexpected['fixture_path']} "
                f"{unexpected['source_segment_label']}"
            )
    for fusion_run in cast(list[dict[str, Any]], result["fusion_runs"]):
        lines.extend(
            (
                (
                    f"Repetition {fusion_run['repetition']} candidate groups: "
                    f"{sum(len(segment['candidate_groups']) for segment in fusion_run['segments'])}"
                ),
                (
                    f"Repetition {fusion_run['repetition']} candidate pairs: "
                    f"{sum(len(segment['candidate_pairs']) for segment in fusion_run['segments'])}"
                ),
                (
                    f"Repetition {fusion_run['repetition']} pair exclusions: "
                    f"{sum(len(segment['pair_exclusions']) for segment in fusion_run['segments'])}"
                ),
            )
        )
    lines.extend(("", "Candidate fusion traces"))
    for fusion_run in cast(list[dict[str, Any]], result["fusion_runs"]):
        lines.extend(("", f"Repetition {fusion_run['repetition']}"))
        for segment in cast(list[dict[str, Any]], fusion_run["segments"]):
            lines.extend(
                (
                    "",
                    (
                        f"Segment: {segment['fixture_path']} | "
                        f"{segment['paragraph_node_id']} | {segment['source_segment_label']}"
                    ),
                    f"Source SHA-256: {segment['source_text_sha256']}",
                    f"Source input: {segment['source_text']}",
                    "Gold output: "
                    + json.dumps(segment["gold_mentions"], ensure_ascii=False, sort_keys=True),
                    "Qwen input/output: "
                    + json.dumps(segment["baseline_input"], ensure_ascii=False, sort_keys=True),
                    "GLiNER input/output: "
                    + json.dumps(segment["rescue_input"], ensure_ascii=False, sort_keys=True),
                    "Fused candidate output: "
                    + json.dumps(segment["mention_candidates"], ensure_ascii=False, sort_keys=True),
                    "Candidate groups: "
                    + json.dumps(segment["candidate_groups"], ensure_ascii=False, sort_keys=True),
                    "Candidate pairs: "
                    + json.dumps(segment["candidate_pairs"], ensure_ascii=False, sort_keys=True),
                    "Pair exclusions: "
                    + json.dumps(segment["pair_exclusions"], ensure_ascii=False, sort_keys=True),
                )
            )
    lines.extend(("", "Relation judgment traces"))
    for relation_run in cast(list[dict[str, Any]], result["combined_relation_runs"]):
        lines.extend(("", f"Repetition {relation_run['repetition']}"))
        for segment in cast(list[dict[str, Any]], relation_run["segments"]):
            lines.extend(
                (
                    "",
                    (
                        f"Segment: {segment['fixture_path']} | "
                        f"{segment['paragraph_node_id']} | {segment['source_segment_label']}"
                    ),
                    f"Source input: {segment['source_copy_text']}",
                )
            )
            for pair_result in cast(list[dict[str, Any]], segment["pair_results"]):
                lines.append(
                    "Pair input/output: "
                    + json.dumps(pair_result, ensure_ascii=False, sort_keys=True)
                )
    return "\n".join(lines) + "\n"


def _complete_subset_fusion_runs(
    fusion_runs: list[dict[str, Any]], baseline_relation: dict[str, Any]
) -> list[dict[str, Any]]:
    relation_runs = cast(list[dict[str, Any]], baseline_relation["runs"])
    results: list[dict[str, Any]] = []
    for fusion_run, relation_run in zip(fusion_runs, relation_runs, strict=True):
        fusion_by_key = {
            _review_key(item): item for item in cast(list[dict[str, Any]], fusion_run["segments"])
        }
        segments: list[dict[str, Any]] = []
        for relation_segment in cast(list[dict[str, Any]], relation_run["segments"]):
            key = _review_key(relation_segment)
            if key not in fusion_by_key:
                raise ValueError("H2.3 fusion misses a complete relation Source segment.")
            segments.append(fusion_by_key[key])
        results.append({"repetition": fusion_run["repetition"], "segments": segments})
    return results


def _combined_relation_runs(
    baseline_relation: dict[str, Any], rescue_pair_runs: dict[str, Any]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for baseline_run, rescue_run in zip(
        baseline_relation["runs"], rescue_pair_runs["runs"], strict=True
    ):
        rescue_by_key = {
            _review_key(item): item for item in cast(list[dict[str, Any]], rescue_run["segments"])
        }
        segments: list[dict[str, Any]] = []
        for baseline_segment in cast(list[dict[str, Any]], baseline_run["segments"]):
            rescue = rescue_by_key[_review_key(baseline_segment)]
            segments.append(
                {
                    **baseline_segment,
                    "pair_results": list(baseline_segment["pair_results"])
                    + list(rescue["pair_results"]),
                }
            )
        results.append({"repetition": baseline_run["repetition"], "segments": segments})
    return results


def _baseline_mentions_retained(baseline_run: dict[str, Any], fusion_run: dict[str, Any]) -> bool:
    fusion = {
        _review_key(segment): {
            (int(item["start"]), int(item["end"]), str(item["text"]))
            for item in segment["proposals"]
        }
        for segment in fusion_run["segments"]
    }
    return all(
        {
            (int(item["start"]), int(item["end"]), str(item["text"]))
            for item in segment["proposals"]
        }.issubset(fusion[_review_key(segment)])
        for segment in baseline_run["segments"]
    )


def _matched_ids(score: dict[str, Any]) -> set[str]:
    return {
        str(item["expectation_id"])
        for item in score["target_results"]
        if item["target_status"] == "matched"
    }


def _observation(proposer_id: str, value: dict[str, Any]) -> MentionProposalObservation:
    return MentionProposalObservation(
        proposer_id,
        str(value["text"]),
        int(value["start"]),
        int(value["end"]),
        float(value["score"]) if value.get("score") is not None else None,
        str(value["model_run_id"]) if value.get("model_run_id") is not None else None,
    )


def _proposer_input_trace(proposer_id: str, value: dict[str, Any]) -> dict[str, Any]:
    """Retain one source-bound proposer input and its complete observable output."""
    return {
        "proposer_id": proposer_id,
        "source_text": value["source_text"],
        "source_text_sha256": value["source_text_sha256"],
        "status": value["status"],
        "model_eligibility": value["model_eligibility"],
        "model_run_id": value.get("model_run_id"),
        "prompt_digest": value.get("prompt_digest"),
        "raw_output": value.get("raw_output"),
        "proposals": value["proposals"],
    }


def _review_key(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(value["fixture_path"]),
        str(value["source_text_sha256"]),
        str(value["source_segment_label"]),
    )


def _proposer(comparison: dict[str, Any], proposer_id: str) -> dict[str, Any]:
    values = [item for item in comparison["proposers"] if item["proposer_id"] == proposer_id]
    if len(values) != 1:
        raise ValueError("H2.3 requires one named proposer result.")
    return cast(dict[str, Any], values[0])
