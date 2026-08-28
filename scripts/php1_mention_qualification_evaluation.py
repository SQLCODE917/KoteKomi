"""Report assembly for PHP-1 H2.2 Organization mention qualification."""

from __future__ import annotations

import json
from typing import Any, cast

from kotekomi_application import MentionProposalObservation, fuse_mention_proposals
from php1_span_proposer_evaluation import REPETITIONS, review_segment_key, score_run

SCHEMA_VERSION = "php1_organization_mention_qualification_v1"
MANDATORY_PAIR_EXPECTATION_IDS = ("php1-target-ad-09-anthropic-palantir",)


def source_segment_identity(value: dict[str, Any]) -> str:
    return "\x1f".join(
        (
            str(value["fixture_path"]),
            str(value["source_text_sha256"]),
            str(value["source_segment_label"]),
        )
    )


def build_fused_candidate_runs(
    comparison: dict[str, Any],
    representations: dict[str, str],
) -> list[dict[str, Any]]:
    """Fuse paired Qwen and GLiNER runs without losing proposer provenance."""
    proposers = {
        str(item["proposer_id"]): item
        for item in cast(list[dict[str, Any]], comparison["proposers"])
    }
    qwen = proposers["qwen2.5-h2-mention-v1"]
    gliner = proposers["gliner-medium-v2.1"]
    qwen_runs = cast(list[dict[str, Any]], qwen["runs"])
    gliner_runs = cast(list[dict[str, Any]], gliner["runs"])
    if len(qwen_runs) != REPETITIONS or len(gliner_runs) != REPETITIONS:
        raise ValueError("H2.2 requires three paired proposer runs.")
    fused_runs: list[dict[str, Any]] = []
    for qwen_run, gliner_run in zip(qwen_runs, gliner_runs, strict=True):
        repetition = int(qwen_run["repetition"])
        if int(gliner_run["repetition"]) != repetition:
            raise ValueError("H2.2 proposer repetitions do not align.")
        qwen_segments = {
            review_segment_key(item): item
            for item in cast(list[dict[str, Any]], qwen_run["segments"])
        }
        gliner_segments = {
            review_segment_key(item): item
            for item in cast(list[dict[str, Any]], gliner_run["segments"])
        }
        if set(qwen_segments) != set(gliner_segments):
            raise ValueError("H2.2 proposer runs do not cover equal Source segments.")
        segments: list[dict[str, Any]] = []
        for key in sorted(qwen_segments):
            qwen_segment = qwen_segments[key]
            gliner_segment = gliner_segments[key]
            source_text = str(qwen_segment["source_text"])
            if source_text != gliner_segment["source_text"]:
                raise ValueError("H2.2 proposers received different source characters.")
            observations = tuple(
                [
                    MentionProposalObservation(
                        "qwen2.5-h2-mention-v1",
                        str(item["text"]),
                        int(item["start"]),
                        int(item["end"]),
                        None,
                        str(qwen_segment["model_run_id"]),
                    )
                    for item in cast(list[dict[str, Any]], qwen_segment["proposals"])
                ]
                + [
                    MentionProposalObservation(
                        "gliner-medium-v2.1",
                        str(item["text"]),
                        int(item["start"]),
                        int(item["end"]),
                        float(item["score"]),
                        None,
                    )
                    for item in cast(list[dict[str, Any]], gliner_segment["proposals"])
                ]
            )
            segment_id = source_segment_identity(qwen_segment)
            candidates = fuse_mention_proposals(source_text, segment_id, observations)
            fixture_path = str(qwen_segment["fixture_path"])
            segments.append(
                {
                    "fixture_path": fixture_path,
                    "representation_id": representations[fixture_path],
                    "paragraph_node_id": qwen_segment["paragraph_node_id"],
                    "source_segment_label": qwen_segment["source_segment_label"],
                    "source_segment_id": segment_id,
                    "source_text_sha256": qwen_segment["source_text_sha256"],
                    "source_text": source_text,
                    "candidates": [_candidate_value(item) for item in candidates],
                }
            )
        fused_runs.append({"repetition": repetition, "segments": segments})
    return fused_runs


def assemble_report(
    comparison: dict[str, Any],
    catalog: tuple[dict[str, Any], ...],
    qualification: dict[str, Any],
) -> dict[str, Any]:
    """Score qualified runs and apply the explicit selection gates."""
    if qualification["status"] != "completed":
        return qualification
    qwen = next(
        item
        for item in cast(list[dict[str, Any]], comparison["proposers"])
        if item["proposer_id"] == "qwen2.5-h2-mention-v1"
    )
    qwen_runs = cast(list[dict[str, Any]], qwen["runs"])
    qualification_runs = cast(list[dict[str, Any]], qualification["runs"])
    if len(qwen_runs) != REPETITIONS or len(qualification_runs) != REPETITIONS:
        raise ValueError("H2.2 report requires three paired qualification runs.")
    quality_runs: list[dict[str, Any]] = []
    selected = True
    for qwen_run, qualified_run in zip(qwen_runs, qualification_runs, strict=True):
        repetition = int(qualified_run["repetition"])
        if int(qwen_run["repetition"]) != repetition:
            raise ValueError("H2.2 qualification repetitions do not align.")
        qwen_score = score_run(catalog, cast(list[dict[str, Any]], qwen_run["segments"]))
        qualified_catalog = _reanchor_catalog(
            catalog,
            cast(list[dict[str, Any]], qualified_run["segments"]),
        )
        qualified_score = score_run(
            qualified_catalog,
            cast(list[dict[str, Any]], qualified_run["segments"]),
        )
        qwen_micro = cast(dict[str, Any], qwen_score["micro"])
        qualified_micro = cast(dict[str, Any], qualified_score["micro"])
        gates = {
            "qwen_true_positives_preserved": _qwen_true_positives_preserved(
                catalog,
                cast(list[dict[str, Any]], qwen_run["segments"]),
                cast(list[dict[str, Any]], qualified_run["segments"]),
            ),
            "precision_not_lower": float(qualified_micro["precision"])
            >= float(qwen_micro["precision"]),
            "recall_higher": float(qualified_micro["recall"]) > float(qwen_micro["recall"]),
            "nist_alias_resolved": _nist_alias_resolved(qualified_run),
            "mandatory_pairs_preserved": _mandatory_pairs_preserved(qualified_run),
        }
        run_selected = all(gates.values())
        selected = selected and run_selected
        quality_runs.append(
            {
                "repetition": repetition,
                "qwen": qwen_score,
                "qualified": qualified_score,
                "gates": gates,
                "selection_status": "selected" if run_selected else "not_selected",
            }
        )
    return {
        "status": "completed",
        "selection_status": "selected" if selected else "not_selected",
        "schema_version": SCHEMA_VERSION,
        "source_segment_count": comparison["source_segment_count"],
        "case_count": comparison["case_count"],
        "repetitions": REPETITIONS,
        "quality_runs": quality_runs,
        "runs": qualification_runs,
    }


def render_review_report(result: dict[str, Any]) -> str:
    lines = [
        "PHP-1 H2.2 Organization mention qualification",
        f"Status: {result['status']}",
        f"Selection: {result.get('selection_status', 'not_evaluated')}",
        "",
    ]
    for quality in cast(list[dict[str, Any]], result.get("quality_runs", [])):
        lines.extend(
            (
                f"Repetition: {quality['repetition']}",
                "Qwen quality: "
                + json.dumps(quality["qwen"]["micro"], ensure_ascii=False, sort_keys=True),
                "Qualified quality: "
                + json.dumps(quality["qualified"]["micro"], ensure_ascii=False, sort_keys=True),
                "Gates: " + json.dumps(quality["gates"], sort_keys=True),
                "",
            )
        )
    for run in cast(list[dict[str, Any]], result.get("runs", [])):
        lines.extend((f"Qualification repetition {run['repetition']}", ""))
        for segment in cast(list[dict[str, Any]], run["segments"]):
            lines.extend(
                (
                    f"Fixture: {segment['fixture_path']}",
                    f"Source segment: {segment['source_segment_label']}",
                    f"Source: {segment['source_text']}",
                    "Candidates: "
                    + json.dumps(segment["candidates"], ensure_ascii=False, sort_keys=True),
                    "Qualification results: "
                    + json.dumps(
                        segment["qualification_results"], ensure_ascii=False, sort_keys=True
                    ),
                    "Validated mentions: "
                    + json.dumps(segment["proposals"], ensure_ascii=False, sort_keys=True),
                    "Qualified pairs: "
                    + json.dumps(segment["qualified_pairs"], ensure_ascii=False, sort_keys=True),
                    "",
                )
            )
        lines.append(
            "Alias decisions: "
            + json.dumps(run["alias_decisions"], ensure_ascii=False, sort_keys=True)
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _candidate_value(candidate: Any) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "source_segment_id": candidate.source_segment_id,
        "source_text_digest": candidate.source_text_digest,
        "text": candidate.text,
        "start": candidate.start,
        "end": candidate.end,
        "observations": [
            {
                "proposer_id": item.proposer_id,
                "text": item.text,
                "start": item.start,
                "end": item.end,
                "score": item.score,
                "model_run_id": item.model_run_id,
            }
            for item in candidate.observations
        ],
    }


def _span_set(segment: dict[str, Any]) -> set[tuple[int, int, str]]:
    return {
        (int(item["start"]), int(item["end"]), str(item["text"]))
        for item in cast(list[dict[str, Any]], segment["proposals"])
    }


def _qwen_true_positives_preserved(
    catalog: tuple[dict[str, Any], ...],
    qwen_segments: list[dict[str, Any]],
    qualified_segments: list[dict[str, Any]],
) -> bool:
    gold = {
        review_segment_key(item): _span_set({"proposals": item["gold_mentions"]})
        for item in catalog
    }
    qwen = {review_segment_key(item): _span_set(item) for item in qwen_segments}
    qualified = {review_segment_key(item): _span_set(item) for item in qualified_segments}
    if set(gold) != set(qwen) or set(gold) != set(qualified):
        raise ValueError("H2.2 preservation gate does not cover the Mention catalog.")
    return all((qwen[key] & gold[key]) <= qualified[key] for key in gold)


def _reanchor_catalog(
    catalog: tuple[dict[str, Any], ...],
    segments: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    current = {review_segment_key(item): str(item["paragraph_node_id"]) for item in segments}
    if set(current) != {review_segment_key(item) for item in catalog}:
        raise ValueError("H2.2 qualification run does not cover the Mention catalog.")
    return tuple(
        {**item, "paragraph_node_id": current[review_segment_key(item)]} for item in catalog
    )


def _nist_alias_resolved(run: dict[str, Any]) -> bool:
    decisions = cast(list[dict[str, Any]], run["alias_decisions"])
    return any(
        item["alias"] == "NIST"
        and item["status"] == "resolved"
        and "National Institute of Standards and Technology" in str(item["expanded_name"])
        for item in decisions
    )


def _mandatory_pairs_preserved(run: dict[str, Any]) -> bool:
    targets = {
        str(item["expectation_id"]): item
        for item in cast(list[dict[str, Any]], run["target_results"])
    }
    return all(
        expectation_id in targets and targets[expectation_id]["candidate_pair_state"] == "present"
        for expectation_id in MANDATORY_PAIR_EXPECTATION_IDS
    )
