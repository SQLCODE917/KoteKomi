import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, cast

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


def test_php1_segment_v6_prompt_calibrates_direct_relation_constructions() -> None:
    prompt = (ROOT / "prompts" / "paragraph_hypothesis_segment_v6.md").read_text(encoding="utf-8")

    assert "SOURCE SEGMENT: sN" in prompt
    assert "claim: s1 |" in prompt
    assert "<sN>" not in prompt
    assert "pronoun" in prompt
    assert "generic description" in prompt
    assert "was founded as part of" in prompt
    assert "established as an evolution of" in prompt
    assert "joined" in prompt
    assert "reached an agreement with" in prompt
    assert "had already partnered with" in prompt
    assert "Through its interoperability with" in prompt
    assert "coordinated participants" in prompt
    assert "no blank lines" in prompt
    assert "Anthropic" not in prompt
    assert "Palantir" not in prompt
    assert "UNESCO" not in prompt


def test_php1_h1_replay_uses_v6_while_the_current_prompt_remains_v3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _packet_module()
    support = _support_module()
    captured: dict[str, object] = {}

    def blocked_run_cases(*_args: object, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "runtime_unavailable", "cases": []}

    monkeypatch.setattr(module, "run_cases", blocked_run_cases)

    result = module.run_h1(None)

    assert support.CURRENT_PHP1_PROMPT.prompt_id == "paragraph_hypothesis_segment_v3"
    assert cast(Any, captured["prompt_contract"]).prompt_id == "paragraph_hypothesis_segment_v6"
    assert result["h1_scorecard"]["status"] == "blocked"


def test_php1_h1_scorecard_defines_held_out_targets_and_observation() -> None:
    module = _packet_module()
    scorecard = module.h1_scorecard(module.expectation_catalog(module.packet_cases()))

    assert scorecard["minimum_matched_count"] == 7
    assert len(scorecard["scored_expectation_ids"]) == 11
    assert scorecard["observation_expectation_ids"] == ["php1-target-ai-12-unesco-meity"]
    assert not (
        set(scorecard["scored_expectation_ids"]) & set(scorecard["observation_expectation_ids"])
    )


def test_php1_h1_scorecard_rejects_unknown_and_overlapping_targets(tmp_path: Path) -> None:
    module = _packet_module()
    payload = json.loads(module.H1_SCORECARD_PATH.read_text(encoding="utf-8"))
    payload["scored_expectation_ids"].append("unknown-target")
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unique known targets"):
        module.h1_scorecard(module.expectation_catalog(module.packet_cases()), path)

    payload = json.loads(module.H1_SCORECARD_PATH.read_text(encoding="utf-8"))
    payload["observation_expectation_ids"] = [payload["scored_expectation_ids"][0]]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="conflicting scored and required targets"):
        module.h1_scorecard(module.expectation_catalog(module.packet_cases()), path)


def test_php1_h1_scorecard_requires_baseline_and_structural_target_groups() -> None:
    module = _packet_module()
    scorecard = module.h1_scorecard(module.expectation_catalog(module.packet_cases()))
    target_results = [
        {"expectation_id": expectation_id, "target_status": "missing"}
        for expectation_id in scorecard["scored_expectation_ids"]
        + scorecard["observation_expectation_ids"]
    ]
    matched = {
        "php1-target-ad-06-anthropic-palantir",
        "php1-target-ad-06-anthropic-aws",
        "php1-target-ad-09-anthropic-palantir",
        "php1-target-ai-03-uk-aisi-frontier-taskforce",
        "php1-target-cs-05-anthropic-aisic",
        "php1-target-ai-04-us-aisi-nist",
        "php1-target-ad-04-anthropic-congress",
    }
    for target in target_results:
        if target["expectation_id"] in matched:
            target["target_status"] = "matched"
    result = {"target_report": {"target_results": target_results, "unexpected_hypotheses": []}}

    scored = module.h1_result(result, scorecard)

    assert scored["status"] == "passed"
    assert scored["matched_count"] == 7
    assert scored["observation_results"] == [
        {"expectation_id": "php1-target-ai-12-unesco-meity", "target_status": "missing"}
    ]

    next(
        item
        for item in target_results
        if item["expectation_id"] == "php1-target-ad-06-anthropic-palantir"
    )["target_status"] = "missing"
    assert module.h1_result(result, scorecard)["status"] == "failed"


def test_php1_h2_derives_source_ordered_candidate_pairs() -> None:
    support = _support_module()
    mentions = (
        support.H2MentionCandidate("Third", 30, 35),
        support.H2MentionCandidate("First", 0, 5),
        support.H2MentionCandidate("Second", 12, 18),
    )

    pairs = support.candidate_pairs(
        tuple(sorted(mentions, key=lambda item: item.source_copy_start))
    )

    assert pairs == (
        support.H2CandidatePair("First", "Second"),
        support.H2CandidatePair("First", "Third"),
        support.H2CandidatePair("Second", "Third"),
    )


def test_php1_h2_classifies_nonlexical_segments_without_a_model_task() -> None:
    support = _support_module()

    assert support.classify_source_segment_model_eligibility("[25][26]") == (
        "not_applicable_nonlexical"
    )
    assert support.classify_source_segment_model_eligibility("(...)") == (
        "not_applicable_nonlexical"
    )
    assert support.classify_source_segment_model_eligibility("Next Steps") == "model_eligible"


def test_php1_h2_prompts_cover_complete_mentions_and_supported_relationship_shapes() -> None:
    mention_prompt = (ROOT / "prompts" / "paragraph_organization_mention_v1.md").read_text(
        encoding="utf-8"
    )
    qualification_prompt = (
        ROOT / "prompts" / "paragraph_organization_qualification_v1.md"
    ).read_text(encoding="utf-8")
    prompt = (ROOT / "prompts" / "paragraph_organization_pair_relation_v1.md").read_text(
        encoding="utf-8"
    )

    assert "coordinated list" in mention_prompt
    assert "complete Organization name" in mention_prompt
    assert "legislature" in mention_prompt
    assert "single proper name can identify an Organization" in mention_prompt
    assert "collective Agent" in mention_prompt
    assert "Scan the segment from left to right" in mention_prompt
    assert "parenthetical" in mention_prompt
    assert "possessive geographic qualifier" in mention_prompt
    assert "no `abstain:` line" in mention_prompt
    assert "Do not comment on the result" in mention_prompt
    assert "government acting collectively" in mention_prompt
    assert "government collective action" in qualification_prompt
    assert "project or initiative that does not denote a collective Agent" in qualification_prompt
    for corpus_name in ("Anthropic", "AISI", "Project Maven", "Stargate", "Palantir"):
        assert corpus_name not in qualification_prompt
    assert "coordinated participants" in prompt
    assert "began consulting" in prompt
    assert "partnership, agreement, membership, containment, lineage" in prompt
    assert "directed action, refusal, or interoperability" in prompt
    assert "established as an evolution of" in prompt
    assert "elided second clause" in prompt
    assert "relationship direction expressed by the source" in prompt
    assert "subject field must equal one candidate exactly" in prompt
    assert "quoted conditions in the relation field" in prompt


def test_php1_h2_prompt_reports_render_full_source_expected_and_actual_results() -> None:
    module = _packet_module()
    expectations = module.expectation_catalog(module.packet_cases())[:1]
    expectation = expectations[0]
    result: dict[str, Any] = {
        "status": "completed",
        "h2_target_report": {
            "target_results": [
                {
                    "expectation_id": expectation.expectation_id,
                    "target_status": "matched",
                    "paragraph_node_id": "node-1",
                    "source_segment_label": "s1",
                    "diagnostics": [],
                }
            ]
        },
        "mention_results": [
            {
                "fixture_path": expectation.fixture_path,
                "paragraph_node_id": "node-1",
                "source_segment_label": "s1",
                "source_copy_text": "Anthropic joined Congress.",
                "status": "complete",
                "raw_output": "mention: s1 | Anthropic\nmention: s1 | Congress",
            }
        ],
        "pair_results": [
            {
                "fixture_path": expectation.fixture_path,
                "paragraph_node_id": "node-1",
                "source_segment_label": "s1",
                "judgments": [
                    {
                        "first_organization_text": expectation.subject_text,
                        "second_organization_text": expectation.object_text,
                        "status": "verified",
                        "raw_output": "claim: s1 | Anthropic | joined | Congress",
                        "faithfulness_accepted_claim_count": 1,
                        "faithfulness_rejected_claim_count": 0,
                    }
                ],
            }
        ],
    }

    mention_report, pair_report = module.render_h2_prompt_reports(result, expectations)

    assert mention_report.startswith("Prompt file: prompts/paragraph_organization_mention_v1.md")
    assert "Source segment:\nAnthropic joined Congress." in mention_report
    assert f"`{expectation.subject_text}` and `{expectation.object_text}`" in mention_report
    assert "Actual result:\nMention status: complete" in mention_report
    assert pair_report.startswith("Prompt file: prompts/paragraph_organization_pair_relation_v1.md")
    assert "Expected result:" in pair_report
    assert "Actual result:\nPair status: verified" in pair_report


def test_php1_h2_target_result_identifies_first_failed_stage() -> None:
    support = _support_module()
    expectation = support.Php1Expectation(
        "target",
        ("AD-06",),
        "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf",
        "paragraph",
        "segment",
        "First Organization",
        "Second Organization",
        "partnership",
    )
    plan = support._ResolvedSegment("fixture", "representation", "paragraph", "text", "s1", None)
    mention_result = {
        "status": "complete",
        "context_manifest_id": "ctx_mention",
        "model_run_id": "mrn_mention",
        "mention_candidates": [
            {
                "organization_text": "First Organization",
                "source_copy_start": 0,
                "source_copy_end": 18,
            },
            {
                "organization_text": "Second Organization",
                "source_copy_start": 20,
                "source_copy_end": 39,
            },
        ],
    }
    pair_result = {
        "first_organization_text": "First Organization",
        "second_organization_text": "Second Organization",
        "status": "verified",
        "model_run_id": "mrn_pair",
        "verified_hypotheses": [
            {
                "subject_text": "First Organization",
                "relation_text": "partnered with",
                "object_text": "Second Organization",
                "proposed_change_id": "prp_01",
            }
        ],
    }

    matched = support.h2_target_result(expectation, plan, mention_result, (pair_result,))

    assert matched["target_status"] == "matched"
    assert matched["subject_mention_state"] == "present"
    assert matched["candidate_pair_state"] == "present"
    missing = support.h2_target_result(
        expectation,
        plan,
        {**mention_result, "mention_candidates": mention_result["mention_candidates"][1:]},
        (),
    )
    assert missing["target_status"] == "subject_mention_missing"


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
