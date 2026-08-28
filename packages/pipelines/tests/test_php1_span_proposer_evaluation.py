from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    path = ROOT / "scripts/php1_span_proposer_evaluation.py"
    spec = importlib.util.spec_from_file_location("php1_span_proposer_evaluation_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _source(text: str = "Anthropic met Palantir.") -> dict[str, Any]:
    import hashlib

    return {
        "case_ids": ["AD-TEST"],
        "fixture_path": "raw/test.pdf",
        "fixture_sha256": "a" * 64,
        "representation_id": "rep_test",
        "paragraph_node_id": "nod_test",
        "source_segment_label": "s1",
        "source_text": text,
        "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _catalog_segment(source: dict[str, Any]) -> dict[str, Any]:
    return {
        key: source[key]
        for key in (
            "case_ids",
            "fixture_path",
            "fixture_sha256",
            "paragraph_node_id",
            "source_segment_label",
            "source_text_sha256",
        )
    } | {
        "gold_mentions": [
            {"text": "Anthropic", "start": 0, "end": 9},
            {"text": "Palantir", "start": 14, "end": 22},
        ]
    }


def test_catalog_requires_complete_exact_source_coverage(tmp_path: Path) -> None:
    module = _module()
    source = _source()
    catalog = {
        "schema_version": module.CATALOG_SCHEMA_VERSION,
        "annotation_status": "provisional_agent_authored",
        "segments": [_catalog_segment(source)],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    result = module.load_and_validate_catalog(
        path,
        {"status": "completed", "segments": [source]},
    )

    assert result[0]["gold_mentions"][1]["text"] == "Palantir"


def test_catalog_reanchors_after_only_the_derived_node_id_changes(tmp_path: Path) -> None:
    module = _module()
    source = _source()
    catalog_segment = _catalog_segment(source)
    catalog_segment["paragraph_node_id"] = "nod_prior_build"
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": module.CATALOG_SCHEMA_VERSION,
                "annotation_status": "provisional_agent_authored",
                "segments": [catalog_segment],
            }
        ),
        encoding="utf-8",
    )

    result = module.load_and_validate_catalog(
        path,
        {"status": "completed", "segments": [source]},
    )

    assert result[0]["catalog_paragraph_node_id"] == "nod_prior_build"
    assert result[0]["paragraph_node_id"] == "nod_test"


def test_project_catalog_covers_all_packet_cases_and_unique_segments() -> None:
    catalog = json.loads(
        (ROOT / "docs/php1-organization-mention-gold-v1.json").read_text(encoding="utf-8")
    )

    assert len(catalog["segments"]) == 164
    assert len({case_id for item in catalog["segments"] for case_id in item["case_ids"]}) == 50
    assert sum(len(item["gold_mentions"]) for item in catalog["segments"]) == 174
    assert sum(not item["gold_mentions"] for item in catalog["segments"]) == 83


def test_catalog_rejects_source_digest_and_span_drift(tmp_path: Path) -> None:
    module = _module()
    source = _source()
    catalog_segment = _catalog_segment(source)
    catalog_segment["source_text_sha256"] = "b" * 64
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": module.CATALOG_SCHEMA_VERSION,
                "annotation_status": "provisional_agent_authored",
                "segments": [catalog_segment],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="drifted"):
        module.load_and_validate_catalog(path, {"status": "completed", "segments": [source]})


def test_qwen_name_expands_to_every_exact_occurrence() -> None:
    module = _module()

    result = module.exact_name_occurrences("Anthropic met Anthropic.", "Anthropic")

    assert [(item["start"], item["end"]) for item in result] == [(0, 9), (14, 23)]


def test_scoring_reports_exact_and_boundary_failures() -> None:
    module = _module()
    gold = [
        {"text": "Anthropic", "start": 0, "end": 9},
        {"text": "Palantir", "start": 14, "end": 22},
    ]
    proposals = [
        {"text": "Anthropic", "start": 0, "end": 9},
        {"text": "Palanti", "start": 14, "end": 21},
        {"text": "met", "start": 10, "end": 13},
    ]

    result = module.score_segment(gold, proposals)

    assert result["true_positive_count"] == 1
    assert result["false_positive_count"] == 2
    assert result["false_negative_count"] == 1
    assert result["boundary_counts"] == {
        "exact": 1,
        "truncated": 1,
        "expanded": 0,
        "crossing": 0,
        "missing": 0,
    }


def test_latency_and_three_run_stability_are_separate_metrics() -> None:
    module = _module()
    source = _source()
    base = {
        "fixture_path": source["fixture_path"],
        "paragraph_node_id": source["paragraph_node_id"],
        "source_segment_label": source["source_segment_label"],
        "latency_milliseconds": 10,
        "proposals": [{"text": "Anthropic", "start": 0, "end": 9}],
    }
    runs = [
        {"repetition": 1, "segments": [base]},
        {"repetition": 2, "segments": [{**base, "latency_milliseconds": 20}]},
        {"repetition": 3, "segments": [{**base, "latency_milliseconds": 30}]},
    ]

    assert module.latency_summary(runs) == {
        "measured_segment_count": 3,
        "p50_milliseconds": 20,
        "p95_milliseconds": 30,
        "total_milliseconds": 60,
    }
    assert module.stability_summary(runs)["exact_set_stable_segment_rate"] == 1.0


def test_review_report_shows_gold_and_each_proposer_for_every_segment() -> None:
    module = _module()
    source = _source("Anthropic")
    gold = {
        **_catalog_segment(source),
        "catalog_paragraph_node_id": "nod_prior_build",
    }
    gold["gold_mentions"] = [{"text": "Anthropic", "start": 0, "end": 9}]
    segment = {
        **source,
        "latency_milliseconds": 10,
        "proposals": [{"text": "Anthropic", "start": 0, "end": 9, "score": 0.9}],
    }
    runs = [
        {"repetition": repetition, "segments": [segment]}
        for repetition in range(1, module.REPETITIONS + 1)
    ]
    catalog = (gold,)
    result = {
        "status": "completed",
        "source_segment_count": 1,
        "proposers": [
            module.proposer_report("qwen", {}, catalog, runs, load_elapsed_milliseconds=None),
            module.proposer_report("gliner", {}, catalog, runs, load_elapsed_milliseconds=5),
        ],
    }

    report = module.render_review_report(result, catalog)

    assert "Source: Anthropic" in report
    assert 'Gold mentions: [{"end": 9, "start": 0, "text": "Anthropic"}]' in report
    assert "qwen repetition 3" in report
    assert "gliner repetition 3" in report
