from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"


def _load_script() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    path = SCRIPTS / "compare_hp8_compaction.py"
    spec = importlib.util.spec_from_file_location("compare_hp8_compaction", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mention_comparison_uses_source_identity_not_execution_ids() -> None:
    module = _load_script()
    before = _mention_output("mnc_before", "mrn_before")
    after = _mention_output("mnc_after", "mrn_after")

    assert module._stage_signature("mention", before) == module._stage_signature("mention", after)


def test_mention_comparison_exposes_missing_candidate_by_source_span() -> None:
    module = _load_script()
    output = _mention_output("mnc_runtime_specific", "mrn_runtime_specific")
    output["interpretations"] = []

    signature = cast(dict[str, Any], module._stage_signature("mention", output))

    assert signature["missing_candidates"] == [
        {
            "source_text_sha256": "a" * 64,
            "start": 0,
            "end": 9,
            "text": "Anthropic",
        }
    ]
    assert "mnc_runtime_specific" not in str(signature)


def test_support_comparison_uses_source_meaning_not_execution_ids() -> None:
    module = _load_script()
    before = _support_output("etg_before", "sst_before", "spj_before", "mrn_before")
    after = _support_output("etg_after", "sst_after", "spj_after", "mrn_after")

    assert module._stage_signature("support", before) == module._stage_signature("support", after)


def test_support_comparison_detects_changed_outcome() -> None:
    module = _load_script()
    before = _support_output("etg_before", "sst_before", "spj_before", "mrn_before")
    after = _support_output("etg_after", "sst_after", "spj_after", "mrn_after")
    after["traces"][0]["output"]["support_judgment"]["outcome"] = "unsupported"

    assert module._stage_signature("support", before) != module._stage_signature("support", after)


def test_changed_output_requires_reviewed_adjudication() -> None:
    module = _load_script()
    baseline = _report(_mention_output("mnc_before", "mrn_before"))
    candidate_output = _mention_output("mnc_after", "mrn_after")
    candidate_output["interpretations"][0]["discourse_role"] = "participant"
    candidate = _report(candidate_output)
    runs = [_execution("mrn_before", 20), _execution("mrn_after", 10)]

    unreviewed = module._compare(
        stage="mention",
        baseline=baseline,
        candidate=candidate,
        baseline_executions=[runs[0]],
        candidate_executions=[runs[1]],
    )
    digest = unreviewed["paragraphs"][0]["source_text_sha256"]
    reviewed = module._compare(
        stage="mention",
        baseline=baseline,
        candidate=candidate,
        baseline_executions=[runs[0]],
        candidate_executions=[runs[1]],
        adjudications={(0, digest): ("improvement", "The new role follows the source verb.")},
    )

    assert unreviewed["summary"]["quality_passed"] is False
    assert unreviewed["paragraphs"][0]["assessment"] == "inconclusive"
    assert reviewed["summary"]["quality_passed"] is True
    assert reviewed["paragraphs"][0]["assessment"] == "improvement"


def _report(output: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_sha256": "a" * 64,
        "first_ledger_counts": {
            "accepted_actors": 0,
            "accepted_organizations": 0,
            "accepted_events": 0,
            "accepted_assertions": 0,
        },
        "summary": {
            "passed": True,
            "approved_gold_events_observed": 7,
            "approved_gold_events_expected": 7,
            "known_false_events_observed": 1,
            "known_false_events_expected": 1,
            "replay_model_calls": 0,
        },
        "paragraphs": [
            {
                "ordinal": 0,
                "authoritative_text": "Anthropic announced.",
                "paragraph_work": {"paragraph_node_id": "nod_authoritative"},
                "stage_outputs": {"hp1_mentions": output},
            }
        ],
    }


def _execution(model_run_id: str, elapsed: int) -> dict[str, Any]:
    return {
        "model_run_id": model_run_id,
        "execution_diagnostics": {"elapsed_milliseconds": elapsed},
    }


def _mention_output(candidate_id: str, model_run_id: str) -> dict[str, Any]:
    return {
        "terminal_status": "complete",
        "traces": [
            {
                "stage_id": "mention_interpretation",
                "execution_record_ids": [model_run_id],
            }
        ],
        "candidates": [
            {
                "id": candidate_id,
                "source_segment_id": "seg_authoritative",
                "source_text_sha256": "a" * 64,
                "start": 0,
                "end": 9,
                "text": "Anthropic",
            }
        ],
        "interpretations": [
            {
                "candidate_id": candidate_id,
                "referentiality": "specific_entity",
                "contextual_kind": "organization",
                "discourse_role": "actor",
                "support_segment_id": "seg_authoritative",
                "model_run_id": model_run_id,
            }
        ],
    }


def _support_output(
    evidence_target_id: str,
    statement_id: str,
    judgment_id: str,
    model_run_id: str,
) -> dict[str, Any]:
    return {
        "terminal_status": "complete",
        "traces": [
            {
                "stage_id": "hybrid_semantic_source_support",
                "execution_record_ids": [model_run_id],
                "input": {
                    "evidence_target": {
                        "id": evidence_target_id,
                        "source_id": f"src_{evidence_target_id}",
                        "document_id": f"doc_{evidence_target_id}",
                        "representation_id": f"rep_{evidence_target_id}",
                        "text_view_id": f"tvw_{evidence_target_id}",
                        "text_view_digest": "a" * 64,
                        "start_char": 10,
                        "end_char": 30,
                        "exact_text": "Anthropic announced.",
                        "prefix_text": "",
                        "suffix_text": "",
                        "normalization_policy": "source_v1",
                        "dom_selector": None,
                        "table_selector": None,
                        "node_ids": [f"nod_{evidence_target_id}"],
                        "pdf_region_ids": [],
                        "created_at": "2026-09-03T00:00:00Z",
                    },
                    "semantic_statement": {
                        "id": statement_id,
                        "event_semantic_id": f"esn_{statement_id}",
                        "subject_record_id": f"evt_{statement_id}",
                        "evidence_target_id": evidence_target_id,
                        "kind": "frame",
                        "text": "The event expressed by announced is an announcement event.",
                        "governed_definition": "One entity makes information public.",
                    },
                },
                "output": {
                    "model_run_status": "succeeded",
                    "support_judgment": {
                        "id": judgment_id,
                        "statement_id": statement_id,
                        "evidence_target_id": evidence_target_id,
                        "extraction_task_id": f"ext_{judgment_id}",
                        "model_run_id": model_run_id,
                        "outcome": "directly_supported",
                        "reason": "The evidence states that Anthropic announced.",
                    },
                },
            }
        ],
    }
