from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _proposer_segment(
    source_text: str,
    proposals: list[dict[str, Any]],
    *,
    raw_output: str | None,
) -> dict[str, Any]:
    return {
        "fixture_path": "raw/test.pdf",
        "paragraph_node_id": "nod_test",
        "source_segment_label": "s1",
        "source_text_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
        "source_text": source_text,
        "status": "complete",
        "model_eligibility": "model_eligible",
        "model_run_id": "run_test" if raw_output is not None else None,
        "prompt_digest": "p" * 64 if raw_output is not None else None,
        "raw_output": raw_output,
        "proposals": proposals,
    }


def _fusion_baseline() -> dict[str, Any]:
    source_text = "Anthropic met Palantir."
    qwen_segment = _proposer_segment(
        source_text,
        [{"text": "Anthropic", "start": 0, "end": 9, "score": None}],
        raw_output="mention: s1 | Anthropic",
    )
    gliner_segment = _proposer_segment(
        source_text,
        [
            {"text": "Anthropic", "start": 0, "end": 9, "score": 0.9},
            {"text": "Palantir", "start": 14, "end": 22, "score": 0.8},
        ],
        raw_output=None,
    )
    return {
        "span_comparison": {
            "catalog": [
                {
                    "fixture_path": "raw/test.pdf",
                    "paragraph_node_id": "nod_test",
                    "source_segment_label": "s1",
                    "source_text_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
                    "gold_mentions": [
                        {"text": "Anthropic", "start": 0, "end": 9},
                        {"text": "Palantir", "start": 14, "end": 22},
                    ],
                }
            ],
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
    }


def _module() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    dependencies = (
        "php1_span_proposer_evaluation",
        "php1_diagnostic_support",
        "php1_relation_benchmark",
        "php1_corrected_baseline",
    )
    for name in dependencies:
        if name in sys.modules:
            continue
        path = ROOT / f"scripts/{name}.py"
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None
        assert spec.loader is not None
        dependency = importlib.util.module_from_spec(spec)
        sys.modules[name] = dependency
        spec.loader.exec_module(dependency)
    path = ROOT / "scripts/php1_monotonic_gliner_rescue.py"
    spec = importlib.util.spec_from_file_location("php1_monotonic_gliner_rescue_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_comparison_gates_require_monotonic_mentions_and_relation_gain() -> None:
    module = _module()
    baseline_segment = {
        "fixture_path": "raw/test.pdf",
        "source_text_sha256": "a" * 64,
        "source_segment_label": "s1",
        "proposals": [{"text": "Anthropic", "start": 0, "end": 9}],
    }
    fusion_segment = {
        **baseline_segment,
        "proposals": [
            {"text": "Anthropic", "start": 0, "end": 9},
            {"text": "Palantir", "start": 20, "end": 28},
        ],
    }
    baseline_qwen = {
        "quality_runs": [{"micro": {"recall": 0.5}}] * 3,
        "runs": [{"segments": [baseline_segment]}] * 3,
    }
    baseline_relation = [
        {
            "matched_target_count": 1,
            "target_results": [{"expectation_id": "baseline", "target_status": "matched"}],
        }
    ] * 3
    fusion_relation = [
        {
            "matched_target_count": 2,
            "target_results": [
                {"expectation_id": "baseline", "target_status": "matched"},
                {"expectation_id": "rescue", "target_status": "matched"},
            ],
            "unexpected_accepted_relations": [],
            "all_pair_tasks_terminal": True,
        }
    ] * 3

    gates = module.comparison_gates(
        baseline_qwen,
        baseline_relation,
        [{"segments": [fusion_segment]}] * 3,
        [{"micro": {"recall": 0.75}}] * 3,
        fusion_relation,
    )

    assert all(gates.values())


def test_monotonic_fusion_trace_binds_gold_source_and_each_proposer_output() -> None:
    module = _module()

    runs = module.build_monotonic_fusion_runs(_fusion_baseline())

    segment = runs[0]["segments"][0]
    assert segment["gold_mentions"][1]["text"] == "Palantir"
    assert segment["baseline_input"]["raw_output"] == "mention: s1 | Anthropic"
    assert segment["rescue_input"]["proposals"][1]["text"] == "Palantir"
    assert [item["text"] for item in segment["mention_candidates"]] == [
        "Anthropic",
        "Palantir",
    ]
    assert segment["source_text_sha256"] == segment["mention_candidates"][0]["source_text_digest"]


def test_baseline_binding_rejects_partial_and_drifted_evidence() -> None:
    module = _module()
    report_bytes = b'{"status":"completed"}\n'
    inputs = {"policy": "a" * 64}
    module.corrected_baseline_input_digests = lambda: inputs

    def identity_digests(_comparison: dict[str, Any]) -> dict[str, str]:
        return {"qwen": "b" * 64}

    module.proposer_identity_digests = identity_digests
    baseline: dict[str, Any] = {
        "status": "completed",
        "schema_version": "php1_corrected_baseline_v1",
        "input_digests": inputs,
        "span_comparison": {"proposers": []},
    }
    summary = {
        "full_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "proposer_identity_digests": {"qwen": "b" * 64},
    }

    module.validate_baseline_binding(baseline, summary, report_bytes)

    with pytest.raises(ValueError, match="completed corrected baseline"):
        module.validate_baseline_binding({**baseline, "status": "blocked"}, summary, report_bytes)
    with pytest.raises(ValueError, match="repository inputs drifted"):
        module.validate_baseline_binding(
            {**baseline, "input_digests": {"policy": "b" * 64}},
            summary,
            report_bytes,
        )
    with pytest.raises(ValueError, match="model identities drifted"):
        module.validate_baseline_binding(
            baseline,
            {**summary, "proposer_identity_digests": {"qwen": "c" * 64}},
            report_bytes,
        )


def test_comparison_gates_reject_lost_baseline_behavior_and_false_relations() -> None:
    module = _module()
    segment = {
        "fixture_path": "raw/test.pdf",
        "source_text_sha256": "a" * 64,
        "source_segment_label": "s1",
        "proposals": [{"text": "Anthropic", "start": 0, "end": 9}],
    }
    baseline_qwen = {
        "quality_runs": [{"micro": {"recall": 0.5}}] * 3,
        "runs": [{"segments": [segment]}] * 3,
    }
    baseline_relation = [
        {
            "matched_target_count": 1,
            "target_results": [{"expectation_id": "baseline", "target_status": "matched"}],
        }
    ] * 3
    fusion_relation = [
        {
            "matched_target_count": 1,
            "target_results": [],
            "unexpected_accepted_relations": [{"relation_text": "wrong"}],
            "all_pair_tasks_terminal": True,
        }
    ] * 3

    gates = module.comparison_gates(
        baseline_qwen,
        baseline_relation,
        [{"segments": [{**segment, "proposals": []}]}] * 3,
        [{"micro": {"recall": 0.6}}] * 3,
        fusion_relation,
    )

    assert gates["baseline_mentions_retained"] is False
    assert gates["baseline_targets_retained"] is False
    assert gates["additional_relation_target_matched"] is False
    assert gates["no_unexpected_accepted_relation"] is False


def test_review_report_exposes_baseline_gates_and_unexpected_relations() -> None:
    module = _module()
    result = {
        "status": "completed",
        "selection_status": "not_selected",
        "baseline_full_report_sha256": "a" * 64,
        "baseline_input_digests": {"gold": "b" * 64},
        "proposer_identities": {"gliner": {"model_revision": "revision"}},
        "gates": {"baseline_mentions_retained": True, "no_false_relation": False},
        "mention_scores": [{"micro": {"precision": 0.6, "recall": 0.8, "f1": 0.7}}],
        "relation_scores": [
            {
                "repetition": 1,
                "matched_target_count": 2,
                "target_count": 3,
                "pair_task_count": 1,
                "unexpected_accepted_relations": [
                    {
                        "subject_text": "Palantir",
                        "relation_text": "interoperability with",
                        "object_text": "Anthropic",
                        "fixture_path": "raw/test.pdf",
                        "source_segment_label": "s1",
                    }
                ],
            }
        ],
        "fusion_runs": [
            {
                "repetition": 1,
                "segments": [
                    {
                        "fixture_path": "raw/test.pdf",
                        "paragraph_node_id": "nod_test",
                        "source_segment_label": "s1",
                        "source_text_sha256": "b" * 64,
                        "source_text": "Anthropic met Palantir.",
                        "gold_mentions": [{"text": "Anthropic", "start": 0, "end": 9}],
                        "baseline_input": {"proposals": [{"text": "Anthropic"}]},
                        "rescue_input": {"proposals": [{"text": "Palantir"}]},
                        "mention_candidates": [{"text": "Anthropic"}],
                        "candidate_groups": [{"preferred_text": "Anthropic"}],
                        "candidate_pairs": [
                            {
                                "first_candidate_text": "Anthropic",
                                "second_candidate_text": "Palantir",
                            }
                        ],
                        "pair_exclusions": [],
                    }
                ],
            }
        ],
        "combined_relation_runs": [
            {
                "repetition": 1,
                "segments": [
                    {
                        "fixture_path": "raw/test.pdf",
                        "paragraph_node_id": "nod_test",
                        "source_segment_label": "s1",
                        "source_copy_text": "Anthropic met Palantir.",
                        "pair_results": [
                            {
                                "first_organization_text": "Anthropic",
                                "second_organization_text": "Palantir",
                                "status": "pair_abstained",
                                "raw_output": "abstain",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    review = module.render_rescue_review_report(result)

    assert f"Baseline report: {'a' * 64}" in review
    assert "no_false_relation: fail" in review
    assert '"model_revision": "revision"' in review
    assert "Palantir | interoperability with | Anthropic" in review
    assert "Source input: Anthropic met Palantir." in review
    assert "Qwen input/output" in review
    assert "GLiNER input/output" in review
    assert "Pair input/output" in review
    summary = module.compact_rescue_summary(result, b"full report\n")
    assert summary["quality_runs"][0]["mention_candidate_count"] == 1
    assert summary["quality_runs"][0]["candidate_pair_count"] == 1
    assert summary["quality_runs"][0]["pair_exclusion_count"] == 0
