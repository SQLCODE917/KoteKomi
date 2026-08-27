import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _packet_cases() -> Any:
    return _packet_module().packet_cases()


def _packet_module() -> Any:
    support_path = ROOT / "scripts/php1_diagnostic_support.py"
    support_spec = importlib.util.spec_from_file_location("php1_diagnostic_support", support_path)
    assert support_spec is not None
    assert support_spec.loader is not None
    support_module = importlib.util.module_from_spec(support_spec)
    sys.modules[support_spec.name] = support_module
    support_spec.loader.exec_module(support_module)
    packet_path = ROOT / "scripts/verify_php1_packet.py"
    packet_spec = importlib.util.spec_from_file_location("verify_php1_packet", packet_path)
    assert packet_spec is not None
    assert packet_spec.loader is not None
    packet_module = importlib.util.module_from_spec(packet_spec)
    packet_spec.loader.exec_module(packet_module)
    return packet_module


def _support_module() -> Any:
    support_path = ROOT / "scripts/php1_diagnostic_support.py"
    support_spec = importlib.util.spec_from_file_location(
        "php1_diagnostic_support_limit", support_path
    )
    assert support_spec is not None
    assert support_spec.loader is not None
    support_module = importlib.util.module_from_spec(support_spec)
    sys.modules[support_spec.name] = support_module
    support_spec.loader.exec_module(support_module)
    return support_module


def test_php1_packet_diagnostic_loads_each_unique_annotation_row() -> None:
    cases = _packet_cases()

    assert len(cases) == 50  # type: ignore[arg-type]
    assert len({case.case_id for case in cases}) == 50  # type: ignore[union-attr]
    assert {case.case_id for case in cases} >= {  # type: ignore[union-attr]
        "AD-01",
        "AI-01",
        "CS-01",
    }
    assert {case.metadata["provisional_eligibility"] for case in cases} >= {  # type: ignore[union-attr]
        "eligible",
        "control",
        "out_of_scope",
    }


def test_php1_expectation_catalog_is_scoped_to_literal_eligible_organization_pairs() -> None:
    module = _packet_module()
    expectations = module.expectation_catalog(module.packet_cases())

    assert len(expectations) == 12
    assert {item.expectation_id for item in expectations} >= {
        "php1-target-ad-07-anthropic-aisi",
        "php1-target-ai-12-unesco-meity",
        "php1-target-cs-05-anthropic-aisic",
    }
    assert all(item.case_ids for item in expectations)
    assert all(item.subject_text != item.object_text for item in expectations)


def test_php1_expectation_catalog_rejects_unknown_or_ineligible_cases(tmp_path: Path) -> None:
    module = _packet_module()
    payload = {
        "schema_version": module.EXPECTATION_CATALOG_SCHEMA_VERSION,
        "expectations": [
            {
                "expectation_id": "target-one",
                "case_ids": ["AD-01"],
                "fixture_path": "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf",
                "paragraph_anchor": "anchor",
                "source_segment_anchor": "segment",
                "subject_text": "Subject",
                "object_text": "Object",
                "relationship_shape": "shape",
            }
        ],
    }
    catalog = tmp_path / "expectations.json"
    catalog.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="not eligible"):
        module.expectation_catalog(module.packet_cases(), catalog)

    payload["expectations"][0]["case_ids"] = ["unknown"]
    catalog.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown packet case"):
        module.expectation_catalog(module.packet_cases(), catalog)


def test_php1_expectation_catalog_rejects_duplicate_target_identity(tmp_path: Path) -> None:
    module = _packet_module()
    entry = {
        "expectation_id": "target-one",
        "case_ids": ["AD-04"],
        "fixture_path": "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf",
        "paragraph_anchor": "Anthropic privately lobbied for Congress",
        "source_segment_anchor": "Anthropic privately lobbied for Congress",
        "subject_text": "Anthropic",
        "object_text": "Congress",
        "relationship_shape": "directed_action",
    }
    payload = {
        "schema_version": module.EXPECTATION_CATALOG_SCHEMA_VERSION,
        "expectations": [entry, {**entry, "expectation_id": "target-two"}],
    }
    catalog = tmp_path / "expectations.json"
    catalog.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="target identity"):
        module.expectation_catalog(module.packet_cases(), catalog)


def test_php1_segment_v3_prompt_uses_literal_source_segment_labels() -> None:
    prompt = (ROOT / "prompts" / "paragraph_hypothesis_segment_v3.md").read_text(encoding="utf-8")

    assert "SOURCE SEGMENT: sN" in prompt
    assert "claim: s1 |" in prompt
    assert "<sN>" not in prompt
    assert "pronoun" in prompt
    assert "generic description" in prompt


def test_php1_eight_claim_evaluation_measures_only_eligible_claim_batches() -> None:
    support = _support_module()
    raw_output = "\n".join(
        f"claim: s1 | Org {index} | works with | Partner {index}" for index in range(1, 10)
    )

    assert support.evaluate_eight_claim_limit(raw_output, "eligible") == {
        "state": "measured",
        "excess_claim_line_count": 1,
    }
    assert support.evaluate_eight_claim_limit(raw_output, "control") == {
        "state": "not_applicable",
        "excess_claim_line_count": 0,
    }
    assert support.evaluate_eight_claim_limit("abstain: no relation", "eligible") == {
        "state": "not_measurable",
        "excess_claim_line_count": 0,
    }


def test_php1_diagnostic_separates_verifier_rejection_from_publication() -> None:
    support = _support_module()

    rejected = {"faithfulness_rejected_claim_count": 1}
    assert support.diagnostic_segment_status("succeeded", 0, rejected) == "faithfulness_rejected"
    assert support.diagnostic_segment_status("succeeded", 1, rejected) == "complete"
    assert support.diagnostic_case_status({"faithfulness_rejected", "abstained"}) == (
        "faithfulness_rejected"
    )


def test_php1_summary_reports_legacy_cases_and_source_segments() -> None:
    module_path = ROOT / "scripts/verify_php1_packet.py"
    spec = importlib.util.spec_from_file_location("verify_php1_packet_summary", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.summary(
        {
            "status": "completed",
            "cases": [
                {
                    "case_id": "AI-01",
                    "status": "complete",
                    "provisional_eligibility": "eligible",
                    "segments": [{"status": "abstained"}, {"status": "complete"}],
                }
            ],
        }
    )

    assert result["status_counts"] == {"complete": 1}
    assert result["source_segment_report"]["status_counts"] == {
        "abstained": 1,
        "complete": 1,
    }


def test_php1_target_report_requires_the_same_segment_and_ordered_literals() -> None:
    support = _support_module()
    expectation = support.Php1Expectation(
        "target",
        ("AD-04",),
        "raw/source.pdf",
        "paragraph",
        "segment",
        "Anthropic",
        "Congress",
        "directed_action",
    )
    plan = support._ResolvedSegment("raw/source.pdf", "rep", "node", "paragraph", "s1", None)
    resolved: dict[str, dict[str, Any]] = {
        "target": {"resolution_status": "resolved", "diagnostics": [], "plan": plan}
    }
    results: dict[tuple[str, str, str], dict[str, Any]] = {
        plan.key: {
            "status": "abstained",
            "model_run_id": "mrn_one",
            "verified_hypotheses": [],
            "prompt_digest": "prompt",
            "schema_digest": "schema",
            "execution_spec_digest": "execution",
        },
        ("raw/source.pdf", "node", "s2"): {
            "status": "complete",
            "model_run_id": "mrn_two",
            "verified_hypotheses": [
                {
                    "subject_text": "Congress",
                    "relation_text": "was lobbied by",
                    "object_text": "Anthropic",
                    "proposed_change_id": "pcg_reverse",
                },
                {
                    "subject_text": "Anthropic",
                    "relation_text": "lobbied",
                    "object_text": "Congress",
                    "proposed_change_id": "pcg_wrong_segment",
                },
                {
                    "subject_text": "Anthropic",
                    "relation_text": "lobbied",
                    "object_text": "Congress",
                    "proposed_change_id": "pcg_duplicate",
                },
            ],
            "prompt_digest": "prompt",
            "schema_digest": "schema",
            "execution_spec_digest": "execution",
        },
    }

    report = support._target_report((expectation,), resolved, results)

    assert report["target_results"][0]["target_status"] == "missing"
    assert report["target_results"][0]["matched_model_run_ids"] == []
    assert len(report["unexpected_hypotheses"]) == 2


def test_php1_target_report_records_match_block_and_unresolved_once() -> None:
    support = _support_module()
    expectation = support.Php1Expectation(
        "target",
        ("AD-04",),
        "raw/source.pdf",
        "paragraph",
        "segment",
        "Anthropic",
        "Congress",
        "directed_action",
    )
    plan = support._ResolvedSegment("raw/source.pdf", "rep", "node", "paragraph", "s1", None)
    resolved: dict[str, dict[str, Any]] = {
        "target": {"resolution_status": "resolved", "diagnostics": [], "plan": plan}
    }
    matched_results: dict[tuple[str, str, str], dict[str, Any]] = {
        plan.key: {
            "status": "complete",
            "model_run_id": "mrn_one",
            "verified_hypotheses": [
                {
                    "subject_text": "Anthropic",
                    "relation_text": "lobbied",
                    "object_text": "Congress",
                    "proposed_change_id": "pcg_one",
                }
            ],
            "prompt_digest": "prompt",
            "schema_digest": "schema",
            "execution_spec_digest": "execution",
        }
    }
    report = support._target_report((expectation,), resolved, matched_results)
    assert report["target_results"][0]["target_status"] == "matched"
    assert report["target_results"][0]["matched_proposed_change_ids"] == ["pcg_one"]
    assert report["unexpected_hypotheses"] == []

    blocked: dict[str, Any] = {
        **matched_results[plan.key],
        "status": "context_not_ready",
        "verified_hypotheses": [],
    }
    report = support._target_report((expectation,), resolved, {plan.key: blocked})
    assert report["target_results"][0]["target_status"] == "blocked"

    report = support._target_report(
        (expectation,),
        {"target": {"resolution_status": "unresolved", "diagnostics": ["no_match"]}},
        {},
    )
    assert report["target_results"][0]["target_status"] is None
