from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from kotekomi_application.candidate_wiki import (
    CandidateWikiPlan,
    WikiAuditCatalog,
    WikiCitationRegistry,
    WikiEventPresentation,
    WikiEvidenceReference,
    WikiPageInput,
)
from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V3,
    paragraph_source_segments,
)
from kotekomi_pipelines.task_allocation_evaluation import (
    TASK_ALLOCATION_CASES,
    TaskAllocationBaseline,
    TaskAllocationCatalogEvaluation,
    TaskAllocationCheck,
    TaskAllocationGoldCatalog,
    TaskAllocationItemEvaluation,
    TaskAllocationRunCost,
    compare_task_allocation_baseline,
    evaluate_task_allocation_catalog,
    load_task_allocation_baseline,
    load_task_allocation_evaluator_corrections,
    load_task_allocation_gold,
)

ROOT = Path(__file__).resolve().parents[3]
AMODEI = ROOT / "docs/hsq-task-allocation-amodei-gold-v1.json"
ANTHROPIC = ROOT / "docs/hsq-task-allocation-anthropic-gold-v1.json"
BASELINE = ROOT / "docs/hsq-task-allocation-baseline-2026-09-08.json"
EVALUATOR_CORRECTIONS = ROOT / "docs/hsq-stage-local-evaluator-corrections-v1.json"
BOUNDARY_PROMPT = ROOT / "prompts/hybrid_mention_boundary_adjudication_v2.md"
REFERENCE_PROMPT = ROOT / "prompts/semantic_reference_challenge_v4.md"
REFERENCE_VALIDATION_PROMPT = ROOT / "prompts/semantic_reference_candidate_validation_v1.md"
STANDING_FACT_PROMPT = ROOT / "prompts/hybrid_standing_fact_task_v3.md"
EVENT_PROMPTS = tuple(
    path
    for path in sorted((ROOT / "prompts").glob("event_*_v1.md"))
    if path.name.startswith(("event_noun_", "event_verb_"))
)


def test_development_gold_freezes_seventeen_missing_and_three_demonstrated_items() -> None:
    catalog = load_task_allocation_gold(AMODEI)

    assert catalog.catalog_role == "development"
    assert catalog.focus_entity.name == "Dario Amodei"
    assert catalog.baseline_partition is not None
    assert len(catalog.baseline_partition.previously_missing_item_ids) == 17
    assert len(catalog.baseline_partition.previously_demonstrated_item_ids) == 3


def test_held_out_gold_contains_twenty_frozen_anthropic_items() -> None:
    catalog = load_task_allocation_gold(ANTHROPIC)

    assert catalog.catalog_role == "held_out"
    assert catalog.focus_entity.name == "Anthropic"
    assert catalog.focus_entity.record_type == "Organization"
    assert catalog.baseline_partition is None


def test_two_catalogs_cover_every_diagnosed_task_allocation_boundary() -> None:
    catalogs = (load_task_allocation_gold(AMODEI), load_task_allocation_gold(ANTHROPIC))
    observed = {
        allocation_case
        for catalog in catalogs
        for item in catalog.items
        for allocation_case in item.allocation_cases
    }

    assert observed == TASK_ALLOCATION_CASES


def test_held_out_expectations_are_separate_from_development_expectations() -> None:
    development = load_task_allocation_gold(AMODEI)
    held_out = load_task_allocation_gold(ANTHROPIC)

    assert {item.item_id for item in development.items}.isdisjoint(
        item.item_id for item in held_out.items
    )
    assert development.catalog_id != held_out.catalog_id


def test_boundary_prompt_preserves_complete_proper_name_possessors_without_gold_leakage() -> None:
    prompt = BOUNDARY_PROMPT.read_text()

    assert "A proper name that identifies a referent remains complete" in prompt
    assert "both `Acme` and `Acme's services` are complete" in prompt
    assert "Do not prefer the longest candidate" in prompt
    assert "Complete every line listed under `required_output_prefixes` exactly once" in prompt
    assert "<supplied" not in prompt
    assert "ontology kind" not in prompt
    assert "source offsets" not in prompt
    assert "Ledger records" not in prompt
    assert "Anthropic" not in prompt
    assert "Amodei" not in prompt


def test_reference_prompt_asks_only_for_one_task_local_semantic_choice() -> None:
    prompt = REFERENCE_PROMPT.read_text()

    assert "Perform only semantic antecedent selection" in prompt
    assert "Resolve only the exact target" in prompt
    assert "nearby wording that identifies its occurrence" in prompt
    assert "Select one supplied `aN` label" in prompt
    assert "Return exactly those two lines" in prompt
    assert "smallest complete clause" not in prompt
    assert "Substitute each supplied candidate expression" not in prompt
    assert "F-Coref" not in prompt
    assert "source range" not in prompt
    assert "Entity ID" not in prompt
    assert "Ledger record" not in prompt


def test_reference_validation_prompt_asks_one_binary_semantic_question() -> None:
    prompt = REFERENCE_VALIDATION_PROMPT.read_text()

    assert "one supplied antecedent candidate" in prompt
    assert "Decide only whether the target reference means" in prompt
    assert "`supported`" in prompt
    assert "`unsupported`" in prompt
    assert "`unclear`" in prompt
    assert "Return exactly those two lines" in prompt
    assert "F-Coref" not in prompt
    assert "candidate ID" not in prompt
    assert "source offset" not in prompt
    assert "Ledger" not in prompt


def test_trigger_prompts_each_assign_one_bounded_semantic_task() -> None:
    assert len(EVENT_PROMPTS) == 8
    for path in EVENT_PROMPTS:
        prompt = path.read_text()
        assert "Return exactly one" in prompt
        assert "marked" in prompt.casefold()
        if path.name == "event_verb_role_v1.md":
            assert all(f"{answer} means" in prompt for answer in ("E", "S", "H"))
        else:
            assert " N" in prompt
            assert any(
                f"Answer {answer}" in prompt or f"{answer} means" in prompt for answer in ("E", "Y")
            )
        assert "SourceOccurrence" not in prompt
        assert "occurrence_id" not in prompt
        assert "source offset" not in prompt
        assert "Ledger" not in prompt
        assert "Anthropic" not in prompt
        assert "Amodei" not in prompt


def test_standing_fact_prompt_uses_source_choices_without_gold_leakage() -> None:
    prompt = STANDING_FACT_PROMPT.read_text()

    assert "The occurrence location distinguishes candidates whose names repeat." in prompt
    assert "select the complete phrase as a literal object" in prompt
    assert "select the smallest contiguous relation range" in prompt.casefold()
    assert "literal | <supplied oN[-oN] object selector>" in prompt
    assert "Northstar's policy mirrors Rivera's views on exports" in prompt
    assert "Anthropic" not in prompt
    assert "Amodei" not in prompt
    assert "Ledger" not in prompt
    assert "source offset" not in prompt


def test_amodei_07_is_the_mixed_event_and_standing_fact_gold_contract() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    item = next(item for item in catalog.items if item.item_id == "AMO-07")
    source = _source_segment_text(catalog, item.item_id)

    assert item.expected_route == "standing_fact"
    assert item.expected_standing_fact is not None
    assert item.expected_standing_fact.subject_text == "Anthropic"
    assert item.expected_standing_fact.relation_terms == ("strategy", "mirrored")
    assert item.expected_standing_fact.object_text == "Amodei's views toward Trump"
    assert source.startswith("Anthropic's strategy has mirrored Amodei's views toward Trump;")
    assert all(value in source for value in ("urged", "vote", "describing"))


def test_evaluation_preserves_exact_model_input_output_and_scores_one_bounded_event() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    item = next(item for item in catalog.items if item.item_id == "AMO-18")
    paragraph = _event_paragraph(item.source_segment_sha256)

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(item for item in evaluation.items if item.item_id == "AMO-18")

    assert result.passed is True
    assert result.first_failed_stage is None
    assert result.reached_review is True
    assert result.wiki_visible is None
    assert result.stage_evidence[0].exact_input == "select one supplied occurrence"
    assert result.stage_evidence[0].raw_output == "event: o3 | criticism\n"
    assert result.stage_evidence[0].parsed_output == {"selected": "o3"}


def test_evaluation_names_first_failed_bounded_stage_instead_of_only_counting_misses() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    paragraph = _event_paragraph(
        next(item.source_segment_sha256 for item in catalog.items if item.item_id == "AMO-18")
    )
    stages = cast(dict[str, Any], paragraph["stage_outputs"])
    hp6 = cast(dict[str, Any], stages["hp6_event_semantics"])
    traces = cast(list[dict[str, Any]], hp6["traces"])
    selection = next(
        trace for trace in traces if trace["stage_id"] == "hybrid_event_frame_selection"
    )
    cast(dict[str, Any], selection["output"])["parsed_selection"] = {"frame_id": "agreement"}

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(item for item in evaluation.items if item.item_id == "AMO-18")

    assert result.passed is False
    assert result.first_failed_stage == "bounded_frame_selection"
    assert next(check for check in result.checks if check.check_id == "frame").actual == "agreement"


def test_evaluation_names_missing_focus_mention_before_downstream_absence() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    item = next(item for item in catalog.items if item.item_id == "AMO-18")
    paragraph = _event_paragraph(item.source_segment_sha256)
    stages = cast(dict[str, Any], paragraph["stage_outputs"])
    hp1 = cast(dict[str, Any], stages["hp1_mentions"])
    hp1["candidates"] = []
    hp1["boundary_decisions"] = []
    hp1["interpretations"] = []

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(result for result in evaluation.items if result.item_id == "AMO-18")

    assert result.first_failed_stage == "mention_proposal"


def test_reference_evaluation_joins_by_target_candidate_not_expanded_context_digest() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    item = next(item for item in catalog.items if item.item_id == "AMO-08")
    segment_sha256 = item.source_segment_sha256
    paragraph: dict[str, Any] = {
        "ordinal": 5,
        "stage_outputs": {
            "hp1_mentions": {
                "candidates": [
                    {
                        "id": "candidate-amodei",
                        "source_text_sha256": segment_sha256,
                        "text": "Amodei",
                    },
                    {
                        "id": "candidate-his",
                        "source_text_sha256": segment_sha256,
                        "text": "his",
                    },
                ],
                "boundary_decisions": [
                    {
                        "selected_candidate_ids": ["candidate-amodei", "candidate-his"],
                    }
                ],
                "interpretations": [
                    {
                        "candidate_id": "candidate-amodei",
                        "referentiality": "specific_entity",
                        "contextual_kind": "person",
                    },
                    {
                        "candidate_id": "candidate-his",
                        "referentiality": "anaphoric",
                        "contextual_kind": "person",
                    },
                ],
                "traces": [],
            },
            "hp2_references": {
                "semantic_antecedent_spans": [
                    {"id": "span-amodei", "text": "Amodei"},
                ],
                "reference_decisions": [
                    {
                        "candidate_id": "candidate-his",
                        "antecedent_span_ids": ["span-amodei"],
                        "status": "resolved",
                        "trace_id": "trace-reference",
                    }
                ],
                "traces": [
                    {
                        "id": "trace-reference",
                        "stage_id": "bounded_semantic_reference",
                        "source_text_sha256": "b" * 64,
                        "input": {"model_visible_input": "resolve his from supplied IDs"},
                        "output": {"decision": {"status": "resolved"}},
                        "status": "completed",
                        "execution_record_ids": [],
                    }
                ],
            },
        },
        "raw_model_outputs": {},
    }

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(result for result in evaluation.items if result.item_id == "AMO-08")

    assert result.first_failed_stage == "source_occurrence_selection"
    assert all(check.passed for check in result.checks[:6])
    assert any(item.stage_id == "bounded_semantic_reference" for item in result.stage_evidence)


def test_structured_evaluator_correction_accepts_exact_ant14_source_boundary() -> None:
    catalog = load_task_allocation_gold(ANTHROPIC)
    corrections = load_task_allocation_evaluator_corrections(EVALUATOR_CORRECTIONS)
    item = next(item for item in catalog.items if item.item_id == "ANT-14")
    source = next(source for source in catalog.sources if source.source_id == item.source_id)
    paragraph: dict[str, Any] = {
        "ordinal": source.paragraph_ordinal,
        "stage_outputs": {
            "hp1_mentions": {
                "observations": [
                    {"id": "obs-anthropic", "producer_id": "qwen2.5"},
                    {
                        "id": "obs-he",
                        "producer_id": "kotekomi_reference_marker_v1",
                    },
                ],
                "candidates": [
                    {
                        "id": "candidate-anthropic",
                        "source_text_sha256": item.source_segment_sha256,
                        "text": "Anthropic",
                        "observation_ids": ["obs-anthropic"],
                    },
                    {
                        "id": "candidate-he",
                        "source_text_sha256": item.source_segment_sha256,
                        "text": "he",
                        "observation_ids": ["obs-he"],
                    },
                ],
                "boundary_decisions": [
                    {
                        "selected_candidate_ids": [
                            "candidate-anthropic",
                            "candidate-he",
                        ]
                    }
                ],
                "interpretations": [
                    {
                        "candidate_id": "candidate-anthropic",
                        "referentiality": "specific_entity",
                        "contextual_kind": "organization",
                    }
                ],
                "traces": [],
            },
            "hp2_references": {
                "semantic_antecedent_spans": [
                    {"id": "span-sacks", "text": "David  Sacks"},
                ],
                "reference_decisions": [
                    {
                        "candidate_id": "candidate-he",
                        "antecedent_span_ids": ["span-sacks"],
                        "status": "resolved",
                    }
                ],
                "traces": [],
            },
        },
        "raw_model_outputs": {},
    }

    historical = evaluate_task_allocation_catalog(catalog, [paragraph])
    corrected = evaluate_task_allocation_catalog(
        catalog,
        [paragraph],
        evaluator_corrections=corrections,
    )
    historical_item = next(result for result in historical.items if result.item_id == "ANT-14")
    corrected_item = next(result for result in corrected.items if result.item_id == "ANT-14")

    assert (
        next(
            check for check in historical_item.checks if check.check_id == "reference_resolution_1"
        ).passed
        is False
    )
    corrected_reference = next(
        check for check in corrected_item.checks if check.check_id == "reference_resolution_1"
    )
    assert corrected_reference.passed is True
    corrected_expected = cast(dict[str, object], corrected_reference.expected)
    assert corrected_expected["accepted_antecedent_texts"] == ["David  Sacks"]
    assert corrected_item.first_failed_stage == "source_occurrence_selection"


def test_evaluation_rejects_a_non_boolean_frame_fit_boundary_value() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    item = next(item for item in catalog.items if item.item_id == "AMO-18")
    paragraph = _event_paragraph(item.source_segment_sha256)
    stages = cast(dict[str, Any], paragraph["stage_outputs"])
    hp6 = cast(dict[str, Any], stages["hp6_event_semantics"])
    traces = cast(list[dict[str, Any]], hp6["traces"])
    fit = next(trace for trace in traces if trace["stage_id"] == "hybrid_event_frame_fit")
    cast(dict[str, Any], fit["output"])["parsed_decision"] = {"fits": "yes"}

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(result for result in evaluation.items if result.item_id == "AMO-18")

    assert result.passed is False
    assert result.first_failed_stage == "bounded_frame_fit"
    assert next(check for check in result.checks if check.check_id == "frame_fit").actual is None


def test_unmapped_gold_cannot_be_counted_as_correct_when_a_nearby_frame_is_forced() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    gap = next(item for item in catalog.items if item.item_id == "AMO-10")
    paragraph: dict[str, Any] = {
        "ordinal": 5,
        "stage_outputs": {
            "hp1_mentions": _mention_stage(gap.source_segment_sha256),
            "hp4_event_triggers": {
                "triggers": [
                    {
                        "id": "trigger-cut",
                        "source_text_sha256": gap.source_segment_sha256,
                        "text": "cut",
                        "head_text": "cut",
                    }
                ],
                "traces": [],
            },
            "hp6_event_semantics": {
                "semantic_events": [],
                "assignments": [],
                "targets": [],
                "qualifiers": [],
                "gaps": [
                    {
                        "event_subject_id": "subject-cut",
                        "code": "unmapped_frame",
                    }
                ],
                "traces": [
                    {
                        "stage_id": "hybrid_event_frame_selection",
                        "source_text_sha256": gap.source_segment_sha256,
                        "source_segment_id": "segment-cut",
                        "input": {
                            "trigger": {"id": "trigger-cut"},
                            "event_subject": {"id": "subject-cut"},
                        },
                        "output": {"parsed_selection": {"frame_id": "criticism"}},
                        "status": "completed",
                        "execution_record_ids": [],
                    },
                    {
                        "stage_id": "hybrid_event_frame_fit",
                        "source_text_sha256": gap.source_segment_sha256,
                        "source_segment_id": "segment-cut",
                        "input": {"trigger": {"id": "trigger-cut"}},
                        "output": {"parsed_decision": {"fits": True}},
                        "status": "completed",
                        "execution_record_ids": [],
                    },
                ],
            },
        },
        "raw_model_outputs": {},
    }

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(item for item in evaluation.items if item.item_id == "AMO-10")

    assert result.first_failed_stage == "bounded_frame_selection"
    assert evaluation.wrong_forced_frame_count == 2


def test_candidate_wiki_evaluation_uses_stable_record_identity_across_runs() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    item = next(item for item in catalog.items if item.item_id == "AMO-18")
    paragraph = _event_paragraph(item.source_segment_sha256)
    segment_text = _source_segment_text(catalog, item.item_id)
    stable_event_id = "evt_stargate"
    stages = cast(dict[str, Any], paragraph["stage_outputs"])
    hp7 = cast(dict[str, Any], stages["hp7_proposal_plan"])
    hp7["proposed_changes"] = [
        {
            "id": "pcg-stargate",
            "proposed_json": {"record": {"id": stable_event_id}},
        }
    ]
    plan = _wiki_plan(
        focus_label="Dario Amodei",
        stable_event_id=stable_event_id,
        source_text=segment_text,
    )

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph], wiki_plan=plan)
    result = next(result for result in evaluation.items if result.item_id == "AMO-18")

    assert result.passed is True
    assert result.wiki_visible is True
    assert result.wiki_page_paths == ("actors/Dario-Amodei.md",)


def test_pinned_baseline_preserves_cost_and_corrected_stable_wiki_identity() -> None:
    baseline = load_task_allocation_baseline(BASELINE)
    development = next(
        catalog for catalog in baseline.catalogs if catalog.catalog_role == "development"
    )
    amodei_06 = next(item for item in development.items if item.item_id == "AMO-06")

    assert baseline.cost == TaskAllocationRunCost(
        extraction_task_count=2194,
        model_run_count=2194,
        proposed_change_count=315,
        total_model_elapsed_milliseconds=15_609_774,
    )
    assert len(baseline.catalogs) == 2
    assert all(len(catalog.items) == 20 for catalog in baseline.catalogs)
    assert amodei_06.passed is True
    assert amodei_06.wiki_visible is True
    assert baseline.evaluator_corrections


def test_baseline_comparison_names_per_catalog_gains_regressions_and_cost_delta() -> None:
    baseline = load_task_allocation_baseline(BASELINE)
    evaluations = _baseline_evaluations(
        baseline,
        outcomes={"AMO-01": True, "AMO-06": False, "ANT-01": True},
    )
    current_cost = TaskAllocationRunCost(
        extraction_task_count=2200,
        model_run_count=2201,
        proposed_change_count=320,
        total_model_elapsed_milliseconds=15_600_000,
    )

    comparison = compare_task_allocation_baseline(baseline, evaluations, current_cost)
    development = next(item for item in comparison.catalogs if item.catalog_role == "development")
    held_out = next(item for item in comparison.catalogs if item.catalog_role == "held_out")

    assert development.newly_complete_item_ids == ("AMO-01",)
    assert development.regressed_item_ids == ("AMO-06",)
    assert held_out.newly_complete_item_ids == ("ANT-01",)
    assert held_out.regressed_item_ids == ()
    assert comparison.extraction_task_count_delta == 6
    assert comparison.model_run_count_delta == 7
    assert comparison.proposed_change_count_delta == 5
    assert comparison.total_model_elapsed_milliseconds_delta == -9_774


def _event_paragraph(segment_sha256: str) -> dict[str, Any]:
    subject_id = "subject-stargate"
    semantic_id = "semantic-stargate"
    proposition_id = "proposition-stargate"
    trigger = {
        "id": "trigger-stargate",
        "source_segment_id": "segment-stargate",
        "source_text_sha256": segment_sha256,
        "text": "criticized",
        "head_text": "criticized",
    }
    targets = [
        {"id": "target-critic", "text": "Dario Amodei"},
        {"id": "target-subject", "text": "Stargate"},
        {"id": "target-assessment", "text": "chaotic"},
    ]
    assignments = [
        {
            "event_subject_id": subject_id,
            "frame_role_id": "criticism.critic",
            "target_id": "target-critic",
        },
        {
            "event_subject_id": subject_id,
            "frame_role_id": "criticism.target",
            "target_id": "target-subject",
        },
        {
            "event_subject_id": subject_id,
            "frame_role_id": "criticism.assessment",
            "target_id": "target-assessment",
        },
    ]
    return {
        "ordinal": 3,
        "stage_outputs": {
            "hp1_mentions": _mention_stage(segment_sha256),
            "hp4_event_triggers": {
                "triggers": [trigger],
                "traces": [
                    {
                        "stage_id": "event_trigger_selection",
                        "source_segment_id": "segment-stargate",
                        "source_text_sha256": segment_sha256,
                        "input": {"model_visible_task": "select one supplied occurrence"},
                        "output": {"selected": "o3"},
                        "status": "completed",
                        "execution_record_ids": ["mrn_trigger"],
                    }
                ],
            },
            "hp6_event_semantics": {
                "semantic_events": [
                    {
                        "id": semantic_id,
                        "event_subject_id": subject_id,
                        "trigger_id": trigger["id"],
                        "frame_id": "criticism",
                        "polarity": "affirmed",
                        "modality": "actual",
                        "attribution_kind": "source_narrator",
                    }
                ],
                "assignments": assignments,
                "targets": targets,
                "qualifiers": [
                    {
                        "event_subject_id": subject_id,
                        "kind": "time",
                        "temporal_relation": "at",
                        "text": "January 2025",
                    }
                ],
                "gaps": [],
                "propositions": [{"id": proposition_id, "subject_record_id": semantic_id}],
                "proposition_decisions": [
                    {"proposition_id": proposition_id, "disposition": "supported"}
                ],
                "traces": [
                    {
                        "stage_id": "hybrid_event_frame_selection",
                        "source_segment_id": "segment-stargate",
                        "source_text_sha256": segment_sha256,
                        "input": {
                            "trigger": {"id": trigger["id"]},
                            "event_subject": {"id": subject_id},
                        },
                        "output": {"parsed_selection": {"frame_id": "criticism"}},
                        "status": "completed",
                        "execution_record_ids": [],
                    },
                    {
                        "stage_id": "hybrid_event_frame_fit",
                        "source_segment_id": "segment-stargate",
                        "source_text_sha256": segment_sha256,
                        "input": {"trigger": {"id": trigger["id"]}},
                        "output": {"parsed_decision": {"fits": True}},
                        "status": "completed",
                        "execution_record_ids": [],
                    },
                ],
            },
            "hp7_proposal_plan": {
                "decisions": [
                    {
                        "event_semantic_id": semantic_id,
                        "disposition": "proposed",
                        "proposed_change_ids": ["pcg-stargate"],
                    }
                ],
                "traces": [],
            },
        },
        "raw_model_outputs": {
            "mrn_trigger": {
                "archive_status": "available",
                "raw_output": "event: o3 | criticism\n",
            }
        },
    }


def _mention_stage(segment_sha256: str) -> dict[str, object]:
    return {
        "candidates": [
            {
                "id": "candidate-amodei",
                "source_text_sha256": segment_sha256,
                "text": "Dario Amodei",
            }
        ],
        "boundary_decisions": [
            {
                "selected_candidate_ids": ["candidate-amodei"],
            }
        ],
        "interpretations": [
            {
                "candidate_id": "candidate-amodei",
                "referentiality": "specific_entity",
                "contextual_kind": "person",
            }
        ],
        "traces": [],
    }


def _source_segment_text(catalog: TaskAllocationGoldCatalog, item_id: str) -> str:
    item = next(item for item in catalog.items if item.item_id == item_id)
    source = next(source for source in catalog.sources if source.source_id == item.source_id)
    return next(
        segment.exact_text
        for segment in paragraph_source_segments(source.source_text, PARAGRAPH_SEGMENT_V3)
        if segment.label == item.source_segment_label
    )


def _baseline_evaluations(
    baseline: TaskAllocationBaseline,
    *,
    outcomes: dict[str, bool],
) -> tuple[TaskAllocationCatalogEvaluation, ...]:
    source_text = "authoritative fixture"
    source_sha256 = hashlib.sha256(source_text.encode()).hexdigest()
    evaluations: list[TaskAllocationCatalogEvaluation] = []
    for catalog in baseline.catalogs:
        items: list[TaskAllocationItemEvaluation] = []
        for baseline_item in catalog.items:
            passed = outcomes.get(baseline_item.item_id, baseline_item.passed)
            failed_stage = (
                None if passed else (baseline_item.first_failed_stage or "baseline_regression")
            )
            check_stage = failed_stage or "baseline_comparison"
            items.append(
                TaskAllocationItemEvaluation(
                    item_id=baseline_item.item_id,
                    expected_summary="frozen baseline outcome",
                    expected_route="event",
                    source_segment_text=source_text,
                    source_segment_sha256=source_sha256,
                    checks=(
                        TaskAllocationCheck(
                            check_id="outcome",
                            stage_id=check_stage,
                            passed=passed,
                            expected=True,
                            actual=passed,
                        ),
                    ),
                    first_failed_stage=failed_stage,
                    reached_review=baseline_item.reached_review,
                    wiki_visible=baseline_item.wiki_visible,
                    wiki_page_paths=(),
                    stage_evidence=(),
                    actual={},
                    passed=passed,
                )
            )
        failures: dict[str, int] = {}
        for item in items:
            if item.first_failed_stage is not None:
                failures[item.first_failed_stage] = failures.get(item.first_failed_stage, 0) + 1
        evaluations.append(
            TaskAllocationCatalogEvaluation(
                catalog_id=catalog.catalog_id,
                catalog_role=catalog.catalog_role,
                focus_entity_name="fixture",
                item_count=len(items),
                passed_count=sum(item.passed for item in items),
                review_count=sum(item.reached_review for item in items),
                wiki_visible_count=sum(item.wiki_visible is True for item in items),
                wrong_forced_frame_count=0,
                first_failed_stage_counts=dict(sorted(failures.items())),
                items=tuple(items),
            )
        )
    return tuple(evaluations)


def _wiki_plan(
    *,
    focus_label: str,
    stable_event_id: str,
    source_text: str,
) -> CandidateWikiPlan:
    snapshot_digest = "a" * 64
    citation = WikiEvidenceReference(
        citation_number=1,
        reference_key="proposal:pcg_replay_run",
        reference_kind="proposal_evidence",
        source_id="src_fixture",
        document_id="doc_fixture",
        representation_id="rep_fixture",
        text_view_id="tvw_fixture",
        start_char=0,
        end_char=len(source_text),
        exact_text=source_text,
        prefix_text="",
        suffix_text="",
        node_ids=("nod_fixture",),
        page_numbers=(1,),
        evidence_target_id=None,
        evidence_validation_attempt_id=None,
        proposed_change_id="pcg_replay_run",
    )
    presentation = WikiEventPresentation(
        presentation_id="presentation_fixture",
        event_id=stable_event_id,
        assertion_ids=(),
        proposed_change_ids=("pcg_replay_run",),
        event_label="criticized",
        state="pending",
        edges=(),
        issues=(),
        citation_numbers=(1,),
        related_paths=(),
    )
    page = WikiPageInput(
        relative_path="actors/Dario-Amodei.md",
        page_kind="Actor",
        record_id="act_amodei",
        display_label=focus_label,
        state="pending",
        details=(),
        links=(),
        presentations=(presentation,),
        citation_numbers=(1,),
        input_fingerprint="b" * 64,
    )
    return CandidateWikiPlan(
        view_policy_id="candidate_wiki_view_v5",
        renderer_policy_id="source_grounded_markdown_wiki_v8",
        ingestion_run_id="igr_fixture",
        ingestion_change_set_id="ics_fixture",
        candidate_snapshot_digest=snapshot_digest,
        pages=(page,),
        citation_registry=WikiCitationRegistry(snapshot_digest, (citation,)),
        audit_catalog=WikiAuditCatalog(snapshot_digest, ()),
        counts=(),
    )
