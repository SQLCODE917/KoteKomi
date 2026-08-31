from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module(name: str) -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_evaluation_preserves_complete_inputs_and_applies_safe_possessive_rule() -> None:
    module = _module("organization_boundary_reconciliation_evaluation")
    report, catalog = _proposal_report()
    result = module.evaluate_boundary_reconciliation(
        report,
        catalog,
        phase="development",
        proposal_report_sha256="a" * 64,
        catalog_sha256="b" * 64,
    )

    assert result["selection_status"] == "selected"
    assert result["gates"] == {
        "zero_wrong_resolved_decisions": True,
        "safe_non_equal_resolution_observed": True,
        "candidate_retention_complete": True,
        "ambiguous_components_have_no_winner": True,
    }
    segment = result["runs"][0]["segments"][0]
    assert segment["qwen"]["prompt_text"] == (
        ROOT / "prompts/paragraph_organization_mention_v1.md"
    ).read_text(encoding="utf-8")
    assert segment["qwen"]["result"]["raw_output"] == "mention: s1 | Anthropic"
    assert segment["gliner"]["effective_configuration"]["threshold"] == 0.5
    assert [trace["stage_id"] for trace in segment["stage_traces"]] == [
        "organization_mention_proposal",
        "organization_mention_proposal",
        "organization_candidate_fusion",
        "organization_boundary_reconciliation",
    ]
    assert segment["reconciliation"]["decisions"][0]["rule_id"] == ("terminal_possessive_suffix_v1")


def test_evaluation_is_byte_deterministic_and_rejects_source_or_prompt_drift() -> None:
    module = _module("organization_boundary_reconciliation_evaluation")
    report, catalog = _proposal_report()
    first = module.evaluate_boundary_reconciliation(
        report,
        catalog,
        phase="development",
        proposal_report_sha256="a" * 64,
        catalog_sha256="b" * 64,
    )
    second = module.evaluate_boundary_reconciliation(
        report,
        catalog,
        phase="development",
        proposal_report_sha256="a" * 64,
        catalog_sha256="b" * 64,
    )
    assert module.canonical_evaluation_json(first) == module.canonical_evaluation_json(second)

    drifted = json.loads(json.dumps(report))
    drifted["proposers"][1]["runs"][0]["segments"][0]["source_text"] = "other"
    with pytest.raises(ValueError, match="Source segment drifted"):
        module.evaluate_boundary_reconciliation(
            drifted,
            catalog,
            phase="development",
            proposal_report_sha256="a" * 64,
            catalog_sha256="b" * 64,
        )
    wrong_prompt = json.loads(json.dumps(report))
    wrong_prompt["proposers"][0]["runs"][0]["segments"][0]["prompt_digest"] = "0" * 64
    with pytest.raises(ValueError, match="prompt digest"):
        module.evaluate_boundary_reconciliation(
            wrong_prompt,
            catalog,
            phase="development",
            proposal_report_sha256="a" * 64,
            catalog_sha256="b" * 64,
        )


def test_held_out_output_cannot_be_overwritten(tmp_path: Path) -> None:
    verifier = _module("verify_organization_boundary_reconciliation")
    output = tmp_path / "held-out.json"
    output.write_text("sealed", encoding="utf-8")

    with pytest.raises(FileExistsError, match="cannot be overwritten"):
        verifier.ensure_output_available(output, "held_out")
    verifier.ensure_output_available(output, "development")


def _proposal_report() -> tuple[dict[str, Any], dict[str, Any]]:
    source = "Anthropic's policy changed."
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    prompt_digest = hashlib.sha256(
        (ROOT / "prompts/paragraph_organization_mention_v1.md").read_bytes()
    ).hexdigest()
    key = {
        "fixture_path": "raw/test.pdf",
        "paragraph_node_id": "nod_test",
        "source_segment_label": "s1",
        "source_text": source,
        "source_text_sha256": digest,
    }
    qwen_segment = {
        **key,
        "status": "complete",
        "model_run_id": "mrn_test",
        "prompt_digest": prompt_digest,
        "raw_output": "mention: s1 | Anthropic",
        "proposals": [{"text": "Anthropic", "start": 0, "end": 9, "score": None}],
    }
    gliner_segment = {
        **key,
        "status": "complete",
        "proposals": [{"text": "Anthropic's", "start": 0, "end": 11, "score": 0.9}],
    }
    report = {
        "status": "completed",
        "schema_version": "php1_span_proposer_comparison_v1",
        "repetitions": 3,
        "proposers": [
            {
                "proposer_id": "qwen2.5-h2-mention-v1",
                "identity": {"name": "qwen2.5-14b-instruct"},
                "runs": [
                    {"repetition": repetition, "segments": [qwen_segment]}
                    for repetition in range(1, 4)
                ],
            },
            {
                "proposer_id": "gliner-medium-v2.1",
                "identity": {"model_id": "gliner", "threshold": 0.5},
                "runs": [
                    {"repetition": repetition, "segments": [gliner_segment]}
                    for repetition in range(1, 4)
                ],
            },
        ],
    }
    catalog = {
        "segments": [
            {
                **key,
                "source_segment_id": "src_test",
                "gold_mentions": [{"text": "Anthropic", "start": 0, "end": 9}],
            }
        ]
    }
    return report, catalog
