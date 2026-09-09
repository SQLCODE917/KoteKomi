from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from kotekomi_pipelines.task_allocation_evaluation import (
    TASK_ALLOCATION_CASES,
    evaluate_task_allocation_catalog,
    load_task_allocation_gold,
)

ROOT = Path(__file__).resolve().parents[3]
AMODEI = ROOT / "docs/hsq-task-allocation-amodei-gold-v1.json"
ANTHROPIC = ROOT / "docs/hsq-task-allocation-anthropic-gold-v1.json"


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
    semantic = cast(list[dict[str, Any]], hp6["semantic_events"])[0]
    semantic["frame_id"] = "agreement"

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(item for item in evaluation.items if item.item_id == "AMO-18")

    assert result.passed is False
    assert result.first_failed_stage == "bounded_frame_selection"
    assert next(check for check in result.checks if check.check_id == "frame").actual == "agreement"


def test_unmapped_gold_cannot_be_counted_as_correct_when_a_nearby_frame_is_forced() -> None:
    catalog = load_task_allocation_gold(AMODEI)
    gap = next(item for item in catalog.items if item.item_id == "AMO-10")
    paragraph: dict[str, Any] = {
        "ordinal": 5,
        "stage_outputs": {
            "hp4_event_triggers": {
                "triggers": [
                    {
                        "id": "trigger-cut",
                        "source_text_sha256": gap.source_segment_sha256,
                        "text": "cut",
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
                    }
                ],
            },
        },
        "raw_model_outputs": {},
    }

    evaluation = evaluate_task_allocation_catalog(catalog, [paragraph])
    result = next(item for item in evaluation.items if item.item_id == "AMO-10")

    assert result.first_failed_stage == "bounded_frame_selection"
    assert evaluation.wrong_forced_frame_count == 2


def _event_paragraph(segment_sha256: str) -> dict[str, Any]:
    subject_id = "subject-stargate"
    semantic_id = "semantic-stargate"
    proposition_id = "proposition-stargate"
    trigger = {
        "id": "trigger-stargate",
        "source_segment_id": "segment-stargate",
        "source_text_sha256": segment_sha256,
        "text": "criticized",
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
                "traces": [],
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
