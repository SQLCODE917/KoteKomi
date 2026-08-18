"""Deterministic scorecards and comparisons for TDD metrics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from kotekomi_devtools.evidence_catalog import index_record, state_root
from kotekomi_devtools.tdd_metrics import tdd_metrics

type Json = dict[str, Any]
_SCORE_WEIGHTS = {
    "evidence_confidence": 0.2,
    "verification_completeness": 0.2,
    "lifecycle_completeness": 0.2,
    "scope_discipline": 0.15,
    "first_pass_effectiveness": 0.15,
    "repair_efficiency": 0.1,
}
_REPAIR_DIMENSIONS = ("first_pass_effectiveness", "repair_efficiency")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _round(value: float) -> int:
    return int(value + 0.5)


def score_metrics(metric: Json) -> Json:
    missing = int(metric.get("missing_evidence_count", 0))
    receipt_missing = int(metric.get("receipt_missing_count", 0))
    mismatch = int(metric.get("digest_mismatch_count", 0))
    planned = int(metric.get("planned_check_count", 0))
    verified = int(metric.get("verified_check_count", 0))
    repairs = int(metric.get("repair_count", 0))
    failed = int(metric.get("failed_check_count", 0))
    all_dimensions = {
        "evidence_confidence": 100 - min(100, receipt_missing * 20 + mismatch * 40 + missing * 15),
        "verification_completeness": 100
        if planned == 0 and verified == 0
        else 100 * verified / planned
        if planned
        else 0,
        "lifecycle_completeness": sum(
            [
                100 if metric.get("candidate_lifecycle_ready") else 0,
                100 if metric.get("main_lifecycle_ready") else 0,
                100 if metric.get("candidate_ci_conclusion") == "success" else 0,
                100 if metric.get("main_ci_conclusion") == "success" else 0,
                100 if metric.get("branch_cleanup_complete") else 0,
            ]
        )
        / 5,
        "scope_discipline": 100
        - min(
            100,
            int(metric.get("budget_violation_count", 0)) * 25
            + int(metric.get("protected_artifact_violation_count", 0)) * 50,
        ),
        "first_pass_effectiveness": 100
        - min(
            100,
            repairs * 20
            + failed * 10
            + (0 if metric.get("candidate_ci_conclusion") == "success" else 25),
        ),
        "repair_efficiency": 100 - min(100, repairs * 15),
    }
    repair_history_available = metric.get("repair_history_available") is True
    omitted = [] if repair_history_available else list(_REPAIR_DIMENSIONS)
    dimensions = {
        key: _round(max(0, min(100, value)))
        for key, value in all_dimensions.items()
        if key not in omitted
    }
    scored_weight_total = round(sum(_SCORE_WEIGHTS[key] for key in dimensions), 2)
    provisional_overall_score = None
    if metric["status"] != "blocked":
        provisional_overall_score = _round(
            sum(dimensions[key] * _SCORE_WEIGHTS[key] for key in dimensions) / scored_weight_total
        )
    ranking_eligible = metric["status"] == "complete" or (
        metric["status"] == "partial" and dimensions["evidence_confidence"] > 0
    )
    overall_score = provisional_overall_score if ranking_eligible else None
    diagnostics = list(metric.get("diagnostics", []))
    if not repair_history_available:
        diagnostics.append(
            {
                "code": "scorecard.repair_history_unavailable",
                "location": "/raw_metrics/repair_history_available",
                "rule": "omit_repair_dimensions_and_reweight_available_dimensions",
            }
        )
    return {
        "schema_version": 1,
        "task_id": metric["task_id"],
        "primary_tdd_path": metric["primary_tdd_path"],
        "tdd_paths": metric["tdd_paths"],
        "tdd_sha256": metric["tdd_sha256"],
        "implementation_run_id": metric["implementation_run_id"],
        "status": metric["status"],
        "raw_metrics": metric,
        "score_dimensions": dimensions,
        "omitted_score_dimensions": omitted,
        "scored_weight_total": scored_weight_total,
        "provisional_overall_score": provisional_overall_score,
        "overall_score": overall_score,
        "ranking_eligible": ranking_eligible,
        "diagnostics": diagnostics,
    }


def tdd_score(
    tdd_path: str | None,
    *,
    state_root_path: Path | None = None,
    run_id: str | None = None,
    latest: bool = False,
    output: Path | None = None,
    markdown: Path | None = None,
) -> tuple[int, Json]:
    root = state_root(state_root_path)
    code, metrics = tdd_metrics(tdd_path, state_root_path=root, run_id=run_id, latest=latest)
    cards = [score_metrics(metric) for metric in metrics.get("metrics", [])]
    for card in cards:
        rel = (
            f"experiments/{card['task_id']}/runs/"
            f"{card['implementation_run_id']}/scorecard/tdd-scorecard.json"
        )
        _write(root / rel, card)
        index_record(
            root,
            str(card["task_id"]),
            str(card["implementation_run_id"]),
            phase="complete",
            evidence_type="scorecard_record",
            subject_id=str(card["implementation_run_id"]),
            path_scope="state",
            relative_path=rel,
            producer_command="tdd-score",
        )
    collection_status = (
        "complete"
        if cards and all(card["status"] == "complete" for card in cards)
        else "partial"
        if cards
        else "blocked"
    )
    collection = {
        "schema_version": 1,
        "status": collection_status,
        "scorecard_collection_path": "",
        "scorecard_record_paths": {
            str(card["implementation_run_id"]): (
                f"experiments/{card['task_id']}/runs/"
                f"{card['implementation_run_id']}/scorecard/tdd-scorecard.json"
            )
            for card in cards
        },
        "scorecards": cards,
        "diagnostics": [],
    }
    path = root / (
        f"experiments/{cards[0]['task_id']}/scorecards/tdd-scorecards.collection.json"
        if tdd_path and cards
        else "tdds/reports/scorecards/all-known.scorecards.json"
    )
    collection["scorecard_collection_path"] = str(path)
    _write(path, collection)
    if output:
        _write(output, collection)
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text("# TDD scorecards\n")
    return code, collection


def _comparison(cards: list[Json]) -> tuple[int, Json]:
    if len(cards) < 2:
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "diagnostics": [
                {"code": "compare.inputs", "location": "/", "rule": "at_least_two_scorecards"}
            ],
        }
    digests = [
        hashlib.sha256(json.dumps(card, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        for card in cards
    ]
    if len(set(digests)) != len(digests):
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "diagnostics": [
                {
                    "code": "compare.duplicate",
                    "location": "/scorecard",
                    "rule": "unique_scorecard_digests",
                }
            ],
        }
    identifier = (
        "compare-"
        + hashlib.sha256(json.dumps(sorted(digests), separators=(",", ":")).encode()).hexdigest()[
            :16
        ]
    )
    cards.sort(
        key=lambda card: (
            card.get("status") != "complete",
            -(card.get("overall_score") or -1),
            -card["score_dimensions"]["evidence_confidence"],
            card["implementation_run_id"],
        )
    )
    baseline = cards[0]
    raw_metrics = (
        "planned_check_count",
        "verified_check_count",
        "failed_check_count",
        "repair_count",
    )
    raw_metric_deltas = [
        {
            "implementation_run_id": card["implementation_run_id"],
            "baseline_implementation_run_id": baseline["implementation_run_id"],
            "deltas": {
                field: int(card["raw_metrics"].get(field, 0))
                - int(baseline["raw_metrics"].get(field, 0))
                for field in raw_metrics
            },
        }
        for card in cards
    ]
    score_dimension_deltas = [
        {
            "implementation_run_id": card["implementation_run_id"],
            "baseline_implementation_run_id": baseline["implementation_run_id"],
            "deltas": {
                field: int(card["score_dimensions"][field])
                - int(baseline["score_dimensions"][field])
                for field in sorted(
                    set(card["score_dimensions"]) & set(baseline["score_dimensions"])
                )
            },
        }
        for card in cards
    ]
    return 0, {
        "schema_version": 1,
        "status": "complete",
        "comparison_id": identifier,
        "scorecards": cards,
        "ranking": [card["implementation_run_id"] for card in cards],
        "raw_metric_deltas": raw_metric_deltas,
        "score_dimension_deltas": score_dimension_deltas,
        "diagnostics": [],
    }


def compare_scorecards(
    paths: list[Path],
    *,
    output: Path | None = None,
    markdown: Path | None = None,
    state_root_path: Path | None = None,
) -> tuple[int, Json]:
    try:
        cards = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    except (OSError, json.JSONDecodeError) as error:
        return 1, {
            "schema_version": 1,
            "status": "blocked",
            "diagnostics": [
                {"code": "compare.input", "location": "/scorecard", "rule": str(error)}
            ],
        }
    code, report = _comparison(cards)
    if code:
        return code, report
    root = state_root(state_root_path)
    _write(root / "tdds" / "reports" / "comparisons" / f"{report['comparison_id']}.json", report)
    if output:
        _write(output, report)
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text("# TDD comparison\n")
    return 0, report


def compare_tdds(
    tdd_paths: list[str],
    *,
    output: Path | None = None,
    markdown: Path | None = None,
    state_root_path: Path | None = None,
) -> tuple[int, Json]:
    cards: list[Json] = []
    for tdd_path in tdd_paths:
        code, collection = tdd_score(tdd_path, state_root_path=state_root_path)
        if code or not collection.get("scorecards", []):
            return 1, {
                "schema_version": 1,
                "status": "blocked",
                "diagnostics": [
                    {
                        "code": "compare.tdd",
                        "location": "/tdd_path",
                        "rule": "at_least_one_scorecard_per_tdd",
                    }
                ],
            }
        cards.extend(collection["scorecards"])
    code, report = _comparison(cards)
    if code:
        return code, report
    root = state_root(state_root_path)
    _write(root / "tdds" / "reports" / "comparisons" / f"{report['comparison_id']}.json", report)
    if output:
        _write(output, report)
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text("# TDD comparison\n")
    return 0, report
