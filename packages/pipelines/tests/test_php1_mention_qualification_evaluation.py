from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    dependency_path = ROOT / "scripts/php1_span_proposer_evaluation.py"
    dependency_spec = importlib.util.spec_from_file_location(
        "php1_span_proposer_evaluation", dependency_path
    )
    assert dependency_spec is not None
    assert dependency_spec.loader is not None
    dependency = importlib.util.module_from_spec(dependency_spec)
    sys.modules[dependency_spec.name] = dependency
    dependency_spec.loader.exec_module(dependency)
    path = ROOT / "scripts/php1_mention_qualification_evaluation.py"
    spec = importlib.util.spec_from_file_location(
        "php1_mention_qualification_evaluation_test", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _module()
assemble_report = MODULE.assemble_report
build_fused_candidate_runs = MODULE.build_fused_candidate_runs
render_review_report = MODULE.render_review_report

SOURCE = "Anthropic met NIST."
DIGEST = hashlib.sha256(SOURCE.encode()).hexdigest()


def _segment(proposals: list[dict[str, Any]], *, model_run_id: str | None = None):
    value = {
        "fixture_path": "raw/test.pdf",
        "paragraph_node_id": "nod_test",
        "source_segment_label": "s1",
        "source_text_sha256": DIGEST,
        "source_text": SOURCE,
        "status": "complete",
        "latency_milliseconds": 10,
        "proposals": proposals,
    }
    if model_run_id is not None:
        value["model_run_id"] = model_run_id
    return value


def _comparison() -> dict[str, Any]:
    qwen_segment = _segment(
        [{"text": "Anthropic", "start": 0, "end": 9, "score": None}],
        model_run_id="mrn_qwen",
    )
    gliner_segment = _segment(
        [
            {"text": "Anthropic", "start": 0, "end": 9, "score": 0.9},
            {"text": "met", "start": 10, "end": 13, "score": 0.6},
            {"text": "NIST", "start": 14, "end": 18, "score": 0.8},
        ]
    )
    return {
        "status": "completed",
        "source_segment_count": 1,
        "case_count": 1,
        "proposers": [
            {
                "proposer_id": "qwen2.5-h2-mention-v1",
                "runs": [
                    {"repetition": repetition, "segments": [qwen_segment]}
                    for repetition in range(1, 4)
                ],
            },
            {
                "proposer_id": "gliner-medium-v2.1",
                "runs": [
                    {"repetition": repetition, "segments": [gliner_segment]}
                    for repetition in range(1, 4)
                ],
            },
        ],
    }


def _catalog() -> tuple[dict[str, Any], ...]:
    return (
        {
            "case_ids": ["TEST-01"],
            "fixture_path": "raw/test.pdf",
            "paragraph_node_id": "nod_test",
            "source_segment_label": "s1",
            "source_text_sha256": DIGEST,
            "gold_mentions": [
                {"text": "Anthropic", "start": 0, "end": 9},
                {"text": "NIST", "start": 14, "end": 18},
            ],
        },
    )


def _qualified_run(repetition: int, proposals: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "repetition": repetition,
        "segments": [
            {
                **_segment(proposals),
                "paragraph_node_id": "nod_reanchored",
                "candidates": [],
                "qualification_results": [],
                "qualified_pairs": [],
            }
        ],
        "alias_decisions": [
            {
                "alias": "NIST",
                "expanded_name": "National Institute of Standards and Technology",
                "expression": "National Institute of Standards and Technology (NIST)",
                "status": "resolved",
            }
        ],
        "target_results": [
            {
                "expectation_id": "php1-target-ad-09-anthropic-palantir",
                "candidate_pair_state": "present",
            }
        ],
    }


def test_fused_candidates_preserve_both_proposers_and_overlaps() -> None:
    runs = build_fused_candidate_runs(_comparison(), {"raw/test.pdf": "rep_test"})

    candidates = runs[0]["segments"][0]["candidates"]
    assert len(candidates) == 3
    assert [item["proposer_id"] for item in candidates[0]["observations"]] == [
        "gliner-medium-v2.1",
        "qwen2.5-h2-mention-v1",
    ]
    assert candidates[1]["text"] == "met"


def test_selection_requires_preservation_precision_recall_alias_and_pair_gates() -> None:
    qualified = [
        {"text": "Anthropic", "start": 0, "end": 9, "score": None},
        {"text": "NIST", "start": 14, "end": 18, "score": None},
    ]
    result = assemble_report(
        _comparison(),
        _catalog(),
        {
            "status": "completed",
            "runs": [_qualified_run(repetition, qualified) for repetition in range(1, 4)],
        },
    )

    assert result["selection_status"] == "selected"
    assert all(item["selection_status"] == "selected" for item in result["quality_runs"])


def test_lost_qwen_true_positive_prevents_selection_and_remains_reviewable() -> None:
    qualified = [{"text": "NIST", "start": 14, "end": 18, "score": None}]
    result = assemble_report(
        _comparison(),
        _catalog(),
        {
            "status": "completed",
            "runs": [_qualified_run(repetition, qualified) for repetition in range(1, 4)],
        },
    )

    assert result["selection_status"] == "not_selected"
    assert result["quality_runs"][0]["gates"]["qwen_true_positives_preserved"] is False
    assert "Selection: not_selected" in render_review_report(result)
