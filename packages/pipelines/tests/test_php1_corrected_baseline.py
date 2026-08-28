from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    for name in (
        "php1_span_proposer_evaluation",
        "php1_diagnostic_support",
        "php1_relation_benchmark",
    ):
        if name in sys.modules:
            continue
        path = ROOT / f"scripts/{name}.py"
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None
        assert spec.loader is not None
        dependency = importlib.util.module_from_spec(spec)
        sys.modules[name] = dependency
        spec.loader.exec_module(dependency)
    path = ROOT / "scripts/php1_corrected_baseline.py"
    spec = importlib.util.spec_from_file_location("php1_corrected_baseline_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_compact_summary_binds_full_report_and_quality_counts() -> None:
    module = _module()
    qwen: dict[str, Any] = {
        "proposer_id": "qwen",
        "identity": {"model": "qwen"},
        "quality_runs": [{"micro": {"precision": 0.9, "recall": 0.8, "f1": 0.85}}],
        "stability": {"exact_set_stable_segment_rate": 1.0, "unstable_segments": []},
        "runs": [
            {
                "segments": [
                    {"status": "complete"},
                    {"status": "not_applicable_nonlexical"},
                ]
            }
        ],
    }
    gliner: dict[str, Any] = {
        "proposer_id": "gliner",
        "identity": {"model": "gliner"},
        "quality_runs": [{"micro": {"precision": 0.7, "recall": 0.9, "f1": 0.79}}],
        "stability": {"exact_set_stable_segment_rate": 1.0, "unstable_segments": []},
        "runs": [{"segments": []}],
    }
    result: dict[str, Any] = {
        "status": "completed",
        "input_digests": {"policy": "a" * 64},
        "span_comparison": {
            "source_segment_count": 2,
            "proposers": [qwen, gliner],
        },
        "relation_scores": [
            {
                "repetition": 1,
                "target_count": 2,
                "matched_target_count": 1,
                "missing_target_count": 1,
                "unexpected_accepted_relations": [],
                "pair_task_count": 3,
                "all_pair_tasks_terminal": True,
            }
        ],
    }

    summary = module.compact_baseline_summary(result, b"full report\n")

    assert summary["full_report_sha256"]
    assert summary["model_eligible_segment_count"] == 1
    assert summary["relation_quality_runs"][0]["matched_target_count"] == 1
    assert set(summary["proposer_identity_digests"]) == {"qwen", "gliner"}
