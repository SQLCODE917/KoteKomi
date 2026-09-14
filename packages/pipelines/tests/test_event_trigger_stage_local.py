from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_application import (
    HybridEventTriggerStatus,
    build_hybrid_event_trigger_preview,
    derive_source_copy_view,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft, event_trigger_id
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    TriggerStageSegmentEvaluation,
    build_trigger_stage_report,
    evaluate_trigger_segment,
    load_trigger_gold_catalog,
    render_trigger_gold_review,
)
from kotekomi_pipelines.task_allocation_stage_local import load_stage_local_inputs

ROOT = Path(__file__).resolve().parents[3]
SPLIT = ROOT / "docs" / "hsq-stage-local-split-v2.json"
TRIGGER_GOLD = ROOT / "docs" / "hsq-event-trigger-gold-v1.json"


def test_trigger_gold_covers_every_unique_stage_local_segment_and_rejects_unapproved_copy(
    tmp_path: Path,
) -> None:
    _, inputs = load_stage_local_inputs(SPLIT, repository_root=ROOT)

    catalog = load_trigger_gold_catalog(
        TRIGGER_GOLD,
        repository_root=ROOT,
        inputs=inputs,
        require_approved=False,
    )

    assert catalog.review_status == "approved"
    assert len(catalog.segments) == 26
    assert sum(len(item.events) for item in catalog.segments) == 87
    assert {item.source_text_sha256 for item in catalog.segments} == {
        item.source_text_sha256 for item in inputs
    }
    assert (
        load_trigger_gold_catalog(
            TRIGGER_GOLD,
            repository_root=ROOT,
            inputs=inputs,
            require_approved=True,
        )
        == catalog
    )
    proposed_value = catalog.model_dump(mode="json")
    proposed_value["review_status"] = "proposed"
    proposed_path = tmp_path / "proposed-trigger-gold.json"
    proposed_path.write_text(json.dumps(proposed_value), encoding="utf-8")
    with pytest.raises(ValueError, match="human approval"):
        load_trigger_gold_catalog(
            proposed_path,
            repository_root=ROOT,
            inputs=inputs,
            require_approved=True,
        )


def test_trigger_gold_rejects_split_digest_drift(tmp_path: Path) -> None:
    _, inputs = load_stage_local_inputs(SPLIT, repository_root=ROOT)
    value = json.loads(TRIGGER_GOLD.read_bytes())
    value["source_split_sha256"] = "0" * 64
    changed = tmp_path / "changed-trigger-gold.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="source split digest drifted"):
        load_trigger_gold_catalog(
            changed,
            repository_root=ROOT,
            inputs=inputs,
            require_approved=False,
        )


def test_trigger_gold_rejects_unknown_source_occurrence() -> None:
    value = json.loads(TRIGGER_GOLD.read_bytes())
    value["segments"][0]["events"][0]["head_occurrence_id"] = "o999"

    with pytest.raises(ValueError, match="unknown SourceOccurrence"):
        TriggerGoldCatalog.model_validate_json(json.dumps(value))


def test_tge_019_preserves_the_complete_exact_decision_expression() -> None:
    catalog = TriggerGoldCatalog.model_validate_json(TRIGGER_GOLD.read_bytes())
    segment = next(
        item
        for item in catalog.segments
        if any(event.event_id == "TGE-019" for event in item.events)
    )
    event = next(item for item in segment.events if item.event_id == "TGE-019")
    expression = event.accepted_expression_ranges[0]
    source_copy = derive_source_copy_view(segment.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    start, end = source_copy.authoritative_range(
        occurrences[expression.start_occurrence_id].start,
        occurrences[expression.end_occurrence_id].end,
    )

    assert event.head_occurrence_id == "o4"
    assert (expression.start_occurrence_id, expression.end_occurrence_id) == ("o4", "o14")
    assert segment.source_text[start:end] == (
        "decision to attend the World Economic Forum over Trump's second inauguration"
    )


def test_trigger_evaluator_matches_exact_source_spans_without_scoring_label() -> None:
    catalog = TriggerGoldCatalog.model_validate_json(TRIGGER_GOLD.read_bytes())
    gold = next(item for item in catalog.segments if len(item.events) == 1)
    expected = gold.events[0]
    source_copy = derive_source_copy_view(gold.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    expression = expected.accepted_expression_ranges[0]
    start, end = source_copy.authoritative_range(
        occurrences[expression.start_occurrence_id].start,
        occurrences[expression.end_occurrence_id].end,
    )
    head = occurrences[expected.head_occurrence_id]
    head_start, head_end = source_copy.authoritative_range(head.start, head.end)
    segment_id = "seg_trigger_evaluator_fixture"
    linguistic_trace = build_extraction_stage_trace(
        trace_run_id="run_trigger_evaluator_fixture",
        ordinal=0,
        stage_id="linguistic_analysis",
        stage_version="fixture",
        producer_id="fixture",
        source_segment_id=segment_id,
        source_text_sha256=gold.source_text_sha256,
        configuration={},
        input_payload={"source_text": gold.source_text},
        output_payload={"tokens": []},
        status=ExtractionStageStatus.COMPLETED,
    )
    candidate_trace = build_extraction_stage_trace(
        trace_run_id="run_trigger_evaluator_fixture",
        ordinal=1,
        stage_id="event_head_candidate_selection",
        stage_version="stanza_verb_qanom_noun_v1",
        producer_id="fixture",
        source_segment_id=segment_id,
        source_text_sha256=gold.source_text_sha256,
        parent_trace_ids=(linguistic_trace.id,),
        configuration={},
        input_payload={},
        output_payload={
            "candidates": [
                {
                    "occurrence_id": head.occurrence_id,
                    "text": head.text,
                    "start": head.start,
                    "end": head.end,
                }
            ],
            "dispositions": [
                {
                    "occurrence_id": item.occurrence_id,
                    "disposition": (
                        "included" if item.occurrence_id == head.occurrence_id else "excluded"
                    ),
                }
                for item in occurrences.values()
            ],
        },
        status=ExtractionStageStatus.COMPLETED,
    )
    trace = build_extraction_stage_trace(
        trace_run_id="run_trigger_evaluator_fixture",
        ordinal=2,
        stage_id="event_verb_role",
        stage_version="event_verb_role_v1",
        producer_id="fixture",
        source_segment_id=segment_id,
        source_text_sha256=gold.source_text_sha256,
        parent_trace_ids=(candidate_trace.id,),
        execution_record_ids=("ext_trigger_fixture", "mrn_trigger_fixture"),
        configuration={},
        input_payload={"source_text": gold.source_text},
        output_payload={"parsed_answer": "EVENT"},
        status=ExtractionStageStatus.COMPLETED,
    )
    reconciliation_trace = build_extraction_stage_trace(
        trace_run_id="run_trigger_evaluator_fixture",
        ordinal=3,
        stage_id="event_trigger_reconciliation",
        stage_version="target_bound_event_judgment_v5",
        producer_id="fixture",
        source_segment_id=segment_id,
        source_text_sha256=gold.source_text_sha256,
        parent_trace_ids=(trace.id,),
        configuration={},
        input_payload={},
        output_payload={"unclassified_occurrence_ids": []},
        status=ExtractionStageStatus.COMPLETED,
    )
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id=segment_id,
            source_text_sha256=gold.source_text_sha256,
            start=start,
            end=end,
            text=gold.source_text[start:end],
            head_start=head_start,
            head_end=head_end,
            head_text=head.text,
            event_type_label="intentionally_not_gold",
            extraction_task_id="ext_trigger_fixture",
            model_run_id="mrn_trigger_fixture",
            trace_id=reconciliation_trace.id,
        ),
        source_segment_id=segment_id,
        source_text_sha256=gold.source_text_sha256,
        start=start,
        end=end,
        text=gold.source_text[start:end],
        head_start=head_start,
        head_end=head_end,
        head_text=head.text,
        event_type_label="intentionally_not_gold",
        extraction_task_id="ext_trigger_fixture",
        model_run_id="mrn_trigger_fixture",
        trace_id=reconciliation_trace.id,
    )
    preview = build_hybrid_event_trigger_preview(
        parent_preview_id="hgp_" + "1" * 24,
        parent_preview_sha256="a" * 64,
        reference_preview_id="hrp_" + "2" * 24,
        reference_preview_sha256="b" * 64,
        mention_preview_id="hxp_" + "3" * 24,
        mention_preview_sha256="c" * 64,
        representation_id="rep_trigger_fixture",
        paragraph_node_id="nod_trigger_fixture",
        context_manifest_ids=("ctx_trigger_fixture",),
        triggers=(trigger,),
        extraction_task_ids=("ext_trigger_fixture",),
        model_run_ids=("mrn_trigger_fixture",),
        traces=(linguistic_trace, candidate_trace, trace, reconciliation_trace),
        terminal_status=HybridEventTriggerStatus.COMPLETE,
    )

    evaluation = evaluate_trigger_segment(gold, preview)
    report = build_trigger_stage_report(
        phase=gold.phase,
        evaluations=(evaluation,),
        model_execution_count=1,
        model_elapsed_milliseconds=7,
    )

    assert evaluation.passed is True
    assert evaluation.exact_head_matched_event_ids == (expected.event_id,)
    assert evaluation.exact_expression_matched_event_ids == (expected.event_id,)
    assert evaluation.matched_event_ids == (expected.event_id,)
    assert report.passed is True
    assert report.exact_head_match_count == 1
    assert report.exact_expression_match_count == 1
    assert report.unclassified_candidate_count == 0
    assert report.gold_candidate_miss_count == 0
    assert report.proposed_change_count == 0
    assert report.accepted_ledger_change_count == 0


def test_trigger_gold_review_renders_exact_source_heads_and_expressions() -> None:
    catalog = TriggerGoldCatalog.model_validate_json(TRIGGER_GOLD.read_bytes())
    rendered = render_trigger_gold_review(catalog)
    first = catalog.segments[0]
    first_event = first.events[0]
    source_copy = derive_source_copy_view(first.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    head = occurrences[first_event.head_occurrence_id]
    expression = first_event.accepted_expression_ranges[0]
    start = occurrences[expression.start_occurrence_id]
    end = occurrences[expression.end_occurrence_id]

    assert first.source_text in rendered
    assert first_event.meaning in rendered
    assert json.dumps(head.text, ensure_ascii=False) in rendered
    authoritative_start, authoritative_end = source_copy.authoritative_range(
        start.start,
        end.end,
    )
    assert (
        json.dumps(
            first.source_text[authoritative_start:authoritative_end],
            ensure_ascii=False,
        )
        in rendered
    )
    assert rendered.count("Event review: `approved`") == 87
    assert rendered.count("Segment review: `approved`") == 26
    assert hashlib.sha256(rendered.encode()).hexdigest()


def test_zero_candidate_segment_requires_no_model_execution() -> None:
    catalog = TriggerGoldCatalog.model_validate_json(TRIGGER_GOLD.read_bytes())
    gold = catalog.segments[0]
    evaluation = TriggerStageSegmentEvaluation(
        phase=gold.phase,
        source_text_sha256=gold.source_text_sha256,
        expected_event_count=0,
        actual_event_count=0,
        exact_head_matched_event_ids=(),
        exact_expression_matched_event_ids=(),
        matched_event_ids=(),
        missing_event_ids=(),
        extra_trigger_ids=(),
        duplicate_trigger_ids=(),
        bounded_semantic_judgment_count=0,
        failed_model_judgment_count=0,
        source_occurrence_count=3,
        event_head_candidate_count=0,
        classified_candidate_count=0,
        unclassified_candidate_ids=(),
        gold_candidate_miss_event_ids=(),
        complete_candidate_dispositions=True,
        exact_source_mapping=True,
        passed=True,
    )

    report = build_trigger_stage_report(
        phase=gold.phase,
        evaluations=(evaluation,),
        model_execution_count=0,
        model_elapsed_milliseconds=0,
    )

    assert report.passed is True
    assert report.model_execution_count == 0
